"""#8074: a `CopyUnresolved` refusal ("the engine resolved nothing; the estate holds X") names WHY the engine's
census lacks a member the translator found: an ancestor directory the aperture prunes, a file the aperture
excludes, or a file the aperture admits that the language lens did not claim. Authored fixtures, invented names."""

from pathlib import Path

import pytest

from gitgalaxy.tools.cobol_to_java.det import source as SRC

COPYBOOK = "       01  FAKE-REC.\n           05  FAKE-ID   PIC X(8).\n"


def _refusal(tmp_path: Path, rel: str) -> str:
    root = tmp_path / "repo"
    member = root / rel
    member.parent.mkdir(parents=True, exist_ok=True)
    member.write_text(COPYBOOK)
    prog = root / "FAKE.APP.COBOL" / "FAKEPGM.cbl"
    prog.parent.mkdir(parents=True, exist_ok=True)
    prog.write_text("       PROGRAM-ID. FAKEPGM.\n")
    eng = SRC.EngineCopies.of(prog, root, {})
    with pytest.raises(SRC.CopyUnresolved) as ei:
        eng.unresolved("FAKE.APP.COBOL/FAKEPGM.cbl", "FAKECPY", member, "FAKEPGM")
    return str(ei.value)


@pytest.mark.parametrize("rel", ["node_modules/lib/FAKECPY.cpy", "vendor/x/node_modules/FAKECPY.cpy"])
def test_a_member_under_an_excluded_directory_names_the_directory(tmp_path, rel):
    msg = _refusal(tmp_path, rel)
    assert "the engine resolved nothing; the estate holds " + rel in msg
    assert "cause: directory " in msg and "path rules" in msg


@pytest.mark.parametrize("rel", ["FAKE.APP.COPYLIB/FAKECPY.png", "FAKE.APP.COPYLIB/FAKECPY.exe"])
def test_a_member_the_aperture_excludes_names_the_aperture(tmp_path, rel):
    msg = _refusal(tmp_path, rel)
    assert "cause: the aperture excludes the member" in msg


@pytest.mark.parametrize("rel", ["FAKE.APP.COPYLIB/FAKECPY.cpy", "COPYLIB/FAKECPY", "FAKE.APP.DCLGEN/FAKECPY"])
def test_a_member_the_aperture_admits_names_the_language_lens(tmp_path, rel):
    msg = _refusal(tmp_path, rel)
    assert "the aperture admits the member; the language lens did not claim it as COBOL" in msg


def test_a_member_outside_the_estate_is_still_no_refusal(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    prog = root / "FAKE.APP.COBOL" / "FAKEPGM.cbl"
    prog.parent.mkdir()
    prog.write_text("       PROGRAM-ID. FAKEPGM.\n")
    outside = tmp_path / "elsewhere" / "FAKECPY.cpy"
    assert (
        SRC.EngineCopies.of(prog, root, {}).unresolved("FAKE.APP.COBOL/FAKEPGM.cbl", "FAKECPY", outside, "FAKEPGM")
        is None
    )
