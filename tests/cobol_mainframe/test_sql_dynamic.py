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
        ("ALLOCATE C1 CURSOR FOR RESULT SET :LOC", "EXEC SQL ALLOCATE: .*result set locator"),
        ("ASSOCIATE LOCATORS (:LOC) WITH PROCEDURE PROC1", "EXEC SQL ASSOCIATE: .*result sets"),
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
# the whole refused class of det/sql.py's _REFUSED_VERBS (a SET that assigns a host variable, SET :H = ..., is modelled)
_REFUSED_SQL_VERB = re.compile(
    r"EXEC\s+SQL\s+(CALL|CONNECT|DESCRIBE|PREPARE|EXECUTE|WHENEVER|ALLOCATE|ASSOCIATE|SET\s+(?!\(?\s*:))\b", re.I
)


def test_the_burned_estate_pin_covers_every_refused_verb():
    from gitgalaxy.tools.cobol_to_java.det.sql import _REFUSED_VERBS

    for verb in _REFUSED_VERBS:
        probe = "SET CURRENT SQLID" if verb == "SET" else verb
        assert _REFUSED_SQL_VERB.search(f"EXEC SQL {probe} X"), verb
    assert not _REFUSED_SQL_VERB.search("EXEC SQL SET :H = CURRENT TIMESTAMP")


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
    ("FETCH BEFORE FROM C1", "FETCH BEFORE"),  # (C1 is not declared SCROLL)
    ("FETCH AFTER FROM C1", "FETCH AFTER"),
    ("FETCH ABSOLUTE 3 FROM C1 INTO :A", "FETCH ABSOLUTE"),
    ("FETCH RELATIVE -2 C1 INTO :A", "FETCH RELATIVE"),
    ("FETCH INSENSITIVE PRIOR FROM C1 INTO :A", "FETCH PRIOR"),
    ("FETCH SENSITIVE ABSOLUTE :N FROM C1 INTO :A", "FETCH ABSOLUTE"),
    ("fetch\n  prior\n from c1 into :a", "FETCH PRIOR"),
    ("FETCH NEXT ROWSET FROM C1 INTO :A", "multi-row FETCH"),
    ("FETCH ROWSET STARTING AT ABSOLUTE 4 FROM C1 FOR :N ROWS INTO :A", "FETCH ABSOLUTE|multi-row FETCH"),
    ("FETCH FROM C1 FOR 3 ROWS INTO :A", "multi-row FETCH"),
    ("INSERT INTO T (A) VALUES (:A) FOR :N ROWS NOT ATOMIC CONTINUE ON SQLEXCEPTION", "multi-row INSERT"),
    ("INSERT INTO T (A) VALUES (:A) FOR 10 ROWS NOT ATOMIC CONTINUE ON SQLEXCEPTION", "multi-row INSERT"),
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
        ("S1 CURSOR", "FETCH BEFORE S1", "needs a cursor declared SCROLL"),
        ("S1 NO SCROLL CURSOR", "FETCH AFTER FROM S1", "needs a cursor declared SCROLL"),
        ("S1 SENSITIVE SCROLL CURSOR", "FETCH BEFORE S1", "SENSITIVE or DYNAMIC"),
        ("S1 INSENSITIVE SCROLL CURSOR", "FETCH SENSITIVE AFTER S1", "SENSITIVE or DYNAMIC"),
        ("S1 SCROLL CURSOR WITH HOLD", "FETCH AFTER S1", "WITH HOLD"),
        ("S1 SCROLL CURSOR", "FETCH BEFORE S1 INTO :A", "BEFORE / AFTER: takes a cursor and no INTO"),
        ("S1 SCROLL CURSOR", "FETCH INSENSITIVE AFTER FROM S1 INTO :A", "BEFORE / AFTER: takes a cursor and no INTO"),
        ("S1 SCROLL CURSOR", "FETCH ROWSET STARTING AT ABSOLUTE 2 FROM S1 FOR 2 ROWS INTO :A", "multi-row"),
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


@pytest.mark.parametrize("declare", ["S1 SCROLL CURSOR", "S1 INSENSITIVE SCROLL CURSOR", "S1 ASENSITIVE SCROLL CURSOR"])
@pytest.mark.parametrize(
    "fetch, where",
    [
        ("FETCH BEFORE S1", "BEFORE"),
        ("FETCH AFTER S1", "AFTER"),
        ("FETCH BEFORE FROM S1", "BEFORE"),
        ("FETCH INSENSITIVE AFTER FROM S1", "AFTER"),
        ("fetch\n  after\n from s1", "AFTER"),
    ],
)
def test_fetch_before_or_after_a_scroll_cursor_parks_it_with_no_row_and_no_repository_method(declare, fetch, where):
    # (no generated method in this stub, none needed: a position reads no row)
    out = _scroll_sql(declare).command(f"EXEC SQL {fetch} END-EXEC", 7, "")
    assert out == [f'DetSql.positionScroll(ca, "P:7", "S1", "{where}", CS);']


def test_fetch_before_and_after_are_refused_in_a_cics_program_too():
    from gitgalaxy.tools.cobol_to_java.det.sql import SqlError

    gen = _Gen()
    gen.cics = SimpleNamespace()
    with pytest.raises(SqlError, match="register Q4"):
        _run("FETCH BEFORE FROM C1", gen=gen)


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
        Map<String, Object> row = null;
        if (o.equals("BEFORE") || o.equals("AFTER")) DetSql.positionScroll(ca, "P:9", c, o, CS);
        else row = o.equals("NEXT") ? DetSql.fetch(ca, "P:9", c, CS) : DetSql.fetchScroll(ca, "P:9", c, o, n, CS);
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
            {"ABSOLUTE", -6}, {"NEXT", 0}, {"RELATIVE", 0},
            {"AFTER", 0}, {"PRIOR", 0}, {"BEFORE", 0}, {"NEXT", 0}, {"AFTER", 0}, {"NEXT", 0}, {"BEFORE", 0}, {"PRIOR", 0},
            {"AFTER", 0}, {"BEFORE", 0}, {"LAST", 0}};
        for (Object[] s : steps) go(ca, "S1", (String) s[0], ((Number) s[1]).longValue());
        DetSql.close(ca, "P:2", "S1", CS);
        go(ca, "S1", "LAST", 0);
        go(ca, "S1", "AFTER", 0);
        go(ca, "S1", "BEFORE", 0);
        DetSql.open(ca, "P:3", "S2", () -> rows(0), CS);
        go(ca, "S2", "FIRST", 0);
        go(ca, "S2", "LAST", 0);
        go(ca, "S2", "NEXT", 0);
        go(ca, "S2", "PRIOR", 0);
        go(ca, "S2", "AFTER", 0);
        go(ca, "S2", "NEXT", 0);
        go(ca, "S2", "BEFORE", 0);
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
        "AFTER 0 0 10",  # FETCH AFTER / BEFORE: a position, SQLCODE 0, the host variable untouched
        "PRIOR 0 0 50",  # from after the last row, PRIOR is the last
        "BEFORE 0 0 50",
        "NEXT 0 0 10",  # from before the first, NEXT is the first
        "AFTER 0 0 10",
        "NEXT 0 100 10",  # after the last: still +100
        "BEFORE 0 0 10",
        "PRIOR 0 100 10",
        "AFTER 0 0 10",
        "BEFORE 0 0 10",
        "LAST 0 0 50",
        "LAST 0 -501 50",  # closed
        "AFTER 0 -501 50",
        "BEFORE 0 -501 50",
        "FIRST 0 100 50",
        "LAST 0 100 50",
        "NEXT 0 100 50",
        "PRIOR 0 100 50",  # no rows: every move is +100
        "AFTER 0 0 50",
        "NEXT 0 100 50",
        "BEFORE 0 0 50",
        "PRIOR 0 100 50",
        "refused",
    ]


SCR = Path(__file__).resolve().parents[1] / "equivalence" / "db2" / "scrolldemo"
# SCRDEMO's DISPLAYs, traced by hand over the rows 10..50: tag (14), SQLCODE (10), the host variable (10)
_TRACED_SCROLL = [
    ("NEXT", 0, 10), ("LAST", 0, 50), ("PRIOR", 0, 40), ("FIRST", 0, 10), ("ABS 3", 0, 30), ("ABS -2", 0, 40),
    ("REL 1", 0, 50), ("REL 1 PAST", 100, 50), ("PRIOR OFF", 0, 50), ("CURRENT", 0, 50), ("REL VAR -3", 0, 20),
    ("ABS VAR 4", 0, 40), ("FIRST", 0, 10), ("PRIOR BEFORE", 100, 10), ("NEXT AFTER", 0, 10), ("ABS 9", 100, 10),
    ("PRIOR LAST", 0, 50), ("REL -9", 100, 50), ("NEXT FIRST", 0, 10), ("ABS 0", 100, 10),
    ("AFTER", 0, 10), ("PRIOR AFTER", 0, 50), ("BEFORE", 0, 50), ("NEXT BEFORE", 0, 10), ("AFTER FROM", 0, 10),
    ("NEXT PAST", 100, 10), ("BEFORE FROM", 0, 10), ("PRIOR PAST", 100, 10), ("CLOSE", 0, 10),
    ("LAST CLOSED", -501, 10), ("EMPTY FIRST", 100, 10), ("EMPTY LAST", 100, 10),
    ("EMPTY AFTER", 0, 10), ("EMPTY BEFORE", 0, 10),
]  # fmt: skip
TRACED_SCROLL = "".join(f"{t:<14}{c:>10}{v:>10}\n" for t, c, v in _TRACED_SCROLL)


def test_the_oracle_takes_fetch_before_and_after_as_a_position_with_no_row():
    """#4269: equivalence_sql.py gives BEFORE / AFTER (no INTO) a scroll statement with no host variable; ggsql.c reads
    the `K:BEFORE` / `K:AFTER` token. A cursor not declared SCROLL, or the INTO form, stays refused by name."""
    import equivalence_sql as Q

    _, table = Q.precompile((SCR / "cbl" / "SCRDEMO.cbl").read_text(encoding="utf-8"), [], Path("SCRDEMO.cbl"))
    fetches = [ln.split() for ln in table.splitlines() if ln.startswith("S ") and " FETCH " in ln]
    positions = [(f[5], f[8]) for f in fetches if f[8] in ("K:BEFORE", "K:AFTER")]
    assert positions == [("SC1", "K:AFTER"), ("SC1", "K:BEFORE"), ("SC1", "K:AFTER"), ("SC1", "K:BEFORE"),
                         ("SC2", "K:AFTER"), ("SC2", "K:BEFORE")]  # fmt: skip
    assert all(f[3:5] == ["0", "0"] for f in fetches if f[8] in ("K:BEFORE", "K:AFTER"))  # no input, no output
    src = (SCR / "cbl" / "SCRDEMO.cbl").read_text(encoding="utf-8")
    plain = src.replace("SC1 INSENSITIVE SCROLL CURSOR", "SC1 CURSOR").replace("SC2 SCROLL CURSOR", "SC2 CURSOR")
    with pytest.raises(Q.Unsupported, match="not declared SCROLL"):
        Q.precompile(plain, [], Path("SCRDEMO.cbl"))


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL, Db2) and a JDK + Maven")
def test_scrolldemo_det_port_proves_on_db2_against_the_hand_trace(tmp_path):
    import json
    import shutil

    pytest.importorskip("tree_sitter_language_pack")
    import det_port

    from gitgalaxy.tools.cobol_to_java.det import program as P

    estate = tmp_path / "estate"
    shutil.copytree(SCR, estate, ignore=shutil.ignore_patterns("seed.sql"))
    for argv in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "e"]):
        subprocess.run(["git", "-C", str(estate), *argv], check=True)  # noqa: S603, S607
    case = {"corpus": "scroll-synthetic", "program": "SCRDEMO", "program_source": "cbl/SCRDEMO.cbl", "copy_dirs": [],
            "parm": None, "clock": "2026/10/08 10:00:00.00", "datasets": {},
            "db2": {"ddl": ["ddl/ITEM.ddl"], "seed": str(SCR / "seed.sql"), "compare": ["GGSCR.ITEM"],
                    "compare_sql": True}}  # fmt: skip
    (tmp_path / "case.json").write_text(json.dumps(case), encoding="utf-8")
    project = det_port.estate(estate, tmp_path / "translate")  # (its own work: never inside the estate)
    stub = (project / "src/main/java" / det_port.PKG_DIR / "service" / "ScrdemoService.java").read_text("utf-8")
    r = P.translate(estate / "cbl/SCRDEMO.cbl", [estate / "cbl"], stub, det_port.PKG, P.estate_files(project), project)
    assert r.stats["holes"] == []
    assert r.java.count("DetSql.fetchScroll(") == 22  # every FETCH but the plain NEXT ones and BEFORE / AFTER
    assert r.java.count("DetSql.positionScroll(") == 6  # (4 on SC1, 2 on the empty SC2): the oracle runs these as well
    port = tmp_path / "port"
    (port / "service").mkdir(parents=True)
    (port / "service" / f"{r.service}.java").write_text(r.java, encoding="utf-8")
    for rel, text in P.runtime_files(det_port.PKG, P.has_batch(project)).items():
        if "/cics/" not in rel:  # (an estate with no CICS has no cics package)
            (port / rel).parent.mkdir(parents=True, exist_ok=True)
            (port / rel).write_text(text, encoding="utf-8")
    keep = tmp_path / "proof"
    proc = subprocess.run([sys.executable, str(TOOLS / "equivalence.py"), "run", "scroll", "--case-file",  # noqa: S603
                           str(tmp_path / "case.json"), "--corpus-dir", str(estate), "--port", str(port), "--keep",
                           str(keep), "--faults", "none", "--sql-faults", "none"],
                          capture_output=True, text=True, check=False)  # fmt: skip
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-3000:]
    import json as _json

    report = _json.loads((keep / "report.json").read_text(encoding="utf-8"))
    assert report["proven"] is True
    assert (keep / "cobol" / "stdout.txt").read_text(encoding="latin-1") == TRACED_SCROLL


# #4269 rowset FETCH: ROWDEMO is built inline (no committed estate); rows 10..50, QTY NULL on id 20
_ROWDEMO_CBL = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ROWDEMO.
       ENVIRONMENT DIVISION.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
           EXEC SQL INCLUDE SQLCA END-EXEC.
           EXEC SQL DECLARE GGROW.ITEM TABLE
               ( ID                 INTEGER NOT NULL,
                 NAME               CHAR(4) NOT NULL,
                 QTY                DECIMAL(5,2)
               ) END-EXEC.
       01  WS-TABLES.
           05  WS-ID                PIC S9(9) COMP OCCURS 3.
           05  WS-NAME              PIC X(4) OCCURS 3.
           05  WS-QTY               PIC S9(3)V99 COMP-3 OCCURS 3.
           05  WS-QI                PIC S9(4) COMP OCCURS 3.
       01  WS-N                     PIC S9(9) COMP.
       01  WS-I                     PIC S9(9) COMP.
       01  WS-CODE                  PIC -(9)9.
       01  WS-ROWS                  PIC -(9)9.
       01  WS-SHOW                  PIC -(9)9.
       01  WS-Q                     PIC -(3)9.99.
       01  WS-IND                   PIC -(9)9.
       01  WS-TAG                   PIC X(8).
           EXEC SQL DECLARE RC1 CURSOR WITH ROWSET POSITIONING FOR
               SELECT ID, NAME, QTY FROM GGROW.ITEM ORDER BY ID
           END-EXEC.
       PROCEDURE DIVISION.
       MAIN-PARA.
           EXEC SQL OPEN RC1 END-EXEC
           EXEC SQL FETCH NEXT ROWSET FROM RC1 FOR 2 ROWS
               INTO :WS-ID, :WS-NAME, :WS-QTY :WS-QI END-EXEC
           MOVE 'LIT 2' TO WS-TAG
           PERFORM SHOW-PARA
           MOVE 3 TO WS-N
           EXEC SQL FETCH ROWSET FROM RC1 FOR :WS-N ROWS
               INTO :WS-ID, :WS-NAME, :WS-QTY :WS-QI END-EXEC
           MOVE 'VAR 3' TO WS-TAG
           PERFORM SHOW-PARA
           EXEC SQL FETCH NEXT ROWSET FROM RC1 FOR 3 ROWS
               INTO :WS-ID, :WS-NAME, :WS-QTY :WS-QI END-EXEC
           MOVE 'END' TO WS-TAG
           PERFORM SHOW-PARA
           EXEC SQL CLOSE RC1 END-EXEC
           EXEC SQL OPEN RC1 END-EXEC
           EXEC SQL FETCH NEXT ROWSET FROM RC1 FOR :WS-N ROWS
               INTO :WS-ID, :WS-NAME, :WS-QTY :WS-QI END-EXEC
           MOVE 'FULL' TO WS-TAG
           PERFORM SHOW-PARA
           EXEC SQL FETCH NEXT ROWSET FROM RC1 FOR :WS-N ROWS
               INTO :WS-ID, :WS-NAME, :WS-QTY :WS-QI END-EXEC
           MOVE 'SHORT' TO WS-TAG
           PERFORM SHOW-PARA
           EXEC SQL CLOSE RC1 END-EXEC
           EXEC SQL FETCH NEXT ROWSET FROM RC1 FOR 3 ROWS
               INTO :WS-ID, :WS-NAME, :WS-QTY :WS-QI END-EXEC
           MOVE 'CLOSED' TO WS-TAG
           PERFORM SHOW-PARA
           STOP RUN.
       SHOW-PARA.
           MOVE SQLCODE TO WS-CODE
           MOVE SQLERRD(3) TO WS-ROWS
           DISPLAY WS-TAG WS-CODE WS-ROWS
           PERFORM SHOW-ROW VARYING WS-I FROM 1 BY 1
               UNTIL WS-I > SQLERRD(3).
       SHOW-ROW.
           MOVE WS-ID(WS-I) TO WS-SHOW
           IF WS-QI(WS-I) < 0
               MOVE 0 TO WS-Q
           ELSE
               MOVE WS-QTY(WS-I) TO WS-Q
           END-IF
           MOVE WS-QI(WS-I) TO WS-IND
           DISPLAY WS-NAME(WS-I) WS-SHOW WS-Q WS-IND.
"""
_ROWDEMO_JCL = """\
//ROWDEMO  JOB (COBOL),'ROWDEMO',CLASS=A,MSGCLASS=H
//STEP1    EXEC PGM=IKJEFT01
//SYSTSPRT DD SYSOUT=*
//SYSTSIN  DD *
     DSN SYSTEM(DB2P)
          RUN PROGRAM(ROWDEMO) PLAN(GGROW)
/*
"""
_ROWDEMO_DDL = (
    "CREATE TABLE GGROW.ITEM (ID INTEGER NOT NULL, NAME CHAR(4) NOT NULL, QTY DECIMAL(5,2), PRIMARY KEY (ID));\n"
)
_ROWDEMO_SEED = (
    "INSERT INTO GGROW.ITEM VALUES (10, 'AAAA', 1.50);\nINSERT INTO GGROW.ITEM VALUES (20, 'BBBB', NULL);\n"
    "INSERT INTO GGROW.ITEM VALUES (30, 'CCCC', 3.00);\nINSERT INTO GGROW.ITEM VALUES (40, 'DDDD', 4.25);\n"
    "INSERT INTO GGROW.ITEM VALUES (50, 'EEEE', 5.00);\n"
)
_ROW = {10: ("AAAA", "1.50", 0), 20: ("BBBB", "0.00", -1), 30: ("CCCC", "3.00", 0), 40: ("DDDD", "4.25", 0),
        50: ("EEEE", "5.00", 0)}  # fmt: skip
# per FETCH: tag (8), SQLCODE (10), SQLERRD(3) (10), then one line per row read: name (4), id (10), qty (7), indicator (10)
_TRACED_ROWSET = [
    ("LIT 2", 0, [10, 20]), ("VAR 3", 0, [30, 40, 50]), ("END", 100, []), ("FULL", 0, [10, 20, 30]),
    ("SHORT", 100, [40, 50]), ("CLOSED", -501, []),
]  # fmt: skip
TRACED_ROWSET = "".join(
    f"{t:<8}{c:>10}{len(ids):>10}\n" + "".join(f"{_ROW[i][0]}{i:>10}{_ROW[i][1]:>7}{_ROW[i][2]:>10}\n" for i in ids)
    for t, c, ids in _TRACED_ROWSET
)


def _rowdemo_port(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    import det_port

    from gitgalaxy.tools.cobol_to_java.det import program as P

    estate = tmp_path / "estate"
    for rel, text in (
        ("cbl/ROWDEMO.cbl", _ROWDEMO_CBL),
        ("jcl/ROWDEMO.jcl", _ROWDEMO_JCL),
        ("ddl/ITEM.ddl", _ROWDEMO_DDL),
    ):
        (estate / rel).parent.mkdir(parents=True, exist_ok=True)
        (estate / rel).write_text(text, encoding="utf-8")
    (tmp_path / "seed.sql").write_text(_ROWDEMO_SEED, encoding="utf-8")
    for argv in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "e"]):
        subprocess.run(["git", "-C", str(estate), *argv], check=True)  # noqa: S603, S607
    project = det_port.estate(estate, tmp_path / "translate")  # (its own work: never inside the estate)
    stub = (project / "src/main/java" / det_port.PKG_DIR / "service" / "RowdemoService.java").read_text("utf-8")
    r = P.translate(estate / "cbl/ROWDEMO.cbl", [estate / "cbl"], stub, det_port.PKG, P.estate_files(project), project)
    port = tmp_path / "port"
    (port / "service").mkdir(parents=True)
    (port / "service" / f"{r.service}.java").write_text(r.java, encoding="utf-8")
    for rel, text in P.runtime_files(det_port.PKG, P.has_batch(project)).items():
        if "/cics/" not in rel:
            (port / rel).parent.mkdir(parents=True, exist_ok=True)
            (port / rel).write_text(text, encoding="utf-8")
    return estate, r, port


@pytest.mark.slow(reason="builds an estate and runs the det-port translator (tree-sitter load, ~40 s)")
def test_rowdemo_translates_every_rowset_fetch_with_no_holes(tmp_path):
    _estate, r, _port = _rowdemo_port(tmp_path)
    assert r.stats["holes"] == []
    assert r.java.count("DetSql.fetchRowset(") == 6
    assert r.java.count("DetSql.intoRows(") == 6


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL, Db2) and a JDK + Maven")
def test_rowdemo_det_port_proves_on_db2_against_the_hand_trace(tmp_path):
    import json

    estate, _r, port = _rowdemo_port(tmp_path)
    case = {"corpus": "rowset-synthetic", "program": "ROWDEMO", "program_source": "cbl/ROWDEMO.cbl", "copy_dirs": [],
            "parm": None, "clock": "2026/10/30 10:00:00.00", "datasets": {},
            "db2": {"ddl": ["ddl/ITEM.ddl"], "seed": str(tmp_path / "seed.sql"), "compare": ["GGROW.ITEM"],
                    "compare_sql": True}}  # fmt: skip
    (tmp_path / "case.json").write_text(json.dumps(case), encoding="utf-8")
    keep = tmp_path / "proof"
    proc = subprocess.run([sys.executable, str(TOOLS / "equivalence.py"), "run", "rowset", "--case-file",  # noqa: S603
                           str(tmp_path / "case.json"), "--corpus-dir", str(estate), "--port", str(port), "--keep",
                           str(keep), "--faults", "none", "--sql-faults", "none"],
                          capture_output=True, text=True, check=False)  # fmt: skip
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-3000:]
    report = json.loads((keep / "report.json").read_text(encoding="utf-8"))
    assert report["proven"] is True
    assert (keep / "cobol" / "stdout.txt").read_text(encoding="latin-1") == TRACED_ROWSET


# #4269 INSERT ... FOR n ROWS: the translator's reading of the host variable tables, with items in place of a COBOL source
def _insert_rows_sql(items):
    from types import SimpleNamespace as NS

    from gitgalaxy.tools.cobol_to_java.det.sql import Method, Sql

    def item(name, pic="X(4)", occurs=3, category="ALPHANUMERIC"):
        return NS(name=name, parent=None, pic=pic, occurs=occurs, category=category, children=[], usage="DISPLAY",
                  level=5)  # fmt: skip

    class Gen(_Gen):
        def tmpname(self, base):
            return base

        def resolve(self, ref):
            return items(item)[ref.name]

    sql = Sql(Gen(), "P", None)
    sql.methods = {
        ("P", 7): Method("Repo", "ins", "INSERT", {k: k.lower() for k in ("A", "B", "C", "S", "N", "T", "SHORT")})
    }
    return sql


def _insert_items(item):
    return {
        "A": item("A"),
        "B": item("B", "S9(5)", 3, "NUMERIC"),
        "C": item("C", "S9(4)", 3, "NUMERIC"),
        "S": item("S", "X(4)", 1),
        "N": item("N", "S9(4)", 1, "NUMERIC"),
        "T": item("T", "X(4)", 1, "ALPHANUMERIC"),
        "SHORT": item("SHORT", "X(4)", 2),
    }


def test_insert_for_n_rows_calls_the_single_row_insert_per_element():
    out = _insert_rows_sql(_insert_items).command(
        "EXEC SQL INSERT INTO T (A, B) VALUES (:A, :B :C) FOR 2 ROWS ATOMIC END-EXEC", 7, ""
    )
    assert out == [
        'DetSql.insertRows(ca, "P:7", 2L, 3, "XN", new String[] {"a", "b"}, '
        "new Field[][] {{ca, ca, ca}, {ca, ca, ca}}, new Field[][] {null, {ca, ca, ca}}, p -> repo.ins(p), CS);"
    ]


def test_insert_for_a_host_variable_n_rows_reads_n_at_run_time():
    out = _insert_rows_sql(_insert_items).command("EXEC SQL INSERT INTO T (A) VALUES (:A) FOR :N ROWS END-EXEC", 7, "")
    assert 'DetSql.insertRows(ca, "P:7", DetSql.numIn(ca, CS).longValue(), 3, "X"' in out[0]


@pytest.mark.parametrize(
    "stmt, why",
    [
        ("INSERT INTO T (A) VALUES (:S) FOR 2 ROWS", "not an elementary table"),
        ("INSERT INTO T (A, B) VALUES (:A, :S) FOR 2 ROWS", "not an elementary table"),
        ("INSERT INTO T (A) VALUES (:A) FOR 4 ROWS", "exceeds the host variable tables"),
        ("INSERT INTO T (A) VALUES (:A) FOR :T ROWS", "not a numeric host variable"),
        ("INSERT INTO T (A, B) VALUES (:A, :SHORT) FOR 3 ROWS", "exceeds the host variable tables"),
        ("INSERT INTO T (A) VALUES (:A :SHORT) FOR 2 ROWS", "indicator array"),
    ],
)
def test_insert_for_n_rows_with_host_variables_that_are_not_matching_tables_is_refused(stmt, why):
    from gitgalaxy.tools.cobol_to_java.det.sql import SqlError

    with pytest.raises(SqlError, match=why):
        _insert_rows_sql(_insert_items).command(f"EXEC SQL {stmt} END-EXEC", 7, "")


def test_the_forge_method_for_insert_for_n_rows_is_the_single_row_insert():
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_db2_forge import to_jdbc

    for tail in ("FOR 2 ROWS", "FOR :N ROWS ATOMIC", "for 10 rows"):
        sql, params, _notes = to_jdbc(f"INSERT INTO T (A, B) VALUES (:WS-A, :WS-B) {tail}", "INSERT")
        assert sql == "INSERT INTO T (A, B) VALUES (:wsA, :wsB)"
        assert [h for h, _ in params] == ["WS-A", "WS-B"]


# #4269 INSERT ... FOR n ROWS, proven on Db2: INSDEMO is built inline; GGINS.ITEM holds one seeded row (id 1)
_INSDEMO_CBL = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. INSDEMO.
       ENVIRONMENT DIVISION.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
           EXEC SQL INCLUDE SQLCA END-EXEC.
           EXEC SQL DECLARE GGINS.ITEM TABLE
               ( ID                 INTEGER NOT NULL,
                 NAME               CHAR(4) NOT NULL,
                 QTY                DECIMAL(5,2)
               ) END-EXEC.
       01  WS-TABLES.
           05  WS-ID                PIC S9(9) COMP OCCURS 3.
           05  WS-NAME              PIC X(4) OCCURS 3.
           05  WS-QTY               PIC S9(3)V99 COMP-3 OCCURS 3.
           05  WS-QI                PIC S9(4) COMP OCCURS 3.
       01  WS-N                     PIC S9(9) COMP.
       01  WS-CNT                   PIC S9(9) COMP.
       01  WS-CODE                  PIC -(9)9.
       01  WS-ROWS                  PIC -(9)9.
       01  WS-TAG                   PIC X(8).
       PROCEDURE DIVISION.
       MAIN-PARA.
           MOVE 10 TO WS-ID(1)
           MOVE 20 TO WS-ID(2)
           MOVE 30 TO WS-ID(3)
           MOVE 'AAAA' TO WS-NAME(1)
           MOVE 'BBBB' TO WS-NAME(2)
           MOVE 'CCCC' TO WS-NAME(3)
           MOVE 1.5 TO WS-QTY(1)
           MOVE 2.5 TO WS-QTY(2)
           MOVE 3.5 TO WS-QTY(3)
           MOVE 0 TO WS-QI(1)
           MOVE -1 TO WS-QI(2)
           MOVE 0 TO WS-QI(3)
           EXEC SQL INSERT INTO GGINS.ITEM (ID, NAME, QTY)
               VALUES (:WS-ID, :WS-NAME, :WS-QTY :WS-QI)
               FOR 2 ROWS END-EXEC
           MOVE 'LIT 2' TO WS-TAG
           PERFORM SHOW-PARA
           MOVE 3 TO WS-N
           MOVE 40 TO WS-ID(1)
           MOVE 50 TO WS-ID(2)
           MOVE 60 TO WS-ID(3)
           EXEC SQL INSERT INTO GGINS.ITEM (ID, NAME, QTY)
               VALUES (:WS-ID, :WS-NAME, :WS-QTY :WS-QI)
               FOR :WS-N ROWS ATOMIC END-EXEC
           MOVE 'VAR 3' TO WS-TAG
           PERFORM SHOW-PARA
           MOVE 1 TO WS-ID(1)
           MOVE 70 TO WS-ID(2)
           EXEC SQL INSERT INTO GGINS.ITEM (ID, NAME, QTY)
               VALUES (:WS-ID, :WS-NAME, :WS-QTY :WS-QI)
               FOR 2 ROWS END-EXEC
           MOVE 'DUP KEY' TO WS-TAG
           PERFORM SHOW-PARA
           MOVE 80 TO WS-ID(1)
           MOVE 1 TO WS-ID(2)
           MOVE 90 TO WS-ID(3)
           EXEC SQL INSERT INTO GGINS.ITEM (ID, NAME, QTY)
               VALUES (:WS-ID, :WS-NAME, :WS-QTY :WS-QI)
               FOR 3 ROWS ATOMIC END-EXEC
           MOVE 'DUP ROW2' TO WS-TAG
           PERFORM SHOW-PARA
           MOVE 81 TO WS-ID(1)
           MOVE 82 TO WS-ID(2)
           MOVE 1 TO WS-ID(3)
           MOVE 3 TO WS-N
           EXEC SQL INSERT INTO GGINS.ITEM (ID, NAME, QTY)
               VALUES (:WS-ID, :WS-NAME, :WS-QTY :WS-QI)
               FOR :WS-N ROWS END-EXEC
           MOVE 'DUP LAST' TO WS-TAG
           PERFORM SHOW-PARA
           EXEC SQL SELECT COUNT(*) INTO :WS-CNT FROM GGINS.ITEM
           END-EXEC
           MOVE WS-CNT TO SQLERRD(3)
           MOVE 'COUNT' TO WS-TAG
           PERFORM SHOW-PARA
           STOP RUN.
       SHOW-PARA.
           MOVE SQLCODE TO WS-CODE
           MOVE SQLERRD(3) TO WS-ROWS
           DISPLAY WS-TAG WS-CODE WS-ROWS.
"""
_INSDEMO_JCL = _ROWDEMO_JCL.replace("ROWDEMO", "INSDEMO").replace("GGROW", "GGINS")
_INSDEMO_DDL = (
    "CREATE TABLE GGINS.ITEM (ID INTEGER NOT NULL, NAME CHAR(4) NOT NULL, QTY DECIMAL(5,2), PRIMARY KEY (ID));\n"
)
_INSDEMO_SEED = "INSERT INTO GGINS.ITEM VALUES (1, 'ZZZZ', 9.00);\n"
# per statement: tag (8), SQLCODE (10), SQLERRD(3) (10); the duplicate key is the first row: -803, nothing inserted; a
# duplicate on row 2 or the last row is -803 with the rows before it undone (ATOMIC), the count still 6
TRACED_INSERT_ROWS = "".join(
    f"{tag:<8}{code:>10}{rows:>10}\n"
    for tag, code, rows in (
        ("LIT 2", 0, 2),
        ("VAR 3", 0, 3),
        ("DUP KEY", -803, 0),
        ("DUP ROW2", -803, 0),
        ("DUP LAST", -803, 0),
        ("COUNT", 0, 6),
    )
)


def _insdemo_port(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    import det_port

    from gitgalaxy.tools.cobol_to_java.det import program as P

    estate = tmp_path / "estate"
    for rel, text in (
        ("cbl/INSDEMO.cbl", _INSDEMO_CBL),
        ("jcl/INSDEMO.jcl", _INSDEMO_JCL),
        ("ddl/ITEM.ddl", _INSDEMO_DDL),
    ):
        (estate / rel).parent.mkdir(parents=True, exist_ok=True)
        (estate / rel).write_text(text, encoding="utf-8")
    (tmp_path / "seed.sql").write_text(_INSDEMO_SEED, encoding="utf-8")
    for argv in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "e"]):
        subprocess.run(["git", "-C", str(estate), *argv], check=True)  # noqa: S603, S607
    project = det_port.estate(estate, tmp_path / "translate")  # (its own work: never inside the estate)
    stub = (project / "src/main/java" / det_port.PKG_DIR / "service" / "InsdemoService.java").read_text("utf-8")
    r = P.translate(estate / "cbl/INSDEMO.cbl", [estate / "cbl"], stub, det_port.PKG, P.estate_files(project), project)
    port = tmp_path / "port"
    (port / "service").mkdir(parents=True)
    (port / "service" / f"{r.service}.java").write_text(r.java, encoding="utf-8")
    for rel, text in P.runtime_files(det_port.PKG, P.has_batch(project)).items():
        if "/cics/" not in rel:
            (port / rel).parent.mkdir(parents=True, exist_ok=True)
            (port / rel).write_text(text, encoding="utf-8")
    return estate, r, port


@pytest.mark.slow(reason="builds an estate and runs the det-port translator (tree-sitter load, ~40 s)")
def test_insdemo_translates_every_insert_for_n_rows_with_no_holes(tmp_path):
    _estate, r, _port = _insdemo_port(tmp_path)
    assert r.stats["holes"] == []
    assert r.java.count("DetSql.insertRows(") == 5


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL, Db2) and a JDK + Maven")
def test_insdemo_det_port_proves_on_db2_against_the_hand_trace(tmp_path):
    import json

    estate, _r, port = _insdemo_port(tmp_path)
    case = {"corpus": "insert-rows-synthetic", "program": "INSDEMO", "program_source": "cbl/INSDEMO.cbl",
            "copy_dirs": [], "parm": None, "clock": "2026/10/30 10:00:00.00", "datasets": {},
            "db2": {"ddl": ["ddl/ITEM.ddl"], "seed": str(tmp_path / "seed.sql"), "compare": ["GGINS.ITEM"],
                    "compare_sql": True}}  # fmt: skip
    (tmp_path / "case.json").write_text(json.dumps(case), encoding="utf-8")
    keep = tmp_path / "proof"
    proc = subprocess.run([sys.executable, str(TOOLS / "equivalence.py"), "run", "insrows", "--case-file",  # noqa: S603
                           str(tmp_path / "case.json"), "--corpus-dir", str(estate), "--port", str(port), "--keep",
                           str(keep), "--faults", "none", "--sql-faults", "none"],
                          capture_output=True, text=True, check=False)  # fmt: skip
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-3000:]
    report = json.loads((keep / "report.json").read_text(encoding="utf-8"))
    assert report["proven"] is True
    assert (keep / "cobol" / "stdout.txt").read_text(encoding="latin-1") == TRACED_INSERT_ROWS


@pytest.mark.parametrize(
    "declare, why",
    [
        ("R1 CURSOR", "not declared WITH ROWSET POSITIONING"),
        ("R1 SCROLL CURSOR", "not declared WITH ROWSET POSITIONING"),
        ("R1 SENSITIVE SCROLL CURSOR WITH ROWSET POSITIONING", "SENSITIVE or DYNAMIC"),
    ],
)
def test_a_rowset_fetch_of_a_cursor_the_port_cannot_model_is_refused_by_name(declare, why):
    from gitgalaxy.tools.cobol_to_java.det.sql import SqlError

    with pytest.raises(SqlError, match=rf"{why}.*register Q4"):
        _scroll_sql(declare).command("EXEC SQL FETCH NEXT ROWSET FROM R1 FOR 2 ROWS INTO :A END-EXEC", 7, "")


def test_a_rowset_cursor_is_found_by_its_declaration():
    from gitgalaxy.tools.cobol_to_java.det.sql import Sql

    src = (
        "EXEC SQL DECLARE R1 CURSOR WITH HOLD WITH ROWSET POSITIONING FOR SELECT A FROM T END-EXEC. "
        "EXEC SQL DECLARE R2 CURSOR FOR SELECT A FROM T END-EXEC. "
        "EXEC SQL DECLARE R3 SCROLL CURSOR WITH ROWSET POSITIONING FOR SELECT A FROM T END-EXEC."
    )
    assert Sql(_Gen(), "P", None, src).rowset == {"R1", "R3"}


_ROWSET_MAIN = """\
package ggtest;

import ggtest.cobolrt.Field;
import ggtest.cobolrt.Storage;
import ggtest.cobolrt.sql.DetSql;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

public class Main {
    static final Charset CS = StandardCharsets.ISO_8859_1;

    static int num(Field ca, int off) {
        byte[] b = ca.storage().bytes;
        return (b[off] & 0xFF) | (b[off + 1] & 0xFF) << 8 | (b[off + 2] & 0xFF) << 16 | b[off + 3] << 24;
    }

    static void go(Field ca, String c, long n, int cap) {
        List<Map<String, Object>> rows = DetSql.fetchRowset(ca, "P:9", c, n, cap, CS);
        System.out.println(c + " " + n + " code=" + num(ca, 12) + " rows=" + rows.size() + " erd3=" + num(ca, 104));
    }

    public static void main(String[] a) {
        Field ca = Field.group(new Storage(136), 0, 136);
        DetSql.open(ca, "P:1", "R1", () -> List.of(Map.of("ID", 1), Map.of("ID", 2), Map.of("ID", 3), Map.of("ID", 4), Map.of("ID", 5)), CS);
        go(ca, "R1", 2, 3);
        go(ca, "R1", 3, 3);
        go(ca, "R1", 3, 3);
        go(ca, "R1", 1, 3);
        DetSql.close(ca, "P:2", "R1", CS);
        go(ca, "R1", 2, 3);
        DetSql.open(ca, "P:3", "R2", () -> List.of(), CS);
        go(ca, "R2", 2, 3);
        DetSql.open(ca, "P:4", "R3", () -> List.of(Map.of("ID", 1)), CS);
        for (long n : new long[] {0, 4}) {
            try {
                go(ca, "R3", n, 3);
            } catch (UnsupportedOperationException e) {
                System.out.println("refused " + n);
            }
        }
    }
}
"""


def _run_detsql_main(tmp_path, main_java):
    """Compile the det runtime beside `main_java` (ggtest.Main) with the JDK and return its stdout lines."""
    from javac_server import javac as javac_run

    rt = TOOLS.parent.parent / "gitgalaxy" / "tools" / "cobol_to_java" / "det" / "cobolrt"
    src = tmp_path / "src" / "ggtest"
    for sub in ("", "sql"):
        (src / "cobolrt" / sub).mkdir(parents=True, exist_ok=True)
        for f in (rt / sub).glob("*.java"):
            text = f.read_text(encoding="utf-8").replace("__PACKAGE__", "ggtest")
            (src / "cobolrt" / sub / f.name).write_text(text, encoding="utf-8")
    (src / "Main.java").write_text(main_java, encoding="utf-8")
    jdk = _jdk()
    files = [str(p) for p in (tmp_path / "src").rglob("*.java")]
    javac = javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"), *files],  # noqa: S603
                      capture_output=True, text=True, encoding="utf-8", check=False)  # fmt: skip
    assert javac.returncode == 0, javac.stderr[:3000]
    return subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(tmp_path / "classes"), "ggtest.Main"],  # noqa: S603
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout.splitlines()  # fmt: skip


@pytest.mark.skipif(_jdk() is None, reason="no JDK (JDK_17 / JAVA_HOME)")
def test_detsql_reads_a_rowset_and_sets_sqlerrd3_as_db2_does(tmp_path):
    out = _run_detsql_main(tmp_path, _ROWSET_MAIN)
    assert out == [
        "R1 2 code=0 rows=2 erd3=2",
        "R1 3 code=0 rows=3 erd3=3",  # rows 3, 4, 5: full
        "R1 3 code=100 rows=0 erd3=0",  # past the last row
        "R1 1 code=100 rows=0 erd3=0",
        "R1 2 code=-501 rows=0 erd3=0",  # closed
        "R2 2 code=100 rows=0 erd3=0",  # no rows
        "refused 0",
        "refused 4",
    ]


_INSERT_ROWS_MAIN = """\
package ggtest;

import ggtest.cobolrt.Field;
import ggtest.cobolrt.Storage;
import ggtest.cobolrt.sql.DetSql;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

public class Main {
    static final Charset CS = StandardCharsets.ISO_8859_1;
    static final List<String> LOG = new ArrayList<>();

    static int num(Field ca, int off) {
        byte[] b = ca.storage().bytes;
        return (b[off] & 0xFF) | (b[off + 1] & 0xFF) << 8 | (b[off + 2] & 0xFF) << 16 | b[off + 3] << 24;
    }

    static void go(String tag, long n, int failAt, boolean unit) {
        Field ca = Field.group(new Storage(136), 0, 136);
        Field cell = Field.group(new Storage(4), 0, 4);
        Field[][] hosts = {{cell, cell, cell}};
        int[] row = {0};
        LOG.clear();
        DetSql.unitOfWork(unit ? new DetSql.UnitOfWork() {
            public void commit() {}
            public void rollback() {}
            public void execute(String sql) { LOG.add(sql); }
        } : null);
        try {
            DetSql.insertRows(ca, "P:1", n, 3, "X", new String[] {"a"}, hosts, new Field[][] {null},
                    p -> { if (++row[0] == failAt) throw new IllegalStateException(new java.sql.SQLException("duplicate", "23505", -803)); return 1; }, CS);
            System.out.println(tag + " erd3=" + num(ca, 104) + " rows=" + row[0] + " " + LOG);
        } catch (UnsupportedOperationException e) {
            System.out.println(tag + " refused rows=" + row[0] + " " + LOG);
        }
        System.out.println(tag + " code=" + num(ca, 12));
    }

    public static void main(String[] a) {
        go("ok3", 3, 0, true);
        go("ok1", 1, 0, true);
        go("fail1", 3, 1, true);
        go("fail2", 3, 2, true);
        go("fail3", 3, 3, true);
        go("single", 1, 1, true);
        go("nounit_fail1", 2, 1, false);
        go("nounit_fail2", 2, 2, false);
    }
}
"""


@pytest.mark.skipif(_jdk() is None, reason="no JDK (JDK_17 / JAVA_HOME)")
def test_detsql_insert_rows_undoes_the_rows_before_a_failing_one_with_a_savepoint(tmp_path):
    sp = "SAVEPOINT GGINSROWS_UNDO ON ROLLBACK RETAIN CURSORS"
    undo = "ROLLBACK TO SAVEPOINT GGINSROWS_UNDO"
    rel = "RELEASE SAVEPOINT GGINSROWS_UNDO"
    out = _run_detsql_main(tmp_path, _INSERT_ROWS_MAIN)
    assert out == [
        f"ok3 erd3=3 rows=3 [{sp}, {rel}]",  # a whole rowset: the savepoint released
        "ok3 code=0",
        "ok1 erd3=1 rows=1 []",  # one row needs no undo
        "ok1 code=0",
        f"fail1 erd3=0 rows=1 [{sp}, {undo}, {rel}]",  # the first row: nothing inserted
        "fail1 code=-803",
        f"fail2 erd3=0 rows=2 [{sp}, {undo}, {rel}]",  # row 2 of 3: row 1 undone, row 3 never run
        "fail2 code=-803",
        f"fail3 erd3=0 rows=3 [{sp}, {undo}, {rel}]",  # the last row: rows 1 and 2 undone
        "fail3 code=-803",
        "single erd3=0 rows=1 []",
        "single code=-803",
        "nounit_fail1 erd3=0 rows=1 []",  # no unit of work: the first row is Db2's error as before
        "nounit_fail1 code=-803",
        "nounit_fail2 refused rows=2 []",  # ... a later row is refused, never answered
        "nounit_fail2 code=0",
    ]
