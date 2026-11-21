# jcl_gdg.py -- #8413: which absolute generation each GDG relative DD names, and the catalog after the job.
#
# Input: the `job_flow.jcl_job_flow` rows, a job, the GDG catalog as the job starts ({base: {limit, generations}}, the
# cataloged absolute numbers oldest first) and the `JclFlow.run` result (which steps ran, which abended). The rules are
# IBM's (z/OS MVS JCL Reference, SA23-1385: DD DSNAME generation numbers, DISP; z/OS DFSMS Using Data Sets, generation
# data groups); `tests/equivalence/jcl/gdg/scenarios.json` carries answers written from that text before this module existed.
#
# Rules modelled: a relative number is resolved against the catalog as it stood when the job started (so a (+1) in a
# later step is the generation an earlier step created, and (0) is still the old current one); a created generation is
# rolled into the catalog at the end of the job (User's Guide, Appendix A, GDGBIAS=JOB) and the group's LIMIT drops the oldest; a step that did not
# run allocates nothing; a created generation's step-end disposition is its abnormal DISP when the step abended (else its
# normal DISP; NEW with none is DELETE) -- CATLG catalogs it, DELETE removes it, PASS hands it to a later step, KEEP leaves
# it in deferred roll-in (not in the active group; DFSMS Using Data Sets, "Rolling In a Generation Data Set"). A (0) / (-n)
# is a position in the group's index; an EMPTY group at its LIMIT rolls off every generation when one is rolled in.
# A DD naming the group itself with a deleting disposition removes every generation at that step's end, and DELETE of the
# oldest (-n) removes that one; the relative / absolute relationship fixed at the job's first relative reference survives
# both (User's Guide, Appendix A, 'Deleting and uncataloging generation data sets'). A (NEW,PASS) generation no later step
# receives is scratched and uncataloged at job end (p. 237); a number past G9999 wraps to G0001 (p. 237).
# GDGBIAS=STEP (JOB statement; User's Guide, Appendix A, 'Relative generation numbers' pp. 235-237) re-fixes the relationship at
# each step's first reference and rolls its new generations into the catalog at the end of that step. A procedure's step is
# a job step for this (assumption A7). Refused by name (JclGdgRefused): see the `scenarios.json` "refused" list.
from __future__ import annotations

from collections.abc import Collection
from typing import Any

from gitgalaxy.core.jcl_flow import FlowResult


class JclGdgRefused(ValueError):
    """A GDG construct IBM's text does not settle here, or a JCL / catalog error: refused by name, never guessed."""


_STATE = {"CATLG": "cataloged", "DELETE": "deleted", "PASS": "passed", "KEEP": "deferred", "UNCATLG": "kept"}


def _int_generation(text: str) -> int:
    return int(text)  # job_flow writes `+1` / `0` / `-1`


def resolve_gdg(
    rows: list[dict[str, Any]],
    job: str,
    catalogs: dict[str, dict[str, Any]],
    flow: FlowResult,
    skipped: Collection[str] = (),
) -> tuple[dict[str, int], dict[str, dict[str, Any]]]:
    """-> ({"STEP.DDNAME": absolute generation} for each GDG DD of a step that ran, the catalog after the job)."""
    start = {b: list(c["generations"]) for b, c in catalogs.items()}
    live = {
        b: list(g) for b, g in start.items()
    }  # the catalog as the steps so far left it (deletes happen at step end)
    anchor: dict[str, list[int]] = {}  # base -> the catalog at the job's first relative reference (GDGBIAS=JOB)
    deleted: set[tuple[str, int]] = set()
    created: dict[
        tuple[str, int], str
    ] = {}  # (base, absolute) -> "pending" | "cataloged" | "passed" | "kept" | "deleted"
    names: dict[str, int] = {}
    current = None
    dds: dict[str, list[dict[str, Any]]] = {}  # job step -> its DDs
    proc_dds: dict[tuple[str, str], list[dict[str, Any]]] = {}  # (procedure, its step) -> its DDs
    proc_of = {r["step_name"]: r["in_proc"] for r in rows if r["kind"] == "STEP" and r.get("in_proc")}
    bias = "JOB"
    for row in rows:
        if row["kind"] == "JOB":
            current = row["name"]
            if current == job:
                bias = row.get("gdgbias", "JOB")
                if bias not in ("JOB", "STEP"):
                    raise JclGdgRefused(f"GDGBIAS={bias} is not JOB or STEP")
        elif current == job and row["kind"] == "DD" and (row.get("generation") is not None or row.get("dsn") in start):
            if row.get("in_proc"):
                proc_dds.setdefault((row["in_proc"], row["step_name"]), []).append(row)
            else:
                dds.setdefault(row["step_name"], []).append(row)
    for step in dds:
        if step not in flow.steps and step not in skipped and any(d.get("generation") is not None for d in dds[step]):
            raise JclGdgRefused(f"{step}: a GDG DD that overrides a procedure step's DD is not answered here")
    for step in skipped:  # a checkpoint restart: the steps before the restart step ran and cataloged their generations
        step_dds = proc_dds.get((proc_of[step], step.split(".", 1)[1]), []) if step in proc_of else dds.get(step, [])
        for dd in step_dds:
            if dd.get("generation") is None or _int_generation(dd["generation"]) <= 0:
                continue
            if bias == "STEP" or dd["disp"] not in ("NEW", "MOD"):
                raise JclGdgRefused(
                    f"{step}.{dd['dd_name']}: a restart over a skipped step is answered for GDGBIAS=JOB"
                )
            base = dd["dsn"]
            if base not in start:
                raise JclGdgRefused(f"GDG base {base} has no catalog entry given")
            seen = anchor.setdefault(base, list(live[base]))
            absolute = _next_generation(seen, _int_generation(dd["generation"]))
            end = _step_end(dd, False)
            created[(base, absolute)] = _STATE[end] if end else "pending"
    unreceived: set[str] = (
        set()
    )  # STEP bias: groups with a passed / deferred generation, which no later step may reference
    for step, res in flow.steps.items():
        if res.action != "run":
            continue  # a bypassed step allocates none of its DDs
        if "." in step and step in proc_of:
            step_dds = proc_dds.get((proc_of[step], step.split(".", 1)[1]), [])
        else:
            step_dds = dds.get(step, [])
        if bias == "STEP":
            anchor.clear()  # a new relationship at each step's first reference
        wipe: list[str] = []  # bases whose whole group this step deletes at its end
        drop: list[tuple[str, int]] = []  # oldest generations this step deletes at its end
        for dd in step_dds:
            base = dd["dsn"]
            if bias == "STEP" and dd.get("generation") is not None and base in unreceived:
                raise JclGdgRefused(
                    f"{step}.{dd['dd_name']}: {base} holds a passed or deferred generation under GDGBIAS=STEP"
                )
            if dd.get("generation") is None:
                end = _step_end(dd, res.abend is not None)
                if end == "DELETE":
                    wipe.append(base)
                elif end == "UNCATLG":
                    raise JclGdgRefused(f"{step}.{dd['dd_name']}: UNCATLG of a generation group is not answered here")
                continue
            n = _int_generation(dd["generation"])
            if base not in start:
                raise JclGdgRefused(f"GDG base {base} has no catalog entry given")
            key = f"{step}.{dd['dd_name']}"
            # the first relative reference fixes the relative / absolute relationship for the rest of the job
            seen = anchor.setdefault(base, list(live[base]))
            if n > 0:
                absolute = _next_generation(seen, n)
            elif len(seen) + n > 0:
                absolute = seen[n - 1]  # (0) / (-n) is a position in the index: a skipped number is not counted
            else:
                raise JclGdgRefused(f"{key}: no cataloged generation ({n}) of {base}")
            names[key] = absolute
            if n <= 0 and (base, absolute) in deleted:
                raise JclGdgRefused(f"{key}: generation {absolute} of {base} was deleted earlier in the job")
            if n > 0:
                state = created.get((base, absolute))
                if dd["disp"] == "NEW":
                    if state is not None:
                        raise JclGdgRefused(f"{key}: two steps create the same (+{n}) with DISP=NEW")
                    created[(base, absolute)] = "pending"
                elif dd["disp"] == "MOD" and state is None:
                    created[(base, absolute)] = "pending"  # MOD of an absent generation is changed to NEW (DISP)
                elif state is None:
                    raise JclGdgRefused(f"{key}: (+{n}) read before any step creates it")
            end = _step_end(dd, res.abend is not None)
            if end is None:
                continue
            if n > 0:
                created[(base, absolute)] = _STATE[end]
            elif end == "DELETE":
                if not live[base] or absolute != live[base][0]:
                    raise JclGdgRefused(f"{key}: DELETE of a generation other than the oldest is not answered here")
                drop.append((base, absolute))
            elif end == "UNCATLG":
                raise JclGdgRefused(f"{key}: a disposition that removes an existing generation is not answered here")
        for base in wipe:
            if any(b == base for b, _ in created):
                raise JclGdgRefused(
                    f"{step}: deleting all of {base} in a job that created a generation is not answered"
                )
            deleted.update((base, g) for g in live[base])
            live[base].clear()
        for base, absolute in drop:
            if absolute in live[base]:
                live[base].remove(absolute)
                deleted.add((base, absolute))
        if bias == "STEP":  # the step's new generations are rolled into the catalog as it ends
            for (base, absolute), state in sorted(created.items(), key=lambda kv: _since(anchor, *kv[0])):
                if state == "cataloged":
                    _roll_in(live[base], absolute, catalogs[base])
                    created[(base, absolute)] = "rolled"
                elif state in ("passed", "deferred"):
                    unreceived.add(base)
    after = {b: {"limit": catalogs[b]["limit"], "generations": list(live[b])} for b in start}
    for b in start:
        if catalogs[b].get("empty"):
            after[b]["empty"] = True
    for (base, absolute), state in sorted(created.items(), key=lambda kv: _since(anchor, *kv[0])):
        if state == "cataloged":  # a generation still passed at the end of the job is scratched and uncataloged
            _roll_in(after[base]["generations"], absolute, catalogs[base])
        elif state == "deferred":
            after[base].setdefault("deferred_rollin", []).append(absolute)
    return names, after


def _next_generation(seen: list[int], n: int) -> int:
    """The absolute number (+n) takes: n past the newest, wrapping from G9999 to G0001 (User's Guide, Appendix A)."""
    return ((seen[-1] if seen else 0) + n - 1) % 9999 + 1


def _since(anchor: dict[str, list[int]], base: str, absolute: int) -> int:
    """How far past the group's newest generation at the job's first reference a created generation is (wrap-safe)."""
    seen = anchor.get(base) or []
    return (absolute - (seen[-1] if seen else 0)) % 9999


def _roll_in(gens: list[int], absolute: int, catalog: dict[str, Any]) -> None:
    if catalog.get("empty") and len(gens) >= catalog["limit"]:
        gens.clear()  # EMPTY: a roll-in at the limit rolls off every active generation
    gens.append(absolute)
    del gens[: max(0, len(gens) - catalog["limit"])]  # LIMIT: the oldest rolls off


def _step_end(dd: dict[str, Any], abended: bool) -> str | None:
    """The step-end disposition word of a DD, or None when it states none and only reads. IBM DISP: the abnormal
    disposition applies when the step abended and defaults to the normal one; a NEW dataset's normal default is DELETE."""
    normal = dd.get("disp_normal")
    abnormal = dd.get("disp_abnormal")
    word = (abnormal or normal) if abended else normal
    if word is None:
        if dd["disp"] == "NEW":
            word = "DELETE"
        else:
            return None
    return word
