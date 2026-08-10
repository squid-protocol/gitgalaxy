#!/usr/bin/env python3
"""
AST Accuracy Audit (#1200)

Baseline-gated regression check for GitGalaxy's own structural-signature
extraction accuracy, measured against Python's stdlib `ast` module as
ground truth -- the same methodology docs/language_status/python.md's
Section 9 uses (the methodology that originally surfaced #1182/#1183/
#1184/#1193). Same "regression gate, not a zero-tolerance floor" shape as
tests/ruff_audit.py/tests/mypy_audit.py/tests/dead_key_audit.py: PRs can
make this better, are free to leave it unchanged, but --ci fails if any
tracked metric gets WORSE than the committed baseline.

WHY THE CORPUS IS PINNED (read before touching CORPUS_REF)
ruff_audit.py/mypy_audit.py scan THIS checkout's own live code -- the
target and the tool under test are the same moving thing, which is fine
for lint/types. This check is different: it measures whether the PARSING
ENGINE (gitgalaxy/core/detector.py, prism.py, language_standards.py --
always whatever's checked out right now) correctly extracts functions/
classes/args from a body of Python source. If the target source were also
"whatever's checked out right now," every PR that adds/removes/edits a
single Python file would shift the corpus itself, and a change in the
measured recall/precision numbers could mean "the engine changed" or just
as easily "the corpus changed" -- indistinguishable without a fixed
target. So the CORPUS (what gets parsed) is pinned to a fixed git tag
(CORPUS_REF below) of gitgalaxy's own source, extracted once via `git
archive` into a gitignored cache dir and reused across runs -- only the
ENGINE side of the comparison moves. Same reason tests/tools/
crucible_check.py diffs against language-crucible (a fixed EXTERNAL
corpus) rather than this repo's own current tree.

Bumping CORPUS_REF to a newer tag is a deliberate, reviewable action (like
regenerating any other baseline here) -- it changes the fixed target, so
it always requires a same-PR baseline regeneration (`--regenerate`) with
the diff explained, never as a silent side effect of something else.

USAGE
    python tests/ast_accuracy_audit.py             # full report: recomputes
                                                     # current metrics, shows
                                                     # the comparison against
                                                     # the baseline plus a
                                                     # sample of any missing/
                                                     # extra/args-mismatched
                                                     # functions found, exits
                                                     # 1 on any regression.
    python tests/ast_accuracy_audit.py --ci         # terse regression gate
                                                     # (what CI runs).
    python tests/ast_accuracy_audit.py --regenerate # accept the current
                                                     # numbers as the new
                                                     # baseline -- refuses if
                                                     # any metric would
                                                     # regress (use this only
                                                     # after a genuine
                                                     # engine improvement, or
                                                     # after deliberately
                                                     # bumping CORPUS_REF).

BASELINE
tests/ast_accuracy_baseline.json records the metrics measured immediately
after #1193 landed (function recall jumped from #1193's own measured ~60%
to 98.1% by fixing prism.py's shared line_exclusive delimiter list -- see
that issue for the full history). Tracked metrics and their "better"
direction:
  - found_functions / found_classes: higher is better (recall floor).
  - extra_functions / extra_classes: lower is better (precision ceiling --
    a name GitGalaxy reports that `ast` has no record of at all).
  - args_exact_match: higher is better (of the functions GitGalaxy DID
    find, how many also got the real parameter count right).
  - files_scanned / real_functions / real_classes / args_comparable are
    NOT regression-gated -- they're `ast`'s own ground-truth counts against
    the pinned corpus, which should be bit-for-bit stable given a fixed
    CORPUS_REF and a fixed Python `ast` grammar version. If one of these
    drifts on a PR that didn't touch CORPUS_REF, the corpus cache is
    probably stale/corrupted (see SCOPE below) rather than a real finding.

SCOPE & LIMITATIONS
Only counts FunctionDef/AsyncFunctionDef/ClassDef at any nesting depth
(module-level, class methods, and nested/closure functions all count --
matches `ast.walk`'s traversal, not just top-level defs). A function is
"found" by exact name match within its file -- this repo has very few
duplicate method names across unrelated classes in the same file, but a
same-named method on two different classes in one file is not
disambiguated by class, so this can occasionally overcount recall via a
false-positive name match. args-count compares `ast`'s real parameter
count (positional-only + positional-or-keyword + keyword-only + 1 each for
*args/**kwargs, matching Python's own calling-convention slots) against
function_data.args for the first same-named row.
"""

import argparse
import ast
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = Path(__file__).resolve().parent / "ast_accuracy_baseline.json"
CORPUS_REF = "v2.4.7"
CORPUS_CACHE_DIR = REPO_ROOT / ".ast_accuracy_corpus" / CORPUS_REF


def _git_archive_extract(ref: str, dest: Path) -> None:
    """Extracts every `*.py` file tracked at git ref `ref` into `dest`, without a shell pipe."""
    result = subprocess.run(  # noqa: S603 -- fixed "git" binary via PATH, args are literals/constants only
        ["git", "archive", "--format=tar", ref, "--", "*.py"],  # noqa: S607
        cwd=REPO_ROOT,
        capture_output=True,
    )
    if result.returncode != 0:
        sys.exit(
            f"ast_accuracy_audit: `git archive {ref}` failed -- is the {ref!r} tag present locally?\n"
            "CI checkouts default to a shallow clone; this check needs full history/tags "
            "(actions/checkout with `fetch-depth: 0`). Locally, `git fetch --tags` first.\n"
            f"stderr: {result.stderr.decode(errors='replace')}"
        )
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=BytesIO(result.stdout)) as tar:
        tar.extractall(dest, filter="data")

    # galaxyscope's file census (galaxyscope.py's `git ls-files`) resolves the
    # nearest .git upward from its target dir -- since `dest` lives inside
    # THIS checkout's own tree, without its own .git that census would walk
    # up to gitgalaxy's real .git and correctly report 0 tracked files under
    # an untracked/gitignored path (confirmed: "CENSUS_COMPLETE: Found 0
    # tracked artifacts" before this fix). Giving the extracted corpus its
    # own throwaway index is enough -- `git ls-files` reads the index, no
    # commit needed.
    subprocess.run(["git", "init", "-q"], cwd=dest, check=True)  # noqa: S607
    subprocess.run(["git", "add", "-A"], cwd=dest, check=True)  # noqa: S607


def ensure_corpus() -> Path:
    """Returns the pinned corpus directory, extracting it from CORPUS_REF on first use."""
    if not CORPUS_CACHE_DIR.exists() or not any(CORPUS_CACHE_DIR.rglob("*.py")):
        print(f"ast_accuracy_audit: extracting pinned corpus ({CORPUS_REF}) -- first run, or cache was cleared...")
        _git_archive_extract(CORPUS_REF, CORPUS_CACHE_DIR)
    return CORPUS_CACHE_DIR


def run_engine_scan(corpus_dir: Path, tmp_dir: Path) -> Path:
    """Runs the CURRENT checkout's galaxyscope against the pinned corpus, returns the resulting sqlite DB path."""
    galaxyscope = shutil.which("galaxyscope")
    if not galaxyscope:
        sys.exit("ast_accuracy_audit: galaxyscope not found on PATH -- activate the venv (pip install -e .)")

    output_stub = tmp_dir / "scan.json"
    result = subprocess.run(  # noqa: S603 -- galaxyscope resolved absolute via shutil.which, fixed args
        [
            galaxyscope,
            str(corpus_dir),
            "--config",
            str(REPO_ROOT / ".galaxyscope.yaml"),
            "--db-only",
            "--output",
            str(output_stub),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "GITGALAXY_LICENSE_KEY": "COMMUNITY_FREE_TIER"},
    )
    db_path = output_stub.with_name(f"{output_stub.stem}_master.db")
    if result.returncode != 0 or not db_path.exists():
        sys.exit(
            "ast_accuracy_audit: galaxyscope scan of the pinned corpus failed.\n"
            f"stdout: {result.stdout[-2000:]}\nstderr: {result.stderr[-2000:]}"
        )
    return db_path


def _real_arg_count(node: Any) -> int:
    args = node.args
    return (
        len(args.posonlyargs)
        + len(args.args)
        + len(args.kwonlyargs)
        + (1 if args.vararg else 0)
        + (1 if args.kwarg else 0)
    )


def measure(verbose: bool = False) -> dict:
    """Runs the full pinned-corpus scan + `ast` diff, returns the metrics dict (see module docstring)."""
    corpus_dir = ensure_corpus()

    with tempfile.TemporaryDirectory() as tmp:
        db_path = run_engine_scan(corpus_dir, Path(tmp))
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            files = conn.execute("SELECT id, file_path FROM file_data WHERE language = 'python'").fetchall()

            metrics: dict[str, Any] = {
                "corpus_ref": CORPUS_REF,
                "files_scanned": 0,
                "real_functions": 0,
                "found_functions": 0,
                "extra_functions": 0,
                "real_classes": 0,
                "found_classes": 0,
                "extra_classes": 0,
                "args_comparable": 0,
                "args_exact_match": 0,
            }
            missing_examples: list[tuple[str, list[str]]] = []
            extra_examples: list[tuple[str, list[str]]] = []
            args_mismatch_examples: list[str] = []

            for row in files:
                path = corpus_dir / row["file_path"]
                if not path.exists():
                    continue
                try:
                    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
                except SyntaxError:
                    continue

                real_funcs: dict[str, int] = {}
                real_classes: set[str] = set()
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        real_funcs[node.name] = _real_arg_count(node)
                    elif isinstance(node, ast.ClassDef):
                        real_classes.add(node.name)

                metrics["files_scanned"] += 1
                metrics["real_functions"] += len(real_funcs)
                metrics["real_classes"] += len(real_classes)

                gg_funcs = conn.execute(
                    "SELECT func_name, args FROM function_data WHERE file_id = ?", (row["id"],)
                ).fetchall()
                gg_classes = {
                    r["class_name"]
                    for r in conn.execute("SELECT class_name FROM class_data WHERE file_id = ?", (row["id"],))
                }
                gg_func_names = {r["func_name"] for r in gg_funcs}
                gg_args_by_name: dict[str, Optional[int]] = {}
                for r in gg_funcs:
                    gg_args_by_name.setdefault(r["func_name"], r["args"])

                found = real_funcs.keys() & gg_func_names
                missing = real_funcs.keys() - gg_func_names
                extra = gg_func_names - real_funcs.keys()

                metrics["found_functions"] += len(found)
                metrics["extra_functions"] += len(extra)
                metrics["found_classes"] += len(real_classes & gg_classes)
                metrics["extra_classes"] += len(gg_classes - real_classes)

                for name in found:
                    metrics["args_comparable"] += 1
                    if gg_args_by_name.get(name) == real_funcs[name]:
                        metrics["args_exact_match"] += 1
                    elif verbose and len(args_mismatch_examples) < 10:
                        args_mismatch_examples.append(
                            f"{row['file_path']}::{name}  real={real_funcs[name]} got={gg_args_by_name.get(name)}"
                        )

                if verbose and missing and len(missing_examples) < 8:
                    missing_examples.append((row["file_path"], sorted(missing)[:3]))
                if verbose and extra and len(extra_examples) < 8:
                    extra_examples.append((row["file_path"], sorted(extra)[:3]))
        finally:
            conn.close()

    if verbose:
        metrics["_missing_examples"] = missing_examples
        metrics["_extra_examples"] = extra_examples
        metrics["_args_mismatch_examples"] = args_mismatch_examples
    return metrics


def load_baseline() -> dict:
    if not BASELINE_PATH.exists():
        return {}
    with open(BASELINE_PATH, encoding="utf-8") as f:
        return json.load(f)


# (metric_key, "higher_is_better" | "lower_is_better")
_GATED_METRICS = (
    ("found_functions", "higher_is_better"),
    ("extra_functions", "lower_is_better"),
    ("found_classes", "higher_is_better"),
    ("extra_classes", "lower_is_better"),
    ("args_exact_match", "higher_is_better"),
)
# Not regression-gated, but flagged if they drift -- see BASELINE section above.
# NOTE: args_comparable is deliberately NOT here -- despite being reported
# alongside these, it's `len(found_functions)` (every name found gets an
# args comparison), so it moves whenever the engine's real_functions/found_functions
# does and isn't pure `ast`-only ground truth the way the others are.
_GROUND_TRUTH_METRICS = ("corpus_ref", "files_scanned", "real_functions", "real_classes")
# Reported and persisted in the baseline for context, but neither gated nor
# ground-truth-checked -- see the NOTE above _GROUND_TRUTH_METRICS.
_INFORMATIONAL_METRICS = ("args_comparable",)
_ALL_BASELINE_KEYS = (*[k for k, _ in _GATED_METRICS], *_GROUND_TRUTH_METRICS, *_INFORMATIONAL_METRICS)


def _regressions(current: dict, baseline: dict) -> list[str]:
    regressions = []
    for key, direction in _GATED_METRICS:
        if key not in baseline:
            continue
        cur, base = current[key], baseline[key]
        worse = cur < base if direction == "higher_is_better" else cur > base
        if worse:
            regressions.append(f"{key}: {base} -> {cur} ({direction.replace('_', ' ')}, this got worse)")
    return regressions


def _ground_truth_drift(current: dict, baseline: dict) -> list[str]:
    return [
        f"{key}: baseline={baseline[key]} current={current[key]}"
        for key in _GROUND_TRUTH_METRICS
        if key in baseline and baseline[key] != current[key]
    ]


def _print_report(current: dict, baseline: dict) -> None:
    print(f"{'metric':<20} {'baseline':>10} {'current':>10}")
    for key in _ALL_BASELINE_KEYS:
        if key == "corpus_ref":
            continue
        print(f"{key:<20} {baseline.get(key, '-')!s:>10} {current.get(key)!s:>10}")

    if current.get("_missing_examples"):
        print("\nSample missing (real function `ast` found, GitGalaxy didn't):")
        for path, names in current["_missing_examples"]:
            print(f"  {path}: {names}")
    if current.get("_extra_examples"):
        print("\nSample extra (GitGalaxy reported a name `ast` has no record of):")
        for path, names in current["_extra_examples"]:
            print(f"  {path}: {names}")
    if current.get("_args_mismatch_examples"):
        print("\nSample args-count mismatches:")
        for line in current["_args_mismatch_examples"]:
            print(f"  {line}")


def run_full_report() -> int:
    current = measure(verbose=True)
    baseline = load_baseline()

    _print_report(current, baseline)

    if not baseline:
        print("\nast_accuracy_audit: no baseline committed yet -- run with --regenerate to create one.")
        return 1

    drift = _ground_truth_drift(current, baseline)
    if drift:
        print("\nast_accuracy_audit: ground-truth metric(s) drifted (see SCOPE section for what this means):")
        for line in drift:
            print(f"  {line}")

    regressions = _regressions(current, baseline)
    if regressions:
        print(f"\nast_accuracy_audit: {len(regressions)} regression(s) against the baseline:")
        for line in regressions:
            print(f"  {line}")
        return 1

    print("\nast_accuracy_audit: no regressions.")
    return 0


def run_ci_check() -> int:
    current = measure(verbose=False)
    baseline = load_baseline()

    if not baseline:
        print("ast_accuracy_audit: no baseline committed (tests/ast_accuracy_baseline.json) -- failing closed.")
        return 1

    drift = _ground_truth_drift(current, baseline)
    if drift:
        print("ast_accuracy_audit: ground-truth metric(s) drifted from the pinned corpus's expected values:")
        for line in drift:
            print(f"  {line}")
        print(
            "This means the pinned corpus cache doesn't match CORPUS_REF as committed, or Python's own "
            "`ast` grammar changed between environments -- not necessarily an engine regression. Investigate "
            "before regenerating."
        )
        return 1

    regressions = _regressions(current, baseline)
    if regressions:
        print(f"ast_accuracy_audit: {len(regressions)} regression(s) against the baseline:")
        for line in regressions:
            print(f"  {line}")
        return 1

    improved = [k for k, d in _GATED_METRICS if k in baseline and current[k] != baseline[k]]
    if improved:
        print(f"ast_accuracy_audit: OK -- improved on {', '.join(improved)} (consider --regenerate to lock it in).")
    else:
        print("ast_accuracy_audit: OK -- matches the committed baseline, no regressions.")
    return 0


def run_regenerate() -> int:
    current = measure(verbose=True)
    baseline = load_baseline()

    _print_report(current, baseline)

    if baseline:
        regressions = _regressions(current, baseline)
        if regressions:
            print(f"\nast_accuracy_audit: refusing to regenerate -- {len(regressions)} regression(s) present:")
            for line in regressions:
                print(f"  {line}")
            print("Fix the regression first, or if it's intentional/expected, explain why in the PR description.")
            return 1

    to_write = {k: current[k] for k in _ALL_BASELINE_KEYS}
    with open(BASELINE_PATH, "w", encoding="utf-8") as f:
        json.dump(to_write, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"\nast_accuracy_audit: wrote new baseline to {BASELINE_PATH.relative_to(REPO_ROOT)}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--ci", action="store_true", help="Terse baseline-gated regression check (what CI runs).")
    group.add_argument("--regenerate", action="store_true", help="Accept current numbers as the new baseline.")
    args = parser.parse_args()

    if args.regenerate:
        return run_regenerate()
    if args.ci:
        return run_ci_check()
    return run_full_report()


if __name__ == "__main__":
    sys.exit(main())
