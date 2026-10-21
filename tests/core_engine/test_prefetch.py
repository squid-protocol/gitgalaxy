"""#3189: the cold-storage page-cache prefetch warms only; it gates, caps and stops cleanly."""

import os
import time

import pytest

from gitgalaxy.core import prefetch as pf


def _files(tmp_path, names, size=10):
    out = []
    for n in names:
        p = tmp_path / n
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * size)
        out.append((str(p), size))
    return out


def _wait(handle):
    t = handle._thread
    if t is not None:
        t.join(timeout=5)


@pytest.mark.parametrize(
    ("mode", "n", "total", "rot", "reason"),
    [
        ("0", 10**6, 10**12, True, "disabled"),
        ("off", 10**6, 10**12, True, "disabled"),
        ("auto", 0, 0, True, "no files"),
        ("1", 0, 0, True, "no files"),
        ("auto", 10, 10, True, "small scan"),
        ("auto", pf.PREFETCH_MIN_FILES, 10, True, "small scan"),
        ("auto", 10, pf.PREFETCH_MIN_BYTES, True, "small scan"),
        ("auto", pf.PREFETCH_MIN_FILES, pf.PREFETCH_MIN_BYTES, False, "non-rotational"),
        ("auto", pf.PREFETCH_MIN_FILES, pf.PREFETCH_MIN_BYTES, True, None),
        ("auto", pf.PREFETCH_MIN_FILES, pf.PREFETCH_MIN_BYTES, None, None),  # unknown device: run
        ("1", 1, 1, False, None),  # forced on skips the size and device gates
    ],
)
def test_decide(mode, n, total, rot, reason):
    got = pf.decide(mode, n, total, lambda: rot)
    if reason is None:
        assert got is None
    else:
        assert reason in got


def test_small_scan_is_inert(tmp_path):
    h = pf.start_prefetch(str(tmp_path), _files(tmp_path, ["a", "b"]), environ={})
    assert h.skipped and h._thread is None
    h.stop()  # idempotent on an inert handle
    h.stop()


def test_forced_run_visits_every_file_including_unreadable_and_non_ascii(tmp_path):
    entries = _files(tmp_path, ["z.py", "a/b.py", "café/x.py"], size=100)
    entries.append((str(tmp_path / "missing.py"), 5))  # phantom
    entries.append((str(tmp_path), 0))  # a directory
    h = pf.start_prefetch(str(tmp_path), entries, environ={pf.PREFETCH_ENV: "1"})
    _wait(h)
    h.stop()
    assert h.files == 3
    assert h.bytes == 300


def test_path_order(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(pf.Prefetcher, "_warm", lambda self, p: seen.append(p) or 1)
    entries = _files(tmp_path, ["c", "a", "b"], size=1)
    h = pf.start_prefetch(str(tmp_path), entries, environ={pf.PREFETCH_ENV: "1"})
    _wait(h)
    assert seen == sorted(seen)
    assert len(seen) == 3


def test_read_fallback_without_fadvise(tmp_path, monkeypatch):
    monkeypatch.delattr(os, "posix_fadvise", raising=False)
    entries = _files(tmp_path, ["a", "b"], size=3_000_000)  # more than one read chunk
    h = pf.start_prefetch(str(tmp_path), entries, environ={pf.PREFETCH_ENV: "1"})
    _wait(h)
    assert (h.files, h.bytes) == (2, 6_000_000)


def test_read_fallback_when_fadvise_exists_without_its_constant(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(os, "posix_fadvise", lambda *a: calls.append(a), raising=False)
    monkeypatch.delattr(os, "POSIX_FADV_WILLNEED", raising=False)  # absent on macOS and Windows
    entries = _files(tmp_path, ["a", "b"], size=3_000_000)
    h = pf.start_prefetch(str(tmp_path), entries, environ={pf.PREFETCH_ENV: "1"})
    _wait(h)
    assert calls == []
    assert (h.files, h.bytes) == (2, 6_000_000)


def test_memory_cap_stops_the_thread(tmp_path):
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemTotal: 1 kB\nMemAvailable:       1 kB\n")  # cap = ~716 bytes
    entries = _files(tmp_path, ["a", "b", "c"], size=500)
    h = pf.start_prefetch(str(tmp_path), entries, environ={pf.PREFETCH_ENV: "1"}, meminfo=str(meminfo))
    _wait(h)
    assert h.files == 1


def test_mem_available_parsing(tmp_path):
    f = tmp_path / "m"
    f.write_text("MemAvailable:   2048 kB\n")
    assert pf.mem_available_bytes(str(f)) == 2048 * 1024
    assert pf.mem_available_bytes(str(tmp_path / "nope")) is None
    f.write_text("MemAvailable: garbage kB\n")
    assert pf.mem_available_bytes(str(f)) is None


def test_lead_window_waits_for_the_pool_and_stop_is_prompt(tmp_path, monkeypatch):
    monkeypatch.setattr(pf, "PREFETCH_LEAD_BYTES", 10)
    entries = _files(tmp_path, ["a", "b", "c"], size=100)
    h = pf.start_prefetch(str(tmp_path), entries, environ={pf.PREFETCH_ENV: "1"})
    time.sleep(0.3)
    assert h.files == 1  # parked: the pool has consumed nothing
    t0 = time.monotonic()
    h.stop()
    assert time.monotonic() - t0 < 2
    assert not any(t.name == "gg-prefetch" and t.is_alive() for t in __import__("threading").enumerate())
    h2 = pf.start_prefetch(str(tmp_path), entries, environ={pf.PREFETCH_ENV: "1"})
    for _ in range(3):
        h2.note_done(100)
        time.sleep(0.1)
    _wait(h2)
    assert h2.files == 3


def test_env_is_read_at_call_time(tmp_path, monkeypatch):
    entries = _files(tmp_path, ["a"], size=1)
    monkeypatch.setenv(pf.PREFETCH_ENV, "0")
    assert pf.start_prefetch(str(tmp_path), entries).skipped
    monkeypatch.setenv(pf.PREFETCH_ENV, "1")
    h = pf.start_prefetch(str(tmp_path), entries)
    _wait(h)
    assert h.skipped is None and h.files == 1


@pytest.mark.skipif(not hasattr(os, "major"), reason="os.major/os.minor do not exist on Windows (#5367)")
def test_is_rotational_reads_the_flag(tmp_path):
    dev = os.stat(tmp_path).st_dev
    q = tmp_path / f"{os.major(dev)}:{os.minor(dev)}" / "queue"
    q.mkdir(parents=True)
    (q / "rotational").write_text("1\n")
    assert pf.is_rotational(str(tmp_path), sys_block=str(tmp_path)) is True
    (q / "rotational").write_text("0\n")
    assert pf.is_rotational(str(tmp_path), sys_block=str(tmp_path)) is False
    assert pf.is_rotational(str(tmp_path / "gone"), sys_block=str(tmp_path)) is None


def test_scan_output_is_identical_with_and_without_prefetch(tmp_path):
    """A forced prefetch over a pool-sized scan changes no row of the master DB."""
    import sqlite3
    import subprocess
    import sys

    estate = tmp_path / "estate"
    estate.mkdir()
    for i in range(24):  # above _INLINE_MAX_FILES, so the pool (and the hook) runs
        (estate / f"m{i}.py").write_text(f"import os\n\n\ndef f{i}(x):\n    if x:\n        return os.getcwd()\n")

    def facts(mode):
        env = {k: v for k, v in os.environ.items() if k != "GALAXYSCOPE_MAX_WORKERS"}
        env.update(GITGALAXY_LICENSE_KEY="COMMUNITY_FREE_TIER", GITGALAXY_DISABLE_GIT_HISTORY="1")
        env["GALAXYSCOPE_MAX_WORKERS"] = "2"
        env[pf.PREFETCH_ENV] = mode
        out = tmp_path / f"out{mode}"
        subprocess.run(
            [sys.executable, "-m", "gitgalaxy.galaxyscope", str(estate), "--db-only", "--output", str(out)],
            check=True,
            env=env,
            capture_output=True,
        )
        (db,) = out.glob("*_galaxy_master.db")
        con = sqlite3.connect(db)
        res = {}
        for (table,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"):
            cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
            keep = [c for c in cols if not any(t in c.lower() for t in ("time", "speed", "timestamp", "duration"))]
            if keep:
                sel = ", ".join(f'"{c}"' for c in keep)
                res[table] = sorted(map(repr, con.execute(f"SELECT {sel} FROM {table}")))
        return res

    assert facts("0") == facts("1")
