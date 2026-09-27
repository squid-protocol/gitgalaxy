"""#3816 part 3a: IBM's mixed single/double-byte CJK host code pages, and raw files written in them.

cp930 / cp939 (Japanese), cp935 (Simplified Chinese), cp937 (Traditional Chinese) and cp933 (Korean)
read single bytes until Shift-Out (0x0E), then pairs until Shift-In (0x0F). Python ships none of them;
`ebcdic_dbcs` decodes them from tables generated off the JDK (tests/tools/gen_ebcdic_dbcs.py), and
`read_source` splits a raw download into records on bytes, keeping each card's sequence area at
column 73 however many characters its Kanji make.
"""

import codecs
import os
import sqlite3
import subprocess
import sys

import pytest

from gitgalaxy.core import ebcdic_dbcs
from gitgalaxy.core.ebcdic_codecs import EBCDIC_CODE_PAGES
from gitgalaxy.core.source_text import decode_source, parse_source_encoding, read_source

PAGES = ["cp930", "cp939", "cp935", "cp937", "cp933"]
SO, SI = b"\x0e", b"\x0f"

# What the JDK (21, x-IBM93x) writes for these strings -- the codec must write and read the same bytes.
JDK = [
    ("cp930", "      * 顧客マスタ更新 PROGRAM-ID. PGMA.", "4040404040405c400e4eee4ade43a4438e43914a6d45870f40d7d9d6c7d9c1d460c9c44b40d7c7d4c14b"),
    ("cp930", "MOVE N'名前' TO WS-NAME.", "d4d6e5c540d57d0e45f345af0f7d40e3d640e6e260d5c1d4c54b"),
    ("cp930", "ｱｲｳ ABC 123", "81828340c1c2c340f1f2f3"),
    ("cp939", "      * 顧客マスタ更新 PROGRAM-ID. PGMA.", "4040404040405c400e4eee4ade43a4438e43914a6d45870f40d7d9d6c7d9c1d460c9c44b40d7c7d4c14b"),
    ("cp939", "MOVE N'名前' TO WS-NAME.", "d4d6e5c540d57d0e45f345af0f7d40e3d640e6e260d5c1d4c54b"),
    ("cp939", "ｱｲｳ ABC 123", "59626340c1c2c340f1f2f3"),
    ("cp935", "MOVE N'名前' TO WS-NAME.", "d4d6e5c540d57d0e529c54500f7d40e3d640e6e260d5c1d4c54b"),
    ("cp935", "客户信息 PROGRAM", "0e506d4e4758c458420f40d7d9d6c7d9c1d4"),
    ("cp937", "      * 顧客マスタ更新 PROGRAM-ID. PGMA.", "4040404040405c400e67c0528b43a4438e43914f755c5b0f40d7d9d6c7d9c1d460c9c44b40d7c7d4c14b"),
    ("cp937", "MOVE N'名前' TO WS-NAME.", "d4d6e5c540d57d0e4dd752490f7d40e3d640e6e260d5c1d4c54b"),
    ("cp937", "客戶資料 表", "0e528b4cc15d9254e80f400e51cf0f"),
    ("cp933", "      * 顧客マスタ更新 PROGRAM-ID. PGMA.", "4040404040405c400e51ad50bf457e4559455f51585bf80f40d7d9d6c7d9c1d460c9c44b40d7c7d4c14b"),
    ("cp933", "MOVE N'名前' TO WS-NAME.", "d4d6e5c540d57d0e56d260a50f7d40e3d640e6e260d5c1d4c54b"),
    ("cp933", "客戶資料 表", "0e50bf66a05fd655d00f400e658d0f"),
    ("cp933", "고객 정보 PROGRAM", "0e89a188820f400eb8f7a5a10f40d7d9d6c7d9c1d4"),
]  # fmt: skip


@pytest.mark.parametrize("cp, text, hexed", JDK)
def test_the_codec_writes_and_reads_what_the_jdk_does(cp, text, hexed):
    assert text.encode(cp).hex() == hexed
    assert bytes.fromhex(hexed).decode(cp) == text


@pytest.mark.parametrize("cp", PAGES)
def test_every_double_byte_character_round_trips(cp):
    """The tables load from package data, and every character the page decodes writes back to a pair
    that reads as it again (IBM's duplicate pairs write as the one the JDK picks)."""
    _, dbcs, _, _ = ebcdic_dbcs._tables(cp)
    assert len(dbcs) > 9000
    text = "".join(sorted(set(dbcs.values())))
    assert text.encode(cp).decode(cp) == text
    assert codecs.lookup("IBM-" + cp[2:]).name == cp and codecs.lookup("x-ibm" + cp[2:]).name == cp
    assert cp in EBCDIC_CODE_PAGES and parse_source_encoding(cp) == cp


def test_the_two_japanese_pages_differ_in_their_single_byte_half():
    """cp930 is the Katakana host page: half-width Katakana where cp939 (the Latin one) has lower-case
    Latin, which cp930 moves elsewhere -- the same letters are different bytes."""
    assert bytes([0x81, 0x82, 0x83]).decode("cp930") == "ｱｲｳ"
    assert bytes([0x81, 0x82, 0x83]).decode("cp939") == "abc"
    assert "abc".encode("cp930") == bytes([0x62, 0x63, 0x64])


def test_the_shifts_are_state_not_text():
    assert (SO + SI + b"\xc1" + SO + b"\x45\xf3" + SI).decode("cp930") == "A名"
    assert (b"\xc1" + SO + b"\x40\x40").decode("cp930") == "A　"  # ends shifted out: legal
    assert "A名名B".encode("cp930") == b"\xc1" + SO + b"\x45\xf3\x45\xf3" + SI + b"\xc2"  # one shift per run


def test_a_bad_pair_is_an_error_not_a_guess():
    with pytest.raises(UnicodeDecodeError):
        (SO + b"\x45").decode("cp930")  # a lead byte with no trail
    with pytest.raises(UnicodeDecodeError):
        (SO + b"\xfe\xfe" + SI).decode("cp935")  # a pair the page does not map
    assert (SO + b"\xfe\xfe" + SI + b"\xc1").decode("cp935", errors="replace") == "�A"
    assert "A名\u20acB".encode("cp930", errors="replace") == b"\xc1" + SO + b"\x45\xf3" + SI + b"\x6f\xc2"


def test_the_incremental_decoder_keeps_state_and_a_split_pair():
    data = "      * 顧客マスタ更新".encode("cp930")
    for cut in range(len(data) + 1):
        dec = codecs.getincrementaldecoder("cp930")()
        assert dec.decode(data[:cut]) + dec.decode(data[cut:], final=True) == "      * 顧客マスタ更新"
    enc = codecs.getincrementalencoder("cp930")()
    assert enc.encode("A名") + enc.encode("前B") + enc.encode("", final=True) == "A名前B".encode("cp930")


# ---- raw source files --------------------------------------------------------------------------
COBOL = ["      * {comment}", "       IDENTIFICATION DIVISION.", "       PROGRAM-ID. PGMA.",
         "       PROCEDURE DIVISION.", "       100-MAIN.", "           MOVE N'名前' TO WS-NAME.",
         "           CALL 'SUBPGM'.", "           GOBACK."]  # fmt: skip


def card(line: str, cp: str, seq: int) -> bytes:
    """A card image as the host holds it: the program in bytes 1-72, a sequence number in 73-80."""
    data = line.encode(cp)
    assert len(data) <= 72
    return data.ljust(72, b"\x40") + f"{seq:08d}".encode(cp)


COMMENTS = {"cp930": "顧客マスタ更新処理", "cp939": "顧客マスタ更新処理", "cp935": "客户信息更新",
            "cp937": "客戶資料更新", "cp933": "고객 정보 갱신"}  # fmt: skip


def deck(cp: str) -> list[str]:
    return [line.format(comment=COMMENTS[cp]) for line in COBOL]


@pytest.mark.parametrize("cp", PAGES)
def test_a_fixed_block_deck_keeps_its_sequence_area_at_column_73(cp):
    data = b"".join(card(line, cp, n * 100) for n, line in enumerate(deck(cp)))
    src = decode_source(data, declared=cp)
    assert (src.encoding, src.how) == (cp, "declared")
    lines = src.text.splitlines()
    assert [line[:72].rstrip() for line in lines] == deck(cp)
    assert [line[72:] for line in lines] == [f"{n * 100:08d}" for n in range(len(COBOL))]


def test_nel_ends_a_line_and_is_found_in_the_bytes():
    data = "MOVE N'名前' TO A.".encode("cp930") + b"\x15" + "B.".encode("cp930") + b"\x15"
    assert decode_source(data, declared="cp930").text == "MOVE N'名前' TO A.\nB.\n"


def test_a_short_line_is_not_padded():
    data = "      * 名前".encode("cp930") + b"\x15"
    assert decode_source(data, declared="cp930").text == "      * 名前\n"


def test_a_pair_cut_by_column_72_decodes_the_record_whole():
    """Malformed (the compiler wants the shift-in by byte 72), but no byte is lost over it."""
    record = b"\x40" * 70 + SO + b"\x45\xf3" + SI + "000001".encode("cp930")
    assert len(record) == 80
    assert decode_source(record, declared="cp930").text == " " * 70 + "名000001\n"


def test_a_truncated_read_drops_only_the_cut_pair(tmp_path):
    path = tmp_path / "BIG.cbl"
    head = "      * 顧客".encode("cp930")
    path.write_bytes(head + b"\x15" + b"\x40" * 5 + SO + b"\x45\xf3\x45\xf3" + SI)
    src = read_source(path, limit=len(head) + 1 + 5 + 1 + 3, declared="cp930")  # cut inside the second pair
    assert (src.how, src.text) == ("declared", "      * 顧客\n     名")


def test_a_single_byte_page_reads_as_before():
    """The byte-level split is for the mixed pages only: cp037 decodes as characters, as it did."""
    text = "       PROGRAM-ID. PGMA.".ljust(72) + "00000100"
    assert decode_source(text.encode("cp037"), declared="cp037").text == text + "\n"


def test_a_raw_cp930_program_scans_with_its_kanji(tmp_path):
    """End to end: a fixed-block cp930 member, declared, keeps its Japanese comment and N-literal and
    the engine finds its units and calls as it does in the UTF-8 file."""
    src = tmp_path / "src" / "cbl"
    src.mkdir(parents=True)
    (src / "PGMA.cbl").write_bytes(b"".join(card(line, "cp930", n * 100) for n, line in enumerate(deck("cp930"))))
    env = dict(os.environ, GITGALAXY_LICENSE_KEY="COMMUNITY_FREE_TIER", GITGALAXY_DISABLE_GIT_HISTORY="1")
    subprocess.run([sys.executable, "-m", "gitgalaxy.galaxyscope", str(tmp_path / "src"), "--db-only", "--output",
                    str(tmp_path / "out"), "--source-encoding", "cp930"], check=True, env=env, capture_output=True)  # fmt: skip
    (db,) = (tmp_path / "out").glob("*_galaxy_master.db")
    con = sqlite3.connect(db)
    assert set(con.execute("SELECT source_encoding, source_decode FROM file_data")) == {("cp930", "declared")}
    assert ("CALL", "SUBPGM") in {(r[0], r[1]) for r in con.execute("SELECT verb, target FROM call_site_data")}
    assert "100-MAIN" in {r[0] for r in con.execute("SELECT func_name FROM function_data")}
