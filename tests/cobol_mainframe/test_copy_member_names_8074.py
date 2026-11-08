"""#8074: a copy member whose name carries a national character (`@`, `#`, `$`: valid in a PDS member name) was
scanned, but the engine's COPY capture stopped at the character (`COPY FAKE@I.` read as `FAKE`), so no COPY edge was
drawn and the det translator refused `CopyUnresolved`. One real scan of an authored estate (invented names)."""

import pytest
from scan_server import scan_to_db

from gitgalaxy.core import cobol_preprocessor as PRE
from gitgalaxy.standards.language_standards.languages.cobol import DEFINITION as COBOL
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir
from gitgalaxy.tools.cobol_to_java.det import source as SRC

BODY = "       01  {n}-REC.\n           05  {n}-ID   PIC X(8).\n"
# COPY member -> (library dir, file name, item-name stem)
MEMBERS = {
    "FAKE@I": ("FAKE.APP.COPYLIB", "FAKE@I", "FAKEI"),
    "FAKE#J": ("FAKE.APP.COPYLIB", "FAKE#J.cpy", "FAKEJ"),
    "FAKE$K": ("FAKE.APP.CPYLIB", "FAKE$K", "FAKEK"),
    "@FAKEL": ("FAKE.APP.COPYLIB", "@FAKEL", "FAKEL"),
}
PROG = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. FAKEPGM.\n       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    + "".join(f"       COPY {m}.\n" for m in MEMBERS)
    + "       PROCEDURE DIVISION.\n           GOBACK.\n"
)


@pytest.fixture(scope="module")
def estate(tmp_path_factory):
    base = tmp_path_factory.mktemp("copy8074n")
    repo = base / "repo"
    (repo / "FAKE.APP.COBOL").mkdir(parents=True)
    (repo / "FAKE.APP.COBOL" / "FAKEPGM").write_text(PROG)
    for d, f, n in MEMBERS.values():
        (repo / d).mkdir(exist_ok=True)
        (repo / d / f).write_text(BODY.format(n=n))
    return repo, load_galaxy_ir(scan_to_db(repo, base / "scan"))


@pytest.mark.parametrize("m", MEMBERS)
def test_a_member_with_a_national_character_resolves(estate, m):
    repo, ir = estate
    _, f, _ = MEMBERS[m]
    copies = SRC.engine_copies_from_ir(ir, "FAKE.APP.COBOL/FAKEPGM", repo)
    assert [p.name for p in copies.resolved[m]] == [f]
    assert not copies.gaps


def test_the_engine_capture_reads_the_name_the_translator_reads():
    cap = COBOL["rules"]["_dependency_capture"]
    for m in MEMBERS:
        assert cap.search(f"       COPY {m}.\n").group(1) == m
        assert cap.search(f"           EXEC SQL INCLUDE {m} END-EXEC.\n").group(1) == m
    assert all(c in PRE._NAME_START for c in "@#$")
