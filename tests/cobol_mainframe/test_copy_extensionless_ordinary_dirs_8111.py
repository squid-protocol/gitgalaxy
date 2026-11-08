"""#8111: an extensionless COPY member in a directory with no library qualifier (`src/`, `testing/`, `lib/x/`) was
labelled another language, so the engine drew no COPY edge. Its COBOL body proves it. The lens tests cover the whole
input class (shapes, names, negatives); one real scan of an authored estate (invented names) backs the edge."""

import pytest

from gitgalaxy.standards.language_lens import LanguageDetector
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir
from gitgalaxy.tools.cobol_to_java.det import source as SRC
from scan_server import scan_to_db

ITEMS = "       05 FAKE-ID PIC 9.\n       05 FAKE-AMT PIC S9(5)V99 COMP-3.\n"
GROUP = "       01  FAKE-REC.\n        05  FAKE-STATUS PIC X(20) VALUE SPACES.\n"
SEQ = "000100     05  FAKE-ID     PIC 9(4).                                   FAKE1\n000200     05  FAKE-NM     PIC X(8).                                   FAKE1\n"
DIVISION = "       WORKING-STORAGE SECTION.\n       77  FAKE-CNT  PIC 9(3).\n"
NO_NEWLINE = "       05 TAG-ID PIC 9.\n       05 TAR-ID PIC 9."
LOWER = "       05 fake-id pic 9.\n       05 fake-nm pic x(8).\n"
POSITIVES = {
    "items": ITEMS,
    "group": GROUP,
    "sequence-area": SEQ,
    "section": DIVISION,
    "no-final-newline": NO_NEWLINE,
    "lowercase": LOWER,
}
NAMES = ["FAKEA", "fakeb", "FAKE#C", "FAKE@D", "FAKE$E", "FAKE_F", "FAKE-G", "F1"]
DIRS = ["src", "testing", "lib/cobol-shared", "a/b/c/d/e/f/g", "include", "Copy Members"]


@pytest.fixture(scope="module")
def detector():
    return LanguageDetector(LANGUAGE_DEFINITIONS, {})


@pytest.mark.parametrize("shape", POSITIVES)
@pytest.mark.parametrize("d", DIRS)
def test_every_body_shape_is_claimed_in_every_ordinary_directory(detector, d, shape):
    assert detector.focus(f"{d}/FAKEA", POSITIVES[shape])[0] == "cobol"


@pytest.mark.parametrize("name", NAMES)
def test_every_member_name_shape_is_claimed(detector, name):
    assert detector.focus(f"src/{name}", GROUP)[0] == "cobol"


@pytest.mark.parametrize(
    ("path", "text"),
    [
        ("src/README", "Build notes\nrun it twice.\n"),
        ("src/CHANGES", "01 Introduction.\n02 Setup.\n03 Usage.\n"),
        ("src/STRAY", "       05 FAKE-ID PIC 9.\nnothing else here\n"),
        ("src/FAKEH", "#define FAKEH_MAX 8\nint fakeh_count(void);\n"),
        ("src/run", "#!/bin/sh\necho 01 PIC\n"),
        ("src/BLOB", "\x00\x01\x02 PIC 9\x00"),
        ("src/notes.txt", ITEMS),
        ("src/FAKEPGM.dat", GROUP),
        ("src/has space", GROUP),
        ("src/" + "N" * 31, GROUP),
    ],
)
def test_text_that_is_not_a_member_is_not_claimed(detector, path, text):
    assert detector.focus(path, text)[0] != "cobol"


def test_library_directory_member_still_routes_on_a_configuration_section_opening(detector):
    text = "000100 CONFIGURATION SECTION.                                           FAKE1\n000200 SOURCE-COMPUTER.\n"
    assert detector.focus("FAKE.APP.COPYBOOK/FAKEA", text)[0] == "cobol"


PROG = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. FAKEPGM.\n       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    + "".join(f"       COPY {m}.\n" for m in ("ITEMS", "GROUPX", "SEQNCE"))
    + "       PROCEDURE DIVISION.\n           GOBACK.\n"
)


@pytest.fixture(scope="module")
def estate(tmp_path_factory):
    base = tmp_path_factory.mktemp("copy8111")
    repo = base / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "FAKEPGM.cbl").write_text(PROG)
    (repo / "testing").mkdir()
    (repo / "testing" / "ITEMS").write_text(ITEMS)
    (repo / "lib" / "shared").mkdir(parents=True)
    (repo / "lib" / "shared" / "GROUPX").write_text(GROUP)
    (repo / "src" / "SEQNCE").write_text(SEQ)
    (repo / "src" / "README").write_text("Notes on this estate.\nOwner: nobody.\n")
    return repo, load_galaxy_ir(scan_to_db(repo, base / "scan"))


def test_the_engine_draws_an_edge_to_each_ordinary_directory_member(estate):
    repo, ir = estate
    copies = SRC.engine_copies_from_ir(ir, "src/FAKEPGM.cbl", repo)
    assert {m: [p.parent.name for p in ps] for m, ps in copies.resolved.items()} == {
        "ITEMS": ["testing"],
        "GROUPX": ["shared"],
        "SEQNCE": ["src"],
    }


def test_a_readme_beside_the_members_is_not_claimed(estate):
    _, ir = estate
    assert "src/README" not in ir.files or ir.files["src/README"].language != "cobol"
