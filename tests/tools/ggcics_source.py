"""#5274: the text of the CICS stub as one source. ggcics.c includes its families where each block sat, so a test that
reads a stub function by its text reads this, not ggcics.c alone. The families with a part guard or a test of their own
(ggcics_web.c, ggcics_containers.c ...) stay as #include lines: these eight are the plain cuts that hold no guard."""

from __future__ import annotations

import re
from pathlib import Path

STUB_DIR = Path(__file__).resolve().parents[1] / "equivalence" / "cics"
PLAIN_FAMILIES = ("filewrite", "terminal", "program", "inquire", "counters", "system", "storage", "setforms")
_INCLUDE = re.compile(r'^#include "ggcics_(' + "|".join(PLAIN_FAMILIES) + r')\.c".*$', re.M)


def stub_source() -> str:
    """ggcics.c with each plain family's text at its #include."""
    host = (STUB_DIR / "ggcics.c").read_text(encoding="utf-8")
    return _INCLUDE.sub(lambda m: (STUB_DIR / f"ggcics_{m[1]}.c").read_text(encoding="utf-8"), host)
