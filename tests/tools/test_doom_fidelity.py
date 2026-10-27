"""DOOM study fidelity column (#5620): vocabulary, phrase matching, check outcomes and the committed manifest.

Synthetic READMEs only (no DOOM text); the tool dir goes on sys.path and the module is imported as a bare name
(tests/ has no __init__.py).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "doom_speedrun"))

import doom_speedrun  # noqa: E402
import fidelity  # noqa: E402


def row(name, value, file="README.md", phrase="", cls="engine-port", reason=""):
    return {
        "name": name,
        "class": cls,
        "fidelity": value,
        "fidelity_file": file,
        "fidelity_phrase": phrase,
        "fidelity_reason": reason,
    }


def clone(repos, name, text, file="README.md"):
    path = repos / name / file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.mark.parametrize(
    "readme",
    [
        "It aims to **accurately\n  reproduce** the original.",  # emphasis and a wrapped line
        "it AIMS to accurately reproduce the Original",  # case
        "It aims to accurately `reproduce` the original",  # code span
    ],
)
def test_phrase_matches_through_markdown_whitespace_and_case(readme):
    assert fidelity.phrase_in(readme, "aims to accurately reproduce the original")


def test_phrase_absent_is_not_matched():
    assert not fidelity.phrase_in("aims to reproduce the original", "aims to accurately reproduce")


def test_check_passes_every_value_and_lists_missing_clones_as_unchecked(tmp_path):
    clone(tmp_path, "a", "This is faithful to the 1997 release.")
    rows = [
        row("a", "faithful", phrase="faithful to the 1997 release"),
        row("b", "compatible", phrase="demo compatible"),  # no clone: unchecked, not passed
        row("c", "unstated", file="", reason="readme-silent"),
        row("d", "original", file=""),
    ]
    problems, unchecked = fidelity.check_rows(rows, tmp_path)
    assert (problems, unchecked) == ([], ["b"])


def test_check_flags_a_phrase_that_left_the_readme(tmp_path):
    clone(tmp_path, "a", "Nothing about fidelity here.")
    problems, _ = fidelity.check_rows([row("a", "enhanced", phrase="many new features")], tmp_path)
    assert len(problems) == 1 and "no longer contains" in problems[0]


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        (row("a", "pristine", phrase="x"), "is not one of"),
        (row("a", "", file=""), "is not one of"),  # an empty cell is not a value
        (row("a", "faithful", phrase=""), "needs fidelity_file and fidelity_phrase"),
        (row("a", "divergent", file="", phrase="x"), "needs fidelity_file and fidelity_phrase"),
        (row("a", "unstated", phrase="x", reason="readme-silent"), "must not carry"),
        (row("a", "unstated", file=""), "needs a fidelity_reason"),
        (row("a", "unstated", file="", reason="because"), "needs a fidelity_reason"),
        (row("a", "faithful", phrase="x", reason="readme-silent"), "must not carry a fidelity_reason"),
        (row("a", "original", file="README.md"), "must not carry"),
    ],
)
def test_check_rejects_a_malformed_row(tmp_path, bad, message):
    problems, _ = fidelity.check_rows([bad], tmp_path)
    assert len(problems) == 1 and message in problems[0]


def test_report_counts_per_class_and_value():
    rows = [
        row("a", "faithful", phrase="x"),
        row("b", "faithful", phrase="x"),
        row("c", "unstated", file="", cls="raycaster", reason="no-readme"),
    ]
    table = fidelity.report(rows)
    assert "| engine-port | - | a, b |" in table
    assert "| raycaster |" in table and table.rstrip().splitlines()[-1] == "| **ports** | 0 | 2 | 0 | 0 | 0 | 1 |"


def test_strict_makes_an_absent_clone_an_error(tmp_path, capsys):
    manifest = tmp_path / "m.csv"
    manifest.write_text(
        "name,class,fidelity,fidelity_file,fidelity_phrase\nb,engine-port,compatible,README.md,demo compatible\n"
    )
    argv = ["check", "--work", str(tmp_path / "work"), "--manifest", str(manifest)]
    assert fidelity.main(argv) == 0
    assert fidelity.main([*argv, "--strict"]) == 1
    assert "1 unchecked" in capsys.readouterr().out


def test_committed_manifest_is_well_formed():
    # structure only: phrases are checked against the pinned clones by `fidelity.py check`
    rows = doom_speedrun.read_manifest()
    problems, _ = fidelity.check_rows(rows, Path("/nonexistent-clones"))
    assert problems == []
    assert {r["fidelity"] for r in rows} <= set(fidelity.VOCAB)
    assert [r["name"] for r in rows if r["fidelity"] == "original"] == ["linuxdoom"]
    # every port carries a statement (a README phrase) or a named reason it has none (#6097)
    assert [r["name"] for r in rows if r["fidelity"] == "unstated" and not r["fidelity_reason"]] == []
