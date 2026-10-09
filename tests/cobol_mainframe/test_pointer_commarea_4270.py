"""#4270 (oracle_assumptions.md C9): a COMMAREA with data after a POINTER.

A POINTER is 4 bytes in Enterprise COBOL (AMODE 31) and 8 in GnuCOBOL on x86-64 -- the oracle; cobc 3.1.2 has no
option or configuration key that lays one out in 4 (`numeric-pointer` makes it BINARY-DOUBLE, still 8; the width is
`sizeof(void *)` of the build). Every offset after one differs, so the translator refused such a COMMAREA (CBSA's
INQACCCU-COMMAREA, passed by BNK1CCA, CREACC and DELCUS).

Each side now reads the fields where its OWN program put them, and they are compared by NAME, never as raw bytes across
the two layouts:
- the det port's storage is the oracle's (8-byte POINTER); the generated DTO's offsets are IBM's (4-byte). The COMMAREA
  codec places each DTO field past the wider POINTERs before it (det.cics.Dto.at), so the data after a POINTER is the
  same field in both; a POINTER under an OCCURS (wider once per occurrence) is refused by name.
- the harness lays a record out as the oracle stores it (equivalence_common.layout_fields: POINTER 8 bytes), and
  compares a POINTER only as NULL or not -- an address is meaningless across sides and IBM gives it no stable value.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest
from test_det_programs import PKG, _cobol, _java, _java_run, program

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_cics as ec  # noqa: E402
import equivalence_common as common  # noqa: E402

E2E = pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1" or not shutil.which("docker") or _java() is None,
                         reason="needs Docker and a JDK 17 (JAVA_HOME / JDK_17)")  # fmt: skip

COPYBOOK = """\
          03 CA-HEAD                 PIC X(3).
          03 CA-PTR                  POINTER.
          03 CA-NUM                  PIC 9(4).
          03 CA-TAIL                 PIC X(5).
"""
# the generator's DTO for it: IBM's offsets (a 4-byte POINTER), as CBSA's InqacccuDfhcommarea
DTO = """\
package com.x.dto.contract;

/**
 * COBOL record DFHCOMMAREA (PTRLNK.cbl), 16 bytes, from GitGalaxy's verified skeleton.
 */
public class PtrlnkDfhcommarea {

    // CA-HEAD: PIC X(3), offset 0, 3 bytes (ptrca.cpy)
    private String caHead;

    // CA-PTR: POINTER, offset 3, 4 bytes (ptrca.cpy)
    private String caPtr;

    // CA-NUM: PIC 9(4), offset 7, 4 bytes (ptrca.cpy)
    private Integer caNum;

    // CA-TAIL: PIC X(5), offset 11, 5 bytes (ptrca.cpy)
    private String caTail;

}
"""
PTRLNK = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PTRLNK.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-CA.
          COPY PTRCA.
       LINKAGE SECTION.
       01 DFHCOMMAREA.
          COPY PTRCA.
       PROCEDURE DIVISION USING DFHCOMMAREA.
           MOVE CA-NUM OF DFHCOMMAREA TO CA-NUM OF WS-CA
           SET CA-PTR OF WS-CA TO NULL
           EXEC CICS LINK PROGRAM('PTRCB') COMMAREA(WS-CA) END-EXEC
           MOVE CA-TAIL OF WS-CA TO CA-TAIL OF DFHCOMMAREA
           EXEC CICS RETURN END-EXEC.
"""
STUB = (
    "package com.x.service;\nimport com.x.cics.CicsTask;\nimport com.x.dto.contract.PtrlnkDfhcommarea;\n"
    "public class PtrlnkService {\n"
    "    public PtrlnkDfhcommarea handleLink(PtrlnkDfhcommarea request) { return request; }\n"
    "    public PtrlnkDfhcommarea linkPtrcb(PtrlnkDfhcommarea request) { return request; }\n"
    "    public void runTask(CicsTask task) {}\n}\n"
)


def _translate(tmp_path: Path, copybook: str = COPYBOOK, dto: str = DTO):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "PTRLNK.cbl").write_text(PTRLNK, encoding="utf-8")
    (tmp_path / "ptrca.cpy").write_text(copybook, encoding="utf-8")
    contract = tmp_path / "proj/src/main/java/com/x/dto/contract"
    contract.mkdir(parents=True)
    (contract / "PtrlnkDfhcommarea.java").write_text(dto, encoding="utf-8")
    vsam = tmp_path / "proj/src/main/java/com/x/entity/vsam"
    vsam.mkdir(parents=True)
    (vsam / "CobolRecords.java").write_text("package com.x.entity.vsam; public class CobolRecords {}\n")
    return P.translate(tmp_path / "PTRLNK.cbl", [tmp_path], STUB, "com.x", {}, tmp_path / "proj")


def test_the_dto_maps_ibm_offsets_past_each_wider_pointer(tmp_path):
    from gitgalaxy.tools.cobol_to_java.det import cics as C

    contract = tmp_path / "src/main/java/com/x/dto/contract"
    contract.mkdir(parents=True)
    (contract / "PtrlnkDfhcommarea.java").write_text(DTO, encoding="utf-8")
    d = C.Generated(tmp_path, STUB).dto("PtrlnkDfhcommarea")
    assert (d.record, d.occurs, d.wider) == (16, False, 4)
    assert [d.at(x.offset) for x in d.leaves] == [0, 3, 11, 15]  # CA-NUM: IBM's offset 7, the oracle's 11
    assert d.size == 20  # the record in GnuCOBOL's storage (EIBCALEN on the oracle side)


def test_a_dto_whose_occurs_fields_appear_once_carries_its_whole_record(tmp_path):
    """CBSA's INQACCCU-COMMAREA: 20 accounts after the POINTER, listed once; the whole record (1981 bytes on z/OS,
    1985 in GnuCOBOL) travels, not the first account's 119."""
    from gitgalaxy.tools.cobol_to_java.det import cics as C

    contract = tmp_path / "src/main/java/com/x/dto/contract"
    contract.mkdir(parents=True)
    dto = DTO.replace("16 bytes, from GitGalaxy's verified skeleton.", "40 bytes, from GitGalaxy's verified skeleton.\n"
                      " * Fields inside an OCCURS group appear once; the offsets and the width count every occurrence.")  # fmt: skip
    (contract / "PtrlnkDfhcommarea.java").write_text(dto, encoding="utf-8")
    assert C.Generated(tmp_path, STUB).dto("PtrlnkDfhcommarea").size == 44


def test_a_commarea_with_data_after_a_pointer_translates_onto_the_storages_offsets(tmp_path):
    r = _translate(tmp_path)
    assert (r.stats["translated"], r.stats["holes"]) == (r.stats["statements"], [])
    codec = r.java[r.java.index("private void in_PtrlnkDfhcommarea") :]
    assert "DetCics.pointerIn(d.getCaPtr(), s, base + 3, 8);" in codec
    assert "Field.zoned(s, base + 11, 4," in codec and "Field.alphanumeric(s, base + 15, 5," in codec
    assert "calen = cx(task, 20);" in r.java
    assert "Cobol.commarea(" in r.java and ", 20);" in r.java[r.java.index("Cobol.commarea(") :].split("\n")[0]


def test_a_pointer_under_an_occurs_with_data_after_it_is_refused_by_name(tmp_path):
    copybook = COPYBOOK.replace(
        "03 CA-PTR                  POINTER.", "03 CA-PTRS OCCURS 2.\n            05 CA-PTR POINTER."
    )
    r = _translate(tmp_path, copybook)
    assert r.stats["holes"] and any("POINTER CA-PTR under an OCCURS" in h for h in r.stats["holes"]), r.stats["holes"]


def test_a_dto_pointer_that_is_not_ibms_four_bytes_is_refused_by_name(tmp_path):
    r = _translate(
        tmp_path, dto=DTO.replace("CA-PTR: POINTER, offset 3, 4 bytes", "CA-PTR: POINTER, offset 3, 8 bytes")
    )
    assert any("a 8-byte POINTER (IBM's is 4" in h for h in r.stats["holes"]), r.stats["holes"]


# ---- the harness: the oracle's layout, a POINTER compared as NULL or not --------------------------------------
@pytest.fixture
def corpus(tmp_path):
    (tmp_path / "ptrca.cpy").write_text("       01 CA-REC.\n" + COPYBOOK, encoding="utf-8")
    return tmp_path


def test_the_harness_lays_a_pointer_out_as_the_oracle_does(corpus):
    fields = common.layout_fields(corpus, "ptrca.cpy", "CA-REC")
    assert [(f["name"], f["offset"], f["bytes"], f["usage"]) for f in fields] == [
        ("CA-HEAD", 0, 3, None), ("CA-PTR", 3, 8, "POINTER"), ("CA-NUM", 11, 4, None), ("CA-TAIL", 15, 5, None)]  # fmt: skip


def test_a_pointer_is_given_and_compared_only_as_null(corpus):
    fields = common.layout_fields(corpus, "ptrca.cpy", "CA-REC")
    rec = ec.encode_record(fields, {"CA-HEAD": "ABC", "CA-NUM": "42", "CA-PTR": "NULL"}, b"init", "latin-1")
    assert rec == b"ABC" + bytes(8) + b"0042" + b" " * 5
    assert ec.encode_record(fields, {"CA-HEAD": "ABC"}, b"init", "latin-1")[3:11] == bytes(8)  # INITIALIZE: NULL
    back = ec.decode_record(rec, fields, "latin-1", exact=True)
    assert back == {"CA-HEAD": "ABC", "CA-PTR": None, "CA-NUM": "42", "CA-TAIL": ""}
    assert ec._same_commarea(back["CA-PTR"], None)  # the det DTO's NULL (DetCics.pointerOut)
    set_ = rec[:3] + b"\x10\x20\x30\x40\x00\x00\x00\x00" + rec[11:]
    assert ec.decode_record(set_, fields, "latin-1")["CA-PTR"] == common.POINTER_SET
    assert not ec._same_commarea(common.POINTER_SET, None)
    with pytest.raises(ValueError, match="a POINTER can only be given as 'NULL'"):
        ec.encode_record(fields, {"CA-PTR": "0x7fff0000"}, b"init", "latin-1")


# ---- end to end: the oracle's bytes, the harness's layout and the det port's storage agree -----------------------
REC = program(
    "PTRREC",
    ["01 CA-REC.", "   03 CA-HEAD PIC X(3).", "   03 CA-PTR POINTER.", "   03 CA-NUM PIC 9(4).", "   03 CA-TAIL PIC X(5).",
     "01 CA-COPY.", "   03 CC-HEAD PIC X(3).", "   03 CC-PTR POINTER.", "   03 CC-NUM PIC 9(4).", "   03 CC-TAIL PIC X(5)."],
    ["INITIALIZE CA-REC", "MOVE 'ABC' TO CA-HEAD", "MOVE 42 TO CA-NUM", "MOVE 'TAILS' TO CA-TAIL", "DISPLAY CA-REC",
     "MOVE CA-REC TO CA-COPY", "SET CC-PTR TO NULL", "ADD 1 TO CC-NUM", "DISPLAY CA-COPY", "DISPLAY CC-NUM CC-TAIL"],
)  # fmt: skip


@E2E
@pytest.mark.parametrize("mode", ["bytes", "typed", "groups"])
def test_data_after_a_pointer_is_where_gnucobol_puts_it(mode, tmp_path, corpus):
    pytest.importorskip("tree_sitter_language_pack")
    cob = tmp_path / "cobol"
    cob.mkdir()
    want = _cobol(REC, cob, raw=True)
    got = _java_run("PTRREC", REC, tmp_path, mode != "bytes", mode == "groups", raw=True)
    assert got == want
    first, second = want.split(b"\n")[:2]
    fields = common.layout_fields(corpus, "ptrca.cpy", "CA-REC")
    # the harness's layout is the oracle's: the record it encodes is the bytes the program holds, field for field
    assert first == ec.encode_record(fields, {"CA-HEAD": "ABC", "CA-NUM": "42", "CA-TAIL": "TAILS"}, b"init", "latin-1")
    assert ec.decode_record(second, fields, "latin-1") == {"CA-HEAD": "ABC", "CA-PTR": None, "CA-NUM": "43",
                                                            "CA-TAIL": "TAILS"}  # fmt: skip
