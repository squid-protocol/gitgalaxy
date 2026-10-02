#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""
Archetype drift harness (#4100): how far has the engine moved the archetype
labels since the brains were trained?

The brains are retrained offline (gitgalaxy-population-analyses) far less often
than the engine changes, so drift is expected. This tool measures it instead of
letting it accumulate unseen behind golden-master re-blesses:

* ``tests/archetype_trained_baseline.json`` -- every crucible code file's
  function/file/composition labels as the engine the brains were trained
  against assigned them. It moves only on ``rebaseline`` (after a retrain).
* ``gitgalaxy/standards/archetype_brains/archetype_validation.json`` -- the
  shipped record: when the brains were trained, per-level agreement with that
  baseline, the eroding archetypes, the open retrain issue, and a short history.
  ``archetype_parity.validation_status`` turns it into per-level states.

Subcommands::

    measure  --audit <data_galaxy_audit.json> [--write-record] [--summary-md F]
             [--github-output F] [--engine-commit C] [--corpus X]
    issue-body --out F                 # retrain-issue markdown from the record
    set-issue  <N|none>                # record the open retrain issue
    rebaseline --audit <audit> --engine-version V --engine-commit C --trained-at D --corpus X

``measure --write-record`` only rewrites the record when something moved (a
state change, or any agreement shifting by >= RECORD_EPSILON), so a push that
relabels nothing opens no PR. Agreement is stability with respect to the
trained state, not accuracy.

The audit is a ``galaxyscope`` run over language-crucible/data with the
golden-master flags (``GITGALAXY_DISABLE_GIT_HISTORY=1``, ``--file-speed
--splicing-speed``); a golden-master fixture directory works too.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_HERE.parent))  # tests/ -- golden_store (no tests/__init__.py)
import golden_store  # noqa: E402

from gitgalaxy.metrics import archetype_classifier as ac  # noqa: E402
from gitgalaxy.metrics import archetype_parity as ap  # noqa: E402

BASELINE_PATH = REPO_ROOT / "tests" / "archetype_trained_baseline.json"
RECORD_PATH = REPO_ROOT / "gitgalaxy" / "standards" / "archetype_brains" / "archetype_validation.json"

PARSED = "6. Parsed Files (Scanned Artifacts)"
GLOBAL = "2. Global Ecosystem Summary"
REPO_KEY = "Repository Composition Archetype"
# Below this many baseline files an archetype's retention is noise, not erosion.
EROSION_MIN_FILES = 20
# Agreement moves smaller than this do not rewrite the record (no PR churn).
RECORD_EPSILON = 0.0025
HISTORY_CAP = 60


# ------------------------------------------------------------------ extraction
def extract(audit: dict[str, Any]) -> dict[str, Any]:
    """Code files' archetype labels from an audit. The general file archetype is
    reported under the legacy key "Repository Archetype"."""
    files: dict[str, Any] = {}
    for group in (audit.get(PARSED) or {}).values():
        for path, f in (group.get("Files") or {}).items():
            prof = f.get("3. Architectural Profile") or {}
            if not (prof.get("Coding LOC") or 0) > 0:
                continue
            files[path] = {
                "file": prof.get("Repository Archetype"),
                "composition": prof.get("Composition Archetype"),
                "composition_z": prof.get("Composition Fit (Z-Score)") or 0.0,
                "functions": dict(sorted((prof.get("Function Archetype Mix") or {}).items())),
            }
    return {"repo": (audit.get(GLOBAL) or {}).get(REPO_KEY), "files": files}


def load_audit(path: str | Path) -> dict[str, Any]:
    return extract(golden_store.load(str(path)))


# ------------------------------------------------------------------ measurement
def _label_level(base: dict, cur: dict, common: list[str], key: str, threshold: float) -> dict[str, Any]:
    if not common:
        return {"agreement": None, "files_compared": 0}
    same = sum(1 for p in common if base[p][key] == cur[p][key])
    by_label: dict[str, list[str]] = {}
    for p in common:
        by_label.setdefault(base[p][key], []).append(p)
    eroding = {}
    for label, paths in sorted(by_label.items()):
        if len(paths) < EROSION_MIN_FILES:
            continue
        kept = sum(1 for p in paths if cur[p][key] == label)
        if kept / len(paths) < threshold:
            dest: dict[str, int] = {}
            for p in paths:
                if cur[p][key] != label:
                    dest[cur[p][key]] = dest.get(cur[p][key], 0) + 1
            eroding[label] = {
                "retained": round(kept / len(paths), 4),
                "files": len(paths),
                "mostly_to": max(dest, key=lambda k: dest[k]) if dest else None,
            }
    return {"agreement": round(same / len(common), 4), "files_compared": len(common), "eroding": eroding}


def _function_level(base: dict, cur: dict, common: list[str], threshold: float) -> dict[str, Any]:
    moved = total = 0.0
    kept_by: dict[str, float] = {}
    base_by: dict[str, float] = {}
    for p in common:
        a, b = base[p]["functions"], cur[p]["functions"]
        l1 = sum(abs(a.get(k, 0) - b.get(k, 0)) for k in set(a) | set(b))
        # Functions that changed label; a pure count change (a function gained or
        # lost by extraction) is not a relabel.
        moved += (l1 - abs(sum(a.values()) - sum(b.values()))) / 2
        total += sum(a.values())
        for k, n in a.items():
            base_by[k] = base_by.get(k, 0) + n
            kept_by[k] = kept_by.get(k, 0) + min(n, b.get(k, 0))
    if not total:
        return {"agreement": None, "functions_compared": 0}
    eroding = {
        k: {"retained": round(kept_by[k] / n, 4), "functions": int(n)}
        for k, n in sorted(base_by.items())
        if n >= EROSION_MIN_FILES and kept_by[k] / n < threshold
    }
    return {"agreement": round(1 - moved / total, 4), "functions_compared": int(total), "eroding": eroding}


def measure(baseline: dict[str, Any], current: dict[str, Any], thresholds: dict[str, float]) -> dict[str, Any]:
    """Per-level agreement of ``current`` with the trained-state ``baseline``."""
    base, cur = baseline["files"], current["files"]
    common = sorted(set(base) & set(cur))
    thr = thresholds["validated"]
    comp = _label_level(base, cur, common, "composition", thr)
    code = [
        p
        for p in common
        if base[p]["composition"] not in ac.NONCODE_FILE_ARCHETYPES
        and cur[p]["composition"] not in ac.NONCODE_FILE_ARCHETYPES
    ]
    if code:
        comp["fit_shift"] = round(
            sum(cur[p]["composition_z"] for p in code) / len(code)
            - sum(base[p]["composition_z"] for p in code) / len(code),
            3,
        )
    return {
        "coverage": round(len(common) / len(base), 4) if base else 0.0,
        "levels": {
            "function": _function_level(base, cur, common, thr),
            "file": _label_level(base, cur, common, "file", thr),
            "composition_file": comp,
            # One corpus is one repo: no measurable agreement of its own.
            "composition_repo": {
                "inherits": "composition_file",
                "crucible_label": {"trained": baseline.get("repo"), "current": current.get("repo")},
            },
        },
    }


# ------------------------------------------------------------------ record
def load_record() -> dict[str, Any]:
    return json.loads(RECORD_PATH.read_text(encoding="utf-8")) if RECORD_PATH.exists() else {}


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_baseline(data: dict[str, Any]) -> None:
    """One line per file: compact, and a re-anchor diffs file by file."""
    head = {k: v for k, v in data.items() if k != "files"}
    rows = [
        f"    {json.dumps(p)}: {json.dumps(v, sort_keys=True, separators=(',', ':'))}"
        for p, v in sorted(data["files"].items())
    ]
    body = json.dumps(head, sort_keys=True)[:-1] + ', "files": {\n' + ",\n".join(rows) + "\n}}\n"
    BASELINE_PATH.write_text(body, encoding="utf-8")


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def status_for(record: dict[str, Any]) -> dict[str, Any]:
    return ap.validation_status(ac.loaded_brains(), record)


def record_moved(old: dict[str, Any], new: dict[str, Any]) -> bool:
    """Does ``new`` differ from ``old`` enough to be worth a commit?"""
    if not old.get("measured"):
        return True
    so, sn = status_for(old)["levels"], status_for(new)["levels"]
    for lvl in ap.LEVELS:
        if so[lvl]["state"] != sn[lvl]["state"]:
            return True
        a, b = so[lvl]["agreement"], sn[lvl]["agreement"]
        if (a is None) != (b is None) or (a is not None and abs(a - b) >= RECORD_EPSILON):
            return True
        if set(so[lvl]["eroding"]) != set(sn[lvl]["eroding"]):
            return True
    return False


def updated_record(record: dict[str, Any], result: dict[str, Any], engine_commit: str, corpus: str) -> dict[str, Any]:
    new = json.loads(json.dumps(record))
    new["levels"] = result["levels"]
    new["measured"] = {
        "engine_commit": engine_commit,
        "measured_at": _dt.datetime.now(tz=_dt.timezone.utc).date().isoformat(),
        "corpus": corpus,
        "coverage": result["coverage"],
    }
    status = status_for(new)
    new.setdefault("history", []).append(
        {
            "date": new["measured"]["measured_at"],
            "engine_commit": engine_commit,
            "agreement": {lvl: status["levels"][lvl]["agreement"] for lvl in ap.LEVELS},
            "state": {lvl: status["levels"][lvl]["state"] for lvl in ap.LEVELS},
        }
    )
    new["history"] = new["history"][-HISTORY_CAP:]
    return new


# ------------------------------------------------------------------ rendering
def render_status(status: dict[str, Any], *, title: str = "Archetype validation") -> str:
    lines = [f"### {title}", "", ap.trained_line(status), ""]
    lines += ["| Level | State | Agreement | Why |", "|---|---|---|---|"]
    for lvl in ap.LEVELS:
        v = status["levels"][lvl]
        agr = f"{v['agreement']:.1%}" if v["agreement"] is not None else "--"
        why = "; ".join(v["reasons"] + [f"note: {n}" for n in v["notes"]]) or "--"
        lines.append(f"| {lvl} | {v['state']}{' (withheld)' if v['withheld'] else ''} | {agr} | {why} |")
    eroding = [(lvl, k, e) for lvl in ap.LEVELS for k, e in status["levels"][lvl]["eroding"].items()]
    if eroding:
        lines += ["", "**Eroding archetypes** (share of trained-state members still assigned):", ""]
        for lvl, k, e in eroding:
            dest = f", mostly to {e['mostly_to']!r}" if e.get("mostly_to") else ""
            lines.append(f"- {lvl} `{k}`: {e['retained']:.1%} retained{dest}")
    lines += ["", "_Agreement = share of crucible code files labelled as at training; stability, not accuracy._"]
    return "\n".join(lines)


def render_pr_delta(recorded: dict[str, Any], result: dict[str, Any]) -> str:
    """Markdown for a PR: this branch's agreement vs the one recorded on main."""
    before = status_for(recorded)
    after = status_for(updated_record(recorded, result, "this PR", (recorded.get("measured") or {}).get("corpus", "")))
    lines = ["### Archetype drift from this change (#4100, report-only)", ""]
    lines += ["| Level | Recorded on main | This PR | Δ |", "|---|---|---|---|"]
    for lvl in ap.LEVELS:
        a, b = before["levels"][lvl], after["levels"][lvl]
        fa = f"{a['agreement']:.1%}" if a["agreement"] is not None else "--"
        fb = f"{b['agreement']:.1%}" if b["agreement"] is not None else "--"
        d = (
            f"{(b['agreement'] - a['agreement']) * 100:+.2f} pp"
            if a["agreement"] is not None and b["agreement"] is not None
            else "--"
        )
        state = a["state"] if a["state"] == b["state"] else f"{a['state']} → **{b['state']}**"
        lines.append(f"| {lvl} | {fa} | {fb} | {d} ({state}) |")
    lines += ["", "Never fails the build; the push-to-main run records it and opens a retrain issue if needed."]
    return "\n".join(lines)


def render_issue(status: dict[str, Any]) -> str:
    lines = [
        "The archetype brains have fallen out of step with the engine. Labels in DEGRADED levels are still "
        "emitted but qualified; INVALID levels are withheld (`Unvalidated`). This issue is opened, updated and "
        "closed by `archetype-validation.yml` (#4100) -- it closes itself once every level is back to "
        "VALIDATED or DRIFTING.",
        "",
        render_status(status, title="Current state"),
        "",
        "### Clearing it",
        "",
        "1. Retrain/refreeze the brains in gitgalaxy-population-analyses on a current fleet scan.",
        "2. Land them here with the paired engine review (`EXPECTED_CONTRACT_SHA` in "
        "`tests/core_engine/test_archetype_parity.py`) and a golden-master re-bless.",
        "3. Re-anchor the drift baseline on the engine the brains were trained against:",
        "   `python tests/tools/archetype_drift.py rebaseline --audit <crucible audit> --engine-version vX.Y.Z "
        "--engine-commit <sha> --trained-at <date> --corpus <corpus>`",
    ]
    hist = (load_record().get("history") or [])[-10:]
    if hist:
        lines += ["", "### Recent measurements", "", "| Date | Engine | " + " | ".join(ap.LEVELS) + " |"]
        lines.append("|---" * (2 + len(ap.LEVELS)) + "|")
        for h in hist:
            cells = [
                f"{h['agreement'][lvl]:.1%} {h['state'][lvl]}"
                if h["agreement"].get(lvl) is not None
                else h["state"][lvl]
                for lvl in ap.LEVELS
            ]
            lines.append(f"| {h['date']} | `{h['engine_commit']}` | " + " | ".join(cells) + " |")
    return "\n".join(lines)


# ------------------------------------------------------------------ commands
def cmd_measure(args: argparse.Namespace) -> int:
    record = load_record()
    if not BASELINE_PATH.exists():
        print(f"no trained-state baseline at {BASELINE_PATH}; run `rebaseline` first", file=sys.stderr)
        return 2
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    thresholds = {**ap.DEFAULT_THRESHOLDS, **(record.get("thresholds") or {})}
    result = measure(baseline, load_audit(args.audit), thresholds)
    if result["coverage"] < 0.5:
        print(
            f"only {result['coverage']:.0%} of the baseline's files are in this audit -- wrong corpus?", file=sys.stderr
        )
        return 2
    corpus = args.corpus or (record.get("measured") or {}).get("corpus") or "language-crucible"
    new = updated_record(record, result, args.engine_commit or _git("rev-parse", "--short", "HEAD"), corpus)
    status = status_for(new)
    report = render_status(status)
    print(report)
    if args.summary_md:
        with open(args.summary_md, "a", encoding="utf-8") as fh:
            fh.write(render_pr_delta(record, result) + "\n\n" + report + "\n")
    changed = record_moved(record, new)
    if args.write_record and changed:
        write_json(RECORD_PATH, new)
        print(f"\nrecord updated: {RECORD_PATH.relative_to(REPO_ROOT)}")
    elif args.write_record:
        print("\nnothing moved beyond the record epsilon; record left as is")
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as fh:
            fh.write(f"needs_retrain={'true' if ap.needs_retrain(status) else 'false'}\n")
            fh.write(f"record_changed={'true' if changed else 'false'}\n")
    return 0


def cmd_issue_body(args: argparse.Namespace) -> int:
    Path(args.out).write_text(render_issue(status_for(load_record())) + "\n", encoding="utf-8")
    return 0


def cmd_set_issue(args: argparse.Namespace) -> int:
    record = load_record()
    value = None if args.number.lower() == "none" else int(args.number.lstrip("#"))
    if record.get("retrain_issue") != value:
        record["retrain_issue"] = value
        write_json(RECORD_PATH, record)
    return 0


def cmd_rebaseline(args: argparse.Namespace) -> int:
    current = load_audit(args.audit)
    write_baseline(
        {
            "trained_against": {"engine_commit": args.engine_commit, "corpus": args.corpus},
            "repo": current["repo"],
            "files": current["files"],
        }
    )
    record = load_record()
    record["schema"] = 1
    record.setdefault("thresholds", dict(ap.DEFAULT_THRESHOLDS))
    record["trained"] = {
        "engine_version": args.engine_version,
        "engine_commit": args.engine_commit,
        "trained_at": args.trained_at,
        "corpus": args.corpus,
        "brain_fingerprints": {lvl: ap.brain_fingerprint(b) for lvl, b in ac.loaded_brains().items()},
    }
    for key in ("levels", "measured"):
        record.pop(key, None)
    record["history"] = []
    record.setdefault("retrain_issue", None)
    write_json(RECORD_PATH, record)
    print(f"baseline: {len(current['files'])} code files -> {BASELINE_PATH.relative_to(REPO_ROOT)}")
    print("now run `measure --write-record` against a current audit")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("measure", help="measure drift vs the trained-state baseline")
    m.add_argument("--audit", required=True)
    m.add_argument("--write-record", action="store_true")
    m.add_argument("--summary-md")
    m.add_argument("--github-output")
    m.add_argument("--engine-commit")
    m.add_argument("--corpus")
    m.set_defaults(func=cmd_measure)
    i = sub.add_parser("issue-body", help="render the retrain issue body")
    i.add_argument("--out", required=True)
    i.set_defaults(func=cmd_issue_body)
    s = sub.add_parser("set-issue", help="record the open retrain issue number (or 'none')")
    s.add_argument("number")
    s.set_defaults(func=cmd_set_issue)
    r = sub.add_parser("rebaseline", help="re-anchor on the engine the brains were trained against")
    for flag in ("--audit", "--engine-version", "--engine-commit", "--trained-at", "--corpus"):
        r.add_argument(flag, required=True)
    r.set_defaults(func=cmd_rebaseline)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
