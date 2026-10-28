"""#6266: the Doomsday oracle reads `#if 0` text as preprocessor ("macro"), not as a call the engine invented."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "doom_speedrun"))

import callgraph_oracle as co  # noqa: E402


def test_dead_branches_are_blanked_and_returned_separately():
    text, dead = co._split_dead_branches("a();\n#if 0\nold();\n#if X\nmid();\n#endif\nolder();\n#endif\nb();\n")
    assert "old()" not in text and "older()" not in text and "a();" in text and "b();" in text
    assert any("old()" in d and "older()" in d for d in dead)


def test_a_logical_operator_in_template_looking_arguments_is_no_call():
    tree = co._parser("cpp").parse(b"void f() { if (d < e || d > (3 - e)) { go(); } }")
    body = co.Body(co.function_nodes(tree)[0])
    assert "d" not in body.calls and "go" in body.calls
