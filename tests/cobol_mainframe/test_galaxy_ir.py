"""
#3120: the refraction pipeline's engine IR source (gitgalaxy/tools/cobol_to_cobol/galaxy_ir.py).

One real galaxyscope scan of a three-file mainframe fixture (program, copybook,
JCL member) backs every test, so the reader is pinned against the schema the
engine actually writes rather than a hand-built imitation of it.
"""

import shutil
import sqlite3
from unittest.mock import patch

import pytest

import gitgalaxy.cobol_refractor_controller as controller_module
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

PAYROLL = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYROLL.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT EMP-FILE ASSIGN TO EMPIN.
       DATA DIVISION.
       FILE SECTION.
       FD  EMP-FILE.
       01  EMP-REC PIC X(80).
       WORKING-STORAGE SECTION.
           COPY EMPREC.
       PROCEDURE DIVISION.
       000-MAIN.
           OPEN INPUT EMP-FILE.
           PERFORM 100-CALC.
           CLOSE EMP-FILE.
           STOP RUN.
       100-CALC.
           MOVE 1 TO EMP-ID.
"""

EMPREC = """\
       01  EMP-WS.
           05 EMP-ID   PIC 9(5).
"""

PAYJOB = """\
//PAYJOB   JOB (ACCT),'PAYROLL'
//STEP01   EXEC PGM=PAYROLL
//EMPIN    DD DSN=HR.EMP.MASTER,DISP=SHR
"""


def _write_fixture(root):
    for rel, text in {"src/PAYROLL.cbl": PAYROLL, "copy/EMPREC.cpy": EMPREC, "jcl/PAYJOB.jcl": PAYJOB}.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("galaxy_ir")
    repo = base / "legacy"
    _write_fixture(repo)
    db = scan_to_db(repo, base / "scan")
    return repo, db


def test_scan_writes_the_master_db_named_after_the_target(scanned):
    _, db = scanned
    assert db.name == "legacy_galaxy_master.db"


def test_programs_exclude_copybooks(scanned):
    _, db = scanned
    ir = load_galaxy_ir(db)
    assert [f.file_path for f in ir.programs("cobol")] == ["src/PAYROLL.cbl"]
    assert not ir.files["copy/EMPREC.cpy"].is_program


def test_program_id_units_and_copy_edge(scanned):
    _, db = scanned
    payroll = load_galaxy_ir(db).files["src/PAYROLL.cbl"]
    assert payroll.program_ids == ["PAYROLL"]
    assert [u.name for u in payroll.units] == ["000-MAIN", "100-CALC"]
    assert payroll.units[0].start_line == 14
    assert payroll.copy_deps == ["copy/EMPREC.cpy"]


def test_inventory_spans_the_mainframe_family(scanned):
    _, db = scanned
    ir = load_galaxy_ir(db)
    assert ir.inventory() == {"cobol": {"files": 1, "units": 2}, "jcl": {"files": 1, "units": 1}}
    assert ir.inventory(languages=("jcl",)) == {"jcl": {"files": 1, "units": 1}}


def test_lookup_resolves_against_the_target_root(scanned):
    repo, db = scanned
    ir = load_galaxy_ir(db)
    assert ir.lookup(repo / "src" / "PAYROLL.cbl", repo).program_ids == ["PAYROLL"]
    assert ir.lookup(repo.parent / "elsewhere.cbl", repo) is None


def test_reader_opens_read_only(scanned, tmp_path):
    _, db = scanned
    copy = tmp_path / "copy.db"
    shutil.copy(db, copy)
    before = copy.read_bytes()
    load_galaxy_ir(copy)
    assert copy.read_bytes() == before
    with pytest.raises(FileNotFoundError):
        load_galaxy_ir(tmp_path / "missing.db")
    assert not (tmp_path / "missing.db").exists()


def test_a_multi_repo_db_needs_an_explicit_repo_name(scanned, tmp_path):
    _, db = scanned
    copy = tmp_path / "multi.db"
    shutil.copy(db, copy)
    with sqlite3.connect(copy) as conn:
        conn.execute("INSERT INTO repo_data (repo_name, commit_hash, commit_date) VALUES ('other', 'x', '2000-01-01')")
    with pytest.raises(ValueError, match="pass repo_name"):
        load_galaxy_ir(copy)
    assert load_galaxy_ir(copy, repo_name="legacy").programs()[0].program_ids == ["PAYROLL"]


# ==============================================================================
# Refractor wiring
# ==============================================================================
def test_process_payload_carries_engine_fields(scanned, tmp_path):
    repo, db = scanned
    work = tmp_path / "legacy"
    shutil.copytree(repo, work)
    engine_file = load_galaxy_ir(db).files["src/PAYROLL.cbl"]
    mgr = controller_module.IRStateManager("RAM", tmp_path)

    ir = controller_module.process_payload(work / "src" / "PAYROLL.cbl", mgr, engine_file=engine_file)

    assert ir["metadata"]["ir_source"] == "galaxy_db"
    assert ir["analysis"]["base_intent"]["program_id"] == "PAYROLL"
    assert ir["analysis"]["copy_dependencies"] == ["copy/EMPREC.cpy"]
    assert [u["name"] for u in ir["analysis"]["engine_units"]] == ["000-MAIN", "100-CALC"]
    # The forge still owns what the DB does not carry.
    assert ir["analysis"]["base_intent"]["files_requested"] == [{"internal": "EMP-FILE", "dd_name": "EMPIN"}]
    assert "EMPIN" in ir["analysis"]["lineage"]["inputs"]


def test_process_payload_without_engine_file_is_unchanged(scanned, tmp_path):
    repo, _ = scanned
    work = tmp_path / "legacy"
    shutil.copytree(repo, work)
    ir = controller_module.process_payload(
        work / "src" / "PAYROLL.cbl", controller_module.IRStateManager("RAM", tmp_path)
    )
    assert "ir_source" not in ir["metadata"]
    assert "copy_dependencies" not in ir["analysis"]
    assert "engine_units" not in ir["analysis"]


def test_main_with_galaxy_db_reports_the_engine_inventory(scanned, tmp_path):
    repo, db = scanned
    work = tmp_path / "legacy"
    shutil.copytree(repo, work)
    with patch("sys.argv", ["refract", str(work), "--galaxy-db", str(db)]):
        controller_module.main()

    (clean_dir,) = tmp_path.glob("legacy_gitgalaxy_clean_*")
    report = (clean_dir / "03_audit_reports" / "master_refraction_audit.txt").read_text()
    assert "[5] ENGINE INVENTORY" in report
    assert "jcl       : 1 files, 1 units (detected, not yet migratable)" in report
    assert (clean_dir / "04_ir_state_dumps" / "PAYROLL_ir.json").exists()


def test_main_refuses_a_db_of_another_target(scanned, tmp_path, capsys):
    _, db = scanned
    other = tmp_path / "other"
    other.mkdir()
    with patch("sys.argv", ["refract", str(other), "--galaxy-db", str(db)]), pytest.raises(SystemExit) as exc:
        controller_module.main()
    assert exc.value.code == 1
    assert "does not describe" in capsys.readouterr().out
    assert not list(tmp_path.glob("other_gitgalaxy_clean_*")), "a rejected DB must not leave a clean room behind"
