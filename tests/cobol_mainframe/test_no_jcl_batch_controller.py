"""#3992: a batch program with no JCL -- a PC dialect (GnuCOBOL, opensourcecobol4j, Micro Focus) that ASSIGNs its
files to literals -- gets a REST controller that compiles: its files are uploads (MultipartFile), and the controller
names no class the run does not generate (it used to bind `@RequestBody TestFileDTO`, which nothing writes)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import gitgalaxy.cobol_refractor_controller as refractor
import gitgalaxy.cobol_to_java_controller as java_controller
from gitgalaxy.tools.cobol_to_cobol.cobol_jcl_forge import analyze_cobol_intent
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import scan_to_db
from gitgalaxy.tools.cobol_to_java.cobol_to_java_api_contract_forge import generate_rest_controller


def _program(pgm: str, select: str, fd: str, open_: str) -> str:
    return (
        "       IDENTIFICATION DIVISION.\n"
        f"       PROGRAM-ID. {pgm}.\n"
        "       ENVIRONMENT DIVISION.\n"
        "       INPUT-OUTPUT SECTION.\n"
        "       FILE-CONTROL.\n"
        f"           {select}\n"
        "                  ORGANIZATION SEQUENTIAL\n"
        "                  FILE STATUS F-STATUS.\n"
        "       DATA DIVISION.\n"
        "       FILE SECTION.\n"
        f"       FD {fd}.\n"
        "       01 TEST-RECORD PIC X(10).\n"
        "       WORKING-STORAGE SECTION.\n"
        "       77 F-STATUS PIC X(02).\n"
        "       PROCEDURE DIVISION.\n"
        f"           OPEN {open_} {fd}.\n"
        "           DISPLAY F-STATUS.\n"
        f"           CLOSE {fd}.\n"
        "           STOP RUN.\n"
    )


# The issue's reproduction, and the other literal / OPTIONAL shapes of the opensourcecobol4j jp-compat suite
ESTATE = {
    "ASGPATH.cbl": _program("ASGPATH", 'SELECT TEST-FILE ASSIGN "TEST-FILE"', "TEST-FILE", "I-O"),
    "ASGDOT.cbl": _program("ASGDOT", 'SELECT TEST-FILE ASSIGN "./TEST-FILE"', "TEST-FILE", "EXTEND"),
    "ASGTO.cbl": _program("ASGTO", 'SELECT IN-FILE ASSIGN TO "./input.txt"', "IN-FILE", "INPUT"),
    "ASGDIGIT.cbl": _program("ASGDIGIT", "SELECT OPTIONAL F1 ASSIGN TO '01.DAT'", "F1", "INPUT"),
}


# ---------------------------------------------------------------------------------------------------------------
# The intent reader: the SELECT forms the engine reads (mainframe_boundary._SELECT_ASSIGN)
# ---------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("select", "internal", "dd_name"),
    [
        ('SELECT TEST-FILE ASSIGN "TEST-FILE"', "TEST-FILE", "TEST-FILE"),
        ('SELECT TEST-FILE ASSIGN "./TEST-FILE"', "TEST-FILE", "./TEST-FILE"),
        ('SELECT IN-FILE ASSIGN TO "./input.txt"', "IN-FILE", "./input.txt"),
        ("SELECT IN-FILE ASSIGN TO 'S01'", "IN-FILE", "S01"),
        ("SELECT OPTIONAL F1 ASSIGN TO UT-S-DD1", "F1", "DD1"),
        ("SELECT F2 ASSIGN TO DD2", "F2", "DD2"),  # the word forms read as before
        ("SELECT F3 ASSIGN DD3", "F3", "DD3"),
    ],
)
def test_select_assign_reads_literals_and_optional(tmp_path, select, internal, dd_name):
    pgm = tmp_path / "IO.cbl"
    pgm.write_text(f"       FILE-CONTROL.\n           {select}\n               ORGANIZATION SEQUENTIAL.\n")
    assert analyze_cobol_intent(pgm)["files_requested"] == [{"internal": internal, "dd_name": dd_name}]


def test_assign_to_a_literal_never_reads_the_to_keyword(tmp_path):
    """`ASSIGN TO "x"` backtracked past the optional TO and read `TO` itself as the DD (`@RequestParam("toFile")`);
    an empty or unclosed literal is no file, not `TO`."""
    pgm = tmp_path / "IO.cbl"
    pgm.write_text(
        "       FILE-CONTROL.\n"
        '           SELECT F-EMPTY ASSIGN TO "".\n'
        '           SELECT F-OPEN ASSIGN TO "' + "X" * 2000 + ".\n"
    )
    assert analyze_cobol_intent(pgm)["files_requested"] == []


# ---------------------------------------------------------------------------------------------------------------
# The controller
# ---------------------------------------------------------------------------------------------------------------


def _ir(inputs, files_requested=(), is_cics=False, outputs=()):
    return {
        "metadata": {"file_name": "ASGPATH.cbl"},
        "analysis": {
            "base_intent": {"files_requested": list(files_requested), "is_cics": is_cics},
            "lineage": {"inputs": list(inputs), "outputs": list(outputs)},
        },
    }


def test_a_non_cics_program_with_input_files_is_batch_without_selects():
    """The issue's IR: lineage.inputs = ['TEST-FILE'], files_requested = [], is_cics = False."""
    java = generate_rest_controller(_ir(["TEST-FILE"], outputs=["TEST-FILE"]), "com.acme")
    assert '@PostMapping(value = "/execute-batch", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)' in java
    assert '@RequestParam("testFileFile") MultipartFile testFileFile' in java
    assert "import org.springframework.web.multipart.MultipartFile;" in java
    assert "DTO" not in java and "@RequestBody" not in java


def test_the_selects_still_decide_the_upload_parameters():
    ir = _ir(["INDD"], files_requested=[{"internal": "IN-FILE", "dd_name": "INDD"}, {"dd_name": "OUTDD"}])
    java = generate_rest_controller(ir, "com.acme")
    assert '@RequestParam("inddFile") MultipartFile inddFile' in java
    assert '@RequestParam("outddFile") MultipartFile outddFile' in java


def test_a_cics_program_names_no_request_dto_for_its_files():
    """The transactional branch lists a file input for the porter; it never binds a <File>DTO nothing generates."""
    java = generate_rest_controller(_ir(["CUSTFILE"], is_cics=True), "com.acme")
    assert '@PostMapping("/execute")' in java
    assert "// Input files: CUSTFILE (no request DTO is generated for them)" in java
    assert "DTO " not in java.replace("request DTO is", "") and "@RequestBody" not in java


@pytest.mark.parametrize(
    ("dd_name", "var"),
    [("01.DAT", "file01DatFile"), ("./input.txt", "inputTxtFile"), ("KUNDE§NR", "kunde_nrFile")],
)
def test_a_literal_dd_name_becomes_a_legal_java_identifier(dd_name, var):
    java = generate_rest_controller(_ir([], files_requested=[{"dd_name": dd_name}]), "com.acme")
    assert f'@RequestParam("{var}") MultipartFile {var}' in java


# ---------------------------------------------------------------------------------------------------------------
# End to end: scan, refract and generate the no-JCL estate; every class a controller names is generated, and
# (with a JDK 17 and Maven that resolve offline) the project compiles.
# ---------------------------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    base = tmp_path_factory.mktemp("no_jcl_batch")
    repo = base / "estate"
    repo.mkdir()
    for name, text in ESTATE.items():
        (repo / name).write_text(text, encoding="utf-8")
    db = scan_to_db(repo, base / "scan")
    with patch.object(sys, "argv", ["refract", str(repo), "--galaxy-db", str(db)]):
        refractor.main()
    (clean,) = base.glob("estate_gitgalaxy_clean_*")
    (base / "none.txt").write_text("", encoding="utf-8")
    with patch.object(sys, "argv", ["cobol-to-java", str(clean), "--header", str(base / "none.txt")]):
        java_controller.main()
    (java,) = base.glob("estate_gitgalaxy_java_spring_*")
    return java


_TYPE_USE = re.compile(r"@Request(?:Body|Param\([^)]*\))\s+([A-Za-z_$][\w$]*)\s")
_JDK_TYPES = {"MultipartFile", "String"}


def test_every_controller_is_a_batch_upload_endpoint(generated):
    controllers = sorted((generated / "src/main/java/com/gitgalaxy/modernized/controller").glob("*.java"))
    assert {p.stem for p in controllers} == {"AsgpathController", "AsgdotController", "AsgtoController",
                                             "AsgdigitController"}  # fmt: skip
    for p in controllers:
        code = p.read_text(encoding="utf-8")
        assert "MultipartFile" in code and "@RequestBody" not in code, p.name
        assert '"toFile"' not in code, p.name


def test_controllers_name_only_generated_classes(generated):
    classes = {p.stem for p in generated.rglob("*.java")} | _JDK_TYPES
    for p in (generated / "src/main/java/com/gitgalaxy/modernized/controller").glob("*.java"):
        for used in _TYPE_USE.findall(p.read_text(encoding="utf-8")):
            assert used in classes, f"{p.name} names {used}, which the run did not generate"


JDK17 = Path(os.environ.get("JDK_17") or "/usr/lib/jvm/java-17-openjdk-amd64")


@pytest.mark.skipif(not shutil.which("mvn") or not (JDK17 / "bin" / "javac").is_file(), reason="no Maven + JDK 17")
def test_the_generated_project_compiles(generated):
    env = {**os.environ, "JAVA_HOME": str(JDK17)}
    proc = subprocess.run(["mvn", "-q", "-o", "compile"], cwd=generated, env=env, capture_output=True, text=True,
                          timeout=600)  # fmt: skip
    out = proc.stdout + proc.stderr
    if proc.returncode and "COMPILATION ERROR" not in out and re.search(r"offline|resolve|Could not", out):
        pytest.skip("Maven cannot resolve the Spring Boot build offline here")
    assert proc.returncode == 0, out[-4000:]
