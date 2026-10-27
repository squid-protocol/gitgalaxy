#!/usr/bin/env python3
"""The test files the Equivalence E2E shards run (#6664): only the ones whose result can differ from ground-truth's.

    python tests/tools/equivalence_e2e_select.py        # one path per line, for the shard step's pytest line

`mainframe-ground-truth.yml` (a required check) runs all of tests/cobol_mainframe without EQUIVALENCE_E2E, the oracle
image or the shards' JDK 17 setup. The shards used to run the whole directory again: measured on one commit (junit of
runs 40225533892 and 40225536142, 2026-10-25), 7126 of the 7822 tests they ran passed in ground-truth too (1810 s), and
the 696 that ran only in the shards (3177 s) sit in 46 files. A file is selected when

* it reads EQUIVALENCE_E2E (the same test as tests/tools/test_env_gated_tests_run_in_ci_5954.py), or
* a skip reason in it names a tool the shards provide and ground-truth does not: Docker / GnuCOBOL / the oracle image,
  a JDK, Maven or a jar (5 of the 46 files skip in ground-truth for "no JDK 17" and read no variable).

That keeps every one of the 696 and 188 s of the duplicates. tests/tools/test_zos_probes.py is always added, and the
five Db2 files (the `db2` job runs them) and test_evidence_components.py (ground-truth runs it) are left out. Runs
after the install: it reads through gitgalaxy.core.source_text (#3813).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from gitgalaxy.core.source_text import read_source

sys.path.insert(0, str(Path(__file__).resolve().parent))
from equivalence_e2e_plan import DB2_FILES  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
E2E_READ = re.compile(r"environ(?:\.get\(|\[)\s*[\"']EQUIVALENCE_E2E")
REASON = re.compile(r"(?:reason=|skip\()\s*f?\"([^\"]*)\"")  # as test_env_gated_tests_run_in_ci_5954.REASON
TOOL_REASON = re.compile(r"Docker|docker|GnuCOBOL|oracle image|JDK|Maven|\bjar\b")
ALWAYS = ("tests/tools/test_zos_probes.py",)
LEFT_OUT = (*DB2_FILES, "tests/cobol_mainframe/test_evidence_components.py")


def selected_by(text: str) -> bool:
    return bool(E2E_READ.search(text) or TOOL_REASON.search(" ".join(REASON.findall(text))))


def select(root: Path = REPO_ROOT) -> list[str]:
    picked = []
    for f in sorted((root / "tests" / "cobol_mainframe").rglob("test_*.py")):
        rel = f.relative_to(root).as_posix()
        if rel not in LEFT_OUT and selected_by(read_source(f).text):  # #3813: no lossy decode
            picked.append(rel)
    return picked + [p for p in ALWAYS if (root / p).is_file()]


def main() -> int:
    picked = select()
    if len(picked) <= len(ALWAYS):  # an empty selection would let pytest collect from the rootdir instead
        print("equivalence_e2e_select: no tests/cobol_mainframe file selected", file=sys.stderr)
        return 1
    print("\n".join(picked))
    return 0


if __name__ == "__main__":
    sys.exit(main())
