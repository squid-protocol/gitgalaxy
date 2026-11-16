"""#4713 & #4716: Rule-usage evidence and exit-route simplification report for cobolrt.

Joins a RuleTelemetry snapshot ({rule_id: count}) with docs/language_status/cobolrt_rules.json to produce:
1. #4713 Evidence summary: exercised rules, status breakdown (MATCHED/DIFFERS/ASSUMED/REFUSED), and calibration.
2. #4716 Exit-route report: COBOL quirk rules that never fired (0 hits) -> safe plain-Java simplification candidates,
   vs quirk rules that did fire (> 0 hits) -> keep cobolrt semantics.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
RULES_PATH = REPO / "docs" / "language_status" / "cobolrt_rules.json"

QUIRK_SIMPLIFICATIONS: dict[str, dict[str, str]] = {
    "RT-NUM-TRUNC-BINARY": {
        "simplification": "Replace Cobol.store / Codec.write truncation with plain Java long/BigDecimal assignment.",
        "guard": "Add a unit test asserting no numeric field exceeds its PICTURE digit count.",
    },
    "RT-NUM-NONDIGIT-GET-SIGN": {
        "simplification": "Lift zoned numeric fields to plain Java long/BigDecimal without Zoned byte-level sign repair.",
        "guard": "Validate incoming record fields contain only ASCII/EBCDIC digits at boundary ingest.",
    },
    "RT-NUM-NONDIGIT-ARITHMETIC": {
        "simplification": "Use plain BigDecimal/long arithmetic instead of Zoned.operand non-digit emulation.",
        "guard": "Keep a boundary digit-validation test on arithmetic inputs.",
    },
    "RT-NUM-NONDIGIT-COMPARE": {
        "simplification": "Use plain BigDecimal.compareTo / Long.compare instead of Zoned.compareValue.",
        "guard": "Keep a boundary digit-validation test on compared fields.",
    },
    "RT-CBL-MOVE-NONDIGIT": {
        "simplification": "Replace Cobol.move on zoned items with typed Java field/DTO assignment.",
        "guard": "Verify no spaces/letters are moved into numeric receivers.",
    },
    "RT-NUM-ZONED-OVERPUNCH": {
        "simplification": "Use standard signed decimal parsing instead of EBCDIC/ASCII overpunch ({A-I/}J-R) decoding.",
        "guard": "Assert external inputs use standard +/- or unsigned digits.",
    },
    "RT-CBL-ZERO-DIVISOR-NAN": {
        "simplification": "Replace Cobol.divide NaN propagation with standard Java BigDecimal.divide + explicit zero check.",
        "guard": "Add a unit test confirming divisors are non-zero (or handled by ON SIZE ERROR).",
    },
    "RT-CBL-OSVS-INTERMEDIATE-ALIGN": {
        "simplification": "Drop Cobol.align intermediate truncation and use standard BigDecimal expression evaluation.",
        "guard": "Verify intermediate scales do not rely on OS/VS alignment truncation.",
    },
}


def load_catalogue(path: Path = RULES_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_report(counts: dict[str, int], catalogue: dict[str, Any] | None = None) -> dict[str, Any]:
    cat = catalogue if catalogue is not None else load_catalogue()
    rules_by_id = {r["id"]: r for r in cat.get("rules", [])}

    exercised: list[dict[str, Any]] = []
    by_status: dict[str, int] = {}
    by_calibration: dict[str, int] = {}
    assumed_ids: list[str] = []
    differs_ids: list[str] = []

    for rule_id in sorted(counts):
        hits = int(counts[rule_id])
        if hits <= 0:
            continue
        meta = rules_by_id.get(rule_id, {})
        status = meta.get("status", "UNKNOWN")
        cal = meta.get("calibration", "uncalibrated")
        cal_key = cal if isinstance(cal, str) else cal.get("status", "z/OS-measured")
        by_status[status] = by_status.get(status, 0) + 1
        by_calibration[cal_key] = by_calibration.get(cal_key, 0) + 1
        if status == "ASSUMED":
            assumed_ids.append(rule_id)
        elif status == "DIFFERS":
            differs_ids.append(rule_id)
        exercised.append({
            "id": rule_id,
            "hits": hits,
            "family": meta.get("family", ""),
            "title": meta.get("title", ""),
            "status": status,
            "calibration": cal,
            "ibm": meta.get("ibm"),
        })

    parts = [f"uses {len(exercised)} rules"]
    if by_status:
        status_bits = [f"{cnt} {st}" for st, cnt in sorted(by_status.items())]
        parts.append(", ".join(status_bits))
    if assumed_ids:
        parts.append(f"assumed: {', '.join(assumed_ids)}")
    if differs_ids:
        parts.append(f"differs: {', '.join(differs_ids)}")

    safe_to_simplify: list[dict[str, Any]] = []
    keep_runtime: list[dict[str, Any]] = []
    for rule_id, advice in QUIRK_SIMPLIFICATIONS.items():
        hits = int(counts.get(rule_id, 0))
        meta = rules_by_id.get(rule_id, {})
        entry = {
            "id": rule_id,
            "hits": hits,
            "title": meta.get("title", ""),
            **advice,
        }
        if hits == 0:
            safe_to_simplify.append(entry)
        else:
            keep_runtime.append(entry)

    return {
        "evidence": {
            "summary": "; ".join(parts),
            "total_rules_exercised": len(exercised),
            "by_status": by_status,
            "by_calibration": by_calibration,
            "rules": exercised,
        },
        "exit_route": {
            "safe_to_simplify": safe_to_simplify,
            "keep_runtime": keep_runtime,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    ev = report["evidence"]
    ex = report["exit_route"]
    lines = [
        "# cobolrt Rule Evidence & Exit-Route Report",
        "",
        f"**Evidence summary:** {ev['summary']}",
        "",
        "## Exercised Rules (#4713)",
        "",
        "| Rule ID | Hits | Status | Calibration | Title |",
        "|---|---:|---|---|---|",
    ]
    lines.extend(
        f"| `{r['id']}` | {r['hits']} | {r['status']} | {r['calibration']} | {r['title']} |"
        for r in ev["rules"]
    )

    lines += [
        "",
        "## Safe Plain-Java Simplifications (#4716 — 0 quirk hits)",
        "",
    ]
    if ex["safe_to_simplify"]:
        for item in ex["safe_to_simplify"]:
            lines.append(f"- **`{item['id']}`**: {item['simplification']} *(Guard: {item['guard']})*")
    else:
        lines.append("- None (every tracked quirk fired during this run).")

    lines += [
        "",
        "## Quirks That Fired (Keep cobolrt semantics)",
        "",
    ]
    if ex["keep_runtime"]:
        for item in ex["keep_runtime"]:
            lines.append(f"- **`{item['id']}`** ({item['hits']} hits): {item['title']}")
    else:
        lines.append("- None.")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Generate #4713 evidence and #4716 exit-route report from RuleTelemetry JSON")
    ap.add_argument("telemetry_json", type=Path, help="Path to JSON file produced by RuleTelemetry.toJson()")
    ap.add_argument("--format", choices=("json", "md"), default="md")
    args = ap.parse_args(argv)
    counts = json.loads(args.telemetry_json.read_text(encoding="utf-8"))
    report = build_report(counts)
    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
