"""#6572: an import-shaped line inside a multi-line Go raw string is data, not an import."""

import time

import pytest

from gitgalaxy.galaxyscope import extract_raw_imports
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANG = LANGUAGE_DEFINITIONS["go"]
_REGEX = _LANG["rules"]["_dependency_capture"]


def _imports(src: str) -> set[str]:
    return extract_raw_imports(_REGEX, src, _LANG)


_REAL = 'import (\n\t"os"\n\t"testing"\n)\n'

_EMBEDDED = (
    "func f() {\n"
    '\terr := os.WriteFile(name, []byte(`package main\n\nimport (\n\t"fmt"\n\t"os"\n\n'
    '\t"github.com/spf13/cobra"\n)\n\nvar x = 1\n`), 0600)\n}\n'
)


def test_import_block_inside_raw_string_is_no_import():
    assert _imports("package p\n\n" + _REAL + "\n" + _EMBEDDED) == {"os", "testing"}


def test_real_imports_after_a_raw_string_are_kept():
    src = 'package p\n\nvar t = `a\nb`\n\nimport "fmt"\n'
    assert _imports(src) == {"fmt"}


@pytest.mark.parametrize(
    "line",
    ['import "fmt"', "import `fmt`", 'import f "fmt"', 'import ( "fmt" )', 'import (\n\t"fmt"\n)'],
)
def test_real_import_forms_survive(line):
    assert _imports(f"package p\n\n{line}\n") == {"fmt"}


@pytest.mark.parametrize("literal", ["'`'", '"`"', '"a`b"'])
def test_backtick_in_rune_or_string_does_not_pair(literal):
    src = f'package p\n\nvar c = {literal}\n\nimport (\n\t"fmt"\n\t"os"\n)\n'
    assert _imports(src) == {"fmt", "os"}


def test_bare_quoted_line_in_raw_string_is_no_import():
    src = 'package p\n\nvar t = `\n"fmt"\n"os"\n)\n`\n'
    assert _imports(src) == set()


def test_unterminated_backticks_stay_linear():
    src = "package p\n" + "var s = `x\n" * 3000
    t = time.perf_counter()
    _imports(src)
    assert time.perf_counter() - t < 5


def test_one_line_raw_string_before_the_embedded_program_keeps_pairing():
    # cobra_test.go: a one-line `{{...}}` template precedes the embedded program.
    src = "package p\n\n" + _REAL + "\nvar u = `{{if t}}{{h}}{{end}}`\n" + _EMBEDDED
    assert _imports(src) == {"os", "testing"}
