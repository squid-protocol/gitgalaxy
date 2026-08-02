import pytest
import sys
from unittest.mock import patch

# IMPORTANT: Adjust this path to match exactly where your file is located
import gitgalaxy.tools.cobol_to_cobol.cobol_system_limits_reporter as limit_reporter


# ==============================================================================
# TEST 1: The Dragon Traps & Comment Shield
# ==============================================================================
def test_system_limits_regex_and_comments(tmp_path):
    """
    Proves that the regex traps correctly identify all 3 anomalies,
    but strictly ignore them if they are commented out in column 7.
    """
    # 1. Create a physical mock COBOL file
    cobol_file = tmp_path / "DRAGONS.cbl"

    # Notice the 6 spaces before the 7th column for standard COBOL formatting
    cobol_code = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DRAGONS.\n"
        "      * THIS IS A COMMENT: ALTER PARA-A TO PROCEED TO PARA-B\n"  # Should be ignored
        "       PROCEDURE DIVISION.\n"
        "       PARA-1.\n"
        "           ALTER PARA-X TO PROCEED TO PARA-Y.\n"  # Hit 1 (Line 6)
        "           DISPLAY 'HELLO'.\n"
        "           EXEC CICS HANDLE CONDITION ERROR(ERR-RTN).\n"  # Hit 2 (Line 8)
        "           COPY 'MYLIB' REPLACING ==A== BY ==B==.\n"  # Hit 3 (Line 9)
    )
    cobol_file.write_text(cobol_code, encoding="utf-8")

    # 2. Execute the Scanner directly
    anomalies = limit_reporter.scan_system_limits(cobol_file)

    # 3. Assertions
    assert len(anomalies) == 3, "Failed to catch all 3 active anomalies or failed to ignore the comment!"

    # Join into a single string to easily assert the formatted output
    output_str = "\n".join(anomalies)

    assert "Line 0006] CRITICAL LIMIT" in output_str and "dynamically rewritten" in output_str
    assert "Line 0008] CRITICAL LIMIT" in output_str and "Asynchronous error routing" in output_str
    assert "Line 0009] HIGH LIMIT" in output_str and "Macro substitution" in output_str


# ==============================================================================
# TEST 2: The Clean Baseline
# ==============================================================================
def test_system_limits_clean_baseline(tmp_path):
    """
    Proves that a mathematically deterministic, modern COBOL file
    passes the Honesty Protocol without triggering false positives.
    """
    clean_file = tmp_path / "CLEAN.cbl"
    clean_code = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. CLEAN.\n"
        "       PROCEDURE DIVISION.\n"
        "           PERFORM PARA-1 THRU PARA-2.\n"
        "           GOBACK.\n"
    )
    clean_file.write_text(clean_code, encoding="utf-8")

    anomalies = limit_reporter.scan_system_limits(clean_file)
    assert len(anomalies) == 0, "False positive triggered on clean COBOL code!"


# ==============================================================================
# TEST 3: E2E Directory Traversal
# ==============================================================================
def test_system_limits_cli_directory_traversal(tmp_path, capsys):
    """
    Proves that the CLI wrapper correctly recurses through a directory,
    targets ONLY .cbl and .cob files, and aggregates the warnings.
    """
    repo_dir = tmp_path / "legacy_repo"
    repo_dir.mkdir()

    # File 1: Infected .cbl file
    (repo_dir / "PGM1.cbl").write_text("           ALTER P1 TO P2.\n", encoding="utf-8")

    # File 2: Infected .cob file
    (repo_dir / "PGM2.cob").write_text("           COPY A REPLACING B.\n", encoding="utf-8")

    # File 3: Irrelevant file (should be ignored)
    (repo_dir / "readme.txt").write_text("ALTER P1 TO P2.\n", encoding="utf-8")

    # Execute the CLI tool
    test_args = ["cobol_system_limits_reporter.py", str(repo_dir)]
    with patch.object(sys, "argv", test_args):
        # We catch SystemExit in case something fails, but a normal run exits gracefully
        try:
            limit_reporter.main()
        except SystemExit as e:
            if e.code != 0:
                pytest.fail(f"CLI exited with unexpected error code: {e.code}")

    # Capture the print statements sent to stdout
    captured = capsys.readouterr()

    # Verify the results
    assert "executing architectural integrity scan on 2 files" in captured.out, (
        "Failed to properly filter .cbl and .cob files!"
    )
    assert "PGM1.cbl : Line 0001" in captured.out
    assert "PGM2.cob : Line 0001" in captured.out
    assert "WARNING: Found 2 structural anomalies" in captured.out
