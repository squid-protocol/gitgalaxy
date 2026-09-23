"""
Split golden-master layout (#3384): round-trip, determinism, strictness, and
the property the split exists for -- two PRs that each add a different key
touch disjoint files and merge without conflicts.
"""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import golden_diff as gd
import golden_store as gs

REPO_ROOT = Path(__file__).resolve().parent.parent
PF = gs.PARSED_FILES_KEY


def _sample() -> dict:
    """A miniature of the real audit shape, including the awkward cases: a
    per-file section that is a string for some files and a dict for others,
    an empty-dict value, a file entry with no sections, lists, non-ASCII,
    floats that must round-trip exactly, and two keys whose slugs collide."""
    return {
        "Audit Protocol": "GitGalaxy-Audit",
        "1. Forensic Trail (Traceability)": {
            "Analysis Context": {"Engine Identity": "x", "Missing Dependencies": {"numpy": False}},
            "Source Control Footprint (Immutable Anchor)": {},
        },
        "2. Global Ecosystem Summary": {
            "summary": {"total_files": 3, "Percent_Visible": 90.4},
            "typosquat_hits": 17,
            "I/O Routines": 1,
            "I-O Routines": 2,  # slug collides with the key above
        },
        "5. Unparsable Artifacts (Excluded Artifacts Queue)": [{"Path": "a/b.bin", "Diagnostic Reason": "binary"}],
        "7. Empty Section": {},
        PF: {
            "cobol/app": {
                "Directory Group Magnitude": 12.5,
                "File Count": 2,
                "Files": {
                    "cobol/app/PAY.cbl": {
                        "1. Artifact Identity": {"Language": "cobol", "Path": "cobol/app/PAY.cbl"},
                        "2. Topological Coordinates": {"X": 0.1 + 0.2, "Y": -1e-9, "Z": 3.0},
                        "5. Function Analysis": [{"name": "MAIN", "complexity": 4}],
                        "6. Contextual Mitigations & Amplifications": {"Mitigated Danger": "yes"},
                        "10. Mainframe System Facts": {"Call Sites": [{"target": "SUBR"}]},
                    },
                    "cobol/app/EMPTY.cpy": {},
                },
            },
            "python/tool": {
                "Directory Group Magnitude": 1.0,
                "File Count": 1,
                "Files": {
                    "python/tool/über.py": {
                        "1. Artifact Identity": {"Language": "python", "Path": "python/tool/über.py"},
                        "2. Topological Coordinates": {"X": 1.0, "Y": 2.0, "Z": 3.0},
                        "5. Function Analysis": [],
                        "6. Contextual Mitigations & Amplifications": "None",
                        "8. Dependency Network": {},
                    }
                },
            },
        },
    }


def _parts(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


# --------------------------------------------------------------------------
# round-trip + determinism
# --------------------------------------------------------------------------


def test_round_trip_is_exact(tmp_path):
    data = _sample()
    gs.write(data, tmp_path / "gm")
    back = gs.load(tmp_path / "gm")
    assert back == data
    assert gd.generate_deterministic_hash(back) == gd.generate_deterministic_hash(data)
    assert gd.deep_compare(data, back) == []
    # the float survives bit-for-bit, not just within golden_diff's tolerance
    xs = back[PF]["cobol/app"]["Files"]["cobol/app/PAY.cbl"]["2. Topological Coordinates"]["X"]
    assert xs == 0.1 + 0.2


def test_rewrite_is_byte_stable_and_order_independent(tmp_path):
    data = _sample()
    gs.write(data, tmp_path / "a")
    gs.write(gs.load(tmp_path / "a"), tmp_path / "a")  # re-bless of unchanged output
    reordered = json.loads(json.dumps(data), object_pairs_hook=lambda kv: dict(reversed(kv)))
    gs.write(reordered, tmp_path / "b")
    assert _parts(tmp_path / "a") == _parts(tmp_path / "b")
    assert gs.check_canonical(tmp_path / "a") == []
    for rel, blob in _parts(tmp_path / "a").items():
        assert blob.endswith(b"\n") and not blob.endswith(b"\n\n"), rel
        assert "/" not in rel.split("/")[-1] and rel.endswith(".json")


def test_write_removes_stale_parts(tmp_path):
    data = _sample()
    gs.write(data, tmp_path / "gm")
    del data["2. Global Ecosystem Summary"]["typosquat_hits"]
    gs.write(data, tmp_path / "gm")
    assert gs.load(tmp_path / "gm") == data
    assert not any("typosquat" in rel for rel in _parts(tmp_path / "gm"))


def test_plain_json_files_still_load(tmp_path):
    """A fresh scan's data_galaxy_audit.json is a plain file -- load() and
    golden_diff.load_and_sanitize() read it exactly as before."""
    f = tmp_path / "data_galaxy_audit.json"
    f.write_text(json.dumps(_sample()), encoding="utf-8")
    assert gs.load(f) == _sample()


def test_colliding_slugs_get_distinct_files(tmp_path):
    gs.write(_sample(), tmp_path / "gm")
    names = [r for r in _parts(tmp_path / "gm") if r.startswith("2_global_ecosystem_summary/i_o_routines")]
    assert len(names) == 2


# --------------------------------------------------------------------------
# strictness: malformed directories fail loudly
# --------------------------------------------------------------------------


@pytest.fixture
def written(tmp_path):
    root = tmp_path / "gm"
    gs.write(_sample(), root)
    return root


def test_missing_layout_marker_fails(written):
    (written / gs.LAYOUT_FILE).unlink()
    with pytest.raises(gs.GoldenStoreError, match="_layout"):
        gs.load(written)


def test_stray_file_fails(written):
    (written / "notes.txt").write_text("hi", encoding="utf-8")
    with pytest.raises(gs.GoldenStoreError, match="stray"):
        gs.load(written)


def test_extra_section_file_in_wrong_place_fails(written):
    src = written / "2_global_ecosystem_summary" / "summary.json"
    src.rename(written / "2_global_ecosystem_summary" / "renamed.json")
    with pytest.raises(gs.GoldenStoreError, match="canonical layout"):
        gs.load(written)


def test_duplicate_logical_path_fails(written):
    src = written / "2_global_ecosystem_summary" / "summary.json"
    (written / "2_global_ecosystem_summary" / "summary_copy.json").write_bytes(src.read_bytes())
    with pytest.raises(gs.GoldenStoreError, match="duplicate"):
        gs.load(written)


def test_orphan_per_file_value_fails(written):
    col = written / "6_parsed_files_scanned_artifacts" / "files" / "10_mainframe_system_facts" / "call_sites.json"
    obj = json.loads(col.read_text(encoding="utf-8"))
    obj["groups"]["cobol/app"]["cobol/app/GHOST.cbl"] = []
    col.write_text(json.dumps(obj), encoding="utf-8")
    with pytest.raises(gs.GoldenStoreError, match="GHOST"):
        gs.load(written)


def test_missing_groups_index_fails(written):
    (written / "6_parsed_files_scanned_artifacts" / gs.GROUPS_FILE).unlink()
    with pytest.raises(gs.GoldenStoreError, match="_groups"):
        gs.load(written)


def test_missing_section_file_is_reported_as_drift_not_skipped(written):
    """Deleting a section file must not pass silently: the reassembled fixture
    lacks those keys, so the crucible diff against a real scan flags them."""
    (written / "6_parsed_files_scanned_artifacts" / "files" / "10_mainframe_system_facts" / "call_sites.json").unlink()
    diffs = gd.deep_compare(gs.load(written), _sample())
    assert diffs and all("10. Mainframe System Facts" in d for d in diffs)


def test_invalid_json_part_fails(written):
    (written / "audit_protocol.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(gs.GoldenStoreError, match="invalid JSON"):
        gs.load(written)


# --------------------------------------------------------------------------
# the point of the split: additive keys land in disjoint files
# --------------------------------------------------------------------------


def _with_new_fact_channel(data: dict, channel: str, files: list) -> dict:
    out = copy.deepcopy(data)
    for fp in files:
        group = fp.rsplit("/", 1)[0]
        entry = out[PF][group]["Files"][fp]
        entry.setdefault("10. Mainframe System Facts", {})[channel] = [{"fact": channel}]
    return out


def _changed_parts(base: Path, other: Path) -> set:
    a, b = _parts(base), _parts(other)
    return {r for r in set(a) | set(b) if a.get(r) != b.get(r)}


@pytest.mark.parametrize(
    "mutate_a, mutate_b",
    [
        # two fact channels on the SAME files (the #3249 conflict), one of
        # them creating the section on a file that had none
        (
            lambda d: _with_new_fact_channel(d, "CICS Resources", ["cobol/app/PAY.cbl", "python/tool/über.py"]),
            lambda d: _with_new_fact_channel(d, "CSD Resources", ["cobol/app/PAY.cbl", "python/tool/über.py"]),
        ),
        # two new top-level report sections
        (lambda d: {**d, "8. Channel A Report": {"n": 1}}, lambda d: {**d, "9. Channel B Report": {"n": 2}}),
        # two new global-summary entries
        (
            lambda d: {**d, "2. Global Ecosystem Summary": {**d["2. Global Ecosystem Summary"], "a_summary": 1}},
            lambda d: {**d, "2. Global Ecosystem Summary": {**d["2. Global Ecosystem Summary"], "b_summary": 2}},
        ),
    ],
    ids=["fact-channels-same-files", "top-level-sections", "global-summary-keys"],
)
def test_two_additive_branches_touch_disjoint_files(tmp_path, mutate_a, mutate_b):
    base = _sample()
    gs.write(base, tmp_path / "base")
    gs.write(mutate_a(base), tmp_path / "a")
    gs.write(mutate_b(base), tmp_path / "b")
    changed_a = _changed_parts(tmp_path / "base", tmp_path / "a")
    changed_b = _changed_parts(tmp_path / "base", tmp_path / "b")
    assert changed_a and changed_b
    assert changed_a.isdisjoint(changed_b), changed_a & changed_b
    # and every changed path is a NEW file -- nothing existing was edited
    assert not (changed_a | changed_b) & set(_parts(tmp_path / "base"))


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True)
    assert result.returncode == 0, f"git {args} failed:\n{result.stdout}\n{result.stderr}"
    return result


def test_real_git_merge_of_two_fact_channel_branches_is_conflict_free(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    # A scratch repo has no .gitattributes; without this, Windows' default
    # autocrlf rewrites checked-out parts to CRLF and check_canonical fails.
    _git(repo, "config", "core.autocrlf", "false")
    rel = gs.FULL_PRECISION
    base = _sample()
    gs.write(base, repo / rel)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")

    files = ["cobol/app/PAY.cbl", "python/tool/über.py"]
    _git(repo, "checkout", "-q", "-b", "channel-a")
    gs.write(_with_new_fact_channel(base, "CICS Resources", files), repo / rel)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "channel A")

    _git(repo, "checkout", "-q", "-b", "channel-b", "main")
    gs.write(_with_new_fact_channel(base, "CSD Resources", files), repo / rel)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "channel B")

    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-edit", "channel-a")
    merged = subprocess.run(["git", "merge", "--no-edit", "channel-b"], cwd=repo, text=True, capture_output=True)
    assert merged.returncode == 0, merged.stdout + merged.stderr

    expected = _with_new_fact_channel(_with_new_fact_channel(base, "CICS Resources", files), "CSD Resources", files)
    assert gs.load(repo / rel) == expected
    assert gs.check_canonical(repo / rel) == []
    # and the git-rev reader sees the same thing the working tree does
    assert gs.load_from_git("HEAD", rel, repo=repo) == expected
    assert gs.load_from_git("HEAD~2", rel, repo=repo) in (
        _with_new_fact_channel(base, "CICS Resources", files),
        base,
    )


def test_load_from_git_falls_back_to_pre_split_monolith(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    # A scratch repo has no .gitattributes; without this, Windows' default
    # autocrlf rewrites checked-out parts to CRLF and check_canonical fails.
    _git(repo, "config", "core.autocrlf", "false")
    (repo / "tests").mkdir()
    (repo / f"{gs.FULL_PRECISION}.json").write_text(json.dumps(_sample()), encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "monolith")
    assert gs.load_from_git("HEAD", gs.FULL_PRECISION, repo=repo) == _sample()
    assert gs.load_from_git("HEAD", gs.ZERO_DEPENDENCY, repo=repo) is None


# --------------------------------------------------------------------------
# the committed fixtures themselves
# --------------------------------------------------------------------------


@pytest.mark.parametrize("fixture", gs.GOLDEN_MASTERS)
def test_committed_fixture_is_loadable_and_canonical(fixture):
    """Catches a hand-edit, a partial/garbled merge, or a stray/missing part in
    the committed golden masters in the default suite, not only in the
    corpus-backed crucible job."""
    root = REPO_ROOT / fixture
    assert root.is_dir(), f"{fixture} missing -- the golden masters are split directories since #3384"
    assert not (REPO_ROOT / f"{fixture}.json").exists(), "pre-#3384 monolith must not come back"
    data = gs.load(root)  # strict: stray/misplaced/duplicate/orphan parts raise
    assert data.get(PF), "per-file section missing from the reassembled fixture"
    rendered = gs.render(data)
    not_canonical = [rel for rel, blob in rendered.items() if (root / rel).read_bytes() != blob]
    assert not_canonical == [], "regenerate with `python tests/tools/crucible_check.py --update --yes`"
