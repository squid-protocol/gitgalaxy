"""#8161 (PR 5): a Kotlin extension function (`fun String.escapeIfKeyword()`) is free, yet a call through a receiver
reaches it (`name.escapeIfNotJavaIdentifier().escapeIfKeyword()`): 399 of kotlinpoet's reference edges were named
but never linked. It is a confident link only as the one definition of the name; beside a same-named extension on
another receiver type (or a method) the receiver the scan cannot type makes it the ambiguous `receiver` guess."""

from gitgalaxy.core.call_resolver import EXTENSION_SHAPE, resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _parse(code: str) -> dict:
    return StructuralExtractor("kotlin", LANGUAGE_DEFINITIONS).splice(code, "")


UTIL = (
    "package p\n"
    "internal fun String.escapeIfKeyword(): String = this\n"  # 2
    "internal fun String.escapeIfNotJavaIdentifier(): String = this\n"  # 3
    "fun plain(x: Int): Int = x\n"
)
NAMES = "package p\nfun KClass<*>.asClassName(): ClassName = ClassName()\n"  # 2
REFLECT = "package p\nfun Class<*>.asClassName(): ClassName = ClassName()\n"  # 2
USE = (
    "package p\n"
    "class Spec {\n"
    "    fun emit(name: String, k: Any): String {\n"
    "        k.asClassName()\n"
    "        return name.escapeIfNotJavaIdentifier().escapeIfKeyword()\n"
    "    }\n"
    "}\n"
)


def test_extension_functions_are_marked():
    shapes = {f["name"]: f.get("def_shape") for f in _parse(UTIL)["functions"]}
    assert shapes == {"escapeIfKeyword": EXTENSION_SHAPE, "escapeIfNotJavaIdentifier": EXTENSION_SHAPE, "plain": None}


def test_a_receiver_call_reaches_a_unique_extension_and_guesses_among_several():
    files = {"src/p/Util.kt": UTIL, "src/p/Names.kt": NAMES, "src/p/Reflect.kt": REFLECT, "src/p/Spec.kt": USE}
    parsed = []
    for path, code in files.items():
        p = _parse(code)
        parsed.append({"path": path, "lang_id": "kotlin", "functions": p["functions"], "classes": p["classes"]})
    sites, _ = resolve_calls(parsed)
    got = {(s["callee"], s["step"], s["dst_path"]) for s in sites if s["src_name"].endswith("emit")}
    assert ("escapeIfKeyword", "file", "src/p/Util.kt") in got or ("escapeIfKeyword", "import", "src/p/Util.kt") in got
    assert any(c == "escapeIfNotJavaIdentifier" and step in ("file", "import") for c, step, _ in got)
    assert {step for c, step, _ in got if c == "asClassName"} == {"receiver"}  # KClass or Class: not typed here


def test_a_csharp_extension_method_is_marked_too():
    code = (
        "public static class E\n{\n"
        "    public static string FormatWith(this string f, int a)\n    {\n        return f;\n    }\n"
        "    public static string Plain(string thisx)\n    {\n        return thisx;\n    }\n}\n"
    )
    funcs = StructuralExtractor("csharp", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    assert {f["name"]: f.get("def_shape") for f in funcs} == {"FormatWith": EXTENSION_SHAPE, "Plain": None}


def test_a_library_typed_receiver_reaches_extensions_only():
    code = (
        "package p\n"
        "class Names {\n"
        '    fun trim(): String = ""\n'  # 3: a repo method named like String.trim
        "    fun use(s: String): String {\n"
        "        return s.trim().escapeIfKeyword()\n"
        "    }\n"
        "}\n"
        "internal fun String.escapeIfKeyword(): String = this\n"  # 8
    )
    p = _parse(code)
    sites, _ = resolve_calls(
        [{"path": "src/p/Names.kt", "lang_id": "kotlin", "functions": p["functions"], "classes": p["classes"]}]
    )
    got = {(s["callee"], s["dst_line"]) for s in sites if s["src_name"].endswith("use") and s["dst_line"]}
    assert ("trim", 3) not in got  # `s` is a String: its own trim, not Names.trim
    assert ("escapeIfKeyword", 8) in got
