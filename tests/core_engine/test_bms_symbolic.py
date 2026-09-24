"""
#3490: COBOL symbolic maps generated from BMS source (core/bms_symbolic.py) -- the
exact DFHMAPS layout (TIOA prefix, L/F/A/I and the O record REDEFINES, extended
attribute bytes from DSATTS / EXTATT, PICIN / PICOUT, OCCURS), and a byte-for-byte
oracle against the generated copybooks CardDemo checks in beside its BMS sources.
"""

import os
from pathlib import Path

import pytest

from gitgalaxy.core.bms_screen_fields import bms_screen_fields
from gitgalaxy.core.bms_symbolic import symbolic_maps


def _bms(*statements: str) -> str:
    """BMS statements, each continued at column 72 with operands resuming at column 16."""
    out = []
    for stmt in statements:
        head, *more = stmt.split("|")
        if not more:
            out.append(head)
            continue
        out.append(head.ljust(71) + "-")
        for i, m in enumerate(more):
            line = " " * 15 + m
            out.append(line.ljust(71) + "-" if i < len(more) - 1 else line)
    return "\n".join(out) + "\n"


def test_layout_prefix_attributes_pictures_and_occurs():
    src = _bms(
        "MS1     DFHMSD TYPE=&&SYSPARM,LANG=COBOL,MODE=INOUT,|TIOAPFX=YES,|DSATTS=(COLOR,HILIGHT)",
        "MAP1    DFHMDI SIZE=(24,80)",
        "        DFHMDF POS=(1,1),LENGTH=5,INITIAL='Name:'",
        "NAME    DFHMDF POS=(1,7),LENGTH=10,ATTRB=UNPROT",
        "AMT     DFHMDF POS=(2,7),LENGTH=6,PICIN='999999',PICOUT='ZZZZZ9'",
        "ROW     DFHMDF POS=(4,1),LENGTH=3,OCCURS=2",
        "        DFHMSD TYPE=FINAL",
    )
    assert symbolic_maps(bms_screen_fields(src)) == {
        "MS1": "\n".join(
            [
                "       01  MAP1I.",
                "           02  FILLER PIC X(12).",
                "           02  NAMEL    COMP  PIC  S9(4).",
                "           02  NAMEF    PICTURE X.",
                "           02  FILLER REDEFINES NAMEF.",
                "             03 NAMEA    PICTURE X.",
                "           02  FILLER   PICTURE X(2).",
                "           02  NAMEI  PIC X(10).",
                "           02  AMTL    COMP  PIC  S9(4).",
                "           02  AMTF    PICTURE X.",
                "           02  FILLER REDEFINES AMTF.",
                "             03 AMTA    PICTURE X.",
                "           02  FILLER   PICTURE X(2).",
                "           02  AMTI  PIC 999999.",
                "           02  ROWD OCCURS 2 TIMES.",
                "             03  ROWL    COMP  PIC  S9(4).",
                "             03  ROWF    PICTURE X.",
                "             03  FILLER REDEFINES ROWF.",
                "               04 ROWA    PICTURE X.",
                "             03  FILLER   PICTURE X(2).",
                "             03  ROWI  PIC X(3).",
                "       01  MAP1O REDEFINES MAP1I.",
                "           02  FILLER PIC X(12).",
                "           02  FILLER PICTURE X(3).",
                "           02  NAMEC    PICTURE X.",
                "           02  NAMEH    PICTURE X.",
                "           02  NAMEO  PIC X(10).",
                "           02  FILLER PICTURE X(3).",
                "           02  AMTC    PICTURE X.",
                "           02  AMTH    PICTURE X.",
                "           02  AMTO  PIC ZZZZZ9.",
                "           02  DFHMS1 OCCURS 2 TIMES.",
                "             03  FILLER PICTURE X(3).",
                "             03  ROWC    PICTURE X.",
                "             03  ROWH    PICTURE X.",
                "             03  ROWO  PIC X(3).",
            ]
        )
        + "\n"
    }


def test_no_prefix_and_no_attributes():
    src = _bms("MS2     DFHMSD TYPE=MAP,LANG=COBOL", "M2      DFHMDI SIZE=(24,80)", "F1      DFHMDF POS=(1,1),LENGTH=2")
    text = symbolic_maps(bms_screen_fields(src))["MS2"]
    assert "X(12)" not in text and "F1C" not in text and "FILLER   PICTURE" not in text


_CARDDEMO = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", "/nonexistent")) / "aws-mainframe-modernization-carddemo"


def _norm(text: str) -> list[str]:
    out = []
    for line in text.split("\n"):
        line = line[:72]
        if len(line) > 6 and line[6] in "*/":
            continue
        body = " ".join(line[7:].split())
        if body:
            out.append(body)
    return out


@pytest.mark.skipif(not _CARDDEMO.is_dir(), reason="the pinned CardDemo corpus is not cloned")
def test_matches_every_generated_copybook_carddemo_checks_in():
    checked = 0
    for bms in sorted(_CARDDEMO.rglob("*.bms")):
        src = "\n".join("" if ln.startswith("*") else ln for ln in bms.read_text().split("\n"))
        copybook = next(p for p in bms.parent.parent.rglob("*") if p.parent.name == "cpy-bms" and p.stem == bms.stem)
        (text,) = symbolic_maps(bms_screen_fields(src)).values()
        assert _norm(text) == _norm(copybook.read_text()), bms.name
        checked += 1
    assert checked == 21
