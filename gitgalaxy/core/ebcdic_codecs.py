# ==============================================================================
# GitGalaxy -- ebcdic_codecs: the national EBCDIC code pages Python ships without (#3816)
# ==============================================================================
"""
Python ships cp037 (US / Canada), cp273 (Germany / Austria), cp500 (international) and cp1140, but
none of the other Latin EBCDIC pages a Western European estate is written in. Declaring one
(`--source-encoding cp277`, a conversion's `data.code_page`) raised LookupError. This module
registers them with `codecs`, so every decode -- source reads, the zoned-sign table, the
equivalence harness -- knows them by the usual names (cp277, ibm277, ibm-277):

    cp277  Denmark / Norway      cp278  Finland / Sweden     cp280  Italy
    cp284  Spain / Latin America cp285  United Kingdom       cp297  France
    cp1047 z/OS Open Systems Latin-1 (USS)

Each page is cp037 with its national positions moved: the same 256 characters, permuted (IBM
CDRA; `@ # $` show as Æ Ø Å on cp277, which is why mainframe names carry them). The overrides
below were generated once from the JDK 17 charsets (`new String(bytes, Charset.forName("IBM277"))`
for bytes 0x00-0xFF, diffed against IBM037) and checked: every page is a permutation of cp037,
and its zoned-decimal zero signs are the ones #3826 had tabulated by hand. The JDK maps 0x15 (NL)
to LF for USS convenience; these tables keep CDRA's NEL (U+0085), as Python's own cp037 does.
"""

from __future__ import annotations

import codecs
import encodings.cp037
from typing import Any

# {code page: {byte: code point}} -- where each page differs from cp037
_OVERRIDES: dict[str, dict[int, int]] = {
    "cp277": {0x47: 0x007D, 0x4A: 0x0023, 0x4F: 0x0021, 0x5A: 0x00A4, 0x5B: 0x00C5, 0x5F: 0x005E, 0x67: 0x0024, 0x6A: 0x00F8, 0x70: 0x00A6, 0x7B: 0x00C6, 0x7C: 0x00D8, 0x80: 0x0040, 0x9C: 0x007B, 0x9E: 0x005B, 0x9F: 0x005D, 0xA1: 0x00FC, 0xB0: 0x00A2, 0xBA: 0x00AC, 0xBB: 0x007C, 0xC0: 0x00E6, 0xD0: 0x00E5, 0xDC: 0x007E},
    "cp278": {0x43: 0x007B, 0x47: 0x007D, 0x4A: 0x00A7, 0x4F: 0x0021, 0x51: 0x0060, 0x5A: 0x00A4, 0x5B: 0x00C5, 0x5F: 0x005E, 0x63: 0x0023, 0x67: 0x0024, 0x6A: 0x00F6, 0x71: 0x005C, 0x79: 0x00E9, 0x7B: 0x00C4, 0x7C: 0x00D6, 0x9F: 0x005D, 0xA1: 0x00FC, 0xB0: 0x00A2, 0xB5: 0x005B, 0xBA: 0x00AC, 0xBB: 0x007C, 0xC0: 0x00E4, 0xCC: 0x00A6, 0xD0: 0x00E5, 0xDC: 0x007E, 0xE0: 0x00C9, 0xEC: 0x0040},
    "cp280": {0x44: 0x007B, 0x48: 0x005C, 0x4A: 0x00B0, 0x4F: 0x0021, 0x51: 0x005D, 0x54: 0x007D, 0x58: 0x007E, 0x5A: 0x00E9, 0x5F: 0x005E, 0x6A: 0x00F2, 0x79: 0x00F9, 0x7B: 0x00A3, 0x7C: 0x00A7, 0x90: 0x005B, 0xA1: 0x00EC, 0xB0: 0x00A2, 0xB1: 0x0023, 0xB5: 0x0040, 0xBA: 0x00AC, 0xBB: 0x007C, 0xC0: 0x00E0, 0xCD: 0x00A6, 0xD0: 0x00E8, 0xDD: 0x0060, 0xE0: 0x00E7},
    "cp284": {0x49: 0x00A6, 0x4A: 0x005B, 0x5A: 0x005D, 0x69: 0x0023, 0x6A: 0x00F1, 0x7B: 0x00D1, 0xA1: 0x00A8, 0xB0: 0x00A2, 0xBA: 0x005E, 0xBB: 0x0021, 0xBD: 0x007E},
    "cp285": {0x4A: 0x0024, 0x5B: 0x00A3, 0xA1: 0x00AF, 0xB0: 0x00A2, 0xB1: 0x005B, 0xBA: 0x005E, 0xBC: 0x007E},
    "cp297": {0x44: 0x0040, 0x48: 0x005C, 0x4A: 0x00B0, 0x4F: 0x0021, 0x51: 0x007B, 0x54: 0x007D, 0x5A: 0x00A7, 0x5F: 0x005E, 0x6A: 0x00F9, 0x79: 0x00B5, 0x7B: 0x00A3, 0x7C: 0x00E0, 0x90: 0x005B, 0xA0: 0x0060, 0xA1: 0x00A8, 0xB0: 0x00A2, 0xB1: 0x0023, 0xB5: 0x005D, 0xBA: 0x00AC, 0xBB: 0x007C, 0xBD: 0x007E, 0xC0: 0x00E9, 0xD0: 0x00E8, 0xDD: 0x00A6, 0xE0: 0x00E7},
    "cp1047": {0x5F: 0x005E, 0xAD: 0x005B, 0xB0: 0x00AC, 0xBA: 0x00DD, 0xBB: 0x00A8, 0xBD: 0x005D},
}  # fmt: skip

_ALIASES = {alias: cp for cp in _OVERRIDES for alias in (cp, "ibm" + cp[2:], "ibm_" + cp[2:])}


def _codec_info(name: str) -> codecs.CodecInfo | None:
    cp = _ALIASES.get(name.lower().replace("-", "_"))
    if cp is None:
        return None
    table = list(encodings.cp037.decoding_table)
    for byte, code_point in _OVERRIDES[cp].items():
        table[byte] = chr(code_point)
    # a str table is what the stdlib's own charmap codecs pass (encodings/cp037.py); typeshed only
    # knows the dict form, hence Any
    decoding: Any = "".join(table)
    encoding = codecs.charmap_build(decoding)

    def encode(text: str, errors: str = "strict") -> tuple[bytes, int]:
        return codecs.charmap_encode(text, errors, encoding)

    def decode(data: Any, errors: str = "strict") -> tuple[str, int]:
        return codecs.charmap_decode(data, errors, decoding)

    class IncrementalDecoder(codecs.IncrementalDecoder):
        def decode(self, input: Any, final: bool = False) -> str:  # noqa: A002, ARG002 -- the stdlib signature
            return codecs.charmap_decode(input, self.errors, decoding)[0]

    class IncrementalEncoder(codecs.IncrementalEncoder):
        def encode(self, input: str, final: bool = False) -> bytes:  # noqa: A002, ARG002 -- the stdlib signature
            return codecs.charmap_encode(input, self.errors, encoding)[0]

    return codecs.CodecInfo(encode, decode, name=cp, incrementalencoder=IncrementalEncoder,
                            incrementaldecoder=IncrementalDecoder)  # fmt: skip


# EBCDIC pages, Python's and these: a file decoded with one is a record-oriented mainframe file
EBCDIC_CODE_PAGES = frozenset({"cp037", "cp273", "cp500", "cp1140", "cp875", "cp1026", *_OVERRIDES})


def register() -> None:
    """Make the pages known to `codecs` -- idempotent: once cp277 resolves, they are registered
    (importing gitgalaxy.core.source_text calls it)."""
    try:
        codecs.lookup("cp277")
    except LookupError:
        codecs.register(_codec_info)
