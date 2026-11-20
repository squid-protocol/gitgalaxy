# jcl_proc.py -- #8413 slice 2: resolve a job's procedure calls into the steps and DDs the system runs.
#
# `resolve_job(text, libraries, job)` returns, per EXEC of the job (a procedure call is one entry per procedure step,
# keyed `CALLSTEP.PROCSTEP`), the program, PARM, COND and the DSN-naming DDs after: symbolic parameters (EXEC value >
# PROC default > SET, Table 13; a nullified symbol is empty), EXEC `PARM.procstep=` / `COND.procstep=` overrides, `procstep.ddname`
# DD overrides and added DDs, INCLUDE, and the JCLLIB ORDER search (first library holding the member wins).
# `expand_flow_rows(rows, job, text, libraries)` splices a call's procedure steps (in-stream or library member) into `jcl_job_flow` rows as `CALLSTEP.PROCSTEP` so
# `jcl_flow.JclFlow` can answer `IF (CALLSTEP.PROCSTEP.RC = 0)`.
#
# Procedure search (JCL Reference, "Using a procedure", p. 26): the job's in-stream procedure first, then the JCLLIB ORDER
# libraries in the order coded ("JCLLIB", ORDER=); an INCLUDE group is searched the same way ("Considerations for using
# INCLUDE groups", p. 376). Duplicate symbols (p. 36-37): the first on an EXEC or a PROC statement wins, the last on a SET.
# Unqualified EXEC PARM= goes to the first procedure step only (the others' PARM are nullified); unqualified COND= to every step.
# A4: a nested procedure's steps are keyed CALLSTEP.PROCSTEP naming the PGM step itself (levels flattened, as the manual's
# "equivalent statements" do). Nested calls (15 levels), INCLUDE groups inside a procedure (and inside an INCLUDE group),
# and DD kind overrides (DUMMY / DSN=NULLFILE nullify a DSN, a DSN other than NULLFILE nullifies a DUMMY) are resolved.
# Refused by name (JclProcRefused): an unqualified PARM= / COND= together with the .procstep form on one call, a symbolic
# assigned nowhere, a SYSOUT / * / DATA override of a DD that names a DSN,
# a backward reference procstep.procstep.ddname or a modifying statement for a step that is absent or itself a call,
# EXEC PARM= / COND= on a call of a procedure that calls procedures, nesting past 15 levels (invalid, pp. 32, 376), an INCLUDE
# group holding JOB / PROC / PEND / JCLLIB (invalid, p. 376), an EXEC / SET statement in an INCLUDE group inside a procedure (a job-level
# group is spliced into the job whole, EXEC and SET included, p. 376), a member found
# in no library. An OUTPUT statement in an INCLUDE group adds no DD and is skipped.
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from gitgalaxy.core.job_flow import _parm, _split, _statements, jcl_job_flow


class JclProcRefused(ValueError):
    """A construct this resolver does not carry: refused by name, never guessed."""


_SYMBOLIC = re.compile(r"&([A-Z@#$][A-Z0-9@#$]{0,7})\.?", re.I)
_COND_STEP = re.compile(r"(\(\s*\d+\s*,\s*[A-Z]{2}\s*,\s*)([A-Z@#$][A-Z0-9@#$]*)(\s*\))", re.I)


def _first_wins(ops: list[tuple[str | None, str]]) -> dict[str, str]:
    """Keyword operands with the first of a duplicated key kept (duplicate JCL symbols on EXEC / PROC, p. 36-37)."""
    out: dict[str, str] = {}
    for k, v in ops:
        if k and k not in out:
            out[k] = v
    return out


def _keyword(field: str, key: str) -> str:
    """The value of a keyword operand (`ORDER=(...)`, `MEMBER=X`) on a statement, empty when it is not coded."""
    return dict(_split(field)).get(key, "")


def _substitute(text: str | None, values: Mapping[str, str]) -> str | None:
    """`&NAME.` -> value (the period ends the name and is consumed); `&NAME` followed by anything else -> value."""
    if text is None:
        return None

    def sub(m: re.Match[str]) -> str:
        name = m.group(1).upper()
        if name not in values:
            raise JclProcRefused(
                f"symbolic parameter &{name} is assigned nowhere: invalid, every JCL symbol coded must have a value (p. 37)"
            )
        return values[name]

    return _SYMBOLIC.sub(sub, text)


def _find(member: str, order: list[str], libraries: Mapping[str, Mapping[str, str]]) -> str:
    for lib in order:
        if member in libraries.get(lib, {}):
            return libraries[lib][member]
    raise JclProcRefused(f"member {member} is in no library of ORDER={order}")


def _dd_keys(field: str) -> dict[str, str]:
    """A DD statement's keyword operands, plus `DUMMY` (bare DUMMY, or DSN=NULLFILE: same effect) and `*` (DD * / DATA)."""
    ops = _split(field)
    keyed = {k: v for k, v in ops if k}
    for k, v in ops:
        if not k and v.upper() == "DUMMY":
            keyed["DUMMY"] = ""
        elif not k and (v == "*" or v.upper() == "DATA"):
            keyed["*"] = ""
    if (keyed.get("DSN") or keyed.get("DSNAME") or "").upper() == "NULLFILE":
        keyed["DUMMY"] = ""
    return keyed


def _dd_dsn(dk: Mapping[str, str], values: Mapping[str, str]) -> str | None:
    """The DSN a DD names after symbol substitution; None for a DUMMY / NULLFILE DD or one with no DSN."""
    dsn = _substitute(dk.get("DSN") or dk.get("DSNAME"), values)
    return None if "DUMMY" in dk else dsn


_MAX_LEVELS = 15


def _include_statements(
    member: str, order: list[str], libraries: Mapping[str, Mapping[str, str]], depth: int = 1
) -> list[tuple[int, str, str, str]]:
    """The statements of INCLUDE group `member`, nested INCLUDEs spliced in place (the group replaces the statement)."""
    if depth > _MAX_LEVELS:
        raise JclProcRefused(f"INCLUDE nested past {_MAX_LEVELS} levels is invalid (p. 376)")
    out: list[tuple[int, str, str, str]] = []
    for st in _statements(_find(member, order, libraries)):
        if st[2] == "INCLUDE":
            out += _include_statements(_keyword(st[3], "MEMBER").upper(), order, libraries, depth + 1)
        elif st[2] in ("JOB", "PROC", "PEND", "JCLLIB"):
            raise JclProcRefused(f"an INCLUDE group cannot hold a {st[2]} statement (invalid, p. 376)")
        else:
            out.append(st)
    return out


def _include_dds(member: str, order: list[str], libraries: Mapping[str, Mapping[str, str]]):
    """The DD statements of INCLUDE group `member` inside a procedure (an EXEC / SET there is not carried)."""
    out: list[tuple[str, dict[str, str]]] = []
    for _l, ddn, iop, ifield in _include_statements(member, order, libraries):
        if iop == "DD":
            out.append((ddn.upper(), _dd_keys(ifield)))
        elif iop != "OUTPUT":
            raise JclProcRefused(f"a {iop} statement in an INCLUDE group inside a procedure is not carried here")
    return out


def _splice_includes(
    stmts: list[tuple[int, str, str, str]], libraries: Mapping[str, Mapping[str, str]]
) -> list[tuple[int, str, str, str]]:
    """The job's statements with each job-level INCLUDE replaced by its group (EXEC and SET included, p. 376): symbol values
    a group's SET assigns hold for the statements after it. An INCLUDE inside an in-stream PROC .. PEND is left for the proc."""
    out: list[tuple[int, str, str, str]] = []
    order: list[str] = []
    in_proc = False
    for st in stmts:
        if st[2] == "JCLLIB":
            order = [x.strip().upper() for x in _keyword(st[3], "ORDER").strip("()").split(",") if x.strip()]
        elif st[2] == "PROC":
            in_proc = True
        elif st[2] == "PEND":
            in_proc = False
        if st[2] == "INCLUDE" and not in_proc:
            out += _include_statements(_keyword(st[3], "MEMBER").upper(), order, libraries)
        else:
            out.append(st)
    return out


def _proc_body(stmts: list[tuple[int, str, str, str]]) -> tuple[dict[str, str], list[tuple[int, str, str, str]]]:
    """The PROC statement's defaults and the statements up to PEND (or the end of a library member)."""
    defaults: dict[str, str] = {}
    body: list[tuple[int, str, str, str]] = []
    for _line, _name, op, field in stmts:
        if op == "PROC":
            defaults = {k: _parm(v, sublist=False) or "" for k, v in _first_wins(_split(field)).items()}
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
            keyed = _first_wins(ops)
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
            keyed = _dd_keys(field)
            ddname = name
            target = steps[-1]
            if "." in ddname:
                pstep, _, ddname = ddname.partition(".")
                if "." in ddname:
                    raise JclProcRefused(f"{name}: a backward reference procstep.procstep.ddname is invalid (rule 5)")
                target["dd_over"].append((pstep.upper(), ddname.upper(), keyed))
            else:
                target["dd"].append((ddname.upper(), keyed))
        elif op == "INCLUDE" and steps:
            steps[-1]["dd"] += _include_dds(_keyword(field, "MEMBER").upper(), order, libraries)
    return steps


def _load_proc(name: str, instream: Mapping[str, Any], order: list[str], libraries: Mapping[str, Mapping[str, str]]):
    if name in instream:
        return instream[name]  # p. 26
    return _proc_body(_statements(_find(name, order, libraries)))


def _expand_call(
    call: dict[str, Any],
    defaults: dict[str, str],
    body: list[tuple[int, str, str, str]],
    set_values: dict[str, str],
    order: list[str] | None = None,
    libraries: Mapping[str, Mapping[str, str]] | None = None,
    instream: Mapping[str, Any] | None = None,
    depth: int = 1,
) -> dict[str, dict[str, Any]]:
    """The steps of one procedure call, each procedure step keyed `CALLSTEP.PROCSTEP`. `set_values` is the symbol layer
    the call inherits (SET values at level 0, the calling procedure's values when nested: Table 13 rule 5)."""
    order, libraries, instream = order or [], libraries or {}, instream or {}
    keyed = call["keyed"]
    reserved = {"PROC", "PGM", "PARM", "COND", "RD", "ACCT", "TIME", "REGION", "ADDRSPC", "DYNAMNBR", "CCSID"}
    exec_values = {
        k: _substitute(_parm(v, sublist=False) or "", set_values) or ""
        for k, v in keyed.items()
        if k not in reserved and "." not in k
    }
    for kw in ("PARM", "COND"):
        if call["proc"] and kw in keyed and any(k.startswith(f"{kw}.") for k in keyed):
            raise JclProcRefused(f"{kw}= together with {kw}.procstep= on one call: precedence is not answered")
    values = {**set_values, **defaults, **exec_values}
    proc_steps = _step_dds(body, order, libraries)
    by_name = {ps["name"].upper(): ps for ps in proc_steps}
    for pstep, ddn, _dk in call["dd_over"]:
        if pstep not in by_name or by_name[pstep]["proc"]:
            raise JclProcRefused(
                f"{pstep}.{ddn} modifies a step that is absent from the procedure or itself calls one (rule 3)"
            )
    calls_inside = any(ps["proc"] for ps in proc_steps)
    if calls_inside and ("PARM" in keyed or "COND" in keyed):
        raise JclProcRefused("EXEC PARM= / COND= on a call of a procedure that calls procedures is not answered")
    out: dict[str, dict[str, Any]] = {}
    for index, ps in enumerate(proc_steps):
        if ps["proc"]:
            if depth >= _MAX_LEVELS:
                raise JclProcRefused(f"procedure nesting past {_MAX_LEVELS} levels is invalid (p. 32)")
            if any(k in keyed for k in (f"PARM.{ps['name']}", f"COND.{ps['name']}")):
                raise JclProcRefused(
                    "PARM.procstep= / COND.procstep= naming a step that calls a procedure is not answered"
                )
            inner_defaults, inner_body = _load_proc(ps["proc"], instream, order, libraries)
            inner = _expand_call(ps, inner_defaults, inner_body, values, order, libraries, instream, depth + 1)
            for ikey, ival in inner.items():  # A4: levels flattened under the outermost call step
                out[f"{call['name']}.{ikey.partition('.')[2]}"] = ival
            continue
        key = f"{call['name']}.{ps['name']}"
        parm = keyed.get(f"PARM.{ps['name']}", ps["parm"])
        cond = keyed.get(f"COND.{ps['name']}", ps["cond"])
        if (
            "PARM" in keyed
        ):  # JCL Reference, EXEC PARM: only the first procedure step gets it, later steps' PARM are nullified
            parm = (keyed["PARM"] or None) if index == 0 else None
        if "COND" in keyed:  # EXEC COND: replaces the step's COND, or is added where it has none: every procedure step
            cond = keyed["COND"] or None
        dds: dict[str, str | None] = {}
        for ddn, dk in ps["dd"]:
            dds[ddn] = _dd_dsn(dk, values)
        for pstep, ddn, dk in call["dd_over"]:
            if pstep != ps["name"].upper():
                continue
            if "DUMMY" in dk:  # DUMMY / DSN=NULLFILE on an override nullifies everything but DCB, the DSN included
                dds[ddn] = None
                continue
            if ("SYSOUT" in dk or "*" in dk) and (dds.get(ddn) or dk.get("DSN") or dk.get("DSNAME")):
                raise JclProcRefused("a SYSOUT / * / DATA override of a DD that names a DSN is not answered")
            dsn = dk.get("DSN") or dk.get("DSNAME")
            if dsn is not None or ddn not in dds:
                dds[ddn] = _substitute(
                    dsn, values
                )  # an added DD lands after the procedure's own; a DSN replaces in place
        out[key] = {
            "pgm": ps["pgm"],
            "parm": _parm(_substitute(parm, values)),
            "cond": _substitute(cond, values),
            "dd": {k: v for k, v in dds.items() if v is not None},
        }
    return out


def resolve_job(text: str, libraries: Mapping[str, Mapping[str, str]], job: str) -> dict[str, dict[str, Any]]:
    """Every EXEC of `job`, resolved. `libraries`: {library: {member: JCL text}}."""
    stmts = _splice_includes(_job_statements(text, job), libraries)
    order: list[str] = []
    instream: dict[str, tuple[dict[str, str], list[tuple[int, str, str, str]]]] = {}
    main: list[tuple[int, str, str, str]] = []
    i = 0
    while i < len(stmts):
        _line, name, op, field = stmts[i]
        if op == "JCLLIB":
            raw = _keyword(field, "ORDER")
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
            defaults, body = _load_proc(call["proc"], instream, order, libraries)
            out.update(_expand_call(call, defaults, body, in_force, order, libraries, instream))
        else:
            values = in_force
            out[call["name"]] = {
                "pgm": call["pgm"],
                "parm": _parm(_substitute(call["parm"], values)),
                "cond": _substitute(call["cond"], values),
                "dd": {k: v for k, v in ((n, _dd_dsn(d, values)) for n, d in call["dd"]) if v},
            }
    return out


def _library_order(text: str, job: str) -> list[str]:
    for _line, _name, op, field in _job_statements(text, job):
        if op == "JCLLIB":
            return [x.strip().upper() for x in _keyword(field, "ORDER").strip("()").split(",") if x.strip()]
    return []


def expand_flow_rows(
    rows: list[dict[str, Any]],
    job: str,
    text: str | None = None,
    libraries: Mapping[str, Mapping[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """The rows of `job` (JOB row first) with each procedure call replaced by its steps `CALLSTEP.PROCSTEP` (the call's
    IF condition kept, COND tests inside the procedure re-pointed at the qualified names, `COND.procstep=` applied).
    An in-stream procedure is used first (p. 26); otherwise, given the job's `text` and the `libraries`, the member is
    searched along the job's JCLLIB ORDER (first library wins, JCLLIB ORDER) and its steps are read as the in-stream ones are."""
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
            if text is None or libraries is None:
                raise JclProcRefused(f"procedure {r['proc']} is not in-stream and no libraries were given")
            member = _find(r["proc"], _library_order(text, job), libraries)
            procs[r["proc"]] = [m for m in jcl_job_flow(member) if m["kind"] == "STEP" and m["in_proc"]]
        if any(ps["proc"] for ps in procs[r["proc"]]):
            raise JclProcRefused("nested procedure calls in IF flow are not answered")
        over = {o["step"]: o["cond"] for o in r.get("cond_overrides", [])}
        call = r["step_name"]
        for ps in procs[r["proc"]]:
            cond = over.get(ps["step_name"], ps["cond"])
            if cond:
                cond = _COND_STEP.sub(rf"\g<1>{call}.\g<2>\g<3>", cond)
            row = dict(ps, step_name=f"{r['step_name']}.{ps['step_name']}", cond=cond, if_cond=r["if_cond"])
            row.pop("if_chain", None)
            if r.get("if_chain"):
                row["if_chain"] = r["if_chain"]
            out.append(row)
    return out
