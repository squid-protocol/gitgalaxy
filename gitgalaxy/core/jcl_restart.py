# jcl_restart.py -- #8413 slice 4: which steps run when a job is resubmitted with JOB RESTART=.
#
# `restart_flow(rows, job, given)` takes the `job_flow.jcl_job_flow` rows (an in-stream procedure's steps are spliced in as
# `CALLSTEP.PROCSTEP` by `jcl_proc.expand_flow_rows`), reads the JOB statement's RESTART= and answers, per step, "skipped"
# (before the restart step: not executed), "run" or "bypass" (the restart step's or a later step's COND / IF kept it from
# starting). The answers in `tests/equivalence/jcl/restart/scenarios.json` were written from IBM's z/OS MVS JCL Reference
# (SA23-1385, the JOB statement's RESTART parameter) before this module ran on them.
# RESTART=* is the first step. RESTART=(step,checkid) is a deferred checkpoint restart: it needs a SYSCHK DD before the
# first EXEC and starts the same steps as a step restart. EXEC RD= (automatic restart during a run) is not read.
# ASSUMED (A1, scenarios.json): a skipped step has no return code in the restarted run, so a bare COND / IF RC reads only
# the steps that executed in it.
# A COND test or IF relation naming a step before the restart step is false, and the restart step's own COND is false
# (z/OS 3.1 JCL Reference, JOB: RESTART cautions and EXEC: COND).
# Refused by name (JclRestartRefused): a step that is not in the job, a restart at a procedure's calling step with no
# procstepname, a restart step name that is not unique, a checkid with no SYSCHK DD.
from __future__ import annotations

from typing import Any

from gitgalaxy.core.jcl_flow import JclFlow
from gitgalaxy.core.jcl_proc import expand_flow_rows


class JclRestartRefused(ValueError):
    """A restart construct IBM's text does not settle, or that is invalid JCL: refused by name, never guessed."""


def restart_flow(rows: list[dict[str, Any]], job: str, given: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Per step of `job` (in order): "skipped", "run" or "bypass". `given`: per step that starts, its outcome."""
    job = job.upper()
    mine: list[dict[str, Any]] = []
    inside = False
    for r in rows:
        if r["kind"] == "JOB":
            inside = r["name"] == job
        if inside:
            mine.append(r)
    head = mine[0]
    restart = head.get("restart")
    calls = {r["step_name"] for r in mine if r["kind"] == "STEP" and not r["in_proc"] and r["proc"]}
    flat = expand_flow_rows(rows, job)
    steps = [r for r in flat if r["kind"] == "STEP"]
    names = [s["step_name"] for s in steps]
    if restart == "*":
        restart = names[0] if names else None
    if restart and "." not in restart and restart in calls:
        raise JclRestartRefused(
            f"RESTART={restart} names a procedure's calling step: stepname.procstepname is stated, no procstepname"
        )
    if restart and restart not in names:
        raise JclRestartRefused(f"RESTART={restart} is not a step of {job}")
    if head.get("restart_checkid") and not any(r["kind"] == "DD" and r["dd_name"] == "SYSCHK" for r in mine):
        raise JclRestartRefused(f"RESTART checkid {head['restart_checkid']} needs a SYSCHK DD before the first EXEC")
    if restart and names.count(restart) > 1:
        raise JclRestartRefused(f"RESTART={restart} is not unique in {job}: IBM leaves the restart step undetermined")
    cut = names.index(restart) if restart else 0
    skipped = set(names[:cut])
    # IBM (JOB RESTART cautions, EXEC COND): a COND or IF relation naming a skipped step is false, and the restart step
    # (the first step to execute) has its COND evaluated false. Skipped rows are dropped, so a relation naming one reads
    # "did not start" and a COND test naming one is false; the first executed row loses its COND.
    flow_rows = [r for r in flat if r["kind"] != "STEP" or r["step_name"] not in skipped]
    first = next((r for r in flow_rows if r["kind"] == "STEP"), None)
    if first is not None and first.get("cond"):
        flow_rows = [({**r, "cond": None} if r is first else r) for r in flow_rows]
    run = JclFlow(flow_rows).run(job, given)
    return {n: ("skipped" if n in skipped else run.actions[n]) for n in names}
