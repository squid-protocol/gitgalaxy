import pytest
import sys
import json
from unittest.mock import patch

# IMPORTANT: Adjust this path to match exactly where your file is located
import gitgalaxy.tools.terabyte_log_scanning.terabyte_log_scanner as scanner_module


# ==============================================================================
# TEST 1: IR State Ingestion & Stream Processing
# ==============================================================================
def test_scanner_json_ingestion_and_extraction(tmp_path):
    """
    Validates that the scanner correctly parses the IR state JSON, extracts the targets,
    processes a binary log stream, and safely writes only the matching lines to disk.
    """
    # 1. Setup the physical mock workspace
    work_dir = tmp_path / "scanner_workspace"
    work_dir.mkdir()

    # A) The Mock IR State (GitGalaxy Standard Schema)
    ir_state = {"analysis": {"known_programs": ["PGM_ALPHA", "PGM_BETA"]}}
    state_file = work_dir / "ir_state.json"
    state_file.write_text(json.dumps(ir_state), encoding="utf-8")

    # B) The Mock Log File (Mix of noise and target hits)
    target_log = work_dir / "production_dump.log"
    target_log.write_text(
        "2026-05-11 09:15 [INFO] System boot sequence initialized\n"
        "2026-05-11 09:20 [EXEC] PGM_ALPHA executed successfully\n"
        "2026-05-11 09:25 [WARN] Unrelated process memory spike\n"
        "2026-05-11 10:00 [EXEC] PGM_BETA encountered warning 04\n"
        "2026-05-11 10:05 [EXEC] PGM_ALPHA restarted\n",
        encoding="utf-8",
    )

    # 2. Execute the Engine
    test_args = [
        "terabyte_log_scanner.py",
        str(target_log),
        "--input_state",
        str(state_file),
    ]

    with patch.object(sys, "argv", test_args):
        # We don't trap SystemExit here because a successful run should exit normally
        scanner_module.main()

    # 3. The Invariant Assertions
    # A) Verify the filtered results log
    results_file = work_dir / "production_dump_results.txt"
    assert results_file.exists(), "Scanner failed to create the results output file!"

    results_content = results_file.read_text(encoding="utf-8")

    assert "PGM_ALPHA executed successfully" in results_content
    assert "PGM_BETA encountered warning 04" in results_content
    assert "System boot sequence initialized" not in results_content, (
        "Unrelated log entries bypassed the stream filter."
    )

    # B) Verify the Telemetry Sidecar
    sidecar_file = work_dir / "dynamic_telemetry.json"
    assert sidecar_file.exists(), "Scanner failed to generate the JSON sidecar!"

    telemetry = json.loads(sidecar_file.read_text(encoding="utf-8"))
    counts = telemetry.get("execution_counts", {})

    # PGM_ALPHA appeared twice, PGM_BETA appeared once
    assert counts.get("PGM_ALPHA") == 2, "Execution count aggregation failed for PGM_ALPHA."
    assert counts.get("PGM_BETA") == 1, "Execution count aggregation failed for PGM_BETA."


# ==============================================================================
# TEST 2: Schema Validation (Invalid JSON Rejection)
# ==============================================================================
def test_scanner_invalid_json_schema(tmp_path):
    """
    Proves that if a malformed or incorrect JSON schema is provided, the
    scanner aggressively aborts to prevent silent failures down the pipeline.
    """
    work_dir = tmp_path / "schema_repo"
    work_dir.mkdir()

    # Create a JSON file missing the required 'analysis' -> 'known_programs' path
    bad_state_file = work_dir / "bad_state.json"
    bad_state_file.write_text(json.dumps({"wrong_root": []}), encoding="utf-8")

    dummy_log = work_dir / "dummy.log"
    dummy_log.write_text("empty", encoding="utf-8")

    test_args = [
        "terabyte_log_scanner.py",
        str(dummy_log),
        "--input_state",
        str(bad_state_file),
    ]

    with patch.object(sys, "argv", test_args):
        with pytest.raises(SystemExit) as exc:
            scanner_module.main()

        # The engine must throw a fatal error (exit code 1) on schema mismatch
        assert exc.value.code == 1, "Scanner failed to halt on an invalid JSON schema."


# ==============================================================================
# TEST 3: Manual Keyword Extraction (-k Flag)
# ==============================================================================
def test_scanner_manual_keyword_override(tmp_path):
    """
    Proves that the scanner can bypass the JSON input state and process
    raw CLI keyword arguments correctly.
    """
    work_dir = tmp_path / "cli_repo"
    work_dir.mkdir()

    target_log = work_dir / "app.log"
    target_log.write_text(
        "Line 1: ERROR 500\nLine 2: SUCCESS 200\nLine 3: ERROR 404\n",
        encoding="utf-8",
    )

    # Use -k ERROR to hunt for errors
    test_args = ["terabyte_log_scanner.py", str(target_log), "-k", "ERROR"]

    with patch.object(sys, "argv", test_args):
        scanner_module.main()

    results_file = work_dir / "app_results.txt"
    content = results_file.read_text(encoding="utf-8")

    assert "ERROR 500" in content
    assert "ERROR 404" in content
    assert "SUCCESS 200" not in content, "Manual keyword override failed to filter properly."


# ==============================================================================
# TEST 4: Missing Target Argument
# ==============================================================================
def test_missing_target_argument(capsys):
    """Ensures the CLI gracefully exits when no target is provided."""
    with patch.object(sys, "argv", ["terabyte_log_scanner.py"]):
        with pytest.raises(SystemExit) as exc_info:
            scanner_module.main()
        # argparse default exit code for missing arguments is 2
        assert exc_info.value.code == 2

    captured = capsys.readouterr()
    assert "the following arguments are required: target" in captured.err


# ==============================================================================
# TEST 5: Invalid Target Path Handling
# ==============================================================================
def test_invalid_target_path(tmp_path, capsys):
    """Ensures the tool exits cleanly when provided a non-existent file."""
    invalid_path = tmp_path / "does_not_exist.log"
    test_args = ["terabyte_log_scanner.py", str(invalid_path), "-k", "TEST"]

    with patch.object(sys, "argv", test_args):
        with pytest.raises(SystemExit) as exc_info:
            scanner_module.main()
        assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "Target log file does not exist or is not a file" in captured.out


# ==============================================================================
# TEST 6: Missing Input State File
# ==============================================================================
def test_missing_state_file(tmp_path, capsys):
    """Ensures the tool exits cleanly when the specified --input_state file is missing."""
    work_dir = tmp_path / "missing_state_repo"
    work_dir.mkdir()

    dummy_log = work_dir / "dummy.log"
    dummy_log.write_text("empty", encoding="utf-8")

    missing_state = work_dir / "missing.json"

    test_args = ["terabyte_log_scanner.py", str(dummy_log), "--input_state", str(missing_state)]

    with patch.object(sys, "argv", test_args):
        with pytest.raises(SystemExit) as exc_info:
            scanner_module.main()
        assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "Input state JSON file not found" in captured.out


# ==============================================================================
# TEST 7: Empty Known Programs Array
# ==============================================================================
def test_empty_known_programs(tmp_path, capsys):
    """Ensures the tool exits cleanly (code 0) if the known_programs array is empty."""
    work_dir = tmp_path / "empty_programs_repo"
    work_dir.mkdir()

    ir_state = {"analysis": {"known_programs": []}}
    state_file = work_dir / "ir_state.json"
    state_file.write_text(json.dumps(ir_state), encoding="utf-8")

    dummy_log = work_dir / "dummy.log"
    dummy_log.write_text("empty", encoding="utf-8")

    test_args = [
        "terabyte_log_scanner.py",
        str(dummy_log),
        "--input_state",
        str(state_file),
    ]

    with patch.object(sys, "argv", test_args):
        with pytest.raises(SystemExit) as exc_info:
            scanner_module.main()

        # An empty target list is not a crash, just a clean exit because there's nothing to do
        assert exc_info.value.code == 0

    captured = capsys.readouterr()
    assert "array is empty or invalid. Nothing to search." in captured.out


# ==============================================================================
# TEST 8: Custom Output Directory Override
# ==============================================================================
def test_custom_output_directory(tmp_path):
    """Verifies that the --out argument redirects the generated files successfully."""
    log_dir = tmp_path / "source_logs"
    log_dir.mkdir()
    target_log = log_dir / "app.log"
    target_log.write_text("2026-05-11T10:00 [DEBUG] ERROR 500\n", encoding="utf-8")

    custom_out = tmp_path / "analysis_results"
    test_args = ["terabyte_log_scanner.py", str(target_log), "-k", "ERROR", "--out", str(custom_out)]

    with patch.object(sys, "argv", test_args):
        scanner_module.main()

    assert custom_out.exists(), "Custom output directory was not created."

    results_file = custom_out / "app_results.txt"
    sidecar_file = custom_out / "dynamic_telemetry.json"

    assert results_file.exists(), "Results log not found in custom output directory."
    assert sidecar_file.exists(), "Telemetry JSON not found in custom output directory."
    assert "ERROR 500" in results_file.read_text(encoding="utf-8")
