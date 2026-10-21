# ==============================================================================
# GitGalaxy Core: the COBOL text-level front end shared by the scanner and the translator (#5648)
# ==============================================================================
"""
The scanner (mainframe_boundary, galaxy_ir) and the COBOL->Java translator (det/source.py) both turn a COBOL
file into the text the compiler sees. Each kept its own rules for it, so the fact cross-check (#4273) could
catch them disagreeing but not sharing a blind spot: both missed `COPY "ws-state.cpy".` (#5618, #5645). The
rules live here once, zero-dependency (no tree-sitter), and both sides import them:

    COPY_STATEMENT  `COPY text-name [OF|IN library-name]`: the text-name unquoted, quoted, or a quoted file
                    literal with its extension (`COPY "ws-state.cpy".`, GnuCOBOL); copy_statements()
    statement_end   where the COPY statement's separator period is (not one inside pseudo-text or a literal)
    copy_replacing  the REPLACING phrase's operand pairs (pseudo-text, words, literals, LEADING / TRAILING)
    replace_text    one left-to-right REPLACING pass over a text, as the compiler applies it
    continuation_resume / continued_literal / join_continuation
                    a continued nonnumeric literal: where it resumes, its whole value, and one continuation
                    line joined onto the logical line before it
    open_literal / comment_at / drop_comment / free_code
                    a floating `*>` comment (free format, and IBM Enterprise COBOL 6 / GnuCOBOL in fixed form
                    too) is a comment only outside a literal: where it starts and the text without it
    join_copy_alone / gather_copy / sql_include_as_copy
                    a COPY statement spread over lines (`COPY` ending a line, its member on the next; the
                    statement running on to its period) and `EXEC SQL INCLUDE member END-EXEC` read as `COPY member.`
    MappedLine / line_map
                    one expanded line with the file and line it came from (a COPY member's own line, not a
                    line of the expanded text), and the map of a whole expansion: findings and generated
                    code point at `CUSTREC.cpy:12`

Member resolution stays in core/copy_libraries.py (the engine owns it since #4468).
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from gitgalaxy.standards.language_standards.identifiers import NATIONAL, WIDE_DIGITS, WIDE_HYPHENS

_SP = r"[ \t\n　]+"
# a text-name / library-name: COBOL word characters, national letters included (estate-crucible NORD
# `COPY KUNDEÅ.`, read in cp277); never starting with a hyphen
_NAME_START = "A-Z" + NATIONAL + WIDE_DIGITS + "0-9@#$"
_NAME_CHAR = _NAME_START + WIDE_HYPHENS + "-"
_NAME = "[" + _NAME_START + "][" + _NAME_CHAR + "]*"
# #5645 / #5618: a quoted literal may carry the copybook file's extension (`"ws-state.cpy"`, GnuCOBOL); the
# member is the stem, and the `OF|IN` / `REPLACING` after the closing quote still parse
COPY_STATEMENT = re.compile(
    "(?<![" + _NAME_CHAR + "])COPY" + _SP
    + "(?:(['\"])(" + _NAME + r")(?:\.([A-Z0-9_-]+))?\1|(" + _NAME + "))"
    + "(?:" + _SP + "(?:OF|IN)" + _SP + "(['\"]?)(" + _NAME + r")\5)?",
    re.I,
)  # fmt: skip
# #3355 / #4278: the scanner's head scan -- `COPY member` or `EXEC SQL INCLUDE member` (which expands in place the same
# way); group 1 is the member (a quoted file literal's extension, closed by its quote, left off). The library and the
# REPLACING phrase are read from where it ends (COPY_LIBRARY, copy_replacing), so a COPY whose closing quote is
# missing still names its member.
COPY_OR_INCLUDE_HEAD = re.compile(
    "(?<![" + _NAME_CHAR + "])(?:COPY|EXEC" + _SP + "SQL" + _SP + "INCLUDE)" + _SP
    + "['\"]?(" + _NAME + r")(?:\.[\w-]+(?=['\"]))?",
    re.I,
)  # fmt: skip
# #4265: the `IN|OF library-name` after a COPY's text-name (closing quote allowed), matched at the head's end.
COPY_LIBRARY = re.compile(
    "['\"]?" + _SP + "(?:IN|OF)" + _SP + "['\"]?(" + _NAME + ")",
    re.I,
)  # fmt: skip
# #4459: a COPY ending its line, its text-name on the next
COPY_ALONE = re.compile("(?<![" + _NAME_CHAR + r"])COPY\s*$", re.I)


@dataclass(frozen=True)
class CopyStatement:
    """One `COPY text-name [OF|IN library-name]` in a text: `start` its COPY, `end` just past the text-name (its
    closing quote) and library-name. `member` is upper case, a file literal's extension left off (the member the
    libraries are searched for); `file_name` is that literal as written (`ws-state.cpy`), "" for any other form.
    `library` is upper case, "" when none is named."""

    start: int
    end: int
    member: str
    file_name: str
    library: str


def copy_statements(text: str, pos: int = 0) -> Iterator[CopyStatement]:
    """Each COPY statement head in `text` from `pos`, in order (a caller skips one inside a literal)."""
    for m in COPY_STATEMENT.finditer(text, pos):
        quoted = m.group(2) is not None
        name = m.group(2) if quoted else m.group(4)
        yield CopyStatement(
            m.start(),
            m.end(),
            name.upper(),
            f"{name}.{m.group(3)}" if quoted and m.group(3) else "",
            (m.group(6) or "").upper(),
        )


def statement_end(stmt: str, start: int) -> int:
    """Index just past the period that ends the COPY statement beginning at `start` (-1: not ended yet); a period
    inside ==pseudo-text== or a literal does not end it."""
    quote, pseudo, k = None, False, start
    while k < len(stmt):
        ch = stmt[k]
        if pseudo:
            if stmt.startswith("==", k):
                pseudo, k = False, k + 1
        elif quote:
            quote = None if ch == quote else quote
        elif stmt.startswith("==", k):
            pseudo, k = True, k + 1
        elif ch in "'\"":
            quote = ch
        elif ch == "." and (k + 1 == len(stmt) or stmt[k + 1].isspace()):
            return k + 1
        k += 1
    return -1


# #4265: `REPLACING operand BY operand ...` after a COPY's text-name (and library): each operand is
# ==pseudo-text== or a single word / literal. Read up to the statement's separator period.
_COPY_REPLACING_HEAD = re.compile(
    r"['\"]?(?:[ \t\n　]+(?:IN|OF)[ \t\n　]+['\"]?[^\s.'\"]+['\"]?)?[ \t\n　]+REPLACING(?![\w-])", re.I
)
_REPLACING_OPERAND = r"==(.*?)==|('[^'\n]*'|\"[^\"\n]*\"|[^\s.=]+(?:\.[^\s.=]+)*)"
_REPLACING_PAIR = re.compile(
    r"[ \t\n　]+(?:(LEADING|TRAILING)[ \t\n　]+)?(?:"
    + _REPLACING_OPERAND
    + r")[ \t\n　]+BY[ \t\n　]+(?:"
    + _REPLACING_OPERAND
    + r")",
    re.I | re.S,
)


def copy_replacing(text: str, at: int) -> list[list[str]] | None:
    """#4265: the [from, to] pairs of the REPLACING phrase of the COPY whose text-name ends at `at` -- a
    third element LEADING / TRAILING when the phrase says so (partial-word replacement). An operand's
    separators are one space each. None when the COPY replaces nothing."""
    head = _COPY_REPLACING_HEAD.match(text, at)
    if not head:
        return None
    pairs: list[list[str]] = []
    pos = head.end()
    while len(pairs) < 50:
        m = _REPLACING_PAIR.match(text, pos)
        if not m:
            break
        mode, src = m.group(1), (m.group(2) if m.group(2) is not None else m.group(3))
        dst = m.group(4) if m.group(4) is not None else (m.group(5) or "")
        pair = [" ".join(src.split()), " ".join(dst.split())]
        pairs.append([*pair, mode.upper()] if mode else pair)
        pos = m.end()
    return pairs or None


def replace_text(text: str | None, pairs: list) -> str | None:
    """#4265: `text` after a COPY's REPLACING. A pseudo-text operand delimited by `:` or `( )` (a
    tag: `:TAG:-ID`) replaces partial words; LEADING / TRAILING replace a word's start / end; any
    other operand replaces whole words only. One left-to-right pass, as the compiler does: at each
    position the first pair that matches is applied, and replaced text is never matched again."""
    if not text:
        return text
    patterns: list[str] = []
    targets: list[str] = []
    for pair in pairs:
        src, dst = pair[0], pair[1]
        mode = pair[2] if len(pair) > 2 else None
        if not src:
            continue
        if mode == "LEADING":
            patterns.append(rf"(?<![\w-]){re.escape(src)}")
        elif mode == "TRAILING":
            patterns.append(rf"{re.escape(src)}(?![\w-])")
        elif src[:1] in ":(" and src[-1:] in ":)":
            patterns.append(re.escape(src))
        else:
            patterns.append(rf"(?<![\w-]){re.escape(src)}(?![\w-])")
        targets.append(dst)
    if not patterns:
        return text
    combined = re.compile("|".join(f"(?P<p{i}>{p})" for i, p in enumerate(patterns)), re.I)
    return combined.sub(lambda m: targets[int((m.lastgroup or "p0")[1:])], text)



def join_copy_alone(texts: list[str], i: int) -> str | None:
    """#4459: line `i` with the next line's text joined on when it ends in a bare `COPY` (its member is on the next
    line), or None when it does not."""
    text = texts[i]
    if COPY_ALONE.search(text) and not open_literal(text) and i + 1 < len(texts):
        return text.rstrip() + " " + texts[i + 1].lstrip()
    return None


def gather_copy(texts: list[str], i: int, start: int) -> tuple[str, int]:
    """The COPY statement beginning at `start` of line `i`, joined over as many following lines as it takes to reach
    its period: (the text from line `i` on, index of the last line used)."""
    stmt, j = texts[i], i
    end = statement_end(stmt, start)
    while end < 0 and j + 1 < len(texts):
        j += 1
        stmt += " " + texts[j]
        end = statement_end(stmt, start)
    return stmt, j


_SQL_INCLUDE = re.compile(r"\s*EXEC\s+SQL\s+INCLUDE\s+([A-Z0-9#@$-]+)\s+END-EXEC\s*\.?\s*$", re.I)


def sql_include_as_copy(texts: list[str], i: int) -> tuple[str, int] | None:
    """`EXEC SQL INCLUDE member END-EXEC` starting at line `i` is a COPY of the member (Db2's precompiler includes it the
    same way): (`COPY member.`, index of the block's last line), or None for any other EXEC SQL block."""
    if not re.match(r"\s*EXEC\s+SQL\b", texts[i], re.I):
        return None
    j, block = i, texts[i]
    while not re.search(r"\bEND-EXEC\b", block, re.I) and j + 1 < len(texts):
        j += 1
        block += " " + texts[j]
    inc = _SQL_INCLUDE.match(block)
    return (f"COPY {inc.group(1)}.", j) if inc else None

def continuation_resume(line: str, quote: str | None = None) -> int | None:
    """#5648: where a continued nonnumeric literal resumes on a continuation line (indicator `-` in column 7): the
    offset just past the first quote in the program-text area (columns 8-72), which must be the first nonblank
    there (Enterprise COBOL LR, "Continuation lines"). `quote` is the quote the literal opened with; None accepts
    either. None when the line does not resume a literal (no quote, text before it, a quote at or past column 72,
    or the other quote)."""
    area = line[7:72]
    body = area.lstrip(" ")
    if not body or body[0] not in ("'", '"') or (quote is not None and body[0] != quote):
        return None
    return 7 + len(area) - len(body) + 1


def continued_literal(code_stream: str, open_at: int) -> str | None:
    """#4391, #5648: the value of the nonnumeric literal whose opening quote is at `open_at` when it is
    continued (Enterprise COBOL LR, "Continuation lines"): its first line's characters after the
    quote through column 72, then each continuation line's (`-` in column 7) characters after its
    first quote -- through column 72 again, until a line closes the literal. None when the source is
    not that shape (a free-format literal, a missing indicator): the raw text is then kept."""
    quote = code_stream[open_at]
    line_start = code_stream.rfind("\n", 0, open_at) + 1
    col = open_at - line_start
    if col >= 72:
        return None
    line_end = code_stream.find("\n", open_at)
    line = code_stream[line_start : line_end if line_end != -1 else len(code_stream)]
    parts = [line[col + 1 : 72].ljust(72 - col - 1)]
    pos = line_end
    for _ in range(50):  # a literal is at most 160 characters; bounded either way
        if pos == -1:
            return None
        nxt_end = code_stream.find("\n", pos + 1)
        nxt = code_stream[pos + 1 : nxt_end if nxt_end != -1 else len(code_stream)]
        if len(nxt) < 8 or nxt[6] != "-":
            return None
        resume = continuation_resume(nxt, quote)
        if resume is None:
            return None
        resume -= 1
        close = nxt.find(quote, resume + 1)
        while close != -1 and close + 1 < len(nxt) and nxt[close + 1] == quote:  # a doubled quote
            close = nxt.find(quote, close + 2)
        if close != -1 and close < 72:
            parts.append(nxt[resume + 1 : close])
            return "".join(parts)
        parts.append(nxt[resume + 1 : 72].ljust(72 - resume - 1))
        pos = nxt_end
    return None


def join_continuation(prev_text: str, line: str, literal_open: bool) -> str:
    """#5648: the logical line `prev_text` (columns 8-72 of the line before) with the continuation `line`
    (indicator `-`) joined on. An open literal ran to column 72 (its trailing spaces are part of it) and resumes
    after the continuation's first quote; any other continuation joins as a word, one space between."""
    resume = continuation_resume(line)
    if resume is not None and literal_open:
        return prev_text.ljust(65) + line[resume:72]
    return prev_text.rstrip() + " " + line[7:72].lstrip()


def open_literal(text: str) -> bool:
    """#5648: whether `text` ends inside an unterminated literal."""
    quote = None
    for ch in text:
        if quote is None and ch in "'\"":
            quote = ch
        elif ch == quote:
            quote = None
    return quote is not None


def comment_at(text: str) -> int:
    """#5648: where `text`'s `*>` comment starts (one outside a literal), or len(text)."""
    at = text.find("*>")
    while at >= 0:
        if not open_literal(text[:at]):
            return at
        at = text.find("*>", at + 2)
    return len(text)


def free_code(line: str) -> str:
    """#5648: a free-format line without its `*>` comment (one outside a literal)."""
    return line[: comment_at(line)]


def drop_comment(text: str) -> str:
    """#4874, #5648: `text` without a floating `*>` comment (one outside a literal), trailing blanks left off; a
    literal that holds `*>` is kept whole."""
    at = comment_at(text)
    return text[:at].rstrip() if at < len(text) else text


@dataclass
class MappedLine:
    """#5648: one line of an expanded program with where it came from: `file` and 1-based `line` of the source or
    COPY member that holds it (a member's lines keep the member's own numbers), never a position in the expanded
    text. The translator's `Line` extends it with its column-72 bookkeeping."""

    text: str
    file: str
    line: int

    @property
    def origin(self) -> str:
        """`file:line` with the path as given."""
        return f"{self.file}:{self.line}"

    @property
    def short_origin(self) -> str:
        """`CUSTREC.cpy:12`: the file's name without its directory."""
        return f"{Path(self.file).name}:{self.line}"


def line_map(lines: list[MappedLine]) -> list[tuple[str, int]]:
    """#5648: the expansion's line map: entry i is the (file, line) of expanded line i."""
    return [(ln.file, ln.line) for ln in lines]
