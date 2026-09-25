"""tests/tools/preflight.py (#3654): gate selection, changed-file discovery from any
directory, skips with reasons, and the summary table. The real gates are not run here."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "preflight", Path(__file__).resolve().parents[1] / "tools" / "preflight.py"
)
preflight = importlib.util.module_from_spec(_SPEC)
sys.modules["preflight"] = preflight  # dataclasses resolve annotations through sys.modules
_SPEC.loader.exec_module(preflight)


def test_changed_files_are_repo_relative_sorted_existing_py(monkeypatch, tmp_path):
    (tmp_path / "pkg").mkdir()
    for name in ("pkg/b.py", "a.py", "notes.txt"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    monkeypatch.setattr(preflight, "REPO_ROOT", tmp_path)
    outputs = {
        "origin/main...HEAD": "pkg/b.py\ngone.py\n",  # gone.py: deleted since, not on disk
        "HEAD": "a.py\nnotes.txt\n",
        "--others": "pkg/b.py\n",
    }

    def fake_run(cmd, cwd, **_kw):
        assert cwd == tmp_path  # always the repo root, whatever the caller's cwd
        key = next(k for k in outputs if k in cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout=outputs[key], stderr="")

    monkeypatch.setattr(preflight.subprocess, "run", fake_run)
    assert preflight.changed_py_files() == ["a.py", "pkg/b.py"]


def test_ruff_format_skips_when_nothing_changed():
    with pytest.raises(preflight.SkipGate, match="no .py files changed"):
        preflight._ruff_format(preflight.GateContext("python", [], None))


def test_java_gates_skip_without_a_corpus(tmp_path):
    ctx = preflight.GateContext("python", [], tmp_path)
    gate = next(g for g in preflight.GATES if g.name == "java-cics-genapp")
    assert preflight.run_gate(gate, ctx, {}).status == "SKIP"


def test_java_env_names_what_is_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("JDK_17", raising=False)
    monkeypatch.delenv("JDK_21", raising=False)
    monkeypatch.setattr(preflight, "REPO_ROOT", tmp_path)
    env, why = preflight.java_env()
    assert env is None and "JDK_17" in why and "setup_java_toolchain.sh" in why
    for v in ("17", "21"):
        (tmp_path / ".tools" / f"jdk-{v}" / "bin").mkdir(parents=True)
        (tmp_path / ".tools" / f"jdk-{v}" / "bin" / "javac").write_text("", encoding="utf-8")
    env, why = preflight.java_env()
    assert env["JAVA_HOME"] == env["JDK_17"] == str(tmp_path / ".tools" / "jdk-17")


def test_the_table_lists_every_gate_and_the_failed_tails():
    out = preflight.render(
        [
            preflight.Result("ruff-audit", "PASS", 1.25),
            preflight.Result("mypy-audit", "FAIL", 3.0, "exit 1", ["error: X", "Found 1 error"]),
            preflight.Result("java-carddemo", "SKIP", reason="JDK_17 is not set"),
        ]
    )
    assert "ruff-audit             PASS       1.2s" in out
    assert "mypy-audit             FAIL       3.0s  exit 1" in out
    assert "java-carddemo          SKIP          -  JDK_17 is not set" in out
    assert out.endswith("--- mypy-audit: last 2 lines ---\nerror: X\nFound 1 error")
