"""#3831: the generated CobolRecords runtime accepts only ASCII digits, as COBOL does.

Java's number parsers accept any Unicode decimal digit -- `new BigInteger("١٢")`
(Arabic-Indic), `"１２"` (full-width) and `Integer.parseInt("१२")` (Devanagari) all
give 12 -- so `CobolRecords.zoned` / `decimal` took data a mainframe's NUMERIC test
and NUMVAL reject. And `decimal("1,5")` threw even in a DECIMAL-POINT IS COMMA
program. The runtime now checks `0`-`9` itself and carries a NUMVAL that takes the
program's decimal point.

The Java is compiled and run with the local JDK; without one the test is skipped
(java-compile.yml compiles the generated project in CI).
"""

import shutil
import subprocess

import pytest

from gitgalaxy.tools.cobol_to_java.cobol_to_java_repository_forge import COBOL_RECORDS_JAVA

# (expression, expected output). "INVALID" = COBOL's invalid-data path, a NumberFormatException.
CASES = [
    ('CobolRecords.numval("123")', "123"),
    ('CobolRecords.numval("  -12.50 ")', "-12.50"),
    ('CobolRecords.numval("12.5-")', "-12.5"),
    ('CobolRecords.numval("12.5 CR")', "-12.5"),
    ('CobolRecords.numval("+ .5")', "0.5"),
    ("CobolRecords.numval(\"1,5\", ',')", "1.5"),  # DECIMAL-POINT IS COMMA
    ("CobolRecords.numval(\"1.5\", ',')", "INVALID"),
    ('CobolRecords.numval("1,5")', "INVALID"),
    ('CobolRecords.numval("١٢٣")', "INVALID"),  # Arabic-Indic digits
    ('CobolRecords.numval("１２３")', "INVALID"),  # full-width digits
    ('CobolRecords.numval("१२")', "INVALID"),  # Devanagari digits
    ('CobolRecords.numval("1 2")', "INVALID"),
    ('CobolRecords.numval(".")', "INVALID"),
    ('CobolRecords.numval("-")', "INVALID"),
    ('CobolRecords.numval("1e5")', "INVALID"),
    ('CobolRecords.decimal("١٢٣")', "INVALID"),
    ('CobolRecords.decimal("１２３")', "INVALID"),
    ('CobolRecords.decimal(" 42 ")', "42"),
    ("CobolRecords.decimal(\"3,25\", ',')", "3.25"),
    ("CobolRecords.decimal(Integer.valueOf(7))", "7"),
    ('CobolRecords.zoned("00123".getBytes(UTF), 0, 5, 2, UTF)', "1.23"),
    ('CobolRecords.zoned("0012C".getBytes(UTF), 0, 5, 0, UTF)', "123"),
    ('CobolRecords.zoned("١٢٣".getBytes(UTF), 0, "١٢٣".getBytes(UTF).length, 0, UTF)', "INVALID"),
    ('CobolRecords.zoned("１２3".getBytes(UTF), 0, "１２3".getBytes(UTF).length, 0, UTF)', "INVALID"),
]


@pytest.mark.skipif(shutil.which("javac") is None or shutil.which("java") is None, reason="no JDK")
def test_cobol_records_reads_only_ascii_digits(tmp_path):
    pkg = tmp_path / "t"
    pkg.mkdir()
    source = COBOL_RECORDS_JAVA.replace("__PACKAGE__", "t")
    source = source.replace("__POSITIVE__", "{ABCDEFGHI").replace("__NEGATIVE__", "}JKLMNOPQR")
    (pkg / "CobolRecords.java").write_text(source, encoding="utf-8")
    calls = "\n".join(f"        run(() -> String.valueOf({expr}));" for expr, _ in CASES)
    (pkg / "Probe.java").write_text(
        "package t;\n"
        "import java.nio.charset.Charset;\n"
        "import java.nio.charset.StandardCharsets;\n"
        "import java.util.concurrent.Callable;\n"
        "public class Probe {\n"
        "    static final Charset UTF = StandardCharsets.UTF_8;\n"
        "    static void run(Callable<String> c) {\n"
        "        try { System.out.println(c.call()); }\n"
        '        catch (NumberFormatException e) { System.out.println("INVALID"); }\n'
        '        catch (Exception e) { System.out.println("ERROR " + e); }\n'
        "    }\n"
        "    public static void main(String[] a) {\n"
        f"{calls}\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    subprocess.run(
        [
            "javac",
            "-encoding",
            "UTF-8",
            "-d",
            str(tmp_path / "out"),
            str(pkg / "CobolRecords.java"),
            str(pkg / "Probe.java"),
        ],
        check=True,
        capture_output=True,
    )
    run = subprocess.run(
        ["java", "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(tmp_path / "out"), "t.Probe"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    got = run.stdout.splitlines()
    assert [(expr, out) for (expr, _), out in zip(CASES, got)] == CASES
