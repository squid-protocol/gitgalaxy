"""
Lua extraction hardening (epic #813, issue #832). See
tests/extraction/how_to_harden_extraction.md for the methodology.

Covers all four extraction gauntlets for lua in one file: func_start,
args, class_start, _dependency_capture. Migrated out of the old
monolithic dict files.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from typing import Any  # noqa: E402

from _extraction_harness import (  # noqa: E402 # type: ignore
    assert_invalid_no_match,
    assert_pathological_dependency_match,
    assert_pathological_match,
    assert_redos_immune,
    assert_valid_dependency_match,
    assert_valid_match,
)

LUA_RULES = LANGUAGE_DEFINITIONS["lua"]["rules"]

# ==============================================================================
# FUNC_START (func_start)
# ==============================================================================
FUNCTION_CASES: dict[str, Any] = {
    "valid": [
        ("function TargetFunc()", "TargetFunc"),
        ("local function TargetFunc(", "TargetFunc"),
        ("export function TargetFunc()", "TargetFunc"),
        ("local export function TargetFunc()", "TargetFunc"),
        ("function math.abs()", "math.abs"),
        ("function my_table:my_method()", "my_table:my_method"),
    ],
    "invalid": [
        "TargetFunc = function()",
        "if TargetFunc() then",
        "local f = function()",
    ],
    "pathological": [
        ("local \n function \n TargetFunc \n (", "TargetFunc"),
        ("local \t \n export \n \t function \n TargetFunc \n\n (", "TargetFunc"),
    ],
}

@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["valid"])
def test_lua_func_start_valid(payload, expected_name):
    assert_valid_match(LUA_RULES["func_start"], payload, expected_name, "func_start")

@pytest.mark.parametrize("payload", FUNCTION_CASES["invalid"])
def test_lua_func_start_invalid(payload):
    assert_invalid_no_match(LUA_RULES["func_start"], payload, "func_start")

@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["pathological"])
def test_lua_func_start_pathological(payload, expected_name):
    assert_pathological_match(LUA_RULES["func_start"], payload, expected_name, "func_start")

def test_lua_func_start_redos():
    assert_redos_immune(LUA_RULES["func_start"], "local export function " + " \n " * 50 + "TargetFunc")

# ==============================================================================
# CLASS_START (class_start)
# ==============================================================================
CLASS_CASES: dict[str, Any] = {
    "valid": [
        ("---@class MyClass", "MyClass"),
        ("MyClass = {", "MyClass"),
        ("local MyClass = {", "MyClass"),
        ("export MyClass = {", "MyClass"),
        ("local export MyClass = {", "MyClass"),
    ],
    "invalid": [
        "local my_var = {",  # Lowercase starting var
        "---@type MyClass",
    ],
    "pathological": [
        ("local \n export \n MyClass \n = \n {", "MyClass"),
        ("---@class \n MyClass", "MyClass"),
    ],
}

@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["valid"])
def test_lua_class_start_valid(payload, expected_name):
    assert_valid_match(LUA_RULES["class_start"], payload, expected_name, "class_start")

@pytest.mark.parametrize("payload", CLASS_CASES["invalid"])
def test_lua_class_start_invalid(payload):
    assert_invalid_no_match(LUA_RULES["class_start"], payload, "class_start")

@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["pathological"])
def test_lua_class_start_pathological(payload, expected_name):
    assert_pathological_match(LUA_RULES["class_start"], payload, expected_name, "class_start")

# ==============================================================================
# ARGS (args)
# ==============================================================================
ARGS_CASES: dict[str, Any] = {
    "valid": [
        ("function foo(a, b, c)", "function foo(a, b, c)"),
        ("local function bar(x)", "function bar(x)"),
        ("function my_table:method()", "function my_table:method()"),
        ("local f = function(a, b)", "function(a, b)"),
        ("function(a, b)", "function(a, b)"),
        ("function foo(a: string, b: (number, string) -> boolean)", "function foo(a: string, b: (number, string) -> boolean)"),
    ],
    "invalid": [
        "function foo",
        "local function bar",
    ],
    "pathological": [
        ("function \n foo \n ( \n a, \n b \n )", "function \n foo \n ( \n a, \n b \n )"),
    ],
}

@pytest.mark.parametrize("payload,expected_match", ARGS_CASES["valid"])
def test_lua_args_valid(payload, expected_match):
    match = LUA_RULES["args"].search(payload)
    assert match is not None  # noqa: S101
    assert match.group(0) == expected_match  # noqa: S101

@pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
def test_lua_args_invalid(payload):
    match = LUA_RULES["args"].search(payload)
    assert match is None  # noqa: S101

@pytest.mark.parametrize("payload,expected_match", ARGS_CASES["pathological"])
def test_lua_args_pathological(payload, expected_match):
    match = LUA_RULES["args"].search(payload)
    assert match is not None  # noqa: S101
    assert match.group(0) == expected_match  # noqa: S101

def test_lua_args_redos():
    assert_redos_immune(LUA_RULES["args"], "function foo" + "(((" * 50)

# ==============================================================================
# DEPENDENCY CAPTURE (_dependency_capture)
# ==============================================================================
DEPENDENCY_CASES: dict[str, Any] = {
    "valid": [
        ("require 'math'", "math"),
        ("require(\"ffi\")", "ffi"),
        ("local ffi = require('ffi')", "ffi"),
        ("dofile 'main.lua'", "main.lua"),
        ("dofile(\"utils.lua\")", "utils.lua"),
    ],
    "invalid": [
        "local require_path = ''",
        "require = nil",
        "dofile = nil",
    ],
    "pathological": [
        ("require \n ( \n 'bit32' \n )", "bit32"),
        ("dofile \t \n ( \t \n \"complex/path.lua\" \t \n )", "complex/path.lua"),
    ],
}

@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["valid"])
def test_lua_dependency_capture_valid(payload, expected_path):
    assert_valid_dependency_match(LUA_RULES["_dependency_capture"], payload, expected_path, "_dependency_capture")

@pytest.mark.parametrize("payload", DEPENDENCY_CASES["invalid"])
def test_lua_dependency_capture_invalid(payload):
    assert_invalid_no_match(LUA_RULES["_dependency_capture"], payload, "_dependency_capture")

@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["pathological"])
def test_lua_dependency_capture_pathological(payload, expected_path):
    assert_pathological_dependency_match(LUA_RULES["_dependency_capture"], payload, expected_path, "_dependency_capture")
