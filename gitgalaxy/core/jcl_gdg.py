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
# receives is scratched and uncataloged at job end (p. 237); a number past G9999 wraps to G0001 (p. 237). UNCATLG of a new
# generation is rejected and treated as KEEP; of the oldest existing one it is ignored when the group's catalog entry gives
# sms: true (KEEP implied) and removes the entry when it gives sms: false (JCL Reference, DISP: UNCATLG); absent, refused.
# GDGBIAS=STEP (JOB statement; User's Guide, Appendix A, 'Relative generation numbers' pp. 235-237) re-fixes the relationship at
# each step's first reference and rolls its new generations into the catalog at the end of that step. A procedure's step is
# a job step for this (assumption A7). A catalog entry that gives scratch: true / false reports the generations a roll-in
# pushed out of the group as rolled_off scratched / recataloged (DFSMS Using Data Sets, 'Generation data groups'). Refused by name (JclGdgRefused): see the `scenarios.json` "refused" list.
from __future__ import annotations

from collections.abc import Collection
from typing import Any

from gitgalaxy.core.jcl_flow import FlowResult


class JclGdgRefused(ValueError):
    """A GDG construct IBM's text does not settle here, or a JCL / catalog error: refused by name, never guessed."""


_STATE = {
    "CATLG": "cataloged",
    "DELETE": "deleted",
    "PASS": "passed",
    "KEEP": "deferred",
    "UNCATLG": "deferred",
}  # a new data set's UNCATLG is rejected and treated as KEEP


def _int_generation(text: str) -> int:
    return int(text)  # job_flow writes `+1` / `0` / `-1`


def resolve_gdg(
    rows: list[dict[str, Any]],
    job: str,
    catalogs: dict[str, dict[str, Any]],
    flow: FlowResult,
    skipped: Collection[str] = (),
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
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
    names: dict[str, Any] = {}  # an int, or a list (read order) for a concatenation or a GDG ALL read
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
    for dd in (d for ds in proc_dds.values() for d in ds):
        if dd.get("sysout_over"):
            raise JclGdgRefused(
                f"{dd['step_name']}.{dd['dd_name']}: a SYSOUT override of a DD that names a generation is not answered"
            )
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
    rolled: dict[str, list[int]] = {}  # base -> generations the job's roll-ins pushed out of the group (LIMIT / EMPTY)
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
                elif dd["disp"] in ("SHR", "OLD") and base in start:
                    _put(names, f"{step}.{dd['dd_name']}", _gdg_all(dd, base, live[base], catalogs[base], created))
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
            _put(names, key, absolute)
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
            elif end == "UNCATLG" and catalogs[base].get("sms") is None:
                raise JclGdgRefused(f"{key}: a disposition that removes an existing generation is not answered here")
            elif end == "UNCATLG" and catalogs[base]["sms"]:
                continue  # SMS-managed: UNCATLG is ignored, KEEP is implied (JCL Reference, DISP: UNCATLG)
            elif end in ("DELETE", "UNCATLG"):
                if not live[base] or absolute != live[base][0]:
                    raise JclGdgRefused(f"{key}: {end} of a generation other than the oldest is not answered here")
                drop.append((base, absolute))
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
                    rolled.setdefault(base, []).extend(_roll_in(live[base], absolute, catalogs[base]))
                    created[(base, absolute)] = "rolled"
                elif state in ("passed", "deferred"):
                    unreceived.add(base)
    after = {b: {"limit": catalogs[b]["limit"], "generations": list(live[b])} for b in start}
    for b in start:
        if catalogs[b].get("empty"):
            after[b]["empty"] = True
        if "sms" in catalogs[b]:
            after[b]["sms"] = catalogs[b]["sms"]  # the group's SMS state is carried to the next job
        if catalogs[b].get("gdgorder"):
            after[b]["gdgorder"] = catalogs[b][
                "gdgorder"
            ]  # the catalog entry's retrieval order is carried to the next job
    for b in start:
        if "scratch" in catalogs[b]:
            after[b]["scratch"] = catalogs[b]["scratch"]  # the group's SCRATCH / NOSCRATCH attribute is carried on
    for (base, absolute), state in sorted(created.items(), key=lambda kv: _since(anchor, *kv[0])):
        if state == "cataloged":  # a generation still passed at the end of the job is scratched and uncataloged
            rolled.setdefault(base, []).extend(_roll_in(after[base]["generations"], absolute, catalogs[base]))
        elif state == "deferred":
            after[base].setdefault("deferred_rollin", []).append(absolute)
    for (
        base,
        gens,
    ) in rolled.items():  # DFSMS Using Data Sets, 'Generation data groups': the fate of a rolled-off generation
        if gens and "scratch" in catalogs[base]:
            after[base]["rolled_off"] = {("scratched" if catalogs[base]["scratch"] else "recataloged"): gens}
    return names, after


def _put(names: dict[str, Any], key: str, value: Any) -> None:
    """Record what a DD names; a DD name used again (an unnamed DD concatenated onto it) extends a list, in read order."""
    new = value if isinstance(value, list) else [value]
    if key not in names:
        names[key] = value
    else:
        names[key] = [*(names[key] if isinstance(names[key], list) else [names[key]]), *new]


def _gdg_all(
    dd: dict[str, Any], base: str, live: list[int], catalog: dict[str, Any], created: dict[tuple[str, int], str]
) -> list[int]:
    """A GDG ALL read (the group named with no generation number, DISP=SHR / OLD): every cataloged generation, newest
    first by default (LIFO), oldest first for FIFO; GDGORDER=USECATLG takes the catalog entry's order (User's Guide,
    Appendix A, 'Retrieving all generation data sets', pp. 240-241)."""
    where = f"{dd['step_name']}.{dd['dd_name']}"
    order = dd.get("gdgorder", "USECATLG")
    if order == "USECATLG":
        order = catalog.get("gdgorder", "LIFO")
    if order not in ("LIFO", "FIFO"):
        raise JclGdgRefused(f"{where}: GDGORDER={order} is not LIFO, FIFO or USECATLG")
    if any(b == base for b, _ in created):
        raise JclGdgRefused(f"{where}: a whole-group read in a job that creates a generation of {base} is not answered")
    if not live:
        raise JclGdgRefused(f"{where}: a whole-group read of {base}, which has no cataloged generation")
    return list(live) if order == "FIFO" else list(reversed(live))


def _next_generation(seen: list[int], n: int) -> int:
    """The absolute number (+n) takes: n past the newest, wrapping from G9999 to G0001 (User's Guide, Appendix A)."""
    return ((seen[-1] if seen else 0) + n - 1) % 9999 + 1


def _since(anchor: dict[str, list[int]], base: str, absolute: int) -> int:
    """How far past the group's newest generation at the job's first reference a created generation is (wrap-safe)."""
    seen = anchor.get(base) or []
    return (absolute - (seen[-1] if seen else 0)) % 9999


def _roll_in(gens: list[int], absolute: int, catalog: dict[str, Any]) -> list[int]:
    """Roll a generation in; return the generations it pushed out of the group, oldest first."""
    off: list[int] = []
    if catalog.get("empty") and len(gens) >= catalog["limit"]:
        off = list(gens)  # EMPTY: a roll-in at the limit rolls off every active generation
        gens.clear()
    gens.append(absolute)
    extra = max(0, len(gens) - catalog["limit"])
    off += gens[:extra]  # LIMIT: the oldest rolls off
    del gens[:extra]
    return off


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
