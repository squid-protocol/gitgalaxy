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

import unicodedata

_START_CATEGORIES = frozenset({"Lu", "Ll", "Lt", "Lm", "Lo", "Nl"})
_CONTINUE_CATEGORIES = _START_CATEGORIES | {"Mn", "Mc", "Nd", "Pc"}
_PLANES = (range(0x0, 0x40000), range(0xE0000, 0xF0000))
_CLASS_SPECIALS = frozenset("\\]^-[")


def _esc(cp: int) -> str:
    c = chr(cp)
    return "\\" + c if c in _CLASS_SPECIALS else c


def _class_contents(codepoints: list[int]) -> str:
    """Sorted code points as character-class contents, runs collapsed to ranges."""
    out: list[str] = []
    i = 0
    while i < len(codepoints):
        j = i
        while j + 1 < len(codepoints) and codepoints[j + 1] == codepoints[j] + 1:
            j += 1
        a, b = codepoints[i], codepoints[j]
        out.append(_esc(a) if a == b else _esc(a) + _esc(b) if b == a + 1 else f"{_esc(a)}-{_esc(b)}")
        i = j + 1
    return "".join(out)


def _build() -> tuple[str, str, str, str]:
    start, cont, virama, capital = [], [], [], []
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
                if combining(chr(cp)) == 9:
                    virama.append(cp)
    return _class_contents(start), _class_contents(cont), _class_contents(virama), _class_contents(capital)


# CAPITAL: what `[A-Z]` meant for a name that must start with a capital (a Java constructor):
# upper- and title-case letters, and letters of scripts with no case at all (Devanagari, Han, ...).
# VIRAMA: the marks (canonical combining class 9: Devanagari ्, Tamil ், ...) after which UAX #31
# allows a ZWNJ / ZWJ inside a name (rules A1/A2) -- the one place those joiners are spelling,
# not hidden text.
ID_START, ID_CONTINUE, VIRAMA, CAPITAL = _build()
NAME = f"[{ID_START}][{ID_CONTINUE}]*"

# #3814 / #3810: MAINFRAME national characters. EBCDIC's national bytes 0x5B / 0x7B / 0x7C -- `$ # @`
# on US pages -- display as other characters on national pages (IBM CDRA), so names exported from
# those systems carry them: cp277 Danish / Norwegian `Å Æ Ø`, cp278 Finnish / Swedish `Å Ä Ö`, cp273
# German / cp280 Italian `§`, cp284 Spanish `Ñ`, cp285 UK / cp297 French / cp280 `£`, cp297 `à`; Ü for
# German-keyed names. Mainframe names are upper case; the lower-case forms cover lower-cased exports.
# Every mainframe reader class that accepts letters also accepts these (tests/core_engine/
# test_national_names.py checks that no such class is missing them).
NATIONAL = "ÆØÅÄÖÜÑ§£àæøåäöüñ"
