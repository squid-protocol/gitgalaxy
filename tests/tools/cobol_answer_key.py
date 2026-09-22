"""
#3210: the COBOL modernization answer key -- hand-verified, per-program truth for
real mainframe corpora -- and the scorer that measures the refraction ("forge")
tools and the engine's master DB against it.

    python tests/tools/cobol_answer_key.py draft <repo> --corpus NAME --url URL --ref SHA \
        --out key.json [--report why.md]
    python tests/tools/cobol_answer_key.py score <repo> --key key.json [--db master.db] [--md out.md]

AUTHORITY. `draft` computes CANDIDATE values with its own fixed-format reading
(Area A headers, PERFORM ... THRU, GO TO, SECTION fall-through, terminal
statements, zapp.yaml copybook libraries). It is a helper for the human pass,
not the key: every `dead` verdict, every value where the draft, the forge and
the engine disagree, and a spot sample of agreements are checked against the
source, and the program's `verification.status` becomes `validated` with notes.
A key file whose programs are still `draft` is not evidence of anything.

This is a test tool. It is deliberately NOT shared with, or imported by, either
parser it grades.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

SCHEMA_VERSION = 1
PROGRAM_EXTS = (".cbl", ".cob", ".cobol", ".ccp")
COPYBOOK_EXTS = (".cpy", ".copy")

NAME = r"[A-Z0-9][A-Z0-9-]*"
_HEADER = re.compile(rf"^({NAME})(?:\s+(SECTION)(?:\s+[0-9]{{1,2}})?)?\s*\.(?:\s|$)")
# Words that can sit in Area A followed by a period without being a unit header.
_NOT_A_HEADER = {"DECLARATIVES", "END", "EXIT", "GOBACK", "CONTINUE", "STOP", "ELSE"}
_PERFORM = re.compile(rf"\bPERFORM\s+({NAME})(?:\s+(?:THRU|THROUGH)\s+({NAME}))?")
_GOTO = re.compile(rf"\bGO\s+(?:TO\s+)?((?:{NAME}\s*)+)")
_SENTENCE_END = re.compile(r"\.(?=\s|$)")
_TERMINAL_TAIL = re.compile(rf"(?:\bGOBACK|\bSTOP\s+RUN|\bEXIT\s+PROGRAM|\bGO\s+(?:TO\s+)?{NAME})\s*$")
_SELECT = re.compile(rf"\bSELECT\s+(?:OPTIONAL\s+)?({NAME})\s+ASSIGN\s+(?:TO\s+)?([A-Z0-9@#$-]+)")
_OPEN_MODES = {"INPUT", "OUTPUT", "I-O", "EXTEND"}
_CALL = re.compile(r"\bCALL\s+")
_CICS_PROGRAM = re.compile(r"\bEXEC\s+CICS\s+(LINK|XCTL)\b")
# CICS transfers control to these labels itself (on an abend, a condition or an
# attention key), so a unit named in one is reachable with no PERFORM or GO TO.
_CICS_HANDLE = re.compile(r"\bEXEC\s+CICS\s+HANDLE\s+(?:ABEND|CONDITION|AID)\b(.{0,600}?)\bEND-EXEC", re.S)
_COPY = re.compile(r"(?:^|\s)COPY\s+['\"]?([A-Z0-9@#$-]+)['\"]?(?:\s+(?:IN|OF)\s+([A-Z0-9@#$-]+))?")
_SQL_INCLUDE = re.compile(r"\bEXEC\s+SQL\s+INCLUDE\s+([A-Z0-9@#$-]+)")
_SYSTEM_COPY = (
    ("DFH", "CICS-supplied"),
    ("CEE", "Language Environment-supplied"),
    ("SQLCA", "DB2 precompiler-supplied"),
    ("SQLDA", "DB2 precompiler-supplied"),
)

# #3246: DATA DIVISION record layouts, read with THIS tool's own fixed-format
# model (Source), independent of both the engine's mainframe_boundary walker and
# the forge's cobol_schema_forge -- so the key can adjudicate a record delta
# between them. Each clause is read inside one entry (level number to the next).
_DATA_DIVISION = re.compile(r"\bDATA\s+DIVISION\b")
_PROC_DIVISION = re.compile(r"\bPROCEDURE\s+DIVISION\b")
_DD_SECTION = re.compile(r"\b(FILE|WORKING-STORAGE|LOCAL-STORAGE|LINKAGE|COMMUNICATION|REPORT|SCREEN)\s+SECTION\b")
_DD_FD = re.compile(rf"^\s*(?:FD|SD)\s+({NAME})", re.M)
_DD_LEVEL = re.compile(rf"^\s*(\d{{1,2}})\s+({NAME})(?![A-Z0-9-])", re.M)
_DD_PIC = re.compile(r"\bPIC(?:TURE)?\s+(?:IS\s+)?([-A-Z0-9(),.$/*+]+)")
_DD_USAGE = re.compile(
    r"(?:\bUSAGE\s+(?:IS\s+)?)?(?<![A-Z0-9-])"
    r"(COMPUTATIONAL(?:-[1-6])?|COMP(?:-[1-6])?|BINARY|PACKED-DECIMAL|DISPLAY(?:-1)?|INDEX|POINTER)(?![A-Z0-9-])"
)
_DD_OCCURS = re.compile(r"\bOCCURS\s+(\d+)(?:\s+TO\s+(\d+))?")
_DD_DEPENDING = re.compile(rf"\bDEPENDING\s+(?:ON\s+)?({NAME})")
_DD_REDEFINES = re.compile(rf"\bREDEFINES\s+({NAME})")
_DD_VALUE = re.compile(r"\bVALUE\s+(?:IS\s+)?(?:'([^']*)'|\"([^\"]*)\"|([A-Z0-9][A-Z0-9+.-]*))")
_DD_ENTRY_LIMIT = 600


# ==============================================================================
# Source reading (fixed reference format: cols 1-6 sequence, 7 indicator,
# 8-11 Area A, 12-72 Area B)
# ==============================================================================
def _blank_literals(text: str) -> str:
    """Replaces the inside of '...' and "..." literals with spaces, preserving offsets.

    Quote state resets at every newline: a fixed-format literal cannot span lines
    except by an explicit column-7 continuation, whose next line reopens the quote.
    Without the reset, `AUTHOR. James O'Grady.` (CBSA) blanked the rest of the file."""
    out, quote = [], None
    for ch in text:
        if ch == "\n":
            quote = None
            out.append(ch)
        elif quote:
            if ch == quote:
                quote = None
                out.append(ch)
            else:
                out.append(" ")
        else:
            if ch in ("'", '"'):
                quote = ch
            out.append(ch)
    return "".join(out)


class Source:
    """One program's code lines, split into divisions, with literal-blanked twins."""

    def __init__(self, path: Path):
        self.path = path
        self.lines: list[tuple[int, str]] = []  # (1-based line, Area A..B text), comments dropped
        for no, raw in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if len(raw) > 6 and raw[6] in "*/Dd":
                continue
            area = raw[7:72] if len(raw) > 7 else ""
            area = area.split("*>", 1)[0]
            self.lines.append((no, area.upper()))
        self.raw_text = "\n".join(a for _, a in self.lines)
        self.text = _blank_literals(self.raw_text)
        self._line_at = []
        for no, area in self.lines:
            self._line_at.extend([no] * (len(area) + 1))
        self.proc_start = self._procedure_start()

    def line_of(self, offset: int) -> int:
        return self._line_at[min(offset, len(self._line_at) - 1)] if self._line_at else 0

    def _procedure_start(self) -> Optional[int]:
        """Index into self.lines of the first line AFTER the PROCEDURE DIVISION header sentence."""
        for i, (_, area) in enumerate(self.lines):
            if re.search(r"\bPROCEDURE\s+DIVISION\b", _blank_literals(area)):
                j = i
                while j < len(self.lines) and not _SENTENCE_END.search(_blank_literals(self.lines[j][1])):
                    j += 1
                return j + 1
        return None

    def program_id(self) -> Optional[str]:
        m = re.search(r"\bPROGRAM-ID\.?\s+['\"]?([A-Z0-9@#$-]+)", self.raw_text)
        return m.group(1) if m else None


# ==============================================================================
# Units and reachability
# ==============================================================================
def _units(src: Source) -> list[dict[str, Any]]:
    """Paragraph/section headers in Area A of the PROCEDURE DIVISION, with bodies.

    An implicit unit holds any statements between the division header and the
    first named header (the program's unnamed first paragraph)."""
    if src.proc_start is None:
        return []
    units: list[dict[str, Any]] = [{"name": None, "kind": "implicit", "line": None, "body": []}]
    for no, area in src.lines[src.proc_start :]:
        lead = len(area) - len(area.lstrip(" "))
        m = _HEADER.match(area.strip()) if area.strip() and lead < 4 else None
        if m and m.group(1) not in _NOT_A_HEADER and not m.group(1).startswith("END-"):
            units.append({"name": m.group(1), "kind": "section" if m.group(2) else "paragraph", "line": no, "body": []})
            rest = area.strip()[m.end() :]
            if rest.strip():
                units[-1]["body"].append(rest)
        else:
            units[-1]["body"].append(area)
    if not "".join(units[0]["body"]).strip():
        units.pop(0)
    for u in units:
        u["text"] = _blank_literals("\n".join(u["body"]))
    return units


def _is_terminal(text: str) -> bool:
    """Does the unit's last sentence end in an unconditional transfer that never falls through?"""
    sentences = [s.strip() for s in _SENTENCE_END.split(text) if s.strip()]
    if not sentences:
        return False
    last = re.sub(r"\s+", " ", sentences[-1])
    if len(re.findall(r"\bIF\b", last)) != len(re.findall(r"\bEND-IF\b", last)):
        return False  # the transfer sits inside an unterminated IF: conditional
    if len(re.findall(r"\bEVALUATE\b", last)) != len(re.findall(r"\bEND-EVALUATE\b", last)):
        return False
    if last.endswith("END-EXEC"):
        start = [m.start() for m in re.finditer(r"\bEXEC\s", last)]
        return bool(start) and re.match(r"EXEC\s+CICS\s+(RETURN|XCTL|ABEND)\b", last[start[-1] :]) is not None
    return _TERMINAL_TAIL.search(last) is not None and " DEPENDING " not in last


def _tail_perform(text: str) -> Optional[tuple[str, Optional[str]]]:
    """(target, thru) when the unit's last sentence is exactly an unconditional out-of-line PERFORM."""
    sentences = [x.strip() for x in _SENTENCE_END.split(text) if x.strip()]
    if not sentences:
        return None
    last = re.sub(r"\s+", " ", sentences[-1])
    m = re.search(rf"\bPERFORM ({NAME})(?: (?:THRU|THROUGH) ({NAME}))?$", last)
    if not m or len(re.findall(r"\bIF\b", last)) != len(re.findall(r"\bEND-IF\b", last)):
        return None
    if len(re.findall(r"\bEVALUATE\b", last)) != len(re.findall(r"\bEND-EVALUATE\b", last)):
        return None
    return m.group(1), m.group(2)


def reachability(units: list[dict[str, Any]], cross_sections: bool = True) -> dict[str, str]:
    """Maps each reached unit name to the first reason it is reached.

    Contexts are (start, end) index ranges: the main flow is (entry, None) and
    falls through until a terminal statement; PERFORM P is (P, P), PERFORM S of a
    section is (S, last paragraph of S), PERFORM A THRU B is (A, B). A GO TO
    continues in the enclosing range when its target lies inside it."""
    index = {u["name"]: i for i, u in enumerate(units) if u["name"]}
    section_end: dict[int, int] = {}
    for i, u in enumerate(units):
        if u["kind"] == "section":
            j = i
            while j + 1 < len(units) and units[j + 1]["kind"] != "section":
                j += 1
            section_end[i] = j

    def span_end(i: int) -> int:
        return section_end.get(i, i)

    # A unit is terminal if its last sentence ends in GOBACK/STOP RUN/RETURN/...,
    # or in an unconditional PERFORM of a range that itself never returns (the
    # CBSA shape: `PERFORM GET-ME-OUT-OF-HERE.` where that section RETURNs).
    # Fixpoint, since "never returns" is defined through `terminal`.
    terminal = [_is_terminal(u["text"]) for u in units]
    tails = [_tail_perform(u["text"]) for u in units]
    changed = True
    while changed:
        changed = False
        for i, tail in enumerate(tails):
            if terminal[i] or not tail or tail[0] not in index:
                continue
            a = index[tail[0]]
            b = span_end(index[tail[1]]) if tail[1] in index else span_end(a)
            if any(terminal[k] for k in range(a, b + 1)):
                terminal[i] = changed = True

    reached: dict[int, str] = {}
    queue: list[tuple[int, Optional[int], str]] = [(0, None, "entry")]
    for i, u in enumerate(units):
        for m in _CICS_HANDLE.finditer(u["text"]):
            for tok in re.findall(rf"\(\s*({NAME})\s*\)", m.group(1)):
                if tok in index:
                    queue.append((index[tok], None, f"EXEC CICS HANDLE label in {u['name'] or '(procedure division)'}"))
    seen: set[tuple[int, Optional[int]]] = set()
    while queue:
        start, end, why = queue.pop(0)
        if (start, end) in seen:
            continue
        seen.add((start, end))
        k, reason = start, why
        while k < len(units):
            reached.setdefault(k, reason)
            u, here = units[k], units[k]["name"] or "(procedure division)"
            for m in _PERFORM.finditer(u["text"]):
                if m.group(1) in index:
                    a = index[m.group(1)]
                    b = span_end(index[m.group(2)]) if m.group(2) in index else span_end(a)
                    queue.append((a, b, f"PERFORM from {here}"))
            for m in _GOTO.finditer(u["text"]):
                for tok in m.group(1).split():
                    if tok not in index:
                        break
                    t = index[tok]
                    queue.append((t, end if end is not None and start <= t <= end else None, f"GO TO from {here}"))
            if (end is not None and k >= end) or terminal[k]:
                break
            # Verification aid: with cross_sections=False the main flow may not
            # fall off the end of one section into the next, which exposes units
            # whose liveness depends only on that.
            if not cross_sections and end is None and k + 1 < len(units) and units[k + 1]["kind"] == "section":
                break
            k, reason = k + 1, f"fall-through from {here}"
    return {units[i]["name"]: why for i, why in reached.items() if units[i]["name"]}


# ==============================================================================
# Copybooks (zapp.yaml libraries when the corpus declares them)
# ==============================================================================
def _zapp_locations(zapp: Path) -> dict[str, list[str]]:
    """library name -> local location globs, for the cobol property group(s). A
    deliberately small reader for the zapp.yaml shape (no YAML dependency)."""
    libs: dict[str, list[str]] = {}
    group_lang, lib_name, lib_type, in_locations = None, None, None, False
    for line in zapp.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if m := re.match(r"language:\s*(\S+)", s):
            group_lang, lib_name, in_locations = m.group(1), None, False
        elif m := re.match(r"-\s*name:\s*(\S+)", s):
            lib_name, lib_type, in_locations = m.group(1).upper(), None, False
        elif m := re.match(r"type:\s*(\S+)", s):
            lib_type = m.group(1)
        elif s.startswith("locations:"):
            in_locations = True
        elif in_locations and s.startswith("-") and group_lang == "cobol" and lib_type == "local" and lib_name:
            libs.setdefault(lib_name, []).append(s.lstrip("- ").strip("\"'"))
        elif s and not s.startswith("-"):
            in_locations = False
    return libs


def _nearest_zapp(program: Path, repo: Path) -> Optional[Path]:
    d = program.parent
    while True:
        if (d / "zapp.yaml").is_file():
            return d / "zapp.yaml"
        if d == repo or repo not in d.parents:
            return None
        d = d.parent


def _library_dirs(zapp: Path, library: str, repo: Path) -> list[Path]:
    out = []
    for loc in _zapp_locations(zapp).get(library, []):
        if loc.startswith("**/"):
            leaf = loc[3:]
            out += [p for p in zapp.parent.rglob(leaf) if p.is_dir()]
        elif (zapp.parent / loc).is_dir():
            out.append(zapp.parent / loc)
        else:  # a multi-root workspace folder, named relative to the workspace
            out += [p for p in repo.rglob(loc) if p.is_dir() and ".git" not in p.parts]
    return out


def resolve_copybook(name: str, library: Optional[str], program: Path, repo: Path, files: list[Path]) -> dict[str, Any]:
    for prefix, owner in _SYSTEM_COPY:
        if name.startswith(prefix):
            return {"resolves_to": None, "why": owner}
    cands = [p for p in files if p.stem.upper() == name and p.suffix.lower() in COPYBOOK_EXTS]
    zapp = _nearest_zapp(program, repo)
    if zapp is not None:
        dirs = _library_dirs(zapp, (library or "SYSLIB").upper(), repo)
        in_lib = [p for p in cands if any(p.parent == d for d in dirs)]
        if len(in_lib) == 1:
            lib = f"library {library}" if library else "syslib"
            return {
                "resolves_to": in_lib[0].relative_to(repo).as_posix(),
                "why": f"{zapp.relative_to(repo).as_posix()} {lib}",
            }
    if len(cands) == 1:
        return {"resolves_to": cands[0].relative_to(repo).as_posix(), "why": "only copybook with this name"}
    if not cands:
        bms = [p for p in files if p.stem.upper() == name and p.suffix.lower() == ".bms"]
        if bms:
            return {"resolves_to": None, "why": f"symbolic map generated from {bms[0].relative_to(repo).as_posix()}"}
        return {"resolves_to": None, "why": "not in the repository"}
    return {"resolves_to": None, "why": "AMBIGUOUS: " + ", ".join(p.relative_to(repo).as_posix() for p in cands)}


# ==============================================================================
# DATA DIVISION record layouts (#3246)
# ==============================================================================
def record_field_key(name: str) -> str:
    """The cross-parser comparison key for a field name: hyphens folded to
    underscores, upper-cased -- the form cobol_schema_forge emits as a column."""
    return name.replace("-", "_").upper()


def is_record_field(item: dict[str, Any]) -> bool:
    """A named, non-FILLER elementary item with a PIC -- what all three sides turn
    into a column. Group items, FILLER and 66/88 levels are not fields."""
    return (
        bool(item.get("pic")) and bool(item.get("name")) and item["name"] != "FILLER" and item["level"] not in (66, 88)
    )


def _data_items(src: Source) -> list[dict[str, Any]]:
    """The DATA DIVISION item tree of one program, this tool's own reading.

    One dict per data description entry in source order, with `parent` the
    ordinal of the enclosing group (None for an 01/77 root). Read from the
    literal-preserving raw text so a VALUE clause is intact; only entries between
    DATA DIVISION and PROCEDURE DIVISION are taken (a copybook has neither header
    and is read whole, but this runs on programs)."""
    text = src.raw_text
    dd = _DATA_DIVISION.search(text)
    start = dd.end() if dd else 0
    proc = _PROC_DIVISION.search(text, start)
    end = proc.start() if proc else len(text)
    sections = [(m.start(), m.group(1)) for m in _DD_SECTION.finditer(text)]
    fds = [(m.start(), m.group(1)) for m in _DD_FD.finditer(text)]

    def _context(off: int) -> tuple[Optional[str], Optional[str]]:
        section = next((name for pos, name in reversed(sections) if pos <= off), None)
        fd_name = None
        if section == "FILE":
            sec_off = next((pos for pos, name in reversed(sections) if pos <= off), -1)
            fd_name = next((name for pos, name in reversed(fds) if sec_off <= pos <= off), None)
        return section, fd_name

    entries = list(_DD_LEVEL.finditer(text))
    items: list[dict[str, Any]] = []
    stack: list[tuple[int, int]] = []
    last_item = None
    for pos, m in enumerate(entries):
        if m.start() < start or m.start() >= end:
            continue
        level = int(m.group(1))
        name = m.group(2).upper()
        stop = entries[pos + 1].start() if pos + 1 < len(entries) else len(text)
        window = text[m.end() : min(stop, m.end() + _DD_ENTRY_LIMIT)]
        ordinal = len(items)
        if level in (66, 88):
            parent = last_item
        else:
            while stack and stack[-1][0] >= level:
                stack.pop()
            parent = stack[-1][1] if stack else None
            stack.append((level, ordinal))
            last_item = ordinal
        pic_m = _DD_PIC.search(window)
        use_m = _DD_USAGE.search(window)
        occ_m = _DD_OCCURS.search(window)
        occ_min = int(occ_m.group(1)) if occ_m else None
        occ_max = int(occ_m.group(2)) if occ_m and occ_m.group(2) else occ_min
        dep_m = _DD_DEPENDING.search(window) if occ_m else None
        redef_m = _DD_REDEFINES.search(window)
        val_m = _DD_VALUE.search(window)
        value = None
        if val_m:
            value = (
                (val_m.group(1) if val_m.group(1) is not None else val_m.group(2))
                if (val_m.group(1) is not None or val_m.group(2) is not None)
                else val_m.group(3).rstrip(".")
            )
        section, fd_name = _context(m.start())
        items.append(
            {
                "ordinal": ordinal,
                "parent": parent,
                "level": level,
                "name": name,
                "section": section,
                "fd": fd_name,
                "pic": pic_m.group(1).rstrip(".") if pic_m else None,
                "usage": use_m.group(1).upper() if use_m else None,
                "occurs_min": occ_min,
                "occurs_max": occ_max,
                "occurs_depending_on": dep_m.group(1).upper() if dep_m else None,
                "redefines": redef_m.group(1).upper() if redef_m else None,
                "value": value,
                "line": src.line_of(m.start()),
            }
        )
    return items


# ==============================================================================
# Draft
# ==============================================================================
def _operand(src: Source, offset: int) -> tuple[str, str]:
    """The CALL/PROGRAM operand at `offset` in the raw text: (form, value)."""
    raw = src.raw_text[offset : offset + 80].lstrip()
    if raw[:1] in ("'", '"'):
        q = raw[0]
        return "literal", raw[1:].split(q, 1)[0].strip()
    m = re.match(rf"({NAME})", raw)
    return "identifier", m.group(1) if m else ""


def _value_of(src: Source, ident: str) -> Optional[str]:
    m = re.search(
        rf"\b(?:0[1-9]|[1-4][0-9]|77)\s+{re.escape(ident)}\s[^.]{{0,80}}?\bVALUE\s+(?:IS\s+)?['\"]([^'\"]*)['\"]",
        src.raw_text,
    )
    return m.group(1).strip() if m else None


def _common_prefix(a: str, b: str) -> list[str]:
    out = []
    for x, y in zip(a.split("/"), b.split("/")):
        if x != y:
            break
        out.append(x)
    return out


def draft_program(
    path: Path,
    repo: Path,
    files: list[Path],
    pid_to_path: dict[str, list[str]],
    tx_map: Optional[dict[str, set[str]]] = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    src = Source(path)
    units = _units(src)
    reached = reachability(units)
    named = [u for u in units if u["name"]]
    dead: dict[str, dict[str, Any]] = {}
    section = None
    for u in named:
        if u["kind"] == "section":
            section = u["name"]
        if u["name"] in reached:
            continue
        if u["kind"] == "section":
            reason = "section never PERFORMed, GO TO'd or named in an EXEC CICS HANDLE"
        elif section and section not in reached:
            reason = f"inside unreferenced section {section}"
        else:
            reason = "never PERFORMed or GO TO'd, and the unit before it never falls through"
        body = re.sub(r"\s+", " ", u["text"]).strip()
        # An `EXIT.`-only paragraph is dead but carries no logic: a tool that
        # counts it as removable bloat is right about reachability, not about size.
        dead[u["name"]] = {"reason": reason, "trivial": body in ("EXIT.", "EXIT")}

    copybooks = []
    for rx, via in ((_COPY, "COPY"), (_SQL_INCLUDE, "SQL INCLUDE")):
        for m in rx.finditer(src.text):
            name = m.group(1)
            library = m.group(2) if via == "COPY" else None
            entry = {"name": name, "via": via, "line": src.line_of(m.start(1)), "library": library}
            entry.update(resolve_copybook(name, library, path, repo, files))
            copybooks.append(entry)

    selects = {m.group(1): m.group(2) for m in _SELECT.finditer(src.text)}
    modes: dict[str, set[str]] = {k: set() for k in selects}
    for m in re.finditer(r"\bOPEN\s+", src.text):
        mode = None
        for tok in re.split(r"[\s,]+", src.text[m.end() : m.end() + 400]):
            tok = tok.rstrip(".")
            if tok in _OPEN_MODES:
                mode = tok
            elif tok in selects and mode:
                modes[tok].add(mode)
            else:
                break
    files_ = [
        {"internal": k, "assign": v, "dd": re.sub(r"^(?:UT|UR)-S-", "", v), "modes": sorted(modes[k])}
        for k, v in selects.items()
    ]

    calls = []
    for m in _CALL.finditer(src.text):
        form, value = _operand(src, m.end())
        if value:
            calls.append({"verb": "CALL", "form": form, "operand": value, "line": src.line_of(m.start())})
    for m in _CICS_PROGRAM.finditer(src.text):
        seg = src.text[m.end() : m.end() + 600]
        end = seg.find("END-EXEC")
        p = re.search(r"\bPROGRAM\s*\(\s*", seg[: end if end >= 0 else None])
        if p:
            form, value = _operand(src, m.end() + p.end())
            calls.append({"verb": m.group(1), "form": form, "operand": value, "line": src.line_of(m.start())})
    here = path.relative_to(repo).as_posix()
    for c in calls:
        target = c["operand"] if c["form"] == "literal" else _value_of(src, c["operand"])
        c["target"] = target
        cands = pid_to_path.get(target, []) if target else []
        # Several programs can share a PROGRAM-ID (copies per workspace root);
        # which one a CALL binds is a load-library question, so take the one
        # nearest the caller and say so.
        c["resolves_to"] = max(cands, key=lambda q: len(_common_prefix(q, here))) if cands else None
        if len(cands) > 1:
            c["note"] = "PROGRAM-ID shared by " + ", ".join(cands) + "; nearest taken"
        elif not cands and target and target.startswith("CEE"):
            c["note"] = "Language Environment callable service"

    entry = {
        "program_id": src.program_id(),
        "units": [{"name": u["name"], "kind": u["kind"], "line": u["line"]} for u in named],
        "dead": dead,
        "copybooks": copybooks,
        "files": files_,
        "calls": calls,
        "records": _data_items(src),  # #3246: DATA DIVISION item tree + FD layouts
        # #3247: the CICS transaction ids that entry-point into this program, from
        # the repo's CSD decks. Drafted; adjudicates a differential delta only once
        # a program is explicitly signed off with `transactions_validated` (the
        # records_validated precedent).
        "transactions": sorted(tx_map.get(src.program_id(), set())) if tx_map else [],
        "cics": bool(re.search(r"\bEXEC\s+CICS\b", src.text)),
        "sql": bool(re.search(r"\bEXEC\s+SQL\b", src.text)),
        "verification": {"status": "draft", "notes": []},
    }
    return entry, reached


def draft(repo: Path, corpus: str, url: str, ref: str) -> tuple[dict[str, Any], str]:
    files = [p for p in repo.rglob("*") if p.is_file() and ".git" not in p.parts]
    programs = sorted(p for p in files if p.suffix.lower() in PROGRAM_EXTS and Source(p).program_id())
    pid_to_path: dict[str, list[str]] = {}
    for p in programs:
        pid_to_path.setdefault(Source(p).program_id(), []).append(p.relative_to(repo).as_posix())
    tx_map = _key_transactions(repo)  # #3247: repo-wide CSD read, once
    key: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "corpus": corpus, "url": url, "ref": ref, "programs": {}}
    report = [f"# Draft reachability evidence: {corpus} @ {ref[:8]}", ""]
    for p in programs:
        rel = p.relative_to(repo).as_posix()
        entry, reached = draft_program(p, repo, files, pid_to_path, tx_map)
        key["programs"][rel] = entry
        report += [f"## {rel} ({entry['program_id']})", "", "| unit | line | reached by |", "|---|---|---|"]
        for u in entry["units"]:
            report.append(f"| {u['name']} | {u['line']} | {reached.get(u['name'], '**DEAD**')} |")
        report.append("")
    return key, "\n".join(report)


# ==============================================================================
# Score
# ==============================================================================
def _pr(truth: set, got: set) -> str:
    if not truth and not got:
        return "—"
    tp = len(truth & got)
    p = f"{tp}/{len(got)}" if got else "0/0"
    r = f"{tp}/{len(truth)}" if truth else "0/0"
    return f"P {p} · R {r}"


def old_paragraphs(path: Path, repo: Path) -> set[str]:
    """The forge (graveyard) view of a program's paragraph/section names, with
    copybooks inlined as the refractor does. Lives here, beside the other COBOL
    readers, so the harness and the scorer share one implementation without
    importing each other (#3211: refraction_differential is the harness on top)."""
    from gitgalaxy.tools.cobol_to_cobol.cobol_graveyard_finder import resolve_copybooks, unit_headers

    content = resolve_copybooks(path.read_text(encoding="utf-8", errors="ignore").upper(), path, repo)
    if "PROCEDURE DIVISION" not in content:
        return set()
    return set(unit_headers(content.split("PROCEDURE DIVISION", 1)[1]))


def old_copybooks(path: Path, repo: Path) -> tuple[set[str], dict[str, Path]]:
    """(named, resolved): the COPY names the forge sees and the member it resolves
    each to (searched under `repo`, as the refractor does)."""
    from gitgalaxy.tools.cobol_to_cobol.cobol_graveyard_finder import COPY_PATTERN, find_copybook

    named = {m.group(1).upper() for m in COPY_PATTERN.finditer(path.read_text(encoding="utf-8", errors="ignore"))}
    resolved = {n: hit for n in named if (hit := find_copybook(n, repo, path)) is not None}
    return named, resolved


# #3247: the answer key's OWN CICS transaction reader -- a third CSD parser,
# independent of the engine (core.mainframe_boundary) and the forge
# (cics_transaction_reader), so `transaction` can adjudicate a forge-vs-engine
# delta. The two operands the key keeps (PROGRAM/TRANSID) are always bare resource
# names, so unlike the other two readers this one needs no paren-balanced attribute
# scan -- a genuinely simpler, independent parse of the same decks.
_CSD_CMD = re.compile(r"^[ \t]*(?:DEFINE|DELETE|ALTER|ADD|REMOVE|LIST|UPGRADE|COPY)\b", re.I)
_CSD_HEAD = re.compile(r"^[ \t]*DEFINE[ \t]+([A-Z0-9]+)[ \t]*\([ \t]*([A-Z0-9@#$]+)[ \t]*\)", re.I)
_CSD_OPERAND = re.compile(r"\b(PROGRAM|TRANSID)[ \t]*\([ \t]*([A-Z0-9@#$]+)", re.I)
_CSD_DFHCSDUP = re.compile(r"\bPGM=DFHCSDUP\b", re.I)
_CSD_EXCLUDED = frozenset({"DB2TRAN", "DB2ENTRY", "DB2CONN"})


def _csd_pairs(text: str) -> list[tuple[str, str]]:
    """The (transid, program) pairs a CSD deck declares. A DEFINE record has no
    continuation character, so it runs to the next command / `*` comment / `//`
    line / blank line. Both record shapes yield the same edge:
    `DEFINE TRANSACTION(T) ... PROGRAM(P)` and the `DEFINE PROGRAM(P) ...
    TRANSID(T)` autoinstall pairing; `DEFINE DB2TRAN`'s TRANSID is excluded."""
    pairs: list[tuple[str, str]] = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        head = _CSD_HEAD.match(lines[i])
        if not (head and _CSD_CMD.match(lines[i])):
            i += 1
            continue
        record = [lines[i]]
        j = i + 1
        while j < len(lines):
            nxt = lines[j]
            stripped = nxt.strip()
            if not stripped or stripped.startswith("*") or nxt.lstrip().startswith("//") or _CSD_CMD.match(nxt):
                break
            record.append(nxt)
            j += 1
        resource, name = head.group(1).upper(), head.group(2).upper()
        if resource not in _CSD_EXCLUDED:
            operands = {m.group(1).upper(): m.group(2).upper() for m in _CSD_OPERAND.finditer("\n".join(record))}
            if resource == "TRANSACTION" and operands.get("PROGRAM"):
                pairs.append((name, operands["PROGRAM"]))
            elif resource == "PROGRAM" and operands.get("TRANSID"):
                pairs.append((operands["TRANSID"], name))
        i = j
    return pairs


def _key_transactions(repo: Path) -> dict[str, set[str]]:
    """program-id (upper) -> the entry transaction ids that route into it, read
    from every `.csd` deck and every DFHCSDUP-inline JCL job under `repo`."""
    by_program: dict[str, set[str]] = {}
    for path in repo.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        suffix = path.suffix.lower()
        if suffix == ".csd":
            text = path.read_text(encoding="utf-8", errors="ignore")
        elif suffix == ".jcl":
            text = path.read_text(encoding="utf-8", errors="ignore")
            if not _CSD_DFHCSDUP.search(text):
                continue
        else:
            continue
        for transid, program in _csd_pairs(text):
            by_program.setdefault(program, set()).add(transid)
    return by_program


def score(repo: Path, key: dict[str, Any], db: Optional[Path]) -> tuple[dict[str, Any], str]:
    from gitgalaxy.tools.cobol_to_cobol.cics_transaction_reader import extract_transactions
    from gitgalaxy.tools.cobol_to_cobol.cobol_dag_architect import extract_lineage
    from gitgalaxy.tools.cobol_to_cobol.cobol_graveyard_finder import x_ray_dead_code
    from gitgalaxy.tools.cobol_to_cobol.cobol_jcl_forge import analyze_cobol_intent
    from gitgalaxy.tools.cobol_to_cobol.cobol_schema_forge import forge_schemas

    ir = None
    engine_tx: dict[str, set[str]] = {}
    if db is not None:
        from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir

        ir = load_galaxy_ir(db)
        for t in ir.transaction_map("cobol"):  # #3247: engine entry transactions per program
            if t["program"]:
                engine_tx.setdefault(t["program"].upper(), set()).add(t["transid"].upper())
    forge_tx = extract_transactions(repo)  # #3247: forge/independent CSD read, once

    fields = [
        "program_id",
        "units",
        "dead",
        "dead (non-trivial)",
        "copybook paths",
        "DD names",
        "inputs",
        "outputs",
        "dynamic CALLs",
        # #3200: every call target the program names, literal or resolved
        # through a working-storage VALUE. The forge has no equivalent -- its
        # lineage tool only records non-literal `CALL` operands, and never sees
        # `EXEC CICS LINK`/`XCTL` at all -- so this row measures the engine
        # against the key with no forge column.
        "call targets",
        # #3246: DATA DIVISION record fields. All three sides read a program's own
        # DATA DIVISION into columns; the forge's cobol_schema_forge is the flat
        # reader, the engine carries the full tree (record_data), and the key is
        # this tool's own independent reading.
        "record fields",
        # #3247: CICS entry transactions (which transaction id routes into this
        # program). Truth is the key's own CSD read, forge is cics_transaction_reader,
        # engine is transaction_map from the DB.
        "entry transactions",
        "cics/sql",
    ]
    agg: dict[str, dict[str, list[set]]] = {f: {"truth": [], "forge": [], "engine": []} for f in fields}

    def add(field: str, prog: str, truth, forge, engine):
        agg[field]["truth"].append({(prog, x) for x in truth})
        agg[field]["forge"].append({(prog, x) for x in forge} if forge is not None else None)
        agg[field]["engine"].append({(prog, x) for x in engine} if engine is not None else None)

    unverified = []
    for rel, k in key["programs"].items():
        if k["verification"]["status"] != "validated":
            unverified.append(rel)
        path = repo / rel
        intent = analyze_cobol_intent(path)
        gy = x_ray_dead_code(path, copybook_root=repo) or {}
        lin = extract_lineage(path, dead_paras=set(gy.get("dead_paras", set()))) or {}
        ef = ir.files.get(rel) if ir else None

        add("program_id", rel, {k["program_id"]}, {intent["program_id"]}, set(ef.program_ids[:1]) if ef else None)
        add(
            "units",
            rel,
            {u["name"] for u in k["units"]},
            old_paragraphs(path, repo),
            {u.name.upper() for u in ef.units} if ef else None,
        )
        forge_dead = set(gy.get("dead_paras", set()))
        engine_dead = {u.name.upper() for u in ef.units if u.usage_status == 1} if ef else None
        add("dead", rel, set(k["dead"]), forge_dead, engine_dead)
        # Only real logic: a tool is not credited, or blamed, for EXIT.-only paragraphs.
        trivial = {n for n, v in k["dead"].items() if v["trivial"]}
        add(
            "dead (non-trivial)",
            rel,
            set(k["dead"]) - trivial,
            forge_dead - trivial,
            engine_dead - trivial if engine_dead is not None else None,
        )
        truth_cp = {c["resolves_to"] for c in k["copybooks"] if c["resolves_to"]}
        _, forge_resolved = old_copybooks(path, repo)
        forge_cp = {hit.relative_to(repo).as_posix() for hit in forge_resolved.values()}
        add("copybook paths", rel, truth_cp, forge_cp, set(ef.copy_deps) if ef else None)
        dd_modes = {f["dd"]: set(f["modes"]) for f in k["files"]}
        # #3201: the engine's own SELECT/ASSIGN + OPEN-mode extraction
        # (dataset_data, the COBOL half -- a JCL DD binding is not a program's
        # file). Before #3201 every one of these was `None` -> "not carried".
        engine_files = [d for d in ef.datasets if not d.is_binding] if ef else None
        engine_modes = {d.dd_name: set(d.modes) for d in engine_files} if engine_files is not None else None
        add(
            "DD names",
            rel,
            set(dd_modes),
            {f["dd_name"] for f in intent["files_requested"]},
            set(engine_modes) if engine_modes is not None else None,
        )
        add(
            "inputs",
            rel,
            {d for d, m in dd_modes.items() if m & {"INPUT", "I-O", "EXTEND"}},
            set(lin.get("inputs", set())),
            (
                {d for d, m in engine_modes.items() if m & {"INPUT", "I-O", "EXTEND"}}
                if engine_modes is not None
                else None
            ),
        )
        add(
            "outputs",
            rel,
            {d for d, m in dd_modes.items() if m & {"OUTPUT", "I-O", "EXTEND"}},
            set(lin.get("outputs", set())),
            (
                {d for d, m in engine_modes.items() if m & {"OUTPUT", "I-O", "EXTEND"}}
                if engine_modes is not None
                else None
            ),
        )
        add(
            "dynamic CALLs",
            rel,
            {c["operand"] for c in k["calls"] if c["verb"] == "CALL" and c["form"] == "identifier"},
            set(lin.get("unresolved_calls", [])),
            (
                {c.operand for c in ef.calls if c.verb == "CALL" and c.form == "identifier" and c.operand}
                if ef
                else None
            ),
        )
        add(
            "call targets",
            rel,
            {c["target"] for c in k["calls"] if c["target"]},
            None,
            ({c.target for c in ef.calls if c.target} if ef else None),
        )
        forge_schema = forge_schemas(path)
        forge_records = {record_field_key(n) for n in forge_schema["json"]["properties"]} if forge_schema else set()
        add(
            "record fields",
            rel,
            {record_field_key(r["name"]) for r in k.get("records", []) if is_record_field(r)},
            forge_records,
            (
                {
                    record_field_key(it.name)
                    for it in ef.data_items
                    if it.pic and it.name != "FILLER" and it.level not in (66, 88)
                }
                if ef
                else None
            ),
        )
        pid = (k["program_id"] or "").upper()
        add(
            "entry transactions",
            rel,
            set(k.get("transactions", [])),
            forge_tx.get(pid, set()),
            engine_tx.get(pid, set()) if ir else None,
        )
        add(
            "cics/sql",
            rel,
            {x for x, on in (("cics", k["cics"]), ("sql", k["sql"])) if on},
            {x for x, on in (("cics", intent["is_cics"]), ("sql", intent["is_db2"])) if on},
            None,
        )

    result: dict[str, Any] = {
        "corpus": key["corpus"],
        "ref": key["ref"],
        "unverified_programs": unverified,
        "fields": {},
    }
    md = [f"## {key['corpus']} @ {key['ref'][:8]}", ""]
    if unverified:
        md += [
            f"> **{len(unverified)} of {len(key['programs'])} programs are still `draft`** -- these scores are not evidence yet.",
            "",
        ]
    md += ["| field | forge | engine DB |", "|---|---|---|"]
    for f in fields:
        t = set().union(*agg[f]["truth"]) if agg[f]["truth"] else set()
        cols = []
        for side in ("forge", "engine"):
            vals = agg[f][side]
            if not vals or any(v is None for v in vals):
                cols.append("n/a (not carried)" if side == "engine" else "n/a")
                result["fields"].setdefault(f, {})[side] = None
            else:
                got = set().union(*vals)
                cols.append(_pr(t, got))
                result["fields"].setdefault(f, {})[side] = {"tp": len(t & got), "got": len(got), "truth": len(t)}
        md.append(f"| {f} | {cols[0]} | {cols[1]} |")
    md.append("")
    md.append("P = correct / reported, R = correct / true. Sets are (program, value) pairs.")
    return result, "\n".join(md) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draft")
    d.add_argument("repo", type=Path)
    d.add_argument("--corpus", required=True)
    d.add_argument("--url", required=True)
    d.add_argument("--ref", required=True)
    d.add_argument("--out", type=Path, required=True)
    d.add_argument("--report", type=Path)
    s = sub.add_parser("score")
    s.add_argument("repo", type=Path)
    s.add_argument("--key", type=Path, required=True)
    s.add_argument("--db", type=Path)
    s.add_argument("--md", type=Path)
    s.add_argument("--json", type=Path)
    args = ap.parse_args()

    repo = args.repo.resolve()
    if args.cmd == "draft":
        key, report = draft(repo, args.corpus, args.url, args.ref)
        args.out.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        if args.report:
            args.report.write_text(report + "\n", encoding="utf-8")
        print(f"drafted {len(key['programs'])} programs -> {args.out}")
        return 0

    key = json.loads(args.key.read_text(encoding="utf-8"))
    result, md = score(repo, key, args.db)
    if args.md:
        args.md.write_text(md, encoding="utf-8")
    if args.json:
        args.json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
