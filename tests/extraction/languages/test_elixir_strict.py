"""
Elixir (#6572): `.ex` / `.exs` / `mix.exs` are mapped, `def` / `defp` / `defmacro` units are sliced by their
`do` ... `end` pair (a `do:` one-line body opens no scope), and `use` / `import` / `alias` / `require` name
their module in `_dependency_capture`. Every snippet is a real Elixir shape.
"""

import sys
from pathlib import Path

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.standards.language_lens import LanguageDetector
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune_all  # noqa: E402 # type: ignore

EX = LANGUAGE_DEFINITIONS["elixir"]
RULES = EX["rules"]

SRC = (
    "defmodule Doom.Player do\n"
    "  use GenServer\n"
    "  alias Doom.{Map, Thing}\n"
    "  import Enum, only: [map: 2]\n"
    "  require Logger\n"
    "\n"
    "  def start_link(opts) do\n"
    "    GenServer.start_link(__MODULE__, opts)\n"
    "  end\n"
    "\n"
    "  defp tick(state, dt) when dt > 0 do\n"
    "    if state.hp > 0 do\n"
    "      %{state | hp: state.hp - 1}\n"
    "    else\n"
    "      state\n"
    "    end\n"
    "  end\n"
    "\n"
    "  def handle_call(:hp, _from, state), do: {:reply, state.hp, state}\n"
    "\n"
    "  def total(items) do\n"
    "    Enum.map(items, fn x -> x * 2 end)\n"
    "  end\n"
    "end\n"
)


def _route(name: str, content: str) -> str:
    return LanguageDetector(LANGUAGE_DEFINITIONS, {}).focus(name, content)[0]


def _splice(content: str) -> dict:
    return StructuralExtractor("elixir", LANGUAGE_DEFINITIONS).splice(content, "")


def _hits(rule: str, content: str) -> list[str]:
    return [m.group(0).strip() for m in RULES[rule].finditer(content)]


def test_elixir_extensions_and_manifests_route_to_elixir():
    assert _route("player.ex", SRC) == "elixir"
    assert _route("test/player_test.exs", SRC) == "elixir"
    assert _route("mix.exs", SRC) == "elixir"


def test_def_defp_and_one_line_do_colon_are_functions():
    names = sorted(f["name"] for f in _splice(SRC)["functions"] if f["name"] != "__global_context__")
    assert names == ["handle_call", "start_link", "tick", "total"]


def test_function_spans_follow_do_end_and_do_colon_is_one_line():
    fns = {f["name"]: (f["start_line"], f["end_line"]) for f in _splice(SRC)["functions"]}
    assert fns["start_link"] == (7, 9)
    # the nested `if ... do` / `fn ... end` blocks close inside their unit
    assert fns["tick"] == (11, 17)
    assert fns["handle_call"] == (19, 19)
    assert fns["total"] == (21, 23)


def test_modules_are_found():
    assert _hits("class_start", SRC) == ["defmodule Doom.Player"]
    assert _hits("class_start", "defprotocol Size do\nend\ndefimpl Size, for: List do\nend\n") == [
        "defprotocol Size",
        "defimpl Size",
    ]


def test_arguments_are_counted():
    fns = {f["name"]: f["args"] for f in _splice(SRC)["functions"]}
    assert fns["start_link"] == 1
    assert fns["tick"] == 2
    assert fns["handle_call"] == 3


def test_dependencies_capture_the_module():
    caps = [m.group(1) for m in RULES["_dependency_capture"].finditer(SRC)]
    assert caps == ["GenServer", "Doom", "Enum", "Logger"]


def test_a_do_colon_keyword_arg_does_not_unbalance_the_next_unit():
    src = "defmodule M do\n  def a(x), do: x\n  def b(y) do\n    y\n  end\nend\n"
    fns = {f["name"]: (f["start_line"], f["end_line"]) for f in _splice(src)["functions"]}
    assert fns["a"] == (2, 2)
    assert fns["b"] == (3, 5)


def test_string_to_atom_is_a_safety_bypass():
    assert _hits("safety_bypasses", "String.to_atom(input)\n") == ["String.to_atom("]


def test_every_rule_survives_pathological_input():
    payloads = [
        "def " + "a" * 20000 + "\n",
        "def f(" + "a, " * 4000 + "\n",
        "def f(" + "(" * 5000 + "\n",
        "defmodule " + "A." * 4000 + "\n",
        "alias " + "A." * 5000 + "\n",
        "@spec f(" + "list(" * 3000 + "\n",
        "  " * 5000 + "fn " + "a," * 3000 + "\n",
        "# " + "def " * 5000 + "\n",
    ]
    pairs = [(rule, p) for rule in [r for r in RULES.values() if hasattr(r, "finditer")] for p in payloads]
    assert_redos_immune_all(pairs)
