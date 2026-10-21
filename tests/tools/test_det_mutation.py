"""det_mutation (#4628): the det-port mutation ledger, the reviewed survivors, and the L5 hook. Fingerprints are
stubbed; no proof, translator or corpus needed (the committed ledgers' own check needs git only)."""

import sys
from pathlib import Path

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
    monkeypatch.setattr(dm, "fingerprints", lambda case: {**FP, "generator": "moved"})
    assert dm.status(CASE) is None


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
    assert dm.stale(e, now) == []  # the harness moved, but only in a component (db2) this case does not use
    now["harness"]["components"] = {"cics": "x2"}
    assert dm.stale(e, now) == ["harness"]
    assert dm.stale(entry(), {**FP, "harness": "c2"}) == ["harness"]  # no components stored: the whole input decides


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
    e = entry(inputs={"port": dm.port_sha(port) if ported else "other", **FP})
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
    written, _ = refresh_env(monkeypatch, tmp_path, True, {**FP, "harness": "c2"}, ("survived", "killed"))
    assert dm.refresh([CASE], tmp_path) == 1
    assert written[CASE]["survived"] == [S1]


def test_refresh_generator_only_does_not_rerun(monkeypatch, tmp_path):
    written, calls = refresh_env(monkeypatch, tmp_path, True, {**FP, "generator": "g2"}, ("killed", "killed"))
    assert dm.refresh([CASE], tmp_path) == 0
    assert calls == [] and "refreshed" not in written[CASE] and written[CASE]["inputs"]["generator"] == "g2"


def test_refresh_refuses_when_the_port_moved(monkeypatch, tmp_path):
    written, calls = refresh_env(monkeypatch, tmp_path, False, {**FP, "case": "a2"}, ("survived", "survived"))
    assert dm.refresh([CASE], tmp_path) == 2
    assert written == {} and calls == []


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
