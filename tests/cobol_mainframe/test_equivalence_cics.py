"""#3754: the CICS half of the equivalence harness, without a container.

The translator is pinned per command (what each EXEC CICS becomes, and that an unknown one
is refused by name, never skipped), the stub's file table is derived from a real scan of a
small estate -- CSD DEFINE FILE -> DSNAME -> IDCAMS KEYS, a PATH through its AIX -- and the
pieces the comparison stands on are pinned: field encoding round-trips, a DTO's shape read
from its comments, and events compared field by field.
"""

import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence as eq  # noqa: E402
import equivalence_cics as ec  # noqa: E402

from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db  # noqa: E402


def test_a_read_becomes_a_stub_call_and_its_resp_is_the_programs():
    got = ec.translate_command(" READ DATASET (LIT-ACCTFILENAME) RIDFLD (WS-KEY) KEYLENGTH (LENGTH OF WS-KEY)"
                               " INTO (ACCOUNT-RECORD) RESP (WS-RESP-CD) RESP2 (WS-REAS-CD) ")  # fmt: skip
    assert got[:3] == ["MOVE LIT-ACCTFILENAME TO GG-NAME1", "MOVE SPACES TO GG-FLAGS",  # not UPDATE: holds nothing
                       "CALL 'GGCREAD' USING GG-CICS"]  # fmt: skip
    assert "    BY VALUE LENGTH OF WS-KEY" in got and "    BY REFERENCE ACCOUNT-RECORD" in got
    assert got[-2:] == ["MOVE GG-RESP TO WS-RESP-CD", "MOVE GG-RESP2 TO WS-REAS-CD"]


def test_an_untested_condition_goes_to_the_stubs_condition_handling():
    """#4003: no RESP / NOHANDLE -> GGCCOND decides (IGNORE, a HANDLE label, ERROR, or an abend); a label
    is a GO TO ... DEPENDING ON over the program's HANDLE labels, and GG-GOTO -1 leaves the program."""
    got = ec.translate_command("RECEIVE MAP('MAP1') MAPSET('SET1') INTO(MAP1I)")
    assert got[-6:] == ["IF GG-RESP NOT = 0", "    CALL 'GGCCOND' USING GG-CICS", "    IF GG-GOTO < 0",
                        "        GOBACK", "    END-IF", "END-IF"]  # fmt: skip
    got = ec.translate_command("READQ TS QUEUE('Q') INTO(X) LENGTH(L)", ["NO-QUEUE", "PAST-END"])
    assert got[-9:-3] == ["    CALL 'GGCCOND' USING GG-CICS", "    GO TO", "        NO-QUEUE", "        PAST-END",
                           "        DEPENDING ON GG-GOTO", "    IF GG-GOTO < 0"]  # fmt: skip
    for body in ("READQ TS QUEUE('Q') INTO(X) RESP(R)", "READQ TS QUEUE('Q') INTO(X) NOHANDLE"):
        assert "    CALL 'GGCCOND' USING GG-CICS" not in ec.translate_command(body, ["A"])


def test_handle_ignore_push_pop_and_assign_become_stub_calls():
    labels = ec.handler_labels(["HANDLE CONDITION QIDERR(NO-QUEUE) ITEMERR(past-end) ERROR(ANY-ERROR)", "RETURN",
                                "HANDLE ABEND LABEL(MAIN-ABEND)", "HANDLE ABEND CANCEL", "HANDLE AID PF3(BYE)",
                                "HANDLE CONDITION ITEMERR(PAST-END) LENGERR"])  # fmt: skip
    assert labels == ["NO-QUEUE", "PAST-END", "ANY-ERROR", "MAIN-ABEND", "BYE"]
    got = ec.translate_command("HANDLE CONDITION QIDERR(NO-QUEUE) LENGERR", labels)
    assert got == ["MOVE 44 TO GG-NUM", "MOVE 1 TO GG-ITEM", "CALL 'GGCHCND' USING GG-CICS",
                   "MOVE 22 TO GG-NUM", "MOVE 0 TO GG-ITEM", "CALL 'GGCHCND' USING GG-CICS"]  # fmt: skip
    assert ec.translate_command("IGNORE CONDITION ITEMERR", labels)[:2] == ["MOVE 26 TO GG-NUM", "MOVE -1 TO GG-ITEM"]
    assert ec.translate_command("HANDLE ABEND LABEL(MAIN-ABEND)", labels) == [
        "MOVE 'LABEL' TO GG-NAME2", "MOVE 4 TO GG-ITEM", "MOVE 'MAIN-ABEND' TO GG-FLAGS",
        "CALL 'GGCHABN' USING GG-CICS"]  # fmt: skip
    assert ec.translate_command("HANDLE ABEND CANCEL")[0] == "MOVE 'CANCEL' TO GG-NAME2"
    assert ec.translate_command("HANDLE ABEND RESET")[0] == "MOVE 'RESET' TO GG-NAME2"
    assert ec.translate_command("PUSH HANDLE")[0] == "CALL 'GGCPUSH' USING GG-CICS"
    assert "    CALL 'GGCCOND' USING GG-CICS" in ec.translate_command("POP HANDLE")  # INVREQ with nothing pushed
    assert ec.translate_command("ASSIGN ABCODE(WS-AB)")[1:3] == ["CALL 'GGCASGN' USING GG-CICS",
                                                                "MOVE GG-NAME1(1:4) TO WS-AB"]  # fmt: skip
    abend = ec.translate_command("ABEND ABCODE('HCX1')", ["SUB-ABEND"])
    assert abend[:3] == ["MOVE 'HCX1' TO GG-NAME1", "MOVE SPACES TO GG-FLAGS", "CALL 'GGCABND' USING GG-CICS"]
    assert abend[3:] == ["GO TO", "    SUB-ABEND", "    DEPENDING ON GG-GOTO", "GOBACK"]
    assert ec.translate_command("ABEND ABCODE('X') CANCEL")[1] == "MOVE 'CANCEL' TO GG-FLAGS"


def test_a_link_runs_a_new_level_on_the_callers_own_commarea():
    """#4004: GGCLINK checks and records the LINK; on NORMAL, GGCRUN runs the target on the caller's area (by
    reference) and GGCLRET pops the level, where an abend exit up here can take over; a failed LINK goes
    through the condition handling."""
    got = ec.translate_command("LINK PROGRAM('CASUB') COMMAREA(WS-CA100) LENGTH(100)", ["MAIN-ABEND"])
    assert got[:4] == ["MOVE 'CASUB' TO GG-NAME1", "MOVE 100 TO GG-LEN", "MOVE 1 TO GG-ITEM",
                       "CALL 'GGCLINK' USING GG-CICS"]  # fmt: skip
    assert got[5:12] == ["IF GG-RESP = 0", "    CALL 'GGCRUN' USING WS-CA100", "    CALL 'GGCLRET' USING GG-CICS",
                         "    GO TO", "        MAIN-ABEND", "        DEPENDING ON GG-GOTO", "    IF GG-GOTO < 0"]  # fmt: skip
    assert "    CALL 'GGCCOND' USING GG-CICS" in got  # PGMIDERR without RESP: the default action
    bare = ec.translate_command("LINK PROGRAM(WS-PGM) RESP(WS-R)")
    assert bare[1:3] == ["MOVE 0 TO GG-LEN", "MOVE 0 TO GG-ITEM"] and "    CALL 'GGCRUN' USING GG-FLAGS" in bare
    assert ec.translate_command("LINK PROGRAM('X') COMMAREA(CA)")[1] == "MOVE LENGTH OF CA TO GG-LEN"


def test_interval_control_commands_become_stub_calls():
    """#4006: START's TRANSID / TERMID / REQID / INTERVAL or TIME / FROM / PROTECT go to GGCSTRT; RETRIEVE's LENGTH
    is set back on NORMAL / LENGERR only; CANCEL needs a REQID."""
    got = ec.translate_command("START TRANSID('GT12') TERMID(WS-TERM) INTERVAL(30) FROM(WS-A) LENGTH(10) "
                               "REQID('GTREQ001') PROTECT")  # fmt: skip
    assert got[:7] == ["MOVE 'GT12' TO GG-NAME1", "MOVE WS-TERM TO GG-NAME2", "MOVE 'GTREQ001' TO GG-QNAME",
                       "MOVE 30 TO GG-NUM", "MOVE 'INTERVAL PROTECT' TO GG-FLAGS", "MOVE 10 TO GG-LEN",
                       "MOVE 1 TO GG-ITEM"]  # fmt: skip
    bare = ec.translate_command("START TRANSID('GT02') TIME(093000)")
    assert bare[1:7] == ["MOVE SPACES TO GG-NAME2", "MOVE SPACES TO GG-QNAME", "MOVE 093000 TO GG-NUM",
                         "MOVE 'TIME' TO GG-FLAGS", "MOVE 0 TO GG-LEN", "MOVE 0 TO GG-ITEM"]  # fmt: skip
    assert ec.translate_command("START TRANSID('GT02')")[3] == "MOVE 0 TO GG-NUM"
    r = ec.translate_command("RETRIEVE INTO(WS-DATA) LENGTH(WS-LEN) RESP(WS-RESP)")
    assert r[:5] == ["MOVE WS-LEN TO GG-LEN", "CALL 'GGCRTRV' USING GG-CICS", "    BY REFERENCE WS-DATA",
                     "IF GG-RESP = 0 OR GG-RESP = 22", "    MOVE GG-LEN TO WS-LEN"]  # fmt: skip
    assert ec.translate_command("CANCEL REQID('GTREQ001')")[:2] == ["MOVE 'GTREQ001' TO GG-QNAME",
                                                                   "CALL 'GGCCNCL' USING GG-CICS"]  # fmt: skip
    for body in ("START TRANSID('X') AFTER SECONDS(5)", "RETRIEVE SET(P) LENGTH(L)", "CANCEL", "START INTERVAL(0)"):
        with pytest.raises(ec.Unsupported):
            ec.translate_command(body)


def test_the_task_driver_and_dispatcher_are_generated_for_the_cases_programs():
    run = ec.task_dispatcher({"CALINK": False, "CASUB": True})
    assert "PROGRAM-ID. GGCRUN RECURSIVE." in run and "LOCAL-STORAGE SECTION." in run
    assert "            CALL 'CASUB' USING LK-X\n" in run and "            CALL 'CALINK'\n" in run
    assert "            CANCEL 'CASUB'\n" in run and "CALL 'GGCNOPG' USING GG-CICS" in run
    drv = ec.task_driver()
    assert "CALL 'GGCTASK' USING GG-CICS" in drv and "CALL 'GGCRUN' USING WS-CA" in drv
    assert "MOVE IN-TRMID TO EIBTRMID" in drv
    assert all(len(ln) <= 72 for ln in (run + drv).splitlines())


def test_handle_aid_labels_are_taken_after_an_input_command():
    """#4007: HANDLE AID registers each key's label; RECEIVE MAP / RECEIVE then GO TO the pressed key's label
    (GGCAID) when they completed normally, unless RESP or NOHANDLE suspends the handlers."""
    labels = ["MENU-EXIT", "MENU-REFRESH"]
    assert ec.translate_command("HANDLE AID PF3(MENU-EXIT) PF5(MENU-REFRESH) PF9", labels) == [
        "MOVE 'PF3' TO GG-NAME1", "MOVE 1 TO GG-ITEM", "CALL 'GGCHAID' USING GG-CICS",
        "MOVE 'PF5' TO GG-NAME1", "MOVE 2 TO GG-ITEM", "CALL 'GGCHAID' USING GG-CICS",
        "MOVE 'PF9' TO GG-NAME1", "MOVE 0 TO GG-ITEM", "CALL 'GGCHAID' USING GG-CICS"]  # fmt: skip
    recv = ec.translate_command("RECEIVE MAP('PCMN') MAPSET('PCSET2') INTO(PCMNI)", labels, handle_aid=True)
    assert recv[-8:] == ["IF GG-RESP = 0", "    MOVE EIBAID TO GG-NAME1", "    CALL 'GGCAID' USING GG-CICS",
                         "    GO TO", "        MENU-EXIT", "        MENU-REFRESH", "        DEPENDING ON GG-GOTO",
                         "END-IF"]  # fmt: skip
    assert "    CALL 'GGCAID' USING GG-CICS" in ec.translate_command("RECEIVE INTO(X) LENGTH(L)", labels, True)
    assert "    CALL 'GGCAID' USING GG-CICS" not in ec.translate_command("RECEIVE MAP('M') INTO(X)", labels)
    for body in ("RECEIVE MAP('M') INTO(X) RESP(R)", "RECEIVE MAP('M') INTO(X) NOHANDLE"):
        assert "    CALL 'GGCAID' USING GG-CICS" not in ec.translate_command(body, labels, handle_aid=True)
    with pytest.raises(ec.Unsupported):
        ec.translate_command("HANDLE AID PF99(X)", ["X"])


def test_a_program_names_itself_to_the_stub_as_it_starts():
    text, _ = ec.translate(PROGRAM)
    lines = text.splitlines()
    at = next(i for i, ln in enumerate(lines) if "PROCEDURE DIVISION" in ln)
    assert lines[at + 1 : at + 3] == [
        "           MOVE 'ACCTINQ' TO GG-NAME1",
        "           CALL 'GGCPENT' USING GG-CICS.",
    ]


def test_return_xctl_and_abend_end_the_task():
    ret = ec.translate_command("RETURN TRANSID (LIT-TRAN) COMMAREA (WS-CA) LENGTH(LENGTH OF WS-CA)")
    assert ret[0] == "MOVE LIT-TRAN TO GG-NAME1" and ret[-1] == "GOBACK" and "    BY VALUE LENGTH OF WS-CA" in ret
    assert ec.translate_command("RETURN")[-3:] == ["    BY REFERENCE GG-FLAGS", "    BY VALUE 0", "GOBACK"]
    xctl = ec.translate_command("XCTL PROGRAM (WS-PGM) COMMAREA(CA)")
    assert xctl[:3] == ["MOVE WS-PGM TO GG-NAME1", "MOVE 1 TO GG-ITEM", "CALL 'GGCXCTL' USING GG-CICS"]
    # #4008: a failed XCTL (LENGERR, PGMIDERR) stays in the program, through the condition handling
    assert xctl[5:8] == ["IF GG-RESP = 0", "    GOBACK", "END-IF"] and "    CALL 'GGCCOND' USING GG-CICS" in xctl
    assert ec.translate_command("XCTL PROGRAM('P')")[1] == "MOVE 0 TO GG-ITEM"
    assert ec.translate_command("ABEND ABCODE('9999')")[0] == "MOVE '9999' TO GG-NAME1"


def test_send_map_records_its_options_and_area():
    got = ec.translate_command("SEND MAP(M) MAPSET(S) FROM(MO) CURSOR ERASE FREEKB")
    assert "MOVE 'CURSOR ERASE FREEKB' TO GG-FLAGS" in got and "    BY REFERENCE MO" in got


def test_a_terminal_receive_passes_its_length_in_and_takes_the_datas_length_back():
    """#4005: LENGTH is in-out -- in, the most INTO takes; out, the data's length (IBM, EXEC CICS RECEIVE)."""
    got = ec.translate_command("RECEIVE INTO(WS-INPUT) LENGTH(WS-INLEN)")
    assert got[:3] == ["MOVE WS-INLEN TO GG-LEN", "CALL 'GGCRECT' USING GG-CICS", "    BY REFERENCE WS-INPUT"]
    assert got[3] == "MOVE GG-LEN TO WS-INLEN" and got[-5] == "    CALL 'GGCCOND' USING GG-CICS"
    assert ec.translate_command("RECEIVE INTO(WS-I) LENGTH(WS-L) MAXLENGTH(30)")[0] == "MOVE 30 TO GG-LEN"
    omitted = ec.translate_command("RECEIVE INTO(WS-I) RESP(WS-R)")
    assert omitted[0] == "MOVE LENGTH OF WS-I TO GG-LEN" and "MOVE GG-RESP TO WS-R" in omitted
    assert not any(ln.startswith("MOVE GG-LEN") for ln in omitted)


def test_ts_commands_pass_length_item_and_numitems_in_and_out():
    """#4002: READQ's LENGTH is set back on NORMAL / LENGERR only; NEXT is item 0; WRITEQ's ITEM is set on
    NORMAL, unless REWRITE makes it an input."""
    got = ec.translate_command("READQ TS QUEUE('HCQ1') INTO(WS-ITEM) LENGTH(WS-ILEN) ITEM(WS-N) NUMITEMS(WS-K)")
    assert got[:4] == ["MOVE 'HCQ1' TO GG-QNAME", "MOVE WS-ILEN TO GG-LEN", "MOVE WS-N TO GG-ITEM",
                       "CALL 'GGCREADQ' USING GG-CICS"]  # fmt: skip
    assert got[5:11] == ["IF GG-RESP = 0 OR GG-RESP = 22", "    MOVE GG-LEN TO WS-ILEN", "END-IF",
                         "IF GG-RESP = 0", "    MOVE GG-NUM TO WS-K", "END-IF"]  # fmt: skip
    assert "MOVE 0 TO GG-ITEM" in ec.translate_command("READQ QUEUE(Q) INTO(X) LENGTH(L) NEXT")  # TS is the default
    assert ec.translate_command("READQ TS QNAME(Q) INTO(X) RESP(R)")[1] == "MOVE LENGTH OF X TO GG-LEN"
    w = ec.translate_command("WRITEQ TS QUEUE('Q') FROM(WS-ONE) LENGTH(1) ITEM(WS-I)")
    assert w[:4] == ["MOVE 'Q' TO GG-QNAME", "MOVE 1 TO GG-LEN", "MOVE 0 TO GG-ITEM", "MOVE SPACES TO GG-FLAGS"]
    # a LENGTH past the FROM item stops the run, refused by name (oracle_assumptions.md X6)
    assert w[4:9] == ["IF GG-LEN > LENGTH OF WS-ONE", "    DISPLAY 'WRITEQ TS LENGTH > FROM: not modelled'",
                      "    MOVE 98 TO RETURN-CODE", "    STOP RUN", "END-IF"]  # fmt: skip
    assert ["IF GG-RESP = 0", "    MOVE GG-ITEM TO WS-I", "END-IF"] == w[11:14]
    r = ec.translate_command("WRITEQ TS QUEUE('Q') FROM(A) ITEM(WS-I) REWRITE")
    assert r[2:4] == ["MOVE WS-I TO GG-ITEM", "MOVE 'REWRITE' TO GG-FLAGS"] and "    MOVE GG-ITEM TO WS-I" not in r


@pytest.mark.parametrize("body", ["READ FILE(F) RIDFLD(K) INTO(R) GENERIC", "READQ TS QUEUE(Q) SET(P) LENGTH(L)",
                                  "HANDLE ABEND PROGRAM('X')", "ASSIGN USERID(U)", "HANDLE CONDITION NOSUCH(X)",
                                  "WRITEQ TS QUEUE(Q) FROM(A) SYSID(S)", "WRITEQ TS QUEUE(Q) FROM(A) REWRITE",
                                  "READQ TD QUEUE(Q) INTO(A)",
                                  "RECEIVE INTO(X) LENGTH(L) NOTRUNCATE", "RECEIVE SET(P) LENGTH(L)", "STARTBR FILE(F) RIDFLD(K) REQID(1)",
                                  "DELETE FILE('X') RIDFLD(K) GENERIC KEYLENGTH(2)", "LINK PROGRAM('X') SYSID('S')"])  # fmt: skip
def test_an_unmodelled_command_is_refused_by_name(body):
    with pytest.raises(ec.Unsupported):
        ec.translate_command(body)


PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ACCTINQ.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-RESP                PIC S9(8) COMP.
       01  ACCT-REC               PIC X(20).
       01  WS-KEY                 PIC X(5).
       LINKAGE SECTION.
       01  DFHCOMMAREA            PIC X(10).
       PROCEDURE DIVISION.
       MAIN-PARA.
           MOVE DFHCOMMAREA(1:5) TO WS-KEY
           EXEC CICS READ FILE('ACCT') RIDFLD(WS-KEY)
                INTO(ACCT-REC) RESP(WS-RESP)
           END-EXEC.
           IF WS-RESP = DFHRESP(NOTFND)
              MOVE SPACES TO ACCT-REC
           END-IF
           EXEC CICS RETURN END-EXEC.
"""


def test_a_program_is_translated_whole():
    text, has_commarea = ec.translate(PROGRAM)
    assert has_commarea
    assert "       COPY DFHEIBLK." in text and "PROCEDURE DIVISION USING DFHCOMMAREA." in text
    assert "IF WS-RESP = 13" in text and "EXEC CICS" not in text
    assert all(len(line) <= 72 for line in text.splitlines())


def test_an_unknown_command_in_a_program_names_its_line():
    with pytest.raises(ec.Unsupported, match="line 13: EXEC CICS READQ TD"):
        ec.translate(PROGRAM.replace("READ FILE('ACCT') RIDFLD(WS-KEY)", "READQ TD QUEUE('CSSL') INTO(WS-KEY)"))


CSD = """\
 DEFINE FILE(ACCT) GROUP(APP) DSNAME(APP.ACCT.KSDS)
 DEFINE FILE(ACCTAIX) GROUP(APP) DSNAME(APP.ACCT.PATH)
"""
# IDCAMS reads columns 2-72: a longer statement continues with "-", as real decks do.
IDCAMS = """\
//DEFINE   JOB (ACCT),'DEFINE'
//STEP1    EXEC PGM=IDCAMS
//SYSIN    DD *
  DEFINE CLUSTER (NAME(APP.ACCT.KSDS) INDEXED -
         KEYS(5 0) RECORDSIZE(20 20))
  DEFINE ALTERNATEINDEX (NAME(APP.ACCT.AIX) -
         RELATE(APP.ACCT.KSDS) KEYS(4 5) NONUNIQUEKEY)
  DEFINE PATH (NAME(APP.ACCT.PATH) PATHENTRY(APP.ACCT.AIX))
/*
"""


@pytest.fixture(scope="module")
def scanned(tmp_path_factory):
    base = tmp_path_factory.mktemp("cics_harness")
    repo = base / "estate"
    program = PROGRAM.replace("RETURN END-EXEC.", "READ FILE('ACCTAIX') RIDFLD(WS-KEY) INTO(ACCT-REC)\n"
                                                  "                RESP(WS-RESP) END-EXEC.\n"
                                                  "           EXEC CICS RETURN END-EXEC.")  # fmt: skip
    for rel, text in {"cbl/ACCTINQ.cbl": program, "csd/APP.csd": CSD, "jcl/DEFINE.jcl": IDCAMS}.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    return load_galaxy_ir(scan_to_db(repo, base / "scan"))


def test_the_stub_file_table_comes_from_the_engines_facts(scanned):
    files = {f["file"]: f for f in ec.stub_files(scanned, "cbl/ACCTINQ.cbl")}
    assert files["ACCT"] == {"file": "ACCT", "dsname": "APP.ACCT.KSDS", "base": "APP.ACCT.KSDS", "key_offset": 0,
                             "key_length": 5, "reclen": 20, "via": []}  # fmt: skip
    aix = files["ACCTAIX"]
    assert (aix["base"], aix["key_offset"], aix["key_length"]) == ("APP.ACCT.KSDS", 5, 4)
    assert aix["via"] == ["PATH APP.ACCT.PATH", "AIX APP.ACCT.AIX"]


def test_fields_round_trip_through_their_storage():
    for value, pic, usage, n in [("12.34", "S9(5)V99", None, 7), ("-5", "S9(3)", "COMP-3", 2),
                                 ("300", "S9(4)", "COMP", 2), ("AB", "X(4)", None, 4), ("7", "9(1)", None, 1)]:  # fmt: skip
        raw = ec.encode_field(value, pic, usage, n)
        assert len(raw) == n
        back = eq.decode_field(raw, pic, usage)
        assert (back.rstrip() == value) if isinstance(back, str) else back == Decimal(value)


def test_map_input_sets_the_typed_field_and_its_length():
    fields = [{"name": "ACCTL", "offset": 0, "bytes": 2, "pic": "S9(4)", "usage": "COMP"},
              {"name": "ACCTF", "offset": 2, "bytes": 1, "pic": "X", "usage": None},
              {"name": "ACCTI", "offset": 3, "bytes": 5, "pic": "99999", "usage": None}]  # fmt: skip
    assert ec.map_input(fields, {"ACCTI": "ABC"}) == b"\x00\x03\x00ABC  "


def test_a_dtos_shape_is_read_from_its_comments(tmp_path):
    (tmp_path / "Part.java").write_text("public class Part {\n    // CA-ID: PIC 9(4), offset 0, 4 bytes (x.cpy)\n"
                                        "    private Integer caId;\n}\n")  # fmt: skip
    (tmp_path / "Whole.java").write_text("public class Whole {\n    // DFHCOMMAREA(1:4) at line 9: offset 0, 4 bytes"
                                         " -> CA-PART (x.cpy)\n    private Part caPart;\n}\n")  # fmt: skip
    shape = ec.dto_shape(tmp_path, "Whole")
    assert shape == {"caPart": ("Part", {"caId": "CA-ID"})}
    assert ec.to_java({"CA-ID": "12"}, shape) == {"caPart": {"caId": 12}}
    assert ec.from_java({"caPart": {"caId": 12}}, shape) == {"CA-ID": 12}


def test_a_dto_is_found_by_its_package_not_its_simple_name(tmp_path):
    """#4011: entity/PcwizWsState and dto/contract/PcwizWsState share a simple name. The contract
    DTO is found by its qualified name, or from the service that imports it; a bare simple name
    with nothing to choose between the two is refused instead of picking the entity."""
    pkg = tmp_path / "com/x"
    for d in ("entity", "dto/contract", "service"):
        (pkg / d).mkdir(parents=True)
    (pkg / "entity/PcwizWsState.java").write_text(
        "package com.x.entity;\npublic class PcwizWsState {\n    private Long id;\n}\n"
    )
    (pkg / "dto/contract/PcwizWsState.java").write_text(
        "package com.x.dto.contract;\npublic class PcwizWsState {\n"
        "    // WS-STEP: PIC 9, offset 0, 1 bytes (x.cpy)\n    private Integer wsStep;\n"
        "    // WS-STATE(2:4) at line 9: offset 1, 4 bytes -> WS-PART (x.cpy)\n    private PcwizPart wsPart;\n}\n"
    )
    (pkg / "dto/contract/PcwizPart.java").write_text(
        "package com.x.dto.contract;\npublic class PcwizPart {\n"
        "    // WS-NAME: PIC X(4), offset 1, 4 bytes (x.cpy)\n    private String wsName;\n}\n"
    )
    (pkg / "service/PcwizService.java").write_text(
        "package com.x.service;\nimport com.x.dto.contract.PcwizWsState;\npublic class PcwizService {}\n"
    )
    want = {"wsStep": "WS-STEP", "wsPart": ("PcwizPart", {"wsName": "WS-NAME"})}
    assert ec.dto_shape(tmp_path, "com.x.dto.contract.PcwizWsState") == want
    assert ec.dto_shape(tmp_path, "PcwizWsState", pkg / "service/PcwizService.java") == want
    (pkg / "service/PcwizService.java").write_text(
        "package com.x.service;\nimport com.x.dto.contract.*;\npublic class PcwizService {}\n"
    )
    assert ec.dto_shape(tmp_path, "PcwizWsState", pkg / "service/PcwizService.java") == want
    with pytest.raises(LookupError, match="PcwizWsState is ambiguous"):
        ec.dto_shape(tmp_path, "PcwizWsState")
    with pytest.raises(LookupError, match="no generated class"):
        ec.dto_shape(tmp_path, "com.x.dto.contract.Nope")


def test_events_are_compared_field_by_field():
    cobol = [{"event": "SEND-MAP", "map": "M", "screen": {"NAME": "Ann", "BAL": "+   1.00"}},
             {"event": "RETURN", "transid": "T1", "commarea": {"CA-CTX": "1"}}]  # fmt: skip
    java = [{"event": "SEND-MAP", "map": "M", "screen": {"NAME": "Ann  ", "BAL": "+1.00"}},
            {"event": "RETURN", "transid": "T1", "commarea": {"CA-CTX": 1}}]  # fmt: skip
    d = ec.compare_events(cobol, java)
    assert (d["equal"], d["events"]) == (1, 2)
    assert d["diffs"] == [{"event": 1, "kind": "SEND-MAP",
                           "fields": [{"field": "screen.BAL", "cobol": "+   1.00", "java": "+1.00"}]}]  # fmt: skip
    assert ec.compare_events(cobol, java[:1])["diffs"][-1] == {"event": 2, "cobol": "RETURN", "java": None}


@pytest.mark.skipif(__import__("os").environ.get("EQUIVALENCE_E2E") != "1",
                    reason="needs Docker (GnuCOBOL) and a JDK + Maven")  # fmt: skip
def test_carddemo_account_view_is_equivalent_end_to_end(tmp_path):
    """COACTVWC as COBOL under the stub runtime and as the generated Java plus the case's port: every
    scenario's every event (screen, COMMAREA, XCTL) equal, field by field."""
    import json
    import subprocess

    proc = subprocess.run([sys.executable, str(Path(eq.__file__)), "run", "carddemo-acctview", "--keep",  # noqa: S603
                           str(tmp_path)], capture_output=True, text=True, check=False)  # fmt: skip
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-3000:]
    report = json.loads((tmp_path / "report.json").read_text())
    # #4009: a scenario that types into the screen also compares its RECEIVE MAP (CicsTask records it)
    # (the case's fault-injected scenarios -- an I/O error, a disabled file -- are compared too: all of them equal)
    got = {n: (o["equal"], o["records"]) for n, o in report["outputs"].items()}
    assert all(e == r for e, r in got.values()), got
    assert {"enter-from-menu": (2, 2), "view-account": (3, 3), "account-not-on-file": (3, 3),
            "account-not-numeric": (3, 3), "pf3-back-to-menu": (1, 1)}.items() <= got.items()  # fmt: skip


# ---- file updates: WRITE, REWRITE, READ UPDATE, SYNCPOINT (CardDemo's update programs) -----------------------
def test_file_updates_translate_to_stub_calls():
    upd = ec.translate_command("READ DATASET(WS-F) INTO(R) RIDFLD(K) UPDATE RESP(X)")
    assert upd[:3] == ["MOVE WS-F TO GG-NAME1", "MOVE 'UPDATE' TO GG-FLAGS", "CALL 'GGCREAD' USING GG-CICS"]
    w = ec.translate_command("WRITE DATASET(F) FROM(REC) RIDFLD(K) RESP(X)")
    assert w[:2] == ["MOVE F TO GG-NAME1", "CALL 'GGCWRIT' USING GG-CICS"] and "    BY REFERENCE REC" in w
    rw = ec.translate_command("REWRITE FILE(F) FROM(REC) RESP(X) RESP2(Y)")
    assert rw[:2] == ["MOVE F TO GG-NAME1", "CALL 'GGCREWR' USING GG-CICS"]
    assert ec.translate_command("SYNCPOINT")[:2] == ["MOVE SPACES TO GG-FLAGS", "CALL 'GGCSYNC' USING GG-CICS"]
    assert ec.translate_command("SYNCPOINT ROLLBACK")[0] == "MOVE 'ROLLBACK' TO GG-FLAGS"
    for bad in ("WRITE FILE(F) FROM(R) RIDFLD(K) MASSINSERT", "REWRITE FILE(F) FROM(R) SYSID(S)"):
        with pytest.raises(ec.Unsupported):
            ec.translate_command(bad)
    sc = {"faults": [{"cmd": "REWRITE", "file": "ACCTDAT", "resp": "NOTOPEN"}]}
    assert ec.fault_lines(sc) == ["REWRITE ACCTDAT 1 19 0"]


def test_a_tasks_files_are_compared_in_key_order():
    files = [{"base": "ACCT", "reclen": 6, "key_offset": 0, "key_length": 2}]
    case = {"datasets": {"ACCT": {}}}

    def compare(cobol, java, tmp):
        (tmp / "s.ACCT.out").write_bytes(java)
        return ec.compare_files(case, Path("."), files, {"ACCT": cobol}, tmp, "s")

    import tempfile

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        assert compare(b"02BBBB01AAAA", b"01AAAA02BBBB", tmp) == {}  # the order a store keeps is not data
        diff = compare(b"01AAAA02BBBB", b"01AAAA02BBBX", tmp)
        assert diff["ACCT"]["equal"] == 1 and diff["ACCT"]["records"] == 2
        assert compare(b"01AAAA02BBBB03CCCC", b"01AAAA02BBBB", tmp)["ACCT"]["equal"] == 2  # a WRITE the port missed


def test_a_case_csd_defines_the_programs_and_no_csd_defines_all(tmp_path):
    (tmp_path / "x.csd").write_text(" DEFINE PROGRAM(COMEN01C) GROUP(G)\n DEFINE  PROGRAM(COUSR00C)\n"
                                    " DEFINE TRANSACTION(CM00) PROGRAM(COMEN01C)\n", encoding="ascii")  # fmt: skip
    assert ec.csd_programs(tmp_path, {"csd": "x.csd"}) == ["COMEN01C", "COUSR00C"]
    assert ec.csd_programs(tmp_path, {}) is None
    # the Java side (CicsTask.withPrograms) is proven by carddemo-adminmenu: options 5 and 6 are PGMIDERR on both


def test_browse_delete_and_time_commands_translate():
    assert ec.translate_command("STARTBR DATASET(F) RIDFLD(K) EQUAL RESP(R)")[:3] == [
        "MOVE F TO GG-NAME1",
        "MOVE 'EQUAL' TO GG-FLAGS",
        "CALL 'GGCSTBR' USING GG-CICS",
    ]
    assert ec.translate_command("READPREV DATASET(F) INTO(REC) RIDFLD(K) RESP(R)")[2] == "CALL 'GGCRDPV' USING GG-CICS"
    assert ec.translate_command("DELETE FILE(F) RESP(R)")[1] == "MOVE 'HELD' TO GG-FLAGS"  # the READ UPDATE's record
    for bad in (
        "STARTBR FILE(F) RIDFLD(K) GENERIC KEYLENGTH(2)",
        "READNEXT FILE(F) INTO(R) RIDFLD(K) REQID(1)",
        "FORMATTIME ABSTIME(T) DAYOFWEEK(D)",
    ):
        with pytest.raises(ec.Unsupported):
            ec.translate_command(bad)
    long_names = "FORMATTIME ABSTIME(WS-ABS-TIME) YYYYMMDD(WS-CUR-DATE-X10) DATESEP('-') TIME(WS-T) TIMESEP"
    for cmd in ("ASKTIME ABSTIME(WS-ABS-TIME)", long_names):  # each statement fits area B (col 12-72)
        assert all(len(s) <= 61 for s in ec.translate_command(cmd))


def test_an_alphanumeric_commarea_field_reaches_the_port_as_text():
    """CardDemo's CDEMO-CT01-TRN-SELECTED (PIC X(16)) '0000000000683580' reached the port as the number 683580."""
    fields = [{"name": "SEL", "pic": "X(16)"}, {"name": "PAGE", "pic": "9(08)"}, {"name": "AMT", "pic": "S9(5)V99"}]
    shape = {"sel": "SEL", "page": "PAGE", "amt": "AMT"}
    got = ec.to_java({"SEL": "0000000000683580", "PAGE": "00000002", "AMT": "12.50"}, shape, ec.alphanumeric(fields))
    assert got == {"sel": "0000000000683580", "page": 2, "amt": 12.5}


def test_a_repeat_count_with_a_nine_is_not_a_digit_position():
    """COACTUPC's ACUP-OLD-CUST-SSN-X (PIC X(09)) '017590544' reached the port as the number 17590544: the 9 of the
    repetition count read as a numeric PICTURE symbol -- the port then saw another record than COBOL's."""
    fields = [{"name": "SSN", "pic": "X(09)"}, {"name": "ID", "pic": "X(19)"}, {"name": "N", "pic": "9(09)"}]
    assert ec.alphanumeric(fields) == frozenset({"SSN", "ID"})
    got = ec.to_java({"SSN": "017590544", "N": "000000042"}, {"ssn": "SSN", "n": "N"}, ec.alphanumeric(fields))
    assert got == {"ssn": "017590544", "n": 42}


def test_assign_applid_sysid_and_writeq_td_translate():
    got = ec.translate_command("ASSIGN APPLID(A) SYSID(S)")
    assert got[:3] == ["MOVE 'APPLID' TO GG-NAME2", "CALL 'GGCASGN' USING GG-CICS", "MOVE GG-NAME1(1:8) TO A"]
    assert got[3:6] == ["MOVE 'SYSID' TO GG-NAME2", "CALL 'GGCASGN' USING GG-CICS", "MOVE GG-NAME1(1:4) TO S"]
    td = ec.translate_command("WRITEQ TD QUEUE('JOBS') FROM(REC) RESP(R)")
    assert td[:4] == ["MOVE 'JOBS' TO GG-QNAME", "MOVE LENGTH OF REC TO GG-LEN", "CALL 'GGCWRTD' USING GG-CICS",
                      "    BY REFERENCE REC"]  # fmt: skip
    with pytest.raises(ec.Unsupported):
        ec.translate_command("ASSIGN USERID(U)")


def test_an_esds_browse_by_rba_translates_and_the_rest_of_rba_is_refused():
    """#4213 (IBM DBB EPSMLIST): STARTBR / READNEXT / READPREV ... RBA reach the stub with 'RBA' in GG-FLAGS.
    IBM, EXEC CICS STARTBR: EQUAL "is the default for a direct ESDS browse" and GTEQ "is not valid for directly
    browsing an ESDS", so an RBA browse is EQUAL and GTEQ with RBA is refused; READ / WRITE / DELETE by RBA, XRBA,
    RRN and KEYLENGTH with RBA are not modelled (refused by name)."""
    assert ec.translate_command("STARTBR DATASET('EPSMORTF') RIDFLD(RID-LENGTH) RBA EQUAL RESP(R)")[:3] == [
        "MOVE 'EPSMORTF' TO GG-NAME1",
        "MOVE 'EQUAL RBA' TO GG-FLAGS",
        "CALL 'GGCSTBR' USING GG-CICS",
    ]
    assert ec.translate_command("STARTBR FILE(F) RIDFLD(K) RBA RESP(R)")[1] == "MOVE 'EQUAL RBA' TO GG-FLAGS"
    for verb, stub in (("READNEXT", "GGCRDNX"), ("READPREV", "GGCRDPV")):
        assert ec.translate_command(f"{verb} FILE(F) INTO(REC) RIDFLD(K) RBA RESP(R)")[:3] == [
            "MOVE F TO GG-NAME1",
            "MOVE 'RBA' TO GG-FLAGS",
            f"CALL '{stub}' USING GG-CICS",
        ]
        # a keyed READNEXT says so too: GG-FLAGS is not left as the last command set it
        assert ec.translate_command(f"{verb} FILE(F) INTO(REC) RIDFLD(K) RESP(R)")[1] == "MOVE SPACES TO GG-FLAGS"
    for bad in (
        "STARTBR FILE(F) RIDFLD(K) RBA GTEQ",
        "STARTBR FILE(F) RIDFLD(K) RBA KEYLENGTH(4)",
        "STARTBR FILE(F) RIDFLD(K) XRBA",
        "STARTBR FILE(F) RIDFLD(K) RRN",
        "READNEXT FILE(F) INTO(R) RIDFLD(K) XRBA",
        "READPREV FILE(F) INTO(R) RIDFLD(K) RRN",
        "READNEXT FILE(F) INTO(R) RIDFLD(K) RBA KEYLENGTH(4)",
        "READ FILE(F) INTO(R) RIDFLD(K) RBA",
        "WRITE FILE(F) FROM(R) RIDFLD(K) RBA",
        "DELETE FILE(F) RIDFLD(K) RBA",
    ):
        with pytest.raises(ec.Unsupported):
            ec.translate_command(bad)


class _NoDefineIR:
    """An estate whose CICS file has no CSD DEFINE FILE (IBM DBB MortgageApplication's EPSMORTF)."""

    files: dict = {}

    @staticmethod
    def cics_file_lineage():
        return [{"program": "p.cbl", "name": "EPSMORTF", "definitions": []}]


def test_a_case_states_an_esds_the_estate_does_not_define():
    """#4213: with no CSD DEFINE FILE nor IDCAMS DEFINE in the estate, the case's dataset may state the file
    (`csd`: organization ESDS, reclen, why) -- a deployment fact, as `recovery` is. Anything else stays refused."""
    csd = {"organization": "ESDS", "reclen": 56, "why": "stated"}
    assert ec.stub_files(_NoDefineIR(), "p.cbl", {"EPSMORTF": {"csd": csd}}) == [
        {
            "file": "EPSMORTF",
            "dsname": "EPSMORTF",
            "base": "EPSMORTF",
            "key_offset": 0,
            "key_length": 0,
            "reclen": 56,
            "via": ["the case's csd"],
            "organization": "ESDS",
        }  # fmt: skip
    ]
    with pytest.raises(ec.Unsupported):
        ec.stub_files(_NoDefineIR(), "p.cbl", {})
    for wrong in ({"organization": "KSDS", "reclen": 56, "why": "x"}, {"organization": "ESDS", "why": "x"},
                  {"organization": "ESDS", "reclen": 56}):  # fmt: skip
        with pytest.raises(ec.Unsupported):
            ec.stub_files(_NoDefineIR(), "p.cbl", {"EPSMORTF": {"csd": wrong}})


def test_an_esds_is_compared_in_arrival_order():
    """#4213: an ESDS has no key -- its records' order is their RBAs, so it is data and is compared as it is."""
    files = [{"base": "LOG", "reclen": 2, "key_offset": 0, "key_length": 0, "organization": "ESDS"}]
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        (tmp / "s.LOG.out").write_bytes(b"BBAA")
        diff = ec.compare_files({"datasets": {"LOG": {}}}, Path("."), files, {"LOG": b"AABB"}, tmp, "s")
        assert diff["LOG"]["equal"] == 0 and diff["LOG"]["records"] == 2
