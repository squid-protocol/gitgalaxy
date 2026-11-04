"""The recorded estate sizes (tests/fixtures/estate_size.json, read by the status slide) are what a live count of the
pinned corpora gives; the counters themselves are checked on small inputs."""

import json
import os
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import estate_size as es  # noqa: E402

CORPORA = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", es.REPO / ".mainframe_corpora"))


def test_copy_names_skip_comments_and_the_precompilers_own_areas():
    lines = [
        "       COPY CUSTREC.",
        "      *    COPY NOTME.",
        "           EXEC SQL INCLUDE SQLCA END-EXEC.",
        "           EXEC SQL INCLUDE DCLCUST END-EXEC.",
        "       01  X.  COPY 'QUOTED'.",
    ]
    assert es.copy_names(lines) == {"CUSTREC", "DCLCUST", "QUOTED"}


def test_a_job_counts_when_read_with_a_step_and_a_cond_job_when_a_step_tests(tmp_path):
    root = tmp_path / "e"
    (root / "jcl").mkdir(parents=True)
    (root / "jcl" / "A.jcl").write_text(
        "//A JOB (1),'X'\n//S1 EXEC PGM=IEFBR14\n//S2 EXEC PGM=IEFBR14,COND=(0,NE)\n", encoding="latin-1"
    )
    (root / "jcl" / "B.jcl").write_text("//B JOB (1),'X'\n//S1 EXEC PGM=IEFBR14\n", encoding="latin-1")
    out = es.measure_estate(root, [], "e")
    assert (out["jcl_members"], out["jcl_jobs"], out["jcl_cond_jobs"]) == (2, 2, 1)


def test_the_record_matches_a_live_count_of_the_corpora():
    rec = es.load()
    assert rec, "tests/fixtures/estate_size.json is missing"
    if not CORPORA.is_dir():
        pytest.skip(f"no mainframe corpora at {CORPORA}")
    try:
        programs = es.estate_programs()
    except Exception as exc:  # the evidence reports are materialized from the generated branch
        pytest.skip(f"evidence reports unavailable: {exc}")
    live = es.measure(CORPORA, programs)["estates"]
    for name, row in live.items():
        assert rec.get(name) == row, f"{name}: re-record with `python tests/tools/estate_size.py CORPORA --write`"
