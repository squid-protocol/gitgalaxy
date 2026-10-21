"""Sequential page-cache prefetch for cold-storage scans (#3189).

The extraction pool dispatches largest-first (#3175) and reads concurrently, so on a cold
spinning disk every file costs a seek (illumos-gate: 11.4 ms/file, 425 s in `2_Disk_IO`). One
background thread streams the scan's files in path order into the page cache ahead of the
pool. It only warms the cache: nothing it reads reaches the scan, so output cannot change.

Gating (all decided at call time, never at import):
  * GITGALAXY_PREFETCH=0 disables, =1 forces it on (skips only the size gate's device probe),
    unset/`auto` runs it only for a big scan on a device not known to be non-rotational.
  * a small corpus (few files or few bytes) is skipped: it is warm or cheap anyway.
  * the thread stops at PREFETCH_MEM_FRACTION of MemAvailable and never runs more than
    PREFETCH_LEAD_BYTES ahead of the pool, so it cannot evict pages the workers still need.
Every OS error is swallowed; the thread is a daemon and `stop()` ends it promptly.
"""

import logging
import os
import stat
import threading
from collections.abc import Callable, Iterable
from typing import Any

from gitgalaxy.core.source_text import decode_bytes

logger = logging.getLogger(__name__)

PREFETCH_ENV = "GITGALAXY_PREFETCH"
PREFETCH_MIN_FILES = 500
PREFETCH_MIN_BYTES = 64 * 1024 * 1024
PREFETCH_MEM_FRACTION = 0.70
PREFETCH_FALLBACK_CAP_BYTES = 1024 * 1024 * 1024  # where MemAvailable is unreadable (not Linux)
PREFETCH_LEAD_BYTES = 512 * 1024 * 1024
_READ_CHUNK = 1024 * 1024
_POLL_S = 0.05


def mem_available_bytes(meminfo: str = "/proc/meminfo") -> int | None:
    """MemAvailable in bytes, or None where it cannot be read."""
    try:
        with open(meminfo, "rb") as fh:
            text = decode_bytes(fh.read())
        for line in text.splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return None


def is_rotational(root: str, sys_block: str = "/sys/dev/block") -> bool | None:
    """True/False from the device's queue/rotational flag, None when unknown."""
    try:
        dev = os.stat(root).st_dev
        base = os.path.join(sys_block, f"{os.major(dev)}:{os.minor(dev)}")
        # A partition has no queue/ of its own; the flag lives on the parent disk.
        for candidate in (os.path.join(base, "queue", "rotational"), os.path.join(base, "..", "queue", "rotational")):
            if os.path.isfile(candidate):
                with open(candidate, "rb") as fh:
                    return decode_bytes(fh.read()).strip() == "1"
    except (OSError, AttributeError, ValueError):
        pass
    return None


def decide(
    mode: str,
    n_files: int,
    total_bytes: int,
    rotational: Callable[[], bool | None],
) -> str | None:
    """Return None to run, else the skip reason."""
    mode = (mode or "auto").strip().lower()
    if mode in ("0", "off", "false", "no"):
        return "disabled by GITGALAXY_PREFETCH"
    if n_files == 0:
        return "no files"
    if mode in ("1", "on", "true", "yes", "force"):
        return None
    if n_files < PREFETCH_MIN_FILES or total_bytes < PREFETCH_MIN_BYTES:
        return "small scan"
    if rotational() is False:
        return "non-rotational device"
    return None


class Prefetcher:
    """Handle for the running (or skipped) prefetch thread; usable as a context manager."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self.consumed = 0  # bytes the pool has completed (advances the lead window)
        self.files = 0
        self.bytes = 0
        self.skipped: str | None = None

    def note_done(self, nbytes: int) -> None:
        with self._lock:
            self.consumed += nbytes

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        if self._thread is not None:
            logger.info(f"PREFETCH: warmed {self.files} files / {self.bytes} bytes ahead of the pool.")
            self._thread = None

    def __enter__(self) -> "Prefetcher":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.stop()

    def _warm(self, path: str) -> int:
        try:
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0))
        except OSError:
            return 0
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode):  # a directory, FIFO or device is not source
                return 0
            size = st.st_size
            fadvise = getattr(os, "posix_fadvise", None)
            willneed = getattr(os, "POSIX_FADV_WILLNEED", None)
            if fadvise is not None and willneed is not None:
                try:
                    fadvise(fd, 0, 0, willneed)
                    return size
                except OSError:
                    pass
            done = 0
            while not self._stop.is_set():
                chunk = os.read(fd, _READ_CHUNK)
                if not chunk:
                    break
                done += len(chunk)
            return done
        except OSError:
            return 0
        finally:
            os.close(fd)

    def _run(self, ordered: list[tuple[str, int]], cap: int) -> None:
        issued = 0
        try:
            for path, size in ordered:
                if self._stop.is_set() or self.bytes + size > cap:
                    break
                # Stay within the lead window of what the pool has finished with.
                while not self._stop.is_set() and issued - self.consumed > PREFETCH_LEAD_BYTES:
                    self._stop.wait(_POLL_S)
                if self._stop.is_set():
                    break
                got = self._warm(path)
                issued += size
                if got:
                    self.files += 1
                    self.bytes += got
        except Exception as exc:  # a warming failure must never reach the scan
            logger.debug(f"PREFETCH: stopped on {exc!r}")


def start_prefetch(
    root: str,
    entries: Iterable[tuple[str, int]],
    environ: "os._Environ[str] | dict[str, str] | None" = None,
    meminfo: str = "/proc/meminfo",
) -> Prefetcher:
    """Start the prefetch thread over (absolute path, size) entries, or return an inert handle."""
    env = os.environ if environ is None else environ
    handle = Prefetcher()
    ordered = sorted(entries, key=lambda e: e[0])
    total = sum(size for _, size in ordered)
    reason = decide(env.get(PREFETCH_ENV, "auto"), len(ordered), total, lambda: is_rotational(root))
    if reason is not None:
        handle.skipped = reason
        logger.debug(f"PREFETCH: skipped ({reason}).")
        return handle
    avail = mem_available_bytes(meminfo)
    cap = int(avail * PREFETCH_MEM_FRACTION) if avail is not None else PREFETCH_FALLBACK_CAP_BYTES
    thread = threading.Thread(target=handle._run, args=(ordered, cap), name="gg-prefetch", daemon=True)
    handle._thread = thread
    thread.start()
    return handle
