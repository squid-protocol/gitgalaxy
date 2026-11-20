#!/usr/bin/env python3
"""MVS 3.8J probe run (JCL oracle tier 2, #8414): the era-compatible IBM-written scenarios, run on the box.

Internal use only until counsel answers Q16: the results file is never published and no MVS number leaves the repo.

    probe.py cond [--printer FILE] [--out FILE] [--timeout S] [--dry]   # tests/equivalence/jcl/fixture CONDJOB / EVNJOB
    probe.py proc [--printer FILE] [--out FILE] [--timeout S] [--dry]   # tests/equivalence/jcl/proc SYMJOB / OVRJOB / PCJOB

For each scenario a deck is built from the fixture's own EXEC cards (their COND kept as written): a step whose `given` is
`{rc: n}` runs IDCAMS with `SET MAXCC=n`; `{abend: ...}` runs a program 3.8J cannot find (S806, the abend seen live; the
scenario names a code, but COND, EVEN and ONLY read an abend, not its code); a step with no `given` runs IDCAMS with
`SET MAXCC=0`, so a step the manual answer bypasses but the box starts shows as a disagreement. The deck is submitted
through `runner.py`; its `mvs38j-run` log is read back as run / bypass and set against two other columns: the manual answer
(`expect`, written from IBM's z/OS text before any evaluator) and the engine's `jcl_flow` answer. Three columns that are not
all equal are a finding for the register, never a change to `expect` or to the evaluator.

`proc` runs the PROC scenarios 3.8J can express (symbolics, EXEC / DD overrides, an added DD, an EXEC PARM / COND on the call;
no SET, JCLLIB, INCLUDE or nesting). The deck keeps each procedure's statements and the call's own overrides; every `PGM=` is
IEFBR14 and every DD keeps its DSN but is allocated NEW on SYSDA (DISP left to default, DELETE, so a symbol's expansion stays under column 72: IEF621I), so the log shows which DSN each ddname of each
step got (IEF237I ddname, IEF285I DSN, in step order) and IEF653I shows a symbol's substituted PARM. The box cannot show a
resolved PGM (replaced), a PARM that is not symbolic, or a COND (IEFBR14 ends 0 and the COND values here all run): those are
listed as `unobserved`, not compared.
"""

import argparse
import json
import re
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
from gitgalaxy.core.jcl_proc import resolve_job  # noqa: E402

FIXTURE = REPO / "tests" / "equivalence" / "jcl" / "fixture"
COND_JOBS = ("CONDJOB", "EVNJOB")  # IFJOB needs IF / THEN / ELSE, which 3.8J does not have (tier 1 only)
RESULTS = FIXTURE / "mvs38j_probe.json"
PROC_CASE = REPO / "tests" / "equivalence" / "jcl" / "proc"
PROC_RESULTS = PROC_CASE / "mvs38j_probe.json"
PROC_JOBS = ("SYMJOB", "OVRJOB", "PCJOB")  # SET / JCLLIB / INCLUDE / nested procedures are not in 3.8J (tier 1 only)
PROC_UNOBSERVED = [
    "pgm (every PGM= is IEFBR14)",
    "parm unless a symbolic",
    "cond (every step ends 0, every COND here runs)",
]
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


def proc_deck(lines, job, call):
    """(deck text, procedure steps with a symbolic PARM) for one call: the job's procedure, that call, its override DDs."""
    block, inside = [], False
    for ln in lines:
        f = ln.split()
        if len(f) > 1 and f[1] == "JOB" and not ln.startswith("//*"):
            inside = f[0] == f"//{job}"
        elif inside and not ln.startswith("//*") and not ln.startswith("// SET"):
            block.append(ln)
    out = [f"//{job:<8} JOB (ACCT),'PROBE',CLASS=A,MSGCLASS=A,MSGLEVEL=(1,1)"]
    in_proc, keep, sym, step = True, True, [], None
    for ln in block:
        f = ln.split()
        is_exec = len(f) > 2 and f[1] == "EXEC"
        if in_proc:
            if len(f) > 1 and f[1] == "PEND":
                in_proc = False
            elif is_exec:
                step = f[0][2:]
                if "PGM=" in f[2] and "&" in ln.partition("PARM=")[2]:
                    sym.append(step)
        elif is_exec:
            keep = f[0][2:] == call
        if not in_proc and not keep and f[1:2] != ["PEND"]:
            continue
        if is_exec:
            ln = re.sub(r"PGM=[A-Z0-9$#@]+", "PGM=IEFBR14", ln)
        elif f[1:2] == ["DD"] and "DSN=" in ln:
            dsn = re.search(r"DSN=([^,\s]+)", ln).group(1)
            ln = f"{f[0].ljust(max(9, len(f[0])))} DD DSN={dsn},UNIT=SYSDA,SPACE=(TRK,1)"
        out.append(ln)
    return "\n".join(out) + "\n", sym


_ALLOC = re.compile(r"IEF236I ALLOC\. FOR (\S+) (\S+) (\S+)")
_DDALLOC = re.compile(r"IEF237I\s+\S+\s+ALLOCATED TO (\S+)")
_SUBST = re.compile(r"IEF653I SUBSTITUTION JCL - PGM=\S+?,PARM='([^']*)'")
_DSNDISP = re.compile(r"IEF285I\s+(\S+)\s+(?:KEPT|DELETED|PASSED|CATALOGED|UNCATALOGED)")


def observe_proc(text, job):
    """{ 'CALL.PROCSTEP': {'dd': {ddname: dsn}} } from a job's printer text, plus the IEF653I PARM substitutions, in step order."""
    steps, order, subst = {}, [], []
    cur = None
    for line in text.splitlines():
        if m := _ALLOC.search(line):
            if m.group(1) != job:
                cur = None
                continue
            cur = f"{m.group(3)}.{m.group(2)}"
            steps[cur] = {"dd": [], "dsn": []}
            order.append(cur)
        elif cur and (m := _DDALLOC.search(line)):
            steps[cur]["dd"].append(m.group(1))
        elif m := _SUBST.search(line):
            subst.append(m.group(1))
        elif cur and (m := _DSNDISP.search(line)):
            steps[cur]["dsn"].append(m.group(1))
    return {k: {"dd": dict(zip(steps[k]["dd"], steps[k]["dsn"], strict=False))} for k in order}, subst


def proc_projection(steps, sym_keys, parms):
    """The compared view: each step's ddname -> DSN (in order), plus the PARM of a symbolic-PARM step."""
    out = {}
    for k, v in steps.items():
        out[k] = {"dd": list(v["dd"].items())}
        if k in sym_keys and parms.get(k) is not None:
            out[k]["parm"] = parms[k]
    return out


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


def proc_scenarios():
    doc = json.loads((PROC_CASE / "scenarios.json").read_text(encoding="utf-8"))
    libs = {lib: {m: "\n".join(ls) + "\n" for m, ls in members.items()} for lib, members in doc["libraries"].items()}
    return (
        doc,
        "\n".join(doc["flow_jcl"]) + "\n",
        libs,
        [s for s in doc["resolve"] if s["job"] in PROC_JOBS and "." in next(iter(s["expect"]))],
    )


def run_proc_scenario(sc, doc, printer, host, port, timeout):
    """Submit the scenario's deck; return (box projection, parsed log) or (None, None) when the job never ended."""
    deck, sym = proc_deck(doc["flow_jcl"], sc["job"], sc["call"])
    with tempfile.TemporaryDirectory(prefix="mvs38j-probe-") as tmp:
        path = Path(tmp) / f"{sc['id']}.jcl"
        path.write_text(deck)
        before = Path(printer).stat().st_size if Path(printer).is_file() else 0
        runner.submit(path, host, port)
    if not runner.wait_for_job(printer, sc["job"], timeout, before):
        return None, None
    text = Path(printer).read_bytes()[before:].decode("utf-8", "backslashreplace")
    steps, subst = observe_proc(text, sc["job"])
    keys = [f"{sc['call']}.{p}" for p in sym]
    return proc_projection(steps, set(keys), dict(zip(keys, subst, strict=False))), runner.parse_log(text, sc["job"])


def main_proc(args):
    doc, text, libs, scs = proc_scenarios()
    if args.dry:
        for sc in scs:
            print(f"* {sc['id']}\n{proc_deck(doc['flow_jcl'], sc['job'], sc['call'])[0]}")
        return 0
    if not args.printer:
        print("probe: --printer FILE is required (the 1403 file of a started box)", file=sys.stderr)
        return 2
    results = []
    for sc in scs:
        box, parsed = run_proc_scenario(sc, doc, args.printer, args.host, args.port, args.timeout)
        _, sym = proc_deck(doc["flow_jcl"], sc["job"], sc["call"])
        keys = {f"{sc['call']}.{p}" for p in sym}
        engine_all = resolve_job(text, libs, sc["job"])
        engine = proc_projection(
            {k: v for k, v in engine_all.items() if k in sc["expect"]},
            keys,
            {k: v.get("parm") for k, v in engine_all.items()},
        )
        expect = proc_projection(sc["expect"], keys, {k: v.get("parm") for k, v in sc["expect"].items()})
        job = parsed["jobs"][-1] if parsed and parsed["jobs"] else None
        ran = [(s["procstep"], s["step"], s["executed"], s["cond_code"]) for s in job["steps"]] if job else None
        results.append(
            {
                "id": sc["id"],
                "job": sc["job"],
                "call": sc["call"],
                "expect": expect,
                "engine": engine,
                "box": box,
                "verdict": verdict(expect, engine, box),
                "box_steps": [{"procstep": a, "step": b, "executed": c, "cond_code": d} for a, b, c, d in ran]
                if ran
                else None,
                "jcl_error": job["jcl_error"] if job else None,
                "unobserved": PROC_UNOBSERVED,
            }
        )
        print(f"{sc['id']}: {results[-1]['verdict']}", flush=True)
    out = {
        "provenance": runner.PROVENANCE,
        "internal_only": "Q16: MVS 3.8J results are not published",
        "fixture": "tests/equivalence/jcl/proc/scenarios.json (SYMJOB / OVRJOB / PCJOB)",
        "results": results,
    }
    Path(args.out if args.out != str(RESULTS) else PROC_RESULTS).write_text(json.dumps(out, indent=1) + "\n")
    return 0 if all(r["verdict"] == "agree" for r in results) else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("what", choices=["cond", "proc"])
    ap.add_argument("--printer")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=3505)
    ap.add_argument("--timeout", type=float, default=180)
    ap.add_argument("--out", default=str(RESULTS))
    ap.add_argument("--dry", action="store_true", help="print the decks, submit nothing")
    args = ap.parse_args(argv)
    if args.what == "proc":
        return main_proc(args)
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
