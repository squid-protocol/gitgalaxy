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
  sides (#3361 removed the engine's built-in filter).
  Keyword captures (#3359) and nested-declaration captures (#3360) show up as
  lost precision. Function detection is NOT scored here: a function only one
  side finds is skipped. tree_sitter_accuracy_audit.py scores that.

  Tree-sitter works at the same unresolved-name level as calls_out, so this is
  a like-for-like comparison. It is NOT a resolution benchmark; that is Level 2
  (call_graph_resolution.py). Disagreements are leads, to be checked against
  source (CLAUDE.md's comparative-correctness rule), not verdicts.

    python tests/tools/call_graph_accuracy.py                # report
    python tests/tools/call_graph_accuracy.py --samples 8    # + top FP/FN names
    python tests/tools/call_graph_accuracy.py --buckets 3    # + FP/FN by CAUSE, 3 examples each
    python tests/tools/call_graph_accuracy.py --ledger       # merge the shapes into the ledger

RECONCILED, NOT GRADED (#3641)
  Like the structural tri-comparison (docs/self_scan/tri_comparison_README.md), a
  disagreement is a discrepancy until someone reads the source. `--buckets` groups each
  one into a SHAPE (language / `call` / cause label / which reader claims it), and
  `--ledger` merges the shapes into docs/self_scan/graph_comparison_ledger.json through
  tri_comparison_ledger.py -- the same module, schema and lifecycle, a separate file. A
  validated entry moves the VALIDATED numbers with the ledger's own credit geometry:
    agree[gitgalaxy]   credit gitgalaxy   -> GitGalaxy was right  (FP becomes TP)
                       no credit          -> GitGalaxy was wrong  (stays FP)
    agree[tree_sitter] credit tree_sitter -> GitGalaxy missed it  (stays FN)
                       no credit          -> tree-sitter was wrong (leaves FN)
  With two readers there is no consensus, so an unvalidated shape counts exactly as it
  does raw: the validated numbers only ever move on a recorded verdict. The --ci gate
  stays on the raw numbers.
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
LEDGER = REPO_ROOT / "docs" / "self_scan" / "graph_comparison_ledger.json"
READERS = ("gitgalaxy", "tree_sitter")
# Examples a ledger entry keeps per shape: enough to read a verdict from, small enough to commit.
# The full list is always one `--buckets N` run away.
LEDGER_EXAMPLES = 5

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
        "type_conversion_expression",  # go `[]byte(s)` -- a conversion is a call (C3)
    }
)
_CALLEE_FIELDS = ("function", "method", "name", "macro", "constructor", "type")
_MEMBER_FIELDS = ("property", "field", "name", "attribute", "method")
_LEAF_SUFFIXES = ("identifier", "constant")
_QUALIFIED_TYPES = frozenset({"scoped_identifier", "qualified_identifier", "scoped_type_identifier"})
_LINE_SLACK = 3  # decorators/annotations/doc comments can move a start line

# #3359: names tree-sitter parses as a call node but the #3327 contract says are
# keywords, never calls (C2) -- language constructs and operator keywords the
# engine's `_calls_out_ignore` now drops. Removed from the tree-sitter side so
# both sides score the same contract instead of the engine losing "recall" for
# following it. Built-ins are NOT here: they are calls (decision 1, #3361).
CONTRACT_NON_CALLS: dict[str, frozenset[str]] = {
    "php": frozenset({"isset", "empty", "unset", "die", "exit", "array", "list"}),
    "csharp": frozenset({"nameof"}),
}

# Gate tolerance, in percentage points, before --ci calls a drop a regression.
TOLERANCE_PP = 0.5


# ----------------------------------------------------------------------------- tree-sitter side


def _leaf_name(node: Any, depth: int = 0) -> str | None:
    """The rightmost identifier a callee expression names."""
    if node is None or depth > 8:
        return None
    if node.type == "generic_function":  # rust `collect::<Vec<_>>()`: the function, not the type
        return _leaf_name(node.child_by_field_name("function"), depth + 1)
    if node.type in ("generic_name", "generic_type"):  # c# `OfType<T>()`, java `new HashMap<K, V>()`
        return _leaf_name(node.named_children[0], depth + 1) if node.named_children else None
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


_KEEP_TREE: list[Any] = [None]


def ts_functions(source: bytes, lang: str, audit: Any) -> list[tuple[str, int, set[str], Any]]:
    """(name, start_line, callee names, node) for every function tree-sitter finds."""
    import tree_sitter_language_pack

    spec = audit.NODE_MAPS[lang]
    tree = tree_sitter_language_pack.get_parser(spec["ts_lang"]).parse(source)
    _KEEP_TREE[0] = tree  # the returned nodes are only valid while their tree lives
    func_types = spec["func_node_types"]
    non_calls = CONTRACT_NON_CALLS.get(lang, frozenset())
    out: list[tuple[str, int, set[str], Any]] = []
    stack: list[tuple[Any, list[set[str]]]] = [(tree.root_node, [])]
    # iterative walk; `owners` is the chain of enclosing function call-sets
    while stack:
        node, owners = stack.pop()
        if node.type in func_types:
            name = audit._get_node_name(node)
            # C8 (#3641): an anonymous function is no unit of its own -- its calls stay with the
            # enclosing named unit. Only a named function starts a new owner.
            if name:
                calls: set[str] = set()
                out.append((name, node.start_point[0] + 1, calls, node))
                owners = [*owners, calls]
        elif node.type in CALL_NODE_TYPES and owners:
            name = _callee(node)
            if name and name not in non_calls:
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
    gg: list[tuple[str, int, list[str]]], ts: list[tuple[str, int, set[str], Any]]
) -> list[tuple[str, set[str], set[str], Any]]:
    """Match functions by name, then nearest start line within the slack."""
    by_name: dict[str, list[tuple[int, set[str], Any]]] = collections.defaultdict(list)
    for name, line, calls, node in ts:
        by_name[name].append((line, calls, node))
    pairs = []
    for name, line, calls in gg:
        cands = by_name.get(name)
        if not cands:
            continue
        i = min(range(len(cands)), key=lambda k: abs(cands[k][0] - line))
        if abs(cands[i][0] - line) > _LINE_SLACK:
            continue
        _, ts_calls, node = cands.pop(i)
        pairs.append((name, set(calls) - {name}, set(ts_calls) - {name}, node))
    return pairs


# ----------------------------------------------------------------------------- disagreement causes


def _walk(node: Any):
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        stack.extend(reversed(n.children))


def _owner(node: Any, func_types: frozenset[str], top: Any, audit: Any) -> Any:
    """The innermost NAMED function node enclosing `node`, stopping at `top` (C8: an
    anonymous function is part of the unit it is written in)."""
    p = node.parent
    while p is not None and p.id != top.id:
        if p.type in func_types and audit._get_node_name(p):
            return p
        p = p.parent
    return top


def _cause(kind: str, callee: str, fn: Any, lang: str, audit: Any, engine_elsewhere: bool) -> tuple[str, Any]:
    """Why one side has `callee` in `fn` and the other does not, as a shape label.

    `kind` is "fp" (engine only) or "fn" (tree-sitter only). Returns the label and
    the node that exemplifies it (None when the name has no node in the function).
    The labels are leads for a person to verify, not verdicts (CLAUDE.md's
    comparative-correctness rule): a `ts-...` label says the ground truth side
    may be the one that is wrong.
    """
    func_types = frozenset(audit.NODE_MAPS[lang]["func_node_types"])
    calls = [n for n in _walk(fn) if n.type in CALL_NODE_TYPES and _callee(n) == callee]
    if kind == "fp":
        if callee in CONTRACT_NON_CALLS.get(lang, ()):
            return "fp:contract-non-call", None
        for n in calls:  # tree-sitter sees the call, but gives it to an inner function
            inner = _owner(n, func_types, fn, audit)
            if inner.id != fn.id:
                return f"fp:inner-named-{inner.type}", n
        ids = [n for n in _walk(fn) if n.text == callee.encode() and not n.children]
        if ids:
            parent = ids[0].parent
            grand = parent.parent if parent is not None else None
            shape = f"{parent.type if parent else '?'}<{grand.type if grand else '?'}"
            return f"fp:not-a-call-in-ts:{shape}", ids[0]
        return "fp:outside-ts-function", None
    if engine_elsewhere:
        return "fn:engine-attributes-to-another-function", calls[0] if calls else None
    if not calls:
        return "fn:?", None
    n = calls[0]
    field = next((n.child_by_field_name(f) for f in _CALLEE_FIELDS if n.child_by_field_name(f) is not None), None)
    shape = f"{n.type}/{field.type if field is not None else '-'}"
    text = (field.text if field is not None else n.text).decode("utf-8", "replace")
    flags = "".join(
        f for f, hit in (("+generic", "<" in text), ("+bang", callee.endswith("!") or "!" in text[-2:])) if hit
    )
    return f"fn:{shape}{flags}", n


def _example(src: bytes, path: str, node: Any) -> str:
    if node is None:
        return path
    line = src.splitlines()[node.start_point[0]].decode("utf-8", "replace").strip()
    return f"{path}:{node.start_point[0] + 1}: {line[:110]}"


def measure(crucible: Path, samples: int = 0, buckets: int = 0) -> dict[str, dict[str, Any]]:
    sys.path.insert(0, str(TOOLS))
    import tree_sitter_accuracy_audit as audit

    engine = engine_functions(crucible)
    results: dict[str, dict[str, Any]] = {}
    for lang in LANGS:
        tp = fp = fn = funcs = parse_failures = 0
        fps: collections.Counter[str] = collections.Counter()
        fns: collections.Counter[str] = collections.Counter()
        causes: collections.Counter[str] = collections.Counter()
        examples: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
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
            source = src.read_bytes() if buckets else b""
            engine_names = {c for _, _, calls in gg for c in calls}
            for fname, mine, theirs, node in _pair(gg, ts):
                funcs += 1
                tp += len(mine & theirs)
                fp += len(mine - theirs)
                fn += len(theirs - mine)
                fps.update(mine - theirs)
                fns.update(theirs - mine)
                if not buckets:
                    continue
                for kind, names in (("fp", mine - theirs), ("fn", theirs - mine)):
                    for callee in names:
                        label, ex = _cause(kind, callee, node, lang, audit, callee in engine_names)
                        causes[label] += 1
                        if len(examples[label]) < buckets:
                            examples[label].append(
                                {
                                    "file_path": path,
                                    "name": f"{fname} -> {callee}",
                                    "line": ex.start_point[0] + 1 if ex is not None else None,
                                    "text": _example(source, path, ex),
                                }
                            )
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
        if buckets:
            results[lang]["top_causes"] = [
                {"cause": c, "count": k, "examples": examples[c]} for c, k in causes.most_common()
            ]
    return results


def render_causes(results: dict[str, dict[str, Any]], limit: int = 12) -> str:
    """Per language, each disagreement cause with its share of that side (FP or FN)."""
    out = []
    for lang, r in results.items():
        if "top_causes" not in r:
            continue
        out.append(f"\n### {lang}  (FP {r['fp']}, FN {r['fn']})")
        for c in r["top_causes"][:limit]:
            side = r["fp"] if c["cause"].startswith("fp:") else r["fn"]
            share = f"{100 * c['count'] / side:.0f}%" if side else "-"
            out.append(f"- {c['cause']}: {c['count']} ({share})")
            out.extend(f"    {e['name']}  {e['text']}" for e in c["examples"])
    return "\n".join(out)


# ----------------------------------------------------------------------------- ledger


def _side(cause: str) -> tuple[str, str]:
    """(claiming reader, the other reader) for a cause label."""
    return ("gitgalaxy", "tree_sitter") if cause.startswith("fp:") else ("tree_sitter", "gitgalaxy")


def shape_groups(results: dict[str, dict[str, Any]]) -> dict[str, list[Any]]:
    """Per language, one tri_comparison_reconcile.DiscrepancyGroup per cause shape."""
    sys.path.insert(0, str(TOOLS))
    from tri_comparison_reconcile import DiscrepancyExample, DiscrepancyGroup

    out: dict[str, list[Any]] = {}
    for lang, r in results.items():
        groups = []
        for c in r.get("top_causes", []):
            claim, other = _side(c["cause"])
            groups.append(
                DiscrepancyGroup(
                    language=lang,
                    symbol_type="call",
                    metric=c["cause"].split(":", 1)[1],
                    agreeing_tools=frozenset({claim}),
                    dissenting_tools=frozenset({other}),
                    total_occurrences=c["count"],
                    examples=[
                        DiscrepancyExample(e["file_path"], e["name"], {claim: e["line"], other: None})
                        for e in c["examples"]
                    ],
                )
            )
        out[lang] = groups
    return out


def validated(results: dict[str, dict[str, Any]], ledger_path: Path = LEDGER) -> dict[str, dict[str, Any]]:
    """Per language: precision/recall after the ledger's verdicts, and what is still open."""
    sys.path.insert(0, str(TOOLS))
    import tri_comparison_ledger as tl

    entries = tl.load_ledger(ledger_path).get("entries", {})
    out: dict[str, dict[str, Any]] = {}
    for lang, groups in shape_groups(results).items():
        r = results[lang]
        tp, fp, fn, open_n, open_shapes = r["tp"], r["fp"], r["fn"], 0, 0
        for g in groups:
            entry = entries.get(g.shape_key)
            if not entry or entry.get("status") != "validated":
                open_n += g.total_occurrences
                open_shapes += 1
                continue
            credit = set(entry.get("credit_tools") or [])
            if "gitgalaxy" in g.agreeing_tools and "gitgalaxy" in credit:
                tp, fp = tp + g.total_occurrences, fp - g.total_occurrences
            elif "tree_sitter" in g.agreeing_tools and "tree_sitter" not in credit:
                fn -= g.total_occurrences
        out[lang] = {
            "precision_pct": round(100.0 * tp / (tp + fp), 1) if tp + fp else None,
            "recall_pct": round(100.0 * tp / (tp + fn), 1) if tp + fn else None,
            "open_occurrences": open_n,
            "open_shapes": open_shapes,
        }
    return out


def merge_ledger(results: dict[str, dict[str, Any]], ledger_path: Path = LEDGER) -> None:
    sys.path.insert(0, str(TOOLS))
    import tri_comparison_ledger as tl

    for lang, groups in shape_groups(results).items():
        tl.merge_and_save(lang, groups, ledger_path)


def render(results: dict[str, dict[str, Any]]) -> str:
    lines = ["| language | functions | precision | recall | TP | FP | FN |", "|---|---|---|---|---|---|---|"]
    for lang, r in results.items():
        lines.append(
            f"| {lang} | {r['matched_functions']} | {r['precision_pct']}% | {r['recall_pct']}% | "
            f"{r['tp']} | {r['fp']} | {r['fn']} |"
        )
    return "\n".join(lines)


def render_validated(results: dict[str, dict[str, Any]], v: dict[str, dict[str, Any]]) -> str:
    lines = [
        "| language | raw precision | raw recall | validated precision | validated recall | open shapes | open |",
        "|---|---|---|---|---|---|---|",
    ]
    for lang, r in results.items():
        x = v.get(lang, {})
        star = "*" if x.get("open_shapes") else ""
        lines.append(
            f"| {lang} | {r['precision_pct']}% | {r['recall_pct']}% | {x.get('precision_pct')}%{star} | "
            f"{x.get('recall_pct')}%{star} | {x.get('open_shapes', 0)} | {x.get('open_occurrences', 0)} |"
        )
    lines.append("\n`*` = a shape in this language has no verdict yet; the number is not a claim.")
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
    ap.add_argument("--buckets", type=int, default=0, help="classify every FP/FN by cause, N examples each")
    ap.add_argument("--ledger", action="store_true", help="merge the discrepancy shapes into the ledger")
    ap.add_argument("--ci", action="store_true", help="fail on a drop beyond the baseline tolerance")
    ap.add_argument("--regenerate", action="store_true", help="rewrite the committed baseline")
    ap.add_argument("--json", metavar="PATH")
    a = ap.parse_args(argv)
    if not (CRUCIBLE / "data").is_dir():
        print(f"call_graph_accuracy: no crucible at {CRUCIBLE} (set LANGUAGE_CRUCIBLE_PATH)")
        return 2
    buckets = max(a.buckets, LEDGER_EXAMPLES) if a.ledger else a.buckets
    results = measure(CRUCIBLE, a.samples, buckets)
    print(render(results))
    if buckets:
        print(render_causes(results))
        if a.ledger:
            merge_ledger(results)
            print(f"\ncall_graph_accuracy: shapes merged into {LEDGER.relative_to(REPO_ROOT)}")
        print("\n" + render_validated(results, validated(results)))
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
