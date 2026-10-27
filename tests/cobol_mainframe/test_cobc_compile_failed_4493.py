"""#4493 slice A: a case cobc does not compile reaches the sweep row as `cobol_compile_failed` + cobc's stderr."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import det_port  # noqa: E402
import equivalence  # noqa: E402
import proof_sweep as ps  # noqa: E402

CASE = {"name": "demo", "program": "DEMO"}
STDERR = "COBOL side failed:\n\nsrc/PROGRAM.cbl: 12: error: 'FOO' is not defined"


def test_a_missing_program_binary_is_a_compile_failure(tmp_path):
    rep = equivalence.cobc_failure_report(CASE, tmp_path, STDERR)
    assert rep["cobol_compile_failed"] is True and rep["proven"] is False and rep["outputs"] == {}
    assert "error: 'FOO' is not defined" in rep["cobc_stderr"]


def test_a_run_time_failure_is_not(tmp_path):
    (tmp_path / "program").write_bytes(b"")  # compiled: the failure came later
    assert equivalence.cobc_failure_report(CASE, tmp_path, STDERR) is None


def test_the_flag_reaches_det_port_and_the_sweep_row(tmp_path, monkeypatch):
    def fake_run(argv, **kw):
        keep = Path(argv[argv.index("--keep") + 1])
        keep.mkdir(parents=True)
        rep = equivalence.cobc_failure_report(CASE, keep / "cobol", STDERR)
        (keep / "report.json").write_text(json.dumps(rep), encoding="utf-8")
        return subprocess.CompletedProcess(argv, 1)

    monkeypatch.setattr(det_port.subprocess, "run", fake_run)
    (tmp_path / "demo").mkdir()
    proof = det_port._prove("demo", tmp_path, "none")
    assert proof["cobol_compile_failed"] and not proof["proved"] and "FOO" in proof["cobc_stderr"]
    # a proof that compiled carries neither key
    monkeypatch.setattr(det_port.subprocess, "run", lambda argv, **kw: subprocess.CompletedProcess(argv, 0))
    assert "cobol_compile_failed" not in det_port._prove("demo", tmp_path, "none")

    summary = [{"case": "demo", **proof, "statements": 3, "translated_statements": 3}]
    (tmp_path / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    monkeypatch.setattr(ps, "det_cases", lambda skip_db2=False: ["demo"])
    monkeypatch.setattr(ps.subprocess, "run", lambda *a, **k: None)
    row = ps.det_sweep(tmp_path, 1, "none")["demo"]
    assert row["cobol_compile_failed"] is True and "FOO" in row["cobc_stderr"] and row["proved"] is False
    summary[0].pop("cobol_compile_failed")
    (tmp_path / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    assert "cobol_compile_failed" not in ps.det_sweep(tmp_path, 1, "none")["demo"]
