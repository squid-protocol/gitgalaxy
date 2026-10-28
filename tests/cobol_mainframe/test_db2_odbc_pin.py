"""#4980: IBM's ODBC CLI driver -- the Db2 oracle image's one network download -- is pinned (url + sha256), fetched with
retries, cached in CI, checked again in the Dockerfile, and a failed download names itself as infrastructure."""

import hashlib
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_db2 as db2  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
PAYLOAD = b"not really a driver"
SHA = hashlib.sha256(PAYLOAD).hexdigest()


def _pin(url="https://example.invalid/linuxx64_odbc_cli.tar.gz", sha=SHA):
    return {"url": url, "sha256": sha}


def _curl_writes(monkeypatch, body: bytes | None, rc: int = 0, stderr: str = ""):
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        if body is not None:
            Path(cmd[cmd.index("--output") + 1]).write_bytes(body)
        return subprocess.CompletedProcess(cmd, rc, "", stderr)

    monkeypatch.setattr(db2.subprocess, "run", run)
    return calls


# --- the pin and the Dockerfile -------------------------------------------------------------------------------------


def test_the_pin_is_an_https_url_and_a_sha256():
    pin = db2.odbc_pin()
    assert pin["url"].startswith("https://")
    assert re.fullmatch(r"[0-9a-f]{64}", pin["sha256"])


def test_the_dockerfile_copies_the_driver_and_checks_it_instead_of_adding_a_url():
    text = (REPO / "tests" / "equivalence" / "gnucobol-db2.Dockerfile").read_text(encoding="utf-8")
    instructions = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    body = "\n".join(instructions)
    assert not re.search(r"^\s*ADD\s+https?://", body, re.M), "a bare ADD <url> has no retry and no checksum"
    assert "https://" not in body
    assert f"COPY {db2.ODBC_TARBALL.name} " in body
    assert "COPY odbc_cli.pin " in body
    assert "sha256sum -c" in body


def test_the_tarball_is_git_ignored_and_the_pin_is_not():
    ignore = (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert f"tests/equivalence/{db2.ODBC_TARBALL.name}" in ignore


def test_a_pin_move_stales_the_db2_evidence():
    text = (REPO / "tests" / "tools" / "evidence.py").read_text(encoding="utf-8")
    assert text.count("tests/equivalence/odbc_cli.pin") >= 2  # the ORACLE globs and the oracle:image-db2 component


@pytest.mark.parametrize("workflow", ["det-sweep.yml", "evidence-refresh.yml"])
def test_every_workflow_that_builds_the_db2_image_caches_the_driver_on_the_pin(workflow):
    text = (REPO / ".github" / "workflows" / workflow).read_text(encoding="utf-8")
    assert "tests/equivalence/linuxx64_odbc_cli.tar.gz" in text
    assert re.search(r"hashFiles\('gitgalaxy/tests/equivalence/odbc_cli\.pin'\)", text)


@pytest.mark.parametrize("job", ["shard", "db2"])
def test_every_equivalence_e2e_job_that_can_build_the_db2_image_restores_and_saves_the_driver(job):
    """#6921: a shard's cbsa-updacc proof built the Db2 image with no driver cache and failed on an IBM curl timeout."""
    text = (REPO / ".github" / "workflows" / "equivalence-e2e.yml").read_text(encoding="utf-8")
    body = re.split(rf"^  {job}:\n", text, flags=re.M)[1]
    body = re.split(r"^  [a-z0-9-]+:\n", body, flags=re.M)[0]
    key = r"db2-odbc-cli-\$\{\{ hashFiles\('tests/equivalence/odbc_cli\.pin'\) \}\}"
    assert re.search(
        rf"actions/cache/restore@.*\n\s+with:\n\s+path: tests/equivalence/linuxx64_odbc_cli\.tar\.gz\n\s+key: {key}",
        body,
    )
    save = body.split("Save the Db2 ODBC CLI driver to the cache")[1]
    assert "github.event_name != 'pull_request'" in save and "actions/cache/save@" in save
    assert "continue-on-error: true" in save


# --- the fetch ------------------------------------------------------------------------------------------------------


def test_a_matching_file_already_there_is_kept_without_a_download(tmp_path, monkeypatch):
    dest = tmp_path / "cli.tgz"
    dest.write_bytes(PAYLOAD)
    calls = _curl_writes(monkeypatch, b"other")
    assert db2.fetch_odbc_cli(dest, _pin()) == dest
    assert calls == []
    assert dest.read_bytes() == PAYLOAD


def test_a_miss_downloads_with_retries_and_verifies(tmp_path, monkeypatch):
    dest = tmp_path / "cli.tgz"
    calls = _curl_writes(monkeypatch, PAYLOAD)
    assert db2.fetch_odbc_cli(dest, _pin()) == dest
    cmd = calls[0]
    assert cmd[0] == "curl"
    assert {"--fail", "--location", "--retry", "--retry-all-errors", "--connect-timeout"} <= set(cmd)
    assert dest.read_bytes() == PAYLOAD
    assert not list(tmp_path.glob("*.part"))


def test_a_stale_or_corrupt_cached_file_is_replaced(tmp_path, monkeypatch):
    dest = tmp_path / "cli.tgz"
    dest.write_bytes(b"truncated")
    _curl_writes(monkeypatch, PAYLOAD)
    db2.fetch_odbc_cli(dest, _pin())
    assert dest.read_bytes() == PAYLOAD


@pytest.mark.parametrize(
    ("body", "rc", "why"),
    [
        (None, 22, "curl exited 22"),  # HTTP error / DNS / reset after the retries
        (None, 0, "no file"),  # curl "succeeded" and wrote nothing
        (b"", 0, "is not the pinned"),  # an empty body
        (PAYLOAD[:5], 0, "is not the pinned"),  # a truncated download
        (b"<html>maintenance</html>", 0, "is not the pinned"),  # an error page served with 200
    ],
)
def test_every_download_failure_names_itself_as_infrastructure(tmp_path, monkeypatch, body, rc, why):
    dest = tmp_path / "cli.tgz"
    _curl_writes(monkeypatch, body, rc=rc, stderr="curl: (22) The requested URL returned error: 503")
    with pytest.raises(db2.OdbcDownloadError) as err:
        db2.fetch_odbc_cli(dest, _pin())
    message = str(err.value)
    assert message.startswith("INFRASTRUCTURE (not a code defect)")
    assert "example.invalid" in message
    assert why in message
    assert not dest.exists()
    assert not list(tmp_path.glob("*.part"))


def test_curl_missing_or_hanging_is_infrastructure_too(tmp_path, monkeypatch):
    def gone(cmd, **kwargs):
        raise FileNotFoundError("curl")

    monkeypatch.setattr(db2.subprocess, "run", gone)
    with pytest.raises(db2.OdbcDownloadError, match="INFRASTRUCTURE"):
        db2.fetch_odbc_cli(tmp_path / "cli.tgz", _pin())

    def slow(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 1000)

    monkeypatch.setattr(db2.subprocess, "run", slow)
    with pytest.raises(db2.OdbcDownloadError, match="INFRASTRUCTURE"):
        db2.fetch_odbc_cli(tmp_path / "cli.tgz", _pin())


# --- #5048: the siblings of #4980 (apt in the Dockerfiles, the Db2 image pull) ---------------------------------------


@pytest.mark.parametrize("name", ["gnucobol.Dockerfile", "gnucobol-db2.Dockerfile"])
def test_dockerfile_apt_retries_and_no_failure_is_swallowed(name):
    text = (REPO / "tests" / "equivalence" / name).read_text(encoding="utf-8")
    body = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    assert not any("|| true" in ln for ln in body), "a failed install must fail the build"
    for ln in body:
        for m in re.finditer(r"apt-get(?P<opts>[^&|;]*)", ln):
            if re.search(r"\b(update|install)\b", m.group("opts")):
                assert "Acquire::Retries=" in m.group("opts"), ln


def test_the_db2_image_installs_nothing_because_the_base_image_supplies_libxml2():
    """#5048: the db2 Dockerfile dropped its `apt-get install libxml2 || true`; the driver's libxml2 comes from libcob4."""
    root = REPO / "tests" / "equivalence"
    db2_body = [
        ln
        for ln in (root / "gnucobol-db2.Dockerfile").read_text(encoding="utf-8").splitlines()
        if not ln.lstrip().startswith("#")
    ]
    assert not any("apt-get" in ln for ln in db2_body), "a new apt step needs Acquire::Retries and no `|| true`"
    base = (root / "gnucobol.Dockerfile").read_text(encoding="utf-8")
    assert "libcob4=" in base, "libcob4 is what puts libxml2 in the base image for the Db2 driver"


def _docker_script(monkeypatch, present: bool, failures: int, exc=None):
    """Fake `docker`: `image inspect` finds the image or not; the first `failures` pulls fail."""
    calls, sleeps = [], []

    def run(cmd, **kwargs):
        calls.append(cmd[1:])
        if cmd[1:3] == ["image", "inspect"]:
            return subprocess.CompletedProcess(cmd, 0 if present else 1, "sha256:abc\n" if present else "", "")
        if cmd[1] == "pull":
            if exc is not None:
                raise exc
            n = sum(1 for c in calls if c[0] == "pull")
            if n <= failures:
                return subprocess.CompletedProcess(cmd, 1, "", "net/http: TLS handshake timeout")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(db2.subprocess, "run", run)
    monkeypatch.setattr(db2.time, "sleep", sleeps.append)
    return calls, sleeps


def _pulls(calls):
    return [c for c in calls if c[0] == "pull"]


def test_the_pull_keeps_the_digest_pin():
    assert db2.pinned_by_digest(db2.IMAGE)


def test_an_image_already_on_the_host_is_not_pulled(monkeypatch):
    calls, _ = _docker_script(monkeypatch, present=True, failures=0)
    db2.pull_image()
    assert not _pulls(calls)


def test_a_pull_is_one_call_with_the_pinned_digest(monkeypatch):
    calls, sleeps = _docker_script(monkeypatch, present=False, failures=0)
    db2.pull_image()
    assert [c[-1] for c in _pulls(calls)] == [db2.IMAGE]
    assert not sleeps


def test_a_pull_that_fails_then_succeeds_is_retried_with_growing_backoff(monkeypatch):
    calls, sleeps = _docker_script(monkeypatch, present=False, failures=2)
    db2.pull_image()
    assert len(_pulls(calls)) == 3
    assert sleeps == [db2.PULL_BACKOFF, db2.PULL_BACKOFF * 2]


def test_a_pull_that_never_works_stops_at_the_bound_and_says_infrastructure(monkeypatch):
    calls, sleeps = _docker_script(monkeypatch, present=False, failures=99)
    with pytest.raises(db2.Db2ImagePullError, match="INFRASTRUCTURE") as err:
        db2.pull_image()
    assert len(_pulls(calls)) == db2.PULL_ATTEMPTS
    assert len(sleeps) == db2.PULL_ATTEMPTS - 1
    assert db2.IMAGE in str(err.value) and "TLS handshake timeout" in str(err.value)


@pytest.mark.parametrize("exc", [FileNotFoundError("docker"), subprocess.TimeoutExpired("docker", 1800)])
def test_docker_missing_or_hanging_is_infrastructure_too(monkeypatch, exc):
    _docker_script(monkeypatch, present=False, failures=0, exc=exc)
    with pytest.raises(db2.Db2ImagePullError, match="INFRASTRUCTURE"):
        db2.pull_image()


# --- #5094: the sweep's parallel jobs share one fetch --------------------------------------------------------------


@pytest.mark.skipif(
    sys.platform == "win32", reason="the fetch lock is a no-op without fcntl (the Db2 sweep is Linux-only)"
)
def test_concurrent_fetches_download_once_and_all_succeed(tmp_path, monkeypatch):
    """#5094: four --jobs processes starting on a fresh runner each fetched into the same `.part` and deleted each
    other's file ("sha256 no file"). One fetch runs at a time; the rest find the verified file."""
    import threading
    import time

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    dest = tmp_path / "cli.tgz"
    calls, errors = [], []

    def run(cmd, **kwargs):
        calls.append(cmd)
        part = Path(cmd[cmd.index("--output") + 1])
        part.write_bytes(PAYLOAD[:3])
        time.sleep(0.2)  # a slow download: the window the other jobs used to unlink the part in
        part.write_bytes(PAYLOAD)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(db2.subprocess, "run", run)

    def job():
        try:
            assert db2.fetch_odbc_cli(dest, _pin()) == dest
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=job) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert len(calls) == 1
    assert dest.read_bytes() == PAYLOAD
    assert not list(tmp_path.glob("*.part"))
