"""#7155: negative controls for the corpus-diff gates (doom-rosetta, ports-compile, golden-crucible).

Each feeds the gate's real decision a planted regression and asserts red; a clean input is the positive control.
The measurement (a scan, a Maven build, a pytest run) is stubbed, so these prove the gate's logic, not the job around it.
rosetta-audit's control is test_audit_runners_refuse_empty.py::test_rosetta_audit_regression_against_baseline_exits_1.
"""

import copy
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS / "doom_speedrun"))
import crucible_check as cc  # noqa: E402
import doom_rosetta_check as dr  # noqa: E402
import ports_compile_check as pc  # noqa: E402

_GOLDEN = {"summary": {"functions": 10}, "sha": "abc", "files": {"a.c": ["c", 10, 10, 0, "h"]}, "exclusions": {}}


def test_doom_rosetta_goes_red_on_drift_and_on_a_missing_golden(monkeypatch):
    row = {"name": "planted-port"}
    scanned = {"value": copy.deepcopy(_GOLDEN)}
    monkeypatch.setattr(dr, "scan_and_build", lambda r, w, fetch=True: (scanned["value"], {}))
    monkeypatch.setattr(dr, "read_golden", lambda name: copy.deepcopy(_GOLDEN))
    report, _ = dr.check_port(row, Path("."))
    assert report == ""  # positive control: the golden itself is green
    scanned["value"]["summary"]["functions"] = 9
    scanned["value"]["files"]["a.c"] = ["c", 10, 9, 0, "h"]
    report, _ = dr.check_port(row, Path("."))
    assert "summary.functions" in report and "file a.c" in report  # a drifted port is reported by field and file
    monkeypatch.setattr(dr, "read_golden", lambda name: None)
    report, _ = dr.check_port(row, Path("."))
    assert "no golden" in report  # an unblessed port fails, it is not skipped


def test_doom_rosetta_main_exits_1_on_drift(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(dr, "select", lambda only: [{"name": "planted-port"}])
    monkeypatch.setattr(dr.shutil, "which", lambda name: "/usr/bin/ctags")
    result = {"report": ""}
    monkeypatch.setattr(dr, "check_port", lambda row, work: (result["report"], copy.deepcopy(_GOLDEN)))
    monkeypatch.setattr(dr, "read_golden", lambda name: copy.deepcopy(_GOLDEN))
    argv = ["--work", str(tmp_path)]
    assert dr.main(argv) == 0
    result["report"] = "planted-port: 1 difference(s) from the golden"
    assert dr.main(argv) == 1
    assert "planted-port: 1 difference(s) from the golden" in capsys.readouterr().err


def test_ports_compile_main_exits_1_on_a_port_that_does_not_compile_and_2_on_nothing_checked(monkeypatch, capsys):
    outcome = {"value": (3, [])}
    monkeypatch.setattr(pc, "check_equivalence", lambda cases, work, offline: outcome["value"])
    argv = ["--only", "equivalence"]
    assert pc.main(argv) == 0  # positive control: every committed port compiles
    outcome["value"] = (3, ["equivalence:planted/PROG"])
    assert pc.main(argv) == 1
    assert "equivalence:planted/PROG" in capsys.readouterr().out
    outcome["value"] = (0, [])
    assert pc.main(argv) == 2  # zero ports checked is a failure, never a pass


def test_golden_crucible_run_check_is_red_when_the_wrapped_pytest_fails(monkeypatch, capsys):
    rc = {"value": 0}
    out = {"value": ""}

    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, rc["value"], stdout=out["value"], stderr="")

    monkeypatch.setattr(cc.subprocess, "run", fake_run)
    monkeypatch.setattr(cc, "_venv_env", lambda py: {})
    assert cc.run_check("full", Path("python")) is True  # positive control
    rc["value"] = 1
    out["value"] = "noise\nStructural drift detected: planted.py differs\n"
    assert cc.run_check("full", Path("python")) is False
    assert "Structural drift detected: planted.py differs" in capsys.readouterr().out
