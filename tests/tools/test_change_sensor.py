# ruff: noqa: S101, S603, S607
"""`gitgalaxy change`: the diff parser, the repeated-rename rule, debt markers and the git-only report (no scan needed)."""

import subprocess
import sys
from pathlib import Path

from gitgalaxy.tools.sensors import change

REPO = Path(__file__).resolve().parents[2]


def _hunks(pairs, path="a.c"):
    return [(path, [x for x, _ in pairs], [y for _, y in pairs])]


def test_a_call_swapped_five_times_is_a_repeated_rename():
    pairs = [(f"  old_free(p{i});", f"  new_free(p{i});") for i in range(5)]
    assert change.repeated_renames(_hunks(pairs)) == {("old_free", "new_free"): 5}


def test_four_swaps_are_not_reported():
    pairs = [(f"  old_free(p{i});", f"  new_free(p{i});") for i in range(4)]
    assert change.repeated_renames(_hunks(pairs)) == {}


def test_comments_declarators_and_unequal_hunks_are_not_renames():
    comments = [(f"  // old_free(p{i})", f"  // new_free(p{i})") for i in range(6)]
    declarators = [(f"  int (*cb{i})(void);", f"  GIT_CALLBACK (*cb{i})(void);") for i in range(6)]
    assert change.repeated_renames(_hunks(comments)) == {}
    assert change.repeated_renames(_hunks(declarators)) == {}
    assert change.repeated_renames([("a.c", ["a(1);"] * 6, ["c(1);"] * 5)]) == {}


def test_markers_count_only_source_files():
    hunks = [("src/a.c", ["// TODO old"], ["// FIXME new", "x = 1;"]), ("tests/t.c", [], ["// TODO in a test"])]
    got = change.markers(hunks, {"src/a.c"})
    assert [t for _, t in got["added"]] == ["// FIXME new"]
    assert [t for _, t in got["removed"]] == ["// TODO old"]


def test_parse_diff_gives_new_side_ranges():
    text = "+++ b/a.c\n@@ -1,2 +10,3 @@\n-x\n+y\n+z\n+w\n"
    files, hunks, ranges = change.parse_diff(text)
    assert files == {"a.c": [3, 1]}
    assert ranges == {"a.c": [(10, 3)]}
    assert hunks[0][1] == ["x"]


def _git(tmp, *args):
    subprocess.run(["git", "-C", str(tmp), *args], check=True, capture_output=True)


def test_the_command_reports_a_real_commit(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    body = "".join(f"void f{i}(void) {{ old_free(p{i}); }}\n" for i in range(6))
    (tmp_path / "a.c").write_text(body + "/* nothing */\n")
    _git(tmp_path, "add", "a.c")
    _git(tmp_path, "commit", "-qm", "one")
    (tmp_path / "a.c").write_text(body.replace("old_free", "new_free") + "/* TODO later */\n")
    _git(tmp_path, "commit", "-qam", "two")
    out = subprocess.run(
        [sys.executable, "-m", "gitgalaxy.cli", "change", str(tmp_path)],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO,
    ).stdout
    assert "old_free -> new_free x6" in out
    assert "added 1, removed 0" in out
    assert "source: " in out


def test_touched_functions_come_from_the_scan(tmp_path):
    import sqlite3

    db = tmp_path / "s_galaxy_master.db"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE file_data(id INTEGER PRIMARY KEY, file_path TEXT);
        CREATE TABLE function_data(id INTEGER PRIMARY KEY, file_id INTEGER, func_name TEXT, start_line INTEGER, loc INTEGER);
        CREATE TABLE fcall_data(id INTEGER PRIMARY KEY, src_file_id INTEGER, src_func_id INTEGER, kind TEXT, dst_func_id INTEGER);
        INSERT INTO file_data VALUES (1,'a.c'),(2,'b.c');
        INSERT INTO function_data VALUES (10,1,'hit',5,10),(11,1,'miss',40,5),(12,2,'caller',1,3),(13,2,'outer',9,3);
        INSERT INTO fcall_data(src_file_id,src_func_id,kind,dst_func_id) VALUES (2,12,'call',10),(2,13,'call',12);
        """
    )
    con.commit()
    con.close()
    got = change.touched_functions(db, {"a.c": [(8, 2)]})
    assert got == [{"function": "hit", "file": "a.c", "caller_functions": 1, "caller_files": 1, "one_hop_out": 1}]
