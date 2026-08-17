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

CSS_DEFS = LANGUAGE_DEFINITIONS["css"]["rules"]

# --- PAYLOADS ---

VALID_FUNC_STARTS = [
    (
        "@media screen { @supports (display: grid) { @keyframes slide { 0% { opacity: 0; } 100% { opacity: 1; } } } }",
        "@media",
    ),
    (
        "@media\n\r\t (min-width:\n  500px)\n   {\n  .foo { color: red; }\n}\n@-webkit-keyframes\nspin { }",
        "@media",
    ),
]

INVALID_FUNC_STARTS = [
    '/* @media print { body { display: none; } } */ .fake { content: "@keyframes spin { 0% {} }"; }',
]

PATHOLOGICAL_FUNC_STARTS = [
    "@media" + " \n\t" * 1000 + "(min-width: 0) {",
]

VALID_CLASS_STARTS = [
    (
        ".btn, #nav > .dropdown ~ .item + #active::before { color: blue; }",
        ".btn",
    ),
    (
        ".\\31 23-number, .\\@special\\+chars, #\\#fake-id-hash { display: none; }",
        ".\\31 23-number",
    ),
    (
        ".foo\n\n\r\t  ,\n\n  #bar\n\n\r  { display: block; }",
        ".foo",
    ),
]

INVALID_CLASS_STARTS = [
    'input[value=".not-a-class"] { content: "#not-an-id"; } /* .comment-class {} */',
]

PATHOLOGICAL_CLASS_STARTS = [
    ".a" + " > .b" * 1000 + " {",
    ".class" + " \n" * 1000 + "{",
]

VALID_ARGS = [
    (
        "width: calc(100% - var(--sidebar, calc(var(--base) * 2px)));",
        "calc(100% - var(--sidebar, calc(var(--base) * 2px)))",
    ),
    (
        "background: url(data:image/svg+xml;base64,PHN2ZyB...=); mask-image: url( http://evil.com/path?a=1&b=2 );",
        "url(data:image/svg+xml;base64,PHN2ZyB...=)",
    ),
    (
        "color: VaR(\n  --primary-color\n ); transform: CaLc(\n 10px\n + \n 5% \n);",
        "VaR(\n  --primary-color\n )",
    ),
]

INVALID_ARGS = [
    'content: "calc(100% - 10px)"; /* color: var(--hacked); */',
]

PATHOLOGICAL_ARGS = [
    "calc(" + "var(" * 50 + "--x" + ")" * 50 + ")",
]

VALID_DEPENDENCIES = [
    (
        '@import "style.css";\n@import \'print.css\' print;\n@import url("mobile.css") screen and (max-width: 600px);',
        "style.css",
    ),
    (
        "@import\n\turl( \npath/to/styles.css \n)\n\t;",
        "path/to/styles.css",
    ),
]

INVALID_DEPENDENCIES = [
    '/* @import "malware.css"; */\nbody { font-family: \'@import "font.css"\'; content: "@import url(\'fake.css\');"; }',
]

PATHOLOGICAL_DEPENDENCIES = [
    "@import" + " \n\t" * 1000 + "url( \n\t" * 100 + '"file.css"',
]

# --- TESTS ---


@pytest.mark.parametrize("payload,expected_matches", VALID_FUNC_STARTS)
def test_css_func_start_valid(payload, expected_matches):
    assert_valid_match(CSS_DEFS["func_start"], payload, expected_matches, "css.func_start")


@pytest.mark.parametrize("payload", INVALID_FUNC_STARTS)
def test_css_func_start_invalid(payload):
    assert_invalid_no_match(CSS_DEFS["func_start"], payload, "css.func_start")


@pytest.mark.parametrize("payload", PATHOLOGICAL_FUNC_STARTS)
def test_css_func_start_redos(payload):
    assert_redos_immune(CSS_DEFS["func_start"], payload)


@pytest.mark.parametrize("payload,expected_matches", VALID_CLASS_STARTS)
def test_css_class_start_valid(payload, expected_matches):
    assert_valid_match(CSS_DEFS["class_start"], payload, expected_matches, "css.class_start")


@pytest.mark.parametrize("payload", INVALID_CLASS_STARTS)
def test_css_class_start_invalid(payload):
    assert_invalid_no_match(CSS_DEFS["class_start"], payload, "css.class_start")


@pytest.mark.parametrize("payload", PATHOLOGICAL_CLASS_STARTS)
def test_css_class_start_redos(payload):
    assert_redos_immune(CSS_DEFS["class_start"], payload)


@pytest.mark.parametrize("payload,expected_matches", VALID_ARGS)
def test_css_args_valid(payload, expected_matches):
    assert_valid_match(CSS_DEFS["args"], payload, expected_matches, "css.args")


@pytest.mark.parametrize("payload", PATHOLOGICAL_ARGS)
def test_css_args_redos(payload):
    assert_redos_immune(CSS_DEFS["args"], payload)


@pytest.mark.parametrize("payload,expected_matches", VALID_DEPENDENCIES)
def test_css_dependency_valid(payload, expected_matches):
    assert_valid_dependency_match(CSS_DEFS["_dependency_capture"], payload, expected_matches, "css._dependency_capture")


@pytest.mark.parametrize("payload", INVALID_DEPENDENCIES)
def test_css_dependency_invalid(payload):
    assert_invalid_no_match(CSS_DEFS["_dependency_capture"], payload, "css._dependency_capture")


@pytest.mark.parametrize("payload", PATHOLOGICAL_DEPENDENCIES)
def test_css_dependency_redos(payload):
    assert_redos_immune(CSS_DEFS["_dependency_capture"], payload)
