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


# ---- --provision and the shared-checkout WARN (#4270) ---------------------------------------------------------------
import json  # noqa: E402
import subprocess  # noqa: E402

import _cics_crucible_pin as cics_pin  # noqa: E402


def _git(*argv, cwd=None):
    subprocess.run(["git", *argv], cwd=cwd, check=True, capture_output=True)


def _repo(path: Path, tag: str | None = None, commits: int = 1) -> Path:
    path.mkdir(parents=True)
    _git("init", "-q", "-b", "main", cwd=path)
    for i in range(commits):
        (path / "f.txt").write_text(str(i))
        _git("add", "f.txt", cwd=path)
        _git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", str(i), cwd=path)
        if tag and i == 0:
            _git("tag", tag, cwd=path)
    return path


@pytest.fixture
def remote(tmp_path, monkeypatch):
    base = tmp_path / "remote"
    _repo(base / "squid-protocol" / "cics-crucible", tag=cics_pin.PINNED_REF, commits=2)  # HEAD past the pin
    for r in ("o/one", "o/two"):
        _repo(base / r)
    monkeypatch.setattr(ee, "census_repos", lambda: ["o/one", "o/two"])
    cands = tmp_path / "cands.json"
    cands.write_text(json.dumps({"candidates": [{"full_name": "Someone/Elsewhere", "description": "unread"}]}))
    monkeypatch.setattr(ee, "CANDIDATES_JSON", cands)
    return base


def test_provision_clones_at_the_pin_records_shas_and_is_idempotent(tmp_path, remote):
    root = tmp_path / "scratch"
    log: list[str] = []
    rec = ee.provision(root, str(remote), log=log.append)
    crucible = root / "cics-crucible"
    head = subprocess.run(
        ["git", "-C", str(crucible), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    assert rec["crucible"]["sha"] == head and rec["crucible"]["ref"] == cics_pin.PINNED_REF
    assert cics_pin.pin_mismatch(crucible) is None
    assert set(rec["census"]) == {"one", "two"} and all(len(v["sha"]) == 40 for v in rec["census"].values())
    assert json.loads((root / "provision.json").read_text())["census"]["one"]["repo"] == "o/one"
    assert len(log) == 4  # crucible clone + checkout, two census clones
    log.clear()
    (root / "census" / "stray").mkdir()
    again = ee.provision(root, str(remote), log=log.append)
    assert log == [] and again["crucible"]["sha"] == head  # nothing cloned twice
    assert any("stray" in e for e in again["errors"])
    env = ee.provisioned_env({}, root)
    assert env["CICS_CENSUS_CORPORA"] == str(root / "census") and env["GG_SCRATCH"] == str(root)
    assert env["CICS_CRUCIBLE_PATH"] == str(crucible)


def test_provision_refuses_an_estate4_candidate_before_cloning(tmp_path, remote, monkeypatch):
    monkeypatch.setattr(ee, "census_repos", lambda: ["o/one", "o/elsewhere"])
    with pytest.raises(ee.ProvisionRefused, match="o/elsewhere"):
        ee.provision(tmp_path / "scratch", str(remote))
    assert not (tmp_path / "scratch").exists()


def test_the_census_list_is_the_ineligible_list_minus_burned():
    import estate4_draw

    repos = ee.census_repos()
    assert repos and set(repos) < set(estate4_draw.INELIGIBLE_LIST)
    assert not {r.split("/")[-1] for r in repos} & {n.lower() for n in estate4_draw.BURNED_NAMES}
    assert not set(repos) & ee.candidate_names()  # the committed lists never overlap


def test_an_off_pin_shared_checkout_warns_a_private_one_fails(tmp_path, monkeypatch):
    main = tmp_path / "box" / "v6"
    main.mkdir(parents=True)
    shared = _repo(tmp_path / "box" / "cics-crucible", tag=cics_pin.PINNED_REF, commits=2)
    monkeypatch.setattr(ee.pr_gates, "_main_checkout", lambda: main)
    monkeypatch.delenv(cics_pin.ALLOW_UNPINNED_ENV, raising=False)
    item, ok, detail = ee.crucible_check({"CICS_CRUCIBLE_PATH": str(shared)})
    assert ok is None and "SHARED" in detail and "--provision" in detail
    private = _repo(tmp_path / "mine", tag=cics_pin.PINNED_REF, commits=2)
    assert ee.crucible_check({"CICS_CRUCIBLE_PATH": str(private)})[1] is False
    _git("checkout", "-q", cics_pin.PINNED_REF, cwd=shared)
    assert ee.crucible_check({"CICS_CRUCIBLE_PATH": str(shared)})[1] is True


def test_scratch_root_order(tmp_path, monkeypatch):
    monkeypatch.setenv("GG_SCRATCH", str(tmp_path / "env"))
    assert ee.scratch_root(tmp_path / "arg") == (tmp_path / "arg").resolve()
    assert ee.scratch_root() == (tmp_path / "env").resolve()
    monkeypatch.delenv("GG_SCRATCH")
    monkeypatch.setenv("GITGALAXY_WORKTREES", str(tmp_path / "wt"))
    assert ee.scratch_root() == tmp_path / "wt" / "_shared-scratch"
