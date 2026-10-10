"""#3985: a PIC X field's width is bytes, and a mixed DBCS page's Shift-Out / Shift-In bytes count.

IBM's mixed EBCDIC pages (cp930 / cp939 Japanese, cp933 Korean, cp935 / cp937 Chinese) wrap each run of
double-byte characters in Shift-Out (0x0E) and Shift-In (0x0F). `AB日本C` is 5 Java characters and 9 bytes
in IBM939, so a 12-byte field decodes to an 8-character String. Reading and re-writing it is lossless; the
defect was the write of a value too wide for its field: putText cut the encoded bytes, leaving a Shift-Out
with no Shift-In and half a double-byte character (`AB日` + garbage). It now keeps whole characters
(CobolRecords.fit), and width / fit give the port the field's byte geometry. On a single-byte page the
bytes are exactly what they were.

The Java is compiled and run with the local JDK (IBM939 ships with it); without one the test is skipped.
"""

import shutil
import subprocess

import pytest

from gitgalaxy.tools.cobol_to_java.cobol_to_java_port_tickets import PORTING_RULES, multibyte_rules
from gitgalaxy.tools.cobol_to_java.cobol_to_java_repository_forge import COBOL_RECORDS_JAVA

# (expression, expected output); J = IBM939 (mixed Japanese Latin-Kanji), E = IBM037 (single byte)
CASES = [
    ('hex(bytesOf("AB日本C", J))', "C1C20E456245660FC3"),  # SO, two double-byte characters, SI
    ('String.valueOf(CobolRecords.width("AB日本C", J))', "9"),
    ("String.valueOf(CobolRecords.width(null, J))", "0"),
    # a 12-byte field: the String is shorter than the field, and writing it back is byte-exact
    ('String.valueOf(CobolRecords.text(put(12, "AB日本C", J), 0, 12, J).length())', "8"),
    ('hex(put(12, CobolRecords.text(put(12, "AB日本C", J), 0, 12, J), J))', "C1C20E456245660FC3404040"),
    # too wide: whole characters go, the Shift-Out run is closed, the rest is spaces
    ('hex(put(6, "AB日本", J))', "C1C20E45620F"),  # AB + SO 日 SI (6 bytes)
    ('hex(put(7, "AB日本", J))', "C1C20E45620F40"),  # 日本 needs 8: one character, then a space
    ('hex(put(8, "AB日本", J))', "C1C20E456245660F"),
    ('hex(put(4, "AB日本", J))', "C1C24040"),  # 日 needs SO + 2 + SI: none fits after AB
    ('CobolRecords.text(put(6, "AB日本", J), 0, 6, J)', "AB日"),
    ('"[" + CobolRecords.fit("AB日本", 7, J) + "]"', "[AB日 ]"),
    ('String.valueOf(CobolRecords.width(CobolRecords.fit("AB日本C", 20, J), J))', "20"),
    ('"[" + CobolRecords.fit(null, 3, J) + "]"', "[   ]"),
    # a single-byte page: the MOVE as before -- cut at the width, padded with spaces
    ('hex(put(4, "ABCDEF", E))', "C1C2C3C4"),
    ('hex(put(6, "AB", E))', "C1C2404040" + "40"),
    ('"[" + CobolRecords.fit("ABCDEF", 4, E) + "]"', "[ABCD]"),
    # a supplementary character (a surrogate pair) is never split
    ('"[" + CobolRecords.fit("A\\uD83D\\uDE00B", 3, StandardCharsets.UTF_8) + "]"', "[A  ]"),
    ('"[" + CobolRecords.fit("A\\uD83D\\uDE00B", 5, StandardCharsets.UTF_8) + "]"', "[A\U0001f600]"),
]


@pytest.mark.skipif(shutil.which("javac") is None or shutil.which("java") is None, reason="no JDK")
def test_text_fields_keep_their_byte_width(tmp_path):
    pkg = tmp_path / "t"
    pkg.mkdir()
    source = COBOL_RECORDS_JAVA.replace("__PACKAGE__", "t")
    source = source.replace("__POSITIVE__", "{ABCDEFGHI").replace("__NEGATIVE__", "}JKLMNOPQR")
    (pkg / "CobolRecords.java").write_text(source, encoding="utf-8")
    # UTF-8 whatever the console's code page: -Dstdout.encoding is JDK 19+, and a JDK 17 on Windows writes cp1252
    lines = "\n".join(f"        out.println({expr});" for expr, _ in CASES)
    (pkg / "Probe.java").write_text(
        "package t;\n"
        "import java.nio.charset.Charset;\n"
        "import java.nio.charset.StandardCharsets;\n"
        "public class Probe {\n"
        '    static final Charset J = Charset.forName("IBM939");\n'
        '    static final Charset E = Charset.forName("IBM037");\n'
        "    static byte[] bytesOf(String s, Charset cs) { return s.getBytes(cs); }\n"
        "    static byte[] put(int width, String value, Charset cs) {\n"
        "        byte[] rec = CobolRecords.blank(width, cs);\n"
        "        CobolRecords.putText(rec, 0, width, value, cs);\n"
        "        return rec;\n"
        "    }\n"
        "    static String hex(byte[] b) {\n"
        "        StringBuilder s = new StringBuilder();\n"
        '        for (byte x : b) s.append(String.format("%02X", x));\n'
        "        return s.toString();\n"
        "    }\n"
        "    public static void main(String[] a) throws Exception {\n"
        '        java.io.PrintStream out = new java.io.PrintStream(new java.io.FileOutputStream(java.io.FileDescriptor.out), true, "UTF-8");\n'
        f"{lines}\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["javac", "-encoding", "UTF-8", "-d", str(tmp_path / "out"), str(pkg / "CobolRecords.java"),
         str(pkg / "Probe.java")],
        check=True,
    )  # fmt: skip
    run = subprocess.run(
        ["java", "-Dstdout.encoding=UTF-8", "-cp", str(tmp_path / "out"), "t.Probe"],
        capture_output=True,
        encoding="utf-8",
        check=True,
    )
    got = run.stdout.splitlines()
    assert [(expr, g) for (expr, _), g in zip(CASES, got, strict=False)] == [
        (expr, want) for expr, want in CASES
    ]  # reason: length may differ


def test_a_multibyte_code_page_gets_the_width_rule():
    for code_page in ("cp930", "cp939", "cp933", "cp935", "cp937", "shift_jis", "cp932"):
        (rule,) = multibyte_rules({"code_page": code_page})
        assert rule.startswith(f"This migration's code page ({code_page}) is multi-byte")
        assert "CobolRecords.width" in rule and "CobolRecords.fit" in rule and "substring()" in rule
        assert "reference modification" in rule and "#3985" in rule
    assert not any("#3985" in r for r in PORTING_RULES)  # only where it applies


def test_a_single_byte_code_page_keeps_todays_rules():
    for data in (None, {}, {"code_page": "cp037"}, {"code_page": "cp277"}, {"code_page": "cp1047"},
                 {"code_page": "cp1252"}):  # fmt: skip
        assert multibyte_rules(data) == []
    assert multibyte_rules({"code_page": "no-such-page"}) == []
