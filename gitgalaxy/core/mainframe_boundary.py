# ==============================================================================
# GitGalaxy Core: Mainframe Boundary Extraction (#3200, #3201, #3246, #3211-followup, #3250)
# (+ #3351-#3354: EXEC CICS resource operations, extracted by core/cics_resources.py
#  and returned from extract_boundary as `cics_resources`)
#
# PURPOSE:
# The counted rules tell you THAT a COBOL program calls something and THAT a JCL
# job allocates a dataset (`ipc_rpc_bridges` -> arch_ipc, `io` -> arch_io). They
# never say WHAT. This module is the named channel for the mainframe relations
# that the hit counts flatten:
#
#   1. invocation  -- COBOL `CALL`, CICS `LINK`/`XCTL PROGRAM(...)`, JCL
#                     `EXEC PGM=`: who runs whom (#3200).
#                     A CICS LINK/XCTL/RETURN TRANSID site also carries
#                     the record it passes -- `COMMAREA(x)` with its
#                     `LENGTH(...)`/`DATALENGTH(...)` as written (#3355).
#   2. dataset     -- COBOL `SELECT ... ASSIGN TO <ddname>` with the `OPEN`
#                     modes actually used, and the JCL `DD` statement that binds
#                     that ddname to a real dataset (#3201). A JCL DSN built
#                     from symbolic parameters (`SET`, PROC defaults, EXEC
#                     overrides, `&SYM.`) is also resolved where one file
#                     determines it, beside the raw DSN (#3345).
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
#                     Since #3356 the same CSD records are also kept whole, one
#                     row per DEFINE of any resource type (FILE -> DSNAME,
#                     TDQUEUE -> DDNAME/DSNAME, DB2TRAN -> DB2ENTRY -> PLAN,
#                     MAPSET, LIBRARY, URIMAP, ...), as `csd_resources`.
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

# #3351-#3354: CICS resource operations (FILE/MAP/QUEUE/CONTAINER/CHANNEL) live in
# their own module and ride out of extract_boundary as `cics_resources`.
from gitgalaxy.core.call_using import blank_stream, call_using_args, entry_points
from gitgalaxy.core.cics_resources import cobol_move_literals, extract_cics_resources
from gitgalaxy.core.cics_tasks import extract_cics_tasks
from gitgalaxy.core.db2_declare_table import extract_sql_tables
from gitgalaxy.core.db2_sql_statements import extract_sql_statements
from gitgalaxy.core.file_control import cobol_file_control, jcl_vsam_defines
from gitgalaxy.core.job_flow import jcl_job_flow
from gitgalaxy.core.job_submits import cobol_job_cards, jcl_intrdr_dds
from gitgalaxy.core.mq_calls import extract_mq_calls
from gitgalaxy.core.uow_handlers import extract_uow_handlers

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

# #3355: the COMMAREA contract operands of a LINK/XCTL/RETURN block -- which
# record the call passes (`COMMAREA(x)`) and how many bytes it says it passes
# (`LENGTH(...)`, and LINK's `DATALENGTH(...)`). Each keyword is delimited by COBOL
# name-character boundaries, so `DFHCOMMAREA(` is not a COMMAREA operand and
# `DATALENGTH(` / `INPUTMSGLEN(` are not LENGTH. The operand body is read by a
# paren-balanced scan (`LENGTH(LENGTH OF X)`, `COMMAREA(WS-AREA(1:10))`) capped at
# `_CICS_OPERAND_LIMIT`, inside the already END-EXEC-bounded block.
_CICS_CONTRACT_OPERANDS = (
    ("commarea", re.compile(r"(?<![A-Z0-9-])COMMAREA[ \t\n]*\(", re.I)),
    ("commarea_length", re.compile(r"(?<![A-Z0-9-])LENGTH[ \t\n]*\(", re.I)),
    ("commarea_datalength", re.compile(r"(?<![A-Z0-9-])DATALENGTH[ \t\n]*\(", re.I)),
)
_CICS_OPERAND_LIMIT = 160

# A JCL statement: `//name operation operands`. The name field is optional --
# unnamed DD and EXEC statements are valid and common.
_JCL_STATEMENT = re.compile(r"^//([A-Z0-9_#$@]*)[ \t]+([A-Z]+)(?:[ \t]+(.*))?$", re.I)
# `EXEC PGM=X`. `EXEC name` / `EXEC PROC=name` invoke a PROCEDURE, not a
# program: jcl.py's `api` rule already owns that relation and #3200 asks for
# PGM= specifically.
_JCL_EXEC_PGM = re.compile(r"\bPGM=([A-Z0-9_#$@]+)", re.I)
# `DSN=`/`DSNAME=` on a DD. `&&NAME` is a job-local temporary dataset and `*`
# opens an in-stream payload -- neither is an external binding, and jcl.py's
# `_dependency_capture` already excludes both for the same reason. `+` is in the
# class for a relative GDG generation (`DSN=X.BKUP(+1)`), which it used to cut to
# `X.BKUP(` (#3345).
_JCL_DSN = re.compile(r"\bDSN(?:AME)?=(?!(?:&&|\*))([A-Z0-9_#$@.&()+-]+)", re.I)

# ---- #3345: JCL symbolic-parameter resolution -------------------------------
# A symbol reference: `&NAME` (1-8 chars) with an optional delimiting period that
# substitution consumes (`&HLQ..DATA` -> `PROD.DATA`). `&&` is matched first so a
# temporary-dataset prefix is never read as a symbol. Bounded: {0,7}.
_JCL_SYMBOL_REF = re.compile(r"&&|&([A-Z@#$][A-Z0-9@#$]{0,7})(\.?)", re.I)
# `KEY=` at the head of one operand. A dotted key (`PARM.STEP1=`) is an EXEC
# keyword aimed at a procedure step, never a symbol; the class admits the dot so
# the caller can see and skip it.
_JCL_OPERAND_KEY = re.compile(r"([A-Z@#$][A-Z0-9@#$.]{0,24})=", re.I)
# EXEC keywords: an `EXEC proc,KEY=value` operand with one of these names is a
# step parameter, not a symbolic-parameter override.
_JCL_EXEC_KEYWORDS = frozenset(
    {
        "PGM",
        "PROC",
        "PARM",
        "PARMDD",
        "COND",
        "REGION",
        "REGIONX",
        "TIME",
        "ACCT",
        "ADDRSPC",
        "DPRTY",
        "PERFORM",
        "RD",
        "CCSID",
        "DYNAMNBR",
        "MEMLIMIT",
        "TVSMSG",
        "TVSAMCOM",
    }
)
# A PROC default may name other symbols (`CPYBKS=&HLQ..CPY`); resolution follows
# them at most this deep, so a self- or mutually-referencing chain ends as
# `unresolved` rather than recursing.
_JCL_RESOLVE_DEPTH = 8

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
# #3355: `COPY <member>` inside one data-description entry's window -- the
# copybook that expands at that point (`01 DFHCOMMAREA.` + `COPY INQCUST.`). The
# member is recorded on the entry it follows (`copy_members`); expanding it is the
# reader's job (galaxy_ir), exactly as for every other cross-file layout. Quotes
# and a trailing `OF/IN library` are allowed; the member name is what is kept.
_COPY_IN_ENTRY = re.compile(r"(?<![A-Z0-9-])COPY[ \t\n]+['\"]?([A-Z0-9@#$][A-Z0-9@#$-]*)", re.I)
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
# #3356: the longest value `_csd_attributes` will scan before calling it unterminated.
_CSD_VALUE_MAX = 1024
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


def _cics_contract_operands(block: str) -> dict[str, str]:
    """The COMMAREA / LENGTH / DATALENGTH operands of one CICS block, as written (#3355).

    `block` is the text between the verb and END-EXEC. Each operand body is read
    to its balancing `)` (at most `_CICS_OPERAND_LIMIT` chars -- an unbalanced
    paren yields nothing rather than a runaway), whitespace-collapsed and
    upper-cased. Only the operands the block carries are returned, so a site with
    no COMMAREA keeps exactly the shape it had before #3355.
    """
    out: dict[str, str] = {}
    for key, pattern in _CICS_CONTRACT_OPERANDS:
        match = pattern.search(block)
        if not match:
            continue
        depth, body_end = 1, None
        limit = min(len(block), match.end() + _CICS_OPERAND_LIMIT)
        for i in range(match.end(), limit):
            ch = block[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    body_end = i
                    break
        if body_end is None:
            continue
        body = " ".join(block[match.end() : body_end].split()).upper()
        if body:
            out[key] = body
    return out


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
        # #3355: the record this transfer passes, and its declared length(s).
        contract = _cics_contract_operands(block)
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
                    **contract,
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
                **contract,
            }
        )

    blanked: list[str] = []

    def _using(end: int) -> dict[str, str]:
        """#3454: the CALL's USING list, only when it has one (so a CALL without
        USING keeps its pre-#3454 shape). The sequence-blanked stream is built once."""
        if not blanked:
            blanked.append(blank_stream(code_stream))
        args = call_using_args(blanked[0], end)
        return {"using_args": args} if args else {}

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
                **_using(match.end()),  # #3454
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
                **_using(match.end()),  # #3454
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
                # #3355: `RETURN TRANSID(t) COMMAREA(x)` hands x to the next task
                # of t. Plain RETURN (no TRANSID) draws no row, and none is added
                # for it: that would change the call graph (#3355 keeps it
                # byte-identical) for a COMMAREA with no named receiver.
                **_cics_contract_operands(block),
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

        # #3355: the copybook(s) that expand right after this entry. Searched only
        # up to the next section header / FD and the PROCEDURE DIVISION, so a
        # section-level `LINKAGE SECTION.` + `COPY X.` (a COPY that belongs to no
        # entry) and a procedure-division COPY are never attributed to the entry
        # above them.
        copy_stop = min(stop, level_match.end() + _ENTRY_LIMIT, data_end)
        for offsets in (section_offsets, fd_offsets):
            nxt = bisect.bisect_right(offsets, level_match.end())
            if nxt < len(offsets):
                copy_stop = min(copy_stop, offsets[nxt])
        copy_window = code_stream[level_match.end() : max(copy_stop, level_match.end())]
        copy_members = [m.group(1).upper() for m in _COPY_IN_ENTRY.finditer(copy_window)]

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
                # Presence-keyed: an entry with no COPY after it keeps its pre-#3355 shape.
                **({"copy_members": ",".join(copy_members)} if copy_members else {}),
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


def _jcl_operand_field(text: str) -> str:
    """The operand field of one JCL line: everything up to the first blank that
    is not inside apostrophes. What follows that blank is a comment
    (`// SET HLQ='IBMUSER'   *TSO USER ID`), never an operand (#3345)."""
    quoted = False
    for idx, ch in enumerate(text):
        if ch == "'":
            quoted = not quoted
        elif not quoted and ch in " \t":
            return text[:idx]
    return text


def _jcl_statements(code_stream: str) -> list[tuple[int, str, str, str]]:
    """Logical JCL statements as (line, name, operation, operands).

    A JCL statement continues onto the next `//` line when its operand field
    ends in a comma, so `//DD1 DD DSN=X,\\n//  UNIT=SYSDA` is one statement.
    In-stream payload (a line not starting with `//`) ends any continuation:
    it is data, not JCL, and jcl.py's own rules anchor the same way -- but it
    ENDS the statement, it does not discard it. An empty line is a `//*` comment
    PRISM blanked, so it neither ends nor breaks a continuation: `//S EXEC
    PGM=X,` / `//* note` / `//  PARM=Y` is still one EXEC. Only the operand FIELD
    is kept: a comment after it (`//P PROC M=,   NAME - REQUIRED`) neither hides
    the continuing comma nor joins the operands (#3345).
    """
    statements: list[tuple[int, str, str, str]] = []
    pending: Optional[list] = None

    for idx, line in enumerate(code_stream.split("\n"), start=1):
        stripped = line.rstrip()
        if not stripped:
            continue
        if not stripped.startswith("//"):
            if pending:
                statements.append(tuple(pending))
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
            operands = _jcl_operand_field((match.group(3) or "").strip())
            pending = [idx, match.group(1).upper(), match.group(2).upper(), operands]
            if not operands.endswith(","):
                statements.append(tuple(pending))
                pending = None
        elif pending:
            # A continuation line: `//` then blanks then more operands.
            continued = _jcl_operand_field(stripped[2:].strip())
            pending[3] = pending[3] + continued
            if not continued.endswith(","):
                statements.append(tuple(pending))
                pending = None

    if pending:
        statements.append(tuple(pending))
    return statements


def _jcl_operands(field: str) -> list[tuple[Optional[str], str]]:
    """One operand field split on its top-level commas into (KEY, value) pairs.

    Commas inside apostrophes or parentheses do not split
    (`SPACE1='SYSALLDA,SPACE=(CYL,(1,1))'`). A positional operand (the procedure
    name in `EXEC MYPROC,HLQ=X`) comes back with a None key.
    """
    parts: list[str] = []
    depth = 0
    quoted = False
    start = 0
    for idx, ch in enumerate(field):
        if ch == "'":
            quoted = not quoted
        elif quoted:
            continue
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            parts.append(field[start:idx])
            start = idx + 1
    parts.append(field[start:])

    out: list[tuple[Optional[str], str]] = []
    for part in parts:
        key = _JCL_OPERAND_KEY.match(part)
        if key:
            out.append((key.group(1).upper(), part[key.end() :]))
        elif part:
            out.append((None, part))
    return out


def _jcl_unquote(value: str) -> str:
    """`'IBMUSER'` -> `IBMUSER`, with `''` read as one apostrophe."""
    if len(value) >= 2 and value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    return value


def _jcl_symbol_table(operands: str, keep_null: bool) -> dict[str, str]:
    """The `NAME=value` symbol assignments of one SET / PROC / EXEC operand field.

    `keep_null` decides what `NAME=` (a null value) means. On SET and on an EXEC
    override it nullifies the symbol, which is a real value. On a PROC statement
    it is the "caller must supply this" convention (`//BLDBAT PROC MEM=,HLQ=`),
    so it is left undefined rather than silently substituting nothing.
    """
    table: dict[str, str] = {}
    for key, value in _jcl_operands(operands):
        if not key or "." in key or len(key) > 8:
            continue
        if value == "" and not keep_null:
            continue
        table[key] = _jcl_unquote(value)
    return table


def _jcl_substitute(text: str, table: dict[str, str], depth: int = 0) -> tuple[str, bool]:
    """`text` with every `&SYM`/`&SYM.` replaced from `table`, and whether every
    reference resolved. A symbol's value is itself resolved (a PROC default may
    name another symbol) up to `_JCL_RESOLVE_DEPTH`; a missing symbol, a `&&`
    and a chain that runs too deep each leave the reference as written."""
    complete = True

    def _replace(match: "re.Match[str]") -> str:
        nonlocal complete
        name = (match.group(1) or "").upper()
        if not name or name not in table or depth >= _JCL_RESOLVE_DEPTH:
            complete = False
            return match.group(0)
        value, ok = _jcl_substitute(table[name], table, depth + 1)
        if not ok:
            complete = False
        return value

    return _JCL_SYMBOL_REF.sub(_replace, text), complete


def _jcl_resolve_dsn(dsn: str, table: dict[str, str]) -> Optional[str]:
    """The DSN with its symbols substituted, or None unless every one resolved.

    After substitution JCL re-reads the operand, so a blank or comma a value
    carried ends the DSN (`SET MACLIB='SYS1.MACLIB   '` -> `SYS1.MACLIB`)."""
    text, complete = _jcl_substitute(dsn, table)
    if not complete:
        return None
    resolved = re.split(r"[ \t,]", text, maxsplit=1)[0].upper()
    return resolved or None


def _jcl_resolve_datasets(
    job_rows: list[tuple[dict[str, Any], dict[str, str]]],
    procs: list[dict[str, Any]],
) -> None:
    """Sets `dsn_resolved`/`dsn_resolution` on every JCL DD binding (#3345).

    `dsn` itself is never touched: it stays the DSN as written. `dsn_resolution`:

      literal       no symbol in the DSN; `dsn_resolved` is the DSN.
      resolved      every symbol resolved from this file -- job-level SETs, or an
                    in-stream PROC every one of whose in-file invocations agrees.
      proc_default  a PROC's DD resolved only through the PROC's own defaults
                    (a cataloged-PROC member, or an in-stream PROC this file never
                    invokes): a caller in another member may override them.
      ambiguous     an in-stream PROC invoked here with values that disagree.
      unresolved    some symbol has no value in this file (a system symbol such as
                    `&SYSUID`, or a value only a cross-member caller supplies).

    Precedence inside a procedure is EXEC override > PROC default > SET.
    """

    def _mark(row: dict[str, Any], resolved: Optional[str], status: str) -> None:
        row["dsn_resolved"] = resolved
        row["dsn_resolution"] = status

    for row, table in job_rows:
        if "&" not in row["dsn"]:
            _mark(row, row["dsn"], "literal")
            continue
        resolved = _jcl_resolve_dsn(row["dsn"], table)
        _mark(row, resolved, "resolved" if resolved else "unresolved")

    for proc in procs:
        for row, local_sets in proc["rows"]:
            if "&" not in row["dsn"]:
                _mark(row, row["dsn"], "literal")
                continue
            if not proc["invocations"]:
                table = {**proc["job_sets"], **local_sets, **proc["defaults"]}
                resolved = _jcl_resolve_dsn(row["dsn"], table)
                _mark(row, resolved, "proc_default" if resolved else "unresolved")
                continue
            results = {
                _jcl_resolve_dsn(row["dsn"], {**job_sets, **local_sets, **proc["defaults"], **overrides})
                for job_sets, overrides in proc["invocations"]
            }
            if None in results:
                _mark(row, None, "unresolved")
            elif len(results) > 1:
                _mark(row, None, "ambiguous")
            else:
                _mark(row, results.pop(), "resolved")


def _jcl_boundary(code_stream: str) -> dict[str, list[dict[str, Any]]]:
    """JCL `EXEC PGM=` steps and the `DD` statements that bind a ddname to a dataset.

    #3345: alongside the walk it keeps the file's symbol tables -- job-level
    `SET`s in source order, each PROC's defaults and in-body SETs, and every
    in-file invocation of an in-stream PROC with its EXEC overrides -- so each
    binding's DSN can be resolved once the whole file has been read.
    """
    calls: list[dict[str, Any]] = []
    datasets: list[dict[str, Any]] = []
    step = ""
    last_dd = ""
    job_seen = False
    job_sets: dict[str, str] = {}
    job_rows: list[tuple[dict[str, Any], dict[str, str]]] = []
    procs: list[dict[str, Any]] = []
    procs_by_name: dict[str, dict[str, Any]] = {}
    current: Optional[dict[str, Any]] = None

    for line, name, operation, operands in _jcl_statements(code_stream):
        if operation == "JOB":
            job_seen = True
        elif operation == "SET":
            # A SET value is substituted when the SET is read, against what is
            # in effect then -- so `SET HLQ=&HLQ..X` cannot refer to itself.
            scope = current["sets"] if current is not None else job_sets
            for key, value in _jcl_symbol_table(operands, keep_null=True).items():
                scope[key] = _jcl_substitute(value, {**job_sets, **scope})[0]
        elif operation == "PROC":
            # A PROC before any JOB is a cataloged-procedure member; after one it
            # is in-stream and ends at PEND.
            current = {
                "defaults": _jcl_symbol_table(operands, keep_null=False),
                "sets": {},
                "rows": [],
                "invocations": [],
                "instream": job_seen,
                "job_sets": dict(job_sets),
            }
            procs.append(current)
            if name and job_seen:
                procs_by_name[name] = current
            step = ""
            last_dd = ""
        elif operation == "PEND":
            current = None
            step = ""
            last_dd = ""
        elif operation == "EXEC":
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
            elif current is None:
                ops = _jcl_operands(operands)
                proc_name = next((v for k, v in ops if k == "PROC"), None) or next(
                    (v for k, v in ops if k is None), None
                )
                invoked = procs_by_name.get((proc_name or "").upper())
                if invoked is not None:
                    # Overrides are substituted in the CALLER's context, so
                    # `EXEC P,HLQ=&HLQ` passes the job's HLQ, not itself.
                    overrides = {
                        k: _jcl_substitute(v, job_sets)[0]
                        for k, v in _jcl_symbol_table(operands, keep_null=True).items()
                        if k not in _JCL_EXEC_KEYWORDS
                    }
                    invoked["invocations"].append((dict(job_sets), overrides))
        elif operation == "DD":
            # An unnamed DD concatenates onto the ddname above it, so the
            # binding belongs to that ddname rather than to nothing.
            dd_name = name or last_dd
            if name:
                last_dd = name
            dsn = _JCL_DSN.search(operands)
            if dd_name and dsn:
                row: dict[str, Any] = {
                    "internal_name": None,
                    "assign_name": None,
                    "dd_name": dd_name,
                    "modes": [],
                    "dsn": dsn.group(1).upper(),
                    "step_name": step or None,
                    "line": line,
                }
                datasets.append(row)
                if current is not None:
                    current["rows"].append((row, dict(current["sets"])))
                else:
                    job_rows.append((row, dict(job_sets)))

    _jcl_resolve_datasets(job_rows, procs)
    return {"calls": calls, "datasets": datasets}


def _csd_attributes(record: str) -> dict[str, str]:
    """Every `KEYWORD(value)` attribute in one DEFINE record, first value winning.

    Paren-balanced and quote-aware because real attribute values carry commas
    (`WAITTIME(0,0,0)`), spaces and slashes (`DESCRIPTION('Credit/Debit')`) and
    the audit trailers embed spaces (`DEFINETIME(22/06/10 20:05:10)`). A flat
    `KEYWORD\\(([^)]*)\\)` would truncate the first and misread the rest.
    """
    attrs: dict[str, str] = {}
    pos = 0
    # #3356: resume the keyword search AFTER each value, so a `WORD(` inside a
    # value (`DESCRIPTION(RETRY FOR PLAN(X))`) is never read as an attribute.
    while (m := _CSD_ATTR_KEY.search(record, pos)) is not None:
        key = m.group(1).upper()
        key = _CSD_ATTR_SYNONYMS.get(key, key)
        depth = 1
        i = m.end()
        # #3356: bound the value scan. The longest CSD operand is a 255-char path
        # (URIMAP PATH, PIPELINE CONFIGFILE); a value still open after this many
        # characters is unterminated, and without the bound a record of stray
        # parens or quotes rescans to its end from every keyword (quadratic).
        stop = min(len(record), i + _CSD_VALUE_MAX)
        quote: Optional[str] = None
        chars: list[str] = []
        while i < stop and depth > 0:
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
        # An unterminated value (a stray apostrophe: `DESCRIPTION(Bank's file)`)
        # ran to the end of the record; resume right after its keyword instead,
        # so the attributes after it are still found.
        pos = i if depth == 0 else m.end()
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


def _csd_int(value: Optional[str]) -> Optional[int]:
    """A numeric CSD attribute (`KEYLENGTH(16)`), or None when absent or not a number."""
    value = (value or "").strip()
    return int(value) if value.isdigit() and len(value) <= 9 else None


def _csd_upper(value: Optional[str]) -> Optional[str]:
    """A name-valued CSD attribute, upper-cased, or None when absent or empty."""
    return (value or "").strip().upper() or None


def _csd_resources(code_stream: str) -> list[dict[str, Any]]:
    """Every CSD `DEFINE <type>(<name>)` record as one resource row (#3356).

    The transaction map (`_csd_transactions`) keeps only the transaction ->
    program routing. This is the whole resource inventory the same records
    declare, one generic row per DEFINE of ANY type -- FILE, MAPSET, TDQUEUE,
    DB2ENTRY/DB2TRAN/DB2CONN, LIBRARY, URIMAP, WEBSERVICE, PIPELINE,
    TCPIPSERVICE, ... and TRANSACTION/PROGRAM too, whose non-routing attributes
    (LANGUAGE, DATALOCATION, TWASIZE) the map drops. The attributes that JOIN the
    online system to something else are lifted into their own keys; everything
    else rides in `attributes`, the record's full operand text:

      - `dsname`        FILE / TDQUEUE `DSNAME`, LIBRARY `DSNAME01` (the first of
                        its concatenation) -- the dataset, joinable to JCL lineage
      - `ddname`        TDQUEUE `DDNAME` -- bound by the CICS region's own JCL
      - `record_format` / `key_length` / `record_size`  FILE and TDQUEUE shape
      - `queue_type`    TDQUEUE `TYPE` (EXTRA / INTRA / INDIRECT)
      - `plan`          DB2ENTRY / DB2CONN `PLAN`
      - `db2_entry`     DB2TRAN `ENTRY` -- the DB2ENTRY it assigns its transid to
      - `transid`       the transaction the resource names: a TRANSACTION's own
                        name, `TRANSID(...)` (PROGRAM autoinstall, DB2TRAN), or a
                        `TRANSACTION(...)` operand (TCPIPSERVICE, URIMAP)
      - `program`       a PROGRAM's own name, or a `PROGRAM(...)` operand
                        (TRANSACTION, URIMAP)

    `attributes` is the record text after `DEFINE <type>(<name>)` with every
    whitespace run folded to one blank (a CSD record has no continuation
    character, so its line breaks carry no meaning). Nothing is resolved here:
    joining a FILE's DSNAME to dataset_data or a DB2TRAN to its DB2ENTRY is the
    reader's job (galaxy_ir), as for every other channel.
    """
    out: list[dict[str, Any]] = []
    for line_no, record in _csd_records(code_stream):
        head = _CSD_DEFINE_HEAD.match(record)
        if not head:
            continue
        resource = head.group(1).upper()
        name = head.group(2).upper()
        attrs = _csd_attributes(record[head.end() :])
        if resource == _CSD_TXN_RESOURCE:
            transid: Optional[str] = name
        else:
            transid = _csd_upper(attrs.get("TRANSID") or attrs.get("TRANSACTION"))
        program = name if resource == _CSD_PGM_RESOURCE else _csd_upper(attrs.get("PROGRAM"))
        out.append(
            {
                "resource_type": resource,
                "name": name,
                "group": _csd_upper(attrs.get("GROUP")),
                "dsname": _csd_upper(attrs.get("DSNAME") or attrs.get("DSNAME01")),
                "ddname": _csd_upper(attrs.get("DDNAME")),
                "record_format": _csd_upper(attrs.get("RECORDFORMAT")),
                "key_length": _csd_int(attrs.get("KEYLENGTH")),
                "record_size": _csd_int(attrs.get("RECORDSIZE")),
                "queue_type": _csd_upper(attrs.get("TYPE")) if resource == "TDQUEUE" else None,
                "plan": _csd_upper(attrs.get("PLAN")),
                "db2_entry": _csd_upper(attrs.get("ENTRY")) if resource == "DB2TRAN" else None,
                "transid": transid,
                "program": program,
                "attributes": " ".join(record[head.end() :].split()) or None,
                "line": line_no,
            }
        )
    return out


def _jcl_csd_resources(code_stream: str) -> list[dict[str, Any]]:
    """The CSD resources of a DFHCSDUP SYSIN deck inline in a JCL job (#3356), or [].

    Same gate as `_jcl_csd_transactions`: only a job that runs DFHCSDUP carries a
    deck, and one that points SYSIN at a separate member yields nothing here."""
    if not _DFHCSDUP.search(code_stream):
        return []
    return _csd_resources(code_stream)


def _pli_value_map(records: list[dict[str, Any]]) -> dict[str, str]:
    """PL/I name -> its `INIT`/`VALUE` string (first declaration wins), the PL/I
    analog of `_cobol_value_map` for CICS operand resolution (#3351-#3354).

    `_pli_records` has already unquoted a string INIT; a numeric one (`INIT(0)`)
    is never a resource name and is skipped."""
    values: dict[str, str] = {}
    for item in records:
        value = item.get("value")
        name = item.get("name")
        if not name or not isinstance(value, str):
            continue
        text = value.strip()
        if text and not re.fullmatch(r"[-+]?[0-9.]+", text):
            values.setdefault(name.upper(), text)
    return values


def _cics_resources(code_stream: str, values: dict[str, str], dialect: str) -> list[dict[str, Any]]:
    """The CICS FILE/MAP/QUEUE/CONTAINER/CHANNEL operations of one file (#3351-#3354).

    Operands resolve through the same-file VALUE map (as LINK targets do), then a
    single MOVEd literal (COBOL only); an `EXEC CICS` inside a literal is skipped.
    """
    if "CICS" not in code_stream.upper():
        return []
    newlines = [i for i, ch in enumerate(code_stream) if ch == "\n"]

    def _shielded(offset: int) -> bool:
        index = bisect.bisect_left(newlines, offset)
        line_start = newlines[index - 1] + 1 if index else 0
        return _opens_inside_literal(code_stream, line_start, offset)

    moves = cobol_move_literals(code_stream) if dialect == "cobol" else {}
    return extract_cics_resources(code_stream, values, moves, dialect, _shielded)


def _cics_tasks(
    code_stream: str, values: dict[str, str], records: list[dict[str, Any]], dialect: str
) -> list[dict[str, Any]]:
    """The CICS task-control commands of one file (#3449): RUN/START children,
    FETCH/FREE joins, RETRIEVE, CANCEL, DELAY, POST, WAIT and ENQ/DEQ.

    Operands resolve as in `_cics_resources`; a COBOL transaction id built by
    STRING becomes a pattern sized by each source's PIC (`records`).
    """
    if "CICS" not in code_stream.upper():
        return []
    newlines = [i for i, ch in enumerate(code_stream) if ch == "\n"]

    def _shielded(offset: int) -> bool:
        index = bisect.bisect_left(newlines, offset)
        line_start = newlines[index - 1] + 1 if index else 0
        return _opens_inside_literal(code_stream, line_start, offset)

    moves = cobol_move_literals(code_stream) if dialect == "cobol" else {}
    pics: dict[str, str] = {}
    for r in records:
        if r.get("name") and r.get("pic"):
            pics.setdefault(str(r["name"]).upper(), str(r["pic"]))
    return extract_cics_tasks(code_stream, values, moves, pics, dialect, _shielded)


def _uow_handlers(code_stream: str, values: dict[str, str]) -> list[dict[str, Any]]:
    """Commit / rollback points, HANDLE CONDITION / ABEND / AID handlers, explicit
    ABENDs and RESP checks of one COBOL file (#3453)."""
    newlines = [i for i, ch in enumerate(code_stream) if ch == "\n"]

    def _shielded(offset: int) -> bool:
        index = bisect.bisect_left(newlines, offset)
        line_start = newlines[index - 1] + 1 if index else 0
        return _opens_inside_literal(code_stream, line_start, offset)

    return extract_uow_handlers(code_stream, values, _shielded)


def _mq_calls(code_stream: str, values: dict[str, str]) -> list[dict[str, Any]]:
    """Every IBM MQ call of one COBOL file (#3447), with the queue each reaches
    (via its object descriptor, or the MQOPEN its handle came from)."""
    if "MQ" not in code_stream.upper():
        return []
    newlines = [i for i, ch in enumerate(code_stream) if ch == "\n"]

    def _shielded(offset: int) -> bool:
        index = bisect.bisect_left(newlines, offset)
        line_start = newlines[index - 1] + 1 if index else 0
        return _opens_inside_literal(code_stream, line_start, offset)

    return extract_mq_calls(code_stream, values, _shielded)


def _cobol_job_cards(code_stream: str) -> list[dict[str, Any]]:
    """The JCL JOB / EXEC cards a COBOL file holds as literals (#3448), kept only
    when a JOB card is among them; a quote inside another literal is skipped."""
    if "//" not in code_stream:
        return []
    newlines = [i for i, ch in enumerate(code_stream) if ch == "\n"]

    def _shielded(offset: int) -> bool:
        index = bisect.bisect_left(newlines, offset)
        line_start = newlines[index - 1] + 1 if index else 0
        return _opens_inside_literal(code_stream, line_start, offset)

    return cobol_job_cards(code_stream, _shielded)


def extract_boundary(dialect: str, code_stream: str) -> dict[str, list[dict[str, Any]]]:
    """The named invocation, dataset, record-layout and transaction facts for one mainframe file.

    `dialect` is the language's `boundary_extraction` declaration, not its
    language id, so a future dialect can share COBOL's reading without being
    named cobol. Every return carries all four keys (`calls`, `datasets`,
    `records`, `transactions`) so the caller reads a uniform shape; a dialect that
    carries only some channels (JCL has no record layouts; CSD only transactions;
    PL/I only records, #3250) fills the rest with empty lists, and an unrecognised
    declaration degrades to "no facts" rather than raising in a worker.

    #3356: csd (and jcl, for an inline DFHCSDUP deck) additionally carry
    `csd_resources` -- every CSD DEFINE record, of any resource type.

    #3344: cobol and pli additionally carry `sql_tables` -- the DB2 `EXEC SQL
    DECLARE <table> TABLE (...)` columns (db2_declare_table). Callers read it
    with a default, so the dialects that cannot embed SQL simply omit it.
    #3446: cobol and pli also carry `sql_statements` -- every embedded SQL
    statement with the tables it reads / inserts / updates / deletes, its
    cursor and host variables (db2_sql_statements), read with a default.
    #3351-#3354: cobol and pli also carry `cics_resources` -- every EXEC CICS
    command naming a FILE, MAP, QUEUE, CONTAINER or passed CHANNEL
    (cics_resources), read with a default the same way.
    #3449: cobol and pli also carry `cics_tasks` -- every CICS task-control
    command (RUN/START/FETCH/FREE/RETRIEVE/CANCEL/DELAY/POST/WAIT/ENQ/DEQ,
    cics_tasks), read with a default.
    #3448: cobol (JCL JOB/EXEC card literals) and jcl (DDs routed to the
    internal reader, SYSOUT=(x,INTRDR)) carry `job_submits` (job_submits).
    #3447: cobol also carries `mq_calls` -- every IBM MQ call with its queue,
    direction, handle and options (mq_calls), read with a default.
    #3453: cobol also carries `uow_handlers` -- commit / rollback points,
    condition / abend / AID handlers, explicit ABENDs and RESP checks.
    #3455: cobol also carries `file_control` (each SELECT's organisation, access
    mode and keys) and jcl `vsam_defines` (IDCAMS DEFINE CLUSTER / AIX / PATH).
    #3451: jcl also carries `job_flow` -- job / step order, COND / IF conditions,
    PROC calls, and each DSN DD's disposition and GDG generation (job_flow).
    """
    if not code_stream:
        return {"calls": [], "datasets": [], "records": [], "transactions": []}
    if dialect == "cobol":
        values = _cobol_value_map(code_stream)
        records = _cobol_records(code_stream)
        return {
            "calls": _cobol_calls(code_stream, values),
            "datasets": _cobol_datasets(code_stream),
            "records": records,
            "transactions": [],
            "sql_tables": extract_sql_tables(code_stream, "cobol"),  # #3344
            "sql_statements": extract_sql_statements(code_stream, "cobol"),  # #3446
            "cics_resources": _cics_resources(code_stream, values, "cobol"),  # #3351-#3354
            "entry_points": entry_points(code_stream),  # #3454
            "cics_tasks": _cics_tasks(code_stream, values, records, "cobol"),  # #3449
            "job_submits": _cobol_job_cards(code_stream),  # #3448
            "mq_calls": _mq_calls(code_stream, values),  # #3447
            "uow_handlers": _uow_handlers(code_stream, values),  # #3453
            "file_control": cobol_file_control(code_stream),  # #3455
        }
    if dialect == "jcl":
        boundary = _jcl_boundary(code_stream)
        boundary["records"] = []
        boundary["transactions"] = _jcl_csd_transactions(code_stream)
        boundary["csd_resources"] = _jcl_csd_resources(code_stream)  # #3356
        boundary["job_submits"] = jcl_intrdr_dds(_jcl_statements(code_stream))  # #3448
        boundary["vsam_defines"] = jcl_vsam_defines(code_stream)  # #3455
        boundary["job_flow"] = jcl_job_flow(code_stream)  # #3451
        return boundary
    if dialect == "csd":
        return {
            "calls": [],
            "datasets": [],
            "records": [],
            "transactions": _csd_transactions(code_stream),
            # #3356: every DEFINE as a resource row (FILE, TDQUEUE, DB2..., ...).
            "csd_resources": _csd_resources(code_stream),
        }
    if dialect == "pli":
        pli_records = _pli_records(code_stream)
        return {
            "calls": [],
            "datasets": [],
            "records": pli_records,
            "transactions": [],
            "sql_tables": extract_sql_tables(code_stream, "pli"),  # #3344
            "sql_statements": extract_sql_statements(code_stream, "pli"),  # #3446
            "cics_resources": _cics_resources(code_stream, _pli_value_map(pli_records), "pli"),  # #3351-#3354
            "cics_tasks": _cics_tasks(code_stream, _pli_value_map(pli_records), [], "pli"),  # #3449
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
