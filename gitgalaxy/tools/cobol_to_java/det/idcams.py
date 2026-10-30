"""An IDCAMS REPRO step as a plain record copy (#4268): the command a step's SYSIN holds, parsed into the two DDs it
names and the COPY model det/dfsort.py already lowers to a COBOL program (cobolrt/Sort, GnuCOBOL as the oracle).

The model (IBM z/OS DFSMS Access Method Services for Catalogs, SC23-6853, "REPRO"; "Modal commands"; "Continuing
commands and comments"):

* `REPRO INFILE(dd) OUTFILE(dd)` (IFILE / OFILE are the abbreviations) copies the input data set's records to the
  output, in order, for sequential data sets (the caller states that both DDs are sequential: SYSIN cannot tell).
* A command continues on the next line after a trailing `-` (or `+`); `/* ... */` comments may stand anywhere.
* One command only. Every other command (DEFINE, DELETE, ALTER, LISTCAT, PRINT, VERIFY, SET ...), every other REPRO
  parameter (INDATASET / OUTDATASET, FROMKEY, SKIP, COUNT, REPLACE, REUSE, ENCIPHER ...) and a DD with a password is
  refused by name.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .dfsort import Control, Refused

_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_PARAM = re.compile(r"\s*([A-Za-z][A-Za-z0-9]*)(?:\s*\(([^()]*)\))?")
_DD = re.compile(r"[A-Z#@$][A-Z0-9#@$]{0,7}$")
_ALIAS = {"INFILE": "INFILE", "IFILE": "INFILE", "OUTFILE": "OUTFILE", "OFILE": "OUTFILE"}


@dataclass(frozen=True)
class Repro:
    infile: str
    outfile: str

    @property
    def control(self) -> Control:
        """The copy, in dfsort's model."""
        return Control("COPY", (), None, False, False)


def _commands(sysin: str) -> list[str]:
    """Each command of `sysin`, comments dropped and continuation lines joined."""
    text = _COMMENT.sub(" ", sysin)
    if "/*" in text or "*/" in text:
        raise Refused("an unterminated comment")
    out: list[str] = []
    cur = ""
    for raw in text.splitlines():
        line = raw[:72].strip()
        if not line:
            continue
        if line[-1] in "-+":
            cur += line[:-1] + " "
            continue
        out.append((cur + line).strip())
        cur = ""
    if cur.strip():
        out.append(cur.strip())
    return out


def parse(sysin: str) -> Repro:
    """The REPRO command in `sysin` as the DDs it copies; anything else is refused by name."""
    cmds = _commands(sysin)
    if not cmds:
        raise Refused("no IDCAMS command")
    if len(cmds) > 1:
        raise Refused("more than one IDCAMS command")
    verb, _, rest = cmds[0].partition(" ")
    verb = verb.upper()
    if verb != "REPRO":
        raise Refused(f"the IDCAMS {verb} command")
    dds: dict[str, str] = {}
    pos = 0
    while pos < len(rest.rstrip()):
        m = _PARAM.match(rest, pos)
        if not m:
            raise Refused(f"an IDCAMS REPRO operand ({rest[pos:].strip()[:20]})")
        name = m.group(1).upper()
        if name not in _ALIAS:
            raise Refused(f"the IDCAMS REPRO {name} parameter")
        key = _ALIAS[name]
        if key in dds:
            raise Refused(f"the IDCAMS REPRO {key} parameter twice")
        dd = (m.group(2) or "").strip().upper()
        if "/" in dd:
            raise Refused(f"the IDCAMS REPRO {key} password")
        if not _DD.match(dd):
            raise Refused(f"the IDCAMS REPRO {key} value ({dd or 'empty'}) is not a DD name")
        dds[key] = dd
        pos = m.end()
    for key in ("INFILE", "OUTFILE"):
        if key not in dds:
            raise Refused(f"the IDCAMS REPRO without {key}")
    return Repro(dds["INFILE"], dds["OUTFILE"])
