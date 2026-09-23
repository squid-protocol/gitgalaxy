"""
Synthetic-repo tests for rebase_rebless.py (#3385). Real gitgalaxy/language-crucible
machinery (crucible_check.py's venvs, audit_check.py's ruff/mypy scans) isn't available
here, so regenerate_golden_masters/refresh_lint_baselines are monkeypatched to fakes that
write deterministic content -- everything else (fetch, rebase, conflict classification,
own-key auto-detection, foreign-drift verification) runs against real, throwaway git repos.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import golden_diff as gd
import golden_store

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rebase_rebless as rr

MASTER_REL = golden_store.FULL_PRECISION  # split fixture directory (#3384)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True)
    assert result.returncode == 0, f"git {args} in {repo} failed:\n{result.stdout}\n{result.stderr}"
    return result


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test")
    _git(path, "config", "commit.gpgsign", "false")


def _write_master(repo: Path, data: dict) -> None:
    golden_store.write(data, repo / MASTER_REL)


def _read_master(repo: Path) -> dict:
    return golden_store.load(repo / MASTER_REL)


def _commit(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


def _build_two_branch_scenario(tmp_path: Path, feature_key_value=2, sibling_key_value="S") -> Path:
    """bare origin <- seed (advances main, simulating a sibling PR merging) and
    feature (the branch under test, blesses its own key, never pushed)."""
    bare = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(bare))

    seed = tmp_path / "seed"
    _init_repo(seed)
    _git(seed, "remote", "add", "origin", str(bare))
    _write_master(seed, {"data": {"shared": 1}})
    _commit(seed, "base golden master")
    _git(seed, "push", "-q", "-u", "origin", "main")

    feature = tmp_path / "feature"
    _git(tmp_path, "clone", "-q", str(bare), str(feature))
    _git(feature, "config", "user.email", "test@example.com")
    _git(feature, "config", "user.name", "Test")
    _git(feature, "config", "commit.gpgsign", "false")
    _git(feature, "checkout", "-q", "-b", "feature")
    _write_master(feature, {"data": {"shared": 1, "feature_key": feature_key_value}})
    _commit(feature, "branch blesses its own key")

    _write_master(seed, {"data": {"shared": 1, "sibling_key": sibling_key_value}})
    _commit(seed, "sibling blesses its own key")
    _git(seed, "push", "-q", "origin", "main")

    return feature


def _fake_regenerate(final_data: dict):
    def fake(repo: Path) -> None:
        _write_master(repo, final_data)

    return fake


def _fake_refresh_ok(repo: Path) -> bool:
    return True


# --------------------------------------------------------------------------
# unit-level: no git repo needed
# --------------------------------------------------------------------------


def test_classify_splits_artifact_and_code():
    artifact, code = rr.classify(
        [
            "tests/golden_master_audit/2_global_ecosystem_summary/summary.json",
            "tests/golden_master_zero_dep_audit/_layout.json",
            "tests/golden_master_audit.json",  # pre-#3384 monolith, rebasing across the split
            "gitgalaxy/core.py",
            "tests/golden_master_audit_notes.md",
            "tests/ruff_audit_baseline.json",
        ]
    )
    assert artifact == [
        "tests/golden_master_audit/2_global_ecosystem_summary/summary.json",
        "tests/golden_master_zero_dep_audit/_layout.json",
        "tests/golden_master_audit.json",
        "tests/ruff_audit_baseline.json",
    ]
    assert code == ["gitgalaxy/core.py", "tests/golden_master_audit_notes.md"]


def test_leaf_keys_filters_topological_coordinates():
    old = {"Section": {"node": {"X": 1.0, "Y": 2.0, "Z": 3.0, "new_key": 0}}}
    new = {"Section": {"node": {"X": 1.5, "Y": 2.1, "Z": 3.2, "new_key": 5}}}
    diffs = gd.deep_compare(old, new)
    assert rr.leaf_keys(diffs) == {"new_key"}


def test_push_without_execute_errors():
    with pytest.raises(SystemExit):
        rr.main(["--push"])


# --------------------------------------------------------------------------
# synthetic two-branch scenarios
# --------------------------------------------------------------------------


def test_clean_rebase_only_own_key_drifts(tmp_path, monkeypatch):
    feature = _build_two_branch_scenario(tmp_path)
    monkeypatch.setattr(
        rr,
        "regenerate_golden_masters",
        _fake_regenerate({"data": {"shared": 1, "sibling_key": "S", "feature_key": 2}}),
    )
    monkeypatch.setattr(rr, "refresh_lint_baselines", _fake_refresh_ok)

    rc = rr.main(["--execute", "--repo", str(feature)])
    assert rc == 0

    final = _read_master(feature)
    assert final == {"data": {"shared": 1, "sibling_key": "S", "feature_key": 2}}
    # the rebase actually landed: origin/main's sibling commit is now an ancestor
    log = _git(feature, "log", "--oneline", "origin/main..HEAD").stdout
    assert "sibling" not in log  # sibling's commit is behind HEAD, not ahead of it


def test_foreign_drift_rejected(tmp_path, monkeypatch):
    feature = _build_two_branch_scenario(tmp_path)
    # The rebless introduces an extra, undeclared key -- e.g. a bug, or scope
    # creep unrelated to this branch's own pre-rebase diff.
    monkeypatch.setattr(
        rr,
        "regenerate_golden_masters",
        _fake_regenerate({"data": {"shared": 1, "sibling_key": "S", "feature_key": 2, "unexpected_key": "oops"}}),
    )
    monkeypatch.setattr(rr, "refresh_lint_baselines", _fake_refresh_ok)

    rc = rr.main(["--execute", "--repo", str(feature)])
    assert rc == 1


def test_expect_keys_override_can_reject_an_otherwise_clean_rebase(tmp_path, monkeypatch):
    feature = _build_two_branch_scenario(tmp_path)
    monkeypatch.setattr(
        rr,
        "regenerate_golden_masters",
        _fake_regenerate({"data": {"shared": 1, "sibling_key": "S", "feature_key": 2}}),
    )
    monkeypatch.setattr(rr, "refresh_lint_baselines", _fake_refresh_ok)

    rc = rr.main(["--execute", "--repo", str(feature), "--expect-keys", "totally_different_key"])
    assert rc == 1


def test_code_conflict_stops_without_aborting(tmp_path):
    bare = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(bare))

    seed = tmp_path / "seed"
    _init_repo(seed)
    _git(seed, "remote", "add", "origin", str(bare))
    code_path = seed / "gitgalaxy" / "core.py"
    code_path.parent.mkdir(parents=True)
    code_path.write_text("value = 1\n", encoding="utf-8")
    _commit(seed, "base code")
    _git(seed, "push", "-q", "-u", "origin", "main")

    feature = tmp_path / "feature"
    _git(tmp_path, "clone", "-q", str(bare), str(feature))
    _git(feature, "config", "user.email", "test@example.com")
    _git(feature, "config", "user.name", "Test")
    _git(feature, "config", "commit.gpgsign", "false")
    _git(feature, "checkout", "-q", "-b", "feature")
    (feature / "gitgalaxy" / "core.py").write_text("value = 2\n", encoding="utf-8")
    _commit(feature, "feature changes the same line")

    (seed / "gitgalaxy" / "core.py").write_text("value = 3\n", encoding="utf-8")
    _commit(seed, "main changes the same line")
    _git(seed, "push", "-q", "origin", "main")

    rc = rr.main(["--execute", "--repo", str(feature)])
    assert rc == 1
    # Left mid-flight for a human/agent to resolve normally -- never auto-resolved,
    # never aborted out from under them.
    assert rr.rebase_in_progress(feature)
    assert rr.conflicted_files(feature) == ["gitgalaxy/core.py"]


def test_dry_run_default_does_not_mutate(tmp_path):
    feature = _build_two_branch_scenario(tmp_path)
    before_content = _read_master(feature)
    before_head = _git(feature, "rev-parse", "HEAD").stdout.strip()

    rc = rr.main(["--repo", str(feature)])  # no --execute

    assert rc == 0
    assert _read_master(feature) == before_content
    assert _git(feature, "rev-parse", "HEAD").stdout.strip() == before_head
    assert not rr.rebase_in_progress(feature)


def test_dry_run_reports_code_conflict_and_fails(tmp_path):
    bare = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(bare))

    seed = tmp_path / "seed"
    _init_repo(seed)
    _git(seed, "remote", "add", "origin", str(bare))
    code_path = seed / "gitgalaxy" / "core.py"
    code_path.parent.mkdir(parents=True)
    code_path.write_text("value = 1\n", encoding="utf-8")
    _commit(seed, "base code")
    _git(seed, "push", "-q", "-u", "origin", "main")

    feature = tmp_path / "feature"
    _git(tmp_path, "clone", "-q", str(bare), str(feature))
    _git(feature, "config", "user.email", "test@example.com")
    _git(feature, "config", "user.name", "Test")
    _git(feature, "config", "commit.gpgsign", "false")
    _git(feature, "checkout", "-q", "-b", "feature")
    (feature / "gitgalaxy" / "core.py").write_text("value = 2\n", encoding="utf-8")
    _commit(feature, "feature changes the same line")

    (seed / "gitgalaxy" / "core.py").write_text("value = 3\n", encoding="utf-8")
    _commit(seed, "main changes the same line")
    _git(seed, "push", "-q", "origin", "main")

    rc = rr.main(["--repo", str(feature)])  # no --execute
    assert rc == 1
    assert not rr.rebase_in_progress(feature)  # merge-tree never touches the real branch


# --------------------------------------------------------------------------
# split golden masters (#3384)
# --------------------------------------------------------------------------


def test_additive_keys_no_longer_conflict(tmp_path):
    """The #3249 failure mode: two branches each add their own key to the same
    region. With the split layout each key is its own file, so the merge-tree
    preview reports nothing at all -- not even an artifact conflict."""
    feature = _build_two_branch_scenario(tmp_path)
    _git(feature, "fetch", "-q", "origin")
    assert rr.dry_run_preview(feature, "origin/main") == []


def test_same_value_conflict_resolves_to_main_and_regenerates(tmp_path, monkeypatch):
    """Both sides re-bless the SAME leaf (e.g. a shared coordinate) -- a real
    conflict inside one split file, still classified as an artifact and resolved."""
    feature = _build_two_branch_scenario(tmp_path)
    _write_master(feature, {"data": {"shared": 2, "feature_key": 2}})
    _commit(feature, "branch also moves the shared leaf")
    seed = tmp_path / "seed"
    _write_master(seed, {"data": {"shared": 3, "sibling_key": "S"}})
    _commit(seed, "sibling moves the shared leaf too")
    _git(seed, "push", "-q", "origin", "main")

    _git(feature, "fetch", "-q", "origin")
    preview = rr.dry_run_preview(feature, "origin/main")
    assert preview and all(golden_store.is_golden_master_path(p) for p in preview)

    final = {"data": {"shared": 3, "sibling_key": "S", "feature_key": 2}}
    monkeypatch.setattr(rr, "regenerate_golden_masters", _fake_regenerate(final))
    monkeypatch.setattr(rr, "refresh_lint_baselines", _fake_refresh_ok)
    rc = rr.main(["--execute", "--repo", str(feature), "--expect-keys", "feature_key,shared"])
    assert rc == 0
    assert _read_master(feature) == final
    assert not rr.rebase_in_progress(feature)


def test_branch_cut_before_the_split_rebases_across_it(tmp_path, monkeypatch):
    """A branch that still edits the pre-#3384 monolith, rebased onto a main
    that replaced it with the split directory: the modify/delete conflict is an
    artifact conflict (main's deletion wins), own keys are still auto-detected
    from the monolith history, and the rebless lands in the split layout."""
    legacy = "tests/golden_master_audit.json"
    bare = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(bare))
    seed = tmp_path / "seed"
    _init_repo(seed)
    _git(seed, "remote", "add", "origin", str(bare))
    (seed / "tests").mkdir()
    (seed / legacy).write_text(json.dumps({"data": {"shared": 1}}, indent=4), encoding="utf-8")
    _commit(seed, "monolithic golden master")
    _git(seed, "push", "-q", "-u", "origin", "main")

    feature = tmp_path / "feature"
    _git(tmp_path, "clone", "-q", str(bare), str(feature))
    _git(feature, "config", "user.email", "test@example.com")
    _git(feature, "config", "user.name", "Test")
    _git(feature, "config", "commit.gpgsign", "false")
    _git(feature, "checkout", "-q", "-b", "feature")
    (feature / legacy).write_text(json.dumps({"data": {"shared": 1, "feature_key": 2}}, indent=4), encoding="utf-8")
    _commit(feature, "branch blesses its own key into the monolith")

    _git(seed, "rm", "-q", legacy)
    _write_master(seed, {"data": {"shared": 1, "sibling_key": "S"}})
    _commit(seed, "main splits the golden master and adds a sibling key")
    _git(seed, "push", "-q", "origin", "main")

    final = {"data": {"shared": 1, "sibling_key": "S", "feature_key": 2}}
    monkeypatch.setattr(rr, "regenerate_golden_masters", _fake_regenerate(final))
    monkeypatch.setattr(rr, "refresh_lint_baselines", _fake_refresh_ok)
    rc = rr.main(["--execute", "--repo", str(feature)])  # own keys auto-detected
    assert rc == 0
    assert not (feature / legacy).exists()
    assert _read_master(feature) == final
