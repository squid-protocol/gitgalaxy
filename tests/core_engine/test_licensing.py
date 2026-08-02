import os
from unittest.mock import mock_open, patch

from gitgalaxy.licensing import _validate_offline_key, enforce_licensing_guard


# ==============================================================================
# TEST 1: THE PYTEST BYPASS (REMOVED)
# ==============================================================================
def test_licensing_pytest_bypass(monkeypatch, capsys):
    """Proves the Pytest bypass was successfully removed and strict compliance is enforced."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "True")
    monkeypatch.setenv("GITGALAXY_LICENSE_KEY", "COMMUNITY_FREE_TIER")

    with patch("gitgalaxy.licensing.time.sleep") as mock_sleep:
        enforce_licensing_guard()

        # It should NO LONGER exit silently. It must print the compliance tripwire.
        mock_sleep.assert_not_called()
        captured = capsys.readouterr()
        assert "LEGAL AUDIT TRIPWIRE" in captured.err


# ==============================================================================
# TEST 2: THE ZERO-DEPENDENCY .ENV LOADER
# ==============================================================================
@patch("os.path.exists")
def test_licensing_env_loader(mock_exists, monkeypatch):
    """Proves the custom .env loader parses variables without overriding existing ones."""
    # Strip the bypass so the engine actually runs the logic
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    # Pre-existing environment variable (should NOT be overwritten)
    monkeypatch.setattr(os, "environ", {"EXISTING_VAR": "keep_me"})

    mock_exists.return_value = True
    mock_env_content = (
        "# This is a comment\n"
        "\n"
        "GITGALAXY_LICENSE_KEY=COMMUNITY_FREE_TIER\n"  # gitleaks:allow
        "EXISTING_VAR=overwrite_me\n"
        'QUOTED_VAR="clean_value"\n'
    )

    # We must patch print/sleep to prevent the Community Tier warning from polluting stdout
    with patch("builtins.open", mock_open(read_data=mock_env_content)):
        with patch("builtins.print"), patch("gitgalaxy.licensing.time.sleep"):
            enforce_licensing_guard()

    assert os.environ.get("GITGALAXY_LICENSE_KEY") == "COMMUNITY_FREE_TIER"
    assert os.environ.get("EXISTING_VAR") == "keep_me"  # Protected!
    assert os.environ.get("QUOTED_VAR") == "clean_value"  # Quotes stripped


@patch("os.path.exists")
def test_licensing_env_loader_exception(mock_exists, monkeypatch):
    """Proves OS permission errors on the .env file are swallowed gracefully."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(os, "environ", {})
    mock_exists.return_value = True

    # Force a permission error when opening the .env file
    with (
        patch("builtins.open", side_effect=PermissionError("Locked")), patch("builtins.print"),
        patch("gitgalaxy.licensing.time.sleep") as mock_sleep,
    ):
        # It should fail to read the file, drop to the MISSING trap, and sleep for 5 seconds
        enforce_licensing_guard()
        mock_sleep.assert_called_once_with(5.0)


# ==============================================================================
# TEST 3: OFFLINE RSA MATH VALIDATION (_validate_offline_key)
# ==============================================================================
def test_validate_key_missing_or_malformed():
    """Proves empty or malformed keys are flagged as MALFORMED, not FORGED -- a
    fat-fingered copy-paste is not the same claim as cryptographic tampering."""
    # 1. Missing Key
    assert _validate_offline_key("") == "MISSING"
    assert _validate_offline_key(None) == "MISSING"

    # 2. Malformed Format
    assert _validate_offline_key("TOO-SHORT") == "MALFORMED"
    assert _validate_offline_key("WRONG-TIER-CUSTOMER-DATE-SIG") == "MALFORMED"  # Missing GG prefix

    # 3. Invalid Hex Signature (Throws ValueError internally)
    assert _validate_offline_key("GG-TIER-CUST-20991231-NOTHEX") == "MALFORMED"


@patch("gitgalaxy.licensing.pow")
def test_validate_key_cryptographic_authenticity(mock_pow):
    """Proves the engine authenticates exact hash matches and correctly evaluates dates."""

    # To test the math without your private key, we mock the pow() function
    # to return the exact SHA-256 integer hash of our fake payload.
    import hashlib

    payload = b"ENTERPRISE-ACME-20991231"
    expected_hash_int = int.from_bytes(hashlib.sha256(payload).digest(), byteorder="big")

    # 1. VALID KEY (Future Date)
    mock_pow.return_value = expected_hash_int
    valid_key = "GG-ENTERPRISE-ACME-20991231-1A2B"  # gitleaks:allow
    assert _validate_offline_key(valid_key) == "VALID"

    # 2. EXPIRED KEY (Authentic math, but date is in the past)
    payload_exp = b"ENTERPRISE-ACME-20000101"
    expected_hash_int_exp = int.from_bytes(hashlib.sha256(payload_exp).digest(), byteorder="big")
    mock_pow.return_value = expected_hash_int_exp

    expired_key = "GG-ENTERPRISE-ACME-20000101-1A2B"  # gitleaks:allow
    assert _validate_offline_key(expired_key) == "EXPIRED"

    # 3. FORGED KEY (Math mismatch -- the one branch that's actually tampering)
    mock_pow.return_value = 99999999999  # Incorrect decryption
    assert _validate_offline_key(valid_key) == "FORGED"

    # 4. CORRUPTED DATE FORMAT (signature checks out, but the payload itself
    # is broken -- still not tampering evidence, so it's MALFORMED not FORGED)
    payload_bad_date = b"ENTERPRISE-ACME-BAD_DATE"
    expected_hash_bad = int.from_bytes(hashlib.sha256(payload_bad_date).digest(), byteorder="big")
    mock_pow.return_value = expected_hash_bad

    corrupted_date_key = "GG-ENTERPRISE-ACME-BAD_DATE-1A2B"  # gitleaks:allow
    assert _validate_offline_key(corrupted_date_key) == "MALFORMED"


# ==============================================================================
# TEST 4: THE 3-TIER FRICTION ROUTING (enforce_licensing_guard)
# ==============================================================================
def test_routing_community_tier(monkeypatch, capsys):
    """Proves the Community tier logs the audit tripwire with NO sleep penalty."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(os, "environ", {"GITGALAXY_LICENSE_KEY": "COMMUNITY_FREE_TIER"})

    with patch("gitgalaxy.licensing.time.sleep") as mock_sleep:
        enforce_licensing_guard()

        mock_sleep.assert_not_called()
        captured = capsys.readouterr()
        assert "LEGAL AUDIT TRIPWIRE" in captured.err


@patch("gitgalaxy.licensing._validate_offline_key")
def test_routing_valid_enterprise_tier(mock_validate, monkeypatch, capsys):
    """Proves a valid enterprise key executes silently with NO sleep penalty."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(os, "environ", {"GITGALAXY_LICENSE_KEY": "GG-VALID-KEY"})
    mock_validate.return_value = "VALID"

    with patch("gitgalaxy.licensing.time.sleep") as mock_sleep:
        enforce_licensing_guard()

        mock_sleep.assert_not_called()
        captured = capsys.readouterr()
        assert captured.err == ""


@patch("gitgalaxy.licensing._validate_offline_key")
def test_routing_forgery_hammer(mock_validate, monkeypatch, capsys):
    """Proves forged keys trigger the maximum 10-second penalty, and that the
    message no longer makes the false claim that an incident was "flagged"
    somewhere -- this check is entirely local/offline and nothing persists."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(os, "environ", {"GITGALAXY_LICENSE_KEY": "GG-FORGED-KEY"})
    mock_validate.return_value = "FORGED"

    with patch("gitgalaxy.licensing.time.sleep") as mock_sleep:
        enforce_licensing_guard()

        mock_sleep.assert_called_once_with(10.0)
        captured = capsys.readouterr()
        assert "LICENSE FORGERY DETECTED" in captured.err
        assert "flagged" not in captured.err.lower()


@patch("gitgalaxy.licensing._validate_offline_key")
def test_routing_malformed_key(mock_validate, monkeypatch, capsys):
    """Proves a malformed key (e.g. a copy-paste error) gets the lighter,
    non-accusatory 5-second friction trap instead of the forgery hammer --
    a fat-fingered paste isn't evidence of tampering."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(os, "environ", {"GITGALAXY_LICENSE_KEY": "GG-TRUNCATED"})
    mock_validate.return_value = "MALFORMED"

    with patch("gitgalaxy.licensing.time.sleep") as mock_sleep:
        enforce_licensing_guard()

        mock_sleep.assert_called_once_with(5.0)
        captured = capsys.readouterr()
        assert "LICENSE KEY MALFORMED" in captured.err
        assert "FORGERY" not in captured.err
        assert "tampering" not in captured.err.lower()
