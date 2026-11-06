"""#6572: a `use`/`alias` line inside an ordinary multi-line Elixir "..." string is text, not an import."""

import time

from gitgalaxy.galaxyscope import extract_raw_imports
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANG = LANGUAGE_DEFINITIONS["elixir"]
_REGEX = _LANG["rules"]["_dependency_capture"]
_BODY = "  use Doc.Only\n  alias Doc.Alias\n"


def _imports(src: str) -> set[str]:
    return extract_raw_imports(_REGEX, src, _LANG)


def test_multiline_string_body_is_no_import():
    assert _imports(f'use A.One\nx = "\n{_BODY}"\nalias A.Two\n') == {"A.One", "A.Two"}


def test_crlf_string():
    assert _imports(f'use A.One\r\nx = "\r\n{_BODY}"\r\nuse A.Two\r\n') == {"A.One", "A.Two"}


def test_escaped_quote_does_not_close_the_string():
    assert _imports(f'use A.One\nx = "a \\"\n{_BODY}"\nuse A.Two\n') == {"A.One", "A.Two"}


def test_quote_in_comment_blanks_nothing_real():
    assert _imports('use A.One\n# say "hi\nuse A.Two\n') == {"A.One", "A.Two"}


def test_empty_string_and_one_line_string_leave_neighbours():
    assert _imports('use A.One\nx = ""\ny = "a b"\nuse A.Two\n') == {"A.One", "A.Two"}


def test_heredoc_and_sigil_still_blanked():
    src = f'use A.One\nx = """\n{_BODY}"""\ny = ~S(\n{_BODY})\nuse A.Two\n'
    assert _imports(src) == {"A.One", "A.Two"}


def test_unterminated_string_stops_at_the_cap():
    assert "A.Far" in _imports('x = "\n' + "y = 1\n" * 5000 + "use A.Far\n")


def test_many_unterminated_openers_stay_linear():
    def cost(n: int) -> float:
        src = 'x = "\n' * n
        t = time.perf_counter()
        _imports(src)
        return time.perf_counter() - t

    cost(200)
    small, big = cost(2000), cost(4000)
    assert big < max(small * 6, 0.5)
