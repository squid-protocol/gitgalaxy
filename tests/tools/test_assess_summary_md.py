"""Tests for gitgalaxy assess --summary-md (#5054)."""

from __future__ import annotations

import json
from pathlib import Path

from gitgalaxy.tools.readiness.assess import main, render_markdown


def test_render_markdown_includes_totals_eras_and_tells() -> None:
    report = {
        "schema": "readiness.v1",
        "tool_version": "2.12.2",
        "redacted": True,
        "totals": {
            "programs": 10,
            "parsed": 9,
            "unparsed": 1,
            "translation": {"whole": 5, "holes": 2, "refused": 2},
        },
        "eras": {"by_era": {"1": 2, "2": 8}, "tells": {"resp": 6, "dli": 2}},
        "rules": {"CICS_HANDLE": {"programs": 3}},
    }
    md = render_markdown(report)
    assert "Estate Readiness Summary (redacted)" in md
    assert "`5` whole, `2` with holes, `2` refused" in md
    assert "| Era 2 | 8 |" in md
    assert "| `resp` | 6 |" in md
    assert "| `CICS_HANDLE` | 3 |" in md


def test_assess_summary_md_writes_file_and_rejects_inside_estate(tmp_path: Path) -> None:
    estate = tmp_path / "estate"
    estate.mkdir()
    rc_bad = main([str(estate), "--no-translate", "--summary-md", str(estate / "sum.md")])
    assert rc_bad == 2

    out_json = tmp_path / "readiness.json"
    out_md = tmp_path / "summary.md"
    rc_ok = main([str(estate), "--no-translate", "--redact", "--out", str(out_json), "--summary-md", str(out_md)])
    assert rc_ok == 0
    assert json.loads(out_json.read_text(encoding="utf-8"))["redacted"] is True
    assert "Estate Readiness Summary (redacted)" in out_md.read_text(encoding="utf-8")
