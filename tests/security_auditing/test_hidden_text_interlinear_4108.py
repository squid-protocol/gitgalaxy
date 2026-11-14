"""#4108: interlinear annotation anchors (U+FFF9-FFFB) render as nothing and count as hidden text."""

import pytest

from gitgalaxy.security.security_lens import SecurityLens


@pytest.fixture(scope="module")
def lens():
    return SecurityLens()


def _hidden(lens, text):
    return lens.scan_content(text)["counts"].get("reflection_metaprogramming", 0)


@pytest.mark.parametrize("ch", ["￹", "￺", "￻"])
@pytest.mark.parametrize("shape", ["comment", "string", "code"])
def test_interlinear_anchor_fires_wherever_it_sits(lens, ch, shape):
    src = {
        "comment": f"x = 1  # a{ch}b\n",
        "string": f'x = "a{ch}b"\n',
        "code": f"if admin{ch}:\n    pass\n",
    }[shape]
    assert _hidden(lens, src) == 1, (hex(ord(ch)), shape)


@pytest.mark.parametrize(
    "src",
    [
        "x = '￸'\n",  # unassigned neighbour below
        "x = '￼ �'\n",  # object replacement / replacement character: visible glyphs
        "x = 'café 中文'\n",
    ],
)
def test_neighbours_do_not_fire(lens, src):
    assert _hidden(lens, src) == 0, src
