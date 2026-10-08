"""A fixed-format COBOL program as the translator reads it: COPY members expanded (with REPLACING), comment and
debugging lines dropped, continued literals joined. Every logical line keeps where it came from."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from gitgalaxy.core.compiler_options import cards
from gitgalaxy.core.source_text import read_source

# a copybook's own extensions before a program's: `COPY GETCOMPY` in GETCOMPY.cbl means the member, not the program
COPYBOOK_EXTS = ("", ".cpy", ".CPY", ".copy", ".COPY", ".dcl", ".DCL")  # (.dcl: a DCLGEN member)
PROGRAM_EXTS = (".cbl", ".CBL", ".cob", ".COB")
COPY_EXTS = COPYBOOK_EXTS + PROGRAM_EXTS


def cobol_parser():
    """tree-sitter's COBOL parser (det/layout.py and det/stmt.py). The language pack is the optional `translator`
    extra, imported on first use, so a missing install says which extra to add instead of a bare ImportError."""
    try:
        from tree_sitter_language_pack import get_parser
    except ImportError as exc:
        raise ImportError(
            "the COBOL-to-Java translator needs tree-sitter-language-pack: pip install gitgalaxy[translator]"
        ) from exc
    return get_parser("cobol")


@dataclass
class Line:
    text: str  # columns 8-72 (area A and B)
    file: str
    line: int
    cut: str = ""  # #4462: the text past column 72 of a line whose columns 8-72 end inside a literal


# ---- the survey-only what-if switch (#4270 `cics_census.py blockers --unmask`) -----------------------------------
# A refusal that stops the WHOLE program (a cut literal, a missing copybook, ...) hides every gap behind it: the blocker
# ranking only learns what a program would hit next after the refusal is fixed. `survey_unmask` switches ONE named
# refusal check off for the duration of a `with` block, so a survey can ask "what would this program hit next?".
# It is honoured ONLY inside that block, which only tests/tools/det_survey.py --unmask opens (tests pin that no module
# under gitgalaxy/ does): no environment variable, flag or default turns it on, so no production path can translate
# a program the translator refuses. What a survey reports under it is a what-if, never a translation.
UNMASKABLE = {
    "cut-literal": "a literal cut open at column 72 (cut_literal): read with its text past column 72, as if fixed",
    "several-programs": "several programs in one source (several_programs): read as one",
    "unmodelled": "national / DBCS text, a national letter in a name, IDMS, a decimal-point literal under "
    "DECIMAL-POINT IS COMMA, the stand-in control characters (unmodelled): read as the grammar is handed them",
    "missing-copybook": "a COPY found in no directory: expanded to nothing, so its items are `no such item` holes",
}
_unmasked: frozenset[str] = frozenset()


@contextmanager
def survey_unmask(*checks: str) -> Iterator[None]:
    """SURVEY ONLY (tests/tools/det_survey.py --unmask): the named refusal checks (UNMASKABLE) are off inside the block."""
    global _unmasked
    bad = [c for c in checks if c not in UNMASKABLE]
    if bad:
        raise ValueError(f"not an unmaskable refusal check: {', '.join(bad)} (UNMASKABLE: {', '.join(UNMASKABLE)})")
    saved, _unmasked = _unmasked, _unmasked | frozenset(checks)
    try:
        yield
    finally:
        _unmasked = saved


def unmasked(check: str) -> bool:
    """Whether a survey switched `check` off (survey_unmask); always False outside such a block."""
    return check in _unmasked


def refusal(lines: list[Line]) -> str | None:
    """#4462: why the program is refused whole before the parser (unmodelled, several_programs, cut_literal), or None.
    A check a survey switched off (survey_unmask) is skipped."""
    for check, why in (("unmodelled", unmodelled), ("several-programs", several_programs),
                       ("cut-literal", cut_literal)):  # fmt: skip
        if not unmasked(check):
            msg = why(lines)
            if msg:
                return msg
    return None


class CopyNotFound(Exception):
    pass


class CopyAmbiguous(CopyNotFound):
    """#4461: no engine answer decided a COPY (a run without an engine, or a member outside the estate) and the
    directories searched hold the member in more than one: the translator does not pick the first, it refuses by
    name and lists the candidates. A single match still resolves."""


class CopyUnresolved(CopyNotFound):
    """#4468: a COPY the engine did not resolve to one file (a gap, several files; a collision in strict mode, #4486),
    or that the translator never expanded where the engine resolved it: the program is refused by name, never built
    on a guessed member."""


@dataclass(frozen=True)
class EngineCopies:
    """#4468 (ownership per #4273, docs/language_status/fact_ownership.md): the engine's resolution of every COPY the
    program reaches -- the program's own and its copybooks' -- which the translator takes instead of searching
    directories. The engine resolves the way the compiler does (copy libraries, SYSLIB order, COPY ... IN: #4265,
    #4420); the translator's first-hit search took the wrong library's member (#4461) and spliced a program source in
    for a member no library holds (#4460).

    `root`: the estate the engine scanned (its paths are relative to it). `edges`: importer (repo-relative, every
    estate file the program's COPYs reach) -> member -> ((file, the COPY forms' library-names: "" an unqualified COPY;
    empty: not recorded), ...). `gaps` / `collisions`: (importer, member) the engine reports no declared library
    holds, or several do (#4421; only when the scan declared copy libraries). `pages` (#4462): repo-relative file ->
    the code page the estate declares for it and the engine decoded it with (`--source-encoding`, #3909), so the
    translator reads the program and its members the same way.

    #4486: a collision is no error on z/OS -- the compiler takes the first library of the SYSLIB order holding the
    member, and the engine resolves it the same way. The translator takes the engine's member and records a warning
    in `warnings` (the member, the library chosen, the other libraries holding it in search order:
    `collision_libraries`). `strict`: refuse every collision by name instead (CopyUnresolved), as before #4486. A gap
    (no library holds the member) is refused in both modes."""

    program: Path
    root: Path
    edges: dict[str, dict[str, tuple[tuple[Path, frozenset[str]], ...]]]
    gaps: frozenset[tuple[str, str]] = frozenset()
    collisions: frozenset[tuple[str, str]] = frozenset()
    pages: dict[str, str] = field(default_factory=dict)
    collision_libraries: dict[tuple[str, str], tuple[str, tuple[str, ...]]] = field(default_factory=dict)
    strict: bool = False
    warnings: list[str] = field(default_factory=list, compare=False)

    @classmethod
    def of(cls, program: Path, root: Path, deps: dict[str, dict[str, list[str]] | list[str]],
           gaps=(), collisions=(), pages: dict[str, str] | None = None, strict: bool = False) -> EngineCopies:  # fmt: skip
        """From importer -> its resolved COPY files (repo-relative; a list, or file -> library-names). A symbolic
        map generated from BMS (`map.bms#MAPSET`) is not an estate file: the translator generates its own.
        `collisions`: (importer, member[, library chosen, [other libraries]]) rows (GalaxyIR.copy_resolution)."""
        edges: dict[str, dict[str, list[tuple[Path, frozenset[str]]]]] = {}
        for imp, files in deps.items():
            mine = edges.setdefault(imp, {})
            for f in files:
                if not re.search(r"\.bms#[^/]*$", f, re.I):
                    libs = files.get(f) if isinstance(files, dict) else None
                    mine.setdefault(Path(f).stem.upper(), []).append((root / f, frozenset(libs or ())))
        return cls(program, root, {i: {m: tuple(v) for m, v in e.items()} for i, e in edges.items()},
                   frozenset((i, m.upper()) for i, m in gaps), frozenset((c[0], c[1].upper()) for c in collisions),
                   {_nfc(f): p for f, p in (pages or {}).items() if p},
                   {(c[0], c[1].upper()): (str(c[2] or "?"), tuple(str(x) for x in c[3] or ()))
                    for c in collisions if len(c) >= 4}, strict)  # fmt: skip

    @property
    def resolved(self) -> dict[str, tuple[Path, ...]]:
        """member -> the files the engine resolved for the program's own COPY of it."""
        own = self.edges.get(self.rel(self.program), {})
        return {m: tuple(f for f, _ in hits) for m, hits in own.items()}

    def rel(self, p: Path) -> str:
        try:
            return p.resolve().relative_to(self.root.resolve()).as_posix()
        except ValueError:
            return str(p)

    def page(self, p: Path) -> str | None:
        """#4462: the code page the engine decoded `p` with (the estate's declaration); None: read unaided."""
        return self.pages.get(_nfc(self.rel(p))) if self.pages else None

    def with_program(self, program: Path) -> EngineCopies:
        return EngineCopies(program, self.root, self.edges, self.gaps, self.collisions, self.pages,
                            self.collision_libraries, self.strict, self.warnings)  # fmt: skip

    def in_estate(self, p: Path) -> bool:
        return self.rel(p) != str(p)

    def member(self, importer: str, name: str, library: str | None, where: str) -> Path | None:
        """The file the engine resolved `COPY name [IN library]` in `importer` to. None: the engine resolved nothing
        for it -- a system or generated member outside the estate (DFHAID, SQLCA, a BMS symbolic map), which the
        caller then finds itself; an estate file it would find instead is refused (`unresolved`)."""
        imp = self.rel(Path(importer))
        # (a collision is the SYSLIB search's: `COPY name IN library` searches that library only)
        collision = not library and (imp, name) in self.collisions
        if collision and self.strict:
            raise CopyUnresolved(f"{where}: COPY {name}: the engine records a collision (several libraries hold it)")
        hits = self.edges.get(imp, {}).get(name, ())
        if len(hits) > 1:  # #4265: `COPY X` and `COPY X IN LIB` in one file reach two files; the COPY's own form picks
            hits = tuple(h for h in hits if (library or "") in h[1]) or hits
        if len(hits) > 1:
            raise CopyUnresolved(f"{where}: COPY {name}: the engine resolved several files: "
                                 f"{', '.join(sorted(self.rel(f) for f, _ in hits))}")  # fmt: skip
        if collision:
            if not hits:  # (the first library holds several files of the member: the engine chose none)
                raise CopyUnresolved(f"{where}: COPY {name}: the engine records a collision and resolved no member")
            self.collided(name, imp, hits[0][0])
        return hits[0][0] if hits else None

    def collided(self, name: str, importer: str, chosen: Path) -> None:
        """#4486: the warning for a collision translated through the first library's member."""
        lib, others = self.collision_libraries.get((importer, name), ("?", ()))
        note = (f"COPY {name} in {importer}: SYSLIB collision -- took {self.rel(chosen)} from library {lib} (first in "
                f"search order); also in {', '.join(others) or 'another library'}")  # fmt: skip
        if note not in self.warnings:
            self.warnings.append(note)

    def unresolved(self, importer: str, name: str, found: Path, where: str) -> None:
        """A member the engine resolved nothing for, found by the translator's own search: refused when it is an
        estate file (#4460: a program source spliced in; a gap no declared library fills)."""
        if not self.in_estate(found):
            return
        why = ("records a gap (no declared library holds it)" if (self.rel(Path(importer)), name) in self.gaps
               else "resolved nothing")  # fmt: skip
        raise CopyUnresolved(f"{where}: COPY {name}: the engine {why}; the estate holds {self.rel(found)}")

    def check_all_expanded(self, expanded: set[str]) -> None:
        """Every member the engine resolved for the program was expanded by the translator (#4459)."""
        resolved = self.resolved
        for name in sorted(set(resolved) - expanded):
            raise CopyUnresolved(f"{self.program}: COPY {name}: engine resolved "
                                 f"{', '.join(sorted(self.rel(e) for e in resolved[name]))}, "
                                 "translator expanded no COPY of it")  # fmt: skip


def _nfc(path: str) -> str:
    return unicodedata.normalize("NFC", path.replace("\\", "/"))


def _raw_lines(path: Path, engine: EngineCopies | None = None) -> list[str]:
    """#4462: decoded the way the engine decoded it: with the code page the estate declares for the file (cp273,
    cp037, cp277 ...: EngineCopies.pages); without a declaration, read_source's ladder (UTF-8, else a guess)."""
    return read_source(path, declared=engine.page(path) if engine is not None else None).text.splitlines()


_ID_DIVISION = re.compile(r"^(\s*)ID\s+DIVISION(?=\s*\.)", re.I)
# #4462: `PROGRAM-ID LNCALC.` (estate-crucible LOAN), the header's period left out: IBM Enterprise COBOL accepts it
# (a warning), the grammar does not
_PROGRAM_ID_NO_PERIOD = re.compile(r"^(\s*PROGRAM-ID)(?=\s+[^\s.])", re.I)


def _headers(code: str) -> str:
    """IDENTIFICATION DIVISION headers in the one form the parser downstream knows: `ID DIVISION.` (IBM's
    abbreviation, IBM DBB MortgageApplication) in full, and PROGRAM-ID's period put back."""
    if _ID_DIVISION.match(code):
        code = _ID_DIVISION.sub(lambda m: m.group(1) + "IDENTIFICATION DIVISION", code, count=1)
    return _PROGRAM_ID_NO_PERIOD.sub(lambda m: m.group(1) + ".", code, count=1)


# `>>SOURCE FORMAT FREE` / `>>SOURCE FORMAT IS FIXED` / `>>SOURCE FREE` (IBM Enterprise COBOL 6.3+, GnuCOBOL)
_SOURCE_FORMAT = re.compile(r"\s*>>\s*SOURCE(?:\s+FORMAT)?(?:\s+IS)?\s+(FREE|FIXED)\b", re.I)


def _free_code(line: str) -> str:
    """A free-format line without its `*>` comment (one outside a literal)."""
    at = line.find("*>")
    while at >= 0:
        if not _open_literal(line[:at]):
            return line[:at]
        at = line.find("*>", at + 2)
    return line


# #4462: IBM's listing-control statements -- EJECT, SKIP1 / SKIP2 / SKIP3, TITLE literal -- each the only statement on
# its line (Area A or B, an optional separator period): they direct the compiler's listing, not the program, and the
# grammar has none of them (cics-java-jcics-samples EC01's EJECT after a paragraph, cics-java-recgen EDUPGM's TITLE
# before its IDENTIFICATION DIVISION)
_LISTING = re.compile(r"\s*(?:EJECT|SKIP[123]|TITLE\s+(?:'[^']*'|\"[^\"]*\"))\s*\.?\s*", re.I)


def logical_lines(raw: list[str], file: str) -> list[Line]:
    """Columns 8-72 of each code line; comment (* /), debugging (D) and blank lines dropped; a continuation line
    (indicator '-') joined to the line before: a continued literal resumes after the continuation's first quote.
    #4462: after `>>SOURCE FORMAT FREE` (until `>>SOURCE FORMAT FIXED`) a line is code from column 1, of any length,
    up to a `*>` comment. Listing-control statements (EJECT, SKIPn, TITLE) are dropped; a line whose columns 8-72
    end inside a literal keeps its text past column 72 in `cut` (cut_literal)."""
    out: list[Line] = []
    # Compiler-option cards (CBL / PROCESS, before the program or after an END PROGRAM) are not COBOL text. The
    # engine's own reader decides which lines they are: a card may start in any column from 1, so IBM DBB's
    # `   CBL NUMPROC(MIG),...` (CBL in columns 4-6) is one, as GenApp's `       PROCESS SQL` is.
    card_lines = {n for n, _ in cards("\n".join(raw))}
    free = False
    for n, line in enumerate(raw, 1):
        if n in card_lines:
            continue
        fmt = _SOURCE_FORMAT.match(line if free else line[6:])
        if fmt:
            free = fmt.group(1).upper() == "FREE"
            continue
        if free:
            code = _free_code(line).rstrip()
            if code.strip() and not code.lstrip().startswith(">>D ") and not _LISTING.fullmatch(code):
                out.append(Line(_headers(code), file, n))
            continue
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
        if not body.strip() or _LISTING.fullmatch(body):
            continue
        body = _headers(body)
        is_open = _open_literal(body)
        out.append(Line(body if is_open else body.rstrip(), file, n, line[72:].rstrip() if is_open else ""))
    return out


def cut_literal(lines: list[Line]) -> str | None:
    """#4462: a literal left open where its line's program-text area ends (column 72) with more text past it and no
    continuation line closing it (NexusBank's `MOVE '...coincidere.'` with `e.'` in columns 73-75): fixed-form
    COBOL does not read past column 72, so the program does not compile as written. A source defect, refused by name
    (the PROCEDURE DIVISION had failed to parse, unnamed); a `>>SOURCE FORMAT FREE` program has no column limit and
    is read whole. None: no such line."""
    for ln in lines:
        if ln.cut.strip() and _open_literal(ln.text):
            return (f"{Path(ln.file).name}:{ln.line}: source defect: source text past column 72 (`{ln.cut.strip()}`) cuts "
                    "a literal open: fixed-form COBOL reads columns 8-72 only")  # fmt: skip
    return None


# #4523: a quotation mark inside a quotation-mark literal, as the grammar is handed it (`unwrap` restores `""`): the
# grammar splits `"IT""S"` into two literals (a VALUE read as two, a MOVE refused), though it reads `'IT''S'` whole
QQ = "\x1e"
# #4462: a hexadecimal literal on a re-wrapped line, as the grammar is handed it: `"<HX>C1C2"` (an alphanumeric literal,
# which it continues onto the next row; it continues no X"..."), restored to X"C1C2" by `unwrap`
HX = "\x1f"
# #4272: a character beyond Latin-1 inside a PROCEDURE DIVISION alphanumeric literal, as the grammar is handed it
# (`narrowed`): the statement holding it is a hole by name (gen.WIDE_WHY), never translated
WIDE = "\x1d"


_DECIMAL_COMMA = re.compile(r"\bDECIMAL-POINT\s+(?:IS\s+)?COMMA\b", re.I)
# #4462: a PICTURE character-string (its `.` and `,` are editing symbols, never a literal's decimal point)
_PICTURE = re.compile(r"(?<![\w-])PIC(?:TURE)?(?:\s+IS)?\s+\S+", re.I)
# #4462: under DECIMAL-POINT IS COMMA, a numeric literal's decimal point: a comma between digits (a separator comma
# is followed by a space), and a point between digits (which the clause makes no decimal point)
_COMMA_POINT = re.compile(r"(?<![\w.,-])[+-]?\d+(,)\d+(?![\w-]|[.,]\d)")
_POINT_POINT = re.compile(r"(?<![\w.,-])[+-]?\d+\.\d+(?![\w-]|[.,]\d)")
# #4462: an IDMS program (CA IDMS / IDMS-DC, the DMLC precompiler's input): its ENVIRONMENT DIVISION's IDMS-CONTROL
# SECTION (PROTOCOL. MODE IS IDMS-...) or its DATA DIVISION's SCHEMA SECTION (DB subschema WITHIN schema)
_IDMS = re.compile(r"^\s*(?:IDMS-CONTROL\s+SECTION|SCHEMA\s+SECTION)\s*\.|\bMODE\s+IS\s+IDMS(?:-DC|-CICS)?\b", re.I)


def _outside_literals(text: str) -> str:
    """`text` with each literal's content blanked (its quotes kept)."""
    out, quote = [], None
    for ch in text:
        if quote is None:
            quote = ch if ch in "'\"" else None
            out.append(ch)
        elif ch == quote:
            quote = None
            out.append(ch)
        else:
            out.append(" ")
    return "".join(out)


def unmodelled(lines: list[Line]) -> str | None:
    """#4462: why the translator cannot read `lines` (a refusal by name, before the parser), or None.

    - A character beyond Latin-1 (national / DBCS text: a Kanji name or literal, an ideographic space, a PIC G
      literal; estate-crucible KYUY): the translator lays records out, and hands the parser its text, in one byte a
      character. It had raised UnicodeEncodeError; a DBCS estate is refused, never laid out wrong.
    - A national letter in a word outside a literal (`BETRÄGE`, read in cp273): the COBOL grammar reads ASCII words
      only, and refused the line unnamed.
    - #4462: under DECIMAL-POINT IS COMMA (modelled: comma_literals, Item.decimal_comma), a numeric literal written
      with a decimal POINT (`1.5`): the clause makes `,` the decimal point, so it is no number the compiler reads.
    - #4462: IDMS (IDMS-CONTROL SECTION, SCHEMA SECTION; estate-crucible LOAN LNIDMS01): its DML (BIND RUN-UNIT,
      READY, OBTAIN CALC, FINISH, DC RETURN) and subschema records are not modelled, so the program is refused by name
      (#4532 tracks IDMS support), never parsed as COBOL with holes.
    - #4523: the control characters U+001E and U+001F, which the grammar is handed for a doubled `""` and a hex
      literal's `X"` (as_fixed_rows), and U+001D, which it is handed for a wide character in a literal (`narrowed`).

    #4272: not refused here -- a character beyond Latin-1 in a `*>` comment (no parser reads it), or inside an
    alphanumeric literal of the PROCEDURE DIVISION (a UTF-8 em dash in `MOVE 'Conto — bloccato' TO MSG`): its
    bytes and length are what the source's transfer to a single-byte code page made of it, so the statement holding
    it is a hole by name (`narrowed`, gen.WIDE_WHY) and the rest of the program translates. A VALUE (it lays storage
    out) and a national / DBCS literal (N'...', G'...', NX'...', U'...': national data, #4272) stay refused here.

    The IDENTIFICATION DIVISION's paragraphs after PROGRAM-ID (AUTHOR, REMARKS ...) are free text no parser reads."""
    in_id = in_proc = False
    comma = decimal_comma(lines)
    for ln in lines:
        head = ln.text.lstrip().upper()
        if re.match(r"(?:IDENTIFICATION|ID)\s+DIVISION\b", head):
            in_id, in_proc = True, False
        elif re.match(r"(?:ENVIRONMENT|DATA|PROCEDURE)\s+DIVISION\b", head):
            in_id, in_proc = False, head.startswith("PROCEDURE")
        elif in_id and not head.startswith("PROGRAM-ID"):
            continue
        ctl = next((c for c in (QQ, HX, WIDE) if c in ln.text), None)
        if ctl is not None:  # #4523, #4462, #4272: a character the grammar is handed for `""` / `X"` / a wide one
            return f"{Path(ln.file).name}:{ln.line}: the control character U+{ord(ctl):04X} is not modelled"
        wide = next((c for c in _wide_chars(ln.text, in_proc) if c[1] == "refused"), (None,))[0]
        if wide is not None:
            return (f"{Path(ln.file).name}:{ln.line}: national / DBCS text ({wide!r}, U+{ord(wide):04X}) is not modelled: the "
                    "translator reads a single-byte code page")  # fmt: skip
        bare = _outside_literals(ln.text[: _comment_at(ln.text)])  # (#4272: a `*>` comment is no name)
        word = re.search(r"[^\s.,;:()'\"=<>+*/]*[^\x00-\x7f][^\s.,;:()'\"=<>+*/]*", bare)
        if word is not None:
            return (f"{Path(ln.file).name}:{ln.line}: the name {word.group(0)} holds a national letter: the COBOL grammar reads "
                    "ASCII words only")  # fmt: skip
        if _IDMS.search(bare):
            return f"{Path(ln.file).name}:{ln.line}: IDMS DML not supported (an IDMS-DC / DMLC program: {bare.strip()})"
        point = _POINT_POINT.search(_numeric_text(ln.text)) if comma else None
        if point is not None:
            return (f"{Path(ln.file).name}:{ln.line}: the literal {point.group(0)} has a decimal point under "
                    "DECIMAL-POINT IS COMMA: not modelled")  # fmt: skip
    return None


def decimal_comma(lines: list[Line]) -> bool:
    """#4462: whether the program declares SPECIAL-NAMES DECIMAL-POINT IS COMMA (before its DATA DIVISION)."""
    for ln in lines:
        if re.match(r"(?:DATA|PROCEDURE)\s+DIVISION\b", ln.text.lstrip(), re.I):
            return False
        if _DECIMAL_COMMA.search(_outside_literals(ln.text)):
            return True
    return False


def _numeric_text(text: str) -> str:
    """`text` with its literals' content, its `*>` comment and its PICTURE strings blanked (a column for a column):
    where a numeric literal can be."""
    bare = _outside_literals(text[: _comment_at(text)]).ljust(len(text))
    return _PICTURE.sub(lambda m: " " * len(m.group(0)), bare)


def comma_literals(lines: list[Line]) -> list[Line]:
    """#4462: under DECIMAL-POINT IS COMMA (estate-crucible DEUT ZINSBER), each numeric literal's decimal comma handed
    to the grammar as a point, a column for a column (`1000,00` -> `1000.00`, `0,5` -> `0.5`), so a VALUE and a
    PROCEDURE DIVISION literal are the numbers cobc reads (a comma between digits is the decimal point; a separator
    comma is followed by a space), never a list of integers. A PICTURE keeps its characters as written: its `,` is
    the decimal point there (layout.Item.decimal_comma, and the runtime's Field.decimalComma). Without the clause,
    `lines` unchanged."""
    if not decimal_comma(lines):
        return lines
    out: list[Line] = []
    for ln in lines:
        text = list(ln.text)
        for m in _COMMA_POINT.finditer(_numeric_text(ln.text)):
            text[m.start(1)] = "."
        out.append(Line("".join(text), ln.file, ln.line, ln.cut))
    return out


def _comment_at(text: str) -> int:
    """Where `text`'s `*>` comment starts (one outside a literal), or len(text)."""
    at = text.find("*>")
    while at >= 0:
        if not _open_literal(text[:at]):
            return at
        at = text.find("*>", at + 2)
    return len(text)


def _wide_chars(text: str, in_proc: bool) -> list[tuple[str, str, int]]:
    """#4272: each character beyond Latin-1 in `text`: (the character, where, its index). Where: "comment" (in a `*>`
    comment), "literal" (inside an alphanumeric literal of the PROCEDURE DIVISION, `in_proc`: no N / G / NX / U /
    X prefix), "refused" (anywhere else: a name, a DATA DIVISION literal, a national / DBCS literal)."""
    out: list[tuple[str, str, int]] = []
    end = _comment_at(text)
    quote, plain = None, False
    for i, ch in enumerate(text):
        if quote is None and i < end and ch in "'\"":
            quote = ch
            plain = in_proc and not re.search(r"(?<![\w-])(?:N|G|NX|U|X|BX)$", text[:i], re.I)
        elif ch == quote:
            quote = None
        elif ord(ch) > 0xFF:
            out.append((ch, "comment" if i >= end else "literal" if quote is not None and plain else "refused", i))
    return out


def narrowed(lines: list[Line]) -> list[Line]:
    """#4272: `lines` as the grammar can be handed them (one byte a character, after `unmodelled` let them through):
    a character beyond Latin-1 in a `*>` comment written as a space, one inside a PROCEDURE DIVISION alphanumeric
    literal as WIDE (a column for a column: every node keeps its place), so the statement holding the literal is a
    hole by name (gen.WIDE_WHY), never translated with a stand-in byte.

    A survey's what-if only (the cut-literal check off by survey_unmask): a literal cut open at column 72 is read
    with its text past column 72, as if the source were fixed, so the survey sees what the program would hit next."""
    if unmasked("cut-literal"):
        lines = [Line(ln.text + ln.cut.rstrip(), ln.file, ln.line) if ln.cut.strip() and _open_literal(ln.text) else ln
                 for ln in lines]  # fmt: skip
    out: list[Line] = []
    in_proc = False
    for ln in lines:
        head = ln.text.lstrip().upper()
        if re.match(r"(?:IDENTIFICATION|ID|ENVIRONMENT|DATA|PROCEDURE)\s+DIVISION\b", head):
            in_proc = head.startswith("PROCEDURE")
        wide = _wide_chars(ln.text, in_proc)
        if not wide:
            out.append(ln)
            continue
        text = list(ln.text)
        for _, where, i in wide:
            text[i] = " " if where == "comment" else WIDE if where == "literal" else text[i]
        out.append(Line("".join(text), ln.file, ln.line))
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


# #4459: a COPY anywhere on its line (`01 WS-HEAD.  COPY RPTHDR.`), never inside a literal; its member may be on the
# next line (`COPY` / `UPDCTL.`, joined by `expand`)
# #4462: a member's name may hold national letters (estate-crucible NORD `COPY KUNDEÅ.`, read in cp277)
_WORD = r"(?:[^\W_]|[#@$-])"
_COPY = re.compile(rf"(?<!{_WORD})COPY\s+(['\"]?)({_WORD}+)\1(?:\s+(?:OF|IN)\s+({_WORD}+))?", re.I)
_COPY_ALONE = re.compile(rf"(?<!{_WORD})COPY\s*$", re.I)
_PROGRAM_MARK = re.compile(r"^\s*(?:IDENTIFICATION|ID)\s+DIVISION\b|^\s*PROGRAM-ID\b", re.I)


def _copy_match(text: str):
    """The COPY statement in `text` (not inside a literal), or None."""
    for m in _COPY.finditer(text):
        if not _open_literal(text[: m.start()]):
            return m
    return None


def copy_names(lines: list[Line]) -> set[str]:
    """The members the COPY statements of `lines` name (each form `expand` reads: after other text, several to a
    line, the member on the next line)."""
    names: set[str] = set()
    for i, ln in enumerate(lines):
        text = ln.text
        if _COPY_ALONE.search(text) and not _open_literal(text) and i + 1 < len(lines):
            text = text.rstrip() + " " + lines[i + 1].text.lstrip()
        for m in _COPY.finditer(text):
            if not _open_literal(text[: m.start()]):
                names.add(m.group(2).upper())
    return names


def _statement_end(stmt: str, start: int) -> int:
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


_SHIPPED_COPY = (Path(__file__).parent / "copy").resolve()  # DFHEIBLK, DFHAID, DFHBMSCA: a fallback, never a rival


def _search_member(name: str, dirs: list[Path], chain: frozenset, where: str) -> Path | None:
    """#4461: the one file `COPY name` names in `dirs` (no engine answer). A copybook extension beats a program
    extension (CBSA keeps a program INQCUST.cbl beside its sources and the copybook INQCUST.cpy elsewhere); the
    translator's shipped system members (DFHAID ...) are consulted only where no other directory holds the member.
    The same file reached through several directories is one candidate; several distinct files are CopyAmbiguous."""
    for shipped in (False, True):
        for exts in (COPYBOOK_EXTS, PROGRAM_EXTS):
            found: dict[Path, Path] = {}  # resolved -> as found; one per directory (its first name/extension)
            for d in dirs:
                if (d.resolve() == _SHIPPED_COPY) != shipped:
                    continue
                hit = next((d / f"{nm}{ext}" for nm in dict.fromkeys((name, name.lower())) for ext in exts
                            if (d / f"{nm}{ext}").is_file() and (d / f"{nm}{ext}").resolve() not in chain), None)  # fmt: skip
                if hit is not None:
                    found.setdefault(hit.resolve(), hit)
            if len(found) > 1:
                raise CopyAmbiguous(
                    f"{where}: COPY {name} is ambiguous: no engine resolution decides it and "
                    f"{len(found)} directories hold it: {', '.join(sorted(map(str, found.values())))}"
                )
            if found:
                return next(iter(found.values()))
    return None


def expand(lines: list[Line], dirs: list[Path], depth: int = 0, chain: frozenset = frozenset(),
           engine: EngineCopies | None = None, expanded_names: set[str] | None = None) -> list[Line]:  # fmt: skip
    """COPY statements replaced by their members' lines (recursively); REPLACING ==a== BY ==b== and word-for-word
    `a BY b` applied. A member found nowhere raises CopyNotFound. `engine` (#4468): each COPY in an estate file takes
    the member the engine resolved (CopyUnresolved where it resolved none or several); without it, and for a member
    outside the estate, the first of `dirs` holding it. `expanded_names` collects the program's own members."""
    out: list[Line] = []
    own = str(engine.program) if engine is not None else None
    i = 0
    while i < len(lines):
        ln = lines[i]
        if _COPY_ALONE.search(ln.text) and not _open_literal(ln.text) and i + 1 < len(lines):
            # #4459: the member name on the next line
            ln = Line(ln.text.rstrip() + " " + lines[i + 1].text.lstrip(), ln.file, ln.line)
            lines = [*lines[:i], ln, *lines[i + 2 :]]
        m = _copy_match(ln.text)
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
                m = _copy_match(ln.text)
        if not m:
            out.append(ln)
            i += 1
            continue
        stmt, j = ln.text, i
        end = _statement_end(stmt, m.start())
        while end < 0 and j + 1 < len(lines):
            j += 1
            stmt += " " + lines[j].text
            end = _statement_end(stmt, m.start())
        tail = stmt[end:] if end > 0 else ""
        stmt = stmt[m.start() : end] if end > 0 else stmt[m.start() :]
        name = m.group(2).upper()
        # never a file being expanded already (the including program or copybook itself)
        # a copybook's extensions in every directory before a program's: CBSA keeps a program INQCUST.cbl next to
        # its sources and the copybook INQCUST.cpy elsewhere; never a file being expanded already
        where = f"{ln.file}:{ln.line}"
        member = engine.member(ln.file, name, m.group(3) and m.group(3).upper(), where) if engine is not None else None
        if member is not None and member.resolve() in chain:
            raise CopyNotFound(f"{where}: COPY {name} resolves to {member}, which is being expanded already")
        if member is None:
            member = _search_member(name, dirs, chain, where)
            if member is None and not unmasked("missing-copybook"):  # (a survey's what-if only: survey_unmask)
                raise CopyNotFound(f"{where}: COPY {name} found in none of {[str(d) for d in dirs]}")
            if member is not None and engine is not None and engine.in_estate(Path(ln.file)):
                engine.unresolved(ln.file, name, member, where)
        if depth > 8:
            raise CopyNotFound(f"{where}: COPY {name} nests deeper than 8")
        if engine is not None and ln.file == own and expanded_names is not None:
            expanded_names.add(name)
        expanded: list[Line] = []
        if member is not None:
            body = logical_lines(_raw_lines(member, engine), str(member))
            if any(_PROGRAM_MARK.match(b.text) for b in body):
                # #4460: a program, not a copybook: splicing it in would give the includer another program's records
                raise CopyNotFound(f"{where}: COPY {name} resolves to {member}, which is a program (IDENTIFICATION "
                                   "DIVISION / PROGRAM-ID), not a copybook")  # fmt: skip
            pairs = _replacing(stmt)
            if pairs:
                for b in body:
                    for old, new in pairs:
                        b.text = _replace(b.text, old, new)
            expanded = expand(body, dirs, depth + 1, chain | {member.resolve()}, engine)
        # the text before COPY on its line (rare: `01 X. COPY Y.`) and what follows the COPY's period stay
        head = ln.text[: m.start()]
        if head.strip():
            out.append(Line(head, ln.file, ln.line))
        out += expanded
        if tail.strip():  # what follows the COPY's period (`COPY A. COPY B.`) is read on
            lines = [*lines[: j + 1], Line(tail.lstrip(), ln.file, lines[j].line), *lines[j + 1 :]]
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


def program_lines(program: Path, dirs: list[Path], engine: EngineCopies | None = None) -> list[Line]:
    """The whole program, expanded. `engine` (#4468): every COPY in an estate file takes the member the engine
    resolved; refused (CopyUnresolved) where the engine resolved none or several, or a member it resolved for the
    program is never expanded (#4459)."""
    if engine is not None and engine.program != program:
        engine = engine.with_program(program)
    names: set[str] = set()
    out = expand(logical_lines(_raw_lines(program, engine), str(program)), [program.parent, *dirs],
                 chain=frozenset({program.resolve()}), engine=engine, expanded_names=names)  # fmt: skip
    if engine is not None:
        engine.check_all_expanded(names)
    return out


class UnitRefused(ValueError):
    """#4462: a program of a multi-program source the translator does not read on its own (a nested program that
    can see its container's GLOBAL items; END PROGRAM markers that do not nest)."""


@dataclass
class Unit:
    """#4462: one program of a source: its name (PROGRAM-ID's, upper case, unquoted), its own lines (from its
    IDENTIFICATION DIVISION up to its END PROGRAM, without the programs nested in it or the END PROGRAM markers) and
    the program containing it (None: an outermost program, the first or one compiled after it in a batch)."""

    name: str
    lines: list[Line]
    parent: str | None = None


_HEADER = re.compile(r"^\s*(?:IDENTIFICATION|ID)\s+DIVISION\s*\.", re.I)
_PROGRAM_ID = re.compile(r"^\s*PROGRAM-ID\s*\.?\s*(?:(['\"]?)([A-Z0-9#@$-]+)\1)?", re.I)
_END_PROGRAM = re.compile(r"^\s*END\s+PROGRAM\s+(['\"]?)([A-Z0-9#@$-]+)\1\s*\.?\s*$", re.I)


def program_units(lines: list[Line]) -> list[Unit]:
    """#4462: the programs of an expanded source, in source order (estate-crucible PAYMAIN: PAYCALC nested in it,
    PAYRPT batch-compiled after its END PROGRAM). A program begins at its IDENTIFICATION DIVISION (or a PROGRAM-ID
    with none before it); one beginning while another is open is nested in it; END PROGRAM closes the innermost open
    program, which it must name. A source of one program is one Unit holding `lines` as they are."""
    units: list[Unit] = []
    stack: list[Unit] = []
    pending: list[Line] = []  # an IDENTIFICATION DIVISION header, its PROGRAM-ID still to come
    want_name: Unit | None = None  # `PROGRAM-ID.` with its name on the next line
    for ln in lines:
        if want_name is not None:
            m = re.match(r"\s*(['\"]?)([A-Z0-9#@$-]+)\1", ln.text, re.I)
            want_name.name, want_name = (m.group(2).upper() if m else "?"), None
            stack[-1].lines.append(ln)
            continue
        if _HEADER.match(ln.text):
            pending.append(ln)
            continue
        pid = _PROGRAM_ID.match(ln.text)
        if pid:
            u = Unit(pid.group(2).upper() if pid.group(2) else "?", [*pending, ln], stack[-1].name if stack else None)
            pending = []
            if not pid.group(2):
                want_name = u
            units.append(u)
            stack.append(u)
            continue
        if pending:  # a header with no PROGRAM-ID after it: no program boundary the units can be cut at
            return [Unit(units[0].name if units else "?", lines)]
        end = _END_PROGRAM.match(ln.text)
        if end:
            name = end.group(2).upper()
            if not stack or stack[-1].name != name:
                raise UnitRefused(f"{Path(ln.file).name}:{ln.line}: END PROGRAM {name} closes no open program of "
                                  f"that name ({', '.join(u.name for u in stack) or 'none open'})")  # fmt: skip
            stack.pop()
            continue
        if not stack:
            if not units:  # text before any program (no IDENTIFICATION DIVISION / PROGRAM-ID): one unit, as read
                return [Unit("?", lines)]
            raise UnitRefused(f"{Path(ln.file).name}:{ln.line}: text after END PROGRAM {units[-1].name}, outside "
                              "any program")  # fmt: skip
        stack[-1].lines.append(ln)
    if len(units) <= 1 or pending:
        return [Unit(units[0].name if units else "?", lines)]
    return units


_GLOBAL = re.compile(r"\bGLOBAL\b", re.I)


def program_unit(lines: list[Line], name: str | None = None) -> list[Line]:
    """#4462: the lines of one program of a source (`name`: its PROGRAM-ID; None: the first). A nested program whose
    containers declare GLOBAL items (or files) is refused: it can name them, and its own lines do not hold them."""
    if lines and not any(_PROGRAM_ID.match(ln.text) for ln in lines):
        raise UnitRefused(f"{Path(lines[0].file).name}: no PROGRAM-ID: a member to be copied, not a program")
    units = program_units(lines)
    want = units[0].name if name is None else name.upper()
    unit = next((u for u in units if u.name == want), None)
    if unit is None:
        raise UnitRefused(f"no program {want} in the source (it holds {', '.join(u.name for u in units)})")
    by_name = {u.name: u for u in units}
    parent = unit.parent
    while parent is not None:
        up = by_name[parent]
        hit = next((ln for ln in up.lines if _GLOBAL.search(_outside_literals(ln.text))), None)
        if hit is not None:
            raise UnitRefused(f"{Path(hit.file).name}:{hit.line}: {unit.name} is nested in {up.name}, which declares "
                              "GLOBAL items: a nested program's view of its container's GLOBAL data is not modelled")  # fmt: skip
        parent = up.parent
    return unit.lines


def several_programs(lines: list[Line]) -> str | None:
    """#4462: why `lines` cannot be read as one program (they hold several: each is read on its own, program_unit),
    or None."""
    try:
        units = program_units(lines)
    except UnitRefused as e:
        return str(e)
    if len(units) > 1:
        return (f"several programs in one source ({', '.join(u.name for u in units)}): each is translated on its own "
                "(det.source.program_unit)")  # fmt: skip
    return None


def engine_copies_from_ticket(project: Path, program: Path, strict: bool = False) -> EngineCopies | None:
    """#4468: the engine's resolution of `program`'s COPYs from the port ticket the generator wrote for it
    (ai_agent_jobs/*_port_ticket.json, repo-relative): the skeleton's `copy_edges` (every estate file the program's
    COPYs reach, with library-names) and its gaps and collisions; a ticket without them (written before #4468): the
    program's own copybooks. None where no ticket names the program (the translator then searches `dirs`).
    `copy_pages` (#4462): the code pages the scan decoded the program and its members with. `strict` (#4486):
    refuse a SYSLIB collision instead of taking the first library's member (EngineCopies.strict)."""
    jobs = project / "ai_agent_jobs"
    if not jobs.is_dir():
        return None
    target = program.resolve().as_posix()
    import json

    for t in sorted(jobs.glob("*_port_ticket.json")):
        try:
            doc = json.loads(t.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        src = doc.get("source") or {}
        rel = (src.get("program") or {}).get("file")
        if not rel or not target.endswith("/" + rel.replace("\\", "/")):
            continue
        root = Path(target[: -len(rel) - 1])
        facts = (doc.get("facts") or {}).get("program") or {}
        edges = facts.get("copy_edges")
        if edges is None:
            edges = {rel: [c.get("file") or "" for c in src.get("copybooks") or [] if c.get("file")]}
        return EngineCopies.of(program, root, edges, [tuple(g) for g in facts.get("copy_gaps") or []],
                               [tuple(c) for c in facts.get("copy_collisions") or []],
                               facts.get("copy_pages"), strict)  # fmt: skip
    return None


WIDTH = 65  # columns 8-72


def as_fixed(lines: list[Line]) -> str:
    """The lines as fixed-format source again (for a parser): seven blank columns, then the text."""
    return as_fixed_rows(lines)[0]


def as_fixed_rows(lines: list[Line]) -> tuple[str, list[int]]:
    """as_fixed's text, and for each of its rows the index in `lines` it came from. A line longer than columns
    8-72 (a joined continuation) is wrapped back into fixed form (#4412): split at a space outside literals, or a
    literal open at column 72 continued on the next row ('-' in column 7, the quote again in column 10). The
    grammar fails on a line run past column 72; `unwrap` joins the continued literal again. #4523: the grammar
    continues a literal only in quotation marks, so a wrapped line's apostrophe literals are written in them (same
    value), and reads `""` inside one only as QQ (`_grammar_literals`); #4462: it continues no hex literal, so a
    wrapped line's X"C1C2" is written "<HX>C1C2" (`unwrap` restores it); an EXEC block's line keeps its own text (in
    SQL an apostrophe is a string, a quotation mark a name)."""
    out: list[str] = []
    rows: list[int] = []
    in_exec = False
    for k, ln in enumerate(lines):
        bare = _outside_literals(ln.text)
        opens = _EXEC.search(bare)
        # SQL / CICS text keeps its own quote style (the grammar never reads it: blanked, or a placeholder CALL)
        code = ln.text if in_exec or opens else _grammar_literals(ln.text, apostrophes=len(ln.text) > WIDTH)
        wrapped = _wrap(code) if len(code) > WIDTH else ["       " + code]
        for row in wrapped:
            out.append(row + "\n")
            rows.append(k)
        if opens or in_exec:
            in_exec = not _END_EXEC.search(bare[opens.end() :] if opens else bare)
    return "".join(out), rows


_EXEC = re.compile(r"\bEXEC(?:UTE)?\s+(?:CICS|SQL|DLI)\b", re.I)
_END_EXEC = re.compile(r"\bEND-EXEC\b", re.I)


def _grammar_literals(text: str, apostrophes: bool) -> str:
    """`text` with each quotation-mark literal's doubled `""` written QQ, and (`apostrophes`) each apostrophe
    literal written in quotation marks, its value unchanged (`''` undoubled, a `"` written QQ): the grammar continues
    a literal only in quotation marks, and every reader of a literal takes its delimiter from its first character
    (expr._unquote, layout._one). An unterminated literal is kept as it is. #4462: a hex literal's `x` is written
    `X` (the grammar reads no x'00': GenApp lgtestc1's INSPECT ... REPLACING ALL x'00' BY x'40')."""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        q = text[i]
        hexa = (q in "'\"" and len(out) > 0 and out[-1] in ("x", "X")
                and not re.match(r"[\w-]", out[-2][-1:] if len(out) > 1 else " "))  # fmt: skip
        if hexa:
            out[-1] = "X"
        if q not in "'\"" or (q == "'" and not apostrophes):
            if q == "'":  # an apostrophe literal kept: copied whole (a `"` inside it is its own)
                j = i + 1
                while j < n and not (text[j] == "'" and text[j + 1 : j + 2] != "'"):
                    j += 2 if text[j] == "'" else 1
                out.append(text[i : j + 1])
                i = j + 1
                continue
            out.append(q)
            i += 1
            continue
        j, value = i + 1, []
        while j < n:
            if text[j] == q:
                if text[j + 1 : j + 2] != q:
                    break
                j += 1
            value.append(text[j])
            j += 1
        if j >= n:  # unterminated: as it is
            out.append(text[i:])
            break
        if (
            hexa and apostrophes
        ):  # #4462: X'C1C2' -> "<HX>C1C2", a literal the grammar continues (`unwrap` restores X"C1C2")
            out[-1] = '"' + HX
        else:
            out.append('"')
        out.append("".join(value).replace('"', QQ) + '"')
        i = j + 1
    return "".join(out)


def _wrap(text: str) -> list[str]:
    rows: list[str] = []
    rest, cont = text, False
    while True:
        lead = "      -  " if cont else "       "
        lim = 72 - len(lead)
        if len(rest) <= lim:
            return [*rows, lead + rest]
        quote, last_space, closed = None, -1, -1
        for i, ch in enumerate(rest[:lim]):
            if quote:
                quote, closed = (None, i) if ch == quote else (quote, closed)
            elif ch in "'\"":
                quote = ch
            elif ch == " ":
                last_space = i
        if quote is None and closed == lim - 1 and rest[lim : lim + 1] == rest[closed]:
            # #4523: column 72 holds the first of a doubled quote: the literal is still open; the row ends a column
            # early so the pair stays together on the next (the grammar's row is short; `unwrap` joins it exactly)
            rows.append(lead + rest[: lim - 1])
            rest, cont = rest[closed] + rest[lim - 1 :], True
            continue
        if quote is not None:  # the literal runs to column 72 and reopens on the next row
            rows.append(lead + rest[:lim])
            rest, cont = quote + rest[lim:], True
            continue
        k = last_space if last_space > 0 else lim
        rows.append(lead + rest[:k])
        rest, cont = rest[k:].lstrip(" "), False


_CONTINUED = re.compile(r"\n {6}-\s*['\"]")


def unwrap(text: str) -> str:
    """Parser text with as_fixed_rows' literal continuations joined again (a continued literal's own text), and its
    stand-ins (QQ, HX) back as `""` and `X"`."""
    return _CONTINUED.sub("", text).replace(QQ, '""').replace('"' + HX, 'X"')


# #4462: the COBOL-74 / OS/VS alphabet clause, `alphabet-name IS {literal ... | STANDARD-1 | NATIVE ...}` with no
# ALPHABET keyword (IBM OS/VS COBOL; DSF PLUKKFR's `IDIOT IS 'ABCDEFGHIJKLMNOPQRSTUVWXYZÆØÅ'`)
_SPECIAL_NAMES = re.compile(r"^\s*SPECIAL-NAMES\s*\.", re.I)
_SPECIAL_TOKEN = re.compile(r"'[^']*'?|\"[^\"]*\"?|[A-Z0-9][A-Z0-9-]*|\S", re.I)
_ALPHABET_NAMED = {"STANDARD-1", "STANDARD-2", "NATIVE", "EBCDIC", "ASCII"}
# words before IS that never name an alphabet: other clauses' (CURRENCY SIGN IS '$', CLASS c IS 'A' THRU 'Z',
# ALPHABET a FOR ALPHANUMERIC IS ...); an alphabet already introduced by ALPHABET
_NOT_ALPHABET_NAMES = {"CURRENCY", "SIGN", "DECIMAL-POINT", "ALPHANUMERIC", "NATIONAL", "SYMBOLIC", "CHARACTERS"}
_NOT_AFTER = {"ALPHABET", "CLASS", "CURRENCY", "SYMBOLIC", "CHARACTERS"}


def alphabet_keywords(lines: list[Line]) -> list[Line]:
    """#4462: `lines` with ALPHABET written before each alphabet clause of SPECIAL-NAMES that has none (the OS/VS
    COBOL form IBM's compilers accept; the grammar and program.alphabets read only `ALPHABET name IS ...`). A clause
    is an alphabet when a name not introduced by another clause's word is followed by IS and a literal or STANDARD-1
    / STANDARD-2 / NATIVE / EBCDIC / ASCII (a mnemonic, `C01 IS KANAL-1`, is followed by a name). Other lines are
    the same objects."""
    out = list(lines)
    k = next((i for i, ln in enumerate(lines) if _SPECIAL_NAMES.match(ln.text)), None)
    if k is None:
        return out
    toks: list[tuple[int, int, str]] = []  # (line index, column, token) up to the paragraph's period
    first = True
    for i in range(k, len(lines)):
        text = lines[i].text
        start = _SPECIAL_NAMES.match(text).end() if first else 0  # type: ignore[union-attr]
        first = False
        ended = False
        for m in _SPECIAL_TOKEN.finditer(text, start):
            if m.group(0) == ".":
                ended = True
                break
            toks.append((i, m.start(), m.group(0)))
        if ended:
            break
    inserts: dict[int, list[int]] = {}
    for j in range(len(toks) - 2):
        w, nxt, obj = toks[j][2].upper(), toks[j + 1][2].upper(), toks[j + 2][2]
        if nxt != "IS" or not w[:1].isalpha() or w in _NOT_ALPHABET_NAMES:
            continue
        if j > 0 and toks[j - 1][2].upper() in _NOT_AFTER:
            continue
        if obj[:1] in "'\"" or obj.upper() in _ALPHABET_NAMED:
            inserts.setdefault(toks[j][0], []).append(toks[j][1])
    for i, cols in inserts.items():
        text = lines[i].text
        for c in sorted(cols, reverse=True):
            text = text[:c] + "ALPHABET " + text[c:]
        out[i] = Line(text, lines[i].file, lines[i].line)
    return out


# #4462: LABEL RECORD ARE / LABEL RECORDS IS (IBM accepts IS or ARE with either; the grammar wants RECORD IS /
# RECORDS ARE): the optional word dropped, at the same length
_LABEL_RECORDS = re.compile(r"\b(LABEL\s+RECORDS?)(\s+(?:IS|ARE))\b", re.I)


def label_records(text: str) -> str:
    """#4462: `text` with LABEL RECORD[S] IS / ARE written LABEL RECORD[S] and blanks (DSF FO04D1X1's `LABEL RECORD
    ARE STANDARD`), outside literals."""
    bare = _outside_literals(text)
    for m in reversed(list(_LABEL_RECORDS.finditer(bare))):
        text = text[: m.start(2)] + " " * len(m.group(2)) + text[m.end(2) :]
    return text


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


def engine_copies_from_ir(ir, rel: str, root: Path, strict: bool = False) -> EngineCopies | None:
    """#4468: the engine's resolution of every COPY the program at `rel` (repo-relative) reaches, from GalaxyIR
    (GalaxyIR.copy_resolution). None: no such file. `strict` (#4486): EngineCopies.strict."""
    if ir.files.get(rel) is None:
        return None
    res = ir.copy_resolution(rel)
    return EngineCopies.of(root / rel, root, res["edges"], [tuple(g) for g in res["gaps"]],
                           [tuple(c) for c in res["collisions"]], ir.copy_pages(rel), strict)  # fmt: skip
