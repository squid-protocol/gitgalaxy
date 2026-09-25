"""
Call-graph accuracy, Level 2: resolution correctness (#3332, Epic #3265 step 5).

Level 1 (call_graph_accuracy.py) asks whether the engine found the right callee
NAMES. This asks whether the call resolver (core/call_resolver.py, #3328) linked
each name to the right DEFINITION, separately for the confident steps (the ones
function PageRank uses) and the ambiguous ones (which it deliberately does not).

  python   Against pyan3's call graph (a static, import- and self-aware
           analyser, in requirements.txt) on language-crucible's Python repos.
           pyan is a reference, not ground truth: it has its own misses. So each
           engine link whose two ends pyan also knows is one of
             agree        pyan has the same caller -> callee edge
             wrong        pyan has the caller call a DIFFERENT function of the
                          same name (the collision the resolver exists to defeat)
             unconfirmed  pyan has no edge from the caller to that name at all
           and precision is agree / (agree + wrong). Recall is the share of
           pyan's function->function edges that the engine linked confidently.
  cobol    Against the hand-verified answer keys (tests/cobol_mainframe/
           answer_key/): every confident link out of a COBOL paragraph must
           land on a real unit (name and line) of the same program, and never
           on a unit the key proves dead.

    python tests/tools/call_graph_resolution.py python [--samples 5]
    python tests/tools/call_graph_resolution.py python --ci           # gate vs the baseline
    python tests/tools/call_graph_resolution.py python --regenerate   # rewrite the baseline
    python tests/tools/call_graph_resolution.py cobol      # needs mainframe_corpus.py fetch+scan
    python tests/tools/call_graph_resolution.py all --json out.json

Disagreements are leads to check against source (CLAUDE.md's
comparative-correctness rule), not verdicts.
"""

from __future__ import annotations

import argparse
import collections
import glob
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
BASELINE = REPO_ROOT / "tests" / "call_graph_resolution_baseline.json"
# Gate tolerance, in percentage points, before --ci calls a drop a regression.
TOLERANCE_PP = 0.5
# The python metrics --ci gates (all higher-is-better).
GATED = ("confident_precision_pct", "recall_pct", "resolution_recall_pct")
CONFIDENT = ("class", "qualified", "file", "import", "unique")
AMBIGUOUS = ("nearest", "unseen", "receiver")
_LINE_SLACK = 3

_LINKS_SQL = """
SELECT sfd.file_path, sfn.func_name, sfn.start_line, c.callee, c.step,
       dfd.file_path, dfn.func_name, dfn.start_line
FROM fcall_data c
JOIN function_data sfn ON sfn.id = c.src_func_id
JOIN file_data sfd ON sfd.id = sfn.file_id
JOIN function_data dfn ON dfn.id = c.dst_func_id
JOIN file_data dfd ON dfd.id = dfn.file_id
"""


def _scan(root: Path) -> Path:
    """In-process scan of `root` with THIS checkout's engine; returns a DB copy's path."""
    sys.path.insert(0, str(REPO_ROOT))
    import gitgalaxy
    from gitgalaxy.galaxyscope import main as galaxyscope_main

    if Path(gitgalaxy.__file__).resolve().parents[1] != REPO_ROOT:
        raise SystemExit(f"engine import resolved to {gitgalaxy.__file__}, not {REPO_ROOT} -- set PYTHONPATH")
    out = Path(tempfile.mkdtemp(prefix="cgr_"))
    argv = sys.argv
    sys.argv = ["galaxyscope", str(root), "--output", str(out / "s.json"), "--db-only"]
    try:
        galaxyscope_main()
    finally:
        sys.argv = argv
    (db,) = out.glob("*_master.db")
    return db


def _extracted(db: Path) -> dict[tuple[str, str, int], set[str]]:
    """(path, name, start_line) -> the callee names calls_out_to holds."""
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            "SELECT fd.file_path, fn.func_name, fn.start_line, fn.calls_out_to "
            "FROM function_data fn JOIN file_data fd ON fd.id = fn.file_id"
        ).fetchall()
    finally:
        conn.close()
    return {(p, n, int(line or 0)): set(json.loads(c or "[]")) for p, n, line, c in rows}


def _links(db: Path) -> list[tuple]:
    conn = sqlite3.connect(db)
    try:
        return conn.execute(_LINKS_SQL).fetchall()
    finally:
        conn.close()


# ----------------------------------------------------------------------------- python / pyan3


def _compiles(path: str) -> bool:
    """pyan aborts the whole run on one file Python itself cannot compile."""
    try:
        compile(Path(path).read_text(encoding="utf-8", errors="replace"), path, "exec")
    except (SyntaxError, ValueError):
        return False
    return True


def _pyan_graph(repo: Path) -> tuple[dict[tuple[str, str], list[int]], set[tuple], dict[tuple, set[tuple]]]:
    """pyan3 over every compilable .py file of `repo`.

    Returns (defs, edges, by_caller_name):
      defs     (relpath, name) -> def lines
      edges    {(caller_key, callee_key)}, a key being (relpath, name, line)
      by_name  (caller_key, callee_name) -> the callee keys pyan links it to
    """
    from pyan.analyzer import CallGraphVisitor

    files = [f for f in glob.glob(str(repo / "**" / "*.py"), recursive=True) if _compiles(f)]
    v = CallGraphVisitor(files, root=str(repo))

    def key(node):
        if (
            node.filename is None
            or node.ast_node is None
            or str(node.flavor) not in ("Flavor.FUNCTION", "Flavor.METHOD")
        ):
            return None
        return (os.path.relpath(node.filename, repo), node.name, int(getattr(node.ast_node, "lineno", 0)))

    defs: dict[tuple[str, str], list[int]] = collections.defaultdict(list)
    edges: set[tuple] = set()
    by_name: dict[tuple, set[tuple]] = collections.defaultdict(set)
    for src, dsts in v.uses_edges.items():
        ks = key(src)
        if ks is None:
            continue
        for dst in dsts:
            kd = key(dst)
            if kd is None or kd == ks:
                continue
            edges.add((ks, kd))
            by_name[(ks, kd[1])].add(kd)
    for node_list in v.nodes.values():
        for node in node_list:
            k = key(node)
            if k:
                defs[(k[0], k[1])].append(k[2])
    return defs, edges, by_name


def _to_pyan(defs: dict[tuple[str, str], list[int]], path: str, name: str, line: int):
    """An engine function (repo-relative path) to pyan's key, by name then nearest line."""
    lines = defs.get((path, name))
    if not lines:
        return None
    best = min(lines, key=lambda x: abs(x - line))
    return (path, name, best) if abs(best - line) <= _LINE_SLACK else None


def score_python(samples: int = 0) -> dict[str, Any]:
    root = CRUCIBLE / "data" / "python"
    totals = {g: collections.Counter() for g in ("confident", "ambiguous")}
    recall_hits = recall_total = 0
    named_hits = named_total = 0
    wrong_examples: list[str] = []
    per_repo = {}
    for repo in sorted(p for p in root.iterdir() if p.is_dir()):
        defs, edges, by_name = _pyan_graph(repo)
        db = _scan(repo)
        mine: set[tuple] = set()
        repo_counts = {g: collections.Counter() for g in totals}
        for sp, sn, sl, _callee, step, dp, dn, dl in _links(db):
            group = "confident" if step in CONFIDENT else "ambiguous" if step in AMBIGUOUS else None
            if group is None:
                continue
            ks, kd = _to_pyan(defs, sp, sn, sl), _to_pyan(defs, dp, dn, dl)
            if ks is None or kd is None:
                repo_counts[group]["unmapped"] += 1
                continue
            if group == "confident":
                mine.add((ks, kd))
            if (ks, kd) in edges:
                verdict = "agree"
            elif by_name.get((ks, kd[1])):
                verdict = "wrong"
                if group == "confident" and len(wrong_examples) < samples:
                    other = sorted(by_name[(ks, kd[1])])[0]
                    wrong_examples.append(f"{repo.name}: {sp}:{sn} -> {dp}:{dl} (pyan: {other[0]}:{other[2]})")
            else:
                verdict = "unconfirmed"
            repo_counts[group][verdict] += 1
        mapped_edges = {e for e in edges if e[1][1]}
        recall_total += len(mapped_edges)
        recall_hits += len(mapped_edges & mine)
        # Resolution recall: only pyan edges whose callee NAME the engine extracted
        # for that caller -- the resolver's own share, apart from Level 1's misses
        # and from pyan's reference edges (a function passed or returned, which the
        # #3327 contract does not count as a call).
        extracted = {}
        for (p, n, line), names in _extracted(db).items():
            k = _to_pyan(defs, p, n, line)
            if k is not None:
                extracted.setdefault(k, set()).update(names)
        named = {e for e in mapped_edges if e[1][1] in extracted.get(e[0], ())}
        named_total += len(named)
        named_hits += len(named & mine)
        for g in totals:
            totals[g].update(repo_counts[g])
        per_repo[repo.name] = {g: dict(c) for g, c in repo_counts.items()}

    def rates(c: collections.Counter) -> dict[str, Any]:
        judged = c["agree"] + c["wrong"]
        return {
            **dict(c),
            "precision_pct": round(100.0 * c["agree"] / judged, 1) if judged else None,
            "wrong_target_pct": round(100.0 * c["wrong"] / judged, 1) if judged else None,
        }

    return {
        "reference": "pyan3",
        "confident": rates(totals["confident"]),
        "ambiguous": rates(totals["ambiguous"]),
        "recall_pct": round(100.0 * recall_hits / recall_total, 1) if recall_total else None,
        "resolution_recall_pct": round(100.0 * named_hits / named_total, 1) if named_total else None,
        "named_pyan_edges": named_total,
        "pyan_edges": recall_total,
        "per_repo": per_repo,
        "wrong_examples": wrong_examples,
    }


# ----------------------------------------------------------------------------- cobol / answer keys


def score_cobol() -> dict[str, Any]:
    sys.path.insert(0, str(TOOLS))
    import mainframe_corpus as mc

    out: dict[str, Any] = {}
    for corpus in mc.load_manifest():
        key_path = corpus.get("answer_key")
        if not key_path:
            continue
        db = mc.cache_root() / "_scans" / corpus["name"]
        dbs = sorted(db.glob("*/*_master.db"), key=lambda p: p.stat().st_mtime)
        if not dbs:
            out[corpus["name"]] = "not scanned: run mainframe_corpus.py fetch+scan"
            continue
        key = json.loads((REPO_ROOT / key_path).read_text())
        programs = key.get("programs", {})
        c = collections.Counter()
        bad: list[str] = []
        for sp, sn, _sl, _callee, step, dp, dn, dl in _links(dbs[-1]):
            prog = programs.get(sp)
            if prog is None or step not in CONFIDENT:
                continue
            c["links"] += 1
            units = {(u["name"].upper(), int(u["line"])) for u in prog.get("units", [])}
            dead = {n.upper() for n in (prog.get("dead") or {})}
            if dp != sp:
                c["other_program"] += 1
                bad.append(f"{sp}:{sn} -> {dp}:{dn}")
            elif (str(dn).upper(), int(dl)) not in units:
                c["not_a_unit"] += 1
                bad.append(f"{sp}:{sn} -> {dn}@{dl}")
            elif str(dn).upper() in dead:
                c["into_dead_unit"] += 1
                bad.append(f"{sp}:{sn} -> dead {dn}")
            else:
                c["correct"] += 1
        out[corpus["name"]] = {
            **dict(c),
            "correct_pct": round(100.0 * c["correct"] / c["links"], 1) if c["links"] else None,
            "issues": bad[:10],
        }
    return out


def gated_metrics(py: dict[str, Any]) -> dict[str, Any]:
    """The flat, baseline-able view of score_python's result."""
    return {
        "confident_precision_pct": py["confident"]["precision_pct"],
        "confident_judged": py["confident"].get("agree", 0) + py["confident"].get("wrong", 0),
        "ambiguous_precision_pct": py["ambiguous"]["precision_pct"],
        "recall_pct": py["recall_pct"],
        "resolution_recall_pct": py["resolution_recall_pct"],
        "pyan_edges": py["pyan_edges"],
    }


def regressions(current: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    return [
        f"python: {m} {baseline[m]} -> {current.get(m)}"
        for m in GATED
        if baseline.get(m) is not None and (current.get(m) or 0.0) < baseline[m] - TOLERANCE_PP
    ]


def render(current: dict[str, Any]) -> str:
    def pct(v: Any) -> str:
        return "n/a" if v is None else f"{v}%"

    return "\n".join(
        [
            "| language | reference | confident precision | ambiguous precision | recall | resolution recall |",
            "|---|---|---|---|---|---|",
            f"| python | pyan3 | {pct(current['confident_precision_pct'])} ({current['confident_judged']} judged) | "
            f"{pct(current['ambiguous_precision_pct'])} | {pct(current['recall_pct'])} | "
            f"{pct(current['resolution_recall_pct'])} |",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("python", "cobol", "all"))
    ap.add_argument("--samples", type=int, default=5)
    ap.add_argument("--json", metavar="PATH")
    ap.add_argument("--ci", action="store_true", help="python: fail on a drop beyond the baseline tolerance")
    ap.add_argument("--regenerate", action="store_true", help="python: rewrite the committed baseline")
    ap.add_argument("--summary", metavar="PATH", help="append the python table here (e.g. $GITHUB_STEP_SUMMARY)")
    a = ap.parse_args(argv)
    if (a.ci or a.regenerate) and a.mode == "cobol":
        print(
            "call_graph_resolution: --ci/--regenerate gate the python mode (cobol is gated by the ground-truth ledger)"
        )
        return 2
    result: dict[str, Any] = {}
    if a.mode in ("python", "all"):
        result["python"] = score_python(a.samples)
    if a.mode in ("cobol", "all"):
        result["cobol"] = score_cobol()
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "per_repo"} for k, v in result.items()}, indent=2))
    if a.json:
        Path(a.json).write_text(json.dumps(result, indent=2) + "\n")
    if "python" not in result:
        return 0
    current = gated_metrics(result["python"])
    print(render(current))
    if a.summary:
        with open(a.summary, "a", encoding="utf-8") as fh:
            fh.write("### Call resolution (Level 2: engine links vs pyan3)\n\n" + render(current) + "\n\n")
    # #2682: an audit that measured nothing must not pass.
    if (a.ci or a.regenerate) and not current["confident_judged"]:
        print("call_graph_resolution: FAIL -- no confident link was judged (scan, pyan or corpus problem)")
        return 1
    if a.regenerate:
        BASELINE.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        print(f"call_graph_resolution: baseline rewritten -> {BASELINE.relative_to(REPO_ROOT)}")
        return 0
    if a.ci:
        if not BASELINE.exists():
            print("call_graph_resolution: no baseline; run --regenerate")
            return 1
        bad = regressions(current, json.loads(BASELINE.read_text()))
        if bad:
            print("call_graph_resolution: REGRESSION\n  " + "\n  ".join(bad))
            return 1
        print("call_graph_resolution: OK -- no gated metric dropped beyond the baseline tolerance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
