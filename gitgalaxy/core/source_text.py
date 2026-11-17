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
4. the estate's declared code page (`--source-encoding`, or a per-glob map), strictly -- a file
   the declared codec cannot decode falls through to the guesses rather than failing. #3816: the
   national EBCDIC pages Python lacks (cp277, cp278, cp280, cp284, cp285, cp297, cp1047) are
   registered by `ebcdic_codecs`; a raw EBCDIC file's NEL (0x15) ends a line, and a file with no
   line ends at all is a fixed-block download (FB80), split into its 80-byte records. The mixed
   CJK pages (cp930, cp939, cp935, cp937, cp933) are split on bytes, and a record's sequence area
   (bytes 73-80) stays at column 73 however many characters its Kanji make (`_dbcs_records`);
5. strict cp1252 -- a guess: the commonest legacy code page;
6. Latin-1 -- a guess that cannot fail (every byte maps).

No decode ever drops or replaces a byte; `read_source` then applies universal newlines (CRLF and CR
become LF), as the text-mode `open()` it replaces did. `how` records which path was taken, so a guess
(`cp1252-fallback`, `latin-1-fallback`) can be surfaced rather than trusted silently.

`decode_bytes` is the same ladder for bytes that are not a whole file (a log line, a sniffed head),
and `resolve_declared_encoding` maps a file's path to the estate's declared code page.
"""

from __future__ import annotations

import codecs
import fnmatch
import io
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from gitgalaxy.core.ebcdic_codecs import EBCDIC_CODE_PAGES, register
from gitgalaxy.core.ebcdic_dbcs import DBCS_CODE_PAGES, decode_record

register()  # #3816: cp277 / cp278 / ... resolve wherever a source is decoded

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
    how: str  # "bom" | "utf-16-heuristic" | "utf-8" | "declared" | "cp1252-fallback" | "latin-1-fallback"
    cjk_candidates: tuple[str, ...] = ()  # #3878: a legacy guess that decodes strictly as these
    ebcdic_undeclared: bool = False  # #8412: a legacy guess made on bytes that read as raw EBCDIC


# What the estate declares: one codec for every file, or {glob: codec} matched in order against the
# file's repo-relative POSIX path (first match wins; a glob without "/" also matches the bare name).
DeclaredEncoding = str | Mapping[str, str] | None  # typing forms: the package supports 3.9


def validate_declared_encoding(spec: DeclaredEncoding) -> None:
    """Fail loudly, up front, on an unknown codec name -- a typo must not silently mean 'guess'."""
    if spec is None:
        return
    codecs_named = [spec] if isinstance(spec, str) else list(spec.values())
    if not isinstance(spec, (str, Mapping)) or not all(isinstance(c, str) for c in codecs_named):
        raise ValueError(f"source encoding must be a codec name or a {{glob: codec}} map, not {spec!r}")
    unknown = [codec for codec in codecs_named if not _is_codec(codec)]
    if unknown:
        raise ValueError(f"unknown source encoding {unknown[0]!r}")


def _is_codec(name: str) -> bool:
    try:
        codecs.lookup(name)
    except LookupError:
        return False
    return True


def parse_source_encoding(value: object) -> DeclaredEncoding:
    """The declared encoding from `--source-encoding` or `.galaxyscope.yaml`, validated: None, a
    codec name, "GLOB=CODEC,GLOB=CODEC" (the CLI form of a map), or a {glob: codec} mapping."""
    if value is None or value == "":
        return None
    spec: DeclaredEncoding
    if isinstance(value, str) and "=" in value:
        spec = {}
        for pair in value.split(","):
            glob, sep, codec = pair.partition("=")
            if not sep or not glob.strip() or not codec.strip():
                raise ValueError(f"source encoding pair {pair!r} is not GLOB=CODEC")
            spec[glob.strip()] = codec.strip()
    elif isinstance(value, str):
        spec = value.strip()
    elif isinstance(value, Mapping):
        spec = {str(k): v for k, v in value.items()}
    else:
        raise ValueError(f"source encoding must be a codec name or a {{glob: codec}} map, not {value!r}")
    validate_declared_encoding(spec)
    return spec


def resolve_declared_encoding(rel_path: str, spec: DeclaredEncoding) -> str | None:
    """The code page the estate declares for `rel_path`, or None when it declares none."""
    if spec is None or isinstance(spec, str):
        return spec or None
    posix = rel_path.replace("\\", "/")
    name = posix.rsplit("/", 1)[-1]
    for glob, codec in spec.items():
        if fnmatch.fnmatchcase(posix, glob) or ("/" not in glob and fnmatch.fnmatchcase(name, glob)):
            return codec
    return None


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


# #8412: EBCDIC letters, digits and the blank (0x40) -- the bytes of a COBOL / JCL / HLASM member. In
# ASCII, 0x40 is `@` and 0x81-0xF9 are high bytes only a legacy text holds a few of, so a sample made
# mostly of them, with a blank every few bytes and next to no printable ASCII, is raw EBCDIC.
_EBCDIC_TEXT_BYTES = frozenset(
    {0x40}
    | set(range(0x81, 0x8A))
    | set(range(0x91, 0x9A))
    | set(range(0xA2, 0xAA))
    | set(range(0xC1, 0xCA))
    | set(range(0xD1, 0xDA))
    | set(range(0xE2, 0xEA))
    | set(range(0xF0, 0xFA))
)
_EBCDIC_SAMPLE = 4096


def looks_like_ebcdic(data: bytes) -> bool:
    """#8412: True when `data` is raw EBCDIC text that no code page was declared for. The guess ladder
    (cp1252, then Latin-1) decodes every such byte to something, so the garbage was silent; this names
    it. A sniff, never a decode: which national page (cp037, cp500, cp1047...) is the estate's to say."""
    sample = data[:_EBCDIC_SAMPLE]
    if len(sample) < 16:
        return False
    n = len(sample)
    text_like = sum(1 for b in sample if b in _EBCDIC_TEXT_BYTES)
    blanks = sample.count(0x40)
    ascii_printable = sum(1 for b in sample if 0x20 <= b <= 0x7E and b != 0x40)  # the blank is 0x40
    return text_like * 100 >= n * 60 and blanks * 100 >= n * 4 and ascii_printable * 100 <= n * 40


_RDW_SAMPLE = 65536


def _rdw_chain(data: bytes, pos: int, end: int, cut_ok: bool) -> int:
    """#8412: how many RDWs (2-byte big-endian length that counts its own 4 bytes, then two zero bytes) chain
    from `pos` to exactly `end`; 0 when the chain breaks. `cut_ok`: the last record may run past `end` (the
    sample is a prefix), but only as a record whose header was valid."""
    n = 0
    while pos < end:
        if pos + 4 > end:
            return n if cut_ok and n else 0
        length = int.from_bytes(data[pos : pos + 2], "big")
        if length < 4 or data[pos + 2 : pos + 4] != b"\x00\x00":
            return 0
        n += 1
        pos += length
    return n if pos == end or (cut_ok and pos > end) else 0


def rdw_framing(data: bytes) -> str | None:
    """#8412: "bdw+rdw" or "rdw" when `data` is a RECFM=V / VB export -- every record behind a 4-byte record
    descriptor word, every block behind a block descriptor word -- else None. A sniff by structure, never a
    decode: the 4 prefix bytes are binary in any code page, so the lengths must chain to the end of the file
    (3+ records) and a plain text has no NUL to hold the two zero bytes. BDW is tried first: a block's
    descriptor looks like one long record's. Which code page the records are in is the estate's to say."""
    sample = data[:_RDW_SAMPLE]
    cut = len(data) > len(sample)
    if len(sample) < 8 or sample[2:4] != b"\x00\x00":
        return None
    block = int.from_bytes(sample[:2], "big")
    # one block alone is a file too; else the next block must start with a descriptor
    block_ok = 8 <= block <= len(sample) and _rdw_chain(sample, 4, block, False) >= 1
    if block_ok and (block == len(sample) or _rdw_chain(sample, block, len(sample), cut) >= 1):
        return "bdw+rdw"
    if _rdw_chain(sample, 0, len(sample), cut) >= 3:
        return "rdw"
    return None


_FB_LRECL = 80  # a card image: the record length of source PDSes (JCL, COBOL, PL/I, HLASM)


def _ebcdic_records(text: str) -> str:
    """#3816: lines of a file decoded from raw EBCDIC. z/OS text ends a line with NEL (0x15, U+0085); a
    binary download of a fixed-block member has no line ends at all, only 80-byte records back to back
    -- split, so fixed-format columns (7, 72, 73-80) stay where the language reads them."""
    text = text.replace("\x85", "\n")
    if "\n" not in text and len(text) >= _FB_LRECL and len(text) % _FB_LRECL == 0:
        text = "\n".join(text[i : i + _FB_LRECL] for i in range(0, len(text), _FB_LRECL)) + "\n"
    return text


_SEQUENCE_COLUMN = 72  # bytes 1-72 are the program; 73-80 the sequence area


def _dbcs_records(data: bytes, cp: str, truncated: bool) -> str:
    """#3816 part 3a: `_ebcdic_records` for a mixed single/double-byte page, done on bytes -- a
    Shift-Out / pair / Shift-In run is one character per two bytes, and the shifts none, so a record's
    80 bytes are fewer characters and a character split would cut records mid-line. NEL (0x15) and the
    record boundaries are found in the bytes (a pair's bytes are 0x40-0xFE, never 0x15), and each
    record is decoded on its own, starting in single-byte mode.

    Columns are bytes on the host: the compiler reads a record's first 72 bytes as the program and the
    last 8 as the sequence area, however many characters the Kanji make of them. So a record longer
    than 72 bytes that shifts out is decoded in two parts, the first padded to 72 characters -- the
    sequence area stays at index 72, where every fixed-format reader slices it off. A pair the byte-72
    boundary would cut (malformed, but it happens) decodes the record whole instead."""
    if b"\x15" in data:
        records = data.split(b"\x15")
        ends = "\n"
    elif b"\x25" not in data and len(data) >= _FB_LRECL and len(data) % _FB_LRECL == 0:
        records = [data[i : i + _FB_LRECL] for i in range(0, len(data), _FB_LRECL)] + [b""]
        ends = "\n"
    else:
        records, ends = [data], ""
    lines = []
    for n, record in enumerate(records):
        final = not truncated or n < len(records) - 1  # only the last record can be cut by the read
        if len(record) > _SEQUENCE_COLUMN and b"\x0e" in record and final:
            try:
                head = decode_record(cp, record[:_SEQUENCE_COLUMN])
            except UnicodeDecodeError:
                pass
            else:
                lines.append(head.ljust(_SEQUENCE_COLUMN) + decode_record(cp, record[_SEQUENCE_COLUMN:]))
                continue
        lines.append(decode_record(cp, record, final))
    return ends.join(lines)


# #3878: the double-byte code pages a legacy-guessed file may really be in. GB18030 is left out: it
# decodes almost any bytes, so "it decodes" is no evidence (GBK, its strict subset, stands for it).
_CJK_CANDIDATES = ("shift_jis", "euc_jp", "gbk", "big5", "euc_kr")
_CJK_SAMPLE = 65536
_NON_ASCII_RUN = re.compile(rb"[\x80-\xff]{1,64}")


def cjk_candidates(data: bytes) -> tuple[str, ...]:
    """#3878: the CJK code pages a file that fell back to cp1252 / Latin-1 decodes strictly as -- a
    hint that the estate should declare one (`--source-encoding`), never a decode. Evidence: CJK text
    is double-byte characters in runs, so at least 3 non-ASCII runs of 4+ bytes (two characters) that
    hold 60%+ of the non-ASCII bytes; Western text is accents alone between ASCII letters (`élève`,
    `für`), which Shift-JIS and GBK would otherwise read as kanji. Every codec that decodes is named:
    GB and Big5 and EUC-KR share byte ranges, so which one is the estate's is for its owner to say."""
    sample = data[:_CJK_SAMPLE]
    runs = [len(m.group(0)) for m in _NON_ASCII_RUN.finditer(sample)]
    long_runs = [n for n in runs if n >= 4]
    if len(long_runs) < 3 or sum(long_runs) < 0.6 * sum(runs):
        return ()
    if len(data) > _CJK_SAMPLE:  # don't let a character cut at the sample's end fail every codec
        sample = sample[: sample.rfind(b"\n") + 1] or sample
    found = []
    for codec in _CJK_CANDIDATES:
        try:
            sample.decode(codec)
        except UnicodeDecodeError:
            continue
        found.append(codec)
    return tuple(found)


def decode_source(data: bytes, *, truncated: bool = False, declared: str | None = None) -> SourceText:
    """Decode source bytes without losing any. `truncated`: the bytes are a prefix of the file, so a
    multi-byte character cut at the end must not make valid UTF-8 look invalid. `declared`: the
    estate's code page for this file, tried strictly after UTF-8 and before the legacy guesses."""
    for bom, codec in _BOMS:
        if data.startswith(bom):
            try:
                return SourceText(_decode(data[len(bom) :], codec, truncated), codec, "bom")
            except UnicodeDecodeError:
                break  # a false mark (e.g. Latin-1 text starting "ÿþ"): decode the bytes as they are
    utf16 = _utf16_without_bom(data)
    if utf16 is not None:
        try:
            text = _decode(data, utf16, truncated)
        except UnicodeDecodeError:
            text = None
        if text is not None and _looks_like_text(text):
            return SourceText(text, utf16, "utf-16-heuristic")
    try:
        return SourceText(_decode(data, "utf-8", truncated), "utf-8", "utf-8")
    except UnicodeDecodeError:
        pass
    if declared:
        try:
            name = codecs.lookup(declared).name
            if name in DBCS_CODE_PAGES:
                return SourceText(_dbcs_records(data, name, truncated), name, "declared")
            text = _decode(data, declared, truncated)
            if name in EBCDIC_CODE_PAGES:
                text = _ebcdic_records(text)
            return SourceText(text, name, "declared")
        except UnicodeDecodeError:
            pass  # the declaration does not fit this file: guess rather than drop a byte
    try:
        text, name, how = data.decode("cp1252"), "cp1252", "cp1252-fallback"
    except UnicodeDecodeError:  # cp1252 leaves 0x81 0x8D 0x8F 0x90 0x9D unmapped
        text, name, how = data.decode("latin-1"), "latin-1", "latin-1-fallback"
    return SourceText(text, name, how, cjk_candidates(data), ebcdic_undeclared=not declared and looks_like_ebcdic(data))


def decode_bytes(data: bytes, declared: str | None = None) -> str:
    """Text for bytes that are not a whole source file (a log line, a sniffed head): the same
    lossless ladder, minus universal newlines -- the caller owns its own line splitting."""
    return decode_source(data, declared=declared).text


def read_source(path: str | Path, limit: int | None = None, declared: str | None = None) -> SourceText:
    """A source file's text, decoded without losing a byte. `limit`: read at most that many bytes (a
    guard against multi-GB logs) -- the file is then decoded as the prefix it is. `declared`: the
    estate's code page for this file (see `resolve_declared_encoding`)."""
    with open(path, "rb") as f:
        data = f.read() if limit is None else f.read(limit)
    src = decode_source(data, truncated=limit is not None and len(data) == limit, declared=declared)
    if "\r" not in src.text:
        return src
    # universal newlines, as text-mode open() gave every caller: CRLF and lone CR become LF, so line
    # counts, `$` anchors and fixed-format columns see one line ending whatever the file used
    return replace(src, text=src.text.replace("\r\n", "\n").replace("\r", "\n"))


def open_source(path: str | Path, declared: str | None = None) -> io.StringIO:
    """`read_source` as a text stream, for a `with open(path) as f:` body (json.load, f.read(), line
    iteration) that should decode like every other source read -- a strict UTF-8 open raised on a
    cp1252 manifest, and json.load refused a BOM."""
    return io.StringIO(read_source(path, declared=declared).text)
