"""#4420 (estate-crucible H-0053): with a declared SYSLIB, a COPY no declared library holds draws no
edge -- it must not fall back to a PROGRAM source of the same name -- and is recorded as a gap.
#4421: the collision and gap reports are persisted in the master DB (a --db-only scan), restored by
the state rehydrator and exposed through GalaxyIR."""

import json
import sqlite3

import pytest

from gitgalaxy.core.state_rehydrator import StateRehydrator
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

MAIN = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ORDMAIN.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-DATE.
           COPY DATEWS.
       01  WS-PRICE.
           COPY ORDPRICE.
       01  WS-RATE.
           COPY ORDPRICE IN ORDCPY.
           EXEC SQL INCLUDE SQLCA END-EXEC.
       PROCEDURE DIVISION.
           GOBACK.
"""
# an importer outside every declared `programs` glob: no SYSLIB declared for it
LOOSE = MAIN.replace("ORDMAIN", "LOOSEPGM")
PRICE_PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ORDPRICE.
       PROCEDURE DIVISION.
           GOBACK.
"""
DATEWS = "           05  WS-D   PIC X(8).\n"
DECLARATION = {
    "libraries": {"ORDCPY": ["apps/ORDR/copybook"], "SHRCPY": ["shared/copylib"]},
    "syslib": [{"programs": "apps/ORDR/*", "order": ["ORDCPY", "SHRCPY"]}],
}


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("copy_gaps")
    repo = base / "estate"
    for rel, text in {
        "apps/ORDR/cobol/ORDMAIN.cbl": MAIN,
        "apps/ORDR/cobol/ORDPRICE.cbl": PRICE_PROGRAM,
        "apps/ORDR/copybook/DATEWS.cpy": DATEWS,
        "shared/copylib/DATEWS.cpy": DATEWS,  # a collision, to persist
        "other/LOOSEPGM.cbl": LOOSE,
    }.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    spec = base / "libraries.json"
    spec.write_text(json.dumps(DECLARATION), encoding="utf-8")
    db = scan_to_db(repo, base / "scan", extra_args=["--copy-libraries", str(spec)])
    return db, load_galaxy_ir(db)


def test_a_member_in_no_declared_library_does_not_link_to_a_same_named_program(scanned):
    _, ir = scanned
    assert ir.files["apps/ORDR/cobol/ORDMAIN.cbl"].copy_deps == ["apps/ORDR/copybook/DATEWS.cpy"]


def test_the_gap_is_recorded_for_unqualified_and_in_library_copies_and_the_runtime_member(scanned):
    _, ir = scanned
    gaps = {(g["importer"], g["member"], tuple(g["searched"])) for g in ir.copy_member_gaps}
    assert ("apps/ORDR/cobol/ORDMAIN.cbl", "ORDPRICE", ("ORDCPY", "SHRCPY")) in gaps
    assert ("apps/ORDR/cobol/ORDMAIN.cbl", "ORDPRICE", ("ORDCPY",)) in gaps  # COPY ... IN ORDCPY
    assert ("apps/ORDR/cobol/ORDMAIN.cbl", "SQLCA", ("ORDCPY", "SHRCPY")) in gaps  # runtime-supplied: no edge


def test_an_undeclared_importer_keeps_the_default_resolver_and_has_no_gaps(scanned):
    _, ir = scanned
    # no SYSLIB search order for it: only its explicit `IN ORDCPY` (a declared library) can be a gap
    assert [g["searched"] for g in ir.copy_member_gaps if g["importer"].startswith("other/")] == [["ORDCPY"]]
    assert ir.files["other/LOOSEPGM.cbl"].copy_deps  # still resolved by the default resolver


def test_collisions_are_persisted_by_a_db_only_scan_and_exposed_by_galaxy_ir(scanned):
    db, ir = scanned
    assert [(c["importer"], c["member"], c["library"]) for c in ir.copy_member_collisions] == [
        ("apps/ORDR/cobol/ORDMAIN.cbl", "DATEWS", "ORDCPY")
    ]
    conn = sqlite3.connect(db)
    try:
        raw = conn.execute("SELECT copy_member_collisions FROM repo_data").fetchone()[0]
    finally:
        conn.close()
    assert json.loads(raw) == ir.copy_member_collisions


def test_the_state_rehydrator_restores_both_reports(scanned):
    db, ir = scanned
    state = StateRehydrator(str(db)).load_state(ir.repo_name)
    assert state["copy_member_collisions"] == ir.copy_member_collisions
    assert state["copy_member_gaps"] == ir.copy_member_gaps


def test_a_scan_without_copy_libraries_persists_no_reports(tmp_path):
    repo = tmp_path / "estate"
    (repo / "a").mkdir(parents=True)
    (repo / "a" / "ORDMAIN.cbl").write_text(MAIN, encoding="utf-8")
    ir = load_galaxy_ir(scan_to_db(repo, tmp_path / "scan"))
    assert ir.copy_member_collisions is None and ir.copy_member_gaps is None
