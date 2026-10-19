"""#5126 (register X64): EIBFN and EIBRCODE (and the other EIB fields no harness states) are not modelled, because IBM's
function-code and condition tables are not at hand and no whole burned program reads them. This pins the reading: the
burned estates' COBOL reads these fields only in the programs X64 names, so a new reader fails here and sends whoever
finds it to model the field (EIBFN per IBM's function-code table, EIBRCODE per condition row) rather than to a silent
`fact:` gap. Burned estates only (the census and blind-estate clones are never opened)."""

import os
import sys
from pathlib import Path

import pytest

from gitgalaxy.core.source_text import read_source

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "tools"))
sys.path.insert(0, str(HERE))
import proof_blockers as pb  # noqa: E402

UNMODELLED = ("EIBFN", "EIBRCODE", "EIBCPOSN", "EIBREQID", "EIBRSRCE", "EIBERR", "EIBERRCD")
# the burned corpus directories (estate4_draw.BURNED_NAMES) that hold COBOL
BURNED_DIRS = (
    "aws-mainframe-modernization-carddemo",
    "cics-async-api-credit-card-application-example",
    "cics-banking-sample-application-cbsa",
    "cics-genapp",
    "dbb-mortgage-application",
    "zecs",
)
# program -> the unmodelled EIB fields it reads (register X64: ZECS001 translates with holes and has no case)
KNOWN_READERS = {"ZECS001": {"EIBRCODE"}}
SUFFIXES = {".cbl", ".cob", ".cobol"}


def _corpora() -> Path:
    root = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    if not root or not Path(root).is_dir():
        pytest.skip("GITGALAXY_MAINFRAME_CORPORA is not set")
    return Path(root)


def _readers() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for name in BURNED_DIRS:
        base = _corpora() / name
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if path.suffix.lower() not in SUFFIXES or not path.is_file():
                continue
            text = read_source(path).text
            if "EIB" not in text.upper():
                continue
            names = set(pb.facts_needed(text)["eib"]) & set(UNMODELLED)
            if names:
                found.setdefault(path.stem.upper(), set()).update(names)
    return found


def test_the_unmodelled_eib_fields_stay_unmodelled_and_named():
    # the gap is by name: a program that reads one is a `fact:` gap, not a silent zero
    assert set(UNMODELLED) <= pb.EIB_FIELDS
    assert not set(UNMODELLED) & pb.STATED_EIB
    assert not set(UNMODELLED) & pb.CASE_STATED_EIB


def test_only_the_named_burned_programs_read_the_unmodelled_eib_fields():
    assert _readers() == KNOWN_READERS, (
        "a burned program reads an EIB field X64 leaves unmodelled: model it (EIBFN per IBM's function-code table, "
        "EIBRCODE per condition row), state it in the harness, then update X64 and KNOWN_READERS"
    )
