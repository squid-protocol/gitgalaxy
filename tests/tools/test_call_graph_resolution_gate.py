"""call_graph_resolution.py --ci: the Level 2 gate reads a DROP in a gated python
metric beyond the tolerance as a regression, and never a rise."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import call_graph_resolution as cgr
import callgraph_refs


def test_gated_metrics_flatten_the_scored_result():
    py = {
        "confident": {"agree": 98, "wrong": 2, "precision_pct": 98.0},
        "ambiguous": {"agree": 1, "wrong": 1, "precision_pct": 50.0},
        "recall_pct": 36.1,
        "resolution_recall_pct": 71.8,
        "pyan_edges": 3492,
        "decorator": {"agree": 575, "wrong": 0, "precision_pct": 100.0},
        "recall_with_decorators_pct": 67.9,
        "reference_edges": {"agree": 322, "wrong": 1, "precision_pct": 99.7},
        "recall_all_kinds_pct": 77.3,
    }
    assert cgr.gated_metrics(py) == {
        "confident_precision_pct": 98.0,
        "confident_judged": 100,
        "ambiguous_precision_pct": 50.0,
        "recall_pct": 36.1,
        "resolution_recall_pct": 71.8,
        "pyan_edges": 3492,
        "decorator_precision_pct": 100.0,
        "decorator_judged": 575,
        "recall_with_decorators_pct": 67.9,
        "reference_precision_pct": 99.7,
        "reference_judged": 323,
        "recall_all_kinds_pct": 77.3,
    }


def test_regressions_respect_the_tolerance_and_ignore_the_ungated_metric():
    base = {
        "confident_precision_pct": 98.7,
        "recall_pct": 36.1,
        "resolution_recall_pct": 71.8,
        "ambiguous_precision_pct": 50.0,
    }
    ok = {
        "confident_precision_pct": 98.3,
        "recall_pct": 40.0,
        "resolution_recall_pct": 71.8,
        "ambiguous_precision_pct": 0.0,
    }
    assert cgr.regressions(ok, base) == []
    bad = dict(ok, confident_precision_pct=98.0)
    assert cgr.regressions(bad, base) == ["python: confident_precision_pct 98.7 -> 98.0"]


def test_typescript_metrics_report_the_checkers_external_verdict():
    ts = {
        "reference": "tsc",
        "reference_version": cgr.TYPESCRIPT_VERSION,
        "confident": {
            "agree": 96,
            "wrong": 1,
            "external": 3,
            "unmapped": 7,
            "precision_pct": 99.0,
            "strict_precision_pct": 96.0,
        },
        "ambiguous": {"agree": 1, "wrong": 1, "precision_pct": 50.0},
        "recall_pct": 56.9,
        "resolution_recall_pct": 73.7,
        "pyan_edges": 2661,
    }
    m = cgr.gated_metrics(ts)
    assert m["confident_judged"] == 97
    assert (m["confident_external"], m["confident_strict_precision_pct"], m["confident_unmapped"]) == (3, 96.0, 7)
    assert "decorator_precision_pct" not in m and "reference_precision_pct" not in m
    base = dict(m, recall_pct=60.0)
    assert cgr.regressions(m, base, "typescript") == ["typescript: recall_pct 60.0 -> 56.9"]


def test_verdict_order_agree_wrong_external_unconfirmed():
    a, b, c = ("f.ts", "caller", 1), ("f.ts", "trim", 9), ("g.ts", "trim", 3)
    ref = cgr.RefGraph({}, {(a, b)}, {(a, "trim"): {b}}, {(a, "trim"), (a, "has")})
    assert cgr._verdict(ref, a, b) == "agree"
    assert cgr._verdict(ref, a, c) == "wrong"  # the reference links the same name elsewhere
    assert cgr._verdict(ref, a, ("h.ts", "has", 5)) == "external"
    assert cgr._verdict(ref, a, ("h.ts", "save", 5)) == "unconfirmed"


def test_ts_callgraph_js_mode_resolves_commonjs_with_allow_js(tmp_path):
    import json
    import shutil
    import subprocess

    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    env = callgraph_refs.node_env()
    probe = "process.exit(typeof require('typescript').createProgram === 'function' ? 0 : 1)"
    if subprocess.run(["node", "-e", probe], env=env, capture_output=True).returncode:
        pytest.skip("no typescript with the JavaScript compiler API (<= 6.x) on NODE_PATH")
    (tmp_path / "util.js").write_text("exports.clone = function clone(x) {\n  return x;\n};\n")
    (tmp_path / "mod.cjs").write_text("module.exports = function build() {\n  return 1;\n};\n")
    (tmp_path / "proto.mjs").write_text(
        "export function Box() {}\nBox.prototype.open = function () {\n  return 2;\n};\nexport const make = () => new Box();\n"
    )
    (tmp_path / "main.js").write_text(
        "var util = require('./util');\n"
        "var build = require('./mod.cjs');\n"
        "var proto = {};\n"
        "proto.run = function run(s, box) {\n"
        "  's'.trim();\n"
        "  build();\n"
        "  box.open();\n"
        "  return util.clone(1);\n"
        "};\n"
    )
    (tmp_path / "typed.ts").write_text("export function only() {\n  return 1;\n}\n")

    def graph(*extra):
        out = subprocess.run(
            ["node", str(cgr.TOOLS / "ts_callgraph.js"), str(tmp_path), *extra], env=env, capture_output=True, text=True
        )
        assert out.returncode == 0, out.stderr
        return json.loads(out.stdout)

    g = graph("--js")
    run = ["main.js", "run", 4]
    assert ["typed.ts", "only", 1] not in g["defs"]  # the TypeScript files are not read in js mode
    assert {tuple(d) for d in g["defs"]} >= {
        ("util.js", "clone", 1),
        ("mod.cjs", "build", 1),
        ("proto.mjs", "open", 2),
        ("proto.mjs", "make", 5),
        tuple(run),
    }
    edges = {(tuple(e[0]), tuple(e[1])): e[2] for e in g["edges"]}
    assert edges[(tuple(run), ("util.js", "clone", 1))] == 8  # exports.f = function through require()
    assert edges[(tuple(run), ("mod.cjs", "build", 1))] == 6  # module.exports = function
    assert edges[(("proto.mjs", "make", 5), ("proto.mjs", "Box", 1))] == 5  # `new Box()` runs the function
    assert not any(e[0] == run and e[1][1] == "open" for e in g["edges"])  # an untyped receiver: silent, not wrong
    assert [run, "trim"] in g["external"]  # a string literal's trim() is String.prototype.trim
    # the typescript mode never reads .js
    assert all(not d[0].endswith((".js", ".cjs", ".mjs")) for d in graph()["defs"])


def test_ts_callgraph_resolves_calls_with_the_type_checker(tmp_path):
    import json
    import shutil
    import subprocess

    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    env = callgraph_refs.node_env()
    # a typescript whose package has the JavaScript compiler API: 7.x (the native
    # port, what a bare `npm install -g typescript` gives) has none
    probe = "process.exit(typeof require('typescript').createProgram === 'function' ? 0 : 1)"
    if subprocess.run(["node", "-e", probe], env=env, capture_output=True).returncode:
        pytest.skip("no typescript with the JavaScript compiler API (<= 6.x) on NODE_PATH")
    (tmp_path / "util.ts").write_text("export function clone(x: number) {\n  return x;\n}\n")
    (tmp_path / "main.ts").write_text(
        'import { clone } from "./util";\n'
        "class Str {\n"
        "  trim() {\n"
        "    return 1;\n"
        "  }\n"
        "}\n"
        "export const run = (s: string, t: Str) => {\n"
        "  s.trim();\n"
        "  t.trim();\n"
        "  new Str();\n"
        "  return clone(1);\n"
        "};\n"
    )
    out = subprocess.run(
        ["node", str(cgr.TOOLS / "ts_callgraph.js"), str(tmp_path)], env=env, capture_output=True, text=True
    )
    assert out.returncode == 0, out.stderr
    g = json.loads(out.stdout)
    run = ["main.ts", "run", 7]
    assert sorted(g["defs"]) == [run, ["main.ts", "trim", 3], ["util.ts", "clone", 1]]
    # each edge carries its first call site: `t.trim()` on line 9, `clone(1)` on line 11
    assert sorted(g["edges"]) == [[run, ["main.ts", "trim", 3], 9], [run, ["util.ts", "clone", 1], 11]]
    assert g["external"] == [[run, "trim"]]  # s.trim() is String.prototype.trim


def test_go_callgraph_resolves_calls_with_the_type_checker(tmp_path):
    import json
    import shutil

    if shutil.which("go") is None or callgraph_refs._go_version() is None:
        pytest.skip("no Go 1.24+ toolchain on PATH")
    (tmp_path / "go.mod").write_text("module example.com/m\n\ngo 1.22\n")
    (tmp_path / "util").mkdir()
    (tmp_path / "util" / "util.go").write_text("package util\n\nfunc Clone(x int) int {\n\treturn x\n}\n")
    (tmp_path / "main.go").write_text(
        "package main\n"  # 1
        "\n"
        'import (\n\t"strings"\n\n\t"example.com/m/util"\n)\n'  # 3-7
        "\n"
        "type Speaker interface{ Speak() int }\n"  # 9
        "\n"
        "type Dog struct{}\n"  # 11
        "\n"
        "func (d *Dog) Speak() int { return util.Clone(1) }\n"  # 13
        "\n"
        "func Map[T any](x T) T { return x }\n"  # 15
        "\n"
        "func run(s Speaker, d Dog) int {\n"  # 17
        '\tstrings.TrimSpace("x")\n'  # 18
        "\tf := func() int { return d2().Speak() }\n"  # 19
        "\t_ = Map(1)\n"  # 20
        "\ts.Speak()\n"  # 21
        "\treturn f()\n"  # 22
        "}\n"
        "\n"
        "func d2() *Dog { return &Dog{} }\n"  # 25
        "\n"
        "func main() { run(&Dog{}, Dog{}) }\n"  # 27
    )
    g = callgraph_refs.go_contract(tmp_path)
    run, speak, clone, mapf, d2, main = (
        ["main.go", "run", 17],
        ["main.go", "Speak", 13],
        ["util/util.go", "Clone", 3],
        ["main.go", "Map", 15],
        ["main.go", "d2", 25],
        ["main.go", "main", 27],
    )
    assert sorted(g["defs"]) == sorted([run, speak, clone, mapf, d2, main])
    edges = {(json.dumps(a), json.dumps(b)) for a, b, _ in g["edges"]}
    # run -> Speak is the interface call; run -> d2 is made inside a closure
    want = [(run, speak), (run, mapf), (run, d2), (speak, clone), (main, run)]
    assert {(json.dumps(a), json.dumps(b)) for a, b in want} <= edges
    # a call outside the module is external, a closure's calls belong to its enclosing function
    assert [run, "TrimSpace"] in g["external"]
    assert g["files"] == 2


def test_clang_callgraph_resolves_c_calls_across_translation_units(tmp_path):
    import clang_callgraph

    if clang_callgraph.libclang_version() is None:
        pytest.skip("libclang (pip install libclang==18.1.1) is not installed")
    (tmp_path / "util.h").write_text("int helper(int x);\nint twice(int x) {\n  return helper(x) * 2;\n}\n")  # 1-4
    (tmp_path / "util.c").write_text(
        '#include "util.h"\n'
        "static int hidden(int x) { return x; }\n"  # 2
        "int helper(int x) {\n"  # 3
        "  return hidden(x);\n"
        "}\n"
    )
    (tmp_path / "other.c").write_text("static int hidden(int x) { return -x; }\nint neg(int x) { return hidden(x); }\n")
    (tmp_path / "main.c").write_text(
        '#include "util.h"\n'
        "#include <string.h>\n"
        "#define SQ(x) ((x) * (x))\n"  # looks like a call, is not one
        "#define VIA(x) helper(x)\n"  # expands to one
        "int run(char *s, int (*fp)(int)) {\n"  # 5
        "  int n = (int)strlen(s);\n"
        "  fp(n);\n"
        "  return SQ(n) + VIA(n) + twice(n);\n"
        "}\n"
    )
    g = clang_callgraph.build(tmp_path)
    run, twice, helper = ["main.c", "run", 5], ["util.h", "twice", 2], ["util.c", "helper", 3]
    hidden, neg = ["util.c", "hidden", 2], ["other.c", "neg", 2]
    # the prototype `int helper(int x);` is no def; each static `hidden` is its own def
    assert sorted(g["defs"]) == sorted([run, twice, helper, hidden, ["other.c", "hidden", 1], neg])
    # cross-file: run -> twice (a header function) and -> helper (via the macro, and twice -> helper through the
    # prototype); a static callee is its own translation unit's definition, not the other file's `hidden`
    assert sorted(g["edges"]) == sorted(
        [
            [run, twice, 8],
            [run, helper, 8],
            [twice, helper, 3],
            [helper, hidden, 4],
            [neg, ["other.c", "hidden", 1], 2],
        ]
    )
    # strlen resolves only in a system header; the call through `fp` names no function
    assert g["external"] == [[run, "strlen"]]
    assert g["files"] == 3


def test_clang_callgraph_links_windows_sources_as_their_own_group(tmp_path):
    import clang_callgraph

    if clang_callgraph.libclang_version() is None:
        pytest.skip("libclang (pip install libclang==18.1.1) is not installed")
    (tmp_path / "unix").mkdir()
    (tmp_path / "win").mkdir()
    (tmp_path / "common.c").write_text("int shared(void) { return 1; }\nint both(void) { return 2; }\n")  # 1, 2
    (tmp_path / "unix" / "u.c").write_text(
        "int shared(void);\nint both(void);\nint u_only(void) { return 3; }\n"  # 3
        "int uv_x(void) { return u_only() + both() + shared(); }\n"  # 4
    )
    # the Windows copy of `both` and `uv_x`; windows.h is not on this host, so `Sleep` is an implicit declaration: external, never an edge
    (tmp_path / "win" / "w.c").write_text(
        "#include <windows.h>\n"
        "int both(void) { return 4; }\n"  # 2
        "int uv_x(void) {\n"  # 3
        "  Sleep(1);\n"
        "  return both() + shared();\n"  # 5
        "}\n"
    )
    (tmp_path / "main-win.c").write_text(
        "int uv_x(void);\n#ifdef _WIN32\nint main_win(void) { return uv_x(); }\n#endif\n"
    )
    (tmp_path / "plain.c").write_text("int uv_x(void);\nint plain(void) { return uv_x(); }\n")
    g = clang_callgraph.build(tmp_path)
    shared, both_c, both_w = ["common.c", "shared", 1], ["common.c", "both", 2], ["win/w.c", "both", 2]
    ux_u, ux_w, main_win, plain = (
        ["unix/u.c", "uv_x", 4],
        ["win/w.c", "uv_x", 3],
        ["main-win.c", "main_win", 3],
        ["plain.c", "plain", 2],
    )
    # `-D_WIN32` keeps the `#ifdef _WIN32` body of main-win.c
    assert main_win in g["defs"] and ux_w in g["defs"]
    edges = {(tuple(a), tuple(b)) for a, b, _ in g["edges"]}
    # a Windows caller takes the Windows `both` and falls back to the shared `shared`; it never reaches unix/
    assert (tuple(ux_w), tuple(both_w)) in edges and (tuple(ux_w), tuple(shared)) in edges
    assert (tuple(ux_w), tuple(both_c)) not in edges
    # a Unix caller never links to a Windows definition
    assert (tuple(ux_u), tuple(both_c)) in edges and (tuple(ux_u), tuple(both_w)) not in edges
    # a Windows-file caller of `uv_x` links the Windows definition only; a shared-file caller links the Unix one only
    assert (tuple(main_win), tuple(ux_w)) in edges and (tuple(main_win), tuple(ux_u)) not in edges
    assert (tuple(plain), tuple(ux_u)) in edges and (tuple(plain), tuple(ux_w)) not in edges
    assert g["external"] == [[ux_w, "Sleep"]]


def test_clang_callgraph_parses_a_file_naming_a_platform_macro_once_more_per_platform(tmp_path):
    import clang_callgraph

    if clang_callgraph.libclang_version() is None:
        pytest.skip("libclang (pip install libclang==18.1.1) is not installed")
    (tmp_path / "unix").mkdir()
    # one file, three configurations: Linux (the base parse), `__APPLE__`, `_AIX`, and an unnamed platform
    (tmp_path / "unix" / "plat.c").write_text(
        "int helper(void) { return 1; }\n"  # 1
        "#if defined(__APPLE__)\n"
        "int apple_only(void) { return helper(); }\n"  # 3
        "#elif defined(_AIX)\n"
        "int aix_only(void) { return helper(); }\n"  # 5
        "#elif defined(__sun)\n"
        "int sun_only(void) { return 1; }\n"  # 7
        "#else\n"
        "int linux_only(void) { return helper(); }\n"  # 9
        "#endif\n"
        "#if defined(__APPLE__) || defined(_AIX)\n"
        "int fallback(void) { return 1; }\n"  # 12
        "#else\n"
        "int fallback(void) { return 2; }\n"  # 14
        "#endif\n"
    )
    (tmp_path / "user.c").write_text(
        "int apple_only(void);\nint fallback(void);\nint user(void) { return apple_only() + fallback(); }\n"  # 3
    )
    # a file that names no platform macro is parsed once, as Linux
    (tmp_path / "plain.c").write_text("int linux_only(void);\nint plain(void) { return linux_only(); }\n")
    g = clang_callgraph.build(tmp_path)
    plat = "unix/plat.c"
    defs = {tuple(d) for d in g["defs"]}
    assert {(plat, n, ln) for n, ln in (("apple_only", 3), ("aix_only", 5), ("sun_only", 7), ("linux_only", 9))} <= defs
    edges = {(tuple(a), tuple(b)) for a, b, _ in g["edges"]}
    helper = (plat, "helper", 1)
    # each platform's caller links the shared helper from its own configuration
    for name, line in (("apple_only", 3), ("aix_only", 5), ("linux_only", 9)):
        assert ((plat, name, line), helper) in edges
    # a Linux caller never links a def only another platform has (a repo function all the same, not external), but
    # reaches every `#if` variant of one function (one unit to the engine)
    user = ("user.c", "user", 3)
    assert (user, (plat, "apple_only", 3)) not in edges
    assert (user, (plat, "fallback", 12)) in edges and (user, (plat, "fallback", 14)) in edges
    assert (("plain.c", "plain", 2), (plat, "linux_only", 9)) in edges
    assert g["external"] == []


def test_clang_callgraph_parses_freebsd_qnx_and_mvs_branches_as_platform_groups(tmp_path):
    import clang_callgraph

    if clang_callgraph.libclang_version() is None:
        pytest.skip("libclang (pip install libclang==18.1.1) is not installed")
    (tmp_path / "unix").mkdir()
    (tmp_path / "unix" / "bsd.c").write_text(
        "int helper(void) { return 1; }\n"  # 1
        "#if defined(__FreeBSD__)\n"
        "int bsd_only(void) { return helper(); }\n"  # 3
        "#elif defined(__QNX__)\n"
        "int qnx_only(void) { return helper(); }\n"  # 5
        "#elif defined(__MVS__)\n"
        "int mvs_only(void) { return helper(); }\n"  # 7
        "#else\n"
        "int linux_only(void) { return helper(); }\n"  # 9
        "#endif\n"
    )
    (tmp_path / "user.c").write_text(
        "int bsd_only(void);\nint linux_only(void);\nint user(void) { return linux_only(); }\n"
    )
    g = clang_callgraph.build(tmp_path)
    plat = "unix/bsd.c"
    defs = {tuple(d) for d in g["defs"]}
    assert {(plat, n, ln) for n, ln in (("bsd_only", 3), ("qnx_only", 5), ("mvs_only", 7), ("linux_only", 9))} <= defs
    edges = {(tuple(a), tuple(b)) for a, b, _ in g["edges"]}
    for name, line in (("bsd_only", 3), ("qnx_only", 5), ("mvs_only", 7)):
        assert ((plat, name, line), (plat, "helper", 1)) in edges
    # a Linux caller links the Linux def and never another platform's
    assert (("user.c", "user", 3), (plat, "linux_only", 9)) in edges
    assert not any(b[1] == "bsd_only" for _, b in edges if _[0] == "user.c")


def test_clang_callgraph_names_a_one_argument_macro_def_as_the_engine_does(tmp_path):
    import clang_callgraph

    if clang_callgraph.libclang_version() is None:
        pytest.skip("libclang (pip install libclang==18.1.1) is not installed")
    (tmp_path / "task.h").write_text(
        "#define TEST_IMPL(name) int run_test_##name(void); int run_test_##name(void)\n"
        "#define HELPER_IMPL(name) int run_helper_##name(void); int run_helper_##name(void)\n"
        "int shared(void);\n"
    )
    (tmp_path / "t.c").write_text(
        '#include "task.h"\n'
        "int shared(void) { return 1; }\n"  # 2
        "TEST_IMPL(kill) {\n"  # 3
        "  return shared();\n"
        "}\n"
        "HELPER_IMPL(kill_helper) {\n"  # 6
        "  return 0;\n"
        "}\n"
        "int run_plain(void) { return shared(); }\n"  # 9
    )
    g = clang_callgraph.build(tmp_path)
    # the engine names `TEST_IMPL(kill)` `kill`, not the `run_test_kill` the macro declares; a plain def is unchanged
    assert sorted(g["defs"]) == [
        ["t.c", "kill", 3],
        ["t.c", "kill_helper", 6],
        ["t.c", "run_plain", 9],
        ["t.c", "shared", 2],
    ]
    assert [["t.c", "kill", 3], ["t.c", "shared", 2], 4] in g["edges"]


def test_clang_callgraph_resolves_cpp_calls_by_usr_with_engine_names(tmp_path):
    import clang_callgraph

    if clang_callgraph.libclang_version() is None or not clang_callgraph._system_includes():
        pytest.skip("libclang (pip install libclang==18.1.1) or a host g++ is not available")
    (tmp_path / "inc").mkdir()
    (tmp_path / "inc" / "lib.h").write_text(
        "#pragma once\n"
        "#include <cstring>\n"
        "int proto(int x);\n"  # 3: a prototype is no def
        "struct Foo {\n"  # 4
        "  Foo() {}\n"  # 5
        "  int inl() { return proto(1); }\n"  # 6
        "  int out(int x);\n"
        "  int out(double x);\n"
        "};\n"
        "template <typename T> T twice(T v) { return v + v; }\n"  # 10
        "#define VIA(x) proto(x)\n"
    )
    (tmp_path / "a.cc").write_text(
        '#include "lib.h"\n'
        "namespace {\n"
        "int hidden() { return 1; }\n"  # 3: internal linkage
        "}\n"
        "int proto(int x) { return hidden() + x; }\n"  # 5
        "int Foo::out(int x) { return proto(x); }\n"  # 6
        "int Foo::out(double x) { return (int)x; }\n"  # 7
        "namespace ns { int deep() { return Foo().out(1); } }\n"  # 8
    )
    (tmp_path / "b.cc").write_text(
        '#include "lib.h"\n'
        "namespace {\n"
        "int hidden() { return 2; }\n"  # 3
        "}\n"
        "int run(const char *s) {\n"  # 5
        "  Foo f;\n"
        "  int n = (int)strlen(s);\n"
        "  return twice(n) + twice(1.5) + hidden() + VIA(n) + f.out(2.0) + f.inl();\n"
        "}\n"
    )
    g = clang_callgraph.build(tmp_path, "cpp")
    foo_inl, twice = ["inc/lib.h", "inl", 6], ["inc/lib.h", "twice", 10]
    proto, out_int, out_dbl = ["a.cc", "proto", 5], ["a.cc", "Foo::out", 6], ["a.cc", "Foo::out", 7]
    deep, run = ["a.cc", "deep", 8], ["b.cc", "run", 5]
    hidden_a, hidden_b = ["a.cc", "hidden", 3], ["b.cc", "hidden", 3]
    # in-class definitions keep their bare name, out-of-line ones are Class::name; the prototype is no def
    assert ["inc/lib.h", "Foo", 5] in g["defs"]
    assert sorted(d for d in g["defs"] if d[1] != "Foo") == sorted(
        [foo_inl, twice, proto, out_int, out_dbl, deep, run, hidden_a, hidden_b]
    )
    edges = {(tuple(a), tuple(b)) for a, b, _ in g["edges"]}
    assert (tuple(foo_inl), tuple(proto)) in edges  # the header prototype is linked to its .cc body
    assert (tuple(proto), tuple(hidden_a)) in edges and (tuple(run), tuple(hidden_b)) in edges  # each TU's own hidden
    assert (tuple(proto), tuple(hidden_b)) not in edges

    assert (tuple(run), tuple(proto)) in edges  # through the macro
    # overloads: the int and the double `out` are told apart, not linked by name
    assert (tuple(deep), tuple(out_int)) in edges and (tuple(deep), tuple(out_dbl)) not in edges
    assert (tuple(run), tuple(out_dbl)) in edges and (tuple(run), tuple(out_int)) not in edges
    # both instantiations of the template are its one pattern
    assert (tuple(run), tuple(twice)) in edges
    # strlen is outside the repo
    assert [run, "strlen"] in g["external"]


def test_clang_callgraph_names_a_template_conversion_operator_as_the_engine_does(tmp_path):
    import clang_callgraph

    if clang_callgraph.libclang_version() is None or not clang_callgraph._system_includes():
        pytest.skip("libclang (pip install libclang==18.1.1) or a host g++ is not available")
    (tmp_path / "t.cc").write_text(
        "template <typename T> struct Box { T v; operator Box<int>() const { return Box<int>{1}; } };\n"  # 1
        "int use() { Box<long> b{2}; Box<int> c = b; (void)c; return 0; }\n"
    )
    g = clang_callgraph.build(tmp_path, "cpp")
    # the engine spells it `operator Box`, without the template arguments libclang appends
    assert ("operator Box", 1) in {(d[1], d[2]) for d in g["defs"]}


def test_clang_callgraph_names_a_gtest_body_by_its_test_name(tmp_path):
    import clang_callgraph

    if clang_callgraph.libclang_version() is None or not clang_callgraph._system_includes():
        pytest.skip("libclang (pip install libclang==18.1.1) or a host g++ is not available")
    (tmp_path / "t.cc").write_text(
        "#define TEST(s, n) struct s##_##n##_Test { void TestBody(); }; void s##_##n##_Test::TestBody()\n"
        "int helper() { return 1; }\n"
        "TEST(suite, first_case) { helper(); }\n"  # 3
        "TEST(suite_b, other) { helper(); }\n"  # 4
    )
    g = clang_callgraph.build(tmp_path, "cpp")
    # the engine names the unit `first_case`, not `suite_first_case_Test::TestBody`
    names = {(d[1], d[2]) for d in g["defs"]}
    assert {("first_case", 3), ("other", 4)} <= names
    assert not any("TestBody" in n for n, _ in names)
