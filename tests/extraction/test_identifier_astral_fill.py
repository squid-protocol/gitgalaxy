"""#3814: the identifier classes fill astral gaps so a class miss stays cheap, without changing what matters.

`re` tests a class's astral ranges one by one on every character the class rejects; ~280 of them made
javascript func_start ~6x slower on a blanked template (the #3182 ReDoS gate failed on CI). The classes
now merge astral gaps. This pins what that may and may not change.
"""

import re
import time
import unicodedata

import pytest

from gitgalaxy.standards.language_standards import identifiers

_EXACT = {
    "ID_START": lambda cat, cp: cat in {"Lu", "Ll", "Lt", "Lm", "Lo", "Nl"} or cp == 0x5F,
    "ID_CONTINUE": lambda cat, cp: cat in {"Lu", "Ll", "Lt", "Lm", "Lo", "Nl", "Mn", "Mc", "Nd", "Pc"}
    or cp in (0x200C, 0x200D),
    "CAPITAL": lambda cat, cp: cat in {"Lu", "Lt", "Lo"},
    "SMALL": lambda cat, cp: cat in {"Ll", "Lm", "Lo"} or cp == 0x5F,
}
_NEVER = {"Cf", "Zs", "Zl", "Zp", "Cc", "Co", "Cs"}
_EXCLUDED_CASE = {"CAPITAL": {"Ll"}, "SMALL": {"Lu", "Lt"}}
_PLANES = [*range(0x0, 0x40000), *range(0xE0000, 0xF0000)]


@pytest.mark.parametrize("name", sorted(_EXACT))
def test_fill_keeps_every_member_and_admits_nothing_that_matters(name):
    cls = re.compile(f"[{getattr(identifiers, name)}]")
    exact, never = _EXACT[name], _NEVER | _EXCLUDED_CASE.get(name, set())
    for cp in _PLANES:
        ch = chr(cp)
        cat = unicodedata.category(ch)
        member, matched = exact(cat, cp), cls.match(ch) is not None
        if member:
            assert matched, f"{name} lost U+{cp:04X}"
        elif matched:
            # Only astral gap fill may add, never in the BMP or the emoji blocks, never an invisible,
            # a space, a control or a letter of the excluded case.
            assert cp > 0xFFFF and not 0x1F000 <= cp < 0x20000, f"{name} added U+{cp:04X}"
            assert cat not in never, f"{name} added U+{cp:04X} ({cat})"


@pytest.mark.parametrize("name", sorted(_EXACT))
def test_a_class_miss_is_several_times_cheaper_than_unfilled(name):
    """Measured on 400k blanks: unfilled 135-189x `[A-Za-z_]`, filled 5-25x. A ratio of two regexes, not wall clock."""
    exact = [cp for cp in _PLANES if _EXACT[name](unicodedata.category(chr(cp)), cp)]
    unfilled = identifiers._class_contents(identifiers._runs(exact))
    blanks = " " * 400_000

    def best(contents):
        rx, runs = re.compile(f"[{contents}]"), []
        for _ in range(5):
            t = time.perf_counter()
            rx.search(blanks)
            runs.append(time.perf_counter() - t)
        return min(runs)

    assert best(getattr(identifiers, name)) * 3 < best(unfilled)
