"""#5274: a task started with a channel, and the containers it leaves compared (X24). Split out of test_equivalence_cics.py, which every CICS slice appended to."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence as eq  # noqa: E402
import equivalence_cics as ec  # noqa: E402
from cics_test_cases import facade_case as _facade_case  # noqa: E402


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


def test_a_scenario_states_its_own_transid_else_the_cases():
    """#6072: `scenario_transid` is the scenario's "transid", else the case's; a value that is not one to four
    characters is refused by name, and the case is left untouched."""
    case = _facade_case()
    before = repr(case)
    assert ec.scenario_transid(case, {"name": "a"}) == "T001"
    assert ec.scenario_transid(case, {"name": "b", "transid": "HCA1"}) == "HCA1"
    assert ec.scenario_transid(case, {"name": "c", "transid": "X"}) == "X"
    assert repr(case) == before
    for bad in ("", "TOOLG", 5, None):
        with pytest.raises(ec.Unsupported, match="transid"):
            ec.scenario_transid(case, {"name": "d", "transid": bad})
    src = inspect.getsource(ec)
    assert "scenario_transid(case, sc):<4}" in src  # eib.in, the COBOL side
    assert 'new CicsTask(sc.path("transid").asText(' in src  # the Java side


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
