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
import capability_ledger as cl  # noqa: E402
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


def _titles(svg):
    root = ET.fromstring(svg)
    return [(e.text or "").strip() for e in root.iter("{http://www.w3.org/2000/svg}title")]


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
        f"{comp['cics']['modelled_both_runtimes']} / {comp['cics']['burned_commands']}",  # the CICS ledger row
        f"{comp['det_mutation']['total']['caught']:,}",  # the L5 tile: planted bugs caught by tests
        f"Runtime fidelity: {comp['cobolrt_rules']['status'].get('MATCHED', 0)} of "
        f"{comp['cobolrt_rules']['rules']} rules match IBM",
        f"{iss['core']['closed']} / {iss['core']['total']}",
        str(iss["frontier"]["total"]),
        "78 / 97",
        "123 / 139",
        "85%  (17/20)",
    ]
    for w in want:
        assert w in texts, w
    assert f"{lad['total']['l4_plus']} / {lad['total']['programs']}" in texts  # the highlighted L4 tile
    # each row's level bar carries its L4+ count (L5 programs count at L4 there), the L5 bar its L5 count
    titles = _titles(ps.render(report))
    assert f"All real codebases: {lad['total']['l4_plus']} at L4 Every branch or above" in titles
    for key, estate in lad["estates"].items():
        nm = ps.ESTATE_NAMES.get(key, key)
        if estate["l4_plus"]:
            assert f"{nm}: {estate['l4_plus']} at L4 Every branch or above" in titles
        e5 = report["components"]["det_mutation"]["estates"].get(key)
        if e5 and e5["l5"]:
            assert f"{nm}: {e5['l5']} pass L5" in titles
    for era, row in report["eras"].items():
        if era != "none" and row["programs"]:
            assert f"{row['programs']} programs" in texts
            assert f"same output (L2+): {row['l2_plus']} ({100 * row['l2_plus'] / row['programs']:.0f}%)" in texts


def _fresh(blind_draws=(1,), planned=17, with_l2=True):
    """A journey with the census rehearsal and blind draws, plus a trials ledger for draw 1."""
    est = [{
        "key": "census", "name": "Census", "kind": "census", "measure": "L1", "program_basis": 39,
        "first_contact": {"date": "d0", "value": 8, "total": 40, "source": "s"},
        "milestones": [{"value": 13, "total": 39, "prs": 108, "days": 3.3}],
        "series": [{"date": "2026-11-04 1:46 PM ET", "prs": 0, "value": 8, "accounted": None, "total": 40, "source": "s"},
                   {"date": "2026-11-07 8:42 PM ET", "prs": 108, "value": 13, "accounted": 37, "total": 39,
                    "source": "s"}],
    }]  # fmt: skip
    t0, l2_at, read = "2026-11-07 10:32 PM ET", "2026-11-11 06:50:22 UTC", "2026-11-13 1:17 PM UTC"
    for d in blind_draws:
        est.append({
            "key": f"blind-{d}", "name": f"Blind {d}", "kind": "blind", "draw": d, "estate": f"estate-{d}",
            "trial": f"trial-00{d}", "measure": "L1", "program_basis": 29,
            "first_contact": {"date": "d0", "value": 0, "total": 29, "source": "s"},
            "milestones": [{"value": 25, "total": 29, "prs": 5, "days": 0.4}],
            "series": [{"date": t0, "prs": 0, "value": 0, "accounted": 7, "total": 29, "source": "s"},
                       {"date": read, "prs": 68, "value": 28, "accounted": None, "total": 29, "source": "s"}],
            **({"l2_series": [{"date": t0, "prs": 0, "value": 0, "total": 29, "source": "s"},
                              {"date": "2026-11-10 12:10:24 UTC", "prs": 27, "value": 2, "total": 29, "source": "s"},
                              {"date": l2_at, "prs": 46, "value": 28, "total": 29, "source": "s"},
                              {"date": read, "prs": 68, "value": 28, "total": 29, "source": "s"}]} if with_l2 else {}),
        })  # fmt: skip
    progs = {f"P{i}": {"final": "proven@1", "attempts": [{"n": 1}]} for i in range(23)}
    progs |= {f"Q{i}": {"final": "proven@2(engine)", "attempts": [{"n": 1}, {"n": 2}]} for i in range(5)}
    trials = {"trials": [{"id": "trial-001", "estate": "estate-1", "closed": "2026-11-12", "eligible": list(progs),
                          "system": {"engine_version": "v2.12.0"}, "programs": progs}]}  # fmt: skip
    return pr.fresh_component({"estates": est}, trials, planned)


def test_fresh_code_is_counted_from_the_journey_and_the_trial_ledger():
    fr = _fresh()
    (c,), (b,) = fr["census"], fr["blind"]
    assert (c["l1"]["first"], c["l1"]["first_total"], c["l1"]["now"], c["accounted"]["now"]) == (8, 40, 13, 37)
    assert (b["l1"]["first"], b["l1"]["now"], b["l2"]["now"], b["l2"]["prs_to_now"]) == (0, 28, 28, 46)
    assert (b["l2"]["days_to_now"], b["l1"]["days_to_now"], c["l1"]["days_to_now"]) == (3.1, 5.4, 3.3)  # ET and UTC
    assert b["accounted"] is None  # measured at T0 only: an old reading is never shown as the current one
    ft = b["first_try"]
    assert (ft["proven_first"], ft["judged"], ft["proven_final"]) == (23, 28, 28)  # fixes never turn into first try


def test_a_date_that_does_not_parse_leaves_the_days_out():
    assert pr.journey_time("d0") is None and pr.journey_time(None) is None
    assert pr._climb([{"date": "d0", "prs": 0, "value": 0, "total": 2}, {"prs": 3, "value": 2, "total": 2}])[
        "days_to_now"] is None  # fmt: skip


def _panel_widths(svg):
    return {m[2]: float(m[1]) for m in re.finditer(r'<rect [^>]*width="([\d.]+)"[^>]*><title>Blind (\d+): ', svg)}


def test_every_planned_draw_has_a_slot_and_a_drawn_one_shows_its_climb_and_days(report):
    svg = ps.render({**report, "fresh": _fresh()})
    texts = _texts(svg)
    assert "Blind trials: 1 of 17 drawn" in texts
    assert texts.count("not yet drawn") == 16
    assert "0/29 → 28/29" in texts and "23 / 28" in texts and "82%" in texts
    assert "Same output (L2): 0 → 28 of 29" in texts and "46 PRs · 3.1 days" in texts
    assert "Blind 1: L2 from 0 to 28 of 29" in _titles(svg)
    assert not any("no blind codebase has been measured yet" in t for t in texts)
    # owner, 2026-11-13: right under the tiles, before the ladder; a drawn panel two cells wide while few are drawn
    assert texts.index("Blind trials: 1 of 17 drawn") < next(
        i for i, t in enumerate(texts) if t.startswith("Results:"))  # fmt: skip
    assert _panel_widths(svg)["1"] > 2 * 180


def test_from_wide_until_draws_a_drawn_panel_is_one_cell(report):
    many = ps.render({**report, "fresh": _fresh(blind_draws=tuple(range(1, ps.WIDE_UNTIL + 1)))})
    assert len(set(_panel_widths(many).values())) == 1 and max(_panel_widths(many).values()) < 200
    assert _texts(many).count("not yet drawn") == 17 - ps.WIDE_UNTIL


def test_the_census_is_not_on_the_slide_its_gains_are_on_the_capability_rows(report):
    # owner, 2026-11-13: no census card or row; what the trials made us build shows on the capability ledger instead
    svg = ps.render({**report, "fresh": _fresh()})
    texts = _texts(svg)
    assert not any("Census" in t or "8/40" in t for t in texts)
    found = {r["name"]: r["found"] for r in report["components"]["capabilities"]["rows"] if r.get("found")}
    assert {"Copybook search", "JSON GENERATE / PARSE", "Db2 embedded SQL"} <= set(found)
    for f in found.values():
        assert f in texts and f.startswith(("Gap found by ", "Tested by "))


def test_a_draw_without_cases_is_drawn_at_l1_never_l2(report):
    svg = ps.render({**report, "fresh": _fresh(blind_draws=(1, 2), with_l2=False)})
    texts = _texts(svg)
    assert "Translates whole (L1): 0 → 28 of 29" in texts and "68 PRs · 5.4 days" in texts
    assert not any(t.startswith("Same output (L2)") for t in texts)
    assert texts.count("not yet drawn") == 15


def test_with_no_fresh_code_the_section_is_absent(report):
    texts = _texts(ps.render({**report, "fresh": pr.fresh_component(None, None, 17)}))
    assert not any(t.startswith("Blind trials") for t in texts)


def test_the_family_rows_come_from_the_rules_families(report):
    texts = _texts(ps.render(report))
    for fam in ("SQL", "LE", "DLI"):
        c = report["components"]["cobolrt_rules"]["families"].get(fam, {})
        assert f"{c.get('MATCHED', 0)} / {sum(c.values())}" in texts
    c = report["components"]["cobolrt_rules"]["families"].get("MQ", {})
    assert any(f"{c.get('MATCHED', 0)} of {sum(c.values())} rules match IBM" in t for t in texts)


def test_offline_the_github_parts_are_not_measured_and_print_no_number(offline):
    assert offline["issues"]["measured"] is False
    svg = ps.render(offline)
    texts = _texts(svg)
    assert texts.count(ps.NOT_MEASURED) >= 4  # the four issue boxes
    assert any(t.startswith("Milestones: not measured") for t in texts)
    assert not any(re.search(r"\(\d+/\d+\)", t) for t in texts)  # no milestone fraction


def test_every_ledger_row_is_on_the_slide_with_its_state_and_count(report):
    texts = _texts(ps.render(report))
    caps = report["components"]["capabilities"]
    for r in caps["rows"]:
        assert r["name"] in texts and r["have"] in texts
        assert cl.STATE_LABEL[r["state"]] in texts
        if r["of"]:
            assert f"{r['done']} / {r['of']}" in texts
    # a row with no list to count against gets no bar and no fraction (said once, in the subtitle)
    assert not any("no list to count against" in t for t in texts)
    assert sum(1 for t in texts if re.fullmatch(r"\d+ / \d+", t)) >= sum(1 for r in caps["rows"] if r["of"])


def test_a_state_comes_from_the_count_or_the_code_never_from_a_hand_typed_row():
    assert [cl.of_state(*c) for c in ((0, 7), (3, 7), (7, 7))] == ["none", "partial", "works"]
    assert cl.seen(cl.DET / "dfsort.py", "class Refused", "partial") == "partial"
    assert cl.seen(cl.DET / "dfsort.py", "code that went away", "partial") == "none"
    assert cl.seen(cl.DET / "no_such_file.py", "x", "works") == "none"


def test_the_language_row_leaves_out_the_families_that_are_not_cobol():
    rules = [
        {"family": "CBL", "status": "MATCHED"},
        {"family": "NUM", "status": "DIFFERS"},
        {"family": "CICS", "status": "MATCHED"},
    ]
    assert cl.family_counts(rules, cl.LANGUAGE_FAMILIES) == (1, 2)


def test_the_spec_tables_are_shown_as_depth_of_the_rules_not_as_more_rules(report):
    row = next(r for r in report["components"]["capabilities"]["rows"] if r["name"] == "Runtime spec tables")
    assert row["of"] is None and "part of the rules above" in row["note"]


def test_external_and_internal_estates_are_apart_and_the_levels_show_their_build(report):
    texts = _texts(ps.render(report))
    joined = " ".join(texts)
    bands = ["1. Training codebases", "All real codebases", "2. Our own test suites"]
    at = [joined.index(b) for b in bands]
    assert at == sorted(at)
    for lv in report["components"]["crucibles"]["estate_crucible"]["levels"]:
        assert lv["name"] in texts
        assert f"built {lv['built']} of {lv['constructs']} planned constructs ({lv['built_pct'] or 0:.0f}%)" in texts
        assert ("first run pending" if not lv["first_run"] else f"first run {lv['first_run']['date']}") in texts
    # our own estates have no planted-bug run yet: their L5 bar says so instead of drawing a zero
    assert texts.count("L5 not yet started") >= len(report["components"]["crucibles"]["estate_crucible"]["levels"])


def test_every_program_below_l4_is_named_with_its_reason(report):
    texts = _texts(ps.render(report))
    below = report["ladder"]["below_l4"]
    if not below:
        pytest.skip("the fixture estates have no program below L4")
    assert f"The {len(below)} not at every branch yet, each named: none dropped" in texts
    for b in below:
        assert any(b["program"] in t for t in texts), b["program"]
        assert b["why"] in texts


def test_a_test_estate_is_shown_and_never_counted():
    prog = {"level": "L1", "program": "x/CAA.cbl", "translation": {"whole": True}}
    rep = pr.ladder([prog, {**prog, "level": "L0", "translation": {"whole": False}}])
    assert rep["levels"]["L1"] == 1 and rep["programs"] == 2
    out = pr._test_estate_lines({"cics-crucible": rep})
    assert any("`cics-crucible` | 2 | 1 | 1 |" in line for line in out)
    assert pr._test_estate_lines({}) == []


def _program(name, level, **mutation):
    return {"program": f"src/{name}.cbl", "level": level, "mutation": mutation}


def test_ready_is_not_l5_and_the_raw_score_and_sample_stay_beside_it():
    reports = {"e": {"programs": [
        _program("A", "L4", score=0.5, l5=True, current=False, killed=5, survived=5),
        _program("B", "L5", score=1.0, l5=True, current=True, killed=10, survived=0),
        _program("C", "L4", score=None),
    ]}}  # fmt: skip
    ledger = {
        "e-a": {"program": "A", "chosen": 10, "mutants": 100},
        "e-b": {"program": "B", "chosen": 10, "mutants": 10},
    }
    claims = {"e-a": [{"verdict": "equivalent"}] * 3 + [{"verdict": "unreachable"}] * 2}
    r = pr.det_mutation_component(reports, ledger, claims)["estates"]["e"]
    assert (r["measured"], r["l5"], r["ready"], r["programs"]) == (2, 1, 1, 3)
    assert (r["raw_pct"], r["sampled"], r["mutants"]) == (75.0, 20, 110)
    assert (r["equivalent"], r["unreachable"]) == (3, 2)


def test_the_hand_port_score_is_not_called_the_translators(report):
    text = " ".join(_texts(ps.render(report)))
    assert "translator mutants caught" not in text
    assert "hand-written ports, not the translator" in text
    assert "not started" not in text.lower()


def test_the_house_style_is_dark_with_no_scheme_switch(report):
    """Owner 2026-11-08: dark always, matching the README films. GitHub renders the SVG through an <img>,
    where prefers-color-scheme follows the viewer's OS, so a scheme switch would show white to light-OS viewers."""
    svg = ps.render(report)
    assert "prefers-color-scheme" not in svg
    assert f".bg {{ fill: {ps.SURFACE}; }}" in svg
    for colour in (*ps.LADDER_DARK, *ps.STATUS_DARK, *ps.L5_DARK):
        assert colour in svg


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


def test_the_code_page_rows_are_counted_from_the_codecs_the_gauntlet_and_the_crucible(report):
    rows = {r["name"]: r for r in report["components"]["capabilities"]["rows"]
            if r["group"] == "Code pages and national text"}  # fmt: skip
    cp = cl.code_pages()
    assert (rows["EBCDIC code pages"]["done"], rows["EBCDIC code pages"]["of"]) == (cp["java"], cp["pages"])
    assert cp["dbcs"] >= 1 and cp["sbcs"] >= 1
    g = cl.cultural_gauntlet()
    assert f"{g['failing']} failing cells (Cultural Gauntlet)" in rows["Cultural dialects"]["note"]
    ok, n = cl.multicultural_estate()
    assert (rows["Multicultural test estate"]["done"], rows["Multicultural test estate"]["of"]) == (
        ok or None,
        n or None,
    ) or not n
