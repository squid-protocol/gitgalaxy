"""#5126: two checklist members that turned out to be settled, pinned so they stay so.

1. No burned-estate program that reads ASSIGN STARTCODE lacks a case that states it (proof_blockers then drops the gap).
2. `cics_census` and `embedded_verb_coverage` hold no EIB-name scan, so they cannot share proof_blockers' literal /
   hyphen false positive (`'EIBFN: '`, `EIBRCODE-NICE`, #5125): the only EIB scan is proof_blockers' own `_EIB`."""

import os
import sys
from pathlib import Path

import pytest

from gitgalaxy.core.source_text import read_source

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[0] / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(HERE))
import proof_blockers as pb  # noqa: E402

BURNED_DIRS = (
    "aws-mainframe-modernization-carddemo",
    "cics-async-api-credit-card-application-example",
    "cics-banking-sample-application-cbsa",
    "cics-genapp",
    "dbb-mortgage-application",
    "zecs",
)
SUFFIXES = {".cbl", ".cob", ".cobol"}


def test_the_census_tools_scan_no_eib_names():
    for name in ("cics_census.py", "embedded_verb_coverage.py"):
        text = read_source(TOOLS / name).text
        assert "eib" not in text.lower(), f"{name} now names EIB: give it proof_blockers' whole-word rule"


def test_every_burned_startcode_reader_has_a_case_that_states_it():
    root = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    if not root or not Path(root).is_dir():
        pytest.skip("GITGALAXY_MAINFRAME_CORPORA is not set")
    runs = pb.equivalence_runs()
    stems: dict[tuple[str, str], list[pb.Run]] = {}
    for (corpus, path), rs in runs.items():
        stems.setdefault((corpus, Path(path).stem.lower()), []).extend(rs)
    readers = []
    for name in BURNED_DIRS:
        base = Path(root) / name
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if path.suffix.lower() not in SUFFIXES or not path.is_file():
                continue
            text = read_source(path).text
            if "STARTCODE" in text.upper() and "STARTCODE" in pb.facts_needed(text)["assign_task"]:
                readers.append((name, path.stem.lower()))
    assert readers, "no burned STARTCODE reader found: the scan or the corpora moved"
    unstated = [r for r in readers if not any(x.startcode for x in stems.get(r, []))]
    assert not unstated, f"STARTCODE readers with no case stating it: {unstated}"
