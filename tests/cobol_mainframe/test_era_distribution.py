"""#5117: era distributions of non-burned estates are committed as COUNTS ONLY (no per-program data)."""

import json
import re
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import era_distribution as ed  # tests/tools/era_distribution.py
import support_matrix as sm  # tests/tools/support_matrix.py

SUMMARY = {
    "programs": 3,
    "by_era": {"0": 0, "1": 1, "2": 1, "3": 0, "4": 0, "none": 1},
    "mixed": 0,
    "tells": {"resp": 1},
}


def test_counts_only_drops_everything_but_the_allowed_keys():
    out = ed.counts_only({**SUMMARY, "programs_list": ["A.cbl"], "raised_by_copybook": 1})
    assert set(out) <= set(ed.KEYS)
    assert out["raised_by_copybook"] == 1 and "programs_list" not in out


def test_counts_only_adds_the_optional_key_only_when_present():
    assert "raised_by_copybook" not in ed.counts_only(SUMMARY)


def test_census_label_is_opaque_and_stable():
    a = ed.census_label("some-census-repo")
    assert a == ed.census_label("some-census-repo") and a != ed.census_label("other-census-repo")
    assert re.fullmatch(r"census-[0-9a-f]{6}", a) and "some" not in a


def test_a_burned_root_is_refused(tmp_path):
    with pytest.raises(SystemExit, match="burned"):
        ed.collect({"cics-genapp": tmp_path}, None, tmp_path / "none")


def test_collect_labels_census_clones_and_skips_burned_ones(tmp_path, monkeypatch):
    census = tmp_path / "census"
    for n in ("alpha-repo", "zecs", "_scans", ".hidden"):
        (census / n).mkdir(parents=True)
    (census / "a-file").write_text("x")
    monkeypatch.setattr(ed, "distribution", lambda d, db: dict(SUMMARY))
    got = ed.collect({}, census, tmp_path / "no-corpora")
    assert list(got) == [ed.census_label("alpha-repo")]
    assert got[ed.census_label("alpha-repo")]["kind"] == "census"
    assert "alpha" not in json.dumps(got)


def test_collect_takes_the_pinned_non_burned_corpora(tmp_path, monkeypatch):
    (tmp_path / "dsf").mkdir()
    (tmp_path / "cics-genapp").mkdir()  # burned: never picked up as a pinned non-burned estate
    monkeypatch.setattr(ed, "distribution", lambda d, db: dict(SUMMARY))
    got = ed.collect({}, None, tmp_path)
    assert list(got) == ["dsf"] and got["dsf"]["kind"] == "pinned"


def test_distribution_end_to_end_names_no_program(tmp_path):
    """A real scan: a RESP program, an untagged one, and an ISPF screen dump saved as .cbl (NotCobol, once a crash)."""
    est = tmp_path / "secretly-named-estate"
    est.mkdir()
    head = "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. {}.\n       PROCEDURE DIVISION.\n"
    (est / "SECRETA.cbl").write_text(
        head.format("SECRETA") + "           EXEC CICS RETURN RESP(WS-R) END-EXEC.\n           GOBACK.\n"
    )
    (est / "SECRETB.cbl").write_text(head.format("SECRETB") + "           GOBACK.\n")
    (est / "SECRETC.cbl").write_text(
        " File  Edit  Confirm  Menu  Utilities  Compilers  Test  Help\n"
        " EDIT       USER.SRC(X) - 01.00                      Columns 00001 00072\n"
        " Command ===>                                          Scroll ===> CSR\n"
        " ****** ***************************** Top of Data ******************************\n"
    )
    out = ed.distribution(est, tmp_path / "db")
    assert out["programs"] == 3 and out["by_era"]["2"] == 1 and out["by_era"]["none"] == 2
    assert not re.search(r"SECRET|secretly", json.dumps(out))


def test_committed_summary_has_counts_only_and_no_burned_name():
    data = ed.load()
    burned = {b.lower() for b in ed.burned_names()}
    for label, e in data["estates"].items():
        assert label.lower() not in burned
        assert e["kind"] in ("pinned", "census")
        assert set(e) <= {"kind", *ed.KEYS}
        assert sum(e["by_era"].values()) == e["programs"] and e["mixed"] <= e["programs"]
        assert e["kind"] == "pinned" or re.fullmatch(r"census-[0-9a-f]{6}", label)
        assert not re.search(r"\.(cbl|cob|cobol|cpy)\b|/", json.dumps(e))


def test_support_matrix_renders_the_counts_only_table():
    lines = sm.render_non_burned_eras({"census-aaaaaa": {"kind": "census", **SUMMARY}})
    text = "\n".join(lines)
    assert "counts only" in text.lower()
    assert "| census-aaaaaa | 3 | 0 | 1 | 1 | 0 | 0 | 1 | 0 |" in text


def test_support_matrix_render_omits_the_section_when_nothing_is_committed():
    m = {"catalogue": None, "estates": {}}
    assert "non-burned" not in sm.render(m)
    m["non_burned_eras"] = {"census-aaaaaa": {"kind": "census", **SUMMARY}}
    assert "Era, non-burned estates" in sm.render(m)
