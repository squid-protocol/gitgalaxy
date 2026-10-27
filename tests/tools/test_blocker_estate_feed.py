"""blocker_estate_feed (#5054 done-when 4): each burned estate's survey becomes a full + anonymized report and customer
ledger rows that match the blockers the estate is known to have; a census corpus is never read."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blocker_estate_feed as bef
import blocker_report as br
from test_blocker_report import GAPS, result

KNOWN = {
    "P1": ["EXEC CICS READQ TS NUMITEMS", "no case"],
    "P2": ["EXEC CICS READQ TD"],
    "P3": ["known unproven: #4101"],
}
BURNED = ["aws-mainframe-modernization-carddemo", "cics-genapp", "cics-banking-sample-application-cbsa", "zecs",
          "dbb-mortgage-application", "cics-async-api-credit-card-application-example", "cics-crucible"]  # fmt: skip


def survey(corpora):
    return {(c, f"P{i}"): {"program": f"P{i}"} for c in corpora for i in range(2)}


def compute_for(gaps):
    def compute(rows, roots):
        res = result(gaps)
        corpus = next(iter(rows))[0]
        res["programs"] = [{**p, "corpus": corpus} for p in res["programs"]]
        return res

    return compute


def feed(tmp_path, corpora, gaps=KNOWN, roots=()):
    return bef.run(survey(corpora), list(roots), tmp_path, compute=compute_for(gaps))


@pytest.mark.parametrize("estate", BURNED)
def test_each_burned_estate_passes(tmp_path, estate):
    problems, summaries = feed(tmp_path, [estate])
    assert problems == [] and [s["estate"] for s in summaries] == [estate]
    ledger = json.loads((tmp_path / estate / "ledger.json").read_text(encoding="utf-8"))
    assert {r["estate"].split(":")[0] for r in ledger["rows"]} == {"customer"}
    assert estate not in json.dumps(ledger)


def test_known_signatures_link_and_unknown_ones_are_the_feed(tmp_path):
    problems, summaries = feed(tmp_path, ["cics-genapp"], {**KNOWN, "P9": ["something never seen: SECRETFLD"]})
    assert problems == []
    out = json.loads((tmp_path / "feed.json").read_text(encoding="utf-8"))
    assert summaries[0]["linked"] >= 3 and summaries[0]["unmatched"] == len(out["unmatched"]["cics-genapp"])
    assert "SECRETFLD" not in json.dumps(out)


def test_census_corpora_are_skipped_and_empty_survey_fails(tmp_path):
    problems, summaries = feed(tmp_path, ["some-census-repo"])
    assert summaries == [] and problems == ["no burned estate in the survey"]


def test_every_burned_estate_in_one_survey(tmp_path):
    problems, summaries = feed(tmp_path, [*BURNED, "some-census-repo"])
    assert problems == [] and len(summaries) == len(BURNED)


def test_a_broken_count_is_reported(tmp_path, monkeypatch):
    real = br.anon_report

    def lossy(res, salt, estate, redact_more=()):
        rep = real(res, salt, estate, redact_more)
        rep["blockers"][0]["programs_only_gap"] += 1
        return rep

    monkeypatch.setattr(br, "anon_report", lossy)
    problems, _ = feed(tmp_path, ["zecs"])
    assert any("full report says" in p for p in problems)


def test_a_leaked_source_name_is_reported(tmp_path):
    src = tmp_path / "corpora" / "zecs"
    src.mkdir(parents=True)
    (src / "ZECSPGM1.cbl").write_text("       PROGRAM-ID. ZECSPGM1.\n       01 SECRET-FIELD PIC X.\n", encoding="utf-8")
    # a signature word that is also a source name must be caught
    problems, summaries = feed(tmp_path / "ok", ["zecs"], roots=[tmp_path / "corpora"])
    assert problems == [] and summaries[0]["leak_checked"]
    assert bef.leaked({"SECRET-FIELD"}, "x SECRET-FIELD y") == ["SECRET-FIELD"]
    assert bef.leaked({"SECRET-FIELD"}, "PGM_aaaaaa") == []
    assert "ZECSPGM1" in bef.source_names(src)


def test_a_source_named_like_the_manifest_prose_is_not_a_leak(tmp_path):
    # CBSA has a CUSTOMER copybook; the fixed manifest text says "customer salt" (Evidence Refresh 40136742662)
    src = tmp_path / "corpora" / "zecs"
    src.mkdir(parents=True)
    (src / "CUSTOMER.cpy").write_text("       01 CUSTOMER-REC PIC X.\n", encoding="utf-8")
    assert "CUSTOMER" not in bef.source_names(src) and "CUSTOMER-REC" in bef.source_names(src)
    problems, summaries = feed(tmp_path / "ok", ["zecs"], roots=[tmp_path / "corpora"])
    assert problems == [] and summaries[0]["leak_checked"]


def test_other_salt_gives_other_ids():
    a = br.anon_report(result(GAPS), bef.CI_SALT, "zecs")
    b = br.anon_report(result(GAPS), bef.OTHER_SALT, "zecs")
    assert {x["id"] for x in a["blockers"]}.isdisjoint({x["id"] for x in b["blockers"]})


def test_cli_refuses_a_directory_with_no_survey(tmp_path):
    with pytest.raises(SystemExit):
        bef.main([str(tmp_path), "--out", str(tmp_path / "o"), "--corpora", str(tmp_path)])


def test_sources_resolve_under_a_root_or_as_the_root(tmp_path):
    (tmp_path / "zecs").mkdir()
    crucible = tmp_path / "ws" / "cics-crucible"
    crucible.mkdir(parents=True)
    assert bef.find_sources([tmp_path], "zecs") == tmp_path / "zecs"
    assert bef.find_sources([crucible], "cics-crucible") == crucible
    assert bef.find_sources([tmp_path], "cics-genapp") is None


def test_require_sources_fails_when_the_leak_scan_cannot_run(tmp_path):
    problems, _ = bef.run(survey(["zecs"]), [], tmp_path, compute=compute_for(KNOWN), require_sources=True)
    assert any("leak scan did not run" in p for p in problems)
    (tmp_path / "c" / "zecs").mkdir(parents=True)
    problems, summaries = bef.run(
        survey(["zecs"]), [tmp_path / "c"], tmp_path / "o", compute=compute_for(KNOWN), require_sources=True
    )
    assert problems == [] and summaries[0]["leak_checked"]


def test_the_crucible_checkout_passed_as_a_root_is_leak_scanned(tmp_path):
    root = tmp_path / "cics-crucible"
    root.mkdir()
    (root / "ZZPGMONE.cbl").write_text("       PROGRAM-ID. ZZPGMONE.\n", encoding="utf-8")
    problems, summaries = bef.run(
        survey(["cics-crucible"]), [root], tmp_path / "o", compute=compute_for(KNOWN), require_sources=True
    )
    assert problems == [] and summaries[0]["leak_checked"]


def test_unmatched_rows_become_a_deduped_queue(tmp_path, capsys):
    gaps = {**KNOWN, "P9": ["something never seen: SECRETFLD"]}
    feed(tmp_path, ["cics-genapp", "zecs"], gaps)
    data = json.loads((tmp_path / "feed.json").read_text(encoding="utf-8"))
    assert data["schema"] == 1
    items = bef.queue(data)
    assert items and all(i["body"].startswith("### Customer blocker") for i in items)
    assert len({i["id"] for i in items}) == len(items) <= sum(len(v) for v in data["unmatched"].values())
    assert bef.queue({"unmatched": {"a": data["unmatched"]["zecs"], "b": data["unmatched"]["zecs"]}}) == bef.queue(
        {"unmatched": {"a": data["unmatched"]["zecs"]}}
    )
    out = tmp_path / "q.json"
    assert bef.main(["queue", "--feed", str(tmp_path / "feed.json"), "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8")) == items
    assert "SECRETFLD" not in out.read_text(encoding="utf-8")


def test_one_construct_from_two_estates_is_one_queue_item(tmp_path):
    gaps = {**KNOWN, "P9": ["something never seen: SECRETFLD"]}
    feed(tmp_path, ["cics-genapp", "zecs"], gaps)
    data = json.loads((tmp_path / "feed.json").read_text(encoding="utf-8"))
    rows = [r for v in data["unmatched"].values() for r in v]
    items = bef.queue(data)
    assert len(items) < len(rows)
    assert sorted(i for it in items for i in it["ids"]) == sorted({r["id"] for r in rows})
    assert all(len(it["ids"]) >= 1 and it["key"].startswith(it["category"] + "|") for it in items)


def test_opened_issues_are_recorded_and_not_reopened(tmp_path):
    feed(tmp_path, ["cics-genapp"], {**KNOWN, "P9": ["something never seen: SECRETFLD"]})
    data = json.loads((tmp_path / "feed.json").read_text(encoding="utf-8"))
    items = bef.queue(data)
    made: list[tuple[str, str]] = []

    def create(title, body):
        made.append((title, body))
        return 9000 + len(made)

    filed = tmp_path / "out" / "filed.json"
    assert len(bef.file_issues(items, filed, create)) == len(items) == len(made)
    assert "SECRETFLD" not in " ".join(t + b for t, b in made)
    assert bef.file_issues(items, filed, create) == [] and len(made) == len(items)  # a second run opens nothing
    assert bef.queue(data, bef.bi.load_filed(filed)) == []


def test_open_issues_needs_a_filed_file(tmp_path):
    (tmp_path / "f.json").write_text('{"unmatched": {}}', encoding="utf-8")
    with pytest.raises(SystemExit):
        bef.queue_main(["--feed", str(tmp_path / "f.json"), "--open-issues"])
