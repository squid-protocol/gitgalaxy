#!/usr/bin/env python3
"""#4724: the readiness scanner's support matrix -- per burned estate, every feature of its inventory with its support
status, from committed tool outputs only (no corpus, no scan).

    python tests/tools/support_matrix.py [ESTATE ...] [--json] [--catalogue PATH] [--out FILE]

Sources:
  inventory     tests/fixtures/feature_inventory/<estate>.json (feature_inventory.py, #4723): feature -> programs
  levels        docs/language_status/evidence_report/<estate>/report.json (evidence_report.py, #4601): each
                program's level, its proving case, and the translate-only refusal / holes of the survey behind it
  refusals      docs/language_status/refusal_map.json: each refusal or hole text -> its issue, agreed refusal family
                (definition_of_done.md section 2), or system library; an unmapped text is listed as such
  catalogue     docs/language_status/cobolrt_rules.json (#4711), optional: until it exists every feature is "not yet
                catalogued", as definition_of_done.md section 5 says. --catalogue reads another copy
  register      the oracle-assumptions register (tests/tools/register.py) for the status of a rule's entries

A feature's status (the first that holds):
  supported and proven   a program that uses it is at L2 or above (a case runs it, the port equal on every scenario)
  supported, unproven    a program that uses it is translated and no refusal of that program names the feature
  refused by name        a refusal names it (its issue, or the agreed refusal family)
  unknown / never seen   none of the above: only programs the translator refused whole use it
Beside it, the conditions of "supported" (definition_of_done.md section 5) the feature does not meet. Proof is per
program, as the charter's L2: a proven program's scenarios need not reach every feature it holds (L3 / L4 say more).

A refused program over a COPY member of an IBM product library (MQ's CMQ*, LE's CEE*) is a configuration gap the
customer fixes by naming the library, not a translator limit; a program that calls a runtime API the runtime does
not model (MQI) translates but is not provable. Both have their own sections (#4724 design points 2 and 3).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))

STATUS_DOCS = REPO / "docs" / "language_status"
REPORTS = STATUS_DOCS / "evidence_report"
INVENTORY = TOOLS.parent / "fixtures" / "feature_inventory"
CATALOGUE = STATUS_DOCS / "cobolrt_rules.json"
REFUSAL_MAP = STATUS_DOCS / "refusal_map.json"
CHARTER = STATUS_DOCS / "definition_of_done.md"

PROVEN, UNPROVEN, REFUSED, UNKNOWN = (
    "supported and proven",
    "supported, unproven",
    "refused by name",
    "unknown / never seen",
)
STATUSES = (PROVEN, UNPROVEN, REFUSED, UNKNOWN)
PROVEN_LEVELS = ("L2", "L3", "L4", "L5")
FAMILIES = "refusal_families"  # #5121: programs refused by name by family (macro-level CICS, CICS Assembler)
GAPS = "copybook_resolution_gaps"  # not features: read as `missing copybook NAME` refusals
RULE_ORDER = ("MATCHED", "ASSUMED", "DIFFERS", "REFUSED")  # worst last
SEQUENCE_FRAGMENT = re.compile(r"\b\d{6,8}\b")  # a key holding a sequence-area number (columns 1-6 / 73-80)

def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def estates() -> list[str]:
    """The burned estates: only theirs are published under evidence_report/ (evidence_report.py), with an inventory."""
    if not any(REPORTS.glob("*/report.json")):  # #5206: the report is published on `generated`, not committed
        import evidence_report

        evidence_report.materialize()
    return sorted(
        d.name for d in REPORTS.iterdir() if (d / "report.json").is_file() and (INVENTORY / f"{d.name}.json").is_file()
    )


def load_map(path: Path = REFUSAL_MAP) -> dict[str, Any]:
    m = _load(path)
    for e in m["entries"]:
        e["_re"] = re.compile(e["match"])
    return m


def classify(text: str, rmap: dict[str, Any]) -> list[dict[str, Any]]:
    """The refusal-map entries whose `match` hits `text` (exactly one, when the map is right)."""
    return [e for e in rmap["entries"] if e["_re"].search(text)]


NEEDS_ISSUE = "needs an issue"


def owned(e: dict[str, Any]) -> bool:
    """#4724 acceptance: an entry maps to an issue, an agreed refusal family or a system library, and an unmodelled
    API it names has its issue."""
    return bool(e.get("issue") or e.get("charter") or e.get("system_library")) and (
        not e.get("api") or bool(e["api"].get("issue"))
    )


def entry_label(e: dict[str, Any] | None, rmap: dict[str, Any]) -> str:
    if e is None:
        return "UNMAPPED: add it to refusal_map.json"
    parts = []
    if e.get("system_library"):
        parts.append(f"system copybook: name {e['system_library']}")
    if e.get("charter"):
        parts.append(f"agreed refusal ({rmap['charter'][e['charter']]})")
    if e.get("issue"):
        parts.append(f"#{e['issue']}")
    return ", ".join(parts) if owned(e) else NEEDS_ISSUE


def load_catalogue(path: Path | None) -> dict[str, Any] | None:
    return _load(path) if path and path.is_file() else None


def match_rules(category: str, key: str, catalogue: dict[str, Any] | None) -> list[dict[str, Any]]:
    """The catalogue rules for a feature: a compile option by the rules' `options`, any other feature by the rules'
    `features` (the inventory's "category: key", #5565)."""
    if not catalogue:
        return []
    if category == "compile_options":
        option = key.split(":")[0].strip()
        return [r for r in catalogue["rules"] if option in r.get("options", [])]
    fid = f"{category}: {key}"
    return [r for r in catalogue["rules"] if fid in r.get("features", [])]


def _programs(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {r["program"]: r for r in report["programs"]}


def _texts(row: dict[str, Any]) -> list[str]:
    t = row["translation"]
    return ([t["refused"]] if t.get("refused") else []) + list(t.get("holes") or [])


def _eras(inventory: dict[str, Any]) -> dict[str, Any] | None:
    """#5117: the estate's era distribution, its mixed programs and the programs behind each era (None: an inventory
    from before era tags). Each program lists the tells its tag used."""
    e = inventory.get("eras")
    if not e:
        return None
    progs = e["programs"]
    return {
        "summary": e["summary"],
        "mixed": {
            p: [t["tell"] + f" (era {t['era']})" for t in v["tells"]] for p, v in sorted(progs.items()) if v["mixed"]
        },
        "programs": {
            era: sorted(p for p, v in progs.items() if str(v["era"] if v["era"] is not None else "none") == era)
            for era in ("0", "1", "2", "3", "4", "none")
        },
    }


def build_estate(
    estate: str,
    inventory: dict[str, Any],
    report: dict[str, Any],
    rmap: dict[str, Any],
    catalogue: dict[str, Any] | None,
    register: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    progs = _programs(report)
    # Every refusal / hole text of every program, and every copybook gap of the inventory, classified.
    hits: dict[str, list[tuple[str, dict[str, Any] | None]]] = defaultdict(list)  # program -> [(text, entry)]
    for p, row in progs.items():
        for text in _texts(row):
            found = classify(text, rmap)
            hits[p].append((text, found[0] if len(found) == 1 else None))
    for key, v in inventory.get(GAPS, {}).items():
        if key == "unknown":
            continue
        text = "missing copybook " + key.removeprefix("COPY ").strip()
        found = classify(text, rmap)
        for p in v["programs"]:
            if (text, found[0] if len(found) == 1 else None) not in hits[p]:
                hits[p].append((text, found[0] if len(found) == 1 else None))

    for key, v in inventory.get(FAMILIES, {}).items():  # read as `<family> not supported`, like a gap
        text = f"{key} not supported"
        found = classify(text, rmap)
        for p in v["programs"]:
            if (text, found[0] if len(found) == 1 else None) not in hits[p]:
                hits[p].append((text, found[0] if len(found) == 1 else None))

    features = []
    for category in sorted(inventory):
        if category in (GAPS, FAMILIES, "unparsed_programs", "eras"):
            continue
        for key, v in sorted(inventory[category].items()):
            if key == "unknown":
                continue
            fid = f"{category}: {key}"
            users = v["programs"]
            proven = [p for p in users if progs.get(p, {}).get("level") in PROVEN_LEVELS]
            refusing: dict[str, list[str]] = defaultdict(list)  # entry id -> programs
            for p in users:
                for _text, e in hits.get(p, []):
                    if e and fid in e.get("features", []) and p not in refusing[e["id"]]:
                        refusing[e["id"]].append(p)
            refused_here = {p for ps in refusing.values() for p in ps}
            translated = [
                p
                for p in users
                if p in progs and progs[p]["translation"].get("statements") is not None and p not in refused_here
            ]
            status = PROVEN if proven else UNPROVEN if translated else REFUSED if refusing else UNKNOWN
            rules = match_rules(category, key, catalogue)
            worst = max((r["status"] for r in rules), key=RULE_ORDER.index, default=None)
            reg = sorted({x for r in rules for x in r.get("register", [])})
            missing = []
            if status in (REFUSED, UNKNOWN):
                missing.append("modelled")
            if not rules:
                missing.append("catalogued" if catalogue else "catalogued (no catalogue yet, #4711)")
            if status != PROVEN:
                missing.append("proven (L2)")
            if worst in ("ASSUMED", "DIFFERS"):
                missing.append(f"IBM-matched (worst rule {worst}: uncalibrated)")
            if not rules or any(r.get("calibration", "uncalibrated") == "uncalibrated" for r in rules):
                missing.append("calibrated on z/OS (#4702)")
            features.append(
                {
                    "feature": fid,
                    "programs": len(users),
                    "status": status,
                    "best_level": max((progs[p]["level"] for p in users if p in progs), default=None),
                    "cases": sorted(
                        {c["case"] for p in proven if (c := (progs[p].get("equivalence") or {}).get("chosen"))}
                    ),
                    "refusals": {k: sorted(ps) for k, ps in sorted(refusing.items())},
                    "rules": [r["id"] for r in rules],
                    "rule_status": worst,
                    "register": [
                        {"id": x, "status": (register or {}).get(x, {}).get("status", "not in the register")}
                        for x in reg
                    ],
                    "missing": missing,
                    "sequence_fragment": bool(SEQUENCE_FRAGMENT.search(key)),
                }
            )

    refusals: dict[str, dict[str, Any]] = {}
    unmapped: dict[str, list[str]] = defaultdict(list)
    for p, items in sorted(hits.items()):
        for text, e in items:
            if e is None:
                unmapped[text].append(p)
                continue
            r = refusals.setdefault(
                e["id"],
                {
                    "label": entry_label(e, rmap),
                    "issue": e.get("issue"),
                    "charter": rmap["charter"].get(e.get("charter") or ""),
                    "system_library": e.get("system_library"),
                    "api": e.get("api"),
                    "note": e.get("note"),
                    "programs": [],
                    "texts": [],
                },
            )
            if p not in r["programs"]:
                r["programs"].append(p)
            if text not in r["texts"]:
                r["texts"].append(text)
    for r in refusals.values():
        r["programs"].sort()
        r["texts"].sort()

    unknown = {
        "buckets": {
            c: {"count": v["unknown"]["count"], "programs": v["unknown"]["programs"]}
            for c, v in sorted(inventory.items())
            if c not in ("unparsed_programs", "eras") and v.get("unknown", {}).get("count")
        },
        "unparsed_programs": inventory.get("unparsed_programs", []),
        "sequence_fragments": [f["feature"] for f in features if f["sequence_fragment"]],
        "never_seen": [f["feature"] for f in features if f["status"] == UNKNOWN and not f["sequence_fragment"]],
    }
    counts = {s: sum(f["status"] == s for f in features) for s in STATUSES}
    return {
        "estate": estate,
        "burned": report.get("burned", True),
        "survey": (report.get("measured") or {}).get("survey", {}).get("sha"),
        "counts": counts,
        "features": features,
        "refusals": dict(sorted(refusals.items())),
        "unmapped": {k: sorted(v) for k, v in sorted(unmapped.items())},
        "eras": _eras(inventory),
        "needs_issue": sorted(k for k, r in refusals.items() if r["label"] == NEEDS_ISSUE),
        "unknown": unknown,
    }


def _register() -> dict[str, dict[str, str]]:
    import evidence_report  # tests/tools/evidence_report.py: the register's summary table

    return evidence_report.register()


def build(names: list[str] | None = None, catalogue_path: Path | None = CATALOGUE) -> dict[str, Any]:
    rmap = load_map()
    catalogue = load_catalogue(catalogue_path)
    register = _register() if catalogue else None
    out = {
        "format": "gitgalaxy-support-matrix/1",
        "catalogue": catalogue_path.name if catalogue and catalogue_path else None,
        "estates": {},
    }
    for name in names or estates():
        inv = _load(INVENTORY / f"{name}.json")
        rep = _load(REPORTS / name / "report.json")
        out["estates"][name] = build_estate(name, inv, rep, rmap, catalogue, register)
    if names is None and (nb := _non_burned_eras()):  # present only when non-empty (#5117)
        out["non_burned_eras"] = nb
    return out


def _non_burned_eras() -> dict[str, Any]:
    """#5117: era distributions of the non-burned estates, counts only (tests/tools/era_distribution.py)."""
    path = TOOLS.parent / "fixtures" / "era_distribution" / "summary.json"
    return _load(path)["estates"] if path.is_file() else {}


def _cell(x: Any) -> str:
    return str(x).replace("|", "\\|").replace("\n", " ")


def _progs(ps: list[str], n: int = 4) -> str:
    names = [p.rsplit("/", 1)[-1] for p in ps]
    return ", ".join(names[:n]) + (f" (+{len(names) - n})" if len(names) > n else "")


def render_eras(e: dict[str, Any] | None) -> list[str]:
    """#5117: the era section -- programs per era with the tells that placed them, and the mixed programs."""
    if not e:
        return []
    s = e["summary"]
    L = ["", "### Era (from the source's own tells, not dates)", ""]
    L.append(
        f"{s['programs']} programs; {s['mixed']} mixed (tells from more than one era: layered code). A program's era "
        "is the latest era any of its tells reaches; none = no tell."
    )
    L += ["", "| era | programs | share | examples |", "|---|---|---|---|"]
    for era, n in s["by_era"].items():
        share = f"{100 * n / s['programs']:.0f}%" if s["programs"] else "-"
        L.append(f"| {era} | {n} | {share} | {_progs(e['programs'][era])} |")
    if s.get("raised_by_copybook"):  # present only when a copybook raised a program's era (#5117)
        L += [
            "",
            f"{s['raised_by_copybook']} programs have a higher era than their own text shows: a copybook they COPY carries the tell.",
        ]
    if s.get("copybook_skipped"):  # present only when a program's copybook pass was skipped (#5195)
        L += [
            "",
            f"{s['copybook_skipped']} programs were tagged without their copybooks (the COPY expansion was refused): a tell in one is not counted.",
        ]
    L += ["", "Tells used (programs): " + (", ".join(f"{k} {v}" for k, v in s["tells"].items()) or "none") + ".", ""]
    if e["mixed"]:
        L += ["Mixed programs:", ""]
        L += [f"- {p}: {', '.join(t)}" for p, t in list(e["mixed"].items())[:20]]
        if len(e["mixed"]) > 20:
            L.append(f"- ... and {len(e['mixed']) - 20} more (see `--json`)")
    return L


def render_estate(m: dict[str, Any]) -> list[str]:
    L = [f"## {m['estate']}", ""]
    L.append(
        f"{'Burned estate (the translator was developed against it). ' if m['burned'] else ''}"
        f"Levels and refusals from its evidence report (survey at `{(m['survey'] or 'unknown')[:12]}`): a refusal "
        "fixed since shows until the evidence refresh."
    )
    L += ["", "| status | features |", "|---|---|"]
    L += [f"| {s} | {n} |" for s, n in m["counts"].items()]
    L += render_eras(m.get("eras"))
    L += ["", "### Features", ""]
    L += [
        "| feature | programs | status | best level | proving cases | rules (worst status; register caveats) | not yet met (charter section 5) |",
        "|---|---|---|---|---|---|---|",
    ]
    for f in m["features"]:
        refusals = "; ".join(f"{k}: {_progs(v)}" for k, v in f["refusals"].items())
        status = f["status"] + (f" (refused: {refusals})" if refusals else "")
        rules = ", ".join(f["rules"]) + (f" ({f['rule_status']})" if f["rule_status"] else "")
        if f["register"]:
            rules += "; register " + ", ".join(x["id"] for x in f["register"])
        L.append(
            f"| `{_cell(f['feature'])}` | {f['programs']} | {_cell(status)} | {f['best_level'] or '-'} | "
            f"{_cell(_progs(f['cases'], 3)) or '-'} | {_cell(rules) or '-'} | {_cell('; '.join(f['missing'])) or '-'} |"
        )
    L += ["", "### Refusals and holes", ""]
    if not m["refusals"] and not m["unmapped"]:
        L.append("None.")
    else:
        L += ["| refusal | owner | programs | texts |", "|---|---|---|---|"]
        for rid, r in m["refusals"].items():
            L.append(
                f"| {rid} | {_cell(r['label'])} | {_cell(_progs(r['programs']))} | {_cell('; '.join(r['texts'][:3]))} |"
            )
        for text, ps in m["unmapped"].items():
            L.append(f"| UNMAPPED | add it to refusal_map.json | {_cell(_progs(ps))} | {_cell(text)} |")
    if m["unmapped"] or m["needs_issue"]:
        L += [
            "",
            "**Acceptance gap (#4724): every refusal maps to an issue or an agreed refusal.** Unowned: "
            + ", ".join([*m["needs_issue"], *(f"`{t}`" for t in m["unmapped"])]),
        ]
    syslib = {k: r for k, r in m["refusals"].items() if r["system_library"]}
    L += ["", "### System copybooks (a configuration fix, not a translator limit)", ""]
    if not syslib:
        L.append("None.")
    for r in syslib.values():
        L.append(
            f"- {_progs(r['programs'], 10)}: {_cell('; '.join(r['texts']))}. "
            f"{_cell(r['note'] or 'Point the scanner at ' + r['system_library'] + '.')}"
        )
    apis = {k: r for k, r in m["refusals"].items() if r["api"]}
    L += ["", "### Runtime APIs not modelled (translates, not provable)", ""]
    if not apis:
        L.append("None.")
    for r in apis.values():
        a = r["api"]
        owner = f" (#{a['issue']})" if a.get("issue") else " (no issue yet)"
        L.append(f'- {a["name"]}{owner}: {_progs(r["programs"], 10)}. Never "supported" while it is unmodelled.')
    u = m["unknown"]
    L += ["", "### Unknown, for triage", ""]
    for c, b in u["buckets"].items():
        L.append(f"- `{c}` unknown bucket: {b['count']} in {_progs(b['programs'])}")
    for p in u["unparsed_programs"]:
        L.append(f"- not parsed by the inventory: {p['program']} ({_cell(p['reason'])})")
    if u["sequence_fragments"]:
        heads = sorted({x for x in u["sequence_fragments"] if x.startswith("cics_commands: ")})
        L.append(
            f"- {len(u['sequence_fragments'])} keys holding a sequence-area number (the inventory read a line's "
            "sequence number as a word), e.g. " + ", ".join(f"`{x}`" for x in (heads or u["sequence_fragments"])[:8])
        )
    if u["never_seen"]:
        L.append("- never translated (only in programs refused whole): " + ", ".join(f"`{x}`" for x in u["never_seen"]))
    if not any(u.values()):
        L.append("None.")
    return [*L, ""]


def render_non_burned_eras(nb: dict[str, Any]) -> list[str]:
    """#5117: one table of the non-burned estates' era counts. Counts only: nothing per program is committed for them."""
    L = ["## Era, non-burned estates (counts only)", ""]
    L.append(
        "Not burned, so no per-program data is committed (first-contact numbers stay first-contact); `census-*` labels "
        "are opaque. A program's era is the latest era any of its tells reaches; none = no tell."
    )
    L += ["", "| estate | programs | 0 | 1 | 2 | 3 | 4 | none | mixed |", "|---|---|---|---|---|---|---|---|---|"]
    for name, e in sorted(nb.items()):
        b = e["by_era"]
        L.append(
            f"| {name} | {e['programs']} | "
            + " | ".join(str(b[k]) for k in ("0", "1", "2", "3", "4", "none"))
            + f" | {e['mixed']} |"
        )
    return [*L, ""]


def render(matrix: dict[str, Any] | None = None) -> str:
    m = matrix or build()
    catalogue = (
        f"`{m['catalogue']}` (features matched to rules by their `features` keys)."
        if m["catalogue"]
        else "not yet catalogued (#4711): every feature misses that condition."
    )
    L = [
        "---",
        (
            'description: "Support matrix (#4724): per burned estate, each inventoried COBOL / CICS / SQL feature as '
            'proven, unproven, refused by name or unknown, joined with the rule catalogue and the refusals."'
        ),
        "---",
        "# Support matrix (generated)",
        "",
        (
            "> Rendered by `tests/tools/support_matrix.py --out FILE` from committed sources (the feature inventory, "
            "the evidence reports, `refusal_map.json`, the rule catalogue); the page itself is not committed. What "
            '"supported" means: [definition_of_done.md](https://github.com/squid-protocol/gitgalaxy/blob/main/docs/'
            "language_status/definition_of_done.md) section 5."
        ),
        "",
        (
            "Status: **supported and proven** (a program using it is at L2+), **supported, unproven** (translated, "
            "no proof), **refused by name** (a refusal names it), **unknown / never seen** (only in programs refused "
            "whole). Proof is per program: L2 does not say a scenario reached the feature."
        ),
        "",
        "Rule catalogue: " + catalogue,
        "",
    ]
    for e in m["estates"].values():
        L += render_estate(e)
    if m.get("non_burned_eras"):
        L += render_non_burned_eras(m["non_burned_eras"])
    return "\n".join(L).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("estates", nargs="*", help="burned estates (default: all)")
    ap.add_argument("--json", action="store_true", help="print the matrix as JSON")
    ap.add_argument("--catalogue", type=Path, default=CATALOGUE, help="the rule catalogue (default: %(default)s)")
    ap.add_argument("--out", type=Path, help="write here instead of stdout")
    args = ap.parse_args(argv)
    unknown = sorted(set(args.estates) - set(estates()))
    if unknown:
        ap.error(f"not a burned estate with a report and an inventory: {', '.join(unknown)}")
    m = build(args.estates or None, args.catalogue)
    text = json.dumps(m, indent=1, sort_keys=True) + "\n" if args.json else render(m)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
