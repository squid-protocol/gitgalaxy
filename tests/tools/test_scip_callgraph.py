"""The shared SCIP -> call-graph contract adapter (#3783). Each case builds a small SCIP
index by hand (the protobuf wire format is simple enough), so no indexer, JDK or network
is needed; the scip-java gate itself is the end-to-end check."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import scip_callgraph as sc


def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _field(num: int, payload: bytes | int | str) -> bytes:
    if isinstance(payload, int):
        return _varint(num << 3) + _varint(payload)
    data = payload.encode() if isinstance(payload, str) else payload
    return _varint(num << 3 | 2) + _varint(len(data)) + data


def _packed(nums: list[int]) -> bytes:
    return b"".join(_varint(n) for n in nums)


def _occ(rng: list[int], symbol: str, definition: bool = False, enclosing: list[int] | None = None) -> bytes:
    body = _field(1, _packed(rng)) + _field(2, symbol) + (_field(3, 1) if definition else b"")
    return body + (_field(7, _packed(enclosing)) if enclosing else b"")


def _sym(symbol: str, kind: int, display: str = "") -> bytes:
    return _field(1, symbol) + _field(5, kind) + (_field(6, display) if display else b"")


def _index(path: str, occurrences: list[bytes], symbols: list[bytes]) -> bytes:
    tool = _field(2, _field(1, "scip-java") + _field(2, "0.12.3"))
    doc = _field(1, path) + b"".join(_field(2, o) for o in occurrences) + b"".join(_field(3, s) for s in symbols)
    return _field(1, tool) + _field(2, doc)


JAVA = (
    "class A {\n"  # 0
    '  A() { helper(1); helper("s"); }\n'  # 1: a constructor calling two overloads
    "  void helper(int x) { System.out.println(x); Runnable r = A::other; }\n"  # 2: external + method ref
    "  void helper(String s) { new Runnable() { public void run() { other(); } }; }\n"  # 3: anonymous class
    "  void other() {}\n"  # 4
    "  abstract void sig();\n"  # 5: bodyless
    "}\n"
)
P = "semanticdb maven . . "
CTOR, H1, H2, OTHER, SIG = (
    P + "A#`<init>`().",
    P + "A#helper().",
    P + "A#helper(+1).",
    P + "A#other().",
    P + "A#sig().",
)
PRINTLN = "semanticdb maven jdk 21 java/io/PrintStream#println(+1)."


def _col(line: int, text: str, nth: int = 0) -> list[int]:
    row, start = JAVA.splitlines()[line], -1
    for _ in range(nth + 1):
        start = row.index(text, start + 1)
    return [line, start, start + len(text)]


def _java_index() -> bytes:
    lines = JAVA.splitlines()
    whole = lambda n: [n, 2, n, len(lines[n])]  # noqa: E731
    occ = [
        _occ(_col(1, "A"), CTOR, True, whole(1)),
        _occ(_col(1, "helper"), H1),
        _occ(_col(1, "helper", 1), H2),
        _occ(_col(2, "helper"), H1, True, whole(2)),
        _occ(_col(2, "println"), PRINTLN),
        _occ(_col(2, "other"), OTHER),  # A::other -- a method reference, not a call
        _occ(_col(3, "helper"), H2, True, whole(3)),
        _occ(_col(3, "run"), "local 1", True, [3, lines[3].index("public"), 3, lines[3].rindex("}") - 3]),
        _occ(_col(3, "other"), OTHER),
        _occ(_col(4, "other"), OTHER, True, whole(4)),
        _occ(_col(5, "sig"), SIG, True, whole(5)),
    ]
    syms = [
        _sym(CTOR, 9, "<init>"),
        _sym(H1, 26),
        _sym(H2, 26),
        _sym(OTHER, 26),
        _sym(SIG, 66),
        _sym("local 1", 26, "run"),
    ]
    return _index("src/A.java", occ, syms)


def test_read_index_decodes_documents_occurrences_and_symbols():
    tool, docs = sc.read_index(_java_index())
    assert tool == {"name": "scip-java", "version": "0.12.3"}
    (doc,) = docs
    assert doc.path == "src/A.java" and len(doc.occurrences) == 11
    assert doc.symbols[SIG] == (66, "") and doc.symbols["local 1"] == (26, "run")
    assert doc.occurrences[0].is_definition and doc.occurrences[0].enclosing == [1, 2, 1, len(JAVA.splitlines()[1])]


def test_java_contract_follows_the_engine_naming_and_counts_only_calls(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "A.java").write_text(JAVA)
    c = sc.contract_from_index(_java_index(), tmp_path, "java")
    f = "src/A.java"
    # the constructor is named after its class, each overload keeps its own line, the anonymous
    # class's method is a def, and the bodyless `sig` is not
    assert c["defs"] == [[f, "A", 2], [f, "helper", 3], [f, "helper", 4], [f, "other", 5], [f, "run", 4]]
    assert c["edges"] == [
        [[f, "A", 2], [f, "helper", 3], 2],
        [[f, "A", 2], [f, "helper", 4], 2],
        [[f, "run", 4], [f, "other", 5], 4],  # the anonymous class's call, not helper(String)'s
    ]  # `A::other` is a method reference: no edge
    assert c["external"] == [[[f, "helper", 3], "println"]]
    assert (c["tool"], c["version"], c["files"]) == ("scip-java", "0.12.3", 1)


def test_typescript_names_constructors_and_const_bound_functions(tmp_path):
    ts = "export const f = (x: number) => g(x);\nexport function g(y: number) { return new K(); }\nclass K { constructor() {} }\n"
    (tmp_path / "a.ts").write_text(ts)
    p = "scip-typescript npm pkg 1.0.0 `a.ts`/"
    lines = ts.splitlines()

    def at(line: int, text: str) -> list[int]:
        s = lines[line].index(text)
        return [line, s, s + len(text)]

    occ = [
        _occ(at(0, "f"), p + "f.", True, [0, 13, 0, len(lines[0]) - 1]),
        _occ(at(0, "g"), p + "g()."),
        _occ(at(1, "g"), p + "g().", True, [1, 7, 1, len(lines[1])]),
        _occ(at(1, "K"), p + "K#"),
        _occ(at(2, "K"), p + "K#", True, [2, 0, 2, len(lines[2])]),
        _occ(at(2, "constructor"), p + "K#`<constructor>`().", True, [2, 10, 2, 26]),
    ]
    c = sc.contract_from_index(_index("a.ts", occ, []), tmp_path, "typescript")
    assert c["defs"] == [["a.ts", "constructor", 3], ["a.ts", "f", 1], ["a.ts", "g", 2]]
    assert c["edges"] == [[["a.ts", "f", 1], ["a.ts", "g", 2], 1], [["a.ts", "g", 2], ["a.ts", "constructor", 3], 2]]


def test_descriptors_parse_backticks_methods_and_types():
    assert sc._descriptors("scip-typescript npm zod 4.6.5 src/`util.ts`/assertEqual().") == [
        ("src", "/"),
        ("util.ts", "/"),
        ("assertEqual", "()."),
    ]
    assert sc._descriptors(P + "com/google/gson/JsonArray#`<init>`(+1).")[-2:] == [
        ("JsonArray", "#"),
        ("<init>", "()."),
    ]
    assert sc._name(P + "com/google/gson/JsonArray#`<init>`(+1).", "", "java") == "JsonArray"
    assert sc._name(P + "com/google/gson/JsonArray#add(+4).", "", "java") == "add"
    assert sc._name(P + "com/google/gson/JsonArray#elements.", "", "java") == "elements"  # a field: filtered by kind


def test_compare_reports_agreement_on_each_side():
    edge = lambda a, b: [["x.ts", a, 1], ["x.ts", b, 2], 1]  # noqa: E731
    a = {"tool": "tsc", "version": "6", "defs": [[]] * 3, "edges": [edge("f", "g"), edge("f", "h")]}
    b = {"tool": "scip-typescript", "version": "0.4", "defs": [[]] * 3, "edges": [edge("f", "g"), edge("g", "h")]}
    text = sc.compare(a, b)
    assert "| in both | 1 | 1 |" in text and "| only here | 1 | 1 |" in text
    assert "x.ts:f -> x.ts:h" in text and "x.ts:g -> x.ts:h" in text


TT = (
    "class T<X> {\n"  # 0
    "  protected T() { }\n"  # 1
    "  private T(Map<String, X> m) { }\n"  # 2: a comma inside the parameter's type
    "  void use() { new T<String>() { }; new T<String>(m) { }; }\n"  # 3: anonymous subclasses
    "}\n"
)


def test_anonymous_class_reference_picks_the_constructor_by_argument_count(tmp_path):
    # #4124: `new T<X>() { }` references the CLASS `T#`, not a constructor. With two
    # constructors, a one-entry map sent every such reference to the last one; scip-java's
    # side then called the engine's right `T()` link a wrong overload (137 on gson).
    (tmp_path / "T.java").write_text(TT)
    lines = TT.splitlines()

    def at(line: int, text: str, nth: int = 0) -> list[int]:
        start = -1
        for _ in range(nth + 1):
            start = lines[line].index(text, start + 1)
        return [line, start, start + len(text)]

    whole = lambda n: [n, 2, n, len(lines[n])]  # noqa: E731
    cls, c0, c1, use = P + "T#", P + "T#`<init>`().", P + "T#`<init>`(+1).", P + "T#use()."
    occ = [
        _occ(at(1, "T"), c0, True, whole(1)),
        _occ(at(2, "T"), c1, True, whole(2)),
        _occ(at(3, "use"), use, True, whole(3)),
        _occ(at(3, "T", 0), cls),
        _occ(at(3, "T", 1), cls),
    ]
    syms = [_sym(c0, 9, "<init>"), _sym(c1, 9, "<init>"), _sym(use, 26), _sym(cls, 7)]
    c = sc.contract_from_index(_index("T.java", occ, syms), tmp_path, "java")
    assert c["edges"] == [[["T.java", "use", 4], ["T.java", "T", 2], 4], [["T.java", "use", 4], ["T.java", "T", 3], 4]]


def test_arg_count_skips_type_arguments_literals_and_nesting():
    assert sc._arg_count(["<String>() { }"], 0, 0) == 0
    assert sc._arg_count(["(a, f(b, c), \"x,y\", ',')"], 0, 0) == 4
    assert sc._arg_count(["(Map<String, X> m, int n)"], 0, 0, declaration=True) == 2
    assert sc._arg_count(["(", "  a,", "  b)"], 0, 0) == 2  # across lines
    assert sc._arg_count([" = 1;"], 0, 0) is None


RUST = (
    "struct S;\n"  # 0
    "trait T {\n"  # 1
    "    fn sig(&self);\n"  # 2: no default body
    "    fn dflt(&self) { helper::<u8>(1); }\n"  # 3: turbofish call
    "}\n"  # 4
    "impl S {\n"  # 5
    "    fn new() -> S { S }\n"  # 6
    '    fn go(&self) { Self::new(); println!("x"); let _ = Vec::<u8>::len(&v); }\n'  # 7
    "}\n"  # 8
    "fn helper<X>(x: X) { let f = go; }\n"  # 9: `go` as a value, not a call
)
RP = "rust-analyzer cargo demo 0.1.0 "


@pytest.mark.parametrize("enclose", [True, False], ids=["enclosing_range", "no_enclosing_range"])
def test_rust_contract_names_impl_methods_and_skips_bodyless_trait_methods(tmp_path, enclose):
    # rust-analyzer 1.90.0 emits no enclosing_range at all: the extent is read from the source
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "lib.rs").write_text(RUST)
    lines = RUST.splitlines()

    def at(line: int, text: str, nth: int = 0) -> list[int]:
        start = -1
        for _ in range(nth + 1):
            start = lines[line].index(text, start + 1)
        return [line, start, start + len(text)]

    whole = lambda n: [n, 4, n, len(lines[n])] if enclose else None  # noqa: E731
    sig, dflt, new, go = RP + "T#sig().", RP + "T#dflt().", RP + "impl#[`S`]new().", RP + "impl#[`S`]go()."
    helper = RP + "helper()."
    occ = [
        _occ(at(2, "sig"), sig, True, whole(2)),
        _occ(at(3, "dflt"), dflt, True, whole(3)),
        _occ(at(3, "helper"), helper),
        _occ(at(6, "new"), new, True, whole(6)),
        _occ(at(7, "go"), go, True, whole(7)),
        _occ(at(7, "new"), new),
        _occ(at(7, "println"), "rust-analyzer cargo std 1.90.0 macros/println!"),
        _occ(at(7, "len"), "rust-analyzer cargo alloc 1.90.0 vec/Vec#len()."),
        _occ([9, 3, 9, 9], helper, True, [9, 0, 9, len(lines[9])] if enclose else None),
        _occ(at(9, "go"), go),
    ]
    syms = [
        _sym(sig, 26),
        _sym(dflt, 26),
        _sym(new, 26),
        _sym(go, 26),
        _sym(helper, 17),
        _sym("rust-analyzer cargo alloc 1.90.0 vec/Vec#len().", 26),
    ]
    index = _index("src/lib.rs", occ, syms)
    c = sc.contract_from_index(index, tmp_path, "rust")
    f = "src/lib.rs"
    # `sig` has no body so it is no def; the macro and the `go` value are not call edges
    assert c["defs"] == [[f, "dflt", 4], [f, "go", 8], [f, "helper", 10], [f, "new", 7]]
    assert c["edges"] == [[[f, "dflt", 4], [f, "helper", 10], 4], [[f, "go", 8], [f, "new", 7], 8]]
    assert c["external"] == [[[f, "go", 8], "len"]]


def test_rust_descriptors_keep_a_quoted_slice_type_whole():
    sym = RP + "impl#[`[u8]`]first()."
    assert sc._descriptors(sym)[-1] == ("first", "().")
    assert sc._name(sym, "", "rust") == "first"


def test_rust_symbols_of_real_rust_analyzer_output_keep_their_method_name():
    # shapes read from `rust-analyzer scip` on serde-rs/json (1.90.0): a generic inherent impl,
    # a trait impl, a free fn, a nested-module method
    for sym, name in (
        (RP + "de/impl#[`Deserializer<R>`]peek().", "peek"),
        (RP + "error/impl#[Error][Error]custom().", "custom"),
        (RP + "value/de/impl#[`Value`][`Deserializer<'de>`]deserialize_any().", "deserialize_any"),
        (RP + "ser/invalid_number().", "invalid_number"),
    ):
        assert sc._name(sym, "", "rust") == name


def test_rust_enclosing_reads_the_extent_of_a_fn_from_source():
    src = [
        "fn a(x: [u8; 4]) -> u32 {",  # 0: `;` inside [] is not a terminator
        '    let s = "}{"; let c = \'{\'; let r = r#"}"#; // }',  # 1: braces in a string, char, raw string, comment
        '    /* } /* } */ } */ let l: &\'static str = "";',  # 2: nested block comment, a lifetime
        "    if x { 1 } else { 2 }",  # 3
        "}",  # 4
        "trait T { fn decl(&self) -> [u8; 2]; fn d(&self) {} }",  # 5
    ]
    end = lambda n, name: src[n].index(name) + len(name)  # noqa: E731
    assert sc._rust_enclosing(src, (0, 4)) == [0, 4, 4, 1]
    # a bodyless declaration ends at its `;`, so it has no body; the next fn on the line does
    assert sc._has_body(src, sc._rust_enclosing(src, (5, end(5, "decl"))), (5, end(5, "decl"))) is False
    d = src[5].rindex("fn d") + 4
    assert sc._rust_enclosing(src, (5, d)) == [5, d, 5, len(src[5]) - 2]
    assert sc._rust_enclosing(["fn open() {", "    x"], (0, 7)) == []  # unterminated
