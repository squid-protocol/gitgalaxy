"""#7901: the census inventory lists a data-only copy member and never counts it as a program."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cics_census as cc  # noqa: E402
import gap_prevalence as gp  # noqa: E402

DATA_ONLY = "       01  CUST-REC.\n           05  CUST-ID   PIC X(8).\n           05  CUST-NAME PIC X(30).\n"
PROGRAM = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. PGM1.\n       PROCEDURE DIVISION.\n"
    "           EXEC CICS RETURN END-EXEC.\n"
)
NO_PROGRAM_ID = "       IDENTIFICATION DIVISION.\n       PROCEDURE DIVISION.\n           EXEC CICS RETURN END-EXEC.\n"
PROCEDURE_ONLY = "       PROCEDURE DIVISION.\n           EXEC CICS RETURN END-EXEC.\n"
FREE = ">>SOURCE FORMAT FREE\nidentification division.\nprogram-id. pgm2.\nprocedure division.\n  goback.\n"


def test_data_only_member_is_a_copy_member():
    assert cc.copy_member_reason(DATA_ONLY) == cc.COPY_MEMBER_REASON


def test_real_programs_are_not_copy_members():
    for text in (PROGRAM, NO_PROGRAM_ID, PROCEDURE_ONLY, FREE):
        assert cc.copy_member_reason(text) is None


def test_comment_mentioning_a_division_does_not_make_a_program():
    assert cc.copy_member_reason("      * IDENTIFICATION DIVISION. PROGRAM-ID. X.\n" + DATA_ONLY)


def test_load_surveys_splits_the_copy_member(tmp_path):
    d = tmp_path / "before-b"
    d.mkdir()
    rows = {"c": [{"program": "A.cbl", "statements": 1}, {"program": "REC.cbl", "copy_member": cc.COPY_MEMBER_REASON}]}
    (d / "survey.json").write_text(json.dumps(rows), encoding="utf-8")
    assert set(cc.load_surveys(tmp_path, "before")) == {("c", "A.cbl")}
    assert cc.load_copy_members(tmp_path, "before") == {("c", "REC.cbl"): cc.COPY_MEMBER_REASON}


def test_headline_lists_copy_members_only_when_present():
    res = {"programs": 39, "whole_now": 11, "copy_members": 1,
           "coverage_if_closed": [{"top": 1, "whole": 12, "share": 0.3, "upper_bound": False}]}  # fmt: skip
    note = [x for x in gp.headline(res) if x.startswith("Copy members")]
    assert len(note) == 1 and "1 listed, not counted in the 39 programs" in note[0]
    del res["copy_members"]
    assert not [x for x in gp.headline(res) if x.startswith("Copy members")]


def test_survey_markdown_does_not_count_the_copy_member():
    import det_survey as ds

    rows = {"c": [{"program": "A.cbl", "statements": 2, "translated": 2, "holes": []},
                  {"program": "REC.cbl", "copy_member": cc.COPY_MEMBER_REASON}]}  # fmt: skip
    assert "| c | 1 | 1 | 0 | 0 |" in ds.markdown(rows)


def test_load_runs_skips_the_copy_member(tmp_path):
    d = tmp_path / "before-b"
    d.mkdir()
    rows = {"c": [{"program": "A.cbl", "statements": 1}, {"program": "REC.cbl", "copy_member": cc.COPY_MEMBER_REASON}]}
    (d / "survey.json").write_text(json.dumps(rows), encoding="utf-8")
    assert set(cc.load_runs(tmp_path, "before")["b"]) == {("c", "A.cbl")}


def test_survey_markdown_lists_the_copy_member_with_its_reason():
    import det_survey as ds

    rows = {"c": [{"program": "A.cbl", "statements": 2, "translated": 2, "holes": []},
                  {"program": "REC.cbl", "copy_member": cc.COPY_MEMBER_REASON}]}  # fmt: skip
    md = ds.markdown(rows)
    assert f"| 1 | {cc.COPY_MEMBER_REASON} |" in md and "REC.cbl" not in md
    assert "Copy members" not in ds.markdown({"c": rows["c"][:1]})


def test_program_without_program_id_keeps_a_program_row():
    import det_survey as ds

    rows = {"c": [{"program": "B.cbl", "error": "UnitRefused: no PROGRAM-ID"}]}
    assert cc.copy_member_reason(NO_PROGRAM_ID) is None
    assert "| c | 1 | 0 | 0 | 1 |" in ds.markdown(rows)
