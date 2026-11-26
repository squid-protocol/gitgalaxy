"""JavaScript keyword-family oracle after the #8868 doc pass: a doc above a wrapper counts as the function's doc."""

import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_language_pack")
sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
import family_oracle_ts


def _count(src, name, key="doc"):
    oracle = family_oracle_ts.get_oracle("javascript")
    index = oracle.index(textwrap.dedent(src))
    node = next(n for (nm, _line), n in index.items() if nm == name)
    return oracle.count(node)[0].get(key, 0)


@pytest.mark.parametrize(
    "src,name",
    [
        ("/** d */\nfunction f() {}\n", "f"),
        ("/** d */\nexport default function f(a) { return a; }\n", "f"),
        ("/** d */\nexport const g = (a) => a;\n", "g"),
        ("/** d */\nconst h = function (a) { return a; };\n", "h"),
        ("const o = {\n  /** d */\n  join: (a) => a,\n};\n", "join"),
        ("class C {\n  /** d */\n  run = (a) => a;\n}\n", "run"),
        ("/** d */\nC.prototype.emit = function (p) {};\n", "emit"),
        ("function K() {\n  /** d */\n  this.render = function (s) {};\n}\n", "render"),
    ],
)
def test_oracle_reads_a_doc_above_the_wrapper(src, name):
    assert _count(src, name) == 1


@pytest.mark.parametrize(
    "src,name",
    [
        ("// plain\nexport default function f() {}\n", "f"),
        ("/* block */\nconst h = function () {};\n", "h"),
        ("/** d */\n\n\nC.prototype.emit = function () {};\n", "emit"),
        ("const o = {\n  // note\n  join: (a) => a,\n};\n", "join"),
        ("const x = 1;\nfunction f() {}\n", "f"),
    ],
)
def test_oracle_does_not_read_a_plain_comment_or_a_distant_doc(src, name):
    assert _count(src, name) == 0


def test_a_doc_above_the_assignment_is_not_borrowed_by_the_left_side():
    # only the right-hand function of `a.b = function` is wrapped; a call argument keeps its own surroundings
    assert _count("/** d */\nregister(function cb() {});\n", "cb") == 0
