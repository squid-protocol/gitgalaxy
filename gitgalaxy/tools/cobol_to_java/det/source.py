"""A fixed-format COBOL program as the translator reads it: COPY members expanded (with REPLACING), comment and
debugging lines dropped, continued literals joined. Every logical line keeps where it came from."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from gitgalaxy.core.source_text import read_source

COPY_EXTS = ("", ".cpy", ".CPY", ".cbl", ".CBL", ".cob", ".copy")


@dataclass
class Line:
    text: str  # columns 8-72 (area A and B)
    file: str
    line: int


class CopyNotFound(Exception):
    pass


def _raw_lines(path: Path) -> list[str]:
    return read_source(path).text.splitlines()


def logical_lines(raw: list[str], file: str) -> list[Line]:
    """Columns 8-72 of each code line; comment (* /), debugging (D) and blank lines dropped; a continuation line
    (indicator '-') joined to the line before: a continued literal resumes after the continuation's first quote."""
    out: list[Line] = []
    for n, line in enumerate(raw, 1):
        if len(line) < 7:
            continue
        ind = line[6]
        if ind in "*/Dd":
            continue
        body = line[7:72]
        if ind == "-" and out:
            prev = out[-1]
            cont = body.lstrip()
            if cont[:1] in ("'", '"') and _open_literal(prev.text):
                # the open literal ran to column 72 (its trailing spaces are part of it)
                prev.text = prev.text.ljust(65) + cont[1:]
            else:
                prev.text = prev.text.rstrip() + " " + cont
            continue
        if not body.strip():
            continue
        out.append(Line(body.rstrip() if not _open_literal(body) else body, file, n))
    return out


def _open_literal(text: str) -> bool:
    """Whether `text` ends inside an unterminated literal."""
    quote = None
    for ch in text:
        if quote is None and ch in "'\"":
            quote = ch
        elif ch == quote:
            quote = None
    return quote is not None


_COPY = re.compile(r"^\s*COPY\s+(['\"]?)([A-Z0-9#@$-]+)\1(?:\s+(?:OF|IN)\s+[A-Z0-9-]+)?\s*(.*)$", re.I)


def expand(lines: list[Line], dirs: list[Path], depth: int = 0) -> list[Line]:
    """COPY statements replaced by their members' lines (recursively); REPLACING ==a== BY ==b== and word-for-word
    `a BY b` applied. A member found nowhere raises CopyNotFound."""
    out: list[Line] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = _COPY.match(ln.text)
        if not m:
            out.append(ln)
            i += 1
            continue
        stmt, j = ln.text, i
        while not re.search(r"\.\s*$", re.sub(r"==.*?==|'[^']*'", "", stmt)) and j + 1 < len(lines):
            j += 1
            stmt += " " + lines[j].text
        name = m.group(2).upper()
        member = next((d / f"{nm}{ext}" for d in dirs for nm in dict.fromkeys((name, name.lower()))
                       for ext in COPY_EXTS if (d / f"{nm}{ext}").is_file()), None)  # fmt: skip
        if member is None:
            raise CopyNotFound(f"{ln.file}:{ln.line}: COPY {name} found in none of {[str(d) for d in dirs]}")
        if depth > 8:
            raise CopyNotFound(f"{ln.file}:{ln.line}: COPY {name} nests deeper than 8")
        body = logical_lines(_raw_lines(member), str(member))
        pairs = _replacing(stmt)
        if pairs:
            for b in body:
                for old, new in pairs:
                    b.text = _replace(b.text, old, new)
        expanded = expand(body, dirs, depth + 1)
        # the text before COPY on its line (rare: `01 X. COPY Y.`) and what follows the COPY's period stay
        head = ln.text[: m.start()]
        if head.strip():
            out.append(Line(head, ln.file, ln.line))
        out += expanded
        i = j + 1
    return out


def _replacing(stmt: str) -> list[tuple[str, str]]:
    m = re.search(r"\bREPLACING\b(.*)$", stmt, re.I | re.S)
    if not m:
        return []
    body = m.group(1).rstrip().rstrip(".")
    pairs = re.findall(r"==(.*?)==\s+BY\s+==(.*?)==", body, re.I | re.S)
    if pairs:
        return [(a.strip(), b.strip()) for a, b in pairs]
    return [(a, b) for a, b in re.findall(r"(\S+)\s+BY\s+(\S+)", body, re.I)]


def _replace(text: str, old: str, new: str) -> str:
    if re.fullmatch(r"[A-Z0-9-]+", old, re.I):  # a word: whole words only
        return re.sub(rf"(?<![A-Z0-9-]){re.escape(old)}(?![A-Z0-9-])", new, text, flags=re.I)
    return text.replace(old, new)


def program_lines(program: Path, dirs: list[Path]) -> list[Line]:
    """The whole program, expanded."""
    return expand(logical_lines(_raw_lines(program), str(program)), [program.parent, *dirs])


def as_fixed(lines: list[Line]) -> str:
    """The lines as fixed-format source again (for a parser): seven blank columns, then the text -- longer lines
    are kept whole (a joined continuation), which the parser reads as free text."""
    return "".join(f"       {ln.text}\n" for ln in lines)
