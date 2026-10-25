"""#5054 done-when 2: the anonymized blocker report leaks none of a burned estate's own names, on every PR.

The leak scan itself lives in tests/tools/test_blocker_report.py, which the ground-truth job does not run; this job
fetches the pinned corpora, so the scan is collected here (the same function, bare-imported) and fails, rather than
skips, when the job has the corpora variable but an estate is missing from it."""

import os
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import test_blocker_report as tbr
from test_blocker_report import test_leak_free_on_burned_estate_names  # noqa: F401  (collected here)

_CORPORA = os.environ.get("GITGALAXY_MAINFRAME_CORPORA", "")


@pytest.mark.skipif(not _CORPORA, reason="GITGALAXY_MAINFRAME_CORPORA not set")
@pytest.mark.parametrize("estate", tbr.ESTATES)
def test_the_job_has_every_burned_estate_checked_out(estate):
    assert (Path(_CORPORA) / estate).is_dir(), (
        f"{estate} missing under GITGALAXY_MAINFRAME_CORPORA: the leak scan would skip"
    )
