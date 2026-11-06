"""#6572: a Go grouped import block may hold `;`-separated specs on one line."""

import time

import pytest

from gitgalaxy.galaxyscope import extract_raw_imports
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANG = LANGUAGE_DEFINITIONS["go"]
_REGEX = _LANG["rules"]["_dependency_capture"]


def _imports(src: str) -> set[str]:
    return extract_raw_imports(_REGEX, src, _LANG)


@pytest.mark.parametrize(
    ("src", "want"),
    [
        ('import (\n\t"f/g"; "h/i"\n)\n', {"f/g", "h/i"}),
        ('import ("a"; "b")\n', {"a", "b"}),
        ('import (\n\t_ "a/b"; x "c"; . "d";\n\t"e"\n)\n', {"a/b", "c", "d", "e"}),
        ('import (\n\t"a"; "b" // note\n\t"c"\n)\n', {"a", "b", "c"}),
        ('import (\n\t"a"\n\t"b"\n)\n', {"a", "b"}),
        ('import "a"\n', {"a"}),
        ('import x "a"\n', {"a"}),
    ],
)
def test_specs_are_read(src, want):
    assert _imports("package p\n\n" + src) == want


def test_raw_string_block_is_still_no_import():
    src = 'package p\n\nvar t = `import (\n\t"a"; "b"\n)\n`\n'
    assert _imports(src) == set()


def test_code_after_semicolon_is_no_import():
    assert _imports("package p\n\nfunc f() { x := g(); _ = x }\n") == set()


def test_pathological_line_is_bounded():
    src = "import (\n" + '\t"a"; ' * 5000 + "\n" + '\t"b"\n' * 2000
    t = time.perf_counter()
    _imports(src)
    assert time.perf_counter() - t < 5
