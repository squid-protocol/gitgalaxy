"""#5628 (part 3): the resolver's `class` rung found the unit itself for a bare `f(` inside
`Scope::f` and dropped the row as recursion, so the edge to the free `f` was missing even
though the detector kept the call (part 2). Detector output feeds the resolver end to end."""

import pytest

from gitgalaxy.core.call_resolver import resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _edges(lang: str, code: str, path: str) -> list[tuple[str, str, int | None]]:
    parsed = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")
    file = {"path": path, "lang_id": lang, "functions": parsed["functions"], "classes": parsed.get("classes", [])}
    sites, _ = resolve_calls([file])
    return [(s["src_name"], s["dst_name"], s["dst_line"]) for s in sites if s["dst_name"]]


def test_cpp_scoped_unit_resolves_bare_call_to_the_free_function():
    src = "void f(int a) {\n  g(a);\n}\nvoid Scope::f(int a) {\n  f(a);\n}\n"
    assert ("Scope::f", "f", 1) in _edges("cpp", src, "a.cpp")


def test_cpp_hand_built_rows_resolve_to_the_free_function():
    def fn(name, line, calls=()):
        return {
            "name": name,
            "start_line": line,
            "calls_out_to": list(calls),
            "calls_out_qualifiers": {c: [""] for c in calls},
        }

    files = [{"path": "a.cpp", "lang_id": "cpp", "functions": [fn("f", 1), fn("Scope::f", 4, ["f"])], "classes": []}]
    sites, _ = resolve_calls(files)
    (row,) = sites
    assert (row["src_name"], row["dst_name"], row["dst_line"]) == ("Scope::f", "f", 1)


def test_cpp_true_recursion_stays_dropped():
    assert _edges("cpp", "void Scope::f(int a) {\n  f(a);\n}\n", "a.cpp") == []
    assert _edges("cpp", "int r(int n) {\n  return r(n - 1);\n}\n", "a.cpp") == []


def test_cpp_explicit_self_references_stay_recursion():
    src = "void f() {}\nvoid Scope::f(int a) {\n  this->f(a);\n  Scope::f(a);\n}\n"
    assert _edges("cpp", src, "a.cpp") == []


def test_cpp_free_function_gains_no_edge_from_a_scoped_namesake():
    src = "void f(int a) {\n  f(a);\n}\nvoid Scope::f(int a) {\n  g(a);\n}\n"
    assert _edges("cpp", src, "a.cpp") == []


@pytest.mark.parametrize("lang,path", [("csharp", "a.cs")])
def test_csharp_explicit_interface_impl_reaches_the_class_method(lang, path):
    src = (
        "class A : IEnumerable {\n"
        "  public IEnumerator GetEnumerator() { return null; }\n"
        "  IEnumerator IEnumerable.GetEnumerator() => GetEnumerator();\n"
        "  int Rec(int n) { return Rec(n - 1); }\n"
        "}\n"
    )
    edges = _edges(lang, src, path)
    assert ("IEnumerable.GetEnumerator", "GetEnumerator", 2) in edges
    assert all(src_name != "Rec" for src_name, _, _ in edges)


def test_csharp_block_bodied_explicit_interface_impl_reaches_the_class_method():
    # the helion shapes (VertexAllocator, ArchiveMapiterator, ConsoleCommands): a block body, not `=>`
    src = (
        "class A : IEnumerable {\n"
        "  public IEnumerator<int> GetEnumerator() {\n"
        "    yield return 1;\n"
        "  }\n"
        "  IEnumerator IEnumerable.GetEnumerator() {\n"
        "    return GetEnumerator();\n"
        "  }\n"
        "}\n"
    )
    assert ("IEnumerable.GetEnumerator", "GetEnumerator", 2) in _edges("csharp", src, "a.cs")


def _scan(files: dict[str, str]) -> tuple[list[dict], list[dict]]:
    parsed_files = []
    for path, code in files.items():
        parsed = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS).splice(code, "")
        parsed_files.append(
            {"path": path, "lang_id": "cpp", "functions": parsed["functions"], "classes": parsed.get("classes", [])}
        )
    sites, _ = resolve_calls(parsed_files)
    return parsed_files, sites


def test_cpp_scoped_unit_reaches_a_free_function_in_another_file():
    files, sites = _scan(
        {"scope.cpp": "void Scope::f(int a) {\n  f(a);\n}\n", "free.cpp": "void f(int a) {\n  g(a);\n}\n"}
    )
    assert [(s["src_name"], s["dst_path"], s["dst_name"]) for s in sites if s["src_name"] == "Scope::f"] == [
        ("Scope::f", "free.cpp", "f")
    ]
    scoped = next(fn for fn in files[0]["functions"] if fn["name"] == "Scope::f")
    assert scoped["calls_out_to"] == ["f"]


def test_cpp_cross_file_recursion_with_no_free_function_anywhere_stays_dropped():
    files, sites = _scan({"scope.cpp": "void Scope::f(int a) {\n  f(a);\n}\n", "other.cpp": "void h() {\n}\n"})
    assert not [s for s in sites if s["src_name"] == "Scope::f"]
    assert next(fn for fn in files[0]["functions"] if fn["name"] == "Scope::f")["calls_out_to"] == []


def test_cpp_other_class_method_is_not_reachable_by_a_bare_name():
    files, sites = _scan({"a.cpp": "void Other::f() {\n}\nvoid Scope::f(int a) {\n  f(a);\n}\n"})
    assert not [s for s in sites if s["src_name"] == "Scope::f" and s["dst_name"] == "Other::f"]
    assert next(fn for fn in files[0]["functions"] if fn["name"] == "Scope::f")["calls_out_to"] == []


def test_cpp_receiver_call_to_the_same_name_is_not_pruned():
    files, _ = _scan({"a.cpp": "void Scope::f(int a) {\n  child->f(a);\n}\n"})
    assert next(fn for fn in files[0]["functions"] if fn["name"] == "Scope::f")["calls_out_to"] == ["f"]
