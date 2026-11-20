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
# both (User's Guide, Appendix A, 'Deleting and uncataloging generation data sets').
# Refused by name (JclGdgRefused): see the `scenarios.json` "refused" list.
from __future__ import annotations

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
) -> tuple[dict[str, int], dict[str, dict[str, Any]]]:
    """-> ({"STEP.DDNAME": absolute generation} for each GDG DD of a step that ran, the catalog after the job)."""
    start = {b: list(c["generations"]) for b, c in catalogs.items()}
    live = {b: list(g) for b, g in start.items()}  # the catalog as the steps so far left it (deletes happen at step end)
    anchor: dict[str, list[int]] = {}  # base -> the catalog at the job's first relative reference (GDGBIAS=JOB)
    deleted: set[tuple[str, int]] = set()
    created: dict[
        tuple[str, int], str
    ] = {}  # (base, absolute) -> "pending" | "cataloged" | "passed" | "kept" | "deleted"
    names: dict[str, int] = {}
    current = None
    dds: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row["kind"] == "JOB":
            current = row["name"]
        elif current == job and row["kind"] == "DD" and not row.get("in_proc"):
            if row.get("generation") is not None or row.get("dsn") in start:
                dds.setdefault(row["step_name"], []).append(row)
    for step, res in flow.steps.items():
        if res.action != "run":
            continue  # a bypassed step allocates none of its DDs
        wipe: list[str] = []  # bases whose whole group this step deletes at its end
        drop: list[tuple[str, int]] = []  # oldest generations this step deletes at its end
        for dd in dds.get(step, []):
            base = dd["dsn"]
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
                absolute = (seen[-1] if seen else 0) + n
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
                raise JclGdgRefused(f"{step}: deleting all of {base} in a job that created a generation is not answered")
            deleted.update((base, g) for g in live[base])
            live[base].clear()
        for base, absolute in drop:
            if absolute in live[base]:
                live[base].remove(absolute)
                deleted.add((base, absolute))
    after = {b: {"limit": catalogs[b]["limit"], "generations": list(live[b])} for b in start}
    for b in start:
        if catalogs[b].get("empty"):
            after[b]["empty"] = True
    for (base, absolute), state in sorted(created.items(), key=lambda kv: kv[0][1]):
        if state == "passed":
            raise JclGdgRefused(f"{base} generation {absolute} is passed and never received")
        if state == "cataloged":
            gens = after[base]["generations"]
            if after[base].get("empty") and len(gens) >= after[base]["limit"]:
                gens.clear()  # EMPTY: a roll-in at the limit rolls off every active generation
            gens.append(absolute)
            del gens[: max(0, len(gens) - after[base]["limit"])]  # LIMIT: the oldest rolls off
        elif state == "deferred":
            after[base].setdefault("deferred_rollin", []).append(absolute)
    return names, after


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
