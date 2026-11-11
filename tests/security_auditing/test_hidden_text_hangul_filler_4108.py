"""#4108: a run of Hangul fillers is hidden text, a lone conjoining-jamo placeholder is not.

U+3164 / U+FFA0 / U+115F / U+1160 render blank. A run of two or more is a blank name or padding hiding a payload;
a lone U+115F / U+1160 is legitimate decomposed Korean. Characters are escaped: the code point is the point.
"""

import pytest

from gitgalaxy.security.security_lens import SecurityLens


@pytest.fixture(scope="module")
def lens():
    return SecurityLens()


def _homoglyphs(lens, text):
    return lens.scan_content(text)["counts"].get("homoglyphs", 0)


@pytest.mark.parametrize("ch", ["ㅤ", "ﾠ", "ᅟ", "ᅠ"])
@pytest.mark.parametrize("shape", ["name", "string", "comment"])
def test_a_run_of_fillers_fires_wherever_it_sits(lens, ch, shape):
    run = ch * 3
    src = {
        "name": f"{run} = 1\n",
        "string": f'x = "a{run}b"\n',
        "comment": f"x = 1  # a{run}b\n",
    }[shape]
    assert _homoglyphs(lens, src) == 1, (hex(ord(ch)), shape)


def test_mixed_fillers_in_a_run_fire(lens):
    assert _homoglyphs(lens, 'x = "ㅤﾠ"\n') == 1


@pytest.mark.parametrize(
    "src",
    [
        "x = 1  # plain ascii\n",
        "x = '한국어 안녕하세요'\n",  # precomposed Korean
        "x = '한 글'\n",  # decomposed jamo, no filler
        "x = 'ᅟᅡ'\n",  # lone choseong filler before a vowel
        "x = 'ᄀᅠ'\n",  # lone jungseong filler after a consonant
        "x = 'ㅤ'\n",  # one filler alone
        "x = 'ㄱㄴ ㄱ ㄴ'\n",  # compatibility jamo with spaces
    ],
)
def test_korean_text_and_a_lone_filler_do_not_fire(lens, src):
    assert _homoglyphs(lens, src) == 0, src
