# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#4726: `gitgalaxy assess --jcl`: the estate's compile options read from its own JCL.

Every `EXEC PGM=IGYCRCTL,PARM=...` step of the JCL members given is a compile PARM. The options all of them agree on
become `parm.default` of an estate options file (core/estate_options.py) with the member and line as provenance; an
option that differs between steps (CICS in one, NOCICS in another) is dropped, because the JCL does not say which
program each step builds. Everything the JCL cannot say (compiler version, LE, Db2, CICS) is `assumed`.

The result is read by the dry run only; nothing of it, and no JCL text, reaches the report. The notices name options and
reasons, never JCL text.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

JCL_SUFFIXES = {".jcl", ".cntl", ".proc", ".prc"}
COMPILER = "IGYCRCTL"
ASSUMED = "assumed: not stated in the corpus"


def members(path: Path) -> list[Path]:
    """The JCL members under `path` (a file is taken as it is), sorted."""
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in JCL_SUFFIXES)


def compile_steps(files: list[Path], root: Path) -> list[dict[str, Any]]:
    """[{source, parm}] for each IGYCRCTL step: `source` is '<member relative to root>:<line>'."""
    from gitgalaxy.core.job_flow import jcl_job_flow
    from gitgalaxy.core.source_text import read_source

    steps: list[dict[str, Any]] = []
    for f in files:
        rel = f.relative_to(root).as_posix() if f != root else f.name
        steps.extend(
            {"source": f"{rel}:{row['line']}", "parm": row.get("parm")}
            for row in jcl_job_flow(read_source(f).text)
            if row["kind"] == "STEP" and row["program"] == COMPILER
        )
    return steps


def options_from_jcl(path: Path) -> tuple[dict[str, Any], list[str]]:
    """(an estate options file, notices). Notices say what the JCL did not settle."""
    from gitgalaxy.core.compiler_options import parse_options
    from gitgalaxy.core.estate_options import FORMAT

    root = path if path.is_dir() else path.parent
    steps = compile_steps(members(path), root)
    notices: list[str] = []
    agreed: dict[tuple[str, str], str] | None = None
    dropped: set[str] = set()
    for step in steps:
        parm = step["parm"] or ""
        if parm.strip().upper() == "OPTFILE":
            notices.append("a compile step takes its options from an OPTFILE (SYSOPTF) member, which is not read")
            parm = ""
        rows = {(o, v or ""): step["source"] for o, v, _ in parse_options(parm)}
        if agreed is None:
            agreed = rows
        else:
            dropped |= {o for (o, _v) in set(agreed) ^ set(rows)}
            agreed = {k: s for k, s in agreed.items() if k in rows}
    if not steps:
        notices.append("no compile step (EXEC PGM=IGYCRCTL) found: every option is IBM's default")
    elif len(steps) > 1 and dropped:
        notices.append(
            f"{len(steps)} compile steps differ; options dropped as not common to all: " + ", ".join(sorted(dropped))
        )
    note = "a compile step's PARM in the estate's JCL" + (f" (common to {len(steps)} steps)" if len(steps) > 1 else "")
    doc: dict[str, Any] = {
        "format": FORMAT,
        "estate": "jcl",
        "corpus": "jcl",
        "compiler": {
            "product": {"value": "Enterprise COBOL", "source": steps[0]["source"], "note": f"PGM={COMPILER}"}
            if steps
            else {"value": "Enterprise COBOL", "source": ASSUMED, "note": "no compile step in the JCL given"},
            "version": {"value": None, "source": ASSUMED, "note": "the JCL does not state the compiler version"},
            "installation_defaults": {},
        },
        "parm": {
            "default": [
                {"option": o, "value": v, "source": src, "note": note} for (o, v), src in sorted((agreed or {}).items())
            ],
            "programs": {},
        },
        "le": {},
        "db2": {},
        "cics": {},
    }
    return doc, notices
