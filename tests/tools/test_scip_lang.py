"""The C#, Kotlin and PHP conventions of the SCIP call-graph adapter (tests/tools/scip_lang.py, #8161 PR 5).
Indexes are built by hand (test_scip_callgraph's protobuf helpers); the gate lanes are the end-to-end check."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import callgraph_refs as cr
import scip_callgraph as sc
import scip_lang
from test_scip_callgraph import _field, _index, _occ, _sym


def _at(lines: list[str], line: int, text: str, nth: int = 0) -> list[int]:
    start = -1
    for _ in range(nth + 1):
        start = lines[line].index(text, start + 1)
    return [line, start, start + len(text)]


CS = (
    "class W {\n"  # 0
    "    [Obsolete]\n"  # 1
    "    public void Write(int v) { Write(v, 0); }\n"  # 2
    "    public void Write(int v, int w) => Flush();\n"  # 3
    "    public abstract void Flush();\n"  # 4
    '    public W() { var s = @"}"; Flush(); }\n'  # 5: a verbatim string holding `}`
    "    void IList.Add(object o) { Flush(); }\n"  # 6
    "}\n"
)
CP = "scip-dotnet nuget . . "


def test_csharp_extents_names_and_attribute_lines(tmp_path):
    # scip-dotnet writes no enclosing_range and no kinds: extents come from the source, and an abstract
    # member (no body) is no def; `.ctor` is the class's name, the explicit interface method `IList.Add`
    (tmp_path / "W.cs").write_text(CS)
    lines = CS.splitlines()
    w1, w2, fl, ctor, add = (
        CP + "W#Write().",
        CP + "W#Write(+1).",
        CP + "W#Flush().",
        CP + "W#`.ctor`().",
        CP + "W#`System.Collections.IList.Add`().",
    )
    occ = [
        _occ(_at(lines, 2, "Write"), w1, True),
        _occ(_at(lines, 2, "Write", 1), w2),
        _occ(_at(lines, 3, "Write"), w2, True),
        _occ(_at(lines, 3, "Flush"), fl),
        _occ(_at(lines, 4, "Flush"), fl, True),
        _occ(_at(lines, 5, "W"), ctor, True),
        _occ(_at(lines, 5, "Flush"), fl),
        _occ(_at(lines, 6, "Add"), add, True),
        _occ(_at(lines, 6, "Flush"), fl),
    ]
    c = sc.contract_from_index(_index("W.cs", occ, []), tmp_path, "csharp")
    f = "W.cs"
    assert c["defs"] == [[f, "IList.Add", 7], [f, "W", 6], [f, "Write", 2], [f, "Write", 4]]  # Write@2: its attribute
    assert c["edges"] == [[[f, "Write", 2], [f, "Write", 4], 3]]  # the delegation to the other overload
    assert c["external"] == []  # Flush is defined here (bodyless): neither an edge nor external


def test_source_extent_php_and_kotlin_bodies():
    php = ["  public function a() {", "    $s = '}';  # }", "    return 1;", "  }", "  abstract function b();"]
    assert scip_lang.source_extent(php, (0, 19), "php", 0) == [0, 19, 3, 3]
    assert scip_lang.source_extent(php, (4, 21), "php", 4) == []
    kt = ["  fun f(x: Int) =", "    g(x)", "  fun h(): Int", "  fun k() { \"${'}'}\" }"]
    assert scip_lang.source_extent(kt, (0, 7), "kotlin", 0) == [0, 7, 1, 8]  # an expression body on the next line
    assert scip_lang.source_extent(kt, (2, 7), "kotlin", 2) == []  # bodyless
    assert scip_lang.source_extent(kt, (3, 7), "kotlin", 3) == [3, 7, 3, len(kt[3])]  # a template holding `}`


KT = (
    "class B(val n: String) {\n"  # 0: an implicit primary constructor
    "  /** Docs. */\n"  # 1
    "  fun build(): B = builder(n)\n"  # 2
    "  fun builder(x: String): B { val m = x.length; return B(x) }\n"  # 3
    "  constructor(i: Int) : this(i.toString())\n"  # 4
    "}\n"
)
KP = "semanticdb maven . . "


def _typed(*r: int) -> bytes:
    if len(r) == 3:
        return _field(8, _field(1, r[0]) + _field(2, r[1]) + _field(3, r[2]))
    return _field(9, _field(1, r[0]) + _field(2, r[1]) + _field(3, r[2]) + _field(4, r[3]))


def _typed_enc(l0: int, c0: int, l1: int, c1: int) -> bytes:
    return _field(11, _field(1, l0) + _field(2, c0) + _field(3, l1) + _field(4, c1))


def test_kotlin_defs_and_named_calls_follow_the_engine(tmp_path):
    (tmp_path / "B.kt").write_text(KT)
    lines = KT.splitlines()
    build, builder, init0, init1 = KP + "B#build().", KP + "B#builder().", KP + "B#`<init>`().", KP + "B#`<init>`(+1)."
    length = KP + "kotlin/String#length().get()."  # a getter: not a named call

    def occ(rng: list[int], sym: str, definition: bool = False, enc: tuple[int, int, int, int] | None = None) -> bytes:
        body = _typed(*rng) + _field(2, sym) + (_field(3, 1) if definition else b"")
        return body + (_typed_enc(*enc) if enc else b"")

    occs = [
        occ([0, 0, 24], init0, True, (0, 0, 5, 1)),  # range = the whole class header: no `constructor` keyword
        occ(_at(lines, 2, "build"), build, True, (1, 2, 2, len(lines[2]))),  # enclosing from the KDoc
        occ(_at(lines, 2, "builder"), builder),
        occ(_at(lines, 3, "builder"), builder, True, (3, 2, 3, len(lines[3]))),
        occ(_at(lines, 3, "length"), length),
        occ(_at(lines, 3, "B", 1), init0),
        occ([4, 2, 4, len(lines[4])], init1, True, (4, 2, 4, len(lines[4]))),
        occ(_at(lines, 4, "this"), init0),
    ]
    syms = [_sym(build, 26), _sym(builder, 26), _sym(init0, 9), _sym(init1, 9)]
    c = sc.contract_from_index(_index("B.kt", occs, syms), tmp_path, "kotlin")
    f = "B.kt"
    # build's line is after its KDoc; the implicit primary constructor is no def; the secondary is `constructor`
    assert c["defs"] == [[f, "build", 3], [f, "builder", 4], [f, "constructor", 5]]
    assert c["edges"] == [[[f, "build", 3], [f, "builder", 4], 3]]  # B(x) / this(...) reach a non-def
    assert c["external"] == []  # `x.length` is a property read, not a call


def test_kotlin_calls_need_no_parenthesis_but_references_are_not_calls():
    assert scip_lang.is_call(["  run { x }"], (0, 2, 0, 5), "kotlin")  # a trailing lambda
    assert scip_lang.is_call(["a to b"], (0, 2, 0, 4), "kotlin")  # infix
    assert not scip_lang.is_call(["list.map(::f)"], (0, 11, 0, 12), "kotlin")
    assert not scip_lang.is_call([" * See [f]."], (0, 8, 0, 9), "kotlin")  # a KDoc link
    assert not scip_lang.is_call(["  run { x }"], (0, 2, 0, 5), "csharp")


def test_php_keeps_its_constructor_name():
    assert scip_lang.name("scip-php composer composer dev App/Foo#__construct().", "php") == "__construct"
    assert sc._name("scip-php composer composer dev App/Foo#__construct().", "", "php") == "__construct"
    assert sc._ctor_names("php") >= {"__construct", "<init>"}


def test_m3_scope_excludes_tests_examples_vendored_and_generated_code():
    for path in (
        "Src/Newtonsoft.Json.Tests/A.cs",
        "Src/Newtonsoft.Json.TestConsole/P.cs",
        "kotlinpoet/src/jvmTest/kotlin/A.kt",
        "interop/ksp/test-processor/src/P.kt",
        "src/Composer/FooTest.php",
        "vendor/x/y.php",
        "doc/a.php",
    ):
        assert scip_lang.m3_excluded(path, ""), path
    assert scip_lang.m3_excluded("src/A.kt", "// Code generated by x. DO NOT EDIT.")
    assert not scip_lang.m3_excluded("src/Composer/Factory.php", "<?php")
    assert not scip_lang.m3_excluded("Src/Newtonsoft.Json/Testable.cs", "")


def test_scope_keeps_in_scope_code_and_lists_the_indexed_files():
    a, t, g = ["src/A.php", "f", 1], ["tests/T.php", "t", 1], ["src/gen.php", "g", 1]
    contract = {
        "defs": [a, t, g, ["src/x.js", "j", 1]],
        "edges": [[t, a, 2], [a, g, 3]],
        "external": [[a, "strlen"], [t, "strlen"]],
    }
    heads = {"src/gen.php": "<?php // auto-generated"}
    out = scip_lang.scope(contract, "php", lambda p: heads.get(p, ""))
    assert out["defs"] == [a] and out["edges"] == [] and out["external"] == [[a, "strlen"]]
    assert out["indexed"] == ["src/A.php"]
    # the gate then scores only those files: an engine link out of any other is out of scope
    graph = cr.load_contract(out)
    assert not graph.is_vendored("src/A.php")
    assert graph.is_vendored("src/Other.php") and graph.is_vendored("tests/T.php") and graph.is_vendored(None)
    assert cr.scope_vendored(graph, ("src/A",)).is_vendored("src/A.php")  # a vendored prefix still applies
    assert not cr.load_contract({"defs": [], "edges": []}).is_vendored("anything.php")  # unscoped: as before
