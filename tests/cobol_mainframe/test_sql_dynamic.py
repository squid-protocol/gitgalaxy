"""#4269 -- EXEC SQL EXECUTE IMMEDIATE 'statement text', and PREPARE name FROM 'text' + EXECUTE name.

IBM Db2 for z/OS SQL Reference, EXECUTE IMMEDIATE statement: the statement string is prepared and executed in one step,
Db2 answering it (its SQLCODE lands in the SQLCA). Modelled here: a string-literal text of an INSERT ... VALUES, run as
written on the unit of work's connection (DetSql.savepoint's path). Refused by name, never guessed: a host variable as
the text, a searched UPDATE / DELETE / MERGE and an INSERT ... SELECT (each is +100 when it changes no row, a count the
connection does not give back), a parameter marker in EXECUTE IMMEDIATE, DDL, and a CICS program. PREPARE FROM such a
literal keeps the text (the statement runs a no-op, SQLCODE 0); an EXECUTE of the name runs it. Its parameter markers
are bound by EXECUTE ... USING :H [:IND], ...: the port writes each value into the text as a literal, Db2 binds it.
"""

from __future__ import annotations

import os
import re
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
        ("DESCRIBE STMT1 INTO :SQLDA", "EXEC SQL DESCRIBE: .*SQLDA"),
        ("CONNECT TO LOC1", "EXEC SQL CONNECT: .*location switch"),
        ("CONNECT RESET", "EXEC SQL CONNECT: .*one connection"),
        ("CALL PROC1 (:A)", "EXEC SQL CALL: .*stored procedure"),
        ("SET CURRENT SQLID = 'X'", "EXEC SQL SET: .*SET CURRENT"),
        ("EXECUTE STMT1 USING :A", "EXEC SQL EXECUTE"),
        ("EXECUTE STMT1 USING DESCRIPTOR :SQLDA", "EXEC SQL EXECUTE"),
        ("EXECUTE STMT1", "EXEC SQL EXECUTE"),
        ("PREPARE STMT1 FROM :TXT", "EXEC SQL PREPARE"),
        ("PREPARE STMT1 INTO :SQLDA FROM 'INSERT INTO T VALUES (1)'", "EXEC SQL PREPARE"),
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
    assert r.java.count("DetSql.savepoint(") == 11  # 4 immediate, 2 PREPARE no-ops, 2 EXECUTEs, 3 EXECUTE ... USING
    assert "INSERT INTO GGDYN.DTAB VALUES (" in r.java and "instanceof String" in r.java
    assert "INSERT INTO GGDYN.DTAB VALUES (5, 'PREP')" in r.java.replace('\\"', '"')
    assert "INSERT INTO GGDYN.DTAB VALUES (3, 'IT''S')" in r.java.replace('\\"', '"')


def test_the_oracles_precompiler_runs_the_literal_as_written(tmp_path):
    import equivalence_sql as ES

    src = (DYN / "cbl" / "DYNDEMO.cbl").read_text(encoding="latin-1")
    out, table = ES.precompile(src, [DYN / "cbl"], DYN / "cbl" / "DYNDEMO.cbl", 1, "DYNDEMO")
    assert "EXECUTE S1" not in out and "PREPARE S1" not in out
    assert "Q INSERT INTO GGDYN.DTAB VALUES (3, 'IT''S')" in table.splitlines()
    assert table.count(" EXEC 0 0 ") == 8
    assert table.count(" EXEC 2 0 ") == 3  # the EXECUTE ... USING: two host variables each
    assert table.count("Q VALUES 1") == 2  # the PREPAREs
    assert "IF SQLCODE < 0" in out  # the WHENEVER after the first dynamic statements applies to the last


@pytest.mark.parametrize(
    "stmt",
    ["EXECUTE IMMEDIATE :STMT", "EXECUTE IMMEDIATE 'DELETE FROM T'", "EXECUTE IMMEDIATE 'INSERT INTO T SELECT 1 FROM U'",
     "EXECUTE S1", "PREPARE S1 FROM 'SELECT 1'", "PREPARE S1 FROM :TXT",
     "EXECUTE IMMEDIATE 'INSERT INTO T VALUES (?, 1)'"],
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
J USING          0
K BOUND BOUND'S   
L USING AGAIN       -803
M NULL NAME       -407
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


# ---- EXECUTE name USING :H [:IND], ...: the parameter markers of a prepared INSERT (#4269) --------------------------
class _Host(_Gen):
    """Host variables WS-ID (numeric), WS-NAME (character), WS-IND (the indicator) and a group, by name."""

    n = 0

    def tmpname(self, base):
        self.n += 1
        return f"{base}{self.n}"

    def resolve(self, ref):
        if ref.name == "WS-GRP":
            return SimpleNamespace(name="WS-GRP", pic=None, occurs=1, children=[
                SimpleNamespace(name="A", pic="X", occurs=1, children=[], category="ALPHANUMERIC", level=5),
                SimpleNamespace(name="B", pic="X", occurs=1, children=[], category="ALPHANUMERIC", level=5)],
                category="GROUP", level=1, usage=None, parent=None)  # fmt: skip
        cat = "NUMERIC" if ref.name in ("WS-ID", "WS-IND") else "ALPHANUMERIC"
        return SimpleNamespace(name=ref.name, pic="9", occurs=1, children=[], category=cat, level=1, usage=None,
                               parent=None)  # fmt: skip


def _using(text, using, gen=None):
    from gitgalaxy.tools.cobol_to_java.det.sql import Sql

    sq = Sql(gen or _Host(), "P", None)
    sq.scan_whenever([SimpleNamespace(line=3, text=f"EXEC SQL PREPARE S1 FROM '{text}' END-EXEC")])
    return sq.command(f"EXEC SQL EXECUTE S1 {using} END-EXEC", 9, "")


def test_using_writes_each_host_value_into_its_marker():
    out = _using("INSERT INTO T VALUES (?, ?)", "USING :WS-ID, :WS-NAME")
    assert out[0].startswith("Object ") and out[1].startswith("Object ")
    call = out[2]
    assert call.startswith('DetSql.savepoint(ca, "P:9", "INSERT INTO T VALUES (" + (')
    assert call.count("instanceof String") == 2 and call.endswith('+ ")", CS);')
    assert "DetSql.numIn(ca, CS)" in out[0] and "DetSql.charIn(ca, CS)" in out[1]


def test_an_indicator_makes_the_value_null():
    out = _using("INSERT INTO T VALUES (?, ?)", "USING :WS-ID :WS-IND, :WS-NAME")
    assert "DetSql.orNull(DetSql.numIn(ca, CS), ca, CS)" in out[0]


def test_a_question_mark_inside_a_string_literal_is_not_a_marker():
    out = _using("INSERT INTO T VALUES (''WHY?'', ?)", "USING :WS-ID")
    assert len(out) == 2 and "WHY?" in out[1]
    assert _using("INSERT INTO T VALUES (''WHY?'')", "")[0].startswith("DetSql.savepoint(")


@pytest.mark.parametrize(
    "text, using, why",
    [
        ("INSERT INTO T VALUES (?, ?)", "USING :WS-ID", "2 parameter markers, 1 USING"),
        ("INSERT INTO T VALUES (?)", "USING :WS-ID, :WS-NAME", "1 parameter markers, 2 USING"),
        ("INSERT INTO T VALUES (?)", "", "1 parameter markers, 0 USING"),
        ("INSERT INTO T VALUES (1)", "USING :WS-ID", "0 parameter markers, 1 USING"),
        ("INSERT INTO T VALUES (?)", "USING WS-ID", "only host variables"),
        ("INSERT INTO T VALUES (?)", "USING DESCRIPTOR :SQLDA", "only host variables"),
        ("INSERT INTO T VALUES (?)", "USING :WS-GRP", "host structure"),
    ],
)
def test_using_that_does_not_match_the_markers_is_refused_by_name(text, using, why):
    from gitgalaxy.tools.cobol_to_java.det.sql import SqlError

    with pytest.raises(SqlError, match=why):
        _using(text, using)


def test_using_in_a_cics_program_is_refused():
    from gitgalaxy.tools.cobol_to_java.det.sql import SqlError

    gen = _Host()
    gen.cics = SimpleNamespace()
    with pytest.raises(SqlError, match="CICS"):
        _using("INSERT INTO T VALUES (?)", "USING :WS-ID", gen=gen)


# #4269: the forms above that stay refused (DESCRIBE, CONNECT, CALL, host-variable text) wait on a burned program that
# uses them; this pins the premise of register Q4 ("burned estates using any of them: none") so it fails when it ends.
_BURNED_CORPORA = (
    "aws-mainframe-modernization-carddemo",
    "cics-async-api-credit-card-application-example",
    "cics-banking-sample-application-cbsa",
    "cics-genapp",
    "dbb-mortgage-application",
    "zecs",
)
_REFUSED_SQL_VERB = re.compile(r"EXEC\s+SQL\s+(CALL|CONNECT|DESCRIBE|PREPARE|EXECUTE|WHENEVER)\b", re.I)


def test_no_burned_estate_program_issues_a_refused_dynamic_or_connection_sql_verb():
    root = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", TOOLS.parents[1] / ".mainframe_corpora"))
    present = [root / n for n in _BURNED_CORPORA if (root / n).is_dir()]
    if not present:
        pytest.skip("needs the burned mainframe corpora (GITGALAXY_MAINFRAME_CORPORA)")
    hits = []
    for corpus in present:
        for path in corpus.rglob("*"):
            if path.suffix.lower() not in (".cbl", ".cob", ".cpy") or not path.is_file():
                continue
            text = path.read_text(encoding="latin-1")
            # a fixed-format comment line (* or / in column 7) is not a statement
            code = "\n".join(ln for ln in text.splitlines() if len(ln) < 7 or ln[6] not in "*/")
            hits += [f"{path.relative_to(root)}: {m.group(0)}" for m in _REFUSED_SQL_VERB.finditer(code)]
    assert not hits, "a burned program now issues a refused SQL verb: model it (register Q4):\n" + "\n".join(hits[:10])


_SCROLL_AND_ROWSET = [
    ("FETCH PRIOR FROM C1 INTO :A", "FETCH PRIOR"),
    ("FETCH FIRST FROM C1 INTO :A", "FETCH FIRST"),
    ("FETCH LAST FROM C1 INTO :A", "FETCH LAST"),
    ("FETCH CURRENT FROM C1 INTO :A", "FETCH CURRENT"),
    ("FETCH BEFORE FROM C1", "FETCH BEFORE"),
    ("FETCH AFTER FROM C1", "FETCH AFTER"),
    ("FETCH ABSOLUTE 3 FROM C1 INTO :A", "FETCH ABSOLUTE"),
    ("FETCH RELATIVE -2 C1 INTO :A", "FETCH RELATIVE"),
    ("FETCH INSENSITIVE PRIOR FROM C1 INTO :A", "FETCH PRIOR"),
    ("FETCH SENSITIVE ABSOLUTE :N FROM C1 INTO :A", "FETCH ABSOLUTE"),
    ("fetch\n  prior\n from c1 into :a", "FETCH PRIOR"),
    ("FETCH NEXT ROWSET FROM C1 FOR 5 ROWS INTO :A", "multi-row FETCH"),
    ("FETCH ROWSET STARTING AT ABSOLUTE 4 FROM C1 FOR :N ROWS INTO :A", "FETCH ABSOLUTE|multi-row FETCH"),
    ("FETCH FROM C1 FOR 3 ROWS INTO :A", "multi-row FETCH"),
    ("INSERT INTO T (A) VALUES (:A) FOR :N ROWS", "multi-row INSERT"),
    ("INSERT INTO T (A) VALUES (:A) FOR 10 ROWS ATOMIC", "multi-row INSERT"),
]


@pytest.mark.parametrize("sql, why", _SCROLL_AND_ROWSET)
def test_orientations_without_a_scroll_cursor_and_multi_row_forms_are_refused_by_name(sql, why):
    from gitgalaxy.tools.cobol_to_java.det.sql import SqlError

    with pytest.raises(SqlError, match=rf"(?s)({why}).*register Q4"):
        _run(sql)


@pytest.mark.parametrize("sql", _SCROLL_AND_ROWSET[:3] + _SCROLL_AND_ROWSET[-2:])
def test_scroll_and_multi_row_forms_are_refused_in_a_cics_program_too(sql):
    from gitgalaxy.tools.cobol_to_java.det.sql import SqlError

    gen = _Gen()
    gen.cics = SimpleNamespace()
    with pytest.raises(SqlError, match="register Q4"):
        _run(sql[0], gen=gen)


@pytest.mark.parametrize(
    "sql",
    [
        "FETCH C1 INTO :A",
        "FETCH NEXT FROM C1 INTO :A",
        "Fetch Cust_Cursor\n  INTO\n        :A,\n        :B",  # GenApp LGIPDB01's spelling on an INSENSITIVE SCROLL cursor
        "fetch zip_cursor into :a",
        "FETCH FIRST-CUR INTO :A",  # a cursor whose name starts with an orientation word
        "FETCH PRIOR-ROW INTO :A",
        "INSERT INTO T (A) VALUES ('FOR 3 ROWS')",
        "INSERT INTO T (A) VALUES (:A)",
    ],
)
def test_plain_fetch_and_insert_are_not_taken_for_scroll_or_multi_row(sql):
    from gitgalaxy.tools.cobol_to_java.det.sql import SqlError

    # no generated repository method in this stub: the refusal is the missing method, never a Q4 scroll / multi-row one
    with pytest.raises(SqlError, match="no generated Db2 repository method"):
        _run(sql)


_SCROLL_OR_ROWSET_SQL = re.compile(
    r"EXEC\s+SQL\s+(?:(?!END-EXEC).)*?\b(?:FETCH\s+(?:(?:INSENSITIVE|SENSITIVE)\s+)?(?:BEFORE|AFTER|NEXT\s+ROWSET|"
    r"ROWSET)\b|FOR\s+:?[A-Z0-9-]+\s+ROWS\b|WITH\s+ROWSET\s+POSITIONING)",
    re.I | re.S,
)


def test_no_burned_estate_program_uses_a_positioning_fetch_or_multi_row_sql():  # (PRIOR, FIRST ... are modelled, #4269)
    root = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", TOOLS.parents[1] / ".mainframe_corpora"))
    present = [root / n for n in _BURNED_CORPORA if (root / n).is_dir()]
    if not present:
        pytest.skip("needs the burned mainframe corpora (GITGALAXY_MAINFRAME_CORPORA)")
    hits = []
    for corpus in present:
        for path in corpus.rglob("*"):
            if path.suffix.lower() not in (".cbl", ".cob", ".cpy") or not path.is_file():
                continue
            code = "\n".join(
                ln for ln in path.read_text(encoding="latin-1").splitlines() if len(ln) < 7 or ln[6] not in "*/"
            )
            hits += [f"{path.relative_to(root)}: {_norm_hit(m.group(0))}" for m in _SCROLL_OR_ROWSET_SQL.finditer(code)]
    assert not hits, (
        "a burned program now uses FETCH BEFORE / AFTER or multi-row SQL: model it (register Q4):\n"
        + "\n".join(hits[:10])
    )


def _norm_hit(text):
    return re.sub(r"\s+", " ", text)[:80]


# ---- #4269: FETCH PRIOR / FIRST / LAST / CURRENT / ABSOLUTE n / RELATIVE n of an (INSENSITIVE) SCROLL cursor ---------
# IBM Db2 for z/OS SQL Reference, FETCH: the cursor sits before the first row, on a row, or after the last; a move that
# leaves the rows is SQLCODE +100 and parks it there. The port reads the rows at OPEN, so it models the insensitive cursor.


def _scroll_sql(declare):
    from gitgalaxy.tools.cobol_to_java.det.sql import Sql

    return Sql(_Gen(), "P", None, f"EXEC SQL DECLARE {declare} FOR SELECT A FROM T END-EXEC.")


@pytest.mark.parametrize(
    "declare, fetch, why",
    [
        ("S1 SENSITIVE SCROLL CURSOR", "FETCH PRIOR S1 INTO :A", "SENSITIVE or DYNAMIC"),
        ("S1 SENSITIVE DYNAMIC SCROLL CURSOR", "FETCH LAST S1 INTO :A", "SENSITIVE or DYNAMIC"),
        ("S1 INSENSITIVE SCROLL CURSOR", "FETCH SENSITIVE LAST S1 INTO :A", "SENSITIVE or DYNAMIC"),
        ("S1 SCROLL CURSOR WITH HOLD", "FETCH FIRST S1 INTO :A", "WITH HOLD"),
        ("S1 NO SCROLL CURSOR", "FETCH FIRST S1 INTO :A", "not declared SCROLL"),
        ("S1 CURSOR", "FETCH ABSOLUTE 2 S1 INTO :A", "not declared SCROLL"),
        ("S1 SCROLL CURSOR", "FETCH BEFORE S1", "only positions"),
        ("S1 SCROLL CURSOR", "FETCH AFTER S1", "only positions"),
        ("S1 SCROLL CURSOR", "FETCH NEXT ROWSET FROM S1 FOR 2 ROWS INTO :A", "multi-row"),
    ],
)
def test_a_scroll_fetch_the_port_cannot_model_is_refused_by_name(declare, fetch, why):
    from gitgalaxy.tools.cobol_to_java.det.sql import SqlError

    with pytest.raises(SqlError, match=rf"(?s){why}.*register Q4"):
        _scroll_sql(declare).command(f"EXEC SQL {fetch} END-EXEC", 7, "")


@pytest.mark.parametrize("declare", ["S1 SCROLL CURSOR", "S1 INSENSITIVE SCROLL CURSOR", "S1 ASENSITIVE SCROLL CURSOR"])
@pytest.mark.parametrize(
    "fetch", ["FETCH PRIOR S1", "FETCH FIRST FROM S1", "FETCH ABSOLUTE -2 S1", "FETCH RELATIVE :N S1"]
)
def test_a_scroll_fetch_of_a_scroll_cursor_passes_the_checks(declare, fetch):
    # (the stub has no generated repository method: reaching that error means every Q4 check passed)
    from gitgalaxy.tools.cobol_to_java.det.sql import SqlError

    with pytest.raises(SqlError, match="no generated Db2 repository method"):
        _scroll_sql(declare).command(f"EXEC SQL {fetch} INTO :A END-EXEC", 7, "")


_SCROLL_MAIN = """package ggtest;

import ggtest.cobolrt.Field;
import ggtest.cobolrt.Storage;
import ggtest.cobolrt.sql.DetSql;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

public class Main {
    static final Charset CS = StandardCharsets.ISO_8859_1;
    static Object last = 0;

    static int sqlcode(Field ca) {
        byte[] b = ca.storage().bytes;
        return (b[12] & 0xFF) | (b[13] & 0xFF) << 8 | (b[14] & 0xFF) << 16 | b[15] << 24;
    }

    static List<Map<String, Object>> rows(int n) {
        List<Map<String, Object>> out = new java.util.ArrayList<>();
        for (int i = 1; i <= n; i++) out.add(Map.of("ID", i * 10));
        return out;
    }

    static void go(Field ca, String c, String o, long n) {
        Map<String, Object> row = o.equals("NEXT") ? DetSql.fetch(ca, "P:9", c, CS) : DetSql.fetchScroll(ca, "P:9", c, o, n, CS);
        if (row != null) last = row.get("ID");
        System.out.println(o + " " + n + " " + sqlcode(ca) + " " + last);
    }

    public static void main(String[] a) {
        Field ca = Field.group(new Storage(136), 0, 136);
        DetSql.open(ca, "P:1", "S1", () -> rows(5), CS);
        Object[][] steps = {
            {"NEXT", 0}, {"LAST", 0}, {"PRIOR", 0}, {"FIRST", 0}, {"ABSOLUTE", 3}, {"ABSOLUTE", -2}, {"RELATIVE", 1},
            {"RELATIVE", 1}, {"PRIOR", 0}, {"CURRENT", 0}, {"RELATIVE", -3}, {"ABSOLUTE", 4}, {"FIRST", 0}, {"PRIOR", 0},
            {"NEXT", 0}, {"ABSOLUTE", 9}, {"PRIOR", 0}, {"RELATIVE", -9}, {"NEXT", 0}, {"ABSOLUTE", 0}, {"ABSOLUTE", -5},
            {"ABSOLUTE", -6}, {"NEXT", 0}, {"RELATIVE", 0}};
        for (Object[] s : steps) go(ca, "S1", (String) s[0], ((Number) s[1]).longValue());
        DetSql.close(ca, "P:2", "S1", CS);
        go(ca, "S1", "LAST", 0);
        DetSql.open(ca, "P:3", "S2", () -> rows(0), CS);
        go(ca, "S2", "FIRST", 0);
        go(ca, "S2", "LAST", 0);
        go(ca, "S2", "NEXT", 0);
        go(ca, "S2", "PRIOR", 0);
        try {
            DetSql.fetchScroll(ca, "P:4", "S2", "SIDEWAYS", 0, CS);
        } catch (UnsupportedOperationException e) {
            System.out.println("refused");
        }
    }
}
"""


def _jdk():
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    return Path(home) / "bin" if home and (Path(home) / "bin" / "javac").is_file() else None


@pytest.mark.skipif(_jdk() is None, reason="no JDK (JDK_17 / JAVA_HOME)")
def test_detsql_moves_a_position_over_the_rows_read_at_open_as_db2_does(tmp_path):
    from javac_server import javac as javac_run

    rt = TOOLS.parent.parent / "gitgalaxy" / "tools" / "cobol_to_java" / "det" / "cobolrt"
    src = tmp_path / "src" / "ggtest"
    for sub in ("", "sql"):
        (src / "cobolrt" / sub).mkdir(parents=True, exist_ok=True)
        for f in (rt / sub).glob("*.java"):
            text = f.read_text(encoding="utf-8").replace("__PACKAGE__", "ggtest")
            (src / "cobolrt" / sub / f.name).write_text(text, encoding="utf-8")
    (src / "Main.java").write_text(_SCROLL_MAIN, encoding="utf-8")
    jdk = _jdk()
    files = [str(p) for p in (tmp_path / "src").rglob("*.java")]
    javac = javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"), *files],  # noqa: S603
                      capture_output=True, text=True, encoding="utf-8", check=False)  # fmt: skip
    assert javac.returncode == 0, javac.stderr[:3000]
    out = subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(tmp_path / "classes"), "ggtest.Main"],  # noqa: S603
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout.splitlines()  # fmt: skip
    # rows 10..50; "<orientation> <n> <SQLCODE> <the last row fetched>" -- +100 leaves the host variable as it was
    assert out == [
        "NEXT 0 0 10",
        "LAST 0 0 50",
        "PRIOR 0 0 40",
        "FIRST 0 0 10",
        "ABSOLUTE 3 0 30",
        "ABSOLUTE -2 0 40",
        "RELATIVE 1 0 50",
        "RELATIVE 1 100 50",  # past the last row: after it
        "PRIOR 0 0 50",  # from after the last row, PRIOR is the last
        "CURRENT 0 0 50",
        "RELATIVE -3 0 20",
        "ABSOLUTE 4 0 40",
        "FIRST 0 0 10",
        "PRIOR 0 100 10",  # before the first row
        "NEXT 0 0 10",  # from before the first, NEXT is the first
        "ABSOLUTE 9 100 10",
        "PRIOR 0 0 50",  # beyond the end, then back one from after-last
        "RELATIVE -9 100 50",
        "NEXT 0 0 10",
        "ABSOLUTE 0 100 10",  # ABSOLUTE 0: before the first row
        "ABSOLUTE -5 0 10",
        "ABSOLUTE -6 100 10",  # -n counts from the end; one more than there are is before the first
        "NEXT 0 0 10",
        "RELATIVE 0 0 10",
        "LAST 0 -501 10",  # closed
        "FIRST 0 100 10",
        "LAST 0 100 10",
        "NEXT 0 100 10",
        "PRIOR 0 100 10",  # no rows: every move is +100
        "refused",
    ]
