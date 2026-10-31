#!/usr/bin/env python3
"""#5280: the progress page -- every status number the READMEs used to hand-write, rendered from committed artifacts.

    python tests/tools/progress_report.py [--json] [--out FILE]
    python tests/tools/progress_report.py fetch [--cache FILE]     # write the issues cache (needs GITHUB_TOKEN or gh auth)

`generated_docs.PAGES` renders `docs/language_status/progress.md` and `progress.json` from `build()`; the generated-docs
workflow publishes them to the `generated` branch. Main never commits them (#5057) and the READMEs only link them.

Every denominator is fixed:
  burned ladder      the programs of the burned estates' evidence reports (evidence_report.py, estate4_draw.BURNED_NAMES)
  translator         programs translated whole, out of those same programs
  CICS               the commands a burned program uses: census `burned > 0` in cics_spec_status.json, the "(unlisted)"
                     and "(unparsed)" forms included (they are counted as not modelled). The whole spec is a separate
                     line, frontier context
  cobolrt rules      cobolrt_rules.json status counts; "measured on z/OS" = a rule with a calibration other than
                     `uncalibrated`
  det mutation       the estate reports' det-port results, what L5 reads, with the ledgers' sample and the reviewed
                     survivor claims (tests/equivalence/det_mutation*/)
  hand ports         mutation_scores.json (mutation_scores.scores), adjusted and raw: model / hand ports, not the
                     translator's, so it never feeds a level
  capabilities       capability_ledger.py: what exists, counted from the code, with the zeros left in
  test estates       cics-crucible's report, shown next to the ladder and never in its fixed denominator
  crucibles          tests/cics_crucible/coverage.json and tests/estate_crucible/baseline.json
  eras               feature_inventory `eras` (era_tags.py) against each program's level
  core burn-down     GitHub issues by `scope:*` label, from a cached JSON (offline, hermetic) or the API when a token is
                     set. No cache and no token: the section says so and prints no number

A level is an evidence level, never a bare "proven": the oracle is GnuCOBOL plus IBM documentation, not z/OS. Nothing in
the output is read from the clock: the issue windows end at the cache's own `fetched_at`.
"""

from __future__ import annotations

import argparse
import functools
import json
import os
import subprocess
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO))

import capability_ledger  # noqa: E402
import ladder_exclusions  # noqa: E402

FORMAT = "gitgalaxy-progress/1"
STATUS_DOCS = REPO / "docs" / "language_status"
SPEC_STATUS = STATUS_DOCS / "cics_spec_status.json"
RULES = STATUS_DOCS / "cobolrt_rules.json"
MUTATION = STATUS_DOCS / "mutation_scores.json"
CICS_CRUCIBLE = REPO / "tests" / "cics_crucible" / "coverage.json"
ESTATE_CRUCIBLE = REPO / "tests" / "estate_crucible" / "baseline.json"
ISSUES_CACHE = STATUS_DOCS / "progress_issues_cache.json"  # git-ignored (*.json); `fetch` writes it
CACHE_ENV = "PROGRESS_ISSUES_CACHE"
REPO_SLUG = "squid-protocol/gitgalaxy"
TEST_ESTATES = ("cics-crucible",)  # written to break the translator: shown, never in the burned denominator
CORE_MILESTONE = 28
FRONTIER_MILESTONE = 30
WINDOW_DAYS = 7
LEVELS = ("L0", "L1", "L2", "L3", "L4", "L5")
ERAS = ("0", "1", "2", "3", "4", "none")
SCOPES = ("core", "sweep", "frontier", "infra")
OPEN_WORLD_EPICS = (4890, 4891, 4892, 4893, 4894)  # the slide's runtime rows read their states (#5286)
TITLE_TERMS = ("CICS", "COBOL")  # issues with the term in the title, for the slide's resolved-issue boxes (#5286)
NOT_CONVERGING = "not converging"
SOURCES = {
    "ladder": "docs/language_status/evidence_report/<estate>/report.json (evidence_report.py, generated branch)",
    "cics": "docs/language_status/cics_spec_status.json (cics_spec_status.py)",
    "rules": "docs/language_status/cobolrt_rules.json",
    "mutation": "docs/language_status/mutation_scores.json",
    "det_mutation": "the estate reports, tests/equivalence/det_mutation/, tests/equivalence/det_mutation_survivors/",
    "capabilities": "tests/tools/capability_ledger.py, from the code",
    "crucibles": "tests/cics_crucible/coverage.json, tests/estate_crucible/baseline.json",
    "eras": "tests/fixtures/feature_inventory/<estate>.json (era_tags.py)",
    "issues": "GitHub issues by scope:* label (progress_issues_cache.json)",
}


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def pct(n: int, d: int) -> float | None:
    return round(100.0 * n / d, 1) if d else None


def pct_text(n: int, d: int) -> str:
    p = pct(n, d)
    return "n/a" if p is None else f"{p:.1f}%"


# ---- 1. the burned-estate ladder, and the eras ---------------------------------------------------------------------


def ladder(programs: list[dict[str, Any]]) -> dict[str, Any]:
    levels = Counter(p["level"] for p in programs)
    n = len(programs)
    l2 = sum(levels.get(lv, 0) for lv in LEVELS[2:])
    l4 = sum(levels.get(lv, 0) for lv in LEVELS[4:])
    whole = sum(1 for p in programs if p["translation"]["whole"])
    return {
        "programs": n,
        "levels": {lv: levels.get(lv, 0) for lv in LEVELS},
        "l2_plus": l2,
        "l2_plus_pct": pct(l2, n),
        "l4_plus": l4,
        "l4_plus_pct": pct(l4, n),
        "l5": levels.get("L5", 0),
        "translated_whole": whole,
    }


def sum_ladders(parts: list[dict[str, Any]]) -> dict[str, Any]:
    levels = {lv: sum(p["levels"][lv] for p in parts) for lv in LEVELS}
    n = sum(p["programs"] for p in parts)
    l2 = sum(levels[lv] for lv in LEVELS[2:])
    l4 = sum(levels[lv] for lv in LEVELS[4:])
    return {
        "programs": n,
        "levels": levels,
        "l2_plus": l2,
        "l2_plus_pct": pct(l2, n),
        "l4_plus": l4,
        "l4_plus_pct": pct(l4, n),
        "l5": levels["L5"],
        "translated_whole": sum(p["translated_whole"] for p in parts),
    }


def era_table(per_estate: dict[str, list[tuple[str, str]]]) -> dict[str, Any]:
    """per_estate: estate -> [(era, level)] for each program; programs per era with how many are at L2+ / L4+."""
    rows = {e: {"programs": 0, "l2_plus": 0, "l4_plus": 0} for e in ERAS}
    for pairs in per_estate.values():
        for era, level in pairs:
            r = rows[era if era in rows else "none"]
            r["programs"] += 1
            r["l2_plus"] += level in LEVELS[2:]
            r["l4_plus"] += level in LEVELS[4:]
    return rows


# ---- 2. components --------------------------------------------------------------------------------------------------


def cics_component(census: dict[str, Any], spec_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The burned denominator is census `burned > 0`; a key the translator maps to no spec entry is not modelled."""
    by_key = {r["key"]: r for r in spec_rows}
    used = sorted(k for k, v in census.items() if v.get("burned", 0) > 0)
    modelled, unmodelled = [], []
    for k in used:
        r = by_key.get(k)
        ok = r is not None and r["entry"] != "name-only" and r["translator"].startswith("yes") and r["stub"] == "yes"
        (modelled if ok else unmodelled).append(k)
    kinds = Counter(r["entry"] for r in spec_rows)
    return {
        "burned_commands": len(used),
        "modelled_both_runtimes": len(modelled),
        "not_modelled": len(unmodelled),
        "not_modelled_commands": unmodelled,
        "unlisted_or_unparsed": sum(1 for k in used if k.startswith("(")),
        "spec": {
            "entries": len(spec_rows),
            "full": kinds.get("full", 0),
            "engine_only": kinds.get("engine-only", 0),
            "name_only": kinds.get("name-only", 0),
        },
    }


def rules_component(doc: dict[str, Any]) -> dict[str, Any]:
    rules = doc["rules"]
    status = Counter(r["status"] for r in rules)
    measured = sum(1 for r in rules if r.get("calibration") not in (None, "uncalibrated"))
    families: dict[str, dict[str, int]] = {f["id"]: {} for f in doc.get("families", [])}
    for r in rules:
        fam = families.setdefault(r.get("family", "?"), {})
        fam[r["status"]] = fam.get(r["status"], 0) + 1
    out = {
        "rules": len(rules),
        "status": {s: status.get(s, 0) for s in ("MATCHED", "DIFFERS", "ASSUMED", "REFUSED")},
        "measured_on_zos": measured,
    }
    if families:  # the slide's per-family bars (#5286); added only when non-empty
        out["families"] = {k: dict(sorted(v.items())) for k, v in families.items()}  # the catalogue's own order
    return out


def mutation_component(doc: dict[str, Any]) -> dict[str, Any]:
    import mutation_scores

    caught = raw = adjusted = 0
    for port in doc["ports"]:
        c, r, a = mutation_scores.scores(port["total"])
        caught, raw, adjusted = caught + c, raw + r, adjusted + a
    return {
        "ports": len(doc["ports"]),
        "killed": caught,
        "adjusted_total": adjusted,
        "adjusted_kill_pct": pct(caught, adjusted),
        "raw_total": raw,
        "raw_kill_pct": pct(caught, raw),
    }


def det_mutation_component(
    reports: dict[str, dict[str, Any]], ledger: dict[str, dict[str, Any]], claims: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    """Per estate, what L5 rests on. `ready` passes on its last measurement but is not current, so it is not L5. The
    raw score and the sample stay next to each other: L5 has no score bar, it needs every survivor accounted for."""
    by_program: dict[str, str] = {}
    for case, entry in sorted(ledger.items()):
        by_program.setdefault(str(entry.get("program")).upper(), case)
    estates = {}
    for name, rep in sorted(reports.items()):
        r = Counter()
        for p in rep["programs"]:
            m = p.get("mutation") or {}
            if m.get("score") is None:
                continue
            r["measured"] += 1
            r["ready"] += bool(m.get("l5")) and not m.get("current")
            r["caught"] += m.get("killed") or 0
            r["survived"] += m.get("survived") or 0
            case = by_program.get(Path(p["program"]).stem.upper())
            if case:
                r["sampled"] += ledger[case].get("chosen") or 0
                r["mutants"] += ledger[case].get("mutants") or 0
                for c in claims.get(case, []):
                    r[c["verdict"]] += 1
        estates[name] = {
            "programs": len(rep["programs"]),
            "measured": r["measured"],
            "l5": sum(1 for p in rep["programs"] if p["level"] == "L5"),
            "ready": r["ready"],
            "caught": r["caught"],
            "survived": r["survived"],
            "raw_pct": pct(r["caught"], r["caught"] + r["survived"]),
            "sampled": r["sampled"],
            "mutants": r["mutants"],
            "sampled_pct": pct(r["sampled"], r["mutants"]),
            "equivalent": r["equivalent"],
            "unreachable": r["unreachable"],
        }
    keys = (
        "programs",
        "measured",
        "l5",
        "ready",
        "caught",
        "survived",
        "sampled",
        "mutants",
        "equivalent",
        "unreachable",
    )
    total: dict[str, Any] = {k: sum(e[k] for e in estates.values()) for k in keys}
    total["raw_pct"] = pct(total["caught"], total["caught"] + total["survived"])
    total["sampled_pct"] = pct(total["sampled"], total["mutants"])
    return {"estates": estates, "total": total}


def crucibles_component(cics: dict[str, Any], estate: dict[str, Any]) -> dict[str, Any]:
    progs = cics["programs"]
    horrors = estate.get("horrors") or {}
    return {
        "cics_crucible": {
            "ref": cics.get("crucible_ref"),
            "programs": len(progs),
            "scenarios": sum(len(v.get("scenarios") or {}) for v in progs.values()),
        },
        "estate_crucible": {
            "ref": estate.get("pinned_ref"),
            "horrors": len(horrors),
            "pass": sum(1 for v in horrors.values() if v == "PASS"),
        },
    }


# ---- 4/5. issues ----------------------------------------------------------------------------------------------------


def _day(ts: str | None) -> datetime | None:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None


def eta(open_n: int, net_per_day: float) -> str:
    """Open / net closure rate; never a date the numbers cannot support."""
    if open_n == 0:
        return "none open"
    if net_per_day <= 0:
        return NOT_CONVERGING
    return f"{open_n / net_per_day:.0f} days"


def issues_component(cache: dict[str, Any] | None) -> dict[str, Any]:
    if not cache:
        return {"measured": False, "note": "not measured: no issues cache and no GITHUB_TOKEN"}
    end = _day(cache["fetched_at"])
    assert end is not None
    start = end - timedelta(days=WINDOW_DAYS)
    issues = [i for i in cache["issues"] if "pull_request" not in i]

    def scoped(scope: str) -> list[dict[str, Any]]:
        return [i for i in issues if f"scope:{scope}" in i["labels"]]

    def window(group: list[dict[str, Any]]) -> tuple[int, int]:
        opened = sum(1 for i in group if (d := _day(i["created_at"])) and start < d <= end)
        closed = sum(1 for i in group if (d := _day(i.get("closed_at"))) and start < d <= end)
        return opened, closed

    def counts(group: list[dict[str, Any]]) -> dict[str, int]:
        o = sum(1 for i in group if i["state"] == "open")
        return {"open": o, "closed": len(group) - o, "total": len(group)}

    core = scoped("core")
    opened, closed = window(core)
    net = closed - opened
    rate = net / WINDOW_DAYS
    core_open = counts(core)["open"]
    m28 = [i for i in core if i.get("milestone") == CORE_MILESTONE]
    frontier = scoped("frontier")
    f_opened, _ = window(frontier)
    extra = _slide_inputs(cache)
    return {
        **extra,
        "measured": True,
        "as_of": cache["fetched_at"],
        "window_days": WINDOW_DAYS,
        "core": counts(core),
        "core_milestone": {"number": CORE_MILESTONE, **counts(m28)},
        "core_last_window": {"opened": opened, "closed": closed, "net_closed": net},
        "eta": eta(core_open, rate),
        "frontier": {**counts(frontier), "found_last_window": f_opened},
        "frontier_milestone": {
            "number": FRONTIER_MILESTONE,
            **counts([i for i in issues if i.get("milestone") == FRONTIER_MILESTONE]),
        },
        "sweep": counts(scoped("sweep")),
        "infra": counts(scoped("infra")),
    }


def _slide_inputs(cache: dict[str, Any]) -> dict[str, Any]:
    """The status slide's GitHub inputs (#5286): milestones, title-search counts and the Open World epic states. Each
    key is added only when the cache carries it, so an older cache still loads and the slide says "not measured"."""
    out: dict[str, Any] = {}
    if cache.get("milestones"):
        out["milestones"] = [
            {
                "number": m["number"],
                "title": m["title"],
                "open": m["open_issues"],
                "closed": m["closed_issues"],
                "total": m["open_issues"] + m["closed_issues"],
            }
            for m in sorted(cache["milestones"], key=lambda m: m["number"])
        ]
    if cache.get("title_counts"):
        out["title_counts"] = {k: dict(v) for k, v in sorted(cache["title_counts"].items())}
    if cache.get("epics"):
        out["epics"] = {str(k): v for k, v in sorted(cache["epics"].items(), key=lambda kv: int(kv[0]))}
    return out


def _api(path: str, token: str) -> Any:
    req = urllib.request.Request(  # noqa: S310 -- a fixed https URL
        f"https://api.github.com/{path}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
        return json.load(resp)


def fetch_issues(token: str | None = None) -> dict[str, Any]:
    """Every issue (no PRs) carrying a scope label, from the GitHub REST API (stdlib only)."""
    token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is not set")
    seen: dict[int, dict[str, Any]] = {}
    for scope in SCOPES:
        for page in range(1, 41):
            batch = _api(f"repos/{REPO_SLUG}/issues?labels=scope:{scope}&state=all&per_page=100&page={page}", token)
            for i in batch:
                if "pull_request" in i:
                    continue
                seen[i["number"]] = {
                    "number": i["number"],
                    "state": i["state"],
                    "created_at": i["created_at"],
                    "closed_at": i.get("closed_at"),
                    "labels": sorted(label["name"] for label in i["labels"]),
                    "milestone": (i.get("milestone") or {}).get("number"),
                }
            if len(batch) < 100:
                break
    milestones = [
        {
            "number": m["number"],
            "title": m["title"],
            "open_issues": m["open_issues"],
            "closed_issues": m["closed_issues"],
        }
        for m in _api(f"repos/{REPO_SLUG}/milestones?state=all&per_page=100", token)
    ]
    title_counts = {}
    for term in TITLE_TERMS:
        tot = _api(f"search/issues?q=repo:{REPO_SLUG}+is:issue+{term}+in:title&per_page=1", token)["total_count"]
        closed = _api(f"search/issues?q=repo:{REPO_SLUG}+is:issue+is:closed+{term}+in:title&per_page=1", token)[
            "total_count"
        ]
        title_counts[term.lower()] = {"total": tot, "closed": closed}
    epics = {n: _api(f"repos/{REPO_SLUG}/issues/{n}", token)["state"] for n in OPEN_WORLD_EPICS}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "fetched_at": now,
        "issues": [seen[k] for k in sorted(seen)],
        "milestones": milestones,
        "title_counts": title_counts,
        "epics": epics,
    }


def load_issues() -> dict[str, Any] | None:
    """The cache named by PROGRESS_ISSUES_CACHE (or the default), else a live fetch when a token is set, else None."""
    path = Path(os.environ.get(CACHE_ENV) or ISSUES_CACHE)
    if path.is_file():
        return _load(path)
    if os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"):
        try:
            return fetch_issues()
        except Exception as e:  # noqa: BLE001 -- a failed fetch leaves the section "not measured", not the page broken
            print(f"progress_report: issues not fetched: {type(e).__name__}: {e}", file=sys.stderr)
    return None


# ---- build ----------------------------------------------------------------------------------------------------------


def head_commit() -> str:
    res = subprocess.run(
        ["git", "rev-parse", "--short=9", "HEAD"], cwd=REPO, capture_output=True, text=True, check=False
    )  # noqa: S603, S607
    return res.stdout.strip() or "unknown"


def burned_estates_ok(estates: list[str]) -> list[str]:
    """The estate reports must be the burned estates' (estate4_draw.BURNED_NAMES); returns the ones that are not."""
    import estate4_draw

    return [e for e in estates if e.lower() not in estate4_draw.BURNED_NAMES]


def build(
    reports: dict[str, dict[str, Any]],
    inventories: dict[str, dict[str, Any]],
    spec_data: dict[str, Any],
    spec_rows: list[dict[str, Any]],
    rules: dict[str, Any],
    mutation: dict[str, Any],
    cics_crucible: dict[str, Any],
    estate_crucible: dict[str, Any],
    issues: dict[str, Any] | None,
    commit: str,
    test_estates: dict[str, dict[str, Any]] | None = None,
    ledger: dict[str, dict[str, Any]] | None = None,
    claims: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    per, pairs = {}, {}
    for name in sorted(reports):
        progs = reports[name]["programs"]
        per[name] = ladder(progs)
        eras = ((inventories.get(name) or {}).get("eras") or {}).get("programs") or {}
        pairs[name] = [
            (
                str(eras[p["program"]]["era"]) if eras.get(p["program"], {}).get("era") is not None else "none",
                p["level"],
            )
            for p in progs
        ]
    total = sum_ladders(list(per.values()))
    unreachable = ladder_exclusions.summarize({n: reports[n]["programs"] for n in reports})
    if unreachable:  # added only when non-empty; every program stays in the fixed denominator
        total["unreachable"] = unreachable
        total["reachable"] = total["programs"] - unreachable["count"]
    cics = cics_component(spec_data.get("census") or {}, spec_rows)
    return {
        "format": FORMAT,
        "commit": commit,
        "sources": SOURCES,
        "oracle": "GnuCOBOL plus IBM documentation, not z/OS",
        "ladder": {
            "estates": per,
            "total": total,
            "test_estates": {n: ladder(r["programs"]) for n, r in sorted((test_estates or {}).items())},
        },
        "components": {
            "translator": {"whole": total["translated_whole"], "of": total["programs"]},
            "cics": cics,
            "cobolrt_rules": rules_component(rules),
            "mutation": mutation_component(mutation),
            "det_mutation": det_mutation_component(reports, ledger or {}, claims or {}),
            "capabilities": capability_ledger.build(rules, cics),
            "crucibles": crucibles_component(cics_crucible, estate_crucible),
        },
        "eras": era_table(pairs),
        "issues": issues_component(issues),
    }


@functools.cache
def _issues_once() -> dict[str, Any] | None:
    return load_issues()


def gather() -> dict[str, Any]:
    """The report from the committed artifacts (the estate reports are materialized from `generated` on demand)."""
    import cics_spec_status
    import det_mutation
    import readiness_report

    names = readiness_report.estates()
    bad = burned_estates_ok(names)
    if bad:
        raise RuntimeError(f"evidence reports for estates that are not burned: {bad}")
    reports = {n: readiness_report._load(readiness_report._reports() / n / "report.json") for n in names}
    inv = {n: readiness_report._load(readiness_report.INVENTORY / f"{n}.json") for n in names}
    data = cics_spec_status.load_data()
    tests = {
        n: readiness_report._load(f)
        for n in TEST_ESTATES
        if (f := readiness_report._reports() / n / "report.json").is_file()
    }
    return build(
        reports,
        inv,
        data,
        cics_spec_status.rows(data),
        _load(RULES),
        _load(MUTATION),
        _load(CICS_CRUCIBLE),
        _load(ESTATE_CRUCIBLE),
        _issues_once(),
        head_commit(),
        tests,
        det_mutation.load(),
        det_mutation.load_survivors(),
    )


# ---- render ---------------------------------------------------------------------------------------------------------


def _test_estate_lines(estates: dict[str, dict[str, Any]]) -> list[str]:
    """The test estates' levels, apart from the ladder: built to be hard, so never in its fixed denominator."""
    if not estates:
        return []
    out = ["Test estates, written to break the translator and so never in the denominator above:", ""]
    out += ["| Test estate | Programs | L0 | L1 | L2 | L3 | L4 | L5 |", "|---|---|---|---|---|---|---|---|"]
    for name, r in estates.items():
        out.append(f"| `{name}` | {r['programs']} | " + " | ".join(str(r["levels"][x]) for x in LEVELS) + " |")
    return [*out, ""]


def _det_mutation_lines(dm: dict[str, Any]) -> list[str]:
    def line(name: str, r: dict[str, Any]) -> str:
        raw = f"{r['raw_pct']}% ({r['caught']} of {r['caught'] + r['survived']})" if r["measured"] else "not measured"
        sample = f"{r['sampled_pct']}% ({r['sampled']} of {r['mutants']})" if r["mutants"] else "not measured"
        return (
            f"| {name} | {r['programs']} | {r['measured']} | {r['l5']} | {r['ready']} | {raw} | {sample} "
            f"| {r['equivalent']} | {r['unreachable']} |"
        )

    return [*(line(f"`{n}`", r) for n, r in dm["estates"].items()), line("**Total**", dm["total"])]


def _capability_lines(cap: dict[str, Any]) -> list[str]:
    out = []
    for r in cap["rows"]:
        count = f"{r['done']} of {r['of']} {r['unit']}" if r["of"] else "no denominator"
        note = f" ({r['note']})" if r["note"] else ""
        label = capability_ledger.STATE_LABEL[r["state"]]
        out.append(f"| {r['group']} | {r['name']} | {label} | {count} | {r['have']}{note} |")
    return out


def render(rep: dict[str, Any]) -> str:
    lad, comp = rep["ladder"], rep["components"]
    t = lad["total"]
    out = [
        "# Progress",
        "",
        f"Generated from main at `{rep['commit']}` by `tests/tools/progress_report.py` (#5280); do not edit. Every",
        "denominator is fixed and every number names its source below. A level is an evidence level, never a bare",
        f"claim of correctness: the oracle is {rep['oracle']}.",
        "",
        "## 1. Burned-estate ladder",
        "",
        f"Fixed denominator: the {t['programs']} programs of the {len(lad['estates'])} burned estates. "
        f"Source: {rep['sources']['ladder']}.",
        "",
        "| Estate | Programs | L0 | L1 | L2 | L3 | L4 | L5 | L2+ | L4+ | L5 |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    if "reachable" in t:
        u = t["unreachable"]
        parts = " - ".join(str(u["kinds"][k]["count"]) for k in u["kinds"])
        out[-2:-2] = [
            f"Reachable denominator: {t['reachable']} programs ({t['programs']} - {parts}). These programs stay in "
            "the fixed denominator and in the table; each is reported apart because its blocker is not a translator gap.",
            "",
            "| Not reachable for a non-translator reason | Programs | Issue | Reason |",
            "|---|---|---|---|",
            *(
                f"| {ladder_exclusions.KIND_LABEL[k]} | {v['count']}: "
                + ", ".join(f"`{n}`" for n in v["programs"])
                + f" | {', '.join(v['issues'])} | {'; '.join(v['reasons'])} |"
                for k, v in u["kinds"].items()
            ),
            *(
                ["", f"Entries that no longer hold (the program is above L0): {', '.join(u['stale'])}."]
                if u.get("stale")
                else []
            ),
            "",
        ]
    rows = [*lad["estates"].items(), ("Total", t)]
    for name, r in rows:
        lv = r["levels"]
        label = f"**{name}**" if name == "Total" else f"`{name}`"
        out.append(
            f"| {label} | {r['programs']} | " + " | ".join(str(lv[x]) for x in LEVELS)
            + f" | {r['l2_plus']} ({pct_text(r['l2_plus'], r['programs'])})"
            + f" | {r['l4_plus']} ({pct_text(r['l4_plus'], r['programs'])}) | {r['l5']} |"
        )  # fmt: skip
    c = comp["cics"]
    ru = comp["cobolrt_rules"]
    mu = comp["mutation"]
    cc = comp["crucibles"]
    st = ru["status"]
    out += [
        "",
        "L0 inventoried, L1 translated whole, L2 executed equal, L3 every paragraph, L4 every net branch, L5 every",
        "surviving translator mutant accounted for (`definition_of_done.md`).",
        "",
        *_test_estate_lines(lad["test_estates"]),
        "## L5: what it rests on",
        "",
        "L5 has no score bar: it needs every surviving mutant of the det port's sample accounted for, on current inputs.",
        "*Ready* passes on its last measurement and waits for a refresh, so it is not L5. *Raw* is mutants caught of those",
        "judged; *sample* is mutants judged of those the program has. Claims are the reviewed survivor statements.",
        "",
        "| Estate | Programs | Measured | L5 | Ready | Raw caught | Sample | Equivalent | Unreachable |",
        "|---|---|---|---|---|---|---|---|---|",
        *_det_mutation_lines(comp["det_mutation"]),
        "",
        "## Capability ledger",
        "",
        "Counted from the code by `capability_ledger.py`. A blank denominator means no honest list exists to count against.",
        "*Match* means IBM's documentation.",
        "",
        "| Group | Capability | State | Count | What exists |",
        "|---|---|---|---|---|",
        *_capability_lines(comp["capabilities"]),
        "",
        f"z/OS: {comp['capabilities']['zos']['measured']} of {comp['capabilities']['zos']['of']} rules measured; "
        f"{comp['capabilities']['zos']['probes']} probes written, none run. Register of named limits: "
        f"{comp['capabilities']['register']['entries']} entries, {comp['capabilities']['register']['refused']} refuse by name.",
        "",
        "## 2. Components",
        "",
        "| Component | Measure | Denominator | Source |",
        "|---|---|---|---|",
        f"| Translator | {comp['translator']['whole']} programs translated whole | {comp['translator']['of']} burned programs | {rep['sources']['ladder']} |",
        f"| CICS commands | {c['modelled_both_runtimes']} modelled on both runtimes | {c['burned_commands']} commands a burned program uses ({c['unlisted_or_unparsed']} unlisted or unparsed forms, counted as not modelled) | {rep['sources']['cics']} |",
        f"| COBOL runtime rules | {st['MATCHED']} MATCHED, {st['DIFFERS']} DIFFERS, {st['ASSUMED']} ASSUMED, {st['REFUSED']} REFUSED; {ru['measured_on_zos']} measured on z/OS | {ru['rules']} rules | {rep['sources']['rules']} |",
        f"| Mutation, hand ports (not the translator) | {mu['killed']} killed = {pct_text(mu['killed'], mu['adjusted_total'])} adjusted ({pct_text(mu['killed'], mu['raw_total'])} raw) | {mu['adjusted_total']} adjusted, {mu['raw_total']} raw mutants over {mu['ports']} ports | {rep['sources']['mutation']} |",
        f"| CICS crucible | {cc['cics_crucible']['programs']} programs, {cc['cics_crucible']['scenarios']} scenarios | pinned at `{cc['cics_crucible']['ref']}` | tests/cics_crucible/coverage.json |",
        f"| Estate crucible | {cc['estate_crucible']['pass']} of {cc['estate_crucible']['horrors']} horrors pass | pinned at `{cc['estate_crucible']['ref']}` | tests/estate_crucible/baseline.json |",
        "",
        f"CICS commands not modelled on both runtimes: {', '.join(f'`{k}`' for k in c['not_modelled_commands']) or 'none'}.",
        "",
        "Frontier context, not the denominator above: the whole CICS spec has "
        f"{c['spec']['entries']} entries, {c['spec']['full']} full, {c['spec']['engine_only']} engine-only and "
        f"{c['spec']['name_only']} refused by name.",
        "",
        "## 3. Eras",
        "",
        f"Source: {rep['sources']['eras']}. Programs per era, with how many are at L2+ and L4+.",
        "",
        "| Era | Programs | L2+ | L4+ |",
        "|---|---|---|---|",
    ]
    for e in ERAS:
        r = rep["eras"][e]
        out.append(f"| {'untagged' if e == 'none' else e} | {r['programs']} | {r['l2_plus']} | {r['l4_plus']} |")
    out += ["", "## 4. Core burn-down", ""]
    i = rep["issues"]
    if not i["measured"]:
        out += [i["note"] + ".", "", "## 5. Gap Atlas", "", i["note"] + "."]
    else:
        cm, w = i["core_milestone"], i["core_last_window"]
        out += [
            f"Source: {rep['sources']['issues']}, as of {i['as_of']}.",
            "",
            f"- `scope:core`: {i['core']['open']} open, {i['core']['closed']} closed.",
            f"- Milestone {cm['number']}: {cm['open']} open, {cm['closed']} closed.",
            f"- Last {i['window_days']} days: {w['opened']} opened, {w['closed']} closed, net {w['net_closed']:+d} closed.",
            f"- ETA (open / net closure rate): **{i['eta']}**.",
            "",
            "## 5. Gap Atlas",
            "",
            "Frontier issues are discoveries, not debt: the sweeps keep finding siblings, and each one is a new entry.",
            "",
            f"- `scope:frontier`: {i['frontier']['found_last_window']} found in the last {i['window_days']} days, "
            f"{i['frontier']['total']} in total ({i['frontier']['open']} open, {i['frontier']['closed']} closed).",
            f"- Milestone {i['frontier_milestone']['number']} (Gap Atlas): {i['frontier_milestone']['total']} issues.",
            f"- `scope:sweep`: {i['sweep']['open']} open, {i['sweep']['closed']} closed.",
            f"- `scope:infra`: {i['infra']['open']} open, {i['infra']['closed']} closed.",
        ]
    return "\n".join(out) + "\n"


def render_json(rep: dict[str, Any]) -> str:
    return json.dumps(rep, indent=1, sort_keys=True) + "\n"


def render_page() -> str:
    return render(gather())


def render_json_page() -> str:
    return render_json(gather())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", nargs="?", choices=["render", "fetch"], default="render")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--cache", type=Path, default=ISSUES_CACHE)
    args = ap.parse_args(argv)
    if args.cmd == "fetch":
        args.cache.write_text(json.dumps(fetch_issues(), indent=1) + "\n", encoding="utf-8")
        print(f"wrote {args.cache}")
        return 0
    rep = gather()
    text = render_json(rep) if args.json else render(rep)
    if args.out:
        args.out.write_text(text, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
