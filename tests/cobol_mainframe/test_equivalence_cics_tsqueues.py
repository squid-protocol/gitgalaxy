"""#5274: WRITEQ TS on both sides, and X6 judged up to the refused WRITEQ (#4607). Split out of test_equivalence_cics.py, which every CICS slice appended to."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_cics as ec  # noqa: E402
from cics_test_cases import facade_case as _facade_case  # noqa: E402


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
