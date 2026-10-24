#!/usr/bin/env python3
"""Whether a pull request needs the Python audits (the plan step of ruff-audit.yml, mypy-audit.yml, small-audits.yml, gitgalaxy.yml, #6278).

    python tests/tools/audit_skip_plan.py --profile lint|small|gate [--event pull_request] [--base origin/main]
                                          [--files FILE ...] [--labels a,b] [--github-output PATH]

The three audits are required (or share a slot with one), so their workflows cannot take a path filter: they always
start, report, and this step decides whether the install and the audit run (`none`) or not (`full`). Their jobs and steps
are gated on the output, never the workflow trigger, so a `none` PR still gets a green check.

`none` needs every changed file to be docs the profile provably does not read, by the classifier's area() AND an
extension that no audit lints, type-checks or loads as config:

* `lint` (ruff, mypy: they read .py / .pyi under the repo and pyproject.toml): `prose`, `test-read-doc`, `agent-config`.
* `small` (dead-key, ast-accuracy, signal-contract, golden-master guard: they read tests/, docs/signal_contracts.md and the
  whole engine): `prose` only, since a `test-read-doc` is what a test (these audits are tests/*.py) may open.

* `gate` (gitgalaxy.yml's pre-gate: Vault Sentinel, X-Ray, Supply Chain Firewall scan code and manifests): the `lint`
  areas. The workflow used to ignore `docs/**` altogether; it now asks this plan instead, so prose outside docs/ skips too.

Anything else, a `.py` / `.pyi` / `.toml` / `.json` / `.txt` / `.yml` / `.sh` file even under docs or .claude, a rename from
such a file, the `shepherd:full` label, an unreadable or empty diff, and every event that is not a pull_request is `full`.
Prints JSON {mode, reason}; with --github-output appends mode=none|full. Stdlib only: it runs before anything is installed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import change_classifier  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
FULL_LABEL = "shepherd:full"
PROFILES = {
    "lint": ("prose", "test-read-doc", "agent-config"),
    "small": ("prose",),
    "gate": ("prose", "test-read-doc", "agent-config"),
}
# a file the audits could read as code or config, wherever it sits (docs/x.py, .claude/hooks/y.sh ...)
CODE_SUFFIXES = (".py", ".pyi", ".toml", ".json", ".jsonl", ".txt", ".yml", ".yaml", ".cfg", ".ini", ".sh", ".ipynb")


def plan(files: list[str], event: str, profile: str, labels: tuple[str, ...] = (), refs: dict | None = None) -> dict:
    full = {"mode": "full"}
    if event != "pull_request":
        return {**full, "reason": f"{event}: always the full audit"}
    if FULL_LABEL in labels:
        return {**full, "reason": f"label {FULL_LABEL}"}
    if not files:
        return {**full, "reason": "no changed files found (the diff is unreadable or empty)"}
    refs = change_classifier.load() if refs is None else refs
    allowed = PROFILES[profile]
    reach = sorted(f for f in files if f.lower().endswith(CODE_SUFFIXES) or change_classifier.area(f, refs) not in allowed)
    if reach:
        return {**full, "reason": f"{len(reach)} changed file(s) can reach the {profile} audits, first: {reach[0]}"}
    return {"mode": "none", "reason": f"every changed file is {'/'.join(allowed)} no {profile} audit reads"}


def changed_files(base: str) -> list[str]:
    proc = subprocess.run(["git", "diff", "--name-only", f"{base}...HEAD"], cwd=REPO_ROOT,  # noqa: S603, S607
                          capture_output=True, text=True, check=False)  # fmt: skip
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git diff failed")
    return [ln for ln in proc.stdout.splitlines() if ln.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", choices=sorted(PROFILES), required=True)
    ap.add_argument("--event", default="pull_request")
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--files", nargs="*", help="the changed files, instead of git diff --name-only BASE...HEAD")
    ap.add_argument("--labels", default="", help="comma-separated PR labels")
    ap.add_argument("--github-output", type=Path, help="append mode=none|full for later steps")
    args = ap.parse_args()
    try:
        files = (
            args.files if args.files is not None else (changed_files(args.base) if args.event == "pull_request" else [])
        )
        p = plan(files, args.event, args.profile, tuple(x for x in args.labels.split(",") if x))
    except RuntimeError as e:  # cannot tell what changed: everything
        p = {"mode": "full", "reason": f"cannot diff ({e})"}
    print(json.dumps(p, indent=1))
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as fh:
            fh.write(f"mode={p['mode']}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
