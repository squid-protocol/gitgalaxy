"""#3812: the Unicode Gauntlet's own machinery.

The transforms (names renamed only as whole words, path and content alike; the ASCII twin of a
script word; encodings that cannot hold a text refused, not mangled) and the oracle (facts
compared with the renaming applied, JSON-valued columns as data) are pinned here. One real run
on the mainframe seed checks that the oracle is sound: every ASCII cell -- the seed only
re-encoded or given Windows line endings -- must pass, or the gauntlet is measuring itself.
"""

import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
import unicode_gauntlet as ug  # noqa: E402


def test_a_rename_touches_whole_names_only():
    rename = ug.renamer({"PGMA": "PGMAÆØÅ", "CUSTA": "CUSTAÆØÅ"}, "A-Za-z0-9_@#$\\-ÆØÅÄÖÜ")
    assert rename("CALL PGMA; X-PGMA PGMAB PROD.CUSTA.DATA") == "CALL PGMAÆØÅ; X-PGMA PGMAB PROD.CUSTAÆØÅ.DATA"
    assert rename("pli/PGMA.pli") == "pli/PGMAÆØÅ.pli"  # paths too: an include resolves by its member name


def test_the_ascii_twin_keeps_the_shape():
    assert ug.ascii_twin("ÆØÅ") == "XXX" and ug.ascii_twin("éèç") == "xxx"
    assert ug.ascii_twin(unicodedata.normalize("NFD", "é")) == "x"  # the combining accent is not a letter
    assert ug.ascii_twin("名前") == "xx"


def test_a_name_limit_is_kept_and_collisions_are_separated():
    assert ug.variant_name("PROBEIO", "ÆØÅ", 8) == "PROBEÆØÅ"
    m = ug._mapping(["PROBETEST", "PROBETEL"], "ÆØÅ", 8)
    assert m is not None and len(set(m.values())) == 2 and all(len(v) <= 8 for v in m.values())


def test_an_encoding_that_cannot_hold_the_text_is_refused():
    assert ug.encode("名前", "cp1252") is None
    assert ug.encode("a\nb\n", "crlf") == b"a\r\nb\r\n"
    assert ug.encode("é", "utf-16-be").startswith(b"\xfe\xff")


def test_json_columns_compare_as_data():
    assert ug._norm('["probe\\u0627"]') == ug._norm('["probeا"]')


def test_the_diff_names_what_moved():
    want = {"x/a.py": {"language": "python", "ints": {"function_count": 3}, **{c: [] for c in ug.CHANNELS}}}
    got = {"x/a.py": {"language": "python", "ints": {"function_count": 0}, **{c: [] for c in ug.CHANNELS}}}
    assert ug.diff_cell(want, got) == ["x/a.py: function_count 3 -> 0"]
    assert ug.diff_cell(want, {}) == ["x/a.py: missing file"]


def test_the_oracle_is_sound_on_the_mainframe_seed(tmp_path):
    """Every ASCII cell (the seed re-encoded, or CRLF) passes: the gauntlet does not fail itself."""
    results = ug.run(tmp_path / "no-corpus", {"mainframe"}, False, tmp_path / "work", jobs=2)
    ascii_cells = {cid: r["diffs"] for cid, r in results.items() if r["script"] == "ascii"
                   and r["encoding"] in ("utf-8", "utf-8-sig", "crlf")}  # fmt: skip
    assert set(ascii_cells) == {"mainframe|ascii|utf-8", "mainframe|ascii|utf-8-sig", "mainframe|ascii|crlf"}
    assert all(not d for d in ascii_cells.values()), ascii_cells
    assert any(r["script"] == "nordic" for r in results.values())  # the national-letter cells were built


def test_the_baseline_is_one_mergeable_line_per_cell(tmp_path, monkeypatch):
    """One `cell<TAB>difference` line per failing cell, no counts, merged by git as a union
    (.gitattributes): two PRs fixing different cells merge cleanly; a stale line is harmless."""
    monkeypatch.setattr(ug, "BASELINE", tmp_path / "baseline.txt")
    ug.write_baseline({"b|x|utf-8": "b/a: function_data missing [('f',\n 'doc\tline')]", "a|x|utf-8": "a/a: n 3 -> 0"})
    lines = (tmp_path / "baseline.txt").read_text(encoding="utf-8").splitlines()
    body = [line for line in lines if not line.startswith("#")]
    assert body == ["a|x|utf-8\ta/a: n 3 -> 0", "b|x|utf-8\tb/a: function_data missing [('f', 'doc line')]"]
    assert ug.read_baseline() == {
        "a|x|utf-8": "a/a: n 3 -> 0",
        "b|x|utf-8": "b/a: function_data missing [('f', 'doc line')]",
    }
    attrs = (Path(__file__).resolve().parents[1] / ".gitattributes").read_text(encoding="utf-8")
    assert "tests/unicode_gauntlet/baseline.txt merge=union" in attrs
    assert ug.ROSETTA_REF.read_text(encoding="utf-8").strip()  # the pinned corpus commit CI checks out


def test_a_legacy_cjk_estate_is_scanned_with_its_code_page_declared(tmp_path, monkeypatch):
    """#3878: Shift-JIS / GB18030 cannot be told from cp1252 by their bytes, so a real estate
    declares them; the gauntlet scans those estates the same way, and nothing else declared."""
    import gitgalaxy.tools.cobol_to_cobol.galaxy_ir as gir

    seen = {}
    monkeypatch.setattr(
        gir, "scan_to_db", lambda estate, out, extra_args=(): seen.update({estate.name: tuple(extra_args)})
    )
    for name in ("han__shift_jis", "kana__gb18030", "han__cp1252", "ascii__utf-16", "twin__han", "seed"):
        ug.scan(tmp_path / name, tmp_path / "out")
    assert seen == {
        "han__shift_jis": ("--source-encoding", "shift_jis"),
        "kana__gb18030": ("--source-encoding", "gb18030"),
        "han__cp1252": (),
        "ascii__utf-16": (),
        "twin__han": (),
        "seed": (),
    }
