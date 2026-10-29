"""#6278 item 5: the per-test coverage map -- build from coverage.py's SQLite data, select conservatively."""

import datetime as dt
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


NOW = dt.datetime(2026, 10, 29, 12, tzinfo=dt.timezone.utc)
MAP = {
    "version": cm.VERSION,
    "built_at": NOW.isoformat(),
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
    tests, why = cm.select(["gitgalaxy/a.py", "gitgalaxy/b.py"], MAP, tmp_path, NOW)
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
        tests, why = cm.select(files, cmap, tmp_path, NOW)
        assert tests is None and why, files


def test_select_is_full_when_the_map_is_stale_unstamped_or_from_the_future(tmp_path):
    tree(tmp_path, ["tests/test_a.py"])
    day = dt.timedelta(days=1)
    edge = cm.MAX_AGE_DAYS * day
    for built in (NOW, NOW - edge):  # up to the limit still selects
        tests, why = cm.select(["gitgalaxy/a.py"], {**MAP, "built_at": built.isoformat()}, tmp_path, NOW)
        assert tests is not None, why
    stale = {**MAP, "built_at": (NOW - edge - dt.timedelta(seconds=1)).isoformat()}
    unstamped = {k: v for k, v in MAP.items() if k != "built_at"}
    for cmap in (
        stale,
        unstamped,
        {**MAP, "built_at": "yesterday"},
        {**MAP, "built_at": None},
        {**MAP, "built_at": (NOW + day).isoformat()},
    ):
        tests, why = cm.select(["gitgalaxy/a.py"], cmap, tmp_path, NOW)
        assert tests is None and why, cmap.get("built_at")
    naive = {**MAP, "built_at": NOW.replace(tzinfo=None).isoformat()}  # no zone: read as UTC
    assert cm.select(["gitgalaxy/a.py"], naive, tmp_path, NOW)[0] is not None


def test_build_stamps_the_map_with_the_build_time(tmp_path):
    data = tmp_path / ".coverage"
    make_data(data, [("gitgalaxy/a.py", "tests/test_a.py::t|run")])
    (tmp_path / "tests").mkdir()
    m = cm.build(data, tmp_path)
    assert cm.map_age_problem(m) is None


def test_load_rejects_a_missing_or_foreign_map(tmp_path):
    assert cm.load(tmp_path / "none.json") is None
    (tmp_path / "bad.json").write_text("{", encoding="utf-8")
    assert cm.load(tmp_path / "bad.json") is None
    (tmp_path / "old.json").write_text('{"version": 0}', encoding="utf-8")
    assert cm.load(tmp_path / "old.json") is None
    (tmp_path / "ok.json").write_text(f'{{"version": {cm.VERSION}}}', encoding="utf-8")
    assert cm.load(tmp_path / "ok.json") == {"version": cm.VERSION}


# --- the nightly wiring (#6278 item 5): the writer and the reader of the map must agree on key and file name
ROOT = TOOLS.parents[1]
MAP_WORKFLOW = (ROOT / ".github" / "workflows" / "engine-coverage-map.yml").read_text(encoding="utf-8")
SMOKE = (ROOT / ".github" / "workflows" / "smoke-test.yml").read_text(encoding="utf-8")


def test_the_map_workflow_is_nightly_only_and_builds_the_default_map():
    head = MAP_WORKFLOW.split("jobs:", 1)[0]
    assert "schedule:" in head and "workflow_dispatch:" in head
    assert "pull_request" not in head  # no PR waits on an instrumented run
    assert "--cov=gitgalaxy --cov-context=test" in MAP_WORKFLOW
    assert "coverage_map.py build --data .coverage --out engine-map-cache/engine_test_map.json" in MAP_WORKFLOW


def test_smoke_restores_what_the_map_workflow_saves():
    assert "key: engine-test-map-${{ github.run_id }}" in MAP_WORKFLOW
    assert "engine-test-map-\n" in SMOKE.split("Restore the newest coverage map", 1)[1].split("Plan the suite", 1)[0]
    assert "--coverage-map engine-map-cache/engine_test_map.json" in SMOKE


def test_the_smoke_nightly_stays_uninstrumented():
    # coverage overhead would inflate the per-test times the suite budget (+10% fails) and the durations cache are built from
    assert "--cov=" not in SMOKE and "--cov-context" not in SMOKE


def test_ci_pins_pytest_cov_with_hashes():
    pins = (ROOT / "ci" / "requirements" / "test.txt").read_text(encoding="utf-8")
    assert "pytest-cov==" in pins and "\ncoverage==" in pins
    assert "pytest-cov" in (ROOT / "ci" / "requirements" / "pytest.in").read_text(encoding="utf-8")
