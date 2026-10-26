"""DOOM Port Speedrun harness (#5468): manifest shape, scorer helpers, pinned-SHA fetch, the work-dir guard.

No network and no scan: the fetch test clones a throwaway local repo. Sibling tool dir goes on sys.path and the
modules are imported as bare names (tests/ has no __init__.py).
"""

import collections
import json
import sqlite3
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


def test_manifest_is_pinned_unique_licensed_ports():
    # #5619: only clearly licensed ports, each with the license read from its files and a class
    rows = doom_speedrun.read_manifest()
    names = [r["name"] for r in rows]
    assert len(rows) == 44 and len(set(names)) == len(names)
    for r in rows:
        assert re.fullmatch(r"[0-9a-f]{40}", r["sha"]), r["name"]
        assert r["upstream"].startswith("https://github.com/"), r["name"]
        assert r["lineage"].strip(), r["name"]
        assert re.match(r"(GPL-[23]\.0|MIT|Apache-2\.0|BSD-3-Clause)\b", r["license"]), r["name"]
        assert r["class"] in {"engine-port", "reimplementation", "raycaster", "separate-engine", "assets"}, r["name"]


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
    # json.dumps, not %-interpolation: a Windows path's backslashes are invalid JSON escapes (main red, #5546)
    entry = {"directory": str(tmp_path), "file": "a.c", "command": "cc -DX=1 -Iinc -c a.c -o a.o"}
    (tmp_path / "compile_commands.json").write_text(json.dumps([entry]))
    assert doom_clang.compile_commands(tmp_path) == {str((tmp_path / "a.c").resolve()): ["-DX=1", "-Iinc"]}
    assert doom_clang.compile_commands(tmp_path / "nowhere") == {}


def test_compile_commands_arguments_form_and_malformed_file(tmp_path):
    (tmp_path / "compile_commands.json").write_text(
        json.dumps([{"directory": str(tmp_path), "file": "a.c", "arguments": ["cc", "-DY", "-o", "a.o", "-c", "a.c"]}])
    )
    assert doom_clang.compile_commands(tmp_path) == {str((tmp_path / "a.c").resolve()): ["-DY"]}
    (tmp_path / "compile_commands.json").write_text("[{not json")
    assert doom_clang.compile_commands(tmp_path) == {}


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


@pytest.mark.parametrize(
    "rel, text, category",
    [
        ("docs/examples/demo.py", "", "docs-tree"),
        ("src/doc/gen.js", "", "docs-tree"),
        ("__MACOSX/src/._main.c", "", "appledouble"),
        ("src/._main.c", "", "appledouble"),
        ("engine/third_party/lib/x.c", "", "third-party"),
        ("engine/thirdparty/x.c", "", "third-party"),
        ("engine/3rdparty/x.c", "", "third-party"),
        ("src/parser.cc", "/* Generated by re2c 3.0 on Mon */", "generated-parser"),
        ("src/gram.c", "/* A Bison parser, made by GNU Bison */\n/* Generated by bison 3.8 */", "generated-parser"),
        ("src/main.c", "int main(void) { return 0; }", None),
        ("src/documents.c", "", None),  # a file name is not a docs directory
        ("src/parser.cc", "/* hand written */", None),
        ("tools/re2c/parser.cc", "/* A Bison parser, made by GNU Bison 2.3.  */", "generated-signature"),
        ("gameplay/src/info.rs", "//! THIS FILE IS GENERATED WITH MULTIGEN\n//! @generated\n", "generated-signature"),
        ("src/info.rs", "// the @generated tag is mentioned in prose only\nfn f() {}", None),
        ("doomsday/build/scripts/unify.py", "import os", "tooling-dir"),
        ("web/site/webplayer.py", "import os", "tooling-dir"),
        ("src/build/tools.py", "import os", None),  # build/ alone is not tooling
        ("src/site/a.py", "import os", None),
    ],
)
def test_by_design_reason_classes(rel, text, category):
    hit = doom_scorer.by_design_reason(rel, text)
    assert (hit[0] if hit else None) == category


def test_posix_rel_turns_windows_separators_into_slashes(tmp_path):
    # Windows os.path.relpath gives "src\\a.c"; the DB keys and by_design_reason need "src/a.c" (#5595)
    rel = doom_scorer.posix_rel(str(tmp_path / "docs" / "a.py"), tmp_path)
    assert rel == "docs/a.py"
    assert doom_scorer.by_design_reason(doom_scorer.posix_rel("docs\\a.py", ".", sep="\\"), "")[0] == "docs-tree"


def _stub_ctags_counts(repo, files_by_lang, scratch):
    return collections.Counter({"src/main.c": 1, "src/lost.c": 1})


def test_score_port_scores_by_design_exclusions_with_a_reason(tmp_path, monkeypatch):
    # CI has no Universal Ctags: stub the oracle (one definition in each C file)
    monkeypatch.setattr(doom_scorer, "ctags_counts", _stub_ctags_counts)
    repo, scan = tmp_path / "repo", tmp_path / "scan"
    files = {
        "src/main.c": "int main(void) { return 0; }\n",
        "docs/ex.py": "def f():\n    pass\n",
        "__MACOSX/._main.c": "junk\n",
        "src/parser.cc": "/* Generated by re2c 3.0 */\nint x;\n",
        "src/lost.c": "int lost(void) { return 1; }\n",
    }
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text)
    scan.mkdir()
    (scan / "rc.txt").write_text("0\n")
    con = sqlite3.connect(scan / "p_galaxy_master.db")
    con.executescript(
        "create table file_data (id integer primary key, file_path text, language text, has_credentials int);"
        "create table function_data (id integer primary key, file_id int, func_name text, start_line int, calls_out_to text);"
        "create table excluded_artifacts (file_path text, exclusion_reason text);"
        "insert into file_data values (1, 'src/main.c', 'c', 0);"
        "insert into function_data values (1, 1, 'main', 1, '[]');"
        "insert into excluded_artifacts values ('docs/ex.py', 'Doc Surface');"
    )
    con.commit()
    con.close()
    row, det = doom_scorer.score_port("p", repo, scan, tmp_path)
    assert row["excluded_by_design"] == 3  # docs, AppleDouble, re2c parser
    assert row["excluded_by_design_reasons"] == "appledouble:1 docs-tree:1 generated-parser:1"
    assert [m[0] for m in det["missed"]] == ["src/lost.c"]  # a real miss still counts
    assert row["missed_src"] == 1
    assert "coverage" in row["fails"]
    assert all("engine:" in why for _, _, why in det["excluded_by_design"])
    assert "docs/ex.py" not in [m[0] for m in det["missed"]]


@pytest.mark.parametrize(
    ("gg", "ct", "ts", "who"),
    [
        (100, 101, None, "ctags"),
        (100, 120, 101, "tree-sitter"),
        (100, 120, 130, ""),
        (100, 120, None, ""),
        (100, 0, None, "ctags"),
    ],
)
def test_functions_agreement_names_the_oracle_that_passes(gg, ct, ts, who):
    assert doom_scorer.functions_agreement(gg, ct, ts) == who


# Manifest languages check 1 does not score: data/markup/build files, and SQL and JCL (own extension policy).
_SRC_EXT_EXEMPT = {
    "sql": "data-like .sql files", "jcl": "job streams, mainframe estate checks", "makefile": "no extension",
    "m4": "build glue", "css": "markup", "json": "data", "yaml": "data", "markdown": "docs", "plaintext": "docs",
}  # fmt: skip


def test_src_ext_covers_every_code_language_the_ports_use():
    # #6097: check 1 only walks SRC_EXT files, so a language missing from it (Fortran, Crystal, F#, COBOL) made
    # the coverage check vacuous for that port. Derived from the manifest, not a hand list.
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    langs = {lang for r in doom_speedrun.read_manifest() for lang in r["languages"].split()}
    code = {lang for lang in langs if lang in LANGUAGE_DEFINITIONS and lang not in _SRC_EXT_EXEMPT}
    for must in ("fortran", "crystal", "fsharp", "cobol", "dart", "scheme"):
        assert must in code
    uncovered = {
        lang for lang in code if not set(LANGUAGE_DEFINITIONS[lang].get("extensions") or ()) & doom_scorer.SRC_EXT
    }
    assert not uncovered, f"no SRC_EXT extension for {sorted(uncovered)}"
    for ext in (".f90", ".cr", ".fs", ".cbl", ".cob", ".cpy", ".dart", ".scm", ".rb"):
        assert ext in doom_scorer.SRC_EXT
