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


# ---- #6072: cics-crucible resolves as a ladder corpus without joining the manifest -------------------------------
def _crucible_repo(tmp_path, monkeypatch, tag_at_head=True):
    repo = tmp_path / "cics-crucible"
    repo.mkdir()
    _git("init", "-q", cwd=repo)
    _git("-c", "user.email=a@b", "-c", "user.name=n", "commit", "-q", "--allow-empty", "-m", "x", cwd=repo)
    entry = mc.select(["cics-crucible"])[0]
    if tag_at_head:
        _git("tag", entry["ref"], cwd=repo)
    else:
        _git("-c", "user.email=a@b", "-c", "user.name=n", "commit", "-q", "--allow-empty", "-m", "y", cwd=repo)
        _git("tag", entry["ref"], "HEAD~1", cwd=repo)
    monkeypatch.setenv(mc.CRUCIBLE_PATH_ENV, str(repo))
    monkeypatch.delenv(mc.CRUCIBLE_UNPINNED_ENV, raising=False)
    return repo, entry


def test_crucible_is_selectable_but_not_in_the_manifest():
    (entry,) = mc.select(["cics-crucible"])
    from _cics_crucible_pin import PINNED_REF

    assert entry["ref"] == PINNED_REF and entry["crucible"] == "cics"
    assert "cics-crucible" not in {c["name"] for c in mc.select([])}
    assert mc.select([]) == CORPORA


def test_crucible_require_clone_at_the_pin(tmp_path, monkeypatch):
    repo, entry = _crucible_repo(tmp_path, monkeypatch)
    assert mc.require_clone(entry) == repo
    assert mc.clone_path(entry) == repo


def test_crucible_off_the_pin_is_refused_unless_unpinned(tmp_path, monkeypatch):
    repo, entry = _crucible_repo(tmp_path, monkeypatch, tag_at_head=False)
    with pytest.raises(SystemExit, match="sync-pins"):
        mc.require_clone(entry)
    monkeypatch.setenv(mc.CRUCIBLE_UNPINNED_ENV, "1")
    assert mc.require_clone(entry) == repo


def test_crucible_missing_checkout_is_refused(tmp_path, monkeypatch):
    (entry,) = mc.select(["cics-crucible"])
    monkeypatch.setenv(mc.CRUCIBLE_PATH_ENV, str(tmp_path / "absent"))
    with pytest.raises(SystemExit, match="no checkout"):
        mc.require_clone(entry)


def test_bare_fetch_takes_the_crucible_and_a_named_fetch_does_not():
    bare = mc.fetch_targets([])
    assert bare[: len(CORPORA)] == CORPORA and [c["name"] for c in bare[len(CORPORA) :]] == ["cics-crucible"]
    assert mc.fetch_targets([CORPORA[0]["name"]]) == [CORPORA[0]]


@pytest.mark.parametrize("by_sha", [False, True], ids=["tag", "sha"])
def test_fetch_clones_an_absent_crucible_at_the_pin(tmp_path, monkeypatch, by_sha):
    upstream, entry = _crucible_repo(tmp_path, monkeypatch)
    entry["url"] = upstream.as_uri()
    if by_sha:
        entry["ref"] = _git("rev-parse", "HEAD", cwd=upstream)
    dest = tmp_path / "ci" / "cics-crucible"
    monkeypatch.setenv(mc.CRUCIBLE_PATH_ENV, str(dest))
    assert mc.fetch(entry) == dest
    assert mc.require_clone(entry) == dest  # the tag is kept, so the pin check resolves it
    assert mc.fetch(entry) == dest  # a second fetch (ports-compile cloned first) is a no-op


def test_fetch_retries_a_crucible_clone_that_died_before_a_checkout(tmp_path, monkeypatch):
    upstream, entry = _crucible_repo(tmp_path, monkeypatch)
    entry["url"] = upstream.as_uri()
    dest = tmp_path / "cics-crucible-retry"
    dest.mkdir()
    _git("init", "-q", cwd=dest)
    monkeypatch.setenv(mc.CRUCIBLE_PATH_ENV, str(dest))
    mc.fetch(entry)
    assert mc.require_clone(entry) == dest


def test_fetch_leaves_an_existing_crucible_to_sync_pins(tmp_path, monkeypatch):
    repo, entry = _crucible_repo(tmp_path, monkeypatch, tag_at_head=False)
    entry["url"] = "file:///nowhere"  # a fetch would fail: it must not try
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout
    assert mc.fetch(entry) == repo
    assert subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout == head


def test_unknown_corpus_still_lists_the_manifest():
    with pytest.raises(SystemExit, match="zecs"):
        mc.select(["cics-crucible", "nope"])
