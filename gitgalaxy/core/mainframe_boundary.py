# ==============================================================================
# GitGalaxy Core: Mainframe Boundary Extraction (#3200, #3201, #3246, #3211-followup, #3250)
#
# PURPOSE:
# The counted rules tell you THAT a COBOL program calls something and THAT a JCL
# job allocates a dataset (`ipc_rpc_bridges` -> arch_ipc, `io` -> arch_io). They
# never say WHAT. This module is the named channel for the mainframe relations
# that the hit counts flatten:
#
#   1. invocation  -- COBOL `CALL`, CICS `LINK`/`XCTL PROGRAM(...)`, JCL
#                     `EXEC PGM=`: who runs whom (#3200).
#   2. dataset     -- COBOL `SELECT ... ASSIGN TO <ddname>` with the `OPEN`
#                     modes actually used, and the JCL `DD` statement that binds
#                     that ddname to a real dataset (#3201).
#   3. records     -- the DATA DIVISION item tree (WORKING-STORAGE / LINKAGE /
#                     LOCAL-STORAGE) and FILE SECTION `FD`/`01` record layouts:
#                     level, name, PIC, USAGE/COMP-3, OCCURS [DEPENDING ON],
#                     REDEFINES, VALUE -- the schema of the system (#3246).
#                     PL/I `DECLARE`d structures feed the same channel (#3250).
#   4. transaction -- the CICS transaction map (#3211-followup): the CSD
#                     `DEFINE TRANSACTION(TTTT) ... PROGRAM(PPPP)` records (and
#                     `DEFINE PROGRAM(PPPP) ... TRANSID(TTTT)` autoinstall
#                     pairings), from `.csd` decks and from DFHCSDUP SYSIN inside
#                     JCL; plus the in-source routing verbs a COBOL program uses
#                     to hand control to a transaction -- `EXEC CICS
#                     RETURN/START/RUN TRANSID(...)`. The transaction is the
#                     external front door: a user submits a 4-char id and CICS
#                     routes it to a program. Without it the DB has the internal
#                     call graph but not the entry points a modernizer turns into
#                     service/API boundaries.
#
# Together they are the mainframe call graph, the dataset lineage, the record
# layouts and the transaction map that `docs/refraction_engine_differential.md`
# recorded as stated absences: "program P reads DD X, job J binds DD X to dataset
# D", "no data items are extracted", and "transaction T entry-points into program
# P", were all unanswerable from the DB.
#
# SCOPE AND NON-SCOPE:
#   - Extraction only. Nothing here resolves a name to a file; that is
#     `invocation_resolver.py`, which needs the whole repository.
#   - Reads the PRISM CODE STREAM, never the raw file, so a commented-out CALL
#     or a `//* EXEC PGM=` banner cannot produce an edge. The code stream keeps
#     line numbers 1:1 with the source, so `line` is the real source line.
#   - No reachability. An `OPEN` inside an unreachable paragraph is still
#     extracted; the engine has no reachability model (docs/
#     unreferenced_by_name_contract.md corollary 3) and inventing one here would
#     repeat exactly the mistake #3198 corrected.
#   - Record layouts are SAME-FILE ONLY (#3246), like `_cobol_value_map`: a
#     copybook's items are extracted when the copybook itself is scanned, so a
#     `.cpy` carries its own layout and cross-file COPY assembly stays the
#     reader's job (mirrors how `copy_deps` works). Byte offsets, COMP-3 width
#     and REDEFINES overlay resolution are NOT computed here -- that is a
#     consumer's job on top of this tree, the same split the forge kept.
#
# WHY A STATEMENT WALKER AND NOT ONE BIG REGEX:
# Every construct here is a COBOL SENTENCE or a JCL STATEMENT, and all four span
# lines in real source (`OPEN INPUT A\n B\n OUTPUT C.`, `EXEC CICS LINK\n
# PROGRAM('CREACC')\n END-EXEC`, `//DD1 DD DSN=X,\n// UNIT=SYSDA`). A regex that
# spans lines to catch them is exactly the unbounded `[^.]*` shape #3222 had to
# go and bound. Accumulating the statement first costs one pass and leaves every
# pattern anchored inside a single bounded string.
# ==============================================================================
import bisect
import re
from typing import Any, Optional

# #3344: the DB2 DECLARE TABLE / DCLGEN channel lives in its own module (it is
# not a DATA DIVISION construct) and rides out of extract_boundary as `sql_tables`.
from gitgalaxy.core.bms_screen_fields import bms_screen_fields
from gitgalaxy.core.db2_declare_table import extract_sql_tables

# The dialects that carry a top-level `boundary_extraction` declaration. It is
# top level rather than inside `rules` because language_lens.py re.compile()s
# every string value in `rules` (#2806). `csd` is the CICS resource-definition
# deck (#3211-followup); jcl additionally carries a DFHCSDUP SYSIN deck inline.
# `pli` carries only the record channel: its DECLAREd structures (#3250).
# `bms` carries only the screen-field channel: its map field layouts (#3347).
BOUNDARY_DIALECTS = ("cobol", "jcl", "csd", "pli", "bms")

# #3211-followup: the call-site verbs whose `target` is a TRANSACTION, not a
# program. They ride in call_site_data alongside program invocations, but their
# target resolves through the CSD transaction map (transid -> program), never the
# PROGRAM-ID index -- so invocation_resolver does not program-resolve them and
# galaxy_ir.unresolved_calls does not count them as unresolved program calls.
TRANSACTION_ROUTING_VERBS = ("RETURN TRANSID", "START TRANSID", "RUN TRANSID")

# COBOL's optional sequence-number area (cols 1-6) plus the indicator column,
# the same prefix cobol.py's own anchored rules carry. Accepted source may or
# may not number its lines; both forms appear in the pinned corpora.
_COBOL_AREA_A = r"^(?:[0-9a-zA-Z \t]{6}[ \-]?)?[ \t]*"

# A data description entry opens with a level number. 01-49 plus the special
# levels 66/77/88; `77` carries a VALUE as often as `01` does in real source.
# re.M because the anchor has to fire on EVERY line, not just the first of the
# buffer it is handed -- without it the entry above a blank line was invisible,
# which lost all 124 of CBSA's `VALUE`-resolved LINK targets.
_LEVEL_START = re.compile(_COBOL_AREA_A + r"(\d{1,2})[ \t]+([A-Z][A-Z0-9-]*)(?![A-Z0-9-])", re.I | re.M)

# A data description entry runs to the next level number. Capped so the last
# entry before PROCEDURE DIVISION cannot swallow the procedure body and read a
# `VALUE` that belongs to nothing. The longest real entry in the pinned corpora
# is 214 chars.
_ENTRY_LIMIT = 600

# `VALUE 'LIT'` / `VALUE IS "LIT"` inside one already-bounded entry. The literal
# body cannot contain the quote that opened it, so neither branch can run away.
_VALUE_LITERAL = re.compile(r"\bVALUE[ \t]+(?:IS[ \t]+)?(?:'([^']*)'|\"([^\"]*)\")", re.I)

# `SELECT <internal-file-name> ASSIGN TO <name>`, inside one accumulated
# sentence. TO is optional (IBM accepts `ASSIGN <name>`), and the assign operand
# may be a literal in some dialects, so both forms are read.
_SELECT_ASSIGN = re.compile(
    r"\bSELECT[ \t]+(?:OPTIONAL[ \t]+)?([A-Z][A-Z0-9-]*)[ \t\n]+"
    r"ASSIGN[ \t\n]+(?:TO[ \t\n]+)?(?:'([^']*)'|\"([^\"]*)\"|([A-Z][A-Z0-9@#$-]*))",
    re.I,
)

# The four OPEN modes. A single OPEN carries several (`OPEN INPUT A B OUTPUT C`),
# so the operand run is walked and the mode switches at each keyword.
_OPEN_MODES = ("INPUT", "OUTPUT", "I-O", "EXTEND")

# The OPEN verb itself. `-` is a COBOL name character, so plain `\b` would fire
# inside `WS-OPEN-FLAG`; both guards exclude it explicitly.
_OPEN_ANCHOR = re.compile(r"(?<![A-Z0-9-])OPEN(?![A-Z0-9-])")

# Environment-division device prefixes that are not part of the ddname
# (`ASSIGN TO UT-S-CUSTFILE` binds DD CUSTFILE). Stripped for `dd_name`; the
# operand as written is kept in `assign_name`.
_ASSIGN_DEVICE_PREFIX = re.compile(r"^(?:UT|UR|DA|UT-S|UR-S|DA-S)-(?:S-)?", re.I)

# `CALL 'PROG'` / `CALL "PROG"` -- the static, link-edited form.
_CALL_LITERAL = re.compile(r"\bCALL[ \t\n]+(?:'([^']*)'|\"([^\"]*)\")", re.I)

# `CALL WS-PROGRAM-NAME` -- the dynamic form, resolved through the data item's
# own VALUE clause when it has one. The negative lookahead keeps the literal
# form above from matching twice, and `END-CALL` cannot match because the verb
# is anchored on a word boundary that `-` does not close.
_CALL_IDENTIFIER = re.compile(r"(?<![A-Z0-9-])CALL[ \t\n]+(?!['\"])([A-Z][A-Z0-9-]*)", re.I)

# An `EXEC CICS LINK`/`XCTL` block, up to its END-EXEC. The body bound is
# generous enough for the real multi-option blocks (PROGRAM/COMMAREA/RESP/
# RESP2/SYNCONRETURN) and hard-capped so an unterminated EXEC cannot scan the
# rest of the file.
_CICS_TRANSFER = re.compile(r"\bEXEC[ \t\n]+CICS[ \t\n]+(LINK|XCTL)\b", re.I)
_CICS_PROGRAM_OPERAND = re.compile(r"\bPROGRAM[ \t\n]*\([ \t\n]*(?:'([^']*)'|\"([^\"]*)\"|([A-Z][A-Z0-9-]*))", re.I)
# Longest real LINK block in the pinned corpora is 6 lines / ~220 chars; 2000
# leaves an order of magnitude of headroom without ever crossing a paragraph.
_CICS_BLOCK_LIMIT = 2000

# #3211-followup: the CICS in-source routing verbs whose operand is a
# TRANSACTION, not a program. `RETURN TRANSID(...)` sets the next transaction of
# a pseudo-conversational task; `START`/`RUN TRANSID(...)` dispatch one. Plain
# `EXEC CICS RETURN` (no TRANSID) is not routing and draws nothing. `START` is
# `\bSTART\b`, so `STARTBR` (a file browse) cannot match. Read as an EXEC block
# up to END-EXEC, the same bounded shape as the LINK/XCTL transfer above.
_CICS_TRANSID_VERB = re.compile(r"\bEXEC[ \t\n]+CICS[ \t\n]+(RETURN|START|RUN)\b", re.I)
# The TRANSID operand: a 4-char literal (`TRANSID('OCRA')`) or a data-name
# resolved through its working-storage VALUE (`TRANSID(WS-TRANID)` where
# `05 WS-TRANID PIC X(4) VALUE 'CC00'`). A name with no readable VALUE (populated
# at runtime, `VALUE SPACES`) resolves to None -- data, not a gap.
_CICS_TRANSID_OPERAND = re.compile(r"\bTRANSID[ \t\n]*\([ \t\n]*(?:'([^']*)'|\"([^\"]*)\"|([A-Z][A-Z0-9-]*))", re.I)

# A JCL statement: `//name operation operands`. The name field is optional --
# unnamed DD and EXEC statements are valid and common.
_JCL_STATEMENT = re.compile(r"^//([A-Z0-9_#$@]*)[ \t]+([A-Z]+)(?:[ \t]+(.*))?$", re.I)
# `EXEC PGM=X`. `EXEC name` / `EXEC PROC=name` invoke a PROCEDURE, not a
# program: jcl.py's `api` rule already owns that relation and #3200 asks for
# PGM= specifically.
_JCL_EXEC_PGM = re.compile(r"\bPGM=([A-Z0-9_#$@]+)", re.I)
# `DSN=`/`DSNAME=` on a DD. `&&NAME` is a job-local temporary dataset and `*`
# opens an in-stream payload -- neither is an external binding, and jcl.py's
# `_dependency_capture` already excludes both for the same reason.
_JCL_DSN = re.compile(r"\bDSN(?:AME)?=(?!(?:&&|\*))([A-Z0-9_#$@.&()-]+)", re.I)

# ---- #3246: DATA DIVISION record-layout clauses ----------------------------
# All of these are searched INSIDE one already-bounded data-description entry
# (`_LEVEL_START` to the next level number, capped at `_ENTRY_LIMIT`), so none
# can run away across the whole file -- the same bounding `_cobol_value_map`
# relies on. `[ \t\n]` where a clause can wrap onto a continuation line, which
# real source does constantly (`USAGE\n IS COMP-3.`, `REDEFINES\n WS-FOO.`).

# The division/section that owns the entries that follow it. Only the data
# sections matter; `FILE SECTION` additionally carries FD record layouts.
_SECTION_HEADER = re.compile(
    _COBOL_AREA_A + r"(FILE|WORKING-STORAGE|LOCAL-STORAGE|LINKAGE|COMMUNICATION|REPORT|SCREEN)[ \t]+SECTION[ \t]*\.",
    re.I | re.M,
)
# The DATA DIVISION / PROCEDURE DIVISION boundaries: record layouts live only
# between them (a copybook has neither header and is parsed whole).
_DATA_DIVISION = re.compile(_COBOL_AREA_A + r"DATA[ \t]+DIVISION[ \t]*\.", re.I | re.M)
_PROCEDURE_DIVISION = re.compile(_COBOL_AREA_A + r"PROCEDURE[ \t]+DIVISION", re.I | re.M)
# `FD <file>` / `SD <sort-file>` binds the `01` record(s) that follow it in the
# FILE SECTION to a logical file. It is not a data-description entry (no level
# number), so it is tracked separately and joined by position.
_FD_START = re.compile(_COBOL_AREA_A + r"(?:FD|SD)[ \t]+([A-Z][A-Z0-9-]*)(?![A-Z0-9-])", re.I | re.M)
# `PIC`/`PICTURE [IS] <chars>`. The character class is the COBOL picture symbol
# set (X A 9 S V P Z * B / , . $ + - CR/DB and the `(n)` repeat); it contains no
# whitespace, so it stops at the first space and cannot cross into the next
# clause. A clause-terminating period is stripped by the caller.
_PIC_CLAUSE = re.compile(r"\bPIC(?:TURE)?[ \t]+(?:IS[ \t]+)?([-A-Z0-9(),.$/*+]+)", re.I)
# USAGE, with or without the `USAGE [IS]` keyword (COBOL allows a bare `COMP-3`).
# The keyword is delimited by COBOL name-character boundaries, not `\b`: `-` is a
# name character, so `\bBINARY\b` otherwise matches inside `TWO-BYTES-BINARY`
# (the name in a `REDEFINES TWO-BYTES-BINARY` clause) and mislabels a group item.
_USAGE_CLAUSE = re.compile(
    r"(?:\bUSAGE[ \t\n]+(?:IS[ \t\n]+)?)?"
    r"(?<![A-Z0-9-])(COMPUTATIONAL(?:-[1-6])?|COMP(?:-[1-6])?|BINARY|PACKED-DECIMAL|DISPLAY(?:-1)?|INDEX|POINTER)"
    r"(?![A-Z0-9-])",
    re.I,
)
# `OCCURS <n> [TO <m>] [TIMES]` plus the optional `DEPENDING [ON] <name>`.
_OCCURS_CLAUSE = re.compile(r"\bOCCURS[ \t\n]+(\d+)(?:[ \t\n]+TO[ \t\n]+(\d+))?", re.I)
_DEPENDING_CLAUSE = re.compile(r"\bDEPENDING[ \t\n]+(?:ON[ \t\n]+)?([A-Z][A-Z0-9-]*)", re.I)
# `REDEFINES <name>` -- the storage-overlay pointer.
_REDEFINES_CLAUSE = re.compile(r"\bREDEFINES[ \t\n]+([A-Z][A-Z0-9-]*)", re.I)
# `VALUE [IS] <literal>`: a quoted string, or a numeric / figurative constant
# (`ZERO`, `SPACES`, `HIGH-VALUES`, `-1`, `12.5`).
_VALUE_CLAUSE = re.compile(
    r"\bVALUE[ \t\n]+(?:IS[ \t\n]+)?(?:'([^']*)'|\"([^\"]*)\"|([A-Z0-9][A-Z0-9+.-]*))",
    re.I,
)
# The special levels: 88 condition-names and 66 RENAMES describe the item above
# them rather than nesting by level number, so they attach to the last real
# item and are never pushed as a potential parent themselves.
_CONDITION_LEVELS = (66, 88)

# --- #3211-followup: the CICS CSD (resource-definition) deck ----------------
# A DFHCSDUP/CEDA deck runs DFHCSDUP; a JCL that does not is not a CSD deck and
# the inline pass is skipped entirely.
_DFHCSDUP = re.compile(r"\bPGM=DFHCSDUP\b", re.I)
# A CSD command opens a line (tolerating a leading blank column or JCL-inline
# indentation): DEFINE a resource, or a structural command (DELETE/ADD/LIST/...).
# Only DEFINE carries a resource we capture; the rest merely terminate the record
# that precedes them.
_CSD_COMMAND = re.compile(r"^[ \t]*(DEFINE|DELETE|ALTER|ADD|REMOVE|LIST|UPGRADE|COPY)\b", re.I)
# The head of a DEFINE record: the resource type and its name. The name run is
# permissive (a CICS transaction id is 4 chars, a program 8; an over-long name is
# DFHCSDUP's diagnostic, not ours).
_CSD_DEFINE_HEAD = re.compile(r"^[ \t]*DEFINE[ \t]+([A-Z0-9]+)[ \t]*\([ \t]*([A-Z0-9@#$]+)[ \t]*\)", re.I)
# A `KEYWORD(` attribute opener. The value is read by a paren-balanced scan
# (values carry spaces, commas `WAITTIME(0,0,0)`, slashes and quoted strings), so
# this only finds the keyword and the opening paren.
_CSD_ATTR_KEY = re.compile(r"\b([A-Z][A-Z0-9]*)[ \t]*\(", re.I)
# Attribute-name abbreviations DFHCSDUP accepts (seen in carddemo inline JCL).
# Only the ones that touch a field we keep need mapping; the rest pass through.
_CSD_ATTR_SYNONYMS = {"DA": "DATALOCATION", "TASKDATAL": "TASKDATALOC", "DESC": "DESCRIPTION"}
# The two resource types the transaction map is built from, plus the DB2TRAN type
# whose `TRANSID(...)` is a DB2 attribute -- NOT a transaction definition -- and
# must be excluded.
_CSD_TXN_RESOURCE = "TRANSACTION"
_CSD_PGM_RESOURCE = "PROGRAM"
_CSD_EXCLUDED_RESOURCES = frozenset({"DB2TRAN", "DB2ENTRY", "DB2CONN"})


def _opens_inside_literal(code_stream: str, line_start: int, offset: int) -> bool:
    """Whether `offset` sits inside a quoted literal opened earlier on its own line.

    `DISPLAY 'GNP CALL FAILED :'` is not a call to FAILED. Measured on
    aws-mainframe-modernization-carddemo, which the two answer-keyed corpora do
    not cover: 5 of 102 extracted call sites were this shape, all of them an
    IMS status message naming the very verb that had just run.

    Quote state is tracked PER LINE and never across one. A COBOL literal does
    not span a physical line without a continuation indicator, and an unbalanced
    apostrophe in real source (`AUTHOR. James O'Grady.`) would otherwise swallow
    the rest of the file -- the same trap the answer-key drafter hit (#3210).
    """
    quote = None
    for ch in code_stream[line_start:offset]:
        if quote is None:
            if ch in "'\"":
                quote = ch
        elif ch == quote:
            quote = None
    return quote is not None


def _cobol_sentences(code_stream: str) -> list[tuple[int, str]]:
    """Split the code stream into (1-based start line, text) COBOL sentences.

    A sentence ends at a period. Splitting on the period rather than the newline
    is what lets every pattern above stay inside one bounded string while still
    seeing the multi-line statements real source is full of.
    """
    sentences: list[tuple[int, str]] = []
    buf: list[str] = []
    start_line = 1
    for idx, line in enumerate(code_stream.split("\n"), start=1):
        if not buf:
            start_line = idx
        buf.append(line)
        # A period ends the sentence. A period inside a literal or a decimal
        # point would end it early; that only ever truncates a sentence, never
        # merges two, so an over-split costs a missed operand and never invents
        # one. (PIC decimals use `V`, so the realistic exposure is small.)
        if "." in line:
            sentences.append((start_line, "\n".join(buf)))
            buf = []
    if buf:
        sentences.append((start_line, "\n".join(buf)))
    return sentences


def _cobol_value_map(code_stream: str) -> dict[str, str]:
    """Data-name -> its `VALUE` literal, for every data description entry that has one.

    This is how a dynamic `CALL`/`LINK` target is resolved: CBSA's dominant
    idiom is `01 WS-ABEND-PGM PIC X(8) VALUE 'ABNDPROC'.` followed by
    `EXEC CICS LINK PROGRAM(WS-ABEND-PGM)`, 124 of its 144 call sites.

    SAME FILE ONLY. The engine's worker sees one file; a copybook's VALUE clause
    is not in this stream, so a target declared in a copybook resolves to None
    and is recorded as an unresolved target rather than guessed at.
    """
    values: dict[str, str] = {}
    entries = list(_LEVEL_START.finditer(code_stream))
    for pos, level in enumerate(entries):
        # The entry ends at the next level number, or at the cap -- whichever
        # comes first. Bounding it on a real delimiter rather than on a period
        # keeps `VALUE 'A.B'` readable.
        stop = entries[pos + 1].start() if pos + 1 < len(entries) else len(code_stream)
        literal = _VALUE_LITERAL.search(code_stream[level.end() : min(stop, level.end() + _ENTRY_LIMIT)])
        if not literal:
            continue
        text = literal.group(1) if literal.group(1) is not None else literal.group(2)
        text = (text or "").strip()
        if not text:
            continue
        # First declaration wins: a name redefined later in the same program is
        # ambiguous, and taking the first matches the answer key's reading.
        values.setdefault(level.group(2).upper(), text)
    return values


def _cobol_calls(code_stream: str, values: dict[str, str]) -> list[dict[str, Any]]:
    """Every COBOL invocation site: `CALL`, and CICS `LINK`/`XCTL PROGRAM(...)`."""
    calls: list[dict[str, Any]] = []

    # Line numbers come from a precomputed newline index. Counting newlines per
    # call site instead is O(file) per call, which turns a program with many
    # CALLs into a quadratic scan of itself.
    newlines = [i for i, ch in enumerate(code_stream) if ch == "\n"]

    def _line_of(offset: int) -> int:
        return bisect.bisect_left(newlines, offset) + 1

    def _shielded(offset: int) -> bool:
        """True when this verb is text inside a literal, not a statement."""
        index = bisect.bisect_left(newlines, offset)
        line_start = newlines[index - 1] + 1 if index else 0
        return _opens_inside_literal(code_stream, line_start, offset)

    # 1. EXEC CICS LINK / XCTL. Read first so the PROGRAM(...) operand is
    #    attributed to its own verb, and recorded at the line of the EXEC.
    for match in _CICS_TRANSFER.finditer(code_stream):
        if _shielded(match.start()):
            continue
        block = code_stream[match.end() : match.end() + _CICS_BLOCK_LIMIT]
        end = block.upper().find("END-EXEC")
        if end != -1:
            block = block[:end]
        operand_match = _CICS_PROGRAM_OPERAND.search(block)
        if not operand_match:
            # A LINK with no PROGRAM operand is a CHANNEL-only transfer or
            # malformed source. Recorded with no operand: the site exists.
            calls.append(
                {
                    "verb": match.group(1).upper(),
                    "form": "unknown",
                    "operand": None,
                    "target": None,
                    "line": _line_of(match.start()),
                }
            )
            continue
        literal = operand_match.group(1) if operand_match.group(1) is not None else operand_match.group(2)
        if literal is not None:
            form, operand, target = "literal", literal.strip(), literal.strip()
        else:
            operand = operand_match.group(3).upper()
            form, target = "identifier", values.get(operand)
        calls.append(
            {
                "verb": match.group(1).upper(),
                "form": form,
                "operand": operand or None,
                "target": (target or None),
                "line": _line_of(match.start()),
            }
        )

    # 2. CALL 'LITERAL'
    for match in _CALL_LITERAL.finditer(code_stream):
        if _shielded(match.start()):
            continue
        literal = match.group(1) if match.group(1) is not None else match.group(2)
        literal = (literal or "").strip()
        calls.append(
            {
                "verb": "CALL",
                "form": "literal",
                "operand": literal or None,
                "target": literal or None,
                "line": _line_of(match.start()),
            }
        )

    # 3. CALL IDENTIFIER
    for match in _CALL_IDENTIFIER.finditer(code_stream):
        if _shielded(match.start()):
            continue
        operand = match.group(1).upper()
        calls.append(
            {
                "verb": "CALL",
                "form": "identifier",
                "operand": operand,
                "target": values.get(operand),
                "line": _line_of(match.start()),
            }
        )

    # 4. #3211-followup: CICS RETURN/START/RUN TRANSID -- the in-source routing
    #    to a TRANSACTION. The `verb` names the transaction target ("RETURN
    #    TRANSID"), so galaxy_ir.transaction_map joins it against the CSD map and
    #    galaxy_ir.unresolved_calls skips it (its target is a transaction id, not
    #    a program, so program resolution would only ever add a false unresolved).
    for match in _CICS_TRANSID_VERB.finditer(code_stream):
        if _shielded(match.start()):
            continue
        block = code_stream[match.end() : match.end() + _CICS_BLOCK_LIMIT]
        end = block.upper().find("END-EXEC")
        if end != -1:
            block = block[:end]
        operand_match = _CICS_TRANSID_OPERAND.search(block)
        if not operand_match:
            # A plain RETURN with no TRANSID is an ordinary return, not routing;
            # START/RUN always carry TRANSID, so a miss there is malformed source.
            continue
        literal = operand_match.group(1) if operand_match.group(1) is not None else operand_match.group(2)
        if literal is not None:
            form, operand, target = "literal", literal.strip(), literal.strip()
        else:
            operand = operand_match.group(3).upper()
            form, target = "identifier", values.get(operand)
        calls.append(
            {
                "verb": f"{match.group(1).upper()} TRANSID",
                "form": form,
                "operand": operand or None,
                "target": (target or None),
                "line": _line_of(match.start()),
            }
        )

    calls.sort(key=lambda c: (c["line"], c["verb"], c["operand"] or ""))
    return calls


def _cobol_datasets(code_stream: str) -> list[dict[str, Any]]:
    """`SELECT ... ASSIGN TO <dd>` with the OPEN modes each file is actually opened in."""
    records: dict[str, dict[str, Any]] = {}
    sentences = _cobol_sentences(code_stream)

    for line_no, sentence in sentences:
        match = _SELECT_ASSIGN.search(sentence)
        if not match:
            continue
        internal = match.group(1).upper()
        assign = next((g for g in (match.group(2), match.group(3), match.group(4)) if g), "")
        assign = assign.strip()
        if not assign:
            continue
        records.setdefault(
            internal,
            {
                "internal_name": internal,
                "assign_name": assign.upper(),
                "dd_name": _ASSIGN_DEVICE_PREFIX.sub("", assign).upper(),
                "modes": set(),
                "line": line_no,
            },
        )

    # OPEN walks its operand run, switching mode at each mode keyword. Only
    # operands that a SELECT declared are credited, which is what keeps a
    # stray word in an OPEN sentence from inventing a dataset.
    for _line_no, sentence in sentences:
        upper = sentence.upper()
        anchor = 0
        while True:
            found = _OPEN_ANCHOR.search(upper, anchor)
            if not found:
                break
            anchor = found.end()
            mode: Optional[str] = None
            for token in upper[found.end() :].replace(",", " ").replace(".", " ").split():
                if token in _OPEN_MODES:
                    mode = token
                elif token in records and mode:
                    records[token]["modes"].add(mode)

    out = []
    for rec in records.values():
        rec = dict(rec)
        rec["modes"] = sorted(rec["modes"])
        rec["dsn"] = None
        rec["step_name"] = None
        out.append(rec)
    out.sort(key=lambda r: (r["line"], r["internal_name"]))
    return out


def _cobol_records(code_stream: str) -> list[dict[str, Any]]:
    """The DATA DIVISION item tree and FD record layouts of one COBOL file (#3246).

    Each entry is a flat dict; the tree is rebuilt by the reader from `ordinal`
    and `parent_ordinal`, so the row order here IS the source order:

        {section, fd_name, ordinal, parent_ordinal, level, name, pic, usage,
         occurs_min, occurs_max, occurs_depending_on, redefines, value, line}

    A data description entry runs from its level number to the next one, capped
    at `_ENTRY_LIMIT`, so every clause is read inside one bounded window -- the
    same guard `_cobol_value_map` uses. Only entries between `DATA DIVISION` and
    `PROCEDURE DIVISION` are emitted; a copybook has neither header, so its bare
    `01`/`05` items are read from the whole stream. Nesting is by level number
    (a level opens a child of the nearest shallower level still open); `66`/`88`
    describe the item above them and never become a parent.
    """
    newlines = [i for i, ch in enumerate(code_stream) if ch == "\n"]

    def _line_of(offset: int) -> int:
        return bisect.bisect_left(newlines, offset) + 1

    # The data-division window. A copybook (no headers) is read whole; a program
    # is read only between its own two division headers so a numbered PROCEDURE
    # construct can never be mistaken for a level number.
    dd_match = _DATA_DIVISION.search(code_stream)
    data_start = dd_match.end() if dd_match else 0
    proc_match = _PROCEDURE_DIVISION.search(code_stream, data_start)
    data_end = proc_match.start() if proc_match else len(code_stream)

    # Section and FD markers, joined to the entries below them by position.
    sections = [(m.start(), m.group(1).upper()) for m in _SECTION_HEADER.finditer(code_stream)]
    fds = [(m.start(), m.group(1).upper()) for m in _FD_START.finditer(code_stream)]
    section_offsets = [s[0] for s in sections]
    fd_offsets = [f[0] for f in fds]

    def _context(offset: int) -> tuple[Optional[str], Optional[str]]:
        """The (section, fd_name) in force at `offset`. fd only inside FILE SECTION."""
        s_idx = bisect.bisect_right(section_offsets, offset) - 1
        section = sections[s_idx][1] if s_idx >= 0 else None
        fd_name = None
        if section == "FILE":
            f_idx = bisect.bisect_right(fd_offsets, offset) - 1
            # The FD must fall inside the current FILE SECTION, not an earlier one.
            if f_idx >= 0 and fd_offsets[f_idx] >= section_offsets[s_idx]:
                fd_name = fds[f_idx][1]
        return section, fd_name

    entries = list(_LEVEL_START.finditer(code_stream))
    records: list[dict[str, Any]] = []
    stack: list[tuple[int, int]] = []  # (level, ordinal) of the open group items
    last_item_ordinal: Optional[int] = None

    for pos, level_match in enumerate(entries):
        start = level_match.start()
        if start < data_start or start >= data_end:
            continue
        level = int(level_match.group(1))
        name = level_match.group(2).upper()

        # The entry body: from just after the name to the next level number.
        stop = entries[pos + 1].start() if pos + 1 < len(entries) else len(code_stream)
        window = code_stream[level_match.end() : min(stop, level_match.end() + _ENTRY_LIMIT)]

        ordinal = len(records)
        if level in _CONDITION_LEVELS:
            parent_ordinal: Optional[int] = last_item_ordinal
        else:
            while stack and stack[-1][0] >= level:
                stack.pop()
            parent_ordinal = stack[-1][1] if stack else None
            stack.append((level, ordinal))
            last_item_ordinal = ordinal

        pic_match = _PIC_CLAUSE.search(window)
        pic = pic_match.group(1).rstrip(".") if pic_match else None
        usage_match = _USAGE_CLAUSE.search(window)
        usage = usage_match.group(1).upper() if usage_match else None
        occurs_match = _OCCURS_CLAUSE.search(window)
        occurs_min = occurs_max = None
        depending = None
        if occurs_match:
            occurs_min = int(occurs_match.group(1))
            occurs_max = int(occurs_match.group(2)) if occurs_match.group(2) else occurs_min
            dep_match = _DEPENDING_CLAUSE.search(window)
            depending = dep_match.group(1).upper() if dep_match else None
        redefines_match = _REDEFINES_CLAUSE.search(window)
        redefines = redefines_match.group(1).upper() if redefines_match else None
        value_match = _VALUE_CLAUSE.search(window)
        value = None
        if value_match:
            if value_match.group(1) is not None or value_match.group(2) is not None:
                # A quoted literal is kept verbatim (it may legitimately end in a period).
                value = value_match.group(1) if value_match.group(1) is not None else value_match.group(2)
            else:
                # A bareword numeric / figurative constant: strip the clause-terminating
                # period the character class swallowed (`VALUE 0.` -> `0`, not `0.`).
                value = value_match.group(3).rstrip(".")

        section, fd_name = _context(start)
        records.append(
            {
                "section": section,
                "fd_name": fd_name,
                "ordinal": ordinal,
                "parent_ordinal": parent_ordinal,
                "level": level,
                "name": name,
                "pic": pic,
                "usage": usage,
                "occurs_min": occurs_min,
                "occurs_max": occurs_max,
                "occurs_depending_on": depending,
                "redefines": redefines,
                "value": value,
                "line": _line_of(start),
            }
        )
    return records


# ---- #3250: PL/I DECLARE structures -----------------------------------------
# A PL/I `DECLARE`d structure is the direct analog of a COBOL record layout: a
# level-number hierarchy of named items with attributes. The same `record_data`
# spine carries it; the columns map where the meaning is the same and the full
# attribute text rides in `attributes` for everything that has no COBOL home:
#
#   level_number        <- level (a level-less declaration is level 1)
#   pic                 <- the PICTURE string, unquoted
#   usage               <- the data type as written, in canonical order:
#                          `FIXED DEC(7,2)`, `CHAR(10) VARYING`, `BIT(1)`, `POINTER`
#   section             <- the root's storage class as written
#                          (STATIC / AUTOMATIC / BASED / CONTROLLED), else None
#   occurs_min/max      <- the first dimension's extent; occurs_depending_on <- REFER
#   redefines           <- DEFINED/DEF base (BASED names a pointer, not an item)
#   value               <- INIT/INITIAL/VALUE content
#   attributes          <- every attribute but INIT, whitespace-collapsed
#
# Names are PL/I identifiers (`_ID` in pli.py): letters, digits, `_@#$` and the
# national letters real source uses (navikt/DSF: `DATO_ÅMD`). `\w` is Unicode on
# a str pattern. `*` is the unnamed (filler) member.
_PLI_NAME = re.compile(r"(?:[^\W\d]|[@#$])[\w@#$]*|\*")
_PLI_LEVEL = re.compile(r"(\d{1,3})(?=[ \t\r\n(])")
_PLI_DECLARE = re.compile(r"(?:DCL|DECLARE)(?![\w@#$])", re.I)
# A preprocessor procedure (`%NAME: PROCEDURE ...; ... %END;`) runs at compile
# time; a DECLARE inside it declares a macro variable, not program storage.
_PLI_MACRO_PROC = re.compile(r"%[ \t\r\n]*[\w@#$]+[ \t\r\n]*:[ \t\r\n]*PROC(?:EDURE)?(?![\w@#$])", re.I)
_PLI_MACRO_END = re.compile(r"%[ \t\r\n]*END(?![\w@#$])", re.I)
# Fixed-format source carries a sequence number in columns 73-80 (navikt/DSF:
# `00000110`). Blanked in place so offsets and line numbers are unchanged. A line
# over 80 columns is free-format and left alone.
_PLI_SEQ_FIELD = re.compile(r"[ \t]*[A-Z]{0,4}[0-9]{2,8}[ \t]*", re.I)
# PRISM removes a comment but not the sequence number after it, so a line such as
# `2 X CHAR(1), /* note */ 00000160` leaves the number at a column other than 73.
# It then sits alone before a newline at the start of the next item or statement --
# several in a row when consecutive lines each lost a comment.
_PLI_LEADING_SEQ = re.compile(r"[ \t\r\n]*[A-Z]{0,4}[0-9]{2,8}[ \t]*(?=\r?\n)", re.I)
# Canonical spellings of the attribute keywords this reader interprets.
_PLI_SYNONYMS = {
    "CHARACTER": "CHAR",
    "DECIMAL": "DEC",
    "BINARY": "BIN",
    "PICTURE": "PIC",
    "INITIAL": "INIT",
    "DEFINED": "DEF",
    "PTR": "POINTER",
    "AUTO": "AUTOMATIC",
    "CTL": "CONTROLLED",
    "VAR": "VARYING",
    "DIMENSION": "DIM",
    "COND": "CONDITION",
    "WCHAR": "WIDECHAR",
}
_PLI_STORAGE_CLASSES = ("STATIC", "AUTOMATIC", "BASED", "CONTROLLED")
_PLI_STRING_TYPES = ("CHAR", "BIT", "GRAPHIC", "WIDECHAR", "UCHAR")
_PLI_LOCATOR_TYPES = ("POINTER", "OFFSET", "HANDLE", "AREA", "LABEL")
# Declarations that are not data: a file constant, a builtin, a condition, a
# generic or an entry constant (an ENTRY VARIABLE is data), a named FORMAT.
_PLI_NOT_DATA = frozenset({"FILE", "BUILTIN", "CONDITION", "GENERIC", "ENTRY", "RETURNS", "FORMAT"})


def _pli_blank_sequence_fields(code_stream: str) -> str:
    """Columns 73-80 blanked on every fixed-format line that carries a sequence number."""
    lines = code_stream.split("\n")
    for idx, line in enumerate(lines):
        body = line.rstrip("\r")
        if 72 < len(body.rstrip()) <= 80 and _PLI_SEQ_FIELD.fullmatch(body[72:]):
            lines[idx] = body[:72] + " " * (len(line) - 72)
    return "\n".join(lines)


def _pli_skip_leading(text: str) -> int:
    """The index of the first real character: past whitespace and any orphaned
    sequence numbers (one match per line, so the loop is linear)."""
    i = 0
    while True:
        lead = _PLI_LEADING_SEQ.match(text, i)
        if not lead:
            break
        i = lead.end()
    while i < len(text) and text[i].isspace():
        i += 1
    return i


def _pli_split(text: str, sep: str) -> list[tuple[int, str]]:
    """(offset, piece) for `text` split on `sep` outside quotes and parentheses."""
    pieces: list[tuple[int, str]] = []
    depth = 0
    quote: Optional[str] = None
    start = 0
    for i, ch in enumerate(text):
        if quote is not None:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(depth - 1, 0)
        elif ch == sep and depth == 0:
            pieces.append((start, text[start:i]))
            start = i + 1
    pieces.append((start, text[start:]))
    return pieces


def _pli_balanced(text: str, open_at: int) -> int:
    """The index just past the `)` closing the `(` at `open_at` (quote-aware), or len(text)."""
    depth = 0
    quote: Optional[str] = None
    for i in range(open_at, len(text)):
        ch = text[i]
        if quote is not None:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i + 1
    return len(text)


def _pli_upper(text: str) -> str:
    """Upper-cased outside quoted literals, whitespace runs collapsed to one space
    and dropped just inside parentheses (`POS( 4)` reads `POS(4)`)."""
    out: list[str] = []
    quote: Optional[str] = None
    for ch in text:
        if quote is not None:
            out.append(ch)
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
            out.append(ch)
        elif ch.isspace():
            if out and out[-1] not in " (":
                out.append(" ")
        else:
            if ch == ")" and out and out[-1] == " ":
                out.pop()
            out.append(ch.upper())
    return "".join(out).strip()


def _pli_tokens(text: str) -> list[str]:
    """The attribute tokens of one item: whitespace-separated outside quotes and
    parentheses, with a `(...)` or quoted operand glued to its keyword so `CHAR (10)`
    and `PIC '999'` read like `CHAR(10)` and `PIC'999'`."""
    raw: list[str] = []
    buf: list[str] = []
    depth = 0
    quote: Optional[str] = None
    for ch in text:
        if quote is not None:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "'\"":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(depth - 1, 0)
        elif ch.isspace() and depth == 0:
            if buf:
                raw.append("".join(buf))
                buf = []
            continue
        buf.append(ch)
    if buf:
        raw.append("".join(buf))
    tokens: list[str] = []
    for tok in raw:
        if tokens and tok[0] in "('\"":
            tokens[-1] += tok
        else:
            tokens.append(tok)
    # A bare number is a sequence field a removed comment left mid-item, never an
    # attribute (every PL/I attribute is a keyword, optionally with an operand).
    return [_pli_upper(t) for t in tokens if not t.isdigit()]


def _pli_unquote(literal: str) -> Optional[str]:
    """The body of a single quoted literal (`''` folded to `'`), or None if it is not one."""
    literal = literal.strip()
    if len(literal) >= 2 and literal[0] in "'\"" and literal[-1] == literal[0]:
        body = literal[1:-1]
        doubled = literal[0] * 2
        if literal[0] not in body.replace(doubled, ""):
            return body.replace(doubled, literal[0])
    return None


def _pli_extent(dims: str) -> tuple[Optional[int], Optional[str]]:
    """(extent, REFER name) of the first dimension of a `(...)` dimension list."""
    first = _pli_split(dims, ",")[0][1].strip()
    refer = None
    refer_at = re.search(r"(?<![\w@#$])REFER[ \t\r\n]*\(", first, re.I)
    if refer_at:
        close = _pli_balanced(first, refer_at.end() - 1)
        refer = first[refer_at.end() : close - 1].strip().upper() or None
        first = first[: refer_at.start()].strip()
    bounds = [b.strip() for _, b in _pli_split(first, ":")]
    try:
        if len(bounds) == 2:
            return int(bounds[1]) - int(bounds[0]) + 1, refer
        return int(bounds[0]), refer
    except ValueError:
        return None, refer


def _pli_item_attributes(tokens: list[str]) -> Optional[dict[str, Any]]:
    """The record_data fields of one item from its attribute tokens, or None when
    the declaration is not data (a FILE, BUILTIN, CONDITION, ENTRY constant ...)."""
    parsed: list[tuple[str, str]] = []
    for tok in tokens:
        m = re.match(r"[A-Z_]+", tok)
        keyword = m.group(0) if m else ""
        parsed.append((_PLI_SYNONYMS.get(keyword, keyword), tok[len(keyword) :]))
    keywords = {k for k, _ in parsed}
    if keywords & _PLI_NOT_DATA and "VARIABLE" not in keywords:
        return None

    scale = base = precision = None
    string_type = varying = locator = pic = value = redefines = section = None
    dims = None
    kept: list[str] = []
    skip_next = False
    for pos, (keyword, operand) in enumerate(parsed):
        if skip_next:
            skip_next = False
            kept.append(tokens[pos])
            continue
        if keyword in ("INIT", "VALUE"):
            value = operand.strip()
            if value.startswith("(") and value.endswith(")"):
                value = value[1:-1].strip()
            unquoted = _pli_unquote(value)
            value = unquoted if unquoted is not None else (value or None)
            continue
        kept.append(tokens[pos])
        if keyword in ("FIXED", "FLOAT"):
            scale = keyword
            precision = precision or (operand or None)
        elif keyword in ("DEC", "BIN"):
            base = keyword
            precision = precision or (operand or None)
        elif keyword in _PLI_STRING_TYPES and string_type is None:
            string_type = keyword + operand
        elif keyword in ("VARYING", "VARYINGZ"):
            varying = keyword
        elif keyword in _PLI_LOCATOR_TYPES and locator is None:
            locator = keyword + operand
        elif keyword == "PIC":
            pic = _pli_unquote(operand)
        elif keyword == "DEF":
            target = operand.strip()[1:-1] if operand.strip().startswith("(") else ""
            if not target and pos + 1 < len(parsed):
                target, skip_next = tokens[pos + 1], True
            name = re.match(r"[\w@#$.]+", target.strip())
            redefines = name.group(0).upper() if name else None
        elif keyword == "DIM" and operand.startswith("("):
            dims = operand[1:-1]
        if keyword in _PLI_STORAGE_CLASSES and section is None:
            section = keyword

    if scale or base:
        usage: Optional[str] = " ".join(x for x in (scale, base) if x) + (precision or "")
    elif string_type:
        usage = string_type + (f" {varying}" if varying else "")
    else:
        usage = locator
    return {
        "usage": usage,
        "pic": pic,
        "value": value,
        "redefines": redefines,
        "section": section,
        "dims": dims,
        "attributes": " ".join(kept),
    }


def _pli_items(body: str) -> list[tuple[int, Optional[int], str, Optional[str], list[str]]]:
    """Split one DECLARE body into (offset, level, name, dims, attribute tokens) items.

    A factored declaration (`DCL (A, B) CHAR(5)`, `2 (X, Y) FIXED BIN`) expands to
    one item per name sharing the outer attributes. A `%INCLUDE` standing in for a
    structure's members (navikt/DSF: `DCL 1 B01 BASED(P), %INCLUDE P0019921;`) and
    a macro-built name (`DCL FIELD%;J ...`) are not items this file declares.
    """
    out = []
    for offset, piece in _pli_split(body, ","):
        i = _pli_skip_leading(piece)
        if i >= len(piece) or piece[i] == "%":
            continue
        level = None
        level_match = _PLI_LEVEL.match(piece, i)
        if level_match:
            level = int(level_match.group(1))
            i = level_match.end()
            while i < len(piece) and piece[i].isspace():
                i += 1
        names: list[tuple[int, str, list[str]]] = []
        if i < len(piece) and piece[i] == "(":
            close = _pli_balanced(piece, i)
            for inner_offset, part in _pli_split(piece[i + 1 : close - 1], ","):
                part_tokens = _pli_tokens(part)
                if part_tokens and _PLI_NAME.fullmatch(part_tokens[0]):
                    names.append((i + 1 + inner_offset, part_tokens[0], part_tokens[1:]))
            i = close
        else:
            name_match = _PLI_NAME.match(piece, i)
            if not name_match:
                continue
            if piece[name_match.end() : name_match.end() + 1] == "%":
                continue
            names.append((i, name_match.group(0).upper(), []))
            i = name_match.end()
        while i < len(piece) and piece[i].isspace():
            i += 1
        dims = None
        if i < len(piece) and piece[i] == "(":
            close = _pli_balanced(piece, i)
            dims = piece[i + 1 : close - 1]
            i = close
        outer = _pli_tokens(piece[i:])
        dims_text = f"({_pli_upper(dims)})" if dims is not None else None
        for name_offset, name, inner in names:
            tokens = ([dims_text] if dims_text else []) + inner + outer
            out.append((offset + name_offset, level, name, dims, tokens))
    return out


def _pli_records(code_stream: str) -> list[dict[str, Any]]:
    """The DECLAREd data items of one PL/I file as a record tree (#3250).

    Same flat, source-ordered shape as `_cobol_records` (the reader rebuilds the
    tree from `ordinal`/`parent_ordinal`), plus `attributes`. Every data
    declaration is an item -- a level-less scalar is a level-1 root, the PL/I
    analog of a COBOL 77 -- and a structure's members nest by level number. The
    root's storage class is its members' `section` (PL/I allows it only on
    level 1). Statements are accumulated to their `;` outside quotes first, so
    every pattern runs inside one bounded statement, the same reason the COBOL
    walker reads whole sentences. Block scope is not modelled: two procedures
    declaring the same name yield two roots, in source order.
    """
    text = _pli_blank_sequence_fields(code_stream)
    newlines = [i for i, ch in enumerate(text) if ch == "\n"]

    def _line_of(offset: int) -> int:
        return bisect.bisect_left(newlines, offset) + 1

    records: list[dict[str, Any]] = []
    in_macro = False
    for start, statement in _pli_split(text, ";"):
        i = _pli_skip_leading(statement)
        head = statement[i:]
        if in_macro:
            in_macro = not _PLI_MACRO_END.match(head)
            continue
        if _PLI_MACRO_PROC.match(head):
            in_macro = True
            continue
        declare = _PLI_DECLARE.match(head)
        if not declare:
            continue
        body_start = start + i + declare.end()
        stack: list[tuple[int, int, Optional[str]]] = []  # (level, ordinal, root storage class)
        for offset, level, name, dims, tokens in _pli_items(text[body_start : start + len(statement)]):
            fields = _pli_item_attributes(tokens)
            if fields is None:
                continue
            level = level or 1
            while stack and stack[-1][0] >= level:
                stack.pop()
            parent_ordinal = stack[-1][1] if stack else None
            section = stack[0][2] if stack else fields["section"]
            ordinal = len(records)
            stack.append((level, ordinal, section))
            occurs = depending = None
            first_dims = dims if dims is not None else fields["dims"]
            if first_dims is not None:
                occurs, depending = _pli_extent(first_dims)
            records.append(
                {
                    "section": section,
                    "fd_name": None,
                    "ordinal": ordinal,
                    "parent_ordinal": parent_ordinal,
                    "level": level,
                    "name": name,
                    "pic": fields["pic"],
                    "usage": fields["usage"],
                    "occurs_min": occurs,
                    "occurs_max": occurs,
                    "occurs_depending_on": depending,
                    "redefines": fields["redefines"],
                    "value": fields["value"],
                    "attributes": fields["attributes"] or None,
                    "line": _line_of(body_start + offset),
                }
            )
    return records


def _jcl_statements(code_stream: str) -> list[tuple[int, str, str, str]]:
    """Logical JCL statements as (line, name, operation, operands).

    A JCL statement continues onto the next `//` line when its operand field
    ends in a comma, so `//DD1 DD DSN=X,\\n//  UNIT=SYSDA` is one statement.
    In-stream payload (a line not starting with `//`) ends any continuation:
    it is data, not JCL, and jcl.py's own rules anchor the same way.
    """
    statements: list[tuple[int, str, str, str]] = []
    pending: Optional[list] = None

    for idx, line in enumerate(code_stream.split("\n"), start=1):
        stripped = line.rstrip()
        if not stripped.startswith("//"):
            pending = None
            continue
        if stripped.startswith("//*"):
            continue

        match = _JCL_STATEMENT.match(stripped)
        if match and match.group(2).upper() not in {"DD", "EXEC", "JOB", "PROC", "PEND", "SET", "INCLUDE", "JCLLIB"}:
            match = None

        if match:
            if pending:
                statements.append(tuple(pending))
            operands = (match.group(3) or "").strip()
            pending = [idx, match.group(1).upper(), match.group(2).upper(), operands]
            if not operands.endswith(","):
                statements.append(tuple(pending))
                pending = None
        elif pending:
            # A continuation line: `//` then blanks then more operands.
            continued = stripped[2:].strip()
            pending[3] = pending[3] + continued
            if not continued.endswith(","):
                statements.append(tuple(pending))
                pending = None

    if pending:
        statements.append(tuple(pending))
    return statements


def _jcl_boundary(code_stream: str) -> dict[str, list[dict[str, Any]]]:
    """JCL `EXEC PGM=` steps and the `DD` statements that bind a ddname to a dataset."""
    calls: list[dict[str, Any]] = []
    datasets: list[dict[str, Any]] = []
    step = ""
    last_dd = ""

    for line, name, operation, operands in _jcl_statements(code_stream):
        if operation == "EXEC":
            step = name
            last_dd = ""
            pgm = _JCL_EXEC_PGM.search(operands)
            if pgm:
                target = pgm.group(1).upper()
                calls.append(
                    {
                        "verb": "EXEC PGM",
                        "form": "literal",
                        "operand": target,
                        "target": target,
                        "line": line,
                    }
                )
        elif operation == "DD":
            # An unnamed DD concatenates onto the ddname above it, so the
            # binding belongs to that ddname rather than to nothing.
            dd_name = name or last_dd
            if name:
                last_dd = name
            dsn = _JCL_DSN.search(operands)
            if dd_name and dsn:
                datasets.append(
                    {
                        "internal_name": None,
                        "assign_name": None,
                        "dd_name": dd_name,
                        "modes": [],
                        "dsn": dsn.group(1).upper(),
                        "step_name": step or None,
                        "line": line,
                    }
                )

    return {"calls": calls, "datasets": datasets}


def _csd_attributes(record: str) -> dict[str, str]:
    """Every `KEYWORD(value)` attribute in one DEFINE record, first value winning.

    Paren-balanced and quote-aware because real attribute values carry commas
    (`WAITTIME(0,0,0)`), spaces and slashes (`DESCRIPTION('Credit/Debit')`) and
    the audit trailers embed spaces (`DEFINETIME(22/06/10 20:05:10)`). A flat
    `KEYWORD\\(([^)]*)\\)` would truncate the first and misread the rest.
    """
    attrs: dict[str, str] = {}
    for m in _CSD_ATTR_KEY.finditer(record):
        key = m.group(1).upper()
        key = _CSD_ATTR_SYNONYMS.get(key, key)
        depth = 1
        i = m.end()
        quote: Optional[str] = None
        chars: list[str] = []
        while i < len(record) and depth > 0:
            ch = record[i]
            if quote is not None:
                if ch == quote:
                    quote = None
                chars.append(ch)
            elif ch in "'\"":
                quote = ch
                chars.append(ch)
            elif ch == "(":
                depth += 1
                chars.append(ch)
            elif ch == ")":
                depth -= 1
                if depth > 0:
                    chars.append(ch)
            else:
                chars.append(ch)
            i += 1
        # First declaration wins, matching the value-map reading elsewhere: a
        # keyword repeated in one record is DFHCSDUP-illegal, so the first is it.
        attrs.setdefault(key, "".join(chars).strip())
    return attrs


def _csd_records(code_stream: str) -> list[tuple[int, str]]:
    """Split a CSD deck into (1-based start line, record text) DEFINE records.

    A CSD record has NO continuation character: a DEFINE runs until the next
    command, a `*` (or `//*`) comment, a JCL `//` statement line, a blank line,
    or end of deck. That tolerance is what lets ONE reader serve a standalone
    `.csd` file, a hand-written DFHCSDUP SYSIN member and the inline SYSIN inside
    a JCL job -- in the last, the `SET`/`EXEC`/`DD` control lines all begin `//`
    and so cleanly separate the DEFINE records they surround.
    """
    records: list[tuple[int, list[str]]] = []
    current: Optional[tuple[int, list[str]]] = None

    def _flush() -> None:
        nonlocal current
        if current is not None:
            records.append(current)
            current = None

    for lineno, raw in enumerate(code_stream.split("\n"), start=1):
        stripped = raw.strip()
        # A JCL control/comment line, a CSD `*` comment, or a blank line ends the
        # record in progress and is never part of one.
        if not stripped or stripped.startswith("*") or raw.lstrip().startswith("//"):
            _flush()
            continue
        command = _CSD_COMMAND.match(raw)
        if command:
            _flush()
            if command.group(1).upper() == "DEFINE":
                current = (lineno, [raw])
            # A DELETE/ADD/LIST/... command starts no record we keep; it only
            # terminated the one above.
            continue
        # A continuation/attribute line belongs to the DEFINE in progress.
        if current is not None:
            current[1].append(raw)

    _flush()
    return [(start, "\n".join(lines)) for start, lines in records]


def _csd_transactions(code_stream: str) -> list[dict[str, Any]]:
    """The CICS transaction map: transaction id -> program, from a CSD deck.

    Two record shapes yield the same fact:
      - `DEFINE TRANSACTION(TTTT) ... PROGRAM(PPPP)` -- the transaction names its
        program directly.
      - `DEFINE PROGRAM(PPPP) ... TRANSID(TTTT)` -- an autoinstall pairing that
        declares the same edge from the program's side (carddemo's inline JCL).
    `DEFINE DB2TRAN(...)` also carries a `TRANSID(...)`, but that is a DB2 plan
    attribute, not a CICS transaction definition, and is excluded.
    """
    out: list[dict[str, Any]] = []
    for line_no, record in _csd_records(code_stream):
        head = _CSD_DEFINE_HEAD.match(record)
        if not head:
            continue
        resource = head.group(1).upper()
        name = head.group(2).upper()
        if resource in _CSD_EXCLUDED_RESOURCES:
            continue
        attrs = _csd_attributes(record)
        if resource == _CSD_TXN_RESOURCE:
            transid, program = name, (attrs.get("PROGRAM") or "").upper() or None
        elif resource == _CSD_PGM_RESOURCE and attrs.get("TRANSID"):
            transid, program = attrs["TRANSID"].upper(), name
        else:
            continue
        out.append(
            {
                "transid": transid,
                "program": program,
                "group": (attrs.get("GROUP") or "").upper() or None,
                "profile": (attrs.get("PROFILE") or "").upper() or None,
                "line": line_no,
            }
        )
    out.sort(key=lambda t: (t["line"], t["transid"]))
    return out


def _jcl_csd_transactions(code_stream: str) -> list[dict[str, Any]]:
    """A DFHCSDUP SYSIN deck carried inline in a JCL job, or [] if the job is not one.

    The DEFINE records sit in the in-stream `//SYSIN DD *` payload; `_csd_records`
    already treats every `//` control line as a separator, so handing it the whole
    job reads the deck and ignores the JCL around it. A job that runs DFHCSDUP but
    points SYSIN at a separate member (a `.csd` file the csd dialect reads on its
    own) simply has no inline DEFINEs and yields nothing here -- no double count.
    """
    if not _DFHCSDUP.search(code_stream):
        return []
    return _csd_transactions(code_stream)


def extract_boundary(dialect: str, code_stream: str) -> dict[str, list[dict[str, Any]]]:
    """The named invocation, dataset, record-layout and transaction facts for one mainframe file.

    `dialect` is the language's `boundary_extraction` declaration, not its
    language id, so a future dialect can share COBOL's reading without being
    named cobol. Every return carries all four keys (`calls`, `datasets`,
    `records`, `transactions`) so the caller reads a uniform shape; a dialect that
    carries only some channels (JCL has no record layouts; CSD only transactions;
    PL/I only records, #3250) fills the rest with empty lists, and an unrecognised
    declaration degrades to "no facts" rather than raising in a worker.

    #3344: cobol and pli additionally carry `sql_tables` -- the DB2 `EXEC SQL
    DECLARE <table> TABLE (...)` columns (db2_declare_table). Callers read it
    with a default, so the dialects that cannot embed SQL simply omit it.
    """
    if not code_stream:
        return {"calls": [], "datasets": [], "records": [], "transactions": []}
    if dialect == "cobol":
        values = _cobol_value_map(code_stream)
        return {
            "calls": _cobol_calls(code_stream, values),
            "datasets": _cobol_datasets(code_stream),
            "records": _cobol_records(code_stream),
            "transactions": [],
            "sql_tables": extract_sql_tables(code_stream, "cobol"),  # #3344
        }
    if dialect == "jcl":
        boundary = _jcl_boundary(code_stream)
        boundary["records"] = []
        boundary["transactions"] = _jcl_csd_transactions(code_stream)
        return boundary
    if dialect == "csd":
        return {"calls": [], "datasets": [], "records": [], "transactions": _csd_transactions(code_stream)}
    if dialect == "pli":
        return {
            "calls": [],
            "datasets": [],
            "records": _pli_records(code_stream),
            "transactions": [],
            "sql_tables": extract_sql_tables(code_stream, "pli"),  # #3344
        }
    if dialect == "bms":
        # #3347: BMS map field layouts ride their own key (`screen_fields`), read
        # by the caller with a default -- no other dialect carries it.
        return {
            "calls": [],
            "datasets": [],
            "records": [],
            "transactions": [],
            "screen_fields": bms_screen_fields(code_stream),
        }
    return {"calls": [], "datasets": [], "records": [], "transactions": []}
