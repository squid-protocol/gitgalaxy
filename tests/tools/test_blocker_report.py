"""blocker_report (#5054): one run writes the full and anonymized reports; the anonymized one keeps every blocker's
category and counts, carries no customer identifier, literal, comment or path, and hashes stably per salt.
The leak test runs on a synthetic estate and, where the burned corpora are checked out, on the real names in them."""

import json
import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blocker_report as br
from gitgalaxy.core.source_text import read_source

SALT = bytes.fromhex("aa" * 32)
OTHER = bytes.fromhex("bb" * 32)

SECRETS = ["ACMEPAY", "CUSTLEDG", "PAYROLL-MASTER", "SECRETFLD", "ZZCOPY1", "/home/acme/src/pay.cbl", "PGMALPHA"]


def result(gaps_by_program: dict[str, list[str]]) -> dict:
    """A proof_blockers-shaped result: the ranking over `gaps` (only / one_away / touched) and the programs."""
    stats: dict[str, dict[str, int]] = {}
    for gaps in gaps_by_program.values():
        for g in gaps:
            st = stats.setdefault(g, {"only": 0, "one_away": 0, "touched": 0})
            st["touched"] += 1
            if len(gaps) == 1:
                st["only"] += 1
            elif len(gaps) == 2:
                st["one_away"] += 1
    return {
        "whole": len(gaps_by_program),
        "proven": sum(not g for g in gaps_by_program.values()),
        "gaps": [{"gap": g, **st} for g, st in stats.items()],
        "programs": [{"corpus": "ACMEPAY", "program": f"src/{p}.cbl", "case": f"c-{p}", "gaps": sorted(g),
                      "detail": {x: "/home/acme/src/pay.cbl 3/9" for x in g}, "burned": False}
                     for p, g in gaps_by_program.items()],
    }  # fmt: skip


GAPS = {
    "PGMALPHA": ["missing copybook ZZCOPY1"],
    "CUSTLEDG": ["missing copybook ZZCOPY1", "EXEC CICS FORMATTIME RESP"],
    "PAYROLL-MASTER": ["refused: LayoutError: source text past column 72 cuts the literal 'SECRETFLD' open"],
    "P4": ["scenario differs: RETURN SECRETFLD"],
    "P5": ["coverage: LINKed program PGMALPHA has live paragraphs no scenario runs"],
    "P6": ["fact: EIBTASKN", "fact: SECRETFLD"],
    "P7": ["known unproven: #4101", "no case"],
    "P8": ["EXEC CICS (no reason given)"],
    "P9": ["something the classifier has never seen: ACMEPAY CUSTLEDG"],
    "DONE": [],
}


def by_category(blockers: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for b in blockers:
        out[b["category"]] = out.get(b["category"], 0) + b.get("programs_blocked", 0)
    return out


def test_one_run_writes_both_reports(tmp_path):
    paths = br.write_reports(result(GAPS), tmp_path, SALT, "ACMEPAY")
    assert {p.name for p in paths.values()} == {
        "blocker_report.full.json", "blocker_report.full.md", "blocker_report.anon.json", "blocker_report.anon.md",
    }  # fmt: skip
    assert all(p.is_file() and p.stat().st_size for p in paths.values())
    assert "PGMALPHA" in paths["full_md"].read_text()  # the full report keeps every name


def test_every_full_blocker_appears_with_same_counts():
    res = result(GAPS)
    anon = br.anon_report(res, SALT, "ACMEPAY")
    assert anon["totals"] == {"whole": 10, "proven": 1}
    # programs blocked per category match the full report's programs
    expect: dict[str, set[str]] = {}
    for p in res["programs"]:
        for g in p["gaps"]:
            expect.setdefault(br.classify(g, SALT)[0], set()).add(p["program"])
    got = by_category(anon["blockers"])  # merged signatures can count a program once per signature
    assert all(got[c] >= len(v) for c, v in expect.items())
    cats = {b["category"] for b in anon["blockers"]}
    assert {"unresolved-link", "refusal", "cics-command", "scenario-differs", "coverage", "runtime-fact",
            "known-unproven", "no-case", "other"} <= cats  # fmt: skip
    cop = next(b for b in anon["blockers"] if b["category"] == "unresolved-link")
    assert (cop["programs_blocked"], cop["programs_only_gap"], cop["programs_one_away"]) == (2, 1, 1)


def test_one_program_with_two_merging_gaps_counts_once():
    res = result({"A": ["missing copybook X1", "missing copybook X2"]})
    anon = br.anon_report(res, SALT, "e")
    assert sorted(b["programs_blocked"] for b in anon["blockers"]) == [1, 1]  # two copybooks, two signatures


def test_leak_free_synthetic():
    anon = br.anon_report(result(GAPS), SALT, "ACMEPAY")
    text = json.dumps(anon) + br.anon_markdown(anon)
    for secret in SECRETS + ["ACMEPAY", "src/", "c-PGM", "something the classifier"]:
        assert secret not in text, secret
    assert "EIBTASKN" in text and "FORMATTIME" in text and "LayoutError" in text  # fixed vocabulary survives
    assert "literal" not in text  # the refusal message is gone, only its class stays
    assert not re.search(r"[^\x00-\x7f]", text)


def test_unicode_and_odd_names_hash_not_leak():
    names = ["KUNDENÄ", "顧客", "A@B#C", "x" * 300]
    res = result({f"P{i}": [f"missing copybook {n}", f"fact: {n}", f"scenario differs: RETURN {n}"]
                  for i, n in enumerate(names)})  # fmt: skip
    text = json.dumps(br.anon_report(res, SALT, "e"), ensure_ascii=False)
    for n in names:
        assert n not in text


def test_hashes_stable_for_same_salt_and_differ_for_other():
    a = json.dumps(br.anon_report(result(GAPS), SALT, "e"), sort_keys=True)
    assert a == json.dumps(br.anon_report(result(GAPS), SALT, "e"), sort_keys=True)
    b = json.dumps(br.anon_report(result(GAPS), OTHER, "e"), sort_keys=True)
    assert a != b
    ids_a = {x["id"] for x in json.loads(a)["blockers"]}
    ids_b = {x["id"] for x in json.loads(b)["blockers"]}
    assert not ids_a & ids_b
    assert br.hashed(SALT, "CPY", "abc") == br.hashed(SALT, "CPY", "ABC")  # case-folded
    assert br.hashed(SALT, "CPY", "ABC") != br.hashed(SALT, "PGM", "ABC")  # kind-separated


def test_salt_file_created_once_and_never_written_to_reports(tmp_path):
    f = tmp_path / "private" / "salt"
    s1 = br.load_salt(f)
    assert br.load_salt(f) == s1 and f.stat().st_mode & 0o077 == 0
    assert br.load_salt(None) != br.load_salt(None)
    br.write_reports(result(GAPS), tmp_path / "out", s1)
    for p in (tmp_path / "out").iterdir():
        assert s1.hex() not in p.read_text()


def test_redact_more():
    anon = br.anon_report(result(GAPS), SALT, "e", ("subclass", "counts"))
    for b in anon["blockers"]:
        assert set(b) == {"id", "category", "signature"}
    assert anon["redactions"] == ["subclass", "counts"]
    with pytest.raises(ValueError):
        br.anon_report(result(GAPS), SALT, "e", ("names",))


def test_manifest_lists_exactly_the_emitted_fields():
    anon = br.anon_report(result(GAPS), SALT, "e")
    assert set(anon) == set(br.ANON_REPORT_FIELDS)
    for b in anon["blockers"]:
        assert set(b) <= set(br.ANON_BLOCKER_FIELDS)
    assert anon["schema_version"] == br.SCHEMA_VERSION


def test_empty_result():
    anon = br.anon_report({"whole": 0, "proven": 0, "gaps": [], "programs": []}, SALT, "e")
    assert anon["blockers"] == []


def test_cli(tmp_path, capsys):
    src = tmp_path / "pb.json"
    src.write_text(json.dumps(result(GAPS)))
    assert (
        br.main([str(src), "--out", str(tmp_path / "o"), "--salt-file", str(tmp_path / "s"), "--estate", "ACMEPAY"])
        == 0
    )
    assert br.main(["--manifest"]) == 0
    assert "programs_blocked" in capsys.readouterr().out


# ---- the real names of the burned estates (CardDemo, GenApp, CBSA, zECS, ...) ---------------------------------------
CORPORA = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", ""))
ESTATES = ["aws-mainframe-modernization-carddemo", "cics-genapp", "cics-banking-sample-application-cbsa", "zecs"]
_NAME = re.compile(r"\b[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+\b|\b[A-Z]{3,8}\d{2,}[A-Z0-9]*\b")


@pytest.mark.parametrize("estate", ESTATES)
def test_leak_free_on_burned_estate_names(estate):
    root = CORPORA / estate
    if not root.is_dir():
        pytest.skip(f"{estate} not checked out under GITGALAXY_MAINFRAME_CORPORA")
    names: set[str] = set()
    for f in sorted(root.rglob("*"))[:4000]:
        if f.suffix.lower() in {".cbl", ".cob", ".cpy"} and f.stat().st_size < 400_000:
            names.update(_NAME.findall(read_source(f).text))
            names.add(f.stem.upper())
    vocab = br.vocabulary()
    names = {n for n in names if n not in vocab and len(n) >= 4}
    assert names
    gaps = {}
    for i, n in enumerate(sorted(names)[:600]):
        gaps[n] = [f"missing copybook {n}", f"fact: {n}", f"scenario differs: RETURN {n}", f"refused: LayoutError: {n}"]
    res = result(gaps)
    res["programs"] = [{**p, "corpus": estate, "program": f"{p['program']}"} for p in res["programs"]]
    text = json.dumps(br.anon_report(res, SALT, estate)) + br.anon_markdown(br.anon_report(res, SALT, estate))
    leaked = [n for n in names if n in text]
    assert not leaked, leaked[:10]
    assert estate not in text
