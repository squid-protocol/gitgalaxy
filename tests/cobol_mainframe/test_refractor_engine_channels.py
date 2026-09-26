"""
#3348: the refractor reads DD lineage, dynamic CALLs and record layouts from the engine's
fact channels (dataset_data, call_site_data, record_data) instead of re-parsing the source.

One real scan of a program whose dead paragraph OPENs a file and CALLs a program
through an identifier backs the tests. The pinned mainframe corpora never do that
(0 masked OPENs / CALLs over 123 programs), so this fixture is what pins the masking:
the engine's facts in a paragraph the forge's reachability analysis calls dead are
dropped, exactly as the forge drops them. Both paths are pinned -- engine-sourced (a DB
with the channels) and the forge fallback (no DB, or a DB from before the channels) --
and so is the channel's own round trip (write, delta-scan restore, reader).
"""

import shutil
import sqlite3

import pytest

import gitgalaxy.cobol_refractor_controller as controller
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

LEDGER = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. LEDGER.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT IN-FILE ASSIGN TO UT-S-INDD.
           SELECT OUT-FILE ASSIGN TO OUTDD.
           SELECT OLD-FILE ASSIGN TO OLDDD.
       DATA DIVISION.
       FILE SECTION.
       FD  IN-FILE.
       01  IN-REC                PIC X(80).
       FD  OUT-FILE.
       01  OUT-REC               PIC X(80).
       FD  OLD-FILE.
       01  OLD-REC               PIC X(80).
       WORKING-STORAGE SECTION.
       01  WS-AMOUNT-DISPLAY     PIC +9(7).99.
       01  WS-TOTALS.
           05 WS-TOTAL           PIC S9(9)V99 COMP-3.
           05 WS-TOTAL-X REDEFINES WS-TOTAL PIC X(6).
           05 WS-COUNT           PIC 9(4) COMP.
           05 WS-ROW-AMT         PIC 9(5)V99 OCCURS 1 TO 10
                                 DEPENDING ON WS-COUNT.
       01  WS-PGM                PIC X(8) VALUE 'POSTPGM'.
       01  WS-OLD-PGM            PIC X(8).
       PROCEDURE DIVISION.
       000-MAIN.
           OPEN INPUT IN-FILE
                OUTPUT OUT-FILE.
           CALL WS-PGM.
           PERFORM 100-POST.
           CLOSE IN-FILE OUT-FILE.
           STOP RUN.
       100-POST.
           ADD 1 TO WS-TOTAL.
           MOVE WS-TOTAL TO WS-AMOUNT-DISPLAY.
           DISPLAY WS-TOTAL-X WS-ROW-AMT (1).
       900-RETIRED.
           OPEN I-O OLD-FILE.
           CALL WS-OLD-PGM.
"""


LINES = LEDGER.splitlines()
OPEN_LIVE = next(n for n, t in enumerate(LINES, 1) if "OPEN INPUT IN-FILE" in t)
OPEN_DEAD = next(n for n, t in enumerate(LINES, 1) if "OPEN I-O OLD-FILE" in t)


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("engine_channels")
    repo = base / "legacy"
    (repo / "src").mkdir(parents=True)
    (repo / "src/LEDGER.cbl").write_text(LEDGER, encoding="utf-8")
    return repo, scan_to_db(repo, base / "scan")


def _payload(repo, tmp_path, engine_file=None):
    work = tmp_path / "work"
    shutil.copytree(repo, work, dirs_exist_ok=True)
    mgr = controller.IRStateManager("RAM", tmp_path)
    return controller.process_payload(work / "src/LEDGER.cbl", mgr, engine_file=engine_file)


def _pre_3348(db, tmp_path):
    """The same DB as a scan from before the channels: no open_sites, no record_data."""
    old = tmp_path / "old.db"
    shutil.copy(db, old)
    with sqlite3.connect(old) as conn:
        conn.execute("ALTER TABLE dataset_data DROP COLUMN open_sites")
        conn.execute("DROP TABLE record_data")
    return old


def test_the_engine_records_every_open_site(scanned):
    _, db = scanned
    by_dd = {d.dd_name: d for d in load_galaxy_ir(db).files["src/LEDGER.cbl"].datasets}
    # A site is the OPEN statement's line: OUTPUT OUT-FILE on the next line is the same OPEN.
    assert by_dd["INDD"].open_sites == [("INPUT", OPEN_LIVE)]
    assert by_dd["OUTDD"].open_sites == [("OUTPUT", OPEN_LIVE)]
    assert by_dd["OLDDD"].open_sites == [("I-O", OPEN_DEAD)]


def test_with_a_db_lineage_calls_and_schemas_come_from_the_engine(scanned, tmp_path):
    repo, db = scanned
    ir = _payload(repo, tmp_path, load_galaxy_ir(db).files["src/LEDGER.cbl"])
    assert ir["metadata"]["ir_sources"] == {"lineage": "galaxy_db", "schemas": "galaxy_db"}
    lineage = ir["analysis"]["lineage"]
    # 900-RETIRED is dead: its OPEN I-O OLD-FILE and CALL WS-OLD-PGM are dropped.
    assert "900-RETIRED" in ir["analysis"]["dead_code"]["dead_paras"]
    assert (lineage["inputs"], lineage["outputs"], lineage["unresolved_calls"]) == ({"INDD"}, {"OUTDD"}, ["WS-PGM"])
    props = ir["generation"]["schemas"]["json"]["properties"]
    assert {"WS_AMOUNT_DISPLAY", "WS_TOTAL", "WS_TOTAL_X", "WS_ROW_AMT"} <= set(props)
    assert "COMP-3 (Packed Decimal)" in ir["generation"]["schemas"]["sql"]
    assert "OCCURS DEPENDING ON" in ir["generation"]["schemas"]["sql"]


def test_the_engine_and_the_forge_agree(scanned, tmp_path):
    repo, db = scanned
    engine = _payload(repo, tmp_path / "a", load_galaxy_ir(db).files["src/LEDGER.cbl"])
    forge = _payload(repo, tmp_path / "b")
    assert "ir_source" not in forge["metadata"]
    assert forge["metadata"]["ir_sources"] == {"lineage": "forge", "schemas": "forge"}
    assert engine["analysis"]["lineage"] == forge["analysis"]["lineage"]
    assert engine["generation"]["schemas"] == forge["generation"]["schemas"]


def test_a_db_from_before_the_channels_falls_back_to_the_forge(scanned, tmp_path):
    repo, db = scanned
    ef = load_galaxy_ir(_pre_3348(db, tmp_path)).files["src/LEDGER.cbl"]
    assert {d.open_sites for d in ef.datasets} == {None} and not ef.records_read
    ir = _payload(repo, tmp_path, ef)
    assert ir["metadata"]["ir_source"] == "galaxy_db"  # PROGRAM-ID, COPY graph, units still from the DB
    assert ir["metadata"]["ir_sources"] == {"lineage": "forge", "schemas": "forge"}
    assert ir["analysis"]["lineage"]["inputs"] == {"INDD"} and ir["generation"]["schemas"]


def test_open_sites_survive_a_delta_scan(scanned):
    from gitgalaxy.core.state_rehydrator import StateRehydrator

    _, db = scanned
    cache = StateRehydrator(str(db)).load_state("legacy")["ram_cache"]
    rows = {d["dd_name"]: d["open_sites"] for d in cache["src/LEDGER.cbl"]["dataset_bindings"]}
    assert rows == {"INDD": [["INPUT", OPEN_LIVE]], "OUTDD": [["OUTPUT", OPEN_LIVE]], "OLDDD": [["I-O", OPEN_DEAD]]}


def test_a_baseline_without_open_sites_still_rehydrates(scanned, tmp_path):
    from gitgalaxy.core.state_rehydrator import StateRehydrator

    _, db = scanned
    cache = StateRehydrator(str(_pre_3348(db, tmp_path))).load_state("legacy")["ram_cache"]
    assert all("open_sites" not in d for d in cache["src/LEDGER.cbl"]["dataset_bindings"])
