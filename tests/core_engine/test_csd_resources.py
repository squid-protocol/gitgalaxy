"""
#3356: CSD resource definitions beyond TRANSACTION/PROGRAM -- the `csd_resources`
channel of core/mainframe_boundary.py.

Every shape here is lifted from the pinned corpora: carddemo's CEDA EXTRACT dump
(CARDDEMO.CSD: FILE, TDQUEUE, LIBRARY), its DB2 decks (CRDDEMOD.csd: DB2ENTRY +
DB2TRAN at column 1), CBSA's hand-written DFHCSDUP SYSIN (BANK.csd: FILE with
KEYLENGTH/RECORDSIZE, DB2CONN, TCPIPSERVICE, quoted DESCRIPTIONs) and the inline
DFHCSDUP SYSIN in a JCL job (carddemo CBADMCDJ.jcl).
"""

from gitgalaxy.core.mainframe_boundary import _csd_attributes, _csd_transactions, extract_boundary

# carddemo CARDDEMO.CSD (a leading blank column, no continuation character).
CARDDEMO_EXTRACT = """\
 DEFINE FILE(ACCTDAT) GROUP(CARDDEMO)
        DSNAME(AWS.M2.CARDDEMO.ACCTDATA.VSAM.KSDS) RLSACCESS(NO)
        UPDATEMODEL(LOCKING) LOAD(NO) RECORDFORMAT(V) ADD(YES)
        BACKUPTYPE(STATIC) DEFINETIME(22/05/13 12:56:44)
 DEFINE MAPSET(COACTUP) GROUP(CARDDEMO)
 DESCRIPTION(CREDIT CARD ACCOUNT UPDATE MAP)
        RESIDENT(NO) USAGE(NORMAL) USELPACOPY(NO) STATUS(ENABLED)
 DEFINE LIBRARY(CARDDLIB) GROUP(CARDDEMO)
        RANKING(50) CRITICAL(NO) STATUS(ENABLED)
        DSNAME01(AWS.M2.CARDDEMO.LOADLIB) DEFINETIME(22/02/19 19:04:04)
 DEFINE TDQUEUE(JOBS) GROUP(CARDDEMO)
 DESCRIPTION(SUBMIT JOBS FROM CICS)
        TYPE(EXTRA) DATABUFFERS(1) DDNAME(INREADER) ERROROPTION(IGNORE)
        OPENTIME(INITIAL) TYPEFILE(OUTPUT) RECORDSIZE(80)
        RECORDFORMAT(FIXED) BLOCKFORMAT(UNBLOCKED) DISPOSITION(MOD)
"""

# carddemo CRDDEMOD.csd: DEFINE at column 1, the DB2 pair.
CARDDEMO_DB2 = """\
DEFINE DB2ENTRY(CARDDEMO) GROUP(CARDDEMO)
DESCRIPTION(DB2 RETRY FOR CARDDEMO PLAN)
       ACCOUNTREC(TXID) AUTHTYPE(USERID) DROLLBACK(YES) PLAN(CARDDEMO)
       PRIORITY(HIGH) PROTECTNUM(0) THREADLIMIT(1) THREADWAIT(YES)
DEFINE DB2TRAN(CTLITRAN) GROUP(CARDDEMO)
DESCRIPTION(DB2TRAN FOR CTLI TRANSACTION)
       ENTRY(CARDDEMO) TRANSID(CTLI) DEFINETIME(23/03/24 11:16:32)
DEFINE TRANSACTION(CTLI) GROUP(CARDDEMO)
       PROGRAM(COTRTLIC) TWASIZE(0) PROFILE(DFHCICST) STATUS(ENABLED)
"""

# CBSA BANK.csd: `*` comments, a DELETE command, blank-line separators, a
# quoted DESCRIPTION, KEYLENGTH/RECORDSIZE, DB2CONN and TCPIPSERVICE.
CBSA_SYSIN = """\
*
* Copyright IBM Corp. 2023
*
 DELETE GROUP(BANK)

 DEFINE FILE(CUSTOMER) GROUP(BANK)
 DESCRIPTION(Bank Customer VSAM)
        DSNAME(CBSA.CICSBSA.CUSTOMER) RLSACCESS(NO)
        STRINGS(20) RECORDSIZE(259) KEYLENGTH(16) STATUS(ENABLED)
        UPDATEMODEL(LOCKING) LOAD(NO) RECORDFORMAT(V) ADD(YES)

 DEFINE MAPSET(BNK1ACC) GROUP(BANK)
 DESCRIPTION('BANK Online Inquire Account for Customer')
        RESIDENT(NO) USAGE(NORMAL) USELPACOPY(NO) STATUS(ENABLED)

DEFINE TCPIPSERVICE(BANK) GROUP(BANK)
  PORTNUMBER(12345)
  PROTOCOL(HTTP)
  TRANSACTION(CWXN)

 DEFINE DB2CONN(DBCG) GROUP(BANK)
 CONNECTERROR(SQLCODE) DB2ID(DBCG) MSGQUEUE1(CSMT)
 PLAN(CBSA)
"""

# carddemo CBADMCDJ.jcl: a DFHCSDUP deck inline, `*`-commented DEFINEs, and a
# DSNAME01 written with a JCL symbol (kept as written).
JCL_INLINE = """\
//CBADMCDJ JOB (COBOL),'AWSCODR',CLASS=A
//   SET HLQ=AWS.M2.CARDDEMO
//STEP1   EXEC PGM=DFHCSDUP,REGION=0M
//SYSIN    DD  *,SYMBOLS=JCLONLY
  DEFINE LIBRARY(COM2DOLL) GROUP(CARDDEMO)
                DSNAME01(&HLQ..LOADLIB)

* DEFINE TDQUEUE(CSSD) GROUP(CARDDEMO) TYPE(INTRA)
  DEFINE MAPSET(COSGN00M) GROUP(CARDDEMO)
/*
"""


def _resources(dialect, text):
    return extract_boundary(dialect, text)["csd_resources"]


def _by_name(rows):
    return {(r["resource_type"], r["name"]): r for r in rows}


def test_a_file_carries_its_dataset_and_record_shape():
    (acct,) = [r for r in _resources("csd", CARDDEMO_EXTRACT) if r["resource_type"] == "FILE"]
    assert acct["name"] == "ACCTDAT"
    assert acct["group"] == "CARDDEMO"
    assert acct["dsname"] == "AWS.M2.CARDDEMO.ACCTDATA.VSAM.KSDS"
    assert acct["record_format"] == "V"
    assert acct["key_length"] is None and acct["record_size"] is None  # carddemo writes neither
    assert acct["line"] == 1

    (cust,) = [r for r in _resources("csd", CBSA_SYSIN) if r["resource_type"] == "FILE"]
    assert (cust["dsname"], cust["key_length"], cust["record_size"]) == ("CBSA.CICSBSA.CUSTOMER", 16, 259)


def test_every_define_is_one_row_in_source_order_of_any_type():
    rows = _resources("csd", CARDDEMO_EXTRACT)
    assert [(r["resource_type"], r["name"], r["line"]) for r in rows] == [
        ("FILE", "ACCTDAT", 1),
        ("MAPSET", "COACTUP", 5),
        ("LIBRARY", "CARDDLIB", 8),
        ("TDQUEUE", "JOBS", 11),
    ]
    mapset = _by_name(rows)[("MAPSET", "COACTUP")]
    # A MAPSET has no join attribute; its facts ride in `attributes`.
    assert all(
        mapset[k] is None
        for k in ("dsname", "ddname", "record_format", "key_length", "record_size", "queue_type", "plan")
    )
    assert mapset["attributes"].startswith("GROUP(CARDDEMO) DESCRIPTION(CREDIT CARD ACCOUNT UPDATE MAP) RESIDENT(NO)")


def test_library_takes_its_first_concatenated_dataset():
    lib = _by_name(_resources("csd", CARDDEMO_EXTRACT))[("LIBRARY", "CARDDLIB")]
    assert lib["dsname"] == "AWS.M2.CARDDEMO.LOADLIB"


def test_an_extrapartition_tdqueue_carries_type_ddname_and_shape():
    q = _by_name(_resources("csd", CARDDEMO_EXTRACT))[("TDQUEUE", "JOBS")]
    assert (q["queue_type"], q["ddname"], q["dsname"]) == ("EXTRA", "INREADER", None)
    assert (q["record_format"], q["record_size"]) == ("FIXED", 80)


def test_db2tran_names_its_entry_and_transid_and_db2entry_its_plan():
    rows = _by_name(_resources("csd", CARDDEMO_DB2))
    assert rows[("DB2ENTRY", "CARDDEMO")]["plan"] == "CARDDEMO"
    tran = rows[("DB2TRAN", "CTLITRAN")]
    assert (tran["db2_entry"], tran["transid"], tran["plan"]) == ("CARDDEMO", "CTLI", None)
    # TRANSACTION rows are kept too, with their own id and the program they name.
    txn = rows[("TRANSACTION", "CTLI")]
    assert (txn["transid"], txn["program"]) == ("CTLI", "COTRTLIC")


def test_the_db2tran_transid_still_never_enters_the_transaction_map():
    """#3211-followup's exclusion is unchanged: the resource row does not leak a
    DB2TRAN's TRANSID into `transactions`."""
    assert [(t["transid"], t["program"]) for t in _csd_transactions(CARDDEMO_DB2)] == [("CTLI", "COTRTLIC")]


def test_sysin_comments_commands_and_other_resource_types():
    rows = _by_name(_resources("csd", CBSA_SYSIN))
    assert set(rows) == {("FILE", "CUSTOMER"), ("MAPSET", "BNK1ACC"), ("TCPIPSERVICE", "BANK"), ("DB2CONN", "DBCG")}
    assert rows[("TCPIPSERVICE", "BANK")]["transid"] == "CWXN"
    assert rows[("DB2CONN", "DBCG")]["plan"] == "CBSA"
    assert "DESCRIPTION('BANK Online Inquire Account for Customer')" in rows[("MAPSET", "BNK1ACC")]["attributes"]


def test_jcl_inline_deck_is_read_and_a_commented_define_is_not():
    rows = _resources("jcl", JCL_INLINE)
    assert [(r["resource_type"], r["name"]) for r in rows] == [("LIBRARY", "COM2DOLL"), ("MAPSET", "COSGN00M")]
    # A symbol in in-stream data is kept as written (SYMBOLS=JCLONLY substitution
    # is the JCL's, not the CSD's).
    assert rows[0]["dsname"] == "&HLQ..LOADLIB"


def test_a_job_that_does_not_run_dfhcsdup_yields_no_resources():
    assert _resources("jcl", JCL_INLINE.replace("PGM=DFHCSDUP", "PGM=IEFBR14")) == []


def test_other_dialects_carry_no_resources():
    for dialect in ("cobol", "pli", "bms"):
        assert extract_boundary(dialect, CBSA_SYSIN).get("csd_resources", []) == []
    assert extract_boundary("csd", "")["transactions"] == []


def test_a_word_paren_inside_a_value_is_not_an_attribute():
    """A `KEYWORD(` inside a value no longer plants a fake attribute ahead of the
    real one (the scan resumes after each value)."""
    attrs = _csd_attributes("DESCRIPTION(RETRY FOR PLAN(X)) PLAN(Y)")
    assert attrs == {"DESCRIPTION": "RETRY FOR PLAN(X)", "PLAN": "Y"}


def test_an_unterminated_quote_does_not_swallow_the_later_attributes():
    attrs = _csd_attributes("DESCRIPTION(Bank's file) PROGRAM(X) PLAN(Y)")
    assert (attrs["PROGRAM"], attrs["PLAN"]) == ("X", "Y")


def test_a_pathological_record_stays_linear():
    """Bounded: a 38KB record of 6,000 unterminated values is scanned in linear
    time (~1s). Rescanning each value to the end of the record -- the unbounded
    shape -- is quadratic here (~10^8 character steps)."""
    import time

    record = "DEFINE FILE(X) " + "DESCRIPTION(" * 2000 + "'" * 2000 + " PLAN(" * 2000
    start = time.perf_counter()
    _resources("csd", record)
    assert time.perf_counter() - start < 6.0
