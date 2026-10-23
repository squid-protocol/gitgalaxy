"""#4767 (X37): the crucible runner's HTTP driver -- an inbound request is a task, its WEB-SEND is the peer's response.

Pure Python: no GnuCOBOL, no Maven. Pinned: the SERVER URIMAP match (SCHEME, HOST or `*`, PATH or a `*` prefix,
STATUS), the scheduler starting one `http` task per request in time order, a request the case cannot serve being a
defined `http-peer` failure, the response check against the client peer's stated responses, the EVENTUAL WEB-SEND
moved ahead of its RETURN, and the comparator refusing http-triggered tasks on a side that cannot run them.
"""

import datetime
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
import cics_crucible as runner  # noqa: E402
import cics_crucible_compare as cc  # noqa: E402

CSD = """
DEFINE PROGRAM(GTHECHO) GROUP(G) LANGUAGE(COBOL)
DEFINE TRANSACTION(GT81) GROUP(G) PROGRAM(GTHECHO)
DEFINE URIMAP(ECHOURI) GROUP(G) USAGE(SERVER) SCHEME(HTTP)
       HOST(*) PATH(/crucible/echo) TRANSACTION(GT81) PROGRAM(GTHECHO)
DEFINE URIMAP(OTHERURI) GROUP(G) USAGE(SERVER) SCHEME(HTTP)
       HOST(*) PATH(/crucible/other/*) TRANSACTION(GT81) PROGRAM(GTHECHO)
DEFINE URIMAP(OFFURI) GROUP(G) USAGE(SERVER) SCHEME(HTTP) STATUS(DISABLED)
       HOST(*) PATH(/crucible/off) TRANSACTION(GT81) PROGRAM(GTHECHO)
"""


def _req(at: int, body: str = "HELLO", path: str = "/crucible/echo", peer: str = "client-a") -> dict:
    return {"at": at, "peer": peer, "method": "POST", "scheme": "HTTP", "host": "crucible.example", "path": path,
            "mediatype": "text/plain", "body": body}  # fmt: skip


def _case(*responses: str) -> cc.Case:
    data = {"id": "x", "clock": "2026-01-01T10:00:00", "terminal": "T001",
            "peers": {"client-a": {"responses": [{"status": 200, "mediatype": "text/plain", "body": b} for b in responses]}}}  # fmt: skip
    return cc.Case(Path("."), data, {}, cc.parse_csd(CSD))


def _task(request: int, body: str, status: int = 200, extra: list | None = None) -> dict:
    send = {"event": "WEB-SEND", "status": status, "statustext": None, "mediatype": "text/plain", "resp": "NORMAL",
            "from": cc.RawArea(body.encode("latin-1"), "latin-1")}  # fmt: skip
    return {"program": "GTHECHO", "termid": None, "trigger": {"kind": "http", "request": request},
            "events": [{"event": "RETURN", "level": 1}, send, *(extra or [])], "end": "normal"}  # fmt: skip


def test_urimap_match_is_scheme_host_path_and_enabled():
    case = _case("a")
    base = {"scheme": "HTTP", "host": "h", "path": "/crucible/echo"}
    assert runner.server_urimap_matches(case, base) == ["ECHOURI"]
    assert runner.server_urimap_matches(case, {**base, "path": "/crucible/other/x/y"}) == ["OTHERURI"]
    assert runner.server_urimap_matches(case, {**base, "path": "/crucible/other"}) == []
    assert runner.server_urimap_matches(case, {**base, "path": "/crucible/off"}) == []  # STATUS(DISABLED)
    assert runner.server_urimap_matches(case, {**base, "scheme": "HTTPS"}) == []


def test_plan_resolves_the_transaction_and_refuses_what_it_cannot_serve():
    case = _case("a")
    plan, why = runner.http_plan(case, {"requests": [_req(0), _req(5, "AB")]})
    assert why is None
    assert [(h["index"], h["at"], h["transid"]) for h in plan] == [(0, 0, "GT81"), (1, 5, "GT81")]
    assert plan[0]["request"]["body"] == "HELLO"
    assert "names peer 'nobody'" in runner.http_plan(case, {"requests": [_req(0, peer="nobody")]})[1]
    assert "matches 0 server URIMAPs" in runner.http_plan(case, {"requests": [_req(0, path="/nope")]})[1]


def test_each_request_is_one_http_task_in_time_order():
    case = _case("ECHO:HELLO", "ECHO:AB")
    sc = {"steps": [], "until": 60, "requests": [_req(5, "AB"), _req(0)]}
    seen = []

    def run_one(frame, transid, commarea, step, data, unexpired):
        seen.append((frame["at"], frame["trigger"], frame["startcode"], frame["http_request"]["body"], transid))
        return _task(frame["trigger"]["request"], "x")

    tasks, stopped = runner.drive_scenario(case, sc, run_one)
    assert stopped is None and len(tasks) == 2
    assert seen == [("2026-01-01T10:00:05", {"kind": "http", "request": 0}, None, "AB", "GT81"),
                    ("2026-01-01T10:00:00", {"kind": "http", "request": 1}, None, "HELLO", "GT81")][::-1]  # fmt: skip
    assert datetime.datetime.fromisoformat(seen[0][0]) < datetime.datetime.fromisoformat(seen[1][0])


def test_an_unservable_request_stops_the_scenario():
    tasks, stopped = runner.drive_scenario(_case("a"), {"steps": [], "requests": [_req(0, path="/nope")]}, None)
    assert tasks == [] and stopped.startswith("http-peer:")


def test_peer_check_compares_status_media_type_and_body():
    case = _case("ECHO:HELLO", "ECHO:AB")
    sc = {"requests": [_req(0), _req(5, "AB")]}
    ok = [_task(0, "ECHO:HELLO"), _task(1, "ECHO:AB")]
    assert runner.http_peer_log(case, sc, ok) == {}
    bad = runner.http_peer_log(case, sc, [_task(0, "ECHO:HELLO"), _task(1, "ECHO:XX")])
    assert "response body 'ECHO:XX', the peer states 'ECHO:AB'" in bad["http_peer"]
    assert "status 500" in runner.http_peer_log(case, sc, [_task(0, "ECHO:HELLO", 500)])["http_peer"]
    two = _task(0, "ECHO:HELLO", extra=[_task(0, "again")["events"][1]])
    assert "sent 2 responses" in runner.http_peer_log(case, sc, [two])["http_peer"]
    silent = _task(0, "")
    silent["events"] = silent["events"][:1]
    assert "sent 0 responses" in runner.http_peer_log(case, sc, [silent])["http_peer"]
    assert "states no response #2" in runner.http_peer_log(_case("ECHO:HELLO"), sc, ok)["http_peer"]


def test_an_eventual_send_is_logged_before_the_return_it_trails():
    t = _task(0, "ECHO:HELLO")
    assert [e["event"] for e in runner.http_order([t])[0]["events"]] == ["WEB-SEND", "RETURN"]
    other = {"trigger": {"kind": "start"}, "events": [{"event": "RETURN", "level": 1}, {"event": "WEB-SEND"}]}
    assert [e["event"] for e in runner.http_order([other])[0]["events"]] == ["RETURN", "WEB-SEND"]


def test_web_events_have_the_spec_keys_and_resp_names():
    ev = runner._web_send_event(200, None, "text/plain", b"OK", 0, 0)
    assert ev["resp"] == "NORMAL" and "resp2" not in ev and ev["from"].data == b"OK"
    rc = runner._web_receive_event(22, 16, None)
    assert rc["resp"] == "LENGERR" and rc["resp2"] == 16 and rc["data"] is None and rc["length"] is None
    assert "from" in cc.EVENT_KEYS["WEB-SEND"] and "data" in cc.EVENT_KEYS["WEB-RECEIVE"]


def test_a_side_without_http_tasks_is_refused_by_name():
    exp = {"tasks": [{"program": "GTHECHO", "trigger": {"kind": "http", "request": 0}, "events": []}]}
    mk = lambda on: cc.Capabilities("x", frozenset(), {}, http_tasks=on)  # noqa: E731
    assert any("http-triggered tasks" in b for b in cc.blockers(exp, mk(False)))
    assert not any("http-triggered tasks" in b for b in cc.blockers(exp, mk(True)))


def test_plan_carries_the_requests_query_and_headers():
    case = _case("a")
    req = {**_req(0), "query": "a=1&b=2", "headers": {"X-One": "1", "X-Two": "2"}}
    plan, why = runner.http_plan(case, {"requests": [req]})
    assert why is None
    assert plan[0]["request"]["query"] == "a=1&b=2"
    assert plan[0]["request"]["headers"] == [["X-One", "1"], ["X-Two", "2"]]
    bare = runner.http_plan(case, {"requests": [_req(0)]})[0][0]["request"]
    assert (bare["query"], bare["headers"]) == ("", [])


def test_client_events_have_the_spec_keys_and_resp_names():  # #4767 (X35)
    opened = runner._web_client_event("WEB-OPEN", "orders.example", "HTTP", None, None, None, None, None, 0, 0)
    assert opened == {"resp": "NORMAL", "host": "orders.example", "scheme": "HTTP"}
    conv = runner._web_client_event(
        "WEB-CONVERSE", "orders.example", None, "GET", "/gt/item", 404, 12, "no such item", 0, 0
    )
    assert conv["resp"] == "NORMAL" and conv["status"] == 404 and conv["tolength"] == 12
    assert conv["into"].data == b"no such item" and "host" not in conv
    short = runner._web_client_event("WEB-CONVERSE", None, None, "GET", "/p", 200, 0, "", 22, 57)
    assert short["into"] is None and short["resp"] == "LENGERR" and short["resp2"] == 57
    assert runner._web_client_event("WEB-CLOSE", None, None, None, None, None, None, None, 19, 27) == {
        "resp": "NOTOPEN",
        "resp2": 27,
    }


def _origin_case() -> cc.Case:
    case = _case("a")
    case.data["peers"] = {
        "orders": {
            "host": "orders.example",
            "responses": [
                {"status": 200, "mediatype": "text/plain", "body": "item=42"},
                {"status": 404, "mediatype": "text/plain", "body": "gone"},
            ],
        },
        "other": {"host": "other.example", "responses": [{"status": 200, "mediatype": "text/plain", "body": "o"}]},
    }
    ev = [
        {"event": "WEB-OPEN", "host": "orders.example", "scheme": "HTTP", "resp": "NORMAL"},
        {"event": "WEB-CONVERSE", "method": "GET", "path": "/gt/item", "status": 200, "resp": "NORMAL"},
        {"event": "WEB-CONVERSE", "method": "GET", "path": "/gt/item", "query": "k=1", "status": 404, "resp": "NORMAL"},
        {"event": "WEB-CLOSE", "resp": "NORMAL"},
    ]
    case.expected = {"s": {"tasks": [{"events": ev}]}}
    return case


def test_origin_peers_take_each_exchange_from_the_expected_conversation():
    peers = runner.origin_peers(_origin_case(), {"id": "s"})
    assert [(p["scheme"], p["host"], p["port"]) for p in peers] == [("HTTP", "orders.example", 80)]
    assert [(x["method"], x["path"], x["query"], x["status"], x["body"]) for x in peers[0]["exchanges"]] == [
        ("GET", "/gt/item", "", 200, "item=42"),
        ("GET", "/gt/item", "k=1", 404, "gone"),
    ]
    import equivalence_cics as ec

    assert ec.http_peers({}, {"name": "s", "http_peers": peers}) == peers  # the harness accepts what it is given


def test_a_case_with_only_client_peers_states_no_origin_peer():
    case = _case("a")
    case.expected = {"s": {"tasks": []}}
    assert runner.origin_peers(case, {"id": "s"}) is None


def test_both_sides_model_the_client_events():
    for caps in (runner.COBOL_CAPS, runner.JAVA_CAPS):
        assert set(caps.events["WEB-CONVERSE"]) == set(cc.EVENT_KEYS["WEB-CONVERSE"])
        assert set(caps.events["WEB-OPEN"]) == set(cc.EVENT_KEYS["WEB-OPEN"])
        assert set(caps.events["WEB-CLOSE"]) == set(cc.EVENT_KEYS["WEB-CLOSE"])


def test_both_raw_shapes_of_a_client_session_match_the_expected_log(tmp_path):
    """The stub's events.txt lines and CicsTask's raw events (what #4767 made them record) map to one SPEC event list."""
    hx = "orders.example".encode().hex().upper()
    (tmp_path / "events.txt").write_text(
        f"001 WEB-OPEN pgm=P host={hx} scheme=HTTP resp=0 resp2=0\n"
        f"002 WEB-CONVERSE pgm=P host={hx} method=GET path={b'/gt/item'.hex().upper()} query=- media=- body=0 "
        f"resp=0 resp2=0 status=404 tolen=12 into={b'no such item'.hex().upper()}\n"
        "003 WEB-CLOSE pgm=P resp=0 resp2=0\n",
        encoding="latin-1",
    )
    stub = runner._cobol_events(tmp_path, "P")
    java = [
        runner._web_client_event(e["event"], e.get("host"), e.get("scheme"), e.get("method"), e.get("path"),
                                 e.get("status"), e.get("tolength"), e.get("into"), e["resp"], e["resp2"])
        for e in (
            {"event": "WEB-OPEN", "host": "orders.example", "scheme": "HTTP", "resp": 0, "resp2": 0},
            {"event": "WEB-CONVERSE", "host": "orders.example", "method": "GET", "path": "/gt/item", "query": "",
             "status": 404, "tolength": 12, "into": "no such item", "resp": 0, "resp2": 0},
            {"event": "WEB-CLOSE", "resp": 0, "resp2": 0},
        )
    ]  # fmt: skip
    assert [{k: v for k, v in e.items() if k not in ("program", "event")} for e in stub] == java


def _hdr(name: str, value: str) -> dict:
    return runner._web_header_event(name, value, 0, 0)


def test_both_sides_model_the_response_header_event():  # #4767 (X38)
    for caps in (runner.COBOL_CAPS, runner.JAVA_CAPS):
        assert set(caps.events["WEB-WRITE-HTTPHEADER"]) == set(cc.EVENT_KEYS["WEB-WRITE-HTTPHEADER"])
    ev = _hdr("X-One", "1")
    assert ev == {"event": "WEB-WRITE-HTTPHEADER", "name": "X-One", "value": "1", "resp": "NORMAL"}


def test_the_stub_header_line_maps_to_the_spec_event(tmp_path):
    (tmp_path / "events.txt").write_text(
        f"001 WEB-HEADER pgm=P name={b'X-One'.hex().upper()} value={b'reply-200'.hex().upper()} resp=0 resp2=0\n",
        encoding="latin-1",
    )
    (stub,) = runner._cobol_events(tmp_path, "P")
    assert {k: v for k, v in stub.items() if k != "program"} == _hdr("X-One", "reply-200")


def test_peer_check_compares_the_response_headers():  # #4767 (X38)
    case = _case("A", "B", "C")
    case.data["peers"]["client-a"]["responses"][0]["headers"] = {"X-One": "1", "X-Two": "2"}
    case.data["peers"]["client-a"]["responses"][1]["headers"] = {"X-One": "1"}
    sc = {"requests": [_req(0), _req(5), _req(10)]}
    both = [_hdr("X-Two", "2"), _hdr("X-One", "1")]  # the order the program wrote them in is not compared
    ok = [_task(0, "A", extra=both), _task(1, "B", extra=both[1:]), _task(2, "C")]
    assert runner.http_peer_log(case, sc, ok) == {}
    missing = runner.http_peer_log(case, sc, [_task(0, "A", extra=both[1:])])
    assert "response headers [('X-One', '1')]" in missing["http_peer"]
    wrong = runner.http_peer_log(case, sc, [_task(0, "A", extra=[_hdr("X-One", "9"), both[0]])])
    assert "response headers" in wrong["http_peer"]
    twice = runner.http_peer_log(case, sc, [_task(0, "A", extra=[*both, _hdr("X-One", "1")])])
    assert "response headers" in twice["http_peer"]  # a header written twice is two headers
    unstated = runner.http_peer_log(case, sc, [_task(0, "A", extra=both), _task(1, "B", extra=both)])
    assert "response headers" in unstated["http_peer"]  # a peer that states none for a response expects none
    assert (
        runner.http_peer_log(case, sc, [_task(0, "A", extra=both), _task(1, "B", extra=both[1:]), _task(2, "C")]) == {}
    )
