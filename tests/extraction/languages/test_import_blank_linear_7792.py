"""#7792: import blanking must stay linear when a terminator is missing (doubling the input must not quadruple time)."""

import time

import pytest

from gitgalaxy.galaxyscope import _blank_with_heredocs, extract_raw_imports
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


def _imports(lang: str, src: str) -> set[str]:
    d = LANGUAGE_DEFINITIONS[lang]
    return extract_raw_imports(d["rules"]["_dependency_capture"], src, d)


def _best_of(fn, runs: int = 3) -> float:
    best = float("inf")
    for _ in range(runs):
        start = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - start)
    return best


def _assert_linear(fn, unit: str) -> None:
    small, large = _best_of(lambda: fn(unit * 2000)), _best_of(lambda: fn(unit * 4000))
    assert large < max(small * 3.2, 0.5)


@pytest.mark.parametrize(
    ("lang", "unit"),
    [
        ("java", 'String s = "x";\n'),
        ("kotlin", 'val s = "x"\n'),
        ("scala", 'val s = "x"\n'),
        ("go", "x := `a\nb\n"),
        ("go", 'x := "a\n'),
        ("perl", "print <<EOT;\nsome text line\n"),
    ],
)
def test_unterminated_openers_scale_linearly(lang, unit):
    opener = {"java": '"""\n', "kotlin": '"""\n', "scala": '"""\n'}.get(lang, "")
    _assert_linear(lambda s: _imports(lang, s + opener), unit)


def test_heredoc_blanker_many_openers_one_tag_and_distinct_tags():
    opener = r"<<(?P<tag>[A-Z]\w*)\n"
    same = "<<EOT\ntext\n"
    _assert_linear(lambda s: _blank_with_heredocs("(?!x)x", opener, s), same)
    for n in (200, 400):
        src = "".join(f"<<T{i}\ntext\n" for i in range(n))
        assert _blank_with_heredocs("(?!x)x", opener, src) == src


def test_heredoc_blanker_keeps_length_and_newlines():
    src = "a <<EOT\nuse X;\nEOT\nb\n"
    out = _blank_with_heredocs("(?!x)x", r"<<(?P<tag>[A-Z]\w*)\n", src)
    assert len(out) == len(src) and out.count("\n") == src.count("\n")
    assert "use X" not in out and out.endswith("\nb\n")
