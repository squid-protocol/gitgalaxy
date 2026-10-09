"""estate_intake: the customer-facing confirmation list of one estate (#4709).

Reads tests/equivalence/estate_options/<corpus>.json and lists every value whose provenance is `assumed: ...`, with
the checklist section of docs/language_status/estate_intake.md that says what to send so the value is found, not
assumed. Also lists the copybooks the committed evidence report says are missing (`refused: missing copybook X`).
Deterministic, no network, no corpus needed.

    python tests/tools/estate_intake.py <corpus> [--options-dir DIR] [--report FILE]
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OPTIONS_DIR = ROOT / "tests" / "equivalence" / "estate_options"
REPORT_DIR = ROOT / "docs" / "language_status" / "evidence_report"
CHECKLIST = "docs/language_status/estate_intake.md"
MISSING = re.compile(r"missing copybook (\S+)")

# estate options path (first parts) -> (checklist section number, what to send)
SECTIONS: list[tuple[tuple[str, ...], str, str]] = [
    (("compiler", "installation_defaults"), "2", "the IGYCDOPT installation-defaults listing"),
    (("compiler",), "2", "the compiler STEPLIB / product and version"),
    (("parm",), "1", "the compile JCL, PARM and CBL / PROCESS cards"),
    (("le",), "3", "the CEEOPTS / CEEUOPT / CEEDOPT / CEEROPT members"),
    (("db2",), "4", "the Db2 precompile and bind cards, DSNHDECP"),
    (("cics", "region"), "5", "the CICS SIT and region code page"),
    (("cics", "program_definition"), "5", "the CSD definitions"),
    (("cics",), "5", "the CICS translator options and CSD / SIT"),
]


def section_of(path: tuple[str, ...]) -> tuple[str, str]:
    for prefix, number, ask in SECTIONS:
        if path[: len(prefix)] == prefix:
            return number, ask
    return "1", "the build files that set this option"


def assumed_values(node: Any, path: tuple[str, ...] = ()) -> list[dict[str, str]]:
    """Every {value, source, note} leaf whose source starts `assumed:`, in file order, with its dotted path."""
    found: list[dict[str, str]] = []
    if isinstance(node, dict):
        source = node.get("source")
        if isinstance(source, str) and ("value" in node or "option" in node):
            if source.startswith("assumed:"):
                number, ask = section_of(path)
                name = str(node.get("option") or path[-1])
                value = str(node.get("value", ""))
                found.append(
                    {
                        "where": ".".join(path),
                        "option": name,
                        "value": value,
                        "basis": source.removeprefix("assumed: "),
                        "section": number,
                        "ask": ask,
                    }
                )
            return found
        for key, child in node.items():
            found += assumed_values(child, path + (str(key),))
    elif isinstance(node, list):
        for index, child in enumerate(node):
            found += assumed_values(child, path + (str(index),))
    return found


def missing_copybooks(report: dict[str, Any]) -> dict[str, list[str]]:
    """{copybook: [programs]} from an evidence report's `refused: missing copybook X` residuals."""
    out: dict[str, list[str]] = {}
    for program in report.get("programs", []):
        match = MISSING.search(str((program.get("residual") or {}).get("refused") or ""))
        if match:
            out.setdefault(match.group(1), []).append(str(program.get("program")))
    return {k: sorted(v) for k, v in sorted(out.items())}


def render(corpus: str, estate: dict[str, Any], report: dict[str, Any] | None) -> str:
    rows = assumed_values({s: estate[s] for s in ("compiler", "parm", "le", "db2", "cics") if s in estate})
    lines = [
        f"# Estate intake: {corpus}",
        "",
        f"Please confirm each value below in writing, or send the file named. What each request means: `{CHECKLIST}`.",
        "A value you do not confirm stays an assumption and is listed as one in the evidence report.",
        "",
        f"## Assumed options ({len(rows)})",
        "",
    ]
    if rows:
        lines += [
            "| # | option | assumed value | assumed because | send | checklist | confirmed |",
            "|---|---|---|---|---|---|---|",
        ]
        for i, r in enumerate(rows, 1):
            value = f"`{r['value']}`" if r["value"] else "(none)"
            lines.append(
                f"| {i} | `{r['where']}` | {value} | {r['basis']} | {r['ask']} | section {r['section']} | [ ] |"
            )
    else:
        lines.append("None: every option has a source in the estate.")
    lines += ["", "## Missing inputs", ""]
    missing = missing_copybooks(report) if report else {}
    if report is None:
        lines.append("No committed evidence report for this estate: copybooks not checked.")
    elif missing:
        lines += ["| copybook | needed by | checklist |", "|---|---|---|"]
        for name, programs in missing.items():
            lines.append(f"| `{name}` | {', '.join(programs)} | section 7 |")
    else:
        lines.append("No missing copybooks in the evidence report.")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("corpus")
    ap.add_argument("--options-dir", type=Path, default=OPTIONS_DIR)
    ap.add_argument("--report", type=Path, help="evidence report.json (default: the committed one for the corpus)")
    args = ap.parse_args(argv)
    path = args.options_dir / f"{args.corpus}.json"
    if not path.is_file():
        print(f"no estate options file: {path}", file=sys.stderr)
        return 2
    estate = json.loads(path.read_text(encoding="utf-8"))
    report_path = args.report or REPORT_DIR / args.corpus / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else None
    sys.stdout.write(render(args.corpus, estate, report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
