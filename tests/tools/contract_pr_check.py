#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""
The contract-PR gauntlet in one command (#2916).

From the current worktree, runs the legs a rule- or score-contract PR owes --
in parallel where they are independent -- and prints a PR-body block with the
four standard sections (Measured / Corpus / Golden masters / Tests) filled from
the tools' own output:

  1. extraction strict tests for the TOUCHED languages (`git diff --name-only`
     against origin/main, mapped language_standards/languages/<lang>.py ->
     tests/extraction/languages/test_<lang>_strict.py);
  2. `rosetta_audit.py --allow-regressions --corpus <kr-worktree>`;
  3. `crucible_check.py` (verification mode -- run your bless FIRST);
  4. `bless_scope.py --from-head <fixture> --summary` on both fixtures;
  5. `audit_check.py` (the baseline-gated audit battery).

Usage:
    PATH=<venv>/bin:$PATH python tests/tools/contract_pr_check.py --corpus <kr-worktree>
    python tests/tools/contract_pr_check.py --score --corpus ...   # adds no legs today;
        # --rules/--score label the PR-body header so the block says which contract
        # family the run certifies (score contracts add audit_score_inputs runs by hand).

Exit: nonzero if any leg failed; the PR-body block prints either way, with
failed legs marked, so a red run still yields the review artifact.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PY = sys.executable


def sh(cmd: list[str], timeout: int = 1800) -> tuple[int, str]:
    r = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr)


def touched_languages() -> list[str]:
    rc, out = sh(["git", "diff", "--name-only", "origin/main...HEAD"])
    if rc != 0:
        rc, out = sh(["git", "diff", "--name-only", "origin/main"])
    langs = set()
    for line in out.splitlines():
        p = Path(line.strip())
        if p.parent.as_posix().endswith("language_standards/languages") and p.suffix == ".py":
            langs.add(p.stem)
    return sorted(langs)


def leg_extraction(langs: list[str]) -> tuple[str, int, str]:
    tests = [
        f"tests/extraction/languages/test_{lang}_strict.py"
        for lang in langs
        if (REPO_ROOT / f"tests/extraction/languages/test_{lang}_strict.py").is_file()
    ]
    if not tests:
        return ("extraction (no touched languages)", 0, "skipped: git diff touched no language file")
    rc, out = sh([PY, "-m", "pytest", *tests, "-q", "-p", "no:cacheprovider"])
    tail = out.strip().splitlines()[-1] if out.strip() else ""
    return (f"extraction strict ({len(tests)} languages)", rc, tail)


def leg_rosetta(corpus: str | None) -> tuple[str, int, str]:
    cmd = [PY, "tests/tools/rosetta_audit.py", "--allow-regressions"]
    if corpus:
        cmd += ["--corpus", corpus]
    rc, out = sh(cmd)
    tail = next((ln for ln in reversed(out.splitlines()) if "rosetta_audit:" in ln), out.strip().splitlines()[-1] if out.strip() else "")
    return ("rosetta_audit --allow-regressions", rc, tail)


def leg_crucible() -> tuple[str, int, str]:
    rc, out = sh([PY, "tests/tools/crucible_check.py"], timeout=3600)
    verdicts = [ln.strip() for ln in out.splitlines() if "PASS" in ln or "FAIL" in ln]
    return ("crucible_check (verify)", rc, "; ".join(verdicts[-2:]) or out.strip().splitlines()[-1])


def leg_bless_scope() -> tuple[str, int, str]:
    chunks = []
    worst = 0
    for fixture in ("tests/golden_master_audit.json", "tests/golden_master_zero_dep_audit.json"):
        rc, out = sh([PY, "tests/tools/bless_scope.py", "--from-head", fixture, "--show", "0", "--summary"])
        worst = max(worst, rc)
        lines = out.splitlines()
        head = lines[0] if lines else ""
        summ = next((i for i, ln in enumerate(lines) if ln.startswith("--summary")), None)
        block = "\n".join(lines[summ : summ + 9]) if summ is not None else ""
        chunks.append(f"{Path(fixture).name}: {head}\n{block}")
    return ("bless_scope --from-head (both fixtures)", worst, "\n".join(chunks))


def leg_audit_check() -> tuple[str, int, str]:
    rc, out = sh([PY, "tests/tools/audit_check.py"])
    tail = "\n".join(out.strip().splitlines()[-3:])
    return ("audit_check (baseline-gated battery)", rc, tail)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    fam = ap.add_mutually_exclusive_group()
    fam.add_argument("--rules", action="store_true", help="label the block as a rule-contract run (default)")
    fam.add_argument("--score", action="store_true", help="label the block as a score-contract run")
    ap.add_argument("--corpus", help="keyword-rosetta worktree for rosetta_audit")
    args = ap.parse_args(argv)

    langs = touched_languages()
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        futs = {
            "extraction": ex.submit(leg_extraction, langs),
            "rosetta": ex.submit(leg_rosetta, args.corpus),
            "crucible": ex.submit(leg_crucible),
            "audits": ex.submit(leg_audit_check),
        }
        results = {k: f.result() for k, f in futs.items()}
    # bless_scope reads the same fixtures crucible_check verifies -- run it after.
    results["bless"] = leg_bless_scope()

    family = "score-contract" if args.score else "rule-contract"
    failed = [name for name, (_, rc, _) in results.items() if rc != 0]
    print(f"\n{'=' * 72}\n## PR body -- {family} gauntlet ({'ALL GREEN' if not failed else 'FAILED: ' + ', '.join(failed)})\n")
    print("### Measured")
    print(f"- touched languages: {', '.join(langs) or 'none'}")
    print(f"- {results['extraction'][0]}: {'PASS' if results['extraction'][1] == 0 else 'FAIL'} -- {results['extraction'][2]}")
    print("\n### Corpus")
    print(f"- {results['rosetta'][0]}: {'PASS' if results['rosetta'][1] == 0 else 'FAIL'} -- {results['rosetta'][2]}")
    print("\n### Golden masters")
    print(f"- {results['crucible'][0]}: {'PASS' if results['crucible'][1] == 0 else 'FAIL'} -- {results['crucible'][2]}")
    for ln in results["bless"][2].splitlines():
        print(f"  {ln}")
    print("\n### Tests")
    print(f"- {results['audits'][0]}: {'PASS' if results['audits'][1] == 0 else 'FAIL'}")
    for ln in results["audits"][2].splitlines():
        print(f"  {ln}")
    print("=" * 72)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
