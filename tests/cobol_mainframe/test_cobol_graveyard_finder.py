import sys
import time
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
        "           GOBACK.\n"  # Terminal: the main flow never falls into what follows
        "       USED-PARA.\n"  # Reached via PERFORM
        "           DISPLAY USED-VAR.\n"
        "       DEAD-PARA.\n"  # Unreachable (Phantom)
        "           DISPLAY 'HELLO'.\n"
        "       DEAD-EXIT.\n"  # Only reachable by falling out of DEAD-PARA: dead too
        "           EXIT.\n"
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
    # No *-EXIT exemption: an EXIT paragraph is dead when nothing reaches it
    # (the answer key counts it as trivial dead code, #3203).
    assert "DEAD-EXIT" in metrics["dead_paras"]

    # 3. Math (1 orphaned var + 2 dead paras * 10 lines = 21 LOC saved)
    assert metrics["loc_saved"] == 21


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
        "       DATA DIVISION.\n       PROCEDURE DIVISION.\n       MAIN.\n           GOBACK.\n       DEAD-P.\n",
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
        "000550     GOBACK.\n"
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

    assert metrics["total_paras"] == 3  # PREMIERE SECTION, A010, B020
    assert metrics["dead_paras"] == set()


# ==============================================================================
# #3203 defect 5: the SECTION model and reachability
# ==============================================================================
def _dead(tmp_path, *body):
    pgm = tmp_path / "PGM.cbl"
    pgm.write_text(_proc(*body), encoding="utf-8")
    return graveyard_module.x_ray_dead_code(pgm)["dead_paras"]


def test_performing_a_section_reaches_its_paragraphs_by_fall_through(tmp_path):
    """CBSA's PREMIERE SECTION shape: a PERFORMed section runs to its last paragraph."""
    assert _dead(
        tmp_path,
        "       PREMIERE SECTION.",
        "       A010.",
        "           PERFORM WORK-SECTION.",
        "           GOBACK.",
        "       WORK-SECTION SECTION.",
        "       W010.",
        "           DISPLAY 'ONE'.",
        "       W020.",
        "           DISPLAY 'TWO'.",
        "       W999.",
        "           EXIT.",
        "       UNUSED SECTION.",
        "       U010.",
        "           DISPLAY 'NEVER'.",
    ) == {"UNUSED", "U010"}


def test_perform_thru_and_go_to(tmp_path):
    assert _dead(
        tmp_path,
        "       MAIN-PARA.",
        "           PERFORM P1 THRU P1-EXIT.",
        "           GO TO FINISH.",
        "       P1.",
        "           DISPLAY 'P1'.",
        "       P1-MIDDLE.",
        "           DISPLAY 'IN THE RANGE'.",
        "       P1-EXIT.",
        "           EXIT.",
        "       ORPHAN.",
        "           DISPLAY 'NEVER'.",
        "       FINISH.",
        "           STOP RUN.",
    ) == {"ORPHAN"}


def test_conditional_transfer_still_falls_through(tmp_path):
    """A GOBACK inside an unterminated IF is conditional: the next paragraph is live."""
    assert _dead(
        tmp_path,
        "       MAIN-PARA.",
        "           IF A = B",
        "              GOBACK.",
        "       NEXT-PARA.",
        "           GOBACK.",
        "       DEAD-PARA.",
        "           DISPLAY 'NEVER'.",
    ) == {"DEAD-PARA"}


def test_perform_of_a_range_that_never_returns_is_terminal(tmp_path):
    """CBSA shape: `PERFORM GET-ME-OUT-OF-HERE.` where that section RETURNs, so the
    unit after the PERFORM is not reached by fall-through."""
    assert _dead(
        tmp_path,
        "       MAIN-PARA.",
        "           PERFORM GET-ME-OUT-OF-HERE.",
        "       AFTER-PARA.",
        "           DISPLAY 'NEVER'.",
        "       GET-ME-OUT-OF-HERE SECTION.",
        "       GMOFH010.",
        "           EXEC CICS RETURN",
        "           END-EXEC.",
    ) == {"AFTER-PARA"}


def test_cics_handle_labels_and_comments(tmp_path):
    """A HANDLE ABEND LABEL target is reached by CICS itself; a PERFORM in a comment
    line or inside a literal reaches nothing."""
    assert _dead(
        tmp_path,
        "       MAIN-PARA.",
        "           EXEC CICS HANDLE ABEND LABEL(ABEND-HANDLING)",
        "           END-EXEC.",
        "           DISPLAY 'PERFORM COMMENTED-OUT'.",
        "      *    PERFORM COMMENTED-OUT.",
        "           GOBACK.",
        "       ABEND-HANDLING.",
        "           GOBACK.",
        "       COMMENTED-OUT.",
        "           DISPLAY 'NEVER'.",
    ) == {"COMMENTED-OUT"}


# ==============================================================================
# #3222: the REPLACING pair scan starts only at a token boundary
# ==============================================================================
def test_replacing_pairs_are_linear_in_the_clause_length():
    """Without the boundary lookbehind, every position inside a long name is a
    candidate start that consumes the rest of the name before failing on the
    required `BY`. 20k name characters cost 10s before, ~1ms after."""
    start = time.perf_counter()
    pairs = graveyard_module._REPLACING_PAIR.findall("A" * 20000)
    elapsed = time.perf_counter() - start

    assert pairs == []
    assert elapsed < 5.0, f"REPLACING pair scan took {elapsed:.2f}s on a 20k-character name"


def test_replacing_pairs_are_unchanged_by_the_boundary_anchor():
    """The lookbehind captures the same pairs: a name run is greedy and cannot stop
    inside a token, so a mid-token start would report the same two names anyway."""
    clause = " ==TAG== BY ==WS-CUST== LEADING BY TRAILING ==A-1== BY ==B_2== "

    assert graveyard_module._REPLACING_PAIR.findall(clause) == [
        ("TAG", "WS-CUST"),
        ("LEADING", "TRAILING"),
        ("A-1", "B_2"),
    ]
    # Pre-existing and unchanged: `:` is outside the name class, so a `:TAG:`
    # pseudo-text name matches neither the old pattern nor this one.
    assert graveyard_module._REPLACING_PAIR.findall("==:TAG:== BY ==WS-CUST==") == []


def test_replacing_clause_still_substitutes_into_the_copybook(tmp_path):
    """End to end: the extracted pair renames the whole token, so the aliased field
    is the one the dead-code X-ray sees referenced."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "TAGCOPY.cpy").write_text("       01 TAG-BALANCE PIC 9(5).\n", encoding="utf-8")
    pgm = repo / "PGM.cbl"
    pgm.write_text(
        "       PROGRAM-ID. PGM.\n"
        "       WORKING-STORAGE SECTION.\n"
        "           COPY TAGCOPY REPLACING ==TAG-BALANCE== BY ==WS-CUST-BALANCE==.\n"
        "       PROCEDURE DIVISION.\n"
        "       A010.\n"
        "           MOVE 1 TO WS-CUST-BALANCE.\n",
        encoding="utf-8",
    )

    resolved = graveyard_module.resolve_copybooks(pgm.read_text(), pgm, copybook_root=repo)
    assert "01 WS-CUST-BALANCE" in resolved
    assert "01 TAG-BALANCE" not in resolved
    assert graveyard_module.x_ray_dead_code(pgm, copybook_root=repo)["orphaned_vars"] == set()
