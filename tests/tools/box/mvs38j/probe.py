#!/usr/bin/env python3
"""MVS 3.8J probe run (JCL oracle tier 2, #8414): the era-compatible IBM-written scenarios, run on the box.

Internal use only until counsel answers Q16: the results file is never published and no MVS number leaves the repo.

    probe.py cond [--printer FILE] [--out FILE] [--timeout S] [--dry]   # tests/equivalence/jcl/fixture CONDJOB / EVNJOB

For each scenario a deck is built from the fixture's own EXEC cards (their COND kept as written): a step whose `given` is
`{rc: n}` runs IDCAMS with `SET MAXCC=n`; `{abend: ...}` runs a program 3.8J cannot find (S806, the abend seen live; the
scenario names a code, but COND, EVEN and ONLY read an abend, not its code); a step with no `given` runs IDCAMS with
`SET MAXCC=0`, so a step the manual answer bypasses but the box starts shows as a disagreement. The deck is submitted
through `runner.py`; its `mvs38j-run` log is read back as run / bypass and set against two other columns: the manual answer
(`expect`, written from IBM's z/OS text before any evaluator) and the engine's `jcl_flow` answer. Three columns that are not
all equal are a finding for the register, never a change to `expect` or to the evaluator.
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))
import runner  # noqa: E402

from gitgalaxy.core import job_flow  # noqa: E402
from gitgalaxy.core.jcl_flow import JclFlow  # noqa: E402

FIXTURE = REPO / "tests" / "equivalence" / "jcl" / "fixture"
COND_JOBS = ("CONDJOB", "EVNJOB")  # IFJOB needs IF / THEN / ELSE, which 3.8J does not have (tier 1 only)
RESULTS = FIXTURE / "mvs38j_probe.json"
ABEND_PGM = "NOPGM001"  # not in any library: step abend S806 (IEF450I, no IEF142I)


def build_deck(rows, job, given):
    """The probe deck for one scenario: the job's EXEC cards with COND as written, each step's program set from `given`."""
    steps, cur = [], None
    for r in rows:
        if r["kind"] == "JOB":
            cur = r["name"]
        elif r["kind"] == "STEP" and cur == job:
            steps.append(r)
    out = [f"//{job:<8} JOB (ACCT),'PROBE',CLASS=A,MSGCLASS=A"]
    for st in steps:
        g = given.get(st["step_name"], {"rc": 0})
        cond = f",COND={st['cond']}" if st.get("cond") else ""
        if "abend" in g:
            out.append(f"//{st['step_name']:<8} EXEC PGM={ABEND_PGM}{cond}")
            continue
        out.append(f"//{st['step_name']:<8} EXEC PGM=IDCAMS{cond}")
        out += ["//SYSPRINT DD SYSOUT=A", "//SYSIN    DD *", f" SET MAXCC={g['rc']}", "/*"]
    return "\n".join(out) + "\n"


def observed(parsed, job, step_names):
    """run / bypass per step from a `runner.parse_log` result: IEF142I or an IEF450I abend means the step started."""
    jobs = [j for j in parsed["jobs"] if j["job"] == job]
    if not jobs:
        return None
    j = jobs[-1]
    started = {s["step"] for s in j["steps"] if s["executed"]} | {a["step"] for a in j["abends"]}
    return {n: ("run" if n in started else "bypass") for n in step_names}


def verdict(expect, engine, box):
    """agree: all three equal; otherwise name who differs from the manual answer."""
    if box is None:
        return "no-box-answer"
    if expect == engine == box:
        return "agree"
    odd = [n for n, v in (("engine", engine), ("box", box)) if v != expect]
    return "differ:" + "+".join(odd)


def run_scenario(sc, rows, printer, host, port, timeout):
    deck = build_deck(rows, sc["job"], sc["given"])
    with tempfile.TemporaryDirectory(prefix="mvs38j-probe-") as tmp:
        path = Path(tmp) / f"{sc['id']}.jcl"
        path.write_text(deck)
        before = Path(printer).stat().st_size if Path(printer).is_file() else 0
        runner.submit(path, host, port)
    if not runner.wait_for_job(printer, sc["job"], timeout, before):
        return None
    text = Path(printer).read_bytes()[before:].decode("utf-8", "backslashreplace")
    return runner.parse_log(text, sc["job"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("what", choices=["cond"])
    ap.add_argument("--printer")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=3505)
    ap.add_argument("--timeout", type=float, default=180)
    ap.add_argument("--out", default=str(RESULTS))
    ap.add_argument("--dry", action="store_true", help="print the decks, submit nothing")
    args = ap.parse_args(argv)
    doc = json.loads((FIXTURE / "scenarios.json").read_text(encoding="utf-8"))
    rows = job_flow.jcl_job_flow((FIXTURE / "FLOW.jcl").read_text(encoding="utf-8"))
    flow = JclFlow(rows)
    scs = [s for s in doc["scenarios"] if s["job"] in COND_JOBS]
    if args.dry:
        for sc in scs:
            print(f"* {sc['id']}\n{build_deck(rows, sc['job'], sc['given'])}")
        return 0
    if not args.printer:
        print("probe: --printer FILE is required (the 1403 file of a started box)", file=sys.stderr)
        return 2
    results = []
    for sc in scs:
        parsed = run_scenario(sc, rows, args.printer, args.host, args.port, args.timeout)
        names = list(sc["expect"])
        box = observed(parsed, sc["job"], names) if parsed else None
        engine = flow.run(sc["job"], sc["given"]).actions
        results.append(
            {
                "id": sc["id"],
                "job": sc["job"],
                "expect": sc["expect"],
                "engine": engine,
                "box": box,
                "verdict": verdict(sc["expect"], engine, box),
                "box_steps": parsed["jobs"][-1]["steps"] if parsed and parsed["jobs"] else None,
                "box_abends": parsed["jobs"][-1]["abends"] if parsed and parsed["jobs"] else None,
                "unparsed_ief": parsed["unparsed_ief"] if parsed else None,
            }
        )
        print(f"{sc['id']}: {results[-1]['verdict']}", flush=True)
    out = {
        "provenance": runner.PROVENANCE,
        "internal_only": "Q16: MVS 3.8J results are not published",
        "fixture": "FLOW.jcl / scenarios.json",
        "results": results,
    }
    Path(args.out).write_text(json.dumps(out, indent=1) + "\n")
    return 0 if all(r["verdict"] == "agree" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
