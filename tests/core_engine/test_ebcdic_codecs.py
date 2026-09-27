"""#3816: the national EBCDIC code pages Python lacks, and raw EBCDIC source files.

A Western European estate is written in cp277 (Denmark / Norway), cp278 (Finland / Sweden), cp280 (Italy),
cp284 (Spain), cp285 (UK), cp297 (France) or cp1047 (z/OS USS); Python ships only cp037 / cp273 / cp500 /
cp1140. `ebcdic_codecs` registers the rest, and `read_source` reads a raw download: NEL ends a line, and a
fixed-block member with no line ends is split into its 80-byte card images.
"""

import codecs
import os
import sqlite3
import subprocess
import sys

import pytest

from gitgalaxy.core.ebcdic_codecs import EBCDIC_CODE_PAGES
from gitgalaxy.core.source_text import decode_source, parse_source_encoding
from gitgalaxy.tools.cobol_to_java.java_target import zoned_sign_characters

PAGES = ["cp277", "cp278", "cp280", "cp284", "cp285", "cp297", "cp1047"]
ALL = bytes(range(256))


@pytest.mark.parametrize("cp", PAGES)
def test_each_page_is_a_lossless_permutation_of_cp037(cp):
    text = ALL.decode(cp)
    assert text.encode(cp) == ALL
    assert sorted(text) == sorted(ALL.decode("cp037"))  # the same 256 characters, moved
    assert codecs.lookup("IBM-" + cp[2:]).name == cp and codecs.lookup("ibm" + cp[2:]).name == cp
    assert cp in EBCDIC_CODE_PAGES
    assert codecs.getincrementaldecoder(cp)().decode(ALL[:128]) == text[:128]


@pytest.mark.parametrize("cp, national", [("cp277", "ÆØÅ"), ("cp278", "ÄÖÅ"), ("cp037", "#@$"), ("cp273", "#§$")])
def test_the_national_bytes_show_the_national_letters(cp, national):
    """The bytes of `# @ $` on cp037 (0x7B 0x7C 0x5B) are the letters a Nordic / German name is written in."""
    assert bytes([0x7B, 0x7C, 0x5B]).decode(cp) == national


def test_cp1047_moves_the_brackets_and_the_caret():
    assert bytes([0xAD, 0xBD, 0x5F, 0xB0]).decode("cp1047") == "[]^¬"
    assert bytes([0xBA, 0xBB, 0x5F, 0xB0]).decode("cp037") == "[]¬^"


@pytest.mark.parametrize("cp, plus, minus", [("cp277", "æ", "å"), ("cp278", "ä", "å"), ("cp280", "à", "è"),
                                             ("cp284", "{", "}"), ("cp285", "{", "}"), ("cp297", "é", "è"),
                                             ("cp1047", "{", "}")])  # fmt: skip
def test_the_zoned_signs_come_from_the_codec(cp, plus, minus):
    """#3826 tabulated these zero signs by hand (IBM CDRA); the registered codecs now derive them."""
    assert zoned_sign_characters(cp) == (plus + "ABCDEFGHI", minus + "JKLMNOPQR")


def test_a_declared_page_is_validated_not_guessed():
    assert parse_source_encoding("cp278") == "cp278"
    assert parse_source_encoding("*.jcl=ibm-277") == {"*.jcl": "ibm-277"}
    with pytest.raises(ValueError, match="unknown source encoding"):
        parse_source_encoding("cp999")


def test_a_fixed_block_download_splits_into_card_images():
    cards = ["//JOBÆ     JOB (ACCT)", "//STEPØ    EXEC PGM=ØKONOMI", "//KUNDÆR   DD DSN=PROD.ÅRSOPPGJØR,DISP=SHR"]
    src = decode_source("".join(c.ljust(80) for c in cards).encode("cp277"), declared="cp277")
    assert (src.encoding, src.how) == ("cp277", "declared")
    assert src.text.splitlines() == [c.ljust(80) for c in cards]


def test_nel_ends_a_line_and_other_lengths_are_left_alone():
    nel = decode_source("A = 1;\x85B = 2;\x85".encode("cp278"), declared="cp278")
    assert nel.text.splitlines() == ["A = 1;", "B = 2;"]
    odd = decode_source(("X" * 81).encode("cp278"), declared="cp278")  # not whole 80-byte records
    assert odd.text == "X" * 81


def test_a_utf8_file_is_still_read_as_utf8_under_an_ebcdic_declaration():
    src = decode_source("//JOBÆ JOB\n".encode("utf-8"), declared="cp277")
    assert (src.encoding, src.text) == ("utf-8", "//JOBÆ JOB\n")


JCL = ["//JOBÆ     JOB (ACCT),'NATT'", "//STEGØ    EXEC PGM=ØKONOMI", "//KUNDÆR   DD DSN=PROD.ÅRSOPPGJØR,DISP=SHR"]
COBOL = ["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. ØKONOMI.", "       PROCEDURE DIVISION.",
         "       100-RÆKNE.", '           CALL "BETALÅ"', "           GOBACK."]  # fmt: skip


def test_a_raw_cp277_estate_scans_with_its_letters(tmp_path):
    """End to end: fixed-block cp277 members, declared, keep every national letter in the facts."""
    for rel, lines in (("jcl/NATT.jcl", JCL), ("cbl/OKONOMI.cbl", COBOL)):
        (tmp_path / "src" / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "src" / rel).write_bytes("".join(line.ljust(80) for line in lines).encode("cp277"))
    env = dict(os.environ, GITGALAXY_LICENSE_KEY="COMMUNITY_FREE_TIER", GITGALAXY_DISABLE_GIT_HISTORY="1")
    subprocess.run([sys.executable, "-m", "gitgalaxy.galaxyscope", str(tmp_path / "src"), "--db-only", "--output",
                    str(tmp_path / "out"), "--source-encoding", "cp277"], check=True, env=env, capture_output=True)  # fmt: skip
    (db,) = (tmp_path / "out").glob("*_galaxy_master.db")
    con = sqlite3.connect(db)
    assert set(con.execute("SELECT source_encoding, source_decode FROM file_data")) == {("cp277", "declared")}
    steps = {r[0] for r in con.execute("SELECT step_name FROM job_flow_data WHERE kind = 'STEP'")}
    assert steps == {"STEGØ"}
    dsns = {r[0] for r in con.execute("SELECT dsn FROM job_flow_data WHERE kind = 'DD'")}
    assert dsns == {"PROD.ÅRSOPPGJØR"}
    calls = {(r[0], r[1]) for r in con.execute("SELECT verb, target FROM call_site_data")}
    assert ("EXEC PGM", "ØKONOMI") in calls and ("CALL", "BETALÅ") in calls
    units = {r[0] for r in con.execute("SELECT func_name FROM function_data")}
    assert "100-RÆKNE" in units
