# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#4726: the readiness scanner's no-network guarantee, enforced rather than promised.

`install()` replaces the socket entry points a network call goes through (connect, connect_ex, sendto, sendmsg,
create_connection, getaddrinfo, gethostbyname[_ex]) with ones that raise `OfflineViolation` for any address family
but AF_UNIX (multiprocessing's local channels stay usable), except inside `socket.socketpair` itself, whose Windows
emulation connects over AF_INET loopback. It is installed in the assess process and, through
`BOOTSTRAP`, in the galaxyscope scan it runs; the scan's worker processes inherit it where they fork (Linux). A
spawn-start worker (macOS / Windows default) starts a fresh interpreter, so the scan passes `OFFLINE_ENV` to
`_init_worker`, which installs the guard there (#5235).
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

_LOCAL_FAMILIES = frozenset({getattr(socket, "AF_UNIX", None)} - {None})
_installed = False
_local = threading.local()

# Set in the scan child so galaxyscope's worker initializer installs the guard in spawn-start workers too.
OFFLINE_ENV = "GITGALAXY_ASSESS_OFFLINE"

# Runs galaxyscope's own __main__ with the guard installed first (the argv after `-c` is galaxyscope's).
BOOTSTRAP = (
    "import runpy, sys; from gitgalaxy.tools.readiness.offline import install; install(); "
    "sys.argv[0] = 'galaxyscope'; runpy.run_module('gitgalaxy.galaxyscope', run_name='__main__', alter_sys=True)"
)


class OfflineViolation(OSError):
    """A network call attempted while the readiness scanner runs."""


def _refuse(what: str) -> OfflineViolation:
    return OfflineViolation(f"gitgalaxy assess runs offline: {what} refused")


@contextmanager
def _allow_local() -> Iterator[None]:
    """Exempt this thread's socket calls for the duration: the stdlib's own loopback plumbing (Windows has no native
    `socketpair`; CPython builds one from an AF_INET listen + connect on 127.0.0.1)."""
    depth = getattr(_local, "depth", 0)
    _local.depth = depth + 1
    try:
        yield
    finally:
        _local.depth = depth


def install() -> None:
    """Refuse every non-local socket call in this process from now on. Idempotent."""
    global _installed
    if _installed:
        return
    cls = socket.socket

    def _wrap(name: str) -> None:
        original = getattr(cls, name, None)
        if original is None:
            return

        def guarded(self: socket.socket, *args: Any, **kwargs: Any) -> Any:
            if self.family not in _LOCAL_FAMILIES and not getattr(_local, "depth", 0):
                raise _refuse(f"socket.{name}")
            return original(self, *args, **kwargs)

        setattr(cls, name, guarded)

    for name in ("connect", "connect_ex", "sendto", "sendmsg"):
        _wrap(name)

    def _resolver(name: str) -> Any:
        def refused(*_args: Any, **_kwargs: Any) -> Any:
            raise _refuse(f"socket.{name}")

        return refused

    for name in ("create_connection", "getaddrinfo", "gethostbyname", "gethostbyname_ex", "gethostbyaddr"):
        setattr(socket, name, _resolver(name))

    original_pair = getattr(socket, "socketpair", None)
    if original_pair is not None:

        def socketpair(*args: Any, **kwargs: Any) -> Any:
            with _allow_local():
                return original_pair(*args, **kwargs)

        socket.socketpair = socketpair  # type: ignore[assignment]
    _installed = True


def installed() -> bool:
    return _installed


def guarded_scan(target: Path, out_dir: Path, timeout: int = 3600, verbose: bool = False) -> Path:
    """`galaxy_ir.scan_to_db`'s scan, offline and writing nothing into `target`: galaxyscope `--db-only` (which opens
    no dependency cache) with `--no-dependency-cache` as well, git history off, the guard installed in the child.
    Its console output is shown only with `verbose` or on failure (it is the local terminal, never the report)."""
    target = Path(target).resolve()
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, GITGALAXY_DISABLE_GIT_HISTORY="1", **{OFFLINE_ENV: "1"})
    argv = [
        sys.executable,
        "-c",
        BOOTSTRAP,
        str(target),
        "--db-only",
        "--no-dependency-cache",
        "--output",
        str(out_dir),
    ]
    res = subprocess.run(  # noqa: S603 -- this interpreter + a fixed bootstrap; target/out_dir are argv entries
        argv,
        env=env,
        timeout=timeout,
        check=False,
        stdout=None if verbose else subprocess.PIPE,
        stderr=subprocess.STDOUT if not verbose else None,
        text=True,
    )
    if res.returncode != 0:
        if res.stdout:
            sys.stderr.write(res.stdout[-4000:])
        raise RuntimeError(f"the estate scan failed (exit {res.returncode})")
    db_path = out_dir / f"{target.name}_galaxy_master.db"
    if not db_path.is_file():
        raise FileNotFoundError(f"Scan finished but {db_path.name} was not written")
    return db_path
