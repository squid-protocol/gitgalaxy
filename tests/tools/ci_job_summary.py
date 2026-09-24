#!/usr/bin/env python3
"""
GitHub Actions Job Summary for a galaxyscope scan (#935).

GitHub's code-scanning tool-status page only shows per-language "files scanned"
coverage for integrated tools such as CodeQL; a third-party SARIF upload has no
field that can fill it. This writes the equivalent -- and more -- as a Job
Summary instead, from the `*_audit.json` the scan already produced. It adds no
analysis and runs no second scan; it only presents what the audit report holds.

USAGE
    python tests/tools/ci_job_summary.py gitgalaxy-results_audit.json \
        [--sbom gitgalaxy-results_sbom.json] [--top 5]

Appends to $GITHUB_STEP_SUMMARY when it is set, otherwise prints to stdout.

Stdlib only on purpose: gitgalaxy.yml installs gitgalaxy from PyPI, not from
this checkout, so this script must run beside whatever version that is. Every
section is optional -- a key the installed version does not emit drops that
section instead of failing the job.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

TRAIL = "1. Forensic Trail (Traceability)"
GLOBAL = "2. Global Ecosystem Summary"
SECURITY = "3. Forensic Security & Vulnerability Audit"
PARSED = "6. Parsed Files (Scanned Artifacts)"

_MAGNITUDE_NOTE = (
    "> Structural weight and centralization, the same ranking as the LLM brief's Ranked Artifacts. "
    "Magnitude is not a risk score; the blast radius says what a change would reach."
)


def _get(d: Any, *keys: str) -> Any:
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def _cell(value: Any) -> str:
    """One markdown table cell: no pipes or newlines from file paths/names."""
    return str(value).replace("|", "\\|").replace("\n", " ")


def _num(value: Any) -> str:
    return (
        f"{value:,}"
        if isinstance(value, int) and not isinstance(value, bool)
        else "-"
        if value is None
        else _cell(value)
    )


def _headline(audit: dict) -> list[str]:
    summary = _get(audit, GLOBAL, "summary") or {}
    context = _get(audit, TRAIL, "Analysis Context") or {}
    commit = _get(audit, TRAIL, "Source Control Footprint (Immutable Anchor)", "Commit Hash (SHA-1)")
    rows = [
        ("Files scanned", summary.get("verified_files")),
        ("Files in census", summary.get("total_files")),
        ("Total LOC", summary.get("total_loc")),
        ("Dominant language", summary.get("dominant_language")),
        ("Repository archetype", summary.get("repo_composition_archetype")),
        ("Scan duration", context.get("Total Scan Duration")),
        ("Commit", commit[:12] if isinstance(commit, str) else None),
    ]
    zero_dep = context.get("Zero-Dependency Mode Active")
    if zero_dep is not None:
        rows.append(("Precision mode", "Zero-Dependency" if zero_dep else "Full Precision"))
    rows = [(k, v) for k, v in rows if v not in (None, "")]
    if not rows:
        return []
    out = ["| | |", "|---|---|"]
    for k, v in rows:
        out.append(f"| {k} | {_num(v)} |")
    return [*out, ""]


def _languages(audit: dict) -> list[str]:
    comp = _get(audit, GLOBAL, "composition")
    if not isinstance(comp, dict) or not comp:
        return []
    rows = [(lang, s.get("files", 0) or 0, s.get("loc", 0) or 0) for lang, s in comp.items() if isinstance(s, dict)]
    if not rows:
        return []
    rows.sort(key=lambda r: (-r[2], -r[1], r[0]))
    total_loc = sum(r[2] for r in rows)
    out = [
        "### Languages",
        "",
        "| Language | Files | LOC | % of LOC |",
        "|---|--:|--:|--:|",
    ]
    for lang, files, loc in rows:
        pct = f"{100.0 * loc / total_loc:.1f}%" if total_loc else "-"
        out.append(f"| {_cell(lang)} | {files:,} | {loc:,} | {pct} |")
    return [*out, ""]


def _parsed_files(audit: dict) -> list[dict]:
    groups = _get(audit, PARSED)
    if not isinstance(groups, dict):
        return []
    files: list[dict] = []
    for group in groups.values():
        entries = _get(group, "Files")
        if isinstance(entries, dict):
            files.extend(f for f in entries.values() if isinstance(f, dict))
    return files


def _top_files(audit: dict, top: int) -> list[str]:
    ranked = []
    for f in _parsed_files(audit):
        magnitude = _get(f, "3. Architectural Profile", "Structural Magnitude")
        if not isinstance(magnitude, (int, float)):
            continue
        ranked.append((magnitude, f))
    if not ranked or top <= 0:
        return []
    ranked.sort(key=lambda r: (-r[0], str(_get(r[1], "1. Artifact Identity", "Path"))))
    out = [
        f"### Top {min(top, len(ranked))} files by structural magnitude",
        "",
        _MAGNITUDE_NOTE,
        "",
        "| File | Language | LOC | Magnitude | Imported by |",
        "|---|---|--:|--:|--:|",
    ]
    for magnitude, f in ranked[:top]:
        path = _get(f, "1. Artifact Identity", "Path") or "?"
        lang = _get(f, "1. Artifact Identity", "Language") or "?"
        loc = _get(f, "3. Architectural Profile", "Total LOC")
        blast = _get(f, "8. Dependency Network", "Direct Downstream (Dependency Blast Radius)")
        out.append(f"| `{_cell(path)}` | {_cell(lang)} | {_num(loc)} | {magnitude:,.1f} | {_num(blast)} |")
    return [*out, ""]


def _security(audit: dict, sbom: dict | None) -> list[str]:
    sec = _get(audit, SECURITY)
    lines = []
    if isinstance(sec, dict):
        status = sec.get("Audit Status")
        if status:
            lines.append(f"- **Audit status:** `{_cell(status)}`")
        infected = _get(sec, "ML Threat Intelligence (XGBoost)", "Infected Files Detected")
        if infected is not None:
            lines.append(f"- **ML threat model (XGBoost):** {infected} infected file(s) detected")
        secrets = sec.get("Exposed Secrets & Credentials (Quarantined Files)")
        if isinstance(secrets, list):
            lines.append(f"- **Quarantined files (exposed secrets):** {len(secrets)}")
        hits = sec.get("Raw Threat Signature Hits (Total Repository Occurrences)")
        if isinstance(hits, dict):
            nonzero = [(k, v) for k, v in hits.items() if not k.startswith("_") and isinstance(v, int) and v]
            if nonzero:
                listed = ", ".join(f"{_cell(k)}: {v}" for k, v in sorted(nonzero, key=lambda kv: -kv[1]))
                lines.append(f"- **Threat signature hits:** {listed}")
    if isinstance(sbom, dict) and isinstance(sbom.get("components"), list):
        lines.append(f"- **SBOM components:** {len(sbom['components'])}")
    if not lines:
        return []
    return ["### Security & supply chain", "", *lines, ""]


def render(audit: dict, sbom: dict | None = None, top: int = 5) -> str:
    root = _get(audit, TRAIL, "Analysis Context", "Target Root Name")
    title = f"## GitGalaxy scan: `{_cell(root)}`" if root else "## GitGalaxy scan"
    body = [*_headline(audit), *_languages(audit), *_top_files(audit, top), *_security(audit, sbom)]
    if not body:
        body = ["_The audit report had none of the sections this summary reads._", ""]
    return "\n".join([title, "", *body])


def _load(path: Path | None) -> dict | None:
    if path is None or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"ci_job_summary: could not read {path}: {exc}", file=sys.stderr)
        return None
    return data if isinstance(data, dict) else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("audit", type=Path, help="the scan's *_audit.json")
    ap.add_argument("--sbom", type=Path, help="the scan's *_sbom.json (optional)")
    ap.add_argument("--top", type=int, default=5, help="how many files to rank (default 5)")
    args = ap.parse_args(argv)

    audit = _load(args.audit)
    if audit is None:
        print(f"ci_job_summary: no readable audit report at {args.audit}; nothing to summarize", file=sys.stderr)
        return 1
    text = render(audit, _load(args.sbom), args.top)

    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if target:
        with open(target, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
    else:
        sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
