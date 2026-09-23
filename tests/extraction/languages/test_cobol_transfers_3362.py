"""#3362: COBOL GO TO is an unconditional transfer, not a call (calls_out contract C4).
It leaves calls_out_to and is recorded as transfers_to, so the paragraph it
reaches is still reached."""

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_SRC = """       IDENTIFICATION DIVISION.
       PROGRAM-ID. P.
       PROCEDURE DIVISION.
       MAIN-PARA.
           PERFORM SUB-PARA.
           IF X GO TO EXIT-PARA.
           go to exit-para.
           EXEC SQL WHENEVER SQLERROR GO TO ERR-PARA END-EXEC.
       SUB-PARA.
           GO TO SUB-PARA.
       EXIT-PARA.
           STOP RUN.
"""


def _nodes():
    return {f["name"]: f for f in StructuralExtractor("cobol", LANGUAGE_DEFINITIONS).splice(_SRC, "")["functions"]}


def test_go_to_is_a_transfer_not_a_call():
    main = _nodes()["MAIN-PARA"]
    assert main["calls_out_to"] == ["SUB-PARA"]
    # case-distinct spellings are kept as written; WHENEVER ... GO TO is a handler
    assert main["transfers_to"] == ["EXIT-PARA", "exit-para"]


def test_a_jump_to_its_own_paragraph_is_a_loop_not_an_edge():
    assert _nodes()["SUB-PARA"]["transfers_to"] == []


def test_other_languages_record_no_transfers():
    nodes = StructuralExtractor("c", LANGUAGE_DEFINITIONS).splice("void f(void) {\n  goto out;\nout:\n  g();\n}\n", "")
    assert all(f.get("transfers_to") == [] for f in nodes["functions"])
