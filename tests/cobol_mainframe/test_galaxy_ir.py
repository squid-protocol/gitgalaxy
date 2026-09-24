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
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import (
    EngineCicsResource,
    EngineFile,
    GalaxyIR,
    load_galaxy_ir,
    scan_to_db,
)

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


def test_records_carry_fd_layouts_and_the_item_tree(scanned):
    """#3246: PAYROLL's own DATA DIVISION is its FILE SECTION `01 EMP-REC` bound
    to FD EMP-FILE; the WORKING-STORAGE `COPY EMPREC` layout belongs to the
    copybook file, not the program (same-file only, like copy_deps)."""
    ir = load_galaxy_ir(scanned[1])
    payroll = ir.files["src/PAYROLL.cbl"]
    assert [(r.name, r.fd_name, r.pic, r.section) for r in payroll.records] == [
        ("EMP-REC", "EMP-FILE", "X(80)", "FILE")
    ]
    # The copybook carries its own tree: EMP-WS group with an EMP-ID field under it.
    emprec = ir.files["copy/EMPREC.cpy"]
    root = emprec.records[0]
    assert (root.name, root.is_group) == ("EMP-WS", True)
    assert [c.name for c in root.children] == ["EMP-ID"]
    assert root.children[0].pic == "9(5)"


def test_a_pre_3246_db_loads_with_no_records(scanned, tmp_path):
    """A master DB written before #3246 has no record_data table; the reader must
    treat it as 'no records', not fail -- the same rule as call_site/dataset_data."""
    copy = tmp_path / "old.db"
    shutil.copy(scanned[1], copy)
    with sqlite3.connect(copy) as conn:
        conn.execute("DROP TABLE record_data")
    ir = load_galaxy_ir(copy)
    assert all(not f.records and not f.data_items for f in ir.files.values())


# #3250: PL/I DECLAREd structures ride the same record_data spine. A REAL scan,
# so the top-level `boundary_extraction` declaration is proven to survive the
# config pipeline (language_lens + PROJECT_OVERRIDES) -- the #2806 trap unit
# tests that build from LANGUAGE_DEFINITIONS cannot see.
CUSTPGM = """\
 CUSTPGM: PROC OPTIONS(MAIN);
   DCL 1 CUSTOMER_RECORD  BASED(ADDR(CUSTFILE_RECORD)),
         2 CUSTOMER_KEY,
           3 CUST_ID         CHAR(5),
         2 ACCT_BALANCE      PIC '9999999V99',
         2 ORDERS(12)        FIXED DEC(7,2);
   DCL TRAN_COMMENT CHAR(1) DEFINED CUSTFILE_RECORD;
 END CUSTPGM;
"""


@pytest.fixture(scope="module")
def scanned_pli(tmp_path_factory):
    base = tmp_path_factory.mktemp("galaxy_ir_pli")
    repo = base / "plirepo"
    (repo / "PLI").mkdir(parents=True)
    (repo / "PLI" / "CUSTPGM.pli").write_text(CUSTPGM, encoding="utf-8")
    return scan_to_db(repo, base / "scan")


def test_pli_structures_load_as_a_record_tree(scanned_pli):
    ef = load_galaxy_ir(scanned_pli).files["PLI/CUSTPGM.pli"]
    assert ef.language == "pli"
    assert [r.name for r in ef.records] == ["CUSTOMER_RECORD", "TRAN_COMMENT"]
    root = ef.records[0]
    assert (root.section, root.attributes, root.is_group) == ("BASED", "BASED(ADDR(CUSTFILE_RECORD))", True)
    key, balance, orders = root.children
    assert [c.name for c in key.children] == ["CUST_ID"]
    # A PL/I elementary item has its type in `usage` and no PIC: it is not a group.
    cust_id = key.children[0]
    assert (cust_id.usage, cust_id.pic, cust_id.is_group) == ("CHAR(5)", None, False)
    assert (balance.pic, balance.is_group) == ("9999999V99", False)
    assert (orders.usage, orders.occurs, orders.attributes) == ("FIXED DEC(7,2)", 12, "(12) FIXED DEC(7,2)")
    assert ef.records[1].redefines == "CUSTFILE_RECORD"


def test_a_pre_3250_db_loads_pli_records_without_attributes(scanned_pli, tmp_path):
    """A record_data table written before `attributes` existed still loads."""
    copy = tmp_path / "old.db"
    shutil.copy(scanned_pli, copy)
    with sqlite3.connect(copy) as conn:
        conn.execute("ALTER TABLE record_data DROP COLUMN attributes")
    ef = load_galaxy_ir(copy).files["PLI/CUSTPGM.pli"]
    assert [r.name for r in ef.records] == ["CUSTOMER_RECORD", "TRAN_COMMENT"]
    assert all(item.attributes is None for item in ef.data_items)


# #3347: BMS screen-field layouts ride their own screen_field_data table. A REAL
# scan, so the top-level `boundary_extraction: "bms"` declaration is proven to
# survive the config pipeline (#2806). The map is cics-banking-sample-application-
# cbsa's BNK1CAM shape: `*` continuation, an INITIAL literal continued mid-word.
BNK1CAM = "\n".join(
    [
        f"{'BNK1CAM  DFHMSD TYPE=&SYSPARM,MODE=INOUT,LANG=COBOL,STORAGE=AUTO,':<71}*",
        "               TIOAPFX=YES",
        f"{'BNK1CA   DFHMDI SIZE=(24,80),':<71}*",
        "               COLUMN=1,LINE=1",
        f"{'         DFHMDF POS=(3,1),LENGTH=57,ATTRB=(NORM,PROT),COLOR=TURQUOISE,':<71}*",
        f"{'               INITIAL=' + chr(39) + 'Please provide the requested information and pr':<71}*",
        "               ess Enter.'",
        f"{'CUSTNO   DFHMDF POS=(6,23),LENGTH=10,ATTRB=(NORM,NUM,FSET),':<71}*",
        "               COLOR=GREEN,HILIGHT=UNDERLINE",
        "*OLDFLD  DFHMDF POS=(7,23),LENGTH=10",
        "         DFHMSD TYPE=FINAL",
        "         END",
        "",
    ]
)


@pytest.fixture(scope="module")
def scanned_bms(tmp_path_factory):
    base = tmp_path_factory.mktemp("galaxy_ir_bms")
    repo = base / "bmsrepo"
    (repo / "bms_src").mkdir(parents=True)
    (repo / "bms_src" / "BNK1CAM.bms").write_text(BNK1CAM, encoding="utf-8")
    return scan_to_db(repo, base / "scan")


def test_bms_maps_load_as_screen_fields(scanned_bms):
    ef = load_galaxy_ir(scanned_bms).files["bms_src/BNK1CAM.bms"]
    assert ef.language == "bms"
    assert [(sf.kind, sf.name, sf.parent_ordinal) for sf in ef.screen_fields] == [
        ("mapset", "BNK1CAM", None),
        ("map", "BNK1CA", 0),
        ("field", None, 1),
        ("field", "CUSTNO", 1),
    ]
    literal, custno = ef.screen_fields[2:]
    assert literal.initial == "Please provide the requested information and press Enter."
    assert (literal.is_symbolic, custno.is_symbolic) == (False, True)
    assert (custno.pos_line, custno.pos_column, custno.length, custno.attrb) == (6, 23, 10, "NORM,NUM,FSET")
    assert custno.attributes == "COLOR=GREEN,HILIGHT=UNDERLINE"
    assert ef.screen_fields[1].attributes == "SIZE=(24,80),COLUMN=1,LINE=1"


def test_a_pre_3347_db_loads_with_no_screen_fields(scanned_bms, tmp_path):
    copy = tmp_path / "old.db"
    shutil.copy(scanned_bms, copy)
    with sqlite3.connect(copy) as conn:
        conn.execute("DROP TABLE screen_field_data")
    assert load_galaxy_ir(copy).files["bms_src/BNK1CAM.bms"].screen_fields == []


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


def test_windows_separators_are_normalized(scanned, tmp_path):
    """A DB scanned on Windows stores `src\\PAYROLL.cbl`; the reader keys by POSIX form."""
    repo, db = scanned
    copy = tmp_path / "windows.db"
    shutil.copy(db, copy)
    with sqlite3.connect(copy) as conn:
        conn.execute("UPDATE file_data SET file_path = REPLACE(file_path, '/', '\\')")
    ir = load_galaxy_ir(copy)
    assert [f.file_path for f in ir.programs()] == ["src/PAYROLL.cbl"]
    assert ir.files["src/PAYROLL.cbl"].copy_deps == ["copy/EMPREC.cpy"]
    assert ir.lookup(repo / "src" / "PAYROLL.cbl", repo) is ir.files["src/PAYROLL.cbl"]


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


# ==============================================================================
# #3211-followup: THE CICS TRANSACTION MAP
# ==============================================================================
# A menu program that routes to a transaction (RETURN TRANSID) and hands control
# to another program (XCTL), the program it routes to, and the CSD deck that maps
# the two transactions to their programs.
MENU = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. MENU.
       PROCEDURE DIVISION.
       000-MAIN.
           EXEC CICS XCTL PROGRAM('PAYPGM') END-EXEC.
           EXEC CICS RETURN TRANSID('PAYT') END-EXEC.
"""

PAYPGM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYPGM.
       PROCEDURE DIVISION.
       000-MAIN.
           STOP RUN.
"""

APPCSD = """\
 DEFINE TRANSACTION(MENU) GROUP(APP)
        PROGRAM(MENU) PROFILE(DFHCICST) STATUS(ENABLED)
 DEFINE TRANSACTION(PAYT) GROUP(APP)
        PROGRAM(PAYPGM) STATUS(ENABLED)
 DEFINE TRANSACTION(EXTN) GROUP(APP)
        PROGRAM(NOTHERE) STATUS(ENABLED)
"""


@pytest.fixture(scope="module")
def txn_scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("galaxy_ir_txn")
    repo = base / "cicsapp"
    for rel, text in {"src/MENU.cbl": MENU, "src/PAYPGM.cbl": PAYPGM, "csd/APP.csd": APPCSD}.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    db = scan_to_db(repo, base / "scan")
    return repo, db


def test_transaction_map_names_each_program_entry_transaction(txn_scanned):
    """The CSD deck resolves each transaction to the program it entry-points."""
    _, db = txn_scanned
    entries = {(t["transid"], t["resolves_to"]) for t in load_galaxy_ir(db).transaction_map()}
    assert ("MENU", "src/MENU.cbl") in entries
    assert ("PAYT", "src/PAYPGM.cbl") in entries


def test_a_transaction_whose_program_is_absent_resolves_to_none(txn_scanned):
    """A transaction pointing at a program this repository does not contain is a
    real front door, kept with resolves_to None rather than dropped."""
    _, db = txn_scanned
    extn = [t for t in load_galaxy_ir(db).transaction_map() if t["transid"] == "EXTN"]
    assert extn and extn[0]["program"] == "NOTHERE" and extn[0]["resolves_to"] is None


def test_the_csd_deck_carries_the_transactions_not_the_cobol_file(txn_scanned):
    """transaction_data hangs off the DEFINING deck; the program files carry none."""
    _, db = txn_scanned
    ir = load_galaxy_ir(db)
    assert {t.transid for t in ir.files["csd/APP.csd"].transactions} == {"MENU", "PAYT", "EXTN"}
    assert ir.files["src/MENU.cbl"].transactions == []


def test_return_transid_routing_rides_in_calls_but_not_unresolved(txn_scanned):
    """The in-source `RETURN TRANSID('PAYT')` is a call site on the program, yet a
    transaction target is never an unresolved PROGRAM call."""
    _, db = txn_scanned
    ir = load_galaxy_ir(db)
    menu = ir.files["src/MENU.cbl"]
    assert any(c.verb == "RETURN TRANSID" and c.target == "PAYT" for c in menu.calls)
    # XCTL PROGRAM('PAYPGM') resolves to a file; RETURN TRANSID is excluded -- so
    # MENU has no unresolved PROGRAM calls at all.
    assert [c for c in ir.unresolved_calls() if c["file"] == "src/MENU.cbl"] == []


# ==============================================================================
# #3344: DB2 DECLARE TABLE / DCLGEN schemas (sql_table_data)
# ==============================================================================
# A real scan (so the config pipeline runs, the #2806 trap): a DCLGEN copybook in
# CBSA's ACCDB2.cpy shape, a program that INCLUDEs it, and a PL/I include.
ACCDB2 = """\
      *  Copyright IBM Corp. 2023
           EXEC SQL DECLARE ACCOUNT TABLE
              ( ACCOUNT_SORTCODE               CHAR(6) NOT NULL,
                ACCOUNT_NUMBER                 CHAR(8) NOT NULL,
                ACCOUNT_INTEREST_RATE          DECIMAL(4, 2),
                ACCOUNT_OPENED                 DATE )
           END-EXEC.
"""

ACCPGM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ACCPGM.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
           EXEC SQL INCLUDE ACCDB2 END-EXEC.
       PROCEDURE DIVISION.
           GOBACK.
"""

DEPTINC = """\
 EXEC SQL DECLARE DSN8C10.DEPT TABLE
           ( DEPTNO    CHAR(3) NOT NULL,
             DEPTNAME  VARCHAR(36) NOT NULL
           ) ;
"""


@pytest.fixture(scope="module")
def scanned_db2(tmp_path_factory):
    base = tmp_path_factory.mktemp("galaxy_ir_db2")
    repo = base / "db2repo"
    for rel, text in {"copy/ACCDB2.cpy": ACCDB2, "src/ACCPGM.cbl": ACCPGM, "pli/DEPTINC.pli": DEPTINC}.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return scan_to_db(repo, base / "scan")


def test_declared_tables_load_per_declaring_file(scanned_db2):
    ir = load_galaxy_ir(scanned_db2)
    (table,) = ir.files["copy/ACCDB2.cpy"].sql_tables
    assert (table.name, table.line) == ("ACCOUNT", 2)
    assert [(c.colno, c.name, c.sql_type, c.length, c.scale, c.nullable) for c in table.columns] == [
        (1, "ACCOUNT_SORTCODE", "CHAR", 6, None, False),
        (2, "ACCOUNT_NUMBER", "CHAR", 8, None, False),
        (3, "ACCOUNT_INTEREST_RATE", "DECIMAL", 4, 2, True),
        (4, "ACCOUNT_OPENED", "DATE", None, None, True),
    ]
    assert table.columns[0].attributes == "NOT NULL"
    # The including program declares nothing itself (same-file only).
    assert ir.files["src/ACCPGM.cbl"].sql_tables == []
    (dept,) = ir.files["pli/DEPTINC.pli"].sql_tables
    assert (dept.name, [c.name for c in dept.columns]) == ("DSN8C10.DEPT", ["DEPTNO", "DEPTNAME"])


def test_a_pre_3344_db_loads_with_no_sql_tables(scanned_db2, tmp_path):
    copy = tmp_path / "old.db"
    shutil.copy(scanned_db2, copy)
    with sqlite3.connect(copy) as conn:
        conn.execute("DROP TABLE sql_table_data")
    ir = load_galaxy_ir(copy)
    assert all(ef.sql_tables == [] for ef in ir.files.values())
    assert "copy/ACCDB2.cpy" in ir.files


# ==============================================================================
# #3356: CSD RESOURCE DEFINITIONS (csd_resource_data) AND THEIR JOINS
# ==============================================================================
# A CICS deck (carddemo/CBSA shapes) naming a VSAM file, two extrapartition queues
# (one by DSNAME, one by the region's DDNAME), an intrapartition queue, and the
# DB2TRAN -> DB2ENTRY -> PLAN chain for a transaction; plus the batch side: a
# COBOL program that reads the file's dataset under a job that spells the DSN
# through a SET symbol (#3345), so the join must go through dsn_resolved.
BANKCSD = """\
 DEFINE FILE(CUSTOMER) GROUP(BANK)
 DESCRIPTION(Bank Customer VSAM)
        DSNAME(CBSA.CICSBSA.CUSTOMER) RLSACCESS(NO)
        RECORDSIZE(259) KEYLENGTH(16) RECORDFORMAT(V)
 DEFINE FILE(NOJOB) GROUP(BANK)
        DSNAME(CBSA.CICSBSA.ELSEWHERE) RECORDFORMAT(F)
 DEFINE TDQUEUE(AUDT) GROUP(BANK)
        TYPE(EXTRA) DSNAME(CBSA.AUDIT.LOG) RECORDFORMAT(VARIABLE)
 DEFINE TDQUEUE(JOBS) GROUP(BANK)
        TYPE(EXTRA) DDNAME(INREADER) RECORDSIZE(80) RECORDFORMAT(FIXED)
 DEFINE TDQUEUE(CSSD) GROUP(BANK) TYPE(INTRA)
 DEFINE MAPSET(BNK1ACC) GROUP(BANK)
 DESCRIPTION('BANK Online Inquire Account for Customer')
 DEFINE TRANSACTION(OCAC) GROUP(BANK)
        PROGRAM(BNK1CAC) PROFILE(DFHCICST)
 DEFINE DB2ENTRY(HBANK) GROUP(BANK)
       ACCOUNTREC(NONE) AUTHTYPE(USERID) PLAN(CBSA)
 DEFINE DB2TRAN(OCAC) GROUP(BANK)
       ENTRY(HBANK) TRANSID(OCAC)
 DEFINE DB2TRAN(ORPH) GROUP(BANK)
       ENTRY(NOENTRY) TRANSID(ORPH)
"""

CUSTRPT = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CUSTRPT.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT CUST-FILE ASSIGN TO CUSTIN.
       DATA DIVISION.
       FILE SECTION.
       FD  CUST-FILE.
       01  CUST-REC PIC X(259).
       PROCEDURE DIVISION.
       000-MAIN.
           OPEN INPUT CUST-FILE.
           CLOSE CUST-FILE.
           STOP RUN.
"""

CUSTJOB = """\
//CUSTJOB  JOB (ACCT),'CUSTOMER REPORT'
//   SET HLQ=CBSA.CICSBSA
//STEP01   EXEC PGM=CUSTRPT
//CUSTIN   DD DSN=&HLQ..CUSTOMER,DISP=SHR
//AUDIT    DD DSN=CBSA.AUDIT.LOG,DISP=SHR
"""

BNK1CAC = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BNK1CAC.
       PROCEDURE DIVISION.
       000-MAIN.
           EXEC CICS RETURN END-EXEC.
"""


@pytest.fixture(scope="module")
def csd_scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("galaxy_ir_csd")
    repo = base / "bank"
    files = {
        "csd/BANK.csd": BANKCSD,
        "src/CUSTRPT.cbl": CUSTRPT,
        "src/BNK1CAC.cbl": BNK1CAC,
        "jcl/CUSTJOB.jcl": CUSTJOB,
    }
    for rel, text in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return scan_to_db(repo, base / "scan")


# ==============================================================================
# #3351-#3354: CICS RESOURCE OPERATIONS AND THEIR JOINS
# ==============================================================================
# A REAL scan, so the cobol dialect's `cics_resources` key is proven to reach
# cics_resource_data through the config pipeline. INQ sends/receives a BMS map,
# reads a CICS file, writes a TS queue and calls SVC with a channel; SVC reads
# the queue (its name through a VALUE), GETs INQ's container from its current
# channel and PUTs a reply that INQ GETs back.
INQ = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. INQ.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-CHAN   PIC X(16) VALUE SPACES.
       PROCEDURE DIVISION.
       000-MAIN.
           MOVE 'SVCCHAN' TO WS-CHAN.
           EXEC CICS RECEIVE MAP('CUSTA') MAPSET('CUSTM')
                INTO(CUSTAI) END-EXEC.
           EXEC CICS READ FILE('CUSTFILE') INTO(CUST-REC)
                RIDFLD(CUST-KEY) END-EXEC.
           EXEC CICS WRITEQ TS QUEUE('AUDITQ') FROM(CUST-REC) END-EXEC.
           EXEC CICS PUT CONTAINER('REQ') CHANNEL(WS-CHAN)
                FROM(CUST-KEY) END-EXEC.
           EXEC CICS LINK PROGRAM('SVC') CHANNEL(WS-CHAN) END-EXEC.
           EXEC CICS GET CONTAINER('RESP') CHANNEL(WS-CHAN)
                INTO(CUST-REC) END-EXEC.
           EXEC CICS SEND MAP('CUSTA') MAPSET('CUSTM') FROM(CUSTAO)
                ERASE END-EXEC.
           EXEC CICS SEND MAP('GONE') END-EXEC.
           EXEC CICS RETURN END-EXEC.
"""

SVC = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SVC.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-Q      PIC X(8) VALUE 'AUDITQ'.
       PROCEDURE DIVISION.
       000-MAIN.
           EXEC CICS GET CONTAINER('REQ') INTO(SVC-KEY) END-EXEC.
           EXEC CICS READQ TS QUEUE(WS-Q) INTO(SVC-REC) ITEM(1) END-EXEC.
           EXEC CICS PUT CONTAINER('RESP') FROM(SVC-REC) END-EXEC.
           EXEC CICS RETURN END-EXEC.
"""

CUSTM = "\n".join(
    [
        "CUSTM    DFHMSD TYPE=&SYSPARM,MODE=INOUT,LANG=COBOL",
        "CUSTA    DFHMDI SIZE=(24,80)",
        "CUSTNO   DFHMDF POS=(6,23),LENGTH=10,ATTRB=(NORM,NUM,FSET)",
        "CUSTNM   DFHMDF POS=(7,23),LENGTH=30",
        "         DFHMSD TYPE=FINAL",
        "         END",
        "",
    ]
)


@pytest.fixture(scope="module")
def scanned_cics(tmp_path_factory):
    base = tmp_path_factory.mktemp("galaxy_ir_cics")
    repo = base / "cicsres"
    for rel, text in {"src/INQ.cbl": INQ, "src/SVC.cbl": SVC, "bms/CUSTM.bms": CUSTM}.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return scan_to_db(repo, base / "scan")


def test_csd_resources_load_per_deck_of_every_type(csd_scanned):
    ir = load_galaxy_ir(csd_scanned)
    deck = ir.files["csd/BANK.csd"].csd_resources
    assert [(r.resource_type, r.name) for r in deck] == [
        ("FILE", "CUSTOMER"),
        ("FILE", "NOJOB"),
        ("TDQUEUE", "AUDT"),
        ("TDQUEUE", "JOBS"),
        ("TDQUEUE", "CSSD"),
        ("MAPSET", "BNK1ACC"),
        ("TRANSACTION", "OCAC"),
        ("DB2ENTRY", "HBANK"),
        ("DB2TRAN", "OCAC"),
        ("DB2TRAN", "ORPH"),
    ]
    cust = deck[0]
    assert (cust.dsname, cust.key_length, cust.record_size, cust.record_format) == (
        "CBSA.CICSBSA.CUSTOMER",
        16,
        259,
        "V",
    )
    assert ir.files["src/CUSTRPT.cbl"].csd_resources == []
    # transaction_data is untouched: still one transaction, no DB2TRAN leak.
    assert [t.transid for t in ir.files["csd/BANK.csd"].transactions] == ["OCAC"]
    assert [r["name"] for r in ir.csd_resources("db2tran")] == ["OCAC", "ORPH"]


def test_a_cics_file_joins_its_dataset_to_the_batch_lineage(csd_scanned):
    """CICS FILE -> DSNAME -> the JCL DD that binds it (through the #3345 resolved
    DSN, `&HLQ..CUSTOMER`) -> the batch program that opens that DD."""
    ir = load_galaxy_ir(csd_scanned)
    files = {e["file"]: e for e in ir.cics_file_datasets()}
    cust = files["CUSTOMER"]
    assert cust["dsname"] == "CBSA.CICSBSA.CUSTOMER"
    assert [(b["job"], b["dd_name"], b["dsn"], b["dsn_resolved"]) for b in cust["bindings"]] == [
        ("jcl/CUSTJOB.jcl", "CUSTIN", "&HLQ..CUSTOMER", "CBSA.CICSBSA.CUSTOMER")
    ]
    assert [(p["program"], p["modes"], p["job"]) for p in cust["batch_programs"]] == [
        ("src/CUSTRPT.cbl", ["INPUT"], "jcl/CUSTJOB.jcl")
    ]
    # A file no job in the repository binds is kept, with nothing joined.
    assert (files["NOJOB"]["bindings"], files["NOJOB"]["batch_programs"]) == ([], [])


def test_extrapartition_tdqueues_join_by_dsname_or_candidate_ddname(csd_scanned):
    ir = load_galaxy_ir(csd_scanned)
    queues = {q["queue"]: q for q in ir.tdqueue_datasets()}
    assert set(queues) == {"AUDT", "JOBS"}  # the INTRA queue is not a dataset
    assert queues["AUDT"]["via"] == "dsname"
    assert [(b["job"], b["dd_name"]) for b in queues["AUDT"]["bindings"]] == [("jcl/CUSTJOB.jcl", "AUDIT")]
    # DDNAME(INREADER) is bound in the CICS region's JCL, which is not here.
    assert (queues["JOBS"]["via"], queues["JOBS"]["ddname"], queues["JOBS"]["bindings"]) == ("ddname", "INREADER", [])


def test_a_transaction_reaches_its_db2_plan_through_db2tran_and_db2entry(csd_scanned):
    ir = load_galaxy_ir(csd_scanned)
    plans = {p["transid"]: p for p in ir.transaction_db2_plans()}
    assert (plans["OCAC"]["db2_entry"], plans["OCAC"]["plan"], plans["OCAC"]["programs"]) == (
        "HBANK",
        "CBSA",
        ["BNK1CAC"],
    )
    # A DB2TRAN naming an undefined DB2ENTRY keeps the edge with no plan.
    assert (plans["ORPH"]["plan"], plans["ORPH"]["programs"]) == (None, [])


def test_a_pre_3356_db_loads_with_no_csd_resources(csd_scanned, tmp_path):
    copy = tmp_path / "old.db"
    shutil.copy(csd_scanned, copy)
    with sqlite3.connect(copy) as conn:
        conn.execute("DROP TABLE csd_resource_data")
    ir = load_galaxy_ir(copy)
    assert all(ef.csd_resources == [] for ef in ir.files.values())
    assert ir.cics_file_datasets() == [] and ir.tdqueue_datasets() == [] and ir.transaction_db2_plans() == []
    # The transaction map is a separate table and still loads.
    assert [t["transid"] for t in ir.transaction_map()] == ["OCAC"]


def test_a_db2entry_may_assign_a_generic_transid_itself(tmp_path):
    """cics-genapp's shape: `DB2ENTRY(E) TRANSID(SS*) PLAN(P)` assigns every
    transaction matching SS* (CICS `*`, and `+` for one character) to P directly."""
    repo = tmp_path / "genapp"
    files = {
        "csd/GENA.csd": (
            " DEFINE DB2ENTRY(GENALU2) GROUP(GENA) TRANSID(SS*) PLAN(GENAONE)\n"
            " DEFINE DB2ENTRY(GENALU3) GROUP(GENA) TRANSID(S+ZZ) PLAN(GENATWO)\n"
            " DEFINE TRANSACTION(SSC1) GROUP(GENA) PROGRAM(LGTESTC1)\n"
            " DEFINE TRANSACTION(SSP1) GROUP(GENA) PROGRAM(LGTESTP1)\n"
            " DEFINE TRANSACTION(DSC1) GROUP(GENA) PROGRAM(LGTESTD1)\n"
        ),
    }
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    ir = load_galaxy_ir(scan_to_db(repo, tmp_path / "scan"))
    plans = {p["transid"]: p for p in ir.transaction_db2_plans()}
    assert (plans["SS*"]["via"], plans["SS*"]["db2tran"], plans["SS*"]["plan"]) == ("db2entry", None, "GENAONE")
    assert plans["SS*"]["programs"] == ["LGTESTC1", "LGTESTP1"]
    assert plans["S+ZZ"]["programs"] == []


def test_cics_operations_load_per_program(scanned_cics):
    ir = load_galaxy_ir(scanned_cics)
    inq = ir.files["src/INQ.cbl"]
    assert [(op.verb, op.kind, op.access, op.name) for op in inq.cics_resources] == [
        ("RECEIVE", "MAP", "read", "CUSTA"),
        ("READ", "FILE", "read", "CUSTFILE"),
        ("WRITEQ", "QUEUE", "write", "AUDITQ"),
        ("PUT", "CONTAINER", "write", "REQ"),
        ("LINK", "CHANNEL", "pass", "SVCCHAN"),
        ("GET", "CONTAINER", "read", "RESP"),
        ("SEND", "MAP", "write", "CUSTA"),
        ("SEND", "MAP", "write", "GONE"),
    ]
    put = inq.cics_resources[3]
    assert (put.qualifier_operand, put.qualifier, put.record_clause, put.record) == (
        "WS-CHAN",
        "SVCCHAN",
        "FROM",
        "CUST-KEY",
    )
    link = inq.cics_resources[4]
    assert (link.resolution, link.qualifier) == ("move", "SVC")
    readq = ir.files["src/SVC.cbl"].cics_resources[1]
    assert (readq.operand, readq.name, readq.resolution, readq.qualifier, readq.attributes) == (
        "WS-Q",
        "AUDITQ",
        "value",
        "TS",
        "ITEM(1)",
    )


def test_screen_bindings_join_each_map_to_its_bms_fields(scanned_cics):
    bindings = load_galaxy_ir(scanned_cics).screen_bindings()
    assert [(b["verb"], b["map"], b["mapset"], b["record"], b["bms_file"]) for b in bindings] == [
        ("RECEIVE", "CUSTA", "CUSTM", "CUSTAI", "bms/CUSTM.bms"),
        ("SEND", "CUSTA", "CUSTM", "CUSTAO", "bms/CUSTM.bms"),
        # No MAPSET: CICS defaults it to the map name, and no BMS source defines it.
        ("SEND", "GONE", "GONE", None, None),
    ]
    assert [(sf.name, sf.pos_line, sf.length) for sf in bindings[0]["fields"]] == [("CUSTNO", 6, 10), ("CUSTNM", 7, 30)]
    assert bindings[2]["fields"] == []


def test_queue_flows_link_the_writer_to_the_reader(scanned_cics):
    ir = load_galaxy_ir(scanned_cics)
    assert ir.queue_flows() == [
        {"queue": "AUDITQ", "queue_type": "TS", "producer": "src/INQ.cbl", "consumer": "src/SVC.cbl"}
    ]
    assert ir.cics_resource_users("FILE") == {"CUSTFILE": {"read": ["src/INQ.cbl"]}}


def test_container_flows_follow_the_channel_handoff_both_ways(scanned_cics):
    flows = load_galaxy_ir(scanned_cics).container_flows()
    assert flows == [
        # SVC GETs REQ from its current channel, which INQ handed it on LINK.
        {
            "container": "REQ",
            "channel": "SVCCHAN",
            "producer": "src/INQ.cbl",
            "consumer": "src/SVC.cbl",
            "match": "handoff",
        },
        # The return leg: SVC PUTs RESP into its current channel, INQ GETs it from SVCCHAN.
        {
            "container": "RESP",
            "channel": "SVCCHAN",
            "producer": "src/SVC.cbl",
            "consumer": "src/INQ.cbl",
            "match": "handoff",
        },
    ]


def test_a_pre_channel_db_loads_with_no_cics_resources(scanned_cics, tmp_path):
    copy = tmp_path / "old.db"
    shutil.copy(scanned_cics, copy)
    with sqlite3.connect(copy) as conn:
        conn.execute("DROP TABLE cics_resource_data")
    ir = load_galaxy_ir(copy)
    assert all(ef.cics_resources == [] for ef in ir.files.values())
    assert (ir.screen_bindings(), ir.queue_flows(), ir.container_flows()) == ([], [], [])


def _container(verb, access, name=None, candidates=None, channel=None, explicit=True):
    return EngineCicsResource(
        verb=verb,
        kind="CONTAINER",
        access=access,
        operand="X",
        name=name,
        resolution="literal" if name else "ambiguous",
        candidates=candidates,
        qualifier_operand="C" if explicit else None,
        qualifier=channel,
        record_clause=None,
        record=None,
        attributes=None,
        line=1,
    )


def test_container_flows_match_candidates_and_reject_a_different_channel(tmp_path):
    """CBSA's fan-out: CRECUST PUTs one of CIPA..CIPB (ambiguous MOVEs) into
    CIPCREDCHANN; each agency GETs its own. A reader on another channel never
    matches, and an unresolved channel is only `unverified`."""
    files = {
        "CRECUST.cbl": EngineFile(
            "CRECUST.cbl",
            "cobol",
            1,
            cics_resources=[_container("PUT", "write", candidates="CIPA,CIPB", channel="CIPCREDCHANN")],
        ),
        "AGY1.cbl": EngineFile(
            "AGY1.cbl", "cobol", 1, cics_resources=[_container("GET", "read", "CIPA", channel="CIPCREDCHANN")]
        ),
        "OTHER.cbl": EngineFile(
            "OTHER.cbl", "cobol", 1, cics_resources=[_container("GET", "read", "CIPB", channel="ELSE")]
        ),
        "UNK.cbl": EngineFile("UNK.cbl", "cobol", 1, cics_resources=[_container("GET", "read", "CIPB", channel=None)]),
    }
    flows = GalaxyIR(tmp_path / "x.db", "r", "c", files).container_flows()
    assert [(f["container"], f["producer"], f["consumer"], f["match"]) for f in flows] == [
        ("CIPA", "CRECUST.cbl", "AGY1.cbl", "channel"),
        ("CIPB", "CRECUST.cbl", "UNK.cbl", "unverified"),
    ]


def _file_op(verb, access, name, kind="FILE", qualifier=None):
    return EngineCicsResource(
        verb, kind, access, f"'{name}'", name, "literal", None, None, qualifier, None, None, None, 7
    )


def test_cics_file_lineage_joins_program_file_ops_to_the_csd_dataset(tmp_path, monkeypatch):
    """Program -> EXEC CICS FILE -> #3356's cics_file_datasets() row (DSNAME, JCL
    bindings, batch programs). The CSD side is stubbed: its own tests pin it. With
    no CSD definition a program's files are still listed, `definitions` empty."""
    files = {
        "INQ.cbl": EngineFile(
            "INQ.cbl",
            "cobol",
            1,
            cics_resources=[
                _file_op("READ", "read", "CUSTOMER"),
                _file_op("REWRITE", "update", "CUSTOMER"),
                _file_op("READ", "read", "NODEF"),
                _file_op("WRITEQ", "write", "LOGQ", kind="QUEUE", qualifier="TD"),
                _file_op("WRITEQ", "write", "TSQ", kind="QUEUE", qualifier="TS"),
            ],
        )
    }
    ir = GalaxyIR(tmp_path / "x.db", "r", "c", files)
    assert [(e["name"], e["definitions"]) for e in ir.cics_file_lineage()] == [("CUSTOMER", []), ("NODEF", [])]
    assert [(e["name"], e["definitions"]) for e in ir.tdqueue_lineage()] == [("LOGQ", [])]

    csd = {"file": "CUSTOMER", "dsname": "PROD.CUSTOMER", "bindings": [{"job": "LOAD.jcl"}], "batch_programs": []}
    monkeypatch.setattr(GalaxyIR, "cics_file_datasets", lambda self: [csd])
    monkeypatch.setattr(
        GalaxyIR, "tdqueue_datasets", lambda self: [{"queue": "LOGQ", "dsname": "PROD.LOG"}], raising=False
    )
    cust, nodef = ir.cics_file_lineage()
    assert (cust["program"], cust["accesses"], cust["verbs"], cust["definitions"]) == (
        "INQ.cbl",
        ["read", "update"],
        ["READ", "REWRITE"],
        [csd],
    )
    assert nodef["definitions"] == []
    # Only TD queues map to an extrapartition dataset; a TS queue is CICS storage.
    assert [(e["name"], e["definitions"][0]["dsname"]) for e in ir.tdqueue_lineage()] == [("LOGQ", "PROD.LOG")]


# ==============================================================================
# #3446: embedded SQL statements (sql_statement_data) and the table-access matrix
# ==============================================================================
SQLPGM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SQLPGM.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
           EXEC SQL DECLARE ACC-CURSOR CURSOR FOR
                SELECT A FROM ACCOUNT
           END-EXEC.
       PROCEDURE DIVISION.
           EXEC SQL OPEN ACC-CURSOR END-EXEC.
           EXEC SQL FETCH ACC-CURSOR INTO :WS-A END-EXEC.
           EXEC SQL UPDATE ACCOUNT SET A = :WS-A END-EXEC.
           EXEC SQL INSERT INTO PROCTRAN (A) VALUES (:WS-A) END-EXEC.
           GOBACK.
"""


@pytest.fixture(scope="module")
def scanned_sql(tmp_path_factory):
    base = tmp_path_factory.mktemp("galaxy_ir_sql")
    repo = base / "sqlrepo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "SQLPGM.cbl").write_text(SQLPGM, encoding="utf-8")
    return scan_to_db(repo, base / "scan")


def test_sql_statements_load_and_the_access_matrix_joins_cursors(scanned_sql):
    ir = load_galaxy_ir(scanned_sql)
    verbs = [(s.verb, s.table, s.access, s.cursor) for s in ir.files["src/SQLPGM.cbl"].sql_statements]
    assert verbs == [
        ("DECLARE CURSOR", "ACCOUNT", "read", "ACC-CURSOR"),
        ("OPEN", None, None, "ACC-CURSOR"),
        ("FETCH", None, None, "ACC-CURSOR"),
        ("UPDATE", "ACCOUNT", "update", None),
        ("INSERT", "PROCTRAN", "insert", None),
    ]
    matrix = {r["table"]: (r["accesses"], r["via_cursor"]) for r in ir.sql_table_access()}
    assert matrix == {"ACCOUNT": (["read", "update"], ["ACC-CURSOR"]), "PROCTRAN": (["insert"], [])}


def test_a_pre_3446_db_loads_with_no_sql_statements(scanned_sql, tmp_path):
    old = tmp_path / "old.db"
    shutil.copy(scanned_sql, old)
    with sqlite3.connect(old) as conn:
        conn.execute("DROP TABLE sql_statement_data")
    ir = load_galaxy_ir(old)
    assert all(ef.sql_statements == [] for ef in ir.files.values())
    assert ir.sql_table_access() == []


# ---- #3449: CICS task control and the async task graph ------------------------
ASYNC_CSD = """\
 DEFINE TRANSACTION(OCR1) GROUP(BANK)
        PROGRAM(CRDTAGY1)
 DEFINE TRANSACTION(OCR2) GROUP(BANK)
        PROGRAM(CRDTAGY2)
 DEFINE TRANSACTION(OCRA) GROUP(BANK)
        PROGRAM(BNKMENU)
 DEFINE TRANSACTION(OCUP) GROUP(BANK)
        PROGRAM(UPDWORK)
"""

PARENT = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PARENT.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-CC-CNT              PIC 9      VALUE 0.
       01 WS-CHANNEL-NAME        PIC X(16)  VALUE SPACES.
       01 WS-RUN-TRANSID         PIC X(4)   VALUE SPACES.
       01 WS-CONT                PIC X(16)  VALUE SPACES.
       01 WS-TKN                 PIC X(16).
       01 WS-FETCH-TKN           PIC X(16).
       PROCEDURE DIVISION.
       000-MAIN.
           MOVE 'CREDCHAN' TO WS-CHANNEL-NAME.
           MOVE 'CIPA' TO WS-CONT.
           PERFORM VARYING WS-CC-CNT FROM 1 BY 1 UNTIL WS-CC-CNT > 2
              STRING 'OCR' DELIMITED BY SIZE,
                      WS-CC-CNT DELIMITED BY SIZE
                 INTO WS-RUN-TRANSID
              END-STRING
              EXEC CICS PUT CONTAINER(WS-CONT)
                   FROM(WS-CC-CNT) CHANNEL(WS-CHANNEL-NAME)
              END-EXEC
              EXEC CICS RUN TRANSID(WS-RUN-TRANSID)
                   CHANNEL(WS-CHANNEL-NAME) CHILD(WS-TKN)
              END-EXEC
           END-PERFORM.
           EXEC CICS FETCH ANY(WS-FETCH-TKN) CHANNEL(WS-CHANNEL-NAME)
           END-EXEC.
           EXEC CICS START TRANSID('OCUP') FROM(WS-CONT)
           END-EXEC.
           EXEC CICS RETURN END-EXEC.
"""


def _child(pid: str, body: str = "           EXEC CICS RETURN END-EXEC.\n") -> str:
    return (
        "       IDENTIFICATION DIVISION.\n"
        f"       PROGRAM-ID. {pid}.\n"
        "       PROCEDURE DIVISION.\n"
        "       000-MAIN.\n" + body
    )


@pytest.fixture(scope="module")
def async_scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("galaxy_ir_async")
    repo = base / "bank"
    files = {
        "csd/BANK.csd": ASYNC_CSD,
        "src/PARENT.cbl": PARENT,
        "src/CRDTAGY1.cbl": _child("CRDTAGY1", "           EXEC CICS DELAY FOR SECONDS(1) END-EXEC.\n"),
        "src/CRDTAGY2.cbl": _child("CRDTAGY2"),
        "src/BNKMENU.cbl": _child("BNKMENU"),
        "src/UPDWORK.cbl": _child("UPDWORK", "           EXEC CICS RETRIEVE INTO(WS-REQ) END-EXEC.\n"),
    }
    for rel, text in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return scan_to_db(repo, base / "scan")


def test_task_rows_load_in_source_order(async_scanned):
    ir = load_galaxy_ir(async_scanned)
    rows = [(t.verb, t.name, t.resolution, t.candidates, t.token) for t in ir.files["src/PARENT.cbl"].cics_tasks]
    assert rows == [
        ("RUN", None, "pattern", "OCR[0-9]", "WS-TKN"),
        ("FETCH ANY", None, None, None, "WS-FETCH-TKN"),
        ("START", "OCUP", "literal", None, None),
    ]
    assert [(t.verb, t.timing) for t in ir.files["src/CRDTAGY1.cbl"].cics_tasks] == [("DELAY", "FOR SECONDS(1)")]


def test_async_tasks_joins_children_containers_fetches_and_retrieves(async_scanned):
    run, start = load_galaxy_ir(async_scanned).async_tasks()
    assert (run["parent"], run["verb"]) == ("src/PARENT.cbl", "RUN")
    # OCR[0-9] reaches OCR1 and OCR2 through the deck, never OCRA.
    assert [(c["transid"], c["program"], c["resolves_to"]) for c in run["children"]] == [
        ("OCR1", "CRDTAGY1", "src/CRDTAGY1.cbl"),
        ("OCR2", "CRDTAGY2", "src/CRDTAGY2.cbl"),
    ]
    assert (run["channel"], run["containers"]) == ("CREDCHAN", ["CIPA"])
    assert [(j["verb"], j["match"]) for j in run["joins"]] == [("FETCH ANY", "any")]
    assert run["retrieves"] == []
    assert [c["transid"] for c in start["children"]] == ["OCUP"]
    assert [(r["file"], r["record"]) for r in start["retrieves"]] == [("src/UPDWORK.cbl", "WS-REQ")]
    assert start["joins"] == []


def test_a_pre_3449_db_loads_with_no_tasks(async_scanned, tmp_path):
    old = tmp_path / "old.db"
    shutil.copy(async_scanned, old)
    with sqlite3.connect(old) as conn:
        conn.execute("DROP TABLE cics_task_data")
    ir = load_galaxy_ir(old)
    assert all(ef.cics_tasks == [] for ef in ir.files.values())
    assert ir.async_tasks() == []


# ---- #3448: job submission through the internal reader ------------------------
SUBMIT_CSD = """\
 DEFINE TDQUEUE(JOBS) GROUP(DEMO)
        TYPE(EXTRA) DDNAME(INREADER) RECORDSIZE(80)
 DEFINE TDQUEUE(AUDT) GROUP(DEMO)
        TYPE(EXTRA) DDNAME(AUDITLOG)
 DEFINE TDQUEUE(SUBQ) GROUP(DEMO)
        TYPE(EXTRA) DDNAME(SUBQDD)
 DEFINE TRANSACTION(CR00) GROUP(DEMO)
        PROGRAM(RPTPGM)
"""


def _writer(pid: str, queue: str, cards: str = "") -> str:
    return (
        "       IDENTIFICATION DIVISION.\n"
        f"       PROGRAM-ID. {pid}.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01 JCL-RECORD PIC X(80).\n" + cards + "       PROCEDURE DIVISION.\n"
        "       000-MAIN.\n"
        f"           EXEC CICS WRITEQ TD QUEUE('{queue}') FROM(JCL-RECORD)\n"
        "           END-EXEC.\n"
        "           EXEC CICS RETURN END-EXEC.\n"
    )


RPT_CARDS = (
    "       01 JOB-DATA.\n"
    "          05 FILLER PIC X(80) VALUE \"//RPTJOB01 JOB 'RPT',CLASS=A\".\n"
    '          05 FILLER PIC X(80) VALUE "//STEP10 EXEC PROC=RPTPROC".\n'
)


@pytest.fixture(scope="module")
def submit_scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("galaxy_ir_submit")
    repo = base / "demo"
    files = {
        "csd/DEMO.csd": SUBMIT_CSD,
        "cbl/RPTPGM.cbl": _writer("RPTPGM", "JOBS", RPT_CARDS),
        "cbl/AUDPGM.cbl": _writer("AUDPGM", "AUDT"),
        "cbl/SUBPGM.cbl": _writer("SUBPGM", "SUBQ"),
        "proc/RPTPROC.prc": "//RPTPROC PROC\n//S1 EXEC PGM=IEFBR14\n",
        "jcl/RPTPROC.jcl": "//RPTPROC JOB CLASS=A\n//S1 EXEC RPTPROC\n",
        "jcl/REGION.jcl": "//REGION JOB CLASS=A\n//CICS EXEC PGM=DFHSIP\n//SUBQDD DD SYSOUT=(A,INTRDR)\n",
        "jcl/SUBMIT1.jcl": (
            "//SUBMIT1 JOB CLASS=A\n//STEP01 EXEC PGM=IEBGENER\n"
            "//SYSUT1 DD DSN=MY.JCL(RPTPROC),DISP=SHR\n//SYSUT2 DD SYSOUT=(A,INTRDR)\n"
        ),
    }
    for rel, text in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return scan_to_db(repo, base / "scan")


def test_job_submissions_join_online_and_batch(submit_scanned):
    subs = {(s["submitter"], s["via"]): s for s in load_galaxy_ir(submit_scanned).job_submissions()}
    # AUDT is extrapartition too, but nothing says it reaches the internal reader.
    assert sorted(subs) == [
        ("cbl/RPTPGM.cbl", "tdq"),
        ("cbl/SUBPGM.cbl", "tdq"),
        ("jcl/REGION.jcl", "intrdr_dd"),
        ("jcl/SUBMIT1.jcl", "intrdr_dd"),
    ]
    rpt = subs[("cbl/RPTPGM.cbl", "tdq")]
    assert (rpt["queue"], rpt["ddname"], rpt["transactions"], rpt["jobs"]) == (
        "JOBS",
        "INREADER",
        ["CR00"],
        ["RPTJOB01"],
    )
    assert rpt["evidence"] == ["job_card"]
    # PROC=RPTPROC prefers the procedure member over the same-named job.
    (run,) = rpt["runs"]
    assert (run["kind"], run["name"], run["resolves_to"]) == ("PROC", "RPTPROC", "proc/RPTPROC.prc")
    sub = subs[("cbl/SUBPGM.cbl", "tdq")]
    assert (sub["evidence"], sub["jobs"]) == (["region_jcl"], [])
    batch = subs[("jcl/SUBMIT1.jcl", "intrdr_dd")]
    assert (batch["step"], batch["dd"], batch["jobs"]) == ("STEP01", "SYSUT2", ["RPTPROC"])
    assert batch["runs"][0]["resolves_to"] == "jcl/RPTPROC.jcl"
    assert subs[("jcl/REGION.jcl", "intrdr_dd")]["jobs"] == []


def test_a_pre_3448_db_loads_with_no_submissions(submit_scanned, tmp_path):
    old = tmp_path / "old.db"
    shutil.copy(submit_scanned, old)
    with sqlite3.connect(old) as conn:
        conn.execute("DROP TABLE job_submit_data")
    ir = load_galaxy_ir(old)
    assert all(ef.job_submits == [] for ef in ir.files.values())
    assert ir.job_submissions() == []


# ---- #3447: IBM MQ calls, endpoints and flows ---------------------------------
def _mq_program(pid: str, body: str) -> str:
    return (
        "       IDENTIFICATION DIVISION.\n"
        f"       PROGRAM-ID. {pid}.\n"
        "       PROCEDURE DIVISION.\n"
        "       000-MAIN.\n" + body + "           GOBACK.\n"
    )


MQ_PRODUCER = _mq_program(
    "MQPROD",
    "           MOVE 'APP.ORDERS' TO MQOD-OBJECTNAME\n"
    "           COMPUTE MQ-OPTIONS = MQOO-OUTPUT\n"
    "           CALL 'MQOPEN' USING HCONN MQ-OD MQ-OPTIONS HOBJ CC RC\n"
    "           CALL 'MQPUT' USING HCONN HOBJ MD PMO LEN BUF CC RC\n",
)
MQ_CONSUMER = _mq_program(
    "MQCONS",
    "           MOVE 'APP.ORDERS' TO MQOD-OBJECTNAME\n"
    "           COMPUTE MQ-OPTIONS = MQOO-INPUT-SHARED\n"
    "           CALL 'MQOPEN' USING HCONN MQ-OD MQ-OPTIONS HOBJ CC RC\n"
    "           CALL 'MQGET' USING HCONN HOBJ MD GMO LEN BUF DLEN CC RC\n"
    "           MOVE MQMD-REPLYTOQ TO WS-REPLY\n"
    "           MOVE WS-REPLY TO MQOD-OBJECTNAME\n"
    "           CALL 'MQPUT1' USING HCONN MQ-OD MD PMO LEN BUF CC RC\n",
)


@pytest.fixture(scope="module")
def mq_scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("galaxy_ir_mq")
    repo = base / "mq"
    (repo / "cbl").mkdir(parents=True)
    (repo / "cbl" / "MQPROD.cbl").write_text(MQ_PRODUCER, encoding="utf-8")
    (repo / "cbl" / "MQCONS.cbl").write_text(MQ_CONSUMER, encoding="utf-8")
    return scan_to_db(repo, base / "scan")


def test_mq_calls_load_and_queues_pair_producers_with_consumers(mq_scanned):
    ir = load_galaxy_ir(mq_scanned)
    cons = [(q.verb, q.queue, q.resolution, q.open_line) for q in ir.files["cbl/MQCONS.cbl"].mq_calls]
    assert cons == [
        ("MQOPEN", "APP.ORDERS", "literal", None),
        ("MQGET", "APP.ORDERS", "literal", 7),
        ("MQPUT1", None, "reply_to", None),
    ]
    ends = {(e["file"], e["queue"], e["direction"]) for e in ir.mq_queues()}
    assert ends == {
        ("cbl/MQPROD.cbl", "APP.ORDERS", "put"),
        ("cbl/MQCONS.cbl", "APP.ORDERS", "get"),
        ("cbl/MQCONS.cbl", "<reply_to>", "put"),
    }
    assert ir.mq_flows() == [
        {"queue": "APP.ORDERS", "producer": "cbl/MQPROD.cbl", "consumer": "cbl/MQCONS.cbl", "mode": "get"}
    ]


def test_a_pre_3447_db_loads_with_no_mq_calls(mq_scanned, tmp_path):
    old = tmp_path / "old.db"
    shutil.copy(mq_scanned, old)
    with sqlite3.connect(old) as conn:
        conn.execute("DROP TABLE mq_call_data")
    ir = load_galaxy_ir(old)
    assert all(ef.mq_calls == [] for ef in ir.files.values())
    assert ir.mq_queues() == [] and ir.mq_flows() == []


# ---- #3453: units of work, error handlers, RESP checks, TD trigger starts -----
UOW_CSD = """\
 DEFINE TDQUEUE(PRTQ) GROUP(DEMO)
        TYPE(INTRA) TRIGGERLEVEL(5) TRANSID(PRT1)
 DEFINE TDQUEUE(LOGQ) GROUP(DEMO)
        TYPE(INTRA)
 DEFINE TRANSACTION(PRT1) GROUP(DEMO)
        PROGRAM(PRTPGM)
"""

UOWPGM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. UOWPGM.
       PROCEDURE DIVISION.
       A000-MAIN.
           EXEC CICS HANDLE ABEND LABEL(Z999-ABEND) END-EXEC.
           EXEC CICS HANDLE CONDITION NOTFND(MISSING-PARA) END-EXEC.
           EXEC CICS READ FILE('F') INTO(R) RESP(WS-RESP) END-EXEC.
           IF WS-RESP NOT = DFHRESP(NORMAL)
              EXEC CICS SYNCPOINT ROLLBACK END-EXEC
           END-IF.
           EXEC CICS WRITEQ TD QUEUE('PRTQ') FROM(R) RESP(WS-RESP)
           END-EXEC.
           EXEC CICS WRITEQ TD QUEUE('LOGQ') FROM(R) END-EXEC.
           EXEC CICS SYNCPOINT END-EXEC.
           EXEC CICS RETURN END-EXEC.
       Z999-ABEND.
           EXEC CICS ABEND ABCODE('UOW1') END-EXEC.
"""


@pytest.fixture(scope="module")
def uow_scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("galaxy_ir_uow")
    repo = base / "demo"
    files = {
        "csd/DEMO.csd": UOW_CSD,
        "cbl/UOWPGM.cbl": UOWPGM,
        "cbl/PRTPGM.cbl": _writer("PRTPGM", "OTHQ"),
    }
    for rel, text in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return scan_to_db(repo, base / "scan")


def test_units_of_work_and_handlers_are_placed_in_their_paragraph(uow_scanned):
    ir = load_galaxy_ir(uow_scanned)
    assert [(u["kind"], u["verb"], u["unit"]) for u in ir.units_of_work() if u["file"] == "cbl/UOWPGM.cbl"] == [
        ("ROLLBACK", "SYNCPOINT ROLLBACK", "A000-MAIN"),
        ("COMMIT", "SYNCPOINT", "A000-MAIN"),
    ]
    handlers = [(h["kind"], h["condition"], h["target"], h["handler_found"]) for h in ir.error_handlers()]
    # MISSING-PARA is not a paragraph of the program: a real finding.
    assert handlers == [
        ("HANDLE_ABEND", None, "Z999-ABEND", True),
        ("HANDLE_CONDITION", "NOTFND", "MISSING-PARA", False),
    ]
    # READ is tested; WRITEQ PRTQ reuses WS-RESP but nothing tests it.
    assert [(u["verb"], u["line"]) for u in ir.unchecked_responses()] == [("WRITEQ", 11)]


def test_a_triggered_td_queue_starts_its_transaction(uow_scanned):
    (start,) = load_galaxy_ir(uow_scanned).tdq_trigger_starts()
    assert (start["writer"], start["queue"], start["trigger_level"], start["transid"]) == (
        "cbl/UOWPGM.cbl",
        "PRTQ",
        5,
        "PRT1",
    )
    assert (start["program"], start["resolves_to"]) == ("PRTPGM", "cbl/PRTPGM.cbl")


def test_a_pre_3453_db_loads_with_no_uow_rows(uow_scanned, tmp_path):
    old = tmp_path / "old.db"
    shutil.copy(uow_scanned, old)
    with sqlite3.connect(old) as conn:
        conn.execute("DROP TABLE uow_handler_data")
    ir = load_galaxy_ir(old)
    assert all(ef.uow_handlers == [] for ef in ir.files.values())
    assert ir.units_of_work() == [] and ir.error_handlers() == [] and ir.unchecked_responses() == []
