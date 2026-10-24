"""
#6432: a brace in a function signature is no body start.

zig `error{..}!T`, `struct{..}`, `union(enum){..}`, `enum(u8){..}`, `opaque{}` in the result type, and a swift
closure parameter default (`cb: () -> Void = {}`), used to end the unit at the signature line, so the body's
calls landed on the previous function. Driven through `StructuralExtractor.splice()`.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _functions(lang: str, code: str) -> dict[str, dict]:
    functions = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f for f in functions}


_ZIG_RETURN_TYPES = [
    "error{A, B}!u8",
    "error{A}!struct{ n: u8 }",
    "struct{ n: u8 }",
    "struct { a: struct { b: u8 }, c: u8 }",
    "packed struct{ n: u8 }",
    "union(enum){ a: u8, b: u16 }",
    "union(enum(u8)) { a: u8 }",
    "enum(u8){ a, b }",
    "opaque{}",
]


@pytest.mark.parametrize("ret", _ZIG_RETURN_TYPES)
def test_zig_type_brace_in_result_type_keeps_the_body(ret):
    code = f"fn first() void {{\n    one();\n}}\nfn typed(x: u8) {ret} {{\n    return helper(x);\n}}\nfn last() void {{\n    two();\n}}\n"
    fns = _functions("zig", code)
    assert (fns["typed"]["start_line"], fns["typed"]["end_line"]) == (4, 6)
    assert fns["typed"]["calls_out_to"] == ["helper"]
    assert fns["first"]["calls_out_to"] == ["one"]
    assert fns["last"]["calls_out_to"] == ["two"]


def test_zig_type_brace_spanning_lines():
    code = "fn typed() error{\n    A,\n    B,\n}!u8 {\n    return helper();\n}\n"
    fns = _functions("zig", code)
    assert (fns["typed"]["start_line"], fns["typed"]["end_line"]) == (1, 6)
    assert fns["typed"]["calls_out_to"] == ["helper"]


def test_zig_plain_functions_are_unchanged():
    code = "pub fn a() void {\n    x();\n}\nfn b(p: struct{ n: u8 }) !void {\n    y();\n}\nextern fn c() void;\nfn d() void {\n    z();\n}\n"
    fns = _functions("zig", code)
    assert (fns["a"]["start_line"], fns["a"]["end_line"]) == (1, 3)
    assert (fns["b"]["start_line"], fns["b"]["end_line"]) == (4, 6)
    assert fns["b"]["calls_out_to"] == ["y"]
    assert fns["d"]["calls_out_to"] == ["z"]


def test_zig_body_calls_land_on_the_right_function():
    code = "fn helper() u8 {\n    return 1;\n}\nfn typed() error{A}!u8 {\n    return helper();\n}\n"
    fns = _functions("zig", code)
    assert fns["typed"]["calls_out_to"] == ["helper"]
    assert fns["helper"]["calls_out_to"] == []


def test_zig_unbalanced_type_brace_is_bounded():
    code = "fn a() struct{ " * 3000 + "\nfn b() void {\n    x();\n}\n"
    fns = _functions("zig", code)
    assert fns["b"]["calls_out_to"] == ["x"]


@pytest.mark.parametrize(
    "default",
    ["{}", "{ print(1) }", "{ $0 }"],
)
def test_swift_closure_default_keeps_the_body(default):
    code = f"func f(cb: () -> Void = {default}) -> Int {{\n    return helper()\n}}\nfunc g() {{\n    other()\n}}\n"
    fns = _functions("swift", code)
    assert (fns["f"]["start_line"], fns["f"]["end_line"]) == (1, 3)
    assert "helper" in fns["f"]["calls_out_to"]
    assert fns["g"]["calls_out_to"] == ["other"]


def test_swift_plain_and_bodyless_functions_are_unchanged():
    code = "protocol P {\n    func req(a: Int)\n}\nfunc g(a: Int) -> Int {\n    return other(a)\n}\n"
    fns = _functions("swift", code)
    assert (fns["g"]["start_line"], fns["g"]["end_line"]) == (4, 6)
    assert fns["g"]["calls_out_to"] == ["other"]
