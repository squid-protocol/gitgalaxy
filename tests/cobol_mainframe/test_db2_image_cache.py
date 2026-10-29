"""#5262: the pinned Db2 image is restored from actions/cache (key = its digest) instead of pulled from icr.io in every
shard; main alone saves; a miss or a mismatch falls back to the retried pull."""

import re
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import db2_image_cache as cache  # noqa: E402
import equivalence_db2 as db2  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
WORKFLOWS = ["det-sweep.yml", "evidence-refresh.yml"]
IDENT = "sha256:" + "a" * 64


def test_the_cache_key_is_the_pinned_digest():
    assert cache.IMAGE == db2.IMAGE
    assert cache.key() == "db2-image-" + db2.IMAGE.rsplit(":", 1)[1]
    assert cache.ALIAS == db2.IMAGE_ALIAS


@pytest.mark.parametrize("workflow", WORKFLOWS)
def test_a_workflow_restores_everywhere_and_saves_from_main_only(workflow):
    text = (REPO / ".github" / "workflows" / workflow).read_text(encoding="utf-8")
    assert "db2_image_cache.py key" in text
    assert re.search(
        r"actions/cache/restore@\w+.*\n\s+with:\n\s+path: \$\{\{ runner\.temp \}\}/db2-image-cache\n\s+key: \$\{\{ steps\.db2key",
        text,
    )
    save = re.search(r"actions/cache/save@\w+[^\n]*\n\s+with:\n\s+path: \$\{\{ runner\.temp \}\}/db2-image-cache", text)
    assert save, "the cache entry is stored with actions/cache/save"
    guard = text[: save.start()].rsplit("- name:", 1)[1]
    assert "github.event_name != 'pull_request'" in guard and "github.ref == 'refs/heads/main'" in guard
    assert "cache-hit != 'true'" in guard
    assert "ci_retry.sh 4 15 -- docker pull" in text, "a miss keeps the retried, digest-pinned pull"


def _fake_docker(monkeypatch, tmp_path, present=(), loaded_id=IDENT, load_rc=0):
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        if cmd[:3] == ["docker", "image", "inspect"]:
            return subprocess.CompletedProcess(
                cmd, 0 if cmd[-1] in present else 1, IDENT + "\n" if cmd[-1] in present else "", ""
            )
        if cmd[:2] == ["docker", "load"]:
            return subprocess.CompletedProcess(cmd, load_rc, f"Loaded image ID: {loaded_id}\n".encode(), b"")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    class Zstd:
        stdout = open(tmp_path / "dev", "wb")  # noqa: SIM115

        def wait(self):
            return 0

    monkeypatch.setattr(cache.subprocess, "run", run)
    monkeypatch.setattr(cache.subprocess, "Popen", lambda *a, **k: Zstd())
    return calls


def _entry(d):
    d.mkdir()
    (d / cache.TAR).write_bytes(b"x")
    (d / cache.IDFILE).write_text(IDENT + "\n")


def test_a_hit_loads_verifies_and_tags_the_alias(tmp_path, monkeypatch):
    _entry(tmp_path / "c")
    present = set()
    calls = _fake_docker(monkeypatch, tmp_path)
    # after the load the id resolves
    orig = cache.subprocess.run

    def run(cmd, **kw):
        if cmd[:2] == ["docker", "load"]:
            present.add(IDENT)
        return orig(cmd, **kw)

    monkeypatch.setattr(cache.subprocess, "run", run)
    monkeypatch.setattr(cache, "_image_id", lambda ref: IDENT if ref in present else "")
    assert cache.load(tmp_path / "c") is True
    assert ["docker", "tag", IDENT, cache.ALIAS] in calls
    assert not any(c[:2] == ["docker", "pull"] for c in calls)


def test_a_miss_is_reported_so_the_caller_pulls(tmp_path, monkeypatch):
    _fake_docker(monkeypatch, tmp_path)
    monkeypatch.setattr(cache, "_image_id", lambda ref: "")
    assert cache.load(tmp_path / "empty") is False


def test_a_loaded_image_with_another_id_is_refused(tmp_path, monkeypatch):
    _entry(tmp_path / "c")
    calls = _fake_docker(monkeypatch, tmp_path, loaded_id="sha256:" + "b" * 64)
    monkeypatch.setattr(cache, "_image_id", lambda ref: "")
    assert cache.load(tmp_path / "c") is False
    assert not any(c[:2] == ["docker", "tag"] for c in calls)


def test_an_image_already_on_the_host_needs_no_cache(tmp_path, monkeypatch):
    calls = _fake_docker(monkeypatch, tmp_path)
    monkeypatch.setattr(cache, "_image_id", lambda ref: IDENT if ref == cache.IMAGE else "")
    assert cache.load(tmp_path / "none") is True
    assert not any(c[:2] == ["docker", "load"] for c in calls)


def test_save_refuses_when_the_pinned_image_is_not_there(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "_image_id", lambda ref: "")
    assert cache.save(tmp_path / "out") is False
    assert not (tmp_path / "out" / cache.IDFILE).exists()


def test_the_harness_runs_from_the_alias_when_only_the_alias_is_loaded(monkeypatch):
    seen = []

    def docker(*args, check=True, **kw):
        seen.append(args)
        return IDENT if args[-1] == db2.IMAGE_ALIAS else ""

    monkeypatch.setattr(db2, "_docker", docker)
    assert db2.run_ref() == db2.IMAGE_ALIAS
    db2.pull_image()  # the alias counts as present: no pull
    assert not any(a[0] == "pull" for a in seen)


def test_the_harness_prefers_the_digest_name(monkeypatch):
    monkeypatch.setattr(db2, "_docker", lambda *a, **k: IDENT)
    assert db2.run_ref() == db2.IMAGE


def test_a_start_waits_for_the_background_image_load_before_pulling(monkeypatch, tmp_path):
    """#5601: the cache load was still running when the harness looked, so it pulled icr.io and failed on a blip."""
    (tmp_path / "pull.log").write_text("", encoding="utf-8")
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    seen = []

    def docker(*args, **kwargs):
        seen.append(args)
        return ""

    def sleep(_seconds):
        (tmp_path / "pull-done").write_text("1", encoding="utf-8")  # the load ends while we wait
        monkeypatch.setattr(db2, "_docker", lambda *a, **k: IDENT)  # and the image is there

    monkeypatch.setattr(db2, "_docker", docker)
    monkeypatch.setattr(db2.time, "sleep", sleep)
    db2.pull_image()
    assert not any(a[0] == "pull" for a in seen)


def test_no_wait_outside_ci_or_without_a_background_load(monkeypatch, tmp_path):
    monkeypatch.setattr(db2.time, "sleep", lambda _s: pytest.fail("must not wait"))
    monkeypatch.delenv("RUNNER_TEMP", raising=False)
    db2._await_background_load()
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))  # no pull.log: nothing was started
    db2._await_background_load()


def test_every_workflow_that_loads_the_image_in_the_background_marks_its_end():
    """The harness waits for `pull-done` (up to LOAD_WAIT) once `pull.log` exists: a workflow that starts the background
    load without writing the marker made every pull_image call wait the whole 900 s (equivalence-e2e.yml's db2 job)."""
    starters = []
    for path in sorted((REPO / ".github" / "workflows").glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        if "/pull.log" in text and "db2_image_cache.py load" in text:
            starters.append(path.name)
            assert re.search(r"docker pull[^\n]*; date \+%s > '\$RUNNER_TEMP/pull-done'", text), path.name
    assert {"det-sweep.yml", "equivalence-e2e.yml"} <= set(starters)


@pytest.mark.parametrize("job", ["shard", "db2"])
def test_every_equivalence_e2e_job_that_can_start_db2_restores_the_image_and_loads_it_in_the_background(job):
    """#7002: a shard's cbsa-updacc proof pulled the image cold from icr.io and failed on a registry timeout."""
    text = (REPO / ".github" / "workflows" / "equivalence-e2e.yml").read_text(encoding="utf-8")
    body = re.split(rf"^  {job}:\n", text, flags=re.M)[1]
    body = re.split(r"^  [a-z0-9-]+:\n", body, flags=re.M)[0]
    assert "db2_image_cache.py key" in body
    assert re.search(
        r"actions/cache/restore@\w+.*\n\s+with:\n\s+path: \$\{\{ runner\.temp \}\}/db2-image-cache\n\s+key: \$\{\{ steps\.db2key",
        body,
    )
    start = re.search(r"db2_image_cache\.py load[^\n]*docker pull[^\n]*; date \+%s > '\$RUNNER_TEMP/pull-done'", body)
    assert start, "the background load ends with the pull-done marker"
    assert start.start() < body.index("Install dependencies"), "the load overlaps the installs"
