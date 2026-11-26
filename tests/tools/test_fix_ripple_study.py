"""fix_ripple_study (#8958): a synthetic repository with known fix commits and a known call graph. No corpus, no galaxyscope run."""

import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fix_ripple_study as frs

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")

C0 = "int a(int x) {\n  return b(x) + 1;\n}\n\nint b(int x) {\n  return x;\n}\n\nint c(int x) {\n  return x * 2;\n}\n"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.com",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "r"
    r.mkdir()
    _git(r, "init", "-q")
    (r / "m.c").write_text(C0, encoding="utf-8")
    _git(r, "add", "m.c")
    _git(r, "commit", "-q", "-m", "initial import", "--date=2023-01-01T00:00:00")
    # a fix touching a(): def B and orig and D
    (r / "m.c").write_text(C0.replace("b(x) + 1", "b(x) + 2"), encoding="utf-8")
    _git(r, "commit", "-qam", "fix off by one in a", "--date=2023-02-01T00:00:00")
    # a memory fix touching c(): orig and D, NOT B (memory word)
    (r / "m.c").write_text(C0.replace("b(x) + 1", "b(x) + 2").replace("x * 2", "x * 3"), encoding="utf-8")
    _git(r, "commit", "-qam", "fix heap overflow in c", "--date=2023-03-01T00:00:00")
    return r


def test_fix_definitions():
    assert frs.fix_flags("fix off by one") == {"orig": True, "B": True, "D": True}
    assert frs.fix_flags("fix heap overflow") == {"orig": True, "B": False, "D": True}
    assert frs.fix_flags("add feature") == {"orig": False, "B": False, "D": True}


def test_hunk_name_is_c_only():
    assert frs.hunk_name("static int foo(int a)") == "foo"
    assert frs.hunk_name("func (r *T) name(x int)") == "func"  # why Go and Java need their own rule


def test_mining_counts_commits_per_function(repo: Path):
    t = frs.mine_touches(repo, since="2000-01-01")
    assert t["B"] == {("m.c", "a"): 1}
    assert t["orig"] == {("m.c", "a"): 1, ("m.c", "c"): 1}
    assert t["D"][("m.c", "a")] == 1 and t["D"][("m.c", "c")] == 1


def _db(path: Path, funcs: list[tuple], edges: list[tuple]) -> Path:
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE file_data (id INTEGER PRIMARY KEY, file_path TEXT)")
    con.execute(
        "CREATE TABLE function_data (id INTEGER PRIMARY KEY, file_id INT, func_name TEXT, complexity INT, loc INT)"
    )
    con.execute("CREATE TABLE fcall_data (id INTEGER PRIMARY KEY, src_func_id INT, dst_func_id INT, step TEXT)")
    con.execute("INSERT INTO file_data VALUES (1, '/scan/m.c')")
    con.executemany("INSERT INTO function_data VALUES (?,1,?,?,?)", funcs)
    con.executemany("INSERT INTO fcall_data (src_func_id, dst_func_id, step) VALUES (?,?,?)", edges)
    con.commit()
    con.close()
    return path


def test_graph_counts_and_attribution(repo: Path, tmp_path: Path):
    db = _db(
        tmp_path / "g.db",
        [(1, "a", 2, 3), (2, "b", 1, 3), (3, "c", 1, 3)],
        [(1, 2, "unique"), (1, 2, "unique"), (1, 1, "unique"), (3, 2, "tie"), (3, 2, "file")],
    )
    funcs = frs.attach(frs.load_graph(db, "/scan"), frs.mine_touches(repo, since="2000-01-01"))
    by = {f["name"]: f for f in funcs}
    assert (by["a"]["fan_out"], by["a"]["fan_in"]) == (1, 0)  # duplicate edge once, self-call dropped
    assert (by["b"]["fan_in"], by["c"]["fan_out"]) == (2, 1)  # the `tie` row is not an edge
    assert [by[n]["t_B"] for n in "abc"] == [1, 0, 0]
    assert [by[n]["t_orig"] for n in "abc"] == [1, 0, 1]


def test_ambiguous_names_are_dropped():
    funcs = [{"path": "x.c", "name": "f", "loc": 1, "cx": 1, "fan_in": 0, "fan_out": 0}] * 2
    assert frs.attach([dict(f) for f in funcs], {d: {("x.c", "f"): 3} for d in frs.DEFS}) == []


def test_poisson_fit_matches_observed_total_and_lift_by_hand():
    funcs = [
        {
            "path": "p",
            "name": f"f{i}",
            "loc": 10 * (i + 1),
            "cx": 1 + i,
            "fan_in": 0,
            "fan_out": 9 if i < 2 else 0,
            "t_B": t,
        }
        for i, t in enumerate([2, 3, 1, 0, 1, 1])
    ]
    pred = frs.poisson_predict(funcs, "t_B")
    assert abs(sum(pred) - 8) < 1e-5  # intercept score equation: predicted total == observed total
    per = frs.repo_pairs(funcs, "B")
    obs = sum(o for o, _ in per["orchestrator"])
    assert obs == 5
    assert abs(frs._lift(per["orchestrator"]) - 5 / (pred[0] + pred[1])) < 1e-9


def test_groups():
    g = lambda i, o, name="f": frs.groups({"fan_in": i, "fan_out": o, "name": name})
    assert g(7, 8) == ["orchestrator"]
    assert "orchestrator" not in g(8, 8)
    assert g(1, 20) == ["orchestrator", "consumer"]
    assert g(20, 1) == ["producer"]
    assert g(9, 1, "x_free") == ["lifecycle", "producer"]
    assert g(0, 0) == []


def test_partial_spearman_sign():
    n = 30
    loc = list(range(n))
    x = [float(i % 7) for i in range(n)]
    assert frs.partial_spearman(x, x, loc, loc) > 0.99
    assert frs.partial_spearman(x, [-v for v in x], loc, loc) < -0.99


def test_summary_is_deterministic_and_checkable(tmp_path: Path):
    funcs = [
        {
            "path": "p",
            "name": f"f{i}",
            "loc": 5 + i,
            "cx": 1 + i % 4,
            "fan_in": i % 3,
            "fan_out": 10 if i % 5 == 0 else i % 2,
            "t_orig": i % 3,
            "t_B": i % 2,
            "t_D": i % 4,
        }
        for i in range(60)
    ]
    one = json.dumps(frs.summarize({"r": [dict(f) for f in funcs]}), sort_keys=True)
    two = json.dumps(frs.summarize({"r": [dict(f) for f in funcs]}), sort_keys=True)
    assert one == two  # byte-identical rerun
    res = tmp_path / "res.json"
    res.write_text(one, encoding="utf-8")
    exp = tmp_path / "exp.json"
    exp.write_text(json.dumps({"H3": {"positive_repos": 99, "of": 1, "verdict": "pass"}}), encoding="utf-8")
    assert frs.main(["check", str(res), "--expected", str(exp)]) == 1  # a changed verdict fails loudly
    exp.write_text(json.dumps({"H3": json.loads(one)["verdicts"]["H3"]}), encoding="utf-8")
    assert frs.main(["check", str(res), "--expected", str(exp)]) == 0


def test_drop_noise_is_a_copy_and_reports_what_it_removed(tmp_path: Path):
    src = tmp_path / "src"
    for d in ("lib", "tests", "docs", "vendor/x"):
        (src / d).mkdir(parents=True)
        (src / d / "f.c").write_text("int f(void){return 0;}\n", encoding="utf-8")
    (src / ".git").mkdir()
    removed = frs.drop_noise_copy(src, tmp_path / "copy")
    assert removed == ["docs", "tests", "vendor"]
    assert (tmp_path / "copy" / "lib" / "f.c").exists() and not (tmp_path / "copy" / "tests").exists()
    assert (src / "tests" / "f.c").exists()  # the original is untouched
