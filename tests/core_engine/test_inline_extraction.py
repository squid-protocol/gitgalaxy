"""#3913: a small scan (or a pinned single worker) is extracted in-process, not by a worker pool.

Under the `spawn` start method (Windows, macOS) each pool worker re-imports GitGalaxy -- seconds --
to extract files that take milliseconds; a test suite of tiny scans spent most of its time there.
The in-process path runs the same worker code on the same inputs, so its output must be the pool's,
byte for byte, and it must not leak what the process boundary used to contain.
"""

import concurrent.futures
import logging
import os
import signal
import sqlite3
import subprocess
import sys

import pytest

from gitgalaxy import galaxyscope

FILES = {
    **{f"src/mod{i}.py": f"import os\n\n\ndef handler_{i}(event, ctx):\n    if event:\n        return os.getcwd()\n    return None\n" for i in range(12)},
    **{f"lib/util{i}.js": f"export function helper{i}(a, b) {{\n  for (const x of a) {{ b.push(x); }}\n  return b;\n}}\n" for i in range(8)},
    "cbl/PAYROLL.cbl": "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. PAYROLL.\n       PROCEDURE DIVISION.\n       100-MAIN.\n           CALL 'TAXCALC'.\n           GOBACK.\n",
}  # fmt: skip


def _scan(estate, out, workers):
    env = {k: v for k, v in os.environ.items() if k != "GALAXYSCOPE_MAX_WORKERS"}  # conftest pins it under xdist
    env.update(GITGALAXY_LICENSE_KEY="COMMUNITY_FREE_TIER", GITGALAXY_DISABLE_GIT_HISTORY="1")
    if workers:
        env["GALAXYSCOPE_MAX_WORKERS"] = str(workers)
    subprocess.run([sys.executable, "-m", "gitgalaxy.galaxyscope", str(estate), "--db-only", "--output", str(out)],
                   check=True, env=env, capture_output=True)  # fmt: skip
    (db,) = out.glob("*_galaxy_master.db")
    return db


def _facts(db):
    """Every row of every table, minus the columns that time the run."""
    con = sqlite3.connect(db)
    facts = {}
    for (table,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"):
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
        keep = [c for c in cols if not any(t in c.lower() for t in ("time", "speed", "timestamp", "duration"))]
        if keep:
            select = ", ".join(f'"{c}"' for c in keep)
            facts[table] = sorted(map(repr, con.execute(f"SELECT {select} FROM {table}")))
    return facts


def test_in_process_extraction_is_the_pools_output(tmp_path):
    estate = tmp_path / "estate"
    for rel, text in FILES.items():
        (estate / rel).parent.mkdir(parents=True, exist_ok=True)
        (estate / rel).write_text(text, encoding="utf-8")
    assert len(FILES) > galaxyscope._INLINE_MAX_FILES  # large enough that the default is the pool
    pool = _facts(_scan(estate, tmp_path / "pool", workers=None))
    inline = _facts(_scan(estate, tmp_path / "inline", workers=1))
    assert pool == inline
    assert len(pool["function_data"]) >= 21


def test_the_inline_executor_is_the_pool_interface_without_its_leaks():
    seen = {}
    config = {"k": []}

    def init(cfg, level):
        cfg["k"].append("mutated")  # a worker mutating its (pickled) copy must not reach the caller
        seen["cfg"] = cfg
        logging.getLogger().setLevel(level)  # as _init_worker does

    def work(x):
        if x == "boom":
            raise ValueError("worker crash")
        return x * 2

    root = logging.getLogger()
    before = root.level
    handler = signal.getsignal(signal.SIGALRM) if hasattr(signal, "SIGALRM") else None
    try:
        root.setLevel(logging.INFO)
        with galaxyscope._InlineExecutor(init, (config, logging.WARNING)) as ex:
            if handler is not None:
                signal.signal(signal.SIGALRM, galaxyscope.execution_timeout_failsafe)  # as the ReDoS fuse does
            futures = {ex.submit(work, 21): "ok", ex.submit(work, "boom"): "crash"}
            done = {futures[f]: f for f in concurrent.futures.as_completed(futures)}
            assert done["ok"].result() == 42
            with pytest.raises(ValueError, match="worker crash"):
                done["crash"].result()
            assert root.level == logging.WARNING
        assert root.level == logging.INFO  # the worker's log level does not outlive the pass
        assert config == {"k": []} and seen["cfg"] == {"k": ["mutated"]}
        if handler is not None:
            assert signal.getsignal(signal.SIGALRM) == handler  # nor does the ReDoS fuse's handler
    finally:
        root.setLevel(before)


def test_a_scan_off_the_main_thread_keeps_the_pool():
    """The ReDoS fuse needs the main thread (signal.signal), so a scan run from another thread
    does not take the in-process path."""
    assert galaxyscope._can_run_inline()
    with concurrent.futures.ThreadPoolExecutor(1) as ex:
        assert ex.submit(galaxyscope._can_run_inline).result() is False
