"""#5106: DBB MortgageApplication epscsmrd's holes are refused by name and each maps to exactly one refusal_map entry.

The input class: LE condition handler registration (CEEHDLR / CEEHDLU, static and dynamic CALL), SET ... TO ENTRY,
ADDRESS OF a record with no storage of its own, GETMAIN without INITIMG, and the sibling-program CALL (still the generic
refusal: #4447 / #4404). A handler call is never a silent no-op: it translates to a Hole that names the service.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import support_matrix as sm  # noqa: E402

PKG = "t"


def _program(*stmts: str) -> str:
    lines = ["IDENTIFICATION DIVISION.", "PROGRAM-ID. HNDL.", "DATA DIVISION.", "WORKING-STORAGE SECTION.",
             "01 ROUTINE PROCEDURE-POINTER.", "01 TOKEN POINTER.", "01 FC PIC X(12).", "01 PGM PIC X(8) VALUE 'CEEHDLR'.",
             "PROCEDURE DIVISION.", "MAIN-PARA.", *(f"    {s}" for s in stmts), "    STOP RUN."]  # fmt: skip
    return "\n".join(" " * 7 + ln for ln in lines) + "\n"


def _holes(src: str) -> list[str]:
    pytest.importorskip("tree_sitter_language_pack")
    import test_det_programs as tdp
    from gitgalaxy.tools.cobol_to_java.det import program as P

    tmp = Path(tempfile.mkdtemp(prefix="t5106"))
    (tmp / "HNDL.cbl").write_text(src)
    project = tmp / "project"
    tdp._batch_package(project / "src/main/java")
    return P.translate(tmp / "HNDL.cbl", [], "public class HndlService {\n}\n", PKG, None, project).stats["holes"]


@pytest.mark.parametrize(
    ("stmt", "service"),
    [
        ("CALL 'CEEHDLR' USING ROUTINE TOKEN FC", "CEEHDLR"),
        ("CALL 'CEEHDLU' USING ROUTINE FC", "CEEHDLU"),
        ("CALL 'CEEHDLR' USING ROUTINE TOKEN FC RETURNING FC", "CEEHDLR"),
        ("CALL PGM USING ROUTINE TOKEN FC", "CEEHDLR"),
    ],
)
def test_a_condition_handler_call_is_refused_by_name(stmt, service):
    holes = _holes(_program(stmt))
    assert len(holes) == 1 and f"{service}:" in holes[0] and "not modelled" in holes[0], holes
    assert [e["id"] for e in sm.classify(holes[0].split(": ", 1)[1], sm.load_map())] == ["le-condition-handling"]


def test_set_to_entry_stays_a_named_hole():
    holes = _holes(_program("SET ROUTINE TO ENTRY 'EPSCSMRF'"))
    assert len(holes) == 1 and "SET TO ENTRY" in holes[0], holes


def test_the_siblings_in_the_class_stay_refused_not_translated():
    holes = _holes(_program("CALL 'EPSCSMRI' USING FC"))
    assert len(holes) == 1 and "CALL EPSCSMRI" in holes[0], holes


@pytest.mark.parametrize(
    ("text", "owner"),
    [
        ("CALL CALL CEEHDLR", "le-condition-handling"),  # the committed report's text before the named refusal
        ("CALL CEEHDLU: unregistering an LE user condition handler is not modelled (x)", "le-condition-handling"),
        ("CALL CALL EPSCSMRI", "multi-program-call"),
        ("HOLE SET TO ENTRY: procedure / function pointers are not modelled", "procedure-pointer"),
        ("SET-POINTER ADDRESS OF ERROR-RESPONSE: not a LINKAGE 01 record (not modelled)", "address-of-record"),
        ("SET-ADDRESS ADDRESS OF ZF-DATA: a subordinate item is an offset into its record, not a LINKAGE 01 record "
         "(needs a Storage window; not modelled)", "address-of-record"),
        ("EXEC EXEC CICS: GETMAIN without INITIMG: IBM gives acquired storage no default contents", "getmain-initimg"),
        ("EXEC EXEC CICS: EXEC CICS SOAPFAULT CREATE not modelled (web services (SOAP / WS-Addressing) are not "
         "modelled)", "soap"),
        ("EXEC EXEC CICS: EXEC CICS GETMAIN not modelled", "getmain-freemain"),
    ],
)  # fmt: skip
def test_each_epscsmrd_hole_text_maps_to_exactly_one_entry(text, owner):
    assert [e["id"] for e in sm.classify(text, sm.load_map())] == [owner]


def test_every_new_entry_has_an_owner():
    entries = {e["id"]: e for e in sm.load_map()["entries"]}
    for key in ("address-of-record", "getmain-initimg", "le-condition-handling"):
        assert entries[key].get("issue"), key
