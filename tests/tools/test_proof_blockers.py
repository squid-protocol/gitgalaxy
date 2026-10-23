"""proof_blockers: the proof-level ranking over the programs a survey translates WHOLE -- which proof subject runs
each, the verdict sources (sweep, det_sweep_baseline, CI's ratchet, Db2), coverage, runtime facts, and the ranking.
Fixture cases / crucible / corpora under tmp_path; no corpus, translator or sweep needed."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import proof_blockers as pb


def fixed(*code: str) -> str:
    return "\n".join(f"{i * 100:06d} {c}" for i, c in enumerate(code, 1)) + "\n"


CICS = fixed("PROCEDURE DIVISION.", "    EXEC CICS RETURN END-EXEC.")
TASKN = fixed("PROCEDURE DIVISION.", "    MOVE EIBTASKN TO WS-T", "    MOVE EIBRCODE TO WS-R",
              "    EXEC CICS RETURN END-EXEC.")  # fmt: skip
ASSIGN = fixed("PROCEDURE DIVISION.", "    EXEC CICS ASSIGN APPLID(A) USERID(U) END-EXEC.")
BATCH = fixed("PROCEDURE DIVISION.", "    DISPLAY 'HI'", "    STOP RUN.")


def write(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data))
    return path


def case(cases: Path, name: str, corpus: str, prog: str, **extra) -> None:
    write(cases / name / "case.json", {"corpus": corpus, "program": Path(prog).stem.upper(), "program_source": prog,
                                       **extra})  # fmt: skip


def evidence(cases: Path, name: str, covered: int, live: int, bc: int = 1, bt: int = 1) -> None:
    write(cases / name / "evidence.json", {"coverage": {"paragraphs": {"covered": covered, "live": live},
                                                        "branches": {"covered": bc, "total": bt}}})  # fmt: skip


def whole(prog: str) -> dict:
    return {"program": prog, "statements": 5, "translated": 5, "holes": []}


def setup(tmp_path: Path):
    cases, corpora, cru = tmp_path / "cases", tmp_path / "corpora", tmp_path / "crucible"
    files = {"a/PROVEN.cbl": CICS, "a/NOCASE.cbl": CICS, "a/DB2.cbl": CICS, "a/KNOWN.cbl": CICS, "a/COV.cbl": CICS,
             "a/TASKN.cbl": TASKN, "a/ASSIGN.cbl": ASSIGN, "a/BATCH.cbl": BATCH, "a/HOLEY.cbl": CICS,
             "a/LINKED.cbl": CICS, "a/DIFF.cbl": CICS}  # fmt: skip
    for rel, text in files.items():
        write(corpora / "estate" / rel, text)
    case(
        cases, "c-proven", "estate", "a/PROVEN.cbl", programs=[{"program": "LINKED", "program_source": "a/LINKED.cbl"}]
    )
    evidence(cases, "c-proven", 3, 3)
    case(cases, "c-db2", "estate", "a/DB2.cbl", db2={})
    case(cases, "c-known", "estate", "a/KNOWN.cbl")
    case(cases, "c-cov", "estate", "a/COV.cbl")
    evidence(cases, "c-cov", 2, 3, 1, 4)
    case(cases, "c-taskn", "estate", "a/TASKN.cbl")
    evidence(cases, "c-taskn", 1, 1)
    case(cases, "c-assign", "estate", "a/ASSIGN.cbl")
    evidence(cases, "c-assign", 1, 1)
    case(cases, "c-diff", "estate", "a/DIFF.cbl")
    det_baseline = {"c-known": {"issue": "#1", "why": "a known cause"}}
    rows = {("estate", p): whole(p) for p in files}
    rows[("estate", "a/HOLEY.cbl")] = {"program": "a/HOLEY.cbl", "statements": 5, "translated": 4, "holes": ["x"]}
    return cases, corpora, cru, det_baseline, rows


def run(tmp_path, **kw):
    cases, corpora, cru, det_baseline, rows = setup(tmp_path)
    return pb.proof_blockers(rows, [corpora], cases_dir=cases, crucible_dir=cru, det_baseline=det_baseline, **kw)


def gaps_of(res, stem):
    return next(p["gaps"] for p in res["programs"] if Path(p["program"]).stem == stem)


def test_each_gap_class_from_its_source(tmp_path):
    res = run(tmp_path)
    assert gaps_of(res, "PROVEN") == [] and gaps_of(res, "LINKED") == [
        pb.LINKED_NOT_MEASURED
    ]  # run by the case, but its own coverage is not measured (#4270)
    assert gaps_of(res, "NOCASE") == ["no case"]
    assert gaps_of(res, "DB2") == ["not proven in CI: Db2 case (no sweep row, no readable det-sweep ledger entry)"]
    assert gaps_of(res, "KNOWN") == ["known unproven: #1"]
    assert gaps_of(res, "COV") == ["coverage: live paragraphs no scenario runs"]
    assert gaps_of(res, "TASKN") == ["fact: EIBRCODE (no harness states it)"]  # EIBTASKN: the case states it
    assert gaps_of(res, "ASSIGN") == ["fact: ASSIGN APPLID/SYSID (the case states no region)",
                                      "fact: ASSIGN USERID (no equivalence case states it)"]  # fmt: skip
    assert gaps_of(res, "DIFF") == ["coverage: unknown (no sweep, no evidence record)"]
    stems = {Path(p["program"]).stem for p in res["programs"]}
    assert "BATCH" not in stems and "HOLEY" not in stems  # not CICS / not whole
    assert res["not_cics"] == 1
    assert (res["whole"], res["proven"]) == (9, 1)


def test_branches_and_all_programs(tmp_path):
    res = run(tmp_path, branches=True, only_cics=False)
    assert "coverage: branch outcomes no scenario runs" in gaps_of(res, "COV")
    assert gaps_of(res, "BATCH") == ["no case"]


def test_a_sweep_overrides_the_ratchet_and_names_the_diff(tmp_path):
    sweep = tmp_path / "sweep"
    write(sweep / "sweep.json", {"det": {
        "c-diff": {"proved": False, "coverage": "not proven; 3 scenarios cover 3/3 paragraphs and 1/2 branches"},
        "c-db2": {"proved": True, "coverage": "proven on 3 scenarios, covering 3/3 paragraphs and 2/2 branches",
                  "translated": "5/5"},
        "c-known": {"proved": False, "coverage": ""},
    }})  # fmt: skip
    write(sweep / "det" / "c-diff" / "proof" / "report.json", {"outputs": {"s1": {"diffs": [
        {"event": 3, "kind": "RETURN", "fields": [{"field": "commarea.X-Y", "cobol": 1, "java": 2}]}]}}})  # fmt: skip
    res = run(tmp_path, sweeps=pb.load_sweeps([sweep]))
    assert gaps_of(res, "DIFF") == ["scenario differs: RETURN commarea"]
    assert gaps_of(res, "DB2") == []
    assert gaps_of(res, "KNOWN") == ["known unproven: #1"]
    known = next(p for p in res["programs"] if p["program"].endswith("KNOWN.cbl"))
    assert "a known cause" in known["detail"]["known unproven: #1"]


def test_a_case_cobc_does_not_compile_is_a_gap_with_its_diagnostic_and_a_fix(tmp_path):
    """#4493: `cobol_compile_failed` (recorded by the proof) outranks "scenario differs"; the fix names the diagnostic."""
    import harness_report as hr

    sweep = tmp_path / "sweep"
    err = "a/DIFF.cbl:9: warning: x\na/DIFF.cbl:12: error: 'FOO' is not defined\n\n"
    write(sweep / "sweep.json", {"det": {
        "c-diff": {"proved": False, "cobol_compile_failed": True, "cobc_stderr": err, "coverage": ""},
        "c-known": {"proved": False, "coverage": ""},
    }})  # fmt: skip
    res = run(tmp_path, sweeps=pb.load_sweeps([sweep]))
    assert gaps_of(res, "DIFF") == [pb.COBC_NO_COMPILE]  # no "scenario differs", no coverage gap read off a dead run
    diff = next(p for p in res["programs"] if p["program"].endswith("DIFF.cbl"))
    assert diff["detail"][pb.COBC_NO_COMPILE] == "a/DIFF.cbl:12: error: 'FOO' is not defined"
    assert gaps_of(res, "KNOWN") == ["known unproven: #1"]  # a sibling row without the flag is unchanged
    assert pb.last_line("") == "" and pb.last_line(None) == ""
    fix = hr.fix_for(pb.COBC_NO_COMPILE, ["DIFF"], ["c-diff"], [diff["detail"][pb.COBC_NO_COMPILE]])
    assert "compile under cobc" in fix and "'FOO' is not defined" in fix and "c-diff" in fix
    assert hr.gap_status(pb.COBC_NO_COMPILE) == hr.COULDNT_RUN
    assert "no diagnostic recorded" in hr.fix_for(pb.COBC_NO_COMPILE, ["DIFF"], ["c-diff"], [])


def test_the_case_with_fewest_gaps_speaks_for_a_program(tmp_path):
    cases, corpora, cru, det_baseline, rows = setup(tmp_path)
    case(cases, "c-cov-2", "estate", "a/COV.cbl")
    evidence(cases, "c-cov-2", 3, 3)
    res = pb.proof_blockers(rows, [corpora], cases_dir=cases, crucible_dir=cru, det_baseline=det_baseline)
    cov = next(p for p in res["programs"] if p["program"].endswith("COV.cbl"))
    assert cov["gaps"] == [] and cov["case"] == "c-cov-2"


def test_crucible_programs_rank_apart(tmp_path):
    cases, corpora, cru, det_baseline, rows = setup(tmp_path)
    write(cru / "baseline.json", {"cells": {
        "k-fail/s1/java-ported": {"status": "fail", "reason": "task 1 (T1) event 2: WRITEQ-TS expected, got RETURN"},
        "k-noport/s1/java-ported": {"status": "fail", "reason": "no port of any of its programs"}}})  # fmt: skip
    write(cru / "coverage.json", {"programs": {
        "k-ok/OKP": {"live": 1, "scenarios": {"s1": {"units": ["MAIN"]}}},
        "k-fail/FAILP": {"live": 1, "scenarios": {"s1": {"units": ["MAIN"]}}},
        "k-noport/NOP": {"live": 1, "scenarios": {}}}})  # fmt: skip
    for c, p in (("k-ok", "OKP"), ("k-fail", "FAILP")):
        (cru / "ports" / c / p).mkdir(parents=True)
    for c, p in (("k-ok", "OKP"), ("k-fail", "FAILP"), ("k-noport", "NOP")):
        rel = f"cases/trap/{c}/src/{p}.cbl"
        write(corpora / "cics-crucible" / rel, CICS)
        rows[("cics-crucible", rel)] = whole(rel)
    res = pb.proof_blockers(rows, [corpora], cases_dir=cases, crucible_dir=cru, det_baseline=det_baseline)
    assert res["whole"] == 9  # the estates' count is unchanged
    assert (res["crucible"]["whole"], res["crucible"]["proven"]) == (3, 1)
    assert gaps_of(res, "NOP") == ["no det port (crucible)"]
    assert gaps_of(res, "FAILP")[0].startswith("scenario differs: WRITEQ-TS expected")


def test_rank_counts_only_and_one_away_split_burned():
    progs = {("CardDemo", "A"): (True, {"g1"}), ("x", "B"): (False, {"g1"}), ("x", "C"): (False, {"g1", "g2"}),
             ("x", "D"): (False, set())}  # fmt: skip
    r = pb.rank(progs)
    g1 = next(g for g in r["gaps"] if g["gap"] == "g1")
    assert (g1["only"], g1["only_burned"], g1["only_non_burned"], g1["one_away"], g1["touched"]) == (2, 1, 1, 1, 3)
    assert (r["whole"], r["proven"], r["proven_non_burned"]) == (4, 1, 1)


def test_eibtaskn_is_stated_by_an_equivalence_case_not_yet_by_the_crucible():
    """#4270: EIBTASKN is a stated fact of the run (gitgalaxy.standards.cics.eib, $GGCICS_TASKN /
    CicsTask.withTaskNumber): the equivalence harness states it for every task, so neither a case nor a program with
    no case yet has the gap; the crucible runner does not state it, so a crucible case's program keeps it."""
    assert "EIBTASKN" in pb.CASE_STATED_EIB and "EIBRCODE" not in pb.CASE_STATED_EIB
    # #5126 (X64): an equivalence case states EIBDS, a crucible cell does not
    assert "EIBDS" in pb.CASE_STATED_EIB and "EIBDS" not in pb.STATED_EIB
    # the other EIB resource fields stay open, refused by name (X64)
    assert not {"EIBFN", "EIBRCODE", "EIBCPOSN", "EIBREQID", "EIBRSRCE", "EIBERR", "EIBERRCD"} & pb.CASE_STATED_EIB
    facts = {"eib": {"EIBTASKN"}}
    assert pb.fact_gaps(facts, pb.Run("equivalence", "c")) == set()
    assert pb.fact_gaps(facts, None) == set()
    assert pb.fact_gaps(facts, pb.Run("crucible", "k")) == {"fact: EIBTASKN (no harness states it)"}
    assert pb.fact_gaps({"eib": {"EIBRCODE"}}, pb.Run("equivalence", "c")) == {"fact: EIBRCODE (no harness states it)"}


def test_eib_names_match_whole_words_outside_literals_and_comments():
    """#5077: the whole input class of a name that is not a read -- a literal's text, a hyphenated or underscored
    user name that starts with an EIB field, a comment line, a VALUE clause -- against the real reads."""
    for src in (
        fixed("    01  MSG PIC X(8) VALUE 'EIBFN: '.", '    DISPLAY "EIBRCODE=".'),
        fixed("    01  EIBRCODE-NICE PIC X.", "    MOVE 1 TO EIBFN-X", "    MOVE 1 TO WS-EIBFN"),
        fixed("    01  EIBFN_COPY PIC X."),
        "000100*    MOVE EIBFN TO X\n000200/   MOVE EIBRCODE TO X\n",
    ):
        assert pb.facts_needed(src)["eib"] == set(), src
    real = fixed("    MOVE EIBFN TO A", "    MOVE EIBRCODE TO B", "    IF EIBERR = 1 DISPLAY 'EIBDS'.",
                 "    MOVE EIBRCODE(1:1) TO C", "    MOVE 'EIBAID' TO D")  # fmt: skip
    assert pb.facts_needed(real)["eib"] == {"EIBFN", "EIBRCODE", "EIBERR"}
    assert pb.facts_needed(fixed("    MOVE 'A' TO X EIBDS."))["eib"] == {"EIBDS"}


def test_assign_options_inside_a_literal_or_comment_are_no_fact_read():
    """#5089: the fact scan skips string literals for every keyword, not just EIB fields: an ASSIGN written inside a
    literal (a message, a generated-command template) or a comment line is no read of USERID / STARTCODE / APPLID."""
    for src in (
        fixed("    MOVE 'EXEC CICS ASSIGN APPLID(A) USERID(U) END-EXEC' TO X"),
        fixed('    DISPLAY "EXEC CICS ASSIGN STARTCODE(S) END-EXEC"'),
        "000100*    EXEC CICS ASSIGN APPLID(A) USERID(U) END-EXEC\n",
    ):
        assert pb.facts_needed(src) == {"eib": set(), "assign_task": set(), "assign_region": set()}, src
    real = fixed("    MOVE 'EXEC CICS ASSIGN APPLID(A) END-EXEC' TO X", "    EXEC CICS ASSIGN USERID(U) END-EXEC.")
    assert pb.facts_needed(real)["assign_task"] == {"USERID"} and not pb.facts_needed(real)["assign_region"]


def test_a_case_that_states_startcode_drops_the_gap(tmp_path):
    """#5077: STARTCODE is stated by a case's (or every scenario's) "startcode"; a case that leaves one scenario
    without it, or states none, keeps the gap. USERID stays a gap either way."""
    cases = tmp_path / "cases"
    sc = {"name": "a"}, {"name": "b"}
    case(cases, "top", "k", "src/t.cbl", startcode="TD", scenarios=list(sc))
    case(cases, "each", "k", "src/e.cbl", scenarios=[{**x, "startcode": "S"} for x in sc])
    case(cases, "part", "k", "src/p.cbl", scenarios=[{"name": "a", "startcode": "TD"}, {"name": "b"}])
    case(cases, "none", "k", "src/n.cbl", scenarios=list(sc))
    case(cases, "noscen", "k", "src/s.cbl", startcode="TD")
    runs = pb.equivalence_runs(cases)
    stated = {c: runs[("k", f"src/{f}.cbl")][0].startcode for c, f in
              (("top", "t"), ("each", "e"), ("part", "p"), ("none", "n"), ("noscen", "s"))}  # fmt: skip
    assert stated == {"top": True, "each": True, "part": False, "none": False, "noscen": False}
    facts = {"eib": set(), "assign_task": {"STARTCODE", "USERID"}, "assign_region": set()}
    assert pb.fact_gaps(facts, pb.Run("equivalence", "c", startcode=True)) == {
        "fact: ASSIGN USERID (no equivalence case states it)"
    }
    assert pb.fact_gaps(facts, pb.Run("equivalence", "c")) == {
        "fact: ASSIGN USERID (no equivalence case states it)",
        "fact: ASSIGN STARTCODE (no equivalence case states it)",
    }
    assert pb.fact_gaps(facts, pb.Run("crucible", "k", startcode=True)) == set()  # the runner states both


def test_a_case_that_states_a_terminal_drops_the_facility_gap(tmp_path):
    """#5126: ASSIGN FACILITY / TERMCHK are stated by a case's (or every scenario's) "termid" (GGCICS_FACILITY on the
    stub, CicsTask.withTermid on the port); one scenario without it, an empty one, or none keeps the gap. USERID and
    SCRNHT / SCRNWD stay gaps: the harness states neither."""
    cases = tmp_path / "cases"
    sc = {"name": "a"}, {"name": "b"}
    case(cases, "top", "k", "src/t.cbl", termid="T001", scenarios=list(sc))
    case(cases, "each", "k", "src/e.cbl", scenarios=[{**x, "termid": "T002"} for x in sc])
    case(cases, "part", "k", "src/p.cbl", scenarios=[{"name": "a", "termid": "T001"}, {"name": "b"}])
    case(cases, "empty", "k", "src/m.cbl", scenarios=[{"name": "a", "termid": ""}])
    case(cases, "none", "k", "src/n.cbl", scenarios=list(sc))
    case(cases, "noscen", "k", "src/s.cbl", termid="T001")
    runs = pb.equivalence_runs(cases)
    stated = {c: runs[("k", f"src/{f}.cbl")][0].termid for c, f in
              (("top", "t"), ("each", "e"), ("part", "p"), ("empty", "m"), ("none", "n"), ("noscen", "s"))}  # fmt: skip
    assert stated == {"top": True, "each": True, "part": False, "empty": False, "none": False, "noscen": False}
    facts = {"eib": set(), "assign_task": {"FACILITY", "USERID", "SCRNHT/SCRNWD"}, "assign_region": set()}
    userid, screen = ("fact: ASSIGN USERID (no equivalence case states it)",
                      "fact: ASSIGN SCRNHT/SCRNWD (no equivalence case states it)")  # fmt: skip
    assert pb.fact_gaps(facts, pb.Run("equivalence", "c", termid=True)) == {userid, screen}
    assert pb.fact_gaps(facts, pb.Run("equivalence", "c")) == {
        userid,
        screen,
        "fact: ASSIGN FACILITY (no equivalence case states it)",
    }
    assert (
        pb.fact_gaps(
            {"eib": set(), "assign_task": {"FACILITY"}, "assign_region": set()}, pb.Run("equivalence", "c", termid=True)
        )
        == set()
    )
    assert pb.fact_gaps(facts, pb.Run("crucible", "k")) == set()  # the runner states all of them


def test_a_case_that_states_userid_or_screen_drops_that_gap(tmp_path):
    """#5126: ASSIGN USERID is stated by a "userid" (GGCICS_USERID / withUserid), SCRNHT / SCRNWD by a "screen" of a
    stated "termid" (GGCICS_SCREEN / withScreen); one scenario short, an empty value, or a screen with no termid
    keeps the gap."""
    cases = tmp_path / "cases"
    sc = {"name": "a"}, {"name": "b"}
    case(cases, "top", "k", "src/t.cbl", termid="T1", userid="U", screen=[24, 80], scenarios=list(sc))
    case(
        cases,
        "each",
        "k",
        "src/e.cbl",
        scenarios=[{**x, "termid": "T1", "userid": "U", "screen": [24, 80]} for x in sc],
    )
    case(
        cases,
        "part",
        "k",
        "src/p.cbl",
        termid="T1",
        scenarios=[{"name": "a", "userid": "U", "screen": [1, 2]}, {"name": "b"}],
    )
    case(cases, "noterm", "k", "src/n.cbl", userid="U", screen=[24, 80], scenarios=list(sc))
    case(cases, "empty", "k", "src/m.cbl", termid="T1", userid="", scenarios=list(sc))
    runs = pb.equivalence_runs(cases)
    got = {c: (runs[("k", f"src/{f}.cbl")][0].userid, runs[("k", f"src/{f}.cbl")][0].screen) for c, f in
           (("top", "t"), ("each", "e"), ("part", "p"), ("noterm", "n"), ("empty", "m"))}  # fmt: skip
    assert got == {"top": (True, True), "each": (True, True), "part": (False, False), "noterm": (True, False),
                   "empty": (False, False)}  # fmt: skip
    facts = {"eib": set(), "assign_task": {"USERID", "SCRNHT/SCRNWD"}, "assign_region": set()}
    userid, screen = ("fact: ASSIGN USERID (no equivalence case states it)",
                      "fact: ASSIGN SCRNHT/SCRNWD (no equivalence case states it)")  # fmt: skip
    assert pb.fact_gaps(facts, pb.Run("equivalence", "c", userid=True)) == {screen}
    assert pb.fact_gaps(facts, pb.Run("equivalence", "c", screen=True)) == {userid}
    assert pb.fact_gaps(facts, pb.Run("equivalence", "c", userid=True, screen=True)) == set()
    assert pb.fact_gaps(facts, pb.Run("equivalence", "c")) == {userid, screen}


def test_the_facts_of_a_program_with_holes_are_read_but_never_ranked(tmp_path):
    """#5126 (zECS ZECS001's MOVE EIBRCODE): the ranking is over the programs a survey translates WHOLE, so a program
    with holes shows no fact gap there -- though its facts are read (the evidence report prints them)."""
    src = fixed("PROCEDURE DIVISION.", "    MOVE EIBRCODE TO WS-R", "    EXEC CICS RETURN END-EXEC.")
    assert pb.facts_needed(src)["eib"] == {"EIBRCODE"}
    corpora = tmp_path / "corpora"
    write(corpora / "estate" / "a/HOLES.cbl", src)
    rows = {("estate", "a/HOLES.cbl"): {"program": "a/HOLES.cbl", "statements": 5, "translated": 4, "holes": ["x"]}}
    res = pb.proof_blockers(rows, [corpora], cases_dir=tmp_path / "c", crucible_dir=tmp_path / "k", det_baseline={})
    assert res["programs"] == [] and res["whole"] == 0


def test_facts_are_names_only():
    f = pb.facts_needed(fixed("    MOVE EIBTASKN TO A", "    MOVE EIBCALEN TO B",
                              "    EXEC CICS ASSIGN SYSID(S) SCRNHT(H) END-EXEC."))  # fmt: skip
    assert f == {"eib": {"EIBTASKN"}, "assign_task": {"SCRNHT/SCRNWD"}, "assign_region": {"SYSID"}}


def test_cli_prints_the_totals(tmp_path, capsys, monkeypatch):
    cases, corpora, cru, det_baseline, rows = setup(tmp_path)
    survey = tmp_path / "s" / "main-b" / "survey.json"
    write(survey, {"estate": [r for (c, _), r in rows.items()]})
    monkeypatch.setattr(pb, "CASES", cases)
    monkeypatch.setattr(pb, "CRUCIBLE", cru)
    monkeypatch.setattr(pb, "DET_BASELINE", write(tmp_path / "det_sweep_baseline.json", {"det": det_baseline}))
    assert pb.main([str(tmp_path / "s"), "--label", "main", "--corpora", str(corpora), "--no-census"]) == 0
    out = capsys.readouterr().out
    assert "estates: translated whole 9 (non-burned 9); proven 1 (non-burned 1)" in out
    assert "no case" in out


def _stated(cases: Path, entries: dict) -> None:
    write(cases / "infeasible_outcomes.json", {"format": "infeasible-outcomes/1", "cases": entries})


def _entry(line: int, outcome: str) -> dict:
    return {
        "unit": "P",
        "line": line,
        "kind": "IF",
        "outcome": outcome,
        "family": "G",
        "reason": "every caller sets it",
    }


def test_stated_infeasible_outcomes_leave_the_branch_total(tmp_path):
    """#4602: a stated outcome the proof left uncovered leaves the total (and is listed); one it reached is a gap."""
    cases, corpora, cru, det_baseline, rows = setup(tmp_path)
    write(cases / "c-cov" / "evidence.json", {"coverage": {"paragraphs": {"covered": 3, "live": 3},
                                                           "branches": {"covered": 3, "total": 4},
                                                           "uncovered_branches": [{"line": 9, "outcome": "true"}]}})  # fmt: skip
    kw = {"cases_dir": cases, "crucible_dir": cru, "det_baseline": det_baseline, "branches": True}
    res = pb.proof_blockers(rows, [corpora], **kw)
    assert gaps_of(res, "COV") == ["coverage: branch outcomes no scenario runs"]
    _stated(cases, {"c-cov": [_entry(9, "true")]})
    res = pb.proof_blockers(rows, [corpora], **kw)
    cov = next(p for p in res["programs"] if p["program"].endswith("COV.cbl"))
    assert cov["gaps"] == [] and cov["infeasible"] == ["P:9:true"]
    _stated(cases, {"c-cov": [_entry(9, "true"), _entry(9, "false")]})  # 9 false ran: the claim is wrong
    res = pb.proof_blockers(rows, [corpora], **kw)
    cov = next(p for p in res["programs"] if p["program"].endswith("COV.cbl"))
    assert cov["gaps"] == ["infeasible outcome reached (the stated claim is wrong)"]
    assert cov["detail"]["infeasible outcome reached (the stated claim is wrong)"] == "P:9:false"


def test_a_sweep_s_uncovered_outcomes_check_the_claim(tmp_path):
    cases, corpora, cru, det_baseline, rows = setup(tmp_path)
    _stated(cases, {"c-diff": [_entry(9, "true")]})
    sweep = tmp_path / "sweep"
    line = "proven on 3 scenarios, covering 3/3 paragraphs and 1/2 branches"
    write(sweep / "sweep.json", {"det": {"c-diff": {"proved": True, "coverage": line, "translated": "5/5"}}})
    write(sweep / "det" / "c-diff" / "proof" / "cobol" / "coverage.json",
          {"branches": {"uncovered": [{"line": 9, "kind": "IF", "outcome": "true", "unit": "P"}]}})  # fmt: skip
    res = pb.proof_blockers(rows, [corpora], cases_dir=cases, crucible_dir=cru, det_baseline=det_baseline,
                            branches=True, sweeps=pb.load_sweeps([sweep]))  # fmt: skip
    assert gaps_of(res, "DIFF") == []


def test_a_linked_program_does_not_inherit_the_case_s_coverage():
    """#4270: coverage is measured for the case's program_source only; a LINKed program is a gap, never the case's numbers."""
    sweeps = {
        "c": {
            "proved": True,
            "coverage": "proven on 3 scenarios, covering 5/5 paragraphs and 9/9 branches",
            "translated": "2/2",
            "uncovered": [],
        }
    }
    main = pb.Run("equivalence", "c")
    linked = pb.Run("equivalence", "c", role="linked")
    for run in (main, linked):
        pb.judge_equivalence(run, {}, sweeps, True)
    assert main.gaps == set()
    assert linked.gaps == {pb.LINKED_NOT_MEASURED}
    # no coverage at all: the same single gap, not "unknown"
    other = pb.Run("equivalence", "c2", role="linked")
    pb.judge_equivalence(other, {}, {}, True)
    assert other.gaps == {pb.LINKED_NOT_MEASURED}


# ---- #5075: the det-sweep ledger is the Db2 lanes' verdict, and its harness / oracle-stale coverage is the last count --
STALE = {"coverage": [3, 3, 1, 1], "stale_inputs": ["harness", "oracle"], "stale_since": "abc123"}


def subject(res, stem):
    return next(p for p in res["programs"] if Path(p["program"]).stem == stem)


def test_a_db2_case_takes_its_verdict_from_a_readable_ledger_entry(tmp_path):
    """Current or stale on a scheduled input only: proven, with the ledger as its source; the coverage is read too."""
    for reading in ([3, 3, 1, 1], STALE):
        res = run(tmp_path, ledger={"c-db2": reading})
        assert gaps_of(res, "DB2") == []
        assert subject(res, "DB2")["verdict"] == "ledger"
        assert res["sources"]["ledger_verdicts"] == ["c-db2"]
        assert res["sources"]["stale_ledger_coverage"] == (["c-db2"] if reading is STALE else [])
    assert (res["whole"], res["proven"]) == (9, 2)


def test_a_db2_ledger_entry_with_uncovered_paragraphs_is_a_coverage_gap(tmp_path):
    res = run(tmp_path, ledger={"c-db2": [2, 3, 1, 1]})
    assert gaps_of(res, "DB2") == ["coverage: live paragraphs no scenario runs"]


def test_no_entry_or_a_blocking_change_leaves_the_db2_case_unproven(tmp_path):
    """None is what ledger_readings gives a missing entry AND one whose case / corpus changed."""
    for ledger in ({}, {"c-db2": None}):
        res = run(tmp_path, ledger=ledger)
        assert gaps_of(res, "DB2") == ["not proven in CI: Db2 case (no sweep row, no readable det-sweep ledger entry)"]
        assert subject(res, "DB2")["verdict"] == ""


def test_the_ledger_never_overrides_a_baseline_or_a_sweep(tmp_path):
    cases, corpora, cru, det_baseline, rows = setup(tmp_path)
    det_baseline["c-db2"] = {"issue": "#2", "why": "differs"}
    res = pb.proof_blockers(rows, [corpora], cases_dir=cases, crucible_dir=cru, det_baseline=det_baseline,
                            ledger={"c-db2": [3, 3, 1, 1]})  # fmt: skip
    assert gaps_of(res, "DB2") == ["known unproven: #2"] and subject(res, "DB2")["verdict"] == ""
    sweep = tmp_path / "sweep"
    write(sweep / "sweep.json", {"det": {"c-db2": {"proved": False, "coverage": ""}}})
    res = run(tmp_path, ledger={"c-db2": [3, 3, 1, 1]}, sweeps=pb.load_sweeps([sweep]))
    assert gaps_of(res, "DB2") == ["scenario differs: not proven (no report kept)"]


def test_a_non_db2_case_reads_scheduled_stale_coverage_not_blocking(tmp_path):
    """c-diff has no evidence record: its coverage is the ledger's or unknown."""
    res = run(tmp_path, ledger={"c-diff": STALE})
    assert gaps_of(res, "DIFF") == [] and subject(res, "DIFF")["stale_coverage"] == ["harness", "oracle"]
    assert subject(res, "DIFF")["verdict"] == ""  # its verdict is CI's ratchet, not the ledger
    res = run(tmp_path, ledger={"c-diff": None})
    assert gaps_of(res, "DIFF") == ["coverage: unknown (no sweep, no evidence record)"]
    res = run(tmp_path, ledger={"c-diff": {**STALE, "coverage": [1, 3, 1, 1]}})
    assert gaps_of(res, "DIFF") == ["coverage: live paragraphs no scenario runs"]


def test_a_linked_program_never_takes_the_ledger_s_coverage(tmp_path):
    res = run(tmp_path, ledger={"c-proven": [3, 3, 1, 1]})
    assert gaps_of(res, "LINKED") == [pb.LINKED_NOT_MEASURED]


def test_ledger_readings_maps_last_coverage(monkeypatch):
    import det_coverage_ledger as dcl

    base = {"coverage": (4, 4, 2, 2), "measured_at": "deadbeef"}
    lasts = {"cur": {**base, "stale_inputs": [], "blocking": False},
             "sched": {**base, "stale_inputs": ["oracle"], "blocking": False},
             "block": {**base, "stale_inputs": ["corpus"], "blocking": True}, "none": None}  # fmt: skip
    monkeypatch.setattr(dcl, "load", lambda: dict.fromkeys(lasts, {}))
    monkeypatch.setattr(dcl, "last_coverage", lambda case, ledger: lasts[case])
    got = pb.ledger_readings()
    assert got == {"block": None, "cur": [4, 4, 2, 2], "none": None,
                   "sched": {"coverage": [4, 4, 2, 2], "stale_inputs": ["oracle"], "stale_since": "deadbeef"}}  # fmt: skip
    assert (
        pb.ledger_readings(cases_dir=Path("/elsewhere")) == {}
    )  # a fixture tree: the repo's fingerprints do not apply


# ---- #5084: the LINKed programs' coverage ----------------------------------------------------------------------
def _counts(pc, pl):
    return {"paragraphs": {"covered": pc, "live": pl}, "branches": {"covered": 0, "total": 0}}


def _sweep_row(linked):
    return {"c": {"proved": True, "translated": "2/2", "uncovered": [], "linked": linked,
                  "coverage": "proven on 3 scenarios, covering 5/5 paragraphs and 9/9 branches"}}  # fmt: skip


def test_a_linked_program_is_judged_from_its_own_counts():
    sweeps = _sweep_row({"SUBP": _counts(2, 2), "HOLEY": _counts(1, 3)})
    whole = pb.Run("equivalence", "c", role="linked", program="SUBP")
    holey = pb.Run("equivalence", "c", role="linked", program="HOLEY")
    unmeasured = pb.Run("equivalence", "c", role="linked", program="OTHER")
    for run in (whole, holey, unmeasured):
        pb.judge_equivalence(run, {}, sweeps, True)
    assert whole.gaps == set()
    assert holey.gaps == {"coverage: live paragraphs no scenario runs"}
    assert unmeasured.gaps == {pb.LINKED_NOT_MEASURED}


def test_a_caller_is_not_proven_while_a_callee_has_holes():
    main = pb.Run("equivalence", "c")
    pb.judge_equivalence(main, {}, _sweep_row({"SUBP": _counts(2, 2), "HOLEY": _counts(1, 3)}), True)
    assert main.gaps == {"coverage: LINKed program HOLEY has live paragraphs no scenario runs"}
    assert main.detail[next(iter(main.gaps))] == "1/3 paragraphs"
    clean = pb.Run("equivalence", "c")
    pb.judge_equivalence(clean, {}, _sweep_row({"SUBP": _counts(2, 2)}), True)
    assert clean.gaps == set()


def test_the_ledger_reading_carries_the_linked_counts():
    reading, linked = [5, 5, 9, 9], {"c": {"HOLEY": _counts(1, 3)}}
    main = pb.Run("equivalence", "c")
    pb.judge_equivalence(main, {}, {}, True, ledger={"c": reading}, linked_ledger=linked)
    assert main.gaps == {"coverage: LINKed program HOLEY has live paragraphs no scenario runs"}
    callee = pb.Run("equivalence", "c", role="linked", program="HOLEY")
    pb.judge_equivalence(callee, {}, {}, True, ledger={"c": reading}, linked_ledger=linked)
    assert callee.gaps == {"coverage: live paragraphs no scenario runs"}


def test_a_callee_with_only_branch_holes_is_a_branch_gap_with_branches_on():
    row = _sweep_row({"SUBP": {"paragraphs": {"covered": 2, "live": 2}, "branches": {"covered": 1, "total": 2}}})
    on, off = pb.Run("equivalence", "c"), pb.Run("equivalence", "c")
    pb.judge_equivalence(on, {}, row, True)
    pb.judge_equivalence(off, {}, row, False)
    assert on.gaps == {"coverage: LINKed program SUBP has branch outcomes no scenario runs"}
    assert off.gaps == set()


def test_a_fresh_entry_with_linked_counts_is_still_a_current_reading(monkeypatch):
    """#5084: the LINKed counts travel apart from the reading, so a current entry stays a list (no stale_since)."""
    import det_coverage_ledger as dcl

    entry = {"scenarios": 3, "paragraphs": {"covered": 5, "live": 5}, "branches": {"covered": 9, "total": 9},
             "inputs": {}, "measured_at": "abc", "linked": {"HOLEY": _counts(1, 3)}}  # fmt: skip
    monkeypatch.setattr(dcl, "load", lambda directory=None: {"c": entry})
    monkeypatch.setattr(dcl, "last_coverage", lambda case, led: {"coverage": (5, 5, 9, 9), "stale_inputs": [],
                        "blocking": False, "measured_at": "abc", "linked": entry["linked"]})  # fmt: skip
    assert pb.ledger_readings(["c"]) == {"c": [5, 5, 9, 9]}
    assert pb.ledger_linked(["c"]) == {"c": {"HOLEY": _counts(1, 3)}}
    monkeypatch.setattr(dcl, "last_coverage", lambda case, led: {"coverage": (5, 5, 9, 9), "stale_inputs": ["harness"],
                        "blocking": True, "measured_at": "abc", "linked": entry["linked"]})  # fmt: skip
    assert pb.ledger_linked(["c"]) == {}


def test_fact_keywords_in_a_continued_literal_or_inline_comment_are_no_read():
    """#5089: the whole class of text that names a fact without reading it, for every fact keyword -- a literal
    continued onto the next line (column-7 hyphen) and a `*>` floating comment tail -- against the real reads."""
    cont = "      -    'END-EXEC' TO X."
    for src in (
        fixed("    MOVE 'EXEC CICS ASSIGN USERID(U) APPLID(A)", cont),
        fixed('    MOVE "EIBFN EIBRCODE EIBERR', '      -    "TAIL" TO X.'),
        fixed("    MOVE 1 TO X *> EXEC CICS ASSIGN STARTCODE(S) END-EXEC", "    MOVE 2 TO Y *> uses EIBFN"),
    ):
        assert pb.facts_needed(src) == {"eib": set(), "assign_task": set(), "assign_region": set()}, src
    # a `*>` inside a literal is text, and code after a closed continued literal is still read
    real = fixed(
        "    MOVE 'A *> B' TO X EIBFN.",
        "    MOVE 'EXEC CICS ASSIGN APPLID(A)",
        cont,
        "    EXEC CICS ASSIGN USERID(U) END-EXEC.",
    )
    got = pb.facts_needed(real)
    assert got["eib"] == {"EIBFN"} and got["assign_task"] == {"USERID"} and not got["assign_region"]
    # length-preserving: the line structure the command scan relies on is unchanged
    assert [len(x) for x in pb.code_only(real).splitlines()] == [len(x) for x in real.splitlines()]


def col7(*lines: str) -> str:
    """Lines whose first character is the indicator area (column 7)."""
    return "\n".join(f"{i * 100:06d}{ln}" for i, ln in enumerate(lines, 1)) + "\n"


def test_debugging_lines_are_no_read_unless_debugging_mode_is_active():
    """#5089: a column-7 `D` line is a comment unless WITH DEBUGGING MODE is active (a commented one does not count)."""
    empty = {"eib": set(), "assign_task": set(), "assign_region": set()}
    dbg = (
        "D    MOVE EIBFN TO X.",
        "D    EXEC CICS ASSIGN USERID(U) APPLID(A) STARTCODE(S) END-EXEC.",
        "D    MOVE 'EXEC CICS ASSIGN USERID(U)",
        "-    'END-EXEC' TO X.",
    )
    assert pb.facts_needed(col7(" MOVE 1 TO Y.", *dbg)) == empty
    mode = "     SOURCE-COMPUTER. IBM-370 WITH DEBUGGING MODE."
    got = pb.facts_needed(col7(mode, *dbg))
    assert got["eib"] == {"EIBFN"} and got["assign_task"] == {"USERID", "STARTCODE"}  # active: they are code
    assert pb.facts_needed(col7("*" + mode[1:], *dbg)) == empty  # a commented mode does not activate them
    real = col7(dbg[0], "     MOVE EIBRCODE TO Y.")
    assert pb.facts_needed(real)["eib"] == {"EIBRCODE"}
    assert [len(x) for x in pb.code_only(real).splitlines()] == [len(x) for x in real.splitlines()]


def free(*lines: str) -> str:
    """Free-format source: program text from column 1, no sequence area or indicator."""
    return "\n".join(lines) + "\n"


FREE_FACTS = (
    "IDENTIFICATION DIVISION.",
    "PROGRAM-ID. FREEFMT.",
    "PROCEDURE DIVISION.",
    "MOVE EIBFN TO WS-F. *> a floating comment tail with EIBRCODE",
    "EXEC CICS ASSIGN USERID(U) APPLID(A) END-EXEC.",
)


def test_free_format_source_is_read_whole_and_variable_past_column_72():
    """#5089: a free-format program keeps its first six columns and everything past column 72 (the fixed-format cut
    lost both), for every fact keyword; a `>>SOURCE FORMAT` switch is followed line by line."""
    got = pb.facts_needed(free(*FREE_FACTS))
    assert got["eib"] == {"EIBFN"} and got["assign_task"] == {"USERID"} and got["assign_region"] == {"APPLID"}
    far = free(
        "IDENTIFICATION DIVISION.",
        "PROCEDURE DIVISION.",
        "MOVE 1 TO " + "X" * 70 + " EXEC CICS ASSIGN SYSID(S) END-EXEC.",
    )
    assert pb.facts_needed(far)["assign_region"] == {"SYSID"}
    assert pb.cc.commands(far) == [["ASSIGN", "SYSID"]]
    # variable format: fixed areas, no column-72 limit
    var = ">>SOURCE FORMAT IS VARIABLE\n" + col7(" MOVE 1 TO " + "X" * 70 + " EXEC CICS ASSIGN STARTCODE(S) END-EXEC.")
    assert pb.facts_needed(var)["assign_task"] == {"STARTCODE"}
    # a directive switches mid-file: the fixed part keeps its column cut, the free part has none
    mixed = fixed("PROCEDURE DIVISION.", "    MOVE EIBTASKN TO X.") + ">>SOURCE FORMAT FREE\nMOVE EIBRCODE TO Y.\n"
    assert pb.facts_needed(mixed)["eib"] == {"EIBTASKN", "EIBRCODE"}


def test_free_format_literals_comments_and_debug_lines_are_no_read():
    """#5089: the text-that-names-a-fact class in free format: a literal (also continued onto a line opening with
    the quote), `*>` lines and tails, and `>>D` lines (code only under WITH DEBUGGING MODE)."""
    empty = {"eib": set(), "assign_task": set(), "assign_region": set()}
    for src in (
        free("IDENTIFICATION DIVISION.", "MOVE 'EXEC CICS ASSIGN USERID(U) EIBFN", "'END-EXEC' TO X."),
        free("IDENTIFICATION DIVISION.", 'MOVE "EIBRCODE" TO X.', "*> EXEC CICS ASSIGN APPLID(A) END-EXEC"),
        free("IDENTIFICATION DIVISION.", "MOVE 1 TO X. *> EIBFN", "   *> EIBERR"),
        free("IDENTIFICATION DIVISION.", ">>D MOVE EIBFN TO X.", ">>D EXEC CICS ASSIGN USERID(U) END-EXEC."),
    ):
        assert pb.facts_needed(src) == empty, src
    dbg = free("IDENTIFICATION DIVISION.", "SOURCE-COMPUTER. IBM-370 WITH DEBUGGING MODE.", ">>D MOVE EIBFN TO X.")
    assert pb.facts_needed(dbg)["eib"] == {"EIBFN"}
    real = free("IDENTIFICATION DIVISION.", "MOVE 'A *> B' TO X EIBFN.", "'") + "MOVE EIBERR TO Y.\n"
    assert pb.facts_needed(real)["eib"] == {"EIBFN", "EIBERR"}
    assert [len(x) for x in pb.code_only(real).splitlines()] == [len(x) for x in real.splitlines()]
