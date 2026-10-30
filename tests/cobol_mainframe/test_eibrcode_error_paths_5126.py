"""#5126 (register X64): a normal-response EIBRCODE (6 X'00') is unmodelled because no burned program can observe it.
This pins that reading: every EIBRCODE read in the burned estates' COBOL sits in a paragraph that only runs after a
non-NORMAL response. The day a burned program reads it on a normal response, this fails and sends whoever finds it to
set the zero in `det/cics.py` and `ggcics_faults.c` together. Burned estates only (no census clone is opened)."""

import os
import re
import sys
from pathlib import Path

import pytest

from gitgalaxy.core.source_text import read_source

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import test_eib_fn_rcode_5126 as guard  # noqa: E402

READ = re.compile(r"\bEIBRCODE\b(?![-\w])")
PARA = re.compile(r"^.{6} ([A-Z0-9][A-Z0-9-]*)\.\s*$")


def _code_lines(path: Path) -> list[str]:
    # fixed format: column 7 '*' or '/' is a comment
    return [ln for ln in read_source(path).text.splitlines() if len(ln) < 7 or ln[6] not in "*/"]


def _zecs001() -> Path:
    root = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    if not root:
        pytest.skip("GITGALAXY_MAINFRAME_CORPORA is not set")
    found = sorted((Path(root) / "zecs").rglob("ZECS001.cbl"))
    if not found:
        pytest.skip("the zecs corpus is not checked out")
    return found[0]


def test_every_eibrcode_read_is_in_the_file_error_paragraph():
    para, readers = "", []
    for ln in _code_lines(_zecs001()):
        m = PARA.match(ln)
        if m:
            para = m.group(1)
        elif READ.search(ln):
            readers.append(para)
    assert readers == ["9100-FILE-ERROR"], (
        "a burned program reads EIBRCODE outside the error paragraph: a normal-response value is now observable; "
        "set 6 X'00' on both runtimes (det/cics.py + ggcics_faults.c) and update X64"
    )


def test_every_caller_of_the_file_error_paragraph_follows_a_response_test():
    lines = _code_lines(_zecs001())
    calls = [i for i, ln in enumerate(lines) if re.search(r"PERFORM\s+9100-FILE-ERROR", ln)]
    assert calls
    for i in calls:
        window = " ".join(lines[max(0, i - 6) : i])
        assert re.search(r"EIBRESP\s+(NOT\s+)?EQUAL\s+DFHRESP\(NORMAL\)", window), lines[i]


def test_the_guard_module_still_names_zecs001_as_the_only_reader():
    assert guard.KNOWN_READERS == {"ZECS001": {"EIBRCODE"}}
