"""#3834: the Cultural Gauntlet (part 1: source dialect x data code page, checked statically).

The gauntlet's sampled plan runs clean against its ratchet; a broken oracle is caught as a NEW failing
cell; the seed survives the trip through fixed-block EBCDIC in every page and every dialect; and the
zoned-sign oracle is independent of the converter -- IBM's overpunch bytes decoded by the page, and
the national zero signs pinned from IBM CDRA.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import cultural_gauntlet as cg

from gitgalaxy.core.source_text import decode_source


@pytest.fixture(scope="module")
def sampled(tmp_path_factory):
    """The CI run: the default (sampled) plan, --ci against the committed baseline."""
    base = tmp_path_factory.mktemp("cultural_gauntlet")
    code = cg.main(["--ci", "--out", str(base / "out"), "--work", str(base / "work")])
    results = json.loads((base / "out" / "results.json").read_text(encoding="utf-8"))
    return code, results, (base / "out" / "report.md").read_text(encoding="utf-8")


def test_the_sampled_plan_passes_its_ratchet(sampled):
    code, results, report = sampled
    assert code == 0
    assert "| dialect | utf8 | cp037 |" in report and "skipped" in report
    # every page ran, and '£' met every page: the dialect that moves between pages
    ran = {(r["dialect"], r["page"]) for r in results.values() if "skipped" not in r}
    assert {("currency_pound", p) for p in cg.PAGES} <= ran
    assert {d for d, _ in ran} == set(cg.DIALECTS) and all((d, cg.CONTROL) in ran for d in cg.DIALECTS)
    # the euro sign is in none of the pre-euro pages: skipped and counted, never failed
    euro = [r for r in results.values() if r["dialect"] == "currency_euro" and r["page"] != cg.CONTROL]
    assert euro and all("skipped" in r and not r["diffs"] for r in euro)


def test_the_code_page_checks_pass_in_every_page(sampled):
    """The generated CobolRecords overpunches as each page does, and the scan reads each page's
    source to the declared facts: the oracle is sound where the converter is right."""
    _, results, _ = sampled
    for page in cg.PAGES:
        for group in ("records", "facts"):
            assert results[f"currency_pound|{page}|{group}"]["diffs"] == [], (page, group)


def test_a_broken_oracle_is_a_new_failing_cell(monkeypatch, tmp_path, capsys):
    monkeypatch.setitem(cg.DIALECTS["plain"]["expect"], "limit_literal", "12345.68")
    code = cg.main(["--ci", "--full", "--only", "plain", "--pages", "cp273", "--work", str(tmp_path)])
    assert code == 1
    assert (
        "NEW FAILING CELL plain|cp273|facts: WS-LIMIT VALUE: want '12345.68', got '12345.67'" in capsys.readouterr().out
    )


def _canned(monkeypatch, failing: dict, baseline: dict, tmp_path):
    monkeypatch.setattr(cg, "BASELINE", tmp_path / "baseline.txt")
    cg.write_baseline(baseline)
    results = {cid: {"dialect": "plain", "page": "cp037", "group": "facts", "diffs": [d] if d else []}
               for cid, d in failing.items()}  # fmt: skip
    monkeypatch.setattr(cg, "run", lambda *_, **__: results)


def test_the_ratchet_is_the_unicode_gauntlets(monkeypatch, tmp_path, capsys):
    """A listed failure passes CI, a new one fails it, a listed cell that now passes asks for the
    baseline to be lowered without failing, and a listed cell this run did not run is left alone."""
    _canned(monkeypatch, {"a|cp037|facts": "x", "b|cp037|facts": ""}, {"a|cp037|facts": "x", "b|cp037|facts": "y",
                                                                       "c|cp297|facts": "z"}, tmp_path)  # fmt: skip
    assert cg.main(["--ci", "--work", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "1 baseline cells now pass -- lower the baseline" in out and "b|cp037|facts" in out
    assert "c|cp297|facts" not in out
    _canned(monkeypatch, {"a|cp037|facts": "x", "d|cp037|facts": "new"}, {"a|cp037|facts": "x"}, tmp_path)
    assert cg.main(["--ci", "--work", str(tmp_path)]) == 1
    assert "NEW FAILING CELL d|cp037|facts: new" in capsys.readouterr().out


def test_the_baseline_is_one_mergeable_line_per_cell(monkeypatch, tmp_path):
    monkeypatch.setattr(cg, "BASELINE", tmp_path / "baseline.txt")
    cg.write_baseline({"b|cp037|ticket": "multi\nline", "a|cp273|facts": "one"})
    body = [x for x in (tmp_path / "baseline.txt").read_text(encoding="utf-8").splitlines() if not x.startswith("#")]
    assert body == ["a|cp273|facts\tone", "b|cp037|ticket\tmulti line"]
    attrs = (Path(__file__).resolve().parents[2] / ".gitattributes").read_text(encoding="utf-8")
    assert "tests/cultural_gauntlet/baseline.txt merge=union" in attrs


def test_every_committed_baseline_cell_is_a_cell_of_the_full_plan():
    cells = {f"{d}|{c}|{g}" for d, c in cg.plan(full=True) for g in cg.GROUPS}
    assert set(cg.read_baseline()) <= cells


# ---- the seed as raw EBCDIC ---------------------------------------------------------------------
@pytest.mark.parametrize("page", cg.PAGES)
@pytest.mark.parametrize("dialect", sorted(cg.DIALECTS))
def test_the_seed_reads_back_from_fixed_block_ebcdic(dialect, page):
    """80-byte card images, no line ends, read back through the engine's declared decode; a dialect
    character the page lacks (the euro sign) refuses the cell rather than mangling it."""
    text = cg.seed_text(dialect)
    data = cg.encode(text, page)
    if "€" in text:
        assert data is None
        return
    assert data is not None and len(data) == 80 * len(text.splitlines()) and b"\n" not in data
    got = decode_source(data, declared=page)
    assert got.how == "declared"
    assert [line.rstrip() for line in got.text.splitlines()] == text.splitlines()


def test_the_dialect_meets_the_page():
    """'£' is a different byte in each page (0xB1 US, 0x5B UK, where the US page keeps `$`)."""
    line = "           CURRENCY SIGN IS '£'."
    assert cg.encode(line, "cp037")[29] == 0xB1 and cg.encode(line, "cp285")[29] == 0x5B
    assert cg.encode("$", "cp285")[0] == 0x4A and cg.encode("$", "cp037")[0] == 0x5B  # padded to a card


# ---- the zoned-sign oracle ----------------------------------------------------------------------
@pytest.mark.parametrize("page", cg.PAGES)
def test_the_overpunch_characters_are_the_pages_own(page):
    """The page's codec shows IBM's sign bytes as CDRA says: the zero signs move, A-I / J-R do not."""
    plus, minus = cg.CDRA_ZERO_SIGNS[page]
    assert cg.POSITIVE_BYTES.decode(page) == plus + "ABCDEFGHI"
    assert cg.NEGATIVE_BYTES.decode(page) == minus + "JKLMNOPQR"


def test_the_sign_check_names_each_value_a_codec_gets_wrong():
    us = (
        'private static final String POSITIVE = "{ABCDEFGHI";\n    private static final String NEGATIVE = "}JKLMNOPQR";'
    )
    assert cg._sign_diffs(us, "cp037") == []
    diffs = cg._sign_diffs(us, "cp277")  # the US table on a Danish page: only +0 and -0 differ
    assert diffs == ["CobolRecords +0: cp277 byte 0xC0 is 'æ', the codec overpunches '{'",
                     "CobolRecords -0: cp277 byte 0xD0 is 'å', the codec overpunches '}'"]  # fmt: skip
    escaped = us.replace('"{', '"\\u00e4').replace('"}', '"\\u00fc')  # the forge escapes non-ASCII
    assert cg._sign_diffs(escaped, "cp273") == []
