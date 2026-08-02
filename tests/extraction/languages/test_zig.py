"""
Zig extraction hardening. See
tests/extraction/how_to_harden_extraction.md for the methodology.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from _extraction_harness import (  # noqa: E402 # type: ignore
    assert_invalid_no_match,
    assert_redos_immune,
    assert_valid_dependency_match,
    assert_valid_match,
)

ZIG_RULES = LANGUAGE_DEFINITIONS["zig"]["rules"]

# ==============================================================================
# FUNC_START (func_start)
# ==============================================================================
FUNC_START_VALID = [
    ("fn foo() void {}", "foo"),
    ("pub fn foo() void {}", "foo"),
    ("pub inline fn bar(a: i32) !u8 {}", "bar"),
    ('extern "c" fn foo() void', "foo"),
    ('export fn process(data: [*c]u8) callconv(.C) linksection(".text") align(8) void {}', "process"),
    ("fn generic(comptime T: type, alloc: std.mem.Allocator) ?*T {}", "generic"),
    ("pub fn\nmultiline\n(\n    a: i32,\n)\nvoid\n{", "multiline"),
    ('pub fn @"weird function name"() void {}', '@"weird function name"'),
    ("fn\t\t \nweird_whitespace()\n\t!void {", "weird_whitespace"),
    ("fn return_type_func() fn(i32) void {", "return_type_func"),
]

FUNC_START_INVALID = [
    "// fn commentedOut() void {}",
    "/// fn docCommentedOut() void {}",
    'const s = "fn stringFunc() void {}";',
    "\\\\ fn multilineStringFunc() void {}",
    "const callback: fn (u32) void = undefined;",
    "const FuncType = fn (a: i32) bool;",
]


@pytest.mark.parametrize("payload,expected_name", FUNC_START_VALID)
def test_zig_func_start_valid(payload, expected_name):
    assert_valid_match(ZIG_RULES["func_start"], payload, expected_name, "zig.func_start")


@pytest.mark.parametrize("payload", FUNC_START_INVALID)
def test_zig_func_start_invalid(payload):
    assert_invalid_no_match(ZIG_RULES["func_start"], payload, "zig.func_start")


def test_zig_func_start_redos_immunity():
    assert_redos_immune(ZIG_RULES["func_start"], "pub " * 100 + "fn " + "A" * 1000 + "()", timeout_sec=1.0)


# ==============================================================================
# CLASS_START (class_start)
# ==============================================================================
CLASS_START_VALID = [
    ("const Point = struct { x: f32, y: f32 };", "Point"),
    ("pub const PackedUnion = packed union { a: u8, b: u16 };", "PackedUnion"),
    ("const State = enum(u8) { on, off };", "State"),
    ("pub const Handle = opaque {};", "Handle"),
    ("const ErrorSet = error{ OutOfMemory, InvalidFormat };", "ErrorSet"),
    ("const   \nMyStruct\n  =\nextern\nstruct\n{", "MyStruct"),
    ('const @"Class Name" = struct { };', '@"Class Name"'),
    ("const A = struct { const B = struct { }; };", "A"),
]

CLASS_START_INVALID = [
    'const s = "struct { }";',
    "// const Foo = struct {};",
    "fn foo(struct_param: i32) void {}",
    "const instance = .{ .x = 1 };",
]


@pytest.mark.parametrize("payload,expected_name", CLASS_START_VALID)
def test_zig_class_start_valid(payload, expected_name):
    assert_valid_match(ZIG_RULES["class_start"], payload, expected_name, "zig.class_start")


@pytest.mark.parametrize("payload", CLASS_START_INVALID)
def test_zig_class_start_invalid(payload):
    assert_invalid_no_match(ZIG_RULES["class_start"], payload, "zig.class_start")


# ==============================================================================
# ARGS (args)
# ==============================================================================
ARGS_VALID = [
    ("fn foo(a: i32, b: f32) void", "a: i32, b: f32"),
    (
        "fn generic(comptime T: type, allocator: std.mem.Allocator, args: anytype) void",
        "comptime T: type, allocator: std.mem.Allocator, args: anytype",
    ),
    (
        "fn process(data: [*c]const u8, optional_ptr: ?*align(4) u32) void",
        "data: [*c]const u8, optional_ptr: ?*align(4) u32",
    ),
    ("fn varargs(fmt: [*c]const u8, ...) void", "fmt: [*c]const u8, ..."),
    ("fn multiline(\na: i32,\n    b: f32,) void", "\na: i32,\n    b: f32,"),
    ("fn error_union(err: std.mem.Allocator.Error!u8) void", "err: std.mem.Allocator.Error!u8"),
    ("fn whitespace ( comptime \n T \n : \ntype \n, )", " comptime \n T \n : \ntype \n, "),
    ("fn func_ptr(arg: fn(fn(i32) void) bool) void", "arg: fn(fn(i32) void) bool"),
    ('fn custom_id(@"my weird arg": u8) void', '@"my weird arg": u8'),
]

ARGS_INVALID = [
    pytest.param('"fn (a: i32, b: i32)"', marks=pytest.mark.xfail(reason="Known limitation: No block shielding for args inside strings")),
    pytest.param("// fn (a: i32, b: i32)", marks=pytest.mark.xfail(reason="Known limitation: No block shielding for args inside comments")),
]


@pytest.mark.parametrize("payload,expected_args", ARGS_VALID)
def test_zig_args_valid(payload, expected_args):
    assert_valid_match(ZIG_RULES["args"], payload, expected_args, "zig.args")


@pytest.mark.parametrize("payload", ARGS_INVALID)
def test_zig_args_invalid(payload):
    assert_invalid_no_match(ZIG_RULES["args"], payload, "zig.args")


# ==============================================================================
# DEPENDENCY CAPTURE (_dependency_capture)
# ==============================================================================
DEPENDENCY_VALID = [
    ('const std = @import("std");', "std"),
    ('const net = @import("std").net;', "std"),
    ('const parser = @import("parser.zig");', "parser.zig"),
    ('const c = @cImport({ @cInclude("stdio.h"); });', "stdio.h"),
    ('_ = @import("std");', "std"),
    ('const \nstd\n=\n@import\n(\n"std"\n)\n;', "std"),
    ('pub const @"weird import" = @import("weird-name.zig");', "weird-name.zig"),
]

DEPENDENCY_INVALID = [
    '"@import(\\"std\\")"',
    '// const std = @import("std");',
]


@pytest.mark.parametrize("payload,expected_name", DEPENDENCY_VALID)
def test_zig_dependency_valid(payload, expected_name):
    assert_valid_dependency_match(ZIG_RULES["_dependency_capture"], payload, expected_name, "zig.dependency")


@pytest.mark.parametrize("payload", DEPENDENCY_INVALID)
def test_zig_dependency_invalid(payload):
    assert_invalid_no_match(ZIG_RULES["_dependency_capture"], payload, "zig.dependency")
