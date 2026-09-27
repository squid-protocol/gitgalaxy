"""
Every gate a GitGalaxy PR meets in CI, run locally in one command -- so a PR does not learn about a
lint rule, a secret-scanner hit or a golden-master drift from CI, one push at a time.

    python tests/tools/pr_gates.py                  # all gates (~15 min)
    python tests/tools/pr_gates.py --fast           # skip the golden masters and the full suite
    python tests/tools/pr_gates.py --only lint audits gauntlet
    python tests/tools/pr_gates.py --lower-baseline # also rewrite the gauntlet baseline when cells now pass
    python tests/tools/pr_gates.py --e2e            # add the equivalence proofs (Docker GnuCOBOL + JDK 17)

The environment the gates need is set up here, not remembered: the corpora beside the main checkout
(KEYWORD_ROSETTA_PATH, LANGUAGE_CRUCIBLE_PATH, GITGALAXY_MAINFRAME_CORPORA), the interpreter's bin on
PATH (the audits call `ruff` / `mypy` by name), the community licence key (no 5 s delay), and a JDK 17
for --e2e. Run it from the worktree to check, with the project's venv python.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="+", help="run only these gates")
    ap.add_argument("--fast", action="store_true", help="skip the golden masters and the full suite")
    ap.add_argument("--lower-baseline", action="store_true", help="rewrite the gauntlet baseline after the check")
    ap.add_argument("--e2e", action="store_true", help="the full suite also runs the equivalence proofs")
    args = ap.parse_args()
    env = environment(args.e2e)
    plan = gates(args, env)
    chosen = args.only or [g for g in plan if not (args.fast and g in ("golden", "suite"))]
    unknown = sorted(set(chosen) - set(plan))
    if unknown:
        ap.error(f"unknown gate(s) {unknown}; gates are {list(plan)}")
    results: list[tuple[str, bool, float]] = []
    for name in chosen:
        t0, ok, tail = time.time(), True, ""
        for cmd in plan[name]:
            proc = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True, check=False)  # noqa: S603
            if proc.returncode != 0:
                ok, tail = False, "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-25:])
                break
        results.append((name, ok, time.time() - t0))
        print(f"{'PASS' if ok else 'FAIL'}  {name:<9} {time.time() - t0:6.0f}s", flush=True)
        if not ok:
            print("      " + tail.replace("\n", "\n      "), flush=True)
    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} gates pass" + (f"; failing: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
