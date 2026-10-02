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

Not modelled (a Hole naming it): WHENEVER (the program tests SQLCODE itself or the port would guess its branches),
ROLLBACK (the generated repositories run each statement in its own unit of work), positioned UPDATE / DELETE,
dynamic SQL, host variable arrays, a statement the generator has no method for."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
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


_DOC = re.compile(r"/\*\*\s*EXEC SQL ([A-Z ]+?) at ([^\s:]+):(\d+) \((\w+),.*?\*/\s*public\s+[^(]*?\s(\w+)\(", re.S)


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


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class Sql:
    Error = SqlError

    def __init__(self, gen, program: str, java_root: Path | None):
        self.g = gen
        self.program = program.upper()
        self.methods = repositories(java_root)
        self.repos: dict[str, str] = {}  # repository class -> its field

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
        if it.pic or self._varchar(it):
            return [it]
        if it.occurs > 1:
            raise SqlError(f"host variable array {it.name}")
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
        return [ln.replace("SQLCA_AREA", ca) for ln in self._command(text, line, ind)]

    def _command(self, text: str, line: int, ind: str) -> list[str]:
        body = re.match(r"(?is)\s*EXEC\s+SQL\b(.*?)\bEND-EXEC\b", text)
        if not body:
            raise SqlError("EXEC SQL without END-EXEC")
        sql = _norm(body.group(1))
        u = sql.upper()
        verb = u.split()[0] if u else ""
        if verb in ("INCLUDE", "DECLARE"):
            return []
        if verb in ("WHENEVER", "PREPARE", "EXECUTE", "DESCRIBE", "CONNECT", "SET", "CALL"):
            raise SqlError(f"EXEC SQL {verb}")
        if verb == "COMMIT":
            return [f"{ind}DetSql.reset(SQLCA_AREA, CS);  // each statement committed as it ran (the repositories')"]
        if verb == "ROLLBACK":
            raise SqlError("ROLLBACK: the generated repositories commit each statement")
        if re.search(r"\bWHERE\s+CURRENT\s+OF\b", u):
            raise SqlError("a positioned UPDATE / DELETE")
        meth = self.methods.get((self.program, line))
        if meth is None:
            raise SqlError(f"no generated Db2 repository method for the statement at line {line}")
        repo_field = meth.repo[0].lower() + meth.repo[1:]
        self.repos[meth.repo] = repo_field
        call = f"{repo_field}.{meth.name}"
        n = self.g.tmpname("sqlParams")
        if verb in ("INSERT", "UPDATE", "DELETE"):
            searched = verb != "INSERT"
            return [
                *self._params(sql, meth, n, ind),
                f"{ind}DetSql.update(SQLCA_AREA, () -> {call}({n}), {'true' if searched else 'false'}, CS);",
            ]
        if verb in ("SELECT", "WITH") and meth.verb != "CURSOR":
            m = re.match(r"(.*?)\bINTO\b(.*?)\bFROM\b(.*)", sql, re.I | re.S)
            if not m:
                raise SqlError("SELECT without INTO")
            row = self.g.tmpname("sqlRow")
            return [*self._params(m.group(1) + " FROM " + m.group(3), meth, n, ind),
                    f"{ind}java.util.Map<String, Object> {row} = DetSql.selectOne(SQLCA_AREA, () -> {call}({n}), CS);",
                    *self._into(m.group(2), row, ind)]  # fmt: skip
        if verb == "OPEN" and meth.verb == "CURSOR":
            cursor = u.split()[1]
            return [
                *self._params(self._cursor_sql(meth), meth, n, ind),
                f"{ind}DetSql.open(SQLCA_AREA, {self.g_str(cursor)}, () -> {call}({n}), CS);",
            ]
        if verb == "FETCH" and meth.verb == "CURSOR":
            m = re.fullmatch(r"FETCH\s+(?:NEXT\s+)?(?:FROM\s+)?([A-Z0-9_-]+)\s+INTO\s+(.*)", sql, re.I | re.S)
            if not m:
                raise SqlError(f"EXEC SQL {u[:50]}")
            row = self.g.tmpname("sqlRow")
            return [f"{ind}java.util.Map<String, Object> {row} = DetSql.fetch(SQLCA_AREA, "
                    f"{self.g_str(m.group(1).upper())}, CS);", *self._into(m.group(2), row, ind)]  # fmt: skip
        if verb == "CLOSE" and meth.verb == "CURSOR":
            return [f"{ind}DetSql.close(SQLCA_AREA, {self.g_str(u.split()[1])}, CS);"]
        raise SqlError(f"EXEC SQL {verb}")

    def _cursor_sql(self, meth: Method) -> str:
        """The host variables a cursor's query takes (its parameters): as `:NAME` references for _params."""
        return " ".join(f":{h}" for h in meth.params)
