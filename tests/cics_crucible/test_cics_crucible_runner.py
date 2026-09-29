"""#3989: the CICS crucible runner, without GnuCOBOL, Docker or Maven.

Pinned here: reading a case (case.json, the CSD, the expected logs, the format guard), laying out
its areas (COPY members inlined), the exact comparison of SPEC section 6 (text padding, hex, numbers,
areas, event order, unmodelled features), the stub's event log as SPEC events, the Java test's output
as an actual log, the baseline ratchet, the report, and the pin's one-line form the workflow reads.
The fixture case (fixture/cases/...) is in the crucible's format; the end-to-end test at the bottom
runs it through every side and needs EQUIVALENCE_E2E=1 (Docker GnuCOBOL + a JDK 17 and Maven).
"""

import copy
import json
import os
import re
import shutil
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
sys.path.insert(0, str(TESTS))
import _cics_crucible_pin as pin  # noqa: E402
import cics_crucible as runner  # noqa: E402
import cics_crucible_compare as cc  # noqa: E402
import equivalence_cics as ec  # noqa: E402

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixture"
FIXTURE = FIXTURE_ROOT / "cases" / "pseudo-conversational" / "fx-text-chain"
E = cc.EBCDIC


def _case() -> cc.Case:
    return cc.load_case(FIXTURE)


def _raw(text: str) -> cc.RawArea:
    """An area as the ASCII stub runtime holds it."""
    return cc.RawArea(text.encode("latin-1"), "latin-1")


def _actual_from_expected(exp: dict) -> dict:
    """The actual log a perfect stub would record for the fixture (areas as runtime bytes)."""
    act = copy.deepcopy(exp)
    counts = iter(["001", "002", "002", "003"])
    for t in act["tasks"]:
        if t["commarea"]:
            t["commarea"] = _raw(next(counts) if t["seq"] > 1 else "")
    act["tasks"][1]["commarea"] = _raw("001FIRST   ")
    act["tasks"][2]["commarea"] = _raw("002FIRST   ")
    evs = [e for t in act["tasks"] for e in t["events"]]
    evs[1]["commarea"] = _raw("001FIRST   ")
    evs[3]["commarea"] = _raw("002FIRST   ")
    evs[5]["commarea"] = _raw("003FIRST   ")
    for e in evs:
        if e["event"] == "SEND-TEXT":
            e["text"] = e["text"].ljust(20).encode(E)
    return act


def _ctx() -> cc.Context:
    return cc.Context(layouts={"STATE": [
        {"name": "WS-COUNT", "offset": 0, "bytes": 3, "pic": "9(3)", "usage": None},
        {"name": "WS-NAME", "offset": 3, "bytes": 8, "pic": "X(8)", "usage": None}]},
        map_fields={"M1": {"NAME": 8, "MSG": 5}})  # fmt: skip


ALL = cc.Capabilities("all", frozenset(cc.TASK_KEYS) | {"end"},
                      {k: frozenset(v) | ({"fields.data", "fields.attr", "fields.omission"} if k == "SEND-MAP" else set())
                       for k, v in cc.EVENT_KEYS.items()}, ts_queues=True, start_tasks=True)  # fmt: skip


# ---- reading a case ----------------------------------------------------------------------------
def test_the_csd_names_programs_transactions_and_mapsets():
    csd = cc.parse_csd("* a comment DEFINE PROGRAM(NOPE)\nDEFINE PROGRAM(A) GROUP(G)\nDEFINE TRANSACTION(T1)\n"
                       "       GROUP(G) PROGRAM(A)\nDEFINE MAPSET(MS) GROUP(G)\ndefine transaction(t2) program(b)\n")  # fmt: skip
    assert csd == {"programs": {"A"}, "transactions": {"T1": "A", "T2": "B"}, "mapsets": {"MS"}}


def test_a_case_is_read_with_its_expected_logs_and_csd():
    case = _case()
    assert (case.id, case.trap, case.programs) == ("fx-text-chain", "pseudo-conversational", ["FXCHAIN", "FXLAST"])
    assert case.csd["transactions"] == {"FX01": "FXCHAIN"}
    assert list(case.expected) == ["three-visits"] and len(case.expected["three-visits"]["tasks"]) == 3
    assert cc.discover(FIXTURE_ROOT) == [FIXTURE, FIXTURE_ROOT / "cases" / "condition-handling" / "fx-ts-queue"]
    assert cc.discover(FIXTURE_ROOT, {"fx-text-chain"}) == [FIXTURE] and cc.discover(FIXTURE_ROOT, {"nope"}) == []


def test_a_format_this_runner_does_not_read_is_refused(tmp_path):
    shutil.copytree(FIXTURE, tmp_path / "c")
    data = json.loads((tmp_path / "c/case.json").read_text())
    data["format"] = "cics-crucible/case/2"
    (tmp_path / "c/case.json").write_text(json.dumps(data))
    with pytest.raises(cc.CaseError, match="case/2"):
        cc.load_case(tmp_path / "c")
    shutil.copytree(FIXTURE, tmp_path / "d")
    (tmp_path / "d/expected/three-visits.json").unlink()
    with pytest.raises(cc.CaseError, match="no expected/three-visits.json"):
        cc.load_case(tmp_path / "d")


def test_layouts_inline_copy_members_so_later_fields_keep_their_offsets(tmp_path):
    """The answer-key reader lays a record out as written: a COPY left in place would drop the
    copybook's fields and move every later field to the wrong offset (CALINK's WS-BLOCK)."""
    shutil.copytree(FIXTURE, tmp_path / "c")
    (tmp_path / "c/copy").mkdir()
    (tmp_path / "c/copy/HDR.cpy").write_text("           10  H-EYE             PIC X(4).\n"
                                             "           10  H-LEN             PIC S9(4) COMP.\n")  # fmt: skip
    src = (
        (tmp_path / "c/src/FXCHAIN.cbl")
        .read_text()
        .replace("       01  WS-STATE.\n", "       01  WS-STATE.\n           05  WS-HEAD.\n               COPY HDR.\n")
    )
    (tmp_path / "c/src/FXCHAIN.cbl").write_text(src)
    data = json.loads((tmp_path / "c/case.json").read_text())
    data["sources"]["copy"] = ["copy"]
    (tmp_path / "c/case.json").write_text(json.dumps(data))
    ctx = runner.case_context(cc.load_case(tmp_path / "c"), tmp_path / "w")
    assert [(f["name"], f["offset"], f["bytes"]) for f in ctx.layouts["STATE"]] == [
        ("H-EYE", 0, 4), ("H-LEN", 4, 2), ("WS-COUNT", 6, 3), ("WS-NAME", 9, 8)]  # fmt: skip


def test_the_fixture_context_has_its_layout(tmp_path):
    ctx = runner.case_context(_case(), tmp_path)
    assert [(f["name"], f["offset"], f["bytes"]) for f in ctx.layouts["STATE"]] == [
        ("WS-COUNT", 0, 3),
        ("WS-NAME", 3, 8),
    ]


def test_engine_facts_come_from_the_programs_csd_and_the_logs():
    labels = [label for label, _ in runner.fact_checks(_case())]
    assert labels == ["program FXCHAIN", "program FXLAST", "transaction FX01 -> FXCHAIN",
                      "FXCHAIN: RETURN TRANSID(FX01)", "FXCHAIN: XCTL PROGRAM(FXLAST)"]  # fmt: skip


# ---- the comparison ---------------------------------------------------------------------------
def test_a_perfect_log_passes():
    exp = _case().expected["three-visits"]
    assert cc.compare(exp, _actual_from_expected(exp), ALL, _ctx()).status == "pass"


def test_text_is_padded_to_its_length_but_embedded_blanks_count():
    exp = _case().expected["three-visits"]
    act = _actual_from_expected(exp)
    act["tasks"][0]["events"][0]["text"] = "VISIT 001"  # a Java string: padded like the log's text
    assert cc.compare(exp, act, ALL, _ctx()).status == "pass"
    act["tasks"][0]["events"][0]["text"] = "VISIT  001".encode(E).ljust(20, b"\x40")
    v = cc.compare(exp, act, ALL, _ctx())
    assert (
        v.status == "fail"
        and v.reason.startswith("task 1 (FX01) event 1: text 'VISIT 001")
        and "VISIT  001" in v.reason
    )


def test_the_first_divergence_is_reported_with_its_place():
    exp = _case().expected["three-visits"]
    act = _actual_from_expected(exp)
    act["tasks"][1]["events"][1]["commarea"] = _raw("007FIRST   ")
    v = cc.compare(exp, act, ALL, _ctx())
    assert (v.status, v.kind) == ("fail", "commarea field differs")
    assert v.reason.startswith("task 2 (FX01) event 2: commarea.WS-COUNT 2 expected, got 7")


def test_missing_extra_and_wrong_events_and_tasks_fail():
    exp = _case().expected["three-visits"]
    act = _actual_from_expected(exp)
    act["tasks"][2]["events"] = act["tasks"][2]["events"][:2]
    assert cc.compare(exp, act, ALL, _ctx()).reason == \
        "task 3 (FX01) event 3: SEND-TEXT expected, the side recorded no further event"  # fmt: skip
    act = _actual_from_expected(exp)
    act["tasks"][0]["events"].append({"event": "DRIVER-ERROR", "program": "FXCHAIN", "message": "boom"})
    assert (
        cc.compare(exp, act, ALL, _ctx()).reason
        == "task 1 (FX01) event 3: no further event expected, got DRIVER-ERROR (boom)"
    )
    act = _actual_from_expected(exp)
    act["tasks"][0]["events"][1]["event"] = "XCTL"
    assert "RETURN expected, got XCTL" in cc.compare(exp, act, ALL, _ctx()).reason
    act = _actual_from_expected(exp)
    act["tasks"], act["stopped"] = act["tasks"][:1], "step 1: no pending RETURN TRANSID"
    assert cc.compare(exp, act, ALL, _ctx()).reason == \
        "task 2 (FX01): expected a task running FXCHAIN, the side ran none (step 1: no pending RETURN TRANSID)"  # fmt: skip
    act = _actual_from_expected(exp)
    act["tasks"].append({"transid": "FX01"})
    assert cc.compare(exp, act, ALL, _ctx()).kind == "extra task"


def test_task_keys_are_compared():
    exp = _case().expected["three-visits"]
    act = _actual_from_expected(exp)
    act["tasks"][2]["eibaid"] = "ENTER"
    assert cc.compare(exp, act, ALL, _ctx()).reason == "task 3 (FX01): eibaid 'PF3' expected, got 'ENTER'"
    act = _actual_from_expected(exp)
    act["tasks"][1]["eibcalen"] = 10
    assert cc.compare(exp, act, ALL, _ctx()).reason == "task 2 (FX01): eibcalen 11 expected, got 10"


def test_an_event_the_side_cannot_record_is_unsupported_unless_something_diverged_first():
    exp = _case().expected["three-visits"]
    no_xctl = cc.Capabilities("stub", ALL.task_keys, {k: v for k, v in ALL.events.items() if k != "XCTL"})
    act = _actual_from_expected(exp)
    v = cc.compare(exp, act, no_xctl, _ctx())
    assert (v.status, v.reason, v.features) == ("unsupported", "stub: XCTL event", ["stub: XCTL event"])
    act["tasks"][0]["events"][0]["text"] = b"\x40" * 20
    v = cc.compare(exp, act, no_xctl, _ctx())
    assert v.status == "fail" and v.features == ["stub: XCTL event"]  # the blockers still counted


def test_an_unmodelled_key_decides_only_after_the_modelled_keys_of_its_event_agree():
    exp = _case().expected["three-visits"]
    text_only = cc.Capabilities("CicsTask", ALL.task_keys, {**ALL.events, "SEND-TEXT": frozenset({"text"})})
    act = _actual_from_expected(exp)
    assert cc.compare(exp, act, text_only, _ctx()).reason == "CicsTask: SEND-TEXT length"
    act["tasks"][0]["events"][0]["text"] = "NOPE"
    assert cc.compare(exp, act, text_only, _ctx()).status == "fail"
    act = _actual_from_expected(exp)
    act["tasks"][1]["eibcalen"] = cc.Unmodelled("task eibcalen (a DTO has no EIBCALEN)")
    assert cc.compare(exp, act, ALL, _ctx()).reason == "all: task eibcalen (a DTO has no EIBCALEN)"


def test_options_compare_as_sets_and_an_unexpected_optional_key_fails():
    exp = {"tasks": [{"seq": 1, "transid": "T", "program": "P", "termid": "T001", "at": "x", "trigger": {"kind": "terminal", "step": 0}, "eibaid": None,
                      "eibcalen": 0, "commarea": None, "end": "normal",
                      "events": [{"event": "SEND-MAP", "program": "P", "map": "M1", "mapset": "S", "options": ["FREEKB", "ERASE"],
                                  "fields": {}}]}]}  # fmt: skip
    act = copy.deepcopy(exp)
    act["tasks"][0]["events"][0]["options"] = ["ERASE", "FREEKB"]
    assert cc.compare(exp, act, ALL, _ctx()).status == "pass"
    act["tasks"][0]["events"][0]["cursor"] = "NAME"
    assert cc.compare(exp, act, ALL, _ctx()).reason == "task 1 (T) event 1: cursor 'NAME' not expected"


def test_send_map_fields_compare_data_padded_to_the_field_and_attributes_exactly():
    fields = {"NAME": {"attr": "C1", "attr_from": "program", "data": "ADA", "data_from": "program"},
              "MSG": {"attr": None, "attr_from": "none", "data": {"hex": "00C1"}, "data_from": "program"}}  # fmt: skip
    ev = {"event": "SEND-MAP", "program": "P", "map": "M1", "mapset": "S", "options": ["DATAONLY"], "fields": fields}
    exp = {"tasks": [{"seq": 1, "transid": "T", "program": "P", "termid": "T001", "at": "x", "trigger": {"kind": "terminal", "step": 0}, "eibaid": None,
                      "eibcalen": 0, "commarea": None, "end": "normal", "events": [ev]}]}  # fmt: skip
    act = copy.deepcopy(exp)
    act["tasks"][0]["events"][0]["fields"] = {"NAME": {"attr": "C1", "data": "ADA     ".encode(E)},
                                              "MSG": {"attr": None, "data": b"\x00\xc1"}}  # fmt: skip
    caps = cc.Capabilities("x", ALL.task_keys, {**ALL.events, "SEND-MAP": frozenset({"map", "mapset", "options", "fields",
                                                                                    "fields.data", "fields.attr"})})  # fmt: skip
    v = cc.compare(exp, act, caps, _ctx())
    assert (v.status, v.reason) == ("unsupported", "x: SEND-MAP attribute bytes")  # attr_from is not recorded
    assert v.features == ["x: SEND-MAP attribute bytes", "x: SEND-MAP data origin (program / map / none)",
                          "x: SEND-MAP DATAONLY field omission"]  # fmt: skip
    act["tasks"][0]["events"][0]["fields"]["NAME"]["attr"] = "C9"
    assert "field NAME: attr 'C1' expected, got 'C9'" in cc.compare(exp, act, caps, _ctx()).reason
    act["tasks"][0]["events"][0]["fields"]["NAME"]["attr"] = "C1"
    act["tasks"][0]["events"][0]["fields"]["MSG"]["data"] = b"\x40\xc1"
    assert "field MSG: data X'00C1' expected, got X'40C1'" in cc.compare(exp, act, caps, _ctx()).reason
    del act["tasks"][0]["events"][0]["fields"]["MSG"]
    assert cc.compare(exp, act, caps, _ctx()).reason == "task 1 (T) event 1: field MSG expected, not sent"


def test_areas_compare_by_layout_hex_and_number():
    w = cc._Walk(ALL, cc.Context(layouts={"L": [
        {"name": "A", "offset": 0, "bytes": 3, "pic": "S9(3)V99", "usage": "COMP-3"},
        {"name": "B", "offset": 3, "bytes": 2, "pic": "X(2)", "usage": None},
        {"name": "C", "offset": 5, "bytes": 2, "pic": "S9(4)", "usage": "COMP"}]}))  # fmt: skip
    exp = {"length": 7, "layout": "L", "fields": {"A": "-12.50", "B": {"hex": "00C1"}, "C": "258"}}
    good = cc.RawArea(bytes.fromhex("01250D") + b"\x00\xc1" + (258).to_bytes(2, "big"), E)
    w.area("here", "commarea", exp, good)  # no exception: equal
    latin = cc.RawArea(bytes.fromhex("01250D") + b"\x00A" + (258).to_bytes(2, "big"), "latin-1")
    w.area("here", "commarea", exp, latin)  # the runtime's DISPLAY bytes transcoded, COMP / COMP-3 kept
    with pytest.raises(cc._Decided, match=r"commarea.A -12.50 expected, got -12.51"):
        w.area("here", "commarea", exp, cc.RawArea(bytes.fromhex("01251D") + good.data[3:], E))
    with pytest.raises(cc._Decided, match="commarea length 7 expected, got 6"):
        w.area("here", "commarea", exp, cc.RawArea(good.data[:6], E))
    with pytest.raises(cc._Decided, match="commarea none expected, got an area"):
        w.area("here", "commarea", None, good)
    w.area("here", "data", {"length": 4, "text": "AB"}, cc.RawArea("AB  ".encode(E), E))
    with pytest.raises(cc._Decided, match="data byte 1"):
        w.area("here", "data", {"length": 4, "hex": "C1C2C3C4"}, cc.RawArea("AXCD".encode(E), E))


def test_a_dto_area_holds_the_whole_record_and_no_length():
    lay = _ctx().layouts
    w = cc._Walk(ALL, cc.Context(layouts=lay))
    full = {"length": 11, "layout": "STATE", "fields": {"WS-COUNT": "3", "WS-NAME": "FIRST"}}
    w.area("here", "commarea", full, cc.FieldArea({"WS-COUNT": 3, "WS-NAME": "FIRST"}))
    assert w.pending is None
    with pytest.raises(cc._Decided, match="WS-NAME 'FIRST' expected, got 'LAST'"):
        w.area("here", "commarea", full, cc.FieldArea({"WS-COUNT": 3, "WS-NAME": "LAST"}))
    short = {"length": 3, "layout": "STATE", "fields": {"WS-COUNT": "3"}}
    w.area("here", "commarea", short, cc.FieldArea({"WS-COUNT": Decimal(3), "WS-NAME": "FIRST"}))
    assert w.pending == "all: commarea shorter than its record (a DTO has no EIBCALEN)"


def test_blockers_name_every_missing_feature_once():
    exp = {"tasks": [
        {"seq": 1, "trigger": {"kind": "terminal", "step": 0}, "events": [
            {"event": "READQ-TS", "program": "P", "queue": "Q", "item": 1, "resp": "NORMAL", "data": None},
            {"event": "START", "program": "P", "transid": "T", "termid": None, "from": None, "protect": False,
             "resp": "NORMAL", "expires": "x"}]},
        {"seq": 2, "trigger": {"kind": "start", "task": 1, "event": 1}, "events": [
            {"event": "READQ-TS", "program": "P", "queue": "Q", "item": 1, "resp": "NORMAL", "data": None}]}],
        "final": {"ts_queues": {"Q": ["A"]}}}  # fmt: skip
    caps = cc.Capabilities("CicsTask", runner.JAVA_CAPS.task_keys, {"START": frozenset()})
    got = cc.blockers(exp, caps, {"initial": {"ts_queues": {"Q": ["A"]}}})
    assert got == ["CicsTask: TS queue seeding", "CicsTask: READQ-TS event", "CicsTask: START transid",
                   "CicsTask: START termid", "CicsTask: START from", "CicsTask: START protect", "CicsTask: START resp",
                   "CicsTask: START expires", "scheduler: START-triggered tasks (CicsTask)",
                   "CicsTask: TS queue final state"]  # fmt: skip
    assert cc.blockers(exp, runner.JAVA_CAPS) == [
        "CicsTask: START event",
        "scheduler: START-triggered tasks (CicsTask)",
    ]


def test_final_ts_queues_are_compared_exactly():
    exp = _case().expected["three-visits"] | {"final": {"ts_queues": {"Q": ["AB", {"hex": "00"}]}}}
    act = _actual_from_expected(exp) | {"final": {"ts_queues": {"Q": ["AB".encode(E), b"\x00"]}}}
    assert cc.compare(exp, act, ALL, _ctx()).status == "pass"
    act["final"]["ts_queues"]["Q"][0] = "AB ".encode(E)  # a TS item has no length to pad to
    assert cc.compare(exp, act, ALL, _ctx()).kind == "item differs"
    assert cc.compare(exp, act, runner.COBOL_CAPS, _ctx()).status in ("unsupported", "fail")


# ---- the sides' logs --------------------------------------------------------------------------
def test_the_stub_log_becomes_spec_events(tmp_path):
    (tmp_path / "events.txt").write_text(
        "001 HANDLE-ABEND LABEL X\n002 SEND-TEXT len=5 opts=TEXT ERASE FREEKB\n003 SEND-MAP map=M mapset=S len=9 opts=\n"
        "004 RECEIVE-MAP map=M mapset=S resp=36\n005 XCTL program=NEXT len=3\n006 ABEND unhandled-resp=44\n"
        "007 ABEND unhandled-resp=4\n008 ABEND abcode=XX01\n009 RETURN transid=T1 len=2\n010 END\n",
        encoding="latin-1")  # fmt: skip
    (tmp_path / "002.bin").write_bytes(b"HI  !")
    (tmp_path / "005.bin").write_bytes(b"ABC")
    (tmp_path / "009.bin").write_bytes(b"\x00Z")
    evs = runner._cobol_events(tmp_path, "PROG")
    assert [e["event"] for e in evs] == ["SEND-TEXT", "SEND-MAP", "RECEIVE-MAP", "XCTL", "ABEND", "ABEND", "ABEND",
                                         "RETURN", "RETURN"]  # fmt: skip
    assert evs[0] == {"event": "SEND-TEXT", "program": "PROG", "text": "HI  !".encode(E), "length": 5,
                      "options": ["ERASE", "FREEKB"]}  # fmt: skip
    assert evs[2]["resp"] == "MAPFAIL" and evs[3]["target"] == "NEXT" and evs[3]["commarea"].data == b"ABC"
    assert (evs[4]["abcode"], evs[4]["condition"], evs[4]["cause"]) == ("AEYH", "QIDERR", "condition")
    assert isinstance(evs[5]["abcode"], cc.Unmodelled)  # EOF: no documented AEIx code in SPEC 6.2's table
    assert (evs[6]["abcode"], evs[6]["cause"]) == ("XX01", "command")
    assert (evs[7]["transid"], evs[7]["commarea"].data) == ("T1", b"\x00Z")
    assert (evs[8]["transid"], evs[8]["commarea"]) == (None, None)  # a GOBACK is a RETURN


def test_a_terminal_receive_is_logged_with_its_length_and_the_data_it_moved(tmp_path):
    """#4005: `len` is LENGTH after the command (the full length on LENGERR), the blob what went INTO; a
    second RECEIVE in one task would wait for the operator, which no scenario step can express."""
    (tmp_path / "events.txt").write_text("001 RECEIVE resp=22 len=9 copied=4\n002 RECEIVE-WAIT\n", encoding="latin-1")
    (tmp_path / "001.bin").write_bytes(b"CA02")
    evs = runner._cobol_events(tmp_path, "P")
    assert (evs[0]["resp"], evs[0]["length"], evs[0]["data"].data) == ("LENGERR", 9, b"CA02")
    assert evs[1]["event"] == "DRIVER-ERROR" and "second terminal RECEIVE" in evs[1]["message"]
    exp = {"event": "RECEIVE", "program": "P", "resp": "LENGERR", "length": 9, "data": {"length": 4, "text": "CA02"}}
    w = cc._Walk(runner.COBOL_CAPS, _ctx())
    w.event("e", exp, evs[0])
    with pytest.raises(cc._Decided):
        w.event("e", dict(exp, data={"length": 4, "text": "CA03"}), evs[0])


def test_ts_events_carry_length_and_data_only_where_the_command_sets_them(tmp_path):
    """#4002: READQ TS sets LENGTH (and moves data) on NORMAL and LENGERR only; the queue name travels as hex."""
    (tmp_path / "events.txt").write_text(
        "001 READQ-TS queue=4851 item=2 resp=22 len=5 copied=3\n002 READQ-TS queue=4851 item=NEXT resp=26 len=-1 "
        "copied=0\n003 WRITEQ-TS queue=4851 item=3 resp=0 len=2\n004 WRITEQ-TS queue=4851 item=0 resp=22 len=0\n",
        encoding="latin-1")  # fmt: skip
    (tmp_path / "001.bin").write_bytes(b"BBB")
    (tmp_path / "003.bin").write_bytes(b"ZZ")
    evs = runner._cobol_events(tmp_path, "P")
    assert (evs[0]["queue"], evs[0]["item"], evs[0]["resp"], evs[0]["length"], evs[0]["data"].data) == (
        "HQ", 2, "LENGERR", 5, b"BBB")  # fmt: skip
    assert (evs[1]["item"], evs[1]["resp"], evs[1]["length"], evs[1]["data"]) == ("NEXT", "ITEMERR", None, None)
    assert (evs[2]["item"], evs[2]["data"].data, evs[3]["resp"], evs[3]["item"]) == (3, b"ZZ", "LENGERR", None)
    exp = {"event": "READQ-TS", "program": "P", "queue": "HQ", "item": "NEXT", "resp": "ITEMERR", "data": None}
    cc._Walk(runner.COBOL_CAPS, _ctx()).event("e", exp, evs[1])


def test_ts_queues_are_seeded_in_the_stubs_page_and_read_back_as_ebcdic(tmp_path):
    runner.seed_ts(tmp_path / "ts", {"HCQ1": ["AB", {"hex": "C1C2"}], "Q 2": []})
    assert (tmp_path / "ts" / "48435131" / "000001.bin").read_bytes() == b"AB"
    assert (tmp_path / "ts" / "48435131" / "000002.bin").read_bytes() == b"AB"  # X'C1C2' is EBCDIC AB
    assert runner.read_ts(tmp_path / "ts") == {"HCQ1": [b"\xc1\xc2", b"\xc1\xc2"], "Q 2": []}
    assert runner.read_ts(tmp_path / "nothing") == {}


def test_the_java_output_becomes_an_actual_log(tmp_path):
    src = tmp_path / "src"
    dto = src / "com/gitgalaxy/modernized/dto/contract"
    dto.mkdir(parents=True)
    (dto / "St.java").write_text("public class St {\n    // WS-COUNT: PIC 9(3), offset 0\n    private Integer wsCount;\n"
                                 "    // WS-NAME: PIC X(8), offset 3\n    private String wsName;\n}\n")  # fmt: skip
    ca = {"class": "com.gitgalaxy.modernized.dto.contract.St", "value": {"wsCount": 2, "wsName": "FIRST"}}
    raw = {"_scenario": "three-visits", "stopped": None, "ts_queues": {"Q": ["c1c2"]}, "tasks": [
        {"step": 1, "transid": "FX01", "program": "FXCHAIN", "commarea": ca, "end": "normal", "events": [
            {"event": "SEND-MAP", "program": "FXCHAIN", "map": "M1", "screen": {"NAME": "ADA", "MSG": None}},
            {"event": "SEND-TEXT", "program": "FXCHAIN", "text": "VISIT 002"},
            {"event": "RECEIVE", "program": "FXCHAIN", "resp": "NORMAL", "length": 4, "data": "FX01"},
            {"event": "READQ-TS", "program": "FXCHAIN", "queue": "Q", "item": 1, "resp": "NORMAL", "length": 1,
             "data": "wQ=="},
            {"event": "XCTL", "program": "FXCHAIN", "target": "FXLAST", "commarea": ca},
            {"event": "DRIVER-ERROR", "program": "FXLAST", "message": "no generated service for program FXLAST"}]}]}  # fmt: skip
    act = runner.java_actual(_case(), raw, src)
    assert act["final"] == {"ts_queues": {"Q": [b"\xc1\xc2"]}}  # #4002: the queues the scenario left, EBCDIC
    t = act["tasks"][0]
    assert (t["at"], t["eibaid"], t["trigger"], t["termid"]) == ("2026-03-02T10:00:10", "ENTER",
                                                                 {"kind": "terminal", "step": 1}, "T001")  # fmt: skip
    assert isinstance(t["eibcalen"], cc.Unmodelled) and t["commarea"].fields == {"WS-COUNT": 2, "WS-NAME": "FIRST"}
    assert t["events"][0]["fields"] == {"NAME": {"data": "ADA"}, "MSG": {"data": None}}
    assert (t["events"][2]["resp"], t["events"][2]["length"], t["events"][2]["data"].data) == ("NORMAL", 4, b"FX01")
    assert (t["events"][3]["queue"], t["events"][3]["length"], t["events"][3]["data"].data) == ("Q", 1, b"\xc1")
    assert t["events"][4]["target"] == "FXLAST" and t["events"][5]["message"].startswith("no generated service")


# ---- the translator names what it refuses -----------------------------------------------------
def test_the_translator_names_each_refused_command_as_a_feature():
    src = (FIXTURE / "src/FXCHAIN.cbl").read_text().replace(
        "           STRING 'VISIT '",
        "           EXEC CICS LINK PROGRAM('X') END-EXEC\n           EXEC CICS READQ TS QUEUE('Q') INTO(WS-LINE)\n"
        "           END-EXEC\n           EXEC CICS RECEIVE INTO(WS-LINE) END-EXEC\n"
        "           IF EIBRESP = DFHRESP(NOSUCH) CONTINUE END-IF\n           STRING 'VISIT '")  # fmt: skip
    with pytest.raises(ec.Unsupported) as e:
        ec.translate(src)
    assert e.value.features == ["LINK", "DFHRESP(NOSUCH)"]  # #4005 / #4002: RECEIVE and READQ TS translate
    assert ec.translate((FIXTURE / "src/FXCHAIN.cbl").read_text())[1] is True


# ---- the ratchet and the report -----------------------------------------------------------------
def _results(**statuses):
    cells = {}
    for cid, status in statuses.items():
        case, scenario, side = cid.split("__")
        cells[cc.cell_id(case, scenario, side)] = {"case": case, "trap": "t", "scenario": scenario, "side": side,
                                                   "status": status, "reason": f"{status} reason",
                                                   "features": ["stub: X event"] if status == "unsupported" else [],
                                                   "kind": f"{status} kind"}  # fmt: skip
    return {"crucible_ref": "abc", "cells": cells}


def test_the_baseline_lists_every_cell_that_does_not_pass(tmp_path):
    res = _results(c__s__java="fail", c__t__java="pass", c__s__cobol_stub="unsupported")
    base = runner.baseline_of(res)
    assert base["format"] == runner.BASELINE_FORMAT and base["crucible_ref"] == "abc"
    assert base["cells"] == {"c/s/cobol_stub": {"status": "unsupported", "reason": "unsupported reason"},
                             "c/s/java": {"status": "fail", "reason": "fail reason"}}  # fmt: skip
    runner.write_baseline(res, tmp_path / "b.json")
    assert runner.read_baseline(tmp_path / "b.json") == base


def test_the_ratchet_fails_on_new_failures_and_on_ledgered_cells_that_pass():
    base = runner.baseline_of(_results(c__s__java="fail", c__u__java="unsupported", c__gone__java="fail"))
    errors, notes = runner.ratchet(
        _results(c__s__java="fail", c__u__java="fail", c__new__java="unsupported"), base, False
    )
    assert errors == ["NEW UNSUPPORTED: c/new/java: unsupported reason"]
    assert notes == ["c/u/java: was unsupported, now fail: fail reason"]
    errors, _ = runner.ratchet(_results(c__s__java="pass", c__u__java="unsupported"), base, True)
    assert errors == ["NOW PASSES, still ledgered: c/s/java -- remove it (--update-baseline)",
                      "STALE: c/gone/java is ledgered but was not measured -- re-baseline (--update-baseline)"]  # fmt: skip
    assert runner.ratchet(_results(c__s__java="fail", c__u__java="unsupported", c__gone__java="fail"), base, True) == (
        [],
        [],
    )


def test_the_report_counts_sides_features_and_reasons():
    res = _results(a__s__java="fail", a__t__java="unsupported", a__s__cobol_stub="unsupported", **{
        "a__*__engine-facts": "pass", "a__*__forge-compile": "fail"})  # fmt: skip
    for c in res["cells"].values():
        c["side"] = c["side"].replace("cobol_stub", "cobol-stub")
    md = runner.report_md(res)
    assert "| java | 0 | 1 | 1 | 2 |" in md and "| cobol-stub | 0 | 0 | 1 | 1 |" in md
    assert "| t | `a` | pass | **fail** | 0 / 1 | 0 / 2 |" in md
    assert "| stub: X event | 1 | X event |" in md and "| java | fail kind | 1 |" in md
    assert "### java (1 unsupported)" in md and "| 1 | X event | 1 | 1 | 1 |" in md


def test_harness_work_is_ordered_by_the_cells_it_unlocks():
    def cell(status, *features):
        return {"status": status, "features": list(features)}

    cells = [cell("unsupported", "translator: READQ TS", "stub: READQ-TS event", "stub: TS queue seeding"),
             cell("unsupported", "translator: LINK", "translator: WRITEQ TS"),
             cell("unsupported", "translator: LINK", "translator: WRITEQ TS"),
             cell("unsupported", "stub: SEND-MAP cursor"), cell("fail", "stub: SEND-MAP cursor"), cell("pass")]  # fmt: skip
    ts, link, bms = (
        runner.feature_group(f) for f in ("stub: TS queue seeding", "stub: LINK event", "stub: SEND-MAP x")
    )
    assert runner.unlock_order(cells) == [(ts, 3, 1, 1), (link, 2, 0, 3), (bms, 2, 1, 4)]


# ---- the pin -----------------------------------------------------------------------------------
def test_the_pin_is_one_line_in_the_form_the_workflow_reads(tmp_path):
    text = (TESTS / "_cics_crucible_pin.py").read_text()
    found = re.findall(r'^PINNED_REF = "(.*)"$', text, re.M)
    assert found == [pin.PINNED_REF] and re.fullmatch(r"[0-9a-f]{40}|v\d+(\.\d+)*", pin.PINNED_REF)
    workflow = (TESTS.parent / ".github/workflows/cics-crucible.yml").read_text()
    assert 's/^PINNED_REF = "\\(.*\\)"/\\1/p' in workflow and "tests/_cics_crucible_pin.py" in workflow
    assert pin.pin_mismatch(tmp_path) is None  # not a git checkout: nothing to compare


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_an_off_pin_checkout_is_refused(tmp_path, monkeypatch):
    monkeypatch.delenv(pin.ALLOW_UNPINNED_ENV, raising=False)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)  # noqa: S603, S607
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",  # noqa: S603, S607
                    "--allow-empty", "-m", "x"], check=True)  # fmt: skip
    assert "Fix: git -C" in pin.pin_mismatch(tmp_path)
    monkeypatch.setenv(pin.ALLOW_UNPINNED_ENV, "1")
    assert pin.pin_mismatch(tmp_path) is None


# ---- end to end ---------------------------------------------------------------------------------
@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL) and a JDK + Maven")
def test_the_fixture_runs_through_every_side(tmp_path):
    """The COBOL passes on the stub (terminal steps chained by RETURN TRANSID COMMAREA, an XCTL run in
    the same task, areas compared field by field); the generated Java compiles and runs, and fails at
    its first event because the generated runTask is the stub that records nothing."""
    res = runner.measure(FIXTURE_ROOT, None, set(cc.SIDES), tmp_path, offline=os.environ.get("MAVEN_OFFLINE") == "1")
    got = {cid: c["status"] for cid, c in res["cells"].items()}
    assert got == {"fx-text-chain/*/engine-facts": "pass", "fx-text-chain/*/forge-compile": "pass",
                   "fx-text-chain/three-visits/cobol-stub": "pass", "fx-text-chain/three-visits/java": "fail",
                   # #4005 / #4002: terminal RECEIVE, TS seeding, READQ LENGERR / QIDERR, the final queue
                   "fx-ts-queue/*/engine-facts": "pass", "fx-ts-queue/*/forge-compile": "pass",
                   "fx-ts-queue/seeded/cobol-stub": "pass", "fx-ts-queue/seeded/java": "fail"}  # fmt: skip
    java = res["cells"]["fx-text-chain/three-visits/java"]
    assert java["reason"] == "task 1 (FX01) event 1: SEND-TEXT expected, the side recorded no further event"
    assert java["kind"].startswith("runTask records no events")
