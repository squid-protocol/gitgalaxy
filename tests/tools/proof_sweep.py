#!/usr/bin/env python3
"""Re-prove every port after a change that can move them all (the runtime, the harness, an oracle model).

    python tests/tools/proof_sweep.py --work DIR [--det-only | --model-only] [--jobs 2] [--faults all] [--skip-db2]

Two sweeps, as the det-port skill's checklists ask after a runtime or harness change:
  det    every equivalence case translated and proven (det_port.py run --all-cases);
  model  every committed model-written port (a case with port/) proven as committed (equivalence.py run --faults).

DIR/sweep.json holds each case's verdict and coverage line; the summary compares them with tests/equivalence/det_sweep_baseline.json
(KNOWN_UNPROVEN at import), the cases not proven yet, each with its reason and issue: a two-way ratchet, exit 1 when a case not
listed there is not proven, or a listed one now is (--update-baseline drops those entries). Db2 cases each take a database of the pool (equivalence_db2.hold_lock), waiting when every one is taken.
--shard I/N proves the I-th of N balanced slices of the cases (1-based; by recorded duration, tests/equivalence/det_sweep_durations.json,
else by name), --cases NAME,... only those: CI's det-sweep runs the slices on N runners, each writing DIR/sweep.json, and
`--aggregate DIR [DIR ...] [--expect all|NAME,...]` merges them and applies the ratchet (a case missing from the merge fails it).
--skip-db2 leaves out the cases with a "db2" section (IBM's Db2 container is slow to start): CI's det-sweep workflow (#4463).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO_ROOT = TOOLS.parent.parent
sys.path.insert(0, str(REPO_ROOT))
from gitgalaxy.core.source_text import read_source  # noqa: E402

CASES = REPO_ROOT / "tests" / "equivalence"

BASELINE = CASES / "det_sweep_baseline.json"
DURATIONS = CASES / "det_sweep_durations.json"


def load_baseline(path: Path = BASELINE) -> dict[tuple[str, str], str]:
    """(sweep, case) -> "why (issue)" for every case not proven on purpose (tests/equivalence/det_sweep_baseline.json)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return {(sweep, case): f"{e['why']} ({e['issue'] or 'no issue'})"
            for sweep in ("det", "model") for case, e in data.get(sweep, {}).items()}  # fmt: skip


KNOWN_UNPROVEN = load_baseline()


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("GITGALAXY_LICENSE_KEY", "COMMUNITY_FREE_TIER")
    return env


def _coverage(log: Path) -> str:
    """The proof's coverage line ("... proven on N scenarios ..." or "... not proven ..."), or ""."""
    if not log.is_file():
        return ""
    lines = [ln for ln in read_source(log).text.splitlines() if "COBOL coverage:" in ln]
    return lines[-1].split("COBOL coverage:", 1)[-1].strip() if lines else ""


def is_db2(case: str) -> bool:
    """A case with a "db2" section: its proof needs IBM's Db2 container."""
    return "db2" in json.loads((CASES / case / "case.json").read_text(encoding="utf-8"))


def load_durations(path: Path = DURATIONS) -> dict[str, float]:
    """{case: seconds} recorded by `--update-durations` (what a shard is balanced by); {} when there is no file."""
    if not path.is_file():
        return {}
    return {k: float(v) for k, v in json.loads(path.read_text(encoding="utf-8")).get("det", {}).items()}


def parse_shard(text: str) -> tuple[int, int]:
    """ "I/N" (1-based) -> (I, N)."""
    try:
        i, n = (int(x) for x in text.split("/"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"--shard wants I/N (e.g. 2/4), not {text!r}") from None
    if not 1 <= i <= n:
        raise argparse.ArgumentTypeError(f"--shard {text}: I must be 1..N")
    return i, n


def split_cases(cases: list[str], n: int, durations: dict[str, float] | None = None) -> list[list[str]]:
    """`cases` in `n` deterministic slices, balanced by recorded duration (longest first onto the lightest slice; a
    case with no record counts as the median of the recorded ones); with no records at all, round-robin by name.
    Every case is in exactly one slice, the same ones whoever asks."""
    ordered = sorted(set(cases))
    known = sorted(d for c in ordered if (d := (durations or {}).get(c)) is not None)
    if not known:
        return [ordered[k::n] for k in range(n)]
    median = known[len(known) // 2]
    weight = {c: (durations or {}).get(c, median) for c in ordered}
    slices: list[list[str]] = [[] for _ in range(n)]
    load = [0.0] * n
    for c in sorted(ordered, key=lambda c: (-weight[c], c)):
        k = min(range(n), key=lambda k: (load[k], k))
        slices[k].append(c)
        load[k] += weight[c]
    return [sorted(x) for x in slices]


def shard_cases(
    cases: list[str], shard: tuple[int, int] | None, durations: dict[str, float] | None = None
) -> list[str]:
    """The cases of slice `shard` = (I, N) (all of them when there is none)."""
    if shard is None:
        return sorted(set(cases))
    i, n = shard
    return split_cases(cases, n, durations)[i - 1]


def det_cases(skip_db2: bool = False) -> list[str]:
    """Every case a det sweep proves."""
    return sorted(p.parent.name for p in CASES.glob("*/case.json") if not (skip_db2 and is_db2(p.parent.name)))


def merge_sweeps(dirs: list[Path]) -> dict[str, dict[str, dict]]:
    """The union of the `sweep.json` of each directory (a shard's work directory, or an artifact's)."""
    merged: dict[str, dict[str, dict]] = {}
    for d in dirs:
        f = d / "sweep.json" if d.is_dir() else d
        for sweep, cases in json.loads(f.read_text(encoding="utf-8")).items():
            for case, r in cases.items():
                if case in merged.setdefault(sweep, {}):
                    raise ValueError(f"{sweep} {case}: in two shards ({f})")
                merged[sweep][case] = r
    return merged


def missing_cases(results: dict[str, dict[str, dict]], expect: list[str]) -> list[str]:
    """The cases a sweep should have proven (det) and has no result for: a shard that never reported."""
    return [f"det {c}: no result (its shard did not report)" for c in expect if c not in results.get("det", {})]


def det_sweep(
    work: Path, jobs: int, faults: str, skip_db2: bool = False, only: list[str] | None = None
) -> dict[str, dict]:
    which = [c for c in det_cases(skip_db2) if only is None or c in only]
    if not which:  # nothing to prove here (a slice past the cases): no run, no image build
        work.mkdir(parents=True, exist_ok=True)
        return {}
    argv = [sys.executable, str(TOOLS / "det_port.py"), "run", *which, "--jobs", str(jobs), "--faults", faults,
            "--work", str(work)]  # fmt: skip
    subprocess.run(argv, cwd=REPO_ROOT, env=_env(), check=False, stdout=subprocess.DEVNULL)  # noqa: S603
    summary = json.loads((work / "summary.json").read_text(encoding="utf-8"))
    out = {}
    for row in summary:
        cov = _coverage(work / row["case"] / "proof.log")
        out[row["case"]] = {"proved": bool(row.get("proved")), "coverage": cov,
                            "translated": f"{row.get('translated_statements')}/{row.get('statements')}",
                            "seconds": round(row.get("translate_seconds", 0) + row.get("proof_seconds", 0), 1)}  # fmt: skip
    return out


def model_sweep(work: Path, faults: str, skip_db2: bool = False, only: list[str] | None = None) -> dict[str, dict]:
    out = {}
    for port in sorted(CASES.glob("*/port")):
        case = port.parent.name
        if (skip_db2 and is_db2(case)) or (only is not None and case not in only):
            continue
        keep, log = work / case, work / f"{case}.log"
        argv = [sys.executable, str(TOOLS / "equivalence.py"), "run", case, "--keep", str(keep), "--faults", faults]
        with log.open("wb") as fh:
            rc = subprocess.run(argv, cwd=REPO_ROOT, env=_env(), check=False, stdout=fh, stderr=subprocess.STDOUT,  # noqa: S603
                                timeout=3600).returncode  # fmt: skip
        out[case] = {"proved": rc == 0, "coverage": _coverage(log)}
        print(f"model {case:<30} {'PROVED' if rc == 0 else 'NOT PROVEN'}", flush=True)
    return out


def verdict(results: dict[str, dict[str, dict]], known_unproven: dict[tuple[str, str], str] | None = None) -> list[str]:
    """What the sweep says against KNOWN_UNPROVEN: the cases that are not proven and should be, and the listed ones
    that now are (the list is stale)."""
    baseline = KNOWN_UNPROVEN if known_unproven is None else known_unproven
    problems = []
    for sweep, cases in results.items():
        for case, r in sorted(cases.items()):
            known = (sweep, case) in baseline
            if not r["proved"] and not known:
                problems.append(
                    f"{sweep} {case}: NOT PROVEN ({r['coverage'] or 'no coverage line'}); a new failure: fix it, "
                    f"or (only with its true cause and issue) add it to {BASELINE.relative_to(REPO_ROOT)}"
                )
            elif r["proved"] and known:
                problems.append(
                    f"{sweep} {case}: now proven -- update the baseline: python tests/tools/proof_sweep.py "
                    f"--update-baseline --work <the same DIR> (or remove it from {BASELINE.relative_to(REPO_ROOT)})"
                )
    return problems


def prune_baseline(results: dict[str, dict[str, dict]], path: Path = BASELINE) -> list[str]:
    """Drop the baseline entries that now prove (never adds one); returns the cases dropped."""
    data = json.loads(path.read_text(encoding="utf-8"))
    dropped = []
    for sweep, cases in results.items():
        for case, r in cases.items():
            if r["proved"] and case in data.get(sweep, {}):
                del data[sweep][case]
                dropped.append(f"{sweep} {case}")
    path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    return dropped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", type=Path)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--faults", default="all")
    which = ap.add_mutually_exclusive_group()
    which.add_argument("--det-only", action="store_true")
    which.add_argument("--model-only", action="store_true")
    ap.add_argument("--skip-db2", action="store_true", help='leave out the cases with a "db2" section')
    ap.add_argument("--shard", type=parse_shard, metavar="I/N", help="only the I-th of N balanced slices of the cases")
    ap.add_argument("--cases", help="only these cases (comma-separated; default all)")
    ap.add_argument("--no-ratchet", action="store_true",
                    help="write sweep.json and exit 0 whatever the verdicts (a shard: `--aggregate` applies the ratchet)")  # fmt: skip
    ap.add_argument(
        "--aggregate",
        type=Path,
        nargs="+",
        metavar="DIR",
        help="no sweep: merge these shards' sweep.json (directories or files) and apply the ratchet",
    )
    ap.add_argument("--expect", default="all", help="with --aggregate: the cases that must be in the merge: all "
                    "(every det case bar Db2's, as --skip-db2) | none | NAME,NAME")  # fmt: skip
    ap.add_argument(
        "--update-baseline", action="store_true", help="after the sweep, drop the baseline entries that now prove"
    )
    ap.add_argument("--update-durations", action="store_true",
                    help="after the sweep, record each det case's seconds in det_sweep_durations.json (what --shard balances by)")  # fmt: skip
    args = ap.parse_args()
    if args.aggregate:
        results = merge_sweeps(args.aggregate)
        expect = (
            det_cases(skip_db2=True)
            if args.expect == "all"
            else []
            if args.expect == "none"
            else args.expect.split(",")
        )
        return report(results, missing_cases(results, expect), args)
    if args.work is None:
        ap.error("--work is required")
    args.work.mkdir(parents=True, exist_ok=True)
    only = [c for c in args.cases.split(",") if c] if args.cases else None
    known = {p.parent.name for p in CASES.glob("*/case.json")}
    if only and (unknown := sorted(set(only) - known)):
        ap.error(f"--cases: no such case {', '.join(unknown)}")
    if args.shard:  # the slice of what this sweep would prove, balanced by what each case took last time
        det_all = [c for c in det_cases(args.skip_db2) if only is None or c in only]
        model_all = [p.parent.name for p in CASES.glob("*/port") if (only is None or p.parent.name in only)
                     and not (args.skip_db2 and is_db2(p.parent.name))]  # fmt: skip
        det_only = shard_cases(det_all, args.shard, load_durations())
        model_only = shard_cases(model_all, args.shard)
    else:
        det_only, model_only = only, only
    results: dict[str, dict[str, dict]] = {}
    if not args.model_only:
        results["det"] = det_sweep(args.work / "det", args.jobs, args.faults, args.skip_db2, det_only)
    if not args.det_only:
        (args.work / "model").mkdir(exist_ok=True)
        results["model"] = model_sweep(args.work / "model", args.faults, args.skip_db2, model_only)
    (args.work / "sweep.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    if args.update_durations:
        write_durations(results.get("det", {}))
    return report(results, [], args)


def write_durations(det: dict[str, dict], path: Path = DURATIONS) -> None:
    """Merge the sweep's per-case seconds into the durations file (cases not in the sweep keep their record)."""
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {
        "format": "det-sweep-durations/1",
        "about": "Seconds each det case took (translate + proof) in `proof_sweep.py --det-only --update-durations`: what "
                 "`--shard I/N` balances by. A stale or missing entry only unbalances the shards, never changes a verdict.",
    }  # fmt: skip
    data.setdefault("det", {}).update({c: round(r["seconds"]) for c, r in det.items() if r.get("seconds")})
    data["det"] = dict(sorted(data["det"].items()))
    path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")


def report(results: dict[str, dict[str, dict]], missing: list[str], args: argparse.Namespace) -> int:
    """The summary and the ratchet's verdict (exit 1 on a problem; always 0 with --no-ratchet)."""
    for sweep, cases in results.items():
        n = sum(r["proved"] for r in cases.values())
        print(f"{sweep}: {n}/{len(cases)} proven")
    if getattr(args, "update_baseline", False):
        for d in prune_baseline(results):
            print(f"baseline: dropped {d}")
    for sweep, cases in results.items():  # one line per case, the same in a shard and in the merge
        for case, r in sorted(cases.items()):
            print(f"  {sweep} {case:<30} {'PROVED' if r['proved'] else 'NOT PROVEN'}  {r.get('coverage', '')}")
    problems = [*missing, *verdict(results, load_baseline())]
    for p in problems:
        print(p)
    if args.no_ratchet:
        print("sweep: ratchet left to the aggregate")
        return 0
    print("sweep: as expected" if not problems else f"sweep: {len(problems)} unexpected")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
