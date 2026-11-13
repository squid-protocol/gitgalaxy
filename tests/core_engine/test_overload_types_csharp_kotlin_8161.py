"""#8161 (PR 5): C# and Kotlin overloads are chosen by argument type (core/overload_types.py), J1's port. The
detector records each call site's argument types and each unit's parameter types and accepted counts (defaults,
`params`, `vararg`); the resolver links the overload the language picks, only when certain."""

import pytest

from gitgalaxy.core import overload_types as O
from gitgalaxy.core.call_resolver import resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _parse(code: str, lang: str) -> dict:
    return StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")


def _targets(files: dict[str, str], lang: str, caller: str, callee: str) -> list[tuple[str, int | None]]:
    parsed = []
    for path, code in files.items():
        p = _parse(code, lang)
        parsed.append({"path": path, "lang_id": lang, "functions": p["functions"], "classes": p["classes"]})
    sites, _ = resolve_calls(parsed)
    return sorted((s["step"], s["dst_line"]) for s in sites if s["src_name"].endswith(caller) and s["callee"] == callee)


WRITER = (
    "namespace N {\n"
    "public class W {\n"
    "    public void Put(int v) { }\n"  # 3
    "    public void Put(decimal? v) { }\n"  # 4
    "    public void Put(string s) { }\n"  # 5
    "    public void Put(object o, int depth = 0) { }\n"  # 6
    "    public void Log(string format, params object[] args) { }\n"  # 7
    "    public void Log(string message) { }\n"  # 8
    '    public void A(decimal? d, long n, Holder h) { Put(d); Put(7); Put("s"); Put(h, 2); Put(n); }\n'  # 9
    '    public void B(DateTime t) { Log("x"); Log("{0} {1}", 1, 2); Put(t); }\n'  # 10
    "}\n"
    "public class Holder { }\n"
    "}\n"
)


def test_csharp_overloads_follow_the_argument_types():
    rows = _targets({"src/W.cs": WRITER}, "csharp", "A", "Put")
    # decimal? exact, an int literal is int, a string, `h, 2` reaches only the (object, int) one by count;
    # a long goes to decimal? (long -> decimal is implicit; no int / string / object-by-count overload fits)
    assert rows == [("class", 3), ("class", 4), ("class", 5), ("class", 6)]


def test_csharp_params_and_defaults_widen_the_counts():
    rows = _targets({"src/W.cs": WRITER}, "csharp", "B", "Log")
    assert ("class", 7) in rows and ("class", 8) in rows  # `Log("x")` is the exact one, 3 arguments the params one
    # a DateTime (a type the scan does not know) to Put(int) may be a user-defined conversion: undecided
    assert _targets({"src/W.cs": WRITER}, "csharp", "B", "Put") == [("overload", 6)]


POET = (
    "class Spec {\n"
    "    fun addModifiers(vararg modifiers: KModifier): Spec = this\n"  # 2
    "    fun addModifiers(modifiers: Iterable<KModifier>): Spec = this\n"  # 3
    "    fun builder(name: String, type: TypeName, vararg mods: KModifier): Spec = Spec()\n"  # 4
    "    fun builder(name: String, type: Type, vararg mods: KModifier): Spec = builder(name, type.asTypeName(), *mods)\n"  # 5
    "    fun use(ms: List<KModifier>, t: TypeName) {\n"  # 6
    "        addModifiers(KModifier.PUBLIC, KModifier.FINAL)\n"
    "        addModifiers(ms)\n"
    '        builder("n", t)\n'
    "    }\n"
    "}\n"
)


def test_kotlin_vararg_iterable_and_defaults():
    rows = _targets({"src/Spec.kt": POET}, "kotlin", "use", "addModifiers")
    # two arguments: only the vararg one takes two; `addModifiers(ms)` stays undecided (List vs Iterable needs
    # the library's lineage), an `overload` row, never an edge
    assert rows == [("class", 2), ("overload", 3)]
    built = _targets({"src/Spec.kt": POET}, "kotlin", "use", "builder")
    assert built == [("class", 4)]  # a TypeName is exactly TypeName; nothing makes it a java Type


def test_kotlin_expression_body_delegation_to_another_overload_is_a_call():
    # `builder(name, type.asTypeName(), *mods)` inside builder@5 is a sibling overload, not recursion
    rows = _targets({"src/Spec.kt": POET}, "kotlin", "builder", "builder")
    assert rows == [("overload", 4)]  # kept (not pruned as recursion); `type.asTypeName()` is untyped here


def test_detector_records_csharp_and_kotlin_types_and_counts():
    cs = (
        "class A {\n"
        "    private int[] cache;\n"
        "    void F(ref int x, [NotNull] string? s = null, params object[] rest) {\n"
        "        var b = new StringBuilder(); char c = 'q'; decimal? m = null;\n"
        '        G(this.cache, "s", c, b, 1L, 2.5m, (long)x, m, nameof(x));\n'
        "    }\n"
        "    void G(int[] a, string s, char c, StringBuilder sb, long n, decimal d, long l, decimal? m, string k) { }\n"
        "}\n"
    )
    funcs = {
        f["name"]: f
        for f in _parse(
            cs
            + "public static class E\n{\n    public static string FormatWith(this string f, int a, int b = 0)\n    {\n        return f;\n    }\n}\n",
            "csharp",
        )["functions"]
    }
    assert funcs["FormatWith"]["param_types"] == ["int", "int"]  # an extension's `this` receiver is no argument
    assert funcs["FormatWith"]["arity_range"] == [1, 2, 2]
    assert funcs["F"]["param_types"] == ["int", "string", "object[]"]
    assert funcs["F"]["arity_range"] == [1, None, 3]
    assert funcs["F"]["calls_out_arg_types"]["G"] == [
        ["int[]", "string", "char", "StringBuilder", "long", "decimal", "long", "decimal?", "string"]
    ]
    kt = (
        "class K(val name: String) {\n"
        "    fun f(x: Int, label: String? = null, vararg more: Any) {\n"
        '        val s = "a"; val n = 3L; val k = ClassName("p", "K")\n'
        "        g(x, s, n, label, k, K::class, K::class.java, name) { }\n"
        "    }\n"
        "    fun g(a: Int, b: String, c: Long, d: String?, e: ClassName, f: KClass<*>, h: Class<*>, i: String, j: () -> Unit) { }\n"
        "}\n"
    )
    funcs = {f["name"]: f for f in _parse(kt, "kotlin")["functions"]}
    assert funcs["f"]["param_types"] == ["Int", "String?", "Any[]"]
    assert funcs["f"]["arity_range"] == [1, None, 3]
    assert funcs["f"]["calls_out_arities"]["g"] == [9]  # the trailing lambda is an argument
    assert funcs["f"]["calls_out_arg_types"]["g"] == [
        ["Int", "String", "Long", "String?", "ClassName", "KClass", "Class", "String", ""]
    ]


@pytest.mark.parametrize(
    "lang,candidates,args,want",
    [
        ("csharp", [(["int"], False), (["long"], False)], ["int"], 0),
        ("csharp", [(["long"], False), (["double"], False)], ["int"], 0),  # long converts to double: more specific
        ("csharp", [(["decimal?"], False), (["DateTime"], False)], ["decimal?"], 0),
        ("csharp", [(["decimal"], False), (["string"], False)], ["decimal?"], None),  # no Nullable -> T
        ("csharp", [(["object"], False), (["string"], False)], ["null"], 1),
        ("csharp", [(["byte"], False), (["string"], False)], ["int"], None),  # a constant may fit a byte
        ("csharp", [(["JToken"], False), (["string"], False)], ["int"], None),  # a user-defined implicit operator
        ("csharp", [(["string", "object[]"], True), (["string"], False)], ["string"], 1),  # not the expanded form
        ("csharp", [(["string", "object[]"], True), (["string"], False)], ["string", "int", "int"], 0),
        ("kotlin", [(["Long"], False), (["String"], False)], ["Int"], None),  # an integer literal may be a Long
        ("kotlin", [(["Int"], False), (["Long"], False)], ["Int"], 0),
        ("kotlin", [(["String"], False), (["Any"], False)], ["String?"], None),  # String? passes neither... Any? only
        ("kotlin", [(["String?"], False), (["Int"], False)], ["null"], 0),
        ("kotlin", [(["KModifier[]"], True), (["Iterable"], False)], ["KModifier", "KModifier"], 0),
        ("kotlin", [(["TypeName"], False), (["Type"], False)], [""], None),
    ],
)
def test_choose_follows_the_language_and_refuses_when_unsure(lang, candidates, args, want):
    assert O.choose(candidates, args, lang) == want


def test_scans_are_linear():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extraction" / "languages"))
    from linear_assert import assert_linear

    def run(n):
        for lang in ("csharp", "kotlin"):
            text = "int" + " " * n + "\n" + "(" * (n // 4) + "g(" + "x: " * (n // 8) + '"' + " " * n
            O.declared_value_types(text, lang)
            for end in O.name_sites(text).get("g", ()):
                O.site_arg_types(text, end, {}, {}, lang)
            O.param_types(text, 3, lang)

    assert_linear(run, 6000, 12000)
