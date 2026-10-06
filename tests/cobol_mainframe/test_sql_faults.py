"""#4173 -- SQL faults in the equivalence harness, and #4181 -- a LINK COMMAREA never read past its caller's record.

The precompiler keys each statement by its program and its EXEC SQL's own line (the det port's DetSql calls carry the
same key); a scenario's `sql_faults` resolve to those keys; the harness enumerates one fault task per statement a
case's tasks executed; the det runtime (DetSql) injects a planned fault exactly as the COBOL side's stub does
(tests/equivalence/db2/ggsql.c), and Cobol.commarea gives a LINK target the caller's bytes up to the end of its record.
"""

from __future__ import annotations

import base64
import os
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS.parent.parent))

import equivalence_cics as ec  # noqa: E402
import equivalence_sql as es  # noqa: E402

PROGRAM = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. SQLKEY.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
           EXEC SQL INCLUDE SQLCA END-EXEC.
       01  WS-N                 PIC S9(9) COMP.
       PROCEDURE DIVISION.
           EXEC SQL
             INSERT INTO T (C) VALUES (:WS-N)
           END-EXEC.
           EXEC SQL INCLUDE SQLPROC END-EXEC.
           GOBACK.
"""
MEMBER = """           EXEC SQL
             SELECT C INTO :WS-N FROM T
           END-EXEC.
"""


def _table(tmp_path: Path) -> str:
    (tmp_path / "SQLPROC.cpy").write_text(MEMBER, encoding="latin-1")
    _, table = es.precompile(PROGRAM, [tmp_path], tmp_path / "sqlkey.cbl", program="sqlkey")
    return table


def test_each_statement_is_keyed_by_its_program_and_its_exec_sqls_own_line(tmp_path):
    stmts = ec.sql_statements(_table(tmp_path))
    assert [(s["program"], s["line"], s["kind"]) for s in stmts] == [("SQLKEY", 8, "EXEC"), ("SQLKEY", 1, "SELECT1")]
    # (an INCLUDEd member's statement: its line in the member, as the det port numbers it)


def test_a_fault_names_its_statement_by_line_or_by_table_and_verb(tmp_path):
    table = _table(tmp_path)
    case = {"program": "SQLKEY"}
    by_line = {"name": "s", "sql_faults": [{"line": 8, "sqlcode": -803}]}
    assert ec.sql_fault_plan(case, by_line, table) == ["SQLKEY 8 1 -803 23505"]
    by_table = {"name": "s", "sql_faults": [{"table": "T", "verb": "SELECT", "nth": "*", "sqlcode": 100}]}
    assert ec.sql_fault_plan(case, by_table, table) == ["SQLKEY 1 * 100 02000"]
    with pytest.raises(ec.Unsupported):  # an SQLCODE with no known SQLSTATE needs one
        ec.sql_fault_plan(case, {"name": "s", "sql_faults": [{"line": 8, "sqlcode": -999}]}, table)
    with pytest.raises(ec.Unsupported):  # a statement nothing in the program has
        ec.sql_fault_plan(case, {"name": "s", "sql_faults": [{"line": 99, "sqlcode": -803}]}, table)


def test_each_kind_of_statement_meets_its_own_usual_failure():
    assert ec.default_fault({"kind": "EXEC", "sql": "INSERT INTO T VALUES (?)"}) == -803
    assert ec.default_fault({"kind": "EXEC", "sql": "UPDATE T SET C = ?"}) == -913
    assert ec.default_fault({"kind": "SELECT1", "sql": "SELECT C FROM T"}) == 100
    assert ec.default_fault({"kind": "SELECT1", "sql": "VALUES (IDENTITY_VAL_LOCAL())"}) is None  # SET :H = VALUES
    assert ec.default_fault({"kind": "OPEN", "sql": "SELECT C FROM T"}) == -913
    assert ec.default_fault({"kind": "CLOSE", "sql": ""}) is None


def test_one_fault_task_per_statement_the_tasks_executed_first_task_first(tmp_path):
    (tmp_path / "stmts.txt").write_text(_table(tmp_path), encoding="latin-1")
    case = {"scenarios": [{"name": "a"}, {"name": "b"}]}
    for name, trace in (("a", "SQLKEY 8\nSQLKEY 8\n"), ("b", "SQLKEY 8\nSQLKEY 1\n")):
        (tmp_path / "scenarios" / name).mkdir(parents=True)
        (tmp_path / "scenarios" / name / "sqltrace.txt").write_text(trace, encoding="ascii")
    derived = ec.enumerated_sql_faults(case, tmp_path)
    assert [(d["name"], d["sql_faults"][0]["sqlcode"]) for d in derived] == [
        ("a--sql-sqlkey-8", -803),
        ("b--sql-sqlkey-1", 100),
    ]
    assert all(d["derived"] for d in derived)


def test_a_task_that_links_to_a_program_not_run_is_judged_up_to_that_link():
    events = [{"event": "LINK", "program": "A"}, {"event": "LINK", "program": "LGSTSQ"}, {"event": "RETURN"}]
    assert ec._to_link(events, "LGSTSQ") == events[:2]
    area = b"01011900 105655 LGACDB01"
    res = {"links": [{"target": "LGSTSQ", "data": area}]}
    same = [{"event": "LINK", "target": "LGSTSQ", "area": base64.b64encode(area).decode()}]
    assert ec._link_area({}, res, same, "LGSTSQ")["equal"] is True
    other = [{"event": "LINK", "target": "LGSTSQ", "area": base64.b64encode(area[9:]).decode()}]
    assert ec._link_area({}, res, other, "LGSTSQ")["equal"] is False


def _jdk() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    return Path(home) / "bin" if home and (Path(home) / "bin" / "javac").is_file() else None


MAIN = """package ggtest;

import ggtest.cobolrt.Cobol;
import ggtest.cobolrt.Field;
import ggtest.cobolrt.Storage;
import ggtest.cobolrt.sql.DetSql;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.List;

public class Main {
    static int sqlcode(Field ca) {
        byte[] b = ca.storage().bytes;
        return (b[12] & 0xFF) | (b[13] & 0xFF) << 8 | (b[14] & 0xFF) << 16 | b[15] << 24;
    }

    public static void main(String[] a) throws Exception {
        Field ca = Field.group(new Storage(136), 0, 136);
        int[] ran = {0};
        DetSql.withFaults(List.of("PROG 12 2 -803 23505"), Path.of(a[0]));
        for (int i = 1; i <= 3; i++) {
            DetSql.update(ca, "PROG:12", () -> { ran[0]++; return 1; }, false, StandardCharsets.ISO_8859_1);
            System.out.println("run " + i + " sqlcode " + sqlcode(ca) + " ran " + ran[0]);
        }
        DetSql.update(ca, "PROG:13", () -> 1, false, StandardCharsets.ISO_8859_1);  // another statement: no fault
        System.out.println("other sqlcode " + sqlcode(ca));
        // #4181: a 71-byte record LINKed as a 99-byte DTO: its own bytes, LOW-VALUES past it, and back up to its end
        Storage rec = new Storage(71);
        java.util.Arrays.fill(rec.bytes, (byte) 'E');
        Field area = Field.group(rec, 0, 71);
        Storage w = Cobol.commarea(area, 99);
        System.out.println("window " + (char) w.bytes[0] + (char) w.bytes[70] + " " + w.bytes[71] + " " + w.bytes[98]);
        w.bytes[0] = 'X';
        w.bytes[98] = 'Y';
        Cobol.commareaBack(w, area);
        System.out.println("back " + (char) rec.bytes[0] + " " + rec.bytes.length);
    }
}
"""


@pytest.mark.skipif(_jdk() is None, reason="no JDK (JDK_17 / JAVA_HOME)")
def test_detsql_injects_a_planned_fault_and_a_link_window_stops_at_the_record(tmp_path):
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
    log = tmp_path / "fired"
    out = subprocess.run([str(jdk / "java"), "-cp", str(tmp_path / "classes"), "ggtest.Main", str(log)],  # noqa: S603
                         capture_output=True, text=True, check=True).stdout.splitlines()  # fmt: skip
    assert out == ["run 1 sqlcode 0 ran 1", "run 2 sqlcode -803 ran 1", "run 3 sqlcode 0 ran 2",
                   "other sqlcode 0", "window EE 0 0", "back X 71"]  # fmt: skip
    assert log.read_text(encoding="ascii").split() == ["SQL", "PROG", "12", "2", "-803"]


def _service(src, cls, body):
    d = src / "com" / "x" / "service"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{cls}.java").write_text(f"class {cls} {{ void p() {{ {body} }} }}\n", encoding="utf-8")


def test_sql_seam_is_decided_per_statement_owner(tmp_path):
    """#4173 x #4188: a model-ported main program has no seam even when a det-ported program it LINKs to puts
    DetSql on the classpath; a fault on the det program's own statement can be injected and judged."""
    import equivalence_cics as ec

    src = tmp_path / "src"
    _service(src, "InqaccService", "repo.findById(1);")  # model port: its own Db2 access
    _service(src, "AbndprocService", 'DetSql.update("ABNDPROC:120", s);')  # det port, LINKed
    case = {"program": "INQACC", "programs": [{"program": "ABNDPROC", "program_source": "src/abndproc.cbl"}]}
    seams = ec.sql_seam_programs(case, src)
    assert seams == {"ABNDPROC"}
    main_fault = ec.sql_unjudged(["INQACC 270 1 -913 57033"], seams)
    assert "no SQL fault hook" in main_fault and "INQACC" in main_fault  # not judged
    assert ec.sql_unjudged(["ABNDPROC 120 1 -803 23505"], seams) == ""  # injected and judged
    assert "INQACC" in ec.sql_unjudged(["ABNDPROC 120 1 -803 23505", "INQACC 270 1 100 02000"], seams)
    assert ec.sql_unjudged([], set()) == ""  # no faults: nothing to refuse


def test_a_det_main_program_has_the_seam(tmp_path):
    import equivalence_cics as ec

    src = tmp_path / "src"
    _service(src, "Lgacdb01Service", 'DetSql.update("LGACDB01:240", s);')
    assert ec.sql_seam_programs({"program": "LGACDB01"}, src) == {"LGACDB01"}


BINARY_MAIN = """package ggtest;

import ggtest.cobolrt.Cobol;
import ggtest.cobolrt.Field;
import ggtest.cobolrt.Storage;
import ggtest.cobolrt.sql.DetSql;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;

public class Main {
    static int sqlcode(Field ca) {
        byte[] b = ca.storage().bytes;
        return (b[12] & 0xFF) | (b[13] & 0xFF) << 8 | (b[14] & 0xFF) << 16 | b[15] << 24;
    }

    static void run(String label, int digits, boolean signed, boolean nativeBin, boolean trunc, String value) {
        Field ca = Field.group(new Storage(136), 0, 136);
        Field host = Field.binary(new Storage(8), 0, digits, 0, signed, nativeBin);
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("C", new BigDecimal(value));
        boolean before = Cobol.swapTruncBinary(trunc);
        boolean ok = DetSql.into(ca, row, "N", new Field[] {host}, new Field[1], null, StandardCharsets.ISO_8859_1);
        boolean after = Cobol.swapTruncBinary(before);
        System.out.println(label + " " + value + " sqlcode " + sqlcode(ca) + " ok " + ok + " trunc-kept " + after
                + (ok ? " holds " + Cobol.num(host, StandardCharsets.ISO_8859_1) : ""));
    }

    public static void main(String[] a) {
        for (boolean trunc : new boolean[] {true, false}) {
            for (String v : new String[] {"2147483647", "-2147483648", "2147483648", "-2147483649"}) {
                run("S9(9)COMP/" + trunc, 9, true, false, trunc, v);
            }
            for (String v : new String[] {"32767", "-32768", "32768", "-32769"}) {
                run("S9(4)COMP/" + trunc, 4, true, false, trunc, v);
            }
            for (String v : new String[] {"9223372036854775807", "9223372036854775808"}) {
                run("S9(18)COMP/" + trunc, 18, true, false, trunc, v);
            }
            for (String v : new String[] {"2147483647", "2147483648"}) {
                run("S9(9)COMP-5/" + trunc, 9, true, true, trunc, v);
            }
        }
    }
}
"""


def _binary_run(tmp_path):
    rt = TOOLS.parent.parent / "gitgalaxy" / "tools" / "cobol_to_java" / "det" / "cobolrt"
    src = tmp_path / "src" / "ggtest"
    for sub in ("", "sql"):
        (src / "cobolrt" / sub).mkdir(parents=True, exist_ok=True)
        for f in (rt / sub).glob("*.java"):
            (src / "cobolrt" / sub / f.name).write_text(f.read_text(encoding="utf-8").replace("__PACKAGE__", "ggtest"),
                                                        encoding="utf-8")  # fmt: skip
    (src / "Main.java").write_text(BINARY_MAIN, encoding="utf-8")
    jdk = _jdk()
    files = [str(p) for p in (tmp_path / "src").rglob("*.java")]
    javac = subprocess.run([str(jdk / "javac"), "-nowarn", "-d", str(tmp_path / "classes"), *files],  # noqa: S603
                           capture_output=True, text=True, check=False)  # fmt: skip
    assert javac.returncode == 0, javac.stderr[:3000]
    return subprocess.run([str(jdk / "java"), "-cp", str(tmp_path / "classes"), "ggtest.Main"],  # noqa: S603
                          capture_output=True, text=True, check=True).stdout.splitlines()  # fmt: skip


@pytest.mark.skipif(_jdk() is None, reason="no JDK (JDK_17 / JAVA_HOME)")
def test_detsql_assigns_a_binary_host_variable_by_its_bytes_not_its_picture_digits(tmp_path):
    """#4579: SELECT INTO a COMP host variable -- -304 only beyond the halfword / fullword / doubleword, under TRUNC(STD)
    and TRUNC(BIN) alike (Db2 types the host variable by its length); the program's TRUNC is left as it was."""
    out = _binary_run(tmp_path)
    for trunc in ("true", "false"):
        want = [
            f"S9(9)COMP/{trunc} 2147483647 sqlcode 0 ok true trunc-kept {trunc} holds 2147483647",
            f"S9(9)COMP/{trunc} -2147483648 sqlcode 0 ok true trunc-kept {trunc} holds -2147483648",
            f"S9(9)COMP/{trunc} 2147483648 sqlcode -304 ok false trunc-kept {trunc}",
            f"S9(9)COMP/{trunc} -2147483649 sqlcode -304 ok false trunc-kept {trunc}",
            f"S9(4)COMP/{trunc} 32767 sqlcode 0 ok true trunc-kept {trunc} holds 32767",
            f"S9(4)COMP/{trunc} -32768 sqlcode 0 ok true trunc-kept {trunc} holds -32768",
            f"S9(4)COMP/{trunc} 32768 sqlcode -304 ok false trunc-kept {trunc}",
            f"S9(4)COMP/{trunc} -32769 sqlcode -304 ok false trunc-kept {trunc}",
            f"S9(18)COMP/{trunc} 9223372036854775807 sqlcode 0 ok true trunc-kept {trunc} holds 9223372036854775807",
            f"S9(18)COMP/{trunc} 9223372036854775808 sqlcode -304 ok false trunc-kept {trunc}",
            f"S9(9)COMP-5/{trunc} 2147483647 sqlcode 0 ok true trunc-kept {trunc} holds 2147483647",
            f"S9(9)COMP-5/{trunc} 2147483648 sqlcode -304 ok false trunc-kept {trunc}",
        ]
        assert [line for line in out if f"/{trunc} " in line] == want
