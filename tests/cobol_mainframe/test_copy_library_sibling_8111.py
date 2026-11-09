"""#8111 slice 7: two census classes left on the non-candidate corpus, on authored fixtures (invented names).

1. A COPY member in a library directory BELOW the program directory (`app/lib1/MEMBER` beside `app/MAIN.cbl`) is COBOL
   on the library-directory evidence: one strong line, a paragraph with two verb statements (a PROCEDURE DIVISION
   fragment), or a chain of `COPY` lines. Prose and one-statement bodies stay unclaimed.
2. The census counts a member whose importer (or every holder) sits in a directory aperture drops as vendored as
   `vendored`, never as a resolver disagreement.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import copy_resolution_census as crc

from gitgalaxy.standards.language_lens import LanguageDetector
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

BANNER = "      * Fake banner line                                              *\n"
PROC = BANNER + "       FAKE-START.\n           PERFORM FAKE-NEXT.\n\n       FAKE-NEXT.\n           DISPLAY 'FAKE'.\n"
SEQ_PROC = "000100 FAKE-START.\n000200     MOVE 1 TO FAKE-ID.\n000300     PERFORM FAKE-NEXT.\n"
CHAIN = BANNER + "       COPY FAKEZ."  # no trailing newline
ITEM = "       05 FAKE-ID PIC 9.\n"
PROSE = "Fake notes.\n\nStep one.\n    Do this first.\n    Then that.\n"
ONE_STATEMENT = "       FAKE-START.\n           DISPLAY 'FAKE'.\n"
PROGRAM = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. FAKEMAIN.\n       PROCEDURE DIVISION.\n           GOBACK.\n"
)


@pytest.fixture(scope="module")
def detector():
    return LanguageDetector(LANGUAGE_DEFINITIONS, {})


def put(root: Path, rel: str, text: str) -> str:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return str(p)


@pytest.mark.parametrize("body", [PROC, SEQ_PROC, CHAIN, ITEM], ids=["proc", "seq-proc", "chain", "item"])
@pytest.mark.parametrize("sibling", ["app/MAIN.cbl", "app/lib1/OTHER.cpy"], ids=["parent", "own-dir"])
def test_a_library_member_beside_cobol_is_cobol(detector, tmp_path, body, sibling):
    put(tmp_path, sibling, PROGRAM)
    assert detector.focus(put(tmp_path, "app/lib1/FAKEA", body), body)[0] == "cobol"


@pytest.mark.parametrize("body", [PROSE, ONE_STATEMENT], ids=["prose", "one-statement"])
def test_weak_bodies_stay_unclaimed_even_beside_cobol(detector, tmp_path, body):
    put(tmp_path, "app/MAIN.cbl", PROGRAM)
    assert detector.focus(put(tmp_path, "app/lib1/FAKEA", body), body)[0] != "cobol"


@pytest.mark.parametrize("body", [PROC, CHAIN], ids=["proc", "chain"])
def test_no_cobol_in_the_directory_or_its_parent_is_no_claim(detector, tmp_path, body):
    put(tmp_path, "app/notes.txt", "fake\n")
    assert detector.focus(put(tmp_path, "app/lib1/FAKEA", body), body)[0] != "cobol"
    # two levels up is not a library path
    put(tmp_path, "top/MAIN.cbl", PROGRAM)
    assert detector.focus(put(tmp_path, "top/a/b/FAKEB", body), body)[0] != "cobol"


def census_repo(base: Path, vendored_dir: str) -> Path:
    repo = base / "zzfakerepo"
    put(repo, "LICENSE", "Fake License One\n")
    copy = "       COPY FAKEA.\n"
    put(repo, "app/MAIN.cbl", PROGRAM.replace("       PROCEDURE", copy + "       PROCEDURE"))
    put(repo, f"{vendored_dir}/FAKEA.cpy", ITEM)
    return repo


def test_a_member_held_only_in_a_vendored_dir_is_counted_apart(tmp_path):
    n = crc.census_repo(census_repo(tmp_path, "third_party_x"), lambda r: ({}, set()))
    assert (n["members"], n["vendored"], n["vendored:member"], n["miss"]) == (1, 1, 1, 0)
    assert crc.disagreements(n) == 0


def test_an_importer_in_a_vendored_dir_is_counted_apart(tmp_path):
    repo = census_repo(tmp_path, "lib")
    put(repo, "third_party_x/OLD.cbl", PROGRAM.replace("       PROCEDURE", "       COPY FAKEA.\n       PROCEDURE"))
    n = crc.census_repo(repo, lambda r: ({"app/MAIN.cbl": {"lib/FAKEA.cpy": set()}}, set()))
    assert (n["members"], n["agree"], n["vendored:importer"], crc.disagreements(n)) == (2, 1, 1, 0)


def test_an_ordinary_dir_miss_is_still_a_miss(tmp_path):
    n = crc.census_repo(census_repo(tmp_path, "lib"), lambda r: ({}, set()))
    assert (n["miss"], n["vendored"]) == (1, 0)
