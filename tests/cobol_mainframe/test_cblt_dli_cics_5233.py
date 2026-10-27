"""#5233 (register I5), checklist [c:5255ebd4]: CALL 'CBLTDLI' from a CICS program is needed by no burned program, so
the CICS harness refuses it by name and this census pins that: a burned program that starts to need it fails here."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import equivalence_cics as ec  # noqa: E402

from gitgalaxy.core.source_text import read_source  # noqa: E402

CORPORA = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", ROOT / ".mainframe_corpora"))
BURNED = ["aws-mainframe-modernization-carddemo", "cics-banking-sample-application-cbsa", "cics-genapp",
          "dbb-mortgage-application", "zecs", "cics-async-api-credit-card-application-example"]  # fmt: skip
AUTH = CORPORA / "aws-mainframe-modernization-carddemo" / "app" / "app-authorization-ims-db2-mq" / "cbl"


def _code(text: str) -> str:
    return " ".join(ln[7:72] for ln in text.splitlines() if len(ln) > 7 and ln[6] not in "*/").upper()


def _sources():
    for name in BURNED:
        for p in sorted((CORPORA / name).rglob("*")):
            if p.is_file() and p.suffix.lower() in (".cbl", ".cob", ".cpy"):
                yield p, _code(read_source(p).text)


def _src(stmt: str) -> str:
    lines = [
        "IDENTIFICATION DIVISION.",
        "PROGRAM-ID. DLICALL.",
        "PROCEDURE DIVISION.",
        f"    {stmt}",
        "    EXEC CICS RETURN END-EXEC.",
    ]
    return "\n".join(" " * 7 + ln for ln in lines) + "\n"


@pytest.mark.parametrize("name", ["CBLTDLI", "AIBTDLI", "CEETDLI"])
def test_a_call_interface_to_dli_is_refused_by_name_under_cics(name):
    with pytest.raises(ec.Unsupported, match=name):
        ec.refuse_dli_call_interface(_src(f"CALL '{name}' USING FN PCB IOA"))


def test_exec_dli_and_a_commented_call_are_not_refused():
    ec.refuse_dli_call_interface(_src("EXEC DLI SCHD PSB(P) END-EXEC"))
    ec.refuse_dli_call_interface(
        _src("DISPLAY 'X'").replace("       PROCEDURE", "      *CALL 'CBLTDLI'\n       PROCEDURE")
    )


@pytest.mark.skipif(not AUTH.is_dir(), reason="needs the CardDemo corpus (GITGALAXY_MAINFRAME_CORPORA)")
def test_no_burned_cics_program_calls_cbltdli():
    batch = set()
    for path, code in _sources():
        if re.search(r"\bCALL\s+'(CBLTDLI|AIBTDLI|CEETDLI)'", code):
            assert "EXEC CICS" not in code, f"{path.name}: a CICS program CALLs DL/I"
            batch.add(path.name.upper())
    assert {"PAUDBLOD.CBL", "DBUNLDGS.CBL", "PAUDBUNL.CBL"} <= batch  # the batch / BMP users, not CICS
    for prog in ("COPAUA0C", "COPAUS0C", "COPAUS1C"):
        code = _code(read_source(AUTH / f"{prog}.cbl").text)
        assert "EXEC CICS" in code and "EXEC DLI" in code and "CBLTDLI" not in code, prog
