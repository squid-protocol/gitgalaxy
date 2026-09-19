import json
from unittest.mock import patch

import pytest

# IMPORTANT: Adjust this path to match exactly where your file is located
import gitgalaxy.cobol_refractor_controller as controller_module


# ==============================================================================
# TEST 1: The Scale Sensor (OOM Protection)
# ==============================================================================
def test_scale_sensor_calibration(tmp_path):
    """
    Proves the orchestrator accurately calculates repository mass and dynamically
    toggles the storage medium to prevent Out-Of-Memory (OOM) crashes.
    """
    repo_dir = tmp_path / "legacy_repo"
    repo_dir.mkdir()

    # Create 3 small mock COBOL files
    for i in range(3):
        (repo_dir / f"PGM{i}.cbl").write_text("IDENTIFICATION DIVISION.", encoding="utf-8")

    # 1. Test RAM Mode (Thresholds are higher than the payload)
    mode, files = controller_module.calibrate_ir_medium(repo_dir, max_files=5, max_mb=10)
    assert mode == "RAM", "Failed to default to high-speed RAM!"
    assert len(files) == 3

    # 2. Test SQLite Mode (Threshold tripped by file count)
    mode, files = controller_module.calibrate_ir_medium(repo_dir, max_files=2, max_mb=10)
    assert mode == "SQLITE", "Scale sensor failed to trip the SQLite safety switch!"


# ==============================================================================
# TEST 2: Hybrid State Manager Parity
# ==============================================================================
def test_ir_state_manager_parity(tmp_path):
    """
    Proves that the IR abstraction layer perfectly mirrors data retrieval
    whether backed by temporary RAM or a physical SQLite disk database.
    """
    # 1. Initialize RAM Manager
    ram_mgr = controller_module.IRStateManager("RAM", tmp_path)
    ram_mgr.record_dead_code("PGM-ALPHA", dead_paras={"GHOST-PARA"}, orphaned_vars={"DEAD-VAR"})

    # 2. Initialize SQLite Manager
    sql_mgr = controller_module.IRStateManager("SQLITE", tmp_path)
    sql_mgr.record_dead_code("PGM-ALPHA", dead_paras={"GHOST-PARA"}, orphaned_vars={"DEAD-VAR"})

    # 3. Assert Parity
    assert ram_mgr.get_dead_paras("PGM-ALPHA") == sql_mgr.get_dead_paras("PGM-ALPHA")
    assert ram_mgr.get_orphaned_vars("PGM-ALPHA") == sql_mgr.get_orphaned_vars("PGM-ALPHA")

    # 4. Verify SQLite strictly wrote to disk
    assert (tmp_path / "gitgalaxy_ir.db").exists()
    sql_mgr.close()


# ==============================================================================
# TEST 3: Payload Integration Orchestrator
# ==============================================================================
def test_process_payload_integration(tmp_path):
    """
    Proves the orchestrator successfully routes a file through the sub-tools
    (Graveyard Reaper, Lineage Architect, Schema Forge) and aggregates the state.
    """
    cbl_file = tmp_path / "MAINPGM.cbl"
    cbl_file.write_text(
        "       PROGRAM-ID. MAINPGM.\n"
        "       DATA DIVISION.\n"
        "       01 DEAD-VAR PIC X.\n"  # Will trigger Graveyard Reaper
        "       PROCEDURE DIVISION.\n"
        "       MAIN.\n"
        "           DISPLAY 'HELLO'.\n",
        encoding="utf-8",
    )

    mgr = controller_module.IRStateManager("RAM", tmp_path)
    ir_state = controller_module.process_payload(cbl_file, mgr)

    # 1. Verify Metadata Extraction
    assert ir_state["metadata"]["file_name"] == "MAINPGM.cbl"

    # 2. Verify Graveyard Sub-Tool Integration
    assert "DEAD-VAR" in ir_state["analysis"]["dead_code"]["orphaned_vars"], (
        "Orchestrator failed to invoke Graveyard Reaper!"
    )

    # 3. Verify Schema Sub-Tool Integration
    assert "schemas" in ir_state["generation"]

    # 4. Verify IR State Manager persistence
    assert mgr.get_orphaned_vars("MAINPGM") == {"DEAD-VAR"}, "Orchestrator failed to sync with global IR State Manager!"


# ==============================================================================
# TEST 4: Corporate Header & I/O Exception Trap
# ==============================================================================
def test_process_payload_corporate_header_and_exception(tmp_path):
    """Proves the payload processor injects corporate headers and survives locked files."""
    repo_dir = tmp_path / "header_repo"
    repo_dir.mkdir()

    header_file = repo_dir / "corporate_header.txt"
    header_file.write_text("COPYRIGHT 2026", encoding="utf-8")

    cbl_file = repo_dir / "MAIN.cbl"
    cbl_file.write_text("CODE", encoding="utf-8")

    mgr = controller_module.IRStateManager("RAM", tmp_path)

    # 1. Test Header Success
    ir_success = controller_module.process_payload(cbl_file, mgr)
    assert ir_success["metadata"]["corporate_header"] == "COPYRIGHT 2026"
    assert ir_success["metadata"]["loc"] == 1

    # Remove the header file so the mock exception doesn't trip outside the try/except block!
    header_file.unlink()

    # 2. Test Exception block (File Read Error)
    with patch("pathlib.Path.read_text", side_effect=PermissionError("Locked file!")):
        ir_fail = controller_module.process_payload(cbl_file, mgr)
        assert "loc" not in ir_fail["metadata"], "Orchestrator failed to gracefully catch the read exception!"


# ==============================================================================
# TEST 5: CLI Main - Missing Target
# ==============================================================================
def test_main_missing_target(capsys):
    """Proves the CLI gracefully aborts if the legacy directory doesn't exist."""
    with patch("sys.argv", ["refract", "missing_legacy_repo_12345"]), pytest.raises(SystemExit) as exc_info:
        controller_module.main()

    assert exc_info.value.code == 1
    assert "does not exist" in capsys.readouterr().out


# ==============================================================================
# TEST 6: CLI Main - Empty Target (No COBOL files)
# ==============================================================================
def test_main_empty_target(tmp_path, capsys):
    """Proves the CLI safely exits (code 0) if no COBOL code is found to refract."""
    repo_dir = tmp_path / "empty_repo"
    repo_dir.mkdir()

    with patch("sys.argv", ["refract", str(repo_dir)]), pytest.raises(SystemExit) as exc_info:
        controller_module.main()

    assert exc_info.value.code == 0
    assert "No executable COBOL files found" in capsys.readouterr().out


# ==============================================================================
# TEST 7: CLI Main - Full End-to-End Orchestration & Artifact Forging
# ==============================================================================
def test_main_full_orchestration(tmp_path, capsys):
    """
    Proves the orchestrator successfully creates the Clean Room environment,
    invokes all sub-tools, aggregates the telemetry, and writes all artifact
    files (JCL, SQL, JSON, Slices, and the Audit Report) to disk.
    """
    repo_dir = tmp_path / "full_legacy_app"
    repo_dir.mkdir()
    (repo_dir / "PRG1.cbl").write_text("IDENTIFICATION DIVISION.", encoding="utf-8")

    # We mock ALL the heavy sub-tools to ensure the Orchestrator loop executes flawlessly
    # without needing actual compilers or ML models to run.
    with (
        patch("sys.argv", ["refract", str(repo_dir), "--var", "TARGET-VAR"]),
        patch(
            "gitgalaxy.cobol_refractor_controller.patch_lexical_content",
            return_value=None,
        ),
        patch(
            "gitgalaxy.cobol_refractor_controller.x_ray_dead_code",
            return_value={
                "loc_saved": 50,
                "orphaned_vars": {"DEAD_VAR"},
                "dead_paras": {"DEAD_PARA"},
            },
        ),
        patch(
            "gitgalaxy.cobol_refractor_controller.extract_lineage",
            return_value={
                "inputs": set(),
                "outputs": set(),
                "unresolved_calls": ["EXTERNAL_CALL"],
            },
        ),
        patch(
            "gitgalaxy.cobol_refractor_controller.analyze_cobol_intent",
            return_value="BATCH",
        ),
        patch(
            "gitgalaxy.cobol_refractor_controller.scan_system_limits",
            return_value=["HONESTY FLAG: Hardcoded IP"],
        ),
        patch(
            "gitgalaxy.cobol_refractor_controller.forge_schemas",
            return_value={"sql": "CREATE TABLE;", "json": {}},
        ),
        patch(
            "gitgalaxy.cobol_refractor_controller.generate_zero_trust_jcl",
            return_value="//MOCK_JCL JOB",
        ),
        patch(
            "gitgalaxy.cobol_refractor_controller.slice_business_logic",
            return_value=({"rule": "mock"}, ["alias1"]),
        ),
        patch(
            "gitgalaxy.cobol_refractor_controller.audit_zero_trust_jcls",
            return_value={
                "audited": 1,
                "original_loc": 100,
                "forged_loc": 50,
                "excess_dds_blocked": 1,
                "bloat_reduction_pct": 50,
            },
        ),
        patch("gitgalaxy.cobol_refractor_controller.forge_agent_jobs", return_value=3),
    ):
        # Execute the main orchestrator loop
        controller_module.main()

    # Find the dynamically generated clean_dir (timestamped)
    clean_dirs = list(tmp_path.glob("*_gitgalaxy_clean_*"))
    assert len(clean_dirs) == 1, "Orchestrator failed to create the Clean Room directory!"
    clean_dir = clean_dirs[0]

    # Verify all 5 Architectural Pillars were written to disk
    assert (clean_dir / "01_zero_trust_jcls" / "PRG1.jcl").exists(), "Failed to write JCL artifacts!"
    assert (clean_dir / "02_cloud_schemas" / "PRG1_schema.sql").exists(), "Failed to write SQL schema artifacts!"
    assert (clean_dir / "02_cloud_schemas" / "PRG1_schema.json").exists(), "Failed to write JSON schema artifacts!"
    assert (clean_dir / "04_ir_state_dumps" / "PRG1_ir.json").exists(), "Failed to write IR State dumps!"
    assert (clean_dir / "05_microservice_slices" / "PRG1_slice.json").exists(), "Failed to write Microservice Slices!"

    # Verify the Master Audit Report aggregated all the mocked telemetry
    audit_file = clean_dir / "03_audit_reports" / "master_refraction_audit.txt"
    assert audit_file.exists(), "Orchestrator failed to generate the Master Audit Report!"

    audit_text = audit_file.read_text(encoding="utf-8")
    assert "HONESTY FLAG: Hardcoded IP" in audit_text, "Failed to aggregate System Limit honesty flags!"
    assert "Unresolved Dynamic CALL to: EXTERNAL_CALL" in audit_text, "Failed to aggregate Lineage honesty flags!"
    assert "AI Agent Job Tickets Generated : 3" in audit_text, "Failed to aggregate Agent Job counts!"
    assert "Bloat Removed: ~50 Lines" in audit_text, "Failed to aggregate Graveyard Reaper stats!"


# ==============================================================================
# TEST 8: IRStateManager Unsafe Connection & Fallback Returns
# ==============================================================================
def test_ir_state_manager_unsafe_conn_and_fallback(tmp_path):
    """
    Proves the IRStateManager safely handles an unexpected None connection
    and invalid modes without crashing, returning empty sets as required.
    """
    # 1. Test invalid mode (Missing returns fix)
    invalid_mgr = controller_module.IRStateManager("UNKNOWN_MODE", tmp_path)
    assert invalid_mgr.get_dead_paras("PGM") == set(), "Failed to return empty set on invalid mode!"
    assert invalid_mgr.get_orphaned_vars("PGM") == set(), "Failed to return empty set on invalid mode!"

    # 2. Test SQLITE mode but connection drops/is None (Unsafe connection fix)
    sql_mgr = controller_module.IRStateManager("SQLITE", tmp_path)
    sql_mgr.conn = None  # Force the connection to drop

    # Should not raise an AttributeError
    sql_mgr.record_dead_code("PGM", {"PARA"}, {"VAR"})
    assert sql_mgr.get_dead_paras("PGM") == set(), "Failed to return empty set on dropped connection!"
    assert sql_mgr.get_orphaned_vars("PGM") == set(), "Failed to return empty set on dropped connection!"


# ==============================================================================
# TEST 9: The target repository is never written (#3206)
# ==============================================================================
def test_process_payload_patches_a_copy_not_the_target(tmp_path):
    """A program with NEXT SENTENCE is patched into patched_dir, mirroring its
    path under source_root; the original file keeps its exact bytes."""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    cbl_file = repo / "src" / "PATCHME.cbl"
    original = (
        "       PROGRAM-ID. PATCHME.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN.\n"
        "           IF A = B NEXT SENTENCE END-IF.\n"
    )
    cbl_file.write_text(original, encoding="utf-8")
    patched_dir = tmp_path / "clean" / "00_patched_source"

    mgr = controller_module.IRStateManager("RAM", tmp_path)
    ir_state = controller_module.process_payload(cbl_file, mgr, patched_dir=patched_dir, source_root=repo)

    assert cbl_file.read_text(encoding="utf-8") == original, "The refractor rewrote the target repository!"
    patched = patched_dir / "src" / "PATCHME.cbl"
    assert patched.read_text(encoding="utf-8") != original
    assert "CONTINUE *> GitGalaxy Patch" in patched.read_text(encoding="utf-8")
    assert ir_state["metadata"]["patched_path"] == str(patched)
    assert ir_state["metadata"]["path"] == str(cbl_file)


def test_process_payload_without_patched_dir_writes_nothing(tmp_path):
    cbl_file = tmp_path / "PATCHME.cbl"
    original = "       PROCEDURE DIVISION.\n       MAIN.\n           IF A = B NEXT SENTENCE END-IF.\n"
    cbl_file.write_text(original, encoding="utf-8")

    mgr = controller_module.IRStateManager("RAM", tmp_path)
    ir_state = controller_module.process_payload(cbl_file, mgr)

    assert cbl_file.read_text(encoding="utf-8") == original
    assert "patched_path" not in ir_state["metadata"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["PATCHME.cbl"]


# ==============================================================================
# TEST 10: Deterministic IR dumps (#3212)
# ==============================================================================
def test_ir_dump_sorts_sets():
    """Sets are written sorted, whatever their (hash-randomised) iteration order."""
    names = [f"PARA-{i:03d}" for i in range(50)]
    ir_state = {"analysis": {"dead_code": {"dead_paras": set(names)}}}

    assert json.loads(controller_module._ir_to_json(ir_state))["analysis"]["dead_code"]["dead_paras"] == names


# ==============================================================================
# TEST 11: Same-named programs keep separate outputs and IR state (#3218)
# ==============================================================================
def _same_stem_repo(root):
    """Two SAM2.cbl programs. Each one's live paragraph is the other's dead one, so a
    dead-code store keyed by stem hands the second program the first one's verdicts."""
    head = (
        "       PROGRAM-ID. SAM2.\n"
        "           SELECT OUT-FILE ASSIGN TO {dd}.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           PERFORM {live}.\n"
        "           GOBACK.\n"
    )
    body = "       P1.\n           {p1}\n       P2.\n           {p2}\n"
    for sub, dd, live, p1, p2 in (
        ("COBOL", "OUTA", "P1", "OPEN OUTPUT OUT-FILE.", "DISPLAY 'A'."),
        ("multiroot/sam", "OUTB", "P2", "DISPLAY 'B'.", "OPEN OUTPUT OUT-FILE."),
    ):
        (root / sub).mkdir(parents=True)
        (root / sub / "SAM2.cbl").write_text(
            head.format(dd=dd, live=live) + body.format(p1=p1, p2=p2), encoding="utf-8"
        )


def test_output_keys_disambiguate_only_collisions(tmp_path):
    files = [tmp_path / "COBOL" / "SAM2.cbl", tmp_path / "multiroot" / "sam" / "SAM2.cbl", tmp_path / "X" / "SOLO.cbl"]

    keys = controller_module._output_keys(files, tmp_path)

    assert keys == {files[0]: "COBOL__SAM2", files[1]: "multiroot__sam__SAM2", files[2]: "SOLO"}


@pytest.mark.parametrize("ir_mode", ["RAM", "SQLITE"])
def test_same_named_programs_do_not_share_outputs_or_dead_code(tmp_path, ir_mode):
    repo = tmp_path / "zopen"
    _same_stem_repo(repo)

    real_calibrate = controller_module.calibrate_ir_medium

    def forced(target_path, cobol_files=None):
        _, files = real_calibrate(target_path, cobol_files=cobol_files)
        return ir_mode, files

    with (
        patch("sys.argv", ["refract", str(repo)]),
        patch("gitgalaxy.cobol_refractor_controller.calibrate_ir_medium", side_effect=forced),
    ):
        controller_module.main()

    clean_dir = next(tmp_path.glob("*_gitgalaxy_clean_*"))
    ir_dir = clean_dir / "04_ir_state_dumps"
    assert sorted(p.name for p in ir_dir.glob("*_ir.json")) == ["COBOL__SAM2_ir.json", "multiroot__sam__SAM2_ir.json"]
    assert sorted(p.name for p in (clean_dir / "01_zero_trust_jcls").glob("*.jcl")) == [
        "COBOL__SAM2.jcl",
        "multiroot__sam__SAM2.jcl",
    ]

    a = json.loads((ir_dir / "COBOL__SAM2_ir.json").read_text(encoding="utf-8"))
    b = json.loads((ir_dir / "multiroot__sam__SAM2_ir.json").read_text(encoding="utf-8"))
    assert a["analysis"]["dead_code"]["dead_paras"] == ["P2"]
    assert b["analysis"]["dead_code"]["dead_paras"] == ["P1"]
    # Masked with the other program's dead code, B's only OPEN (in its live P2) vanished.
    assert a["analysis"]["lineage"]["outputs"] == ["OUTA"]
    assert b["analysis"]["lineage"]["outputs"] == ["OUTB"]
