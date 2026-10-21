"""#4939: the one place a tests/tools caller learns what to run for Maven.

On Windows Maven ships as `mvn.cmd`; `subprocess` without `shell=True` does not apply PATHEXT, so a bare "mvn" is
not found. `shutil.which` does apply it, so resolve through here (never a literal "mvn" in a subprocess argv --
`test_maven_exe_4939.py` fails on one). The generic resolver is `launcher_exe` (#4969).
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from typing import Any

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


# #5174: Gradle starts two JVMs, the client (`GRADLE_OPTS`) and the daemon (`org.gradle.jvmargs`, which replaces the
# daemon's default 512m heap, so the heap is restated).
GRADLE_DAEMON_ARG = f"-Dorg.gradle.jvmargs=-Xmx512m {JVM_UTF8_FLAGS}"


def gradle_utf8_env(env: Mapping[str, str] | None = None) -> dict[str, str]:
    """A copy of `env` (default: the process's) whose `GRADLE_OPTS` makes Gradle's client JVM write UTF-8; pair it with
    `GRADLE_DAEMON_ARG` in the argv (the daemon JVM) and `encoding="utf-8"` / `run_decoded` on the call."""
    out = dict(os.environ if env is None else env)
    out["GRADLE_OPTS"] = f"{out.get('GRADLE_OPTS', '')} {JVM_UTF8_FLAGS}".strip()
    return out


def decode_output(data: bytes | str | None) -> str:
    """Text for a captured subprocess stream (bytes, or the str a text-mode caller already has), decoded through
    `gitgalaxy.core.source_text` so no byte is lost to an `errors=` handler (#3813)."""
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    from gitgalaxy.core.source_text import decode_bytes

    return decode_bytes(data)


def run_decoded(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    """`subprocess.run(cmd, capture_output=True, **kwargs)` with stdout and stderr decoded by `decode_output`
    (byte capture, so neither the locale nor `errors="replace"` touches the output)."""
    proc = subprocess.run(cmd, capture_output=True, **kwargs)  # noqa: S603
    return subprocess.CompletedProcess(
        proc.args, proc.returncode, decode_output(proc.stdout), decode_output(proc.stderr)
    )
