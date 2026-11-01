"""#5274: the stub refuses what the det translator refuses, with the same message (#4270 spec PR 3). Split out of test_equivalence_cics.py, which every CICS slice appended to."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_cics as ec  # noqa: E402

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
    assert t[:3] == ["MOVE WS-M TO GG-NUM", "MOVE 'MEDIA RAW' TO GG-FLAGS", "CALL 'GGCWRCV' USING GG-CICS"]
    assert t[3:7] == [
        "    BY REFERENCE WS-B",
        "    BY VALUE LENGTH OF WS-B",
        "    BY REFERENCE WS-T",
        "    BY VALUE LENGTH OF WS-T",
    ]
    assert t[7:10] == ["IF GG-RESP = 0 OR GG-RESP2 = 57", "    MOVE GG-LEN TO WS-L", "END-IF"]
    assert ec.translate_command("WEB RECEIVE INTO(WS-B) MAXLENGTH(WS-M) SRVCONVERT")[1] == "MOVE 'CONV' TO GG-FLAGS"
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
