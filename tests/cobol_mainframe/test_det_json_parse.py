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
        ("JSON PARSE JIN INTO REC ON EXCEPTION DISPLAY 'X'\n           END-JSON", "ON phrase"),
        ("JSON PARSE JIN INTO REC NAME OF AMT IS OMITTED", "NAME needs an alphanumeric literal"),
        ("JSON PARSE JIN INTO REC CONVERTING", "CONVERTING phrase"),
    ],
)
def test_a_shape_the_model_does_not_take_is_refused_by_name(tmp_path, stmt, why):
    r = _translate(tmp_path, stmt)
    assert len(r.stats["holes"]) == 1
    hole = str(r.stats["holes"][0])
    assert "JSON PARSE (Enterprise COBOL 6.1+): not modelled" in hole and why in hole


def test_an_elementary_receiver_is_refused_by_name(tmp_path):
    r = _translate(tmp_path, "JSON PARSE JIN INTO CUST-NAME")
    assert len(r.stats["holes"]) == 1 and "JSON PARSE: CUST-NAME is not a plain group" in r.stats["holes"][0]


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
    assert out[3] == "[########][999]"
    assert out[4] == "[########][999]"
    for i, why in ((5, "9 characters"), (6, "takes a JSON number"), (7, "decimals"), (8, "does not fit"),
                   (9, "unsigned"), (10, "exception condition"), (11, "array"), (12, "beyond ASCII")):  # fmt: skip
        assert "refused" in out[i] and why in out[i], out[i]
