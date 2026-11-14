"""#8412 [c:e1e3afb8]: the det translator's fallback COPY search (`source._search_member`) tries fewer extensions than
the engine scans (it lacks .cobol, .pco, .cut and body-judged .inc). It is never reached for an estate member: an
engine-resolved member is taken from the engine whatever its extension, and a member the engine resolved nothing for
but the fallback finds in the estate is refused (`CopyUnresolved`), never spliced in. One real scan of an authored
estate (invented names) backs the tests."""

import pytest

from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir
from gitgalaxy.tools.cobol_to_java.det import source as SRC
from scan_server import scan_to_db

# extensions the engine scans as COBOL (or judges by body) that COPY_EXTS does not try
EXTRA = {"FAKEG": "FAKEG.cobol", "FAKEH": "FAKEH.pco", "FAKEI": "FAKEI.cut", "FAKEJ": "FAKEJ.inc"}
BODY = "       01  {n}-REC.\n           05  {n}-ID   PIC X(8).\n"
PROG = (
    "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. FAKEPGM.\n       DATA DIVISION.\n"
    "       WORKING-STORAGE SECTION.\n"
    + "".join(f"       COPY {m}.\n" for m in EXTRA)
    + "       PROCEDURE DIVISION.\n           GOBACK.\n"
)


@pytest.fixture(scope="module")
def estate(tmp_path_factory):
    base = tmp_path_factory.mktemp("copy8412")
    repo = base / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "FAKEPGM.cbl").write_text(PROG)
    (repo / "lib").mkdir()
    for m, f in EXTRA.items():
        (repo / "lib" / f).write_text(BODY.format(n=m))
    return repo, load_galaxy_ir(scan_to_db(repo, base / "scan"))


def test_the_fallback_really_lacks_these_extensions():
    tried = {e.lower() for e in SRC.COPY_EXTS if e}
    assert not tried & {"." + f.rsplit(".", 1)[1].lower() for f in EXTRA.values()}


def test_engine_resolved_member_never_reaches_the_fallback(estate, monkeypatch):
    repo, ir = estate
    copies = SRC.engine_copies_from_ir(ir, "src/FAKEPGM.cbl", repo)
    assert {m: [p.name for p in v] for m, v in copies.resolved.items()} == {m: [f] for m, f in EXTRA.items()}

    def boom(*a, **k):
        raise AssertionError("the fallback COPY search ran for an engine-resolved member")

    monkeypatch.setattr(SRC, "_search_member", boom)
    lines = SRC.program_lines(repo / "src" / "FAKEPGM.cbl", [repo / "src"], copies)
    text = "\n".join(ln.text for ln in lines)
    assert all(f"{m}-REC" in text for m in EXTRA)


def test_fallback_hit_on_an_estate_file_the_engine_missed_is_refused(estate):
    repo, ir = estate
    copies = SRC.engine_copies_from_ir(ir, "src/FAKEPGM.cbl", repo)
    # the engine resolved nothing for FAKEG, and the fallback (a .cpy twin outside the engine's view) finds an estate file
    (repo / "src" / "FAKEG.cpy").write_text(BODY.format(n="FAKEG"))
    try:
        gap = SRC.EngineCopies.of(copies.program, repo, {"src/FAKEPGM.cbl": {}})
        with pytest.raises(SRC.CopyUnresolved):
            SRC.program_lines(repo / "src" / "FAKEPGM.cbl", [repo / "src"], gap)
    finally:
        (repo / "src" / "FAKEG.cpy").unlink()


def test_without_an_engine_an_extra_extension_is_not_found_not_misread(estate):
    repo, _ = estate
    with pytest.raises(SRC.CopyNotFound):
        SRC.program_lines(repo / "src" / "FAKEPGM.cbl", [repo / "lib"])
