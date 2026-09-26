"""#3813: every source read decodes without losing a byte.

Each decode path (BOM, BOM-less UTF-16, UTF-8, the cp1252 and Latin-1 guesses), the size cap
(a cut through a multi-byte character is still UTF-8), and the traps: a stray NUL is not UTF-16,
and a binary of 16-bit integers is not text -- its NULs must reach the binary gate.
"""

import codecs
import random
import struct

import pytest

from gitgalaxy.core.source_text import decode_source, read_source

SOURCE = "def beløp(ärende):\n    return 'Ω≈ç'  # π\n"


@pytest.mark.parametrize("codec, bom", [("utf-8", codecs.BOM_UTF8), ("utf-16-le", codecs.BOM_UTF16_LE),
                                        ("utf-16-be", codecs.BOM_UTF16_BE), ("utf-32-le", codecs.BOM_UTF32_LE),
                                        ("utf-32-be", codecs.BOM_UTF32_BE)])  # fmt: skip
def test_a_byte_order_mark_picks_the_codec_and_is_consumed(codec, bom):
    got = decode_source(bom + SOURCE.encode(codec))
    assert (got.text, got.encoding, got.how) == (SOURCE, codec, "bom")  # no U+FEFF left on line 1 (#2411)


@pytest.mark.parametrize("codec", ["utf-16-le", "utf-16-be"])
def test_bomless_latin_script_utf16_is_recognised(codec):
    text = "IDENTIFICATION DIVISION.\nPROGRAM-ID. BELØP.\n" * 3
    got = decode_source(text.encode(codec))
    assert (got.text, got.encoding, got.how) == (text, codec, "utf-16-heuristic")


def test_utf8_is_read_strictly():
    got = decode_source(SOURCE.encode("utf-8"))
    assert (got.text, got.encoding, got.how) == (SOURCE, "utf-8", "utf-8")


def test_a_cp1252_file_keeps_its_national_characters():
    text = "       01  KUNDE-ÖRT     PIC X(20).  * “smart quotes” – €\n"
    got = decode_source(text.encode("cp1252"))
    assert (got.text, got.how) == (text, "cp1252-fallback")


def test_bytes_cp1252_cannot_map_fall_back_to_latin1():
    data = b"MOVE X TO Y. \x81\x8d\x8f\x90\x9d \xc4\n"  # the five bytes cp1252 leaves unmapped
    got = decode_source(data)
    assert (got.how, got.text.encode("latin-1")) == ("latin-1-fallback", data)  # every byte kept


def test_shift_jis_is_never_an_error_and_loses_nothing():
    data = "変数 = 1  # コメント\n".encode("shift_jis")
    got = decode_source(data)
    assert got.how in ("cp1252-fallback", "latin-1-fallback")
    assert got.text.encode(got.encoding) == data  # a guess, but a lossless one


def test_a_stray_nul_does_not_make_utf8_look_like_utf16():
    data = ("x = 1\n" * 20).encode() + b"\x00" + ("y = 2\n" * 20).encode()
    got = decode_source(data)
    assert (got.encoding, got.text.count("\x00")) == ("utf-8", 1)


def test_a_binary_of_16_bit_integers_stays_binary():
    """Little-endian shorts below 256 have NUL high bytes, like UTF-16 -- but decode to control
    characters, not text. They must stay NUL-dense so the aperture's binary gate drops them."""
    data = struct.pack("<512H", *range(512)) + struct.pack("<512H", *(i % 32 for i in range(512)))
    got = decode_source(data)
    assert got.how != "utf-16-heuristic"
    assert got.text.count("\x00") * 1000 > len(got.text)  # still binary by aperture's density rule


def test_a_limited_read_reads_only_the_limit(tmp_path):
    p = tmp_path / "big.log"
    p.write_bytes(b"a" * 200_000)
    assert len(read_source(p, limit=50 * 1024).text) == 50 * 1024


def test_a_limit_that_cuts_a_character_still_reads_utf8(tmp_path):
    p = tmp_path / "cut.py"
    p.write_bytes(("é" * 100).encode("utf-8"))  # two bytes each: a limit of 51 cuts the 26th
    got = read_source(p, limit=51)
    assert (got.encoding, got.text) == ("utf-8", "é" * 25)


def test_a_limit_that_cuts_utf16_still_reads_utf16(tmp_path):
    p = tmp_path / "cut16.cbl"
    p.write_bytes(codecs.BOM_UTF16_LE + ("MOVE A TO B.\n" * 20).encode("utf-16-le"))
    got = read_source(p, limit=101)  # an odd cut, mid code unit
    assert (got.encoding, got.how) == ("utf-16-le", "bom") and got.text.startswith("MOVE A TO B.\n")


def test_an_unlimited_read_matches_decode_source(tmp_path):
    p = tmp_path / "s.py"
    p.write_bytes(SOURCE.encode("utf-8"))
    assert read_source(p) == decode_source(SOURCE.encode("utf-8"))


def test_random_bytes_never_raise_and_never_lose_a_byte():
    rng = random.Random(3813)
    for _ in range(200):
        data = bytes(rng.randrange(256) for _ in range(rng.randrange(0, 300)))
        got = decode_source(data)
        if got.how != "bom":
            assert got.text.encode(got.encoding) == data


@pytest.mark.parametrize("ending", ["\r\n", "\r"])
def test_line_endings_become_lf_as_text_mode_open_made_them(tmp_path, ending):
    p = tmp_path / "crlf.cbl"
    p.write_bytes((("MOVE A TO B." + ending) * 3 + "STOP RUN.").encode("utf-16-le"))
    assert read_source(p).text == "MOVE A TO B.\n" * 3 + "STOP RUN."
