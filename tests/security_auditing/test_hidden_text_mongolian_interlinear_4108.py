"""#4108: U+180E and a lone interlinear annotation mark are hidden text; real Mongolian and a whole annotation are not.

Siblings of the Hangul filler (#8249). Characters are escaped: the code point is the point.
"""

import pytest

from gitgalaxy.security.security_lens import SecurityLens

MVS = "᠎"
A, S, T = "￹", "￺", "￻"
MONGOLIAN = "ᠠᠡᠢ"  # letters in the Mongolian block


@pytest.fixture(scope="module")
def lens():
    return SecurityLens()


def _hidden(lens, text):
    return lens.scan_content(text)["counts"].get("reflection_metaprogramming", 0)


@pytest.mark.parametrize(
    "src",
    [
        f"x = 'a{MVS}b'\n",  # ASCII context
        f"{MVS} = 1\n",  # as a name
        f"x = 1  # a{MVS}b\n",  # in a comment
        f"x = '{MONGOLIAN}{MVS}{MVS}'\n",  # the second of a run
        f"x = '{A}a'\n",  # lone anchor
        f"x = '{A}a{S}b'\n",  # no terminator
        f"x = 'a{S}b'\n",  # lone separator
        f"x = '{A}{S}'\n",  # truncated
        f"x = 'a{T}{T}'\n",  # doubled terminator
        f"{T}x = 1\n",  # terminator at line start
        f"x = '{A}a{S}b\n{T}'\n",  # annotation split across lines
    ],
)
def test_hidden_shapes_fire(lens, src):
    assert _hidden(lens, src) >= 1, src


@pytest.mark.parametrize(
    "src",
    [
        "x = 1  # plain ascii\n",
        f"x = '{MONGOLIAN}{MVS}ᠠ'\n",  # real Mongolian: separator after a letter
        f"x = 'ᢀ{MVS}ᠡ'\n",  # extended-block letter
        f"x = '{A}base{S}gloss{T}'\n",  # whole annotation
        f"x = '{A}{S}{T}'\n",  # empty whole annotation
        f"x = '{A}a{S}b{T} and {A}c{S}d{T}'\n",  # two annotations
    ],
)
def test_real_text_does_not_fire(lens, src):
    assert _hidden(lens, src) == 0, src
