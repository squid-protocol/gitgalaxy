"""#4765: a record's OCCURS table is compared whole -- every occurrence, by name and subscript.

The harness's layout (equivalence_common.layout_fields) listed an OCCURS group's fields once, at the first occurrence,
as the generated DTO does ("Fields inside an OCCURS group appear once"). So a COMMAREA's table was compared at its
first occurrence only: CBSA's INQACCCU FETCHes up to 20 accounts into ACCOUNT-DETAILS OCCURS 1 TO 20 DEPENDING ON
NUMBER-OF-ACCOUNTS, and accounts 2..N were never compared on either side -- a port that never wrote account 3 was
proven. And the det LINK / XCTL / RETURN of such a DTO passed the first occurrence's bytes, not the record's.

Now:
- layout_fields(..., occurrences=True) lists every occurrence (`COMM-ACC-TYPE(3)`, `CELL(2,4)` nested), and a COMMAREA
  is read by it, each side by its own OCCURS DEPENDING ON count (active_fields): a count that differs is a difference,
  and so is every occurrence one side has and the other does not;
- a scenario's COMMAREA is the whole record (commarea_record), every occurrence INITIALIZEd, as EIBCALEN says;
- a LINKed task gets its COMMAREA's bytes as well (CicsTask.withLinkArea); a det port takes them (task.linkArea()) and
  its result is read from them, every occurrence -- a DTO's values map to the first occurrence (first_occurrences);
- a det DTO whose OCCURS fields appear once spans its declared record (Dto.size), and a RETURN / XCTL of it passes
  the record's bytes (DetCics.commareaOut).
- a batch file's record names each occurrence (they were compared before only as "bytes outside the layout").
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_cics as ec  # noqa: E402
import equivalence_common as common  # noqa: E402

TABLE = """\
       01 CA-REC.
          03 CA-HEAD                 PIC X(3).
          03 CA-N                    PIC 9(2).
          03 CA-ROW OCCURS 1 TO 3 DEPENDING ON CA-N.
             05 CA-KEY               PIC X(2).
             05 CA-AMT               PIC S9(3) COMP-3.
"""
NESTED = """\
       01 GRID-REC.
          03 GRID-ROW OCCURS 2.
             05 GRID-CELL OCCURS 3    PIC 9.
             05 GRID-TAG              PIC X.
"""
ELEMENTARY = """\
       01 ARR-REC.
          03 ARR-ID                  PIC X(2).
          03 ARR-VAL OCCURS 3        PIC 9(2).
"""


@pytest.fixture
def corpus(tmp_path):
    (tmp_path / "table.cpy").write_text(TABLE, encoding="utf-8")
    (tmp_path / "nested.cpy").write_text(NESTED, encoding="utf-8")
    (tmp_path / "arr.cpy").write_text(ELEMENTARY, encoding="utf-8")
    return tmp_path


def _shape(fields):
    return [(f["name"], f["offset"], f["bytes"]) for f in fields]


# ---- the layout ------------------------------------------------------------------------------------------------
def test_without_occurrences_the_layout_is_unchanged(corpus):
    """What a record is BUILT from (a scenario's COMMAREA as the DTO names it, generated inputs) stays as it was."""
    assert _shape(common.layout_fields(corpus, "table.cpy", "CA-REC")) == [
        ("CA-HEAD", 0, 3), ("CA-N", 3, 2), ("CA-KEY", 5, 2), ("CA-AMT", 7, 2)]  # fmt: skip
    assert _shape(common.layout_fields(corpus, "arr.cpy", "ARR-REC")) == [("ARR-ID", 0, 2), ("ARR-VAL", 2, 6)]


def test_every_occurrence_of_a_group_is_a_field_by_name_and_subscript(corpus):
    fields = common.layout_fields(corpus, "table.cpy", "CA-REC", occurrences=True)
    assert _shape(fields) == [("CA-HEAD", 0, 3), ("CA-N", 3, 2),
                              ("CA-KEY(1)", 5, 2), ("CA-AMT(1)", 7, 2),
                              ("CA-KEY(2)", 9, 2), ("CA-AMT(2)", 11, 2),
                              ("CA-KEY(3)", 13, 2), ("CA-AMT(3)", 15, 2)]  # fmt: skip
    third = fields[-1]
    assert (third["base"], third["subscripts"], third["odo"], third["usage"]) == (
        "CA-AMT",
        [3],
        [["CA-N", 3]],
        "COMP-3",
    )
    assert "odo" not in fields[0] and "subscripts" not in fields[0]  # a field outside a table keeps its own shape


def test_nested_and_elementary_occurs(corpus):
    grid = common.layout_fields(corpus, "nested.cpy", "GRID-REC", occurrences=True)
    assert _shape(grid) == [("GRID-CELL(1,1)", 0, 1), ("GRID-CELL(1,2)", 1, 1), ("GRID-CELL(1,3)", 2, 1),
                            ("GRID-TAG(1)", 3, 1),
                            ("GRID-CELL(2,1)", 4, 1), ("GRID-CELL(2,2)", 5, 1), ("GRID-CELL(2,3)", 6, 1),
                            ("GRID-TAG(2)", 7, 1)]  # fmt: skip
    assert all("odo" not in f for f in grid)  # fixed tables: every occurrence always
    arr = common.layout_fields(corpus, "arr.cpy", "ARR-REC", occurrences=True)
    assert _shape(arr) == [("ARR-ID", 0, 2), ("ARR-VAL(1)", 2, 2), ("ARR-VAL(2)", 4, 2), ("ARR-VAL(3)", 6, 2)]


# ---- OCCURS DEPENDING ON: each side by its own count -----------------------------------------------------------
def _rec(corpus, values):
    fields = common.layout_fields(corpus, "table.cpy", "CA-REC", occurrences=True)
    return fields, ec.commarea_record(fields, values, "latin-1")


def test_only_the_active_occurrences_are_read(corpus):
    fields, rec = _rec(corpus, {"CA-N": "2", "CA-KEY(1)": "AA", "CA-KEY(2)": "BB", "CA-KEY(3)": "ZZ"})
    got = ec.decode_record(rec, fields, "latin-1", exact=True)
    assert set(got) == {"CA-HEAD", "CA-N", "CA-KEY(1)", "CA-AMT(1)", "CA-KEY(2)", "CA-AMT(2)"}
    assert (got["CA-KEY(2)"], got["CA-AMT(2)"]) == ("BB", "0")  # INITIALIZEd: COMP-3 zero, not LOW-VALUES


def test_a_count_that_is_not_a_number_keeps_every_occurrence(corpus):
    fields, rec = _rec(corpus, {"CA-N": "2"})
    garbage = rec[:3] + b"??" + rec[5:]
    assert len(common.active_fields(garbage, fields, "latin-1")) == len(fields)  # never fewer on a guess


def test_a_count_past_the_maximum_keeps_the_maximum(corpus):
    fields, rec = _rec(corpus, {"CA-N": "99"})
    assert len(common.active_fields(rec, fields, "latin-1")) == len(fields)


# ---- the compare: occurrence 3 differs, and it is caught ---------------------------------------------------------
def _events(corpus, values):
    fields, rec = _rec(corpus, values)
    return [{"event": "COMMAREA", "commarea": ec.decode_record(rec, fields, "latin-1", exact=True)}]


def test_a_difference_in_the_third_occurrence_is_a_difference(corpus):
    same = {"CA-N": "3", "CA-KEY(1)": "AA", "CA-KEY(2)": "BB", "CA-KEY(3)": "CC", "CA-AMT(3)": "-7"}
    assert ec.compare_events(_events(corpus, same), _events(corpus, same))["diffs"] == []
    other = dict(same, **{"CA-AMT(3)": "7"})
    d = ec.compare_events(_events(corpus, same), _events(corpus, other))["diffs"]
    assert [f for x in d for f in x["fields"]] == [{"field": "commarea.CA-AMT(3)", "cobol": "-7", "java": "7"}]


def test_counts_that_differ_are_a_difference(corpus):
    three = {"CA-N": "3", "CA-KEY(1)": "AA", "CA-KEY(2)": "BB", "CA-KEY(3)": "CC"}
    two = dict(three, **{"CA-N": "2"})
    d = ec.compare_events(_events(corpus, three), _events(corpus, two))["diffs"]
    fields = [f["field"] for x in d for f in x["fields"]]
    assert "commarea.CA-N" in fields and "commarea.CA-KEY(3)" in fields  # occurrence 3: COBOL has it, Java not


def test_a_dto_value_is_the_first_occurrence_and_the_others_are_absent(corpus):
    """A model port's DTO lists the table's fields once: they are occurrence 1; occurrences 2.. are absent on its side
    -- a difference wherever the COBOL side has one active, never assumed equal."""
    fields = common.layout_fields(corpus, "table.cpy", "CA-REC", occurrences=True)
    shape = {"caHead": "CA-HEAD", "caN": "CA-N", "caKey": "CA-KEY", "caAmt": "CA-AMT"}
    java = ec.java_commarea({"caHead": "H", "caN": 2, "caKey": "AA", "caAmt": 0}, shape, fields, "latin-1")
    assert java == {"CA-HEAD": "H", "CA-N": 2, "CA-KEY(1)": "AA", "CA-AMT(1)": 0}
    cobol = _events(corpus, {"CA-HEAD": "H", "CA-N": "2", "CA-KEY(1)": "AA", "CA-KEY(2)": "BB"})
    d = ec.compare_events(cobol, [{"event": "COMMAREA", "commarea": java}])["diffs"]
    assert [f["field"] for x in d for f in x["fields"]] == ["commarea.CA-KEY(2)", "commarea.CA-AMT(2)"]


def test_a_scenario_names_the_first_occurrence_as_the_dto_does(corpus):
    fields = common.layout_fields(corpus, "table.cpy", "CA-REC", occurrences=True)
    rec = ec.commarea_record(fields, {"CA-N": "1", "CA-KEY": "AA", "CA-KEY(2)": "BB"}, "latin-1")
    assert len(rec) == 17  # the whole record, as EIBCALEN says -- not the first occurrence's 9 bytes
    assert rec[5:7] == b"AA" and rec[9:11] == b"BB"


# ---- end to end through the harness: the COBOL side's commarea.out, the det port's bytes -------------------------
def test_end_to_end_the_third_occurrence_is_compared(corpus, tmp_path):
    """A LINKed task's result: the stub's commarea.out (outputs) against the bytes a det port left (_java_events, an
    `area` on the COMMAREA event), both read by the case's COMMAREA layout. Account 3 differs: caught."""
    case = {"name": "occ", "commarea": {"segments": [{"copybook": "table.cpy", "record": "CA-REC"}]}}
    read = ec.commarea_fields(corpus, case, occurrences=True)
    values = {"CA-HEAD": "HDR", "CA-N": "3", "CA-KEY(1)": "AA", "CA-KEY(2)": "BB", "CA-KEY(3)": "CC", "CA-AMT(3)": "5"}
    out = tmp_path / "cobol" / "out"
    out.mkdir(parents=True)
    (out / "commarea.out").write_bytes(ec.commarea_record(read, values, "latin-1"))
    cobol = ec.cobol_events(ec.outputs(out, case, corpus, read))
    java_out = tmp_path / "java"
    java_out.mkdir()
    wrong = ec.commarea_record(read, dict(values, **{"CA-AMT(3)": "6"}), "latin-1")
    dto = {"caHead": "HDR", "caN": 3, "caKey": "AA", "caAmt": 0}  # the DTO: occurrence 1, which agrees
    (java_out / "s.json").write_text(json.dumps([{"event": "COMMAREA", "commarea": dto,
                                                  "area": base64.b64encode(wrong).decode("ascii")}]))  # fmt: skip
    shape = {"caHead": "CA-HEAD", "caN": "CA-N", "caKey": "CA-KEY", "caAmt": "CA-AMT"}
    java = ec._java_events({"scenarios": [{"name": "s"}]}, java_out, shape, read)["s"]
    linked = {"linked": True}
    d = ec.compare_events(ec.linked_result(linked, cobol), ec.linked_result(linked, java))["diffs"]
    assert [f["field"] for x in d for f in x["fields"]] == ["commarea.CA-AMT(3)"]
    (java_out / "s.json").write_text(json.dumps([{"event": "COMMAREA", "commarea": dto, "area": base64.b64encode(
        ec.commarea_record(read, values, "latin-1")).decode("ascii")}]))  # fmt: skip
    java = ec._java_events({"scenarios": [{"name": "s"}]}, java_out, shape, read)["s"]
    assert ec.compare_events(ec.linked_result(linked, cobol), ec.linked_result(linked, java))["diffs"] == []


# ---- batch: a file's record names each occurrence -----------------------------------------------------------------
def test_a_file_record_names_the_occurrence_that_differs(corpus):
    fields = common.layout_fields(corpus, "arr.cpy", "ARR-REC", occurrences=True)
    d = common.diff_records(b"X1010203", b"X1010299", 8, fields, "cp037", "latin-1")
    assert d["diffs"] == [{"record": 1, "fields": [{"field": "ARR-VAL(3)", "cobol": "3", "java": "99"}]}]


def test_a_file_record_compares_every_occurrence_whatever_its_count(corpus):
    """A file's bytes are the file's: an occurrence past the OCCURS DEPENDING ON count is still compared there."""
    fields = common.layout_fields(corpus, "table.cpy", "CA-REC", occurrences=True)
    a = ec.commarea_record(fields, {"CA-N": "1", "CA-KEY(3)": "CC"}, "latin-1")
    b = ec.commarea_record(fields, {"CA-N": "1", "CA-KEY(3)": "DD"}, "latin-1")
    d = common.diff_records(a, b, 17, fields, "cp037", "latin-1")
    assert [f["field"] for x in d["diffs"] for f in x["fields"]] == ["CA-KEY(3)"]


# ---- the det translator: an OCCURS DTO travels whole ----------------------------------------------------------------
OCC_DTO = """\
package com.x.dto.contract;

/**
 * COBOL record DFHCOMMAREA (OCCLNK.cbl), 17 bytes, from GitGalaxy's verified skeleton.
 * Fields inside an OCCURS group appear once; the offsets and the width count every occurrence.
 */
public class OcclnkDfhcommarea {

    // CA-HEAD: PIC X(3), offset 0, 3 bytes (occca.cpy)
    private String caHead;

    // CA-N: PIC 9(2), offset 3, 2 bytes (occca.cpy)
    private Integer caN;

    // CA-KEY: PIC X(2), offset 5, 2 bytes (occca.cpy)
    private String caKey;

    // CA-AMT: PIC S9(3) COMP-3, offset 7, 2 bytes (occca.cpy)
    private java.math.BigDecimal caAmt;
}
"""
OCCLNK = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. OCCLNK.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-CA.
          COPY OCCCA.
       LINKAGE SECTION.
       01 DFHCOMMAREA.
          COPY OCCCA.
       PROCEDURE DIVISION USING DFHCOMMAREA.
           MOVE CA-N OF DFHCOMMAREA TO CA-N OF WS-CA
           EXEC CICS LINK PROGRAM('OCCB') COMMAREA(WS-CA) END-EXEC
           EXEC CICS XCTL PROGRAM('OCCX') COMMAREA(WS-CA) END-EXEC
           EXEC CICS RETURN END-EXEC.
"""
OCC_STUB = (
    "package com.x.service;\nimport com.x.cics.CicsTask;\nimport com.x.dto.contract.OcclnkDfhcommarea;\n"
    "public class OcclnkService {\n"
    "    public OcclnkDfhcommarea handleLink(OcclnkDfhcommarea request) { return request; }\n"
    "    public OcclnkDfhcommarea linkOccb(OcclnkDfhcommarea request) { return request; }\n"
    "    public OcclnkDfhcommarea xctlOccx(OcclnkDfhcommarea request) { return request; }\n"
    "    public void runTask(CicsTask task) {}\n}\n"
)


def test_a_det_occurs_dto_without_a_pointer_spans_its_record(tmp_path):
    from gitgalaxy.tools.cobol_to_java.det import cics as C

    contract = tmp_path / "src/main/java/com/x/dto/contract"
    contract.mkdir(parents=True)
    (contract / "OcclnkDfhcommarea.java").write_text(OCC_DTO, encoding="utf-8")
    d = C.Generated(tmp_path, OCC_STUB).dto("OcclnkDfhcommarea")
    assert (d.record, d.occurs, d.wider, d.extent, d.size) == (17, True, 0, 9, 17)


def test_a_det_link_and_xctl_of_an_occurs_dto_pass_the_whole_table(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    (tmp_path / "OCCLNK.cbl").write_text(OCCLNK, encoding="utf-8")
    (tmp_path / "occca.cpy").write_text("\n".join(TABLE.splitlines()[1:]) + "\n", encoding="utf-8")
    contract = tmp_path / "proj/src/main/java/com/x/dto/contract"
    contract.mkdir(parents=True)
    (contract / "OcclnkDfhcommarea.java").write_text(OCC_DTO, encoding="utf-8")
    vsam = tmp_path / "proj/src/main/java/com/x/entity/vsam"
    vsam.mkdir(parents=True)
    (vsam / "CobolRecords.java").write_text("package com.x.entity.vsam; public class CobolRecords {}\n")
    r = P.translate(tmp_path / "OCCLNK.cbl", [tmp_path], OCC_STUB, "com.x", {}, tmp_path / "proj")
    assert (r.stats["translated"], r.stats["holes"]) == (r.stats["statements"], [])
    link = next(ln for ln in r.java.splitlines() if "Cobol.commarea(" in ln)
    assert link.rstrip().endswith(", 17);"), link  # the LINK's span: the record, every occurrence (not 9 bytes)
    xctl = next(ln for ln in r.java.splitlines() if "task.xctl(" in ln)
    assert "DetCics.commareaOut(out_OcclnkDfhcommarea(" in xctl and ", 17, 9, CS)" in xctl, xctl
    assert "calen = cx(task, 17);" in r.java  # EIBCALEN: the record's length
