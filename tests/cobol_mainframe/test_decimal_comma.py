"""#3827: DECIMAL-POINT IS COMMA reaches the schema forge, the Spring forge and the generated CobolEdit.

#3984: a VSAM entity of such a program keeps an edited PICTURE (`999,99`) as its display text, never a
BigDecimal read with the period as its decimal point (123,45 as 12345), and the program's port ticket names
its decimal point -- a real scan of a small estate through the refractor and cobol-to-java backs both."""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import gitgalaxy.cobol_refractor_controller as refractor
import gitgalaxy.cobol_to_java_controller as java_controller
from gitgalaxy.tools.cobol_to_cobol.cobol_schema_forge import forge_schemas, parse_cobol_picture
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import scan_to_db
from gitgalaxy.tools.cobol_to_java.cobol_to_java_port_tickets import PORTING_RULES, decimal_point_rules
from gitgalaxy.tools.cobol_to_java.cobol_to_java_repository_forge import _pic_numeric, cobol_edit_source
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


# ---- #3984: the VSAM entity and the port ticket of a DECIMAL-POINT IS COMMA program ----------------
EUROBAT = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. EUROBAT.
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       SPECIAL-NAMES.
           DECIMAL-POINT IS COMMA.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT EURO-FILE ASSIGN TO EURODD
               ORGANIZATION IS INDEXED
               ACCESS MODE IS RANDOM
               RECORD KEY IS EU-ID.
       DATA DIVISION.
       FILE SECTION.
       FD  EURO-FILE.
       01  EU-REC.
           05 EU-ID           PIC 9(8).
           05 EU-AMT          PIC 999,99.
           05 EU-EDIT         PIC ZZZ.ZZ9,99.
           05 EU-RAW          PIC S9(5)V99.
       PROCEDURE DIVISION.
       000-MAIN.
           OPEN I-O EURO-FILE.
           READ EURO-FILE.
           REWRITE EU-REC.
           CLOSE EURO-FILE.
           STOP RUN.
"""
USBAT = EUROBAT.replace("EUROBAT", "USBAT").replace("           DECIMAL-POINT IS COMMA.\n", "")
USBAT = USBAT.replace("EURO-FILE", "US-FILE").replace("EURODD", "USDD").replace("EU-", "US-")
USBAT = USBAT.replace("999,99", "999.99").replace("ZZZ.ZZ9,99", "ZZZ,ZZ9.99")
JOB = """\
//EUROJOB  JOB CLASS=A
//DEFINE   EXEC PGM=IDCAMS
//SYSIN    DD *
   DEFINE CLUSTER (NAME(APP.EURO.KSDS) INDEXED -
          KEYS(8 0) RECORDSIZE(31 31))
   DEFINE CLUSTER (NAME(APP.US.KSDS) INDEXED -
          KEYS(8 0) RECORDSIZE(31 31))
/*
//STEP1    EXEC PGM=EUROBAT
//EURODD   DD DSN=APP.EURO.KSDS,DISP=OLD
//STEP2    EXEC PGM=USBAT
//USDD     DD DSN=APP.US.KSDS,DISP=OLD
"""


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    """The generated project of an estate with one DECIMAL-POINT IS COMMA program and one without."""
    base = tmp_path_factory.mktemp("decimal_comma_estate")
    repo = base / "src_estate"
    for rel, text in {"cbl/EUROBAT.cbl": EUROBAT, "cbl/USBAT.cbl": USBAT, "jcl/EUROJOB.jcl": JOB}.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    out = base / "run"
    out.mkdir()
    work = out / "estate"
    shutil.copytree(repo, work)
    db = scan_to_db(repo, out / "scan")
    with patch.object(sys, "argv", ["refract", str(work), "--galaxy-db", str(db)]):
        refractor.main()
    (clean,) = out.glob("estate_gitgalaxy_clean_*")
    with patch.object(sys, "argv", ["cobol-to-java", str(clean), "--header", str(out / "none.txt")]):
        java_controller.main()
    (java,) = out.glob("estate_gitgalaxy_java_spring_*")
    return java


def test_the_codec_reads_no_edited_picture_as_a_number():
    assert _pic_numeric("999,99") is None and _pic_numeric("ZZZ.ZZ9,99") is None
    assert _pic_numeric("S9(5)V99") == (True, 7, 2)


def test_a_vsam_entity_keeps_the_comma_pictures_as_their_text(generated):
    entity = (generated / "src/main/java/com/gitgalaxy/modernized/entity/vsam/EuRec.java").read_text(encoding="utf-8")
    assert '@Column(name = "EU_AMT", length = 6)\n    private String euAmt;' in entity
    assert '@Column(name = "EU_EDIT", length = 10)\n    private String euEdit;' in entity
    assert '@Column(name = "EU_RAW", precision = 7, scale = 2)\n    private BigDecimal euRaw;' in entity
    assert "r.euAmt = CobolRecords.text(rec, 8, 6, text);" in entity  # 123,45 stays 123,45
    assert "r.euRaw = CobolRecords.zoned(rec, 24, 7, 2, text);" in entity


def test_the_port_ticket_names_the_programs_decimal_point(generated):
    jobs = generated / "ai_agent_jobs"
    euro = json.loads((jobs / "EUROBAT_port_ticket.json").read_text(encoding="utf-8"))
    (rule,) = [r for r in euro["rules"] if "#3984" in r]
    assert rule.startswith("This program codes DECIMAL-POINT IS COMMA (SPECIAL-NAMES, line 6)")
    assert "decimalComma = true" in rule and "Pass ','" in rule
    assert rule in (jobs / "EUROBAT_port_ticket.md").read_text(encoding="utf-8")
    us = json.loads((jobs / "USBAT_port_ticket.json").read_text(encoding="utf-8"))
    assert us["rules"] == PORTING_RULES  # no DECIMAL-POINT IS COMMA: today's rules


def test_culture_decimal_point_overrides_the_program_in_the_ticket():
    comma = "       SPECIAL-NAMES.\n           DECIMAL-POINT IS COMMA.\n       DATA DIVISION.\n"
    (auto,) = decimal_point_rules(comma, {"decimal_point": "auto"})
    assert "line 2" in auto and "decimalComma = true" in auto
    assert decimal_point_rules(comma, None) == [auto]
    (period,) = decimal_point_rules(comma, {"decimal_point": "period"})
    assert "culture.decimal_point: period" in period and "decimalComma = false" in period
    (declared,) = decimal_point_rules("", {"decimal_point": "comma"})
    assert "is ported with culture.decimal_point: comma" in declared and "decimalComma = true" in declared
    assert decimal_point_rules("", {"decimal_point": "auto"}) == []
    assert decimal_point_rules("", {"decimal_point": "period"}) == []
