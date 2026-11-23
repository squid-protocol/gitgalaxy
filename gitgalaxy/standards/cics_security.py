# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""The CICS security model, step 1 of the CICS cross-program SAST milestone (#8606): what counts as untrusted input
and as a sensitive operation in a CICS COBOL estate, as data. Standard library only; nothing imports it yet.

This table makes NO detection claim. It says what the engine will treat as a source, a conduit, a sink or a
sanitizer once a later step reads it; no step has measured any detection yet (step 3 does).

Every entry cites the IBM manual for the release named in MANUALS. A manual page names the command and the operand;
none of them says "untrusted". That a value is untrusted, or that a stated check sanitizes it, is OUR classification:
an entry whose status is "assumed" says so, and "refused" names what we decline to call a sanitizer or a source.

Roles:
  source          data a program takes in from outside its own code (a terminal, another program, a queue, HTTP).
  protected_read  data read from a file or a table; the origin the "disclosure" sink class is defined against.
  conduit         moves a value between programs or tasks, so a cross-program tracker must follow it.
  sink            a sensitive operation, by `sink_class`: sql_injection, file_write, control_transfer, disclosure.
  sanitizer       a check or conversion that removes the taint, stated as narrowly as the manual allows.
  not_a_sanitizer a check a reader may take for validation and we do not (refused by name).
Anything the burned estates use that is none of these is in NOT_SECURITY_RELEVANT with its reason."""

from __future__ import annotations

import re
from dataclasses import dataclass

MODEL_VERSION = 1

# The manuals every cite is to. The release is part of the name: a cite is to this edition and no other.
MANUALS: dict[str, str] = {
    "cics-api": "IBM CICS Transaction Server for z/OS, Version 6, API Reference",
    "cics-app": "IBM CICS Transaction Server for z/OS, Version 6, Developing CICS Applications",
    "db2-sql": "IBM Db2 13 for z/OS, SQL Reference",
    "db2-apsg": "IBM Db2 13 for z/OS, Application Programming and SQL Guide",
    "cobol-lr": "IBM Enterprise COBOL for z/OS 6.4, Language Reference",
}
ROLES = frozenset({"source", "protected_read", "conduit", "sink", "sanitizer", "not_a_sanitizer"})
SINK_CLASSES = frozenset({"sql_injection", "file_write", "control_transfer", "disclosure"})
STATUSES = frozenset({"classified", "assumed", "refused"})
KINDS = frozenset({"exec_cics", "exec_sql", "linkage", "cobol"})


@dataclass(frozen=True)
class Cite:
    """A section of one manual in MANUALS, by the title the manual gives it."""

    manual: str
    section: str


@dataclass(frozen=True)
class Entry:
    """One classification. `key` is the EXEC verb as the lookup reads it (one or two words), or a name for a
    linkage / COBOL construct. `operands` are the operands the role applies to; `when` narrows it (a sink fires
    only for an operand that is a data name, never a literal)."""

    key: str
    kind: str
    role: str
    operands: tuple[str, ...]
    cites: tuple[Cite, ...]
    status: str = "classified"
    sink_class: str | None = None
    when: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        if self.kind not in KINDS or self.role not in ROLES or self.status not in STATUSES:
            raise ValueError(f"{self.key}: unknown kind, role or status")
        if (self.role == "sink") != (self.sink_class is not None) or (
            self.sink_class is not None and self.sink_class not in SINK_CLASSES
        ):
            raise ValueError(f"{self.key}: a sink names one sink class and nothing else does")
        if not self.cites and self.status != "refused":
            raise ValueError(f"{self.key}: every entry cites its manual")
        for c in self.cites:
            if c.manual not in MANUALS or not c.section:
                raise ValueError(f"{self.key}: cite {c!r} is to no manual in MANUALS")
        if self.status in ("assumed", "refused") and not self.note:
            raise ValueError(f"{self.key}: an assumed or refused entry says what the manual leaves open")


def _c(manual: str, *sections: str) -> tuple[Cite, ...]:
    return tuple(Cite(manual, s) for s in sections)


_API = "cics-api"
_APP = "cics-app"
_SQL = "db2-sql"
_APSG = "db2-apsg"
_COB = "cobol-lr"
_OUT = ("FROM",)

# ---- sources ------------------------------------------------------------------------------------------------------
_SOURCES = (
    Entry("RECEIVE", "exec_cics", "source", ("INTO", "SET"), _c(_API, "RECEIVE")),
    Entry(
        "RECEIVE MAP",
        "exec_cics",
        "source",
        ("INTO", "SET"),
        _c(_API, "RECEIVE MAP"),
        note="every symbolic-map input field (xxxI) is one source field",
    ),
    Entry(
        "DFHCOMMAREA",
        "linkage",
        "source",
        ("DFHCOMMAREA",),
        _c(_APP, "Passing data to other programs", "Communication areas"),
        status="assumed",
        when="read in a program a LINK, XCTL or RETURN TRANSID can reach, not one that only starts a task",
        note="the manual says a COMMAREA passes data between programs and is silent on whether the caller is "
        "trusted; we treat it as untrusted because a cross-program tracker cannot see every caller",
    ),
    Entry("GET CONTAINER", "exec_cics", "source", ("INTO", "SET"), _c(_API, "GET CONTAINER (CHANNEL)")),
    Entry("GET64 CONTAINER", "exec_cics", "source", ("INTO", "SET"), _c(_API, "GET64 CONTAINER")),
    Entry(
        "READQ",
        "exec_cics",
        "source",
        ("INTO", "SET"),
        _c(_API, "READQ TS", "READQ TD"),
        status="assumed",
        note="IBM does not say who wrote a queue's records; the queue is a source on the reading side and a conduit "
        "on the writing side (WRITEQ), and a tracker that sees the writer's taint may join them",
    ),
    Entry(
        "RETRIEVE",
        "exec_cics",
        "source",
        ("INTO", "SET"),
        _c(_API, "RETRIEVE"),
        note="data passed by a START FROM in another task",
    ),
    Entry("WEB RECEIVE", "exec_cics", "source", ("INTO", "SET"), _c(_API, "WEB RECEIVE")),
    Entry(
        "WEB READ",
        "exec_cics",
        "source",
        ("VALUE", "SET"),
        _c(_API, "WEB READ FORMFIELD", "WEB READ HTTPHEADER", "WEB READ QUERYPARM"),
    ),
    Entry(
        "WEB EXTRACT",
        "exec_cics",
        "source",
        ("QUERYSTRING", "PATH", "HOST", "HTTPMETHOD"),
        _c(_API, "WEB EXTRACT"),
        note="the request line and headers of an HTTP request CICS serves (CICS as the HTTP server)",
    ),
    Entry(
        "WEB CONVERSE",
        "exec_cics",
        "source",
        ("INTO", "SET"),
        _c(_API, "WEB CONVERSE"),
        status="assumed",
        note="the response of a server CICS called; the manual does not call the remote side trusted or not, we do not",
    ),
)

# ---- protected reads (the origin of a "disclosure") ---------------------------------------------------------------
_PROTECTED = (
    Entry("READ", "exec_cics", "protected_read", ("INTO", "SET"), _c(_API, "READ")),
    Entry("READNEXT", "exec_cics", "protected_read", ("INTO", "SET"), _c(_API, "READNEXT")),
    Entry("READPREV", "exec_cics", "protected_read", ("INTO", "SET"), _c(_API, "READPREV")),
    Entry(
        "SELECT",
        "exec_sql",
        "protected_read",
        ("INTO",),
        _c(_SQL, "select-statement", "SELECT INTO statement"),
        when="a host variable in the INTO clause",
    ),
    Entry("FETCH", "exec_sql", "protected_read", ("INTO",), _c(_SQL, "FETCH statement")),
    Entry(
        "FILE_AND_TABLE_CONTENT",
        "linkage",
        "protected_read",
        (),
        _c(_API, "READ"),
        status="assumed",
        note="a file or table is not itself an untrusted source: a record read back is taken as protected data, not as "
        "attacker input. Data a program wrote into it from a source is second-order and not modelled in step 1",
    ),
)

# ---- conduits ------------------------------------------------------------------------------------------------------
_CONDUITS = (
    Entry(
        "LINK",
        "exec_cics",
        "conduit",
        ("COMMAREA", "CHANNEL", "INPUTMSG"),
        _c(_API, "LINK"),
        note="the value arrives in the callee's DFHCOMMAREA or in the channel's containers",
    ),
    Entry("XCTL", "exec_cics", "conduit", ("COMMAREA", "CHANNEL", "INPUTMSG"), _c(_API, "XCTL")),
    Entry("RETURN", "exec_cics", "conduit", ("COMMAREA", "CHANNEL"), _c(_API, "RETURN")),
    Entry("START", "exec_cics", "conduit", ("FROM", "CHANNEL"), _c(_API, "START"), note="read back by RETRIEVE"),
    Entry("PUT CONTAINER", "exec_cics", "conduit", ("FROM",), _c(_API, "PUT CONTAINER (CHANNEL)")),
    Entry("PUT64 CONTAINER", "exec_cics", "conduit", ("FROM",), _c(_API, "PUT64 CONTAINER")),
    Entry("WRITEQ", "exec_cics", "conduit", ("FROM",), _c(_API, "WRITEQ TS", "WRITEQ TD"), note="read back by READQ"),
)

# ---- sinks ---------------------------------------------------------------------------------------------------------
_VAR_NAME = "the operand is a data name, not a literal"
_SINKS = (
    Entry(
        "PREPARE",
        "exec_sql",
        "sink",
        ("FROM",),
        _c(_SQL, "PREPARE statement"),
        sink_class="sql_injection",
        when="the statement string is a host variable",
    ),
    Entry(
        "EXECUTE IMMEDIATE",
        "exec_sql",
        "sink",
        ("host-variable",),
        _c(_SQL, "EXECUTE IMMEDIATE statement"),
        sink_class="sql_injection",
        when="the statement string is a host variable",
    ),
    Entry(
        "WRITE",
        "exec_cics",
        "sink",
        ("FROM", "RIDFLD"),
        _c(_API, "WRITE"),
        sink_class="file_write",
        when="the record or the key holds a value from a source",
    ),
    Entry("REWRITE", "exec_cics", "sink", ("FROM",), _c(_API, "REWRITE"), sink_class="file_write", when="as WRITE"),
    Entry(
        "DELETE",
        "exec_cics",
        "sink",
        ("RIDFLD",),
        _c(_API, "DELETE"),
        sink_class="file_write",
        when="the key holds a value from a source (a DELETE of the record just read has no key operand)",
    ),
    Entry(
        "LINK",
        "exec_cics",
        "sink",
        ("PROGRAM",),
        _c(_API, "LINK"),
        sink_class="control_transfer",
        when=_VAR_NAME,
    ),
    Entry("XCTL", "exec_cics", "sink", ("PROGRAM",), _c(_API, "XCTL"), sink_class="control_transfer", when=_VAR_NAME),
    Entry("START", "exec_cics", "sink", ("TRANSID",), _c(_API, "START"), sink_class="control_transfer", when=_VAR_NAME),
    Entry(
        "RETURN",
        "exec_cics",
        "sink",
        ("TRANSID",),
        _c(_API, "RETURN"),
        sink_class="control_transfer",
        status="assumed",
        when=_VAR_NAME,
        note="not in the issue's list; it chooses the next transaction the way START TRANSID does, so it is "
        "classified with it. IBM says nothing on who may name it",
    ),
    Entry(
        "RUN",
        "exec_cics",
        "sink",
        ("TRANSID",),
        _c(_API, "RUN TRANSID"),
        sink_class="control_transfer",
        status="assumed",
        when=_VAR_NAME,
        note="as RETURN TRANSID",
    ),
    Entry(
        "SEND",
        "exec_cics",
        "sink",
        _OUT,
        _c(_API, "SEND"),
        sink_class="disclosure",
        when="FROM holds a value that came from a protected_read",
    ),
    Entry(
        "SEND MAP",
        "exec_cics",
        "sink",
        _OUT,
        _c(_API, "SEND MAP"),
        sink_class="disclosure",
        when="a map output field (xxxO) holds a value that came from a protected_read",
    ),
    Entry(
        "SEND TEXT",
        "exec_cics",
        "sink",
        _OUT,
        _c(_API, "SEND TEXT"),
        sink_class="disclosure",
        when="FROM holds a value that came from a protected_read",
    ),
    Entry(
        "WEB SEND",
        "exec_cics",
        "sink",
        _OUT,
        _c(_API, "WEB SEND (Server)"),
        sink_class="disclosure",
        when="FROM holds a value that came from a protected_read",
    ),
)

# ---- sanitizers, stated narrowly, and what we decline to call one -------------------------------------------------
_SANITIZERS = (
    Entry(
        "NUMERIC class test",
        "cobol",
        "sanitizer",
        (),
        _c(_COB, "Class condition"),
        when="the item is tested IS NUMERIC and the failing branch leaves the use; it removes the taint of digits-only "
        "content for the SQL and control-transfer classes, never a range",
    ),
    Entry(
        "BIF DEEDIT",
        "exec_cics",
        "sanitizer",
        ("FIELD",),
        _c(_API, "BIF DEEDIT"),
        when="the field is the one DEEDIT rewrites in place; the IBM text says non-digits are removed, so what is left is "
        "digits only, and no range or length check is implied",
    ),
    Entry(
        "fixed-set comparison",
        "cobol",
        "sanitizer",
        (),
        _c(_COB, "Condition-name condition", "EVALUATE statement"),
        when="the value is compared for equality against literals or an 88-level over literals, every other value "
        "leaves the use, and the checked item is the one then used; for the control_transfer class only",
    ),
    Entry(
        "EIBCALEN check",
        "cobol",
        "not_a_sanitizer",
        (),
        (),
        status="refused",
        note="EIBCALEN tests how many bytes a COMMAREA holds, not what they are",
    ),
    Entry(
        "INQUIRE PROGRAM check",
        "exec_cics",
        "not_a_sanitizer",
        (),
        (),
        status="refused",
        note="proves a program name is installed, not that this caller may choose it",
    ),
    Entry(
        "MOVE or INSPECT REPLACING",
        "cobol",
        "not_a_sanitizer",
        (),
        (),
        status="refused",
        note="a MOVE truncates or pads and INSPECT replaces named characters; neither establishes a safe set",
    ),
    Entry(
        "HANDLE CONDITION or RESP test",
        "exec_cics",
        "not_a_sanitizer",
        (),
        (),
        status="refused",
        note="tests that a command succeeded (RESP), not what it returned",
    ),
    Entry(
        "static SQL host variable",
        "exec_sql",
        "not_a_sanitizer",
        (),
        _c(_APSG, "Using host variables in SQL statements"),
        status="assumed",
        note="a host variable in a static statement is bound as a value, never parsed as SQL text, so it is not an "
        "injection sink; this is our reading of the Db2 text, which does not use the word 'injection'",
    ),
)

ENTRIES: tuple[Entry, ...] = _SOURCES + _PROTECTED + _CONDUITS + _SINKS + _SANITIZERS

# ---- not security-relevant (the second half of "classified or listed as not security-relevant") --------------------
_ENV = "reads or changes the task's own state, no external data and no sensitive effect"
NOT_SECURITY_RELEVANT: dict[tuple[str, str], str] = {
    ("exec_cics", "ABEND"): "ends the task; no data flow",
    ("exec_cics", "ASKTIME"): _ENV,
    (
        "exec_cics",
        "ASSIGN",
    ): "returns task and system facts (user id, terminal) the region sets, not data a sender chose",
    ("exec_cics", "DEFINE COUNTER"): "named counter set-up; a counter holds a number, not a program name or a record",
    ("exec_cics", "DEFINE DCOUNTER"): "as DEFINE COUNTER",
    ("exec_cics", "DELAY"): _ENV,
    ("exec_cics", "DELETE COUNTER"): "as DEFINE COUNTER",
    (
        "exec_cics",
        "DELETEQ",
    ): "removes a queue; deleting is not writing tainted data (a queue NAME from a source is a later-step question)",
    ("exec_cics", "DEQ"): _ENV,
    (
        "exec_cics",
        "DOCUMENT CREATE",
    ): "builds a document in the task's own storage; its output reaches a sink through SEND or WEB SEND",
    ("exec_cics", "DOCUMENT RETRIEVE"): "reads back the task's own document",
    ("exec_cics", "ENDBR"): "closes a browse; no data flow",
    ("exec_cics", "ENQ"): _ENV,
    ("exec_cics", "FETCH ANY"): "returns a child task's completion, not external data",
    ("exec_cics", "FETCH CHILD"): "as FETCH ANY",
    ("exec_cics", "FORMATTIME"): _ENV,
    ("exec_cics", "FREEMAIN"): _ENV,
    ("exec_cics", "GET COUNTER"): "as DEFINE COUNTER",
    ("exec_cics", "GET DCOUNTER"): "as DEFINE COUNTER",
    ("exec_cics", "GETMAIN"): _ENV,
    ("exec_cics", "GETNEXT CONTAINER"): "returns a container NAME while browsing; the data comes through GET CONTAINER",
    ("exec_cics", "HANDLE"): "sets how a condition is handled (see the not_a_sanitizer row)",
    ("exec_cics", "INQUIRE"): "SPI query of a resource (program, terminal, URIMAP, association); not user data",
    ("exec_cics", "QUERY COUNTER"): "as DEFINE COUNTER",
    ("exec_cics", "SEND CONTROL"): "terminal control, carries no data area",
    ("exec_cics", "SET"): "SPI change of a resource attribute (SET TERMINAL); not a data-bearing operation",
    ("exec_cics", "SOAPFAULT"): "builds a SOAP fault from fixed text; a web-service command outside step 1",
    ("exec_cics", "STARTBR"): "positions a browse; the data comes through READNEXT and READPREV",
    ("exec_cics", "STARTBROWSE CONTAINER"): "as GETNEXT CONTAINER",
    ("exec_cics", "SYNCPOINT"): "commits or rolls back; no data flow",
    ("exec_cics", "WEB CLOSE"): "closes an outbound HTTP session",
    (
        "exec_cics",
        "WEB OPEN",
    ): "chooses an outbound HTTP target (SSRF); outside the issue's sink list, deferred to a later step",
    ("exec_cics", "WEB PARSE"): "splits a URL into parts in the task's own storage",
    ("exec_cics", "WEB WRITE"): "writes an HTTP header into the response being built; outside the issue's sink list",
    ("exec_cics", "WRITE OPERATOR"): "writes to the operator console; log forging is outside the issue's sink list",
}
# SQL statements not in ENTRIES.
NOT_SECURITY_RELEVANT.update(
    {
        ("exec_sql", "CLOSE"): "closes a cursor",
        ("exec_sql", "COMMIT"): "ends a unit of work",
        ("exec_sql", "DECLARE"): "declares a cursor, table or statement; names no runtime value",
        (
            "exec_sql",
            "DELETE",
        ): "static SQL: host variables bind as values (see the static SQL host variable row); stored taint is second-order",
        ("exec_sql", "INCLUDE"): "pulls in a copybook or the SQLCA at compile time",
        ("exec_sql", "INSERT"): "as static DELETE",
        ("exec_sql", "OPEN"): "opens a cursor; the host variables in its WHERE clause bind as values",
        ("exec_sql", "SET"): "assigns a special register or host variable",
        ("exec_sql", "UPDATE"): "as static DELETE",
        ("exec_sql", "WHENEVER"): "error-branch directive",
    }
)

# The verbs the burned estates use (CardDemo, CBSA, GenApp, zECS, DBB MortgageApplication, cicsdev async credit-card,
# example-health-apis), COBOL sources only (zECS's assembler ZECSNC also issues DEFINE DCOUNTER; the entry stays), counted once: the test re-derives them from the pinned corpora when they are present, and
# checks every one is classified or listed above.
BURNED_CICS_VERBS = frozenset(
    {
        "ABEND", "ASKTIME", "ASSIGN", "BIF DEEDIT", "DEFINE COUNTER", "DELAY", "DELETE",
        "DELETE COUNTER", "DELETEQ", "DEQ", "DOCUMENT CREATE", "DOCUMENT RETRIEVE", "ENDBR", "ENQ", "FETCH ANY",
        "FETCH CHILD", "FORMATTIME", "FREEMAIN", "GET CONTAINER", "GET COUNTER", "GET DCOUNTER", "GETMAIN",
        "GETNEXT CONTAINER", "HANDLE", "INQUIRE", "LINK", "PUT CONTAINER", "QUERY COUNTER", "READ", "READNEXT",
        "READPREV", "READQ", "RECEIVE", "RECEIVE MAP", "RETRIEVE", "RETURN", "REWRITE", "RUN", "SEND", "SEND CONTROL",
        "SEND MAP", "SEND TEXT", "SET", "SOAPFAULT", "START", "STARTBR", "STARTBROWSE CONTAINER", "SYNCPOINT",
        "WEB CLOSE", "WEB CONVERSE", "WEB EXTRACT", "WEB OPEN", "WEB PARSE", "WEB READ", "WEB RECEIVE", "WEB SEND",
        "WEB WRITE", "WRITE", "WRITE OPERATOR", "WRITEQ", "XCTL",
    }
)  # fmt: skip
BURNED_SQL_VERBS = frozenset(
    {"CLOSE", "COMMIT", "DECLARE", "DELETE", "FETCH", "INCLUDE", "INSERT", "OPEN", "SELECT", "SET", "UPDATE"}
)
# Dynamic SQL no burned program uses; classified from the manual alone, so no case here proves a tracker finds it.
UNUSED_BY_BURNED = ("PREPARE", "EXECUTE IMMEDIATE", "WEB READ HTTPHEADER and QUERYPARM forms")


def classified_keys(kind: str) -> set[str]:
    """Every verb of `kind` the table classifies (an Entry) or lists as not security-relevant."""
    keys = {e.key for e in ENTRIES if e.kind == kind}
    keys |= {k for (kd, k) in NOT_SECURITY_RELEVANT if kd == kind}
    return keys


_WORD = re.compile(r"[A-Z0-9$#@-]+")


def canonical_verb(kind: str, body: str) -> str:
    """The table key an EXEC body (the text between `EXEC CICS` or `EXEC SQL` and `END-EXEC`) names: the two-word
    form when that is a key, else the first word. Operands are dropped. `INQUIRE`, `SET` and `HANDLE` stay one word
    (their object names are not verbs)."""
    words = _WORD.findall(re.sub(r"\(.*?\)", " ", body.upper()))
    if not words:
        return ""
    known = classified_keys(kind)
    if len(words) > 1 and f"{words[0]} {words[1]}" in known:
        return f"{words[0]} {words[1]}"
    return words[0]


def entries_for(kind: str, verb: str) -> tuple[Entry, ...]:
    """Every classification of one verb (LINK is both a conduit and a control-transfer sink)."""
    return tuple(e for e in ENTRIES if e.kind == kind and e.key == verb)
