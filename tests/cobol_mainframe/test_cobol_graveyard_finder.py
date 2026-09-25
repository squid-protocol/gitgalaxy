import sys
import time
from unittest.mock import patch

import pytest

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

    # Right-margin sequence field (cols 73-80) is ignored; paragraph and COPY names
    # still match even when the fixed-format tail carries an ID.
    pgm2 = repo / "SEQPGM2.cbl"
    pgm2.write_text(
        "000100 DATA DIVISION.\n"
        "R2     COPY PARMS.                                                      08490000\n"
        "000300 PROCEDURE DIVISION.\n"
        "000400 MAIN-PARA.                                                       08490000\n"
        "000500     DISPLAY 'HI'.                                                08490000\n"
        "000550     GOBACK.                                                      08490000\n"
        "000600 DEAD-PARA.                                                       08490000\n"
        "000700     DISPLAY 'BYE'.                                               08490000\n",
        encoding="utf-8",
    )

    metrics2 = graveyard_module.x_ray_dead_code(pgm2)
    assert metrics2["dead_paras"] == {"DEAD-PARA"}
    assert metrics2["orphaned_vars"] == {"PARM-A"}, "The right-margin sequence field was not ignored"


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
    (repo / "TAGCOPY.cpy").write_text("       01 TAG-BAL PIC 9(5).\n", encoding="utf-8")
    pgm = repo / "PGM.cbl"
    pgm.write_text(
        "       PROGRAM-ID. PGM.\n"
        "       WORKING-STORAGE SECTION.\n"
        "           COPY TAGCOPY REPLACING ==TAG-BAL== BY ==WS-CUST==.\n"
        "       PROCEDURE DIVISION.\n"
        "       A010.\n"
        "           MOVE 1 TO WS-CUST.\n",
        encoding="utf-8",
    )

    resolved = graveyard_module.resolve_copybooks(pgm.read_text(), pgm, copybook_root=repo)
    assert "01 WS-CUST" in resolved
    assert "01 TAG-BAL" not in resolved
    assert graveyard_module.x_ray_dead_code(pgm, copybook_root=repo)["orphaned_vars"] == set()


# ==============================================================================
# #3420: shapes the mainframe ground-truth census found (each from CardDemo/CBSA)
# ==============================================================================
def test_perform_after_end_perform_is_seen(tmp_path):
    """CardDemo COTRTLIC: `END-PERFORM` then `PERFORM 9450-CLOSE ...` read as a
    PERFORM of the word PERFORM, so the real target was reported dead."""
    assert (
        _dead(
            tmp_path,
            "       MAIN-PARA.",
            "           PERFORM UNTIL WS-X = 1",
            "              MOVE 1 TO WS-X",
            "           END-PERFORM",
            "           PERFORM CLOSE-PARA",
            "           GOBACK.",
            "       CLOSE-PARA.",
            "           DISPLAY 'C'.",
        )
        == set()
    )


def test_closed_if_before_a_terminal_does_not_fall_through(tmp_path):
    """`\\bIF\\b` counted inside `END-IF`: CBSA DELACC's A010 ends `... END-IF ...
    PERFORM GET-ME-OUT-OF-HERE.` and read as falling through into A999."""
    assert _dead(
        tmp_path,
        "       A010.",
        "           IF WS-X = 1",
        "              DISPLAY 'Y'",
        "           END-IF",
        "           GOBACK.",
        "       A999.",
        "           EXIT.",
    ) == {"A999"}


def test_a_terminal_sentence_before_the_last_ends_the_unit(tmp_path):
    """CBSA BNK1*: `EXEC CICS RETURN TRANSID(...) END-EXEC.` then an IF recovery
    sentence. Only the last sentence was tested, so A999 read as live."""
    assert _dead(
        tmp_path,
        "       A010.",
        "           EXEC CICS RETURN TRANSID('OCCS') RESP(WS-R) END-EXEC.",
        "           IF WS-R NOT = 0",
        "              DISPLAY 'FAIL'",
        "           END-IF.",
        "       A999.",
        "           EXIT.",
    ) == {"A999"}


def test_alter_target_is_reached(tmp_path):
    """CardDemo CBSTM03A reaches its 8200/8300/8400 paragraphs only through
    `ALTER 8100-FILE-OPEN TO PROCEED TO ...`."""
    assert (
        _dead(
            tmp_path,
            "       0000-START.",
            "           ALTER 8100-FILE-OPEN TO PROCEED TO 8200-OPEN",
            "           GO TO 8100-FILE-OPEN.",
            "       8100-FILE-OPEN.",
            "           GO TO 8100-FIRST.",
            "       8100-FIRST.",
            "           GOBACK.",
            "       8200-OPEN.",
            "           GOBACK.",
        )
        == set()
    )


def test_header_period_on_the_next_line(tmp_path):
    """CardDemo COTRTLIC `2000-SEND-MAP` / `     .`: the header was not a unit, so
    its THRU range's -EXIT read as dead."""
    pgm = tmp_path / "PGM.cbl"
    pgm.write_text(
        _proc(
            "       MAIN-PARA.",
            "           PERFORM 2000-SEND-MAP THRU 2000-SEND-MAP-EXIT",
            "           GOBACK.",
            "       2000-SEND-MAP",
            "            .",
            "           DISPLAY 'S'.",
            "       2000-SEND-MAP-EXIT.",
            "           EXIT.",
        ),
        encoding="utf-8",
    )
    assert graveyard_module.x_ray_dead_code(pgm)["dead_paras"] == set()
    names = graveyard_module.unit_headers(pgm.read_text().upper().split("PROCEDURE DIVISION", 1)[1])
    assert names == ["MAIN-PARA", "2000-SEND-MAP", "2000-SEND-MAP-EXIT"]


# ==============================================================================
# #3414: copy statements the fallback resolver missed
# ==============================================================================
@pytest.mark.parametrize(
    ("source", "member"),
    [
        ("       COPY 'CSSTRPFY'\n           .\n", "CSSTRPFY"),  # quoted, period on the next line
        ("       COPY CSUTLDPY\n           .\n", "CSUTLDPY"),
        ("206400 COPY 'CSSTRPFY'\n206500     .\n", "CSSTRPFY"),  # period after a sequence field
        ("       COPY DATETIME IN MYFILE.\n", "DATETIME"),  # IN library
        (
            "           COPY CSSETATY REPLACING\n"
            "             ==(TESTVAR1)== BY ==ACCT-STATUS==\n"
            "             ==(MAPNAME3)== BY ==CACTUPA== .\n",
            "CSSETATY",
        ),
        ("030400     EXEC SQL INCLUDE CSDB2RWY END-EXEC\n", "CSDB2RWY"),  # one-line SQL INCLUDE
        ("           EXEC SQL\n                INCLUDE AUTHFRDS\n           END-EXEC.\n", "AUTHFRDS"),
    ],
)
def test_copy_pattern_reads_every_copy_shape(source, member):
    matches = list(graveyard_module.COPY_PATTERN.finditer(source))
    assert [graveyard_module.copy_member(m) for m in matches] == [member]


def test_sql_include_resolves_to_a_dclgen_member(tmp_path):
    (tmp_path / "dcl").mkdir()
    (tmp_path / "dcl" / "AUTHFRDS.dcl").write_text("       01 DCL-AUTH.\n", encoding="utf-8")
    prog = tmp_path / "PROG.cbl"
    prog.write_text("       PROGRAM-ID. PROG.\n", encoding="utf-8")
    assert graveyard_module.find_copybook("AUTHFRDS", tmp_path, prog) == tmp_path / "dcl" / "AUTHFRDS.dcl"


def test_an_exhaustive_evaluate_that_always_transfers_does_not_fall_through():
    """#3510 (CICS GENAPP LGTESTP4): NO-ADD is one EVALUATE whose WHEN 70 and WHEN
    OTHER both GO TO ERROR-OUT, so NO-UPD after it is unreachable; without WHEN
    OTHER the EVALUATE can fall through."""
    from gitgalaxy.tools.cobol_to_cobol.cobol_graveyard_finder import _sentence_is_terminal

    assert _sentence_is_terminal(
        "EVALUATE CA-RETURN-CODE WHEN 70 MOVE 'X' TO A GO TO ERROR-OUT WHEN OTHER MOVE 'Y' TO A GO TO ERROR-OUT END-EVALUATE"
    )
    assert not _sentence_is_terminal("EVALUATE A WHEN 70 GO TO E1 WHEN 80 GO TO E2 END-EVALUATE")
    assert not _sentence_is_terminal("EVALUATE A WHEN 70 GO TO E1 WHEN OTHER MOVE 1 TO B END-EVALUATE")


def test_dsf_shapes_procedure_division_spacing_inline_header_and_at_end(tmp_path):
    """#3533 (navikt/DSF): `PROCEDURE        DIVISION.` is the header; `B.  DISPLAY ...`
    opens unit B with its first statement; `READ ... AT END GO TO X.` is conditional,
    so the paragraph after it is reached by fall-through."""
    pgm = tmp_path / "PLUKK.cbl"
    pgm.write_text(
        "\n".join(
            [
                "       IDENTIFICATION DIVISION.",
                "       PROGRAM-ID. PLUKK.",
                "       PROCEDURE        DIVISION.",
                "       LESE.",
                "           READ INN-FR AT END GO TO SLUTT.",
                "       TEST-TRKNR.",
                "           IF A = B GO TO B.",
                "           GO TO LESE.",
                "       B.  DISPLAY 'FEIL'.",
                "       SLUTT.",
                "           STOP RUN.",
            ]
        ),
        encoding="utf-8",
    )
    metrics = graveyard_module.x_ray_dead_code(pgm)
    assert metrics["total_paras"] == 4
    assert metrics["dead_paras"] == set()
    split = graveyard_module.split_procedure_division("X PROCEDURE    DIVISION. Y")
    assert split == ("X ", ". Y")
