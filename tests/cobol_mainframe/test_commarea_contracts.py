"""
#3355: the COMMAREA contract join in galaxy_ir -- the record a CICS LINK/XCTL/
RETURN TRANSID passes, COPY-expanded, against the callee's LINKAGE DFHCOMMAREA.

One real galaxyscope scan backs every test (as test_galaxy_ir.py does), so the
join is pinned against the columns the engine actually writes: call_site_data's
commarea operands, record_data's copy_members, the resolved COPY edges and the
CSD transaction map. Each shape is one the pinned corpora carry:

  - CBSA's `01 X.` + `COPY INQCUST.` on BOTH sides (same copybook: paired, no
    mismatch);
  - a callee whose own layout disagrees with the passed record (CBSA BNK1UAC ->
    UPDACC: a trailing POINTER one side lacks) -- a length AND shape mismatch,
    reported as data;
  - carddemo's opaque callee `PIC X OCCURS 1 TO 32767 DEPENDING ON EIBCALEN`
    (variable: never claimed as a mismatch);
  - carddemo's `COPY COCOM01Y.` (an 01-level record copybook) continued in the
    program by `05 CDEMO-CPVD-INFO.`, which the engine's same-file level stack
    threads under the group above the COPY;
  - an XCTL through a data-name with no VALUE (callee unresolved);
  - `RETURN TRANSID(...) COMMAREA(...)` resolved through the CSD map.
"""

import shutil
import sqlite3

import pytest

from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

CUSTCOMM = """\
          03 CUST-EYE                  PIC X(4).
          03 CUST-NO                   PIC 9(10).
          03 CUST-BAL                  PIC S9(10)V99 COMP-3.
"""

APPCOMM = """\
       01 APP-COMMAREA.
          05 APP-FROM-PGM              PIC X(8).
          05 APP-USER                  PIC X(8).
"""

CALLER = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CALLER.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-DYN-PGM                   PIC X(8).
       01 WS-CUST.
          COPY CUSTCOMM.
       01 WS-UPD.
          03 UPD-EYE                   PIC X(4).
          03 UPD-AMT                   PIC S9(7) COMP-3.
          03 UPD-PTR                   POINTER.
       01 WS-GROUP.
          05 WS-FLAG                   PIC X.
       COPY APPCOMM.
          05 APP-EXTRA                 PIC X(10).
       LINKAGE SECTION.
       01 DFHCOMMAREA.
          COPY CUSTCOMM.
       PROCEDURE DIVISION USING DFHCOMMAREA.
       A010.
           EXEC CICS LINK PROGRAM('CUSTPGM')
                COMMAREA(WS-CUST)
           END-EXEC.
           EXEC CICS LINK PROGRAM('UPDPGM')
                COMMAREA(WS-UPD)
                LENGTH(12)
           END-EXEC.
           EXEC CICS XCTL PROGRAM('MENUPGM')
                COMMAREA(APP-COMMAREA)
           END-EXEC.
           EXEC CICS XCTL PROGRAM(WS-DYN-PGM)
                COMMAREA(APP-COMMAREA)
           END-EXEC.
           EXEC CICS LINK PROGRAM('CUSTPGM') END-EXEC.
           EXEC CICS RETURN TRANSID('CALR')
                COMMAREA(WS-CUST)
                LENGTH(LENGTH OF WS-CUST)
           END-EXEC.
"""

CUSTPGM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CUSTPGM.
       DATA DIVISION.
       LINKAGE SECTION.
       01 DFHCOMMAREA.
          COPY CUSTCOMM.
       PROCEDURE DIVISION USING DFHCOMMAREA.
           EXEC CICS RETURN END-EXEC.
"""

UPDPGM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. UPDPGM.
       DATA DIVISION.
       LINKAGE SECTION.
       01 DFHCOMMAREA.
          03 COMM-EYE                  PIC X(4).
          03 COMM-AMT                  PIC S9(7) COMP-3.
       PROCEDURE DIVISION USING DFHCOMMAREA.
           EXEC CICS RETURN END-EXEC.
"""

MENUPGM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. MENUPGM.
       DATA DIVISION.
       LINKAGE SECTION.
       01  DFHCOMMAREA.
         05  LK-COMMAREA                           PIC X(01)
             OCCURS 1 TO 32767 TIMES DEPENDING ON EIBCALEN.
       PROCEDURE DIVISION.
           EXEC CICS RETURN END-EXEC.
"""

APPCSD = """\
 DEFINE TRANSACTION(CALR) GROUP(APP)
        PROGRAM(CALLER) STATUS(ENABLED)
"""


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("commarea")
    repo = base / "cicsapp"
    files = {
        "src/CALLER.cbl": CALLER,
        "src/CUSTPGM.cbl": CUSTPGM,
        "src/UPDPGM.cbl": UPDPGM,
        "src/MENUPGM.cbl": MENUPGM,
        "copy/CUSTCOMM.cpy": CUSTCOMM,
        "copy/APPCOMM.cpy": APPCOMM,
        "csd/APP.csd": APPCSD,
    }
    for rel, text in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return scan_to_db(repo, base / "scan")


@pytest.fixture(scope="module")
def contracts(scanned):
    return {(c["verb"], c["line"]): c for c in load_galaxy_ir(scanned).commarea_contracts()}


def _by(contracts, verb, target):
    return [c for (v, _), c in sorted(contracts.items()) if v == verb and c["target"] == target]


def test_the_operands_load_on_each_call(scanned):
    calls = load_galaxy_ir(scanned).files["src/CALLER.cbl"].calls
    upd = next(c for c in calls if c.target == "UPDPGM")
    assert (upd.commarea, upd.commarea_length, upd.commarea_datalength) == ("WS-UPD", "12", None)
    bare = [c for c in calls if c.target == "CUSTPGM" and c.commarea is None]
    assert len(bare) == 1


def test_copy_members_load_on_the_item(scanned):
    ir = load_galaxy_ir(scanned)
    ws_cust = next(i for i in ir.files["src/CALLER.cbl"].data_items if i.name == "WS-CUST")
    assert ws_cust.copy_members == "CUSTCOMM"


def test_same_copybook_on_both_sides_pairs_cleanly(contracts):
    link, bare = _by(contracts, "LINK", "CUSTPGM")
    assert link["status"] == "paired" and link["callee"] == "src/CUSTPGM.cbl"
    assert link["caller_record"]["bytes"] == link["callee_record"]["bytes"] == 4 + 10 + 7
    assert link["caller_record"]["fields"] == 3 and link["same_copybook"] is True
    assert link["mismatches"] == []
    # A LINK passing nothing is still listed, so a site count is a real denominator.
    assert bare["status"] == "no_commarea" and bare["caller_record"] is None


def test_a_disagreeing_callee_is_reported_not_adjudicated(contracts):
    (upd,) = _by(contracts, "LINK", "UPDPGM")
    assert upd["status"] == "paired"
    assert (upd["caller_record"]["bytes"], upd["callee_record"]["bytes"]) == (4 + 4 + 4, 4 + 4)
    kinds = {m["kind"]: m for m in upd["mismatches"]}
    assert kinds["length"] == {"kind": "length", "caller": 12, "callee": 8}
    assert kinds["shape"]["caller"] == "UPD-PTR" and kinds["shape"]["callee"] is None
    # LENGTH(12) agrees with the record passed: no declared_length finding.
    assert upd["declared_length"] == 12 and "declared_length" not in kinds


def test_an_opaque_variable_callee_is_never_a_mismatch(contracts):
    (menu,) = _by(contracts, "XCTL", "MENUPGM")
    assert menu["status"] == "paired"
    assert menu["callee_record"]["variable"] is True
    assert menu["mismatches"] == []


def test_a_01_level_copybook_record_is_found_and_continued_in_the_program(contracts):
    """APP-COMMAREA lives only in APPCOMM.cpy; the program's `05 APP-EXTRA` after
    the COPY continues it (carddemo COCOM01Y + CDEMO-CPVD-INFO)."""
    (menu,) = _by(contracts, "XCTL", "MENUPGM")
    rec = menu["caller_record"]
    assert (rec["name"], rec["file"]) == ("APP-COMMAREA", "copy/APPCOMM.cpy")
    assert (rec["fields"], rec["bytes"]) == (3, 8 + 8 + 10)


def test_the_continuation_is_not_counted_in_the_group_above_the_copy(scanned):
    ir = load_galaxy_ir(scanned)
    caller = ir.files["src/CALLER.cbl"]
    group = next(i for i in caller.data_items if i.name == "WS-GROUP")
    layout = ir.record_layout(caller, group)
    assert [f["name"] for f in layout["fields"]] == ["WS-FLAG"] and layout["bytes"] == 1


def test_an_unresolved_target_keeps_its_caller_record(contracts):
    (dyn,) = [c for (v, _), c in contracts.items() if v == "XCTL" and c["target"] is None]
    assert dyn["status"] == "callee_unresolved" and dyn["callee"] is None
    assert dyn["caller_record"]["name"] == "APP-COMMAREA"


def test_return_transid_resolves_through_the_csd_map(contracts):
    (ret,) = _by(contracts, "RETURN TRANSID", "CALR")
    assert ret["callee"] == "src/CALLER.cbl" and ret["status"] == "paired"
    assert ret["commarea_length"] == "LENGTH OF WS-CUST" and ret["declared_length"] is None
    assert ret["mismatches"] == []


def test_a_db_written_before_3355_loads_with_no_contract_operands(scanned, tmp_path):
    old = tmp_path / "old.db"
    shutil.copy(scanned, old)
    with sqlite3.connect(old) as conn:
        for table, cols in (
            ("call_site_data", ("commarea", "commarea_length", "commarea_datalength")),
            ("record_data", ("copy_members",)),
        ):
            for col in cols:
                conn.execute(f"ALTER TABLE {table} DROP COLUMN {col}")
    ir = load_galaxy_ir(old)
    calls = ir.files["src/CALLER.cbl"].calls
    assert calls and all(c.commarea is None for c in calls)
    contracts = ir.commarea_contracts()
    assert contracts and {c["status"] for c in contracts if c["verb"] != "RETURN TRANSID"} <= {
        "no_commarea",
        "callee_unresolved",
    }
