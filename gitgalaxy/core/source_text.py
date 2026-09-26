# ==============================================================================
# GitGalaxy -- source_text: every source read decodes without losing a byte (#3813)
# ==============================================================================
"""
One decoder for every source read. Reading as UTF-8 with `errors="ignore"` silently dropped
what did not decode: a cp1252 / Latin-1 / Shift-JIS file lost its national characters (names
came out truncated), and a UTF-16 file decoded full of NULs, so the binary gate dropped it whole.

`read_source` decodes the bytes once, in order of certainty:

1. a byte-order mark (UTF-8, UTF-16 LE/BE, UTF-32 LE/BE) -- consumed, never left as U+FEFF;
2. BOM-less UTF-16, only when the bytes are unmistakably Latin-script UTF-16 (one byte lane
   mostly NUL, the other lane clean, the result reads as text) -- a binary of 16-bit
   integers must stay binary, NULs and all, for the binary gate;
3. strict UTF-8;
4. strict cp1252 -- a guess: the commonest legacy code page;
5. Latin-1 -- a guess that cannot fail (every byte maps).

No decode ever drops or replaces a byte; `read_source` then applies universal newlines (CRLF and CR
become LF), as the text-mode `open()` it replaces did. `how` records which path was taken, so a guess
(`cp1252-fallback`, `latin-1-fallback`) can be surfaced rather than trusted silently.
"""

from __future__ import annotations

import codecs
from dataclasses import dataclass
from pathlib import Path
from typing import Union

_BOMS = (  # longest first: the UTF-32 LE mark begins with the UTF-16 LE one
    (codecs.BOM_UTF32_LE, "utf-32-le"),
    (codecs.BOM_UTF32_BE, "utf-32-be"),
    (codecs.BOM_UTF8, "utf-8"),
    (codecs.BOM_UTF16_LE, "utf-16-le"),
    (codecs.BOM_UTF16_BE, "utf-16-be"),
)
_SNIFF = 4096  # bytes the UTF-16 heuristic looks at
_TEXT_CONTROLS = frozenset("\t\n\r\f\v")


@dataclass(frozen=True)
class SourceText:
    text: str
    encoding: str  # the codec that decoded it
    how: str  # "bom" | "utf-16-heuristic" | "utf-8" | "cp1252-fallback" | "latin-1-fallback"


def _decode(data: bytes, codec: str, truncated: bool) -> str:
    """Strict decode; for a truncated prefix, an incomplete character the cut made at the end is
    dropped (at most 3 bytes) rather than failing the whole codec."""
    if truncated:
        return codecs.getincrementaldecoder(codec)().decode(data, final=False)
    return data.decode(codec)


def _looks_like_text(text: str) -> bool:
    """No C0 control characters beyond whitespace, in a sample: what a decoded binary is full of."""
    sample = text[:2048]
    bad = sum(1 for c in sample if c < " " and c not in _TEXT_CONTROLS)
    return bad * 100 <= len(sample)  # at most 1%


def _utf16_without_bom(data: bytes) -> str | None:
    """The codec when `data` is BOM-less Latin-script UTF-16 (NUL high bytes), else None."""
    chunk = data[:_SNIFF]
    pairs = len(chunk) // 2
    if pairs < 8 or b"\x00" not in chunk:
        return None
    even, odd = chunk[0 : pairs * 2 : 2].count(0), chunk[1 : pairs * 2 : 2].count(0)
    for codec, nul_lane, other_lane in (("utf-16-le", odd, even), ("utf-16-be", even, odd)):
        if nul_lane * 10 >= pairs * 3 and other_lane * 20 <= pairs:  # >=30% NUL in one lane, <=5% in the other
            return codec
    return None


def decode_source(data: bytes, *, truncated: bool = False) -> SourceText:
    """Decode source bytes without losing any. `truncated`: the bytes are a prefix of the file, so a
    multi-byte character cut at the end must not make valid UTF-8 look invalid."""
    for bom, codec in _BOMS:
        if data.startswith(bom):
            try:
                return SourceText(_decode(data[len(bom) :], codec, truncated), codec, "bom")
            except UnicodeDecodeError:
                break  # a false mark (e.g. Latin-1 text starting "ÿþ"): decode the bytes as they are
    codec = _utf16_without_bom(data)
    if codec is not None:
        try:
            text = _decode(data, codec, truncated)
        except UnicodeDecodeError:
            text = None
        if text is not None and _looks_like_text(text):
            return SourceText(text, codec, "utf-16-heuristic")
    try:
        return SourceText(_decode(data, "utf-8", truncated), "utf-8", "utf-8")
    except UnicodeDecodeError:
        pass
    try:
        return SourceText(data.decode("cp1252"), "cp1252", "cp1252-fallback")
    except UnicodeDecodeError:  # cp1252 leaves 0x81 0x8D 0x8F 0x90 0x9D unmapped
        return SourceText(data.decode("latin-1"), "latin-1", "latin-1-fallback")


def read_source(path: Union[str, Path], limit: int | None = None) -> SourceText:
    """A source file's text, decoded without losing a byte. `limit`: read at most that many bytes (a
    guard against multi-GB logs) -- the file is then decoded as the prefix it is."""
    with open(path, "rb") as f:
        data = f.read() if limit is None else f.read(limit)
    src = decode_source(data, truncated=limit is not None and len(data) == limit)
    if "\r" not in src.text:
        return src
    # universal newlines, as text-mode open() gave every caller: CRLF and lone CR become LF, so line
    # counts, `$` anchors and fixed-format columns see one line ending whatever the file used
    return SourceText(src.text.replace("\r\n", "\n").replace("\r", "\n"), src.encoding, src.how)
