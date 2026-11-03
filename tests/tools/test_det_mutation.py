"""det_mutation (#4628): the det-port mutation ledger, the reviewed survivors, and the L5 hook. Fingerprints are
stubbed; no proof, translator or corpus needed (the committed ledgers' own check needs git only)."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import det_mutation as dm

CASE = "cbsa-abndproc"  # a case that exists in the tree
FP = {"generator": "g", "case": "a", "corpus": "b", "harness": "c", "oracle": "d"}
S1 = {"id": "aaaa000001", "op": "CON", "file": "service/X.java", "line": 10, "before": "x = 0;", "after": "x = 1;"}
S2 = {"id": "aaaa000002", "op": "DEL", "file": "service/X.java", "line": 12, "before": "f();", "after": "/* f(); */"}


def entry(**over):
    return {"program": "ABNDPROC", "seed": 0, "mutants": 400, "chosen": 6, "mode": "fast",
            "counts": {"killed": 3, "timeout": 0, "survived": 2, "stillborn": 1, "error": 0, "pending": 0},
            "killed": ["k1", "k2", "k3"], "stillborn": ["s1"], "survived": [S1, S2],
            "inputs": {"port": "p", **FP}, **over}  # fmt: skip


def claim(s, verdict="equivalent", **over):
    return {**{k: s[k] for k in ("id", "op", "line", "before", "after")}, "verdict": verdict, "reason": "why", **over}


def test_summary_accounts_survivors():
    s = dm.summary(CASE, entry(), {})
    assert (s["killed"], s["survived"], s["accounted"], s["unaccounted"], s["l5"]) == (3, 2, 0, 2, False)
    assert s["score"] == 0.6
    s = dm.summary(CASE, entry(), {CASE: [claim(S1), claim(S2, "unreachable")]})
    assert (s["accounted"], s["unaccounted"], s["l5"]) == (2, 0, True)
    # a claim on a different Java line (the port moved) does not account for the survivor
    s = dm.summary(CASE, entry(), {CASE: [claim(S1), claim(S2, after="g();")]})
    assert (s["accounted"], s["unaccounted"], s["l5"]) == (1, 1, False)


def test_gap_verdicts_are_triaged_not_accounted():
    survivors = {CASE: [claim(S1), claim(S2, "harness-gap")]}
    s = dm.summary(CASE, entry(), survivors)
    assert (s["accounted"], s["unaccounted"], s["l5"]) == (1, 1, False)
    # a gap entry whose mutant is killed now is a closed gap, not a wrong claim: a warning to drop it
    gap = {**claim(S1, "case-gap"), "id": "k1"}
    assert dm.refuted(CASE, entry(), {CASE: [gap]}) == []
    problems, warnings = dm.check({CASE: entry()}, {CASE: [gap]}, tracked=False)
    assert not problems and "killed now" in warnings[0]


def test_a_killed_stated_mutant_fails():
    killed = {**claim(S1), "id": "k2"}
    survivors = {CASE: [killed, claim(S2)]}
    assert dm.refuted(CASE, entry(), survivors) == ["k2"]
    assert dm.summary(CASE, entry(), survivors)["l5"] is False
    problems, _ = dm.check({CASE: entry()}, survivors, tracked=False)
    assert any("the run killed it" in p for p in problems)


def test_check_form_and_claims():
    assert dm.check({CASE: entry()}, {CASE: [claim(S1), claim(S2)]}, tracked=False) == ([], [])
    problems, _ = dm.check({}, {CASE: [claim(S1, verdict="dunno")]}, tracked=False)
    assert "unknown verdict" in problems[0]
    problems, _ = dm.check({}, {CASE: [claim(S1, reason="")]}, tracked=False)
    assert "lacks reason" in problems[0]
    problems, _ = dm.check({}, {CASE: [claim(S1), claim(S1)]}, tracked=False)
    assert "listed twice" in problems[0]
    problems, _ = dm.check({"no-such-case": entry()}, {}, tracked=False)
    assert "no such case" in problems[0]
    problems, warnings = dm.check({CASE: entry()}, {CASE: [{**claim(S1), "id": "zz"}]}, tracked=False)
    assert not problems and "not judged" in warnings[0]


def test_status_is_none_when_stale(monkeypatch):
    monkeypatch.setattr(dm, "load", lambda path=dm.LEDGER: {CASE: entry()})
    monkeypatch.setattr(dm, "load_survivors", lambda path=dm.SURVIVORS: {CASE: [claim(S1), claim(S2)]})
    monkeypatch.setattr(dm, "fingerprints", lambda case: dict(FP))
    s = dm.status(CASE, "ABNDPROC")
    assert s is not None and s["l5"] and s["killed"] == 3 and s["accounted"] == 2
    assert dm.status(CASE, "OTHER") is None
    assert dm.status("carddemo-signon") is None  # no entry
    for n in dm.BLOCKING:  # an input that decides the score: stale (a "survivors" never recorded is not counted)
        if n in FP:
            monkeypatch.setattr(dm, "fingerprints", lambda case, n=n: {**FP, n: "moved"})
            assert dm.status(CASE) is None, n
    monkeypatch.setattr(dm, "fingerprints", lambda case: {**FP, "survivors": "moved"})
    assert dm.status(CASE) is not None  # (the entry predates the survivors fingerprint)
    monkeypatch.setattr(dm, "load", lambda path=dm.LEDGER: {CASE: entry(inputs={"port": "p", **FP, "survivors": "s"})})
    monkeypatch.setattr(dm, "fingerprints", lambda case: {**FP, "survivors": "s2"})
    assert dm.status(CASE) is None  # the reviewed list was edited since the entry was cut
    monkeypatch.setattr(dm, "load", lambda path=dm.LEDGER: {CASE: entry(port_moved=True)})
    monkeypatch.setattr(dm, "fingerprints", lambda case: dict(FP))
    assert dm.measured(CASE)["stale_inputs"] == ["port"]  # `refresh` found the det port's bytes moved


def test_generator_harness_oracle_drift_alone_does_not_stale(monkeypatch):
    """#5862 (owner 2026-10-23): the whole-tree generator / harness / oracle hashes are information, not staleness."""
    monkeypatch.setattr(dm, "load", lambda path=dm.LEDGER: {CASE: entry()})
    monkeypatch.setattr(dm, "load_survivors", lambda path=dm.SURVIVORS: {CASE: [claim(S1), claim(S2)]})
    for n in dm.INFO:
        monkeypatch.setattr(dm, "fingerprints", lambda case, n=n: {**FP, n: "moved"})
        s = dm.status(CASE)
        assert s is not None and s["l5"] and s["drifted"] == [n], n
        assert dm.stale(entry(), {**FP, n: "moved"}) == [] and dm.drifted(entry(), {**FP, n: "moved"}) == [n]
        assert f"{n} differ from the tree" in dm.describe(s)
    monkeypatch.setattr(dm, "fingerprints", lambda case: dict(FP))
    assert "drifted" not in dm.status(CASE)  # added only when non-empty
    assert set(dm.BLOCKING) | set(dm.INFO) | {"port"} == set(dm.INPUTS)


def test_member_spans_and_scope():
    text = ("class X {\n"
            "    public int runBatch(List<Dd> dds) {\n        if (x) { y(); }\n        return 0;\n    }\n"
            "    public void runTask(CicsTask t) {\n        z();\n    }\n}\n")  # fmt: skip
    assert dm.member_spans(text, ("runBatch",)) == [(2, 5)]
    assert dm.member_spans(text, ("runTask",)) == [(6, 8)]


def test_the_ledgers_are_tracked():
    """`.gitignore` has `*.json`: both directories need their `!dir/*.json` exception, or a PR ships without its data."""
    for case in dm.load():
        assert dm._tracked(dm.LEDGER / f"{case}.json"), case
    for case in dm.load_survivors():
        assert dm._tracked(dm.SURVIVORS / f"{case}.json"), case


def test_per_case_files_round_trip(tmp_path):
    led, sv = tmp_path / "led", tmp_path / "sv"
    dm.write(CASE, entry(), led)
    dm.write_survivors(CASE, [claim(S1)], sv)
    assert dm.load(led) == {CASE: entry()}
    assert dm.load_survivors(sv) == {CASE: [claim(S1)]}
    dm.write_survivors(CASE, [], sv)  # none left: the file goes
    assert dm.load_survivors(sv) == {}


def test_describe_shows_the_raw_score():
    assert dm.describe(None).startswith("not measured")
    line = dm.describe(dm.summary(CASE, entry(), {CASE: [claim(S1)]}))
    assert "raw 60% (3/5 caught" in line and "1 of 2 survivors unaccounted" in line
    line = dm.describe(dm.summary(CASE, entry(), {CASE: [claim(S1), claim(S2)]}))
    assert "every survivor accounted for (2)" in line


def test_the_committed_ledgers_agree():
    problems, _ = dm.check(tracked=False)
    assert problems == []


def test_component_staleness_as_evidence_records():
    """#4731's rule: a stored-components input is stale only when a component the target uses moved."""
    e = entry(components={"harness": {"cics": "x", "db2": "y"}})
    now = {**{k: {"sha256": v} for k, v in FP.items()}, "harness": {"sha256": "c2", "components": {"cics": "x"}}}
    assert dm.drifted(e, now) == []  # the harness moved, but only in a component (db2) this case does not use
    now["harness"]["components"] = {"cics": "x2"}
    assert dm.drifted(e, now) == ["harness"]
    assert dm.drifted(entry(), {**FP, "harness": "c2"}) == ["harness"]  # no components stored: the whole input decides
    e = entry(components={"case": {"k": "x"}})
    assert dm.stale(
        e, {**{k: {"sha256": v} for k, v in FP.items()}, "case": {"sha256": "a2", "components": {"k": "y"}}}
    ) == ["case"]


def rr(s, verdict):
    return {"id": s["id"], "verdict": verdict, "before": s["before"], "after": s["after"]}


def test_merge_survivors_carries_verdicts():
    e = entry()
    m = dm.merge_survivors(e, [rr(S1, "survived"), rr(S2, "killed")])
    assert [s["id"] for s in m["survived"]] == [S1["id"]]
    assert S2["id"] in m["killed"] and m["killed"] == sorted(m["killed"])
    assert (m["counts"]["killed"], m["counts"]["survived"]) == (4, 1)
    assert e == entry()  # the input is not touched
    m = dm.merge_survivors(e, [rr(S1, "timeout"), rr(S2, "survived")])
    assert (m["counts"]["timeout"], m["counts"]["survived"]) == (1, 1)
    m = dm.merge_survivors(e, [rr(S1, "error"), rr(S2, "survived")])  # an error is kept and counted: no L5
    assert [s["id"] for s in m["survived"]] == [S1["id"], S2["id"]] and m["counts"]["error"] == 1
    assert dm.summary(CASE, m, {CASE: [claim(S1), claim(S2)]})["l5"] is False
    assert dm.merge_survivors(e, [rr(S1, "survived")]) is None  # one not re-run
    assert dm.merge_survivors(e, [rr(S1, "survived"), {**rr(S2, "survived"), "after": "g();"}]) is None


def refresh_env(monkeypatch, tmp_path, ported, fresh, verdicts):
    """refresh() with the translator, fingerprints and mutation.run stubbed; returns the entries written."""
    import evidence
    import mutation as mu

    port = tmp_path / "det" / CASE / "port"
    port.mkdir(parents=True)
    (port / "A.java").write_text("class A {}", encoding="utf-8")
    e = entry(inputs={"port": dm.port_sha(port) if ported else "other", "runtime": dm.runtime_sha(port), **FP})
    written, calls = {}, []
    monkeypatch.setattr(dm, "load", lambda path=dm.LEDGER: {CASE: e})
    monkeypatch.setattr(dm, "load_survivors", lambda path=dm.SURVIVORS: {CASE: [claim(S1), claim(S2)]})
    monkeypatch.setattr(dm, "fingerprints", lambda case: {k: {"sha256": v} for k, v in fresh.items()})
    monkeypatch.setattr(dm, "translate", lambda cases, work: tmp_path / "det")
    monkeypatch.setattr(dm, "scope_filter", lambda kind, p: lambda ms: ms)
    monkeypatch.setattr(dm, "write", lambda case, ent, path=None: written.update({case: ent}))
    monkeypatch.setattr(evidence, "harness_commit", lambda: "abc")

    def fake_run(case, work, jobs, n, seed, ops, timeout, keep, full, only=None, **kw):
        calls.append((seed, only))
        return {"results": [rr(S1, verdicts[0]), rr(S2, verdicts[1])], "coverage": "cov"}

    monkeypatch.setattr(mu, "run", fake_run)
    return written, calls


def test_refresh_carries_verdicts_across_case_drift(monkeypatch, tmp_path):
    written, calls = refresh_env(monkeypatch, tmp_path, True, {**FP, "case": "a2"}, ("survived", "survived"))
    assert dm.refresh([CASE], tmp_path) == 0
    assert calls and calls[0][0] == 0  # the entry's seed, only the recorded survivors
    e = written[CASE]
    assert e["inputs"]["case"] == "a2" and e["refreshed"]["survivors_rerun"] == 2 and e["coverage"] == "cov"
    assert dm.stale(e, {k: {"sha256": v} for k, v in {**FP, "case": "a2"}.items()}) == []
    assert dm.summary(CASE, e)["l5"] is True  # both survivors keep their stated verdicts


def test_refresh_flags_a_killed_stated_claim(monkeypatch, tmp_path):
    written, _ = refresh_env(monkeypatch, tmp_path, True, {**FP, "case": "a2"}, ("survived", "killed"))
    assert dm.refresh([CASE], tmp_path) == 1
    assert written[CASE]["survived"] == [S1]


def test_refresh_info_drift_only_does_not_rerun(monkeypatch, tmp_path):
    drift = {**FP, "generator": "g2", "harness": "c2", "oracle": "d2"}
    written, calls = refresh_env(monkeypatch, tmp_path, True, drift, ("killed", "killed"))
    assert dm.refresh([CASE], tmp_path) == 0
    assert calls == [] and "refreshed" not in written[CASE] and written[CASE]["inputs"]["generator"] == "g2"
    assert written[CASE]["inputs"]["harness"] == "c2" and written[CASE]["inputs"]["oracle"] == "d2"


def test_refresh_leaves_a_current_entry_alone(monkeypatch, tmp_path, capsys):
    written, calls = refresh_env(monkeypatch, tmp_path, True, dict(FP), ("killed", "killed"))
    assert dm.refresh([CASE], tmp_path) == 0 and written == {} and calls == []
    assert "nothing stale" in capsys.readouterr().out


def test_refresh_refuses_when_the_port_moved(monkeypatch, tmp_path):
    written, calls = refresh_env(monkeypatch, tmp_path, False, {**FP, "case": "a2"}, ("survived", "survived"))
    assert dm.refresh([CASE], tmp_path) == 2
    assert calls == [] and written[CASE]["port_moved"] is True  # stale until `run` records the new port
    assert dm.stale(written[CASE], {k: {"sha256": v} for k, v in FP.items()}) == ["port"]


def test_refresh_finds_a_port_move_behind_info_drift(monkeypatch, tmp_path):
    """Generator drift alone no longer stales, but refresh still translates and compares the port's bytes."""
    written, calls = refresh_env(monkeypatch, tmp_path, False, {**FP, "generator": "g2"}, ("survived", "survived"))
    assert dm.refresh([CASE], tmp_path) == 2
    assert calls == [] and written[CASE]["port_moved"] is True


def moved_ledger(monkeypatch, cases, fail=()):
    """A ledger of port-moved entries (case -> date) and a fake `run` that records its arguments and, like `record`,
    drops the flag unless the case is in `fail`."""
    ledger = {c: entry(port_moved=True, date=d, chosen=40 + i, seed=i, mode="full" if i else None)
              for i, (c, d) in enumerate(cases.items())}  # fmt: skip
    calls = []

    def fake_run(cs, work, sample, seed, jobs, full):
        calls.append((cs, sample, seed, full))
        if cs[0] in fail:
            return 1
        ledger[cs[0]] = {k: v for k, v in ledger[cs[0]].items() if k != "port_moved"}
        return 0

    monkeypatch.setattr(dm, "load", lambda path=dm.LEDGER: ledger)
    monkeypatch.setattr(dm, "run", fake_run)
    return ledger, calls


def test_rerun_moved_runs_oldest_first_with_the_entrys_own_sample(monkeypatch, tmp_path):
    ledger, calls = moved_ledger(monkeypatch, {"new": "2026-10-20", "old": "2026-10-01", "mid": "2026-10-10"})
    assert dm.rerun_moved(["new", "old", "mid"], tmp_path) == ([], 0)
    assert [c[0] for c in calls] == [["old"], ["mid"], ["new"]]
    assert calls[0] == (["old"], 41, 1, True) and calls[2] == (["new"], 40, 0, False)  # sample, seed, mode carried
    assert not any(e.get("port_moved") for e in ledger.values())


def ticking(step_s):
    """A clock that advances `step_s` seconds per reading."""
    t = [-step_s]

    def clock():
        t[0] += step_s
        return t[0]

    return clock


def test_rerun_moved_stops_starting_cases_when_the_budget_is_spent(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(dm, "SECONDS_PER_MUTANT", 0)  # (this test is about the clock, not a case's size)
    _, calls = moved_ledger(monkeypatch, {"a": "2026-10-01", "b": "2026-10-02", "c": "2026-10-03"})
    # readings: start 0, check a 1, t0 2, end 3 (a took 1 s); check b at 4 s, slowest 1: 4 + 1 >= 5 s budget
    left, rc = dm.rerun_moved(["a", "b", "c"], tmp_path, 5 / 60, clock=ticking(1))
    assert (left, rc) == (["b", "c"], 0) and [c[0] for c in calls] == [["a"]]
    assert "b, c left for the next run" in capsys.readouterr().out
    _, calls = moved_ledger(monkeypatch, {"a": "2026-10-01"})
    assert dm.rerun_moved(["a"], tmp_path, 0, clock=lambda: 0) == (["a"], 0) and calls == []  # a zero budget runs none


def test_rerun_moved_passes_over_a_case_too_large_for_the_budget_and_runs_the_next(monkeypatch, tmp_path, capsys):
    ledger, calls = moved_ledger(monkeypatch, {"huge": "2026-10-01", "small": "2026-10-02"})
    ledger["huge"]["chosen"] = 1992  # ASYNCPNT: about 5 h, the night's run ended at its time limit inside it
    left, rc = dm.rerun_moved(["huge", "small"], tmp_path, 90, clock=lambda: 0)
    assert (left, rc) == (["huge"], 0) and [c[0] for c in calls] == [["small"]]
    assert "too large for what was left of 90 min: huge" in capsys.readouterr().out


def test_the_nightly_keeps_the_ledgers_of_a_mutation_job_that_hit_its_time_limit():
    text = (dm.REPO / ".github" / "workflows" / "evidence-refresh.yml").read_text(encoding="utf-8")
    step = text[text.index("id: detmut_in"):text.index("uses:", text.index("id: detmut_in"))]
    assert "needs.det-mutation.result == 'cancelled'" in step


def test_rerun_moved_does_not_start_a_case_the_slowest_so_far_would_overrun(monkeypatch, tmp_path):
    _, calls = moved_ledger(monkeypatch, {"a": "2026-10-01", "b": "2026-10-02"})
    ticks = iter([0, 0, 0, 50 * 60, 50 * 60])  # start, check a, t0, end (a took 50 min), check b at 50 min
    dm.rerun_moved(["a", "b"], tmp_path, 90, clock=lambda: next(ticks))
    assert [c[0] for c in calls] == [["a"]]  # 50 + 50 >= 90: b would pass the budget


def test_rerun_moved_reports_each_case_and_the_total(monkeypatch, tmp_path, capsys):
    moved_ledger(monkeypatch, {"a": "2026-10-01", "b": "2026-10-02"}, fail=("b",))
    dm.rerun_moved(["a", "b"], tmp_path, clock=ticking(30))
    out = capsys.readouterr().out
    assert "a ran in 0.5 min (ok)" in out and "b ran in 0.5 min (failed)" in out
    assert "2 moved, 2 run in 1.0 min (slowest 0.5), 1 failed" in out


def test_rerun_moved_keeps_the_flag_of_a_failed_run(monkeypatch, tmp_path):
    _, calls = moved_ledger(monkeypatch, {"a": "2026-10-01", "b": "2026-10-02"}, fail=("a",))
    assert dm.rerun_moved(["a", "b"], tmp_path) == (["a"], 1)
    assert len(calls) == 2  # the batch goes on after a failure


def test_refresh_run_moved_clears_a_moved_port(monkeypatch, tmp_path):
    written, calls = refresh_env(monkeypatch, tmp_path, False, {**FP, "case": "a2"}, ("survived", "survived"))
    seen = []
    monkeypatch.setattr(dm, "rerun_moved", lambda cs, work, budget: (seen.append((cs, budget)) or [], 0))
    assert dm.refresh([CASE], tmp_path, run_moved=True, budget_min=30) == 0
    assert seen == [([CASE], pytest.approx(30, abs=1))] and calls == []
    monkeypatch.setattr(dm, "rerun_moved", lambda cs, work, budget: (cs, 0))  # the budget did not reach it
    assert dm.refresh([CASE], tmp_path, run_moved=True) == 2
    monkeypatch.setattr(dm, "rerun_moved", lambda cs, work, budget: ([], 1))  # a run failed or a claim was refuted
    assert dm.refresh([CASE], tmp_path, run_moved=True) == 1


def test_refresh_without_run_moved_never_runs(monkeypatch, tmp_path):
    refresh_env(monkeypatch, tmp_path, False, {**FP, "case": "a2"}, ("survived", "survived"))
    monkeypatch.setattr(dm, "rerun_moved", lambda *a, **k: pytest.fail("ran without --run-moved"))
    assert dm.refresh([CASE], tmp_path) == 2


def test_stale_check_reports_info_drift_without_failing(monkeypatch, capsys):
    monkeypatch.setattr(dm, "load", lambda: {CASE: entry()})
    monkeypatch.setattr(dm, "fingerprints", lambda c: {**{k: {"sha256": v} for k, v in FP.items()},
                                                       "oracle": {"sha256": "d2"}})  # fmt: skip
    assert dm.stale_check() == 0
    out = capsys.readouterr().out
    assert "1 current ledger(s) with generator / harness / oracle drift" in out and "no stale ledger" in out


def test_stale_check_flags_a_moved_case_and_scopes_to_the_branch(monkeypatch, capsys):
    now = {k: {"sha256": v} for k, v in FP.items()}
    moved = {**now, "case": {"sha256": "changed"}}
    monkeypatch.setattr(dm, "load", lambda: {CASE: entry()})
    monkeypatch.setattr(dm, "fingerprints", lambda c: moved)
    assert dm.stale_check() == 1
    assert f"{CASE}: stale (case)" in capsys.readouterr().out
    monkeypatch.setattr(dm, "changed_cases", lambda ref: {"other-case"})  # this PR does not touch the case
    assert dm.stale_check("origin/main") == 0
    monkeypatch.setattr(dm, "changed_cases", lambda ref: {CASE})
    assert dm.stale_check("origin/main") == 1
    monkeypatch.setattr(dm, "fingerprints", lambda c: now)
    assert dm.stale_check("origin/main") == 0


def _git(root, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=root, check=True,
                   capture_output=True)  # fmt: skip


def test_changed_cases_reads_real_git_and_cases_to_rerun_keeps_the_ledgered(monkeypatch, tmp_path):
    eq = tmp_path / "tests" / "equivalence"
    for d in ("a", "b", "det_mutation"):
        (eq / d).mkdir(parents=True)
        (eq / d / "case.json").write_text("{}", encoding="utf-8")
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "base")
    _git(tmp_path, "checkout", "-q", "-b", "pr")
    for d in ("a", "b", "det_mutation"):
        (eq / d / "case.json").write_text('{"x": 1}', encoding="utf-8")
    (eq / "c").mkdir(parents=True)
    (eq / "c" / "evidence.json").write_text('{"refreshed": 1}', encoding="utf-8")
    (eq / "c" / "evidence.md").write_text("report", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qam", "change")
    monkeypatch.setattr(dm, "REPO", tmp_path)
    assert dm.changed_cases("main") == {
        "a",
        "b",
    }  # the ledger directory and refreshed evidence.json/md are not case inputs
    monkeypatch.setattr(dm, "load", lambda: {"a": entry()})
    assert dm.cases_to_rerun("main") == ["a"]
    assert dm.cases_to_rerun("no-such-ref") == []


def test_a_case_touch_in_a_real_branch_fails_the_ratchet_and_an_untouched_one_does_not(monkeypatch, tmp_path, capsys):
    """#5862 box 3 end to end: real git, real `changed_cases` / `stale_check` / `main`; only the fingerprints are stubbed
    (the tree's case hash moves exactly when the case file was changed)."""
    eq = tmp_path / "tests" / "equivalence"
    for d in ("a", "b"):
        (eq / d).mkdir(parents=True)
        (eq / d / "case.json").write_text("{}", encoding="utf-8")
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "base")
    _git(tmp_path, "checkout", "-q", "-b", "pr")
    monkeypatch.setattr(dm, "REPO", tmp_path)
    monkeypatch.setattr(dm, "CASES", eq)
    monkeypatch.setattr(dm, "load", lambda: {"a": entry(), "b": entry()})
    monkeypatch.setattr(dm, "fingerprints",
                        lambda c: {**{k: {"sha256": v} for k, v in FP.items()},
                                   "case": {"sha256": "changed" if (eq / c / "case.json").read_text() != "{}" else "a"}})  # fmt: skip
    assert dm.stale_check("main") == 0 and dm.cases_to_rerun("main") == []
    (eq / "a" / "case.json").write_text('{"strengthened": 1}', encoding="utf-8")
    assert dm.cases_to_rerun("main") == ["a"]  # the working tree counts: pr_gates runs before the commit
    capsys.readouterr()
    assert dm.stale_check("main") == 1
    out = capsys.readouterr().out
    assert "a: stale (case)" in out and "b: stale" not in out and "refresh a --work DIR" in out
    assert dm.stale_check() == 1  # no ref: every ledger; "b" is in step, "a" is not


def test_updacc_typed_dto_entry_scenarios_and_no_open_case_gap():
    """#4049: UPDACC's typed-DTO entry is driven by dto_entry scenarios (the link-area bytes hide an in_ defect), the
    failing run carries every caller field, and no survivor of the case is left a case-gap but the two held out."""
    import json

    root = dm.CASES / "cbsa-updacc"
    scenarios = {s["name"]: s for s in json.loads((root / "case.json").read_text())["scenarios"]}
    dto = [n for n, s in scenarios.items() if s.get("dto_entry")]
    assert len(dto) >= 6 and all(n.startswith("dto-entry-") for n in dto)
    kept = scenarios["dto-entry-caller-fields-kept-on-failure"]["commarea"]
    for field in (
        "COMM-CUSTNO",
        "COMM-OPENED",
        "COMM-LAST-STMT-DT",
        "COMM-NEXT-STMT-DT",
        "COMM-AVAIL-BAL",
        "COMM-ACTUAL-BAL",
    ):
        assert kept[field] not in ("", "0")
    survivors = json.loads((dm.CASES / "det_mutation_survivors" / "cbsa-updacc.json").read_text())["survivors"]
    # #4628: the two open case-gaps die only on inputs held out for an owner ruling on non-digits in a numeric MOVE
    assert {s["id"] for s in survivors if s["verdict"] == "case-gap"} == {"bee9666e07", "eb7aa72523"}


def test_tranadd_survivors_are_all_stated_and_none_is_a_gap():
    """#5862: COTRN02C's committed survivors are all stated `equivalent` / `unreachable` with a reason, so the case is L5."""
    import json

    survivors = json.loads((dm.CASES / "det_mutation_survivors" / "carddemo-tranadd.json").read_text())["survivors"]
    assert len(survivors) >= 37
    assert {s["verdict"] for s in survivors} <= set(dm.ACCOUNTED)
    assert all(s["reason"].strip() for s in survivors)


DRIFT = {**FP, "generator": "g2"}  # a translated port or runtime only moves with the generator


def carry_env(monkeypatch, tmp_path, every, results):
    """refresh() of an entry whose translated program moved: `every` = the ids in the new port."""
    import mutation as mu

    written, calls = refresh_env(monkeypatch, tmp_path, False, DRIFT, ("survived", "survived"))
    known = dm.load()[CASE]
    known["every"] = " ".join(["k1", "k2", "k3", "s1", S1["id"], S2["id"]])
    known["chosen"] = known["mutants"]  # (not sampled)
    monkeypatch.setattr(dm, "mutant_ids", lambda case, port: set(every))

    def fake_run(case, work, jobs, n, seed, ops, timeout, keep, full, only=None, **kw):
        calls.append(json.loads((only / "mutation.json").read_text(encoding="utf-8"))["results"])
        return {"results": results, "coverage": "cov"}

    monkeypatch.setattr(mu, "run", fake_run)
    return written, calls


def test_refresh_carries_a_moved_program_and_runs_only_the_new_mutants(monkeypatch, tmp_path):
    new = {"id": "new0000001", "op": "CON", "file": "service/X.java", "line": 90, "before": "y = 1;", "after": "y = 2;"}
    every = ["k1", "k2", "s1", S1["id"], S2["id"], new["id"]]  # k3 went with its line, one mutant is new
    written, calls = carry_env(monkeypatch, tmp_path, every, [rr(S1, "survived"), rr(S2, "survived"), {**new, "verdict": "killed"}])
    assert dm.refresh([CASE], tmp_path) == 0
    assert [r["id"] for r in calls[0]] == [new["id"]]  # nothing carried is run again
    e = written[CASE]
    assert e["killed"] == ["k1", "k2", new["id"]] and e["counts"]["killed"] == 3 and "port_moved" not in e
    assert e["mutants"] == 6 and sorted(e["every"].split()) == sorted(every) and e["refreshed"]["fresh"] == 1
    assert dm.summary(CASE, e)["l5"] is True


def test_a_new_survivor_withholds_l5_until_it_is_accounted_for(monkeypatch, tmp_path):
    new = {"id": "new0000001", "op": "CON", "file": "service/X.java", "line": 90, "before": "y = 1;", "after": "y = 2;"}
    every = ["k1", "k2", "k3", "s1", S1["id"], S2["id"], new["id"]]
    written, _ = carry_env(monkeypatch, tmp_path, every, [rr(S1, "survived"), rr(S2, "survived"), {**new, "verdict": "survived"}])
    assert dm.refresh([CASE], tmp_path) == 0
    s = dm.summary(CASE, written[CASE])
    assert (s["unaccounted"], s["l5"]) == (1, False)


def test_a_new_mutant_with_no_verdict_leaves_the_entry_stale(monkeypatch, tmp_path):
    new = {"id": "new0000001", "op": "CON", "file": "service/X.java", "line": 90, "before": "y = 1;", "after": "y = 2;"}
    every = ["k1", "k2", "k3", "s1", S1["id"], S2["id"], new["id"]]
    written, _ = carry_env(monkeypatch, tmp_path, every, [rr(S1, "survived"), rr(S2, "survived"), {**new, "verdict": "error"}])
    assert dm.refresh([CASE], tmp_path) == 1
    assert written == {}


def test_a_move_too_large_to_carry_is_a_full_run(monkeypatch, tmp_path):
    every = [f"n{i}" for i in range(100)]
    written, calls = carry_env(monkeypatch, tmp_path, every, [])
    assert dm.refresh([CASE], tmp_path) == 2
    assert calls == [] and written[CASE]["port_moved"] is True


def test_an_entry_from_before_every_is_a_full_run():
    assert dm.fresh_mutants({}, {"a"}) is None
    assert dm.fresh_mutants({"every": "a", "chosen": 1, "mutants": 1}, {"a"}) == []


def test_a_spent_budget_leaves_a_moved_program_flagged_for_the_next_run(monkeypatch, tmp_path, capsys):
    written, calls = carry_env(monkeypatch, tmp_path, ["k1"], [])
    assert dm.refresh([CASE], tmp_path, budget_min=0) == 2
    assert calls == [] and written == {} and "left for the next run" in capsys.readouterr().out


def test_a_runtime_move_is_recorded_and_runs_nothing(monkeypatch, tmp_path):
    written, calls = refresh_env(monkeypatch, tmp_path, True, DRIFT, ("survived", "survived"))
    dm.load()[CASE]["inputs"]["runtime"] = "another"
    assert dm.refresh([CASE], tmp_path) == 0
    assert calls == [] and written[CASE]["inputs"]["runtime"] != "another"


def test_a_case_move_still_reruns_the_survivors_of_a_moved_program(monkeypatch, tmp_path):
    written, calls = carry_env(monkeypatch, tmp_path, ["k1", S1["id"], S2["id"]], [rr(S1, "survived"), rr(S2, "killed")])
    dm.load()[CASE]["inputs"]["case"] = "an older case"
    assert dm.refresh([CASE], tmp_path) == 1  # S2 is stated equivalent and the re-run killed it: a wrong claim
    assert sorted(r["id"] for r in calls[0]) == sorted([S1["id"], S2["id"]])


def test_a_sampled_entry_samples_its_new_mutants_at_its_own_rate():
    ids = [hashlib.sha1(str(i).encode(), usedforsecurity=False).hexdigest()[:10] for i in range(800)]
    e = {"every": " ".join(ids[:640]), "chosen": 150, "mutants": 3000}
    kept = dm.fresh_mutants(e, set(ids))
    assert kept == dm.fresh_mutants(e, set(ids))  # repeatable
    assert 0 < len(kept) < 30 and set(kept) <= set(ids[640:])  # about 5% of the 160 new ones


def test_the_port_fingerprint_leaves_out_the_runtime(tmp_path):
    (tmp_path / "service").mkdir()
    (tmp_path / "cobolrt").mkdir()
    (tmp_path / "service" / "X.java").write_text("class X {}", encoding="utf-8")
    (tmp_path / "cobolrt" / "Cobol.java").write_text("class Cobol {}", encoding="utf-8")
    port, runtime = dm.port_sha(tmp_path), dm.runtime_sha(tmp_path)
    (tmp_path / "cobolrt" / "Cobol.java").write_text("/* reworded */ class Cobol {}", encoding="utf-8")
    assert dm.port_sha(tmp_path) == port and dm.runtime_sha(tmp_path) != runtime
    (tmp_path / "service" / "X.java").write_text("class X { int y; }", encoding="utf-8")
    assert dm.port_sha(tmp_path) != port


def test_a_mutant_keeps_its_id_when_a_line_is_added_above_it():
    import mutation as mu

    ops = set(mu.OPERATORS)
    code = "class X {\n  int f(int a) {\n    if (a > 1) {\n      return 2;\n    }\n    return a + 1;\n  }\n}\n"
    before = {m.id: m.before for m in mu.mutants_of("service/X.java", code, ops)}
    assert before
    moved = code.replace("  int f(int a) {\n", "  int f(int a) {\n    g();\n")
    after = {m.id: m.before for m in mu.mutants_of("service/X.java", moved, ops)}
    assert set(before) <= set(after) and {v for k, v in after.items() if k not in before} == {"g();"}
    edited = code.replace("return a + 1;", "return a + 7;")
    now = mu.mutants_of("service/X.java", edited, ops)
    assert {m.id for m in now} != set(before)  # an edited line's mutants are new


def test_identical_lines_keep_apart_ids():
    import mutation as mu

    code = "class X {\n  void f(int a) {\n    a = a + 1;\n    a = a + 1;\n  }\n}\n"
    ms = mu.mutants_of("service/X.java", code, set(mu.OPERATORS))
    assert len({m.id for m in ms}) == len(ms)
