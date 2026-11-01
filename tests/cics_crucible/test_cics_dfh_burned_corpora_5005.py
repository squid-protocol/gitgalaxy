"""#5005 (register X42 / X44): the burned estates name no CICS-defined (DFH...) container or channel beyond the ones the
engine already runs. IBM lists no CICS-defined read-only names, so every command that could write one refuses a DFH name
by name; this pins the claim that no burned program needs more than the exceptions:

* `DFHREQUEST`, `DFH-BODY`, `DFH-DATA`: the pipeline containers DBB `epscsmrd.cbl` reads and PUTs back (PUT runs them as ordinary);
* `DFHEP.EVENT`, `DFHEP.CCECONTEXT`, `DFHEP.DATA.00001`, `DFHEP.DATA.00002`: the event-processing channel and containers GenApp
  `lgastat1.cbl` only reads (GET), a channel the harness hands the task.

A new quoted DFH literal in a burned COBOL source fails here, so its command gets a stated disposition (or a refusal) before it
ships, instead of silently hitting the by-name refusal."""

import os
import re
from pathlib import Path

import pytest

from gitgalaxy.core.source_text import read_source

# the burned estates (tests/tools/estate4_draw.BURNED_NAMES), as the directory names under the corpora root
BURNED_DIRS = (
    "aws-mainframe-modernization-carddemo",
    "cics-banking-sample-application-cbsa",
    "cics-genapp",
    "zecs",
    "dbb-mortgage-application",
    "cics-async-api-credit-card-application-example",
)
SOURCE_SUFFIXES = {".cbl", ".cob", ".cobol", ".cpy"}
ALLOWED = {
    "DFHREQUEST": "cics_defined_put_exception",
    "DFH-BODY": "cics_defined_put_exception",
    "DFH-DATA": "cics_defined_put_exception",
    "DFHEP.EVENT": "read_only_in_scope",
    "DFHEP.CCECONTEXT": "read_only_in_scope",
    "DFHEP.DATA.00001": "read_only_in_scope",
    "DFHEP.DATA.00002": "read_only_in_scope",
}
_DFH_LITERAL = re.compile(r"""(['"])\s*(DFH[^'"]*)\1""", re.IGNORECASE)


def dfh_names(cobol: str) -> set[str]:
    """Upper-cased quoted DFH names in the code area of fixed-format COBOL (comment lines skipped).
    `DFHCOMMAREA/...` is a field path in a mapping literal, not a container or channel name."""
    found = set()
    for line in cobol.splitlines():
        if len(line) > 6 and line[6] in "*/":
            continue
        for m in _DFH_LITERAL.finditer(line[:72]):
            name = m.group(2).strip().upper()
            if not name.startswith("DFHCOMMAREA"):
                found.add(name)
    return found


def _burned_sources() -> list[Path]:
    env = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    root = Path(env) if env else Path(__file__).resolve().parents[2] / ".mainframe_corpora"
    out: list[Path] = []
    for d in BURNED_DIRS:
        base = root / d
        if base.is_dir():
            out += [p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in SOURCE_SUFFIXES]
    return sorted(out)


def test_dfh_names_are_read_from_code_not_comments_or_field_paths():
    assert dfh_names("           EXEC CICS PUT CONTAINER('DFHXYZ')\n") == {"DFHXYZ"}
    assert dfh_names('           EXEC CICS DELETE CHANNEL("dfhevent")\n') == {"DFHEVENT"}
    assert dfh_names("      * a comment about 'DFHTRANSACTION'\n") == set()
    assert dfh_names("           MOVE 'DFHCOMMAREA/EPSPCOM_X' TO F\n") == set()
    assert dfh_names("           IF EIBRESP = DFHRESP(NORMAL) MOVE DFHCOMMAREA TO X\n") == set()
    assert dfh_names("           MOVE ' DFHREQUEST' TO F\n") == {"DFHREQUEST"}


def test_every_allowed_name_has_a_stated_disposition():
    assert set(ALLOWED.values()) == {"cics_defined_put_exception", "read_only_in_scope"}


def test_the_burned_estates_name_no_other_dfh_container_or_channel():
    sources = _burned_sources()
    if not sources:
        pytest.skip("no burned estate under GITGALAXY_MAINFRAME_CORPORA")
    seen: dict[str, set[str]] = {}
    for p in sources:
        for name in dfh_names(read_source(p).text):
            seen.setdefault(name, set()).add(p.name)
    unexpected = {n: sorted(f) for n, f in seen.items() if n not in ALLOWED}
    assert not unexpected, (
        f"a burned program names a DFH literal with no stated disposition (X42 / X44; PUT, MOVE and DELETE refuse it by name): {unexpected}"
    )
