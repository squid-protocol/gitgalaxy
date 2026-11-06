"""#6572: a `use`/`alias` line inside a delimited Elixir sigil body (`~S(..)`, `~s|..|`, ...) is text, not an import."""

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
    [("(", ")"), ("[", "]"), ("{", "}"), ("<", ">"), ("|", "|"), ("/", "/")],
)
@pytest.mark.parametrize("letter", ["S", "s", "r", "w"])
def test_use_inside_a_delimited_sigil_is_no_import(letter, opener, closer):
    src = f"use Real.Before\nx = ~{letter}{opener}\n{_BODY}{closer}\nalias Real.After\n"
    assert _imports(src) == {"Real.Before", "Real.After"}


def test_crlf_sigil():
    src = f"use A.One\r\nx = ~S(\r\n{_BODY})\r\nimport A.Two\r\n"
    assert _imports(src) == {"A.One", "A.Two"}


def test_single_line_sigil_leaves_neighbours_alone():
    assert _imports("use A.One\nx = ~r/ab+/i\nuse A.Two\n") == {"A.One", "A.Two"}


def test_unterminated_sigil_stops_at_the_cap():
    src = "x = ~S(\n" + "y = 1\n" * 5000 + "use A.Far\n"
    assert "A.Far" in _imports(src)


def test_heredoc_sigil_still_blanked():
    assert _imports(f'use A.One\nx = ~S"""\n{_BODY}"""\nuse A.Two\n') == {"A.One", "A.Two"}


def test_many_unterminated_openers_stay_linear():
    def cost(n: int) -> float:
        src = "x = ~S(\n" * n
        t = time.perf_counter()
        _imports(src)
        return time.perf_counter() - t

    cost(200)
    small, big = cost(2000), cost(4000)
    assert big < max(small * 6, 0.5)


@pytest.mark.parametrize("quote", ['"', "'"])
@pytest.mark.parametrize("letter", ["S", "s", "r", "w"])
def test_use_inside_a_quote_delimited_sigil_is_no_import(letter, quote):
    src = f"use Real.Before\nx = ~{letter}{quote}\n{_BODY}{quote}\nalias Real.After\n"
    assert _imports(src) == {"Real.Before", "Real.After"}


@pytest.mark.parametrize(("opener", "closer"), [("(", ")"), ('"', '"'), ("{", "}")])
def test_multi_uppercase_letter_sigil_is_no_import(opener, closer):
    src = f"use Real.Before\nx = ~MAT{opener}\n{_BODY}{closer}\nalias Real.After\n"
    assert _imports(src) == {"Real.Before", "Real.After"}


@pytest.mark.parametrize("quote", ['"', "'"])
def test_empty_quote_sigil_leaves_neighbours_alone(quote):
    src = f"use A.One\nx = ~s{quote}{quote}\nuse A.Two\n"
    assert _imports(src) == {"A.One", "A.Two"}


@pytest.mark.parametrize("quote", ['"', "'"])
def test_quote_sigil_heredoc_still_blanked_whole(quote):
    q3 = quote * 3
    src = f"use A.One\nx = ~s{q3}\n{_BODY}{q3}\nuse A.Two\n"
    assert _imports(src) == {"A.One", "A.Two"}


def test_crlf_quote_sigil():
    src = f'use A.One\r\nx = ~s"\r\n{_BODY}"\r\nimport A.Two\r\n'
    assert _imports(src) == {"A.One", "A.Two"}


def test_plain_string_is_untouched():
    assert _imports('use A.One\nx = "a\nuse A.Two\n"\nuse A.Three\n') >= {"A.One", "A.Two", "A.Three"}


def test_unterminated_quote_sigil_stops_at_the_cap():
    src = 'x = ~s"\n' + "y = 1\n" * 5000 + "use A.Far\n"
    assert "A.Far" in _imports(src)


def test_many_unterminated_quote_openers_stay_linear():
    def cost(n: int) -> float:
        src = 'x = ~s"\n' * n
        t = time.perf_counter()
        _imports(src)
        return time.perf_counter() - t

    cost(200)
    small, big = cost(2000), cost(4000)
    assert big < max(small * 6, 0.5)
