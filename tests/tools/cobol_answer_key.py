"""
#3210: the COBOL modernization answer key -- hand-verified, per-program truth for
real mainframe corpora -- and the scorer that measures the refraction ("forge")
tools and the engine's master DB against it.

    python tests/tools/cobol_answer_key.py draft <repo> --corpus NAME --url URL --ref SHA \
        --out key.json [--report why.md]
    python tests/tools/cobol_answer_key.py score <repo> --key key.json [--db master.db] [--md out.md]
    python tests/tools/cobol_answer_key.py add-pli <repo> --key key.json
    python tests/tools/cobol_answer_key.py add-pli-calls <repo> --key key.json
    python tests/tools/cobol_answer_key.py add-sql-tables <repo> --key key.json
    python tests/tools/cobol_answer_key.py add-sql-access <repo> --key key.json
    python tests/tools/cobol_answer_key.py add-bms <repo> --key key.json
    python tests/tools/cobol_answer_key.py add-jcl <repo> --key key.json
    python tests/tools/cobol_answer_key.py add-csd <repo> --key key.json
    python tests/tools/cobol_answer_key.py add-commarea <repo> --key key.json
    python tests/tools/cobol_answer_key.py add-cics <repo> --key key.json
    python tests/tools/cobol_answer_key.py add-cics-tasks <repo> --key key.json
    python tests/tools/cobol_answer_key.py add-job-submissions <repo> --key key.json
    python tests/tools/cobol_answer_key.py add-mq <repo> --key key.json
    python tests/tools/cobol_answer_key.py add-uow <repo> --key key.json
    python tests/tools/cobol_answer_key.py add-file-defs <repo> --key key.json
    python tests/tools/cobol_answer_key.py add-job-flow <repo> --key key.json
    python tests/tools/cobol_answer_key.py add-call-using <repo> --key key.json
    python tests/tools/cobol_answer_key.py add-dli <repo> --key key.json
    python tests/tools/cobol_answer_key.py add-ims-gen <repo> --key key.json
    python tests/tools/cobol_answer_key.py add-data-moves <repo> --key key.json
    python tests/tools/cobol_answer_key.py add-symbolic-maps <repo> --key key.json
    python tests/tools/cobol_answer_key.py add-dynamic-targets <repo> --key key.json
    python tests/tools/cobol_answer_key.py add-web-services <repo> --key key.json
    python tests/tools/cobol_answer_key.py add-jcics <repo> --key key.json
    python tests/tools/cobol_answer_key.py add-io-moves <repo> --key key.json
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

`add-cics-tasks` (#3449) drafts every COBOL source's CICS task-control commands
(RUN/START/FETCH/RETRIEVE/DELAY/ENQ ...) and the CSD transactions each RUN/START
reaches into `cics_tasks`, the add-pli way.

`add-job-submissions` (#3448) drafts, per submitting file, the jobs it submits to
the internal reader (CICS WRITEQ TD to an extrapartition queue, or a JCL
SYSOUT=(x,INTRDR) step) into `job_submissions`, the add-pli way.

`add-mq` (#3447) drafts every COBOL source's IBM MQ calls (verb, direction, the
queue or why it is unnamed, the MQOPEN a handle came from) into `mq_calls`.

`add-uow` (#3453) drafts every COBOL source's commit / rollback points, error
handlers, explicit ABENDs and RESP checks into `uow_handlers`, and the TD queues
whose TRIGGERLEVEL starts a transaction into `tdq_triggers`.

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
import random
import re
import sys
from pathlib import Path
from typing import Any, Callable, Optional

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
TIERS = ("sample_verified", "llm_verified", "cross_verified", "human_signed")
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

    def __init__(self, path: Path, lines: Optional[list[tuple[int, str]]] = None):
        """`lines` is another reading's (line, text) pairs (#3495: HlasmSource);
        without it the file is read as fixed-format COBOL."""
        self.path = path
        if lines is None:
            lines = []
            for no, raw in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if len(raw) > 6 and raw[6] in "*/Dd":
                    continue
                area = raw[7:72] if len(raw) > 7 else ""
                area = area.split("*>", 1)[0]
                lines.append((no, area.upper()))
        self.lines: list[tuple[int, str]] = lines  # (1-based line, Area A..B text), comments dropped
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
# HLASM command-level CICS (#3495)
# ==============================================================================
# This tool's own reading of an assembler source, so the CICS readers below (which
# find `EXEC CICS ... END-EXEC` in a COBOL `Source`) read assembler the same way.
# Over the RAW file: `*` / `.*` column-1 comment lines are dropped; a statement is
# its physical lines, each cut at column 71, joined while column 72 is non-blank
# (a continuation line's text is taken whole -- it should start in column 16, and
# real source drifts a column); the LAST line of an `EXEC CICS` statement is closed
# with ` END-EXEC`. An operand names a constant through `NAME DC C'text'` /
# `CLn'text'` (the blank padding to the field is not part of the value). It
# shares the engine's CONTRACT (core/hlasm_cics.py), none of its code.
HLASM_EXTS = (".asm", ".hlasm", ".assemble")
HLASM_NAME = r"[A-Z@#$_][A-Z0-9@#$_]*"
_HLASM_CICS = re.compile(r"^\S*\s+EXEC\s+CICS\b")
_HLASM_DC = re.compile(rf"^({HLASM_NAME})\s+DC\s+C(?:L\d+)?'([^']*)'")


class HlasmSource(Source):
    """An assembler source as a `Source`: statements joined, each EXEC CICS closed."""

    def __init__(self, path: Path):
        physical = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        lines: list[tuple[int, str]] = []
        self.dc: dict[str, str] = {}
        i = 0
        while i < len(physical):
            if physical[i].startswith(("*", ".*")) or not physical[i].strip():
                i += 1
                continue
            group = [(i + 1, physical[i][:71].upper())]
            # Continued by a non-blank column 72; a single character standing alone in
            # column 73 (72 blank, nothing after) is the same mark one column off --
            # never a sequence field, which runs 73-80.
            while (
                physical[i][71:72].strip() or (physical[i][71:72] == " " and len(physical[i][72:].rstrip()) == 1)
            ) and i + 1 < len(physical):
                i += 1
                group.append((i + 1, physical[i][:71].upper()))
            i += 1
            if _HLASM_CICS.match(" ".join(t for _, t in group)):
                no, last = group[-1]
                group[-1] = (no, last.rstrip() + " END-EXEC")
            dc = _HLASM_DC.match(group[0][1])
            if dc and dc.group(2).strip():
                self.dc.setdefault(dc.group(1), dc.group(2).strip())
            lines.extend(group)
        super().__init__(path, lines)

    def _procedure_start(self) -> Optional[int]:
        return 0  # no divisions: every statement is procedure code

    def program_id(self) -> Optional[str]:
        return None


class PliSource(Source):
    """#3491: a PL/I source as a `Source` for the CICS readers. This tool's own
    reading: `/* */` comments blanked (newlines kept), columns 73-80 sequence fields
    dropped (`_pli_source_lines`), and ` END-EXEC` written before the `;` that ends
    each `EXEC CICS` (outside quotes), so no line moves. Operands name the
    `INIT('...')` of their DCL (a qualified reference: of its last field)."""

    def __init__(self, path: Path):
        raw = path.read_text(encoding="utf-8", errors="ignore")
        text = re.sub(r"/\*.*?(?:\*/|\Z)", lambda m: re.sub(r"[^\n]", " ", m.group(0)), raw, flags=re.S)
        text = _pli_source_lines(text).upper()
        out, pos = [], 0
        for m in re.finditer(r"(?<![\w@#$])EXEC\s+CICS(?![\w@#$])", text):
            if m.start() < pos:
                continue
            quoted, i = False, m.end()
            while i < len(text) and (quoted or text[i] != ";"):
                quoted ^= text[i] == "'"
                i += 1
            if i < len(text):
                out.append(text[pos:i] + " END-EXEC")
                pos = i
        out.append(text[pos:])
        self.inits = pli_char_inits(raw)
        super().__init__(path, list(enumerate("".join(out).split("\n"), 1)))

    def _procedure_start(self) -> Optional[int]:
        return 0  # no divisions: every statement is procedure code

    def program_id(self) -> Optional[str]:
        return None


def _key_source(path: Path) -> Source:
    """The reading a CICS reader takes of `path`: HLASM, PL/I or COBOL."""
    suffix = path.suffix.lower()
    if suffix in HLASM_EXTS:
        return HlasmSource(path)
    return PliSource(path) if suffix in PLI_EXTS else Source(path)


PLI_NAME = r"[\w@#$]+(?:\.[\w@#$]+)*"


def _operand_name(src: Source) -> str:
    """The identifier syntax an operand may be written in for `src`'s language."""
    if isinstance(src, PliSource):
        return PLI_NAME
    return HLASM_NAME if isinstance(src, HlasmSource) else NAME


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


_CONDITIONAL_PHRASE = re.compile(
    r"(?<![\w-])(?:(?:NOT\s+)?(?:AT\s+)?(?:END|END-OF-PAGE|EOP)|(?:NOT\s+)?INVALID\s+KEY"
    r"|(?:NOT\s+)?(?:ON\s+)?(?:SIZE\s+ERROR|OVERFLOW|EXCEPTION))(?![\w-])"
)
_PHRASE_SCOPE_END = re.compile(
    r"\bEND-(?:READ|RETURN|WRITE|REWRITE|DELETE|START|ADD|SUBTRACT|MULTIPLY|DIVIDE|COMPUTE|CALL|STRING"
    r"|UNSTRING|SEARCH|ACCEPT|DISPLAY)\b"
)


def _unconditional(sentence: str) -> bool:
    r"""Is the sentence outside any IF / EVALUATE (so what it ends in always runs)?

    `(?<![\w-])`: `\bIF\b` also matches inside `END-IF`, so any sentence with a
    closed IF read as unterminated and a paragraph ending `... END-IF ... GOBACK.`
    as falling through (CardDemo CBPAUP0C MAIN-PARA)."""
    if len(re.findall(r"(?<![\w-])IF\b", sentence)) != len(re.findall(r"\bEND-IF\b", sentence)):
        return False
    # #3491 (DSF pin): an I/O or arithmetic statement's conditional phrase is an IF
    # too -- `READ INN-FR AT END GO TO SLUTT.` transfers only at end of file -- unless
    # the statement's own END- scope terminator closes it before the transfer.
    phrase = None
    for phrase in _CONDITIONAL_PHRASE.finditer(sentence):
        pass
    if phrase is not None and not _PHRASE_SCOPE_END.search(sentence, phrase.end()):
        return False
    return len(re.findall(r"(?<![\w-])EVALUATE\b", sentence)) == len(re.findall(r"\bEND-EVALUATE\b", sentence))


def _evaluate_is_terminal(sentence: str) -> bool:
    """A sentence that is one EVALUATE with WHEN OTHER, every branch of which ends
    in an unconditional transfer, never falls through (CICS GENAPP LGTESTP4 NO-ADD:
    `WHEN 70 ... GO TO ERROR-OUT  WHEN OTHER ... GO TO ERROR-OUT`, found by the
    blind census). Nested EVALUATEs or IFs inside a branch are not claimed."""
    m = re.fullmatch(r"EVALUATE\s(.*)\sEND-EVALUATE", sentence)
    if not m or len(re.findall(r"(?<![\w-])(?:EVALUATE|IF)\b", m.group(1))) or "END-IF" in m.group(1):
        return False
    branches = re.split(r"(?<![\w-])WHEN\s", m.group(1))[1:]
    if not branches or not any(b.startswith("OTHER") for b in branches):
        return False
    return all(_TERMINAL_TAIL.search(b.strip()) and " DEPENDING " not in b for b in branches)


def _sentence_is_terminal(sentence: str) -> bool:
    if _evaluate_is_terminal(sentence):
        return True
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
# PL/I program call sites (#3491)
# ==============================================================================
# This tool's own reading of a PL/I source's calls OUT of the program, over the
# token stream above (comments dropped, columns 73-80 sequence fields removed),
# split into statements at `;`. A statement's leading `label:`s are skipped. Rows:
#   - `EXEC CICS LINK | XCTL`: PROGRAM(x) -- a literal, else a data name whose
#     DCL carries INIT('...') (form identifier, target the INIT text or None);
#   - `EXEC CICS RETURN | START | RUN` with TRANSID(x): verb "<VERB> TRANSID";
#   - `CALL name`: when `name` is no PROC / ENTRY label of this file (a call to an
#     internal procedure is not a program call). Across the repository, a name that
#     is only ever a NESTED procedure (never a file's outermost one) belongs to the
#     program that %INCLUDEs the calling member and is dropped too.
# The same contract as core/pli_calls.py + the invocation resolver, none of the code.
_PLI_UNIT_WORDS = {"PROC", "PROCEDURE", "ENTRY"}


def _pli_statements(tokens: list) -> list[list]:
    out, cur = [], []
    for t in tokens:
        if t[1] == ";":
            out.append(cur)
            cur = []
        else:
            cur.append(t)
    return out + ([cur] if cur else [])


def _pli_unlabelled(stmt: list) -> tuple[list[str], list]:
    """(the statement's leading labels, the rest)."""
    labels, i = [], 0
    while i + 1 < len(stmt) and stmt[i][0] == "word" and stmt[i + 1][1] == ":":
        labels.append(stmt[i][1])
        i += 2
    return labels, stmt[i:]


def pli_char_inits(text: str) -> dict[str, str]:
    """Name -> the character string a CHARACTER item's DCL INITs it to (first wins).
    Only a plain character string: `'0'B` is a bit string, `(78)' '` a repetition."""
    out: dict[str, str] = {}
    for item in pli_data_items(text):
        attrs = item.get("attributes") or ""
        m = re.search(r"\bINIT(?:IAL)?\s*\(\s*'([^']*)'\s*\)", attrs, re.I)
        if m and m.group(1).strip() and re.match(r"CHAR", attrs, re.I):
            out.setdefault(item["name"].upper(), m.group(1).strip())
    return out


def pli_procedures(text: str) -> list[str]:
    """Every PROC / ENTRY label in source order (the first is the outermost)."""
    out = []
    for stmt in _pli_statements(_pli_token_stream(_pli_source_lines(text))):
        labels, rest = _pli_unlabelled(stmt)
        if labels and rest and rest[0][1] in _PLI_UNIT_WORDS:
            out.append(labels[-1])
    return out


def _pli_clause_starts(stmt: list) -> list[int]:
    """Indexes in a statement where a (sub)statement can begin: its start, and after
    THEN / ELSE / OTHERWISE, a `)` (WHEN(...), ON-unit conditions), a label's `:`,
    or an ON-condition name (`ON ERROR CALL X;`, `ON ENDFILE(F) ...`)."""
    out = [0] if stmt else []
    for i in range(1, len(stmt)):
        prev = stmt[i - 1][1]
        if prev in ("THEN", "ELSE", "OTHERWISE", ")", ":", "SNAP", "SYSTEM") or (i >= 2 and stmt[i - 2][1] == "ON"):
            out.append(i)
    return out


def pli_call_rows(text: str) -> list[dict[str, Any]]:
    """The program call sites of one PL/I source (see the section header), before
    the repository-wide nested-procedure rule."""
    tokens = _pli_token_stream(_pli_source_lines(text))
    local = set(pli_procedures(text))
    inits = pli_char_inits(text)
    rows = []
    for stmt in _pli_statements(tokens):
        words = [t[1] if t[0] != "string" else None for t in stmt]
        for i in _pli_clause_starts(stmt):
            if words[i] == "EXEC" and words[i + 1 : i + 2] == ["CICS"] and i + 2 < len(stmt):
                verb = words[i + 2]
                if verb not in ("LINK", "XCTL", "RETURN", "START", "RUN"):
                    continue
                opt = "PROGRAM" if verb in ("LINK", "XCTL") else "TRANSID"
                at = next((j for j in range(i + 3, len(stmt) - 2) if words[j] == opt and words[j + 1] == "("), None)
                if at is None and opt == "TRANSID":
                    continue  # a plain RETURN routes nowhere
                form, operand, target = "unknown", None, None
                if at is not None:
                    kind, value, _ = stmt[at + 2]
                    if kind == "string":
                        form, operand = "literal", value.strip("'").strip()
                        target = operand
                    else:
                        # A qualified reference (`TRANS_OPPL_OMR.TRANSKODE`) is one
                        # operand; its INIT, if any, is the last field's.
                        j = at + 3
                        while j + 1 < len(stmt) and words[j] == "." and stmt[j + 1][0] == "word":
                            value += "." + words[j + 1]
                            j += 2
                        form, operand = "identifier", value
                        target = inits.get(value) or inits.get(value.rsplit(".", 1)[-1])
                rows.append({"verb": verb if opt == "PROGRAM" else f"{verb} TRANSID", "form": form,
                             "operand": operand, "target": target, "line": stmt[i][2]})  # fmt: skip
            elif (
                words[i] == "CALL" and i + 1 < len(stmt) and stmt[i + 1][0] == "word" and not words[i + 1][0].isdigit()
            ):
                name = words[i + 1]
                if name not in local:
                    rows.append(
                        {"verb": "CALL", "form": "literal", "operand": name, "target": name, "line": stmt[i][2]}
                    )
    return rows


def pli_call_keys(rows: list[dict[str, Any]]) -> set[str]:
    """`L<line> VERB OPERAND -> TARGET` per site (on this reader's rows and the engine's)."""
    return {
        f"L{r['line']} {r['verb']} {(r.get('operand') or '-').upper()} -> {(r.get('target') or '-').upper()}"
        for r in rows
    }


def engine_pli_call_row(c: Any) -> dict[str, Any]:
    """An engine call site in this reader's row shape."""
    return {"verb": c.verb, "operand": c.operand, "target": c.target, "line": c.line}


def _pli_files(repo: Path) -> dict[str, str]:
    return {
        p.relative_to(repo).as_posix(): p.read_text(encoding="utf-8", errors="ignore")
        for p in sorted(repo.rglob("*"))
        if p.is_file() and p.suffix.lower() in PLI_EXTS and ".git" not in p.parts
    }


def pli_included_procedures(files: dict[str, str]) -> set[str]:
    """Names only ever a NESTED procedure (never any file's outermost): a CALL to one
    from another member is an include-internal call (see the section header)."""
    outer, nested = set(), set()
    for text in files.values():
        procs = pli_procedures(text)
        outer.update(procs[:1])
        nested.update(procs[1:])
    return nested - outer


def draft_pli_calls(repo: Path) -> dict[str, dict[str, Any]]:
    """Drafted PL/I program call sites per PL/I source (#3491); `pli_calls_validated`
    signs a file off."""
    files = _pli_files(repo)
    included = pli_included_procedures(files)
    out: dict[str, dict[str, Any]] = {}
    for rel, text in files.items():
        # Every PL/I file, none-at-all included, so an engine call site in a file
        # this reader finds nothing in is still a scored disagreement.
        rows = [r for r in pli_call_rows(text) if not (r["verb"] == "CALL" and r["target"] in included)]
        out[rel] = {"calls": rows, "pli_calls_validated": False, "verification": {"status": "draft", "notes": []}}
    return out


# ==============================================================================
# PL/I data moves (#3491 part 3)
# ==============================================================================
# This tool's own reading of the PL/I assignment statement, over the PL/I token
# stream above (comments dropped, sequence fields removed, single-character
# punctuation; a word starting with a digit is a number). The contract is
# core/pli_data_moves.py's, none of its code: `t1, t2 = expr;` gives one row per
# data item of expr for each target (each item once, in order); an item-free
# expr gives one `literal` row (a single, optionally signed literal) or one
# `function` row (a lone built-in call), else none; `A = B, BY NAME;` is
# corresponding; `X op= e` makes X a source. A data item is a qualified name
# without subscripts (`A.B(I).C` -> A.B.C; `P->X` -> X); a built-in's arguments
# are scanned, the built-in is no source; DFHRESP(x) / DFHVALUE(x) are
# cics_constant. SUBSTR(A, ...) / UNSPEC(A) / ... as a target is A, target_refmod.
# A statement starting with a keyword is an assignment only when `=` follows its
# first word; the action is read after labels, IF ... THEN, ELSE, OTHERWISE,
# WHEN(...) and an ON condition (`ON ENDFILE(F) EOF = '1'B;`). A call to a user
# function reads as an array element (its name the source): only a built-in is
# known to be a function. DSF is too large to key in full (~108k rows): `pli_moves` keys a
# seeded sample of its PL/I files (every PL/I file of a smaller corpus).
_PLI_MV_KEYWORDS = set(
    "IF DO DCL DECLARE CALL RETURN GO GOTO END SELECT WHEN OTHERWISE ON REVERT SIGNAL OPEN CLOSE READ WRITE "
    "REWRITE DELETE LOCATE GET PUT ALLOCATE ALLOC FREE LEAVE ITERATE STOP EXIT EXEC DISPLAY FETCH RELEASE WAIT "
    "FORMAT PROC PROCEDURE BEGIN ENTRY DEFINE PACKAGE ELSE THEN".split()
)
_PLI_BUILTINS = set(
    "ABS ACOS ADD ADDR ADDRDATA ALL ALLOCATION ALLOCN ANY ASIN ATAN ATAND ATANH BIN BINARY BIT BOOL CEIL CENTER "
    "CENTRE CHAR CHARACTER COLLATE COMPLEX COPY COS COSD COSH COUNT CURRENTSTORAGE CSTG DATAFIELD DATE DATETIME "
    "DAYS DAYSTODATE DEC DECIMAL DIM DIVIDE EMPTY ERF EXP FIXED FLOAT FLOOR HBOUND HEX HIGH IMAG INDEX LBOUND LEFT "
    "LENGTH LINENO LOG LOG10 LOG2 LOW LOWERCASE LOWER2 MAX MIN MOD MULTIPLY NULL OFFSET ONCHAR ONCODE ONCOUNT ONFILE "
    "ONKEY ONLOC ONSOURCE PLIRETV POINTER PTR POLY PRECISION PREC PROD REAL REM REPEAT REVERSE RIGHT ROUND SEARCH "
    "SIGN SIN SIND SINH SIZE SQRT STATUS STORAGE STG STRING SUBSTR SUBTRACT SUM SYSNULL TALLY TAN TAND TANH TIME "
    "TRANSLATE TRIM TRUNC UNSPEC UPPERCASE VALID VERIFY WHIGH WLOW".split()
)
_PLI_PSEUDO = {"SUBSTR", "UNSPEC", "STRING", "REAL", "IMAG", "ONCHAR", "ONSOURCE", "ENTRYADDR"}


def _pli_is_number(tok: tuple) -> bool:
    return tok[0] == "word" and tok[1][:1].isdigit()


def _pli_ref(stmt: list, i: int) -> tuple[Optional[str], int]:
    """A data reference at stmt[i] (a word not starting with a digit): the qualified
    name without subscripts, and the index after it."""
    if i >= len(stmt) or stmt[i][0] != "word" or _pli_is_number(stmt[i]):
        return None, i
    parts, j = [stmt[i][1]], i + 1
    while j < len(stmt):
        t = stmt[j][1]
        if t == "(":
            j = _pli_group(stmt, j)
        elif t == "." and j + 1 < len(stmt) and stmt[j + 1][0] == "word" and not _pli_is_number(stmt[j + 1]):
            parts.append(stmt[j + 1][1])
            j += 2
        elif t == "-" and j + 2 < len(stmt) and stmt[j + 1][1] == ">" and stmt[j + 2][0] == "word":
            parts, j = [stmt[j + 2][1]], j + 3
        else:
            break
    return ".".join(parts), j


def _pli_mv_sources(expr: list) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    i = 0
    while i < len(expr):
        tok = expr[i]
        if tok[0] != "word" or _pli_is_number(tok):
            if tok[1] == "." and i + 1 < len(expr) and _pli_is_number(expr[i + 1]):
                i += 2  # a decimal fraction
            else:
                i += 1
            continue
        nxt = expr[i + 1][1] if i + 1 < len(expr) else ""
        if nxt == "(" and tok[1] in ("DFHRESP", "DFHVALUE"):
            end = _pli_group(expr, i + 1)
            item = (tok[1] + "(" + "".join(t[1] for t in expr[i + 2 : end - 1]) + ")", "cics_constant")
            i = end
        elif nxt == "(" and tok[1] in _PLI_BUILTINS:
            i += 1
            continue
        else:
            name, i = _pli_ref(expr, i)
            item = (name or tok[1], "item")
        if item not in out:
            out.append(item)
    return out


def _pli_mv_single(expr: list) -> Optional[tuple[str, str]]:
    body = expr[1:] if expr and expr[0][1] in ("-", "+") else expr
    # A literal: one string, or one number (`1`, `1.5` = word . word).
    if len(body) == 1 and (body[0][0] == "string" or _pli_is_number(body[0])):
        return "".join(t[1] for t in expr), "literal"
    if len(body) == 3 and _pli_is_number(body[0]) and body[1][1] == "." and _pli_is_number(body[2]):
        return "".join(t[1] for t in expr), "literal"
    if body and body[0][0] == "word" and body[0][1] in _PLI_BUILTINS:
        if len(body) == 1 or (body[1][1] == "(" and _pli_group(body, 1) == len(body)):
            return body[0][1], "function"
    return None


def _pli_action_start(stmt: list) -> int:
    i = 0
    while True:
        while i + 1 < len(stmt) and stmt[i][0] == "word" and stmt[i + 1][1] == ":":
            i += 2
        word = stmt[i][1] if i < len(stmt) else ""
        after = stmt[i + 1][1] if i + 1 < len(stmt) else ""
        if word == "IF" and after != "=":
            depth, j = 0, i + 1
            while j < len(stmt) and not (depth == 0 and stmt[j][1] == "THEN"):
                depth += {"(": 1, ")": -1}.get(stmt[j][1], 0)
                j += 1
            i = j + 1
        elif word in ("ELSE", "OTHERWISE") and after != "=":
            i += 1
        elif word == "WHEN" and after == "(":
            i = _pli_group(stmt, i + 1)
        elif word == "ON" and after != "=" and i + 1 < len(stmt) and stmt[i + 1][0] == "word":
            i += 2  # `ON cond[(ref)] [SNAP] statement`: the on-unit's statement is the action
            if i < len(stmt) and stmt[i][1] == "(":
                i = _pli_group(stmt, i)
            if i < len(stmt) and stmt[i][1] == "SNAP":
                i += 1
        else:
            return i


def pli_move_rows(text: str) -> list[dict[str, Any]]:
    """Every PL/I assignment's data-move rows, this tool's own reading (see above)."""
    rows: list[dict[str, Any]] = []
    for whole in _pli_statements(_pli_token_stream(_pli_source_lines(text))):
        stmt = whole[_pli_action_start(whole) :]
        if not stmt or stmt[0][0] != "word" or _pli_is_number(stmt[0]):
            continue
        if stmt[0][1] in _PLI_MV_KEYWORDS and not (len(stmt) > 1 and stmt[1][1] == "="):
            continue
        targets, i, ok = [], 0, True
        while True:
            if i < len(stmt) and stmt[i][1] in _PLI_PSEUDO and i + 1 < len(stmt) and stmt[i + 1][1] == "(":
                name, _ = _pli_ref(stmt, i + 2)
                targets.append((name, True))
                i = _pli_group(stmt, i + 1)
            else:
                name, i = _pli_ref(stmt, i)
                targets.append((name, False))
            if name is None:
                ok = False
                break
            if i < len(stmt) and stmt[i][1] == ",":
                i += 1
                continue
            break
        if not ok:
            continue
        compound = False
        if i + 1 < len(stmt) and stmt[i + 1][1] == "=" and stmt[i][1] in ("+", "-", "*", "/"):
            compound, i = True, i + 1
        elif i + 2 < len(stmt) and stmt[i][1] in ("|", "*") and stmt[i + 1][1] == stmt[i][1] and stmt[i + 2][1] == "=":
            compound, i = True, i + 2  # `||=` / `**=`
        if i >= len(stmt) or stmt[i][1] != "=":
            continue
        expr, corr = stmt[i + 1 :], False
        for j in range(len(expr) - 2):
            if expr[j][1] == "," and expr[j + 1][1] == "BY" and expr[j + 2][1] == "NAME":
                expr, corr = expr[:j], True
                break
        sources = _pli_mv_sources(expr)
        for target, partial in targets:
            srcs = ([(target, "item")] if compound else []) + [x for x in sources if not (compound and x[0] == target)]
            if not srcs:
                single = _pli_mv_single(expr)
                srcs = [single] if single else []
            for src, kind in srcs:
                rows.append({"verb": "ASSIGN", "source": src, "kind": kind, "target": target, "corr": corr,
                             "srm": False, "trm": partial, "line": stmt[0][2]})  # fmt: skip
    return rows


PLI_MOVES_SAMPLE = 25  # DSF files keyed (seeded); every PL/I file of a corpus at most this large
PLI_MOVES_SEED = 3491


def draft_pli_moves(repo: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Drafted PL/I data moves (#3491 part 3) and the key's scope: every PL/I file,
    or a seeded sample of PLI_MOVES_SAMPLE when there are more (DSF)."""
    files = sorted(_pli_files(repo))
    scope = {"files": len(files), "keyed": len(files), "seed": None}
    if len(files) > PLI_MOVES_SAMPLE:
        files = sorted(random.Random(PLI_MOVES_SEED).sample(files, PLI_MOVES_SAMPLE))
        scope = {"files": scope["files"], "keyed": len(files), "seed": PLI_MOVES_SEED}
    out = {
        rel: {
            "moves": sorted(data_move_keys(pli_move_rows((repo / rel).read_text(encoding="utf-8", errors="ignore")))),
            "pli_moves_validated": False,
            "verification": {"status": "draft", "notes": []},
        }
        for rel in files
    }
    return out, scope


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
# Embedded SQL table access (#3446)
# ==============================================================================
# This tool's own reading of what each program DOES to DB2 tables: a TOKEN walk
# over its own `_sql_prepared` code (not the engine's regex anchors), sharing the
# engine's CONTRACT only. Access per table: read (FROM / JOIN / a subquery /
# MERGE USING / a DECLAREd cursor's SELECT, which OPEN and FETCH reach), insert,
# update, delete, merge, lock. INCLUDE, DECLARE ... TABLE and WHENEVER are not
# statements; dynamic SQL names no table.
_SQL_ACCESS_TOKEN = re.compile(r"\"[^\"\n]*\"|'[^'\n]*'?|:[A-Z0-9_-]+|[A-Z@#$][A-Z0-9_@#$-]*|[(),.;]|\S", re.I)
_SQL_CLAUSE_WORDS = {
    "WHERE",
    "GROUP",
    "ORDER",
    "HAVING",
    "FETCH",
    "FOR",
    "WITH",
    "UNION",
    "EXCEPT",
    "INTERSECT",
    "JOIN",
    "INNER",
    "LEFT",
    "RIGHT",
    "FULL",
    "CROSS",
    "ON",
    "OPTIMIZE",
    "QUERYNO",
    "SKIP",
    "SET",
    "VALUES",
    "INTO",
    "OUTER",
}
_SQL_NOT_TABLE = {"FINAL", "NEW", "OLD", "TABLE", "LATERAL", "UNNEST", "XMLTABLE", "SELECT"}
_SQL_CURSOR_NOISE = {
    "NEXT",
    "PRIOR",
    "FIRST",
    "LAST",
    "CURRENT",
    "FROM",
    "INTO",
    "ROWSET",
    "STARTING",
    "AT",
    "ABSOLUTE",
    "RELATIVE",
    "USING",
    "DESCRIPTOR",
    "FOR",
    "ROWS",
    "INSENSITIVE",
    "SENSITIVE",
}


def _sql_statement_regions(code: str, pli: bool) -> list[str]:
    """The text of each EXEC SQL statement (after `EXEC SQL`, before its end)."""
    out = []
    pos = 0
    start_rx = re.compile(r"(?<![A-Z0-9_@#$-])EXEC\s+SQL(?![A-Z0-9_@#$-])", re.I)
    end_rx = re.compile(r";" if pli else r"(?<![A-Z0-9_@#$-])END-EXEC(?![A-Z0-9_@#$-])", re.I)
    while True:
        m = start_rx.search(code, pos)
        if not m:
            return out
        e = end_rx.search(code, m.end())
        if not e:
            return out
        out.append(re.sub(r"--[^\n]*", "", code[m.end() : e.start()]))
        pos = e.end()


def _qualified_at(toks: list[str], i: int) -> tuple[str, int]:
    """(`A.B.C` name starting at toks[i], index after it)."""
    parts = [toks[i]]
    j = i + 1
    while j + 1 < len(toks) and toks[j] == "." and re.match(r'[A-Z@#$"]', toks[j + 1], re.I):
        parts.append(toks[j + 1])
        j += 2
    return ".".join(_sql_unquote(x) for x in parts), j


def sql_table_access(text: str, pli: bool = False) -> list[str]:
    """Sorted `access TABLE` strings for one source file, this tool's own reading."""
    code = _sql_prepared(text, pli)
    found: set[str] = set()
    cursors: dict[str, set[str]] = {}
    used: list[str] = []
    targets = {"INSERT": "insert", "UPDATE": "update", "DELETE": "delete", "MERGE": "merge", "LOCK": "lock"}
    for region in _sql_statement_regions(code, pli):
        toks = [t for t in _SQL_ACCESS_TOKEN.findall(region) if not t.startswith(("'", ":"))]
        if not toks:
            continue
        up = [t.upper() for t in toks]
        verb = up[0]
        if verb in ("INCLUDE", "WHENEVER"):
            continue
        if verb in ("OPEN", "FETCH", "CLOSE"):
            names = [t for t in up[1:] if re.fullmatch(r"[A-Z][A-Z0-9_-]*", t) and t not in _SQL_CURSOR_NOISE]
            if verb != "CLOSE" and names:
                used.append(names[0])
            continue
        declared = None
        if verb == "DECLARE":
            if "CURSOR" not in up[:12]:
                continue  # DECLARE ... TABLE / STATEMENT: not a statement here
            declared = up[1]
        reads: set[str] = set()
        i = 0
        while i < len(up):
            t = up[i]
            if i == 0 and t in targets:
                j = 1
                while j < len(up) and up[j] in ("INTO", "FROM", "TABLE"):
                    j += 1
                if j < len(up) and up[j] != "(":
                    name, i = _qualified_at(toks, j)
                    found.add(f"{targets[t]} {name}")
                    continue
            if t in ("FROM", "JOIN") or (t == "USING" and verb == "MERGE"):
                j = i + 1
                while j < len(up):
                    if up[j] == "(" or up[j] in _SQL_NOT_TABLE:
                        break
                    name, j = _qualified_at(toks, j)
                    reads.add(name)
                    if j < len(up) and up[j] == "AS":
                        j += 1
                    if j < len(up) and up[j] not in _SQL_CLAUSE_WORDS and re.match(r"[A-Z]", up[j]):
                        j += 1  # an alias
                    if j < len(up) and up[j] == ",":
                        j += 1
                        continue
                    break
                i = j
                continue
            i += 1
        if declared:
            cursors.setdefault(declared, set()).update(reads)
        found.update(f"read {r}" for r in reads)
    for c in used:
        found.update(f"read {r}" for r in cursors.get(c, ()))
    return sorted(found)


def draft_sql_access(repo: Path) -> dict[str, dict[str, Any]]:
    """Drafted table access for every COBOL/PL/I source with embedded SQL (#3446).
    Adjudicates nothing until signed off with `sql_access_validated`."""
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(repo.rglob("*")):
        if p.is_file() and p.suffix.lower() in SQL_TABLE_EXTS and ".git" not in p.parts:
            acc = sql_table_access(p.read_text(encoding="utf-8", errors="ignore"), p.suffix.lower() in PLI_EXTS)
            if acc:
                out[p.relative_to(repo).as_posix()] = {
                    "accesses": acc,
                    "sql_access_validated": False,
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
CSD_EXTS = (".csd", ".rdo")  # #3495: `.rdo` is a DFHCSDUP member too
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
# or a CHANNEL passed by LINK/XCTL/START/RETURN/RUN -- and (#3512) the two-word
# web commands in _CICS_TWO_WORD, whose verb is both words.
CICS_EXTS = PROGRAM_EXTS + COPYBOOK_EXTS
_CICS_EXEC = re.compile(r"\bEXEC\s+CICS\b")
_CICS_END = re.compile(r"\bEND-EXEC\b")
_CICS_OPTION = re.compile(r"([A-Z][A-Z0-9-]*)\s*(\((?:[^()']|'[^']*'|\([^()]*\))*\))?")
_CICS_MOVE = re.compile(rf"\bMOVE\s+(?:'([^'\n]*)'|\"([^\"\n]*)\")\s+TO\s+({NAME})")
# #3578: `MOVE a TO b` between two plain data-names -- b can hold what a holds (a's VALUE,
# else a's own MOVEd values), followed at most three hops. Figurative constants are values.
_CICS_MOVE_NAME = re.compile(rf"\bMOVE\s+({NAME})\s+TO\s+({NAME})(?![A-Z0-9-]|\s*\()")
_CICS_FIGURATIVE = {"SPACE", "SPACES", "ZERO", "ZEROS", "ZEROES", "LOW-VALUE", "LOW-VALUES", "HIGH-VALUE",
                    "HIGH-VALUES", "QUOTE", "QUOTES", "NULL", "NULLS", "ALL", "FUNCTION", "LENGTH", "ADDRESS"}  # fmt: skip
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
# #3512: (first word, second word) -> (kind, access, name options by precedence,
# qualifier option). A WEB command's qualifier is its side: CLIENT when it opens,
# converses on or closes an outbound session or codes SESSTOKEN, else SERVER. WEB
# READ / WRITE count only for an HTTPHEADER (not FORMFIELD / QUERYPARM).
_CICS_TWO_WORD = {
    ("WEB", "OPEN"): ("WEB", "open", ("URIMAP", "HOST"), None),
    ("WEB", "CONVERSE"): ("WEB", "converse", ("URIMAP", "PATH"), None),
    ("WEB", "SEND"): ("WEB", "write", ("URIMAP", "PATH"), None),
    ("WEB", "RECEIVE"): ("WEB", "read", (), None),
    ("WEB", "CLOSE"): ("WEB", "close", (), None),
    ("WEB", "READ"): ("WEB", "read", ("HTTPHEADER",), None),
    ("WEB", "WRITE"): ("WEB", "write", ("HTTPHEADER",), None),
    ("INVOKE", "SERVICE"): ("SERVICE", "invoke", ("SERVICE",), "CHANNEL"),
    ("INVOKE", "WEBSERVICE"): ("SERVICE", "invoke", ("WEBSERVICE",), "CHANNEL"),
    ("TRANSFORM", "DATATOXML"): ("TRANSFORM", "encode", ("XMLTRANSFORM",), "CHANNEL"),
    ("TRANSFORM", "XMLTODATA"): ("TRANSFORM", "decode", ("XMLTRANSFORM",), "CHANNEL"),
    ("TRANSFORM", "DATATOJSON"): ("TRANSFORM", "encode", ("JSONTRANSFRM",), "CHANNEL"),
    ("TRANSFORM", "JSONTODATA"): ("TRANSFORM", "decode", ("JSONTRANSFRM",), "CHANNEL"),
}


def _cics_value_of(src: Source, ident: str) -> Optional[str]:
    """`ident`'s quoted VALUE, first declaration wins. Unlike `_value_of` (80 chars)
    the entry may run up to its terminating period, because carddemo pads PIC to
    column 72 and writes VALUE on the next line."""
    if isinstance(src, HlasmSource):  # #3495: an assembler operand names a DC constant
        return src.dc.get(ident)
    if isinstance(src, PliSource):  # #3491: a PL/I operand names its DCL's INIT
        return src.inits.get(ident) or src.inits.get(ident.rsplit(".", 1)[-1])
    m = re.search(
        rf"(?m)^\s*\d{{1,2}}\s+{re.escape(ident)}(?![A-Z0-9-])[^.]{{0,400}}?\bVALUE\s+(?:IS\s+)?(?:'([^']*)'|\"([^\"]*)\")",
        src.raw_text,
    )
    if not m:
        return None
    return ((m.group(1) if m.group(1) is not None else m.group(2)) or "").strip() or None


def _cics_moved(src: Any) -> Callable[[str], set[str]]:
    """ident -> every literal it can be MOVEd in `src`: `MOVE 'LIT' TO ident`, and (#3578)
    `MOVE other TO ident`, which passes on other's VALUE, else other's own MOVEd values,
    followed at most three hops."""
    moves: dict[str, set[str]] = {}
    for m in _CICS_MOVE.finditer(src.raw_text):
        lit = (m.group(1) if m.group(1) is not None else m.group(2) or "").strip()
        if lit:
            moves.setdefault(m.group(3), set()).add(lit)
    moved_from: dict[str, set[str]] = {}
    for m in _CICS_MOVE_NAME.finditer(src.raw_text):
        if m.group(1) not in _CICS_FIGURATIVE and m.group(1) != m.group(2) and not m.group(1)[0].isdigit():
            moved_from.setdefault(m.group(2), set()).add(m.group(1))

    def held(ident: str, hops: int = 0, seen: Optional[set[str]] = None) -> set[str]:
        seen = seen or {ident}
        out = set(moves.get(ident, set()))
        if hops < 3:
            for other in moved_from.get(ident, set()) - seen:
                value = _cics_value_of(src, other)
                out |= {value} if value else held(other, hops + 1, seen | {other})
        return out

    return held


def cics_resource_ops(path: Path) -> list[dict[str, Any]]:
    """Every EXEC CICS command in one COBOL source that names a resource, this
    tool's own reading (see the section header)."""
    src = _key_source(path)  # #3495: or an assembler source
    held = _cics_moved(src)

    def resolve(operand: Optional[str]) -> tuple[Optional[str], Optional[str], Optional[str]]:
        if operand is None:
            return None, None, None
        op = operand.strip()
        if op[:1] in "'\"" and len(op) > 1 and op[-1] == op[0]:
            return (op[1:-1].strip() or None), "literal", None
        if not re.fullmatch(_operand_name(src), op) or op[0].isdigit():
            return None, "expression", None
        value = _cics_value_of(src, op)
        if value:
            return value, "value", None
        found = held(op)
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
        elif len(opts) > 1 and (verb, opts[1][0]) in _CICS_TWO_WORD:
            second = opts[1][0]
            kind, access, names, q_key = _CICS_TWO_WORD[(verb, second)]
            if names == ("HTTPHEADER",) and "HTTPHEADER" not in d:
                continue
            name_key = next((k for k in names if k in d), None)
            qtype = None
            if kind == "WEB":
                qtype = "CLIENT" if "SESSTOKEN" in d or second in ("OPEN", "CONVERSE", "CLOSE") else "SERVER"
            verb = f"{verb} {second}"
        else:
            continue
        name, resolution, candidates = resolve(d.get(name_key) if name_key else None)
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
        if p.is_file() and p.suffix.lower() in CICS_EXTS + HLASM_EXTS + PLI_EXTS and ".git" not in p.parts:
            rows = cics_resource_ops(p)
            if rows:
                out[p.relative_to(repo).as_posix()] = {
                    "operations": rows,
                    "cics_validated": False,
                    "verification": {"status": "draft", "notes": []},
                }
    return out


# ==============================================================================
# CICS task control (#3449)
# ==============================================================================
# This tool's own reading of the CICS task-control commands: RUN, START (and
# START ATTACH), FETCH CHILD / FETCH ANY, FREE CHILD, RETRIEVE, CANCEL, DELAY,
# POST, WAIT EVENT / WAIT EXTERNAL / WAITCICS, ENQ and DEQ. Same contract as the
# engine's core/cics_tasks.py, none of its code: commands are found with the CICS
# section's own `_CICS_EXEC` / `_CICS_OPTION` over the literal-blanked twin, and
# a target resolves through `_cics_value_of`, then one MOVEd literal, then -- the
# #3449 addition -- the STRING statements that build it. A STRING is read here
# as a whole sentence cut at INTO (this reader's own regex walk), and each source
# becomes its literal text, `[0-9]`/`?` per character of a DELIMITED BY SIZE
# data-name's PIC (this reader's own PIC lookup), or `*`.
_TASK_TWO = {("FETCH", "CHILD"), ("FETCH", "ANY"), ("FREE", "CHILD"), ("WAIT", "EVENT"), ("WAIT", "EXTERNAL")}
_TASK_ONE = {"RUN", "START", "RETRIEVE", "CANCEL", "DELAY", "POST", "WAITCICS", "ENQ", "DEQ"}
_TASK_TARGET = {"RUN": "TRANSID", "START": "TRANSID", "START ATTACH": "TRANSID", "CANCEL": "TRANSID"}
_TASK_TARGET.update({"ENQ": "RESOURCE", "DEQ": "RESOURCE"})
_TASK_TOKEN = {"RUN": "CHILD", "START": "REQID", "CANCEL": "REQID", "DELAY": "REQID", "POST": "REQID"}
_TASK_WHEN = ("INTERVAL", "TIME", "AFTER", "AT", "FOR", "UNTIL", "HOURS", "MINUTES", "SECONDS", "MILLISECS")
_KEY_STRING = re.compile(rf"\bSTRING\b(.{{1,1500}}?)\bINTO\s+({NAME})", re.S)
_KEY_STRING_SRC = re.compile(
    rf"('[^']*'|\"[^\"]*\"|{NAME}(?:\s*\([^()]*\))?)(?:\s+DELIMITED\s+(?:BY\s+)?('[^']*'|{NAME}))?"
)


def _key_pic(src: Source, ident: str) -> Optional[str]:
    """`ident`'s PIC string, first declaration wins (this reader's own lookup)."""
    m = re.search(
        rf"(?m)^\s*\d{{1,2}}\s+{re.escape(ident)}\s+[^.]{{0,200}}?\bPIC(?:TURE)?\s+(?:IS\s+)?(\S+)", src.raw_text
    )
    return m.group(1).rstrip(".") if m else None


def _key_pic_glob(pic: Optional[str]) -> str:
    if not pic:
        return "*"
    body = pic.upper()
    body = body[1:] if body.startswith("S") else body
    parts = re.findall(r"([9XA])(?:\((\d+)\))?", body)
    if not parts or "".join(c + (f"({n})" if n else "") for c, n in parts) != body:
        return "*"
    width = sum(int(n or 1) for _, n in parts)
    return ("[0-9]" if {c for c, _ in parts} == {"9"} else "?") * width


def _key_string_globs(src: Source) -> dict[str, set[str]]:
    """Receiver -> the fnmatch patterns its STRING statements build."""
    out: dict[str, set[str]] = {}
    for m in _KEY_STRING.finditer(src.raw_text):
        body = m.group(1)
        if re.search(r"\.\s", _blank_literals(body)):
            continue  # a sentence ended before INTO: not one STRING statement
        glob = ""
        for sm in _KEY_STRING_SRC.finditer(body):
            item, delim = sm.group(1), sm.group(2)
            if item.upper() in ("DELIMITED", "BY", "SIZE"):
                continue
            if item[0] in "'\"":
                text = item[1:-1]
                if delim and delim.upper() != "SIZE":
                    cut = delim[1:-1] if delim[0] in "'\"" else (" " if delim.upper().startswith("SPACE") else None)
                    glob += re.sub(r"([\[\]*?])", r"[\1]", text.split(cut)[0] if cut else text)
                    if not cut or cut not in text:
                        glob += "*"
                else:
                    glob += re.sub(r"([\[\]*?])", r"[\1]", text)
            elif delim and delim.upper() == "SIZE" and "(" not in item:
                glob += _key_pic_glob(_key_pic(src, item))
            else:
                glob += "*"
        glob = re.sub(r"\*+", "*", glob)
        if re.search(r"[A-Z0-9]", re.sub(r"\[[^\]]*\]", "", glob)):
            out.setdefault(m.group(2), set()).add(glob)
    return out


def cics_task_ops(path: Path) -> list[dict[str, Any]]:
    """Every CICS task-control command in one COBOL source, this tool's own reading."""
    src = _key_source(path)  # #3495: or an assembler source
    held = _cics_moved(src)  # #3578: + MOVE chains
    globs = _key_string_globs(src)

    def resolve(operand: Optional[str], built: bool) -> tuple[Optional[str], Optional[str], Optional[str]]:
        if operand is None:
            return None, None, None
        op = operand.strip()
        if op[:1] in "'\"" and len(op) > 1 and op[-1] == op[0]:
            return (op[1:-1].strip() or None), "literal", None
        if not re.fullmatch(_operand_name(src), op) or op[0].isdigit():
            return None, "expression", None
        value = _cics_value_of(src, op)
        if value:
            return value, "value", None
        found = held(op)
        if len(found) == 1 and not (built and globs.get(op)):
            return next(iter(found)), "move", None
        every = found | (globs.get(op, set()) if built else set())
        if not every:
            return None, "unresolved", None
        wild = any(re.search(r"[*?\[]", re.sub(r"\[[\[\]*?]\]", "", c)) for c in every)
        if len(every) == 1 and not wild:
            return next(iter(every)), "string", None
        return None, ("pattern" if wild else "ambiguous"), ",".join(sorted(every))

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
        first, second = opts[0][0], (opts[1] if len(opts) > 1 else (None, None))
        if (first, second[0]) in _TASK_TWO and (second[1] is None or first in ("FETCH", "FREE")):
            verb, rest = f"{first} {second[0]}", opts[2:]
            token = second[1] if first in ("FETCH", "FREE") else None
        elif first == "START" and second == ("ATTACH", None):
            verb, rest, token = "START ATTACH", opts[2:], None
        elif first in _TASK_ONE:
            verb, rest, token = first, opts[1:], None
        else:
            continue
        d: dict[str, Optional[str]] = {}
        for k, v in rest:
            d.setdefault(k, v)
        if verb in _TASK_TOKEN:
            token = d.get(_TASK_TOKEN[verb])
        target = _TASK_TARGET.get(verb)
        name, resolution, candidates = resolve(d.get(target) if target else None, target == "TRANSID")
        clause = next((c for c in ("FROM", "INTO", "SET") if d.get(c)), None)
        out.append(
            {
                "verb": verb,
                "name": name,
                "resolution": resolution,
                "candidates": candidates,
                "channel": resolve(d.get("CHANNEL"), False)[0],
                "token": token.upper() if token else None,
                "record_clause": clause,
                "record": d[clause].upper() if clause and d.get(clause) else None,
                "timing": " ".join(f"{k}({v})" if v is not None else k for k, v in rest if k in _TASK_WHEN) or None,
                "line": src.line_of(m.start()),
            }
        )
    return out


def cics_task_keys(rows: list[dict[str, Any]]) -> set[str]:
    """One comparison unit per command: `L<line> VERB T=<target> ch=<channel>
    tok=<token> CLAUSE=RECORD @<timing>`; an unresolved target is
    `<resolution[:candidates]>`. Works on this reader's rows and the engine's."""
    out = set()
    for r in rows:
        if r.get("name"):
            target = r["name"].upper()
        elif r.get("resolution"):
            cands = r.get("candidates")
            target = f"<{r['resolution']}{':' + cands.upper() if cands else ''}>"
        else:
            target = "-"
        record = f" {r['record_clause']}={(r.get('record') or '').upper()}" if r.get("record_clause") else ""
        timing = f" @{r['timing'].upper()}" if r.get("timing") else ""
        out.add(
            f"L{r['line']} {r['verb']} T={target} ch={(r.get('channel') or '-').upper()} "
            f"tok={(r.get('token') or '-').upper()}{record}{timing}"
        )
    return out


def engine_task_row(t: Any) -> dict[str, Any]:
    """An engine `EngineCicsTask` in this reader's row shape (for the unit key)."""
    return {
        "verb": t.verb,
        "name": t.name,
        "resolution": t.resolution,
        "candidates": t.candidates,
        "channel": t.channel,
        "token": t.token,
        "record_clause": t.record_clause,
        "record": t.record,
        "timing": t.timing,
        "line": t.line,
    }


def task_children(rows: list[dict[str, Any]], transids: set[str]) -> set[str]:
    """`VERB TRANSID` for every CSD transaction a RUN/START target can be: the
    resolved name, or each defined transid a candidate literal / pattern matches."""
    import fnmatch

    out = set()
    for r in rows:
        if r["verb"] not in ("RUN", "START", "START ATTACH"):
            continue
        cands = [r["name"]] if r.get("name") else [c for c in (r.get("candidates") or "").split(",") if c]
        for t in transids:
            if any(fnmatch.fnmatchcase(t, c.upper()) for c in cands):
                out.add(f"{r['verb']} {t}")
    return out


def draft_cics_tasks(repo: Path) -> dict[str, dict[str, Any]]:
    """Drafted CICS task control for every COBOL source that issues any (#3449),
    with the CSD transactions each RUN/START reaches (`children`). Adjudicates
    nothing until signed off with `cics_tasks_validated`."""
    transids = {t for tx in _key_transactions(repo).values() for t in tx}
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(repo.rglob("*")):
        if p.is_file() and p.suffix.lower() in CICS_EXTS + HLASM_EXTS + PLI_EXTS and ".git" not in p.parts:
            rows = cics_task_ops(p)
            if rows:
                out[p.relative_to(repo).as_posix()] = {
                    "operations": rows,
                    "children": sorted(task_children(rows, transids)),
                    "cics_tasks_validated": False,
                    "verification": {"status": "draft", "notes": []},
                }
    return out


# ==============================================================================
# Job submission through the internal reader (#3448)
# ==============================================================================
# This tool's own reading of "who submits which job". Online: a COBOL source
# writes (WRITEQ TD, read by this tool's own cics_resource_ops) a queue that
# this tool's own CSD reader finds defined TYPE(EXTRA), and either the source
# holds a literal `//NAME JOB` card or some JCL routes that queue's DDNAME to
# SYSOUT=(x,INTRDR). Batch: a JCL step routes a DD to SYSOUT=(x,INTRDR), and the
# job is the member of that step's SYSUT1 library. JCL is read line by line
# here (no statement parser); a PROC target prefers a procedure member.
_KEY_JOB_CARD = re.compile(r"[\"']//([A-Z@#$][A-Z0-9@#$]{0,7})\s+JOB\b")
_KEY_EXEC_CARD = re.compile(r"[\"']//(?:[A-Z@#$][A-Z0-9@#$]{0,7})?\s+EXEC\s+(?:(PROC|PGM)=)?([A-Z@#$][A-Z0-9@#$]{0,7})")
_KEY_INTRDR = re.compile(r"SYSOUT=\([^,()]*,\s*INTRDR\s*[,)]", re.I)


def _key_jcl_member(repo: Path, name: str, proc: bool) -> Optional[str]:
    hits = sorted(
        p.relative_to(repo).as_posix()
        for p in repo.rglob("*")
        if p.is_file() and p.suffix.lower() in JCL_EXTS and p.stem.upper() == name.upper() and ".git" not in p.parts
    )
    wanted = [h for h in hits if (Path(h).suffix.lower() == ".prc" or "/proc/" in f"/{h.lower()}") == proc] or hits
    return wanted[0] if len(wanted) == 1 else None


def _key_intrdr_steps(text: str) -> list[tuple[Optional[str], str, Optional[str]]]:
    """(step, ddname, SYSUT1 DSN of the step) for each DD routed to the internal reader."""
    out: list[tuple[Optional[str], str, Optional[str]]] = []
    step: Optional[str] = None
    pending: list[tuple[Optional[str], str]] = []
    sysut1: Optional[str] = None
    for raw in text.split("\n") + ["// EXEC"]:
        line = raw[:72].rstrip()
        if not line.startswith("//") or line.startswith("//*"):
            continue
        parts = line[2:].split(None, 2)
        if not parts:
            continue
        label, op = (None, parts[0]) if line[2:3] in (" ", "") else (parts[0], parts[1] if len(parts) > 1 else "")
        rest = line.split(op, 1)[1] if op and op in line else ""
        if op.upper() in ("EXEC", "PROC", "PEND", "JOB"):
            out.extend((s, d, sysut1) for s, d in pending)
            step, pending, sysut1 = (label.upper() if label and op.upper() == "EXEC" else None), [], None
        elif op.upper() == "DD":
            if label and label.upper() == "SYSUT1":
                m = re.search(r"DSN(?:AME)?=([^,\s]+)", rest, re.I)
                sysut1 = m.group(1).upper() if m else None
            if _KEY_INTRDR.search(rest):
                pending.append((step, (label or "").upper()))
    return out


def draft_job_submissions(repo: Path) -> dict[str, dict[str, Any]]:
    """Drafted job submissions per submitting file (#3448), as `via X -> ...`
    strings. Adjudicates nothing until signed off with `submissions_validated`."""
    files = [p for p in sorted(repo.rglob("*")) if p.is_file() and ".git" not in p.parts]
    tdqs: dict[str, Optional[str]] = {}
    intrdr: dict[str, list] = {}
    for p in files:
        suffix = p.suffix.lower()
        if suffix not in CSD_EXTS + JCL_EXTS:
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        if is_csd_deck(p, text):
            for r in csd_resource_definitions(text):
                if r["resource_type"] == "TDQUEUE" and (r["queue_type"] or "").startswith("EXTRA"):
                    tdqs[r["name"]] = r["ddname"]
        if suffix in JCL_EXTS:
            steps = _key_intrdr_steps(text)
            if steps:
                intrdr[p.relative_to(repo).as_posix()] = steps
    intrdr_dds = {dd for steps in intrdr.values() for _s, dd, _src in steps}
    out: dict[str, dict[str, Any]] = {}
    for p in files:
        if p.suffix.lower() not in PROGRAM_EXTS:
            continue
        src = Source(p)
        jobs = sorted(set(_KEY_JOB_CARD.findall(src.raw_text)))
        runs = []
        if jobs:
            for kind, name in _KEY_EXEC_CARD.findall(src.raw_text):
                kind = kind or "PROC"
                runs.append(f"{kind} {name} = {_key_jcl_member(repo, name, kind == 'PROC') or '?'}")
        queues = set()
        for r in cics_resource_ops(p):
            if r["kind"] == "QUEUE" and r["access"] == "write" and r["qualifier"] == "TD":
                queues |= {r["name"].upper()} if r["name"] else set((r["candidates"] or "").upper().split(",")) - {""}
        subs = set()
        for q in sorted(queues & set(tdqs)):
            if jobs or (tdqs[q] or "") in intrdr_dds:
                subs |= {f"tdq {q} -> JOB {j}" for j in jobs} | {f"tdq {q} -> {r}" for r in runs}
                if not jobs:
                    subs.add(f"tdq {q} -> ?")
        if subs:
            out[p.relative_to(repo).as_posix()] = {
                "submissions": sorted(subs),
                "submissions_validated": False,
                "verification": {"status": "draft", "notes": []},
            }
    for rel, steps in intrdr.items():
        subs = set()
        for _step, dd, source in steps:
            member = source.rsplit("(", 1)[1].rstrip(")") if source and source.endswith(")") and "(" in source else None
            if member and not member.lstrip("+-").isdigit():
                subs.add(f"intrdr {dd} -> JOB {member} = {_key_jcl_member(repo, member, False) or '?'}")
            else:
                subs.add(f"intrdr {dd} -> ?")
        out[rel] = {
            "submissions": sorted(subs),
            "submissions_validated": False,
            "verification": {"status": "draft", "notes": []},
        }
    return out


def engine_job_submissions(entries: list[dict[str, Any]]) -> dict[str, set[str]]:
    """GalaxyIR.job_submissions() in this reader's `via X -> ...` unit form."""
    out: dict[str, set[str]] = {}
    for e in entries:
        subs = out.setdefault(e["submitter"], set())
        if e["via"] == "tdq":
            subs |= {f"tdq {e['queue']} -> JOB {j}" for j in e["jobs"]}
            subs |= {f"tdq {e['queue']} -> {r['kind']} {r['name']} = {r['resolves_to'] or '?'}" for r in e["runs"]}
            if not e["jobs"]:
                subs.add(f"tdq {e['queue']} -> ?")
        else:
            subs |= {f"intrdr {e['dd']} -> JOB {r['name']} = {r['resolves_to'] or '?'}" for r in e["runs"]}
            if not e["runs"]:
                subs.add(f"intrdr {e['dd']} -> ?")
    return out


# ==============================================================================
# IBM MQ calls (#3447)
# ==============================================================================
# This tool's own reading of a COBOL program's MQI calls: one token walk over the
# raw text (a literal is one token, so `DISPLAY 'CALL MQPUT'` is never a call),
# carrying the same contract as the engine's core/mq_calls.py and none of its
# code. The queue of an MQOPEN / MQPUT1 is the operand last MOVEd to its
# descriptor's OBJECTNAME; an operand resolves through `_cics_value_of`, then the
# literals MOVEd to it, following name-to-name MOVEs (depth 3), with MQTM-QNAME
# read as `trigger` and MQMD-REPLYTOQ as `reply_to`. A PUT / GET / CLOSE is
# matched to its MQOPEN by the handle it passes or the one MOVEd into that
# operand just before it; copies of an open's handle made before the next MQ call
# are that open's too.
_MQ_TOKEN = re.compile(r"'[^'\n]*'|\"[^\"\n]*\"|[A-Z0-9][A-Z0-9-]*|[=+.,]")
_MQ_RUNTIME = {"MQTM-QNAME": "trigger", "MQMD-REPLYTOQ": "reply_to"}
_MQ_FIG = {"SPACE", "SPACES", "LOW-VALUE", "LOW-VALUES", "HIGH-VALUE", "HIGH-VALUES", "ZERO", "ZEROS"}


def mq_call_ops(path: Path) -> list[dict[str, Any]]:
    """Every MQ call in one COBOL source, this tool's own reading (see above)."""
    src = Source(path)
    toks = [(m.group(0), m.start()) for m in _MQ_TOKEN.finditer(src.raw_text)]
    n = len(toks)

    def name_at(i: int) -> tuple[Optional[str], int]:
        """(data-name at i, index after it and any `OF qualifier`)."""
        if i >= n or toks[i][0][0] in "'\"=+.,":
            return None, i
        j = i + 1
        if j + 1 < n and toks[j][0] == "OF":
            j += 2
        return toks[i][0], j

    moved: dict[str, set[str]] = {}
    events: list[tuple] = []
    i = 0
    while i < n:
        t = toks[i][0]
        if t == "MOVE" and i + 1 < n:
            src_tok = toks[i + 1][0]
            j = i + 2
            if j + 1 < n and toks[j][0] == "OF":
                j += 2
            if j < n and toks[j][0] == "TO":
                tgt, k = name_at(j + 1)
                qual = toks[j + 2][0] if tgt and j + 3 < n and toks[j + 2][0] == "OF" else None
                if tgt:
                    if src_tok[0] in "'\"":
                        if src_tok[1:-1].strip():
                            moved.setdefault(tgt, set()).add("'" + src_tok[1:-1].strip())
                    elif src_tok not in _MQ_FIG and src_tok[0] not in "=+.,":
                        moved.setdefault(tgt, set()).add(src_tok)
                    events.append(("move", src_tok, tgt, qual, toks[i][1]))
                    i = k
                    continue
        elif t == "COMPUTE" and i + 2 < n and toks[i + 2][0] == "=":
            words, j = [], i + 3
            while j < n and toks[j][0].startswith("MQ"):
                words.append(toks[j][0])
                j += 2 if j + 1 < n and toks[j + 1][0] == "+" else 1
                if toks[j - 1][0] != "+":
                    break
            events.append(("opts", toks[i + 1][0], words, toks[i][1]))
        elif t == "CALL" and i + 1 < n and toks[i + 1][0][:1] in "'\"" and toks[i + 1][0][1:3] == "MQ":
            verb = toks[i + 1][0][1:-1]
            args, j = [], i + 2
            if j < n and toks[j][0] == "USING":
                j += 1
                while j < n and len(args) < 4:
                    if toks[j][0] in ("BY", "REFERENCE", "CONTENT", "VALUE"):
                        j += 1
                        continue
                    a, j2 = name_at(j)
                    if not a or a == "END-CALL":
                        break
                    args.append(a)
                    j = j2
            events.append(("call", verb, args, toks[i][1]))
        i += 1

    def values_of(name: str, depth: int = 0) -> set[str]:
        if name in _MQ_RUNTIME:
            return {"<" + _MQ_RUNTIME[name] + ">"}
        v = _cics_value_of(src, name)
        if v:
            return {"'" + v}
        out: set[str] = set()
        for x in moved.get(name, set()):
            out |= {x} if x.startswith("'") else (values_of(x, depth + 1) if depth < 3 else set())
        return out

    def read(operand: Optional[str]) -> tuple[Optional[str], str, Optional[str]]:
        if operand is None:
            return None, "unresolved", None
        if operand[0] in "'\"":
            return operand[1:-1].strip() or None, "literal", None
        found = values_of(operand)
        if len(found) == 1:
            only = next(iter(found))
            if only.startswith("'"):
                return only[1:], ("value" if _cics_value_of(src, operand) else "move"), None
            return None, only[1:-1], None
        if found:
            return None, "ambiguous", ",".join(sorted(x.lstrip("'") for x in found))
        return None, "unresolved", None

    family = {"MQOPEN": "MQOO-", "MQPUT": "MQPMO-", "MQPUT1": "MQPMO-", "MQGET": "MQGMO-"}
    objname: dict[Optional[str], str] = {}
    opts_by_field: dict[str, list[str]] = {}
    into_handle: dict[str, str] = {}
    opens: list[dict[str, Any]] = []
    fresh: Optional[dict[str, Any]] = None
    out: list[dict[str, Any]] = []
    for ev in events:
        if ev[0] == "move":
            _, s_tok, tgt, qual, _off = ev
            if tgt.endswith("OBJECTNAME"):
                objname[qual] = s_tok
                objname[None] = s_tok
            elif re.fullmatch(r"MQ(?:OO|PMO|GMO)-[A-Z0-9-]+", s_tok):
                opts_by_field[tgt] = [s_tok]
            elif s_tok[0] not in "'\"":
                into_handle[tgt] = s_tok
                if fresh is not None and s_tok in fresh["aliases"]:
                    fresh["aliases"].add(tgt)
            continue
        if ev[0] == "opts":
            opts_by_field[ev[1]] = ev[2]
            continue
        _, verb, args, off = ev
        fam = family.get(verb)
        opts: list[str] = []
        if fam:
            for words in reversed(list(opts_by_field.values())):
                if words and words[0].startswith(fam):
                    opts = words
                    break
        if verb in ("MQPUT", "MQPUT1"):
            direction: Optional[str] = "put"
        elif verb == "MQGET":
            direction = "get"
        elif verb == "MQOPEN":
            w = set(opts)
            direction = (
                "get"
                if any(x.startswith("MQOO-INPUT") for x in w)
                else "browse"
                if "MQOO-BROWSE" in w
                else "put"
                if "MQOO-OUTPUT" in w
                else "inquire"
                if "MQOO-INQUIRE" in w
                else "set"
                if "MQOO-SET" in w
                else None
            )
        else:
            direction = None
        row: dict[str, Any] = {"verb": verb, "direction": direction, "queue": None, "resolution": None}
        row.update({"candidates": None, "open_line": None, "line": src.line_of(off)})
        if verb in ("MQOPEN", "MQPUT1") and len(args) >= 2:
            row["queue"], row["resolution"], row["candidates"] = read(objname.get(args[1], objname.get(None)))
            if verb == "MQOPEN" and len(args) >= 4:
                fresh = {"row": row, "hobj": args[3], "aliases": {args[3]}}
                opens.append(fresh)
        elif verb in ("MQPUT", "MQGET", "MQCLOSE", "MQINQ", "MQSET") and len(args) >= 2:
            want = into_handle.get(args[1], args[1])
            hit = [o for o in opens if want in o["aliases"] - {o["hobj"]}] or [o for o in opens if want in o["aliases"]]
            hit = hit or [o for o in opens if args[1] in o["aliases"]]
            if len(hit) > 1:
                hit = hit[-1:]
            if hit:
                o = hit[0]["row"]
                row.update({k: o[k] for k in ("queue", "resolution", "candidates")})
                row["open_line"] = o["line"]
            else:
                row["resolution"] = "unresolved"
        out.append(row)
        into_handle = {}
        if verb != "MQOPEN":
            fresh = None
    return out


def mq_call_keys(rows: list[dict[str, Any]]) -> set[str]:
    """One unit per call: `L<line> VERB dir=<d> q=<queue | <resolution[:cands]>>
    open=L<n>`. Works on this reader's rows and the engine's."""
    out = set()
    for r in rows:
        if r.get("queue"):
            q = r["queue"].upper()
        elif r.get("resolution"):
            q = f"<{r['resolution']}{':' + r['candidates'].upper() if r.get('candidates') else ''}>"
        else:
            q = "-"
        opened = f" open=L{r['open_line']}" if r.get("open_line") else ""
        out.add(f"L{r['line']} {r['verb']} dir={r.get('direction') or '-'} q={q}{opened}")
    return out


def engine_mq_row(q: Any) -> dict[str, Any]:
    """An engine `EngineMqCall` in this reader's row shape."""
    return {
        "verb": q.verb,
        "direction": q.direction,
        "queue": q.queue,
        "resolution": q.resolution,
        "candidates": q.candidates,
        "open_line": q.open_line,
        "line": q.line,
    }


def draft_mq(repo: Path) -> dict[str, dict[str, Any]]:
    """Drafted MQ calls for every COBOL source that makes one (#3447). Adjudicates
    nothing until signed off with `mq_validated`."""
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(repo.rglob("*")):
        if p.is_file() and p.suffix.lower() in CICS_EXTS and ".git" not in p.parts:
            rows = mq_call_ops(p)
            if rows:
                out[p.relative_to(repo).as_posix()] = {
                    "calls": rows,
                    "mq_validated": False,
                    "verification": {"status": "draft", "notes": []},
                }
    return out


# ==============================================================================
# Units of work and error handling (#3453)
# ==============================================================================
# This tool's own reading of commit / rollback points, HANDLE CONDITION / ABEND /
# AID handlers, explicit ABENDs and RESP checks. Commands are found the CICS
# section's way (`_CICS_EXEC` over the literal-blanked twin, options by
# `_CICS_OPTION`); EXEC SQL COMMIT / ROLLBACK by its own regex. A RESP check's
# window is read here from this tool's Source: from END-EXEC to the next command
# setting the same RESP field, the next Area A paragraph / section header, or
# 8000 characters; a DFHRESP(x) in it counts once the field has been named.
_UOW_SQL = re.compile(r"\bEXEC\s+SQL\s+(COMMIT|ROLLBACK)\b((?:\s+(?:WORK|TO|SAVEPOINT|RELEASE)\b)*)")
_UOW_DFHRESP = re.compile(r"DFHRESP\s*\(\s*([A-Z][A-Z0-9]*)\s*\)")
_UOW_HEADER = re.compile(r"^[A-Z0-9][A-Z0-9-]*(?:\s+SECTION)?\s*\.\s*$")
_UOW_SKIP = {"HANDLE", "IGNORE", "PUSH", "POP", "ABEND"}


# EIBRESP codes, this tool's own table (CICS Application Programming Reference):
# a RESP field tested by number (`WHEN 13`) names the same condition as DFHRESP(NOTFND).
_UOW_CODES = {
    "0": "NORMAL",
    "1": "ERROR",
    "4": "EOF",
    "12": "FILENOTFOUND",
    "13": "NOTFND",
    "14": "DUPREC",
    "15": "DUPKEY",
    "16": "INVREQ",
    "17": "IOERR",
    "18": "NOSPACE",
    "19": "NOTOPEN",
    "20": "ENDFILE",
    "21": "ILLOGIC",
    "22": "LENGERR",
    "23": "QZERO",
    "26": "ITEMERR",
    "27": "PGMIDERR",
    "28": "TRANSIDERR",
    "36": "MAPFAIL",
    "44": "QIDERR",
    "70": "NOTAUTH",
}


def _uow_numeric(text: str, var: str) -> set[str]:
    """Codes compared with `var` by number: `var [NOT] = n` / `EQUAL [TO] n`, and the
    `WHEN n` arms of `EVALUATE var` itself (a nested EVALUATE's arms skipped)."""
    out: set[str] = set()
    v = re.escape(var)
    for m in re.finditer(rf"\b{v}(?![A-Z0-9-])\s*(?:NOT\s+)?(?:=|EQUAL(?:\s+TO)?)\s*(\d+)\b(?!\.\d)", text):
        out.add(_UOW_CODES.get(str(int(m.group(1))), str(int(m.group(1)))))
    for ev in re.finditer(rf"\bEVALUATE\s+{v}(?![A-Z0-9-])", text):
        # Walk this EVALUATE's own level only; a nested one's WHENs are not ours.
        level = 0
        for tok in re.finditer(r"\b(END-EVALUATE|EVALUATE|WHEN)\b(?:\s+(\d+)\b(?!\.\d))?", text[ev.end() :]):
            if tok.group(1) == "EVALUATE":
                level += 1
            elif tok.group(1) == "END-EVALUATE":
                if level == 0:
                    break
                level -= 1
            elif level == 0 and tok.group(2):
                out.add(_UOW_CODES.get(str(int(tok.group(2))), str(int(tok.group(2)))))
    # #3495: the assembler tests. `OC v,v` ORs a field into itself to set the
    # condition code -- zero is NORMAL; `CLC v,=F'n'` / `=AL4(n)` compares by number.
    if re.search(rf"\bOC\s+{v},{v}(?![A-Z0-9@#$_])", text):
        out.add(_UOW_CODES.get("0", "0"))
    for m in re.finditer(rf"\bCLC\s+{v},=(?:F'|AL4\()(\d+)", text):
        out.add(_UOW_CODES.get(str(int(m.group(1))), str(int(m.group(1)))))
    return out


def uow_handler_ops(path: Path) -> list[dict[str, Any]]:
    """Every unit-of-work point, handler, ABEND and RESP check in one COBOL
    source, this tool's own reading (see the section header)."""
    src = _key_source(path)  # #3495: or an assembler source

    def value(op: Optional[str]) -> Optional[str]:
        if not op:
            return None
        op = op.strip()
        if op[:1] in "'\"" and op[-1:] == op[:1] and len(op) > 1:
            return op[1:-1].strip() or None
        return _cics_value_of(src, op) or op

    # Offsets (in src.text) where an Area A header line starts.
    headers, offset = [], 0
    for _no, area in src.lines:
        if area[:4].strip() and _UOW_HEADER.match(area.strip()):
            headers.append(offset)
        offset += len(area) + 1

    cmds = []
    for m in _CICS_EXEC.finditer(src.text):
        end = _CICS_END.search(src.text, m.end())
        stop = end.start() if end else len(src.text)
        opts = [
            (o.group(1), " ".join(o.group(2)[1:-1].split()) if o.group(2) else None)
            for o in _CICS_OPTION.finditer(src.raw_text[m.end() : stop])
        ]
        if opts and opts[0][1] is None:
            cmds.append((m.start(), end.end() if end else stop, opts))

    def mk(kind: str, source: str, verb: str, off: int, **kw: Any) -> dict[str, Any]:
        r = {"kind": kind, "source": source, "verb": verb, "condition": None, "target": None}
        r.update({"target_kind": None, "resp_var": None, "attributes": None, "line": src.line_of(off)})
        r.update(kw)
        return r

    out: list[tuple[int, int, dict[str, Any]]] = []
    for i, (pos, end, opts) in enumerate(cmds):
        verb, rest = opts[0][0], opts[1:]
        d = dict(rest)
        if verb == "SYNCPOINT":
            rb = "ROLLBACK" in d
            out.append(
                (pos, 0, mk("ROLLBACK" if rb else "COMMIT", "CICS", "SYNCPOINT ROLLBACK" if rb else "SYNCPOINT", pos))
            )
        elif verb == "ABEND":
            flags = " ".join(k for k, v in rest if v is None and k in ("NODUMP", "CANCEL")) or None
            out.append((pos, 0, mk("ABEND", "CICS", "ABEND", pos, condition=value(d.get("ABCODE")), attributes=flags)))
        elif verb == "HANDLE" and rest and rest[0][0] == "ABEND":
            h = dict(rest[1:])
            if h.get("LABEL"):
                tgt, tk = h["LABEL"], "LABEL"
            elif h.get("PROGRAM"):
                tgt, tk = value(h["PROGRAM"]), "PROGRAM"
            else:
                tgt, tk = None, "RESET" if "RESET" in h else "CANCEL"
            out.append((pos, 0, mk("HANDLE_ABEND", "CICS", "HANDLE ABEND", pos, target=tgt, target_kind=tk)))
        elif verb in ("HANDLE", "IGNORE") and rest and rest[0][0] in ("CONDITION", "AID"):
            for cond, label in rest[1:]:
                if cond in ("RESP", "RESP2", "NOHANDLE"):
                    continue
                if verb == "IGNORE":
                    out.append((pos, 0, mk(f"IGNORE_{rest[0][0]}", "CICS", "IGNORE CONDITION", pos, condition=cond)))
                else:
                    tk = "LABEL" if label else "DEFAULT"
                    kind = f"HANDLE_{rest[0][0]}"
                    out.append(
                        (
                            pos,
                            0,
                            mk(kind, "CICS", f"HANDLE {rest[0][0]}", pos, condition=cond, target=label, target_kind=tk),
                        )
                    )
        elif verb in ("PUSH", "POP") and rest and rest[0][0] == "HANDLE":
            out.append((pos, 0, mk(f"{verb}_HANDLE", "CICS", f"{verb} HANDLE", pos)))
        if verb in _UOW_SKIP:
            continue
        var = (d.get("RESP") or "") or ("EIBRESP" if "NOHANDLE" in d else "")
        if not var:
            continue
        limit = min(len(src.text), end + 8000)
        limit = min([h for h in headers if h > end] + [limit])
        for later_pos, _e, later in cmds[i + 1 :]:
            if later_pos >= limit:
                break
            ld = dict(later[1:])
            if (ld.get("RESP") or "") == var or (var == "EIBRESP" and "NOHANDLE" in ld):
                limit = later_pos
                break
        window = src.text[end:limit]
        first = re.search(rf"(?<![A-Z0-9-]){re.escape(var)}(?![A-Z0-9-])", window)
        seen = set(_UOW_DFHRESP.findall(src.raw_text[end + first.start() : limit])) if first else set()
        if first:
            seen |= _uow_numeric(src.raw_text[end:limit], var)
        out.append(
            (pos, 1, mk("RESP_CHECK", "CICS", verb, pos, condition=",".join(sorted(seen)) or None, resp_var=var))
        )
    for m in _UOW_SQL.finditer(src.text):
        tail = " ".join(m.group(2).split())
        out.append(
            (
                m.start(),
                0,
                mk(
                    "COMMIT" if m.group(1) == "COMMIT" else "ROLLBACK", "SQL", f"{m.group(1)} {tail}".strip(), m.start()
                ),
            )
        )
    out.sort(key=lambda x: (x[0], x[1]))
    rows = [r for _p, _k, r in out]
    if isinstance(src, PliSource):  # #3491: PL/I's own condition handling
        rows += pli_on_rows(path.read_text(encoding="utf-8", errors="ignore"))
    return rows


def uow_keys(rows: list[dict[str, Any]]) -> set[str]:
    """One unit per row: `L<line> KIND VERB c=<condition> t=<target>/<kind> v=<resp field> a=<attrs>`.
    Works on this reader's rows and the engine's."""
    return {
        f"L{r['line']} {r['kind']} {r['verb']} c={r.get('condition') or '-'} "
        f"t={(r.get('target') or '-').upper()}/{r.get('target_kind') or '-'} v={r.get('resp_var') or '-'} "
        f"a={r.get('attributes') or '-'}"
        for r in rows
    }


def engine_uow_row(u: Any) -> dict[str, Any]:
    """An engine `EngineUowHandler` in this reader's row shape."""
    return {
        k: getattr(u, k)
        for k in ("kind", "source", "verb", "condition", "target", "target_kind", "resp_var", "attributes", "line")
    }


# ---- #3491: PL/I condition handling ------------------------------------------
# This tool's own reading of PL/I's ON / REVERT / SIGNAL statements, over the PL/I
# token stream (comments dropped, sequence fields removed) split at `;`. An ON
# counts where a statement can begin (`_pli_clause_starts`) and names a condition
# from the Language Reference's list: a bare condition, or a file condition /
# CONDITION(name) with its parenthesised reference. The on-unit that follows is
# SYSTEM, NULL (the statement ends: the condition is swallowed), BLOCK (BEGIN),
# PROCEDURE (CALL x), LABEL (GO TO x) or STATEMENT; SNAP is an attribute.
_PLI_BARE_CONDITIONS = {
    "ANYCONDITION", "ANYCOND", "AREA", "ATTENTION", "ATTN", "CONVERSION", "CONV", "ERROR", "FINISH",
    "FIXEDOVERFLOW", "FOFL", "INVALIDOP", "OVERFLOW", "OFL", "SIZE", "STORAGE", "STRINGRANGE", "STRG",
    "STRINGSIZE", "STRZ", "SUBSCRIPTRANGE", "SUBRG", "UNDERFLOW", "UFL", "ZERODIVIDE", "ZDIV",
}  # fmt: skip
_PLI_FILE_CONDITIONS = {"ENDFILE", "ENDPAGE", "KEY", "NAME", "RECORD", "TRANSMIT", "UNDEFINEDFILE", "UNDF",
                        "CONDITION", "COND"}  # fmt: skip


def _pli_condition_at(stmt: list, i: int) -> tuple[Optional[str], int]:
    """(the condition written at stmt[i], the index after it) or (None, i)."""
    if i >= len(stmt) or stmt[i][0] != "word":
        return None, i
    word = stmt[i][1]
    if word in _PLI_FILE_CONDITIONS and i + 1 < len(stmt) and stmt[i + 1][1] == "(":
        end = _pli_group(stmt, i + 1)
        return word + "".join(t[1] for t in stmt[i + 1 : end]), end
    if word in _PLI_BARE_CONDITIONS and not (i + 1 < len(stmt) and stmt[i + 1][1] == "("):
        return word, i + 1
    return None, i


def pli_on_rows(text: str) -> list[dict[str, Any]]:
    """Every ON / REVERT / SIGNAL statement of one PL/I source (see above)."""
    rows = []
    for stmt in _pli_statements(_pli_token_stream(_pli_source_lines(text))):
        for i in _pli_clause_starts(stmt):
            word = stmt[i][1] if stmt[i][0] == "word" else None
            if word not in ("ON", "REVERT", "SIGNAL"):
                continue
            cond, j = _pli_condition_at(stmt, i + 1)
            if cond is None:
                continue
            base = {"source": "PLI", "verb": word, "condition": cond, "target": None, "target_kind": None,
                    "resp_var": None, "attributes": None, "line": stmt[i][2]}  # fmt: skip
            if word != "ON":
                rows.append(dict(base, kind=word))
                continue
            snap = j < len(stmt) and stmt[j][1] == "SNAP"
            j += 1 if snap else 0
            rest = [t[1] for t in stmt[j:]]
            target, kind = None, "STATEMENT"
            if not rest:
                kind = "NULL"
            elif rest == ["SYSTEM"]:
                kind = "SYSTEM"
            elif rest[0] == "BEGIN":
                kind = "BLOCK"
            elif rest[0] == "CALL" and len(rest) > 1:
                target, kind = rest[1], "PROCEDURE"
            elif rest[:2] == ["GO", "TO"] and len(rest) > 2:
                target, kind = rest[2], "LABEL"
            elif rest[0] == "GOTO" and len(rest) > 1:
                target, kind = rest[1], "LABEL"
            rows.append(
                dict(base, kind="ON_UNIT", target=target, target_kind=kind, attributes="SNAP" if snap else None)
            )
    return rows


def draft_uow(repo: Path) -> dict[str, dict[str, Any]]:
    """Drafted units of work and handlers for every COBOL, HLASM and PL/I source (#3453,
    #3495, #3491). Adjudicates nothing until signed off with `uow_validated`."""
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(repo.rglob("*")):
        if p.is_file() and p.suffix.lower() in CICS_EXTS + HLASM_EXTS + PLI_EXTS and ".git" not in p.parts:
            rows = uow_handler_ops(p)
            if rows:
                out[p.relative_to(repo).as_posix()] = {
                    "rows": rows,
                    "uow_validated": False,
                    "verification": {"status": "draft", "notes": []},
                }
    return out


def draft_tdq_triggers(repo: Path) -> dict[str, dict[str, Any]]:
    """#3453 add-on: per writing program, the transactions CICS starts because a
    TD queue it writes carries TRIGGERLEVEL + TRANSID in the CSD, as
    `QUEUE -> TRANSID -> PROGRAM` (this tool's CSD, WRITEQ and transaction reads)."""
    triggered: dict[str, str] = {}
    programs: dict[str, str] = {}
    for p in sorted(repo.rglob("*")):
        if not p.is_file() or ".git" in p.parts or p.suffix.lower() not in CSD_EXTS + JCL_EXTS:
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        if not is_csd_deck(p, text):
            continue
        for r in csd_resource_definitions(text):
            if r["resource_type"] == "TDQUEUE" and r["transid"]:
                triggered[r["name"]] = r["transid"]
        for transid, program in _csd_pairs(text):
            programs.setdefault(transid, program)
    out: dict[str, dict[str, Any]] = {}
    if not triggered:
        return out
    for p in sorted(repo.rglob("*")):
        if not (p.is_file() and p.suffix.lower() in CICS_EXTS and ".git" not in p.parts):
            continue
        starts = set()
        for r in cics_resource_ops(p):
            if r["kind"] != "QUEUE" or r["access"] != "write" or r["qualifier"] != "TD":
                continue
            names = {r["name"].upper()} if r["name"] else set((r["candidates"] or "").upper().split(",")) - {""}
            for q in names & set(triggered):
                starts.add(f"{q} -> {triggered[q]} -> {programs.get(triggered[q], '?')}")
        if starts:
            out[p.relative_to(repo).as_posix()] = {
                "starts": sorted(starts),
                "tdq_triggers_validated": False,
                "verification": {"status": "draft", "notes": []},
            }
    return out


# ==============================================================================
# File definitions: FILE-CONTROL SELECTs and IDCAMS defines (#3455)
# ==============================================================================
# This tool's own reading. A SELECT is read from the key's Source (Area A..B,
# comments dropped) between FILE-CONTROL and the next division / I-O-CONTROL, one
# sentence per SELECT, clause by clause over its words. An FD's COPY members are
# the COPYs between `FD name` and the next FD / SD / section. IDCAMS DEFINE
# CLUSTER / AIX / PATH are read from JCL in-stream lines (continuation `-`),
# each parameter by its own regex.
_FC_WORD = re.compile(r"'[^']*'|\"[^\"]*\"|[A-Z0-9][A-Z0-9-]*")


def file_control_rows(path: Path) -> list[dict[str, Any]]:
    src = Source(path)
    text = src.text
    fc = re.search(r"\bFILE-CONTROL\s*\.", text)
    if not fc:
        return []
    end = re.search(r"\b(?:I-O-CONTROL|DATA\s+DIVISION|PROCEDURE\s+DIVISION)\b", text[fc.end() :])
    region = src.raw_text[fc.end() : fc.end() + end.start() if end else len(text)]
    copies: dict[str, list[str]] = {}
    for fd in re.finditer(r"\b[FS]D\s+([A-Z0-9][A-Z0-9-]*)", text):
        stop = re.search(
            r"\b(?:[FS]D\s|WORKING-STORAGE|LOCAL-STORAGE|LINKAGE\s+SECTION|PROCEDURE\s+DIVISION)", text[fd.end() :]
        )
        chunk = src.raw_text[fd.end() : fd.end() + stop.start() if stop else len(text)]
        for m in re.finditer(r"\bCOPY\s+['\"]?([A-Z0-9@#$][A-Z0-9@#$-]*)", chunk):
            if m.group(1) not in copies.setdefault(fd.group(1), []):
                copies[fd.group(1)].append(m.group(1))
    rows = []
    for m in re.finditer(r"\bSELECT\b", region):
        sentence = region[m.end() :]
        stop = re.search(r"\.(?=\s|$)", re.sub(r"'[^']*'|\"[^\"]*\"", lambda q: "x" * len(q.group(0)), sentence))
        words = [w for w in _FC_WORD.findall(sentence[: stop.start() if stop else len(sentence)])]
        nxt = next((i for i, w in enumerate(words) if w == "SELECT"), None)
        words = words[:nxt] if nxt is not None else words
        if words and words[0] == "OPTIONAL":
            words = words[1:]
        if not words:
            continue
        r: dict[str, Any] = {"select": words[0], "assign": None, "org": None, "access": None, "key": None}
        r.update({"alt": [], "rel": None, "status": None, "line": src.line_of(fc.end() + m.start())})

        def val(i: int) -> Optional[str]:
            while i < len(words) and words[i] in ("IS", "ARE", "MODE", "KEY", "TO", "USING"):
                i += 1
            return words[i] if i < len(words) else None

        for i, w in enumerate(words[1:], 1):
            prev = words[i - 1]
            if w == "ASSIGN":
                r["assign"] = (val(i + 1) or "").strip("'\"") or None
            elif w == "ORGANIZATION":
                v = val(i + 1)
                j = words.index(v, i + 1) if v in words[i + 1 :] else i
                r["org"] = (
                    "LINE SEQUENTIAL" if v == "LINE" and j + 1 < len(words) and words[j + 1] == "SEQUENTIAL" else v
                )
            elif (
                w in ("INDEXED", "RELATIVE", "SEQUENTIAL")
                and r["org"] is None
                and prev not in ("IS", "MODE", "ACCESS", "ORGANIZATION", "LINE")
            ):
                r["org"] = w
            elif w == "ACCESS":
                r["access"] = val(i + 1)
            elif w == "RECORD" and prev != "ALTERNATE" and i + 1 < len(words) and words[i + 1] in ("KEY", "IS"):
                r["key"] = val(i + 1)
            elif w == "ALTERNATE":
                j = i + 1 + (1 if i + 1 < len(words) and words[i + 1] == "RECORD" else 0)
                name = val(j)
                k = words.index(name, j) + 1 if name in words[j:] else j
                dup = "DUPLICATES" in words[k : k + 2]
                if name:
                    r["alt"].append(name + ("+DUP" if dup else ""))
            elif w == "RELATIVE" and i + 1 < len(words) and words[i + 1] in ("KEY", "IS"):
                r["rel"] = val(i + 1)
            elif w == "STATUS":
                r["status"] = val(i + 1)
        r["copies"] = copies.get(r["select"], [])
        rows.append(r)
    return rows


def file_control_keys(rows: list[dict[str, Any]]) -> set[str]:
    """`L<line> SELECT X ASSIGN=.. ORG=.. ACCESS=.. KEY=.. ALT=.. REL=.. STATUS=.. COPY=..` per SELECT."""

    def d(v: Any) -> str:
        return (",".join(v) if isinstance(v, list) else str(v)) if v else "-"

    return {
        f"L{r['line']} SELECT {r['select']} ASSIGN={d(r['assign'])} ORG={d(r['org'])} ACCESS={d(r['access'])} "
        f"KEY={d(r['key'])} ALT={d(r['alt'])} REL={d(r['rel'])} STATUS={d(r['status'])} COPY={d(r['copies'])}"
        for r in rows
    }


def engine_file_control_row(fc: Any) -> dict[str, Any]:
    return {
        "select": fc.select_name,
        "assign": fc.assign,
        "org": fc.organization,
        "access": fc.access_mode,
        "key": fc.record_key,
        "alt": [n + ("+DUP" if dup else "") for n, dup in fc.alternate_keys],
        "rel": fc.relative_key,
        "status": fc.file_status,
        "copies": fc.fd_copies,
        "line": fc.line,
    }


def vsam_define_rows(text: str) -> list[dict[str, Any]]:
    """IDCAMS DEFINE CLUSTER / AIX / PATH in one JCL member's in-stream data."""
    lines = text.split("\n")
    rows, step, i = [], None, 0
    verbs = r"(?:DEFINE|DEF|DELETE|DEL|LISTCAT|LISTC|REPRO|PRINT|ALTER|VERIFY|IF|SET|EXPORT|IMPORT|BLDINDEX|BIX)\b"
    while i < len(lines):
        line = lines[i]
        m = re.match(r"//([A-Z0-9@#$]+)\s+EXEC\b", line)
        if m:
            step = m.group(1)
        if line.startswith("//") or not re.match(r"\s*DEF(?:INE)?\s", line):
            i += 1
            continue
        first, body = i + 1, []
        while i < len(lines):
            part = re.sub(r"/\*.*?\*/", " ", lines[i][:72].rstrip())
            if len(body) and (part.startswith("//") or part.startswith("/*") or re.match(r"\s*" + verbs, part)):
                break
            body.append(part.rstrip("-+"))
            i += 1
            if not part.endswith(("-", "+")):
                break
        cmd = " ".join(body)
        kind = re.match(r"\s*DEF(?:INE)?\s+(CLUSTER|CL|ALTERNATEINDEX|AIX|PATH)\b", cmd)
        if not kind:
            continue
        k = {"CLUSTER": "CLUSTER", "CL": "CLUSTER", "ALTERNATEINDEX": "AIX", "AIX": "AIX", "PATH": "PATH"}[
            kind.group(1)
        ]
        own = cmd[kind.end() :]
        # The object's own parameter block ends before DATA( / INDEX(.
        own = re.split(r"\)\s*(?:DATA|INDEX)\s*\(", own)[0]

        def one(*names: str) -> Optional[str]:
            for n in names:
                m2 = re.search(rf"\b{n}\s*\(\s*([^()]*?)\s*\)", own)
                if m2:
                    return m2.group(1)
            return None

        def nums(v: Optional[str]) -> list[int]:
            return [int(x) for x in re.findall(r"\d+", v or "")]

        keys, rec = nums(one("KEYS")), nums(one("RECORDSIZE", "RECSZ"))
        org = next((w for w in ("NONINDEXED", "NUMBERED", "LINEAR", "INDEXED") if re.search(rf"\b{w}\b", own)), None)
        uniq = (
            "NONUNIQUE"
            if re.search(r"\b(?:NONUNIQUEKEY|NUNQK)\b", own)
            else ("UNIQUE" if re.search(r"\b(?:UNIQUEKEY|UNQK)\b", own) else None)
        )
        upg = (
            "NOUPGRADE"
            if re.search(r"\b(?:NOUPGRADE|NUPG)\b", own)
            else ("UPGRADE" if re.search(r"\b(?:UPGRADE|UPG)\b", own) else None)
        )
        rows.append(
            {
                "kind": k,
                "name": one("NAME"),
                "org": org,
                "keys": keys[:2] or None,
                "rec": rec[:2] or None,
                "related": one("RELATE", "PATHENTRY", "PENT"),
                "unique": uniq if k == "AIX" else None,
                "upgrade": upg if k == "AIX" else None,
                "step": step,
                "line": first,
            }
        )
    return rows


def vsam_define_keys(rows: list[dict[str, Any]]) -> set[str]:
    """`L<line> KIND NAME ORG=.. KEYS=l,o REC=a,m REL=.. UNIQ=.. UPG=.. STEP=..` per define."""

    def d(v: Any) -> str:
        return ",".join(str(x) for x in v) if isinstance(v, list) else (str(v) if v else "-")

    return {
        f"L{r['line']} {r['kind']} {d(r['name'])} ORG={d(r['org'])} KEYS={d(r['keys'])} REC={d(r['rec'])} "
        f"REL={d(r['related'])} UNIQ={d(r['unique'])} UPG={d(r['upgrade'])} STEP={d(r['step'])}"
        for r in rows
    }


def engine_vsam_row(v: Any) -> dict[str, Any]:
    return {
        "kind": v.kind,
        "name": v.name,
        "org": v.organization,
        "keys": [x for x in (v.key_length, v.key_offset) if x is not None] or None,
        "rec": [x for x in (v.record_avg, v.record_max) if x is not None] or None,
        "related": v.related,
        "unique": v.unique_key,
        "upgrade": v.upgrade,
        "step": v.step,
        "line": v.line,
    }


def draft_file_defs(repo: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """(file_control, vsam_defines) sections, drafted (#3455)."""
    fc: dict[str, dict[str, Any]] = {}
    vd: dict[str, dict[str, Any]] = {}
    for p in sorted(repo.rglob("*")):
        if not p.is_file() or ".git" in p.parts:
            continue
        rel = p.relative_to(repo).as_posix()
        if p.suffix.lower() in PROGRAM_EXTS:
            rows = file_control_rows(p)
            if rows:
                fc[rel] = {
                    "selects": rows,
                    "file_control_validated": False,
                    "verification": {"status": "draft", "notes": []},
                }
        elif p.suffix.lower() in JCL_EXTS:
            text = "\n".join(
                "" if line.startswith("//*") else line
                for line in p.read_text(encoding="utf-8", errors="ignore").split("\n")
            )
            rows = vsam_define_rows(text.upper())
            if rows:
                vd[rel] = {"defines": rows, "vsam_validated": False, "verification": {"status": "draft", "notes": []}}
    return fc, vd


# ==============================================================================
# JCL job flow (#3451)
# ==============================================================================
# This tool's own reading of a JCL member: `//` statements joined across comma
# continuations (a dotted override name kept), IF ... THEN / ELSE / ENDIF
# tracked as a stack, and per statement the operands this reader needs pulled
# out by its own depth-aware operand scan. Same contract as core/job_flow.py.
def _jf_operand(field: str, key: str) -> Optional[str]:
    depth, quote, i = 0, False, 0
    starts = [0]
    for j, ch in enumerate(field):
        if ch == "'":
            quote = not quote
        elif not quote and ch == "(":
            depth += 1
        elif not quote and ch == ")":
            depth -= 1
        elif not quote and depth == 0 and ch == ",":
            starts.append(j + 1)
    for n, st in enumerate(starts):
        end = starts[n + 1] - 1 if n + 1 < len(starts) else len(field)
        piece = field[st:end]
        if piece.upper().startswith(key + "="):
            return piece[len(key) + 1 :]
    return None


def job_flow_rows(text: str) -> list[dict[str, Any]]:
    stmts: list[list] = []
    open_stmt = None
    for no, raw in enumerate(text.split("\n"), 1):
        line = raw[:72].rstrip()
        if not line.strip() or line.startswith("//*"):
            continue  # a comment inside a continued statement does not end it
        if not line.startswith("//"):
            open_stmt = None
            continue
        m = re.match(r"//(\S*)\s+(JOB|EXEC|DD|PROC|PEND|IF|ELSE|ENDIF|SET|INCLUDE|JCLLIB|OUTPUT)\b\s*(.*)", line)
        if m:
            rest = m.group(3)
            if m.group(2) == "IF":
                stmts.append([no, m.group(1), "IF", " ".join(re.split(r"\sTHEN\b", rest)[0].split())])
                open_stmt = None
                continue
            field = re.match(r"(?:'[^']*'|[^\s'])*", rest).group(0)
            stmts.append([no, m.group(1), m.group(2), field])
            open_stmt = stmts[-1] if field.endswith(",") else None
        elif open_stmt is not None:
            more = re.match(r"(?:'[^']*'|[^\s'])*", line[2:].strip()).group(0)
            open_stmt[3] += more
            if not more.endswith(","):
                open_stmt = None
    rows: list[dict[str, Any]] = []
    proc, n, step, last, ifs = None, 0, None, None, []
    for no, name, op, field in stmts:
        if op == "JOB":
            rows.append({"kind": "JOB", "name": name or None, "cond": _jf_operand(field, "COND"), "line": no})
            proc, n, step = None, 0, None
        elif op == "PROC":
            proc, n, step = name or "PROC", 0, None
        elif op == "PEND":
            proc, n, step = None, 0, None
        elif op == "IF":
            ifs.append(field)
        elif op == "ELSE" and ifs:
            ifs[-1] = "NOT " + ifs[-1]
        elif op == "ENDIF" and ifs:
            ifs.pop()
        elif op == "EXEC":
            n += 1
            step, last = name or None, None
            pgm = _jf_operand(field, "PGM")
            called = _jf_operand(field, "PROC")
            if not pgm and not called:
                first = field.split(",")[0]
                called = first if first and "=" not in first else None
            rows.append(
                {
                    "kind": "STEP",
                    "ord": n,
                    "step": step,
                    "pgm": pgm,
                    "proc": called,
                    "cond": _jf_operand(field, "COND"),
                    "if": " AND ".join(ifs) or None,
                    "in": proc,
                    "line": no,
                }
            )
        elif op == "DD":
            st, dd = name.split(".", 1) if "." in name else (step, name)
            last = dd or last
            dsn = _jf_operand(field, "DSN") or _jf_operand(field, "DSNAME")
            if not dsn:
                continue
            gen = re.search(r"\(([+-]?\d+)\)$", dsn)
            g = None
            if gen:
                v = int(gen.group(1))
                g = f"+{v}" if v > 0 else str(v)
                dsn = dsn[: gen.start()]
            disp = _jf_operand(field, "DISP")
            status = (disp.strip("()").split(",")[0] or "NEW") if disp is not None else "NEW"
            rows.append(
                {
                    "kind": "DD",
                    "step": st,
                    "dd": dd or last,
                    "dsn": dsn,
                    "disp": status,
                    "gen": g,
                    "in": proc,
                    "line": no,
                }
            )
    return rows


def job_flow_keys(rows: list[dict[str, Any]]) -> set[str]:
    """One unit per JOB / STEP / DD row (`L<line> KIND ...` with every field)."""

    def d(v: Any) -> str:
        return str(v) if v not in (None, "") else "-"

    out = set()
    for r in rows:
        if r["kind"] == "JOB":
            out.add(f"L{r['line']} JOB {d(r['name'])} COND={d(r['cond'])}")
        elif r["kind"] == "STEP":
            out.add(
                f"L{r['line']} STEP {r['ord']} {d(r['step'])} PGM={d(r['pgm'])} PROC={d(r['proc'])} "
                f"COND={d(r['cond'])} IF={d(r['if'])} IN={d(r['in'])}"
            )
        else:
            out.add(
                f"L{r['line']} DD {d(r['step'])}.{d(r['dd'])} DSN={d(r['dsn'])} DISP={d(r['disp'])} GEN={d(r['gen'])} IN={d(r['in'])}"
            )
    return out


def engine_job_flow_row(j: Any) -> dict[str, Any]:
    if j.kind == "JOB":
        return {"kind": "JOB", "name": j.name, "cond": j.cond, "line": j.line}
    if j.kind == "STEP":
        return {
            "kind": "STEP",
            "ord": j.step_ordinal,
            "step": j.step_name,
            "pgm": j.program,
            "proc": j.proc,
            "cond": j.cond,
            "if": j.if_cond,
            "in": j.in_proc,
            "line": j.line,
        }
    return {
        "kind": "DD",
        "step": j.step_name,
        "dd": j.dd_name,
        "dsn": j.dsn,
        "disp": j.disp,
        "gen": j.generation,
        "in": j.in_proc,
        "line": j.line,
    }


def draft_job_flow(repo: Path) -> dict[str, dict[str, Any]]:
    """Drafted job flow for every JCL member (#3451); `jobflow_validated` signs it off."""
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(repo.rglob("*")):
        if p.is_file() and p.suffix.lower() in JCL_EXTS and ".git" not in p.parts:
            rows = job_flow_rows(p.read_text(encoding="utf-8", errors="ignore").upper())
            if rows:
                out[p.relative_to(repo).as_posix()] = {
                    "rows": rows,
                    "jobflow_validated": False,
                    "verification": {"status": "draft", "notes": []},
                }
    return out


# ==============================================================================
# Batch CALL USING contracts (#3454)
# ==============================================================================
# This tool's own reading of each CALL's USING list and each program's PROCEDURE
# DIVISION / ENTRY 'X' USING parameters, over the key's Source (Area A..B, so no
# sequence fields; literals found through the blanked twin). Arguments by
# position: BY CONTENT / BY VALUE prefix the items that follow (`CONTENT:X`),
# `A OF B` kept, subscripts dropped, ADDRESS OF / LENGTH OF / OMITTED / literals
# as written. The list stops at RETURNING, ON, NOT, END-CALL, a period, or a verb.
_CU_STOP = {"RETURNING", "ON", "NOT", "END-CALL", "EXCEPTION", "OVERFLOW", "GIVING"}
_CU_VERBS = set(
    "ACCEPT ADD ALTER CALL CANCEL CLOSE COMPUTE CONTINUE DELETE DISPLAY DIVIDE ELSE END-EVALUATE END-IF "
    "END-PERFORM END-READ END-SEARCH END-STRING EVALUATE EXEC EXIT GO GOBACK IF INITIALIZE INSPECT MERGE "
    "MOVE MULTIPLY OPEN PERFORM READ RELEASE RETURN REWRITE SEARCH SET SORT START STOP STRING SUBTRACT "
    "UNSTRING WHEN WRITE COPY".split()
)


def _cu_list(raw: str) -> Optional[str]:
    words = re.findall(r"'[^']*'|\"[^\"]*\"|[A-Z0-9][A-Z0-9-]*|[(),.]", raw)
    if not words or words[0] != "USING":
        return None
    out, mode, i = [], "", 1
    while i < len(words):
        w = words[i]
        if w == "." or w in _CU_STOP or w in _CU_VERBS:
            break
        if w == ",":
            i += 1
        elif w == "BY" and i + 1 < len(words) and words[i + 1] in ("REFERENCE", "CONTENT", "VALUE"):
            mode = "" if words[i + 1] == "REFERENCE" else words[i + 1] + ":"
            i += 2
        elif w in ("REFERENCE", "CONTENT", "VALUE"):
            mode = "" if w == "REFERENCE" else w + ":"
            i += 1
        elif w in ("ADDRESS", "LENGTH") and i + 2 < len(words) and words[i + 1] == "OF":
            out.append(f"{mode}{w} OF {words[i + 2]}")
            i += 3
        elif w == "OMITTED" or w[0] in "'\"":
            out.append(mode + w)
            i += 1
        elif w in ("(", ")"):
            i += 1
        else:
            name, i = w, i + 1
            while i + 1 < len(words) and words[i] in ("OF", "IN"):
                name, i = f"{name} OF {words[i + 1]}", i + 2
            if i < len(words) and words[i] == "(":
                depth = 0
                while i < len(words):
                    depth += (words[i] == "(") - (words[i] == ")")
                    i += 1
                    if depth == 0:
                        break
            out.append(mode + name)
    return ",".join(out) or None


def call_using_rows(path: Path) -> list[dict[str, Any]]:
    """CALL sites with a USING list, and entry points with parameters (or ENTRY)."""
    src = Source(path)
    rows = []
    for m in re.finditer(r"\bCALL\s+(?:'([^']*)'|\"([^\"]*)\"|([A-Z][A-Z0-9-]*))", src.text):
        # The literal's text is blanked in src.text; read it from raw_text.
        raw_target = re.match(r"CALL\s+(?:'([^']*)'|\"([^\"]*)\"|([A-Z][A-Z0-9-]*))", src.raw_text[m.start() :])
        if raw_target is None:
            continue
        target = (raw_target.group(1) or raw_target.group(2) or raw_target.group(3) or "").strip()
        args = _cu_list(src.raw_text[m.start() + raw_target.end() : m.start() + raw_target.end() + 6000])
        if args:
            rows.append({"kind": "CALL", "name": target, "args": args, "line": src.line_of(m.start())})
    for m in re.finditer(r"\bPROCEDURE\s+DIVISION\b", src.text):
        params = _cu_list(src.raw_text[m.end() : m.end() + 6000].lstrip())
        if params:
            rows.append({"kind": "PROCEDURE", "name": None, "args": params, "line": src.line_of(m.start())})
    for m in re.finditer(r"\bENTRY\s+(?:'([^']*)'|\"([^\"]*)\")", src.raw_text):
        if src.text[m.start() : m.start() + 5] != "ENTRY":
            continue
        rows.append(
            {
                "kind": "ENTRY",
                "name": (m.group(1) or m.group(2) or "").strip(),
                "args": _cu_list(src.raw_text[m.end() : m.end() + 6000].lstrip()),
                "line": src.line_of(m.start()),
            }
        )
    return rows


def call_using_keys(rows: list[dict[str, Any]]) -> set[str]:
    """`L<line> CALL|PROCEDURE|ENTRY <name> USING <args>` per row."""
    return {f"L{r['line']} {r['kind']} {r['name'] or '-'} USING {r['args'] or '-'}" for r in rows}


def engine_call_using_rows(ef: Any) -> list[dict[str, Any]]:
    rows = [
        {"kind": "CALL", "name": c.operand, "args": c.using_args, "line": c.line}
        for c in ef.calls
        if c.verb == "CALL" and c.using_args
    ]
    rows += [
        {"kind": e.kind, "name": e.entry_name, "args": e.params, "line": e.line}
        for e in ef.entry_points
        if e.params or e.kind == "ENTRY"
    ]
    return rows


def draft_call_using(repo: Path) -> dict[str, dict[str, Any]]:
    """Drafted CALL USING lists and entry-point parameters per COBOL source (#3454)."""
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(repo.rglob("*")):
        if p.is_file() and p.suffix.lower() in CICS_EXTS and ".git" not in p.parts:
            rows = call_using_rows(p)
            if rows:
                out[p.relative_to(repo).as_posix()] = {
                    "rows": rows,
                    "call_using_validated": False,
                    "verification": {"status": "draft", "notes": []},
                }
    return out


# ==============================================================================
# IMS DL/I calls (#3450)
# ==============================================================================
# This tool's own reading: EXEC DLI blocks through the CICS section's option
# regex, CALL 'CBLTDLI' arguments through the CALL USING reader above. For the
# segment matrix it resolves, on its own, a CBLTDLI function operand and each SSA:
# the data item is looked up in the program and then in every copybook the
# program COPYs (matched by file stem), and a group's load-time text is its
# elementary children's VALUEs, each padded / cut to its PIC width.
_DLI_EXEC = re.compile(r"\bEXEC\s+DLI\b")
_DLI_ACCESS = {"GU": "read", "GHU": "read", "GN": "read", "GHN": "read", "GNP": "read", "GHNP": "read",
               "ISRT": "insert", "REPL": "update", "DLET": "delete"}  # fmt: skip


def _dli_width(pic: str, usage: str) -> Optional[int]:
    body = pic.upper().lstrip("S")
    n = 0
    for ch, rep in re.findall(r"([9XAV])(?:\((\d+)\))?", body):
        n += 0 if ch == "V" else int(rep or 1)
    if not n:
        return None
    u = usage.upper()
    if "COMP-3" in u or "PACKED" in u:
        return n // 2 + 1
    if re.search(r"\b(?:COMP|BINARY|COMP-4|COMP-5)\b", u):
        return 2 if n <= 4 else 4 if n <= 9 else 8
    return n


def _dli_sources(path: Path, repo: Path) -> list[list[str]]:
    """The program's code lines, then each COPYd member's (by file stem)."""
    src = Source(path)
    out = [[a for _, a in src.lines]]
    stems = {}
    for p in repo.rglob("*"):
        if p.is_file() and p.suffix.lower() in COPYBOOK_EXTS and ".git" not in p.parts:
            stems.setdefault(p.stem.upper(), []).append(p)
    for member in re.findall(r"\bCOPY\s+([A-Z0-9@#$-]+)", src.text):
        for cb in stems.get(member, [])[:1]:
            out.append([a for _, a in Source(cb).lines])
    return out


def _dli_value(path: Path, repo: Path, name: str) -> Optional[str]:
    for lines in _dli_sources(path, repo):
        for i, line in enumerate(lines):
            m = re.match(rf"\s*(\d+)\s+{re.escape(name)}(?![A-Z0-9-])(.*)", line)
            if not m:
                continue
            level = int(m.group(1))
            entries = [m.group(2)]
            j = i + 1
            while j < len(lines) and not re.match(r"\s*\d+\s", lines[j]):
                entries[-1] += " " + lines[j]
                j += 1
            kids = []
            while j < len(lines):
                k = re.match(r"\s*(\d+)\s+([A-Z0-9-]+)(.*)", lines[j])
                if k and int(k.group(1)) <= level and int(k.group(1)) not in (66, 88):
                    break
                if k:
                    kids.append([int(k.group(1)), k.group(3)])
                elif kids:
                    kids[-1][1] += " " + lines[j]
                j += 1

            def text_of(desc: str) -> Optional[str]:
                pic = re.search(r"\bPIC(?:TURE)?\s+(?:IS\s+)?(\S+?)\.?(?:\s|$)", desc)
                if not pic:
                    return ""  # a group line
                w = _dli_width(pic.group(1), desc)
                if w is None:
                    return None
                v = re.search(r"\bVALUE\s+(?:IS\s+)?(?:'([^']*)'|\"([^\"]*)\"|(SPACES?|ZEROE?S?))", desc)
                if not v:
                    return "?" * w
                lit = v.group(1) if v.group(1) is not None else v.group(2)
                if lit is None:
                    lit = (" " if v.group(3).startswith("SPACE") else "0") * w
                return lit.ljust(w)[:w]

            if not kids:
                return text_of(entries[0])
            parts = []
            for lvl, desc in kids:
                if lvl in (66, 88) or re.search(r"\bREDEFINES\b", desc):
                    continue
                t = text_of(desc)
                if t is None:
                    return "".join(parts) or None
                parts.append(t)
            return "".join(parts)
    return None


def dli_rows(path: Path) -> list[dict[str, Any]]:
    src = Source(path)
    rows = []
    for m in _DLI_EXEC.finditer(src.text):
        end = _CICS_END.search(src.text, m.end())
        body = src.raw_text[m.end() : end.start() if end else len(src.raw_text)]
        opts = [
            (o.group(1), " ".join(o.group(2)[1:-1].split()) if o.group(2) else None)
            for o in _CICS_OPTION.finditer(body)
        ]
        if not opts or opts[0][1] is not None:
            continue
        rest = [(k, v) for k, v in opts[1:] if k != "USING"]
        d = dict(rest)
        psb = d.get("PSB")
        while psb and psb.startswith("(") and psb.endswith(")"):
            psb = psb[1:-1].strip()
        rows.append({
            "interface": "EXEC", "function": opts[0][0], "operand": None, "pcb": d.get("PCB"),
            "io": d.get("INTO") or d.get("FROM"), "segs": [v for k, v in rest if k == "SEGMENT" and v],
            "where": [v for k, v in rest if k == "WHERE" and v], "psb": psb, "line": src.line_of(m.start()),
        })  # fmt: skip
    for m in re.finditer(r"\bCALL\s+'(?:CBLTDLI|AIBTDLI)'", src.raw_text):
        if src.text[m.start() : m.start() + 4] != "CALL":
            continue
        args = (_cu_list(src.raw_text[m.end() : m.end() + 6000].lstrip()) or "").split(",")
        args = [a for a in args if a]
        rows.append({
            "interface": "CALL", "function": None, "operand": args[0] if args else None,
            "pcb": args[1] if len(args) > 1 else None, "io": args[2] if len(args) > 2 else None,
            "segs": args[3:], "where": [], "psb": None, "line": src.line_of(m.start()),
        })  # fmt: skip
    rows.sort(key=lambda r: r["line"])
    return rows


def dli_keys(rows: list[dict[str, Any]]) -> set[str]:
    """`L<line> EXEC|CALL FN=.. PCB=.. IO=.. SEG=.. WHERE=.. PSB=..` per call (operands as written)."""

    def d(v: Any) -> str:
        return (",".join(v) if isinstance(v, list) else str(v)) if v else "-"

    return {
        f"L{r['line']} {r['interface']} FN={d(r['function'] or r['operand'])} PCB={d(r['pcb'])} IO={d(r['io'])} "
        f"SEG={d(r['segs'])} WHERE={';'.join(r['where']) or '-'} PSB={d(r['psb'])}"
        for r in rows
    }


def engine_dli_row(c: Any) -> dict[str, Any]:
    segs = (c.segments or c.ssas or "").split(",") if (c.segments or c.ssas) else []
    return {
        "interface": c.interface, "function": c.function, "operand": c.function_operand, "pcb": c.pcb,
        "io": c.io_area, "segs": segs, "where": (c.where or "").split(";") if c.where else [], "psb": c.psb,
        "line": c.line,
    }  # fmt: skip


def dli_access(path: Path, repo: Path, rows: list[dict[str, Any]]) -> list[str]:
    """`access SEGMENT` for the program, this tool's own resolution (path calls act
    on their last segment and read the parents)."""
    found = set()
    for r in rows:
        fn = r["function"]
        if r["interface"] == "CALL" and r["operand"]:
            v = _dli_value(path, repo, r["operand"])
            fn = v.strip() if v and "?" not in v else None
        acc = _DLI_ACCESS.get(fn or "")
        if not acc:
            continue
        segs = r["segs"] if r["interface"] == "EXEC" else []
        if r["interface"] == "CALL":
            for ssa in r["segs"]:
                v = _dli_value(path, repo, ssa) or ""
                if v[:8].strip() and "?" not in v[:8]:
                    segs.append(v[:8].strip())
        for i, seg in enumerate(segs):
            found.add(f"{acc if i == len(segs) - 1 else 'read'} {seg.upper()}")
    return sorted(found)


def draft_dli(repo: Path) -> dict[str, dict[str, Any]]:
    """Drafted DL/I calls and segment access per COBOL source (#3450)."""
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(repo.rglob("*")):
        if p.is_file() and p.suffix.lower() in CICS_EXTS and ".git" not in p.parts:
            rows = dli_rows(p)
            if rows:
                out[p.relative_to(repo).as_posix()] = {
                    "calls": rows,
                    "segment_access": dli_access(p, repo, rows),
                    "dli_validated": False,
                    "verification": {"status": "draft", "notes": []},
                }
    return out


# ==============================================================================
# IMS PSB / DBD definitions and the access check (#3477)
# ==============================================================================
# This tool's own reading of the generation macros: a statement is the columns
# 1-71 of its first line plus columns 16-71 of each line after a non-blank column
# 72; operands are walked with a paren-depth regex scan. A SENSEG / SEGM belongs
# to the PCB / DBD above it, an unlabeled PCB is `PCB@<line>`. JCL regions come
# from the job-flow statement reader. The access check joins, on its own, the
# program's PSB (DFSRRC00 PARM by PROGRAM-ID, or SCHD PSB through its VALUE) to
# the PCBs whose SENSEGs name the segment, and each access to the PROCOPT letters.
IMS_GEN_EXTS = (".psb", ".dbd")
_IMS_MACROS = ("PSBGEN", "PCB", "SENSEG", "DBD", "SEGM", "FIELD", "LCHILD", "DATASET")
_IMS_OPERAND = re.compile(r"([A-Z0-9]+)=((?:\([^()]*(?:\([^()]*\)[^()]*)*\)|[^,()\s])*)|([^,=\s]+)")


def _ims_ops(text: str) -> dict[str, str]:
    field = text.split()[0] if text.split() else ""
    return {m.group(1): m.group(2) for m in _IMS_OPERAND.finditer(field) if m.group(1)}


def _ims_name(v: Optional[str]) -> Optional[str]:
    names = re.findall(r"[A-Z0-9@#$]+", v or "")
    return names[0] if names else None


def ims_gen_rows(text: str) -> list[dict[str, Any]]:
    lines = text.upper().split("\n")
    stmts: list[tuple[int, str]] = []
    no = 0
    while no < len(lines):
        if lines[no].startswith("*") or not lines[no].strip():
            no += 1
            continue
        first, body = no, lines[no][:71].rstrip()
        while len(lines[no]) >= 72 and lines[no][71].strip() and no + 1 < len(lines):
            no += 1
            body += lines[no][15:71].rstrip()
        stmts.append((first + 1, body.rstrip()))
        no += 1
    rows: list[dict[str, Any]] = []
    pcb = dbd = seg = None
    for line, body in stmts:
        m = re.match(r"(\S*)\s+(\S+)\s*(.*)", body)
        if not m or m.group(2) not in _IMS_MACROS:
            continue
        label, op, o = m.group(1), m.group(2), _ims_ops(m.group(3))
        r: dict[str, Any] = {"kind": op, "line": line}
        if op == "PCB":
            pcb = label or o.get("PCBNAME") or f"PCB@{line}"
            r.update(name=pcb, type=o.get("TYPE"), dbd=o.get("DBDNAME") or o.get("NAME"), procopt=o.get("PROCOPT"))
        elif op == "SENSEG":
            r.update(
                name=_ims_name(o.get("NAME")), parent=_ims_name(o.get("PARENT")), owner=pcb, procopt=o.get("PROCOPT")
            )
        elif op == "PSBGEN":
            r.update(name=o.get("PSBNAME"))
        elif op == "DBD":
            dbd = o.get("NAME")
            r.update(name=dbd, access=_ims_name(o.get("ACCESS")))
        elif op == "SEGM":
            seg = _ims_name(o.get("NAME"))
            b = re.match(r"\(?(\d+)", o.get("BYTES", ""))
            r.update(name=seg, parent=_ims_name(o.get("PARENT")), owner=dbd, bytes=int(b.group(1)) if b else None)
        elif op == "FIELD":
            parts = re.findall(r"[A-Z0-9@#$]+", o.get("NAME", ""))
            r.update(
                name=parts[0] if parts else None, parent=seg, owner=dbd, access="SEQ" if "SEQ" in parts[1:] else None,
                start=int(o["START"]) if o.get("START", "").isdigit() else None,
                bytes=int(o["BYTES"]) if o.get("BYTES", "").isdigit() else None,
            )  # fmt: skip
        elif op == "LCHILD":
            parts = re.findall(r"[A-Z0-9@#$]+", o.get("NAME", ""))
            r.update(name=parts[0] if parts else None, parent=seg, owner=dbd, dbd=parts[1] if len(parts) > 1 else None)
        elif op == "DATASET":
            r.update(name=o.get("DD1"), owner=dbd)
        rows.append(r)
    return rows


def ims_region_rows(text: str) -> list[dict[str, Any]]:
    rows = []
    for line, _name, op, field in _jcl_key_statements(text.upper()):
        if op != "EXEC" or not re.search(r"\bPGM=DFSRRC00\b", field):
            continue
        parm = re.search(r"PARM=\(?'?([^')]*)", field)
        if parm:
            p = [x.strip() for x in parm.group(1).split(",")] + ["", "", ""]
            rows.append({"kind": "REGION", "access": p[0] or None, "name": p[1] or None, "program": p[1] or None,
                         "psb": p[2] or None, "line": line})  # fmt: skip
    return rows


_IMS_KEY_FIELDS = ("name", "parent", "owner", "dbd", "procopt", "type", "access", "bytes", "start", "psb", "program")


def ims_gen_keys(rows: list[dict[str, Any]]) -> set[str]:
    """`L<line> KIND name=.. parent=.. ...` per statement, set fields only."""
    return {
        f"L{r['line']} {r['kind']} " + " ".join(f"{k}={r[k]}" for k in _IMS_KEY_FIELDS if r.get(k) not in (None, ""))
        for r in rows
    }


def engine_ims_gen_row(g: Any) -> dict[str, Any]:
    return {
        "kind": g.kind, "line": g.line, "name": g.name, "parent": g.parent, "owner": g.owner, "dbd": g.dbd_name,
        "procopt": g.procopt, "type": g.pcb_type, "access": g.access, "bytes": g.bytes, "start": g.start,
        "psb": g.psb_name, "program": g.program,
    }  # fmt: skip


_IMS_PROCOPT = {"read": "G", "insert": "I", "update": "R", "delete": "D"}


def ims_access_check(
    repo: Path, gen: dict[str, dict[str, Any]], dli: dict[str, dict[str, Any]]
) -> dict[str, list[str]]:
    """Program -> `SEGMENT status PSB/PCB[:denied]...` per segment it accesses, from
    this tool's own IMS definition rows and DL/I segment access."""
    psbs: dict[str, list[dict[str, Any]]] = {}
    regions: dict[str, set[str]] = {}
    for entry in gen.values():
        rows = entry["rows"]
        name = next((r["name"] for r in rows if r["kind"] == "PSBGEN" and r.get("name")), None)
        if name:
            psbs[name] = [
                dict(r, sensegs={x["name"] for x in rows if x["kind"] == "SENSEG" and x.get("owner") == r["name"]})
                for r in rows if r["kind"] == "PCB"
            ]  # fmt: skip
        for r in rows:
            if r["kind"] == "REGION" and r.get("program") and r.get("psb"):
                regions.setdefault(r["program"], set()).add(r["psb"])
    out: dict[str, list[str]] = {}
    for rel, k in dli.items():
        path = repo / rel
        pid = re.search(r"PROGRAM-ID\.?\s+['\"]?([A-Z0-9@#$-]+)", Source(path).text)
        names = set(regions.get(pid.group(1), set())) if pid else set()
        for c in k.get("calls", []):
            if c.get("function") == "SCHD" and c.get("psb"):
                v = c["psb"] if c["psb"][0] in "'\"" else _dli_value(path, repo, c["psb"])
                if v and "?" not in v and v.strip(" '\""):
                    names.add(v.strip(" '\"").upper())
        by_seg: dict[str, set[str]] = {}
        for a in k.get("segment_access", []):
            acc, seg = a.split(" ", 1)
            by_seg.setdefault(seg, set()).add(acc)
        lines = []
        for seg, accs in sorted(by_seg.items()):
            hits = []
            for psb in sorted(names):
                for pcb in psbs.get(psb, []):
                    if seg in pcb["sensegs"]:
                        opt = pcb.get("procopt") or ""
                        bad = sorted(
                            a
                            for a in accs
                            if not ("A" in opt or _IMS_PROCOPT[a] in opt or (a == "insert" and "L" in opt))
                        )
                        hits.append((psb, pcb["name"], bad))
            if not any(n in psbs for n in names):
                status = "no_psb"
            elif not hits:
                status = "not_sensitive"
            elif all(b for _, _, b in hits):
                status = "denied"
            else:
                status = "ok"
            lines.append(
                f"{seg} {status} "
                + (",".join(f"{p}/{c}" + (":" + "+".join(b) if b else "") for p, c, b in hits) or "-")
            )
        out[rel] = lines
    return out


def engine_ims_check_lines(checks: list[dict[str, Any]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for c in checks:
        hits = ",".join(
            f"{p['psb']}/{p['pcb']}" + (":" + "+".join(p["denied"]) if p["denied"] else "") for p in c["pcbs"]
        )
        out.setdefault(c["file"], []).append(f"{c['segment']} {c['status']} {hits or '-'}")
    return out


def draft_ims_gen(repo: Path, dli: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Drafted IMS definitions per PSB / DBD / region JCL member, and the access
    check per DL/I program (#3477); `ims_gen_validated` signs it off."""
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(repo.rglob("*")):
        if not p.is_file() or ".git" in p.parts:
            continue
        ext = p.suffix.lower()
        if ext in IMS_GEN_EXTS:
            rows = ims_gen_rows(p.read_text(encoding="utf-8", errors="ignore"))
        elif ext in JCL_EXTS:
            rows = ims_region_rows(p.read_text(encoding="utf-8", errors="ignore"))
        else:
            continue
        if rows:
            out[p.relative_to(repo).as_posix()] = {
                "rows": rows,
                "ims_gen_validated": False,
                "verification": {"status": "draft", "notes": []},
            }
    for rel, lines in ims_access_check(repo, out, dli).items():
        out[rel] = {"access_check": lines, "ims_gen_validated": False, "verification": {"status": "draft", "notes": []}}
    return out


# ==============================================================================
# Field-level data movement (#3452)
# ==============================================================================
# This tool's own reading: statements are cut out of the literal-blanked
# procedure text between a data-moving verb and the next verb / END- word /
# period, then each verb's phrases are split by its keywords with regexes (the
# engine walks a token stream). Operands keep qualifiers, drop subscripts, and
# mark a reference modification `(:)`. Truncation uses this tool's own widths:
# PIC positions per usage, a group the sum of its children with COPY members
# spliced in, one occurrence of an OCCURS item.
_MV_VERBS = ("MOVE", "COMPUTE", "ADD", "SUBTRACT", "MULTIPLY", "DIVIDE", "STRING", "UNSTRING", "INITIALIZE")
_MV_ENDERS = (
    "ACCEPT ADD ALTER CALL CANCEL CLOSE COMPUTE CONTINUE DELETE DISPLAY DIVIDE ELSE EVALUATE EXEC EXIT GO "
    "GOBACK IF INITIALIZE INSPECT MERGE MOVE MULTIPLY OPEN PERFORM READ RELEASE RETURN REWRITE SEARCH SET "
    "SORT START STOP STRING SUBTRACT UNSTRING WHEN WRITE COPY OTHERWISE THEN NEXT NOT INVALID AT"
).split()
_MV_NAME = r"[A-Z0-9][A-Z0-9-]*"
_MV_PARENS = r"\((?:[^()]|\([^()]*\))*\)"
_MV_OPERAND = re.compile(
    r"(?P<lit>[XNGZ]?'[^']*'?|[XNGZ]?\"[^\"]*\"?)"
    rf"|(?P<cics>(?:DFHVALUE|DFHRESP)\s*\(\s*{_MV_NAME}\s*\))"
    rf"|(?P<fn>FUNCTION\s+{_MV_NAME}(?:\s*{_MV_PARENS})?)"
    rf"|(?P<lenof>(?:LENGTH|ADDRESS)\s+OF\s+{_MV_NAME}(?:\s+(?:OF|IN)\s+{_MV_NAME})*)"
    rf"|(?P<all>ALL\s+(?:'[^']*'|\"[^\"]*\"|{_MV_NAME}))"
    r"|(?P<num>[+-]?(?:\d*\.\d+|\d+)(?![A-Z0-9-]))"
    rf"|(?P<id>{_MV_NAME}(?:\s+(?:OF|IN)\s+{_MV_NAME})*)(?P<paren>(?:\s*{_MV_PARENS})*)"
)
_MV_FIGURATIVE = {"SPACE", "SPACES", "ZERO", "ZEROS", "ZEROES", "HIGH-VALUE", "HIGH-VALUES", "LOW-VALUE",
                  "LOW-VALUES", "QUOTE", "QUOTES", "NULL", "NULLS"}  # fmt: skip
_MV_SKIP = {"ROUNDED", "MODE", "IS", "NEAREST-AWAY-FROM-ZERO", "TRUNCATION"}


_MV_LITERAL = re.compile(r"[XNGZ]?'[^'\n]*'?|[XNGZ]?\"[^\"\n]*\"?")


def _mv_matches(text: str) -> list[re.Match]:
    """The operands of a list, in a row: separators are blanks and commas, and the
    first thing that is not an operand (`(SCRNVAR2)C`, pseudo-text awaiting COPY
    REPLACING) ends the list."""
    out, pos = [], 0
    while True:
        while pos < len(text) and text[pos] in " ,":
            pos += 1
        m = _MV_OPERAND.match(text, pos)
        if pos >= len(text) or not m or m.end() == pos:
            return out
        out.append(m)
        pos = m.end()


def _mv_operands(
    text: str, items_only: bool = False, lits: Optional[list] = None, scan: bool = False
) -> list[tuple[str, str, bool]]:
    """(text, kind, refmod) per operand of one phrase, qualifiers as `A OF B`.
    `lits` restores the literals `_mv_statement_pairs` parked as `'<n>'`; `scan`
    picks operands out of an arithmetic expression instead of reading a list."""
    out = []
    for m in _MV_OPERAND.finditer(text) if scan else _mv_matches(text):
        if m.group("lit") and lits is not None:
            out.append((lits[int(m.group("lit").strip("'"))], "literal", False))
        elif m.group("lit") or m.group("num"):
            out.append((m.group(0).strip(), "literal", False))
        elif m.group("cics"):
            # #3495 zECS pin: a CICS translator constant (DFHVALUE / DFHRESP), no data item.
            out.append(("".join(m.group("cics").split()), "cics_constant", False))
        elif m.group("fn"):
            out.append((" ".join(m.group("fn").split("(")[0].split()), "function", False))
        elif m.group("lenof"):
            words = m.group("lenof").split()
            out.append((" ".join(words).replace(" IN ", " OF "), words[0].lower(), False))
        elif m.group("all"):
            what = m.group("all").split(None, 1)[1]
            if lits is not None and what[:1] == "'":
                what = lits[int(what.strip("'"))]
            out.append((f"ALL {what}", "figurative", False))
        else:
            name = re.sub(r"\s+(?:OF|IN)\s+", " OF ", m.group("id"))
            if name in _MV_SKIP or not re.search(r"[A-Z]", name):
                continue
            if name in _MV_FIGURATIVE:
                out.append((name, "figurative", False))
                continue
            out.append((name, "item", ":" in (m.group("paren") or "")))
    return [o for o in out if o[1] == "item"] if items_only else out


def _mv_expression_items(text: str) -> list[tuple[str, str, bool]]:
    """Data names of an arithmetic expression: FUNCTION names dropped, arguments kept."""
    text = re.sub(rf"\bFUNCTION\s+{_MV_NAME}", " ", text)
    return _mv_operands(text, items_only=True, scan=True)


def _mv_statement_pairs(verb: str, body: str) -> list[tuple[Optional[tuple], tuple, bool]]:
    # Literals are parked as '<n>' first, so a keyword inside one ('FAILED TO READ')
    # never splits the statement.
    lits: list[str] = []

    def park(m: re.Match) -> str:
        lits.append(m.group(0))
        return f"'{len(lits) - 1}'"

    body = _MV_LITERAL.sub(park, body)

    def ops(text: str) -> list:
        return _mv_operands(text, False, lits)

    def cut(text: str, words: str) -> str:
        m = re.search(rf"(?<![A-Z0-9-])(?:{words})(?![A-Z0-9-])", text)
        return text[: m.start()] if m else text

    pairs: list = []
    if verb == "MOVE":
        m = re.match(r"\s*(CORR(?:ESPONDING)?\s+)?(.*?)(?<![A-Z0-9-])TO(?![A-Z0-9-])(.*)$", body, re.S)
        if not m:
            return []
        src = ops(m.group(2))
        if len(src) != 1:
            return []
        pairs = [(src[0], t, bool(m.group(1))) for t in ops(m.group(3))]
    elif verb == "COMPUTE":
        m = re.match(r"(.*?)(?:=|(?<![A-Z0-9-])EQUAL(?![A-Z0-9-]))(.*)$", body, re.S)
        if not m:
            return []
        rhs = cut(m.group(2), r"ON|NOT|SIZE|END-COMPUTE")
        pairs = [(a, t, False) for t in ops(m.group(1)) for a in _mv_expression_items(rhs)]
    elif verb in ("ADD", "SUBTRACT", "MULTIPLY", "DIVIDE"):
        body = cut(body, r"ON|NOT|SIZE|END-ADD|END-SUBTRACT|END-MULTIPLY|END-DIVIDE")
        if re.match(r"\s*CORR", body):
            return []
        rem = ""
        if re.search(r"(?<![A-Z0-9-])REMAINDER(?![A-Z0-9-])", body):
            body, rem = re.split(r"(?<![A-Z0-9-])REMAINDER(?![A-Z0-9-])", body, maxsplit=1)
        giving = ""
        if re.search(r"(?<![A-Z0-9-])GIVING(?![A-Z0-9-])", body):
            body, giving = re.split(r"(?<![A-Z0-9-])GIVING(?![A-Z0-9-])", body, maxsplit=1)
        halves = re.split(r"(?<![A-Z0-9-])(?:TO|FROM|BY|INTO)(?![A-Z0-9-])", body, maxsplit=1)
        first = ops(halves[0])
        second = ops(halves[1]) if len(halves) > 1 else []
        if giving:
            pairs = [(a, t, False) for t in ops(giving) + ops(rem) for a in first + second]
        else:
            pairs = [(a, t, False) for t in second for a in first]
    elif verb == "STRING":
        parts = re.split(r"(?<![A-Z0-9-])INTO(?![A-Z0-9-])", body, maxsplit=1)
        if len(parts) != 2:
            return []
        head = re.sub(
            rf"DELIMITED\s+(?:BY\s+)?(?:SIZE|'[^']*'|{_MV_NAME}(?:\s+(?:OF|IN)\s+{_MV_NAME})*)", " ", parts[0]
        )
        target = ops(cut(parts[1], r"WITH|POINTER|ON|NOT|END-STRING"))[:1]
        pairs = [(a, target[0], False) for a in ops(head)] if target else []
    elif verb == "UNSTRING":
        parts = re.split(r"(?<![A-Z0-9-])INTO(?![A-Z0-9-])", body, maxsplit=1)
        if len(parts) != 2:
            return []
        src = ops(cut(parts[0], "DELIMITED"))[:1]
        tail = cut(parts[1], r"WITH|POINTER|TALLYING|ON|NOT|END-UNSTRING")
        tail = re.sub(rf"(?:DELIMITER|COUNT)\s+(?:IN\s+)?{_MV_NAME}(?:\s*{_MV_PARENS})*", " ", tail)
        pairs = [(src[0], t, False) for t in ops(tail)] if src else []
    elif verb == "INITIALIZE":
        head = cut(body, r"REPLACING|WITH|ALL|TO|DEFAULT|FILLER")
        pairs = [(None, t, False) for t in ops(head)]
    return [p for p in pairs if p[1][1] == "item"]


_IO_VERBS = ("READ", "RETURN", "WRITE", "REWRITE", "RELEASE", "ACCEPT")  # #3492


def _io_statement_pairs(verb: str, body: str) -> list[tuple[Optional[tuple], tuple, bool]]:
    """#3492: READ / RETURN f ... INTO t (f's record -> t), WRITE / REWRITE /
    RELEASE r FROM s (s -> r), ACCEPT t [FROM w [w]] (w -> t, SYSIN when no FROM)."""
    lits: list[str] = []

    def park(m: re.Match) -> str:
        lits.append(m.group(0))
        return f"'{len(lits) - 1}'"

    body = _MV_LITERAL.sub(park, body)
    if verb in ("READ", "RETURN"):
        m = re.match(rf"\s*({_MV_NAME})\b.*?(?<![A-Z0-9-])INTO\s+(.*)$", body, re.S)
        t = _mv_operands(m.group(2), False, lits)[:1] if m else []
        return [((m.group(1), "file", False), t[0], False)] if m and t and t[0][1] == "item" else []
    if verb in ("WRITE", "REWRITE", "RELEASE"):
        m = re.match(rf"\s*({_MV_NAME})\s+FROM\s+(.*)$", body, re.S)
        src = _mv_operands(m.group(2), False, lits)[:1] if m else []
        return [(src[0], (m.group(1), "item", False), False)] if m and src else []
    m = re.match(rf"\s*({_MV_NAME}(?:\s+(?:OF|IN)\s+{_MV_NAME})*)(?:\s+FROM\s+(.*))?$", body, re.S)
    if not m:
        return []
    words = re.findall(_MV_NAME, m.group(2) or "")[:2] if m.group(2) is not None else ["SYSIN"]
    target = re.sub(r"\s+(?:OF|IN)\s+", " OF ", m.group(1))
    return [((" ".join(words) or "SYSIN", "special", False), (target, "item", False), False)]


def data_move_rows(path: Path, verbs: tuple = _MV_VERBS) -> list[dict[str, Any]]:
    """Data-move rows of `verbs` (the #3452 set by default; `_IO_VERBS` for #3492)."""
    src = Source(path)
    start = 0
    if src.proc_start is not None and src.proc_start < len(src.lines):
        start = sum(len(a) + 1 for _, a in src.lines[: src.proc_start])
    elif src.proc_start is not None:
        return []
    blank = src.text  # EXEC blocks blanked for the verb search; statements still end at EXEC
    for m in re.finditer(r"(?<![A-Z0-9-])EXEC\s.*?(?<![A-Z0-9-])END-EXEC(?![A-Z0-9-])", src.text, re.S):
        blank = blank[: m.start()] + " " * (m.end() - m.start()) + blank[m.end() :]
    # Only COBOL's scope terminators end a statement: a data name may start END- too.
    ends = r"END-(?:ACCEPT|ADD|CALL|COMPUTE|DELETE|DISPLAY|DIVIDE|EVALUATE|EXEC|IF|INVOKE|JSON|MULTIPLY|PERFORM|READ|RECEIVE|RETURN|REWRITE|SEARCH|START|STRING|SUBTRACT|UNSTRING|WRITE|XML)"
    enders = re.compile(r"(?<![A-Z0-9-])(?:" + "|".join(_MV_ENDERS) + "|" + ends + r")(?![A-Z0-9-])|\.(?=\s|$)")
    # READ's own NEXT (READ f NEXT RECORD INTO t) is not NEXT SENTENCE.
    read_enders = re.compile(
        r"(?<![A-Z0-9-])(?:"
        + "|".join(e for e in _MV_ENDERS if e != "NEXT")
        + "|"
        + ends
        + r")(?![A-Z0-9-])|\.(?=\s|$)"
    )
    rows = []
    for m in re.finditer(r"(?<![A-Z0-9-])(" + "|".join(verbs) + r")(?![A-Z0-9-])", blank):
        if m.start() < start:
            continue
        # A verb word inside parentheses is an argument, not a new statement:
        # zECS `MOVE DFHVALUE(DELETE) TO METHOD-CDVA` (#3495 pin).
        end = None
        for cand in (read_enders if m.group(1) in ("READ", "RETURN") else enders).finditer(src.text, m.end()):
            span = src.text[m.end() : cand.start()]
            if span.count("(") <= span.count(")"):
                end = cand
                break
        stop = end.start() if end else len(src.text)
        body = src.raw_text[m.end() : stop].replace("\n", " ")
        pairs = _io_statement_pairs if m.group(1) in _IO_VERBS else _mv_statement_pairs
        for a, t, corr in pairs(m.group(1), " " + body):
            rows.append({
                "verb": m.group(1), "source": a[0] if a else None, "kind": a[1] if a else None, "target": t[0],
                "corr": corr, "srm": bool(a and a[2]), "trm": t[2], "line": src.line_of(m.start()),
            })  # fmt: skip
    return rows


def data_move_keys(rows: list[dict[str, Any]]) -> set[str]:
    """`L<line> VERB[ CORR] SOURCE[(:)] -> TARGET[(:)]`, upper-cased (literal case aside)."""
    return {
        f"L{r['line']} {r['verb']}{' CORR' if r['corr'] else ''} {(r['source'] or '-').upper()}"
        f"{'(:)' if r['srm'] else ''} -> {r['target'].upper()}{'(:)' if r['trm'] else ''}"
        for r in rows
    }


def engine_data_move_row(m: Any) -> dict[str, Any]:
    return {"verb": m.verb, "source": m.source, "kind": m.source_kind, "target": m.target,
            "corr": m.corresponding, "srm": m.source_refmod, "trm": m.target_refmod, "line": m.line}  # fmt: skip


def _mv_pic_width(pic: str, usage: str) -> tuple[Optional[int], str]:
    """(one occurrence's bytes, class X | 9 | other) of a PIC + USAGE."""
    body = ""
    for ch, rep in re.findall(r"([A-Z9$,.+*/-]|\()(?:\((\d+)\))?", pic.upper().rstrip(".")):
        body += ch * int(rep or 1)
    u = usage.upper()
    digits = body.count("9")
    if re.search(r"COMP(?:UTATIONAL)?-3|PACKED", u):
        return digits // 2 + 1, "P"
    if re.search(r"(?<![A-Z0-9-])(?:COMP(?:UTATIONAL)?(?:-[45])?|BINARY)(?![A-Z0-9-])", u):
        return (2 if digits <= 4 else 4 if digits <= 9 else 8) if 0 < digits <= 18 else None, "B"
    if "N" in body or "G" in body:
        return sum(2 for c in body if c in "NG") or None, "N"
    width = sum(1 for c in body if c not in "SVP")
    return width or None, ("X" if set(body) & set("XA") else "9")


def _mv_entries(lines: list[str], repo: Path, stems: dict, depth: int = 0) -> list[tuple[int, str, str]]:
    """(level, name, description) per data entry, COPY members spliced in place."""
    out: list[tuple[int, str, str]] = []
    for line in lines:
        cp = re.match(r"\s*COPY\s+([A-Z0-9@#$-]+)", line)
        if cp and depth < 6:
            for cb in stems.get(cp.group(1), [])[:1]:
                out.extend(_mv_entries([a for _, a in Source(cb).lines], repo, stems, depth + 1))
            continue
        m = re.match(r"\s*(\d+)\s+([A-Z0-9-]+)(.*)", line)
        if m:
            out.append((int(m.group(1)), m.group(2), m.group(3)))
        elif out:
            out[-1] = (out[-1][0], out[-1][1], out[-1][2] + " " + line)
    return out


def _mv_width(entries: list[tuple[int, str, str]], i: int) -> tuple[Optional[int], str]:
    """(one occurrence's bytes, class | 'group') of entry i."""
    level, _name, desc = entries[i]
    pic = re.search(r"\bPIC(?:TURE)?\s+(?:IS\s+)?(\S+)", desc)
    if pic:
        return _mv_pic_width(pic.group(1), desc)
    total = 0
    j = i + 1
    while j < len(entries) and (entries[j][0] > level or entries[j][0] in (66, 88)) and entries[j][0] != 77:
        lv, _, d = entries[j]
        if lv in (66, 88):
            j += 1
            continue
        k = j + 1
        while k < len(entries) and (entries[k][0] > lv or entries[k][0] in (66, 88)):
            k += 1
        if not re.search(r"\bREDEFINES\b", d):
            w, _ = _mv_width(entries, j)
            if w is None:
                return None, "group"
            occ = re.search(r"\bOCCURS\s+(?:\d+\s+TO\s+)?(\d+)", d)
            total += w * (int(occ.group(1)) if occ else 1)
        j = k
    return (total or None), "group"


def data_move_truncations(path: Path, repo: Path, rows: list[dict[str, Any]]) -> list[str]:
    """`L<line> SOURCE -> TARGET` per MOVE into an alphanumeric or group item
    shorter than its item or quoted-literal source (no reference modification)."""
    stems: dict = {}
    for p in repo.rglob("*"):
        if p.is_file() and p.suffix.lower() in COPYBOOK_EXTS and ".git" not in p.parts:
            stems.setdefault(p.stem.upper(), []).append(p)
    src = Source(path)
    proc = src.proc_start if src.proc_start is not None else len(src.lines)
    entries = _mv_entries([a for _, a in src.lines[:proc]], repo, stems)
    # #3490: a COPY of a BMS mapset with no real copybook gets the generated
    # symbolic map -- this tool's own layout arithmetic gives its widths.
    sym: dict[str, int] = {}
    members = set(re.findall(r"\bCOPY\s+['\"]?([A-Z0-9@#$-]+)", "\n".join(a for _, a in src.lines[:proc])))
    wanted = {m for m in members if m not in stems}
    if wanted:
        for mapset, units in _symbolic_layouts(repo).items():
            if mapset in wanted:
                for u in units:
                    nm, _, rest = u.partition(" @")
                    sym[nm] = int(rest.split("+")[1])

    def width(name: str) -> tuple[Optional[int], str]:
        parts = name.split(" OF ")
        if parts[0] in sym and not any(e[1] == parts[0] for e in entries):
            # L is S9(4) COMP; the F / A / attribute bytes and I / O data are PIC X.
            return sym[parts[0]], ("B" if parts[0].endswith("L") else "X")
        hits = []
        for i, (lv, nm, _) in enumerate(entries):
            if nm != parts[0] or lv in (66, 88):
                continue
            want, j, cur = list(parts[1:]), i - 1, lv
            while j >= 0 and want:
                if entries[j][0] < cur and entries[j][0] not in (66, 88):
                    cur = entries[j][0]
                    if entries[j][1] == want[0]:
                        want.pop(0)
                    if cur == 1:
                        break
                j -= 1
            if not want:
                hits.append(_mv_width(entries, i))
        return hits[0] if len(set(hits)) == 1 else (None, "?")

    out = []
    for r in rows:
        if r["verb"] != "MOVE" or r["corr"] or r["srm"] or r["trm"]:
            continue
        tw, tc = width(r["target"])
        if not tw or tc not in ("X", "group"):
            continue
        if r["kind"] == "item":
            sw, _ = width(r["source"])
        elif r["kind"] == "literal" and (r["source"] or "")[:1] in "'\"":
            sw = len(r["source"]) - 2
        else:
            continue
        if sw and sw > tw:
            out.append(f"L{r['line']} {r['source'].upper()} -> {r['target'].upper()}")
    return sorted(set(out))


def draft_io_moves(repo: Path) -> dict[str, dict[str, Any]]:
    """Drafted file-I/O data moves (#3492) per COBOL source; `io_moves_validated` signs it off."""
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(repo.rglob("*")):
        if p.is_file() and ".git" not in p.parts and p.suffix.lower() in CICS_EXTS:
            rows = data_move_rows(p, _IO_VERBS)
            if rows:
                out[p.relative_to(repo).as_posix()] = {
                    "moves": sorted(data_move_keys(rows)),
                    "io_moves_validated": False,
                    "verification": {"status": "draft", "notes": []},
                }
    return out


_SYM_CACHE: dict = {}


def _symbolic_layouts(repo: Path) -> dict[str, list[str]]:
    """Mapset -> its symbolic-map units, under the draft_symbolic_maps ownership rule (#3490)."""
    if repo not in _SYM_CACHE:
        _SYM_CACHE[repo] = {ms: u for e in draft_symbolic_maps(repo).values() for ms, u in e["layouts"].items()}
    return _SYM_CACHE[repo]


def draft_data_moves(repo: Path) -> dict[str, dict[str, Any]]:
    """Drafted data moves (and the MOVE truncations) per COBOL program (#3452);
    `data_moves_validated` signs it off. Moves of a procedure copybook are the
    copybook's own rows; its truncations are judged in the includer's storage, so
    only programs carry truncations."""
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(repo.rglob("*")):
        if not p.is_file() or ".git" in p.parts or p.suffix.lower() not in CICS_EXTS:
            continue
        rows = data_move_rows(p)
        if not rows:
            continue
        program = p.suffix.lower() in PROGRAM_EXTS
        out[p.relative_to(repo).as_posix()] = {
            "moves": sorted(data_move_keys(rows)),
            "truncations": data_move_truncations(p, repo, rows) if program else [],
            "data_moves_validated": False,
            "verification": {"status": "draft", "notes": []},
        }
    return out


# ==============================================================================
# JCICS -- Java on CICS (#3497)
# ==============================================================================
# This tool's own reading, line by line: a variable is a JCICS resource when its
# declaration or `new` names Program / KSDS / ESDS / RRDS / TSQ / TDQ; its name is
# the string of the latest `var.setName(...)` line above the operation (a literal,
# or a `static final String` constant of the file); Program `link(` is a LINK,
# the file / queue methods are their access. Channels: createChannel("X");
# containers: createContainer / getContainer with a literal or constant name.
_JC_TYPES = ("Program", "KSDS", "ESDS", "RRDS", "TSQ", "TDQ")
_JC_ACCESS = {
    "read": "read", "readForUpdate": "read", "readGeneric": "read", "readGenericForUpdate": "read",
    "write": "write", "rewrite": "update", "delete": "delete", "startBrowse": "browse", "startGenericBrowse": "browse",
    "unlock": "unlock", "writeItem": "write", "writeItemConditional": "write", "rewriteItem": "update",
    "readItem": "read", "readNextItem": "read", "writeData": "write", "writeString": "write", "readData": "read",
}  # fmt: skip
_JC_KIND = {"Program": "PROGRAM", "KSDS": "FILE", "ESDS": "FILE", "RRDS": "FILE", "TSQ": "QUEUE", "TDQ": "QUEUE"}


def jcics_units(text: str) -> list[str]:
    """`L<line> LINK <program>` / `L<line> <KIND> <name|?> <access>` per JCICS call."""
    if "com.ibm.cics.server" not in text:
        return []
    lines = text.split("\n")
    code = []
    in_block = False
    for ln in lines:  # comments dropped, line numbers kept
        out = ""
        i = 0
        while i < len(ln):
            if in_block:
                end = ln.find("*/", i)
                if end == -1:
                    i = len(ln)
                    continue
                in_block, i = False, end + 2
                continue
            if ln.startswith("/*", i):
                in_block, i = True, i + 2
                continue
            if ln.startswith("//", i):
                break
            out += ln[i]
            i += 1
        code.append(out)
    consts = dict(re.findall(r'static\s+final\s+String\s+(\w+)\s*=\s*"([^"]*)"', "\n".join(code)))
    types: dict[str, str] = {}
    for ln in code:
        for t, v in re.findall(r"\b(" + "|".join(_JC_TYPES) + r")\s+(\w+)\s*[;=,)]", ln):
            types[v] = t
        for v, t in re.findall(r"\b(\w+)\s*=\s*new\s+(" + "|".join(_JC_TYPES) + r")\s*\(", ln):
            types[v] = t
    joined = "\n".join(code)
    names: dict[str, list[tuple[int, Optional[str]]]] = {}
    for m in re.finditer(r"\b(\w+)\s*\.\s*setName\s*\(\s*([^),]*)", joined):
        if m.group(1) in types:
            arg = m.group(2).strip()
            lit = re.fullmatch(r'"([^"]*)"', arg)
            pre = re.match(r'"([^"]+)"\s*\+', arg)
            val = (
                lit.group(1).strip()
                if lit
                else consts.get(arg, "").strip() or (pre.group(1).strip() + "*" if pre else None)
            )
            names.setdefault(m.group(1), []).append((joined.count("\n", 0, m.start()) + 1, val or None))
    out = set()
    for m in re.finditer(r"\b(\w+)\s*\.\s*(\w+)\s*\(", joined):
        var, meth = m.group(1), m.group(2)
        t = types.get(var)
        if not t:
            continue
        line = joined.count("\n", 0, m.start(2)) + 1  # the method's line (a chained call may wrap)
        prior = [n for ln_, n in names.get(var, []) if ln_ <= line]
        name = prior[-1] if prior else None
        if t == "Program" and meth == "link":
            if name and not name.endswith("*"):
                out.add(f"L{line} LINK {name.upper()}")
        elif t != "Program" and meth in _JC_ACCESS:
            out.add(f"L{line} {_JC_KIND[t]} {(name or '?').upper()} {_JC_ACCESS[meth]}")
    for m in re.finditer(r'\bcreateChannel\s*\(\s*("([^"]*)"|\w+)', joined):
        name = m.group(2) if m.group(2) is not None else consts.get(m.group(1))
        out.add(f"L{joined.count(chr(10), 0, m.start()) + 1} CHANNEL {(name or '?').upper()} pass")
    for m in re.finditer(r'\b(createContainer|getContainer)\s*\(\s*("([^"]*)"|[\w\[\]]+)', joined):
        name = m.group(3) if m.group(3) is not None else consts.get(m.group(2))
        acc = "write" if m.group(1) == "createContainer" else "read"
        out.add(f"L{joined.count(chr(10), 0, m.start()) + 1} CONTAINER {(name or '?').upper()} {acc}")
    return sorted(out)


def engine_jcics_units(ef: Any) -> set[str]:
    out = {f"L{c.line} LINK {c.target.upper()}" for c in ef.calls if c.verb == "LINK" and c.target}
    out |= {
        f"L{op.line} {op.kind} {(op.name or '?').upper()} {op.access}"
        for op in ef.cics_resources
        if (op.attributes or "").startswith("JCICS")
    }
    return out


def draft_jcics(repo: Path) -> dict[str, dict[str, Any]]:
    """Drafted JCICS calls per Java source (#3497); `jcics_validated` signs it off."""
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(repo.rglob("*.java")):
        if p.is_file() and ".git" not in p.parts:
            units = jcics_units(p.read_text(encoding="utf-8", errors="ignore"))
            if units:
                out[p.relative_to(repo).as_posix()] = {
                    "calls": units,
                    "jcics_validated": False,
                    "verification": {"status": "draft", "notes": []},
                }
    return out


# ==============================================================================
# Web / API services from the web-services assistant JCL (#3496)
# ==============================================================================
# This tool's own reading: the JCL statements (the job-flow statement reader) find
# each EXEC of DFHLS2WS / DFHLS2JS / DFHWS2LS / DFHJS2LS; the in-stream data lines
# between the next `DD *` / `DD DATA` and the `/*` or next `//` statement are read
# as KEY=VALUE parameters.
_WS_ASSISTANTS = {"DFHLS2WS": "provider", "DFHLS2JS": "provider", "DFHWS2LS": "requester", "DFHJS2LS": "requester"}
_WS_KEYS = {"PGMNAME": "program", "URI": "uri", "REQMEM": "request", "RESPMEM": "response", "PGMINT": "interface"}


def web_service_rows(text: str) -> list[dict[str, Any]]:
    lines = text.upper().split("\n")
    rows = []
    for i, line in enumerate(lines):
        m = re.match(r"//\S*\s+EXEC\s+(?:PROC=|PGM=)?(DFH(?:LS2WS|LS2JS|WS2LS|JS2LS))\b", line[:72])
        if not m:
            continue
        row: dict[str, Any] = {"assistant": m.group(1), "direction": _WS_ASSISTANTS[m.group(1)], "line": i + 1}
        data = False
        for nxt in lines[i + 1 :]:
            if nxt.startswith("/*"):
                break
            if nxt.startswith("//"):
                if data or re.search(r"\bEXEC\b", nxt[:72]):
                    break
                data = bool(re.search(r"\bDD\s+(?:\*|DATA)", nxt[:72]))
                continue
            if data:
                kv = re.match(r"\s*([A-Z][A-Z0-9-]*)\s*=\s*(\S+)", nxt[:72])
                if kv and kv.group(1) in _WS_KEYS:
                    row.setdefault(_WS_KEYS[kv.group(1)], kv.group(2))
        rows.append(row)
    return rows


def web_service_keys(rows: list[dict[str, Any]]) -> set[str]:
    """`L<line> ASSISTANT direction program=.. uri=.. request=.. response=.. interface=..`."""
    return {
        f"L{r['line']} {r['assistant']} {r['direction']} "
        + " ".join(
            f"{k}={str(r[k]).upper()}" for k in ("program", "uri", "request", "response", "interface") if r.get(k)
        )
        for r in rows
    }


def engine_web_service_row(w: Any) -> dict[str, Any]:
    return {"assistant": w.assistant, "direction": w.direction, "program": w.program, "uri": w.uri,
            "request": w.request, "response": w.response, "interface": w.interface, "line": w.line}  # fmt: skip


def draft_web_services(repo: Path) -> dict[str, dict[str, Any]]:
    """Drafted web-services assistant steps per JCL member (#3496); `web_validated` signs it off."""
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(repo.rglob("*")):
        if p.is_file() and p.suffix.lower() in JCL_EXTS and ".git" not in p.parts:
            rows = web_service_rows(p.read_text(encoding="utf-8", errors="ignore"))
            if rows:
                out[p.relative_to(repo).as_posix()] = {
                    "services": sorted(web_service_keys(rows)),
                    "web_validated": False,
                    "verification": {"status": "draft", "notes": []},
                }
    return out


# ==============================================================================
# Data-driven LINK / XCTL / CALL targets (#3493)
# ==============================================================================
# This tool's own reading: a site whose program operand is a data name (in the
# program, or in a procedure copybook it COPYs -- evaluated in the program) can
# name (1) the item's VALUE, (2) when it is an element of an OCCURS table that
# REDEFINES a VALUE-filled group, each occurrence's slice of that group's text,
# (3) each literal -- or VALUE-holding item -- a MOVE in the program stores in it.
def _dyn_sites(src: Source) -> list[tuple[int, str, str]]:
    out = []
    for m in _CALL.finditer(src.text):
        form, value = _operand(src, m.end())
        if form == "identifier" and value:
            out.append((src.line_of(m.start()), "CALL", value))
    for m in _CICS_PROGRAM.finditer(src.text):
        seg = src.text[m.end() : m.end() + 600]
        end = seg.find("END-EXEC")
        p = re.search(r"\bPROGRAM\s*\(\s*", seg[: end if end >= 0 else None])
        if p:
            form, value = _operand(src, m.end() + p.end())
            if form == "identifier" and value:
                out.append((src.line_of(m.start()), m.group(1), value))
    return out


def _dyn_group_text(entries: list[tuple[int, str, str]], base: int) -> Optional[str]:
    """A group's load-time text: its elementary VALUEs at their PIC widths ('?' unknown)."""
    text, j = "", base + 1
    while j < len(entries) and entries[j][0] > entries[base][0]:
        lvl, _, d = entries[j]
        pic = re.search(r"\bPIC(?:TURE)?\s+(?:IS\s+)?(\S+)", d)
        if lvl not in (66, 88) and pic and not re.search(r"\bREDEFINES\b", d):
            w, _ = _mv_pic_width(pic.group(1).rstrip("."), d)
            if w is None:
                return None
            v = re.search(r"\bVALUE\s+(?:IS\s+)?(?:'([^']*)'|\"([^\"]*)\"|([+-]?\d+))", d)
            if v is None:
                text += "?" * w
            elif v.group(3) is not None:
                text += v.group(3).rjust(w, "0")[-w:]
            else:
                text += (v.group(1) if v.group(1) is not None else v.group(2)).ljust(w)[:w]
        j += 1
    return text


def _dyn_offset(entries: list[tuple[int, str, str]], group: int, target: int) -> Optional[int]:
    """Bytes before entry `target` inside entry `group` (children walked in order)."""
    off, k, glv = 0, group + 1, entries[group][0]
    while k < len(entries) and entries[k][0] > glv:
        if k == target:
            return off
        end = k + 1
        while end < len(entries) and entries[end][0] > entries[k][0]:
            end += 1
        if target < end:
            inner = _dyn_offset(entries, k, target)
            return None if inner is None else off + inner
        if entries[k][0] not in (66, 88) and not re.search(r"\bREDEFINES\b", entries[k][2]):
            w, _ = _mv_width(entries, k)
            if w is None:
                return None
            occ = re.search(r"\bOCCURS\s+(?:\d+\s+TO\s+)?(\d+)", entries[k][2])
            off += w * (int(occ.group(1)) if occ else 1)
        k = end
    return None


def _dyn_table(entries: list[tuple[int, str, str]], name: str) -> list[str]:
    """Occurrence values of `name`, an element of an OCCURS table over a REDEFINES."""
    idx = [i for i, e in enumerate(entries) if e[1] == name and e[0] not in (66, 88)]
    if len(idx) != 1:
        return []
    i = idx[0]
    chain, lv = [i], entries[i][0]
    for j in range(i - 1, -1, -1):
        if entries[j][0] < lv and entries[j][0] not in (66, 88):
            chain.append(j)
            lv = entries[j][0]
            if lv == 1:
                break
    table = next((j for j in chain if re.search(r"\bOCCURS\s+(\d+)", entries[j][2])), None)
    if table is None:
        return []
    red = next(
        (j for j in chain[chain.index(table) :] if re.search(r"\bREDEFINES\s+([A-Z0-9-]+)", entries[j][2])), None
    )
    if red is None:
        return []
    base_name = re.search(r"\bREDEFINES\s+([A-Z0-9-]+)", entries[red][2]).group(1)
    base = next((j for j, e in enumerate(entries) if e[1] == base_name), None)
    text = _dyn_group_text(entries, base) if base is not None else None
    if not text:
        return []
    per, _ = _mv_width(entries, table)
    size, _ = _mv_width(entries, i)
    start = 0 if table == red else _dyn_offset(entries, red, table)
    inner = _dyn_offset(entries, table, i)
    times = int(re.search(r"\bOCCURS\s+(?:\d+\s+TO\s+)?(\d+)", entries[table][2]).group(1))
    if not per or not size or start is None or inner is None:
        return []
    vals = [text[start + n * per + inner : start + n * per + inner + size] for n in range(times)]
    return [v.strip() for v in vals if len(v) == size and v.strip() and "?" not in v]


def dynamic_target_units(path: Path, repo: Path, stems: dict) -> list[str]:
    """`L<line> VERB OPERAND -> PROGRAM` per candidate of each data-driven site."""
    src = Source(path)
    proc = src.proc_start if src.proc_start is not None else len(src.lines)
    entries = _mv_entries([a for _, a in src.lines[:proc]], repo, stems)
    sites = _dyn_sites(src)
    moved: dict[str, set] = {}
    for r in data_move_rows(path):
        moved.setdefault(r["target"].split(" OF ")[0], set()).add((r["kind"], r["source"]))
    # Procedure copybooks the program COPYs (or EXEC SQL INCLUDEs): their sites and
    # MOVEs act on its data.
    includes = r"\b(?:COPY|EXEC\s+SQL\s+INCLUDE)\s+['\"]?([A-Z0-9@#$-]+)"
    for member in re.findall(includes, "\n".join(a for _, a in src.lines[proc:])):
        for cb in stems.get(member, [])[:1]:
            sites += _dyn_sites(Source(cb))
            for r in data_move_rows(cb):
                moved.setdefault(r["target"].split(" OF ")[0], set()).add((r["kind"], r["source"]))
    out = set()
    for line, verb, name in sites:
        cands = set()
        v = _dli_value(path, repo, name)
        if v and v.strip() and "?" not in v:
            cands.add(v.strip())
        cands |= set(_dyn_table(entries, name))
        for kind, source in moved.get(name, set()):
            if kind == "literal" and source[:1] in "'\"":
                cands.add(source.strip("'\"").strip().upper())
            elif kind == "item":
                v = _dli_value(path, repo, source.split(" OF ")[0])
                if v and v.strip() and "?" not in v:
                    cands.add(v.strip().upper())
        out |= {f"L{line} {verb} {name} -> {c}" for c in cands}
    return sorted(out)


def draft_dynamic_targets(repo: Path) -> dict[str, dict[str, Any]]:
    """Drafted data-driven call targets per COBOL program (#3493); `dynamic_validated` signs it off."""
    stems: dict = {}
    for p in repo.rglob("*"):
        if p.is_file() and p.suffix.lower() in COPYBOOK_EXTS and ".git" not in p.parts:
            stems.setdefault(p.stem.upper(), []).append(p)
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(repo.rglob("*")):
        if p.is_file() and p.suffix.lower() in PROGRAM_EXTS and ".git" not in p.parts:
            units = dynamic_target_units(p, repo, stems)
            if units:
                out[p.relative_to(repo).as_posix()] = {
                    "targets": units,
                    "dynamic_validated": False,
                    "verification": {"status": "draft", "notes": []},
                }
    return out


# ==============================================================================
# Symbolic maps generated from BMS source (#3490)
# ==============================================================================
# This tool's own computation, by arithmetic, not by writing and parsing COBOL:
# each named DFHMDF field is one block of 3 + k + LENGTH bytes (L 2, F/A 1, k
# extended-attribute bytes, then the I / O data), after a 12-byte TIOA prefix
# when TIOAPFX=YES; the O record overlays the I record from offset 0. k comes
# from DSATTS= on the map else the mapset, or 4 under EXTATT=YES. An OCCURS=n
# field is n blocks under `<name>D` (input) and `DFHMS<j>` (output).
_SYM_LETTERS = (("COLOR", "C"), ("PS", "P"), ("HILIGHT", "H"), ("VALIDN", "V"), ("OUTLINE", "U"), ("SOSI", "M"),
                ("TRANSP", "T"))  # fmt: skip


def _sym_statements(text: str) -> dict[int, str]:
    """Physical first line -> the whole assembled statement text (column-72 continuation)."""
    lines = text.split("\n")
    out, i = {}, 0
    while i < len(lines):
        if lines[i].startswith(("*", ".*")) or not lines[i].strip():
            i += 1
            continue
        first, body = i, lines[i][:71].rstrip()
        while len(lines[i]) > 71 and lines[i][71] != " " and i + 1 < len(lines):
            i += 1
            body += lines[i][15:71].rstrip()
        out[first + 1] = body
        i += 1
    return out


def _sym_attrs(stmt: str) -> Optional[list[str]]:
    """The extended-attribute letters a DFHMSD / DFHMDI statement declares, or None."""
    m = re.search(r"DSATTS=\(([^)]*)\)|DSATTS=([A-Z]+)", stmt.upper())
    if m:
        names = set((m.group(1) or m.group(2)).split(","))
        return [c for n, c in _SYM_LETTERS if n in names]
    if re.search(r"EXTATT=YES", stmt.upper()):
        return ["C", "P", "H", "V"]
    return None


def symbolic_map_units(text: str) -> dict[str, list[str]]:
    """Mapset -> sorted `NAME @offset+bytes` of its generated COBOL symbolic map."""
    items = bms_screen_items(text)
    stmts = _sym_statements(text)
    by_ord = {it["ordinal"]: it for it in items}
    out: dict[str, set[str]] = {}
    for m in (it for it in items if it["kind"] == "map" and it["name"]):
        ms = by_ord.get(m["parent_ordinal"])
        ms_stmt = stmts.get(ms["line"], "") if ms else ""
        m_stmt = stmts.get(m["line"], "")
        prefix = 12 if "TIOAPFX=YES" in (m_stmt + " " + ms_stmt).upper() else 0
        letters = _sym_attrs(m_stmt)
        letters = letters if letters is not None else (_sym_attrs(ms_stmt) or [])
        k = len(letters)
        units, off, dfhms = set(), prefix, 0
        name = m["name"].upper()
        for f in (it for it in items if it["kind"] == "field" and it["parent_ordinal"] == m["ordinal"] and it["name"]):
            fn, ln, n = f["name"].upper(), f["length"] or 1, f["occurs"] or 0
            block = 3 + k + ln
            if n:
                dfhms += 1
                units |= {f"{fn}D @{off}+{block * n}", f"DFHMS{dfhms} @{off}+{block * n}"}
            units |= {f"{fn}L @{off}+2", f"{fn}F @{off + 2}+1", f"{fn}A @{off + 2}+1", f"{fn}I @{off + 3 + k}+{ln}",
                      f"{fn}O @{off + 3 + k}+{ln}"}  # fmt: skip
            units |= {f"{fn}{c} @{off + 3 + j}+1" for j, c in enumerate(letters)}
            off += block * (n or 1)
        units |= {f"{name}I @0+{off}", f"{name}O @0+{off}"}
        mapset = ((ms or {}).get("name") or name).upper()
        out.setdefault(mapset, set()).update(units)
    return {k: sorted(v) for k, v in out.items()}


def draft_symbolic_maps(repo: Path) -> dict[str, dict[str, Any]]:
    """Drafted symbolic-map layouts per BMS source (#3490); `symbolic_validated` signs it off.
    A mapset defined by several BMS sources is the one in the file named after it
    (a COPY of it can only mean one); its other definitions are not keyed."""
    per_file = {
        p: symbolic_map_units(p.read_text(encoding="utf-8", errors="ignore"))
        for p in sorted(repo.rglob("*"))
        if p.is_file() and p.suffix.lower() in BMS_EXTS and ".git" not in p.parts
    }
    owners: dict[str, list[Path]] = {}
    for p, maps in per_file.items():
        for mapset in maps:
            owners.setdefault(mapset, []).append(p)
    out: dict[str, dict[str, Any]] = {}
    for p, maps in per_file.items():
        maps = {ms: u for ms, u in maps.items() if len(owners[ms]) == 1 or p.stem.upper() == ms}
        if maps:
            out[p.relative_to(repo).as_posix()] = {
                "layouts": maps,
                "symbolic_validated": False,
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
    from gitgalaxy.tools.cobol_to_cobol.cobol_graveyard_finder import (
        resolve_copybooks,
        split_procedure_division,
        unit_headers,
    )

    content = resolve_copybooks(path.read_text(encoding="utf-8", errors="ignore").upper(), path, repo)
    split = split_procedure_division(content)
    return set(unit_headers(split[1])) if split else set()


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
        if suffix in CSD_EXTS:
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
        # #3446: which tables each program reads / inserts / updates / deletes.
        # Truth is this tool's own token walk; no forge reads it; engine is
        # sql_statement_data through GalaxyIR.sql_table_access().
        "DB2 table access",
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
        # #3449: CICS task-control commands (RUN/START/FETCH/RETRIEVE/DELAY/ENQ
        # ...), per COBOL source. Truth is this tool's own reader; no forge; engine
        # is cics_task_data.
        "CICS task control",
        # #3449: the CSD transactions each RUN/START reaches, a STRING-built id
        # expanded against the deck (`RUN OCR1`..`RUN OCR5`). Truth is this tool's
        # own pattern + CSD read; engine is GalaxyIR.async_tasks().
        "async children",
        # #3448: job submission through the internal reader, per submitting file
        # (CICS WRITEQ TD to an extrapartition queue, or a JCL SYSOUT=(x,INTRDR)
        # step). Truth is this tool's own join; engine is GalaxyIR.job_submissions().
        "job submissions",
        # #3447: IBM MQ calls (verb, direction, queue or why unnamed, matched open),
        # per COBOL source. Truth is this tool's own token walk; engine is mq_call_data.
        "MQ calls",
        # #3453: units of work (commit / rollback points), HANDLE CONDITION / ABEND
        # / AID handlers, explicit ABENDs and RESP checks, per COBOL source. Truth
        # is this tool's own reader; engine is uow_handler_data.
        "units of work and handlers",
        # #3453 add-on: transactions CICS starts when a written TD queue fills
        # (TRIGGERLEVEL + TRANSID), per writer. Engine is GalaxyIR.tdq_trigger_starts().
        "TD trigger starts",
        # #3455: FILE-CONTROL SELECT clauses (organisation, access, keys, FD copies)
        # per program, and IDCAMS DEFINE CLUSTER / AIX / PATH per JCL member. Truth is
        # this tool's own readers; engine is file_control_data / vsam_define_data.
        "file control",
        "VSAM defines",
        # #3451: JCL job flow (JOB / STEP order, COND / IF, PROC calls, DD DISP and
        # GDG generation), per JCL member. Truth is this tool's own reader; engine
        # is job_flow_data.
        "JCL job flow",
        # #3454: batch CALL USING lists and PROCEDURE DIVISION / ENTRY USING
        # parameters, per COBOL source. Truth is this tool's own reader; engine is
        # call_site_data.using_args + entry_point_data.
        "CALL USING",
        # #3450: IMS DL/I calls as written, and the program x segment access they
        # resolve to (function codes and SSAs through COPY-expanded VALUEs). Truth
        # is this tool's own reader; engine is dli_call_data + GalaxyIR.ims_segment_access.
        "DL/I calls",
        "IMS segment access",
        # #3477: IMS PSB / DBD macros and JCL IMS regions as rows, and each DL/I
        # program's segment access checked against its PSB's SENSEGs and PROCOPT.
        # Truth is this tool's own reader and join; engine is ims_gen_data +
        # GalaxyIR.ims_access_check.
        "IMS definitions",
        "IMS access check",
        # #3452: data moves (MOVE / COMPUTE / arithmetic / STRING / UNSTRING /
        # INITIALIZE) as written, and the MOVEs that truncate. Truth is this tool's
        # own reader and widths; engine is data_move_data + GalaxyIR.data_flows.
        "data moves",
        "MOVE truncation",
        # #3490: the COBOL symbolic map each BMS mapset generates, as named items
        # at byte offsets. Truth is this tool's own arithmetic; engine is
        # GalaxyIR.symbolic_map_layouts (generated copybook text, record parser).
        "symbolic maps",
        # #3492: READ / RETURN INTO, WRITE / REWRITE / RELEASE FROM, ACCEPT, as
        # written. Truth is this tool's own reader; engine is data_move_data.
        "file I/O moves",
        # #3493: the programs a data-driven LINK / XCTL / CALL can name (VALUE, an
        # OCCURS table over a VALUE-filled REDEFINES, MOVEd literals). Truth is this
        # tool's own reader; engine is GalaxyIR.dynamic_call_targets.
        "dynamic call targets",
        # #3496: the web-services assistant steps (the estate's API surface). Truth
        # is this tool's own reader; engine is web_service_data.
        "web services",
        # #3497: JCICS -- Java Program.link LINKs and KSDS / TSQ / TDQ / channel /
        # container operations. Truth is this tool's own reader; engine is the java
        # boundary dialect's call_site_data + cics_resource_data rows.
        "JCICS",
        # #3491: PL/I program call sites -- EXEC CICS LINK / XCTL / RETURN|START|RUN
        # TRANSID and CALLs leaving the program. Truth is this tool's own reader;
        # engine is the pli boundary dialect's call_site_data (after the resolver).
        "PL/I call sites",
        # #3491 part 3: PL/I assignment data moves, on the keyed files (a seeded sample
        # of DSF's). Truth is this tool's own reader; engine is the pli dialect's rows.
        "PL/I data moves",
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

    engine_access: dict[str, set[str]] = {}
    if ir is not None:
        for row in ir.sql_table_access():
            engine_access.setdefault(row["file"], set()).update(f"{a} {row['table']}" for a in row["accesses"])
    for rel, k in key.get("sql_access", {}).items():
        add(
            "DB2 table access",
            rel,
            set(k.get("accesses", [])),
            None,
            engine_access.get(rel, set()) if ir is not None and rel in ir.files else None,
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

    engine_children: dict[str, set[str]] = {}
    if ir is not None:
        for spawn in ir.async_tasks():
            engine_children.setdefault(spawn["parent"], set()).update(
                f"{spawn['verb']} {c['transid'].upper()}" for c in spawn["children"]
            )
    for rel, k in key.get("cics_tasks", {}).items():
        ef = ir.files.get(rel) if ir else None
        add(
            "CICS task control",
            rel,
            cics_task_keys(k.get("operations", [])),
            None,
            cics_task_keys([engine_task_row(t) for t in ef.cics_tasks]) if ef else None,
        )
        add("async children", rel, set(k.get("children", [])), None, engine_children.get(rel, set()) if ef else None)

    engine_subs = engine_job_submissions(ir.job_submissions()) if ir is not None else {}
    for rel, k in key.get("job_submissions", {}).items():
        add(
            "job submissions",
            rel,
            set(k.get("submissions", [])),
            None,
            engine_subs.get(rel, set()) if ir is not None and rel in ir.files else None,
        )

    for rel, k in key.get("mq_calls", {}).items():
        ef = ir.files.get(rel) if ir else None
        add(
            "MQ calls",
            rel,
            mq_call_keys(k.get("calls", [])),
            None,
            mq_call_keys([engine_mq_row(q) for q in ef.mq_calls]) if ef else None,
        )

    for rel, k in key.get("uow_handlers", {}).items():
        ef = ir.files.get(rel) if ir else None
        add(
            "units of work and handlers",
            rel,
            uow_keys(k.get("rows", [])),
            None,
            uow_keys([engine_uow_row(u) for u in ef.uow_handlers]) if ef else None,
        )
    engine_triggers: dict[str, set[str]] = {}
    if ir is not None:
        for t in ir.tdq_trigger_starts():
            engine_triggers.setdefault(t["writer"], set()).add(
                f"{t['queue']} -> {t['transid']} -> {t['program'] or '?'}"
            )
    for rel, k in key.get("tdq_triggers", {}).items():
        add(
            "TD trigger starts",
            rel,
            set(k.get("starts", [])),
            None,
            engine_triggers.get(rel, set()) if ir is not None and rel in ir.files else None,
        )

    for rel, k in key.get("file_control", {}).items():
        ef = ir.files.get(rel) if ir else None
        add(
            "file control",
            rel,
            file_control_keys(k.get("selects", [])),
            None,
            file_control_keys([engine_file_control_row(x) for x in ef.file_control]) if ef else None,
        )
    for rel, k in key.get("vsam_defines", {}).items():
        ef = ir.files.get(rel) if ir else None
        add(
            "VSAM defines",
            rel,
            vsam_define_keys(k.get("defines", [])),
            None,
            vsam_define_keys([engine_vsam_row(x) for x in ef.vsam_defines]) if ef else None,
        )

    for rel, k in key.get("job_flow", {}).items():
        ef = ir.files.get(rel) if ir else None
        add(
            "JCL job flow",
            rel,
            job_flow_keys(k.get("rows", [])),
            None,
            job_flow_keys([engine_job_flow_row(j) for j in ef.job_flow]) if ef else None,
        )

    for rel, k in key.get("call_using", {}).items():
        ef = ir.files.get(rel) if ir else None
        add(
            "CALL USING",
            rel,
            call_using_keys(k.get("rows", [])),
            None,
            call_using_keys(engine_call_using_rows(ef)) if ef else None,
        )

    engine_ims: dict[str, set[str]] = {}
    if ir is not None:
        for e in ir.ims_segment_access():
            engine_ims.setdefault(e["file"], set()).update(f"{a} {e['segment']}" for a in e["accesses"])
    for rel, k in key.get("dli_calls", {}).items():
        ef = ir.files.get(rel) if ir else None
        add(
            "DL/I calls",
            rel,
            dli_keys(k.get("calls", [])),
            None,
            dli_keys([engine_dli_row(c) for c in ef.dli_calls]) if ef else None,
        )
        add(
            "IMS segment access",
            rel,
            set(k.get("segment_access", [])),
            None,
            engine_ims.get(rel, set()) if ir is not None and rel in ir.files else None,
        )

    for rel, k in key.get("jcics", {}).items():
        ef = ir.files.get(rel) if ir else None
        add("JCICS", rel, set(k.get("calls", [])), None, engine_jcics_units(ef) if ef else None)
    for rel, k in key.get("pli_moves", {}).items():
        ef = ir.files.get(rel) if ir else None
        add(
            "PL/I data moves",
            rel,
            set(k.get("moves", [])),
            None,
            data_move_keys([engine_data_move_row(m) for m in ef.data_moves]) if ef else None,
        )
    for rel, k in key.get("pli_calls", {}).items():
        ef = ir.files.get(rel) if ir else None
        add(
            "PL/I call sites",
            rel,
            pli_call_keys(k.get("calls", [])),
            None,
            pli_call_keys([engine_pli_call_row(c) for c in ef.calls]) if ef else None,
        )
    for rel, k in key.get("web_services", {}).items():
        ef = ir.files.get(rel) if ir else None
        add(
            "web services",
            rel,
            set(k.get("services", [])),
            None,
            web_service_keys([engine_web_service_row(w) for w in ef.web_services]) if ef else None,
        )
    engine_dyn: dict[str, set[str]] = {}
    if ir is not None:
        for d in ir.dynamic_call_targets():
            engine_dyn.setdefault(d["file"], set()).update(
                f"L{d['line']} {d['verb']} {d['operand'].split('(')[0].strip()} -> {c['program']}"
                for c in d["candidates"]
            )
    for rel, k in key.get("dynamic_targets", {}).items():
        add(
            "dynamic call targets",
            rel,
            set(k.get("targets", [])),
            None,
            engine_dyn.get(rel, set()) if ir is not None and rel in ir.files else None,
        )
    engine_maps = ir.symbolic_map_layouts() if ir is not None else {}
    for rel, k in key.get("symbolic_maps", {}).items():
        for mapset, units in k.get("layouts", {}).items():
            eng = engine_maps.get(mapset)
            add(
                "symbolic maps",
                f"{rel}#{mapset}",
                set(units),
                None,
                set(eng["items"]) if eng and eng["file"] == rel else (set() if ir is not None else None),
            )
    for rel, k in key.get("io_moves", {}).items():
        ef = ir.files.get(rel) if ir else None
        add(
            "file I/O moves",
            rel,
            set(k.get("moves", [])),
            None,
            data_move_keys([engine_data_move_row(m) for m in ef.data_moves if m.verb in _IO_VERBS]) if ef else None,
        )
    engine_trunc: dict[str, set[str]] = {}
    if ir is not None:
        for fl in ir.data_flows():
            if fl["truncates"] and not fl["copybook"]:
                engine_trunc.setdefault(fl["file"], set()).add(
                    f"L{fl['line']} {fl['source'].upper()} -> {fl['target']}"
                )
    for rel, k in key.get("data_moves", {}).items():
        ef = ir.files.get(rel) if ir else None
        add(
            "data moves",
            rel,
            set(k.get("moves", [])),
            None,
            data_move_keys([engine_data_move_row(m) for m in ef.data_moves if m.verb not in _IO_VERBS]) if ef else None,
        )
        if rel.lower().endswith(PROGRAM_EXTS):
            add(
                "MOVE truncation",
                rel,
                set(k.get("truncations", [])),
                None,
                engine_trunc.get(rel, set()) if ef else None,
            )
    engine_checks = engine_ims_check_lines(ir.ims_access_check()) if ir is not None else {}
    for rel, k in key.get("ims_gen", {}).items():
        ef = ir.files.get(rel) if ir else None
        if "rows" in k:
            add(
                "IMS definitions",
                rel,
                ims_gen_keys(k["rows"]),
                None,
                ims_gen_keys([engine_ims_gen_row(g) for g in ef.ims_gen]) if ef else None,
            )
        else:
            add(
                "IMS access check",
                rel,
                set(k.get("access_check", [])),
                None,
                set(engine_checks.get(rel, [])) if ef else None,
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
    pm = sub.add_parser("add-pli-moves")
    pm.add_argument("repo", type=Path)
    pm.add_argument("--key", type=Path, required=True)
    pc = sub.add_parser("add-pli-calls")
    pc.add_argument("repo", type=Path)
    pc.add_argument("--key", type=Path, required=True)
    qa = sub.add_parser("add-sql-access")
    qa.add_argument("repo", type=Path)
    qa.add_argument("--key", type=Path, required=True)
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
    dlp = sub.add_parser("add-dli")
    dlp.add_argument("repo", type=Path)
    dlp.add_argument("--key", type=Path, required=True)
    jcp = sub.add_parser("add-jcics")
    jcp.add_argument("repo", type=Path)
    jcp.add_argument("--key", type=Path, required=True)
    wsp = sub.add_parser("add-web-services")
    wsp.add_argument("repo", type=Path)
    wsp.add_argument("--key", type=Path, required=True)
    dyp = sub.add_parser("add-dynamic-targets")
    dyp.add_argument("repo", type=Path)
    dyp.add_argument("--key", type=Path, required=True)
    smp = sub.add_parser("add-symbolic-maps")
    smp.add_argument("repo", type=Path)
    smp.add_argument("--key", type=Path, required=True)
    iop = sub.add_parser("add-io-moves")
    iop.add_argument("repo", type=Path)
    iop.add_argument("--key", type=Path, required=True)
    dmp = sub.add_parser("add-data-moves")
    dmp.add_argument("repo", type=Path)
    dmp.add_argument("--key", type=Path, required=True)
    igp = sub.add_parser("add-ims-gen")
    igp.add_argument("repo", type=Path)
    igp.add_argument("--key", type=Path, required=True)
    cup = sub.add_parser("add-call-using")
    cup.add_argument("repo", type=Path)
    cup.add_argument("--key", type=Path, required=True)
    jfp = sub.add_parser("add-job-flow")
    jfp.add_argument("repo", type=Path)
    jfp.add_argument("--key", type=Path, required=True)
    fdp = sub.add_parser("add-file-defs")
    fdp.add_argument("repo", type=Path)
    fdp.add_argument("--key", type=Path, required=True)
    uw = sub.add_parser("add-uow")
    uw.add_argument("repo", type=Path)
    uw.add_argument("--key", type=Path, required=True)
    mq = sub.add_parser("add-mq")
    mq.add_argument("repo", type=Path)
    mq.add_argument("--key", type=Path, required=True)
    js = sub.add_parser("add-job-submissions")
    js.add_argument("repo", type=Path)
    js.add_argument("--key", type=Path, required=True)
    xt = sub.add_parser("add-cics-tasks")
    xt.add_argument("repo", type=Path)
    xt.add_argument("--key", type=Path, required=True)
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
    if args.cmd == "add-pli-moves":
        # #3491 part 3: refresh drafts, never clobber a file someone already signed off.
        drafted, scope = draft_pli_moves(repo)
        existing_pm = key.get("pli_moves", {})
        for rel, entry in drafted.items():
            if not existing_pm.get(rel, {}).get("pli_moves_validated"):
                existing_pm[rel] = entry
        key["pli_moves"], key["pli_moves_scope"] = existing_pm, scope
        args.key.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        print(f"drafted {len(existing_pm)} PL/I data-move files ({scope['keyed']} of {scope['files']}) -> {args.key}")
        return 0
    if args.cmd == "add-pli-calls":
        # #3491: refresh drafts, never clobber a file someone already signed off.
        existing_pc = key.get("pli_calls", {})
        for rel, entry in draft_pli_calls(repo).items():
            if not existing_pc.get(rel, {}).get("pli_calls_validated"):
                existing_pc[rel] = entry
        key["pli_calls"] = existing_pc
        # The repository-wide include-internal names, for the sampled census's grader.
        key["pli_calls_included"] = sorted(pli_included_procedures(_pli_files(repo)))
        args.key.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        print(f"drafted {len(existing_pc)} PL/I call-site files -> {args.key}")
        return 0
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
    if args.cmd == "add-sql-access":
        # #3446: same rule as add-sql-tables -- refresh drafts, never clobber a sign-off.
        existing_acc = key.get("sql_access", {})
        for rel, entry in draft_sql_access(repo).items():
            if not existing_acc.get(rel, {}).get("sql_access_validated"):
                existing_acc[rel] = entry
        key["sql_access"] = existing_acc
        args.key.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        print(f"drafted {len(existing_acc)} SQL table-access files -> {args.key}")
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
    if args.cmd == "add-dli":
        # #3450: the add-pli discipline -- refresh drafts, keep signed-off files.
        dl = key.get("dli_calls", {})
        for rel, entry in draft_dli(repo).items():
            if not dl.get(rel, {}).get("dli_validated"):
                dl[rel] = entry
        key["dli_calls"] = dl
        args.key.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        print(f"drafted {len(dl)} DL/I files -> {args.key}")
        return 0
    if args.cmd == "add-jcics":
        # #3497: the add-pli discipline; an unvalidated file no longer drafted is dropped.
        jc = {rel: e for rel, e in key.get("jcics", {}).items() if e.get("jcics_validated")}
        for rel, entry in draft_jcics(repo).items():
            if not jc.get(rel, {}).get("jcics_validated"):
                jc[rel] = entry
        key["jcics"] = jc
        args.key.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        print(f"drafted {len(jc)} JCICS Java files -> {args.key}")
        return 0
    if args.cmd == "add-web-services":
        # #3496: the add-pli discipline; an unvalidated file no longer drafted is dropped.
        ws = {rel: e for rel, e in key.get("web_services", {}).items() if e.get("web_validated")}
        for rel, entry in draft_web_services(repo).items():
            if not ws.get(rel, {}).get("web_validated"):
                ws[rel] = entry
        key["web_services"] = ws
        args.key.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        print(f"drafted {len(ws)} web-service JCL members -> {args.key}")
        return 0
    if args.cmd == "add-dynamic-targets":
        # #3493: the add-pli discipline; an unvalidated file no longer drafted is dropped.
        dt = {rel: e for rel, e in key.get("dynamic_targets", {}).items() if e.get("dynamic_validated")}
        for rel, entry in draft_dynamic_targets(repo).items():
            if not dt.get(rel, {}).get("dynamic_validated"):
                dt[rel] = entry
        key["dynamic_targets"] = dt
        args.key.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        print(f"drafted {len(dt)} dynamic-target files -> {args.key}")
        return 0
    if args.cmd == "add-symbolic-maps":
        # #3490: the add-pli discipline -- refresh drafts, keep signed-off files.
        sm = {rel: e for rel, e in key.get("symbolic_maps", {}).items() if e.get("symbolic_validated")}
        for rel, entry in draft_symbolic_maps(repo).items():
            if not sm.get(rel, {}).get("symbolic_validated"):
                sm[rel] = entry
        key["symbolic_maps"] = sm
        args.key.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        print(f"drafted {len(sm)} BMS symbolic-map files -> {args.key}")
        return 0
    if args.cmd == "add-io-moves":
        # #3492: the add-pli discipline; an unvalidated file no longer drafted is dropped.
        io = {rel: e for rel, e in key.get("io_moves", {}).items() if e.get("io_moves_validated")}
        for rel, entry in draft_io_moves(repo).items():
            if not io.get(rel, {}).get("io_moves_validated"):
                io[rel] = entry
        key["io_moves"] = io
        args.key.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        print(f"drafted {len(io)} file-I/O move files -> {args.key}")
        return 0
    if args.cmd == "add-data-moves":
        # #3452: the add-pli discipline -- refresh drafts, keep signed-off files.
        # An unvalidated file the new draft no longer yields is dropped.
        dm = {rel: e for rel, e in key.get("data_moves", {}).items() if e.get("data_moves_validated")}
        for rel, entry in draft_data_moves(repo).items():
            if not dm.get(rel, {}).get("data_moves_validated"):
                dm[rel] = entry
        key["data_moves"] = dm
        args.key.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        print(f"drafted {len(dm)} data-move files -> {args.key}")
        return 0
    if args.cmd == "add-ims-gen":
        # #3477: the add-pli discipline -- refresh drafts, keep signed-off files.
        ig = key.get("ims_gen", {})
        for rel, entry in draft_ims_gen(repo, key.get("dli_calls", {})).items():
            if not ig.get(rel, {}).get("ims_gen_validated"):
                ig[rel] = entry
        key["ims_gen"] = ig
        args.key.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        print(f"drafted {len(ig)} IMS definition / access-check files -> {args.key}")
        return 0
    if args.cmd == "add-call-using":
        # #3454: the add-pli discipline -- refresh drafts, keep signed-off files.
        cu = key.get("call_using", {})
        for rel, entry in draft_call_using(repo).items():
            if not cu.get(rel, {}).get("call_using_validated"):
                cu[rel] = entry
        key["call_using"] = cu
        args.key.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        print(f"drafted {len(cu)} CALL USING files -> {args.key}")
        return 0
    if args.cmd == "add-job-flow":
        # #3451: the add-pli discipline -- refresh drafts, keep signed-off files.
        flows = key.get("job_flow", {})
        for rel, entry in draft_job_flow(repo).items():
            if not flows.get(rel, {}).get("jobflow_validated"):
                flows[rel] = entry
        key["job_flow"] = flows
        args.key.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        print(f"drafted {len(flows)} JCL members' job flow -> {args.key}")
        return 0
    if args.cmd == "add-file-defs":
        # #3455: the add-pli discipline -- refresh drafts, keep signed-off files.
        fc_new, vd_new = draft_file_defs(repo)
        fc, vd = key.get("file_control", {}), key.get("vsam_defines", {})
        for rel, entry in fc_new.items():
            if not fc.get(rel, {}).get("file_control_validated"):
                fc[rel] = entry
        for rel, entry in vd_new.items():
            if not vd.get(rel, {}).get("vsam_validated"):
                vd[rel] = entry
        key["file_control"], key["vsam_defines"] = fc, vd
        args.key.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        print(f"drafted {len(fc)} FILE-CONTROL programs, {len(vd)} IDCAMS JCL members -> {args.key}")
        return 0
    if args.cmd == "add-uow":
        # #3453: the add-pli discipline -- refresh drafts, keep signed-off files.
        uow = key.get("uow_handlers", {})
        for rel, entry in draft_uow(repo).items():
            if not uow.get(rel, {}).get("uow_validated"):
                uow[rel] = entry
        key["uow_handlers"] = uow
        trig = key.get("tdq_triggers", {})
        for rel, entry in draft_tdq_triggers(repo).items():
            if not trig.get(rel, {}).get("tdq_triggers_validated"):
                trig[rel] = entry
        key["tdq_triggers"] = trig
        args.key.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        print(f"drafted {len(uow)} unit-of-work files, {len(trig)} TD-trigger writers -> {args.key}")
        return 0
    if args.cmd == "add-mq":
        # #3447: the add-pli discipline -- refresh drafts, keep signed-off files.
        calls = key.get("mq_calls", {})
        for rel, entry in draft_mq(repo).items():
            if not calls.get(rel, {}).get("mq_validated"):
                calls[rel] = entry
        key["mq_calls"] = calls
        args.key.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        print(f"drafted {len(calls)} MQ files -> {args.key}")
        return 0
    if args.cmd == "add-job-submissions":
        # #3448: the add-pli discipline -- refresh drafts, keep signed-off files.
        subs = key.get("job_submissions", {})
        for rel, entry in draft_job_submissions(repo).items():
            if not subs.get(rel, {}).get("submissions_validated"):
                subs[rel] = entry
        key["job_submissions"] = subs
        args.key.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        print(f"drafted {len(subs)} job-submitting files -> {args.key}")
        return 0
    if args.cmd == "add-cics-tasks":
        # #3449: the add-pli discipline -- refresh drafts, keep signed-off files.
        tasks = key.get("cics_tasks", {})
        for rel, entry in draft_cics_tasks(repo).items():
            if not tasks.get(rel, {}).get("cics_tasks_validated"):
                tasks[rel] = entry
        key["cics_tasks"] = tasks
        args.key.write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        print(f"drafted {len(tasks)} CICS task-control files -> {args.key}")
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
