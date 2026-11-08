"""#8075: the survey and the census count a program once. A repo that ships compile-listing copies of its programs
under a hidden directory (`.expanded/`, IBM's example-health-apis) has the scan skip them (aperture), so the estate
holds one Db2 repository per program; the copy surveyed as a second program had its statements keyed by the expanded
file's line numbers and failed "no generated Db2 repository method" (10 of 58 programs). Fixture corpora under tmp_path."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cics_census as cc
import det_survey as ds

CICS = "       PROCEDURE DIVISION.\n           EXEC CICS RETURN END-EXEC.\n"


@pytest.mark.parametrize(
    ("parts", "expected"),
    [
        (("src", "PROG.cbl"), True),
        (("PROG.cbl",), True),
        (("src", ".expanded", "PROG.cbl"), False),
        ((".hidden", "a", "PROG.cbl"), False),
        ((".git", "PROG.cbl"), False),
        ((".PROG.cbl",), True),  # a hidden FILE name is not a hidden directory
    ],
)
def test_program_path_skips_hidden_directories(parts, expected):
    assert ds.is_program_path(parts) is expected


def test_the_census_reads_the_real_program_and_not_its_hidden_copy(tmp_path):
    corpus = tmp_path / "estate"
    (corpus / "src" / ".expanded").mkdir(parents=True)
    (corpus / "src" / "PROG.cbl").write_text(CICS, encoding="utf-8")
    (corpus / "src" / ".expanded" / "PROG.cbl").write_text(CICS, encoding="utf-8")
    assert cc.cics_programs([tmp_path]) == {("estate", "src/PROG.cbl")}
