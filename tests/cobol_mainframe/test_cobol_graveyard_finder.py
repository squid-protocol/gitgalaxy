import sys
from unittest.mock import patch

# IMPORTANT: Adjust this path to match exactly where your file is located
import gitgalaxy.tools.cobol_to_cobol.cobol_graveyard_finder as graveyard_module


# ==============================================================================
# TEST 1: The Copybook Shapeshifter (Inline Variable Swapping)
# ==============================================================================
def test_copybook_shapeshifter(tmp_path):
    """
    Proves that the engine correctly resolves local .cpy files, injects their
    contents, and accurately processes the REPLACING ==A== BY ==B== logic.
    """
    repo_dir = tmp_path / "copy_repo"
    repo_dir.mkdir()

    # 1. The main program
    main_pgm = repo_dir / "MAIN.cbl"
    main_pgm.write_text("       COPY MYDATA REPLACING ==OLD-VAR== BY ==NEW-VAR==.", encoding="utf-8")

    # 2. The external copybook
    copybook = repo_dir / "MYDATA.cpy"
    copybook.write_text("       01 OLD-VAR PIC X(10).\n       01 OLD-VAR-X PIC X(5).", encoding="utf-8")

    # 3. Execute the resolver
    raw_content = main_pgm.read_text(encoding="utf-8")
    resolved_content = graveyard_module.resolve_copybooks(raw_content, main_pgm)

    # 4. Assertions
    # A) Ensure the content was injected
    assert "START COPY MYDATA" in resolved_content
    # B) Ensure the strict boundary replacement worked (OLD-VAR became NEW-VAR)
    assert "01 NEW-VAR PIC" in resolved_content
    # C) ZERO-TRUST GUARD: Ensure partial matches were NOT replaced (OLD-VAR-X stays OLD-VAR-X)
    assert "01 OLD-VAR-X PIC" in resolved_content, "The Shapeshifter destroyed a partial word match!"


# ==============================================================================
# TEST 2: The AST Dead Code Math
# ==============================================================================
def test_ast_dead_code_math(tmp_path):
    """
    Proves that the engine correctly separates data from execution, isolates
    orphaned variables, and calculates unreachable phantom paragraphs.
    """
    mock_cobol = tmp_path / "DEADPGM.cbl"
    cobol_code = (
        "       DATA DIVISION.\n"
        "       01 USED-VAR      PIC X.\n"
        "       01 ORPHAN-VAR    PIC X.\n"  # Declared but never used
        "       01 FILLER        PIC X.\n"  # Noise, should be ignored
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"  # Entry point (Reached)
        "           PERFORM USED-PARA.\n"
        "       USED-PARA.\n"  # Reached via PERFORM
        "           DISPLAY USED-VAR.\n"
        "       DEAD-PARA.\n"  # Unreachable (Phantom)
        "           DISPLAY 'HELLO'.\n"
        "       DEAD-EXIT.\n"  # Ends in -EXIT (Should be ignored)
    )
    mock_cobol.write_text(cobol_code, encoding="utf-8")

    metrics = graveyard_module.x_ray_dead_code(mock_cobol)

    # 1. Variable Assertions
    assert "ORPHAN-VAR" in metrics["orphaned_vars"]
    assert "USED-VAR" not in metrics["orphaned_vars"]
    assert "FILLER" not in metrics["orphaned_vars"], "Engine failed to filter out FILLER noise!"

    # 2. Paragraph Assertions
    assert "DEAD-PARA" in metrics["dead_paras"]
    assert "MAIN-PARA" not in metrics["dead_paras"], "Engine flagged the entry point as dead!"
    assert "USED-PARA" not in metrics["dead_paras"]
    assert "DEAD-EXIT" not in metrics["dead_paras"], "Engine failed to filter out *-EXIT paragraphs!"

    # 3. Math (1 orphaned var + 1 dead para * 10 lines = 11 LOC saved)
    assert metrics["loc_saved"] == 11


# ==============================================================================
# TEST 3: The E2E CLI Aggregation
# ==============================================================================
def test_graveyard_cli_e2e(tmp_path, capsys):
    """
    Proves the CLI wrapper recurses directories, tallies the bloat savings
    across multiple files, and prints a mathematically accurate summary.
    """
    repo_dir = tmp_path / "legacy_src"
    repo_dir.mkdir()

    # File 1: Has 1 dead paragraph (10 LOC)
    (repo_dir / "PGM1.cbl").write_text(
        "       DATA DIVISION.\n       PROCEDURE DIVISION.\n       MAIN.\n       DEAD-P.\n",
        encoding="utf-8",
    )

    # File 2: Has 2 orphaned vars (2 LOC)
    (repo_dir / "PGM2.cbl").write_text(
        "       DATA DIVISION.\n       01 D1 PIC X.\n       01 D2 PIC X.\n       PROCEDURE DIVISION.\n       MAIN.\n",
        encoding="utf-8",
    )

    test_args = ["cobol_graveyard_finder.py", str(repo_dir)]
    with patch.object(sys, "argv", test_args):
        try:
            graveyard_module.main()
        except SystemExit as e:
            assert e.code == 0

    captured = capsys.readouterr()

    # Assertions on the final CLI output calculations
    assert "Files Flagged for Cleanup : 2" in captured.out
    assert "Unused Memory Addresses   : 2 variables" in captured.out
    assert "Unreachable Logic Blocks  : 1 paragraphs" in captured.out
    assert "Estimated Bloat Removed : ~12 Lines of Code" in captured.out
