"""#5048: `docker build` of the oracle images fetches the digest-pinned base and runs apt; a network hiccup is retried
and named infrastructure, any other build failure fails at once. Plus a sweep over every tracked Dockerfile."""

import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_common as common  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
TOOLS = REPO / "tests" / "tools"


def _script(monkeypatch, results):
    """Fake `docker build`: each call yields the next result (a CompletedProcess spec or an exception)."""
    calls, sleeps = [], []
    queue = list(results)

    def run(cmd, **kwargs):
        calls.append(cmd)
        item = queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        rc, err = item
        return subprocess.CompletedProcess(cmd, rc, "", err)

    monkeypatch.setattr(common.subprocess, "run", run)
    monkeypatch.setattr(common.time, "sleep", sleeps.append)
    return calls, sleeps


def test_first_try_success_is_one_call(monkeypatch):
    calls, sleeps = _script(monkeypatch, [(0, "")])
    common.docker_build("-q", "-t", "x", ".")
    assert calls == [["docker", "build", "-q", "-t", "x", "."]]
    assert not sleeps


@pytest.mark.parametrize(
    "err",
    [
        "net/http: TLS handshake timeout",
        "dial tcp: lookup deb.debian.org: no such host",
        "read tcp: connection reset by peer",
        "E: Failed to fetch http://deb.debian.org/x  Temporary failure resolving 'deb.debian.org'",
        "unexpected status 503 Service Unavailable",
        "toomanyrequests: rate limit",
        "Get https://registry-1.docker.io/v2/: i/o timeout",
    ],
)
def test_a_network_failure_is_retried_with_growing_backoff(monkeypatch, err):
    calls, sleeps = _script(monkeypatch, [(1, err), (1, err), (0, "")])
    common.docker_build("-t", "x", ".", backoff=2)
    assert len(calls) == 3
    assert sleeps == [2, 4]


def test_exhausted_retries_name_infrastructure(monkeypatch):
    calls, sleeps = _script(monkeypatch, [(1, "TLS handshake timeout")] * 3)
    with pytest.raises(common.DockerBuildInfraError, match="INFRASTRUCTURE") as exc:
        common.docker_build("-t", "x", ".", attempts=3, backoff=1)
    assert "TLS handshake timeout" in str(exc.value)
    assert len(calls) == 3
    assert len(sleeps) == 2  # no sleep after the last attempt


@pytest.mark.parametrize(
    "err",
    [
        'the command returned a non-zero code: 1 (test "$(cobc --version | head -n 1)" = ...)',
        "failed to solve: dockerfile parse error on line 3: unknown instruction: RUNN",
        "COPY failed: file not found in build context: linuxx64_odbc_cli.tar.gz",
        "E: Version '3.1.2-9' for 'gnucobol3' was not found",
        "",
    ],
)
def test_a_real_build_failure_is_not_retried_or_called_infrastructure(monkeypatch, err):
    calls, sleeps = _script(monkeypatch, [(1, err)])
    with pytest.raises(RuntimeError) as exc:
        common.docker_build("-t", "x", ".")
    assert not isinstance(exc.value, common.DockerBuildInfraError)
    assert "INFRASTRUCTURE" not in str(exc.value)
    assert len(calls) == 1
    assert not sleeps


@pytest.mark.parametrize("exc", [subprocess.TimeoutExpired("docker", 1), OSError("docker: not found")])
def test_a_timeout_or_os_error_is_retried_then_infrastructure(monkeypatch, exc):
    calls, _ = _script(monkeypatch, [exc, exc])
    with pytest.raises(common.DockerBuildInfraError, match="INFRASTRUCTURE"):
        common.docker_build("-t", "x", ".", attempts=2, backoff=1)
    assert len(calls) == 2


# --- the whole class: every docker build and every Dockerfile --------------------------------------------------------


def test_every_docker_build_in_the_tools_goes_through_the_retry_helper():
    offenders = []
    for path in sorted(TOOLS.rglob("*.py")):
        if path == TOOLS / "equivalence_common.py":
            continue
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"""["']docker["']\s*,\s*["']build["']|_docker\(\s*["']build["']""", text):
            offenders.append(f"{path.relative_to(REPO)}:{text.count(chr(10), 0, m.start()) + 1}")
    assert not offenders, f"bare docker build, use equivalence_common.docker_build: {offenders}"


def test_both_call_sites_use_the_helper():
    for name in ("equivalence.py", "equivalence_db2.py"):
        assert "docker_build(" in (TOOLS / name).read_text(encoding="utf-8"), name


def _tracked_dockerfiles():
    out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True).stdout
    return [REPO / p for p in out.splitlines() if re.search(r"(^|/)(Dockerfile[^/]*|[^/]*\.Dockerfile)$", p)]


def test_there_are_dockerfiles_to_sweep():
    assert {p.name for p in _tracked_dockerfiles()} >= {"gnucobol.Dockerfile", "gnucobol-db2.Dockerfile"}


def test_every_dockerfile_fetch_retries_and_nothing_is_swallowed():
    for path in _tracked_dockerfiles():
        body = [ln for ln in path.read_text(encoding="utf-8").splitlines() if not ln.lstrip().startswith("#")]
        assert not any("|| true" in ln for ln in body), f"{path.name}: a failed step must fail the build"
        for ln in body:
            for m in re.finditer(r"apt(?:-get)?(?P<opts>[^&|;]*)", ln):
                if re.search(r"\b(update|install)\b", m.group("opts")):
                    assert "Acquire::Retries=" in m.group("opts"), f"{path.name}: {ln}"
            for m in re.finditer(r"\bnpm\s+(?:install|i|ci)\b[^&|;]*", ln):
                assert "--fetch-retries" in m.group(0), f"{path.name}: {ln}"
            for m in re.finditer(r"\bpip3?\s+install\b[^&|;]*", ln):
                assert "--retries" in m.group(0), f"{path.name}: {ln}"
            assert not re.search(r"\bcurl\b", ln) or "--retry" in ln, f"{path.name}: {ln}"
