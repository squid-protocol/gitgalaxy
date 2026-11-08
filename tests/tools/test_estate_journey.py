"""The estate journey page (tests/tools/estate_journey.py): sourced numbers, one measure per chart, never stale."""

import copy
import sys
from pathlib import Path

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
