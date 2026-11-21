# ruff: noqa: S101
"""#8863: the tree-sitter oracles written per language beyond the first six (C#, Kotlin, Swift, Scala; Ruby, PHP, Lua, shell).

Each case is one construct in one language: [language, source, function, oracle key, expected count], in family_oracle_cases.json. They were written
against each grammar and pin the readings the oracles make of the family contracts (an anonymous callable, a bitwise operator in operator position, a
handler is not a branch, a doc comment in the language's own style, ...). The scored numbers on real repositories are in tests/family_validity_baseline.json.
"""

import json
import sys
import textwrap
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS.parents[1]))
sys.path.insert(0, str(TOOLS))
import family_oracle as fo  # noqa: E402
import family_oracle_ts as ts  # noqa: E402

try:
    import tree_sitter_language_pack  # noqa: F401

    HAVE_TS = True
except ImportError:
    HAVE_TS = False
needs_ts = pytest.mark.skipif(not HAVE_TS, reason="tree_sitter_language_pack (the translator extra) is not installed")

FIXTURE = json.loads((TOOLS / "family_oracle_cases.json").read_text(encoding="utf-8"))
CASES = [tuple(c) for group in ("a", "b") for c in FIXTURE[group]]
LANGUAGES = ("csharp", "kotlin", "swift", "scala", "ruby", "php", "lua", "shell")


def _count(lang: str, src: str, name: str, key: str) -> int | None:
    oracle = ts.get_oracle(lang)
    index = oracle.index(textwrap.dedent(src))
    node = next((n for (nm, _ln), n in index.items() if nm == name), None)
    return None if node is None else oracle.count(node)[0].get(key, 0)


def test_the_eight_languages_are_registered_and_shell_is_the_bash_grammar():
    assert set(LANGUAGES) <= set(ts.languages())
    assert ts.get_oracle("shell") is ts.get_oracle("bash")
    assert ts.get_oracle("cobol") is None


def test_every_registered_language_has_the_same_families_the_tool_scores():
    for lang in LANGUAGES:
        columns = {f.column for f in ts.get_oracle(lang).families}
        assert {"struct_branch", "bitwise_ops", "state_print_hits"} <= columns, lang
        assert all(f.rule for f in ts.get_oracle(lang).families), (
            lang
        )  # each carries its contract key, so a result can be placed on the grid


def test_the_cases_cover_every_language_with_enough_depth():
    per = {lang: sum(1 for c in CASES if c[0] == lang) for lang in LANGUAGES}
    assert all(n >= 10 for n in per.values()), per
    assert len(CASES) >= 200


@needs_ts
@pytest.mark.parametrize(
    ("lang", "src", "name", "key", "want"), CASES, ids=[f"{c[0]}-{c[3]}-{i}" for i, c in enumerate(CASES)]
)
def test_oracle_reads_one_construct(lang, src, name, key, want):
    assert _count(lang, src, name, key) == want


@needs_ts
def test_unknown_language_is_still_refused(tmp_path):
    db = tmp_path / "x.db"
    db.write_bytes(b"")
    with pytest.raises(SystemExit, match="no oracle"):
        fo.get_oracle("cobol")


def test_grammar_names_fall_back_through_the_pack_s_renames(monkeypatch):
    """CI's language pack knows C# as `csharp`, this box's as `c_sharp`: the oracle tries each name a grammar has had."""
    seen = []

    class _Pack:
        @staticmethod
        def get_parser(name):
            seen.append(name)
            if name == "c_sharp":
                raise LookupError("Language 'c_sharp' is not in the download manifest")
            return f"parser:{name}"

    import types

    monkeypatch.setitem(sys.modules, "tree_sitter_language_pack", types.SimpleNamespace(get_parser=_Pack.get_parser))
    assert ts.get_parser("c_sharp") == "parser:csharp"
    assert seen == ["c_sharp", "csharp"]
    assert ts.get_parser("kotlin") == "parser:kotlin"  # a name with no aliases is tried as given
    with pytest.raises(LookupError):
        monkeypatch.setitem(
            sys.modules,
            "tree_sitter_language_pack",
            types.SimpleNamespace(get_parser=lambda n: (_ for _ in ()).throw(LookupError(n))),
        )
        ts.get_parser("c_sharp")
