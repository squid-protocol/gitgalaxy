import sys
from unittest.mock import patch

import pytest

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
    assert "[SUCCESS] Clean scan. No national IDs, bank accounts, credit cards, or AWS keys detected." in captured.out


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


# ==============================================================================
# TEST 8: Region packs -- national identifiers beyond the US SSN (#3832)
# ==============================================================================
# Every value below is a published specimen or checksum-built test number, not
# a real person's identifier.
_AADHAAR = "234123412346"  # Verhoeff-valid


@pytest.mark.parametrize(
    "line, expected",
    [
        (b"paid to DE89 3704 0044 0532 0130 00", ["IBAN"]),
        (b"paid to GB82WEST12345698765432", ["IBAN"]),
        (b"paid to GB82WEST12345698765433", []),  # mod-97 fails
        (b"nino AB123456C", ["NINO"]),
        (b"nino AB 12 34 56 C", ["NINO"]),
        (b"nino QQ123456C", []),  # Q is never a NINO prefix letter
        (("uid " + _AADHAAR).encode(), ["AADHAAR"]),
        (b"uid 2341 2341 2346", ["AADHAAR"]),
        (b"uid 2341 2341-2346", []),  # mixed separators
        (b"uid 234123412345", []),  # Verhoeff fails
        (b"cpf 529.982.247-25", ["CPF"]),
        (b"cpf 52998224725", ["CPF"]),
        (b"cpf 529.982.247-26", []),  # check digit fails
        (b"cpf 111.111.111-11", []),  # repeated digits are never issued
        (b"BSN: 111222333", ["BSN"]),
        (b"order 111222333", []),  # 11-proof passes, but nothing names it a BSN
        (b"BSN: 111222334", []),  # 11-proof fails
        (b"card 4111111111111111", ["VISA"]),
    ],
)
def test_region_pack_detection(line, expected):
    assert pii_module.find_pii(line) == expected


def test_region_pack_masking_keeps_only_the_tail():
    masked = pii_module.mask_pii(
        "IBAN DE89 3704 0044 0532 0130 00 BSN: 111222333 order 123456789 "
        f"cpf 529.982.247-25 nino AB123456C uid {_AADHAAR}"
    )
    assert masked == (
        "IBAN IBAN-MASKED-3000 BSN: BSN-MASKED-2333 order 123456789 "
        "cpf CPF-MASKED-4725 nino NINO-MASKED-C uid AADHAAR-MASKED-2346"
    )


def test_region_packs_are_selectable(tmp_path):
    log = tmp_path / "eu.log"
    log.write_text(
        "2026-05-11T10:00 cpf 529.982.247-25\n2026-05-11T11:00 iban GB82WEST12345698765432\n",
        encoding="utf-8",
    )
    with patch.object(sys, "argv", ["pii_leak_hunter.py", str(log), "--regions", "iban"]):
        pii_module.main()
    content = (tmp_path / "eu_pii_leak_evidence.log").read_text(encoding="utf-8")
    assert "[IBAN] " in content and "IBAN-MASKED-5432" in content
    # The br pack is off: its line is not reported at all.
    assert "cpf" not in content


def test_unknown_region_pack_is_rejected(tmp_path, capsys):
    log = tmp_path / "x.log"
    log.write_text("data", encoding="utf-8")
    with patch.object(sys, "argv", ["pii_leak_hunter.py", str(log), "--regions", "atlantis"]):
        with pytest.raises(SystemExit) as exc_info:
            pii_module.main()
    assert exc_info.value.code == 1
    assert "unknown PII region pack(s): atlantis" in capsys.readouterr().out


def test_region_pack_patterns_are_linear_on_pathological_input():
    import time

    lines = [b"1" * 50_000, b"AB 12 " * 10_000, b"DE89 " + b"ABCD " * 10_000, b"2341 " * 10_000]
    start = time.perf_counter()
    for line in lines:
        pii_module.find_pii(line)
    assert time.perf_counter() - start < 2.0
