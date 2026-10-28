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

from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir  # noqa: E402
from scan_server import scan_to_db  # noqa: E402


def test_a_read_becomes_a_stub_call_and_its_resp_is_the_programs():
    got = ec.translate_command(" READ DATASET (LIT-ACCTFILENAME) RIDFLD (WS-KEY) KEYLENGTH (LENGTH OF WS-KEY)"
                               " INTO (ACCOUNT-RECORD) RESP (WS-RESP-CD) RESP2 (WS-REAS-CD) ")  # fmt: skip
    assert got[:4] == ["MOVE LIT-ACCTFILENAME TO GG-NAME1", "MOVE 'KEYLENGTH' TO GG-FLAGS",  # not UPDATE: holds nothing; a given KEYLENGTH (#5092)
                       "MOVE LENGTH OF ACCOUNT-RECORD TO GG-LEN", "CALL 'GGCREAD' USING GG-CICS"]  # fmt: skip
    assert "    BY VALUE LENGTH OF WS-KEY" in got and "    BY REFERENCE ACCOUNT-RECORD" in got
    assert got[-2:] == ["MOVE GG-RESP TO WS-RESP-CD", "MOVE GG-RESP2 TO WS-REAS-CD"]


def test_a_reads_length_goes_in_and_comes_back():
    """#4436 (GenApp LGUCVS01: LENGTH(WS-Commarea-Len)): IBM, EXEC CICS READ -- LENGTH is the most INTO takes (a
    longer record is truncated, LENGERR) and is set to the record's length, on NORMAL and LENGERR only. Before, the
    stub was given LENGTH OF INTO and LENGTH was never set. A literal / LENGTH OF has nothing to set back."""
    got = ec.translate_command("READ FILE('KSDSCUST') INTO(WS-AREA) LENGTH(WS-LEN) RIDFLD(K) KEYLENGTH(10) RESP(R)")
    assert got[2:4] == ["MOVE WS-LEN TO GG-LEN", "CALL 'GGCREAD' USING GG-CICS"]
    assert "    BY VALUE LENGTH OF WS-AREA" in got  # the stub refuses a record moved past INTO
    at = got.index("IF GG-RESP = 0 OR GG-RESP = 22")
    assert got[at : at + 4] == ["IF GG-RESP = 0 OR GG-RESP = 22", "    MOVE GG-LEN TO WS-LEN", "END-IF",
                                "MOVE GG-RESP TO EIBRESP"]  # fmt: skip
    lit = ec.translate_command("READ FILE(F) INTO(A) LENGTH(10) RIDFLD(K) RESP(R)")
    assert "MOVE 10 TO GG-LEN" in lit and not any(ln.startswith("    MOVE GG-LEN") for ln in lit)


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
                                                                "MOVE GG-NAME1(1:4) TO WS-AB(1:4)"]  # fmt: skip
    abend = ec.translate_command("ABEND ABCODE('HCX1')", ["SUB-ABEND"])
    assert abend[:3] == ["MOVE 'HCX1' TO GG-NAME1", "MOVE SPACES TO GG-FLAGS", "CALL 'GGCABND' USING GG-CICS"]
    assert abend[3:] == ["GO TO", "    SUB-ABEND", "    DEPENDING ON GG-GOTO", "GOBACK"]
    assert ec.translate_command("ABEND ABCODE('X') CANCEL")[1] == "MOVE 'CANCEL' TO GG-FLAGS"


def test_a_link_runs_a_new_level_on_the_callers_own_commarea():
    """#4004: GGCLINK checks and records the LINK; on NORMAL, GGCRUN runs the target on the caller's area (by
    reference) and GGCLRET pops the level, where an abend exit up here can take over; a failed LINK goes
    through the condition handling."""
    got = ec.translate_command("LINK PROGRAM('CASUB') COMMAREA(WS-CA100) LENGTH(100)", ["MAIN-ABEND"])
    assert got[:5] == ["MOVE 'CASUB' TO GG-NAME1", "MOVE 100 TO GG-LEN", "MOVE 1 TO GG-ITEM",
                       "MOVE SPACES TO GG-FLAGS", "CALL 'GGCLINK' USING GG-CICS"]  # fmt: skip
    assert got[12:19] == ["IF GG-RESP = 0", "    CALL 'GGCRUN' USING WS-CA100", "    CALL 'GGCLRET' USING GG-CICS",
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
    assert r[:6] == ["MOVE 'INTO' TO GG-FLAGS", "MOVE WS-LEN TO GG-LEN", "CALL 'GGCRTRV' USING GG-CICS",
                     "    BY REFERENCE WS-DATA", "IF GG-RESP = 0 OR GG-RESP = 22", "    MOVE GG-LEN TO WS-LEN"]  # fmt: skip
    assert ec.translate_command("CANCEL REQID('GTREQ001')")[:2] == ["MOVE 'GTREQ001' TO GG-QNAME",
                                                                   "CALL 'GGCCNCL' USING GG-CICS"]  # fmt: skip
    for body in ("CANCEL", "START INTERVAL(0)", "START TRANSID('X') SYSID('R')",
                 "START TRANSID('X') AFTER", "START TRANSID('X') HOURS(1)", "START TRANSID('X') INTERVAL(1) AT HOURS(1)",
                 "RETRIEVE LENGTH(L)", "RETRIEVE RTRANSID(T) LENGTH(L)", "RETRIEVE INTO(A) WAIT"):  # fmt: skip
        with pytest.raises(ec.Unsupported):
            ec.translate_command(body)


def test_start_after_at_and_the_data_options_become_stub_calls():
    """#4270 slice 2: AFTER / AT HOURS / MINUTES / SECONDS go to GG-HOURS / GG-MINS / GG-SECS (-999999999: not
    given), RTRANSID / RTERMID / QUEUE to GG-RTRAN / GG-RTERM / GG-RQUEUE, each named in GG-FLAGS; RETRIEVE moves the
    values asked for back on NORMAL / LENGERR only, and may name no INTO."""
    got = ec.translate_command("START TRANSID('GT02') AFTER MINUTES(1) RTRANSID('GT03') QUEUE(WS-Q) RESP(R)")
    assert got[:10] == ["MOVE 'GT02' TO GG-NAME1", "MOVE SPACES TO GG-NAME2", "MOVE SPACES TO GG-QNAME",
                        "MOVE 0 TO GG-NUM", "MOVE 'AFTER RTRANSID QUEUE' TO GG-FLAGS", "MOVE 0 TO GG-LEN",
                        "MOVE 0 TO GG-ITEM", "MOVE -999999999 TO GG-HOURS", "MOVE 1 TO GG-MINS",
                        "MOVE -999999999 TO GG-SECS"]  # fmt: skip
    assert got[10:12] == ["MOVE 'GT03' TO GG-RTRAN", "MOVE WS-Q TO GG-RQUEUE"]
    at = ec.translate_command("START TRANSID('GT02') AT HOURS(H) SECONDS(30) FROM(A) LENGTH(N) PROTECT")
    assert "MOVE 'AT PROTECT' TO GG-FLAGS" in at and "MOVE H TO GG-HOURS" in at and "IF GG-LEN > LENGTH OF A" in at
    r = ec.translate_command("RETRIEVE RTRANSID(WS-T) RTERMID(WS-M) RESP(R)")
    assert r[:4] == ["MOVE 'RTRANSID RTERMID' TO GG-FLAGS", "MOVE 0 TO GG-LEN", "CALL 'GGCRTRV' USING GG-CICS",
                     "    BY REFERENCE GG-FLAGS"]  # fmt: skip
    assert r[4:8] == ["IF GG-RESP = 0 OR GG-RESP = 22", "    MOVE GG-RTRAN TO WS-T", "    MOVE GG-RTERM TO WS-M",
                      "END-IF"]  # fmt: skip


def test_the_task_driver_and_dispatcher_are_generated_for_the_cases_programs():
    run = ec.task_dispatcher({"CALINK": False, "CASUB": True})
    assert "PROGRAM-ID. GGCRUN RECURSIVE." in run and "LOCAL-STORAGE SECTION." in run
    assert "            CALL 'CASUB' USING LK-X\n" in run and "            CALL 'CALINK'\n" in run
    assert "            CANCEL 'CASUB'\n" in run and "CALL 'GGCNOPG' USING GG-CICS" in run
    drv = ec.task_driver()
    assert "CALL 'GGCTASK' USING GG-CICS" in drv and "CALL 'GGCRUN' USING WS-CA" in drv
    assert "MOVE IN-TRMID TO EIBTRMID" in drv
    for d in (drv, ec.cics_driver("PROG", False)):  # #4270: EIBTASKN from the stub ($GGCICS_TASKN)
        assert "CALL 'GGCTASKN' USING GG-CICS\n           MOVE GG-NUM TO EIBTASKN" in d
    assert all(len(ln) <= 72 for ln in (run + drv).splitlines())


def test_handle_aid_labels_are_taken_after_an_input_command():
    """#4007: HANDLE AID registers each key's label; RECEIVE MAP / RECEIVE then GO TO the pressed key's label
    (GGCAID) when they completed normally, unless RESP or NOHANDLE suspends the handlers."""
    labels = ["MENU-EXIT", "MENU-REFRESH"]
    assert ec.translate_command("HANDLE AID PF3(MENU-EXIT) PF5(MENU-REFRESH) PF9", labels) == [
        "MOVE 'PF3' TO GG-NAME1", "MOVE 1 TO GG-ITEM", "CALL 'GGCHAID' USING GG-CICS",
        "MOVE 'PF5' TO GG-NAME1", "MOVE 2 TO GG-ITEM", "CALL 'GGCHAID' USING GG-CICS",
        "MOVE 'PF9' TO GG-NAME1", "MOVE -1 TO GG-ITEM", "CALL 'GGCHAID' USING GG-CICS"]  # fmt: skip
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


def test_an_input_command_refuses_an_aid_label_beside_a_condition_and_ignore_error_is_refused():
    """#4414: GGCAID is called first with the condition an input command raised (it records AID-REFUSED when a label
    applies to the key: which CICS acts on first is not documented), then as before. RECEIVE SET consults HANDLE AID
    too. IGNORE CONDITION ERROR is refused: whether ERROR's action can be to ignore is not documented."""
    labels = ["MENU-EXIT"]
    for body in ("RECEIVE MAP('M') INTO(X)", "RECEIVE INTO(X) LENGTH(L)",
                 "RECEIVE SET(ADDRESS OF LS-X) LENGTH(L) MAXLENGTH(80)"):  # fmt: skip
        out = ec.translate_command(body, labels, handle_aid=True)
        first = out.index("IF GG-RESP NOT = 0")
        assert out[first : first + 4] == ["IF GG-RESP NOT = 0", "    MOVE EIBAID TO GG-NAME1",
                                          "    CALL 'GGCAID' USING GG-CICS", "END-IF"]  # fmt: skip
        assert out.index("MOVE GG-RESP TO EIBRESP") > first and "IF GG-RESP = 0" in out
    assert "IF GG-RESP NOT = 0" not in ec.translate_command("RECEIVE INTO(X) LENGTH(L) RESP(R)", labels, True)
    assert ec.translate_command("IGNORE CONDITION LENGERR", []) == [
        "MOVE 22 TO GG-NUM", "MOVE -1 TO GG-ITEM", "CALL 'GGCHCND' USING GG-CICS"]  # fmt: skip
    with pytest.raises(ec.Unsupported, match="IGNORE CONDITION ERROR"):
        ec.translate_command("IGNORE CONDITION ERROR", [])


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
    assert xctl[:4] == ["MOVE WS-PGM TO GG-NAME1", "MOVE 1 TO GG-ITEM", "MOVE SPACES TO GG-FLAGS",
                        "CALL 'GGCXCTL' USING GG-CICS"]  # fmt: skip
    # #4008: a failed XCTL (LENGERR, PGMIDERR) stays in the program, through the condition handling
    assert xctl[6:9] == ["IF GG-RESP = 0", "    GOBACK", "END-IF"] and "    CALL 'GGCCOND' USING GG-CICS" in xctl
    assert ec.translate_command("XCTL PROGRAM('P')")[1] == "MOVE 0 TO GG-ITEM"
    assert ec.translate_command("ABEND ABCODE('9999')")[0] == "MOVE '9999' TO GG-NAME1"


def test_channels_and_containers_become_stub_calls():
    """#4270: PUT / GET / DELETE CONTAINER -> GGCPUTC / GGCGETC / GGCDELC with the container in GG-QNAME, the channel
    in GG-CHAN (GG-FLAGS CHANNEL; none: the current channel), the data type / APPEND / NODATA in GG-FLAGS and FLENGTH
    in GG-LEN -- set back on NORMAL / LENGERR only (IBM, GET CONTAINER (CHANNEL)); LINK / XCTL CHANNEL pass the
    channel; ASSIGN CHANNEL reads it back. The CCSID options and SET are refused by name; RETURN CHANNEL: see
    test_return_channel_becomes_a_stub_call."""
    put = ec.translate_command("PUT CONTAINER('REQ') CHANNEL(WS-CH) FROM(WS-A) FLENGTH(WS-N) CHAR APPEND RESP(R)")
    assert put[:5] == ["MOVE 'REQ' TO GG-QNAME", "MOVE WS-CH TO GG-CHAN", "MOVE 'CHANNEL CHAR APPEND' TO GG-FLAGS",
                       "MOVE WS-N TO GG-LEN", "IF GG-LEN > LENGTH OF WS-A"]  # fmt: skip
    assert "CALL 'GGCPUTC' USING GG-CICS" in put and "MOVE GG-RESP TO R" in put
    bit = ec.translate_command("PUT CONTAINER(C) FROM(WS-A) DATATYPE(DFHVALUE(BIT))")
    assert bit[1:4] == ["MOVE SPACES TO GG-CHAN", "MOVE 'BIT' TO GG-FLAGS", "MOVE LENGTH OF WS-A TO GG-LEN"]
    get = ec.translate_command("GET CONTAINER(C) INTO(WS-A) FLENGTH(WS-N) RESP(R) RESP2(R2)")
    i = get.index("CALL 'GGCGETC' USING GG-CICS")
    assert get[i + 2 : i + 5] == ["IF GG-RESP = 0 OR GG-RESP = 22", "    MOVE GG-LEN TO WS-N", "END-IF"]
    nodata = ec.translate_command("GET CONTAINER(C) NODATA FLENGTH(WS-N)")
    assert "MOVE 'NODATA' TO GG-FLAGS" in nodata and "MOVE 0 TO GG-LEN" in nodata
    assert ec.translate_command("DELETE CONTAINER(C) CHANNEL('CH')")[:4] == [
        "MOVE C TO GG-QNAME",
        "MOVE 'CH' TO GG-CHAN",
        "MOVE 'CHANNEL' TO GG-FLAGS",
        "CALL 'GGCDELC' USING GG-CICS",
    ]
    link = ec.translate_command("LINK PROGRAM('SUB') CHANNEL(WS-CH)")
    assert link[:6] == ["MOVE 'SUB' TO GG-NAME1", "MOVE 0 TO GG-LEN", "MOVE 0 TO GG-ITEM", "MOVE 'CHANNEL' TO GG-FLAGS",
                        "MOVE WS-CH TO GG-CHAN", "CALL 'GGCLINK' USING GG-CICS"]  # fmt: skip
    xctl = ec.translate_command("XCTL PROGRAM('XB') CHANNEL(WS-CH)")
    assert xctl[2:5] == ["MOVE 'CHANNEL' TO GG-FLAGS", "MOVE WS-CH TO GG-CHAN", "CALL 'GGCXCTL' USING GG-CICS"]
    assert ec.translate_command("ASSIGN CHANNEL(WS-CUR)")[:2] == ["CALL 'GGCASCH' USING GG-CICS",
                                                                 "MOVE GG-CHAN TO WS-CUR"]  # fmt: skip
    for bad in (
        "GET CONTAINER(C) INTO(A) INTOCODEPAGE('UTF-8')",
        "PUT CONTAINER(C) FROM(A) FROMCODEPAGE('IBM037')",
        "GET CONTAINER(C) INTO(A) INTOCCSID(1140) CONVERTST(DFHVALUE(NOCONVERT))",
        "GET CONTAINER(C) INTO(A) CCSID(N)",
        "GET CONTAINER(C) FLENGTH(L)",
        "RETURN CHANNEL(C)",
        "RETURN TRANSID('T') CHANNEL(C) COMMAREA(A)",
        "RETURN TRANSID('T') CHANNEL(C) IMMEDIATE",
        "LINK PROGRAM('P') CHANNEL(C) COMMAREA(A)",
        "MOVE CONTAINER(A)",
        "MOVE CONTAINER(A) AS(B) CONTAINERTYPE(X)",
        "STARTBROWSE CONTAINER CHANNEL(C)",
        "GETNEXT CONTAINER(N)",
        "ENDBROWSE CONTAINER",
        "PUT CONTAINER(C) FROM(A) BIT CHAR",
    ):
        with pytest.raises(ec.Unsupported):
            ec.translate_command(bad)


def test_return_channel_becomes_a_stub_call():
    """#5005 (X17): RETURN TRANSID CHANNEL -> GGCRETC with the transid in GG-NAME1 and the channel in GG-CHAN. It
    returns to the program (GOBACK only on success) when the RETURN fails below level 1 (INVREQ RESP2 2); CHANNEL
    without TRANSID, or beside COMMAREA / LENGTH / IMMEDIATE, is refused by name."""
    ret = ec.translate_command("RETURN TRANSID('PC62') CHANNEL(WS-CUR) RESP(R)")
    assert ret[:3] == ["MOVE 'PC62' TO GG-NAME1", "MOVE WS-CUR TO GG-CHAN", "CALL 'GGCRETC' USING GG-CICS"]
    assert ret[5:8] == ["IF GG-RESP = 0", "    GOBACK", "END-IF"] and "MOVE GG-RESP TO R" in ret
    for bad in ("RETURN CHANNEL(C)", "RETURN TRANSID('T') CHANNEL(C) LENGTH(4)"):
        with pytest.raises(ec.Unsupported, match="RETURN CHANNEL"):
            ec.translate_command(bad)


def test_container_ccsid_options_become_stub_arguments():
    """#4270 (X17): FROMCCSID / INTOCCSID travel in GG-NUM with a flag word in GG-FLAGS;
    CONVERTST(NOCONVERT) is the flag NOCONVERT; CCSID(area) is read back from GG-NUM with FLENGTH on RESP 0 or LENGERR."""
    put = ec.translate_command("PUT CONTAINER(C) FROM(WS-A) FROMCCSID(1140)")
    assert put[2:4] == ["MOVE 1140 TO GG-NUM", "MOVE 'FROMCCSID' TO GG-FLAGS"]
    put = ec.translate_command("PUT CONTAINER(C) FROM(WS-A) CHAR FROMCCSID(500) APPEND")
    assert "MOVE 500 TO GG-NUM" in put and "MOVE 'CHAR APPEND FROMCCSID' TO GG-FLAGS" in put
    get = ec.translate_command("GET CONTAINER(C) INTO(WS-A) INTOCCSID(WS-CS) FLENGTH(WS-N)")
    assert "MOVE WS-CS TO GG-NUM" in get and "MOVE 'INTOCCSID' TO GG-FLAGS" in get
    raw = ec.translate_command("GET CONTAINER(C) INTO(WS-A) CONVERTST(DFHVALUE(NOCONVERT)) CCSID(WS-CCSID)")
    i = raw.index("CALL 'GGCGETC' USING GG-CICS")
    assert "MOVE 'NOCONVERT' TO GG-FLAGS" in raw
    assert raw[i + 2 : i + 5] == ["IF GG-RESP = 0 OR GG-RESP = 22", "    MOVE GG-NUM TO WS-CCSID", "END-IF"]
    sets = ec.translate_command("GET CONTAINER(C) SET(PTR) FLENGTH(WS-N) INTOCCSID(1140)")
    assert "MOVE 1140 TO GG-NUM" in sets and "CALL 'GGCGETS' USING GG-CICS" in "\n".join(sets)


def test_container_byteoffset_and_prepend_become_stub_arguments():
    """#5005 (X17): BYTEOFFSET travels in GG-NUM with the flag BYTEOFFSET (INTO only; no CCSID option, NODATA or SET); PREPEND is a
    flag word (not with APPEND)."""
    get = ec.translate_command("GET CONTAINER(C) CHANNEL('CH') INTO(WS-A) FLENGTH(WS-N) BYTEOFFSET(WS-OFF)")
    assert "MOVE 'CHANNEL BYTEOFFSET' TO GG-FLAGS" in get and "MOVE WS-OFF TO GG-NUM" in get
    assert get.index("MOVE WS-OFF TO GG-NUM") < get.index("CALL 'GGCGETC' USING GG-CICS")
    put = ec.translate_command("PUT CONTAINER(C) FROM(WS-A) BIT PREPEND")
    assert "MOVE 'BIT PREPEND' TO GG-FLAGS" in put
    for bad in (
        "GET CONTAINER(C) NODATA BYTEOFFSET(4)",
        "GET CONTAINER(C) SET(PTR) FLENGTH(WS-N) BYTEOFFSET(4)",
        "GET CONTAINER(C) INTO(A) BYTEOFFSET(4) INTOCCSID(500)",
        "GET CONTAINER(C) INTO(A) BYTEOFFSET(4) CONVERTST(DFHVALUE(NOCONVERT))",
        "PUT CONTAINER(C) FROM(A) APPEND PREPEND",
    ):
        with pytest.raises(ec.Unsupported):
            ec.translate_command(bad)


@pytest.mark.parametrize(
    "base",
    [
        "PUT CONTAINER('REQ') CHANNEL(WS-CH) FROM(WS-A) FLENGTH(WS-N) CHAR APPEND RESP(R)",
        "PUT CONTAINER(C) FROM(WS-A) DATATYPE(DFHVALUE(BIT)) PREPEND",
        "PUT CONTAINER(C) FROM(WS-A) FROMCCSID(1140)",
        "GET CONTAINER(C) INTO(WS-A) FLENGTH(WS-N) RESP(R) RESP2(R2)",
        "GET CONTAINER(C) CHANNEL('CH') INTO(WS-A) BYTEOFFSET(WS-OFF)",
        "GET CONTAINER(C) NODATA FLENGTH(WS-N)",
        "GET CONTAINER(C) INTO(WS-A) INTOCCSID(500) FLENGTH(WS-N)",
    ],
)
def test_get64_and_put64_container_become_the_base_commands_stub_calls(base):
    """#5005 (X17): GET64 / PUT64 CONTAINER take the same options and answer with the same conditions as GET / PUT
    CONTAINER (INTO / FROM an ordinary item, ASSUMED), so the stub gets the very same calls; SET (a 64-bit pointer)
    is refused by name."""
    sixty_four = base.replace("GET ", "GET64 ", 1).replace("PUT ", "PUT64 ", 1)
    assert ec.translate_command(sixty_four) == ec.translate_command(base)


def test_get64_container_set_is_refused_by_name():
    for bad in (
        "GET64 CONTAINER(C) SET(PTR) FLENGTH(WS-N)",
        "GET64 CONTAINER(C) SET(PTR) FLENGTH(WS-N) INTOCCSID(1140)",
    ):
        with pytest.raises(ec.Unsupported, match="64-bit pointer"):
            ec.translate_command(bad)


@pytest.mark.parametrize(
    "base",
    [
        "GET CONTAINER(C) FLENGTH(WS-N)",
        "GET CONTAINER(C) INTO(A) INTOCODEPAGE('UTF-8')",
        "PUT CONTAINER(C) FROM(A) FROMCODEPAGE('IBM037')",
        "PUT CONTAINER(C) FROM(A) APPEND PREPEND",
        "PUT CONTAINER(C) FROM(A) BIT CHAR",
    ],
)
def test_get64_and_put64_container_refuse_what_the_base_command_refuses(base):
    sixty_four = base.replace("GET ", "GET64 ", 1).replace("PUT ", "PUT64 ", 1)
    with pytest.raises(ec.Unsupported) as want:
        ec.translate_command(base)
    with pytest.raises(ec.Unsupported) as got:
        ec.translate_command(sixty_four)
    assert str(got.value) == str(want.value)


def test_move_container_and_the_container_browse_call_the_stub():
    """#4951: MOVE CONTAINER -> GGCMOVC (CONTAINER / AS / CHANNEL / TOCHANNEL in GG-QNAME / GG-AS / GG-CHAN / GG-TOCHAN,
    GG-FLAGS naming the channels given), STARTBROWSE -> GGCSBRC (the token out of GG-NUM on NORMAL), GETNEXT -> GGCGNXC
    (the token in GG-NUM, the name out of GG-QNAME on NORMAL) and ENDBROWSE -> GGCEBRC."""
    move = ec.translate_command("MOVE CONTAINER('A') AS('B') CHANNEL(WS-F) TOCHANNEL(WS-T)")
    assert move[:6] == ["MOVE 'A' TO GG-QNAME", "MOVE 'B' TO GG-AS", "MOVE WS-F TO GG-CHAN", "MOVE WS-T TO GG-TOCHAN",
                        "MOVE 'CHANNEL TOCHAN' TO GG-FLAGS", "CALL 'GGCMOVC' USING GG-CICS"]  # fmt: skip
    bare = ec.translate_command("MOVE CONTAINER('A') AS('B')")
    assert "MOVE SPACES TO GG-FLAGS" in bare and "CALL 'GGCMOVC' USING GG-CICS" in bare
    start = ec.translate_command("STARTBROWSE CONTAINER CHANNEL(WS-F) BROWSETOKEN(WS-TOK)")
    assert start[:4] == ["MOVE WS-F TO GG-CHAN", "MOVE 'CHANNEL' TO GG-FLAGS", "CALL 'GGCSBRC' USING GG-CICS",
                         "IF GG-RESP = 0"] and start[4] == "    MOVE GG-NUM TO WS-TOK"  # fmt: skip
    nxt = ec.translate_command("GETNEXT CONTAINER(WS-NAME) BROWSETOKEN(WS-TOK) RESP(WS-R)")
    assert nxt[:3] == ["MOVE WS-TOK TO GG-NUM", "CALL 'GGCGNXC' USING GG-CICS", "IF GG-RESP = 0"]
    assert nxt[3] == "    MOVE GG-QNAME TO WS-NAME" and "MOVE GG-RESP TO WS-R" in nxt
    end = ec.translate_command("ENDBROWSE CONTAINER BROWSETOKEN(WS-TOK)")
    assert end[:2] == ["MOVE WS-TOK TO GG-NUM", "CALL 'GGCEBRC' USING GG-CICS"]


def test_delete_and_query_channel_call_the_stub():
    """#5005: DELETE CHANNEL -> GGCDELH (CHANNEL in GG-CHAN) and QUERY CHANNEL -> GGCQCHN (the count out of GG-NUM into
    CONTAINERCNT on NORMAL only); CHANNEL (and CONTAINERCNT) required, an option IBM's command does not list refused."""
    got = ec.translate_command("DELETE CHANNEL(WS-CH) RESP(WS-R)")
    assert got[:2] == ["MOVE WS-CH TO GG-CHAN", "CALL 'GGCDELH' USING GG-CICS"] and "MOVE GG-RESP TO WS-R" in got
    assert ec.translate_command("DELETE CHANNEL('C')")[0] == "MOVE 'C' TO GG-CHAN"
    got = ec.translate_command("QUERY CHANNEL(WS-CH) CONTAINERCNT(WS-N) RESP(WS-R)")
    assert got[:5] == ["MOVE WS-CH TO GG-CHAN", "CALL 'GGCQCHN' USING GG-CICS", "IF GG-RESP = 0",
                       "    MOVE GG-NUM TO WS-N", "END-IF"]  # fmt: skip
    for bad in ("DELETE CHANNEL", "DELETE CHANNEL(C) CONTAINERTYPE(X)", "QUERY CHANNEL(C)",
                "QUERY CHANNEL CONTAINERCNT(N)", "QUERY CHANNEL(C) CONTAINERCNT(N) BOGUS(X)"):  # fmt: skip
        with pytest.raises(ec.Unsupported):
            ec.translate_command(bad)


def test_send_map_records_its_options_and_area():
    got = ec.translate_command("SEND MAP(M) MAPSET(S) FROM(MO) CURSOR ERASE FREEKB")
    assert "MOVE 'CURSOR ERASE FREEKB' TO GG-FLAGS" in got and "    BY REFERENCE MO" in got


def test_a_terminal_receive_passes_its_length_in_and_takes_the_datas_length_back():
    """#4005: LENGTH is in-out -- in, the most INTO takes; out, the data's length (IBM, EXEC CICS RECEIVE)."""
    got = ec.translate_command("RECEIVE INTO(WS-INPUT) LENGTH(WS-INLEN)")
    assert got[:4] == ["MOVE SPACES TO GG-FLAGS", "MOVE WS-INLEN TO GG-LEN", "CALL 'GGCRECT' USING GG-CICS",
                       "    BY REFERENCE WS-INPUT"]  # fmt: skip
    assert got[4] == "MOVE GG-LEN TO WS-INLEN" and got[-5] == "    CALL 'GGCCOND' USING GG-CICS"
    assert ec.translate_command("RECEIVE INTO(WS-I) LENGTH(WS-L) MAXLENGTH(30)")[1] == "MOVE 30 TO GG-LEN"
    omitted = ec.translate_command("RECEIVE INTO(WS-I) RESP(WS-R)")
    assert omitted[1] == "MOVE LENGTH OF WS-I TO GG-LEN" and "MOVE GG-RESP TO WS-R" in omitted
    assert not any(ln.startswith("MOVE GG-LEN") for ln in omitted)


def test_receive_notruncate_and_set_and_send_control():
    """#4413: NOTRUNCATE goes to the stub in GG-FLAGS; SET(ADDRESS OF record) takes the stub's buffer through GG-PTR
    (MAXLENGTH and LENGTH required, as det/cics.py); SEND CONTROL passes its options and CURSOR's value."""
    got = ec.translate_command("RECEIVE INTO(WS-I) LENGTH(WS-L) MAXLENGTH(4) NOTRUNCATE")
    assert got[:2] == ["MOVE 'NOTRUNCATE' TO GG-FLAGS", "MOVE 4 TO GG-LEN"]
    got = ec.translate_command("RECEIVE SET(ADDRESS OF LS-IN) LENGTH(WS-L) MAXLENGTH(20) RESP(WS-R)")
    assert got[:6] == ["MOVE SPACES TO GG-FLAGS", "MOVE 20 TO GG-LEN", "CALL 'GGCRECS' USING GG-CICS",
                       "    BY REFERENCE GG-PTR", "SET ADDRESS OF LS-IN TO GG-PTR", "MOVE GG-LEN TO WS-L"]  # fmt: skip
    for bad in ("RECEIVE SET(ADDRESS OF LS-IN) LENGTH(WS-L)", "RECEIVE SET(ADDRESS OF LS-IN) MAXLENGTH(9)"):
        with pytest.raises(ec.Unsupported):
            ec.translate_command(bad)
    assert ec.translate_command("SEND CONTROL FREEKB ERASE")[:3] == [
        "MOVE 'ERASE FREEKB' TO GG-FLAGS", "MOVE -1 TO GG-LEN", "CALL 'GGCSCTL' USING GG-CICS"]  # fmt: skip
    assert ec.translate_command("SEND CONTROL CURSOR(WS-C) ALARM")[:2] == ["MOVE 'ALARM CURSOR' TO GG-FLAGS",
                                                                           "MOVE WS-C TO GG-LEN"]  # fmt: skip
    for bad in ("SEND CONTROL PRINT", "SEND CONTROL CURSOR"):
        with pytest.raises(ec.Unsupported):
            ec.translate_command(bad)


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
    # X6 (ASSUMED): a LENGTH past the FROM item writes FROM's bytes then spaces (GG-PADQ); a record over 32767 is refused
    assert w[4:17] == ["IF GG-LEN > LENGTH OF WS-ONE", "    IF GG-LEN > LENGTH OF GG-PADQ",
                       "        DISPLAY 'WRITEQ TS LENGTH > FROM: not modelled'", "        MOVE 98 TO RETURN-CODE",
                       "        STOP RUN", "    END-IF", "    DISPLAY 'GG-X6 PADDED WRITEQ TS'", "    MOVE SPACES TO GG-PADQ",
                       "    MOVE WS-ONE TO GG-PADQ(1:LENGTH OF WS-ONE)", "    CALL 'GGCWRTQ' USING GG-CICS",
                       "        BY REFERENCE GG-PADQ", "ELSE", "    CALL 'GGCWRTQ' USING GG-CICS"]  # fmt: skip
    assert (
        w[17:20] == ["        BY REFERENCE WS-ONE", "END-IF", "IF GG-RESP = 0"] and "    MOVE GG-ITEM TO WS-I" == w[20]
    )
    r = ec.translate_command("WRITEQ TS QUEUE('Q') FROM(A) ITEM(WS-I) REWRITE")
    assert r[2:4] == ["MOVE WS-I TO GG-ITEM", "MOVE 'REWRITE' TO GG-FLAGS"] and "    MOVE GG-ITEM TO WS-I" not in r


def test_a_read_gteq_generic_search_is_named_to_the_stub():
    """#4270 (GenApp LGICVS01 / LGIPVS01, oracle_assumptions.md X22): GTEQ / GENERIC go to GGCREAD in GG-FLAGS, the
    generic key's length is KEYLENGTH; EQUAL with GTEQ, and GENERIC without KEYLENGTH, refused as the translator."""
    got = ec.translate_command("READ FILE('KSDSPOLY') INTO(A) LENGTH(F64) RIDFLD(PK) KEYLENGTH(F11) GENERIC GTEQ")
    assert got[1] == "MOVE 'GTEQ GENERIC' TO GG-FLAGS" and "    BY VALUE F11" in got
    upd = ec.translate_command("READ FILE(F) INTO(A) RIDFLD(K) GTEQ UPDATE")
    assert upd[1] == "MOVE 'UPDATE GTEQ' TO GG-FLAGS"
    for bad in ("READ FILE(F) INTO(A) RIDFLD(K) GTEQ EQUAL", "READ FILE(F) INTO(A) RIDFLD(K) GENERIC GTEQ"):
        with pytest.raises(ec.Unsupported):
            ec.translate_command(bad)


def test_a_delete_generic_is_named_to_the_stub():
    """#4771 zECS (ZECS003, X22): DELETE GENERIC -> GGCDELT with GG-FLAGS 'GENERIC' and KEYLENGTH as the generic key's
    length (the stub deletes every record with it); without KEYLENGTH or RIDFLD refused as the translator; NUMREC refused."""
    got = ec.translate_command("DELETE FILE(ZF-FCT) RIDFLD(ZF-KEY-16) KEYLENGTH(DELETE-LENGTH) GENERIC NOHANDLE")
    assert got[:3] == ["MOVE ZF-FCT TO GG-NAME1", "MOVE 'GENERIC' TO GG-FLAGS", "CALL 'GGCDELT' USING GG-CICS"]
    assert got[3:5] == ["    BY REFERENCE ZF-KEY-16", "    BY VALUE DELETE-LENGTH"]
    # #5092 (X22): a given KEYLENGTH without GENERIC is named to the stub (INVREQ 26 unless it is the key's length); none, not
    keyed = ec.translate_command("DELETE FILE(F) RIDFLD(K) KEYLENGTH(2) NOHANDLE")
    assert keyed[1] == "MOVE 'KEYLENGTH' TO GG-FLAGS" and "    BY VALUE 2" in keyed
    assert ec.translate_command("DELETE FILE(F) RIDFLD(K) NOHANDLE")[1] == "MOVE SPACES TO GG-FLAGS"
    for bad, why in (("DELETE FILE(F) RIDFLD(K) GENERIC", "without KEYLENGTH"),
                     ("DELETE FILE(F) KEYLENGTH(2) GENERIC", "without RIDFLD")):  # fmt: skip
        with pytest.raises(ec.Unsupported, match=why):
            ec.translate_command(bad)


@pytest.mark.parametrize("body", ["READ FILE(F) RIDFLD(K) INTO(R) GENERIC", 
                                  "HANDLE ABEND PROGRAM('X')", "ASSIGN OPID(U)", "HANDLE CONDITION NOSUCH(X)",
                                  "WRITEQ TS QUEUE(Q) FROM(A) SYSID(S)", "WRITEQ TS QUEUE(Q) FROM(A) REWRITE",
                                  "READQ TD QUEUE(Q) SET(P)",
                                  "RECEIVE INTO(X) LENGTH(L) BUFFER", "RECEIVE SET(P) LENGTH(L)", "STARTBR FILE(F) RIDFLD(K) REQID(1)",
                                  "DELETE FILE('X') RIDFLD(K) GENERIC KEYLENGTH(2) NUMREC(N)", "LINK PROGRAM('X') SYSID('S')"])  # fmt: skip
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
        ec.translate(PROGRAM.replace("READ FILE('ACCT') RIDFLD(WS-KEY)", "READQ TD QUEUE('CSSL') SET(WS-KEY)"))


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


def test_send_control_is_an_event_both_sides_compare_by_options_and_cursor():
    """#4270 (CBSA's CLEAR key): the stub's SEND-CONTROL line is an event like CicsTask's, its options and CURSOR
    compared -- a port that left it out, or sent other options, differs."""
    res = {"events": ["SEND-CONTROL pgm=BNKMENU cursor=-1 opts=ERASE FREEKB", "RETURN pgm=BNKMENU level=1 transid= len=0"],
           "screens": [], "text": [], "return": {"transid": "", "commarea": None}}  # fmt: skip
    cobol = ec.cobol_events(res)
    assert cobol[0] == {"event": "SEND-CONTROL", "options": ["ERASE", "FREEKB"], "cursor": None}
    java = [{"event": "SEND-CONTROL", "options": ["FREEKB", "ERASE"], "cursor": None},
            {"event": "RETURN", "transid": None, "commarea": None}]  # fmt: skip
    assert ec.compare_events(cobol, java)["equal"] == 2
    assert ec.compare_events(cobol, [{**java[0], "options": ["ERASE"]}, java[1]])["equal"] == 1
    assert ec.compare_events(cobol, java[1:])["equal"] == 0


def test_send_text_options_are_compared_both_sides():
    """#5401 (COCRDSLC mutant 0173a35c74): SEND TEXT compared by text only let an options-changing mutant read as
    proven. The stub's opts line (kind marker dropped) is compared with CicsTask's, on the options the stub gets."""
    res = {"events": ["SEND-TEXT len=5 opts=TEXT FREEKB ERASE", "SEND-TEXT len=2 opts=DATA", "SEND-TEXT len=1",
                      "RETURN pgm=P level=1 transid= len=0"],
           "screens": [], "text": ["HELLO", "HI", "X"], "text_options": [ec._text_options(a) for a in
                                                                         ("opts=TEXT FREEKB ERASE", "opts=DATA", "")],
           "return": {"transid": "", "commarea": None}}  # fmt: skip
    cobol = ec.cobol_events(res)
    assert [c["options"] for c in cobol[:3]] == [["ERASE", "FREEKB"], [], []]
    ret = {"event": "RETURN", "transid": None, "commarea": None}

    def java(*opts):
        return [{"event": "SEND-TEXT", "text": t, "options": o} for t, o in zip(("HELLO", "HI", "X"), opts)] + [ret]

    same = java(["ERASE", "FREEKB"], [], [])
    assert ec.compare_events(cobol, same)["equal"] == 4
    assert ec.compare_events(cobol, java(["FREEKB", "ERASE"], [], []))["equal"] == 4  # order
    assert ec.compare_events(cobol, java(["ERASE", "FREEKB", "PRINT"], [], []))["equal"] == 4  # not forwarded
    for wrong in (["ERASE"], ["ERASE", "FREEKB", "ALARM"], ["ERASE", "WAIT"], []):  # missing, extra, other
        got = ec.compare_events(cobol, java(wrong, [], []))
        assert got["equal"] == 3 and got["diffs"][0]["fields"][0]["field"] == "options"
    assert ec.compare_events(cobol, java(["ERASE", "FREEKB"], ["ERASE"], []))["equal"] == 3
    assert ec.compare_events(cobol, java(["ERASE", "FREEKB"], [], ["LAST"]))["equal"] == 3
    other_text = [{**same[0], "text": "BYE"}, *same[1:]]
    assert ec.compare_events(cobol, other_text)["equal"] == 3


def test_a_tasks_terminal_and_origin_are_stated_facts_or_none():
    """#4270: "termid" / "uctranst" / "origin" -- the scenario's, else the case's; unstated None (the commands that
    read them are then refused by both runtimes); a malformed one refused by name."""
    case = {"termid": "T001", "uctranst": "NOUCTRAN"}
    assert ec.terminal_facts(case, {"name": "s"}) == {"termid": "T001", "uctranst": "NOUCTRAN", "origin": None}
    assert ec.terminal_facts({}, {"name": "s"}) == {"termid": None, "uctranst": None, "origin": None}
    origin = {"applid": "CBSAREGN", "userid": "CICSUSER", "facilname": "T001", "networkid": "NET1",
              "faciltype": "TERMINAL"}  # fmt: skip
    assert ec.terminal_facts(case, {"name": "s", "origin": origin})["origin"] == origin
    for bad in ({"termid": "T 01"}, {"termid": "TOOLONG"}, {"termid": "T001", "uctranst": "YES"},
                {"uctranst": "UCTRAN"}, {"origin": {**origin, "userid": ""}}, {"origin": {"applid": "A"}}):  # fmt: skip
        with pytest.raises(ec.Unsupported):
            ec.terminal_facts({}, {"name": "s", **bad})


def test_low_values_and_spaces_in_a_commarea_are_different_values():
    """#4635: a field RECEIVE MAP left LOW-VALUES and one the port left spaces are different bytes to the next program
    (COSGN00C: the RETURN COMMAREA's CDEMO-USER-ID); trailing spaces alone are still not data."""
    lv, sp = "\x00" * 8, "        "

    def ret(v):
        return [{"event": "RETURN", "transid": "T1", "commarea": {"CA-USER": v}}]

    assert ec.compare_events(ret(lv), ret(sp))["equal"] == 0
    assert ec.compare_events(ret(lv), ret(""))["equal"] == 0
    assert ec.compare_events(ret(lv), ret(lv))["equal"] == 1
    assert ec.compare_events(ret("AB"), ret("AB   "))["equal"] == 1
    assert ec.compare_events(ret(sp), ret(""))["equal"] == 1
    # a screen shows neither: its fields still compare as they did
    scr = lambda v: [{"event": "SEND-MAP", "map": "M", "screen": {"F": v}}]  # noqa: E731
    assert ec.compare_events(scr(lv), scr(sp))["equal"] == 1


def test_storage_a_task_without_a_commarea_never_set_stays_undefined_text_too():
    """#4635 x X12: a no-COMMAREA task's returned text left all LOW-VALUES is undefined storage, dropped both sides."""
    ev = lambda v: [{"event": "RETURN", "transid": "T", "commarea": {"CA-T": v, "CA-N": "x"}}]  # noqa: E731
    cev, jev = ec.mask_absent_commarea({"commarea": None}, ev("\x00" * 4), ev("    "), [0])
    assert ec.compare_events(cev, jev)["equal"] == 1
    cev, jev = ec.mask_absent_commarea({"commarea": {"CA-T": "x"}}, ev("\x00" * 4), ev("    "), [0])
    assert ec.compare_events(cev, jev)["equal"] == 0  # a COMMAREA was given: LOW-VALUES are a value


def test_a_returned_commareas_text_keeps_its_low_values():
    fields = [{"name": "CA-USER", "offset": 0, "bytes": 4, "pic": "X(4)", "usage": "DISPLAY"}]
    assert ec.decode_record(b"\x00\x00\x00\x00", fields, exact=True) == {"CA-USER": "\x00\x00\x00\x00"}
    assert ec.decode_record(b"AB  ", fields, exact=True) == {"CA-USER": "AB"}
    assert ec.decode_record(b"\x00\x00\x00\x00", fields) == {"CA-USER": ""}  # a screen's reading, as before


def test_a_tasks_display_output_is_compared_like_a_batch_steps_sysout(tmp_path):
    """#4635: ABNDPROC's two branches end in the same RETURN and differ only in what they DISPLAY."""
    cobol = b"*****\n**** Unable to write to the file ABNDFILE !!!\nRESP=00000000 RESP2=00000000\n"
    java = tmp_path / "t.sysout"
    java.write_text(cobol.decode(), encoding="utf-8")
    assert ec.compare_task_sysout(cobol, java, "latin-1")["differing"] == 0
    java.write_text(cobol.decode().replace("write to", "WRITE to"), encoding="utf-8")
    d = ec.compare_task_sysout(cobol, java, "latin-1")
    assert (d["differing"], d["diffs"][0]["line"]) == (1, 2)
    assert ec.compare_task_sysout(cobol, tmp_path / "none", "latin-1")["differing"] == 3  # the port DISPLAYed nothing
    assert ec.compare_task_sysout(b"", tmp_path / "none", "latin-1")["differing"] == 0


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
    # #4449: and through its deployed entry point, every scenario entered by handleTransaction
    assert report["facade"]["proven"], report["facade"]
    assert [e["method"] for e in report["facade"]["entry_points"]] == ["handleTransaction"]


@pytest.mark.skipif(__import__("os").environ.get("EQUIVALENCE_E2E") != "1",
                    reason="needs Docker (GnuCOBOL) and a JDK + Maven")  # fmt: skip
def test_a_facade_that_builds_its_own_task_fails_the_java_facade_side(tmp_path):
    """#4449: COMEN01C's port with a handleTransaction that runs runTask on a task of its own (not the region's):
    every runTask scenario still passes, every java-facade scenario is refused, and the case is not proven."""
    import json
    import shutil
    import subprocess

    port = tmp_path / "port"
    shutil.copytree(eq.CASES / "carddemo-menu" / "port", port)
    (port / "provenance.json").unlink()
    svc = port / "service" / "Comen01cService.java"
    text = svc.read_text(encoding="utf-8")
    joined = '        CicsTask task = region.transaction(transid, request);\n        region.run(task, "COMEN01C", this::runTask);'
    assert joined in text
    svc.write_text(text.replace(joined, '        CicsTask task = new CicsTask(transid, "ENTER", request, null, '
                                        "java.util.Map.of());\n        runTask(task);"), encoding="utf-8")  # fmt: skip
    proc = subprocess.run([sys.executable, str(Path(eq.__file__)), "run", "carddemo-menu", "--port", str(port),  # noqa: S603
                           "--keep", str(tmp_path / "w")], capture_output=True, text=True, check=False)  # fmt: skip
    report = json.loads((tmp_path / "w" / "report.json").read_text())
    assert proc.returncode == 1 and report["proven"] is False
    assert all(o["equal"] == o["records"] for o in report["outputs"].values())  # runTask: unchanged, passes
    facade = report["facade"]["outputs"]
    assert facade and all(not o["pass"] and o.get("refused") for o in facade.values())
    assert report["facade"]["entry_points"] == []


# ---- #4449: the java-facade side's verdicts -------------------------------------------------------------------
def _facade_case():
    return {"name": "x", "program": "PROG", "transid": "T001", "scenarios": [{"name": "a"}, {"name": "b"}],
            "datasets": {}}  # fmt: skip


def _cobol_task():
    return {"events": ["SEND-TEXT", "RETURN level=1"], "screens": [], "text": ["HELLO"],
            "return": {"transid": "T001", "commarea": None}}  # fmt: skip


def test_the_facade_side_passes_a_scenario_only_when_it_matches_and_was_not_refused(tmp_path):
    same = [{"event": "SEND-TEXT", "text": "HELLO"}, {"event": "RETURN", "transid": "T001", "commarea": None}]
    entered = [{"program": "PROG", "method": "handleTransaction"}]
    facade = {"out": tmp_path, "events": {"a": same, "b": same}, "entries": {"a": entered, "b": entered},
              "refused": {"b": "handleTransaction of PROG did not run its task in the region"}}  # fmt: skip
    got = ec.judge_facade(_facade_case(), tmp_path, [], {"a": _cobol_task(), "b": _cobol_task()}, facade, {},
                          tmp_path)  # fmt: skip
    assert got["outputs"]["a"]["pass"] and not got["outputs"]["b"]["pass"]
    assert got["outputs"]["b"]["refused"].startswith("handleTransaction of PROG")
    assert got["proven"] is False
    assert got["entry_points"] == [{"method": "handleTransaction", "why": ec.FACADE_WHY, "scenarios": ["a"]}]


def test_the_facade_side_fails_a_differing_task_and_a_failed_run(tmp_path):
    other = [{"event": "SEND-TEXT", "text": "BYE"}, {"event": "RETURN", "transid": "T001", "commarea": None}]
    facade = {"out": tmp_path, "events": {"a": other, "b": other}, "entries": {}, "refused": {}}
    got = ec.judge_facade(_facade_case(), tmp_path, [], {"a": _cobol_task()}, facade, {}, tmp_path)
    assert got["proven"] is False and got["outputs"]["a"]["diffs"]
    failed = ec.judge_facade(_facade_case(), tmp_path, [], {"a": _cobol_task()}, {"error": "Java side failed"}, {},
                             tmp_path)  # fmt: skip
    assert failed["proven"] is False and failed["error"] == "Java side failed"


def test_the_generated_test_runs_runtask_unless_the_facade_side_is_asked_for(tmp_path):
    """The runTask side is the default (-Dequivalence.facades unset) and runs as before; the facade side joins the
    scenario's region and enters the program -- by handleLink when the case is LINKed -- and a LINK target the case
    runs through its handleLink."""
    import equivalence_java as ej

    svc = tmp_path / "service" / f"{ej._service_class('PROG')}.java"
    svc.parent.mkdir(parents=True)
    svc.write_text("public void handleTransaction(String transid, ProgCa request) {}", encoding="utf-8")
    case = {**_facade_case(), "clock": "2026/10/01 10:30:15.00", "screens": {},
            "programs": [{"program": "LINKED", "program_source": "x.cbl"}]}  # fmt: skip
    java = ec.cics_equivalence_test(case, tmp_path, [])
    assert 'final boolean facades = Boolean.getBoolean("equivalence.facades");' in java
    assert 'new FacadeRegion(task, commarea, "PROG", false)' in java
    runs = java[java.index("if (facades) {\n                        try (CicsTask.Joined") :]
    assert (
        "region.start(" in runs
        and f"}} else {{\n                        {ej._service_class('PROG')[0].lower()}" in runs
    )
    assert 'if (facades) { region.enter("LINKED", t, ' in java and ".runTask(t); } return; }" in java
    linked = ec.cics_equivalence_test({**case, "linked": True}, tmp_path, [])
    assert 'new FacadeRegion(task, commarea, "PROG", true)' in linked
    pkg = java.split("package ", 1)[1].split(";", 1)[0]
    assert ec.FACADE_JAVA.replace("__PKG__", pkg) in java  # #4695: the port's package names its page's class


# ---- file updates: WRITE, REWRITE, READ UPDATE, SYNCPOINT (CardDemo's update programs) -----------------------
def test_file_updates_translate_to_stub_calls():
    upd = ec.translate_command("READ DATASET(WS-F) INTO(R) RIDFLD(K) UPDATE RESP(X)")
    assert upd[:4] == ["MOVE WS-F TO GG-NAME1", "MOVE 'UPDATE' TO GG-FLAGS", "MOVE LENGTH OF R TO GG-LEN",
                       "CALL 'GGCREAD' USING GG-CICS"]  # fmt: skip
    w = ec.translate_command("WRITE DATASET(F) FROM(REC) RIDFLD(K) RESP(X)")
    assert w[:2] == ["MOVE F TO GG-NAME1", "CALL 'GGCWRIT' USING GG-CICS"] and "    BY REFERENCE REC" in w
    rw = ec.translate_command("REWRITE FILE(F) FROM(REC) RESP(X) RESP2(Y)")
    assert rw[:3] == [
        "MOVE F TO GG-NAME1",
        "MOVE SPACES TO GG-FLAGS",
        "CALL 'GGCREWR' USING GG-CICS",
    ]  # #5078: flags set
    assert ec.translate_command("SYNCPOINT")[:2] == ["MOVE SPACES TO GG-FLAGS", "CALL 'GGCSYNC' USING GG-CICS"]
    assert ec.translate_command("SYNCPOINT ROLLBACK")[0] == "MOVE 'ROLLBACK' TO GG-FLAGS"
    for bad in ("WRITE FILE(F) FROM(R) RIDFLD(K) MASSINSERT", "REWRITE FILE(F) FROM(R) SYSID(S)"):
        with pytest.raises(ec.Unsupported):
            ec.translate_command(bad)
    sc = {
        "faults": [{"cmd": "REWRITE", "file": "ACCTDAT", "resp": "NOSPACE"}]
    }  # IBM's REWRITE lists no NOTOPEN (#5044)
    assert ec.fault_lines(sc) == ["REWRITE ACCTDAT 1 18 100"]


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


def test_formattime_resp_asktime_nohandle_readq_length_of_and_receive_map_asis():
    """#4737 (X28): FORMATTIME is INVREQ RESP2 1 below zero, then RESP / the handlers; ASKTIME NOHANDLE with no ABSTIME
    changes nothing; READQ TS LENGTH(LENGTH OF x) is not set back; RECEIVE MAP ASIS is accepted."""
    fmt = ec.translate_command("FORMATTIME ABSTIME(T) DDMMYYYY(D) RESP(R)")
    assert fmt[:6] == ["MOVE 0 TO GG-RESP", "MOVE 0 TO GG-RESP2", "IF T < 0", "    MOVE 16 TO GG-RESP",
                       "    MOVE 1 TO GG-RESP2", "ELSE"]  # fmt: skip
    assert "MOVE GG-RESP TO R" in fmt and not any("GGCCOND" in x for x in fmt)
    plain = ec.translate_command("FORMATTIME ABSTIME(T) TIME(D)")  # no RESP: an ABSTIME below zero is refused
    assert plain[:2] == ["IF T < 0", "    DISPLAY 'FORMATTIME ABSTIME < 0 NO RESP: not modelled'"]
    assert not any("GG-RESP" in x for x in plain)
    assert ec.translate_command("ASKTIME NOHANDLE") == ["CONTINUE"]
    out = ec.translate_command("READQ TS QUEUE(Q) INTO(A) LENGTH(LENGTH OF A) RESP(R)")
    assert "MOVE LENGTH OF A TO GG-LEN" in out and not any(x.endswith("TO LENGTH OF A") for x in out)
    assert "    MOVE GG-LEN TO L" in ec.translate_command("READQ TS QUEUE(Q) INTO(A) LENGTH(L) RESP(R)")
    assert "CALL 'GGCRECV' USING GG-CICS" in ec.translate_command(
        "RECEIVE MAP('MAP') MAPSET('MS') INTO(MAPI) ASIS RESP(R)"
    )


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
        "FORMATTIME ABSTIME(T) DATE(D)",  # #4415 slice 3 (X46): the installation's DATFORM, not stated
        "FORMATTIME ABSTIME(T) DATESTRING(D) STRINGFORMAT(DFHVALUE(RFC1123))",
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
    assert got[:3] == ["MOVE 'APPLID' TO GG-NAME2", "CALL 'GGCASGN' USING GG-CICS", "MOVE GG-NAME1(1:8) TO A(1:8)"]
    assert got[3:6] == ["MOVE 'SYSID' TO GG-NAME2", "CALL 'GGCASGN' USING GG-CICS", "MOVE GG-NAME1(1:4) TO S(1:4)"]
    td = ec.translate_command("WRITEQ TD QUEUE('JOBS') FROM(REC) RESP(R)")
    assert td[:4] == ["MOVE 'JOBS' TO GG-QNAME", "MOVE LENGTH OF REC TO GG-LEN", "CALL 'GGCWRTD' USING GG-CICS",
                      "    BY REFERENCE REC"]  # fmt: skip
    # X6 (ASSUMED): TD with a LENGTH past FROM pads through GG-PADQ as TS does; LENGTH within FROM or a literal FROM does not
    pad = ec.translate_command("WRITEQ TD QUEUE('JOBS') FROM(REC) LENGTH(WS-L) RESP(R)")
    assert pad[1:3] == ["MOVE WS-L TO GG-LEN", "IF GG-LEN > LENGTH OF REC"]
    assert "    MOVE REC TO GG-PADQ(1:LENGTH OF REC)" in pad and "        BY REFERENCE GG-PADQ" in pad
    assert pad.count("    CALL 'GGCWRTD' USING GG-CICS") == 2 and "        BY REFERENCE REC" in pad
    assert "GG-PADQ" not in " ".join(ec.translate_command("WRITEQ TD QUEUE('JOBS') FROM('X') LENGTH(1) RESP(R)"))
    assert "GG-PADQ" in ec._PADQ
    with pytest.raises(ec.Unsupported):
        ec.translate_command("ASSIGN OPID(U)")


@pytest.mark.parametrize("opt,width", [("APPLID", 8), ("SYSID", 4), ("ABCODE", 4), ("PROGRAM", 8), ("INVOKINGPROG", 8),
                                       ("STARTCODE", 2), ("USERID", 8)])  # fmt: skip
def test_assign_writes_exactly_the_option_width(opt, width):
    """#4049: IBM ASSIGN writes `width` bytes and leaves a wider data area's tail as it was; a plain MOVE would space it
    (CardDemo SYSIDO is 8 bytes, SYSID 4). The target is reference-modified to the width, whatever its qualification,
    and an already reference-modified target is refused by name."""
    for target in ("WS-X", "SYSIDO OF COSGN0AO", "WS-T(IDX)"):
        assert f"MOVE GG-NAME1(1:{width}) TO {target}(1:{width})" in ec.translate_command(f"ASSIGN {opt}({target})")
    with pytest.raises(ec.Unsupported, match="reference-modified"):
        ec.translate_command(f"ASSIGN {opt}(WS-X(1:2))")


def test_send_text_terminal_translates_as_send_text():
    """#4270 slice 4: TERMINAL, the default output disposition, changes nothing in the stub's call; the logical-message,
    printer and partition options are refused by name (register X20)."""
    plain = ec.translate_command("SEND TEXT FROM(L) WAIT FREEKB ERASE")
    assert ec.translate_command("SEND TEXT FROM(L) TERMINAL WAIT FREEKB ERASE") == plain
    assert plain[0] == "MOVE 'TEXT WAIT FREEKB ERASE' TO GG-FLAGS"
    for opt in ("ACCUM", "PAGING", "HEADER(H)", "JUSTIFY(5)", "L80", "SET(P)"):
        with pytest.raises(ec.Unsupported) as e:
            ec.translate_command(f"SEND TEXT FROM(L) TERMINAL {opt}")
        assert e.value.features == [f"SEND TEXT {opt.split('(')[0]}"]


def test_a_tasks_userid_and_screen_are_stated_only_when_given():
    """#5126 (X19): "userid" (1 to 8 characters) and "screen" ([rows, columns], of a stated termid) -- the scenario's,
    else the case's; absent from the result unless stated, malformed refused."""
    case = {"termid": "T001", "userid": "CICSUSER", "screen": [24, 80]}
    got = ec.terminal_facts(case, {"name": "s"})
    assert (got["userid"], got["screen"]) == ("CICSUSER", [24, 80])
    got = ec.terminal_facts(case, {"name": "s", "userid": "BOB", "screen": [43, 80]})
    assert (got["userid"], got["screen"]) == ("BOB", [43, 80])
    assert "userid" not in ec.terminal_facts({"termid": "T001"}, {"name": "s"})
    assert "screen" not in ec.terminal_facts({}, {"name": "s"})
    for bad in ({"userid": ""}, {"userid": "NINECHARS"}, {"userid": "A B"}, {"userid": "A,B"}, {"userid": 7},
                {"termid": "T001", "screen": [24]}, {"termid": "T001", "screen": [24, 0]},
                {"termid": "T001", "screen": [24, "80"]}, {"termid": "T001", "screen": "24 80"},
                {"screen": [24, 80]}):  # fmt: skip
        with pytest.raises(ec.Unsupported):
            ec.terminal_facts({}, {"name": "s", **bad})


def test_assign_startcode_userid_and_the_terminal_facts_translate():
    """#4270 slice 3: STARTCODE / USERID through GGCASGN; FACILITY / SCRNHT / SCRNWD behind TERMCHK (INVREQ RESP2 5 for
    a task with no terminal, then no data area written), with the condition's handling."""
    got = ec.translate_command("ASSIGN STARTCODE(SC) USERID(U)")
    assert got[:6] == ["MOVE 'STARTCOD' TO GG-NAME2", "CALL 'GGCASGN' USING GG-CICS", "MOVE GG-NAME1(1:2) TO SC(1:2)",
                       "MOVE 'USERID' TO GG-NAME2", "CALL 'GGCASGN' USING GG-CICS", "MOVE GG-NAME1(1:8) TO U(1:8)"]  # fmt: skip
    got = ec.translate_command("ASSIGN FACILITY(F) SCRNHT(H) RESP(R)")
    assert got[:4] == ["MOVE 'TERMCHK' TO GG-NAME2", "CALL 'GGCASGN' USING GG-CICS", "IF GG-RESP = 0",
                       "    MOVE 'FACILITY' TO GG-NAME2"]  # fmt: skip
    assert "    MOVE GG-NUM TO H" in got and "MOVE GG-RESP TO R" in got
    assert "    CALL 'GGCCOND' USING GG-CICS" in ec.translate_command("ASSIGN SCRNWD(W)")


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


class _SymbolicIR:
    """An estate whose CSD names a file with install symbols and whose IDCAMS job the engine does not read as a define
    (zECS: ZCEXPIRE.idcams is not JCL), as `record_format` says."""

    files: dict = {}

    def __init__(self, dsname="@ECS_HLQ@.ZCEXPIRE.@ENVIRONMENT@", record_format="V"):
        self.dsname, self.record_format = dsname, record_format

    @staticmethod
    def vsam_stores():
        return []

    def cics_file_lineage(self):
        return [{"program": "p.cbl", "name": "ZCEXPIRE", "definitions": [
            {"file": "ZCEXPIRE", "dsname": self.dsname, "record_format": self.record_format}]}]  # fmt: skip


_SYMBOLS = {"values": {"ECS_HLQ": "ZECS", "ENVIRONMENT": "TEST"}, "why": "this install"}
_VSAM = {"key_offset": 0, "key_length": 4, "reclen": 70, "variable": True, "why": "ZCEXPIRE.idcams KEYS(4 0)"}


def test_install_symbols_are_stated_by_the_case_never_guessed():
    """#5089: `@NAME@` placeholders in a dataset name resolve only to what the case's install_symbols state (names are
    not case-sensitive); the stated file keeps the resolved name; anything unstated or malformed is refused."""
    symbols = ec.install_symbols(_SYMBOLS)
    assert symbols == {"ECS_HLQ": "ZECS", "ENVIRONMENT": "TEST"}
    assert ec.install_symbols(None) == {}
    assert ec.substitute_install_symbols("@ecs_hlq@.ZCEXPIRE.@environment@", symbols) == "ZECS.ZCEXPIRE.TEST"
    assert ec.substitute_install_symbols("@ECS_HLQ@.@OTHER@", symbols) == "ZECS.@OTHER@"  # left: refused by the caller
    assert ec.substitute_install_symbols("PLAIN.NAME", symbols) == "PLAIN.NAME"
    assert ec.substitute_install_symbols("@A@.@A@", {"A": "X"}) == "X.X"  # every occurrence
    assert ec.stub_files(_SymbolicIR(), "p.cbl", {"ZECS.ZCEXPIRE.TEST": {"vsam": _VSAM}}, symbols) == [
        {
            "file": "ZCEXPIRE",
            "dsname": "ZECS.ZCEXPIRE.TEST",
            "base": "ZECS.ZCEXPIRE.TEST",
            "key_offset": 0,
            "key_length": 4,
            "reclen": 70,
            "via": ["the case's install_symbols", "the case's vsam"],
        }  # fmt: skip
    ]


@pytest.mark.parametrize(
    "bad",
    [
        {"values": {"ECS_HLQ": "ZECS"}},  # no why
        {"values": {"ECS_HLQ": "ZECS"}, "why": ""},
        {"values": {}, "why": "x"},
        {"values": {"ECS_HLQ": "zecs"}, "why": "x"},  # not upper case
        {"values": {"ECS_HLQ": 3}, "why": "x"},
        {"values": {"ECS HLQ": "ZECS"}, "why": "x"},
        {"values": {"A": "X", "a": "Y"}, "why": "x"},  # twice
        {"values": {"A": "X"}, "why": "x", "extra": 1},
        ["ECS_HLQ"],
        {"ECS_HLQ": "ZECS"},  # the values are one level down
    ],
)
def test_malformed_install_symbols_are_refused(bad):
    with pytest.raises(ec.Unsupported):
        ec.install_symbols(bad)


def test_an_unstated_install_symbol_or_a_missing_vsam_is_refused():
    """#5089: a symbol the case does not state, no stated KEYS / RECORDSIZE, a V file not acknowledged as stood in for
    by a fixed record length -- each stops the case by name; a stale key (a symbol no name uses) is not an error."""
    only_hlq = ec.install_symbols({"values": {"ECS_HLQ": "ZECS"}, "why": "x"})
    with pytest.raises(ec.Unsupported, match="install symbol the case does not state"):
        ec.stub_files(_SymbolicIR(), "p.cbl", {"ZECS.ZCEXPIRE.TEST": {"vsam": _VSAM}}, only_hlq)
    symbols = ec.install_symbols(_SYMBOLS)
    for datasets in ({}, {"ZECS.ZCEXPIRE.TEST": {}}, {"ZECS.ZCEXPIRE.TEST": {"vsam": {**_VSAM, "why": ""}}},
                     {"ZECS.ZCEXPIRE.TEST": {"vsam": {**_VSAM, "reclen": "70"}}},
                     {"ZECS.ZCEXPIRE.TEST": {"vsam": {k: v for k, v in _VSAM.items() if k != "key_length"}}}):  # fmt: skip
        with pytest.raises(ec.Unsupported, match="no IDCAMS DEFINE"):
            ec.stub_files(_SymbolicIR(), "p.cbl", datasets, symbols)
    with pytest.raises(ec.Unsupported, match="variable-length"):
        ec.stub_files(_SymbolicIR(), "p.cbl", {"ZECS.ZCEXPIRE.TEST": {"vsam": {**_VSAM, "variable": False}}}, symbols)
    fixed = ec.stub_files(_SymbolicIR(record_format="F"), "p.cbl",
                          {"ZECS.ZCEXPIRE.TEST": {"vsam": {**_VSAM, "variable": False}}}, symbols)  # fmt: skip
    assert fixed[0]["reclen"] == 70
    # no symbols stated: the name stays symbolic and is refused as before (the engine's candidate join is separate)
    with pytest.raises(ec.Unsupported, match="no IDCAMS DEFINE"):
        ec.stub_files(_SymbolicIR(), "p.cbl", {"ZECS.ZCEXPIRE.TEST": {"vsam": _VSAM}})
    # a name with no symbols at all is not touched by the stated ones
    with pytest.raises(ec.Unsupported, match="no IDCAMS DEFINE"):
        ec.stub_files(_SymbolicIR(dsname="PLAIN.ZCEXPIRE"), "p.cbl", {"PLAIN.ZCEXPIRE": {"vsam": _VSAM}}, symbols)


def test_a_retrieve_is_compared_as_the_task_records_it():
    """#5089: RETRIEVE's resp, length and data (INTO) and the RTRANSID / RTERMID / QUEUE it returned, from the stub's
    log and from CicsTask's event -- ENDDATA, a NORMAL record, a LENGERR truncation and a RETRIEVE with no INTO."""
    import base64

    assert ec._cobol_retrieve({"resp": "29", "len": "-1", "copied": "0", "into": "1"}, b"", "cp037") == {
        "resp": "ENDDATA", "length": None, "data": None}  # fmt: skip
    got = ec._cobol_retrieve({"resp": "0", "len": "3", "copied": "3", "into": "1", "rtransid": "5a583031"}, b"abc",
                             "ascii")  # fmt: skip
    assert got == {"resp": "NORMAL", "length": 3, "data": "abc", "rtransid": "ZX01"}
    assert ec._cobol_retrieve({"resp": "22", "len": "9", "copied": "2", "into": "1"}, b"ab", "ascii")["length"] == 9
    assert ec._cobol_retrieve({"resp": "0", "len": "0", "copied": "0", "into": "0"}, b"", "ascii")["length"] is None
    java = {"event": "RETRIEVE", "resp": "NORMAL", "length": 3, "data": base64.b64encode(b"\xc1\xc2\xc3").decode()}
    assert ec.java_retrieve_as_compared(java)["data"] == "ABC"  # the region's EBCDIC page
    assert ec.java_retrieve_as_compared({"resp": "ENDDATA", "data": None})["data"] is None


def test_an_esds_is_compared_in_arrival_order():
    """#4213: an ESDS has no key -- its records' order is their RBAs, so it is data and is compared as it is."""
    files = [{"base": "LOG", "reclen": 2, "key_offset": 0, "key_length": 0, "organization": "ESDS"}]
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        (tmp / "s.LOG.out").write_bytes(b"BBAA")
        diff = ec.compare_files({"datasets": {"LOG": {}}}, Path("."), files, {"LOG": b"AABB"}, tmp, "s")
        assert diff["LOG"]["equal"] == 0 and diff["LOG"]["records"] == 2


# ---- #4270 spec PR 3: the stub refuses what the det translator refuses, with the same message -----------------------
_SPEC_BASE = {  # a minimal body of each command, to which one option is added
    "PUT CONTAINER": "PUT CONTAINER('C') FROM(WS-A)", "GET CONTAINER": "GET CONTAINER('C') INTO(WS-A)",
    "DELETE CONTAINER": "DELETE CONTAINER('C')", "START": "START TRANSID('T1')", "RETRIEVE": "RETRIEVE INTO(WS-A)",
    "CANCEL": "CANCEL REQID('R1')", "RUN": "RUN TRANSID('T1') CHILD(WS-C)", "ASSIGN": "ASSIGN USERID(WS-U)",
    "SEND TEXT": "SEND TEXT FROM(WS-A)", "READ": "READ FILE('F') INTO(WS-A) RIDFLD(WS-K)",
    "WRITE": "WRITE FILE('F') FROM(WS-A) RIDFLD(WS-K)", "REWRITE": "REWRITE FILE('F') FROM(WS-A)",
    "STARTBR": "STARTBR FILE('F') RIDFLD(WS-K)", "READNEXT": "READNEXT FILE('F') INTO(WS-A) RIDFLD(WS-K)",
    "ENDBR": "ENDBR FILE('F')", "DELETE": "DELETE FILE('F') RIDFLD(WS-K)", "LINK": "LINK PROGRAM('P')",
    "XCTL": "XCTL PROGRAM('P')", "RETURN": "RETURN", "READQ TS": "READQ TS QUEUE('Q') INTO(WS-A)",
    "WRITEQ TS": "WRITEQ TS QUEUE('Q') FROM(WS-A)", "WRITEQ TD": "WRITEQ TD QUEUE('Q') FROM(WS-A)",
    "RECEIVE": "RECEIVE INTO(WS-A)", "RECEIVE MAP": "RECEIVE MAP('M') INTO(WS-A)",
    "SEND MAP": "SEND MAP('M') FROM(WS-A)", "SEND CONTROL": "SEND CONTROL ERASE", "ENQ": "ENQ RESOURCE(WS-R)",
    "GET COUNTER": "GET COUNTER('C') VALUE(WS-V)", "ABEND": "ABEND ABCODE('XXXX')",
}  # fmt: skip


@pytest.mark.parametrize("key", sorted(_SPEC_BASE))
def test_the_stub_refuses_each_option_the_spec_refuses_with_the_translators_message(key):
    """#4270 spec PR 3 (cics_command_spec.md section 9, decision 3): every option the command's spec entry refuses,
    and one in neither of its tables, is Unsupported with SPEC[key].refusal_message -- the det translator's CicsError
    text -- and never ignored (START, RETRIEVE, CANCEL and SEND TEXT used deny-lists, and ignored the rest)."""
    from gitgalaxy.standards.cics.commands import COMMANDS

    for o in [*COMMANDS[key].refused, "GGNOSUCH"]:
        with pytest.raises(ec.Unsupported) as e:
            ec.translate_command(f"{_SPEC_BASE[key]} {o}(WS-X)")
        assert str(e.value) == COMMANDS[key].refusal_message([o]), o


def test_the_stub_checks_the_translators_option_rules():
    """Spec PR 3: LENGTH with FLENGTH, and START LENGTH without FROM, are refused as the translator refuses them (the
    stub took LENGTH, and moved a length with no area)."""
    for body, msg in [("START TRANSID('T1') FROM(A) LENGTH(5) FLENGTH(5)", "LENGTH and FLENGTH together"),
                      ("RETRIEVE INTO(A) LENGTH(L) FLENGTH(L)", "LENGTH and FLENGTH together"),
                      ("RECEIVE INTO(A) MAXLENGTH(5) MAXFLENGTH(5)", "MAXLENGTH and MAXFLENGTH together"),
                      ("START TRANSID('T1') LENGTH(5)", "START LENGTH without FROM"),
                      ("START TRANSID('T1') INTERVAL(5) TIME(5)", "START INTERVAL and TIME: one expiry option"),
                      ("PUT CONTAINER('C') FROM(A) BIT CHAR", "PUT CONTAINER BIT and CHAR: one data type"),
                      ("LINK PROGRAM('P') CHANNEL('C') LENGTH(5)",
                       "LINK CHANNEL with COMMAREA / LENGTH: one or the other")]:  # fmt: skip
        with pytest.raises(ec.Unsupported, match=f"^{msg}$"):
            ec.translate_command(body)


def test_a_whole_command_refusal_gives_the_spec_reason_and_dfhresp_is_the_spec():
    from gitgalaxy.standards.cics.resp import DFHRESP

    with pytest.raises(ec.Unsupported) as e:
        ec.translate_command("GETMAIN64 SET(P) FLENGTH(10)")
    assert str(e.value).startswith("EXEC CICS GETMAIN64 not modelled (storage CICS acquires")
    assert e.value.features == ["GETMAIN64"]
    with pytest.raises(ec.Unsupported, match=r"^line 2: EXEC CICS GETMAIN64 not modelled \("):  # (named once)
        ec.translate("       PROCEDURE DIVISION.\n           EXEC CICS GETMAIN64 SET(P) FLENGTH(10) END-EXEC.\n")
    assert ec.DFHRESP == DFHRESP and ec.DFHRESP["VOLIDERR"] == 71 and ec.DFHRESP["NOSPOOL"] == 80
    assert all(ec.CICS_RESP[c] == DFHRESP[c] for c in ec.CICS_RESP)


def test_bif_deedit_terminal_uctranst_and_dfhvalue_become_stub_calls():
    """#4415 slice 1 (register X26): BIF DEEDIT FIELD LENGTH -> GGCDEED (LENGTH in GG-NUM, FIELD by reference and its
    size by value; LENGTH defaults to the field's); INQUIRE / SET TERMINAL UCTRANST -> GGCINQT / GGCSETT (the CVDA in
    GG-NUM); DFHVALUE(name) is IBM's CVDA number, an unknown name refused by name. Other options are the spec's refusals."""
    d = ec.translate_command("BIF DEEDIT FIELD(WS-F) LENGTH(9) RESP(R)")
    assert d[:3] == ["MOVE 9 TO GG-NUM", "CALL 'GGCDEED' USING GG-CICS", "    BY REFERENCE WS-F"]
    assert "MOVE LENGTH OF WS-F TO GG-NUM" in ec.translate_command("BIF DEEDIT FIELD(WS-F)")
    inq = ec.translate_command("INQUIRE TERMINAL(EIBTRMID) UCTRANST(WS-U) RESP(R)")
    assert inq[:3] == ["MOVE EIBTRMID TO GG-NAME1", "CALL 'GGCINQT' USING GG-CICS", "IF GG-RESP = 0"]
    assert "    MOVE GG-NUM TO WS-U" in inq
    st = ec.translate_command("SET TERMINAL(EIBTRMID) UCTRANST(DFHVALUE(NOUCTRAN)) RESP(R)")
    assert st[:3] == ["MOVE EIBTRMID TO GG-NAME1", "MOVE DFHVALUE(NOUCTRAN) TO GG-NUM", "CALL 'GGCSETT' USING GG-CICS"]
    with pytest.raises(ec.Unsupported, match="only the terminal's translation state"):
        ec.translate_command("INQUIRE TERMINAL(EIBTRMID) NETNAME(WS-N)")
    with pytest.raises(ec.Unsupported, match="SET TERMINAL without UCTRANST"):
        ec.translate_command("SET TERMINAL(EIBTRMID)")
    src = "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. T.\n       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n       PROCEDURE DIVISION.\n           MOVE DFHVALUE(IMMEDIATE) TO WS-A.\n           MOVE DFHVALUE(NOSUCH) TO WS-B.\n"
    with pytest.raises(ec.Unsupported, match=r"DFHVALUE\(NOSUCH\) is not a documented CVDA"):
        ec.translate(src)
    assert (
        "MOVE 2 TO WS-A" in ec.translate(src.replace("NOSUCH", "DELETE"))[0]
        and "MOVE 292 TO WS-B" in (ec.translate(src.replace("NOSUCH", "DELETE"))[0])
    )


def test_deleteq_ts_inquire_association_and_query_counter_become_stub_calls():
    """#4415 slice 2 (register X29): DELETEQ TS -> GGCDELQ (the queue in GG-QNAME); INQUIRE ASSOCIATION(EIBTASKN) -> one
    GGCINQA call per origin option (GG-FLAGS names it; the 8 characters in GG-NAME1, the CVDA in GG-NUM), refused with
    none; QUERY COUNTER -> GGCQCNT (the value in GG-NUM). Other operands and options are refused by name."""
    d = ec.translate_command("DELETEQ TS QUEUE(WS-Q) RESP(R)")
    assert d[:2] == ["MOVE WS-Q TO GG-QNAME", "CALL 'GGCDELQ' USING GG-CICS"] and "MOVE GG-RESP TO R" in d
    assert ec.translate_command("DELETEQ QNAME('LONGQUEUENAME') NOHANDLE")[1] == "CALL 'GGCDELQ' USING GG-CICS"
    with pytest.raises(ec.Unsupported, match="QUEUE"):
        ec.translate_command("DELETEQ TS")
    with pytest.raises(ec.Unsupported, match="SYSID"):
        ec.translate_command("DELETEQ TS QUEUE(WS-Q) SYSID('AAAA')")
    a = ec.translate_command("INQUIRE ASSOCIATION(EIBTASKN) ODAPPLID(WS-A) ODFACILTYPE(WS-T)")
    assert (
        a[:4]
        == [
            "MOVE 'ODAPPLID' TO GG-FLAGS",
            "CALL 'GGCINQA' USING GG-CICS",
            "MOVE GG-NAME1 TO WS-A",
            "MOVE 'ODFACILTYPE' TO GG-FLAGS",
        ]
        and "MOVE GG-NUM TO WS-T" in a
    )
    with pytest.raises(ec.Unsupported, match="without an origin option"):
        ec.translate_command("INQUIRE ASSOCIATION(EIBTASKN) RESP(R) RESP2(R2)")
    with pytest.raises(ec.Unsupported, match="only the task's own number, EIBTASKN"):
        ec.translate_command("INQUIRE ASSOCIATION(WS-N) ODAPPLID(WS-A)")
    with pytest.raises(ec.Unsupported, match="only the origin data"):
        ec.translate_command("INQUIRE ASSOCIATION(EIBTASKN) ODTASKID(WS-A)")
    q = ec.translate_command("QUERY COUNTER(WS-C) POOL(WS-P) VALUE(WS-V) RESP(R)")
    assert q[:3] == ["MOVE WS-C TO GG-QNAME", "MOVE WS-P TO GG-NAME1", "CALL 'GGCQCNT' USING GG-CICS"]
    assert q[3:9] == [
        "    BY REFERENCE WS-V",
        "    BY VALUE LENGTH OF WS-V",
        "    BY REFERENCE GG-NAME2",
        "    BY VALUE 0",
        "    BY REFERENCE GG-NAME2",
        "    BY VALUE 0",
    ]
    with pytest.raises(ec.Unsupported, match="VALUE"):
        ec.translate_command("QUERY COUNTER(WS-C)")
    assert "MOVE GG-NAME1 TO" not in " ".join(ec.translate_command("RECEIVE MAP('M') MAPSET('S') INTO(WS-I) TERMINAL"))


def test_define_and_delete_counter_become_stub_calls():
    """#4270 (register X30): DEFINE COUNTER -> GGCDCNT, DELETE COUNTER -> GGCXCNT;
    NOSUSPEND is refused by name; GET COUNTER takes RESP2. (#4770, X45: DCOUNTER is the doubleword form; #5039, X50:
    fullword limits.)"""
    d = ec.translate_command("DEFINE COUNTER(WS-C) POOL(WS-P) VALUE(WS-V) RESP(R) RESP2(R2)")
    assert d[:3] == [
        "MOVE WS-C TO GG-QNAME",
        "MOVE WS-P TO GG-NAME1",
        "CALL 'GGCDCNT' USING GG-CICS",
    ]
    assert d[3:9] == [
        "    BY REFERENCE WS-V",
        "    BY VALUE LENGTH OF WS-V",
        "    BY REFERENCE GG-NAME2",
        "    BY VALUE 0",
        "    BY REFERENCE GG-NAME2",
        "    BY VALUE 0",
    ]
    assert "MOVE GG-RESP2 TO R2" in d
    assert ec.translate_command("DEFINE COUNTER(WS-C) RESP(R)").count("    BY VALUE 0") == 3
    x = ec.translate_command("DELETE COUNTER(WS-C) POOL(WS-P) RESP(R)")
    assert x[:3] == ["MOVE WS-C TO GG-QNAME", "MOVE WS-P TO GG-NAME1", "CALL 'GGCXCNT' USING GG-CICS"]
    for bad in (
        "DEFINE COUNTER(WS-C) MINIMUM(WS-M)",
        "DEFINE DCOUNTER(WS-C) MINIMUM(WS-M)",
    ):
        with pytest.raises(ec.Unsupported, match="COUNTER|DCOUNTER"):
            ec.translate_command(bad)
    assert "MOVE GG-RESP2 TO R2" in ec.translate_command("GET COUNTER(WS-C) VALUE(WS-V) RESP(R) RESP2(R2)")


def test_inquire_urimap_browse_and_write_operator_become_stub_calls():
    """#4270 zECS (register X32): INQUIRE URIMAP START / NEXT / END -> GGCURIB (GG-FLAGS names the step); after a NEXT, one
    GGCURIP per output option copies the definition's name / PATH / TRANSACTION to the program's area (at most its length);
    WRITE OPERATOR -> GGCWTO with the area and its length. Other operands and options are refused by name."""
    s = ec.translate_command("INQUIRE URIMAP START NOHANDLE")
    assert s == ["MOVE 'START' TO GG-FLAGS", "CALL 'GGCURIB' USING GG-CICS", "MOVE GG-RESP TO EIBRESP",
                 "MOVE GG-RESP2 TO EIBRESP2"]  # fmt: skip
    n = ec.translate_command("INQUIRE URIMAP(WS-M) PATH(WS-P) TRANSACTION(WS-T) NEXT NOHANDLE")
    assert n[:2] == ["MOVE 'NEXT' TO GG-FLAGS", "CALL 'GGCURIB' USING GG-CICS"] and n[2] == "IF GG-RESP = 0"
    assert (
        "    MOVE 'PATH' TO GG-FLAGS" in n
        and "        BY VALUE LENGTH OF WS-P" in n
        and "        BY REFERENCE WS-M" in n
    )
    with pytest.raises(ec.Unsupported, match="more than one of START, NEXT and END"):
        ec.translate_command("INQUIRE URIMAP(WS-M) PATH(WS-P) NEXT END")
    with pytest.raises(ec.Unsupported, match="returns no definition"):
        ec.translate_command("INQUIRE URIMAP END PATH(WS-P)")
    with pytest.raises(ec.Unsupported, match="only the URIMAP's name"):
        ec.translate_command("INQUIRE URIMAP(WS-M) HOST(WS-P) NEXT")
    w = ec.translate_command("WRITE OPERATOR TEXT(WS-MSG) NOHANDLE")
    assert w[:3] == ["MOVE LENGTH OF WS-MSG TO GG-LEN", "CALL 'GGCWTO' USING GG-CICS", "    BY REFERENCE WS-MSG"]
    with pytest.raises(ec.Unsupported, match="without TEXT"):
        ec.translate_command("WRITE OPERATOR")
    with pytest.raises(ec.Unsupported, match="data area"):
        ec.translate_command("WRITE OPERATOR TEXT('HELLO')")
    with pytest.raises(ec.Unsupported, match="only the plain message"):
        ec.translate_command("WRITE OPERATOR TEXT(WS-MSG) CRITICAL")


def test_web_open_converse_close_become_stub_calls():
    """#4767 zECS (register X35): WEB OPEN -> GGCWOPN (URIMAP: the name in GG-NAME1; HOST: HOSTLENGTH, SCHEME, PORTNUMBER in
    GG-LEN / GG-ITEM / GG-NUM), WEB CONVERSE -> GGCWCNV (METHOD, MAXLENGTH -- INTO's length when omitted -- and the lengths
    in GG fields, every area by reference with its length), TOLENGTH / STATUSCODE moved back when a response came back,
    WEB CLOSE -> GGCWCLS. The option rules as the det translator's."""
    u = ec.translate_command("WEB OPEN SESSTOKEN(WS-TOK) URIMAP(WS-URI) NOHANDLE")
    assert u[:3] == ["MOVE WS-URI TO GG-NAME1", "MOVE 'URIMAP' TO GG-FLAGS", "CALL 'GGCWOPN' USING GG-CICS"]
    h = ec.translate_command(
        "WEB OPEN HOST(WS-H) HOSTLENGTH(WS-HL) PORTNUMBER(WS-P) SCHEME(WS-S) SESSTOKEN(WS-TOK) NOHANDLE"
    )
    assert h[:5] == ["MOVE WS-HL TO GG-LEN", "MOVE WS-S TO GG-ITEM", "MOVE WS-P TO GG-NUM", "MOVE 'HOST PORT' TO GG-FLAGS",
                     "CALL 'GGCWOPN' USING GG-CICS"]  # fmt: skip
    assert "    BY REFERENCE WS-H" in h and "    BY VALUE LENGTH OF WS-H" in h
    v = ec.translate_command(
        "WEB CONVERSE SESSTOKEN(WS-TOK) PATH(WS-PATH) PATHLENGTH(WS-PL) METHOD(WS-M) "
        "MEDIATYPE(WS-MT) INTO(WS-IN) TOLENGTH(WS-LEN) MAXLENGTH(WS-LEN) STATUSCODE(WS-SC) "
        "STATUSLEN(WS-SL) STATUSTEXT(WS-ST) NOOUTCONVERT NOHANDLE"
    )
    assert v[:7] == ["MOVE WS-M TO GG-NUM", "MOVE WS-LEN TO GG-LEN", "MOVE WS-SL TO GG-ITEM", "MOVE WS-PL TO GG-HOURS",
                     "MOVE 0 TO GG-MINS", "MOVE 0 TO GG-SECS", "MOVE 'PATH MEDIA' TO GG-FLAGS"]  # fmt: skip
    assert v[7] == "CALL 'GGCWCNV' USING GG-CICS" and v[8] == "    BY REFERENCE WS-TOK"
    assert v[9:11] == ["    BY REFERENCE WS-PATH", "    BY VALUE LENGTH OF WS-PATH"]
    assert v[11:13] == ["    BY REFERENCE GG-QNAME", "    BY VALUE LENGTH OF GG-QNAME"]  # (no QUERYSTRING)
    i = v.index("IF GG-RESP = 0 OR (GG-RESP = 22 AND GG-RESP2 = 57)")
    assert v[i + 1 : i + 4] == ["    MOVE GG-LEN TO WS-LEN", "    MOVE GG-NUM TO WS-SC", "END-IF"]
    d = ec.translate_command(
        "WEB CONVERSE SESSTOKEN(WS-TOK) PATH(WS-PATH) PATHLENGTH(WS-PL) METHOD(WS-M) INTO(WS-IN) NOHANDLE"
    )
    assert d[1] == "MOVE LENGTH OF WS-IN TO GG-LEN" and d[2] == "MOVE -1 TO GG-ITEM"
    assert ec.translate_command("WEB CLOSE SESSTOKEN(WS-TOK) NOHANDLE")[:2] == ["CALL 'GGCWCLS' USING GG-CICS",
                                                                                 "    BY REFERENCE WS-TOK"]  # fmt: skip
    for bad, why in (("WEB OPEN SESSTOKEN(WS-TOK)", "one of URIMAP and HOST"),
                     ("WEB OPEN SESSTOKEN(WS-TOK) HOST(WS-H) HOSTLENGTH(WS-HL)", "no default scheme"),
                     ("WEB OPEN SESSTOKEN(WS-TOK) URIMAP(WS-URI) SCHEME(WS-S)", "SCHEME without HOST"),
                     ("WEB CONVERSE SESSTOKEN(WS-TOK) METHOD(WS-M)", "without INTO"),
                     ("WEB CONVERSE SESSTOKEN(WS-TOK) METHOD(WS-M) INTO(WS-IN) FROM(WS-F)", "FROM without FROMLENGTH"),
                     ("WEB CONVERSE SESSTOKEN(WS-TOK) METHOD(WS-M) INTO(WS-IN) NOTRUNCATE", "later RECEIVEs"),
                     ("WEB CONVERSE SESSTOKEN(WS-TOK) METHOD(WS-M) INTO(WS-IN) CLIENTCONV(WS-C) NOOUTCONVERT",
                      "more than one conversion option"),
                     ("WEB CLOSE", "without SESSTOKEN")):  # fmt: skip
        with pytest.raises(ec.Unsupported, match=why):
            ec.translate_command(bad)


def test_web_parse_url_becomes_a_stub_call():
    """#4767 zECS (register X36): WEB PARSE URL -> GGCWPRS (URLLENGTH, HOSTLENGTH / PATHLENGTH / QUERYSTRLEN in GG-LEN /
    GG-HOURS / GG-MINS / GG-SECS, GG-FLAGS the pieces asked for, every area by reference with its length); on NORMAL only the
    pieces' lengths and PORTNUMBER move back. The option rules as the det translator's."""
    t = ec.translate_command(
        "WEB PARSE URL(WS-U) URLLENGTH(WS-UL) SCHEMENAME(WS-S) HOST(WS-H) HOSTLENGTH(WS-HL) PORTNUMBER(WS-P) NOHANDLE"
    )
    assert t[:5] == ["MOVE WS-UL TO GG-LEN", "MOVE WS-HL TO GG-HOURS", "MOVE 0 TO GG-MINS", "MOVE 0 TO GG-SECS",
                     "MOVE 'SCHEME HOST' TO GG-FLAGS"]  # fmt: skip
    assert t[5] == "CALL 'GGCWPRS' USING GG-CICS" and t[6:10] == ["    BY REFERENCE WS-U", "    BY VALUE LENGTH OF WS-U",
                                                                 "    BY REFERENCE WS-S", "    BY VALUE LENGTH OF WS-S"]  # fmt: skip
    i = t.index("IF GG-RESP = 0")
    assert t[i + 1 : i + 4] == ["    MOVE GG-HOURS TO WS-HL", "    MOVE GG-NUM TO WS-P", "END-IF"]
    for bad, why in (("WEB PARSE URL(WS-U)", "without URLLENGTH"),
                     ("WEB PARSE URL(WS-U) URLLENGTH(WS-UL) HOST(WS-H)", "HOST without HOSTLENGTH"),
                     ("WEB PARSE URL(WS-U) URLLENGTH(WS-UL) HOSTTYPE(WS-T)", "IPv6 host is refused")):  # fmt: skip
        with pytest.raises(ec.Unsupported, match=why):
            ec.translate_command(bad)


def test_web_send_becomes_a_stub_call():
    """#4767 zECS (register X37): WEB SEND -> GGCWSND (FROMLENGTH, ACTION, STATUSCODE -1 when absent, STATUSLEN -1 when absent,
    the conversion in GG fields, GG-FLAGS the optional areas given, every area by reference with its length). The option
    rules as the det translator's."""
    t = ec.translate_command(
        "WEB SEND FROM(WS-F) FROMLENGTH(WS-FL) MEDIATYPE(WS-M) ACTION(WS-A) STATUSCODE(WS-S) STATUSTEXT(WS-T) SRVCONVERT "
        "NOHANDLE"
    )
    assert t[:7] == ["MOVE WS-FL TO GG-LEN", "MOVE WS-A TO GG-ITEM", "MOVE WS-S TO GG-NUM", "MOVE -1 TO GG-HOURS",
                     "MOVE 1 TO GG-MINS", "MOVE 'MEDIA STEXT' TO GG-FLAGS", "CALL 'GGCWSND' USING GG-CICS"]  # fmt: skip
    assert t[7:9] == ["    BY REFERENCE WS-F", "    BY VALUE LENGTH OF WS-F"]
    ct = ec.translate_command("WEB SEND CONTAINER(WS-K) CHANNEL(WS-C) MEDIATYPE(WS-M) ACTION(WS-A) NOHANDLE")
    assert ct[:7] == ["MOVE 0 TO GG-LEN", "MOVE WS-A TO GG-ITEM", "MOVE -1 TO GG-NUM", "MOVE -1 TO GG-HOURS",
                      "MOVE 0 TO GG-MINS", "MOVE 'MEDIA CHANNEL' TO GG-FLAGS", "MOVE WS-K TO GG-QNAME"]  # fmt: skip
    assert ct[7] == "MOVE WS-C TO GG-CHAN" and "CALL 'GGCWSCT' USING GG-CICS" in ct  # (#5037 X37: a container's data)
    cn = ec.translate_command("WEB SEND CONTAINER(WS-K) ACTION(WS-A) NOHANDLE")
    assert (
        "MOVE 'CHANNEL' TO GG-FLAGS" not in cn and "MOVE SPACES TO GG-FLAGS" in cn
    )  # (no CHANNEL: the current channel)
    d = ec.translate_command("WEB SEND FROM(WS-F) FROMLENGTH(WS-FL) NOHANDLE")
    assert d[:6] == ["MOVE WS-FL TO GG-LEN", "MOVE 0 TO GG-ITEM", "MOVE -1 TO GG-NUM", "MOVE -1 TO GG-HOURS",
                     "MOVE 0 TO GG-MINS", "MOVE SPACES TO GG-FLAGS"]  # fmt: skip
    dd = ec.translate_command("WEB SEND DOCTOKEN(WS-D) MEDIATYPE(WS-M) ACTION(WS-A) STATUSCODE(WS-S) NOHANDLE")
    at = dd.index("CALL 'GGCWSDC' USING GG-CICS")  # (#4767: the response is the document the token names)
    assert "MOVE 0 TO GG-SECS" in dd[:at]  # (#4941 X37: DOCSTATUS not given)
    ds = ec.translate_command("WEB SEND DOCTOKEN(WS-D) ACTION(WS-A) DOCSTATUS(WS-X) NOHANDLE")
    assert "MOVE WS-X TO GG-SECS" in ds[: ds.index("CALL 'GGCWSDC' USING GG-CICS")]
    assert dd[0] == "MOVE 0 TO GG-LEN" and dd[at + 1 : at + 3] == [
        "    BY REFERENCE WS-D",
        "    BY VALUE LENGTH OF WS-D",
    ]
    for bad, why in (("WEB SEND FROMLENGTH(WS-FL)", "needs exactly one of FROM"),
                     ("WEB SEND FROM(WS-F) FROMLENGTH(WS-FL) DOCTOKEN(WS-D)", "needs exactly one of FROM"),
                     ("WEB SEND DOCTOKEN(WS-D) FROMLENGTH(WS-FL)", "FROMLENGTH without FROM"),
                     ("WEB SEND FROM(WS-F) FROMLENGTH(WS-FL) DOCSTATUS(WS-X)", "DOCSTATUS without DOCTOKEN"),
                     ("WEB SEND FROM(WS-F)", "FROM without FROMLENGTH"),
                     ("WEB SEND FROM(WS-F) FROMLENGTH(WS-FL) SRVCONVERT NOSRVCONVERT", "both SRVCONVERT and NOSRVCONVERT"),
                     ("WEB SEND FROM(WS-F) FROMLENGTH(WS-FL) STATUSLEN(WS-SL)", "STATUSLEN without STATUSTEXT"),
                     ("WEB SEND FROM(WS-F) FROMLENGTH(WS-FL) CHUNKING(WS-C)", "chunked response"),
                     ("WEB SEND CONTAINER(WS-K) FROM(WS-F) FROMLENGTH(WS-FL)", "needs exactly one of FROM"),
                     ("WEB SEND CONTAINER(WS-K) DOCTOKEN(WS-D)", "needs exactly one of FROM"),
                     ("WEB SEND CHANNEL(WS-C) FROM(WS-F) FROMLENGTH(WS-FL)", "CHANNEL without CONTAINER"),
                     ("WEB SEND CONTAINER(WS-K) CHUNKING(WS-C)", "chunked response"),
                     ("WEB SEND CONTAINER(WS-K) HOSTCODEPAGE(WS-H)", "code-page conversion"),
                     ("WEB SEND CONTAINER(WS-K) CHARACTERSET(WS-H)", "code-page conversion"),
                     ("WEB SEND CONTAINER(WS-K) CLNTCODEPAGE(WS-H)", "code-page conversion"),
                     ("WEB SEND CONTAINER(WS-K) CLOSESTATUS(WS-H)", "closing the connection"),
                     ("WEB SEND CONTAINER(WS-K) LENGTH(WS-H)", "LENGTH is kept for upgrade only")):  # fmt: skip
        with pytest.raises(ec.Unsupported, match=why):
            ec.translate_command(bad)


def test_web_extract_becomes_a_stub_call():
    """#4767 zECS (register X38): WEB EXTRACT -> GGCWEXT (each length option in GG-LEN / GG-HOURS / GG-MINS / GG-SECS /
    GG-ITEM, GG-FLAGS the pieces asked for, every piece's area by reference with its length), then on NORMAL the lengths,
    PORTNUMBER, SCHEME (1096 / 1029) and REQUESTTYPE (1033) moved back. The option rules as the det translator's."""
    t = ec.translate_command("WEB EXTRACT SCHEME(WS-S) HOST(WS-H) HOSTLENGTH(WS-HL) PATH(WS-P) PATHLENGTH(WS-PL) "
                             "PORTNUMBER(WS-N) REQUESTTYPE(WS-R) NOHANDLE")  # fmt: skip
    assert t[:6] == ["MOVE WS-HL TO GG-LEN", "MOVE 0 TO GG-HOURS", "MOVE 0 TO GG-MINS", "MOVE WS-PL TO GG-SECS",
                     "MOVE 0 TO GG-ITEM", "MOVE 'HOST PATH' TO GG-FLAGS"]  # fmt: skip
    assert t[6] == "CALL 'GGCWEXT' USING GG-CICS" and t[7:9] == ["    BY REFERENCE WS-H", "    BY VALUE LENGTH OF WS-H"]
    tail = "\n".join(t)
    for back in ("MOVE GG-LEN TO WS-HL", "MOVE GG-SECS TO WS-PL", "MOVE GG-NUM TO WS-N", "MOVE 1096 TO WS-S",
                 "IF GG-NAME1(1:5) = 'HTTPS'", "MOVE 1029 TO WS-S", "MOVE 1033 TO WS-R"):  # fmt: skip
        assert back in tail, back
    for bad, why in (("WEB EXTRACT HOST(WS-H)", "HOST without HOSTLENGTH"),
                     ("WEB EXTRACT HTTPMETHOD(WS-M)", "HTTPMETHOD without METHODLENGTH"),
                     ("WEB EXTRACT HTTPVERSION(WS-V)", "HTTPVERSION without VERSIONLEN"),
                     ("WEB EXTRACT QUERYSTRLEN(WS-Q)", "QUERYSTRING without QUERYSTRLEN"),
                     ("WEB EXTRACT SESSTOKEN(WS-T)", "client form"),
                     ("WEB EXTRACT HOSTTYPE(WS-T)", "address format"),
                     ("WEB EXTRACT URIMAP(WS-U)", "URIMAP the request matched")):  # fmt: skip
        with pytest.raises(ec.Unsupported, match=why):
            ec.translate_command(bad)


def test_web_receive_becomes_a_stub_call():
    """#4767 zECS (register X38): WEB RECEIVE INTO -> GGCWRCV (MAXLENGTH in GG-NUM, GG-FLAGS MEDIA when MEDIATYPE is given),
    then LENGTH moved from GG-LEN on NORMAL and on LENGERR 57. SET, NOTRUNCATE, the containers and the code-page options are
    refused by name."""
    t = ec.translate_command(
        "WEB RECEIVE INTO(WS-B) LENGTH(WS-L) MAXLENGTH(WS-M) MEDIATYPE(WS-T) NOSRVCONVERT NOHANDLE"
    )
    assert t[:3] == ["MOVE WS-M TO GG-NUM", "MOVE 'MEDIA' TO GG-FLAGS", "CALL 'GGCWRCV' USING GG-CICS"]
    assert t[3:7] == [
        "    BY REFERENCE WS-B",
        "    BY VALUE LENGTH OF WS-B",
        "    BY REFERENCE WS-T",
        "    BY VALUE LENGTH OF WS-T",
    ]
    assert t[7:10] == ["IF GG-RESP = 0 OR GG-RESP2 = 57", "    MOVE GG-LEN TO WS-L", "END-IF"]
    assert ec.translate_command("WEB RECEIVE INTO(WS-B) MAXLENGTH(WS-M) SRVCONVERT")[1] == "MOVE SPACES TO GG-FLAGS"
    for bad, why in (("WEB RECEIVE", "one of INTO / SET"),
                     ("WEB RECEIVE INTO(WS-B)", "INTO without MAXLENGTH"),
                     ("WEB RECEIVE INTO(WS-B) MAXLENGTH(WS-M) SRVCONVERT NOSRVCONVERT", "both SRVCONVERT and NOSRVCONVERT"),
                     ("WEB RECEIVE SET(WS-P) MAXLENGTH(WS-M)", "SET without LENGTH"),
                     ("WEB RECEIVE INTO(WS-B) MAXLENGTH(WS-M) NOTRUNCATE", "NOTRUNCATE"),
                     ("WEB RECEIVE TOCONTAINER('C')", "container"),
                     ("WEB RECEIVE INTO(WS-B) MAXLENGTH(WS-M) CHARACTERSET(WS-C)", "code-page conversion"),
                     ("WEB RECEIVE INTO(WS-B) MAXLENGTH(WS-M) HOSTCODEPAGE(WS-C)", "code-page conversion"),
                     ("WEB RECEIVE INTO(WS-B) MAXLENGTH(WS-M) SERVERCONV(WS-C)", "SERVERCONV"),
                     ("WEB RECEIVE INTO(WS-B) MAXLENGTH(WS-M) TYPE(WS-C)", "TYPE")):  # fmt: skip
        with pytest.raises(ec.Unsupported, match=why):
            ec.translate_command(bad)


def test_web_read_and_write_httpheader_become_stub_calls():
    """#4767 zECS (register X38): WEB READ HTTPHEADER -> GGCWRDH (NAMELENGTH in GG-LEN, VALUELENGTH in GG-NUM, moved back on
    NORMAL), WEB WRITE HTTPHEADER -> GGCWWRH (the header recorded as WEB-HEADER); the client form is refused."""
    r = ec.translate_command("WEB READ HTTPHEADER(WS-N) NAMELENGTH(WS-NL) VALUE(WS-V) VALUELENGTH(WS-VL) NOHANDLE")
    assert r[:3] == ["MOVE WS-NL TO GG-LEN", "MOVE WS-VL TO GG-NUM", "CALL 'GGCWRDH' USING GG-CICS"]
    assert r[3:7] == [
        "    BY REFERENCE WS-N",
        "    BY VALUE LENGTH OF WS-N",
        "    BY REFERENCE WS-V",
        "    BY VALUE LENGTH OF WS-V",
    ]
    assert r[7:10] == ["IF GG-RESP = 0", "    MOVE GG-NUM TO WS-VL", "END-IF"]
    w = ec.translate_command("WEB WRITE HTTPHEADER(WS-N) NAMELENGTH(WS-NL) VALUE(WS-V) VALUELENGTH(WS-VL) NOHANDLE")
    assert w[:3] == ["MOVE WS-NL TO GG-LEN", "MOVE WS-VL TO GG-NUM", "CALL 'GGCWWRH' USING GG-CICS"]
    assert "GGCWRDH" not in "".join(w) and not any(ln.startswith("IF GG-RESP = 0") for ln in w)
    for form in ("READ", "WRITE"):
        for missing, why in (
            ("NAMELENGTH(WS-NL)", "NAMELENGTH"),
            ("VALUE(WS-V)", "VALUE"),
            ("VALUELENGTH(WS-VL)", "VALUELENGTH"),
        ):
            parts = [
                x
                for x in ("HTTPHEADER(WS-N)", "NAMELENGTH(WS-NL)", "VALUE(WS-V)", "VALUELENGTH(WS-VL)")
                if x != missing
            ]
            with pytest.raises(ec.Unsupported, match=why):
                ec.translate_command(f"WEB {form} " + " ".join(parts))
        with pytest.raises(ec.Unsupported, match="client form"):
            ec.translate_command(
                f"WEB {form} HTTPHEADER(WS-N) NAMELENGTH(WS-NL) VALUE(WS-V) VALUELENGTH(WS-VL) SESSTOKEN(WS-T)"
            )


def test_web_forms_and_browses_become_stub_calls():
    """#4940 (register X38): WEB READ FORMFIELD / QUERYPARM -> GGCWRDP, STARTBROWSE -> GGCWSBR (GG-FLAGS NAME with a start name),
    READNEXT -> GGCWRNX, ENDBROWSE -> GGCWEBR; GG-ITEM names the kind (0 HTTPHEADER, 1 FORMFIELD, 2 QUERYPARM); the lengths go
    back when a value / pair came back. The options the det translator refuses are refused here too."""
    for kind, item in (("FORMFIELD", 1), ("QUERYPARM", 2)):
        r = ec.translate_command(f"WEB READ {kind}(WS-N) NAMELENGTH(WS-NL) VALUE(WS-V) VALUELENGTH(WS-VL) NOHANDLE")
        assert r[:4] == [
            f"MOVE {item} TO GG-ITEM",
            "MOVE WS-NL TO GG-LEN",
            "MOVE WS-VL TO GG-NUM",
            "CALL 'GGCWRDP' USING GG-CICS",
        ]
        assert r[8:11] == ["IF GG-RESP = 0 OR (GG-RESP = 22 AND GG-RESP2 = 5)", "    MOVE GG-NUM TO WS-VL", "END-IF"]
    for kind, item in (("HTTPHEADER", 0), ("FORMFIELD", 1), ("QUERYPARM", 2)):
        e = ec.translate_command(f"WEB ENDBROWSE {kind} NOHANDLE")
        assert e[:2] == [f"MOVE {item} TO GG-ITEM", "CALL 'GGCWEBR' USING GG-CICS"]
        s = ec.translate_command(f"WEB STARTBROWSE {kind} NOHANDLE")
        assert s[:4] == [
            f"MOVE {item} TO GG-ITEM",
            "MOVE 0 TO GG-LEN",
            "MOVE SPACES TO GG-FLAGS",
            "CALL 'GGCWSBR' USING GG-CICS",
        ]
        n = ec.translate_command(f"WEB READNEXT {kind}(WS-N) NAMELENGTH(WS-NL) VALUE(WS-V) VALUELENGTH(WS-VL) NOHANDLE")
        assert n[:4] == [
            f"MOVE {item} TO GG-ITEM",
            "MOVE WS-NL TO GG-LEN",
            "MOVE WS-VL TO GG-NUM",
            "CALL 'GGCWRNX' USING GG-CICS",
        ]
        assert n[8:13] == ["IF GG-RESP = 0 OR (GG-RESP = 22 AND (GG-RESP2 = 4 OR GG-RESP2 = 5))",
                           "    MOVE GG-LEN TO WS-NL", "    MOVE GG-NUM TO WS-VL", "END-IF", "MOVE GG-RESP TO EIBRESP"]  # fmt: skip
    named = ec.translate_command("WEB STARTBROWSE FORMFIELD(WS-N) NAMELENGTH(WS-NL) NOHANDLE")
    assert named[:4] == [
        "MOVE 1 TO GG-ITEM",
        "MOVE WS-NL TO GG-LEN",
        "MOVE 'NAME' TO GG-FLAGS",
        "CALL 'GGCWSBR' USING GG-CICS",
    ]
    assert named[4:6] == ["    BY REFERENCE WS-N", "    BY VALUE LENGTH OF WS-N"]
    for bad, why in (("WEB READ FORMFIELD(WS-N) VALUE(WS-V) VALUELENGTH(WS-VL)", "NAMELENGTH"),
                     ("WEB READ QUERYPARM(WS-N) NAMELENGTH(WS-NL) VALUELENGTH(WS-VL)", "VALUE"),
                     ("WEB READ QUERYPARM(WS-N) NAMELENGTH(WS-NL) VALUE(WS-V)", "VALUELENGTH"),
                     ("WEB READ FORMFIELD(WS-N) NAMELENGTH(WS-NL) VALUE(WS-V) VALUELENGTH(WS-VL) SET(WS-P)", "pointer lane"),
                     ("WEB READ QUERYPARM(WS-N) NAMELENGTH(WS-NL) VALUE(WS-V) VALUELENGTH(WS-VL) HOSTCODEPAGE(WS-C)", "code-page"),
                     ("WEB READ FORMFIELD('A') NAMELENGTH(WS-NL) VALUE(WS-V) VALUELENGTH(WS-VL)", "literal"),
                     ("WEB READNEXT QUERYPARM(WS-N) NAMELENGTH(WS-NL) VALUE(WS-V)", "VALUELENGTH"),
                     ("WEB READNEXT HTTPHEADER NAMELENGTH(WS-NL) VALUE(WS-V) VALUELENGTH(WS-VL)", "HTTPHEADER"),
                     ("WEB READNEXT HTTPHEADER(WS-N) NAMELENGTH(WS-NL) VALUE(WS-V) VALUELENGTH(WS-VL) SESSTOKEN(WS-T)", "client form"),
                     ("WEB STARTBROWSE HTTPHEADER(WS-N)", "not documented"),
                     ("WEB STARTBROWSE FORMFIELD(WS-N)", "without NAMELENGTH"),
                     ("WEB STARTBROWSE QUERYPARM NAMELENGTH(WS-NL)", "NAMELENGTH without a name"),
                     ("WEB STARTBROWSE FORMFIELD HOSTCODEPAGE(WS-C)", "code-page"),
                     ("WEB STARTBROWSE HTTPHEADER SESSTOKEN(WS-T)", "client form")):  # fmt: skip
        with pytest.raises(ec.Unsupported, match=why):
            ec.translate_command(bad)


def test_a_web_header_event_reads_back_and_is_compared():
    """#4767 zECS (X38): a WEB-HEADER line of the stub's events reads back as CicsTask records it; the headers each side wrote
    are compared exactly (name, value, RESP2)."""
    kv = {"name": b"X-Zecs".hex().upper(), "value": b"abc ".hex().upper(), "resp": "0", "resp2": "0"}
    got = ec._cobol_web_header(kv, "latin-1")
    assert got == {"name": "X-Zecs", "value": "abc ", "resp": 0, "resp2": 0}
    java = {"event": "WEB-HEADER", **got}
    assert ec.compare_events([java], [dict(java)])["equal"] == 1
    differs = ec.compare_events([java], [{**java, "value": "abc"}])
    assert differs["diffs"] and differs["diffs"][0]["fields"][0]["field"] == "value"
    res = {"screens": [], "text": [], "events": ["WEB-HEADER name=.. value=.. resp=0 resp2=0"], "webheader": [got]}
    assert ec.cobol_events(res) == [java]


def test_get_dcounter_becomes_a_doubleword_stub_call():
    """#4767 zECS (register X30): GET DCOUNTER -> GGCGDCN (the name in GG-QNAME, the pool in GG-NAME1, VALUE and INCREMENT by
    reference with their lengths; INCREMENT omitted: GG-NAME2 holding 1). The fullword COUNTER form keeps GGCGCNT, and its
    INCREMENT / WRAP are refused."""
    t = ec.translate_command("GET DCOUNTER(WS-N) VALUE(WS-V) INCREMENT(WS-I) WRAP NOHANDLE")
    assert "CALL 'GGCGDCN' USING GG-CICS" in t and "GGCGCNT" not in "".join(t)
    at = t.index("CALL 'GGCGDCN' USING GG-CICS")
    assert t[at + 1 : at + 6] == [
        "    BY REFERENCE WS-V",
        "    BY VALUE LENGTH OF WS-V",
        "    BY REFERENCE WS-I",
        "    BY VALUE LENGTH OF WS-I",
        "    BY VALUE 1",
    ]  # fmt: skip  (#4770: WRAP)
    assert "    BY VALUE 0" in ec.translate_command("GET DCOUNTER(WS-N) VALUE(WS-V) INCREMENT(WS-I) NOHANDLE")
    d = ec.translate_command("GET DCOUNTER(WS-N) VALUE(WS-V) NOHANDLE")
    assert "MOVE X'0000000000000001' TO GG-NAME2" in d and "    BY REFERENCE GG-NAME2" in d
    assert "CALL 'GGCGCNT' USING GG-CICS" in ec.translate_command("GET COUNTER(WS-N) VALUE(WS-V) NOHANDLE")
    for bad, why in (("GET DCOUNTER(WS-N) VALUE('5')", "literal"),):  # (REDUCE / COMPARE / NOSUSPEND: #5039, X53)  # fmt: skip
        with pytest.raises(ec.Unsupported, match=why):
            ec.translate_command(bad)


def test_define_query_delete_dcounter_become_doubleword_stub_calls():
    """#4770 zECS (register X45): DEFINE DCOUNTER -> GGCDDCN with VALUE / MINIMUM / MAXIMUM each an 8-byte area by reference and
    its length (`BY VALUE 0`: omitted -- IBM's defaults), QUERY DCOUNTER -> GGCQDCN likewise, DELETE DCOUNTER -> GGCXCNT. A
    literal, MINIMUM without VALUE, and both forms at once are refused by name."""
    d = ec.translate_command("DEFINE DCOUNTER(WS-C) POOL(WS-P) VALUE(WS-V) MINIMUM(WS-LO) MAXIMUM(WS-HI) RESP(R)")
    assert d[:3] == ["MOVE WS-C TO GG-QNAME", "MOVE WS-P TO GG-NAME1", "CALL 'GGCDDCN' USING GG-CICS"]
    assert d[3:9] == ["    BY REFERENCE WS-V", "    BY VALUE LENGTH OF WS-V", "    BY REFERENCE WS-LO",
                      "    BY VALUE LENGTH OF WS-LO", "    BY REFERENCE WS-HI", "    BY VALUE LENGTH OF WS-HI"]  # fmt: skip
    o = ec.translate_command("DEFINE DCOUNTER(WS-C) NOHANDLE")
    assert o.count("    BY VALUE 0") == 3 and "GGCDCNT" not in "".join(o)
    q = ec.translate_command("QUERY DCOUNTER(WS-C) VALUE(WS-V) MAXIMUM(WS-HI) RESP(R) RESP2(R2)")
    at = q.index("CALL 'GGCQDCN' USING GG-CICS")
    assert q[at + 1 : at + 7] == ["    BY REFERENCE WS-V", "    BY VALUE LENGTH OF WS-V", "    BY REFERENCE GG-NAME2",
                                  "    BY VALUE 0", "    BY REFERENCE WS-HI", "    BY VALUE LENGTH OF WS-HI"]  # fmt: skip
    assert "MOVE GG-RESP2 TO R2" in q
    assert "CALL 'GGCXCNT' USING GG-CICS" in ec.translate_command("DELETE DCOUNTER(WS-C) NOHANDLE")
    for bad, why in (("DEFINE DCOUNTER(WS-C) VALUE(5)", "literal"), ("DEFINE DCOUNTER(WS-C) VALUE(WS-V) MAXIMUM('A')", "literal"),
                     ("DEFINE DCOUNTER(WS-C) MINIMUM(WS-V)", "MINIMUM without VALUE"),
                     ("DEFINE COUNTER(WS-C) DCOUNTER(WS-C)", "one of COUNTER and DCOUNTER"),
                     ("QUERY DCOUNTER(WS-C)", "without VALUE"),
                     ):  # fmt: skip
        with pytest.raises(ec.Unsupported, match=why):
            ec.translate_command(bad)


def test_define_query_counter_become_fullword_stub_calls():
    """#5039 (register X50): DEFINE COUNTER -> GGCDCNT with VALUE / MINIMUM / MAXIMUM each a fullword area by reference and
    its length (`BY VALUE 0`: omitted -- IBM's defaults), QUERY COUNTER -> GGCQCNT likewise, GET COUNTER -> GGCGCNT with
    INCREMENT and WRAP. A literal, MINIMUM without VALUE, and NOSUSPEND are refused."""
    d = ec.translate_command("DEFINE COUNTER(WS-C) POOL(WS-P) VALUE(WS-V) MINIMUM(WS-LO) MAXIMUM(WS-HI) RESP(R)")
    assert d[:3] == ["MOVE WS-C TO GG-QNAME", "MOVE WS-P TO GG-NAME1", "CALL 'GGCDCNT' USING GG-CICS"]
    assert d[3:9] == ["    BY REFERENCE WS-V", "    BY VALUE LENGTH OF WS-V", "    BY REFERENCE WS-LO",
                      "    BY VALUE LENGTH OF WS-LO", "    BY REFERENCE WS-HI", "    BY VALUE LENGTH OF WS-HI"]  # fmt: skip
    o = ec.translate_command("DEFINE COUNTER(WS-C) NOHANDLE")
    assert o.count("    BY VALUE 0") == 3 and "GGCDDCN" not in "".join(o)
    q = ec.translate_command("QUERY COUNTER(WS-C) VALUE(WS-V) MAXIMUM(WS-HI) RESP(R) RESP2(R2)")
    at = q.index("CALL 'GGCQCNT' USING GG-CICS")
    assert q[at + 1 : at + 7] == ["    BY REFERENCE WS-V", "    BY VALUE LENGTH OF WS-V", "    BY REFERENCE GG-NAME2",
                                  "    BY VALUE 0", "    BY REFERENCE WS-HI", "    BY VALUE LENGTH OF WS-HI"]  # fmt: skip
    assert "MOVE GG-RESP2 TO R2" in q
    g = ec.translate_command("GET COUNTER(WS-N) VALUE(WS-V) INCREMENT(WS-I) WRAP NOHANDLE")
    gat = g.index("CALL 'GGCGCNT' USING GG-CICS")
    assert g[gat + 1 : gat + 6] == [
        "    BY REFERENCE WS-V",
        "    BY VALUE LENGTH OF WS-V",
        "    BY REFERENCE WS-I",
        "    BY VALUE LENGTH OF WS-I",
        "    BY VALUE 1",
    ]
    # DEFINE reads its numbers, so a decimal literal is staged big-endian in GG-FLAGS (GenApp's LGSETUP defines VALUE(0))
    lit = ec.translate_command("DEFINE COUNTER(WS-C) VALUE(5) MINIMUM(2) MAXIMUM(99)")
    assert lit[2:5] == ["MOVE X'00000005' TO GG-FLAGS(1:4)", "MOVE X'00000002' TO GG-FLAGS(5:4)",
                        "MOVE X'00000063' TO GG-FLAGS(9:4)"]  # fmt: skip
    assert "    BY REFERENCE GG-FLAGS(5:4)" in lit and "    BY VALUE LENGTH OF GG-FLAGS(9:4)" in lit
    assert "MOVE X'00000000' TO GG-FLAGS(1:4)" in ec.translate_command("DEFINE COUNTER(WS-C) VALUE(0)")
    for bad, why in (("DEFINE COUNTER(WS-C) VALUE(WS-V) MAXIMUM('A')", "literal"),
                     ("QUERY COUNTER(WS-C) VALUE(5)", "literal"),
                     ("DEFINE COUNTER(WS-C) MINIMUM(WS-V)", "MINIMUM without VALUE"),
                     ):  # fmt: skip
        with pytest.raises(ec.Unsupported, match=why):
            ec.translate_command(bad)


def test_the_http_request_is_stated_alike_on_both_sides_and_the_response_compared():
    """#4767 zECS (X37): a case's "http_request" (the scenario's first) is checked and written for the stub as hex in the data's
    page; a WEB-SEND event line reads back as CicsTask records it; the responses are compared exactly."""
    req = {"scheme": "HTTP", "host": "zecs.example", "port": 80, "method": "PUT", "version": "HTTP/1.1", "path": "/k",
           "query": "", "headers": [["Content-Type", "text/plain"]], "mediatype": "text/plain", "body": "v"}  # fmt: skip
    assert ec.http_request({"http_request": req}, {"name": "s"}) == req
    assert ec.http_request({}, {"name": "s"}) is None
    assert (
        ec.http_request(
            {"http_request": req},
            {"name": "s", "http_request": {**req, "method": "GET", "mediatype": None, "body": None}},
        )["method"]
        == "GET"
    )
    for broken in ({**req, "port": 0}, {**req, "scheme": "FTP"}, {**req, "method": "TRACE"}, {**req, "body": None},
                   {**req, "headers": [["a"]]}, {**req, "extra": 1}):  # fmt: skip
        with pytest.raises(ec.Unsupported, match="http_request"):
            ec.http_request({"http_request": broken}, {"name": "s"})
    cfg = ec.http_request_cfg(req, "latin-1").splitlines()
    assert cfg[0] == "R HTTP " + b"zecs.example".hex().upper() + " 80 PUT " + b"/k".hex().upper() + " -"
    assert cfg[1] == "V " + b"HTTP/1.1".hex().upper()  # (#4767 X38: WEB EXTRACT reads the version)
    assert cfg[2] == "B " + b"text/plain".hex().upper() + " " + b"v".hex().upper()  # (WEB RECEIVE reads the body)
    assert cfg[3] == "H " + b"Content-Type".hex().upper() + " " + b"text/plain".hex().upper()
    bare = ec.http_request_cfg({**req, "mediatype": None, "body": None, "headers": []}, "latin-1").splitlines()
    assert [ln[0] for ln in bare] == ["R", "V"]  # (no body: no B line; a request with none is refused by WEB RECEIVE)
    kv = dict(a.split("=", 1) for a in ("WEB-SEND status=404 stext=" + b"NF".hex().upper() + " media=- action=IMMEDIATE "
                                       "resp=0 resp2=0").split()[1:])  # fmt: skip
    got = ec._cobol_web_send(kv, b"gone ", "latin-1")
    assert got == {"status": 404, "statustext": "NF", "mediatype": None, "body": "gone ", "action": "IMMEDIATE",
                   "resp": 0, "resp2": 0}  # fmt: skip
    java = {"event": "WEB-SEND", **got}
    assert ec.compare_events([java], [dict(java)])["equal"] == 1
    differs = ec.compare_events([java], [{**java, "body": "gone"}])  # (a trailing blank is sent: compared exactly)
    assert differs["diffs"] and differs["diffs"][0]["fields"][0]["field"] == "body"


def test_http_peers_are_stated_alike_on_both_sides_and_requests_compared():
    """#4767 zECS (X35): a case's "http_peers" (the scenario's first) is checked, written for the stub as hex in the data's
    page, and a WEB-CONVERSE event line reads back as CicsTask records it; the requests are compared exactly."""
    peer = {"scheme": "HTTP", "host": "zecs.example", "port": 80, "urimap": "ZCCLIENT", "path": "/resources/zc01",
            "exchanges": [{"method": "GET", "path": "/resources/zc01/k1", "query": "", "status": 200, "statustext": "OK",
                           "mediatype": "text/plain", "body": "value"}]}  # fmt: skip
    assert ec.http_peers({"http_peers": [peer]}, {"name": "s"}) == [peer]
    assert ec.http_peers({}, {"name": "s"}) is None
    assert ec.http_peers({"http_peers": [peer]}, {"name": "s", "http_peers": []}) == []
    for broken in ({**peer, "port": 0}, {**peer, "scheme": "FTP"}, {**peer, "urimap": "TOOLONGNAME"},
                   {**peer, "exchanges": [{**peer["exchanges"][0], "method": "TRACE"}]}, {**peer, "extra": 1}):  # fmt: skip
        with pytest.raises(ec.Unsupported, match="http_peers"):
            ec.http_peers({"http_peers": [broken]}, {"name": "s"})
    cfg = ec.http_peers_cfg([peer], "latin-1").splitlines()
    assert cfg[0] == "P HTTP " + b"zecs.example".hex().upper() + " 80 ZCCLIENT " + b"/resources/zc01".hex().upper()
    assert cfg[1].startswith("X GET " + b"/resources/zc01/k1".hex().upper() + " - 200 4F4B ")
    line = (
        "WEB-CONVERSE host="
        + b"zecs.example".hex().upper()
        + " method=PUT path="
        + b"/k".hex().upper()
        + " query=- media="
        + b"text/plain".hex().upper()
        + " body=1 resp=0 resp2=0"
    )
    kv = dict(a.split("=", 1) for a in line.split()[1:])
    got = ec._cobol_web(kv, b"data ", "latin-1")
    assert got == {"host": "zecs.example", "method": "PUT", "path": "/k", "query": "", "mediatype": "text/plain",
                   "body": "data ", "resp": 0, "resp2": 0}  # fmt: skip
    java = {"event": "WEB-CONVERSE", **got}
    assert ec.compare_events([java], [dict(java)])["equal"] == 1
    differs = ec.compare_events([java], [{**java, "body": "data"}])  # (a trailing blank is sent: compared exactly)
    assert differs["diffs"] and differs["diffs"][0]["fields"][0]["field"] == "body"


def test_web_open_and_close_events_read_back_as_cicstask_records_them():
    """#4767 zECS (X35): a WEB-OPEN line (host in hex, '-' none; the scheme as named, '-' none) and a WEB-CLOSE line read back
    as CicsTask records them, a connection refused with a condition included; the host, scheme and RESP2 are compared."""
    host = b"zecs.example".hex().upper()
    cases = [({"host": host, "scheme": "HTTP", "resp": "0", "resp2": "0"}, "zecs.example", "HTTP"),
             ({"host": "-", "scheme": "HTTPS", "resp": "22", "resp2": "21"}, "", "HTTPS"),
             ({"host": host, "scheme": "-", "resp": "16", "resp2": "40"}, "zecs.example", None)]  # fmt: skip
    for kv, want_host, want_scheme in cases:
        got = ec._cobol_web_open(kv, "latin-1")
        assert got == {"host": want_host, "scheme": want_scheme, "resp": int(kv["resp"]), "resp2": int(kv["resp2"])}
        java = {"event": "WEB-OPEN", **got}
        assert ec.compare_events([java], [dict(java)])["equal"] == 1
        for field, value in (("host", "other"), ("scheme", "HTTP" if want_scheme != "HTTP" else None), ("resp2", 99)):
            differs = ec.compare_events([java], [{**java, field: value}])
            assert differs["diffs"] and differs["diffs"][0]["fields"][0]["field"] == field
    close = {"event": "WEB-CLOSE", "resp": 19, "resp2": 27}
    assert ec.compare_events([close], [dict(close)])["equal"] == 1
    differs = ec.compare_events([close], [{**close, "resp2": 0}])
    assert differs["diffs"] and differs["diffs"][0]["fields"][0]["field"] == "resp2"


def test_inquire_urimap_direct_and_program_status_become_stub_calls():
    """#4768 zECS (register X34): INQUIRE URIMAP(name) with no browse option -> the name in GG-NAME1, GGCURIB with GG-FLAGS
    'DIRECT' (NOTFND RESP2 3), then one GGCURIP per output option on NORMAL; INQUIRE PROGRAM STATUS -> GGCINQP, the CVDA
    it leaves in GG-NUM moved to the area on NORMAL."""
    d = ec.translate_command("INQUIRE URIMAP(WS-M) PATH(WS-P) NOHANDLE")
    assert d[:3] == ["MOVE WS-M TO GG-NAME1", "MOVE 'DIRECT' TO GG-FLAGS", "CALL 'GGCURIB' USING GG-CICS"]
    assert d[3] == "IF GG-RESP = 0" and "    MOVE 'PATH' TO GG-FLAGS" in d and "        BY REFERENCE WS-P" in d
    assert "        BY REFERENCE WS-M" not in d  # (the direct form's URIMAP is the name it reads)
    with pytest.raises(ec.Unsupported, match="without URIMAP, START, NEXT or END"):
        ec.translate_command("INQUIRE URIMAP PATH(WS-P)")
    p = ec.translate_command("INQUIRE PROGRAM(WS-PG) STATUS(WS-ST) RESP(WS-R) NOHANDLE")
    assert p[:2] == ["MOVE WS-PG TO GG-NAME1", "CALL 'GGCINQP' USING GG-CICS"]
    assert p[2:5] == ["IF GG-RESP = 0", "    MOVE GG-NUM TO WS-ST", "END-IF"]
    assert "MOVE GG-RESP TO WS-R" in p
    plain = ec.translate_command("INQUIRE PROGRAM(WS-PG) NOHANDLE")
    assert plain[:3] == ["MOVE WS-PG TO GG-NAME1", "CALL 'GGCINQP' USING GG-CICS", "MOVE GG-RESP TO EIBRESP"]


def test_document_create_and_retrieve_become_stub_calls():
    """#4769 (register X33): DOCUMENT CREATE -> GGCDOCC (GG-FLAGS names the source: DATA with GG-LEN, TEMPLATE with its name,
    EMPTY), the token in the DOCTOKEN area; DOCUMENT RETRIEVE -> GGCDOCR (MAXLENGTH in GG-LEN), LENGTH moved back on NORMAL
    and the truncating LENGERR RESP2 2 only. What IBM leaves open is refused by name, as the translator refuses it."""
    t = ec.translate_command("DOCUMENT CREATE DOCTOKEN(DC-TOKEN) TEMPLATE(ZECS-DC) NOHANDLE")
    assert t[:2] == ["MOVE 'TEMPLATE' TO GG-FLAGS", "CALL 'GGCDOCC' USING GG-CICS"]
    assert t[2:6] == ["    BY REFERENCE ZECS-DC", "    BY VALUE LENGTH OF ZECS-DC", "    BY REFERENCE DC-TOKEN",
                      "    BY VALUE LENGTH OF DC-TOKEN"]  # fmt: skip
    lit = ec.translate_command("DOCUMENT CREATE DOCTOKEN(DC-TOKEN) TEMPLATE('ZC01DC') NOHANDLE")
    assert "    BY VALUE 6" in lit  # a literal's own length
    d = ec.translate_command("DOCUMENT CREATE DOCTOKEN(T) TEXT(WS-A) LENGTH(WS-N) RESP(R) RESP2(R2)")
    assert d[:3] == ["MOVE WS-N TO GG-LEN", "MOVE 'DATA' TO GG-FLAGS", "CALL 'GGCDOCC' USING GG-CICS"]
    assert "MOVE GG-RESP2 TO R2" in d and "    BY VALUE LENGTH OF WS-A" in d
    assert (
        ec.translate_command("DOCUMENT CREATE DOCTOKEN(T) BINARY(WS-A) LENGTH(5) NOHANDLE")[1]
        == "MOVE 'DATA' TO GG-FLAGS"
    )
    assert ec.translate_command("DOCUMENT CREATE DOCTOKEN(T) NOHANDLE")[0] == "MOVE 'EMPTY' TO GG-FLAGS"
    r = ec.translate_command("DOCUMENT RETRIEVE DOCTOKEN(T) INTO(WS-A) LENGTH(WS-L) MAXLENGTH(WS-L) DATAONLY NOHANDLE")
    assert r[:2] == ["MOVE WS-L TO GG-LEN", "CALL 'GGCDOCR' USING GG-CICS"]
    assert "    BY REFERENCE WS-A" in r and "IF GG-RESP = 0 OR (GG-RESP = 22 AND GG-RESP2 = 2)" in r
    assert "    MOVE GG-LEN TO WS-L" in r
    assert not any(
        "MOVE GG-LEN" in x
        for x in ec.translate_command("DOCUMENT RETRIEVE DOCTOKEN(T) INTO(WS-A) MAXLENGTH(9) DATAONLY NOHANDLE")
    )  # no LENGTH asked for
    for bad, why in (("DOCUMENT CREATE DOCTOKEN(T) FROM(A) LENGTH(5)", "FROM takes a template"),
                     ("DOCUMENT CREATE DOCTOKEN(T) TEMPLATE(M) SYMBOLLIST(A) LISTLENGTH(2)", "symbol table"),
                     ("DOCUMENT CREATE DOCTOKEN(T) TEMPLATE(M) DOCSIZE(L)", "DOCSIZE"),
                     ("DOCUMENT CREATE DOCTOKEN(T) TEXT(A)", "without LENGTH"),
                     ("DOCUMENT CREATE DOCTOKEN(T) TEMPLATE(M) LENGTH(3)", "LENGTH without TEXT or BINARY"),
                     ("DOCUMENT CREATE DOCTOKEN(T) TEXT(A) BINARY(A) LENGTH(3)", "one source"),
                     ("DOCUMENT CREATE TEMPLATE(M)", "without DOCTOKEN"),
                     ("DOCUMENT CREATE DOCTOKEN(T) TEXT('HI') LENGTH(2)", "as a literal"),
                     ("DOCUMENT RETRIEVE DOCTOKEN(T) INTO(A) MAXLENGTH(9)", "without DATAONLY"),
                     ("DOCUMENT RETRIEVE DOCTOKEN(T) INTO(A) DATAONLY", "without MAXLENGTH"),
                     ("DOCUMENT RETRIEVE DOCTOKEN(T) MAXLENGTH(9) DATAONLY", "without INTO"),
                     ("DOCUMENT RETRIEVE DOCTOKEN(T) INTO(A) MAXLENGTH(9) DATAONLY CHARACTERSET(C)", "code-page")):  # fmt: skip
        with pytest.raises(ec.Unsupported, match=why):
            ec.translate_command(bad)


def test_a_cases_doctemplates_are_stated_to_both_runtimes_or_refused():
    """#4769 (X33): the DOCTEMPLATE definitions are a fact the case states ("doctemplates": name -> text; a scenario's wins);
    unstated they are None (both runtimes refuse a CREATE TEMPLATE); a malformed one is refused by name."""
    assert ec.doctemplates({}, {"name": "s"}) is None
    case = {"doctemplates": {"ZC01DC": "type: AS\r\nhttp://h:1\r\n"}}
    assert ec.doctemplates(case, {"name": "s"}) == case["doctemplates"]
    assert ec.doctemplates(case, {"name": "s", "doctemplates": {}}) == {}
    for bad in ({"A B": "x"}, {"": "x"}, {"N" * 49: "x"}, {"N": 5}, ["N"]):
        with pytest.raises(ec.Unsupported, match="doctemplates"):
            ec.doctemplates({"doctemplates": bad}, {"name": "s"})


def test_the_task_number_is_the_scenarios_else_the_cases_else_zero():
    """#4270: EIBTASKN is a stated fact of the run (oracle_assumptions.md X21): a scenario's "taskn", else the
    case's, else the spec's default 0; never a value PIC S9(7) COMP-3 cannot hold."""
    assert ec.task_number({}, {"name": "s"}) == 0
    assert ec.task_number({"taskn": 34}, {"name": "s"}) == 34
    assert ec.task_number({"taskn": 34}, {"name": "s", "taskn": 9999999}) == 9999999
    for bad in (-1, 10_000_000, "34", True, 1.5):
        with pytest.raises(ec.Unsupported, match="not a task number"):
            ec.task_number({}, {"name": "s", "taskn": bad})


# ---- #4607: WRITEQ TS on both sides; X6 judged up to the refused WRITEQ ------------------------------------------
def test_the_cobol_side_reports_a_writeq_ts_as_cicstask_records_it(tmp_path):
    """#4607: the stub logs a WRITEQ TS (queue in hex, item, RESP, LENGTH; the bytes in its event blob) and CicsTask
    records WRITEQ-TS {queue, data, resp, item}; the COBOL side used to drop it, so a task that writes TS differed."""
    out = tmp_path / "out"
    out.mkdir()
    (out / "events.txt").write_text(
        "001 WRITEQ-TD queue=CSMT resp=0 len=5\n"
        "002 WRITEQ-TS pgm=LGSTSQ queue=47454E4145525253 item=1 resp=0 len=8\n"
        "003 WRITEQ-TS pgm=LGSTSQ queue=47454E4145525253 item=0 resp=22 len=0\n"
        "004 RETURN level=2\n",
        encoding="ascii",
    )
    (out / "001.bin").write_bytes(b"HELLO")
    (out / "002.bin").write_bytes(b"CICA MSG")
    res = ec.outputs(out, {"name": "x"}, tmp_path, [])
    got = ec.cobol_events(res)
    assert got[1:3] == [
        {"event": "WRITEQ-TS", "queue": "GENAERRS", "data": "CICA MSG", "resp": "NORMAL", "item": 1},
        {"event": "WRITEQ-TS", "queue": "GENAERRS", "data": None, "resp": "LENGERR", "item": None},
    ]


def test_a_writeq_ts_is_compared_by_its_queue_data_resp_and_item():
    """#4607: the Java side's item arrives as base64 of the region's page (det port: DetCics.toRegion, CCSID 037 by
    default); read as text it is compared with the COBOL side's, and so are RESP and the item number."""
    import base64

    java = {"event": "WRITEQ-TS", "queue": "GENAERRS", "data": base64.b64encode("CICA MSG".encode("cp037")).decode(),
            "resp": "NORMAL", "item": 1}  # fmt: skip
    got = ec.java_ts_as_compared(java)
    assert got == {"event": "WRITEQ-TS", "queue": "GENAERRS", "data": "CICA MSG", "resp": "NORMAL", "item": 1}
    cobol = {"event": "WRITEQ-TS", "queue": "GENAERRS", "data": "CICA MSG", "resp": "NORMAL", "item": 1}
    assert ec.compare_events([cobol], [got])["equal"] == 1
    d = ec.compare_events([cobol], [{**got, "data": "CICA MSF", "item": 2}])
    assert [f["field"] for f in d["diffs"][0]["fields"]] == ["data", "item"]
    failed = ec.java_ts_as_compared({**java, "resp": "LENGERR", "item": None})
    assert failed["data"] is None  # what a failed write was given is not compared (the stub logs none)


def test_the_cobol_side_reports_a_start_as_cicstask_records_it(tmp_path):
    """#4270 (GenApp LGWEBST5, zECS ZECSPLT): the stub logs each START (GGCSTRT) and CicsTask.start records a START
    event; the COBOL side used to drop it, so every task that STARTs differed. Its FROM data is compared as text, as
    a WRITEQ TS item is; the interval, PROTECT, RESP and the expiry ($GGCICS_NOW: the case's clock) too."""
    import base64

    out = tmp_path / "out"
    out.mkdir()
    (out / "events.txt").write_text(
        "001 START pgm=ZECSPLT transid=ZX01 termid= interval=000000 reqid= protect=0 resp=0 resp2=0 "
        "expires=2026-10-01T10:30:15 len=4 area=1\n"
        "002 START pgm=LGWEBST5 transid=SSST termid= interval=000100 reqid= protect=0 resp=0 resp2=0 "
        "expires=2026-10-01T10:31:15 len=0 area=0\n"
        "003 START pgm=X transid=T1 termid= interval=000000 reqid= protect=0 resp=16 resp2=5 expires= len=0 area=0\n"
        "004 RETURN level=1\n",
        encoding="ascii",
    )
    (out / "001.bin").write_bytes(b"ZC01")
    res = ec.outputs(out, {"name": "x"}, tmp_path, [])
    res["return"] = {"transid": "", "commarea": None}
    got = ec.cobol_events(res)
    assert got[0] == {"event": "START", "transid": "ZX01", "termid": None, "interval": "000000", "protect": False,
                      "resp": "NORMAL", "expires": "2026-10-01T10:30:15", "from": "ZC01"}  # fmt: skip
    assert got[1]["from"] is None and got[1]["interval"] == "000100"
    assert got[2]["resp"] == "INVREQ" and got[2]["resp2"] == 5 and got[2]["expires"] is None

    java = {"event": "START", "transid": "ZX01", "termid": None, "interval": "000000", "protect": False,
            "resp": "NORMAL", "expires": "2026-10-01T10:30:15", "issuer": "ZECSPLT",
            "from": base64.b64encode("ZC01".encode("cp037")).decode()}  # fmt: skip
    j = ec.java_start_as_compared(java)
    assert j["from"] == "ZC01" and ec.compare_events([got[0]], [j])["equal"] == 1
    for key, other in (("from", "ZC02"), ("interval", "000100"), ("expires", "2026-10-01T10:31:15"), ("protect", True)):
        d = ec.compare_events([got[0]], [{**j, key: other}])
        assert [f["field"] for f in d["diffs"][0]["fields"]] == [key], key
    assert ec.clock_iso({"clock": "2026/10/01 10:30:15.00"}) == "2026-10-01T10:30:15"


def test_a_case_states_the_installed_urimaps_on_both_sides(tmp_path):
    """#4270 zECS (X32): INQUIRE URIMAP browses the definitions the run states -- a scenario's (else the case's)
    "urimaps", [NAME, TRANSACTION, PATH] each: the stub's $GGCICS_URIMAPS file, CicsTask.withUrimaps in the generated
    test. Unstated, none (both runtimes refuse the browse by name); a malformed list is refused."""
    import equivalence_java as ej

    defs = [["ZC01", "ZC01", "/resources/ecs/a/b*"], ["NOTRAN", "", "/static/*"]]
    case = {**_facade_case(), "clock": "2026/10/01 10:30:15.00", "screens": {}, "urimaps": defs}
    assert ec.urimaps(case, {"name": "a"}) == defs
    assert ec.urimaps(case, {"name": "b", "urimaps": []}) == []
    assert ec.urimaps({}, {"name": "c"}) is None
    for bad in ([["ZC01", "ZC01"]], [["ZC01", "ZC01", "/a b"]], [["TOOLONGNAME", "", "/x"]], "ZC01"):
        with pytest.raises(ec.Unsupported, match="urimaps"):
            ec.urimaps({}, {"name": "d", "urimaps": bad})
    svc = tmp_path / "service" / f"{ej._service_class('PROG')}.java"
    svc.parent.mkdir(parents=True)
    svc.write_text("public void handleTransaction(String transid, ProgCa request) {}", encoding="utf-8")
    java = ec.cics_equivalence_test(case, tmp_path, [])
    assert 'if (sc.hasNonNull("urimaps")) {' in java and "task.withUrimaps(defs);" in java


def test_the_facade_side_runs_a_link_channel_target_through_runtask():
    """#4270 (async SEQPNT): a LINK CHANNEL to a channel program (its handleLink takes a <Program>ChannelIn DTO, not
    a task) runs through runTask on the facade side, as the scenario's own channel program does (#4343), and
    `entries` says so -- it used to throw before the LINK's level ran."""
    enter = ec.FACADE_JAVA[ec.FACADE_JAVA.index("void enter(String p, CicsTask task, Object service)") :]
    enter = enter[: enter.index("void entry(String p, String method)")]
    chan = enter.index('getSimpleName().endsWith("ChannelIn")')
    assert chan < enter.index("linked = task;")
    assert 'call(method(service, "runTask", 1), service, task);' in enter[chan : enter.index("linked = task;")]


def test_a_writeq_past_its_from_area_is_judged_up_to_the_refusal_x6():
    """Owner decision on #4607 (X6): a task the stub stops at a WRITEQ TS / TD whose LENGTH runs past FROM is judged
    up to that statement; any other "not modelled" stop (START / PUT CONTAINER past FROM, an LE model) is not."""
    said = "junk\nWRITEQ TD LENGTH > FROM: not modelled\n"
    assert ec.x6_writeq_refusal(said) == "WRITEQ TD LENGTH > FROM: not modelled"
    assert ec.x6_writeq_refusal("WRITEQ TS LENGTH > FROM: not modelled") == "WRITEQ TS LENGTH > FROM: not modelled"
    assert ec.x6_writeq_refusal("START LENGTH > FROM: not modelled") is None
    assert ec.x6_writeq_refusal("CEEDAYS picture: not modelled") is None


def test_a_scenario_states_startcode_terminal_input_and_ts_queues():
    """#4270 (GenApp LGICVS01, a terminal transaction reading its control queue): ASSIGN STARTCODE, an unformatted
    RECEIVE's input and the TS queues the task starts with are facts the case states for both sides (the scenario's,
    else the case's), as the cics-crucible runner states them; a startcode IBM does not list, a non-text input and a
    malformed queue are refused."""
    case = {"startcode": "TD", "terminal": "LGCF", "ts": {"GENACNTL": ["**** GENAPP CNTL"]}}
    assert ec.task_facts(case, {"name": "a"}) == ("TD", "LGCF")
    assert ec.task_facts(case, {"name": "b", "startcode": "SD", "terminal": "X"}) == ("SD", "X")
    assert ec.task_facts({}, {"name": "c"}) == (None, None)
    # D: a LINKed-to program's COMMAREA path (#4174)
    assert ec.task_facts({"startcode": "D"}, {"name": "d"}) == ("D", None)
    assert ec.ts_seed(case, {"name": "a"}) == {"GENACNTL": ["**** GENAPP CNTL"]}
    assert ec.ts_seed(case, {"name": "b", "ts": {}}) == {}
    for bad in ({"startcode": "X"}, {"startcode": "d"}, {"terminal": 5}):
        with pytest.raises(ec.Unsupported):
            ec.task_facts(bad, {"name": "x"})
    with pytest.raises(ec.Unsupported):
        ec.ts_seed({"ts": {"Q": "not a list"}}, {"name": "x"})


def test_a_readq_ts_and_a_receive_the_stub_logged_read_as_cicstask_records_them():
    """#4270: the stub's READQ-TS / RECEIVE lines (RESP by number, the queue name in hex) as CicsTask's events; the
    Java item's bytes are in the region's page (CCSID 037), compared as text."""
    import base64

    kv = {"queue": "47454E41434E544C", "item": "NEXT", "resp": "0"}
    assert ec._cobol_read("READQ-TS", kv, b"LOW CUSTOMER=0000000003", "latin-1") == {
        "event": "READQ-TS",
        "queue": "GENACNTL",
        "item": "NEXT",
        "resp": "NORMAL",
        "data": "LOW CUSTOMER=0000000003",
    }
    assert ec._cobol_read("READQ-TS", {**kv, "item": "1", "resp": "26"}, b"", "latin-1")["item"] == 1
    assert ec._cobol_read("RECEIVE", {"resp": "0"}, b"LGCF", "latin-1") == {"event": "RECEIVE", "resp": "NORMAL",
                                                                          "data": "LGCF"}  # fmt: skip
    java = {"event": "READQ-TS", "data": base64.b64encode("LGCF".encode("cp037")).decode()}
    assert ec.java_read_as_compared(java)["data"] == "LGCF"


# ---- #4270: a program that takes no COMMAREA; a scenario's stated COMMAREA length (X23) ---------------------------
def test_a_case_says_its_program_takes_no_commarea(tmp_path):
    """#4270 (the async credit-card services: an empty LINKAGE SECTION, a det service handleLink()): `"commarea": null`
    describes no COMMAREA -- no fields, no DTO, EIBCALEN 0 on both sides. A case that says nothing, or an empty
    segment list, is refused by name (it was a KeyError / IndexError), and so is a scenario that gives one anyway."""
    assert ec.commarea_fields(tmp_path, {"commarea": None}) == []
    with pytest.raises(ec.Unsupported, match='"commarea": null for a program that takes none'):
        ec.commarea_fields(tmp_path, {})
    with pytest.raises(ec.Unsupported, match="describes nothing"):
        ec.commarea_fields(tmp_path, {"commarea": {"segments": []}})
    svc = tmp_path / "GetpolService.java"
    svc.write_text("public class GetpolService {\n    public void handleLink() {\n    }\n}\n", encoding="utf-8")
    assert ec.commarea_class({"commarea": None}, tmp_path, svc) is None
    import equivalence_java as ej

    (tmp_path / "service").mkdir()
    (tmp_path / "service" / f"{ej._service_class('PROG')}.java").write_text("public void handleLink() {}")
    case = {**_facade_case(), "clock": "2026/10/01 10:30:15.00", "screens": {}, "commarea": None, "linked": True}
    java = ec.cics_equivalence_test(case, tmp_path, [])
    assert "Object commarea = null;" in java and "treeToValue" not in java
    assert "ScreenModel" not in java  # an estate with no BMS map has no screen view models (dto.screen)
    assert 'm = method(service, "handleLink", 0);' in java  # the facade side enters handleLink() itself


def test_a_commarea_in_an_event_of_a_case_with_none_is_refused(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "events.txt").write_text("001 RETURN level=1 transid= len=4\n", encoding="ascii")
    (out / "001.bin").write_bytes(b"ABCD")
    with pytest.raises(ec.Unsupported, match="describes none"):
        ec.outputs(out, {"name": "x"}, tmp_path, [])


def test_a_scenario_states_a_commarea_shorter_than_its_record():
    """#4270 (X23): `"commarea_length": N` is EIBCALEN -- the caller passed the record's first N bytes and no more
    (GenApp's IF EIBCALEN < 91, its '98' returns). 0 to the record's length; never on a scenario with no COMMAREA."""
    fields = [{"name": "CA-A", "offset": 0, "bytes": 2}, {"name": "CA-B", "offset": 2, "bytes": 98}]
    assert ec.commarea_length({"name": "s", "commarea": {}}, fields) is None
    assert ec.commarea_length({"name": "s", "commarea": {}, "commarea_length": 60}, fields) == 60
    assert ec.commarea_length({"name": "s", "commarea": {}, "commarea_length": 100}, fields) == 100
    assert ec.commarea_length({"name": "s", "commarea": {}, "commarea_length": 0}, fields) == 0  # #4049: EIBCALEN 0
    for bad in (101, -1, "60", True, 6.0):
        with pytest.raises(ec.Unsupported, match="is not a length"):
            ec.commarea_length({"name": "s", "commarea": {}, "commarea_length": bad}, fields)
    with pytest.raises(ec.Unsupported, match="with no COMMAREA"):
        ec.commarea_length({"name": "s", "commarea": None, "commarea_length": 10}, fields)


def test_the_driver_runs_the_program_on_the_area_the_stub_chose():
    """#4270 (X23): GGCAREA moves a COMMAREA of a stated length before a guard page; the driver passes whatever area
    it chose (LK-CA), and writes back from it."""
    drv = ec.cics_driver("PROG", True)
    assert "CALL 'GGCAREA' USING WS-PTR BY VALUE WS-LEN" in drv and "SET ADDRESS OF LK-CA TO WS-PTR" in drv
    assert "CALL 'PROG' USING LK-CA" in drv and "CALL 'GGCAOUT' USING LK-CA BY VALUE WS-LEN" in drv
    assert "CALL 'PROG'\n" in ec.cics_driver("PROG", False)
    assert all(len(ln) <= 72 for ln in drv.splitlines())


def test_a_padded_writeq_is_named_on_the_task_and_kept_out_of_its_display_log(tmp_path):
    """X6 (ASSUMED, owner 2026-10-21): the stub's line on the padded path names the WRITEQ on the task (so a proof
    states X6 for it) and is not part of the task's DISPLAY output, which the Java side never prints."""
    out = tmp_path / "out"
    out.mkdir()
    (out / "events.txt").write_text("001 RETURN level=1\n", encoding="ascii")
    (tmp_path / "stdout.txt").write_bytes(b"BEFORE\n" + ec.X6_PADDED_SAID.encode("ascii") + b"WRITEQ TD\nAFTER\n")
    res = ec.outputs(out, {"name": "x"}, tmp_path, [])
    assert res["x6_padded"] == ["WRITEQ TD"] and res["sysout"] == b"BEFORE\nAFTER\n"
    (tmp_path / "stdout.txt").write_bytes(b"BEFORE\n")
    assert "x6_padded" not in ec.outputs(out, {"name": "x"}, tmp_path, [])  # no padded WRITEQ, no key


def test_a_writeq_past_from_runs_on_padded_for_ts_and_td_and_a_huge_length_is_refused_x6():
    """X6 (ASSUMED): WRITEQ TS and WRITEQ TD alike write FROM then spaces when LENGTH runs past the item, and the task
    runs on (no judged-up-to stop); only a LENGTH over the pad record's 32767 bytes is still refused by name, and a
    literal FROM is left alone."""
    for what, stub in (("WRITEQ TS", "GGCWRTQ"), ("WRITEQ TD", "GGCWRTD")):
        call = ec._call(stub, ["BY REFERENCE WS-MSG"])
        got = "\n".join(ec._write_from("GG-LEN", "WS-MSG", what, call))
        assert f"DISPLAY '{ec.X6_PADDED_SAID}{what}'" in got and "BY REFERENCE GG-PADQ" in got
        assert got.count(f"DISPLAY '{what} LENGTH > FROM: not modelled'") == 1  # the over-32767 refusal, by name
        assert ec.x6_writeq_refusal(f"{what} LENGTH > FROM: not modelled")
        assert ec._write_from(None, "WS-MSG", what, call) == call  # no LENGTH: nothing past FROM
        assert ec._write_from("23", "'LITERAL'", what, call) == call


def test_no_case_says_a_writeq_past_from_is_refused():
    """#6271: since #6573 a WRITEQ whose LENGTH runs past FROM is written padded (X6) and the task is compared whole;
    only a LENGTH over 32767 is still refused. A case note or scenario `why` that says a task is judged up to a
    "refused WRITEQ" misstates that, in any case (LGSTSQ's error logger, LGICVS01's LOW / HIGH CUSTOMER items, ...)."""
    import json

    root = Path(__file__).resolve().parents[1] / "equivalence"
    cases = sorted(root.glob("*/case.json"))
    assert len(cases) > 100  # the glob found the corpus, not an empty directory
    stale = []
    for path in cases:
        case = json.loads(path.read_text(encoding="utf-8"))
        text = json.dumps([case.get("notes"), [sc.get("why") for sc in case.get("scenarios", [])]])
        if "refused WRITEQ" in text:
            stale.append(path.parent.name)
    assert stale == [], stale
    for n in ("lgtestp1", "lgtestp2", "lgtestp3", "lgtestp4", "lgtestc1"):
        case = json.loads((root / f"genapp-{n}" / "case.json").read_text(encoding="utf-8"))
        assert "padded" in json.dumps([case.get("notes"), [sc.get("why") for sc in case["scenarios"]]]), n


def test_a_reference_past_a_stated_eibcalen_is_judged_up_to_it_x22(tmp_path):
    """#4270 (X23): the stub's guard-page stop is judged up to, as X6's WRITEQ is; the report says which assumption."""
    said = "COMMAREA past EIBCALEN: not modelled\n"
    assert ec.judged_refusal(said) == "COMMAREA past EIBCALEN: not modelled"
    assert ec.judged_refusal("WRITEQ TS LENGTH > FROM: not modelled") == "WRITEQ TS LENGTH > FROM: not modelled"
    assert ec.judged_refusal("START LENGTH > FROM: not modelled") is None
    (tmp_path / "s.x6").write_text("COMMAREA past EIBCALEN (60 bytes): not modelled", encoding="utf-8")
    ev = [{"event": "RETURN", "transid": None, "commarea": None}, {"event": "COMMAREA", "commarea": {"A": "1"}}]
    cev, jev, x = ec.x6_judged({"name": "s", "prefix_x6": said.strip()}, tmp_path, ev, ev)
    assert x == {"cobol": said.strip(), "java": "COMMAREA past EIBCALEN (60 bytes): not modelled", "ok": True,
                 "assumes": "X23"}  # fmt: skip
    assert cev == jev == ev[:1] and ec.judged_to(x).startswith("the refused reference past EIBCALEN (X23")
    _, _, w = ec.x6_judged({"name": "t", "prefix_x6": "WRITEQ TD LENGTH > FROM: not modelled"}, tmp_path, ev, ev)
    assert w["assumes"] == "X6" and not w["ok"] and ec.judged_to(w) == ec.X6_JUDGED
    # both sides refused, but not at the same thing (the det port read past EIBCALEN, the stub stopped at the WRITEQ)
    _, _, m = ec.x6_judged({"name": "s", "prefix_x6": "WRITEQ TD LENGTH > FROM: not modelled"}, tmp_path, ev, ev)
    assert m["assumes"] == "X6" and m["java"].startswith("COMMAREA past EIBCALEN") and not m["ok"]


_AREA_MAIN = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int GGCAREA(char **area, int len);
int main(int argc, char **argv) {
    char buf[200];
    char *a = buf;
    memset(buf, 'x', sizeof buf);
    GGCAREA(&a, atoi(argv[1]));
    printf("moved=%d first=%c\n", a != buf, a[0]);
    fflush(stdout);
    a[atoi(argv[2])] = 'y';
    printf("wrote\n");
    return 0;
}
"""


@pytest.mark.skipif(__import__("sys").platform == "win32" or not __import__("shutil").which("gcc"),
                    reason="needs gcc and a POSIX guard page")  # fmt: skip
def test_a_scenario_states_untyped_commarea_bytes_for_a_case_with_no_layout():
    """#5859 (ZECSNC): `"commarea_hex"` is the exact bytes the caller passed to a program with no typed COMMAREA (an
    HLASM DSECT); EIBCALEN is their count. Refused by name when typed, mixed with a typed key, empty or not hex."""
    case = {"commarea": None}
    assert ec.untyped_commarea(case, {"name": "s"}, []) is None
    assert ec.untyped_commarea(case, {"name": "s", "commarea_hex": "00ff5A43"}, []) == b"\x00\xffZC"
    for bad in ("", "0", "zz", 12, "00 00"):
        with pytest.raises(ec.Unsupported, match="hex byte pairs"):
            ec.untyped_commarea(case, {"name": "s", "commarea_hex": bad}, [])
    for extra in ({"commarea": {}}, {"commarea_length": 4}):
        with pytest.raises(ec.Unsupported, match="commarea_length"):
            ec.untyped_commarea(case, {"name": "s", "commarea_hex": "0000", **extra}, [])
    with pytest.raises(ec.Unsupported, match="no layout"):
        ec.untyped_commarea({"commarea": {}}, {"name": "s", "commarea_hex": "0000"}, [{"name": "A"}])
    with pytest.raises(ec.Unsupported, match="no layout"):
        ec.untyped_commarea(case, {"name": "s", "commarea_hex": "0000"}, [{"name": "A"}])


def test_the_java_side_gets_the_untyped_commarea_in_the_region_page():
    """#5859: the stub reads commarea.in in the case's data page; the port's byte[] is in the region's (CCSID 037),
    as a START's data is, and its length is EIBCALEN."""
    case = {"commarea": None, "data_encoding": "ascii"}
    got = ec._java_untyped_commarea(case, {"name": "s", "commarea_hex": "5A433031"}, [])
    assert got == {"commarea_hex": "E9C3F0F1", "untyped_length": 4}
    assert ec._java_untyped_commarea(case, {"name": "s"}, []) == {}


def test_the_java_template_reads_an_untyped_commarea():
    """#5859: the generated test builds the byte[] from `commarea_hex` and passes its length as EIBCALEN."""
    src = Path(ec.__file__).read_text(encoding="utf-8")
    assert 'sc.hasNonNull("commarea_hex")' in src
    assert "HexFormat.of().parseHex" in src
    assert 'sc.path("untyped_length")' in src


def test_the_stub_stops_a_reference_past_a_stated_commarea_length(tmp_path):
    """#4270 (X23): with commarea.exact, GGCAREA copies the COMMAREA to the end of a page before an inaccessible one:
    the last byte is the program's, the next stops the run (98, "COMMAREA past EIBCALEN: not modelled"). Without it,
    the area is left where the driver has it."""
    import subprocess

    (tmp_path / "main.c").write_text(_AREA_MAIN, encoding="ascii")
    exe = tmp_path / "area"
    built = subprocess.run(["gcc", "-o", str(exe), str(tmp_path / "main.c"), str(ec.STUB / "ggcics.c")],  # noqa: S603,S607
                           capture_output=True, text=True, check=False)  # fmt: skip
    assert built.returncode == 0, built.stderr
    d = tmp_path / "d"
    d.mkdir()

    def run(*args: str) -> tuple[int, str]:
        p = subprocess.run([str(exe), *args], capture_output=True, text=True, env={"GGCICS_DIR": str(d)}, check=False)  # noqa: S603
        return p.returncode, p.stdout

    assert run("60", "99") == (0, "moved=0 first=x\nwrote\n")
    (d / "commarea.exact").write_text("60\n", encoding="ascii")
    assert run("60", "59") == (0, "moved=1 first=x\nwrote\n")
    assert run("60", "60") == (98, "moved=1 first=x\nCOMMAREA past EIBCALEN: not modelled\n")


# ---- #4270: a task started with a channel; the containers it leaves compared (X24); a case's transactions ----------
def _channel_case():
    return {"name": "x", "program": "CRDTCHK", "transid": "ICCK", "scenarios": [], "datasets": {}}


def test_a_scenario_states_the_channel_its_task_starts_with():
    """#4270 (X24): `"channel"` -- a name and containers (text in the case's data page, or hex; BIT unless CHAR, as
    PUT CONTAINER's default) -- is what a RUN TRANSID CHANNEL parent passed. Names are CICS's: 1-16, no blank."""
    sc = {"name": "s", "channel": {"name": "MYCHANNEL", "containers": {
        "INPUTCONTAINER": {"text": "0001"}, "RAW": {"hex": "00ff", "datatype": "CHAR"}}}}  # fmt: skip
    got = ec.scenario_channel(_channel_case(), sc)
    assert got == {"name": "MYCHANNEL", "containers": [{"name": "INPUTCONTAINER", "data": b"0001", "bit": True},
                                                       {"name": "RAW", "data": b"\x00\xff", "bit": False}]}  # fmt: skip
    assert ec.scenario_channel(_channel_case(), {"name": "s"}) is None
    assert ec._channel_json(_channel_case(), sc)["containers"][1] == {"name": "RAW", "hex": "00FF", "bit": False}
    for bad in (
        {"name": "MY CHANNEL"},
        {"name": "X" * 17},
        {"name": "C", "containers": {"K": {"text": "a", "hex": "61"}}},
        {"name": "C", "containers": {"K": {}}},
        {"name": "C", "containers": {"K": {"hex": "61", "datatype": "X"}}},
    ):
        with pytest.raises(ec.Unsupported):
            ec.scenario_channel(_channel_case(), {"name": "s", "channel": bad})


@pytest.mark.parametrize("bad", ["^", "~", "&", "<", "\u00ac", " ", "A B", " A", "", "X" * 17])
def test_a_channel_or_container_name_outside_puts_character_set_is_refused(bad):
    """#4950 (X18): IBM's PUT CONTAINER set; & < and the not sign (RUN TRANSID's page only) are refused too."""
    name = "AB" + bad if bad.strip() and len(bad) == 1 else bad
    for ch in ({"name": name}, {"name": "C", "containers": {name: {"text": "a"}}}):
        with pytest.raises(ec.Unsupported):
            ec.scenario_channel(_channel_case(), {"name": "s", "channel": ch})


@pytest.mark.parametrize("good", ["ABCDEFGHIJKLMNOPQRSTUVWXYZ"[:16], '$@#/%?!:|"=,;>.-', "a.b-c_d", "X" * 16, "9"])
def test_a_channel_or_container_name_in_puts_character_set_is_accepted(good):
    sc = {"name": "s", "channel": {"name": good, "containers": {good: {"text": "a"}}}}
    got = ec.scenario_channel(_channel_case(), sc)
    assert got["name"] == good
    assert got["containers"][0]["name"] == good


def test_no_committed_case_file_states_a_channel_name_the_harness_now_refuses():
    import json
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1] / "equivalence"
    seen = 0
    for f in sorted(root.glob("*/case.json")):
        case = json.loads(f.read_text(encoding="utf-8"))
        for sc in case.get("scenarios") or []:
            if isinstance(sc, dict) and sc.get("channel") is not None:
                ec.scenario_channel(case, sc)
                seen += 1
    assert seen


def test_the_containers_a_task_leaves_are_compared_at_its_end_unless_it_abends(tmp_path):
    """#4270 (X24): the stub's containers.out -> a last CONTAINERS event (before a LINKed program's COMMAREA, as
    CicsTask's test writes them); RUN TRANSID CHILD is compared as CicsTask records it; an abend drops the
    containers, as it drops the COMMAREA; every container's bytes, both ways, are compared."""
    out = tmp_path / "out"
    out.mkdir()
    (out / "events.txt").write_text("001 RUN pgm=CSSTATS2 transid=GETP resp=0 resp2=0\n"
                                    "002 RUN pgm=CSSTATS2 transid=NONE resp=28 resp2=1\n"
                                    "003 RETURN pgm=CSSTATS2 level=1 transid= len=0\n", encoding="ascii")  # fmt: skip
    (out / "containers.out").write_text("CHANNEL MYCHANNEL\nINPUTCONTAINER 30303031\nGETVIPSTATUS 56455259\n",
                                        encoding="ascii")  # fmt: skip
    got = ec.cobol_events(ec.outputs(out, {"name": "x"}, tmp_path, []))
    assert got == [{"event": "RUN", "transid": "GETP", "resp": "NORMAL"},
                   {"event": "RUN", "transid": "NONE", "resp": "TRANSIDERR"},
                   {"event": "RETURN", "transid": None, "commarea": None},
                   {"event": "CONTAINERS", "channel": "MYCHANNEL",
                    "containers": {"INPUTCONTAINER": "30303031", "GETVIPSTATUS": "56455259"}}]  # fmt: skip
    java = [*got[:3], {"event": "CONTAINERS", "channel": "MYCHANNEL",
                       "containers": {"GETVIPSTATUS": "56455259", "INPUTCONTAINER": "30303031"}}]  # fmt: skip
    assert ec.compare_events(got, java)["equal"] == 4  # order of containers does not matter
    java[3] = {**java[3], "containers": {"INPUTCONTAINER": "30303031", "GETVIPSTATUS": "52454755"}}
    assert [f["field"] for f in ec.compare_events(got, java)["diffs"][0]["fields"]] == ["containers.GETVIPSTATUS"]
    abended = [{"event": "ABEND", "abcode": "X"}, got[3]]
    assert ec.linked_result({}, abended) == abended[:1] and ec.linked_result({}, got) == got
    _, _, _ = ec.x6_judged({"name": "s"}, tmp_path, got, got)  # (no refusal: unchanged)
    cev, _, _ = ec.x6_judged({"name": "s", "prefix_x6": "WRITEQ TD LENGTH > FROM: not modelled"}, tmp_path, got, got)
    assert cev == got[:3]  # a task judged up to a refusal: its end state (containers too) is not compared


def test_the_driver_gives_the_task_its_channel_and_a_case_states_its_transactions(tmp_path):
    assert "CALL 'GGCCHIN' USING GG-CICS" in ec.cics_driver("PROG", False)
    assert ec.case_transactions({"transactions": ["SPND", "GETP"]}) == ["GETP", "SPND"]
    with pytest.raises(ec.Unsupported, match="transaction ids"):
        ec.case_transactions({"transactions": ["TOOLONG"]})
    import equivalence_java as ej

    (tmp_path / "service").mkdir()
    (tmp_path / "service" / f"{ej._service_class('PROG')}.java").write_text("public void handleLink() {}")
    case = {**_facade_case(), "clock": "2026/10/01 10:30:15.00", "screens": {}, "commarea": None,
            "transactions": ["GETP", "SPND"]}  # fmt: skip
    java = ec.cics_equivalence_test(case, tmp_path, [])
    assert (
        'public boolean transaction(String transid) { return java.util.Set.of("GETP", "SPND").contains(transid); }'
        in java
    )
    assert "task.withChannel(channel);" in java and 'left.put("event", "CONTAINERS");' in java


_CHANNEL_MAIN = r"""
#include "GGCICS"
int main(void) {
    gg_cics c;
    char into[8] = "....";
    memset(&c, 0, sizeof c);
    GGCCHIN(&c);
    memset(c.qname, ' ', 16);
    memcpy(c.qname, "INPUTCONTAINER", 14);
    memset(c.flags, ' ', 40);
    c.len = 4;
    GGCGETC(&c, into);
    printf("get resp=%d len=%d into=%.4s\n", c.resp, c.len, into);
    memset(c.qname, ' ', 16);
    memcpy(c.qname, "OUT", 3);
    c.len = 3;
    GGCPUTC(&c, "998");
    printf("put resp=%d\n", c.resp);
    GGCEND(&c);
    return 0;
}
"""


@pytest.mark.skipif(not __import__("shutil").which("gcc"), reason="needs gcc")
def test_the_stub_starts_the_task_with_its_channel_and_writes_what_it_leaves(tmp_path):
    """#4270 (X24): GGCCHIN makes channel.cfg's channel the first program's current channel (GET CONTAINER finds the
    stated data, PUT CONTAINER adds to it); GGCEND writes its containers to containers.out. No channel.cfg: no
    current channel (GET CONTAINER INVREQ RESP2 4) and no containers.out, as before."""
    import subprocess

    (tmp_path / "main.c").write_text(_CHANNEL_MAIN.replace("GGCICS", str(ec.STUB / "ggcics.c")), encoding="ascii")
    exe = tmp_path / "chan"
    built = subprocess.run(["gcc", "-o", str(exe), str(tmp_path / "main.c")], capture_output=True, text=True,  # noqa: S603,S607
                           check=False)  # fmt: skip
    assert built.returncode == 0, built.stderr
    d, o = tmp_path / "d", tmp_path / "o"
    d.mkdir()
    o.mkdir()
    env = {"GGCICS_DIR": str(d), "GGCICS_OUT": str(o)}
    run = subprocess.run([str(exe)], capture_output=True, text=True, env=env, check=False)  # noqa: S603
    assert run.stdout.splitlines() == ["get resp=16 len=4 into=....", "put resp=16"]  # INVREQ: no current channel
    assert not (o / "containers.out").exists()
    (d / "channel.cfg").write_text("MYCHANNEL\nINPUTCONTAINER BIT 30303031\n", encoding="ascii")
    run = subprocess.run([str(exe)], capture_output=True, text=True, env=env, check=False)  # noqa: S603
    assert run.stdout.splitlines()[:2] == ["get resp=0 len=4 into=0001", "put resp=0"]
    assert (o / "containers.out").read_text() == "CHANNEL MYCHANNEL\nINPUTCONTAINER 30303031\nOUT 393938\n"


def test_a_java_commarea_passed_as_bytes_is_read_by_the_case_layout():
    """#4679: a RETURN / XCTL whose LENGTH is past the DTO passes the bytes (DetCics.commareaOut: CCSID 037, which
    Jackson writes base64). They are read as the COBOL side's RETURN area is -- in the case's data page, by the case's
    COMMAREA layout -- so CardDemo's LENGTH 2000 RETURN compares the same fields as its 414-byte DTO did; bytes past
    the layout are compared on neither side. A DTO's JSON still goes through its shape; bytes in a case that describes
    no COMMAREA are refused, as on the COBOL side."""
    import base64

    fields = [{"name": "CA-ID", "offset": 0, "bytes": 4, "pic": "X(4)", "usage": "DISPLAY"},
              {"name": "CA-N", "offset": 4, "bytes": 3, "pic": "9(3)", "usage": "DISPLAY"}]  # fmt: skip
    raw = ("ABCD042" + "Z" * 1993).encode("cp037")
    got = ec.java_commarea(base64.b64encode(raw).decode("ascii"), {}, fields, "latin-1")
    assert got == ec.decode_record(raw.decode("cp037").encode("latin-1"), fields, "latin-1", exact=True)
    assert ec._same(got["CA-ID"], "ABCD") and ec._same(got["CA-N"], 42)
    # #4635: LOW-VALUES the task left stay LOW-VALUES, as on the COBOL side (CardDemo COCRDLIC's cleared rows)
    low = ec.java_commarea(base64.b64encode(b"\x00" * 7).decode("ascii"), {}, fields, "latin-1")
    assert low["CA-ID"] == "\x00" * 4 and not ec._same_commarea(low["CA-ID"], "")
    assert ec.java_commarea({"caId": "WXYZ"}, {"caId": "CA-ID"}, fields, "latin-1") == {"CA-ID": "WXYZ"}
    with pytest.raises(ec.Unsupported):
        ec.java_commarea(base64.b64encode(raw).decode("ascii"), {}, [], "latin-1")


def test_each_linked_sql_program_gets_the_next_free_ids_within_four_digits():
    """#4270: GG-SQL-ID is PIC 9(4). Twelve LINKed programs (GenApp's LGTESTP1) once took ranges of 1000 by their
    place in "programs", and the tenth's 10000 lost its high digit (an unknown GG-SQL-ID); each program's statements
    now start at the next hundred after the ids already taken."""
    assert ec.sql_first_id("") == 100
    table = (
        "S 1 SELECT1 1 1 - P 10\nI 0 X 1 0 0 0 0\nS 2 EXEC 1 0 - P 20\nS 100 OPEN 0 0 C Q 30\nS 117 FETCH 0 1 C Q 40\n"
    )
    assert ec.sql_first_id(table) == 200
    assert ec.sql_first_id("S 199 EXEC 0 0 - P 1\n") == 200


def test_return_immediate_and_link_synconreturn_in_the_stub():
    """#4270 (X27), IBM EXEC CICS RETURN / LINK: RETURN TRANSID IMMEDIATE -> GGCRETI, and since it can fail (INVREQ, LENGERR)
    the program goes on when GG-RESP is not 0; without TRANSID refused. SYNCONRETURN is "ignored if the link is local":
    the LINK's lines are the same without it."""
    out = ec.translate_command("RETURN TRANSID('PC52') COMMAREA(WS-CA) LENGTH(8) IMMEDIATE RESP(R)")
    assert "CALL 'GGCRETI' USING GG-CICS" in out and "CALL 'GGCRETN' USING GG-CICS" not in out
    assert out[out.index("IF GG-RESP = 0") + 1].strip() == "GOBACK" and "MOVE 1 TO GG-ITEM" in out
    assert "MOVE GG-RESP TO R" in out
    with pytest.raises(ec.Unsupported, match="IMMEDIATE without TRANSID"):
        ec.translate_command("RETURN IMMEDIATE")
    assert ec.translate_command("LINK PROGRAM('P') SYNCONRETURN") == ec.translate_command("LINK PROGRAM('P')")


def test_send_and_receive_map_leave_the_program_on_the_abm0_abend_x31():
    # #4270 (X31): the stub abends ABM0 for a map its mapset does not hold (GGCSMAP / GGCRECV, $GGCICS_MAPSETS); the
    # generated COBOL follows the exit label (GG-GOTO > 0) or leaves the program (GG-GOTO < 0) before RESP is stored
    for cmd in ("SEND MAP('M') MAPSET('S') FROM(MO) RESP(R)", "RECEIVE MAP('M') MAPSET('S') INTO(MI) RESP(R)"):
        got = ec.translate_command(cmd, ["EXIT-1"])
        call = next(i for i, ln in enumerate(got) if "GGCSMAP" in ln or "GGCRECV" in ln)
        text = "\n".join(got)
        assert "DEPENDING ON GG-GOTO" in text and "IF GG-GOTO < 0" in text
        assert text.index("IF GG-GOTO < 0") < text.index("MOVE GG-RESP TO R"), (call, got)


def test_web_retrieve_becomes_a_stub_call_and_refuses_every_other_option():
    """#4941 (register X41): WEB RETRIEVE DOCTOKEN(area) -> GGCWRTV with the area and its length (the stub writes the DOCTOKEN
    on NORMAL only); DOCTOKEN is required, a literal is refused, and every other option is refused by name."""
    r = ec.translate_command("WEB RETRIEVE DOCTOKEN(WS-T) NOHANDLE")
    assert r[:3] == ["CALL 'GGCWRTV' USING GG-CICS", "    BY REFERENCE WS-T", "    BY VALUE LENGTH OF WS-T"]
    with pytest.raises(ec.Unsupported, match="DOCTOKEN"):
        ec.translate_command("WEB RETRIEVE NOHANDLE")
    with pytest.raises(ec.Unsupported, match="literal"):
        ec.translate_command("WEB RETRIEVE DOCTOKEN('X')")
    for extra in ("SESSTOKEN(WS-S)", "FROM(WS-F)", "ACTION(WS-A)", "DOCSTATUS(WS-D)"):
        with pytest.raises(ec.Unsupported):
            ec.translate_command(f"WEB RETRIEVE DOCTOKEN(WS-T) {extra}")


def test_the_async_child_commands_become_stub_calls():
    """#4950 (X18): DELAY -> GGCDLAY (INTERVAL / TIME / FOR's values; none: INTERVAL(0)), FETCH ANY / CHILD -> GGCFETCH
    (NOSUSPEND / TIMEOUT / CHANNEL named in GG-FLAGS; on NORMAL the token, the reply channel, the abend code and the
    completion status moved to the program's areas), FREE CHILD -> GGCFREE, START CHANNEL -> GGCSTRT with GG-CHAN."""
    d = ec.translate_command("DELAY FOR SECONDS(3)")
    assert d[:6] == ["MOVE 'FOR' TO GG-FLAGS", "MOVE -999999999 TO GG-HOURS", "MOVE -999999999 TO GG-MINS",
                     "MOVE 3 TO GG-SECS", "MOVE -999999999 TO GG-LEN", "CALL 'GGCDLAY' USING GG-CICS"]  # fmt: skip
    assert ec.translate_command("DELAY INTERVAL(105)")[:2] == ["MOVE 'INTERVAL' TO GG-FLAGS", "MOVE 105 TO GG-NUM"]
    assert ec.translate_command("DELAY TIME(120000)")[0] == "MOVE 'TIME' TO GG-FLAGS"
    assert ec.translate_command("DELAY")[:2] == ["MOVE SPACES TO GG-FLAGS", "CALL 'GGCDLAY' USING GG-CICS"]
    f = ec.translate_command("FETCH ANY(WS-T) CHANNEL(WS-C) COMPSTATUS(WS-S) ABCODE(WS-A) NOSUSPEND RESP(R)")
    assert f[:4] == ["MOVE SPACES TO GG-QNAME", "MOVE 'NOSUSPEND CHANNEL' TO GG-FLAGS", "MOVE 0 TO GG-NUM",
                     "CALL 'GGCFETCH' USING GG-CICS"]  # fmt: skip
    assert f[4:12] == ["IF GG-RESP = 0", "    MOVE GG-QNAME TO WS-T", "    MOVE GG-CHAN TO WS-C", "    IF GG-ITEM = 1",
                       "        MOVE GG-NAME1(1:4) TO WS-A", "    END-IF", "    MOVE GG-NUM TO WS-S", "END-IF"]  # fmt: skip
    t = ec.translate_command("FETCH CHILD(WS-T) TIMEOUT(250)")
    assert t[:4] == ["MOVE WS-T TO GG-QNAME", "MOVE 'CHILD TIMEOUT' TO GG-FLAGS", "MOVE 250 TO GG-NUM",
                     "CALL 'GGCFETCH' USING GG-CICS"]  # fmt: skip
    assert ec.translate_command("FETCH CHILD(WS-T)")[1] == "MOVE 'CHILD' TO GG-FLAGS"  # (it waits)
    with pytest.raises(ec.Unsupported, match="FETCH NOSUSPEND and TIMEOUT together"):
        ec.translate_command("FETCH ANY(WS-T) NOSUSPEND TIMEOUT(5)")
    assert ec.translate_command("FREE CHILD(WS-T) RESP(R)")[:2] == [
        "MOVE WS-T TO GG-QNAME",
        "CALL 'GGCFREE' USING GG-CICS",
    ]
    s = ec.translate_command("START TRANSID('GT24') CHANNEL('CH.1')")
    assert "MOVE 'INTERVAL CHANNEL' TO GG-FLAGS" in s and "MOVE 'CH.1' TO GG-CHAN" in s
    with pytest.raises(ec.Unsupported, match="START CHANNEL with FROM"):
        ec.translate_command("START TRANSID('GT24') CHANNEL('CH.1') FROM(WS-A)")


def test_a_case_s_run_children_reach_both_runtimes():
    """#4950: "child_programs" ({TRANSID: PROGRAM}, each one of the case's "programs") is what a RUN child runs: the
    driver lets a child process run its program through the dispatcher (GGCCHLD), the stub reads childprogs.cfg and
    CicsTask its Programs.program; a child program that holds a region resource with no event of its own (ENQ, a
    counter, SQL) is refused when the case is built."""
    case = {"programs": [{"program": "CRDTAGY1", "program_source": "x"}], "child_programs": {"OCR1": "crdtagy1"}}
    assert ec.case_child_programs(case) == {"OCR1": "CRDTAGY1"} and ec.case_child_programs({}) == {}
    with pytest.raises(ec.Unsupported, match="child_programs"):
        ec.case_child_programs({**case, "child_programs": {"OCR1": "OTHER"}})
    drv = ec.cics_driver("PROG", False, True)
    assert "CALL 'GGCCHLD' USING GG-CICS" in drv and "CALL 'GGCRUN' USING WS-CA" in drv
    assert "GGCCHLD" not in ec.cics_driver("PROG", False)
    assert ec._CHILD_STATIC.search("EXEC CICS ENQ RESOURCE(X) END-EXEC") and ec._CHILD_STATIC.search("EXEC SQL SELECT")
    assert ec._CHILD_STATIC.search("EXEC CICS GET COUNTER(X)") and not ec._CHILD_STATIC.search("EXEC CICS DELAY")


def test_a_child_s_events_and_the_fetch_are_compared_both_ways():
    """#4950: FETCH_DIFFERS is gone -- a FETCH is compared by its outcome and, on NORMAL, the child, its completion
    status, abend code and reply channel; a CHILD event (what a dispatched child did) is compared as a task's events."""
    res = {"events": ["FETCH resp=0 resp2=0 child=GGCHILD000000002 compstatus=NORMAL abcode=- channel=GGREPLY000000001",
                      "FREE-CHILD resp=16 resp2=50", "CHILD child=GGCHILD000000001 transid=OCR1 dir=child_001"],
           "screens": [], "text": [], "children": [{"events": ["RETURN level=1"], "screens": [], "text": [],
                                                    "return": {"transid": "", "commarea": None}, "containers": None,
                                                    "linked_commarea": None}]}  # fmt: skip
    cev = ec.cobol_events(res)
    assert cev[0] == {"event": "FETCH", "resp": "NORMAL", "resp2": 0, "child": "GGCHILD000000002",
                      "compstatus": "NORMAL", "abcode": None, "channel": "GGREPLY000000001"}  # fmt: skip
    assert cev[1] == {"event": "FREE-CHILD", "resp": "INVREQ", "resp2": 50}
    assert cev[2] == {"event": "CHILD", "child": "GGCHILD000000001", "transid": "OCR1",
                      "events": [{"event": "RETURN", "transid": None, "commarea": None}]}  # fmt: skip
    assert ec.compare_events(cev, [dict(e) for e in cev])["diffs"] == []
    other = [dict(cev[0], channel=None), cev[1], dict(cev[2], events=[{"event": "ABEND", "abcode": "KIDA"}])]
    diffs = ec.compare_events(cev, other)["diffs"]
    assert [d["fields"][0]["field"] for d in diffs] == ["channel", "events"]


def test_exec_in_a_literal_or_a_debugging_line_is_not_a_command():
    """#4950 (CBSA CRECUST): `DISPLAY 'EXEC CICS FETCH ANY failed. RESP='` is a literal, and an EXEC CICS on a
    debugging line (indicator D) is a comment as cobc reads it without WITH DEBUGGING MODE; with that clause in force the
    program is refused by name. The LE models are linked when the program itself CALLs a CEE service, and the det
    translator's CEEIGZCT stand-in (register L4) is the COPY member where the estate has none."""
    assert ec._in_literal("    DISPLAY 'EXEC CICS FETCH", 13) and not ec._in_literal("    EXEC CICS RETURN", 4)
    assert ec._in_literal('    DISPLAY "A" "EXEC', 17) and not ec._in_literal("    MOVE 'IT''S' TO X EXEC", 22)
    src = ("       PROCEDURE DIVISION.\n"
           "           DISPLAY 'EXEC CICS FETCH ANY failed. RESP=' WS-R\n"
           "      D    EXEC CICS ASKTIME ABSTIME(START-DEQ) END-EXEC\n"
           "           EXEC CICS RETURN END-EXEC.\n")  # fmt: skip
    assert [b[3].strip() for b in ec._exec_blocks(src.splitlines())] == ["RETURN"]
    with pytest.raises(ec.Unsupported, match="WITH DEBUGGING MODE"):
        ec.translate("       SOURCE-COMPUTER. IBM-370 WITH DEBUGGING MODE.\n" + src)
    assert (ec.DET_COPY / "CEEIGZCT.cpy").is_file()


def test_extract_web_is_web_extract_for_the_stub():
    """#4972 (register X38): EXTRACT WEB (IBM: "a synonym of WEB EXTRACT") is the same GGCWEXT call and moves, with the same
    refusals."""
    opts = ("SCHEME(WS-S) HOST(WS-H) HOSTLENGTH(WS-HL) HTTPMETHOD(WS-M) METHODLENGTH(WS-ML) PATH(WS-P) PATHLENGTH(WS-PL) "
            "PORTNUMBER(WS-N) REQUESTTYPE(WS-R) NOHANDLE")  # fmt: skip
    assert ec.translate_command(f"EXTRACT WEB {opts}") == ec.translate_command(f"WEB EXTRACT {opts}")
    for form in ("HOST(WS-H)", "HTTPMETHOD(WS-M)", "HTTPVERSION(WS-V)", "QUERYSTRLEN(WS-Q)", "SESSTOKEN(WS-T)",
                 "HOSTTYPE(WS-T)", "URIMAP(WS-U)"):  # fmt: skip
        with pytest.raises(ec.Unsupported) as want:
            ec.translate_command(f"WEB EXTRACT {form}")
        with pytest.raises(ec.Unsupported) as got:
            ec.translate_command(f"EXTRACT WEB {form}")
        assert str(got.value).replace("EXTRACT WEB", "WEB EXTRACT") == str(want.value), form


def test_extract_tcpip_becomes_a_stub_call():
    """#4972 (register X38): EXTRACT TCPIP -> GGCTCPX (CADDRLENGTH / CNAMELENGTH / SADDRLENGTH / SNAMELENGTH in GG-LEN /
    GG-HOURS / GG-MINS / GG-SECS, 0 for an area given without its length option; GG-FLAGS A1 N1 A2 N2 the areas given and U1
    U2 F1 F2 the numbers asked for; every area by reference with its size), then on NORMAL the lengths, each number from
    GGCTCPN and the IPv4 family (300) moved back. The option rules as the det translator's."""
    t = ec.translate_command("EXTRACT TCPIP CLIENTADDR(WS-A) CADDRLENGTH(WS-AL) SERVERNAME(WS-SN) CLIENTADDRNU(WS-CN) "
                             "SERVERADDRNU(WS-SNU) CLNTIPFAMILY(WS-CF) SRVRIPFAMILY(WS-SF) PORTNUMNU(WS-P) SSLTYPE(WS-T) "
                             "NOHANDLE")  # fmt: skip
    assert t[:5] == ["MOVE WS-AL TO GG-LEN", "MOVE 0 TO GG-HOURS", "MOVE 0 TO GG-MINS", "MOVE 0 TO GG-SECS",
                     "MOVE 'A1 N2 U1 U2 F1 F2' TO GG-FLAGS"]  # fmt: skip
    assert t[5] == "CALL 'GGCTCPX' USING GG-CICS" and t[6:8] == ["    BY REFERENCE WS-A", "    BY VALUE LENGTH OF WS-A"]
    assert t[12:14] == ["    BY REFERENCE WS-SN", "    BY VALUE LENGTH OF WS-SN"]
    tail = "\n".join(t)
    for back in ("MOVE GG-LEN TO WS-AL", "MOVE 'CNU' TO GG-FLAGS", "MOVE 'SNU' TO GG-FLAGS", "MOVE 'PORT' TO GG-FLAGS",
                 "MOVE 'SSL' TO GG-FLAGS", "CALL 'GGCTCPN' USING GG-CICS", "MOVE GG-NUM TO WS-CN", "MOVE GG-NUM TO WS-SNU",
                 "MOVE GG-NUM TO WS-P", "MOVE GG-NUM TO WS-T", "MOVE 300 TO WS-CF", "MOVE 300 TO WS-SF"):  # fmt: skip
        assert back in tail, back
    # the stub reads exactly the flag words this emits (ggcics.c GGCTCPX / GGCTCPN)
    stub = (Path(ec.__file__).resolve().parents[1] / "equivalence" / "cics" / "ggcics_web.c").read_text(
        encoding="utf-8"
    )
    for word in ("A1", "N1", "A2", "N2", "U1", "U2", "F1", "F2"):
        assert f'strstr(flags, "{word}")' in stub, word
    for word in ("CNU", "SNU", "PORT"):
        assert f'strcmp(flags, "{word}")' in stub, word
    for bad, why in (("EXTRACT TCPIP CADDRLENGTH(WS-L)", "CADDRLENGTH without CLIENTADDR"),
                     ("EXTRACT TCPIP SNAMELENGTH(WS-L)", "SNAMELENGTH without SERVERNAME"),
                     ("EXTRACT TCPIP PORTNUMBER(WS-P)", "5 characters are padded"),
                     ("EXTRACT TCPIP CLNTADDR6NU(WS-P)", "IPv6"),
                     ("EXTRACT TCPIP AUTHENTICATE(WS-P)", "authentication"),
                     ("EXTRACT TCPIP TCPIPSERVICE(WS-P)", "TCPIPSERVICE definition"),
                     ("EXTRACT TCPIP CLIENTADDR('1.2.3.4') CADDRLENGTH(WS-L)", "as a literal")):  # fmt: skip
        with pytest.raises(ec.Unsupported, match=why):
            ec.translate_command(bad)


def test_the_tcpip_connection_is_stated_alike_on_both_sides():
    """#4972 (register X38): a case's "tcpip" (the scenario's first) is checked and written for the stub, the names as hex in the
    data's page ('-' for a name the DNS does not know), and handed to CicsTask.withTcpip."""
    conn = {"client_addr": "10.1.2.3", "client_name": "client.example", "server_addr": "10.9.8.7", "server_name": None,
            "port": 8080, "ssl_type": "SSL"}  # fmt: skip
    assert ec.tcpip({"tcpip": conn}, {"name": "s"}) == conn
    assert ec.tcpip({}, {"name": "s"}) is None
    assert ec.tcpip({"tcpip": conn}, {"name": "s", "tcpip": {**conn, "ssl_type": "NOSSL"}})["ssl_type"] == "NOSSL"
    for broken in ({**conn, "port": 0}, {**conn, "ssl_type": "TLS"}, {**conn, "client_addr": ""}, {**conn, "extra": 1},
                   {**conn, "server_name": "a b"}, {**conn, "port": "80"}):  # fmt: skip
        with pytest.raises(ec.Unsupported, match="tcpip"):
            ec.tcpip({"tcpip": broken}, {"name": "s"})
    assert ec.tcpip_cfg(conn, "latin-1") == f"T 10.1.2.3 {b'client.example'.hex().upper()} 10.9.8.7 - 8080 SSL\n"
    assert 'task.withTcpip(new CicsTask.Tcpip(q.get("client_addr")' in Path(ec.__file__).read_text(encoding="utf-8")


def test_formattime_day_of_year_and_binary_forms_translate_to_cobol_of_ibms_values():
    """#4415 slice 3 (X46): YYDDD / YYYYDDD / YYDDMM / YYYYDDMM and the six binary forms, in COBOL from the task's clock."""
    out = ec.translate_command("FORMATTIME ABSTIME(T) YYDDD(A) YYYYDDD(B) YYDDMM(C) YYYYDDMM(E) DATESEP RESP(R)")
    text = "\n".join(out)
    assert "FUNCTION INTEGER-OF-DATE(GG-Y * 10000 + 101) + 1" in text  # the day of the year
    for target, parts in (("A", "GG-Y(3:2) '/' GG-DOY"), ("B", "GG-Y '/' GG-DOY"), ("C", "GG-Y(3:2) '/' GG-D '/' GG-M"),
                          ("E", "GG-Y '/' GG-D '/' GG-M")):  # fmt: skip
        assert f"STRING {parts}" in text
    for width, target in ((6, "A"), (8, "B"), (8, "C"), (10, "E")):
        assert f"MOVE GG-OUT(1:{width}) TO {target}(1:{width})" in text
    nums = ec.translate_command("FORMATTIME ABSTIME(T) DAYCOUNT(A) DAYOFMONTH(B) DAYOFWEEK(C) MONTHOFYEAR(E) YEAR(F) "
                                "MILLISECONDS(G) NOHANDLE")  # fmt: skip
    for line in ("COMPUTE A = GG-DAYS + 1", "COMPUTE B = GG-D", "COMPUTE C = FUNCTION MOD(GG-DAYS + 1, 7)",
                 "COMPUTE E = GG-M", "COMPUTE F = GG-Y", "COMPUTE G = FUNCTION MOD(T, 1000)"):  # fmt: skip
        assert line in nums
    assert all(len(s) <= 61 for s in out + nums)  # each statement fits area B


@pytest.mark.skipif(__import__("os").environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL)")
def test_formattime_day_of_year_and_binary_forms_under_gnucobol_equal_the_java_runtime(tmp_path):
    """#4415 slice 3 (X46): the translated COBOL, run under GnuCOBOL at the six instants test_cics_runtimes.py gives
    CicsTask.formatDate / formatNumber (1900-01-01, a leap day, both year ends, a century leap year): the same text."""
    import subprocess

    cpy = (Path(eq.__file__).parent.parent / "equivalence" / "cics" / "DFHEIBLK.cpy").read_text()
    gg_time = cpy[cpy.index("       01  GG-TIME.") : cpy.index("      * #4413: the address")]
    cmds = ("FORMATTIME ABSTIME(T) YYDDD(A) YYYYDDD(B) YYDDMM(C) YYYYDDMM(E) DATESEP RESP(R)",
            "FORMATTIME ABSTIME(T) DAYCOUNT(N1) DAYOFMONTH(N2) DAYOFWEEK(N3) MONTHOFYEAR(N4) YEAR(N5) MILLISECONDS(N6)")  # fmt: skip
    abs_values = (0, 3867129015123, 3918239999999, 3912969600000, 3944635200007, 3160857600000)
    src = ["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. FT.", "       DATA DIVISION.",
           "       WORKING-STORAGE SECTION.", gg_time, "       01 T PIC S9(18) COMP-3.", "       01 A PIC X(6).",
           "       01 B PIC X(8).", "       01 C PIC X(8).", "       01 E PIC X(10).", "       01 R PIC S9(8) COMP.",
           "       01 EIBRESP PIC S9(8) COMP.", "       01 EIBRESP2 PIC S9(8) COMP.",
           "       01 GG-RESP PIC S9(8) COMP.", "       01 GG-RESP2 PIC S9(8) COMP.",
           *[f"       01 N{k} PIC 9(9) COMP-5." for k in range(1, 7)], "       PROCEDURE DIVISION."]  # fmt: skip
    for v in abs_values:
        src.append(f"           MOVE {v} TO T")
        src += ["           " + ln for c in cmds for ln in ec.translate_command(c)]
        src.append("           DISPLAY A '|' B '|' C '|' E '|' N1 '|' N2 '|' N3 '|' N4 '|' N5 '|' N6")
    src.append("           STOP RUN.")
    (tmp_path / "ft.cob").write_text("\n".join(src) + "\n")
    eq.build_image()
    run = subprocess.run(["docker", "run", "--rm", "-v", f"{tmp_path}:/w", "-w", "/w", eq.IMAGE, "sh", "-c",  # noqa: S603, S607
                          "cobc -x -free -o ft ft.cob && ./ft"], capture_output=True, text=True, check=False)  # fmt: skip
    assert run.returncode == 0, run.stdout + run.stderr
    got = [[int(p) if p.lstrip("+").isdigit() and i > 3 else p for i, p in enumerate(ln.split("|"))]
           for ln in run.stdout.splitlines()]  # fmt: skip
    assert got == [
        ["00/001", "1900/001", "00/01/01", "1900/01/01", 1, 1, 1, 1, 1900, 0],
        ["22/199", "2022/199", "22/18/07", "2022/18/07", 44759, 18, 1, 7, 2022, 123],
        ["24/060", "2024/060", "24/29/02", "2024/29/02", 45350, 29, 4, 2, 2024, 999],
        ["23/365", "2023/365", "23/31/12", "2023/31/12", 45290, 31, 0, 12, 2023, 0],
        ["24/366", "2024/366", "24/31/12", "2024/31/12", 45656, 31, 2, 12, 2024, 7],
        ["00/061", "2000/061", "00/01/03", "2000/01/03", 36585, 1, 3, 3, 2000, 0],
    ]


def test_a_cases_maps_are_stated_as_the_stubs_mapsets():
    """#5076 (X31): a case's "maps" ({MAP: {"mapset": MAPSET}}, as the cics-crucible's) become the stub's
    $GGCICS_MAPSETS, so BNK1CCS's CLEAR -- SEND MAP('BNK1CCM'), the mapset's name, a map it does not hold -- abends ABM0
    on the COBOL side as it does in the det port. Several maps of one mapset are listed together, mapsets sorted."""
    assert ec.mapsets_env({"maps": {"BNK1CC": {"mapset": "BNK1CCM"}}}) == "BNK1CCM=BNK1CC"
    assert (ec.mapsets_env({"maps": {"B": {"mapset": "MSB"}, "A2": {"mapset": "MSA"}, "A1": {"mapset": "MSA"}}})
            == "MSA=A1,A2;MSB=B")  # fmt: skip


def test_map_input_justifies_a_field_as_its_dfhmdf_says_5082():
    """X54: the oracle's RECEIVE MAP input is what BMS leaves in the field: JUSTIFY=(RIGHT,ZERO) right-justified and
    zero-filled, (LEFT,ZERO) zero-filled behind the text; no JUSTIFY (a field absent from `justify`) as typed; the length
    is the text typed's either way."""
    fields = []
    for i, n in enumerate("ABC"):
        fields += [{"name": f"{n}L", "offset": i * 8, "bytes": 2, "pic": "S9(4)", "usage": "COMP"},
                   {"name": f"{n}I", "offset": i * 8 + 2, "bytes": 6, "pic": "X(06)", "usage": None}]  # fmt: skip
    got = ec.map_input(fields, {"AI": "42", "BI": "42", "CI": "42"}, justify={"AI": "RIGHT,ZERO", "BI": "LEFT,ZERO"})
    assert got == b"\x00\x02000042" + b"\x00\x02420000" + b"\x00\x0242    "
    assert ec.justified("  7 ", 4, "RIGHT") == "   7" and ec.justified("12345", 3, "RIGHT") == "345"
    assert ec.justified("", 3, "RIGHT,ZERO") == "000" and ec.justified("ab", 4, ",ZERO") == "ab00"


def test_readq_td_and_deleteq_td_become_stub_calls():
    """#5079 (register X57): READQ TD -> GGCRDTD (the queue in GG-QNAME, LENGTH in GG-LEN, INTO and its size); a data
    area LENGTH is set from GG-LEN on NORMAL and LENGERR; DELETEQ TD -> GGCDLTD. SET, SYSID and NOSUSPEND are refused by name."""
    r = ec.translate_command("READQ TD QUEUE('JOBS') INTO(REC) RESP(R)")
    assert r[:5] == ["MOVE 'JOBS' TO GG-QNAME", "MOVE LENGTH OF REC TO GG-LEN", "CALL 'GGCRDTD' USING GG-CICS",
                     "    BY REFERENCE REC", "    BY VALUE LENGTH OF REC"]  # fmt: skip
    assert "MOVE GG-RESP TO R" in r and not any("GG-LEN TO" in line for line in r)
    n = ec.translate_command("READQ TD QUEUE(WS-Q) INTO(REC) LENGTH(WS-N)")
    assert n[1] == "MOVE WS-N TO GG-LEN"
    assert n[5:8] == ["IF GG-RESP = 0 OR GG-RESP = 22", "    MOVE GG-LEN TO WS-N", "END-IF"]
    assert not any("MOVE GG-LEN TO" in line for line in ec.translate_command("READQ TD QUEUE(Q) INTO(R) LENGTH(8)"))
    d = ec.translate_command("DELETEQ TD QUEUE('JOBS') RESP(R)")
    assert d[:2] == ["MOVE 'JOBS' TO GG-QNAME", "CALL 'GGCDLTD' USING GG-CICS"] and "MOVE GG-RESP TO R" in d
    for body, said in (("READQ TD QUEUE(Q) INTO(A) SYSID('S')", "SYSID"), ("DELETEQ TD QUEUE(Q) SYSID('S')", "SYSID"),
                       ("READQ TD INTO(A)", "QUEUE"), ("READQ TD QUEUE(Q)", "INTO"), ("DELETEQ TD", "QUEUE")):  # fmt: skip
        with pytest.raises(ec.Unsupported, match=said):
            ec.translate_command(body)


def test_readq_td_set_and_nosuspend_5168():
    """#5168 (X61): READQ TD SET(ptr) LENGTH(area) is GGCRDTS (the record as a block, its length to the area); NOSUSPEND changes
    nothing; INTO with SET, SET with no LENGTH area or a literal one are refused."""
    r = ec.translate_command("READQ TD QUEUE('Q1') SET(PTR) LENGTH(WS-N) NOSUSPEND RESP(R)")
    assert r[0] == "MOVE 'Q1' TO GG-QNAME" and "CALL 'GGCRDTS' USING GG-CICS" in r and "    BY REFERENCE PTR" in r
    assert "    MOVE GG-LEN TO WS-N" in r and "MOVE GG-RESP TO R" in r
    n = ec.translate_command("READQ TD QUEUE(Q) INTO(A) LENGTH(WS-N) NOSUSPEND")
    assert "CALL 'GGCRDTD' USING GG-CICS" in n
    for body in ("READQ TD QUEUE(Q) INTO(A) SET(P) LENGTH(N)", "READQ TD QUEUE(Q) SET(P)", "READQ TD QUEUE(Q) SET(P) LENGTH(8)",
                 "READQ TD QUEUE(Q) SET(P(1)) LENGTH(N)"):  # fmt: skip
        with pytest.raises(ec.Unsupported):
            ec.translate_command(body)


def test_csd_tdqueue_attributes_5168(tmp_path):
    (tmp_path / "c.csd").write_text(
        "DEFINE TDQUEUE(AAAA) GROUP(G) TYPE(INTRA) RECOVSTATUS(LOGICAL) TRANSID(TRN1) TRIGGERLEVEL(3)\n"
        "DEFINE TDQUEUE(XXXX) GROUP(G) TYPE(EXTRA) TYPEFILE(INPUT) OPENTIME(DEFERRED)\n"
        "DEFINE TDQUEUE(IIII) GROUP(G) TYPE(INDIRECT) INDIRECTNAME(AAAA)\n"
        "DEFINE TDQUEUE(BBBB) GROUP(G) TYPE(INTRA)\n",
        encoding="ascii",
    )
    got = ec.csd_tdqueue_attrs(tmp_path, {"csd": "c.csd"})
    assert got == {"AAAA": {"RECOVSTATUS": "LOGICAL", "TRANSID": "TRN1", "TRIGGERLEVEL": "3"},
                   "XXXX": {"TYPEFILE": "INPUT", "OPENTIME": "DEFERRED"}, "IIII": {"INDIRECTNAME": "AAAA"}}  # fmt: skip
    assert ec.csd_tdqueue_attrs(tmp_path, {}) == {}
    assert ec.td_seed({}, {}) == {} and ec.td_seed({"td": {"Q": ["a"]}}, {"td": {"R": ["b"]}}) == {"R": ["b"]}
    with pytest.raises(ec.Unsupported):
        ec.td_seed({"td": {"TOOLONG": ["a"]}}, {})


def test_a_td_seed_may_hold_any_text_its_data_encoding_holds_whole():
    """#5168 (X61): a seeded record is text in the case's data page (Latin-1 by default, any single-space page): non-ASCII is fine
    where the page holds it and decodes back to the same text; a character the page lacks is refused, never replaced."""
    ec.td_seed({"td": {"Q": ["caf\u00e9", "\u00dcber"]}}, {})
    assert ec.td_seed({"data_encoding": "cp037", "td": {"Q": ["\u00e9"]}}, {}) == {"Q": ["\u00e9"]}
    for case in ({"td": {"Q": ["\u20ac"]}}, {"data_encoding": "cp037", "td": {"Q": ["\u4e2d"]}}):
        with pytest.raises(ec.Unsupported):
            ec.td_seed(case, {})
    with pytest.raises(ec.Unsupported):
        ec.td_seed({"td": {"Q\u00e9": ["a"]}}, {})


def test_the_td_queue_types_a_csd_defines_are_read_with_their_names(tmp_path):
    """#5079 (X57): `csd_tdqueue_types` is each DEFINE TDQUEUE's TYPE ("" when none), and `csd_tdqueues` its names."""
    (tmp_path / "x.csd").write_text(
        "DEFINE TDQUEUE(JOBS) GROUP(G) TYPE(EXTRA) DDNAME(JOBS)\n"
        "DEFINE TDQUEUE(AUDQ)\n  GROUP(G)\n  TYPE(INTRA)\n"
        "DEFINE TDQUEUE(NONE) GROUP(G)\n"
        "DEFINE PROGRAM(P) TYPE(X)\n", encoding="latin-1")  # fmt: skip
    case = {"csd": "x.csd"}
    assert ec.csd_tdqueue_types(tmp_path, case) == {"JOBS": "EXTRA", "AUDQ": "INTRA", "NONE": ""}
    assert ec.csd_tdqueues(tmp_path, case) == ["AUDQ", "JOBS", "NONE"]
    assert ec.csd_tdqueue_types(tmp_path, {}) is None and ec.csd_tdqueues(tmp_path, {}) is None


def test_a_scenario_states_its_own_clock_else_the_cases():
    """#4622: `scenario_clock` is the scenario's "clock", else the case's; `clock_iso` follows it (a December task's
    $GGCICS_NOW), and the one-argument form is the case's as before."""
    case = {"clock": "2022/07/18 10:30:15.00"}
    assert ec.scenario_clock(case, {"name": "a"}) == "2022/07/18 10:30:15.00"
    assert ec.scenario_clock(case, {"name": "b", "clock": "2022/12/18 10:30:15.00"}) == "2022/12/18 10:30:15.00"
    assert ec.clock_iso(case) == "2022-07-18T10:30:15"
    assert ec.clock_iso(case, {"name": "a"}) == "2022-07-18T10:30:15"
    assert ec.clock_iso(case, {"name": "b", "clock": "2022/12/18 10:30:15.00"}) == "2022-12-18T10:30:15"
    for bad in ("2022-12-18T10:30:15", "2022/12/18 10:30:15", 5):
        with pytest.raises(ec.Unsupported):
            ec.scenario_clock(case, {"name": "c", "clock": bad})


def test_a_scenario_states_its_own_records_for_a_dataset_of_the_case():
    """#4622: `scenario_datasets` is each overridden DD's spec with the scenario's `input` / `append`, the case
    untouched; no override is {}; a DD the case lacks, a stray key or a generated dataset is refused."""
    spec = {"input": "a.txt", "append": "x.txt", "entity": "E", "copybook": "c.cpy", "record": "R"}
    case = {"datasets": {"DD1": spec, "GEN": {"input": "@generate"}}}
    before = repr(case)
    assert ec.scenario_datasets(case, {"name": "a"}) == {}
    assert ec.scenario_datasets(case, {"name": "a", "datasets": {}}) == {}
    got = ec.scenario_datasets(case, {"name": "b", "datasets": {"DD1": {"input": "@case/seed/b.txt"}}})
    assert got == {"DD1": {"input": "@case/seed/b.txt", "entity": "E", "copybook": "c.cpy", "record": "R"}}
    got = ec.scenario_datasets(case, {"name": "b", "datasets": {"DD1": {"append": "y.txt"}}})
    assert got["DD1"]["input"] == "a.txt" and got["DD1"]["append"] == "y.txt"
    assert repr(case) == before
    for bad in ({"NOPE": {"input": "z"}}, {"DD1": {"entity": "F"}}, {"GEN": {"input": "z"}}, {"DD1": "z"}):
        with pytest.raises(ec.Unsupported):
            ec.scenario_datasets(case, {"name": "c", "datasets": bad})


def test_a_syncpoint_rollback_restarts_the_file_unit_of_work_instead_of_ending_it_5089(tmp_path):
    """IBM: SYNCPOINT ROLLBACK ends the unit of work and the next recoverable change starts a new one (register Q3).
    The rollback hook restarts the file transaction (cbsa-delcus's DELETE after INQACCCU's rollback is kept); an
    abend, a refusal or a failed run still marks the CURRENT unit rollback-only, with or without a Db2 database."""
    import equivalence_java as ej

    svc = tmp_path / "service" / f"{ej._service_class('PROG')}.java"
    svc.parent.mkdir(parents=True)
    svc.write_text("public void handleTransaction(String transid, ProgCa request) {}", encoding="utf-8")
    case = {**_facade_case(), "clock": "2026/10/01 10:30:15.00", "screens": {}}
    java = ec.cics_equivalence_test(case, tmp_path, [])
    assert "task.onRollback(() -> { status.restart(); });" in java
    assert "task.onRollback(() -> { status.setRollbackOnly();" not in java
    assert "fileUnit(status -> {" in java
    assert java.count("status.setRollbackOnly();") >= 2  # the refused and failed-run paths: the current unit
    restart = java[java.index("void restart()") :].split("void end()")[0]
    assert "tm.rollback(st);" in restart and "tm.getTransaction(" in restart


@pytest.mark.parametrize("case", ["carddemo-acctview", "carddemo-cardview", "carddemo-signon"])
def test_a_carddemo_hand_ports_send_text_carries_the_erase_freekb_its_cobol_passes(case):
    """#5440: every CardDemo SEND TEXT ends ERASE FREEKB; #5412 compares the options, so a port that drops them fails."""
    import re

    sent = []
    for src in sorted((Path(__file__).resolve().parents[1] / "equivalence" / case / "port").rglob("*.java")):
        for call in re.findall(r"\.sendText\((.*?)\);", src.read_text(encoding="utf-8"), re.S):
            # the one SEND FROM(ABEND-DATA) in COCRDSLC is a plain SEND, not SEND TEXT: it has no options
            if "abendCode" not in call and "data, 134" not in call:
                sent.append(call)
    assert sent, "the port sends no text: the scan found nothing to check"
    for call in sent:
        assert '"ERASE"' in call and '"FREEKB"' in call, call


class _NoFilesIR:
    """An estate whose program names no CICS file the facts carry (zECS ZECS003 builds ZC##FILE at run time)."""

    files: dict = {}

    @staticmethod
    def cics_file_lineage():
        return []


_RUNTIME_FILE = {
    "key_offset": 0,
    "key_length": 16,
    "reclen": 32700,
    "why": "ZECSFILE.idcams: KEYS(16 0) RECORDSIZE(100 32700)",
}


def test_a_case_states_a_file_the_program_names_at_run_time():
    """#4771: ZC01FILE is ZC + EIBTRNID(3:2) + FILE, so no CSD DEFINE FILE of the facts names it; the case's dataset of
    that name states its KEYS and RECORDSIZE with a why, for the COBOL leg only (`runtime`)."""
    got = ec.stub_files(_NoFilesIR(), "p.cbl", {"ZC01FILE": {"runtime_file": _RUNTIME_FILE}})
    assert got == [
        {
            "file": "ZC01FILE",
            "dsname": "ZC01FILE",
            "base": "ZC01FILE",
            "key_offset": 0,
            "key_length": 16,
            "reclen": 32700,
            "via": ["the case's runtime_file"],
            "runtime": True,
        }  # fmt: skip
    ]
    assert ec.stub_files(_NoFilesIR(), "p.cbl", {}) == []
    for wrong in (
        {k: v for k, v in _RUNTIME_FILE.items() if k != "why"},
        {k: v for k, v in _RUNTIME_FILE.items() if k != "reclen"},
        {**_RUNTIME_FILE, "key_length": "16"},
        {**_RUNTIME_FILE, "variable": True},
    ):
        with pytest.raises(ec.Unsupported):
            ec.stub_files(_NoFilesIR(), "p.cbl", {"ZC01FILE": {"runtime_file": wrong}})
    with pytest.raises(ec.Unsupported):  # a CICS file name is at most 8 upper-case characters
        ec.stub_files(_NoFilesIR(), "p.cbl", {"zc01file": {"runtime_file": _RUNTIME_FILE}})


def test_a_clock_value_inside_a_writeq_record_is_masked_like_a_commarea_clock():
    """X6 (past FROM): a WRITEQ record that carries the run's clock (LGAPDB01's CICA line) differs between the two runs
    only by the moment; a stale or scenario-written timestamp is still compared exactly."""
    import datetime

    now = datetime.datetime.now().strftime("%Y-%m-%d-%H.%M.%S.%f")
    case = {"clock_fields": {"commarea": ["CA-REQUEST-SPECIFIC(31:26)"]}}
    counter = [0]
    events = [
        {"verb": "WRITEQ-TD", "text": f"CICA COMMAREA=01A{now}   "},
        {"verb": "WRITEQ-TS", "data": "2001-01-01-00.00.00.000000"},
    ]
    out = ec.mask_clock_events(case, events, counter)
    assert out[0]["text"] == "CICA COMMAREA=01A<clock>   "
    assert out[1]["data"] == "2001-01-01-00.00.00.000000"
    assert counter == [1]


def test_no_recorded_proof_judges_a_task_up_to_the_x6_writeq_refusal():
    """#6271: since #6573 only a WRITEQ LENGTH over 32767 is refused, and no burned program has one. So no committed
    evidence record holds a task `judged_to` the X6 refusal (a task judged up to a LINK or X23 may still appear); one
    that does means a burned program now needs a model for it, not a note."""
    import json

    root = Path(__file__).resolve().parents[1] / "equivalence"
    files = sorted(root.glob("*/evidence.json"))
    assert len(files) > 20  # the glob found the corpus, not an empty directory
    judged = []

    def walk(node, where):
        if isinstance(node, dict):
            if node.get("judged_to") and node.get("assumes") == "X6":
                judged.append(where)
            for k, v in node.items():
                walk(v, f"{where}/{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{where}[{i}]")

    for path in files:
        walk(json.loads(path.read_text(encoding="utf-8")), path.parent.name)
    assert judged == [], judged
