"""survivor_attack (#4628): attacking a survivor before excusing it, and `det_mutation.py state` refusing a verdict with
no attack behind it. No proof, translator or corpus."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import det_mutation as dm
import survivor_attack as sa

PORT = """\
public class XService {
    private static final byte[] IMAGE_USED = new byte[1];
    private static final byte[] IMAGE_UNUSED = new byte[2];
    public void runTask(CicsTask task) {
        step(IMAGE_USED);
    }
    public void handleLink(CicsTask task, byte[] area) {
        linked(area);
    }
    private void step(byte[] b) {
        leaf();
    }
    private void leaf() {
        int x = 1;
    }
    private void linked(byte[] area) {
        int y = 2;
    }
    private void condition(String name) {
        paragraph(1);
    }
    private void paragraph(int n) {
        int z = 3;
    }
}
"""
S1 = {"id": "aaaa000001", "op": "CON", "file": "service/X.java", "line": 10, "before": "x = 0;", "after": "x = 1;"}


def test_dead_code_is_dead_from_every_entry_point_not_from_the_tests():
    live = sa.live_methods(PORT)
    assert {"runTask", "step", "leaf"} <= live
    # a public overload no test calls is still an entry of the program, so it is live
    assert {"handleLink", "linked"} <= live
    # and what no entry reaches is dead, through a chain
    assert not {"condition", "paragraph"} & live


def test_the_port_settles_only_what_its_text_shows():
    assert sa.port_fact(PORT, {"line": 22, "before": "int z = 3;"})["result"] == "no-entry-path"
    assert sa.port_fact(PORT, {"line": 17, "before": "int y = 2;"}) is None
    unused = "    private static final byte[] IMAGE_UNUSED = new byte[2];"
    assert sa.port_fact(PORT, {"line": 3, "before": unused})["result"] == "constant-unused"
    used = "    private static final byte[] IMAGE_USED = new byte[1];"
    assert sa.port_fact(PORT, {"line": 2, "before": used}) is None
    assert set(sa.port_fact(PORT, {"line": 22, "before": ""})) == {"result", "fact"}


@pytest.mark.parametrize("reason", [
    "handleLink(request, byte[] area) overload is never called by the equivalence test runner",
    "ca instanceof byte[] branch is unreachable because the harness passes a DTO, never raw byte[]",
    "the case has no scenario with a COMMAREA longer than the layout, so this stays unrun",
    "no scenario reaches this statement in the committed case for this program",
])  # fmt: skip
def test_unreachable_cannot_rest_on_what_the_tests_do(reason):
    assert any("about the program" in p for p in dm.reason_problems("unreachable", reason))


def test_a_reason_about_the_program_passes():
    reason = "p15 always throws Goback on its last line and no statement jumps to p16, so p16 never runs"
    assert dm.reason_problems("unreachable", reason) == []
    assert dm.reason_problems("equivalent", "WS-JUNK is never read: only its length bounds one copy") == []
    assert any("shorter" in p for p in dm.reason_problems("equivalent", "dead"))


def test_gaps_need_no_defence():
    assert dm.reason_problems("case-gap", "no scenario") == []
    assert dm.attempt_problems("case-gap", []) == []


def test_an_accounted_verdict_needs_an_attack_and_a_kill_wins():
    assert "no attack" in dm.attempt_problems("equivalent", [])[0]
    assert "no attack" in dm.attempt_problems("equivalent", [{"result": "refused"}, {"result": "stillborn"}])[0]
    assert dm.attempt_problems("equivalent", [{"result": "survived"}]) == []
    assert dm.attempt_problems("unreachable", [{"result": "no-entry-path"}]) == []
    assert "killed" in dm.attempt_problems("equivalent", [{"result": "survived"}, {"result": "killed"}])[0]
    assert "COBOL" in dm.attempt_problems("equivalent", [{"result": "survived"}, {"result": "port-differs"}])[0]


@pytest.mark.parametrize("base, mutant, want", [
    ({"verdict": "proven"}, {"verdict": "refuted"}, "killed"),
    ({"verdict": "proven"}, {"verdict": "timeout"}, "killed"),
    ({"verdict": "proven"}, {"verdict": "proven"}, "survived"),
    ({"verdict": "proven"}, {"verdict": "error"}, "refused"),
    ({"verdict": "refuted"}, {"verdict": "proven"}, "port-differs"),
    ({"verdict": "error"}, {"verdict": "proven"}, "refused"),
    ({"verdict": "timeout"}, {"verdict": "refuted"}, "refused"),
    ({"verdict": "refuted", "report": {"refused": {"X": "not modelled"}}}, {"verdict": "error"}, "refused"),
])  # fmt: skip
def test_the_attack_result(base, mutant, want):
    assert sa.judge(base, mutant) == want


def test_the_likeliest_wrong_verdicts_rank_first():
    plain = {"id": "b", "op": "CON", "before": "x = 0;", "verdict": "equivalent", "reason": "x" * 50, "tried": ["a"]}
    excuse = {**plain, "id": "a", "verdict": "unreachable", "reason": "never called by the test runner at all, ever"}
    resp = {**plain, "id": "c", "op": "DEL", "before": "ws.resp = run.respond();"}
    gap = {**plain, "id": "d", "verdict": "case-gap"}
    rows = sa.ranked({"z": [plain, excuse, resp, gap]})
    assert [r["id"] for r in rows] == ["a", "c"]


def test_attempts_accumulate(tmp_path):
    sa.add_attempts(tmp_path, {"m": {"result": "refused"}})
    sa.add_attempts(tmp_path, {"m": {"result": "survived"}, "n": {"result": "killed"}})
    assert [a["result"] for a in sa.load_attempts(tmp_path)["m"]] == ["refused", "survived"]
    assert json.loads((tmp_path / "attempts.json").read_text())["n"] == [{"result": "killed"}]


def _state_setup(monkeypatch, tmp_path):
    entry = {"survived": [S1], "counts": {"killed": 1, "survived": 1}, "inputs": {}, "program": "X", "chosen": 2,
             "mutants": 2, "seed": 0}  # fmt: skip
    monkeypatch.setattr(dm, "load", lambda path=dm.LEDGER: {"cbsa-abndproc": entry})
    written = {}
    monkeypatch.setattr(dm, "write_survivors", lambda case, entries, path=dm.SURVIVORS: written.update({case: entries}))
    monkeypatch.setattr(dm, "load_survivors", lambda path=dm.SURVIVORS: {})
    monkeypatch.setattr(dm, "write", lambda *a, **k: None)
    monkeypatch.setattr(dm, "stated", lambda case, survivors=None: {})
    return written


def test_state_refuses_a_verdict_with_no_attack(monkeypatch, tmp_path):
    written = _state_setup(monkeypatch, tmp_path)
    triage = {S1["id"]: {"verdict": "equivalent", "reason": "x is overwritten by the next MOVE before any read of it"}}
    with pytest.raises(SystemExit, match="no attack on record"):
        dm.state("cbsa-abndproc", triage)
    assert not written


def test_state_keeps_what_was_tried(monkeypatch, tmp_path):
    written = _state_setup(monkeypatch, tmp_path)
    triage = {S1["id"]: {"verdict": "equivalent", "reason": "x is overwritten by the next MOVE before any read of it"}}
    dm.state("cbsa-abndproc", triage, {S1["id"]: [{"result": "survived", "inputs": ["long-body", "empty"]}]})
    assert written["cbsa-abndproc"][0]["tried"] == ["empty", "long-body"]


def test_state_takes_a_gap_without_an_attack(monkeypatch, tmp_path):
    written = _state_setup(monkeypatch, tmp_path)
    dm.state("cbsa-abndproc", {S1["id"]: {"verdict": "case-gap", "reason": "a longer COMMAREA would kill it"}})
    assert written["cbsa-abndproc"][0]["verdict"] == "case-gap"
    assert "tried" not in written["cbsa-abndproc"][0]
