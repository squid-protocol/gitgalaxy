#!/usr/bin/env python3
"""MVS 3.8J probe run (JCL oracle tier 2, #8414): the era-compatible IBM-written scenarios, run on the box.

Internal use only until counsel answers Q16: the results file is never published and no MVS number leaves the repo.

    probe.py cond [--printer FILE] [--out FILE] [--timeout S] [--dry]   # tests/equivalence/jcl/fixture CONDJOB / EVNJOB
    probe.py proc [--printer FILE] [--out FILE] [--timeout S] [--dry]   # tests/equivalence/jcl/proc SYMJOB / OVRJOB / PCJOB
    probe.py flow [--printer FILE] [--out FILE] [--timeout S] [--dry]   # tests/equivalence/jcl/dataflow (&& temps, DISP, DD concat)
    probe.py gdg  [--printer FILE] [--out FILE] [--timeout S] [--dry]   # tests/equivalence/jcl/gdg (relative generations, catalog after)

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
from gitgalaxy.core.jcl_dataflow import resolve_dataflow  # noqa: E402
from gitgalaxy.core.jcl_flow import JclFlow  # noqa: E402
from gitgalaxy.core.jcl_gdg import JclGdgRefused, resolve_gdg  # noqa: E402
from gitgalaxy.core.jcl_proc import expand_flow_rows, resolve_job  # noqa: E402

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
DATAFLOW = REPO / "tests" / "equivalence" / "jcl" / "dataflow"
FLOW_RESULTS = DATAFLOW / "mvs38j_probe.json"
FLOW_SKIP = ("SYSJOB",)  # SYSOUT classes and OUTPUT statements: 3.8J has no OUTPUT statement (tier 1 only)
FLOW_UNOBSERVED = [
    "read order of a concatenation as a program reads it (IEFBR14 reads nothing; the order is that of the allocation messages)",
    "a SYSOUT class (SYSJOB is not run)",
    "the DISP of a permanent dataset (only the names are compared)",
]
GDG_CASE = REPO / "tests" / "equivalence" / "jcl" / "gdg"
GDG_RESULTS = GDG_CASE / "mvs38j_probe.json"
GDG_BASES = ("PAY.GDG", "AUD.GDG")  # every base the scenarios name; each setup deck clears both
GDG_PURGE = range(
    1, 13
)  # absolute generations a scenario can leave behind (the largest number any scenario reaches is 10)
GDG_UNOBSERVED = [
    "what a program reads (every PGM= is IEFBR14): the allocation messages name each DD's generation, nothing is read",
    "the fate of a generation rolled off at LIMIT (SCRATCH / NOSCRATCH): only catalog membership is compared",
    "the deferred roll-in state of a NEW,KEEP generation: the box shows it absent from the catalog (the manual's state is not a 3.8J column)",
    "a system-managed group (assumption A5): 3.8J has a VSAM-catalog GDG with a model DSCB, set up by the probe",
    "a DD naming the base itself (DELAFTER, DELFIRST): the box expands it to every generation (a nameless IEF237I per generation); the model DSCB is not shown",
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


_TEMP_SYS = re.compile(r"SYS\d{5}\.T\d{6}\.RA000\.(?P<job>[A-Z0-9#$@]+)\.(?P<tail>.+)$")
_PROJ_DISP = re.compile(r"IEF285I\s+(\S.*?)\s+(KEPT|DELETED|PASSED|CATALOGED|UNCATALOGED)(?:\s+\*-+\d*)?\s*$")
_DMY = re.compile(r"IEF237I\s+DMY\s+ALLOCATED TO (\S+)")


UCAT = "PUB001."  # alias to a user catalog (mvs01.jcl): a master-catalog entry would wait on IEC301A for the SYSPROG password


# 3.8J would not allocate a generation here (IEF218I PATTERN DSCB RECORD NOT FOUND, four model-DSCB placements tried), so a
# `BASE(0)` reference is probed as the plain dataset `BASE.GSTAND`: the concatenation order is tested, the generation is not.
GDG_REF = re.compile(r"\((?:0|[+-]\d+)\)$")
GDG_STANDIN = ".GSTAND"


def user_cat(ln):
    """A DD line with each permanent DSN= moved under the user-catalog alias (temporaries and NULLFILE stay)."""
    return re.sub(r"DSN=(?!&&|NULLFILE\b)([^,\s]+)", lambda m: "DSN=" + UCAT + GDG_REF.sub(GDG_STANDIN, m.group(1)), ln)


_CATALOGS = (
    "UCPUB000",
    "UCPUB001",
    "UCMVS000",
    "SYS1.VSAM.MASTER.CATALOG",
)  # IEF285I lists the catalog a DD went through


def flow_dsn(name, job):
    """A DSN as the box prints it, in the scenario's terms: a system-named temporary `SYSyyddd.Thhmmss.RA000.JOB.NAME.Hnn`
    is `&&NAME`, one with no name (a DD with no DSN) is `&&(system-named)`, a permanent name is itself."""
    m = _TEMP_SYS.match(name)
    if not m or m.group("job") != job:
        name = name[len(UCAT) :] if name.startswith(UCAT) else name
        return name[: -len(GDG_STANDIN)] + "(0)" if name.endswith(GDG_STANDIN) else name
    tail = re.sub(r"\.H\d+$", "", m.group("tail"))
    return "&&(system-named)" if re.fullmatch(r"R\d+", tail) else f"&&{tail}"


def flow_permanents(lines, job):
    """(dsns the job reads that must exist, dsns the job creates) from a job's own DD statements, as the box deck names them."""
    reads, makes = [], []
    for ln in _job_block(lines, job):
        m = re.search(r"DSN=([^,\s]+)", ln)
        if not m or ln[2:].split()[:1] == ["EXEC"] or m.group(1).startswith("&&") or m.group(1) == "NULLFILE":
            continue
        dsn = GDG_REF.sub(GDG_STANDIN, m.group(1))
        if "DISP=(NEW" in ln.replace(" ", "") and "DUMMY" not in ln:
            makes.append(dsn)
        elif "DISP=" in ln and "DUMMY" not in ln:
            reads.append(dsn)
    return sorted(set(reads) - set(makes)), sorted(set(makes))


def _job_block(lines, job):
    out, inside = [], False
    for ln in lines:
        f = ln.split()
        if len(f) > 1 and f[1] == "JOB" and not ln.startswith("//*"):
            inside = f[0] == f"//{job}"
        elif inside and not ln.startswith("//*"):
            out.append(ln)
    return out


def flow_deck(lines, job, given):
    """The probe deck for one data-flow job: its own statements, every PGM= IEFBR14 (IDCAMS `SET MAXCC=n` for a step whose
    `given` rc is not 0, so a COND on it reads that code), MSGLEVEL=(1,1) so the log lists each DSN; MSGCLASS=A (the printer)."""
    out = [f"//{job:<8} JOB (ACCT),'PROBE',CLASS=A,MSGCLASS=A,MSGLEVEL=(1,1)"]
    for ln in _job_block(lines, job):
        f = ln.split()
        if len(f) > 2 and f[1] == "EXEC":
            rc = given.get(f[0][2:], {}).get("rc", 0)
            pgm = "IDCAMS" if rc else "IEFBR14"
            out.append(re.sub(r"PGM=[A-Z0-9$#@]+", f"PGM={pgm}", ln))
            if rc:
                out += ["//SYSPRINT DD SYSOUT=A", "//SYSIN    DD *", f" SET MAXCC={rc}", "/*"]
        else:
            out.append(user_cat(ln))
            if "DISP=(NEW" in ln.replace(" ", "") and "UNIT=" not in ln and "DUMMY" not in ln:
                # 3.8J allocates a new dataset only with a UNIT; the scenario's z/OS text leaves it to SMS defaults
                out[-1] += ","
                out.append("//            UNIT=SYSDA,SPACE=(TRK,1)")
    return "\n".join(out) + "\n"


def flow_support_decks(lines, job):
    """(preamble, postamble) decks: create what the job reads, delete all of it and what the job made afterwards, so a rerun
    starts from the same catalog. "" when there is nothing to do."""
    reads, makes = flow_permanents(lines, job)
    jcl = lambda name: [f"//{name:<8} JOB (ACCT),'PROBE',CLASS=A,MSGCLASS=A,MSGLEVEL=(1,1)"]  # noqa: E731
    pre, post = jcl("PREP"), jcl("POST")
    for i, dsn in enumerate(reads):
        pre += [
            f"//M{i:<7} EXEC PGM=IEFBR14",
            f"//DD       DD DSN={UCAT}{dsn},DISP=(MOD,CATLG),",  # past column 71 is IEF618I
            "//            UNIT=SYSDA,SPACE=(TRK,1)",
        ]
    # IDCAMS, not DISP=(OLD,DELETE): a missing dataset is cc 8 here, a JCL error that fails the whole job there
    gone = reads + makes
    if gone:
        post += ["//GONE     EXEC PGM=IDCAMS", "//SYSPRINT DD SYSOUT=A", "//SYSIN    DD *"]
        post += [f" DELETE {UCAT}{d}" for d in gone] + [" SET MAXCC=0", "/*"]
    return ("\n".join(pre) + "\n" if len(pre) > 1 else ""), ("\n".join(post) + "\n" if len(post) > 1 else "")


_FALLOC = re.compile(r"IEF236I ALLOC\. FOR (\S+) (\S+)(?: (\S+))?")
JOB_END = "(job end)"  # IEF285I lines the system prints after the last step's IEF374I: not a step's own dispositions


def observe_flow(text, job):
    """{step: {"dsn": [names in log order], "disp": [dispositions], "dummy": [ddnames]}} from a job's printer text."""
    steps, order, cur = {}, [], None
    for line in text.splitlines():
        if m := _FALLOC.search(line):
            if m.group(1) != job:
                cur = None
                continue
            cur = m.group(3) or m.group(2)  # a procedure call has two names, the calling step last
            steps[cur] = {"dsn": [], "disp": [], "dummy": []}
            order.append(cur)
            steps.pop(JOB_END, None)
        elif "IEF374I" in line:
            cur = JOB_END
            steps.setdefault(JOB_END, {"dsn": [], "disp": [], "dummy": []})
        elif cur and (m := _DMY.search(line)):
            steps[cur]["dummy"].append(m.group(1))
        elif cur and (m := _PROJ_DISP.search(line)):
            if m.group(1) in _CATALOGS:
                continue
            steps[cur]["dsn"].append(flow_dsn(m.group(1), job))
            steps[cur]["disp"].append(m.group(2))
    out = {k: steps[k] for k in order}
    if JOB_END in steps:
        out[JOB_END] = steps[JOB_END]
    return out


def flow_expected(engine_answers, engine_temps):
    """The comparable view from an `expect` / `temporaries` pair: per step the datasets in DD order and its dummy ddnames,
    plus each temporary's creator step, receiving steps (in order) and the step after which it was deleted."""
    per = {}
    for key, ans in engine_answers.items():
        step, dd = key.split(".", 1)
        v = per.setdefault(step, {"dsn": [], "dummy": []})
        if ans.get("dummy"):
            v["dummy"].append(dd)
        elif "datasets" in ans:
            v["dsn"] += list(ans["datasets"])
        elif ans.get("temporary"):
            v["dsn"].append("&&(system-named)")
    temps = {
        n: {
            "created": t["created_by"].split(".")[0],
            "received": [r.split(".")[0] for r in t["received_by"]],
            "deleted_after": t["deleted_after"],
        }
        for n, t in engine_temps.items()
    }
    return per, temps


def flow_box_temps(steps):
    """Each `&&name` the box showed: the first step that listed it (its creator), the later ones (receivers), and the step whose
    line says DELETED (`JOB` when no line does)."""
    temps = {}
    for step, v in steps.items():
        for dsn, disp in zip(v["dsn"], v["disp"], strict=False):
            if not dsn.startswith("&&") or dsn == "&&(system-named)":
                continue
            t = temps.setdefault(dsn, {"created": step, "received": [], "deleted_after": "JOB"})
            if step != t["created"]:
                t["received"].append(step)
            if disp == "DELETED":
                t["deleted_after"] = step
    return temps


def flow_scenarios():
    doc = json.loads((DATAFLOW / "scenarios.json").read_text(encoding="utf-8"))
    return doc, [s for s in doc["scenarios"] if s["job"] not in FLOW_SKIP]


def submit_and_read(deck, name, printer, host, port, timeout):
    with tempfile.TemporaryDirectory(prefix="mvs38j-probe-") as tmp:
        path = Path(tmp) / f"{name}.jcl"
        path.write_text(deck)
        before = Path(printer).stat().st_size if Path(printer).is_file() else 0
        runner.submit(path, host, port)
    if not runner.wait_for_job(printer, name, timeout, before):
        return None
    return Path(printer).read_bytes()[before:].decode("utf-8", "backslashreplace")


def main_flow(args):
    doc, scs = flow_scenarios()
    rows = job_flow.jcl_job_flow("\n".join(doc["flow_jcl"]) + "\n")
    if args.dry:
        for sc in scs:
            pre, post = flow_support_decks(doc["flow_jcl"], sc["job"])
            print(f"* {sc['id']}\n{pre}{flow_deck(doc['flow_jcl'], sc['job'], sc['given'])}{post}")
        return 0
    if not args.printer:
        print("probe: --printer FILE is required (the 1403 file of a started box)", file=sys.stderr)
        return 2
    results = []
    for sc in scs:
        pre, post = flow_support_decks(doc["flow_jcl"], sc["job"])
        if pre:
            submit_and_read(pre, "PREP", args.printer, args.host, args.port, args.timeout)
        text = submit_and_read(
            flow_deck(doc["flow_jcl"], sc["job"], sc["given"]),
            sc["job"],
            args.printer,
            args.host,
            args.port,
            args.timeout,
        )
        if post:
            submit_and_read(post, "POST", args.printer, args.host, args.port, args.timeout)
        flow = JclFlow(rows).run(sc["job"], sc["given"])
        eng = resolve_dataflow(rows, sc["job"], flow, sc.get("msgclass"))
        expect = flow_expected(sc["expect"], sc["temporaries"])
        engine = flow_expected(*eng)
        seen = observe_flow(text, sc["job"]) if text else None
        box = None
        if seen is not None:
            run = {s: v for s, v in seen.items() if s != JOB_END}
            # a step with no DD of interest (B1) is not an answer; one the scenario names, or one that shows datasets, is
            keep = {s: v for s, v in run.items() if s in expect[0] or v["dsn"] or v["dummy"]}
            box = ({s: {"dsn": v["dsn"], "dummy": v["dummy"]} for s, v in keep.items()}, flow_box_temps(run))
        results.append(
            {
                "id": sc["id"],
                "job": sc["job"],
                "expect": {"steps": expect[0], "temporaries": expect[1]},
                "engine": {"steps": engine[0], "temporaries": engine[1]},
                "box": {"steps": box[0], "temporaries": box[1]} if box else None,
                "box_dispositions": {s: list(zip(v["dsn"], v["disp"], strict=False)) for s, v in seen.items()}
                if seen
                else None,
                "verdict": verdict(expect, engine, box),
                "unobserved": FLOW_UNOBSERVED,
                "substituted": {"PAY.GDG(0)": "PAY.GDG.GSTAND (a plain dataset)"}
                if "GDG" in json.dumps(sc["expect"])
                else None,
            }
        )
        print(f"{sc['id']}: {results[-1]['verdict']}", flush=True)
    out = {
        "provenance": runner.PROVENANCE,
        "internal_only": "Q16: MVS 3.8J results are not published",
        "fixture": "tests/equivalence/jcl/dataflow/scenarios.json (every job but SYSJOB)",
        "results": results,
    }
    Path(args.out if args.out != str(RESULTS) else FLOW_RESULTS).write_text(json.dumps(out, indent=1) + "\n")
    return 0 if all(r["verdict"] == "agree" for r in results) else 1


# ---- gdg: relative generations ---------------------------------------------------------------------------------------------
# 3.8J's GDG is a VSAM-catalog group: IDCAMS DEFINE GDG, plus a model DSCB (a dataset named exactly the base, on the volume
# the catalog entries use). A generation is `BASE.GnnnnV00`; a scenario's catalog is built by creating each absolute
# generation DISP=(NEW,CATLG), so its numbers are the scenario's own. `(+n)` generations are pinned to the model's volume
# (IEF218I PATTERN DSCB RECORD NOT FOUND otherwise). IEHPROGM SCRATCH, not IDCAMS, clears the VTOC (DELETE ... GDG FORCE
# does not scratch the generations); it needs `VOL=3390=PUB001`.
_GEN_NAME = re.compile(r"^(?P<base>.+)\.G(?P<n>\d{4})V00$")
_GDG_REL = re.compile(r"\((?:0|[+-]\d+)\)$")
_IDCAMS = ("//{n:<8} EXEC PGM=IDCAMS", "//SYSPRINT DD SYSOUT=A", "//SYSIN    DD *")
_DD_CARD = re.compile(r"^//(?P<name>\S*)\s+DD\s+(?P<rest>.*)$")


def gdg_skip(lines, job):
    """Why a scenario's job is not run on 3.8J, or None: GDGBIAS is a post-3.8J JOB keyword; RESTART is a later slice."""
    head, at = "", next((i for i, ln in enumerate(lines) if ln.startswith(f"//{job} ") and " JOB " in ln), None)
    while at is not None and at < len(lines):  # the JOB card and its continuation lines
        head += lines[at].rstrip() if not head else lines[at][2:].strip()
        if not lines[at].rstrip().endswith(","):
            break
        at += 1
    if "GDGBIAS=" in head:
        return "GDGBIAS is a z/OS JOB keyword (not in 3.8J)"
    if "RESTART=" in head:
        return "restart is a later slice (#8413 restart; the JES2 restart scenarios are not run here)"
    return None


def gdg_catalog(doc, sc):
    return doc_by_id(doc)[sc["catalog_from"]]["catalog_after"] if "catalog_from" in sc else sc["catalog"]


def doc_by_id(doc):
    return {s["id"]: s for s in doc["scenarios"]}


def _gdg_cards(lines, job):
    """The job's cards with continuation lines joined (`DD a,` + `//   b` -> `DD a,b`)."""
    cards = []
    for ln in _job_block(lines, job):
        if cards and cards[-1].endswith(",") and ln.startswith("//") and ln[2:3] == " " and ln[2:].strip():
            cards[-1] += ln[2:].strip()
        else:
            cards.append(ln)
    return cards


def gdg_job_deck(lines, job, given):
    """The probe deck for one GDG job: its steps with every PGM= IEFBR14 (a `given` abend runs a missing program, a rc runs
    IDCAMS `SET MAXCC`), each DD re-written as DSN under the user catalog, DISP as coded, a new generation pinned to PUB001."""
    out = [f"//{job:<8} JOB (ACCT),'PROBE',CLASS=A,MSGCLASS=A,MSGLEVEL=(1,1)"]
    for card in _gdg_cards(lines, job):
        f = card.split()
        if len(f) > 2 and f[1] == "EXEC":
            g = given.get(f[0][2:]) or next((v for k, v in given.items() if k.endswith("." + f[0][2:])), {})
            pgm = ABEND_PGM if "abend" in g else "IDCAMS" if g.get("rc") else "IEFBR14"
            out.append(re.sub(r"PGM=[A-Z0-9$#@]+", f"PGM={pgm}", card))
            if pgm == "IDCAMS":
                out += ["//SYSPRINT DD SYSOUT=A", "//SYSIN    DD *", f" SET MAXCC={g['rc']}", "/*"]
        elif m := _DD_CARD.match(card):
            dsn = re.search(r"DSN=([^,\s]+)", m["rest"])[1]
            disp = re.search(r"DISP=(\([^)]*\)|[A-Z]+)", m["rest"])[1]
            out.append(f"//{m['name']:<8} DD DSN={UCAT}{dsn},DISP={disp}")
            if _GDG_REL.search(dsn) and re.match(r"\((NEW|MOD)", disp) and not dsn.endswith("(0)"):
                out[-1] += ","
                out.append(f"//            UNIT=SYSDA,VOL=SER={UCAT[:-1]},SPACE=(TRK,1)")
        elif card.startswith("//*"):
            continue
        else:
            out.append(card)  # PROC / PEND
    return "\n".join(out) + "\n"


def gdg_setup_deck(catalog):
    """Clear both bases (IDCAMS DELETE, then IEHPROGM SCRATCH of the model and every generation a scenario can leave), then
    define each base in `catalog` with its LIMIT / EMPTY, its model DSCB, and each cataloged absolute generation."""
    out = ["//GSETUP   JOB (ACCT),'PROBE',CLASS=A,MSGCLASS=A,MSGLEVEL=(1,1)"]
    out += [x.format(n="DEL") for x in _IDCAMS]
    out += [f" DELETE {UCAT}{b} GDG FORCE PURGE" for b in GDG_BASES]
    out += [" SET MAXCC=0", "/*", "//SCR      EXEC PGM=IEHPROGM", "//SYSPRINT DD SYSOUT=A"]
    out += ["//DD1      DD UNIT=SYSDA,VOL=SER=PUB001,DISP=OLD", "//SYSIN    DD *"]
    for b in GDG_BASES:
        out += [f" SCRATCH DSNAME={UCAT}{b},VOL=3390=PUB001"]
        out += [f" SCRATCH DSNAME={UCAT}{b}.G{n:04d}V00,VOL=3390=PUB001" for n in GDG_PURGE]
    out.append("/*")
    for b, c in catalog.items():
        out += [x.format(n="DEF" + b[:3]) for x in _IDCAMS]
        out += [
            f" DEFINE GDG (NAME({UCAT}{b}) LIMIT({c['limit']}) {'EMPTY' if c.get('empty') else 'NOEMPTY'} SCRATCH)",
            "/*",
        ]
        out += [f"//MOD{b[:3]}   EXEC PGM=IEFBR14", f"//MODEL    DD DSN={UCAT}{b},DISP=(,KEEP),UNIT=SYSDA,"]
        out += [
            "//            VOL=SER=PUB001,SPACE=(TRK,0),",
            "//            DCB=(RECFM=FB,LRECL=80,BLKSIZE=80,DSORG=PS)",
        ]
        for n in c["generations"]:
            out += [f"//G{b[:2]}{n:<5} EXEC PGM=IEFBR14", f"//A        DD DSN={UCAT}{b}.G{n:04d}V00,DISP=(NEW,CATLG),"]
            out.append("//            UNIT=SYSDA,VOL=SER=PUB001,SPACE=(TRK,1)")
    return "\n".join(out) + "\n"


def gdg_list_deck():
    out = ["//GLIST    JOB (ACCT),'PROBE',CLASS=A,MSGCLASS=A,MSGLEVEL=(1,1)"]
    for i, b in enumerate(GDG_BASES):
        out += [x.format(n=f"L{i}") for x in _IDCAMS]
        out += [f" LISTCAT ENTRIES({UCAT}{b}) ALL", " SET MAXCC=0", "/*"]
    return "\n".join(out) + "\n"


def observe_gdg_catalog(text):
    """{base: {"limit": n, "generations": [absolute numbers, oldest first]}} from a LISTCAT listing; a base not found is absent."""
    out = {}
    for m in re.finditer(r"GDG BASE -+ (\S+)(.*?)\n[ \t]*\n", text, re.S):
        base = m[1][len(UCAT) :]
        lim = re.search(r"LIMIT-+(\d+)", m[2])
        out[base] = {
            "limit": int(lim[1]) if lim else None,
            "generations": [int(n) for n in re.findall(r"NONVSAM--\S+\.G(\d{4})V00", m[2])],
        }
    return out


_GDG_DISP = re.compile(
    r"IEF28[57]I\s+(\S.*?)\s+(KEPT|DELETED|PASSED|CATALOGED|UNCATALOGED|NOT RECTLGD)(?:\s+\d+)?(?:\s+\*-+\d*)?\s*$"
)  # IEF287I "NOT RECTLGD 2" = a DISP=(MOD,CATLG) on a dataset the catalog already holds


def observe_gdg(text, job):
    """({"STEP.DDNAME": absolute generation} for each single-generation DD the job allocated, {step: [(dd, dsn, disposition)]})
    from the job's printer text, or (None, steps) when a step's DD list and its dataset list do not line up. The IEF237I lines
    name the DDs in order and the IEF285I / IEF287I lines the datasets in the same order; the user-catalog entries and the
    SYSnnnnn DDs that stand for them are taken out of both. A DD naming a whole group (the base name) shows as one named
    IEF237I line plus nameless ones, one per generation: its rows carry the generations after the first under the name ""
    and it gets no `names` entry. A dataset printed twice in a row (UNCATALOGED then DELETED) is one entry, dispositions
    joined with "+"."""
    steps, cur, dds, dsns = {}, None, [], []

    def close():
        if cur is not None:
            steps[cur] = (list(dds), list(dsns))

    for line in text.splitlines():
        if m := _FALLOC.search(line):
            close()
            cur, dds, dsns = (f"{m[3]}.{m[2]}" if m[3] else m[2]) if m[1] == job else None, [], []
        elif cur is None:
            continue
        elif m := re.search(r"IEF237I\s+(\S+)\s+ALLOCATED TO(?: (\S+))?\s*$", line):
            if m[1] != "JES2" and not (m[2] and re.fullmatch(r"SYS\d{5}", m[2])):
                dds.append(m[2] or "")
        elif (m := _GDG_DISP.search(line)) and m[1] not in _CATALOGS and not _TEMP_SYS.match(m[1]):
            dsn = m[1][len(UCAT) :] if m[1].startswith(UCAT) else m[1]
            if dsns and dsns[-1][0] == dsn:
                dsns[-1] = (dsn, f"{dsns[-1][1]}+{m[2]}")
            else:
                dsns.append((dsn, m[2]))
        elif "IEF374I" in line:
            close()
            cur = None
    names, rows, aligned = {}, {}, True
    for step, (d, n) in steps.items():
        if len(d) != len(n):
            aligned = False
        rows[step] = [(dd, dsn, disp) for dd, (dsn, disp) in zip(d, n, strict=False)]
        for i, (dd, dsn, _) in enumerate(rows[step]):
            grouped = dd == "" or (i + 1 < len(rows[step]) and rows[step][i + 1][0] == "")
            if not grouped and (g := _GEN_NAME.match(dsn)):
                names[f"{step}.{dd}"] = int(g["n"])
    return (names if aligned else None), rows


def observe_gdg_failures(text, job):
    """{step: the IEF2nnI line that stopped it} for each step the job did not execute (IEF272I), from the printer text."""
    out, last = {}, None
    for line in text.splitlines():
        if m := re.search(r"IEF2(?:12|86|10|11|13|14|19)I\s+" + re.escape(job) + r"\s+(\S+)\s+(.*)$", line):
            last = (m[1], line.strip())
        elif m := re.search(r"IEF272I\s+" + re.escape(job) + r"\s+(\S+)\s+- STEP WAS NOT EXECUTED", line):
            out[m[1]] = last[1] if last else line.strip()
    return out


def main_gdg(args):
    doc = json.loads((GDG_CASE / "scenarios.json").read_text(encoding="utf-8"))
    lines = doc["flow_jcl"]
    rows = job_flow.jcl_job_flow("\n".join(lines) + "\n")
    skipped = [(s["id"], gdg_skip(lines, s["job"])) for s in doc["scenarios"]]
    skipped = {i: why for i, why in skipped if why}
    scs = [s for s in doc["scenarios"] if s["id"] not in skipped]
    if args.dry:
        for sc in scs:
            print(f"* {sc['id']}\n{gdg_setup_deck(gdg_catalog(doc, sc))}{gdg_job_deck(lines, sc['job'], sc['given'])}")
        print(gdg_list_deck())
        return 0
    if not args.printer:
        print("probe: --printer FILE is required (the 1403 file of a started box)", file=sys.stderr)
        return 2
    results = []
    send = lambda deck, name: submit_and_read(deck, name, args.printer, args.host, args.port, args.timeout)  # noqa: E731
    for sc in scs:
        catalog = gdg_catalog(doc, sc)
        send(gdg_setup_deck(catalog), "GSETUP")
        text = send(gdg_job_deck(lines, sc["job"], sc["given"]), sc["job"])
        after_text = send(gdg_list_deck(), "GLIST")
        flow_rows = expand_flow_rows(rows, sc["job"])
        try:
            e_names, e_after = resolve_gdg(
                flow_rows, sc["job"], catalog, JclFlow(flow_rows).run(sc["job"], sc["given"])
            )
            engine = {"names": e_names, "catalog": {b: c["generations"] for b, c in e_after.items()}}
        except JclGdgRefused as why:
            engine = {"refused": str(why)}
        expect = {"names": sc["expect"], "catalog": {b: c["generations"] for b, c in sc["catalog_after"].items()}}
        seen, per_step = observe_gdg(text, sc["job"]) if text else (None, None)
        listed = observe_gdg_catalog(after_text) if after_text else None
        failed = observe_gdg_failures(text, sc["job"]) if text else {}
        box = None
        if seen is not None and listed is not None:
            box = {"names": seen, "catalog": {b: listed.get(b, {}).get("generations") for b in expect["catalog"]}}
        results.append(
            {
                "id": sc["id"],
                "job": sc["job"],
                "catalog_before": {b: c["generations"] for b, c in catalog.items()},
                "expect": expect,
                "engine": engine,
                "box": box,
                "verdict": verdict(expect, engine, box),
                "box_dispositions": per_step,
                "box_catalog_after": listed,
                "unobserved": GDG_UNOBSERVED,
            }
        )
        if failed:  # only when non-empty: an always-present empty key would break exact-equality readers
            results[-1]["box_not_executed"] = failed
        print(f"{sc['id']}: {results[-1]['verdict']}", flush=True)
    send(gdg_setup_deck({}), "GSETUP")  # leave the volume clean
    out = {
        "provenance": runner.PROVENANCE,
        "internal_only": "Q16: MVS 3.8J results are not published",
        "fixture": "tests/equivalence/jcl/gdg/scenarios.json",
        "skipped": skipped,
        "results": results,
    }
    Path(args.out if args.out != str(RESULTS) else GDG_RESULTS).write_text(json.dumps(out, indent=1) + "\n")
    return 0 if all(r["verdict"] == "agree" for r in results) else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("what", choices=["cond", "proc", "flow", "gdg"])
    ap.add_argument("--printer")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=3505)
    ap.add_argument("--timeout", type=float, default=180)
    ap.add_argument("--out", default=str(RESULTS))
    ap.add_argument("--dry", action="store_true", help="print the decks, submit nothing")
    args = ap.parse_args(argv)
    if args.what == "proc":
        return main_proc(args)
    if args.what == "flow":
        return main_flow(args)
    if args.what == "gdg":
        return main_gdg(args)
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
