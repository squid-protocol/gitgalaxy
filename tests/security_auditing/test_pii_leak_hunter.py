import pytest
import sys
from unittest.mock import patch

# IMPORTANT: Adjust this path to match exactly where your file is located
import gitgalaxy.tools.terabyte_log_scanning.pii_leak_hunter as pii_module


# ==============================================================================
# TEST 1: The Masking Engine (Data Redaction Verification)
# ==============================================================================
def test_pii_masking_engine():
    """
    Mathematically verifies that the regex engine correctly intercepts and
    redacts sensitive PII data while preserving the safe formatting.
    """
    # 1. VISA Test (Redact 12 digits, keep last 4)
    assert pii_module.mask_pii("Card: 4123456789012345") == "Card: VISA-MASKED-2345"

    # 2. MASTERCARD Test (Redact 12 digits, keep last 4)
    assert pii_module.mask_pii("Card: 5123456789012345") == "Card: MC-MASKED-2345"

    # 3. SSN Test (Redact first 5 digits, keep last 4)
    assert pii_module.mask_pii("ID: 123-45-6789") == "ID: XXX-XX-6789"

    # 4. AWS KEY Test (Keep prefix and last 4, redact the 12-char middle)
    assert pii_module.mask_pii("Key: AKIAIOSFODNN7EXAMPLE") == "Key: AKIA-XXXX-MPLE"

    # 5. The Combo Test (Multiple leaks in a single log line)
    combo_log = "User AKIAIOSFODNN7EXAMPLE charged 4123456789012345"
    assert pii_module.mask_pii(combo_log) == "User AKIA-XXXX-MPLE charged VISA-MASKED-2345"


# ==============================================================================
# TEST 2: The E2E Stream Filter (File I/O and Isolation)
# ==============================================================================
def test_pii_leak_hunter_e2e(tmp_path):
    """
    End-to-End test simulating a live log stream.
    Proves that clean lines are dropped, PII lines are safely written,
    and no raw sensitive data ever touches the output evidence log.
    """
    # 1. Setup the physical mock log file
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    target_log = log_dir / "production_dump.log"

    # Inject a mix of clean lines and highly sensitive data
    target_log.write_text(
        "2026-05-11T09:00 [INFO] System boot sequence normal\n"
        "2026-05-11T10:00 [DEBUG] Transaction 4111111111111111 processed\n"
        "2026-05-11T11:00 [ERROR] Failed AWS auth with AKIAIOSFODNN7EXAMPLE\n"
        "2026-05-11T12:00 [WARN] Input SSN 999-99-9999 failed validation\n",
        encoding="utf-8",
    )

    # 2. Execute the CLI tool
    test_args = ["pii_leak_hunter.py", str(target_log)]
    with patch.object(sys, "argv", test_args):
        pii_module.main()

    # 3. Verify the Evidence Log
    evidence_file = log_dir / "production_dump_pii_leak_evidence.log"
    assert evidence_file.exists(), "The PII Leak Hunter failed to generate the safe evidence log!"

    content = evidence_file.read_text(encoding="utf-8")

    # A) Ensure the clean lines were ignored (Saving disk space/CPU)
    assert "System boot sequence normal" not in content

    # B) Ensure the redacted data made it to the file
    assert "VISA-MASKED-1111" in content
    assert "AKIA-XXXX-MPLE" in content
    assert "XXX-XX-9999" in content

    # C) ZERO-TRUST GUARANTEE: Ensure the raw PII was completely redacted
    assert "4111111111111111" not in content, "CRITICAL LEAK: Raw VISA card written to disk! Redaction failed."
    assert "AKIAIOSFODNN7EXAMPLE" not in content, "CRITICAL LEAK: Raw AWS Key written to disk! Redaction failed."
    assert "999-99-9999" not in content, "CRITICAL LEAK: Raw SSN written to disk! Redaction failed."


# ==============================================================================
# TEST 3: CLI Argument Parsing - Missing Target
# ==============================================================================
def test_missing_target_argument(capsys):
    """Ensures the CLI gracefully exits when no target is provided."""
    with patch.object(sys, "argv", ["pii_leak_hunter.py"]):
        with pytest.raises(SystemExit) as exc_info:
            pii_module.main()
        # argparse default exit code for missing arguments is 2
        assert exc_info.value.code == 2

    captured = capsys.readouterr()
    assert "the following arguments are required: target" in captured.err


# ==============================================================================
# TEST 4: Invalid Target Path Handling
# ==============================================================================
def test_invalid_target_path(tmp_path, capsys):
    """Ensures the tool exits cleanly when provided a non-existent file."""
    invalid_path = tmp_path / "does_not_exist.log"
    test_args = ["pii_leak_hunter.py", str(invalid_path)]

    with patch.object(sys, "argv", test_args):
        with pytest.raises(SystemExit) as exc_info:
            pii_module.main()
        assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "Target file does not exist or is not a file" in captured.out


# ==============================================================================
# TEST 5: Custom Output Directory Override
# ==============================================================================
def test_custom_output_directory(tmp_path):
    """Verifies that the --out argument redirects the evidence log successfully."""
    log_dir = tmp_path / "source_logs"
    log_dir.mkdir()
    target_log = log_dir / "app.log"
    target_log.write_text("2026-05-11T10:00 [DEBUG] Transaction 4111111111111111 processed\n", encoding="utf-8")

    custom_out = tmp_path / "secure_archive"
    test_args = ["pii_leak_hunter.py", str(target_log), "--out", str(custom_out)]

    with patch.object(sys, "argv", test_args):
        pii_module.main()

    assert custom_out.exists(), "Custom output directory was not created."
    evidence_file = custom_out / "app_pii_leak_evidence.log"
    assert evidence_file.exists(), "Evidence log not found in custom output directory."
    assert "VISA-MASKED-1111" in evidence_file.read_text(encoding="utf-8")


# ==============================================================================
# TEST 6: Clean Log Processing (Zero Detection)
# ==============================================================================
def test_clean_log_processing(tmp_path, capsys):
    """Proves the tool processes safe logs without generating false evidence data."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    target_log = log_dir / "clean.log"
    target_log.write_text("2026-05-11T09:00 [INFO] System boot sequence normal\n", encoding="utf-8")

    test_args = ["pii_leak_hunter.py", str(target_log)]
    with patch.object(sys, "argv", test_args):
        pii_module.main()

    evidence_file = log_dir / "clean_pii_leak_evidence.log"
    assert evidence_file.exists()
    assert evidence_file.read_text(encoding="utf-8") == "", "Clean evidence log should be completely empty."

    captured = capsys.readouterr()
    assert "[SUCCESS] Clean scan. No Social Security, Credit Card, or AWS Keys detected." in captured.out


# ==============================================================================
# TEST 7: Output Directory Permission Failure
# ==============================================================================
def test_output_directory_permission_error(tmp_path, capsys):
    """Simulates a scenario where the application lacks rights to create the output folder."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    target_log = log_dir / "app.log"
    target_log.write_text("data", encoding="utf-8")

    test_args = ["pii_leak_hunter.py", str(target_log)]

    with patch("pathlib.Path.mkdir", side_effect=PermissionError("Access Denied")):
        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit) as exc_info:
                pii_module.main()
            assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "[ERROR] Permission denied to create output directory" in captured.out
