"""#4963: the readers of moved generated output (evidence report, estate intake, the nightly blockers) go through
generated_branch -- the published copy first, the committed copy as the fallback -- against a local bare remote."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cics_census as cc
import estate_intake as ei
import evidence_report as er
import generated_branch as gb

REPORT = "docs/language_status/evidence_report/est/report.json"
BLOCKERS = f"{cc.GENERATED_DIR}/blockers.json"


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def clone(tmp_path, monkeypatch):
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    c = tmp_path / "clone"
    git(tmp_path, "clone", "-q", str(remote), str(c))
    git(c, "config", "user.email", "t@t")
    git(c, "config", "user.name", "t")
    (c / REPORT).parent.mkdir(parents=True)
    (c / REPORT).write_text(json.dumps({"v": "committed"}))
    git(c, "add", ".")
    git(c, "commit", "-q", "-m", "seed")
    git(c, "push", "-q", "origin", "HEAD:main")
    monkeypatch.setattr(er, "REPO", c)
    monkeypatch.setattr(cc, "REPO", c)
    monkeypatch.setattr(ei, "ROOT", c)
    return c


def publish(c, rel, text):
    (c / rel).parent.mkdir(parents=True, exist_ok=True)
    (c / rel).write_text(text)
    gb.publish([rel], "m", root=c)
    git(c, "checkout", "-q", "--", ".")  # the working tree goes back to the committed copy (or stays untracked)


def test_report_reads_published_over_committed_and_falls_back(clone):
    p = clone / REPORT
    assert er.current_texts([p]) == {p: json.dumps({"v": "committed"})}  # no generated branch yet
    publish(clone, REPORT, json.dumps({"v": "published"}))
    assert er.current_texts([p]) == {p: json.dumps({"v": "published"})}
    gone = clone / "docs/language_status/evidence_report/new/report.json"  # on neither side
    assert er.current_texts([gone]) == {gone: None}


def test_report_reads_committed_without_an_origin(clone):
    git(clone, "remote", "remove", "origin")
    p = clone / REPORT
    assert er.current_texts([p]) == {p: json.dumps({"v": "committed"})}


def test_estate_intake_reads_the_published_report(clone):
    p = clone / REPORT
    assert ei._read_report(p, published=True) == {"v": "committed"}
    publish(clone, REPORT, json.dumps({"v": "published"}))
    assert ei._read_report(p, published=True) == {"v": "published"}
    assert ei._read_report(p) == {"v": "committed"}  # an explicit --report path is read as given
    assert ei._read_report(clone / "nope.json", published=True) is None


def test_census_read_generated_uses_the_shared_reader(clone):
    with pytest.raises(SystemExit, match="not published"):  # no branch yet: there is no committed fallback
        cc.read_generated(BLOCKERS)
    publish(clone, BLOCKERS, '{"gaps": []}')
    assert json.loads(cc.read_generated(BLOCKERS)) == {"gaps": []}
    with pytest.raises(SystemExit, match="not published"):  # a branch that lacks the file
        cc.read_generated(f"{cc.GENERATED_DIR}/meta.json")


@pytest.fixture
def out_dir(clone, monkeypatch):
    out = clone / "docs/language_status/evidence_report"
    monkeypatch.setattr(er, "OUT", out)
    monkeypatch.setattr(er, "DOCS_OUT", out)
    return out


def test_materialize_copies_the_published_report_and_keeps_the_stub(clone, out_dir):
    """#5206: main commits no report, so the tools that read it fetch the published copy into the ignored directory."""
    base = "docs/language_status/evidence_report"
    for rel, text in (("est/report.json", "{}"), ("est/report.md", "# est"), ("README.md", "published index")):
        (clone / base / rel).parent.mkdir(parents=True, exist_ok=True)
        (clone / base / rel).write_text(text)
    gb.publish([base], "m", root=clone)
    (clone / REPORT).unlink()
    (out_dir / "README.md").write_text("stub")
    assert er.materialize(clone) == 2
    assert (out_dir / "est/report.json").read_text() == "{}"
    assert (out_dir / "README.md").read_text() == "stub"  # the index is not copied over the committed stub


def test_materialize_fails_when_there_is_no_report_anywhere(clone, out_dir):
    (clone / REPORT).unlink()
    with pytest.raises(SystemExit, match="no evidence report"):  # no generated branch yet
        er.materialize(clone)
    git(clone, "remote", "remove", "origin")  # no origin at all
    with pytest.raises(SystemExit, match="no evidence report"):
        er.materialize(clone)


def test_materialize_keeps_what_is_on_disk_when_the_branch_is_unreachable(clone, out_dir):
    git(clone, "remote", "remove", "origin")
    assert er.materialize(clone) == 0  # est/report.json is on disk


def test_materialize_leaves_a_foreign_out_directory_alone(clone, tmp_path, monkeypatch):
    monkeypatch.setattr(er, "OUT", tmp_path)
    assert er.materialize(clone) == 0


def _flaky_git(monkeypatch, failures):
    """gb._git failing `failures` times on the network calls, then delegating; returns the call log."""
    real, calls = gb._git, []

    def flaky(root, *args, **kw):
        if args[0] in ("ls-remote", "fetch"):
            calls.append(args[0])
            if calls.count(args[0]) <= failures:
                raise RuntimeError("git " + args[0] + " failed (128): connection reset")
        return real(root, *args, **kw)

    monkeypatch.setattr(gb, "_git", flaky)
    monkeypatch.setattr(gb, "RETRY_DELAYS", (0, 0))
    return calls


def test_fetch_tip_retries_a_transient_network_failure(clone, monkeypatch):
    """#5312: one dropped connection on a runner must not read as 'no evidence report'."""
    (clone / REPORT).write_text("{}")
    gb.publish([REPORT], "m", root=clone)
    calls = _flaky_git(monkeypatch, 2)
    assert gb.fetch_tip(clone)
    assert calls.count("ls-remote") == 3 and calls.count("fetch") == 3


def test_fetch_tip_gives_up_after_the_retries(clone, monkeypatch):
    calls = _flaky_git(monkeypatch, 99)
    with pytest.raises(RuntimeError, match="connection reset"):
        gb.fetch_tip(clone)
    assert calls == ["ls-remote"] * 3


def test_fetch_tip_does_not_retry_a_missing_branch(clone, monkeypatch):
    calls = _flaky_git(monkeypatch, 0)
    assert gb.fetch_tip(clone) is None
    assert calls == ["ls-remote"]
