"""det keeps one Java method per COBOL paragraph and records the mapping, in every style (#8488).

The class: paragraph -> method provenance (`stats["paragraph_methods"]` plus a `/** NAME. */` Javadoc) is complete and
one-to-one for every input shape det accepts: dispatch / structured style, GO TO programs, PERFORM THRU, sections,
`*-EXIT` stubs, reserved-word names and a real CardDemo program.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

from gitgalaxy.tools.cobol_to_java.det import program as P

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from translation_fidelity import pair_program, parse_cobol_paragraphs, parse_java_methods

HEAD = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. DEMO01.\n       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n       01 WS-X PIC 9(4) VALUE 0.\n       PROCEDURE DIVISION.\n"
)

SHAPES = {
    "plain": (
        (
            "       0000-MAIN.\n           PERFORM 1100-SCREEN-INIT\n           PERFORM 1200-SETUP-VARS\n"
            "           PERFORM 1200-EXIT\n           GOBACK.\n"
            "       1100-SCREEN-INIT.\n           MOVE 1 TO WS-X.\n"
            "       1200-SETUP-VARS.\n           ADD 2 TO WS-X.\n"
            "       1200-EXIT.\n           EXIT.\n"
        ),
        ["0000-MAIN", "1100-SCREEN-INIT", "1200-SETUP-VARS", "1200-EXIT"],
    ),
    "goto": (
        (
            "       0000-MAIN.\n           GO TO 2000-NEXT.\n"
            "       1000-SKIPPED.\n           MOVE 9 TO WS-X.\n"
            "       2000-NEXT.\n           ADD 1 TO WS-X\n           GOBACK.\n"
        ),
        ["0000-MAIN", "1000-SKIPPED", "2000-NEXT"],
    ),
    "thru": (
        (
            "       0000-MAIN.\n           PERFORM 1000-A THRU 1000-EXIT\n           GOBACK.\n"
            "       1000-A.\n           ADD 1 TO WS-X.\n"
            "       1000-B.\n           ADD 2 TO WS-X.\n"
            "       1000-EXIT.\n           EXIT.\n"
        ),
        ["0000-MAIN", "1000-A", "1000-B", "1000-EXIT"],
    ),
    "sections": (
        (
            "       MAIN-SEC SECTION.\n       0000-MAIN.\n           PERFORM WORK-SEC\n           GOBACK.\n"
            "       WORK-SEC SECTION.\n       1000-A.\n           ADD 1 TO WS-X.\n"
            "       1000-B.\n           ADD 2 TO WS-X.\n"
        ),
        ["MAIN-SEC", "0000-MAIN", "WORK-SEC", "1000-A", "1000-B"],
    ),
    "reserved_names": (
        (
            "       0000-MAIN.\n           PERFORM CLASS\n           PERFORM STORE\n           GOBACK.\n"
            "       CLASS.\n           ADD 1 TO WS-X.\n"
            "       STORE.\n           ADD 2 TO WS-X.\n"
        ),
        ["0000-MAIN", "CLASS", "STORE"],
    ),
}


def _translate(tmp_path: Path, body: str, style: str):
    cbl = tmp_path / "DEMO01.cbl"
    cbl.write_text(HEAD + body)
    res = P.translate(cbl, [], "public class Demo01Service {}", "com.example", [], None, style, True, True)
    return cbl, res


@pytest.mark.parametrize("style", ["structured", "dispatch"])
@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_every_paragraph_has_one_method_and_a_javadoc(tmp_path: Path, shape: str, style: str) -> None:
    body, expected = SHAPES[shape]
    _, res = _translate(tmp_path, body, style)
    pmap = res.stats["paragraph_methods"]
    methods = list(pmap.values())
    assert len(methods) == len(set(methods)), "two paragraphs share a method"
    # the map holds the real paragraphs; a section header may or may not be one, but no real paragraph is lost
    real = [n for n in expected if not n.endswith("-SEC")]
    assert set(real) <= set(pmap)
    for para, meth in pmap.items():
        assert f"/** {para}. */" in res.java
        assert re.search(rf"private (?:void|int) {re.escape(meth)}\(\)", res.java), (para, meth)


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_the_map_names_the_same_paragraphs_in_both_styles(tmp_path: Path, shape: str) -> None:
    body, _ = SHAPES[shape]
    _, s = _translate(tmp_path, body, "structured")
    _, d = _translate(tmp_path, body, "dispatch")
    assert list(s.stats["paragraph_methods"]) == list(d.stats["paragraph_methods"])


def test_structured_javadoc_pairs_back_to_cobol(tmp_path: Path) -> None:
    body, _ = SHAPES["plain"]
    cbl, res = _translate(tmp_path, body, "structured")
    java_file = tmp_path / "Demo01Service.java"
    java_file.write_text(res.java)
    pairs = pair_program(parse_cobol_paragraphs(cbl), parse_java_methods(java_file))
    assert {p.cobol_para for p in pairs} == {"0000-MAIN", "1100-SCREEN-INIT", "1200-SETUP-VARS"}
    assert all(p.matched_by == "javadoc" for p in pairs)


def _carddemo(name: str) -> Path | None:
    root = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    if not root:
        return None
    p = Path(root) / "aws-mainframe-modernization-carddemo" / "app" / "cbl" / name
    return p if p.exists() else None


@pytest.mark.parametrize("name", ["COACTVWC.cbl", "COCRDLIC.cbl"])
def test_carddemo_program_keeps_every_paragraph(name: str) -> None:
    cbl = _carddemo(name)
    if cbl is None:
        pytest.skip("CardDemo corpus not available")
    app = cbl.parent.parent
    dirs = [d for d in (app / "cpy", app / "cpy-bms") if d.exists()]
    res = P.translate(cbl, dirs, "public class S {}", "x", [], None, "structured", True, True)
    pmap = res.stats["paragraph_methods"]
    declared = [p.name for p in parse_cobol_paragraphs(cbl)]
    assert declared
    assert set(declared) <= set(pmap), "a COBOL paragraph has no method (inlined or dropped)"
    assert len(set(pmap.values())) == len(pmap)
