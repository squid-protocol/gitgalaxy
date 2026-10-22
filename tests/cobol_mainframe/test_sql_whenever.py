"""#4269 -- EXEC SQL WHENEVER {SQLERROR | NOT FOUND | SQLWARNING} {CONTINUE | GOTO label}.

IBM Db2 for z/OS SQL Reference, WHENEVER statement: the action is in force for the executable SQL statements that
follow it in the program's text, until another WHENEVER for the same condition; after each such statement the
precompiled program tests the SQLCA -- SQLERROR is SQLCODE < 0, NOT FOUND SQLCODE = +100, SQLWARNING SQLWARN0 = 'W' (or
another positive SQLCODE) -- and branches. CONTINUE (the default) tests nothing.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# SQLCODE (COMP-5, little-endian, offset 12 of the SQLCA) and SQLWARN0 (offset 120), read inline: no DetSql change
CODE = "java.nio.ByteBuffer.wrap(ca.storage().bytes, ca.offset() + 12, 4).order(java.nio.ByteOrder.LITTLE_ENDIAN).getInt()"  # fmt: skip
WARNED = f'ca.storage().bytes[ca.offset() + 120] == "W".getBytes(CS)[0] || ({CODE} > 0 && {CODE} != 100)'
TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS.parent.parent))


class _Gen:
    cics = None
    para_index = {"ERR-PARA": 3, "NF-PARA": 4, "WARN-PARA": 5}

    def field_expr(self, ref):
        return "ca"

    def jump(self, target):
        return f"return GOTO | {target};"


def _ex(sql, line):
    return SimpleNamespace(text=f"EXEC SQL {sql} END-EXEC", line=line)


def _sql(stmts, gen=None):
    from gitgalaxy.tools.cobol_to_java.det.sql import Sql

    s = Sql(gen or _Gen(), "P", None)
    s.scan_whenever(stmts)
    return s


def _run(s, st):
    return s.command(st.text, st.line, "")


def test_every_condition_goes_to_its_label_in_ibms_order():
    stmts = [
        _ex("WHENEVER SQLWARNING GO TO WARN-PARA", 1),
        _ex("WHENEVER NOT FOUND GOTO NF-PARA", 2),
        _ex("WHENEVER SQLERROR GO TO ERR-PARA", 3),
        _ex("COMMIT", 4),
    ]
    s = _sql(stmts)
    assert _run(s, stmts[0]) == [] and _run(s, stmts[1]) == [] and _run(s, stmts[2]) == []
    out = _run(s, stmts[3])
    assert out[0] == 'DetSql.commit(ca, "P:4", CS);'
    assert out[1:] == [
        f"if ({CODE} < 0) return GOTO | 3;",
        f"else if ({CODE} == 100) return GOTO | 4;",
        f"else if ({WARNED}) return GOTO | 5;",
    ]


def test_a_statement_before_the_whenever_and_continue_test_nothing():
    stmts = [
        _ex("COMMIT", 1),
        _ex("WHENEVER SQLERROR GO TO ERR-PARA", 2),
        _ex("COMMIT", 3),
        _ex("WHENEVER SQLERROR CONTINUE", 4),
        _ex("COMMIT", 5),
    ]
    s = _sql(stmts)
    assert len(_run(s, stmts[0])) == 1  # before the WHENEVER
    assert len(_run(s, stmts[2])) == 2  # in force
    assert len(_run(s, stmts[4])) == 1  # CONTINUE ends it


def test_a_later_whenever_for_the_same_condition_replaces_the_label_and_others_stay():
    stmts = [
        _ex("WHENEVER SQLERROR GO TO ERR-PARA", 1),
        _ex("WHENEVER NOT FOUND GO TO NF-PARA", 2),
        _ex("WHENEVER SQLERROR GO TO WARN-PARA", 3),
        _ex("SAVEPOINT SP1 ON ROLLBACK RETAIN CURSORS", 4),
    ]
    out = _run(_sql(stmts), stmts[3])
    assert out[1:] == [
        f"if ({CODE} < 0) return GOTO | 5;",
        f"else if ({CODE} == 100) return GOTO | 4;",
    ]


def test_include_and_declare_are_not_executable_and_test_nothing():
    stmts = [_ex("WHENEVER SQLERROR GO TO ERR-PARA", 1), _ex("INCLUDE SQLCA", 2),
             _ex("DECLARE C1 CURSOR FOR SELECT ID FROM T", 3)]  # fmt: skip
    s = _sql(stmts)
    assert [_run(s, x) for x in stmts[1:]] == [[], []]


@pytest.mark.parametrize(
    "stmt, why",
    [
        ("WHENEVER SQLERROR GO TO NOPE", "no such paragraph"),
        ("WHENEVER SQLERROR PERFORM X", "WHENEVER"),
        ("WHENEVER SQLERROR STOP", "WHENEVER"),
    ],
)
def test_a_whenever_not_modelled_is_refused_by_name(stmt, why):
    from gitgalaxy.tools.cobol_to_java.det.sql import SqlError

    stmts = [_ex(stmt, 1), _ex("COMMIT", 2)]
    s = _sql(stmts)
    with pytest.raises(SqlError, match=why):
        _run(s, stmts[0])
        _run(s, stmts[1])


def test_a_shared_line_number_under_two_different_whenevers_is_refused():
    from gitgalaxy.tools.cobol_to_java.det.sql import SqlError

    stmts = [_ex("COMMIT", 9), _ex("WHENEVER SQLERROR GO TO ERR-PARA", 10), _ex("COMMIT", 9)]
    s = _sql(stmts)
    with pytest.raises(SqlError, match="shared"):
        _run(s, stmts[0])


PROGRAM = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. WHEN-EVR.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
           EXEC SQL INCLUDE SQLCA END-EXEC.
       PROCEDURE DIVISION.
       MAIN-PARA.
           EXEC SQL WHENEVER SQLERROR GO TO ERR-PARA END-EXEC.
           EXEC SQL WHENEVER NOT FOUND CONTINUE END-EXEC.
           EXEC SQL COMMIT END-EXEC.
           GOBACK.
       ERR-PARA.
           GOBACK.
"""


@pytest.mark.parametrize("style", ["dispatch", "structured"])
def test_a_program_with_a_whenever_goto_translates_to_the_dispatcher(tmp_path, style):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    prog = tmp_path / "WHEN-EVR.cbl"
    prog.write_text(PROGRAM, encoding="latin-1")
    r = P.translate(prog, [tmp_path], "public class WhenEvrService {\n}\n", "com.x", None, tmp_path / "project",
                    style=style)  # fmt: skip
    assert r.stats["holes"] == [], "\n".join(r.stats["holes"])
    assert "if (java.nio.ByteBuffer.wrap(" in r.java and "return GOTO | 1;" in r.java
    assert "runAll()" not in r.java  # a WHENEVER GOTO is a GO TO: the program is not structured


def test_the_oracles_precompiler_tests_the_sqlca_after_each_statement_in_force(tmp_path):
    import equivalence_sql as ES

    src = PROGRAM.replace(
        "EXEC SQL WHENEVER NOT FOUND CONTINUE END-EXEC.", "EXEC SQL WHENEVER SQLWARNING GO TO ERR-PARA END-EXEC."
    )
    src = src.replace(
        "           EXEC SQL COMMIT END-EXEC.\n",
        "           EXEC SQL COMMIT END-EXEC.\n           EXEC SQL WHENEVER SQLERROR CONTINUE END-EXEC.\n           EXEC SQL COMMIT END-EXEC.\n",
    )
    prog = tmp_path / "WHEN-EVR.cbl"
    prog.write_text(src, encoding="latin-1")
    out, _ = ES.precompile(src, [tmp_path], prog, 1, "WHEN-EVR")
    lines = [ln.strip() for ln in out.splitlines()]
    first = lines.index("IF SQLCODE < 0")
    assert lines[first : first + 7] == [
        "IF SQLCODE < 0",
        "GO TO ERR-PARA",
        "ELSE IF SQLWARN0 = 'W' OR",
        "(SQLCODE > 0 AND SQLCODE NOT = 100)",
        "GO TO ERR-PARA",
        "END-IF",
        "END-IF.",
    ]
    assert lines.count("IF SQLCODE < 0") == 1  # the second COMMIT is past WHENEVER SQLERROR CONTINUE
    assert "IF SQLWARN0 = 'W' OR" in lines


def test_the_oracles_precompiler_refuses_a_whenever_it_does_not_model(tmp_path):
    import equivalence_sql as ES

    src = PROGRAM.replace("GO TO ERR-PARA END-EXEC", "STOP END-EXEC", 1)
    prog = tmp_path / "WHEN-EVR.cbl"
    prog.write_text(src, encoding="latin-1")
    with pytest.raises(ES.Unsupported, match="WHENEVER"):
        ES.precompile(src, [tmp_path], prog, 1, "WHEN-EVR")


# ---- the end-to-end proof on Db2: a synthetic estate (tests/equivalence/db2/whenever) ------------------------------
# No burned estate's program issues EXEC SQL WHENEVER (the census, #4269), so WHENDEMO pins it: NOT FOUND and SQLERROR
# branches taken, CONTINUE cancelling them, and SQLWARNING (a CHAR(10) truncated into PIC X(3)).
WHEN = Path(__file__).resolve().parents[1] / "equivalence" / "db2" / "whenever"
TRACED = """A FOUND
B NOT FOUND        100
B CONTINUE        100
C ERROR       -803
D CONTINUE       -803
E WARNING          0 ABC
"""


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL, Db2) and a JDK + Maven")
def test_whendemo_det_port_proves_on_db2(tmp_path):
    import json
    import shutil

    pytest.importorskip("tree_sitter_language_pack")
    import det_port

    from gitgalaxy.tools.cobol_to_java.det import program as P

    estate = tmp_path / "estate"
    shutil.copytree(WHEN, estate, ignore=shutil.ignore_patterns("seed.sql"))
    for argv in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "e"]):
        subprocess.run(["git", "-C", str(estate), *argv], check=True)  # noqa: S603, S607
    case = {"corpus": "whenever-synthetic", "program": "WHENDEMO", "program_source": "cbl/WHENDEMO.cbl",
            "copy_dirs": [], "parm": None, "clock": "2026/10/08 10:00:00.00", "datasets": {},
            "db2": {"ddl": ["ddl/WTAB.ddl"], "seed": str(WHEN / "seed.sql"), "compare": ["GGWHEN.WTAB"],
                    "compare_sql": True}}  # fmt: skip
    (tmp_path / "case.json").write_text(json.dumps(case), encoding="utf-8")
    project = det_port.estate(estate, tmp_path / "translate")
    stub = (project / "src/main/java" / det_port.PKG_DIR / "service" / "WhendemoService.java").read_text("utf-8")
    r = P.translate(estate / "cbl/WHENDEMO.cbl", [estate / "cbl"], stub, det_port.PKG, P.estate_files(project), project)
    assert r.stats["holes"] == []
    port = tmp_path / "port"
    (port / "service").mkdir(parents=True)
    (port / "service" / f"{r.service}.java").write_text(r.java, encoding="utf-8")
    for rel, text in P.runtime_files(det_port.PKG, P.has_batch(project)).items():
        if "/cics/" not in rel:  # (an estate with no CICS has no cics package)
            (port / rel).parent.mkdir(parents=True, exist_ok=True)
            (port / rel).write_text(text, encoding="utf-8")
    keep = tmp_path / "proof"
    proc = subprocess.run([sys.executable, str(TOOLS / "equivalence.py"), "run", "whenever", "--case-file",  # noqa: S603
                           str(tmp_path / "case.json"), "--corpus-dir", str(estate), "--port", str(port), "--keep",
                           str(keep), "--faults", "none", "--sql-faults", "none"],
                          capture_output=True, text=True, check=False)  # fmt: skip
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-3000:]
    report = json.loads((keep / "report.json").read_text(encoding="utf-8"))
    assert report["proven"] is True
    assert (keep / "cobol" / "stdout.txt").read_text(encoding="latin-1") == TRACED
