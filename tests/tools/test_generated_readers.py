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
