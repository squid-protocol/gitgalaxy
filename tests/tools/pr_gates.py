"""
Every gate a GitGalaxy PR meets in CI, run locally in one command -- so a PR does not learn about a
lint rule, a secret-scanner hit or a golden-master drift from CI, one push at a time.

    python tests/tools/pr_gates.py                  # all gates (~15 min)
    python tests/tools/pr_gates.py --fast           # skip the golden masters and the full suite
    python tests/tools/pr_gates.py --only lint audits gauntlet
    python tests/tools/pr_gates.py --lower-baseline # also rewrite the gauntlet baseline when cells now pass
    python tests/tools/pr_gates.py --e2e            # add the equivalence proofs (Docker GnuCOBOL + JDK 17)
    python tests/tools/pr_gates.py --vs-main        # re-run each failing gate on a fresh origin/main worktree and
                                                    # label it "caused by branch" or "pre-existing on main@<sha>"

The environment the gates need is set up here, not remembered: the corpora beside the main checkout
(KEYWORD_ROSETTA_PATH, LANGUAGE_CRUCIBLE_PATH, GITGALAXY_MAINFRAME_CORPORA), the interpreter's bin on
PATH (the audits call `ruff` / `mypy` by name), the community licence key (no 5 s delay), and a JDK 17
for --e2e. Run it from the worktree to check, with the project's venv python.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = sys.executable


def _main_checkout() -> Path:
    """The main checkout (a worktree's corpora sit beside it, not beside the worktree)."""
    common = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--git-common-dir"],  # noqa: S603, S607
                            capture_output=True, text=True, check=False).stdout.strip()  # fmt: skip
    path = Path(common) if common else REPO / ".git"
    return (path if path.is_absolute() else REPO / path).resolve().parent


def environment(e2e: bool) -> dict[str, str]:
    env = dict(os.environ, PYTHONPATH=str(REPO), GITGALAXY_LICENSE_KEY="COMMUNITY_FREE_TIER")
    env["PATH"] = str(Path(PY).parent) + os.pathsep + env.get("PATH", "")
    main = _main_checkout()
    for var, path in (("KEYWORD_ROSETTA_PATH", main.parent / "keyword-rosetta"),
                      ("LANGUAGE_CRUCIBLE_PATH", main.parent / "language-crucible"),
                      ("GITGALAXY_MAINFRAME_CORPORA", main / ".mainframe_corpora")):  # fmt: skip
        if var not in env and path.is_dir():
            env[var] = str(path)
    if e2e:
        env["EQUIVALENCE_E2E"] = "1"
        if "JAVA_HOME" not in env:  # Maven needs a JDK that compiles release 17
            jdks = sorted(Path("/usr/lib/jvm").glob("java-17-openjdk*")) if Path("/usr/lib/jvm").is_dir() else []
            if jdks:
                env["JAVA_HOME"] = str(jdks[0])
    return env


def ci_pins(repo: Path = REPO) -> dict[str, str | None]:
    """What CI installs, read from the workflows: {'python','ruff','mypy'} -> version, or None if unpinned."""
    wf = repo / ".github" / "workflows"

    def read(name: str) -> str:
        try:
            return (wf / name).read_text(encoding="utf-8")
        except OSError:
            return ""

    ruff_yml, mypy_yml = read("ruff-audit.yml"), read("mypy-audit.yml")
    py = re.search(r"python-version:\s*[\"']?([\d.]+)", ruff_yml or mypy_yml)
    ruff = re.search(r"\bruff==([\w.]+)", ruff_yml)
    mypy = re.search(r"\bmypy==([\w.]+)", mypy_yml)
    return {"python": py and py.group(1), "ruff": ruff and ruff.group(1), "mypy": mypy and mypy.group(1)}


def local_versions(env: dict[str, str] | None = None) -> dict[str, str | None]:
    """Versions of the interpreter, ruff and mypy the gates will actually use (None if not installed)."""
    out: dict[str, str | None] = {"python": ".".join(map(str, sys.version_info[:3]))}
    for tool in ("ruff", "mypy"):
        try:
            txt = subprocess.run([tool, "--version"], capture_output=True, text=True, check=False, env=env).stdout  # noqa: S603
        except OSError:
            txt = ""
        m = re.search(r"(\d+\.\d+(?:\.\d+)?)", txt)
        out[tool] = m.group(1) if m else None
    return out


def version_warnings(pins: dict[str, str | None], local: dict[str, str | None]) -> list[str]:
    """Loud warnings (never a failure) where local tooling differs from what CI pins. python compares major.minor."""
    msgs = []
    for tool in ("python", "ruff", "mypy"):
        want, have = pins.get(tool), local.get(tool)
        if want is None:
            if tool == "mypy":
                msgs.append(
                    "mypy: CI installs it UNPINNED (latest on PyPI) -- a stale local mypy can pass what CI fails (#4257); keep it current."
                )
            continue
        if tool == "python":
            same = bool(have) and have.split(".")[:2] == want.split(".")[:2]
        else:
            same = have == want
        if not same:
            msgs.append(f"{tool}: local {have or 'MISSING'} != CI {want}")
    if any("!=" in m for m in msgs):
        pkgs = " ".join(f"{t}=={v}" if v else t for t, v in (("ruff", pins.get("ruff")), ("mypy", pins.get("mypy"))))
        py = pins.get("python") or "3.12"
        msgs.append(
            f"fix in a PRIVATE venv, never the shared one: python{py} -m venv /tmp/gitgalaxy-scratch/claude/ci-venv && "
            f"/tmp/gitgalaxy-scratch/claude/ci-venv/bin/pip install {pkgs} PyYAML && "
            f"PATH=/tmp/gitgalaxy-scratch/claude/ci-venv/bin:$PATH python tests/tools/pr_gates.py ..."
        )
    return msgs


def run_gate(cmds: list[list[str]], root: Path, env: dict[str, str]) -> tuple[bool, str]:
    """Runs one gate's commands in `root`; returns (ok, output tail of the first failure)."""
    for cmd in cmds:
        proc = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True, check=False)  # noqa: S603
        if proc.returncode != 0:
            return False, "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-25:])
    return True, ""


def attribute_failures(
    failed: list[str], plan_for: Callable[[Path], dict[str, list[list[str]]]], env: dict[str, str]
) -> dict[str, str]:
    """For each failing gate, re-run it on a fresh detached origin/main worktree: {gate: label}.

    `plan_for(root)` returns the gate plan with its cwd/paths for that root. Fetches first so "main" is
    current, not 10 minutes stale (#4220 round); the worktree is removed afterwards.
    """
    subprocess.run(["git", "-C", str(REPO), "fetch", "-q", "origin", "main"], check=False)  # noqa: S603, S607
    sha = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "origin/main"],  # noqa: S603, S607
                         capture_output=True, text=True, check=False).stdout.strip()  # fmt: skip
    tmp = Path(tempfile.mkdtemp(prefix="gg-vs-main-"))
    wt = tmp / "main"
    labels: dict[str, str] = {}
    try:
        subprocess.run(
            ["git", "-C", str(REPO), "worktree", "add", "-q", "--detach", str(wt), "origin/main"], check=True
        )  # noqa: S603, S607
        menv = dict(env, PYTHONPATH=str(wt))
        plan = plan_for(wt)
        for name in failed:
            ok, _ = run_gate(plan[name], wt, menv)
            labels[name] = f"pre-existing on main@{sha}" if not ok else "caused by branch"
    finally:
        subprocess.run(["git", "-C", str(REPO), "worktree", "remove", "--force", str(wt)], check=False)  # noqa: S603, S607
        shutil.rmtree(tmp, ignore_errors=True)
    return labels


def _tool(module: str) -> list[str]:
    return [PY, "-c", f"import sys; sys.argv = ['gate', '.']; from {module} import main; sys.exit(main())"]


def gates(args: argparse.Namespace, env: dict[str, str]) -> dict[str, list[list[str]]]:
    corpus = env.get("KEYWORD_ROSETTA_PATH")
    gauntlet = [PY, "tests/tools/unicode_gauntlet.py", "--ci", "--jobs", str(os.cpu_count() or 4)]
    gauntlet += ["--corpus", corpus] if corpus else []
    suite = [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"]
    return {
        "lint": [[PY, "tests/ruff_audit.py", "--ci"]],
        "audits": [[PY, "tests/mypy_audit.py", "--ci"]],
        "secrets": [_tool("gitgalaxy.tools.supply_chain_security.vault_sentinel")],
        "xray": [_tool("gitgalaxy.tools.supply_chain_security.binary_anomaly_detector")],
        "gauntlet": [gauntlet] + ([[*gauntlet[:2], "--update-baseline", *gauntlet[3:]]] if args.lower_baseline else []),
        "golden": [[PY, "tests/tools/crucible_check.py"]],
        "suite": [suite],
    }


def gates_at(root: Path, args: argparse.Namespace, env: dict[str, str]) -> dict[str, list[list[str]]]:
    """The gate plan is cwd-relative, so a plan for another checkout is the same plan run with cwd=root."""
    return gates(args, env)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="+", help="run only these gates")
    ap.add_argument("--fast", action="store_true", help="skip the golden masters and the full suite")
    ap.add_argument("--lower-baseline", action="store_true", help="rewrite the gauntlet baseline after the check")
    ap.add_argument(
        "--vs-main",
        action="store_true",
        help="label each failing gate caused-by-branch / pre-existing on a fresh origin/main",
    )
    ap.add_argument("--e2e", action="store_true", help="the full suite also runs the equivalence proofs")
    args = ap.parse_args()
    env = environment(args.e2e)
    plan = gates(args, env)
    chosen = args.only or [g for g in plan if not (args.fast and g in ("golden", "suite"))]
    unknown = sorted(set(chosen) - set(plan))
    if unknown:
        ap.error(f"unknown gate(s) {unknown}; gates are {list(plan)}")
    for msg in version_warnings(ci_pins(), local_versions(env)):
        print(f"WARNING  {msg}", flush=True)
    results: list[tuple[str, bool, float]] = []
    for name in chosen:
        t0, ok, tail = time.time(), True, ""
        ok, tail = run_gate(plan[name], REPO, env)
        results.append((name, ok, time.time() - t0))
        print(f"{'PASS' if ok else 'FAIL'}  {name:<9} {time.time() - t0:6.0f}s", flush=True)
        if not ok:
            print("      " + tail.replace("\n", "\n      "), flush=True)
    failed = [n for n, ok, _ in results if not ok]
    print(
        f"\n{len(results) - len(failed)}/{len(results)} gates pass"
        + (f"; failing: {', '.join(failed)}" if failed else "")
    )
    if failed and args.vs_main:
        print("\n--vs-main: re-running failing gates on a fresh origin/main worktree ...", flush=True)
        for name, label in attribute_failures(failed, lambda root: gates_at(root, args, env), env).items():
            print(f"  {name:<9} {label}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
