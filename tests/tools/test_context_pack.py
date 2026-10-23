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
