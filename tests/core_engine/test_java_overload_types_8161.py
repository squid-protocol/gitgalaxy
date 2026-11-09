"""#8161 (J1): Java overloads of one arity are chosen by argument type (core/java_arg_types.py). The detector
records each call site's argument types and each method's declared parameter types; the resolver links the one
overload Java's rules pick (strict, then loose invocation, then the most specific), and only when that is certain:
every argument typed, every candidate's parameters read, no candidate only maybe applicable."""

import pytest

from gitgalaxy.core import java_arg_types as J
from gitgalaxy.core.call_resolver import CONFIDENT_RESOLUTIONS, resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _parse(code: str) -> dict:
    return StructuralExtractor("java", LANGUAGE_DEFINITIONS).splice(code, "")


def _sites(files: dict[str, str]):
    parsed = []
    for path, code in files.items():
        p = _parse(code)
        parsed.append({"path": path, "lang_id": "java", "functions": p["functions"], "classes": p["classes"]})
    sites, _ = resolve_calls(parsed)
    return sites


ARRAYS = (
    "package p;\n"
    "public class ArrayU {\n"
    "    public static int indexOf(int[] a, int v) { return 0; }\n"  # 3
    "    public static int indexOf(long[] a, long v) { return 1; }\n"  # 4
    "    public static int indexOf(Object[] a, Object v) { return 2; }\n"  # 5
    '    public static String pad(int n) { return ""; }\n'  # 6
    '    public static String pad(Integer n) { return ""; }\n'  # 7
    "    public static String pad(String s) { return s; }\n"  # 8
    '    public static String pad(char c) { return ""; }\n'  # 9
    "}\n"
)


def _targets(client: str, caller: str, callee: str) -> list[tuple[str, int | None]]:
    sites = _sites({"src/p/ArrayU.java": ARRAYS, "src/p/Client.java": client})
    return sorted((s["step"], s["dst_line"]) for s in sites if s["src_name"].endswith(caller) and s["callee"] == callee)


def test_same_arity_overloads_are_chosen_by_argument_type():
    client = (
        "package p;\n"
        "public class Client {\n"
        "    boolean has(int[] xs, long[] ls, String[] ss) {\n"
        '        return ArrayU.indexOf(xs, 3) + ArrayU.indexOf(ls, 2L) + ArrayU.indexOf(ss, "a") > 0;\n'
        "    }\n"
        "}\n"
    )
    assert _targets(client, "has", "indexOf") == [("qualified", 3), ("qualified", 4), ("qualified", 5)]


def test_widening_boxing_and_char_literals_follow_java():
    client = (
        "package p;\n"
        "public class Client {\n"
        "    void a(short s) { ArrayU.pad(s); }\n"  # strict: short widens to int, before boxing
        "    void b(Integer i) { ArrayU.pad(i); }\n"  # exact
        "    void c() { ArrayU.pad('x'); }\n"  # a char literal, not a String
        '    void d() { ArrayU.pad("x"); }\n'
        "    void e(Long l) { ArrayU.pad(l); }\n"  # no overload applies: stays ambiguous
        "}\n"
    )
    assert _targets(client, "a", "pad") == [("qualified", 6)]
    assert _targets(client, "b", "pad") == [("qualified", 7)]
    assert _targets(client, "c", "pad") == [("qualified", 9)]
    assert _targets(client, "d", "pad") == [("qualified", 8)]
    assert [step for step, _ in _targets(client, "e", "pad")] == ["overload"]


def test_an_untyped_argument_leaves_the_overload_row():
    client = (
        "package p;\n"
        "public class Client {\n"
        "    int f(int[] xs) { return ArrayU.indexOf(xs, compute()); }\n"
        "    int compute() { return 1; }\n"
        "}\n"
    )
    ((step, _),) = _targets(client, "f", "indexOf")
    assert step == "overload"


def test_one_undecided_site_keeps_the_arity_ambiguous_and_decided_ones_link():
    client = (
        "package p;\n"
        "public class Client {\n"
        "    void g(int[] xs, Object o) { ArrayU.indexOf(xs, 1); ArrayU.indexOf(xs, o.hashCode()); }\n"
        "}\n"
    )
    rows = _targets(client, "g", "indexOf")
    assert ("qualified", 3) in rows and any(step == "overload" for step, _ in rows)


def test_repo_subtypes_decide_and_unknown_reference_types_do_not():
    shapes = (
        "package p;\n"
        "public class Shape { }\n"
        "class Circle extends Shape { }\n"
        "class Other { }\n"
        "class Draw {\n"
        "    static void put(Shape s) { }\n"  # 6
        "    static void put(Other o) { }\n"  # 7
        "    static void run(Circle c, Thing t) { put(c); put(t); }\n"
        "}\n"
    )
    sites = _sites({"src/p/Shapes.java": shapes})
    rows = sorted((s["step"], s["dst_line"]) for s in sites if s["src_name"].endswith("run") and s["callee"] == "put")
    assert ("class", 6) in rows  # Circle extends Shape, and is no Other
    assert any(r[0] == "overload" for r in rows)  # Thing: a class the repo does not define
    assert all(s["resolution"] in CONFIDENT_RESOLUTIONS for s in sites if s.get("dst_line") == 6)


def test_detector_records_site_types_and_parameter_types():
    code = (
        "class A {\n"
        "    private long[] cache;\n"
        "    void f(final int[] xs, String... rest) {\n"
        "        var b = new StringBuilder(); char c = 'q'; // g(1, 2, 3)\n"
        '        g(xs, this.cache, "s,t", c, b, (long) xs.length, xs.length, null, new int[2][3]);\n'
        "        g(xs, x -> x, rest);\n"
        "    }\n"
        "    void g(int[] a, long[] b, String s, char c, StringBuilder sb, long n, int m, Object o, int[][] g) { }\n"
        "}\n"
    )
    funcs = {f["name"]: f for f in _parse(code)["functions"]}
    assert funcs["f"]["param_types"] == ["int[]", "String[]"]
    assert funcs["g"]["param_types"] == [
        "int[]", "long[]", "String", "char", "StringBuilder", "long", "int", "Object", "int[][]",
    ]  # fmt: skip
    assert funcs["f"]["calls_out_arg_types"]["g"] == [
        ["int[]", "long[]", "String", "char", "StringBuilder", "long", "int", "null", "int[][]"],
        ["int[]", "", "String[]"],
    ]


@pytest.mark.parametrize(
    "candidates,args,want",
    [
        ([["int[]", "int"], ["long[]", "long"]], ["long[]", "int"], 1),  # int widens to long
        ([["long"], ["double"]], ["int"], 0),  # both apply; long is more specific
        ([["Object"], ["String"]], ["null"], 1),  # null: the most specific reference
        ([["Object"], ["String"]], ["Foo"], 0),  # nothing extends final String
        ([["CharSequence"], ["Foo"]], ["String"], 0),
        ([["T[]", "T"], ["int[]", "int"]], ["int[]", "int"], 1),  # exact beats a type variable
        ([["T[]", "T"], ["int[]", "int"]], ["String[]", "String"], None),  # a type variable's bound is unread
        ([["Foo"], ["Bar"]], ["Baz"], None),  # unknown subtyping
        ([["int"], ["String"]], [""], None),  # an untyped argument
        ([["int"], None], ["int"], None),  # an unread parameter list
        ([["Integer"], ["long"]], ["int"], 1),  # strict widening before boxing
    ],
)
def test_choose_follows_jls_and_refuses_when_unsure(candidates, args, want):
    assert J.choose(candidates, args) == want


def test_mask_keeps_length_quotes_and_lines():
    src = 'f("a,b", \'c\'); // g(1)\n/* h(\n2) */ k("""\nx""")'
    m = J.mask_literals(src)
    assert len(m) == len(src) and m.count("\n") == src.count("\n")
    assert '"   "' in m and "' '" in m and "g(" not in m and "h(" not in m


def test_scans_are_linear():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extraction" / "languages"))
    from linear_assert import assert_linear

    def run(n):
        text = "int" + " " * n + "\n" + "(" * (n // 4) + "g(" + "x, " * (n // 8) + '"' + " " * n
        J.declared_value_types(text)
        for end in J.call_sites(text, "g"):
            J.site_arg_types(text, end, {}, {})
        J.mask_literals(text)

    assert_linear(run, 6000, 12000)


def test_a_unicode_method_name_keeps_its_parameter_types():
    # the unicode gauntlet: a name with combining marks (`नाम`, a ZWJ) must read like its ASCII twin
    for name in ("probeनाम", "probeक्‍ष", "probeé"):
        code = f"class A {{\n    int {name}(int x) {{ return {name}(1) + g(x); }}\n    int g(int y) {{ return y; }}\n}}\n"
        funcs = {f["name"]: f for f in _parse(code)["functions"]}
        assert funcs[name]["param_types"] == ["int"]
