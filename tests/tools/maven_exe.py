"""#4939: the one place a tests/tools caller learns what to run for Maven.

On Windows Maven ships as `mvn.cmd`; `subprocess` without `shell=True` does not apply PATHEXT, so a bare "mvn" is
not found. `shutil.which` does apply it, so resolve through here (never a literal "mvn" in a subprocess argv --
`test_maven_exe_4939.py` fails on one). A leaf module: it imports nothing from the harness.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Mapping


def mvn_executable(env: Mapping[str, str] | None = None) -> str:
    """The Maven launcher on `env`'s PATH (default: the process's), `mvn.cmd` on Windows; "mvn" when not found, so
    the caller's own not-found error names what it looked for."""
    path = (env if env is not None else os.environ).get("PATH")
    return shutil.which("mvn", path=path) or "mvn"
