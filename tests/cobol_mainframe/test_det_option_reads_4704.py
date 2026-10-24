"""#4704 (verify): the det translator reads every compile option (and so DECIMAL-POINT's and the code page's
neighbours) through the one resolver, `compiler_options.effective_with_defaults` over `effective_options(...).layers`,
never through a reader of its own. DECIMAL-POINT IS COMMA is a SPECIAL-NAMES clause of the program (no option states
it), and the code page is the scan's recorded decode (`EngineCopies.pages`); neither is an option a second reader
could disagree with, and this test names every place a det module touches the option names."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gitgalaxy.core import compiler_options as co  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import program as det_program  # noqa: E402

DET = ROOT / "gitgalaxy" / "tools" / "cobol_to_java" / "det"
OPTION_NAMES = set(co.OPTION_TABLE) | set(co.DEFAULTS) | set(co.SEMANTIC_OPTIONS)
# the det readers of a compile option's value, each of which must resolve it through the one resolver
READERS = ("trunc_mode", "numproc_pfd", "arith_extend")


def _det_files() -> list[Path]:
    return sorted(DET.glob("*.py"))


def _option_subscripts(tree: ast.AST) -> list[tuple[int, str]]:
    """Lines where a det module reads `x["OPTION"]` / `x.get("OPTION")` for a compile-option name."""
    hits = []
    for node in ast.walk(tree):
        key = None
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
            key = node.slice.value
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            key = node.args[0].value
        if isinstance(key, str) and key in OPTION_NAMES and key not in ("BINARY", "DECIMAL"):
            hits.append((node.lineno, key))
    return hits


def test_no_det_module_parses_option_cards_itself():
    for path in _det_files():
        text = path.read_text(encoding="utf-8")
        assert "co._CARD" not in text and "_CARD.match" not in text, f"{path.name} reads CBL / PROCESS cards itself"
        assert "from gitgalaxy.core.compiler_options import _" not in text, f"{path.name} imports a private reader"


def test_option_values_are_read_only_in_the_resolver_backed_readers():
    """A det read of an option's value by name sits inside one of READERS, each calling effective_with_defaults."""
    for path in _det_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        allowed = set()
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef):
                calls = {
                    n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", "")
                    for n in ast.walk(fn)
                    if isinstance(n, ast.Call)
                }
                if "effective_with_defaults" in calls:
                    allowed.update(range(fn.lineno, (fn.end_lineno or fn.lineno) + 1))
        stray = [(ln, k) for ln, k in _option_subscripts(tree) if ln not in allowed]
        assert not stray, f"{path.name}: option read outside the resolver: {stray}"


@pytest.mark.parametrize("name", READERS)
def test_every_option_reader_calls_the_resolver(name):
    fn = getattr(det_program, name)
    assert "effective_with_defaults" in fn.__code__.co_names, f"{name} does not call effective_with_defaults"


def test_the_readers_follow_the_estate_layers_then_the_program_cards(tmp_path):
    src = tmp_path / "P.cbl"
    src.write_text("       IDENTIFICATION DIVISION.\n       PROGRAM-ID. P.\n", encoding="utf-8")
    assert det_program.trunc_mode(src) == "STD"
    assert det_program.trunc_mode(src, ["TRUNC(BIN)"]) == "BIN"
    assert det_program.numproc_pfd(src, ["NUMPROC(PFD)"]) is True
    assert det_program.arith_extend(src, ["ARITH(EXTEND)"]) is True
    card = tmp_path / "Q.cbl"
    card.write_text("       CBL TRUNC(OPT)\n       IDENTIFICATION DIVISION.\n       PROGRAM-ID. Q.\n", encoding="utf-8")
    assert det_program.trunc_mode(card, ["TRUNC(BIN)"]) == "OPT"  # the program's own card is the last layer


def test_decimal_point_is_a_program_clause_not_an_option():
    assert "DECIMAL-POINT" not in co.OPTION_TABLE and "DECIMAL" not in co.OPTION_TABLE
