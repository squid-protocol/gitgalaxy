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
    # the committed port not compiling is the box (a JDK 21 shell), not a finding; a crash on the new input is one
    ({"verdict": "refuted", "report": {"java_failed": True, "feedback": "maven-compiler-plugin: error: release "
                                       "version 17 not supported"}}, {"verdict": "error"}, "refused"),
    ({"verdict": "refuted", "report": {"java_failed": True, "feedback": "java.lang.ArithmeticException at p3"}},
     {"verdict": "error"}, "port-differs"),
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


# ---- batch `try` (owner 2026-11-07: CBSTM03A, PAUDBLOD, PAUDBUNL, COBSWAIT had no attack at all) ------------------
LAYOUT = [{"name": "ACCT", "pic": "9(5)", "usage": None, "offset": 0, "bytes": 5},
          {"name": "NAME", "pic": "X(5)", "usage": None, "offset": 5, "bytes": 5}]  # fmt: skip


def _batch_case(tmp_path, monkeypatch):
    import strengthen as st

    (tmp_path / "in.txt").write_text("00001ALICE\n00002BOB\n", encoding="latin-1")
    monkeypatch.setattr(st, "input_layout", lambda case, corpus, dd: LAYOUT if dd == "IN" else None)
    return {"name": "b", "program": "P", "sysin": "OLD", "parm": None,
            "datasets": {"IN": {"input": "in.txt", "reclen": 10, "organization": "indexed",
                                "keys": [{"offset": 0, "length": 5}]},
                         "GEN": {"input": "@generate", "reclen": 10,
                                 "generate": {"records": 3, "fields": {"A": {"values": [1]}, "B": {"values": [2]}}}},
                         "OUT": {"organization": "sequential", "reclen": 10, "compare": True}},
            "faults": [{"name": "old", "plan": [{"dd": "IN", "op": "OPEN", "nth": 1, "status": "30"}]}]}  # fmt: skip


def test_a_batch_trial_is_the_committed_step_with_the_inputs_changes(tmp_path, monkeypatch):
    case = _batch_case(tmp_path, monkeypatch)
    trial = sa.batch_trial(case, tmp_path, [
        {"name": "high-acct", "dataset": "IN", "based_on": 1, "set": {"ACCT": 99999}},
        {"name": "gen-zero", "generate": {"GEN": {"fields": {"A": {"values": [0]}}, "records": 5}}},
        {"name": "sysin-blank", "sysin": ""},
        {"name": "out-write", "fault": {"plan": [{"dd": "OUT", "op": "WRITE", "nth": 1, "status": "34"}]}},
    ], tmp_path / "work")  # fmt: skip
    lines = Path(trial["datasets"]["IN"]["input"]).read_text(encoding="latin-1").split()
    assert lines == ["00001ALICE", "00002BOB", "99999ALICE"]  # the committed records stay, the new one is appended
    assert trial["datasets"]["GEN"]["generate"] == {
        "records": 5,
        "fields": {"A": {"values": [0]}, "B": {"values": [2]}},
    }
    assert trial["sysin"] == "" and trial["parm"] is None
    assert [f["name"] for f in trial["faults"]] == ["out-write"]  # only the proposed fault runs
    assert case["sysin"] == "OLD" and case["datasets"]["GEN"]["generate"]["records"] == 3  # the case is untouched


@pytest.mark.parametrize("inputs, why", [
    ([], "at least one input"),
    ([{"name": "Bad Name", "sysin": ""}], "kebab-case"),
    ([{"name": "a", "sysin": "", "parm": ""}], "exactly one of"),
    ([{"name": "a", "sysin": ""}, {"name": "a", "parm": ""}], "named twice"),
    ([{"name": "a", "sysin": ""}, {"name": "b", "sysin": "x"}], "one `sysin` per try"),
    ([{"name": "a", "generate": {"IN": {"fields": {}}}}], "not a `@generate` dataset"),
    ([{"name": "a", "generate": {"GEN": {"seed": 1}}}], "only `fields` and `records`"),
    ([{"name": "a", "fault": {"plan": []}}], "`fault` is"),
    ([{"name": "a", "dataset": "IN", "based_on": 1, "set": {"ACCT": 1}}], "already a record's"),
    ([{"name": "a", "dataset": "IN", "based_on": 1, "set": {"ACCT": 7}},
      {"name": "b", "dataset": "IN", "based_on": 2, "set": {"ACCT": 7}}], "same key"),
    ([{"name": "a", "dataset": "GEN", "based_on": 1, "set": {}}], "not an input with a known layout"),
])  # fmt: skip
def test_a_malformed_batch_input_is_refused_by_name(tmp_path, monkeypatch, inputs, why):
    with pytest.raises(SystemExit, match=why):
        sa.batch_trial(_batch_case(tmp_path, monkeypatch), tmp_path, inputs, tmp_path / "work")


def test_try_runs_a_batch_case_with_its_fault_runs_only_when_proposed(tmp_path, monkeypatch):
    import equivalence as eq
    import mainframe_corpus as mc
    import mutation as mu

    case = _batch_case(tmp_path, monkeypatch)
    monkeypatch.setattr(eq, "load_case", lambda n: {**case, "corpus": "x"})
    monkeypatch.setattr(mc, "select", lambda names: [object()])
    monkeypatch.setattr(mc, "require_clone", lambda entry: tmp_path)
    monkeypatch.setattr(sa, "det_port", lambda c, w: tmp_path / "port")
    monkeypatch.setattr(sa, "find_mutants", lambda c, p, ids: {})
    seen = []
    monkeypatch.setattr(mu, "prove", lambda c, port, d, t, flags: seen.append(flags) or {"verdict": "error"})
    for inputs, faults in (([{"name": "s", "sysin": "X"}], "none"),
                           ([{"name": "f", "fault": {"plan": [{"dd": "IN", "op": "READ"}]}}], "all")):  # fmt: skip
        f = tmp_path / "i.json"
        f.write_text(json.dumps(inputs), encoding="utf-8")
        sa.attack("b", [], f, tmp_path / f"w-{faults}", 1)
        flags = seen[-1]
        assert flags[flags.index("--faults") + 1] == faults
        written = json.loads(Path(flags[flags.index("--case-file") + 1]).read_text(encoding="utf-8"))
        assert [x["name"] for x in written["faults"]] == ([] if faults == "none" else ["f"])


# ---- reasons copied in bulk, and "unexercised" against the coverage (owner 2026-11-07, after #7981) --------------
FULL = "proven on 14 runs, covering 25/25 paragraphs and 43/46 branches"


def _gap(i, line, reason, **kw):
    return {"id": i, "op": "DEL", "line": line, "before": f"b{i}", "after": f"a{i}", "verdict": "case-gap",
            "reason": reason, **kw}  # fmt: skip


def test_a_template_keeps_names_and_drops_numbers_quotes_and_calls():
    a = "Execution path in paragraph or method p0() at line 1125: condition 'Cobol.move(x' is unexercised"
    b = "Execution path in paragraph or method p3() at line 7: condition 'f33 = y' is unexercised"
    assert dm.reason_template(a) == dm.reason_template(b)
    assert dm.reason_template("ABNDPROC's WS-A is moved") != dm.reason_template("ABNDPROC's WS-B is moved")


def test_one_reason_on_many_lines_is_refused_unless_attacked():
    many = [_gap(f"m{n}", n, f"Field declaration at line {n}: field variation is unexercised") for n in range(11)]
    assert "11 survivors on 11 lines" in dm.template_problems("c", many)[0]
    assert dm.template_problems("c", many[:10]) == []  # TEMPLATE_MAX lines
    one_line = [_gap(f"o{n}", 5, "every operator on line 5 changes the same unread pad") for n in range(30)]
    assert dm.template_problems("c", one_line) == []  # mutants of one line may share a fact
    assert dm.template_problems("c", [{**e, "tried": ["solver-unread"]} for e in many]) == []
    assert dm.template_problems("c", [{**e, "tried": ["high-acct"]} for e in many]) == []
    assert dm.template_problems("c", many, only={"elsewhere"}) == []
    assert dm.template_problems("c", many, only={"m3"})


def test_a_gap_that_says_covered_code_does_not_run_is_refused():
    said = "condition 'x' is unexercised by current test input scenarios"
    assert dm.reason_problems("case-gap", said, FULL)
    assert not dm.reason_problems("case-gap", said, "proven on 2 runs, covering 24/25 paragraphs")
    assert not dm.reason_problems("case-gap", "the false branch of IF X is not exercised", FULL)  # 3 branches left
    every = "proven on 2 runs, covering 25/25 paragraphs and 46/46 branches"
    assert dm.reason_problems("case-gap", "the false branch of IF X is not exercised", every)
    assert not dm.reason_problems("case-gap", "the record count is not compared by the proof", FULL)
    # code after a transfer runs in no input although its paragraph does: an accounted verdict answers to its attack
    assert not dm.reason_problems(
        "unreachable", "the MOVE after EXEC CICS RETURN in P0 is never reached by any input", FULL
    )


def test_a_change_that_writes_bulk_reasons_is_refused_and_a_carried_one_is_not():
    entry = {"chosen": 9, "coverage": FULL}
    old = [_gap(f"m{n}", n, f"Execution path at line {n}: condition 'q' is unexercised") for n in range(12)]
    out = dm.regressions("c", entry, old, entry, [])
    assert any("12 survivors on 12 lines" in p for p in out)
    assert any("12 new reasons say the code does not run" in p for p in out)
    assert dm.regressions("c", entry, old, entry, old) == []  # the same words carried: main's, not this change's
    names = "ACCT CUST ADDR CITY ZIP PHONE LIMIT BAL DATE TYPE CODE NOTE".split()
    ok = [
        _gap(f"m{n}", n, f"WS-{x} reaches the report line, which the proof does not compare")
        for n, x in enumerate(names)
    ]
    assert dm.regressions("c", entry, ok, entry, []) == []


def test_state_refuses_a_bulk_reason_and_keeps_the_attack_a_gap_stays_open_after(monkeypatch, tmp_path):
    written = _state_setup(monkeypatch, tmp_path)
    many = [{**S1, "id": f"m{n}", "line": n} for n in range(11)]
    monkeypatch.setattr(dm, "load", lambda path=dm.LEDGER: {"cbsa-abndproc": {
        "survived": many, "counts": {"killed": 1, "survived": 11}, "inputs": {}, "program": "X", "chosen": 12,
        "mutants": 12, "seed": 0}})  # fmt: skip
    triage = {e["id"]: {"verdict": "case-gap", "reason": f"line {e['line']}: an input the case lacks"} for e in many}
    with pytest.raises(SystemExit, match="11 survivors on 11 lines"):
        dm.state("cbsa-abndproc", triage)
    attempts = {e["id"]: [{"result": "survived", "inputs": ["long-body"]}] for e in many}
    dm.state("cbsa-abndproc", triage, attempts)
    assert {e["id"]: e.get("tried") for e in written["cbsa-abndproc"]} == {e["id"]: ["long-body"] for e in many}
