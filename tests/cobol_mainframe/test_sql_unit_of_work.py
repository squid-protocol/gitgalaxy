"""#4269 -- EXEC SQL COMMIT / ROLLBACK as the ends of a real Db2 unit of work, and a program name with hyphens.

IBM Db2 for z/OS SQL Reference, COMMIT and ROLLBACK statements: COMMIT ends the unit of work, committing its changes
and closing every cursor not declared WITH HOLD; ROLLBACK backs the changes out and closes every cursor; both are
invalid in CICS (-925 / -926: the unit of work is the task's). A batch step's unit of work commits when the program
ends normally and is backed out when it abends (Application Programming and SQL Guide, units of work in TSO / CAF).

The det translator emits DetSql.commit / rollback (a CICS program's ROLLBACK is refused by name, ROLLBACK TO SAVEPOINT
too); DetSql ends the runner's unit of work (DetSql.unitOfWork) and closes the cursors as Db2 does, and refuses a
ROLLBACK it has no unit of work for; the precompiler marks a WITH HOLD cursor's OPEN for ggsql.c, which closes the
others at a COMMIT and every one at a ROLLBACK; the equivalence harness runs a Db2 batch step as one unit of work.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS.parent.parent))

PROGRAM = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. NEND-DAY.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
           EXEC SQL INCLUDE SQLCA END-EXEC.
       01  WS-ID                PIC S9(9) COMP.
           EXEC SQL DECLARE C1 CURSOR FOR
               SELECT ID FROM T END-EXEC.
           EXEC SQL DECLARE C2 CURSOR
               WITH HOLD FOR SELECT ID FROM T END-EXEC.
       PROCEDURE DIVISION.
           EXEC SQL INSERT INTO T (ID) VALUES (:WS-ID) END-EXEC.
           EXEC SQL COMMIT END-EXEC.
           EXEC SQL OPEN C1 END-EXEC.
           EXEC SQL OPEN C2 END-EXEC.
           EXEC SQL ROLLBACK WORK END-EXEC.
           GOBACK.
"""

# the generator's Javadoc (cobol_to_java_db2_forge): the program name as written, hyphens kept
REPOSITORY = """package com.x.repository.db2;

public class TRepository {
    /** EXEC SQL INSERT at NEND-DAY.cbl:12 (NEND-DAY, insert access).
     *  Parameters: wsId = :WS-ID.
     *  DB2 table access field testing: open. */
    public int insertL12NendDay(java.util.Map<String, ?> params) {
        return 0;
    }

    /** EXEC SQL DECLARE CURSOR at NEND-DAY.cbl:7 (NEND-DAY, read access).
     *  OPEN at line 14.
     *  DB2 table access field testing: open. */
    public java.util.List<java.util.Map<String, Object>> cursorC1L7NendDay(java.util.Map<String, ?> params) {
        return null;
    }

    /** EXEC SQL DECLARE CURSOR at NEND-DAY.cbl:9 (NEND-DAY, read access).
     *  OPEN at line 15.
     *  DB2 table access field testing: open. */
    public java.util.List<java.util.Map<String, Object>> cursorC2L9NendDay(java.util.Map<String, ?> params) {
        return null;
    }
}
"""


def test_a_hyphenated_program_finds_its_generated_methods(tmp_path):
    from gitgalaxy.tools.cobol_to_java.det.sql import repositories

    repo = tmp_path / "com/x/repository/db2/TRepository.java"
    repo.parent.mkdir(parents=True)
    repo.write_text(REPOSITORY, encoding="utf-8")
    methods = repositories(tmp_path)
    assert methods[("NEND-DAY", 12)].name == "insertL12NendDay"
    assert methods[("NEND-DAY", 14)].name == "cursorC1L7NendDay"  # (a cursor's OPEN line)


def test_commit_and_rollback_end_the_unit_of_work_and_a_held_cursor_is_marked(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P

    prog = tmp_path / "NEND-DAY.cbl"
    prog.write_text(PROGRAM, encoding="latin-1")
    repo = tmp_path / "project/src/main/java/com/x/repository/db2/TRepository.java"
    repo.parent.mkdir(parents=True)
    repo.write_text(REPOSITORY, encoding="utf-8")
    r = P.translate(prog, [tmp_path], "public class NendDayService {\n}\n", "com.x", None, tmp_path / "project")
    assert r.stats["holes"] == []
    calls = [ln.strip() for ln in r.java.splitlines() if "DetSql." in ln and "import" not in ln]
    assert 'DetSql.commit(f1_SQLCA, "NEND-DAY:13", CS);' in calls
    assert 'DetSql.rollback(f1_SQLCA, "NEND-DAY:16", CS);' in calls
    assert any('DetSql.open(f1_SQLCA, "NEND-DAY:14", "C1", () ->' in c for c in calls)  # not held
    assert any('DetSql.open(f1_SQLCA, "NEND-DAY:15", "C2", true, () ->' in c for c in calls)  # WITH HOLD


class _Gen:
    cics = None

    def field_expr(self, ref):
        return "ca"


@pytest.mark.parametrize(
    "stmt, cics, why",
    [
        ("ROLLBACK TO SAVEPOINT S1", False, "ROLLBACK TO SAVEPOINT"),
        ("COMMIT WORK HOLD", False, "COMMIT WORK HOLD"),
        ("ROLLBACK", True, "-926"),
        ("ROLLBACK WORK", True, "-926"),
    ],
)
def test_a_unit_of_work_end_not_modelled_is_refused_by_name(stmt, cics, why):
    from gitgalaxy.tools.cobol_to_java.det.sql import Sql, SqlError

    g = _Gen()
    g.cics = object() if cics else None
    with pytest.raises(SqlError, match=why):
        Sql(g, "P", None).command(f"EXEC SQL {stmt} END-EXEC", 7, "")


def test_commit_in_a_cics_program_is_the_tasks_and_in_batch_ends_the_unit_of_work():
    from gitgalaxy.tools.cobol_to_java.det.sql import Sql

    g = _Gen()
    assert Sql(g, "P", None).command("EXEC SQL COMMIT WORK END-EXEC", 7, "") == ['DetSql.commit(ca, "P:7", CS);']
    g.cics = object()
    assert Sql(g, "P", None).command("EXEC SQL COMMIT END-EXEC", 7, "")[0].startswith("DetSql.reset(ca, CS);")


def test_the_precompiler_marks_a_held_cursors_open_for_ggsql():
    import equivalence_sql as es

    prog = PROGRAM.replace("NEND-DAY", "UOWHOLD")
    _, table = es.precompile(prog, [], Path("uowhold.cbl"), program="uowhold")
    opens = [ln for ln in table.splitlines() if ln.startswith("S ") and " OPEN " in ln]
    assert opens[0].endswith(" C1 UOWHOLD 14")
    assert opens[1].endswith(" C2 UOWHOLD 15 H")
    kinds = [ln.split()[2] for ln in table.splitlines() if ln.startswith("S ")]
    assert kinds == ["EXEC", "COMMIT", "OPEN", "OPEN", "ROLLBACK"]


def test_a_db2_batch_step_runs_as_one_unit_of_work_in_the_harness():
    import equivalence_java as ej

    case = {"name": "x", "program": "COBTUPDT", "datasets": {"INPFILE": {"input": "@case/i", "reclen": 53}},
            "clock": "2022/07/18 10:30:15.00"}  # fmt: skip
    plain = ej.equivalence_test(case)
    assert "db2Step" not in plain
    db2 = ej.equivalence_test({**case, "db2": {"ddl": []}})
    assert "db2Step(() -> {" in db2 and "step[0] = cobtupdtService.runBatch(" in db2
    assert "DataSourceTransactionManager" in db2 and 'getMethod("unitOfWork"' in db2


def _jdk() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    return Path(home) / "bin" if home and (Path(home) / "bin" / "javac").is_file() else None


MAIN = """package ggtest;

import ggtest.cobolrt.Field;
import ggtest.cobolrt.Storage;
import ggtest.cobolrt.sql.DetSql;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

public class Main {
    static final Charset CS = StandardCharsets.ISO_8859_1;

    static int sqlcode(Field ca) {
        byte[] b = ca.storage().bytes;
        return (b[12] & 0xFF) | (b[13] & 0xFF) << 8 | (b[14] & 0xFF) << 16 | b[15] << 24;
    }

    static List<Map<String, Object>> rows() {
        return List.of(Map.of("ID", 1), Map.of("ID", 2), Map.of("ID", 3));
    }

    static void fetch(Field ca, String c) {
        Map<String, Object> row = DetSql.fetch(ca, "P:9", c, CS);
        System.out.println("fetch " + c + " " + sqlcode(ca) + (row == null ? "" : " " + row.get("ID")));
    }

    public static void main(String[] a) {
        Field ca = Field.group(new Storage(136), 0, 136);
        StringBuilder log = new StringBuilder();
        // no unit of work: COMMIT has nothing more to commit; ROLLBACK cannot undo what was committed -- refused
        DetSql.commit(ca, "P:1", CS);
        System.out.println("commit alone " + sqlcode(ca));
        try {
            DetSql.rollback(ca, "P:2", CS);
            System.out.println("rollback alone answered");
        } catch (UnsupportedOperationException e) {
            System.out.println("rollback alone refused");
        }
        DetSql.unitOfWork(new DetSql.UnitOfWork() {
            public void commit() { log.append("C"); }
            public void rollback() { log.append("R"); }
        });
        // COMMIT closes C1 (not held), keeps C2 (WITH HOLD) open with no current row
        DetSql.open(ca, "P:3", "C1", Main::rows, CS);
        DetSql.open(ca, "P:4", "C2", true, Main::rows, CS);
        fetch(ca, "C1");
        fetch(ca, "C2");
        DetSql.commit(ca, "P:5", CS);
        System.out.println("commit " + sqlcode(ca));
        fetch(ca, "C1");
        DetSql.updateCurrent(ca, "P:6", "C2", rid -> 1, CS);
        System.out.println("positioned after commit " + sqlcode(ca));
        fetch(ca, "C2");
        // ROLLBACK closes every cursor, held or not
        DetSql.rollback(ca, "P:7", CS);
        System.out.println("rollback " + sqlcode(ca));
        fetch(ca, "C2");
        DetSql.close(ca, "P:8", "C2", CS);
        System.out.println("close " + sqlcode(ca));
        // Db2's own error ending the unit of work is its SQLCODE
        DetSql.unitOfWork(new DetSql.UnitOfWork() {
            public void commit() { throw new RuntimeException(new java.sql.SQLException("x", "57033", -913)); }
            public void rollback() { log.append("R"); }
        });
        DetSql.commit(ca, "P:10", CS);
        System.out.println("failed commit " + sqlcode(ca));
        // a planned SQL fault on the COMMIT (#4173): the unit of work not ended
        DetSql.withFaults(List.of("P 11 1 -911 40001"), null);
        DetSql.unitOfWork(new DetSql.UnitOfWork() {
            public void commit() { log.append("C"); }
            public void rollback() { log.append("R"); }
        });
        DetSql.commit(ca, "P:11", CS);
        System.out.println("faulted commit " + sqlcode(ca));
        System.out.println("unit " + log);
    }
}
"""


@pytest.mark.skipif(_jdk() is None, reason="no JDK (JDK_17 / JAVA_HOME)")
def test_detsql_ends_the_runners_unit_of_work_and_closes_cursors_as_db2_does(tmp_path):
    rt = TOOLS.parent.parent / "gitgalaxy" / "tools" / "cobol_to_java" / "det" / "cobolrt"
    src = tmp_path / "src" / "ggtest"
    for sub in ("", "sql"):
        (src / "cobolrt" / sub).mkdir(parents=True, exist_ok=True)
        for f in (rt / sub).glob("*.java"):
            (src / "cobolrt" / sub / f.name).write_text(f.read_text(encoding="utf-8").replace("__PACKAGE__", "ggtest"),
                                                        encoding="utf-8")  # fmt: skip
    (src / "Main.java").write_text(MAIN, encoding="utf-8")
    jdk = _jdk()
    files = [str(p) for p in (tmp_path / "src").rglob("*.java")]
    javac = subprocess.run([str(jdk / "javac"), "-nowarn", "-d", str(tmp_path / "classes"), *files],  # noqa: S603
                           capture_output=True, text=True, check=False)  # fmt: skip
    assert javac.returncode == 0, javac.stderr[:3000]
    out = subprocess.run([str(jdk / "java"), "-cp", str(tmp_path / "classes"), "ggtest.Main"],  # noqa: S603
                         capture_output=True, text=True, check=True).stdout.splitlines()  # fmt: skip
    assert out == [
        "commit alone 0",
        "rollback alone refused",
        "fetch C1 0 1",
        "fetch C2 0 1",
        "commit 0",
        "fetch C1 -501",  # closed by the COMMIT
        "positioned after commit -508",  # held, but no current row until the next FETCH
        "fetch C2 0 2",  # held: the next row
        "rollback 0",
        "fetch C2 -501",  # ROLLBACK closes a held cursor too
        "close -501",
        "failed commit -913",
        "faulted commit -911",
        "unit CR",  # the COMMIT and the ROLLBACK; the failed and the faulted COMMIT end nothing
    ]


# ---- the end-to-end proof on Db2: a synthetic estate (tests/equivalence/db2/uow), traced by hand ------------------
# No burned estate's program issues EXEC SQL ROLLBACK (the census, #4269), so UOWDEMO pins it: a change committed, two
# backed out, an error then ROLLBACK, a cursor closed by COMMIT, a WITH HOLD cursor kept by it and closed by ROLLBACK,
# and work left uncommitted -- kept at the step's normal end, backed out by an abend (INPFILE `A`). Each SQLCODE below
# is IBM's (Db2 for z/OS SQL Reference: COMMIT, ROLLBACK, FETCH -501 "the cursor is not open", INSERT -803).
UOW = Path(__file__).resolve().parents[1] / "equivalence" / "db2" / "uow"
TRACED = """A UPDATE          0
A COMMIT          0
B INSERT          0
B UPDATE          0
B ROLLBACK          0
C ROWS          3
C BAL 2      200.00
D INSERT       -803
D ROLLBACK          0
D BAL 1      111.00
E FETCH          1
E FETCH AFTER COMMIT       -501
E CLOSE       -501
F FETCH AFTER COMMIT          0
F ROW          2
F CLOSE          0
G FETCH AFTER ROLLBACK       -501
G CLOSE       -501
H DELETE          0
"""
ROWS = {"N": ["[1]|[111.00]", "[2]|[200.00]"],  # row 3's DELETE committed at the step's end
        "A": ["[1]|[111.00]", "[2]|[200.00]", "[3]|[300.00]"]}  # backed out by the abend  # fmt: skip


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL, Db2) and a JDK + Maven")
@pytest.mark.parametrize("mode", ["N", "A"])
def test_uowdemo_det_port_proves_on_db2_against_the_hand_trace(tmp_path, mode):
    import json
    import shutil

    pytest.importorskip("tree_sitter_language_pack")
    import det_port
    import equivalence_java as ej

    from gitgalaxy.tools.cobol_to_java.det import program as P

    estate = tmp_path / "estate"
    shutil.copytree(UOW, estate, ignore=shutil.ignore_patterns("seed.sql"))
    for argv in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "e"]):
        subprocess.run(["git", "-C", str(estate), *argv], check=True)  # noqa: S603, S607
    (tmp_path / "INPFILE").write_text(mode + "\n", encoding="ascii")
    case = {"corpus": "uow-synthetic", "program": "UOWDEMO", "program_source": "cbl/UOWDEMO.cbl", "copy_dirs": [],
            "parm": None, "clock": "2026/10/08 10:00:00.00",
            "datasets": {"INPFILE": {"input": str(tmp_path / "INPFILE"), "reclen": 10}},
            "db2": {"ddl": ["ddl/ACCT.ddl"], "seed": str(UOW / "seed.sql"), "compare": ["GGUOW.ACCT"],
                    "compare_sql": True}}  # fmt: skip
    (tmp_path / "case.json").write_text(json.dumps(case), encoding="utf-8")
    project = det_port.estate(estate, tmp_path / "translate")  # (its own work: never inside the estate)
    stub = (project / "src/main/java" / det_port.PKG_DIR / "service" / "UowdemoService.java").read_text("utf-8")
    r = P.translate(estate / "cbl/UOWDEMO.cbl", [estate / "cbl"], stub, det_port.PKG, P.estate_files(project), project)
    assert r.stats["holes"] == []
    port = tmp_path / "port"
    (port / "service").mkdir(parents=True)
    (port / "service" / f"{r.service}.java").write_text(r.java, encoding="utf-8")
    for rel, text in P.runtime_files(det_port.PKG, P.has_batch(project)).items():
        if "DetCics" not in rel:  # (an estate with no CICS has no cics package)
            (port / rel).parent.mkdir(parents=True, exist_ok=True)
            (port / rel).write_text(text, encoding="utf-8")
    keep = tmp_path / "proof"
    proc = subprocess.run([sys.executable, str(TOOLS / "equivalence.py"), "run", f"uow-{mode}", "--case-file",  # noqa: S603
                           str(tmp_path / "case.json"), "--corpus-dir", str(estate), "--port", str(port), "--keep",
                           str(keep), "--faults", "none", "--sql-faults", "none"],
                          capture_output=True, text=True, check=False)  # fmt: skip
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-3000:]
    report = json.loads((keep / "report.json").read_text(encoding="utf-8"))
    assert report["proven"] is True
    assert (keep / "cobol" / "stdout.txt").read_text(encoding="latin-1") == TRACED
    rows = (keep / "cobol" / "db2" / "DB2_GGUOW.ACCT").read_text(encoding="latin-1").splitlines()[1:]
    assert rows == ROWS[mode]
    table = report["outputs"]["DB2 GGUOW.ACCT"]  # compared after the abend too: Db2 backed the work out
    assert table["equal"] == table["records"] == len(ROWS[mode]) and not table["diffs"]
    assert report["abend"] == ({"cobol": "U0999", "java": "U0999"} if mode == "A" else {"cobol": None, "java": None})
