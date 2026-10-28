"""DOOM study write-up tables (#5620): block rendering, the marker fill, and that the committed doc carries every block.

Synthetic rows only (no DOOM code); the tool dir goes on sys.path and the module is imported as a bare name
(tests/ has no __init__.py).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "doom_speedrun"))

import study_report  # noqa: E402


def test_fill_replaces_every_block_and_keeps_prose():
    doc = "intro\n" + "".join(
        f"{study_report.BEGIN.format(n)}\nold\n{study_report.END.format(n)}\nprose {n}\n" for n in study_report.BLOCKS
    )
    new = study_report.fill(doc, {n: f"table {n}\n" for n in study_report.BLOCKS})
    assert "old" not in new and new.startswith("intro\n")
    assert all(f"table {n}\n" in new and f"prose {n}\n" in new for n in study_report.BLOCKS)
    assert study_report.fill(new, {n: f"table {n}\n" for n in study_report.BLOCKS}) == new  # idempotent


def test_fill_refuses_a_doc_without_the_marker_pair():
    with pytest.raises(SystemExit, match="no '<!-- study:clean-scan begin -->'"):
        study_report.fill("nothing here", {"clean-scan": "x\n"})


def test_committed_doc_has_every_block_once():
    text = study_report.DOC.read_text()
    for name in study_report.BLOCKS:
        assert text.count(study_report.BEGIN.format(name)) == 1
        assert text.count(study_report.END.format(name)) == 1


def test_clean_scan_counts_new_ports_and_gains():
    rows = [{"name": "a"}, {"name": "b"}, {"name": "c"}]
    before = {
        "a": {"fails": "coverage", "missed_src": "3", "func_delta_pct": "1.0"},
        "b": {"fails": "", "missed_src": "0"},
    }
    after = {
        "a": {"fails": "", "first_party_src": "4", "missed_src": "0", "func_delta_pct": "0.5", "gg_functions": "10"},
        "b": {"fails": "functions", "missed_src": "0", "gg_functions": "5"},
        "c": {"fails": "", "first_party_src": "0", "missed_src": "0", "gg_functions": "7"},
    }
    text = study_report.clean_scan_block(rows, before, after)
    assert text.startswith("2 of 3 ports pass every scored check now; 1 of them failed")
    assert "| a | coverage | - | 4 | 3 | 0 | 1.0 | 0.5 | 10 |" in text
    assert "| c | n/a | - | 0 (vacuous) | n/a | 0 | n/a | not compared | 7 |" in text


def test_landmark_ratios_are_against_linuxdoom():
    def row(variant, fn, cx, loc):
        return dict(variant=variant, function=fn, complexity=cx, loc=loc)

    canon = [row("linuxdoom", "F", 10, 100), row("linuxdoom", "G", 4, 40), row("managed-doom", "F", 20, 50),
             row("managed-doom", "G", "", "")]  # fmt: skip
    text = study_report.landmark_block(canon)
    assert "| managed-doom | 1 / 2 | 2.00 | 2.00 - 2.00 | 0.50 | 0.50 - 0.50 |" in text


def test_subway_block_filters_to_listed_ports(tmp_path):
    f = tmp_path / "subway.csv"
    f.write_text(
        "repo,functions,wiring_similarity,edges_kept,shape_distance\n"
        "linuxdoom,777,1.0,1.0,0.0\ngore,100,0.9,0.77,0.5\nunlisted,5,0.1,0.0,2.0\n"
    )
    text = study_report.subway_block(f, ["linuxdoom", "gore"])
    assert "| gore | 100 | 0.9 | 0.77 | 0.5 |" in text
    assert "unlisted" not in text and "| linuxdoom |" not in text
    assert "No `--subway` file" in study_report.subway_block(None, [])


def test_subsystem_block_is_a_port_by_subsystem_ratio_matrix():
    def sub(name, ratio):
        return dict(subsystem=name, complexity_vs_linuxdoom=ratio)

    result = {
        "linuxdoom": ([sub("p", None), sub("r", None)], 0.0),
        "gore": ([sub("p", 0.5), sub("r", None), sub("other", None)], 12.4),
        "dartdoom": ([sub("p", 2.0), sub("r", 1.25)], 0.0),
    }
    text = study_report.subsystem_block(result)
    assert text.splitlines()[0] == "| port | p | r | other % |"
    assert "| dartdoom | 2.00 | 1.25 | 0 |" in text
    assert "| gore | 0.50 |  | 12 |" in text
    assert "linuxdoom" not in text


def test_subsystem_block_shows_median_over_zero_when_linuxdoom_median_is_zero():
    zero = dict(subsystem="i", complexity_vs_linuxdoom=None, complexity_med=2.0, comparable=True)
    small = dict(subsystem="d", complexity_vs_linuxdoom=None, complexity_med=2.0)  # under the minimum: stays blank
    result = {"linuxdoom": ([], 0.0), "gore": ([zero, small], 0.0)}
    text = study_report.subsystem_block(result)
    assert "| port | d | i | other % |" in text
    assert "| gore |  | 2/0 | 0 |" in text
