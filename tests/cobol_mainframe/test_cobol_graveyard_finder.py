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


# ==============================================================================
# #3203 defects 1-4
# ==============================================================================
def _proc(*body):
    return "       DATA DIVISION.\n       PROCEDURE DIVISION.\n" + "".join(line + "\n" for line in body)


def test_scope_terminators_and_area_b_lines_are_not_paragraphs(tmp_path):
    """Defect 1: `END-IF.`, `GOBACK.` and the last line of a multi-line statement
    sit in Area B (col 12+) and are not paragraphs."""
    pgm = tmp_path / "SAM1.cbl"
    pgm.write_text(
        _proc(
            "       000-MAIN.",
            "           IF A = B",
            "              DISPLAY 'X'",
            "           END-IF.",
            "           DISPLAY 'TIME ' CURRENT-HOUR",
            "                   CURRENT-SECOND.",
            "           GOBACK.",
            "       100-DEAD.",
            "           EXIT.",
        ),
        encoding="utf-8",
    )

    metrics = graveyard_module.x_ray_dead_code(pgm)

    assert metrics["total_paras"] == 2
    assert metrics["dead_paras"] == {"100-DEAD"}


def test_sequence_numbered_source(tmp_path):
    """Defect 4: cols 1-6 may hold a sequence field; paragraphs and COPY still match."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "PARMS.cpy").write_text("       01 PARM-A PIC X.\n", encoding="utf-8")
    pgm = repo / "SEQPGM.cbl"
    pgm.write_text(
        "000100 DATA DIVISION.\n"
        "R2     COPY PARMS.\n"
        "000300 PROCEDURE DIVISION.\n"
        "000400 MAIN-PARA.\n"
        "000500     DISPLAY 'HI'.\n"
        "000600 DEAD-PARA.\n"
        "000700     DISPLAY 'BYE'.\n",
        encoding="utf-8",
    )

    metrics = graveyard_module.x_ray_dead_code(pgm)

    assert metrics["dead_paras"] == {"DEAD-PARA"}
    assert metrics["orphaned_vars"] == {"PARM-A"}, "The sequence-numbered COPY was not resolved"


def test_programs_are_never_inlined_as_copybooks(tmp_path):
    """Defect 2: `COPY ACCTCTRL` must resolve to the copybook, not to the program
    ACCTCTRL.cbl that shares its stem (CBSA's BANKDATA shape)."""
    repo = tmp_path / "cbsa"
    (repo / "cobol_src").mkdir(parents=True)
    (repo / "cobol_copy").mkdir()
    (repo / "cobol_src" / "ACCTCTRL.cbl").write_text(
        _proc("       PROGRAM-ID. ACCTCTRL.", "       OTHER-PROGRAM-PARA.", "           GOBACK."),
        encoding="utf-8",
    )
    (repo / "cobol_copy" / "ACCTCTRL.cpy").write_text("       01 ACCOUNT-CONTROL PIC X.\n", encoding="utf-8")
    pgm = repo / "cobol_src" / "BANKDATA.cbl"
    pgm.write_text(
        "       DATA DIVISION.\n"
        "           COPY ACCTCTRL.\n"
        "       PROCEDURE DIVISION.\n"
        "       A010.\n"
        "           MOVE 1 TO ACCOUNT-CONTROL.\n",
        encoding="utf-8",
    )

    resolved = graveyard_module.resolve_copybooks(pgm.read_text(), pgm, copybook_root=repo)
    assert "ACCOUNT-CONTROL" in resolved
    assert "OTHER-PROGRAM-PARA" not in resolved

    metrics = graveyard_module.x_ray_dead_code(pgm, copybook_root=repo)
    assert metrics["dead_paras"] == set(), "The entry paragraph A010 must never be dead"
    assert metrics["orphaned_vars"] == set()


def test_copybook_lookup_searches_the_repo_and_prefers_the_nearest(tmp_path):
    """Defect 3: copybooks live outside the program's directory; with duplicates
    (zopeneditor's COPYBOOK/ vs multiroot/copybooks/) the nearest one wins."""
    repo = tmp_path / "zopen"
    for d in ("COBOL", "COPYBOOK", "multiroot/cobol", "multiroot/copybooks"):
        (repo / d).mkdir(parents=True)
    (repo / "COPYBOOK" / "CUSTCOPY.cpy").write_text("       01 TOP-LEVEL-FIELD PIC X.\n", encoding="utf-8")
    (repo / "multiroot" / "copybooks" / "CUSTCOPY.cpy").write_text(
        "       01 MULTIROOT-FIELD PIC X.\n", encoding="utf-8"
    )
    top = repo / "COBOL" / "SAM1.cbl"
    nested = repo / "multiroot" / "cobol" / "SAM1.cbl"
    for pgm in (top, nested):
        pgm.write_text("       COPY CUSTCOPY.\n", encoding="utf-8")

    assert "TOP-LEVEL-FIELD" in graveyard_module.resolve_copybooks(top.read_text(), top, copybook_root=repo)
    assert "MULTIROOT-FIELD" in graveyard_module.resolve_copybooks(nested.read_text(), nested, copybook_root=repo)


def test_procedure_division_using_operand_is_not_the_entry(tmp_path):
    """CBSA shape: `PROCEDURE DIVISION USING PARM-BUFFER.` The operand is not a
    paragraph, so the entry is A010 and it is never dead."""
    pgm = tmp_path / "BANKDATA.cbl"
    pgm.write_text(
        "       DATA DIVISION.\n"
        "       PROCEDURE DIVISION USING PARM-BUFFER.\n"
        "       PREMIERE SECTION.\n"
        "       A010.\n"
        "           PERFORM B020.\n"
        "       B020.\n"
        "           GOBACK.\n",
        encoding="utf-8",
    )

    metrics = graveyard_module.x_ray_dead_code(pgm)

    assert metrics["total_paras"] == 2
    assert metrics["dead_paras"] == set()
