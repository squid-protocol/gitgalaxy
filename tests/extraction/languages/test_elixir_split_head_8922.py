"""#8922: Elixir split function heads, `&&&` and the `fn ->` arrow."""

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

RULES = LANGUAGE_DEFINITIONS["elixir"]["rules"]


def _spans(src: str) -> dict[str, tuple[int, int]]:
    fns = StructuralExtractor("elixir", LANGUAGE_DEFINITIONS).splice(src, "")["functions"]
    return {f["name"]: (f["start_line"], f["end_line"]) for f in fns if f["name"] != "__global_context__"}


def _count(rule: str, text: str) -> int:
    return len(RULES[rule].findall(text))


def test_head_split_before_when_keeps_its_body():
    src = "defmodule M do\n  def wrapped(a, b)\n      when a > 1 and b > 2 do\n    a + b\n  end\nend\n"
    assert _spans(src)["wrapped"] == (2, 5)


def test_head_split_inside_the_parameter_list():
    src = "defmodule M do\n  def a(x,\n        y) do\n    x\n  end\nend\n"
    assert _spans(src)["a"] == (2, 5)


def test_when_guard_then_do_keyword_on_its_own_line():
    src = "defmodule M do\n  def b(x)\n      when x > 1,\n      do: x\n\n  def c(x) do\n    x\n  end\nend\n"
    spans = _spans(src)
    assert spans["b"] == (2, 4)
    assert spans["c"] == (6, 8)


def test_a_bodiless_protocol_def_stays_one_line():
    src = "defprotocol P do\n  def area(s)\n\n  def perim(s)\nend\n"
    spans = _spans(src)
    assert spans["area"] == (2, 2)
    assert spans["perim"] == (4, 4)


def test_bitwise_and_is_not_a_short_circuit_but_and_still_is():
    assert _count("short_circuit", "a &&& b") == 0
    assert _count("short_circuit", "a && b") == 1
    assert _count("short_circuit", "a && b &&& c") == 1


def test_fn_arrow_is_not_a_branch():
    assert _count("branch", "    f = fn y -> y end\n") == 0
    assert _count("branch", "    Enum.map(xs, fn x -> x * 2 end)\n") == 0


def test_case_arm_arrows_still_count():
    src = "    case x do\n      1 -> :a\n      2 -> :b\n    end\n"
    assert _count("branch", src) == 3  # `case` plus two arms


def test_type_spec_arrow_is_not_a_branch():
    assert _count("branch", "  @spec f((a -> b)) :: c\n") == 0
