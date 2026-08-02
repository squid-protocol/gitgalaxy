"""
HTML extraction hardening (epic #813, issue #840). See
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
    assert_pathological_match,
    assert_redos_immune,
    assert_valid_dependency_match,
    assert_valid_match,
)

HTML_RULES = LANGUAGE_DEFINITIONS["html"]["rules"]

# ==============================================================================
# FUNC_START (func_start)
# ==============================================================================
FUNC_START_VALID = [
    ("<script>", "script"),
    ("<SCRIPT>", "SCRIPT"),
    ("<style>", "style"),
    ("<STYLE>", "STYLE"),
    ('<script type="module">', "script"),
    ("<script type='text/javascript'>", "script"),
    ("<style scoped>", "style"),
    ('<script defer async src="app.js">', "script"),
    ('<script\n  type="text/javascript"\n>', "script"),
    ('<style\tmedia="print"\n>', "style"),
    ('<script/type="module">', "script"),
    ("<script type=module>", "script"),
    ('<script\u0020type="text/javascript">', "script"),
]

FUNC_START_INVALID = [
    "< script >",
    "</script>",
    "<scripting>",
    "<stylesheet>",
    # TODO: Disguised tags (comments/strings) are very hard for naive regex
    # "<!-- <script> -->",
    # "<div title=\"<script>\">",
]

FUNC_START_PATHOLOGICAL = [
    ("<script" + " " * 10000 + ">", "script"),
    ("<script\n\r\t\f" + " " * 5000 + ">", "script"),
    ("<script type='text/javascript'" + " \n" * 500 + ">", "script"),
    ("<script>console.log('</script>');</script>", "script"),
    ("<script type=" + "a" * 1000 + ">", "script"),
]


@pytest.mark.parametrize("payload,expected_name", FUNC_START_VALID)
def test_html_func_start_valid(payload, expected_name):
    assert_valid_match(HTML_RULES["func_start"], payload, expected_name, "html.func_start")


@pytest.mark.parametrize("payload", FUNC_START_INVALID)
def test_html_func_start_invalid(payload):
    assert_invalid_no_match(HTML_RULES["func_start"], payload, "html.func_start")


@pytest.mark.parametrize("payload,expected_name", FUNC_START_PATHOLOGICAL)
def test_html_func_start_pathological(payload, expected_name):
    assert_pathological_match(HTML_RULES["func_start"], payload, expected_name, "html.func_start")


def test_html_func_start_redos_immunity():
    assert_redos_immune(HTML_RULES["func_start"], "<script" + " \n" * 10000 + ">", timeout_sec=1.0)


# ==============================================================================
# CLASS_START (class_start)
# ==============================================================================
CLASS_START_VALID = [
    ("<form>", "form"),
    ('<form action="/submit">', "form"),
    ("<FORM>", "FORM"),
    ("<table>", "table"),
    ('<table id="data">', "table"),
    ("<my-component>", "my-component"),
    ("<my-custom-element-123>", "my-custom-element-123"),
    ("<x-button>", "x-button"),
    ("<math-alpha>", "math-alpha"),
    ("<a-b>", "a-b"),
    ("<form\n method='POST'\n>", "form"),
    ('<table/class="test">', "table"),
]

CLASS_START_INVALID = [
    "<my_element>",  # Missing hyphen
    "<-component>",  # Starts with hyphen
    "<3d-model>",  # Must start with a letter
    "<formating>",  # Starts with 'format', but is not '<form>'
]

CLASS_START_PATHOLOGICAL = [
    ("<form" + " " * 10000 + ">", "form"),
    ('<table\r\n\tclass="complex \n table"' + " \n" * 500 + ">", "table"),
    ("<my-" + "-" * 500 + "component>", "my-" + "-" * 500 + "component"),
    ('<form class="""">', "form"),
    ("<table data-x='>'>", "table"),
]


@pytest.mark.parametrize("payload,expected_name", CLASS_START_VALID)
def test_html_class_start_valid(payload, expected_name):
    assert_valid_match(HTML_RULES["class_start"], payload, expected_name, "html.class_start")


@pytest.mark.parametrize("payload", CLASS_START_INVALID)
def test_html_class_start_invalid(payload):
    assert_invalid_no_match(HTML_RULES["class_start"], payload, "html.class_start")


@pytest.mark.parametrize("payload,expected_name", CLASS_START_PATHOLOGICAL)
def test_html_class_start_pathological(payload, expected_name):
    assert_pathological_match(HTML_RULES["class_start"], payload, expected_name, "html.class_start")


# ==============================================================================
# ARGS (args)
# ==============================================================================
ARGS_VALID = [
    ('data-foo="bar"', "data-foo"),
    ("data-foo='bar'", "data-foo"),
    ("data-foo=bar", "data-foo"),
    ('DATA-FOO="BAR"', "DATA-FOO"),
    ('aria-hidden="true"', "aria-hidden"),
    ('aria-labelledby="id1 id2"', "aria-labelledby"),
    ('name="user_name"', "name"),
    ('value="123"', "value"),
    ("value=''", "value"),
    ("data-is-active", "data-is-active"),
    ("aria-disabled", "aria-disabled"),
    ('data-custom-long-name-with-hyphens="test"', "data-custom-long-name-with-hyphens"),
    ('data-123="numeric"', "data-123"),
    ("value=123", "value"),
    ("name=first.last", "name"),
]

ARGS_INVALID = [
    'data -foo="bar"',
]

ARGS_PATHOLOGICAL = [
    ('data-foo  =  \n "bar"', "data-foo"),
    ("name\n=\n'bar'", "name"),
    ("value \t = \t 123", "value"),
    ("data-foo=unquoted\nvalue", "data-foo"),
    ("name=a'b'c\"", "name"),
    ("data-foo=bar/", "data-foo"),
    ('data-long="' + "a" * 10000 + '"', "data-long"),
    ('data-base64="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."', "data-base64"),
    (" ".join([f"data-bool-{i}" for i in range(500)]), "data-bool-0"),
]


@pytest.mark.parametrize("payload,expected_name", ARGS_VALID)
def test_html_args_valid(payload, expected_name):
    assert_valid_match(HTML_RULES["args"], payload, expected_name, "html.args")


@pytest.mark.parametrize("payload", ARGS_INVALID)
def test_html_args_invalid(payload):
    assert_invalid_no_match(HTML_RULES["args"], payload, "html.args")


@pytest.mark.parametrize("payload,expected_name", ARGS_PATHOLOGICAL)
def test_html_args_pathological(payload, expected_name):
    assert_pathological_match(HTML_RULES["args"], payload, expected_name, "html.args")


# ==============================================================================
# DEPENDENCY CAPTURE (_dependency_capture)
# ==============================================================================
DEPENDENCY_VALID = [
    ('<script src="app.js">', "app.js"),
    ("<script src='app.js'>", "app.js"),
    ("<script src=app.js>", "app.js"),
    ('<link href="style.css">', "style.css"),
    ("<link href='style.css'>", "style.css"),
    ("<link href=style.css>", "style.css"),
    ('<link rel="stylesheet" href="style.css">', "style.css"),
    ('<script type="module" src="app.js">', "app.js"),
    ('<script defer async src="//cdn.com/app.js">', "//cdn.com/app.js"),
    ('<script src="http://x.com/y.js?a=1&b=2#hash">', "http://x.com/y.js?a=1&b=2#hash"),
    ('<script/src="app.js">', "app.js"),
]

DEPENDENCY_INVALID = [
    "<script src>",
    "<script src=>",
    "<link href>",
]

DEPENDENCY_PATHOLOGICAL = [
    ('<script src  =  "app.js">', "app.js"),
    ('<link\n\n\nhref\n=\n"style.css">', "style.css"),
    ("<script \n src \n = \n 'app.js' >", "app.js"),
    ('<script src="data:text/javascript;base64,Y29uc29sZS5sb2coJ2hlbGxvJyk7">', "data:text/javascript"),
    ('<link href="http://example.com/style.css?' + "a=1&" * 1000 + '">', "http://example.com/style.css"),
    ("<link href=style.css?a=1&b=2 rel=stylesheet>", "style.css?a=1&b=2"),
    ("<script src=app.js?v=1.0\ndefer>", "app.js?v=1.0"),
    ('<link href="  style.css  ">', "  style.css  "),
]


@pytest.mark.parametrize("payload,expected_name", DEPENDENCY_VALID)
def test_html_dependency_valid(payload, expected_name):
    assert_valid_dependency_match(HTML_RULES["_dependency_capture"], payload, expected_name, "html.dependency")


@pytest.mark.parametrize("payload", DEPENDENCY_INVALID)
def test_html_dependency_invalid(payload):
    assert_invalid_no_match(HTML_RULES["_dependency_capture"], payload, "html.dependency")


@pytest.mark.parametrize("payload,expected_name", DEPENDENCY_PATHOLOGICAL)
def test_html_dependency_pathological(payload, expected_name):
    assert_pathological_match(HTML_RULES["_dependency_capture"], payload, expected_name, "html.dependency")
