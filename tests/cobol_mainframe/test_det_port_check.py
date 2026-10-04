"""det_port.py check: which ports a change moves -- each case's port compared file by file with the base's."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import det_port  # noqa: E402


def _port(work: Path, case: str, files: dict[str, str]) -> None:
    for rel, text in files.items():
        f = work / case / "port" / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")


def test_a_changed_port_is_named_with_its_file_and_lines(tmp_path):
    base, new = tmp_path / "base", tmp_path / "new"
    svc = "service/XService.java"
    _port(base, "same", {svc: "a\nb\n"})
    _port(new, "same", {svc: "a\nb\n"})
    _port(base, "moved", {svc: "a\nb\nc\n", "cobolrt/Cobol.java": "x\n"})
    _port(new, "moved", {svc: "a\nB\nc\n", "cobolrt/Cobol.java": "x\n"})
    _port(new, "added", {svc: "a\n"})
    rows = {r["case"]: r for r in det_port.compare(base, new)}
    assert rows["same"]["status"] == "unchanged"
    assert rows["moved"]["status"] == "changed"
    assert rows["moved"]["files"] == [{"file": svc, "lines": 2}]  # one line out, one in; the runtime unchanged
    assert rows["added"]["status"] == "new"


def test_every_case_is_listed():
    cases = det_port.all_cases()
    assert "carddemo-cobtupdt" in cases and any(c.startswith("cbsa-") for c in cases)
    assert cases == sorted(cases)
