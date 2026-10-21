#!/usr/bin/env python3
r"""
#4047 / #4024: mutation testing of the CICS-crucible ports.

`tests/tools/mutation.py` mutates an equivalence case's port and proves each mutant with `equivalence.py`. The 17
crucible ports (tests/cics_crucible/ports/<case>/<PROGRAM>/overlay) are proven by a different harness: the crucible
runner's java-ported and java-facade sides (#4343: the facade bodies run only on the second), against the hand-written, IBM-doc-cited expected event logs. This tool uses the same
mutants (`mutation.all_mutants`, the same operators and seeded sample) and proves each one with that runner:

    python tests/cics_crucible.py --cases <case> --sides java-ported java-facade --overlay <mutant> --program <PROGRAM>

Verdicts, as in mutation.py:
  killed     the runner says "not proven"; `killed_by` names the scenarios that failed
  survived   every scenario that runs the program still passes
  stillborn  the ported project does not compile (the compiler caught it, not the proof): counts for nothing
  timeout    over the time limit: caught, but by the clock

    python tests/tools/mutation_crucible.py run --work DIR [--only CASE/PROG,...] [--sample 40] [--seed 0] [--jobs 4]
    python tests/tools/mutation_crucible.py report DIR      # DIR/<case>/<PROG>/mutation.md again
    python tests/tools/mutation_crucible.py compare A B [--require-agree N]   # two runs of one port: same verdicts?

#4047, fast mode (the default): the baseline run generates the case's Java project once and every mutant copies it,
lays its overlay and compiles (`cics_crucible.py --forge-cache`), instead of refactoring and generating again. Both
sides still run every scenario, so a mutant's verdict and `killed_by` are the ones `--full` gives (a JVM per side,
all of the side's scenarios in it); `compare` is the gate that says so for a sample (`--require-agree`).

#4049, the test-strengthening loop: `--strengthened` proves every mutant against the case's strengthened scenarios
too (tests/cics_crucible/strengthened, their logs derived from the COBOL), and `--case-gaps [RESULTS]` runs only
the survivors the committed results (docs/language_status/mutation_scores.json) triaged as case gaps -- the
mutants the new scenarios are meant to kill (`mutation_scores.py build --rejudged` folds their verdicts back in).

Each port's DIR/<case>/<PROG>/mutation.json has mutation.py's shape, so `mutation_scores.py` reads both.
Needs CICS_CRUCIBLE_PATH (a checkout at the pin, tests/_cics_crucible_pin.py).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import mutation as mu  # noqa: E402
from _cics_crucible_pin import PINNED_REF  # noqa: E402

PORTS = REPO / "tests" / "cics_crucible" / "ports"
RUNNER = HERE / "cics_crucible.py"
NOT_COMPILED = "ported project does not compile"
# A port that ships the det translator's runtime (PCIMMA: cobolrt/*.java, 6000 mutants) is judged on its own service
# code: the runtime is shared by every det port and proven by the det-port cells, so its mutants would fill the
# sample with code this program's scenarios never call.
SHARED_RUNTIME = "cobolrt/"


def ports(only: list[str] | None) -> list[tuple[str, str, Path]]:
    """(case, program, overlay) of every committed crucible port, or of the `only` ones (CASE/PROG or PROG)."""
    out = []
    for overlay in sorted(PORTS.glob("*/*/overlay")):
        case, prog = overlay.parent.parent.name, overlay.parent.name
        if only and not ({f"{case}/{prog}", prog} & set(only)):
            continue
        out.append((case, prog, overlay))
    return out


def verdict(rc: int | None, report: dict | None) -> tuple[str, list[str]]:
    """A mutant's verdict from the runner's exit code and report.json: (verdict, the scenarios that killed it)."""
    if rc is None:
        return "timeout", []
    if rc == 0 and report and report.get("proven"):
        return "survived", []
    cells = (report or {}).get("cells", {})
    if cells and all(c.get("kind") == NOT_COMPILED for c in cells.values()):
        return "stillborn", []
    failed = [name.split("/")[1] for name, c in sorted(cells.items()) if c.get("status") != "pass"]
    return "killed", failed or ["runner"]


STRENGTHENED = False  # #4049: --strengthened


def prove_command(case: str, prog: str, overlay: Path, out: Path, cache: Path | None = None) -> list[str]:
    """The crucible runner's command for one proof; `cache`: the fast mode's generated-project directory."""
    return [sys.executable, str(RUNNER), "--cases", case, "--sides", "java-ported", "java-facade", "--overlay", str(overlay),
            "--program", prog, "--report-dir", str(out), *(["--strengthened"] if STRENGTHENED else []),
            *(["--forge-cache", str(cache)] if cache is not None else [])]  # fmt: skip


def prove(case: str, prog: str, overlay: Path, out: Path, timeout: float,
          cache: Path | None = None) -> tuple[str, list[str], float]:  # fmt: skip
    out.mkdir(parents=True, exist_ok=True)
    cmd = prove_command(case, prog, overlay, out, cache)
    t0 = time.monotonic()
    with open(out / "log.txt", "w", encoding="utf-8") as log:
        try:
            rc: int | None = subprocess.run(  # noqa: S603
                cmd, cwd=REPO, stdout=log, stderr=subprocess.STDOUT, timeout=timeout
            ).returncode
        except subprocess.TimeoutExpired:
            rc = None
    rp = out / "report.json"
    report = json.loads(rp.read_text(encoding="utf-8")) if rp.exists() else None
    v, by = verdict(rc, report)
    return v, by, time.monotonic() - t0


def run_port(case: str, prog: str, overlay: Path, work: Path, args) -> dict:
    pw = work / case / prog
    if pw.exists():
        shutil.rmtree(pw)
    cache = None if args.full else pw / "forge-cache"  # the baseline fills it, the mutants copy it
    v, _, base_s = prove(case, prog, overlay, pw / "baseline", 900, cache)
    if v != "survived":
        raise SystemExit(f"{case}/{prog}: the committed port is not proven ({pw / 'baseline'}); nothing to measure")
    every = [m for m in mu.all_mutants(overlay, args.ops) if not m.file.startswith(SHARED_RUNTIME)]
    chosen = mu.sample(every, args.sample, args.seed)
    if args.case_gaps:  # #4049: only the case-gap survivors of the committed results
        import strengthen

        ids = strengthen.case_gaps(args.case_gaps, f"crucible:{case}", prog)
        chosen = [m for m in every if m.id in ids]
    limit = max(120.0, 3 * base_s)
    print(f"{case}/{prog}: {len(every)} mutants, {len(chosen)} chosen; baseline {base_s:.0f} s", flush=True)

    def one(m) -> dict:
        md = mu.write_mutant(overlay, m, pw / "mutants" / m.id)
        v, by, s = prove(case, prog, md, pw / "proofs" / m.id, limit, cache)
        if v != "survived" and not args.keep:
            shutil.rmtree(pw / "proofs" / m.id, ignore_errors=True)
            shutil.rmtree(md, ignore_errors=True)
        return {"id": m.id, "op": m.op, "file": m.file, "line": m.line, "before": m.before, "after": m.after,
                "verdict": v, "killed_by": by, "seconds": round(s, 1)}  # fmt: skip

    t0 = time.monotonic()
    with ThreadPoolExecutor(args.jobs) as pool:
        results = list(pool.map(one, chosen))
    res = {"case": f"crucible:{case}", "program": prog, "mutants": len(every), "chosen": len(chosen),
           "seed": args.seed, "mode": "full" if args.full else "fast", "seconds": round(time.monotonic() - t0), "baseline_seconds": round(base_s, 1),
           "coverage": f"cics-crucible {PINNED_REF} java-ported + java-facade scenarios (100% paragraphs and branches, #4023)",
           "results": sorted(results, key=lambda r: (r["file"], r["line"], r["id"]))}  # fmt: skip
    (pw / "mutation.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    (pw / "mutation.md").write_text(mu.mutation_md(res), encoding="utf-8")
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--work", required=True, type=Path)
    r.add_argument("--only", help="CASE/PROG or PROG, comma-separated (default: every crucible port)")
    r.add_argument("--sample", type=int, help="at most N mutants per port, spread over the operators")
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--jobs", type=int, default=4)
    r.add_argument("--ops", default=",".join(mu.OPERATORS))
    r.add_argument("--full", action="store_true", help="#4047: generate the project again for every mutant (the "
                   "reference `compare` judges fast mode against); the default copies the baseline's")  # fmt: skip
    r.add_argument("--keep", action="store_true", help="keep killed mutants' proof directories too")
    r.add_argument("--strengthened", action="store_true", help="#4049: prove against the strengthened scenarios too")
    r.add_argument("--case-gaps", type=Path, nargs="?", const=REPO / "docs" / "language_status" / "mutation_scores.json",
                   metavar="RESULTS", help="#4049: run only the survivors RESULTS triaged as case gaps")  # fmt: skip
    r.add_argument("--record", action="store_true", help="#4048: each port's run becomes its committed score "
                   "(mutation_scores.json, its survivors' triage kept) and its evidence record's `mutation`")  # fmt: skip
    r.add_argument("--triage", type=Path, nargs="*", default=[], help="with --record: triage files for new survivors")
    rep = sub.add_parser("report")
    rep.add_argument("work", type=Path)
    cp = sub.add_parser("compare", help="two runs of one port (fast and --full): do their verdicts agree?")
    cp.add_argument("a", type=Path, help="a port's run directory (DIR/<case>/<PROG>)")
    cp.add_argument("b", type=Path)
    cp.add_argument("--require-agree", type=int, metavar="N", help="a gate: exit 1 unless both runs judged at least N "
                    "mutants and none of them differ")  # fmt: skip
    args = ap.parse_args(argv)
    if args.cmd == "compare":
        loaded = [json.loads((w / "mutation.json").read_text(encoding="utf-8")) for w in (args.a, args.b)]
        result = mu.compare(*loaded)
        print(json.dumps(result, indent=2))
        return 0 if mu.agreement_gate(result, args.require_agree) else 1
    if args.cmd == "report":
        for mj in sorted(args.work.glob("*/*/mutation.json")):
            mj.with_suffix(".md").write_text(mu.mutation_md(json.loads(mj.read_text(encoding="utf-8"))), "utf-8")
        return 0
    if args.record and args.case_gaps:
        raise SystemExit("--record scores the whole sample: --case-gaps re-judges some mutants (mutation_scores.py "
                         "build --rejudged)")  # fmt: skip
    if not os.environ.get("CICS_CRUCIBLE_PATH"):
        raise SystemExit("set CICS_CRUCIBLE_PATH to a cics-crucible checkout at the pin (tests/_cics_crucible_pin.py)")
    args.ops = {o.strip().upper() for o in args.ops.split(",") if o.strip()}
    global STRENGTHENED
    STRENGTHENED = args.strengthened
    only = [x.strip() for x in args.only.split(",")] if args.only else None
    for case, prog, overlay in ports(only):
        res = run_port(case, prog, overlay, args.work, args)
        caught = sum(r["verdict"] in ("killed", "timeout") for r in res["results"])
        judged = caught + sum(r["verdict"] == "survived" for r in res["results"])
        print(f"{case}/{prog}: {caught}/{judged} caught in {res['seconds']} s", flush=True)
        if args.record:
            import mutation_scores

            mutation_scores.record_run(args.work / case / prog, args.triage)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
