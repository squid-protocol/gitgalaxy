"""
Python extraction hardening (epic #813, issue #818). See
tests/extraction/how_to_harden_extraction.md for the methodology.

Covers all four extraction gauntlets for python in one file: func_start,
args, class_start, _dependency_capture. Migrated out of the four old
monolithic dict files (test_function_extraction_strict.py,
test_args_extraction_strict.py, test_class_extraction_strict.py,
test_dependency_extraction_strict.py) -- python's entries were removed
from those four when this file was added.
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

# tests/ has no __init__.py anywhere in this repo, so a dotted
# `tests.extraction._extraction_harness` import only works by accident
# locally (e.g. `python -m pytest` from the repo root happens to put the
# root on sys.path) and fails in CI, which invokes the `pytest` console
# script directly. Insert this file's parent (tests/extraction/) onto
# sys.path instead, so the harness imports as a plain top-level module.
_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from typing import Any

from _extraction_harness import (  # noqa: E402 # type: ignore
    assert_invalid_no_match,
    assert_pathological_dependency_match,
    assert_pathological_match,
    assert_redos_immune,
    assert_valid_dependency_match,
    assert_valid_match,
)

EMBEDDED_PYTHON_RULES = LANGUAGE_DEFINITIONS["embedded_python"]["rules"]

# ==============================================================================
# FUNC_START (func_start)
# ==============================================================================
FUNCTION_CASES: dict[str, Any] = {
    "valid": [
        # Modern idiom (carried forward)
        ("def TargetFunc():", "TargetFunc"),
        ("async def TargetFunc(a: int) -> str:", "TargetFunc"),
        ("    @decorator\n    def TargetFunc():", "TargetFunc"),
        # Syntax-era / feature coverage
        ("def TargetFunc[T](x: T) -> T:", "TargetFunc"),  # PEP 695 (3.12+) simple generic
        (
            "def TargetFunc[T: Sequence[int]](x: T) -> T:",
            "TargetFunc",
        ),  # PEP 695 generic with nested-bracket bound -- was a real bug, now fixed
        ("def __init__(self, x):", "__init__"),  # dunder method
        ("def TargetFunc(a, /, b, *, c):", "TargetFunc"),  # positional-only + keyword-only params
        ("def TargetFunc(*args, **kwargs):", "TargetFunc"),  # varargs + kwargs
        # Testing-framework-shaped functions that ARE real functions
        (
            "@pytest.mark.parametrize('x', [1, 2, 3])\ndef test_TargetFunc(x):",
            "test_TargetFunc",
        ),  # pytest parametrize decorator
        ("@micropython.viper\ndef TargetFunc():", "TargetFunc"),  # MicroPython viper decorator
        ("@micropython.native\ndef TargetFunc():", "TargetFunc"),  # MicroPython native decorator
    ],
    "invalid": [
        "class TargetFunc:",  # class decl lookalike
        "TargetFunc = 5",  # assignment lookalike
        "if TargetFunc():",  # call inside condition
    ],
    "pathological": [
        (
            "@route('/api')\n@auth(role='admin')\n    async   def \n TargetFunc \n (",
            "TargetFunc",
        ),  # carried-forward: stacked decorators w/ args, extreme spacing, vertical
        (
            "def TargetFunc[T: Sequence[int]] \n ( \n x: T \n ) \n -> \n T \n :",
            "TargetFunc",
        ),  # nested-bracket PEP 695 generic, rest of signature split vertically
        (
            "@app.route('/api/v1', methods=['GET', 'POST'])\n@login_required\n@cache.cached(timeout=60)\nasync def TargetFunc():",
            "TargetFunc",
        ),  # 3+ stacked decorators with nested-list arguments
        (
            "def TargetFunc[T: Comparable, U: Sequence[int]](x: T, y: U) -> T:",
            "TargetFunc",
        ),  # multiple PEP 695 type params, one with a nested-bracket bound
    ],
}


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["valid"])
def test_embedded_python_func_start_valid(payload, expected_name):
    assert_valid_match(EMBEDDED_PYTHON_RULES["func_start"], payload, expected_name, "embedded_python.func_start")


@pytest.mark.parametrize("payload", FUNCTION_CASES["invalid"])
def test_embedded_python_func_start_invalid(payload):
    assert_invalid_no_match(EMBEDDED_PYTHON_RULES["func_start"], payload, "embedded_python.func_start")


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["pathological"])
def test_embedded_python_func_start_pathological(payload, expected_name):
    assert_pathological_match(EMBEDDED_PYTHON_RULES["func_start"], payload, expected_name, "embedded_python.func_start")


def test_embedded_python_func_start_pep695_nested_bracket_regression():
    """
    Regression test for a real bug (epic #813/#818): the PEP 695 (3.12+)
    generic-parameter step-over was a flat `[^\\]]*`, truncating at the
    FIRST `]` -- a nested-bracket type-parameter bound
    (`def Foo[T: Sequence[int]](x: T) -> T:`, a realistic bounded generic,
    directly analogous to java's `<T, U extends Comparable<U>>` #816 bug and
    typescript's own Rule-11 findings) left a stray `]` unconsumed, breaking
    the match entirely. Widened to the one-level-nesting idiom (square-
    bracket variant): `\\[(?:[^\\[\\]]|\\[[^\\[\\]]*\\])*\\]`.
    """
    func_start = EMBEDDED_PYTHON_RULES["func_start"]
    m = func_start.search("def TargetFunc[T: Sequence[int]](x: T) -> T:")
    assert m and "TargetFunc" in m.group(0), "PEP 695 nested-bracket generic detection regressed"


def test_embedded_python_func_start_redos_immunity():
    """ReDoS sweep for the widened PEP 695 generic-parameter step-over."""
    func_start = EMBEDDED_PYTHON_RULES["func_start"]
    assert_redos_immune(func_start, "def Foo[" + "a" * 100000, timeout_sec=3.0)
    assert func_start.search("def Foo[T: Sequence[int]](x: T) -> T:")


def test_embedded_python_func_start_known_limitation_no_whitespace_tolerance_between_name_and_generic_bracket():
    """
    Documents a known, NOT-fixed, PRE-EXISTING gap (unrelated to the
    nested-bracket fix above, present before this pass touched the rule at
    all): there is no whitespace/newline tolerance between the function
    name and an opening PEP 695 generic bracket (`def Foo[T](...)` works,
    but `def Foo\\n[T](...)` does not). Judged not worth fixing: no
    formatter (black, ruff format) ever produces this exact seam --
    real-world vertical splitting happens between modifiers/parens/inside
    the bracket's own contents, never between an identifier and the
    generic-bracket that immediately follows it. Recorded here rather than
    silently working around it in every future pathological test case.
    """
    func_start = EMBEDDED_PYTHON_RULES["func_start"]
    assert not func_start.search("def TargetFunc \n [T](x: T) -> T:"), (
        "documents current (accepted) behavior: a vertical split between name and generic bracket doesn't match"
    )
    assert func_start.search("def TargetFunc[T](x: T) -> T:"), "sanity: the adjacent (realistic) form still matches"


def test_embedded_python_func_start_triple_quoted_string_lookalike_shielded_by_pipeline():
    """
    Documents a CONTRASTING finding to the analogous js/ts/java/go tests
    (recurring bug class 3 in how_to_harden_extraction.md): in isolation,
    func_start's own regex has no string awareness and DOES match
    function-shaped text inside a triple-quoted string at true line start
    -- same shape as the js/ts/java/go false positives. BUT unlike those
    languages (routed through Mode B's `_slice_by_braces`, gated to js/ts
    only), python is routed through Mode C's `_slice_by_indentation`
    (`detector.py`), which ALREADY shields triple-quoted strings, standard
    strings, and comments via an index-aligned shield BEFORE calling
    `func_start.finditer()`. So this is NOT a live pipeline-level bug for
    python, even though the isolated regex (as tested elsewhere in this
    file) still matches -- confirmed by replicating Mode C's own shielding
    step here. Worth keeping as a reference: this is what the future
    "broaden _slice_by_braces" follow-up (tracked in the epic) should end
    up looking like for the other Mode B languages.
    """
    import re

    func_start = EMBEDDED_PYTHON_RULES["func_start"]
    code = 'x = """\ndef TargetFunc():\n    pass\n"""\n'
    assert func_start.search(code), "the isolated regex still matches (expected, matches js/ts/java/go)"

    def index_aligned_shield(m):
        text = m.group(0)
        return "".join("\n" if c == "\n" else " " for c in text)

    safe_code = re.sub(r'"""(.*?)"""', index_aligned_shield, code, flags=re.DOTALL)
    assert not func_start.search(safe_code), (
        "python's real Mode C pipeline (_slice_by_indentation) already shields this -- no live bug"
    )


# ==============================================================================
# ARGS (args)
# ==============================================================================
ARGS_CASES: dict[str, Any] = {
    "valid": [
        ("def TargetFunc(a: int, b=5):", "TargetFunc"),
        ("async def TargetFunc(req: Request) -> Response:", "TargetFunc"),
        ("class TargetClass:\n    def __init__(self, x):", "__init__"),
        (
            "def TargetFunc[T: Sequence[int]](x: T) -> T:",
            "TargetFunc",
        ),  # PEP 695 generic with nested-bracket bound -- was a real bug, now fixed
        ("lambda x, y: x + y", None),  # lambda
    ],
    "invalid": [
        "target_func_call(a, b)",
        "if (a == b):",
    ],
    "pathological": [
        (
            "def \n TargetFunc \n (\n    a: Callable[[int, str], bool],\n    b = lambda x: x * 2\n):",
            "TargetFunc",
        ),  # carried-forward: vertical, nested-generic callable param, default lambda
        (
            "def TargetFunc[T: Comparable, U: Sequence[int]](x: T, y: U) -> T:",
            "TargetFunc",
        ),  # multiple PEP 695 type params, one with a nested-bracket bound
    ],
}


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["valid"])
def test_embedded_python_args_valid(payload, expected_name):
    assert_valid_match(EMBEDDED_PYTHON_RULES["args"], payload, expected_name, "embedded_python.args")


@pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
def test_embedded_python_args_invalid(payload):
    assert_invalid_no_match(EMBEDDED_PYTHON_RULES["args"], payload, "embedded_python.args")


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["pathological"])
def test_embedded_python_args_pathological(payload, expected_name):
    assert_pathological_match(EMBEDDED_PYTHON_RULES["args"], payload, expected_name, "embedded_python.args")


def test_embedded_python_args_pep695_nested_bracket_regression():
    """Regression test for the same root-cause bug as func_start's own regression test above."""
    args = EMBEDDED_PYTHON_RULES["args"]
    m = args.search("def TargetFunc[T: Sequence[int]](x: T) -> T:")
    assert m, "PEP 695 nested-bracket generic args detection regressed"


def test_embedded_python_args_redos_immunity():
    """ReDoS sweep for the widened PEP 695 generic-parameter step-over."""
    args = EMBEDDED_PYTHON_RULES["args"]
    assert_redos_immune(args, "def Foo[" + "a" * 100000, timeout_sec=3.0)
    assert args.search("def Foo[T: Sequence[int]](x: T) -> T:")


# ==============================================================================
# CLASS_START (class_start)
# ==============================================================================
CLASS_CASES: dict[str, Any] = {
    "valid": [
        ("class TargetEntity:", "TargetEntity"),
        ("class TargetEntity(BaseClass):", "TargetEntity"),
        ("class TargetEntity[T](Base):", "TargetEntity"),  # PEP 695 generic class
        ("class TargetEntity(Generic[T]):", "TargetEntity"),  # subscripted generic base
        ("class TargetEntity(list[int]):", "TargetEntity"),  # subscripted builtin generic base
        ("class TargetEntity(Base, metaclass=ABCMeta):", "TargetEntity"),  # metaclass kwarg
        (
            "class TargetEntity[T: Sequence[int]](Base):",
            "TargetEntity",
        ),  # PEP 695 generic class with nested-bracket bound -- was a real bug, now fixed
        ("class TargetEntity(Protocol):", "TargetEntity"),  # Protocol base
        ("class TargetEntity(NamedTuple):", "TargetEntity"),  # NamedTuple base
    ],
    "invalid": [
        "def class_start():",
        "TargetEntity = class()",
        "if isinstance(obj, TargetEntity):",
    ],
    "pathological": [
        (
            "@dataclass\n@decorated(args)\nclass \n TargetEntity \n ( \n Base \n ) \n :",
            "TargetEntity",
        ),  # carried-forward: stacked decorators, extreme vertical spacing
        (
            "class TargetEntity[T: Sequence[int]] \n ( \n Base \n ) \n :",
            "TargetEntity",
        ),  # nested-bracket PEP 695 generic class, rest of signature split vertically
        (
            "@final\n@dataclass(frozen=True)\nclass TargetEntity[T: Comparable](Base, Protocol, metaclass=ABCMeta):",
            "TargetEntity",
        ),  # stacked decorators + nested-bracket generic + multi-base + metaclass, single line
    ],
}


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["valid"])
def test_embedded_python_class_start_valid(payload, expected_name):
    assert_valid_match(EMBEDDED_PYTHON_RULES["class_start"], payload, expected_name, "embedded_python.class_start")


@pytest.mark.parametrize("payload", CLASS_CASES["invalid"])
def test_embedded_python_class_start_invalid(payload):
    assert_invalid_no_match(EMBEDDED_PYTHON_RULES["class_start"], payload, "embedded_python.class_start")


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["pathological"])
def test_embedded_python_class_start_pathological(payload, expected_name):
    assert_pathological_match(EMBEDDED_PYTHON_RULES["class_start"], payload, expected_name, "embedded_python.class_start")


def test_embedded_python_class_start_pep695_nested_bracket_base_capture_regression():
    """
    Regression test for a real bug (epic #813/#818), distinct in effect
    from func_start's own regression test above: class_start's PEP 695
    generic-parameter step-over had the identical flat-`[^\\]]*` bug, but
    since the class NAME (group 1) is captured BEFORE the generic
    step-over, the bug didn't fail the whole match -- it silently dropped
    the base-class capture (group 2) instead, even though the class name
    itself matched fine. Same failure SHAPE as java's #816 class_start bug
    (name looks correct, inheritance info silently vanishes), different
    root cause (missing nesting support here, vs. missing step-over
    entirely there).
    """
    class_start = EMBEDDED_PYTHON_RULES["class_start"]
    assert class_start.groups == 2, "sanity: the rule still has both capture groups"

    m = class_start.search("class Foo[T: Sequence[int]](Base):")
    assert m and m.group(1) == "Foo", "class name capture regressed"
    assert m.group(2) and "Base" in m.group(2), "base-class capture still lost behind a nested-bracket generic bound"


def test_embedded_python_class_start_redos_immunity():
    """ReDoS sweep for the widened PEP 695 generic-parameter step-over."""
    class_start = EMBEDDED_PYTHON_RULES["class_start"]
    assert_redos_immune(class_start, "class Foo[" + "a" * 100000, timeout_sec=3.0)
    assert class_start.search("class Foo[T: Sequence[int]](Base):")


# ==============================================================================
# DEPENDENCY (_dependency_capture)
# ==============================================================================
DEPENDENCY_CASES: dict[str, Any] = {
    "valid": [
        ("import os", "os"),
        ("from gitgalaxy.engine import Parser", "gitgalaxy.engine"),
        ("import numpy as np", "numpy"),
        ("from . import foo", "."),  # relative import, dot-only module
        ("from ..pkg import foo", "..pkg"),  # relative import, up-level
        ("from __future__ import annotations", "__future__"),  # future import
        ("from os import *", "os"),  # star import
        ("import machine", "machine"), # MicroPython hardware import
        ("from network import WLAN", "network"), # MicroPython network import
    ],
    "invalid": [
        "import_path = 'foo'",
        "def import_data():",
    ],
    "pathological": [
        (
            "from \n core.networking.sockets \n import ( \n    TCPSocket \n )",
            "core.networking.sockets",
        ),  # carried-forward: vertical from-import with parenthesized names
        (
            "from \n ..deeply.nested.relative.pkg \n import \n Foo",
            "..deeply.nested.relative.pkg",
        ),  # deeply nested relative import, vertical
    ],
}


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["valid"])
def test_embedded_python_dependency_capture_valid(payload, expected_path):
    assert_valid_dependency_match(
        EMBEDDED_PYTHON_RULES["_dependency_capture"], payload, expected_path, "embedded_python._dependency_capture"
    )


@pytest.mark.parametrize("payload", DEPENDENCY_CASES["invalid"])
def test_embedded_python_dependency_capture_invalid(payload):
    assert_invalid_no_match(EMBEDDED_PYTHON_RULES["_dependency_capture"], payload, "embedded_python._dependency_capture")


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["pathological"])
def test_embedded_python_dependency_capture_pathological(payload, expected_path):
    assert_pathological_dependency_match(
        EMBEDDED_PYTHON_RULES["_dependency_capture"], payload, expected_path, "embedded_python._dependency_capture"
    )


def test_embedded_python_dependency_capture_known_limitation_triple_quoted_string_lookalike_still_matches_at_regex_level():
    """
    Unlike func_start (shielded by Mode C's _slice_by_indentation before
    matching, see the contrasting test above), _dependency_capture is
    matched against fully unshielded raw file content for EVERY language
    unconditionally (galaxyscope.py's `content_buffer`, see the java pass's
    #816 finding) -- there is no per-mode shielding for this rule at all.
    An `import ...`-shaped line inside a python triple-quoted string at
    true line start still produces a phantom dependency-graph edge.
    Documented, not fixed here -- see how_to_harden_extraction.md's
    recurring bug class 10.
    """
    dependency_capture = EMBEDDED_PYTHON_RULES["_dependency_capture"]
    triple_quoted = 'x = """\nimport os\n"""'
    assert dependency_capture.search(triple_quoted), "documents current (accepted, unfixed) regex behavior"
