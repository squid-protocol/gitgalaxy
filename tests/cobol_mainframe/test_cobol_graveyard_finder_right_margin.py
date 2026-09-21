from pathlib import Path

import gitgalaxy.tools.cobol_to_cobol.cobol_graveyard_finder as graveyard_module


def test_fixed_format_right_margin_sequence_numbers_are_ignored(tmp_path: Path):
    """Cols 73-80 are sequence digits, not part of the COBOL header text."""
    proc_div = (
        "       DATA DIVISION.\n"
        "       PROCEDURE DIVISION.\n"
        "       000-MAIN.\n"
        "           DISPLAY 'X'.\n"
        "       100-OK.                                              12345678\n"
        "           DISPLAY 'Y'.\n"
    )

    assert graveyard_module.unit_headers(proc_div.split("PROCEDURE DIVISION", 1)[1]) == [
        "000-MAIN",
        "100-OK",
    ]

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "COPYBOOK.CPY").write_text("       01 COPY-ITEM PIC X.\n", encoding="utf-8")
    source = repo / "PROG.CBL"
    source.write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. PROG.\n"
        "       DATA DIVISION.\n"
        "      COPY COPYBOOK.                                            56789012\n"
        "       PROCEDURE DIVISION.\n"
        "       P000.\n"
        "           GOBACK.\n",
        encoding="utf-8",
    )

    expanded = graveyard_module.resolve_copybooks(source.read_text(encoding="utf-8", errors="ignore").upper(), source, repo)
    assert "01 COPY-ITEM PIC X" in expanded
