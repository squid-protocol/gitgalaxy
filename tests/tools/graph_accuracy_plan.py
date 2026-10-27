#!/usr/bin/env python3
"""Which graph-accuracy gates a pull request can move (the "plan" job of graph-accuracy-audit.yml, #6501).

    python tests/tools/graph_accuracy_plan.py [--event pull_request] [--base origin/main] [--files FILE ...] [--github-output PATH]
    python tests/tools/graph_accuracy_plan.py --resolve ",import-graph,call-go," [--github-output PATH]
    python tests/tools/graph_accuracy_plan.py --replay 50

The workflow installs Node, a JDK, Rust, Go and libclang and runs ten gates. A Haskell rule change moves none of the
call-resolution gates, so this planner maps each changed file to the gates that can move (stdlib only: the job runs before
anything is installed, as ground_truth_plan.py does):

  languages/<lang>.py          that language's call gate (if it has one) + import-graph (if the language is in
                               tests/import_graph_corpus.json) + span anchoring (it covers every language)
  a gate's tool or baseline    that gate; a shared adapter moves every gate on it (scip_callgraph: java, rust;
                               clang_callgraph: c, cpp; ts_callgraph.js: typescript, javascript; go_callgraph/: go)
  shared core, the workflow, the planner, the pins, the corpus list, any other language_standards file   all gates
  anything else                none (the required check reports success)

Every event that is not a pull_request, an empty diff and an unreadable diff plan all gates (when in doubt, run).
Gates are written `,a,b,` so a workflow tests `contains(gates, ',call-c,')` without `call-c` matching `call-cpp`.
--resolve turns the plan job's output into the toolchain switches the job reads; an EMPTY output (the plan job
failed) resolves to all gates, `,` (planned none) to no gates.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import change_classifier  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]

CALL_LANGS = ("python", "typescript", "javascript", "java", "rust", "go", "c", "cpp")
IMPORT, SPAN = "import-graph", "span-anchoring"
ALL = (IMPORT, *(f"call-{lang}" for lang in CALL_LANGS), SPAN)
CALL = tuple(g for g in ALL if g.startswith("call-"))

LANG_DIR = "gitgalaxy/standards/language_standards/languages/"
LANG_STANDARDS = "gitgalaxy/standards/language_standards/"
CORPUS = "tests/import_graph_corpus.json"
T = "tests/tools/"

# Everything here can move every gate (an entry ending in `/` is a directory prefix).
EVERYTHING = (
    "gitgalaxy/core/detector.py",
    "gitgalaxy/core/prism.py",
    "gitgalaxy/core/network_risk_sensor.py",
    "gitgalaxy/core/call_resolver.py",
    ".github/workflows/graph-accuracy-audit.yml",
    "tests/crucible_pins.toml",
    T + "crucible_pins.py",
    T + "graph_accuracy_plan.py",
    T + "change_classifier.py",
    T + "ci_retry.sh",
    CORPUS,  # the pinned repos every corpus gate clones
)
# The tool or baseline of a gate (or of the gates sharing an adapter).
OWNERS: dict[str, tuple[str, ...]] = {
    T + "import_graph_accuracy.py": (IMPORT,),
    "tests/import_graph_accuracy_baseline.json": (IMPORT,),
    T + "call_graph_resolution.py": CALL,
    T + "callgraph_refs.py": CALL,
    T + "ts_callgraph.js": ("call-typescript", "call-javascript"),
    T + "scip_callgraph.py": ("call-java", "call-rust"),
    T + "clang_callgraph.py": ("call-c", "call-cpp"),
    T + "go_callgraph/": ("call-go",),
    T + "span_anchor_audit.py": (SPAN,),
    "tests/span_anchor_baseline.json": (SPAN,),
    "tests/call_graph_resolution_baseline.json": ("call-python",),
    **{f"tests/call_graph_resolution_{lang}_baseline.json": (f"call-{lang}",) for lang in CALL_LANGS[1:]},
}
# Gates that read the import-graph corpus clones (the rest read language-crucible, or both).
CORPUS_GATES = frozenset({IMPORT} | {f"call-{lang}" for lang in CALL_LANGS[1:]})
CRUCIBLE_GATES = frozenset({"call-python", SPAN})
# Gates that need a toolchain step: step key -> the gates that need it.
TOOLCHAINS = {
    "node": ("call-typescript", "call-javascript"),
    "java": ("call-java",),
    "rust": ("call-rust",),
    "go": ("call-go",),
    "clang": ("call-c", "call-cpp"),
}


def _norm(lang: str) -> str:
    return re.sub(r"[-_]", "", lang.lower())


def corpus_languages(root: Path = REPO_ROOT) -> frozenset[str]:
    """The languages tests/import_graph_corpus.json pins repos for (normalised: `objective-c` == `objectivec`)."""
    data = json.loads((root / CORPUS).read_text(encoding="utf-8"))
    return frozenset(_norm(r["language"]) for r in data["repos"])


def _owners(path: str) -> tuple[str, ...] | None:
    for key, gates in OWNERS.items():
        if path == key or (key.endswith("/") and path.startswith(key)):
            return gates
    return None


def gates_for(path: str, corpus: frozenset[str]) -> set[str]:
    """The gates a changed file can move (empty: none). When in doubt, every gate."""
    if path in EVERYTHING:
        return set(ALL)
    owned = _owners(path)
    if owned is not None:
        return set(owned)
    if path.startswith(LANG_DIR) and path.endswith(".py") and "/" not in path[len(LANG_DIR) :]:
        stem = path[len(LANG_DIR) : -3]
        if stem.startswith("_"):  # __init__ and helpers: shared by the languages
            return set(ALL)
        out = {SPAN}
        if stem in CALL_LANGS:
            out.add(f"call-{stem}")
        if _norm(stem) in corpus:
            out.add(IMPORT)
        return out
    if path.startswith(LANG_STANDARDS):  # identifiers.py, _shared_patterns.py, a registry or a data file
        return set(ALL)
    return set()


def plan(files: list[str], event: str, corpus: frozenset[str] | None = None) -> dict:
    if event != "pull_request":
        return {"gates": list(ALL), "reason": f"{event}: every gate", "inputs": []}
    if not files:
        return {"gates": list(ALL), "reason": "no changed files found (the diff is unreadable or empty)", "inputs": []}
    corpus = corpus_languages() if corpus is None else corpus
    chosen: set[str] = set()
    inputs: list[str] = []
    for f in sorted(files):
        g = gates_for(f, corpus)
        if g:
            chosen |= g
            inputs.append(f)
    gates = [g for g in ALL if g in chosen]
    if not gates:
        areas = sorted({change_classifier.area(f) for f in files})
        return {"gates": [], "reason": f"no changed file feeds a gate (areas: {', '.join(areas)})", "inputs": []}
    return {
        "gates": gates,
        "reason": f"{len(inputs)} changed file(s) feed a gate, first: {inputs[0]}",
        "inputs": inputs[:20],
    }


def wrap(gates) -> str:
    return "," + "".join(f"{g}," for g in gates)


def resolve(planned: str) -> dict[str, str]:
    """The step outputs the job reads from the plan job's `gates` output ('' = the plan failed: every gate)."""
    gates = set(ALL) if planned == "" else {g for g in planned.split(",") if g}
    unknown = gates - set(ALL)
    if unknown:  # a gate this script does not know: run everything rather than skip it
        gates = set(ALL)
    out = {"gates": wrap(g for g in ALL if g in gates), "any": str(bool(gates)).lower()}
    out["import_corpus"] = str(bool(gates & CORPUS_GATES)).lower()
    out["crucible"] = str(bool(gates & CRUCIBLE_GATES)).lower()
    for key, needing in TOOLCHAINS.items():
        out[key] = str(bool(gates & set(needing))).lower()
    return out


def changed_files(base: str) -> list[str]:
    proc = subprocess.run(["git", "diff", "--name-only", f"{base}...HEAD"], cwd=REPO_ROOT,  # noqa: S603, S607
                          capture_output=True, text=True, check=False)  # fmt: skip
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git diff failed")
    return [ln for ln in proc.stdout.splitlines() if ln.strip()]


def replay(prs: list[dict], corpus: frozenset[str]) -> dict:
    """Of the pull requests in `prs` (`gh pr list --json number,files`): how many the workflow's `paths:` filter starts
    BEFORE (it ran every gate), and how many start a gate AFTER, with the gate count each. A PR whose file list may
    be cut short by gh (100 entries) counts as every gate."""
    paths = _workflow_paths()
    before = after = 0
    per_pr = {}
    for pr in prs:
        files = [f["path"] for f in pr.get("files") or [] if f.get("path")]
        if len(files) >= 100:
            triggered, gates = True, list(ALL)
        else:
            triggered = any(_glob(f, paths) for f in files)
            gates = plan(files, "pull_request", corpus)["gates"] if triggered else []
        before += triggered
        after += bool(gates)
        if triggered:
            per_pr[pr["number"]] = len(gates)
    n = len(prs)
    return {
        "prs": n,
        "ran_before": before,
        "runs_now": after,
        "share_before": round(before / n, 3) if n else 0.0,
        "share_now": round(after / n, 3) if n else 0.0,
        "mean_gates_when_run": round(sum(c for c in per_pr.values() if c) / max(after, 1), 1),
        "gates_per_triggered_pr": per_pr,
    }


def _glob(path: str, patterns: list[str]) -> bool:
    for p in patterns:
        rx = re.escape(p).replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
        if re.fullmatch(rx, path):
            return True
    return False


def _workflow_paths() -> list[str]:
    """The `paths:` filter of the workflow, read as text (stdlib only: no yaml)."""
    text = (REPO_ROOT / ".github/workflows/graph-accuracy-audit.yml").read_text(encoding="utf-8")
    block = text.split("    paths:\n", 1)[1].split("\n\npermissions:", 1)[0]
    return re.findall(r'^\s+- "([^"]+)"', block, flags=re.M)


def run_replay(n: int) -> dict:
    proc = subprocess.run(  # noqa: S603
        ["gh", "pr", "list", "--state", "merged", "-L", str(n), "--json", "number,files"],  # noqa: S607
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "gh pr list failed")
    return replay(json.loads(proc.stdout), corpus_languages())


def _emit(path: Path | None, items: dict[str, str]) -> None:
    if path:
        with path.open("a", encoding="utf-8") as fh:
            fh.writelines(f"{k}={v}\n" for k, v in items.items())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--event", default="pull_request")
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--files", nargs="*", help="the changed files, instead of git diff --name-only BASE...HEAD")
    ap.add_argument("--github-output", type=Path, help="append the outputs for later steps")
    ap.add_argument("--resolve", metavar="GATES", help="turn the plan job's gates output into the job's switches")
    ap.add_argument("--replay", type=int, metavar="N", help="plan the last N merged PRs (needs gh)")
    args = ap.parse_args()
    if args.replay:
        try:
            print(json.dumps(run_replay(args.replay), indent=1))
        except (RuntimeError, OSError, ValueError) as e:
            print(f"replay failed: {e}", file=sys.stderr)
            return 1
        return 0
    if args.resolve is not None:
        out = resolve(args.resolve)
        print(json.dumps(out, indent=1))
        _emit(args.github_output, out)
        return 0
    try:
        files = (
            args.files if args.files is not None else (changed_files(args.base) if args.event == "pull_request" else [])
        )
        p = plan(files, args.event)
    except (RuntimeError, OSError, ValueError, KeyError) as e:  # cannot tell what changed: everything
        p = {"gates": list(ALL), "reason": f"cannot plan ({e})", "inputs": []}
    print(json.dumps(p, indent=1))
    _emit(args.github_output, {"gates": wrap(p["gates"])})
    return 0


if __name__ == "__main__":
    sys.exit(main())
