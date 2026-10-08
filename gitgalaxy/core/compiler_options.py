# ==============================================================================
# GitGalaxy Core: CBL / PROCESS compiler-option cards (#3828)
#
# PURPOSE:
# A COBOL program can carry its own compiler options on `CBL` / `PROCESS` cards
# ahead of the IDENTIFICATION DIVISION, and some of them change what the program
# computes: INTDATE(LILIAN) moves day 1 of FUNCTION INTEGER-OF-DATE /
# DATE-OF-INTEGER from 1601-01-01 (ANSI, the default) to 1582-10-15; TRUNC(BIN)
# stops binary items truncating to their PICTURE; ARITH(EXTEND) widens
# intermediates to 31 digits; NUMPROC(PFD) trusts signs. Nothing read them. One
# row per option, in source order (compiler_options_data):
#
#   option   the option's full name, upper case (`AR` -> ARITH, `YW` ->
#            YEARWINDOW, `NOCURR` -> NOCURRENCY); a NO- form stays NO-
#   value    what is between its parentheses, as written (`LILIAN`, `'SP,EDF'`),
#            ARITH's `C` / `E` spelled out; None when it has none
#   written  the option as written on the card (`AR(E)`)
#   line     the card's line
#
# SCOPE AND NON-SCOPE:
#   - Extraction only, per file. A card counts where the compiler reads one: in
#     the leading block of the file (blank and comment lines aside), or after an
#     END PROGRAM before the next program of a batch compile -- so a PERFORM
#     continued onto a line that starts `PROCESS THRU ...` is never a card.
#   - Options given outside the source (the compile step's PARM, an installation
#     default module, an OPTFILE) are not seen: a program without cards is not
#     "compiled with the defaults", only "states none".
#   - Columns 73-80 (the identification area) are not part of a card.
# ==============================================================================
import re
from typing import Any, Optional

# IBM Enterprise COBOL option abbreviations -> the full name (Programming Guide, "Compiler options").
_ABBREVIATIONS = {
    "AR": "ARITH", "BUF": "BUFSIZE", "C": "COMPILE", "CP": "CODEPAGE", "CURR": "CURRENCY", "D": "DECK",
    "DEF": "DEFINE", "DP": "DATEPROC", "DS": "DISPSIGN", "DTR": "DIAGTRUNC", "DU": "DUMP", "DYN": "DYNAM",
    "EX": "EXIT", "EXP": "EXPORTALL", "F": "FLAG", "FSRT": "FASTSRT", "IC": "INITCHECK", "LANG": "LANGUAGE",
    "LC": "LINECOUNT", "MD": "MDECK", "NC": "NUMCHECK", "NS": "NSYMBOL", "NUM": "NUMBER", "OBJ": "OBJECT",
    "OFF": "OFFSET", "OPT": "OPTIMIZE", "OUT": "OUTDD", "PC": "PARMCHECK", "PGMN": "PGMNAME", "Q": "QUOTE",
    "S": "SOURCE", "SEQ": "SEQUENCE", "SERV": "SERVICE", "SO": "STGOPT", "SQLC": "SQLCCSID", "SSR": "SSRANGE",
    "TERM": "TERMINAL", "WD": "WORD", "X": "XREF", "XP": "XMLPARSE", "YW": "YEARWINDOW", "ZD": "ZONEDATA",
}  # fmt: skip
# Sub-option abbreviations that change no meaning but would otherwise read differently.
_VALUE_ABBREVIATIONS = {"ARITH": {"C": "COMPAT", "E": "EXTEND"}}
_CARD = re.compile(r"^(?:[0-9]{6})?[ \t]*(CBL|PROCESS)(?=[ \t,]|$)", re.I)
_PROGRAM_END = re.compile(r"(?<![A-Z0-9-])END[ \t]+PROGRAM\b", re.I)
_NAME = re.compile(r"[A-Z][A-Z0-9-]*", re.I)
# The options that change what a program computes (the rest shape listings, code or linkage).
SEMANTIC_OPTIONS = ("ARITH", "INTDATE", "NUMPROC", "TRUNC", "YEARWINDOW")
DEFAULTS = {"ARITH": "COMPAT", "INTDATE": "ANSI", "NUMPROC": "NOPFD", "TRUNC": "STD"}


def _is_filler(line: str) -> bool:
    """A line that neither is a card nor ends the card block: blank, a comment, a `>>` directive."""
    body = line.strip()
    if not body or body.startswith(("*>", ">>")) or line[:1] in ("*", "/"):
        return True
    return len(line) >= 7 and line[6] in ("*", "/") and not line[:6].strip(" 0123456789")


def canonical(name: str, value: Optional[str] = None) -> tuple[str, Optional[str]]:
    """(full option name, value) of one option: `AR`, `E` -> ARITH, EXTEND; `NOCURR` -> NOCURRENCY."""
    up = name.upper()
    if up in _ABBREVIATIONS:
        up = _ABBREVIATIONS[up]
    elif up.startswith("NO") and up[2:] in _ABBREVIATIONS:
        up = "NO" + _ABBREVIATIONS[up[2:]]
    if value is not None:
        value = _VALUE_ABBREVIATIONS.get(up, {}).get(value.strip().upper(), value.strip())
    return up, value


def parse_options(text: str) -> list[tuple[str, Optional[str], str]]:
    """[(option, value, as written)] of one card's option list: comma- or space-separated,
    a parenthesised value kept whole (quotes and nested parentheses included)."""
    out: list[tuple[str, Optional[str], str]] = []
    i, n = 0, len(text)
    while i < n:
        if text[i] in " \t,":
            i += 1
            continue
        m = _NAME.match(text, i)
        if not m:  # a stray character (a closing period, a quote): skip it
            i += 1
            continue
        j = m.end()
        k = j
        while k < n and text[k] in " \t":
            k += 1
        value = None
        if k < n and text[k] == "(":
            depth, q, quote = 0, k, ""
            while q < n:
                ch = text[q]
                if quote:
                    quote = "" if ch == quote else quote
                elif ch in "'\"":
                    quote = ch
                elif ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if not depth:
                        break
                q += 1
            value = text[k + 1 : q]
            j = min(q + 1, n)
        name, value = canonical(m.group(0), value)
        out.append((name, value, text[i:j].strip()))
        i = j
    return out


def cards(code_stream: str) -> list[tuple[int, str]]:
    """[(line, option list)] of each CBL / PROCESS card the compiler reads, in source order."""
    out: list[tuple[int, str]] = []
    if not code_stream or not re.search(r"CBL|PROCESS", code_stream, re.I):
        return out
    in_block = True
    for number, raw in enumerate(code_stream.split("\n"), 1):
        line = raw[:72].rstrip("\r")
        if in_block:
            card = _CARD.match(line)
            if card:
                out.append((number, line[card.end() :]))
                continue
            if _is_filler(line):
                continue
            in_block = False
        if _PROGRAM_END.search(line):
            in_block = True
    return out


def compiler_options(code_stream: str) -> list[dict[str, Any]]:
    """The CBL / PROCESS options of one COBOL file, in source order."""
    return [
        {"option": option, "value": value, "written": written, "line": number}
        for number, text in cards(code_stream)
        for option, value, written in parse_options(text)
    ]


def effective(rows: list[dict[str, Any]]) -> dict[str, Optional[str]]:
    """{option: value} as the compiler applies them: the last card wins, a NO- form cancels its option."""
    out: dict[str, Optional[str]] = {}
    for r in rows:
        opt = str(r.get("option") or "")
        out.pop(opt[2:] if opt.startswith("NO") else "NO" + opt, None)
        out[opt] = r.get("value")
    return out


def intdate(rows: list[dict[str, Any]]) -> str:
    """ANSI or LILIAN: day 1 of INTEGER-OF-DATE / DATE-OF-INTEGER is 1601-01-01 or 1582-10-15."""
    return str(effective(rows).get("INTDATE") or DEFAULTS["INTDATE"]).upper()


def rows_of(options: Any) -> list[dict[str, Any]]:
    """Option rows of a PARM-level option list (`["INTDATE(LILIAN)", "TRUNC(BIN),NUMPROC(PFD)"]`): the compile step's
    PARM, or an estate's layers over it (#4704). None or [] is no options."""
    return [{"option": o, "value": v} for text in options or [] for o, v, _ in parse_options(text)]


def effective_with_defaults(options: Any, source_text: str = "") -> dict[str, str | None]:
    """{option: value} the compiler applies to one program (#4704), IBM's precedence order, lowest first: the options
    in force before the source (`options`: installation defaults, then the compile step's PARM -- gitgalaxy.core.
    estate_options builds that list), then the program's own CBL / PROCESS cards (Enterprise COBOL for z/OS
    Programming Guide, "Compiler options": "Specifying compiler options under z/OS" -- PROCESS / CBL statements
    override the PARM, which overrides the installation defaults). An option nothing names is IBM's default
    (DEFAULTS; #4102: TRUNC(STD)). The one place the oracle's cobc flags and the det port read their options from."""
    eff = effective(rows_of(options) + compiler_options(source_text))
    for option, default in DEFAULTS.items():
        eff.setdefault(option, default)
    return eff
