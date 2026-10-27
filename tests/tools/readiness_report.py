#!/usr/bin/env python3
"""#4725: the readiness scanner's report -- per burned estate, what translates whole today (the evidence ladder, with
counts) and the ranked rules to land, from committed tool outputs only (no corpus, no scan).

    python tests/tools/readiness_report.py [ESTATE ...] [--json] [--previous FILE] [--out FILE]
    python tests/tools/readiness_report.py [ESTATE ...] --blockers DIR --salt-file FILE [--redact-more subclass counts]

Sources (nothing is re-measured here):
  levels / translation   the estate's evidence report.json (evidence_report.py, #4601): each program's level and its
                         translate-only result (whole, holes, refusal, gap classes)
  rules to land          cics_census.blockers() over those programs' gap classes -- the ranking of
                         `cics_census.py blockers`, not a second one. `only` = programs the rule alone leaves not
                         whole, `one_away` = programs it leaves one rule from whole, `touched` = all with it
  proofs to land         the same ranking one level up (#5229): for each program translated whole, what its `next`
                         entries say stops it being proven (coverage below the bar, no case, a Db2 case CI does not
                         sweep, a callee with holes), ranked by proof_blockers.rank() -- derived from the report, not a
                         proof_blockers run (that needs a survey and the corpora). The L5 mutant entry is left out
  era                    tests/fixtures/feature_inventory/<estate>.json `eras` (era_tags.py, #5117)
  missing inputs         estate_intake.py (#4709): assumed options and missing copybooks
  oracle caveats         the register entries each program relies on: those it reaches when its evidence report
                         measured that (`assumptions.reach.registers`), else those its commands name (an upper bound,
                         counted per row in `named_only`; the report does not yet measure reach,
                         definition_of_done.md section 3)
  blocker twins          (#5054) with --blockers DIR the same run also writes, per estate, DIR/<estate>/
                         blocker_report.full.* and the anonymized blocker_report.anon.* (blocker_report.py) from the
                         programs' gap classes (a whole program: its proof classes; any other: its translation gaps)
  charter                the levels and bars of definition_of_done.md section 2, as the report carries them

"Translated whole" is level L1 and says nothing about proof: the ladder below it is counted with it. A program is not
whole while a program it CALLs or LINKs to has holes (#4803): it is counted as whole-translated with a callee that has
holes, and stays below L2. `--previous` reads an earlier `--json` output and prints the change. The output carries no
date, path or host, so a re-run of the same sources is identical.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))

INVENTORY = TOOLS.parent / "fixtures" / "feature_inventory"
OPTIONS = TOOLS.parent / "equivalence" / "estate_options"
REPORTS: Path | None = None  # None: support_matrix.REPORTS (the published reports, materialized on demand)
LEVELS = ("L0", "L1", "L2", "L3", "L4", "L5")
ERAS = ("0", "1", "2", "3", "4", "none")
CALLEE = re.compile(r"\b(?:CALLs|LINKs)\b.*\bholes?\b")  # evidence_report's "EPSCSMRT CALLs EPSMPMT, which has holes"
TOP = 15
# #5229: the evidence report's `next` text -> a proof gap class (numbers and case ids stripped so equal causes group).
# None: not a proof blocker (the L5 hook is "not yet measured" for every program).
PROOF_CLASSES: tuple[tuple[re.Pattern[str], str | None], ...] = (
    (re.compile(r"^every surviving mutant"), None),
    (re.compile(r"^an equivalence case that runs it"), "no case"),
    (re.compile(r"^its det port equal on every scenario of .*\b(?:CALLs|LINKs)\b.*\bholes?\b"), "callee has holes"),
    (
        re.compile(r"^its det port equal on every scenario of .*ledgered as differing"),
        "known unproven: det sweep baseline",
    ),
    (re.compile(r"^its det port equal on every scenario of .*a Db2 case"), "not proven in CI: Db2"),
    (re.compile(r"^paragraph coverage .*\(coverage not measured"), "coverage: not measured"),
    (re.compile(r"^paragraph coverage"), "coverage: paragraphs below the bar"),
    (re.compile(r"^branch coverage .*\(coverage not measured"), "coverage: not measured"),
    (re.compile(r"^branch coverage"), "coverage: branch outcomes below the bar"),
)
PROOF_CLASS_NAMES = frozenset(n for _, n in PROOF_CLASSES if n)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _reports() -> Path:
    import support_matrix

    if REPORTS is not None:
        return REPORTS
    if not any(support_matrix.REPORTS.glob("*/report.json")):  # #6722: a fresh checkout has none; `generated` does
        import evidence_report

        evidence_report.materialize()
    return support_matrix.REPORTS


def estates() -> list[str]:
    """The burned estates with a report and an inventory."""
    import support_matrix

    if REPORTS is None:
        return support_matrix.estates()
    return sorted(
        d.name for d in REPORTS.iterdir() if (d / "report.json").is_file() and (INVENTORY / f"{d.name}.json").is_file()
    )


def era_of(inventory: dict[str, Any]) -> dict[str, str]:
    """program -> era ('0'..'4' or 'none') from the inventory; empty before era tags existed."""
    progs = (inventory.get("eras") or {}).get("programs") or {}
    return {p: str(v["era"]) if v.get("era") is not None else "none" for p, v in progs.items()}


def ladder(programs: list[dict[str, Any]]) -> dict[str, Any]:
    """The evidence ladder with counts: levels, translation outcome, and the refusal reasons."""
    levels = Counter(p["level"] for p in programs)
    whole = [p for p in programs if p["translation"]["whole"]]
    refused = [p for p in programs if p["translation"].get("refused")]
    callee = [p for p in whole if any(CALLEE.search(n) for n in p.get("next") or [])]
    reasons = Counter(g for p in refused for g in p["translation"]["gap_classes"])
    return {
        "programs": len(programs),
        "levels": {lv: levels.get(lv, 0) for lv in LEVELS},
        "translated_whole": len(whole),
        "whole_with_callee_holes": len(callee),
        "with_holes": len(programs) - len(whole) - len(refused),
        "refused": len(refused),
        "refusal_reasons": dict(sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0]))),
        "executed_equivalent_or_above": sum(levels.get(lv, 0) for lv in LEVELS[2:]),
    }


def rules_to_land(programs: list[dict[str, Any]], estate: str, eras: dict[str, str], top: int = TOP) -> dict[str, Any]:
    """cics_census.blockers() over the estate's programs; each rule with the era mix of the programs it alone blocks."""
    import cics_census

    rows = {(estate, p["program"]): {"gap_classes": p["translation"]["gap_classes"]} for p in programs}
    res = cics_census.blockers(rows)
    sole: dict[str, list[str]] = defaultdict(list)
    for p in programs:
        if len(p["translation"]["gap_classes"]) == 1:
            sole[p["translation"]["gap_classes"][0]].append(p["program"])
    gaps = []
    for g in res["gaps"]:
        mix = Counter(eras.get(name, "none") for name in sole.get(g["gap"], []))
        gaps.append(
            {
                "gap": g["gap"],
                "only": g["only"],
                "one_away": g["one_away"],
                "touched": g["touched"],
                "refuses_program": g["refuses_program"],
                "only_by_era": {e: mix[e] for e in ERAS if mix[e]},
            }
        )
    return {"classes": len(gaps), "histogram": res["histogram"], "ranked": gaps[:top] if top else gaps}


def proof_class(text: str) -> str | None:
    """The proof gap class of one `next` entry; None for the L5 hook. An entry no pattern knows keeps its (digit-free)
    text, so a new wording shows up in the ranking instead of vanishing."""
    for pat, name in PROOF_CLASSES:
        if pat.search(text):
            return name
    return re.sub(r"\d+(?:\.\d+)?", "N", text)[:110]


def proofs_to_land(programs: list[dict[str, Any]], top: int = TOP) -> dict[str, Any]:
    """proof_blockers.rank() over the programs translated whole: each one's gaps are the classes of its `next`."""
    import proof_blockers

    progs: dict[tuple[str, str], tuple[bool, set[str]]] = {}
    for p in programs:
        if p["translation"]["whole"]:
            gaps = {c for n in p.get("next") or [] if (c := proof_class(n))}
            progs[("", p["program"])] = (True, gaps)
    res = proof_blockers.rank(progs)
    ranked = [{k: g[k] for k in ("gap", "only", "one_away", "touched")} for g in res["gaps"]]
    return {
        "whole": res["whole"],
        "proven": res["proven"],
        "histogram": res["histogram"],
        "classes": len(ranked),
        "ranked": ranked[:top] if top else ranked,
    }


def blocker_result(estate: str, programs: list[dict[str, Any]]) -> dict[str, Any]:
    """The report's own gaps as a proof_blockers-shaped result (blocker_report.py's input): per program the proof
    classes when translated whole, else the translation gap classes; ranked by proof_blockers.rank()."""
    import proof_blockers

    gaps_of: dict[str, list[str]] = {}
    for p in programs:
        if p["translation"]["whole"]:
            found = {c for n in p.get("next") or [] if (c := proof_class(n))}
        else:
            found = set(p["translation"]["gap_classes"])
        gaps_of[p["program"]] = sorted(found)
    res = proof_blockers.rank({(estate, n): (True, set(g)) for n, g in gaps_of.items()})
    res["programs"] = [{"corpus": estate, "program": n, "case": None, "gaps": g} for n, g in sorted(gaps_of.items())]
    return res


def write_blockers(
    names: list[str], out: Path, salt: bytes, redact_more: tuple[str, ...] = ()
) -> dict[str, dict[str, Path]]:
    """#5054: the full and the anonymized blocker report of each estate, from the same data as the readiness report."""
    import blocker_report

    reports = _reports()
    paths = {}
    for n in names:
        programs = sorted(_load(reports / n / "report.json")["programs"], key=lambda p: p["program"])
        paths[n] = blocker_report.write_reports(blocker_result(n, programs), out / n, salt, n, redact_more)
    return paths


def caveats(programs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Register entries each program relies on, with the programs relying on them.

    A program whose evidence report measured reach (`assumptions.reach` a dict with `registers`, #5229) counts only the
    entries it reaches; any other program counts every entry its commands name, an upper bound. A row carries
    `named_only` (programs counted by the upper bound) only when it is non-zero."""
    seen: dict[str, dict[str, Any]] = {}
    for p in programs:
        a = p.get("assumptions") or {}
        named = {e["id"]: e for e in a.get("named_by_commands") or []}
        reach = a.get("reach")
        measured = isinstance(reach, dict) and isinstance(reach.get("registers"), list)
        for rid in sorted(set(reach["registers"]) & set(named)) if measured else sorted(named):
            e = named[rid]
            row = seen.setdefault(rid, {"id": rid, "status": e["status"], "area": e["area"], "programs": 0})
            row["programs"] += 1
            if not measured:
                row["named_only"] = row.get("named_only", 0) + 1
    return sorted(seen.values(), key=lambda r: (-r["programs"], r["id"]))


def missing_inputs(estate: str, report: dict[str, Any]) -> dict[str, Any]:
    import estate_intake

    path = OPTIONS / f"{estate}.json"
    assumed = (
        estate_intake.assumed_values({s: v for s, v in _load(path).items() if s != "_comment"})
        if path.is_file()
        else []
    )
    sections = Counter(a["section"] for a in assumed)
    return {
        "assumed_options": len(assumed),
        "by_checklist_section": {k: sections[k] for k in sorted(sections)},
        "missing_copybooks": estate_intake.missing_copybooks(report),
    }


def build_estate(estate: str, report: dict[str, Any], inventory: dict[str, Any], top: int = TOP) -> dict[str, Any]:
    programs = sorted(report["programs"], key=lambda p: p["program"])
    eras = era_of(inventory)
    era_counts = Counter(eras.get(p["program"], "none") for p in programs)
    out = {
        "estate": estate,
        "ladder": ladder(programs),
        "eras": {e: era_counts[e] for e in ERAS},
        "rules_to_land": rules_to_land(programs, estate, eras, top),
        "proofs_to_land": proofs_to_land(programs, top),
        "missing_inputs": missing_inputs(estate, report),
        "oracle_caveats": caveats(programs),
        "charter": {"bars": report["bars"], "levels": report["levels"]},
    }
    if not eras:
        out["eras_note"] = "the inventory predates era tags"
    return out


def build(names: list[str] | None = None, top: int = TOP) -> dict[str, Any]:
    reports = _reports()
    return {
        "format": 1,
        "estates": {
            n: build_estate(n, _load(reports / n / "report.json"), _load(INVENTORY / f"{n}.json"), top)
            for n in (names or estates())
        },
    }


def pct(n: int, d: int) -> str:
    return f"{100 * n / d:.0f}%" if d else "-"


def delta(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """The change from an earlier `--json` output: per estate, the ladder counts and each rule's rank and `only`."""
    out: dict[str, Any] = {}
    for name, cur in new["estates"].items():
        prev = (old.get("estates") or {}).get(name)
        if prev is None:
            out[name] = {"new_estate": True}
            continue
        lad = {
            k: [prev["ladder"][k], cur["ladder"][k]]
            for k in ("translated_whole", "with_holes", "refused", "executed_equivalent_or_above")
            if prev["ladder"][k] != cur["ladder"][k]
        }
        old_rank = {g["gap"]: (i + 1, g["only"]) for i, g in enumerate(prev["rules_to_land"]["ranked"])}
        rules = {}
        for i, g in enumerate(cur["rules_to_land"]["ranked"], 1):
            was = old_rank.get(g["gap"])
            if was != (i, g["only"]):
                rules[g["gap"]] = {"rank": [was[0] if was else None, i], "only": [was[1] if was else None, g["only"]]}
        gone = sorted(set(old_rank) - {g["gap"] for g in cur["rules_to_land"]["ranked"]})
        old_p = {
            g["gap"]: (i + 1, g["only"]) for i, g in enumerate((prev.get("proofs_to_land") or {}).get("ranked", []))
        }
        proofs = {}
        for i, g in enumerate(cur["proofs_to_land"]["ranked"], 1):
            was = old_p.get(g["gap"])
            if was != (i, g["only"]):
                proofs[g["gap"]] = {"rank": [was[0] if was else None, i], "only": [was[1] if was else None, g["only"]]}
        out[name] = {"ladder": lad, "rules": rules, "no_longer_ranked": gone, "proofs": proofs}
    return out


def render_estate(m: dict[str, Any], d: dict[str, Any] | None = None) -> list[str]:
    lad, n = m["ladder"], m["ladder"]["programs"]
    out = [
        f"## {m['estate']}",
        "",
        f"{n} programs. Evidence ladder (counts; the oracle is GnuCOBOL plus our stub, not z/OS):",
        "",
        "| level | programs at exactly this level |",
        "|---|---|",
    ]
    names = {lv["level"]: lv["name"] for lv in m["charter"]["levels"]}
    out += [f"| {lv} {names.get(lv, '')} | {c} |" for lv, c in lad["levels"].items()]
    out += [
        "",
        (
            f"- translated whole: {lad['translated_whole']} / {n} ({pct(lad['translated_whole'], n)}); "
            f"with holes: {lad['with_holes']}; refused: {lad['refused']}"
        ),
        (
            "- whole-translated but a CALL / LINK target has holes (below L2 until it is closed): "
            f"{lad['whole_with_callee_holes']}"
        ),
        f"- executed equivalent (L2 and above): {lad['executed_equivalent_or_above']} / {n}",
        (
            f"- charter bars for L3 / L4: paragraphs {m['charter']['bars']['paragraphs']}%, "
            f"branches {m['charter']['bars']['branches']}%"
        ),
    ]
    if lad["refusal_reasons"]:
        out += ["", "Refused whole, by reason:", ""] + [f"- {c} x {r}" for r, c in lad["refusal_reasons"].items()]
    out += ["", "Era evidence (programs by latest era a tell reaches):", ""]
    out.append(
        ", ".join(f"era {e}: {c}" for e, c in m["eras"].items()) + (f" ({m['eras_note']})" if "eras_note" in m else "")
    )
    r = m["rules_to_land"]
    out += [
        "",
        f"### Rules to land ({r['classes']} gap classes; top {len(r['ranked'])}, the `cics_census.py blockers` order)",
        "",
        "| rank | rule (gap class) | makes whole alone | one rule away | touched | era mix of the alone-set |",
        "|---|---|---|---|---|---|",
    ]
    for i, g in enumerate(r["ranked"], 1):
        mix = ", ".join(f"era {e}: {c}" for e, c in g["only_by_era"].items()) or "-"
        star = " (refuses the whole program: upper bound)" if g["refuses_program"] else ""
        out.append(f"| {i} | {g['gap'][:110]}{star} | {g['only']} | {g['one_away']} | {g['touched']} | {mix} |")
    pr = m["proofs_to_land"]
    out += [
        "",
        (
            f"### Proof blockers ({pr['whole']} programs translated whole, {pr['proven']} with no proof gap; "
            f"top {len(pr['ranked'])} of {pr['classes']} classes, `proof_blockers.py` statistics)"
        ),
        "",
        "| rank | what stops the proof | alone | one gap away | touched |",
        "|---|---|---|---|---|",
    ]
    out += [
        f"| {i} | {g['gap'][:110]} | {g['only']} | {g['one_away']} | {g['touched']} |"
        for i, g in enumerate(pr["ranked"], 1)
    ]
    mi = m["missing_inputs"]
    out += ["", "### Missing inputs", "", f"- assumed options awaiting customer confirmation: {mi['assumed_options']}"]
    if mi["by_checklist_section"]:
        out.append(
            "- by estate_intake checklist section: "
            + ", ".join(f"{k}: {v}" for k, v in mi["by_checklist_section"].items())
        )
    cb = mi["missing_copybooks"]
    out.append("- missing copybooks: " + (", ".join(f"{k} ({len(v)})" for k, v in cb.items()) if cb else "none"))
    upper = any(c.get("named_only") for c in m["oracle_caveats"])
    title = "Oracle caveats the estate relies on" + (
        " (upper bound where a program's reach is unmeasured)" if upper else ""
    )
    out += ["", f"### {title}", ""]
    if m["oracle_caveats"]:
        out += [
            "| id | status | area | programs |" + (" named only |" if upper else ""),
            "|---|---|---|---|" + ("---|" if upper else ""),
        ]
        out += [
            f"| {c['id']} | {c['status']} | {c['area']} | {c['programs']} |"
            + (f" {c.get('named_only', 0)} |" if upper else "")
            for c in m["oracle_caveats"]
        ]
    else:
        out.append("None named.")
    if d is not None:
        out += ["", "### Since the previous run", ""]
        if d.get("new_estate"):
            out.append("Not in the previous run.")
        else:
            out += [f"- {k}: {a} -> {b}" for k, (a, b) in d["ladder"].items()] or ["- ladder counts unchanged"]
            out += [f"- rule `{g[:80]}`: rank {v['rank'][0]} -> {v['rank'][1]}, alone {v['only'][0]} -> {v['only'][1]}"
                    for g, v in d["rules"].items()]  # fmt: skip
            out += [f"- rule `{g[:80]}` is no longer ranked" for g in d["no_longer_ranked"]]
            out += [
                f"- proof gap `{g[:80]}`: rank {v['rank'][0]} -> {v['rank'][1]}, alone {v['only'][0]} -> {v['only'][1]}"
                for g, v in d.get("proofs", {}).items()
            ]
    return [*out, ""]


def render(report: dict[str, Any] | None = None, previous: dict[str, Any] | None = None) -> str:
    rep = report or build()
    d = delta(previous, rep) if previous else None
    out = [
        "# Readiness report (#4725)",
        "",
        "Per burned estate: what translates whole today and the rules that would make more programs whole. Measured against",
        'the charter in `definition_of_done.md`. Counts only; a level is an evidence level, never a bare "proven".',
        "",
    ]
    for name, m in rep["estates"].items():
        out += render_estate(m, d[name] if d else None)
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("estates", nargs="*", help="burned estates (default: all)")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    ap.add_argument("--previous", type=Path, help="an earlier --json output to compare with")
    ap.add_argument("--top", type=int, default=TOP, help="rules listed per estate (0: all)")
    ap.add_argument("--reports", type=Path, help="read evidence reports from here (default: the published ones)")
    ap.add_argument("--out", type=Path, help="write here instead of stdout")
    ap.add_argument("--blockers", type=Path, help="also write each estate's full and anonymized blocker reports here")
    ap.add_argument(
        "--salt-file", type=Path, help="the salt of the anonymized hashes (--blockers; created when missing)"
    )
    ap.add_argument("--redact-more", nargs="*", default=[], help="anonymized report: drop subclass / counts / repro")
    args = ap.parse_args(argv)
    if args.blockers and not args.salt_file:
        ap.error("--blockers needs --salt-file: one salt is what keeps the hashes comparable between runs")
    if args.reports:
        global REPORTS
        REPORTS = args.reports
    unknown = sorted(set(args.estates) - set(estates()))
    if unknown:
        ap.error(f"not a burned estate with a report and an inventory: {', '.join(unknown)}")
    if args.blockers:
        import blocker_report

        bad = sorted(set(args.redact_more) - set(blocker_report.REDACTIONS))
        if bad:
            ap.error(f"--redact-more: unknown {', '.join(bad)}; choose from {', '.join(blocker_report.REDACTIONS)}")
        salt = blocker_report.load_salt(args.salt_file)
        write_blockers(args.estates or estates(), args.blockers, salt, tuple(args.redact_more))
    rep = build(args.estates or None, args.top)
    prev = _load(args.previous) if args.previous else None
    text = json.dumps(rep, indent=1, sort_keys=True) + "\n" if args.json else render(rep, prev)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
