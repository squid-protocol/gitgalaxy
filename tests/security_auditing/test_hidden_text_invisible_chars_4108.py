"""#4108: the Invisible Unicode hidden-text half reads every zero-width / bidi control, not a subset.

The Trojan-Source bidi isolates (U+2066-2069), the Arabic letter mark and the word joiner / invisible math
operators render as nothing, so they hide a payload exactly as U+202A-202E and U+200B do. Characters are escaped
on purpose: the invisible code point is the point, and a reader must see which one it is.
"""

import pytest

from gitgalaxy.security.security_lens import SecurityLens


@pytest.fixture(scope="module")
def lens():
    return SecurityLens()


def _hidden(lens, text):
    return lens.scan_content(text)["counts"].get("reflection_metaprogramming", 0)


@pytest.mark.parametrize(
    "ch",
    [
        "\u200b",  # zero width space (already live)
        "\u202e",  # right-to-left override (already live)
        "\u2060",  # word joiner
        "\u2061",  # function application
        "\u2062",  # invisible times
        "\u2063",  # invisible separator
        "\u2064",  # invisible plus
        "\u2066",  # left-to-right isolate
        "\u2067",  # right-to-left isolate
        "\u2068",  # first strong isolate
        "\u2069",  # pop directional isolate
        "\u061c",  # Arabic letter mark
    ],
)
@pytest.mark.parametrize("shape", ["comment", "string", "code"])
def test_an_invisible_control_fires_wherever_it_sits(lens, ch, shape):
    src = {
        "comment": f"x = 1  # a{ch}b\n",
        "string": f'x = "a{ch}b"\n',
        "code": f"if admin{ch}:\n    pass\n",
    }[shape]
    assert _hidden(lens, src) == 1, (hex(ord(ch)), shape)


@pytest.mark.parametrize(
    "src",
    [
        "x = 1  # plain ascii comment\n",
        "x = 'caf\u00e9 \u00fcber \u4e2d\u6587'\n",  # ordinary non-ASCII text
        "x = '\u0642\u0627\u0644'\n",  # Arabic letters, no mark
        "x = '\u2190\u2192 \u2200\u2203'\n",  # arrows and math symbols next to the U+206x block
        "x = '\u2028'\n",  # line separator is not a hidden control
        "x = '\u00ad\u00a0\u3000'\n",  # soft hyphen, nbsp, ideographic space: visible spacing
    ],
)
def test_visible_text_does_not_fire(lens, src):
    assert _hidden(lens, src) == 0, src
