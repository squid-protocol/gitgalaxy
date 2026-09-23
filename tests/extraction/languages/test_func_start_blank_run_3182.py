"""#3182: javascript/typescript func_start's assignment-branch start anchor on blank runs.

The anchor used to be `(?:^|(?<=[^<>(,\\s]))[ \\t\\n]*` under re.M. `_build_brace_safe_stream`
blanks a multi-line template literal to same-length whitespace, and the bare `^` fired on
every line of that blank run -- each attempt scanning to the run's end before failing, so a
16k-line pnpm-lock fixture (nx) cost 60s+ in Cartography_Mode_B_Braces. The rewrite takes `^`
only on a non-blank line, on a blank run's first line start, or at the file start.
"""

import itertools
import re
import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune  # noqa: E402 # type: ignore

_OLD_ANCHOR = r"(?:^|(?<=[^<>(,\s]))[ \t\n]*"
_NEW_ANCHOR = r"(?:(?<=[^<>(,\s])|^(?:(?=[ \t]*[^ \t\n])|(?![ \t]*[^ \t\n])(?:(?<=[^ \t\n]\n)|\A)))[ \t\n]*"

_LANGS = ["javascript", "typescript"]


def _old_and_new(lang):
    new = LANGUAGE_DEFINITIONS[lang]["rules"]["func_start"]
    assert new.pattern.count(_NEW_ANCHOR) == 1
    old = re.compile(new.pattern.replace(_NEW_ANCHOR, _OLD_ANCHOR), new.flags)
    return old, new


@pytest.mark.parametrize("lang", _LANGS)
def test_func_start_blanked_template_run_is_linear_3182(lang):
    """A blanked 4000-line template literal took the old anchor ~4s; now milliseconds."""
    _, func_start = _old_and_new(lang)
    blanked_template = "export default " + "\n".join(" " * 40 for _ in range(4000)) + "\n"
    assert_redos_immune(func_start, blanked_template, timeout_sec=1.0)
    assert not func_start.search(blanked_template)


@pytest.mark.parametrize("lang", _LANGS)
def test_func_start_anchor_equivalence_3182(lang):
    """
    Every (prefix, whitespace run, suffix) combination must give the old match list, except
    the one documented shift: an old match starting on a BLANK line whose previous line ends
    in whitespace (a blanked string after `<>(,`) now starts on a later line -- same end,
    same groups.
    """
    old, new = _old_and_new(lang)
    prefixes = ["", "x", "x;", "x,", "x(", "x<", "x>", "x =>", "x, 'ab'", "(  "]
    ws_tokens = ["", " ", "\t", "\n", "  \n", "\n\n", " \n \n  "]
    suffixes = ["a = () => 1", "a = b => c", "a: () => 1", "a = function () {}", "a", "=> 1", ""]
    shifted = 0
    for prefix, w1, w2, suffix in itertools.product(prefixes, ws_tokens, ws_tokens, suffixes):
        text = prefix + w1 + w2 + suffix
        a = [(m.span(), m.groups()) for m in old.finditer(text)]
        b = [(m.span(), m.groups()) for m in new.finditer(text)]
        if a == b:
            continue
        assert len(a) == len(b), repr(text)
        for (sa, ga), (sb, gb) in zip(a, b):
            assert sa[1] == sb[1] and ga == gb, repr(text)
            if sa[0] == sb[0]:
                continue
            gap = text[sa[0] : sb[0]]
            prev_line = text[: sa[0]].rsplit("\n", 2)[-2] if "\n" in text[: sa[0]] else ""
            assert sb[0] > sa[0] and not gap.strip() and "\n" in gap, repr(text)
            assert text[sa[0]:].split("\n", 1)[0].strip() == "", repr(text)
            assert prev_line.endswith((" ", "\t")), repr(text)
            shifted += 1
    assert shifted, "the documented shift case should be exercised"
