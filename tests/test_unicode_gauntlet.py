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

import pytest

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


def test_the_oracle_is_sound_on_the_mainframe_seed(tmp_path, monkeypatch):
    """Every ASCII cell (the seed re-encoded, or CRLF) passes: the gauntlet does not fail itself.

    Each cell is a full scan, so here the EBCDIC pages are one per family (US, German, Nordic, mixed
    CJK) -- the full suite runs on every OS, where a scan costs minutes, not seconds. unicode-gauntlet.yml
    runs every page."""
    monkeypatch.setattr(ug, "EBCDIC", ["cp037", "cp273", "cp277", "cp930"])
    monkeypatch.setattr(ug, "EBCDIC_SCRIPTS", {"nordic": ["cp277"], "german": ["cp273"]})
    results = ug.run(tmp_path / "no-corpus", {"mainframe"}, False, tmp_path / "work", jobs=2)
    ascii_cells = {cid: r["diffs"] for cid, r in results.items() if r["script"] == "ascii"
                   and r["encoding"] in ("utf-8", "utf-8-sig", "crlf")}  # fmt: skip
    assert set(ascii_cells) == {"mainframe|ascii|utf-8", "mainframe|ascii|utf-8-sig", "mainframe|ascii|crlf"}
    assert all(not d for d in ascii_cells.values()), ascii_cells
    assert any(r["script"] == "nordic" for r in results.values())  # the national-letter cells were built
    # #3816: the seed as raw fixed-block EBCDIC, its page declared, reads as the UTF-8 seed does
    ebcdic = {cid: r["diffs"] for cid, r in results.items() if r["script"] == "ascii" and r["encoding"] in ug.EBCDIC}
    assert set(ebcdic) == {f"mainframe|ascii|{cp}" for cp in ug.EBCDIC}
    assert all(not d for d in ebcdic.values()), ebcdic


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


# ---- #3816: raw EBCDIC -------------------------------------------------------------------------
@pytest.mark.parametrize("codec", ug.EBCDIC)
def test_a_fixed_block_download_reads_back_line_for_line(codec):
    """Every line padded to an 80-byte record, no line ends; the engine's declared read splits it."""
    from gitgalaxy.core.source_text import decode_source

    text = "       PROGRAM-ID. PGMA.\n\n       MOVE 'X' TO WS-A.\n"
    data = ug.fixed_block(text, codec)
    assert len(data) == 3 * ug.FB_LRECL and b"\n" not in data and b"\x15" not in data
    got = decode_source(data, declared=codec)
    assert got.how == "declared"
    assert [line.rstrip() for line in got.text.splitlines()] == text.splitlines()


def test_a_line_or_a_letter_that_does_not_fit_is_refused():
    assert ug.fixed_block("X" * (ug.FB_LRECL + 1), "cp037") is None  # longer than a card
    assert ug.fixed_block("MOVE '\u20ac' TO A.\n", "cp037") is None  # the euro sign is not in cp037
    assert ug.fixed_block("X" * ug.FB_LRECL + "\n", "cp037") is not None  # a full card fits


def test_a_kanji_line_is_padded_in_bytes_not_characters():
    """#3816 part 3a: on a mixed CJK page a Kanji is two bytes plus its shifts -- the record is 80 bytes."""
    data = ug.fixed_block("      * \u9867\u5ba2\u30de\u30b9\u30bf\n       PROGRAM-ID. PGMA.\n", "cp930")
    assert len(data) == 2 * ug.FB_LRECL and data[8:9] == b"\x0e"
    assert ug.fixed_block("*" + "\u540d" * 39 + "\n", "cp930") is None  # 1 + 1 + 78 + 1 = 81 bytes


def test_the_mainframe_seed_fits_a_card_image():
    """Every seed line, renamed with the longest national name, stays within 80 columns."""
    for path in (ug.HERE / "mainframe").rglob("*"):
        if path.is_file() and path.name != "names.json":
            assert all(len(line) <= ug.FB_LRECL for line in path.read_text(encoding="utf-8").splitlines()), path


def test_the_ebcdic_cells_are_in_the_sampled_plan_for_the_mainframe_seed_only(tmp_path):
    """CI runs the sampled plan: each EBCDIC page must be in it, national scripts in their own pages,
    and no rosetta language is ever written in EBCDIC."""
    seeds = {"mainframe": ug.HERE / "mainframe", "python": tmp_path / "seed_python"}
    (tmp_path / "seed_python").mkdir()
    (tmp_path / "seed_python" / "a.py").write_text("def calculate(x):\n    return x\n", encoding="utf-8")
    seed_facts = {"python/a.py": {"function_data": [("calculate",)]}}
    for lang, folder in seeds.items():  # run() writes the seed estate before it builds the cells
        ug._write(folder, tmp_path / "estates" / "seed" / lang, lambda t: t, "utf-8")
    cells = ug.build(seeds, seed_facts, tmp_path / "estates", full=False)
    ebcdic = {(c["language"], c["script"], c["encoding"]) for c in cells if c["encoding"] in ug.EBCDIC}
    assert {("mainframe", "ascii", cp) for cp in ug.EBCDIC} <= ebcdic
    assert {
        ("mainframe", "nordic", "cp277"),
        ("mainframe", "nordic", "cp278"),
        ("mainframe", "german", "cp273"),
    } <= ebcdic
    assert not {cell for cell in ebcdic if cell[0] != "mainframe"}
    # the estate keeps its reference's other languages, in UTF-8 as they are: `.inc` resolves by context
    python_copy = tmp_path / "estates" / "ascii__cp037" / "python" / "a.py"
    assert python_copy.read_bytes() == (tmp_path / "seed_python" / "a.py").read_bytes()
