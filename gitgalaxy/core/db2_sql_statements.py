# ==============================================================================
# GitGalaxy Core: embedded SQL statements -- which tables a program reads and
# writes (#3446, epic #3445)
#
# PURPOSE:
# `sql_table_data` (#3344) carries the DB2 DECLARE TABLE schemas, the SHAPE of a
# table. Nothing said which programs actually USE which table, or how, so the
# engine could not answer "which programs write ACCOUNT?". That program x table
# read/write matrix is where data-migration planning starts. This module reads
# every embedded SQL statement:
#
#     EXEC SQL <statement> END-EXEC        (COBOL)
#     EXEC SQL <statement> ;               (PL/I)
#
# and emits one row per (statement, table): the verb, the access the statement
# makes to the table, the cursor it declares or uses, its host variables, and
# (#3618) the statement text itself -- comments stripped, whitespace collapsed,
# literals kept -- so a generator can carry the program's own SQL.
# It rides out of `mainframe_boundary.extract_boundary` as `sql_statements` and
# lands in `sql_statement_data`.
#
# ACCESS:
#   read    SELECT ... FROM / JOIN, a subquery's FROM, DECLARE ... CURSOR FOR SELECT,
#           MERGE ... USING <table>, INSERT ... SELECT ... FROM <table>
#   insert  INSERT INTO <table>
#   update  UPDATE <table>
#   delete  DELETE FROM <table>
#   merge   MERGE INTO <table>
#   lock    LOCK TABLE <table>
# A statement that names no table (OPEN / FETCH / CLOSE <cursor>, COMMIT,
# ROLLBACK, CALL, SET, PREPARE, EXECUTE, CONNECT) still gets ONE row with
# table=None, so the cursor lifecycle and unit-of-work points are kept. The IR
# reader joins OPEN / FETCH to the cursor's DECLARE for the matrix
# (galaxy_ir.GalaxyIR.sql_table_access).
#
# NON-SCOPE:
#   - `EXEC SQL INCLUDE` (a copy: copy_deps) and `EXEC SQL DECLARE ... TABLE`
#     (#3344's schema) are not statements here. `WHENEVER` is a precompiler
#     directive, not a statement.
#   - Dynamic SQL: `PREPARE s FROM :WS-SQL` / `EXECUTE IMMEDIATE :v` build their
#     text at run time. The row is kept with table=None; the table cannot be
#     recovered from the repository.
#   - Same-file only. A statement written in a copybook is extracted when that
#     member is scanned, like every per-file channel.
#
# BOUNDED SCANNING: the statement end is found with str.find under a hard
# `_STMT_LIMIT`; inside the body, table names are read by fixed-shape regexes
# with no unbounded runs, and literals and `--` comments are blanked first.
# ==============================================================================
import re
from typing import Any, Optional

from gitgalaxy.core.db2_declare_table import (
    _QNAME,
    _blank_sequence_fields,
    _inside_literal,
    _qualified_name,
    _strip_sql_comments,
)

_EXEC_SQL = re.compile(r"(?<![A-Z0-9_@#$-])EXEC[ \t\r\n]{1,200}SQL(?![A-Z0-9_@#$-])", re.I)
_HAS_EXEC = re.compile(r"EXEC[ \t\r\n]{1,200}SQL", re.I)
# A statement longer than this is not read (an unterminated EXEC SQL must not
# swallow the rest of a program). Real DB2 statements in the corpora are < 4k.
_STMT_LIMIT = 32768
_END_EXEC = re.compile(r"(?<![A-Z0-9_@#$-])END-EXEC(?![A-Z0-9_@#$-])", re.I)

_WORD = re.compile(r"[ \t\r\n]*([A-Z][A-Z0-9_]*)", re.I)
_NOT_STATEMENTS = frozenset({"INCLUDE", "WHENEVER", "BEGIN", "END"})

# `FROM` / `JOIN` followed by a table (not a `(` subquery or a table function).
_FROM = re.compile(r"(?<![A-Z0-9_@#$])(?:FROM|JOIN)[ \t\r\n]{1,200}(?!\()(" + _QNAME + r")", re.I)
# The rest of a FROM list: `, t2 [AS] b` after the first table and its alias.
# Words that end a FROM-list entry rather than alias it.
_ALIAS_STOP = "|".join(
    (
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
    )
)
_S = r"[ \t\r\n]{1,200}"
_FROM_LIST_NEXT = re.compile(
    r"(?:" + _S + r"(?:AS" + _S + r")?(?!" + _ALIAS_STOP + r")[A-Z][A-Z0-9_]{0,127})?"
    r"[ \t\r\n]{0,200},[ \t\r\n]{0,200}(?!\()(" + _QNAME + r")",
    re.I,
)
_INSERT_INTO = re.compile(r"^INSERT[ \t\r\n]{1,200}INTO[ \t\r\n]{1,200}(" + _QNAME + r")", re.I)
_UPDATE = re.compile(r"^UPDATE[ \t\r\n]{1,200}(" + _QNAME + r")", re.I)
_DELETE = re.compile(r"^DELETE[ \t\r\n]{1,200}FROM[ \t\r\n]{1,200}(" + _QNAME + r")", re.I)
_MERGE = re.compile(r"^MERGE[ \t\r\n]{1,200}INTO[ \t\r\n]{1,200}(" + _QNAME + r")", re.I)
_MERGE_USING = re.compile(r"(?<![A-Z0-9_@#$])USING[ \t\r\n]{1,200}(?!\()(" + _QNAME + r")", re.I)
_LOCK = re.compile(r"^LOCK[ \t\r\n]{1,200}TABLE[ \t\r\n]{1,200}(" + _QNAME + r")", re.I)
_DECLARE_CURSOR = re.compile(
    r"^DECLARE[ \t\r\n]{1,200}([A-Z][A-Z0-9_-]{0,127})[ \t\r\n]{1,200}(?:[A-Z ]{0,60}?)CURSOR\b", re.I
)
# What may sit between OPEN/FETCH/CLOSE and the cursor name.
_FETCH_ORIENTATION = "|".join(
    (
        "NEXT",
        "PRIOR",
        "FIRST",
        "LAST",
        "CURRENT",
        "FROM",
        "ROWSET",
        "STARTING",
        "AT",
        "ABSOLUTE",
        "RELATIVE",
        r"[+-]?[0-9]{1,9}",
        r":[A-Z0-9_-]{1,128}",
    )
)
_CURSOR_VERB = re.compile(
    r"^(OPEN|FETCH|CLOSE)(?:" + _S + r"(?:" + _FETCH_ORIENTATION + r"))*" + _S + r"([A-Z][A-Z0-9_-]{0,127})",
    re.I,
)
_WHERE_CURRENT_OF = re.compile(
    r"(?<![A-Z0-9_@#$])WHERE[ \t\r\n]{1,200}CURRENT[ \t\r\n]{1,200}OF[ \t\r\n]{1,200}([A-Z][A-Z0-9_-]{0,127})", re.I
)
# A host variable: `:WS-NAME`, `:REC.FIELD`, an indicator `:X:IND` (two hits).
_HOST_NAME = r"[A-Z][A-Z0-9_-]{0,127}"
_HOST_VAR = re.compile(r"(?<![A-Z0-9_@#$-]):[ \t]{0,4}(" + _HOST_NAME + r"(?:\." + _HOST_NAME + r")?)", re.I)
_WS = re.compile(r"[ \t\r\n]+")
# SQL keywords that can follow FROM / JOIN in a position the table regex would
# otherwise read as a name (`FROM FINAL TABLE (...)`, `DELETE FROM` handled apart).
_NOT_TABLES = frozenset({"FINAL", "NEW", "OLD", "TABLE", "LATERAL", "UNNEST", "XMLTABLE", "SELECT"})


def _blank_literals(text: str) -> str:
    """Quoted SQL literals blanked (offsets kept), so `WHERE X = 'FROM T'` names nothing."""
    out, quote = [], None
    for ch in text:
        if ch == "\n":
            quote = None
            out.append(ch)
        elif quote:
            out.append(ch if ch == quote else " ")
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
            out.append(ch)
        else:
            out.append(ch)
    return "".join(out)


def _tables(body: str, verb: str) -> list[tuple[str, str]]:
    """(table, access) pairs a statement body touches, in first-seen order."""
    found: list[tuple[str, str]] = []

    def add(name: str, access: str) -> None:
        table = _qualified_name(name)
        if table.split(".")[-1] in _NOT_TABLES:
            return
        if (table, access) not in found:
            found.append((table, access))

    target = {"INSERT": _INSERT_INTO, "UPDATE": _UPDATE, "DELETE": _DELETE, "MERGE": _MERGE, "LOCK": _LOCK}.get(verb)
    target_span = None
    if target is not None:
        m = target.match(body)
        if m:
            add(
                m.group(1),
                {"INSERT": "insert", "UPDATE": "update", "DELETE": "delete", "MERGE": "merge", "LOCK": "lock"}[verb],
            )
            target_span = m.span(1)
    if verb == "MERGE":
        for m in _MERGE_USING.finditer(body):
            add(m.group(1), "read")
    if verb in ("FETCH", "OPEN", "CLOSE"):
        return found  # `FETCH ... FROM <cursor>`: FROM names the cursor, not a table
    for m in _FROM.finditer(body):
        if target_span and m.start(1) == target_span[0]:
            continue  # DELETE FROM <target> is the delete, not a read
        add(m.group(1), "read")
        pos = m.end()
        while True:
            nxt = _FROM_LIST_NEXT.match(body, pos)
            if not nxt:
                break
            add(nxt.group(1), "read")
            pos = nxt.end()
    return found


def extract_sql_statements(code_stream: str, dialect: str = "cobol") -> list[dict[str, Any]]:
    """Every embedded SQL statement in one COBOL/PL/I file, one row per table touched.

    A flat list in source order:

        {ordinal, verb, table, access, cursor, host_variables, line}

    `ordinal` numbers the statements (1-based), so the rows of one statement
    share it. `verb` is the statement's first keyword (`SELECT`, `INSERT`,
    `DECLARE CURSOR`, `FETCH`, `COMMIT`, ...). `table` is the qualified name as
    DB2 folds it, or None for a statement that names none. `cursor` is the
    cursor a DECLARE declares, or that OPEN / FETCH / CLOSE / `WHERE CURRENT OF`
    uses. `host_variables` is the distinct `:NAME`s in order, comma-joined, or
    None. `line` is the EXEC SQL line.
    """
    if not code_stream or not _HAS_EXEC.search(code_stream):
        return []
    text = _blank_sequence_fields(code_stream, dialect)
    newline_offsets = [i for i, ch in enumerate(text) if ch == "\n"]

    def _line_of(offset: int) -> int:
        lo, hi = 0, len(newline_offsets)
        while lo < hi:
            mid = (lo + hi) // 2
            if newline_offsets[mid] < offset:
                lo = mid + 1
            else:
                hi = mid
        return lo + 1

    out: list[dict[str, Any]] = []
    ordinal = 0
    pos = 0
    while True:
        m = _EXEC_SQL.search(text, pos)
        if not m:
            break
        pos = m.end()
        if _inside_literal(text, m.start()):
            continue
        window = text[m.end() : m.end() + _STMT_LIMIT]
        if dialect == "pli":
            end = window.find(";")
        else:
            e = _END_EXEC.search(window)
            end = e.start() if e else -1
        if end < 0:
            continue
        pos = m.end() + end
        raw = _strip_sql_comments(window[:end])
        body = _WS.sub(" ", _blank_literals(raw)).strip()
        w = _WORD.match(body)
        if not w:
            continue
        verb = w.group(1).upper()
        if verb in _NOT_STATEMENTS:
            continue
        cursor: Optional[str] = None
        if verb == "DECLARE":
            dc = _DECLARE_CURSOR.match(body)
            if not dc:
                continue  # DECLARE ... TABLE (#3344), ... STATEMENT, ... VARIABLE: not a statement here
            verb, cursor = "DECLARE CURSOR", dc.group(1).upper()
        elif verb in ("OPEN", "FETCH", "CLOSE"):
            cv = _CURSOR_VERB.match(body)
            cursor = cv.group(2).upper() if cv else None
        else:
            wco = _WHERE_CURRENT_OF.search(body)
            cursor = wco.group(1).upper() if wco else None
        host = list(dict.fromkeys(h.upper() for h in _HOST_VAR.findall(_blank_literals(raw))))
        statement = _WS.sub(" ", raw).strip()
        ordinal += 1
        line = _line_of(m.start())
        tables: list[tuple[Optional[str], Optional[str]]] = list(_tables(body, verb.split()[0])) or [(None, None)]
        for table, access in tables:
            out.append(
                {
                    "ordinal": ordinal,
                    "verb": verb,
                    "table": table,
                    "access": access,
                    "cursor": cursor,
                    "host_variables": ",".join(host) or None,
                    "line": line,
                    "statement": statement,
                }
            )
    return out
