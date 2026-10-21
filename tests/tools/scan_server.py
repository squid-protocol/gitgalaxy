"""galaxy_ir.scan_to_db for tests, without importing the engine again for every scan.

    from scan_server import scan_to_db   # the same signature as gitgalaxy.tools.cobol_to_cobol.galaxy_ir.scan_to_db

A test's scan of a few files is ~0.2 s of work after ~1.3 s (~3.5 s on a CI runner) of importing gitgalaxy.galaxyscope
in a fresh interpreter. Here one server process per test process imports it once and forks a child for each scan; the
child runs the module as `python -m gitgalaxy.galaxyscope ARGV` does (runpy, `__main__`), with the caller's environment
and working directory, its output on the caller's stderr. Every child starts from the same just-imported state (the
server never scans), so one scan cannot leave anything behind for the next. The server is single-threaded: forking it is
safe where forking a pytest worker (xdist's threads) is not. No fork (Windows), GITGALAXY_SCAN_SERVER=0, or a server that
fails: galaxy_ir.scan_to_db itself.
"""

from __future__ import annotations

import atexit
import json
import os
import subprocess
import sys
import threading
from collections.abc import Sequence
from pathlib import Path

ENV = "GITGALAXY_SCAN_SERVER"
REPO_ROOT = Path(__file__).resolve().parents[2]

SERVER = r"""
import json, os, runpy, sys, traceback
import gitgalaxy.galaxyscope  # noqa: F401 -- the import every scan shares
out = os.fdopen(os.dup(1), "w")  # the protocol; the children's output goes to stderr
os.dup2(2, 1)
for line in sys.stdin:
    req = json.loads(line)
    pid = os.fork()
    if pid == 0:
        code = 1
        try:
            os.chdir(req["cwd"])
            os.environ.clear()
            os.environ.update(req["env"])
            sys.argv = ["galaxyscope", *req["args"]]
            runpy.run_module("gitgalaxy.galaxyscope", run_name="__main__", alter_sys=True)
            code = 0
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        except BaseException:
            traceback.print_exc()
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(code)
    _, status = os.waitpid(pid, 0)
    out.write(f"{os.waitstatus_to_exitcode(status)} {pid}\n")
    out.flush()
"""


class _Server:
    def __init__(self) -> None:
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(filter(None, [str(REPO_ROOT), os.environ.get("PYTHONPATH")])))
        self.proc = subprocess.Popen([sys.executable, "-c", SERVER], stdin=subprocess.PIPE, stdout=subprocess.PIPE,  # noqa: S603
                                     text=True, env=env, start_new_session=True)  # fmt: skip

    def scan(self, args: list[str], env: dict[str, str], timeout: float) -> int:
        assert self.proc.stdin is not None and self.proc.stdout is not None
        self.proc.stdin.write(json.dumps({"args": args, "env": env, "cwd": os.getcwd()}) + "\n")
        self.proc.stdin.flush()
        got: list[str] = []
        t = threading.Thread(target=lambda: got.append(self.proc.stdout.readline()), daemon=True)  # type: ignore[union-attr]
        t.start()
        t.join(timeout)
        if t.is_alive():  # the scan (the child) runs on: kill the server's group, child and all
            os.killpg(self.proc.pid, 9)
            raise subprocess.TimeoutExpired(["galaxyscope", *args], timeout)
        if not got or not got[0].strip():
            raise OSError("scan server ended")
        return int(got[0].split()[0])

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.stdin.close()  # type: ignore[union-attr]
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()


_SERVER: list[_Server] = []
_LOCK = threading.Lock()
_FAILED = [0]


def _close() -> None:
    for s in _SERVER:
        s.close()


atexit.register(_close)


def scan_to_db(target: Path, out_dir: Path, timeout: int = 3600, extra_args: Sequence[str] = ()) -> Path:
    """galaxy_ir.scan_to_db (the same argv, environment default and result), through the server."""
    from gitgalaxy.tools.cobol_to_cobol import galaxy_ir

    if not hasattr(os, "fork") or os.environ.get(ENV, "1") == "0" or _FAILED[0] >= 2:
        return galaxy_ir.scan_to_db(target, out_dir, timeout, extra_args)
    target = Path(target).resolve()
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.setdefault("GITGALAXY_DISABLE_GIT_HISTORY", "1")  # as galaxy_ir.scan_to_db
    args = [str(target), "--db-only", "--output", str(out_dir), *extra_args]
    with _LOCK:
        if not _SERVER or _SERVER[0].proc.poll() is not None:
            _SERVER[:] = [_Server()]
        try:
            rc = _SERVER[0].scan(args, env, timeout)
        except subprocess.TimeoutExpired:
            _SERVER.clear()
            raise
        except (OSError, ValueError):
            _SERVER.clear()
            _FAILED[0] += 1
            return galaxy_ir.scan_to_db(target, out_dir, timeout, extra_args)
    if rc != 0:
        raise subprocess.CalledProcessError(rc, [sys.executable, "-m", "gitgalaxy.galaxyscope", *args])
    db_path = out_dir / f"{target.name}_galaxy_master.db"
    if not db_path.is_file():
        raise FileNotFoundError(f"Scan finished but {db_path} was not written")
    return db_path
