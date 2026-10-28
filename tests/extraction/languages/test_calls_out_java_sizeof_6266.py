"""
#6266: Java has no `sizeof` keyword. `filelump_t.sizeof()` is a static method call (mochadoom), so the callee is kept.

The global calls-out ignore set drops `sizeof` (a C/C++ operator); Java joins the languages that exempt the words
that are ordinary names for them (#5634). C keeps dropping it.
"""

from gitgalaxy.core.call_resolver import resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_JAVA = "class A {\n  int f() {\n    return (int) (n * Filelump.sizeof());\n  }\n}\n"
_C = "int f(void) {\n  return n * sizeof(int);\n}\n"


def _calls(lang: str, code: str) -> list[str]:
    functions = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return next(f["calls_out_to"] for f in functions if f["name"] == "f")


def test_java_static_sizeof_method_is_a_callee_and_c_sizeof_is_not():
    assert _calls("java", _JAVA) == ["sizeof"]
    assert "sizeof" not in _calls("c", _C)


def test_java_sizeof_call_resolves_to_the_qualifying_class():
    files = {
        "a/Filelump.java": "public class Filelump {\n  public static int sizeof() { return 1; }\n}\n",
        "a/Other.java": "public class Other {\n  public static int sizeof() { return 2; }\n}\n",
        "a/A.java": _JAVA,
    }
    parsed = []
    for path, code in files.items():
        spliced = StructuralExtractor("java", LANGUAGE_DEFINITIONS).splice(code, "")
        parsed.append({"path": path, "lang_id": "java", "raw_imports": [], "functions": spliced["functions"],
                       "classes": spliced.get("classes", [])})  # fmt: skip
    sites = [s for s in resolve_calls(parsed, [])[0] if s["src_name"] == "f"]
    assert [(s["callee"], s["dst_path"]) for s in sites] == [("sizeof", "a/Filelump.java")]


def test_kotlin_companion_sizeof_is_a_callee():
    """Kotlin has no `sizeof` either (kocoa: `ByteArray((length * filelump_t.sizeof()).toInt())`)."""
    code = "class A {\n    fun f(): Int {\n        val toc = ByteArray((n * Filelump.sizeof()).toInt())\n        return 1\n    }\n}\n"
    assert "sizeof" in _calls("kotlin", code)


def test_kotlin_require_stays_dropped():
    """Only `sizeof` is exempt for kotlin: keyword-rosetta's kotlin a.kt is locked with `require(..)` dropped."""
    code = "class A {\n    fun f(v: Int): Int {\n        require(v > 0)\n        return 1\n    }\n}\n"
    assert "require" not in _calls("kotlin", code)
