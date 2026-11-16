"""Verify det preserves paragraph boundaries and emits provenance (#8488)."""

from __future__ import annotations

from pathlib import Path

from gitgalaxy.tools.cobol_to_java.det import program as P
from tests.tools.translation_fidelity import parse_cobol_paragraphs, parse_java_methods, pair_program


def test_det_emits_paragraph_provenance_and_map(tmp_path: Path) -> None:
    cbl = tmp_path / "DEMO01.cbl"
    cbl.write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. DEMO01.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01 WS-X PIC 9(4) VALUE 0.\n"
        "       PROCEDURE DIVISION.\n"
        "       0000-MAIN.\n"
        "           PERFORM 1100-SCREEN-INIT\n"
        "           PERFORM 1200-SETUP-VARS\n"
        "           PERFORM 1200-EXIT\n"
        "           GOBACK.\n"
        "       1100-SCREEN-INIT.\n"
        "           MOVE 1 TO WS-X.\n"
        "       1200-SETUP-VARS.\n"
        "           ADD 2 TO WS-X.\n"
        "       1200-EXIT.\n"
        "           EXIT.\n"
    )

    res = P.translate(
        cbl,
        [],
        "public class Demo01Service {}",
        "com.example",
        [],
        None,
        "structured",
        True,
        True,
    )
    pmap = res.stats["paragraph_methods"]
    assert set(pmap) == {"0000-MAIN", "1100-SCREEN-INIT", "1200-SETUP-VARS", "1200-EXIT"}
    for para, meth in pmap.items():
        assert f"/** {para}. */" in res.java
        assert f"private void {meth}()" in res.java

    java_file = tmp_path / "Demo01Service.java"
    java_file.write_text(res.java)
    pairs = pair_program(parse_cobol_paragraphs(cbl), parse_java_methods(java_file))
    assert {p.cobol_para for p in pairs} == {"0000-MAIN", "1100-SCREEN-INIT", "1200-SETUP-VARS"}
    assert all(p.matched_by == "javadoc" for p in pairs)
