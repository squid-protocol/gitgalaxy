"""#5859 slice 9: every assembler source in a burned estate is accounted for. The zECS programs lower through the HLASM
front end and use only its subset (no MVI, no high / low branch); CardDemo's two assembler files are batch library
routines that COBOL CALLs, modelled by runtime code, not lowered. A new burned `.asm` fails here until it is placed."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gitgalaxy.tools.cobol_to_java.det import hlasm  # noqa: E402

CORPORA = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", ROOT / ".mainframe_corpora"))
BURNED = (
    "aws-mainframe-modernization-carddemo",
    "cics-async-api-credit-card-application-example",
    "cics-banking-sample-application-cbsa",
    "cics-genapp",
    "dbb-mortgage-application",
    "zecs",
)
LOWERED = {"ZECSNC.asm", "ZECS002.asm"}
LIBRARY_MODELS = {"COBDATFT.asm", "MVSWAIT.asm"}  # oracle A1 / Mvswait.java: hand-written runtime, not lowered
DIRECTIVES = {"AMODE", "RMODE", "PRINT", "LTORG", "END", "EQU", "DC", "DS", "DSECT", "USING", "DFHEIENT", "EXEC"}

pytestmark = pytest.mark.skipif(not (CORPORA / "zecs").is_dir(), reason="no burned mainframe corpora")


def burned_asm() -> list[Path]:
    return sorted(p for name in BURNED for p in (CORPORA / name).rglob("*.asm"))


def test_each_burned_assembler_file_is_lowered_or_a_named_library_model():
    assert {p.name for p in burned_asm()} == LOWERED | LIBRARY_MODELS


def test_the_lowered_programs_stay_inside_the_subset_and_use_no_mvi():
    for p in burned_asm():
        if p.name not in LOWERED:
            continue
        ops = {s.op for s in hlasm.statements(p.read_text(encoding="latin-1"))}
        assert "MVI" not in ops, p.name
        assert ops <= hlasm.SUBSET | DIRECTIVES | hlasm._IGNORED, (p.name, sorted(ops - hlasm.SUBSET - DIRECTIVES))
