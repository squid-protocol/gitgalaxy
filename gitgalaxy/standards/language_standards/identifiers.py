# ==============================================================================
# GitGalaxy -- identifier character classes (#3814, epic #3811)
# ==============================================================================
"""
What a name may be made of, per Unicode UAX #31, as regex character-class CONTENTS (use them
inside `[...]`, optionally with a language's extras such as `$`):

    ID_START     letters (Lu Ll Lt Lm Lo), letter numbers (Nl) and `_`
    ID_CONTINUE  ID_START plus combining marks (Mn Mc), digits (Nd), connectors (Pc)
                 and the joiners ZWNJ / ZWJ (U+200C / U+200D)

`[A-Za-z_]\\w*` misses every non-Latin name, and even `\\w` is not enough: Python's `\\w` has no
combining marks, so a Devanagari or Tamil name (`नाम`, `பெயர்`, whose vowel signs and viramas
are Mn/Mc) was cut at its first vowel sign, and a decomposed `é` (e + U+0301) at the accent.

Built once from `unicodedata` (no dependency, zero-dep mode included). Only planes 0-3 and 14
hold letters, marks, digits or connectors -- 4-13 are unassigned and 15-16 private use -- so
only they are scanned.
"""

from __future__ import annotations

import bisect
import unicodedata

_START_CATEGORIES = frozenset({"Lu", "Ll", "Lt", "Lm", "Lo", "Nl"})
_CONTINUE_CATEGORIES = _START_CATEGORIES | {"Mn", "Mc", "Nd", "Pc"}
_PLANES = (range(0x0, 0x40000), range(0xE0000, 0xF0000))
_CLASS_SPECIALS = frozenset("\\]^-[")


def _esc(cp: int) -> str:
    c = chr(cp)
    return "\\" + c if c in _CLASS_SPECIALS else c


def _runs(codepoints: list[int]) -> list[list[int]]:
    """Sorted code points as [first, last] runs of consecutive code points."""
    runs: list[list[int]] = []
    for cp in codepoints:
        if runs and runs[-1][1] == cp - 1:
            runs[-1][1] = cp
        else:
            runs.append([cp, cp])
    return runs


def _class_contents(runs: list[list[int]]) -> str:
    """[first, last] runs as character-class contents."""
    return "".join(_esc(a) if a == b else _esc(a) + _esc(b) if b == a + 1 else f"{_esc(a)}-{_esc(b)}" for a, b in runs)


# #3814: above the BMP, `re` keeps each range of a class as its own test, tried one after another on
# every character the class rejects -- and every blank or punctuation character is a rejection. ID_START's
# ~280 astral ranges made a miss ~40x slower (javascript func_start on a blanked 4000-line template:
# 25 ms -> 150 ms, and the ReDoS gate's 1 s budget failed on CI). So a gap between two astral members
# is filled unless it holds a format, space, control or private-use character (or a letter of the case
# a class excludes) or touches U+1F000-U+1FFFF (emoji and pictographs): ~280 ranges become 5-9. What
# that admits is historic scripts' own punctuation and symbols and musical / math symbols, never text
# a name could run into by accident. The BMP stays exact.
_NEVER_FILLED = frozenset({"Cf", "Zs", "Zl", "Zp", "Cc", "Co", "Cs"})
_EMOJI_BLOCKS = range(0x1F000, 0x20000)


def _fill_astral_gaps(runs: list[list[int]], blockers: list[int]) -> list[list[int]]:
    """`runs` with each astral gap merged away that contains no `blockers` code point (sorted)."""
    out: list[list[int]] = []
    for a, b in runs:
        prev = out[-1][1] if out else -1
        if (
            prev > 0xFFFF
            and not (prev < _EMOJI_BLOCKS.stop and a >= _EMOJI_BLOCKS.start)
            and bisect.bisect_right(blockers, prev) == bisect.bisect_left(blockers, a)
        ):
            out[-1][1] = b
        else:
            out.append([a, b])
    return out


def _build() -> tuple[str, str, str, str, str]:
    start, cont, virama, capital, small = [], [], [], [], []
    never, lower, upper = [], [], []  # astral gap blockers, in code point order
    category, combining = unicodedata.category, unicodedata.combining
    for plane in _PLANES:
        for cp in plane:
            cat = category(chr(cp))
            if cat in _CONTINUE_CATEGORIES or cp in (0x200C, 0x200D):
                cont.append(cp)
                if cat in _START_CATEGORIES or cp == 0x5F:  # `_` is Pc: a connector that may also lead
                    start.append(cp)
                if cat in ("Lu", "Lt", "Lo"):
                    capital.append(cp)
                if cat in ("Ll", "Lm", "Lo") or cp == 0x5F:
                    small.append(cp)
                if combining(chr(cp)) == 9:
                    virama.append(cp)
            if cp > 0xFFFF:
                if cat in _NEVER_FILLED:
                    never.append(cp)
                elif cat == "Ll":
                    lower.append(cp)
                elif cat in ("Lu", "Lt"):
                    upper.append(cp)
    c, fill = _class_contents, _fill_astral_gaps
    # CAPITAL / SMALL tell a letter's case, and astral cased scripts (Deseret, Adlam...) interleave the two.
    return (
        c(fill(_runs(start), never)),
        c(fill(_runs(cont), never)),
        c(_runs(virama)),
        c(fill(_runs(capital), sorted(never + lower))),
        c(fill(_runs(small), sorted(never + upper))),
    )


# CAPITAL: what `[A-Z]` meant for a name that must start with a capital (a Java constructor):
# upper- and title-case letters, and letters of scripts with no case at all (Devanagari, Han, ...).
# VIRAMA: the marks (canonical combining class 9: Devanagari ्, Tamil ், ...) after which UAX #31
# allows a ZWNJ / ZWJ inside a name (rules A1/A2) -- the one place those joiners are spelling,
# not hidden text.
# SMALL: what `[a-z_]` meant for a name that must NOT start with a capital (a Haskell variable, whose
# first letter tells it from a constructor): lower-case letters, `_`, and letters of scripts with no
# case (GHC reads an uncased letter as small).
ID_START, ID_CONTINUE, VIRAMA, CAPITAL, SMALL = _build()
NAME = f"[{ID_START}][{ID_CONTINUE}]*"

# #3814 / #3810: MAINFRAME national characters. EBCDIC's national bytes 0x5B / 0x7B / 0x7C -- `$ # @`
# on US pages -- display as other characters on national pages (IBM CDRA), so names exported from
# those systems carry them: cp277 Danish / Norwegian `Å Æ Ø`, cp278 Finnish / Swedish `Å Ä Ö`, cp273
# German / cp280 Italian `§`, cp284 Spanish `Ñ`, cp285 UK / cp297 French / cp280 `£`, cp297 `à`; Ü for
# German-keyed names. Mainframe names are upper case; the lower-case forms cover lower-cased exports.
# Every mainframe reader class that accepts letters also accepts these (tests/core_engine/
# test_national_names.py checks that no such class is missing them).
NATIONAL = "ÆØÅÄÖÜÑ§£àæøåäöüñ"
