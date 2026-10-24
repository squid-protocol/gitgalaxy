"""#5282: hand-written status pages under docs/language_status carry a dated-snapshot banner that links the generated
progress page, so their counts are never read as current."""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
STATUS = REPO / "docs" / "language_status"
PAGE = "generated/docs/language_status/progress.md"
SNAPSHOT_PAGES = ("det_survey.md", "det_port_design.md", "estate4_dbb_mortgage.md", "porting_loop.md", "transferability.md")
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


README_COUNT = re.compile(
    r"\b\d+\s+(?:`[^`]+`\s+)?(?:commands?|programs?|records?|languages?|tells|estates?|tests?|rules?)\b|\(\d+\)|\bacross all \d+\b",
    re.IGNORECASE,
)


def _readme_prose():
    """README text outside fenced code and <details> blocks, with backtick spans kept (a count can sit before one)."""
    text = (STATUS / "README.md").read_text(encoding="utf-8")
    text = re.sub(r"<details>.*?</details>", "", text, flags=re.DOTALL)
    return re.sub(r"^```.*?^```", "", text, flags=re.DOTALL | re.MULTILINE)


def test_readme_states_no_count_outside_details():
    hits = [m.group(0) for m in README_COUNT.finditer(_readme_prose())]
    assert not hits, f"docs/language_status/README.md states hand-written counts: {hits}; link the generated page"


def test_readme_language_table_has_no_numeric_columns():
    rows = [ln for ln in _readme_prose().splitlines() if ln.startswith("| ")]
    assert rows, "the language table moved"
    for row in rows:
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        assert not any(re.fullmatch(r"\d+(/\d+)?\*?", c) for c in cells), f"numeric cell in README table row: {row}"
