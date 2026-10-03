"""
#3329: the receiver chain before each callee, captured beside calls_out_to for the
C-style invocation family. Driven end to end through `splice()` so the literal shield
and the calls_out filters apply exactly as in a scan.
"""

import time

import pytest

from gitgalaxy.core.detector import StructuralExtractor, _call_qualifier
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _quals(lang: str, code: str, fn: str) -> dict[str, list[str]]:
    for f in StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]:
        if f["name"] == fn:
            return f["calls_out_qualifiers"]
    raise AssertionError(f"{fn} not extracted")


@pytest.mark.parametrize(
    "lang, code, fn, expected",
    [
        (
            "python",
            "def run(x):\n    utils.parse(x)\n    self.save()\n    save()\n    os.path.join(x)\n",
            "run",
            {"parse": ["utils"], "save": ["self", ""], "join": ["os.path"]},
        ),
        (
            "javascript",
            "function run(a) {\n  this.load(a);\n  a?.save();\n}\n",
            "run",
            {"load": ["this"], "save": ["a"]},
        ),
        ("java", "class A {\n  void run(int a) {\n    Util.parse(a);\n  }\n}\n", "run", {"parse": ["Util"]}),
        (
            "php",
            "<?php\nfunction run($x) {\n  $this->save($x);\n  Store::load($x);\n}\n",
            "run",
            {"save": ["this"], "load": ["Store"]},
        ),
        ("cpp", "void run(int a) {\n  p->step(a);\n  std::sort(a);\n}\n", "run", {"step": ["p"], "sort": ["std"]}),
        ("go", "package m\nfunc Run(a int) {\n  pkg.Do(a)\n}\n", "Run", {"Do": ["pkg"]}),
        ("rust", "fn run() {\n  Store::new();\n}\n", "run", {"new": ["Store"]}),
    ],
)
def test_receivers_by_language(lang, code, fn, expected):
    assert _quals(lang, code, fn) == expected


def test_expression_receiver_has_no_name():
    assert _quals("python", "def run(x):\n    get_store().save(x)\n    xs[0].load()\n", "run") == {
        "get_store": [""],
        "save": ["<expr>"],
        "load": ["<expr>"],
    }


def test_qualifiers_cover_exactly_the_emitted_callees():
    # filtered names (keywords, self-recursion) carry no qualifier entry either
    q = _quals("python", "def run(x):\n    if (x): run(x)\n    obj.save()\n", "run")
    assert q == {"save": ["obj"]}


def test_non_c_style_languages_capture_no_qualifier():
    code = "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. P.\n       PROCEDURE DIVISION.\n       MAIN-PARA.\n           PERFORM SUB-PARA.\n       SUB-PARA.\n           STOP RUN.\n"
    for f in StructuralExtractor("cobol", LANGUAGE_DEFINITIONS).splice(code, "")["functions"]:
        assert f.get("calls_out_qualifiers", {}) == {}


def test_walk_is_bounded():
    # a pathological receiver chain costs a fixed walk, never a scan of the text
    text = "a." * 200_000 + "b"
    t = time.perf_counter()
    q = _call_qualifier(text, len(text) - 1)
    assert time.perf_counter() - t < 0.05
    assert q == "a.a.a.a"
    long_ident = "x" * 100_000 + ".f"
    assert len(_call_qualifier(long_ident, len(long_ident) - 1)) <= 64


def test_java_lambda_arrow_is_not_a_receiver_separator():
    # #3837: in java `->` only ends a lambda's parameters, so `() -> toJson(gson, x)`
    # is a bare call to toJson, not a call on an `<expr>` receiver.
    code = "class A {\n  void run(Gson gson, Object x) {\n    Runnable r = () -> toJson(gson, x);\n    this.save();\n  }\n}\n"
    quals = _quals("java", code, "run")
    assert quals["toJson"] == [""]
    assert quals["save"] == ["this"]


def test_arrow_stays_a_separator_outside_java():
    # PHP and C/C++ member access still split on `->`.
    assert _call_qualifier("$this->save(", len("$this->")) == "this"
    assert _call_qualifier("p->f(", len("p->")) == "p"


def test_spread_operator_is_not_a_receiver():
    # #3787: `...f()` is a bare call and `...ns.f()` a call on `ns`; the spread's dots are
    # not a member access, so neither has an `<expr>` receiver. `a.b()` and `a.f()` stay.
    assert _call_qualifier("x(...f(", len("x(...")) == ""
    assert _call_qualifier("{ ...f(", len("{ ...")) == ""
    assert _call_qualifier("x(...errorUtil.errToObj(", len("x(...errorUtil.")) == "errorUtil"
    assert _call_qualifier("x(...a.b.f(", len("x(...a.b.")) == "a.b"
    assert _call_qualifier("x(a.f(", len("x(a.")) == "a"
    code = "function run(v, i) {\n  r.push(...parseCaseValue(v));\n  s.parse({ ...makeBig(i), ...errorUtil.errToObj(v) });\n}\n"
    q = _quals("typescript", code, "run")
    assert q["parseCaseValue"] == [""]
    assert q["makeBig"] == [""]
    assert q["errToObj"] == ["errorUtil"]
    assert q["push"] == ["r"]
