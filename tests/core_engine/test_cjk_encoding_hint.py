"""#3878: a file that fell back to cp1252 / Latin-1 but reads as double-byte CJK text gets a hint.

The engine never guesses a CJK code page (GB18030 decodes almost any bytes, so guessing would corrupt
Western estates); the LLM report's 4.1 SOURCE ENCODINGS names the declaration to make instead.
"""

import pytest

from gitgalaxy.core.source_text import decode_source
from gitgalaxy.recorders.llm_recorder import LLMRecorder

JAPANESE = "# 日本語のコメントです。\ndef 計算(値):\n    return 値  # 戻り値を返します\n"
CHINESE = "// 这是一个中文注释，说明这个函数的用途。\nint 计算(int 数值) { return 数值; } // 返回结果\n"
KOREAN = "// 한국어 주석입니다. 이 함수는 값을 계산합니다.\nint 계산(int 값) { return 값; }\n"


@pytest.mark.parametrize(
    "text,codec,expected",
    [
        (JAPANESE, "shift_jis", "shift_jis"),
        (JAPANESE, "euc_jp", "euc_jp"),
        (CHINESE, "gbk", "gbk"),
        (CHINESE, "gb18030", "gbk"),
        (KOREAN, "euc_kr", "euc_kr"),
    ],  # fmt: skip
)
def test_double_byte_text_names_its_code_page(text, codec, expected):
    src = decode_source(text.encode(codec))
    assert src.how in ("cp1252-fallback", "latin-1-fallback")  # a guess: the hint is for exactly this
    assert expected in src.cjk_candidates


@pytest.mark.parametrize(
    "text",
    [
        # accents alone between ASCII letters: Shift-JIS / GBK would read `él` or `ür` as one kanji
        "/* L'élève préfère le thé: très célèbre. Ça arrive à l'école où règne la fièvre. */\nint élève;\n",
        "# Größe für Übermaß: Äpfel, Öle, Müller, Straße, Grüße, schön, überprüfen\nx = 1\n",
        "-- BELØP på kontoen, SKRIVEÅR, Ærø, Åland, sjøen, blåbær, ørret\n",
        "/* señor, niño, año, mañana, Ñandú, corazón, acción, está, sí */\n",
    ],
)
def test_western_legacy_text_gets_no_hint(text):
    src = decode_source(text.encode("cp1252"))
    assert src.how == "cp1252-fallback"
    assert src.cjk_candidates == ()


def test_certain_decodes_get_no_hint():
    assert decode_source(JAPANESE.encode("utf-8")).cjk_candidates == ()
    assert decode_source(JAPANESE.encode("shift_jis"), declared="shift_jis").cjk_candidates == ()


def test_a_character_cut_at_the_sample_end_does_not_hide_the_hint():
    data = (JAPANESE * 3000).encode("shift_jis")  # > 64 KB
    assert "shift_jis" in decode_source(data).cjk_candidates


def test_the_report_names_the_declaration_to_make():
    parsed = [
        {"path": f"src/m{i}.c", "source_encoding": "cp1252", "source_decode": "cp1252-fallback",
         "cjk_candidates": ["shift_jis"]}
        for i in range(7)
    ] + [{"path": "src/plain.c", "source_encoding": "cp1252", "source_decode": "cp1252-fallback"}]  # fmt: skip
    text = "\n".join(LLMRecorder()._source_encoding_lines(parsed))
    assert "> 7 guessed file(s) read as double-byte text that decodes strictly as shift_jis" in text
    assert "`--source-encoding shift_jis`" in text
    assert "`src/m0.c`" in text and "and 2 more" in text and "plain.c" not in text


def test_no_hint_line_without_candidates():
    parsed = [{"path": "a.c", "source_encoding": "cp1252", "source_decode": "cp1252-fallback"}]
    assert "double-byte" not in "\n".join(LLMRecorder()._source_encoding_lines(parsed))
