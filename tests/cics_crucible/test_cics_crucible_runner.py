"""#3989: the CICS crucible runner, without GnuCOBOL, Docker or Maven.

Pinned here: reading a case (case.json, the CSD, the expected logs, the format guard), laying out
its areas (COPY members inlined), the exact comparison of SPEC section 6 (text padding, hex, numbers,
areas, event order, unmodelled features), the stub's event log as SPEC events, the Java test's output
as an actual log, the baseline ratchet, the report, and the pin's one-line form the workflow reads.
The fixture case (fixture/cases/...) is in the crucible's format; the end-to-end test at the bottom
runs it through every side and needs EQUIVALENCE_E2E=1 (Docker GnuCOBOL + a JDK 17 and Maven).
"""

import copy
import datetime
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
    assert csd == {
        "programs": {"A"},
        "transactions": {"T1": "A", "T2": "B"},
        "mapsets": {"MS"},
        "terminals": {},
        "uctran": {},
    }


def test_the_csd_names_each_terminals_device():
    """#4413: a terminal's TYPETERM DEVICE decides whether a terminal RECEIVE raises EOC (SPEC section 2)."""
    csd = cc.parse_csd("DEFINE TYPETERM(LU2) GROUP(G) DEVICE(LUTYPE2) TERMMODEL(2)\n       ATI(YES) TTI(YES)\n"
                       "DEFINE TYPETERM(PLAIN) GROUP(G) ATI(YES) TTI(YES)\nDEFINE TERMINAL(T001) GROUP(G) TYPETERM(LU2)\n"
                       "DEFINE TERMINAL(T002) GROUP(G) TYPETERM(PLAIN)\n")  # fmt: skip
    assert csd["terminals"] == {"T001": "LUTYPE2", "T002": "3270"}


def test_the_csd_names_each_terminals_uctran():
    """#4415 (register X26): a TYPETERM's UCTRAN is the terminal's UCTRANST, YES / NO / TRANID as UCTRAN / NOUCTRAN /
    TRANIDONLY; a terminal whose TYPETERM says nothing has none stated (INQUIRE TERMINAL UCTRANST is refused)."""
    import cics_crucible as runner

    csd = cc.parse_csd("DEFINE TYPETERM(A) GROUP(G) ATI(YES) TTI(YES) UCTRAN(TRANID)\n"
                       "DEFINE TYPETERM(B) GROUP(G) ATI(YES) TTI(YES)\nDEFINE TERMINAL(T001) GROUP(G) TYPETERM(A)\n"
                       "DEFINE TERMINAL(T002) GROUP(G) TYPETERM(B)\n")  # fmt: skip
    assert csd["uctran"] == {"T001": "TRANID"}
    case = type("C", (), {"csd": csd, "data": {"terminal": "T001"}})()
    assert runner.terminal_uctranst(case) == "TRANIDONLY"
    case.data = {"terminal": "T002"}
    assert runner.terminal_uctranst(case) is None
    assert runner.UCTRAN_TO_UCTRANST == {"YES": "UCTRAN", "NO": "NOUCTRAN", "TRANID": "TRANIDONLY"}


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
    ctx = runner.case_context(cc.load_case(tmp_path / "c"))
    assert [(f["name"], f["offset"], f["bytes"]) for f in ctx.layouts["STATE"]] == [
        ("H-EYE", 0, 4), ("H-LEN", 4, 2), ("WS-COUNT", 6, 3), ("WS-NAME", 9, 8)]  # fmt: skip


def test_the_fixture_context_has_its_layout(tmp_path):
    ctx = runner.case_context(_case())
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


# ---- #4049: strengthened scenarios, their logs derived from the COBOL ---------------------------------------
def test_a_log_derived_from_the_cobol_run_is_what_that_run_did():
    case = _case()
    act = _actual_from_expected(case.expected["three-visits"])
    log = runner.derive_expected(case, act, "three-visits", {})
    assert log["derived"]["from"] == "cobol-stub" and log["format"] == cc.EXPECTED_FORMAT
    assert cc.compare(log, act, ALL, _ctx()).status == "pass"
    other = copy.deepcopy(act)
    other["tasks"][1]["commarea"] = _raw("009FIRST   ")
    assert cc.compare(log, other, ALL, _ctx()).status == "fail"
    # a COMMAREA is written by its layout's fields, the same as the hand-written log
    assert log["tasks"][1]["commarea"] == case.expected["three-visits"]["tasks"][1]["commarea"]
    assert log["tasks"][1]["commarea"]["fields"] == {"WS-COUNT": "1", "WS-NAME": "FIRST"}


def test_no_log_is_derived_from_what_the_cobol_side_does_not_model_or_could_not_run():
    case = _case()
    act = _actual_from_expected(case.expected["three-visits"])
    act["tasks"][0]["events"][0]["text"] = cc.Unmodelled("something")
    with pytest.raises(RuntimeError, match="does not model"):
        runner.derive_expected(case, act, "three-visits", {})
    with pytest.raises(RuntimeError, match="stopped early"):
        runner.derive_expected(case, {"tasks": [], "stopped": "step 0: no transid"}, "three-visits", {})


def test_strengthened_scenarios_join_their_case_with_their_derived_logs(tmp_path):
    case = _case()
    sc = {"id": "s-extra", "path": "trap", "summary": "x", "steps": [{"at": 0, "aid": "ENTER", "text": "FX01"}],
          "faults": [{"task": "FX01", "cmd": "WRITEQ-TS", "queue": "Q1", "resp": "INVREQ"}]}  # fmt: skip
    d = tmp_path / case.id
    (d / "expected").mkdir(parents=True)
    (d / "case.json").write_text(json.dumps({"format": runner.STRENGTHENED_FORMAT, "case": case.id,
                                             "scenarios": [sc]}), encoding="utf-8")  # fmt: skip
    with pytest.raises(cc.CaseError, match="derive-expected"):
        runner.add_strengthened(case, tmp_path)
    (d / "expected" / "s-extra.json").write_text(json.dumps({"tasks": []}), encoding="utf-8")
    case = _case()
    assert runner.add_strengthened(case, tmp_path) == ["s-extra"] and case.expected["s-extra"] == {"tasks": []}
    assert case.scenarios[-1]["id"] == "s-extra"
    assert runner.fault_plans(sc) == {"FX01": ["WRITEQ-TS Q1 1 16 0"]} and runner.task_faults(sc, "FX02") == []
    with pytest.raises(cc.CaseError, match="already"):  # a strengthened scenario never replaces the crucible's
        runner.add_strengthened(case, tmp_path)
    with pytest.raises(cc.CaseError, match="names the TRANSID"):
        runner.fault_plans({"id": "x", "faults": [{"cmd": "XCTL", "program": "P", "resp": "PGMIDERR"}]})


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
    # #4009: a COMMAREA passed as its whole record has its layout's length (STATE: 11 bytes)
    act["tasks"][1]["eibcalen"] = cc.FULL
    assert cc.compare(exp, act, ALL, _ctx()).status == "pass"
    exp["tasks"][1]["eibcalen"] = 3
    assert cc.compare(exp, act, ALL, _ctx()).reason == "task 2 (FX01): eibcalen 3 expected, got 11"


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


def test_a_dto_area_is_its_whole_record_unless_a_length_is_given():
    lay = _ctx().layouts
    w = cc._Walk(ALL, cc.Context(layouts=lay))
    full = {"length": 11, "layout": "STATE", "fields": {"WS-COUNT": "3", "WS-NAME": "FIRST"}}
    w.area("here", "commarea", full, cc.FieldArea({"WS-COUNT": 3, "WS-NAME": "FIRST"}))
    assert w.pending is None
    with pytest.raises(cc._Decided, match="WS-NAME 'FIRST' expected, got 'LAST'"):
        w.area("here", "commarea", full, cc.FieldArea({"WS-COUNT": 3, "WS-NAME": "LAST"}))
    short = {"length": 3, "layout": "STATE", "fields": {"WS-COUNT": "3"}}
    # #4009: a DTO passed without a LENGTH is its whole record; a shorter COMMAREA must state its length
    with pytest.raises(cc._Decided, match=r"commarea length 3 expected, got its whole record \(11 bytes"):
        w.area("here", "commarea", short, cc.FieldArea({"WS-COUNT": Decimal(3), "WS-NAME": "FIRST"}))
    w.area("here", "commarea", short, cc.FieldArea({"WS-COUNT": Decimal(3), "WS-NAME": "FIRST"}, 3))
    with pytest.raises(cc._Decided, match="commarea length 3 expected, got 11"):
        w.area("here", "commarea", short, cc.FieldArea({"WS-COUNT": Decimal(3), "WS-NAME": "FIRST"}, 11))
    assert w.pending is None


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
    assert cc.blockers(exp, runner.JAVA_CAPS) == []  # #4006: CicsTask records START, the driver schedules it


def test_final_ts_queues_are_compared_exactly():
    exp = _case().expected["three-visits"] | {"final": {"ts_queues": {"Q": ["AB", {"hex": "00"}]}}}
    act = _actual_from_expected(exp) | {"final": {"ts_queues": {"Q": ["AB".encode(E), b"\x00"]}}}
    assert cc.compare(exp, act, ALL, _ctx()).status == "pass"
    # SPEC 6.1: an item's length is known (its own), so the log's text is blank-padded to it: trailing blanks
    # are optional (#4006: GTLOG's 34-byte items are logged as their text), embedded or missing bytes are not
    act["final"]["ts_queues"]["Q"][0] = "AB  ".encode(E)
    assert cc.compare(exp, act, ALL, _ctx()).status == "pass"
    for wrong in ("A B", "A", "ABC"):
        act["final"]["ts_queues"]["Q"][0] = wrong.encode(E)
        assert cc.compare(exp, act, ALL, _ctx()).kind == "item differs"
    assert cc.compare(exp, act, runner.COBOL_CAPS, _ctx()).status in ("unsupported", "fail")


# ---- the sides' logs --------------------------------------------------------------------------
def test_the_stub_log_becomes_spec_events(tmp_path):
    (tmp_path / "events.txt").write_text(
        "001 RECEIVE-MAP map=M mapset=M resp=0\n002 SEND-TEXT len=5 opts=TEXT ERASE FREEKB\n"
        "003 SEND-MAP map=M mapset=S len=9 opts=\n004 RECEIVE-MAP map=M mapset=S resp=36\n005 XCTL program=NEXT len=3\n"
        "006 ABEND abcode=AEYH cause=condition condition=44 outcome=exit exit=HCMAIN.MAIN-ABEND\n"
        "007 ABEND abcode=???? cause=condition condition=4 outcome=terminated\n"
        "008 ABEND abcode=XX01 cause=command outcome=terminated\n009 RETURN transid=T1 len=2\n010 END\n",
        encoding="latin-1")  # fmt: skip
    (tmp_path / "002.bin").write_bytes(b"HI  !")
    (tmp_path / "005.bin").write_bytes(b"ABC")
    (tmp_path / "009.bin").write_bytes(b"\x00Z")
    evs = runner._cobol_events(tmp_path, "PROG")[1:]
    assert [e["event"] for e in evs] == ["SEND-TEXT", "SEND-MAP", "RECEIVE-MAP", "XCTL", "ABEND", "ABEND", "ABEND",
                                         "RETURN", "RETURN"]  # fmt: skip
    assert evs[0] == {"event": "SEND-TEXT", "program": "PROG", "text": "HI  !".encode(E), "length": 5,
                      "options": ["ERASE", "FREEKB"]}  # fmt: skip
    assert evs[2]["resp"] == "MAPFAIL" and evs[3]["target"] == "NEXT" and evs[3]["commarea"].data == b"ABC"
    assert (evs[4]["abcode"], evs[4]["condition"], evs[4]["cause"]) == ("AEYH", "QIDERR", "condition")
    assert (evs[4]["outcome"], evs[4]["exit"]) == ("exit", {"program": "HCMAIN", "label": "MAIN-ABEND"})
    assert isinstance(evs[5]["abcode"], cc.Unmodelled)  # EOF: no documented AEIx code in SPEC 6.2's table
    assert (evs[6]["abcode"], evs[6]["cause"], evs[6]["outcome"]) == ("XX01", "command", "terminated")
    assert "exit" not in evs[6] and "condition" not in evs[6]
    assert {e["program"] for e in evs} == {"PROG"}  # an exit's program names the exit, not the issuer
    assert (evs[7]["transid"], evs[7]["commarea"].data) == ("T1", b"\x00Z")
    assert (evs[8]["transid"], evs[8]["commarea"]) == (None, None)  # a GOBACK is a RETURN


def test_link_levels_are_logged_with_their_issuer_and_the_callers_commarea(tmp_path):
    """#4004: each stub line names its issuing program; a LINK carries RESP2 only when it failed; a RETURN
    below level 1 carries the LINK COMMAREA as the caller now sees it (len -1: the LINK had none)."""
    (tmp_path / "events.txt").write_text(
        "001 LINK pgm=CALINK target=CASUB len=3 area=1 resp=0 resp2=0\n002 RETURN pgm=CASUB level=2 transid= len=3\n"
        "003 LINK pgm=CALINK target=CAGONE len=3 area=1 resp=27 resp2=1\n"
        "004 LINK pgm=CALINK target=CASUB len=0 area=0 resp=0 resp2=0\n005 RETURN pgm=CASUB level=2 transid= len=-1\n"
        "006 NOPROGRAM pgm=CALINK target=CAXX\n007 RETURN pgm=CALINK level=1 transid=CA01 len=0\n",
        encoding="latin-1")  # fmt: skip
    (tmp_path / "001.bin").write_bytes(b"ABC")
    (tmp_path / "002.bin").write_bytes(b"XYZ")
    evs = runner._cobol_events(tmp_path, "FIRST")
    assert [e["program"] for e in evs] == ["CALINK", "CASUB", "CALINK", "CALINK", "CASUB", "CAXX", "CALINK"]
    assert (evs[0]["target"], evs[0]["length"], evs[0]["commarea"].data, evs[0]["resp"], evs[0]["resp2"]) == (
        "CASUB", 3, b"ABC", "NORMAL", None)  # fmt: skip
    assert evs[1] == {"event": "RETURN", "program": "CASUB", "level": 2, "caller_commarea": evs[1]["caller_commarea"]}
    assert evs[1]["caller_commarea"].data == b"XYZ"
    assert (evs[2]["resp"], evs[2]["resp2"], evs[3]["commarea"], evs[4]["caller_commarea"]) == (
        "PGMIDERR",
        1,
        None,
        None,
    )
    assert evs[5]["event"] == "DRIVER-ERROR" and "CAXX" in evs[5]["message"]
    assert (evs[6]["level"], evs[6]["transid"], evs[6]["commarea"]) == (1, "CA01", None)


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
        {"termid": "T001", "at": "2026-03-02T10:00:10", "trigger": {"kind": "terminal", "step": 1}, "eibaid": "ENTER",
         "transid": "FX01", "program": "FXCHAIN", "commarea": ca, "end": "normal", "events": [
            {"event": "SEND-MAP", "program": "FXCHAIN", "map": "M1", "screen": {"NAME": "ADA", "MSG": None}},
            {"event": "RECEIVE-MAP", "program": "FXCHAIN", "map": "M1", "mapset": "MS", "resp": "MAPFAIL"},
            {"event": "SEND-TEXT", "program": "FXCHAIN", "text": "VISIT 002", "length": 40, "options": ["ERASE"]},
            {"event": "RECEIVE", "program": "FXCHAIN", "resp": "NORMAL", "length": 4, "data": "FX01"},
            {"event": "READQ-TS", "program": "FXCHAIN", "queue": "Q", "item": 1, "resp": "NORMAL", "length": 1,
             "data": "wQ=="},
            {"event": "RETURN", "program": "FXCHAIN", "transid": "FX01", "commarea": ca, "length": 3},
            {"event": "LINK", "program": "FXCHAIN", "target": "SUB", "length": 11, "commarea": ca, "resp": "NORMAL",
             "resp2": None},
            {"event": "RETURN", "program": "SUB", "level": 2, "caller_commarea": ca},
            {"event": "START", "program": "FXCHAIN", "transid": "GT02", "termid": None, "interval": "000010",
             "from": "wcI=", "protect": False, "resp": "NORMAL", "expires": "2026-03-02T10:00:20"},
            {"event": "RETRIEVE", "program": "FXCHAIN", "resp": "ENDDATA", "length": None, "data": None},
            {"event": "CANCEL", "program": "FXCHAIN", "reqid": "R1", "resp": "NOTFND"},
            {"event": "XCTL", "program": "FXCHAIN", "target": "FXLAST", "commarea": ca},
            {"event": "DRIVER-ERROR", "program": "FXLAST", "message": "no generated service for program FXLAST"}]}]}  # fmt: skip
    act = runner.java_actual(_case(), raw, src)
    assert act["final"] == {"ts_queues": {"Q": [b"\xc1\xc2"]}}  # #4002: the queues the scenario left, EBCDIC
    t = act["tasks"][0]
    assert (t["at"], t["eibaid"], t["trigger"], t["termid"]) == ("2026-03-02T10:00:10", "ENTER",
                                                                 {"kind": "terminal", "step": 1}, "T001")  # fmt: skip
    # #4009: no EIBCALEN from the driver -> the whole record, resolved against the layout by the comparison
    assert t["eibcalen"] == cc.FULL and t["commarea"].fields == {"WS-COUNT": 2, "WS-NAME": "FIRST"}
    assert t["commarea"].length == cc.FULL
    assert t["events"][0]["fields"] == {"NAME": {"data": "ADA"}, "MSG": {"data": None}}
    assert t["events"][1] == {"event": "RECEIVE-MAP", "program": "FXCHAIN", "map": "M1", "mapset": "MS",
                              "resp": "MAPFAIL"}  # fmt: skip
    assert (t["events"][2]["text"], t["events"][2]["length"], t["events"][2]["options"]) == ("VISIT 002", 40, ["ERASE"])
    assert (t["events"][3]["resp"], t["events"][3]["length"], t["events"][3]["data"].data) == ("NORMAL", 4, b"FX01")
    assert (t["events"][4]["queue"], t["events"][4]["length"], t["events"][4]["data"].data) == ("Q", 1, b"\xc1")
    assert t["events"][5]["commarea"].length == 3  # RETURN ... LENGTH(3)
    link, back = t["events"][6], t["events"][7]  # #4004
    assert (link["target"], link["commarea"].fields["WS-COUNT"], link["commarea"].length) == ("SUB", 2, 11)
    assert back["level"] == 2 and back["caller_commarea"].fields["WS-NAME"] == "FIRST"
    start, retrieve, cancel = t["events"][8:11]  # #4006
    assert (start["interval"], start["from"].data, start["expires"], "reqid" in start) == (
        "000010", b"\xc1\xc2", "2026-03-02T10:00:20", False)  # fmt: skip
    assert (retrieve["resp"], retrieve["data"], cancel["reqid"], cancel["resp"]) == ("ENDDATA", None, "R1", "NOTFND")
    assert t["events"][11]["target"] == "FXLAST" and t["events"][12]["message"].startswith("no generated service")
    raw["tasks"][0]["eibcalen"] = 3
    t = runner.java_actual(_case(), raw, src)["tasks"][0]
    assert t["eibcalen"] == 3 and t["commarea"].length == 3


# ---- the translator names what it refuses -----------------------------------------------------
def test_the_translator_names_each_refused_command_as_a_feature():
    src = (FIXTURE / "src/FXCHAIN.cbl").read_text().replace(
        "           STRING 'VISIT '",
        "           EXEC CICS SYNCPOINT END-EXEC\n           EXEC CICS READQ TS QUEUE('Q') INTO(WS-LINE)\n"
        "           END-EXEC\n           EXEC CICS RECEIVE INTO(WS-LINE) END-EXEC\n"
        "           IF EIBRESP = DFHRESP(NOSUCH) CONTINUE END-IF\n           STRING 'VISIT '")  # fmt: skip
    with pytest.raises(ec.Unsupported) as e:
        ec.translate(src)
    # #4005 / #4002: RECEIVE and READQ TS translate; file updates: SYNCPOINT too
    assert e.value.features == ["DFHRESP(NOSUCH)"]
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


def _coverage(**scenarios):
    """Results carrying one program's coverage: scenario -> (units, outcomes)."""
    summary = {"paragraphs": {"covered": 0, "live": 3, "dead": [], "uncovered": []},
               "branches": {"covered": 0, "total": 4, "uncovered": [], "unresolvable": []},
               "handler_labels": {"covered": 0, "total": 0, "uncovered": []}}  # fmt: skip
    return {
        "crucible_ref": "abc",
        "cells": {},
        "coverage": {
            "c": {
                "P": {
                    "scenarios": {sid: {"units": u, "outcomes": o} for sid, (u, o) in scenarios.items()},
                    "summary": summary,
                }
            }
        },
    }


def test_the_coverage_ratchet_catches_lost_and_gained_paths(tmp_path):
    """#4023: per scenario, the paragraphs and branch outcomes it executes -- sets, so a swap is caught."""
    runner.write_coverage(_coverage(s=(["A", "B"], ["9:true"]), t=(["A"], [])), tmp_path / "cov.json")
    ledger = runner.read_coverage(tmp_path / "cov.json")
    assert ledger["programs"]["c/P"]["live"] == 3 and ledger["programs"]["c/P"]["outcomes"] == 4
    assert runner.coverage_ratchet(_coverage(s=(["A", "B"], ["9:true"]), t=(["A"], [])), ledger, True) == []
    errors = runner.coverage_ratchet(_coverage(s=(["A", "C"], ["9:true"]), t=(["A"], [])), ledger, True)
    assert errors == ["COVERAGE LOST: c/P scenario s: units B",
                      "COVERAGE GAINED: c/P scenario s: units C -- ratchet it in (--update-baseline)"]  # fmt: skip
    gone = {"crucible_ref": "abc", "cells": {}, "coverage": {}}
    assert runner.coverage_ratchet(gone, ledger, False) == []  # a partial run: not measured is not stale
    assert runner.coverage_ratchet(gone, ledger, True) == [
        "COVERAGE STALE: c/P is in the coverage ledger but was not measured -- re-baseline"]  # fmt: skip
    # a proven port's claim: the scenarios it proved on, and how much of the program those execute
    assert (
        runner.ledger_claim("c", "P", ["s"], ledger) == "proven on 1 scenario, covering 2/3 paragraphs and 1/4 branches"
    )
    assert runner.ledger_claim("c", "Q", ["s"], ledger) is None


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
def test_the_pin_is_the_manifest_ref_the_workflow_reads(tmp_path):
    text = (TESTS / "crucible_pins.toml").read_text()
    found = re.findall(r'^\[cics\]\n(?:(?!\[).*\n)*?ref = "(.*)"$', text, re.M)
    assert found == [pin.PINNED_REF] and re.fullmatch(r"[0-9a-f]{40}|v\d+(\.\d+)*", pin.PINNED_REF)
    workflow = (TESTS.parent / ".github/workflows/cics-crucible.yml").read_text()
    assert "tests/tools/crucible_pins.py get cics" in workflow and "tests/crucible_pins.toml" in workflow
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
    ports = runner.PortOptions(root=FIXTURE_ROOT / "ports")  # the fixture's own scaffolding ports, not the crucible's
    res = runner.measure(FIXTURE_ROOT, None, set(cc.SIDES), tmp_path, offline=os.environ.get("MAVEN_OFFLINE") == "1",
                         ports=ports)  # fmt: skip
    got = {cid: c["status"] for cid, c in res["cells"].items()}
    assert got == {"fx-text-chain/*/engine-facts": "pass", "fx-text-chain/*/forge-compile": "pass",
                   "fx-text-chain/three-visits/cobol-stub": "pass", "fx-text-chain/three-visits/java": "fail",
                   # #3989: the ports laid over the generated services (RETURN LENGTH, an XCTL to a second port)
                   "fx-text-chain/three-visits/java-ported": "pass",
                   # #4343: the fixture's ports keep the old log-only facades: entered through them, nothing runs
                   "fx-text-chain/three-visits/java-facade": "fail",
                   # #4005 / #4002: terminal RECEIVE, TS seeding, READQ LENGERR / QIDERR, the final queue
                   "fx-ts-queue/*/engine-facts": "pass", "fx-ts-queue/*/forge-compile": "pass",
                   "fx-ts-queue/seeded/cobol-stub": "pass", "fx-ts-queue/seeded/java": "fail",
                   "fx-ts-queue/seeded/java-ported": "fail", "fx-ts-queue/seeded/java-facade": "fail"}  # fmt: skip
    assert res["cells"]["fx-ts-queue/seeded/java-ported"]["kind"] == "not ported"
    assert "handleTransaction of FXCHAIN did not run its task in the region" in \
        res["cells"]["fx-text-chain/three-visits/java-facade"]["reason"]  # fmt: skip
    java = res["cells"]["fx-text-chain/three-visits/java"]
    assert java["reason"] == "task 1 (FX01) event 1: SEND-TEXT expected, the side recorded no further event"
    assert java["kind"].startswith("runTask records no events")
    # #4023: the passing cobol-stub scenario's COBOL was traced; the ported programs carry their claim
    chain = res["coverage"]["fx-text-chain"]
    assert chain and all(r["scenarios"] == {"three-visits": r["scenarios"]["three-visits"]} for r in chain.values())
    for r in chain.values():
        s = r["summary"]
        assert s["paragraphs"]["covered"] >= 1 and s["paragraphs"]["unread"] == []
        assert r["port"]["claim"].startswith("proven on 1 scenario, covering ")


# ---- #4006: the scheduler (SPEC section 4) --------------------------------------------------------------
def _sched_case(scenario: dict) -> cc.Case:
    data = {"clock": "2026-03-02T10:00:00", "terminal": "T001", "scenarios": [scenario]}
    return cc.Case(Path("."), data, {}, {"programs": set(), "transactions": {}, "mapsets": set()})


def _start(transid, expires, termid=None, data=None, reqid=None, protect=False):
    e = {"event": "START", "program": "P", "transid": transid, "termid": termid, "protect": protect,
         "resp": "NORMAL", "expires": expires, "from": _raw(data) if data else None}  # fmt: skip
    return e | ({"reqid": reqid} if reqid else {})


def _drive(scenario: dict, script: dict):
    """Runs the scheduler with fake tasks: script[transid] -> the events a task of it records (a callable of
    the task's inputs, or a list), each run noted as (transid, at, termid, trigger, data)."""
    runs = []

    def run_one(frame, transid, commarea, step, data, requests):
        runs.append((transid, frame["at"][11:], frame["termid"], frame["trigger"], [d["data"].decode() for d in data]))
        got = script.get(transid, [])
        events = got(frame, requests) if callable(got) else got
        end = "abend" if any(e.get("outcome") == "terminated" for e in events) else "normal"
        return {"termid": frame["termid"], "events": events, "end": end}

    tasks, stopped = runner.drive_scenario(_sched_case(scenario), scenario, run_one)
    return runs, stopped


def test_expired_starts_run_after_their_starter_in_expiry_order_then_the_next_step():
    """SPEC 4: when a task ends, expired requests run first (earliest expiry, ties by issue order), then the next
    operator step once its time has come; virtual time jumps to the next expiry or step; after the last step,
    requests keep running until none expires before `until`."""
    sc = {"id": "s", "steps": [{"at": 0, "aid": "ENTER", "text": "GT01"}, {"at": 20, "aid": "ENTER", "text": "GT01"}],
          "until": 60}  # fmt: skip
    first = [_start("GT02", "2026-03-02T10:00:30", data="LATE"), _start("GT02", "2026-03-02T10:00:00", data="NOW"),
             _start("GT02", "2026-03-02T10:00:10", data="TEN"), _start("GT02", "2026-03-02T10:02:00", data="NEVER")]  # fmt: skip
    calls = iter([first, []])
    runs, stopped = _drive(sc, {"GT01": lambda f, r: next(calls)})
    assert stopped is None
    assert [(t, at, trig.get("event", trig.get("step")), d) for t, at, _termid, trig, d in runs] == [
        ("GT01", "10:00:00", 0, []), ("GT02", "10:00:00", 1, ["NOW"]), ("GT02", "10:00:10", 2, ["TEN"]),
        ("GT01", "10:00:20", 1, []), ("GT02", "10:00:30", 0, ["LATE"])]  # fmt: skip
    assert runs[1][3] == {"kind": "start", "task": 1, "event": 1} and runs[1][2] is None


def test_expired_terminal_starts_for_one_transid_become_one_task():
    """SPEC 4 / IBM START: all expired requests for the same TRANSID and TERMID are satisfied by one task, which
    RETRIEVEs their data in expiry order; a request not yet expired waits for its own task."""
    sc = {"id": "s", "steps": [{"at": 0, "aid": "ENTER", "text": "GT11"}], "until": 60}
    starts = [_start("GT12", "2026-03-02T10:00:00", "T001", "ALPHA"), _start("GT12", "2026-03-02T10:00:00", "T001", "BRAVO"),
              _start("GT12", "2026-03-02T10:00:10", "T001", "LATER"), _start("GT13", "2026-03-02T10:00:00", "T001", "OTHER")]  # fmt: skip
    runs, _ = _drive(sc, {"GT11": starts})
    assert [(t, at, termid, d) for t, at, termid, _trig, d in runs] == [
        ("GT11", "10:00:00", "T001", []), ("GT12", "10:00:00", "T001", ["ALPHA", "BRAVO"]),
        ("GT13", "10:00:00", "T001", ["OTHER"]), ("GT12", "10:00:10", "T001", ["LATER"])]  # fmt: skip
    assert runs[1][3] == {"kind": "start", "task": 1, "event": 0}  # a coalesced task names the first request


def test_a_protect_start_dies_with_its_abending_starter_and_a_cancel_drops_a_request():
    sc = {"id": "s", "steps": [{"at": 0, "aid": "ENTER", "text": "GT01"}, {"at": 10, "aid": "ENTER", "text": "GT09"}],
          "until": 120}  # fmt: skip
    abend = {"event": "ABEND", "program": "P", "abcode": "GTAB", "cause": "command", "outcome": "terminated"}
    starts = [_start("GT02", "2026-03-02T10:00:00", data="PLAIN"), _start("GT02", "2026-03-02T10:00:00", data="PROT", protect=True),
              _start("GT03", "2026-03-02T10:00:30", reqid="R1"), abend]  # fmt: skip
    seen = []

    def cancel(frame, requests):
        seen.append(requests)
        return [{"event": "CANCEL", "program": "P", "reqid": "R1", "resp": "NORMAL"}]

    runs, _ = _drive(sc, {"GT01": starts, "GT09": cancel})
    assert [(t, d) for t, _at, _termid, _trig, d in runs] == [("GT01", []), ("GT02", ["PLAIN"]), ("GT09", [])]
    assert seen == [[("R1", runner._epoch(datetime.datetime(2026, 3, 2, 10, 0, 30)))]]


def test_the_terminal_follows_its_last_tasks_return_transid():
    ret = {"event": "RETURN", "program": "P", "level": 1, "transid": "NX01", "commarea": _raw("CA")}
    sc = {"id": "s", "steps": [{"at": 0, "aid": "ENTER", "text": "AA01"}, {"at": 10, "aid": "PF3"},
                               {"at": 20, "aid": "ENTER"}]}  # fmt: skip
    runs, stopped = _drive(sc, {"AA01": [ret]})
    assert [t for t, *_ in runs] == [
        "AA01",
        "NX01",
    ] and stopped == "step 2: no pending RETURN TRANSID and no transaction id typed"


def test_a_failed_xctl_is_logged_with_its_resp2(tmp_path):
    (tmp_path / "events.txt").write_text(
        "001 XCTL pgm=CAXA program=CAXB len=32767 area=1 resp=22 resp2=11\n"
        "002 XCTL pgm=CAXA program=CAXB len=10 area=1 resp=0 resp2=0\n003 XCTL pgm=CAXA program=M len=0 area=0 resp=0 resp2=0\n",
        encoding="latin-1")  # fmt: skip
    (tmp_path / "001.bin").write_bytes(b" " * 32767)
    (tmp_path / "002.bin").write_bytes(b"1C0042")
    evs = runner._cobol_events(tmp_path, "P")
    assert (evs[0]["resp"], evs[0]["resp2"], evs[0]["length"], len(evs[0]["commarea"].data)) == (
        "LENGERR",
        11,
        32767,
        32767,
    )
    assert (evs[1]["resp"], evs[1]["resp2"], evs[2]["commarea"]) == ("NORMAL", None, None)


def test_interval_events_are_logged_as_spec_spells_them(tmp_path):
    (tmp_path / "events.txt").write_text(
        "001 START pgm=GTSTART transid=GT02 termid= time=103000 reqid= protect=0 resp=0 expires=2026-03-02T10:30:00 len=20 area=1\n"
        "002 START pgm=GTTERM transid=GT12 termid=T001 interval=000030 reqid=GTREQ001 protect=1 resp=0 "
        "expires=2026-03-02T10:00:30 len=0 area=0\n003 START pgm=X transid=NOPE termid= interval=000000 reqid= protect=0 "
        "resp=28 expires= len=0 area=0\n004 RETRIEVE pgm=GTWORK resp=22 len=30 copied=20\n"
        "005 RETRIEVE pgm=GTWORK resp=29 len=-1 copied=0\n006 CANCEL pgm=GTTERM reqid=GTREQ001 resp=13\n",
        encoding="latin-1")  # fmt: skip
    (tmp_path / "001.bin").write_bytes(b"ORDER 0001 READY    ")
    (tmp_path / "004.bin").write_bytes(b"THIRTY BYTE PAYLOAD ")
    evs = runner._cobol_events(tmp_path, "P")
    assert evs[0]["time"] == "103000" and "interval" not in evs[0] and "reqid" not in evs[0]
    assert (evs[0]["termid"], evs[0]["protect"], evs[0]["from"].data[:5]) == (None, False, b"ORDER")
    assert (evs[1]["interval"], evs[1]["reqid"], evs[1]["protect"], evs[1]["from"]) == (
        "000030",
        "GTREQ001",
        True,
        None,
    )
    assert (evs[2]["resp"], evs[2]["expires"]) == ("TRANSIDERR", None)
    assert (evs[3]["resp"], evs[3]["length"], evs[3]["data"].data) == ("LENGERR", 30, b"THIRTY BYTE PAYLOAD ")
    assert (evs[4]["resp"], evs[4]["length"], evs[4]["data"]) == ("ENDDATA", None, None)
    assert (evs[5]["reqid"], evs[5]["resp"]) == ("GTREQ001", "NOTFND")


# ---- #4001: BMS output fidelity, both sides --------------------------------------------------------
_BMS = (
    "TSET     DFHMSD TYPE=&SYSPARM,MODE=INOUT,LANG=COBOL,TIOAPFX=YES\n"
    "TMAP     DFHMDI SIZE=(24,80)\n"
    "NAME     DFHMDF POS=(1,1),LENGTH=4,ATTRB=(UNPROT,NORM,IC)\n"
    "AMT      DFHMDF POS=(2,1),LENGTH=3,ATTRB=(UNPROT,NUM),INITIAL='000'\n"
    "         DFHMSD TYPE=FINAL\n"
)


def _screen() -> "runner.Screen":
    import cics_bms

    def f(name: str, offset: int, size: int) -> dict:
        return {"name": name, "offset": offset, "bytes": size}

    # the symbolic map as BMS lays it out without DSATTS: L (2), F/A (1), I/O (data), per field
    inp = {n: f(n, o, b) for n, o, b in [("NAMEL", 0, 2), ("NAMEF", 2, 1), ("NAMEI", 3, 4), ("AMTL", 7, 2),
                                         ("AMTF", 9, 1), ("AMTI", 10, 3)]}  # fmt: skip
    out = {"NAMEO": f("NAMEO", 3, 4), "AMTO": f("AMTO", 10, 3)}
    return runner.Screen(cics_bms.parse_bms(_BMS)["TMAP"], inp, out)


def test_a_stub_send_map_is_resolved_from_the_symbolic_map_and_the_bms_source(tmp_path):
    # NAME: X'4D' (an EBCDIC byte, kept) and data typed in the stub's page; AMT: length -1, X'80', nulls
    area = b"\x00\x00\x4dADA " + b"\xff\xff\x80" + b"\x00\x00\x00"
    (tmp_path / "events.txt").write_text("001 SEND-MAP map=TMAP mapset=TSET len=13 cursor=-1 opts=DATAONLY CURSOR\n"
                                         "002 SEND-MAP map=TMAP mapset=TSET len=0 cursor=-1 opts=MAPONLY ERASE\n"
                                         "003 SEND-MAP map=TMAP mapset=TSET len=13 cursor=40 opts=ERASE CURSOR\n",
                                         encoding="latin-1")  # fmt: skip
    for n in ("001", "003"):
        (tmp_path / f"{n}.bin").write_bytes(area)
    one, two, three = runner._cobol_events(tmp_path, "P", {"TMAP": _screen()})
    assert one["options"] == ["DATAONLY", "CURSOR"] and one["cursor"] == "AMT"  # symbolic: AMTL = -1
    assert one["fields"] == {"NAME": {"attr": "4D", "attr_from": "program", "data": "ADA ".encode(E),
                                      "data_from": "program"}}  # AMT: nothing to send under DATAONLY  # fmt: skip
    assert two["fields"]["AMT"] == {"attr": "50", "attr_from": "map", "data": "000".encode(E), "data_from": "map"}
    assert two["cursor"] == "NAME"  # MAPONLY: the IC field
    assert three["cursor"] == {"offset": 40} and three["fields"]["AMT"]["data_from"] == "map"


def test_receive_map_input_is_justified_and_an_erased_field_is_flagged():
    s = _screen()
    assert s.receive_input({"NAME": "AB", "AMT": "7"}) == b"\x00\x02\x00AB  " + b"\x00\x01\x00007"
    assert s.receive_input({"AMT": ""}) == b"\x00" * 7 + b"\x00\x00\x80" + b"\x00" * 3  # ERASE EOF: DFHBMEOF


def test_a_cicstask_send_map_is_resolved_like_the_stubs():
    e = {"event": "SEND-MAP", "map": "TMAP", "mapset": "TSET", "options": ["CURSOR", "DATAONLY"],
         "screen": {"NAME": "ADA ", "AMT": None}, "subfields": {"NAME": {"attr": 0x4D}, "AMT": {"length": -1}},
         "cursor": None}  # fmt: skip
    fields, cursor = runner.java_send_map(_screen(), e)
    assert fields == {"NAME": {"attr": "4D", "attr_from": "program", "data": "ADA ".encode(E), "data_from": "program"}}
    assert cursor == "AMT"
    fields, cursor = runner.java_send_map(_screen(), {**e, "screen": None, "options": ["MAPONLY"]})
    assert fields["AMT"]["data_from"] == "map" and cursor == "NAME"


# ---- #3989: ports (the porting loop's overlays) and proofs ----------------------------------------------
_DTO = """package com.gitgalaxy.modernized.dto.contract;

public class Ca {

    // CA-FLAG: PIC X, offset 0, 1 bytes (src/P.cbl)
    private String caFlag;

    // CA-COUNT: PIC S9(4) COMP, offset 1, 2 bytes (copy/C.cpy)
    private Integer caCount;

    // CA-AMT: PIC S9(3)V99 COMP-3, offset 3, 3 bytes (copy/C.cpy)
    private java.math.BigDecimal caAmt;

    // CA-VISITS: PIC 9(2), offset 6, 2 bytes (copy/C.cpy)
    private Integer caVisits;
}
"""


def test_a_dto_is_encoded_as_its_records_ebcdic_bytes(tmp_path):
    """A log may give a COMMAREA as text or hex; the Java side's DTO is then compared as the bytes its layout
    (the generated field comments) says the record holds: text blank-padded, COMP, COMP-3, zoned."""
    src = tmp_path / "src"
    (src / "com/gitgalaxy/modernized/dto/contract").mkdir(parents=True)
    (src / "com/gitgalaxy/modernized/dto/contract/Ca.java").write_text(_DTO)
    layout = runner.dto_layout(src, "com.gitgalaxy.modernized.dto.contract.Ca")
    assert [(f["name"], f["pic"], f["usage"], f["offset"], f["bytes"]) for f in layout] == [
        ("CA-FLAG", "X", None, 0, 1), ("CA-COUNT", "S9(4)", "COMP", 1, 2), ("CA-AMT", "S9(3)V99", "COMP-3", 3, 3),
        ("CA-VISITS", "9(2)", None, 6, 2)]  # fmt: skip
    values = {"CA-FLAG": "S", "CA-COUNT": -2, "CA-AMT": "12.5", "CA-VISITS": 7}
    assert runner.dto_bytes(values, layout) == (b"\xe2\xff\xfe\x01\x25\x0c\xf0\xf7", 8)
    # a null field: its bytes are unknown, so only the ones before it are known
    assert runner.dto_bytes({**values, "CA-AMT": None}, layout)[1] == 3
    assert runner.dto_bytes(values, None) == (None, 0)
    assert runner.dto_bytes({**values, "CA-COUNT": "x"}, layout) == (None, 0)


def test_a_dto_area_compares_with_a_text_or_hex_area_by_its_bytes():
    ctx = cc.Context()
    exp = {"tasks": [{"seq": 1, "transid": "HX01", "program": "P", "termid": "T001", "at": "x", "trigger": {"kind": "terminal", "step": 0},
                      "eibaid": "ENTER", "eibcalen": 0, "commarea": None, "end": "normal",
                      "events": [{"event": "RETURN", "program": "P", "level": 1, "transid": "HX01",
                                  "commarea": {"length": 1, "text": "S"}}]}]}  # fmt: skip

    def verdict(area):
        act = copy.deepcopy(exp)
        act["tasks"][0]["events"][0]["commarea"] = area
        return cc.compare(exp, act, runner.JAVA_CAPS, ctx)

    assert verdict(cc.FieldArea({"WS-CA": "S"}, 1, b"\xe2", 1)).status == "pass"
    assert verdict(cc.FieldArea({"WS-CA": "S"}, cc.FULL, b"\xe2", 1)).status == "pass"
    bad = verdict(cc.FieldArea({"WS-CA": "X"}, 1, b"\xe7", 1))
    assert (bad.status, bad.reason) == ("fail", "task 1 (HX01) event 1: commarea byte 0: 'S' expected, got 'X'")
    assert verdict(cc.FieldArea({"WS-CA": "S"}, 3, b"\xe2", 1)).status == "unsupported"  # past the DTO's record
    assert verdict(cc.FieldArea({"WS-CA": "S", "B": None}, 1, b"\xe2\x40", 1)).status == "pass"  # before the null
    assert verdict(cc.FieldArea({"WS-CA": "S", "B": None}, 2, b"\xe2\x40", 1)).status == "unsupported"
    assert verdict(cc.FieldArea({"WS-CA": None}, 1, None)).status == "unsupported"
    # a COMMAREA no DTO describes, passed as a String or byte[]: its bytes
    assert verdict(runner._raw_area({"class": "java.lang.String", "value": "S  "}, 1)).status == "pass"
    assert verdict(runner._raw_area({"class": "[B", "value": "4g=="}, None)).status == "pass"  # X'E2'
    assert runner._raw_area({"class": "java.util.Map", "value": {}}, 1) is None


def test_overlays_are_laid_over_the_generated_package(tmp_path):
    ports = tmp_path / "ports"
    for key in ("PA", "PB"):
        f = ports / key / "overlay" / "service" / f"{key.title()}Service.java"
        f.parent.mkdir(parents=True)
        f.write_text(f"// {key}\n")
    (ports / "stray").mkdir()
    assert list(runner.case_overlays(ports)) == ["PA", "PB"]
    assert runner.case_overlays(tmp_path / "none") == {}
    project = tmp_path / "project"
    laid = runner.lay_overlay(ports / "PA" / "overlay", project)
    assert laid == ["src/main/java/com/gitgalaxy/modernized/service/PaService.java"]
    assert (project / laid[0]).read_text() == "// PA\n"


def test_a_case_with_no_port_fails_its_ported_cells_without_building(tmp_path):
    cells = {}

    def put(scenario, side, v):
        cells[(scenario, side)] = v

    opts = runner.PortOptions(root=tmp_path)
    runner.measure_ported(_case(), tmp_path / "w", True, opts, put)
    assert {k: (v.status, v.kind) for k, v in cells.items()} == {
        ("three-visits", "java-ported"): ("fail", "not ported")
    }
    cells.clear()
    runner.measure_ported(_case(), tmp_path / "w", True, runner.PortOptions(root=tmp_path, program="NOPE"), put)
    assert cells == {}  # no scenario runs that program
    assert not (tmp_path / "w").exists()


def test_a_proof_reports_per_scenario_and_feeds_back_the_first_divergence(tmp_path):
    case = _case()
    cid = "fx-text-chain/three-visits/java-ported"
    reason = "task 3 (FX01) event 2: XCTL expected, got RETURN"
    results = {"crucible_ref": "v0", "cells": {cid: {"case": case.id, "trap": case.trap, "scenario": "three-visits",
                                                     "side": "java-ported", "status": "fail", "reason": reason,
                                                     "features": [], "kind": "XCTL expected, other event"}}}  # fmt: skip
    got = [{"event": "SEND-TEXT", "program": "FXCHAIN", "text": "VISIT 003", "length": 20, "options": ["ERASE"]},
           {"event": "RETURN", "program": "FXCHAIN", "level": 1, "transid": "FX01",
            "commarea": cc.FieldArea({"WS-COUNT": 3, "WS-NAME": "FIRST"}, 11)}]  # fmt: skip
    opts = runner.PortOptions(ports=tmp_path / "ports", program="FXCHAIN")
    opts.actual[cid] = {"tasks": [{"events": []}, {"events": []}, {"events": got}]}
    assert runner.write_proof(tmp_path / "proof", case, results, opts) is False
    report = json.loads((tmp_path / "proof" / "report.json").read_text())
    assert report["outputs"] == {"three-visits": {"equal": 0, "records": 1}} and report["proven"] is False
    fb = report["feedback"]
    assert f"First divergence: {reason}" in fb and '"aid": "PF3"' in fb  # the scenario's operator steps
    assert '"event": "XCTL"' in fb and '"target": "FXLAST"' in fb  # the expected event at the divergence
    assert '"WS-COUNT": 3' in fb  # what the port recorded in that task
    results["cells"][cid].update(status="pass", reason="")
    assert runner.write_proof(tmp_path / "proof", case, results, opts) is True


def test_a_facade_proof_needs_both_paths_and_names_the_facades_it_entered_by(tmp_path):
    """#4343: with the java-facade side, a scenario is proven only when it passes through runTask AND through the
    deployed entry points; `entries` names the program's facades its passing java-facade scenarios ran."""
    case = _case()

    def cell(side, status):
        return {"case": case.id, "trap": case.trap, "scenario": "three-visits", "side": side, "status": status,
                "reason": "" if status == "pass" else "task 1 (FX01) event 1: DRIVER-ERROR", "features": [],
                "kind": None}  # fmt: skip

    ported, facade = "fx-text-chain/three-visits/java-ported", "fx-text-chain/three-visits/java-facade"
    results = {
        "crucible_ref": "v0",
        "cells": {ported: cell("java-ported", "pass"), facade: cell("java-facade", "fail")},
    }
    opts = runner.PortOptions(ports=tmp_path / "ports", program="FXCHAIN")
    opts.entries[facade] = [{"task": 1, "program": "FXCHAIN", "method": "handleTransaction"},
                            {"task": 3, "program": "FXLAST", "method": "handleLink"},
                            {"task": 2, "program": "FXCHAIN", "method": "runTask"}]  # fmt: skip
    assert runner.write_proof(tmp_path / "proof", case, results, opts) is False
    report = json.loads((tmp_path / "proof" / "report.json").read_text())
    assert report["outputs"] == {"three-visits": {"equal": 0, "records": 1}} and report["entries"] == []
    results["cells"][facade] = cell("java-facade", "pass")
    assert runner.write_proof(tmp_path / "proof", case, results, opts) is True
    report = json.loads((tmp_path / "proof" / "report.json").read_text())
    assert report["entries"] == [{"method": "handleTransaction", "scenarios": ["three-visits"]}]  # FXCHAIN's own


def test_the_java_test_enters_tasks_through_the_facades_only_when_asked():
    """#4343: the generated test joins the scenario's region and calls handleTransaction / handleLink under
    -Dequivalence.facades=true; a facade that builds its own task is refused, not silently run."""
    src = runner._JAVA_TEST
    assert 'Boolean.getBoolean("equivalence.facades")' in src and "CicsTask.join(region)" in src
    assert '"handleTransaction"' in src and '"handleLink"' in src
    assert "did not run its task in the region" in src and "that is not the one the scenario starts" in src
    assert "java-facade" in cc.SIDES
