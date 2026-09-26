#!/usr/bin/env python3
"""
One command for the local gates a Java-conversion / mainframe PR needs (#3654).

    python tests/tools/preflight.py [--java] [--only NAME ...] [--fail-fast]

Runs, in order, and prints one PASS / FAIL / SKIP table (exit 1 on any FAIL):
  ruff-format          ruff format --check on the .py files changed vs origin/main
  ruff-audit           tests/ruff_audit.py --ci
  mypy-audit           tests/mypy_audit.py --ci
  dead-key-audit       tests/dead_key_audit.py --ci
  xray                 the X-Ray Inspector (binary_anomaly_detector: dense literals, disguised binaries)
  field-testing        tests/tools/field_testing.py check
  refraction-snapshot  tests/tools/refraction_snapshot.py check
  with --java:
  java-carddemo        java_target_matrix.py --scan on CardDemo (default, plain-records, gradle-plain-21)
  java-cics-genapp     java_target_matrix.py --scan on GENAPP (default)

The Java gates need JDK_17 / JDK_21 (or scripts/setup_java_toolchain.sh's .tools/)
and the pinned corpora ($GITGALAXY_MAINFRAME_CORPORA, see mainframe_corpus.py); they
SKIP with the reason when either is missing. Works from any directory.
"""

from __future__ import annotations

import argparse
import dataclasses
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
TAIL_LINES = 15


class SkipGate(Exception):
    """A gate that cannot run here, with the reason."""


@dataclasses.dataclass
class GateContext:
    python_exe: str
    changed_py_files: list[str]
    corpora_root: Optional[Path]


@dataclasses.dataclass
class Gate:
    name: str
    command: Callable[[GateContext], list[str]]
    requires_java: bool = False


@dataclasses.dataclass
class Result:
    name: str
    status: str  # PASS | FAIL | SKIP
    seconds: Optional[float] = None
    reason: str = ""
    tail: list[str] = dataclasses.field(default_factory=list)


def _git(*args: str) -> list[str]:
    out = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False)  # noqa: S603, S607
    return out.stdout.splitlines() if out.returncode == 0 else []


def changed_py_files() -> list[str]:
    """Repo-relative .py files this branch changes vs origin/main: committed, uncommitted and untracked."""
    files = set(_git("diff", "--name-only", "--diff-filter=d", "origin/main...HEAD"))
    files |= set(_git("diff", "--name-only", "--diff-filter=d", "HEAD"))
    files |= set(_git("ls-files", "--others", "--exclude-standard"))
    return sorted(f for f in files if f.endswith(".py") and (REPO_ROOT / f).is_file())


def corpora_root() -> Optional[Path]:
    env = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    for candidate in ([Path(env)] if env else []) + [REPO_ROOT / ".mainframe_corpora"]:
        if candidate.is_dir():
            return candidate
    return None


def java_env() -> tuple[Optional[dict[str, str]], str]:
    """The environment the Java gates need, or (None, why not)."""
    env = dict(os.environ)
    tools = REPO_ROOT / ".tools"
    for version in ("17", "21"):
        key = f"JDK_{version}"
        if not env.get(key):
            local = tools / f"jdk-{version}"
            if not (local / "bin" / "javac").exists():
                return (
                    None,
                    f"{key} is not set and .tools/jdk-{version} is not installed (scripts/setup_java_toolchain.sh)",
                )
            env[key] = str(local)
    env["JAVA_HOME"] = env["JDK_17"]
    gradle = tools / "gradle-8.10.2" / "bin"
    if gradle.is_dir():
        env["PATH"] = f"{gradle}{os.pathsep}{env.get('PATH', '')}"
    return env, ""


def _ruff_format(ctx: GateContext) -> list[str]:
    if not ctx.changed_py_files:
        raise SkipGate("no .py files changed vs origin/main")
    return [ctx.python_exe, "-m", "ruff", "format", "--check", *ctx.changed_py_files]


def _matrix(corpus: str, configs: list[str]) -> Callable[[GateContext], list[str]]:
    def command(ctx: GateContext) -> list[str]:
        if ctx.corpora_root is None or not (ctx.corpora_root / corpus).is_dir():
            raise SkipGate(f"corpus {corpus} not found (set GITGALAXY_MAINFRAME_CORPORA)")
        return [ctx.python_exe, "tests/tools/java_target_matrix.py", str(ctx.corpora_root / corpus), "--scan",
                "--only", *configs]  # fmt: skip

    return command


GATES = [
    Gate("ruff-format", _ruff_format),
    Gate("ruff-audit", lambda ctx: [ctx.python_exe, "tests/ruff_audit.py", "--ci"]),
    Gate("mypy-audit", lambda ctx: [ctx.python_exe, "tests/mypy_audit.py", "--ci"]),
    Gate("dead-key-audit", lambda ctx: [ctx.python_exe, "tests/dead_key_audit.py", "--ci"]),
    Gate(
        "xray", lambda ctx: [ctx.python_exe, "-m", "gitgalaxy.tools.supply_chain_security.binary_anomaly_detector", "."]
    ),
    Gate("field-testing", lambda ctx: [ctx.python_exe, "tests/tools/field_testing.py", "check"]),
    Gate("refraction-snapshot", lambda ctx: [ctx.python_exe, "tests/tools/refraction_snapshot.py", "check"]),
    Gate(
        "java-carddemo",
        _matrix(
            "aws-mainframe-modernization-carddemo",
            ["default", "plain-records", "gradle-plain-21", "ui-thymeleaf", "messaging-jms"],
        ),
        requires_java=True,
    ),  # fmt: skip
    Gate("java-cics-genapp", _matrix("cics-genapp", ["default"]), requires_java=True),
]


def render(results: list[Result]) -> str:
    """The summary table, then the output tail of each failed gate."""
    lines = ["", f"{'gate':<22} {'result':<7} {'time':>7}  note", "-" * 72]
    for r in results:
        secs = f"{r.seconds:.1f}s" if r.seconds is not None else "-"
        lines.append(f"{r.name:<22} {r.status:<7} {secs:>7}  {r.reason}".rstrip())
    for r in results:
        if r.status == "FAIL" and r.tail:
            lines += ["", f"--- {r.name}: last {len(r.tail)} lines ---", *r.tail]
    return "\n".join(lines)


def run_gate(gate: Gate, ctx: GateContext, env: dict[str, str]) -> Result:
    try:
        cmd = gate.command(ctx)
    except SkipGate as e:
        return Result(gate.name, "SKIP", reason=str(e))
    start = time.monotonic()
    proc = subprocess.run(cmd, cwd=REPO_ROOT, env=env, capture_output=True, text=True, check=False)  # noqa: S603
    seconds = time.monotonic() - start
    if proc.returncode == 0:
        return Result(gate.name, "PASS", seconds)
    tail = (proc.stdout + proc.stderr).splitlines()[-TAIL_LINES:]
    return Result(gate.name, "FAIL", seconds, reason=f"exit {proc.returncode}", tail=tail)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--java", action="store_true", help="also compile the generated Java (needs a JDK)")
    ap.add_argument("--only", nargs="+", metavar="NAME", help="only the gates whose names start with NAME")
    ap.add_argument("--fail-fast", action="store_true", help="stop at the first failure")
    args = ap.parse_args(argv)

    ctx = GateContext(sys.executable, changed_py_files(), corpora_root())
    base_env = dict(os.environ, PYTHONPATH=str(REPO_ROOT))
    base_env["PATH"] = f"{Path(sys.executable).parent}{os.pathsep}{base_env.get('PATH', '')}"
    jenv, why = java_env() if args.java else (None, "")

    results: list[Result] = []
    for gate in GATES:
        if args.only and not any(gate.name.startswith(o) for o in args.only):
            continue
        if gate.requires_java and not args.java:
            continue
        if gate.requires_java and jenv is None:
            results.append(Result(gate.name, "SKIP", reason=why))
            continue
        print(f"running {gate.name} ...", flush=True)
        env = dict(base_env)
        if gate.requires_java and jenv is not None:
            env.update({k: jenv[k] for k in ("JDK_17", "JDK_21", "JAVA_HOME", "PATH")})
        results.append(run_gate(gate, ctx, env))
        if args.fail_fast and results[-1].status == "FAIL":
            break
    print(render(results))
    return 1 if any(r.status == "FAIL" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
