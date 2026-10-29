"""#6278 item 5: the per-test coverage map -- build from coverage.py's SQLite data, select conservatively."""

import sqlite3
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import coverage_map as cm  # noqa: E402


def make_data(path: Path, rows: list[tuple[str, str]], table: str = "line_bits") -> None:
    """A coverage.py-shaped database: one (file, context) row per file a context executed."""
    con = sqlite3.connect(path)
    con.execute("create table file (id integer primary key, path text)")
    con.execute("create table context (id integer primary key, context text)")
    cols = "file_id integer, context_id integer, " + ("numbits blob" if table == "line_bits" else "fromno integer")
    con.execute(f"create table {table} ({cols})")
    for f, c in rows:
        fid = con.execute("select id from file where path=?", (f,)).fetchone()
        fid = fid[0] if fid else con.execute("insert into file(path) values (?)", (f,)).lastrowid
        cid = con.execute("select id from context where context=?", (c,)).fetchone()
        cid = cid[0] if cid else con.execute("insert into context(context) values (?)", (c,)).lastrowid
        con.execute(f"insert into {table} values (?, ?, 0)", (fid, cid))
    con.commit()
    con.close()


def tree(root: Path, tests: list[str]) -> None:
    for t in tests:
        (root / t).parent.mkdir(parents=True, exist_ok=True)
        (root / t).write_text("def test_x():\n    pass\n", encoding="utf-8")


def test_test_file_of_reads_the_pytest_context():
    assert cm.test_file_of("tests/a/test_x.py::test_y|run") == "tests/a/test_x.py"
    assert cm.test_file_of("tests/a/test_x.py::T::test_y|setup") == "tests/a/test_x.py"
    assert cm.test_file_of("") is None
    assert cm.test_file_of("|run") is None


def test_build_maps_each_engine_module_to_the_test_files_that_ran_it(tmp_path):
    tree(tmp_path, ["tests/a/test_one.py", "tests/b/test_two.py"])
    for table in ("line_bits", "arc"):
        db = tmp_path / f"cov_{table}"
        make_data(
            db,
            [
                (str(tmp_path / "gitgalaxy/core/prism.py"), "tests/a/test_one.py::test_p|run"),
                ("gitgalaxy/core/prism.py", "tests/b/test_two.py::test_q|run"),
                ("gitgalaxy/consts.py", ""),  # import time only
                ("tests/a/test_one.py", "tests/a/test_one.py::test_p|run"),  # not an engine file
            ],
            table,
        )
        m = cm.build(db, tmp_path)
        assert m["modules"] == {
            "gitgalaxy/core/prism.py": ["tests/a/test_one.py", "tests/b/test_two.py"],
            "gitgalaxy/consts.py": [],
        }
        assert m["tests"] == 2


def test_the_engine_tree_readers_are_always_run(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_walk.py").write_text(
        'for p in ROOT.rglob("*.py"):\n    open("gitgalaxy/x")\n', encoding="utf-8"
    )
    (tmp_path / "tests/test_plain.py").write_text('def test_a():\n    assert open("gitgalaxy/x")\n', encoding="utf-8")
    assert cm.engine_tree_readers(tmp_path) == ["tests/test_walk.py"]


MAP = {
    "version": cm.VERSION,
    "tests": 10,
    "always": ["tests/test_walk.py"],
    "modules": {
        "gitgalaxy/a.py": ["tests/test_a.py"],
        "gitgalaxy/b.py": ["tests/test_b.py"],
        "gitgalaxy/consts.py": [],
        "gitgalaxy/spine.py": [f"tests/test_s{i}.py" for i in range(5)],
    },
}


def test_select_unions_the_covering_tests_and_the_tree_readers(tmp_path):
    tree(tmp_path, ["tests/test_a.py", "tests/test_b.py", "tests/test_walk.py"])
    tests, why = cm.select(["gitgalaxy/a.py", "gitgalaxy/b.py"], MAP, tmp_path)
    assert tests == ["tests/test_a.py", "tests/test_b.py", "tests/test_walk.py"], why


def test_select_is_full_when_it_cannot_prove_the_reach(tmp_path):
    tree(tmp_path, ["tests/test_a.py"])
    for files, cmap in [
        (["gitgalaxy/a.py"], None),  # no map
        (["gitgalaxy/new.py"], MAP),  # a module the map lacks
        (["gitgalaxy/a.py", "gitgalaxy/new.py"], MAP),  # one unmapped file among mapped ones
        (["gitgalaxy/consts.py"], MAP),  # import-time lines only
        (["gitgalaxy/spine.py"], MAP),  # more than MAX_SHARE of the tests
    ]:
        tests, why = cm.select(files, cmap, tmp_path)
        assert tests is None and why, files


def test_load_rejects_a_missing_or_foreign_map(tmp_path):
    assert cm.load(tmp_path / "none.json") is None
    (tmp_path / "bad.json").write_text("{", encoding="utf-8")
    assert cm.load(tmp_path / "bad.json") is None
    (tmp_path / "old.json").write_text('{"version": 0}', encoding="utf-8")
    assert cm.load(tmp_path / "old.json") is None
    (tmp_path / "ok.json").write_text(f'{{"version": {cm.VERSION}}}', encoding="utf-8")
    assert cm.load(tmp_path / "ok.json") == {"version": cm.VERSION}
