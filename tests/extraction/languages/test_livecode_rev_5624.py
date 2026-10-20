"""`.rev` is LiveCode only on content (#5624): DOOM-FX's `bank00.a.rev` build counters are not stacks."""

import pytest

from gitgalaxy.standards.language_lens import LanguageDetector
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS, LENS_CONFIG


def _lang(path, text):
    return LanguageDetector(LANGUAGE_DEFINITIONS, {}).focus(path, text)[0]


def test_rev_is_a_registered_collision_owned_on_proof():
    livecode = LANGUAGE_DEFINITIONS["livecode"]
    assert ".rev" in LENS_CONFIG["COLLISION_FREQUENCIES"]
    assert livecode["extensions_needing_discriminator"] == [".rev"]
    assert livecode["internal_discriminator_extensions"] == [".rev"]


@pytest.mark.parametrize(
    "text",
    [
        "on mouseUp\n  answer \"hi\"\nend mouseUp\n",
        "private function total pA, pB\n  return pA + pB\nend total\n",
        "command doWork\n  put 1 into x\nend doWork\n",
        "getProp myProp\n  return 1\nend myProp\n",
        'script "on openStack\\n  go card 1\\nend openStack"\n',
        "REVO7000 stack data\n",
    ],
)
def test_rev_with_livecode_content_is_livecode(text):
    assert _lang("stacks/main.rev", text) == "livecode"


@pytest.mark.parametrize("text", ["116\n", "116", "0001\n", "build 42\n", "one on two\n"])
def test_rev_build_counter_is_not_livecode(text):
    assert _lang("source/bank00.a.rev", text) != "livecode"


def test_other_livecode_extensions_stay_uncontested():
    for ext in (".lc", ".livecode", ".livecodescript", ".lcb", ".stack"):
        assert _lang(f"x{ext}", "116\n") == "livecode"
