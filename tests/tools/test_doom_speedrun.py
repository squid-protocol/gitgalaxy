"""DOOM Port Speedrun harness (#5468): manifest shape, scorer helpers, pinned-SHA fetch, the work-dir guard.

No network and no scan: the fetch test clones a throwaway local repo. Sibling tool dir goes on sys.path and the
modules are imported as bare names (tests/ has no __init__.py).
"""

import re
import stat
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "doom_speedrun"))

import doom_clang  # noqa: E402
import doom_scorer  # noqa: E402
import doom_speedrun  # noqa: E402


def test_manifest_is_39_pinned_unique_ports():
    rows = doom_speedrun.read_manifest()
    names = [r["name"] for r in rows]
    assert len(rows) == 39 and len(set(names)) == 39
    for r in rows:
        assert re.fullmatch(r"[0-9a-f]{40}", r["sha"]), r["name"]
        assert r["upstream"].startswith("https://github.com/"), r["name"]
        assert r["lineage"].strip(), r["name"]


def test_manifest_unknown_port_is_an_error():
    with pytest.raises(SystemExit, match="nope"):
        doom_speedrun.read_manifest(only=["linuxdoom", "nope"])


@pytest.mark.parametrize(
    ("gg", "ct", "ok"),
    [(0, 0, True), (5, 0, True), (103, 100, True), (104, 100, False), (97, 100, True), (96, 100, False)],
)
def test_functions_tolerance_is_a_scaled_bound(gg, ct, ok):
    assert doom_scorer.functions_ok(gg, ct) is ok


def test_verdict():
    assert doom_scorer.verdict([]) == "PERFECT"
    assert doom_scorer.verdict(["coverage", "health"]) == "4/6"


def test_log_problems_ignores_engine_wide_and_typosquat_lines():
    pad = "2026-10-18 00:00:00,000 - "  # the scorer drops the 24-char timestamp prefix
    log = "\n".join(
        [
            pad + "[ERROR] boom in x.c",
            pad + "[ERROR] XGBoost model missing",
            pad + "[ERROR] TYPOSQUATTING DETECTED: foo",
            pad + "CLASSIFICATION REFUTATION for y.c",
            "Traceback (most recent call last):",
            pad + "[INFO] fine",
        ]
    )
    assert len(doom_scorer.log_problems(log)) == 3


def test_language_misfits(tmp_path):
    (tmp_path / "a.h").write_text("int f(void);\n")
    (tmp_path / "b.h").write_text("@interface Foo\n@end\n")
    mapped = {
        "a.h": ("objective-c", 1),  # no ObjC syntax in a C header
        "b.h": ("objective-c", 2),
        "c.c": ("c", 3),
        "d.c": ("cpp", 4),
        "v/e.c": ("cpp", 5),  # vendored: not judged
    }
    bad = doom_scorer.language_misfits(mapped, tmp_path, lambda p: p.startswith("v/"))
    assert sorted(bad) == [("a.h", "objective-c"), ("d.c", "cpp")]


def test_treesitter_counts_c_and_macro_defined_function(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    (tmp_path / "x.c").write_text("int g(int a){return a;}\nstatic void h(void){}\n")
    (tmp_path / "y.c").write_text("CCMD(foo)\n{\n  return;\n}\nint k(void){return 1;}\n")
    counts = doom_scorer.treesitter_counts(tmp_path, {"c": ["x.c", "y.c"]})
    assert counts["x.c"] == 2
    assert counts["y.c"] >= 1  # the plain function; the macro-defined one is the oracle's own blind spot


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def test_fetch_port_checks_out_exactly_the_pinned_sha(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    _git(src, "init", "-q")
    _git(src, "config", "user.email", "t@example.com")
    _git(src, "config", "user.name", "t")
    _git(src, "config", "uploadpack.allowAnySHA1InWant", "true")
    (src / "a.c").write_text("int a(void){return 1;}\n")
    _git(src, "add", "a.c")
    _git(src, "commit", "-q", "-m", "one")
    pinned = subprocess.run(
        ["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    (src / "a.c").write_text("int a(void){return 2;}\n")
    _git(src, "commit", "-q", "-am", "two")
    repos = tmp_path / "repos"
    repos.mkdir()
    row = {"name": "p", "upstream": src.as_uri(), "sha": pinned}
    assert doom_speedrun.fetch_port(row, repos) is None
    assert (repos / "p" / "a.c").read_text() == "int a(void){return 1;}\n"
    assert doom_speedrun.fetch_port(row, repos) is None  # resumable: already at the SHA
    assert doom_speedrun.fetch_port({**row, "sha": "0" * 40}, repos) is not None


def test_rmtree_removes_read_only_files_and_a_missing_dir(tmp_path):
    """A git checkout's objects are read-only; Windows refused to delete them and fetch_port then hit FileExistsError."""
    tree = tmp_path / "p" / ".git" / "objects"
    tree.mkdir(parents=True)
    ro = tree / "pack.idx"
    ro.write_text("x")
    ro.chmod(stat.S_IREAD)
    doom_speedrun._rmtree(tmp_path / "p")
    assert not (tmp_path / "p").exists()
    doom_speedrun._rmtree(tmp_path / "p")  # already gone: no error


def test_work_dir_inside_repo_is_refused():
    with pytest.raises(SystemExit, match="outside the repo"):
        doom_speedrun.main(["fetch", "--only", "linuxdoom", "--work", str(doom_speedrun.REPO_ROOT / "scratch_doom")])


def test_clang_counts_macro_defined_function_and_skips_included_definitions(tmp_path):
    pytest.importorskip("clang.cindex")
    (tmp_path / "inc.h").write_text("static int from_header(void){return 0;}\n")
    (tmp_path / "x.c").write_text(
        '#define DEF(n) int n(void){return 1;}\nDEF(a)\nint b(void){return 2;}\nint proto(void);\n#include "inc.h"\n'
    )
    (tmp_path / "y.cpp").write_text(
        "struct S { int m() { return 1; } S() {} };\nnamespace n { int f() { return 2; } }\n"
    )
    res = doom_clang.clang_counts(tmp_path, ["x.c", "y.cpp", "notes.txt"])
    if res is None:
        pytest.skip("libclang shared library not loadable")
    counts, with_errors, from_db = res
    assert counts == {"x.c": 2, "y.cpp": 3}  # DEF(a) counted, the prototype and the header's function are not
    assert (with_errors, from_db) == (0, 0)


def test_clang_counts_without_libclang_is_none(tmp_path, monkeypatch):
    monkeypatch.setattr(doom_clang, "_index", lambda: (None, None))
    assert doom_clang.clang_counts(tmp_path, ["x.c"]) is None


def test_compile_commands_flags_are_keyed_by_real_path_without_compiler_or_output(tmp_path):
    (tmp_path / "a.c").write_text("")
    (tmp_path / "compile_commands.json").write_text(
        '[{"directory": "%s", "file": "a.c", "command": "cc -DX=1 -Iinc -c a.c -o a.o"}]' % tmp_path
    )
    assert doom_clang.compile_commands(tmp_path) == {str((tmp_path / "a.c").resolve()): ["-DX=1", "-Iinc"]}
    assert doom_clang.compile_commands(tmp_path / "nowhere") == {}


def test_clang_port_not_in_the_run_is_an_error(tmp_path):
    with pytest.raises(SystemExit, match="not in this run"):
        doom_speedrun.main(["score", "--only", "linuxdoom", "--clang", "gore", "--work", str(tmp_path)])


def _csv(path, rows):
    cols = ["variant", "fails", "gg_functions", "verdict"]
    path.write_text(
        ",".join(cols) + "\n" + "".join(",".join(r.get(c, "") for c in cols) + "\n" for r in rows), encoding="utf-8"
    )
    return path


def test_diff_reports_moves_and_regressions(tmp_path):
    import doom_diff

    old = _csv(
        tmp_path / "a.csv",
        [
            {"variant": "x", "fails": "coverage", "gg_functions": "10", "verdict": "5/6"},
            {"variant": "y", "fails": "", "gg_functions": "7", "verdict": "PERFECT"},
            {"variant": "gone", "fails": "", "gg_functions": "1", "verdict": "PERFECT"},
        ],
    )
    new = _csv(
        tmp_path / "b.csv",
        [
            {"variant": "x", "fails": "", "gg_functions": "12", "verdict": "PERFECT"},
            {"variant": "y", "fails": "health", "gg_functions": "7", "verdict": "5/6"},
            {"variant": "fresh", "fails": "", "gg_functions": "3", "verdict": "PERFECT"},
        ],
    )
    changes, added, removed = doom_diff.diff_rows(doom_diff.load(old), doom_diff.load(new))
    assert changes == {"x": {"fails": ("coverage", ""), "gg_functions": ("10", "12")}, "y": {"fails": ("", "health")}}
    assert (added, removed) == (["fresh"], ["gone"])
    assert doom_diff.regressions(doom_diff.load(old), doom_diff.load(new)) == [
        "y: new fail health",
        "gone: missing from the newer file",
    ]
    assert doom_diff.run(str(old), str(new), tmp_path, fail_on_regression=True) == 1
    assert doom_diff.run(str(old), str(old), tmp_path, fail_on_regression=True) == 0


def test_diff_resolves_dir_sha_and_round2(tmp_path, monkeypatch):
    import doom_diff

    (tmp_path / "results" / "abc123def").mkdir(parents=True)
    csv_path = _csv(tmp_path / "results" / "abc123def" / "clean_check.csv", [{"variant": "x"}])
    assert doom_diff.resolve_csv("abc123def", tmp_path) == csv_path
    assert doom_diff.resolve_csv(str(csv_path.parent), tmp_path) == csv_path
    monkeypatch.setattr(doom_diff, "ROUND2_CSV", csv_path)
    assert doom_diff.resolve_csv("round2", tmp_path) == csv_path
    with pytest.raises(SystemExit, match="nope"):
        doom_diff.resolve_csv("nope", tmp_path)


def test_diff_compares_only_columns_both_files_have(tmp_path):
    import doom_diff

    old = {"x": {"variant": "x", "fails": "", "gg_functions": "1"}}  # a round-2 style file: no treesitter columns
    new = {"x": {"variant": "x", "fails": "", "gg_functions": "1", "treesitter_functions": "9"}}
    assert doom_diff.diff_rows(old, new)[0] == {}
