"""Verify terminal GO TO targets stay in --style structured (#8521)."""

from __future__ import annotations

from pathlib import Path

from gitgalaxy.tools.cobol_to_java.det import program as P


def test_terminal_goto_goback_stays_structured(tmp_path: Path) -> None:
    cbl = tmp_path / "TERM01.cbl"
    cbl.write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. TERM01.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01 WS-OK PIC 9 VALUE 0.\n"
        "       PROCEDURE DIVISION.\n"
        "       0000-MAIN.\n"
        "           IF WS-OK = 0\n"
        "               GO TO 9000-ABORT\n"
        "           END-IF\n"
        "           MOVE 1 TO WS-OK\n"
        "           GOBACK.\n"
        "       9000-ABORT.\n"
        "           MOVE 9 TO WS-OK\n"
        "           GOBACK.\n",
        encoding="utf-8",
    )

    res = P.translate(cbl, [], "public class Term01Service {}", "com.example", [], None, "structured", True, True)
    assert "private int p0()" not in res.java
    assert "private void runAll()" in res.java
    assert "private void abort9000()" in res.java or "abort" in res.java.lower()
    assert "return GOTO |" not in res.java


def test_non_terminal_goto_stays_dispatch(tmp_path: Path) -> None:
    cbl = tmp_path / "LOOP01.cbl"
    cbl.write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. LOOP01.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01 WS-X PIC 9 VALUE 0.\n"
        "       PROCEDURE DIVISION.\n"
        "       0000-MAIN.\n"
        "           IF WS-X = 0\n"
        "               GO TO 1000-NEXT\n"
        "           END-IF\n"
        "           GOBACK.\n"
        "       1000-NEXT.\n"
        "           ADD 1 TO WS-X.\n",
        encoding="utf-8",
    )

    res = P.translate(cbl, [], "public class Loop01Service {}", "com.example", [], None, "structured", True, True)
    assert "private int p0()" in res.java
    assert "return GOTO | 1;" in res.java
