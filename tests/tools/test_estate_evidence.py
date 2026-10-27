"""estate_evidence (#4054): the estate roll-up of the per-program evidence records places every committed record on
the ladder, rolls the numbers up exactly, applies the callee-hole rule and never words a level as a verdict."""

import copy
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import estate_evidence as ee
import evidence as ev


@pytest.fixture(scope="module")
def report():
    return ee.build(live=False)


@pytest.fixture(scope="module")
def rows(report):
    return [r for e in report["estates"].values() for r in e["programs"]]


def _row(**kw):
    base = {
        "has_record": True, "executed_equivalent": True, "holes": 0, "stale": [], "approval": None,
        "proof": {"runs": 3, "fault_runs": 1}, "differences": 0,
        "coverage": {"paragraphs": [4, 4], "branches": [9, 9], "uncovered_branches": 0},
        "mutation": {"killed": 5, "judged": 6, "adjusted_judged": 5, "stillborn": 0, "stale": None, "open_survivors": 0,
                     "survivors": {"case_gap": 0, "harness_gap": 0, "equivalent": 1, "unreachable": 0, "untriaged": 0}},
    }  # fmt: skip
    return {**base, **kw}


# ---- the whole committed record class -------------------------------------------------------------------------------


def test_every_committed_port_is_in_a_reported_estate_with_a_valid_record(rows, report):
    assert not report["refused_estates"]
    assert {r["key"] for r in rows} == {t.key for t in ev.targets()}
    for r in rows:
        assert r["has_record"], r["key"]
        assert ev.validate(json.loads(Path(ev.REPO_ROOT, r["record"]).read_text("utf-8"))) == [], r["key"]


def test_every_record_gets_a_level_a_reason_and_a_status_the_ladder_knows(rows):
    for r in rows:
        assert r["level"] in ee.LEVELS, r["key"]
        assert r["status"] in {"proven, approved", "proven, unapproved", "not-proven", "stale", "no-record"}, r["key"]
        if r["level"] != "E4":
            assert r["why"], f"{r['key']} stops below E4 without saying why"
        assert r["oracle"], r["key"]


def test_a_level_never_outruns_its_numbers(rows):
    for r in rows:
        if r["level"] in ("E2", "E3", "E4"):
            assert r["executed_equivalent"] and not r["holes"], r["key"]
        if r["level"] in ("E3", "E4"):
            c = r["coverage"]
            assert c["paragraphs"][0] == c["paragraphs"][1] and c["branches"][0] == c["branches"][1], r["key"]
        if r["level"] == "E4":
            assert r["mutation"] and not r["mutation"]["survivors"]["untriaged"], r["key"]


# Records whose mutation run has 60 survivors awaiting the owner's review (#5856): a ratchet that only shrinks, the same
# case as MUTATION_PENDING in tests/cobol_mainframe/test_evidence.py (a ledger is committed with its reviewed survivors).
MUTATION_UNREVIEWED = {
    "carddemo-cbstm03a",
    "carddemo-cbpaup0c",
    "carddemo-copaua0c",
    "carddemo-copaus0c",
    "carddemo-copaus1c",
}


def test_every_committed_carddemo_record_has_a_mutation_section():
    """#4048: a burned CardDemo record left at `mutation: null` has no score; this includes a port_from case
    (carddemo-tranview-generated), which has a record but no port/ of its own and is not in targets()."""
    records = sorted((ev.CASES).glob("carddemo-*/" + ev.RECORD_NAME))
    assert records
    for path in records:
        rec = json.loads(path.read_text(encoding="utf-8"))
        if path.parent.name in MUTATION_UNREVIEWED:
            assert not rec["mutation"], f"drop {path.parent.name} from MUTATION_UNREVIEWED"
            continue
        assert rec["mutation"], path.parent.name
        assert not rec["mutation"]["survivors"]["untriaged"], path.parent.name


def test_the_rollup_adds_up_to_the_rows(report, rows):
    s = report["summary"]
    assert s["programs"] == len(rows)
    assert sum(s["levels"].values()) == len(rows)
    assert s["paragraphs"][0] == sum(r["coverage"]["paragraphs"][0] for r in rows if r["coverage"])
    assert s["branches"][1] == sum(r["coverage"]["branches"][1] for r in rows if r["coverage"])
    assert s["mutation"]["killed"] == sum(r["mutation"]["killed"] for r in rows if r["mutation"])
    assert s["mutation"]["open_survivors"] == sum(r["mutation"]["open_survivors"] for r in rows if r["mutation"])
    assert s["declared_differences"] == sum(r["differences"] for r in rows)
    for e in report["estates"].values():
        assert e["summary"]["programs"] == len(e["programs"])
    assert sum(e["summary"]["programs"] for e in report["estates"].values()) == len(rows)


def test_the_crucible_is_its_own_estate_and_every_estate_is_a_burned_one(report):
    assert ee.CRUCIBLE_ESTATE in report["estates"]
    for name in report["estates"]:
        assert ee.reportable(name), name


def test_a_non_burned_estate_is_refused():
    assert not ee.reportable("some-census-repo")
    assert ee.reportable("zecs") and ee.reportable(ee.CRUCIBLE_ESTATE)


def test_the_rendering_never_says_proven_verified_or_guaranteed(report):
    text = ee.render(report)
    bare = re.sub(r"ported_unproven", "", text)
    for word in ee.FORBIDDEN_WORDS:
        assert not re.search(word, bare, re.I), word
    assert "Lines" in text


def test_the_rendering_names_every_program_and_every_level(report, rows):
    text = ee.render(report)
    for r in rows:
        assert r["program"] in text
    for lv in ee.LEVELS:
        assert f"**{lv}**" in text


def test_the_json_report_round_trips(report):
    assert json.loads(json.dumps(report))["format"] == ee.FORMAT


def test_the_live_build_reads_the_tree_and_marks_stale_levels():
    live = ee.build(live=True)
    for e in live["estates"].values():
        for r in e["programs"]:
            assert r["level_current"] == (not r["stale"])


def test_estate_filter_and_out_must_be_outside_the_repo(tmp_path, capsys):
    assert ee.main(["no-such-estate", "--no-live"]) == 2
    assert ee.main(["--out", str(ev.REPO_ROOT / "scratch_ee"), "--no-live"]) == 2
    assert ee.main(["--out", str(tmp_path / "o"), "--no-live", ee.CRUCIBLE_ESTATE]) == 0
    assert (tmp_path / "o" / "report.md").is_file() and (tmp_path / "o" / "report.json").is_file()
    capsys.readouterr()


# ---- the placement rules, on synthetic rows -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("row", "callee_holes", "level"),
    [
        (_row(has_record=False), [], "E0"),
        (_row(executed_equivalent=False), [], "E1"),
        (_row(executed_equivalent=False, proof={"runs": None, "fault_runs": None}), [], "E1"),
        (_row(holes=2), [], "E1"),
        (_row(), ["other-case"], "E1"),  # owner policy 4: a callee with holes caps the caller
        (_row(coverage=None), [], "E2"),
        (_row(coverage={"paragraphs": [3, 4], "branches": [9, 9], "uncovered_branches": 0}), [], "E2"),
        (_row(coverage={"paragraphs": [4, 4], "branches": [8, 9], "uncovered_branches": 1}), [], "E2"),
        (_row(mutation=None), [], "E3"),
        (_row(mutation={**_row()["mutation"], "survivors": {**_row()["mutation"]["survivors"], "untriaged": 1}}), [], "E3"),
        (_row(mutation={**_row()["mutation"], "stale": "stale: port changed"}), [], "E3"),
        (_row(), [], "E4"),
        (_row(mutation={**_row()["mutation"], "open_survivors": 2}), [], "E4"),  # triaged case gaps are listed, not hidden
    ],
)  # fmt: skip
def test_place(row, callee_holes, level):
    row = copy.deepcopy(row)
    ee.place(row, callee_holes)
    assert row["level"] == level
    assert level == "E4" or row["why"]


def test_a_stale_row_keeps_its_level_and_is_marked():
    row = _row(stale=["generator"])
    ee.place(row, [])
    assert row["level"] == "E4" and row["level_current"] is False


def test_callee_holes_are_transitive_and_cycle_safe():
    ok = {"executed_equivalent": True, "holes": 0}
    rows = {"a": ok, "b": ok, "c": {**ok, "holes": 1}, "d": {**ok, "executed_equivalent": False}}
    links = {"a": ["b"], "b": ["c", "a"], "c": [], "d": []}
    assert ee.reaches_holes("a", rows, links) == ["c"]
    assert ee.reaches_holes("c", rows, links) == []
    assert ee.reaches_holes("x", {**rows, "x": ok}, {"x": ["d", "missing"]}) == ["d", "missing"]


def test_summarise_counts_open_survivors_and_unmeasured_programs():
    a = _row(level="E4", mutation={**_row()["mutation"], "open_survivors": 2})
    b = _row(level="E2", mutation=None, coverage=None, approval={"decision": "approved", "current": True},
             stale=["harness"])  # fmt: skip
    s = ee.summarise([a, b])
    assert s["programs"] == 2 and s["levels"]["E4"] == 1 and s["levels"]["E2"] == 1
    assert s["mutation"]["programs_measured"] == 1 and s["mutation"]["open_survivors"] == 2
    assert s["paragraphs"] == [4, 4] and s["approved_current"] == 1 and s["stale_records"] == 1


def test_a_linked_equivalence_case_and_its_crucible_siblings_have_callees():
    by_program = {}
    for t in ev.targets():
        if t.kind != "crucible":
            by_program.setdefault((t.corpus.get("name", ""), t.program), []).append(t)
    linked = [t for t in ev.targets() if t.programs]
    assert linked
    assert any(k.startswith("program:") for t in linked for k in ee.callees(t, by_program))  # no record of its own
    pair = next(t for t in ev.targets() if t.key == "crucible:ca-link-lengths/CALINK")
    assert ee.callees(pair, by_program) == ["crucible:ca-link-lengths/CASUB"]


# ---- lines (#4054) --------------------------------------------------------------------------------------------------

FIXED = (
    "       IDENTIFICATION DIVISION.\n"
    "       PROGRAM-ID. DEMO.\n"
    "      * a comment\n"
    "       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    "       01  X PIC 9.\n"
    "\n"
    "       PROCEDURE DIVISION.\n"
    "       MAIN-PARA.\n"
    "           MOVE 1 TO X.\n"
    "      * another comment\n"
    "           STOP RUN.\n"
)
FREE = (
    ">>SOURCE FORMAT FREE\n"
    "IDENTIFICATION DIVISION.\n"
    "PROGRAM-ID. DEMO.\n"
    "*> a comment\n"
    "PROCEDURE DIVISION.\n"
    "MAIN-PARA.\n"
    "    MOVE 1 TO X.\n"
    "\n"
    "    STOP RUN.\n"
)


@pytest.mark.parametrize("text", [FIXED, FREE], ids=["fixed", "free"])
def test_source_lines_count_procedure_code_lines_only(tmp_path, text):
    src = tmp_path / "DEMO.cbl"
    src.write_text(text, encoding="utf-8")
    got = ee.source_lines(src)
    assert got["procedure"] == 3  # MAIN-PARA, MOVE, STOP RUN: no comment, no blank, no header
    assert got["procedure"] < got["total"]
    assert ee.source_lines(tmp_path / "ABSENT.cbl") is None
    assert ee.source_lines(None) is None


def test_lines_roll_up_by_level_and_weight_coverage():
    rows = [
        {**_row(), "level": "E4", "lines": {"procedure": 100, "total": 150}},
        {
            **_row(coverage={"paragraphs": [1, 2], "branches": [1, 2], "uncovered_branches": 1}),
            "level": "E2",
            "lines": {"procedure": 50, "total": 80},
        },  # fmt: skip
        {**_row(), "level": "E1"},  # no lines: not measured, left out of the totals
    ]
    ln = ee.summarise(rows)["lines"]
    assert ln["programs_measured"] == 2
    assert (ln["procedure"], ln["total"]) == (150, 230)
    assert ln["at_or_above"] == {"E2": 150, "E3": 100, "E4": 100}
    assert ln["paragraph_weighted"] == [125, 150]


def test_without_any_source_lines_are_not_measured():
    s = ee.summarise([{**_row(), "level": "E4"}])
    assert s["lines"] == ee.NOT_MEASURED_LINES
    assert "not measured" in ee._lines_summary(s["lines"], 1)


def test_a_missing_checkout_degrades_to_not_measured(monkeypatch):
    monkeypatch.setattr(ee, "source_path", lambda t: None)
    rep = ee.build(live=False)
    assert rep["summary"]["lines"] == ee.NOT_MEASURED_LINES
    assert all("lines" not in r for e in rep["estates"].values() for r in e["programs"])
    assert "not measured" in ee.render(rep)


def test_the_committed_estates_have_lines_when_the_corpora_are_present(report, rows):
    measured = [r for r in rows if r.get("lines")]
    if not measured:
        pytest.skip("corpus checkouts are not present")
    for r in measured:
        assert 0 < r["lines"]["procedure"] <= r["lines"]["total"], r["key"]
    ln = report["summary"]["lines"]
    assert ln["procedure"] == sum(r["lines"]["procedure"] for r in measured)
    assert ln["at_or_above"]["E2"] <= ln["procedure"]
