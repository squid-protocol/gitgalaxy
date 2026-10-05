"""A fixed-format COBOL program as the translator reads it: COPY members expanded (with REPLACING), comment and
debugging lines dropped, continued literals joined. Every logical line keeps where it came from."""

from __future__ import annotations

import re
from dataclasses import dataclass
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


class CopyNotFound(Exception):
    pass


class CopyUnresolved(CopyNotFound):
    """#4468: a COPY the engine did not resolve to one file (a gap, a collision, several files), or that the translator
    never expanded where the engine resolved it: the program is refused by name, never built on a guessed member."""


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
    holds, or several do (#4421; only when the scan declared copy libraries)."""

    program: Path
    root: Path
    edges: dict[str, dict[str, tuple[tuple[Path, frozenset[str]], ...]]]
    gaps: frozenset[tuple[str, str]] = frozenset()
    collisions: frozenset[tuple[str, str]] = frozenset()

    @classmethod
    def of(cls, program: Path, root: Path, deps: dict[str, dict[str, list[str]] | list[str]],
           gaps=(), collisions=()) -> EngineCopies:  # fmt: skip
        """From importer -> its resolved COPY files (repo-relative; a list, or file -> library-names). A symbolic
        map generated from BMS (`map.bms#MAPSET`) is not an estate file: the translator generates its own."""
        edges: dict[str, dict[str, list[tuple[Path, frozenset[str]]]]] = {}
        for imp, files in deps.items():
            mine = edges.setdefault(imp, {})
            for f in files:
                if not re.search(r"\.bms#[^/]*$", f, re.I):
                    libs = files.get(f) if isinstance(files, dict) else None
                    mine.setdefault(Path(f).stem.upper(), []).append((root / f, frozenset(libs or ())))
        return cls(program, root, {i: {m: tuple(v) for m, v in e.items()} for i, e in edges.items()},
                   frozenset((i, m.upper()) for i, m in gaps), frozenset((i, m.upper()) for i, m in collisions))  # fmt: skip

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

    def in_estate(self, p: Path) -> bool:
        return self.rel(p) != str(p)

    def member(self, importer: str, name: str, library: str | None, where: str) -> Path | None:
        """The file the engine resolved `COPY name [IN library]` in `importer` to. None: the engine resolved nothing
        for it -- a system or generated member outside the estate (DFHAID, SQLCA, a BMS symbolic map), which the
        caller then finds itself; an estate file it would find instead is refused (`unresolved`)."""
        imp = self.rel(Path(importer))
        if (imp, name) in self.collisions:
            raise CopyUnresolved(f"{where}: COPY {name}: the engine records a collision (several libraries hold it)")
        hits = self.edges.get(imp, {}).get(name, ())
        if len(hits) > 1:  # #4265: `COPY X` and `COPY X IN LIB` in one file reach two files; the COPY's own form picks
            hits = tuple(h for h in hits if (library or "") in h[1]) or hits
        if len(hits) > 1:
            raise CopyUnresolved(f"{where}: COPY {name}: the engine resolved several files: "
                                 f"{', '.join(sorted(self.rel(f) for f, _ in hits))}")  # fmt: skip
        return hits[0][0] if hits else None

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


def _raw_lines(path: Path) -> list[str]:
    return read_source(path).text.splitlines()


_ID_DIVISION = re.compile(r"^(\s*)ID\s+DIVISION(?=\s*\.)", re.I)


def logical_lines(raw: list[str], file: str) -> list[Line]:
    """Columns 8-72 of each code line; comment (* /), debugging (D) and blank lines dropped; a continuation line
    (indicator '-') joined to the line before: a continued literal resumes after the continuation's first quote."""
    out: list[Line] = []
    # Compiler-option cards (CBL / PROCESS, before the program or after an END PROGRAM) are not COBOL text. The
    # engine's own reader decides which lines they are: a card may start in any column from 1, so IBM DBB's
    # `   CBL NUMPROC(MIG),...` (CBL in columns 4-6) is one, as GenApp's `       PROCESS SQL` is.
    card_lines = {n for n, _ in cards("\n".join(raw))}
    for n, line in enumerate(raw, 1):
        if n in card_lines:
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
        if not body.strip():
            continue
        if _ID_DIVISION.match(body):
            # `ID DIVISION.`: IBM's abbreviation of IDENTIFICATION DIVISION (IBM DBB MortgageApplication), which the
            # parser downstream knows only in full
            body = _ID_DIVISION.sub(lambda m: m.group(1) + "IDENTIFICATION DIVISION", body, count=1)
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


_COPY = re.compile(r"^\s*COPY\s+(['\"]?)([A-Z0-9#@$-]+)\1(?:\s+(?:OF|IN)\s+([A-Z0-9-]+))?\s*(.*)$", re.I)


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
        # a copybook's extensions in every directory before a program's: CBSA keeps a program INQCUST.cbl next to
        # its sources and the copybook INQCUST.cpy elsewhere; never a file being expanded already
        where = f"{ln.file}:{ln.line}"
        member = engine.member(ln.file, name, m.group(3) and m.group(3).upper(), where) if engine is not None else None
        if member is not None and member.resolve() in chain:
            raise CopyNotFound(f"{where}: COPY {name} resolves to {member}, which is being expanded already")
        if member is None:
            member = next((d / f"{nm}{ext}" for exts in (COPYBOOK_EXTS, PROGRAM_EXTS) for d in dirs
                           for nm in dict.fromkeys((name, name.lower())) for ext in exts
                           if (d / f"{nm}{ext}").is_file() and (d / f"{nm}{ext}").resolve() not in chain), None)  # fmt: skip
            if member is None:
                raise CopyNotFound(f"{where}: COPY {name} found in none of {[str(d) for d in dirs]}")
            if engine is not None and engine.in_estate(Path(ln.file)):
                engine.unresolved(ln.file, name, member, where)
        if depth > 8:
            raise CopyNotFound(f"{where}: COPY {name} nests deeper than 8")
        if engine is not None and ln.file == own and expanded_names is not None:
            expanded_names.add(name)
        body = logical_lines(_raw_lines(member), str(member))
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
        engine = EngineCopies(program, engine.root, engine.edges, engine.gaps, engine.collisions)
    names: set[str] = set()
    out = expand(logical_lines(_raw_lines(program), str(program)), [program.parent, *dirs],
                 chain=frozenset({program.resolve()}), engine=engine, expanded_names=names)  # fmt: skip
    if engine is not None:
        engine.check_all_expanded(names)
    return out


def engine_copies_from_ticket(project: Path, program: Path) -> EngineCopies | None:
    """#4468: the engine's resolution of `program`'s COPYs from the port ticket the generator wrote for it
    (ai_agent_jobs/*_port_ticket.json, repo-relative): the skeleton's `copy_edges` (every estate file the program's
    COPYs reach, with library-names) and its gaps and collisions; a ticket without them (written before #4468): the
    program's own copybooks. None where no ticket names the program (the translator then searches `dirs`)."""
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
                               [tuple(c) for c in facts.get("copy_collisions") or []])  # fmt: skip
    return None


WIDTH = 65  # columns 8-72


def as_fixed(lines: list[Line]) -> str:
    """The lines as fixed-format source again (for a parser): seven blank columns, then the text."""
    return as_fixed_rows(lines)[0]


def as_fixed_rows(lines: list[Line]) -> tuple[str, list[int]]:
    """as_fixed's text, and for each of its rows the index in `lines` it came from. A line longer than columns
    8-72 (a joined continuation) is wrapped back into fixed form (#4412): split at a space outside literals, or a
    literal open at column 72 continued on the next row ('-' in column 7, the quote again in column 10). The
    grammar fails on a line run past column 72; `unwrap` joins the continued literal again."""
    out: list[str] = []
    rows: list[int] = []
    for k, ln in enumerate(lines):
        for row in _wrap(ln.text) if len(ln.text) > WIDTH else ["       " + ln.text]:
            out.append(row + "\n")
            rows.append(k)
    return "".join(out), rows


def _wrap(text: str) -> list[str]:
    rows: list[str] = []
    rest, cont = text, False
    while True:
        lead = "      -  " if cont else "       "
        lim = 72 - len(lead)
        if len(rest) <= lim:
            return [*rows, lead + rest]
        quote, last_space = None, -1
        for i, ch in enumerate(rest[:lim]):
            if quote:
                quote = None if ch == quote else quote
            elif ch in "'\"":
                quote = ch
            elif ch == " ":
                last_space = i
        if quote is not None:  # the literal runs to column 72 and reopens on the next row
            rows.append(lead + rest[:lim])
            rest, cont = quote + rest[lim:], True
            continue
        k = last_space if last_space > 0 else lim
        rows.append(lead + rest[:k])
        rest, cont = rest[k:].lstrip(" "), False


_CONTINUED = re.compile(r"\n {6}-\s*['\"]")


def unwrap(text: str) -> str:
    """Parser text with as_fixed_rows' literal continuations joined again (a continued literal's own text)."""
    return _CONTINUED.sub("", text)


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


def engine_copies_from_ir(ir, rel: str, root: Path) -> EngineCopies | None:
    """#4468: the engine's resolution of every COPY the program at `rel` (repo-relative) reaches, from GalaxyIR
    (GalaxyIR.copy_resolution). None: no such file."""
    if ir.files.get(rel) is None:
        return None
    res = ir.copy_resolution(rel)
    return EngineCopies.of(root / rel, root, res["edges"], [tuple(g) for g in res["gaps"]],
                           [tuple(c) for c in res["collisions"]])  # fmt: skip
