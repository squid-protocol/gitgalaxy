"""#8161 (X6): calls inside JS/TS template-literal holes and Python f-string holes are calls, and a JS/TS
regex literal holding a quote or backtick no longer pairs with a later one and hides the units between."""

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.template_holes import expose_js_holes, expose_python_holes
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _units(lang: str, code: str) -> dict[str, list[str]]:
    parsed = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(code, "")
    return {fn["name"]: fn["calls_out_to"] for fn in parsed["functions"]}


TS = (
    "export function helper(n: number): string {\n  return String(n);\n}\n"
    "export function wrap(s: string): string {\n  return s;\n}\n"
    "export function c_tpl(n: number): string {\n"
    "  return `value ${helper(n)} and ${wrap(`inner ${helper(n + 1)}`)} done`;\n"
    "}\n"
    "export function c_obj(n: number): string {\n  return `${ { a: helper(n) }.a }`;\n}\n"
    "export function c_plain(): string {\n  return `no ${'holes'} here(x)` + 'f(y)';\n}\n"
)


@pytest.mark.parametrize("lang", ["typescript", "javascript"])
def test_calls_in_template_holes_are_found(lang):
    code = TS if lang == "typescript" else TS.replace(": number", "").replace(": string", "")
    units = _units(lang, code)
    assert set(units["c_tpl"]) == {"helper", "wrap"}
    assert units["c_obj"] == ["helper"]
    assert units["c_plain"] == []  # literal text is never a call


@pytest.mark.parametrize("lang", ["typescript", "javascript"])
def test_regex_literal_with_a_backtick_hides_no_unit(lang):
    code = (
        "export const re1 = /^[a-z`{|}~-]+$/;\n\n"
        "export function lost1() {\n  return helperX();\n}\n\n"
        "const tpl = `abc`;\n\n"
        "export const ok = (s) => /^['`]+$/.test(s);\n\n"
        "export function lost2() {\n  return helperX();\n}\n\n"
        "export function helperX() {\n  return 1;\n}\n"
    )
    units = _units(lang, code)
    assert units["lost1"] == ["helperX"]
    assert units["lost2"] == ["helperX"]


def test_python_fstring_holes_are_calls():
    code = (
        "def helper(x):\n    return x\n\n\n"
        "def tf():\n    return 1\n\n\n"
        "def t_fstring(v):\n"
        "    return f\"value={tf()} {helper(v)!r:>10} {{literal()}} {v['k']}\"\n\n\n"
        "def t_nested(v):\n"
        '    return f"{helper(f\'{tf()}\')}" + rf"\\d{helper(2)}" + "{notacall()}"\n\n\n'
        'def t_triple(v):\n    return f"""\n    {helper(v)}\n    """\n'
    )
    units = _units("python", code)
    assert set(units["t_fstring"]) == {"tf", "helper"}  # `{{literal()}}` is escaped text
    assert set(units["t_nested"]) == {"helper", "tf"}  # a plain string's `{notacall()}` is text
    assert units["t_triple"] == ["helper"]


@pytest.mark.parametrize(
    "src,expected",
    [
        ("a = `x ${f(1)} y`;", 'a = ""+(f(1));'),
        ("a = `x\n${f(1)}`;", 'a = ""\n+(f(1));'),
        ("a = `plain`;", "a = `plain`;"),
        ("a = '${f()}';", "a = '${f()}';"),
        ("// `${f()}`\nb", "// `${f()}`\nb"),
        ("r = /`/; t = `${g()}`", 'r = /`/; t = ""+(g())'),
        ("q = a / b / `${g()}`.length", 'q = a / b / ""+(g()).length'),
    ],
)
def test_expose_js_holes(src, expected):
    assert expose_js_holes(src) == expected


@pytest.mark.parametrize(
    "src,expected",
    [
        ('x = f"a {g(1)} b"', 'x = ""+(g(1))'),
        ('x = f"{a!r} {b:>{w}} {c=}"', 'x = ""+(a)+(b)+(c)'),
        ('x = f"{{g()}}"', 'x = ""'),
        ('x = "{g()}"', 'x = "{g()}"'),
        ("# f'{g()}'\ny", "# f'{g()}'\ny"),
        ('elif"{g()}"', 'elif"{g()}"'),
    ],
)
def test_expose_python_holes(src, expected):
    assert expose_python_holes(src) == expected
