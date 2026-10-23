"""#5280: the progress page renders from fixtures, its denominators are fixed, the ETA never prints a date the numbers
cannot support, and the READMEs carry no hand-written status number (they link the generated page)."""

import json
import re
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import progress_report as pr  # noqa: E402

REPO = TOOLS.parents[1]
FIXTURE_REPORTS = REPO / "tests" / "fixtures" / "evidence_report"
END = "2026-10-16T12:00:00Z"


def issue(n, scope="core", state="open", created="2026-09-01T00:00:00Z", closed=None, milestone=None, extra=()):
    return {
        "number": n,
        "state": state,
        "created_at": created,
        "closed_at": closed,
        "labels": [f"scope:{scope}", *extra],
        "milestone": milestone,
    }


def cache(*issues):
    return {"fetched_at": END, "issues": list(issues)}


# ---- the ETA, both directions ---------------------------------------------------------------------------------------


def test_eta_is_not_converging_when_the_net_is_zero_or_positive():
    # 2 opened and 2 closed in the window: net 0
    zero = pr.issues_component(
        cache(
            issue(1),
            issue(2),
            issue(3, state="closed", created="2026-10-12T00:00:00Z", closed="2026-10-13T00:00:00Z"),
            issue(4, state="closed", created="2026-10-12T00:00:00Z", closed="2026-10-14T00:00:00Z"),
        )
    )
    assert zero["core_last_window"]["net_closed"] == 0 and zero["eta"] == pr.NOT_CONVERGING
    # 3 opened, 1 closed: the backlog grows
    grows = pr.issues_component(
        cache(
            issue(1, created="2026-10-12T00:00:00Z"),
            issue(2, created="2026-10-13T00:00:00Z"),
            issue(3, created="2026-10-14T00:00:00Z"),
            issue(4, state="closed", created="2026-08-01T00:00:00Z", closed="2026-10-14T00:00:00Z"),
        )
    )
    assert grows["core_last_window"]["net_closed"] == -2 and grows["eta"] == pr.NOT_CONVERGING


def test_eta_is_a_number_of_days_only_when_the_backlog_shrinks():
    # 10 open, 7 closed in the window and none opened: net 7 over 7 days = 1 a day -> 10 days
    issues = [issue(n) for n in range(1, 11)] + [
        issue(100 + n, state="closed", created="2026-08-01T00:00:00Z", closed="2026-10-13T00:00:00Z") for n in range(7)
    ]
    out = pr.issues_component(cache(*issues))
    assert out["core_last_window"] == {"opened": 0, "closed": 7, "net_closed": 7}
    assert out["eta"] == "10 days"


def test_eta_with_nothing_open_is_not_a_division():
    assert pr.eta(0, 0.0) == "none open"
    assert pr.eta(0, -3.0) == "none open"
    assert pr.eta(5, 0.0) == pr.NOT_CONVERGING
    assert pr.eta(5, -1.0) == pr.NOT_CONVERGING
    assert pr.eta(6, 2.0) == "3 days"


def test_the_window_edges_and_the_milestones_and_pull_requests():
    out = pr.issues_component(
        cache(
            issue(1, milestone=28),
            issue(2, state="closed", closed="2026-10-09T12:00:00Z", milestone=28),  # exactly 7 days back: outside
            issue(3, state="closed", closed="2026-10-09T12:00:01Z"),  # just inside
            {**issue(4), "pull_request": {"url": "x"}},  # a PR is not an issue
            issue(5, scope="frontier", created="2026-10-14T00:00:00Z", milestone=30),
            issue(6, scope="frontier", state="closed", created="2026-08-01T00:00:00Z", closed="2026-09-01T00:00:00Z"),
            issue(7, scope="sweep"),
            issue(8, scope="infra", state="closed", closed="2026-09-01T00:00:00Z"),
        )
    )
    assert out["core"] == {"open": 1, "closed": 2, "total": 3}
    assert out["core_milestone"] == {"number": 28, "open": 1, "closed": 1, "total": 2}
    assert out["core_last_window"]["closed"] == 1
    assert out["frontier"] == {"open": 1, "closed": 1, "total": 2, "found_last_window": 1}
    assert out["frontier_milestone"]["total"] == 1
    assert out["sweep"]["open"] == 1 and out["infra"]["closed"] == 1


def test_no_cache_and_no_token_is_not_measured_and_prints_no_number(tmp_path, monkeypatch):
    monkeypatch.setenv(pr.CACHE_ENV, str(tmp_path / "absent.json"))
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    assert pr.load_issues() is None
    assert pr.issues_component(None) == {"measured": False, "note": "not measured: no issues cache and no GITHUB_TOKEN"}


# ---- the burned-only CICS denominator -----------------------------------------------------------------------------


def _row(key, entry="full", translator="yes (3 options)", stub="yes"):
    return {"key": key, "entry": entry, "translator": translator, "stub": stub}


def test_cics_denominator_is_the_commands_a_burned_program_uses():
    census = {
        "READ": {"burned": 3, "non_burned": 9, "programs": 12},
        "XCTL": {"burned": 1, "non_burned": 0, "programs": 1},
        "ENGINE ONLY": {"burned": 1, "non_burned": 0, "programs": 1},
        "NAME ONLY": {"burned": 2, "non_burned": 0, "programs": 2},
        "DUMP": {"burned": 0, "non_burned": 5, "programs": 5},  # non-burned only: out of the denominator
        "(unlisted) INQUIRE": {"burned": 7, "non_burned": 0, "programs": 7},
        "(unparsed)": {"burned": 1, "non_burned": 0, "programs": 1},
    }
    rows = [
        _row("READ"),
        _row("XCTL", translator="refused whole"),
        _row("ENGINE ONLY", entry="engine-only", stub="refused whole"),
        _row("NAME ONLY", entry="name-only", translator="refused whole", stub="refused whole"),
        _row("DUMP", entry="name-only", translator="refused whole", stub="refused whole"),
        _row("OTHER"),
    ]
    out = pr.cics_component(census, rows)
    assert out["burned_commands"] == 6
    assert out["modelled_both_runtimes"] == 1
    assert out["not_modelled"] == 5
    assert out["unlisted_or_unparsed"] == 2  # the unlisted and unparsed forms are in, and never modelled
    assert "DUMP" not in out["not_modelled_commands"]
    assert out["spec"] == {
        "entries": 6,
        "full": 3,
        "engine_only": 1,
        "name_only": 2,
    }  # the whole spec: frontier context


# ---- the rest of the components ---------------------------------------------------------------------------------------


def test_rules_and_mutation_components():
    rules = {
        "rules": [
            {"status": "MATCHED", "calibration": "uncalibrated"},
            {"status": "MATCHED", "calibration": "z/OS 2.5"},
            {"status": "DIFFERS"},
            {"status": "ASSUMED", "calibration": "uncalibrated"},
        ]
    }
    out = pr.rules_component(rules)
    assert out["status"] == {"MATCHED": 2, "DIFFERS": 1, "ASSUMED": 1, "REFUSED": 0}
    assert out["measured_on_zos"] == 1
    t = {"killed": 9, "survived": 3, "equivalent": 1, "unreachable": 1}
    mut = pr.mutation_component({"ports": [{"total": t}, {"total": t}]})
    assert (mut["killed"], mut["adjusted_total"], mut["raw_total"]) == (18, 20, 24)
    assert mut["adjusted_kill_pct"] == 90.0 and mut["raw_kill_pct"] == 75.0


def test_crucibles_component():
    out = pr.crucibles_component(
        {
            "crucible_ref": "v1",
            "programs": {"a/A": {"scenarios": {"s1": {}, "s2": {}}}, "b/B": {"scenarios": {"s": {}}}},
        },
        {"pinned_ref": "v2", "horrors": {"H1": "PASS", "H2": "FAIL"}},
    )
    assert out["cics_crucible"] == {"ref": "v1", "programs": 2, "scenarios": 3}
    assert out["estate_crucible"] == {"ref": "v2", "horrors": 2, "pass": 1}


def test_ladder_percentages_and_the_era_table():
    progs = [{"level": lv, "translation": {"whole": lv != "L0"}} for lv in ("L0", "L1", "L2", "L4", "L4", "L5")]
    out = pr.ladder(progs)
    assert out["l2_plus"] == 4 and out["l4_plus"] == 3 and out["l5"] == 1 and out["translated_whole"] == 5
    assert out["l2_plus_pct"] == 66.7 and out["l4_plus_pct"] == 50.0
    total = pr.sum_ladders([out, out])
    assert total["programs"] == 12 and total["l2_plus"] == 8 and total["levels"]["L4"] == 4
    eras = pr.era_table({"x": [("2", "L4"), ("2", "L1"), ("none", "L2")], "y": [("4", "L5")]})
    assert eras["2"] == {"programs": 2, "l2_plus": 1, "l4_plus": 1}
    assert eras["none"]["l2_plus"] == 1 and eras["4"]["l4_plus"] == 1 and eras["0"]["programs"] == 0


# ---- the whole page, from fixtures ---------------------------------------------------------------------------------


@pytest.fixture
def report(tmp_path, monkeypatch):
    pytest.importorskip("tree_sitter_language_pack")  # cics_spec_status reads the det translator live
    import readiness_report

    monkeypatch.setattr(readiness_report, "REPORTS", FIXTURE_REPORTS)
    c = tmp_path / "issues.json"
    c.write_text(json.dumps(cache(issue(1, milestone=28), issue(2, scope="frontier", created="2026-10-14T00:00:00Z"))))
    monkeypatch.setenv(pr.CACHE_ENV, str(c))
    pr._issues_once.cache_clear()
    yield pr.gather()
    pr._issues_once.cache_clear()


def test_the_page_has_all_five_sections_and_the_fixed_denominator(report):
    text = pr.render(report)
    for head in (
        "## 1. Burned-estate ladder",
        "## 2. Components",
        "## 3. Eras",
        "## 4. Core burn-down",
        "## 5. Gap Atlas",
    ):
        assert head in text
    n = sum(
        len(json.loads((d / "report.json").read_text())["programs"]) for d in FIXTURE_REPORTS.iterdir() if d.is_dir()
    )
    assert report["ladder"]["total"]["programs"] == n
    assert report["components"]["translator"]["of"] == n
    assert "not z/OS" in text and report["commit"] in text
    assert pr.NOT_CONVERGING in text  # one open core issue, none closed: the rule shows on the page
    assert json.loads(pr.render_json(report))["format"] == pr.FORMAT


def test_the_page_never_says_proven_bare(report):
    # the evidence wording policy: levels and counts; the word only as part of an identifier
    assert not re.search(r"(?<![\w])proven(?![\w])", pr.render(report), re.I)


def test_two_renders_are_identical(report):
    assert pr.render(report) == pr.render(report)
    assert pr.render_json(report) == pr.render_json(report)


def test_an_estate_report_that_is_not_burned_is_refused():
    assert pr.burned_estates_ok(["cics-genapp", "zecs"]) == []
    assert pr.burned_estates_ok(["cics-genapp", "some-census-repo"]) == ["some-census-repo"]


# ---- the READMEs hold no hand-written number --------------------------------------------------------------------------

READMES = ("README.md", "gitgalaxy/tools/cobol_to_java/README.md")
PAGE = "generated/docs/language_status/progress.md"
# a count of estates, programs, commands, scenarios, records, mutants or ports, a fraction, or a percentage
COUNT = re.compile(
    r"(?<!Java )\b\d[\d,]*(?:\.\d+)?\s*(?:/\s*\d|%)|\b\d[\d,]*\s+(?:programs?|estates?|commands?|scenarios?|records?|mutants?|ports?)\b"
    r"|\b(?:six|seven|eight|nine)\s+(?:public|burned|reference)\s+estates?\b",
    re.I,
)


def _section(text, start, stop=None):
    a = text.index(start)
    b = text.index(stop, a + len(start)) if stop else len(text)
    return text[a:b]


def _prose_only(text):
    # a <details> block is a dated, labelled snapshot (the model-written ports table), not a live status number
    return re.sub(r"<details>.*?</details>", "", text, flags=re.S)


def test_the_cics_to_java_readmes_carry_no_hand_written_status_number():
    hits = []
    for rel in READMES:
        text = (REPO / rel).read_text(encoding="utf-8")
        if rel == "README.md":
            text = _section(text, "## CICS to Java: ported, then proven", "\n## ")
            # the CICS tile of the hero table (the other tiles are the scanner's numbers, not this status)
            tiles = re.findall(r"<td[^>]*>.*?</td>", (REPO / rel).read_text(encoding="utf-8"), flags=re.S)
            text += "\n".join(t for t in tiles if "CICS" in t)
        for n, line in enumerate(_prose_only(text).splitlines(), 1):
            for m in COUNT.finditer(line):
                hits.append(f"{rel}: {m.group(0)!r} in {line.strip()[:90]!r}")
    assert not hits, "hand-written numbers (read them off the progress page instead, #5280):\n" + "\n".join(hits)


@pytest.mark.parametrize("rel", READMES)
def test_each_readme_points_at_the_generated_progress_page(rel):
    assert PAGE in (REPO / rel).read_text(encoding="utf-8")


def test_the_readmes_do_not_carry_a_marker_block():
    """The docs bot never writes to main (#5057), so a rendered block would go stale: the READMEs link instead."""
    for rel in READMES:
        assert "progress:begin" not in (REPO / rel).read_text(encoding="utf-8")


def test_det_survey_is_a_dated_snapshot_with_no_current_proof_count():
    text = (REPO / "docs/language_status/det_survey.md").read_text(encoding="utf-8")
    assert "Dated historical snapshot" in text and PAGE in text
    assert "programs are proven" not in text


# ---- docs/language_status pages that quote a status count are dated snapshots (#5282) ---------------------------------

SNAPSHOT_PAGES = (
    "det_survey.md",
    "det_port_design.md",
    "cics_mainframe_facts.md",
    "construct_correspondence.md",
)


@pytest.mark.parametrize("name", SNAPSHOT_PAGES)
def test_a_status_page_with_counts_is_a_dated_snapshot_pointing_at_the_progress_page(name):
    text = (REPO / "docs/language_status" / name).read_text(encoding="utf-8")
    assert re.search(r"Dated historical snapshot \(\d{4}-\d{2}-\d{2}\)", text), name
    assert PAGE in text, name


def test_no_status_page_states_a_current_proof_count_undated():
    text = (REPO / "docs/language_status/det_port_design.md").read_text(encoding="utf-8")
    assert "**Status (2026-10-02): 48 programs" not in text
    assert "Breadth outside CardDemo** is" not in text


def test_fact_ownership_quotes_no_corpus_size():
    text = (REPO / "docs/language_status/fact_ownership.md").read_text(encoding="utf-8")
    universe = _section(text, "- **Universe:**", "- **Engine side:**")
    assert not re.search(r"\b\d+\s+(?:sources|programs|copybooks|COBOL programs)\b", universe), universe


# ---- the READMEs that quoted a command / program count by hand (#5282, reusing the guard above) -----------------------

SWEPT_READMES = (
    "gitgalaxy/standards/cics/README.md",
    "gitgalaxy/tools/cobol_to_cobol/README.md",
    "tests/README.md",
    "docs/ecosystem.md",
    "docs/self_scan/README.md",
)


@pytest.mark.parametrize("rel", SWEPT_READMES)
def test_a_swept_readme_carries_no_hand_written_status_number(rel):
    text = _prose_only((REPO / rel).read_text(encoding="utf-8"))
    hits = [f"{m.group(0)!r} in {line.strip()[:90]!r}" for line in text.splitlines() for m in COUNT.finditer(line)]
    assert not hits, f"{rel}: hand-written numbers (read them off the generated page, #5282):\n" + "\n".join(hits)
