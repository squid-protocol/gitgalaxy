"""#4270: two gaps that kept programs from translating WHOLE.

1. A CICS program nothing in the estate starts or LINKs to (CBSA's ACCTCTRL, LINKed from outside the estate;
   cics-java-recgen's EDUPGM, LINKed from Java) got a plain service, so every EXEC CICS in it was a hole and EIBCALEN
   was `no such item`. `is_cics_program` now also takes a LINKAGE DFHCOMMAREA (the COMMAREA name the CICS translator
   uses) or an EXEC CICS handler / ABEND the engine extracted as CICS evidence.
2. `SET pointer TO NULL` (CBSA CREACC) was refused with every other use of NULL. A data pointer set to NULL holds
   binary zeros (oracle_assumptions.md C9), as INITIALIZE already leaves one; any other use of NULL stays refused.
   A POINTER now has a Field over its bytes, so `SET p TO q` (CBSA DELCUS) -- translated before, as a byte move,
   onto Fields that were never declared -- compiles.
"""

from __future__ import annotations

import os
import shutil

import pytest
from test_det_programs import PKG, _cobol, _java, _java_run, program

E2E = pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker") or _java() is None,
                         reason="needs Docker and a JDK 17 (JAVA_HOME / JDK_17)")  # fmt: skip


# ---- 1. a CICS program with no transaction and no caller in the estate ----------------------------------------
def _skeleton(records=(), uow=(), **sections) -> dict:
    s = {k: {"facts": v} for k, v in sections.items()}
    s["records"] = {"facts": list(records)}
    s["uow_handlers"] = {"facts": list(uow)}
    return {"program": {"file": "src/P.cbl", "language": "cobol", "program_ids": ["P"]}, "sections": s}


def _rec(name: str, section: str, level: int = 1) -> dict:
    return {"level": level, "name": name, "section": section}


@pytest.mark.parametrize(
    "skeleton, cics",
    [
        (_skeleton(), False),  # a batch program
        (_skeleton([_rec("WS-A", "WORKING-STORAGE"), _rec("LS-PARM", "LINKAGE")]), False),
        (_skeleton([_rec("DFHCOMMAREA", "LINKAGE")]), True),  # ACCTCTRL
        (_skeleton([_rec("dfhcommarea", "LINKAGE")]), True),
        (_skeleton([_rec("DFHCOMMAREA", "WORKING-STORAGE")]), False),  # not the COMMAREA the translator passes
        (_skeleton([_rec("DFHCOMMAREA", "LINKAGE", level=5)]), False),
        (_skeleton(uow=[{"kind": "ABEND", "source": "CICS", "verb": "ABEND"}]), True),  # EDUPGM
        (_skeleton(uow=[{"kind": "COMMIT", "source": "SQL", "verb": "COMMIT"}]), False),
        (_skeleton(entry_transactions=[{"transid": "T1"}]), True),  # the evidence it already took
    ],
)
def test_is_cics_program_takes_a_linkage_dfhcommarea_or_an_exec_cics_handler(skeleton, cics):
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import is_cics_program

    assert is_cics_program(skeleton) is cics


# ---- 2. SET pointer TO NULL -------------------------------------------------------------------------------------
NULLP = program(
    "NULLP",
    ["01 REC.", "   05 R-HEAD PIC X(4).", "   05 R-PTR POINTER.", "   05 R-TAIL PIC X(4).",
     "01 TEXT-R REDEFINES REC PIC X(16).",
     "01 PTRS.", "   05 P-TAB POINTER OCCURS 2.", "01 TEXT-REC REDEFINES PTRS PIC X(16).", "01 P2 POINTER.", "01 P2-X REDEFINES P2 PIC X(8)."],
    ["MOVE ALL 'Z' TO TEXT-R", "DISPLAY REC", "SET R-PTR TO NULL", "DISPLAY REC",
     "MOVE ALL 'Q' TO TEXT-REC", "SET P-TAB (2) TO NULLS", "DISPLAY TEXT-REC",
     "SET P-TAB (1) P2 TO NULL", "DISPLAY TEXT-REC",
     "MOVE ALL 'K' TO P2-X", "DISPLAY P2-X", "SET P2 TO R-PTR", "DISPLAY P2-X"],
)  # fmt: skip


def test_set_pointer_to_null_translates(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "NULLP.cbl").write_text(NULLP)
    (tmp_path / "project").mkdir()
    r = P.translate(tmp_path / "NULLP.cbl", [], "public class NullpService {\n}\n", PKG, None, tmp_path / "project")
    assert not r.stats["holes"], r.stats["holes"]
    assert "Figurative.LOW_VALUES" in r.java


@pytest.mark.parametrize(
    "data, stmt, why",
    [
        (["01 X PIC X(8)."], "SET X TO NULL", "SET X TO NULL: not a pointer"),
        (["01 P POINTER.", "01 Q POINTER."], "IF P = NULL DISPLAY 'N' END-IF", "NULL: pointers are not modelled"),
    ],
)
def test_other_uses_of_null_stay_refused(tmp_path, data, stmt, why):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "NULLX.cbl").write_text(program("NULLX", data, [stmt]))
    (tmp_path / "project").mkdir()
    holes = P.translate(tmp_path / "NULLX.cbl", [], "public class NullxService {\n}\n", PKG, None,
                        tmp_path / "project").stats["holes"]  # fmt: skip
    assert holes and why in holes[0], holes


def test_a_pointer_only_set_to_an_address_and_to_null_is_still_write_only():
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import layout as L
    from gitgalaxy.tools.cobol_to_java.det import stmt as S
    from gitgalaxy.tools.cobol_to_java.det.program import write_only_pointers
    from gitgalaxy.tools.cobol_to_java.det.source import logical_lines

    src = program("WOP", ["01 A PIC X(4).", "01 P POINTER.", "01 Q POINTER."],
                  ["SET P TO ADDRESS OF A", "SET P TO NULL", "SET Q TO NULL", "DISPLAY Q"])  # fmt: skip
    lines = logical_lines(src.splitlines(), "WOP.cbl")
    assert write_only_pointers(L.parse(lines), S.parse(lines)) == {"P"}


@E2E
@pytest.mark.parametrize("mode", ["bytes", "typed", "groups"])
def test_set_pointer_to_null_equals_gnucobols(mode, tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    cob = tmp_path / "cobol"
    cob.mkdir()
    want = _cobol(NULLP, cob, raw=True)
    got = _java_run("NULLP", NULLP, tmp_path, mode != "bytes", mode == "groups", raw=True)
    assert want.count(b"\x00") == 8 + 8 + 16 + 8, want  # R-PTR, then P-TAB (2), then both, then P2 from R-PTR
    assert got == want
