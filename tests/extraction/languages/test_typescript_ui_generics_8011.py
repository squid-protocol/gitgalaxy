"""gitgalaxy#8011 (TS ui_framework on type assertions) and the TS half of #8010 (class `extends`
counted as generics)."""

from __future__ import annotations

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS as LD

TS = LD["typescript"]["rules"]


def _hits(rule: str, text: str) -> list[str]:
    return [m.group(0).strip() for m in TS[rule].finditer(text)]


@pytest.mark.parametrize(
    "text",
    ["const x = <E1>node;", "return <NamedTypeNode>factory.create();", "f(<Expression>arg, <Node>other);"],
)
def test_type_assertion_is_not_ui(text):
    assert _hits("ui_framework", text) == []


@pytest.mark.parametrize(
    "text",
    [
        "return <Widget prop={1} />;",
        "return <Widget />;",
        "return <Layout title='x'>{children}</Layout>;",
        "return <Foo.Bar>hi</Foo.Bar>;",
        'return <Panel data-id="p">x</Panel>;',
    ],
)
def test_jsx_component_is_ui(text):
    assert _hits("ui_framework", text)


def test_class_heritage_extends_is_not_generic():
    assert _hits("generics", "class A extends B {") == []
    assert _hits("generics", "interface I extends J {}") == []


@pytest.mark.parametrize(
    "text",
    ["type F<T> = T extends string ? 1 : 2;", "function f<T extends Node>(x: T) {}", "let k: keyof Foo;"],
)
def test_real_generics_still_count(text):
    assert _hits("generics", text)
