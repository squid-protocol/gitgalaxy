"""#5280: programs that cannot reach L1 for a non-translator reason (source defect, not COBOL, owner-held) are reported
in their own rows with a reachable denominator; none leaves the fixed denominator."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ladder_exclusions as lx
import progress_report as pr

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "evidence_report"
REPORTS = {d.name: json.loads((d / "report.json").read_text("utf-8")) for d in FIXTURES.iterdir() if d.is_dir()}


def rows(estate, *named):
    return [{"program": n, "level": lv} for n, lv in named]


def test_every_entry_has_a_known_kind_and_names_its_issue():
    assert set(lx.KIND_LABEL) == set(lx.KINDS)
    for (estate, base), e in lx.EXCLUSIONS.items():
        assert e["kind"] in lx.KINDS and e["issue"].startswith("#") and e["reason"], (estate, base)
        assert base == base.lower()
    assert [sum(e["kind"] == k for e in lx.EXCLUSIONS.values()) for k in lx.KINDS] == [2, 1, 2]


def test_lookup_matches_the_basename_whatever_the_path_and_case():
    assert lx.lookup("zecs", "Source/ZECS002.asm")["kind"] == "not_cobol"
    assert lx.lookup("zecs", "Source/ZECS002.asm")["issue"] == "#5859"
    assert lx.lookup("zecs", "ZECSNC.ASM") is None  # lowered and translated since #6826: core work, not a held member
    assert lx.lookup("zecs", "Source/ZECS001.cbl") is None  # a translator hole, core work (#5945)
    assert lx.lookup("cics-genapp", "ZECS002.asm") is None  # the estate is part of the key


def test_summarize_counts_l0_entries_by_kind_and_reports_a_risen_entry_as_stale():
    out = lx.summarize(
        {
            "zecs": rows(
                "zecs", ("Source/ZECS002.asm", "L0"), ("Source/ZECSNC.asm", "L0"), ("Source/ZECS000.cbl", "L1")
            ),
            "aws-mainframe-modernization-carddemo": rows("c", ("app/cbl/CBEXPORT.cbl", "L0")),
        }
    )
    assert out["count"] == 2 and list(out["kinds"]) == ["source_defect", "not_cobol"]
    assert "stale" not in out and out["kinds"]["not_cobol"]["programs"] == ["zecs/Source/ZECS002.asm"]
    risen = lx.summarize({"zecs": rows("zecs", ("Source/ZECS002.asm", "L1"))})  # lowered later: the entry is stale
    assert risen["count"] == 0 and risen["stale"] == ["zecs/Source/ZECS002.asm"]


def test_summarize_is_none_when_no_entry_matches():
    assert lx.summarize({"cics-genapp": rows("g", ("A.cbl", "L0"))}) is None


def build(reports):
    """The page from the given estate reports, with every other component empty (no translator read, no clock)."""
    return pr.build(reports, {}, {}, [], {"rules": []}, {"ports": []}, {"programs": {}}, {}, None, "abc")


@pytest.fixture
def report():
    return build(REPORTS)


def test_the_progress_page_shows_the_reachable_denominator_beside_the_fixed_one(report):
    t = report["ladder"]["total"]
    n = sum(len(r["programs"]) for r in REPORTS.values())
    listed = sum(
        1 for e, r in REPORTS.items() for p in r["programs"] if lx.lookup(e, p["program"]) and p["level"] == "L0"
    )
    assert t["programs"] == n and listed >= 4  # the fixtures hold CBEXPORT, CBIMPORT, epscsmrd, epsmpmt
    assert t["unreachable"]["count"] == listed and t["reachable"] == n - listed
    text = pr.render(report)
    assert f"Reachable denominator: {n - listed} programs ({n} - " in text
    for label in ("source defect (source IBM rejects)", "held by an owner ruling or z/OS calibration"):
        assert label in text
    assert "#5866" in text and "#5867" in text and "#5106" in text
    assert json.loads(pr.render_json(report))["ladder"]["total"]["reachable"] == n - listed


def test_the_page_without_any_entry_prints_no_reachable_line():
    rep = build({"cics-genapp": {"programs": [{"program": "A.cbl", "level": "L0", "translation": {"whole": False}}]}})
    assert "reachable" not in rep["ladder"]["total"]
    assert "Reachable denominator" not in pr.render(rep)


def test_the_evidence_report_names_a_source_defect_and_only_an_entry_gets_the_note():
    import evidence_report as er

    def tr(whole=False):
        return {"whole": whole, "source_defects": []}

    t = tr()
    x = er.name_exclusion(t, "aws-mainframe-modernization-carddemo", "app/cbl/CBEXPORT.cbl")
    assert x["kind"] == "source_defect" and "RECORD KEY" in t["source_defects"][0] and "#5866" in t["source_defects"][0]
    t = tr()
    assert er.name_exclusion(t, "dbb-mortgage-application", "x/epsmpmt.cbl")["kind"] == "owner_held"
    assert t["source_defects"] == []  # a held program is not a source defect
    t = tr()
    assert er.name_exclusion(t, "zecs", "Source/ZECS000.cbl") is None and t["source_defects"] == []
    t = tr(whole=True)  # a program that now translates whole is no longer excluded
    assert er.name_exclusion(t, "aws-mainframe-modernization-carddemo", "app/cbl/CBEXPORT.cbl") is None
