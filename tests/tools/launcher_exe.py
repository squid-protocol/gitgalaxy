"""#4969: resolve a launcher that ships as a `.cmd` shim on Windows (npm, npx, yarn, mvn, ...) through `shutil.which`.

`subprocess` without `shell=True` does not apply PATHEXT, so a bare "npm" in an argv is not found on Windows;
`shutil.which` does apply it. Never put a literal launcher name in a subprocess argv (`test_maven_exe_4939.py` fails on
one). A leaf module: it imports nothing from the harness.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Mapping


def launcher_executable(name: str, env: Mapping[str, str] | None = None) -> str:
    """`name` resolved on `env`'s PATH (default: the process's), e.g. `npm.cmd` on Windows; the bare `name` when not
    found, so the caller's own not-found error names what it looked for."""
    path = (env if env is not None else os.environ).get("PATH")
    return shutil.which(name, path=path) or name


def npm_executable(env: Mapping[str, str] | None = None) -> str:
    """The npm launcher on `env`'s PATH (`npm.cmd` on Windows)."""
    return launcher_executable("npm", env)
