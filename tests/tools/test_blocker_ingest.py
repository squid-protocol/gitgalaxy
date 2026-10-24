"""blocker_ingest (#5054): an anonymized report becomes customer-side ledger rows, matched to known issues by
construct signature, idempotent per report, refused when it is not a well-formed anonymized report."""

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blocker_ingest as bi
import blocker_report as br
from test_blocker_report import GAPS, OTHER, SALT, result

KNOWN = {
    "P1": ["EXEC CICS WEB OPEN HOST SESSTOKEN"],
    "P2": ["EXEC CICS READQ TS NUMITEMS", "no case"],
    "P3": ["EXEC CICS READQ TD"],
    "P4": ["EXEC CICS ADDRESS COMMAREA"],
    "P5": ["refused: macro-level CICS"],
    "P6": ["known unproven: #4101"],
}


def anon(gaps=GAPS, salt=SALT, redact=()):
    return br.anon_report(result(gaps), salt, "ACMEPAY", redact)


def ingest(rep, ledger=None):
    ledger = {} if ledger is None else ledger
    fresh = bi.ingest(rep, ledger, bi.load_catalogue())
    return ledger, fresh


def test_every_category_has_a_class_and_side():
    assert set(bi.CATEGORY_CLASS) == set(br.CATEGORIES)
    ledger = json.loads((bi.REPO / "tests/cobol_mainframe/port_blockers.json").read_text(encoding="utf-8"))
    for side, cls in bi.CATEGORY_CLASS.values():
        assert side in ledger["sides"] and cls in ledger["classes"]


def test_rows_match_blockers_with_same_counts():
    rep = anon()
    ledger, _ = ingest(rep)
    assert len(ledger["rows"]) == len(rep["blockers"])
    by_id = {r["id"]: r for r in ledger["rows"]}
    for b in rep["blockers"]:
        r = by_id[bi.row_id(rep["estate"], b["id"])]
        assert r["estate"] == f"customer:{rep['estate']}" and r["category"] == b["category"]
        assert r["signature"] == b["signature"]
        assert all(r[k] == b[k] for k in ("programs_blocked", "programs_only_gap", "programs_one_away"))


def test_known_blockers_link_to_their_issues():
    ledger, fresh = ingest(anon(KNOWN))
    issues = {r["signature"]: r["issue"] for r in ledger["rows"]}
    assert [i for sig, i in issues.items() if sig.startswith("EXEC CICS WEB OPEN")] == [4767]
    assert issues["EXEC CICS READQ TS NUMITEMS"] == 4002
    assert issues["EXEC CICS READQ TD"] == 5079
    assert issues["EXEC CICS ADDRESS COMMAREA"] == 5079
    assert issues["refused: macro-level CICS"] == 5121
    assert issues["known unproven: #4101"] == 4101
    assert [r["signature"] for r in fresh] == ["no case"]


def test_match_ignores_the_salt():
    a, _ = ingest(anon(KNOWN))
    b, _ = ingest(anon(KNOWN, OTHER))
    assert sorted(r["issue"] or 0 for r in a["rows"]) == sorted(r["issue"] or 0 for r in b["rows"])
    assert not {r["id"] for r in a["rows"]} & {r["id"] for r in b["rows"]}


def test_unknown_construct_is_new_with_a_draft():
    ledger, fresh = ingest(anon(GAPS))
    assert fresh and all(r["issue"] is None for r in fresh)
    other = [r for r in ledger["rows"] if r["category"] == "other"]
    assert other and other[0]["issue"] is None
    assert "unclassified" in bi.draft_issue(other[0])


def test_reingest_is_idempotent_and_tracks_versions():
    rep = anon(KNOWN)
    ledger, _ = ingest(rep)
    before = copy.deepcopy(ledger)
    ledger, fresh = ingest(rep, ledger)
    assert ledger == before and fresh == []
    later = {**rep, "engine_version": "9.9.9"}
    ledger, fresh = ingest(later, ledger)
    assert fresh == [] and len(ledger["rows"]) == len(before["rows"])
    assert all(r["seen_in"] == [rep["engine_version"], "9.9.9"] for r in ledger["rows"])


def test_redacted_reports_ingest():
    ledger, _ = ingest(anon(KNOWN, redact=("subclass", "counts", "repro")))
    assert len(ledger["rows"]) == 7  # six programs, P2 holds two blockers
    assert all("subclass" not in r and "programs_blocked" not in r for r in ledger["rows"])


def test_refuses_malformed_reports():
    good = anon()
    cases = []
    cases.append({**good, "kind": "full"})
    cases.append({**good, "schema_version": "0.1"})
    cases.append({**good, "programs": []})
    cases.append({**good, "estate": "ACMEPAY"})
    bad = copy.deepcopy(good)
    bad["blockers"][0]["case"] = "c-secret"
    cases.append(bad)
    bad = copy.deepcopy(good)
    bad["blockers"][0]["signature"] = "missing copybook PAYROLL"
    cases.append(bad)
    for rep in cases:
        with pytest.raises(ValueError, match="refused"):
            ingest(rep)


def test_cli(tmp_path, capsys):
    src, led = tmp_path / "anon.json", tmp_path / "customer" / "ledger.json"
    src.write_text(json.dumps(anon(KNOWN)))
    assert bi.main([str(src), "--ledger", str(led)]) == 0
    capsys.readouterr()
    assert json.loads(led.read_text())["rows"]
    src.write_text(json.dumps({**anon(), "kind": "full"}))
    assert bi.main([str(src), "--ledger", str(led)]) == 1


def test_catalogue_cites_issues_and_burned_estates_only():
    import estate4_draw

    burned = {n.lower() for n in estate4_draw.BURNED_NAMES}
    for e in bi.load_catalogue():
        assert e["category"] in br.CATEGORIES and isinstance(e["issue"], int)
        assert e["estate"] in burned


def test_construct_reaches_the_ledger_and_a_1_1_report_still_ingests():
    ledger, _ = ingest(anon(KNOWN))
    assert all(r["construct"] for r in ledger["rows"])
    old = anon(KNOWN)
    old["schema_version"] = "1.1"
    for b in old["blockers"]:
        del b["construct"]
    ledger, _ = ingest(old)
    assert ledger["rows"] and not any("construct" in r for r in ledger["rows"])


def test_a_construct_that_is_not_a_ranking_key_is_refused():
    rep = anon(KNOWN)
    rep["blockers"][0]["construct"] = "missing copybook CPY_7f3a1c"
    assert any("construct" in e for e in bi.check_report(rep))
