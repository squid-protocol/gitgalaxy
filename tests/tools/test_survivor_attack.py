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


def test_a_runtime_class_call_does_not_keep_a_method_alive():
    text = PORT.replace("        int x = 1;\n", "        Cobol.condition(1);\n        task.paragraph(2);\n")
    live = sa.live_methods(text)
    assert "condition" not in live  # Cobol.condition is the runtime's
    assert "paragraph" in live  # task.paragraph could be ours: an unsure call keeps it live


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


def test_a_change_cannot_narrow_a_run():
    full, sample = {"chosen": 455}, {"chosen": 149}
    assert "replaces one that judged 455" in dm.regressions("c", sample, [], full, [])[0]
    assert dm.regressions("c", full, [], sample, []) == []
    assert dm.regressions("c", full, [], None, []) == []


def test_a_new_verdict_needs_its_attack_but_a_carried_one_does_not():
    old = {"id": "a", "before": "x", "after": "y", "verdict": "equivalent"}
    assert dm.regressions("c", None, [{**old, "id": "b"}], None, [old]) == []  # the same mutant, a new id
    new = {"id": "n", "before": "p", "after": "q", "verdict": "unreachable"}
    assert "1 new verdicts" in dm.regressions("c", None, [old, new], None, [old])[0]
    assert dm.regressions("c", None, [old, {**new, "tried": ["long-body"]}], None, [old]) == []
    assert dm.regressions("c", None, [old, {**new, "verdict": "case-gap"}], None, [old]) == []


# ---- what the COBOL settles (branch_solver.py, #4175): the verdicts are data here, no z3 ----------------------------
VERDICTS = {
    "POPULATE-TIME-DATE": "confirmed",
    "PTD010": "confirmed",
    "GET-ME-OUT-OF-HERE": "witness",
    "A010": "witness",
}


def test_a_reason_names_paragraphs_as_whole_words_in_a_negated_clause():
    reason = "POPULATE-TIME-DATE is never PERFORMed (PTD010 neither): the program runs A010 -> GET-ME-OUT-OF-HERE"
    assert sa.named_paragraphs(reason, VERDICTS) == ["POPULATE-TIME-DATE"]
    assert sa.named_paragraphs("PTD010 is not reached either", VERDICTS) == ["PTD010"]
    assert sa.named_paragraphs("POPULATE-TIME-DATE-X is not PERFORMed", VERDICTS) == []
    assert sa.named_paragraphs("used only where no paragraph PERFORMs it (the flow is A010)", VERDICTS) == []


def test_the_solver_settles_an_unreachable_paragraph_and_questions_an_entered_one():
    never = {"verdict": "unreachable", "reason": "POPULATE-TIME-DATE is never PERFORMed: it follows GET-ME-OUT-OF-HERE"}
    assert sa.solver_fact(never, VERDICTS)["result"] == "solver-unreachable"
    wrong = {"verdict": "unreachable", "reason": "GET-ME-OUT-OF-HERE is never reached"}
    assert sa.solver_fact(wrong, VERDICTS)["result"] == "solver-entered"
    assert sa.solver_fact({"verdict": "equivalent", "reason": never["reason"]}, VERDICTS) is None
    assert sa.solver_fact({"verdict": "unreachable", "reason": "no paragraph named here"}, VERDICTS) is None


def test_state_takes_a_solver_settlement_but_not_a_solver_question():
    assert dm.attempt_problems("unreachable", [{"result": "solver-unreachable"}]) == []
    assert "no attack" in dm.attempt_problems("unreachable", [{"result": "solver-entered"}])[0]


# ---- Field declarations no reachable statement uses (branch_solver.py fields, #4175) ----------------------------------
def test_a_field_declaration_names_its_item_and_record():
    assert sa.field_of("private final Field f84_WS_U_TIME = Field.packed(s_WS_U_TIME, 0, 15, 0, true);") == (
        "WS-U-TIME",
        "WS-U-TIME",
    )
    assert sa.field_of("private final Field f69_TITLE01L = Field.binary(s_COADM1AI, 23, 4, 0, true, false);") == (
        "TITLE01L",
        "COADM1AI",
    )
    assert sa.field_of("if (task.exactCommarea()) {") is None


def test_an_unread_item_settles_its_field_mutants_only():
    unread = {("COADM1AI", "TITLE01L")}
    hit = {"before": "private final Field f69_TITLE01L = Field.binary(s_COADM1AI, 23, 4, 0, true, false);"}
    other = {"before": "private final Field f70_TITLE02L = Field.binary(s_COADM1AI, 27, 4, 0, true, false);"}
    assert sa.unread_fact(hit, unread)["result"] == "solver-unread"
    assert sa.unread_fact(other, unread) is None
    assert dm.attempt_problems("equivalent", [{"result": "solver-unread"}]) == []


def test_the_solver_finds_an_item_no_reachable_statement_uses(tmp_path):
    pytest.importorskip("z3")
    pytest.importorskip("tree_sitter_language_pack")
    import branch_solver as bs

    src = tmp_path / "T.cbl"
    src.write_text(
        "\n".join(
            [
                "       IDENTIFICATION DIVISION.",
                "       PROGRAM-ID. T.",
                "       DATA DIVISION.",
                "       WORKING-STORAGE SECTION.",
                "       01 W-USED PIC X VALUE 'A'.",
                "       01 W-DEAD PIC X VALUE 'B'.",
                "       01 W-NEVER PIC X VALUE 'C'.",
                "       PROCEDURE DIVISION.",
                "       A000.",
                "           DISPLAY W-USED",
                "           GOBACK.",
                "       B000.",
                "           DISPLAY W-DEAD.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    got = bs.unread_items(bs.load_program(src, []), {})
    assert {x["item"] for x in got["unread"]} == {"W-DEAD", "W-NEVER"}


def test_dfhaid_counts_as_used_by_the_runtime():
    import branch_solver as bs

    assert "DFHAID" in bs.RUNTIME_RECORDS and "DFHEIBLK" in bs.RUNTIME_RECORDS


def test_try_takes_a_sibling_base_and_refuses_another_corpus(monkeypatch, tmp_path):
    import equivalence as eq

    cases = {"c": {"corpus": "x", "kind": "cics"}, "c-linked": {"corpus": "x", "kind": "cics", "linked": True},
             "other": {"corpus": "y", "kind": "cics"}}  # fmt: skip
    monkeypatch.setattr(eq, "load_case", lambda n: cases[n])
    inputs = tmp_path / "i.json"
    inputs.write_text("[]", encoding="utf-8")
    with pytest.raises(SystemExit, match="not a sibling"):
        sa.attack("c", ["x"], inputs, tmp_path, 1, 1, "other")
