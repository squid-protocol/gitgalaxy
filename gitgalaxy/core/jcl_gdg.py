# jcl_gdg.py -- #8413: which absolute generation each GDG relative DD names, and the catalog after the job.
#
# Input: the `job_flow.jcl_job_flow` rows, a job, the GDG catalog as the job starts ({base: {limit, generations}}, the
# cataloged absolute numbers oldest first) and the `JclFlow.run` result (which steps ran, which abended). The rules are
# IBM's (z/OS MVS JCL Reference, SA23-1385: DD DSNAME generation numbers, DISP; z/OS DFSMS Using Data Sets, generation
# data groups); `tests/equivalence/jcl/gdg/scenarios.json` carries answers written from that text before this module existed.
#
# Rules modelled: a relative number is resolved against the catalog as it stood when the job started (so a (+1) in a
# later step is the generation an earlier step created, and (0) is still the old current one); a created generation is
# rolled into the catalog at the end of the job (ASSUMED A1) and the group's LIMIT drops the oldest; a step that did not
# run allocates nothing; a created generation's step-end disposition is its abnormal DISP when the step abended (else its
# normal DISP; NEW with none is DELETE) -- CATLG catalogs it, DELETE removes it, PASS hands it to a later step.
# Refused by name (JclGdgRefused): see the `scenarios.json` "refused" list.
from __future__ import annotations

from typing import Any

from gitgalaxy.core.jcl_flow import FlowResult


class JclGdgRefused(ValueError):
    """A GDG construct IBM's text does not settle here, or a JCL / catalog error: refused by name, never guessed."""


_STATE = {"CATLG": "cataloged", "DELETE": "deleted", "PASS": "passed", "KEEP": "kept", "UNCATLG": "kept"}


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
    created: dict[
        tuple[str, int], str
    ] = {}  # (base, absolute) -> "pending" | "cataloged" | "passed" | "kept" | "deleted"
    names: dict[str, int] = {}
    current = None
    dds: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row["kind"] == "JOB":
            current = row["name"]
        elif current == job and row["kind"] == "DD" and not row.get("in_proc") and row.get("generation") is not None:
            dds.setdefault(row["step_name"], []).append(row)
    for step, res in flow.steps.items():
        if res.action != "run":
            continue  # a bypassed step allocates none of its DDs
        for dd in dds.get(step, []):
            base, n = dd["dsn"], _int_generation(dd["generation"])
            if base not in start:
                raise JclGdgRefused(f"GDG base {base} has no catalog entry given")
            current_gen = start[base][-1] if start[base] else 0
            absolute = current_gen + n
            key = f"{step}.{dd['dd_name']}"
            names[key] = absolute
            if n > 0:
                state = created.get((base, absolute))
                if dd["disp"] == "NEW":
                    if state is not None:
                        raise JclGdgRefused(f"{key}: two steps create the same (+{n}) with DISP=NEW")
                    created[(base, absolute)] = "pending"
                elif state is None:
                    raise JclGdgRefused(f"{key}: (+{n}) read before any step creates it")
            elif absolute not in start[base]:
                raise JclGdgRefused(f"{key}: no cataloged generation {absolute} of {base}")
            end = _step_end(dd, res.abend is not None)
            if end is None:
                continue
            if n > 0:
                created[(base, absolute)] = _STATE[end]
            elif end in ("DELETE", "UNCATLG"):
                raise JclGdgRefused(f"{key}: a disposition that removes an existing generation is not answered here")
    after = {b: {"limit": catalogs[b]["limit"], "generations": list(start[b])} for b in start}
    for (base, absolute), state in sorted(created.items(), key=lambda kv: kv[0][1]):
        if state == "passed":
            raise JclGdgRefused(f"{base} generation {absolute} is passed and never received")
        if state == "cataloged":
            gens = after[base]["generations"]
            gens.append(absolute)
            del gens[: max(0, len(gens) - after[base]["limit"])]  # LIMIT: the oldest rolls off
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
