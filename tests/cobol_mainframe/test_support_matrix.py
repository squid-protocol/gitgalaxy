"""#4724 support matrix: each status, each refusal kind, the catalogue join (absent / present), and the committed
burned-estate reports (every refusal and hole maps to an issue, an agreed refusal family, or a system library)."""

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import support_matrix as sm  # tests/tools/support_matrix.py

FIXTURE_REPORTS = Path(__file__).resolve().parents[1] / "fixtures" / "evidence_report"


@pytest.fixture(autouse=True)
def _snapshot_reports(monkeypatch):
    """#5206: the evidence report is published on `generated`, not committed; these tests read a frozen snapshot."""
    monkeypatch.setattr(sm, "REPORTS", FIXTURE_REPORTS)


GETMAIN_HOLE = "EXEC EXEC CICS: EXEC CICS GETMAIN not modelled (storage CICS acquires for the task is not modelled)"


def feat(**progs_by_key):
    return {k: {"count": len(v), "programs": v} for k, v in progs_by_key.items()}


INVENTORY = {
    "statements": {
        "unknown": {"count": 2, "programs": ["P3.cbl"]},
        **feat(MOVE=["P1.cbl", "P2.cbl"], ALTER=["P3.cbl"], IF=["P3.cbl"], ADD=["P2.cbl"]),
    },
    "cics_commands": {
        "unknown": {"count": 0, "programs": []},
        **feat(GETMAIN=["P3.cbl"], RETRIEVE=["P4.cbl"], **{"READ 03700306": ["P4.cbl"]}),
    },
    "compile_options": {"unknown": {"count": 0, "programs": []}, **feat(**{"TRUNC: STD": ["P1.cbl"]})},
    "data_types": {"unknown": {"count": 0, "programs": []}, **feat(**{"COMP-1": ["P1.cbl"]})},
    "intrinsic_functions": {"unknown": {"count": 0, "programs": []}, **feat(NUMVAL=["P1.cbl"])},
    "copybook_resolution_gaps": {
        "unknown": {"count": 0, "programs": []},
        **feat(**{"COPY CMQGMOV": ["P4.cbl"], "COPY CEEIGZCT": ["P5.cbl"], "COPY ACCTREC": ["P6.cbl"]}),
    },
    "eras": {
        "programs": {
            "P1.cbl": {
                "era": 4,
                "earliest": 1,
                "mixed": True,
                "tells": [
                    {"tell": "handle-condition", "era": 1, "count": 1, "first_line": 9},
                    {"tell": "channel-container", "era": 4, "count": 1, "first_line": 10},
                ],
            },
            "P2.cbl": {
                "era": 2,
                "earliest": 2,
                "mixed": False,
                "tells": [
                    {"tell": "resp", "era": 2, "count": 3, "first_line": None},
                ],
            },
            "P3.cbl": {"era": None, "earliest": None, "mixed": False, "tells": []},
        },
        "summary": {
            "programs": 3,
            "by_era": {"0": 0, "1": 0, "2": 1, "3": 0, "4": 1, "none": 1},
            "mixed": 1,
            "tells": {"channel-container": 1, "handle-condition": 1, "resp": 1},
        },
    },
    "unparsed_programs": [{"program": "P4.cbl", "reason": "CopyNotFound: COPY CMQGMOV"}],
}


def prog(name, level, statements=10, holes=(), refused=None, case=None):
    chosen = {"case": case} if case else None
    return {
        "program": name,
        "level": level,
        "translation": {"statements": statements, "holes": list(holes), "refused": refused},
        "equivalence": {"chosen": chosen, "cases": [chosen] if chosen else []},
    }


REPORT = {
    "burned": True,
    "measured": {"survey": {"sha": "0123456789abcdef"}},
    "programs": [
        prog("P1.cbl", "L3", case="case-p1"),
        prog("P2.cbl", "L1"),
        prog("P3.cbl", "L0", holes=[GETMAIN_HOLE, "HOLE ALTER not modelled", "CALL CALL ZZZUNKNOWN"]),
        prog("P4.cbl", "L0", statements=None, refused="missing copybook CMQGMOV"),
        prog("P5.cbl", "L0", statements=None, refused="missing copybook CEEIGZCT"),
        prog("P6.cbl", "L0", statements=None, refused="missing copybook ACCTREC"),
    ],
}

CATALOGUE = {
    "rules": [
        {
            "id": "RT-CBL-MOVE",
            "family": "CBL",
            "title": "MOVE of a group",
            "options": [],
            "features": ["statements: MOVE"],
            "register": ["C1"],
            "status": "ASSUMED",
            "calibration": "uncalibrated",
        },
        {
            "id": "RT-NUM-TRUNC",
            "family": "NUM",
            "title": "binary items",
            "options": ["TRUNC"],
            "register": [],
            "status": "MATCHED",
            "calibration": "uncalibrated",
        },
        {
            "id": "RT-HFP-ADD",
            "family": "HFP",
            "title": "hex float",
            "options": [],
            "features": ["data_types: COMP-1"],
            "register": ["C6"],
            "status": "DIFFERS",
            "calibration": "uncalibrated",
        },
        {
            "id": "RT-FUNC-NUMVAL-C",
            "family": "FUNC",
            "title": "FUNCTION NUMVAL-C only",
            "options": [],
            "features": ["intrinsic_functions: NUMVAL-C"],
            "register": [],
            "status": "MATCHED",
            "calibration": "uncalibrated",
        },
    ]
}
REGISTER = {"C1": {"status": "ASSUMED"}, "C6": {"status": "DIFFERS"}}


@pytest.fixture(scope="module")
def rmap():
    return sm.load_map()


@pytest.fixture(scope="module")
def bare(rmap):
    return sm.build_estate("synthetic", INVENTORY, REPORT, rmap, None)


@pytest.fixture(scope="module")
def catalogued(rmap):
    return sm.build_estate("synthetic", INVENTORY, REPORT, rmap, CATALOGUE, REGISTER)


def by_feature(m):
    return {f["feature"]: f for f in m["features"]}


def test_proven_feature_names_its_level_and_case(bare):
    f = by_feature(bare)["statements: MOVE"]
    assert f["status"] == sm.PROVEN
    assert f["best_level"] == "L3"
    assert f["cases"] == ["case-p1"]


def test_translated_feature_without_proof_is_unproven(bare):
    feats = by_feature(bare)
    assert feats["statements: ADD"]["status"] == sm.UNPROVEN  # P2 is L1
    assert feats["statements: IF"]["status"] == sm.UNPROVEN  # P3 has holes, none of them names IF


def test_feature_a_refusal_names_is_refused_with_its_owner(bare):
    feats = by_feature(bare)
    assert feats["cics_commands: GETMAIN"]["status"] == sm.REFUSED
    assert feats["cics_commands: GETMAIN"]["refusals"] == {"getmain-freemain": ["P3.cbl"]}
    assert feats["statements: ALTER"]["status"] == sm.REFUSED
    assert "modelled" in feats["statements: ALTER"]["missing"]
    assert bare["refusals"]["alter"]["label"] == "#5560"  # modelled since #5568; the entry keeps the pre-#5568 report text
    assert bare["refusals"]["getmain-freemain"]["label"] == "#4771"


def test_feature_only_in_programs_refused_whole_is_unknown(bare):
    assert by_feature(bare)["cics_commands: RETRIEVE"]["status"] == sm.UNKNOWN
    assert "cics_commands: RETRIEVE" in bare["unknown"]["never_seen"]


def test_unknown_buckets_unparsed_programs_and_sequence_fragments_are_listed_for_triage(bare):
    u = bare["unknown"]
    assert u["buckets"] == {"statements": {"count": 2, "programs": ["P3.cbl"]}}
    assert u["unparsed_programs"] == INVENTORY["unparsed_programs"]
    assert u["sequence_fragments"] == ["cics_commands: READ 03700306"]
    assert "cics_commands: READ 03700306" not in u["never_seen"]  # listed once, as a fragment


def test_system_copybooks_are_a_configuration_gap_and_mq_is_not_provable(bare):
    r = bare["refusals"]
    assert r["mq-copybooks"]["system_library"].startswith("SCSQCOBC")
    assert r["mq-copybooks"]["api"]["issue"] == 4892
    assert r["mq-copybooks"]["programs"] == ["P4.cbl"]
    assert r["le-copybooks"]["system_library"].startswith("SCEESAMP")
    assert r["estate-copybook"]["charter"] == "COPY members not in the estate"
    assert r["estate-copybook"]["system_library"] is None
    page = sm.render_estate(bare)
    text = "\n".join(page)
    assert "SCSQCOBC" in text and "translates, not provable" in text
    apis = text.split("### Runtime APIs not modelled")[1].split("###")[0]
    assert "IBM MQ" in apis and "P4.cbl" in apis and "P6.cbl" not in apis


def test_an_unowned_entry_is_an_acceptance_gap(rmap):
    unowned = {**rmap, "entries": [{"id": "x", "match": "ZZZ", "_re": re.compile("ZZZ")}, *rmap["entries"]]}
    api = {**rmap, "entries": [{"id": "y", "match": "ZZZ", "_re": re.compile("ZZZ"), "charter": "ims",
                                "api": {"name": "Y", "issue": None}}, *rmap["entries"]]}  # fmt: skip
    for m in (unowned, api):
        e = sm.build_estate("synthetic", INVENTORY, REPORT, m, None)
        assert e["needs_issue"] == [m["entries"][0]["id"]]
        assert e["refusals"][m["entries"][0]["id"]]["label"] == sm.NEEDS_ISSUE
        assert "Acceptance gap (#4724)" in "\n".join(sm.render_estate(e))


def test_an_unmapped_refusal_is_shown_not_dropped(bare):
    assert bare["unmapped"] == {"CALL CALL ZZZUNKNOWN": ["P3.cbl"]}
    assert "UNMAPPED" in "\n".join(sm.render_estate(bare))


def test_no_catalogue_says_not_yet_catalogued(bare):
    for f in bare["features"]:
        assert f["rules"] == []
        assert "catalogued (no catalogue yet, #4711)" in f["missing"]
    assert "not yet catalogued (#4711)" in sm.render({"catalogue": None, "estates": {"synthetic": bare}})


def test_catalogue_join_by_feature_key_and_option(catalogued):
    feats = by_feature(catalogued)
    move = feats["statements: MOVE"]
    assert move["rules"] == ["RT-CBL-MOVE"]
    assert move["rule_status"] == "ASSUMED"
    assert move["register"] == [{"id": "C1", "status": "ASSUMED"}]
    assert "IBM-matched (worst rule ASSUMED: uncalibrated)" in move["missing"]
    assert feats["compile_options: TRUNC: STD"]["rules"] == ["RT-NUM-TRUNC"]
    assert feats["data_types: COMP-1"]["rules"] == ["RT-HFP-ADD"]
    assert feats["intrinsic_functions: NUMVAL"]["rules"] == []  # NUMVAL-C is another key; a title word joins nothing (#5565)
    assert "catalogued" in feats["intrinsic_functions: NUMVAL"]["missing"]
    assert all("calibrated on z/OS (#4702)" in f["missing"] for f in catalogued["features"])


def test_render_is_deterministic(catalogued):
    m = {"catalogue": "cobolrt_rules.json", "estates": {"synthetic": catalogued}}
    assert sm.render(m) == sm.render(json.loads(json.dumps(m)))


# --- the committed sources -------------------------------------------------------------------------------------------


def committed_texts():
    for estate in sm.estates():
        rep = json.loads((sm.REPORTS / estate / "report.json").read_text(encoding="utf-8"))
        for row in rep["programs"]:
            for text in sm._texts(row):
                yield estate, row["program"], text
        inv = json.loads((sm.INVENTORY / f"{estate}.json").read_text(encoding="utf-8"))
        for key, v in inv[sm.GAPS].items():
            if key != "unknown":
                yield estate, v["programs"][0], "missing copybook " + key.removeprefix("COPY ")


def test_every_burned_refusal_and_hole_maps_to_exactly_one_entry(rmap):
    """#4724 acceptance: every refusal maps to exactly one entry. A new text (an evidence refresh) fails here until
    refusal_map.json names it, with its owner (test_every_refusal_map_entry_has_an_owner)."""
    bad = [
        (estate, program, text, [e["id"] for e in sm.classify(text, rmap)])
        for estate, program, text in committed_texts()
        if len(sm.classify(text, rmap)) != 1
    ]
    assert bad == [], "add or narrow docs/language_status/refusal_map.json entries"


def test_refusal_map_entries_are_well_formed(rmap):
    charter = sm.CHARTER.read_text(encoding="utf-8")
    for key, phrase in rmap["charter"].items():
        assert phrase in charter, f"charter family {key}: {phrase!r} is not in definition_of_done.md"
    categories = {"statements", "data_types", "cics_commands", "cics_options", "sql_forms", "intrinsic_functions",
                  "compile_options"}  # fmt: skip
    ids = [e["id"] for e in rmap["entries"]]
    assert len(ids) == len(set(ids))
    for e in rmap["entries"]:
        assert e.get("charter") in (None, *rmap["charter"]), e["id"]
        for f in e.get("features", []):
            assert re.fullmatch(r"[a-z_]+: \S.*", f) and f.split(": ")[0] in categories, (e["id"], f)


def test_every_refusal_map_entry_has_an_owner(rmap):
    """#4724 acceptance: no entry is left at "needs an issue" -- each names an issue, an agreed refusal family or a
    system library, and an unmodelled API it names has its issue."""
    assert [e["id"] for e in rmap["entries"] if not sm.owned(e)] == []


def test_no_burned_estate_has_an_unowned_refusal():
    for estate, m in sm.build()["estates"].items():
        assert (m["needs_issue"], m["unmapped"]) == ([], {}), estate


def test_era_section_has_the_distribution_the_mixed_programs_and_their_tells(bare, rmap):
    """#5117: the era tag reaches the matrix, and is not mistaken for a feature category."""
    assert not [f for f in bare["features"] if f["feature"].startswith("eras")]  # noqa: S101
    assert bare["eras"]["summary"]["by_era"]["4"] == 1  # noqa: S101
    assert bare["eras"]["mixed"] == {"P1.cbl": ["handle-condition (era 1)", "channel-container (era 4)"]}  # noqa: S101
    assert bare["eras"]["programs"]["none"] == ["P3.cbl"]  # noqa: S101
    page = "\n".join(sm.render_estate(bare))
    assert "### Era" in page and "| 4 | 1 | 33% |" in page  # noqa: S101
    assert "P1.cbl: handle-condition (era 1), channel-container (era 4)" in page  # noqa: S101
    assert "resp 1" in page  # noqa: S101


def test_era_section_names_programs_raised_by_a_copybook_only_when_there_are_some(bare, rmap):
    """#5117: the copybook line is rendered only for an estate whose summary carries `raised_by_copybook`."""
    assert "COPY" not in "\n".join(sm.render_eras(bare["eras"]))  # noqa: S101
    inv = json.loads(json.dumps(INVENTORY))
    inv["eras"]["summary"]["raised_by_copybook"] = 2
    m = sm.build_estate("synthetic", inv, REPORT, rmap, None)
    assert "2 programs have a higher era than their own text shows" in "\n".join(sm.render_eras(m["eras"]))  # noqa: S101


def test_an_inventory_without_era_tags_renders_no_era_section(rmap):
    inv = {k: v for k, v in INVENTORY.items() if k != "eras"}
    m = sm.build_estate("synthetic", inv, REPORT, rmap, None)
    assert m["eras"] is None and "### Era" not in "\n".join(sm.render_estate(m))  # noqa: S101


def test_every_burned_estate_has_an_era_section(capsys):
    assert sm.main([]) == 0
    assert capsys.readouterr().out.count("### Era") == len(sm.estates())  # noqa: S101


def test_burned_estates_are_the_inventory_fixtures():
    assert sm.estates() == sorted(p.stem for p in sm.INVENTORY.glob("*.json"))
    assert len(sm.estates()) >= 6


def test_matrix_of_every_burned_estate_renders(capsys):
    assert sm.main([]) == 0
    page = capsys.readouterr().out
    for estate in sm.estates():
        assert f"\n## {estate}\n" in page
    assert "UNMAPPED" not in page


def test_json_output(capsys):
    assert sm.main(["--json", "zecs"]) == 0
    m = json.loads(capsys.readouterr().out)
    assert list(m["estates"]) == ["zecs"]
    assert set(m["estates"]["zecs"]["counts"]) == set(sm.STATUSES)


@pytest.mark.skipif(not sm.CATALOGUE.is_file(), reason="the rule catalogue (#4711) is not on this branch yet")
def test_the_committed_catalogue_joins():
    m = sm.build()
    rules = {r["id"] for r in json.loads(sm.CATALOGUE.read_text(encoding="utf-8"))["rules"]}
    matched = {r for e in m["estates"].values() for f in e["features"] for r in f["rules"]}
    assert matched and matched <= rules
