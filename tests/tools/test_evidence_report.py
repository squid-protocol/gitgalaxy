"""evidence_report (#4601): the committed purchaser-facing reports are current, never say "proven" / "verified" /
"guaranteed", take every number they print from their JSON, and place programs at the level their numbers allow."""

import copy
import json
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
    missing = set(_NUMBER.findall((er.OUT / "README.md").read_text("utf-8"))) - have
    assert not missing, sorted(missing)


# ---- levels ------------------------------------------------------------------------------------------------------
def program(*, whole=True, case=True, det="equal", record=True, stale=(), para=(10, 10), branch=(10, 10), backed=True):
    rec = None
    if record:
        rec = {"stale_inputs": list(stale), "verdict": "all equal", "scenarios": 3}
    chosen = {"case": "c", "role": "program", "det": {"state": det, "why": ["x"]}, "record": rec} if case else None
    cov = {
        "paragraph_pct": er.pct(*para) if para else None,
        "branch_pct": er.pct(*branch) if branch else None,
    }
    return {
        "translation": {"whole": whole, "refused": None, "hole_count": 0 if whole else 2},
        "equivalence": {"cases": [chosen] if chosen else [], "chosen": chosen},
        "coverage": cov,
        "oracle_backing": [{"command": "RETURN", "backed": backed}],
    }


BARS = {"paragraphs": 90.0, "branches": 80.0}


@pytest.mark.parametrize(
    ("kw", "level"),
    [
        ({"whole": False}, "L0"),
        ({"case": False}, "L1"),
        ({"det": "not run"}, "L1"),
        ({"record": False}, "L1"),
        ({"stale": ("harness",)}, "L1"),  # a stale record is never shown as current
        ({"para": (8, 10)}, "L2"),
        ({"para": None}, "L2"),  # coverage not measured: not above any bar
        ({"branch": (7, 10)}, "L3"),
        ({}, "L4"),  # never L5: assumption reach is not measured
        ({"backed": False}, "L4"),
    ],
)
def test_levels_are_cumulative_and_never_reach_l5_unmeasured(kw, level):
    lvl, nxt = er.level_of(program(**kw), BARS)
    assert lvl == level
    assert nxt, "a level always says what the next one needs"
    if level == "L4":
        assert any("not measured" in n for n in nxt)


def test_the_bars_are_parameters():
    p = program(para=(9, 10), branch=(9, 10))
    assert er.level_of(p, BARS)[0] == "L4"
    assert er.level_of(p, {"paragraphs": 95.0, "branches": 80.0})[0] == "L2"
    assert all(str(b) in json.dumps(er.level_table({"paragraphs": 95.0, "branches": 85.0})) for b in (95.0, 85.0))


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
    er.write({tmp_path / "README.md": er.render_index([json.loads((tmp_path / estate / "report.json").read_text())])})
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
