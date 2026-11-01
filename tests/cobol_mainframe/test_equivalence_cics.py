"""#3754: the CICS half of the equivalence harness, without a container.

The translator is pinned per command (what each EXEC CICS becomes, and that an unknown one
is refused by name, never skipped), the stub's file table is derived from a real scan of a
small estate -- CSD DEFINE FILE -> DSNAME -> IDCAMS KEYS, a PATH through its AIX -- and the
pieces the comparison stands on are pinned: field encoding round-trips, a DTO's shape read
from its comments, and events compared field by field. A test of one family goes in its
test_equivalence_cics_<family>.py (#5274), so slices of different families do not collide here.
"""

import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence as eq  # noqa: E402
import equivalence_cics as ec  # noqa: E402
from cics_test_cases import facade_case as _facade_case  # noqa: E402
from scan_server import scan_to_db  # noqa: E402

from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir  # noqa: E402


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
    # X15: with SET, LENGTH is output-only, so no MAXLENGTH means all the input (the stub's whole buffer), both SET forms
    for cmd in ("RECEIVE SET(ADDRESS OF LS-IN) LENGTH(WS-L)", "RECEIVE SET(WS-P) LENGTH(WS-L) NOTRUNCATE"):
        assert "MOVE 32768 TO GG-LEN" in ec.translate_command(cmd)
    for bad in ("RECEIVE SET(ADDRESS OF LS-IN) MAXLENGTH(9)", "RECEIVE SET(WS-P) MAXLENGTH(9)"):
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
                                  "RECEIVE INTO(X) LENGTH(L) BUFFER", "RECEIVE SET(P) MAXLENGTH(9)", "STARTBR FILE(F) RIDFLD(K) REQID(1)",
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


def test_send_text_length_is_compared_both_sides():
    """#5862: the stub's len= is the LENGTH the program passed; a Java event with another length differs."""
    res = {
        "events": ["SEND-TEXT len=72 opts=TEXT", "RETURN pgm=P level=1 transid= len=0"],
        "screens": [],
        "text": ["HELLO"],
        "text_options": [[]],
        "text_lengths": [72],
        "return": {"transid": "", "commarea": None},
    }
    cobol = ec.cobol_events(res)
    assert cobol[0]["length"] == 72
    ret = {"event": "RETURN", "transid": None, "commarea": None}

    def java(n):
        return [{"event": "SEND-TEXT", "text": "HELLO", "options": [], **({} if n is None else {"length": n})}, ret]

    assert ec.compare_events(cobol, java(72))["equal"] == 2
    for wrong in (73, None):
        got = ec.compare_events(cobol, java(wrong))
        assert got["equal"] == 1 and got["diffs"][0]["fields"][0]["field"] == "length"
    legacy = ec.cobol_events({**res, "text_lengths": []})  # no len logged: not compared
    assert "length" not in legacy[0] and ec.compare_events(legacy, java(73))["equal"] == 2


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
    import re
    import shutil
    import subprocess

    port = tmp_path / "port"
    shutil.copytree(eq.CASES / "carddemo-menu" / "port", port)
    (port / "provenance.json").unlink()
    svc = port / "service" / "Comen01cService.java"
    text = svc.read_text(encoding="utf-8")
    # both handleTransaction overloads (the DTO one and, since #4870, the byte-carrying one the harness prefers, #4965)
    joined = re.compile(r'        CicsTask task = region\.transaction\(transid, request(?:, area)?\);\n'
                        r'        region\.run\(task, "COMEN01C", this::runTask\);')  # fmt: skip
    own_task = ('        CicsTask task = new CicsTask(transid, "ENTER", request, null, java.util.Map.of());\n'
                "        runTask(task);")  # fmt: skip
    mutated, n = joined.subn(lambda _: own_task, text)
    assert n == 2
    svc.write_text(mutated, encoding="utf-8")
    proc = subprocess.run([sys.executable, str(Path(eq.__file__)), "run", "carddemo-menu", "--port", str(port),  # noqa: S603
                           "--keep", str(tmp_path / "w")], capture_output=True, text=True, check=False)  # fmt: skip
    report = json.loads((tmp_path / "w" / "report.json").read_text())
    assert proc.returncode == 1 and report["proven"] is False
    assert all(o["equal"] == o["records"] for o in report["outputs"].values())  # runTask: unchanged, passes
    facade = report["facade"]["outputs"]
    assert facade and all(not o["pass"] and o.get("refused") for o in facade.values())
    assert report["facade"]["entry_points"] == []


# ---- #4449: the java-facade side's verdicts -------------------------------------------------------------------
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
