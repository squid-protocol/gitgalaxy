"""#6278: the shared change classifier -- areas, the scanner behind docs_read_by_tests.txt, and the list's freshness."""

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import change_classifier as cc  # noqa: E402


def refs(src: str) -> set[str]:
    return cc.refs_of_source(src, {"x.json"})


def test_a_literal_path_is_a_ref():
    assert "docs/language_status/a.json" in refs('open("docs/language_status/a.json")')


def test_a_path_chain_and_its_alias_resolve_to_the_file():
    src = 'DOCS = ROOT / "docs" / "language_status"\nx = DOCS / "a.json"\nopen(x)\n'
    assert "docs/language_status/a.json" in refs(src)
    assert "docs/language_status/" not in refs(src)


def test_an_fstring_hole_becomes_a_wildcard_and_a_bare_wildcard_is_dropped():
    assert "docs/language_status/" in refs('f"docs/language_status/{name}.md"')  # cut to the literal directory
    assert "*.md" not in refs('f"{name}.md"')


def test_a_url_is_not_a_read():
    assert not any(r.startswith("docs/") for r in refs('"https://github.com/o/r/blob/main/docs/ci.md"'))


@pytest.mark.parametrize(
    ("ref", "path", "hit"),
    [
        ("docs/a/", "docs/a/b.md", True),
        ("docs/a/*.md", "docs/a/b.md", True),
        ("docs/a/b.md", "docs/a/b.md", True),
        ("b.md", "docs/a/b.md", True),
        ("README.md", "README.md", False),  # a bare name is never a root or code file
        ("/CLAUDE.md", "CLAUDE.md", True),
        ("/CLAUDE.md", "docs/CLAUDE.md", False),
    ],
)
def test_ref_matches(ref, path, hit):
    assert cc.ref_matches(ref, path) is hit


@pytest.mark.parametrize(
    ("path", "area"),
    [
        (".claude/rules/x.md", "agent-config"),
        ("CLAUDE.md", "agent-config"),
        ("zz_nothing_reads_this.md", "prose"),
        ("docs/language_status/register/C5.md", "test-read-doc"),
        ("tests/tools/ladder_refresh.py", "test-tooling"),
        ("tests/cobol_mainframe/test_x.py", "tests"),
        ("gitgalaxy/core/prism.py", "engine"),
        (".github/workflows/ci.yml", "workflow"),
        ("setup.cfg", "other"),
    ],
)
def test_area(path, area):
    assert cc.area(path) == area


def test_the_ground_truth_job_reads_the_register_and_not_the_probe_record():
    assert cc.read_by_ground_truth("docs/language_status/register/C5.md")
    assert cc.read_by_ground_truth("docs/language_status/oracle_assumptions.md")
    assert not cc.read_by_ground_truth("docs/language_status/zos_probes.json")
    assert not cc.read_by_ground_truth(".claude/rules/agent-memory.md")
    assert not cc.read_by_ground_truth("README.md")


def test_the_scopes_include_the_engine_and_the_job_tests():
    scopes = cc.ground_truth_scopes()
    assert {"gitgalaxy", "tests/cobol_mainframe", "tests/tools/ground_truth_ledger.py"} <= scopes
    assert "tests/tools/shepherd_gh.py" not in scopes


@pytest.mark.slow(
    reason="scans every .py under tests/ and gitgalaxy/ (about 25 s) to prove the committed list is fresh"
)
def test_the_committed_list_is_fresh():
    assert cc.LIST_PATH.read_text(encoding="utf-8") == cc.render(cc.scan()), (
        "docs_read_by_tests.txt is stale: python tests/tools/change_classifier.py --write"
    )


def test_known_names_are_the_tracked_files_not_an_ignored_one_on_disk(tmp_path):
    """#6302: the evidence report's ignored report.json, materialised by an earlier test, changed the render."""
    import subprocess

    def git(*a):
        subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)

    git("init", "-q")
    (tmp_path / "docs/sub").mkdir(parents=True)
    (tmp_path / "docs/sub/tracked.md").write_text("x")
    (tmp_path / "docs/sub/ignored.json").write_text("{}")
    (tmp_path / ".gitignore").write_text("docs/sub/ignored.json\n")
    git("add", ".gitignore", "docs/sub/tracked.md")
    assert cc._known_names(tmp_path) == {"tracked.md"}


def _git_repo(tmp_path):
    import subprocess

    def git(*a):
        subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)

    git("init", "-q")
    (tmp_path / "tests/tools").mkdir(parents=True)
    (tmp_path / "tests/tools/tracked.py").write_text("x = 1\n")
    (tmp_path / "top.py").write_text("x = 1\n")
    (tmp_path / ".gitignore").write_text("tests/tools/scratch_*.py\n")
    (tmp_path / "tests/tools/scratch_a.py").write_text('P = "docs/ignored_name.md"\n')
    git("add", ".gitignore", "top.py", "tests/tools/tracked.py")


def test_py_files_are_git_s_view_not_an_ignored_scratch_file(tmp_path):
    """#6302 sibling: scan() and ground_truth_scopes() list .py files from git, so an ignored one changes nothing."""
    _git_repo(tmp_path)
    (tmp_path / "tests/tools/new.py").write_text("y = 1\n")  # new and not ignored: still read
    names = {p.name for p in cc._py_files(tmp_path, "tests")}
    assert names == {"tracked.py", "new.py"}
    assert {p.name for p in cc._py_files(tmp_path, deep=False)} == {"top.py"}
    assert {p.name for p in cc._py_files(tmp_path, "tests/tools", deep=False)} == {"tracked.py", "new.py"}


def test_py_files_fall_back_to_disk_without_git(tmp_path, monkeypatch):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/a.py").write_text("x = 1\n")
    monkeypatch.setattr(cc, "_repo_files", lambda *a, **k: None)
    assert [p.name for p in cc._py_files(tmp_path, "tests")] == ["a.py"]
