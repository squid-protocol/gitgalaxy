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
