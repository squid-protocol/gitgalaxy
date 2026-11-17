# jcl_dataflow.py -- #8413 slice 5: what each DD of a step that ran names, and where a `&&` temporary dataset goes.
#
# Input: the `job_flow.jcl_job_flow` rows, a job, the `JclFlow.run` result (which steps ran, which abended) and, when a
# DD codes SYSOUT=*, the JOB statement's MSGCLASS. The rules are IBM's (z/OS MVS JCL Reference, SA23-1385: DD DSNAME
# temporary datasets, DUMMY and NULLFILE, DISP, SYSOUT, OUTPUT, concatenating datasets);
# `tests/equivalence/jcl/dataflow/scenarios.json` carries answers written from that text before this module existed.
#
# Per "STEP.DDNAME" of a step that ran the answer is one of: {"datasets": [...]} (a concatenation lists its datasets in
# the order coded), {"dummy": True}, {"temporary": "system-named"}, {"dd_class": c, "output": [...]} (a SYSOUT DD; `*`
# is the job's MSGCLASS, `output` the OUTPUT statements it references). A `&&name` temporary also gets its creating DD,
# the DDs that receive it and the step after which it is deleted ("JOB": the end of the job, when no DD deleted it).
# A step that did not run allocates nothing, so a bypassed creator creates no temporary.
# ASSUMED (scenarios.json): A1 an existing dataset with no normal disposition stays passed; A2 OUTPUT=*.name is the
# OUTPUT statement of the same step, else the job-level one.
# Refused by name (JclDataflowRefused): see the `scenarios.json` "refused" list.
from __future__ import annotations

from typing import Any

from gitgalaxy.core.jcl_flow import FlowResult


class JclDataflowRefused(ValueError):
    """A data-flow construct IBM's text does not settle here, or a JCL error: refused by name, never guessed."""


_DD_KINDS = ("DD", "DUMMY", "TEMP", "SYSOUT")


def _end_word(row: dict[str, Any], abended: bool, existing: bool) -> str:
    """The step-end disposition of a temporary's DD: the abnormal one defaults to the normal one; none coded is DELETE for
    a NEW dataset and (ASSUMED A1) PASS for an existing one."""
    normal = row.get("disp_normal")
    word = (row.get("disp_abnormal") or normal) if abended else normal
    return word or ("PASS" if existing else "DELETE")


def _output_name(ref: str, step: str, outputs: set[tuple[str | None, str]]) -> str:
    """`*.NAME` -> the OUTPUT of this step, else the job-level one (ASSUMED A2); `*.STEP.NAME` -> that step's."""
    parts = ref[2:].split(".") if ref.startswith("*.") else []
    if len(parts) == 1 and (step, parts[0]) in outputs:
        return parts[0]
    if len(parts) == 1 and (None, parts[0]) in outputs:
        return parts[0]
    if len(parts) == 2 and (parts[0], parts[1]) in outputs:
        return ".".join(parts)
    raise JclDataflowRefused(f"OUTPUT={ref} names no OUTPUT statement of the job")


def resolve_dataflow(
    rows: list[dict[str, Any]], job: str, flow: FlowResult, msgclass: str | None = None
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """-> ({"STEP.DDNAME": answer} for each DD of a step that ran, {"&&NAME": its creator, receivers and deletion})."""
    dds: dict[str, dict[str, list[dict[str, Any]]]] = {}
    outputs: set[tuple[str | None, str]] = set()
    current = None
    for row in rows:
        if row["kind"] == "JOB":
            current = row["name"]
        elif current != job or row.get("in_proc"):
            continue
        elif row["kind"] == "OUTPUT" and row.get("name"):
            outputs.add((row["step_name"], row["name"]))
        elif row["kind"] in _DD_KINDS:
            dds.setdefault(row["step_name"], {}).setdefault(row["dd_name"], []).append(row)
    answers: dict[str, dict[str, Any]] = {}
    temps: dict[str, dict[str, Any]] = {}
    for step, res in flow.steps.items():
        if res.action != "run":
            continue  # a bypassed step allocates none of its DDs
        for ddname, group in dds.get(step, {}).items():
            key = f"{step}.{ddname}"
            if any(r["kind"] == "DUMMY" for r in group):
                if len(group) > 1:
                    raise JclDataflowRefused(f"{key}: DUMMY inside a concatenation is not answered here")
                answers[key] = {"dummy": True}
            elif group[0]["kind"] == "TEMP":
                answers[key] = {"temporary": "system-named"}
            elif group[0]["kind"] == "SYSOUT":
                answers[key] = _sysout(group[0], step, outputs, msgclass, key)
            else:
                answers[key] = {"datasets": [_dataset(r) for r in group]}
                for r in group:
                    if r["dsn"].startswith("&&"):
                        _temporary(temps, r, key, step, res.abend is not None)
    for t in temps.values():
        t["deleted_after"] = t["deleted_after"] or "JOB"
    return answers, temps


def _dataset(row: dict[str, Any]) -> str:
    return f"{row['dsn']}({row['generation']})" if row.get("generation") is not None else row["dsn"]


def _sysout(
    row: dict[str, Any], step: str, outputs: set[tuple[str | None, str]], msgclass: str | None, key: str
) -> dict[str, Any]:
    cls = row.get("sysout")
    if cls == "*":
        cls = msgclass
    if not cls:
        raise JclDataflowRefused(f"{key}: SYSOUT with no class (or * with no MSGCLASS) is not answered here")
    refs = [_output_name(ref, step, outputs) for ref in row.get("output_refs", [])]
    return {"dd_class": cls, **({"output": refs} if refs else {})}


def _temporary(temps: dict[str, dict[str, Any]], row: dict[str, Any], key: str, step: str, abended: bool) -> None:
    name = row["dsn"]
    existing = row["disp"] != "NEW"
    if existing:
        t = temps.get(name)
        if t is None or t["deleted_after"] is not None:
            raise JclDataflowRefused(f"{key}: {name} is received before a step creates it, or after it was deleted")
        if key not in t["received_by"]:
            t["received_by"].append(key)
    elif name in temps:
        raise JclDataflowRefused(f"{key}: {name} is created twice")
    else:
        temps[name] = {"created_by": key, "received_by": [], "deleted_after": None}
    word = _end_word(row, abended, existing)
    if word == "DELETE":
        temps[name]["deleted_after"] = step
    elif word != "PASS":
        raise JclDataflowRefused(f"{key}: {name} with disposition {word} is not answered here")
