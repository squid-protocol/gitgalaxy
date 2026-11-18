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
    funcs = [(10, 1, "hit", 5, 10, 1), (11, 1, "miss", 40, 5, 0), (12, 2, "caller", 1, 3, 0), (13, 2, "outer", 9, 3, 0)]
    db = _scan_db(tmp_path / "s_galaxy_master.db", funcs, [(2, 12, 10), (2, 13, 12)])
    got = change.touched_functions(db, {"a.c": [(8, 2)]})
    assert got == [
        {
            "function": "hit",
            "file": "a.c",
            "caller_functions": 1,
            "caller_files": 1,
            "one_hop_out": 1,
            "signature_changed": None,
            "callers": [],
        }
    ]


def _scan_db(path, funcs, edges=(), markers=None):
    """A scan database with the real column names: funcs = [(id, file_id, name, start_line, loc, args)]."""
    import sqlite3

    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE file_data(id INTEGER PRIMARY KEY, file_path TEXT);
        CREATE TABLE function_data(id INTEGER PRIMARY KEY, file_id INTEGER, func_name TEXT, start_line INTEGER, loc INTEGER, args INTEGER);
        CREATE TABLE fcall_data(id INTEGER PRIMARY KEY, src_file_id INTEGER, src_func_id INTEGER, kind TEXT, dst_func_id INTEGER);
        INSERT INTO file_data VALUES (1,'a.c'),(2,'b.c');
        """
    )
    con.executemany("INSERT INTO function_data VALUES (?,?,?,?,?,?)", funcs)
    con.executemany("INSERT INTO fcall_data(src_file_id,src_func_id,kind,dst_func_id) VALUES (?,?,'call',?)", edges)
    if markers is not None:
        con.execute(
            "CREATE TABLE debt_marker(id INTEGER PRIMARY KEY, file_id INTEGER, line INTEGER, class TEXT, text TEXT)"
        )
        con.executemany("INSERT INTO debt_marker(file_id,line,class,text) VALUES (?,?,?,?)", markers)
    con.commit()
    con.close()
    return path


def test_a_changed_parameter_count_comes_first_with_its_callers(tmp_path):
    funcs = [
        (10, 1, "hot", 5, 10, 3),
        (11, 1, "plain", 20, 10, 1),
        (12, 2, "user_one", 1, 3, 0),
        (13, 2, "user_two", 6, 3, 0),
    ]
    edges = [
        (2, 12, 10),
        (2, 13, 10),
        (2, 12, 11),
        (2, 13, 11),
        (2, 13, 12),
    ]
    now = _scan_db(tmp_path / "now.db", funcs, edges)
    before = _scan_db(tmp_path / "base.db", [(10, 1, "hot", 5, 10, 2), (11, 1, "plain", 20, 10, 1)])
    got = change.touched_functions(now, {"a.c": [(6, 2), (22, 1)]}, before)
    assert [r["function"] for r in got] == ["hot", "plain"]
    assert got[0]["signature_changed"] == "parameters 2 -> 3"
    assert got[0]["callers"] == ["user_one (b.c)", "user_two (b.c)"]
    assert got[1]["signature_changed"] is None
    assert got[1]["callers"] == []


def test_without_a_base_scan_a_hunk_on_the_declaration_line_is_flagged(tmp_path):
    funcs = [(10, 1, "decl", 5, 10, 3), (11, 1, "body", 20, 10, 1)]
    now = _scan_db(tmp_path / "now.db", funcs)
    got = {r["function"]: r for r in change.touched_functions(now, {"a.c": [(5, 1), (25, 1)]})}
    assert got["decl"]["signature_changed"] == "declaration line edited"
    assert got["body"]["signature_changed"] is None


def _git_commit(tmp, who, text, message):
    import os

    env = {**os.environ, "GIT_AUTHOR_DATE": "1700000000 +0000", "GIT_COMMITTER_DATE": "1700000000 +0000"}
    (tmp / "a.c").write_text(text)
    subprocess.run(["git", "-C", str(tmp), "add", "a.c"], check=True, capture_output=True, env=env)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp),
            "-c",
            f"user.name={who}",
            "-c",
            f"user.email={who}@example.com",
            "commit",
            "-qm",
            message,
        ],
        check=True,
        capture_output=True,
        env=env,
    )


def test_while_you_are_here_lists_old_markers_and_not_the_ones_this_change_wrote(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    old = "int a;\n// TODO: old note\n" + "int b;\n" * 10
    _git_commit(tmp_path, "ann", old, "one")
    new = old + "".join(f"int c{i};\n" for i in range(60)) + "// FIXME: brand new\n"
    _git_commit(tmp_path, "bob", new, "two")
    lines = new.splitlines()
    fixme = lines.index("// FIXME: brand new") + 1
    db = _scan_db(
        tmp_path / "s.db",
        [(10, 1, "f", 1, 5, 0)],
        markers=[(1, 2, "planned", "// TODO: old note"), (1, fixme, "fragile", "// FIXME: brand new")],
    )
    rev = change._git(tmp_path, "rev-parse", "HEAD").strip()
    got = change.while_you_are_here(tmp_path, rev, db, source_lines=60, files={"a.c"})
    assert got["offered"] and got["measured"]
    assert [m["text"] for m in got["markers"]] == ["// TODO: old note"]  # the FIXME was written by this change
    assert got["markers"][0]["by_author"] is False
    assert got["markers"][0]["age_years"] == 0.0  # both commits carry the same fixed date


def test_while_you_are_here_waits_for_a_large_change_and_a_scan_with_markers(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    _git_commit(tmp_path, "ann", "int a;\n", "one")
    rev = change._git(tmp_path, "rev-parse", "HEAD").strip()
    with_markers = _scan_db(tmp_path / "m.db", [(10, 1, "f", 1, 1, 0)], markers=[])
    assert change.while_you_are_here(tmp_path, rev, with_markers, 10, {"a.c"})["offered"] is False
    without = _scan_db(tmp_path / "n.db", [(10, 1, "f", 1, 1, 0)])
    assert change.while_you_are_here(tmp_path, rev, without, 500, {"a.c"})["measured"] is False
