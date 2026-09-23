"""
#3355: the COMMAREA contract operands on CICS call sites, and the COPY placement
on record entries that lets a reader expand the passed record and the callee's
DFHCOMMAREA.

The call graph (#3200) says THAT a program LINKs another. These pin WHICH record
it passes (`COMMAREA(x)`) and how long it says that record is (`LENGTH(...)`,
`DATALENGTH(...)`), as written. Every fixture is the shape of real source in the
pinned corpora: CBSA's `LINK PROGRAM(...)` + `COMMAREA(...)` on the next line,
carddemo's `RETURN TRANSID (WS-TRANID) COMMAREA (CARDDEMO-COMMAREA) LENGTH(LENGTH
OF CARDDEMO-COMMAREA)` with a space before each paren, and CBSA's
`01 DFHCOMMAREA.` + `COPY INQCUST.` / section-level `COPY INQACC REPLACING ...`.
"""

import time

import pytest

from gitgalaxy.core.mainframe_boundary import extract_boundary

CBSA_LINKS = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. INQACCCU.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-ABEND-PGM                 PIC X(8) VALUE 'ABNDPROC'.
       01 INQCUST-COMMAREA.
          COPY INQCUST.
       01 ABNDINFO-REC.
           COPY ABNDINFO.
       LINKAGE SECTION.
       01 DFHCOMMAREA.
          COPY INQACCCU.
       PROCEDURE DIVISION USING DFHCOMMAREA.
       A010.
           EXEC CICS LINK PROGRAM('INQCUST ')
              COMMAREA(INQCUST-COMMAREA)
           END-EXEC.
           EXEC CICS LINK PROGRAM(WS-ABEND-PGM)
                     COMMAREA(ABNDINFO-REC)
           END-EXEC.
           EXEC CICS LINK PROGRAM('CRDTAGY1')
                COMMAREA(WS-CONT-IN)
                LENGTH(WS-CONT-LEN)
                DATALENGTH(LENGTH OF WS-CONT-IN)
                SYNCONRETURN
           END-EXEC.
           EXEC CICS LINK PROGRAM('NOAREA') END-EXEC.
           GOBACK.
"""

CARDDEMO_RETURN = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. COSGN00C.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-TRANID                PIC X(04) VALUE 'CC00'.
       COPY COCOM01Y.
       PROCEDURE DIVISION.
       MAIN-PARA.
           EXEC CICS RETURN
                     TRANSID (WS-TRANID)
                     COMMAREA (CARDDEMO-COMMAREA)
                     LENGTH(LENGTH OF CARDDEMO-COMMAREA)
           END-EXEC.
           EXEC CICS
               XCTL PROGRAM(CDEMO-TO-PROGRAM)
               COMMAREA(CARDDEMO-COMMAREA)
           END-EXEC.
           EXEC CICS RETURN END-EXEC.
"""


def _calls(code: str) -> list:
    return extract_boundary("cobol", code)["calls"]


def _records(code: str) -> list:
    return extract_boundary("cobol", code)["records"]


def test_a_link_carries_the_record_it_passes():
    by_target = {c["target"]: c for c in _calls(CBSA_LINKS)}
    assert by_target["INQCUST"]["commarea"] == "INQCUST-COMMAREA"
    assert by_target["ABNDPROC"]["commarea"] == "ABNDINFO-REC"


def test_length_and_datalength_are_kept_as_written():
    crdt = next(c for c in _calls(CBSA_LINKS) if c["target"] == "CRDTAGY1")
    assert (crdt["commarea"], crdt["commarea_length"], crdt["commarea_datalength"]) == (
        "WS-CONT-IN",
        "WS-CONT-LEN",
        "LENGTH OF WS-CONT-IN",
    )


def test_a_site_without_a_commarea_keeps_its_pre_3355_shape():
    """No key at all -- so the call graph payload, the audit block and the golden
    master are byte-identical for every site that passes nothing."""
    bare = next(c for c in _calls(CBSA_LINKS) if c["target"] == "NOAREA")
    assert set(bare) == {"verb", "form", "operand", "target", "line"}


def test_carddemo_return_and_xctl_shapes():
    calls = _calls(CARDDEMO_RETURN)
    ret = next(c for c in calls if c["verb"] == "RETURN TRANSID")
    assert (ret["target"], ret["commarea"], ret["commarea_length"]) == (
        "CC00",
        "CARDDEMO-COMMAREA",
        "LENGTH OF CARDDEMO-COMMAREA",
    )
    xctl = next(c for c in calls if c["verb"] == "XCTL")
    assert (xctl["operand"], xctl["target"], xctl["commarea"]) == ("CDEMO-TO-PROGRAM", None, "CARDDEMO-COMMAREA")
    # A plain RETURN (no TRANSID) still draws no row: #3355 adds no call sites.
    assert [c["verb"] for c in calls] == ["RETURN TRANSID", "XCTL"]


@pytest.mark.parametrize(
    ("block", "expected"),
    [
        # DFHCOMMAREA( is a subscripted data-name, not the COMMAREA operand.
        ("EXEC CICS LINK PROGRAM('P') COMMAREA(DFHCOMMAREA(1:EIBCALEN)) END-EXEC.", "DFHCOMMAREA(1:EIBCALEN)"),
        ("EXEC CICS LINK PROGRAM('P') COMMAREA(WS-AREA OF WS-GROUP) END-EXEC.", "WS-AREA OF WS-GROUP"),
        ("EXEC CICS LINK PROGRAM('P') INPUTMSG(WS-M) INPUTMSGLEN(10) END-EXEC.", None),
    ],
)
def test_operand_boundaries(block, expected):
    (call,) = _calls(f"       PROCEDURE DIVISION.\n           {block}\n")
    assert call.get("commarea") == expected
    assert "commarea_length" not in call  # INPUTMSGLEN( / DATALENGTH( are not LENGTH(


def test_a_link_inside_a_literal_draws_nothing():
    """A DISPLAY literal naming the verb is shielded (comments never reach the
    extractor: it reads the PRISM code stream)."""
    code = "       PROCEDURE DIVISION.\n           DISPLAY 'EXEC CICS LINK PROGRAM(X) COMMAREA(Y)'.\n"
    assert _calls(code) == []


def test_an_unbalanced_operand_is_dropped_not_run_away():
    code = "       PROCEDURE DIVISION.\n           EXEC CICS LINK PROGRAM('P') COMMAREA(WS-X(1 END-EXEC.\n"
    (call,) = _calls(code)
    assert "commarea" not in call


def test_copy_members_ride_on_the_entry_they_follow():
    recs = {r["name"]: r for r in _records(CBSA_LINKS)}
    assert recs["INQCUST-COMMAREA"]["copy_members"] == "INQCUST"
    assert recs["ABNDINFO-REC"]["copy_members"] == "ABNDINFO"
    assert recs["DFHCOMMAREA"]["copy_members"] == "INQACCCU"
    # An entry with no COPY after it has no key (pre-#3355 shape).
    assert "copy_members" not in recs["WS-ABEND-PGM"]


def test_a_section_level_copy_belongs_to_no_entry():
    """CBSA INQACC: `LINKAGE SECTION.` + `COPY INQACC REPLACING ...` -- the COPY sits
    after the section header, so the WORKING-STORAGE record above must not own it."""
    code = """\
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 ABNDINFO-REC.
           COPY ABNDINFO.

       LINKAGE SECTION.
       COPY INQACC REPLACING INQACC-COMMAREA BY DFHCOMMAREA.
       PROCEDURE DIVISION USING DFHCOMMAREA.
           COPY PROCCPY.
"""
    (rec,) = _records(code)
    assert rec["copy_members"] == "ABNDINFO"


def test_a_procedure_division_copy_is_never_attributed():
    code = """\
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-LAST                PIC X.
       PROCEDURE DIVISION.
           COPY PROCCPY.
"""
    (rec,) = _records(code)
    assert "copy_members" not in rec


def test_several_copies_after_one_entry_keep_source_order():
    code = """\
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-AREA.
           COPY FIRSTCP.
           COPY 'SECONDCP' OF MYLIB.
"""
    (rec,) = _records(code)
    assert rec["copy_members"] == "FIRSTCP,SECONDCP"


@pytest.mark.parametrize(
    "payload",
    [
        "EXEC CICS LINK PROGRAM('P') COMMAREA(" + "(" * 5000 + " END-EXEC.",
        "EXEC CICS LINK PROGRAM('P') " + "COMMAREA " * 5000 + " END-EXEC.",
        "EXEC CICS RETURN TRANSID('T') LENGTH(" + "A" * 20000,
        "       01 X.\n" + "           COPY " * 5000,
    ],
    # Short ids: pytest puts the test id in PYTEST_CURRENT_TEST, and a 45,000-char
    # payload id overflows Windows' 32,767-char environment-variable limit.
    ids=["nested-parens", "repeated-commarea", "unterminated-length", "repeated-copy"],
)
def test_pathological_shapes_stay_linear(payload):
    start = time.perf_counter()
    extract_boundary("cobol", "       PROCEDURE DIVISION.\n           " + payload + "\n")
    extract_boundary("cobol", "       WORKING-STORAGE SECTION.\n" + payload + "\n")
    assert time.perf_counter() - start < 2.0
