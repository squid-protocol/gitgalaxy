# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#4726: the translate-only dry run of `gitgalaxy assess`.

Each COBOL program is translated by the det translator (no model, no Docker, Db2 or JDK) against a synthetic service
stub and an empty generated project, and only the outcome is kept: whole / holes / refused, the statement counts, and
the class name of a refusal. A hole's text (it can quote the program) is counted, never kept.

The stub stands in for the estate's generated project, so this is a LOWER BOUND on what the full translate does: a
CICS program's COMMAREA contract and a CALL / LINK target's service are not resolved, and a callee's holes are not
credited to its caller (#4803). It is a translation status, not a proof level.
"""

from __future__ import annotations

import re
import signal
import tempfile
from pathlib import Path
from typing import Any

WHOLE, HOLES, REFUSED = "whole", "holes", "refused"
TRANSLATIONS = (WHOLE, HOLES, REFUSED)
TIMEOUT_S = 60
PKG = "com.gitgalaxy.modernized"
BATCH_STUB = "public class {svc}Service {{\n}}\n"
CICS_STUB = "public class {svc}Service {{\n  void runTask(CicsTask task) {{\n  }}\n}}\n"


class Timeout(Exception):
    pass


def _alarm(_sig: int, _frame: Any) -> None:
    raise Timeout


def _with_timeout(fn: Any, seconds: int) -> Any:
    """`fn()` under a SIGALRM fuse where the platform has one (main thread, POSIX); plain elsewhere."""
    if not hasattr(signal, "SIGALRM"):
        return fn()
    old = signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(seconds)
    try:
        return fn()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def translate_program(
    prog: Path, copy_dirs: list[Path], estate_opt: Any, project: Path, timeout: int = TIMEOUT_S
) -> dict[str, Any]:
    """{"translation": whole | holes | refused, "statements", "translated_statements", "holes"} of one program, or
    {"translation": refused, "refusal": <exception class name>}."""
    from gitgalaxy.core.estate_options import effective_options
    from gitgalaxy.core.source_text import read_source
    from gitgalaxy.tools.cobol_to_java.det import program as P

    try:
        text = read_source(prog).text
        svc = re.sub(r"[^A-Za-z0-9]", "", prog.stem.title()) or "Program"
        stub = (CICS_STUB if re.search(r"(?i)\bEXEC\s+CICS\b", text) else BATCH_STUB).format(svc=svc)
        layers = effective_options(case=None, estate=estate_opt, program=prog.stem).layers
        r = _with_timeout(
            lambda: P.translate(prog, copy_dirs, stub, PKG, None, project, "dispatch", False, False, layers), timeout
        )
    except Timeout:
        return {"translation": REFUSED, "refusal": "Timeout"}
    except Exception as e:
        return {"translation": REFUSED, "refusal": type(e).__name__}
    stats = [r.stats, *(x.stats for x in r.extra)]  # #5106: each sibling program the unit CALLs counts for it
    holes = sum(len(st["holes"]) for st in stats)
    return {
        "translation": HOLES if holes else WHOLE,
        "statements": sum(int(st["statements"]) for st in stats),
        "translated_statements": sum(int(st["translated"]) for st in stats),
        "holes": holes,
    }


def dry_run(
    estate: Path, copy_dirs: list[Path], estate_opt: Any, programs: list[Path], timeout: int = TIMEOUT_S
) -> dict[str, dict[str, Any]]:
    """{estate-relative program path: outcome} for `programs`; nothing is written into `estate`."""
    out: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory(prefix="gitgalaxy-dryrun-") as tmp:
        project = Path(tmp) / "project"
        (project / "src" / "main" / "java").mkdir(parents=True)
        for prog in programs:
            rel = str(prog.relative_to(estate)).replace("\\", "/")
            out[rel] = translate_program(prog, copy_dirs, estate_opt, project, timeout)
    return out
