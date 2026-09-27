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
   the declared codec cannot decode falls through to the guesses rather than failing;
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
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

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


# What the estate declares: one codec for every file, or {glob: codec} matched in order against the
# file's repo-relative POSIX path (first match wins; a glob without "/" also matches the bare name).
DeclaredEncoding = str | Mapping[str, str] | None


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
            return SourceText(_decode(data, declared, truncated), codecs.lookup(declared).name, "declared")
        except UnicodeDecodeError:
            pass  # the declaration does not fit this file: guess rather than drop a byte
    try:
        return SourceText(data.decode("cp1252"), "cp1252", "cp1252-fallback")
    except UnicodeDecodeError:  # cp1252 leaves 0x81 0x8D 0x8F 0x90 0x9D unmapped
        return SourceText(data.decode("latin-1"), "latin-1", "latin-1-fallback")


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
    return SourceText(src.text.replace("\r\n", "\n").replace("\r", "\n"), src.encoding, src.how)


def open_source(path: str | Path, declared: str | None = None) -> io.StringIO:
    """`read_source` as a text stream, for a `with open(path) as f:` body (json.load, f.read(), line
    iteration) that should decode like every other source read -- a strict UTF-8 open raised on a
    cp1252 manifest, and json.load refused a BOM."""
    return io.StringIO(read_source(path, declared=declared).text)
