"""#3213: the pinned mainframe corpus manifest and tests/tools/mainframe_corpus.py.

The network is never touched: fetch is exercised against a local repository.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import mainframe_corpus as mc  # noqa: E402

CORPORA = mc.load_manifest()


def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()  # noqa: S603, S607


def test_manifest_shape():
    names = [c["name"] for c in CORPORA]
    assert len(names) == len(set(names))
    for c in CORPORA:
        assert re.fullmatch(r"[0-9a-f]{40}", c["ref"]), c["name"]
        assert c["url"].startswith("https://github.com/"), c["name"]
        assert c["license"] and c["languages"] and c["branch"], c["name"]
        assert c["excerpt"]["files"] and c["excerpt"]["why"], c["name"]


def test_bms_corpus_is_pinned():
    """#3122's BMS row needed real maps; CBSA and CardDemo carry them."""
    assert {"cics-banking-sample-application-cbsa", "aws-mainframe-modernization-carddemo"} <= {
        c["name"] for c in CORPORA if "bms" in c["languages"]
    }


@pytest.mark.parametrize("corpus", [c for c in CORPORA if c["answer_key"]], ids=lambda c: c["name"])
def test_answer_key_matches_the_pin(corpus):
    key = json.loads((mc.REPO_ROOT / corpus["answer_key"]).read_text(encoding="utf-8"))
    assert (key["corpus"], key["url"], key["ref"]) == (corpus["name"], corpus["url"], corpus["ref"])


@pytest.mark.parametrize("corpus", CORPORA, ids=lambda c: c["name"])
def test_committed_excerpt_matches_the_manifest(corpus):
    """The excerpt directory holds exactly the listed files (plus the license and
    provenance files), copied at the pinned ref."""
    root = mc.EXCERPTS / corpus["name"]
    present = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    legal = {p for p in present if "/" not in p and p.upper().startswith(("LICENSE", "NOTICE"))}
    assert legal, f"{corpus['name']}: no LICENSE/NOTICE copied"
    assert present - legal - {mc.PROVENANCE} == set(corpus["excerpt"]["files"])
    assert corpus["ref"] in (root / mc.PROVENANCE).read_text(encoding="utf-8")


@pytest.mark.parametrize("corpus", CORPORA, ids=lambda c: c["name"])
def test_committed_excerpt_is_byte_identical_to_the_clone(corpus):
    """Local only: skipped unless the corpus is fetched at its pin."""
    clone = mc.clone_path(corpus)
    if not (clone / ".git").exists() or _git("rev-parse", "HEAD", cwd=clone) != corpus["ref"]:
        pytest.skip(f"{corpus['name']} not fetched (mainframe_corpus.py fetch)")
    for rel in corpus["excerpt"]["files"]:
        assert (mc.EXCERPTS / corpus["name"] / rel).read_bytes() == (clone / rel).read_bytes(), rel


@pytest.fixture
def upstream(tmp_path):
    """A local repository with two commits, served over file:// so --depth applies."""
    repo = tmp_path / "upstream"
    repo.mkdir()
    _git("init", "-q", cwd=repo)
    _git("config", "uploadpack.allowAnySHA1InWant", "true", cwd=repo)
    for i in (1, 2):
        (repo / "PROG.cbl").write_text(f"       PROGRAM-ID. PROG{i}.\n", encoding="utf-8")
        _git("add", "PROG.cbl", cwd=repo)
        _git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", f"c{i}", cwd=repo)
    first = _git("rev-list", "--max-parents=0", "HEAD", cwd=repo)
    return {"name": "demo", "url": repo.as_uri(), "ref": first, "excerpt": {"files": ["PROG.cbl"], "why": "w"}}


def test_fetch_pins_an_older_commit_and_is_idempotent(upstream, tmp_path, monkeypatch):
    monkeypatch.setenv(mc.CACHE_ENV, str(tmp_path / "cache"))
    clone = mc.fetch(upstream)
    assert clone == tmp_path / "cache" / "demo"
    assert _git("rev-parse", "HEAD", cwd=clone) == upstream["ref"]
    assert "PROG1" in (clone / "PROG.cbl").read_text(encoding="utf-8")
    assert mc.fetch(upstream) == clone
    assert mc.require_clone(upstream) == clone


def test_fetch_refuses_to_discard_local_edits(upstream, tmp_path, monkeypatch):
    monkeypatch.setenv(mc.CACHE_ENV, str(tmp_path / "cache"))
    clone = mc.fetch(upstream)
    (clone / "PROG.cbl").write_text("edited\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        mc.fetch(upstream)
    mc.fetch(upstream, force=True)
    assert "PROG1" in (clone / "PROG.cbl").read_text(encoding="utf-8")


def test_require_clone_names_the_fetch_command(upstream, tmp_path, monkeypatch):
    monkeypatch.setenv(mc.CACHE_ENV, str(tmp_path / "cache"))
    with pytest.raises(SystemExit, match="mainframe_corpus.py fetch demo"):
        mc.require_clone(upstream)


def test_scan_cache_is_keyed_by_ref_and_engine(upstream, tmp_path, monkeypatch):
    monkeypatch.setenv(mc.CACHE_ENV, str(tmp_path / "cache"))
    a = mc.db_path(upstream, engine="aaaa")
    assert a.name == "demo_galaxy_master.db"
    assert a.parent.name == f"{upstream['ref'][:12]}-aaaa"
    assert mc.db_path(upstream, engine="bbbb") != a


def test_excerpt_copies_files_license_and_provenance(upstream, tmp_path, monkeypatch):
    monkeypatch.setenv(mc.CACHE_ENV, str(tmp_path / "cache"))
    clone = mc.fetch(upstream)
    (clone / "LICENSE").write_text("license\n", encoding="utf-8")
    dest = mc.excerpt({**upstream, "url": "https://example.invalid/demo", "license": "X"}, dest_root=tmp_path / "ex")
    assert sorted(p.name for p in dest.iterdir()) == ["LICENSE", "PROG.cbl", mc.PROVENANCE]
    assert upstream["ref"] in (dest / mc.PROVENANCE).read_text(encoding="utf-8")


def test_unsafe_path_parts_flags_ignored_directory_names(tmp_path):
    assert mc.unsafe_path_parts(Path("/srv/tmp/corpora")) == ["tmp"]
    assert mc.unsafe_path_parts(Path("/srv/corpora")) == []


def test_select_rejects_unknown_names():
    with pytest.raises(SystemExit, match="unknown corpus"):
        mc.select(["no-such-corpus"])
