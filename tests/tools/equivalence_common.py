"""
The equivalence harness's shared primitives (#3624, #3754, #3804): paths, the GnuCOBOL image,
the corpus-input helpers, COBOL storage decoding and copybook layouts. A leaf module -- it
imports none of the harness modules -- so equivalence.py, equivalence_cics.py and
equivalence_inputs.py all build on it without an import cycle; equivalence.py re-exports it.
"""

from __future__ import annotations

import functools
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from gitgalaxy.tools.cobol_to_java.java_target import zoned_sign_characters

REPO_ROOT = Path(__file__).resolve().parents[2]
CASES = REPO_ROOT / "tests" / "equivalence"
IMAGE = "gitgalaxy-gnucobol:3"
sys.path.insert(0, str(Path(__file__).resolve().parent))


def _fixed(src: Path, reclen: int) -> bytes:
    """A corpus data file (text lines) as fixed-length records: CR dropped, each line padded."""
    out = bytearray()
    for line in src.read_bytes().split(b"\n"):
        line = line.rstrip(b"\r")
        if line:
            out += line[:reclen].ljust(reclen, b" ")
    return bytes(out)


def _input_path(case: dict[str, Any], corpus: Path, rel: str) -> Path:
    """A dataset's input: `@case/...` is a file of the case directory, else the corpus's."""
    return CASES / case["name"] / rel[len("@case/") :] if rel.startswith("@case/") else corpus / rel


@functools.lru_cache(maxsize=None)
def _overpunch(code_page: str = "cp037") -> dict[str, tuple[int, int]]:
    """#3826: the zoned sign table of the data's code page, the one the generated CobolRecords uses."""
    pos, neg = zoned_sign_characters(code_page)
    return {**{c: (i, 1) for i, c in enumerate(pos)}, **{c: (i, -1) for i, c in enumerate(neg)}}


def _pic_numeric(pic: str) -> Optional[tuple[bool, int, int]]:
    """(signed, digits, scale) of a numeric PIC, or None."""
    import re

    p = re.sub(r"(.)\((\d+)\)", lambda m: m.group(1) * int(m.group(2)), pic.upper())
    if not p or re.search(r"[^S9V]", p):
        return None
    whole, _, frac = p.partition("V")
    return p.startswith("S"), whole.count("9") + frac.count("9"), frac.count("9")


def _ascii_digits(text: str) -> bool:
    """#3830: only 0-9 -- `int()` also takes spaces, `+`, `_` and non-ASCII digits (`"  12"`, `1_2`, `١٢`)."""
    return bool(text) and text.isascii() and text.isdigit()


def decode_field(
    raw: bytes, pic: Optional[str], usage: Optional[str], code_page: str = "cp037", sign_separate: bool = False
) -> Any:
    """A field's value: an exact Decimal for numeric DISPLAY / COMP-3 / COMP, else its text. Storage a
    COBOL NUMERIC test would reject (a space, a stray `+`, a bad nibble) is `<invalid ...>`, never a number
    (#3830): the oracle may not be more lenient than the program."""
    num = _pic_numeric(pic) if pic else None
    u = (usage or "DISPLAY").upper()
    if num is None:
        return raw.decode("latin-1")
    signed, _digits, scale = num
    invalid = f"<invalid {raw!r}>"
    if u in ("COMP-3", "PACKED-DECIMAL", "COMPUTATIONAL-3"):
        hexs = raw.hex()
        if not hexs or not _ascii_digits(hexs[:-1]) or hexs[-1] not in "abcdef":
            return invalid
        value, sign = int(hexs[:-1]), hexs[-1]
        return Decimal(-value if sign in "bd" else value).scaleb(-scale)
    if u in ("COMP", "COMP-4", "COMP-5", "BINARY", "COMPUTATIONAL", "COMPUTATIONAL-4", "COMPUTATIONAL-5"):
        return Decimal(int.from_bytes(raw, "big", signed=signed)).scaleb(-scale)
    text, sign = raw.decode("latin-1"), 1
    if sign_separate:  # SIGN IS LEADING / TRAILING SEPARATE: its own `+` / `-` byte at one end
        if text[:1] in ("+", "-"):
            sign, text = (-1 if text[0] == "-" else 1), text[1:]
        elif text[-1:] in ("+", "-"):
            sign, text = (-1 if text[-1] == "-" else 1), text[:-1]
        else:
            return invalid
    elif text:
        op = _overpunch(code_page)
        if text[-1] in op:
            d, sign = op[text[-1]]
            text = text[:-1] + str(d)
    if not _ascii_digits(text):
        return invalid
    return (Decimal(int(text)) * sign).scaleb(-scale)


def layout_fields(corpus: Path, copybook: str, record: Optional[str] = None) -> list[dict[str, Any]]:
    """The elementary fields of a copybook record: name, offset, bytes, pic, usage (the answer
    key's own reader and storage arithmetic, cobol_answer_key)."""
    import cobol_answer_key as ak

    items = [it for it in ak._data_items(ak.Source(corpus / copybook)) if it["level"] not in (66, 88)]
    kids: dict[Optional[int], list[dict[str, Any]]] = {}
    for it in items:
        kids.setdefault(it["parent"], []).append(it)

    def size(it: dict[str, Any]) -> int:
        if it.get("pic"):
            own = ak._pic_bytes(it["pic"], it.get("usage"), it.get("sign_separate", False))
        else:
            own = sum(size(c) for c in kids.get(it["ordinal"], []) if not c.get("redefines"))
        return own * (it.get("occurs_max") or 1)

    out: list[dict[str, Any]] = []

    def place(it: dict[str, Any], at: int) -> None:
        if it.get("pic"):
            out.append(
                {"name": it["name"], "offset": at, "bytes": size(it), "pic": it["pic"], "usage": it.get("usage"),
                 "sign_separate": bool(it.get("sign_separate"))}
            )  # fmt: skip
            return
        cur = at
        for c in kids.get(it["ordinal"], []):
            if c.get("redefines"):
                continue
            place(c, cur)
            cur += size(c)

    # A named record may itself REDEFINE another (#3754: a symbolic map's output area, CACTVWAO
    # REDEFINES CACTVWAI); with no name, the first record that does not is the layout.
    roots = [r for r in kids.get(None, []) if (r["name"] == record if record else not r.get("redefines"))]
    place(roots[0], 0)
    return out
