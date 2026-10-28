"""
#5909: calls_out gaps that need context a regex cannot carry (`_calls_out_rewrite`).

Tcl: a `switch` arm is `label body`. The label is a pattern, not a command, and a one-line body (`x { doX }`) is
not at command position. Scheme: a `let`-family binder (`(name init)`) is a name, not a call, for the named-let
first binding and for the second and later bindings of any let form.

Driven through `StructuralExtractor.splice()`, the path a scan takes.
"""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _calls(lang: str, code: str, unit: str = "p") -> list[str]:
    functions = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")["functions"]
    return {f["name"]: f for f in functions}[unit]["calls_out_to"]


def _tcl(body: str) -> list[str]:
    return _calls("tcl", "proc p {v} {\n" + body + "\n}\n")


@pytest.mark.parametrize(
    "arm",
    [
        "a { doA }",
        "a {doA}",
        "a { doA; doB }",
        "a {\n doA\n doB\n}",
        '"a b" { doA ; doB }',
        "{a b} { doA; doB }",
        "$x { doA; doB }",
        "default { doA; doB }",
        "a - \n default { doA; doB }",
        "a { if {$v} { doA } else { doB } }",
    ],
)
def test_a_switch_arm_body_is_scanned_and_its_label_is_not_a_call(arm):
    calls = _tcl("switch -exact -- $v {\n" + arm + "\n}")
    assert {"doA"} <= set(calls) and not {"a", "b", "default", "x"} & set(calls)
    if "doB" in arm:
        assert "doB" in calls


@pytest.mark.parametrize(
    "head", ["switch $v", "switch -- $v", "switch -glob -nocase -- [norm $v]", "switch -regexp -- $v"]
)
def test_every_switch_head_form_reaches_its_arms(head):
    assert {"doA", "doB"} <= set(_tcl(head + " {\n a { doA }\n b { doB }\n}"))


def test_the_arm_list_may_be_inline_and_not_braced():
    calls = _tcl("switch $v a { doA } b { doB }\nafter 5 { doC }")
    assert {"doA", "doB", "doC"} <= set(calls) and not {"a", "b"} & set(calls)


def test_a_switch_nested_in_an_arm_is_read_too():
    calls = _tcl("switch $v {\n a { switch $w { x { doX } y { doY } } }\n}")
    assert {"doX", "doY"} <= set(calls) and not {"a", "x", "y"} & set(calls)


def test_a_command_outside_a_switch_is_not_blanked():
    assert "withLock" in _tcl("withLock $m { doX }")
    assert "a" in _tcl("a { doX }")


@pytest.mark.parametrize("binder", ["a", "b", "c", "i", "j"])
def test_let_binders_are_not_calls(binder):
    code = (
        "(define (p x)\n  (let loop ((i (g 0)) (j (h 1)))\n    (let* ((a (f1 x)) (b (f2 a)) (c d)) (use a b))\n"
        "    (loop (nxt i))))\n"
    )
    calls = _calls("scheme", code)
    assert binder not in calls
    assert {"g", "h", "f1", "f2", "use", "loop", "nxt"} <= set(calls)


@pytest.mark.parametrize("form", ["let", "let*", "letrec", "letrec*", "fluid-let", "do"])
def test_every_binding_of_every_let_form_is_a_name(form):
    code = f"(define (p x)\n  ({form} ((aa (f1 x)) (bb (f2 x)) (cc (f3 x))) (body)))\n"
    calls = _calls("scheme", code)
    assert not {"aa", "bb", "cc"} & set(calls) and {"f1", "f2", "f3", "body"} <= set(calls)


def test_named_let_and_empty_bindings():
    code = "(define (p x)\n  (let loop () (loop))\n  (let () (real x)))\n"
    assert _calls("scheme", code) == ["loop", "real"]


def test_let_values_formals_are_names_and_the_init_is_a_call():
    code = "(define (p x)\n  (let-values (((q r) (floor/ x 2)) ((s) (one))) (use q r s)))\n"
    calls = _calls("scheme", code)
    assert not {"q", "r", "s"} & set(calls) and {"floor/", "one", "use"} <= set(calls)


def test_a_binding_whose_init_is_a_bare_name_leaves_no_call():
    assert _calls("scheme", "(define (p x)\n  (let ((a b) (c d)) (use a c)))\n") == ["use"]


def test_a_call_that_looks_like_a_binding_outside_a_let_is_kept():
    assert _calls("scheme", "(define (p x)\n  (foo (a) (b) (c)))\n") == ["foo", "a", "b", "c"]
