"""#3986: alphanumeric relation conditions compare as the mainframe does, not as String.compareTo.

EBCDIC orders lower case before upper and letters before digits (`a` 0x81 < `A` 0xC1 < `0` 0xF0); Java's
compareTo orders digits first, so a ported `IF CUST-ID > 'A'` takes the other branch for '1001'. COBOL also
pads the shorter operand with spaces ('AB' = 'AB  '). Every generated project gets util/CobolCompare (the
code page's bytes, space-padded), and every port ticket requires it.
"""

import shutil
import subprocess
from unittest.mock import patch

import pytest

from gitgalaxy.tools.cobol_to_java.cobol_to_java_compare_forge import generate_compare_util
from gitgalaxy.tools.cobol_to_java.cobol_to_java_port_tickets import PORTING_RULES, collation_rules
from gitgalaxy.tools.cobol_to_java.port_runner import _RUNTIME_HELPERS


def test_the_runtime_compares_in_the_conversions_code_page():
    assert 'Charset.forName("IBM037")' in generate_compare_util("com.test")
    assert 'Charset.forName("IBM277")' in generate_compare_util("com.test", "cp277")
    assert generate_compare_util("com.test").startswith("package com.test.util;")


def test_every_ticket_requires_it_for_alphanumeric_conditions():
    (rule,) = [r for r in PORTING_RULES if "#3986" in r]
    assert "CobolCompare" in rule and "never String.compareTo or equals" in rule
    assert "IF CUST-ID > 'A'" in rule and "'AB' = 'AB  '" in rule and "BigDecimal.compareTo" in rule
    assert "PROGRAM COLLATING SEQUENCE" in rule
    assert "util/CobolCompare.java" in _RUNTIME_HELPERS  # the port agent is shown the class


def test_a_non_ebcdic_key_collation_is_named_in_the_ticket():
    assert collation_rules(None) == [] and collation_rules({"key_collation": "ebcdic"}) == []
    (binary,) = collation_rules({"key_collation": "binary"})
    assert "culture.key_collation: binary" in binary and "UTF-8 byte order" in binary and "TODO" in binary
    (database,) = collation_rules({"key_collation": "database"})
    assert "the database's default collation" in database


def test_every_generated_project_has_it(tmp_path):
    from gitgalaxy import cobol_to_java_controller

    clean = tmp_path / "estate_gitgalaxy_clean_x"
    clean.mkdir()
    with patch("sys.argv", ["cobol-to-java", str(clean), "--header", str(tmp_path / "none.txt")]):
        cobol_to_java_controller.main()
    (java,) = tmp_path.glob("estate_gitgalaxy_java_spring_*")
    (util,) = java.glob("src/main/java/**/util/CobolCompare.java")
    assert "public final class CobolCompare" in util.read_text(encoding="utf-8")


# (a, b, the sign of CobolCompare.compare in IBM037) -- String.compareTo disagrees on the first four
CASES = [
    ("1001", "A", 1),  # digits after letters: IF CUST-ID > 'A' is true
    ("A", "a", 1),  # upper case after lower
    ("Z", "0", -1),
    ("abc", "ABC", -1),
    ("AB", "AB  ", 0),  # the shorter operand is padded with spaces
    ("AB", "AB\u00a0", -1),  # ... with the space (0x40), not another blank (a no-break space is 0x41)
    ("", None, 0),  # a null is empty: all spaces
    ("A-1", "A 1", 1),  # '-' 0x60 > ' ' 0x40
]


@pytest.mark.skipif(not shutil.which("javac"), reason="no JDK")
def test_compare_follows_the_ebcdic_bytes(tmp_path):
    (tmp_path / "CobolCompare.java").write_text(generate_compare_util("com.test"), encoding="utf-8")

    def lit(s):
        return "null" if s is None else '"' + s.replace("\u00a0", "\\u00a0") + '"'

    checks = "\n".join(
        f'        check(Integer.signum(CobolCompare.compare({lit(a)}, {lit(b)})), {want}, {lit(a)} + " ? " + {lit(b)});'
        for a, b, want in CASES
    )
    (tmp_path / "Runner.java").write_text(
        "package com.test.util;\npublic class Runner {\n"
        "    static void check(Object got, Object want, String what) {\n"
        '        if (!want.equals(got)) throw new AssertionError(what + ": got " + got + " want " + want);\n'
        "    }\n    public static void main(String[] a) {\n" + checks + "\n"
        '        check(CobolCompare.gt("1001", "A"), true, "gt");\n'
        '        check("1001".compareTo("A") > 0, false, "compareTo disagrees");\n'
        '        check(CobolCompare.eq("AB", "AB  "), true, "eq pads");\n'
        '        check(CobolCompare.lt("ZZZZ", CobolCompare.highValues(4)), true, "HIGH-VALUES");\n'
        '        check(CobolCompare.gt("    ", CobolCompare.lowValues(4)), true, "LOW-VALUES");\n'
        '        try { CobolCompare.compare("\\u4e00", "A"); throw new AssertionError("unmappable"); }\n'
        "        catch (IllegalArgumentException expected) { }\n"
        "    }\n}\n",
        encoding="utf-8",
    )
    subprocess.run(["javac", "-d", str(tmp_path), *map(str, tmp_path.glob("*.java"))], check=True)
    run = subprocess.run(["java", "-cp", str(tmp_path), "com.test.util.Runner"], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
