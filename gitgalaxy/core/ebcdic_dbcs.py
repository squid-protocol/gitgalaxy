# ==============================================================================
# GitGalaxy -- ebcdic_dbcs: IBM's mixed single/double-byte host code pages (#3816 part 3a)
# ==============================================================================
"""
The CJK host code pages mix single- and double-byte text in one stream: bytes are read one at a time
until Shift-Out (0x0E), then in pairs (lead and trail 0x40-0xFE; 0x4040 is the ideographic space)
until Shift-In (0x0F). Python ships none of them; the tables in `ebcdic_dbcs/` were generated from
the JDK's charsets by tests/tools/gen_ebcdic_dbcs.py, which also documents the one deliberate
difference (0x15 is CDRA's NEL, as in part 1):

    cp930  Japanese Katakana-Kanji     cp939  Japanese Latin-Kanji
    cp935  Simplified Chinese          cp937  Traditional Chinese        cp933  Korean

The shift bytes are state, not text: they decode to nothing and are written back around each run
of double-byte characters. A stream that ends shifted out is legal (the next record starts in
single-byte mode); a pair cut by the end of the input is not -- the incremental decoder keeps it.
"""

from __future__ import annotations

import codecs
import json
from functools import cache
from importlib import resources
from typing import Any, cast

SO, SI = 0x0E, 0x0F
DBCS_CODE_PAGES = frozenset({"cp930", "cp939", "cp935", "cp937", "cp933"})
_ALIASES = {alias: cp for cp in DBCS_CODE_PAGES for alias in (cp, "ibm" + cp[2:], "ibm_" + cp[2:], "x_ibm" + cp[2:])}
_UNMAPPED = "�"


@cache
def _tables(cp: str) -> tuple[str, dict[int, str], dict[str, int], dict[str, int]]:
    """(single-byte table, {pair: char}, {char: byte}, {char: pair}) for a page, loaded once."""
    doc = json.loads(resources.files("gitgalaxy.core").joinpath(f"ebcdic_dbcs/{cp}.json").read_bytes())  # UTF-8 JSON
    sbcs: str = doc["sbcs"]
    dbcs: dict[int, str] = {}
    for lead_hex, row in doc["dbcs"].items():
        lead = int(lead_hex, 16) << 8
        for i, ch in enumerate(row):
            if ch != _UNMAPPED:
                dbcs[lead | (0x40 + i)] = ch
    enc_sbcs = {ch: b for b, ch in enumerate(sbcs) if ch != _UNMAPPED and b not in (SO, SI)}
    enc_dbcs: dict[str, int] = {}
    for pair in sorted(dbcs):  # the lowest pair per character, then the JDK's own choice where it differs
        enc_dbcs.setdefault(dbcs[pair], pair)
    enc_dbcs.update({ch: int(pair, 16) for ch, pair in doc["encode_overrides"].items()})
    return sbcs, dbcs, enc_sbcs, enc_dbcs


def _decode(cp: str, data: bytes, errors: str, shifted: bool, final: bool) -> tuple[str, int, bool]:
    """Decode `data` starting in `shifted` state: (text, bytes consumed, state at the end). A lead
    byte with no trail yet is left unconsumed unless `final`."""
    sbcs, dbcs, _, _ = _tables(cp)
    out: list[str] = []
    i, n = 0, len(data)
    while i < n:
        b = data[i]
        if b == SO:
            shifted, i = True, i + 1
            continue
        if b == SI:
            shifted, i = False, i + 1
            continue
        if shifted:
            if i + 1 >= n:
                if not final:
                    break
                ch, width = _error(errors, data, i, i + 1, cp, "truncated double-byte character")
            else:
                ch = dbcs.get((b << 8) | data[i + 1], _UNMAPPED)
                width = 2
                if ch == _UNMAPPED:
                    ch, width = _error(errors, data, i, i + 2, cp, "unmapped double-byte character")
        else:
            ch, width = sbcs[b], 1
            if ch == _UNMAPPED:
                ch, width = _error(errors, data, i, i + 1, cp, "unmapped single-byte character")
        out.append(ch)
        i += width
    return "".join(out), i, shifted


def decode_record(cp: str, data: bytes, final: bool = True) -> str:
    """One record, strictly, starting in single-byte mode (a host record never carries shift state
    into the next). Not `final`: a lead byte the cut left without its trail is dropped."""
    return _decode(cp, data, "strict", False, final)[0]


def _error(errors: str, data: bytes, start: int, end: int, cp: str, reason: str) -> tuple[str, int]:
    exc = UnicodeDecodeError(cp, data, start, end, reason)
    replacement, resume = codecs.lookup_error(errors)(exc)
    return cast(str, replacement), resume - start  # a decode error handler returns text


def _encode(cp: str, text: str, errors: str, shifted: bool, final: bool) -> tuple[bytes, bool]:
    _, _, enc_sbcs, enc_dbcs = _tables(cp)
    out = bytearray()
    i = 0
    while i < len(text):
        ch = text[i]
        if ch in enc_sbcs:
            if shifted:
                out.append(SI)
                shifted = False
            out.append(enc_sbcs[ch])
        elif ch in enc_dbcs:
            if not shifted:
                out.append(SO)
                shifted = True
            out += enc_dbcs[ch].to_bytes(2, "big")
        else:  # the error handler's replacement ("?" for "replace") is written like any other text
            exc = UnicodeEncodeError(cp, text, i, i + 1, "character not in the code page")
            replacement, i = codecs.lookup_error(errors)(exc)
            if isinstance(replacement, bytes):
                out += replacement
            else:
                data, shifted = _encode(cp, replacement, "strict", shifted, False)
                out += data
            continue
        i += 1
    if final and shifted:
        out.append(SI)
        shifted = False
    return bytes(out), shifted


def codec_info(name: str) -> codecs.CodecInfo | None:
    found = _ALIASES.get(name.lower().replace("-", "_"))
    if found is None:
        return None
    cp: str = found

    def encode(text: str, errors: str = "strict") -> tuple[bytes, int]:
        return _encode(cp, text, errors, False, True)[0], len(text)

    def decode(data: Any, errors: str = "strict") -> tuple[str, int]:
        text, used, _ = _decode(cp, bytes(data), errors, False, True)
        return text, used

    class IncrementalDecoder(codecs.BufferedIncrementalDecoder):
        def __init__(self, errors: str = "strict") -> None:
            super().__init__(errors)
            self.shifted = False

        def _buffer_decode(self, input: Any, errors: str, final: bool) -> tuple[str, int]:  # noqa: A002
            text, used, self.shifted = _decode(cp, bytes(input), errors, self.shifted, final)
            return text, used

        def reset(self) -> None:
            super().reset()
            self.shifted = False

    class IncrementalEncoder(codecs.IncrementalEncoder):
        def __init__(self, errors: str = "strict") -> None:
            super().__init__(errors)
            self.shifted = False

        def encode(self, input: str, final: bool = False) -> bytes:  # noqa: A002 -- the stdlib signature
            data, self.shifted = _encode(cp, input, self.errors, self.shifted, final)
            return data

        def reset(self) -> None:
            self.shifted = False

    return codecs.CodecInfo(encode, decode, name=cp, incrementalencoder=IncrementalEncoder,
                            incrementaldecoder=IncrementalDecoder)  # fmt: skip
