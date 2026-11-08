"""#8112: compile listings, expanded copies and duplicate PROGRAM-IDs are listed, never counted as programs."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cics_census as cc  # noqa: E402
import cics_preflight as pf  # noqa: E402

PROGRAM = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. {pid}.\n       PROCEDURE DIVISION.\n"
    "           EXEC CICS RETURN END-EXEC.\n"
)
BODY = "           MOVE 1 TO WS-A.\n" * 25


def numbered(width: int, pad: str) -> str:
    """Every line carries a line number in columns 1-6 (`pad` fills the left: '0' a sequence area, ' ' a listing)."""
    src = (PROGRAM.format(pid="NUMPGM") + BODY * 3).splitlines()
    return "\n".join(f"{str(i + 1).rjust(width, pad)} {ln[1:]}" for i, ln in enumerate(src)) + "\n"


def parts(*p: str) -> tuple[str, ...]:
    return p


@pytest.mark.parametrize("name", ["PGM.cbl", "PGM.cob", "PGM.COBOL", "PGM.lst.cbl", "pgm.sysprint.cob", "PGM-LIST.cbl"])
def test_listing_names_are_listings(name):
    assert cc.listing_reason(PROGRAM.format(pid="A"), parts("sub", name)) == (
        None if name in {"PGM.cbl", "PGM.cob", "PGM.COBOL"} else "listing path (directory or file name)"
    )


@pytest.mark.parametrize("d", ["." + "expanded", "Expan" + "ded", "listings", "SYSPRINT", ".hidden"])
def test_listing_directories_are_listings(d):
    assert cc.listing_reason(PROGRAM.format(pid="A"), parts("a", d, "PGM.cbl"))


@pytest.mark.parametrize(
    "marker", ["PP 5655-EC6 IBM COBOL FOR Z/OS", "DB2 SQL PRECOMPILER", "CALL 'DFHEI1' USING X", "DFHEIGBL"]
)
def test_banners_and_translator_output_are_listings(marker):
    assert cc.listing_reason(f"1PP 5655  {marker}\n" + PROGRAM.format(pid="A"), parts("PGM.cbl"))


def test_space_padded_listing_numbers_are_a_listing_and_a_zero_padded_sequence_area_is_not():
    assert cc.listing_reason(numbered(6, " "), parts("PGM.cbl")) == "listing line numbers (space-padded, increasing)"
    assert cc.listing_reason(numbered(6, "0"), parts("PGM.cbl")) is None


def test_plain_fixed_free_and_short_programs_are_programs():
    free = ">>SOURCE FORMAT FREE\nidentification division.\nprogram-id. pgm2.\nprocedure division.\n  goback.\n"
    for text in (PROGRAM.format(pid="A"), PROGRAM.format(pid="A") + BODY, free):
        assert cc.listing_reason(text, parts("x", "PGM.cbl")) is None


def test_program_id_reads_fixed_and_free_format_case_insensitively():
    assert cc.program_id(PROGRAM.format(pid="abc-1")) == "ABC-1"
    assert cc.program_id(">>SOURCE FORMAT FREE\nprogram-id. pgm2.\n") == "PGM2"
    assert cc.program_id("       01  REC.\n") is None


def test_duplicates_exact_and_near_and_first_path_stays_the_program():
    a = PROGRAM.format(pid="DUP")
    texts = {"b/z.cbl": a, "a/y.cbl": a, "c/near.cbl": a + BODY, "d/other.cbl": PROGRAM.format(pid="OTHER")}
    out = cc.duplicate_reasons(texts)
    assert set(out) == {"b/z.cbl", "c/near.cbl"}  # a/y.cbl sorts first
    assert "exact" in out["b/z.cbl"] and "near" in out["c/near.cbl"]
    assert all("DUP" not in r for r in out.values())  # a reason names no PROGRAM-ID


def test_same_program_id_in_different_estates_is_no_duplicate():
    assert cc.duplicate_reasons({"a.cbl": PROGRAM.format(pid="X")}) == {}


def test_not_program_rows_does_not_flag_a_listing_as_a_duplicate_of_itself():
    texts = {"a.cbl": PROGRAM.format(pid="X"), "lst/a.cbl": PROGRAM.format(pid="X")}
    out = cc.not_program_rows(texts, {p: tuple(p.split("/")) for p in texts})
    assert list(out) == ["lst/a.cbl"] and out["lst/a.cbl"].startswith("listing")


def test_load_surveys_splits_the_not_program_rows(tmp_path):
    d = tmp_path / "before-b"
    d.mkdir()
    rows = {"c": [{"program": "A.cbl", "statements": 1}, {"program": "x/A.cbl", "not_program": "why"}]}
    (d / "survey.json").write_text(json.dumps(rows), encoding="utf-8")
    assert set(cc.load_surveys(tmp_path, "before")) == {("c", "A.cbl")}
    assert cc.load_not_programs(tmp_path, "before") == {("c", "x/A.cbl"): "why"}
    res: dict = {}
    cc.note_copy_members(res, 0, 0)
    assert res == {}  # added only when non-empty
    cc.note_copy_members(res, 0, 2)
    assert res == {"not_programs": 2}


def test_markdown_lists_them_apart_and_does_not_count_them():
    import det_survey as ds

    rows = {"c": [{"program": "A.cbl", "statements": 2, "translated": 2, "holes": []},
                  {"program": "L.cbl", "not_program": "duplicate PROGRAM-ID (exact copy of another program in the estate)"}]}  # fmt: skip
    md = ds.markdown(rows)
    assert "| c | 1 | 1 | 0 | 0 |" in md and "## Listings and duplicates (not counted as programs)" in md


def test_preflight_reports_listings_and_duplicates_as_findings_by_count(tmp_path, monkeypatch, capsys):
    root = tmp_path / "census"
    repo = root / "ZZREPO"
    (repo / ("." + "expanded")).mkdir(parents=True)
    (repo / "pgm.cbl").write_text(PROGRAM.format(pid="ZZ1"), encoding="utf-8")
    (repo / "copy2.cbl").write_text(PROGRAM.format(pid="ZZ1"), encoding="utf-8")
    (repo / ("." + "expanded") / "pgm.cbl").write_text(PROGRAM.format(pid="ZZ1"), encoding="utf-8")
    monkeypatch.setattr(cc, "census_root_problems", lambda path: [])
    monkeypatch.setattr(pf, "owner_issues", lambda: [1])
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=cc.REPO, capture_output=True, text=True, check=True
    ).stdout.strip()
    args = argparse.Namespace(root=tmp_path, census_corpora=root, t0=sha)
    rc = pf.cmd_preflight(args, state_of=lambda n: "open")
    out = capsys.readouterr().out
    assert rc != 0
    assert "FAIL listing-shaped files 1" in out and "FAIL duplicate PROGRAM-IDs 1" in out
    assert "programs 1, copy members 0" in out
    assert "ZZREPO" not in out and "ZZ1" not in out
