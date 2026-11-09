"""#8161 (J5): a class header's whole parent clause is recorded as one string (`Holder<String> implements
Scaled, Serializable`, Python's `Base, Mixin, metaclass=M`, C#'s `Base<int>, IFoo`), which as a single
lineage key matched no class, so an inherited method was unreachable. Each named parent is its own key."""

import pytest

from gitgalaxy.core.call_resolver import _parent_names, resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


@pytest.mark.parametrize(
    "raw,names",
    [
        ("Holder<String> implements Scaled, java.io.Serializable", ["Holder", "Scaled", "Serializable"]),
        ("Scaled, Comparable<Multi> ", ["Scaled", "Comparable"]),
        ("Map<String, List<Integer>>", ["Map"]),
        ("Base, Mixin, metaclass=M", ["Base", "Mixin"]),
        ("typing.Generic[T]", ["Generic"]),
        ("Base<int>, IFoo ", ["Base", "IFoo"]),
        ("public Base", ["Base"]),
        ("Base", ["Base"]),
    ],
)
def test_parent_names(raw, names):
    assert _parent_names(raw) == names


def _edges(lang: str, path: str, code: str):
    parsed = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")
    file = {"path": path, "lang_id": lang, "functions": parsed["functions"], "classes": parsed.get("classes", [])}
    sites, _ = resolve_calls([file])
    return {(s["src_name"], s["dst_name"], s["dst_line"], s["step"]) for s in sites if s["dst_name"]}


def test_java_generic_parent_with_implements_is_walked():
    code = (
        "package p;\n"
        "abstract class Holder<T> {\n    int hold() { return 1; }\n}\n"
        "interface Scaled { int scale(); }\n"
        "class Impl extends Holder<String> implements Scaled {\n"
        "    public int scale() { return 2; }\n"
        "    int run() { return hold(); }\n"
        "}\n"
    )
    assert ("run", "hold", 3, "class") in _edges("java", "A.java", code)


def test_python_multiple_bases_are_each_walked():
    code = (
        "class Base:\n    def ping(self):\n        return 1\n\n"
        "class Mixin:\n    def pong(self):\n        return 2\n\n"
        "class Meta(type):\n    pass\n\n"
        "class D(Base, Mixin, metaclass=Meta):\n"
        "    def run(self):\n        return self.ping() + self.pong()\n"
    )
    edges = _edges("python", "a.py", code)
    assert ("run", "ping", 2, "class") in edges
    assert ("run", "pong", 6, "class") in edges
