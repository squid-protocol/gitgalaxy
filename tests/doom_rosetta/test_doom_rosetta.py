"""DOOM-rosetta (#5619): zero drift of the pinned DOOM ports against ``tests/golden_doom_rosetta``.

Opt-in: ``pytest -m doom_rosetta`` fetches each port at its manifest SHA (never committed), rescans it with the
engine and diffs the measurements against the golden; a failure names the port, the file and the field. Bless with
``tests/tools/doom_rosetta_check.py --update --yes``. ``DOOM_ROSETTA_PORTS=a,b`` narrows the run (the CI shards),
``DOOM_SPEEDRUN_WORK`` moves the clone cache (outside the repo). It skips itself unless the marker expression selects
it, because ``smoke-test.yml`` replaces ``addopts`` with its own ``-m`` and would otherwise run all of it.
The unmarked tests at the bottom are fast and always run.
"""

import ast
import fnmatch
import json
import os
import re
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "doom_speedrun"))
import doom_rosetta_check as check  # noqa: E402
import doom_scorer  # noqa: E402
import doom_speedrun  # noqa: E402

PORTS = doom_speedrun.read_manifest()
NAMES = [r["name"] for r in PORTS]
ONLY = [n for n in os.environ.get("DOOM_ROSETTA_PORTS", "").split(",") if n]


def _selected(config):
    expr = config.getoption("markexpr", "") or ""
    return "doom_rosetta" in expr and "not doom_rosetta" not in expr


@pytest.mark.doom_rosetta
@pytest.mark.parametrize("row", [r for r in PORTS if not ONLY or r["name"] in ONLY], ids=lambda r: r["name"])
def test_port_matches_golden(row, request):
    if not _selected(request.config):
        pytest.skip("opt-in: run with `pytest -m doom_rosetta`")
    assert shutil.which("ctags"), "Universal Ctags is required on PATH (the functions check)"
    work = Path(os.environ.get("DOOM_SPEEDRUN_WORK", doom_speedrun.DEFAULT_WORK))
    report, golden = check.check_port(row, work)
    assert not report, f"\n{report}\n(bless an intended change with tests/tools/doom_rosetta_check.py --update --yes)"
    assert golden["summary"]["expected_fails_met"], (
        f"{row['name']} fails {golden['summary']['fails']!r}, the manifest expects {row['expected_fails']!r}"
    )


def test_every_manifest_port_has_a_golden_and_no_other_does():
    on_disk = {p.name.removesuffix(".json.gz") for p in check.GOLDEN_DIR.glob("*.json.gz")}
    assert on_disk == set(NAMES)


TOOLS = Path(__file__).resolve().parents[1] / "tools"
WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "doom-rosetta.yml"


def _reached_tool_modules():
    """Every tests/tools module this file reaches through imports, lazy (in-function) ones included, as repo paths."""
    seen, todo = set(), [Path(__file__).resolve()]
    while todo:
        tree = ast.parse(todo.pop().read_text())
        names = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        names |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module and not n.level}
        for name in names:
            for d in (TOOLS, TOOLS / "doom_speedrun"):
                path = d / f"{name}.py"
                if path.is_file() and path not in seen:
                    seen.add(path)
                    todo.append(path)
    return {p.relative_to(WORKFLOW.parents[2]).as_posix() for p in seen}


def test_workflow_paths_cover_the_check_imports():
    # doom-rosetta.yml lists the check's own tool modules, not all of tests/tools/doom_speedrun/: a module the check
    # imports that the list misses would let a PR change it without running the check
    block = WORKFLOW.read_text().split("    paths:\n", 1)[1].split("  schedule:", 1)[0]
    globs = [g for g in re.findall(r'^\s+- "([^"]+)"', block, re.M) if not g.startswith("!")]
    reached = _reached_tool_modules()
    assert {"tests/tools/doom_rosetta_check.py", "tests/tools/doom_speedrun/doom_scorer.py"} <= reached
    missing = sorted(p for p in reached if not any(fnmatch.fnmatch(p, g) for g in globs))
    assert not missing, f"add to doom-rosetta.yml's pull_request paths: {missing}"


def test_manifest_expected_fails_are_known_checks():
    known = {"coverage", "language", "functions", "typosquat", "credentials", "health", "callgraph"}
    for row in PORTS:
        assert set((row["expected_fails"] or "").split()) <= known, row["name"]


def _oracle(misses=None, kinds=None):
    return {"recall": 1.0, "precision": 1.0, "misses_by_shape": misses or {}, "engine_only_by_kind": kinds or {}}


def test_callgraph_scores_misses_and_absent_or_comment_edges_only():
    cols = doom_scorer.callgraph_columns(_oracle({"statement": 2, "after-cast": 1}, {"absent": 4, "comment/string": 1}))
    assert (cols["callgraph_misses"], cols["callgraph_engine_only"], cols["callgraph_unscored"]) == (3, 5, 0)
    # a constructor, a bare function reference and a macro mention are reported in their own column, never scored
    cols = doom_scorer.callgraph_columns(_oracle(kinds={"type": 754, "function-pointer": 21, "macro": 2, "absent": 1}))
    assert (cols["callgraph_misses"], cols["callgraph_engine_only"], cols["callgraph_unscored"]) == (0, 1, 777)


def _scan_db(path, rows):
    """A minimal scan DB: rows are (file_path, language, func_name, start_line, calls_out_to list)."""
    con = sqlite3.connect(path)
    con.execute("create table file_data (id integer primary key, file_path text, language text)")
    con.execute("create table function_data (file_id int, func_name text, start_line int, calls_out_to text)")
    for i, (rel, lang, name, start, calls) in enumerate(rows):
        con.execute("insert into file_data values (?, ?, ?)", (i, rel, lang))
        con.execute("insert into function_data values (?, ?, ?, ?)", (i, name, start, json.dumps(calls)))
    con.commit()
    con.close()


def test_callgraph_is_na_and_a_shown_pass_without_an_oracle(tmp_path):
    # a port whose only functions are in a language no oracle covers (dart): n/a, not a silent pass
    _scan_db(tmp_path / "s.db", [("a.dart", "dart", "f", 1, ["g"]), ("a.dart", "dart", "g", 5, [])])
    cols, ok = doom_scorer.callgraph_check("dartdoom", tmp_path, tmp_path / "s.db")
    assert ok and set(cols.values()) == {"n/a"} and set(cols) == set(doom_scorer.CALLGRAPH_NA)


LANG_FIXTURES = {  # language -> (file, source with f calling g, h; g, h and the comment/string/macro cases defined)
    "go": ("a.go", "package a\nfunc g() {}\nfunc h() {}\nfunc f() {\n\tg()\n\tx.h()\n}\n"),
    "java": ("A.java", "class A {\n void g() {}\n void h() {}\n void f() {\n  g();\n  this.h();\n }\n}\n"),
    "csharp": ("A.cs", "class A {\n void g() {}\n void h() {}\n void f() {\n  g();\n  this.h();\n }\n}\n"),
    "rust": ("a.rs", "fn g() {}\nfn h() {}\nfn f() {\n    g();\n    vec![h(); 2];\n}\n"),
    "javascript": ("a.js", "function g() {}\nfunction h() {}\nfunction f() {\n  g();\n  o.h();\n}\n"),
    "kotlin": ("a.kt", "fun g() {}\nfun h() {}\nfun f() {\n    g()\n    x.h()\n}\n"),
    "python": ("a.py", "def g():\n    pass\ndef h():\n    pass\ndef f():\n    g()\n    o.h()\n"),
    "lua": ("a.lua", "function g() end\nfunction h() end\nfunction f()\n  g()\n  o:h()\nend\n"),
    "shell": ("a.sh", "g() { :; }\nh() { :; }\nf() {\n  g\n  h x\n}\n"),
    "tcl": ("a.tcl", "proc g {} {}\nproc h {} {}\nproc f {} {\n  g\n  h x\n}\n"),
}
FIXTURE_START = {"go": 4, "java": 4, "csharp": 4, "rust": 3, "javascript": 3, "python": 5, "kotlin": 3, "lua": 3, "shell": 3, "tcl": 3}


@pytest.mark.parametrize("lang", sorted(LANG_FIXTURES))
def test_ts_oracle_scores_each_covered_language(lang, tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    import ts_callgraph_oracle as ts

    if not ts.available(lang):
        pytest.skip(f"tree-sitter language pack has no {lang} grammar")
    rel, src = LANG_FIXTURES[lang]
    (tmp_path / rel).write_text(src)
    starts = {"g": FIXTURE_START[lang] - 2, "h": FIXTURE_START[lang] - 1}
    if lang == "python":
        starts = {"g": 1, "h": 3}
    rows = [(rel, lang, n, s, []) for n, s in starts.items()]
    # the engine saw only g: one miss (h), no engine-only edge
    db = tmp_path / "s.db"
    _scan_db(db, rows + [(rel, lang, "f", FIXTURE_START[lang], ["g"])])
    cols, ok = doom_scorer.callgraph_check("a-port", tmp_path, db)
    assert (cols["callgraph_misses"], cols["callgraph_engine_only"], ok) == (1, 0, False), cols
    # the engine saw both: perfect
    _scan_db(tmp_path / "t.db", rows + [(rel, lang, "f", FIXTURE_START[lang], ["g", "h"])])
    cols, ok = doom_scorer.callgraph_check("a-port", tmp_path, tmp_path / "t.db")
    assert (cols["callgraph_recall"], cols["callgraph_precision"], ok) == (1.0, 1.0, True), cols
    # an engine edge to a defined function the body never names is scored (kind absent)
    k = (rel, lang, "k", 1, [])
    _scan_db(tmp_path / "u.db", rows + [k, (rel, lang, "f", FIXTURE_START[lang], ["g", "h", "k"])])
    cols, ok = doom_scorer.callgraph_check("a-port", tmp_path, tmp_path / "u.db")
    assert (cols["callgraph_misses"], cols["callgraph_engine_only"], ok) == (0, 1, False), cols


def test_ts_oracle_reads_the_small_script_call_shapes(tmp_path):
    """#5640: a Lua call after ``..`` and under ``while not``, a shell command word and ``$(..)`` substitution, and a Tcl
    command on the line after a closing ``}`` are calls; a string or comment naming a function is not."""
    pytest.importorskip("tree_sitter_language_pack")
    import ts_callgraph_oracle as ts

    cases = {
        "lua": (
            "a.lua",
            "function g() end\nfunction h() end\nfunction f()\n  w(\"x\"..g(1))\n  while not h(2) do end\n  -- g()\nend\n",
            3,
        ),
        "shell": ("a.sh", "g() { :; }\nh() { :; }\nf() {\n  x=$(g 1)\n  echo \"h\"\n  if true; then\n    h\n  fi\n}\n", 3),
        "tcl": ("a.tcl", "proc g {} {}\nproc h {} {}\nproc f {} {\n  if {1} {\n    g\n  }\n  h\n}\n", 3),
    }
    for lang, (rel, src, start) in cases.items():
        if not ts.available(lang):
            pytest.skip(f"tree-sitter language pack has no {lang} grammar")
        (tmp_path / rel).write_text(src)
        rows = [(rel, lang, "g", 1, []), (rel, lang, "h", 2, []), (rel, lang, "f", start, ["g", "h"])]
        res = ts.body_oracle(tmp_path, rows)
        assert (res["oracle_calls"], res["misses_by_shape"], res["engine_only_by_kind"]) == (2, {}, {}), (lang, res)


def test_ts_oracle_scores_a_bound_function_expression_as_its_own_unit(tmp_path):
    """#6266: ``window.f = () => {..}`` and ``const f = () => ..`` are functions the engine names; their calls are not the
    enclosing function's. An anonymous callback argument stays in the enclosing function."""
    pytest.importorskip("tree_sitter_language_pack")
    import ts_callgraph_oracle as ts

    if not ts.available("javascript"):
        pytest.skip("tree-sitter language pack has no javascript grammar")
    src = (
        "function g() {}\nfunction h() {}\nfunction k() {}\n"
        "function f() {\n  window.a = () => {\n    g();\n  };\n  const b = function () { h(); };\n"
        "  [1].forEach(() => { k(); });\n}\n"
    )
    (tmp_path / "a.js").write_text(src)
    rows = [("a.js", "javascript", n, i + 1, []) for i, n in enumerate("ghk")]
    rows += [
        ("a.js", "javascript", "f", 4, ["k"]),
        ("a.js", "javascript", "a", 5, ["g"]),
        ("a.js", "javascript", "b", 8, ["h"]),
    ]
    res = ts.body_oracle(tmp_path, rows)
    assert (res["misses_by_shape"], res["engine_only_by_kind"], res["unmatched_functions"]) == ({}, {}, 0), res


def test_ts_oracle_reads_a_csharp_builtin_type_name_as_a_reference_not_an_absent_edge(tmp_path):
    """#6266: ``new string(..)`` beside a user ``operator string`` names the type in the body: reported, never ``absent``."""
    pytest.importorskip("tree_sitter_language_pack")
    import ts_callgraph_oracle as ts

    if not ts.available("csharp"):
        pytest.skip("tree-sitter language pack has no csharp grammar")
    src = "class A {\n void string() {}\n void f() {\n  var s = new string(c);\n }\n}\n"
    (tmp_path / "A.cs").write_text(src)
    rows = [("A.cs", "csharp", "string", 2, []), ("A.cs", "csharp", "f", 3, ["string"])]
    res = ts.body_oracle(tmp_path, rows)
    assert res["engine_only_by_kind"] == {"function-pointer": 1} and res["misses_by_shape"] == {}, res
    assert doom_scorer.callgraph_columns(res)["callgraph_engine_only"] == 0


def test_ts_oracle_kotlin_units_and_trailing_lambda_calls(tmp_path):
    """An ``init`` block and a secondary constructor are units the engine names; ``x.run { }`` is the stdlib scope
    function (not a call to a port-defined ``run``) but a user function called with only a lambda is a call."""
    pytest.importorskip("tree_sitter_language_pack")
    import ts_callgraph_oracle as ts

    if not ts.available("kotlin"):
        pytest.skip("tree-sitter language pack has no kotlin grammar")
    src = (
        "fun run() {}\nfun ifKey(b: () -> Unit) {}\n"
        "class A {\n  init {\n    ifKey { }\n  }\n  constructor(x: Int) {\n    x.run { }\n    ifKey(f)\n  }\n}\n"
    )
    (tmp_path / "A.kt").write_text(src)
    rows = [("A.kt", "kotlin", "run", 1, []), ("A.kt", "kotlin", "ifKey", 2, [])]
    rows += [("A.kt", "kotlin", "init", 4, []), ("A.kt", "kotlin", "constructor", 7, ["ifKey"])]
    res = ts.body_oracle(tmp_path, rows)
    assert res["unmatched_functions"] == 0 and res["oracle_calls"] == 2, res
    assert res["misses_by_shape"] == {"call": 1} and res["engine_only_by_kind"] == {}, res  # init -> ifKey missed


def test_ts_oracle_kotlin_stdlib_filter_does_not_leak_into_other_languages(tmp_path):
    """The lambda-only stdlib rule is Kotlin's: a JavaScript ``map(x)`` of a port-defined ``map`` is still a call."""
    pytest.importorskip("tree_sitter_language_pack")
    import ts_callgraph_oracle as ts

    if not ts.available("javascript"):
        pytest.skip("tree-sitter language pack has no javascript grammar")
    (tmp_path / "a.js").write_text("function map() {}\nfunction f() {\n  map();\n}\n")
    res = ts.body_oracle(tmp_path, [("a.js", "javascript", "map", 1, []), ("a.js", "javascript", "f", 2, [])])
    assert res["oracle_calls"] == 1 and res["misses_by_shape"] == {"call": 1}, res


def test_ts_oracle_reads_rust_macro_arguments_and_skips_quote(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    import ts_callgraph_oracle as ts

    src = "fn g() {}\nfn h() {}\nfn f() {\n    let v = vec![g(); 3];\n    let t = quote! { h() };\n}\n"
    (tmp_path / "a.rs").write_text(src)
    rows = [("a.rs", "rust", "g", 1, []), ("a.rs", "rust", "h", 2, []), ("a.rs", "rust", "f", 3, [])]
    res = ts.body_oracle(tmp_path, rows)
    assert res["oracle_calls"] == 1 and res["misses_by_shape"] == {
        "call": 1
    }  # g() inside vec![] counts, quote! does not


def test_seven_check_verdict_counts_out_of_seven():
    assert doom_scorer.verdict([], 7) == "PERFECT"
    assert doom_scorer.verdict(["callgraph"], 7) == "6/7"
    assert set(doom_speedrun.COLUMNS) >= set(doom_scorer.CALLGRAPH_NA) | {"verdict6"}


def _golden(files, **summary):
    return {"sha": "a", "summary": {"fails": "", **summary}, "files": files, "exclusions": {"x/y.c": "vendor"}}


def test_func_hash_ignores_order_and_carries_no_names():
    a = [("f", 3, 5, 1), ("g", 9, 2, 1)]
    assert check.func_hash(a) == check.func_hash(a[::-1])
    assert check.func_hash(a) != check.func_hash([("f", 3, 5, 2), ("g", 9, 2, 1)])  # complexity moved
    assert len(check.func_hash(a)) == 16


def test_diff_names_the_file_and_the_field():
    old = _golden({"a.c": ["c", 10, 2, 0, "h1"], "b.c": ["c", 5, 1, 0, "h2"]}, functions=3)
    new = _golden({"a.c": ["c", 10, 3, 0, "h9"], "c.c": ["c", 1, 0, 0, "h3"]}, functions=4)
    new["exclusions"] = {}
    lines = check.diff_golden(old, new)
    assert "summary.functions: 3 -> 4" in lines
    assert "file a.c: functions 2 -> 3, func_hash 'h1' -> 'h9'" in lines
    assert "file added: c.c" in lines and "file removed: b.c" in lines
    assert "exclusion removed: x/y.c" in lines
    assert check.diff_golden(old, old) == []


def test_report_caps_long_diffs():
    text = check.format_report("p", [f"l{i}" for i in range(100)], limit=5)
    assert "100 difference(s)" in text and "95 more" in text


def test_golden_write_is_byte_stable(tmp_path, monkeypatch):
    monkeypatch.setattr(check, "GOLDEN_DIR", tmp_path)
    golden = _golden({"a.c": ["c", 1, 1, 0, "h"]})
    check.write_golden("p", golden)
    first = (tmp_path / "p.json.gz").read_bytes()
    check.write_golden("p", golden)
    assert (tmp_path / "p.json.gz").read_bytes() == first
    assert check.read_golden("p") == golden
    assert check.read_golden("absent") is None
