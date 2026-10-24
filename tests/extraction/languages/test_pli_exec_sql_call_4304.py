"""#4304 (PL/I side): `EXEC SQL CALL proc;` is a Db2 stored-procedure call, not a PL/I CALL. Both PL/I CALL
readers -- mainframe_boundary's call sites (call_site_data) and the calls_out rule (calls_out_to) -- scanned
EXEC commands too, so `EXEC SQL CALL MYSCHEMA.GETCUST (:A);` became a call of an entry named `MYSCHEMA`.
A CALL inside any `EXEC <word> ... ;` command now belongs to that command; sql_statement_data keeps it."""

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.mainframe_boundary import extract_boundary
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)

SRC = """\
 T: PROC OPTIONS(MAIN);
   DCL A CHAR(4);
   EXEC SQL CALL MYSCHEMA.GETCUST (:A);
   EXEC SQL
      CALL UPDPROC;
   EXEC CICS LINK PROGRAM('CICSPGM');
   CALL REALSUB(A);
   EXEC SQL COMMIT;
   CALL AFTERSUB;
 END T;
"""


def test_boundary_records_no_pli_call_inside_exec_command():
    code = _PRISM.split_streams(SRC, "pli")["code_stream"]
    b = extract_boundary("pli", code)
    assert sorted((c["verb"], c["operand"]) for c in b["calls"]) == [
        ("CALL", "AFTERSUB"),
        ("CALL", "REALSUB"),
        ("LINK", "CICSPGM"),
    ]
    assert [s["verb"] for s in b["sql_statements"]][:2] == ["CALL", "CALL"]


def test_calls_out_skips_exec_commands():
    st = _PRISM.split_streams(SRC, "pli")
    out = StructuralExtractor("pli", LANGUAGE_DEFINITIONS).splice(
        code_stream=st["code_stream"],
        comment_stream=st["comment_stream"],
        raw_content=SRC,
        positional_comment_stream=_PRISM.split_positional_comment_stream(SRC, "pli"),
    )
    callees = [c for f in out["functions"] for c in f["calls_out_to"]]
    assert "REALSUB" in callees and "AFTERSUB" in callees
    assert not {"MYSCHEMA", "UPDPROC"} & set(callees)


def test_unterminated_exec_masks_nothing_beyond_the_bound():
    src = " T: PROC;\n EXEC SQL CALL X\n" + "   A = 1;\n" * 5 + " CALL REALSUB;\n END T;\n"
    code = _PRISM.split_streams(src, "pli")["code_stream"]
    ops = [c["operand"] for c in extract_boundary("pli", code)["calls"]]
    assert "REALSUB" in ops
