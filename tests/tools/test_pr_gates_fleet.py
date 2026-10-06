"""pr_gates: CI version-pin check and --vs-main attribution (subprocess mocked)."""

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pr_gates


def test_ci_pins_reads_workflows():
    pins = pr_gates.ci_pins()
    assert pins["python"] and pins["ruff"]  # ruff is pinned in ruff-audit.yml
    assert pins["mypy"]  # mypy is pinned in tests/requirements-mypy.txt


def test_mypy_workflow_installs_from_the_pin_file():
    yml = (pr_gates.REPO / ".github" / "workflows" / "mypy-audit.yml").read_text(encoding="utf-8")
    assert "pip install -r tests/requirements-mypy.txt" in yml


def test_version_warnings_flag_drift_and_print_private_venv():
    pins = {"python": "3.12", "ruff": "0.16.0", "mypy": "2.4.0"}
    msgs = pr_gates.version_warnings(pins, {"python": "3.12.3", "ruff": "0.15.1", "mypy": "1.0"})
    text = "\n".join(msgs)
    assert "ruff: local 0.15.1 != CI 0.16.0" in text
    assert "PRIVATE venv" in text and "ruff==0.16.0" in text
    assert "python:" not in text  # 3.12.3 matches 3.12


def test_version_warnings_quiet_when_matching():
    pins = {"python": "3.12", "ruff": "0.16.0", "mypy": "2.4.0"}
    assert pr_gates.version_warnings(pins, {"python": "3.12.9", "ruff": "0.16.0", "mypy": "2.4.0"}) == []


def test_attribute_failures_labels(monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        if cmd[:2] == ["git", "-C"] and "rev-parse" in cmd:
            return SimpleNamespace(returncode=0, stdout="abc1234\n", stderr="")
        if cmd and cmd[0] == "FAILS-ON-MAIN":
            return SimpleNamespace(returncode=1, stdout="x", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    plan = {"lint": [["FAILS-ON-MAIN"]], "audits": [["passes-on-main"]]}
    labels = pr_gates.attribute_failures(["lint", "audits"], lambda root: plan, {})
    assert labels == {"lint": "pre-existing on main@abc1234", "audits": "caused by branch"}
    assert any("fetch" in c for c in calls) and any("remove" in c for c in calls)


def test_ratchets_argument_parsing(monkeypatch):
    seen = {}
    monkeypatch.setattr(pr_gates, "run_ratchets", lambda chosen, env: seen.update(chosen=chosen) or 0)
    assert pr_gates.main(["--ratchets", "--only-ratchets", "estate", "ports"]) == 0
    assert seen["chosen"] == ["estate", "ports"]
    assert pr_gates.main(["--only-ratchets", "estate"]) == 0


def test_ratchets_skip_when_nothing_present(monkeypatch, tmp_path, capsys):
    env = {"GITGALAXY_MAINFRAME_CORPORA": str(tmp_path), "ESTATE_CRUCIBLE_PATH": str(tmp_path / "e"),
           "CICS_CRUCIBLE_PATH": str(tmp_path / "c"), "PATH": str(tmp_path)}  # fmt: skip
    ran = []
    monkeypatch.setattr(pr_gates, "run_gate", lambda cmds, root, e: ran.append(cmds) or (True, ""))
    assert pr_gates.run_ratchets(None, env) == 0  # skipped is not failed ...
    out = capsys.readouterr().out
    assert not ran  # ... and nothing was run
    assert out.count("not available:") == 6
    assert "not checked" in out and "mainframe_corpus.py fetch" in out and "mvn" in out


def test_ratchet_failure_prints_update_command(monkeypatch, tmp_path, capsys):
    env = {"GITGALAXY_MAINFRAME_CORPORA": str(tmp_path)}
    (tmp_path / "x" / ".git").mkdir(parents=True)
    monkeypatch.setattr(pr_gates, "run_gate", lambda cmds, root, e: (False, "drift"))
    assert pr_gates.run_ratchets(["ground-truth"], env) == 1
    out = capsys.readouterr().out
    assert "FAIL  ground-truth" in out and "ground_truth_ledger.py update" in out
    assert pr_gates.run_ratchets(["nope"], env) == 2


def test_audits_always_run_under_env_i_and_print_the_tool_used(monkeypatch, capsys):
    """#4551: whether or not the local version matches, the audit is clean-env and names the tool it used."""
    monkeypatch.setattr(
        pr_gates,
        "local_versions",
        lambda env=None: {"mypy": pr_gates.ci_pins()["mypy"], "ruff": pr_gates.ci_pins()["ruff"]},
    )
    [cmd] = pr_gates.pinned_mypy_audit(pr_gates.REPO, {})
    assert cmd[:2] == ["env", "-i"] and "NO_COLOR=1" in cmd and not any(a.startswith("FORCE_COLOR") for a in cmd)
    [cmd], _ = pr_gates.pinned_ruff_lint({})
    assert cmd[:2] == ["env", "-i"]
    out = capsys.readouterr().out
    assert "mypy used:" in out and "ruff used:" in out
