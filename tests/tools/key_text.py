"""
#3869: the ground-truth side's own lossless decoder -- deliberately NOT gitgalaxy.core.source_text.

The answer keys (`cobol_answer_key.py`) and the blind-review packets (`cross_verify_sections.py`) are
evidence only while they share no code with the engine they grade
(`test_draft_readers_never_import_the_parsers_they_grade`). That holds for decoding too: if the key
read files through the engine's decoder, a decoding bug would corrupt both sides the same way and
read as agreement -- the false pass #3869 exists to remove. So this is a second, independently
written decoder. Where it and the engine disagree on a file, the ledger shows a mismatch instead of
hiding one.

It never drops or replaces a byte. In order:

1. a byte-order mark (UTF-32, UTF-8, UTF-16), consumed;
2. BOM-less UTF-16 -- one byte lane of the first 4 KB mostly NUL, the other lane almost never;
3. strict UTF-8;
4. strict cp1252, then Latin-1 (which maps every byte).

Line endings are then made universal (CRLF and lone CR become LF), as a text-mode read gave the key.
"""

from __future__ import annotations

from pathlib import Path

_MARKS = (  # longest first: the UTF-32 LE mark starts with the UTF-16 LE one
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xef\xbb\xbf", "utf-8"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
)


def _bomless_utf16(data: bytes) -> str | None:
    head = data[:4096]
    half = len(head) // 2
    if half < 8:
        return None
    even_nul = sum(1 for b in head[0 : half * 2 : 2] if b == 0)
    odd_nul = sum(1 for b in head[1 : half * 2 : 2] if b == 0)
    if odd_nul * 10 >= half * 3 and even_nul * 20 <= half:
        return "utf-16-le"  # ASCII-range text: the high byte of each unit, second, is NUL
    if even_nul * 10 >= half * 3 and odd_nul * 20 <= half:
        return "utf-16-be"
    return None


def decode_key_bytes(data: bytes) -> str:
    """Bytes to text without losing one (see the module docstring for the order)."""
    for mark, codec in _MARKS:
        if data.startswith(mark):
            try:
                return data[len(mark) :].decode(codec)
            except UnicodeDecodeError:
                break  # a false mark: decode the bytes as they are
    codec16 = _bomless_utf16(data)
    if codec16:
        try:
            text = data.decode(codec16)
        except UnicodeDecodeError:
            pass
        else:
            if "\x00" not in text:  # a real UTF-16 text decodes NUL-free; a binary does not
                return text
    text = _strict(data, "utf-8")
    if text is None:
        text = _strict(data, "cp1252")
    return data.decode("latin-1") if text is None else text


def _strict(data: bytes, codec: str) -> str | None:
    try:
        return data.decode(codec)
    except UnicodeDecodeError:
        return None


def read_key_text(path: str | Path) -> str:
    """A source file's text for the ground-truth readers: lossless, universal newlines."""
    text = decode_key_bytes(Path(path).read_bytes())
    return text.replace("\r\n", "\n").replace("\r", "\n") if "\r" in text else text
