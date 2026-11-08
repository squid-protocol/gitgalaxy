"""#8111 slice 4: a COPY / EXEC SQL INCLUDE member the lens did not call COBOL. Two input classes, each proven through
the lens over the whole class and by one real scan of an authored estate (invented names):
  - an `.inc` member (the extension is shared with PHP / NASM / C /
    PL/I): the COBOL body decides;
  - an extensionless member in a library-path directory (one that holds COBOL files), on weaker evidence."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import copy_resolution_census as crc

from gitgalaxy.standards.language_lens import LanguageDetector
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

ITEMS = "       05 FAKE-ID PIC 9.\n       05 FAKE-AMT PIC S9(5)V99 COMP-3.\n"
GROUP = "       01  FAKE-REC.\n        05  FAKE-STATUS PIC X(20) VALUE SPACES.\n"
ONE_ITEM = "       05 TAG-ID PIC 9.\n"
BANNER = "      * Fake banner line one                                          *\n      * Fake banner line two                                          *\n"
CHAIN = BANNER + "       COPY FAKEZ.\n"
MEMBER_EXTS = [".inc", ".INC", ".Inc"]
PROGRAM = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. {pid}.\n       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n       01  REC.\n{copies}       PROCEDURE DIVISION.\n           GOBACK.\n"
)


@pytest.fixture(scope="module")
def detector():
    return LanguageDetector(LANGUAGE_DEFINITIONS, {})


@pytest.mark.parametrize("ext", MEMBER_EXTS)
@pytest.mark.parametrize("body", [ITEMS, GROUP], ids=["items", "group"])
def test_every_member_extension_with_a_cobol_body_is_cobol(detector, tmp_path, ext, body):
    assert detector.focus(str(tmp_path / ("FAKEA" + ext)), body)[0] == "cobol"


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("page.inc", "<?php\n$fake = 1;\necho $fake;\n"),
        ("macros.inc", "%include 'fake.inc'\nsection .text\nglobal _start\n"),
        ("fake.inc", "#define FAKE_MAX 8\nint fake_count(void);\n"),
        ("notes.inc", "01 Introduction.\n02 Setup.\n03 Usage.\n"),
        ("stray.inc", ONE_ITEM + "nothing else here\n"),
        ("run.inc", "#!/bin/sh\necho 01 PIC\n"),
        ("fake.INC", "just some text\n"),
    ],
)
def test_a_member_extension_without_a_cobol_body_is_not_cobol(detector, tmp_path, name, text):
    assert detector.focus(str(tmp_path / name), text)[0] != "cobol"


def test_a_pli_include_beside_pli_programs_stays_pli(detector, tmp_path):
    (tmp_path / "PGMA.pli").write_text("PGMA: PROC;\n", encoding="utf-8")
    assert detector.focus(str(tmp_path / "INCB.inc"), "%INCLUDE INCC;\nDCL CODEA CHAR(2);\n")[0] == "pli"


@pytest.mark.parametrize("body", [ONE_ITEM, ITEMS, CHAIN], ids=["one-item", "items", "copy-chain"])
def test_extensionless_member_beside_cobol_files_is_cobol(detector, tmp_path, body):
    (tmp_path / "A.cpy").write_text(GROUP, encoding="utf-8")
    assert detector.focus(str(tmp_path / "FAKEA"), body)[0] == "cobol"


@pytest.mark.parametrize("sibling", ["A.cbl", "A.CPY", "a.cob", "A.copy"])
def test_every_cobol_sibling_extension_makes_the_directory_a_library(detector, tmp_path, sibling):
    (tmp_path / sibling).write_text(GROUP, encoding="utf-8")
    assert detector.focus(str(tmp_path / "FAKEA"), ONE_ITEM)[0] == "cobol"


@pytest.mark.parametrize(
    ("name", "text", "siblings"),
    [
        ("FAKEA", ONE_ITEM, False),  # no COBOL file beside it: one stray item is not a copybook
        ("FAKEA", CHAIN, False),
        ("FAKEA", BANNER, True),  # comments alone prove nothing
        ("FAKEA", BANNER + "       COPY FAKEZ.\nsome prose\n", True),
        ("README", "Build notes\nrun it twice.\n", True),
        ("FAKEA", "COPY FAKEZ.\n", False),
        ("has space", ONE_ITEM, True),
    ],
)
def test_weak_evidence_needs_a_library_directory_and_a_clean_body(detector, tmp_path, name, text, siblings):
    if siblings:
        (tmp_path / "A.cpy").write_text(GROUP, encoding="utf-8")
    else:
        (tmp_path / "notes.md").write_text("plain\n", encoding="utf-8")
    assert detector.focus(str(tmp_path / name), text)[0] != "cobol"


@pytest.fixture(scope="module")
def estate(tmp_path_factory):
    repo = tmp_path_factory.mktemp("est") / "fakeestate"
    (repo / "apps").mkdir(parents=True)
    copies = ""
    for i, ext in enumerate([".inc", ".INC", ".Inc"]):
        (repo / "inc").mkdir(exist_ok=True)
        (repo / "inc" / f"INCM{i}{ext}").write_text(GROUP, encoding="utf-8")
        copies += f"       EXEC SQL INCLUDE {'incm' if i % 2 else 'INCM'}{i} END-EXEC.\n"
    (repo / "libdir").mkdir()
    (repo / "libdir" / "BASE.cpy").write_text(GROUP, encoding="utf-8")
    (repo / "libdir" / "LIBA").write_text(ONE_ITEM, encoding="utf-8")
    (repo / "libdir" / "LIBB").write_text(BANNER + "       COPY BASE.\n", encoding="utf-8")
    copies += "       COPY LIBA.\n       COPY LIBB.\n"
    (repo / "apps" / "MAINPG.cbl").write_text(PROGRAM.format(pid="MAINPG", copies=copies), encoding="utf-8")
    edges, gaps = crc.engine_side(repo)
    return repo, edges, gaps


@pytest.mark.parametrize("member", ["inc/INCM0.inc", "inc/INCM1.INC", "inc/INCM2.Inc", "libdir/LIBA", "libdir/LIBB"])
def test_the_engine_draws_the_edge(estate, member):
    _repo, edges, _gaps = estate
    assert member in edges["apps/MAINPG.cbl"]


def test_the_census_finds_no_disagreement(estate):
    repo, _edges, _gaps = estate
    n = crc.census_repo(repo)
    assert crc.disagreements(n) == 0, n
