"""#7169: a PICTURE's repeat count is a run length, never expanded to one entry per position.

`_pic_positions` built one list entry per picture position, so `PIC X(1073741824)` -- a 1 GiB LINKAGE
buffer, a GnuCOBOL idiom for a caller-sized area (acherm/agentic-cobol-compress-cc declares it 8 times) --
became ~10^9 list entries: the scan reached 12.9 GB RSS in 7.6 s and was OOM-killed in the completeness
phase (dynamic_call_targets -> data_flows -> _storage_spans -> _elementary_bytes). Under a memory cap the
MemoryError was caught by the phase's guard and the completeness score silently dropped. `_pic_runs`
keeps (symbol, count) runs; every width is computed from them and is unchanged for ordinary pictures.
"""

import json
import os
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path

import pytest

from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import EngineDataItem, _elementary_bytes, _pic_runs

GIB = 1073741824  # the buffer's size: scanned only in a capped subprocess below
# In-process tests use 2**24 positions: still 2000 times their 64 KiB bound if a regression expands it (128 MiB
# as a list), but a size any CI runner survives -- expanding GIB in-process would be ~8 GiB.
BIG = 2**24
ROOT = Path(__file__).resolve().parents[2]


def _item(pic, usage=None, sign_separate=False, currency=None):
    return EngineDataItem(
        ordinal=0, parent_ordinal=None, level=5, name="F", section=None, fd_name=None, pic=pic, usage=usage,
        occurs_min=None, occurs_max=None, occurs_depending_on=None, redefines=None, value=None, line=1,
        sign_separate=sign_separate, currency=currency or {},
    )  # fmt: skip


def test_a_huge_picture_is_one_run_in_bounded_time_and_memory():
    tracemalloc.start()
    started = time.perf_counter()
    runs = _pic_runs(f"X({BIG})")
    width = _elementary_bytes(_item(f"X({BIG})"))
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert runs == [("X", BIG)]
    assert width == BIG
    # the old expansion allocated ~8 bytes a position here; a run list is a few hundred bytes
    assert peak < 64 * 1024, peak
    assert elapsed < 0.5, elapsed


def test_runs_keep_the_old_position_counts():
    assert _pic_runs("X(3)9") == [("X", 3), ("9", 1)]
    assert _pic_runs("S9(4)V99") == [("S", 1), ("9", 4), ("V", 1), ("9", 1), ("9", 1)]
    assert _pic_runs("ZZ9.99CR") == [("Z", 1), ("Z", 1), ("9", 1), (".", 1), ("9", 1), ("9", 1), ("C", 2)]
    assert _pic_runs("CR(3)") == [("C", 4)]  # a repeat after CR repeats its letter, as before
    assert _pic_runs("X(0)") == [("X", 1)]  # X(0) stayed one position
    for bad in ("X(3", "X()", "X(A)", "X(²)"):  # X(²) used to raise ValueError
        assert _pic_runs(bad) is None, bad


@pytest.mark.parametrize(
    ("pic", "usage", "kw", "width"),
    [
        ("X(10)", None, {}, 10),
        (f"X({BIG})", "DISPLAY", {}, BIG),
        (f"9({BIG})", None, {}, BIG),
        ("S9(7)V99", None, {}, 9),  # S and V take no storage
        ("S9(7)V99", None, {"sign_separate": True}, 10),
        ("PPP999", None, {}, 3),
        ("ZZZ,ZZ9.99CR", None, {}, 12),
        ("-(5)9.99DB", None, {}, 11),
        ("$$$,$$9.99", None, {}, 10),
        ("UUU9.99", None, {"currency": {"U": "EUR "}}, 10),  # #3820
        ("UUU9.99", None, {"currency": {"U": None}}, None),
        ("S9(7)", "COMP-3", {}, 4),
        ("S9(4)", "COMP", {}, 2),
        ("S9(9)", "BINARY", {}, 4),
        ("S9(18)", "COMP-5", {}, 8),
        ("9(19)", "COMP", {}, None),  # more than 18 digits: unknown
        ("X(4)", "COMP", {}, None),  # binary without digits: unknown
        ("N(5)", None, {}, 10),
        ("G(4)", "DISPLAY-1", {}, 8),
        ("X(3)", "NATIONAL", {}, 6),
        (":TAG:", None, {}, None),  # a REPLACING tag: unknown, not guessed
        ("X(3", None, {}, None),
    ],
)
def test_widths_of_ordinary_pictures_do_not_change(pic, usage, kw, width):
    assert _elementary_bytes(_item(pic, usage, **kw)) == width


PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. BIGBUF.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-BUF               PIC X(1073741824).
       01  WS-PGM               PIC X(8) VALUE 'SUBPGM'.
       LINKAGE SECTION.
       01  LK-BUF               PIC X(1073741824).
       PROCEDURE DIVISION USING LK-BUF.
           MOVE SPACES TO WS-BUF.
           MOVE WS-BUF TO LK-BUF.
           CALL WS-PGM USING LK-BUF.
           GOBACK.
"""

# Reads the scan back in a child under the same cap: the record widths and the completeness pass that
# used to expand the picture (dynamic_call_targets -> data_flows -> _storage_spans).
READ_BACK = """
import json, sys
from pathlib import Path
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir
ir = load_galaxy_ir(Path(sys.argv[1]))
(ef,) = [f for f in ir.files.values() if f.file_path.endswith("BIGBUF.cbl")]
widths = {r.name: ir.record_layout(ef, r)["bytes"] for r in ef.records}
ir.completeness()
print(json.dumps({"widths": widths, "dynamic": len(ir.dynamic_call_targets())}))
"""

CAP = 3 * 1024**3  # the old expansion needs ~8 GiB per field: it fails fast under this cap, never the box


def _capped():
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (CAP, CAP))


@pytest.mark.skipif(sys.platform != "linux", reason="RLIMIT_AS caps the child's address space on Linux only")
def test_a_gib_working_storage_and_linkage_buffer_scans_under_a_cap(tmp_path):
    repo = tmp_path / "estate"
    (repo / "cbl").mkdir(parents=True)
    (repo / "cbl" / "BIGBUF.cbl").write_text(PROGRAM, encoding="utf-8")
    out = tmp_path / "scan"
    env = {**os.environ, "GITGALAXY_DISABLE_GIT_HISTORY": "1"}
    started = time.perf_counter()
    scan = subprocess.run(  # noqa: S603 -- this interpreter + fixed module
        [sys.executable, "-m", "gitgalaxy.galaxyscope", str(repo), "--db-only", "--output", str(out)],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=600, preexec_fn=_capped, check=False,
    )  # fmt: skip
    assert scan.returncode == 0, scan.stderr[-2000:]
    # the phase guard logged (and swallowed) the MemoryError before #7169
    assert "COMPLETENESS_FAILURE" not in scan.stderr, scan.stderr[-2000:]
    assert "MemoryError" not in scan.stderr
    read = subprocess.run(  # noqa: S603
        [sys.executable, "-c", READ_BACK, str(out / "estate_galaxy_master.db")],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=600, preexec_fn=_capped, check=False,
    )  # fmt: skip
    assert read.returncode == 0, read.stderr[-2000:]
    got = json.loads(read.stdout.strip().splitlines()[-1])
    assert got["widths"] == {"WS-BUF": GIB, "WS-PGM": 8, "LK-BUF": GIB}
    assert time.perf_counter() - started < 300
