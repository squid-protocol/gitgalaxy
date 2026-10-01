"""A fixed-format COBOL program as the translator reads it: COPY members expanded (with REPLACING), comment and
debugging lines dropped, continued literals joined. Every logical line keeps where it came from."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from gitgalaxy.core.source_text import read_source

# a copybook's own extensions before a program's: `COPY GETCOMPY` in GETCOMPY.cbl means the member, not the program
COPY_EXTS = ("", ".cpy", ".CPY", ".copy", ".cbl", ".CBL", ".cob")


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
        if not out and re.match(r"\s*(CBL|PROCESS)\b", line[7:72] if len(line) > 7 else line, re.I):
            continue  # compiler options before the program (PROCESS CICS,... / CBL ...): not COBOL text
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


def expand(lines: list[Line], dirs: list[Path], depth: int = 0, chain: frozenset = frozenset()) -> list[Line]:
    """COPY statements replaced by their members' lines (recursively); REPLACING ==a== BY ==b== and word-for-word
    `a BY b` applied. A member found nowhere raises CopyNotFound."""
    out: list[Line] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = _COPY.match(ln.text)
        if not m and re.match(r"\s*EXEC\s+SQL\b", ln.text, re.I):
            # EXEC SQL INCLUDE member END-EXEC is a COPY of the member (Db2's precompiler includes it the same way)
            j, block = i, ln.text
            while not re.search(r"\bEND-EXEC\b", block, re.I) and j + 1 < len(lines):
                j += 1
                block += " " + lines[j].text
            inc = re.match(r"\s*EXEC\s+SQL\s+INCLUDE\s+([A-Z0-9#@$-]+)\s+END-EXEC\s*\.?\s*$", block, re.I)
            if inc:
                lines = [*lines[:i], Line(f"COPY {inc.group(1)}.", ln.file, ln.line), *lines[j + 1 :]]
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
        # never a file being expanded already (the including program or copybook itself)
        member = next((d / f"{nm}{ext}" for d in dirs for nm in dict.fromkeys((name, name.lower()))
                       for ext in COPY_EXTS if (d / f"{nm}{ext}").is_file()
                       and (d / f"{nm}{ext}").resolve() not in chain), None)  # fmt: skip
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
        expanded = expand(body, dirs, depth + 1, chain | {member.resolve()})
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
    return expand(logical_lines(_raw_lines(program), str(program)), [program.parent, *dirs],
                  chain=frozenset({program.resolve()}))  # fmt: skip


def as_fixed(lines: list[Line]) -> str:
    """The lines as fixed-format source again (for a parser): seven blank columns, then the text -- longer lines
    are kept whole (a joined continuation), which the parser reads as free text."""
    return "".join(f"       {ln.text}\n" for ln in lines)


def bms_copybooks(bms_files: list[Path], out: Path) -> list[str]:
    """The symbolic-map copybooks (gitgalaxy.core.bms_symbolic, the BMS assembler's DSECT layout) of the BMS
    sources, written to `out` as <MAPSET>.cpy -- a build artefact most estates do not check in (CBSA ships none).
    Put `out` after the estate's own copybook directories: a copybook the estate does ship wins."""
    from gitgalaxy.core.bms_screen_fields import bms_screen_fields
    from gitgalaxy.core.bms_symbolic import symbolic_maps

    out.mkdir(parents=True, exist_ok=True)
    made = []
    for f in bms_files:
        for mapset, text in symbolic_maps(bms_screen_fields(read_source(f).text)).items():
            (out / f"{mapset.upper()}.cpy").write_text(text, encoding="utf-8")
            made.append(mapset.upper())
    return made
