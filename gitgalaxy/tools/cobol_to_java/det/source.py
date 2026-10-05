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


class CopyDisagrees(CopyNotFound):
    """#4467: the translator's resolution of a COPY is not the engine's (the program is refused by name)."""


@dataclass(frozen=True)
class EngineCopies:
    """#4467: the engine's resolution of a program's own COPY statements (the scan's copy_deps: GalaxyIR, or the port
    ticket the generator wrote from it). The translator's first-hit directory search is independent of the engine's
    resolver (copy libraries, SYSLIB order, COPY ... IN, collisions and gaps: #4265, #4420); until the translator
    takes the engine's resolution (#4461), a program where the two differ is refused rather than built on a member
    the engine did not choose (#4459 a COPY not expanded, #4460 a program spliced in, #4461 the wrong library).

    `root`: the estate the engine scanned (its paths are relative to it). `resolved`: member -> the files the
    engine resolved for the program's COPY of it. `gaps` / `collisions`: the members the engine reports no declared
    library holds, or several do (#4421; only when the scan declared copy libraries)."""

    program: Path
    root: Path
    resolved: dict[str, tuple[Path, ...]]
    gaps: frozenset[str] = frozenset()
    collisions: frozenset[str] = frozenset()

    def rel(self, p: Path) -> str:
        try:
            return p.resolve().relative_to(self.root.resolve()).as_posix()
        except ValueError:
            return str(p)

    def check(self, name: str, member: Path, where: str) -> None:
        """One COPY of the program's own: the member the translator found against the engine's."""
        in_estate = self.rel(member) != str(member)  # (else a system or generated member: the engine has none)
        if name in self.collisions:
            raise CopyDisagrees(f"{where}: COPY {name}: the engine records a collision (several libraries hold it)")
        if name in self.gaps and in_estate:  # (a gap the translator fills from its system members: SQLCA, DFHAID)
            raise CopyDisagrees(f"{where}: COPY {name}: the engine records a gap (no declared library holds it), "
                                f"translator resolved {self.rel(member)}")  # fmt: skip
        engine = self.resolved.get(name, ())
        if not engine:
            if in_estate:
                raise CopyDisagrees(f"{where}: COPY {name}: translator resolved {self.rel(member)}, "
                                    "engine resolved nothing")  # fmt: skip
            return
        if member.resolve() not in {e.resolve() for e in engine}:
            raise CopyDisagrees(f"{where}: COPY {name}: translator resolved {self.rel(member)}, engine resolved "
                                f"{', '.join(sorted(self.rel(e) for e in engine))}")  # fmt: skip

    def check_all_expanded(self, expanded: set[str]) -> None:
        """Every member the engine resolved for the program was expanded by the translator (#4459)."""
        for name in sorted(set(self.resolved) - expanded):
            raise CopyDisagrees(f"{self.program}: COPY {name}: engine resolved "
                                f"{', '.join(sorted(self.rel(e) for e in self.resolved[name]))}, "
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


_COPY = re.compile(r"^\s*COPY\s+(['\"]?)([A-Z0-9#@$-]+)\1(?:\s+(?:OF|IN)\s+[A-Z0-9-]+)?\s*(.*)$", re.I)


def expand(lines: list[Line], dirs: list[Path], depth: int = 0, chain: frozenset = frozenset(),
           engine: EngineCopies | None = None, expanded_names: set[str] | None = None) -> list[Line]:  # fmt: skip
    """COPY statements replaced by their members' lines (recursively); REPLACING ==a== BY ==b== and word-for-word
    `a BY b` applied. A member found nowhere raises CopyNotFound. `engine` (#4467): each COPY in the engine's program
    is checked against the engine's resolution (CopyDisagrees); `expanded_names` collects the members it expanded."""
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
        member = next((d / f"{nm}{ext}" for exts in (COPYBOOK_EXTS, PROGRAM_EXTS) for d in dirs
                       for nm in dict.fromkeys((name, name.lower())) for ext in exts
                       if (d / f"{nm}{ext}").is_file() and (d / f"{nm}{ext}").resolve() not in chain), None)  # fmt: skip
        if member is None:
            raise CopyNotFound(f"{ln.file}:{ln.line}: COPY {name} found in none of {[str(d) for d in dirs]}")
        if depth > 8:
            raise CopyNotFound(f"{ln.file}:{ln.line}: COPY {name} nests deeper than 8")
        if engine is not None and ln.file == own:
            engine.check(name, member, f"{ln.file}:{ln.line}")
            if expanded_names is not None:
                expanded_names.add(name)
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


def program_lines(program: Path, dirs: list[Path], engine: EngineCopies | None = None) -> list[Line]:
    """The whole program, expanded. `engine` (#4467): refused (CopyDisagrees) where a COPY of the program's own
    resolves otherwise than the engine resolved it, or a member the engine resolved is never expanded."""
    if engine is not None:
        engine = EngineCopies(program, engine.root, engine.resolved, engine.gaps, engine.collisions)
    names: set[str] = set()
    out = expand(logical_lines(_raw_lines(program), str(program)), [program.parent, *dirs],
                 chain=frozenset({program.resolve()}), engine=engine, expanded_names=names)  # fmt: skip
    if engine is not None:
        engine.check_all_expanded(names)
    return out


def engine_copies_from_ticket(project: Path, program: Path) -> EngineCopies | None:
    """#4467: the engine's resolution of `program`'s COPYs from the port ticket the generator wrote for it
    (ai_agent_jobs/*_port_ticket.json: source.program.file and the copybooks the scan resolved, repo-relative). None
    where no ticket names the program (nothing to compare against)."""
    jobs = project / "ai_agent_jobs"
    if not jobs.is_dir():
        return None
    target = program.resolve().as_posix()
    import json

    for t in sorted(jobs.glob("*_port_ticket.json")):
        try:
            src = json.loads(t.read_text(encoding="utf-8")).get("source") or {}
        except (OSError, ValueError):
            continue
        rel = (src.get("program") or {}).get("file")
        if not rel or not target.endswith("/" + rel.replace("\\", "/")):
            continue
        root = Path(target[: -len(rel) - 1])
        resolved: dict[str, list[Path]] = {}
        for c in src.get("copybooks") or []:
            f = c.get("file") or ""
            if f and "#" not in f:
                resolved.setdefault(Path(f).stem.upper(), []).append(root / f)
        return EngineCopies(program, root, {k: tuple(v) for k, v in resolved.items()})
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
    """#4467: the engine's resolution of the program at `rel` (repo-relative) from GalaxyIR: its copy_deps, and the
    collisions and gaps the scan reported for it (#4421: only when it declared copy libraries). None: no such file."""
    ef = ir.files.get(rel)
    if ef is None:
        return None
    resolved: dict[str, list[Path]] = {}
    for dep in ef.copy_deps:
        if "#" not in dep:
            resolved.setdefault(Path(dep).stem.upper(), []).append(root / dep)
    mine = [r for r in (ir.copy_member_collisions or []) if r.get("importer") == rel]
    gaps = [r for r in (ir.copy_member_gaps or []) if r.get("importer") == rel]
    return EngineCopies(root / rel, root, {k: tuple(v) for k, v in resolved.items()},
                        frozenset(str(r["member"]).upper() for r in gaps),
                        frozenset(str(r["member"]).upper() for r in mine))  # fmt: skip
