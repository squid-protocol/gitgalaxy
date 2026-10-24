"""context_pack: resolve an issue's paths and names against a small fixture master DB."""

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import context_pack as cp  # noqa: E402


@pytest.fixture()
def db():
    con = sqlite3.connect(":memory:")
    con.executescript(
        """
        CREATE TABLE file_data (id INTEGER PRIMARY KEY, file_path TEXT, file_name TEXT,
            total_loc INTEGER, token_mass INTEGER);
        CREATE TABLE function_data (id INTEGER PRIMARY KEY, file_id INTEGER, func_name TEXT,
            start_line INTEGER, loc INTEGER, complexity INTEGER, func_fan_in INTEGER);
        CREATE TABLE class_data (id INTEGER PRIMARY KEY, file_id INTEGER, class_name TEXT);
        CREATE TABLE fcall_data (id INTEGER PRIMARY KEY, src_func_id INTEGER, dst_func_id INTEGER);
        CREATE TABLE edge_data (id INTEGER PRIMARY KEY, src_file_id INTEGER, dst_file_id INTEGER);
        INSERT INTO file_data VALUES (1, 'gitgalaxy/core/detector.py', 'detector.py', 10000, 135000);
        INSERT INTO file_data VALUES (2, 'gitgalaxy/core/prism.py', 'prism.py', 300, 4000);
        INSERT INTO file_data VALUES (3, 'gitgalaxy/standards/language_standards/languages/glsl.py',
            'glsl.py', 90, 900);
        INSERT INTO function_data VALUES (1, 1, 'process_payload', 236, 165, 31, 2);
        INSERT INTO function_data VALUES (2, 2, 'split_surface', 40, 20, 5, 1);
        INSERT INTO function_data VALUES (3, 1, 'helper_a', 1, 5, 1, 0);
        INSERT INTO class_data VALUES (1, 2, 'PrismSplitter');
        INSERT INTO fcall_data VALUES (1, 1, 2);
        INSERT INTO edge_data VALUES (1, 1, 2);
        """
    )
    return con


def test_exact_path_gives_range_free_file_line_and_big_flag(db):
    out = cp.build_pack(db, "fix", "see `gitgalaxy/core/detector.py`")
    assert "`gitgalaxy/core/detector.py` (10000 loc, 135000 tokens: BIG, read only the named ranges" in out
    assert "prism.py" not in out


def test_bare_function_name_gives_span_and_one_hop_edges(db):
    out = cp.build_pack(db, "bug in process_payload", "")
    assert "`process_payload` gitgalaxy/core/detector.py:236-400 (complexity 31)" in out
    assert "callees: `split_surface` gitgalaxy/core/prism.py:40-59" in out
    split = cp.build_pack(db, "", "`split_surface()` is wrong")
    assert "callers: `process_payload` gitgalaxy/core/detector.py:236-400" in split


def test_class_name(db):
    out = cp.build_pack(db, "PrismSplitter drops a line", "")
    assert "`PrismSplitter` in `gitgalaxy/core/prism.py`" in out


def test_language_stem_word_points_at_the_language_file(db):
    assert "languages/glsl.py" in cp.build_pack(db, "GLSL shaders are dropped", "")


def test_extensions_and_short_words_are_not_names(db):
    assert cp.build_pack(db, "`.py` and `fp` and `run`", "plain prose here") == ""


def test_no_match_prints_nothing(db):
    assert cp.build_pack(db, "nothing_here", "`no_such_func` in `nope/missing.py`") == ""


def test_token_cap(db):
    for i in range(40):
        db.execute("INSERT INTO function_data VALUES (?, 2, ?, 1, 5, 1, 0)", (100 + i, f"long_name_func_{i}"))
    body = " ".join(f"long_name_func_{i}" for i in range(40))
    full = cp.build_pack(db, "t", body, max_tokens=3000)
    capped = cp.build_pack(db, "t", body, max_tokens=60)
    assert len(capped) < len(full)
    assert len(capped) // cp.CHARS_PER_TOKEN <= 60 + 5


def test_cli_body_file_offline(db, tmp_path):
    path = tmp_path / "m.db"
    disk = sqlite3.connect(path)
    db.backup(disk)
    disk.close()
    body = tmp_path / "issue.md"
    body.write_text("title\n`process_payload` is wrong\n", encoding="utf-8")
    out = subprocess.run(
        [sys.executable, str(Path(cp.__file__)), "1", "--db", str(path), "--body-file", str(body)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "process_payload" in out


def test_prior_files_name_an_epic_whose_body_names_no_code(db):
    out = cp.build_pack(db, "epic: speed", "no code named here", prior=["gitgalaxy/core/prism.py", "docs/x.md"])
    assert "Earlier PRs for this issue changed:" in out
    assert "`gitgalaxy/core/prism.py`" in out
    assert "docs/x.md" not in out  # not in the DB


def test_prior_files_reads_commits_mentioning_the_issue(tmp_path):
    def git(*a):
        subprocess.run(["git", "-c", "user.email=a@b", "-c", "user.name=x", *a], cwd=tmp_path, check=True)

    git("init", "-q")
    (tmp_path / "a.py").write_text("1\n")
    (tmp_path / "b.py").write_text("1\n")
    git("add", "a.py")
    git("commit", "-qm", "a (Part of #77)")
    git("add", "b.py")
    git("commit", "-qm", "b (Part of #770)")
    git("update-ref", "refs/remotes/origin/main", "HEAD")
    assert cp.prior_files("77", tmp_path) == ["a.py"]
    assert cp.prior_files("not-a-number", tmp_path) == []


def test_prior_files_matches_the_number_at_the_end_or_before_punctuation(tmp_path):
    def git(*a):
        subprocess.run(["git", "-c", "user.email=a@b", "-c", "user.name=x", *a], cwd=tmp_path, check=True)

    git("init", "-q")
    for name, msg in (("a.py", "a #77"), ("b.py", "b (see #77, again)"), ("c.py", "c #7")):
        (tmp_path / name).write_text("1\n")
        git("add", name)
        git("commit", "-qm", msg)
    git("update-ref", "refs/remotes/origin/main", "HEAD")
    assert sorted(cp.prior_files("77", tmp_path)) == ["a.py", "b.py"]


def _git(repo, *a):
    subprocess.run(["git", "-c", "user.email=a@b", "-c", "user.name=x", *a], cwd=repo, check=True)


def test_prior_files_before_excludes_the_commit_itself(tmp_path):
    _git(tmp_path, "init", "-q")
    for name, msg in (("a.py", "a (Part of #77)"), ("b.py", "b (Part of #77) (#9)")):
        (tmp_path / name).write_text("1\n")
        _git(tmp_path, "add", name)
        _git(tmp_path, "commit", "-qm", msg)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True
    ).stdout.strip()
    _git(tmp_path, "update-ref", "refs/remotes/origin/main", "HEAD")
    assert sorted(cp.prior_files("77", tmp_path)) == ["a.py", "b.py"]
    assert cp.prior_files("77", tmp_path, before=sha) == ["a.py"]


def test_is_source_keeps_code_and_tests_drops_docs_and_data():
    assert cp.is_source("gitgalaxy/core/prism.py")
    assert cp.is_source("tests/tools/test_x.py")
    for p in ("docs/a.py", "README.md", "tests/g/part.json", ".github/workflows/ci.yml", ".claude/rules/a.md"):
        assert not cp.is_source(p)


def test_recent_issue_prs_one_per_issue_newest_first(tmp_path):
    _git(tmp_path, "init", "-q")
    for name, msg in (
        ("a.py", "first (Part of #10) (#1)"),
        ("b.py", "no issue here (#2)"),
        ("c.py", "second (Closes #11) (#3)"),
        ("d.py", "again (Part of #11) (#4)"),
        ("e.py", "issue but no pr (Part of #12)"),
    ):
        (tmp_path / name).write_text("1\n")
        _git(tmp_path, "add", name)
        _git(tmp_path, "commit", "-qm", msg)
    _git(tmp_path, "update-ref", "refs/remotes/origin/main", "HEAD")
    rows = cp.recent_issue_prs(5, tmp_path)
    assert [(i, pr, f) for i, pr, _sha, f in rows] == [("11", "4", ["d.py"]), ("10", "1", ["a.py"])]


def test_evaluate_counts_named_source_files_and_stays_under_the_cap(db, tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "base")
    _git(tmp_path, "update-ref", "refs/remotes/origin/main", "HEAD")
    prs = [
        ("1", "11", "HEAD", ["gitgalaxy/core/prism.py", "docs/x.md"]),
        ("2", "12", "HEAD", ["gitgalaxy/core/detector.py", "gitgalaxy/core/prism.py"]),
        ("3", "13", "HEAD", ["gitgalaxy/other.py"]),
    ]
    issues = {
        "1": ("fix `split_surface`", ""),
        "2": ("fix `PrismSplitter`", "no detector named"),
        "3": ("nothing", "nothing resolvable"),
    }
    out = cp.evaluate(db, prs, fetch=lambda n: issues[n], repo=tmp_path)
    assert "| #1 | #11 |" in out and "| 1/1 | 1/2 |" in out
    assert "| 1/2 | 1/2 |" in out  # issue 2 names prism.py only
    assert "| 0/1 | 0/1 |" in out
    assert "Pack names >=1 changed file: 2/3; >=1 changed source file: 2/3; every changed source file: 1/3." in out


def test_cli_requires_issue_or_eval(db, tmp_path):
    (tmp_path / "x.db").write_bytes(b"")
    with pytest.raises(SystemExit):
        cp.main(["--db", str(tmp_path / "x.db")])
