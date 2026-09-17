#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""
Embedded-verb coverage: does every CICS/SQL/DLI command and native-COBOL idiom
in the corpus fire a semantic rule, or is its absence recorded on purpose?

gitgalaxy#2990: an audit of four new CICS sample repos found that
`reflection_metaprogramming`'s bare `EXEC CICS`/`EXEC SQL` catch-all makes
every embedded-language statement LOOK covered, while seven verb families
(most visibly the CICS Async API -- `RUN TRANSID` / `FETCH CHILD|ANY`) carried
no semantic signal at all: a modern async CICS app scored `arch_concurrency =
0`. The issue's acceptance criterion is that every verb/idiom found in the
corpus is either (a) owned by a semantic rule, or (b) recorded as
deliberately blanket-only/unowned with a one-line reason -- so future gaps
are a diff against a table, not archaeology. This is that table, computed
from the real corpus every time it is run, never hand-maintained as a static
list.

METHOD
    1. Parse every `EXEC CICS|SQL|DLI ... END-EXEC` block (cobol) or every
       JCL statement/operand (jcl) out of the corpus's code stream (Prism
       strips comments first -- a `* ... FETCH any data` narrative comment
       is not a command).
    2. Normalize each block/statement to a canonical verb name (first token,
       plus a second token where the pair is a distinct CICS/SQL/DLI command
       -- `SEND` vs `SEND MAP`, `HANDLE CONDITION` vs `HANDLE ABEND`).
    3. Run every non-blanket rule in the language's registry over the block
       text; record which rules fire and at what share of that verb's blocks.
    4. Look the verb up in EXPECTED (this file's hand-maintained ownership
       table) and render a verdict:
         owned         expected rules all fire at >=90% share
         blanket-only  expected says the blanket is the semantic owner, and
                       indeed no non-blanket rule fires
         none          expected says deliberately unowned, and indeed
                       nothing fires
         MISMATCH      expected disagrees with what is actually observed
         GAP           the verb has real hits and no EXPECTED entry at all

`--check` exits 1 on any GAP or MISMATCH with >=1 hit -- that IS #2990's
acceptance criterion, runnable in CI. `--markdown` renders the tables
`docs/cobol_semantic_coverage.md` is built from.

USAGE
    python tests/tools/embedded_verb_coverage.py cobol
    python tests/tools/embedded_verb_coverage.py jcl --check
    python tests/tools/embedded_verb_coverage.py cobol --extra /tmp/async/repo1 /tmp/async/repo2
    python tests/tools/embedded_verb_coverage.py cobol --markdown docs/cobol_semantic_coverage_tables.md

Sibling of tests/tools/rule_probe.py; imports its corpus-file walker and
stream helpers rather than re-deriving them.
"""

from __future__ import annotations

import argparse
import collections
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import rule_probe  # noqa: E402 -- sibling import, no tests/__init__.py (CLAUDE.md testing conventions)

REPO_ROOT = TOOLS_DIR.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from gitgalaxy.core.prism import Prism  # noqa: E402
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS  # noqa: E402
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS  # noqa: E402

BLANKET = "blanket"
NONE_OWNED = "none"
OWNED = "owned"

OWNED_VERDICT = "owned"
BLANKET_VERDICT = "blanket-only"
NONE_VERDICT = "none"
GAP_VERDICT = "GAP"
MISMATCH_VERDICT = "MISMATCH"

# Rules that are a deliberate "this touches CICS/SQL/DLI" catch-all, not a
# semantic owner for any one verb -- excluded from attribution so a verb's
# observed-owner set only ever contains rules that mean something specific.
BLANKET_RULES = frozenset({"reflection_metaprogramming"})
# structural_boundaries fires on unrelated keywords inside a block's operand
# text (DISPLAY, PERFORM, ...); not a per-verb owner either.
NOISE_RULES = frozenset({"structural_boundaries"})


@dataclass(frozen=True)
class Owner:
    rules: frozenset[str] = field(default_factory=frozenset)
    kind: str = OWNED  # "owned" | "blanket" | "none"
    reason: str = ""
    # Some JCL statement keywords (STMT:DD, STMT:EXEC) are coarse buckets that
    # legitimately bundle several sub-forms -- a DD DUMMY or in-stream `DD *`
    # carries no DSN=/SYSOUT= at all, so io's real share over EVERY `DD`
    # statement is diluted well below the ~90% a single-purpose CICS/SQL verb
    # reaches. Lower on a specific row, with the reason saying why, rather
    # than loosening the threshold for every verb.
    min_share: float = 0.0  # 0.0 means "use SHARE_THRESHOLD"


def owned(*rules: str, reason: str, min_share: float = 0.0) -> Owner:
    return Owner(rules=frozenset(rules), kind=OWNED, reason=reason, min_share=min_share)


def blanket_only(reason: str) -> Owner:
    return Owner(kind=BLANKET, reason=reason)


def none_owned(reason: str) -> Owner:
    return Owner(kind=NONE_OWNED, reason=reason)


# ------------------------------------------------------------------------------
# COBOL: EXEC CICS/SQL/DLI block parsing
# ------------------------------------------------------------------------------

_EXEC_BLOCK = re.compile(r"EXEC\s+(CICS|SQL|DLI)\b(.*?)END-EXEC", re.I | re.S)
_MAX_BLOCK = 4000  # a block this long in real source is pathological; cap the verb scan, not the rule scan

# Two-word CICS/SQL/DLI commands where the qualifier changes the command's
# meaning (a distinct API entry, not an operand of the bare verb).
_TWO_WORD = {
    ("SEND", "MAP"),
    ("SEND", "TEXT"),
    ("SEND", "CONTROL"),
    ("SEND", "PAGE"),
    ("RECEIVE", "MAP"),
    ("HANDLE", "CONDITION"),
    ("HANDLE", "ABEND"),
    ("HANDLE", "AID"),
    ("PUSH", "HANDLE"),
    ("POP", "HANDLE"),
    ("IGNORE", "CONDITION"),
    ("PUT", "CONTAINER"),
    ("GET", "CONTAINER"),
    ("MOVE", "CONTAINER"),
    ("DELETE", "CONTAINER"),
    ("DELETE", "COUNTER"),
    ("DEFINE", "COUNTER"),
    ("QUERY", "COUNTER"),
    ("GET", "COUNTER"),
    ("REWIND", "COUNTER"),
    ("UPDATE", "COUNTER"),
    ("WRITEQ", "TS"),
    ("WRITEQ", "TD"),
    ("READQ", "TS"),
    ("READQ", "TD"),
    ("DELETEQ", "TS"),
    ("DELETEQ", "TD"),
    ("WEB", "SEND"),
    ("WEB", "RECEIVE"),
    ("WEB", "OPEN"),
    ("WEB", "CLOSE"),
    ("WEB", "READ"),
    ("WEB", "WRITE"),
    ("WEB", "EXTRACT"),
    ("WEB", "CONVERSE"),
    ("WEB", "STARTBROWSE"),
    ("WEB", "READNEXT"),
    ("WEB", "ENDBROWSE"),
    ("DOCUMENT", "CREATE"),
    ("DOCUMENT", "INSERT"),
    ("DOCUMENT", "SET"),
    ("DOCUMENT", "RETRIEVE"),
    ("RUN", "TRANSID"),
    ("RUN", "ACTIVITY"),
    ("RUN", "ACQPROCESS"),
    ("FETCH", "CHILD"),
    ("FETCH", "ANY"),
    ("FREE", "CHILD"),
    ("START", "TRANSID"),
    ("START", "BREXIT"),
    ("START", "CHANNEL"),
    ("SYNCPOINT", "ROLLBACK"),
    ("WAIT", "EVENT"),
    ("WAIT", "EXTERNAL"),
    ("WAIT", "JOURNALNAME"),
    ("WAIT", "SIGNAL"),
    ("SIGNAL", "EVENT"),
    ("BIF", "DEEDIT"),
    ("BIF", "DIGEST"),
    ("TRANSFORM", "DATATOXML"),
    ("TRANSFORM", "XMLTODATA"),
    ("TRANSFORM", "DATATOJSON"),
    ("TRANSFORM", "JSONTODATA"),
    ("VERIFY", "PASSWORD"),
    ("VERIFY", "PHRASE"),
    ("INQUIRE", "TERMINAL"),
    ("SET", "TERMINAL"),
    ("SET", "TASK"),
    ("SET", "FILE"),
    ("ADDRESS", "SET"),
    ("WRITE", "JOURNALNAME"),
    ("WRITE", "OPERATOR"),
    ("DUMP", "TRANSACTION"),
    ("ENTER", "TRACENUM"),
    ("ISSUE", "ERASEAUP"),
    ("INVOKE", "WEBSERVICE"),
    ("INVOKE", "SERVICE"),
    ("INVOKE", "APPLICATION"),
    ("EXTRACT", "WEB"),
    ("EXTRACT", "TCPIP"),
    ("EXTRACT", "CERTIFICATE"),
    ("CHANGE", "TASK"),
    ("CHANGE", "PASSWORD"),
    ("QUERY", "SECURITY"),
    ("DELETE", "FILE"),
    ("READ", "FILE"),
    ("WRITE", "FILE"),
    ("REWRITE", "FILE"),
    ("STARTBR", "FILE"),
    ("READNEXT", "FILE"),
    ("READPREV", "FILE"),
    ("ENDBR", "FILE"),
    ("LINK", "PROGRAM"),
    ("LINK", "ACQPROCESS"),
    ("RETURN", "TRANSID"),
    ("ABEND", "ABCODE"),
    ("ASSIGN", "APPLID"),
    ("ASSIGN", "PROGRAM"),
    ("ASSIGN", "SYSID"),
    ("ASSIGN", "INVOKINGPROG"),
    ("ASSIGN", "ABCODE"),
    ("ASSIGN", "STARTCODE"),
    ("EXECUTE", "IMMEDIATE"),
    ("DECLARE", "CURSOR"),
    ("SELECT", "INTO"),
    ("LOCK", "TABLE"),
    ("CANCEL", "REQID"),
    ("GU", "USING"),
    ("GN", "USING"),
    ("GNP", "USING"),
    ("GHU", "USING"),
    ("GHN", "USING"),
    ("GHNP", "USING"),
    ("ISRT", "USING"),
    ("REPL", "USING"),
    ("DLET", "USING"),
    ("WHENEVER", "SQLERROR"),
    ("WHENEVER", "SQLWARNING"),
}
# Verbs whose real identity is the FIRST token alone; a trailing qualifier
# that appears in _TWO_WORD elsewhere is just that verb's normal operand
# shape (`DELETE FILE(X)` is plain DELETE, not a distinct "DELETE FILE"
# command -- only the counter/container/named forms above are distinct).
_COLLAPSE_TO_FIRST = {
    ("DELETE", "FILE"),
    ("READ", "FILE"),
    ("WRITE", "FILE"),
    ("REWRITE", "FILE"),
    ("STARTBR", "FILE"),
    ("READNEXT", "FILE"),
    ("READPREV", "FILE"),
    ("ENDBR", "FILE"),
    ("LINK", "PROGRAM"),
    ("LINK", "ACQPROCESS"),
    ("RETURN", "TRANSID"),
    ("ABEND", "ABCODE"),
    ("ASSIGN", "APPLID"),
    ("ASSIGN", "PROGRAM"),
    ("ASSIGN", "SYSID"),
    ("ASSIGN", "INVOKINGPROG"),
    ("ASSIGN", "ABCODE"),
    ("ASSIGN", "STARTCODE"),
    ("SELECT", "INTO"),
    ("CANCEL", "REQID"),
    ("GU", "USING"),
    ("GN", "USING"),
    ("GNP", "USING"),
    ("GHU", "USING"),
    ("GHN", "USING"),
    ("GHNP", "USING"),
    ("ISRT", "USING"),
    ("REPL", "USING"),
    ("DLET", "USING"),
}


# Runtime-service literals a `CALL '<name>'` invokes are their own rows below
# (each is a specific engine addition, e.g. CEE3ABD -> panics_and_aborts); every
# other literal is an ORDINARY application program call -- already covered by
# ipc_rpc_bridges (the generic `CALL\s+` alternative) and args (if it has a
# USING list). Bucketing them avoids one census row per arbitrary program name.
_KNOWN_CALL_SERVICES = {"CEE3ABD", "DSNTIAR", "CBLTDLI", "AIBTDLI", "MQPUT", "MQGET"}


def _call_bucket(name: str) -> str:
    if name in _KNOWN_CALL_SERVICES or name.startswith("CEE"):
        return name
    return "<ordinary program>"


def _cobol_verb(kind: str, body: str) -> str:
    toks = re.findall(r"[A-Z0-9-]+", body.upper())
    if not toks:
        return "?"
    first = toks[0]
    m = re.match(r"\s*[A-Z0-9-]+\s+([A-Z]+)(?=[\s(]|$)", body.upper())
    second = m.group(1) if m else ""
    pair = (first, second)
    if pair in _TWO_WORD and pair not in _COLLAPSE_TO_FIRST:
        return f"{kind}:{first} {second}"
    return f"{kind}:{first}"


def _native_verbs(code_stream: str) -> collections.Counter:
    """Native (non-EXEC) COBOL constructs the CICS/SQL/DLI table doesn't cover."""
    c = collections.Counter()
    # FUNCTION's name must sit on the SAME line as the keyword -- a COBOL
    # data-item literally named FUNCTION (real corpus shape, BANKDATA.cbl)
    # followed by an unrelated word on the next physical line is not a call.
    for m in re.finditer(r"\bFUNCTION[ \t]+([A-Z0-9-]+)", code_stream, re.I):
        c[f"NATIVE:FUNCTION {m.group(1).upper()}"] += 1
    for m in re.finditer(r"CALL\s+'([A-Z0-9@#$-]+)'", code_stream, re.I):
        c[f"NATIVE:CALL '{_call_bucket(m.group(1).upper())}'"] += 1
    for kw in (
        "SORT",
        "MERGE",
        "INVOKE",
        "SEARCH",
        "EXHIBIT",
        "READY TRACE",
        "RESET TRACE",
        "SIGNON",
        "SIGNOFF",
    ):
        pat = r"\b" + re.escape(kw).replace(r"\ ", r"\s+") + r"\b"
        n = len(re.findall(pat, code_stream, re.I))
        if n:
            c[f"NATIVE:{kw}"] += n
    for m in re.finditer(
        r"\bACCEPT\s+[A-Za-z0-9_-]+\s+FROM\s+(ENVIRONMENT|ARGUMENT-NUMBER|COMMAND-LINE|SYSIN|CONSOLE)\b",
        code_stream,
        re.I,
    ):
        c["NATIVE:ACCEPT FROM (env/arg)"] += 1
    # These are body-level idioms, never their own EXEC block -- a RESP()/SQLCODE
    # check sits in a separate statement after the command it inspects. Tracked as
    # their own verbs so the safety/safety_bypasses additions they justify are
    # visible in the coverage table, not silently invisible to the census.
    c["NATIVE:DFHRESP("] += len(re.findall(r"\bDFHRESP\(", code_stream, re.I))
    c["NATIVE:IF/EVALUATE SQLCODE"] += len(re.findall(r"\b(?:IF|EVALUATE)\s+SQLCODE\b", code_stream, re.I))
    c["NATIVE:NOHANDLE"] += len(re.findall(r"(?<![-\w])NOHANDLE(?![-\w])", code_stream, re.I))
    c["NATIVE:WHENEVER"] += len(re.findall(r"\bEXEC\s+SQL\s+WHENEVER\b", code_stream, re.I))
    c["NATIVE:GRANT/REVOKE"] += len(re.findall(r"\bEXEC\s+SQL\s+(?:GRANT|REVOKE)\b", code_stream, re.I))
    c["NATIVE:FILE STATUS clause"] += len(re.findall(r"\bFILE\s+STATUS\s+IS\b", code_stream, re.I))
    return collections.Counter(
        {k: v for k, v in c.items() if v}
    )  # drop zero-count keys (Counter += 0 still materializes them)


def parse_cobol(code_stream: str) -> collections.Counter[str]:
    counts = collections.Counter()
    for m in _EXEC_BLOCK.finditer(code_stream):
        kind, body = m.group(1).upper(), m.group(2)[:_MAX_BLOCK]
        counts[_cobol_verb(kind, body)] += 1
    counts.update(_native_verbs(code_stream))
    return counts


def block_texts_cobol(code_stream: str) -> dict[str, list[str]]:
    """verb -> list of the full `EXEC ... END-EXEC` block texts (for rule attribution)."""
    out: dict[str, list[str]] = collections.defaultdict(list)
    for m in _EXEC_BLOCK.finditer(code_stream):
        kind, body = m.group(1).upper(), m.group(2)[:_MAX_BLOCK]
        verb = _cobol_verb(kind, body)
        out[verb].append(f"EXEC {kind} {body} END-EXEC")
    for verb, texts in list(_native_block_texts(code_stream).items()):
        out[verb].extend(texts)
    return out


def _native_block_texts(code_stream: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = collections.defaultdict(list)
    # The paren-content class stops before a NESTED FUNCTION call rather than
    # swallowing it (`FUNCTION MOD(35, FUNCTION INTEGER(A * B))`, real corpus
    # shape, IF1244.2.cbl) -- otherwise the outer match's span consumes the
    # inner call's text entirely and finditer can never see it as its own
    # sample, undercounting the inner verb's attributed owners relative to
    # the raw count (which does not consume parens and sees both).
    for m in re.finditer(r"\bFUNCTION[ \t]+[A-Z0-9-]+[ \t]*(?:\((?:(?!FUNCTION)[^)\n])*\))?", code_stream, re.I):
        name = re.match(r"\bFUNCTION[ \t]+([A-Z0-9-]+)", m.group(0), re.I).group(1).upper()
        out[f"NATIVE:FUNCTION {name}"].append(m.group(0))
    for m in re.finditer(r"CALL\s+'[A-Z0-9@#$-]+'(?:[^.\n]*)", code_stream, re.I):
        name = re.match(r"CALL\s+'([A-Z0-9@#$-]+)'", m.group(0), re.I).group(1).upper()
        out[f"NATIVE:CALL '{_call_bucket(name)}'"].append(m.group(0)[:200])
    for kw in ("SORT", "MERGE", "INVOKE", "SEARCH", "EXHIBIT", "READY TRACE", "RESET TRACE", "SIGNON", "SIGNOFF"):
        pat = r"\b" + re.escape(kw).replace(r"\ ", r"\s+") + r"\b[^.\n]*"
        for m in re.finditer(pat, code_stream, re.I):
            out[f"NATIVE:{kw}"].append(m.group(0)[:200])
    for m in re.finditer(
        r"\bACCEPT\s+[A-Za-z0-9_-]+\s+FROM\s+(?:ENVIRONMENT|ARGUMENT-NUMBER|COMMAND-LINE|SYSIN|CONSOLE)\b",
        code_stream,
        re.I,
    ):
        out["NATIVE:ACCEPT FROM (env/arg)"].append(m.group(0))
    for m in re.finditer(r"[^\n]*\bDFHRESP\([^\n]*", code_stream, re.I):
        out["NATIVE:DFHRESP("].append(m.group(0)[:200])
    for m in re.finditer(r"[^\n]*\b(?:IF|EVALUATE)\s+SQLCODE\b[^\n]*", code_stream, re.I):
        out["NATIVE:IF/EVALUATE SQLCODE"].append(m.group(0)[:200])
    for m in re.finditer(r"[^\n]*(?<![-\w])NOHANDLE(?![-\w])[^\n]*", code_stream, re.I):
        out["NATIVE:NOHANDLE"].append(m.group(0)[:200])
    for m in re.finditer(r"EXEC\s+SQL\s+WHENEVER\b.*?END-EXEC", code_stream, re.I | re.S):
        out["NATIVE:WHENEVER"].append(m.group(0)[:200])
    for m in re.finditer(r"EXEC\s+SQL\s+(?:GRANT|REVOKE)\b.*?END-EXEC", code_stream, re.I | re.S):
        out["NATIVE:GRANT/REVOKE"].append(m.group(0)[:200])
    for m in re.finditer(r"[^\n]*\bFILE\s+STATUS\s+IS\b[^\n]*", code_stream, re.I):
        out["NATIVE:FILE STATUS clause"].append(m.group(0)[:200])
    return out


# ------------------------------------------------------------------------------
# JCL: statement / operand parsing
# ------------------------------------------------------------------------------

_JCL_STMT = re.compile(r"^[ \t]*//[A-Za-z0-9_#$@]*[ \t]+([A-Za-z]+)\b", re.M)
# #2990: an operand only exists on a real JCL control statement -- a line
# beginning `//`. Without that anchor, the census swept up arbitrary
# in-stream payload data (a whole CICS SIT parameter deck, DFH$SIP1.jcl, has
# no `//` anywhere and is not JCL at all; its AICONS=/GRPLIST=/KEYRING=
# lines are the target application's config, not a JCL operand) -- that
# payload surface is real and unowned, but it is #2990's filed follow-up
# (jcl in-stream payload grammar), not this table's job to enumerate one
# row per arbitrary embedded key. The per-line scan below (not a single
# compiled multi-line regex) is what enforces that anchor.

# #3002: that filed follow-up, picked up. The Db2 DSN command processor /
# IDCAMS control-statement verbs actually carried inside a `//ddname DD *` or
# `DD DATA` payload -- real, but deliberately not one row per arbitrary
# embedded key the way OPERAND:/STMT: are; a small fixed vocabulary instead
# (DSN SYSTEM, RUN PROGRAM, GRANT, DROP, DELETE, BIND, DEFINE CLUSTER, REPRO,
# FREE -- the set the issue's own corpus grep found). PAYLOAD: prefix keeps
# these visibly separate from real `//`-anchored JCL statement vocabulary.
# #3010 closed the one gap that review left: BIND is owned by
# high_risk_execution (see the EXPECTED row); the other eight stay none_owned.
# The ddname class includes `.` for the qualified proc-step override form
# (`//BIND.SYSTSIN DD *,SYMBOLS=...`, the cobol-programming-course CBLDB2xC
# shape) -- #3010, kept identical to detector.py's _JCL_DD_INSTREAM_OPEN so
# the engine and this referee always read the same spans.
_DD_INSTREAM_OPEN = re.compile(r"^[ \t]*//[A-Za-z0-9_#$@.]*[ \t]+DD[ \t]+(?:\*|DATA\b)", re.I)
_INSTREAM_VERB_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("PAYLOAD:DSN SYSTEM", re.compile(r"\bDSN\s+SYSTEM\b", re.I)),
    ("PAYLOAD:RUN PROGRAM", re.compile(r"\bRUN\s+PROGRAM\b", re.I)),
    ("PAYLOAD:DEFINE CLUSTER", re.compile(r"\bDEFINE\s+CLUSTER\b", re.I)),
    ("PAYLOAD:GRANT", re.compile(r"\bGRANT\b", re.I)),
    ("PAYLOAD:DROP", re.compile(r"\bDROP\b", re.I)),
    ("PAYLOAD:DELETE", re.compile(r"\bDELETE\b", re.I)),
    ("PAYLOAD:BIND", re.compile(r"\bBIND\b", re.I)),
    ("PAYLOAD:REPRO", re.compile(r"\bREPRO\b", re.I)),
    ("PAYLOAD:FREE", re.compile(r"\bFREE\b", re.I)),
]
# A span this long is pathological; cap the scan, not the file (mirrors
# cobol's _MAX_BLOCK for EXEC ... END-EXEC).
_MAX_PAYLOAD_SPAN_LINES = 500


def _jcl_instream_verb_hits(code_stream: str) -> dict[str, list[str]]:
    """verb -> matched lines, over every `DD *`/`DD DATA` payload span.
    Opens on the DD statement itself, closes on a bare `/*` line or the next
    real `//` control statement, whichever comes first -- payload data has no
    other terminator (same anchor discipline _JCL_STMT's own comment names)."""
    out: dict[str, list[str]] = collections.defaultdict(list)
    lines = code_stream.splitlines()
    i, total = 0, len(lines)
    while i < total:
        if not _DD_INSTREAM_OPEN.match(lines[i]):
            i += 1
            continue
        i += 1
        span_lines = 0
        while i < total and span_lines < _MAX_PAYLOAD_SPAN_LINES:
            line = lines[i]
            if line.strip() == "/*" or re.match(r"^[ \t]*//(?!\*)", line):
                break
            for label, pat in _INSTREAM_VERB_PATTERNS:
                if pat.search(line):
                    out[label].append(line.strip()[:200])
            i += 1
            span_lines += 1
    return out


def parse_jcl(code_stream: str) -> collections.Counter[str]:
    counts = collections.Counter()
    for m in _JCL_STMT.finditer(code_stream):
        kw = m.group(1).upper()
        if kw in {
            "JOB",
            "EXEC",
            "DD",
            "PROC",
            "PEND",
            "SET",
            "IF",
            "ELSE",
            "ENDIF",
            "INCLUDE",
            "JCLLIB",
            "OUTPUT",
            "EXPORT",
            "COMMAND",
            "CNTL",
            "ENDCNTL",
            "XMIT",
            "NOTIFY",
        }:
            counts[f"STMT:{kw}"] += 1
    for line in code_stream.splitlines():
        if not re.match(r"^[ \t]*//(?!\*)", line):
            continue
        for m in re.finditer(r"\b([A-Z]{2,10})=", line, re.I):
            counts[f"OPERAND:{m.group(1).upper()}="] += 1
        if re.search(r"\bPGM=[A-Za-z0-9#$@]+", line, re.I):
            counts["PGM:*"] += 1
    for verb, samples in _jcl_instream_verb_hits(code_stream).items():
        counts[verb] += len(samples)
    return counts


def block_texts_jcl(code_stream: str) -> dict[str, list[str]]:
    """Same // -line-anchored scope as parse_jcl (see its docstring note),
    so counts and attribution samples agree exactly."""
    out: dict[str, list[str]] = collections.defaultdict(list)
    for m in _JCL_STMT.finditer(code_stream):
        kw = m.group(1).upper()
        line = code_stream[m.start() : code_stream.find("\n", m.start())]
        out[f"STMT:{kw}"].append(line[:200])
    for line in code_stream.splitlines():
        if not re.match(r"^[ \t]*//(?!\*)", line):
            continue
        for m in re.finditer(r"\b([A-Z]{2,10})=", line, re.I):
            out[f"OPERAND:{m.group(1).upper()}="].append(line[:200])
        if re.search(r"\bPGM=[A-Za-z0-9#$@]+", line, re.I):
            out["PGM:*"].append(line[:200])
    for verb, samples in _jcl_instream_verb_hits(code_stream).items():
        out[verb].extend(samples)
    return out


PARSERS = {"cobol": parse_cobol, "jcl": parse_jcl}
BLOCK_TEXTS = {"cobol": block_texts_cobol, "jcl": block_texts_jcl}

# ------------------------------------------------------------------------------
# Attribution: which non-blanket rules fire on a verb's blocks
# ------------------------------------------------------------------------------


def attribute(lang: str, texts: dict[str, list[str]]) -> dict[str, collections.Counter]:
    """verb -> Counter(rule -> hit count) over that verb's block/statement texts."""
    rules = LANGUAGE_DEFINITIONS[lang]["rules"]
    active = {
        k: v
        for k, v in rules.items()
        if v is not None and not k.startswith("_") and k not in BLANKET_RULES | NOISE_RULES
    }
    out: dict[str, collections.Counter] = {}
    for verb, samples in texts.items():
        c = collections.Counter()
        for text in samples:
            for rule_name, pattern in active.items():
                if pattern.search(text):
                    c[rule_name] += 1
        out[verb] = c
    return out


def blanket_fires(lang: str, texts: dict[str, list[str]]) -> dict[str, int]:
    rules = LANGUAGE_DEFINITIONS[lang]["rules"]
    blanket = {k: v for k, v in rules.items() if k in BLANKET_RULES and v is not None}
    out: dict[str, int] = {}
    for verb, samples in texts.items():
        out[verb] = sum(1 for text in samples if any(p.search(text) for p in blanket.values()))
    return out


# ------------------------------------------------------------------------------
# Verdicts
# ------------------------------------------------------------------------------

SHARE_THRESHOLD = 0.90


def verdict_for(verb: str, n: int, observed: collections.Counter, owner: Owner | None) -> str:
    if owner is None:
        return GAP_VERDICT if n >= 1 else GAP_VERDICT  # unrecorded is always a finding once it appears
    threshold = owner.min_share if (owner.kind == OWNED and owner.min_share) else SHARE_THRESHOLD
    non_zero_observed = {r for r, c in observed.items() if n and c / n >= threshold}
    if owner.kind == BLANKET:
        return BLANKET_VERDICT if not non_zero_observed else MISMATCH_VERDICT
    if owner.kind == NONE_OWNED:
        return NONE_VERDICT if not non_zero_observed else MISMATCH_VERDICT
    # kind == OWNED. "extra" is still checked at SHARE_THRESHOLD, never the
    # lowered floor -- a lowered floor explains why a real owner sometimes
    # doesn't fire, it does not license an unrelated rule sneaking in.
    strict_observed = {r for r, c in observed.items() if n and c / n >= SHARE_THRESHOLD}
    missing = owner.rules - non_zero_observed
    extra = strict_observed - owner.rules
    return OWNED_VERDICT if not missing and not extra else MISMATCH_VERDICT


@dataclass
class Row:
    verb: str
    n: int
    files: int
    owner: Owner | None
    observed: collections.Counter
    verdict: str


# #2990: JCL's EXEC statement can carry arbitrary SYM=value keyword overrides
# for a cataloged PROC (installation- or application-defined symbolic
# parameters -- APPLID=, GRPLIST=, KEYRING=, dozens more, each 1-2 files).
# These are real `//` statement operands, not noise, but they are not JCL
# LANGUAGE vocabulary either -- enumerating one EXPECTED row per site-specific
# symbol name would be documentation theater, not a coverage table. Any
# OPERAND spread across fewer than this many distinct files is bucketed into
# one row instead of appearing as its own; the widely-used JCL/dataset/EXEC
# keywords (DISP=, DSN=, PGM=, COND=, ...) all clear this bar easily.
_INSTALLATION_OPERAND_FILE_FLOOR = 3


def _bucket_installation_specific_operands(totals, files_seen, all_texts) -> None:
    bucket = "OPERAND:<installation- or application-specific>"
    for verb in [
        v for v in list(totals) if v.startswith("OPERAND:") and len(files_seen[v]) < _INSTALLATION_OPERAND_FILE_FLOOR
    ]:
        n = totals.pop(verb)
        totals[bucket] += n
        files_seen.setdefault(bucket, set())
        files_seen[bucket] |= files_seen.pop(verb)
        if verb in all_texts:
            all_texts.setdefault(bucket, [])
            all_texts[bucket].extend(all_texts.pop(verb))


def build_rows(lang: str, corpus: str, extra: list[Path]) -> list[Row]:
    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    parser = PARSERS[lang]
    blocker = BLOCK_TEXTS[lang]
    totals: collections.Counter = collections.Counter()
    files_seen: dict[str, set] = collections.defaultdict(set)
    all_texts: dict[str, list[str]] = collections.defaultdict(list)

    def scan_root(root: Path, corpus_name: str):
        exts = rule_probe._extensions(lang)
        if not root.is_dir():
            return
        for p in sorted(root.rglob("*")):
            if not p.is_file() or ".git" in p.parts or p.stat().st_size > rule_probe.MAX_FILE_BYTES:
                continue
            if exts and p.suffix.lower() not in exts and p.name.lower() not in exts:
                continue
            try:
                src = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            code = prism.split_streams(src, lang)["code_stream"]
            counts = parser(code)
            if not counts:
                continue
            for verb in counts:
                files_seen[verb].add(str(p))
            totals.update(counts)
            for verb, texts in blocker(code).items():
                all_texts[verb].extend(texts)

    d = rule_probe.CORPUS_DIR.get(lang, lang)
    if corpus in ("crucible", "both"):
        scan_root(rule_probe.CRUCIBLE / d, "crucible")
    if corpus in ("rosetta", "both"):
        scan_root(rule_probe.ROSETTA / d, "rosetta")
    for xroot in extra:
        scan_root(xroot, "extra")

    if lang == "jcl":
        _bucket_installation_specific_operands(totals, files_seen, all_texts)

    observed_by_verb = attribute(lang, all_texts)
    inventory = EXPECTED.get(lang, {})
    rows = []
    for verb, n in sorted(totals.items(), key=lambda kv: (-kv[1], kv[0])):
        owner = inventory.get(verb)
        observed = observed_by_verb.get(verb, collections.Counter())
        v = verdict_for(verb, n, observed, owner)
        rows.append(Row(verb=verb, n=n, files=len(files_seen[verb]), owner=owner, observed=observed, verdict=v))
    return rows


def print_report(lang: str, rows: list[Row], show_all: bool) -> int:
    bad = [r for r in rows if r.verdict in (GAP_VERDICT, MISMATCH_VERDICT)]
    print(f"{lang}: {len(rows)} verbs observed, {len(bad)} GAP/MISMATCH")
    for r in rows:
        if not show_all and r.verdict not in (GAP_VERDICT, MISMATCH_VERDICT):
            continue
        obs = ", ".join(f"{k}:{c}/{r.n}" for k, c in r.observed.most_common()) or "--"
        exp = r.owner.reason if r.owner else "(no EXPECTED entry)"
        print(f"  [{r.verdict:9s}] {r.verb:34s} n={r.n:<5d} files={r.files:<3d} observed=({obs})  expected={exp}")
    return 1 if bad else 0


def render_markdown(lang: str, rows: list[Row]) -> str:
    lines = [f"### {lang}\n", "| verb | n | files | verdict | owner rule(s) | reason |", "|---|---|---|---|---|---|"]
    for r in rows:
        owner_str = (
            ", ".join(sorted(r.owner.rules))
            if r.owner and r.owner.rules
            else ("blanket" if r.owner and r.owner.kind == BLANKET else "—")
        )
        reason = r.owner.reason if r.owner else "**NOT RECORDED**"
        lines.append(f"| `{r.verb}` | {r.n} | {r.files} | {r.verdict} | {owner_str} | {reason} |")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------------
# EXPECTED: the ownership table. Filled from the real corpus census (see
# docs/cobol_semantic_coverage.md for the full table and rationale); this is
# the CI-checked source of truth.
# ------------------------------------------------------------------------------

EXPECTED_COBOL: dict[str, Owner] = {
    # --- CICS: async task control / concurrency ---
    "CICS:RUN TRANSID": owned(
        "concurrency",
        "ipc_rpc_bridges",
        reason="#2990: spawns a child task -- the async spawn half of the Async API; also hands work to another transaction (ipc).",
    ),
    "CICS:FETCH CHILD": owned(
        "concurrency", reason="#2990: joins a child task spawned by RUN TRANSID -- the async join half."
    ),
    "CICS:FETCH ANY": owned(
        "concurrency", reason="#2990: joins whichever child completes first -- same async join family as FETCH CHILD."
    ),
    "CICS:START TRANSID": owned(
        "concurrency",
        "ipc_rpc_bridges",
        reason="#2990: schedules another transaction to start (interval control's task-spawn form).",
    ),
    "CICS:DELAY": owned(
        "concurrency",
        "thread_sleeps",
        reason="pre-#2990 dual, unchanged: a forced wait (async primitive) that also blocks the task (thread_sleeps).",
    ),
    "CICS:ENQ": owned(
        "concurrency", "sync_locks", reason="pre-#2990 dual, unchanged: task coordination + the CICS lock primitive."
    ),
    "CICS:DEQ": owned("concurrency", reason="pre-#2990, unchanged: releases the ENQ lock -- task coordination."),
    # --- CICS: browse / file control (io) ---
    "CICS:READ": owned("io", reason="pre-#2990, unchanged: VSAM/file read."),
    "CICS:WRITE": owned("io", reason="pre-#2990, unchanged: VSAM/file write."),
    "CICS:REWRITE": owned("io", reason="pre-#2990, unchanged: VSAM/file update."),
    "CICS:DELETE": owned(
        "io",
        "cleanup",
        reason="pre-#2990, unchanged: removes a record from an external store -- io boundary and a release of that state.",
    ),
    "CICS:STARTBR": owned(
        "io", reason="#2990: opens a VSAM browse cursor -- a boundary operation, same family as the bare file verbs."
    ),
    "CICS:READNEXT": owned("io", reason="#2990: advances a browse cursor forward."),
    "CICS:READPREV": owned("io", reason="#2990: advances a browse cursor backward."),
    "CICS:ENDBR": owned(
        "io", "cleanup", reason="#2990: releases a browse cursor -- the `EXEC SQL CLOSE` (cursor) shape, io + cleanup."
    ),
    # --- CICS: named counters (io / cleanup) ---
    "CICS:DEFINE COUNTER": owned(
        "io", reason="#2990: creates a named counter in the coupling facility -- an external, shared store."
    ),
    "CICS:QUERY COUNTER": owned("io", reason="#2990: reads a named counter's value from the coupling facility."),
    "CICS:GET COUNTER": owned(
        "io", reason="#2990: reads and increments a named counter -- same external-store boundary."
    ),
    "CICS:DELETE COUNTER": owned(
        "io", "cleanup", reason="#2990: removes a named counter -- boundary + release of external state."
    ),
    # --- CICS: unit-of-work / exception handling (safety) ---
    "CICS:SYNCPOINT": owned(
        "safety",
        reason="#2990: commits the current unit of work -- the transactional guard sqlite.py already counts as safety.",
    ),
    "CICS:SYNCPOINT ROLLBACK": owned(
        "safety", reason="#2990: backs out the current unit of work -- same transactional-guard family."
    ),
    "CICS:HANDLE ABEND": owned(
        "safety",
        reason="#2990: installs an abend handler -- the stated #2869 sentence's 'installed failure handler'; moved from no owner.",
    ),
    "CICS:HANDLE CONDITION": owned(
        "safety",
        reason="#2990: installs a condition handler -- moved OUT of `events` (the declared row excludes the receiving side) and into `safety` per the stated #2869 contract.",
    ),
    # --- CICS: terminal / UI ---
    "CICS:SEND MAP": owned("ui_framework", reason="pre-#2990, unchanged: formatted 3270 screen output."),
    "CICS:SEND TEXT": owned("ui_framework", reason="#2990: bare terminal text output -- widened from SEND MAP only."),
    "CICS:SEND CONTROL": owned(
        "ui_framework", reason="#2990: terminal control (cursor/erase) output -- same widening."
    ),
    "CICS:SEND": owned(
        "ui_framework",
        "safety_bypasses",
        reason="#2990: bare SEND FROM(...) writes directly to the terminal with no map. The crucible's only 4 occurrences all carry NOHANDLE (real, deliberate error-suppression dual on this idiom -- not asserted as a general SEND property).",
    ),
    "CICS:RECEIVE MAP": owned(
        "listeners", reason="pre-#2990, unchanged: registration to receive formatted terminal input."
    ),
    "CICS:RECEIVE": owned(
        "listeners", reason="pre-#2990, unchanged: registration to receive unformatted terminal input."
    ),
    "CICS:HANDLE AID": owned(
        "listeners",
        reason="#2990: registers a handler for a terminal attention key -- a registration to receive, listeners' contract.",
    ),
    # --- CICS: time ---
    "CICS:ASKTIME": owned(
        "time_date_logic", reason="#2990: reads the current time -- a clock call, no owner before this."
    ),
    "CICS:FORMATTIME": owned("time_date_logic", reason="#2990: formats a time value -- same clock/calendar family."),
    # --- CICS: conversions ---
    "CICS:BIF DEEDIT": owned(
        "explicit_casts", reason="#2990: de-edits a numeric field back to a number -- a conversion call."
    ),
    # --- CICS: program/task linkage (ipc_rpc_bridges) ---
    "CICS:LINK": owned(
        "ipc_rpc_bridges", reason="pre-#2990, unchanged: synchronous program-to-program call across a boundary."
    ),
    "CICS:XCTL": owned("ipc_rpc_bridges", reason="pre-#2990, unchanged: transfers control to another program."),
    "CICS:RETURN": owned(
        "ipc_rpc_bridges", reason="pre-#2990, unchanged: returns control, optionally to another transaction."
    ),
    "CICS:PUT CONTAINER": owned(
        "state_mutation",
        "ipc_rpc_bridges",
        reason="pre-#2990 dual, unchanged: writes state that outlives the program AND hands it to another one.",
    ),
    "CICS:GET CONTAINER": owned(
        "ipc_rpc_bridges",
        reason="pre-#2990, unchanged: reads a container -- the bridge without the mutation (GET CONTAINER's asymmetry with PUT is deliberate).",
    ),
    "CICS:SIGNAL EVENT": owned(
        "events", reason="pre-#2990, unchanged: publishes into the CICS event-processing channel."
    ),
    # --- CICS: SPI / ambient introspection -- blanket is the semantic owner ---
    "CICS:ASSIGN": blanket_only(
        "introspection of the task/terminal/system environment (APPLID, SYSID, ABCODE, ...); no cross-language rule owns 'read an ambient runtime attribute', and reflection_metaprogramming's bare EXEC CICS catch-all is the only signal it needs -- a dedicated rule would duplicate the blanket for a low-value, CICS-only construct."
    ),
    "CICS:INQUIRE": blanket_only(
        "same SPI-introspection reasoning as ASSIGN (0 real occurrences with a specific object; the crucible's one hit is a bare form)."
    ),
    "CICS:INQUIRE TERMINAL": blanket_only(
        "same SPI-introspection reasoning as ASSIGN -- reads a terminal's attributes."
    ),
    "CICS:SET TERMINAL": owned(
        "state_mutation",
        reason="pre-#2990, unchanged: bare SET already fires state_mutation -- an SPI attribute WRITE is a real mutation, unlike the read-only INQUIRE/ASSIGN family.",
    ),
    # --- CICS: queue lifecycle (already owned pre-#2990) ---
    "CICS:WRITEQ TS": owned("io", reason="pre-#2990, unchanged."),
    "CICS:READQ TS": owned("io", reason="pre-#2990, unchanged."),
    "CICS:DELETEQ TS": owned("io", reason="pre-#2990, unchanged."),
    "CICS:WRITEQ TD": owned(
        "io",
        "telemetry",
        reason="pre-#2990 dual, unchanged: a transient-data write is a real io boundary AND the CICS journalling idiom.",
    ),
    # --- CICS: abort ---
    "CICS:ABEND": owned("panics_and_aborts", reason="pre-#2990, unchanged: terminates the task abnormally."),
    # --- CICS: exception suppression ---
    "CICS:IGNORE CONDITION": owned(
        "safety_bypasses",
        "test_skip",
        reason="pre-#2990 dual, unchanged: IGNORE CONDITION suppresses a handler (safety_bypasses); the bare word IGNORE is also test_skip's keyword.",
    ),
    # --- SQL: every EXEC SQL form fires the bare-block io + ipc_rpc_bridges alternative ---
    "SQL:INCLUDE": owned(
        "io",
        "ipc_rpc_bridges",
        reason="pre-#2990 base (bare EXEC SQL alternative). The `import` rule fires on ~89% of these blocks (it names a real copybook, e.g. SQLCA/ACCDB2) but only when INCLUDE starts its own physical line -- a pre-existing, formatting-dependent positional dual, out of #2990's scope to make deterministic.",
    ),
    "SQL:SELECT": owned("io", "ipc_rpc_bridges", reason="pre-#2990, unchanged."),
    "SQL:INSERT": owned("io", "ipc_rpc_bridges", reason="pre-#2990, unchanged."),
    "SQL:UPDATE": owned(
        "io",
        "state_mutation",
        "ipc_rpc_bridges",
        reason="pre-#2990, unchanged: an UPDATE ... SET is both a boundary and a write.",
    ),
    "SQL:DELETE": owned("io", "cleanup", "ipc_rpc_bridges", reason="pre-#2990, unchanged."),
    "SQL:DECLARE": owned("io", "ipc_rpc_bridges", reason="pre-#2990, unchanged: declares a cursor."),
    "SQL:OPEN": owned("io", "ipc_rpc_bridges", reason="pre-#2990, unchanged: opens a cursor."),
    "SQL:FETCH": owned("io", "ipc_rpc_bridges", reason="pre-#2990, unchanged: reads through a cursor."),
    "SQL:CLOSE": owned("io", "cleanup", "ipc_rpc_bridges", reason="pre-#2990, unchanged: releases a cursor."),
    "SQL:SET": owned(
        "io",
        "state_mutation",
        "ipc_rpc_bridges",
        reason="pre-#2990, unchanged: SET :host-var = expr writes through the SQL boundary.",
    ),
    "SQL:COMMIT": owned(
        "io",
        "safety",
        "ipc_rpc_bridges",
        reason="#2990: added `safety` -- unit-of-work control, the same transactional guard as SYNCPOINT/sqlite's COMMIT.",
    ),
    # --- DLI (no crucible occurrences yet; documented from the engine's own SQL-sibling design) ---
    # --- Native COBOL: math/statistical intrinsics -> scientific ---
    **{
        f"NATIVE:FUNCTION {n}": owned(
            "scientific",
            reason="#2990: a math/statistical intrinsic, widened alongside the existing ACOS/ASIN/.../VARIANCE set.",
        )
        for n in (
            "RANDOM",
            "INTEGER",
            "MOD",
            "INTEGER-PART",
            "REM",
            "MEAN",
            "STANDARD-DEVIATION",
            "MEDIAN",
            "MIDRANGE",
            "ORD-MIN",
            "VARIANCE",
            "ORD-MAX",
            "SUM",
            "RANGE",
            "ANNUITY",
            "FACTORIAL",
            "MAX",
            "MIN",
            "ACOS",
            "ASIN",
            "ATAN",
            "COS",
            "LOG",
            "LOG10",
            "PRESENT-VALUE",
            "SIN",
            "SQRT",
            "TAN",
        )
    },
    # --- Native COBOL: date/time intrinsics -> time_date_logic ---
    **{
        f"NATIVE:FUNCTION {n}": owned(
            "time_date_logic",
            reason="#2990: a date/time intrinsic, widened alongside the existing ACCEPT FROM DATE/TIME/DAY forms.",
        )
        for n in ("CURRENT-DATE", "INTEGER-OF-DATE", "DATE-OF-INTEGER", "DAY-OF-INTEGER", "INTEGER-OF-DAY")
    },
    "NATIVE:FUNCTION WHEN-COMPILED": owned(
        "branch",
        "time_date_logic",
        reason="#2990 dual: WHEN-COMPILED is time's, and every real occurrence is inside an IF/EVALUATE (branch's decision) -- an incidental corollary of the corpus's own usage, not a design requirement.",
    ),
    # --- Native COBOL: conversion intrinsics -> explicit_casts ---
    "NATIVE:FUNCTION NUMVAL": owned("explicit_casts", reason="#2990: string-to-numeric conversion."),
    "NATIVE:FUNCTION NUMVAL-C": owned(
        "explicit_casts", reason="#2990: string-to-numeric conversion (currency-edited)."
    ),
    # --- Native COBOL: string-processing intrinsics -- deliberately unowned ---
    **{
        f"NATIVE:FUNCTION {n}": none_owned(
            "a string-processing intrinsic (case/trim/length/reverse/ordinal); no cross-language rule owns generic string manipulation for any language in this registry -- out of #2990's scope, which targeted the CICS/SQL/DLI async and error-handling gap."
        )
        for n in (
            "TRIM",
            "UPPER-CASE",
            "LOWER-CASE",
            "LENGTH",
            "REVERSE",
            "ORD",
            "CHAR",
            "PIC",
            "TEST-NUMVAL-C",
            "TEST-NUMVAL",
        )
    },
    "NATIVE:FUNCTION FUNC1": none_owned(
        "a user-defined FUNCTION-ID (COBOL 2002+ allows programmer-defined intrinsics); not a library call this table can classify by name."
    ),
    # --- Native COBOL: error-handling idioms (safety / safety_bypasses) ---
    "NATIVE:DFHRESP(": owned(
        "safety",
        "branch",
        reason="#2990: `DFHRESP(` is the mainframe try/catch's value-level check (safety). branch also fires on 95% of real occurrences because the check is almost always written as an IF/EVALUATE condition -- an incidental corollary of the corpus's usage, not a design requirement of DFHRESP( itself.",
    ),
    "NATIVE:IF/EVALUATE SQLCODE": owned(
        "branch",
        "safety",
        reason="#2990: by construction this token IS an IF/EVALUATE (branch) testing SQLCODE (safety's value-level check) -- the dual is definitional.",
    ),
    "NATIVE:NOHANDLE": owned(
        "safety_bypasses",
        reason="#2990: switches CICS exception handling off for one command -- an error swallowed on purpose.",
    ),
    # --- Native COBOL: LE / Db2 service calls ---
    "NATIVE:CALL 'CEE3ABD'": owned(
        "panics_and_aborts",
        "ipc_rpc_bridges",
        reason="#2990: the Language Environment abend service -- the batch sibling of EXEC CICS ABEND. ipc_rpc_bridges already owns every CALL (unchanged).",
    ),
    "NATIVE:CALL 'DSNTIAR'": owned(
        "args",
        "telemetry",
        "ipc_rpc_bridges",
        reason="#2990: formats a Db2 diagnostic message (telemetry, the CEEMOUT class) -- its calling convention always passes the SQLCA and an output buffer, so args is a genuine property of this specific service call, not incidental.",
    ),
    "NATIVE:CALL 'CEEGMT'": owned(
        "args",
        "time_date_logic",
        "ipc_rpc_bridges",
        reason="#2990: an LE date/time service -- its calling convention always passes an output parameter, so args is a genuine property of this specific service call.",
    ),
    "NATIVE:CALL 'CEEDATM'": owned(
        "args", "time_date_logic", "ipc_rpc_bridges", reason="#2990: same LE date/time service family as CEEGMT."
    ),
    "NATIVE:CALL '<ordinary program>'": owned(
        "ipc_rpc_bridges",
        reason="pre-#2990, unchanged: an ordinary application CALL. `args` fires only when the call happens to pass a USING list (60% of the corpus's calls do) -- a property of the individual call site, not of 'calling a program' in general, so it is not required here.",
    ),
    # --- Native COBOL: deliberately unowned (recorded, not fixed) ---
    "NATIVE:SORT": none_owned(
        "a file-sort utility statement; no cross-language rule owns 'sort a dataset'. The io/branch noise below 90% share is from unrelated tokens (KEY, GIVING clauses) sharing SORT's captured line fragment, not SORT itself."
    ),
    "NATIVE:SEARCH": none_owned(
        "a table-search statement (SEARCH / SEARCH ALL); no cross-language rule owns linear/binary table search. The branch/api/safety_bypasses noise below 90% share is from a same-line WHEN/AT END/INVALID KEY clause, not SEARCH itself."
    ),
    "NATIVE:MERGE": none_owned("a file-merge utility statement, same family as SORT; no cross-language owner."),
    "NATIVE:INVOKE": none_owned(
        "invokes an OO-COBOL method; the crucible carries only 2 occurrences and no rule owns generic method invocation for this registry."
    ),
    "NATIVE:SIGNON": none_owned(
        "bare SIGNON outside an EXEC block -- every corpus occurrence is a paragraph name or comment "
        "(carddemo's SEND-SIGNON-SCREEN), not a command. The real EXEC CICS SIGNON/SIGNOFF/VERIFY "
        "PASSWORD/QUERY SECURITY commands are auth_middleware's since #3004 (EXEC-anchored precisely so "
        "these bare-word occurrences stay unowned)."
    ),
    "NATIVE:FILE STATUS clause": none_owned(
        "a data-item declaration naming the field a READ/WRITE populates with its status code, not a call or check itself; the field name is user-chosen so no keyword anchors it. The debug_prints noise (23%) is files whose status field happens to be tested near a DISPLAY, not a property of the clause."
    ),
    "NATIVE:ACCEPT FROM (env/arg)": none_owned(
        "reads a command-line argument or environment variable; distinct from python counting no `input()`/argv-read as io either -- kept consistent with that cross-language precedent rather than adding a COBOL-only exception."
    ),
    "NATIVE:GRANT/REVOKE": owned(
        "auth_middleware",
        reason="EXEC SQL GRANT/REVOKE, the DCL privilege boundary -- auth_middleware's since #3004 "
        "(db2_sql's standalone GRANT/REVOKE moved to the same key in that pass). 0 occurrences in the "
        "corpus today; the ownership row is engine-correctness ahead of corpus evidence, the same "
        "posture as NATIVE:WHENEVER.",
    ),
    "NATIVE:WHENEVER": none_owned(
        "EXEC SQL WHENEVER; 0 occurrences in the corpus today (the safety/safety_bypasses regex additions for its GO TO/CONTINUE forms are engine-correctness additions with no corpus evidence yet, the same posture as high_risk_execution's PREPARE/EXECUTE IMMEDIATE)."
    ),
}


EXPECTED_JCL: dict[str, Owner] = {
    # --- statement classes ---
    "STMT:DD": owned(
        "io",
        reason="io's real anchor requires the SAME line/continuation to carry DSN=/SYSOUT=; a DD DUMMY, in-stream `DD *`, or a DD covered entirely by a preceding JOBLIB/STEPLIB carries no target and legitimately dilutes this coarse per-statement bucket below the usual verb-level threshold -- the io_rule_contract's own C5 (a job-local temporary crosses no boundary).",
        min_share=0.5,
    ),
    "STMT:EXEC": owned(
        "func_start", reason="pre-#2990, unchanged: an EXEC statement is a callable unit (func_start's contract)."
    ),
    "STMT:JOB": owned(
        "class_start",
        reason="pre-#2990, unchanged: the JOB card is jcl's program-unit exception, the cobol-family precedent.",
    ),
    "STMT:INCLUDE": owned(
        "import", reason="pre-#2990, unchanged: INCLUDE MEMBER= is jcl's dependency-inclusion statement."
    ),
    "STMT:JCLLIB": none_owned(
        "JCLLIB ORDER= names a search library for later INCLUDE/PROC lookups -- it binds no unit itself (import corollary 1: a reference is not a declaration), same reasoning as JOBLIB not being `import` in cobol."
    ),
    "STMT:SET": owned(
        "state_mutation",
        "globals",
        reason="pre-#2990, unchanged: a job-wide symbol assignment is both a write and the creation of shared state (#2750's dual).",
    ),
    "STMT:IF": owned("branch", reason="pre-#2990, unchanged."),
    "STMT:ELSE": owned("branch", reason="pre-#2990, unchanged."),
    "STMT:ENDIF": none_owned(
        "a block closer, same class as cobol's END-* terminators -- structure, not a second decision."
    ),
    "STMT:PROC": owned(
        "api",
        reason="pre-#2990, unchanged: a PROC declaration is jcl's callable surface (the api contract's fallback family).",
    ),
    "STMT:PEND": none_owned(
        "closes an in-stream PROC; a closer, not a second declaration -- same reasoning as PROC's own doc note."
    ),
    "STMT:NOTIFY": none_owned(
        "the standalone `// NOTIFY user` job-completion-mail statement (distinct from the JOB card's NOTIFY= operand below); no cross-language rule owns 'notify on completion'."
    ),
    "STMT:EXPORT": owned(
        "globals",
        reason="pre-#2990, unchanged: EXPORT SYMLIST= makes symbols visible to in-stream data -- shared state.",
    ),
    # --- true JCL/dataset operand vocabulary ---
    "OPERAND:DISP=": owned(
        "io",
        "sync_locks",
        "cleanup",
        reason="pre-#2990, unchanged: DISP names the allocation (io); OLD/MOD is jcl's serialization primitive (#2733); a DELETE disposition is teardown (#2749). Each sub-share is well below 90% alone because most DISP values are the plain SHR/NEW/CATLG forms that trigger none of the three -- the three are read together, not required each on their own.",
        min_share=0.02,
    ),
    "OPERAND:DSN=": owned("io", reason="pre-#2990, unchanged: the dataset name is io's own anchor keyword."),
    "OPERAND:SYSOUT=": owned("io", reason="pre-#2990, unchanged."),
    "OPERAND:PGM=": owned("func_start", reason="pre-#2990, unchanged: PGM= is the EXEC step's callable unit."),
    "OPERAND:MEMBER=": owned(
        "import",
        min_share=0.5,
        reason="pre-#2990, unchanged for `// INCLUDE MEMBER=` (import's target). This corpus's MEMBER= keyword is also a plain PROC/utility parameter unrelated to INCLUDE (e.g. IEBCOPY's MEMBER= card) on ~44% of occurrences, co-occurring with func_start instead -- two distinct statement shapes sharing one keyword, not import failing to fire.",
    ),
    "OPERAND:NOTIFY=": owned(
        "class_start",
        min_share=0.85,
        reason="pre-#2990: NOTIFY= sits on the JOB card, so class_start's capture (which spans the whole card) fires alongside it -- an artifact of the census unit, not a claim that NOTIFY= itself is class_start's. telemetry co-occurs on ~37% (the JOB card also carries MSGCLASS=/CLASS=) but is not required.",
    ),
    "OPERAND:REGION=": none_owned(
        "a step/job memory-region-size attribute; no cross-language rule owns memory sizing. It sits on the same JOB/EXEC card as MSGLEVEL=/MSGCLASS= (telemetry, 52%) and PGM=/PROC= (func_start, 38%) often enough to show up as noise, but neither reaches a share that makes REGION= itself their owner."
    ),
    "OPERAND:MSGCLASS=": owned(
        "telemetry",
        reason="pre-#2990, unchanged: telemetry's own operand. class_start co-occurs on 65% of occurrences (the JOB card) but is not required.",
    ),
    "OPERAND:ORDER=": none_owned(
        "JCLLIB ORDER='s library list; same reasoning as the JCLLIB statement itself -- a reference, not a declaration."
    ),
    "OPERAND:CLASS=": owned(
        "telemetry",
        min_share=0.85,
        reason="pre-#2990: the JOB card's output class -- telemetry's observability-dial family. class_start co-occurs on 85% (the JOB card) but is close enough to the floor that it is not separately required.",
    ),
    "OPERAND:BLKSIZE=": owned(
        "io",
        min_share=0.2,
        reason="a DCB attribute; io fires only when it rides the same continuation as a fresh DSN=/SYSOUT= (25%) -- most BLKSIZE= values in this corpus modify a DD that references another dataset's DCB (DCB=*.step.dd) and inherit that boundary instead of opening a new one.",
    ),
    "OPERAND:RECFM=": owned(
        "io",
        min_share=0.2,
        reason="same DCB-attribute reasoning as BLKSIZE= -- io fires only when it rides the same continuation as a fresh DSN=/SYSOUT=.",
    ),
    "OPERAND:DSORG=": owned("io", min_share=0.2, reason="same DCB-attribute reasoning as BLKSIZE=/RECFM=."),
    "OPERAND:MSGLEVEL=": owned(
        "telemetry", reason="pre-#2990, unchanged: what the job log records -- telemetry's own operand."
    ),
    "OPERAND:VOL=": none_owned(
        "a volume-serial allocation attribute; no cross-language rule owns 'which physical volume'."
    ),
    "OPERAND:UNIT=": none_owned(
        "a device/unit-type allocation attribute; no cross-language rule owns device selection. The cleanup/sync_locks noise (<1% each) is DISP=(...,DELETE)/DISP=OLD sharing the same continuation line, not UNIT= itself."
    ),
    "OPERAND:SPACE=": none_owned(
        "a space-allocation attribute (primary/secondary extents); no cross-language rule owns storage sizing. The sync_locks/state_mutation/globals noise (~2% each) is other operands on the same continuation line, not SPACE= itself."
    ),
    "OPERAND:PARM=": owned(
        "args",
        min_share=0.6,
        reason="pre-#2990, unchanged: PARM= is the EXEC step's parameter (args). func_start co-occurs on 67% (the same EXEC step) but is not separately required.",
    ),
    "OPERAND:DYNAMNBR=": owned(
        "func_start",
        "high_risk_execution",
        reason="#2751: DYNAMNBR only ever appears on the same EXEC step as one of the command-executor programs (IKJEFT01 etc.) this corpus plants -- co-occurrence, not a claim that DYNAMNBR itself is dangerous.",
    ),
    "OPERAND:LRECL=": none_owned("a DCB record-length attribute; no cross-language rule owns record-length."),
    "OPERAND:DCB=": owned(
        "io",
        min_share=0.3,
        reason="references another dataset's DCB attributes on the same DD -- io fires only when that DD ALSO carries its own fresh DSN=/SYSOUT= on the same continuation window (42%); a DCB=*.step.dd cross-reference alone inherits the target rather than opening one.",
    ),
    "OPERAND:OUTLIM=": owned("io", reason="pre-#2990, unchanged: a SYSOUT limit -- io's own operand family."),
    "OPERAND:COND=": owned("safety", reason="pre-#2990, unchanged: a return-code test -- jcl's error-handling idiom."),
    "OPERAND:DSNAME=": owned(
        "io",
        min_share=0.8,
        reason="the long form of DSN= -- same boundary. This corpus's 33 occurrences are concentrated in 6 files, so the share is noisier than DSN='s 499-occurrence spread.",
    ),
    "OPERAND:DSNTYPE=": none_owned(
        "a dataset-type qualifier (PDS/PDSE/LIBRARY); no cross-language rule owns dataset-type classification."
    ),
    "OPERAND:OUTC=": none_owned(
        "a SYSOUT class override distinct from the JOB card's CLASS=; no dedicated rule, and it never co-occurs with telemetry at this corpus's sample size."
    ),
    "OPERAND:PROC=": owned(
        "func_start", reason="the keyword form of `EXEC PROC=name` -- same callable-unit contract as bare `EXEC name`."
    ),
    "OPERAND:RMODE=": owned(
        "func_start",
        reason="co-occurs with func_start (the binder attribute rides the same EXEC step as PGM=/PROC=); not a claim RMODE= itself is a callable unit.",
    ),
    "OPERAND:SYMBOLS=": none_owned("a loader symbol-table option; no cross-language owner."),
    "OPERAND:HLQ=": owned(
        "state_mutation",
        "globals",
        reason="a `// SET HLQ=` high-level-qualifier symbol -- same dual as the SET statement itself.",
    ),
    "OPERAND:TIME=": owned(
        "func_start",
        min_share=0.85,
        reason="a step time limit; co-occurs with func_start (the same EXEC step) on 7 of 8 occurrences -- the corpus's smallest reliably-attributed operand sample.",
    ),
    "OPERAND:DDNAME=": none_owned(
        "cross-references another DD's name (e.g. for SYSOUT routing); no dedicated rule, and this corpus's 4 files show no consistent co-occurrence."
    ),
    "OPERAND:SRC=": owned(
        "func_start",
        "args",
        "api",
        min_share=0.5,
        reason="a build-utility PROC's source-member keyword parameter; co-occurs with func_start/args/api the same way PARM= does (each at exactly half of this tiny 6-occurrence sample).",
    ),
    "OPERAND:BLK=": owned("state_mutation", "globals", reason="a `// SET BLK=` symbol -- same SET dual."),
    "OPERAND:CMPLLIB=": owned(
        "state_mutation",
        "globals",
        min_share=0.7,
        reason="a `// SET CMPLLIB=` symbol -- same SET dual (3 of its 4 occurrences).",
    ),
    "OPERAND:MBR=": owned(
        "args",
        min_share=0.7,
        reason="a PROC's member-name keyword parameter -- same PARM=/PROC= family. func_start co-occurs on 3 of 4 occurrences but is not separately required.",
    ),
    "OPERAND:MEMLIMIT=": none_owned(
        "a step memory limit; no dedicated rule, and its 4 occurrences show no consistent co-occurrence."
    ),
    "OPERAND:START=": none_owned("a PROC's step-start-point override (restart control); no dedicated rule."),
    "OPERAND:LIBPRFX=": owned(
        "args", "api", reason="a build-utility PROC's library-prefix keyword parameter -- same PARM=/PROC= family."
    ),
    "OPERAND:LINKLIB=": owned("state_mutation", "globals", reason="a `// SET LINKLIB=` symbol -- same SET dual."),
    "OPERAND:LNGPRFX=": owned("args", "api", reason="same build-utility PROC-parameter family as LIBPRFX="),
    "PGM:*": owned(
        "func_start",
        reason="pre-#2990, unchanged: PGM= is func_start's callable unit; a minority also names one of #2751's command-executor programs (high_risk_execution, 34%) or carries COND=/PARM= on the same line (safety/args) -- real but not universal co-occurrences, not claims about PGM= itself.",
    ),
    "OPERAND:<installation- or application-specific>": owned(
        "func_start",
        min_share=0.3,
        reason="#2990: a catch-all for `EXEC PROC=name,SYM1=val1,...` keyword symbolic overrides whose names are site- or application-defined (APPLID=, GRPLIST=, KEYRING=, dozens more, each 1-2 files) -- real `//` statement operands, but not JCL language vocabulary; bucketed rather than given one row per site-specific symbol name. Most co-occur with func_start (they ride the same EXEC/PROC step as PGM=/PROC=) at well under the single-verb threshold because the bucket spans many unrelated PROCs.",
    ),
    # --- the CICS WS-bind utility's fixed symbolic set (8 files, > the installation floor) ---
    **{
        f"OPERAND:{k}=": none_owned(
            "a fixed keyword parameter of the CICS Web Services bind utility PROC (DFHWBSVC/DFHWBTUP); real, recurring vocabulary across this corpus's 8 CICS Explorer samples, but application/product-specific, not JCL language vocabulary -- no cross-language rule owns it."
        )
        for k in ("JAVADIR", "PATHPREF", "TMPDIR", "TMPFILE", "USSDIR")
    },
    # --- #3002: Db2 DSN command processor / IDCAMS verbs inside a DD */DATA
    # payload. Checked against docs/high_risk_execution_rule_contract.md
    # (#2878) verb by verb, not as one blob -- full reasoning in jcl.py's own
    # comment above the high_risk_execution rule.
    "PAYLOAD:DSN SYSTEM": none_owned(
        "#3002: runs inside a DSN session an IKJEFT01 step already launched -- high_risk_execution already counts that step; a payload hit would recount the same execution decision at finer grain (the #2751 problem, in miniature)."
    ),
    "PAYLOAD:RUN PROGRAM": none_owned(
        "#3002: same reasoning as DSN SYSTEM -- the launching IKJEFT01 step is high_risk_execution's real owner, not the command it's told to run."
    ),
    "PAYLOAD:GRANT": none_owned(
        "#3002: Db2 DCL; doesn't fit any of high_risk_execution's five contract families. Same auth-surface gap as cobol's EXEC SQL GRANT/REVOKE (NATIVE:GRANT/REVOKE above) -- recorded the same way, not ad hoc."
    ),
    "PAYLOAD:DROP": none_owned(
        "#3002: DSN's DROP (table/tablespace, not DROP DATABASE) is IDCAMS/DSN's own fixed command grammar -- the same reasoning that already excludes IDCAMS itself from high_risk_execution (destructive-capable utility, fixed command language, the rm/rm-rf analogy)."
    ),
    "PAYLOAD:DELETE": none_owned(
        "#3002: IDCAMS DELETE removes one dataset -- per the contract's C4, single-item deletion is cleanup's question, not high_risk_execution's, and jcl's cleanup rule already models this exact teardown idiom at the DISP=(...,DELETE) layer. A payload DELETE restates that decision in IDCAMS syntax, not a new one."
    ),
    "PAYLOAD:BIND": owned(
        "high_risk_execution",
        min_share=0.45,
        reason="#3010: BIND PACKAGE(/BIND PLAN( installs an executable Db2 package -- contract family (c) 'loading or rewriting code' (sqlite's load_extension( is the same family). The rule anchors on the statement form per C2, so the DYNAMICRULES(BIND)/VALIDATE(BIND) bind-time-option lines this \\bBIND\\b census also sweeps up (roughly half the samples, hence the floor) deliberately never fire; the DD */DD DATA span bound itself lives in detector.py's jcl_instream_payload scope filter, which attribute() rightly doesn't run.",
    ),
    "PAYLOAD:DEFINE CLUSTER": none_owned(
        "#3002: IDCAMS's VSAM-allocation command -- io's territory conceptually (it names a dataset to create), not high_risk_execution's; same fixed-command-language reasoning as the rest of the IDCAMS family."
    ),
    "PAYLOAD:REPRO": none_owned(
        "#3002: IDCAMS's copy-between-datasets command -- io's territory conceptually, not high_risk_execution's; same fixed-command-language reasoning as DEFINE CLUSTER."
    ),
    "PAYLOAD:FREE": none_owned(
        "#3002: releases a dataset allocation -- cleanup-shaped (same family as DELETE above), not high_risk_execution's."
    ),
}

EXPECTED: dict[str, dict[str, Owner]] = {"cobol": EXPECTED_COBOL, "jcl": EXPECTED_JCL}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lang", choices=("cobol", "jcl"))
    ap.add_argument("--corpus", choices=("crucible", "rosetta", "both"), default="both")
    ap.add_argument("--extra", nargs="*", type=Path, default=[], help="extra directories to include in the census")
    ap.add_argument("--check", action="store_true", help="exit 1 on any GAP/MISMATCH")
    ap.add_argument("--all", action="store_true", help="print every verb, not just GAP/MISMATCH")
    ap.add_argument("--markdown", help="write the coverage table to this path")
    ap.add_argument("--dump-owners", action="store_true", help="print verb -> observed-owner-set (bootstrap EXPECTED)")
    args = ap.parse_args(argv)

    rows = build_rows(args.lang, args.corpus, args.extra)

    if args.dump_owners:
        for r in rows:
            share = ", ".join(f"{k}={c}/{r.n}" for k, c in r.observed.most_common())
            print(f"{r.verb}\tn={r.n}\tfiles={r.files}\towners=({share})")
        return 0

    rc = print_report(args.lang, rows, args.all)
    if args.markdown:
        Path(args.markdown).write_text(render_markdown(args.lang, rows))
        print(f"markdown written: {args.markdown}")
    return rc if args.check else 0


if __name__ == "__main__":
    raise SystemExit(main())
