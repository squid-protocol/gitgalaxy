"""
#6266: a C++ constructor's initializer list names a base class (`: Base(a)`) or a data member (`: type(t)`).

The detector marks each bare top-level entry with the `<init>` qualifier and the resolver keeps the edge only
when the name resolves to a class: a member is no call, even when a free function of the same name exists
(doomsday / odamex `event_t -> type`).
"""

import pytest

from gitgalaxy.core.call_resolver import INIT_LIST_QUALIFIER, resolve_calls
from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _functions(code: str) -> dict[str, dict]:
    functions = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f for f in functions}


@pytest.mark.parametrize(
    "code, unit, marked, unmarked",
    [
        ("struct E {\n  E(int t, int f) : type(t), flags(f) {}\n};\n", "E", ["type", "flags"], []),
        ("D::D(int a) : Base(a), v(type(a))\n{\n  setup(v);\n}\n", "D::D", ["Base", "v"], ["type", "setup"]),
        ("D::D(int a)\n    : Base(a)\n    , v(a)\n{\n  v2 = b ? g(1) : f(2);\n}\n", "D::D", ["Base", "v"], ["g", "f"]),
        ("void run(int a) {\n  x = c ? one(a) : two(a);\n}\n", "run", [], ["one", "two"]),
        ("void ns::f(int a)\n{\n  std::string s = ns::g(a);\n}\n", "ns::f", [], ["g"]),
    ],
)
def test_initializer_list_entries_are_marked_and_body_calls_are_not(code, unit, marked, unmarked):
    quals = _functions(code)[unit]["calls_out_qualifiers"]
    assert [c for c, q in quals.items() if q == [INIT_LIST_QUALIFIER]] == marked
    assert all(INIT_LIST_QUALIFIER not in quals.get(c, []) for c in unmarked)


def _edges(functions, classes=()):
    parsed = [{"path": "a.cc", "lang_id": "cpp", "functions": functions, "classes": list(classes)}]
    sites, _ = resolve_calls(parsed, [])
    return {(s["src_name"], s["dst_name"]) for s in sites if s["dst_name"]}


def _fn(name, line, calls=(), qualifier=""):
    return {
        "name": name,
        "start_line": line,
        "calls_out_to": list(calls),
        "calls_out_qualifiers": {c: [qualifier] for c in calls},
    }


def test_member_initializer_does_not_reach_a_same_named_free_function():
    functions = [_fn("type", 1), _fn("E", 5, ["type"], INIT_LIST_QUALIFIER)]
    assert _edges(functions) == set()


def test_unmarked_call_to_the_same_name_still_resolves():
    functions = [_fn("type", 1), _fn("E", 5, ["type"])]
    assert _edges(functions) == {("E", "type")}


def test_entry_that_is_also_called_in_the_body_keeps_the_body_edge():
    functions = [_fn("type", 1), {**_fn("E", 5, ["type"]), "calls_out_qualifiers": {"type": [INIT_LIST_QUALIFIER, ""]}}]
    assert _edges(functions) == {("E", "type")}


def test_base_class_initializer_still_reaches_the_base_constructor():
    functions = [_fn("Base::Base", 1), _fn("D::D", 5, ["Base"], INIT_LIST_QUALIFIER)]
    classes = [
        {"name": "Base", "start_line": 1, "inheritance": []},
        {"name": "D", "start_line": 4, "inheritance": ["Base"]},
    ]
    assert _edges(functions, classes) == {("D::D", "Base::Base")}


def test_resolver_prunes_a_member_from_calls_out_to_and_clears_the_marker_on_a_base():
    member = _fn("E", 5, ["type"], INIT_LIST_QUALIFIER)
    derived = {
        **_fn("D::D", 9, ["Base", "type"]),
        "calls_out_qualifiers": {"Base": [INIT_LIST_QUALIFIER], "type": [INIT_LIST_QUALIFIER, ""]},
    }
    functions = [_fn("type", 1), _fn("Base::Base", 3), member, derived]
    _edges(functions)
    assert member["calls_out_to"] == []
    assert derived["calls_out_to"] == ["Base", "type"]
    assert derived["calls_out_qualifiers"] == {"Base": [""], "type": [""]}
