"""#8074: the COPY search as a class. For every layout of an authored estate (invented names) the engine's census
must resolve each COPY the det translator's own search finds: a member in a copybook (a COPY or EXEC SQL INCLUDE
inside a copybook), a copybook with a program extension, a lowercase file or statement, a quoted file literal, a
member in a deep or dataset-named directory. One real scan; a disagreement is a `CopyUnresolved` refusal."""

import pytest
from scan_server import scan_to_db

from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir
from gitgalaxy.tools.cobol_to_java.det import source as SRC

BODY = "       01  {n}-REC.\n           05  {n}-ID   PIC X(8).\n"
INNER = "       COPY FAKEIN.\n"
INNER_SQL = "       EXEC SQL INCLUDE FAKESQ END-EXEC.\n"
# member -> (relative file, file text)
FILES = {
    "FAKEA": ("lib/FAKEA.cpy", BODY.format(n="FAKEA")),
    "FAKEB": ("lib/FAKEB.cbl", BODY.format(n="FAKEB")),  # a copybook with a program extension
    "FAKEC": ("lib/FAKEC.COB", BODY.format(n="FAKEC")),
    "FAKED": ("lib/fakeD.cpy", BODY.format(n="FAKED")),  # lowercase file, uppercase COPY
    "FAKEE": ("a/b/c/d/FAKEE.cpy", BODY.format(n="FAKEE")),
    "FAKEOUT": ("lib/FAKEOUT.cpy", BODY.format(n="FAKEOUT") + INNER + INNER_SQL),  # a copybook that COPYs
    "FAKEIN": ("other/FAKEIN.cpy", BODY.format(n="FAKEIN")),
    "FAKESQ": ("other2/FAKESQ.dcl", BODY.format(n="FAKESQ")),
    "FAKE-H1": ("lib/FAKE-H1.cpy", BODY.format(n="FAKEH")),
    "FAKEQ": ("lib/FAKEQ.cpy", BODY.format(n="FAKEQ")),
    "FAKER": ("src/FAKER.cpy", BODY.format(n="FAKER")),  # beside the program
    "FAKES": ("lib/FAKES.CPY", BODY.format(n="FAKES")),
    "FAKET": ("lib/FAKET.cpy", BODY.format(n="FAKET").replace("\n", "\r\n")),  # CRLF
    "1FAKEU": ("lib/1FAKEU.cpy", BODY.format(n="FAKEU")),  # digit-led member
    "FAKEV": ("FAKEV.cpy", BODY.format(n="FAKEV")),  # at the estate root
    "FAKEW": ("FAKELIB/FAKEW.cpy", BODY.format(n="FAKEW")),  # COPY FAKEW OF FAKELIB
    "FAKEX": ("lib/FAKEX.cpy", BODY.format(n="FAKEX")),  # a statement split over two lines
}
STATEMENTS = [
    "       COPY FAKEA.",
    "       COPY FAKEB.",
    "       COPY FAKEC.",
    "       COPY FAKED.",
    "       copy fakee.",
    "       COPY FAKEOUT.",
    "       COPY FAKE-H1.",
    '       COPY "FAKEQ.cpy".',
    "       COPY FAKER.",
    "       COPY FAKES REPLACING ==A== BY ==B==.",
    "       COPY FAKET.",
    "       COPY 1FAKEU.",
    "       COPY FAKEV.",
    "       COPY FAKEW OF FAKELIB.",
    "       COPY",
    "           FAKEX.",
]
PROG = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. FAKEPGM.\n       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    + "".join(s + "\n" for s in STATEMENTS)
    + "       PROCEDURE DIVISION.\n           GOBACK.\n"
)


@pytest.fixture(scope="module")
def estate(tmp_path_factory):
    base = tmp_path_factory.mktemp("copy8074m")
    repo = base / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "FAKEPGM.cbl").write_text(PROG)
    for rel, text in FILES.values():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text)
    return repo, load_galaxy_ir(scan_to_db(repo, base / "scan"))


@pytest.mark.parametrize(
    "member",
    [
        "FAKEA",
        "FAKEB",
        "FAKEC",
        "FAKED",
        "FAKEE",
        "FAKEOUT",
        "FAKE-H1",
        "FAKEQ",
        "FAKER",
        "FAKES",
        "FAKET",
        "1FAKEU",
        "FAKEV",
        "FAKEW",
        "FAKEX",
    ],
)
def test_the_program_copy_resolves_to_the_member_the_translator_finds(estate, member):
    repo, ir = estate
    copies = SRC.engine_copies_from_ir(ir, "src/FAKEPGM.cbl", repo)
    want = FILES[member][0]
    assert [p.relative_to(repo).as_posix() for p in copies.resolved[member]] == [want]
    assert not copies.gaps


@pytest.mark.parametrize("importer,member", [("lib/FAKEOUT.cpy", "FAKEIN"), ("lib/FAKEOUT.cpy", "FAKESQ")])
def test_a_copy_inside_a_copybook_resolves(estate, importer, member):
    _, ir = estate
    res = ir.copy_resolution(importer)["edges"]
    assert any(f.endswith(FILES[member][0]) for f in res.get(importer, [])), res


def test_the_translator_expands_the_whole_estate_program(estate):
    repo, ir = estate
    eng = SRC.engine_copies_from_ir(ir, "src/FAKEPGM.cbl", repo)
    lines = SRC.program_lines(repo / "src" / "FAKEPGM.cbl", [], eng)
    text = "\n".join(ln.text for ln in lines)
    for n in ("FAKEA", "FAKEB", "FAKEC", "FAKED", "FAKEE", "FAKEIN", "FAKEQ"):
        assert f"{n}-ID" in text, n
