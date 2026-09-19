import sys
import time
from unittest.mock import patch

import pytest

# IMPORTANT: Adjust this path to match exactly where your file is located
import gitgalaxy.tools.cobol_to_cobol.cobol_dag_architect as dag_module


# ==============================================================================
# TEST 1: The Ghost Deflector & Intent Extraction
# ==============================================================================
def test_ghost_deflector_lineage(tmp_path):
    """
    Proves the lineage extractor correctly maps DD assignments, strips prefixes,
    catches dynamic calls, and perfectly ignores 'OPEN' statements hidden inside
    paragraphs marked as dead.
    """
    mock_cobol = tmp_path / "PGM1.cbl"
    cobol_code = (
        "       PROGRAM-ID. PGM1.\n"
        "       SELECT FILE-IN ASSIGN TO UT-S-INPUT01.\n"
        "       SELECT FILE-OUT ASSIGN TO OUTPUT01.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-ENTRY.\n"
        "           OPEN INPUT FILE-IN.\n"
        "           CALL 'STATIC-PGM'.\n"  # Static call (should be ignored)
        "           CALL WS-DYN-PGM.\n"  # Dynamic call (Honesty Sensor should catch)
        "       DEAD-PARA.\n"
        "           OPEN OUTPUT FILE-OUT.\n"  # This is dead code!
    )
    mock_cobol.write_text(cobol_code, encoding="utf-8")

    # 1. Test without dead code context (Base baseline)
    raw_lineage = dag_module.extract_lineage(mock_cobol)
    assert "INPUT01" in raw_lineage["inputs"]
    assert "OUTPUT01" in raw_lineage["outputs"]  # Without Ghost Deflector, it hallucinates this output

    # 2. Test WITH the Ghost Deflector activated
    safe_lineage = dag_module.extract_lineage(mock_cobol, dead_paras={"DEAD-PARA"})
    assert "INPUT01" in safe_lineage["inputs"]
    assert "OUTPUT01" not in safe_lineage["outputs"], "Ghost Deflector failed! It hallucinated dead code dependencies."

    # 3. Test the Honesty Sensor
    assert "WS-DYN-PGM" in safe_lineage["unresolved_calls"], "Failed to catch the dynamic jump!"
    assert "STATIC-PGM" not in safe_lineage["unresolved_calls"]


# ==============================================================================
# TEST 2: Mathematical Topological Sort (Happy Path)
# ==============================================================================
def test_dag_architect_topological_sort(tmp_path, capsys):
    """
    Proves Kahn's Algorithm perfectly calculates execution order by resolving
    Producer -> Consumer file dependencies.
    """
    repo_dir = tmp_path / "dag_repo"
    repo_dir.mkdir()

    # PGM_C reads FILE2 and writes FILE3
    (repo_dir / "PGMC.cbl").write_text(
        "       PROGRAM-ID. PGMC.\n"
        "       SELECT F2 ASSIGN TO FILE2.\n"
        "       SELECT F3 ASSIGN TO FILE3.\n"
        "       PROCEDURE DIVISION.\n"
        "           OPEN INPUT F2.\n"
        "           OPEN OUTPUT F3.\n",
        encoding="utf-8",
    )

    # PGM_A reads FILE0 and writes FILE1 (Should run FIRST)
    (repo_dir / "PGMA.cbl").write_text(
        "       PROGRAM-ID. PGMA.\n"
        "       SELECT F1 ASSIGN TO FILE1.\n"
        "       PROCEDURE DIVISION.\n"
        "           OPEN OUTPUT F1.\n",
        encoding="utf-8",
    )

    # PGM_B reads FILE1 and writes FILE2 (Should run SECOND)
    (repo_dir / "PGMB.cbl").write_text(
        "       PROGRAM-ID. PGMB.\n"
        "       SELECT F1 ASSIGN TO FILE1.\n"
        "       SELECT F2 ASSIGN TO FILE2.\n"
        "       PROCEDURE DIVISION.\n"
        "           OPEN INPUT F1.\n"
        "           OPEN OUTPUT F2.\n",
        encoding="utf-8",
    )

    test_args = ["cobol_dag_architect.py", str(repo_dir)]
    with patch.object(sys, "argv", test_args):
        dag_module.main()

    captured = capsys.readouterr()

    # Assert execution order is exactly A -> B -> C regardless of file read order
    assert "STEP 01: Run [PGMA]" in captured.out
    assert "STEP 02: Run [PGMB]" in captured.out
    assert "STEP 03: Run [PGMC]" in captured.out


# ==============================================================================
# TEST 3: Cycle Detection (Deadlock Trap)
# ==============================================================================
def test_dag_architect_cycle_detection(tmp_path, capsys):
    """
    Proves the engine catches circular data dependencies and halts execution
    before generating a mathematically impossible pipeline.
    """
    repo_dir = tmp_path / "cyclic_repo"
    repo_dir.mkdir()

    # PGM_1 reads FILE-B and writes FILE-A
    (repo_dir / "P1.cbl").write_text(
        "       PROGRAM-ID. P1.\n"
        "       SELECT FB ASSIGN TO FILE-B.\n"
        "       SELECT FA ASSIGN TO FILE-A.\n"
        "       PROCEDURE DIVISION.\n"
        "           OPEN INPUT FB.\n"
        "           OPEN OUTPUT FA.\n",
        encoding="utf-8",
    )

    # PGM_2 reads FILE-A and writes FILE-B (Creates a deadlock cycle)
    (repo_dir / "P2.cbl").write_text(
        "       PROGRAM-ID. P2.\n"
        "       SELECT FA ASSIGN TO FILE-A.\n"
        "       SELECT FB ASSIGN TO FILE-B.\n"
        "       PROCEDURE DIVISION.\n"
        "           OPEN INPUT FA.\n"
        "           OPEN OUTPUT FB.\n",
        encoding="utf-8",
    )

    test_args = ["cobol_dag_architect.py", str(repo_dir)]
    with patch.object(sys, "argv", test_args):
        with pytest.raises(SystemExit) as exc:
            dag_module.main()

        # Must exit with error code 1 due to the cycle
        assert exc.value.code == 1, "Failed to trap the cycle and crash the build!"

    captured = capsys.readouterr()
    assert "WARNING: Cyclic Dependency Detected" in captured.out
    assert "Deadlocked Programs:" in captured.out


# ==============================================================================
# TEST: Multi-mode OPEN (#3204)
# ==============================================================================
def test_multi_mode_open_switches_mode_per_keyword(tmp_path):
    """The zopeneditor SAM1.cbl shape: one OPEN with INPUT and OUTPUT operand lists.
    The mode switches at each keyword instead of applying the first to every file."""
    pgm = tmp_path / "SAM1.cbl"
    pgm.write_text(
        "       PROGRAM-ID. SAM1.\n"
        "           SELECT TRANSACTION-FILE ASSIGN TO TRANFILE.\n"
        "           SELECT CUSTOMER-FILE ASSIGN TO CUSTFILE.\n"
        "           SELECT CUSTOMER-FILE-OUT ASSIGN TO CUSTOUT.\n"
        "           SELECT REPORT-FILE ASSIGN TO CUSTRPT.\n"
        "           SELECT AUDIT-FILE ASSIGN TO AUDITLOG.\n"
        "       PROCEDURE DIVISION.\n"
        "       000-MAIN.\n"
        "           OPEN INPUT  TRANSACTION-FILE\n"
        "                       CUSTOMER-FILE\n"
        "                OUTPUT CUSTOMER-FILE-OUT\n"
        "                       REPORT-FILE.\n"
        "           OPEN EXTEND AUDIT-FILE.\n",
        encoding="utf-8",
    )

    lineage = dag_module.extract_lineage(pgm)

    assert lineage["inputs"] == {"TRANFILE", "CUSTFILE", "AUDITLOG"}
    assert lineage["outputs"] == {"CUSTOUT", "CUSTRPT", "AUDITLOG"}


# ==============================================================================
# TEST: Dead-unit masking follows sections and sequence-numbered headers (#3203)
# ==============================================================================
def test_masking_covers_a_dead_section_in_sequence_numbered_source(tmp_path):
    """Every line belongs to the latest paragraph OR section header, found as the
    graveyard finds them, so masking a dead section hides its body."""
    pgm = tmp_path / "PGM.cbl"
    pgm.write_text(
        "000100 PROGRAM-ID. PGM.\n"
        "000200     SELECT LIVE-FILE ASSIGN TO LIVEDD.\n"
        "000300     SELECT DEAD-FILE ASSIGN TO DEADDD.\n"
        "000400 PROCEDURE DIVISION.\n"
        "000500 MAIN SECTION.\n"
        "000600     OPEN INPUT LIVE-FILE.\n"
        "000700     GOBACK.\n"
        "000800 OLD-BATCH SECTION.\n"
        "000900     OPEN OUTPUT DEAD-FILE.\n",
        encoding="utf-8",
    )

    lineage = dag_module.extract_lineage(pgm, dead_paras={"OLD-BATCH"})

    assert lineage["inputs"] == {"LIVEDD"}
    assert lineage["outputs"] == set()


# ==============================================================================
# #3222: the OPEN operand run is sliced, not rescanned
# ==============================================================================
def test_open_operand_run_is_linear_on_unterminated_input(tmp_path):
    """`[^.]*\\.` inside the pattern rescanned to the end of the program from every
    OPEN. 20k unterminated OPENs cost 24s before, ~1ms after."""
    pgm = tmp_path / "BIG.cbl"
    pgm.write_text(
        "       PROGRAM-ID. BIG.\n       PROCEDURE DIVISION.\n" + "           OPEN INPUT WS-F\n" * 20000,
        encoding="utf-8",
    )

    start = time.perf_counter()
    lineage = dag_module.extract_lineage(pgm)
    elapsed = time.perf_counter() - start

    # No period anywhere, so no OPEN is a statement -- the old pattern's rule, kept.
    assert not lineage["inputs"] and not lineage["outputs"]
    assert elapsed < 5.0, f"OPEN scan took {elapsed:.2f}s on 20k unterminated OPENs"


def test_open_statements_still_read_every_mode_after_anchoring(tmp_path):
    """The anchored scan keeps #3204's multi-mode walk and stops at the period."""
    pgm = tmp_path / "IO.cbl"
    pgm.write_text(
        "       PROGRAM-ID. IO.\n"
        "       FILE-CONTROL.\n"
        "           SELECT F-IN ASSIGN TO DDIN.\n"
        "           SELECT F-OUT ASSIGN TO DDOUT.\n"
        "           SELECT F-UPD ASSIGN TO DDUPD.\n"
        "       PROCEDURE DIVISION.\n"
        "           OPEN INPUT F-IN OUTPUT F-OUT.\n"
        "           OPEN I-O F-UPD.\n",
        encoding="utf-8",
    )

    lineage = dag_module.extract_lineage(pgm)

    assert sorted(lineage["inputs"]) == ["DDIN", "DDUPD"]
    assert sorted(lineage["outputs"]) == ["DDOUT", "DDUPD"]
