"""Tests for tests/tools/translation_fidelity.py (#7532)."""

from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from translation_fidelity import evaluate_fidelity, main


def test_translation_fidelity_beats_shuffled_and_unrelated_controls(tmp_path: Path) -> None:
    cbl_dir = tmp_path / "cobol"
    java_dir = tmp_path / "java"
    cbl_dir.mkdir()
    java_dir.mkdir()

    (cbl_dir / "PROG1.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. PROG1.\n"
        "       PROCEDURE DIVISION.\n"
        "       0000-MAIN.\n"
        "           IF WS-FLAG = 'Y'\n"
        "               PERFORM 1000-CHECK\n"
        "           ELSE\n"
        "               PERFORM 2000-CLOSE\n"
        "           END-IF\n"
        "           GOBACK.\n"
        "       1000-CHECK.\n"
        "           IF WS-AMT > 0\n"
        "               IF WS-STAT = 'A'\n"
        "                   ADD 1 TO WS-CNT\n"
        "               END-IF\n"
        "           END-IF.\n"
        "       2000-CLOSE.\n"
        "           MOVE 'N' TO WS-FLAG.\n"
    )

    (java_dir / "Prog1Service.java").write_text(
        "package com.example;\n"
        "public class Prog1Service {\n"
        "    /** 0000-MAIN. */\n"
        "    private void mainTask() {\n"
        "        if (wsFlag.equals(\"Y\")) {\n"
        "            check();\n"
        "        } else {\n"
        "            closeOut();\n"
        "        }\n"
        "        return;\n"
        "    }\n"
        "    /** 1000-CHECK. */\n"
        "    private void check() {\n"
        "        if (wsAmt > 0) {\n"
        "            if (wsStat.equals(\"A\")) {\n"
        "                wsCnt += 1;\n"
        "            }\n"
        "        }\n"
        "    }\n"
        "    /** 2000-CLOSE. */\n"
        "    private void closeOut() {\n"
        "        wsFlag = \"N\";\n"
        "    }\n"
        "}\n"
    )

    (cbl_dir / "PROG2.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. PROG2.\n"
        "       PROCEDURE DIVISION.\n"
        "       1000-STEP.\n"
        "           MOVE 1 TO WS-NUM.\n"
    )
    (java_dir / "Prog2Service.java").write_text(
        "package com.example;\n"
        "public class Prog2Service {\n"
        "    /** 1000-STEP. */\n"
        "    private void step() {\n"
        "        wsNum = 1;\n"
        "    }\n"
        "}\n"
    )

    res = evaluate_fidelity(cbl_dir, java_dir, draws=20, seed=1)
    assert res["evaluated_programs"] == 2
    assert res["total_paired"] == 4
    assert res["observed_fidelity"] > res["shuffled_null"]
    assert res["observed_fidelity"] > res["unrelated_null"]
    assert res["gap_vs_shuffled"] > 0
    assert res["gap_vs_unrelated"] > 0


def test_translation_fidelity_uses_traceability_json(tmp_path: Path) -> None:
    cbl_dir = tmp_path / "cobol"
    java_dir = tmp_path / "java"
    cbl_dir.mkdir()
    java_dir.mkdir()

    (cbl_dir / "BILL01.cbl").write_text(
        "       PROCEDURE DIVISION.\n"
        "       1000-PAY.\n"
        "           IF WS-OK = 1\n"
        "               MOVE 0 TO WS-ERR\n"
        "           END-IF.\n"
    )
    (java_dir / "Bill01Service.java").write_text(
        "public class Bill01Service {\n"
        "    public void processPayment() {\n"
        "        if (wsOk == 1) {\n"
        "            wsErr = 0;\n"
        "        }\n"
        "    }\n"
        "}\n"
    )
    trace = tmp_path / "traceability.json"
    trace.write_text(json.dumps({
        "artifacts": [{
            "symbol": "Bill01Service#processPayment",
            "facts": [{"paragraph": "1000-PAY"}],
        }]
    }))

    rc = main([
        "--cobol-dir", str(cbl_dir),
        "--java-dir", str(java_dir),
        "--traceability", str(trace),
    ])
    assert rc == 0
