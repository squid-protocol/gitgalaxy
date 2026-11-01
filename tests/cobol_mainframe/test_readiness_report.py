"""#4725 readiness report: the ranking is cics_census.blockers' ranking, the render is deterministic, the ladder counts
add up, and a callee with holes keeps a whole-translated caller out of the whole count."""

import copy
import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import cics_census as cc  # tests/tools/cics_census.py
import evidence_report as er  # tests/tools/evidence_report.py
import readiness_report as rr  # tests/tools/readiness_report.py

FIXTURE_REPORTS = Path(__file__).resolve().parents[1] / "fixtures" / "evidence_report"


@pytest.fixture(autouse=True)
def _snapshot_reports(monkeypatch):
    """#5206: the evidence report is published on `generated`, not committed; these tests read a frozen snapshot."""
    monkeypatch.setattr(rr, "REPORTS", FIXTURE_REPORTS)


def prog(name, level="L0", gaps=(), whole=None, refused=None, nxt=()):
    whole = (not gaps) if whole is None else whole
    return {
        "program": name,
        "level": level,
        "next": list(nxt),
        "assumptions": {"named_by_commands": [{"id": "X1", "status": "ASSUMED", "area": "CICS"}]},
        "translation": {"whole": whole, "refused": refused, "gap_classes": list(gaps)},
    }


def test_every_burned_estate_builds_and_ladder_adds_up():
    rep = rr.build()
    assert rep["estates"]
    for m in rep["estates"].values():
        lad = m["ladder"]
        assert sum(lad["levels"].values()) == lad["programs"]
        assert lad["translated_whole"] + lad["with_holes"] + lad["refused"] == lad["programs"]
        assert sum(m["eras"].values()) == lad["programs"]


def test_ranking_equals_the_blockers_tool():
    for name in rr.estates():
        report = json.loads((FIXTURE_REPORTS / name / "report.json").read_text(encoding="utf-8"))
        rows = {(name, p["program"]): {"gap_classes": p["translation"]["gap_classes"]} for p in report["programs"]}
        want = [(g["gap"], g["only"], g["one_away"], g["touched"]) for g in cc.blockers(rows)["gaps"]]
        got = rr.rules_to_land(report["programs"], name, {}, top=0)["ranked"]
        assert [(g["gap"], g["only"], g["one_away"], g["touched"]) for g in got] == want


def test_render_is_deterministic():
    assert rr.render() == rr.render()
    assert json.dumps(rr.build(), sort_keys=True) == json.dumps(rr.build(), sort_keys=True)


def test_ladder_counts_whole_holes_refused_and_callee_holes():
    progs = [
        prog("A", "L2"),
        prog("B", "L1", nxt=["its det port equal on every scenario of c: B CALLs C, which has holes"]),
        prog("C", "L0", gaps=["CALL X", "EXEC CICS GETMAIN"]),
        prog("D", "L0", gaps=["missing copybook Q"], refused="missing copybook Q"),
    ]
    lad = rr.ladder(progs)
    assert (lad["translated_whole"], lad["with_holes"], lad["refused"]) == (2, 1, 1)
    assert lad["whole_with_callee_holes"] == 1
    assert lad["executed_equivalent_or_above"] == 1
    assert lad["refusal_reasons"] == {"missing copybook Q": 1}


def test_rules_rank_by_programs_made_whole_with_era_mix():
    progs = [prog("A", gaps=["g1"]), prog("B", gaps=["g1"]), prog("C", gaps=["g2"]), prog("D", gaps=["g1", "g2"])]
    r = rr.rules_to_land(progs, "e", {"A": "2", "B": "3"})
    assert [g["gap"] for g in r["ranked"]] == ["g1", "g2"]
    assert r["ranked"][0]["only"] == 2 and r["ranked"][0]["only_by_era"] == {"2": 1, "3": 1}
    assert r["ranked"][1]["only"] == 1 and r["ranked"][1]["one_away"] == 1  # D is one rule away
    assert r["ranked"][1]["only_by_era"] == {"none": 1}


def test_an_estate_with_no_gaps_and_no_eras():
    m = rr.rules_to_land([prog("A", "L3")], "e", {})
    assert m["ranked"] == [] and m["classes"] == 0
    assert rr.era_of({}) == {}


def test_previous_run_delta():
    old = rr.build()
    new = copy.deepcopy(old)
    name = next(iter(new["estates"]))
    new["estates"][name]["ladder"]["translated_whole"] += 1
    ranked = new["estates"][name]["rules_to_land"]["ranked"]
    if ranked:
        ranked[0]["only"] += 5
    d = rr.delta(old, new)
    assert d[name]["ladder"]["translated_whole"][1] == d[name]["ladder"]["translated_whole"][0] + 1
    assert all(not v["ladder"] and not v["rules"] for k, v in d.items() if k != name)
    assert "Since the previous run" in rr.render(new, old)
    other = {"estates": {}}
    assert rr.delta(other, new)[name] == {"new_estate": True}


def test_unknown_estate_is_refused():
    with pytest.raises(SystemExit):
        rr.main(["no-such-estate"])


def test_main_json_round_trips(tmp_path):
    out = tmp_path / "r.json"
    assert rr.main(["--json", "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8")) == json.loads(json.dumps(rr.build(), sort_keys=True))


def test_every_next_entry_of_a_whole_program_is_classified():
    """#5229: a new evidence-report wording must be added to PROOF_CLASSES, not fall through to the raw-text fallback."""
    seen = 0
    for name in rr.estates():
        report = json.loads((FIXTURE_REPORTS / name / "report.json").read_text(encoding="utf-8"))
        for p in report["programs"]:
            if not p["translation"]["whole"]:
                continue
            for n in p["next"]:
                got = rr.proof_class(n)
                seen += 1
                assert got is None or got in rr.PROOF_CLASS_NAMES, n
    assert seen


def test_proof_classes_strip_numbers_and_ids():
    a = rr.proof_class("paragraph coverage >= 100.0 (now 57.1)")
    assert a == rr.proof_class("paragraph coverage >= 100.0 (now 98.4)") == "coverage: paragraphs below the bar"
    assert rr.proof_class("branch coverage >= 100.0 net (now 50.0 raw, 50.0 net of the reviewed)") == (
        "coverage: branch outcomes below the bar"
    )
    assert rr.proof_class("every surviving mutant of the det port accounted for: not yet measured (#4628)") is None
    assert rr.proof_class(
        "its det port equal on every scenario of x: ledgered as differing (#4803): A CALLs B, which has holes"
    ) == ("callee has holes")
    assert rr.proof_class("a brand new wording 12") == "a brand new wording N"  # kept, never dropped


def test_proofs_rank_counts_only_whole_programs_and_leaves_out_l5():
    l5 = "every surviving mutant of the det port accounted for: not yet measured (#4628)"
    progs = [
        prog("A", "L3", nxt=[l5]),  # no proof gap but the L5 hook: proven
        prog("B", "L1", nxt=["an equivalence case that runs it", l5]),
        prog("C", "L2", nxt=["paragraph coverage >= 100.0 (now 50.0)", "an equivalence case that runs it"]),
        prog("D", "L0", gaps=["g"], nxt=["translated whole (3 holes left)"]),  # not whole: out of the proof ranking
    ]
    r = rr.proofs_to_land(progs)
    assert (r["whole"], r["proven"]) == (3, 1)
    by = {g["gap"]: g for g in r["ranked"]}
    assert by["no case"]["only"] == 1 and by["no case"]["touched"] == 2
    assert by["coverage: paragraphs below the bar"]["only"] == 0
    assert by["coverage: paragraphs below the bar"]["touched"] == 1
    assert r["ranked"][0]["gap"] == "no case"


def test_proofs_ranking_equals_proof_blockers_rank_on_the_fixtures():
    import proof_blockers as pb

    for name in rr.estates():
        report = json.loads((FIXTURE_REPORTS / name / "report.json").read_text(encoding="utf-8"))
        progs = {
            ("", p["program"]): (True, {c for n in p["next"] if (c := rr.proof_class(n))})
            for p in report["programs"]
            if p["translation"]["whole"]
        }
        want = [(g["gap"], g["only"], g["one_away"], g["touched"]) for g in pb.rank(progs)["gaps"]]
        got = rr.proofs_to_land(report["programs"], top=0)["ranked"]
        assert [(g["gap"], g["only"], g["one_away"], g["touched"]) for g in got] == want


def test_proof_section_is_rendered_and_in_the_delta():
    old = rr.build()
    new = json.loads(json.dumps(old))
    name = next(iter(new["estates"]))
    pr = new["estates"][name]["proofs_to_land"]["ranked"]
    assert "### Proof blockers" in rr.render(new)
    if pr:
        pr[0]["only"] += 3
        assert rr.delta(old, new)[name]["proofs"][pr[0]["gap"]]["only"][1] == pr[0]["only"]


def test_main_markdown_carries_a_proof_section_for_every_estate_with_whole_programs(tmp_path):
    """#5229: the CLI output (not just render()) ranks proof blockers per burned estate, beside the rules to land."""
    out = tmp_path / "r.md"
    assert rr.main(["--top", "0", "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    built = rr.build(top=0)
    wholes = [n for n, m in built["estates"].items() if m["proofs_to_land"]["whole"]]
    assert wholes
    assert text.count("### Proof blockers (") == len(wholes)
    assert text.count("### Rules to land (") == len(built["estates"])


def _prog(named, reach="not measured"):
    return {
        "assumptions": {
            "named_by_commands": [{"id": i, "status": "ASSUMED", "area": f"area {i}"} for i in named],
            "reach": reach,
        }
    }


def test_caveats_without_measured_reach_are_the_named_upper_bound():
    rows = rr.caveats([_prog(["A1", "A2"]), _prog(["A2"])])
    assert [(r["id"], r["programs"], r["named_only"]) for r in rows] == [("A2", 2, 2), ("A1", 1, 1)]


def test_caveats_narrow_to_the_reached_entries_and_mix_with_unmeasured_programs():
    reached = _prog(["A1", "A2", "A3"], {"registers": ["A2", "A9"]})  # A9 is not named: never counted
    rows = {r["id"]: r for r in rr.caveats([reached, _prog(["A1", "A2"])])}
    assert rows["A2"]["programs"] == 2 and rows["A2"]["named_only"] == 1
    assert rows["A1"]["programs"] == 1 and rows["A1"]["named_only"] == 1
    assert "A3" not in rows and "A9" not in rows


def test_fully_measured_caveats_carry_no_named_only_key_and_render_without_upper_bound():
    rows = rr.caveats([_prog(["A1", "A2"], {"registers": ["A1"]}), _prog(["A1"], {"registers": []})])
    assert rows == [{"id": "A1", "status": "ASSUMED", "area": "area A1", "programs": 1}]


def _measured_prog(commands, role="program"):
    """A program whose `assumptions` is built the way evidence_report builds it: `named_by_commands` is every entry its
    commands name (the upper bound), `reach` is reach_of() of the chosen case, not a hand-written dict."""
    spec = er.css.spec()
    named = sorted({r for k in ("WRITEQ TS", "RETURN", "SEND MAP") for r in er.css.registers(spec[k])})
    rec = {"commands_run": commands} if commands is not None else {}
    reach = er.reach_of({"case": "c", "role": role, "record": rec})
    return {
        "assumptions": {
            "named_by_commands": [{"id": i, "status": "ASSUMED", "area": f"area {i}"} for i in named],
            "reach": reach,
        }
    }, set(named)


def test_caveats_consume_the_measured_reach_of_evidence_report():
    """The producer/consumer contract (#5229): a reached entry is counted, a named-only one is not, and every shape
    reach_of returns (a measured dict, "not measured" for no case / no commands / a LINKed role / an unmapped verb) is
    read: measured programs narrow, the rest stay the upper bound."""
    spec = er.css.spec()
    reached = set(er.css.registers(spec["RETURN"]))
    prog, named = _measured_prog(["RETURN"])
    assert reached <= named
    rows = {r["id"]: r for r in rr.caveats([prog])}
    assert set(rows) == reached  # narrower than what the commands name, when the rest is not reached
    assert all("named_only" not in r for r in rows.values())
    for commands, role in (
        (None, "program"),  # a record from before commands were recorded
        ([], "program"),
        (["RETURN"], "linked"),
        (["RETURN", "MQGET"], "program"),  # an MQI call is no spec entry
    ):
        unmeasured, named = _measured_prog(commands, role)
        assert unmeasured["assumptions"]["reach"] == "not measured"
        got = {r["id"]: r for r in rr.caveats([unmeasured])}
        assert set(got) == named and all(r["named_only"] == 1 for r in got.values())


def test_estate_with_measured_and_unmeasured_programs_counts_each_by_its_own_basis():
    measured, named = _measured_prog(["RETURN"])
    unmeasured, _ = _measured_prog(None)
    reached = set(er.css.registers(er.css.spec()["RETURN"]))
    for r in rr.caveats([measured, unmeasured]):
        assert r["named_only"] == 1  # the unmeasured program names every entry
        assert r["programs"] == (2 if r["id"] in reached else 1)


def test_blockers_one_run_writes_full_and_anonymized_reports_with_stable_hashes(tmp_path):
    """#5054 done-when 1 and 3: both reports from one run; each full blocker is in the twin under the same category
    with at least its programs; the hashes repeat with the same salt and change with another."""
    import blocker_report as br

    estate = rr.estates()[0]
    salt = tmp_path / "salt"

    def run(out, salt_file):
        assert (
            rr.main(["--blockers", str(out), "--salt-file", str(salt_file), "--out", str(tmp_path / "r.md"), estate])
            == 0
        )
        return out / estate

    a, b, other = run(tmp_path / "a", salt), run(tmp_path / "b", salt), run(tmp_path / "c", tmp_path / "salt2")
    names = sorted(p.name for p in a.iterdir())
    assert names == [
        "blocker_report.anon.json",
        "blocker_report.anon.md",
        "blocker_report.full.json",
        "blocker_report.full.md",
    ]
    full = json.loads((a / "blocker_report.full.json").read_text(encoding="utf-8"))
    anon = json.loads((a / "blocker_report.anon.json").read_text(encoding="utf-8"))
    assert full["blockers"], "the snapshot estate has blockers to compare"
    key = br.load_salt(salt)
    twin = {(x["category"], x["signature"]) for x in anon["blockers"]}
    cats = {}
    for g in full["blockers"]:
        cat, _sub, sig = br.classify(g["gap"], key)
        assert (cat, sig) in twin, g["gap"]
        cats.setdefault(cat, set()).add(g["gap"])
    for cat, gaps in cats.items():
        blocked = {p["program"] for p in full["programs"] if gaps & set(p["gaps"])}
        assert sum(x["programs_blocked"] for x in anon["blockers"] if x["category"] == cat) >= len(blocked) > 0
    assert (a / "blocker_report.anon.json").read_bytes() == (b / "blocker_report.anon.json").read_bytes()
    assert (a / "blocker_report.anon.json").read_bytes() != (other / "blocker_report.anon.json").read_bytes()


def test_blockers_needs_a_salt_file():
    with pytest.raises(SystemExit):
        rr.main(["--blockers", "somewhere"])


def test_blocker_result_is_proof_blockers_shaped():
    res = rr.blocker_result(
        "E",
        [prog("A", gaps=["EXEC CICS FORMATTIME RESP"]), prog("B", nxt=["an equivalence case that runs it"]), prog("C")],
    )
    assert res["whole"] == 3 and res["proven"] == 1
    assert {g["gap"] for g in res["gaps"]} == {"EXEC CICS FORMATTIME RESP", "no case"}
    assert [p["gaps"] for p in res["programs"]] == [["EXEC CICS FORMATTIME RESP"], ["no case"], []]


def _stub_materialize(monkeypatch, tmp_path, calls):
    import evidence_report as er
    import support_matrix as sm

    monkeypatch.setattr(rr, "REPORTS", None)
    monkeypatch.setattr(sm, "REPORTS", tmp_path)

    def fake():
        calls.append(1)
        (tmp_path / "est").mkdir()
        (tmp_path / "est" / "report.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(er, "materialize", fake)


def test_reports_materializes_the_published_report_when_none_is_on_disk(monkeypatch, tmp_path):
    """#6722: write_blockers for an estate without an inventory skips estates(), the only other materializer."""
    calls = []
    _stub_materialize(monkeypatch, tmp_path, calls)
    assert rr._reports() == tmp_path
    assert calls == [1]
    assert rr._reports() == tmp_path  # a report is on disk now: nothing more is fetched
    assert calls == [1]


CARDDEMO = "aws-mainframe-modernization-carddemo"


def test_source_defect_programs_are_named_fix_the_source_first_with_the_ibm_citation():
    """#5866: CBEXPORT / CBIMPORT, from the registry (the fixture's own source_defects is empty)."""
    rep = rr.build()
    held = rep["estates"][CARDDEMO]["fix_source_first"]
    assert [h["program"].rsplit("/", 1)[-1] for h in held] == ["CBEXPORT.cbl", "CBIMPORT.cbl"]
    assert all(h["issue"] == "#5866" and "Enterprise COBOL Language Reference" in h["reason"] for h in held)
    assert all("fix_source_first" not in m for n, m in rep["estates"].items() if n != CARDDEMO)
    text = rr.render(rep)
    assert "### Fix the source first" in text and "CBEXPORT.cbl: RECORD KEY names an item" in text
    assert text.count("### Fix the source first") == 1


def test_fix_the_source_first_skips_whole_risen_and_other_kinds():
    rows = [
        prog("app/cbl/CBEXPORT.cbl", gaps=("g",)),
        prog("app/cbl/CBIMPORT.cbl", level="L1", gaps=("g",)),
        prog("app/cbl/OTHER.cbl", gaps=("g",)),
    ]
    assert [h["program"] for h in rr.source_first(CARDDEMO, rows)] == ["app/cbl/CBEXPORT.cbl"]
    assert rr.source_first(CARDDEMO, [prog("app/cbl/CBEXPORT.cbl")]) == []  # whole: nothing to fix
    assert rr.source_first("zecs", [prog("ZECS002.asm", gaps=("g",))]) == []  # not_cobol is not a source defect
    assert rr.source_first("other-estate", rows) == []


def test_delta_reports_a_change_in_the_programs_to_fix_at_the_source():
    new = rr.build([CARDDEMO])
    old = copy.deepcopy(new)
    del old["estates"][CARDDEMO]["fix_source_first"]
    assert rr.delta(old, new)[CARDDEMO]["fix_source_first"] == [0, 2]
    assert "programs to fix at the source: 0 -> 2" in rr.render(new, old)
