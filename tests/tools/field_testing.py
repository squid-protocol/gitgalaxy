"""
Field-testing counters for the mainframe fact channels.

For every ledger field (fact channel) this reports, on how many estates the field has
been FIELD-TESTED -- public repositories (the keyed corpora of corpora.json) and
private estates (customer scans, anonymised) -- and how many engine / forge defects those
rounds exposed.

Not every round is a field TEST. A channel is built and tuned against the estates that
exist when it is written (`fields.<field>.development_rounds` in the registry); those
rounds count toward "tested on" but prove little about unseen code. Only a FRESH round
-- an estate first checked after the channel existed -- tests it. The stopping rule: a
field is `field-tested` once CLEAN_ROUNDS fresh rounds after its last engine defect
found none AND those rounds carried at least CLEAN_FACTS facts (a 95% bound of 1% on
the engine's per-fact defect rate).

Sources:
  tests/cobol_mainframe/field_testing.json   estates (the rounds) + the defect log
  tests/cobol_mainframe/ground_truth_ledger.json   per estate and field: facts and tier
  tests/cobol_mainframe/answer_key/*.json    facts the reviewers were asked, key errors
                                             (census rulings `key_fixed`)

A PUBLIC estate tests a field when the ledger has facts for it there at a verified
tier (not draft). A PRIVATE estate tests the fields its registry entry lists.

    python tests/tools/field_testing.py report [--write]   # print (or write) the report
    python tests/tools/field_testing.py check              # validate the log; report up to date
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = REPO_ROOT / "tests" / "cobol_mainframe" / "field_testing.json"
LEDGER = REPO_ROOT / "tests" / "cobol_mainframe" / "ground_truth_ledger.json"
MANIFEST = REPO_ROOT / "tests" / "cobol_mainframe" / "corpora.json"
KEYS = REPO_ROOT / "tests" / "cobol_mainframe" / "answer_key"
REPORT = REPO_ROOT / "docs" / "language_status" / "cics_field_testing.md"
# #3614: the per-field status shipped inside the package, so a scan's skeleton export
# (gitgalaxy/tools/cobol_to_cobol/skeleton_export.py) can say how far each fact channel is proven.
CONFIDENCE = REPO_ROOT / "gitgalaxy" / "standards" / "fact_channel_confidence.json"

CLEAN_ROUNDS = 2  # fresh defect-free rounds (after the field's last engine defect) required
CLEAN_FACTS = 300  # ... carrying at least this many facts: a rule-of-three 95% bound of 1%
VERIFIED = ("sample_verified", "llm_verified", "cross_verified", "human_signed")
SIDES = ("engine", "forge", "key", "brief")
SEVERITIES = ("fact", "attribute")
KINDS = ("public", "private")


def load() -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))["corpora"]
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    corpora = [c["name"] for c in (manifest.get("corpora") if isinstance(manifest, dict) else manifest)]
    return registry, ledger, corpora


def ledger_fields(ledger: dict[str, Any]) -> list[str]:
    fields: dict[str, None] = {}
    for corpus in ledger.values():
        fields.update(dict.fromkeys(corpus["scoreboard"]))
    return list(fields)


def validate(registry: dict[str, Any], ledger: dict[str, Any], corpora: list[str]) -> list[str]:
    errors = []
    estates = registry.get("estates", [])
    ids = [e["id"] for e in estates]
    if len(ids) != len(set(ids)):
        errors.append("duplicate estate ids")
    rounds = [e.get("round") for e in estates]
    if rounds != sorted(rounds) or len(set(rounds)) != len(rounds):
        errors.append("estates must be listed in strictly increasing `round` order")
    fields = set(ledger_fields(ledger))
    for e in estates:
        if e.get("kind") not in KINDS:
            errors.append(f"{e['id']}: kind must be one of {KINDS}")
        if e.get("kind") == "public" and e["id"] not in corpora:
            errors.append(f"{e['id']}: a public estate must be a corpus of corpora.json")
        if e.get("kind") == "private":
            if any(k in e for k in ("url", "ref", "path")):
                errors.append(f"{e['id']}: a private estate carries no url / ref / path (anonymised label only)")
            unknown = set(e.get("fields", [])) - fields
            if unknown or not e.get("fields"):
                errors.append(f"{e['id']}: private `fields` must list ledger fields; unknown {sorted(unknown)}")
    for f in sorted(fields - set(registry.get("fields", {}))):
        errors.append(f"ledger field {f!r} has no `fields` entry (introduced PR, development_rounds)")
    for f, meta in registry.get("fields", {}).items():
        if not isinstance(meta.get("development_rounds"), int) or not re.fullmatch(
            r"#\d+", str(meta.get("introduced"))
        ):
            errors.append(f"fields.{f}: needs `introduced` (#PR) and an integer `development_rounds`")
    missing = [c for c in corpora if c not in ids]
    if missing:
        errors.append(f"keyed corpora with no estate entry: {missing}")
    seen = set()
    for d in registry.get("defects", []):
        where = d.get("id", "?")
        if where in seen:
            errors.append(f"{where}: duplicate defect id")
        seen.add(where)
        if d.get("estate") not in ids:
            errors.append(f"{where}: unknown estate {d.get('estate')}")
        if d.get("side") not in SIDES:
            errors.append(f"{where}: side must be one of {SIDES}")
        if d.get("severity") not in SEVERITIES:
            errors.append(f"{where}: severity must be one of {SEVERITIES}")
        unknown = set(d.get("fields", [])) - fields
        if unknown or not d.get("fields"):
            errors.append(f"{where}: `fields` must list ledger fields; unknown {sorted(unknown)}")
        if not d.get("issue") and not d.get("fixed_by"):
            errors.append(f"{where}: cite an issue or a fixing PR")
        if d.get("fixed_by") and not re.fullmatch(r"#\d+", str(d["fixed_by"])):
            errors.append(f"{where}: fixed_by is a PR reference like #1234")
        if not d.get("summary"):
            errors.append(f"{where}: summary is required")
    return errors


def tested(estate: dict[str, Any], field: str, ledger: dict[str, Any]) -> bool:
    if estate["kind"] == "private":
        return field in estate.get("fields", [])
    row = ledger.get(estate["id"], {}).get("scoreboard", {}).get(field, {})
    facts = (row.get("engine") or {}).get("truth") or 0
    return bool(facts) and row.get("truth") in VERIFIED


def estate_census(estate_id: str) -> tuple[int, int]:
    """(facts reviewers were asked, key errors their rulings fixed) for one keyed estate."""
    path = KEYS / f"{estate_id}.json"
    if not path.is_file():
        return 0, 0
    key = json.loads(path.read_text(encoding="utf-8"))
    asked = errors = 0
    for rec in key.get("cross_verification", []) + key.get("section_census", []):
        asked += sum(t.get("asked", 0) for t in rec.get("tasks", {}).values())
        errors += sum(1 for r in rec.get("rulings", {}).values() if r.get("verdict") == "key_fixed")
    return asked, errors


def counters(registry: dict[str, Any], ledger: dict[str, Any]) -> list[dict[str, Any]]:
    estates = registry["estates"]
    order = {e["id"]: e["round"] for e in estates}
    rows = []
    for field in ledger_fields(ledger):
        hit = [e for e in estates if tested(e, field, ledger)]
        engine = [
            d for d in registry["defects"] if field in d["fields"] and d["side"] == "engine" and d["severity"] == "fact"
        ]
        forge = [d for d in registry["defects"] if field in d["fields"] and d["side"] == "forge"]
        last = max((order[d["estate"]] for d in engine), default=0)
        dev = registry["fields"][field]["development_rounds"]
        fresh = [e for e in hit if e["round"] > dev]
        clean_estates = [e for e in fresh if e["round"] > last]
        clean = len(clean_estates)
        clean_facts = sum(
            (ledger[e["id"]]["scoreboard"][field].get("engine") or {}).get("truth") or 0
            for e in clean_estates
            if e["kind"] == "public"
        )
        facts = sum(
            (ledger[e["id"]]["scoreboard"][field].get("engine") or {}).get("truth") or 0
            for e in hit
            if e["kind"] == "public"
        )
        rows.append({
            "field": field,
            "public": sum(1 for e in hit if e["kind"] == "public"),
            "private": sum(1 for e in hit if e["kind"] == "private"),
            "facts": facts,
            "fresh": len(fresh),
            "engine_defects": len(engine),
            "forge_defects": len(forge),
            "clean_rounds": clean,
            "clean_facts": clean_facts,
            "status": "field-tested"
            if clean >= CLEAN_ROUNDS and clean_facts >= CLEAN_FACTS
            else ("open" if hit else "untested"),
            "needs": ", ".join(
                x
                for x in (
                    f"{CLEAN_ROUNDS - clean} more clean fresh round(s)" if clean < CLEAN_ROUNDS else "",
                    f"{CLEAN_FACTS - clean_facts:,} more clean fresh facts" if clean_facts < CLEAN_FACTS else "",
                )
                if x
            )
            or "-",
        })  # fmt: skip
    return rows


def _bound(facts: int) -> str:
    """The rule-of-three 95% upper bound on a per-fact defect rate after `facts` clean facts."""
    return f"{300 / facts:.1f}%" if facts >= 3 else "-"


def render(registry: dict[str, Any], ledger: dict[str, Any]) -> str:
    rows = counters(registry, ledger)
    out = [
        "# Mainframe fact channels -- field testing",
        "",
        "Generated by `python tests/tools/field_testing.py report --write` from",
        "`tests/cobol_mainframe/field_testing.json` (estates + defect log), the ground-truth ledger and the",
        "answer keys. Do not edit by hand. `check` (in CI) fails when this page is stale.",
        "",
        "**Tested on** counts the estates where a field was checked against truth: a public repository (a",
        "keyed corpus) whose ledger tier for the field is verified with facts present, or a private estate (a",
        "customer scan; anonymised) whose record lists the field. **Fresh** counts only estates the channel",
        "had NOT been built or tuned against (the rest are development rounds: zopeneditor, CBSA and CardDemo",
        "for every channel, GENAPP too for the web / JCICS channels, DSF for the PL/I ones). **Clean fresh**",
        "counts fresh rounds after the field's last engine defect. A field is **field-tested** once",
        f"{CLEAN_ROUNDS} clean fresh rounds carrying at least {CLEAN_FACTS} facts found no engine defect in it",
        "(a 95% bound of 1%); before that it is **open**, and **needs** says what is missing.",
        "**Bound** is the rule-of-three 95% upper bound on the engine's per-fact defect rate over the clean",
        "fresh facts (3 / facts): how thin the evidence behind a status is. Private-estate facts are not",
        "counted in it (their fact counts are not recorded here).",
        "",
        "## By field",
        "",
        "| field | tested on: public | private | fresh | facts (public) | engine defects | forge defects | clean fresh | clean fresh facts | bound | status | needs |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    rank = {"field-tested": 0, "open": 1, "untested": 2}
    for r in sorted(rows, key=lambda r: (rank[r["status"]], -r["clean_facts"], -r["public"], r["field"])):
        out.append(
            f"| {r['field']} | {r['public']} | {r['private']} | {r['fresh']} | {r['facts']:,} | {r['engine_defects']} | "
            f"{r['forge_defects']} | {r['clean_rounds']} | {r['clean_facts']:,} | "
            f"{_bound(r['clean_facts'])} | {r['status']} | {r['needs']} |"
        )
    out += ["", "## By round", "",
            "| round | estate | kind | facts reviewers checked | key errors | engine | forge | brief gaps |",
            "|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for e in registry["estates"]:
        asked, key_errors = estate_census(e["id"]) if e["kind"] == "public" else (0, 0)
        ds = [d for d in registry["defects"] if d["estate"] == e["id"]]
        count = {s: sum(1 for d in ds if d["side"] == s) for s in SIDES}
        name = e["id"] if e["kind"] == "public" else e.get("label", e["id"])
        out.append(
            f"| {e['round']} | {name} | {e['kind']} | {asked:,} | {key_errors} | {count['engine']} | "
            f"{count['forge']} | {count['brief']} |"
        )
    out += ["", "## Defect log", "", "| id | round | side | severity | fields | issue / fix | summary |",
            "|---|---|---|---|---|---|---|"]  # fmt: skip
    order = {e["id"]: e["round"] for e in registry["estates"]}
    for d in registry["defects"]:
        ref = " / ".join(x for x in (f"#{d['issue']}" if d.get("issue") else "", d.get("fixed_by") or "") if x)
        out.append(
            f"| {d['id']} | {order[d['estate']]} | {d['side']} | {d['severity']} | {', '.join(d['fields'])} | "
            f"{ref} | {d['summary'].replace('|', '/')} |"
        )
    out += [
        "",
        "Key errors (the census's findings against the answer key itself) are counted from each key's",
        "rulings, not logged by hand. The engine agreeing with a key is only as good as the key: a key",
        "error is a verification defect, not a product one, and does not reset a field's clean rounds.",
        "",
    ]
    return "\n".join(out)


def confidence(registry: dict[str, Any], ledger: dict[str, Any]) -> str:
    """The shipped confidence file: per ledger field, its field-testing status and evidence."""
    rows = {
        r["field"]: {
            "status": r["status"],
            "tested_on_public": r["public"],
            "tested_on_private": r["private"],
            "fresh_rounds": r["fresh"],
            "clean_fresh_rounds": r["clean_rounds"],
            "clean_fresh_facts": r["clean_facts"],
            "engine_defects": r["engine_defects"],
        }
        for r in sorted(counters(registry, ledger), key=lambda r: r["field"])
    }
    doc = {
        "about": "Generated by tests/tools/field_testing.py from tests/cobol_mainframe/field_testing.json, the "
        "ground-truth ledger and the answer keys; do not edit. Per mainframe fact channel (ledger field): "
        f"field-tested = {CLEAN_ROUNDS} clean fresh rounds carrying >= {CLEAN_FACTS} facts; open / untested otherwise.",
        "fields": rows,
    }
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    rp = sub.add_parser("report")
    rp.add_argument("--write", action="store_true", help=f"write {REPORT.relative_to(REPO_ROOT)}")
    sub.add_parser("check")
    args = ap.parse_args()
    registry, ledger, corpora = load()
    errors = validate(registry, ledger, corpora)
    if errors:
        print("field_testing.json is invalid:\n  " + "\n  ".join(errors))
        return 1
    text = render(registry, ledger)
    conf = confidence(registry, ledger)
    if args.cmd == "report":
        if args.write:
            REPORT.write_text(text, encoding="utf-8")
            CONFIDENCE.write_text(conf, encoding="utf-8")
            print(f"wrote {REPORT.relative_to(REPO_ROOT)} and {CONFIDENCE.relative_to(REPO_ROOT)}")
        else:
            sys.stdout.write(text)
        return 0
    if not CONFIDENCE.is_file() or CONFIDENCE.read_text(encoding="utf-8") != conf:
        print(f"{CONFIDENCE.relative_to(REPO_ROOT)} is stale: run `python tests/tools/field_testing.py report --write`")
        return 1
    if not REPORT.is_file() or REPORT.read_text(encoding="utf-8") != text:
        print(f"{REPORT.relative_to(REPO_ROOT)} is stale: run `python tests/tools/field_testing.py report --write`")
        return 1
    print("field testing record: valid, report up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
