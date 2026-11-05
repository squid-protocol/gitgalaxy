#!/usr/bin/env python3
"""How big each burned estate is, and how much of its JCL the step-flow reader reads -- recorded for the status slide.

Owner 2026-11-04 (#7699 follow-up): a reader weighing "125 of 129 programs" asks how big those programs are, and a
reader of the JCL step-flow row asks how many of the estates' jobs it covers. Both need the corpus checkouts, which
the docs run does not have, so this records them once in tests/fixtures/estate_size.json; a test re-measures and
compares wherever the corpora are present (GITGALAXY_MAINFRAME_CORPORA, as the CardDemo JCL case does).

Per estate:
  programs / program_lines   the ladder's programs (the evidence report's list) and their physical lines
  copybooks / copybook_lines distinct COPY / EXEC SQL INCLUDE names those programs use, and the lines of the ones
                             found in the checkout by member name (missing: named but not in the checkout)
  jcl_members                files with a JCL extension (.jcl, .proc, .prc)
  jcl_jobs                   JOB statements gitgalaxy.core.job_flow reads with at least one step
  jcl_cond_jobs              of those, jobs whose flow depends on a test (a step with COND= or inside IF/THEN)
  jcl_checked_jobs           of those, jobs with IBM-based run / bypass answers the evaluator reproduces
                             (tests/equivalence/jcl/<estate short>/scenarios.json)

    python tests/tools/estate_size.py CORPORA [--write]      # print, or rewrite the record
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO))

RECORD = REPO / "tests" / "fixtures" / "estate_size.json"
FORMAT = "estate-size/1"
JCL_EXT = {".jcl", ".proc", ".prc"}
JCL_CASES = {
    "aws-mainframe-modernization-carddemo": REPO / "tests" / "equivalence" / "jcl" / "carddemo" / "scenarios.json"
}
_COPY = re.compile(r"\bCOPY\s+['\"]?([A-Z0-9#@$][A-Z0-9#@$-]*)", re.I)
_INCLUDE = re.compile(r"\bEXEC\s+SQL\s+INCLUDE\s+([A-Z0-9#@$][A-Z0-9#@$-]*)", re.I)
_SKIP_INCLUDE = {"SQLCA", "SQLDA"}  # the precompiler's own areas, not members


def _lines(path: Path) -> list[str]:
    from gitgalaxy.core.source_text import read_source

    return read_source(path).text.splitlines()


def _code(line: str) -> str:
    """Area A-B of a fixed-format line (columns 8-72), or "" for a comment / debugging line."""
    if len(line) > 6 and line[6] in "*/":
        return ""
    return line[7:72] if len(line) > 7 else ""


def copy_names(lines: list[str]) -> set[str]:
    out: set[str] = set()
    for ln in lines:
        code = _code(ln)
        out |= {m.upper() for m in _COPY.findall(code)}
        out |= {m.upper() for m in _INCLUDE.findall(code) if m.upper() not in _SKIP_INCLUDE}
    return out


def _members(root: Path) -> dict[str, Path]:
    """Member name (file stem, upper case) -> file, first in sorted order; skips the checkout's .git."""
    out: dict[str, Path] = {}
    for f in sorted(p for p in root.rglob("*") if p.is_file() and ".git" not in p.parts):
        out.setdefault(f.stem.upper(), f)
    return out


def measure_estate(root: Path, programs: list[str], estate: str) -> dict[str, Any]:
    from gitgalaxy.core import job_flow

    prog_lines = 0
    names: set[str] = set()
    progs = [root / p for p in programs]
    for f in progs:
        if f.is_file():
            ls = _lines(f)
            prog_lines += len(ls)
            names |= copy_names(ls)
    members = _members(root)
    program_files = {f.resolve() for f in progs}
    cb_lines, missing = 0, 0
    for n in sorted(names):
        f = members.get(n)
        if f is None or f.resolve() in program_files:
            missing += f is None
            continue
        cb_lines += len(_lines(f))
    jobs = cond = 0
    for f in sorted(
        p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in JCL_EXT and ".git" not in p.parts
    ):
        rows = job_flow.jcl_job_flow("\n".join(_lines(f)))
        current, has_step, has_test = None, False, False
        for r in [*rows, {"kind": "JOB"}]:  # a sentinel closes the last job
            if r["kind"] == "JOB":
                if current is not None and has_step:
                    jobs += 1
                    cond += has_test
                current, has_step, has_test = r.get("name") or "", False, False
            elif r["kind"] == "STEP":
                has_step = True
                has_test = has_test or bool(r.get("cond") or r.get("if_cond"))
    n_jcl = sum(1 for p in root.rglob("*") if p.is_file() and p.suffix.lower() in JCL_EXT and ".git" not in p.parts)
    case = JCL_CASES.get(estate)
    checked = len(json.loads(case.read_text(encoding="utf-8"))["jobs"]) if case and case.is_file() else 0
    return {
        "programs": len(programs),
        "program_lines": prog_lines,
        "copybooks": len(names),
        "copybook_lines": cb_lines,
        "copybooks_missing": missing,
        "jcl_members": n_jcl,
        "jcl_jobs": jobs,
        "jcl_cond_jobs": cond,
        "jcl_checked_jobs": checked,
    }


def estate_programs() -> dict[str, list[str]]:
    """estate -> the ladder's program paths, from the evidence reports (as progress_report reads them)."""
    import readiness_report

    return {
        n: [p["program"] for p in readiness_report._load(readiness_report._reports() / n / "report.json")["programs"]]
        for n in readiness_report.estates()
    }


def measure(corpora: Path, programs: dict[str, list[str]] | None = None) -> dict[str, Any]:
    programs = estate_programs() if programs is None else programs
    return {
        "format": FORMAT,
        "estates": {
            n: measure_estate(corpora / n, ps, n) for n, ps in sorted(programs.items()) if (corpora / n).is_dir()
        },
    }


def load() -> dict[str, Any]:
    """The recorded sizes ({} when absent): estate -> the fields above."""
    return (json.loads(RECORD.read_text(encoding="utf-8")).get("estates") or {}) if RECORD.is_file() else {}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("corpora", type=Path)
    ap.add_argument("--write", action="store_true", help=f"rewrite {RECORD.relative_to(REPO)}")
    a = ap.parse_args(argv)
    body = measure(a.corpora)
    text = json.dumps(body, indent=2) + "\n"
    if a.write:
        RECORD.write_text(text, encoding="utf-8")
        print(RECORD)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
