"""The database of a Db2 equivalence case: one real Db2 (IBM Db2 Community Edition, in a container) that both sides
run their SQL on -- the COBOL side through ggsql.c and IBM's CLI driver, the Java side through JDBC.

A case declares it under "db2":

    "db2": {"ddl": ["app/.../ddl/TRNTYPE.ddl"],        the tables, created as the corpus's DDL says
            "seed": "@case/seed.sql",                 INSERTs: the tables' content before every run
            "compare": ["CARDDEMO.TRANSACTION_TYPE"], what each run leaves there, compared row by row
            "qualifier": "IBMUSER",                   the bind's QUALIFIER: the schema unqualified names resolve to
            "symbols": {"<DB2DBID>": "GENASA1"}}      install symbols in the DDL and seed, as the installer sets them

A seed may be a z/OS job too (GenApp's db2cre.jcl creates its tables and INSERTs their rows): its INSERTs are the
seed. Every reset also restarts each compared table's identity column at its START WITH value, so both sides
generate the same keys.

A DDL member may be SQL, or a z/OS job that runs it (a `.jcl` member: its in-stream SQL, from the first statement to
`/*`). Db2 for z/OS clauses that place or audit a table but do not change what a query returns are removed, as Db2
for Linux rejects them (ddl_text): `IN database.tablespace`, `USING STOGROUP`, `AUDIT ...`, `[NOT] VOLATILE
[CARDINALITY]`, `SET CURRENT SQLID`, and CREATE DATABASE / STOGROUP / TABLESPACE statements.

Before each run (the COBOL step, every Java run, every fault run) the compared and seeded tables are emptied and
the seed loaded again. A table is dumped as text, one row a line, ordered by every column: each value between
brackets as Db2 renders it in character form (VARCHAR() of the column: a string with its trailing blanks, a number
as its decimal digits), NULL as NULL -- so a length or a trailing blank that differs is a difference.

The container is started on first use and left running (`docker rm -f gitgalaxy-db2` stops it).

A pool of databases in that one instance lets Db2 cases run side by side: GGDB (the container's own) and GGDB1 ..
GGDB<n-1> ($GITGALAXY_DB2_POOL, default 4), each created on first use with GGDB's code set, territory, collation and
page size. A case takes one database for its whole run (hold_lock: a lock file per database, GGDB's the one older
checkouts take). Every name its SQL uses -- IBMUSER.ACCOUNT, CARDDEMO.TRANSACTION_TYPE, a bind QUALIFIER -- is the
same in every database, so nothing in either side's SQL changes, and no case sees another's rows: a database has its
own catalog, schemas, tables and identity counters. The database is held active (activate): one nothing keeps
active is activated by each connect and deactivated by the last disconnect, about a second each time.

Table metadata (columns, identity columns) is read once a run, after the tables are created, in one query; a run's
reset and its dumps go to Db2 as one CLP call each (a CLP call costs about a second, mostly its back end starting)."""

from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

import equivalence_common as common

CONTAINER = "gitgalaxy-db2"
NETWORK = "gitgalaxy-db2"
IMAGE = "icr.io/db2_community/db2:latest"
COBOL_IMAGE = "gitgalaxy-gnucobol-db2:3"
DATABASE0 = "GGDB"  # the container's own database: the pool's first
DATABASE = DATABASE0  # this process's database (hold_lock picks it from the pool)
POOL_ENV = "GITGALAXY_DB2_POOL"
USER, PASSWORD = "db2inst1", "ggdb2pass"  # a local, throwaway test database
PORT = 50000
DOCKERFILE = common.CASES / "gnucobol-db2.Dockerfile"
STUB = common.CASES / "db2" / "ggsql.c"
RUNNER = common.CASES / "db2" / "ggsqlrun.c"


_LOCK = None


def pool() -> list[str]:
    """The databases Db2 cases run on, one case at a time each."""
    n = max(1, int(os.environ.get(POOL_ENV) or 4))
    return [DATABASE0, *(f"{DATABASE0}{i}" for i in range(1, n))]


def _lock_path(database: str) -> Path:
    # GGDB's is the path older checkouts lock, so they and this one never share it
    name = "gitgalaxy-db2.lock" if database == DATABASE0 else f"gitgalaxy-db2-{database}.lock"
    return Path.home() / ".cache" / name


def hold_lock() -> None:
    """A database of the pool to this process until it ends (an exclusive lock on it; with every database taken,
    the next one free)."""
    global _LOCK, DATABASE
    import fcntl

    if _LOCK is not None:
        return
    while True:
        for database in pool():
            path = _lock_path(database)
            path.parent.mkdir(parents=True, exist_ok=True)
            fh = path.open("w")
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                fh.close()
                continue
            _LOCK, DATABASE = fh, database
            return
        time.sleep(1)


def _docker(*args: str, check: bool = True, timeout: int = 600, inp: str | None = None) -> str:
    proc = subprocess.run(["docker", *args], capture_output=True, text=True, check=False, timeout=timeout,  # noqa: S603, S607
                          input=inp)  # fmt: skip
    if check and proc.returncode != 0:
        raise RuntimeError(f"docker {' '.join(args[:3])}: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout


_ACTIVE: set[str] = set()


def ensure() -> None:
    """The Db2 container running, this process's database created and active, the COBOL side's image built."""
    _ensure_container()
    _ensure_database(DATABASE)
    activate(DATABASE)


def activate(database: str) -> None:
    """The database held active, once a process (see the module's docstring)."""
    if database not in _ACTIVE:
        _instance(f"db2 activate database {database}")
        _ACTIVE.add(database)


def _instance(command: str) -> str:
    """A Db2 instance command (no database connection), as the instance owner."""
    return _docker("exec", CONTAINER, "su", "-", USER, "-c", command, check=False, timeout=1800)


def _db_cfg(database: str) -> dict[str, str]:
    cfg = {}
    for ln in _instance(f"db2 get db cfg for {database}").splitlines():
        key, eq, value = ln.partition(" = ")
        if eq:
            cfg[key.strip()] = value.strip()
    return cfg


def _ensure_database(database: str) -> None:
    """A pool database (not GGDB, the container's own) created on first use, as GGDB is: its code set, territory,
    collating sequence and page size -- what a stored value, a comparison or an ORDER BY can depend on."""
    if database == DATABASE0 or database in _ACTIVE:
        return
    import fcntl

    listed = lambda: re.findall(r"Database name\s*=\s*(\S+)", _instance("db2 list database directory"))  # noqa: E731
    if database in listed():
        return
    path = Path.home() / ".cache" / "gitgalaxy-db2-setup.lock"
    with path.open("w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)  # one CREATE DATABASE at a time
        if database in listed():
            return
        ref = _db_cfg(DATABASE0)
        out = _instance(f"db2 create database {database} using codeset {ref['Database code set']} territory "
                        f"{ref['Database territory']} collate using {ref['Database collating sequence']} "
                        f"pagesize {ref['Database page size']}")  # fmt: skip
        if database not in listed():
            raise RuntimeError(f"Db2: CREATE DATABASE {database} failed: {out.strip()[-400:]}")


def _ensure_container() -> None:
    if not _docker("images", "-q", COBOL_IMAGE).strip():
        _docker("build", "-q", "-t", COBOL_IMAGE, "-f", str(DOCKERFILE), str(common.CASES), timeout=1800)
    state = _docker("inspect", "-f", "{{.State.Running}}", CONTAINER, check=False).strip()
    if state == "true":
        return
    if not _docker("network", "ls", "-q", "-f", f"name=^{NETWORK}$").strip():
        _docker("network", "create", NETWORK)
    if state == "false":
        _docker("start", CONTAINER)
    else:
        _docker("run", "-d", "--name", CONTAINER, "--network", NETWORK, "--privileged", "-p", f"127.0.0.1:{PORT}:50000",
                "-e", "LICENSE=accept", "-e", f"DB2INSTANCE={USER}", "-e", f"DB2INST1_PASSWORD={PASSWORD}",
                "-e", f"DBNAME={DATABASE0}", "-e", "BLU=false", "-e", "ENABLE_ORACLE_COMPATIBILITY=false",
                "-e", "UPDATEAVAIL=NO", "-e", "TO_CREATE_SAMPLEDB=false", "-e", "REPODB=false",
                "-e", "IS_OSXFS=false", "-e", "PERSISTENT_HOME=false", "-e", "HADR_ENABLED=false", IMAGE)  # fmt: skip
    for _ in range(120):  # first start: several minutes
        if "Setup has completed" in _docker("logs", CONTAINER, check=False) and _clp("VALUES 1", check=False)[0] == 0:
            return
        time.sleep(10)
    raise RuntimeError("Db2 did not come up")


def _clp(script: str, check: bool = True) -> tuple[int, str]:
    """Run SQL (`;`-terminated statements) with Db2's command line processor, connected to the case database."""
    proc = subprocess.run(["docker", "exec", "-i", CONTAINER, "su", "-", USER, "-c",  # noqa: S603, S607
                           f"db2 connect to {DATABASE} >/dev/null && db2 -x -t -v +p"],
                          input=script if script.rstrip().endswith(";") else script + ";",
                          capture_output=True, text=True, check=False, timeout=600)  # fmt: skip
    failed = [ln for ln in proc.stdout.splitlines() if ln.startswith("SQL") and "N " in ln[:12]]
    if check and failed:
        raise RuntimeError(f"Db2: {failed[0]}")
    return (1 if failed else 0), proc.stdout


def _tables(case: dict[str, Any]) -> list[str]:
    spec = case["db2"]
    return list(dict.fromkeys([*spec.get("compare", []), *spec.get("tables", [])]))


_ZOS_ONLY = [
    re.compile(r"\bIN\s+[A-Z0-9_#@$]+\.[A-Z0-9_#@$]+", re.I),  # IN database.tablespace
    re.compile(r"\bUSING\s+STOGROUP\s+[A-Z0-9_#@$]+", re.I),
    re.compile(r"\bAUDIT\s+(NONE|CHANGES|ALL)\b", re.I),
    re.compile(r"\b(NOT\s+)?VOLATILE(\s+CARDINALITY)?\b", re.I),
    re.compile(r"\bCCSID\s+(EBCDIC|ASCII|UNICODE)\b", re.I),  # (the table's text then sorts as Unicode: register Q7)
    re.compile(r"\bCOPY\s+(YES|NO)\b", re.I),
]
_ZOS_STATEMENTS = re.compile(r"^\s*(SET\s+CURRENT\s+SQLID|CREATE\s+(DATABASE|STOGROUP|TABLESPACE)|COMMIT"
                             r"|GRANT\s+DBADM|GRANT\s+USE\s+OF)\b", re.I)  # fmt: skip


def ddl_text(path: Path, symbols: dict[str, str] | None = None) -> str:
    """A DDL member as Db2 for Linux runs it (see the module's docstring): a job's in-stream SQL, install symbols
    set, z/OS-only clauses and statements removed. Anything else is kept as written."""
    text = path.read_text(encoding="latin-1")
    for k, v in (symbols or {}).items():
        text = text.replace(k, v)
    if path.suffix.lower() == ".jcl":
        body, on = [], False
        for ln in text.splitlines():
            if ln.startswith("/*") and on:
                on = False
            elif re.match(r"\s*(SET|CREATE|ALTER|INSERT|DROP)\b", ln, re.I) and not ln.startswith("//"):
                on = True
            if on and not ln.startswith("//"):
                body.append(ln[:72])
        text = "\n".join(body)
    out = []
    for stmt in text.split(";"):
        if not stmt.strip() or _ZOS_STATEMENTS.match(stmt):
            continue
        for rx in _ZOS_ONLY:
            stmt = rx.sub("", stmt)
        out.append(stmt.strip() + ";")
    return "\n".join(out) + "\n"


def create(case: dict[str, Any], corpus: Path) -> None:
    """The case's tables, dropped and created again from its DDL (every table the DDL creates, compared or not)."""
    ensure()
    _META.clear()
    ddls = [ddl_text(corpus / ddl, case["db2"].get("symbols")) for ddl in case["db2"].get("ddl", [])]
    made = [t for text in ddls for t in re.findall(r"CREATE\s+TABLE\s+([A-Z0-9_.$#@]+)", text, re.I)]
    # one CLP call: each DROP fails alone when its table is not there (CLP goes on to the next statement); a row
    # longer than a 4K page (GenApp's ENDOWMENT VARCHAR(32606)) needs a table space whose pages hold it, created
    # once a database (z/OS sizes its pages per table space in the DDL itself)
    _clp("".join(f"DROP TABLE {t};\n" for t in dict.fromkeys([*_tables(case), *made]))
         + "CREATE BUFFERPOOL GGBP32K SIZE 1000 PAGESIZE 32K;\nCREATE TABLESPACE GGTS32K PAGESIZE 32K BUFFERPOOL GGBP32K;",
         check=False)  # fmt: skip
    if ddls:
        _clp("".join(ddls))


def reset(case: dict[str, Any], corpus: Path) -> None:
    """The tables as the seed has them: emptied, the seed's INSERTs run, committed."""
    _clp(reset_script(case, corpus).rstrip() + "\nCOMMIT;")


_META: dict[tuple[str, str], list[tuple[str, bool]]] = {}  # (schema, table) -> [(column, identity)], COLNO order


def _key(table: str) -> tuple[str, str]:
    schema, _, name = table.upper().rpartition(".")
    return schema or USER.upper(), name


def _load_meta(tables: list[str]) -> None:
    """The tables' columns from the catalog, in one query, kept for the run (create() empties it)."""
    need = [k for k in dict.fromkeys(_key(t) for t in tables) if k not in _META]
    if not need:
        return
    where = " OR ".join(f"(TABSCHEMA = '{s}' AND TABNAME = '{n}')" for s, n in need)
    _, out = _clp(f"SELECT RTRIM(TABSCHEMA) || '|' || TABNAME || '|' || COLNAME || '|' || IDENTITY "
                  f"FROM SYSCAT.COLUMNS WHERE {where} ORDER BY TABSCHEMA, TABNAME, COLNO;")  # fmt: skip
    found: dict[tuple[str, str], list[tuple[str, bool]]] = {}
    for ln in out.splitlines():
        parts = ln.strip().split("|")
        if len(parts) == 4 and (parts[0], parts[1]) in need:
            found.setdefault((parts[0], parts[1]), []).append((parts[2], parts[3] == "Y"))
    _META.update(found)


def columns(table: str) -> list[str]:
    _load_meta([table])
    names = [c for c, _ in _META.get(_key(table), [])]
    if not names:
        raise RuntimeError(f"Db2: no table {table}")
    return names


def dump_query(table: str, names: list[str]) -> str:
    """The query a dump runs: one column, each row's values rendered and joined."""
    expr = " || '|' || ".join(f"COALESCE('[' || VARCHAR({c}) || ']', 'NULL')" for c in names)
    return f"SELECT {expr} FROM {table} ORDER BY {', '.join(names)}"


_DUMP_END = "GG-DUMP-END"  # a line no dump row can be: rows start with "[" or NULL


def dump(case: dict[str, Any], table: str) -> bytes:
    """One table's rows as text (see the module's docstring)."""
    return dumps(case, [table])[table]


def dumps(case: dict[str, Any], tables: list[str]) -> dict[str, bytes]:
    """Each table's rows as text, every query in one CLP call (each followed by a marker row)."""
    _load_meta(tables)
    names = {t: columns(t) for t in tables}
    _, out = _clp("".join(f"{dump_query(t, names[t])};\nVALUES '{_DUMP_END}';\n" for t in tables))
    sections: list[list[str]] = [[]]
    for ln in out.splitlines():
        if ln.strip() == _DUMP_END:
            sections.append([])
        elif ln.startswith("[") or ln.startswith("NULL"):
            sections[-1].append(ln.rstrip())  # (CLP pads rows)
    return {t: ("|".join(names[t]) + "\n" + "\n".join(rows) + "\n").encode("latin-1")
            for t, rows in zip(tables, sections)}  # fmt: skip


def reset_script(case: dict[str, Any], corpus: Path) -> str:
    """The SQL that resets the tables to the seed (ggsqlrun -f, and the Java side's EquivalenceRunTest): every table
    the seed fills or the case names, emptied (the seed's tables in the reverse of their INSERTs: children first),
    each one's identity column restarted, then the seed's INSERTs."""
    seed_sql = ""
    seed = case["db2"].get("seed")
    if seed:
        path = common._input_path(case, corpus, seed)
        symbols = case["db2"].get("symbols")
        if path.suffix.lower() == ".jcl":  # a job's INSERTs
            stmts = [st.strip() for st in ddl_text(path, symbols).split(";")]
            seed_sql = "".join(st + ";\n" for st in stmts if re.match(r"INSERT\b", st, re.I))
        else:
            seed_sql = path.read_text(encoding="latin-1")
            for k, v in (symbols or {}).items():
                seed_sql = seed_sql.replace(k, v)
    seeded = list(dict.fromkeys(t.upper() for t in re.findall(r"INSERT\s+INTO\s+([A-Z0-9_.$#@]+)", seed_sql, re.I)))
    tables = [*reversed(seeded), *[t for t in _tables(case) if t.upper() not in seeded]]
    script = "".join(f"DELETE FROM {t};\n" for t in tables)
    _load_meta(tables)
    for t in tables:
        for c in [c for c, identity in _META.get(_key(t), []) if identity]:
            script += f"ALTER TABLE {t} ALTER COLUMN {c} RESTART;\n"
    return script + seed_sql


def diff_dump(left: bytes, right: bytes) -> dict[str, Any]:
    """Two dumps of a table compared row by row, in the shape of a record diff (a row a record, its line the field)."""
    a_lines = left.decode("latin-1").splitlines()
    b_lines = right.decode("latin-1").splitlines()
    head = a_lines[0] if a_lines else (b_lines[0] if b_lines else "")
    a_rows, b_rows = a_lines[1:], b_lines[1:]
    diffs: list[dict[str, Any]] = []
    for i in range(max(len(a_rows), len(b_rows))):
        a = a_rows[i] if i < len(a_rows) else None
        b = b_rows[i] if i < len(b_rows) else None
        if a is None or b is None:
            diffs.append({"record": i + 1, "missing": "cobol" if a is None else "java"})
        elif a != b:
            diffs.append({"record": i + 1, "fields": [{"field": head, "cobol": a, "java": b}]})
    rows = max(len(a_rows), len(b_rows))
    return {"records": rows, "equal": rows - len(diffs), "diffs": diffs[:20], "layout_bytes": None}


def outputs(case: dict[str, Any]) -> dict[str, bytes]:
    tables = case["db2"].get("compare", [])
    return {f"DB2 {t}": data for t, data in dumps(case, tables).items()} if tables else {}


# ---- the COBOL side --------------------------------------------------------------------------------------------
def qualifier(case: dict[str, Any] | None) -> str | None:
    """The bind's QUALIFIER (the schema unqualified table names resolve to), or None: the user's own."""
    return ((case or {}).get("db2") or {}).get("qualifier")


def cobol_docker_args(case: dict[str, Any] | None = None) -> list[str]:
    """The COBOL step's container: on the Db2 network, the connection in its environment (not in run.sh)."""
    # DATETIMESTRINGFORMAT=ISO: a TIMESTAMP into a character host variable as Db2 for z/OS gives it with the ISO date
    # format (2011-08-22-12.13.01.000000), not the CLI's default (2011-08-22 12:13:01.000000)
    conn = (f"DATABASE={DATABASE};HOSTNAME={CONTAINER};PORT=50000;PROTOCOL=TCPIP;UID={USER};PWD={PASSWORD};"
            "DATETIMESTRINGFORMAT=ISO;")  # fmt: skip
    if qualifier(case):
        conn += f"CURRENTSCHEMA={qualifier(case)};"
    return ["--network", NETWORK, "-e", f"GGSQL_CONN={conn}"]


def cobol_env(stmts: str) -> str:
    return f"GGSQL_STMTS={stmts} DB2CODEPAGE=819 "


COBOL_LINK = "-I/opt/ibm/clidriver/include -L/opt/ibm/clidriver/lib -ldb2"


# ---- the Java side ---------------------------------------------------------------------------------------------
JCC = ("com.ibm.db2", "jcc", "11.5.9.0")

CONFIG = """package __PKG__;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

/** The equivalence harness's Db2 (tests/tools/equivalence_db2.py): the generated Db2 repositories' JDBC template on
 *  the database the COBOL side ran on; JPA and Spring Batch keep the project's own datasource. */
@Configuration
public class EquivalenceDb2Config {
    @Bean
    @Primary
    public NamedParameterJdbcTemplate equivalenceDb2Jdbc() {
        DriverManagerDataSource ds = new DriverManagerDataSource(
            System.getProperty("gitgalaxy.db2.url"), System.getProperty("gitgalaxy.db2.user"),
            System.getProperty("gitgalaxy.db2.password"));
        ds.setDriverClassName("com.ibm.db2.jcc.DB2Driver");
        return new NamedParameterJdbcTemplate(ds);
    }
}
"""


def patch_project(project: Path, package: str) -> None:
    """The project's copy: IBM's JDBC driver, and the Db2 repositories' template on the harness's Db2."""
    pom = project / "pom.xml"
    text = pom.read_text(encoding="utf-8")
    if JCC[1] not in text:
        dep = (f"        <dependency>\n            <groupId>{JCC[0]}</groupId>\n            <artifactId>{JCC[1]}</artifactId>\n"
               f"            <version>{JCC[2]}</version>\n        </dependency>\n")  # fmt: skip
        pom.write_text(text.replace("    </dependencies>", dep + "    </dependencies>", 1), encoding="utf-8")
    dest = project / "src" / "test" / "java" / Path(*package.split(".")) / "EquivalenceDb2Config.java"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(CONFIG.replace("__PKG__", package), encoding="utf-8")


def java_props(case: dict[str, Any] | None = None) -> str:
    schema = f":currentSchema={qualifier(case)};" if qualifier(case) else ""
    return (f"-Dgitgalaxy.db2.url=jdbc:db2://localhost:{PORT}/{DATABASE}{schema} -Dgitgalaxy.db2.user={USER} "
            f"-Dgitgalaxy.db2.password={PASSWORD}")  # fmt: skip
