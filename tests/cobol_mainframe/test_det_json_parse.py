"""#7524 slice 2 (register X77): JSON PARSE into a group of DISPLAY items is translated from IBM's text alone (the
oracle has no JSON statement). The runtime is run on bytes; each shape IBM defines but the model does not is refused
by name."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "tools"))

pytest.importorskip("tree_sitter_language_pack")

from javac_server import javac as javac_run  # noqa: E402

from gitgalaxy.tools.cobol_to_java.det import program as P  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import stmt as S  # noqa: E402


def _jdk() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    return Path(home) / "bin" if home and (Path(home) / "bin/javac").is_file() else None


DATA = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. PROG.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  REC.
           05  CUST-NAME  PIC X(8) VALUE 'Ann'.
           05  FILLER     PIC X.
           05  AMT        PIC S9(3)V99 VALUE -12.5.
           05  ADDR.
               10  CITY   PIC X(4) VALUE 'Rome'.
       01  OUT  PIC X(100).
       01  JIN  PIC X(100).
       PROCEDURE DIVISION.
"""


def _translate(tmp_path, *body: str):
    src = tmp_path / "PROG.cbl"
    src.write_text(DATA + "".join(f"           {b}\n" for b in body) + "           GOBACK.\n", encoding="utf-8")
    return P.translate(src, [], "public class ProgService { }", "t")


def test_a_group_receiver_is_a_runtime_call_with_its_members_in_storage_order(tmp_path):
    r = _translate(tmp_path, "JSON PARSE JIN INTO REC WITH DETAIL")
    assert r.stats["holes"] == []
    line = next(x for x in r.java.splitlines() if "JsonParse.parse" in x)
    assert 'group("REC"' in line and 'text("CUST-NAME"' in line and 'number("AMT"' in line and 'group("ADDR"' in line
    assert "FILLER" not in line


def test_name_of_and_suppress_shape_the_members(tmp_path):
    r = _translate(tmp_path, "JSON PARSE JIN INTO REC NAME OF CUST-NAME IS 'who'", "    SUPPRESS AMT", "    END-JSON")
    line = next(x for x in r.java.splitlines() if "JsonParse.parse" in x)
    assert 'text("who"' in line and "AMT" not in line and 'group("ADDR"' in line


@pytest.mark.parametrize(
    "stmt, why",
    [
        ("JSON PARSE JIN INTO REC SUPPRESS AMT WHEN ZERO", "SUPPRESS ... WHEN / EVERY"),
        ("JSON PARSE JIN INTO REC NAME OF AMT IS OMITTED", "NAME needs an alphanumeric literal"),
        ("JSON PARSE JIN INTO REC IGNORING ALL NULL", "IGNORING phrase"),
    ],
)
def test_a_shape_the_model_does_not_take_is_refused_by_name(tmp_path, stmt, why):
    r = _translate(tmp_path, stmt)
    assert len(r.stats["holes"]) == 1
    hole = str(r.stats["holes"][0])
    assert "JSON PARSE (Enterprise COBOL 6.1+): not modelled" in hole and why in hole


NUMS = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. PROG.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  REC.
           05  BIN-N    PIC S9(4) COMP.
           05  PK-N     PIC S9(5)V99 COMP-3.
           05  NAT-N    PIC 9(9) COMP-5.
           05  PD-N     PIC 9(3) PACKED-DECIMAL.
       01  TBL.
           05  PK-T     PIC 9(3) COMP-3 OCCURS 2.
       01  JIN  PIC X(100).
       PROCEDURE DIVISION.
"""


def _nums(tmp_path, *body: str):
    src = tmp_path / "PROG.cbl"
    src.write_text(NUMS + "".join(f"           {b}\n" for b in body) + "           GOBACK.\n", encoding="utf-8")
    return P.translate(src, [], "public class ProgService { }", "t")


def test_comp_comp3_and_comp5_numbers_are_translated_for_parse(tmp_path):
    r = _nums(tmp_path, "JSON PARSE JIN INTO REC")
    assert r.stats["holes"] == []
    line = next(x for x in r.java.splitlines() if "JsonParse.parse" in x)
    for name in ("BIN-N", "PK-N", "NAT-N", "PD-N"):
        assert f'number("{name}"' in line


def test_a_fixed_table_is_an_array_node_with_one_element_per_occurrence(tmp_path):
    r = _nums(tmp_path, "JSON PARSE JIN INTO TBL")
    assert r.stats["holes"] == [] and 'array("PK-T"' in r.java
    r = _translate_tbl(tmp_path, "JSON PARSE JIN INTO REC")
    assert r.stats["holes"] == []
    line = next(x for x in r.java.splitlines() if "JsonParse.parse" in x)
    assert line.count('number("", ') == 2 and 'array("T"' in line and line.count('group("", ') == 2
    assert 'array("ROWS"' in line


def test_an_occurs_depending_on_table_is_a_table_node_read_at_the_odo_objects_count(tmp_path):
    r = _translate_tbl(tmp_path, "JSON PARSE JIN INTO ODOREC")
    assert r.stats["holes"] == []
    line = next(x for x in r.java.splitlines() if "JsonParse.parse" in x)
    assert 'JsonParse.table("OT", ' in line and '1, "CNT"' in line and line.count('number("", ') == 3
    assert 'number("CNT"' in line  # the ODO object is an ordinary member: the statement does not update it itself


def test_an_odo_group_table_and_an_odo_inside_a_table_are_split_by_what_ibm_states(tmp_path):
    r = _translate_tbl(tmp_path, "JSON PARSE JIN INTO ODOGRP")
    assert r.stats["holes"] == []
    assert 'JsonParse.table("RW", ' in next(x for x in r.java.splitlines() if "JsonParse.parse" in x)
    r = _translate_tbl(tmp_path, "JSON PARSE JIN INTO ODOIN")
    assert len(r.stats["holes"]) == 1 and "inside another table" in str(r.stats["holes"][0])


def test_a_comp1_or_comp2_receiver_is_a_floating_node(tmp_path):
    r = _translate_tbl(tmp_path, "JSON PARSE JIN INTO FLREC")
    assert r.stats["holes"] == []
    line = next(x for x in r.java.splitlines() if "JsonParse.parse" in x)
    assert 'floating("F1", ' in line and 'floating("", ' in line  # a COMP-1 item and a COMP-1 table element
    r = _translate_tbl(tmp_path, "JSON PARSE JIN INTO FL2REC")
    assert r.stats["holes"] == []
    line = next(x for x in r.java.splitlines() if "JsonParse.parse" in x)
    assert line.count("floating(") == 3 and 'floating("F2", ' in line and 'floating("", ' in line  # item and table


TBLS = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. PROG.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  REC.
           05  T      PIC 9(3) OCCURS 2.
           05  ROWS   OCCURS 2.
               10  RN PIC X(2).
       01  ODOREC.
           05  CNT    PIC 9.
           05  OT     PIC 9 OCCURS 1 TO 3 DEPENDING ON CNT.
       01  ODOGRP.
           05  GC     PIC 9.
           05  RW     OCCURS 1 TO 3 DEPENDING ON GC.
               10  RV PIC 9.
       01  ODOIN.
           05  IC     PIC 9.
           05  OUTR   OCCURS 2.
               10  IN2 PIC 9 OCCURS 1 TO 3 DEPENDING ON IC.
       01  FLREC.
           05  F1     COMP-1.
           05  FT     COMP-1 OCCURS 2.
       01  FL2REC.
           05  F2     COMP-2.
           05  F2T    COMP-2 OCCURS 2.
       01  JIN  PIC X(100).
       PROCEDURE DIVISION.
"""


def _translate_tbl(tmp_path, *body: str):
    src = tmp_path / "PROG.cbl"
    src.write_text(TBLS + "".join(f"           {b}\n" for b in body) + "           GOBACK.\n", encoding="utf-8")
    return P.translate(src, [], "public class ProgService { }", "t")


@pytest.mark.skipif(_jdk() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_the_runtime_stores_packed_and_binary_numbers(tmp_path):
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_SPEC_JAVA, CICS_TASK_JAVA

    src = tmp_path / "src"
    files = {"t/cics/CicsTask.java": CICS_TASK_JAVA.replace("__PACKAGE__", "t").replace("__ZONE__", "UTC"),
             "t/cics/CicsSpec.java": CICS_SPEC_JAVA.replace("__PACKAGE__", "t"),
             **{f"t/{k}": v for k, v in P.runtime_files("t", batch=False).items()}}  # fmt: skip
    files["Main.java"] = """
import java.nio.charset.Charset;
import t.cobolrt.Field;
import t.cobolrt.JsonParse;
import t.cobolrt.Storage;
public class Main {
    static Charset CS = Charset.forName("ISO-8859-1");
    static String hex(Storage st, int off, int n) {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < n; i++) b.append(String.format("%02X", st.bytes[off + i] & 0xFF));
        return b.toString();
    }
    static void run(String json, boolean tryIt) {
        Storage st = new Storage(300);
        byte[] j = json.getBytes(CS);
        System.arraycopy(j, 0, st.bytes, 100, j.length);
        for (int i = j.length; i < 100; i++) st.bytes[100 + i] = ' ';
        try {
            Field in = Field.alphanumeric(st, 100, 100, false);
            Field p = Field.packed(st, 0, 5, 2, true);
            Field b = Field.binary(st, 10, 4, 0, true, false);
            Field u = Field.packed(st, 20, 3, 0, false);
            JsonParse.Node g = JsonParse.group("G", JsonParse.number("P", p), JsonParse.number("B", b), JsonParse.number("U", u));
            if (tryIt) {
                boolean exc = JsonParse.tryParse(in, g, CS);
                System.out.println((exc ? "EXC " : "OK ") + hex(st, 0, 3) + " " + hex(st, 10, 2) + " " + hex(st, 20, 2));
            } else {
                JsonParse.parse(in, g, CS);
                System.out.println(hex(st, 0, 3) + " " + hex(st, 10, 2) + " " + hex(st, 20, 2));
            }
        } catch (RuntimeException e) {
            System.out.println("HOLE " + e.getMessage());
        }
    }
    public static void main(String[] x) {
        run("{\\"P\\":-123.45,\\"B\\":-12,\\"U\\":7}", false);
        run("{\\"P\\":1000.00}", true);
        run("{\\"B\\":10000}", true);
        run("{\\"U\\":-1}", true);
        run("{\\"U\\":1.5}", true);
    }
}
"""
    for rel, text in files.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text, encoding="utf-8")
    jdk = _jdk()
    built = javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"),
                       *map(str, src.rglob("*.java"))], capture_output=True, text=True, encoding="utf-8", check=False)  # fmt: skip
    assert built.returncode == 0, built.stderr
    out = subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(tmp_path / "classes"), "Main"],  # noqa: S603
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout.splitlines()  # fmt: skip
    assert out[0] == "12345D FFF4 007F", out[0]
    # 1000.00 does not fit S9(5)V99; 10000 not S9(4): IBM stores it anyway (JSON-STATUS 128), the stored form is unstated
    assert out[1].startswith("HOLE") and "does not fit" in out[1] and out[2].startswith("HOLE")
    assert out[3].startswith("HOLE") and "unsigned" in out[3]
    assert out[4].startswith("HOLE") and "decimals" in out[4]


@pytest.mark.parametrize("item", ["CUST-NAME", "AMT", "CITY OF ADDR"])
def test_an_elementary_receiver_is_refused_by_name(tmp_path, item):
    # IBM (JSON PARSE, identifier-2): "the group or elementary data item to be populated"; the pages state no mapping of
    # a top-level JSON value (or a name) to an elementary item, so it stays refused by name (X77)
    r = _translate(tmp_path, f"JSON PARSE JIN INTO {item}")
    assert len(r.stats["holes"]) == 1
    assert "is not a plain group (IBM allows an elementary receiver but its pages do not say" in r.stats["holes"][0]


def test_the_statement_parses_every_phrase_ibm_names():
    st = S._json_parse("JSON PARSE A WITH DETAIL INTO R NAME OF C IS 'c' D IS 'd' SUPPRESS E F END-JSON", 1)
    assert st.kind == "JSONPARSE" and st.data["detail"]
    assert [lit for _, lit in st.data["names"]] == ["c", "d"] and len(st.data["suppress"]) == 2


@pytest.mark.skipif(_jdk() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_the_runtime_reads_ibms_text_and_stops_where_ibm_is_silent(tmp_path):
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_SPEC_JAVA, CICS_TASK_JAVA

    src = tmp_path / "src"
    files = {"t/cics/CicsTask.java": CICS_TASK_JAVA.replace("__PACKAGE__", "t").replace("__ZONE__", "UTC"),
             "t/cics/CicsSpec.java": CICS_SPEC_JAVA.replace("__PACKAGE__", "t"),
             **{f"t/{k}": v for k, v in P.runtime_files("t", batch=False).items()}}  # fmt: skip
    files["Main.java"] = """
import java.nio.charset.Charset;
import t.cobolrt.Field;
import t.cobolrt.JsonParse;
import t.cobolrt.Storage;
public class Main {
    static Charset CS = Charset.forName("ISO-8859-1");
    static void run(String name, String json, int digits, int scale, boolean signed) {
        Storage st = new Storage(300);
        byte[] j = json.getBytes(CS);
        System.arraycopy(j, 0, st.bytes, 100, j.length);
        for (int i = j.length; i < 100; i++) st.bytes[100 + i] = ' ';
        for (int i = 0; i < 8; i++) st.bytes[i] = '#';
        for (int i = 0; i < 6; i++) st.bytes[50 + i] = '9';
        try {
            Field in = Field.alphanumeric(st, 100, 100, false);
            Field a = Field.alphanumeric(st, 0, 8, false);
            Field b = Field.zoned(st, 50, digits, scale, signed, false, false);
            JsonParse.parse(in, JsonParse.group("G", JsonParse.text("A-B", a), JsonParse.number("N", b)), CS);
            System.out.println("[" + new String(st.bytes, 0, 8, CS) + "][" + new String(st.bytes, 50, digits, CS) + "]");
        } catch (RuntimeException e) {
            System.out.println(name + " refused: " + e.getMessage());
        }
    }
    static void tryRun(String json, boolean wantCode, boolean wantStat) {
        int digits = 3, scale = 0;
        boolean signed = false;
        Storage st = new Storage(300);
        byte[] j = json.getBytes(CS);
        System.arraycopy(j, 0, st.bytes, 100, j.length);
        for (int i = j.length; i < 100; i++) st.bytes[100 + i] = ' ';
        for (int i = 0; i < 8; i++) st.bytes[i] = '#';
        for (int i = 0; i < 6; i++) st.bytes[50 + i] = '9';
        try {
            Field in = Field.alphanumeric(st, 100, 100, false);
            Field a = Field.alphanumeric(st, 0, 8, false);
            Field b = Field.zoned(st, 50, digits, scale, signed, false, false);
            int[] stat = new int[1];
            int code = JsonParse.tryParse(in, JsonParse.group("G", JsonParse.text("A-B", a), JsonParse.number("N", b)), CS, stat, wantCode, wantStat);
            System.out.println("C" + code + "S" + stat[0] + "[" + new String(st.bytes, 0, 8, CS) + "][" + new String(st.bytes, 50, digits, CS) + "]");
        } catch (RuntimeException e) {
            System.out.println("HOLE " + e.getMessage());
        }
    }
    public static void main(String[] x) {
        run("plain", "{\\"A-B\\":\\"Ann\\",\\"N\\":-0.12}", 5, 2, true);
        run("order", " { \\"N\\" : 7 , \\"A-B\\" : \\"a\\\\\\"b\\" } ", 3, 0, false);
        run("unmatched", "{\\"other\\":1,\\"N\\":5}", 3, 0, false);
        run("keep", "{\\"X\\":1}", 3, 0, false);
        run("case", "{\\"n\\":5}", 3, 0, false);
        run("long", "{\\"A-B\\":\\"123456789\\"}", 3, 0, false);
        run("type", "{\\"N\\":\\"5\\"}", 3, 0, false);
        run("decimals", "{\\"N\\":1.5}", 3, 0, false);
        run("big", "{\\"N\\":1000}", 3, 0, false);
        run("neg", "{\\"N\\":-1}", 3, 0, false);
        run("bad", "{\\"N\\":5", 3, 0, false);
        run("array", "{\\"N\\":[1]}", 3, 0, false);
        run("wide", "{\\"A-B\\":\\"\u00e9\\"}", 3, 0, false);
        tryRun("{\\"A-B\\":\\"Ann\\",\\"N\\":7}", true, false);
        tryRun("{\\"N\\":5", true, false);
        tryRun("[1]", true, false);
        tryRun("{\\"N\\":\\"5\\"}", true, false);
        tryRun("{\\"A-B\\":\\"123456789\\"}", true, false);
        tryRun("{\\"N\\":1000}", true, false);
        tryRun("{\\"A-B\\":\\"Ann\\",\\"N\\":\\"x\\"}", true, false);
        tryRun("{\\"N\\":1.5}", true, false);
        tryRun("{\\"N\\":-1}", true, false);
        tryRun("{\\"N\\":1e2}", true, false);
        tryRun("{\\"N\\":1,\\"N\\":2}", true, false);
        tryRun("   ", true, false);
        tryRun("{\\"A-B\\":\\"Ann\\",\\"N\\":7} x", true, false);
        tryRun("{\\"other\\":1}", true, false);
        tryRun("{\\"N\\":5}", true, true);
        tryRun("{\\"A-B\\":\\"Ann\\",\\"N\\":7,\\"zz\\":1}", true, true);
        tryRun("{\\"zz\\":1}", true, true);
        tryRun("5", false, false);
        tryRun("{\\"N\\":\\"5\\"}", true, true);
        tryRun("{\\"A-B\\":\\"\u00e9\\"}", true, false);
        tryRun("{\\"zz\\":1,\\"N\\":\\"5\\"}", true, true);
        tryRun("{\\"N\\":5", true, true);
        tryRun("{\\"N\\":5} x", true, true);
        tryRun("", true, true);
        tryRun("[1]", true, true);
    }
}
"""
    for rel, text in files.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text, encoding="utf-8")
    jdk = _jdk()
    built = javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"),
                       *map(str, src.rglob("*.java"))], capture_output=True, text=True, encoding="utf-8", check=False)  # fmt: skip
    assert built.returncode == 0, built.stderr
    out = subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(tmp_path / "classes"), "Main"],  # noqa: S603
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout.splitlines()  # fmt: skip
    assert out[0] == "[Ann     ][0001K]"
    assert out[1] == '[a"b     ][007]'
    assert out[2] == "[########][005]"
    assert "refused" in out[3] and "JSON-CODE 106" in out[3]  # no name matched: IBM's exception 106
    assert "refused" in out[4] and "JSON-CODE 106" in out[4]  # names are case-sensitive, so "n" matches nothing
    for i, why in ((5, "9 characters"), (6, "takes a JSON number"), (7, "decimals"), (8, "does not fit"),
                   (9, "unsigned"), (10, "JSON-CODE 100"), (11, "array"), (12, "beyond ASCII")):  # fmt: skip
        assert "refused" in out[i] and why in out[i], out[i]
    # ON EXCEPTION: IBM's exception-class failures are caught; malformed text stores nothing, a type or size failure
    # keeps what was stored before it, and what IBM leaves undefined or the model does not take stays a Hole
    tail = out[13:]
    assert tail[0] == "C0S0[Ann     ][007]"
    assert tail[1] == "C100S0[########][999]"  # unterminated object: invalid text
    assert tail[3] == "C104S0[########][999]"  # string for a number: incompatible value
    assert tail[6] == "C104S0[Ann     ][999]"  # A-B stored before N failed
    assert tail[11] == "C101S0[########][999]"  # empty text
    assert tail[12] == "C102S0[########][999]"  # text after the closing brace: nothing stored (assumed)
    assert tail[13] == "C106S3[########][999]"  # no name matched (the status bits are kept, 3)
    assert tail[14] == "C0S1[########][005]"  # item A-B had no pair -> JSON-STATUS 1
    assert tail[15] == "C0S2[Ann     ][007]"  # the pair zz has no item -> JSON-STATUS 2
    # JSON-STATUS after an exception (IBM: the nonexception conditions that occurred before it)
    assert tail[16] == "C106S3[########][999]"  # no name matched: the pair had no item (2), the item no pair (1)
    assert tail[18] == "C104S0[########][999]"  # the type failure came before anything was noted
    assert tail[20] == "C104S2[########][999]"  # a superfluous pair before the failing one is kept (2)
    assert tail[22] == "C102S0[########][999]"  # text after the brace: nothing was processed
    assert tail[23] == "C101S0[########][999]"  # empty text
    assert tail[17] == "C-1S0[########][999]"  # a bare number is not an object: the Programming Guide states no code
    for i, why in ((2, "JSON array"), (4, "9 characters"), (5, "does not fit"), (7, "decimals"),
                   (8, "unsigned"), (9, "exponent"), (10, "occurs twice"), (19, "beyond ASCII"),
                   (21, "JSON-STATUS after this exception"), (24, "top-level JSON array")):  # fmt: skip
        assert tail[i].startswith("HOLE") and why in tail[i], tail[i]


_PHRASES = [
    "JSON PARSE JIN INTO REC",
    "    ON EXCEPTION DISPLAY 'BAD'",
    "    NOT ON EXCEPTION DISPLAY 'OK'",
    "END-JSON",
]


def test_on_exception_phrases_run_around_the_runtime_call(tmp_path):
    r = _translate(tmp_path, *_PHRASES)
    assert r.stats["holes"] == []
    java = r.java
    assert "JsonParse.tryParse(" in java and "JsonParse.parse(" not in java
    flag = next(x for x in java.splitlines() if "JsonParse.tryParse(" in x).split()[1]
    assert f"if ({flag} != 0) {{" in java and f"if ({flag} == 0) {{" in java
    assert java.index(f"if ({flag} != 0) {{") < java.index(f"if ({flag} == 0) {{")


@pytest.mark.parametrize(
    "phrases",
    [_PHRASES[:2] + _PHRASES[3:], [_PHRASES[0], _PHRASES[2], _PHRASES[3]], [_PHRASES[0], _PHRASES[1], _PHRASES[2]]],
)
def test_either_phrase_alone_and_an_unterminated_statement_bind_to_the_parse(tmp_path, phrases):
    r = _translate(tmp_path, *phrases)
    assert r.stats["holes"] == []
    assert "JsonParse.tryParse(" in r.java


def test_without_a_phrase_the_call_stays_the_throwing_one(tmp_path):
    r = _translate(tmp_path, "JSON PARSE JIN INTO REC WITH DETAIL")
    assert "JsonParse.parse(" in r.java and "JsonParse.tryParse(" not in r.java


def test_a_shape_the_model_does_not_take_keeps_its_phrases_in_one_hole(tmp_path):
    r = _translate(tmp_path, "JSON PARSE JIN INTO REC IGNORING ALL NULL", "    ON EXCEPTION DISPLAY 'BAD'", "END-JSON")
    assert [h for h in r.stats["holes"] if "JSON PARSE" in str(h)]
    assert "JsonParse.tryParse(" not in r.java


def test_json_code_and_status_are_stored_from_the_runtime_result(tmp_path):
    r = _translate(tmp_path, "JSON PARSE JIN INTO REC", "    ON EXCEPTION DISPLAY JSON-CODE", "END-JSON")
    assert r.stats["holes"] == []
    java = r.java
    assert "JsonParse.tryParse(" in java and "true, false);" in java
    assert "GG_JSON_CODE" in java


def test_json_code_alone_asks_the_runtime_for_the_code_only(tmp_path):
    r = _translate(tmp_path, "JSON PARSE JIN INTO REC", "DISPLAY JSON-CODE")
    assert r.stats["holes"] == []
    assert "true, false);" in r.java and "GG_JSON_STATUS" not in r.java


def test_json_status_is_a_hidden_register_stored_from_the_runtime_status(tmp_path):
    for body in (["JSON PARSE JIN INTO REC", "DISPLAY JSON-STATUS"],
                 ["JSON PARSE JIN INTO REC", "    ON EXCEPTION DISPLAY 'BAD'", "    NOT ON EXCEPTION DISPLAY JSON-STATUS", "END-JSON"],
                 ["JSON PARSE JIN INTO REC WITH DETAIL", "DISPLAY JSON-STATUS"]):  # fmt: skip
        r = _translate(tmp_path, *body)
        assert r.stats["holes"] == [], body
        java = r.java
        assert "false, true);" in java and "tryParse(" in java and "GG_JSON_CODE" not in java
        store = [x for x in java.splitlines() if "GG_JSON_STATUS" in x and "Cobol.store" in x]
        assert len(store) == 1 and "[0]" in store[0]


def test_json_status_with_code_asks_for_both(tmp_path):
    r = _translate(tmp_path, "JSON PARSE JIN INTO REC", "DISPLAY JSON-CODE JSON-STATUS")
    assert "GG_JSON_CODE" in r.java and "GG_JSON_STATUS" in r.java and "true, true);" in r.java


def test_a_programs_own_json_status_item_is_kept(tmp_path):
    src = tmp_path / "PROG.cbl"
    own = DATA.replace(
        "       01  OUT  PIC X(100).\n", "       01  OUT  PIC X(100).\n       01  JSON-STATUS  PIC S9(4) COMP.\n"
    )
    src.write_text(
        own + "           JSON PARSE JIN INTO REC\n           DISPLAY JSON-STATUS\n           GOBACK.\n",
        encoding="utf-8",
    )
    r = P.translate(src, [], "public class ProgService { }", "t")
    assert r.stats["holes"] == [] and "GG_JSON_STATUS" not in r.java


def test_no_hidden_json_status_without_a_json_parse(tmp_path):
    r = _translate(tmp_path, "DISPLAY 'X'")
    assert "GG_JSON_STATUS" not in r.java
    r = _translate(tmp_path, "JSON PARSE JIN INTO REC")
    assert "GG_JSON_STATUS" not in r.java  # not named: no register


@pytest.mark.skipif(_jdk() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_the_runtime_fills_a_fixed_table_from_a_json_array(tmp_path):
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_SPEC_JAVA, CICS_TASK_JAVA

    src = tmp_path / "src"
    files = {"t/cics/CicsTask.java": CICS_TASK_JAVA.replace("__PACKAGE__", "t").replace("__ZONE__", "UTC"),
             "t/cics/CicsSpec.java": CICS_SPEC_JAVA.replace("__PACKAGE__", "t"),
             **{f"t/{k}": v for k, v in P.runtime_files("t", batch=False).items()}}  # fmt: skip
    files["Main.java"] = """
import java.nio.charset.Charset;
import t.cobolrt.Field;
import t.cobolrt.JsonParse;
import t.cobolrt.Storage;
public class Main {
    static Charset CS = Charset.forName("ISO-8859-1");
    static void run(String json) {
        Storage st = new Storage(300);
        for (int i = 0; i < 20; i++) st.bytes[i] = ' ';
        byte[] j = json.getBytes(CS);
        System.arraycopy(j, 0, st.bytes, 100, j.length);
        for (int i = j.length; i < 100; i++) st.bytes[100 + i] = ' ';
        try {
            Field in = Field.alphanumeric(st, 100, 100, false);
            JsonParse.Node g = JsonParse.group("G",
                JsonParse.array("A", JsonParse.text("", Field.alphanumeric(st, 0, 2, false)),
                                     JsonParse.text("", Field.alphanumeric(st, 2, 2, false))));
            boolean exc = JsonParse.tryParse(in, g, CS);
            System.out.println((exc ? "EXC " : "OK ") + new String(st.bytes, 0, 4, CS));
        } catch (RuntimeException e) {
            System.out.println("HOLE " + e.getMessage());
        }
    }
    public static void main(String[] x) {
        run("{\\"A\\":[\\"ab\\",\\"c\\"]}");
        run("{\\"A\\":[\\"ab\\"]}");
        run("{\\"A\\":[\\"a\\",\\"b\\",\\"c\\"]}");
        run("{\\"A\\":\\"ab\\"}");
        run("{\\"A\\":[\\"a\\",7]}");
        run("{\\"A\\":[\\"a\\",}");
        run("[\\"a\\"]");
    }
}
"""
    for rel, text in files.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text, encoding="utf-8")
    jdk = _jdk()
    built = javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"),
                       *map(str, src.rglob("*.java"))], capture_output=True, text=True, encoding="utf-8", check=False)  # fmt: skip
    assert built.returncode == 0, built.stderr
    out = subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(tmp_path / "classes"), "Main"],  # noqa: S603
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout.splitlines()  # fmt: skip
    assert out[0] == "OK abc "
    assert out[1].startswith("HOLE") and "OCCURS 2" in out[1] and out[2].startswith("HOLE")
    assert out[3] == "EXC " + " " * 4  # a string for a table: JSON-CODE 104, nothing stored
    assert out[4] == "EXC a   "  # the element before the number was stored (X77: left to right)
    assert out[5] == "EXC " + " " * 4  # malformed text stores nothing
    assert out[6].startswith("HOLE") and "top-level JSON array" in out[6]


@pytest.mark.skipif(_jdk() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_the_runtime_takes_odo_tables_and_comp1_numbers(tmp_path):
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_SPEC_JAVA, CICS_TASK_JAVA

    src = tmp_path / "src"
    files = {"t/cics/CicsTask.java": CICS_TASK_JAVA.replace("__PACKAGE__", "t").replace("__ZONE__", "UTC"),
             "t/cics/CicsSpec.java": CICS_SPEC_JAVA.replace("__PACKAGE__", "t"),
             **{f"t/{k}": v for k, v in P.runtime_files("t", batch=False).items()}}  # fmt: skip
    files["Main.java"] = """
import java.nio.charset.Charset;
import t.cobolrt.Field;
import t.cobolrt.JsonParse;
import t.cobolrt.Storage;
public class Main {
    static Charset CS = Charset.forName("ISO-8859-1");
    static String hex(Storage st, int off, int n) {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < n; i++) b.append(String.format("%02X", st.bytes[off + i] & 0xFF));
        return b.toString();
    }
    static void run(String json, int cnt) {
        Storage st = new Storage(300);
        byte[] j = json.getBytes(CS);
        System.arraycopy(j, 0, st.bytes, 100, j.length);
        for (int i = j.length; i < 100; i++) st.bytes[100 + i] = ' ';
        try {
            Field in = Field.alphanumeric(st, 100, 100, false);
            JsonParse.Node g = JsonParse.group("G", JsonParse.floating("F", Field.hfp(st, 0, false)),
                JsonParse.number("N", Field.packed(st, 4, 3, 0, true)), JsonParse.floating("D", Field.hfp(st, 20, true)),
                JsonParse.table("OT", cnt, 1, "CNT", JsonParse.number("", Field.packed(st, 10, 1, 0, false)),
                    JsonParse.number("", Field.packed(st, 11, 1, 0, false)), JsonParse.number("", Field.packed(st, 12, 1, 0, false))));
            boolean exc = JsonParse.tryParse(in, g, CS);
            System.out.println((exc ? "EXC " : "OK ") + hex(st, 0, 4) + " " + hex(st, 4, 2) + " " + hex(st, 10, 3) + " " + hex(st, 20, 8));
        } catch (RuntimeException e) {
            System.out.println("HOLE " + e.getMessage());
        }
    }
    public static void main(String[] x) {
        run("{\\"F\\":1.5}", 2);
        run("{\\"F\\":2.5E1}", 2);
        run("{\\"F\\":-2}", 2);
        run("{\\"F\\":15e-1}", 2);
        run("{\\"N\\":1E2}", 2);
        run("{\\"OT\\":[1,2]}", 2);
        run("{\\"OT\\":[1,2,3]}", 2);
        run("{\\"OT\\":[1]}", 2);
        run("{\\"OT\\":[1,2]}", 5);
        run("{\\"F\\":\\"x\\"}", 2);
        run("{\\"F\\":1E}", 2);
        run("{\\"F\\":1E200}", 2);
        run("{\\"OT\\":[1,2,3]}", 3);
        run("{\\"OT\\":[]}", 0);
        run("{\\"D\\":1.5}", 2);
        run("{\\"D\\":-2}", 2);
        run("{\\"D\\":15e-1}", 2);
        run("{\\"D\\":\\"x\\"}", 2);
        run("{\\"D\\":1E200}", 2);
    }
}
"""
    for rel, text in files.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text, encoding="utf-8")
    jdk = _jdk()
    built = javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"),
                       *map(str, src.rglob("*.java"))], capture_output=True, text=True, encoding="utf-8", check=False)  # fmt: skip
    assert built.returncode == 0, built.stderr
    out = subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(tmp_path / "classes"), "Main"],  # noqa: S603
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout.splitlines()  # fmt: skip
    assert out[0].startswith("OK 41180000"), out[0]
    assert out[1].startswith("OK 42190000"), out[1]  # an exponent form is taken by a float receiver
    assert out[2].startswith("OK C1200000"), out[2]
    assert out[3].startswith("OK 41180000"), out[3]
    assert out[4].startswith("HOLE") and "exponent" in out[4]  # a fixed-point item does not take one
    assert out[5].startswith("OK") and " 1F2F00 " in out[5], out[5]
    for k, why in ((6, "array elements"), (7, "array elements"), (8, "outside")):
        assert out[k].startswith("HOLE") and why in out[k], out[k]  # IBM states no result
    assert out[9].startswith("EXC")  # type mismatch (JSON-CODE 104)
    assert out[10].startswith("EXC")  # a malformed exponent (JSON-CODE 100)
    assert out[11].startswith("HOLE") and "range" in out[11]
    assert out[12].startswith("OK") and " 1F2F3F " in out[12], out[12]
    assert out[13].startswith("HOLE") and "outside 1 to 3" in out[13]  # a count below the clause's low bound: undefined
    assert out[14].endswith(" 4118000000000000"), out[14]  # a COMP-2 takes 1.5 as an 8-byte HFP value
    assert out[15].endswith(" C120000000000000"), out[15]
    assert out[16].endswith(" 4118000000000000"), out[16]  # an exponent form
    assert out[17].startswith("EXC")  # a string for a float: type mismatch (JSON-CODE 104)
    assert out[18].startswith("HOLE") and "range" in out[18]


CONV = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. PROG.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  REC.
           05  FLAG-A  PIC X.
               88  A-ON  VALUE 'T'.
               88  A-OFF VALUE 'F'.
           05  FLAG-B  PIC X.
           05  FLAG-W  PIC XX.
           05  TBL-F   PIC X OCCURS 2.
           05  CNT     PIC 9(4).
           05  LABEL   PIC X(10).
           05  ADDR.
               10  CITY PIC X(4).
               10  ZIP  PIC 9(3).
       01  JIN  PIC X(100).
       PROCEDURE DIVISION.
"""


def _conv(tmp_path, *body: str):
    src = tmp_path / "PROG.cbl"
    lines: list[str] = []
    for b in body:  # fixed form reads columns 8-72: wrap a long statement on its spaces
        cur = ""
        for w in b.split():
            if len(cur) + len(w) > 50:
                lines.append(cur)
                cur = "    "
            cur += ("" if cur.endswith(" ") or not cur else " ") + w
        lines.append(cur)
    src.write_text(CONV + "".join(f"           {ln}\n" for ln in lines) + "           GOBACK.\n", encoding="utf-8")
    return P.translate(src, [], "public class ProgService { }", "t")


def _parse_line(r):
    return next(x for x in r.java.splitlines() if "JsonParse.parse" in x)


def test_the_converting_phrase_parses_every_form_ibm_names():
    st = S._json_parse(
        "JSON PARSE J INTO R CONVERTING A FROM BOOLEAN USING A-ON AND A-OFF ALSO B FROM JSON BOOL USING 'y' AND 'n'"
        " ALSO C FROM NULL USING ZEROS ALSO D FROM JSON NULL USING SPACE END-JSON",
        1,
    )
    assert [
        (i.name, t.name if hasattr(t, "name") else t, f.name if hasattr(f, "name") else f)
        for i, t, f in st.data["bools"]
    ] == [
        ("A", "A-ON", "A-OFF"),
        ("B", "y", "n"),
    ]
    assert [(i.name, f) for i, f in st.data["nulls"]] == [("C", "ZERO"), ("D", "SPACE")]
    one = S._json_parse("JSON PARSE J INTO R CONVERTING A FROM BOOLEAN USING A-FLAG", 1)
    assert one.data["bools"][0][2] is None
    assert "bools" not in S._json_parse("JSON PARSE J INTO R", 1).data


def test_converting_is_translated_to_runtime_nodes(tmp_path):
    r = _conv(
        tmp_path,
        "JSON PARSE JIN INTO REC CONVERTING FLAG-A FROM BOOLEAN USING A-ON AND A-OFF",
        "    ALSO FLAG-B FROM BOOLEAN USING 'y' AND 'n'",
        "    ALSO LABEL FROM NULL USING SPACES",
        "    ALSO ADDR FROM NULL USING LOW-VALUES",
        "    END-JSON",
    )
    assert r.stats["holes"] == []
    line = _parse_line(r)
    assert 'JsonParse.bool("FLAG-A", ' in line and '"T", "F")' in line and '"y", "n")' in line
    assert 'convertNull(t.cobolrt.JsonParse.text("LABEL"' in line and '"SPACE")' in line
    assert 'convertNull(t.cobolrt.JsonParse.group("ADDR"' in line and '"LOW-VALUE")' in line


@pytest.mark.parametrize(
    "conv, why",
    [
        ("CNT FROM BOOLEAN USING 'y' AND 'n'", "needs a one-byte PIC X item"),
        ("FLAG-W FROM BOOLEAN USING 'y' AND 'n'", "needs a one-byte PIC X item"),
        ("TBL-F(1) FROM BOOLEAN USING 'y' AND 'n'", "needs a one-byte PIC X item"),
        ("FLAG-B FROM BOOLEAN USING 'yy' AND 'n'", "not a single-byte literal"),
        ("FLAG-B FROM BOOLEAN USING 'y'", "one literal"),
        ("FLAG-A FROM BOOLEAN USING A-ON", "WHEN SET TO FALSE"),
        ("FLAG-B FROM BOOLEAN USING A-ON AND A-OFF", "not an 88 directly under FLAG-B"),
        ("FLAG-B FROM BOOLEAN USING 'y' AND 'n' ALSO FLAG-B FROM BOOLEAN USING 'a' AND 'b'", "named twice"),
        ("CNT FROM NULL USING SPACES", "not a legal MOVE to a number"),
        ("LABEL FROM NULL USING ZERO ALSO LABEL FROM NULL USING SPACE", "with SUPPRESS ... WHEN or another CONVERTING"),
        ("FLAG-B FROM BOOLEAN USING 'y' AND 'n' ALSO FLAG-B FROM NULL USING SPACE", "another CONVERTING"),
        ("TBL-F FROM NULL USING SPACE", "item in a table"),
        ("FLAG-A FROM NUMBER USING 'y'", "CONVERTING FROM NUMBER"),
    ],
)
def test_a_converting_shape_the_model_does_not_take_is_refused_by_name(tmp_path, conv, why):
    r = _conv(tmp_path, f"JSON PARSE JIN INTO REC CONVERTING {conv}")
    assert len(r.stats["holes"]) == 1
    assert why in str(r.stats["holes"][0])


def test_converting_keeps_its_on_exception_phrases(tmp_path):
    r = _conv(
        tmp_path,
        "JSON PARSE JIN INTO REC CONVERTING FLAG-B FROM BOOLEAN USING 'y' AND 'n'",
        "    ON EXCEPTION DISPLAY 'BAD'",
        "    NOT ON EXCEPTION DISPLAY 'OK'",
        "    END-JSON",
    )
    assert r.stats["holes"] == [] and "JsonParse.tryParse(" in r.java


@pytest.mark.skipif(_jdk() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_the_runtime_converts_true_false_and_null_and_holes_the_rest(tmp_path):
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_SPEC_JAVA, CICS_TASK_JAVA

    src = tmp_path / "src"
    files = {"t/cics/CicsTask.java": CICS_TASK_JAVA.replace("__PACKAGE__", "t").replace("__ZONE__", "UTC"),
             "t/cics/CicsSpec.java": CICS_SPEC_JAVA.replace("__PACKAGE__", "t"),
             **{f"t/{k}": v for k, v in P.runtime_files("t", batch=False).items()}}  # fmt: skip
    files["Main.java"] = """
import java.nio.charset.Charset;
import t.cobolrt.Field;
import t.cobolrt.JsonParse;
import t.cobolrt.Storage;
public class Main {
    static Charset CS = Charset.forName("ISO-8859-1");
    // bytes 0: flag, 1: flag2, 10..13: number (4), 20..29: label (10)
    static void run(String json, boolean convNull, boolean needStatus) {
        Storage st = new Storage(300);
        byte[] j = json.getBytes(CS);
        System.arraycopy(j, 0, st.bytes, 100, j.length);
        for (int i = j.length; i < 100; i++) st.bytes[100 + i] = ' ';
        st.bytes[0] = '#'; st.bytes[1] = '#';
        for (int i = 0; i < 4; i++) st.bytes[10 + i] = '7';
        for (int i = 0; i < 10; i++) st.bytes[20 + i] = 'x';
        try {
            Field in = Field.alphanumeric(st, 100, 100, false);
            Field f1 = Field.alphanumeric(st, 0, 1, false);
            Field f2 = Field.alphanumeric(st, 1, 1, false);
            Field n = Field.zoned(st, 10, 4, 0, false, false, false);
            Field l = Field.alphanumeric(st, 20, 10, false);
            JsonParse.Node num = JsonParse.number("N", n);
            JsonParse.Node lab = JsonParse.text("L", l);
            if (convNull) {
                num = JsonParse.convertNull(num, n, "ZERO");
                lab = JsonParse.convertNull(lab, l, "SPACE");
            }
            int[] stat = new int[1];
            int code = JsonParse.tryParse(in, JsonParse.group("G", JsonParse.bool("F1", f1, "T", "F"),
                    JsonParse.bool("F2", f2, "1", "0"), num, lab), CS, stat, true, needStatus);
            System.out.println("C" + code + "S" + stat[0] + "[" + new String(st.bytes, 0, 2, CS) + "]["
                    + new String(st.bytes, 10, 4, CS) + "][" + new String(st.bytes, 20, 10, CS) + "]");
        } catch (RuntimeException e) {
            System.out.println("HOLE " + e.getMessage());
        }
    }
    public static void main(String[] x) {
        run("{\\"F1\\":true,\\"F2\\":false}", false, false);
        run("{\\"F1\\":false,\\"F2\\":true}", false, false);
        run("{\\"N\\":null,\\"L\\":null}", true, false);
        run("{\\"N\\":null,\\"L\\":null}", true, true);
        run("{\\"N\\":5,\\"L\\":\\"ab\\"}", true, false);
        run("{\\"N\\":null}", false, false);
        run("{\\"F1\\":null}", true, false);
        run("{\\"F1\\":\\"T\\"}", false, false);
        run("{\\"L\\":true}", true, false);
        run("{\\"zz\\":true,\\"F1\\":true}", false, false);
        run("{\\"F1\\":truex}", false, false);
        run("{\\"F1\\":tru}", false, false);
    }
}
"""
    for rel, text in files.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text, encoding="utf-8")
    jdk = _jdk()
    built = javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(tmp_path / "classes"),
                       *map(str, src.rglob("*.java"))], capture_output=True, text=True, encoding="utf-8", check=False)  # fmt: skip
    assert built.returncode == 0, built.stderr
    lines = subprocess.run([str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(tmp_path / "classes"), "Main"],  # noqa: S603
                           capture_output=True, text=True, encoding="utf-8", check=True).stdout.splitlines()  # fmt: skip
    assert lines[0] == "C0S1[T0][7777][xxxxxxxxxx]"
    assert lines[1] == "C0S1[F1][7777][xxxxxxxxxx]"
    assert lines[2] == "C0S1[##][0000][          ]"
    assert lines[3].startswith("HOLE") and "JSON-STATUS of a null" in lines[3]
    assert lines[4] == "C0S1[##][0005][ab        ]"
    assert lines[5].startswith("HOLE") and "no CONVERTING phrase" in lines[5]
    assert lines[6].startswith("HOLE") and "no CONVERTING phrase" in lines[6]
    assert lines[7].startswith("HOLE") and "not true or false" in lines[7]
    assert lines[8].startswith("HOLE") and "no CONVERTING phrase" in lines[8]
    assert lines[9].startswith("HOLE") and "unmatched name zz" in lines[9]
    assert lines[10] == "C100S0[##][7777][xxxxxxxxxx]"
    assert lines[11] == "C100S0[##][7777][xxxxxxxxxx]"
