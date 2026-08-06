"""python strict structural-signature coverage.

Migrated out of tests/core_engine/test_language_standards_strict.py, then
colocated here in tests/extraction/languages/ alongside the extraction
gauntlets' own test_<lang>.py files (the `_strict` suffix on this filename
avoids a basename collision between the two under pytest's default import
mode). See tests/core_engine/test_language_standards_strict.py's git history
for the original single-file layout and section banners (Issue references, etc).
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune  # noqa: E402 # type: ignore


# ==============================================================================
# PYTHON: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #606)
# ==============================================================================
PY_RULES = LANGUAGE_DEFINITIONS["python"]["rules"]

_PY_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if x:\n    pass", "raise ValueError('x')"),
    ("safety", "try:\n    f()\nexcept ValueError:\n    g()", "f()"),
    ("safety_bypasses", "except Exception:\n    log(e)", "except ValueError:\n    log(e)"),
    ("high_risk_execution", "eval(user_input)", "print('safe')"),
    ("io", "with open('f.txt') as f:\n    pass", "opened = True"),
    ("state_mutation", "self.value = 1", "print(self.value)"),
    ("dead_code", "# def old_unused_function():", "# just a note"),
    ("doc", '"""A module docstring."""', '"a regular string"'),
    ("concurrency", "async def f():\n    await g()", "def f(): g()"),
    ("ui_framework", "import streamlit as st", "import string"),
    ("globals", "sys.argv[0]", "system = argv[0]"),
    ("decorators", "@staticmethod", "staticmethods = 1"),
    ("generics", "def f(x: List[int]) -> None: ...", "def f(x): pass"),
    ("scientific", "import numpy as np", "import numbers"),
    ("reflection_metaprogramming", "getattr(obj, 'attr')", "obj.attr"),
    ("ownership", "__author__ = 'Jane Doe'", "author = 'Jane Doe'"),
    ("planned_debt", "# TODO: refactor this", "# TODONE"),
    ("fragile_debt", "# HACK: temporary workaround", "# HACKATHON"),
    ("spec_exposure", "# [SPEC-123] implements the contract", "# spec sheet"),
    ("ssr_boundaries", "return HttpResponse('ok')", "return response"),
    ("events", "post_save.connect(handler)", "connected = True"),
    ("dependency_injection", "db: Session = Depends(get_db)", "db = get_db()"),
    ("pointers", "ptr = ctypes.POINTER(ctypes.c_int)", "ptr = c_int"),
    ("telemetry", "logger.info('started')", "logger = info"),
    ("debug_prints", "print('debug value:', x)", "printer = print"),
    ("explicit_casts", "int('42')", "int_var = 42"),
    ("panics_and_aborts", "raise ValueError('bad state')", "ValueError('bad state')"),
    ("thread_sleeps", "time.sleep(1)", "time = sleep"),
    ("sync_locks", "lock = threading.Lock()", "locked = True"),
    ("immutability_locks", "x: Final[int] = 1", "finally: pass"),
    ("cleanup", "conn.close()", "closed = True"),
    ("listeners", "signal.connect(receiver=on_event)", "connected = True"),
    ("test_skip", "@pytest.mark.skip", "pytest_skipped = True"),
    ("serialization_parsing", "data = pickle.loads(raw)", "loaded = True"),
    ("regex_execution", "re.compile(r'foo')", "compiled = True"),
    ("time_date_logic", "datetime.datetime.now()", "datetime_now = True"),
    ("ipc_rpc_bridges", "import multiprocessing", "import multiple"),
    ("api", "@app.get('/users')\ndef list_users():\n    pass", "def _internal_helper():\n    pass"),
    ("bitwise_ops", "x = a << 2", "result = base ** exponent"),
    ("closures", "f = lambda x: x + 1", "def f(x):\n    return x + 1"),
    ("comprehensions", "[x**2 for x in range(10)]", "for x in range(10):\n    print(x)"),
    ("cryptography", "import bcrypt", "import hashlib"),
    ("dl_frameworks", "import torch", "import sklearn"),
    ("encapsulation", "self._private_value = 1", "self.public_value = 1"),
    (
        "exfiltration_camouflage",
        "requests.post('https://telemetry.example.com/collect', json=payload)",
        "requests.post('https://api.example.com/users', json=payload)",
    ),
    ("hardware_bridge", "import usb.core", "import socket"),
    ("import", "import os", "importance = 1"),
    ("lazy_evaluation", "yield x", "return x"),
    ("llm_api", "import openai", "import requests"),
    ("llm_orchestrator", "from langchain.chains import LLMChain", "from flask import Flask"),
    ("llm_vector_store", "import chromadb", "import sqlite3"),
    ("memory_scraping", "path = '/proc/' + str(pid) + '/mem'", "path = '/proc/self/status'"),
    ("ml_traditional", "from sklearn.linear_model import LogisticRegression", "from scipy import stats"),
    ("structural_boundaries", "return x", "yield x"),
    ("test", "def test_addition():\n    assert 1 + 1 == 2", "def calculate_addition(a, b):\n    return a + b"),
    ("vectorized_math", "result = A @ B", "result = a * b"),

    # === DEEP/ADVERSARIAL CASES FOR HIGH-AMBIGUITY SIGNATURES ===
    # branch (match/case, walrus, strings/suffixes)
    ("branch", "if (x := 1):", "iffy = True"),
    ("branch", "match x:\n    case 1:", "def case_func():"),
    ("branch", "while True:", "while_loop = False"),
    ("branch", "with open('f.txt') as f:", "without = True"),
    ("branch", "for i in range(10):", "format_string"),
    
    # args (generics, newlines, edge-case lambdas)
    ("args", "def foo[T, U](x, y):", "define_foo = 1"),
    ("args", "def foo(\n    a,\n    b\n):", "definition = True"),
    ("args", "lambda: 1", "lambda_function = True"),
    ("args", "lambda x, y=1: x + y", "lambda_function_2 = True"),
    ("args", "async def _private_func(x):", "async_def_func = False"),

    # func_start (async, generics, newlines, decorators)
    ("func_start", "    def foo():", "def_func_not_anchor = True"),
    ("func_start", "async def foo():", "async_def = False"),
    ("func_start", "def foo[T, U](x):", "def_foo_T_U = 1"),
    ("func_start", "@decorator\ndef foo():", "def_not_here = False"),
    ("func_start", "def _private_method(self):", "_private = True"),

    # class_start (generics, multiline bases)
    ("class_start", "class Foo(Generic[T]):", "class_not_start = False"),
    ("class_start", "class Foo(\n    Base1,\n    Base2\n):", "class_not = False"),
    ("class_start", "class Foo[T, U](Base):", "class_T = False"),
    ("class_start", "class Foo:", "classy = False"),
    ("class_start", "class _Private:", "PrivateClass = False"),

    # structural_boundaries (keywords, encapsulation bypass)
    ("structural_boundaries", "await asyncio.sleep(1)", "awaiting = True"),
    ("structural_boundaries", "type Point = tuple[float, float]", "typedef = True"),
    ("structural_boundaries", "del x", "delete = True"),
    ("structural_boundaries", "global x", "global_var = True"),
    ("structural_boundaries", "nonlocal x", "nonlocal_var = True"),
]


@pytest.mark.parametrize("signature,positive,negative", _PY_SIMPLE_CASES)
def test_python_signature_positive_and_negative(signature, positive, negative):
    pattern = PY_RULES[signature]
    assert pattern is not None, f"python's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"python {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"python {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_python_comprehensions_was_fixed_from_a_javascript_copy_paste():
    """
    Regression test: python's comprehensions rule used to be
    `\\.(?:map|filter|reduce|...)\\s*\\(` -- JavaScript's Array-method idiom,
    copy-pasted in by mistake. Python has no builtin `.map(`/`.filter(` list
    methods; it has comprehension syntax. The old pattern never matched a
    single real Python comprehension and only fired incidentally on
    unrelated methods sharing a name (e.g. Django's queryset `.filter(...)`).
    """
    pattern = PY_RULES["comprehensions"]
    assert pattern.search("[x**2 for x in range(10)]"), "Failed to match a real list comprehension"
    assert pattern.search("{k: v for k, v in items}"), "Failed to match a real dict comprehension"
    assert pattern.search("{x for x in range(10)}"), "Failed to match a real set comprehension"
    assert pattern.search("sum(x for x in range(10))"), "Failed to match a real generator expression"
    assert not pattern.search("User.objects.filter(active=True)"), (
        "Incorrectly matched an unrelated .filter() method call (the old JS-idiom bug)"
    )


def test_python_comprehensions_redos_immunity():
    pattern = PY_RULES["comprehensions"]
    assert_redos_immune(pattern, "(" * 40000, timeout_sec=3.0)
    assert_redos_immune(pattern, "[" * 40000, timeout_sec=3.0)


def test_python_structural_boundaries_and_args():
    boundaries = PY_RULES["structural_boundaries"]
    for kw_snippet in ("def foo():", "class Foo:", "return x", "import os", "from os import path", "del x"):
        assert boundaries.search(kw_snippet), f"structural_boundaries failed to match {kw_snippet!r}"

    args = PY_RULES["args"]
    assert args.search("def foo(a, b):")
    assert args.search("async def foo(a, b):")
    assert args.search("lambda x: x + 1")


def test_python_func_start_skips_decorators_and_excludes_reserved_words():
    pattern = PY_RULES["func_start"]
    assert pattern.search("def foo():")
    assert pattern.search("    @staticmethod\n    @property\n    def foo():")
    assert pattern.search("async def foo():")


def test_python_class_start_captures_name_and_bases():
    pattern = PY_RULES["class_start"]
    m = pattern.search("class Dog(Animal, Mixin):")
    assert m is not None
    assert m.group(1) == "Dog"
    assert "Animal" in m.group(2)
    
    # Multiline
    m2 = pattern.search("class Foo(\n    Base1,\n    Base2\n):")
    assert m2 is not None
    assert m2.group(1) == "Foo"
    assert "Base2" in m2.group(2)
    
    # Generics
    m3 = pattern.search("class Foo(Generic[T]):")
    assert m3 is not None
    assert m3.group(1) == "Foo"
    assert m3.group(2) == "Generic[T]"



def test_python_api_excludes_underscore_prefixed_definitions():
    """api captures implicit-public root defs/classes; a leading underscore is explicitly private."""
    pattern = PY_RULES["api"]
    assert pattern.search("def public_func():")
    assert pattern.search("class PublicClass:")
    assert not pattern.search("def _private_func():"), "api incorrectly matched an underscore-prefixed function"
    assert not pattern.search("class _PrivateClass:"), "api incorrectly matched an underscore-prefixed class"


def test_python_import_dependency_capture():
    dep_pattern = PY_RULES["_dependency_capture"]
    m = dep_pattern.search("from os.path import join")
    assert m is not None
    assert "os.path" in m.groups()

    m2 = dep_pattern.search("import numpy")
    assert m2 is not None
    assert "numpy" in m2.groups()


def test_python_safety_bypasses_bare_except_vs_typed_except():
    """
    A bare `except:` or `except Exception:` swallows errors; a typed except
    does not. Bodies deliberately avoid a bare `pass` statement here -- `pass`
    is itself one of this rule's own alternatives (an empty handler body is
    a bypass regardless of exception type), which would trigger a match for
    the wrong reason and mask what this test is actually isolating.
    """
    pattern = PY_RULES["safety_bypasses"]
    assert pattern.search("except:\n    log(e)")
    assert pattern.search("except Exception:\n    log(e)")
    assert not pattern.search("except ValueError:\n    log(e)"), (
        "safety_bypasses incorrectly flagged a specific, typed except clause"
    )


def test_python_bitwise_ops_and_closures_do_not_collide():
    """
    The known bitwise_ops/closures ambiguity found in Rust (`|a| a + 1`) and
    C++ (`std::cout <<`) doesn't reproduce in python: the `lambda` keyword
    shares no token with `<<`, `>>`, `^`, `~`.
    """
    bitwise = PY_RULES["bitwise_ops"]
    closures = PY_RULES["closures"]
    assert bitwise.search("x = a << 2")
    assert not bitwise.search("f = lambda x: x + 1"), "bitwise_ops false-positived on a lambda"
    assert closures.search("f = lambda x: x + 1")
    assert not closures.search("x = a << 2"), "closures false-positived on a bitwise shift"


def test_python_explicit_casts_vs_pointers_no_overlap():
    """
    The known explicit_casts/pointers ambiguity found in C (cast syntax
    overlapping pointer-asterisk repetition) doesn't reproduce in python:
    explicit_casts checks builtin type calls (int(, str(, ...); pointers
    checks ctypes-specific tokens. No shared token between them.
    """
    casts = PY_RULES["explicit_casts"]
    pointers = PY_RULES["pointers"]
    assert casts.search("int('42')")
    assert not casts.search("ctypes.POINTER(ctypes.c_int)"), "explicit_casts false-positived on a ctypes pointer"
    assert pointers.search("ctypes.POINTER(ctypes.c_int)")
    assert not pointers.search("int('42')"), "pointers false-positived on a builtin cast"


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# CROSS-LANGUAGE SWEEP: LITERAL `()` TRAILING-\b BOUNDARY BUGS
# ==============================================================================
# Found while writing go's time_date_logic test (`time.Now()` never
# matched). Broadened the sweep to check every `\b(...)\b`-wrapped
# alternative ending in a literal empty-parens function call, since `)` is
# non-word and whatever follows a function call (`;`, a newline, another
# `.method()`, end of string) is never a word character -- the shared
# trailing \b can never fire. Affects 8 languages; bundled the same way as
# the earlier ReDoS (#631), symbolic-\b (#637), and @-boundary (#645) sweeps.


def test_python_globals_builtin_call_boundary_regression():
    r = LANGUAGE_DEFINITIONS["python"]["rules"]
    assert r["globals"].search("x = globals()")
    assert r["globals"].search("y = locals()")
