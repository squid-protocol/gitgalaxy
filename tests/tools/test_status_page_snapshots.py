"""#5282: hand-written status pages under docs/language_status carry a dated-snapshot banner that links the generated
progress page, so their counts are never read as current."""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
STATUS = REPO / "docs" / "language_status"
PAGE = "generated/docs/language_status/progress.md"
SNAPSHOT_PAGES = ("det_survey.md", "det_port_design.md", "estate4_dbb_mortgage.md", "porting_loop.md")
BANNER = re.compile(r"Dated historical snapshot \((\d{4}-\d{2}-\d{2})\)")
BANNER_WITHIN_LINES = 14
CURRENT_CLAIM = re.compile(r"\bprograms are (translated|proven)\b|\bStatus \(\d{4}-\d{2}-\d{2}\)")


@pytest.mark.parametrize("name", SNAPSHOT_PAGES)
def test_page_is_a_dated_snapshot_linking_the_generated_page(name):
    head = "\n".join((STATUS / name).read_text(encoding="utf-8").splitlines()[:BANNER_WITHIN_LINES])
    assert BANNER.search(head), f"{name}: no dated-snapshot banner near the top"
    assert PAGE in head, f"{name}: the banner does not link the generated progress page"


def test_no_other_status_page_claims_a_current_proof_count():
    """A page outside SNAPSHOT_PAGES must not state a current proof count; add the banner and list it instead."""
    offenders = [
        p.name
        for p in sorted(STATUS.glob("*.md"))
        if p.name not in SNAPSHOT_PAGES and CURRENT_CLAIM.search(p.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"pages with a current-status count and no snapshot banner: {offenders}"
