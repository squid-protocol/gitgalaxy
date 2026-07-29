import sys
from unittest.mock import patch

# IMPORTANT: Adjust this path to match exactly where your file is located
import gitgalaxy.tools.cobol_to_cobol.cobol_jcl_forge as forge_module


# ==============================================================================
# TEST 1: The Flattener and Intent Extractor
# ==============================================================================
def test_cobol_intent_analysis(tmp_path):
    """
    Proves that the engine correctly ignores column-7 comments, extracts
    the PROGRAM-ID, cleans DD names, and identifies transactional DB blocks.
    """
    mock_cobol = tmp_path / "MOCKPGM.cbl"

    # Notice the strict 6-space margin and the column-7 asterisk
    cobol_code = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. 'GLB001'.\n"
        "      *SELECT FAKE-FILE ASSIGN TO FAKEDD. (Should be ignored!)\n"
        "       INPUT-OUTPUT SECTION.\n"
        "       FILE-CONTROL.\n"
        "           SELECT IN-FILE ASSIGN TO UT-S-INPUTDD.\n"
        "           SELECT OUT-FILE ASSIGN TO OUTPUTDD.\n"
        "       PROCEDURE DIVISION.\n"
        "           EXEC CICS\n"
        "              RECEIVE MAP('MAP1')\n"
        "           END-EXEC.\n"
        "           EXEC SQL\n"
        "              SELECT * FROM TABLE\n"
        "           END-EXEC.\n"
    )
    mock_cobol.write_text(cobol_code, encoding="utf-8")

    intent = forge_module.analyze_cobol_intent(mock_cobol)

    # 1. Verify basic extraction
    assert intent["program_id"] == "GLB001", "Failed to extract PROGRAM-ID!"

    # 2. Verify file extraction and prefix stripping (UT-S-)
    files = {f["internal"]: f["dd_name"] for f in intent["files_requested"]}
    assert "IN-FILE" in files and files["IN-FILE"] == "INPUTDD"
    assert "OUT-FILE" in files and files["OUT-FILE"] == "OUTPUTDD"
    assert "FAKE-FILE" not in files, "Failed to ignore column-7 comment!"

    # 3. Verify transactional/database flags
    assert intent["is_cics"] is True
    assert intent["cics_calls"] == 1
    assert intent["is_db2"] is True
    assert intent["sql_calls"] == 1


# ==============================================================================
# TEST 2: The Zero-Trust JCL Generator
# ==============================================================================
def test_zero_trust_jcl_generation():
    """
    Proves that the parsed intent dictionary correctly maps into a formatted,
    runnable Mainframe JCL script with the requested architecture boundaries.
    """
    mock_intent = {
        "program_id": "TESTPGM",
        "files_requested": [{"internal": "INFILE", "dd_name": "INPUT01"}],
        "is_cics": True,
        "is_db2": False,
    }

    # Force a mock lineage to test the NEW disposition creation
    mock_lineage = {"outputs": {"INPUT01"}, "inputs": set()}

    jcl_output = forge_module.generate_zero_trust_jcl(
        intent=mock_intent,
        job_name="MOCKJOB",
        account_code="9999",
        lineage=mock_lineage,
    )

    # 1. Job Card and Base Environment
    assert "//MOCKJOB JOB (9999)" in jcl_output
    assert "//STEP01   EXEC PGM=TESTPGM" in jcl_output

    # 2. Architecture Flags
    assert "ARCHITECTURE REQUIRES: CICS" in jcl_output
    assert "DB2" not in jcl_output

    # 3. File Dispositions
    assert "//INPUT01  DD DSN=HERC01.DATA.INPUT01" in jcl_output
    assert "DISP=(NEW,CATLG,DELETE)" in jcl_output  # Because it was passed in the 'outputs' lineage


# ==============================================================================
# TEST 3: The Hygienic E2E CLI Routing
# ==============================================================================
def test_hygienic_cli_defaults(tmp_path):
    """
    Proves the CLI wrapper correctly discovers files, isolates the output into a
    timestamped hygienic directory, and successfully writes the JCL payload.
    """
    # 1. Setup the physical legacy source directory
    src_dir = tmp_path / "legacy_src"
    src_dir.mkdir()

    (src_dir / "PROG1.cbl").write_text("       PROGRAM-ID. P1.\n", encoding="utf-8")
    (src_dir / "PROG2.cob").write_text("       PROGRAM-ID. P2.\n", encoding="utf-8")

    # 2. Execute the Forge
    test_args = ["cobol_jcl_forge.py", str(src_dir)]
    with patch.object(sys, "argv", test_args):
        # We don't trap SystemExit because a successful run exits normally
        forge_module.main()

    # 3. Verify the Hygienic Output Directory
    # Look for a directory matching 'legacy_src_generated_YYYYMMDD_HHMMSS'
    directories = [d for d in tmp_path.iterdir() if d.is_dir() and "legacy_src_generated_" in d.name]
    assert len(directories) == 1, "The engine failed to create the isolated output directory!"

    hygienic_dir = directories[0]

    # 4. Verify the physical forged files
    p1_jcl = hygienic_dir / "P1.jcl"
    p2_jcl = hygienic_dir / "P2.jcl"

    assert p1_jcl.exists(), "P1 JCL was not written to the hygienic directory!"
    assert p2_jcl.exists(), "P2 JCL was not written to the hygienic directory!"
    assert "EXEC PGM=P1" in p1_jcl.read_text(encoding="utf-8")
