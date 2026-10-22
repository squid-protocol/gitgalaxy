"""#3617: VSAM files -> Spring Data repositories.

A real galaxyscope scan of a small estate backs the tests. IDCAMS reads SYSIN columns 1-72 only
(73-80 are sequence numbers), so the DEFINEs continue with `-`. One IDCAMS job DEFINEs:
- ACCT: a KSDS keyed on its first 8 bytes, with a non-unique AIX (and PATH) on bytes 8-12.
- TCAT: a KSDS whose 6-byte key is a group of two fields.
The CSD maps CICS files ACCTF (the cluster) and ACCTX (the path).

Three programs use the files:
- ACCTCICS (CICS) READs, WRITEs, DELETEs and browses ACCTF, and READs through ACCTX.
- ACCTBAT (batch) reads ACCT sequentially: an INDEXED SELECT, a JCL DD, OPEN INPUT.
- TCATBAT (batch) updates TCAT: OPEN I-O.

Compiling the generated Java is the compile matrix's job (java_target_matrix.py --scan).
"""

import json
import shutil
from unittest.mock import patch

import pytest

import gitgalaxy.cobol_refractor_controller as refractor
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir
from scan_server import scan_to_db

ACCTREC = """\
       01  ACCT-REC.
           05 ACCT-ID          PIC 9(8).
           05 ACCT-BRANCH      PIC X(5).
           05 ACCT-NAME        PIC X(20).
           05 ACCT-BAL         PIC S9(7)V99 COMP-3.
"""

ACCTCICS = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ACCTCICS.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
           COPY ACCTREC.
       PROCEDURE DIVISION.
       000-MAIN.
           EXEC CICS READ FILE('ACCTF') INTO(ACCT-REC) RIDFLD(ACCT-ID) END-EXEC.
           EXEC CICS WRITE FILE('ACCTF') FROM(ACCT-REC) RIDFLD(ACCT-ID) END-EXEC.
           EXEC CICS DELETE FILE('ACCTF') RIDFLD(ACCT-ID) END-EXEC.
           EXEC CICS STARTBR FILE('ACCTF') RIDFLD(ACCT-ID) END-EXEC.
           EXEC CICS READNEXT FILE('ACCTF') INTO(ACCT-REC) RIDFLD(ACCT-ID) END-EXEC.
           EXEC CICS READPREV FILE('ACCTF') INTO(ACCT-REC) RIDFLD(ACCT-ID) END-EXEC.
           EXEC CICS ENDBR FILE('ACCTF') END-EXEC.
           EXEC CICS READ FILE('ACCTX') INTO(ACCT-REC) RIDFLD(ACCT-BRANCH) END-EXEC.
           EXEC CICS RETURN END-EXEC.
"""

ACCTBAT = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ACCTBAT.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT ACCT-FILE ASSIGN TO ACCTDD
               ORGANIZATION IS INDEXED
               ACCESS MODE IS SEQUENTIAL
               RECORD KEY IS FD-ACCT-ID.
       DATA DIVISION.
       FILE SECTION.
       FD  ACCT-FILE.
       01  FD-ACCT-REC.
           05 FD-ACCT-ID       PIC 9(8).
           05 FD-ACCT-REST     PIC X(30).
       PROCEDURE DIVISION.
       000-MAIN.
           OPEN INPUT ACCT-FILE.
           READ ACCT-FILE.
           CLOSE ACCT-FILE.
           STOP RUN.
"""

TCATBAT = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TCATBAT.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT TCAT-FILE ASSIGN TO TCATDD
               ORGANIZATION IS INDEXED
               ACCESS MODE IS RANDOM
               RECORD KEY IS FD-TCAT-KEY.
       DATA DIVISION.
       FILE SECTION.
       FD  TCAT-FILE.
       01  FD-TCAT-REC.
           05 FD-TCAT-KEY.
              10 FD-TCAT-TYPE  PIC X(2).
              10 FD-TCAT-CD    PIC 9(4).
           05 FD-TCAT-DESC     PIC X(44).
       PROCEDURE DIVISION.
       000-MAIN.
           OPEN I-O TCAT-FILE.
           READ TCAT-FILE.
           REWRITE FD-TCAT-REC.
           CLOSE TCAT-FILE.
           STOP RUN.
"""

JOB = """\
//VSAMJOB  JOB CLASS=A
//DEFINE   EXEC PGM=IDCAMS
//SYSIN    DD *
   DEFINE CLUSTER (NAME(APP.ACCT.KSDS) INDEXED -
          KEYS(8 0) RECORDSIZE(38 38))
   DEFINE AIX (NAME(APP.ACCT.AIX) RELATE(APP.ACCT.KSDS) -
          KEYS(5 8) NONUNIQUEKEY)
   DEFINE PATH (NAME(APP.ACCT.PATH) PATHENTRY(APP.ACCT.AIX))
   DEFINE CLUSTER (NAME(APP.TCAT.KSDS) INDEXED -
          KEYS(6 0) RECORDSIZE(50 50))
/*
//STEP1    EXEC PGM=ACCTBAT
//ACCTDD   DD DSN=APP.ACCT.KSDS,DISP=SHR
//STEP2    EXEC PGM=TCATBAT
//TCATDD   DD DSN=APP.TCAT.KSDS,DISP=OLD
"""

CSD = """\
 DEFINE TRANSACTION(ACCT) GROUP(APP)
        PROGRAM(ACCTCICS)
 DEFINE FILE(ACCTF) GROUP(APP)
        DSNAME(APP.ACCT.KSDS)
 DEFINE FILE(ACCTX) GROUP(APP)
        DSNAME(APP.ACCT.PATH)
"""


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("vsam_repos")
    repo = base / "estate"
    files = {
        "cbl/ACCTCICS.cbl": ACCTCICS,
        "cbl/ACCTBAT.cbl": ACCTBAT,
        "cbl/TCATBAT.cbl": TCATBAT,
        "cpy/ACCTREC.cpy": ACCTREC,
        "jcl/VSAMJOB.jcl": JOB,
        "csd/APP.csd": CSD,
    }
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    return repo, scan_to_db(repo, base / "scan")


def test_a_store_joins_idcams_csd_cics_and_batch(scanned):
    _, db = scanned
    stores = {s["dataset"]: s for s in load_galaxy_ir(db).vsam_stores()}
    acct = stores["APP.ACCT.KSDS"]
    assert (acct["organization"], acct["key_offset"], acct["key_length"], acct["record_max"]) == ("INDEXED", 0, 8, 38)
    assert [
        (a["aix"], a["paths"], a["key_offset"], a["key_length"], a["unique"]) for a in acct["alternate_indexes"]
    ] == [("APP.ACCT.AIX", ["APP.ACCT.PATH"], 8, 5, False)]
    assert sorted((c["file"], c["via"]) for c in acct["cics_files"]) == [("ACCTF", None), ("ACCTX", "APP.ACCT.PATH")]
    users = {(u["kind"], u["name"]): u for u in acct["users"]}
    cics = users[("cics", "ACCTF")]
    assert cics["verbs"] == ["DELETE", "ENDBR", "READ", "READNEXT", "READPREV", "STARTBR", "WRITE"]
    assert cics["ridflds"] == [{"ridfld": "ACCT-ID", "offset": 0, "length": 8}]
    assert users[("cics", "ACCTX")]["via"] == "APP.ACCT.PATH"
    batch = users[("batch", "ACCT-FILE")]
    assert (batch["dd"], batch["access_mode"], batch["modes"], batch["key_offset"]) == (
        "ACCTDD",
        "SEQUENTIAL",
        ["INPUT"],
        0,
    )
    tcat = stores["APP.TCAT.KSDS"]
    (user,) = tcat["users"]
    assert (user["name"], user["modes"], user["records"][0]["record"]) == ("TCAT-FILE", ["I-O"], "FD-TCAT-REC")


def test_a_group_ridfld_is_placed_in_its_record(scanned):
    _, db = scanned
    ir = load_galaxy_ir(db)
    ef = ir.files["cbl/TCATBAT.cbl"]
    layout = ir.record_layout(ef, ef.records[0])
    assert ir._position_in(ef, "FD-TCAT-KEY", layout) == (0, 6)  # a group: its fields' run
    assert ir._position_in(ef, "FD-TCAT-DESC", layout) == (6, 44)
    assert ir._position_in(ef, "NO-SUCH-ITEM", layout) == (None, None)


def _java(scanned, tmp_path, config=None):
    from gitgalaxy import cobol_to_java_controller

    repo, db = scanned
    work = tmp_path / "estate"
    shutil.copytree(repo, work)
    with patch("sys.argv", ["refract", str(work), "--galaxy-db", str(db)]):
        refractor.main()
    (clean,) = tmp_path.glob("estate_gitgalaxy_clean_*")
    argv = ["cobol-to-java", str(clean), "--header", str(tmp_path / "none.txt")]
    if config:
        cfg = tmp_path / "t.json"
        cfg.write_text(json.dumps(config), encoding="utf-8")
        argv += ["--config", str(cfg)]
    with patch("sys.argv", argv):
        cobol_to_java_controller.main()
    (java,) = tmp_path.glob("estate_gitgalaxy_java_spring_*")
    return java, java / "src/main/java/com/gitgalaxy/modernized"


def test_each_store_becomes_an_entity_and_a_repository(scanned, tmp_path):
    java, src = _java(scanned, tmp_path)
    entity = (src / "entity/vsam/AcctRec.java").read_text(encoding="utf-8")
    assert '@Entity(name = "VsamAcctRec")' in entity and '@Table(name = "vsam_acct")' in entity
    assert "Key: ACCT-ID (offset 0, 8 bytes, from IDCAMS KEYS)" in entity
    assert '    @Id\n    @Column(name = "ACCT_ID")\n    private Integer acctId;' in entity
    assert "CICS files: ACCTF, ACCTX (path APP.ACCT.PATH)" in entity
    repo = (src / "repository/vsam/AcctRecRepository.java").read_text(encoding="utf-8")
    assert "extends JpaRepository<AcctRec, Integer>" in repo
    assert "findByAcctIdGreaterThanEqualOrderByAcctIdAsc(Integer acctId, Pageable page);" in repo  # STARTBR/READNEXT
    assert "findByAcctIdLessThanEqualOrderByAcctIdDesc(Integer acctId, Pageable page);" in repo  # READPREV
    assert "List<AcctRec> findByAcctBranch(String acctBranch);" in repo  # the non-unique AIX

    # a group key: an @EmbeddedId of the fields it spans
    tcat = (src / "entity/vsam/FdTcatRec.java").read_text(encoding="utf-8")
    assert "@EmbeddedId\n    private FdTcatRecKey id;" in tcat and "fdTcatType" not in tcat
    key = (src / "entity/vsam/FdTcatRecKey.java").read_text(encoding="utf-8")
    assert "@Embeddable" in key and "private String fdTcatType;" in key and "private Integer fdTcatCd;" in key

    # each program's service: exactly the verbs it uses (CICS) or its OPEN modes (batch)
    cics = (src / "service/AcctcicsService.java").read_text(encoding="utf-8")
    for method in ("readAcctf(Integer key)", "writeAcctf(AcctRec record)", "deleteAcctf(Integer key)",
                   "browseAcctf(Integer from, int count)", "browseBackAcctf(Integer from, int count)",
                   "List<AcctRec> readAcctx(String acctBranch)"):  # fmt: skip
        assert method in cics, method
    assert "rewriteAcctf" not in cics  # never REWRITEs
    bat = (src / "service/AcctbatService.java").read_text(encoding="utf-8")
    assert "public List<AcctRec> readAllAcctFile() {" in bat and "writeAcctFile" not in bat  # OPEN INPUT, sequential
    assert "TODO: this program uses FD-ACCT-REC (38 bytes); the entity follows ACCT-REC (38 bytes)" in bat
    tcat_svc = (src / "service/TcatbatService.java").read_text(encoding="utf-8")
    assert "readTcatFile(FdTcatRecKey key)" in tcat_svc and "rewriteTcatFile(FdTcatRec record)" in tcat_svc  # I-O

    audit = (java / "java_migration_audit.txt").read_text(encoding="utf-8")
    assert "VSAM stores (#3617)      : 2 entities + repositories (1 keyed by one field); 0 not generated" in audit


def test_plain_classes_give_the_key_class_value_equality(scanned, tmp_path):
    _, src = _java(scanned, tmp_path, {"java": {"data_classes": "plain"}})
    key = (src / "entity/vsam/FdTcatRecKey.java").read_text(encoding="utf-8")
    assert "public boolean equals(Object o)" in key and "Objects.hash(fdTcatType, fdTcatCd)" in key
    assert "lombok" not in (src / "entity/vsam/AcctRec.java").read_text(encoding="utf-8")


def test_one_class_name_registry_spans_the_forges(scanned):
    """#3657: a name one forge generated is never reused by another. A service importing
    dto.contract.AcctRec and entity.vsam.AcctRec would not compile."""
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_common import ClassNames
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_repository_forge import RepositoryForge

    _, db = scanned
    ir = load_galaxy_ir(db)
    estate = {"sections": {"vsam_stores": {"facts": ir.vsam_stores()}}}
    skeletons = {ef.file_path.split("/")[-1][:-4]: {"program": {"file": ef.file_path}} for ef in ir.programs()}
    alone = RepositoryForge(estate, skeletons, "com.acme")
    assert "AcctRec" in [st.entity for st in alone.stores]
    names = ClassNames()
    names.claim("AcctRec")  # e.g. a COMMAREA DTO the transaction forge generated first
    shared = RepositoryForge(estate, skeletons, "com.acme", names=names)
    entities = [st.entity for st in shared.stores]
    assert "AcctRec" not in entities and "AcctAcctRec" in entities
    assert {"AcctAcctRecRepository", "FdTcatRecKey"} <= names.taken


def test_symbolic_pattern():
    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import _symbolic_pattern

    pat = _symbolic_pattern("@BANK_PREFIX@.CUSTOMER")
    assert pat.match("CBSA.CICSBSA.CUSTOMER")
    assert pat.match("X.CUSTOMER")
    assert not pat.match("CBSA.CUSTOMER.OLD")

    pat2 = _symbolic_pattern("<USRHLQ>.GENAPP.KSDSCUST")
    assert pat2.match("PROD.GENAPP.KSDSCUST")

    pat3 = _symbolic_pattern("APP.ZC@ID@FILE")
    assert pat3.match("APP.ZCABCFILE")
    assert not pat3.match("APP.ZC.X.FILE")

    pat4 = _symbolic_pattern("&HLQ..DATA")
    assert pat4.match("PROD.DATA")
    assert pat4.match("PROD.SUB.DATA")

    assert _symbolic_pattern("PROD.DATA") is None

    pat5 = _symbolic_pattern("@PFX@.SYS1.A+B")
    assert pat5.match("PROD.SYS1.A+B")
    assert not pat5.match("PROD.SYS1.A-B")


def test_symbolic_merge(tmp_path):
    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir
    from scan_server import scan_to_db

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "jcl").mkdir()
    (repo / "cbl").mkdir()
    (repo / "csd").mkdir()

    (repo / "jcl" / "DEF.jcl").write_text("""//DEF JOB
//STEP1 EXEC PGM=IDCAMS
//SYSPRINT DD SYSOUT=*
//SYSIN DD *
  DEFINE CLUSTER(NAME(@PFX@.ACCT.KSDS) -
         KEYS(8 0) RECORDSIZE(38 38) INDEXED)
/*
""")
    (repo / "csd" / "APP.csd").write_text("""
  DEFINE FILE(ACCTF) GROUP(APP)
         DSNAME(PROD.APP.ACCT.KSDS)
""")
    (repo / "cbl" / "PROG.cbl").write_text("""       ID DIVISION.
       PROGRAM-ID. PROG.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 ACCT-REC.
          05 ACCT-ID PIC X(8).
          05 FILLER PIC X(30).
       PROCEDURE DIVISION.
           EXEC CICS READ FILE('ACCTF') INTO(ACCT-REC)
                     RIDFLD(ACCT-ID) END-EXEC.
""")

    db = scan_to_db(repo, tmp_path / "scan")
    ir = load_galaxy_ir(db)
    stores = ir.vsam_stores()

    assert len(stores) == 1
    acct = stores[0]
    assert acct["dataset"] == "PROD.APP.ACCT.KSDS"
    assert acct["organization"] == "INDEXED"
    assert acct["key_offset"] == 0
    assert acct["key_length"] == 8
    assert acct["defined_by"]["match"] == "symbolic"


def test_symbolic_conflict_rejected(tmp_path):
    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir
    from scan_server import scan_to_db

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "jcl").mkdir()
    (repo / "cbl").mkdir()
    (repo / "csd").mkdir()

    (repo / "jcl" / "DEF.jcl").write_text("""//DEF JOB
//STEP1 EXEC PGM=IDCAMS
//SYSPRINT DD SYSOUT=*
//SYSIN DD *
  DEFINE CLUSTER(NAME(@PFX@.ACCT.KSDS) -
         KEYS(4 12) RECORDSIZE(38 38) INDEXED)
/*
""")
    (repo / "csd" / "APP.csd").write_text("""
  DEFINE FILE(ACCTF) GROUP(APP)
         DSNAME(PROD.APP.ACCT.KSDS)
""")
    (repo / "cbl" / "PROG.cbl").write_text("""       ID DIVISION.
       PROGRAM-ID. PROG.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 ACCT-REC.
          05 ACCT-ID PIC X(8).
          05 FILLER PIC X(30).
       PROCEDURE DIVISION.
           EXEC CICS READ FILE('ACCTF') INTO(ACCT-REC)
                     RIDFLD(ACCT-ID) END-EXEC.
""")

    db = scan_to_db(repo, tmp_path / "scan")
    ir = load_galaxy_ir(db)
    stores = ir.vsam_stores()

    assert len(stores) == 2
    sym_store = next(s for s in stores if s["dataset"] == "@PFX@.ACCT.KSDS")
    concrete = next(s for s in stores if s["dataset"] == "PROD.APP.ACCT.KSDS")

    assert sym_store["defined"]
    assert concrete["symbolic_candidate_rejected"]
    assert "disagrees with KEYS(4 12)" in concrete["symbolic_candidate_rejected"]["why"]


def _symbolic_estate(tmp_path, keys: str, recsize: str, ridfld: bool):
    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir
    from scan_server import scan_to_db

    repo = tmp_path / "repo"
    for d in ("jcl", "cbl", "csd"):
        (repo / d).mkdir(parents=True)
    (repo / "jcl" / "DEF.jcl").write_text(
        "//DEF JOB\n//STEP1 EXEC PGM=IDCAMS\n//SYSIN DD *\n"
        f"  DEFINE CLUSTER(NAME(@PFX@.ACCT.KSDS) -\n         KEYS({keys}) RECORDSIZE({recsize}) INDEXED)\n/*\n"
    )
    (repo / "csd" / "APP.csd").write_text("  DEFINE FILE(ACCTF) GROUP(APP)\n         DSNAME(PROD.APP.ACCT.KSDS)\n")
    read = "RIDFLD(ACCT-ID) " if ridfld else ""
    (repo / "cbl" / "PROG.cbl").write_text(
        "       ID DIVISION.\n       PROGRAM-ID. PROG.\n       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n"
        "       01 ACCT-REC.\n          05 ACCT-ID PIC X(8).\n          05 FILLER PIC X(30).\n"
        "       PROCEDURE DIVISION.\n"
        f"           EXEC CICS READ FILE('ACCTF') INTO(ACCT-REC)\n                     {read}END-EXEC.\n"
    )
    return load_galaxy_ir(scan_to_db(repo, tmp_path / "scan")).vsam_stores()


def test_a_record_shorter_than_recordsize_max_still_merges(tmp_path):
    """VSAM allows a record shorter than the maximum (CBSA ABNDFILE: 678 of 681)."""
    (store,) = _symbolic_estate(tmp_path, "8 0", "38 40", ridfld=True)
    assert store["defined_by"]["match"] == "symbolic"
    assert "program records of [38] bytes fit RECORDSIZE max 40" in store["defined_by"]["evidence"]


def test_a_record_longer_than_recordsize_max_is_refused(tmp_path):
    stores = _symbolic_estate(tmp_path, "8 0", "30 30", ridfld=True)
    (concrete,) = [s for s in stores if s["dataset"] == "PROD.APP.ACCT.KSDS"]
    assert "exceeds RECORDSIZE max 30" in concrete["symbolic_candidate_rejected"]["why"]


def test_the_name_pattern_alone_does_not_merge(tmp_path):
    stores = _symbolic_estate(tmp_path, "8 0", "38 40", ridfld=False)  # no key, no exact size
    (concrete,) = [s for s in stores if s["dataset"] == "PROD.APP.ACCT.KSDS"]
    assert concrete["symbolic_candidate_rejected"]["why"] == "no key or exact record size corroborates the name pattern"


def test_a_write_from_a_field_with_a_length_is_the_window_it_writes(tmp_path):
    """GenApp LGACVS01: `WRITE FILE('KSDSCUST') FROM(CA-CUSTOMER-NUM) LENGTH(CUSTOMER-RECORD-SIZE)` writes the
    225 bytes AT the 10-byte field; the window's end falls inside CA-REQUEST-SPECIFIC, which the first
    REDEFINES ending exactly there (CA-CUSTOMER-REQUEST) lays out. KEYS / RECORDSIZE sit on DATA(...)."""
    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir
    from scan_server import scan_to_db

    repo = tmp_path / "repo"
    for d in ("jcl", "cbl", "csd"):
        (repo / d).mkdir(parents=True)
    (repo / "jcl" / "DEF.jcl").write_text(
        "//DEF JOB\n//STEP1 EXEC PGM=IDCAMS\n//SYSIN DD *\n"
        " DEFINE CLUSTER(NAME(APP.CUST) INDEXED) -\n"
        "        DATA(NAME(APP.CUST.DATA) KEYS(10 0) RECORDSIZE(40 40)) -\n"
        "        INDEX(NAME(APP.CUST.INDEX))\n/*\n"
    )
    (repo / "csd" / "APP.csd").write_text("  DEFINE FILE(CUSTF) GROUP(APP)\n         DSNAME(APP.CUST)\n")
    (repo / "cbl" / "PROG.cbl").write_text(
        "       ID DIVISION.\n       PROGRAM-ID. PROG.\n       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n"
        "       01 REC-SIZE PIC S9(4) BINARY VALUE 0040.\n"
        "       LINKAGE SECTION.\n"
        "       01 DFHCOMMAREA.\n"
        "          03 CA-REQ-ID PIC X(6).\n"
        "          03 CA-CUST-NUM PIC 9(10).\n"
        "          03 CA-SPECIFIC PIC X(500).\n"
        "          03 CA-SECR REDEFINES CA-SPECIFIC.\n"
        "             05 CA-PASS PIC X(32).\n"
        "             05 CA-REST PIC X(468).\n"
        "          03 CA-CUST REDEFINES CA-SPECIFIC.\n"
        "             05 CA-FIRST PIC X(10).\n"
        "             05 CA-LAST PIC X(20).\n"
        "             05 CA-POLICY PIC X(470).\n"
        "       PROCEDURE DIVISION.\n"
        "           EXEC CICS WRITE FILE('CUSTF') FROM(CA-CUST-NUM)\n"
        "                LENGTH(REC-SIZE) RIDFLD(CA-CUST-NUM) END-EXEC.\n"
        "           EXEC CICS RETURN END-EXEC.\n"
    )
    ir = load_galaxy_ir(scan_to_db(repo, tmp_path / "scan"))
    (store,) = ir.vsam_stores()
    assert (store["key_offset"], store["key_length"], store["record_max"]) == (0, 10, 40)
    (user,) = store["users"]
    (rec,) = user["records"]
    assert (rec["record"], rec["length"], rec["window_of"], rec["window_offset"], rec["overlay"]) == (
        "CA-CUST-NUM",
        40,
        "DFHCOMMAREA",
        6,
        "CA-CUST",
    )
    assert [(f["name"], f["offset"], f["bytes"]) for f in rec["layout"]["fields"]] == [
        ("CA-CUST-NUM", 0, 10),
        ("CA-FIRST", 10, 10),
        ("CA-LAST", 20, 20),
    ]
    assert rec["layout"]["bytes"] == 40
    assert user["ridflds"] == [{"ridfld": "CA-CUST-NUM", "offset": 0, "length": 10}]

    # the entity carries the whole record, keyed by IDCAMS KEYS
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_repository_forge import RepositoryForge

    forge = RepositoryForge({"sections": {"vsam_stores": {"facts": [store]}}}, {"PROG": {"program": {"file": "cbl/PROG.cbl"}}},
                            "com.acme")  # fmt: skip
    (st,) = forge.stores
    assert [(f.cobol, f.offset, f.bytes) for f in st.fields] == [
        ("CA-CUST-NUM", 0, 10), ("CA-FIRST", 10, 10), ("CA-LAST", 20, 20)]  # fmt: skip
    assert st.key is not None and st.key.cobol == "CA-CUST-NUM"
    assert "from offset 6 of DFHCOMMAREA, laid out by REDEFINES CA-CUST" in forge.entity_source(st)


def test_a_cics_write_is_duprec_on_a_key_already_on_file(scanned, tmp_path):
    """A CICS WRITE adds a record: the service checks the key first, as CICS raises DUPREC (save would replace)."""
    _, src = _java(scanned, tmp_path)
    cics = (src / "service/AcctcicsService.java").read_text(encoding="utf-8")
    assert "Optional<AcctRec> onFile = acctRecRepository.findById(record.getAcctId());" in cics
    assert "throw new org.springframework.dao.DuplicateKeyException(" in cics
    bat = (src / "service/TcatbatService.java").read_text(encoding="utf-8")
    assert "DuplicateKeyException" not in bat  # a REWRITE replaces the record it read


# ---- #4949: the symbolic merge keeps the batch programs that open the symbolic dataset ----------------------------
_SYM_BATCH = """\
       ID DIVISION.
       PROGRAM-ID. BATPROG.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT ACCT-FILE ASSIGN TO VSAM
                  ORGANIZATION IS INDEXED ACCESS MODE IS RANDOM
                  RECORD KEY IS ACCT-ID FILE STATUS IS ACCT-STATUS.
       DATA DIVISION.
       FILE SECTION.
       FD  ACCT-FILE.
       01  ACCT-REC.
           05 ACCT-ID PIC X(8).
           05 FILLER PIC X(30).
       WORKING-STORAGE SECTION.
       01  ACCT-STATUS PIC XX.
       PROCEDURE DIVISION.
           OPEN OUTPUT ACCT-FILE.
           WRITE ACCT-REC.
           CLOSE ACCT-FILE.
           GOBACK.
"""


def _symbolic_batch_estate(tmp_path, keys="8 0"):
    repo = tmp_path / "repo"
    for d in ("jcl", "cbl", "csd"):
        (repo / d).mkdir(parents=True)
    (repo / "jcl" / "DEF.jcl").write_text(
        "//DEF JOB\n//STEP1 EXEC PGM=IDCAMS\n//SYSIN DD *\n"
        f"  DEFINE CLUSTER(NAME(@PFX@.ACCT.KSDS) -\n         KEYS({keys}) RECORDSIZE(38 38) INDEXED)\n/*\n"
        "//RUN EXEC PGM=IKJEFT01\n//VSAM DD DISP=SHR,DSN=@PFX@.ACCT.KSDS\n//SYSTSIN DD *\n"
        " DSN SYSTEM(DB2)\n RUN PROGRAM(BATPROG) PLAN(P)\n END\n/*\n"
    )
    (repo / "csd" / "APP.csd").write_text("  DEFINE FILE(ACCTF) GROUP(APP)\n         DSNAME(PROD.APP.ACCT.KSDS)\n")
    (repo / "cbl" / "BATPROG.cbl").write_text(_SYM_BATCH)
    (repo / "cbl" / "CICSPROG.cbl").write_text(
        "       ID DIVISION.\n       PROGRAM-ID. CICSPROG.\n       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n"
        "       01 ACCT-REC.\n          05 ACCT-ID PIC X(8).\n          05 FILLER PIC X(30).\n"
        "       PROCEDURE DIVISION.\n"
        "           EXEC CICS READ FILE('ACCTF') INTO(ACCT-REC)\n                     RIDFLD(ACCT-ID) END-EXEC.\n"
    )
    return load_galaxy_ir(scan_to_db(repo, tmp_path / "scan")).vsam_stores()


def test_a_merged_symbolic_store_keeps_its_batch_users(tmp_path):
    (store,) = _symbolic_batch_estate(tmp_path)
    assert store["dataset"] == "PROD.APP.ACCT.KSDS" and store["defined_by"]["match"] == "symbolic"
    users = {(u["kind"], u["program"].rsplit("/", 1)[-1]): u for u in store["users"]}
    assert set(users) == {("cics", "CICSPROG.cbl"), ("batch", "BATPROG.cbl")}
    batch = users[("batch", "BATPROG.cbl")]
    assert (batch["name"], batch["dd"], batch["modes"]) == ("ACCT-FILE", "VSAM", ["OUTPUT"])
    assert batch["records"][0]["record"] == "ACCT-REC"


def test_a_refused_symbolic_merge_keeps_the_batch_user_on_its_own_store(tmp_path):
    stores = _symbolic_batch_estate(tmp_path, keys="4 12")  # the RIDFLD disagrees: no merge
    by = {s["dataset"]: s for s in stores}
    assert "symbolic_candidate_rejected" in by["PROD.APP.ACCT.KSDS"]
    assert [u["kind"] for u in by["@PFX@.ACCT.KSDS"]["users"]] == ["batch"]
    assert [u["kind"] for u in by["PROD.APP.ACCT.KSDS"]["users"]] == ["cics"]


# ---- #5034: a CALLed subprogram runs under its caller's step DDs (CardDemo CBSTM03B, called by CBSTM03A) ----------
def _prog(name, body, select=None):
    files = ""
    if select:
        files = (
            "       ENVIRONMENT DIVISION.\n       INPUT-OUTPUT SECTION.\n       FILE-CONTROL.\n"
            f"           SELECT {select}-FILE ASSIGN TO {select}DD\n"
            f"                  ORGANIZATION IS INDEXED ACCESS MODE IS RANDOM RECORD KEY IS {select}-ID.\n"
            f"       DATA DIVISION.\n       FILE SECTION.\n       FD  {select}-FILE.\n"
            f"       01  {select}-REC.\n           05 {select}-ID PIC X(8).\n           05 FILLER PIC X(30).\n"
        )
    return (
        f"       IDENTIFICATION DIVISION.\n       PROGRAM-ID. {name}.\n{files}"
        f"       WORKING-STORAGE SECTION.\n       01  WS-TARGET PIC X(8).\n"
        f"       PROCEDURE DIVISION.\n{body}           GOBACK.\n"
    )


def _call_estate(tmp_path, jcl, programs):
    repo = tmp_path / "repo"
    for d in ("jcl", "cbl"):
        (repo / d).mkdir(parents=True)
    for name, text in jcl.items():
        (repo / "jcl" / f"{name}.jcl").write_text(text)
    for name, text in programs.items():
        (repo / "cbl" / f"{name}.cbl").write_text(text)
    return load_galaxy_ir(scan_to_db(repo, tmp_path / "scan"))


_DEFINE = (
    "//DEF JOB\n//S1 EXEC PGM=IDCAMS\n//SYSIN DD *\n"
    "  DEFINE CLUSTER(NAME(APP.LEAF.KSDS) KEYS(8 0) RECORDSIZE(38 38) INDEXED)\n"
    "  DEFINE CLUSTER(NAME(APP.OTHER.KSDS) KEYS(8 0) RECORDSIZE(38 38) INDEXED)\n/*\n"
)
_LEAF = _prog("LEAF", "           OPEN INPUT LEAF-FILE.\n           CLOSE LEAF-FILE.\n", "LEAF")


def _lineage(ir, program):
    return sorted(
        (e["job"].rsplit("/", 1)[-1] if e["job"] else None, e["dd_name"], e["dataset"])
        for e in ir.dataset_lineage()
        if e["program"].endswith(f"/{program}.cbl")
    )


def test_a_called_program_takes_its_callers_step_dds(tmp_path):
    ir = _call_estate(
        tmp_path,
        {"DEF": _DEFINE, "RUN": "//RUN JOB\n//ST EXEC PGM=TOP\n//LEAFDD DD DSN=APP.LEAF.KSDS,DISP=SHR\n"},
        {
            "TOP": _prog("TOP", "           CALL 'MID'.\n"),
            "MID": _prog("MID", "           CALL 'LEAF'.\n"),
            "LEAF": _LEAF,
        },
    )
    assert _lineage(ir, "LEAF") == [("RUN.jcl", "LEAFDD", "APP.LEAF.KSDS")]  # two CALLs down
    (store,) = [s for s in ir.vsam_stores() if s["dataset"] == "APP.LEAF.KSDS"]
    assert [(u["kind"], u["program"].rsplit("/", 1)[-1], u["dd"]) for u in store["users"]] == [
        ("batch", "LEAF.cbl", "LEAFDD")
    ]


def test_a_call_cycle_terminates_and_binds_each_program_once(tmp_path):
    ir = _call_estate(
        tmp_path,
        {"RUN": "//RUN JOB\n//ST EXEC PGM=TOP\n//LEAFDD DD DSN=APP.LEAF.KSDS,DISP=SHR\n"},
        {
            "TOP": _prog("TOP", "           CALL 'LEAF'.\n"),
            "LEAF": _prog("LEAF", "           OPEN INPUT LEAF-FILE.\n           CALL 'TOP'.\n", "LEAF"),
        },
    )
    assert _lineage(ir, "LEAF") == [("RUN.jcl", "LEAFDD", "APP.LEAF.KSDS")]


def test_a_dynamic_call_binds_nothing(tmp_path):
    ir = _call_estate(
        tmp_path,
        {"RUN": "//RUN JOB\n//ST EXEC PGM=TOP\n//LEAFDD DD DSN=APP.LEAF.KSDS,DISP=SHR\n"},
        {"TOP": _prog("TOP", "           CALL WS-TARGET.\n"), "LEAF": _LEAF},
    )
    assert _lineage(ir, "LEAF") == [(None, "LEAFDD", None)]  # the target is data: not followed


def test_a_callee_run_by_two_jobs_keeps_both_bindings(tmp_path):
    ir = _call_estate(
        tmp_path,
        {
            "DEF": _DEFINE,
            "RUN1": "//RUN1 JOB\n//ST EXEC PGM=TOP\n//LEAFDD DD DSN=APP.LEAF.KSDS,DISP=SHR\n",
            "RUN2": "//RUN2 JOB\n//ST EXEC PGM=LEAF\n//LEAFDD DD DSN=APP.OTHER.KSDS,DISP=SHR\n",
        },
        {"TOP": _prog("TOP", "           CALL 'LEAF'.\n"), "LEAF": _LEAF},
    )
    assert _lineage(ir, "LEAF") == [
        ("RUN1.jcl", "LEAFDD", "APP.LEAF.KSDS"),
        ("RUN2.jcl", "LEAFDD", "APP.OTHER.KSDS"),
    ]
    # one DD on two datasets: the repository stays refused by design
    (v,) = [x for x in ir.vsam_files() if x["program"].endswith("/LEAF.cbl")]
    assert v["datasets"] == ["APP.LEAF.KSDS", "APP.OTHER.KSDS"]


# ---- #5072: a DD binding belongs to its own step, not the whole job ------------------------------------------------
_TWO_STEPS = (
    "//RUN JOB\n//S1 EXEC PGM={a}\n//LEAFDD DD DSN=APP.LEAF.KSDS,DISP=SHR\n"
    "//S2 EXEC PGM={b}\n//LEAFDD DD DSN=APP.OTHER.KSDS,DISP=SHR\n"
)
_FILE_PROG = _prog("OTH", "           OPEN INPUT LEAF-FILE.\n           CLOSE LEAF-FILE.\n", "LEAF")


def test_each_step_binds_only_its_own_dd(tmp_path):
    ir = _call_estate(
        tmp_path,
        {"DEF": _DEFINE, "RUN": _TWO_STEPS.format(a="LEAF", b="OTH")},
        {"LEAF": _LEAF, "OTH": _FILE_PROG},
    )
    assert _lineage(ir, "LEAF") == [("RUN.jcl", "LEAFDD", "APP.LEAF.KSDS")]
    assert _lineage(ir, "OTH") == [("RUN.jcl", "LEAFDD", "APP.OTHER.KSDS")]
    (v,) = [x for x in ir.vsam_files() if x["program"].endswith("/LEAF.cbl")]
    assert v["datasets"] == ["APP.LEAF.KSDS"]  # one DSN: no longer refused


def test_a_callee_takes_only_its_callers_step(tmp_path):
    ir = _call_estate(
        tmp_path,
        {"DEF": _DEFINE, "RUN": _TWO_STEPS.format(a="TOP", b="OTH")},
        {
            "TOP": _prog("TOP", "           CALL 'MID'.\n"),
            "MID": _prog("MID", "           CALL 'LEAF'.\n"),
            "LEAF": _LEAF,
            "OTH": _FILE_PROG,
        },
    )
    assert _lineage(ir, "LEAF") == [("RUN.jcl", "LEAFDD", "APP.LEAF.KSDS")]  # two CALLs down, step S1 only


def test_a_callee_reached_from_two_steps_takes_both(tmp_path):
    ir = _call_estate(
        tmp_path,
        {"DEF": _DEFINE, "RUN": _TWO_STEPS.format(a="TOPA", b="TOPB")},
        {
            "TOPA": _prog("TOPA", "           CALL 'LEAF'.\n"),
            "TOPB": _prog("TOPB", "           CALL 'LEAF'.\n"),
            "LEAF": _LEAF,
        },
    )
    assert _lineage(ir, "LEAF") == [("RUN.jcl", "LEAFDD", "APP.LEAF.KSDS"), ("RUN.jcl", "LEAFDD", "APP.OTHER.KSDS")]


def test_one_program_run_by_two_steps_keeps_both_bindings(tmp_path):
    ir = _call_estate(
        tmp_path,
        {"DEF": _DEFINE, "RUN": _TWO_STEPS.format(a="LEAF", b="LEAF")},
        {"LEAF": _LEAF},
    )
    assert _lineage(ir, "LEAF") == [("RUN.jcl", "LEAFDD", "APP.LEAF.KSDS"), ("RUN.jcl", "LEAFDD", "APP.OTHER.KSDS")]


def test_a_call_cycle_across_steps_scopes_each_step(tmp_path):
    ir = _call_estate(
        tmp_path,
        {"DEF": _DEFINE, "RUN": _TWO_STEPS.format(a="TOP", b="OTH")},
        {
            "TOP": _prog("TOP", "           CALL 'LEAF'.\n"),
            "LEAF": _prog("LEAF", "           OPEN INPUT LEAF-FILE.\n           CALL 'TOP'.\n", "LEAF"),
            "OTH": _FILE_PROG,
        },
    )
    assert _lineage(ir, "LEAF") == [("RUN.jcl", "LEAFDD", "APP.LEAF.KSDS")]


def test_a_step_that_is_not_found_keeps_the_whole_job(tmp_path):
    # a DD bound outside any named step of the job (a PROC step) is not scoped away
    jcl = "//RUN JOB\n//S1 EXEC PGM=LEAF\n//LEAFDD DD DSN=APP.LEAF.KSDS,DISP=SHR\n"
    ir = _call_estate(tmp_path, {"DEF": _DEFINE, "RUN": jcl}, {"LEAF": _LEAF})
    assert _lineage(ir, "LEAF") == [("RUN.jcl", "LEAFDD", "APP.LEAF.KSDS")]


# ---- #5072: a CALL through a data item is followed only where the item has one provable value ----------------------
_RUN = "//RUN JOB\n//ST EXEC PGM=TOP\n//LEAFDD DD DSN=APP.LEAF.KSDS,DISP=SHR\n"
_BOUND = [("RUN.jcl", "LEAFDD", "APP.LEAF.KSDS")]
_UNBOUND = [(None, "LEAFDD", None)]


def _dyn_top(ws, body):
    return _prog("TOP", body).replace("       01  WS-TARGET PIC X(8).\n", ws)


@pytest.mark.parametrize(
    "ws, body, expected",
    [
        pytest.param(
            "       01  WS-TARGET PIC X(8).\n", "           MOVE 'LEAF' TO WS-TARGET.\n", _BOUND, id="one-move"
        ),
        pytest.param("       01  WS-TARGET PIC X(8) VALUE 'LEAF'.\n", "", _BOUND, id="value"),
        pytest.param(
            "       01  WS-TARGET PIC X(8) VALUE 'LEAF'.\n", "           MOVE 'LEAF' TO WS-TARGET.\n", _BOUND, id="same"
        ),
        pytest.param(
            "       01  WS-TARGET PIC X(8) VALUE 'LEAF'.\n",
            "           MOVE 'OTHER' TO WS-TARGET.\n",
            _UNBOUND,
            id="two",
        ),
        pytest.param(
            "       01  WS-TARGET PIC X(8).\n       01  WS-IN PIC X(8).\n",
            "           MOVE 'LEAF' TO WS-TARGET.\n           MOVE WS-IN TO WS-TARGET.\n",
            _UNBOUND,
            id="unknown-source",
        ),
        pytest.param(
            "       01  WS-TARGET PIC X(8).\n",
            "           MOVE 'LEAF' TO WS-TARGET.\n           MOVE 'LEAF2' TO WS-TARGET.\n",
            _UNBOUND,
            id="two-moves",
        ),
        pytest.param(
            "       01  WS-TARGET PIC X(8).\n",
            "           MOVE 'NOSUCH' TO WS-TARGET.\n",
            _UNBOUND,
            id="not-in-repo",
        ),
    ],
)
def test_a_dynamic_call_is_followed_only_for_one_provable_value(tmp_path, ws, body, expected):
    ir = _call_estate(
        tmp_path,
        {"DEF": _DEFINE, "RUN": _RUN},
        {"TOP": _dyn_top(ws, body + "           CALL WS-TARGET.\n"), "LEAF": _LEAF},
    )
    assert _lineage(ir, "LEAF") == expected


def test_a_dynamic_call_takes_only_its_callers_step(tmp_path):
    ir = _call_estate(
        tmp_path,
        {"DEF": _DEFINE, "RUN": _TWO_STEPS.format(a="TOP", b="OTH")},
        {
            "TOP": _dyn_top(
                "       01  WS-TARGET PIC X(8).\n", "           MOVE 'LEAF' TO WS-TARGET.\n           CALL WS-TARGET.\n"
            ),
            "LEAF": _LEAF,
            "OTH": _FILE_PROG,
        },
    )
    assert _lineage(ir, "LEAF") == _BOUND  # step S1 only


def test_a_dynamic_call_cycle_terminates(tmp_path):
    top = _dyn_top(
        "       01  WS-TARGET PIC X(8).\n", "           MOVE 'LEAF' TO WS-TARGET.\n           CALL WS-TARGET.\n"
    )
    leaf = _prog("LEAF", "           OPEN INPUT LEAF-FILE.\n           CALL 'TOP'.\n", "LEAF")
    ir = _call_estate(tmp_path, {"DEF": _DEFINE, "RUN": _RUN}, {"TOP": top, "LEAF": leaf})
    assert _lineage(ir, "LEAF") == _BOUND
