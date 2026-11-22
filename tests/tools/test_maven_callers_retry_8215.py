# ruff: noqa: S101
"""#8215: a tool that runs Maven against the network goes through `maven_exe.run_maven_retrying_resolution`, so one
Central miss or a cached `.lastUpdated` miss earns the `-U` rerun (#7561, #8216) instead of failing the whole shard.

A file that builds a Maven argv (`mvn_executable(`) either calls the wrapper or is listed here with its reason."""

from __future__ import annotations

from pathlib import Path

TOOLS = Path(__file__).resolve().parent
WRAPPER = "run_maven_retrying_resolution"

# file -> why it does not need the retry. A new entry needs a reason a reviewer can check.
EXEMPT = {
    "maven_exe.py": "defines the wrapper",
    "det_survey.py": "`mvn -o compile` is offline; the classpath goal reads the already-built local repository",
    "mutation.py": "`mvn -o` is offline: nothing is fetched, so `-U` has nothing to ask again",
    "devin_port.py": "third-party port tooling, not a burned estate; its own `-Dmaven.repo.local` scratch repo",
    "thirdparty_port.py": "third-party port tooling, not a burned estate",
    "ibm_wca4z_port.py": "third-party port tooling, not a burned estate",
    "scip_callgraph.py": "scip-java call-graph reference with its own MAVEN_FLAGS 429 retry",
}


def _callers() -> list[Path]:
    return sorted(
        p
        for p in TOOLS.glob("*.py")
        if not p.name.startswith("test_") and "mvn_executable(" in p.read_text(encoding="utf-8")
    )


def test_every_online_maven_caller_uses_the_retry_wrapper():
    bare = [p.name for p in _callers() if p.name not in EXEMPT and WRAPPER not in p.read_text(encoding="utf-8")]
    assert not bare, f"run Maven through maven_exe.run_maven_retrying_resolution (or list with a reason): {bare}"


def test_the_burned_estate_builders_call_the_wrapper():
    for name in ("equivalence_java.py", "cics_crucible.py", "java_target_matrix.py"):
        assert WRAPPER in (TOOLS / name).read_text(encoding="utf-8"), name


def test_the_exemptions_are_not_stale():
    names = {p.name for p in _callers()} | {"maven_exe.py"}
    assert set(EXEMPT) <= names, sorted(set(EXEMPT) - names)
    for name in EXEMPT:
        if name != "maven_exe.py":
            assert WRAPPER not in (TOOLS / name).read_text(encoding="utf-8"), f"{name} uses the wrapper: drop its entry"
