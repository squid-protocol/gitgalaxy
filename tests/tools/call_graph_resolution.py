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
  typescript
           Against the TypeScript compiler's own type checker
           (tests/tools/ts_callgraph.js, typescript pinned at TYPESCRIPT_VERSION)
           on the pinned typescript repos of tests/import_graph_corpus.json
           (fetched by import_graph_accuracy.py --fetch-only). Same verdicts as
           python, plus one pyan cannot give:
             external     the checker resolved the call ONLY outside the repo
                          (`str.trim()` is String.prototype.trim), so an engine
                          link to a repo function of that name is wrong.
           Reported as strict precision, agree / (agree + wrong + external).
  cobol    Against the hand-verified answer keys (tests/cobol_mainframe/
           answer_key/): every confident link out of a COBOL paragraph must
           land on a real unit (name and line) of the same program, and never
           on a unit the key proves dead.

    python tests/tools/call_graph_resolution.py python [--samples 5]
    python tests/tools/call_graph_resolution.py python --ci           # gate vs the baseline
    python tests/tools/call_graph_resolution.py python --regenerate   # rewrite the baseline
    python tests/tools/call_graph_resolution.py typescript --ci       # needs node + typescript
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
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS = Path(__file__).resolve().parent
CRUCIBLE = Path(os.environ.get("LANGUAGE_CRUCIBLE_PATH", REPO_ROOT.parent / "language-crucible"))
BASELINE = REPO_ROOT / "tests" / "call_graph_resolution_baseline.json"
BASELINES = {
    "python": BASELINE,
    "typescript": REPO_ROOT / "tests" / "call_graph_resolution_typescript_baseline.json",
}
REFERENCE = {"python": "pyan3", "typescript": "tsc"}
# The TypeScript checker the typescript baseline was measured with (CI installs it;
# a different version is warned about, and refused by --regenerate).
TYPESCRIPT_VERSION = "6.0.2"

sys.path.insert(0, str(REPO_ROOT))
from gitgalaxy.core.call_resolver import CONFIDENT_RESOLUTIONS, RESOLUTION_OF_STEP  # noqa: E402

# Gate tolerance, in percentage points, before --ci calls a drop a regression.
TOLERANCE_PP = 0.5
# The python metrics --ci gates (all higher-is-better).
GATED = ("confident_precision_pct", "recall_pct", "resolution_recall_pct")
# the resolver's own confident steps, so a new one is counted without an edit here
CONFIDENT = tuple(step for step, res in RESOLUTION_OF_STEP.items() if res in CONFIDENT_RESOLUTIONS)
AMBIGUOUS = ("nearest", "unseen", "receiver")
_LINE_SLACK = 3

_LINKS_SQL = """
SELECT sfd.file_path, sfn.func_name, sfn.start_line, c.callee, c.step,
       dfd.file_path, dfn.func_name, dfn.start_line, c.kind
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


class RefGraph:
    """A reference tool's call graph for one repo, keyed like pyan (relpath, name, line).

    defs      (relpath, name) -> def lines
    edges     {(caller_key, callee_key)}
    by_name   (caller_key, callee_name) -> the callee keys the reference links it to
    external  {(caller_key, callee_name)}: calls the reference resolved ONLY outside
              the repo (a built-in or library method). pyan cannot say this; the
              TypeScript checker can, so an engine link there is provably wrong.
    """

    def __init__(self, defs, edges, by_name, external=frozenset()) -> None:
        self.defs, self.edges, self.by_name, self.external = defs, edges, by_name, external


def _verdict(ref: RefGraph, ks: tuple, kd: tuple) -> str:
    if (ks, kd) in ref.edges:
        return "agree"
    if ref.by_name.get((ks, kd[1])):
        return "wrong"
    if (ks, kd[1]) in ref.external:
        return "external"
    return "unconfirmed"


def _score(reference: str, repos, samples: int = 0) -> dict[str, Any]:
    """Engine links vs a reference graph. `repos` yields (name, RefGraph, engine db)."""
    totals = {g: collections.Counter() for g in ("confident", "ambiguous", "decorator", "reference")}
    recall_dec_hits = recall_all_hits = 0
    recall_hits = recall_total = 0
    named_hits = named_total = 0
    wrong_examples: list[str] = []
    external_examples: list[str] = []
    per_repo = {}
    for repo_name, ref, db in repos:
        defs, edges, by_name = ref.defs, ref.edges, ref.by_name
        mine: set[tuple] = set()
        mine_dec: set[tuple] = set()
        mine_ref: set[tuple] = set()
        repo_counts = {g: collections.Counter() for g in totals}
        for sp, sn, sl, _callee, step, dp, dn, dl, kind in _links(db):
            if kind in ("decorator", "reference"):
                # decorated function -> decorator, function -> a function it uses as a
                # value: each its own precision and recall line; the gated call
                # metrics below stay calls-only
                ks, kd = _to_pyan(defs, sp, sn, sl), _to_pyan(defs, dp, dn, dl)
                if step not in CONFIDENT:
                    continue
                if ks is None or kd is None:
                    repo_counts[kind]["unmapped"] += 1
                    continue
                (mine_dec if kind == "decorator" else mine_ref).add((ks, kd))
                repo_counts[kind][_verdict(ref, ks, kd)] += 1
                continue
            if kind not in (None, "call"):
                continue
            group = "confident" if step in CONFIDENT else "ambiguous" if step in AMBIGUOUS else None
            if group is None:
                continue
            ks, kd = _to_pyan(defs, sp, sn, sl), _to_pyan(defs, dp, dn, dl)
            if ks is None or kd is None:
                repo_counts[group]["unmapped"] += 1
                continue
            if group == "confident":
                mine.add((ks, kd))
            verdict = _verdict(ref, ks, kd)
            if group == "confident" and verdict == "wrong" and len(wrong_examples) < samples:
                other = sorted(by_name[(ks, kd[1])])[0]
                wrong_examples.append(f"{repo_name}: {sp}:{sn} -> {dp}:{dl} ({reference}: {other[0]}:{other[2]})")
            if group == "confident" and verdict == "external" and len(external_examples) < samples:
                external_examples.append(f"{repo_name}: {sp}:{sn} -> {dp}:{dn}@{dl} ({reference}: outside the repo)")
            repo_counts[group][verdict] += 1
        mapped_edges = {e for e in edges if e[1][1]}
        recall_total += len(mapped_edges)
        recall_hits += len(mapped_edges & mine)
        recall_dec_hits += len(mapped_edges & (mine | mine_dec))
        recall_all_hits += len(mapped_edges & (mine | mine_dec | mine_ref))
        # Resolution recall: only reference edges whose callee NAME the engine extracted
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
        per_repo[repo_name] = {g: dict(c) for g, c in repo_counts.items()}

    def rates(c: collections.Counter) -> dict[str, Any]:
        judged = c["agree"] + c["wrong"]
        strict = judged + c["external"]
        return {
            **dict(c),
            "precision_pct": round(100.0 * c["agree"] / judged, 1) if judged else None,
            "wrong_target_pct": round(100.0 * c["wrong"] / judged, 1) if judged else None,
            # also counts a link the reference proves goes outside the repo as wrong
            "strict_precision_pct": round(100.0 * c["agree"] / strict, 1) if strict else None,
        }

    return {
        "reference": reference,
        "confident": rates(totals["confident"]),
        "ambiguous": rates(totals["ambiguous"]),
        "recall_pct": round(100.0 * recall_hits / recall_total, 1) if recall_total else None,
        # calls + decorator edges (decorated function -> decorator), not gated
        "decorator": rates(totals["decorator"]),
        "recall_with_decorators_pct": round(100.0 * recall_dec_hits / recall_total, 1) if recall_total else None,
        # calls + decorators + references (function names used as values), not gated
        "reference_edges": rates(totals["reference"]),
        "recall_all_kinds_pct": round(100.0 * recall_all_hits / recall_total, 1) if recall_total else None,
        "resolution_recall_pct": round(100.0 * named_hits / named_total, 1) if named_total else None,
        "named_pyan_edges": named_total,
        "pyan_edges": recall_total,
        "per_repo": per_repo,
        "wrong_examples": wrong_examples,
        "external_examples": external_examples,
    }


def score_python(samples: int = 0) -> dict[str, Any]:
    root = CRUCIBLE / "data" / "python"

    def repos():
        for repo in sorted(p for p in root.iterdir() if p.is_dir()):
            yield repo.name, RefGraph(*_pyan_graph(repo)), _scan(repo)

    return _score("pyan3", repos(), samples)


# ----------------------------------------------------------------------------- typescript / tsc


def _node_env() -> dict[str, str]:
    """NODE_PATH for ts_callgraph.js: the caller's, else the global npm root."""
    env = dict(os.environ)
    if not env.get("NODE_PATH"):
        try:
            root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            root = ""
        if root:
            env["NODE_PATH"] = root
    return env


def _tsc_graph(repo: Path) -> tuple[RefGraph, str]:
    """The TypeScript checker's call graph of `repo` (tests/tools/ts_callgraph.js)."""
    try:
        proc = subprocess.run(
            ["node", str(TOOLS / "ts_callgraph.js"), str(repo)],
            capture_output=True,
            text=True,
            env=_node_env(),
        )
    except OSError as exc:
        raise SystemExit(f"call_graph_resolution: node is required for the typescript mode ({exc})") from exc
    if proc.returncode != 0:
        raise SystemExit(f"call_graph_resolution: ts_callgraph.js failed on {repo}:\n{proc.stderr[-2000:]}")
    raw = json.loads(proc.stdout)
    defs: dict[tuple[str, str], list[int]] = collections.defaultdict(list)
    edges: set[tuple] = set()
    by_name: dict[tuple, set[tuple]] = collections.defaultdict(set)
    for p, n, line in raw["defs"]:
        defs[(p, n)].append(int(line))
    for src, dst in raw["edges"]:
        ks, kd = tuple(src), tuple(dst)
        edges.add((ks, kd))
        by_name[(ks, kd[1])].add(kd)
    external = {(tuple(src), name) for src, name in raw["external"]}
    return RefGraph(defs, edges, by_name, external), raw["version"]


def score_typescript(samples: int = 0) -> dict[str, Any]:
    """Against the TypeScript checker on the pinned typescript repos of
    tests/import_graph_corpus.json. Not language-crucible: its TypeScript samples
    are flattened into one directory per repo, so no relative import resolves and
    the checker would know almost nothing."""
    sys.path.insert(0, str(TOOLS))
    import import_graph_accuracy as iga

    entries = [e for e in iga.load_manifest() if e["language"] == "typescript"]
    missing = [e["repo"] for e in entries if not (iga.repo_dir(iga.CORPUS, e) / ".git").is_dir()]
    if missing:
        raise SystemExit(f"call_graph_resolution: not fetched: {missing} -- run import_graph_accuracy.py --fetch-only")
    versions: set[str] = set()

    def repos():
        for e in entries:
            d = iga.repo_dir(iga.CORPUS, e)
            ref, version = _tsc_graph(d)
            versions.add(version)
            yield e["repo"], ref, _scan(d)

    result = _score("tsc", repos(), samples)
    result["reference_version"] = ", ".join(sorted(versions))
    return result


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
        for sp, sn, _sl, _callee, step, dp, dn, dl, _kind in _links(dbs[-1]):
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
    """The flat, baseline-able view of a _score result (python or typescript)."""
    out = {
        "confident_precision_pct": py["confident"]["precision_pct"],
        "confident_judged": py["confident"].get("agree", 0) + py["confident"].get("wrong", 0),
        "ambiguous_precision_pct": py["ambiguous"]["precision_pct"],
        "recall_pct": py["recall_pct"],
        "resolution_recall_pct": py["resolution_recall_pct"],
        "pyan_edges": py["pyan_edges"],
        # decorator edges (kind='decorator'): reported and baselined, not gated
        "decorator_precision_pct": (py.get("decorator") or {}).get("precision_pct"),
        "decorator_judged": (py.get("decorator") or {}).get("agree", 0) + (py.get("decorator") or {}).get("wrong", 0),
        "recall_with_decorators_pct": py.get("recall_with_decorators_pct"),
        "reference_precision_pct": (py.get("reference_edges") or {}).get("precision_pct"),
        "reference_judged": (py.get("reference_edges") or {}).get("agree", 0)
        + (py.get("reference_edges") or {}).get("wrong", 0),
        "recall_all_kinds_pct": py.get("recall_all_kinds_pct"),
    }
    if py.get("reference") == "tsc":
        # the checker's extra verdict: a confident link it proves leaves the repo.
        # Reported and baselined, not gated (yet).
        out["confident_external"] = py["confident"].get("external", 0)
        out["confident_strict_precision_pct"] = py["confident"].get("strict_precision_pct")
        out["confident_unmapped"] = py["confident"].get("unmapped", 0)
        out["reference_version"] = py.get("reference_version")
        for k in ("decorator_precision_pct", "decorator_judged", "recall_with_decorators_pct"):
            out.pop(k)
        for k in ("reference_precision_pct", "reference_judged", "recall_all_kinds_pct"):
            out.pop(k)
    return out


def regressions(current: dict[str, Any], baseline: dict[str, Any], lang: str = "python") -> list[str]:
    return [
        f"{lang}: {m} {baseline[m]} -> {current.get(m)}"
        for m in GATED
        if baseline.get(m) is not None and (current.get(m) or 0.0) < baseline[m] - TOLERANCE_PP
    ]


def render(current: dict[str, Any], lang: str = "python") -> str:
    def pct(v: Any) -> str:
        return "n/a" if v is None else f"{v}%"

    reference = REFERENCE[lang]
    lines = [
        "| language | reference | confident precision | ambiguous precision | recall | resolution recall |",
        "|---|---|---|---|---|---|",
        f"| {lang} | {reference} | {pct(current['confident_precision_pct'])} ({current['confident_judged']} judged) | "
        f"{pct(current['ambiguous_precision_pct'])} | {pct(current['recall_pct'])} | "
        f"{pct(current['resolution_recall_pct'])} |",
    ]
    if current.get("confident_strict_precision_pct") is not None:
        lines.append(
            f"\nconfident links {reference} resolves outside the repo (not gated): {current['confident_external']}; "
            f"strict precision counting them wrong {pct(current['confident_strict_precision_pct'])}; "
            f"unmapped (an end {reference} has no function for) {current['confident_unmapped']}"
        )
    if current.get("decorator_precision_pct") is not None:
        lines.append(
            f"\ndecorator edges (not gated): precision {pct(current['decorator_precision_pct'])} "
            f"({current['decorator_judged']} judged); recall with decorators {pct(current['recall_with_decorators_pct'])}"
        )
    if current.get("reference_precision_pct") is not None:
        lines.append(
            f"reference edges (not gated): precision {pct(current['reference_precision_pct'])} "
            f"({current['reference_judged']} judged); recall, all kinds {pct(current['recall_all_kinds_pct'])}"
        )
    return "\n".join(lines)


def _gate(lang: str, current: dict[str, Any], a: argparse.Namespace) -> int:
    baseline_path = BASELINES[lang]
    print(render(current, lang))
    if a.summary:
        with open(a.summary, "a", encoding="utf-8") as fh:
            fh.write(
                f"### Call resolution (Level 2: {lang} engine links vs {REFERENCE[lang]})\n\n"
                + render(current, lang)
                + "\n\n"
            )
    # #2682: an audit that measured nothing must not pass.
    if (a.ci or a.regenerate) and not current["confident_judged"]:
        print(f"call_graph_resolution: FAIL -- no confident {lang} link was judged (scan, reference or corpus problem)")
        return 1
    version = current.get("reference_version")
    if lang == "typescript" and version != TYPESCRIPT_VERSION:
        msg = f"typescript {version} is not the pinned {TYPESCRIPT_VERSION}; numbers are not comparable to the baseline"
        if a.regenerate:
            print(f"call_graph_resolution: FAIL -- {msg}")
            return 1
        print(f"call_graph_resolution: WARNING -- {msg}")
    if a.regenerate:
        baseline_path.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        print(f"call_graph_resolution: baseline rewritten -> {baseline_path.relative_to(REPO_ROOT)}")
        return 0
    if a.ci:
        if not baseline_path.exists():
            print(f"call_graph_resolution: no {lang} baseline; run --regenerate")
            return 1
        bad = regressions(current, json.loads(baseline_path.read_text()), lang)
        if bad:
            print("call_graph_resolution: REGRESSION\n  " + "\n  ".join(bad))
            return 1
        print(f"call_graph_resolution: OK -- no gated {lang} metric dropped beyond the baseline tolerance.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("python", "typescript", "cobol", "all"))
    ap.add_argument("--samples", type=int, default=5)
    ap.add_argument("--json", metavar="PATH")
    ap.add_argument("--ci", action="store_true", help="python/typescript: fail on a drop beyond the baseline tolerance")
    ap.add_argument("--regenerate", action="store_true", help="python/typescript: rewrite the committed baseline")
    ap.add_argument("--summary", metavar="PATH", help="append the tables here (e.g. $GITHUB_STEP_SUMMARY)")
    a = ap.parse_args(argv)
    if (a.ci or a.regenerate) and a.mode == "cobol":
        print(
            "call_graph_resolution: --ci/--regenerate gate python and typescript (cobol is gated by the ground-truth ledger)"
        )
        return 2
    result: dict[str, Any] = {}
    if a.mode in ("python", "all"):
        result["python"] = score_python(a.samples)
    if a.mode in ("typescript", "all"):
        result["typescript"] = score_typescript(a.samples)
    if a.mode in ("cobol", "all"):
        result["cobol"] = score_cobol()
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "per_repo"} for k, v in result.items()}, indent=2))
    if a.json:
        Path(a.json).write_text(json.dumps(result, indent=2) + "\n")
    rc = 0
    for lang in ("python", "typescript"):
        if lang in result:
            rc |= _gate(lang, gated_metrics(result[lang]), a)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
