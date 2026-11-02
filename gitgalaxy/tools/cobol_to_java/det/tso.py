"""An IKJEFT01 step's SYSTSIN as the one program it runs and the PARM that program gets (#4890): the Db2 batch idiom

    DSN SYSTEM(ssid)
    RUN PROGRAM(prog) PLAN(plan) LIB('load.library') PARMS('text')
    END

The model (IBM Db2 for z/OS Commands, "DSN (TSO)" and "RUN (DSN)"; z/OS TSO/E Command Reference, "Continuing a
command"):

* `DSN SYSTEM(ssid)` connects to the Db2 subsystem; `RUN PROGRAM(prog)` runs the load module with the PLAN and LIB the
  command names; `PARMS('text')` is the program's parameter string (the way EXEC PARM= is for a plain step); `END`
  leaves DSN. A command continues on the next line after a trailing `-` (or `+`).
* The oracle has no Db2 subsystem and no plan, so SSID, PLAN and LIB are recorded, not compared: only PROGRAM and
  PARMS reach the program. A step with Db2 statements in the program still needs the Db2 oracle (a separate case).
* One RUN only. Every other subcommand (BIND, REBIND, FREE, RETRY, SPUFI, ...), any other RUN keyword (CP, NOCP,
  IOSTAT ...), a PARMS that is not one quoted string and a second DSN is refused by name.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .dfsort import Refused

_NAME = r"[A-Za-z0-9@#$]{1,8}"
_KEY = re.compile(r"\s*([A-Za-z]+)\s*(?:\(\s*(.*?)\s*\))?(?=\s|$)", re.DOTALL)
_PARMS = re.compile(r"\bPARMS\s*\(\s*'((?:[^']|'')*)'\s*\)", re.IGNORECASE)
_QUOTED = re.compile(r"'(?:[^']|'')*'")
_ALLOWED = {"PROGRAM": "PROGRAM", "PROG": "PROGRAM", "PLAN": "PLAN", "LIB": "LIB", "PARMS": "PARMS"}
_OTHER = "a TSO / DSN subcommand the oracle has no model of"


@dataclass(frozen=True)
class Run:
    program: str
    ssid: str | None
    plan: str | None
    lib: str | None
    parms: str | None  # the program's parameter string, quotes undoubled


def _commands(text: str) -> list[str]:
    out: list[str] = []
    cur = ""
    for raw in text.splitlines():
        line = raw[:72].strip()
        if not line:
            continue
        if line[-1] in "-+":
            cur += line[:-1].rstrip() + " "
            continue
        out.append((cur + line).strip())
        cur = ""
    if cur.strip():
        out.append(cur.strip())
    return out


def _operands(rest: str, verb: str) -> dict[str, str]:
    """`KEY(value)` operands of a RUN command; quoted values are masked so a `)` inside PARMS cannot end one."""
    masked = _QUOTED.sub(lambda m: "\x00" * len(m.group(0)), rest)
    found: dict[str, str] = {}
    pos = 0
    while pos < len(rest.rstrip()):
        m = _KEY.match(masked, pos)
        if not m or m.end() == pos:
            raise Refused(f"the {verb} operand {rest[pos:].strip()[:20]!r}")
        name = m.group(1).upper()
        key = _ALLOWED.get(name)
        if key is None:
            raise Refused(f"the {verb} {name} keyword")
        if key in found:
            raise Refused(f"the {verb} {key} keyword twice")
        found[key] = rest[m.start(2) : m.end(2)] if m.group(2) is not None else ""
        pos = m.end()
    return found


def parse(systsin: str) -> Run:
    """The one RUN PROGRAM in `systsin`; anything else is refused by name."""
    run: Run | None = None
    ssid: str | None = None
    seen_dsn = False
    for cmd in _commands(systsin):
        verb, _, rest = cmd.partition(" ")
        verb = verb.upper()
        if verb == "DSN":
            if seen_dsn:
                raise Refused("a second DSN command")
            seen_dsn = True
            m = re.fullmatch(rf"\s*SYSTEM\s*\(\s*({_NAME})\s*\)\s*", rest, re.IGNORECASE)
            if rest.strip() and not m:
                raise Refused(f"the DSN operand {rest.strip()[:20]!r} ({_OTHER})")
            ssid = m.group(1).upper() if m else None
        elif verb == "RUN":
            if run is not None:
                raise Refused("more than one RUN PROGRAM")
            if not seen_dsn:
                raise Refused("a RUN without a DSN command before it")
            ops = _operands(rest, "RUN")
            prog = ops.get("PROGRAM", "").strip().strip("'").upper()
            if not re.fullmatch(_NAME, prog):
                raise Refused(f"the RUN PROGRAM value ({prog or 'empty'}) is not a load module name")
            parms = None
            if "PARMS" in ops:
                m = _PARMS.search(rest)
                if not m:
                    raise Refused("a RUN PARMS that is not one quoted string")
                parms = m.group(1).replace("''", "'")
            plan = ops.get("PLAN", "").strip().strip("'").upper() or None
            lib = ops.get("LIB", "").strip().strip("'") or None
            run = Run(prog, ssid, plan, lib, parms)
        elif verb == "END":
            if rest.strip():
                raise Refused("an END with operands")
        else:
            raise Refused(f"the {verb} command ({_OTHER})")
    if run is None:
        raise Refused("no RUN PROGRAM")
    return run
