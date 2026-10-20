"""pr_gates: CI version-pin check and --vs-main attribution (subprocess mocked)."""

import subprocess
import sys

from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pr_gates


def test_ci_pins_reads_workflows():
    pins = pr_gates.ci_pins()
    assert pins["python"] and pins["ruff"]  # ruff is pinned in ci/requirements/lint.in
    assert pins["mypy"]  # mypy is pinned in tests/requirements-mypy.txt


def test_mypy_workflow_installs_from_the_pin_file():
    yml = (pr_gates.REPO / ".github" / "workflows" / "mypy-audit.yml").read_text(encoding="utf-8")
    assert "pip install --require-hashes -r ci/requirements/mypy.txt" in yml


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
    # ... and nothing that needs an external resource ran: only cics-spec (spec PR 4) and time (#5166), which need none
    assert [c[0][2:] for c in ran] == [["gitgalaxy.standards.cics", "regen", "--check"], ["check"]]
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


@pytest.mark.skipif(sys.platform == "win32", reason="the gate runs under POSIX `env -i` with a /usr/bin:/bin PATH")
def test_matching_tool_off_the_interpreter_bin_dir_is_on_the_clean_path(monkeypatch, tmp_path):
    """churn's precheck runs under /usr/bin/python3 with the pinned ruff on ~/.local/bin: the gate's `env -i` PATH must
    name the dir the matched ruff/mypy is in, not the interpreter's (it failed lint in 0 s with 'ruff' not found)."""
    tools = tmp_path / "local-bin"
    tools.mkdir()
    for name in ("ruff", "mypy"):
        (tools / name).write_text("#!/bin/sh\n")
        (tools / name).chmod(0o755)
    monkeypatch.setattr(
        pr_gates,
        "local_versions",
        lambda env=None: {"mypy": pr_gates.ci_pins()["mypy"], "ruff": pr_gates.ci_pins()["ruff"]},
    )
    sysbin = tmp_path / "sysbin"  # the interpreter's bin dir, with no ruff/mypy in it (like /usr/bin)
    sysbin.mkdir()
    monkeypatch.setattr(pr_gates, "PY", str(sysbin / "python3"))
    env = {"PATH": f"{sysbin}:{tools}"}
    [cmd] = pr_gates.pinned_mypy_audit(pr_gates.REPO, env)
    assert f"PATH={tools.resolve()}:/usr/bin:/bin" in cmd
    [cmd], _ = pr_gates.pinned_ruff_lint(env)
    assert f"PATH={tools.resolve()}:/usr/bin:/bin" in cmd


@pytest.mark.slow(reason="builds the pinned actionlint venv on a fresh runner (pip + release binary download)")
def test_workflows_gate_is_in_fast_and_catches_expression_arithmetic(tmp_path, monkeypatch):
    """#5768: `${{ x - 3 }}` made full-suite-gate.yml unloadable; the --fast `workflows` gate (actionlint) names it."""
    plan = pr_gates.gates(SimpleNamespace(lower_baseline=False), {})
    assert "workflows" in plan
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "bad.yml").write_text(
        "on: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n    timeout-minutes: ${{ (matrix.t || 30) - 3 }}\n"
        "    steps:\n      - run: echo hi\n",
        encoding="utf-8",
    )
    rc = pr_gates.actionlint_gate(tmp_path)
    if not (pr_gates.MYPY_CACHE / f"actionlint-{pr_gates.ACTIONLINT_PIN}" / ".ready").exists():
        pytest.skip("actionlint could not be installed here (offline)")
    assert rc != 0
    (wf / "bad.yml").write_text(
        "on: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo hi\n", encoding="utf-8"
    )
    assert pr_gates.actionlint_gate(tmp_path) == 0


def test_workflows_gate_passes_with_a_note_when_actionlint_cannot_install(tmp_path, monkeypatch, capsys):
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "a.yml").write_text("on: push\n", encoding="utf-8")
    monkeypatch.setattr(pr_gates, "MYPY_CACHE", tmp_path / "cache")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr=""))
    assert pr_gates.actionlint_gate(tmp_path) == 0
    assert "could not be installed" in capsys.readouterr().out
