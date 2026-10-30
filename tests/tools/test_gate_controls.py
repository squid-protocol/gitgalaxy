"""#7155: every gate is listed, a named failure proof exists, and the first controls prove gates can go red."""

import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS.parent))
import gate_controls as gc
import mypy_audit
import ruff_audit

REPO = TOOLS.parents[1]
WORKFLOWS = REPO / ".github" / "workflows"


def _pr_workflows() -> set[str]:
    out = set()
    for path in WORKFLOWS.glob("*.yml"):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        on = doc.get(True) or doc.get("on") or {}  # YAML reads a bare `on:` key as True
        if {"pull_request", "pull_request_target"} & set(on if isinstance(on, (dict, list)) else [on]):
            out.add(path.name)
    return out


def test_every_workflow_on_a_pr_is_a_listed_gate_or_says_why_not():
    listed = {g.workflow for g in gc.GATES} | set(gc.NOT_GATES)
    assert not _pr_workflows() - listed, "add it to gate_controls.GATES, or NOT_GATES with the reason"
    assert not {w for w in listed if not (WORKFLOWS / w).exists()}, "a listed workflow is gone"


def test_every_required_check_is_listed():
    import shepherd_gh

    names = {g.name.split(" (")[0] for g in gc.GATES if g.required}
    assert set(shepherd_gh.REQUIRED_CHECKS) <= names


def test_every_named_proof_is_a_real_test():
    for g in gc.GATES:
        if g.proof:
            path, _, name = g.proof.partition("::")
            assert f"def {name}(" in (REPO / path).read_text(encoding="utf-8"), f"{g.name}: {g.proof} is gone"


def test_a_notice_cannot_also_claim_a_proof():
    assert not [g.name for g in gc.GATES if g.notice and g.proof]


def test_the_unproven_count_only_goes_down():
    n = len(gc.unproven())
    assert n <= gc.MAX_UNPROVEN, f"{n} gates have no failure proof, the limit is {gc.MAX_UNPROVEN}: add a control"
    assert n == gc.MAX_UNPROVEN, f"good news: {n} unproven now, so lower MAX_UNPROVEN to {n}"


def _audit_at(tmp_path, monkeypatch, module, baseline=None):
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(baseline or {}), encoding="utf-8")
    monkeypatch.setattr(module, "BASELINE_PATH", path)


@pytest.mark.skipif(shutil.which("ruff") is None, reason="needs ruff")
def test_ruff_audit_fails_on_a_planted_finding_with_real_ruff(tmp_path, monkeypatch, capsys):
    """The negative control: real ruff over a planted file, so a broken runner or parser can't pass unnoticed."""
    (tmp_path / "planted.py").write_text("import os\n", encoding="utf-8")
    real = ruff_audit.run_ruff_findings
    _audit_at(tmp_path, monkeypatch, ruff_audit)
    monkeypatch.setattr(ruff_audit, "run_ruff_findings", lambda: real(tmp_path, tmp_path))
    monkeypatch.setattr(ruff_audit, "run_ruff_format_check", lambda: True)
    assert ruff_audit.run_ci_check() == 1
    assert "F401" in capsys.readouterr().out


def test_ruff_audit_fails_on_format_alone(tmp_path, monkeypatch, capsys):
    _audit_at(tmp_path, monkeypatch, ruff_audit)
    monkeypatch.setattr(ruff_audit, "run_ruff_findings", lambda: {})
    monkeypatch.setattr(ruff_audit, "run_ruff_format_check", lambda: False)
    assert ruff_audit.run_ci_check() == 1  # no lint findings at all: format is zero-tolerance on its own
    assert "ruff format" in capsys.readouterr().out


def test_mypy_audit_fails_on_a_new_error(tmp_path, monkeypatch, capsys):
    (tmp_path / "planted.py").write_text("x: int = 'a'\n", encoding="utf-8")
    stdout = "planted.py:1: error: Incompatible types in assignment  [assignment]\n"
    found = mypy_audit.parse_mypy_output(stdout, tmp_path)
    assert found, "the parser lost a real mypy line, so the audit would pass on anything"
    _audit_at(tmp_path, monkeypatch, mypy_audit)
    monkeypatch.setattr(mypy_audit, "run_mypy_findings", lambda: found)
    assert mypy_audit.run_ci_check() == 1
    assert "1 NEW type error" in capsys.readouterr().out
    _audit_at(tmp_path, monkeypatch, mypy_audit, {k: "known" for k in found})
    assert mypy_audit.run_ci_check() == 0  # the same error, baselined, passes: the ratchet, not a blanket failure
