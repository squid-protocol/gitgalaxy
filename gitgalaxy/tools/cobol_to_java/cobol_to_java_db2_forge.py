# ==============================================================================
# GitGalaxy Tool: embedded DB2 -> Spring JDBC repositories (#3618)
#
# PURPOSE:
# Each DB2 table the programs use (GalaxyIR.db2_tables: its DECLARE ... TABLE
# and every embedded statement against it) becomes:
#   - `<Table>Row`, a data class of the DECLAREd columns with Java types for the
#     declared SQL types (when the repository holds a DECLARE);
#   - `<Table>Repository`, a @Repository over NamedParameterJdbcTemplate with one
#     method per embedded statement -- the program's OWN SQL text, host variables
#     turned into named parameters (`:WS-ACCT-ID` -> `:wsAcctId`), a singleton
#     SELECT's `INTO :x, :y` dropped (the row comes back instead), a cursor's
#     SELECT run as a query whose rows the OPEN / FETCH / CLOSE lines consumed.
#
# Not JPA: DECLARE TABLE states no primary key, and an @Entity needs one; a
# made-up key would be a guess. Positioned `WHERE CURRENT OF` statements keep
# their text with a TODO (JDBC has no cursor position here). The SQL is DB2's;
# with another `database.engine` the class says so. Every method cites the
# program file:line and the field-testing status of `DB2 table access`.
# ==============================================================================
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from gitgalaxy.tools.cobol_to_java.cobol_to_java_common import ClassNames, java_identifier, status_text
from gitgalaxy.tools.cobol_to_java.cobol_to_java_names import java_class_base
from gitgalaxy.tools.cobol_to_java.cobol_to_java_spring_forge import render_dto_class
from gitgalaxy.tools.cobol_to_java.java_target import JavaTarget

ROW_SUBPACKAGE = "dto.db2"
REPOSITORY_SUBPACKAGE = "repository.db2"
# A host variable (with an optional indicator `:H:IND`, `:H :IND` or `:H INDICATOR :IND`).
_HOST = re.compile(
    r":([A-Z0-9][A-Z0-9_-]*(?:\.[A-Z0-9][A-Z0-9_-]*)?)(?:\s*(?:INDICATOR\s*)?:[A-Z0-9][A-Z0-9_-]*)?", re.I
)
_SINGLETON_INTO = re.compile(
    r"\bINTO\s+:[^\s,]+(?:\s*(?:INDICATOR\s*)?:[^\s,]+)?(?:\s*,\s*:[^\s,]+(?:\s*(?:INDICATOR\s*)?:[^\s,]+)?)*", re.I
)
_CURSOR_FOR = re.compile(r"^DECLARE\s+\S+\s+(?:[A-Z ]+\s+)?CURSOR\s+(?:WITH\s+(?:HOLD|RETURN)\s+)*FOR\s+", re.I)
_SQL_TYPES = {
    "CHAR": "String", "CHARACTER": "String", "VARCHAR": "String", "GRAPHIC": "String", "VARGRAPHIC": "String",
    "CLOB": "String", "DBCLOB": "String", "LONG VARCHAR": "String",
    "SMALLINT": "Integer", "INTEGER": "Integer", "INT": "Integer", "BIGINT": "Long",
    "DECIMAL": "BigDecimal", "DEC": "BigDecimal", "NUMERIC": "BigDecimal",
    "REAL": "Double", "FLOAT": "Double", "DOUBLE": "Double", "DOUBLE PRECISION": "Double", "DECFLOAT": "BigDecimal",
    "DATE": "LocalDate", "TIME": "LocalTime", "TIMESTAMP": "LocalDateTime",
    "BLOB": "byte[]", "BINARY": "byte[]", "VARBINARY": "byte[]",
}  # fmt: skip
_TIME_IMPORTS = {"LocalDate": "java.time.LocalDate", "LocalTime": "java.time.LocalTime",
                 "LocalDateTime": "java.time.LocalDateTime"}  # fmt: skip


def sql_java_type(sql_type: str) -> str:
    """The Java type of a declared DB2 column type (`TIMESTAMP WITH TIME ZONE` -> LocalDateTime)."""
    t = " ".join(sql_type.upper().split())
    for name in sorted(_SQL_TYPES, key=len, reverse=True):
        if t == name or t.startswith(name + " ") or t.startswith(name + "("):
            return _SQL_TYPES[name]
    return "String"


def to_jdbc(statement: str, verb: str) -> tuple[str, list[tuple[str, str]], list[str]]:
    """(SQL for NamedParameterJdbcTemplate, [(host variable, parameter)], notes) of one statement."""
    sql, notes = statement, []
    if verb == "DECLARE CURSOR":
        sql = _CURSOR_FOR.sub("", sql, count=1)
    if verb.split()[0] == "SELECT" or verb == "DECLARE CURSOR":
        sql, n = _SINGLETON_INTO.subn("", sql, count=1)
        if n:
            notes.append("the INTO host variables are the columns of the returned row")
    params: dict[str, str] = {}

    def named(m: re.Match) -> str:
        host = m.group(1).upper()
        params.setdefault(host, java_identifier(host.replace(".", "-")))
        return ":" + params[host]

    sql = _HOST.sub(named, sql)
    if re.search(r"\bWHERE\s+CURRENT\s+OF\b", sql, re.I):
        notes.append("TODO: a positioned statement (WHERE CURRENT OF): rewrite it to the row's key")
    return " ".join(sql.split()), sorted(params.items()), notes


def _text_block(sql: str) -> str:
    """A Java text block holding `sql` (Java 15+; the matrix targets 17 and 21)."""
    body = sql.replace("\\", "\\\\").replace('"""', '\\"""')
    return '"""\n            ' + body + '\n            """'


@dataclass
class Table:
    raw: dict
    row: str | None
    repository: str
    methods: list[str] = field(default_factory=list)
    programs: set[str] = field(default_factory=set)


class Db2Forge:
    """Plans each DB2 table used by a converted program: its row class, repository and service wiring."""

    def __init__(self, estate: dict, skeletons: dict[str, dict], package: str, target: JavaTarget,
                 names: ClassNames) -> None:  # fmt: skip
        self.package, self.target, self.names = package, target, names
        section = (estate.get("sections") or {}).get("db2_tables") or {}
        self.status = status_text(section)
        self.key_of = {sk["program"]["file"]: key for key, sk in skeletons.items()}
        self.tables: list[Table] = []
        self.counts = {"tables": 0, "rows": 0, "statements": 0, "positioned": 0}
        self.uses: dict[str, set[str]] = {}  # program key -> repository classes it uses
        for raw in section.get("facts", []):
            mine = [s for s in raw.get("statements", []) if s.get("file") in self.key_of and s.get("statement")]
            if mine:
                self.tables.append(self._plan({**raw, "statements": mine}))

    def _claim(self, name: str) -> str:
        base, n = name, 1
        while name in self.names:
            n += 1
            name = f"{base}{n}"
        return self.names.claim(name)

    def _plan(self, raw: dict) -> Table:
        base = java_class_base(raw["table"])
        row = self._claim(base + "Row") if raw.get("columns") else None
        t = Table(raw, row, self._claim(base + "Repository"))
        self.counts["tables"] += 1
        self.counts["rows"] += bool(row)
        used: set[str] = set()
        for st in raw["statements"]:
            key = self.key_of[st["file"]]
            self.uses.setdefault(key, set()).add(t.repository)
            t.programs.add(key)
            verb = st["verb"]
            sql, params, notes = to_jdbc(st["statement"], verb)
            self.counts["statements"] += 1
            self.counts["positioned"] += any("WHERE CURRENT OF" in n for n in notes)
            stem = "cursor" + java_class_base(st["cursor"]) if verb == "DECLARE CURSOR" else verb.split()[0].lower()
            name = f"{stem}L{st['line']}{java_class_base(key)}"
            while name in used:
                name += "X"
            used.add(name)
            doc = [
                f"    /** EXEC SQL {verb} at {st['file']}:{st['line']} ({key.upper()}, {st['access'] or 'no'} access)."
            ]
            if st.get("cursor_use"):
                doc.append(
                    "     *  The cursor's "
                    + ", ".join(f"{u['verb']} at line {u['line']}" for u in st["cursor_use"])
                    + "."
                )
            if params:
                doc.append("     *  Parameters: " + ", ".join(f"{p} = :{h}" for h, p in params) + ".")
            doc += [f"     *  {n[0].upper() + n[1:]}." for n in notes]
            doc.append(f"     *  DB2 table access field testing: {self.status}. */")
            if verb == "DECLARE CURSOR":
                sig, call = "List<Map<String, Object>>", "queryForList"
            elif verb.split()[0] == "SELECT":
                sig, call = "Map<String, Object>", "queryForMap"  # SQLCODE +100 -> EmptyResultDataAccessException
            else:
                sig, call = "int", "update"
            t.methods += [
                *doc,
                f"    public {sig} {name}(Map<String, ?> params) {{",
                f"        return jdbc.{call}({_text_block(sql)}, params);",
                "    }\n",
            ]
        return t

    # ---- Java -------------------------------------------------------------------
    def row_source(self, t: Table) -> str:
        body: list[str] = []
        imports: set[str] = set()
        seen: dict[str, int] = {}
        for c in t.raw["columns"]:
            jtype = sql_java_type(c["sql_type"])
            if jtype in _TIME_IMPORTS:
                imports.add(_TIME_IMPORTS[jtype])
            var = java_identifier(c["name"].replace("_", "-"))
            seen[var] = seen.get(var, 0) + 1
            var = var if seen[var] == 1 else f"{var}{seen[var]}"
            size = (
                f"({c['length']}{',' + str(c['scale']) if c.get('scale') is not None else ''})"
                if c.get("length")
                else ""
            )
            null = "" if c.get("nullable") else " NOT NULL"
            body += [
                f"    // {c['name']} {c['sql_type']}{size}{null} (column {c['colno']})",
                f"    private {jtype} {var};\n",
            ]
        doc = [f"DB2 table {', '.join(t.raw['names'])}, as DECLAREd at {t.raw['declared_in']}:{t.raw['line']}.",
               "No primary key is declared, so this is a row, not a JPA entity.",
               f"DB2 table access field testing: {self.status}."]  # fmt: skip
        java = render_dto_class(f"{self.package}.{ROW_SUBPACKAGE}", t.row or "", body, False, self.target, javadoc=doc)
        if imports:  # java.time types: add the imports after the package line
            head, rest = java.split("\n", 1)
            java = head + "\n" + "".join(f"import {i};\n" for i in sorted(imports)) + rest
        return java

    def repository_source(self, t: Table) -> str:
        engine = self.target.database.engine
        java = [f"package {self.package}.{REPOSITORY_SUBPACKAGE};\n",
                "import java.util.List;", "import java.util.Map;",
                "import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;",
                "import org.springframework.stereotype.Repository;", "",
                "/**", f" * DB2 table {', '.join(t.raw['names'])}: the embedded SQL of "
                f"{', '.join(sorted(k.upper() for k in t.programs))}, one method per statement, as written.",
                " * Each returns what JDBC returns; mapping onto business types is the service's job."]  # fmt: skip
        if t.row:
            java.append(f" * Columns: {self.package}.{ROW_SUBPACKAGE}.{t.row}.")
        if engine != "db2":
            java.append(f" * TODO: this SQL is DB2's; the configured database is {engine} -- review each statement.")
        java += [" */", "@Repository", f"public class {t.repository} {{\n",
                 "    private final NamedParameterJdbcTemplate jdbc;\n",
                 f"    public {t.repository}(NamedParameterJdbcTemplate jdbc) {{", "        this.jdbc = jdbc;", "    }\n"]  # fmt: skip
        java += t.methods
        java.append("}")
        return "\n".join(java)

    def sources(self) -> dict[tuple[str, ...], dict[str, str]]:
        return {
            ("dto", "db2"): {t.row: self.row_source(t) for t in self.tables if t.row},
            ("repository", "db2"): {t.repository: self.repository_source(t) for t in self.tables},
        }

    def service_extras(self, key: str) -> dict[str, Any] | None:
        repos = sorted(self.uses.get(key, set()))
        if not repos:
            return None
        return {
            "imports": [f"import {self.package}.{REPOSITORY_SUBPACKAGE}.{r};" for r in repos],
            "fields": [(r, r[0].lower() + r[1:]) for r in repos],
        }
