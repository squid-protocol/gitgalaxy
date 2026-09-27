"""
The equivalence harness's shared primitives (#3624, #3754, #3804): paths, the GnuCOBOL image,
the corpus-input helpers, COBOL storage decoding and copybook layouts. A leaf module -- it
imports none of the harness modules -- so equivalence.py, equivalence_cics.py and
equivalence_inputs.py all build on it without an import cycle; equivalence.py re-exports it.

#3815 -- declared encodings. A case (or `--source-encoding` / `--data-encoding`) may declare
`"source_encoding"` -- how the COBOL sources are read: default the engine's `read_source` ladder
(BOM, UTF-8, the declared page, cp1252, Latin-1), which reads a UTF-8 estate's national names
losslessly -- and `"data_encoding"` -- the code page of the record bytes, every text and zoned
field in them (cp277, cp273, utf-8 ...; default Latin-1, the harness's behaviour before, so an
undeclared run is byte-identical). Every bytes <-> text step of the harness goes through it.
"""

from __future__ import annotations

import codecs
import functools
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from gitgalaxy.core.compiler_options import SEMANTIC_OPTIONS, cards, compiler_options, effective, parse_options
from gitgalaxy.core.ebcdic_codecs import java_charset_name
from gitgalaxy.core.ebcdic_codecs import register as _register_ebcdic
from gitgalaxy.core.source_text import read_source
from gitgalaxy.tools.cobol_to_java.java_target import zoned_sign_characters

REPO_ROOT = Path(__file__).resolve().parents[2]
CASES = REPO_ROOT / "tests" / "equivalence"
IMAGE = "gitgalaxy-gnucobol:3"
sys.path.insert(0, str(Path(__file__).resolve().parent))
_register_ebcdic()  # #3816: cp277 / cp278 / ... resolve in every decode and encode below

# #3815: the record bytes' code page when a case declares none -- what the harness always assumed
DEFAULT_DATA_ENCODING = "latin-1"
_ASCII_PROBE = "AZaz09 {}+-.\n"


def _check_codec(name: str, what: str) -> str:
    try:
        codecs.lookup(name)
    except LookupError as e:
        raise ValueError(f"{what} {name!r}: not a known encoding") from e
    return name


def data_encoding(case: dict[str, Any]) -> str:
    """#3815: the code page of the case's record bytes (`data_encoding`, default Latin-1). A record is
    fixed-width bytes padded with the page's space, so the space must be one byte (not UTF-16 / UTF-32)."""
    enc = _check_codec(case.get("data_encoding") or DEFAULT_DATA_ENCODING, "data_encoding")
    if len(" ".encode(enc)) != 1:
        raise ValueError(f"data_encoding {enc!r}: a record's space must be one byte")
    return enc


def source_encoding(case: dict[str, Any]) -> Optional[str]:
    """#3815: the estate's declared source code page (`source_encoding`), or None: the read_source ladder."""
    enc = case.get("source_encoding")
    return _check_codec(enc, "source_encoding") if enc else None


def ascii_compatible(enc: str) -> bool:
    """#3815: does `enc` store ASCII as ASCII (Latin-1, cp1252, UTF-8 ...; not EBCDIC, not UTF-16)?"""
    try:
        return _ASCII_PROBE.encode(enc) == _ASCII_PROBE.encode("ascii")
    except UnicodeError:
        return False


def read_program(case: dict[str, Any], path: Path) -> tuple[str, str]:
    """#3815: (a COBOL source's text, the encoding to stage it for GnuCOBOL in). Read by the engine's ladder
    (declared page from `source_encoding`), so a UTF-8 source's names (BELØP, नाम) arrive whole, and staged in
    the encoding it was read in -- the same bytes back, as the Latin-1 read / write before gave. GnuCOBOL
    reads ASCII-family bytes, so a source read as EBCDIC or UTF-16 is staged as UTF-8."""
    src = read_source(path, declared=source_encoding(case))
    return src.text, src.encoding if ascii_compatible(src.encoding) else "utf-8"


def sign_page(enc: str, code_page: str = "cp037") -> str:
    """#3815: the zoned sign table for records in `enc`: in EBCDIC bytes the overpunch is the byte itself
    (0xC0-0xD9), so the page's own characters (cp277's +0 is `æ`); in ASCII-family bytes, `code_page`'s."""
    return code_page if ascii_compatible(enc) else enc


def require_ascii_runtime(case: dict[str, Any]) -> None:
    """#3815: GnuCOBOL's storage is ASCII-family: EBCDIC record bytes would reach it as garbage digits (0xF0 is
    no `0`), and transcoding a record blindly corrupts its COMP / COMP-3 fields. Such a case can be decoded
    and diffed, but not run here -- say so rather than run unfaithfully."""
    enc = data_encoding(case)
    if not ascii_compatible(enc):
        raise UnsupportedOption(f"data_encoding {enc}: GnuCOBOL runs ASCII-family storage, so the case cannot be run")


def text_bytes(text: str, nbytes: int, enc: str = DEFAULT_DATA_ENCODING) -> bytes:
    """#3815: `text` as an `nbytes` text field stores it in `enc`: cut at a whole character (a UTF-8 name
    never ends in half a letter), padded with the page's space (0x40 in EBCDIC). An unencodable character
    raises -- never dropped. Latin-1: exactly the `encode("latin-1")[:n].ljust(n, b" ")` of before."""
    data = text.encode(enc)
    if len(data) > nbytes:
        cut = text[:nbytes]  # every character is at least one byte
        while len(cut.encode(enc)) > nbytes:
            cut = cut[:-1]
        data = cut.encode(enc)
    return data + " ".encode(enc) * (nbytes - len(data))


def java_charset(enc: str = DEFAULT_DATA_ENCODING) -> str:
    """#3815: the Java expression for `enc`, the Charset the generated test's record codecs use.
    #3908: the JDK name comes from gitgalaxy (java_charset_name), the one mapping the generated
    EbcdicDecoderUtil uses too."""
    if codecs.lookup(enc).name == "iso8859-1":
        return "StandardCharsets.ISO_8859_1"  # the default: the generated test byte-identical to before
    return f'Charset.forName("{java_charset_name(enc)}")'


def _fixed(src: Path, reclen: int, enc: str = DEFAULT_DATA_ENCODING) -> bytes:
    """A corpus data file (text lines) as fixed-length records: CR dropped, each line padded.
    #3815: lines, CR and padding in the data's page; an EBCDIC file's lines may end in NEL (0x15),
    and one with no line ends at all is fixed-block already, cut into its records."""
    data, nl, cr, pad = src.read_bytes(), "\n".encode(enc), "\r".encode(enc), " ".encode(enc)
    if not ascii_compatible(enc):
        nel = "\x85".encode(enc)
        if nl not in data and nel not in data:
            lines = [data[i : i + reclen] for i in range(0, len(data), reclen)]
        else:
            lines = data.replace(nel, nl).split(nl)
    else:
        lines = data.split(nl)
    out = bytearray()
    for line in lines:
        line = line.rstrip(cr)
        if line:
            out += line[:reclen] + pad * (reclen - len(line[:reclen]))
    return bytes(out)


def _input_path(case: dict[str, Any], corpus: Path, rel: str) -> Path:
    """A dataset's input: `@case/...` is a file of the case directory, else the corpus's."""
    return CASES / case["name"] / rel[len("@case/") :] if rel.startswith("@case/") else corpus / rel


# #3828: the compiler options that change results, as GnuCOBOL 3.1 flags under `-std=ibm` ("" = its own
# behaviour already). GnuCOBOL has no INTDATE (INTEGER-OF-DATE is always ANSI), no ARITH(EXTEND) or NUMPROC
# switch and no TRUNC(OPT): a case needing one cannot be proven here, and says so rather than run unfaithfully.
COBC_OPTIONS = {
    ("INTDATE", "ANSI"): "", ("TRUNC", "STD"): "", ("TRUNC", "BIN"): "-fnotrunc", ("ARITH", "COMPAT"): "",
    ("NUMPROC", "NOPFD"): "",
}  # fmt: skip


class UnsupportedOption(Exception):
    """A compiler option the GnuCOBOL side cannot honour (#3828)."""


def compile_options(case: dict[str, Any], source: str) -> tuple[str, list[str]]:
    """#3828: (the program with its CBL / PROCESS cards blanked -- GnuCOBOL rejects CBL --, the cobc
    flags for its options). The case's `compiler_options` (e.g. ["INTDATE(LILIAN)"]) stand for the
    compile step's PARM, so the program's own cards override them, as on z/OS. Options that change
    no result (APOST, CICS, SQL, OPT ...) are dropped; a semantic one GnuCOBOL cannot honour raises."""
    rows = [{"option": o, "value": v} for text in case.get("compiler_options", []) for o, v, _ in parse_options(text)]
    rows += compiler_options(source)
    flags = []
    for option, value in effective(rows).items():
        if option not in SEMANTIC_OPTIONS:
            continue
        flag = COBC_OPTIONS.get((option, str(value or "").upper()))
        if flag is None:
            raise UnsupportedOption(f"{option}({value}): GnuCOBOL 3.1 has no equivalent, so the case cannot be proven")
        if flag:
            flags.append(flag)
    blank = {n for n, _ in cards(source)}
    lines = source.split("\n")
    return "\n".join("" if n in blank else ln for n, ln in enumerate(lines, 1)), flags


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


def _decode_text(raw: bytes, enc: str) -> Optional[str]:
    """#3815: strictly; None when the bytes are not text in `enc` (half a UTF-8 letter, an unmapped byte)."""
    try:
        return raw.decode(enc)
    except UnicodeDecodeError:
        return None


def decode_field(
    raw: bytes,
    pic: Optional[str],
    usage: Optional[str],
    code_page: str = "cp037",
    sign_separate: bool = False,
    data_encoding: str = DEFAULT_DATA_ENCODING,
) -> Any:
    """A field's value: an exact Decimal for numeric DISPLAY / COMP-3 / COMP, else its text. Storage a
    COBOL NUMERIC test would reject (a space, a stray `+`, a bad nibble) is `<invalid ...>`, never a number
    (#3830): the oracle may not be more lenient than the program. #3815: text and zoned bytes are read in
    `data_encoding`; bytes that are not text there are `<undecodable ...>` (the raw bytes kept, never dropped)."""
    num = _pic_numeric(pic) if pic else None
    u = (usage or "DISPLAY").upper()
    if num is None:
        text = _decode_text(raw, data_encoding)
        return f"<undecodable {raw!r} in {data_encoding}>" if text is None else text
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
    decoded, sign = _decode_text(raw, data_encoding), 1
    if decoded is None:
        return invalid
    text = decoded
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
