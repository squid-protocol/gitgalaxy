"""evidence_report (#4601): the committed purchaser-facing reports are current, never say "proven" / "verified" /
"guaranteed", take every number they print from their JSON, and place programs at the level their numbers allow."""

import copy
import json
import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evidence_report as er

REPORTS = sorted(er.OUT.glob("*/report.json"))
# A number as the Markdown prints it: not part of a name (CBACT01C, L5) or a hex digest (8dff2ec2e).
_NUMBER = re.compile(r"(?<![A-Za-z0-9.])\d+(?:\.\d+)*(?![A-Za-z0-9])")


def numbers_in(value):
    """Every number a JSON value holds: numeric values (as the report prints them) and numbers inside strings."""
    if isinstance(value, bool) or value is None:
        return set()
    if isinstance(value, (int, float)):
        return {str(value)}
    if isinstance(value, str):
        return set(_NUMBER.findall(value))
    items = value.items() if isinstance(value, dict) else enumerate(value)
    out = set()
    for k, v in items:
        if isinstance(k, str):
            out |= numbers_in(k)
        out |= numbers_in(v)
    return out


def test_burned_estate_reports_are_committed_and_only_burned():
    assert REPORTS, "no committed report: python tests/tools/evidence_report.py --all --baseline"
    import cics_census as cc

    for f in REPORTS:
        assert cc.is_burned(f.parent.name), f"{f.parent.name}: only burned estates are committed"


@pytest.mark.skipif(
    os.environ.get("EVIDENCE_REPORT_ADVISORY") == "1",
    reason="#4703: per-PR CI is advisory (smoke-test.yml / full-suite-gate.yml print the level deltas); the evidence-refresh "
    "bot regenerates the reports on main and the release gate (publish.yml) runs `evidence_report.py --check --live`",
)
def test_the_committed_reports_are_current():
    assert er.main(["--check"]) == 0, "stale: python tests/tools/evidence_report.py --refresh"


@pytest.mark.parametrize("path", REPORTS, ids=lambda p: p.parent.name)
def test_committed_report_validates(path):
    assert er.validate(json.loads(path.read_text("utf-8"))) == []


@pytest.mark.parametrize("path", [*REPORTS, er.OUT / "README.md"], ids=lambda p: p.parent.name + "/" + p.name)
def test_no_forbidden_words(path):
    md = path.with_name("report.md") if path.suffix == ".json" else path
    hits = er._FORBIDDEN.findall(md.read_text("utf-8"))
    assert not hits, f"{md}: the report never says {sorted(set(hits))} (levels and numbers, #4601)"


@pytest.mark.parametrize("path", REPORTS, ids=lambda p: p.parent.name)
def test_every_number_in_the_markdown_comes_from_the_json(path):
    rep = json.loads(path.read_text("utf-8"))
    md = path.with_name("report.md").read_text("utf-8")
    missing = set(_NUMBER.findall(md)) - numbers_in(rep)
    assert not missing, f"numbers in {path.with_name('report.md')} that report.json does not hold: {sorted(missing)}"


def test_the_index_numbers_come_from_the_reports():
    reps = [json.loads(f.read_text("utf-8")) for f in REPORTS]
    have = set().union(*(numbers_in(r) for r in reps))
    # the index's per-burned-group totals are sums of the reports' histograms
    for burned in (True, False):
        rs = [r for r in reps if r["burned"] == burned]
        have |= {str(sum(r["summary"]["programs"] for r in rs))}
        have |= {str(sum(r["summary"]["histogram"][lv] for r in rs)) for lv in er.LEVELS}
        have |= {
            str(sum(er.stale_counts(r["summary"])[lv] for r in rs)) for lv in er.LEVELS
        }  # "(k stale)" cells (#4730)
    missing = set(_NUMBER.findall((er.OUT / "README.md").read_text("utf-8"))) - have
    assert not missing, sorted(missing)


# ---- levels ------------------------------------------------------------------------------------------------------
def program(
    *,
    whole=True,
    case=True,
    det="equal",
    record=True,
    stale=(),
    para=(10, 10),
    branch=(10, 10),
    net=None,
    refuted=(),
    backed=True,
):
    rec = {"stale_inputs": list(stale), "verdict": "all equal", "scenarios": 3} if record else None
    chosen = {"case": "c", "role": "program", "det": {"state": det, "why": ["x"]}, "record": rec} if case else None
    net = branch if net is None else net
    cov = {
        "paragraph_pct": er.pct(*para) if para else None,
        "branch_pct": er.pct(*branch) if branch else None,
        "branch_net_pct": er.pct(*net) if net else None,
        "infeasible_refuted": list(refuted),
    }
    return {
        "translation": {"whole": whole, "refused": None, "hole_count": 0 if whole else 2},
        "equivalence": {"cases": [chosen] if chosen else [], "chosen": chosen},
        "coverage": cov,
        "oracle_backing": [{"command": "RETURN", "backed": backed}],
        "mutation": {"det_port": er.MUTATION},
    }


BARS = er.DEFAULT_BARS


@pytest.mark.parametrize(
    ("kw", "level"),
    [
        ({"whole": False}, "L0"),
        ({"case": False}, "L1"),
        ({"det": "not run"}, "L1"),  # a Db2 case with no local sweep
        ({"det": "not equal"}, "L1"),
        ({"record": False}, "L4"),  # the evidence record is reported, not a gate (#4601 owner decision)
        ({"stale": ("harness",)}, "L4"),
        ({"para": (9, 10)}, "L2"),  # strict bars: 100%
        ({"para": None}, "L2"),  # coverage not measured: not above any bar
        ({"branch": (9, 10)}, "L3"),
        ({"branch": (9, 10), "net": (9, 9)}, "L4"),  # 100% net of the reviewed infeasible outcomes (#4602)
        ({"branch": (9, 10), "net": (9, 9), "refuted": ["P:1:true"]}, "L3"),  # a refuted claim is no claim
        ({}, "L4"),  # never L5 until det-port mutation (#4628) is measured
        ({"backed": False}, "L4"),  # oracle backing is a column, not a rung
    ],
)
def test_levels_are_cumulative_and_never_reach_l5_unmeasured(kw, level):
    lvl, nxt = er.level_of(program(**kw), BARS)
    assert lvl == level
    assert nxt, "a level always says what the next one needs"
    if level == "L4":
        assert any("#4628" in n for n in nxt)
        assert not any("oracle" in n for n in nxt)


def test_the_bars_are_parameters_and_strict_by_default():
    assert er.DEFAULT_BARS == {"paragraphs": 100.0, "branches": 100.0}
    p = program(para=(9, 10), branch=(9, 10))
    assert er.level_of(p, BARS)[0] == "L2"
    assert er.level_of(p, {"paragraphs": 90.0, "branches": 85.0})[0] == "L4"
    assert all(str(b) in json.dumps(er.level_table({"paragraphs": 95.0, "branches": 85.0})) for b in (95.0, 85.0))


def test_the_ladder_is_the_owners():
    names = [lv["name"] for lv in er.level_table(BARS)]
    assert names[5] == "mutants accounted for"
    assert "#4628" in er.level_table(BARS)[5]["condition"]
    assert not any("crucible" in lv["condition"] for lv in er.level_table(BARS))  # oracle backing: a column


def test_coverage_comes_from_the_sweep_or_the_ledger_never_the_record():
    case = {"case": "no-such-case", "record": {"coverage": {"paragraphs": {"covered": 1, "live": 1}}}}
    assert er.coverage_of(case, {}, {})["source"] is None
    got = er.coverage_of(case, {}, {"no-such-case": [3, 4, 5, 10]})
    assert (got["paragraph_pct"], got["branch_pct"], got["branch_net_pct"]) == (75.0, 50.0, 50.0)
    assert "ledger" in got["source"]
    line = {"no-such-case": {"coverage": "proven on 2 scenarios, covering 4/4 paragraphs and 6/6 branches"}}
    assert er.coverage_of(case, line, {"no-such-case": [3, 4, 5, 10]})["source"] == "local sweep coverage line"


def test_infeasible_outcomes_are_stated_and_netted_never_hidden():
    import infeasible_outcomes as io

    case, entries = next(iter(io.load().items()))
    got = er.coverage_of({"case": case, "record": None}, {}, {case: [5, 5, 10, 10 + len(entries)]})
    assert got["branches"] == {"covered": 10, "total": 10 + len(entries)}  # raw, as measured
    assert got["branches_net"] == {"covered": 10, "total": 10}  # net of the stated entries
    assert got["branch_net_pct"] == 100.0
    assert [e["key"] for e in got["infeasible_stated"]] == [e["key"] for e in io.stated(case)]
    assert all(e["family"] in "GCR" and e["reason"] for e in got["infeasible_stated"])


def test_neutral_rewords_quoted_tool_text():
    assert er.neutral("not proven in CI; 7 cases re-proven; Verified") == (
        "not shown equal in CI; 7 cases re-shown equal; checked"
    )
    assert er.neutral("unproven methods") == "unproven methods"  # not the word itself


def test_rendered_text_rewords_what_a_tool_says():
    rep = json.loads(REPORTS[0].read_text("utf-8"))
    rep = copy.deepcopy(rep)
    rep["assumptions_named"] = [{"id": "C6", "area": "compiler", "status": "MATCHED", "entry": er.neutral("proven by")}]
    assert not er._FORBIDDEN.search(er.render(rep))


# ---- the committed-file guard and the measured block ---------------------------------------------------------------
def test_a_non_burned_estate_is_never_written_into_the_repo(tmp_path):
    run = tmp_path / "before-nb"
    run.mkdir()
    (run / "survey.json").write_text(json.dumps({"some-census-repo": [{"program": "P.cbl", "statements": 1,
                                                                       "translated": 1, "holes": []}]}))  # fmt: skip
    with pytest.raises(SystemExit, match="not a burned estate"):
        er.main(["some-census-repo", "--survey", str(tmp_path)])


def test_check_fails_on_an_edited_report(tmp_path, monkeypatch):
    estate = REPORTS[0].parent.name
    (tmp_path / estate).mkdir()
    for name in ("report.json", "report.md"):
        (tmp_path / estate / name).write_text((er.OUT / estate / name).read_text("utf-8"))
    monkeypatch.setattr(er, "OUT", tmp_path)
    er.write(er.expected())  # the committed JSON may predate a format change (#4730): the bot regenerates it on main
    assert er.main(["--check"]) == 0
    md = tmp_path / estate / "report.md"
    md.write_text(md.read_text().replace("| L0 |", "| L0 (edited) |", 1))
    assert er.main(["--check"]) == 1


def test_measure_reads_commands_and_facts(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")  # the det translator's EXEC parser keys the commands
    code = ["PROCEDURE DIVISION.", "    EXEC CICS ASKTIME ABSTIME(WS-T) END-EXEC.",
            "    MOVE EIBTASKN TO WS-N.", "    EXEC CICS RETURN END-EXEC."]  # fmt: skip
    src = tmp_path / "zecs" / "Source"
    src.mkdir(parents=True)
    (src / "P1.cbl").write_text("".join(f"{i * 100:06d} {c}\n" for i, c in enumerate(code, 1)))
    rows = {("zecs", "Source/P1.cbl"): {"program": "Source/P1.cbl", "statements": 3, "translated": 3, "holes": []}}
    m = er.measure("zecs", rows, [tmp_path], {"sha": None, "scope": "test", "label": "before"}, {})
    (p,) = m["programs"]
    assert p["commands"] == ["ASKTIME", "RETURN"]
    assert p["facts"]["eib"] == ["EIBTASKN"]
    rep = er.build(m, "zecs", BARS)
    assert er.validate(rep) == []
    (prog,) = rep["programs"]
    assert prog["level"] == "L1"  # whole, no case
    assert prog["assumptions"]["reach"] == "not measured"
    assert any("EIBTASKN" in f for f in prog["assumptions"]["facts_unstated"])
    assert not er._FORBIDDEN.search(er.render(rep))


def test_deltas_are_advisory_and_name_the_level_changes(tmp_path, monkeypatch, capsys):
    estate = REPORTS[0].parent.name
    (tmp_path / estate).mkdir()
    rep = json.loads((er.OUT / estate / "report.json").read_text("utf-8"))
    rep["programs"][0]["level"] = "L5"  # a committed level the repo no longer makes
    (tmp_path / estate / "report.json").write_text(er.dumps(rep), "utf-8")
    monkeypatch.setattr(er, "OUT", tmp_path)
    assert er.main(["--deltas"]) == 0
    out = capsys.readouterr().out
    assert "differ from what the repo makes now" in out and rep["programs"][0]["program"] in out and "L5" in out


# ---- #4730: a stale level is kept, marked, and never current --------------------------------------------------------
CASE = "carddemo-adminmenu"  # a carddemo program's case, whose coverage the ledger holds
FULL = [4, 4, 2, 2]
STALE = {"coverage": FULL, "stale_inputs": ["harness", "oracle"], "stale_since": "abc1234def5678"}


def stale_fixture(tmp_path, monkeypatch, cov):
    """A tmp OUT holding the carddemo report refreshed with the ledger's measurement of CASE = cov (list: current;
    dict: stale on a scheduled input; None: unknown). Live status is the same measurement (no tree needed)."""
    estate = "aws-mainframe-modernization-carddemo"
    old = json.loads((er.OUT / estate / "report.json").read_text("utf-8"))
    old["measured"]["det_coverage"] = {**old["measured"]["det_coverage"], CASE: cov}
    (tmp_path / estate).mkdir(exist_ok=True)
    monkeypatch.setattr(er, "OUT", tmp_path)
    (tmp_path / estate / "report.json").write_text(er.dumps(old), "utf-8")
    monkeypatch.setattr(er, "record_status", lambda: old["measured"]["record_status"])
    monkeypatch.setattr(er, "det_coverage", lambda: old["measured"]["det_coverage"])
    er.write(er.expected(True))
    return estate


def program_of(tmp_path, estate):
    rep = json.loads((tmp_path / estate / "report.json").read_text("utf-8"))
    return rep, next(p for p in rep["programs"] if p["equivalence"]["chosen"]["case"] == CASE)


def test_a_harness_only_change_keeps_the_last_level_marked_stale(tmp_path, monkeypatch):
    estate = stale_fixture(tmp_path, monkeypatch, STALE)
    rep, p = program_of(tmp_path, estate)
    assert (p["level"], p["level_current"]) == ("L3", False)  # not 0 / unknown
    assert p["stale_inputs"] == ["harness", "oracle"] and p["stale_since"] == "abc1234def5678"
    assert er.validate(rep, strict=True) == []
    s = rep["summary"]
    assert s["histogram"]["L3"] == 1 and s["histogram_stale"]["L3"] == 1 and s["levels_stale"] == 1
    md = (tmp_path / estate / "report.md").read_text("utf-8")
    assert f"| {p['program']} | L3* |" in md and "stale since `abc1234def56` (harness, oracle)" in md
    assert "L3+: 1 (1 awaiting re-check)" in md and "How to read" in md and "Stale levels" in md
    assert not er._FORBIDDEN.search(md)


def test_a_current_measurement_is_a_current_level(tmp_path, monkeypatch):
    estate = stale_fixture(tmp_path, monkeypatch, FULL)
    rep, p = program_of(tmp_path, estate)
    assert (p["level"], p["level_current"], p["stale_inputs"], p["stale_since"]) == ("L3", True, [], None)
    assert rep["summary"]["levels_stale"] == 0 and er.validate(rep, strict=True) == []


def test_a_blocking_change_drops_the_level(tmp_path, monkeypatch):
    estate = stale_fixture(tmp_path, monkeypatch, None)  # det_coverage() maps a case / corpus change to None
    _, p = program_of(tmp_path, estate)
    assert (p["level"], p["level_current"]) == ("L2", True)


def test_det_coverage_keeps_scheduled_staleness_and_drops_blocking(monkeypatch):
    import det_coverage_ledger as dcl

    base = {"coverage": (4, 4, 2, 2), "measured_at": "deadbeef"}
    got = {}
    monkeypatch.setattr(dcl, "load", lambda: {})
    for name, last in {
        "current": {**base, "stale_inputs": [], "blocking": False},
        "harness": {**base, "stale_inputs": ["harness"], "blocking": False},
        "case": {**base, "stale_inputs": ["harness", "case"], "blocking": True},
        "none": None,
    }.items():
        monkeypatch.setattr(dcl, "last_coverage", lambda case, ledger, last=last: last)
        got[name] = er.det_coverage()[CASE]
    assert got["current"] == FULL
    assert got["harness"] == {"coverage": FULL, "stale_inputs": ["harness"], "stale_since": "deadbeef"}
    assert got["case"] is None and got["none"] is None


def test_the_release_gate_fails_while_a_level_is_stale(tmp_path, monkeypatch, capsys):
    stale_fixture(tmp_path, monkeypatch, STALE)
    assert er.main(["--check", "--live"]) == 1  # the files are what the tree makes, yet the gate fails
    assert "stale level" in capsys.readouterr().err
    stale_fixture(tmp_path, monkeypatch, FULL)
    assert er.main(["--check", "--live"]) == 0


def test_deltas_report_stale_against_current(tmp_path, monkeypatch, capsys):
    stale_fixture(tmp_path, monkeypatch, FULL)  # committed: current
    now = {**er.det_coverage(), CASE: STALE}  # the harness moved since
    monkeypatch.setattr(er, "det_coverage", lambda: now)
    assert er.main(["--deltas", "--live"]) == 0
    out = capsys.readouterr().out
    assert "1 stale" in out and "L3*" in out and "abc1234def56" in out and "harness, oracle" in out
    assert "L3 | L3*" in out  # level now (current) | level after refresh (stale)
