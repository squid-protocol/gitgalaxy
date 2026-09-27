"""#3815: generated Java keeps national names legally (NFC, legal identifier characters, one letter per letter)
and every generated build compiles its sources as UTF-8."""

from __future__ import annotations

import shutil
import subprocess
import unicodedata
from pathlib import Path

import pytest

from gitgalaxy.tools.cobol_to_cobol.cobol_jcl_forge import analyze_cobol_intent
from gitgalaxy.tools.cobol_to_java.cobol_to_java_build_forge import generate_build_gradle, generate_pom_xml
from gitgalaxy.tools.cobol_to_java.cobol_to_java_common import container_var, java_identifier
from gitgalaxy.tools.cobol_to_java.cobol_to_java_names import (
    capitalize_name,
    java_class_base,
    lower_name,
    title_name,
)
from gitgalaxy.tools.cobol_to_java.java_target import JavaTarget

NATIONAL = ["KUNDNAVN-ÆØÅ", "100-RÆKNE", "ØKONOMI", "ÄÖÜ-FELD", "KUNDE§NR", "AÑO-FISCAL", "नाम", "CAFÉ-é",
            "STRASSE-ß", "§X"]  # fmt: skip

_START = {"Lu", "Ll", "Lt", "Lm", "Lo", "Nl", "Sc", "Pc"}
_PART = _START | {"Nd", "Mn", "Mc"}


def _java_legal(name: str) -> bool:
    """Java's Character.isJavaIdentifierStart / isJavaIdentifierPart, by Unicode category."""
    cats = [unicodedata.category(ch) for ch in name]
    return bool(name) and cats[0] in _START and all(c in _PART for c in cats)


@pytest.mark.parametrize("name", NATIONAL)
def test_national_names_give_legal_nfc_java_names(name):
    for java in (java_identifier(name), java_class_base(name), container_var(name)):
        assert _java_legal(java), java
        assert unicodedata.normalize("NFC", java) == java


@pytest.mark.parametrize(
    "name, field, cls",
    [
        ("KUNDNAVN-ÆØÅ", "kundnavnÆøå", "KundnavnÆøå"),
        ("ØKONOMI", "økonomi", "Økonomi"),  # was `konomi` / `Konomi`: the Ø was a separator
        ("100-RÆKNE", "v100Rækne", "Legacy100Rækne"),
        ("ÄÖÜ-FELD", "äöüFeld", "ÄöüFeld"),
        ("AÑO-FISCAL", "añoFiscal", "AñoFiscal"),
        ("नाम", "नाम", "नाम"),
        ("KUNDE§NR", "kunde_nr", "Kunde_nr"),  # `§` replaced, not dropped
        ("STRASSE-ß", "strasseß", "Strasseß"),  # `ß` stays one letter (str.title() makes it `Ss`)
    ],
)
def test_national_names_keep_their_letters(name, field, cls):
    assert java_identifier(name) == field
    assert java_class_base(name) == cls


def test_illegal_characters_and_eszett_do_not_collide():
    assert java_identifier("KUNDE§NR") != java_identifier("KUNDE-NR")
    assert java_identifier("KUNDE§NR") != java_identifier("KUNDENR")
    assert java_class_base("KUNDE§NR") != java_class_base("KUNDENR")
    assert java_identifier("STRASSE-ß") != java_identifier("STRASSE-SS")
    assert java_class_base("STRASSE-ß") != java_class_base("STRASSE-SS")
    assert java_class_base("ØKONOMI") != java_class_base("KONOMI")


@pytest.mark.parametrize("name", ["CAFÉ-é", "KUNDNAVN-ÆØÅ", "ÄÖÜ-FELD", "AÑO"])
def test_nfd_and_nfc_spellings_give_one_name(name):
    nfd, nfc = unicodedata.normalize("NFD", name), unicodedata.normalize("NFC", name)
    assert nfd != nfc
    assert java_identifier(nfd) == java_identifier(nfc)
    assert java_class_base(nfd) == java_class_base(nfc)
    assert container_var(nfd) == container_var(nfc)


def test_a_leading_combining_mark_is_prefixed_and_recomposed():
    assert _java_legal(java_identifier("̈A"))
    assert java_class_base("̈A") == unicodedata.normalize("NFC", "Legacÿa")


@pytest.mark.parametrize(
    "name, field, cls",
    [
        ("WS-CUST-NAME", "wsCustName", "WsCustName"),
        ("CUST_ID", "custId", "CustId"),
        ("100-TOTAL", "v100Total", "Legacy100Total"),
        ("CLASS", "classVal", "LegacyClass"),
        ("SAM2LIB-X2Y", "sam2libX2Y", "Sam2libX2y"),
        ("SAM1LIB", "sam1lib", "Sam1lib"),
        ("COBOL__SAM2", "cobolSam2", "CobolSam2"),
        ("multiroot__sam__SAM2", "multirootSamSam2", "MultirootSamSam2"),
        ("OBJECT", "object", "LegacyObject"),
    ],
)
def test_ascii_names_are_unchanged(name, field, cls):
    assert java_identifier(name) == field
    assert java_class_base(name) == cls


def test_case_helpers_match_str_methods_over_ascii():
    for word in ["SAM2LIB", "x2y", "ABC-DEF_ghi", "A#B@C$D", "", "9ZZ", "mIxEd CaSe"]:
        assert lower_name(word) == word.lower()
        assert title_name(word) == word.title()
        assert capitalize_name(word) == word.capitalize()


def test_gradle_and_maven_builds_compile_as_utf8():
    gradle = generate_build_gradle("com.acme", JavaTarget())
    assert "tasks.withType(JavaCompile).configureEach {\n    options.encoding = 'UTF-8'\n}" in gradle
    # Maven: spring-boot-starter-parent sets project.build.sourceEncoding to UTF-8 for the compiler plugin
    pom = generate_pom_xml("com.acme", "app", JavaTarget())
    assert "<artifactId>spring-boot-starter-parent</artifactId>" in pom
    assert pom.startswith('<?xml version="1.0" encoding="UTF-8"?>')


def test_a_national_select_is_still_a_batch_file(tmp_path):
    """The IR's files_requested decides batch vs transactional; a SELECT named `KUNDER-ÆØÅ` was missed, so the
    controller asked for a DTO of the DD that nothing generates and the project did not compile."""
    src = tmp_path / "ØKONOMI.cbl"
    src.write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. ØKONOMI.\n"
        "       ENVIRONMENT DIVISION.\n"
        "       FILE-CONTROL.\n"
        "           SELECT KUNDER-ÆØÅ ASSIGN TO FILØ.\n"
        "           SELECT KUNDE-NR ASSIGN TO UT-S-FILEB.\n",
        encoding="utf-8",
    )
    intent = analyze_cobol_intent(src)
    assert intent["program_id"] == "ØKONOMI"
    assert intent["files_requested"] == [
        {"internal": "KUNDER-ÆØÅ", "dd_name": "FILØ"},
        {"internal": "KUNDE-NR", "dd_name": "FILEB"},
    ]


JAVAC = Path("/usr/lib/jvm/java-17-openjdk-amd64/bin/javac")


@pytest.mark.skipif(not JAVAC.is_file() and not shutil.which("javac"), reason="no JDK")
def test_a_class_named_from_national_names_compiles(tmp_path):
    javac = str(JAVAC) if JAVAC.is_file() else shutil.which("javac")
    cls = java_class_base("ØKONOMI") + "Service"
    fields = [java_identifier(n) for n in NATIONAL]
    body = "".join(f"    private String {f};\n" for f in fields)
    src = tmp_path / f"{cls}.java"
    src.write_text(f"public class {cls} {{\n{body}}}\n", encoding="utf-8")
    proc = subprocess.run([javac, "-encoding", "UTF-8", "-d", str(tmp_path / "out"), str(src)],
                          capture_output=True, text=True, timeout=120)  # fmt: skip
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "out" / f"{cls}.class").is_file()
