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
import os
import re
import shutil
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from gitgalaxy.core.compiler_options import (
    DEFAULTS,
    SEMANTIC_OPTIONS,
    cards,
    effective_with_defaults,
)
from gitgalaxy.core.ebcdic_codecs import java_charset_name
from gitgalaxy.core.ebcdic_codecs import register as _register_ebcdic
from gitgalaxy.core.estate_options import effective_options
from gitgalaxy.core.source_text import decode_bytes, read_source
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
    """A dataset's input: `@case/...` is a file of the case directory, an absolute path itself (#4049: the
    strengthening loop's candidate inputs), else the corpus's."""
    if rel.startswith("@case/"):
        return CASES / case["name"] / rel[len("@case/") :]
    return Path(rel) if Path(rel).is_absolute() else corpus / rel


# #3828: the compiler options that change results, as GnuCOBOL 3.1 flags under `-std=ibm` ("" = its own
# behaviour already). #4102: `-std=ibm` alone keeps a binary item's bytes (TRUNC(BIN)); -fbinary-truncate gives IBM's
# default TRUNC(STD) -- MOVE 99999 to S9(4) COMP stores 9999, ADD past 9999 is a size error (measured 2026-10-02). GnuCOBOL has no INTDATE (INTEGER-OF-DATE is always ANSI), no ARITH(EXTEND)
# and no TRUNC(OPT) (#4706: OPT is TRUNC(STD) wherever every binary value fits its PICTURE, and the det runtime stops
# by name where one would not -- so the oracle runs -fbinary-truncate; see option_differences): a case needing one it
# cannot honour cannot be proven here, and says so rather than run unfaithfully. NUMPROC: see numproc_mig and
# numproc_guard (#4271).
COBC_OPTIONS = {
    ("INTDATE", "ANSI"): "", ("TRUNC", "STD"): "-fbinary-truncate", ("TRUNC", "BIN"): "-fnotrunc", ("ARITH", "COMPAT"): "",
    # #4706: under TRUNC(OPT) IBM "assumes that data conforms to PICTURE specifications in USAGE BINARY receiving
    # fields" and leaves a value that does not to the generated code (Programming Guide, "TRUNC"); conforming, the
    # results are TRUNC(STD)'s. The det runtime stops by name before a value past a binary receiver's PICTURE is
    # stored (Codec.truncOpt), so a scenario that reaches one is never judged; a port without that stop is proven as
    # TRUNC(STD), a declared difference (option_differences).
    ("TRUNC", "OPT"): "-fbinary-truncate",
    ("NUMPROC", "NOPFD"): "",
    # #4271: with preferred signs NUMPROC(PFD) computes as NOPFD (Programming Guide SC27-8714-03, "Sign representation
    # of zoned and packed-decimal data"); what it does with any other sign IBM leaves to the generated code, and the
    # det runtime refuses such a value by name (Codec.numprocPfd). A port without that guard is refused here
    # (numproc_guard): GnuCOBOL accepts every sign.
    ("NUMPROC", "PFD"): "",
}  # fmt: skip


def bms_dir(corpus: Path) -> Path:
    """The symbolic-map copybooks of the corpus's BMS sources (det.source.bms_copybooks, the generator the det
    translator's own copybook path uses), generated once next to the corpus clone: a build artefact most estates do
    not check in (CBSA, IBM DBB MortgageApplication)."""
    from gitgalaxy.tools.cobol_to_java.det.source import bms_copybooks

    out = corpus.parent / "_bms" / corpus.name
    if not out.is_dir():
        bms_copybooks([p for p in corpus.rglob("*") if p.is_file() and p.suffix.lower() == ".bms"
                       and ".git" not in p.parts], out)  # fmt: skip
    return out


def case_path(corpus: Path, rel: str) -> Path:
    """A path a case names: relative to the corpus, or `@bms/<MAPSET>.cpy` -- a generated symbolic map (bms_dir)."""
    return bms_dir(corpus) / rel[len("@bms/") :] if rel.startswith("@bms/") else corpus / rel


def stage_copybooks(case: dict[str, Any], corpus: Path, src: Path) -> None:
    """The case's copy_dirs into the GnuCOBOL source directory. A z/OS library member's name is upper-case and COPY
    names are not case-sensitive, so each file is also staged under its upper-case name: COPY COACTVW finds
    COACTVW.cpy, and COPY EPSNBRPM finds IBM DBB's lower-case epsnbrpm.cpy. A case whose screens name generated
    symbolic maps (`@bms/...`) also gets them, after the estate's own copybooks (a member the estate ships wins).
    A BMS map source (`.bms`, assembler macros) is no COPY member: GenApp keeps ssmap.bms beside its programs, and
    staged as SSMAP.cpy it would shadow the generated symbolic map that `COPY SSMAP` means (#4270)."""
    for cpy in case.get("copy_dirs", []):
        for p in (corpus / cpy).iterdir():
            if p.is_file() and p.suffix.lower() != ".bms":
                shutil.copy(p, src / p.name)
                shutil.copy(p, src / (p.stem.upper() + ".cpy"))
    if any(str(s.get("copybook", "")).startswith("@bms/") for s in (case.get("screens") or {}).values()):
        for p in bms_dir(corpus).iterdir():
            if p.is_file() and not (src / p.name).exists():
                shutil.copy(p, src / p.name)


# A PROGRAM-ID paragraph whose name is not followed by its period: IBM Enterprise COBOL assumes the period (a
# warning) and compiles; GnuCOBOL refuses (IBM DBB MortgageApplication EPSNBRVL: `PROGRAM-ID. EPSNBRVL`).
_PROGRAM_ID_NO_PERIOD = re.compile(r"^(.{6}[ ]{1,4}PROGRAM-ID\.?[ ]+'?[A-Z0-9#@$-]+'?)([ ]*)$", re.I)


def ibm_assumed_periods(source: str) -> str:
    """The source as IBM's compiler reads it where it assumes a missing period GnuCOBOL requires: a PROGRAM-ID name
    with nothing after it on its line gets its period (oracle_assumptions.md, register entry L4)."""
    lines = source.split("\n")
    for i, ln in enumerate(lines):
        body = ln[:72]
        m = _PROGRAM_ID_NO_PERIOD.match(body.rstrip())
        if m and not body.rstrip().endswith("."):
            lines[i] = m.group(1) + "." + ln[len(m.group(1)) + 1 :] if len(ln) > len(m.group(1)) else m.group(1) + "."
    return "\n".join(lines)


class UnsupportedOption(Exception):
    """A compiler option the GnuCOBOL side cannot honour (#3828)."""


def compiler_version(case: dict[str, Any]) -> Optional[tuple[int, int]]:
    """(version, release) of the IBM compiler a case states it was built with (`"compiler": {"product": "Enterprise
    COBOL", "version": "6.1", "evidence": ...}`, e.g. the estate's build JCL's IGY.V6R1M0.SIGYCOMP), else the estate
    options file's (#4704: gitgalaxy.core.estate_options), else None."""
    c = effective_options(case).compiler
    m = re.fullmatch(r"(\d+)(?:\.(\d+))?(?:\.\d+)*", str(c.get("version") or "").strip())
    if not m or str(c.get("product") or "").strip().lower() != "enterprise cobol":
        return None
    return int(m.group(1)), int(m.group(2) or 0)


def numproc_mig(case: dict[str, Any]) -> str:
    """#4271: what NUMPROC(MIG) compiles as (register C5). Enterprise COBOL 5 and 6 no longer support MIG: "If
    NUMPROC(MIG) is specified, Enterprise COBOL 5 or 6 issues a warning message and the compilation will get the
    default setting for NUMPROC. This is either the user-customized default or the IBM default, which is
    NUMPROC(NOPFD)" (Enterprise COBOL for z/OS 6.4 Migration Guide, GC27-8715-03, Table 18 "Compiler options not
    supported in Enterprise COBOL"; the same in the 5.2 Migration Guide, GC14-7383-03). The installation default is taken as IBM's (ASSUMED). Under Enterprise COBOL 4 or earlier
    MIG was its own sign processing, documented only as "similar to OS/VS COBOL": refused, as is a case that does
    not state its compiler."""
    version = compiler_version(case)
    if version is None or version[0] < 5:
        raise UnsupportedOption(
            "NUMPROC(MIG): its sign processing is OS/VS COBOL's under Enterprise COBOL 4 and earlier, which IBM does "
            "not specify, so the case cannot be proven; a case built by Enterprise COBOL 5 or later states its "
            '"compiler" (product, version, evidence), and MIG then compiles as NUMPROC(NOPFD)'
        )
    return DEFAULTS["NUMPROC"]


def numproc(case: dict[str, Any], source: str) -> str:
    """The NUMPROC the program compiles with: its cards over the case's `compiler_options`, else IBM's default; MIG
    resolved by numproc_mig."""
    value = str(effective_with_defaults(effective_options(case).layers, source).get("NUMPROC") or "").upper()
    value = value or DEFAULTS["NUMPROC"]
    return numproc_mig(case) if value == "MIG" else value


DET_PORT_HEADER = "// gitgalaxy-det-port:"


def numproc_guard(case: dict[str, Any], source: str, port_dir: Optional[Path]) -> None:
    """#4271: a NUMPROC(PFD) program is proven only through a det port, whose runtime refuses a non-preferred sign
    (register C5); a model port or the generated service has no such guard, so GnuCOBOL's NOPFD reading of a
    non-preferred sign could pass for IBM's PFD. Raises UnsupportedOption for those."""
    if numproc(case, source) != "PFD":
        return
    services = sorted(port_dir.rglob("*Service.java")) if port_dir and port_dir.is_dir() else []
    if not any(read_source(p).text.startswith(DET_PORT_HEADER) for p in services):
        raise UnsupportedOption(
            "NUMPROC(PFD): only a det port's runtime refuses a non-preferred sign (oracle_assumptions.md C5); this "
            "port has no such guard, so the case cannot be proven with it"
        )


# #4751: GnuCOBOL 3.1.2 lays out a COMP-5 item of 1 or 2 digits (its PICTURE's 9s) in one byte whatever
# -fbinary-size says (`-std=ibm` already sets 2-4-8, which COMP / COMP-4 / BINARY follow); IBM and the det layout use a
# halfword. Register C16.
_COMP5 = re.compile(r"\bCOMP(?:UTATIONAL)?-5\b", re.I)
_LEVEL = re.compile(r"\s*(\d{1,2})\s")
_PICTURE = re.compile(r"\bPIC(?:TURE)?\s+(?:IS\s+)?(\S+)", re.I)


def one_byte_comp5(text: str) -> list[str]:
    """#4751: the data items of a COBOL source (program or copybook, fixed format) that GnuCOBOL lays out in one byte
    and IBM in a halfword: a COMP-5 item, its own USAGE or a group's, whose PICTURE has 1 or 2 9s."""
    code = []
    for ln in text.splitlines():
        if len(ln) > 6 and ln[6] in "*/":
            continue
        code.append(ln[7:72].split("*>")[0])
    found: list[str] = []
    groups: list[tuple[int, bool]] = []  # the open groups: (level, USAGE COMP-5)
    for entry in re.split(r"\.(?=\s|$)", " ".join(code)):
        m = _LEVEL.match(entry)
        if not m or int(m.group(1)) in (66, 88):
            continue
        level = int(m.group(1))
        level = 1 if level == 77 else level
        while groups and groups[-1][0] >= level:
            groups.pop()
        comp5 = bool(_COMP5.search(entry)) or any(c for _, c in groups)
        pic = _PICTURE.search(entry)
        if pic is None:
            groups.append((level, comp5))
            continue
        p = re.sub(r"(.)\((\d+)\)", lambda x: x.group(1) * int(x.group(2)), pic.group(1).upper())
        if comp5 and 0 < p.count("9") <= 2 and not re.search(r"[XAN]", p):
            found.append(" ".join(entry.split()))
    return found


def comp5_layout_guard(src: Path) -> None:
    """#4751: refuse an oracle build whose COBOL sources (the staged program, its copybooks and called programs)
    declare a 1- or 2-digit COMP-5 item: GnuCOBOL lays it out in one byte, IBM in a halfword, so its offsets, its
    record's length and a value past 127 / 255 differ (register C16). No cobc option changes it (-fbinary-size is
    ignored for COMP-5 but for `1--8`)."""
    for p in sorted(src.iterdir()):
        if p.is_file() and p.suffix.lower() not in (".c", ".h", ".sql", ".cfg"):
            hits = one_byte_comp5(decode_bytes(p.read_bytes()))
            if hits:
                raise UnsupportedOption(
                    f"{p.name}: `{hits[0]}`: GnuCOBOL lays out a 1- or 2-digit COMP-5 item in one byte, IBM in a "
                    "halfword (oracle_assumptions.md C16), so the case cannot be proven"
                )


TRUNC_OPT_STOP = "Cobol.swapTruncOpt(true)"  # det/program.with_trunc: a det port run under TRUNC(OPT)'s stop


def option_differences(case: dict[str, Any], source: str, port_dir: Optional[Path]) -> list[dict[str, Any]]:
    """#4706: the options the proof of `port_dir` (None: the generated service) cannot claim, as declared differences
    for its evidence record. TRUNC(OPT) is claimed only by a det port built with the runtime's stop on a value past a
    binary receiver's PICTURE (TRUNC_OPT_STOP); any other port is proven as TRUNC(STD) -- what IBM computes under OPT
    for conforming values, but nothing guarantees a scenario stays conforming."""
    trunc = str(effective_with_defaults(effective_options(case).layers, source).get("TRUNC") or "").upper()
    if trunc != "OPT":
        return []
    services = sorted(port_dir.rglob("*Service.java")) if port_dir and port_dir.is_dir() else []
    if any(TRUNC_OPT_STOP in read_source(p).text for p in services):
        return []
    return [{"kind": "option", "option": "TRUNC", "declared": "OPT", "applied": "STD",
             "note": "TRUNC(OPT): this port has no stop on a value past a binary item's PICTURE (only a det port's "
                     "runtime has one, oracle_assumptions.md C5), so it is proven as TRUNC(STD) -- IBM's OPT result "
                     "only while every binary value fits its PICTURE (#4706)"}]  # fmt: skip


def compile_options(case: dict[str, Any], source: str) -> tuple[str, list[str]]:
    """#3828: (the program with its CBL / PROCESS cards blanked -- GnuCOBOL rejects CBL --, the cobc
    flags for its options). The case's `compiler_options` (e.g. ["INTDATE(LILIAN)"]) stand for the
    compile step's PARM, so the program's own cards override them, as on z/OS. Options that change
    no result (APOST, CICS, SQL, OPT ...) are dropped; a semantic one GnuCOBOL cannot honour raises. The estate's own
    PARM comes from its options file (tests/equivalence/estate_options, #4704), where a value the harness cannot
    honour carries the `applied_value` the proof runs under (a declared difference)."""
    flags = []
    # #4704: one resolver -- installation defaults < the estate's PARM < the case's `compiler_options` < the cards --
    # an option nothing names is IBM's default (#4102: TRUNC(STD))
    eff = effective_with_defaults(effective_options(case).layers, source)
    if str(eff.get("NUMPROC") or "").upper() == "MIG":
        eff["NUMPROC"] = numproc_mig(case)
    for option, value in eff.items():
        if option not in SEMANTIC_OPTIONS:
            continue
        flag = COBC_OPTIONS.get((option, str(value or "").upper()))
        if flag is None:
            raise UnsupportedOption(f"{option}({value}): GnuCOBOL 3.1 has no equivalent, so the case cannot be proven")
        if flag:
            flags.append(flag)
    blank = {n for n, _ in cards(source)}
    lines = ibm_assumed_periods(source).split("\n")
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
    if u == "POINTER" and not pic:  # #4270 (C9): NULL or not, never the address
        return decode_pointer(raw)
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


class LayoutError(ValueError):
    """A record's layout cannot be computed faithfully (#4010): a COPY inside it that resolves
    nowhere, or a COPY ... REPLACING. Raised instead of returning a layout whose later fields shift."""


# #4010: a COPY statement's start, in Area A..B text (upper-cased, comments dropped). The member
# name may be quoted; the rest of the statement (OF/IN library, REPLACING, the period) is read by
# _copy_statement with plain string operations, so no regex spans it.
_COPY_START = re.compile(r"^\s*COPY\s+['\"]?([A-Z0-9#@$][A-Z0-9#@$-]*)['\"]?(?![A-Z0-9#@$-])")
_HEADER = re.compile(r"^\s*(?:[A-Z0-9-]+\s+SECTION|[A-Z]+\s+DIVISION)\b")
_COPY_EXTS = (".cpy", ".CPY", ".copy", ".COPY", "")
_COPY_DEPTH = 8


def _area_lines(path: Path) -> list[str]:
    """Area A..B of each code line of a fixed-format source, as the answer key's Source reads it:
    comment and debug lines dropped, `*>` comments cut, upper-cased."""
    from key_text import read_key_text

    out = []
    for raw in read_key_text(path).splitlines():
        if len(raw) > 6 and raw[6] in "*/Dd":
            continue
        out.append((raw[7:72] if len(raw) > 7 else "").split("*>", 1)[0].upper())
    return out


def _copy_statement(lines: list[str], i: int) -> tuple[str, int]:
    """The text of the COPY statement starting on lines[i], up to its period (a few lines at
    most), and the index of the line after it."""
    text, j = lines[i], i + 1
    while "." not in text and j < len(lines) and j < i + 12:
        text += " " + lines[j]
        j += 1
    return text, j


_PROCEDURE_DIVISION = re.compile(r"^\s*PROCEDURE\s+DIVISION\b", re.IGNORECASE)


def _expanded_lines(path: Path, dirs: list[Path], unresolved: list[tuple[int, str]], depth: int = 0) -> list[str]:
    """The code lines of `path` with each `COPY member.` replaced by the member's own (expanded)
    lines, found in `dirs` in order. A COPY found nowhere contributes no lines: its position (the
    index in the returned list its lines would have started at) and name go to `unresolved`."""
    lines = _area_lines(path)
    out: list[str] = []
    i = 0
    while i < len(lines):
        if _PROCEDURE_DIVISION.match(lines[i]):  # no record is laid out here: its COPYs (COACTUPC's 39 COPY
            out.extend(lines[i:])  # CSSETATY REPLACING, screen-attribute code) are left as written
            break
        m = _COPY_START.match(lines[i])
        if not m:
            out.append(lines[i])
            i += 1
            continue
        stmt, i = _copy_statement(lines, i)
        member = m.group(1)
        if "REPLACING" in stmt.split():
            raise LayoutError(f"{path.name}: COPY {member} REPLACING is not modelled by layout_fields")
        if depth >= _COPY_DEPTH:
            raise LayoutError(f"{path.name}: COPY {member} nests deeper than {_COPY_DEPTH} levels")
        found = next(
            (d / f"{name}{ext}" for d in dirs for name in dict.fromkeys((member, member.lower()))
             for ext in _COPY_EXTS if (d / f"{name}{ext}").is_file()),
            None,
        )  # fmt: skip
        if found is None:
            unresolved.append((len(out), member))
        else:
            out.extend(_expanded_lines(found, dirs, unresolved, depth + 1))
    return out


# #4270 (oracle_assumptions.md C9): a POINTER as the oracle lays it out -- GnuCOBOL on x86-64, 8 bytes; Enterprise
# COBOL's (AMODE 31) is 4. A record is laid out as the oracle stores it, so each side's fields are read where its own
# program put them and compared by NAME (never as raw bytes across the two layouts). A POINTER's value is an address,
# meaningless across sides: it is compared only as NULL or not (decode_field / decode_pointer).
ORACLE_POINTER_BYTES = 8
POINTER_NULL = "NULL"
POINTER_SET = "<a POINTER holding an address: not portable, never equal>"


def _pointer(it: dict[str, Any]) -> bool:
    return not it.get("pic") and (it.get("usage") or "").upper() == "POINTER"


def decode_pointer(raw: bytes) -> str:
    """A POINTER's bytes as compared: NULL (all zero, as SET ... TO NULL and INITIALIZE leave it), else POINTER_SET --
    an address, which no other run of either side would hold (IBM gives it no stable value), so it never compares
    equal to anything."""
    return POINTER_NULL if not any(raw) else POINTER_SET


def layout_fields(
    corpus: Path,
    copybook: str,
    record: Optional[str] = None,
    copy_dirs: Optional[list[Path]] = None,
    occurrences: bool = False,
) -> list[dict[str, Any]]:
    """The elementary fields of a copybook record: name, offset, bytes, pic, usage (the answer
    key's own reader and storage arithmetic, cobol_answer_key).

    #4010: each COPY in the file is expanded first, its member looked up in `copy_dirs` (default:
    the file's own directory, then `corpus`), so the fields after a nested COPY keep their offsets.
    A COPY that resolves nowhere is harmless outside the chosen record but raises LayoutError
    inside it, as does a COPY ... REPLACING anywhere before the PROCEDURE DIVISION (after it, no record
    is laid out and nothing is expanded): a shifted layout is never returned.

    #4765 `occurrences`: every occurrence of an OCCURS item is a field of its own, named by its subscripts
    (`COMM-ACC-TYPE(3)`, `CELL(2,4)` under a nested OCCURS), with `base` (the item's name), `subscripts` and -- under
    an OCCURS DEPENDING ON -- `odo`: [[object, subscript], ...], the occurrence's index in each variable table above
    it (active_fields keeps an occurrence only while each object holds at least that). Without it an OCCURS group's
    fields are listed once, at its first occurrence, and an elementary OCCURS item once, as wide as all of them: what
    a record is BUILT from (a scenario's COMMAREA, generated inputs), as the DTO lists them; a record COMPARED is
    read with every occurrence."""
    import cobol_answer_key as ak

    path = corpus / copybook
    dirs = copy_dirs if copy_dirs is not None else [path.parent, corpus]
    unresolved: list[tuple[int, str]] = []
    text = _expanded_lines(path, dirs, unresolved)
    items = [it for it in ak._data_items(ak.Source(path, list(enumerate(text, 1)))) if it["level"] not in (66, 88)]
    kids: dict[Optional[int], list[dict[str, Any]]] = {}
    for it in items:
        kids.setdefault(it["parent"], []).append(it)

    def own(it: dict[str, Any]) -> int:  # one occurrence's bytes
        if _pointer(it):
            return ORACLE_POINTER_BYTES
        if it.get("pic"):
            return ak._pic_bytes(it["pic"], it.get("usage"), it.get("sign_separate", False))
        return sum(size(c) for c in kids.get(it["ordinal"], []) if not c.get("redefines"))

    def size(it: dict[str, Any]) -> int:
        return own(it) * (it.get("occurs_max") or 1)

    out: list[dict[str, Any]] = []

    def field(it: dict[str, Any], at: int, subs: list[int], odo: list[list[Any]]) -> dict[str, Any]:
        f: dict[str, Any] = {"name": it["name"], "offset": at}
        if _pointer(it):  # #4270 (C9): as the oracle stores it, so the fields after it sit where its program reads them
            f.update({"bytes": own(it) if occurrences else size(it), "pic": None, "usage": "POINTER",
                      "sign_separate": False})  # fmt: skip
        else:
            f.update({"bytes": own(it) if occurrences else size(it), "pic": it["pic"], "usage": it.get("usage"),
                      "sign_separate": bool(it.get("sign_separate")),
                      **({"sign_leading": bool(it.get("sign_leading"))} if it.get("sign_separate") else {})})  # fmt: skip
        if subs:  # #4765: one occurrence, by name and subscripts
            f.update({"name": f"{it['name']}({','.join(map(str, subs))})", "base": it["name"], "subscripts": subs})
            if odo:
                f["odo"] = odo
        return f

    def place(it: dict[str, Any], at: int, subs: list[int], odo: list[list[Any]]) -> None:
        times = (it.get("occurs_max") or 1) if occurrences else 1
        varying = it.get("occurs_depending_on") if occurrences else None
        for k in range(1, times + 1):
            start = at + (k - 1) * own(it)
            ksubs = [*subs, k] if occurrences and it.get("occurs_max") else subs
            kodo = [*odo, [varying, k]] if varying else odo
            if _pointer(it) or it.get("pic"):
                out.append(field(it, start, ksubs, kodo))
                continue
            cur = start
            for c in kids.get(it["ordinal"], []):
                if c.get("redefines"):
                    continue
                place(c, cur, ksubs, kodo)
                cur += size(c)

    # A named record may itself REDEFINE another (#3754: a symbolic map's output area, CACTVWAO
    # REDEFINES CACTVWAI); with no name, the first record that does not is the layout.
    roots = [r for r in kids.get(None, []) if (r["name"] == record if record else not r.get("redefines"))]
    if not roots:
        raise LayoutError(f"{copybook}: no record {record or '(first)'}")
    root = roots[0]
    # The record runs from its own line to the next 01/77, section or division header (or the
    # end): a COPY that resolved nowhere there could hold any of its fields. (Line n is
    # text[n - 1]; an unresolved COPY at index `at` sits just before line at + 1.)
    later = [r["line"] for r in kids.get(None, []) if r["line"] > root["line"]]
    later += [n for n, line in enumerate(text, 1) if n > root["line"] and _HEADER.match(line)]
    end = min(later) if later else len(text) + 1
    inside = [name for at, name in unresolved if root["line"] < at + 1 <= end]
    if inside:
        raise LayoutError(
            f"{copybook}: COPY {', '.join(inside)} inside {root['name']} resolves nowhere in "
            f"{', '.join(str(d) for d in dirs)}, so every field after it would shift"
        )
    place(root, 0, [], [])
    return out


def active_fields(
    data: bytes, fields: list[dict[str, Any]], data_encoding: str = DEFAULT_DATA_ENCODING
) -> list[dict[str, Any]]:
    """#4765: the fields of a record (layout_fields(..., occurrences=True)) its own bytes make active: an occurrence
    of an OCCURS DEPENDING ON table is kept only while the object holds at least its subscript, read from `data`
    itself -- each side's record by its own count, so a count that differs is a difference and so is every occurrence
    one side has and the other does not. An object the layout does not hold, or one that is not a number, keeps
    every occurrence (the table's maximum), never fewer: nothing is left uncompared on a guess."""
    if not any(f.get("odo") for f in fields):
        return fields
    by_name = {f["name"]: f for f in fields}
    counts: dict[str, Optional[int]] = {}

    def count(obj: str) -> Optional[int]:
        if obj not in counts:
            f = by_name.get(obj)
            v = None
            if f is not None and f["offset"] + f["bytes"] <= len(data):
                v = decode_field(data[f["offset"] : f["offset"] + f["bytes"]], f["pic"], f["usage"],
                                 sign_page(data_encoding), f.get("sign_separate", False), data_encoding)  # fmt: skip
            counts[obj] = int(v) if isinstance(v, Decimal) and v == v.to_integral_value() else None
        return counts[obj]

    def active(f: dict[str, Any]) -> bool:
        for obj, k in f.get("odo") or []:
            n = count(obj)
            if n is not None and k > n:
                return False
        return True

    return [f for f in fields if active(f)]


# ---- the field-by-field diff ---------------------------------------------------------
# #3815: the usages whose bytes are characters in the data's page (the rest -- COMP, COMP-3 -- are binary)
_TEXT_USAGES = frozenset({"DISPLAY"})


def _as_text(raw: bytes, enc: str) -> Any:
    """#3815: bytes as text in `enc`, or the bytes themselves when they are not text there (never lost)."""
    try:
        return raw.decode(enc)
    except UnicodeDecodeError:
        return raw


def split_varseq(data: bytes) -> list[bytes]:
    """A variable-length sequential file (RECORDING MODE V / RECORD VARYING) as GnuCOBOL writes it
    (COB_VARSEQ_FORMAT 0, its default): per record a 4-byte header -- the data length as a big-endian halfword,
    then two zero bytes -- and the data. Unlike a z/OS RDW, the length does not count the header. Both sides of
    a comparison are framed this way; a framing error is a difference, never skipped."""
    recs, i = [], 0
    while i < len(data):
        if i + 4 > len(data) or data[i + 2 : i + 4] != b"\0\0":
            raise ValueError(f"not a GnuCOBOL variable-length record header at byte {i}: {data[i : i + 4]!r}")
        n = int.from_bytes(data[i : i + 2], "big")
        if i + 4 + n > len(data):
            raise ValueError(f"record at byte {i} claims {n} bytes; {len(data) - i - 4} remain")
        recs.append(data[i + 4 : i + 4 + n])
        i += 4 + n
    return recs


def diff_varseq(
    left: bytes,
    right: bytes,
    layouts: dict[int, list[dict[str, Any]]],
    code_page: str = "cp037",
    data_encoding: str = DEFAULT_DATA_ENCODING,
) -> dict[str, Any]:
    """diff_records for a variable-length file: records paired in order, each compared field by field against the
    layout its length selects (`layouts`: length -> fields; a length with no layout is compared byte for byte). A
    record of another length, a missing record, or a framing error is a difference."""
    out: dict[str, Any] = {"records": 0, "equal": 0, "diffs": [], "filler_differs": 0, "layout_bytes": 0}
    try:
        lrecs, rrecs = split_varseq(left), split_varseq(right)
    except ValueError as e:
        out["diffs"].append({"record": 0, "framing": str(e)})
        return out
    out["records"] = max(len(lrecs), len(rrecs))
    out["layout_bytes"] = max(layouts, default=0)
    for n in range(out["records"]):
        a = lrecs[n] if n < len(lrecs) else None
        b = rrecs[n] if n < len(rrecs) else None
        if a is None or b is None:
            out["diffs"].append({"record": n + 1, "missing": "cobol" if a is None else "java"})
            continue
        if len(a) != len(b):
            out["diffs"].append({"record": n + 1, "fields": [{"field": "(record length)", "cobol": str(len(a)),
                                                              "java": str(len(b))}]})  # fmt: skip
            continue
        d = diff_records(a, b, len(a), layouts.get(len(a), []), code_page, data_encoding)
        out["filler_differs"] += d["filler_differs"]
        if d["diffs"]:
            out["diffs"].append({"record": n + 1, "fields": d["diffs"][0]["fields"]})
        else:
            out["equal"] += 1
    return out


def diff_records(
    left: bytes,
    right: bytes,
    reclen: int,
    fields: list[dict[str, Any]],
    code_page: str = "cp037",
    data_encoding: str = DEFAULT_DATA_ENCODING,
    right_encoding: Optional[str] = None,
) -> dict[str, Any]:
    """Pair records in order; per pair, every differing field (value left vs right). A field whose value is
    equal but whose bytes are not (a C vs F sign nibble, -0 vs +0) is a difference too, marked `raw` and
    shown as hex (#3830): the files differ, and a later program may test the sign. A FILLER is counted
    apart (`filler_differs`), not as a difference: no program can name it, so what it holds after an
    INITIALIZE or a new record is the runtime's leftover record area, not the program's logic.

    #3820: the bytes no field covers are compared too, as `(bytes outside the layout)`. The layout is
    read from the copybook, so a width it gets wrong (a currency string sized as one byte) leaves the
    record's tail -- where the real later fields sit -- unread: comparing only the listed fields let
    two different records pass as equal. `layout_bytes` reports the layout's own width beside `reclen`.

    #3815: text and zoned fields are decoded in `data_encoding` (the case's page, default Latin-1), the right
    side in `right_encoding` when it was written in another (a mainframe's cp277 unload against a run in
    ISO-8859-1): then the same text in two pages is equal, and only a binary field's (COMP / COMP-3) bytes,
    which no page changes, are compared as bytes; FILLER and the bytes outside the layout are compared as text.
    Across pages, a record's layout must fit both (single-byte pages): offsets are bytes."""
    renc = right_encoding or data_encoding
    same_page = codecs.lookup(renc).name == codecs.lookup(data_encoding).name

    def same_bytes(x: bytes, y: bytes, usage: Optional[str] = None) -> bool:
        if same_page or (usage or "DISPLAY").upper() not in _TEXT_USAGES:
            return x == y
        return _as_text(x, data_encoding) == _as_text(y, renc)

    covered = bytearray(reclen)
    for f in fields:
        for i in range(max(f["offset"], 0), min(f["offset"] + f["bytes"], reclen)):
            covered[i] = 1
    layout_bytes = max((f["offset"] + f["bytes"] for f in fields), default=0)
    lrecs = [left[i : i + reclen] for i in range(0, len(left), reclen)]
    rrecs = [right[i : i + reclen] for i in range(0, len(right), reclen)]
    diffs, equal, filler = [], 0, 0
    for n in range(max(len(lrecs), len(rrecs))):
        a = lrecs[n] if n < len(lrecs) else None
        b = rrecs[n] if n < len(rrecs) else None
        if a is None or b is None:
            diffs.append({"record": n + 1, "missing": "cobol" if a is None else "java"})
            continue
        bad, filler_bad = [], False
        for f in fields:
            sl = slice(f["offset"], f["offset"] + f["bytes"])
            sep = f.get("sign_separate", False)
            va, vb = (
                decode_field(a[sl], f["pic"], f["usage"], code_page, sep, data_encoding),
                decode_field(b[sl], f["pic"], f["usage"], code_page, sep, renc),
            )
            if not same_bytes(a[sl], b[sl], f["usage"]) and f["name"] == "FILLER":
                filler_bad = True
            elif va != vb:
                bad.append({"field": f["name"], "cobol": str(va), "java": str(vb)})
            elif not same_bytes(a[sl], b[sl], f["usage"]):  # #3830: same value, other bytes -- C vs F sign, -0 / +0
                bad.append({"field": f["name"], "cobol": a[sl].hex(), "java": b[sl].hex(), "raw": True})
        outside = [
            i
            for i in range(max(len(a), len(b)))
            if (i >= reclen or not covered[i]) and not same_bytes(a[i : i + 1], b[i : i + 1])
        ]
        if outside:
            lo, hi = outside[0], outside[-1] + 1
            bad.append(
                {"field": f"(bytes outside the layout @{lo}..{hi})", "cobol": repr(a[lo:hi]), "java": repr(b[lo:hi])}
            )
        filler += filler_bad
        if bad:
            diffs.append({"record": n + 1, "fields": bad})
        else:
            equal += 1
    return {"records": max(len(lrecs), len(rrecs)), "equal": equal, "diffs": diffs, "filler_differs": filler,
            "layout_bytes": layout_bytes}  # fmt: skip


def java_failure_report(case: dict[str, Any], work: Path, error: str) -> dict[str, Any]:
    """The report of a proof whose Java side did not build or run: its compiler / test errors as the feedback."""
    log = next((p for p in [work / "java" / "maven.log", *(work / "java").glob("**/maven.log")] if p.is_file()), None)
    text = decode_bytes(log.read_bytes()) if log else error  # #3813: the lossless ladder, never errors=
    errors = []  # each compiler / test error once, its path cut to the file name (Maven prints them twice)
    boiler = ("Help 1", "Re-run Maven", "Please refer", "For more information", "To see the full stack trace",
              "Failed to execute goal", "-> [Help")  # fmt: skip
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        keep = ("[ERROR]" in ln and ln.strip() != "[ERROR]" and not any(b in ln for b in boiler)) or (
            ln.startswith(("java.", "Caused by:")) and "Exception" in ln and i > 0 and "Tests run" in "".join(lines[max(0, i - 3) : i])
        )  # fmt: skip
        if keep:
            ln = re.sub(r"\S*/([A-Za-z0-9_$]+\.java)", r"\1", ln)
            if ln not in errors:
                errors.append(ln)
            if ln.startswith("java.") and "Exception" in ln:  # where in the port: its first frames
                frames = [f.strip() for f in lines[i + 1 : i + 40] if f.strip().startswith("at com.gitgalaxy.")]
                errors += [f"    {f}" for f in frames[:4] if f"    {f}" not in errors]
    shown = "\n".join(errors[:40]) if errors else "\n".join(text.splitlines()[-60:])
    return {"case": case["name"], "program": case["program"], "outputs": {}, "proven": False,
            "java_failed": True, "feedback": "### The Java side did not build or run\n\n```\n" + shown + "\n```"}  # fmt: skip


# ---- --reuse: an earlier run's COBOL side and generated project ----------------------------------------------------
# Mutation testing (tests/tools/mutation.py) proves hundreds of ports of ONE case. Each would redo the same COBOL
# runs and regenerate the same estate; only the port differs. With `run --reuse EARLIER`, a COBOL step whose
# run.sh is byte-identical to the one EARLIER ran takes EARLIER's outputs instead of running (the step is
# deterministic: the same program, inputs, clock and fault plan), and the Java project is EARLIER's, re-overlaid
# with the port (the same files, or it refuses). Everything after -- reading, comparing, coverage -- is unchanged.
_REUSE: tuple[Path, Path] | None = None  # (this run's work root, the earlier run's)


def reuse(work: Path, earlier: Path) -> None:
    global _REUSE
    if not (earlier / "report.json").is_file():
        raise SystemExit(f"--reuse: {earlier} is not a finished run (no report.json)")
    _REUSE = (work.resolve(), earlier.resolve())


def reused(work: Path) -> Path | None:
    """The earlier run's directory for this run's `work`, when reusing; else None."""
    if _REUSE is None:
        return None
    root, earlier = _REUSE
    return earlier / work.resolve().relative_to(root)


def step_reused(work: Path) -> bool:
    """Whether run_cobol_step(work) will take the earlier run's outputs (--reuse, and the same run.sh)."""
    earlier = reused(work)
    script = earlier / "run.sh" if earlier is not None else None
    return script is not None and script.is_file() and script.read_bytes() == (work / "run.sh").read_bytes()


def _docker_run(work: Path, image: str, docker_args: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    # the step runs as root: what it wrote is handed back to the caller (chown), so a reused step can be
    # copied over it and the work directory removed (#4476: the copy over a root-owned pass-1 file was refused)
    owner = f"{os.getuid()}:{os.getgid()}" if hasattr(os, "getuid") else "0:0"
    keep_status = 'bash /work/run.sh; rc=$?; chown -R "$0" /work 2>/dev/null; exit $rc'
    return subprocess.run(["docker", "run", "--rm", *docker_args, "-v", f"{work}:/work", image, "bash", "-c",  # noqa: S603, S607
                           keep_status, owner], capture_output=True, text=True, check=False)  # fmt: skip


def run_cobol_step(
    work: Path, image: str = IMAGE, docker_args: tuple[str, ...] = ()
) -> subprocess.CompletedProcess[str]:
    """Run work/run.sh in the GnuCOBOL image (`image`: a Db2 case's, on `docker_args`' network) -- or, with --reuse,
    copy in what the earlier run's identical step wrote; a step the earlier run did not run (#4476: a CICS case's
    second pass, with the derived SQL-fault tasks, overwrote the first pass's run.sh) runs afresh."""
    if not step_reused(work):
        return _docker_run(work, image, docker_args)
    earlier = reused(work)
    assert earlier is not None
    shutil.copytree(earlier, work, dirs_exist_ok=True)
    return subprocess.CompletedProcess(["reuse", str(earlier)], 0, "", "")


NOT_MODELLED = "GGDISPLAY-NOT-MODELLED"  # faults/ggdisplay.c: an operand IBM's text is not modelled for


def sysout_lines(data: bytes, enc: str) -> list[str]:
    """The job log's lines as compared: trailing blanks dropped (a SYSOUT record is blank-padded to its length,
    so they are not text) and libcob's own runtime messages left out (they are GnuCOBOL's, not the program's)."""
    # #4698: records are separated by a plain LF byte on both sides whatever the charset (the separator is the
    # capture's framing, not data -- IBM's SYSOUT record has none), so split the bytes, then decode each record
    lines = [x.rstrip(" \r") for x in (r.decode(enc) for r in data.split(b"\n")) if not x.startswith("libcob: ")]
    while lines and not lines[-1]:
        lines.pop()
    return lines


def compare_sysout(cobol: bytes, java: bytes, enc: str) -> dict[str, Any]:
    """#4056: what each side DISPLAYed, line by line. Not compared (and said so) when the COBOL side DISPLAYed an
    operand ggdisplay.c does not model: GnuCOBOL's text for it is not IBM's."""
    c, j = (
        sysout_lines(cobol, enc),
        [r.decode(enc) for r in java.split(b"\n")] if java else [],
    )  # #4691: the port writes record-charset bytes (a CICS task's log too: the harness passes the data charset);
    # #4698: its records end in a plain LF byte whatever the charset, so the bytes are split before they are decoded
    j = [x.rstrip(" \r") for x in j]
    while j and not j[-1]:
        j.pop()
    if NOT_MODELLED in c:
        return {"compared": False, "why": "a DISPLAY operand IBM's text is not modelled for (faults/ggdisplay.c)",
                "lines": len(c), "equal": 0, "diffs": []}  # fmt: skip
    diffs = [{"line": i + 1, "cobol": c[i] if i < len(c) else None, "java": j[i] if i < len(j) else None}
             for i in range(max(len(c), len(j))) if (c[i] if i < len(c) else None) != (j[i] if i < len(j) else None)]  # fmt: skip
    return {"compared": True, "lines": len(c), "equal": max(len(c), len(j)) - len(diffs), "diffs": diffs[:20],
            "differing": len(diffs)}  # fmt: skip
