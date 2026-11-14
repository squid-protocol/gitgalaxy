"""The estate journey page (tests/tools/estate_journey.py): sourced numbers, one measure per chart, never stale."""

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import estate_journey as ej  # noqa: E402


def _data():
    return {
        "intro": "intro",
        "chapters": [
            {"title": "Dev", "overlay": "overlay_l2", "estates": ["d"]},
            {"title": "Trials", "overlay": "overlay_l1", "estates": ["b"]},
        ],
        "estates": [
            {"key": "d", "name": "Dev estate", "measure": "L2", "program_basis": 4,
             "first_contact": {"date": "2026-01-01", "value": 1, "total": 4, "source": "#1"},
             "series": [{"date": "2026-01-01", "prs": 0, "value": 0, "total": 4, "source": "#1"},
                        {"date": "2026-01-09", "prs": 8, "value": 4, "total": 4, "source": "#2"}],
             "learned": [{"text": "a lesson", "refs": ["#2"]}]},
            {"key": "b", "name": "Blind estate", "measure": "L1", "program_basis": 2,
             "first_contact": {"date": "2026-02-01", "value": 0, "total": 2, "source": "#3"},
             "series": [{"date": "2026-02-01", "prs": 0, "value": 0, "total": 2, "accounted": 1, "source": "#3"}]},
        ],
        "journal": [{"date": "2026-02-01", "text": "we assumed X", "refs": ["#3"]}],
        "caveats": ["oracle is GnuCOBOL"],
    }  # fmt: skip


def test_every_number_needs_a_source_and_one_measure():
    assert ej.problems(_data()) == []
    d = copy.deepcopy(_data())
    del d["estates"][0]["series"][1]["source"]
    d["estates"][1]["measure"] = "L9"
    bad = ej.problems(d)
    assert any("has no source" in b for b in bad) and any("not L1 or L2" in b for b in bad)


def test_l1_and_l2_estates_never_share_an_overlay():
    files = ej.build(_data())
    assert (
        "Dev estate" in files["estate_journey/overlay_l2.svg"]
        and "Blind estate" not in files["estate_journey/overlay_l2.svg"]
    )
    assert (
        "Blind estate" in files["estate_journey/overlay_l1.svg"]
        and "Dev estate" not in files["estate_journey/overlay_l1.svg"]
    )


def test_page_lists_lessons_journal_and_accounted_line():
    files = ej.build(_data())
    page = files["estate_journey.md"]
    assert "**What we learned**" in page and "- a lesson (#2)" in page and "we assumed X" in page
    assert 'stroke-dasharray="5 4"' in files["estate_journey/b.svg"]  # accounted drawn dashed
    assert ej.build(_data()) == files  # deterministic


def test_the_committed_page_is_current():
    assert ej.problems(ej.load()) == []
    assert ej.main(["--check"]) == 0


def test_a_one_reading_dip_is_dropped_but_a_lasting_drop_stays():
    assert ej._without_blips([(0, 0.5), (1, 0.2), (2, 0.5)]) == [(0, 0.5), (2, 0.5)]
    assert ej._without_blips([(0, 0.5), (1, 0.2), (2, 0.2), (3, 0.5)]) == [(0, 0.5), (1, 0.2), (2, 0.2), (3, 0.5)]


def test_axis_ends_at_the_nearest_round_value():
    assert [ej._nice(n) for n in (5, 108, 3128)] == [8, 200, 4000]


# ---- recording a draw: add-draw, point, l2-from-prs ------------------------------------------------------------------


def _with_draws():
    d = _data()
    d["intro"] = "The first of 3 pre-registered draws. 2 draws remain."
    d["estates"][1].update({"kind": "blind", "draw": 1, "estate": "estate-b"})
    d["chapters"].append({"title": "Next: 2 draws left", "text": "Before each draw: the preflight."})
    return d


def test_add_draw_records_first_contact_its_chapter_and_recounts_the_prose():
    d = ej.add_draw(_with_draws(), draw=2, repo="o/r", issue=9000, estate="estate-c", basis=12,
                    date="2026-12-01 9:00 AM", whole=3, accounted=5, source="#9000 T0", planned=3,
                    trial="trial-002", trial_issues=[9001])  # fmt: skip
    e = d["estates"][-1]
    assert (e["key"], e["kind"], e["draw"], e["measure"]) == ("blind-trial-2", "blind", 2, "L1")
    assert e["trial_issues"] == [9000, 9001]
    assert e["series"] == [
        {"date": "2026-12-01 9:00 AM", "prs": 0, "value": 3, "accounted": 5, "total": 12, "source": "#9000 T0"}
    ]
    assert [c["title"] for c in d["chapters"]][-2:] == ["Blind estate 2 of 3 (drawn 2026-12-01)", "Next: 1 draws left"]
    assert "1 draws remain" in d["intro"]
    assert ej.problems(d, planned=3) == []
    for bad in ({"draw": 2}, {"draw": 4}, {"draw": 3, "source": ""}):
        args = dict(repo="o/r", issue=1, estate="e", basis=1, date="d", whole=0, source="s", planned=3) | bad
        with pytest.raises(ValueError):
            ej.add_draw(copy.deepcopy(d), **args)


def test_l2_on_a_blind_draw_needs_the_owner_amendment_and_points_never_go_back():
    d = _with_draws()
    kw = dict(key="b", measure="L2", prs=4, value=1, total=2, source="#5", date="d")
    with pytest.raises(ValueError, match="amendment"):
        ej.add_point(copy.deepcopy(d), **kw)
    d = ej.add_point(d, **kw, l2_note="Amendment 9: cases allowed")
    assert [(p["prs"], p["value"]) for p in d["estates"][1]["l2_series"]] == [(0, 0), (4, 1)]
    for bad in ({"prs": 3}, {"value": 3}, {"source": ""}):
        with pytest.raises(ValueError):
            ej.add_point(copy.deepcopy(d), **(kw | bad))
    d = ej.add_point(d, key="b", measure="L1", prs=6, value=2, total=2, accounted=2, source="#6", date="d")
    assert d["estates"][1]["series"][-1] == {
        "date": "d", "prs": 6, "value": 2, "total": 2, "source": "#6", "accounted": 2
    }  # fmt: skip
    assert ej.problems(d, planned=3) == []


def test_problems_catch_a_wrong_remaining_count_a_repeated_draw_and_an_l2_without_its_note():
    d = _with_draws()
    d["intro"] = "5 draws remain."
    d["estates"][0].update({"kind": "blind", "draw": 1, "estate": "x"})
    d["estates"][1]["l2_series"] = [{"prs": 0, "value": 0, "total": 2, "source": "s"}]
    d["estates"][1]["series"].append({"prs": -1, "value": 0, "total": 2, "source": "s"})
    bad = " | ".join(ej.problems(d, planned=3))
    for want in ("says 5 draws remain", "numbers repeat", "needs l2_measure_note", "goes back in PRs"):
        assert want in bad, want


def test_the_l2_series_counts_trial_prs_and_steps_only_on_new_case_programs():
    rows = [
        ("2026-12-01T08:00:00Z", 1, "Before first contact (Part of #9000)"),
        ("2026-12-01T10:00:00Z", 2, "Census: copybook members reach the census (Part of #9001)"),
        ("2026-12-01T11:00:00Z", 3, "Hidden text: unrelated work (Part of #4108)"),
        ("2026-12-01T12:00:00Z", 4, "Equivalence cases for estate-c family 1: PGMA, PGMB (Part of #9002)"),
        ("2026-12-01T13:00:00Z", 5, "Det Db2: the engine fix the proof run booked as a cause"),
        ("2026-12-01T14:00:00Z", 6, "Health PGMA: scenarios lift it to L3 (Part of #9002)"),
        ("2026-12-01T15:00:00Z", 7, "Equivalence case for PGMB again and PGMC (Part of #9002)"),
    ]
    prs = ej.trial_prs(rows, "2026-12-01T09:00", [9000, 9001, 9002], "estate-c", causes=[5])
    assert [n for _, n, _ in prs] == [2, 4, 5, 6, 7]
    series = ej.l2_series_from_prs(prs, ["PGMA", "PGMB", "PGMC", "PGMD"], 4, "T0")
    assert [(p["prs"], p["value"]) for p in series] == [(0, 0), (2, 2), (5, 3)]
    assert all(p["source"] for p in series)
    assert "PGMC" in series[-1]["source"] and "PGMB" not in series[-1]["source"]


def test_a_rebuild_keeps_hand_recorded_points_and_refuses_what_it_cannot_credit():
    # review of #8406: --write replaced the series and dropped Blind 1's closing evidence-report point; an empty
    # eligible list matched the empty string and credited a program; `point` on a development estate wrote a
    # second L2 series the page build then crashed on
    rebuilt = [
        {"prs": 0, "value": 0, "total": 4, "source": "first contact: no case exists"},
        {"prs": 2, "value": 2, "total": 4, "source": "PR #4 merged, case added: PGMA, PGMB"},
    ]
    committed = [
        {"prs": 0, "value": 0, "total": 4, "source": "first contact: stale wording"},
        {"prs": 1, "value": 1, "total": 4, "source": "PR #3 merged, case added: a row the rebuild no longer makes"},
        {"prs": 9, "value": 2, "total": 4, "source": "origin/generated abc: L2+ 2 of 4"},
    ]
    merged = ej.keep_recorded_points(rebuilt, committed)
    assert [(p["prs"], p["source"][:6]) for p in merged] == [(0, "first "), (2, "PR #4 "), (9, "origin")]
    with pytest.raises(ValueError, match="no eligible programs"):
        ej.l2_series_from_prs([("2026-12-01T12:00:00Z", 4, "Equivalence cases for x (Part of #9002)")], [], 4, "T0")
    with pytest.raises(ValueError, match="not a blind draw"):
        ej.add_point(_with_draws(), key="d", measure="L2", prs=1, value=1, total=2, source="s", date="d")


def test_l2_from_prs_refuses_an_unknown_key_or_trial_without_a_traceback(capsys):
    assert ej.main(["l2-from-prs", "--key", "no-such-estate", "--since", "2026-12-01T09:00"]) == 1
    assert "refused: no estate 'no-such-estate'" in capsys.readouterr().err
    assert ej.main(["l2-from-prs", "--key", "blind-trial-1", "--since", "2026-12-01T09:00", "--trial", "nope"]) == 1
    assert "refused: no trial 'nope'" in capsys.readouterr().err


def test_a_blind_l2_series_gets_its_own_chart_never_the_l1_overlay():
    d = ej.add_point(_with_draws(), key="b", measure="L2", prs=3, value=2, total=2, source="#7", date="d",
                     l2_note="Amendment 9: cases allowed")  # fmt: skip
    files = ej.build(d)
    assert "estate_journey/b-l2.svg" in files and "L2 or better" in files["estate_journey/b-l2.svg"]
    assert "L2 or better" not in files["estate_journey/overlay_l1.svg"]
    page = files["estate_journey.md"]
    assert "Amendment 9: cases allowed" in page and "(estate_journey/b-l2.svg)" in page
