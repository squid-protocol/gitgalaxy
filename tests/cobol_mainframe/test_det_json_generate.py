"""#7524 slice 2 (register X76): JSON GENERATE from a group of DISPLAY items is translated from IBM's text alone (the
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
       01  N    PIC 9(4).
       PROCEDURE DIVISION.
"""


def _translate(tmp_path, *body: str):
    src = tmp_path / "PROG.cbl"
    src.write_text(DATA + "".join(f"           {b}\n" for b in body) + "           GOBACK.\n", encoding="utf-8")
    return P.translate(src, [], "public class ProgService { }", "t")


def test_a_group_source_is_a_runtime_call_with_its_members_in_storage_order(tmp_path):
    r = _translate(tmp_path, "JSON GENERATE OUT FROM REC COUNT IN N")
    assert r.stats["holes"] == []
    call = 'JsonGenerate.generate(f7_OUT, t.cobolrt.JsonGenerate.group("REC", t.cobolrt.JsonGenerate.text("CUST-NAME"'
    assert call.replace("JsonGenerate.generate", "t.cobolrt.JsonGenerate.generate") in r.java or call in r.java
    assert 'number("AMT"' in r.java and 'group("ADDR"' in r.java and "FILLER" not in r.java.split("generate(")[1]


def test_name_of_and_suppress_shape_the_members(tmp_path):
    r = _translate(tmp_path, "JSON GENERATE OUT FROM REC NAME OF CUST-NAME IS 'who'", "    SUPPRESS AMT")
    line = next(x for x in r.java.splitlines() if "JsonGenerate.generate" in x)
    assert 'text("who"' in line and "AMT" not in line and 'group("ADDR"' in line


@pytest.mark.parametrize(
    "stmt, why",
    [
        ("JSON GENERATE OUT FROM REC SUPPRESS AMT WHEN ZERO", "SUPPRESS ... WHEN / EVERY"),
        (
            "JSON GENERATE OUT FROM REC CONVERTING ON EXCEPTION\n           DISPLAY 'X'\n           END-JSON",
            "CONVERTING phrase",
        ),
        ("JSON GENERATE OUT FROM REC NAME OF AMT IS OMITTED", "NAME needs an alphanumeric literal"),
    ],
)
def test_a_shape_the_model_does_not_take_is_refused_by_name(tmp_path, stmt, why):
    r = _translate(tmp_path, stmt)
    assert len(r.stats["holes"]) == 1
    hole = str(r.stats["holes"][0])
    assert "JSON GENERATE (Enterprise COBOL 6.1+): not modelled" in hole and why in hole


@pytest.mark.parametrize(
    ("body", "bad", "ok", "count"),
    [
        (["JSON GENERATE OUT FROM REC", "    ON EXCEPTION DISPLAY 'BAD'", "END-JSON"], True, False, False),
        (["JSON GENERATE OUT FROM REC", "    NOT ON EXCEPTION DISPLAY 'OK'", "END-JSON"], False, True, False),
        (
            [
                "JSON GENERATE OUT FROM REC COUNT N",
                "    ON EXCEPTION DISPLAY 'BAD'",
                "    NOT ON EXCEPTION DISPLAY 'OK'",
                "END-JSON",
            ],
            True,
            True,
            True,
        ),  # fmt: skip
        (
            ["JSON GENERATE OUT FROM REC", "    ON EXCEPTION DISPLAY 'BAD'", "    NOT ON EXCEPTION DISPLAY 'OK'."],
            True,
            True,
            False,
        ),  # fmt: skip
        (["JSON GENERATE OUT FROM REC NOT EXCEPTION DISPLAY 'OK'", "END-JSON"], False, True, False),
    ],
)
def test_exception_phrases_bind_to_the_statement(tmp_path, body, bad, ok, count):
    """IBM's DISPLAY has no ON EXCEPTION, so both phrases belong to the JSON GENERATE even after a DISPLAY."""
    r = _translate(tmp_path, *body)
    java = str(r.java)
    assert r.stats["holes"] == [] and "JsonGenerate.tryGenerate(" in java
    assert ("if (jsonbytes1 < 0) {\n            // DISPLAY 'BAD'" in java) is bad
    assert ("if (jsonbytes1 >= 0) {\n            // DISPLAY 'OK'" in java) is ok
    assert ("Cobol.store(f8_N, BigDecimal.valueOf(jsonbytes1)" in java) is count


def test_phrases_scope_to_their_own_statement(tmp_path):
    r = _translate(
        tmp_path,
        "IF N = 0",
        "    JSON GENERATE OUT FROM REC",
        "        ON EXCEPTION MOVE 1 TO N",
        "    END-JSON",
        "    DISPLAY 'AFTER'",
        "END-IF",
        "JSON GENERATE OUT FROM REC SUPPRESS AMT WHEN ZERO",
        "    ON EXCEPTION MOVE 2 TO N",
        "END-JSON",
    )
    assert len(r.stats["holes"]) == 1 and "SUPPRESS ... WHEN / EVERY" in str(r.stats["holes"][0])


def test_xml_and_parse_phrases_stay_in_their_hole(tmp_path):
    r = _translate(tmp_path, "XML GENERATE OUT FROM REC ON EXCEPTION DISPLAY 'X' END-XML")
    assert len(r.stats["holes"]) == 1 and "XML GENERATE" in str(r.stats["holes"][0])


def test_an_elementary_source_is_refused_by_name(tmp_path):
    r = _translate(tmp_path, "JSON GENERATE OUT FROM CUST-NAME")
    assert len(r.stats["holes"]) == 1 and "JSON GENERATE: CUST-NAME is not a plain group" in r.stats["holes"][0]


def test_the_statement_parses_every_phrase_ibm_names():
    st = S._json_generate("JSON GENERATE A FROM R COUNT IN B NAME OF C IS 'c' D IS 'd' SUPPRESS E F END-JSON", 1)
    assert st.kind == "JSONGEN"
    assert [lit for _, lit in st.data["names"]] == ["c", "d"] and len(st.data["suppress"]) == 2


@pytest.mark.skipif(_jdk() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_the_runtime_writes_ibms_text_and_stops_where_ibm_is_silent(tmp_path):
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_SPEC_JAVA, CICS_TASK_JAVA

    src = tmp_path / "src"
    files = {"t/cics/CicsTask.java": CICS_TASK_JAVA.replace("__PACKAGE__", "t").replace("__ZONE__", "UTC"),
             "t/cics/CicsSpec.java": CICS_SPEC_JAVA.replace("__PACKAGE__", "t"),
             **{f"t/{k}": v for k, v in P.runtime_files("t", batch=False).items()}}  # fmt: skip
    files["Main.java"] = """
import java.nio.charset.Charset;
import t.cobolrt.Field;
import t.cobolrt.JsonGenerate;
import t.cobolrt.Storage;
public class Main {
    static Charset CS = Charset.forName("ISO-8859-1");
    static void run(String name, String text, int digits, int scale, boolean signed, String num, int room) {
        Storage st = new Storage(200);
        byte[] t = text.getBytes(CS), n = num.getBytes(CS);
        System.arraycopy(t, 0, st.bytes, 0, t.length);
        System.arraycopy(n, 0, st.bytes, 50, n.length);
        try {
            Field out = Field.alphanumeric(st, 100, room, false);
            for (int i = 0; i < room; i++) st.bytes[100 + i] = '#';
            Field a = Field.alphanumeric(st, 0, 8, false);
            Field b = Field.zoned(st, 50, digits, scale, signed, false, false);
            JsonGenerate.Node g = JsonGenerate.group("G", JsonGenerate.text("A-B", a), JsonGenerate.number("N", b));
            if (name.equals("small")) {
                System.out.println("try " + JsonGenerate.tryGenerate(out, g, CS) + " " + new String(st.bytes, 100, room, CS));
            }
            int c = JsonGenerate.generate(out, g, CS);
            System.out.println(c + " " + new String(st.bytes, 100, room, CS));
        } catch (RuntimeException e) {
            System.out.println(name + " refused: " + e.getMessage());
        }
    }
    public static void main(String[] x) {
        run("plain", "Ann     ", 5, 2, true, "0001K", 40);
        run("pos", "        ", 5, 2, false, "00000", 40);
        run("esc", "a\\"b\\\\c   ", 3, 0, false, "007", 60);
        run("tight", "Ann     ", 3, 0, false, "007", 25);
        run("small", "Ann     ", 3, 0, false, "007", 24);
        run("junk", "Ann     ", 3, 0, false, "0a7", 40);
        run("wide", "\\u00e9       ", 3, 0, false, "007", 40);
        run("negzero", "Ann     ", 3, 0, true, "00}", 40);
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
    assert out[0] == '29 {"G":{"A-B":"Ann","N":-0.12}}' + "#" * 11
    assert out[1].startswith('26 {"G":{"A-B":" ","N":0.00}}')
    assert '"A-B":"a\\"b\\\\c"' in out[2] and '"N":7}' in out[2]
    assert out[3].startswith("25 ")
    assert out[4] == "try -1 " + "#" * 24  # the exception condition: the receiver is untouched
    assert out[5].startswith("small refused: JSON GENERATE: the JSON is longer than the receiver of 24 bytes")
    assert "non-digit data in numeric item N" in out[6] and "undefined by IBM" in out[6]
    assert "beyond ASCII" in out[7] and "negative zero" in out[8]


WIDE = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. PROG.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  REC.
           05  BIN-N    PIC S9(4) COMP.
           05  PK-N     PIC S9(5)V99 COMP-3.
           05  NAT-N    PIC 9(9) COMP-5.
           05  PD-N     PIC 9(3) PACKED-DECIMAL.
           05  CODES    PIC X(2) OCCURS 3.
           05  LINES-T OCCURS 2.
               10  QTY  PIC 9(2).
               10  CELLS PIC 9 OCCURS 2.
       01  OUT  PIC X(200).
       PROCEDURE DIVISION.
"""


def _wide(tmp_path, *body: str, data: str = WIDE):
    src = tmp_path / "PROG.cbl"
    src.write_text(data + "".join(f"           {b}\n" for b in body) + "           GOBACK.\n", encoding="utf-8")
    return P.translate(src, [], "public class ProgService { }", "t")


def test_comp_numbers_and_fixed_tables_are_translated_for_generate(tmp_path):
    r = _wide(tmp_path, "JSON GENERATE OUT FROM REC")
    assert r.stats["holes"] == []
    java = str(r.java)
    for name in ("BIN-N", "PK-N", "NAT-N", "PD-N"):
        assert f'JsonGenerate.number("{name}"' in java
    # an elementary table is an array of values, a group table an array of objects (3 + 2 groups of 1 + 2 cells)
    assert 'JsonGenerate.array("CODES", t.cobolrt.JsonGenerate.text("", f' in java
    assert java.count('JsonGenerate.text("", ') == 3 and 'array("LINES-T"' in java
    assert java.count('group("", ') == 2 and java.count('array("CELLS"') == 2
    assert ".at(2, " in java


def test_name_of_and_suppress_apply_to_a_table_and_its_elements(tmp_path):
    r = _wide(tmp_path, "JSON GENERATE OUT FROM REC NAME OF CODES IS 'c'", "    SUPPRESS QTY PK-N")
    java = str(r.java)
    assert r.stats["holes"] == [] and 'array("c"' in java and '"QTY"' not in java and '"PK-N"' not in java


@pytest.mark.parametrize(
    ("data_line", "why"),
    [
        ("           05  T PIC X OCCURS 1 TO 5 DEPENDING ON N1.", None),
        ("           05  T PIC X OCCURS 300.", "more than 256 items and table elements"),
        ("           05  T COMP-1.", "COMP-1 FLOAT"),
        ("           05  T PIC S9(4) SIGN LEADING SEPARATE.", "P-scaled or separately signed"),
        ("           05  T PIC 9(4) COMP-3 REDEFINES N1.", None),
    ],
)
def test_wide_shapes_the_model_does_not_take_are_refused_by_name(tmp_path, data_line, why):
    data = WIDE.replace("       01  OUT", "           05  N1 PIC 9.\n" + data_line + "\n       01  OUT")
    r = _wide(tmp_path, "JSON GENERATE OUT FROM REC", data=data)
    if why is None:  # a REDEFINES item is left out, as IBM says; an ODO table is translated (see below)
        assert r.stats["holes"] == []
        return
    assert len(r.stats["holes"]) == 1 and why in str(r.stats["holes"][0])


ODO_DATA = WIDE.replace(
    "       01  OUT",
    "           05  N1 PIC 9.\n           05  VT PIC X(2) OCCURS 0 TO 4 DEPENDING ON N1.\n"
    "           05  VG OCCURS 1 TO 3 DEPENDING ON N1.\n               10  VQ PIC 9(2).\n       01  OUT",
)


def test_an_odo_table_is_an_array_of_the_odo_objects_count(tmp_path):
    """#7524: IBM's LR: a table with zero occurrences is `[]`; the elements generated are the ODO object's count."""
    r = _wide(tmp_path, "JSON GENERATE OUT FROM REC NAME OF VT IS 'v'", data=ODO_DATA)
    java = str(r.java)
    assert r.stats["holes"] == []
    assert 'JsonGenerate.table("v", ' in java and 'JsonGenerate.table("VG", ' in java
    assert java.count('"N1"') >= 1 and ', 0, "N1"' in java and ', 1, "N1"' in java  # the clause's lower bounds


def test_an_odo_table_inside_another_table_is_refused(tmp_path):
    line = "           05  TT OCCURS 2.\n               10  IN-T PIC X OCCURS 1 TO 3 DEPENDING ON N1."
    data = WIDE.replace("       01  OUT", "           05  N1 PIC 9.\n" + line + "\n       01  OUT")
    r = _wide(tmp_path, "JSON GENERATE OUT FROM REC", data=data)
    assert len(r.stats["holes"]) == 1 and "OCCURS DEPENDING ON inside another table" in str(r.stats["holes"][0])


def test_parse_still_refuses_an_odo_table(tmp_path):
    r = _wide(tmp_path, "JSON PARSE OUT INTO REC", data=ODO_DATA)
    assert len(r.stats["holes"]) == 1 and "table" in str(r.stats["holes"][0])


def test_a_table_as_the_source_itself_is_still_refused(tmp_path):
    r = _wide(tmp_path, "JSON GENERATE OUT FROM LINES-T")
    assert len(r.stats["holes"]) == 1 and "table" in str(r.stats["holes"][0])


def test_parse_does_not_take_what_only_generate_models(tmp_path):
    """JSON PARSE takes COMP numbers (#7524, X77) but still refuses tables (a sibling slice)."""
    r = _wide(tmp_path, "JSON PARSE OUT INTO REC")
    assert (
        len(r.stats["holes"]) == 1 and "JSON PARSE" in str(r.stats["holes"][0]) and "table" in str(r.stats["holes"][0])
    )


@pytest.mark.skipif(_jdk() is None, reason="needs a JDK 17 (JAVA_HOME / JDK_17)")
def test_the_runtime_writes_comp_numbers_and_tables(tmp_path):
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_transaction_forge import CICS_SPEC_JAVA, CICS_TASK_JAVA

    src = tmp_path / "src"
    files = {"t/cics/CicsTask.java": CICS_TASK_JAVA.replace("__PACKAGE__", "t").replace("__ZONE__", "UTC"),
             "t/cics/CicsSpec.java": CICS_SPEC_JAVA.replace("__PACKAGE__", "t"),
             **{f"t/{k}": v for k, v in P.runtime_files("t", batch=False).items()}}  # fmt: skip
    files["Main.java"] = """
import java.nio.charset.Charset;
import t.cobolrt.Field;
import t.cobolrt.JsonGenerate;
import t.cobolrt.Storage;
public class Main {
    static Charset CS = Charset.forName("ISO-8859-1");
    static void show(String what, Field out, Storage st, JsonGenerate.Node n) {
        try {
            int c = JsonGenerate.generate(out, n, CS);
            System.out.println(what + " " + new String(st.bytes, 100, c, CS));
        } catch (RuntimeException e) {
            System.out.println(what + " refused: " + e.getMessage());
        }
    }
    static void showS(String what, Field out, Storage st, java.util.function.Supplier<JsonGenerate.Node> n) {
        try {
            show(what, out, st, n.get());
        } catch (RuntimeException e) {
            System.out.println(what + " refused: " + e.getMessage());
        }
    }
    static Storage st(int... b) {
        Storage s = new Storage(200);
        for (int i = 0; i < b.length; i++) s.bytes[i] = (byte) b[i];
        return s;
    }
    public static void main(String[] x) {
        Storage s = st(0xFF, 0x85, 0x12, 0x34, 0x5D, 0x2A, 0x00, 0x00, 0x00, 0x01, 0x2C, 'a', ' ', 'b', ' ');
        Field out = Field.alphanumeric(s, 100, 100, false);
        show("bin", out, s, JsonGenerate.number("B", Field.binary(s, 0, 4, 0, true, false)));
        show("packed", out, s, JsonGenerate.number("P", Field.packed(s, 2, 5, 2, true)));
        show("native", out, s, JsonGenerate.number("N", Field.binary(s, 5, 9, 0, false, true)));
        show("pd", out, s, JsonGenerate.number("D", Field.packed(s, 9, 3, 0, false)));
        show("table", out, s, JsonGenerate.group("G", JsonGenerate.array("T",
            JsonGenerate.text("", Field.alphanumeric(s, 11, 2, false)), JsonGenerate.text("", Field.alphanumeric(s, 13, 2, false))),
            JsonGenerate.array("U", JsonGenerate.group("", JsonGenerate.number("Q", Field.packed(s, 9, 3, 0, false))))));
        Field e0 = Field.alphanumeric(s, 11, 2, false);
        Field e1 = Field.alphanumeric(s, 13, 2, false);
        show("odo2", out, s, JsonGenerate.group("G", JsonGenerate.table("T", 2, 0, "N", JsonGenerate.text("", e0), JsonGenerate.text("", e1))));
        show("odo0", out, s, JsonGenerate.group("G", JsonGenerate.table("T", 0, 0, "N", JsonGenerate.text("", e0), JsonGenerate.text("", e1))));
        showS("odohi", out, s, () -> JsonGenerate.table("T", 3, 0, "N", JsonGenerate.text("", e0), JsonGenerate.text("", e1)));
        showS("odolo", out, s, () -> JsonGenerate.table("T", 0, 1, "N", JsonGenerate.text("", e0)));
        Storage bad = st(0x1A, 0x2C, 0x12, 0x34, 0x0D, 0x00, 0x1D);
        Field o2 = Field.alphanumeric(bad, 100, 100, false);
        show("badnibble", o2, bad, JsonGenerate.number("P", Field.packed(bad, 0, 3, 0, true)));
        show("badsign", o2, bad, JsonGenerate.number("P", Field.packed(bad, 2, 3, 0, true)));
        show("negzero", o2, bad, JsonGenerate.number("P", Field.packed(bad, 4, 1, 0, true)));
        show("overpic", o2, bad, JsonGenerate.number("B", Field.binary(bad, 0, 2, 0, false, false)));
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
    assert out[0] == 'bin {"B":-123}' and out[1] == 'packed {"P":-123.45}'
    assert out[2] == 'native {"N":42}' and out[3] == 'pd {"D":12}'
    assert '"T":["a","b"]' in out[4] and '"U":[{"Q":12}]' in out[4]
    assert out[5] == 'odo2 {"G":{"T":["a","b"]}}' and out[6] == 'odo0 {"G":{"T":[]}}'
    assert "outside 0 to 2" in out[7] and "outside 1 to 1" in out[8] and "undefined" in out[7]
    out = out[:5] + out[9:]
    assert "non-digit data in numeric item P" in out[5] and "non-digit data in numeric item P" in out[6]
    assert "negative zero" in out[7] and "past its PICTURE's digits" in out[8]


def test_json_code_is_zero_after_a_generate_and_only_declared_when_named(tmp_path):
    """#7524: IBM's LR: JSON-CODE holds zero after a JSON GENERATE that raised no exception."""
    r = _translate(
        tmp_path, "MOVE 5 TO JSON-CODE", "JSON GENERATE OUT FROM REC COUNT N", "IF JSON-CODE = 0 DISPLAY 'OK'"
    )
    assert not r.stats["holes"]
    assert "GG_JSON_CODE" in r.java.upper().replace("-", "_")
    assert r.java.count("BigDecimal.ZERO") >= 1
    plain = _translate(tmp_path, "JSON GENERATE OUT FROM REC")
    assert "JSON_CODE" not in plain.java.upper().replace("-", "_")


@pytest.mark.parametrize(
    "body",
    [
        ["JSON GENERATE OUT FROM REC ON EXCEPTION DISPLAY JSON-CODE", "END-JSON"],
        ["JSON GENERATE OUT FROM REC", "DISPLAY JSON-CODE", "JSON PARSE OUT INTO REC"],
    ],
)
def test_a_json_code_after_an_exception_is_refused_by_name(tmp_path, body):
    r = _translate(tmp_path, *body)
    assert len(r.stats["holes"]) >= 1


def test_a_program_s_own_json_code_item_is_kept(tmp_path):
    src = tmp_path / "PROG.cbl"
    text = DATA.replace("       01  N    PIC 9(4).\n", "       01  N    PIC 9(4).\n       01  JSON-CODE PIC 9(4).\n")
    src.write_text(text + "           JSON GENERATE OUT FROM REC\n           DISPLAY JSON-CODE\n           GOBACK.\n")
    r = P.translate(src, [], "public class ProgService { }", "t")
    assert "GG_JSON_CODE" not in r.java.upper().replace("-", "_")
