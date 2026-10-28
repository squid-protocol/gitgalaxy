"""
#6266 (gzdoom): a computed-goto label macro is no function, and a constructor's initializer span ends at its body.

`OP(CLSS):\n{ .. }` in a VM exec loop read as a constructor with an initializer list (the colon, then the body's brace).
A constructor `Box(int n = {}) : a(n)\n{ Init(0); }` lost the call in its body: the span ran to the end of the unit, so
`Init(0)` was taken for an initializer entry. Driven through `StructuralExtractor.splice()`, the path a scan takes.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _units(code: str) -> dict:
    functions = StructuralExtractor("cpp", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f for f in functions}


def test_a_call_in_the_body_after_an_initializer_list_is_kept():
    code = "Rng::Rng(bool client)\n: crc(0), bClient(client)\n{\n\tif (bClient)\n\t{\n\t\tnext = list;\n\t}\n\tInit(0);\n}\n"
    assert "Init" in _units(code)["Rng::Rng"]["calls_out_to"]  # the resolver, not the detector, drops `crc`


def test_a_brace_default_argument_does_not_end_the_initializer_span():
    code = "Box::Box(Opts o = {}, int n = 1)\n: Base(n), m(o)\n{\n\tgo();\n}\n"
    calls = _units(code)["Box::Box"]["calls_out_to"]
    assert "go" in calls
    assert "Base" in calls


@pytest.mark.parametrize(
    "label_body", ["{\n\t\tdo_it();\n\t}", "\n\t\tif (x) { do_it(); }", "\n#if 0\n\t\tskip();\n#endif"]
)
def test_a_label_macro_before_a_body_is_not_a_function(label_body):
    code = "int Exec(int x)\n{\n\tswitch (x)\n\t{\n\tOP(CLSS):\n\t" + label_body + "\n\t}\n\treturn 0;\n}\n"
    assert "OP" not in _units(code)


def _init_edges(files: dict[str, tuple[list, list]], imports=()):
    from gitgalaxy.core.call_resolver import resolve_calls

    parsed = [
        {"path": p, "lang_id": "cpp", "functions": fns, "classes": classes} for p, (fns, classes) in files.items()
    ]
    edges = [{"src": s, "dst": d, "edge_kind": "import"} for s, d in imports]
    sites, _ = resolve_calls(parsed, edges)
    return {(s["src_name"], s["dst_name"]) for s in sites if s["dst_name"]}


def _ctor(name, line, calls=(), init=False):
    return {
        "name": name,
        "start_line": line,
        "calls_out_to": list(calls),
        "calls_out_qualifiers": {c: ["<init>" if init else ""] for c in calls},
    }


def test_an_init_entry_naming_a_class_and_its_constructor_pins_the_base_constructor():
    files = {
        "n/Base.h": ([], [{"name": "Base", "start_line": 1, "inheritance": []}]),
        "n/Base.cpp": ([_ctor("Base::Base", 1)], []),
        "n/D.cpp": ([_ctor("D::D", 1, ["Base"], init=True)], [{"name": "D", "start_line": 1, "inheritance": ["Base"]}]),
    }
    assert ("D::D", "Base::Base") in _init_edges(files, [("n/D.cpp", "n/D.h"), ("n/D.h", "n/Base.h")])


def test_an_init_entry_pins_the_one_visible_class_among_platform_copies():
    base = [{"name": "Fb", "start_line": 1, "inheritance": []}]
    files = {
        "win/base.h": ([], base),
        "win/base.cpp": ([_ctor("Fb::Fb", 1)], []),
        "sdl/base.h": ([], base),
        "win/gl.cpp": (
            [_ctor("Gl::Gl", 1, ["Fb"], init=True)],
            [{"name": "Gl", "start_line": 1, "inheritance": ["Fb"]}],
        ),
    }
    assert ("Gl::Gl", "Fb::Fb") in _init_edges(files, [("win/gl.cpp", "win/base.h")])


def test_an_init_entry_naming_a_class_no_included_file_declares_is_no_base():
    files = {
        "a/Node.h": ([], [{"name": "Node", "start_line": 1, "inheritance": []}]),
        "a/Node.cpp": ([_ctor("Node::Node", 1)], []),
        "b/user.cpp": ([_ctor("User::User", 1, ["Node"], init=True)], []),
    }
    assert ("User::User", "Node::Node") not in _init_edges(files)


def test_an_init_entry_matching_two_included_nested_classes_is_a_member_not_a_base():
    nested = [{"name": "Node", "start_line": 1, "inheritance": []}]
    files = {
        "u/arr.h": ([], nested),
        "u/arena.h": ([], nested),
        "u/arr.cpp": ([_ctor("Node::Node", 1)], []),
        "s/sym.cpp": ([_ctor("Sym::Sym", 1, ["Node"], init=True)], []),
    }
    assert ("Sym::Sym", "Node::Node") not in _init_edges(files, [("s/sym.cpp", "u/arr.h"), ("s/sym.cpp", "u/arena.h")])
