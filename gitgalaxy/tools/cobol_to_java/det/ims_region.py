"""A DFSRRC00 step's PARM as the IMS region it starts, not the program's parameter (#4890):

    //BMP  EXEC PGM=DFSRRC00,PARM='BMP,POSTIT,POSTPSB'

The model (IBM IMS System Definition / System Administration, "IMS procedures" and "DFSRRC00 execution parameters", read
from memory, not re-read offline: ASSUMED, recorded with the register row):

* Positions 1-3 are the region type (`DLI`, `DBB` or `BMP`), the application program (load module) and its PSB. DFSRRC00 is
  IMS's region controller, so the whole string is IMS's own: the application is never handed it as a PARM (IMS passes
  the PSB's PCBs through the CALL's USING list instead, `det/program.py` `dli_pcbs`).
* Positions 4 on are IMS region options (buffers, IMSID, DBRC, ...). The oracle has no IMS control region, so they are
  refused by name rather than dropped, as is any other region type and a symbolic (`&NAME`) value.
* The PSB and the region type are recorded, not compared: no PSB / DBD is read here (the DL/I model's own PCBs are the
  program's input, `I1`-`I6`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .dfsort import Refused

_NAME = re.compile(r"[A-Z0-9@#$]{1,8}")
_REGIONS = frozenset({"DLI", "DBB", "BMP"})


@dataclass(frozen=True)
class Region:
    region: str
    program: str
    psb: str | None  # None when the PARM leaves it out


def parse(parm: str | None) -> Region:
    """The region type, program and PSB of a DFSRRC00 PARM; anything beyond them is refused by name."""
    if parm is None or not parm.strip():
        raise Refused("no DFSRRC00 PARM (the region type and program come from it)")
    if "&" in parm:
        raise Refused("a symbolic DFSRRC00 PARM value (not resolved here)")
    parts = [p.strip().upper() for p in parm.split(",")]
    region = parts[0]
    if region not in _REGIONS:
        raise Refused(f"the DFSRRC00 region type {region or 'empty'!r} (only DLI, DBB and BMP run as a batch step)")
    program = parts[1] if len(parts) > 1 else ""
    if not _NAME.fullmatch(program):
        raise Refused(f"the DFSRRC00 program ({program or 'empty'}) is not a load module name")
    psb = parts[2] if len(parts) > 2 and parts[2] else None
    if psb is not None and not _NAME.fullmatch(psb):
        raise Refused(f"the DFSRRC00 PSB ({psb}) is not a name")
    for n, extra in enumerate(parts[3:], start=4):
        if extra:
            raise Refused(
                f"the DFSRRC00 PARM position {n} ({extra[:12]!r}), an IMS region option the oracle has no model of"
            )
    return Region(region, program, psb)
