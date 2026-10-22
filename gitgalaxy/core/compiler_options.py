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
from typing import Any

# IBM Enterprise COBOL option abbreviations -> the full name (Programming Guide, "Compiler options").
_ABBREVIATIONS = {
    "AR": "ARITH", "BUF": "BUFSIZE", "C": "COMPILE", "CP": "CODEPAGE", "CURR": "CURRENCY", "D": "DECK",
    "DEF": "DEFINE", "DP": "DATEPROC", "DS": "DISPSIGN", "DTR": "DIAGTRUNC", "DU": "DUMP", "DYN": "DYNAM",
    "EX": "EXIT", "EXP": "EXPORTALL", "F": "FLAG", "FSRT": "FASTSRT", "IC": "INITCHECK", "INVD": "INVDATA", "LANG": "LANGUAGE",
    "LC": "LINECOUNT", "MD": "MDECK", "NC": "NUMCHECK", "NS": "NSYMBOL", "NUM": "NUMBER", "OBJ": "OBJECT",
    "OFF": "OFFSET", "OPT": "OPTIMIZE", "OUT": "OUTDD", "PC": "PARMCHECK", "PGMN": "PGMNAME", "Q": "QUOTE",
    "S": "SOURCE", "SEQ": "SEQUENCE", "SERV": "SERVICE", "SO": "STGOPT", "SQLC": "SQLCCSID", "SSR": "SSRANGE",
    "TERM": "TERMINAL", "WD": "WORD", "X": "XREF", "XP": "XMLPARSE", "YW": "YEARWINDOW", "ZD": "ZONEDATA",
}  # fmt: skip
# Sub-option abbreviations that change no meaning but would otherwise read differently.
_VALUE_ABBREVIATIONS = {
    "ARITH": {"C": "COMPAT", "E": "EXTEND"},
    "DISPSIGN": {"C": "COMPAT", "S": "SEP"},
    "NSYMBOL": {"NAT": "NATIONAL"},
}
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


def canonical(name: str, value: str | None = None) -> tuple[str, str | None]:
    """(full option name, value) of one option: `AR`, `E` -> ARITH, EXTEND; `NOCURR` -> NOCURRENCY."""
    up = name.upper()
    if up in _ABBREVIATIONS:
        up = _ABBREVIATIONS[up]
    elif up.startswith("NO") and up[2:] in _ABBREVIATIONS:
        up = "NO" + _ABBREVIATIONS[up[2:]]
    if value is not None:
        value = _VALUE_ABBREVIATIONS.get(up, {}).get(value.strip().upper(), value.strip())
    return up, value


def parse_options(text: str) -> list[tuple[str, str | None, str]]:
    """[(option, value, as written)] of one card's option list: comma- or space-separated,
    a parenthesised value kept whole (quotes and nested parentheses included)."""
    out: list[tuple[str, str | None, str]] = []
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


def effective(rows: list[dict[str, Any]]) -> dict[str, str | None]:
    """{option: value} as the compiler applies them: the last card wins, a NO- form cancels its option."""
    out: dict[str, str | None] = {}
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


# ---- the options that change results and are not SEMANTIC_OPTIONS (#4706) -------------------------------------------------
# One row per option the table of docs/language_status/register/C5.md lists. `policy` says what a value the harness cannot
# honour becomes: "refuse" (UnsupportedOption by name, nothing is proven) or "declare" (proven under `applied`, a declared
# difference in the evidence record, as TRUNC(OPT) before the det stop); None: the option changes no defined result.
# `honoured` lists the values (upper case) the proof runs as IBM does; a "flag" option (SSRANGE ...) is honoured when off.
# Citations are Enterprise COBOL for z/OS 6.x Programming Guide, "Compiler options" (the option's own section).
OPTION_TABLE: dict[str, dict[str, Any]] = {
    "ZONEDATA": {"kind": "value", "default": "PFD", "honoured": ("PFD",), "policy": "refuse",
                 "reason": "ZONEDATA(NOPFD|MIG) defines what invalid zone bits / digits do in MOVE, compare and arithmetic "
                           "(APAR PI57769); no source states the results, and GnuCOBOL's are a guess"},
    "INVDATA": {"kind": "flag", "default": "NOINVDATA", "honoured": (), "policy": "refuse",
                "reason": "INVDATA (INVD(FNC|NOFNC,CS|NOCS)) supersedes ZONEDATA: it defines what invalid DISPLAY / "
                          "PACKED-DECIMAL data does; the harness models none of it"},
    "CODEPAGE": {"kind": "value", "default": "1140", "honoured": ("1140", "37"), "policy": "declare",
                 "reason": "CODEPAGE(ccsid) sets the CCSID of compile-time and runtime character conversion (literals, "
                           "collating, national <-> alphanumeric); the proof runs data in the case's data_encoding"},
    "NSYMBOL": {"kind": "value", "default": "NATIONAL", "honoured": ("NATIONAL",), "policy": "refuse",
                "reason": "NSYMBOL(DBCS) makes N literals and PIC N DBCS, not national; national / DBCS text is refused "
                          "by name already (#4272)"},
    "DISPSIGN": {"kind": "value", "default": "COMPAT", "honoured": ("COMPAT",), "policy": "refuse",
                 "reason": "DISPSIGN(SEP) changes how DISPLAY shows a signed numeric item; the harness models COMPAT only"},
    "FLOAT": {"kind": "value", "default": "HEX", "honoured": ("HEX", "S390"), "policy": "refuse",
              "reason": "FLOAT(NATIVE) is IEEE binary floating point; the det port models IBM hexadecimal floating point "
                        "(register C6)"},
    "AFP": {"kind": "value", "default": "NOVOLATILE", "honoured": None, "policy": None,
            "reason": "AFP only decides which floating-point registers the code uses, not a defined result"},
    "SSRANGE": {"kind": "flag", "default": "NOSSRANGE", "honoured": (), "policy": "declare", "applied": "NOSSRANGE",
                "reason": "SSRANGE aborts the run on an out-of-range subscript / reference modification; a run with none "
                          "computes as NOSSRANGE, and an out-of-range one is undefined under NOSSRANGE"},
    "NUMCHECK": {"kind": "flag", "default": "NONUMCHECK", "honoured": (), "policy": "declare", "applied": "NONUMCHECK",
                 "reason": "NUMCHECK aborts or messages on invalid numeric data in a sending item; a run with none "
                           "computes as NONUMCHECK"},
    "INITCHECK": {"kind": "flag", "default": "NOINITCHECK", "honoured": None, "policy": None,
                  "reason": "INITCHECK only warns at compile time about uninitialised items: no run result changes"},
    "NOZWB": {"kind": "flag", "default": "ZWB", "honoured": (), "policy": "refuse",
              "reason": "NOZWB moves the signed value of a zoned DISPLAY operand into the temporary item of a numeric-vs-"
                        "nonnumeric comparison, where ZWB (IBM's default) moves the unsigned value (Language Reference, "
                        "General relation conditions; Programming Guide, ZWB); the det port and the oracle compare unsigned"},
    "OPTIMIZE": {"kind": "value", "default": "0", "honoured": None, "policy": None,
                 "reason": "OPTIMIZE(0|1|2|STD|FULL) changes run time and storage, not a defined result; a zero divisor without ON SIZE "
                           "ERROR is undefined on IBM at every level, and the harness follows cobc there whatever the level (C14)"},
}  # fmt: skip
# Options of SEMANTIC_OPTIONS: the oracle's cobc flags (equivalence_common.COBC_OPTIONS) decide them, not this table.
COBC_DECIDED_OPTIONS = ("ARITH", "INTDATE", "NUMPROC", "TRUNC")


def result_option_state(eff: dict[str, str | None], option: str) -> str | None:
    """The value of a OPTION_TABLE option in `eff` (effective_with_defaults), as the table compares it: a "value"
    option's value, upper case (its default when unnamed); a "flag" option's text when on (`SSRANGE(ZLEN)`), else None."""
    row = OPTION_TABLE[option]
    if row["kind"] == "flag":
        if option not in eff:
            return None
        return f"{option}({eff[option]})" if eff[option] not in (None, "") else option
    return str(eff.get(option) or row["default"]).strip().upper()


def unhonoured(eff: dict[str, str | None], code_page: str | None = None) -> list[dict[str, Any]]:
    """The OPTION_TABLE in force (`eff`: effective_with_defaults) whose value the harness cannot honour, in table order:
    [{option, declared, policy, applied, note}] -- `policy` "refuse" or "declare". `code_page` is the CCSID of the
    case's data (None: not a CCSID page); CODEPAGE(n) is honoured only for the IBM default or that CCSID."""
    out = []
    for option, row in OPTION_TABLE.items():
        state = result_option_state(eff, option)
        if row["policy"] is None or state is None:
            continue
        if row["kind"] == "value" and (state in row["honoured"] or (option == "CODEPAGE" and state == code_page)):
            continue
        if option == "CODEPAGE":
            applied = (
                f"data in code page {code_page}" if code_page else "data in the case's data_encoding (no CCSID page)"
            )
        else:
            applied = row.get("applied") or row["default"]
        out.append({"option": option, "declared": state, "policy": row["policy"], "applied": applied,
                    "note": f"{state if row['kind'] == 'flag' else f'{option}({state})'}: {row['reason']}"})  # fmt: skip
    return out


# ---- the compiler version bounds which options exist (#4704) -------------------------------------------------------------
# First Enterprise COBOL for z/OS release that has the option (Programming Guide, "Compiler options": each option's
# section names the release it came in). Only the options whose release is certain are listed; an option not listed is
# never reported. A program whose estate states an older compiler cannot have been compiled under such an option, so the
# value is an assumption that contradicts the stated version, not a finding.
OPTION_SINCE: dict[str, tuple[int, int]] = {"NUMCHECK": (6, 3), "INVDATA": (6, 4)}


def version_tuple(version: Any) -> tuple[int, int] | None:
    """(major, minor) of a version text (`6.1`, `V6.3.0`, `4.2`); None when it names none."""
    m = re.match(r"\s*[Vv]?(\d+)(?:\.(\d+))?", str(version or ""))
    return (int(m.group(1)), int(m.group(2) or 0)) if m else None


def not_in_version(eff: dict[str, str | None], version: Any) -> list[dict[str, Any]]:
    """[{option, since, version}] of the options in `eff` that the stated compiler `version` does not have, in
    OPTION_SINCE order. A NO- form counts as the option; an unstated or unparsable version reports nothing."""
    have = version_tuple(version)
    if have is None:
        return []
    named = {o[2:] if o.startswith("NO") and o[2:] in OPTION_SINCE else o for o in eff}
    return [
        {"option": o, "since": ".".join(map(str, since)), "version": str(version)}
        for o, since in OPTION_SINCE.items()
        if o in named and have < since
    ]
