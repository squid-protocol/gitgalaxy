"""#4269 -- EXEC SQL EXECUTE IMMEDIATE 'statement text', and PREPARE name FROM 'text' + EXECUTE name.

IBM Db2 for z/OS SQL Reference, EXECUTE IMMEDIATE statement: the statement string is prepared and executed in one step,
Db2 answering it (its SQLCODE lands in the SQLCA). Modelled here: a string-literal text of an INSERT ... VALUES, run as
written on the unit of work's connection (DetSql.savepoint's path). Refused by name, never guessed: a host variable as
the text, a searched UPDATE / DELETE / MERGE and an INSERT ... SELECT (each is +100 when it changes no row, a count the
connection does not give back), a parameter marker, DDL, and a CICS program. PREPARE FROM such a literal keeps the text
(the statement runs a no-op, SQLCODE 0); an EXECUTE of the name runs it, EXECUTE ... USING stays refused.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS.parent.parent))


class _Gen:
    cics = None

    def field_expr(self, ref):
        return "ca"


def _run(sql, line=7, gen=None):
    from gitgalaxy.tools.cobol_to_java.det.sql import Sql

    return Sql(gen or _Gen(), "P", None).command(f"EXEC SQL {sql} END-EXEC", line, "")


def test_a_literal_insert_values_runs_as_written_at_its_line():
    out = _run("EXECUTE IMMEDIATE 'INSERT INTO T VALUES (2, 1)'")
    assert out == ['DetSql.savepoint(ca, "P:7", "INSERT INTO T VALUES (2, 1)", CS);']


def test_a_doubled_quote_in_the_literal_is_one_quote_in_the_statement():
    out = _run("EXECUTE IMMEDIATE 'INSERT INTO T VALUES (3, ''IT''''S'')'")
    assert out == ["DetSql.savepoint(ca, \"P:7\", \"INSERT INTO T VALUES (3, 'IT''S')\", CS);"]


def test_the_statement_text_may_span_lines_and_keep_its_case():
    out = _run("EXECUTE   IMMEDIATE\n   'insert into t\n   values (1)'")
    assert out == ['DetSql.savepoint(ca, "P:7", "insert into t values (1)", CS);']


@pytest.mark.parametrize(
    "sql, why",
    [
        ("EXECUTE IMMEDIATE :STMT", "string literal"),
        ("EXECUTE IMMEDIATE 'INSERT INTO T VALUES (?, 1)'", "INSERT ... VALUES"),
        ("EXECUTE IMMEDIATE 'UPDATE T SET A = 1'", "INSERT ... VALUES"),
        ("EXECUTE IMMEDIATE 'DELETE FROM T'", "INSERT ... VALUES"),
        ("EXECUTE IMMEDIATE 'INSERT INTO T SELECT A FROM U'", "INSERT ... VALUES"),
        ("EXECUTE IMMEDIATE 'INSERT INTO T VALUES ((SELECT 1 FROM U))'", "INSERT ... VALUES"),
        ("EXECUTE IMMEDIATE 'CREATE TABLE T (A INT)'", "INSERT ... VALUES"),
        ("EXECUTE IMMEDIATE 'COMMIT'", "INSERT ... VALUES"),
        ("EXECUTE IMMEDIATE 'SELECT 1 FROM SYSIBM.SYSDUMMY1'", "INSERT ... VALUES"),
        ("EXECUTE STMT1 USING :A", "EXEC SQL EXECUTE"),
        ("EXECUTE STMT1", "EXEC SQL EXECUTE"),
        ("PREPARE STMT1 FROM :TXT", "EXEC SQL PREPARE"),
        ("PREPARE STMT1 INTO :SQLDA FROM 'INSERT INTO T VALUES (1)'", "EXEC SQL PREPARE"),
        ("PREPARE STMT1 FROM 'INSERT INTO T VALUES (?, 1)'", "INSERT ... VALUES"),
        ("PREPARE STMT1 FROM 'DELETE FROM T'", "INSERT ... VALUES"),
        ("PREPARE STMT1 FROM 'SELECT 1 FROM SYSIBM.SYSDUMMY1'", "INSERT ... VALUES"),
        ("PREPARE STMT1 FROM 'INSERT INTO T SELECT A FROM U'", "INSERT ... VALUES"),
    ],
)
def test_every_other_form_is_refused_by_name(sql, why):
    from gitgalaxy.tools.cobol_to_java.det.sql import SqlError

    with pytest.raises(SqlError, match=why):
        _run(sql)


def test_a_cics_program_is_refused():
    from gitgalaxy.tools.cobol_to_java.det.sql import SqlError

    gen = _Gen()
    gen.cics = SimpleNamespace()
    with pytest.raises(SqlError, match="CICS"):
        _run("EXECUTE IMMEDIATE 'INSERT INTO T VALUES (1)'", gen=gen)


def _prepared(*preps, execute="S1", at=9):
    """A Sql that has scanned `preps` ((name, line, text) PREPAREs), then EXECUTE `execute` at line `at`."""
    from gitgalaxy.tools.cobol_to_java.det.sql import Sql

    sq = Sql(_Gen(), "P", None)
    stmts = [SimpleNamespace(line=ln, text=f"EXEC SQL PREPARE {n} FROM '{t}' END-EXEC") for n, ln, t in preps]
    sq.scan_whenever(stmts)
    return sq.command(f"EXEC SQL EXECUTE {execute} END-EXEC", at, "")


INS = "INSERT INTO T VALUES (2, ''X'')"


def test_prepare_runs_a_no_op_and_execute_runs_the_text_at_its_own_line():
    out = _run("PREPARE S1 FROM 'INSERT INTO T VALUES (1)'", line=5)
    assert out == ['DetSql.savepoint(ca, "P:5", "VALUES 1", CS);']
    assert _prepared(("S1", 5, INS)) == ['DetSql.savepoint(ca, "P:9", "INSERT INTO T VALUES (2, \'X\')", CS);']


def test_a_name_may_be_prepared_twice_from_the_same_text_and_is_case_insensitive():
    out = _prepared(("s1", 4, INS), ("S1", 6, INS), execute="s1")
    assert len(out) == 1


@pytest.mark.parametrize(
    "preps, execute, at, why",
    [
        ([], "S1", 9, "no earlier PREPARE"),
        ([("S2", 5, INS)], "S1", 9, "no earlier PREPARE"),
        ([("S1", 12, INS)], "S1", 9, "no earlier PREPARE"),
        ([("S1", 5, INS), ("S1", 6, "INSERT INTO T VALUES (3)")], "S1", 9, "more than one literal"),
    ],
)
def test_an_execute_without_one_literal_prepare_before_it_is_refused(preps, execute, at, why):
    from gitgalaxy.tools.cobol_to_java.det.sql import SqlError

    with pytest.raises(SqlError, match=why):
        _prepared(*preps, execute=execute, at=at)


def test_prepare_and_execute_in_a_cics_program_are_refused():
    from gitgalaxy.tools.cobol_to_java.det.sql import SqlError

    gen = _Gen()
    gen.cics = SimpleNamespace()
    with pytest.raises(SqlError, match="CICS"):
        _run("PREPARE S1 FROM 'INSERT INTO T VALUES (1)'", gen=gen)


DYN = Path(__file__).resolve().parents[1] / "equivalence" / "db2" / "dynsql"


def test_dyndemo_translates_whole_with_the_whenever_after_a_dynamic_statement():
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    r = P.translate(DYN / "cbl" / "DYNDEMO.cbl", [DYN / "cbl"], "public class DyndemoService {\n}\n", "com.x", None,
                    DYN)  # fmt: skip
    # (the two SELECTs have no generated repository method without the forge's project: the e2e test below has one)
    holes = [h for h in r.stats["holes"] if "no generated Db2 repository method" not in h]
    assert holes == [], "\n".join(holes)
    assert r.java.count("DetSql.savepoint(") == 7  # 4 immediate, the PREPARE's no-op, 2 EXECUTEs
    assert "INSERT INTO GGDYN.DTAB VALUES (5, 'PREP')" in r.java.replace('\\"', '"')
    assert "INSERT INTO GGDYN.DTAB VALUES (3, 'IT''S')" in r.java.replace('\\"', '"')


def test_the_oracles_precompiler_runs_the_literal_as_written(tmp_path):
    import equivalence_sql as ES

    src = (DYN / "cbl" / "DYNDEMO.cbl").read_text(encoding="latin-1")
    out, table = ES.precompile(src, [DYN / "cbl"], DYN / "cbl" / "DYNDEMO.cbl", 1, "DYNDEMO")
    assert "EXECUTE S1" not in out and "PREPARE S1" not in out
    assert "Q INSERT INTO GGDYN.DTAB VALUES (3, 'IT''S')" in table.splitlines()
    assert table.count(" EXEC 0 0 ") == 7
    assert table.count("Q VALUES 1") == 1  # the PREPARE
    assert "IF SQLCODE < 0" in out  # the WHENEVER after the first dynamic statements applies to the last


@pytest.mark.parametrize(
    "stmt",
    ["EXECUTE IMMEDIATE :STMT", "EXECUTE IMMEDIATE 'DELETE FROM T'", "EXECUTE IMMEDIATE 'INSERT INTO T SELECT 1 FROM U'",
     "EXECUTE S1", "PREPARE S1 FROM 'SELECT 1'", "PREPARE S1 FROM :TXT"],
)  # fmt: skip
def test_the_oracles_precompiler_refuses_what_the_port_refuses(tmp_path, stmt):
    import equivalence_sql as ES

    src = (DYN / "cbl" / "DYNDEMO.cbl").read_text(encoding="latin-1")
    src = src.replace("EXECUTE IMMEDIATE\n               'INSERT INTO GGDYN.DTAB VALUES (2, ''DYN'')'", stmt, 1)
    with pytest.raises(ES.Unsupported, match="EXEC SQL"):
        ES.precompile(src, [DYN / "cbl"], DYN / "cbl" / "DYNDEMO.cbl", 1, "DYNDEMO")


# ---- the end-to-end proof on Db2: a synthetic estate (tests/equivalence/db2/dynsql) ---------------------------------
# No burned estate's program issues EXECUTE IMMEDIATE (the census, #4269), so DYNDEMO pins it: an insert, a quote
# inside the text, Db2's -803 and -204 for a duplicate key and a missing table, and the table compared at the end.
TRACED = """A INSERT          0
B ROW DYN       
C QUOTE IT'S      
D DUPLICATE       -803
F PREPARE          0
G EXECUTE          0
H AGAIN       -803
I MISSING TABLE       -204
"""


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL, Db2) and a JDK + Maven")
def test_dyndemo_det_port_proves_on_db2(tmp_path):
    import json
    import shutil

    pytest.importorskip("tree_sitter_language_pack")
    import det_port

    from gitgalaxy.tools.cobol_to_java.det import program as P

    estate = tmp_path / "estate"
    shutil.copytree(DYN, estate, ignore=shutil.ignore_patterns("seed.sql"))
    for argv in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "e"]):
        subprocess.run(["git", "-C", str(estate), *argv], check=True)  # noqa: S603, S607
    case = {"corpus": "dynsql-synthetic", "program": "DYNDEMO", "program_source": "cbl/DYNDEMO.cbl",
            "copy_dirs": [], "parm": None, "clock": "2026/10/08 10:00:00.00", "datasets": {},
            "db2": {"ddl": ["ddl/DTAB.ddl"], "seed": str(DYN / "seed.sql"), "compare": ["GGDYN.DTAB"],
                    "compare_sql": True}}  # fmt: skip
    (tmp_path / "case.json").write_text(json.dumps(case), encoding="utf-8")
    project = det_port.estate(estate, tmp_path / "translate")
    stub = (project / "src/main/java" / det_port.PKG_DIR / "service" / "DyndemoService.java").read_text("utf-8")
    r = P.translate(estate / "cbl/DYNDEMO.cbl", [estate / "cbl"], stub, det_port.PKG, P.estate_files(project), project)
    assert r.stats["holes"] == []
    port = tmp_path / "port"
    (port / "service").mkdir(parents=True)
    (port / "service" / f"{r.service}.java").write_text(r.java, encoding="utf-8")
    for rel, text in P.runtime_files(det_port.PKG, P.has_batch(project)).items():
        if "/cics/" not in rel:  # (an estate with no CICS has no cics package)
            (port / rel).parent.mkdir(parents=True, exist_ok=True)
            (port / rel).write_text(text, encoding="utf-8")
    keep = tmp_path / "proof"
    proc = subprocess.run([sys.executable, str(TOOLS / "equivalence.py"), "run", "dynsql", "--case-file",  # noqa: S603
                           str(tmp_path / "case.json"), "--corpus-dir", str(estate), "--port", str(port), "--keep",
                           str(keep), "--faults", "none", "--sql-faults", "none"],
                          capture_output=True, text=True, check=False)  # fmt: skip
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-3000:]
    report = json.loads((keep / "report.json").read_text(encoding="utf-8"))
    assert report["proven"] is True
    assert (keep / "cobol" / "stdout.txt").read_text(encoding="latin-1") == TRACED
