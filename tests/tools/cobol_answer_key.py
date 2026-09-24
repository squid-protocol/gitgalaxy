"""
#3210: the COBOL modernization answer key -- hand-verified, per-program truth for
real mainframe corpora -- and the scorer that measures the refraction ("forge")
tools and the engine's master DB against it.

    python tests/tools/cobol_answer_key.py draft <repo> --corpus NAME --url URL --ref SHA \
        --out key.json [--report why.md]
    python tests/tools/cobol_answer_key.py score <repo> --key key.json [--db master.db] [--md out.md]
    python tests/tools/cobol_answer_key.py add-pli <repo> --key key.json
    python tests/tools/cobol_answer_key.py add-sql-tables <repo> --key key.json
    python tests/tools/cobol_answer_key.py add-bms <repo> --key key.json
    python tests/tools/cobol_answer_key.py add-jcl <repo> --key key.json
    python tests/tools/cobol_answer_key.py add-csd <repo> --key key.json
    python tests/tools/cobol_answer_key.py add-commarea <repo> --key key.json
    python tests/tools/cobol_answer_key.py add-cics <repo> --key key.json
    python tests/tools/cobol_answer_key.py sample --key key.json [--n 25] [--seed S] [--out checklist.md]

`add-pli` (#3250) drafts the PL/I DECLARE record layouts of every PL/I source in
<repo> into the key's `pli_programs`, leaving every COBOL program (and its
`validated` status) untouched -- a full `draft` would wipe them.
`add-sql-tables` (#3344) does the same for DB2 `EXEC SQL DECLARE ... TABLE`
columns (inline or DCLGEN members) into the key's `sql_tables`. `add-bms` (#3347)
does the same for every BMS map source's screen fields, into `bms_maps`.
`add-jcl` (#3345) does the same for every JCL member's DD bindings and
symbol-resolved DSNs, into `jcl_jobs`. `add-csd` (#3356) does the same for every
CSD deck's resource definitions (FILE, TDQUEUE, DB2TRAN, ...), into `csd_decks`.
`add-commarea` (#3355) drafts each keyed COBOL program's CICS LINK/XCTL/RETURN
TRANSID COMMAREA operands (with LENGTH/DATALENGTH) into its `commareas`, leaving
every other field -- and a program already `commareas_validated` -- untouched.

`add-cics` (#3351-#3354) drafts every COBOL source's EXEC CICS
FILE/MAP/QUEUE/CONTAINER/CHANNEL operations into `cics_resources`, the add-pli way.

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

# How strongly a `validated` program's truth is backed, weakest first. Every
# validated program names one in `verification.tier`:
#   llm_verified    one model checked the draft against the source (every dead
#                   verdict and every draft/forge/engine disagreement)
#   cross_verified  a second reviewer model, with a fresh context, answered the
#                   same questions BLIND (dead units mixed with live controls,
#                   without the key's answers), and every disagreement was
#                   settled against the source (tests/tools/cross_verify.py);
#                   `verification.cross_by` names it
#   human_signed    a person spot-checked a sample (`sample` subcommand) and
#                   signed; `verification.signed_by` names them
# The ledger labels each field with the weakest tier behind it, so a score is
# never quoted as stronger evidence than it is.
TIERS = ("llm_verified", "cross_verified", "human_signed")
PROGRAM_EXTS = (".cbl", ".cob", ".cobol", ".ccp")
# `.dcl`: a DCLGEN member, which `EXEC SQL INCLUDE` pulls in like a copybook
# (CardDemo COPAUS2C `INCLUDE AUTHFRDS` -> app/.../dcl/AUTHFRDS.dcl).
COPYBOOK_EXTS = (".cpy", ".copy", ".dcl")

NAME = r"[A-Z0-9][A-Z0-9-]*"
_HEADER = re.compile(rf"^({NAME})(?:\s+(SECTION)(?:\s+[0-9]{{1,2}})?)?\s*\.(?:\s|$)")
_HEADER_NO_PERIOD = re.compile(rf"^({NAME})(?:\s+SECTION(?:\s+[0-9]{{1,2}})?)?$")
# Words that can sit in Area A followed by a period without being a unit header.
_NOT_A_HEADER = {"DECLARATIVES", "END", "EXIT", "GOBACK", "CONTINUE", "STOP", "ELSE"}
# `(?<![\w-])` for the same reason as _CALL below: `END-PERFORM` followed by a
# real `PERFORM X` read as a PERFORM of the word `PERFORM`, swallowing X
# (CardDemo COTRTLIC 9450-CLOSE-FORWARD-CURSOR read as dead).
_PERFORM = re.compile(rf"(?<![\w-])PERFORM\s+({NAME})(?:\s+(?:THRU|THROUGH)\s+({NAME}))?")
_ALTER = re.compile(rf"(?<![\w-])ALTER\s+({NAME})\s+TO\s+(?:PROCEED\s+TO\s+)?({NAME})")
_GOTO = re.compile(rf"(?<![\w-])GO\s+(?:TO\s+)?((?:{NAME}\s*)+)")
_SENTENCE_END = re.compile(r"\.(?=\s|$)")
_TERMINAL_TAIL = re.compile(rf"(?:\bGOBACK|\bSTOP\s+RUN|\bEXIT\s+PROGRAM|\bGO\s+(?:TO\s+)?{NAME})\s*$")
_SELECT = re.compile(rf"\bSELECT\s+(?:OPTIONAL\s+)?({NAME})\s+ASSIGN\s+(?:TO\s+)?([A-Z0-9@#$-]+)")
_OPEN_MODES = {"INPUT", "OUTPUT", "I-O", "EXTEND"}
# `(?<![\w-])`, not `\b`: `\b` matches after a hyphen, so `END-CALL` and a
# paragraph named `3200-INSERT-IMS-CALL` read as the CALL verb (found drafting
# CardDemo; pinned by test_end_call_and_hyphenated_names_are_not_calls).
_CALL = re.compile(r"(?<![\w-])CALL\s+")
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
    ("CMQ", "IBM MQ-supplied"),  # CMQV, CMQODV, CMQMDV, ... (CardDemo's MQ programs)
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
    lines = src.lines[src.proc_start :]
    for i, (no, area) in enumerate(lines):
        lead = len(area) - len(area.lstrip(" "))
        head = area.strip()
        if head and lead < 4 and _HEADER_NO_PERIOD.match(head):
            # A header's separator period may sit on the next code line
            # (CardDemo COTRTLIC `2000-SEND-MAP` / `     .`).
            nxt = next((a.strip() for _, a in lines[i + 1 :] if a.strip()), "")
            if nxt.startswith("."):
                head += " ."
        m = _HEADER.match(head) if head and lead < 4 else None
        if m and m.group(1) not in _NOT_A_HEADER and not m.group(1).startswith("END-"):
            units.append({"name": m.group(1), "kind": "section" if m.group(2) else "paragraph", "line": no, "body": []})
            rest = head[m.end() :] if head == area.strip() else ""
            if rest.strip():
                units[-1]["body"].append(rest)
        else:
            units[-1]["body"].append(area)
    if not "".join(units[0]["body"]).strip():
        units.pop(0)
    for u in units:
        u["text"] = _blank_literals("\n".join(u["body"]))
    return units


_TRAILING_COPY = re.compile(
    r"\bCOPY\s+(?:'[^']*'|\"[^\"]*\"|[A-Z0-9@#$-]+)(?:\s+(?:IN|OF)\s+[A-Z0-9@#$-]+)?(?:\s+REPLACING\b.*?)?\s*\."
)


def _is_exit_only(body: str) -> bool:
    """`EXIT.` alone, however spaced (`EXIT .`, CardDemo's style), and ignoring a COPY
    after it -- a procedure copybook brings its own paragraph header, so its code is
    not in this unit."""
    t = re.sub(r"\s+\.", ".", _TRAILING_COPY.sub("", body)).strip()
    return t in ("EXIT.", "EXIT")


def _sentences(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", x.strip()) for x in _SENTENCE_END.split(text) if x.strip()]


def _unconditional(sentence: str) -> bool:
    r"""Is the sentence outside any IF / EVALUATE (so what it ends in always runs)?

    `(?<![\w-])`: `\bIF\b` also matches inside `END-IF`, so any sentence with a
    closed IF read as unterminated and a paragraph ending `... END-IF ... GOBACK.`
    as falling through (CardDemo CBPAUP0C MAIN-PARA)."""
    if len(re.findall(r"(?<![\w-])IF\b", sentence)) != len(re.findall(r"\bEND-IF\b", sentence)):
        return False
    return len(re.findall(r"(?<![\w-])EVALUATE\b", sentence)) == len(re.findall(r"\bEND-EVALUATE\b", sentence))


def _sentence_is_terminal(sentence: str) -> bool:
    if not _unconditional(sentence):
        return False  # the transfer sits inside an unterminated IF: conditional
    if sentence.endswith("END-EXEC"):
        start = [m.start() for m in re.finditer(r"\bEXEC\s", sentence)]
        return bool(start) and re.match(r"EXEC\s+CICS\s+(RETURN|XCTL|ABEND)\b", sentence[start[-1] :]) is not None
    return _TERMINAL_TAIL.search(sentence) is not None and " DEPENDING " not in sentence


def _is_terminal(text: str) -> bool:
    """Does ANY sentence of the unit end in an unconditional transfer that never
    falls through? Not only the last: CBSA BNK1CCS A010 ends
    `EXEC CICS RETURN TRANSID(...) RESP(...) END-EXEC.` then an
    `IF <resp not normal> ... PERFORM ABEND-THIS-TASK END-IF.` recovery sentence,
    and the RETURN alone already ends the unit (found by the blind cross-check)."""
    return any(_sentence_is_terminal(s) for s in _sentences(text))


def _tail_perform(text: str) -> list[tuple[str, Optional[str]]]:
    """(target, thru) for every sentence of the unit that is exactly an
    unconditional out-of-line PERFORM -- any one of a range that never returns
    makes the unit terminal, wherever it sits in the unit."""
    out = []
    for s in _sentences(text):
        m = re.search(rf"(?<![\w-])PERFORM ({NAME})(?: (?:THRU|THROUGH) ({NAME}))?$", s)
        if m and _unconditional(s):
            out.append((m.group(1), m.group(2)))
    return out


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

    # A unit is terminal if any unconditional sentence ends in GOBACK/STOP RUN/RETURN/...,
    # or is an unconditional PERFORM of a range that itself never returns (the
    # CBSA shape: `PERFORM GET-ME-OUT-OF-HERE.` where that section RETURNs).
    # Fixpoint, since "never returns" is defined through `terminal`.
    terminal = [_is_terminal(u["text"]) for u in units]
    tails = [_tail_perform(u["text"]) for u in units]
    changed = True
    while changed:
        changed = False
        for i, unit_tails in enumerate(tails):
            for tail in unit_tails:
                if terminal[i] or tail[0] not in index:
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
            # `ALTER P TO PROCEED TO Q` rewires P's GO TO to jump to Q: Q is
            # reached through P, as a GO TO target (CardDemo CBSTM03A's
            # 8200/8300/8400-*-OPEN are reached only this way).
            for m in _ALTER.finditer(u["text"]):
                if m.group(2) in index:
                    queue.append((index[m.group(2)], None, f"ALTER (GO TO via {m.group(1)}) from {here}"))
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
# PL/I DECLARE structures (#3250)
# ==============================================================================
# This tool's own reading of a PL/I file's declarations: a token stream over the
# RAW file (it strips its own comments and sequence columns -- it never sees the
# engine's PRISM code stream) and a recursive-descent walk of each DECLARE list.
# It shares the engine's CONTRACT (which declarations are data, how levels nest),
# not its code, so an agreement is evidence and a disagreement is a finding.
PLI_EXTS = (".pli", ".pl1", ".plinc")
_PLI_TOKEN = re.compile(
    r"(?P<comment>/\*.*?(?:\*/|\Z)|//[^\n]*)"
    r"|(?P<string>'(?:[^']|'')*'[A-Z0-9]*|\"(?:[^\"]|\"\")*\"[A-Z0-9]*)"
    r"|(?P<word>[\w@#$]+)"
    r"|(?P<punct>\S)",
    re.S | re.I,
)
# Declarations that declare no storage (the contract the engine states too).
_PLI_NON_DATA = {"FILE", "BUILTIN", "CONDITION", "COND", "GENERIC", "ENTRY", "RETURNS", "FORMAT"}


def _pli_source_lines(text: str) -> str:
    """The raw file with columns 73-80 dropped wherever a fixed-format line numbers them."""
    out = []
    for line in text.split("\n"):
        tail = line[72:].strip()
        if len(line.rstrip()) <= 80 and tail and re.fullmatch(r"[A-Z]{0,4}[0-9]{2,8}", tail, re.I):
            line = line[:72]
        out.append(line)
    return "\n".join(out)


def _pli_token_stream(text: str) -> list[tuple[str, str, int]]:
    """(kind, TEXT, line) tokens, comments dropped; words upper-cased."""
    tokens = []
    line = 1
    pos = 0
    for m in _PLI_TOKEN.finditer(text):
        line += text.count("\n", pos, m.start())
        pos = m.start()
        kind = m.lastgroup or "punct"
        if kind != "comment":
            tokens.append((kind, m.group(0) if kind == "string" else m.group(0).upper(), line))
    return tokens


def _pli_group(tokens: list, i: int) -> int:
    """Index just past the `)` matching the `(` at tokens[i]."""
    depth = 0
    while i < len(tokens):
        t = tokens[i][1]
        if t == "(":
            depth += 1
        elif t == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return i


def _pli_top_words(tokens: list) -> set[str]:
    """The attribute keywords of an item: words outside any parentheses."""
    words, depth = set(), 0
    for kind, text, _ in tokens:
        depth += {"(": 1, ")": -1}.get(text, 0)
        if kind == "word" and depth == 0:
            words.add(text)
    return words


def _pli_text(tokens: list) -> str:
    """Tokens joined as written: no space before `(`, `)` or `,`, none after `(`."""
    out = ""
    for _, text, _ in tokens:
        if out and text not in ("(", ")", ",") and not out.endswith("("):
            out += " "
        out += text
    return out


def _pli_declaration(tokens: list) -> list[dict[str, Any]]:
    """The items of one DECLARE list (tokens between DCL and `;`)."""
    items = []
    i = 0
    while i < len(tokens):
        # One item runs to the next comma at depth 0.
        j, depth = i, 0
        while j < len(tokens) and not (tokens[j][1] == "," and depth == 0):
            depth += {"(": 1, ")": -1}.get(tokens[j][1], 0)
            j += 1
        item, i = tokens[i:j], j + 1
        if not item or item[0][1] == "%":
            continue
        k = 0
        level = 1
        if item[0][1].isdigit():
            level, k = int(item[0][1]), 1
        names: list[tuple[str, int, list]] = []
        if k < len(item) and item[k][1] == "(":
            end = _pli_group(item, k)
            inner = item[k + 1 : end - 1]
            part: list = []
            for t in inner + [("punct", ",", 0)]:
                if t[1] == "," and part:
                    names.append((part[0][1], part[0][2], part[1:]))
                    part = []
                elif t[1] != ",":
                    part.append(t)
            k = end
        elif k < len(item) and (item[k][0] == "word" or item[k][1] == "*"):
            if k + 1 < len(item) and item[k + 1][1] == "%":
                continue  # a macro-built name (`DCL FIELD%;J ...`)
            names.append((item[k][1], item[k][2], []))
            k += 1
        else:
            continue
        dims = None
        if k < len(item) and item[k][1] == "(":
            end = _pli_group(item, k)
            dims = item[k + 1 : end - 1]
            k = end
        attrs = item[k:]
        for name, line, inner_attrs in names:
            words = _pli_top_words(inner_attrs) | _pli_top_words(attrs)
            if words & _PLI_NON_DATA and "VARIABLE" not in words:
                continue
            items.append(
                {
                    "level": level,
                    "name": name,
                    "dims": _pli_text(dims) if dims is not None else None,
                    "attributes": _pli_text(inner_attrs + attrs),
                    "line": line,
                }
            )
    return items


def pli_data_items(text: str) -> list[dict[str, Any]]:
    """Every DECLAREd data item of one PL/I source, in source order, with `parent`
    the ordinal of its enclosing structure member (None for a level-1 root)."""
    tokens = _pli_token_stream(_pli_source_lines(text))
    statements: list[list] = [[]]
    for t in tokens:
        if t[1] == ";" and t[0] == "punct":
            statements.append([])
        else:
            statements[-1].append(t)
    items: list[dict[str, Any]] = []
    macro = False
    for st in statements:
        # A trailing sequence number orphaned by a stripped comment is a bare number.
        while st and st[0][0] == "word" and st[0][1].isdigit() and len(st) > 1 and st[1][2] > st[0][2]:
            st = st[1:]
        if not st:
            continue
        if st[0][1] == "%":
            if macro:
                macro = not (len(st) > 1 and st[1][1] == "END")
            elif len(st) > 3 and st[2][1] == ":" and st[3][1] in ("PROC", "PROCEDURE"):
                macro = True
            continue
        if macro or st[0][1] not in ("DCL", "DECLARE") or st[0][0] != "word":
            continue
        stack: list[tuple[int, int]] = []
        for it in _pli_declaration(st[1:]):
            while stack and stack[-1][0] >= it["level"]:
                stack.pop()
            it = {"ordinal": len(items), "parent": stack[-1][1] if stack else None, **it}
            stack.append((it["level"], it["ordinal"]))
            items.append(it)
    return items


def pli_record_fields(items: list[dict[str, Any]], parent_key: str = "parent") -> set[str]:
    """The dotted paths (`ROOT.GROUP.FIELD`) of every named leaf item -- the PL/I
    comparison unit. A leaf is an item nothing nests under; `*` is unnamed filler.
    Works on this reader's items and on the engine's (`parent_key="parent_ordinal"`)."""
    by_ordinal = {it["ordinal"]: it for it in items}
    has_child = {it[parent_key] for it in items if it[parent_key] is not None}
    out: set[str] = set()
    for it in items:
        if it["ordinal"] in has_child or it["name"] == "*":
            continue
        path = [it["name"]]
        parent = it[parent_key]
        while parent is not None and parent in by_ordinal:
            path.append(by_ordinal[parent]["name"])
            parent = by_ordinal[parent][parent_key]
        out.add(".".join(reversed(path)))
    return out


def draft_pli(repo: Path) -> dict[str, dict[str, Any]]:
    """Drafted PL/I record layouts for every PL/I source in `repo` (#3250). Records
    adjudicate a differential delta only once a file is signed off with
    `records_validated` -- the COBOL records precedent (#3246)."""
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(repo.rglob("*")):
        if p.is_file() and p.suffix.lower() in PLI_EXTS and ".git" not in p.parts:
            items = pli_data_items(p.read_text(encoding="utf-8", errors="ignore"))
            out[p.relative_to(repo).as_posix()] = {
                "records": items,
                "records_validated": False,
                "verification": {"status": "draft", "notes": []},
            }
    return out


# ==============================================================================
# DB2 DECLARE TABLE / DCLGEN schemas (#3344)
# ==============================================================================
# This tool's own reading of `EXEC SQL DECLARE <table> TABLE (...)`. It works on
# the RAW file with its own comment/sequence handling (COBOL: cols 8-72 of every
# non-comment line; PL/I: `/* */` blanked, cols 73-80 dropped) and cuts each
# statement at its TERMINATOR -- `END-EXEC` in COBOL, `;` in PL/I -- then takes
# the list up to the last `)`. The engine instead walks the PRISM code stream to
# the balancing parenthesis, so the two share the CONTRACT (per column: name,
# type, length/precision, scale, NOT NULL) and not the code: an agreement is
# evidence, a disagreement a finding.
# `.dcl`: COBOL DCLGEN members, e.g. carddemo dcl/DCLTRTYP.dcl (#3365).
SQL_TABLE_EXTS = PROGRAM_EXTS + COPYBOOK_EXTS + (".pco", ".cut", ".dcl") + PLI_EXTS
_SQL_NAME = r'(?:"[^"\n]+"|[A-Z@#$][A-Z0-9_@#$]*)'
_SQL_DECLARE = re.compile(rf"\bEXEC\s+SQL\s+DECLARE\s+({_SQL_NAME}(?:\s*\.\s*{_SQL_NAME}){{0,2}})\s+TABLE\s*\(", re.I)
_SQL_TOKEN = re.compile(r'"[^"]*"|[()]|[^\s()]+')
_SQL_OPTION_WORDS = {
    "NOT",
    "NULL",
    "WITH",
    "FOR",
    "DEFAULT",
    "CCSID",
    "GENERATED",
    "IMPLICITLY",
    "INLINE",
    "CONSTRAINT",
    "PRIMARY",
    "UNIQUE",
    "REFERENCES",
    "CHECK",
    "AS",
    "FIELDPROC",
}
_SQL_UNIT = {"K": 1024, "M": 1024**2, "G": 1024**3}


def _sql_prepared(text: str, pli: bool) -> str:
    """The raw file reduced to code, one output line per source line."""
    if pli:
        text = _pli_source_lines(text)
        return re.sub(r"/\*.*?(?:\*/|\Z)", lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.S)
    out = []
    for raw in text.split("\n"):
        raw = raw.rstrip("\r")
        if len(raw) > 6 and raw[6] in "*/":
            out.append("")
        else:
            out.append((raw[7:72] if len(raw) > 7 else "").split("*>", 1)[0])
    return "\n".join(out)


def _sql_unquote(name: str) -> str:
    return name[1:-1] if name.startswith('"') and name.endswith('"') else name.upper()


def sql_table_columns(text: str, pli: bool = False) -> list[dict[str, Any]]:
    """Every DECLARE TABLE column in one source file, this tool's own reading."""
    code = _sql_prepared(text, pli)
    terminator = re.compile(r";" if pli else r"\bEND-EXEC\b", re.I)
    out: list[dict[str, Any]] = []
    for m in _SQL_DECLARE.finditer(code):
        term = terminator.search(code, m.end())
        region = code[m.end() : term.start() if term else len(code)]
        body = re.sub(r"--[^\n]*", "", region[: region.rfind(")")])
        table = ".".join(_sql_unquote(p.strip()) for p in re.findall(_SQL_NAME, m.group(1), re.I))
        # Top-level commas only: `DECIMAL(10, 2)` is one column.
        pieces, depth, start = [], 0, 0
        for i, ch in enumerate(body):
            depth += ch == "("
            depth -= ch == ")"
            if ch == "," and depth == 0:
                pieces.append((start, body[start:i]))
                start = i + 1
        pieces.append((start, body[start:]))
        colno = 0
        for off, piece in pieces:
            toks = _SQL_TOKEN.findall(piece)
            if len(toks) < 2 or toks[0].upper() in ("PRIMARY", "FOREIGN", "CONSTRAINT", "UNIQUE", "CHECK"):
                continue
            i, words = 1, []
            while i < len(toks) and toks[i] != "(" and toks[i].upper() not in _SQL_OPTION_WORDS and len(words) < 4:
                words.append(toks[i].upper())
                i += 1
            if not words:
                continue
            length = scale = None
            if i < len(toks) and toks[i] == "(":
                j = toks.index(")", i) if ")" in toks[i:] else len(toks)
                args = " ".join(toks[i + 1 : j])
                lm = re.match(r"(\d+)\s*([KMG])?\b", args, re.I)
                if lm:
                    length = int(lm.group(1)) * _SQL_UNIT.get((lm.group(2) or "").upper(), 1)
                sm = re.search(r",\s*(\d+)", args.replace(" ,", ","))
                scale = int(sm.group(1)) if sm else None
                i = j + 1
            rest = " ".join(toks[i:]).upper()
            tz = re.match(r"(WITH(?:OUT)?) TIME ZONE\b", rest)
            if tz:
                words += [tz.group(1), "TIME", "ZONE"]
                rest = rest[tz.end() :]
            colno += 1
            lead = len(piece) - len(piece.lstrip())
            out.append(
                {
                    "table": table,
                    "colno": colno,
                    "name": _sql_unquote(toks[0]),
                    "sql_type": " ".join(words),
                    "length": length,
                    "scale": scale,
                    "nullable": not re.search(r"\bNOT NULL\b", rest),
                    "line": code.count("\n", 0, m.end() + off + lead) + 1,
                }
            )
    return out


def sql_column_key(
    table: str, name: str, sql_type: str, length: Optional[int], scale: Optional[int], nullable: bool
) -> str:
    """The cross-reader comparison key for one column: its full declared shape, so a
    disagreement on type, length, scale or nullability is a delta, not just a name."""
    args = "" if length is None else f"({length})" if scale is None else f"({length},{scale})"
    return f"{table}.{name} {sql_type}{args} {'NULLABLE' if nullable else 'NOT NULL'}".upper()


def sql_column_keys(columns: list[dict[str, Any]]) -> set[str]:
    return {
        sql_column_key(c["table"], c["name"], c["sql_type"], c.get("length"), c.get("scale"), c.get("nullable", True))
        for c in columns
    }


def draft_sql_tables(repo: Path) -> dict[str, dict[str, Any]]:
    """Drafted DECLARE TABLE columns for every COBOL/PL/I source that declares one
    (#3344). A file's columns adjudicate a differential delta only once it is
    signed off with `sql_tables_validated` -- the records precedent (#3246)."""
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(repo.rglob("*")):
        if p.is_file() and p.suffix.lower() in SQL_TABLE_EXTS and ".git" not in p.parts:
            cols = sql_table_columns(p.read_text(encoding="utf-8", errors="ignore"), p.suffix.lower() in PLI_EXTS)
            if cols:
                out[p.relative_to(repo).as_posix()] = {
                    "columns": cols,
                    "sql_tables_validated": False,
                    "verification": {"status": "draft", "notes": []},
                }
    return out


# ==============================================================================
# BMS screen-field layouts (#3347)
# ==============================================================================
# This tool's own reading of a BMS map source, over the RAW file (it drops its
# own `*`/`.*` comment lines -- it never sees the engine's PRISM stream). Each
# statement is its physical lines sliced at the HLASM columns (1-71, then 16-71
# for every line whose column 72 is non-blank), concatenated, and tokenized with
# one regex; a blank outside a literal ends the operands unless it is the padding
# between a trailing comma and the next continuation line. It shares the engine's
# CONTRACT (one row per DFHMSD/DFHMDI/DFHMDF, TYPE=FINAL is not a mapset), not its
# code, so an agreement is evidence and a disagreement is a finding.
BMS_EXTS = (".bms",)
_BMS_HEAD = re.compile(r"([A-Z@#$][A-Z0-9@#$_]*)?[ \t]+(DFHMSD|DFHMDI|DFHMDF)(?=[ \t]|$)", re.I)
_BMS_TOKEN = re.compile(r"'(?:[^']|'')*'?|[(),=]|[^\s(),=']+|\s+")
_BMS_KIND = {"DFHMSD": "mapset", "DFHMDI": "map", "DFHMDF": "field"}
# The item keys the comparison reads, shared by this reader's items and the engine's rows.
BMS_ITEM_KEYS = (
    "kind",
    "ordinal",
    "parent_ordinal",
    "name",
    "pos_line",
    "pos_column",
    "length",
    "attrb",
    "picin",
    "picout",
    "initial",
    "occurs",
)


def _bms_operands(text: str, boundaries: set[int]) -> list[list[str]]:
    """The statement's operands as token lists, split at top-level commas."""
    operands: list[list[str]] = [[]]
    depth = 0
    for m in _BMS_TOKEN.finditer(text):
        tok = m.group(0)
        if tok.isspace():
            padding = any(m.start() <= b <= m.end() for b in boundaries)
            if padding and depth == 0 and not operands[-1]:
                continue  # between `,` and the next continuation line
            break
        if tok == "(":
            depth += 1
        elif tok == ")":
            depth -= 1
        if tok == "," and depth == 0:
            operands.append([])
        else:
            operands[-1].append(tok)
    return [o for o in operands if o]


def bms_screen_items(text: str) -> list[dict[str, Any]]:
    """Every DFHMSD/DFHMDI/DFHMDF of one BMS source, in source order, with
    `parent_ordinal` the owning mapset (for a map) or map (for a field)."""
    lines = [ln.rstrip("\r") for ln in text.split("\n")]
    items: list[dict[str, Any]] = []
    mapset = map_ = None
    i = 0
    while i < len(lines):
        if lines[i].startswith(("*", ".*")):
            i += 1
            continue
        first = i
        segments = [lines[i][:71]]
        while len(lines[i]) > 71 and lines[i][71] != " " and i + 1 < len(lines):
            i += 1
            segments.append(lines[i][15:71])
        i += 1
        head = _BMS_HEAD.match(segments[0])
        if not head:
            continue
        kind = _BMS_KIND[head.group(2).upper()]
        body = segments[0][head.end() :]
        lead = len(body) - len(body.lstrip())
        body = body[lead:]
        boundaries, offset = set(), len(body)
        for seg in segments[1:]:
            boundaries.add(offset)
            offset += len(seg)
        row: dict[str, Any] = {
            "kind": kind,
            "name": head.group(1),
            "pos_line": None,
            "pos_column": None,
            "length": None,
            "attrb": None,
            "picin": None,
            "picout": None,
            "initial": None,
            "occurs": None,
            "line": first + 1,
        }
        final = False
        for op in _bms_operands(body + "".join(segments[1:]), boundaries):
            key = op[0].upper()
            value = "".join(op[2:]) if len(op) > 2 and op[1] == "=" else ""
            if key == "TYPE" and value.upper() == "FINAL":
                final = True
            if kind != "field":
                continue
            nums = re.fullmatch(r"\((\d+),(\d+)\)", value)
            if key == "POS" and nums:
                row["pos_line"], row["pos_column"] = int(nums.group(1)), int(nums.group(2))
            elif key in ("LENGTH", "OCCURS") and value.isdigit():
                row[key.lower()] = int(value)
            elif key == "ATTRB":
                row["attrb"] = value.strip("()").upper()
            elif key in ("PICIN", "PICOUT", "INITIAL"):
                lit = value[1:-1] if len(value) > 1 and value.startswith("'") and value.endswith("'") else value
                row[key.lower()] = lit.replace("''", "'").replace("&&", "&")
        if kind == "mapset" and final:
            mapset = map_ = None
            continue
        row["ordinal"] = len(items)
        if kind == "mapset":
            row["parent_ordinal"] = None
            mapset, map_ = row["ordinal"], None
        elif kind == "map":
            row["parent_ordinal"] = mapset
            map_ = row["ordinal"]
        else:
            row["parent_ordinal"] = map_ if map_ is not None else mapset
        items.append(row)
    return items


def bms_layout_units(items: list[dict[str, Any]]) -> set[str]:
    """The BMS comparison unit: one string per mapset, map and field carrying its
    owner and every parsed column, e.g. `field BNK1CA.CUSTNO @6,23 len=10
    attrb=NORM,NUM,FSET`. Works on this reader's items and on the engine's rows
    (the same keys). An unnamed field (a screen literal) is `.` + its position,
    so two literals are two units."""
    by_ordinal = {it["ordinal"]: it for it in items}
    out: set[str] = set()
    for it in items:
        name = (it.get("name") or "").upper()
        if it["kind"] != "field":
            parent = by_ordinal.get(it.get("parent_ordinal"))
            owner = f"{(parent.get('name') or '').upper()}." if parent else ""
            out.add(f"{it['kind']} {owner}{name}")
            continue
        parent = by_ordinal.get(it.get("parent_ordinal"))
        owner = (parent.get("name") or "").upper() if parent else ""
        pos = f"@{it['pos_line']},{it['pos_column']}" if it.get("pos_line") is not None else "@?"
        unit = f"field {owner}.{name} {pos} len={it.get('length')}"
        for col in ("attrb", "picin", "picout", "occurs", "initial"):
            if it.get(col) is not None:
                unit += f" {col}={it[col]!r}" if col == "initial" else f" {col}={it[col]}"
        out.add(unit)
    return out


def bms_symbolic_names(items: list[dict[str, Any]]) -> set[str]:
    """`MAP.FIELD` for every NAMED field -- exactly the names that become
    `<field>L/F/A/I/O` in the generated symbolic map."""
    by_ordinal = {it["ordinal"]: it for it in items}
    out: set[str] = set()
    for it in items:
        if it["kind"] == "field" and it.get("name"):
            parent = by_ordinal.get(it.get("parent_ordinal"))
            out.add(f"{(parent.get('name') or '').upper() if parent else ''}.{it['name'].upper()}")
    return out


def symbolic_map_names(copybook: Path) -> set[str]:
    """`MAP.FIELD` from a GENERATED symbolic-map copybook (IBM's DFHMAPS output):
    each `01 <map>I` input record's `<field>I` items, the suffix dropped. Read with
    this tool's own COBOL data-item reader."""
    out: set[str] = set()
    root = None
    for it in _data_items(Source(copybook)):
        if it["level"] == 1:
            root = it["name"][:-1] if it["name"].endswith("I") else None
        elif root and it["name"] != "FILLER" and it["name"].endswith("I") and it["level"] == 2:
            out.add(f"{root}.{it['name'][:-1]}")
    return out


def draft_bms(repo: Path) -> dict[str, dict[str, Any]]:
    """Drafted screen-field layouts for every BMS source in `repo` (#3347). They
    adjudicate a differential delta only once a map is signed off with
    `fields_validated` -- the records_validated precedent (#3246/#3250)."""
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(repo.rglob("*")):
        if p.is_file() and p.suffix.lower() in BMS_EXTS and ".git" not in p.parts:
            out[p.relative_to(repo).as_posix()] = {
                "fields": bms_screen_items(p.read_text(encoding="utf-8", errors="ignore")),
                "fields_validated": False,
                "verification": {"status": "draft", "notes": []},
            }
    return out


# ==============================================================================
# JCL DD bindings with symbolic parameters resolved (#3345)
# ==============================================================================
# This tool's own reading of a JCL member: it works on the RAW file (it drops
# `//*` comments and columns 73-80 itself, never seeing the PRISM stream), splits
# each statement with a character scanner rather than the engine's statement
# regex, and substitutes symbols with a hand-written scan rather than a regex
# `sub`. It shares the engine's CONTRACT -- which statements bind a DSN, how
# SET / PROC defaults / EXEC overrides combine (EXEC > PROC default > SET), what
# counts as statically resolvable inside one file -- not its code, so an agreement
# is evidence and a disagreement is a finding.
JCL_EXTS = (".jcl", ".prc")
_JCL_OPS = {"JOB", "EXEC", "DD", "PROC", "PEND", "SET", "INCLUDE", "JCLLIB"}
_JCL_NAME_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$")
_JCL_EXEC_PARAMS = {
    "PGM", "PROC", "PARM", "PARMDD", "COND", "REGION", "REGIONX", "TIME", "ACCT", "ADDRSPC",
    "DPRTY", "PERFORM", "RD", "CCSID", "DYNAMNBR", "MEMLIMIT", "TVSMSG", "TVSAMCOM",
}  # fmt: skip


def _jcl_field_end(text: str) -> int:
    """Index of the first blank outside apostrophes -- where the operand field ends."""
    quoted = False
    for i, ch in enumerate(text):
        if ch == "'":
            quoted = not quoted
        elif ch in " \t" and not quoted:
            return i
    return len(text)


def _jcl_key_statements(text: str) -> list[tuple[int, str, str, str]]:
    """(line, NAME, OP, operand field) per logical statement, continuations joined."""
    out: list[list] = []
    open_stmt = False
    for no, raw in enumerate(text.splitlines(), 1):
        line = raw[:72].rstrip()
        if not line.startswith("//") or line.startswith("//*"):
            if not line.startswith("//*"):
                open_stmt = False
            continue
        body = line[2:]
        name_end = 0
        while name_end < len(body) and body[name_end] not in " \t":
            name_end += 1
        name, rest = body[:name_end].upper(), body[name_end:].lstrip()
        op_end = 0
        while op_end < len(rest) and rest[op_end] not in " \t":
            op_end += 1
        op = rest[:op_end].upper()
        if op in _JCL_OPS and all(c in _JCL_NAME_CHARS or c == "_" for c in name):
            operands = rest[op_end:].lstrip()
            operands = operands[: _jcl_field_end(operands)]
            out.append([no, name, op, operands])
            open_stmt = operands.endswith(",")
        elif open_stmt and not name:
            more = body.lstrip()
            more = more[: _jcl_field_end(more)]
            out[-1][3] += more
            open_stmt = more.endswith(",")
        else:
            open_stmt = False
    return [tuple(s) for s in out]


def _jcl_key_split(field: str) -> list[tuple[Optional[str], str]]:
    """Top-level comma split (not inside '...' or (...)) into (KEY or None, value)."""
    pieces, buf, depth, quoted = [], [], 0, False
    for ch in field:
        if ch == "'":
            quoted = not quoted
        if not quoted and ch == "(":
            depth += 1
        if not quoted and ch == ")" and depth:
            depth -= 1
        if ch == "," and not quoted and depth == 0:
            pieces.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    pieces.append("".join(buf))
    out: list[tuple[Optional[str], str]] = []
    for p in pieces:
        eq = p.find("=")
        head = p[:eq] if eq > 0 else ""
        if head and head[0].isalpha() or head[:1] in ("@", "#", "$"):
            out.append((head.upper(), p[eq + 1 :]))
        elif p:
            out.append((None, p))
    return out


def _jcl_key_value(v: str) -> str:
    if len(v) > 1 and v[0] == "'" and v[-1] == "'":
        return v[1:-1].replace("''", "'")
    return v


def _jcl_key_symbols(field: str, null_is_value: bool) -> dict[str, str]:
    table = {}
    for k, v in _jcl_key_split(field):
        if k is None or "." in k or len(k) > 8 or not all(c in _JCL_NAME_CHARS for c in k):
            continue
        if v or null_is_value:
            table[k] = _jcl_key_value(v)
    return table


def _jcl_key_subst(text: str, table: dict[str, str], depth: int = 0) -> tuple[str, bool]:
    """Substitute `&NAME` / `&NAME.` by scanning; (result, every reference resolved)."""
    out, i, ok = [], 0, True
    upper = text.upper()
    while i < len(text):
        if text[i] != "&":
            out.append(text[i])
            i += 1
            continue
        if text[i + 1 : i + 2] == "&":  # a temporary-dataset prefix, not a symbol
            out.append("&&")
            ok = False
            i += 2
            continue
        j = i + 1
        while j < len(text) and j - i <= 8 and upper[j] in _JCL_NAME_CHARS:
            j += 1
        name = upper[i + 1 : j]
        end = j + 1 if text[j : j + 1] == "." else j
        if not name or name[0].isdigit() or name not in table or depth >= 8:
            out.append(text[i:end])
            ok = False
        else:
            val, sub_ok = _jcl_key_subst(table[name], table, depth + 1)
            out.append(val)
            ok = ok and sub_ok
        i = end
    return "".join(out), ok


def _jcl_key_dsn(dsn: str, table: dict[str, str]) -> Optional[str]:
    text, ok = _jcl_key_subst(dsn, table)
    if not ok:
        return None
    for stop in (" ", "\t", ","):
        text = text.split(stop, 1)[0]
    return text.upper() or None


def jcl_dataset_bindings(text: str) -> list[dict[str, Any]]:
    """Every DD -> DSN binding in one JCL member, with the DSN's symbols resolved.

    Each binding: line, step, dd, dsn (as written, upper), resolved (None unless
    every symbol resolved) and status (literal / resolved / proc_default /
    ambiguous / unresolved). `&&TEMP` and `*` (backward reference) DSNs are not
    bindings; override DDs (`//STEP.DD`) and cross-member PROC callers are out of
    scope -- the same contract the engine states."""
    rows: list[dict[str, Any]] = []
    job = False
    sets: dict[str, str] = {}
    procs: list[dict[str, Any]] = []
    named: dict[str, dict[str, Any]] = {}
    proc: Optional[dict[str, Any]] = None
    step, last_dd = "", ""
    for no, name, op, field in _jcl_key_statements(text):
        if op == "JOB":
            job = True
        elif op == "SET":
            scope = proc["sets"] if proc is not None else sets
            for k, v in _jcl_key_symbols(field, True).items():
                scope[k] = _jcl_key_subst(v, {**sets, **scope})[0]
        elif op == "PROC":
            proc = {
                "defaults": _jcl_key_symbols(field, False),
                "sets": {},
                "rows": [],
                "calls": [],
                "sets0": dict(sets),
            }
            procs.append(proc)
            if job and name:
                named[name] = proc
            step, last_dd = "", ""
        elif op == "PEND":
            proc, step, last_dd = None, "", ""
        elif op == "EXEC":
            step, last_dd = name, ""
            ops = _jcl_key_split(field)
            if proc is None and not any(k == "PGM" for k, _ in ops):
                target = next((v for k, v in ops if k == "PROC"), None) or next((v for k, v in ops if k is None), "")
                if target.upper() in named:
                    over = {
                        k: _jcl_key_subst(v, sets)[0]
                        for k, v in _jcl_key_symbols(field, True).items()
                        if k not in _JCL_EXEC_PARAMS
                    }
                    named[target.upper()]["calls"].append((dict(sets), over))
        elif op == "DD":
            if name:
                last_dd = name
            dd = name or last_dd
            dsn = next((v for k, v in _jcl_key_split(field) if k in ("DSN", "DSNAME")), None)
            if not dd or not dsn or dsn.startswith(("&&", "*", "'")):
                continue
            row = {"line": no, "step": step or None, "dd": dd, "dsn": dsn.upper()}
            rows.append(row)
            if proc is not None:
                proc["rows"].append((row, dict(proc["sets"])))
            elif "&" not in dsn:
                row.update(resolved=row["dsn"], status="literal")
            else:
                got = _jcl_key_dsn(dsn, sets)
                row.update(resolved=got, status="resolved" if got else "unresolved")
    for p in procs:
        for row, local in p["rows"]:
            if "&" not in row["dsn"]:
                row.update(resolved=row["dsn"], status="literal")
            elif not p["calls"]:
                got = _jcl_key_dsn(row["dsn"], {**p["sets0"], **local, **p["defaults"]})
                row.update(resolved=got, status="proc_default" if got else "unresolved")
            else:
                seen = {_jcl_key_dsn(row["dsn"], {**s0, **local, **p["defaults"], **ov}) for s0, ov in p["calls"]}
                if None in seen:
                    row.update(resolved=None, status="unresolved")
                elif len(seen) > 1:
                    row.update(resolved=None, status="ambiguous")
                else:
                    row.update(resolved=seen.pop(), status="resolved")
    return rows


def jcl_dsn_values(rows: list[dict[str, Any]]) -> set[str]:
    """The comparison unit: `STEP/DD@line=RESOLVED[status]`, one per binding. Works on
    this reader's rows and on the engine's (keys step_name/dd_name/dsn_resolved/...)."""
    out = set()
    for r in rows:
        step = r.get("step", r.get("step_name")) or "-"
        dd = r.get("dd", r.get("dd_name"))
        resolved = r.get("resolved", r.get("dsn_resolved")) or "?"
        status = r.get("status", r.get("dsn_resolution"))
        out.add(f"{step}/{dd}@{r['line']}={resolved}[{status}]")
    return out


def draft_jcl(repo: Path) -> dict[str, dict[str, Any]]:
    """Drafted JCL DD bindings (with resolved DSNs) for every JCL member in `repo`
    (#3345). They adjudicate a differential delta only once a member is signed off
    with `dsns_validated` -- the records_validated precedent (#3246)."""
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(repo.rglob("*")):
        if p.is_file() and p.suffix.lower() in JCL_EXTS and ".git" not in p.parts:
            rows = jcl_dataset_bindings(p.read_text(encoding="utf-8", errors="ignore"))
            if rows:
                out[p.relative_to(repo).as_posix()] = {
                    "bindings": rows,
                    "dsns_validated": False,
                    "verification": {"status": "draft", "notes": []},
                }
    return out


# ==============================================================================
# CSD resource definitions beyond TRANSACTION/PROGRAM (#3356)
# ==============================================================================
# This tool's own reading of a CSD deck (a `.csd` file, or the DFHCSDUP SYSIN
# inline in a JCL job): the RAW file, split into DEFINE records by a line walk,
# each record tokenized by a character scanner into (KEYWORD, value) operands.
# It models DFHCSDUP's quoting rule directly -- a value is quoted only when it
# BEGINS with an apostrophe, `''` inside it is an escaped apostrophe -- where the
# engine tracks quotes anywhere in a value and bounds its scan. It shares the
# engine's CONTRACT (which operand feeds which key column) and none of its code,
# so an agreement is evidence and a disagreement is a finding.
CSD_EXTS = (".csd",)
_CSD_KEY_COMMANDS = {"DEFINE", "DELETE", "ALTER", "ADD", "REMOVE", "LIST", "UPGRADE", "COPY"}
# The comparison unit's attributes, in a fixed order.
CSD_KEY_FIELDS = (
    "group", "dsname", "ddname", "record_format", "key_length", "record_size",
    "queue_type", "plan", "db2_entry", "transid", "program",
)  # fmt: skip


def _csd_key_operands(text: str) -> list[tuple[str, Optional[str]]]:
    """(KEYWORD, value or None) per operand of one record, in order."""
    out: list[tuple[str, Optional[str]]] = []
    i, n = 0, len(text)
    while i < n:
        if not (text[i].isalpha() or text[i] in "@#$"):
            i += 1
            continue
        j = i
        while j < n and (text[j].isalnum() or text[j] in "@#$"):
            j += 1
        word = text[i:j].upper()
        k = j
        while k < n and text[k] in " \t":
            k += 1
        if k >= n or text[k] != "(":
            out.append((word, None))
            i = j
            continue
        k += 1
        while k < n and text[k] in " \t":
            k += 1
        buf: list[str] = []
        if k < n and text[k] == "'":  # a quoted value: to the closing apostrophe
            k += 1
            while k < n:
                if text[k] == "'" and text[k + 1 : k + 2] == "'":
                    buf.append("'")
                    k += 2
                elif text[k] == "'":
                    k += 1
                    break
                else:
                    buf.append(text[k])
                    k += 1
            while k < n and text[k] != ")":
                k += 1
            k += 1
        else:  # an unquoted value: to the matching close paren
            depth = 1
            while k < n:
                if text[k] == "(":
                    depth += 1
                elif text[k] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                buf.append(text[k])
                k += 1
            k += 1
        out.append((word, "".join(buf).strip()))
        i = k
    return out


def csd_resource_definitions(text: str) -> list[dict[str, Any]]:
    """Every `DEFINE <type>(<name>)` record in one CSD deck, with its key columns.

    A record starts at a DEFINE line and runs to the next CSD command, `*` or `//`
    line, blank line, or end of text. Rows carry `line`, `resource_type`, `name`
    and the CSD_KEY_FIELDS (None when the record does not carry the operand)."""
    records: list[tuple[int, list[str]]] = []
    for no, raw in enumerate(text.split("\n"), 1):
        stripped = raw.strip()
        first = stripped.split(None, 1)[0].upper() if stripped else ""
        if not stripped or stripped.startswith(("*", "//", "/*")):
            records.append((0, []))  # a separator
            continue
        if first in _CSD_KEY_COMMANDS:
            records.append((no if first == "DEFINE" else 0, [stripped]))
            continue
        if records and records[-1][0]:
            records[-1][1].append(stripped)
    rows: list[dict[str, Any]] = []
    for no, lines in records:
        if not no:
            continue
        ops = _csd_key_operands(" ".join(lines))
        if len(ops) < 2 or ops[0] != ("DEFINE", None) or ops[1][1] is None:
            continue
        # The engine's name contract: A-Z 0-9 @ # $ only. A template placeholder
        # (cics-genapp's `DB2CONN(<DB2SSID>)`) is not a resource either side keeps.
        if not ops[1][1] or not all(c.isalnum() or c in "@#$" for c in ops[1][1]):
            continue
        rtype, name = ops[1][0], ops[1][1].upper()
        vals: dict[str, str] = {}
        for word, value in ops[2:]:
            if value is not None and word not in vals:
                vals[word] = value

        def up(key: str, _vals: dict = vals) -> Optional[str]:
            return _vals[key].upper() if _vals.get(key) else None

        def num(key: str, _vals: dict = vals) -> Optional[int]:
            v = _vals.get(key, "")
            return int(v) if v.isdigit() else None

        rows.append(
            {
                "line": no,
                "resource_type": rtype,
                "name": name,
                "group": up("GROUP"),
                "dsname": up("DSNAME") or up("DSNAME01"),
                "ddname": up("DDNAME"),
                "record_format": up("RECORDFORMAT"),
                "key_length": num("KEYLENGTH"),
                "record_size": num("RECORDSIZE"),
                "queue_type": up("TYPE") if rtype == "TDQUEUE" else None,
                "plan": up("PLAN"),
                "db2_entry": up("ENTRY") if rtype == "DB2TRAN" else None,
                "transid": name if rtype == "TRANSACTION" else (up("TRANSID") or up("TRANSACTION")),
                "program": name if rtype == "PROGRAM" else up("PROGRAM"),
            }
        )
    return rows


def csd_resource_values(rows: list[dict[str, Any]]) -> set[str]:
    """The comparison unit: `TYPE(NAME)@line k=v ...` over the key columns that are
    set. Works on this reader's rows and on the engine's EngineCsdResource dicts."""
    out = set()
    for r in rows:
        attrs = " ".join(f"{k}={r[k]}" for k in CSD_KEY_FIELDS if r.get(k) is not None)
        out.add(f"{r['resource_type']}({r['name']})@{r['line']} {attrs}".rstrip())
    return out


def is_csd_deck(path: Path, text: str) -> bool:
    """A `.csd` file, or a JCL job that runs DFHCSDUP (its SYSIN may be inline)."""
    suffix = path.suffix.lower()
    return suffix in CSD_EXTS or (suffix in JCL_EXTS and "PGM=DFHCSDUP" in text.upper())


def draft_csd(repo: Path) -> dict[str, dict[str, Any]]:
    """Drafted CSD resource definitions for every deck in `repo` (#3356). They
    adjudicate a differential delta only once a deck is signed off with
    `resources_validated` -- the records_validated precedent (#3246)."""
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(repo.rglob("*")):
        if not p.is_file() or ".git" in p.parts:
            continue
        text = p.read_text(encoding="utf-8", errors="ignore") if p.suffix.lower() in CSD_EXTS + JCL_EXTS else ""
        if text and is_csd_deck(p, text):
            rows = csd_resource_definitions(text)
            if rows:
                out[p.relative_to(repo).as_posix()] = {
                    "resources": rows,
                    "resources_validated": False,
                    "verification": {"status": "draft", "notes": []},
                }
    return out


# ==============================================================================
# #3355: CICS COMMAREA operands -- this tool's own reader over its fixed-format
# Source model (comments dropped, literals blanked), sharing no code with the
# engine's PRISM-stream walker in mainframe_boundary.
# ==============================================================================
_KEY_CICS_EXEC = re.compile(r"\bEXEC\s+CICS\s+(LINK|XCTL|RETURN)\b")


def _key_paren_operand(block: str, keyword: str) -> Optional[str]:
    """`KEYWORD( ... )` inside one EXEC block, paren-balanced, whitespace-collapsed.
    The keyword must stand alone (`DFHCOMMAREA(`/`DATALENGTH(` are other words)."""
    for m in re.finditer(rf"(?<![A-Z0-9-]){keyword}\s*\(", block):
        depth = 1
        for i in range(m.end(), len(block)):
            depth += {"(": 1, ")": -1}.get(block[i], 0)
            if depth == 0:
                return " ".join(block[m.end() : i].split()) or None
        return None
    return None


def cics_commareas(src: Source) -> list[dict[str, Any]]:
    """Every CICS LINK/XCTL (and RETURN with a TRANSID) that passes a COMMAREA:
    `verb`, `line` (of the EXEC), `commarea`, `length`, `datalength` as written."""
    out = []
    for m in _KEY_CICS_EXEC.finditer(src.text):
        seg = src.text[m.end() : m.end() + 600]
        end = seg.find("END-EXEC")
        block = src.raw_text[m.end() : m.end() + (end if end >= 0 else 600)]
        verb = m.group(1)
        if verb == "RETURN":
            if _key_paren_operand(block, "TRANSID") is None:
                continue
            verb = "RETURN TRANSID"
        area = _key_paren_operand(block, "COMMAREA")
        if area is None:
            continue
        out.append(
            {
                "verb": verb,
                "line": src.line_of(m.start()),
                "commarea": area,
                "length": _key_paren_operand(block, "LENGTH"),
                "datalength": _key_paren_operand(block, "DATALENGTH"),
            }
        )
    return out


def commarea_values(rows: list[dict[str, Any]]) -> set[str]:
    """The comparison unit: `VERB@line=COMMAREA|LENGTH|DATALENGTH` ('-' for none).
    Works on this reader's rows and on the engine's (commarea_length/_datalength)."""
    out = set()
    for r in rows:
        length = r.get("length", r.get("commarea_length")) or "-"
        datalength = r.get("datalength", r.get("commarea_datalength")) or "-"
        out.add(f"{r['verb']}@{r['line']}={r['commarea']}|{length}|{datalength}")
    return out


# ==============================================================================
# CICS resource operations (#3351-#3354)
# ==============================================================================
# This tool's own reading of the EXEC CICS commands that name a resource. It works
# on `Source` -- the RAW file, cols 8-72 of every non-comment line, upper-cased --
# finds `EXEC CICS` in the LITERAL-BLANKED twin (so a DISPLAY 'EXEC CICS ...' is
# never a command), cuts the block at the next END-EXEC, and reads the options
# with one nesting-limited regex. Names resolve through this tool's own `_value_of`
# (the VALUE reader the call-site key already uses), then a sole `MOVE 'LIT' TO`
# literal. It shares the engine's CONTRACT, not its code: one row per command
# naming a FILE (FILE/DATASET), MAP, QUEUE (QUEUE/QNAME, TS unless TD), CONTAINER
# or a CHANNEL passed by LINK/XCTL/START/RETURN/RUN.
CICS_EXTS = PROGRAM_EXTS + COPYBOOK_EXTS
_CICS_EXEC = re.compile(r"\bEXEC\s+CICS\b")
_CICS_END = re.compile(r"\bEND-EXEC\b")
_CICS_OPTION = re.compile(r"([A-Z][A-Z0-9-]*)\s*(\((?:[^()']|'[^']*'|\([^()]*\))*\))?")
_CICS_MOVE = re.compile(rf"\bMOVE\s+(?:'([^'\n]*)'|\"([^\"\n]*)\")\s+TO\s+({NAME})")
_CICS_FILE = {
    "READ": "read",
    "READNEXT": "read",
    "READPREV": "read",
    "STARTBR": "browse",
    "RESETBR": "browse",
    "ENDBR": "browse",
    "WRITE": "write",
    "REWRITE": "update",
    "DELETE": "delete",
    "UNLOCK": "unlock",
}
_CICS_QUEUE = {"WRITEQ": "write", "READQ": "read", "DELETEQ": "delete"}
_CICS_CONTAINER = {"PUT": "write", "GET": "read", "MOVE": "move", "DELETE": "delete"}
_CICS_MAP = {"SEND": "write", "RECEIVE": "read"}
_CICS_PASS = {"LINK": "PROGRAM", "XCTL": "PROGRAM", "START": "TRANSID", "RETURN": "TRANSID", "RUN": "TRANSID"}


def _cics_value_of(src: Source, ident: str) -> Optional[str]:
    """`ident`'s quoted VALUE, first declaration wins. Unlike `_value_of` (80 chars)
    the entry may run up to its terminating period, because carddemo pads PIC to
    column 72 and writes VALUE on the next line."""
    m = re.search(
        rf"(?m)^\s*\d{{1,2}}\s+{re.escape(ident)}(?![A-Z0-9-])[^.]{{0,400}}?\bVALUE\s+(?:IS\s+)?(?:'([^']*)'|\"([^\"]*)\")",
        src.raw_text,
    )
    if not m:
        return None
    return ((m.group(1) if m.group(1) is not None else m.group(2)) or "").strip() or None


def cics_resource_ops(path: Path) -> list[dict[str, Any]]:
    """Every EXEC CICS command in one COBOL source that names a resource, this
    tool's own reading (see the section header)."""
    src = Source(path)
    moves: dict[str, set[str]] = {}
    for m in _CICS_MOVE.finditer(src.raw_text):
        lit = (m.group(1) if m.group(1) is not None else m.group(2) or "").strip()
        if lit:
            moves.setdefault(m.group(3), set()).add(lit)

    def resolve(operand: Optional[str]) -> tuple[Optional[str], Optional[str], Optional[str]]:
        if operand is None:
            return None, None, None
        op = operand.strip()
        if op[:1] in "'\"" and len(op) > 1 and op[-1] == op[0]:
            return (op[1:-1].strip() or None), "literal", None
        if not re.fullmatch(NAME, op) or op[0].isdigit():
            return None, "expression", None
        value = _cics_value_of(src, op)
        if value:
            return value, "value", None
        found = moves.get(op, set())
        if len(found) == 1:
            return next(iter(found)), "move", None
        if found:
            return None, "ambiguous", ",".join(sorted(found))
        return None, "unresolved", None

    out: list[dict[str, Any]] = []
    for m in _CICS_EXEC.finditer(src.text):
        end = _CICS_END.search(src.text, m.end())
        body = src.raw_text[m.end() : end.start() if end else len(src.raw_text)]
        opts: list[tuple[str, Optional[str]]] = [
            (o.group(1), " ".join(o.group(2)[1:-1].split()) if o.group(2) else None)
            for o in _CICS_OPTION.finditer(body)
        ]
        if not opts or opts[0][1] is not None:
            continue
        verb = opts[0][0]
        d: dict[str, Optional[str]] = {}
        for k, v in opts[1:]:
            d.setdefault(k, v)
        if verb in _CICS_CONTAINER and "CONTAINER" in d:
            kind, access, name_key, q_key, qtype = "CONTAINER", _CICS_CONTAINER[verb], "CONTAINER", "CHANNEL", None
        elif verb in _CICS_FILE and ("FILE" in d or "DATASET" in d):
            kind, access, q_key, qtype = "FILE", _CICS_FILE[verb], None, None
            name_key = "FILE" if "FILE" in d else "DATASET"
        elif verb in _CICS_MAP and "MAP" in d:
            kind, access, name_key, q_key, qtype = "MAP", _CICS_MAP[verb], "MAP", "MAPSET", None
        elif verb in _CICS_QUEUE and ("QUEUE" in d or "QNAME" in d):
            kind, access, q_key = "QUEUE", _CICS_QUEUE[verb], None
            name_key = "QUEUE" if "QUEUE" in d else "QNAME"
            qtype = "TD" if "TD" in d else "TS"
        elif verb in _CICS_PASS and "CHANNEL" in d:
            kind, access, name_key, q_key, qtype = "CHANNEL", "pass", "CHANNEL", _CICS_PASS[verb], None
        else:
            continue
        name, resolution, candidates = resolve(d.get(name_key))
        qualifier = qtype if qtype else resolve(d.get(q_key) if q_key else None)[0]
        clause = next((c for c in ("INTO", "FROM", "SET") if d.get(c)), None)
        out.append(
            {
                "verb": verb,
                "kind": kind,
                "access": access,
                "name": name,
                "resolution": resolution,
                "candidates": candidates,
                "qualifier": qualifier,
                "record_clause": clause,
                "record": d[clause] if clause else None,
                "line": src.line_of(m.start()),
            }
        )
    return out


def cics_resource_keys(rows: list[dict[str, Any]]) -> set[str]:
    """The comparison unit, one per command: `L<line> VERB KIND NAME q=QUALIFIER
    CLAUSE=RECORD`, where an unresolved NAME is `<resolution[:candidates]>`. Works on
    this reader's rows and on the engine's (the same keys)."""
    out = set()
    for r in rows:
        name = r.get("name")
        if name:
            shown = name.upper()
        else:
            cands = r.get("candidates")
            shown = f"<{r.get('resolution')}{':' + cands.upper() if cands else ''}>"
        record = f" {r['record_clause']}={(r.get('record') or '').upper()}" if r.get("record_clause") else ""
        out.add(
            f"L{r['line']} {r['verb']} {r['kind']} {shown} q={(r.get('qualifier') or '-').upper()}{record}".rstrip()
        )
    return out


def engine_cics_row(op: Any) -> dict[str, Any]:
    """An engine `EngineCicsResource` in this reader's row shape (for the unit key)."""
    return {
        "verb": op.verb,
        "kind": op.kind,
        "name": op.name,
        "resolution": op.resolution,
        "candidates": op.candidates,
        "qualifier": op.qualifier,
        "record_clause": op.record_clause,
        "record": op.record,
        "line": op.line,
    }


def draft_cics(repo: Path) -> dict[str, dict[str, Any]]:
    """Drafted CICS resource operations for every COBOL source that issues one
    (#3351-#3354). They adjudicate a differential delta only once a file is signed
    off with `cics_validated` -- the records_validated precedent (#3246)."""
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(repo.rglob("*")):
        if p.is_file() and p.suffix.lower() in CICS_EXTS and ".git" not in p.parts:
            rows = cics_resource_ops(p)
            if rows:
                out[p.relative_to(repo).as_posix()] = {
                    "operations": rows,
                    "cics_validated": False,
                    "verification": {"status": "draft", "notes": []},
                }
    return out


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
        dead[u["name"]] = {"reason": reason, "trivial": _is_exit_only(body)}

    copybooks = []
    for rx, via in ((_COPY, "COPY"), (_SQL_INCLUDE, "SQL INCLUDE")):
        # Matched on the raw text so a quoted member (`COPY 'CSUTLDWY'.`, CardDemo)
        # keeps its name, then kept only where the keyword itself survives literal
        # blanking -- a `COPY` inside a DISPLAY literal is not a copy.
        for m in rx.finditer(src.raw_text):
            kw = m.start() + m.group(0).index("COPY" if via == "COPY" else "EXEC")
            if src.text[kw : kw + 4] != src.raw_text[kw : kw + 4]:
                continue
            name = m.group(1)
            library = m.group(2) if via == "COPY" else None
            entry = {"name": name, "via": via, "line": src.line_of(m.start(1)), "library": library}
            entry.update(resolve_copybook(name, library, path, repo, files))
            copybooks.append(entry)

    selects = {m.group(1): m.group(2) for m in _SELECT.finditer(src.text)}
    modes: dict[str, set[str]] = {k: set() for k in selects}
    for m in re.finditer(r"(?<![\w-])OPEN\s+", src.text):
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
        # #3355: the COMMAREA each CICS transfer passes. Drafted; adjudicates a
        # differential delta only once the program is `commareas_validated`.
        "commareas": cics_commareas(src),
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
    key: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "corpus": corpus,
        "url": url,
        "ref": ref,
        "programs": {},
        "pli_programs": draft_pli(repo),  # #3250
        "sql_tables": draft_sql_tables(repo),  # #3344
        "bms_maps": draft_bms(repo),  # #3347
        "jcl_jobs": draft_jcl(repo),  # #3345
        "csd_decks": draft_csd(repo),  # #3356
        "cics_resources": draft_cics(repo),  # #3351-#3354
    }
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
def _pair_str(pair: tuple) -> tuple[str, str]:
    """A scored (program, value) pair with the value flattened to one stable string."""
    prog, value = pair
    return str(prog), value if isinstance(value, str) else json.dumps(value, sort_keys=True, default=str)


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
    from gitgalaxy.tools.cobol_to_cobol.cobol_graveyard_finder import (
        COPY_PATTERN,
        _trim_fixed_format,
        copy_member,
        find_copybook,
    )

    # Cols 73-80 trimmed first, exactly as resolve_copybooks does before matching.
    text = "\n".join(
        _trim_fixed_format(line) for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
    )
    named = {copy_member(m) for m in COPY_PATTERN.finditer(text)}
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


# The key's `calls` are program invocations only (CALL, EXEC CICS LINK/XCTL).
# The engine's call_site_data also carries the transaction-routing verbs
# (#3251), whose target is a TRANSID, not a program -- mirrors
# galaxy_ir.TRANSACTION_ROUTING_VERBS, kept local so scoring needs no import.
_TRANSACTION_ROUTING_VERBS = frozenset({"RETURN TRANSID", "START TRANSID", "RUN TRANSID"})


def engine_call_targets(calls) -> set[str]:
    """The program names an engine file's call sites denote, excluding TRANSID routing."""
    return {c.target for c in calls if c.target and c.verb not in _TRANSACTION_ROUTING_VERBS}


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
        # against the key with no forge column. Transaction-routing sites
        # (`RETURN TRANSID` etc.) are not program calls; see engine_call_targets.
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
        # #3250: PL/I DECLARE leaf fields (dotted paths), per PL/I file. Truth is
        # this tool's own PL/I reader; there is no PL/I forge; engine is record_data.
        "PL/I record fields",
        # #3344: DB2 DECLARE TABLE columns (full shape key), per declaring file.
        # Truth is this tool's own terminator-cut reader; no forge reads them;
        # engine is sql_table_data.
        "DB2 table columns",
        # #3347: BMS screen-field layout units (mapset/map/field with position,
        # length and attributes), per map source. Truth is this tool's own BMS
        # reader; there is no BMS forge; engine is screen_field_data.
        "BMS screen fields",
        # #3345: JCL DD bindings with their symbolic-parameter-resolved DSN, per JCL
        # member. Truth is this tool's own JCL reader; there is no JCL forge; engine
        # is dataset_data (dsn_resolved + dsn_resolution).
        "JCL resolved DSNs",
        # #3356: CSD resource definitions (type, name and key attributes), per deck.
        # Truth is this tool's own CSD tokenizer; there is no forge for them; engine
        # is csd_resource_data.
        "CSD resources",
        # #3351-#3354: EXEC CICS FILE/MAP/QUEUE/CONTAINER/CHANNEL operations, per
        # COBOL source. Truth is this tool's own EXEC CICS reader; no forge reads
        # them; engine is cics_resource_data.
        "CICS resources",
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
            (engine_call_targets(ef.calls) if ef else None),
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

    for rel, k in key.get("pli_programs", {}).items():
        ef = ir.files.get(rel) if ir else None
        engine_items = (
            [{"ordinal": it.ordinal, "parent_ordinal": it.parent_ordinal, "name": it.name} for it in ef.data_items]
            if ef
            else None
        )
        add(
            "PL/I record fields",
            rel,
            pli_record_fields(k.get("records", [])),
            None,
            pli_record_fields(engine_items, "parent_ordinal") if engine_items is not None else None,
        )

    for rel, k in key.get("sql_tables", {}).items():
        ef = ir.files.get(rel) if ir else None
        add(
            "DB2 table columns",
            rel,
            sql_column_keys(k.get("columns", [])),
            None,
            (
                {
                    sql_column_key(t.name, c.name, c.sql_type, c.length, c.scale, c.nullable)
                    for t in ef.sql_tables
                    for c in t.columns
                }
                if ef
                else None
            ),
        )

    for rel, k in key.get("bms_maps", {}).items():
        ef = ir.files.get(rel) if ir else None
        engine_rows = [{c: getattr(sf, c) for c in BMS_ITEM_KEYS} for sf in ef.screen_fields] if ef else None
        add(
            "BMS screen fields",
            rel,
            bms_layout_units(k.get("fields", [])),
            None,
            bms_layout_units(engine_rows) if engine_rows is not None else None,
        )

    for rel, k in key.get("jcl_jobs", {}).items():
        ef = ir.files.get(rel) if ir else None
        add(
            "JCL resolved DSNs",
            rel,
            jcl_dsn_values(k.get("bindings", [])),
            None,
            (
                jcl_dsn_values(
                    [
                        {
                            "step_name": d.step_name,
                            "dd_name": d.dd_name,
                            "dsn_resolved": d.dsn_resolved,
                            "dsn_resolution": d.dsn_resolution,
                            "line": d.line,
                        }
                        for d in ef.datasets
                        if d.is_binding
                    ]
                )
                if ef
                else None
            ),
        )

    for rel, k in key.get("csd_decks", {}).items():
        ef = ir.files.get(rel) if ir else None
        add(
            "CSD resources",
            rel,
            csd_resource_values(k.get("resources", [])),
            None,
            csd_resource_values([r.__dict__ for r in ef.csd_resources]) if ef else None,
        )

    for rel, k in key.get("cics_resources", {}).items():
        ef = ir.files.get(rel) if ir else None
        add(
            "CICS resources",
            rel,
            cics_resource_keys(k.get("operations", [])),
            None,
            cics_resource_keys([engine_cics_row(op) for op in ef.cics_resources]) if ef else None,
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
                result["fields"].setdefault(f, {})[side] = {
                    "tp": len(t & got),
                    "got": len(got),
                    "truth": len(t),
                    # The individual (program, value) pairs behind the counts, for
                    # the ground-truth ledger (tests/tools/ground_truth_ledger.py).
                    "fp": sorted(_pair_str(x) for x in got - t),
                    "fn": sorted(_pair_str(x) for x in t - got),
                }
        md.append(f"| {f} | {cols[0]} | {cols[1]} |")
    md.append("")
    md.append("P = correct / reported, R = correct / true. Sets are (program, value) pairs.")
    return result, "\n".join(md) + "\n"


def sample_claims(key: dict[str, Any], n: int, seed: int) -> list[dict[str, Any]]:
    """A seeded random sample of the key's program-level claims, for a human spot
    check (the `human_signed` tier): dead verdicts, PROGRAM-IDs, copybook
    resolutions, call targets and file modes, drawn uniformly over all of them."""
    import random

    claims: list[dict[str, Any]] = []
    for rel, p in key["programs"].items():
        claims.append({"program": rel, "kind": "program_id", "claim": f"PROGRAM-ID is {p['program_id']}"})
        live = [u for u in p["units"] if u["name"] not in p["dead"]]
        for name, d in p["dead"].items():
            claims.append({"program": rel, "kind": "dead", "claim": f"{name} is unreachable ({d['reason']})"})
        for u in live:
            claims.append({"program": rel, "kind": "live", "claim": f"{u['name']} (line {u['line']}) is reachable"})
        for c in p["copybooks"]:
            to = c["resolves_to"] or f"nothing in the repository ({c['why']})"
            claims.append(
                {"program": rel, "kind": "copybook", "claim": f"{c['via']} {c['name']} (line {c['line']}) -> {to}"}
            )
        for c in p["calls"]:
            claims.append(
                {
                    "program": rel,
                    "kind": "call",
                    "claim": f"{c['verb']} {c['operand']} (line {c['line']}) -> {c['target']}",
                }
            )
        for f in p["files"]:
            claims.append(
                {"program": rel, "kind": "file", "claim": f"{f['internal']} DD {f['dd']} opened {f['modes']}"}
            )
    return random.Random(seed).sample(claims, min(n, len(claims)))


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
    a = sub.add_parser("add-pli")
    a.add_argument("repo", type=Path)
    a.add_argument("--key", type=Path, required=True)
    q = sub.add_parser("add-sql-tables")
    q.add_argument("repo", type=Path)
    q.add_argument("--key", type=Path, required=True)
    b = sub.add_parser("add-bms")
    b.add_argument("repo", type=Path)
    b.add_argument("--key", type=Path, required=True)
    j = sub.add_parser("add-jcl")
    j.add_argument("repo", type=Path)
    j.add_argument("--key", type=Path, required=True)
    c = sub.add_parser("add-csd")
    c.add_argument("repo", type=Path)
    c.add_argument("--key", type=Path, required=True)
    cm = sub.add_parser("add-commarea")
    cm.add_argument("repo", type=Path)
    cm.add_argument("--key", type=Path, required=True)
    x = sub.add_parser("add-cics")
    x.add_argument("repo", type=Path)
    x.add_argument("--key", type=Path, required=True)
    sp = sub.add_parser("sample")
    sp.add_argument("--key", type=Path, required=True)
    sp.add_argument("--n", type=int, default=25)
    sp.add_argument("--seed", type=int, default=3210)
    sp.add_argument("--out", type=Path)
    args = ap.parse_args()

    if args.cmd == "sample":
        key = json.loads(args.key.read_text(encoding="utf-8"))
        rows = sample_claims(key, args.n, args.seed)
        md = [
            f"# Spot check: {key['corpus']} @ {key['ref'][:12]} (seed {args.seed}, {len(rows)} claims)",
            "",
            "Check each claim against the source. Record any wrong one in the program's",
            "`verification.notes` and fix the key; once every claim holds, set the checked",
            "programs' `verification.tier` to `human_signed` with `signed_by` and the date.",
            "",
            "| ok | program | kind | claim |",
            "|---|---|---|---|",
            *[f"| [ ] | `{r['program']}` | {r['kind']} | {r['claim']} |" for r in rows],
        ]
        text = "\n".join(md) + "\n"
        if args.out:
            args.out.write_text(text, encoding="utf-8")
        print(text)
        return 0

    repo = args.repo.resolve()
    if args.cmd == "draft":
        key, report = draft(repo, args.corpus, args.url, args.ref)
        args.out.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        if args.report:
            args.report.write_text(report + "\n", encoding="utf-8")
        print(f"drafted {len(key['programs'])} programs -> {args.out}")
        return 0

    key = json.loads(args.key.read_text(encoding="utf-8"))
    if args.cmd == "add-pli":
        # Refresh drafts, but never clobber a file someone already signed off.
        existing = key.get("pli_programs", {})
        for rel, entry in draft_pli(repo).items():
            if not existing.get(rel, {}).get("records_validated"):
                existing[rel] = entry
        key["pli_programs"] = existing
        args.key.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        print(f"drafted {len(existing)} PL/I files -> {args.key}")
        return 0
    if args.cmd == "add-sql-tables":
        # #3344: same rule as add-pli -- refresh drafts, never clobber a sign-off.
        existing_sql = key.get("sql_tables", {})
        for rel, entry in draft_sql_tables(repo).items():
            if not existing_sql.get(rel, {}).get("sql_tables_validated"):
                existing_sql[rel] = entry
        key["sql_tables"] = existing_sql
        args.key.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        print(f"drafted {len(existing_sql)} DECLARE TABLE files -> {args.key}")
        return 0
    if args.cmd == "add-bms":
        # Refresh drafts, but never clobber a map someone already signed off.
        existing = key.get("bms_maps", {})
        for rel, entry in draft_bms(repo).items():
            if not existing.get(rel, {}).get("fields_validated"):
                existing[rel] = entry
        key["bms_maps"] = existing
        args.key.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        print(f"drafted {len(existing)} BMS maps -> {args.key}")
        return 0
    if args.cmd == "add-jcl":
        # #3345: the add-pli discipline -- refresh drafts, keep signed-off members.
        jobs = key.get("jcl_jobs", {})
        for rel, entry in draft_jcl(repo).items():
            if not jobs.get(rel, {}).get("dsns_validated"):
                jobs[rel] = entry
        key["jcl_jobs"] = jobs
        args.key.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        print(f"drafted {len(jobs)} JCL members -> {args.key}")
        return 0
    if args.cmd == "add-csd":
        # #3356: the add-pli discipline -- refresh drafts, keep signed-off decks.
        decks = key.get("csd_decks", {})
        for rel, entry in draft_csd(repo).items():
            if not decks.get(rel, {}).get("resources_validated"):
                decks[rel] = entry
        key["csd_decks"] = decks
        args.key.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        print(f"drafted {len(decks)} CSD decks -> {args.key}")
        return 0
    if args.cmd == "add-commarea":
        # #3355: the add-pli discipline, per keyed program -- refresh the drafted
        # `commareas` field only, never a program signed off with `commareas_validated`.
        programs = key.get("programs", {})
        drafted = 0
        for rel, entry in programs.items():
            path = repo / rel
            if entry.get("commareas_validated") or not path.is_file():
                continue
            entry["commareas"] = cics_commareas(Source(path))
            entry.setdefault("commareas_validated", False)
            drafted += len(entry["commareas"])
        args.key.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        print(f"drafted {drafted} COMMAREA operands over {len(programs)} programs -> {args.key}")
        return 0
    if args.cmd == "add-cics":
        # #3351-#3354: the add-pli discipline -- refresh drafts, keep signed-off files.
        ops = key.get("cics_resources", {})
        for rel, entry in draft_cics(repo).items():
            if not ops.get(rel, {}).get("cics_validated"):
                ops[rel] = entry
        key["cics_resources"] = ops
        args.key.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        print(f"drafted {len(ops)} CICS files -> {args.key}")
        return 0
    result, md = score(repo, key, args.db)
    if args.md:
        args.md.write_text(md, encoding="utf-8")
    if args.json:
        args.json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
