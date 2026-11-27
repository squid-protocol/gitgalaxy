"""#9303: OCaml `(* ... *)` block comments (nested, doc, around strings) go to the comment stream, not the code stream."""

import pytest

from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)


def _streams(src: str):
    st = _PRISM.split_streams(src, "ocaml")
    return st["code_stream"], st["comment_stream"]


def test_ocaml_uses_the_ml_family():
    assert LANGUAGE_DEFINITIONS["ocaml"]["lexical_family"] == "recursive_block_ml"


def test_single_and_multiline_comment_leave_code():
    code, comment = _streams("(* if x then y *)\nlet f x =\n  (* match\n  z *)\n  x\n")
    assert "if x then y" not in code and "match" not in code
    assert "let f x" in code
    assert "if x then y" in comment


def test_nested_comments_close_on_the_matching_delimiter():
    code, comment = _streams("(* outer (* inner if *) still_outer while *)\nlet g y = y\n")
    assert "still_outer" not in code and "while" not in code
    assert "still_outer" in comment
    assert "let g y" in code


def test_doc_comment_goes_to_comment_stream():
    code, comment = _streams("(** Doc: returns if *)\nval f : int -> int\n")
    assert "Doc" not in code
    assert "Doc" in comment
    assert "val f" in code


def test_comment_opener_inside_a_string_is_code():
    code, _ = _streams('let s = "(* not a comment"\nlet t = 1 (* real *)\n')
    assert '"(* not a comment"' in code
    assert "let t = 1" in code and "real" not in code


def test_comment_closer_inside_a_string_does_not_end_the_comment():
    code, _ = _streams('(* a "*)" if *)\nlet u = 2\n')
    assert "if" not in code
    assert "let u = 2" in code


def test_quoted_string_and_char_literal_shield():
    code, _ = _streams("let q = {id|(* keep |id}\nlet c = '\"'\nlet d = 3 (* gone *)\n")
    assert "(* keep" in code
    assert "let d = 3" in code and "gone" not in code


def test_type_variable_quote_is_not_a_char_literal():
    code, _ = _streams("let id : 'a -> 'a = fun x -> x (* c *)\n")
    assert "fun x -> x" in code and " c " not in code


def test_line_count_is_preserved():
    src = "(* a\nb\nc *)\nlet z = 1\n"
    code, _ = _streams(src)
    assert code.count("\n") == src.count("\n")
    assert code.splitlines()[3].startswith("let z")


@pytest.mark.parametrize("n", [3000])
def test_unterminated_comment_is_linear(n):
    code, _ = _streams("let a = 1\n(* " + "(* " * n + "\n")
    assert "let a = 1" in code


def test_positional_stream_holds_only_the_comment():
    src = 'let s = "(*" (* c *) let t = 1\n(* d\n e *)\n'
    pos = _PRISM.split_positional_comment_stream(src, "ocaml")
    assert "(* c *)" in pos and "(* d" in pos
    assert "let" not in pos and '"(*"' not in pos
    assert pos.count("\n") == src.count("\n")
