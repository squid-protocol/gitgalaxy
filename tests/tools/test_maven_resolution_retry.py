# ruff: noqa: S101
"""#7561: a Maven dependency-resolution failure (Central miss, cached negative lookup) is retried once with `-U`;
a compile error or test failure never is."""

from __future__ import annotations

import subprocess

import maven_exe

MVN = maven_exe.mvn_executable({"PATH": ""})
JCC_LOG = (
    "[ERROR] \tCould not find artifact com.ibm.db2:jcc:jar:11.5.9.0 in central (https://repo.maven.apache.org/maven2)"
)

# Maven's text for a miss it cached earlier in the same local repository (det sweep run 42721961353, shard 6/6)
CACHED_MISS_LOG = (
    "[FATAL] Non-resolvable parent POM for com.gitgalaxy.modernized:cics-crucible:1.0.0-SNAPSHOT: The following "
    "artifacts could not be resolved: org.springframework.boot:spring-boot-starter-parent:pom:3.2.4 (present, but "
    "unavailable): org.springframework.boot:spring-boot-starter-parent:pom:3.2.4 was not found in "
    "https://repo.maven.apache.org/maven2 during a previous attempt. This failure was cached in the local repository "
    "and resolution is not reattempted until the update interval of central has elapsed or updates are forced"
)


def _proc(code: int, out: str = "", err: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([MVN], code, out, err)


def _script(monkeypatch, results):
    calls = []

    def fake(cmd, **_kwargs):
        calls.append(list(cmd))
        return results[len(calls) - 1]

    monkeypatch.setattr(maven_exe, "run_decoded", fake)
    return calls


def test_resolution_failures_are_told_from_the_rest():
    assert maven_exe.is_resolution_failure(JCC_LOG)
    assert maven_exe.is_resolution_failure("Could not transfer artifact x: Connection reset")
    assert maven_exe.is_resolution_failure(CACHED_MISS_LOG)
    assert not maven_exe.is_resolution_failure("[ERROR] COMPILATION ERROR : cannot find symbol")
    assert not maven_exe.is_resolution_failure("Tests run: 3, Failures: 1")
    assert not maven_exe.is_resolution_failure("")


def test_a_resolution_failure_reruns_once_with_dash_u(monkeypatch):
    calls = _script(monkeypatch, [_proc(1, err=JCC_LOG), _proc(0, out="ok")])
    proc = maven_exe.run_maven_retrying_resolution([MVN, "-q", "test"])
    assert proc.returncode == 0
    assert calls == [[MVN, "-q", "test"], [MVN, "-U", "-q", "test"]]
    assert "jcc" in proc.stdout and "reran once with -U" in proc.stdout


def test_a_second_resolution_failure_is_returned_not_looped(monkeypatch):
    calls = _script(monkeypatch, [_proc(1, err=JCC_LOG), _proc(1, err=JCC_LOG)])
    assert maven_exe.run_maven_retrying_resolution([MVN, "test"]).returncode == 1
    assert len(calls) == 2


def test_compile_and_test_failures_and_success_run_once(monkeypatch):
    for result in (_proc(1, err="COMPILATION ERROR"), _proc(1, out="Tests run: 1, Failures: 1"), _proc(0)):
        calls = _script(monkeypatch, [result])
        assert maven_exe.run_maven_retrying_resolution([MVN, "test"]) is result
        assert len(calls) == 1


def test_a_cached_miss_reruns_with_dash_u_which_ignores_the_cache(monkeypatch):
    calls = _script(monkeypatch, [_proc(1, err=CACHED_MISS_LOG), _proc(0, out="ok")])
    assert maven_exe.run_maven_retrying_resolution([MVN, "-q", "-B", "test"]).returncode == 0
    assert calls[1] == [MVN, "-U", "-q", "-B", "test"]
