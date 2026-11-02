"""#5119 (register X56): a CICS command's SET(BLL cell) names the record the cell addresses.

OS/VS COBOL's BLL cell list is the LINKAGE 01 of fullwords (a FILLER first) after DFHCOMMAREA; each following 01 has one
cell per 4096 bytes (CICS/MVS 2.1.2 APR, SC33-0512-1, pp. 21-23). The scanner's `cics_resources` row reports that
record, and the cell as `record_cell`, instead of the cell as the record.
"""

import pytest

from gitgalaxy.core.cics_resources import bll_cell_records
from gitgalaxy.core.mainframe_boundary import extract_boundary


def _src(records: str, command: str, commarea: str = "", cells: str = "FRPTR FRPTR1 TSPTR") -> str:
    cell_lines = "".join(f"           02  {c} PIC S9(8) COMP.\n" for c in cells.split())
    return (
        "       LINKAGE SECTION.\n"
        f"{commarea}"
        "       01  BLL-CELLS.\n"
        "           02  FILLER PIC S9(8) COMP.\n"
        f"{cell_lines}"
        f"{records}"
        "       PROCEDURE DIVISION.\n"
        f"           EXEC CICS {command} END-EXEC.\n"
    )


def _ops(source: str) -> list[dict]:
    return extract_boundary("cobol", source)["cics_resources"]


def _one(source: str) -> dict:
    ops = _ops(source)
    assert len(ops) == 1, ops
    return ops[0]


SMALL = "       01  FILE-REC PIC X(80).\n       01  TS-REC PIC X(40).\n"


@pytest.mark.parametrize(
    "command",
    [
        "READ FILE('F') RIDFLD(K) SET(FRPTR)",
        "READ FILE('F') RIDFLD(K) UPDATE SET(FRPTR)",
        "READNEXT FILE('F') RIDFLD(K) SET(FRPTR)",
        "READPREV FILE('F') RIDFLD(K) SET(FRPTR)",
    ],
)
def test_a_file_read_into_a_cell_reports_the_record_the_cell_addresses(command):
    op = _one(_src(SMALL, command))
    assert (op["record_clause"], op["record"], op["record_cell"]) == ("SET", "FILE-REC", "FRPTR")


def test_readq_ts_set_cell_reports_the_second_record():
    op = _one(_src(SMALL, "READQ TS QUEUE('Q') SET(FRPTR1) LENGTH(L)"))
    assert (op["record"], op["record_cell"]) == ("TS-REC", "FRPTR1")


def test_every_cell_of_the_list_is_read():
    ops = _ops(_src(SMALL, "READ FILE('F') RIDFLD(K) SET(FRPTR1)"))
    assert [o["record"] for o in ops] == ["TS-REC"]


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        (4095, {"FRPTR": "BIG-REC", "FRPTR1": "NEXT-REC"}),
        (4096, {"FRPTR": "BIG-REC", "FRPTR1": "NEXT-REC"}),
        (4097, {"FRPTR": "BIG-REC", "FRPTR1": "BIG-REC", "TSPTR": "NEXT-REC"}),
        (8192, {"FRPTR": "BIG-REC", "FRPTR1": "BIG-REC", "TSPTR": "NEXT-REC"}),
        (8193, {"FRPTR": "BIG-REC", "FRPTR1": "BIG-REC", "TSPTR": "BIG-REC"}),  # NEXT-REC has no cell
    ],
)
def test_a_record_takes_one_cell_per_4096_bytes(size, expected):
    records = f"       01  BIG-REC PIC X({size}).\n       01  NEXT-REC PIC X(8).\n"
    assert bll_cell_records(extract_boundary("cobol", _src(records, "RETURN"))["records"]) == expected


def test_a_secondary_cell_reports_the_long_record():
    records = "       01  BIG-REC PIC X(5400).\n       01  NEXT-REC PIC X(8).\n"
    base = _one(_src(records, "READ FILE('F') RIDFLD(K) SET(FRPTR)"))
    second = _one(_src(records, "READ FILE('F') RIDFLD(K) SET(FRPTR1)"))
    after = _one(_src(records, "READ FILE('F') RIDFLD(K) SET(TSPTR)"))
    assert (base["record"], second["record"], after["record"]) == ("BIG-REC", "BIG-REC", "NEXT-REC")
    assert second["record_cell"] == "FRPTR1"


def test_a_group_with_occurs_and_packed_and_binary_items_is_sized_by_its_storage():
    records = (
        "       01  TBL-REC.\n"
        "           05  ROW OCCURS 100.\n"
        "               10  A PIC X(30).\n"
        "               10  P PIC S9(7) COMP-3.\n"
        "               10  B PIC S9(9) COMP.\n"
        "       01  NEXT-REC PIC X(8).\n"
    )  # 100 * (30 + 4 + 4) = 3800 bytes: one cell
    assert bll_cell_records(extract_boundary("cobol", _src(records, "RETURN"))["records"])["FRPTR1"] == "NEXT-REC"
    wider = records.replace("OCCURS 100", "OCCURS 110")  # 4180 bytes: two cells
    assert bll_cell_records(extract_boundary("cobol", _src(wider, "RETURN"))["records"])["FRPTR1"] == "TBL-REC"


def test_the_list_after_dfhcommarea_is_found():
    commarea = "       01  DFHCOMMAREA PIC X(10).\n"
    op = _one(_src(SMALL, "READ FILE('F') RIDFLD(K) SET(FRPTR)", commarea=commarea))
    assert op["record"] == "FILE-REC"


def test_a_set_that_names_no_cell_is_unchanged():
    for command, record in (
        ("READ FILE('F') RIDFLD(K) SET(ADDRESS OF FILE-REC)", "ADDRESS OF FILE-REC"),
        ("READ FILE('F') RIDFLD(K) SET(OTHER-PTR)", "OTHER-PTR"),
        ("READ FILE('F') RIDFLD(K) INTO(FILE-REC)", "FILE-REC"),
    ):
        op = _one(_src(SMALL, command))
        assert op["record"] == record
        assert "record_cell" not in op


def test_a_linkage_group_that_is_no_cell_list_maps_nothing():
    for linkage in (
        "       01  PARMS.\n           02  P1 PIC S9(8) COMP.\n           02  P2 PIC S9(8) COMP.\n",  # no FILLER first
        "       01  PARMS.\n           02  FILLER PIC X(4).\n           02  P2 PIC S9(8) COMP.\n",  # not fullwords
        "       01  PARMS.\n           02  FILLER PIC S9(8) COMP.\n           02  P2 PIC S9(4) COMP.\n",  # a halfword
    ):
        src = "       LINKAGE SECTION.\n" + linkage + "       01  REC PIC X(8).\n"
        assert bll_cell_records(extract_boundary("cobol", src)["records"]) == {}


def test_a_record_of_unreadable_size_ends_the_mapping_and_keeps_the_cell():
    records = (
        "       01  FILE-REC PIC X(8).\n       01  ODD-REC USAGE OBJECT REFERENCE.\n       01  NEXT-REC PIC X(8).\n"
    )
    assert bll_cell_records(extract_boundary("cobol", _src(records, "RETURN"))["records"]) == {"FRPTR": "FILE-REC"}
    op = _one(_src(records, "READ FILE('F') RIDFLD(K) SET(TSPTR)"))
    assert op["record"] == "TSPTR"
    assert "record_cell" not in op


def test_a_huge_pic_count_is_bounded():
    records = "       01  FILE-REC PIC X(99999999999).\n"
    assert bll_cell_records(extract_boundary("cobol", _src(records, "RETURN"))["records"]) == {
        "FRPTR": "FILE-REC",
        "FRPTR1": "FILE-REC",
        "TSPTR": "FILE-REC",
    }
