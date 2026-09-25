#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: Deprecated Trails Analyzer
#
# PURPOSE:
# Static Analysis of COBOL structural signatures to isolate unused memory
# declarations and mathematically unreachable execution logic.
#
# ARCHITECTURAL DECISION:
# Legacy COBOL architectures frequently suffer from "code rot" where memory
# addresses (Data Division) and execution blocks (Procedure Division) are
# abandoned but never removed by cautious developers. This analyzer prevents
# migrating this dead weight to the cloud by statically mapping actual execution
# usage against declarations, shedding unnecessary state flux and cognitive load.
# ==============================================================================
import argparse
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional

# Copybook members are found by stem. .cbl/.cob are allowed because some shops keep
# copybooks under program extensions, but a member with a PROGRAM-ID is a program
# and is never inlined (#3203: `COPY ACCTCTRL` used to inline ACCTCTRL.cbl).
# `.dcl`: a DCLGEN member, which `EXEC SQL INCLUDE` pulls in like a copybook (#3414).
_COPYBOOK_EXTS = (".cpy", ".copy", ".dcl", ".cbl", ".cob")
_PROGRAM_ID = re.compile(r"\bPROGRAM-ID\b", re.IGNORECASE)

# Fixed-format sequence area (cols 1-6, blanks or a sequence field) + indicator (col 7).
_SEQ_AREA = r"(?:[^\n]{6} )?"

# Scope terminators and verbs that can stand alone on a line ending in a period.
# None of these can name a paragraph (#3203 defect 1).
_NOT_A_PARAGRAPH = re.compile(r"END-[A-Z0-9\-]+|GOBACK|EXIT|CONTINUE|STOP|DECLARATIVES")

# Matches a copy statement, with or without a sequence field in cols 1-6
# (`R2     COPY SAM2PARM.`):
#   COPY NAME.  /  COPY 'NAME'.  /  COPY NAME IN|OF LIB.  /  COPY NAME REPLACING ... .
#   EXEC SQL INCLUDE NAME END-EXEC   (one line, or split over lines)
# Named groups: `name` (COPY) or `inc` (SQL INCLUDE), `lib`, `rep`.
# #3414: the period may follow on a later line (CardDemo `COPY CSUTLDPY` /
# `    .`, `COPY 'CSSTRPFY'` / `    .`), REPLACING may span lines (CSSETATY),
# and `IN LIB` / `EXEC SQL INCLUDE` were not matched at all (zopeneditor
# SAM1LIB, CBSA's DB2 members, CardDemo's .dcl DCLGEN members). A split
# `EXEC SQL` / `INCLUDE X`, or a period on the next line (`206500     .`), may
# carry a sequence field there.
COPY_PATTERN = re.compile(
    "^"
    + _SEQ_AREA
    + r"[ \t]*(?:"
    + r"COPY\s+[\'\"]?(?P<name>[A-Z0-9_\-]+)[\'\"]?(?:\s+(?:IN|OF)\s+(?P<lib>[A-Z0-9_\-]+))?"
    + r"(?:\s+REPLACING\s+(?P<rep>[^.]+?))?\s*(?:[0-9]{6}[ \t]*)?\."
    + r"|EXEC\s+SQL\s+(?:\S{6}\s+)?INCLUDE\s+(?P<inc>[A-Z0-9_\-]+)(?:\s+(?:\S{6}\s+)?END-EXEC)?\.?"
    + r")",
    re.MULTILINE | re.IGNORECASE,
)


def copy_member(match: re.Match) -> str:
    """The member a COPY_PATTERN match names (COPY or SQL INCLUDE), upper-cased."""
    return (match.group("name") or match.group("inc")).upper()


_NAME = r"[A-Z0-9][A-Z0-9\-]*"

# A fixed-format unit header: `NAME.` or `NAME SECTION [nn].` starting in Area A
# (cols 8-11), alone on its line.
# Built from fragments: cols 1-7, then the name starting in cols 8-11.
_AREA_A_START = r"^[^\n]{6} {1,4}"
_SECTION_SUFFIX = r"(\s+SECTION(?:\s+[0-9]{1,2})?)?"
_UNIT_HEADER = re.compile(_AREA_A_START + f"({_NAME})" + _SECTION_SUFFIX + r"\s*\.[ \t]*$")

# Control flow read by the reachability pass (#3203 defect 5).
# #3420: `(?<![A-Z0-9-])`, not `\b`, before every verb. COBOL words run through
# hyphens and `\b` fires at each one, so `END-PERFORM` followed by `PERFORM X`
# read as a PERFORM of the word PERFORM (swallowing X, which then read dead --
# CardDemo COTRTLIC 9450-CLOSE-FORWARD-CURSOR), and `END-IF` counted as an IF.
_V = r"(?<![A-Z0-9\-])"
_PERFORM = re.compile(rf"{_V}PERFORM\s+({_NAME})(?:\s+(?:THRU|THROUGH)\s+({_NAME}))?")
_GO_TO = re.compile(rf"{_V}GO\s+(?:TO\s+)?({_NAME}(?:\s+{_NAME})*)")
# `ALTER P TO PROCEED TO Q` rewires P's GO TO: Q is reached as a GO TO target
# (CardDemo CBSTM03A's 8200/8300/8400-*-OPEN are reached only this way).
_ALTER = re.compile(rf"{_V}ALTER\s+({_NAME})\s+TO\s+(?:PROCEED\s+TO\s+)?({_NAME})")
_SENTENCE_END = re.compile(r"\.(?=\s|$)")
_TERMINAL_TAIL = re.compile(rf"(?:{_V}GOBACK|{_V}STOP\s+RUN|{_V}EXIT\s+PROGRAM|{_V}GO\s+(?:TO\s+)?{_NAME})$")
_TAIL_PERFORM = re.compile(rf"{_V}PERFORM ({_NAME})(?: (?:THRU|THROUGH) ({_NAME}))?$")
# A header whose separator period sits on the next line (#3419 shape, CardDemo
# COTRTLIC `2000-SEND-MAP` / `     .`): the name alone, no period.
_UNIT_HEADER_OPEN = re.compile(_AREA_A_START + f"({_NAME})" + _SECTION_SUFFIX + r"[ \t]*$")
# #3533: a header with its first statement on the same line -- navikt/DSF
# FO04D1X1 `006550 B.  DISPLAY PARAM, ' PARAM ER GALT'.` (legal COBOL: the
# paragraph's sentences may start right after its period). Group 3 is that code.
_UNIT_HEADER_INLINE = re.compile(_AREA_A_START + f"({_NAME})" + _SECTION_SUFFIX + r"\.[ \t]+(\S.*)$")
_CICS_TERMINAL = re.compile(r"EXEC\s+CICS\s+(?:RETURN|XCTL|ABEND)\b")
# CICS transfers control to these labels itself (an abend, a condition, an
# attention key), so a unit named in one is reached with no PERFORM or GO TO.
_CICS_HANDLE = re.compile(r"\bEXEC\s+CICS\s+HANDLE\s+(?:ABEND|CONDITION|AID)\b(.{0,600}?)\bEND-EXEC", re.S)
_CICS_LABEL = re.compile(rf"\(\s*({_NAME})\s*\)")
# One `REPLACING ==A== BY ==B==` pair. #3222: the leading `(?<!...)` only lets a
# pair start at a token boundary. Without it every position inside a long name
# is a candidate start, each one consuming the rest of the name before failing
# on the required `BY` -- quadratic in the clause length. It changes no pair:
# the name run is greedy and cannot stop inside a token, so a match that starts
# mid-token always captures the same names as the boundary start does.
_REPLACING_PAIR = re.compile(
    r"(?<![A-Z0-9_\-])(?:==)?([A-Z0-9_\-]+)(?:==)?\s+BY\s+(?:==)?([A-Z0-9_\-]+)(?:==)?",
    re.IGNORECASE,
)


def _trim_fixed_format(line: str) -> str:
    """Trim fixed-format right-margin sequence numbers (cols 73-80) before matching.

    COBOL fixed-format source uses columns 73-80 for sequence numbers, which are not
    part of the executable code or paragraph/COPY headers. The parser already treats
    cols 8-72 as the meaningful code region; this helper keeps that model consistent.
    """
    if len(line) > 72:
        return line[:72]
    return line


@lru_cache(maxsize=8)
def _copybook_index(root: Path) -> dict[str, list[Path]]:
    """Maps an upper-cased member stem to every copybook candidate under `root`.

    Cached: the refractor resolves every program of a repository against the same root.
    """
    index: dict[str, list[Path]] = {}
    for path in root.rglob("*"):
        if path.suffix.lower() in _COPYBOOK_EXTS and path.is_file():
            index.setdefault(path.stem.upper(), []).append(path)
    return index


def _nearest(candidates: list[Path], origin: Path) -> list[Path]:
    """Orders candidates by how many leading path parts they share with `origin`, then by path."""

    def shared(p: Path) -> int:
        n = 0
        for a, b in zip(p.parent.parts, origin.parent.parts):
            if a != b:
                break
            n += 1
        return n

    return sorted(candidates, key=lambda p: (-shared(p), p.suffix.lower() != ".cpy", str(p)))


def find_copybook(name: str, copybook_root: Path, origin: Path) -> Optional[Path]:
    """The member `COPY name` resolves to: searched under `copybook_root` (the
    repository, not just the program's directory: real layouts keep copybooks in
    COPYBOOK/ or cobol_copy/), nearest to `origin` first, never a program (#3203)."""
    for candidate in _nearest(_copybook_index(copybook_root).get(name.upper(), []), origin):
        if not _PROGRAM_ID.search(candidate.read_text(encoding="utf-8", errors="ignore")):
            return candidate
    return None


def _blank_literals(text: str) -> str:
    """Blanks the inside of '...' and "..." literals, preserving offsets. Quote state
    resets at each newline: a fixed-format literal only continues via column 7."""
    out, quote = [], None
    for ch in text:
        if ch == "\n":
            quote = None
        elif quote:
            if ch == quote:
                quote = None
            else:
                ch = " "
        elif ch in ("'", '"'):
            quote = ch
        out.append(ch)
    return "".join(out)


def _code_area(line: str) -> Optional[str]:
    """Area A..B (cols 8-72) of a fixed-format line with literals blanked and any
    inline `*>` comment cut, or None for a comment / debug line (column 7)."""
    if len(line) > 6 and line[6] in "*/D":
        return None
    area = _blank_literals(_trim_fixed_format(line)[7:72])
    return area.split("*>", 1)[0]


def unit_header(line: str) -> Optional[str]:
    """The paragraph or section name a line declares, or None.

    A header is `NAME.` / `NAME SECTION.` starting in Area A (cols 8-11), alone on
    its line. A lone `NAME.` deeper in Area B is the last line of a multi-line
    statement or a scope terminator (`END-IF.`, `GOBACK.`), not a unit (#3203
    defect 1). Cols 1-6 may carry a sequence field (defect 4), and cols 73-80 are
    ignored as a right-margin sequence number field (#3244).
    """
    line = _trim_fixed_format(line)
    m = _UNIT_HEADER.match(line)
    if m is None or _NOT_A_PARAGRAPH.fullmatch(m.group(1)):
        return None
    return m.group(1)


def procedure_units(proc_div: str) -> list[dict]:
    """The paragraphs and sections of an upper-cased PROCEDURE DIVISION, in source order.

    `proc_div` is the text after `PROCEDURE DIVISION`. The rest of that header
    sentence (` USING DFHCOMMAREA.`, possibly over several lines) is skipped, or its
    operand would read as the entry. Each unit is {name, kind, text}; statements
    before the first header form an unnamed `implicit` unit, the program's entry.
    """
    lines = proc_div.split("\n")
    i = 0
    if not _SENTENCE_END.search(_blank_literals(_trim_fixed_format(lines[0]))):
        i = 1
        while i < len(lines) and not _SENTENCE_END.search(_code_area(_trim_fixed_format(lines[i])) or ""):
            i += 1
    units: list[dict] = [{"name": None, "kind": "implicit", "body": []}]
    body = [_trim_fixed_format(line) for line in lines[i + 1 :]]
    skip_period_line = False
    for j, line in enumerate(body):
        code = _code_area(line)
        if code is None:
            continue
        if skip_period_line:
            if not code.strip():
                continue
            skip_period_line = False
            if code.strip() == ".":
                continue
        name = unit_header(line)
        header = _UNIT_HEADER.match(line)
        if name is None:
            # #3420: a header whose period is on the next code line.
            open_header = _UNIT_HEADER_OPEN.match(line)
            nxt = next((c for c in (_code_area(x) for x in body[j + 1 :]) if c is not None and c.strip()), "")
            if open_header and nxt.strip().startswith(".") and not _NOT_A_PARAGRAPH.fullmatch(open_header.group(1)):
                name, header, skip_period_line = open_header.group(1), open_header, nxt.strip() == "."
        inline = None
        if name is None:
            inline = _UNIT_HEADER_INLINE.match(line)
            if inline and not _NOT_A_PARAGRAPH.fullmatch(inline.group(1)):
                name, header = inline.group(1), inline
            else:
                inline = None
        if name is not None:
            kind = "section" if header and header.group(2) else "paragraph"
            units.append({"name": name, "kind": kind, "body": []})
            if inline:  # the header line's own statement opens the unit's body
                units[-1]["body"].append(inline.group(3))
        else:
            units[-1]["body"].append(code)
    if not "".join(units[0]["body"]).strip():
        units.pop(0)
    for u in units:
        u["text"] = "\n".join(u.pop("body"))
    return units


def split_procedure_division(content: str) -> Optional[tuple[str, str]]:
    """(text before, text after) the PROCEDURE DIVISION header, or None. #3533: any
    run of blanks may separate the two words (navikt/DSF PLUKKFR writes
    `PROCEDURE        DIVISION.`)."""
    m = re.search(r"PROCEDURE[ \t]+DIVISION", content)
    return (content[: m.start()], content[m.end() :]) if m else None


def unit_headers(proc_div: str) -> list[str]:
    """Names of the paragraphs and sections of an upper-cased PROCEDURE DIVISION."""
    return [u["name"] for u in procedure_units(proc_div) if u["name"]]


_CONDITIONAL_PHRASE = re.compile(
    r"(?<![A-Z0-9-])(?:(?:NOT\s+)?(?:AT\s+)?(?:END|END-OF-PAGE|EOP)|(?:NOT\s+)?INVALID\s+KEY"
    r"|(?:NOT\s+)?(?:ON\s+)?(?:SIZE\s+ERROR|OVERFLOW|EXCEPTION))(?![A-Z0-9-])"
)
_PHRASE_SCOPE_END = re.compile(
    r"\bEND-(?:READ|RETURN|WRITE|REWRITE|DELETE|START|ADD|SUBTRACT|MULTIPLY|DIVIDE|COMPUTE|CALL|STRING"
    r"|UNSTRING|SEARCH|ACCEPT|DISPLAY)\b"
)


def _unconditional_sentences(text: str) -> list[str]:
    """The unit's sentences, whitespace-collapsed, that sit outside any IF /
    EVALUATE -- what each ends in always runs. `END-IF` / `END-EVALUATE` are not
    openers (#3420: `\bIF\b` matched inside `END-IF`, so any sentence with a
    closed IF read as unterminated)."""
    out = []
    for raw in _SENTENCE_END.split(text):
        s = re.sub(r"\s+", " ", raw.strip())
        if not s:
            continue
        balanced = all(
            len(re.findall(opener, s)) == len(re.findall(closer, s))
            for opener, closer in ((rf"{_V}IF\b", r"\bEND-IF\b"), (rf"{_V}EVALUATE\b", r"\bEND-EVALUATE\b"))
        )
        # #3533: an I/O or arithmetic statement's conditional phrase is an IF too --
        # `READ INN-FR AT END GO TO SLUTT.` (navikt/DSF PLUKKFR) transfers only at end
        # of file -- unless its own END- scope terminator closes it first.
        phrases = list(_CONDITIONAL_PHRASE.finditer(s))
        if balanced and (not phrases or _PHRASE_SCOPE_END.search(s, phrases[-1].end())):
            out.append(s)
    return out


def _last_sentence(text: str) -> Optional[str]:
    """The unit's last sentence if it is unconditional, else None."""
    sentences = [x for x in _SENTENCE_END.split(text) if x.strip()]
    if not sentences:
        return None
    last = _unconditional_sentences(sentences[-1])
    return last[0] if last else None


def _evaluate_is_terminal(sentence: str) -> bool:
    """One EVALUATE with WHEN OTHER whose every branch ends in an unconditional
    transfer never falls through (#3510: CICS GENAPP LGTESTP4 NO-ADD, `WHEN 70 ...
    GO TO ERROR-OUT  WHEN OTHER ... GO TO ERROR-OUT`, so NO-UPD after it is dead).
    A branch holding a nested IF / EVALUATE is not claimed."""
    m = re.fullmatch(rf"{_V}EVALUATE\s(.*)\sEND-EVALUATE", sentence)
    if not m or re.search(rf"{_V}(?:EVALUATE|IF)\b", m.group(1)):
        return False
    branches = re.split(rf"{_V}WHEN\s", m.group(1))[1:]
    if not any(b.startswith("OTHER") for b in branches):
        return False
    return all(_TERMINAL_TAIL.search(b.strip()) and " DEPENDING " not in b for b in branches)


def _sentence_is_terminal(sentence: str) -> bool:
    if _evaluate_is_terminal(sentence):
        return True
    if sentence.endswith("END-EXEC"):
        starts = [m.start() for m in re.finditer(r"\bEXEC\s", sentence)]
        return bool(starts) and _CICS_TERMINAL.match(sentence[starts[-1] :]) is not None
    return _TERMINAL_TAIL.search(sentence) is not None and " DEPENDING " not in sentence


def _is_terminal(text: str) -> bool:
    """Does ANY unconditional sentence of the unit end in a transfer that never
    falls through? Not only the last (#3420): CBSA's BNK1* A010 has
    `EXEC CICS RETURN TRANSID(...) END-EXEC.` then an `IF <resp> ... END-IF.`
    recovery sentence, and the RETURN alone ends the unit."""
    return any(_sentence_is_terminal(s) for s in _unconditional_sentences(text))


def reachable_units(units: list[dict]) -> set[str]:
    """Names of the units reachable from the entry (#3203 defect 5).

    Control is followed as ranges (start, end): the main flow starts at the first
    unit and falls through until a terminal statement; PERFORM P runs (P, P),
    PERFORM S of a section runs (S, S's last paragraph), PERFORM A THRU B runs
    (A, B). A GO TO continues within the enclosing range when its target lies
    inside it. A unit whose last sentence is an unconditional PERFORM of a range
    that never returns is itself terminal. CICS HANDLE labels are entry points.
    """
    index = {u["name"]: i for i, u in enumerate(units) if u["name"]}
    section_end: dict[int, int] = {}
    for i, u in enumerate(units):
        if u["kind"] == "section":
            j = i
            while j + 1 < len(units) and units[j + 1]["kind"] != "section":
                j += 1
            section_end[i] = j

    def span(first: str, thru: Optional[str]) -> tuple[int, int]:
        a = index[first]
        last = index.get(thru, a) if thru else a
        return a, section_end.get(last, last)

    terminal = [_is_terminal(u["text"]) for u in units]
    # Every unconditional sentence that is exactly a PERFORM: any one of a range
    # that never returns makes the unit terminal, wherever it sits (#3420).
    tails: list[list[tuple[str, Optional[str]]]] = []
    for u in units:
        found: list[tuple[str, Optional[str]]] = []
        for s in _unconditional_sentences(u["text"]):
            m = _TAIL_PERFORM.search(s)
            if m and m.group(1) in index:
                found.append((m.group(1), m.group(2)))
        tails.append(found)
    changed = True
    while changed:  # fixpoint: "never returns" is defined through `terminal`
        changed = False
        for i, unit_tails in enumerate(tails):
            for tail in unit_tails:
                if not terminal[i]:
                    a, b = span(*tail)
                    if any(terminal[a : b + 1]):
                        terminal[i] = changed = True

    queue: list[tuple[int, Optional[int]]] = [(0, None)] if units else []
    for u in units:
        for m in _CICS_HANDLE.finditer(u["text"]):
            queue.extend((index[t], None) for t in _CICS_LABEL.findall(m.group(1)) if t in index)
    reached: set[int] = set()
    seen: set[tuple[int, Optional[int]]] = set()
    while queue:
        start, end = queue.pop()
        if (start, end) in seen:
            continue
        seen.add((start, end))
        k = start
        while k < len(units):
            reached.add(k)
            text = units[k]["text"]
            queue.extend(span(m.group(1), m.group(2)) for m in _PERFORM.finditer(text) if m.group(1) in index)
            for m in _GO_TO.finditer(text):
                for target in m.group(1).split():
                    if target not in index:
                        break
                    t = index[target]
                    queue.append((t, end if end is not None and start <= t <= end else None))
            queue.extend((index[m.group(2)], None) for m in _ALTER.finditer(text) if m.group(2) in index)
            if (end is not None and k >= end) or terminal[k]:
                break
            k += 1
    return {units[i]["name"] for i in reached if units[i]["name"]}


def resolve_copybooks(
    content: str,
    source_path: Path,
    copybook_root: Optional[Path] = None,
    origin: Optional[Path] = None,
) -> str:
    """
    Recursively hunts for COBOL 'COPY' statements and injects the contents of the
    target .cpy file directly into the memory string to ensure accurate structural scanning.
    """
    # ==========================================================================
    # DEFENSIVE DESIGN (INLINE COPYBOOK EXPANSION):
    # A COBOL program's data declarations are often hidden inside external copybooks.
    # Scanning the source file alone would result in massive false-positives for
    # undeclared variables. We recursively expand and inline copybooks directly
    # into the memory buffer before analysis to ensure mathematically accurate
    # dependency tracking.
    # ==========================================================================

    root = copybook_root if copybook_root is not None else source_path.parent
    origin = origin if origin is not None else source_path

    def replacer(match):
        copy_name = copy_member(match)
        replacing_clause = match.group("rep")
        cpy_file = find_copybook(copy_name, root, origin)
        if cpy_file is not None:
            cpy_content = cpy_file.read_text(encoding="utf-8", errors="ignore").upper()
            # ==============================================================
            # DEFENSIVE DESIGN (DYNAMIC ALIASING):
            # COBOL's 'REPLACING' clause allows dynamic text substitution at
            # compile time. We must simulate this substitution in our in-memory
            # buffer to prevent missing usage references for aliased variables.
            # ==============================================================
            if replacing_clause:
                # Extracts pairs, ignoring the optional == delimiters
                pairs = _REPLACING_PAIR.findall(replacing_clause)
                for old_val, new_val in pairs:
                    # Use negative lookarounds so we don't accidentally replace partial words with hyphens
                    cpy_content = re.sub(
                        r"(?<![A-Z0-9_\-])" + re.escape(old_val) + r"(?![A-Z0-9_\-])",
                        new_val,
                        cpy_content,
                    )

            return f"*> --- START COPY {copy_name} ---\n{cpy_content}\n*> --- END COPY {copy_name} ---"

        # If the copybook is missing from the repo, leave the statement intact to avoid crashing
        return match.group(0)

    # Right-margin sequence numbers (cols 73-80) are not part of the effective COBOL
    # source, so trim them before matching COPY headers. This fixes #3244.
    safe_content = "\n".join(_trim_fixed_format(line.rstrip("\n")) for line in content.splitlines())
    # Run the substitution up to 3 times to handle nested copybooks (COPY within a COPY)
    for _ in range(3):
        safe_content = COPY_PATTERN.sub(replacer, safe_content)

    return safe_content


def x_ray_dead_code(
    filepath: Path,
    copybook_root: Optional[Path] = None,
    origin: Optional[Path] = None,
) -> Optional[dict]:
    """Parses a fully-expanded COBOL file to find mathematically unreachable logic and memory.

    `copybook_root` is where COPY members are searched (default: the file's own
    directory); `origin` is the program's path in the repository when `filepath`
    is a patched copy elsewhere, used to pick the nearest of several same-named copybooks.
    """
    try:
        raw_content = filepath.read_text(encoding="utf-8", errors="ignore").upper()
    except Exception:
        return None

    # Resolve all external memory layouts into the local string before structural validation
    content = resolve_copybooks(raw_content, filepath, copybook_root, origin)

    # COBOL is strictly divided. We need to split the data from the execution.
    split = split_procedure_division(content)
    if split is None:
        return None
    data_div, proc_div = split

    # ==========================================
    # 1. ISOLATING UNUSED MEMORY ADDRESSES
    # ==========================================
    # Look for COBOL variable declarations (Levels 01-49, 77, 88)
    # Bypassing Area A sequence numbers by allowing up to 11 leading spaces/chars.
    var_pattern = re.compile(
        r"^[ \tA-Z0-9]{0,11}(?:0[1-9]|[1-4][0-9]|77|88)[ \t]+([A-Z0-9\-]+)",
        re.MULTILINE,
    )
    declared_vars = set(var_pattern.findall(data_div))

    # Strip out common noise like FILLER
    if "FILLER" in declared_vars:
        declared_vars.remove("FILLER")

    used_vars = set()
    for var in declared_vars:
        # A variable is "used" if it appears as a whole word anywhere in the Procedure Division
        # We use a fast regex boundary \b to prevent partial matches (e.g. tracking "ID" shouldn't flag "USER-ID")
        if re.search(r"\b" + re.escape(var) + r"\b", proc_div):
            used_vars.add(var)

    orphaned_vars = declared_vars - used_vars

    # ==========================================
    # 2. ISOLATING UNREACHABLE LOGIC BLOCKS
    # ==========================================
    # A unit (paragraph or section) is dead when no path from the entry reaches it:
    # PERFORM, PERFORM ... THRU, GO TO, fall-through within and across sections,
    # and CICS HANDLE labels are all followed (#3203 defect 5).
    units = procedure_units(proc_div)
    declared_units = {u["name"] for u in units if u["name"]}
    dead_paragraphs = declared_units - reachable_units(units)

    # Calculate a rough estimate of Lines of Code (LOC) saved
    # (Assuming average 10 lines per paragraph and 1 line per variable)
    loc_saved = (len(dead_paragraphs) * 10) + len(orphaned_vars)

    return {
        "program_id": filepath.name,
        "total_vars": len(declared_vars),
        "orphaned_vars": orphaned_vars,
        "total_paras": len(declared_units),
        "dead_paras": dead_paragraphs,
        "loc_saved": loc_saved,
    }


def main():
    from gitgalaxy.licensing import enforce_licensing_guard

    enforce_licensing_guard("Deprecated Trails Analyzer")

    parser = argparse.ArgumentParser(description="GitGalaxy Deprecated Trails Analyzer")
    parser.add_argument("target", help="Directory containing legacy COBOL payloads")
    args = parser.parse_args()

    target_path = Path(args.target).resolve()
    if not target_path.exists():
        print(f"Error: Target {target_path} does not exist.")
        sys.exit(1)

    print(f"🔍 GitGalaxy Deprecated Trails Analyzer scanning {target_path.name} for obsolete logic...\n")

    cobol_files = list(target_path.rglob("*.cbl")) + list(target_path.rglob("*.cob"))

    totals = {
        "loc_saved": 0,
        "orphaned_vars": 0,
        "dead_paras": 0,
        "files_with_dead_code": 0,
    }

    for file_path in cobol_files:
        metrics = x_ray_dead_code(file_path, copybook_root=target_path)
        if metrics and (metrics["orphaned_vars"] or metrics["dead_paras"]):
            totals["files_with_dead_code"] += 1
            totals["loc_saved"] += metrics["loc_saved"]
            totals["orphaned_vars"] += len(metrics["orphaned_vars"])
            totals["dead_paras"] += len(metrics["dead_paras"])

            print(f" 🎯 TARGET: {metrics['program_id']}")
            if metrics["orphaned_vars"]:
                print(
                    f"    ↳ Unused Memory Addresses ({len(metrics['orphaned_vars'])}): {', '.join(list(metrics['orphaned_vars'])[:5])}"
                    + ("..." if len(metrics["orphaned_vars"]) > 5 else "")
                )
            if metrics["dead_paras"]:
                print(
                    f"    ↳ Unreachable Logic Blocks ({len(metrics['dead_paras'])}): {', '.join(list(metrics['dead_paras'])[:5])}"
                    + ("..." if len(metrics["dead_paras"]) > 5 else "")
                )
            print("-" * 60)

    # Presentation
    print("\n==========================================================")
    print(" 📉 DEPRECATED TRAILS REDUCTION REPORT")
    print("==========================================================")
    print(f" Files Flagged for Cleanup : {totals['files_with_dead_code']}")
    print(f" Unused Memory Addresses   : {totals['orphaned_vars']} variables")
    print(f" Unreachable Logic Blocks  : {totals['dead_paras']} paragraphs")
    print(f" ✂️ Estimated Bloat Removed : ~{totals['loc_saved']} Lines of Code")
    print("==========================================================\n")


if __name__ == "__main__":
    main()
