#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""
Rule probe: what does one rule match, per language, on the code streams the
engine actually scans?

Every rule-contract session (api #2730, args #2773, state_mutation #2765) and every
single-language rule fix before them (#2654, #2660, #2673, #2674) hand-rolled this
same script: run `LANGUAGE_DEFINITIONS[lang]["rules"][rule]` over the Prism
code stream of every file in a corpus, count the hits, show the matched lines.
This is that script, committed, with the two things the audit table needs on
top: a saved JSON snapshot and a before/after comparison of two snapshots.

USAGE
    # incidence + top matched lines, one language or all of them
    python tests/tools/rule_probe.py state_mutation haskell
    python tests/tools/rule_probe.py state_mutation all --samples 5

    # snapshot before the rule edit, snapshot after, then the audit-table rows
    python tests/tools/rule_probe.py state_mutation all --json /tmp/before.json
    ...edit the rules...
    python tests/tools/rule_probe.py state_mutation all --json /tmp/after.json
    python tests/tools/rule_probe.py state_mutation all --compare /tmp/before.json /tmp/after.json

    # try a candidate regex without editing the registry
    python tests/tools/rule_probe.py state_mutation c --override '(?:^|[;{])[ \\t]*\\w+ *=' --flags M

CORPORA
    Both are scanned by default: the language-crucible real-world corpus
    (LANGUAGE_CRUCIBLE_PATH, default ../language-crucible -- scan a clean
    worktree of the pinned tag, never a checkout with scan residue in it) and the
    keyword-rosetta control corpus (KEYWORD_ROSETTA_PATH, default
    ../keyword-rosetta). --corpus crucible|rosetta picks one.

WHAT IT MEASURES
    Raw rule hits over `Prism.split_streams(...)["code_stream"]` -- comments
    stripped, string literals kept, exactly the text detector.py hands the rule.
    NOT the recorded count: scope filters (`_scope_filters`, e.g. matlab's return
    channel) and the per-function slicer run after the regex, so a language with a
    filter reads higher here than in a manifest. That is the right thing for a
    rule audit (it isolates the regex) and the wrong thing for a corpus bless
    (use tests/tools/rosetta_audit.py for that).

Run it from a worktree with PYTHONPATH pointing at that worktree, so the registry
you probe is the one you are editing (the sibling .venv is an editable install of
whatever the primary checkout has checked out).
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from gitgalaxy.core.prism import Prism  # noqa: E402
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS  # noqa: E402
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS  # noqa: E402


def _sibling(env: str, name: str) -> Path:
    """The corpus checkout: $env, else ../<name> from the checkout, else ../../<name> from a worktree."""
    if os.environ.get(env):
        return Path(os.environ[env])
    for base in (REPO_ROOT.parent, REPO_ROOT.parent.parent):
        if (base / name / "data").is_dir():
            return base / name
    return REPO_ROOT.parent / name


CRUCIBLE = _sibling("LANGUAGE_CRUCIBLE_PATH", "language-crucible") / "data"
ROSETTA = _sibling("KEYWORD_ROSETTA_PATH", "keyword-rosetta") / "data"
# registry key -> corpus directory name, where they differ
CORPUS_DIR = {"objectivec": "objective-c"}
MAX_FILE_BYTES = 2_000_000


def _extensions(lang: str) -> set[str]:
    defn = LANGUAGE_DEFINITIONS[lang]
    exts = defn.get("extensions") or defn.get("file_extensions") or []
    return {e.lower() for e in exts}


def corpus_files(lang: str, corpus: str):
    exts = _extensions(lang)
    d = CORPUS_DIR.get(lang, lang)
    roots = []
    if corpus in ("crucible", "both"):
        roots.append(("crucible", CRUCIBLE / d))
    if corpus in ("rosetta", "both"):
        roots.append(("rosetta", ROSETTA / d))
    for name, root in roots:
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*")):
            if not p.is_file() or ".git" in p.parts or p.stat().st_size > MAX_FILE_BYTES:
                continue
            if exts and p.suffix.lower() not in exts and p.name.lower() not in exts:
                continue
            yield name, root, p


def compile_override(pattern: str, flags: str) -> re.Pattern:
    fl = 0
    for ch in flags.upper():
        fl |= {"I": re.I, "M": re.M, "S": re.S, "X": re.X}[ch]
    return re.compile(pattern, fl)


def probe(rule_name: str, lang: str, corpus: str, samples: int, override: re.Pattern | None, prism: Prism):
    rule = override or LANGUAGE_DEFINITIONS[lang]["rules"].get(rule_name)
    if rule is None or not hasattr(rule, "finditer"):
        return None
    per: dict[str, dict] = {}
    for name, root, path in corpus_files(lang, corpus):
        try:
            src = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        code = prism.split_streams(src, lang)["code_stream"]
        hits = list(rule.finditer(code))
        c = per.setdefault(name, {"files": 0, "hits": 0, "by_file": {}, "samples": collections.Counter()})
        c["files"] += 1
        c["hits"] += len(hits)
        if hits:
            c["by_file"][str(path.relative_to(root))] = len(hits)
        for m in hits:
            ls = code.rfind("\n", 0, m.start()) + 1
            le = code.find("\n", m.end())
            line = code[ls : len(code) if le < 0 else le].strip()
            c["samples"][(m.group(0).strip()[:40], line[:120])] += 1
    for c in per.values():
        c["samples"] = [(tok, line, n) for (tok, line), n in c["samples"].most_common(samples)]
    return per


def print_probe(lang: str, per: dict | None, samples: int) -> None:
    if per is None:
        print(f"{lang:16s} rule is None")
        return
    summary = "  ".join(f"{k}:{v['hits']}/{v['files']}f" for k, v in per.items())
    print(f"{lang:16s} {summary}")
    for k, v in per.items():
        for tok, line, n in v["samples"][:samples]:
            print(f"      [{k}] x{n:<4d} {tok!r:24s} | {line}")


def compare(before: dict, after: dict, langs: list[str]) -> None:
    print("| language | crucible | keyword-rosetta |")
    print("|---|---|---|")
    for lang in langs:
        b, a = before.get(lang), after.get(lang)
        if a is None and b is None:
            print(f"| `{lang}` | rule is `None` | n/a |")
            continue

        def cell(corpus: str, b=b, a=a) -> str:
            hb = (b or {}).get(corpus, {}).get("hits")
            ha = (a or {}).get(corpus, {}).get("hits")
            if hb is None and ha is None:
                return "--"
            return f"{hb} -> {ha}" if hb != ha else f"{ha}"

        print(f"| `{lang}` | {cell('crucible')} | {cell('rosetta')} |")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rule")
    ap.add_argument("lang", help="a registry key, or `all`")
    ap.add_argument("--corpus", choices=("crucible", "rosetta", "both"), default="both")
    ap.add_argument("--samples", type=int, default=6, help="matched lines to show per corpus (most frequent first)")
    ap.add_argument("--override", help="probe this regex instead of the registry's rule")
    ap.add_argument("--flags", default="", help="flags for --override, e.g. IM")
    ap.add_argument("--json", help="write the per-language snapshot here")
    ap.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"), help="print audit-table rows from two snapshots")
    args = ap.parse_args(argv)

    langs = sorted(LANGUAGE_DEFINITIONS) if args.lang == "all" else [args.lang]
    if args.compare:
        before, after = (json.loads(Path(p).read_text(encoding="utf-8")) for p in args.compare)
        compare(before, after, langs)
        return 0

    override = compile_override(args.override, args.flags) if args.override else None
    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    out: dict[str, dict | None] = {}
    for lang in langs:
        per = probe(args.rule, lang, args.corpus, args.samples, override, prism)
        out[lang] = per
        print_probe(lang, per, args.samples)
    if args.json:
        Path(args.json).write_text(json.dumps(out, indent=1), encoding="utf-8")
        print(f"snapshot written: {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
