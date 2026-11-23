"""Tests for tests/tools/rebless_batch.py: pure logic plus real git in tiny temp repos (no network, no remote)."""

# ruff: noqa: S603, S607
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import rebless_batch as rb

SNAP = "tests/golden_master_audit/12_scan_output_snapshots/gpu_json.json"


def git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return r.stdout.strip()


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "r"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    (repo / "src").mkdir()
    (repo / "src" / "a.py").write_text("".join(f"line {i}\n" for i in range(1, 41)))
    (repo / "src" / "b.py").write_text("b1\nb2\nb3\n")
    for p in (SNAP, "tests/golden_doom_rosetta/x.json.gz", "tests/golden_master_zero_dep_audit/z.json"):
        (repo / p).parent.mkdir(parents=True, exist_ok=True)
        (repo / p).write_text("snapshot v0\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    return repo


def branch_with(repo: Path, name: str, edits: dict[str, str]) -> str:
    git(repo, "checkout", "-q", "-b", name, "main")
    for path, text in edits.items():
        (repo / path).write_text(text)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", name)
    git(repo, "checkout", "-q", "main")
    return name


# ---- pure logic ----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "snap"),
    [
        (SNAP, True),
        ("tests/golden_master_zero_dep_audit/2_global/summary.json", True),
        ("tests/golden_doom_rosetta/odamex.json.gz", True),
        ("tests/golden_master_audit_notes.md", False),  # a prefix of the name is not the directory
        ("gitgalaxy/standards/language_standards/languages/dart.py", False),
        ("tests/golden_store.py", False),
    ],
)
def test_snapshot_paths_are_exactly_the_three_generated_trees(path, snap):
    assert rb.is_snapshot(path) is snap


def test_split_paths_keeps_order_and_separates():
    hand, snap = rb.split_paths(["a.py", SNAP, "b.md", "tests/golden_doom_rosetta/x.json.gz"])
    assert hand == ["a.py", "b.md"] and snap == [SNAP, "tests/golden_doom_rosetta/x.json.gz"]


def test_parse_hunks_reads_old_side_ranges_per_file():
    diff = (
        "diff --git a/src/a.py b/src/a.py\n--- a/src/a.py\n+++ b/src/a.py\n@@ -10,3 +10,4 @@ x\n+new\n"
        "@@ -30 +31,2 @@\n+two\n"
        "diff --git a/src/b.py b/src/b.py\n@@ -0,0 +1,2 @@\n+n\n"
    )
    h = rb.parse_hunks(diff)
    assert h["src/a.py"] == [(10, 12), (30, 30)]
    assert h["src/b.py"] == [(0, 0)]  # a pure insertion counts as the one line it follows


def test_overlaps_flag_shared_lines_only():
    per = {
        1: {"f.py": [(10, 20)], "g.py": [(1, 5)]},
        2: {"f.py": [(18, 25)], "g.py": [(6, 9)]},  # f overlaps; g is adjacent, not overlapping
        3: {"f.py": [(40, 41)]},
    }
    assert rb.find_overlaps(per) == [("f.py", 1, 2)]


def test_no_overlap_across_different_files():
    assert rb.find_overlaps({1: {"a": [(1, 9)]}, 2: {"b": [(1, 9)]}}) == []


def test_parse_prs_sorts_dedupes_and_needs_two():
    assert rb.parse_prs("9061, 9053 9053,9054") == [9053, 9054, 9061]
    with pytest.raises(rb.Refused):
        rb.parse_prs("9053")


def test_title_body_and_close_commands_name_every_pr():
    prs = [rb.PrInfo(9053, "swift fix", ["a.py"]), rb.PrInfo(9054, "haskell fix", ["b.py", "c.py"])]
    assert rb.batch_title(prs) == "Rebless once for 2 stacked engine fixes (supersedes #9053 #9054)"
    body = rb.render_body(prs, blessed=True)
    assert "#9053 swift fix: `a.py`" in body and "#9054 haskell fix: `b.py`, `c.py`" in body
    assert "blesses the snapshots once" in body and body.rstrip().endswith(rb.ATTRIBUTION)
    assert "not run yet" in rb.render_body(prs, blessed=False)
    cmds = rb.close_commands(prs, "#9111")
    assert len(cmds) == 2 and all("Superseded by #9111" in c for c in cmds) and cmds[0].startswith("gh pr close 9053 ")


# ---- real git, temp repos ------------------------------------------------------------------------------------------


def test_hand_written_diff_leaves_snapshots_out(tmp_path):
    repo = make_repo(tmp_path)
    b = branch_with(
        repo, "pr1", {"src/b.py": "b1\nB2\nb3\n", SNAP: "snapshot v1\n", "tests/golden_doom_rosetta/x.json.gz": "v1\n"}
    )
    diff = rb.hand_written_diff(repo, "main", b)
    assert "src/b.py" in diff and "golden" not in diff
    assert rb.split_paths(rb.changed_files(repo, "main", b))[0] == ["src/b.py"]


def test_two_prs_in_different_places_apply_and_overlap_is_found_when_same_lines(tmp_path):
    repo = make_repo(tmp_path)
    a_lines = (repo / "src" / "a.py").read_text().splitlines()
    top = "\n".join(["TOP", *a_lines[1:]]) + "\n"
    bottom = "\n".join([*a_lines[:-1], "BOTTOM"]) + "\n"
    same = "\n".join([a_lines[0], "SAME", *a_lines[2:]]) + "\n"
    p1 = branch_with(repo, "p1", {"src/a.py": top, SNAP: "s1\n"})
    p2 = branch_with(repo, "p2", {"src/a.py": bottom, SNAP: "s2\n"})
    p3 = branch_with(repo, "p3", {"src/a.py": same.replace("SAME", "TOP2").replace(a_lines[0], "TOP2b", 1)})
    d1, d2 = (rb.hand_written_diff(repo, "main", b) for b in (p1, p2))
    assert rb.find_overlaps({1: rb.parse_hunks(d1), 2: rb.parse_hunks(d2)}) == []  # far apart: stacks
    d3 = rb.hand_written_diff(repo, "main", p3)
    assert rb.find_overlaps({1: rb.parse_hunks(d1), 3: rb.parse_hunks(d3)}) == [("src/a.py", 1, 3)]
    # both non-overlapping PRs apply, in order, onto a fresh copy of main, and the snapshot conflict never arises
    git(repo, "checkout", "-q", "-b", "batch", "main")
    for d in (d1, d2):
        ok, why = rb.apply_diff(repo, d)
        assert ok, why
        git(repo, "commit", "-q", "-m", "apply")
    text = (repo / "src" / "a.py").read_text()
    assert text.startswith("TOP\n") and text.endswith("BOTTOM\n")
    assert (repo / SNAP).read_text() == "snapshot v0\n"  # untouched: the bless owns it


def test_a_diff_that_no_longer_applies_is_reported_not_forced(tmp_path):
    repo = make_repo(tmp_path)
    pr = branch_with(repo, "pr", {"src/b.py": "b1\nFROM-PR\nb3\n"})
    diff = rb.hand_written_diff(repo, "main", pr)
    (repo / "src" / "b.py").write_text("b1\nFROM-MAIN\nb3\n")  # main moved the same line since the PR branched
    git(repo, "commit", "-q", "-am", "main moves")
    ok, why = rb.apply_diff(repo, diff)
    assert not ok and why
    # --3way leaves conflict markers behind: build() therefore refuses and throws the whole worktree away on any failure
    assert "<<<<<<<" in (repo / "src" / "b.py").read_text()


def test_binary_hand_written_files_survive_the_diff(tmp_path):
    repo = make_repo(tmp_path)
    git(repo, "checkout", "-q", "-b", "binpr", "main")
    (repo / "src" / "blob.bin").write_bytes(bytes(range(256)) * 4)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "bin")
    git(repo, "checkout", "-q", "main")
    diff = rb.hand_written_diff(repo, "main", "binpr")
    git(repo, "checkout", "-q", "-b", "batch", "main")
    ok, why = rb.apply_diff(repo, diff)
    assert ok, why
    assert (repo / "src" / "blob.bin").read_bytes() == bytes(range(256)) * 4


def test_bless_env_puts_the_venv_first_and_sets_crucible_paths(monkeypatch):
    for var in ("LANGUAGE_CRUCIBLE_PATH", "CICS_CRUCIBLE_PATH", "ESTATE_CRUCIBLE_PATH"):
        monkeypatch.delenv(var, raising=False)
    env = rb.bless_env()
    assert env["PATH"].startswith(str(rb.VENV_BIN))
    assert env["LANGUAGE_CRUCIBLE_PATH"].endswith("language-crucible") and env["ESTATE_CRUCIBLE_PATH"].endswith(
        "estate-crucible"
    )
    monkeypatch.setenv("CICS_CRUCIBLE_PATH", "/elsewhere")
    assert rb.bless_env()["CICS_CRUCIBLE_PATH"] == "/elsewhere"  # an explicit setting wins


def test_a_change_already_on_main_applies_to_nothing(tmp_path):
    repo = make_repo(tmp_path)
    pr = branch_with(repo, "pr", {"src/b.py": "b1\nB2\nb3\n"})
    diff = rb.hand_written_diff(repo, "main", pr)
    git(repo, "merge", "-q", "--ff-only", pr)  # the same change lands on main by another route
    ok, why = rb.apply_diff(repo, diff)
    assert not ok or not git(repo, "diff", "--cached", "--name-only"), (
        why
    )  # applies to nothing, or is refused: never a stray commit
