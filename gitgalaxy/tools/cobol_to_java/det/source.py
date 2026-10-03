"""A fixed-format COBOL program as the translator reads it: COPY members expanded (with REPLACING), comment and
debugging lines dropped, continued literals joined. Every logical line keeps where it came from."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from gitgalaxy.core.source_text import read_source

# a copybook's own extensions before a program's: `COPY GETCOMPY` in GETCOMPY.cbl means the member, not the program
COPYBOOK_EXTS = ("", ".cpy", ".CPY", ".copy", ".COPY", ".dcl", ".DCL")  # (.dcl: a DCLGEN member)
PROGRAM_EXTS = (".cbl", ".CBL", ".cob", ".COB")
COPY_EXTS = COPYBOOK_EXTS + PROGRAM_EXTS


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
    """COPY statements replaced by their members' lines (recursively); REPLACING's operands applied in order:
    ==a== BY ==b==, word-for-word `a BY b`, a literal BY a literal, and LEADING / TRAILING ==a== BY ==b== on text
    words. A member found nowhere raises CopyNotFound."""
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
        while not re.search(r"\.\s*$", re.sub(r"==.*?==|'[^']*'|\"[^\"]*\"", "", stmt)) and j + 1 < len(lines):
            j += 1
            stmt += " " + lines[j].text
        name = m.group(2).upper()
        # never a file being expanded already (the including program or copybook itself)
        # a copybook's extensions in every directory before a program's: CBSA keeps a program INQCUST.cbl next to
        # its sources and the copybook INQCUST.cpy elsewhere; never a file being expanded already
        member = next((d / f"{nm}{ext}" for exts in (COPYBOOK_EXTS, PROGRAM_EXTS) for d in dirs
                       for nm in dict.fromkeys((name, name.lower())) for ext in exts
                       if (d / f"{nm}{ext}").is_file() and (d / f"{nm}{ext}").resolve() not in chain), None)  # fmt: skip
        if member is None:
            raise CopyNotFound(f"{ln.file}:{ln.line}: COPY {name} found in none of {[str(d) for d in dirs]}")
        if depth > 8:
            raise CopyNotFound(f"{ln.file}:{ln.line}: COPY {name} nests deeper than 8")
        body = logical_lines(_raw_lines(member), str(member))
        pairs = _replacing(stmt)
        if pairs:
            for b in body:
                for mode, old, new in pairs:
                    b.text = _replace(b.text, old, new, mode)
        expanded = expand(body, dirs, depth + 1, chain | {member.resolve()})
        # the text before COPY on its line (rare: `01 X. COPY Y.`) and what follows the COPY's period stay
        head = ln.text[: m.start()]
        if head.strip():
            out.append(Line(head, ln.file, ln.line))
        out += expanded
        i = j + 1
    return out


# one REPLACING operand: pseudo-text, a literal, or a word (a separator comma / semicolon after it is not part of it)
_OPERAND = r"==.*?==|\"(?:[^\"]|\"\")*\"|'(?:[^']|'')*'|[^\s,;=]+"
_REPLACING_PAIR = re.compile(rf"(?:\b(LEADING|TRAILING)\s+)?({_OPERAND})\s+BY\s+({_OPERAND})", re.I | re.S)


def _operand(op: str) -> str:
    return op[2:-2].strip() if op.startswith("==") else op


def _replacing(stmt: str) -> list[tuple[str, str, str]]:
    """COPY ... REPLACING's (mode, old, new) operands, in order; mode is '', 'LEADING' or 'TRAILING'. The operands
    may mix pseudo-text, literals and words, separated by spaces, commas or semicolons."""
    m = re.search(r"\bREPLACING\b(.*)$", stmt, re.I | re.S)
    if not m:
        return []
    body = m.group(1).rstrip().rstrip(".")
    return [((mode or "").upper(), _operand(a), _operand(b)) for mode, a, b in _REPLACING_PAIR.findall(body)]


def _replace(text: str, old: str, new: str, mode: str = "") -> str:
    if mode == "LEADING":  # the leading part of each text word that starts with `old`
        return re.sub(rf"(?<![A-Z0-9-]){re.escape(old)}(?=[A-Z0-9-])", new, text, flags=re.I)
    if mode == "TRAILING":  # the trailing part of each text word that ends with `old`
        return re.sub(rf"(?<=[A-Z0-9-]){re.escape(old)}(?![A-Z0-9-])", new, text, flags=re.I)
    if re.fullmatch(r"[A-Z0-9-]+", old, re.I):  # a word: whole words only
        return re.sub(rf"(?<![A-Z0-9-]){re.escape(old)}(?![A-Z0-9-])", new, text, flags=re.I)
    return text.replace(old, new)


_LITERAL = r"[-+]?\d+(?:\.\d+)?|X?\"[^\"]*\"|X?'[^']*'"
_CONSTANT = re.compile(rf"\s*78\s+([A-Z0-9][A-Z0-9-]*)\s+VALUE\s+(?:IS\s+)?({_LITERAL})\s*\.\s*$", re.I)
_LIT_SPLIT = re.compile(r"(X?\"[^\"]*\"|X?'[^']*')", re.I)


def constants(lines: list[Line]) -> list[Line]:
    """Level-78 constant entries (COBOL 2002 / GnuCOBOL: `78 NAME VALUE literal.`) resolved as the compiler does:
    the entry dropped and every NAME outside a literal replaced by its literal. Only a literal VALUE is taken; any
    other 78 entry is left for the layout to refuse by name."""
    found: dict[str, str] = {}
    kept: list[Line] = []
    for ln in lines:
        m = _CONSTANT.match(ln.text)
        if m:
            found[m.group(1).upper()] = m.group(2)
        else:
            kept.append(ln)
    if not found:
        return lines
    names = re.compile(rf"(?<![A-Z0-9-])({'|'.join(map(re.escape, sorted(found, key=len, reverse=True)))})(?![A-Z0-9-])",
                       re.I)  # fmt: skip
    for ln in kept:
        parts = _LIT_SPLIT.split(ln.text)
        ln.text = "".join(
            p if i % 2 else names.sub(lambda m: found[m.group(1).upper()], p) for i, p in enumerate(parts)
        )
    return kept


def program_lines(program: Path, dirs: list[Path]) -> list[Line]:
    """The whole program, expanded, its level-78 constants resolved."""
    return constants(expand(logical_lines(_raw_lines(program), str(program)), [program.parent, *dirs],
                            chain=frozenset({program.resolve()})))  # fmt: skip


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
    for f in sorted(bms_files):
        maps = symbolic_maps(bms_screen_fields(read_source(f).text))
        for mapset, text in maps.items():
            # the copybook is the source member's (DFHMAPS names it by the member assembled, not the DFHMSD label):
            # CBSA's BNK1B2M.bms declares mapset BNK1TFM too, and COPY BNK1TFM means BNK1TFM.bms's
            name = f.stem.upper() if len(maps) == 1 else mapset.upper()
            (out / f"{name}.cpy").write_text(text, encoding="utf-8")
            made.append(name)
    return made
