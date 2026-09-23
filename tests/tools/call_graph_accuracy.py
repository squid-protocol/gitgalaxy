"""
Call-graph accuracy, Level 1: callee-name extraction (#3332, Epic #3265 step 5).

Precision and recall of the engine's per-function `calls_out_to` against
tree-sitter call nodes, on language-crucible, per language.

WHAT IS COMPARED
  For every function both sides find (same file, same name, start lines within
  a few lines of each other), the SET of callee names:
    engine: function_data.calls_out_to, from one in-process scan of the crucible
            with THIS checkout's engine;
    tree-sitter: every call node inside the function, attributed to its
            INNERMOST enclosing function, named by its callee's rightmost
            identifier (`a.b.save()` -> `save`, `new Foo()` -> `Foo`,
            `Store::make()` -> `make`, `println!()` -> `println`).
  Both sides follow the #3327 contract: names are deduplicated, and the
  function's own name is dropped (recursion). Built-ins count as calls on both
  sides, so the engine's built-in filter (#3361) shows up as missed recall.
  Keyword captures (#3359) and nested-declaration captures (#3360) show up as
  lost precision. Function detection is NOT scored here: a function only one
  side finds is skipped. tree_sitter_accuracy_audit.py scores that.

  Tree-sitter works at the same unresolved-name level as calls_out, so this is
  a like-for-like comparison. It is NOT a resolution benchmark; that is Level 2
  (call_graph_resolution.py). Disagreements are leads, to be checked against
  source (CLAUDE.md's comparative-correctness rule), not verdicts.

    python tests/tools/call_graph_accuracy.py                # report
    python tests/tools/call_graph_accuracy.py --samples 8    # + top FP/FN names
    python tests/tools/call_graph_accuracy.py --ci           # gate vs the baseline
    python tests/tools/call_graph_accuracy.py --regenerate   # rewrite the baseline
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS = Path(__file__).resolve().parent
CRUCIBLE = Path(os.environ.get("LANGUAGE_CRUCIBLE_PATH", REPO_ROOT.parent / "language-crucible"))
BASELINE = REPO_ROOT / "tests" / "call_graph_accuracy_baseline.json"

# The languages #3329 scoped for qualifier capture, plus C and Rust: the
# C-style invocation family where tree-sitter's call node is unambiguous.
LANGS = ("python", "javascript", "typescript", "java", "go", "c", "cpp", "csharp", "php", "ruby", "rust")

CALL_NODE_TYPES = frozenset(
    {
        "call",  # python, ruby
        "call_expression",  # js/ts, c/cpp, go, rust
        "new_expression",  # js/ts constructor
        "method_invocation",  # java
        "object_creation_expression",  # java, c#, php
        "invocation_expression",  # c#
        "function_call_expression",  # php
        "member_call_expression",  # php
        "nullsafe_member_call_expression",  # php
        "scoped_call_expression",  # php
        "macro_invocation",  # rust
    }
)
_CALLEE_FIELDS = ("function", "method", "name", "macro", "constructor", "type")
_MEMBER_FIELDS = ("property", "field", "name", "attribute", "method")
_LEAF_SUFFIXES = ("identifier", "constant")
_QUALIFIED_TYPES = frozenset({"scoped_identifier", "qualified_identifier", "scoped_type_identifier"})
_LINE_SLACK = 3  # decorators/annotations/doc comments can move a start line

# Gate tolerance, in percentage points, before --ci calls a drop a regression.
TOLERANCE_PP = 0.5


# ----------------------------------------------------------------------------- tree-sitter side


def _leaf_name(node: Any, depth: int = 0) -> str | None:
    """The rightmost identifier a callee expression names."""
    if node is None or depth > 8:
        return None
    if node.type in _QUALIFIED_TYPES:  # `ControlFlow::Continue`, `OS::get_singleton`
        child = node.child_by_field_name("name")
        return _leaf_name(child, depth + 1) if child is not None else None
    if node.type.endswith(_LEAF_SUFFIXES) or node.type == "name":
        return node.text.decode("utf-8", "replace")
    for field in _MEMBER_FIELDS:
        child = node.child_by_field_name(field)
        if child is not None:
            return _leaf_name(child, depth + 1)
    for child in reversed(node.named_children):
        got = _leaf_name(child, depth + 1)
        if got:
            return got
    return None


def _callee(node: Any) -> str | None:
    for field in _CALLEE_FIELDS:
        child = node.child_by_field_name(field)
        if child is not None:
            return _leaf_name(child)
    if node.type == "object_creation_expression":  # php: `new Foo(...)` has no field
        for child in node.named_children:
            if child.type in ("name", "qualified_name"):
                return _leaf_name(child)
    return None


def ts_functions(source: bytes, lang: str, audit: Any) -> list[tuple[str, int, set[str]]]:
    """(name, start_line, callee names) for every function tree-sitter finds."""
    import tree_sitter_language_pack

    spec = audit.NODE_MAPS[lang]
    tree = tree_sitter_language_pack.get_parser(spec["ts_lang"]).parse(source)
    func_types = spec["func_node_types"]
    out: list[tuple[str, int, set[str]]] = []
    stack: list[tuple[Any, list[set[str]]]] = [(tree.root_node, [])]
    # iterative walk; `owners` is the chain of enclosing function call-sets
    while stack:
        node, owners = stack.pop()
        if node.type in func_types:
            name = audit._get_node_name(node)
            calls: set[str] = set()
            if name:
                out.append((name, node.start_point[0] + 1, calls))
            owners = [*owners, calls]
        elif node.type in CALL_NODE_TYPES and owners:
            name = _callee(node)
            if name:
                owners[-1].add(name)
        stack.extend((child, owners) for child in reversed(node.children))
    return out


# ----------------------------------------------------------------------------- engine side


def engine_functions(crucible: Path) -> dict[tuple[str, str], list[tuple[str, int, list[str]]]]:
    """(language, path relative to the scan root) -> [(name, start_line, calls_out_to)]."""
    sys.path.insert(0, str(REPO_ROOT))
    import gitgalaxy
    from gitgalaxy.galaxyscope import main as galaxyscope_main

    if Path(gitgalaxy.__file__).resolve().parents[1] != REPO_ROOT:
        raise SystemExit(f"engine import resolved to {gitgalaxy.__file__}, not {REPO_ROOT} -- set PYTHONPATH")
    out: dict[tuple[str, str], list[tuple[str, int, list[str]]]] = collections.defaultdict(list)
    with tempfile.TemporaryDirectory() as tmp:
        argv = sys.argv
        sys.argv = ["galaxyscope", str(crucible / "data"), "--output", f"{tmp}/c.json", "--db-only"]
        try:
            galaxyscope_main()
        finally:
            sys.argv = argv
        (db,) = Path(tmp).glob("*_master.db")
        conn = sqlite3.connect(db)
        try:
            rows = conn.execute(
                "SELECT fd.language, fd.file_path, fn.func_name, fn.start_line, fn.calls_out_to "
                "FROM function_data fn JOIN file_data fd ON fd.id = fn.file_id"
            ).fetchall()
        finally:
            conn.close()
    for lang, path, name, line, calls in rows:
        lang = str(lang or "").lower()
        if lang in LANGS:
            out[(lang, path)].append((name, int(line or 0), json.loads(calls or "[]")))
    return out


# ----------------------------------------------------------------------------- comparison


def _pair(
    gg: list[tuple[str, int, list[str]]], ts: list[tuple[str, int, set[str]]]
) -> list[tuple[str, set[str], set[str]]]:
    """Match functions by name, then nearest start line within the slack."""
    by_name: dict[str, list[tuple[int, set[str]]]] = collections.defaultdict(list)
    for name, line, calls in ts:
        by_name[name].append((line, calls))
    pairs = []
    for name, line, calls in gg:
        cands = by_name.get(name)
        if not cands:
            continue
        i = min(range(len(cands)), key=lambda k: abs(cands[k][0] - line))
        if abs(cands[i][0] - line) > _LINE_SLACK:
            continue
        _, ts_calls = cands.pop(i)
        pairs.append((name, set(calls) - {name}, set(ts_calls) - {name}))
    return pairs


def measure(crucible: Path, samples: int = 0) -> dict[str, dict[str, Any]]:
    sys.path.insert(0, str(TOOLS))
    import tree_sitter_accuracy_audit as audit

    engine = engine_functions(crucible)
    results: dict[str, dict[str, Any]] = {}
    for lang in LANGS:
        tp = fp = fn = funcs = parse_failures = 0
        fps: collections.Counter[str] = collections.Counter()
        fns: collections.Counter[str] = collections.Counter()
        for (elang, path), gg in sorted(engine.items()):
            if elang != lang:
                continue
            src = crucible / "data" / path
            if not src.is_file():
                continue
            try:
                ts = ts_functions(src.read_bytes(), lang, audit)
            except Exception:  # a parse failure is tree_sitter_accuracy_audit's to report
                parse_failures += 1
                continue
            for _, mine, theirs in _pair(gg, ts):
                funcs += 1
                tp += len(mine & theirs)
                fp += len(mine - theirs)
                fn += len(theirs - mine)
                fps.update(mine - theirs)
                fns.update(theirs - mine)
        if not funcs:
            continue
        results[lang] = {
            "matched_functions": funcs,
            "parse_failures": parse_failures,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision_pct": round(100.0 * tp / (tp + fp), 1) if tp + fp else None,
            "recall_pct": round(100.0 * tp / (tp + fn), 1) if tp + fn else None,
        }
        if samples:
            results[lang]["top_fp"] = fps.most_common(samples)
            results[lang]["top_fn"] = fns.most_common(samples)
    return results


def render(results: dict[str, dict[str, Any]]) -> str:
    lines = ["| language | functions | precision | recall | TP | FP | FN |", "|---|---|---|---|---|---|---|"]
    for lang, r in results.items():
        lines.append(
            f"| {lang} | {r['matched_functions']} | {r['precision_pct']}% | {r['recall_pct']}% | "
            f"{r['tp']} | {r['fp']} | {r['fn']} |"
        )
    return "\n".join(lines)


def regressions(results: dict[str, dict[str, Any]], baseline: dict[str, dict[str, Any]]) -> list[str]:
    out = []
    for lang, base in baseline.items():
        cur = results.get(lang)
        if cur is None:
            out.append(f"{lang}: no longer measured (baseline had {base['matched_functions']} functions)")
            continue
        out.extend(
            f"{lang}: {metric} {base[metric]} -> {cur.get(metric)}"
            for metric in ("precision_pct", "recall_pct")
            if base.get(metric) is not None and (cur.get(metric) or 0.0) < base[metric] - TOLERANCE_PP
        )
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--samples", type=int, default=0, help="print the N most frequent FP/FN names per language")
    ap.add_argument("--ci", action="store_true", help="fail on a drop beyond the baseline tolerance")
    ap.add_argument("--regenerate", action="store_true", help="rewrite the committed baseline")
    ap.add_argument("--json", metavar="PATH")
    a = ap.parse_args(argv)
    if not (CRUCIBLE / "data").is_dir():
        print(f"call_graph_accuracy: no crucible at {CRUCIBLE} (set LANGUAGE_CRUCIBLE_PATH)")
        return 2
    results = measure(CRUCIBLE, a.samples)
    print(render(results))
    if a.samples:
        for lang, r in results.items():
            print(f"\n{lang}  FP: {r['top_fp']}\n{' ' * len(lang)}  FN: {r['top_fn']}")
    if a.json:
        Path(a.json).write_text(json.dumps(results, indent=2) + "\n")
    stripped = {k: {m: v for m, v in r.items() if not m.startswith("top_")} for k, r in results.items()}
    if a.regenerate:
        BASELINE.write_text(json.dumps(stripped, indent=2, sort_keys=True) + "\n")
        print(f"call_graph_accuracy: baseline rewritten -> {BASELINE.relative_to(REPO_ROOT)}")
        return 0
    if a.ci:
        if not BASELINE.exists():
            print("call_graph_accuracy: no baseline; run --regenerate")
            return 1
        bad = regressions(stripped, json.loads(BASELINE.read_text()))
        if bad:
            print("call_graph_accuracy: REGRESSION\n  " + "\n  ".join(bad))
            return 1
        print("call_graph_accuracy: OK -- no language dropped beyond the baseline tolerance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
