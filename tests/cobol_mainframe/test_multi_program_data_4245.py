"""#4245: a source holding several programs -- a nested program and a batch-compiled sibling
(estate-crucible H-0031; IBM DBB MortgageApplication epscsmrd.cbl has 13 PROGRAM-IDs) -- has
one DATA DIVISION per program, and every one of them is read: by the engine's record_data and
by the answer key's `_data_items`. The owning program is derived in GalaxyIR (each item's
`program`), so sibling programs' same-named records stay different storage: a MOVE, a CALL
USING argument and a dynamic CALL target resolve inside their own program."""

import sys
from pathlib import Path

import pytest

from gitgalaxy.core.mainframe_boundary import extract_boundary
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import cobol_answer_key as ak  # noqa: E402

PAYMAIN = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYMAIN.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-AREA.
          05 WS-A PIC X(4).
          05 WS-N PIC 9(4).
       01 WS-IN PIC X(4).
       01 WS-PGM PIC X(8) VALUE 'PAYSUB1'.
       PROCEDURE DIVISION.
           MOVE WS-IN TO WS-A.
           CALL WS-PGM.
           CALL 'PAYCALC' USING WS-AREA.
           GOBACK.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYCALC.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-GROSS PIC 9(7)V99.
       01 WS-I PIC 9(2).
       LINKAGE SECTION.
       01 LK-AREA.
          05 LK-A PIC X(8).
       PROCEDURE DIVISION USING LK-AREA.
           MOVE 1 TO WS-I.
           GOBACK.
       END PROGRAM PAYCALC.
       END PROGRAM PAYMAIN.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. 'PAYRPT'.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-AREA.
          05 WS-N PIC 9(2).
          05 WS-A PIC X(8).
       01 WS-IN PIC X(8).
       01 WS-PGM PIC X(8) VALUE 'PAYSUB2'.
       LINKAGE SECTION.
       01 LK-RPT.
          05 LK-R PIC X(12).
       PROCEDURE DIVISION USING LK-RPT.
           MOVE WS-IN TO WS-A.
           CALL WS-PGM.
           CALL 'PAYSUB2' USING WS-AREA.
           GOBACK.
       END PROGRAM 'PAYRPT'.
"""

CALLER = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CALLER.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-PARM PIC X(12).
       PROCEDURE DIVISION.
           CALL 'PAYRPT' USING WS-PARM.
           GOBACK.
"""

ONE = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ONE.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-X PIC X(3).
       01 WS-Y PIC X(3).
       PROCEDURE DIVISION.
           MOVE WS-X TO WS-Y.
           GOBACK.
"""

NEST = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. OUTER.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 G-DATA IS GLOBAL.
          03 G-1 PIC X(2).
       PROCEDURE DIVISION.
           CALL 'INNER'.
           GOBACK.
       IDENTIFICATION DIVISION.
       PROGRAM-ID. INNER.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 W-IN PIC X(2).
       PROCEDURE DIVISION.
           MOVE 'ZZ' TO G-1.
           MOVE G-1 TO W-IN.
           GOBACK.
       END PROGRAM INNER.
       END PROGRAM OUTER.
"""

# (level, name, line) of every item, in source order: all three programs' DATA DIVISIONs.
EXPECTED = [
    (1, "WS-AREA", 5), (5, "WS-A", 6), (5, "WS-N", 7), (1, "WS-IN", 8), (1, "WS-PGM", 9),
    (1, "WS-GROSS", 19), (1, "WS-I", 20), (1, "LK-AREA", 22), (5, "LK-A", 23),
    (1, "WS-AREA", 33), (5, "WS-N", 34), (5, "WS-A", 35), (1, "WS-IN", 36), (1, "WS-PGM", 37),
    (1, "LK-RPT", 39), (5, "LK-R", 40),
]  # fmt: skip


def _tree(rows: list, parent_key: str) -> list:
    by_ordinal = {r["ordinal"]: r for r in rows}
    return [(r["name"], by_ordinal[r[parent_key]]["name"] if r[parent_key] is not None else None) for r in rows]


def test_the_engine_reads_every_programs_data_division():
    rows = extract_boundary("cobol", PAYMAIN)["records"]
    assert [(r["level"], r["name"], r["line"]) for r in rows] == EXPECTED
    # each program's records nest under its own groups only
    tree = _tree(rows, "parent_ordinal")
    assert tree[9:12] == [("WS-AREA", None), ("WS-N", "WS-AREA"), ("WS-A", "WS-AREA")]
    assert tree[5] == ("WS-GROSS", None)
    assert {r["name"]: r["section"] for r in rows}["LK-RPT"] == "LINKAGE"


def test_the_answer_key_reads_every_programs_data_division(tmp_path):
    path = tmp_path / "PAYMAIN.cbl"
    path.write_text(PAYMAIN, encoding="utf-8")
    items = ak._data_items(ak.Source(path))
    assert [(it["level"], it["name"], it["line"]) for it in items] == EXPECTED
    assert _tree(items, "parent")[9:12] == [("WS-AREA", None), ("WS-N", "WS-AREA"), ("WS-A", "WS-AREA")]


def test_a_one_program_source_is_unchanged():
    rows = extract_boundary("cobol", ONE)["records"]
    assert [(r["name"], r["line"]) for r in rows] == [("WS-X", 5), ("WS-Y", 6)]


@pytest.fixture(scope="module")
def ir(tmp_path_factory):
    base = tmp_path_factory.mktemp("multi_program_4245")
    repo = base / "estate"
    for rel, text in {
        "cbl/PAYMAIN.cbl": PAYMAIN,
        "cbl/CALLER.cbl": CALLER,
        "cbl/ONE.cbl": ONE,
        "cbl/NEST.cbl": NEST,
    }.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    return load_galaxy_ir(scan_to_db(repo, base / "scan"))


def test_each_item_names_its_owning_program(ir):
    items = ir.files["cbl/PAYMAIN.cbl"].data_items
    assert [(it.name, it.program) for it in items if it.level == 1] == [
        ("WS-AREA", "PAYMAIN"), ("WS-IN", "PAYMAIN"), ("WS-PGM", "PAYMAIN"),
        ("WS-GROSS", "PAYCALC"), ("WS-I", "PAYCALC"), ("LK-AREA", "PAYCALC"),
        ("WS-AREA", "PAYRPT"), ("WS-IN", "PAYRPT"), ("WS-PGM", "PAYRPT"), ("LK-RPT", "PAYRPT"),
    ]  # fmt: skip
    assert {it.program for it in ir.files["cbl/ONE.cbl"].data_items} == {None}


def test_same_named_records_of_sibling_programs_do_not_collide(ir):
    flows = {fl["line"]: fl for fl in ir.data_flows() if fl["file"] == "cbl/PAYMAIN.cbl"}
    main, rpt = flows[11], flows[42]
    assert (main["status"], rpt["status"]) == ("resolved", "resolved")
    span = lambda s: (s["record"], s["program"], s["offset"], s["bytes"])  # noqa: E731
    assert span(main["target_span"]) == ("WS-AREA", "PAYMAIN", 0, 4)
    assert span(rpt["target_span"]) == ("WS-AREA", "PAYRPT", 2, 8)
    assert span(rpt["source_span"]) == ("WS-IN", "PAYRPT", 0, 8)
    assert main["truncates"] is False and rpt["truncates"] is False
    # a one-program source keeps its spans' program as None
    (one,) = [fl for fl in ir.data_flows() if fl["file"] == "cbl/ONE.cbl"]
    assert one["status"] == "resolved" and one["target_span"]["program"] is None


def test_call_using_reads_its_own_programs_storage(ir):
    calls = {(c["caller"], c["line"]): c for c in ir.call_contracts()}
    assert calls[("cbl/PAYMAIN.cbl", 13)]["args"][0]["caller_bytes"] == 8
    assert calls[("cbl/PAYMAIN.cbl", 44)]["args"][0]["caller_bytes"] == 10
    # CALL 'PAYRPT' enters PAYRPT's PROCEDURE DIVISION USING LK-RPT, not PAYMAIN's (no USING)
    into = calls[("cbl/CALLER.cbl", 7)]
    assert (into["callee"], into["status"]) == ("cbl/PAYMAIN.cbl", "paired")
    assert (into["args"][0]["parameter"], into["args"][0]["callee_bytes"]) == ("LK-RPT", 12)


def test_dynamic_call_targets_read_their_own_programs_value(ir):
    got = {d["line"]: [c["program"] for c in d["candidates"]] for d in ir.dynamic_call_targets()
           if d["file"] == "cbl/PAYMAIN.cbl"}  # fmt: skip
    assert got == {12: ["PAYSUB1"], 43: ["PAYSUB2"]}


def test_field_lineage_stays_inside_the_named_program(ir):
    hops = ir.field_lineage("cbl/PAYMAIN.cbl", "WS-IN", program="PAYRPT")
    assert [(h["item"], h["program"]) for h in hops] == [("WS-IN", "PAYRPT"), ("WS-A", "PAYRPT")]


def test_a_nested_program_reads_its_containers_global_item(ir):
    # NIST IC228A-1 reads IC228A's `01 GLOBAL-DATA IS GLOBAL`: a name the nested program does not
    # declare is the containing program's GLOBAL item, not unresolved.
    flows = {fl["line"]: fl for fl in ir.data_flows() if fl["file"] == "cbl/NEST.cbl"}
    assert flows[16]["status"] == flows[17]["status"] == "resolved"
    assert (flows[16]["target_span"]["record"], flows[16]["target_span"]["program"]) == ("G-DATA", "OUTER")
    assert (flows[17]["target_span"]["record"], flows[17]["target_span"]["program"]) == ("W-IN", "INNER")
