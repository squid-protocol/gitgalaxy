"""#3827: DECIMAL-POINT IS COMMA reaches the schema forge, the Spring forge and the generated CobolEdit."""

import shutil
import subprocess
from pathlib import Path

import pytest

from gitgalaxy.tools.cobol_to_cobol.cobol_schema_forge import forge_schemas, parse_cobol_picture
from gitgalaxy.tools.cobol_to_java.cobol_to_java_repository_forge import cobol_edit_source
from gitgalaxy.tools.cobol_to_java.cobol_to_java_spring_forge import generate_java_entity, parse_pic_clause
from gitgalaxy.tools.cobol_to_java.java_target import Culture, JavaTarget

_JDK = Path("/usr/lib/jvm/java-17-openjdk-amd64/bin")


def test_schema_forge_reads_the_comma_as_the_decimal_point():
    assert parse_cobol_picture("ZZZ.ZZ9,99", True) == {"sql": "DECIMAL(8, 2)", "json": "number"}
    assert parse_cobol_picture("ZZZ,ZZ9.99", False) == {"sql": "DECIMAL(8, 2)", "json": "number"}
    assert parse_cobol_picture("S9(7)V99", False) == {"sql": "DECIMAL(9, 2)", "json": "number"}
    assert parse_cobol_picture("9(4)", False) == {"sql": "SMALLINT", "json": "integer"}


def test_schema_forge_finds_special_names_before_the_data_division(tmp_path):
    src = tmp_path / "DCPROG.cbl"
    src.write_text(
        "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. DCPROG.\n       ENVIRONMENT DIVISION.\n"
        "       CONFIGURATION SECTION.\n       SPECIAL-NAMES.\n           DECIMAL-POINT IS COMMA.\n"
        "       DATA DIVISION.\n       WORKING-STORAGE SECTION.\n       01 WS-REC.\n"
        "          05 WS-AMT PIC ZZZ.ZZ9,99.\n       PROCEDURE DIVISION.\n           STOP RUN.\n"
    )
    out = forge_schemas(src)
    assert out is not None
    assert "DECIMAL(8, 2)" in out["sql"]
    assert out["json"]["decimal_comma"] is True


def test_spring_forge_reads_the_whole_comma_picture():
    assert parse_pic_clause("PIC ZZZ.ZZ9,99", True) == {"precision": 8, "scale": 2}
    assert parse_pic_clause("PIC ZZZ,ZZ9.99", False) == {"precision": 8, "scale": 2}


def test_culture_decimal_point_overrides_the_program():
    schema = {
        "title": "MYTABLE",
        "decimal_comma": True,
        "properties": {"AMT": {"type": "number", "description": "Legacy PIC: 9(6),99"}},
    }
    as_program = generate_java_entity(schema, "com.test", target=JavaTarget())
    as_period = generate_java_entity(schema, "com.test", target=JavaTarget(culture=Culture(decimal_point="period")))
    assert "scale = 2" in as_program
    assert "scale = 2" not in as_period


@pytest.mark.skipif(not (_JDK / "javac").exists() or not shutil.which("true"), reason="no JDK 17")
def test_cobol_edit_formats_as_cobol(tmp_path):
    (tmp_path / "CobolEdit.java").write_text(cobol_edit_source("com.test"))
    cases = [
        ("ZZZ.ZZ9,99-", "1234.50", True, "  1.234,50 "),
        ("ZZZ.ZZ9,99-", "-1234.5", True, "  1.234,50-"),
        ("ZZZ,ZZ9.99-", "1234.50", False, "  1,234.50 "),
        ("Z(3).Z(2)9,9(2)", "7", True, "      7,00"),
        ("$ZZ9.99CR", "-12.5", False, "$ 12.50CR"),
    ]
    checks = "\n".join(
        f'        check(CobolEdit.format("{pic}", new BigDecimal("{v}"), {str(dc).lower()}, "$"), "{want}");'
        for pic, v, dc, want in cases
    )
    (tmp_path / "Runner.java").write_text(
        "package com.test.entity.vsam;\nimport java.math.BigDecimal;\npublic class Runner {\n"
        "    static void check(String got, String want) {\n"
        '        if (!want.equals(got)) throw new AssertionError("got [" + got + "] want [" + want + "]");\n'
        "    }\n    public static void main(String[] a) {\n" + checks + "\n    }\n}\n"
    )
    subprocess.run([str(_JDK / "javac"), "-d", str(tmp_path), *map(str, tmp_path.glob("*.java"))], check=True)
    run = subprocess.run([str(_JDK / "java"), "-cp", str(tmp_path), "com.test.entity.vsam.Runner"],
                         capture_output=True, text=True)  # fmt: skip
    assert run.returncode == 0, run.stderr
