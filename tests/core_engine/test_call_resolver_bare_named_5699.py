"""#5699: a method and a free function both named `f`. In a language where a bare `f(` never
reaches a method (it needs `self.f` / `this.f`), the call inside the method reaches the free
`f`; recursion through the bare name stays dropped (#3327). Languages where a member shadows
the free function keep dropping it."""

import pytest

from gitgalaxy.core.call_resolver import resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

METHOD_CALLS_FREE = {
    "rust": (
        "a.rs",
        "fn f(a: i32) -> i32 {\n    a\n}\nstruct S;\nimpl S {\n    fn f(&self, a: i32) -> i32 {\n        f(a)\n    }\n}\n",
    ),
    "php": (
        "a.php",
        "<?php\nfunction f($a) {\n    return $a;\n}\nclass S {\n    public function f($a) {\n        return f($a);\n    }\n}\n",
    ),
    "typescript": (
        "a.ts",
        "function f(a: number): number {\n    return a\n}\nclass S {\n    f(a: number): number {\n        return f(a)\n    }\n}\n",
    ),
    "javascript": ("a.js", "function f(a) {\n    return a\n}\nclass S {\n    f(a) {\n        return f(a)\n    }\n}\n"),
    "python": ("a.py", "def f(a):\n    return a\n\nclass S:\n    def f(self, a):\n        return f(a)\n"),
}

RECURSION = {
    "rust": ("a.rs", "fn f(a: i32) -> i32 {\n    f(a - 1)\n}\n"),
    "php": ("a.php", "<?php\nfunction f($a) {\n    return f($a - 1);\n}\n"),
    "typescript": ("a.ts", "function f(a: number): number {\n    return f(a - 1)\n}\n"),
    "javascript": ("a.js", "function f(a) {\n    return f(a - 1)\n}\n"),
    "python": ("a.py", "def f(a):\n    return f(a - 1)\n"),
}

# a member shadows the free function: a bare `f(` in the member is the member
MEMBER_SHADOWS = {
    "kotlin": (
        "a.kt",
        "fun f(a: Int): Int {\n    return a\n}\nclass S {\n    fun f(a: Int): Int {\n        return f(a)\n    }\n}\n",
    ),
    "swift": (
        "a.swift",
        "func f(_ a: Int) -> Int {\n    return a\n}\nclass S {\n    func f(_ a: Int) -> Int {\n        return f(a)\n    }\n}\n",
    ),
    "ruby": ("a.rb", "def f(a)\n  a\nend\nclass S\n  def f(a)\n    f(a)\n  end\nend\n"),
}


def _scan(lang: str, path: str, code: str):
    parsed = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")
    file = {"path": path, "lang_id": lang, "functions": parsed["functions"], "classes": parsed.get("classes", [])}
    sites, _ = resolve_calls([file])
    return file, [(s["src_name"], s["dst_name"], s["src_line"], s["dst_line"]) for s in sites if s["dst_name"]]


@pytest.mark.parametrize("lang", sorted(METHOD_CALLS_FREE))
def test_method_bare_call_reaches_the_free_function(lang):
    _, edges = _scan(lang, *METHOD_CALLS_FREE[lang])
    assert len(edges) == 1
    src, dst, src_line, dst_line = edges[0]
    assert src == dst == "f"
    assert dst_line < src_line  # the free `f` is declared first


@pytest.mark.parametrize("lang", sorted(RECURSION))
def test_bare_recursion_stays_dropped_and_pruned(lang):
    file, edges = _scan(lang, *RECURSION[lang])
    assert edges == []
    assert all(not fn["calls_out_to"] for fn in file["functions"])


@pytest.mark.parametrize("lang", sorted(MEMBER_SHADOWS))
def test_member_shadowing_languages_keep_dropping_it(lang):
    _, edges = _scan(lang, *MEMBER_SHADOWS[lang])
    assert edges == []


@pytest.mark.parametrize(
    "lang,path,code",
    [
        ("python", "a.py", "def f(a):\n    return a\n\nclass S:\n    def f(self, a):\n        return self.f(a)\n"),
        ("typescript", "a.ts", "function f() {}\nclass S {\n    f() {\n        return this.f()\n    }\n}\n"),
        (
            "php",
            "a.php",
            "<?php\nfunction f() {}\nclass S {\n    function f() {\n        return $this->f();\n    }\n}\n",
        ),
    ],
)
def test_explicit_receiver_self_call_stays_recursion(lang, path, code):
    _, edges = _scan(lang, path, code)
    assert edges == []


@pytest.mark.parametrize(
    "lang,path,code",
    [
        (
            "php",
            "a.php",
            "<?php\nfunction f() {}\nclass S {\n    function f() {\n        return new class {\n            public function f() {}\n        };\n    }\n}\n",
        ),
        (
            "python",
            "a.py",
            "def f():\n    pass\n\nclass S:\n    def f(self):\n        def f():\n            pass\n        return 1\n",
        ),
    ],
)
def test_nested_declaration_of_the_same_name_is_not_a_call(lang, path, code):
    _, edges = _scan(lang, path, code)
    assert edges == []
