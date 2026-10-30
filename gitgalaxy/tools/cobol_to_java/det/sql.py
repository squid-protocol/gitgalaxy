"""EXEC SQL for a det port: each statement runs as the generated Db2 repository's method for it.

The boundary is the generator's, as for files and CICS: GitGalaxy generates, per Db2 table, a repository with one
method per embedded SQL statement (repository/db2/<Table>Repository.java), the SQL as written, its Javadoc naming
the statement's source line and each named parameter's host variable:

    /** EXEC SQL INSERT at app/.../cbl/COBTUPDT.cbl:137 (COBTUPDT, insert access).
     *  Parameters: inputRecDesc = :INPUT-REC-DESC, inputRecNumber = :INPUT-REC-NUMBER. ...
    public int insertL137Cobtupdt(Map<String, ?> params)

A statement is found by its program and line; its host variables' values are passed by those names, and what the
method returns is turned into the SQLCA (cobolrt/sql/DetSql: +100, -811, Db2's own SQLCODE) and, for SELECT INTO /
FETCH, into the host variables -- as Db2's precompiler declares them for COBOL (CHAR, VARCHAR, DECIMAL / binary).

#4269 -- the unit of work. COMMIT and ROLLBACK (WORK) end the Db2 unit of work the program runs in (DetSql.commit /
rollback): a batch step's is the runner's (one Db2 transaction for the step, DetSql.unitOfWork; the equivalence
harness gives it), committed at the step's normal end and backed out when it abends, as Db2 for z/OS does for a
DSN / CAF batch program (oracle_assumptions Q3). COMMIT closes the cursors not declared WITH HOLD, ROLLBACK every
cursor. In a CICS program the unit of work is the task's: COMMIT stays a reset of the SQLCA (each task's work is
committed with the task), ROLLBACK is refused -- Db2 for z/OS answers it -926 in CICS (SYNCPOINT ROLLBACK backs out).

SAVEPOINT, ROLLBACK TO SAVEPOINT and RELEASE SAVEPOINT run as written on the batch unit of work's connection
(DetSql.savepoint), Db2 answering them; in a CICS program they are refused.

#4269 -- WHENEVER {SQLERROR | NOT FOUND | SQLWARNING} {CONTINUE | GOTO label} (IBM Db2 for z/OS SQL Reference): in force
for the executable SQL statements after it in the program's text, until the next WHENEVER for the same condition. After
each such statement the port tests the SQLCA in IBM's order -- SQLCODE < 0, SQLCODE = +100, SQLWARN0 = 'W' or another
positive SQLCODE -- and goes to the label (the paragraph dispatcher's GOTO; a program with a WHENEVER GOTO is not
"structured"). CONTINUE, and a condition with no WHENEVER, test nothing.

Not modelled (a Hole naming it): dynamic SQL, host variable arrays, a statement the generator has no method for."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from gitgalaxy.tools.cobol_to_java.det import expr as E
from gitgalaxy.tools.cobol_to_java.det import layout as L


class SqlError(Exception):
    pass


@dataclass
class Method:
    repo: str  # the repository class
    name: str
    verb: str  # INSERT UPDATE DELETE SELECT CURSOR ...
    params: dict = field(default_factory=dict)  # host variable name -> parameter name
    opens: list = field(default_factory=list)  # a cursor's OPEN lines
    fetches: list = field(default_factory=list)
    closes: list = field(default_factory=list)


# (#4269: a program name may hold hyphens -- NEND-DAY -- as the generator writes it)
_DOC = re.compile(r"/\*\*\s*EXEC SQL ([A-Z ]+?) at ([^\s:]+):(\d+) \(([\w-]+),.*?\*/\s*public\s+[^(]*?\s(\w+)\(", re.S)


def repositories(java_root: Path | None) -> dict[tuple[str, int], Method]:
    """The generated Db2 repositories' methods, by (program, the statement's line)."""
    out: dict[tuple[str, int], Method] = {}
    if java_root is None:
        return out
    for f in sorted(java_root.rglob("repository/db2/*Repository.java")):
        text = f.read_text(encoding="utf-8")
        for m in _DOC.finditer(text):
            doc = m.group(0)
            params = {}
            pm = re.search(r"Parameters:\s*(.*?)\.\s*(?:\n|\*)", doc, re.S)
            if pm:
                for p, h in re.findall(r"(\w+)\s*=\s*:([A-Z0-9-]+)", pm.group(1)):
                    params[h.upper()] = p
            meth = Method(f.stem, m.group(5), m.group(1).strip().split()[0], params)
            if "CURSOR" in m.group(1):
                meth.verb = "CURSOR"
                for verb, line in re.findall(r"(FETCH|OPEN|CLOSE) at line (\d+)", doc):
                    {"OPEN": meth.opens, "FETCH": meth.fetches, "CLOSE": meth.closes}[verb].append(int(line))
                for ln in meth.opens + meth.fetches + meth.closes:
                    out[(m.group(4).upper(), ln)] = meth
            out[(m.group(4).upper(), int(m.group(3)))] = meth
    return out


_HOST = re.compile(r":\s*([A-Z0-9][A-Z0-9-]*(?:\s+(?:OF|IN)\s+[A-Z0-9][A-Z0-9-]*)?)"
                   r"(?:\s*(?:INDICATOR\s*)?:\s*([A-Z0-9][A-Z0-9-]*))?", re.I)  # fmt: skip


def _set_parts(sql: str) -> tuple[list[str], list[str]]:
    """SET's host variables and expressions, in order: `SET :A = e1, :B = e2` or `SET (:A, :B) = (e1, e2)`."""
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_db2_forge import _split_top

    m = re.fullmatch(r"SET\s*\(([^)]*)\)\s*=\s*\((.*)\)", sql.strip(), re.I | re.S)
    if m:
        targets, exprs = _split_top(m.group(1)), _split_top(m.group(2))
    else:
        targets, exprs = [], []
        for part in _split_top(sql.strip()[3:]):
            a = re.fullmatch(r"\s*(:[^=]+?)\s*=\s*(.+)", part, re.S)
            if not a:
                raise SqlError(f"EXEC SQL SET {part.strip()[:40]}")
            targets.append(a.group(1))
            exprs.append(a.group(2))
    if len(targets) != len(exprs):
        raise SqlError("EXEC SQL SET: as many host variables as values")
    return [t.strip() for t in targets], [e.strip() for e in exprs]


# #4269: the savepoint statements (Db2 for z/OS SQL Reference: SAVEPOINT, ROLLBACK ... TO SAVEPOINT, RELEASE SAVEPOINT)
_WHENEVER = re.compile(r"WHENEVER\s+(SQLERROR|NOT\s+FOUND|SQLWARNING)\s+(?:(CONTINUE)|GO\s*TO\s+:?([A-Z0-9_-]+))", re.I)
# #4269: the dynamic / connection verbs still refused, each with the form it stands for (register Q4)
_REFUSED_VERBS = {
    "PREPARE": "a PREPARE that is not FROM one INSERT ... VALUES string literal is not modelled",
    "EXECUTE": "an EXECUTE that is not of a name PREPAREd earlier from a literal is not modelled",
    "DESCRIBE": "DESCRIBE (an SQLDA of a prepared statement or table) is not modelled",
    "CONNECT": "CONNECT (a Db2 location switch) is not modelled; the port has one connection",
    "CALL": "EXEC SQL CALL (a stored procedure) is not modelled; the oracle has no procedure fixture",
    "SET": "a SET that does not assign a host variable (SET CURRENT ...) is not modelled",
}
_WHENEVER_ORDER = ("SQLERROR", "NOT FOUND", "SQLWARNING")
_SAVEPOINT = re.compile(r"SAVEPOINT\s.*|ROLLBACK(?:\s+WORK)?\s+TO\s+SAVEPOINT(?:\s+[A-Z0-9_]+)?|RELEASE(?:\s+TO)?\s+SAVEPOINT\s+"
                        r"[A-Z0-9_]+", re.S)  # fmt: skip
# #4269: EXECUTE IMMEDIATE 'statement text' (a string literal fixed in the source); an embedded quote is doubled
_IMMEDIATE = re.compile(r"EXECUTE\s+IMMEDIATE\s+'((?:[^']|'')*)'", re.I)
# #4269: PREPARE name FROM 'text' / EXECUTE name (no USING): the same literal-text path as EXECUTE IMMEDIATE
_PREPARE = re.compile(r"PREPARE\s+([A-Z0-9_-]+)\s+FROM\s+'((?:[^']|'')*)'", re.I)
# (#4269: ... USING :H1, :H2 binds the prepared text's parameter markers, one host variable each)
_EXECUTE = re.compile(r"EXECUTE\s+([A-Z0-9_-]+)(?:\s+USING\s+(.+))?", re.I)
_IMMEDIATE_INSERT = re.compile(r"INSERT\s+INTO\s.*\bVALUES\b.*", re.I | re.S)
_QUOTED = re.compile(r"'(?:[^']|'')*'")
# #4269: a scroll cursor's FETCH (IBM Db2 for z/OS SQL Reference, FETCH): [INSENSITIVE | SENSITIVE] [orientation] [FROM]
# cursor INTO ...; NEXT is what a plain FETCH means. ABSOLUTE / RELATIVE take an integer constant or a host variable.
_FETCH = re.compile(
    r"FETCH\s+(?:(INSENSITIVE|SENSITIVE)\s+)?"
    r"(?:(NEXT|PRIOR|FIRST|LAST|CURRENT|(?:ABSOLUTE|RELATIVE)\s+(?:[+-]?\d+|:[A-Z0-9_-]+))\s+)?"
    r"(?:FROM\s+)?([A-Z0-9_-]+)\s+INTO\s+(.*)",
    re.I | re.S,
)
# #4269: the orientations that are positions only (no row, no INTO): FETCH [INSENSITIVE] BEFORE | AFTER [FROM] cursor
_ORIENT_NO_ROW = re.compile(
    r"FETCH\s+(?:(INSENSITIVE|SENSITIVE)\s+)?(BEFORE|AFTER)\s+(?:FROM\s+)?([A-Z0-9_-]+)\s*", re.I
)
# DECLARE name [INSENSITIVE | SENSITIVE [STATIC | DYNAMIC] | ASENSITIVE] [NO] SCROLL CURSOR: the words between name and CURSOR
_DECLARE_CURSOR = re.compile(r"\bDECLARE\s+([A-Z0-9_-]+)\s+((?:[A-Z]+\s+){0,4}?)CURSOR\b(\s+WITH\s+HOLD\b)?", re.I)
# #4269: a multi-row (rowset) FETCH / INSERT: `FETCH ... ROWSET`, `FOR :N ROWS`
_ROWSET = re.compile(r"\bROWSET\b|\bFOR\s+(?::?[A-Z0-9_-]+)\s+ROWS?\b", re.I)
# #4269: FETCH [NEXT] ROWSET [FROM] cursor FOR n ROWS INTO :a1, :a2 (n an integer or a host variable; each host variable a
# table, one per column). The cursor was declared WITH ROWSET POSITIONING.
_ROWSET_FETCH = re.compile(
    r"FETCH\s+(?:(?:INSENSITIVE|SENSITIVE)\s+)?(?:NEXT\s+)?ROWSET\s+(?:FROM\s+)?([A-Z0-9_-]+)\s+"
    r"FOR\s+(\d+|:[A-Z0-9_-]+)\s+ROWS?\s+INTO\s+(.*)",
    re.I | re.S,
)
_ROWSET_DECL = re.compile(
    r"\bDECLARE\s+([A-Z0-9_-]+)\s+(?:[A-Z]+\s+){0,4}?CURSOR\s+(?:WITH\s+(?:HOLD|RETURN)\s+)*WITH\s+ROWSET\s+POSITIONING\b",
    re.I,
)
# #4269: INSERT ... VALUES (:A1, :A2) FOR n ROWS [ATOMIC] -- the host variables tables (n an integer or a host variable);
# NOT ATOMIC CONTINUE ON SQLEXCEPTION is not matched, so it stays refused
_INSERT_ROWS = re.compile(r"\bFOR\s+(\d+|:[A-Z0-9_-]+)\s+ROWS?(?:\s+ATOMIC)?\s*$", re.I)
_HOLD = re.compile(r"\bDECLARE\s+([A-Z0-9_-]+)\s+(?:[A-Z]+\s+){0,2}?CURSOR\s+WITH\s+HOLD\b", re.I)


# #4269: what a PREPARE runs: a statement Db2 answers SQLCODE 0 with no row touched (the SQLCA a PREPARE leaves)
PREPARE_NOOP = "VALUES 1"


def _markers(text: str) -> list[int]:
    """#4269: the offsets of the parameter markers (`?`) in a statement text, outside its string literals."""
    return [m.start() for m in re.finditer(r"\?", _QUOTED.sub(lambda q: " " * len(q.group()), text))]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class Sql:
    Error = SqlError

    def __init__(self, gen, program: str, java_root: Path | None, source: str = ""):
        self.g = gen
        self.program = program.upper()
        self.methods = repositories(java_root)
        self.repos: dict[str, str] = {}  # repository class -> its field
        # #4269: the cursors declared WITH HOLD (the program's text, its copybooks included): a COMMIT keeps them open
        self.hold = {m.group(1).upper() for m in _HOLD.finditer(source)}
        # #4269: the cursors declared SCROLL -> (sensitive, WITH HOLD); a FETCH orientation is for these only
        self.rowset = {m.group(1).upper() for m in _ROWSET_DECL.finditer(source)}
        self.scroll: dict[str, tuple[bool, bool]] = {}
        for m in _DECLARE_CURSOR.finditer(source):
            words = m.group(2).upper().split()
            if "SCROLL" in words and "NO" not in words:
                self.scroll[m.group(1).upper()] = (any(w in ("SENSITIVE", "DYNAMIC") for w in words), bool(m.group(3)))
        # #4269: (line, normalised text) of an executable statement -> its WHENEVER actions {condition: label}; None
        # when two statements share the key with different actions (a copybook line number that collides)
        self.whenever: dict[tuple[int, str], dict[str, str] | None] = {}
        # #4269: PREPARE name FROM 'literal' -> [(line, text)] of every such PREPARE of the name, source order
        self.prepared: dict[str, list[tuple[int, str]]] = {}

    def scan_whenever(self, stmts) -> None:
        """#4269: walk the program's EXEC statements in source order, WHENEVER scoping each executable EXEC SQL."""
        state: dict[str, str] = {}
        for s in stmts:
            m = re.match(r"(?is)\s*EXEC\s+SQL\b(.*?)\bEND-EXEC\b", s.text)
            if not m:
                continue
            sql = _norm(m.group(1))
            verb = sql.upper().split()[0] if sql else ""
            if verb == "WHENEVER":
                w = _WHENEVER.fullmatch(sql)
                if w:
                    cond = re.sub(r"\s+", " ", w.group(1).upper())
                    if w.group(2):
                        state.pop(cond, None)
                    else:
                        state[cond] = w.group(3).upper()
            elif verb not in ("INCLUDE", "DECLARE"):
                p = _PREPARE.fullmatch(sql)
                if p:
                    self.prepared.setdefault(p.group(1).upper(), []).append((s.line, p.group(2).replace("''", "'")))
                key = (s.line, sql.upper())
                if key in self.whenever and self.whenever[key] != state:
                    self.whenever[key] = None
                else:
                    self.whenever[key] = dict(state)

    # -- host variables ------------------------------------------------------------------------------------
    def _ref(self, name: str) -> E.Ref:
        parts = re.split(r"\s+(?:OF|IN)\s+", name.strip(), flags=re.I)
        return (
            E.Ref(parts[0].upper(), qualifiers=[q.upper() for q in parts[1:]])
            if len(parts) > 1
            else E.Ref(parts[0].upper())
        )

    def _item(self, ref: E.Ref) -> L.Item:
        return self.g.resolve(ref)

    @staticmethod
    def _varchar(it: L.Item) -> bool:
        kids = it.children
        return (len(kids) == 2 and all(k.level == 49 for k in kids) and kids[0].category == "NUMERIC"
                and kids[0].usage in ("BINARY", "COMP-5") and kids[1].category == "ALPHANUMERIC")  # fmt: skip

    def _elementary(self, it: L.Item) -> list[L.Item]:
        """A host variable, or a host structure's members (a VARCHAR pair is one)."""
        if it.occurs > 1:  # (a table is a column of a FETCH ROWSET only: _fetch_rowset)
            raise SqlError(f"host variable array {it.name}: a host-variable array is modelled only as a column of "
                           "FETCH ROWSET (register Q4)")  # fmt: skip
        if it.pic or self._varchar(it):
            return [it]
        out: list[L.Item] = []
        for k in it.children:
            if k.name != "FILLER":
                out += self._elementary(k)
        return out

    def _field(self, it: L.Item) -> str:
        return self.g.field_expr(E.Ref(it.name, qualifiers=[it.parent.name] if it.parent else []))

    def value_in(self, it: L.Item) -> str:
        if self._varchar(it):
            ln, tx = it.children
            return f"DetSql.varcharIn({self._field(ln)}, {self._field(tx)}, CS)"
        if it.category in ("ALPHANUMERIC", "ALPHABETIC"):
            return f"DetSql.charIn({self._field(it)}, CS)"
        if it.category == "NUMERIC":
            return f"DetSql.numIn({self._field(it)}, CS)"
        raise SqlError(f"host variable {it.name}: {it.category}")

    def _params(self, text: str, meth: Method, var: str, ind: str) -> list[str]:
        """The statement's input host variables into `var`, by the generator's parameter names."""
        out = [f"{ind}java.util.Map<String, Object> {var} = new java.util.HashMap<>();"]
        for m in _HOST.finditer(text):
            name = re.split(r"\s+(?:OF|IN)\s+", m.group(1), flags=re.I)[0].upper()
            param = meth.params.get(name)
            if param is None:
                raise SqlError(f"the generated method {meth.name} has no parameter for :{name}")
            items = self._elementary(self._item(self._ref(m.group(1))))
            if len(items) != 1:
                raise SqlError(f"a host structure as an input (:{name})")
            value = self.value_in(items[0])
            if m.group(2):
                value = f"DetSql.orNull({value}, {self.g.field_expr(self._ref(m.group(2)))}, CS)"
            out.append(f"{ind}{var}.put({self.g_str(param)}, {value});")
        return out

    @staticmethod
    def g_str(s: str) -> str:
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'

    def _into(self, text: str, row: str, ind: str) -> list[str]:
        """FETCH / SELECT INTO: the row's columns into the host variables, in order."""
        kinds, hosts, texts, inds = [], [], [], []
        for m in _HOST.finditer(text):
            items = self._elementary(self._item(self._ref(m.group(1))))
            if m.group(2) and len(items) > 1:
                raise SqlError(f"an indicator array for host structure :{m.group(1)}")
            for it in items:
                if self._varchar(it):
                    kinds.append("V")
                    hosts.append(self._field(it.children[0]))
                    texts.append(self._field(it.children[1]))
                elif it.category in ("ALPHANUMERIC", "ALPHABETIC", "NUMERIC"):
                    kinds.append("N" if it.category == "NUMERIC" else "X")
                    hosts.append(self._field(it))
                    texts.append("null")
                else:
                    raise SqlError(f"host variable {it.name}: {it.category}")
                inds.append(self.g.field_expr(self._ref(m.group(2))) if m.group(2) else "null")
        indicators = "null" if all(i == "null" for i in inds) else f"new Field[] {{{', '.join(inds)}}}"
        return [f"{ind}if ({row} != null) {{",
                f"{ind}    DetSql.into(SQLCA_AREA, {row}, {self.g_str(''.join(kinds))}, new Field[] {{{', '.join(hosts)}}}, "
                f"new Field[] {{{', '.join(texts)}}}, {indicators}, CS);",
                f"{ind}}}"]  # fmt: skip

    # -- statements --------------------------------------------------------------------------------------
    def command(self, text: str, line: int, ind: str) -> list[str]:
        ca = self.g.field_expr(E.Ref("SQLCA"))
        out = self._command(text, line, ind)
        if out and getattr(self.g.cics, "handle_abend", False):
            # #6271 (X73): a scenario's planned Db2 abend (AD2Z) at this statement went to this program's HANDLE ABEND
            # exit, or unwound past this level; checked before the WHENEVER tests, as the stub's GGCSQLAB is
            ex = self.g.tmpname("exit")
            out += [f'{ind}task.planned("SQL", {self.g_str(f"{self.program}:{line}")});',
                    f"{ind}String {ex} = task.abendExit();",
                    f"{ind}if ({ex} != null) {self.g.jump(f'paragraph({ex})')}",
                    f"{ind}if (task.ended()) throw abended();"]  # fmt: skip
        if out:
            out += self._whenever_tests(text, line, ind)
        return [ln.replace("SQLCA_AREA", ca) for ln in out]

    def _whenever_tests(self, text: str, line: int, ind: str) -> list[str]:
        """#4269: the SQLCA tests of the WHENEVER actions in force at this statement, in IBM's order."""
        body = re.match(r"(?is)\s*EXEC\s+SQL\b(.*?)\bEND-EXEC\b", text)
        key = (line, _norm(body.group(1)).upper() if body else "")
        if key not in self.whenever:
            return []
        acts = self.whenever[key]
        if acts is None:
            raise SqlError("WHENEVER: the statement's line number is shared with a statement under another WHENEVER")
        # (inline, not a DetSql method: a runtime edit would move every Db2 port. SQLCODE is COMP-5, native little-
        # endian, at offset 12 of the SQLCA; SQLWARN0 is the byte at 120, written in the program's charset)
        code = "java.nio.ByteBuffer.wrap(SQLCA_AREA.storage().bytes, SQLCA_AREA.offset() + 12, 4).order(java.nio.ByteOrder.LITTLE_ENDIAN).getInt()"  # fmt: skip
        warn0 = 'SQLCA_AREA.storage().bytes[SQLCA_AREA.offset() + 120] == "W".getBytes(CS)[0]'
        tests = {
            "SQLERROR": f"{code} < 0",
            "NOT FOUND": f"{code} == 100",
            "SQLWARNING": f"{warn0} || ({code} > 0 && {code} != 100)",
        }
        out, first = [], True
        for cond in _WHENEVER_ORDER:
            label = acts.get(cond)
            if label is None:
                continue
            idx = self.g.para_index.get(label)
            if idx is None:
                raise SqlError(f"WHENEVER {cond} GO TO {label}: no such paragraph")
            out.append(f"{ind}{'' if first else 'else '}if ({tests[cond]}) {self.g.jump(str(idx))}")
            first = False
        return out

    def _command(self, text: str, line: int, ind: str) -> list[str]:
        body = re.match(r"(?is)\s*EXEC\s+SQL\b(.*?)\bEND-EXEC\b", text)
        if not body:
            raise SqlError("EXEC SQL without END-EXEC")
        sql = _norm(body.group(1))
        u = sql.upper()
        verb = u.split()[0] if u else ""
        if verb in ("INCLUDE", "DECLARE"):
            return []
        assigns = verb == "SET" and re.match(r"SET\s*\(?\s*:", sql, re.I)  # SET :H = expr (not SET CURRENT ...)
        if verb == "WHENEVER":
            if not _WHENEVER.fullmatch(sql):
                raise SqlError(f"EXEC SQL {u[:50]}")  # WHENEVER with a form not modelled
            return []
        if verb == "EXECUTE" and re.match(r"EXECUTE\s+IMMEDIATE\b", u):
            return self._execute_immediate(sql, line, ind)
        if verb == "PREPARE" and _PREPARE.fullmatch(sql):
            return self._prepare(sql, line, ind)
        if verb == "EXECUTE" and _EXECUTE.fullmatch(sql):
            return self._execute_prepared(sql, line, ind)
        if verb in _REFUSED_VERBS and not assigns:
            raise SqlError(f"EXEC SQL {verb}: {_REFUSED_VERBS[verb]} (register Q4; no burned program uses it)")
        if _SAVEPOINT.fullmatch(u):
            return self._savepoint(sql, u, line, ind)
        if verb in ("COMMIT", "ROLLBACK"):
            return self._end_unit_of_work(verb, u, line, ind)
        self._refuse_scroll_and_rowset(verb, sql)
        if verb == "FETCH" and (bare := _ORIENT_NO_ROW.fullmatch(_QUOTED.sub("''", sql))):
            return self._fetch_position(bare, line, ind)
        pos = re.search(r"\bWHERE\s+CURRENT\s+OF\s+([A-Z0-9_-]+)", u)
        meth = self.methods.get((self.program, line))
        if meth is None:
            raise SqlError(f"no generated Db2 repository method for the statement at line {line}")
        at = self.g_str(f"{self.program}:{line}")  # #4173: the key a SQL fault names (ggsql.c's program and line)
        repo_field = meth.repo[0].lower() + meth.repo[1:]
        self.repos[meth.repo] = repo_field
        call = f"{repo_field}.{meth.name}"
        n = self.g.tmpname("sqlParams")
        if pos:  # positioned: the generated method takes the current row's id (GG_RID) as :ggRid
            if verb not in ("UPDATE", "DELETE") or "GG-RID" not in meth.params:
                raise SqlError("a positioned statement the generated method does not position")
            return [*self._params(sql[: pos.start()], meth, n, ind),
                    f"{ind}DetSql.updateCurrent(SQLCA_AREA, {at}, {self.g_str(pos.group(1))}, rid -> {{ "
                    f"{n}.put({self.g_str(meth.params['GG-RID'])}, rid); return {call}({n}); }}, CS);"]  # fmt: skip
        if verb == "INSERT" and (rows := _INSERT_ROWS.search(sql)):
            return self._insert_rows(sql, rows, meth, at, ind)
        if verb in ("INSERT", "UPDATE", "DELETE"):
            searched = verb != "INSERT"
            return [
                *self._params(sql, meth, n, ind),
                f"{ind}DetSql.update(SQLCA_AREA, {at}, () -> {call}({n}), {'true' if searched else 'false'}, CS);",
            ]
        if verb in ("SELECT", "WITH") and meth.verb != "CURSOR":
            m = re.match(r"(.*?)\bINTO\b(.*?)\bFROM\b(.*)", sql, re.I | re.S)
            if not m:
                raise SqlError("SELECT without INTO")
            row = self.g.tmpname("sqlRow")
            return [*self._params(m.group(1) + " FROM " + m.group(3), meth, n, ind),
                    f"{ind}java.util.Map<String, Object> {row} = DetSql.selectOne(SQLCA_AREA, {at}, () -> {call}({n}), CS);",
                    *self._into(m.group(2), row, ind)]  # fmt: skip
        if assigns:  # the generated method runs VALUES (the expressions); its row goes into the host variables
            targets, exprs = _set_parts(sql)
            row = self.g.tmpname("sqlRow")
            return [*self._params(", ".join(exprs), meth, n, ind),
                    f"{ind}java.util.Map<String, Object> {row} = DetSql.selectOne(SQLCA_AREA, {at}, () -> {call}({n}), CS);",
                    *self._into(", ".join(targets), row, ind)]  # fmt: skip
        if verb == "OPEN" and meth.verb == "CURSOR":
            cursor = u.split()[1]
            hold = ", true" if cursor in self.hold else ""  # #4269: WITH HOLD -- a COMMIT keeps it open
            return [
                *self._params(self._cursor_sql(meth), meth, n, ind),
                f"{ind}DetSql.open(SQLCA_AREA, {at}, {self.g_str(cursor)}{hold}, () -> {call}({n}), CS);",
            ]
        if verb == "FETCH" and meth.verb == "CURSOR" and (rowset := _ROWSET_FETCH.fullmatch(sql)):
            return self._fetch_rowset(rowset, at, ind)
        if verb == "FETCH" and meth.verb == "CURSOR":
            m = _FETCH.fullmatch(sql)
            if not m:
                raise SqlError(f"EXEC SQL {u[:50]}")
            cursor = m.group(3).upper()
            orient = re.sub(r"\s+", " ", (m.group(2) or "NEXT").upper()).split(" ")
            row = self.g.tmpname("sqlRow")
            if orient[0] == "NEXT" and not m.group(1):
                call = f"DetSql.fetch(SQLCA_AREA, {at}, {self.g_str(cursor)}, CS)"
            else:
                call = self._fetch_scroll(cursor, orient, at)
            return [f"{ind}java.util.Map<String, Object> {row} = {call};", *self._into(m.group(4), row, ind)]
        if verb == "CLOSE" and meth.verb == "CURSOR":
            return [f"{ind}DetSql.close(SQLCA_AREA, {at}, {self.g_str(u.split()[1])}, CS);"]
        raise SqlError(f"EXEC SQL {verb}")

    def _elems(self, it: L.Item, cap: int) -> str:
        """The first `cap` elements of a host-variable table, as a Java Field array."""
        quals = [it.parent.name] if it.parent else []
        refs = (E.Ref(it.name, qualifiers=quals, subscripts=[E.Lit(Decimal(k))]) for k in range(1, cap + 1))
        return "{" + ", ".join(self.g.field_expr(r) for r in refs) + "}"

    def _table(self, it: L.Item, what: str) -> L.Item:
        """A host variable that is an elementary table (PIC item with OCCURS), the host variable array of a column."""
        if not it.pic or it.occurs < 2 or self._varchar(it) or it.category not in ("ALPHANUMERIC", "NUMERIC"):
            raise SqlError(f"{what}: :{it.name} is not an elementary table (PIC item with OCCURS), "
                           "the host variable array of a column")  # fmt: skip
        return it

    def _rows_count(self, count: str, cap: int, what: str) -> str:
        """FOR n ROWS' n as a Java long: an integer within the tables, or a numeric host variable."""
        if count.startswith(":"):
            items = self._elementary(self._item(self._ref(count[1:])))
            if len(items) != 1 or items[0].category != "NUMERIC":
                raise SqlError(f"{what}: {count} is not a numeric host variable")
            return f"{self.value_in(items[0])}.longValue()"
        if int(count) > cap:
            raise SqlError(f"{what}: FOR {count} ROWS exceeds the host variable tables ({cap})")
        return f"{int(count)}L"

    def _insert_rows(self, sql: str, m: re.Match, meth: Method, at: str, ind: str) -> list[str]:
        """#4269 (register Q4): INSERT ... VALUES (:A1 [:I1], :A2 ...) FOR n ROWS [ATOMIC] -- each host variable a table,
        one per column. The generated method is the single-row INSERT; DetSql.insertRows runs it for elements 1..n and
        sets SQLERRD(3) to the rows inserted. ATOMIC (the default) is modelled with an internal savepoint: a failing row
        undoes the whole statement, so SQLERRD(3) is 0 and the SQLCODE is that row's."""
        what = "EXEC SQL INSERT ... FOR n ROWS"
        names: list[str] = []
        kinds = ""
        tables: list[L.Item] = []
        inds: list[L.Item | None] = []
        for h in _HOST.finditer(sql[: m.start()]):
            name = re.split(r"\s+(?:OF|IN)\s+", h.group(1), flags=re.I)[0].upper()
            param = meth.params.get(name)
            if param is None:
                raise SqlError(f"the generated method {meth.name} has no parameter for :{name}")
            it = self._table(self._item(self._ref(h.group(1))), what)
            names.append(self.g_str(param))
            tables.append(it)
            kinds += "N" if it.category == "NUMERIC" else "X"
            if h.group(2):
                ii = self._item(self._ref(h.group(2)))
                if ii.occurs != it.occurs:
                    raise SqlError(f"{what}: the indicator array :{h.group(2)} is not a table of {it.occurs} like "
                                   f":{it.name}")  # fmt: skip
                inds.append(ii)
            else:
                inds.append(None)
        if not tables:
            raise SqlError(f"{what}: no host variable table")
        cap = min(t.occurs for t in tables)
        n = self._rows_count(m.group(1), cap, what)
        hosts = ", ".join(self._elems(t, cap) for t in tables)
        ids = "null" if all(i is None for i in inds) else ", ".join(self._elems(i, cap) if i else "null" for i in inds)
        indicators = "null" if ids == "null" else f"new Field[][] {{{ids}}}"
        repo_field = meth.repo[0].lower() + meth.repo[1:]
        return [f"{ind}DetSql.insertRows(SQLCA_AREA, {at}, {n}, {cap}, {self.g_str(kinds)}, new String[] {{{', '.join(names)}}}, "
                f"new Field[][] {{{hosts}}}, {indicators}, p -> {repo_field}.{meth.name}(p), CS);"]  # fmt: skip

    def _fetch_rowset(self, m: re.Match, at: str, ind: str) -> list[str]:
        """#4269 (register Q4): FETCH [NEXT] ROWSET FROM cursor FOR n ROWS INTO :A1, :A2 -- each host variable an
        elementary table (OCCURS) holding one column's rows. DetSql.fetchRowset reads up to n rows and sets SQLERRD(3);
        DetSql.intoRows moves row j into element j of every table."""
        cursor = m.group(1).upper()
        tables: list[L.Item] = []
        kinds = ""
        inds: list[L.Item | None] = []
        for h in _HOST.finditer(m.group(3)):
            it = self._item(self._ref(h.group(1)))
            if not it.pic or it.occurs < 2 or self._varchar(it) or it.category not in ("ALPHANUMERIC", "NUMERIC"):
                raise SqlError(f"EXEC SQL FETCH ROWSET {cursor}: :{h.group(1)} is not an elementary table "
                               "(PIC item with OCCURS), the host variable array of a column")  # fmt: skip
            tables.append(it)
            kinds += "N" if it.category == "NUMERIC" else "X"
            if h.group(2):
                ii = self._item(self._ref(h.group(2)))
                if ii.occurs != it.occurs:
                    raise SqlError(f"EXEC SQL FETCH ROWSET {cursor}: the indicator array :{h.group(2)} is not a table "
                                   f"of {it.occurs} like :{h.group(1)}")  # fmt: skip
                inds.append(ii)
            else:
                inds.append(None)
        if not tables:
            raise SqlError(f"EXEC SQL FETCH ROWSET {cursor}: no host variable table")
        cap = min(t.occurs for t in tables)

        count = m.group(2)
        if count.startswith(":"):
            items = self._elementary(self._item(self._ref(count[1:])))
            if len(items) != 1 or items[0].category != "NUMERIC":
                raise SqlError(f"EXEC SQL FETCH ROWSET {cursor}: {count} is not a numeric host variable")
            n = f"{self.value_in(items[0])}.longValue()"
        else:
            n = f"{int(count)}L"
            if int(count) > cap:
                raise SqlError(
                    f"EXEC SQL FETCH ROWSET {cursor}: FOR {count} ROWS exceeds the host variable tables ({cap})"
                )
        row = self.g.tmpname("sqlRows")
        hosts = ", ".join(self._elems(t, cap) for t in tables)
        ids = "null" if all(i is None for i in inds) else ", ".join(self._elems(i, cap) if i else "null" for i in inds)
        indicators = "null" if ids == "null" else f"new Field[][] {{{ids}}}"
        read = (f"{ind}java.util.List<java.util.Map<String, Object>> {row} = DetSql.fetchRowset(SQLCA_AREA, {at}, "
                f"{self.g_str(cursor)}, {n}, {cap}, CS);")  # fmt: skip
        into = f"{ind}DetSql.intoRows(SQLCA_AREA, {row}, {self.g_str(kinds)}, new Field[][] {{{hosts}}}, {indicators}, CS);"
        return [read, into]

    def _fetch_scroll(self, cursor: str, orient: list[str], at: str) -> str:
        """#4269 (register Q4): FETCH [INSENSITIVE] PRIOR | FIRST | LAST | CURRENT | ABSOLUTE n | RELATIVE n of a cursor
        declared SCROLL (`_refuse_scroll_and_rowset` has vetted it): DetSql.fetchScroll moves the position over the rows
        OPEN read. n is an integer constant or a numeric host variable."""
        n = "0"
        if len(orient) > 1:
            if orient[1].startswith(":"):
                items = self._elementary(self._item(self._ref(orient[1][1:])))
                if len(items) != 1 or items[0].category != "NUMERIC":
                    raise SqlError(f"EXEC SQL FETCH {orient[0]} {cursor}: {orient[1]} is not a numeric host variable")
                n = f"{self.value_in(items[0])}.longValue()"
            else:
                n = f"{int(orient[1])}L"
        return f"DetSql.fetchScroll(SQLCA_AREA, {at}, {self.g_str(cursor)}, {self.g_str(orient[0])}, {n}, CS)"

    def _fetch_position(self, m: re.Match[str], line: int, ind: str) -> list[str]:
        """#4269 (register Q4): FETCH [INSENSITIVE] BEFORE | AFTER [FROM] cursor of a SCROLL cursor
        (`_refuse_scroll_and_rowset` has vetted it): DetSql.positionScroll parks the cursor before its first row or
        after its last. SQLCODE 0, no host variable touched, no repository method (no row is read)."""
        at = self.g_str(f"{self.program}:{line}")
        cursor = self.g_str(m.group(3).upper())
        where = self.g_str(m.group(2).upper())
        return [f"{ind}DetSql.positionScroll(SQLCA_AREA, {at}, {cursor}, {where}, CS);"]

    def _refuse_scroll_and_rowset(self, verb: str, sql: str) -> None:
        """#4269 (register Q4): a multi-row FETCH / INSERT, FETCH BEFORE / AFTER (a position, no row), an orientation on a
        cursor not declared SCROLL, a SENSITIVE or DYNAMIC scroll cursor (the port's rows are a copy made at OPEN) and a
        scroll cursor WITH HOLD (its position after a COMMIT) stop by name."""
        bare = _QUOTED.sub("''", sql)
        rowset = _ROWSET_FETCH.fullmatch(bare) if verb == "FETCH" else None
        if rowset:  # taken: _fetch_rowset checks the host variables
            cursor = rowset.group(1).upper()
            if cursor not in self.rowset:
                raise SqlError(f"EXEC SQL FETCH ROWSET {cursor}: the cursor is not declared WITH ROWSET POSITIONING"
                               " (register Q4)")  # fmt: skip
            if cursor in self.scroll and self.scroll[cursor][0]:
                raise SqlError(
                    f"EXEC SQL FETCH ROWSET {cursor}: a SENSITIVE or DYNAMIC cursor is not modelled (register Q4)"
                )
            return
        if verb == "INSERT" and _INSERT_ROWS.search(bare):  # taken: _insert_rows checks the host variables
            return
        if verb in ("FETCH", "INSERT") and _ROWSET.search(bare):
            what = ("FETCH ... ROWSET with STARTING AT, an orientation or no FOR n ROWS" if verb == "FETCH"
                    else "INSERT ... NOT ATOMIC CONTINUE ON SQLEXCEPTION or a FOR n ROWS not at the end")  # fmt: skip
            msg = f"EXEC SQL {verb}: a multi-row {what} is not modelled; only FETCH [NEXT] ROWSET FROM cursor "
            msg += "FOR n ROWS INTO host-variable tables and INSERT ... VALUES (tables) FOR n ROWS [ATOMIC] are "
            raise SqlError(msg + "(register Q4; no burned program uses it)")
        if verb != "FETCH":
            return
        o = _ORIENT_NO_ROW.fullmatch(bare)
        if o:  # FETCH BEFORE | AFTER cursor: a position, no row (the checks below are the scroll cursor's)
            cursor, orient = o.group(3).upper(), o.group(2).upper()
            what = f"EXEC SQL FETCH {orient} {cursor}"
            if cursor not in self.scroll:
                raise SqlError(f"{what}: a FETCH that only positions the cursor needs a cursor declared SCROLL "
                               "(register Q4)")  # fmt: skip
            if self.scroll[cursor][0] or (o.group(1) or "").upper() == "SENSITIVE":
                raise SqlError(f"{what}: a SENSITIVE or DYNAMIC scroll cursor sees later changes; only an INSENSITIVE or "
                               "ASENSITIVE one, read once at OPEN, is modelled (register Q4)")  # fmt: skip
            if self.scroll[cursor][1]:
                raise SqlError(f"{what}: a scroll cursor WITH HOLD (its position after COMMIT) is not modelled "
                               "(register Q4)")  # fmt: skip
            return
        if re.match(r"FETCH\s+(?:(?:INSENSITIVE|SENSITIVE)\s+)?(?:BEFORE|AFTER)\b", bare, re.I):
            raise SqlError("EXEC SQL FETCH BEFORE / AFTER: takes a cursor and no INTO, no row is read (register Q4)")
        m = _FETCH.fullmatch(bare)
        if not m:
            return
        cursor = m.group(3).upper()
        orient = (m.group(2) or "NEXT").upper()
        what = f"EXEC SQL FETCH {orient} {cursor}"
        if cursor in self.scroll and (self.scroll[cursor][0] or (m.group(1) or "").upper() == "SENSITIVE"):
            raise SqlError(f"{what}: a SENSITIVE or DYNAMIC scroll cursor sees later changes; only an INSENSITIVE or "
                           "ASENSITIVE one, read once at OPEN, is modelled (register Q4)")  # fmt: skip
        if orient == "NEXT" and not m.group(1):
            return
        if cursor not in self.scroll:
            raise SqlError(f"{what}: the cursor is not declared SCROLL (register Q4)")
        if self.scroll[cursor][1]:
            raise SqlError(
                f"{what}: a scroll cursor WITH HOLD (its position after COMMIT) is not modelled (register Q4)"
            )

    def _end_unit_of_work(self, verb: str, u: str, line: int, ind: str) -> list[str]:
        """#4269: COMMIT / ROLLBACK [WORK] (IBM Db2 for z/OS SQL Reference, COMMIT and ROLLBACK statements)."""
        if not re.fullmatch(rf"{verb}(\s+WORK)?", u):
            raise SqlError(f"EXEC SQL {u[:50]}")  # COMMIT / ROLLBACK with another option
        if self.g.cics is not None:
            if verb == "ROLLBACK":  # Db2 for z/OS: -926, SQLSTATE 2D521 -- ROLLBACK not valid in CICS
                raise SqlError("ROLLBACK in a CICS program: Db2 for z/OS answers -926 (the task's unit of work is "
                               "CICS's: SYNCPOINT ROLLBACK)")  # fmt: skip
            return [f"{ind}DetSql.reset(SQLCA_AREA, CS);  // the task's unit of work commits with the task"]
        at = self.g_str(f"{self.program}:{line}")
        return [f"{ind}DetSql.{verb.lower()}(SQLCA_AREA, {at}, CS);"]

    def _execute_immediate(self, sql: str, line: int, ind: str) -> list[str]:
        """#4269: EXECUTE IMMEDIATE 'INSERT ... VALUES ...' (IBM Db2 for z/OS SQL Reference, EXECUTE IMMEDIATE): the
        literal's text runs as written on the unit of work's connection, Db2 answering (DetSql.savepoint's path). Only
        what that path answers faithfully is taken: an INSERT of VALUES. A searched UPDATE / DELETE / MERGE that changes
        no row is +100 and an INSERT ... SELECT of no row too, which needs the row count the connection does not give
        back (a later slice), so those are refused with the rest."""
        m = _IMMEDIATE.fullmatch(sql)
        if not m:
            raise SqlError(f"EXEC SQL {sql[:50]}: only a string literal as the statement text is modelled")
        text = m.group(1).replace("''", "'")
        if self.g.cics is not None:
            raise SqlError("EXEC SQL EXECUTE IMMEDIATE in a CICS program: the task's unit of work is not modelled "
                           "for it (a later slice)")  # fmt: skip
        if not _IMMEDIATE_INSERT.fullmatch(text.strip()) or re.search(r"\bSELECT\b", text, re.I) or _markers(text):
            raise SqlError("EXEC SQL EXECUTE IMMEDIATE: only INSERT ... VALUES (no parameter marker) is modelled")
        at = self.g_str(f"{self.program}:{line}")
        return [f"{ind}DetSql.savepoint(SQLCA_AREA, {at}, {self.g_str(text.strip())}, CS);"]

    def _literal_text(self, text: str, what: str) -> str:
        """#4269: the dynamic statement text this slice runs: an INSERT ... VALUES, no CICS (parameter markers are
        bound by an EXECUTE ... USING; an unbound one is Db2's -313 and refused at the EXECUTE)."""
        if self.g.cics is not None:
            raise SqlError(f"EXEC SQL {what} in a CICS program: the task's unit of work is not modelled for it "
                           "(a later slice)")  # fmt: skip
        if not _IMMEDIATE_INSERT.fullmatch(text.strip()) or re.search(r"\bSELECT\b", text, re.I):
            why = f"EXEC SQL {what}: only "
            why += "INSERT ... VALUES is modelled"
            raise SqlError(why)
        return text.strip()

    def _prepare(self, sql: str, line: int, ind: str) -> list[str]:
        """#4269: PREPARE name FROM 'INSERT ... VALUES ...' (IBM Db2 for z/OS SQL Reference, PREPARE). The text is
        kept for the EXECUTE; the statement itself leaves the SQLCA at SQLCODE 0 and touches no row. Assumption: Db2's
        -104 for text it cannot parse lands at the EXECUTE here, not at the PREPARE. A name PREPAREd with two
        different literals is refused (which text an EXECUTE runs is control flow). Parameter markers are allowed: the
        EXECUTE ... USING binds them."""
        m = _PREPARE.fullmatch(sql)
        if m is None:
            raise SqlError(f"EXEC SQL {sql[:50]}")
        name = m.group(1).upper()
        self._literal_text(m.group(2).replace("''", "'"), "PREPARE")
        if len({t for _, t in self.prepared.get(name, [])}) > 1:
            raise SqlError(f"EXEC SQL PREPARE {name}: prepared from more than one literal text")
        at = self.g_str(f"{self.program}:{line}")
        return [f"{ind}DetSql.savepoint(SQLCA_AREA, {at}, {self.g_str(PREPARE_NOOP)}, CS);"]

    def _execute_prepared(self, sql: str, line: int, ind: str) -> list[str]:
        """#4269: EXECUTE name [USING :H, ...] of a name PREPAREd earlier in the source from a literal: that text runs as
        EXECUTE IMMEDIATE's does. An EXECUTE reached at run time before its PREPARE (-518) is not modelled; one placed
        before every PREPARE of the name in the source is refused. USING binds the text's parameter markers, one scalar
        host variable (with an optional indicator) each, by value at the EXECUTE: the port writes the value into the
        text as a literal (a character value quoted, an indicator below zero NULL, a number as its digits) where Db2
        binds it. Assumption: that is the same row for an INSERT ... VALUES. Refused by name: USING DESCRIPTOR, a
        host structure or array, and a marker count that is not the host-variable count (Db2 answers -313)."""
        m = _EXECUTE.fullmatch(sql)
        if m is None:
            raise SqlError(f"EXEC SQL {sql[:50]}")
        name = m.group(1).upper()
        preps = self.prepared.get(name, [])
        if not preps or min(ln for ln, _ in preps) >= line:
            raise SqlError(f"EXEC SQL EXECUTE {name}: no earlier PREPARE {name} FROM a string literal")
        texts = {t for _, t in preps}
        if len(texts) > 1:
            raise SqlError(f"EXEC SQL EXECUTE {name}: prepared from more than one literal text")
        text = self._literal_text(next(iter(texts)), "EXECUTE")
        at = self.g_str(f"{self.program}:{line}")
        marks = _markers(text)
        using = m.group(2) or ""
        hosts = list(_HOST.finditer(using))
        if re.sub(r"[\s,]", "", _HOST.sub("", using)) or (using and not hosts):
            raise SqlError(f"EXEC SQL EXECUTE {name} USING {using[:30]}: only host variables are modelled")
        if len(hosts) != len(marks):
            raise SqlError(f"EXEC SQL EXECUTE {name}: {len(marks)} parameter markers, {len(hosts)} USING host "
                           "variables (Db2 answers -313)")  # fmt: skip
        if not marks:
            return [f"{ind}DetSql.savepoint(SQLCA_AREA, {at}, {self.g_str(text)}, CS);"]
        out, parts, last = [], [], 0
        for h, pos in zip(hosts, marks, strict=True):
            items = self._elementary(self._item(self._ref(h.group(1))))
            if len(items) != 1:
                raise SqlError(f"a host structure in EXECUTE {name} USING (:{h.group(1)})")
            value = self.value_in(items[0])
            if h.group(2):
                value = f"DetSql.orNull({value}, {self.g.field_expr(self._ref(h.group(2)))}, CS)"
            v = self.g.tmpname("sqlArg")
            out.append(f"{ind}Object {v} = {value};")
            lit = f'({v} == null ? "NULL" : {v} instanceof String ? "\'" + ((String) {v}).replace("\'", "\'\'") + '
            lit += f'"\'" : ((java.math.BigDecimal) {v}).toPlainString())'
            parts += [self.g_str(text[last:pos]), lit]
            last = pos + 1
        parts.append(self.g_str(text[last:]))
        return [*out, f"{ind}DetSql.savepoint(SQLCA_AREA, {at}, {' + '.join(parts)}, CS);"]

    def _savepoint(self, sql: str, u: str, line: int, ind: str) -> list[str]:
        """#4269: SAVEPOINT, ROLLBACK [WORK] TO SAVEPOINT, RELEASE SAVEPOINT (IBM Db2 for z/OS SQL Reference): run as
        written on the unit of work's connection, Db2 answering (-880: no such savepoint, -881: UNIQUE reused)."""
        if self.g.cics is not None:
            raise SqlError(f"EXEC SQL {u.split()[0]} SAVEPOINT in a CICS program: the task's unit of work is not "
                           "modelled for it (a later slice)")  # fmt: skip
        if ":" in sql:
            raise SqlError(f"EXEC SQL {u[:50]}: a host variable in a savepoint statement")
        at = self.g_str(f"{self.program}:{line}")
        return [f"{ind}DetSql.savepoint(SQLCA_AREA, {at}, {self.g_str(sql)}, CS);"]

    def _cursor_sql(self, meth: Method) -> str:
        """The host variables a cursor's query takes (its parameters): as `:NAME` references for _params."""
        return ", ".join(f":{h}" for h in meth.params)  # (commas: `:A :B` would be A with indicator B)
