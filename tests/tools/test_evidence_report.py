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

REPORTS = sorted(er.FIXTURE.glob("*/report.json"))  # #5206: main commits no report; the tests read a frozen snapshot


@pytest.fixture(autouse=True)
def _snapshot(monkeypatch):
    monkeypatch.setattr(er, "OUT", er.FIXTURE)


TREE = next(
    (
        s["translator"]
        for f in REPORTS
        for s in [json.loads(f.read_text("utf-8")).get("measured", {}).get("survey", {})]
        if s.get("translator")
    ),
    None,
) or {"sha256": "tree-fp", "files": 3}  # the translator fingerprint of the tree, as these tests pin it (#4863, #4912)


@pytest.fixture(autouse=True)
def translator_in_the_tree_matches_the_surveys(monkeypatch):
    """#4863: a live build compares the survey's translator fingerprint with the tree's. Pin both so no test here
    depends on which translator commit the committed reports were surveyed at (#4912); the tests of the comparison
    itself set their own."""
    monkeypatch.setattr(er, "translator_now", lambda: TREE)
    monkeypatch.setattr(er, "translator_at", lambda sha: TREE)


@pytest.fixture(autouse=True, scope="module")
def tree_fingerprints_computed_once():
    """#5178: every live build fingerprints each case's inputs by hashing the tree (~27 of a build's ~35 s), and no test
    here edits the tree, so a case's fingerprint is computed once per module, not once per build."""
    import det_coverage_ledger as dcl

    real, seen = dcl.fingerprints, {}

    def once(case):
        if case not in seen:
            seen[case] = real(case)
        return dict(seen[case])  # (stale() only reads it)

    import proof_blockers as pb

    real_ledger, ledgers = pb._ledger, {}

    def ledger():
        """#5162: _ledger() stats every ledger file on each of ~1,000 calls a build; no test here writes one, and a
        test's own `load` or directory is a different key."""
        key = (id(dcl.load), str(dcl.LEDGER_DIR))
        if key not in ledgers:
            ledgers[key] = real_ledger()
        return ledgers[key]

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(dcl, "fingerprints", once)
        mp.setattr(pb, "_ledger", ledger)
        yield


@pytest.fixture(autouse=True, scope="module")
def published_tip_fetched_once():
    """Every live check fetched the `generated` branch's tip from origin (ls-remote + fetch, ~1.7 s a test): once a
    module now (a tip does not move between two tests)."""
    import generated_branch as gb

    real_tip, tips = gb.fetch_tip, {}

    def fetch_tip(*a, **k):
        key = (a, tuple(sorted(k.items())))
        if key not in tips:
            try:
                tips[key] = (real_tip(*a, **k), None)
            except RuntimeError as e:  # (no origin: every call raises, as it would have)
                tips[key] = (None, e)
        tip, err = tips[key]
        if err is not None:
            raise err
        return tip

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(gb, "fetch_tip", fetch_tip)
        yield


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


@pytest.mark.parametrize("path", REPORTS, ids=lambda p: p.parent.name)
def test_snapshot_report_validates(path):
    assert er.validate(json.loads(path.read_text("utf-8"))) == []


@pytest.mark.parametrize("path", [*REPORTS, er.FIXTURE / "README.md"], ids=lambda p: p.parent.name + "/" + p.name)
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
    para_net=None,
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
        **({"paragraph_net_pct": er.pct(*para_net)} if para_net else {}),
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
        ({"para": (9, 10), "para_net": (9, 9)}, "L4"),  # net of a reviewed infeasible paragraph
        ({"para": (9, 10), "para_net": (8, 9)}, "L2"),  # still under the bar after netting
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


@pytest.mark.slow(reason="builds the evidence report live over the Db2 case (#5178)")
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
    # hermetic: the committed report's other cases may themselves be stale (a refresh after a harness change marks
    # them so); only CASE's staleness is this fixture's to set, so every other measurement is pinned current
    others = {k: (v["coverage"] if isinstance(v, dict) else v) for k, v in old["measured"]["det_coverage"].items()}
    old["measured"]["det_coverage"] = {**others, CASE: cov}
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


@pytest.mark.slow(reason="builds the evidence report live over the Db2 case (#5178)")
def test_a_harness_only_change_keeps_the_last_level_marked_stale(tmp_path, monkeypatch):
    estate = stale_fixture(tmp_path, monkeypatch, STALE)
    rep, p = program_of(tmp_path, estate)
    assert (p["level"], p["level_current"]) == ("L3", False)  # not 0 / unknown
    assert p["stale_inputs"] == ["harness", "oracle"] and p["stale_since"] == "abc1234def5678"
    assert er.validate(rep, strict=True) == []
    # the counts of other programs move with the translator and the cases (#4863): only CASE's stale level is asserted
    s = rep["summary"]
    assert s["histogram"]["L3"] >= 1 and s["histogram_stale"]["L3"] == 1 and s["levels_stale"] == 1
    md = (tmp_path / estate / "report.md").read_text("utf-8")
    assert f"| {p['program']} | L3* |" in md and "stale since `abc1234def56` (harness, oracle)" in md
    assert re.search(r"L3\+: \d+ \(1 awaiting re-check\)", md) and "How to read" in md and "Stale levels" in md
    assert not er._FORBIDDEN.search(md)


@pytest.mark.slow(reason="builds the evidence report live over the Db2 case (#5176)")
def test_a_current_measurement_is_a_current_level(tmp_path, monkeypatch):
    estate = stale_fixture(tmp_path, monkeypatch, FULL)
    rep, p = program_of(tmp_path, estate)
    assert (p["level"], p["level_current"], p["stale_inputs"], p["stale_since"]) == ("L3", True, [], None)
    assert rep["summary"]["levels_stale"] == 0 and er.validate(rep, strict=True) == []


@pytest.mark.slow(reason="builds the evidence report live over the Db2 case (#5176)")
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


@pytest.mark.slow(reason="builds the evidence report live over the Db2 case twice (15-16 s, over the 15 s limit)")
def test_the_release_gate_fails_while_a_level_is_stale(tmp_path, monkeypatch, capsys):
    stale_fixture(tmp_path, monkeypatch, STALE)
    assert er.main(["--check", "--live"]) == 1  # the files are what the tree makes, yet the gate fails
    assert "stale level" in capsys.readouterr().err
    stale_fixture(tmp_path, monkeypatch, FULL)
    assert er.main(["--check", "--live"]) == 0


@pytest.mark.slow(reason="builds the evidence report live over the Db2 case (#5208)")
def test_the_release_gate_passes_the_published_non_live_report(tmp_path, monkeypatch):
    """#5208: the refresh publishes a non-live render; the release gate must pass it."""
    stale_fixture(tmp_path, monkeypatch, FULL)
    er.write(er.expected(False))  # what the refresh publishes
    assert er.main(["--check", "--live"]) == 0  # clean right after a refresh
    assert er.main(["--check"]) == 0


@pytest.mark.slow(reason="builds the evidence report live over the Db2 case (#5208)")
def test_the_release_gate_fails_an_edited_rendering_and_edited_data(tmp_path, monkeypatch):
    """Split from one test (#5610): each test's builds stay under the per-test time limit."""
    estate = stale_fixture(tmp_path, monkeypatch, FULL)
    er.write(er.expected(False))
    md = tmp_path / estate / "report.md"
    clean_md = md.read_text("utf-8")
    md.write_text(clean_md.replace("| L0 |", "| L0 (edited) |", 1), "utf-8")
    assert er.main(["--check", "--live"]) == 1  # edited rendering
    md.write_text(clean_md, "utf-8")
    js = tmp_path / estate / "report.json"
    clean_js = js.read_text("utf-8")
    js.write_text(clean_js.replace("evidence.py status at build time", "edited", 1), "utf-8")
    assert er.main(["--check", "--live"]) == 1  # edited data


@pytest.mark.slow(reason="builds the evidence report live over the Db2 case (#5208)")
def test_the_release_gate_fails_an_extra_file_until_it_is_removed(tmp_path, monkeypatch):
    estate = stale_fixture(tmp_path, monkeypatch, FULL)
    er.write(er.expected(False))
    (tmp_path / estate / "stray.md").write_text("x", "utf-8")
    assert er.main(["--check", "--live"]) == 1  # an extra file
    (tmp_path / estate / "stray.md").unlink()
    assert er.main(["--check", "--live"]) == 0


@pytest.mark.slow(reason="builds the evidence report live over the Db2 case (#5208)")
def test_the_release_gate_still_fails_a_stale_level_in_a_non_live_published_report(tmp_path, monkeypatch, capsys):
    stale_fixture(tmp_path, monkeypatch, STALE)
    er.write(er.expected(False))
    assert er.main(["--check", "--live"]) == 1
    assert "stale level" in capsys.readouterr().err
    assert er.main(["--check"]) == 0  # non-live compares content only


def test_deltas_report_stale_against_current(tmp_path, monkeypatch, capsys):
    stale_fixture(tmp_path, monkeypatch, FULL)  # committed: current
    now = {**er.det_coverage(), CASE: STALE}  # the harness moved since
    monkeypatch.setattr(er, "det_coverage", lambda: now)
    assert er.main(["--deltas", "--live"]) == 0
    out = capsys.readouterr().out
    assert "1 stale" in out and "L3*" in out and "abc1234def56" in out and "harness, oracle" in out
    assert "L3 | L3*" in out  # level now (current) | level after refresh (stale)


# ---- #4758: a Db2 case's det verdict from a sweep, else from the ledger the scheduled Db2 sweep wrote ----------------
GENAPP = "cics-genapp"
DB2_CASE = "genapp-lgacus01"  # a Db2 case: CI's per-PR det-sweep skips it, the evidence refresh's db2 job sweeps it
DB2_COV = [3, 3, 2, 8]  # lgacus01 has four reviewed infeasible outcomes: 2 covered leaves 2 open, still L3


def db2_fixture(tmp_path, monkeypatch, cov, sweep=None, isolate=False):
    """A tmp OUT holding the GenApp report refreshed --live with the ledger's measurement of DB2_CASE = cov (list:
    current; dict: stale on a scheduled input; None: no entry) and, optionally, a sweep row for it. isolate: every
    other case's ledger entry dropped too, so DB2_CASE is the only Db2 case with a verdict (#4863: the committed
    report's ledger grows as cases are added; a front-end case that LINKs a program would otherwise answer for it)."""
    old = json.loads((er.OUT / GENAPP / "report.json").read_text("utf-8"))
    others = dict.fromkeys(old["measured"]["det_coverage"]) if isolate else old["measured"]["det_coverage"]
    old["measured"]["det_coverage"] = {**others, DB2_CASE: cov}
    if sweep is not None:
        old["measured"]["sweeps"] = {**old["measured"]["sweeps"], DB2_CASE: sweep}
    (tmp_path / GENAPP).mkdir(exist_ok=True)
    monkeypatch.setattr(er, "OUT", tmp_path)
    (tmp_path / GENAPP / "report.json").write_text(er.dumps(old), "utf-8")
    monkeypatch.setattr(er, "record_status", lambda: old["measured"]["record_status"])
    monkeypatch.setattr(er, "det_coverage", lambda: old["measured"]["det_coverage"])
    er.write(er.expected(True))
    rep = json.loads((tmp_path / GENAPP / "report.json").read_text("utf-8"))
    p = next(p for p in rep["programs"] if p["program"].endswith("lgacus01.cbl"))
    assert er.validate(rep, strict=True) == []
    return rep, p


@pytest.mark.slow(reason="builds the evidence report live over the Db2 case (#5178)")
def test_a_db2_case_with_no_sweep_and_no_ledger_entry_is_not_run(tmp_path, monkeypatch):
    _, p = db2_fixture(tmp_path, monkeypatch, None, isolate=True)
    assert p["level"] == "L1" and p["equivalence"]["chosen"]["det"]["state"] == "not run"


@pytest.mark.slow(reason="builds the evidence report live over the Db2 case (#5178)")
def test_a_db2_verdict_from_a_sweep_input(tmp_path, monkeypatch):
    row = {"proved": True, "coverage": "proven on 8 scenarios, covering 3/3 paragraphs and 2/8 branches",
           "translated": "", "first_diff": "", "uncovered": None}  # fmt: skip
    _, p = db2_fixture(tmp_path, monkeypatch, None, sweep=row)
    det = p["equivalence"]["chosen"]["det"]
    assert (det["state"], det["source"]) == ("equal", "local sweep (proof_sweep.py --det-only)")
    assert (p["level"], p["level_current"]) == ("L3", True)  # 3/3 paragraphs, 2/8 branches
    assert p["coverage"]["source"] == "local sweep coverage line"


@pytest.mark.slow(reason="builds the evidence report live over the Db2 case (#5178)")
def test_a_db2_verdict_persists_from_the_ledger_on_a_run_without_db2(tmp_path, monkeypatch):
    """A push refresh skips the db2 job; the ledger entry the last full refresh wrote (proven cases only) carries."""
    _, p = db2_fixture(tmp_path, monkeypatch, DB2_COV)
    det = p["equivalence"]["chosen"]["det"]
    assert (det["state"], det["source"]) == ("equal", er.LEDGER_VERDICT)
    assert (p["level"], p["level_current"], p["stale_inputs"]) == ("L3", True, [])
    assert p["coverage"]["paragraphs"] == {"covered": 3, "live": 3} and p["coverage"]["branches"]["total"] == 8


@pytest.mark.slow(reason="builds the evidence report live over the Db2 case (#5178)")
def test_a_db2_verdict_from_a_stale_ledger_entry_is_marked_stale(tmp_path, monkeypatch):
    stale = {"coverage": DB2_COV, "stale_inputs": ["harness"], "stale_since": "abc1234def5678"}
    rep, p = db2_fixture(tmp_path, monkeypatch, stale)
    assert p["equivalence"]["chosen"]["det"]["state"] == "equal"
    assert (p["level"], p["level_current"]) == ("L3", False)
    assert p["stale_inputs"] == ["harness"] and p["stale_since"] == "abc1234def5678"
    assert rep["summary"]["histogram_stale"]["L3"] >= 1
    md = (tmp_path / GENAPP / "report.md").read_text("utf-8")
    assert f"| {p['program']} | L3* |" in md and not er._FORBIDDEN.search(md)


def test_the_ledger_never_overrides_a_known_unproven_db2_case(monkeypatch):
    """det_sweep_baseline.json's known-unproven entry and a sweep's verdict both outrank a ledger entry."""
    import proof_blockers as pb

    run = pb.Run(kind="equivalence", case=DB2_CASE, db2=True)
    run.gaps.add("known unproven: #1")
    assert er.ledger_verdicts({("x", "y"): [run]}, {DB2_CASE: DB2_COV}) == set()
    assert "known unproven: #1" in run.gaps
    run2 = pb.Run(kind="equivalence", case=DB2_CASE, db2=True)
    run2.gaps.add("not proven in CI: Db2 case (det-sweep runs --skip-db2)")
    assert er.ledger_verdicts({("x", "y"): [run2]}, {DB2_CASE: None}) == set() and run2.gaps
    assert er.ledger_verdicts({("x", "y"): [run2]}, {DB2_CASE: DB2_COV}) == {DB2_CASE} and not run2.gaps


@pytest.mark.slow(reason="builds the evidence report live over the Db2 case (#5178)")
def test_a_linked_program_never_inherits_the_cases_coverage_and_its_ledger_verdict_is_stale(tmp_path, monkeypatch):
    """LGSTSQ is only LINKed by the GenApp Db2 cases (here only DB2_CASE has a ledger entry): equal by the ledger is L2 (no coverage of its own, #4270),
    stale with the entry it rests on."""
    stale = {"coverage": DB2_COV, "stale_inputs": ["oracle"], "stale_since": "abc1234def5678"}
    # the VSAM front ends (lgapvs01, lgupvs01) LINK LGSTSQ too, and CI's ratchet proves them current (#5252): keep only
    # the Db2 case, which is the one this test is about
    real = er.pb.equivalence_runs
    monkeypatch.setattr(
        er.pb, "equivalence_runs", lambda: {k: [r for r in v if r.case == DB2_CASE] for k, v in real().items()}
    )
    db2_fixture(tmp_path, monkeypatch, stale, isolate=True)
    rep = json.loads((tmp_path / GENAPP / "report.json").read_text("utf-8"))
    p = next(p for p in rep["programs"] if p["program"].endswith("lgstsq.cbl"))
    c = p["equivalence"]["chosen"]
    assert (c["case"], c["role"], c["det"]["state"]) == (DB2_CASE, "linked", "equal")
    assert p["coverage"]["source"] is None and "LINKed" in p["next"][0]
    assert (p["level"], p["level_current"], p["stale_inputs"]) == ("L2", False, ["oracle"])


# ---- #4708: the options a level holds under --------------------------------------------------------------------------
def demo_estate(tmp_path, monkeypatch):
    from gitgalaxy.core import estate_options as eo

    def e(value, source, **kw):
        return {"value": value, "source": source, "note": "n", **kw}

    data = {
        "format": eo.FORMAT, "estate": "demo", "corpus": "demo",
        "compiler": {"product": e("Enterprise COBOL", "b/DEFAULT.jcl:7"), "version": e("6.3", "b/DEFAULT.jcl:7"),
                     "installation_defaults": {"NUMPROC": e("NOPFD", "assumed: IBM default")}},
        "parm": {"default": [{"option": "TRUNC", **e("OPT", "b/CICS.jcl:9", applied_value="STD", applied_note="why")}],
                 "programs": {}},
        "le": {"runtime_options": {"STORAGE": e("NONE", "assumed: IBM default")}}, "db2": {}, "cics": {},
    }  # fmt: skip
    (tmp_path / "demo.json").write_text(json.dumps(data))
    monkeypatch.setattr(eo, "ESTATE_OPTIONS_DIR", tmp_path)
    return data


def test_options_show_value_origin_and_found_vs_assumed(tmp_path, monkeypatch):
    demo_estate(tmp_path, monkeypatch)
    cards = [{"option": "INTDATE", "value": "LILIAN", "written": "INTDATE(LILIAN)", "line": 3}]
    o = er.program_options(None, "demo", "P.cbl", cards)
    by = {r["option"]: r for r in o["values"]}
    assert (by["INTDATE"]["value"], by["INTDATE"]["provenance"], by["INTDATE"]["source"]) == (
        "LILIAN",
        "found",
        "P.cbl:3",
    )
    assert (by["TRUNC"]["value"], by["TRUNC"]["provenance"], by["TRUNC"]["source"]) == ("STD", "found", "b/CICS.jcl:9")
    assert (by["NUMPROC"]["provenance"], by["NUMPROC"]["source"]) == ("assumed", "assumed: IBM default")
    assert by["ARITH"]["origin"] == "IBM default" and by["ARITH"]["provenance"] == "assumed"
    assert o["found"] == 2 and o["assumed"] == len(o["values"]) - 2
    assert o["compiler"] == {"product": "Enterprise COBOL", "version": "6.3"}
    # the declared difference: the estate says TRUNC(OPT), the proof ran STD
    assert [(d["option"], d["declared"], d["applied"]) for d in o["deviations"]] == [("TRUNC", "OPT", "STD")]
    text = "\n".join(er.options_lines(o))
    assert "TRUNC(STD) [found at b/CICS.jcl:9]" in text and "NUMPROC(NOPFD) [assumed: IBM default]" in text
    assert "Declared option difference:** TRUNC is OPT in the estate, applied as STD" in text
    # a program card overrides the PARM, so the deviation disappears
    o2 = er.program_options(
        None, "demo", "P.cbl", [{"option": "TRUNC", "value": "BIN", "written": "TRUNC(BIN)", "line": 1}]
    )
    assert o2["deviations"] == [] and {r["option"]: r["value"] for r in o2["values"]}["TRUNC"] == "BIN"


def test_options_carry_the_records_declared_differences_and_the_estate_table(tmp_path, monkeypatch):
    demo_estate(tmp_path, monkeypatch)
    diff = [{"kind": "option", "option": "TRUNC", "declared": "OPT", "applied": "STD", "note": "proven as STD"}]
    o = er.program_options(None, "demo", "P.cbl", [], diff)
    assert o["record_differences"][0]["note"] == "shown equal as STD"  # reworded to the report's vocabulary
    est = er.estate_options("demo", [{"options": o}])
    assert est["counts"] == {"found": 3, "assumed": 2} and est["programs_with_deviation"] == 1
    assert est["parm_default"][0]["applied_value"] == "STD" and est["sections"]["le"] == {"found": 0, "assumed": 1}
    md = "\n".join(er.estate_options_lines(est))
    assert "| compiler | version: 6.3 | found | b/DEFAULT.jcl:7 |" in md
    assert "TRUNC(OPT) (applied as STD: declared difference) | found | b/CICS.jcl:9" in md
    assert not er._FORBIDDEN.search(md + "\n".join(er.options_lines(o)))


def test_an_estate_without_an_options_file_is_ibm_defaults_assumed(tmp_path, monkeypatch):
    from gitgalaxy.core import estate_options as eo

    monkeypatch.setattr(eo, "ESTATE_OPTIONS_DIR", tmp_path)
    o = er.program_options(None, "none", "P.cbl", [])
    assert o["found"] == 0 and o["assumed"] == len(o["values"]) > 0 and not o["estate_file"]
    est = er.estate_options("none", [{"options": o}])
    assert est["estate_file"] is None and "IBM's default (assumed)" in "\n".join(er.estate_options_lines(est))


def test_the_options_section_validates_and_an_older_report_still_does(tmp_path, monkeypatch):
    demo_estate(tmp_path, monkeypatch)
    rep = copy.deepcopy(json.loads(REPORTS[0].read_text("utf-8")))
    for p in rep["programs"]:
        p["options"] = er.program_options(None, "demo", p["program"], [])
    rep["options"] = er.estate_options("demo", rep["programs"])
    assert er.validate(rep) == []
    bad = copy.deepcopy(rep)
    bad["programs"][0]["options"]["values"][0]["provenance"] = "guessed"
    assert any("provenance" in e for e in er.validate(bad))
    del rep["options"]
    for p in rep["programs"]:
        del p["options"]
    assert er.validate(rep) == []  # committed before #4708: no options until the bot regenerates it
    assert any("options" in e for e in er.validate(rep, strict=True))


def test_options_are_deterministic(tmp_path, monkeypatch):
    demo_estate(tmp_path, monkeypatch)
    cards = [{"option": "INTDATE", "value": "LILIAN", "written": "INTDATE(LILIAN)", "line": 3}]
    a, b = (er.program_options(None, "demo", "P.cbl", cards) for _ in range(2))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert er.estate_options("demo", [{"options": a}]) == er.estate_options("demo", [{"options": b}])
    assert "\n".join(er.options_lines(a)) == "\n".join(er.options_lines(b))


# ---- #4863 step 2: a survey can be stale -------------------------------------------------------------------------------
def test_the_fingerprint_covers_the_translator_and_nothing_else():
    files = {
        "gitgalaxy/tools/cobol_to_java/det/stmt.py": b"a",
        "gitgalaxy/tools/cobol_to_java/det/cobolrt/Cobol.java": b"b",
        "gitgalaxy/standards/cics/commands/api.py": b"c",
        "gitgalaxy/core/compiler_options.py": b"d",
        "docs/readme.md": b"e",
        "gitgalaxy/tools/cobol_to_java/det/__pycache__/stmt.cpython-312.pyc": b"f",
    }

    def fp(**changed):
        data = {**files, **changed}
        return er.translator_fingerprint(tuple(sorted(data)), data.__getitem__)

    base = fp()
    assert base["files"] == 4  # the four translator inputs, not the doc or the bytecode
    assert (
        fp(**{"docs/readme.md": b"x", "gitgalaxy/tools/cobol_to_java/det/__pycache__/stmt.cpython-312.pyc": b"x"})
        == base
    )
    for path in ("gitgalaxy/tools/cobol_to_java/det/stmt.py", "gitgalaxy/tools/cobol_to_java/det/cobolrt/Cobol.java",
                 "gitgalaxy/standards/cics/commands/api.py", "gitgalaxy/core/compiler_options.py"):  # fmt: skip
        assert fp(**{path: b"changed"})["sha256"] != base["sha256"], path


def test_the_inputs_cover_what_the_translator_imports():
    """Every gitgalaxy module the det translator (or the CICS spec) imports is a fingerprint input: a new import cannot
    leave the survey's fingerprint blind to it."""
    import ast

    repo = er.REPO
    roots = [
        *(repo / "gitgalaxy/tools/cobol_to_java/det").rglob("*.py"),
        *(repo / "gitgalaxy/standards/cics").rglob("*.py"),
    ]
    files = tuple(er.ev._files_now())
    mods = set()
    for path in roots:
        for n in ast.walk(ast.parse(path.read_text("utf-8"))):
            if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("gitgalaxy.") and not n.level:
                mods.add(n.module)
                mods |= {f"{n.module}.{a.name}" for a in n.names}
    covered = set(er.ev._match(files, list(er.TRANSLATOR_INPUTS), list(er.TRANSLATOR_EXCLUDE)))
    for m in sorted(mods):
        rel = m.replace(".", "/")
        if f"{rel}.py" in files or f"{rel}/__init__.py" in files:
            assert f"{rel}.py" in covered or f"{rel}/__init__.py" in covered, (
                f"{m} is read by the translator but not fingerprinted"
            )
    assert {Path(p).name for p in covered} >= {"stmt.py", "det_survey.py", "Cobol.java"}


def test_survey_check_compares_the_stored_fingerprint_with_the_tree():
    ok = er.survey_check({"sha": "s", "translator": {"sha256": "A"}}, {"sha256": "A"})
    assert ok == {"fingerprint": "A", "current": True}
    bad = er.survey_check({"sha": "s", "translator": {"sha256": "A"}}, {"sha256": "B"})
    assert bad["current"] is False and bad["now"] == "B" and "translator changed" in bad["why"]


def test_a_survey_without_a_fingerprint_is_checked_through_its_commit():
    old = {"sha": "abc"}  # made before the fingerprint was stored
    assert er.survey_check(old, {"sha256": "A"}, at=lambda sha: {"sha256": "A"})["current"] is True
    assert er.survey_check(old, {"sha256": "A"}, at=lambda sha: {"sha256": "Z"})["current"] is False
    unknown = er.survey_check(old, {"sha256": "A"}, at=lambda sha: None)  # a shallow clone does not have the commit
    assert unknown["current"] is False and "not here" in unknown["why"]


def survey_estate(tmp_path, monkeypatch, stored, now):
    """A tmp OUT with one estate surveyed with translator fingerprint `stored` (None: the older format), the tree's
    translator being `now`: a whole program (L1) and one with a hole (L0). Records and coverage are pinned empty."""
    pytest.importorskip("tree_sitter_language_pack")  # measure() parses the EXEC commands
    src = tmp_path / "src" / "zecs" / "Source"
    src.mkdir(parents=True)
    for name in ("P1", "P2"):
        (src / f"{name}.cbl").write_text("000100 PROCEDURE DIVISION.\n000200     EXEC CICS RETURN END-EXEC.\n")
    rows = {
        ("zecs", "Source/P1.cbl"): {"program": "Source/P1.cbl", "statements": 2, "translated": 2, "holes": []},
        ("zecs", "Source/P2.cbl"): {"program": "Source/P2.cbl", "statements": 2, "translated": 1, "holes": ["x"]},
    }
    survey = {"sha": "abc1234def5678", "scope": "test", "label": "before"}
    if stored is not None:
        survey["translator"] = {"sha256": stored, "files": 3}
    monkeypatch.setattr(er, "OUT", tmp_path / "out")
    monkeypatch.setattr(er, "record_status", dict)
    monkeypatch.setattr(er, "det_coverage", dict)
    # zecs is in no ledger, and these tests are about the translator's currency: the ledger readers answer "no entry"
    # at once instead of re-reading and re-fingerprinting the real ledger for every program of every build (#5162)
    import proof_blockers as pb

    monkeypatch.setattr(pb, "ledger_linked", lambda *a, **k: {})
    monkeypatch.setattr(pb, "ledger_coverage", lambda *a, **k: None)
    monkeypatch.setattr(er, "translator_now", lambda: {"sha256": now, "files": 3})
    monkeypatch.setattr(er, "translator_at", lambda sha: {"sha256": "OLD", "files": 3})
    measured = er.measure("zecs", rows, [tmp_path / "src"], survey, {})
    (er.OUT / "zecs").mkdir(parents=True)
    (er.OUT / "zecs" / "report.json").write_text(er.dumps(er.build(measured, "zecs", BARS)), "utf-8")
    return measured, rows, survey


def levels(estate_dir):
    rep = json.loads((estate_dir / "report.json").read_text("utf-8"))
    return rep, {p["program"]: p for p in rep["programs"]}


def test_a_translator_merge_without_a_refresh_fails_the_release_gate_and_a_refresh_passes(
    tmp_path, monkeypatch, capsys
):
    measured, rows, survey = survey_estate(tmp_path, monkeypatch, "A", "A")
    er.write(er.expected(True))
    assert er.main(["--check", "--live"]) == 0  # the survey ran the translator in the tree

    monkeypatch.setattr(er, "translator_now", lambda: {"sha256": "B", "files": 3})  # a translator merge, no refresh
    assert er.main(["--check", "--live"]) == 1
    err = capsys.readouterr().err
    assert "stale survey: zecs surveyed at abc1234def56" in err and "stale level: zecs/Source/P1.cbl L1*" in err
    assert "Source/P2.cbl" not in err  # L0 is the inventory: it does not read the translator

    # the report says so: stale on `translator`, counted apart, rendered
    er.write(er.expected(True))
    rep, progs = levels(er.OUT / "zecs")
    p1, p2 = progs["Source/P1.cbl"], progs["Source/P2.cbl"]
    assert (p1["level"], p1["level_current"], p1["stale_inputs"], p1["survey_stale"]) == (
        "L1",
        False,
        ["translator"],
        True,
    )
    assert p1["stale_since"] == "abc1234def5678"
    assert (p2["level"], p2["level_current"], p2["survey_stale"]) == ("L0", True, False)
    s = rep["summary"]
    assert (s["levels_stale"], s["levels_stale_survey"], s["histogram_stale_survey"]["L1"]) == (1, 1, 1)
    assert rep["survey_translator"]["current"] is False and rep["survey_translator"]["now"] == "B"
    assert er.validate(rep, strict=True) == []
    md = (er.OUT / "zecs" / "report.md").read_text("utf-8")
    assert "Stale survey" in md and "| Source/P1.cbl | L1* |" in md and "stale because the translation survey" in md
    assert "stale on `translator`" in md and not er._FORBIDDEN.search(md)
    assert "stale (translator" not in er.deltas_markdown(True) and "translation survey is stale" in er.deltas_markdown(
        True
    )

    # a refresh = the translation surveyed again with the translator now in the tree
    survey["translator"] = {"sha256": "B", "files": 3}
    (er.OUT / "zecs" / "report.json").write_text(
        er.dumps(er.build(er.measure("zecs", rows, [tmp_path / "src"], survey, {}), "zecs", BARS)), "utf-8"
    )
    er.write(er.expected(True))
    assert er.main(["--check", "--live"]) == 0
    assert levels(er.OUT / "zecs")[0]["survey_translator"]["current"] is True


def test_a_committed_report_is_not_failed_by_a_translator_merge_unless_live(tmp_path, monkeypatch):
    """The non-live check compares the report with the frozen measurement: only the live gate looks at the tree."""
    survey_estate(tmp_path, monkeypatch, "A", "A")
    er.write(er.expected())
    monkeypatch.setattr(er, "translator_now", lambda: {"sha256": "B", "files": 3})
    assert er.main(["--check"]) == 0


def test_a_report_surveyed_before_the_fingerprint_stays_as_committed_while_its_commit_is_current(tmp_path, monkeypatch):
    survey_estate(tmp_path, monkeypatch, None, "OLD")  # no stored fingerprint; the commit it ran at has the tree's
    er.write(er.expected(True))
    rep, progs = levels(er.OUT / "zecs")
    assert (
        "survey_translator" not in rep and "survey_stale" not in progs["Source/P1.cbl"]
    )  # the older format, unchanged
    assert er.validate(rep, strict=True) == [] and er.main(["--check", "--live"]) == 0
    monkeypatch.setattr(er, "translator_now", lambda: {"sha256": "NEW", "files": 3})  # the translator moved
    assert er.main(["--check", "--live"]) == 1


def test_a_survey_run_stores_the_translator_fingerprint(tmp_path, monkeypatch):
    pytest.importorskip("tree_sitter_language_pack")
    monkeypatch.setattr(er, "translator_now", lambda: {"sha256": "STORED", "files": 3})
    src = tmp_path / "src" / "zecs" / "Source"
    src.mkdir(parents=True)
    (src / "P1.cbl").write_text("000100 PROCEDURE DIVISION.\n")
    run = tmp_path / "svy" / "before-main"
    run.mkdir(parents=True)
    (run / "survey.json").write_text(json.dumps({"zecs": [{"program": "Source/P1.cbl", "statements": 1,
                                                             "translated": 1, "holes": []}]}))  # fmt: skip
    out = tmp_path / "out"
    assert (
        er.main(["zecs", "--survey", str(tmp_path / "svy"), "--corpora", str(tmp_path / "src"), "--out", str(out)]) == 0
    )
    rep = json.loads((out / "zecs" / "report.json").read_text("utf-8"))
    assert rep["measured"]["survey"]["translator"] == {"sha256": "STORED", "files": 3}
    assert rep["survey_translator"] == {"fingerprint": "STORED", "current": True}


def test_options_list_the_runtime_values_with_the_tables_verdict(tmp_path, monkeypatch):
    demo_estate(
        tmp_path, monkeypatch
    )  # its LE STORAGE is "NONE": not the table's full default, so a declared difference
    o = er.program_options(None, "demo", "P.cbl", [])
    (row,) = o["runtime"]
    assert (row["option"], row["value"], row["effect"], row["provenance"]) == (
        "le.runtime_options.STORAGE",
        "NONE",
        "declared",
        "assumed",
    )
    assert "le.runtime_options.STORAGE=NONE [declared; assumed" in "\n".join(er.options_lines(o))
    # a corpus with no estate file has no runtime values, and the key is absent (older reports stay valid)
    assert "runtime" not in er.program_options(None, "nofile", "P.cbl", [])


def test_a_reviewed_infeasible_paragraph_is_netted_from_the_paragraph_count_only_when_unreached(monkeypatch):
    import infeasible_outcomes as io

    ledger = {"c": [{"unit": "6000-EXIT", "kind": "PARAGRAPH", "outcome": "entered", "family": "R", "reason": "r"}]}
    monkeypatch.setattr(io, "stated", lambda case, *a, **k: ledger.get(case, []))
    real = io.adjust
    monkeypatch.setattr(io, "adjust", lambda case, cov, unc, led=None: real(case, cov, unc, ledger))
    case = {"case": "c", "record": None}
    got = er.coverage_of(case, {}, {"c": [15, 16, 38, 40]})  # counts only: every entry taken as uncovered
    assert (got["paragraph_pct"], got["paragraph_net_pct"]) == (93.8, 100.0)
    assert got["paragraphs_net"] == {"covered": 15, "live": 15}
    assert er.level_of(program(para=(15, 16), para_net=(15, 15), branch=(38, 40), net=(38, 38)), BARS)[0] == "L4"
    # a sweep that reached the paragraph refutes the claim: nothing netted, raw percent stays
    row = {"c": {"coverage": "proven on 2 scenarios, covering 16/16 paragraphs and 38/40 branches", "uncovered": []}}
    reached = er.coverage_of(case, row, {})
    assert "paragraph_net_pct" not in reached and reached["infeasible_refuted"] == ["6000-EXIT:paragraph"]
    # no paragraph entry: no optional key
    assert "paragraph_net_pct" not in er.coverage_of({"case": "d", "record": None}, {}, {"d": [15, 16, 38, 40]})
