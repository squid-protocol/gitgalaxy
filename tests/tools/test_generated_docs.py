"""generated_docs (#5057): the aggregate pages render deterministically from committed sources, are never committed,
and two PRs that each add a register entry merge in either order without a conflict."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import generated_docs as gd  # noqa: E402
import register  # noqa: E402

REPO = TOOLS.parents[1]


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


@pytest.mark.parametrize("rel", sorted(gd.PAGES))
def test_every_page_renders_twice_identically(rel, tmp_path):
    if rel.endswith("cics_spec_status.md"):
        pytest.importorskip("tree_sitter_language_pack")  # the det translator is read live
    assert gd.check(tmp_path, {rel: gd.PAGES[rel]}) == []
    assert (tmp_path / rel).read_text(encoding="utf-8") == gd.PAGES[rel]()


@pytest.mark.parametrize("rel", sorted(gd.PAGES))
def test_no_page_is_committed_and_each_is_ignored(rel):
    assert git(REPO, "ls-files", "--", rel) == "", f"{rel} is generated: commit its sources, not the page"
    assert subprocess.run(["git", "check-ignore", "-q", rel], cwd=REPO, check=False).returncode == 0


def test_a_page_that_does_not_render_fails_the_check(tmp_path):
    def broken():
        raise ValueError("entries in a family _layout.json does not place: ['Z1']")

    problems = gd.check(tmp_path, {"docs/x.md": broken})
    assert problems and "docs/x.md: does not render" in problems[0] and "Z1" in problems[0]
    assert not (tmp_path / "docs" / "x.md").exists()


def test_a_non_deterministic_render_fails_the_check(tmp_path):
    calls = iter(["a\n", "b\n"])
    problems = gd.check(tmp_path, {"docs/x.md": lambda: next(calls)})
    assert problems and "not deterministic" in problems[0]


def test_a_stray_register_entry_fails_the_register_render(tmp_path, monkeypatch):
    """A source the renderer cannot place (a family _layout.json does not list) is an error, not a silent drop."""
    reg = tmp_path / "register"
    shutil.copytree(register.REG, reg)
    meta = dict.fromkeys(register.KEYS, "") | {"id": "Z1", "family": "Z", "title": "t", "status": "s"}
    (reg / "Z1.md").write_text(register.format_entry(meta, "body"), encoding="utf-8")
    monkeypatch.setattr(register, "REG", reg)
    problems = gd.check(None, {"docs/language_status/oracle_assumptions.md": gd._register})
    assert problems and "Z1" in problems[0]
    assert register.check()


def test_diff_names_changed_pages_only(tmp_path):
    base, new = tmp_path / "base", tmp_path / "new"
    for root, text in ((base, "a\nb\n"), (new, "a\nc\n")):
        (root / "docs").mkdir(parents=True)
        (root / "docs" / "p.md").write_text(text, encoding="utf-8")
        (root / "docs" / "same.md").write_text("x\n", encoding="utf-8")
    out = gd.diff(base, new, ["docs/p.md", "docs/same.md", "docs/new.md"])
    assert "`docs/p.md`: +1 / -1 lines" in out and "-b" in out and "+c" in out
    assert "`docs/same.md`: unchanged" in out
    assert "`docs/new.md`: unchanged" in out  # absent on both sides


def test_diff_of_a_page_new_in_the_pr_is_all_additions(tmp_path):
    (tmp_path / "new" / "docs").mkdir(parents=True)
    (tmp_path / "new" / "docs" / "p.md").write_text("a\nb\n", encoding="utf-8")
    (tmp_path / "base").mkdir()
    assert "`docs/p.md`: +2 / -0 lines" in gd.diff(tmp_path / "base", tmp_path / "new", ["docs/p.md"])


def test_two_prs_each_adding_a_register_entry_merge_in_either_order(tmp_path, monkeypatch):
    """#5057 acceptance: with the page uncommitted, two branches that each add one entry file (the whole of a register
    PR now) merge in both orders with no conflict, and the render of the merge holds both entries."""
    repo = tmp_path / "repo"
    reg_rel = Path("docs/language_status/register")
    shutil.copytree(register.REG, repo / reg_rel)
    git(repo.parent, "init", "-q", "-b", "main", str(repo))
    git(repo, "config", "user.email", "t@t")
    git(repo, "config", "user.name", "t")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "seed")
    fam = next(m["family"] for m, _ in register.load_entries())
    ids = [f"{fam}{900 + i}" for i in range(2)]
    for branch, i in zip(("a", "b"), ids, strict=True):
        git(repo, "checkout", "-q", "-b", branch, "main")
        meta = dict.fromkeys(register.KEYS, "") | {"id": i, "family": fam, "title": f"entry {i}", "status": "open"}
        meta["summary"] = f"summary {i}"
        (repo / reg_rel / f"{i}.md").write_text(register.format_entry(meta, f"body {i}"), encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-q", "-m", i)
    for first, second in (("a", "b"), ("b", "a")):
        git(repo, "checkout", "-q", "-B", f"m-{first}", "main")
        git(repo, "merge", "-q", "--no-edit", first)
        merged = subprocess.run(["git", "merge", "--no-edit", second], cwd=repo, capture_output=True, text=True)
        assert merged.returncode == 0, f"{first} then {second} conflicted: {merged.stdout}{merged.stderr}"
        monkeypatch.setattr(register, "REG", repo / reg_rel)
        page = register.render()
        monkeypatch.undo()
        assert all(f"### {i}. entry {i}" in page and f"| {i} |" in page for i in ids)
