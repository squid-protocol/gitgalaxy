"""#8412: the REPLACE statement (`REPLACE ==a== BY ==b==.` / `REPLACE OFF.`) applied to the det reader's logical lines.

IBM Enterprise COBOL (Language Reference, "REPLACE statement"): the statement rewrites the source text that follows it,
after COPY ... REPLACING has run, until the next REPLACE statement or `REPLACE OFF`; its operands are pseudo-text only;
the statement itself is not part of the program. Matching reuses the COPY REPLACING rule (core.cobol_preprocessor.
replace_text: whole words, a `:TAG:` operand partial words, one left-to-right pass, replaced text never matched again),
applied outside literals (a literal is one text-word and is not matched inside).

What is NOT read stays refused by name, never translated unreplaced: a multi-word pseudo-text operand (its match can
span a line break), an empty one, a non-pseudo-text operand, a REPLACE that does not start its line, a statement with no
period, and a REPLACE still in effect at `END PROGRAM` (its scope across programs is not read)."""

from __future__ import annotations

import re

from gitgalaxy.core.cobol_preprocessor import replace_text, statement_end

_STATEMENT = re.compile(r"\s*REPLACE(?:\s|$)", re.I)  # no other COBOL statement starts with the word
_OFF = re.compile(r"\s*REPLACE\s+OFF\s*", re.I)
_PAIR = re.compile(r"\s*==(.*?)==\s*BY\s*==(.*?)==", re.I | re.S)
_MID_LINE = re.compile(r"\.\s+REPLACE\s+(?:OFF\b|==)", re.I)
_END_PROGRAM = re.compile(r"\s*END\s+PROGRAM\b", re.I)
_LITERAL = re.compile(r"""('[^']*(?:''[^']*)*'|"[^"]*(?:""[^"]*)*"|'[^']*$|"[^"]*$)""")


class ReplaceStatementRefused(ValueError):
    """#8412: a REPLACE statement (`REPLACE ==A== BY ==B==.` / `REPLACE OFF.`) this reader does not apply."""


def is_statement(text: str) -> bool:
    return _STATEMENT.match(text) is not None


def _refuse(ln, why: str) -> ReplaceStatementRefused:
    from pathlib import Path

    return ReplaceStatementRefused(
        f"{Path(ln.file).name}:{ln.line}: the REPLACE statement is not read ({why}; refused by name)"
    )


def _pairs(ln, body: str) -> list[list[str]]:
    pairs: list[list[str]] = []
    pos = len("REPLACE")
    while pos < len(body.rstrip()):
        m = _PAIR.match(body, pos)
        if not m:
            raise _refuse(ln, "an operand is not ==pseudo-text== BY ==pseudo-text==")
        src, dst = " ".join(m.group(1).split()), " ".join(m.group(2).split())
        if not src:
            raise _refuse(ln, "an empty pseudo-text operand")
        if " " in src:
            raise _refuse(ln, f"the multi-word pseudo-text =={src}== can span a line break and is not matched")
        pairs.append([src, dst])
        pos = m.end()
    if not pairs:
        raise _refuse(ln, "no operand")
    return pairs


def _apply(text: str, pairs: list[list[str]]) -> str:
    return "".join(seg if k % 2 else (replace_text(seg, pairs) or seg) for k, seg in enumerate(_LITERAL.split(text)))


def apply(lines: list) -> list:
    """`lines` (the program, COPY members expanded) with each REPLACE statement applied to the text after it and removed."""
    out: list = []
    pairs: list[list[str]] | None = None
    i = 0
    while i < len(lines):
        ln = lines[i]
        if is_statement(ln.text):
            stmt, j = ln.text.strip(), i
            while statement_end(stmt, 0) < 0 and j + 1 < len(lines):
                j += 1
                stmt += " " + lines[j].text.strip()
            end = statement_end(stmt, 0)
            if end < 0:
                raise _refuse(ln, "no period ends it")
            body, tail = stmt[: end - 1], stmt[end:].strip()
            pairs = None if _OFF.fullmatch(body) else _pairs(ln, body)
            i = j + 1
            if tail:  # what follows the statement's period on its line is read on, under the new REPLACE
                lines = [*lines[:i], type(ln)(tail, ln.file, lines[j].line), *lines[i:]]
            continue
        if _MID_LINE.search(_outside(ln.text)):
            raise _refuse(ln, "it does not start its line")
        if pairs:
            if _END_PROGRAM.match(ln.text):
                raise _refuse(ln, "a REPLACE is still in effect at END PROGRAM; its scope across programs is not read")
            ln.text = _apply(ln.text, pairs)
            if not ln.text.strip():
                i += 1
                continue
        out.append(ln)
        i += 1
    return out


def _outside(text: str) -> str:
    return "".join("" if k % 2 else seg for k, seg in enumerate(_LITERAL.split(text)))
