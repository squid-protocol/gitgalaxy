#!/usr/bin/env python3
"""
class_start Named-Entity Diff -- offline triage tool for #1295

Companion to `tree_sitter_accuracy_audit.py`. That script answers "how many
classes did GitGalaxy find" (aggregate counts, baseline-gated). This script
answers the question you actually need before touching a language: "which
*specific names* are wrong, and what does the source line around each one
look like" -- the per-file `gg_classes - real_classes` / `real_classes -
gg_classes` diff that #1264's own investigation had to write ad hoc for
csharp and fortran. Made permanent so the next language doesn't repeat that.

BACKGROUND
    #1264 found that `detector.py`'s named-entity class extractor (feeds
    `class_data`/`class_count`) used one hardcoded, language-agnostic regex
    instead of each language's own `class_start` rule. Fixed for 18
    languages verified clean, gated behind `_CLASS_START_NAMED_EXTRACTION_LANGS`
    in `gitgalaxy/core/detector.py`. 13 more languages regressed when tried
    the same way and were left on the legacy fallback -- extending the
    allowlist to them is #1295's job, using this tool.

WHAT THIS PREVIEWS
    For a given `--lang`, this applies that language's OWN `class_start` rule
    (via `_resolve_class_start_match`, the exact same function
    `StructuralExtractor.splice()` calls -- imported, not reimplemented, so
    this can never silently drift from the real pipeline's name-resolution
    algorithm) against each corpus file's RAW text, regardless of whether the
    language is currently in the allowlist. This lets you preview a language
    BEFORE editing detector.py at all.

    File selection and language detection still go through a real
    `galaxyscope` scan (`run_engine_scan`, borrowed from
    tree_sitter_accuracy_audit.py) so you get GitGalaxy's actual ecosystem-
    aware file-to-language assignment, not a naive extension guess.

CAVEAT -- this is a triage approximation, not the authoritative check
    Matching against raw file text skips `prism.py`'s comment/string
    shielding, so a `class_start` match sitting inside a string literal or
    comment could show up here but never fire in the real pipeline (or vice
    versa). This tool is for fast, cheap triage of *which names* are extra/
    missing and *why* -- it is not a substitute for the real verification
    sequence once a language looks ready:
        1. add the language to `_CLASS_START_NAMED_EXTRACTION_LANGS` in
           gitgalaxy/core/detector.py
        2. python tests/tools/tree_sitter_accuracy_audit.py --lang <x> --ci
        3. python tests/tools/tree_sitter_accuracy_audit.py --lang <x> --regenerate
        4. python tests/tools/crucible_check.py (both modes)
    See tests/extraction/how_to_extend_class_start_named_extraction.md for
    the full checklist.

USAGE
    python tests/tools/class_start_diff.py --lang go
    python tests/tools/class_start_diff.py --lang go --max-examples 20
    python tests/tools/class_start_diff.py --lang go --json
"""

import argparse
import json
import re
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tests" / "tools"))

import tree_sitter_accuracy_audit as tsaa  # noqa: E402
import tree_sitter_language_pack  # noqa: E402

from gitgalaxy.core.detector import (  # noqa: E402
    _CLASS_START_NAMED_EXTRACTION_LANGS,
    _resolve_class_start_match,
)
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS  # noqa: E402


def _first_line_context(text: str, name: str) -> str:
    """First line containing `name` as a whole word, formatted `<lineno>: <line>`.

    Best-effort only -- for a common short name this may land on a usage
    site rather than the declaration; read a few lines of surrounding
    context in the actual file before concluding anything from this alone.
    """
    pattern = re.compile(r"\b" + re.escape(name) + r"\b")
    for i, line in enumerate(text.splitlines(), start=1):
        if pattern.search(line):
            return f"{i}: {line.strip()[:160]}"
    return "(name not found verbatim in file -- likely synthesized/aliased)"


def _real_classes_in(tree: Any, class_node_types: set[str], lang: str) -> set[str]:
    """Walks a tree-sitter tree, collecting ground-truth class-shaped node names."""
    found: set[str] = set()
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        if node.type in class_node_types:
            if lang == "c" and node.child_by_field_name("body") is None:
                pass
            else:
                name = tsaa._get_node_name(node)
                if name:
                    found.add(name)
        stack.extend(node.children)
    return found


def _gg_positions_in(text: str, class_start_pattern: re.Pattern, groups: int, lang: str) -> dict[str, list[int]]:
    """Applies class_start + the shared name-resolution algorithm, returns name -> match start offsets."""
    positions: dict[str, list[int]] = {}
    for match in class_start_pattern.finditer(text):
        if lang == "c":
            lookahead = text[match.end() : match.end() + 200]
            anchor_match = re.search(r"^[^\{;,)=]{0,200}?([\{;,)=])", lookahead)
            if not anchor_match or anchor_match.group(1) != "{":
                continue
        _, name, _ = _resolve_class_start_match(match, groups)
        positions.setdefault(name, []).append(match.start(0))
    return positions


def _context_for(name: str, gg_positions: dict[str, list[int]], text: str) -> str:
    lines = text.splitlines()
    if name == "Anonymous_Class":
        n = len(gg_positions["Anonymous_Class"])
        line_no = text.count("\n", 0, gg_positions["Anonymous_Class"][0]) + 1
        first_line = lines[line_no - 1].strip()[:140] if line_no <= len(lines) else ""
        return (
            f"{n} unnamed match(es) -- class_start has no/optional capture group here. First at {line_no}: {first_line}"
        )
    if name in gg_positions:
        line_no = text.count("\n", 0, gg_positions[name][0]) + 1
        line = lines[line_no - 1].strip()[:160] if line_no <= len(lines) else ""
        return f"{line_no}: {line}"
    return _first_line_context(text, name)


def diff_language(lang: str) -> dict[str, Any]:
    """Runs the diff for one language, returns a structured report."""
    if lang not in tsaa.NODE_MAPS:
        sys.exit(f"class_start_diff: {lang!r} has no NODE_MAPS entry in tree_sitter_accuracy_audit.py.")
    if lang not in LANGUAGE_DEFINITIONS:
        sys.exit(f"class_start_diff: {lang!r} not found in LANGUAGE_DEFINITIONS.")

    class_start_pattern = LANGUAGE_DEFINITIONS[lang].get("rules", {}).get("class_start")
    if class_start_pattern is None:
        sys.exit(f"class_start_diff: {lang!r}'s class_start rule is None -- nothing to preview.")

    lang_config = tsaa.NODE_MAPS[lang]
    ts_lang = lang_config.get("ts_lang", lang)
    class_node_types = lang_config["class_node_types"]

    parser = tree_sitter_language_pack.get_parser(ts_lang)
    corpus_dir = tsaa.ensure_corpus(lang)
    class_start_groups = class_start_pattern.groups

    with tempfile.TemporaryDirectory() as tmp:
        db_path = tsaa.run_engine_scan(corpus_dir, Path(tmp))
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            files = conn.execute("SELECT id, file_path FROM file_data WHERE language = ?", (lang,)).fetchall()
        finally:
            conn.close()

    per_file: list[dict[str, Any]] = []
    total_real = total_found = total_extra = total_missing = 0

    for row in files:
        path = corpus_dir / row["file_path"]
        if not path.exists():
            continue
        try:
            code_bytes = path.read_bytes()
            text = code_bytes.decode("utf-8", errors="ignore")
            tree = parser.parse(code_bytes)
        except Exception:  # noqa: S112 -- triage tool, skip unparsable files rather than aborting the run
            continue

        real_classes = _real_classes_in(tree, class_node_types, lang)

        # Mirrors the real pipeline exactly, including its sharp edge:
        # `class_data` is populated per-match, but the accuracy harness reads
        # it back as a per-file SET of names -- so every match whose
        # class_start captured no name at all collapses into a single
        # "Anonymous_Class" entry per file (never a real ground-truth name,
        # so always a guaranteed extra). Do NOT filter these out: that
        # collapse is exactly the C/Swift-shaped failure mode #1264 found (a
        # capture-group-less class_start floods class_data with one phantom
        # entry per file), and hiding it here would make a language that
        # would actually flood production look clean in this tool.
        gg_positions = _gg_positions_in(text, class_start_pattern, class_start_groups, lang)
        gg_classes = set(gg_positions)

        extra = sorted(gg_classes - real_classes)
        missing = sorted(real_classes - gg_classes)
        found = gg_classes & real_classes

        total_real += len(real_classes)
        total_found += len(found)
        total_extra += len(extra)
        total_missing += len(missing)

        if extra or missing:
            per_file.append(
                {
                    "file": row["file_path"],
                    "extra": [{"name": n, "context": _context_for(n, gg_positions, text)} for n in extra],
                    "missing": [{"name": n, "context": _context_for(n, gg_positions, text)} for n in missing],
                }
            )

    return {
        "lang": lang,
        "currently_allowlisted": lang in _CLASS_START_NAMED_EXTRACTION_LANGS,
        "files_scanned": len(files),
        "real_classes": total_real,
        "found_classes": total_found,
        "extra_classes": total_extra,
        "missing_classes": total_missing,
        "per_file": per_file,
    }


def print_report(report: dict[str, Any], max_examples: int) -> None:
    lang = report["lang"]
    status = "ON allowlist" if report["currently_allowlisted"] else "OFF allowlist (legacy fallback active today)"
    print(f"=== {lang} -- {status} ===")
    print(f"files_scanned={report['files_scanned']}  real_classes={report['real_classes']}")
    print(f"  IF flipped to its own class_start: found={report['found_classes']}  extra={report['extra_classes']}")
    print()

    for shown, entry in enumerate(report["per_file"]):
        if shown >= max_examples:
            remaining = len(report["per_file"]) - shown
            print(f"... {remaining} more file(s) with diffs, use --max-examples to see more or --json for all")
            break
        print(entry["file"])
        for item in entry["extra"]:
            print(f"  extra   {item['name']!r:30} {item['context']}")
        for item in entry["missing"]:
            print(f"  missing {item['name']!r:30} {item['context']}")

    if not report["per_file"]:
        print("(no extra/missing names -- every match's name matched ground truth exactly)")


def main() -> int:
    parser = argparse.ArgumentParser(description="class_start named-entity diff (offline triage for #1295)")
    parser.add_argument("--lang", required=True, help="Language to preview (e.g. go, css, swift).")
    parser.add_argument("--max-examples", type=int, default=10, help="Max files with diffs to print (human mode).")
    parser.add_argument("--json", action="store_true", help="Machine-readable output (all files, no truncation).")
    args = parser.parse_args()

    report = diff_language(args.lang)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report, args.max_examples)
    return 0


if __name__ == "__main__":
    sys.exit(main())
