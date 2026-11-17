"""#8412: Endevor / ChangeMan-style stage trees (one member in several stages) and compile listings with no banner and
no listing path are listed, never counted as programs. Names are invented."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cics_census as cc  # noqa: E402

SRC = [
    "       IDENTIFICATION DIVISION.",
    "       PROGRAM-ID. {pid}.",
    "       DATA DIVISION.",
    "       WORKING-STORAGE SECTION.",
    "       01  WS-A PIC 9.",
    "       PROCEDURE DIVISION.",
    "           MOVE 1 TO WS-A.",
    "           GOBACK.",
]


def program(pid: str, extra: str = "") -> str:
    return "\n".join(SRC).format(pid=pid) + "\n" + extra


def plain_listing(repeat: int, width: int) -> str:
    """A listing with no banner: every source line carries a space-padded line number."""
    lines = [ln.strip() for ln in (SRC * repeat)]
    return "\n".join(f"{str(i + 1).rjust(width)}  {ln}".format(pid="LSTPGM") for i, ln in enumerate(lines)) + "\n"


@pytest.mark.parametrize("repeat,width", [(1, 6), (1, 3), (2, 4), (3, 5)])
def test_a_plain_listing_with_no_banner_and_no_listing_path_is_a_listing(repeat, width):
    assert cc.listing_reason(plain_listing(repeat, width), ("src", "LSTPGM.cbl")) == (
        "listing line numbers (space-padded, consecutive)"
    )


def test_real_short_programs_and_level_numbers_are_never_a_listing():
    assert cc.listing_reason(program("REALPGM"), ("src", "REALPGM.cbl")) is None
    levels = "\n".join(f"  {n:02d}  F{n} PIC X." for n in (1, 5, 5, 10, 10, 5, 10, 10, 15, 15))
    assert cc.listing_reason(program("REALPGM", levels), ("src", "REALPGM.cbl")) is None


def stage_tree(root: Path) -> dict[str, str]:
    """An Endevor-style tree: ORDPOST in three stages (the QA stage differs), a second member in one stage."""
    files = {
        "ENDEVOR/DEV/COBOL/ORDPOST.cbl": program("ORDPOST"),
        "ENDEVOR/QA/COBOL/ORDPOST.cbl": program("ORDPOST", "           DISPLAY 'QA'.\n"),
        "ENDEVOR/PROD/COBOL/ORDPOST.cbl": program("ORDPOST"),
        "ENDEVOR/PROD/COBOL/INVRPT.cbl": program("INVRPT"),
    }
    for rel, text in files.items():
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    return {rel: (root / rel).read_text(encoding="utf-8") for rel in files}


def test_a_member_in_several_stages_is_one_program_and_the_other_stages_are_listed(tmp_path):
    texts = stage_tree(tmp_path)
    out = cc.not_program_rows(texts, {p: tuple(p.split("/")) for p in texts})
    assert set(out) == {"ENDEVOR/PROD/COBOL/ORDPOST.cbl", "ENDEVOR/QA/COBOL/ORDPOST.cbl"}  # DEV sorts first, stays
    assert "exact" in out["ENDEVOR/PROD/COBOL/ORDPOST.cbl"] and "near" in out["ENDEVOR/QA/COBOL/ORDPOST.cbl"]
    assert "ENDEVOR/PROD/COBOL/INVRPT.cbl" not in out


def test_a_listing_copy_in_a_stage_directory_is_a_listing_not_the_stage_s_program(tmp_path):
    texts = stage_tree(tmp_path)
    texts["ENDEVOR/DEV/COBOL/ORDPOST.cbl"] = plain_listing(
        2, 5
    )  # the DEV member is a listing: the next stage (PROD) is the program
    out = cc.not_program_rows(texts, {p: tuple(p.split("/")) for p in texts})
    assert out["ENDEVOR/DEV/COBOL/ORDPOST.cbl"].startswith("listing")
    assert "ENDEVOR/PROD/COBOL/ORDPOST.cbl" not in out and "ENDEVOR/QA/COBOL/ORDPOST.cbl" in out
