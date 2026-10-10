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
    assert got[:4] == ["MOVE LIT-ACCTFILENAME TO GG-NAME1", "MOVE SPACES TO GG-FLAGS",  # not UPDATE: holds nothing
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
    assert got[:5] == ["MOVE 'CASUB' TO GG-NAME1", "MOVE 100 TO GG-LEN", "MOVE 1 TO GG-ITEM",
                       "MOVE SPACES TO GG-FLAGS", "CALL 'GGCLINK' USING GG-CICS"]  # fmt: skip
    assert got[6:13] == ["IF GG-RESP = 0", "    CALL 'GGCRUN' USING WS-CA100", "    CALL 'GGCLRET' USING GG-CICS",
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
    for body in ("RETRIEVE SET(P) LENGTH(L)", "CANCEL", "START INTERVAL(0)", "START TRANSID('X') SYSID('R')",
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
    channel; ASSIGN CHANNEL reads it back. The CCSID options, SET and RETURN CHANNEL are refused by name."""
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
        "GET CONTAINER(C) INTO(A) INTOCCSID(1140)",
        "PUT CONTAINER(C) FROM(A) FROMCCSID(37)",
        "GET CONTAINER(C) SET(P) FLENGTH(L)",
        "GET CONTAINER(C) FLENGTH(L)",
        "RETURN TRANSID('T') CHANNEL(C)",
        "LINK PROGRAM('P') CHANNEL(C) COMMAREA(A)",
        "MOVE CONTAINER(A) AS(B)",
        "PUT CONTAINER(C) FROM(A) BIT CHAR",
    ):
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
    # a LENGTH past the FROM item stops the run, refused by name (oracle_assumptions.md X6)
    assert w[4:9] == ["IF GG-LEN > LENGTH OF WS-ONE", "    DISPLAY 'WRITEQ TS LENGTH > FROM: not modelled'",
                      "    MOVE 98 TO RETURN-CODE", "    STOP RUN", "END-IF"]  # fmt: skip
    assert ["IF GG-RESP = 0", "    MOVE GG-ITEM TO WS-I", "END-IF"] == w[11:14]
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


@pytest.mark.parametrize("body", ["READ FILE(F) RIDFLD(K) INTO(R) GENERIC", "READQ TS QUEUE(Q) SET(P) LENGTH(L)",
                                  "HANDLE ABEND PROGRAM('X')", "ASSIGN OPID(U)", "HANDLE CONDITION NOSUCH(X)",
                                  "WRITEQ TS QUEUE(Q) FROM(A) SYSID(S)", "WRITEQ TS QUEUE(Q) FROM(A) REWRITE",
                                  "READQ TD QUEUE(Q) INTO(A)",
                                  "RECEIVE INTO(X) LENGTH(L) BUFFER", "RECEIVE SET(P) LENGTH(L)", "STARTBR FILE(F) RIDFLD(K) REQID(1)",
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
    assert ec.FACADE_JAVA in java


# ---- file updates: WRITE, REWRITE, READ UPDATE, SYNCPOINT (CardDemo's update programs) -----------------------
def test_file_updates_translate_to_stub_calls():
    upd = ec.translate_command("READ DATASET(WS-F) INTO(R) RIDFLD(K) UPDATE RESP(X)")
    assert upd[:4] == ["MOVE WS-F TO GG-NAME1", "MOVE 'UPDATE' TO GG-FLAGS", "MOVE LENGTH OF R TO GG-LEN",
                       "CALL 'GGCREAD' USING GG-CICS"]  # fmt: skip
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
        ec.translate_command("ASSIGN OPID(U)")


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


def test_assign_startcode_userid_and_the_terminal_facts_translate():
    """#4270 slice 3: STARTCODE / USERID through GGCASGN; FACILITY / SCRNHT / SCRNWD behind TERMCHK (INVREQ RESP2 5 for
    a task with no terminal, then no data area written), with the condition's handling."""
    got = ec.translate_command("ASSIGN STARTCODE(SC) USERID(U)")
    assert got[:6] == ["MOVE 'STARTCOD' TO GG-NAME2", "CALL 'GGCASGN' USING GG-CICS", "MOVE GG-NAME1(1:2) TO SC",
                       "MOVE 'USERID' TO GG-NAME2", "CALL 'GGCASGN' USING GG-CICS", "MOVE GG-NAME1(1:8) TO U"]  # fmt: skip
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
        ec.translate_command("GETMAIN SET(P) LENGTH(10)")
    assert str(e.value).startswith("EXEC CICS GETMAIN not modelled (storage CICS acquires")
    assert e.value.features == ["GETMAIN"]
    with pytest.raises(ec.Unsupported, match=r"^line 2: EXEC CICS GETMAIN not modelled \("):  # (named once)
        ec.translate("       PROCEDURE DIVISION.\n           EXEC CICS GETMAIN SET(P) LENGTH(10) END-EXEC.\n")
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
    assert "    MOVE GG-NUM TO WS-V" in q
    with pytest.raises(ec.Unsupported, match="MINIMUM"):
        ec.translate_command("QUERY COUNTER(WS-C) VALUE(WS-V) MINIMUM(WS-M)")
    with pytest.raises(ec.Unsupported, match="VALUE"):
        ec.translate_command("QUERY COUNTER(WS-C)")
    assert "MOVE GG-NAME1 TO" not in " ".join(ec.translate_command("RECEIVE MAP('M') MAPSET('S') INTO(WS-I) TERMINAL"))


def test_define_and_delete_counter_become_stub_calls():
    """#4270 (register X30): DEFINE COUNTER -> GGCDCNT (VALUE in GG-NUM, zero when omitted), DELETE COUNTER -> GGCXCNT;
    MINIMUM / MAXIMUM / NOSUSPEND / DCOUNTER are refused by name; GET COUNTER takes RESP2."""
    d = ec.translate_command("DEFINE COUNTER(WS-C) POOL(WS-P) VALUE(WS-V) RESP(R) RESP2(R2)")
    assert d[:4] == [
        "MOVE WS-C TO GG-QNAME",
        "MOVE WS-P TO GG-NAME1",
        "MOVE WS-V TO GG-NUM",
        "CALL 'GGCDCNT' USING GG-CICS",
    ]
    assert "MOVE GG-RESP2 TO R2" in d
    assert "MOVE 0 TO GG-NUM" in ec.translate_command("DEFINE COUNTER(WS-C) RESP(R)")
    x = ec.translate_command("DELETE COUNTER(WS-C) POOL(WS-P) RESP(R)")
    assert x[:3] == ["MOVE WS-C TO GG-QNAME", "MOVE WS-P TO GG-NAME1", "CALL 'GGCXCNT' USING GG-CICS"]
    for bad in (
        "DEFINE COUNTER(WS-C) MINIMUM(WS-M)",
        "DEFINE COUNTER(WS-C) MAXIMUM(WS-M)",
        "DEFINE COUNTER(WS-C) NOSUSPEND",
        "DEFINE DCOUNTER(WS-C)",
        "DELETE DCOUNTER(WS-C)",
        "DELETE COUNTER(WS-C) NOSUSPEND",
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
    with pytest.raises(ec.Unsupported, match="only the browse is modelled"):
        ec.translate_command("INQUIRE URIMAP(WS-M) PATH(WS-P)")
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
    assert ec.ts_seed(case, {"name": "a"}) == {"GENACNTL": ["**** GENAPP CNTL"]}
    assert ec.ts_seed(case, {"name": "b", "ts": {}}) == {}
    for bad in ({"startcode": "D"}, {"terminal": 5}):
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
    (GenApp's IF EIBCALEN < 91, its '98' returns). 1 to the record's length; never on a scenario with no COMMAREA."""
    fields = [{"name": "CA-A", "offset": 0, "bytes": 2}, {"name": "CA-B", "offset": 2, "bytes": 98}]
    assert ec.commarea_length({"name": "s", "commarea": {}}, fields) is None
    assert ec.commarea_length({"name": "s", "commarea": {}, "commarea_length": 60}, fields) == 60
    assert ec.commarea_length({"name": "s", "commarea": {}, "commarea_length": 100}, fields) == 100
    for bad in (0, 101, -1, "60", True, 6.0):
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
