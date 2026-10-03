"""#3814 / #3810: mainframe names carry national letters.

On national EBCDIC code pages the bytes behind `$ # @` display as `Å Æ Ø` (cp277), `Å Ä Ö` (cp278),
`§` (cp273), `Ñ` (cp284), `£` (cp285 / cp297) ... so exported JCL, CSD, HLASM, COBOL and BMS names
carry them. Each channel must read such a name whole -- and every letter class in the mainframe
readers must splice in identifiers.NATIONAL, so a new rule cannot quietly drop them again.
"""

import re
from pathlib import Path

import pytest

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.mainframe_boundary import extract_boundary
from gitgalaxy.core.prism import Prism
from gitgalaxy.core.source_text import read_source
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

ROOT = Path(__file__).resolve().parents[2]
READERS = [
    *(f"gitgalaxy/standards/language_standards/languages/{n}.py" for n in ("jcl", "cobol", "hlasm", "bms", "csd")),
    *(f"gitgalaxy/core/{n}.py" for n in ("mainframe_boundary", "job_flow", "file_control")),
]


def _code(rel: str) -> str:
    """The file without its comment lines (a comment may quote an old, ASCII-only class)."""
    lines = (ROOT / rel).read_text(encoding="utf-8").splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("#"))


def test_every_mainframe_letter_class_accepts_the_national_letters():
    missing = [
        f"{rel}: {m.group(0)}"
        for rel in READERS
        for m in re.finditer(r"\[(?!\^)[^\]\[]*A-Z[^\]\[]*\]", _code(rel))
        # the class splices the constant in (a COBOL word class adds #3991's full-width digits / hyphens after it)
        if not re.search(r'"\s*\+\s*NATIONAL(?:\s*\+\s*WIDE_(?:DIGITS|HYPHENS))*\s*\+\s*r"', m.group(0))
    ]
    assert not missing, "\n".join(missing)


def test_jcl_job_step_program_and_dataset_are_whole():
    out = extract_boundary(
        "jcl",
        "//ØKJOBB   JOB (ACCT),'X'\n//ÆSTEG1   EXEC PGM=ØKONOMI\n//INN      DD DSN=PROD.ÅRSOPPGJØR(+1),DISP=SHR\n",
    )
    assert [c["target"] for c in out["calls"]] == ["ØKONOMI"]
    assert [(d["step_name"], d["dsn"]) for d in out["datasets"]] == [("ÆSTEG1", "PROD.ÅRSOPPGJØR(+1)")]
    flow = {(f["kind"], f["name"] or f["step_name"] or f["dd_name"]) for f in out["job_flow"]}
    assert {("JOB", "ØKJOBB"), ("STEP", "ÆSTEG1"), ("DD", "ÆSTEG1")} <= flow


def test_a_csd_resource_and_its_dataset_are_whole():
    (res,) = extract_boundary("csd", "DEFINE FILE(KUNDÆR) GROUP(ØKGRP) DSNAME(PROD.KUNDEØ.DATA)\n")["csd_resources"]
    assert (res["name"], res["group"], res["dsname"]) == ("KUNDÆR", "ØKGRP", "PROD.KUNDEØ.DATA")


def test_cobol_calls_and_data_items_are_whole():
    src = (
        "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. RÄKNA.\n       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n       01  WS-HÄLSNING    PIC X(10).\n       PROCEDURE DIVISION.\n"
        "       100-RÄKNA.\n           CALL 'ØKONOMI' USING WS-HÄLSNING.\n"
    )
    out = extract_boundary("cobol", src)
    assert [c["target"] for c in out["calls"]] == ["ØKONOMI"]
    assert [r["name"] for r in out["records"]] == ["WS-HÄLSNING"]


def _units(lang: str, code: str) -> list[str]:
    streams = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS).split_streams(code, lang)
    out = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(
        code_stream=streams["code_stream"], comment_stream=streams["comment_stream"], confidence=1.0
    )
    return [f["name"] for f in out["functions"]]


@pytest.mark.parametrize(
    "lang, code, name",
    [
        ("hlasm", "ØKASM    CSECT\n         BR    14\n         END\n", "ØKASM"),
        ("hlasm", "§PRUF    CSECT\n         BR    14\n         END\n", "§PRUF"),  # cp273's national `@`
        ("cobol", "       PROCEDURE DIVISION.\n       100-RÄKNA.\n           STOP RUN.\n", "100-RÄKNA"),
        ("jcl", "//ØKJOBB   JOB (ACCT)\n//ÆSTEG1   EXEC PGM=ØKONOMI\n", "ÆSTEG1"),
    ],
)
def test_a_national_unit_is_found_whole(lang, code, name):
    assert name in _units(lang, code)


# --- #3991: a Japanese COBOL word's full-width digits and hyphen --------------------------------------
# #3955 let a COBOL word hold any Unicode letter; a Japanese word also holds full-width digits (０-９) and
# the full-width hyphen. Shift-JIS 0x817C is that hyphen, and it has two decodings: cp932 gives U+FF0D
# (－), Python's shift_jis gives U+2212 (−). Before this, the name was cut at either character.
_JP_WORDS = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. JPWORDS.\n       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    "       01  項目２           PIC X(4).\n"
    "       01  Ｏ−文字列       PIC X(4).\n"
    "       01  ｗｋ－０３       PIC X(4).\n"
    "       01  横浜-1           PIC X(4).\n"
    "       01  ＴＥＳＴ−ＤＡＴＡ１ PIC X(4).\n"
    "       01  ＴＥＳＴ−ＲＥＣＯＲＤ１ REDEFINES ＴＥＳＴ−ＤＡＴＡ１ PIC X(4).\n"
    "       PROCEDURE DIVISION.\n"
    "       主処理 SECTION.\n           PERFORM Ｓ−初期化.\n           MOVE 'A' TO 項目２.\n"
    "       ASCII-SEC SECTION.\n           DISPLAY 'X'.\n"
    "       Ｓ−初期化 SECTION.\n           DISPLAY 'Y'.\n"
    "       ｓ１２３ SECTION.\n           DISPLAY 'Z'.\n"
    "       Ｓ－終了 SECTION.\n           STOP RUN.\n"
)


def test_japanese_data_names_keep_their_full_width_digits_and_hyphens():
    records = extract_boundary("cobol", _JP_WORDS)["records"]
    assert [r["name"] for r in records] == [
        "項目２",
        "Ｏ−文字列",
        "ＷＫ－０３",  # upper-cased like any COBOL name
        "横浜-1",
        "ＴＥＳＴ−ＤＡＴＡ１",
        "ＴＥＳＴ−ＲＥＣＯＲＤ１",  # no longer collides with the item above as `ＴＥＳＴ`
    ]
    assert records[-1]["redefines"] == "ＴＥＳＴ−ＤＡＴＡ１"


def test_japanese_sections_with_full_width_digits_and_hyphens_are_found_whole():
    assert _units("cobol", _JP_WORDS) == ["主処理", "ASCII-SEC", "Ｓ−初期化", "ｓ１２３", "Ｓ－終了"]


def test_a_japanese_callee_is_read_whole():
    rules = LANGUAGE_DEFINITIONS["cobol"]["rules"]
    assert rules["calls_out"].findall("           PERFORM Ｓ－終了.\n") == ["Ｓ－終了"]
    assert rules["_transfers_out"].findall("           GO TO ｓ１２３.\n") == ["ｓ１２３"]


@pytest.mark.parametrize("codec, hyphen", [("shift_jis", "\u2212"), ("cp932", "\uff0d")])
def test_both_decodings_of_sjis_0x817c_are_the_word_hyphen(tmp_path, codec, hyphen):
    p = tmp_path / "JPSJIS.cbl"
    p.write_bytes(_JP_WORDS.replace("\u2212", "\uff0d").encode("cp932"))
    assert p.read_bytes().count(b"\x81\x7c") == 8  # every hyphen above is the one byte pair
    text = read_source(p, declared=codec).text
    assert "\uff0d\u2212".replace(hyphen, "") not in text  # the codec decides which character it is
    records = [r["name"] for r in extract_boundary("cobol", text)["records"]]
    assert records[1] == f"Ｏ{hyphen}文字列" and records[-1] == f"ＴＥＳＴ{hyphen}ＲＥＣＯＲＤ１"
    assert [u for u in _units("cobol", text) if u.startswith("Ｓ")] == [f"Ｓ{hyphen}初期化", f"Ｓ{hyphen}終了"]


@pytest.mark.parametrize("minus", ["\u2212", "\uff0d"])
def test_a_spaced_full_width_minus_is_not_part_of_a_name(minus):
    # Only a hyphen INSIDE a word joins it; `A − B` (arithmetic, operands spaced as COBOL requires) is two words.
    rules = LANGUAGE_DEFINITIONS["cobol"]["rules"]
    assert rules["calls_out"].findall(f"           PERFORM ＷＫ {minus} ＷＫ２.\n") == ["ＷＫ"]
    src = f"       PROCEDURE DIVISION.\n       MAIN-PARA.\n           COMPUTE ＷＫ = ＷＫ１ {minus} ＷＫ２.\n"
    assert _units("cobol", src) == ["MAIN-PARA"]


def test_every_cobol_word_class_takes_the_full_width_digits_and_hyphens():
    """#3991: a COBOL word class that takes `0-9` takes WIDE_DIGITS, and one that takes `-` takes WIDE_HYPHENS.

    The fixed-format sequence area (`[0-9a-zA-Z ... \\t]{6}`) is a column prefix, not a word, and is exempt.
    """
    code = _code("gitgalaxy/standards/language_standards/languages/cobol.py")
    missing = []
    for m in re.finditer(r"\[(?!\^)[^\]\[]*A-Z[^\]\[]*\]", code):
        cls = m.group(0)
        if "\\t" in cls or "0-9" not in cls:
            continue
        if "WIDE_DIGITS" not in cls or (cls.endswith("-]") and "WIDE_HYPHENS" not in cls):
            missing.append(cls)
    assert not missing, "\n".join(missing)
