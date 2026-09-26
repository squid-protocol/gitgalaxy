# ==============================================================================
# GitGalaxy Core: the program a batch runner runs (#3710)
#
# PURPOSE:
# A batch program is often not `EXEC PGM=<program>` but run through a runner, and
# the step's PGM= then names the runner, not the program:
#
#   runner                  the program it runs                         via
#   IKJEFT01 / 1A / 1B      in-stream SYSTSIN `RUN PROGRAM(x) PLAN(p)`   RUN PROGRAM
#   (TSO batch)             in-stream SYSTSIN `CALL 'lib(x)'`            TSO CALL
#                           in-stream SYSTSIN `EXEC 'lib(x)'` / `%x`     TSO EXEC (a REXX / CLIST
#                                                                        exec, not a load module)
#   DFSRRC00 (IMS)          PARM='region,x,psb'                          DFSRRC00
#
# One row per program run: `line` (of the step's EXEC), `step`, `runner`, `program`,
# `via`, `plan` (RUN PROGRAM's PLAN), `region` / `psb` (DFSRRC00), `at` (the line
# naming the program), and for a SYSTSIN that is a dataset rather than in-stream,
# `member` -- the member it names (`DSN=&LBNM..CNTL(DB2TEP41)`), with `program`
# None: the commands live in that member, which the reader resolves where the
# repository holds it. An in-stream SYSTSIN whose commands run no program (DSN FREE /
# BIND, RACF) is one row with `program` None and `via` "TSO commands".
#
# SCOPE AND NON-SCOPE:
#   - Extraction only, per file, over the code stream: in-stream data is kept there
#     (it ends a continued JCL statement), which is where SYSTSIN's commands are.
#   - A TSO command continues onto the next line when it ends in `-` or `+`.
#   - DSN SYSTEM(...), END, FREE, BIND and other commands run nothing.
# ==============================================================================
import re
from typing import Any, Optional

_TSO_RUNNERS = frozenset({"IKJEFT01", "IKJEFT1A", "IKJEFT1B"})
_STMT = re.compile(r"^//([A-Z0-9@#$.]{0,17})[ \t]+([A-Z]{2,8})(?:[ \t]+(.*))?$", re.I)
_PGM = re.compile(r"\bPGM=([A-Z0-9@#$]{1,8})", re.I)
_INSTREAM = re.compile(r"^[ \t]*(?:\*|DATA)(?![A-Z0-9@#$])", re.I)
_MEMBER = re.compile(r"\bDSN=[^,( \t]*\(([A-Z0-9@#$]{1,8})\)", re.I)
_REGION_PARM = re.compile(r"\bPARM=\(?'?([^')]*)", re.I)
# `RUN PROGRAM(X)` / `RUN PROG(X)` (a quoted name too), `PLAN(P)` anywhere in the command.
_RUN = re.compile(r"^RUN\s+PROG(?:RAM)?\s*\(\s*'?([A-Z0-9@#$]{1,8})'?\s*\)", re.I)
_PLAN = re.compile(r"\bPLAN\s*\(\s*'?([A-Z0-9@#$]{1,8})'?\s*\)", re.I)
# TSO CALL 'lib(X)' / CALL lib(X) / CALL 'X': a load module.
_CALL = re.compile(r"^CALL\s+'?(?:[^'()\s]*\(\s*([A-Z0-9@#$]{1,8})\s*\)|([A-Z0-9@#$]{1,8}))'?", re.I)
# TSO EXEC 'lib(X)' / EX lib(X) / %X / a bare implicit exec is not recognised (it
# is indistinguishable from any other command).
_EXEC = re.compile(r"^(?:EXEC|EX)\s+'?(?:[^'()\s]*\(\s*([A-Z0-9@#$]{1,8})\s*\)|([A-Z0-9@#$]{1,8}))'?", re.I)
_PERCENT = re.compile(r"^%([A-Z0-9@#$]{1,8})\b", re.I)


def _commands(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """(line, command) from in-stream TSO input: `-` / `+` at the end continues a command."""
    out: list[tuple[int, str]] = []
    pending: Optional[list] = None
    for no, raw in lines:
        text = raw[:72].strip()
        if not text:
            continue
        cont = text.endswith(("-", "+"))
        body = text[:-1].rstrip() if cont else text
        if pending is None:
            pending = [no, body]
        else:
            pending[1] += " " + body
        if not cont:
            out.append((pending[0], pending[1]))
            pending = None
    if pending is not None:
        out.append((pending[0], pending[1]))
    return out


def _tso_rows(base: dict[str, Any], commands: list[tuple[int, str]]) -> list[dict[str, Any]]:
    rows = []
    for no, cmd in commands:
        run = _RUN.match(cmd)
        if run:
            plan = _PLAN.search(cmd)
            rows.append({**base, "program": run.group(1).upper(), "via": "RUN PROGRAM",
                         "plan": plan.group(1).upper() if plan else None, "at": no})  # fmt: skip
            continue
        call = _CALL.match(cmd)
        if call:
            rows.append({**base, "program": (call.group(1) or call.group(2)).upper(), "via": "TSO CALL", "at": no})
            continue
        ex = _EXEC.match(cmd) or _PERCENT.match(cmd)
        if ex:
            name = next(g for g in ex.groups() if g)
            rows.append({**base, "program": name.upper(), "via": "TSO EXEC", "at": no})
    return rows


def runner_targets(code_stream: str) -> list[dict[str, Any]]:
    """Every program a runner step runs (see above), in source order."""
    lines = code_stream.split("\n")
    rows: list[dict[str, Any]] = []
    step: Optional[dict[str, Any]] = None  # the current EXEC: line, step, runner
    i = 0
    while i < len(lines):
        line = lines[i][:72].rstrip()
        m = _STMT.match(line) if line.startswith("//") and not line.startswith("//*") else None
        if m is None:
            i += 1
            continue
        op, name = m.group(2).upper(), m.group(1).upper()
        if op == "EXEC":
            # the EXEC may continue: PGM= and PARM= can sit on following `//` lines
            text, j = line, i
            while text.rstrip().endswith(",") and j + 1 < len(lines) and lines[j + 1].startswith("//") \
                    and not lines[j + 1].startswith("//*") and not _STMT.match(lines[j + 1][:72].rstrip() or " "):  # fmt: skip
                j += 1
                text += lines[j][2:72].strip()
            pgm = _PGM.search(text)
            runner = pgm.group(1).upper() if pgm else None
            step = {"line": i + 1, "step": name or None, "runner": runner} if runner else None
            if step is not None and runner == "DFSRRC00":
                parm = _REGION_PARM.search(text)
                parts = [p.strip().upper() for p in parm.group(1).split(",")] if parm else []
                if len(parts) > 1 and parts[1]:
                    rows.append({**step, "program": parts[1], "via": "DFSRRC00", "region": parts[0] or None,
                                 "psb": parts[2] if len(parts) > 2 and parts[2] else None, "at": i + 1})  # fmt: skip
            i = j + 1
            continue
        if op in ("JOB", "PROC", "PEND"):
            step = None
        if op == "DD" and step and step["runner"] in _TSO_RUNNERS and name == "SYSTSIN":
            operands = m.group(3) or ""
            if _INSTREAM.match(operands):
                data: list[tuple[int, str]] = []
                j = i + 1
                while j < len(lines) and not lines[j].startswith(("//", "/*")):
                    data.append((j + 1, lines[j]))
                    j += 1
                ran = _tso_rows(step, _commands(data))
                # commands only (DSN FREE / BIND, RACF): recorded as such, so "nothing found" stays apart
                rows.extend(ran or [{**step, "program": None, "via": "TSO commands", "at": i + 1}])
                i = j
                continue
            member = _MEMBER.search(operands)
            if member:
                rows.append({**step, "program": None, "via": "SYSTSIN member", "member": member.group(1).upper(),
                             "at": i + 1})  # fmt: skip
        i += 1
    for r in rows:
        for k in ("plan", "region", "psb", "member"):
            r.setdefault(k, None)
    return rows


def systsin_programs(text: str) -> list[dict[str, Any]]:
    """The programs a SYSTSIN member's TSO commands run (a `.ctl` member a runner step
    reads by DSN): the same rows as in-stream SYSTSIN, without the step fields."""
    base: dict[str, Any] = {}
    rows = _tso_rows(base, _commands([(n, t) for n, t in enumerate(text.split("\n"), 1)]))
    for r in rows:
        r.setdefault("plan", None)
    return rows
