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
