"""#5286: the status slide renders from fixtures into valid XML, every number on it is the matching progress.json
value, GitHub-fed parts read "not measured" offline (never a number), both colour schemes are present, and the
READMEs show it as a picture linking to the full page."""

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import progress_report as pr  # noqa: E402
import progress_slide as ps  # noqa: E402

REPO = TOOLS.parents[1]
FIXTURE_REPORTS = REPO / "tests" / "fixtures" / "evidence_report"
END = "2026-10-16T12:00:00Z"
IMAGE = "https://raw.githubusercontent.com/squid-protocol/gitgalaxy/generated/docs/language_status/progress.svg"
PAGE = "https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/progress.md"
READMES = ("README.md", "gitgalaxy/tools/cobol_to_java/README.md")


def _issue(n, scope="core", state="open", milestone=None):
    return {
        "number": n,
        "state": state,
        "created_at": "2026-09-01T00:00:00Z",
        "closed_at": None if state == "open" else "2026-10-15T00:00:00Z",
        "labels": [f"scope:{scope}"],
        "milestone": milestone,
    }


def _cache(epics=None):
    return {
        "fetched_at": END,
        "issues": [_issue(1, milestone=28), _issue(2, state="closed"), _issue(3, scope="frontier", milestone=30)],
        "milestones": [
            {"number": 10, "title": "Enter the Mainframe", "open_issues": 3, "closed_issues": 17},
            {"number": 28, "title": "Training Montage", "open_issues": 23, "closed_issues": 3},
        ],
        "title_counts": {"cics": {"total": 97, "closed": 78}, "cobol": {"total": 139, "closed": 123}},
        "epics": epics or {"4890": "open", "4891": "open", "4892": "open", "4893": "open", "4894": "open"},
    }


def _gather(tmp_path, monkeypatch, cache):
    pytest.importorskip("tree_sitter_language_pack")  # cics_spec_status reads the det translator live
    import readiness_report

    monkeypatch.setattr(readiness_report, "REPORTS", FIXTURE_REPORTS)
    path = tmp_path / "issues.json"
    if cache is not None:
        path.write_text(json.dumps(cache))
    monkeypatch.setenv(pr.CACHE_ENV, str(path))
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    pr._issues_once.cache_clear()
    try:
        return pr.gather()
    finally:
        pr._issues_once.cache_clear()


@pytest.fixture
def report(tmp_path, monkeypatch):
    return _gather(tmp_path, monkeypatch, _cache())


@pytest.fixture
def offline(tmp_path, monkeypatch):
    return _gather(tmp_path, monkeypatch, None)


def _texts(svg):
    root = ET.fromstring(svg)
    return [(e.text or "").strip() for e in root.iter("{http://www.w3.org/2000/svg}text")]


def test_the_slide_is_valid_xml_and_renders_twice_identically(report):
    svg = ps.render(report)
    root = ET.fromstring(svg)
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert ps.render(report) == ps.render(report)


def test_every_number_on_the_slide_is_the_progress_json_value(report):
    texts = _texts(ps.render(report))
    comp, lad, iss = report["components"], report["ladder"], report["issues"]
    want = [
        f"{comp['translator']['whole']} / {comp['translator']['of']}",
        f"{lad['total']['l2_plus']} / {lad['total']['programs']}",
        f"{comp['cics']['modelled_both_runtimes']} / {comp['cics']['burned_commands']}",
        f"{comp['mutation']['adjusted_kill_pct']:.1f}%",
        f"{comp['cobolrt_rules']['status']['MATCHED']} / {comp['cobolrt_rules']['rules']}",
        f"COBOL runtime rules: {comp['cobolrt_rules']['rules']} catalogued",
        f"{iss['core']['closed']} / {iss['core']['total']}",
        str(iss["frontier"]["total"]),
        "78 / 97",
        "123 / 139",
        "85%  (17/20)",
    ]
    for w in want:
        assert w in texts, w
    # the total row: one count per level, then the programs
    total_cells = [str(lad["total"]["levels"][k]) if lad["total"]["levels"][k] else "·" for k in pr.LEVELS]
    joined = " ".join(texts)
    assert " ".join([*total_cells, str(lad["total"]["programs"])]) in joined or all(c in texts for c in total_cells)
    for estate in lad["estates"].values():
        assert str(estate["programs"]) in texts
    for era, row in report["eras"].items():
        if era != "none" and row["programs"]:
            assert f"{row['programs']} programs" in texts
            assert f"run equal (L2+): {row['l2_plus']} ({100 * row['l2_plus'] / row['programs']:.0f}%)" in texts


def test_the_family_rows_come_from_the_rules_families(report):
    texts = _texts(ps.render(report))
    for fam in ("SQL", "LE", "MQ", "DLI"):
        c = report["components"]["cobolrt_rules"]["families"].get(fam, {})
        assert f"{c.get('MATCHED', 0)} / {sum(c.values())}" in texts


def test_offline_the_github_parts_are_not_measured_and_print_no_number(offline):
    assert offline["issues"]["measured"] is False
    svg = ps.render(offline)
    texts = _texts(svg)
    assert texts.count(ps.NOT_MEASURED) >= 4  # the four issue boxes
    assert any(t.startswith("Milestones: not measured") for t in texts)
    assert not any(re.search(r"\(\d+/\d+\)", t) for t in texts)  # no milestone fraction
    assert not any("epic closed" in t for t in texts)
    assert any(f"Epic #{n} state not measured" in t for t in texts for n in pr.OPEN_WORLD_EPICS)


def test_a_closed_open_world_epic_turns_its_row_to_in_use(tmp_path, monkeypatch):
    rep = _gather(tmp_path, monkeypatch, _cache({"4890": "closed", "4891": "open"}))
    texts = _texts(ps.render(rep))
    assert any("In use: Open World #4890; epic closed" in t for t in texts)
    assert any(t.startswith("Not started: Open World #4891") for t in texts)


def test_both_colour_schemes_are_present(report):
    svg = ps.render(report)
    assert "@media (prefers-color-scheme: dark)" in svg
    light, dark = svg.split("@media (prefers-color-scheme: dark)")
    for colour in (*ps.LADDER_LIGHT, *ps.STATUS_LIGHT):
        assert colour in light
    for colour in (*ps.LADDER_DARK, *ps.STATUS_DARK):
        assert colour in dark


def test_the_page_is_registered_and_publishable():
    import generated_docs

    rel = "docs/language_status/progress.svg"
    assert rel in generated_docs.PAGES
    assert f"docs/language_status/progress.svg" in (REPO / ".github/workflows/generated-docs.yml").read_text()
    assert 'cron: "17 5 * * *"' in (REPO / ".github/workflows/generated-docs.yml").read_text()


@pytest.mark.parametrize("rel", READMES)
def test_each_readme_shows_the_slide_linking_to_the_full_page(rel):
    text = (REPO / rel).read_text(encoding="utf-8")
    assert f"[![CICS to Java: where we stand]({IMAGE})]({PAGE})" in text


def test_the_slide_inputs_are_added_only_when_the_cache_carries_them():
    old = pr.issues_component({"fetched_at": END, "issues": [_issue(1)]})
    assert not {"milestones", "title_counts", "epics"} & set(old)  # an older cache still loads (#5100)
    new = pr.issues_component(_cache())
    assert new["milestones"][1] == {"number": 28, "title": "Training Montage", "open": 23, "closed": 3, "total": 26}
    assert new["title_counts"]["cics"] == {"closed": 78, "total": 97}
    assert new["epics"]["4890"] == "open"
