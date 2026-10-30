"""easytrieve strict structural-signature coverage."""

import sys
from pathlib import Path

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune


def test_easytrieve_calls_out_strict():
    lang = LANGUAGE_DEFINITIONS["easytrieve"]
    rule = lang["rules"]["calls_out"]

    assert rule.findall("PERFORM MY-PROC") == ["MY-PROC"]
    assert rule.findall("  CALL EXTERNAL-PGM") == ["EXTERNAL-PGM"]
    assert rule.findall("EXEC SUB-01") == ["SUB-01"]

    assert rule.findall("PERFORM") == []

    assert rule.groups == 1
    assert_redos_immune(rule, "PERFORM " + "A" * 100000)


def test_easytrieve_func_start_strict():
    lang = LANGUAGE_DEFINITIONS["easytrieve"]
    rule = lang["rules"]["func_start"]

    assert [m.group(1) for m in rule.finditer("JOB INPUT FILEA\n")] == ["INPUT"]
    assert [m.group(1) for m in rule.finditer("PROC MY-PROC\n")] == ["MY-PROC"]
    assert [m.group(1) for m in rule.finditer("MACRO MY-MACRO\n")] == ["MY-MACRO"]

    # Must be at line start
    assert [m.group(1) for m in rule.finditer("  PROC SUB")] == ["SUB"]
    assert [m.group(1) for m in rule.finditer("IF X = Y PROC SUB")] == []

    assert rule.groups == 1
    assert_redos_immune(rule, "PROC " + "A" * 100000)


def test_easytrieve_branch_strict():
    lang = LANGUAGE_DEFINITIONS["easytrieve"]
    rule = lang["rules"]["branch"]

    assert len(rule.findall("IF A = B")) == 1
    assert len(rule.findall("END-IF")) == 1
    assert len(rule.findall("DO WHILE")) == 2

    assert_redos_immune(rule, "IF " + "A" * 100000)


def test_easytrieve_io_strict():
    lang = LANGUAGE_DEFINITIONS["easytrieve"]
    rule = lang["rules"]["io"]

    assert len(rule.findall("GET FILEA")) == 1
    assert len(rule.findall("PRINT REPORT-1")) == 1
    assert len(rule.findall("WRITE FILEB FROM REC")) == 1

    assert_redos_immune(rule, "GET " + "A" * 100000)


def test_easytrieve_state_mutation_strict():
    lang = LANGUAGE_DEFINITIONS["easytrieve"]
    rule = lang["rules"]["state_mutation"]

    assert [m.group(1) for m in rule.finditer("X = 1\n")] == ["X"]
    assert [m.group(1) for m in rule.finditer("  FIELD-A = B\n")] == ["FIELD-A"]
    # move to syntax does not capture group 1, it just matches
    assert len(rule.findall("MOVE 'A' TO B")) == 1

    assert_redos_immune(rule, "X = " + "1" * 100000)
    assert_redos_immune(rule, "MOVE " + "A" * 100000 + " TO B")


def test_easytrieve_dead_code_strict():
    lang = LANGUAGE_DEFINITIONS["easytrieve"]
    rule = lang["rules"]["dead_code"]

    assert len(rule.findall("* IF A = B")) == 1
    assert len(rule.findall("  * PERFORM X")) == 1
    assert len(rule.findall("* just a comment")) == 0

    assert_redos_immune(rule, "* IF " + "A" * 100000)


def test_easytrieve_structural_boundaries_strict():
    lang = LANGUAGE_DEFINITIONS["easytrieve"]
    rule = lang["rules"]["structural_boundaries"]

    assert len(rule.findall("END-PROC")) == 1
    assert len(rule.findall("END-MACRO")) == 1
    assert len(rule.findall("RETURN")) == 1
    assert len(rule.findall("GOTO XYZ")) == 1
    assert len(rule.findall("GO TO ABC")) == 1


def test_easytrieve_high_risk_execution_strict():
    lang = LANGUAGE_DEFINITIONS["easytrieve"]
    rule = lang["rules"]["high_risk_execution"]

    assert len(rule.findall("STOP EXECUTE")) == 1
    assert len(rule.findall("EXIT")) == 1


def test_easytrieve_hardcoded_secrets_strict():
    lang = LANGUAGE_DEFINITIONS["easytrieve"]
    rule = lang["rules"]["hardcoded_secrets"]

    assert len(rule.findall("PASSWORD = 'mysecret'")) == 1
    assert len(rule.findall('PWD = "supersecret123"')) == 1
    assert len(rule.findall("SECRET='small'")) == 1
    assert len(rule.findall("PASSWORD = 'x'")) == 0  # too short


def test_easytrieve_macros_strict():
    lang = LANGUAGE_DEFINITIONS["easytrieve"]
    rule = lang["rules"]["macros"]

    assert len(rule.findall("MACRO MY-MAC")) == 1
    assert len(rule.findall("  MACRO")) == 1
    assert len(rule.findall("X = MACRO")) == 0


def test_easytrieve_planned_debt_strict():
    lang = LANGUAGE_DEFINITIONS["easytrieve"]
    rule = lang["rules"]["planned_debt"]

    assert len(rule.findall("* TODO: fix this")) == 1
    assert len(rule.findall("  * FIXME : later")) == 1
    assert len(rule.findall("TODO fix this")) == 0  # missing comment marker


def test_easytrieve_internal_discriminator_strict():
    disc = LANGUAGE_DEFINITIONS["easytrieve"]["internal_discriminator"]
    assert disc is not None

    # Positive matches: Easytrieve statement shapes
    assert disc.search("FILE INPUT1")
    assert disc.search("  FILE INPUT1 FB(80 800)")
    assert disc.search("FILE &FILE ORGANIZATION &ORG")
    assert disc.search("JOB INPUT")
    assert disc.search("JOB INPUT FILEA")
    assert disc.search("  JOB INPUT(INPUT1)")
    assert disc.search("JOB MYJOB INPUT(PERSNL)")
    assert disc.search("PRINT")
    assert disc.search("PRINT REPORT-1")
    assert disc.search("  PRINT RPT1")
    assert disc.search("REPORT REPORT-1")
    assert disc.search("PROC MY-PROC")
    assert disc.search("MACRO 2 FILE SIZE")
    assert disc.search("MACRO &COUNT")
    assert disc.search("MACRO MYMAC")
    assert disc.search("END-PROC")
    assert disc.search("END-MACRO")
    assert disc.search("END-JOB")
    assert disc.search("END-REPORT")
    assert disc.search("%MSTFILE CUSTOMER 100")
    # Names that merely START with an HLASM opcode spelling (the opcode guard is word-bounded)
    assert disc.search("FILE DSNIN FB(80 800)")
    assert disc.search("FILE STUDENT FB(80 800)")
    assert disc.search("FILE LAYOUT")
    assert disc.search("JOB JOBS")
    assert disc.search("PRINT ONELINE")
    assert disc.search("REPORT STATS")
    assert disc.search("SORT STFILE")

    # Negative matches: HLASM labels followed by HLASM opcodes
    assert not disc.search("FILE     DC    CL80' '")
    assert not disc.search("FILE     DS    0H")
    assert not disc.search("FILE     EQU   *")
    assert not disc.search("JOB      CSECT")
    assert not disc.search("JOB      USING *,15")
    assert not disc.search("PRINT    EQU   *")
    assert not disc.search("         PRINT NOGEN")
    assert not disc.search("         PRINT GEN")

    # #7064: NASM / preprocessor `%` directives are not Easytrieve macro calls
    for directive in (
        "%macro proc 1",
        "%MACRO proc 1",
        "%endmacro",
        "%define X 1",
        "%xdefine X 1",
        "%include 'a.inc'",
        "%ifdef X",
        "%ifndef X",
        "%ifnidni a, b",
        "%elifdef X",
        "%else",
        "%endif",
        "%rep 4",
        "%endrep",
        "%assign i 1",
        "%1:",
    ):
        assert not disc.search(directive), directive
    assert disc.search("%MACROX 1")  # a name that merely starts with a directive word

    # ReDoS immunity
    assert_redos_immune(disc, "   " * 10000)
    assert_redos_immune(disc, "FILE " + "A" * 100000)
    assert_redos_immune(disc, "JOB " + "A" * 100000)
    assert_redos_immune(disc, "PRINT " + "A" * 100000)
    assert_redos_immune(disc, "MACRO " + "A" * 100000)
    assert_redos_immune(disc, "%" + "A" * 100000)
    assert_redos_immune(disc, "END-MACRO" + "A" * 100000)
