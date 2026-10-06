"""equivalence_env: JDK 17 detection (refusing loudly without one), the exported environment, the pin escape hatch."""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import equivalence_env as ee


def _jvm(tmp_path: Path, *names: str) -> Path:
    root = tmp_path / "jvm"
    for n in names:
        (root / n / "bin").mkdir(parents=True)
    return root


def _majors(table: dict[str, int]):
    return lambda home: table.get(home.name)


def test_find_jdk17_prefers_a_17_over_a_java_home_of_21(tmp_path):
    root = _jvm(tmp_path, "java-21-openjdk-amd64", "java-17-openjdk-amd64")
    env = {"JAVA_HOME": str(root / "java-21-openjdk-amd64")}
    home, notes = ee.find_jdk17(env, root, _majors({"java-21-openjdk-amd64": 21, "java-17-openjdk-amd64": 17}))
    assert home.name == "java-17-openjdk-amd64"
    assert notes and "JAVA_HOME" in notes[0] and "not a JDK 17" in notes[0]


def test_find_jdk17_takes_jdk_17_env_first(tmp_path):
    root = _jvm(tmp_path, "java-17-openjdk-amd64", "custom17")
    env = {"JDK_17": str(root / "custom17")}
    home, notes = ee.find_jdk17(env, root, _majors({"java-17-openjdk-amd64": 17, "custom17": 17}))
    assert home.name == "custom17" and notes == []


def test_find_jdk17_refuses_loudly_when_only_another_jdk_exists(tmp_path):
    root = _jvm(tmp_path, "java-21-openjdk-amd64")
    with pytest.raises(ee.JdkError) as e:
        ee.find_jdk17({}, root, _majors({"java-21-openjdk-amd64": 21}))
    assert "JDK 21" in str(e.value) and "release version 17 not supported" in str(e.value)


@pytest.mark.skipif(os.name == "nt", reason="a shell-script java")
def test_java_major_reads_the_version_line(tmp_path):
    for name, line in (("j17", 'openjdk version "17.0.12" 2024-07-16'), ("j8", 'java version "1.8.0_402"')):
        java = tmp_path / name / "bin" / "java"
        java.parent.mkdir(parents=True)
        java.write_text(f"#!/bin/sh\necho '{line}' >&2\n")
        java.chmod(0o755)
    assert ee.java_major(tmp_path / "j17") == 17
    assert ee.java_major(tmp_path / "j8") == 8
    assert ee.java_major(tmp_path / "missing") is None


def test_environment_sets_the_crucibles_the_jdk_and_the_escape_hatch(tmp_path, monkeypatch):
    monkeypatch.setattr(ee, "find_jdk17", lambda _env, _root: (tmp_path / "jdk17", []))
    monkeypatch.delenv("CICS_CRUCIBLE_PATH", raising=False)
    env, _ = ee.environment(tmp_path / "my-crucible", unpinned=True)
    assert env["CICS_CRUCIBLE_PATH"] == str((tmp_path / "my-crucible").resolve())
    assert env["CICS_CRUCIBLE_ALLOW_UNPINNED"] == "1"
    assert env["JAVA_HOME"] == env["JDK_17"] == str(tmp_path / "jdk17")
    assert env["PATH"].startswith(str(tmp_path / "jdk17" / "bin"))
    assert env["PYTHONPATH"] == str(ee.REPO) and env["GITGALAXY_LICENSE_KEY"] == "COMMUNITY_FREE_TIER"
    assert "ESTATE_CRUCIBLE_PATH" in env
    lines = ee.shell_lines(dict(env, CICS_CRUCIBLE_PATH="/a b/c"))
    assert "export CICS_CRUCIBLE_PATH='/a b/c'" in lines


def test_main_exits_2_without_a_jdk17(monkeypatch, capsys):
    def boom(*_a, **_k):
        raise ee.JdkError("no JDK 17 found -- only: x (JDK 21)")

    monkeypatch.setattr(ee, "find_jdk17", boom)
    assert ee.main(["--shell"]) == 2
    assert "REFUSED" in capsys.readouterr().err


def test_pin_message_applies_and_restores_the_escape_hatch(tmp_path, monkeypatch):
    seen = []

    class Pin:
        ALLOW_UNPINNED_ENV = "X_ALLOW_UNPINNED"

        @staticmethod
        def pin_mismatch(_path):
            seen.append(os.environ.get("X_ALLOW_UNPINNED"))
            return None if os.environ.get("X_ALLOW_UNPINNED") == "1" else "off pin\nFix: checkout"

    monkeypatch.delenv("X_ALLOW_UNPINNED", raising=False)
    assert ee.pin_message(Pin, tmp_path, {"X_ALLOW_UNPINNED": "1"}) is None
    assert ee.pin_message(Pin, tmp_path, {}) == "off pin Fix: checkout"
    assert seen == ["1", None] and "X_ALLOW_UNPINNED" not in os.environ
