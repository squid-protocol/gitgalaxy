import sys
from unittest.mock import patch

# IMPORTANT: Adjust this path to match exactly where your file is located
import gitgalaxy.tools.cobol_to_cobol.cobol_microservice_slicer as slicer_module


# ==============================================================================
# TEST 1: The Recursive Alias Engine (Taint Tracking)
# ==============================================================================
def test_slicer_recursive_tainting(tmp_path):
    """
    Proves that the engine successfully chains taints across multiple operations
    (MOVE, ADD, COMPUTE) and extracts exactly the lines that touch the logic.
    """
    pgm = tmp_path / "SLICE1.cbl"
    cobol_code = (
        "       PROCEDURE DIVISION.\n"
        "       MAIN-ENTRY.\n"
        "           MOVE TARGET-VAR TO VAR-B.\n"  # Taints VAR-B
        "           ADD 10 TO VAR-B.\n"  # Extracted (touches VAR-B)
        "           COMPUTE VAR-C = VAR-B * 2.\n"  # Taints VAR-C
        "           DISPLAY VAR-C.\n"  # Extracted (touches VAR-C)
        "           DISPLAY NOISE-VAR.\n"  # Ignored (Untainted)
    )
    pgm.write_text(cobol_code, encoding="utf-8")

    logic, taints = slicer_module.slice_business_logic(pgm, "TARGET-VAR")

    # 1. Verify Taint Graph
    assert "TARGET-VAR" in taints
    assert "VAR-B" in taints
    assert "VAR-C" in taints
    assert "NOISE-VAR" not in taints, "Engine hallucinated a taint on a noise variable!"

    # 2. Verify Line Extraction
    assert len(logic) == 4, "Failed to slice the exact 4 lines of business logic!"
    extracted_statements = [item["statement"] for item in logic]
    assert "MOVE TARGET-VAR TO VAR-B." in extracted_statements
    assert "COMPUTE VAR-C = VAR-B * 2." in extracted_statements
    assert "DISPLAY NOISE-VAR." not in extracted_statements


# ==============================================================================
# TEST 2: The Ghost Deflector (IR Context Awareness)
# ==============================================================================
def test_slicer_ghost_deflector(tmp_path):
    """
    Proves that the slicer uses the IR RAM (dead_paras) to mathematically blind
    itself to dead code, preventing false-positive taints and extractions.
    """
    pgm = tmp_path / "SLICE2.cbl"
    cobol_code = (
        "       PROCEDURE DIVISION.\n"
        "       MAIN-ENTRY.\n"
        "           MOVE TARGET-VAR TO ALIAS-1.\n"
        "       DEAD-PARA.\n"  # This paragraph is mathematically dead
        "           MOVE ALIAS-1 TO ALIAS-2.\n"  # Should NOT taint ALIAS-2
        "           DISPLAY ALIAS-2.\n"  # Should NOT be extracted
    )
    pgm.write_text(cobol_code, encoding="utf-8")

    logic, taints = slicer_module.slice_business_logic(pgm, "TARGET-VAR", dead_paras={"DEAD-PARA"})

    # 1. Verify the deflector blocked the taint
    assert "ALIAS-1" in taints
    assert "ALIAS-2" not in taints, "Ghost Deflector failed! ALIAS-2 was tainted by dead code."

    # 2. Verify the deflector blocked the extraction
    assert len(logic) == 1
    assert logic[0]["statement"] == "MOVE TARGET-VAR TO ALIAS-1."
    assert "DEAD-PARA" not in [item["paragraph"] for item in logic]


# ==============================================================================
# TEST 3: The Orphaned Memory Abort (Fast Exit)
# ==============================================================================
def test_slicer_orphaned_memory_abort(tmp_path):
    """
    Proves that if the Graveyard Reaper identifies the variable as dead memory,
    the slicer instantly aborts processing to save CPU cycles.
    """
    pgm = tmp_path / "SLICE3.cbl"
    pgm.write_text(
        "       PROCEDURE DIVISION.\n       MAIN.\n           MOVE A TO B.\n",
        encoding="utf-8",
    )

    logic, taints = slicer_module.slice_business_logic(pgm, "DEAD-VAR", orphaned_vars={"DEAD-VAR"})

    assert logic == [], "Orphaned memory abort failed to return an empty logic slice!"
    assert isinstance(taints, dict)
    assert taints["DEAD-VAR"] == "ORPHANED_MEMORY", "Failed to return the abort payload!"


# ==============================================================================
# TEST 4: The CLI E2E Output
# ==============================================================================
def test_slicer_cli_e2e(tmp_path, capsys):
    """
    Proves the CLI wrapper correctly formats the extracted slice into terminal output.
    """
    pgm = tmp_path / "SLICE4.cbl"
    pgm.write_text(
        "       PROCEDURE DIVISION.\n       MAIN-ENTRY.\n           MOVE T TO X.\n",
        encoding="utf-8",
    )

    test_args = ["cobol_microservice_slicer.py", str(pgm), "--var", "T"]
    with patch.object(sys, "argv", test_args):
        try:
            slicer_module.main()
        except SystemExit as e:
            assert e.code == 0

    captured = capsys.readouterr()
    assert "TAINTS FOUND: T, X" in captured.out or "TAINTS FOUND: X, T" in captured.out
    assert "[MAIN-ENTRY]" in captured.out
    assert "MOVE T TO X." in captured.out
