"""
The graph comparison ledger (#3641, docs/self_scan/graph_comparison_README.md).

call_graph_accuracy.py and import_graph_accuracy.py both reconcile, not grade: each
disagreement with tree-sitter's side goes into a SHAPE -- language / symbol type (`call`
or `import`) / cause label / which reader claims it -- and the shapes are merged into
docs/self_scan/graph_comparison_ledger.json through tri_comparison_ledger.py, the same
module, schema and lifecycle the structural tri-comparison uses.

A tool hands this module its per-language results with:
  - `top_causes`: [{"cause": "fp:<label>" | "fn:<label>", "count": n, "examples": [
        {"file_path", "name", "line", "text"}, ...]}, ...]
  - the four counts the two ratios are made of, named by the tool:
        precision = p_ok / (p_ok + p_bad)        recall = r_ok / (r_ok + r_bad)
    (calls: tp, fp, tp, fn; imports: correct edges, false edges, found imports, missed).

A validated shape moves the VALIDATED numbers with the ledger's credit geometry:
    agree[gitgalaxy]   credit gitgalaxy   -> GitGalaxy was right   (p_bad -> p_ok)
                       no credit          -> GitGalaxy was wrong   (unchanged)
    agree[tree_sitter] credit tree_sitter -> GitGalaxy missed it   (unchanged)
                       no credit          -> tree-sitter was wrong (leaves r_bad)
With two readers there is no consensus, so an unvalidated shape counts exactly as it
does raw: the validated numbers move only on a recorded verdict.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO_ROOT = TOOLS.parents[1]
LEDGER = REPO_ROOT / "docs" / "self_scan" / "graph_comparison_ledger.json"
# Examples a ledger entry keeps per shape: enough to read a verdict from, small enough to commit.
# The full list is always one `--buckets N` run away.
LEDGER_EXAMPLES = 5

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def side(cause: str) -> tuple[str, str]:
    """(claiming reader, the other reader) for a cause label."""
    return ("gitgalaxy", "tree_sitter") if cause.startswith("fp:") else ("tree_sitter", "gitgalaxy")


def shape_groups(results: dict[str, dict[str, Any]], symbol_type: str) -> dict[str, list[Any]]:
    """Per language, one tri_comparison_reconcile.DiscrepancyGroup per cause shape."""
    from tri_comparison_reconcile import DiscrepancyExample, DiscrepancyGroup

    out: dict[str, list[Any]] = {}
    for lang, r in results.items():
        groups = []
        for c in r.get("top_causes", []):
            claim, other = side(c["cause"])
            groups.append(
                DiscrepancyGroup(
                    language=lang,
                    symbol_type=symbol_type,
                    metric=c["cause"].split(":", 1)[1],
                    agreeing_tools=frozenset({claim}),
                    dissenting_tools=frozenset({other}),
                    total_occurrences=c["count"],
                    examples=[
                        DiscrepancyExample(e["file_path"], e["name"], {claim: e.get("line"), other: None})
                        for e in c["examples"]
                    ],
                )
            )
        out[lang] = groups
    return out


def validated(
    results: dict[str, dict[str, Any]],
    symbol_type: str,
    counts: tuple[str, str, str, str],
    ledger_path: Path = LEDGER,
) -> dict[str, dict[str, Any]]:
    """Per language: precision/recall after the ledger's verdicts, and what is still open.
    `counts` names the result keys (p_ok, p_bad, r_ok, r_bad)."""
    import tri_comparison_ledger as tl

    entries = tl.load_ledger(ledger_path).get("entries", {})
    out: dict[str, dict[str, Any]] = {}
    for lang, groups in shape_groups(results, symbol_type).items():
        r = results[lang]
        p_ok, p_bad, r_ok, r_bad = (int(r[k]) for k in counts)
        open_n = open_shapes = 0
        for g in groups:
            entry = entries.get(g.shape_key)
            if not entry or entry.get("status") != "validated":
                open_n += g.total_occurrences
                open_shapes += 1
                continue
            credit = set(entry.get("credit_tools") or [])
            if "gitgalaxy" in g.agreeing_tools and "gitgalaxy" in credit:
                p_ok, p_bad = p_ok + g.total_occurrences, p_bad - g.total_occurrences
            elif "tree_sitter" in g.agreeing_tools and "tree_sitter" not in credit:
                r_bad -= g.total_occurrences
        out[lang] = {
            "precision_pct": round(100.0 * p_ok / (p_ok + p_bad), 1) if p_ok + p_bad else None,
            "recall_pct": round(100.0 * r_ok / (r_ok + r_bad), 1) if r_ok + r_bad else None,
            "open_occurrences": open_n,
            "open_shapes": open_shapes,
        }
    return out


def merge(results: dict[str, dict[str, Any]], symbol_type: str, ledger_path: Path = LEDGER) -> None:
    """Merge this run's shapes into the ledger. Only this symbol type's entries go stale."""
    import tri_comparison_ledger as tl

    ledger = tl.load_ledger(ledger_path)
    other = {k: e for k, e in ledger.get("entries", {}).items() if e.get("symbol_type") != symbol_type}
    for lang, groups in shape_groups(results, symbol_type).items():
        tl.merge_and_save(lang, groups, ledger_path)
    # merge_and_save marks every entry of a language that this run did not see as stale -- the
    # other symbol type's entries of that language were not measured here, so restore them.
    ledger = tl.load_ledger(ledger_path)
    ledger["entries"].update(other)
    tl.save_ledger(ledger, ledger_path)


def render_causes(results: dict[str, dict[str, Any]], counts: tuple[str, str, str, str], limit: int = 12) -> str:
    """Per language, each disagreement cause with its share of that side (FP or FN)."""
    out = []
    for lang, r in results.items():
        if "top_causes" not in r:
            continue
        fp, fn = int(r[counts[1]]), int(r[counts[3]])
        out.append(f"\n### {lang}  (FP {fp}, FN {fn})")
        for c in r["top_causes"][:limit]:
            total = fp if c["cause"].startswith("fp:") else fn
            share = f"{100 * c['count'] / total:.0f}%" if total else "-"
            out.append(f"- {c['cause']}: {c['count']} ({share})")
            out.extend(f"    {e['name']}  {e['text']}" for e in c["examples"])
    return "\n".join(out)


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
