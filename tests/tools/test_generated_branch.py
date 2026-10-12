"""generated_branch (#4847): publish/fetch/show against a local bare remote (no network), and a lint that main is
written by bot workflows only where listed -- the history bots publish to `generated` instead."""

import re
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import generated_branch as gb  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO / ".github" / "workflows"


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def remote_and_clone(tmp_path):
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "-q", str(remote), str(clone))
    git(clone, "config", "user.email", "t@t")
    git(clone, "config", "user.name", "t")
    (clone / "docs").mkdir()
    (clone / "docs" / "h.csv").write_text("seed\n")
    git(clone, "add", ".")
    git(clone, "commit", "-q", "-m", "seed")
    git(clone, "push", "-q", "origin", "HEAD:main")
    return remote, clone


def test_first_publish_creates_the_branch_and_leaves_the_checkout_alone(remote_and_clone):
    remote, clone = remote_and_clone
    head = git(clone, "rev-parse", "HEAD")
    (clone / "docs" / "h.csv").write_text("seed\nrow1\n")
    assert gb.publish(["docs/h.csv"], "m", root=clone, stamp="w1")
    assert git(remote, "show", "generated:docs/h.csv") == "seed\nrow1"
    assert "Source: main @" in git(remote, "show", "generated:.generated_from/w1.txt")
    assert git(clone, "rev-parse", "HEAD") == head and git(clone, "status", "--porcelain").endswith("M docs/h.csv")


def test_unchanged_files_commit_nothing_and_a_change_is_one_commit(remote_and_clone):
    remote, clone = remote_and_clone
    assert gb.publish(["docs/h.csv"], "m", root=clone, stamp="w1")
    assert gb.publish(["docs/h.csv"], "m", root=clone, stamp="w1") is None
    (clone / "docs" / "h.csv").write_text("changed\n")
    assert gb.publish(["docs/h.csv"], "m2", root=clone, stamp="w1")
    assert git(remote, "rev-list", "--count", "generated") == "2"


def test_writers_with_disjoint_paths_do_not_overwrite_each_other(remote_and_clone):
    remote, clone = remote_and_clone
    (clone / "docs" / "other.json").write_text("{}\n")
    assert gb.publish(["docs/other.json"], "other", root=clone)
    assert gb.publish(["docs/h.csv"], "mine", root=clone)
    assert git(remote, "show", "generated:docs/other.json") == "{}"
    assert git(remote, "show", "generated:docs/h.csv") == "seed"


def test_fetch_restores_the_published_copy_and_falls_back_when_absent(remote_and_clone):
    remote, clone = remote_and_clone
    assert gb.fetch(["docs/h.csv"], root=clone) == []  # no generated branch yet: the committed copy stays
    assert gb.show("docs/h.csv", root=clone) == b"seed\n"
    (clone / "docs" / "h.csv").write_text("seed\nnewer\n")
    gb.publish(["docs/h.csv"], "m", root=clone)
    git(clone, "checkout", "-q", "--", "docs/h.csv")
    assert gb.show("docs/h.csv", root=clone) == b"seed\nnewer\n"
    assert gb.fetch(["docs/h.csv", "docs/not-published.csv"], root=clone) == ["docs/h.csv"]
    assert (clone / "docs" / "h.csv").read_text() == "seed\nnewer\n"


def test_publish_refuses_a_missing_file(remote_and_clone):
    _, clone = remote_and_clone
    with pytest.raises(FileNotFoundError):
        gb.publish(["docs/nope.csv"], "m", root=clone)


# --- the workflows -----------------------------------------------------------------------------------------------

# Bot workflows that still land a commit on main through a PR. Each is a known gap (#4847 / #4935), not a pattern to
# copy: new bot output goes to `generated` through tests/tools/generated_branch.py.
STILL_COMMITS_TO_MAIN = {
    "gitgalaxy.yml",  # docs/gitgalaxy_architecture_brief.md, read from the checkout by agents (CLAUDE.md)
    "mainframe-ground-truth.yml",  # docs/self_scan/ground_truth_history.jsonl (#4935 in flight)
    "evidence-refresh.yml",  # evidence records + det-sweep ledger: inputs of human approval, must be on main
    "release-crucible-archive.yml",  # opens its PR in language-crucible, not in this repo
}
MOVED = {
    "call-resolution-history.yml": ["docs/self_scan/call_resolution_history.csv"],
    "graph-comparison-history.yml": ["docs/self_scan/graph_comparison_ledger.json"],
    "tree-sitter-accuracy-history.yml": ["docs/self_scan/tree_sitter_accuracy_history.csv"],
    "tri-comparison-history.yml": ["docs/self_scan/tri_comparison_ledger.json"],
    "archetype-validation.yml": ["gitgalaxy/standards/archetype_brains/archetype_validation.json"],
}


def _text(name):
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def _code(name):
    return "\n".join(ln for ln in _text(name).splitlines() if not ln.lstrip().startswith("#"))


def test_only_the_listed_workflows_commit_to_main():
    offenders = []
    for p in sorted(WORKFLOWS.glob("*.yml")):
        code = _code(p.name)
        if re.search(r"create-pull-request@|gh pr merge|git push[^\n]*\borigin\b[^\n]*\bmain\b", code):
            offenders.append(p.name)
    assert set(offenders) == STILL_COMMITS_TO_MAIN, (
        f"workflows committing to main: {offenders}; publish bot output to `generated` "
        f"(tests/tools/generated_branch.py) or list the new writer here with a reason"
    )


@pytest.mark.parametrize("name", sorted(MOVED))
def test_a_moved_writer_publishes_to_generated_and_never_opens_a_pr(name):
    code = _code(name)
    assert "create-pull-request" not in code and "gh pr merge" not in code and "AUTOMATION_PAT" not in code
    assert "generated_branch.py publish" in code
    for path in MOVED[name]:
        assert path in code, f"{name} does not publish {path}"
    assert re.search(r"pull-requests:\s*write", code) is None, "a writer that opens no PR needs no pull-requests: write"
    assert re.search(r"persist-credentials:\s*true", code), "the publish step pushes with the checkout's credentials"


@pytest.mark.parametrize(
    "name", ["call-resolution-history.yml", "tree-sitter-accuracy-history.yml", "graph-comparison-history.yml"]
)
def test_an_appending_writer_starts_from_the_published_series(name):
    """The history CSV is appended to: it must be restored from generated before the tool runs, or each run would
    append to main's frozen copy and publish a series that forgets every earlier batch."""
    code = _code(name)
    assert code.index("generated_branch.py fetch") < code.index("--history")
