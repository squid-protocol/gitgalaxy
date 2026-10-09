"""The database of a Db2 equivalence case: one real Db2 (IBM Db2 Community Edition, in a container) that both sides
run their SQL on -- the COBOL side through ggsql.c and IBM's CLI driver, the Java side through JDBC.

A case declares it under "db2":

    "db2": {"ddl": ["app/.../ddl/TRNTYPE.ddl"],        the tables, created as the corpus's DDL says
            "seed": "@case/seed.sql",                 INSERTs: the tables' content before every run
            "compare": ["CARDDEMO.TRANSACTION_TYPE"], what each run leaves there, compared row by row
            "qualifier": "IBMUSER",                   the bind's QUALIFIER: the schema unqualified names resolve to
            "symbols": {"<DB2DBID>": "GENASA1"}}      install symbols in the DDL and seed, as the installer sets them

A seed may be a z/OS job too (GenApp's db2cre.jcl creates its tables and INSERTs their rows): its INSERTs are the
seed. Or "@generate" (#4507): rows generated from the tables' declarations -- columns, NOT NULL, keys, foreign keys
-- with each type's boundary values and NULLs (generate_rows); and "compare_sql": true compares, per task, what Db2
answered each side's statements: SQLCODE, SQLSTATE and rows (compare_outcomes). Every reset also restarts each compared table's identity column at its START WITH value, so both sides
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
import random
import re
import subprocess
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

import equivalence_common as common

CONTAINER = "gitgalaxy-db2"
NETWORK = "gitgalaxy-db2"
# #4733: pinned by digest, never a tag -- `:latest` moves under the proofs (the Db2 version, its code pages, its SQL
# behaviour) and a Db2 case's verdict could change with no change of ours. Moving it is a deliberate change: see "The Db2
# image is pinned" in docs/language_status/oracle_assumptions.md. tests/cobol_mainframe/test_db2_image_pin.py enforces it.
IMAGE = "icr.io/db2_community/db2@sha256:2de8151713c261843868c5c3411b57be6ae79d99d70a5b3022337836776bfda6"
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
        for _ in range(60):  # #4733: a fresh container (CI) is still creating GGDB when the first pool cases start
            if "Database code set" in ref:
                break
            time.sleep(10)
            ref = _db_cfg(DATABASE0)
        out = _instance(f"db2 create database {database} using codeset {ref['Database code set']} territory "
                        f"{ref['Database territory']} collate using {ref['Database collating sequence']} "
                        f"pagesize {ref['Database page size']}")  # fmt: skip
        if database not in listed():
            raise RuntimeError(f"Db2: CREATE DATABASE {database} failed: {out.strip()[-400:]}")


def _ensure_container() -> None:
    if not _docker("images", "-q", COBOL_IMAGE).strip():
        _docker("build", "-q", "-t", COBOL_IMAGE, "-f", str(DOCKERFILE), str(common.CASES), timeout=1800)
    import fcntl

    # #4733: several processes start together on a fresh container (CI): one starts it, the others wait for it
    lock = Path.home() / ".cache" / "gitgalaxy-db2-start.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        state = _docker("inspect", "-f", "{{.State.Running}}", CONTAINER, check=False).strip()
        if state in ("true", "false"):
            _check_container_image()
        if not _docker("network", "ls", "-q", "-f", f"name=^{NETWORK}$").strip():
            _docker("network", "create", NETWORK)
        if state == "false":
            _docker("start", CONTAINER)
        elif state != "true":
            _docker("run", "-d", "--name", CONTAINER, "--network", NETWORK, "--privileged", "-p", f"127.0.0.1:{PORT}:50000",
                    "-e", "LICENSE=accept", "-e", f"DB2INSTANCE={USER}", "-e", f"DB2INST1_PASSWORD={PASSWORD}",
                    "-e", f"DBNAME={DATABASE0}", "-e", "BLU=false", "-e", "ENABLE_ORACLE_COMPATIBILITY=false",
                    "-e", "UPDATEAVAIL=NO", "-e", "TO_CREATE_SAMPLEDB=false", "-e", "REPODB=false",
                    "-e", "IS_OSXFS=false", "-e", "PERSISTENT_HOME=false", "-e", "HADR_ENABLED=false", IMAGE)  # fmt: skip
    for _ in range(120):  # first start: several minutes. Ready = set up, and GGDB (the pool's reference) exists
        if "Setup has completed" in _docker("logs", CONTAINER, check=False) and "Database code set" in _db_cfg(
            DATABASE0
        ):
            return
        time.sleep(10)
    raise RuntimeError("Db2 did not come up")


def pinned_by_digest(image: str = IMAGE) -> bool:
    """#4733: the Db2 image is named by content digest (`name@sha256:<64 hex>`), not by a tag that can move."""
    return re.fullmatch(r"[a-z0-9][a-z0-9./_-]*@sha256:[0-9a-f]{64}", image) is not None


def _check_container_image() -> None:
    """An existing container must have been made from the pinned image: one left from `:latest` of another day would
    prove against a Db2 the pin does not name. Compared by image id, when the pinned image is on this host."""
    want = _docker("image", "inspect", "-f", "{{.Id}}", IMAGE, check=False).strip()
    have = _docker("inspect", "-f", "{{.Image}}", CONTAINER, check=False).strip()
    if want.startswith("sha256:") and have.startswith("sha256:") and want != have:
        raise RuntimeError(f"Db2: container {CONTAINER} was made from another image ({have[:19]}) than the pin "
                           f"{IMAGE} ({want[:19]}); `docker rm -f {CONTAINER}` and run again (#4733)")  # fmt: skip


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


def split_sql(text: str, name: str = "SQL") -> list[str]:
    """#4610: text's statements, split at ';' outside literals, with `--` line comments and `/* */` blocks removed
    (a comment becomes one space). Single quotes ('' escapes inside) and double-quoted identifiers hide everything.
    The loaders of both sides (ggsqlrun -f, EquivalenceRunTest) know only single quotes and ';', so what they get is
    this splitter's output (normalise_sql). Anything it cannot read the same way is refused by name, never guessed:
    an unterminated quote or block comment, and a `'` or `;` inside a double-quoted identifier."""
    stmts: list[str] = []
    cur: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        two = text[i : i + 2]
        if ch in "'\"":
            end = text.find(ch, i + 1)
            while end != -1 and text[end + 1 : end + 2] == ch:  # '' / "" is an escaped quote
                end = text.find(ch, end + 2)
            if end == -1:
                raise ValueError(f"{name}: unterminated {ch} literal at offset {i}")
            lit = text[i : end + 1]
            if ch == '"' and ("'" in lit or ";" in lit):
                raise ValueError(f"{name}: a ' or ; inside the quoted identifier {lit!r} is not supported")
            cur.append(lit)
            i = end + 1
        elif two == "--":
            end = text.find("\n", i)
            i = n if end == -1 else end  # the newline itself stays
            cur.append(" ")
        elif two == "/*":
            end = text.find("*/", i + 2)
            if end == -1:
                raise ValueError(f"{name}: unterminated /* comment at offset {i}")
            i = end + 2
            cur.append(" ")
        elif ch == ";":
            if "".join(cur).strip():
                stmts.append("".join(cur).strip())
            cur = []
            i += 1
        else:
            cur.append(ch)
            i += 1
    if "".join(cur).strip():
        stmts.append("".join(cur).strip())
    return stmts


def normalise_sql(text: str, name: str = "SQL") -> str:
    """split_sql's statements, each ended by ';' on its own line: the one form both loaders read alike."""
    return "".join(st + ";\n" for st in split_sql(text, name))


def reset_script(case: dict[str, Any], corpus: Path) -> str:
    """The SQL that resets the tables to the seed (ggsqlrun -f, and the Java side's EquivalenceRunTest): every table
    the seed fills or the case names, emptied (the seed's tables in the reverse of their INSERTs: children first),
    each one's identity column restarted, then the seed's INSERTs."""
    seed_sql = ""
    seed = case["db2"].get("seed")
    if seed == "@generate":  # #4507: rows generated from the tables' declarations
        seed_sql = generated_seed(case, corpus)
    elif seed:
        path = common._input_path(case, corpus, seed)
        symbols = case["db2"].get("symbols")
        if path.suffix.lower() == ".jcl":  # a job's INSERTs
            stmts = split_sql(ddl_text(path, symbols), seed)
            seed_sql = "".join(st + ";\n" for st in stmts if re.match(r"INSERT\b", st, re.I))
        else:
            seed_sql = path.read_text(encoding="latin-1")
            for k, v in (symbols or {}).items():
                seed_sql = seed_sql.replace(k, v)
            seed_sql = normalise_sql(seed_sql, seed)  # #4610: comments gone, so both loaders split alike
    seeded = list(dict.fromkeys(t.upper() for t in re.findall(r"INSERT\s+INTO\s+([A-Z0-9_.$#@]+)", seed_sql, re.I)))
    tables = [*reversed(seeded), *[t for t in _tables(case) if t.upper() not in seeded]]
    script = "".join(f"DELETE FROM {t};\n" for t in tables)
    _load_meta(tables)
    for t in tables:
        for c in [c for c, identity in _META.get(_key(t), []) if identity]:
            script += f"ALTER TABLE {t} ALTER COLUMN {c} RESTART;\n"
    return script + seed_sql


_FIELD_SEP = re.compile(r"(?<=\]|L)\|(?=\[|NULL)")


def split_row(line: str) -> list[str]:
    """A dump row's values ([value] or NULL each), split at the separators between them."""
    return _FIELD_SEP.split(line)


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
        elif a != b:  # #4507: field by field, by the table's columns (the whole line when it does not split)
            names, av, bv = head.split("|"), split_row(a), split_row(b)
            if len(av) == len(bv) == len(names):
                fields = [{"field": c, "cobol": x, "java": y} for c, x, y in zip(names, av, bv) if x != y]
            else:
                fields = [{"field": head, "cobol": a, "java": b}]
            diffs.append({"record": i + 1, "fields": fields})
    rows = max(len(a_rows), len(b_rows))
    return {"records": rows, "equal": rows - len(diffs), "diffs": diffs[:20], "layout_bytes": None}


def outputs(case: dict[str, Any]) -> dict[str, bytes]:
    tables = case["db2"].get("compare", [])
    return {f"DB2 {t}": data for t, data in dumps(case, tables).items()} if tables else {}


# ---- #4507: generated rows -------------------------------------------------------------------------------------
# A case whose seed is "@generate" gets its tables' rows from the declared structures -- the DDL's CREATE TABLE (or
# a DCLGEN's DECLARE TABLE), its keys (PRIMARY KEY, UNIQUE, CREATE UNIQUE INDEX) and foreign keys -- like #3804
# builds a VSAM file from its copybook:
#
#   "db2": {..., "seed": "@generate",
#           "generate": {"seed": 4507, "rows": 20, "dclgen": ["src/dcl/ACCOUNT.dcl"],
#                        "tables": {"IBMUSER.ACCOUNT": {"rows": 24,
#                                   "columns": {"ACCOUNT_SORTCODE": {"values": ["987654", "123456"], "every": 4},
#                                               "ACCOUNT_NUMBER": {"digits": true},
#                                               "ACCOUNT_CUSTOMER_NUMBER": {"from": "IBMUSER.CUSTOMER.CUSTNO"},
#                                               "ACCOUNT_OPENED": {"null": false}}}}}}
#
# Each column's values, in row order: its type's boundary values first, then NULL (a nullable column; each at a row of
# its own), then values in between --
#   CHAR(n)            n characters, blanks, a short value                  (the full length, and the empty value)
#   VARCHAR(n)         empty, n characters (at most 4000), a short value, one with trailing blanks
#   DECIMAL(p,s)       0, 1, the largest (10^(p-s) - 10^-s), its negative, the smallest fraction, its negative, halves
#   SMALLINT/INTEGER/BIGINT  0, 1, -1, the type's largest and smallest
#   DATE / TIME / TIMESTAMP  the type's first and last value (0001-01-01, 9999-12-31-23.59.59.999999), a leap day
# A key's columns (the primary key, a UNIQUE constraint or unique index) are unique together; a foreign key's
# columns take the parent's generated key (parents are generated first, added when the case does not name them);
# an identity column is left to Db2 (reset_script restarts it, so its values are START WITH, +INCREMENT ...).
# Rows always satisfy the table's constraints: what a program meets when a key is MISSING (+100 on SELECT / UPDATE /
# DELETE, -530 on an INSERT whose parent is not there) or DUPLICATE (-803 on an INSERT of a key already there) comes
# from the scenarios: a scenario_generate COMMAREA rule {"from": "SCHEMA.TABLE.COLUMN", "miss": 0.25} draws the
# key from the generated rows (a duplicate, for an INSERT) or, that share of the time, a value they do not hold.
_TYPE = re.compile(r"(?P<t>[A-Z]+(?:\s+(?:VARYING|PRECISION))?)\s*(?:\(\s*(?P<a>\d+)\s*(?:,\s*(?P<b>\d+)\s*)?\))?",
                   re.I)  # fmt: skip
_INT_RANGE = {"SMALLINT": 2**15, "INTEGER": 2**31, "INT": 2**31, "BIGINT": 2**63}


def _top_split(body: str) -> list[str]:
    """A parenthesised list's items: split at commas outside any nested parentheses and quotes."""
    out, depth, quote, cur = [], 0, False, []
    for ch in body:
        if ch == "'":
            quote = not quote
        elif not quote and ch == "(":
            depth += 1
        elif not quote and ch == ")":
            depth -= 1
        if ch == "," and depth == 0 and not quote:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        out.append("".join(cur).strip())
    return out


def _paren(text: str, start: int) -> tuple[str, int]:
    """The text inside the parenthesis opening at or after `start`, and the index after its close."""
    i = text.index("(", start)
    depth = 0
    for j in range(i, len(text)):
        depth += {"(": 1, ")": -1}.get(text[j], 0)
        if depth == 0:
            return text[i + 1 : j], j + 1
    raise ValueError(f"unbalanced parentheses in: {text[start : start + 80]!r}")


def _names(text: str) -> list[str]:
    return [re.split(r"\s+", c.strip())[0].strip('"').upper() for c in text.split(",") if c.strip()]


def _column(item: str) -> dict[str, Any] | None:
    """A column definition: name, type, length / precision / scale, nullable, identity, generated."""
    m = re.match(r'\s*("?[A-Z0-9_#@$]+"?)\s+(.*)$', item, re.I | re.S)
    if not m:
        return None
    name, rest = m.group(1).strip('"').upper(), m.group(2)
    t = _TYPE.match(rest)
    if not t:
        return None
    base = re.sub(r"\s+", " ", t.group("t").upper())
    base = {"CHARACTER": "CHAR", "CHAR VARYING": "VARCHAR", "CHARACTER VARYING": "VARCHAR", "DEC": "DECIMAL",
            "NUMERIC": "DECIMAL", "NUM": "DECIMAL", "INT": "INTEGER", "DOUBLE PRECISION": "DOUBLE"}.get(base, base)  # fmt: skip
    a, b = t.group("a"), t.group("b")
    col: dict[str, Any] = {"name": name, "type": base, "nullable": True, "identity": None, "generated": False}
    if base in ("CHAR", "VARCHAR", "GRAPHIC", "VARGRAPHIC"):
        col["length"] = int(a or 1)
    elif base == "DECIMAL":
        col["precision"], col["scale"] = int(a or 5), int(b or 0)
    tail = rest[t.end() :].upper()
    if re.search(r"\bNOT\s+NULL\b", tail) or re.search(r"\bPRIMARY\s+KEY\b", tail):
        col["nullable"] = False
    ident = re.search(r"\bGENERATED\s+(ALWAYS|BY\s+DEFAULT)\s+AS\s+IDENTITY\b", tail)
    if ident:
        start = re.search(r"\bSTART\s+WITH\s+(-?\d+)", tail)
        inc = re.search(r"\bINCREMENT\s+BY\s+(-?\d+)", tail)
        col["identity"] = {"start": int(start.group(1)) if start else 1, "increment": int(inc.group(1)) if inc else 1}
        col["nullable"] = False
    elif re.search(r"\bGENERATED\b", tail):  # a ROW CHANGE TIMESTAMP, an expression: Db2's to set
        col["generated"] = True
    col["inline_key"] = "primary" if re.search(r"\bPRIMARY\s+KEY\b", tail) else (
        "unique" if re.search(r"\bUNIQUE\b", tail) else None)  # fmt: skip
    ref = re.search(r"\bREFERENCES\s+([A-Z0-9_.$#@\"]+)\s*(\(([^)]*)\))?", tail)
    col["inline_ref"] = (ref.group(1).replace('"', ""), _names(ref.group(3)) if ref.group(3) else None) if ref else None
    return col


def parse_tables(text: str) -> dict[str, dict[str, Any]]:
    """{TABLE: {"columns": [...], "keys": [[column, ...], ...] (the primary key first), "fks": [{"columns",
    "parent", "parent_columns"}]}} from SQL text (ddl_text's): CREATE TABLE, DECLARE ... TABLE (a DCLGEN), ALTER
    TABLE ... ADD PRIMARY KEY / UNIQUE / FOREIGN KEY, CREATE UNIQUE INDEX."""
    tables: dict[str, dict[str, Any]] = {}
    for stmt in text.split(";"):
        s = stmt.strip()
        m = (re.match(r"CREATE\s+TABLE\s+([A-Z0-9_.$#@\"]+)\s*\(", s, re.I)
             or re.match(r"(?:EXEC\s+SQL\s+)?DECLARE\s+([A-Z0-9_.$#@\"]+)\s+TABLE\s*\(", s, re.I))  # fmt: skip
        if m:
            name = m.group(1).replace('"', "").upper()
            body, _ = _paren(s, m.end() - 1)
            t = tables.setdefault(name, {"columns": [], "keys": [], "fks": []})
            t["columns"] = []
            for item in _top_split(body):
                _constraint(t, item) or _add_column(t, item)
            continue
        m = re.match(r"CREATE\s+UNIQUE\s+INDEX\s+\S+\s+ON\s+([A-Z0-9_.$#@\"]+)\s*\(", s, re.I)
        if m:
            cols, _ = _paren(s, m.end() - 1)
            tables.setdefault(m.group(1).replace('"', "").upper(), {"columns": [], "keys": [], "fks": []})[
                "keys"].append(_names(cols))  # fmt: skip
            continue
        m = re.match(r"ALTER\s+TABLE\s+([A-Z0-9_.$#@\"]+)\s+ADD\s+(.*)$", s, re.I | re.S)
        if m:
            _constraint(tables.setdefault(m.group(1).replace('"', "").upper(), {"columns": [], "keys": [], "fks": []}),
                        m.group(2))  # fmt: skip
    for t in tables.values():  # unique sets once each, the primary key first
        seen: list[list[str]] = []
        for k in t["keys"]:
            if k not in seen:
                seen.append(k)
        t["keys"] = seen
    return tables


def _add_column(t: dict[str, Any], item: str) -> None:
    col = _column(item)
    if col is None:
        return
    t["columns"].append(col)
    if col["inline_key"] == "primary":
        t["keys"].insert(0, [col["name"]])
    elif col["inline_key"] == "unique":
        t["keys"].append([col["name"]])
    if col["inline_ref"]:
        t["fks"].append({"columns": [col["name"]], "parent": col["inline_ref"][0].upper(),
                         "parent_columns": col["inline_ref"][1]})  # fmt: skip


def _constraint(t: dict[str, Any], item: str) -> bool:
    """A table constraint (PRIMARY KEY / UNIQUE / FOREIGN KEY / CHECK, with or without CONSTRAINT name) taken into
    the table; False when the item is a column."""
    s = re.sub(r"^\s*CONSTRAINT\s+\S+\s+", "", item, flags=re.I)
    m = re.match(r"(PRIMARY\s+KEY|UNIQUE)\s*\(", s, re.I)
    if m:
        cols, _ = _paren(s, m.end() - 1)
        if m.group(1).upper().startswith("PRIMARY"):
            t["keys"].insert(0, _names(cols))
            for c in t["columns"]:
                if c["name"] in _names(cols):
                    c["nullable"] = False
        else:
            t["keys"].append(_names(cols))
        return True
    m = re.match(r"FOREIGN\s+KEY\s*(?:[A-Z0-9_#@$]+\s*)?\(", s, re.I)
    if m:
        cols, end = _paren(s, m.end() - 1)
        ref = re.match(r"\s*REFERENCES\s+([A-Z0-9_.$#@\"]+)\s*(\(([^)]*)\))?", s[end:], re.I)
        if ref:
            t["fks"].append({"columns": _names(cols), "parent": ref.group(1).replace('"', "").upper(),
                             "parent_columns": _names(ref.group(3)) if ref.group(3) else None})  # fmt: skip
        return True
    return bool(re.match(r"(CHECK\s*\(|PERIOD\b|LIKE\b)", s, re.I))


def declared_tables(case: dict[str, Any], corpus: Path) -> dict[str, dict[str, Any]]:
    """The case's tables as its DDL declares them (then its `generate.dclgen` members, for tables the DDL does not
    create: a DCLGEN's DECLARE TABLE has the columns, not the keys)."""
    spec = case["db2"]
    symbols = spec.get("symbols")
    tables: dict[str, dict[str, Any]] = {}
    for ddl in spec.get("ddl", []):
        for name, t in parse_tables(ddl_text(corpus / ddl, symbols)).items():
            old = tables.setdefault(name, {"columns": [], "keys": [], "fks": []})
            old["columns"] = t["columns"] or old["columns"]
            old["keys"] += [k for k in t["keys"] if k not in old["keys"]]
            old["fks"] += t["fks"]
    for dcl in (spec.get("generate") or {}).get("dclgen", []):
        text = (corpus / dcl).read_text(encoding="latin-1")
        sql = " ".join(
            re.findall(r"EXEC\s+SQL(.*?)END-EXEC", "\n".join(ln[6:72] for ln in text.splitlines()), re.S | re.I)
        )
        for name, t in parse_tables(sql.replace("END-EXEC", ";")).items():
            if not tables.get(name, {}).get("columns"):
                tables[name] = t
    return tables


def _qualify(name: str, tables: dict[str, Any], default: str | None) -> str:
    if name in tables or "." in name:
        return name
    return f"{default}.{name}" if default and f"{default}.{name}" in tables else name


def _edges(col: dict[str, Any]) -> list[Any]:
    """The column's boundary values (see the section's comment), in the order they are given to rows."""
    t = col["type"]
    if t == "CHAR":
        n = col["length"]
        return ["Z" * n, "", "A" * max(1, n // 2)]
    if t == "VARCHAR":
        n = col["length"]
        return ["", "Z" * min(n, 4000), "A" * max(1, min(n, 4000) // 2), ("B  " if n >= 3 else "B")]
    if t == "DECIMAL":
        p, s = col["precision"], col["scale"]
        top = Decimal(10) ** (p - s) - Decimal(1).scaleb(-s)
        tiny = Decimal(1).scaleb(-s) if s else Decimal(1)
        halves = [h for h in (Decimal("0.5"), Decimal("2.5")) if s and h <= top]
        return [Decimal(0), Decimal(1) if p > s else tiny, top, -top, tiny, -tiny, *halves, *[-h for h in halves]]
    if t in _INT_RANGE:
        r = _INT_RANGE[t]
        return [0, 1, -1, r - 1, -r]
    if t == "DATE":
        return ["0001-01-01", "9999-12-31", "2024-02-29"]
    if t == "TIME":
        return ["00.00.00", "23.59.59"]
    if t == "TIMESTAMP":
        return ["0001-01-01-00.00.00.000000", "9999-12-31-23.59.59.999999", "2024-02-29-12.00.00.000000"]
    if t in ("REAL", "FLOAT", "DOUBLE"):
        return [0, 1, -1]
    raise ValueError(f"column {col['name']}: type {t} is not generated (give it `values`)")


_ALNUM = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def _spread(rng: random.Random, col: dict[str, Any], digits: bool = False) -> Any:
    """A value in between the boundaries."""
    t = col["type"]
    if t in ("CHAR", "VARCHAR"):
        n = min(col["length"], 254)
        width = n if t == "CHAR" or rng.random() < 0.5 else rng.randint(1, n)
        return "".join(rng.choice("0123456789" if digits else _ALNUM) for _ in range(width))
    if t == "DECIMAL":
        p, s = col["precision"], col["scale"]
        whole = rng.randint(0, 10 ** min(p - s, 9) - 1) if p > s else 0
        v = Decimal(whole) + (Decimal(rng.randint(0, 10**s - 1)).scaleb(-s) if s else Decimal(0))
        return -v if rng.random() < 0.3 else v
    if t in _INT_RANGE:
        return rng.randint(-1000, 100000)
    y, mo, d = rng.randint(1990, 2030), rng.randint(1, 12), rng.randint(1, 28)
    if t == "DATE":
        return f"{y:04d}-{mo:02d}-{d:02d}"
    if t == "TIME":
        return f"{rng.randint(0, 23):02d}.{rng.randint(0, 59):02d}.{rng.randint(0, 59):02d}"
    if t == "TIMESTAMP":
        return (f"{y:04d}-{mo:02d}-{d:02d}-{rng.randint(0, 23):02d}.{rng.randint(0, 59):02d}."
                f"{rng.randint(0, 59):02d}.{rng.randint(0, 999999):06d}")  # fmt: skip
    return rng.randint(-1000, 1000)


def _fits(col: dict[str, Any], v: Any) -> Any:
    """A value as the column holds it (a `values` / `digits` value too long for the column is cut)."""
    if v is None:
        return None
    if col["type"] in ("CHAR", "VARCHAR"):
        return str(v)[: col["length"]]
    if col["type"] == "DECIMAL":
        return Decimal(str(v))
    return v


def literal(v: Any) -> str:
    """A generated value as an SQL literal."""
    if v is None:
        return "NULL"
    if isinstance(v, Decimal):
        return format(v, "f")
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def _gen_order(tables: dict[str, dict[str, Any]], wanted: list[str]) -> list[str]:
    """The tables to generate, each after its foreign keys' parents (a parent the case does not name is added)."""
    out: list[str] = []

    def visit(name: str, path: tuple[str, ...]) -> None:
        if name in out or name in path:
            return
        if name not in tables:
            raise ValueError(f"generated table {name}: no CREATE TABLE / DECLARE TABLE for it in the case's DDL")
        for fk in tables[name]["fks"]:
            if fk["parent"] != name:
                visit(fk["parent"], (*path, name))
        out.append(name)

    for w in wanted:
        visit(w, ())
    return out


def generate_rows(case: dict[str, Any], corpus: Path, tables: dict[str, dict[str, Any]] | None = None
                  ) -> tuple[list[tuple[str, dict[str, Any]]], dict[str, list[Any]]]:  # fmt: skip
    """([(table, {column: value})] in INSERT order, {TABLE.COLUMN: the values it holds}) -- deterministic (the
    generate block's seed); the pools are what a scenario's keys are drawn from (prepare_cics_case)."""
    gen = case["db2"].get("generate") or {}
    tables = tables if tables is not None else declared_tables(case, corpus)
    qual = qualifier(case)
    wanted = {_qualify(k.upper(), tables, qual): v for k, v in (gen.get("tables") or {}).items()}
    if not wanted:
        wanted = {_qualify(t.upper(), tables, qual): {} for t in _tables(case)}
    rows_out: list[tuple[str, dict[str, Any]]] = []
    pools: dict[str, list[Any]] = {}
    held: dict[str, list[dict[str, Any]]] = {}  # each generated table's rows as Db2 holds them (identities set)
    for name in _gen_order(tables, list(wanted)):
        t, spec = tables[name], wanted.get(name, {})
        rules = {k.upper(): v for k, v in (spec.get("columns") or {}).items()}
        unknown = set(rules) - {c["name"] for c in t["columns"]}
        if unknown:
            raise ValueError(f"{name}: no column {sorted(unknown)}")
        n = spec.get("rows", gen.get("rows", 20))
        rng = random.Random(f"{gen.get('seed', 0)}:{name}")
        cols = [c for c in t["columns"] if not c["generated"]]
        fks = [fk for fk in t["fks"] if fk["parent"] != name]  # (a self-reference: left to the case's rules)
        fk_cols = {c for fk in fks for c in fk["columns"]}
        idents = {c["name"]: c["identity"] for c in cols if c["identity"] and "values" not in rules.get(c["name"], {})}
        keys = [k for k in t["keys"] if not set(k) & set(idents)]
        key_cols = {c for k in keys for c in k}
        nullable = [c["name"] for c in cols if c["nullable"] and c["name"] not in key_cols]
        seen: list[set[tuple[Any, ...]]] = [set() for _ in keys]
        made: list[dict[str, Any]] = []
        idx = dict.fromkeys((c["name"] for c in cols), 0)  # each column's next value in its sequence
        attempts = 0
        while len(made) < n:
            attempts += 1
            if attempts > n * 50:
                raise ValueError(f"{name}: cannot make {n} rows with unique keys {keys}")
            row: dict[str, Any] = {}
            for fk in fks:  # a parent row each foreign key refers to (absent, now and then, when it may be)
                parent = held.get(fk["parent"]) or []
                if not parent:
                    raise ValueError(f"{name}: its parent {fk['parent']} has no generated rows")
                pcols = fk["parent_columns"] or tables[fk["parent"]]["keys"][0]
                optional = all(next(c for c in cols if c["name"] == x)["nullable"] for x in fk["columns"])
                p = None if optional and len(made) % 9 == 8 else rng.choice(parent)
                for x, pc in zip(fk["columns"], pcols):
                    row[x] = None if p is None else p[pc]
            for c in cols:
                cn, rule = c["name"], rules.get(c["name"], {})
                if cn in idents or (cn in fk_cols and not rule):
                    continue
                i = idx[cn]
                if "values" in rule:  # `every` k: the value changes each k rows
                    v = rule["values"][(len(made) // rule.get("every", 1)) % len(rule["values"])]
                elif "from" in rule:
                    pool = pools.get(rule["from"].upper())
                    if not pool:
                        raise ValueError(f"{name}.{cn}: nothing generated yet for {rule['from']}")
                    v = rng.choice(pool)
                elif rule.get("digits"):  # a CHAR column that holds a number (an account number kept as text)
                    v = "".join(rng.choice("0123456789") for _ in range(c.get("length", 1)))
                else:
                    edges = [] if rule.get("edges") is False else _edges(c)
                    # NULL after the boundaries, each nullable column at a row of its own (one NULL at a time:
                    # a program that tests its columns one by one meets each test alone)
                    null_at = len(edges) + nullable.index(cn) if cn in nullable and rule.get("null", True) else -1
                    # the boundaries in turn, each column from its own place in its list (so one row is not
                    # every column's first boundary), then NULL, then values in between
                    j = cols.index(c)
                    v = (edges[(i + j) % len(edges)] if i < len(edges)
                         else (None if i == null_at else _spread(rng, c)))  # fmt: skip
                row[cn] = _fits(c, v)
            tups = [tuple(row.get(c) for c in k) for k in keys]
            if any(tup in s for tup, s in zip(tups, seen)):
                for c in key_cols:  # the next attempt: in-between values for the key's columns
                    idx[c] = max(idx[c], 99)
                continue
            for tup, s in zip(tups, seen):
                s.add(tup)
            for c in cols:
                idx[c["name"]] += 1
            made.append(row)
        held[name] = []
        for r, row in enumerate(made):
            rows_out.append((name, row))
            full = {**row, **{c: i["start"] + r * i["increment"] for c, i in idents.items()}}
            held[name].append(full)
            for c in cols:
                if full.get(c["name"]) is not None:
                    pools.setdefault(f"{name}.{c['name']}", []).append(full[c["name"]])
    return rows_out, pools


_GENERATED: dict[str, str] = {}  # a db2 section (as JSON) -> its generated seed, made once a process


def generated_seed(case: dict[str, Any], corpus: Path) -> str:
    """The generated rows as the seed's INSERTs, one a row (identity columns left to Db2). Made once a process (the
    batch side's Java runs reset the tables with no corpus at hand: create() made it first)."""
    import json

    key = json.dumps(case["db2"], sort_keys=True)
    if key not in _GENERATED:
        rows, _ = generate_rows(case, corpus)
        _GENERATED[key] = "".join(
            f"INSERT INTO {t} ({', '.join(r)}) VALUES ({', '.join(literal(v) for v in r.values())});\n" for t, r in rows
        )
    return _GENERATED[key]


# ---- #4507: what Db2 answered each side -------------------------------------------------------------------------
# A case with "compare_sql": true in its db2 section compares, per task, the statements each side ran and what Db2
# answered them, in order: the verb, SQLCODE, SQLSTATE and the rows (a query's rows read -- compared when both sides
# read to its end -- or an INSERT / UPDATE / DELETE's count). The COBOL side's come from ggsql.c ($GGSQL_OUTCOMES),
# the Java side's from its JDBC connections (EquivalenceDb2Config). What a COBOL program's host variables add after
# Db2 answered -- -304 (a number too big for its host variable), -305 (a NULL with no indicator), -811 (a second row
# for a SELECT INTO) -- is the stub's, not Db2's: the Java side has no host variables, so those count as the row Db2
# returned (the program's reaction to them is compared through its outputs). COMMIT / ROLLBACK are not statements
# the Java side runs (they end the harness's unit of work, #4269), so they are not compared, nor a FETCH of a cursor
# they closed (-501, the stub's); a warning (SQLCODE > 0 other than +100) counts as success.
_ASSIGN = (-304, -305)


def _settle(e: dict[str, Any]) -> dict[str, Any]:
    """An outcome as compared: a query that returned nothing +100 / 02000; success 0 / 00000."""
    code = e["sqlcode"]
    if code > 0 and code != 100:
        code = 0
    if code >= 0 and e["kind"] == "Q" and e["ended"] and e["rows"] == 0:
        code = 100
    elif code >= 0 and e["kind"] == "U" and e["verb"] in ("INSERT", "UPDATE", "DELETE", "MERGE") and e["rows"] == 0:
        code = 100
    elif code == 100 and e["kind"] == "Q" and e["rows"]:
        code = 0
    state = {0: "00000", 100: "02000"}.get(code, e["sqlstate"])
    rows = e["rows"] if code >= 0 and (e["kind"] == "U" or e["ended"]) else None
    return {"verb": e["verb"], "sqlcode": code, "sqlstate": state, "rows": rows}


def cobol_outcomes(text: str) -> list[dict[str, Any]]:
    """ggsql.c's outcome log (one line a statement) as the statements Db2 answered, cursors folded into their
    query (OPEN, its FETCHes, CLOSE: one query, its rows those FETCHed)."""
    out: list[dict[str, Any]] = []
    open_q: dict[str, dict[str, Any]] = {}
    for ln in text.splitlines():
        parts = ln.split()
        if len(parts) != 7:
            continue
        kind, cursor, verb, code, state, rows, fault = parts[0], parts[1], parts[2], int(parts[3]), parts[4], int(
            parts[5]), parts[6] == "1"  # fmt: skip
        if kind in ("COMMIT", "ROLLBACK", "CLOSE"):
            continue
        if kind == "OPEN":
            e = {"verb": verb, "sqlcode": code, "sqlstate": state, "rows": 0, "ended": code < 0, "kind": "Q",
                 "fault": fault}  # fmt: skip
            out.append(e)
            open_q[cursor] = e
        elif kind == "FETCH":
            e = open_q.get(cursor)
            if e is None:
                continue
            if code == -501 and not fault:  # #4269: the stub's "not open" -- the program's COMMIT / ROLLBACK closed
                del open_q[cursor]  # the cursor (ggsql.c), not Db2's answer to the query: what it read stays
                continue
            if code == 100:
                e["ended"] = True
            elif code >= 0 or code in _ASSIGN:
                e["rows"] += 1
            else:
                e["sqlcode"], e["sqlstate"], e["ended"] = code, state, True
        elif kind == "SELECT1":
            if code in _ASSIGN:
                code, state, n = 0, "00000", 1
            elif code == -811:
                code, state, n = 0, "00000", 2  # (the Java side reads every row: at least 2)
            else:
                n = 1 if 0 <= code != 100 else 0
            out.append({"verb": verb, "sqlcode": code, "sqlstate": state, "rows": n, "ended": True, "kind": "Q",
                        "fault": fault})  # fmt: skip
        else:  # EXEC
            out.append({"verb": verb, "sqlcode": code, "sqlstate": state, "rows": rows, "ended": True, "kind": "U",
                        "fault": fault})  # fmt: skip
    return [_settle(e) for e in out]


def java_outcomes(text: str) -> list[dict[str, Any]]:
    """EquivalenceDb2Config's log as the statements Db2 answered."""
    out = []
    for ln in text.splitlines():
        parts = ln.split()
        if len(parts) != 6:
            continue
        verb, code, state, rows, ended, kind = parts
        out.append(_settle({"verb": verb, "sqlcode": int(code), "sqlstate": state, "rows": int(rows),
                            "ended": ended == "1" or kind == "U", "kind": kind}))  # fmt: skip
    return out


def compare_outcomes(cobol: list[dict[str, Any]], java: list[dict[str, Any]]) -> dict[str, Any]:
    """The two sides' statements paired in order, field by field: {statements, equal, diffs, cobol, java}. Rows are
    compared when both sides know them (a query read to its end on both sides)."""
    diffs = []
    n = max(len(cobol), len(java))
    for i in range(n):
        a = cobol[i] if i < len(cobol) else None
        b = java[i] if i < len(java) else None
        if a is None or b is None:
            diffs.append({"statement": i + 1, "record": i + 1, "missing": "cobol" if a is None else "java",
                          "cobol": a, "java": b})  # fmt: skip
            continue
        fields = [{"field": f, "cobol": a[f], "java": b[f]} for f in ("verb", "sqlcode", "sqlstate")
                  if a[f] != b[f]]  # fmt: skip
        if a["rows"] is not None and b["rows"] is not None and a["rows"] != b["rows"]:
            fields.append({"field": "rows", "cobol": a["rows"], "java": b["rows"]})
        if fields:
            diffs.append({"statement": i + 1, "record": i + 1, "fields": fields})
    # (`records` / `record` too: a batch report's outputs are read as record diffs, a statement a record)
    return {"statements": n, "records": n, "equal": n - len(diffs), "diffs": diffs[:20], "cobol": cobol, "java": java}


def generated_pools(case: dict[str, Any], corpus: Path) -> dict[str, list[Any]]:
    """{TABLE.COLUMN: values} of a case whose seed is generated; {} otherwise."""
    if (case.get("db2") or {}).get("seed") != "@generate":
        return {}
    return generate_rows(case, corpus)[1]


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

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

/** The equivalence harness's Db2 (tests/tools/equivalence_db2.py): the generated Db2 repositories' JDBC template on
 *  the database the COBOL side ran on; JPA and Spring Batch keep the project's own datasource.
 *
 *  #4507: while the system property gitgalaxy.db2.sqllog names a file, every statement run through this template's
 *  connections is logged there as Db2 answered it -- `verb sqlcode sqlstate rows ended kind` (kind Q: a query, its
 *  rows those the port read, ended when it read past the last; U: an update count) -- what the COBOL side's
 *  $GGSQL_OUTCOMES holds for the same task (equivalence_db2.compare_outcomes). */
@Configuration
public class EquivalenceDb2Config {
    static final class Outcome {
        final String verb;
        final char kind;
        int code;
        String state = "00000";
        long rows;
        boolean ended;

        Outcome(String verb, char kind) {
            this.verb = verb;
            this.kind = kind;
        }
    }

    static final List<Outcome> LOG = new ArrayList<>();
    static String logPath;

    static synchronized Outcome start(String sql, char kind) {
        String path = System.getProperty("gitgalaxy.db2.sqllog");
        if (path == null || path.isEmpty()) {
            return null;
        }
        if (!path.equals(logPath)) {
            LOG.clear();
            logPath = path;
        }
        String s = sql == null ? "" : sql.strip();
        while (s.startsWith("(")) {
            s = s.substring(1).strip();
        }
        int end = 0;
        while (end < s.length() && !Character.isWhitespace(s.charAt(end)) && s.charAt(end) != '(') {
            end++;
        }
        Outcome o = new Outcome(end == 0 ? "-" : s.substring(0, end).toUpperCase(Locale.ROOT), kind);
        LOG.add(o);
        return o;
    }

    static synchronized void flush() {
        if (logPath == null) {
            return;
        }
        StringBuilder b = new StringBuilder();
        for (Outcome o : LOG) {
            b.append(o.verb).append(' ').append(o.code).append(' ').append(o.state).append(' ').append(o.rows)
                    .append(' ').append(o.ended ? 1 : 0).append(' ').append(o.kind).append('\\n');
        }
        try {
            Files.writeString(Path.of(logPath), b.toString(), StandardCharsets.ISO_8859_1);
        } catch (java.io.IOException e) {
            throw new java.io.UncheckedIOException(e);
        }
    }

    static Object call(Object target, Method m, Object[] a) throws Throwable {
        try {
            return m.invoke(target, a);
        } catch (InvocationTargetException e) {
            throw e.getCause();
        }
    }

    static void failed(Outcome o, java.sql.SQLException e) {
        if (o != null) {
            o.code = e.getErrorCode();
            o.state = e.getSQLState() == null ? "-----" : e.getSQLState();
            flush();
        }
    }

    static java.sql.ResultSet rows(java.sql.ResultSet rs, Outcome o) {
        if (o == null) {
            return rs;
        }
        return (java.sql.ResultSet) Proxy.newProxyInstance(EquivalenceDb2Config.class.getClassLoader(),
                new Class<?>[] {java.sql.ResultSet.class}, (p, m, a) -> {
                    try {
                        Object r = call(rs, m, a);
                        if (m.getName().equals("next")) {
                            if (Boolean.TRUE.equals(r)) {
                                o.rows++;
                            } else {
                                o.ended = true;
                            }
                            flush();
                        }
                        return r;
                    } catch (java.sql.SQLException e) {
                        failed(o, e);
                        throw e;
                    }
                });
    }

    static Object statement(java.sql.Statement st, String sql, Class<?> type) {
        Outcome[] last = new Outcome[1];
        return Proxy.newProxyInstance(EquivalenceDb2Config.class.getClassLoader(), new Class<?>[] {type},
                (p, m, a) -> {
                    String n = m.getName();
                    if (n.equals("getResultSet")) {
                        return rows((java.sql.ResultSet) call(st, m, a), last[0]);
                    }
                    if (!n.startsWith("execute")) {
                        return call(st, m, a);
                    }
                    String text = sql != null ? sql : (a != null && a.length > 0 && a[0] instanceof String s ? s : "");
                    Outcome o = start(text, n.equals("executeQuery") ? 'Q' : 'U');
                    last[0] = o;
                    try {
                        Object r = call(st, m, a);
                        if (o == null) {
                            return r;
                        }
                        if (r instanceof java.sql.ResultSet rs) {
                            return rows(rs, o);
                        }
                        if (r instanceof Integer k) {
                            o.rows = k;
                        } else if (r instanceof Long k) {
                            o.rows = k;
                        } else if (r instanceof int[] ks) {
                            for (int k : ks) {
                                o.rows += Math.max(k, 0);
                            }
                        } else if (Boolean.FALSE.equals(r)) {
                            o.rows = st.getUpdateCount();
                        }
                        flush();
                        return r;
                    } catch (java.sql.SQLException e) {
                        failed(o, e);
                        throw e;
                    }
                });
    }

    static java.sql.Connection logged(java.sql.Connection c) {
        return (java.sql.Connection) Proxy.newProxyInstance(EquivalenceDb2Config.class.getClassLoader(),
                new Class<?>[] {java.sql.Connection.class}, (p, m, a) -> {
                    Object r = call(c, m, a);
                    String n = m.getName();
                    if (n.equals("prepareStatement") && r instanceof java.sql.PreparedStatement ps) {
                        return statement(ps, (String) a[0], java.sql.PreparedStatement.class);
                    }
                    if (n.equals("prepareCall") && r instanceof java.sql.CallableStatement cs) {
                        return statement(cs, (String) a[0], java.sql.CallableStatement.class);
                    }
                    if (n.equals("createStatement") && r instanceof java.sql.Statement st) {
                        return statement(st, null, java.sql.Statement.class);
                    }
                    return r;
                });
    }

    @Bean
    @Primary
    public NamedParameterJdbcTemplate equivalenceDb2Jdbc() {
        DriverManagerDataSource ds = new DriverManagerDataSource(
            System.getProperty("gitgalaxy.db2.url"), System.getProperty("gitgalaxy.db2.user"),
            System.getProperty("gitgalaxy.db2.password")) {
            @Override
            public java.sql.Connection getConnection() throws java.sql.SQLException {
                return logged(super.getConnection());
            }

            @Override
            public java.sql.Connection getConnection(String user, String password) throws java.sql.SQLException {
                return logged(super.getConnection(user, password));
            }
        };
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
