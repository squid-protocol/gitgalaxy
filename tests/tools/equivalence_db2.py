"""The database of a Db2 equivalence case: one real Db2 (IBM Db2 Community Edition, in a container) that both sides
run their SQL on -- the COBOL side through ggsql.c and IBM's CLI driver, the Java side through JDBC.

A case declares it under "db2":

    "db2": {"ddl": ["app/.../ddl/TRNTYPE.ddl"],        the tables, created as the corpus's DDL says
            "seed": "@case/seed.sql",                 INSERTs: the tables' content before every run
            "compare": ["CARDDEMO.TRANSACTION_TYPE"]} what each run leaves there, compared row by row

Before each run (the COBOL step, every Java run, every fault run) the compared and seeded tables are emptied and
the seed loaded again. A table is dumped as text, one row a line, ordered by every column: each value between
brackets as Db2 renders it in character form (VARCHAR() of the column: a string with its trailing blanks, a number
as its decimal digits), NULL as NULL -- so a length or a trailing blank that differs is a difference.

The container is started on first use and left running (`docker rm -f gitgalaxy-db2` stops it)."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

import equivalence_common as common

CONTAINER = "gitgalaxy-db2"
NETWORK = "gitgalaxy-db2"
IMAGE = "icr.io/db2_community/db2:latest"
COBOL_IMAGE = "gitgalaxy-gnucobol-db2:3"
DATABASE = "GGDB"
USER, PASSWORD = "db2inst1", "ggdb2pass"  # a local, throwaway test database
PORT = 50000
DOCKERFILE = common.CASES / "gnucobol-db2.Dockerfile"
STUB = common.CASES / "db2" / "ggsql.c"
RUNNER = common.CASES / "db2" / "ggsqlrun.c"


_LOCK = None


def hold_lock() -> None:
    """The Db2 to this process until it ends (an exclusive lock; another Db2 case waits for it)."""
    global _LOCK
    import fcntl

    if _LOCK is None:
        path = Path.home() / ".cache" / "gitgalaxy-db2.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        _LOCK = path.open("w")
        fcntl.flock(_LOCK, fcntl.LOCK_EX)


def _docker(*args: str, check: bool = True, timeout: int = 600, inp: str | None = None) -> str:
    proc = subprocess.run(["docker", *args], capture_output=True, text=True, check=False, timeout=timeout,  # noqa: S603, S607
                          input=inp)  # fmt: skip
    if check and proc.returncode != 0:
        raise RuntimeError(f"docker {' '.join(args[:3])}: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout


def ensure() -> None:
    """The Db2 container running, and the COBOL side's image built."""
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
                "-e", f"DBNAME={DATABASE}", "-e", "BLU=false", "-e", "ENABLE_ORACLE_COMPATIBILITY=false",
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


def create(case: dict[str, Any], corpus: Path) -> None:
    """The case's tables, dropped and created again from its DDL."""
    ensure()
    for t in _tables(case):
        _clp(f"DROP TABLE {t};", check=False)
    for ddl in case["db2"].get("ddl", []):
        _clp((corpus / ddl).read_text(encoding="latin-1"))


def reset(case: dict[str, Any], corpus: Path) -> None:
    """The tables as the seed has them: emptied, the seed's INSERTs run, committed."""
    _clp(reset_script(case, corpus).rstrip() + "\nCOMMIT;")


def columns(table: str) -> list[str]:
    schema, _, name = table.upper().rpartition(".")
    _, cols = _clp(f"SELECT COLNAME FROM SYSCAT.COLUMNS WHERE TABSCHEMA = '{schema or USER.upper()}' "
                   f"AND TABNAME = '{name}' ORDER BY COLNO;")  # fmt: skip
    names = [c.strip() for c in cols.splitlines() if c.strip() and not c.startswith("SELECT")]
    if not names:
        raise RuntimeError(f"Db2: no table {table}")
    return names


def dump_query(table: str, names: list[str]) -> str:
    """The query a dump runs: one column, each row's values rendered and joined."""
    expr = " || '|' || ".join(f"COALESCE('[' || VARCHAR({c}) || ']', 'NULL')" for c in names)
    return f"SELECT {expr} FROM {table} ORDER BY {', '.join(names)}"


def dump(case: dict[str, Any], table: str) -> bytes:
    """One table's rows as text (see the module's docstring)."""
    names = columns(table)
    _, rows = _clp(dump_query(table, names) + ";")
    lines = [ln.rstrip() for ln in rows.splitlines() if ln.startswith("[") or ln.startswith("NULL")]  # (CLP pads rows)
    return ("|".join(names) + "\n" + "\n".join(lines) + "\n").encode("latin-1")


def reset_script(case: dict[str, Any], corpus: Path) -> str:
    """The SQL that resets the tables to the seed (ggsqlrun -f, and the Java side's EquivalenceRunTest)."""
    script = "".join(f"DELETE FROM {t};\n" for t in _tables(case))
    seed = case["db2"].get("seed")
    if seed:
        script += common._input_path(case, corpus, seed).read_text(encoding="latin-1")
    return script


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
    return {f"DB2 {t}": dump(case, t) for t in case["db2"].get("compare", [])}


# ---- the COBOL side --------------------------------------------------------------------------------------------
def cobol_docker_args() -> list[str]:
    """The COBOL step's container: on the Db2 network, the connection in its environment (not in run.sh)."""
    conn = f"DATABASE={DATABASE};HOSTNAME={CONTAINER};PORT=50000;PROTOCOL=TCPIP;UID={USER};PWD={PASSWORD};"
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


def java_props() -> str:
    return (f"-Dgitgalaxy.db2.url=jdbc:db2://localhost:{PORT}/{DATABASE} -Dgitgalaxy.db2.user={USER} "
            f"-Dgitgalaxy.db2.password={PASSWORD}")  # fmt: skip
