import pytest
import yaml
from unittest.mock import patch

import gitgalaxy.tools.supply_chain_security.binary_anomaly_detector as xray_module
from gitgalaxy.standards.config_resolver import ResolvedConfig, resolve_config


def _make_config(**overrides):
    """
    Builds a ResolvedConfig for direct run_xray_audit() calls (#335): starts
    from real gitgalaxy_config.py defaults and overlays just the keys a
    given test cares about, replacing the old
    monkeypatch.setattr(xray_module, "X", ...) pattern now that the
    detector reads config off a passed-in object instead of module globals.
    """
    values = resolve_config().to_dict()
    values.update(overrides)
    return ResolvedConfig(_values=values)


def _write_config_yaml(tmp_path, **overrides):
    """
    Writes a .galaxyscope.yaml for main()-based tests that need a
    non-default gitgalaxy_config.py key. Exercises the real --config path
    end-to-end instead of monkeypatching module-level constants that no
    longer exist after the direct-import migration.
    """
    yaml_path = tmp_path / ".galaxyscope.yaml"
    yaml_path.write_text(yaml.dump({"galaxyscope": overrides}))
    return str(yaml_path)


# ==============================================================================
# TEST 1: Path Filtering Logic (Denylist vs Allowlist vs Extensions)
# ==============================================================================
@patch("gitgalaxy.tools.supply_chain_security.binary_anomaly_detector.SecurityLens")
@patch("gitgalaxy.tools.supply_chain_security.binary_anomaly_detector.ApertureFilter")
def test_xray_routing_matrix(mock_aperture_class, mock_security_class, tmp_path):
    config = _make_config(
        DENYLIST_PATTERNS=["*.key", "*.pem", "id_rsa*"],
        XRAY_BYPASS_EXTENSIONS=[".gz", ".zip"],
        ALLOWLIST_PATHS=["approved_keys/"],
    )

    mock_aperture = mock_aperture_class.return_value
    mock_aperture._check_ignore_rules.return_value = True

    mock_security = mock_security_class.return_value
    mock_security.scan_content.return_value = {"counts": {"entropy": 6.5, "bitwise_ops": 0}}
    mock_security.scan_binary.return_value = {}

    repo_dir = tmp_path / "routing_repo"
    repo_dir.mkdir()

    # File A (Anomaly)
    (repo_dir / "private.key").write_text("FAKE_PRIVATE_KEY", encoding="utf-8")

    # File B (Bypass Allowlist)
    approved_dir = repo_dir / "approved_keys"
    approved_dir.mkdir()
    (approved_dir / "service.pem").write_text("FAKE_CERT", encoding="utf-8")

    # File C (Bypass Extension)
    (repo_dir / "compressed.zip").write_text("FAKE_ZIP_DATA", encoding="utf-8")

    result = xray_module.run_xray_audit(repo_dir, config=config)
    assert result["anomalies_found"] == 1, "Path filtering logic failed! Verify Denylist and Allowlist evaluation."


# ==============================================================================
# TEST 2: Deep Content Inspection (Magic Bytes & High Entropy)
# ==============================================================================
@patch("gitgalaxy.tools.supply_chain_security.binary_anomaly_detector.SecurityLens")
@patch("gitgalaxy.tools.supply_chain_security.binary_anomaly_detector.ApertureFilter")
def test_xray_deep_scan_threats(mock_aperture_class, mock_security_class, tmp_path):
    mock_aperture = mock_aperture_class.return_value
    mock_aperture._check_ignore_rules.return_value = True

    repo_dir = tmp_path / "deep_scan_repo"
    repo_dir.mkdir()

    clean_file = repo_dir / "clean.txt"
    clean_file.write_text("Hello world", encoding="utf-8")

    spoofed_file = repo_dir / "hidden_exe.jpg"
    spoofed_file.write_text("MZ\x90\x00...", encoding="utf-8")

    mock_security = mock_security_class.return_value

    def mock_scan_binary(head_bytes, ext):
        if ext == ".jpg":
            return {"threat_snippet": "Magic Byte Mismatch: Expected JPEG, got PE32 Executable"}
        return {}

    def mock_scan_content(content):
        if "MZ" in content:
            return {"counts": {"entropy": 6.8, "bitwise_ops": 2}}
        return {"counts": {"entropy": 1.2, "bitwise_ops": 0}}

    mock_security.scan_binary.side_effect = mock_scan_binary
    mock_security.scan_content.side_effect = mock_scan_content

    result = xray_module.run_xray_audit(repo_dir)
    assert result["anomalies_found"] == 1, "Failed to flag magic byte mismatch or high entropy structural anomaly."


# ==============================================================================
# TEST 3: Expected Execution Header Exception
# ==============================================================================
@patch("gitgalaxy.tools.supply_chain_security.binary_anomaly_detector.SecurityLens")
@patch("gitgalaxy.tools.supply_chain_security.binary_anomaly_detector.ApertureFilter")
def test_xray_shebang_shield(mock_aperture_class, mock_security_class, tmp_path):
    mock_aperture = mock_aperture_class.return_value
    mock_aperture._check_ignore_rules.return_value = True

    repo_dir = tmp_path / "shebang_repo"
    repo_dir.mkdir()

    sh_file = repo_dir / "deploy.sh"
    sh_file.write_text("#!/bin/bash\necho 'Deploying...'", encoding="utf-8")

    mock_security = mock_security_class.return_value
    mock_security.scan_content.return_value = {"counts": {"entropy": 0, "bitwise_ops": 0}}
    mock_security.scan_binary.return_value = {"threat_snippet": "Suspicious execution header: #!/bin/bash"}

    result = xray_module.run_xray_audit(repo_dir)
    assert result["anomalies_found"] == 0, "Expected execution header bypass failed."


# ==============================================================================
# TEST 4: I/O Exception Handling (Programmatic Entry)
# ==============================================================================
@patch("gitgalaxy.tools.supply_chain_security.binary_anomaly_detector.SecurityLens")
@patch("gitgalaxy.tools.supply_chain_security.binary_anomaly_detector.ApertureFilter")
def test_xray_run_audit_exception(mock_aperture_class, mock_security_class, tmp_path):
    mock_aperture = mock_aperture_class.return_value
    mock_aperture._check_ignore_rules.return_value = True

    repo_dir = tmp_path / "broken_audit"
    repo_dir.mkdir()
    (repo_dir / "locked.dat").write_text("data", encoding="utf-8")

    with patch("builtins.open", side_effect=PermissionError("Locked")):
        result = xray_module.run_xray_audit(repo_dir)

    assert result["anomalies_found"] == 0, "Failed to gracefully catch IO exception in run_xray_audit!"


# ==============================================================================
# TEST 5: CLI Main - Missing Target Validation
# ==============================================================================
def test_main_missing_target(capsys):
    """Proves the CLI catches invalid directories and exits safely."""
    with patch("sys.argv", ["xray", "non_existent_folder_path_12345"]):
        with pytest.raises(SystemExit) as exc_info:
            xray_module.main()

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Error: Target" in captured.out


# ==============================================================================
# TEST 6: CLI Main - Clean Run & Allowlist Bypasses
# ==============================================================================
@patch("gitgalaxy.tools.supply_chain_security.binary_anomaly_detector.SecurityLens")
@patch("gitgalaxy.tools.supply_chain_security.binary_anomaly_detector.ApertureFilter")
def test_main_clean_run(mock_aperture_class, mock_security_class, tmp_path, capsys):
    """Proves a clean repository successfully logs completion without raising SystemExit."""
    config_path = _write_config_yaml(tmp_path, ALLOWLIST_PATHS=["approved/"])
    mock_aperture = mock_aperture_class.return_value
    mock_aperture._check_ignore_rules.return_value = True

    mock_security = mock_security_class.return_value
    mock_security.scan_binary.return_value = {}

    # We must trigger an anomaly in the bypassed file so the engine logs it as 'allowed'
    def mock_scan_content(content):
        if "bypassed" in content:
            return {"counts": {"entropy": 6.0, "bitwise_ops": 0}}
        return {"counts": {"entropy": 0, "bitwise_ops": 0}}

    mock_security.scan_content.side_effect = mock_scan_content

    repo_dir = tmp_path / "clean_repo_cli"
    repo_dir.mkdir()

    (repo_dir / "safe.txt").write_text("safe", encoding="utf-8")

    approved_dir = repo_dir / "approved"
    approved_dir.mkdir()
    (approved_dir / "bypassed.key").write_text("bypassed", encoding="utf-8")

    with patch("sys.argv", ["xray", str(repo_dir), "--config", config_path]):
        xray_module.main()

    captured = capsys.readouterr()
    assert "[SUCCESS] No obfuscated payloads or binary anomalies detected." in captured.out
    assert "known mock/safe files were bypassed via configuration." in captured.out


# ==============================================================================
# TEST 7: CLI Main - Anomaly Detected (System Exit 1)
# ==============================================================================
@patch("gitgalaxy.tools.supply_chain_security.binary_anomaly_detector.SecurityLens")
@patch("gitgalaxy.tools.supply_chain_security.binary_anomaly_detector.ApertureFilter")
def test_main_anomaly_detected(mock_aperture_class, mock_security_class, tmp_path, capsys):
    """Proves the CLI detects active anomalies, blocks the commit, and logs the blocking action."""
    config_path = _write_config_yaml(tmp_path, DENYLIST_PATTERNS=["*.forbidden"])
    mock_aperture = mock_aperture_class.return_value
    mock_aperture._check_ignore_rules.return_value = True

    repo_dir = tmp_path / "threat_repo_cli"
    repo_dir.mkdir()

    (repo_dir / "bad.forbidden").write_text("bad", encoding="utf-8")
    (repo_dir / "encrypted.dat").write_text("HIGH ENTROPY", encoding="utf-8")

    mock_security = mock_security_class.return_value
    mock_security.scan_binary.return_value = {}
    mock_security.scan_content.side_effect = lambda content: (
        {"counts": {"entropy": 5.0, "bitwise_ops": 1}} if "HIGH ENTROPY" in content else {"counts": {}}
    )

    with patch("sys.argv", ["xray", str(repo_dir), "--config", config_path]):
        with pytest.raises(SystemExit) as exc_info:
            xray_module.main()

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "[BLOCKING ACTION]" in captured.out
    assert "[DENYLIST MATCH]" in captured.out
    assert "[ANOMALY DETECTED]" in captured.out


# ==============================================================================
# TEST 8: CLI Main - Exception Catch
# ==============================================================================
@patch("gitgalaxy.tools.supply_chain_security.binary_anomaly_detector.SecurityLens")
@patch("gitgalaxy.tools.supply_chain_security.binary_anomaly_detector.ApertureFilter")
def test_main_file_read_exception(mock_aperture_class, mock_security_class, tmp_path):
    """Triggers the generic 'except Exception: pass' inside the deep scan loop of main()."""
    mock_aperture = mock_aperture_class.return_value
    mock_aperture._check_ignore_rules.return_value = True

    repo_dir = tmp_path / "broken_main"
    repo_dir.mkdir()
    (repo_dir / "unreadable.dat").write_text("data", encoding="utf-8")

    with patch("sys.argv", ["xray", str(repo_dir)]):
        with patch("builtins.open", side_effect=PermissionError("Locked")):
            xray_module.main()


# ==============================================================================
# TEST 9 (removed, #335): the try/except ImportError module-level fallback
# this test covered no longer exists -- binary_anomaly_detector.py now
# reads config from resolve_config(), which always has real defaults
# (gitgalaxy_config.py is a committed file, not an optional install-time
# artifact). See test_yaml_config_flag_actually_changes_standalone_xray_behavior
# below for the replacement "gap is closed" proof.
# ==============================================================================


# ==============================================================================
# TEST 10: False Positive Mitigation (Test Directory Bypass)
# ==============================================================================
@patch("gitgalaxy.tools.supply_chain_security.binary_anomaly_detector.SecurityLens")
@patch("gitgalaxy.tools.supply_chain_security.binary_anomaly_detector.ApertureFilter")
def test_xray_test_folder_bypass(mock_aperture_class, mock_security_class, tmp_path, capsys):
    """Proves that high entropy mock files placed within test directories are safely ignored."""
    mock_aperture = mock_aperture_class.return_value
    mock_aperture._check_ignore_rules.return_value = True

    repo_dir = tmp_path / "test_bypass_repo"
    repo_dir.mkdir()

    # Create a test directory with a mock encrypted payload
    test_dir = repo_dir / "tests"
    test_dir.mkdir()
    mock_payload = test_dir / "mock_encrypted_payload.bin"
    mock_payload.write_text("HIGH_ENTROPY_DATA", encoding="utf-8")

    mock_security = mock_security_class.return_value
    mock_security.scan_binary.return_value = {}

    # Mock returning high entropy for this file
    mock_security.scan_content.return_value = {"counts": {"entropy": 7.5, "bitwise_ops": 0}}

    with patch("sys.argv", ["xray", str(repo_dir)]):
        xray_module.main()

    captured = capsys.readouterr()
    assert "[SUCCESS] No obfuscated payloads or binary anomalies detected." in captured.out
    assert "known mock/safe files were bypassed via configuration." in captured.out


# ==============================================================================
# TEST 11: #335 -- .galaxyscope.yaml ACTUALLY REACHES STANDALONE MAIN()
# ==============================================================================
@patch("gitgalaxy.tools.supply_chain_security.binary_anomaly_detector.SecurityLens")
@patch("gitgalaxy.tools.supply_chain_security.binary_anomaly_detector.ApertureFilter")
def test_yaml_config_flag_actually_changes_standalone_xray_behavior(mock_aperture_class, mock_security_class, tmp_path):
    """
    Before #335, binary_anomaly_detector.py imported DENYLIST_PATTERNS as a
    module-level constant at load time -- no YAML file, no --config flag,
    nothing could ever change what it blocked. This proves the gap is
    closed: the IDENTICAL file, scanned via the IDENTICAL standalone
    main() CLI entrypoint, passes clean with no --config and hard-blocks
    once a .galaxyscope.yaml denylists its exact filename pattern.
    """
    mock_aperture = mock_aperture_class.return_value
    mock_aperture._check_ignore_rules.return_value = True
    mock_security_class.return_value.scan_binary.return_value = {}
    mock_security_class.return_value.scan_content.return_value = {"counts": {"entropy": 0, "bitwise_ops": 0}}

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "asset.blob").write_text("nothing anomalous here", encoding="utf-8")

    # BEFORE: no --config -- DENYLIST_PATTERNS defaults to [], clean pass.
    with patch("sys.argv", ["xray", str(repo_dir)]):
        try:
            xray_module.main()
        except SystemExit:
            pytest.fail("Detector blocked a file with no denylist config applied.")

    # AFTER: identical file, identical CLI entrypoint, but a .galaxyscope.yaml
    # now denylists this exact pattern -- must hard-block via SystemExit(1).
    config_path = _write_config_yaml(tmp_path, DENYLIST_PATTERNS=["*.blob"])
    with patch("sys.argv", ["xray", str(repo_dir), "--config", config_path]):
        with pytest.raises(SystemExit) as exc:
            xray_module.main()
        assert exc.value.code == 1, (
            "YAML DENYLIST_PATTERNS override never reached standalone "
            "binary_anomaly_detector.py main() -- the #332/#335 "
            "reachability gap is still open."
        )
