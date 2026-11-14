# jcl_proc.py -- #8413 slice 2: resolve a job's procedure calls into the steps and DDs the system runs.
#
# `resolve_job(text, libraries, job)` returns, per EXEC of the job (a procedure call is one entry per procedure step,
# keyed `CALLSTEP.PROCSTEP`), the program, PARM, COND and the DSN-naming DDs after: symbolic parameters (EXEC value >
# PROC default; SET for the job's own statements), EXEC `PARM.procstep=` / `COND.procstep=` overrides, `procstep.ddname`
# DD overrides and added DDs, INCLUDE, and the JCLLIB ORDER search (first library holding the member wins).
# `expand_flow_rows(rows)` splices a call's procedure steps into `jcl_job_flow` rows as `CALLSTEP.PROCSTEP` so
# `jcl_flow.JclFlow` can answer `IF (CALLSTEP.PROCSTEP.RC = 0)`.
#
# ASSUMED (scenarios.json): A1 an in-stream procedure is used before a library member of the same name; A2 INCLUDE
# searches the JCLLIB ORDER libraries first-wins, as EXEC does.
# Refused by name (JclProcRefused): an unqualified PARM= / COND= on a procedure call, a symbolic assigned nowhere, a SET
# of a symbolic the PROC statement also defaults, nested procedure calls, INCLUDE inside a procedure, a DD override that
# turns a DD into SYSOUT / DUMMY, a member found in no library.
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from gitgalaxy.core.job_flow import _parm, _split, _statements


class JclProcRefused(ValueError):
    """A construct this resolver does not carry: refused by name, never guessed."""


_SYMBOLIC = re.compile(r"&([A-Z@#$][A-Z0-9@#$]{0,7})\.?", re.I)
_COND_STEP = re.compile(r"(\(\s*\d+\s*,\s*[A-Z]{2}\s*,\s*)([A-Z@#$][A-Z0-9@#$]*)(\s*\))", re.I)


def _substitute(text: str | None, values: Mapping[str, str]) -> str | None:
    """`&NAME.` -> value (the period ends the name and is consumed); `&NAME` followed by anything else -> value."""
    if text is None:
        return None

    def sub(m: re.Match[str]) -> str:
        name = m.group(1).upper()
        if name not in values:
            raise JclProcRefused(f"symbolic parameter &{name} is assigned nowhere: the null-value rule is not answered")
        return values[name]

    return _SYMBOLIC.sub(sub, text)


def _find(member: str, order: list[str], libraries: Mapping[str, Mapping[str, str]]) -> str:
    for lib in order:
        if member in libraries.get(lib, {}):
            return libraries[lib][member]
    raise JclProcRefused(f"member {member} is in no library of ORDER={order}")


def _proc_body(stmts: list[tuple[int, str, str, str]]) -> tuple[dict[str, str], list[tuple[int, str, str, str]]]:
    """The PROC statement's defaults and the statements up to PEND (or the end of a library member)."""
    defaults: dict[str, str] = {}
    body: list[tuple[int, str, str, str]] = []
    for _line, _name, op, field in stmts:
        if op == "PROC":
            defaults = {k: _parm(v, sublist=False) or "" for k, v in _split(field) if k}
        elif op == "PEND":
            break
        else:
            body.append((_line, _name, op, field))
    return defaults, body


def _job_statements(text: str, job: str) -> list[tuple[int, str, str, str]]:
    out: list[tuple[int, str, str, str]] = []
    inside = False
    for st in _statements(text):
        if st[2] == "JOB":
            inside = st[1] == job.upper()
        if inside:
            out.append(st)
    return out


def _step_dds(stmts: list[tuple[int, str, str, str]], order: list[str], libraries: Mapping[str, Mapping[str, str]]):
    """Walk statements -> ordered steps [{name, pgm, proc, parm, cond, parm_over, cond_over, dd, dd_over}]."""
    steps: list[dict[str, Any]] = []
    for _line, name, op, field in stmts:
        if op == "EXEC":
            ops = _split(field)
            keyed = {k: v for k, v in ops if k}
            bare = [v for k, v in ops if not k]
            proc = (keyed.get("PROC") or (bare[0] if bare else "")).upper() if "PGM" not in keyed else ""
            steps.append(
                {
                    "name": name,
                    "pgm": keyed.get("PGM"),
                    "proc": proc,
                    "parm": keyed.get("PARM"),
                    "cond": keyed.get("COND"),
                    "keyed": keyed,
                    "dd": [],
                    "dd_over": [],
                }
            )
        elif op == "DD" and steps:
            keyed = {k: v for k, v in _split(field) if k}
            ddname = name
            target = steps[-1]
            if "." in ddname:
                pstep, _, ddname = ddname.partition(".")
                target["dd_over"].append((pstep.upper(), ddname.upper(), keyed))
            else:
                target["dd"].append((ddname.upper(), keyed))
        elif op == "INCLUDE" and steps:
            member = dict(_split(field)).get("MEMBER", "").upper()
            _defaults, inc_body = _proc_body(_statements(_find(member, order, libraries)))
            for _l, ddn, iop, ifield in inc_body:
                if iop != "DD":
                    raise JclProcRefused("INCLUDE of anything but DD statements is not answered")
                steps[-1]["dd"].append((ddn.upper(), {k: v for k, v in _split(ifield) if k}))
    return steps


def _expand_call(
    call: dict[str, Any],
    defaults: dict[str, str],
    body: list[tuple[int, str, str, str]],
    set_values: dict[str, str],
) -> dict[str, dict[str, Any]]:
    keyed = call["keyed"]
    reserved = {"PROC", "PGM", "PARM", "COND", "RD", "ACCT", "TIME", "REGION", "ADDRSPC", "DYNAMNBR", "CCSID"}
    exec_values = {k: _parm(v, sublist=False) or "" for k, v in keyed.items() if k not in reserved and "." not in k}
    for k in keyed:
        if (k in ("PARM", "COND")) and call["proc"]:
            raise JclProcRefused(f"unqualified {k}= on a procedure call is not answered")
    for k in defaults:
        if k in set_values:
            raise JclProcRefused(f"SET of &{k}, which the PROC statement also defaults: precedence is not answered")
    values = {**set_values, **defaults, **exec_values}
    proc_steps = _step_dds(body, [], {})
    out: dict[str, dict[str, Any]] = {}
    for ps in proc_steps:
        if ps["proc"]:
            raise JclProcRefused("nested procedure calls are not answered")
        key = f"{call['name']}.{ps['name']}"
        parm = keyed.get(f"PARM.{ps['name']}", ps["parm"])
        cond = keyed.get(f"COND.{ps['name']}", ps["cond"])
        dds: dict[str, str | None] = {}
        for ddn, dk in ps["dd"]:
            dds[ddn] = _substitute(dk.get("DSN") or dk.get("DSNAME"), values)
        for pstep, ddn, dk in call["dd_over"]:
            if pstep != ps["name"].upper():
                continue
            if "SYSOUT" in dk or "DUMMY" in dk:
                raise JclProcRefused("a DD override that makes the DD SYSOUT / DUMMY is not answered")
            dsn = dk.get("DSN") or dk.get("DSNAME")
            if dsn is not None or ddn not in dds:
                dds[ddn] = _substitute(dsn, values)  # an added DD lands after the procedure's own
        out[key] = {
            "pgm": ps["pgm"],
            "parm": _parm(_substitute(parm, values)),
            "cond": _substitute(cond, values),
            "dd": {k: v for k, v in dds.items() if v is not None},
        }
    return out


def resolve_job(text: str, libraries: Mapping[str, Mapping[str, str]], job: str) -> dict[str, dict[str, Any]]:
    """Every EXEC of `job`, resolved. `libraries`: {library: {member: JCL text}}."""
    stmts = _job_statements(text, job)
    order: list[str] = []
    instream: dict[str, tuple[dict[str, str], list[tuple[int, str, str, str]]]] = {}
    main: list[tuple[int, str, str, str]] = []
    i = 0
    while i < len(stmts):
        _line, name, op, field = stmts[i]
        if op == "JCLLIB":
            raw = dict(_split(field)).get("ORDER", "")
            order = [x.strip().upper() for x in raw.strip("()").split(",") if x.strip()]
        elif op == "PROC":
            j = i + 1
            while j < len(stmts) and stmts[j][2] != "PEND":
                j += 1
            instream[name.upper()] = _proc_body(stmts[i : j + 1])
            i = j
        else:
            main.append(stmts[i])
        i += 1
    out: dict[str, dict[str, Any]] = {}
    walk: list[tuple[int, str, str, str]] = []
    # SET applies to the statements after it: resolve each step with the SET values in force where it is coded
    pending_sets: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for st in main:
        if st[2] == "SET":
            current = {**current, **{k: _parm(v, sublist=False) or "" for k, v in _split(st[3]) if k}}
        elif st[2] == "EXEC":
            pending_sets.append(dict(current))
        walk.append(st)
    steps = _step_dds([s for s in walk if s[2] != "SET"], order, libraries)
    for call, in_force in zip(steps, pending_sets, strict=True):
        if call["proc"]:
            if call["proc"] in instream:
                defaults, body = instream[call["proc"]]  # A1
            else:
                defaults, body = _proc_body(_statements(_find(call["proc"], order, libraries)))
            out.update(_expand_call(call, defaults, body, in_force))
        else:
            values = in_force
            out[call["name"]] = {
                "pgm": call["pgm"],
                "parm": _parm(_substitute(call["parm"], values)),
                "cond": _substitute(call["cond"], values),
                "dd": {k: v for k, v in ((n, _substitute(d.get("DSN"), values)) for n, d in call["dd"]) if v},
            }
    return out


def expand_flow_rows(rows: list[dict[str, Any]], job: str) -> list[dict[str, Any]]:
    """The rows of `job` (JOB row first) with each in-stream procedure call replaced by its steps `CALLSTEP.PROCSTEP` (the call's
    IF condition kept, COND tests inside the procedure re-pointed at the qualified names, `COND.procstep=` applied)."""
    mine: list[dict[str, Any]] = []
    inside = False
    for r in rows:
        if r["kind"] == "JOB":
            inside = r["name"] == job.upper()
        if inside:
            mine.append(r)
    rows = mine
    procs: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        if r["kind"] == "STEP" and r["in_proc"]:
            procs.setdefault(r["in_proc"], []).append(r)
    out: list[dict[str, Any]] = []
    for r in rows:
        if r["kind"] != "STEP" or r["in_proc"]:
            if r["kind"] != "STEP":
                out.append(r)
            continue
        if not r["proc"]:
            out.append(r)
            continue
        if r["proc"] not in procs:
            raise JclProcRefused(f"procedure {r['proc']} is not in-stream: expand_flow_rows reads in-stream procedures")
        over = {o["step"]: o["cond"] for o in r.get("cond_overrides", [])}
        call = r["step_name"]
        for ps in procs[r["proc"]]:
            cond = over.get(ps["step_name"], ps["cond"])
            if cond:
                cond = _COND_STEP.sub(rf"\g<1>{call}.\g<2>\g<3>", cond)
            out.append(dict(ps, step_name=f"{r['step_name']}.{ps['step_name']}", cond=cond, if_cond=r["if_cond"]))
    return out
