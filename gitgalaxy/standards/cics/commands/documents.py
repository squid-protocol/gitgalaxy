# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#4270 / #4769: the document handler's DOCUMENT CREATE and DOCUMENT RETRIEVE (register X33), the two commands that hold
up all four HTTP-facing zECS programs (ZECS000, ZECS001, ZECS003: a DOCUMENT CREATE of a template, then a RETRIEVE of what
the template says).

IBM (EXEC CICS DOCUMENT CREATE, EXEC CICS DOCUMENT RETRIEVE): a document is a buffer the task builds and CICS names with a
16-byte DOCTOKEN. CREATE builds it from TEXT (copied unchanged), BINARY (unchanged) or a TEMPLATE (the name, 48 bytes, of a
DOCTEMPLATE definition) or from nothing; RETRIEVE copies it INTO a buffer. Conditions: CREATE LENGERR RESP2 1 (LENGTH negative),
NOTFND RESP2 3 (the TEMPLATE not found); RETRIEVE NOTFND RESP2 1 (the document was not created), LENGERR RESP2 1 (MAXLENGTH below
zero, LENGTH not returned) and 2 (the buffer too short: the document is truncated and LENGTH "is the exact length required to
return the whole document").

What the translator does NOT model is refused by name, and says why: FROM and FROMDOC (the retrieved-document format and its
embedded tags, which IBM does not lay out), SYMBOLLIST / LISTLENGTH / DELIMITER / UNESCAPED (the symbol table), DOCSIZE (the size
CICS counts, tags included, is not stated), HOSTCODEPAGE / CHARACTERSET / CLNTCODEPAGE (code-page conversion), a RETRIEVE without
DATAONLY (the tags CICS embeds are not laid out) and without MAXLENGTH, a CREATE of TEXT / BINARY without LENGTH (IBM states no
default). DOCUMENT INSERT / SET / DELETE stay refused whole: no corpus program uses them."""

from __future__ import annotations

from gitgalaxy.standards.cics.commands.shared import RESP_OPTIONS, ibm
from gitgalaxy.standards.cics.model import (
    Arg,
    Command,
    Fact,
    Outcome,
    Refusal,
    RuntimeRefusal,
    at_most_one,
    required,
    requires,
)

_TOKEN = Arg("area_out", width=16)

_CREATE_REFUSED = {
    "FROM": Refusal(
        "FROM takes a template or a RETRIEVEd document (whose embedded tags IBM does not lay out), and CICS runs the "
        "template language over it: not modelled",
        "X33",
    ),
    "FROMDOC": Refusal("copying a document (bookmark and conversion tags) is not modelled", "X33"),
    "SYMBOLLIST": Refusal("the document's symbol table is not modelled", "X33"),
    "LISTLENGTH": Refusal("the document's symbol table is not modelled", "X33"),
    "DELIMITER": Refusal("the document's symbol table is not modelled", "X33"),
    "UNESCAPED": Refusal("the document's symbol table is not modelled", "X33"),
    "DOCSIZE": Refusal("the size CICS counts for a document (embedded tags included) is not stated by IBM", "X33"),
    "HOSTCODEPAGE": Refusal("code-page conversion of a document is not modelled", "X33"),
}

DOCUMENT_CREATE = Command(
    key="DOCUMENT CREATE",
    ibm=ibm("EXEC CICS DOCUMENT CREATE", "summary-document-create"),
    status="modelled",
    register="X33",
    options={
        "DOCTOKEN": _TOKEN,
        "TEXT": Arg("area_in"),
        "BINARY": Arg("area_in"),
        "TEMPLATE": Arg("name", width=48),
        "LENGTH": Arg("value"),
        **RESP_OPTIONS,
    },
    refused=_CREATE_REFUSED,
    default_refusal=Refusal("only a document of TEXT, BINARY or a TEMPLATE (or empty) is modelled", "X33"),
    groups=(
        required("DOCTOKEN", msg="DOCUMENT CREATE without DOCTOKEN"),
        at_most_one(
            "TEXT", "BINARY", "TEMPLATE", msg="DOCUMENT CREATE: one source of the document (TEXT, BINARY or TEMPLATE)"
        ),
        requires(
            ("TEXT", "BINARY"),
            ("LENGTH",),
            msg="DOCUMENT CREATE TEXT / BINARY without LENGTH: IBM states no default length",
            both_ways=False,
        ),
        requires(
            ("LENGTH",),
            ("TEXT", "BINARY"),
            msg="DOCUMENT CREATE LENGTH without TEXT or BINARY: it is the length of that buffer",
        ),
    ),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("DOCTOKEN",)),
        Outcome("LENGERR", 1, "LENGTH is negative", raised_by=("LENGTH",)),
        Outcome("NOTFND", 3, "The TEMPLATE was not found or was misnamed", raised_by=("TEMPLATE",)),
    ),
    facts=(
        Fact(
            "doctemplates",
            java="withDoctemplates",
            env="GGCICS_DOCTEMPLATES",
            region_default=None,
            options=("TEMPLATE",),
        ),
    ),
    runtime_refusals=(
        RuntimeRefusal(
            "the installed document templates (name and text) are not stated for the task",
            "X33",
            java="the installed document templates are not stated (withDoctemplates)",
            c="DOCUMENT CREATE: the installed document templates are not stated for this task",
        ),
        RuntimeRefusal(
            "a template whose text holds symbols (&name;) or template commands (#set, #include, #echo): the template language is not modelled",
            "X33",
            java="DOCUMENT CREATE TEMPLATE text with symbols or template commands",
            c="DOCUMENT CREATE TEMPLATE text with symbols or template commands",
        ),
        RuntimeRefusal(
            "a LENGTH past the TEXT / BINARY area: CICS reads the storage that follows it, which GnuCOBOL lays out unlike IBM's compiler",
            "X33",
            java="DOCUMENT CREATE LENGTH",
            c="DOCUMENT CREATE LENGTH",
        ),
    ),
    state=("handle_table",),
)

DOCUMENT_RETRIEVE = Command(
    key="DOCUMENT RETRIEVE",
    ibm=ibm("EXEC CICS DOCUMENT RETRIEVE", "summary-document-retrieve"),
    status="modelled",
    register="X33",
    options={
        "DOCTOKEN": Arg("area_in", width=16),
        "INTO": Arg("area_out"),
        "LENGTH": Arg("area_out", width=4, binary=True),
        "MAXLENGTH": Arg("value"),
        "DATAONLY": Arg("flag"),
        **RESP_OPTIONS,
    },
    refused={
        "CHARACTERSET": Refusal("code-page conversion of a document is not modelled", "X33"),
        "CLNTCODEPAGE": Refusal("code-page conversion of a document is not modelled", "X33"),
    },
    default_refusal=Refusal("only DOCTOKEN, INTO, LENGTH, MAXLENGTH and DATAONLY are modelled", "X33"),
    groups=(
        required("DOCTOKEN", msg="DOCUMENT RETRIEVE without DOCTOKEN"),
        required("INTO", msg="DOCUMENT RETRIEVE without INTO"),
        required("MAXLENGTH", msg="DOCUMENT RETRIEVE without MAXLENGTH: IBM states no default"),
        required(
            "DATAONLY",
            msg="DOCUMENT RETRIEVE without DATAONLY: the tags CICS embeds in a retrieved document are not laid out by IBM",
        ),
    ),
    outcomes=(
        Outcome("NORMAL", 0, "", writes=("INTO", "LENGTH")),
        Outcome("NOTFND", 1, "The document was not created, or the name is incorrectly specified"),
        Outcome("LENGERR", 1, "MAXLENGTH is less than zero (LENGTH is not returned)", raised_by=("MAXLENGTH",)),
        Outcome(
            "LENGERR",
            2,
            "The receiving buffer is too short: the document is truncated and LENGTH is the length it needs",
            writes=("INTO", "LENGTH"),
        ),
    ),
    runtime_refusals=(
        RuntimeRefusal(
            "a document longer than INTO that MAXLENGTH lets through: CICS writes the storage that follows INTO, which GnuCOBOL lays out unlike IBM's compiler",
            "X33",
            java="DOCUMENT RETRIEVE MAXLENGTH beyond INTO",
            c="DOCUMENT RETRIEVE MAXLENGTH beyond INTO",
        ),
    ),
    state=("handle_table",),
)

COMMANDS = (DOCUMENT_CREATE, DOCUMENT_RETRIEVE)
