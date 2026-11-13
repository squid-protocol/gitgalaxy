"""#4939: the one place a tests/tools caller learns what to run for Maven.

On Windows Maven ships as `mvn.cmd`; `subprocess` without `shell=True` does not apply PATHEXT, so a bare "mvn" is
not found. `shutil.which` does apply it, so resolve through here (never a literal "mvn" in a subprocess argv --
`test_maven_exe_4939.py` fails on one). The generic resolver is `launcher_exe` (#4969).
"""

from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Mapping
from typing import Any

from launcher_exe import launcher_executable


def mvn_executable(env: Mapping[str, str] | None = None) -> str:
    """The Maven launcher on `env`'s PATH (default: the process's), `mvn.cmd` on Windows; "mvn" when not found, so
    the caller's own not-found error names what it looked for."""
    return launcher_executable("mvn", env)


# #5161: the JVMs Maven starts (Maven's own, surefire's fork) write in the locale charset unless told otherwise.
JVM_UTF8_FLAGS = "-Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8"
# #5882: a JVM that lives seconds (Maven's own, a test's run): C1 only and one GC thread. C2 never pays back in a run
# that short, and its threads take the cores the other parallel cases need (a det shard runs 4 on a 4-vCPU runner).
# The JIT tier changes speed only, not what a program computes (Java 17 floating point is strict at every tier).
JVM_SHORT_RUN_FLAGS = "-XX:TieredStopAtLevel=1 -XX:+UseSerialGC"


def maven_utf8_env(env: Mapping[str, str] | None = None) -> dict[str, str]:
    """A copy of `env` (default: the process's) whose `MAVEN_OPTS` makes Maven's own JVM write UTF-8 (and start like
    a short run, #5882); pair it with `encoding="utf-8"` on the subprocess call that captures the output."""
    out = dict(os.environ if env is None else env)
    out["MAVEN_OPTS"] = f"{out.get('MAVEN_OPTS', '')} {JVM_UTF8_FLAGS} {JVM_SHORT_RUN_FLAGS}".strip()
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


# #7561: a Central miss or a cached negative lookup is the network's answer, not the program's. Only these texts
# (never a compile or test failure) earn the one retry. The cached-miss text is Maven's own for a `.lastUpdated` hit
# ("... was not found in <repo> during a previous attempt. This failure was cached in the local repository and
# resolution is not reattempted ..."): it names no "Could not find artifact", so without its marker one miss on a
# shared local repository failed every later build of the job with no retry (det sweep run 42721961353: 30 of 30).
RESOLUTION_FAILURE_MARKERS = (
    "Could not find artifact",
    "Could not transfer artifact",
    "Connection reset",
    "Read timed out",
    "This failure was cached in the local repository",
    # #8373: an unresolvable parent / import POM (the Spring Boot parent when Central throttles the runner): 29 tests of
    # one shard failed on it; its text names the cause after "Non-resolvable", the rest of the report is boilerplate.
    "Non-resolvable parent POM",
    "Non-resolvable import POM",
    "UnresolvableModelException",
)
# #8373: waits (seconds) before the 2nd and 3rd attempt: a throttled Central needs time, an immediate rerun failed too.
RESOLUTION_RETRY_DELAYS_S = (5, 20)


def is_resolution_failure(text: str) -> bool:
    """True when Maven's output shows a dependency that could not be fetched (a miss on Central, a dropped transfer)."""
    return any(marker in text for marker in RESOLUTION_FAILURE_MARKERS)


def run_maven_retrying_resolution(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    """`run_decoded(cmd)`; on a non-zero exit whose output is a resolution failure, run it again with `-U` (which
    ignores a cached `.lastUpdated` miss), up to `len(RESOLUTION_RETRY_DELAYS_S)` more times, waiting before each
    (#8373). A compile error, a test failure or a timeout is returned as it is."""
    proc = run_decoded(cmd, **kwargs)
    log = ""
    for attempt, delay in enumerate(RESOLUTION_RETRY_DELAYS_S, start=2):
        if proc.returncode == 0 or not is_resolution_failure(proc.stdout + proc.stderr):
            break
        time.sleep(delay)
        again = run_decoded([cmd[0], "-U", *cmd[1:]], **kwargs)
        log += (
            proc.stdout
            + proc.stderr
            + f"\n[maven_exe #7561: dependency resolution failed; rerun with -U, attempt {attempt}]\n"
        )
        proc = subprocess.CompletedProcess(again.args, again.returncode, again.stdout, again.stderr)
    if not log:
        return proc
    return subprocess.CompletedProcess(proc.args, proc.returncode, log + proc.stdout, proc.stderr)
