"""#4939: the one place a tests/tools caller learns what to run for Maven.

On Windows Maven ships as `mvn.cmd`; `subprocess` without `shell=True` does not apply PATHEXT, so a bare "mvn" is
not found. `shutil.which` does apply it, so resolve through here (never a literal "mvn" in a subprocess argv --
`test_maven_exe_4939.py` fails on one). The generic resolver is `launcher_exe` (#4969).
"""

from __future__ import annotations

from collections.abc import Mapping

from launcher_exe import launcher_executable


def mvn_executable(env: Mapping[str, str] | None = None) -> str:
    """The Maven launcher on `env`'s PATH (default: the process's), `mvn.cmd` on Windows; "mvn" when not found, so
    the caller's own not-found error names what it looked for."""
    return launcher_executable("mvn", env)
