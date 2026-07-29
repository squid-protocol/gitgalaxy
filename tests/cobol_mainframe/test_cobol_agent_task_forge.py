import json

# IMPORTANT: Adjust this path to match exactly where your file is located
import gitgalaxy.tools.cobol_to_cobol.cobol_agent_task_forge as forge_module


# ==============================================================================
# TEST 1: The Context Merger (Ticket Generation)
# ==============================================================================
def test_generate_agent_ticket_merging(tmp_path):
    """
    Proves the engine accurately builds the JSON ticket, strips the filename
    prefix from the anomaly strings, and seamlessly merges the IR lineage.
    """
    mock_file = tmp_path / "PGM1.cbl"
    mock_anomalies = [
        "[PGM1.cbl : Line 0010] CRITICAL LIMIT - ALTER detected",
        "[PGM1.cbl : Line 0020] HIGH LIMIT - COPY REPLACING detected",
    ]

    mock_ir = {
        "analysis": {
            "lineage": {
                "inputs": ["FILE-IN"],
                "outputs": ["FILE-OUT"],
                "unresolved_calls": ["SUBPROG"],
            }
        }
    }

    ticket = forge_module.generate_agent_ticket("PGM1.cbl", mock_file, mock_anomalies, mock_ir)

    # 1. Base Ticket Structure
    assert ticket["job_id"] == "PGM1_REMEDIATION"
    assert ticket["task_type"] == "STRUCTURAL_ANOMALY_RESOLUTION"
    assert ticket["target_file"] == str(mock_file.resolve())

    # 2. Anomaly Stripping
    assert "CRITICAL LIMIT - ALTER detected" in ticket["context"]["detected_anomalies"]
    assert "[PGM1.cbl" not in ticket["context"]["detected_anomalies"][0], "Failed to strip the prefix!"

    # 3. IR Lineage Merging
    assert ticket["context"]["inputs_required"] == ["FILE-IN"]
    assert ticket["context"]["outputs_produced"] == ["FILE-OUT"]
    assert ticket["context"]["external_calls"] == ["SUBPROG"]


# ==============================================================================
# TEST 2: The E2E Job Dispatcher (Grouping & File I/O)
# ==============================================================================
def test_forge_agent_jobs_e2e(tmp_path):
    """
    Proves the engine correctly groups multiple flags by file, matches them to
    physical source files, and writes the JSON job tickets to the designated folder.
    """
    clean_room = tmp_path / "clean_room"
    source_dir = tmp_path / "legacy_src"
    source_dir.mkdir()

    # Create the mock source file so the engine finds it
    (source_dir / "PGM2.cbl").write_text("IDENTIFICATION DIVISION.", encoding="utf-8")

    mock_flags = ["[PGM2.cbl] ERROR 1", "[PGM2.cbl] ERROR 2"]

    jobs_created = forge_module.forge_agent_jobs(clean_room, source_dir, mock_flags)

    assert jobs_created == 1, "Failed to group 2 flags into 1 job ticket!"

    # Verify the output directory and file
    job_dir = clean_room / "06_ai_agent_jobs"
    job_file = job_dir / "PGM2_agent_job.json"

    assert job_dir.exists(), "Failed to create the 06_ai_agent_jobs directory!"
    assert job_file.exists(), "Failed to write the physical JSON ticket!"

    # Verify the written payload
    payload = json.loads(job_file.read_text(encoding="utf-8"))
    assert payload["job_id"] == "PGM2_REMEDIATION"
    assert len(payload["context"]["detected_anomalies"]) == 2


# ==============================================================================
# TEST 3: Graceful Degradation (Missing IR & Missing Source)
# ==============================================================================
def test_forge_agent_jobs_graceful_degradation(tmp_path):
    """
    Proves that missing IR state files don't crash the generation (fallback to
    empty arrays) and missing physical source files safely abort ticket creation.
    """
    clean_room = tmp_path / "clean_room"
    source_dir = tmp_path / "legacy_src"
    source_dir.mkdir()

    # PGM3 exists, but has NO matching IR file in 04_ir_state_dumps
    (source_dir / "PGM3.cbl").write_text("IDENTIFICATION DIVISION.", encoding="utf-8")

    # PGM4 does NOT exist in the source directory

    mock_flags = ["[PGM3.cbl] ERROR 1", "[PGM4.cbl] ERROR 2"]

    jobs_created = forge_module.forge_agent_jobs(clean_room, source_dir, mock_flags)

    # Only PGM3 should generate a ticket. PGM4 must be skipped.
    assert jobs_created == 1, "Failed to skip the missing source file!"

    job_file = clean_room / "06_ai_agent_jobs" / "PGM3_agent_job.json"
    assert job_file.exists()

    # Ensure it gracefully degraded the missing IR context to empty arrays
    payload = json.loads(job_file.read_text(encoding="utf-8"))
    assert payload["context"]["inputs_required"] == [], "Graceful fallback for missing IR inputs failed!"
    assert payload["context"]["outputs_produced"] == [], "Graceful fallback for missing IR outputs failed!"
