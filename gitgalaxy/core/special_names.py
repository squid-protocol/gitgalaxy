# ==============================================================================
# GitGalaxy Core: the SPECIAL-NAMES paragraph -- currency and decimal point (#3820)
#
# PURPOSE:
# A COBOL program can change what its PICTURE strings mean. `CURRENCY SIGN IS
# 'EUR ' WITH PICTURE SYMBOL 'U'` makes every `U` in a PIC stand for the four
# characters `EUR `, so `PIC UUU9.99` is 10 bytes, not 7. `DECIMAL-POINT IS
# COMMA` swaps the roles of `.` and `,` in PICs and numeric literals. Nothing
# recorded either, so every width after such a field was wrong. One row per
# clause (special_names_data):
#
#   clause  CURRENCY | DECIMAL-POINT
#   value   CURRENCY: the currency string, unquoted (a hex literal decoded as
#           EBCDIC CP037); DECIMAL-POINT: COMMA
#   symbol  CURRENCY: the PICTURE SYMBOL that stands for the string -- the
#           string itself when no PICTURE SYMBOL is given (it must then be one
#           character); None when it cannot be told
#   line    where the clause starts
#
# SCOPE AND NON-SCOPE:
#   - Extraction only, per file. Sizing a PIC with the declared currency strings
#     is the reader's (galaxy_ir._elementary_bytes), and so is applying a
#     program's declarations to a copybook it COPYs.
#   - Other SPECIAL-NAMES clauses (SYMBOLIC CHARACTERS, CLASS, ALPHABET,
#     mnemonic names, UPSI switches) are not read.
#   - Bounded: the paragraph is cut at the next paragraph, section or division
#     header, and capped.
# ==============================================================================
import bisect
import re
from typing import Any, Optional

_SPECIAL_NAMES = re.compile(r"(?<![A-Z0-9-])SPECIAL-NAMES[ \t]{0,20}\.", re.I)
_WS = r"[ \t\n]{1,200}"
_PARAGRAPH_END = re.compile(
    r"(?<![A-Z0-9-])(?:REPOSITORY[ \t]{0,20}\.|FILE-CONTROL[ \t]{0,20}\.|I-O-CONTROL[ \t]{0,20}\."
    r"|INPUT-OUTPUT" + _WS + "SECTION|DATA" + _WS + "DIVISION|PROCEDURE" + _WS + "DIVISION)",
    re.I,
)
_LITERAL = r"(X?'[^'\n]{1,160}'|X?\"[^\"\n]{1,160}\")"
_CURRENCY = re.compile(
    r"(?<![A-Z0-9-])CURRENCY(?:" + _WS + r"SIGN)?(?:" + _WS + r"IS)?" + _WS + _LITERAL
    + r"(?:(?:" + _WS + r"WITH)?" + _WS + r"PICTURE" + _WS + r"SYMBOL" + _WS + _LITERAL + r")?",
    re.I,
)  # fmt: skip
_DECIMAL_POINT = re.compile(r"(?<![A-Z0-9-])DECIMAL-POINT(?:" + _WS + r"IS)?" + _WS + r"COMMA(?![A-Z0-9-])", re.I)
_PARAGRAPH_LIMIT = 20000


def _unquote(literal: str) -> Optional[str]:
    """The characters a COBOL literal stands for: `'EUR '` -> `EUR `, `X'5B'` -> `$`."""
    if literal[:1] in ("X", "x"):
        hexdigits = literal[2:-1]
        try:
            return bytes.fromhex(hexdigits).decode("cp037")
        except ValueError:
            return None
    return literal[1:-1]


def special_names(code_stream: str) -> list[dict[str, Any]]:
    """The CURRENCY and DECIMAL-POINT clauses of one COBOL file, in source order."""
    rows: list[dict[str, Any]] = []
    if not code_stream:
        return rows
    newlines = [i for i, ch in enumerate(code_stream) if ch == "\n"]

    def _line_of(offset: int) -> int:
        return bisect.bisect_left(newlines, offset) + 1

    for para in _SPECIAL_NAMES.finditer(code_stream):
        end = _PARAGRAPH_END.search(code_stream, para.end())
        stop = min(end.start() if end else len(code_stream), para.end() + _PARAGRAPH_LIMIT)
        found: list[tuple[int, dict[str, Any]]] = []
        for m in _CURRENCY.finditer(code_stream, para.end(), stop):
            value = _unquote(m.group(1))
            symbol = _unquote(m.group(2)) if m.group(2) else (value if value and len(value) == 1 else None)
            found.append((m.start(), {"clause": "CURRENCY", "value": value, "symbol": symbol}))
        found.extend(
            (m.start(), {"clause": "DECIMAL-POINT", "value": "COMMA", "symbol": None})
            for m in _DECIMAL_POINT.finditer(code_stream, para.end(), stop)
        )
        rows.extend({**row, "line": _line_of(start)} for start, row in sorted(found, key=lambda x: x[0]))
    return rows
