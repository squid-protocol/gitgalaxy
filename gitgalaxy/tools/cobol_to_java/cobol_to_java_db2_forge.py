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
#
# #3828: JDBC returns a DATE / TIME / TIMESTAMP as a typed value, but the COBOL
# program's character host variable (a DCLGEN DATE is PIC X(10)) held it in the
# DB2 subsystem's format -- DSNHDECP DATE= / TIME=, `culture.db2_date_format`:
# EUR `26.09.2026`, USA `09/26/2026`, ISO / JIS `2026-09-26`. `Db2Dates`, generated
# beside the repositories, converts both ways in that format.
# ==============================================================================
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from gitgalaxy.tools.cobol_to_java.cobol_to_java_common import (
    ClassNames,
    TraceLog,
    java_identifier,
    java_path,
    status_text,
)
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
    "DATE": "LocalDate", "TIME": "LocalTime", "TIMESTAMP": "LocalDateTime", "TIMESTAMP WITH TIME ZONE": "OffsetDateTime",
    "BLOB": "byte[]", "BINARY": "byte[]", "VARBINARY": "byte[]",
}  # fmt: skip
_TIME_IMPORTS = {"LocalDate": "java.time.LocalDate", "LocalTime": "java.time.LocalTime",
                 "LocalDateTime": "java.time.LocalDateTime", "OffsetDateTime": "java.time.OffsetDateTime"}  # fmt: skip


def sql_java_type(sql_type: str) -> str:
    """The Java type of a declared DB2 column type (`TIMESTAMP WITH TIME ZONE` -> OffsetDateTime)."""
    t = " ".join(sql_type.upper().split())
    for name in sorted(_SQL_TYPES, key=len, reverse=True):
        if t == name or t.startswith(name + " ") or t.startswith(name + "("):
            return _SQL_TYPES[name]
    return "String"


def set_as_values(statement: str) -> str | None:
    """`SET :A = e1, :B = e2` or `SET (:A, :B) = (e1, e2)` as the query `VALUES (e1, e2)` (DB2 SQL Reference,
    SET assignment statement: the host variables take the values in order), or None for another form."""
    s = " ".join(statement.split())
    m = re.fullmatch(r"SET\s*\(([^)]*)\)\s*=\s*\((.*)\)", s, re.I)
    if m:
        return f"VALUES ({m.group(2).strip()})"
    exprs = []
    for part in _split_top(s[3:].strip() if s.upper().startswith("SET") else ""):
        a = re.fullmatch(r":[^\s=]+(?:\s*(?:INDICATOR\s*)?:[^\s=]+)?\s*=\s*(.+)", part.strip(), re.I)
        if not a:
            return None
        exprs.append(a.group(1).strip())
    return f"VALUES ({', '.join(exprs)})" if exprs else None


def _split_top(text: str) -> list[str]:
    """`text` split at the commas outside parentheses and quotes."""
    out: list[str] = []
    cur: list[str] = []
    depth, quote = 0, ""
    for ch in text:
        if quote:
            quote = "" if ch == quote else quote
        elif ch in "'\"":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            out.append("".join(cur))
            cur = []
            continue
        cur.append(ch)
    out.append("".join(cur))
    return out


def to_jdbc(statement: str, verb: str) -> tuple[str, list[tuple[str, str]], list[str]]:
    """(SQL for NamedParameterJdbcTemplate, [(host variable, parameter)], notes) of one statement."""
    sql, notes = statement, []
    if verb == "SET":
        values = set_as_values(statement)
        if values is not None:
            sql = values
            notes.append("the SET's host variables are the columns of the returned row, in order")
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
    if verb == "DECLARE CURSOR" and re.search(r"\bFOR\s+UPDATE\b", sql, re.I):
        # a cursor a positioned statement may use: each row also carries its row id, which that statement names
        at = _top_from(sql)
        if at is not None:
            tm = re.match(r"\s*FROM\s+([A-Z0-9_.$#@]+)(?:\s+(?:AS\s+)?(?!WHERE\b|ORDER\b|FOR\b|GROUP\b)([A-Z0-9_]+))?",
                          sql[at:], re.I)  # fmt: skip
            if tm:
                sql = f"{sql[:at].rstrip()}, RID_BIT({tm.group(2) or tm.group(1)}) AS GG_RID {sql[at:]}"
                notes.append("each row also returns GG_RID, its row id, for a positioned UPDATE / DELETE")
    pos = re.search(r"\bWHERE\s+CURRENT\s+OF\s+[A-Z0-9_-]+", sql, re.I)
    if pos:
        tm = re.match(r"\s*(?:UPDATE|DELETE\s+FROM)\s+([A-Z0-9_.$#@]+)", sql, re.I)
        if tm:  # JDBC has no cursor position here: the row FETCH last returned, by its row id
            sql = f"{sql[: pos.start()]}WHERE RID_BIT({tm.group(1)}) = :ggRid{sql[pos.end() :]}"
            params["GG-RID"] = "ggRid"
            notes.append("positioned (WHERE CURRENT OF): the cursor's current row, by the GG_RID its FETCH returned")
        else:
            notes.append("TODO: a positioned statement (WHERE CURRENT OF): rewrite it to the row's key")
    return " ".join(sql.split()), sorted(params.items()), notes


def _top_from(sql: str) -> int | None:
    """The offset of the outermost SELECT's FROM (outside parentheses and quotes), or None."""
    depth, quote = 0, ""
    for i, ch in enumerate(sql):
        if quote:
            quote = "" if ch == quote else quote
        elif ch == "'":
            quote = ch
        elif ch in "()":
            depth += 1 if ch == "(" else -1
        elif depth == 0 and re.match(r"(?i)\bFROM\b", sql[i : i + 5]) and (i == 0 or not sql[i - 1].isalnum()):
            return i
    return None


# #3828: the DB2 character formats of DATE and TIME (DB2 for z/OS SQL Reference, "Datetime values"):
# (date pattern, time pattern, example date, example time). LOCAL is the installation's exit routine.
DB2_DATETIME_FORMATS = {
    "iso": ("uuuu-MM-dd", "HH.mm.ss", "2026-09-26", "14.30.05"),
    "eur": ("dd.MM.uuuu", "HH.mm.ss", "26.09.2026", "14.30.05"),
    "usa": ("MM/dd/uuuu", "hh:mm a", "09/26/2026", "02:30 PM"),
    "jis": ("uuuu-MM-dd", "HH:mm:ss", "2026-09-26", "14:30:05"),
}


def db2_dates_source(package: str, fmt: str) -> str:
    """#3828: `Db2Dates`, the DB2 character DATE / TIME / TIMESTAMP conversions in the subsystem's
    format `fmt` (culture.db2_date_format)."""
    local = fmt not in DB2_DATETIME_FORMATS
    date_pat, time_pat, ex_date, ex_time = DB2_DATETIME_FORMATS.get(fmt, ("", "", "", ""))
    about = (
        " * The DB2 subsystem's DATE / TIME format is LOCAL (an installation exit routine, DSNXVDTX / DSNXVTMX):\n"
        " * TODO(#3828): set LOCAL_DATE / LOCAL_TIME to the exit's patterns -- date() and time() throw until then.\n"
        if local
        else f" * The DB2 subsystem's DATE / TIME format is {fmt.upper()}: a DATE fetched into a character host variable\n"
        f" * reads {ex_date}, a TIME {ex_time}.\n"
    )
    date_expr = "LOCAL_DATE" if local else f'DateTimeFormatter.ofPattern("{date_pat}", Locale.US)'
    time_expr = "LOCAL_TIME" if local else f'DateTimeFormatter.ofPattern("{time_pat}", Locale.US)'
    return (_DB2_DATES.replace("{pkg}", f"{package}.{REPOSITORY_SUBPACKAGE}").replace("{about}", about)
            .replace("{format}", fmt.upper()).replace("{date}", date_expr).replace("{time}", time_expr))  # fmt: skip


_DB2_DATES = """package {pkg};

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeFormatterBuilder;
import java.time.format.DateTimeParseException;
import java.time.format.ResolverStyle;
import java.time.temporal.ChronoField;
import java.util.Locale;

/**
 * #3828: DB2 DATE, TIME and TIMESTAMP values as the COBOL program's character host variables hold them.
 * JDBC returns typed values (java.sql.Date / Time / Timestamp); a program that FETCHed a DATE into a
 * PIC X(10) saw it in the DB2 subsystem's character format (DSNHDECP DATE= / TIME=, or the precompiler's
 * DATE / TIME option), not ISO -- so never LocalDate.toString() for such a field.
{about} * A TIMESTAMP's character form is always yyyy-mm-dd-hh.mm.ss.nnnnnn. On input DB2 reads ISO, USA, EUR
 * and JIS alike, whatever the subsystem's format: the parse methods do too.
 */
public final class Db2Dates {

    /** The DB2 subsystem's DATE / TIME format (culture.db2_date_format). */
    public static final String FORMAT = "{format}";
    /** LOCAL only: the installation exit's patterns (java.time), e.g. "dd/MM/uuuu" and "HH:mm:ss". */
    public static final DateTimeFormatter LOCAL_DATE = null;
    public static final DateTimeFormatter LOCAL_TIME = null;

    private static final DateTimeFormatter DATE = {date};
    private static final DateTimeFormatter TIME = {time};
    private static final DateTimeFormatter TIMESTAMP =
            DateTimeFormatter.ofPattern("uuuu-MM-dd-HH.mm.ss.SSSSSS", Locale.ROOT);
    private static final DateTimeFormatter[] DATE_INPUTS = {
        strict("uuuu-M-d"), strict("M/d/uuuu"), strict("d.M.uuuu"),
    };
    private static final DateTimeFormatter[] TIME_INPUTS = {
        strict("H.mm[.ss]"), strict("H:mm[:ss]"), strict("h[:mm] a"),
    };

    private Db2Dates() {
    }

    private static DateTimeFormatter strict(String pattern) {
        return new DateTimeFormatterBuilder().parseCaseInsensitive().appendPattern(pattern)
                .parseDefaulting(ChronoField.MINUTE_OF_HOUR, 0).parseDefaulting(ChronoField.SECOND_OF_MINUTE, 0)
                .toFormatter(Locale.US).withResolverStyle(ResolverStyle.STRICT);
    }

    private static DateTimeFormatter need(DateTimeFormatter f, String what) {
        if (f == null) {
            throw new IllegalStateException("DB2 " + what + " format LOCAL: set Db2Dates.LOCAL_" + what);
        }
        return f;
    }

    /** A DATE (java.sql.Date, LocalDate, or text in any DB2 format) as a character host variable holds it. */
    public static String date(Object value) {
        LocalDate d = toDate(value);
        return d == null ? null : need(DATE, "DATE").format(d);
    }

    /** A TIME as a character host variable holds it (USA drops the seconds, as DB2 does). */
    public static String time(Object value) {
        LocalTime t = toTime(value);
        return t == null ? null : need(TIME, "TIME").format(t);
    }

    /** A TIMESTAMP as a character host variable holds it: yyyy-mm-dd-hh.mm.ss.nnnnnn. */
    public static String timestamp(Object value) {
        LocalDateTime ts = toTimestamp(value);
        return ts == null ? null : TIMESTAMP.format(ts);
    }

    /** A character DATE in any format DB2 accepts (ISO, USA, EUR, JIS) -- what binding it to a DATE reads. */
    public static LocalDate parseDate(String text) {
        String s = text.trim();
        for (DateTimeFormatter f : DATE_INPUTS) {
            try {
                return LocalDate.parse(s, f);
            } catch (DateTimeParseException e) {
                // not this format; try the next
            }
        }
        if (LOCAL_DATE != null) {
            return LocalDate.parse(s, LOCAL_DATE);
        }
        throw new DateTimeParseException("not a DB2 date: " + text, text, 0);
    }

    /** A character TIME in any format DB2 accepts (ISO / EUR hh.mm.ss, JIS hh:mm:ss, USA hh:mm AM). */
    public static LocalTime parseTime(String text) {
        String s = text.trim();
        for (DateTimeFormatter f : TIME_INPUTS) {
            try {
                return LocalTime.parse(s, f);
            } catch (DateTimeParseException e) {
                // not this format; try the next
            }
        }
        if (LOCAL_TIME != null) {
            return LocalTime.parse(s, LOCAL_TIME);
        }
        throw new DateTimeParseException("not a DB2 time: " + text, text, 0);
    }

    /** A character TIMESTAMP: yyyy-mm-dd-hh.mm.ss[.n...] (1 to 12 fraction digits; nanoseconds kept).
     *  #3946: the digits 0-9 only, as DB2 reads it -- Integer.parseInt alone takes any Unicode digit
     *  (Arabic-Indic, full-width), which DB2 rejects (SQLCODE -180 / -181). An invalid value throws the
     *  DateTimeParseException parseDate throws. */
    public static LocalDateTime parseTimestamp(String text) {
        String s = text.trim();
        String[] hms = s.length() > 11 ? s.substring(11).split("[.:]", 4) : new String[0];
        if (hms.length < 3 || !digits(hms[0], 1, 2) || !digits(hms[1], 2, 2) || !digits(hms[2], 2, 2)
                || (hms.length == 4 && !digits(hms[3], 0, 12))) {
            throw new DateTimeParseException("not a DB2 timestamp: " + text, text, 0);
        }
        LocalTime t;
        try {
            t = LocalTime.of(Integer.parseInt(hms[0]), Integer.parseInt(hms[1]), Integer.parseInt(hms[2]));
        } catch (java.time.DateTimeException e) {
            throw new DateTimeParseException("not a DB2 timestamp: " + text, text, 11, e);
        }
        if (hms.length == 4) {
            String frac = (hms[3] + "000000000").substring(0, 9);
            t = t.withNano(Integer.parseInt(frac));
        }
        return LocalDateTime.of(parseDate(s.substring(0, 10)), t);
    }

    /** #3946: `min` to `max` ASCII digits, nothing else. */
    private static boolean digits(String s, int min, int max) {
        if (s.length() < min || s.length() > max) {
            return false;
        }
        for (int i = 0; i < s.length(); i++) {
            if (s.charAt(i) < '0' || s.charAt(i) > '9') {
                return false;
            }
        }
        return true;
    }

    private static LocalDate toDate(Object v) {
        if (v == null) {
            return null;
        }
        if (v instanceof LocalDate) {
            return (LocalDate) v;
        }
        if (v instanceof java.sql.Date) {
            return ((java.sql.Date) v).toLocalDate();
        }
        if (v instanceof java.sql.Timestamp) {
            return ((java.sql.Timestamp) v).toLocalDateTime().toLocalDate();
        }
        if (v instanceof LocalDateTime) {
            return ((LocalDateTime) v).toLocalDate();
        }
        return parseDate(v.toString());
    }

    private static LocalTime toTime(Object v) {
        if (v == null) {
            return null;
        }
        if (v instanceof LocalTime) {
            return (LocalTime) v;
        }
        if (v instanceof java.sql.Time) {
            return ((java.sql.Time) v).toLocalTime();
        }
        if (v instanceof java.sql.Timestamp) {
            return ((java.sql.Timestamp) v).toLocalDateTime().toLocalTime();
        }
        if (v instanceof LocalDateTime) {
            return ((LocalDateTime) v).toLocalTime();
        }
        return parseTime(v.toString());
    }

    private static LocalDateTime toTimestamp(Object v) {
        if (v == null) {
            return null;
        }
        if (v instanceof LocalDateTime) {
            return (LocalDateTime) v;
        }
        if (v instanceof java.sql.Timestamp) {
            return ((java.sql.Timestamp) v).toLocalDateTime();
        }
        return parseTimestamp(v.toString());
    }
}
"""


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
                 names: ClassNames, trace: TraceLog | None = None) -> None:  # fmt: skip
        self.package, self.target, self.names, self.trace = package, target, names, trace
        section = (estate.get("sections") or {}).get("db2_tables") or {}
        self.status = status_text(section)
        self.key_of = {sk["program"]["file"]: key for key, sk in skeletons.items()}
        self.tables: list[Table] = []
        self.counts = {"tables": 0, "rows": 0, "statements": 0, "positioned": 0}
        self.uses: dict[str, set[str]] = {}  # program key -> repository classes it uses
        for raw in section.get("facts", []):
            # a statement of a converted program -- its own, or in a member it includes (one per including program)
            mine = []
            for s in raw.get("statements", []):
                if not s.get("statement"):
                    continue
                owners = [s["file"]] if s.get("file") in self.key_of else [p for p in s.get("included_by", [])
                                                                            if p in self.key_of]  # fmt: skip
                mine += [{**s, "program_file": p} for p in owners]
            if mine:
                self.tables.append(self._plan({**raw, "statements": mine}))
        # SET :H = expr: the statements that name no table, one repository of their own
        values = (estate.get("sections") or {}).get("db2_values") or {}
        mine = []
        for s in values.get("facts", []):
            owners = [s["file"]] if s.get("file") in self.key_of else [p for p in s.get("included_by", [])
                                                                        if p in self.key_of]  # fmt: skip
            mine += [{**s, "program_file": p} for p in owners if s.get("statement")]
        if mine:
            raw = {"table": "DB2_VALUES", "names": ["(no table: SET host-variable = expression)"], "columns": [],
                   "declared_in": None, "line": None, "statements": mine}  # fmt: skip
            self.tables.append(self._plan(raw))
        self.dates = self._claim("Db2Dates") if self.tables else ""  # #3828

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
        if self.trace and row:  # #3650
            fact = {"source": f"{raw['declared_in']}:{raw['line']}", "section": "db2_tables", "table": raw["table"]}
            self.trace.record(java_path(self.package, ROW_SUBPACKAGE, row), "Class", "db2-row", [fact])
        for st in raw["statements"]:
            key = self.key_of[st.get("program_file", st["file"])]
            self.uses.setdefault(key, set()).add(t.repository)
            t.programs.add(key)
            verb = st["verb"]
            sql, params, notes = to_jdbc(st["statement"], verb)
            self.counts["statements"] += 1
            self.counts["positioned"] += any("WHERE CURRENT OF" in n for n in notes)  # (rewritten or a TODO)
            stem = "cursor" + java_class_base(st["cursor"]) if verb == "DECLARE CURSOR" else verb.split()[0].lower()
            name = f"{stem}L{st['line']}{java_class_base(key)}"
            while name in used:
                name += "X"
            used.add(name)
            if self.trace:  # #3650
                fact = {"source": f"{st['file']}:{st['line']}", "section": "db2_tables", "verb": verb}
                todos = [n for n in notes if n.startswith("TODO")]
                if self.target.database.engine != "db2":
                    todos.append(f"TODO: DB2 SQL on {self.target.database.engine} -- review the statement")
                self.trace.record(
                    java_path(self.package, REPOSITORY_SUBPACKAGE, t.repository),
                    f"{t.repository}#{name}",
                    "db2-statement",
                    [fact],
                    todos,
                )
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
            elif verb.split()[0] in ("SELECT", "SET"):
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
        dated = [c["name"] for c in t.raw.get("columns") or [] if sql_java_type(c["sql_type"]) in _TIME_IMPORTS]
        if dated:  # #3828: a character host variable held these in the subsystem's format, not ISO
            java.append(f" * {', '.join(dated)}: into or from a character host variable, convert with {self.dates} "
                        f"(DB2 {self.target.culture.db2_date_format.upper()} format).")  # fmt: skip
        if engine != "db2":
            java.append(f" * TODO: this SQL is DB2's; the configured database is {engine} -- review each statement.")
        java += [" */", "@Repository", f"public class {t.repository} {{\n",
                 "    private final NamedParameterJdbcTemplate jdbc;\n",
                 f"    public {t.repository}(NamedParameterJdbcTemplate jdbc) {{", "        this.jdbc = jdbc;", "    }\n"]  # fmt: skip
        java += t.methods
        java.append("}")
        return "\n".join(java)

    def sources(self) -> dict[tuple[str, ...], dict[str, str]]:
        repositories = {t.repository: self.repository_source(t) for t in self.tables}
        if self.tables:  # #3828: the character DATE / TIME conversions every repository's caller may need
            repositories[self.dates] = db2_dates_source(self.package, self.target.culture.db2_date_format)
        return {
            ("dto", "db2"): {t.row: self.row_source(t) for t in self.tables if t.row},
            ("repository", "db2"): repositories,
        }

    def service_extras(self, key: str) -> dict[str, Any] | None:
        repos = sorted(self.uses.get(key, set()))
        if not repos:
            return None
        return {
            "imports": [f"import {self.package}.{REPOSITORY_SUBPACKAGE}.{r};" for r in repos],
            "fields": [(r, r[0].lower() + r[1:]) for r in repos],
        }
