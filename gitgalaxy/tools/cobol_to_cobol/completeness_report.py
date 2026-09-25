# ==============================================================================
# GitGalaxy Tool: mainframe skeleton-completeness report (#3498)
#
# PURPOSE:
# After a scan, how much of the estate's mainframe skeleton actually resolved --
# and which inputs the estate owner still has to hand over to close the gaps.
# A thin renderer over GalaxyIR.completeness(); see its docstring for the
# channels, and docs/mainframe_ingestion_checklist.md for the inputs.
#
#   python -m gitgalaxy.tools.cobol_to_cobol.completeness_report <master.db>
#       [--repo NAME] [--json out.json] [--md out.md]
# ==============================================================================
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir


def render_markdown(report: dict[str, Any], title: str) -> str:
    """The completeness report as Markdown: score, channel table, missing inputs."""
    score = report["score"]
    lines = [f"# Mainframe skeleton completeness: {title}", ""]
    lines.append(
        f"**Score: {score:.0%}** (mean of the channel ratios below)" if score is not None else "No channel has facts."
    )
    lines += ["", "| channel | resolved | of | ratio | system (not a gap) | gaps |", "|---|---|---|---|---|---|"]
    for name, ch in report["channels"].items():
        gaps = ", ".join(f"{k}: {v}" for k, v in ch["gaps"].items() if v) or "-"
        ratio = f"{ch['ratio']:.0%}" if ch["ratio"] is not None else "-"
        lines.append(f"| {name} | {ch['resolved']} | {ch['total']} | {ratio} | {ch['system']} | {gaps} |")
    lines += ["", "## Missing inputs", ""]
    if not report["missing_inputs"]:
        lines.append("None: every gap above is an engine limit, not a missing input.")
    for m in report["missing_inputs"]:
        lines.append(f"- **{m['input']}**: {m['count']}")
        lines += [f"  - `{e}`" for e in m["examples"]]
    lines += ["", "See docs/mainframe_ingestion_checklist.md for how to extract each input."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("db", type=Path, help="a galaxyscope master DB")
    ap.add_argument("--repo", help="repository name inside the DB (default: the only / latest one)")
    ap.add_argument("--json", type=Path, help="also write the report as JSON")
    ap.add_argument("--md", type=Path, help="write the Markdown report here instead of stdout")
    args = ap.parse_args(argv)
    ir = load_galaxy_ir(args.db, args.repo)
    report = ir.completeness()
    md = render_markdown(report, ir.repo_name)
    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.md:
        args.md.write_text(md, encoding="utf-8")
    else:
        sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
