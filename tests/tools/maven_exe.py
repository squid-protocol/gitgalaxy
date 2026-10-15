"""#4939: the one place a tests/tools caller learns what to run for Maven.

On Windows Maven ships as `mvn.cmd`; `subprocess` without `shell=True` does not apply PATHEXT, so a bare "mvn" is
not found. `shutil.which` does apply it, so resolve through here (never a literal "mvn" in a subprocess argv --
`test_maven_exe_4939.py` fails on one). The generic resolver is `launcher_exe` (#4969).
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from launcher_exe import launcher_executable


def mvn_executable(env: Mapping[str, str] | None = None) -> str:
    """The Maven launcher on `env`'s PATH (default: the process's), `mvn.cmd` on Windows; "mvn" when not found, so
    the caller's own not-found error names what it looked for."""
    return launcher_executable("mvn", env)


# #5161: the JVMs Maven starts (Maven's own, surefire's fork) write in the locale charset unless told otherwise.
JVM_UTF8_FLAGS = "-Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8"


def maven_utf8_env(env: Mapping[str, str] | None = None) -> dict[str, str]:
    """A copy of `env` (default: the process's) whose `MAVEN_OPTS` makes Maven's own JVM write UTF-8; pair it with
    `encoding="utf-8"` on the subprocess call that captures the output."""
    out = dict(os.environ if env is None else env)
    out["MAVEN_OPTS"] = f"{out.get('MAVEN_OPTS', '')} {JVM_UTF8_FLAGS}".strip()
    return out
