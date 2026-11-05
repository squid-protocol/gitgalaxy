"""#6572: a `use`/`alias` line inside an Elixir heredoc (@moduledoc, @doc, sigil) is text, not an import."""

import time

import pytest

from gitgalaxy.galaxyscope import extract_raw_imports
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANG = LANGUAGE_DEFINITIONS["elixir"]
_REGEX = _LANG["rules"]["_dependency_capture"]
_BODY = "  use Doc.Only\n  alias Doc.Alias\n  import Doc.Imp\n"


def _imports(src: str) -> set[str]:
    return extract_raw_imports(_REGEX, src, _LANG)


@pytest.mark.parametrize(
    ("opener", "closer"),
    [
        ('@moduledoc """', '"""'),
        ('@doc """', '"""'),
        ('x = ~S"""', '"""'),
        ('x = ~s"""', '"""'),
        ("x = ~S'''", "'''"),
        ("@moduledoc '''", "'''"),
    ],
)
def test_use_inside_a_heredoc_is_no_import(opener, closer):
    src = f"use Real.Before\n{opener}\n{_BODY}{closer}\nalias Real.After\n"
    assert _imports(src) == {"Real.Before", "Real.After"}


def test_two_heredocs_and_crlf():
    src = f'use A.One\r\n@doc """\r\n{_BODY}"""\r\n@doc """\r\n{_BODY}"""\r\nimport A.Two\r\n'
    assert _imports(src) == {"A.One", "A.Two"}


def test_unterminated_heredoc_blanks_nothing():
    assert _imports('use A.One\nx = """\nuse A.Two\n') == {"A.One", "A.Two"}


def test_stray_quote_in_a_comment_blanks_no_import():
    assert _imports('# say "hi\nuse A.One\nx = "q"\nuse A.Two\n') == {"A.One", "A.Two"}


def test_many_unterminated_openers_stay_linear():
    def cost(n: int) -> float:
        src = 'x = """\n' * n
        t = time.perf_counter()
        _imports(src)
        return time.perf_counter() - t

    cost(200)
    small, big = cost(2000), cost(4000)
    assert big < max(small * 6, 0.5)
