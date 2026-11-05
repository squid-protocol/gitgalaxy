"""#6572: a `use A::B;` inside a Perl heredoc body is text, not an import."""

import time

import pytest

from gitgalaxy.galaxyscope import extract_raw_imports
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANG = LANGUAGE_DEFINITIONS["perl"]
_REGEX = _LANG["rules"]["_dependency_capture"]
_BODY = "  use Doc::Only;\n  require Doc::Required;\n"


def _imports(src: str) -> set[str]:
    return extract_raw_imports(_REGEX, src, _LANG)


@pytest.mark.parametrize(
    ("opener", "terminator"),
    [
        ("print <<'EOT';", "EOT"),
        ("print <<EOT;", "EOT"),
        ('my $t = <<"EOT";', "EOT"),
        ("my $t = <<~EOT;", "  EOT"),
        ("my $t = <<~'EOT';", "EOT"),
        ("foo(1, <<EOT, 2);", "EOT"),
        ("return <<END_TEXT;", "END_TEXT"),
    ],
)
def test_use_inside_a_heredoc_is_no_import(opener, terminator):
    src = f"use Real::Before;\n{opener}\n{_BODY}{terminator}\nuse Real::After;\n"
    assert _imports(src) == {"Real::Before", "Real::After"}


def test_two_heredocs_and_crlf():
    src = f"use A::One;\r\nprint <<EOT;\r\n{_BODY}EOT\r\nprint <<'TWO';\r\n{_BODY}TWO\r\nuse A::Two;\r\n"
    assert _imports(src) == {"A::One", "A::Two"}


def test_heredoc_at_end_of_file_without_newline():
    assert _imports(f"use A::One;\nprint <<EOT;\n{_BODY}EOT") == {"A::One"}


def test_a_shift_without_terminator_swallows_nothing():
    src = "use A::One;\nmy $x = 1 << FOO;\nuse A::Two;\n"
    assert _imports(src) == {"A::One", "A::Two"}


def test_unterminated_heredoc_blanks_nothing():
    src = f"use A::One;\nprint <<EOT;\n{_BODY}use A::Two;\n"
    assert {"A::One", "A::Two"} <= _imports(src)


def test_terminator_must_be_alone_on_its_line():
    src = f"print <<EOT;\nEOT not yet\n{_BODY}EOT\nuse A::After;\n"
    assert _imports(src) == {"A::After"}


def test_many_unterminated_openers_is_not_quadratic():
    src = "print <<EOT;\nsome text line\n" * 3000
    start = time.perf_counter()
    _imports(src)
    assert time.perf_counter() - start < 5
