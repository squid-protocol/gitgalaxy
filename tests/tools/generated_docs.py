#!/usr/bin/env python3
"""The aggregate pages rendered from committed sources and published, never committed (#5057, the pattern of #4825 / #4963).

Every PR that added a register entry or a CICS slice re-rendered and committed these pages, so parallel PRs
conflicted on them (30 commits to oracle_assumptions.md in three days). Main now holds only their sources; the pages
are git-ignored. A PR's CI (generated-docs.yml) renders them -- the render must succeed and be deterministic -- and
shows the diff against the PR's base in the job summary; after a merge the same workflow renders them from main and
publishes them to the `generated` branch (tests/tools/generated_branch.py). No workflow writes them to main.

    check [--out DIR]       render every page twice: fail on an error or on two renders that differ; write to DIR
    diff BASE_DIR NEW_DIR   a markdown diff of the pages between two `check --out` directories (job summary)
    render                  write the pages into the working tree (git-ignored; for reading locally)

Published copies: https://github.com/squid-protocol/gitgalaxy/tree/generated/docs/language_status
"""

from __future__ import annotations

import argparse
import difflib
import sys
from collections.abc import Callable
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO))

PUBLISHED = "https://github.com/squid-protocol/gitgalaxy/blob/generated/"
DIFF_LINES = 400  # per page, in the job summary; the artifact carries the whole diff


def _register() -> str:
    import register  # tests/tools/register.py

    return register.render()


def _cics_spec_status() -> str:
    import cics_spec_status  # tests/tools/cics_spec_status.py

    return cics_spec_status.render()


def _cobolrt_rules() -> str:
    import cobolrt_rules  # tests/tools/cobolrt_rules.py (#4711)

    return cobolrt_rules.render()


def _readiness_report() -> str:
    import readiness_report  # tests/tools/readiness_report.py (#4725)

    return readiness_report.render()


def _progress_md() -> str:
    import progress_report  # tests/tools/progress_report.py (#5280)

    return progress_report.render_page()


def _progress_json() -> str:
    import progress_report

    return progress_report.render_json_page()


def _progress_svg() -> str:
    import progress_slide  # tests/tools/progress_slide.py (#5286)

    return progress_slide.render_page()


# repo-relative path -> its renderer. A page added here must also be git-ignored and published by generated-docs.yml
# (test_generated_docs.py checks both).
PAGES: dict[str, Callable[[], str]] = {
    "docs/language_status/oracle_assumptions.md": _register,
    "docs/language_status/cics_spec_status.md": _cics_spec_status,
    "docs/language_status/cobolrt_rules.md": _cobolrt_rules,
    "docs/language_status/readiness_report.md": _readiness_report,
    "docs/language_status/progress.md": _progress_md,
    "docs/language_status/progress.json": _progress_json,
    "docs/language_status/progress.svg": _progress_svg,
}


def check(out: Path | None = None, pages: dict[str, Callable[[], str]] | None = None) -> list[str]:
    """Render each page twice; return the problems (an exception, or two renders that differ). Writes to `out`."""
    problems = []
    for rel, fn in (pages or PAGES).items():
        try:
            first, second = fn(), fn()
        except Exception as e:  # noqa: BLE001 -- any failure of a renderer is reported with its page
            problems.append(f"{rel}: does not render: {type(e).__name__}: {e}")
            continue
        if first != second:
            problems.append(f"{rel}: two renders of the same tree differ (the renderer is not deterministic)")
            continue
        if out is not None:
            dest = out / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(first, encoding="utf-8", newline="\n")
    return problems


def diff(base: Path, new: Path, pages: list[str] | None = None, limit: int = DIFF_LINES) -> str:
    """Markdown: per page, whether it changes and a unified diff (cut at `limit` lines)."""
    out = [
        "## Generated pages (#5057)",
        "",
        "Rendered from this PR's sources; published to `generated` after merge.",
        "",
    ]
    for rel in pages or list(PAGES):
        a, b = base / rel, new / rel
        old = a.read_text(encoding="utf-8").splitlines(keepends=True) if a.is_file() else []
        cur = b.read_text(encoding="utf-8").splitlines(keepends=True) if b.is_file() else []
        lines = list(difflib.unified_diff(old, cur, f"base/{rel}", f"pr/{rel}"))
        if not lines:
            out.append(f"- `{rel}`: unchanged")
            continue
        added = sum(1 for ln in lines if ln.startswith("+") and not ln.startswith("+++"))
        removed = sum(1 for ln in lines if ln.startswith("-") and not ln.startswith("---"))
        out += [f"- `{rel}`: +{added} / -{removed} lines", "", "```diff"]
        out += [ln.rstrip("\n") for ln in lines[:limit]]
        if len(lines) > limit:
            out.append(f"... {len(lines) - limit} more diff lines (see the generated-docs artifact)")
        out += ["```", ""]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="render every page twice; fail on an error or a non-deterministic render")
    c.add_argument("--out", type=Path, help="write the rendered pages under this directory")
    d = sub.add_parser("diff", help="markdown diff of the pages between two `check --out` directories")
    d.add_argument("base", type=Path)
    d.add_argument("new", type=Path)
    sub.add_parser("render", help="write the pages into the working tree (git-ignored)")
    a = ap.parse_args(argv)
    if a.cmd == "diff":
        sys.stdout.write(diff(a.base, a.new))
        return 0
    problems = check(REPO if a.cmd == "render" else a.out)
    for p in problems:
        print(f"generated-docs: {p}", file=sys.stderr)
    if not problems:
        where = "the working tree" if a.cmd == "render" else (str(a.out) if a.out else "nowhere (check only)")
        print(f"{len(PAGES)} page(s) render deterministically; written to {where}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
