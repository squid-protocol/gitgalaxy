# ==============================================================================
# GitGalaxy Core: Mainframe Boundary Extraction (#3200, #3201)
#
# PURPOSE:
# The counted rules tell you THAT a COBOL program calls something and THAT a JCL
# job allocates a dataset (`ipc_rpc_bridges` -> arch_ipc, `io` -> arch_io). They
# never say WHAT. This module is the named channel for the two mainframe
# relations that the hit counts flatten:
#
#   1. invocation  -- COBOL `CALL`, CICS `LINK`/`XCTL PROGRAM(...)`, JCL
#                     `EXEC PGM=`: who runs whom (#3200).
#   2. dataset     -- COBOL `SELECT ... ASSIGN TO <ddname>` with the `OPEN`
#                     modes actually used, and the JCL `DD` statement that binds
#                     that ddname to a real dataset (#3201).
#
# Together they are the mainframe call graph and the dataset lineage that
# `docs/refraction_engine_differential.md` recorded as stated absences: "program
# P reads DD X, job J binds DD X to dataset D" was unanswerable from the DB.
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
#   - FD/01 record layouts are NOT extracted. That is data-division item
#     extraction -- the differential doc's separate "no data items are
#     extracted" absence -- and needs a level-number/PIC/OCCURS/REDEFINES
#     walker. Lineage does not need it.
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

# The two dialects that carry a top-level `boundary_extraction` declaration.
# It is top level rather than inside `rules` because language_lens.py
# re.compile()s every string value in `rules` (#2806).
BOUNDARY_DIALECTS = ("cobol", "jcl")

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


def extract_boundary(dialect: str, code_stream: str) -> dict[str, list[dict[str, Any]]]:
    """The named invocation and dataset facts for one mainframe file.

    `dialect` is the language's `boundary_extraction` declaration, not its
    language id, so a future dialect can share COBOL's reading without being
    named cobol. Returns empty lists for anything else, so an unrecognised
    declaration degrades to "no facts" rather than raising in a worker.
    """
    if not code_stream:
        return {"calls": [], "datasets": []}
    if dialect == "cobol":
        values = _cobol_value_map(code_stream)
        return {"calls": _cobol_calls(code_stream, values), "datasets": _cobol_datasets(code_stream)}
    if dialect == "jcl":
        return _jcl_boundary(code_stream)
    return {"calls": [], "datasets": []}
