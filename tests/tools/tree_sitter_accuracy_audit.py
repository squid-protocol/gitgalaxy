#!/usr/bin/env python3
"""
Tree-sitter Accuracy Audit

Baseline-gated regression check for GitGalaxy's own structural-signature
extraction accuracy, measured against tree-sitter as ground truth.
Generalizes the methodology from `ast_accuracy_audit.py` to support multiple
languages via `--lang <name>`.

USAGE
    python tests/tools/tree_sitter_accuracy_audit.py --lang javascript
    python tests/tools/tree_sitter_accuracy_audit.py --lang javascript --ci
    python tests/tools/tree_sitter_accuracy_audit.py --lang javascript --regenerate

CORPUS
    Unlike ast_accuracy_audit.py which pins this repo's own code via git archive,
    this tool uses the external `language-crucible` corpus. By default, it expects
    it checked out as a sibling directory `../language-crucible`, or set via
    `LANGUAGE_CRUCIBLE_PATH` env var. NOTE: "sibling directory" is relative to
    THIS repo's own checkout root, not a git worktree's -- running from a worktree
    (e.g. `gitgalaxy-worktrees/some-branch/`) needs `LANGUAGE_CRUCIBLE_PATH` set
    explicitly, same pre-existing limitation `crucible_check.py` already has.

BASELINE
    tests/tree_sitter_accuracy_baseline_<lang>.json, one file per language (not
    a combined JSON) so a PR touching one language's baseline shows a small diff.
    Same tracked-metric split as ast_accuracy_audit.py:
      - found_functions / found_classes: higher is better (recall floor).
      - extra_functions / extra_classes: lower is better (precision ceiling -- a
        name GitGalaxy reports that tree-sitter has no record of at all).
      - args_exact_match: higher is better (of the functions GitGalaxy DID find,
        how many also got the real parameter count right).
      - files_scanned / real_functions / real_classes / args_comparable are NOT
        regression-gated -- they're tree-sitter's own ground-truth counts against
        the corpus, which should be stable given a fixed corpus checkout. If one
        of these drifts on a PR that didn't touch the corpus, the local
        `language-crucible` checkout is probably not at the expected pinned tag
        (see `crucible_check.py`'s own corpus pin) rather than a real finding.

SCOPE & LIMITATIONS
    A function is "found" by exact name match WITHIN ITS FILE, matching
    ast_accuracy_audit.py's own documented trade-off -- a same-named
    function/method collision within one file is not disambiguated by
    class/scope, so it can produce a misleading (either falsely inflated or
    falsely low) recall/args-match reading for that one name. Confirmed on this
    corpus: `jquery/event.js` defines two different functions both named `on`
    (a module-level 6-arg helper at file scope, and a 4-arg `.on()` prototype
    method) -- both this tool's tree-sitter walk and GitGalaxy's own
    `function_data` table only ever keep one row per name per file, so the
    reported args-count "mismatch" for `on` in that file is this known
    same-name-collision artifact, not a real args-counting bug in either side.

    Ground truth (tree-sitter) is not infallible either: the plain `javascript`
    grammar cannot fully parse Flow-typed syntax (return-type/param-type
    annotations like `function f(x: ?any): ?Iterator<any> {`), which several
    `language-crucible/data/javascript/react/*.js` files use. A Flow-typed
    function that tree-sitter fails to recognize as a real `function_declaration`
    is invisible to `real_functions`, so if GitGalaxy's own (grammar-agnostic,
    regex-based) `func_start` still correctly matches it, that function gets
    counted as a false "extra" (phantom) against GitGalaxy here -- an artifact of
    this measurement's ground-truth parser, not necessarily a GitGalaxy
    precision defect. Confirmed example: `react/ReactSymbols.js::getIteratorFn`.
    Neither of these is fixable without deeper per-file disambiguation (real
    scope tracking) or a Flow-aware grammar -- noted here so the recall/
    precision numbers aren't read as more precise than the methodology actually
    supports, same spirit as ast_accuracy_audit.py's own SCOPE section.
"""

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

import tree_sitter_language_pack

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CRUCIBLE_PATH = Path(os.environ.get("LANGUAGE_CRUCIBLE_PATH", REPO_ROOT.parent / "language-crucible"))


NODE_MAPS = {
    "javascript": {
        "ts_lang": "javascript",
        "func_node_types": {
            "function_declaration",
            "generator_function_declaration",
            "method_definition",
            "arrow_function",
            "function_expression",
        },
        "class_node_types": {"class_declaration"},
    },
    "ruby": {
        "ts_lang": "ruby",
        "func_node_types": {"method", "singleton_method"},
        "class_node_types": {"class", "singleton_class"},
    },
    "php": {
        "ts_lang": "php",
        "func_node_types": {
            "function_definition",
            "method_declaration",
            "anonymous_function",
            "arrow_function",
        },
        "class_node_types": {"class_declaration", "anonymous_class"},
    },
    "perl": {
        "ts_lang": "perl",
        "func_node_types": {
            "subroutine_declaration_statement",
            "anonymous_subroutine_expression",
            "method_declaration_statement",
            "anonymous_method_expression",
        },
        "class_node_types": {"class_statement"},
    },
    "lua": {
        "ts_lang": "lua",
        "func_node_types": {"function_declaration", "function_definition"},
        "class_node_types": set(),
    },
    "shell": {
        "ts_lang": "bash",
        "func_node_types": {"function_definition"},
        "class_node_types": set(),
    },
}


def _get_baseline_path(lang: str) -> Path:
    return REPO_ROOT / "tests" / f"tree_sitter_accuracy_baseline_{lang}.json"


def ensure_corpus(lang: str) -> Path:
    """Returns the pinned corpus directory for the given language."""
    data_dir = CRUCIBLE_PATH / "data" / lang
    if not data_dir.exists():
        sys.exit(
            f"tree_sitter_accuracy_audit: language-crucible corpus not found at {data_dir}.\n"
            f"Clone squid-protocol/language-crucible (pinned to v1.0) as a sibling directory,\n"
            f"or set LANGUAGE_CRUCIBLE_PATH."
        )
    return data_dir


def run_engine_scan(corpus_dir: Path, tmp_dir: Path) -> Path:
    """Runs the CURRENT checkout's galaxyscope against the pinned corpus, returns the resulting sqlite DB path."""
    galaxyscope = shutil.which("galaxyscope")
    if not galaxyscope:
        sys.exit("tree_sitter_accuracy_audit: galaxyscope not found on PATH -- activate the venv (pip install -e .)")

    output_stub = tmp_dir / "scan.json"
    result = subprocess.run(
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
        timeout=300,
        env={**os.environ, "GITGALAXY_LICENSE_KEY": "COMMUNITY_FREE_TIER"},
    )
    db_path = output_stub.with_name(f"{output_stub.stem}_master.db")
    if result.returncode != 0 or not db_path.exists():
        sys.exit(
            "tree_sitter_accuracy_audit: galaxyscope scan of the pinned corpus failed.\n"
            f"stdout: {result.stdout[-2000:]}\nstderr: {result.stderr[-2000:]}"
        )
    return db_path


def _get_node_name(node: Any) -> Optional[str]:
    name_node = node.child_by_field_name("name")
    if name_node:
        return name_node.text.decode("utf8")
    
    if node.type in ("arrow_function", "function_expression"):
        if node.parent and node.parent.type == "variable_declarator":
            name_node = node.parent.child_by_field_name("name")
            if name_node:
                return name_node.text.decode("utf8")
        if node.parent and node.parent.type == "assignment_expression":
            left = node.parent.child_by_field_name("left")
            if left and left.type in ("identifier", "member_expression"):
                return left.text.decode("utf8").split(".")[-1]
        if node.parent and node.parent.type == "pair":
            key = node.parent.child_by_field_name("key")
            if key and key.type == "property_identifier":
                return key.text.decode("utf8")
    return None


def _get_param_count(node: Any) -> int:
    params_node = node.child_by_field_name("parameters")
    if params_node:
        count = 0
        for child in params_node.named_children:
            if child.type in ("identifier", "assignment_pattern", "array_pattern", "object_pattern", "rest_pattern"):
                count += 1
        return count
    
    param_node = node.child_by_field_name("parameter")
    if param_node:
        return 1
    
    return 0


def measure(lang: str, verbose: bool = False) -> dict:
    """Runs the full pinned-corpus scan + tree-sitter diff, returns the metrics dict."""
    if lang not in NODE_MAPS:
        sys.exit(f"tree_sitter_accuracy_audit: language {lang!r} not supported in NODE_MAPS.")
    
    lang_config = NODE_MAPS[lang]
    ts_lang = lang_config.get("ts_lang", lang)
    func_node_types = lang_config["func_node_types"]
    class_node_types = lang_config["class_node_types"]
    
    parser = tree_sitter_language_pack.get_parser(ts_lang)
    
    corpus_dir = ensure_corpus(lang)

    with tempfile.TemporaryDirectory() as tmp:
        db_path = run_engine_scan(corpus_dir, Path(tmp))
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            # Query file_data using the requested lang
            files = conn.execute("SELECT id, file_path FROM file_data WHERE language = ?", (lang,)).fetchall()

            metrics: dict[str, Any] = {
                "corpus_path": str(corpus_dir.relative_to(CRUCIBLE_PATH.parent)),
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
                    code_bytes = path.read_bytes()
                    tree = parser.parse(code_bytes)
                except Exception:
                    continue

                real_funcs: dict[str, int] = {}
                real_classes: set[str] = set()
                
                def walk(node):
                    if node.type in func_node_types:
                        name = _get_node_name(node)
                        if name:
                            real_funcs[name] = _get_param_count(node)
                    elif node.type in class_node_types:
                        name = _get_node_name(node)
                        if name:
                            real_classes.add(name)
                    for child in node.children:
                        walk(child)
                        
                walk(tree.root_node)

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


def load_baseline(lang: str) -> dict:
    baseline_path = _get_baseline_path(lang)
    if not baseline_path.exists():
        return {}
    with open(baseline_path, encoding="utf-8") as f:
        return json.load(f)


_GATED_METRICS = (
    ("found_functions", "higher_is_better"),
    ("extra_functions", "lower_is_better"),
    ("found_classes", "higher_is_better"),
    ("extra_classes", "lower_is_better"),
    ("args_exact_match", "higher_is_better"),
)
_GROUND_TRUTH_METRICS = ("corpus_path", "files_scanned", "real_functions", "real_classes")
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
        if key == "corpus_path":
            continue
        print(f"{key:<20} {baseline.get(key, '-')!s:>10} {current.get(key)!s:>10}")

    if current.get("_missing_examples"):
        print("\nSample missing (real function `tree-sitter` found, GitGalaxy didn't):")
        for path, names in current["_missing_examples"]:
            print(f"  {path}: {names}")
    if current.get("_extra_examples"):
        print("\nSample extra (GitGalaxy reported a name `tree-sitter` has no record of):")
        for path, names in current["_extra_examples"]:
            print(f"  {path}: {names}")
    if current.get("_args_mismatch_examples"):
        print("\nSample args-count mismatches:")
        for line in current["_args_mismatch_examples"]:
            print(f"  {line}")


def run_full_report(lang: str) -> int:
    current = measure(lang, verbose=True)
    baseline = load_baseline(lang)

    _print_report(current, baseline)

    if not baseline:
        print("\ntree_sitter_accuracy_audit: no baseline committed yet -- run with --regenerate to create one.")
        return 1

    drift = _ground_truth_drift(current, baseline)
    if drift:
        print("\ntree_sitter_accuracy_audit: ground-truth metric(s) drifted (see SCOPE section for what this means):")
        for line in drift:
            print(f"  {line}")

    regressions = _regressions(current, baseline)
    if regressions:
        print(f"\ntree_sitter_accuracy_audit: {len(regressions)} regression(s) against the baseline:")
        for line in regressions:
            print(f"  {line}")
        return 1

    print("\ntree_sitter_accuracy_audit: no regressions.")
    return 0


def run_ci_check(lang: str) -> int:
    current = measure(lang, verbose=False)
    baseline = load_baseline(lang)

    if not baseline:
        print(f"tree_sitter_accuracy_audit: no baseline committed for {lang} -- failing closed.")
        return 1

    drift = _ground_truth_drift(current, baseline)
    if drift:
        print("tree_sitter_accuracy_audit: ground-truth metric(s) drifted from the pinned corpus's expected values:")
        for line in drift:
            print(f"  {line}")
        print("This means the corpus changed. Investigate before regenerating.")
        return 1

    regressions = _regressions(current, baseline)
    if regressions:
        print(f"tree_sitter_accuracy_audit: {len(regressions)} regression(s) against the baseline:")
        for line in regressions:
            print(f"  {line}")
        return 1

    improved = [k for k, d in _GATED_METRICS if k in baseline and current[k] != baseline[k]]
    if improved:
        print(f"tree_sitter_accuracy_audit: OK -- improved on {', '.join(improved)} (consider --regenerate to lock it in).")
    else:
        print("tree_sitter_accuracy_audit: OK -- matches the committed baseline, no regressions.")
    return 0


def run_regenerate(lang: str) -> int:
    current = measure(lang, verbose=True)
    baseline = load_baseline(lang)

    _print_report(current, baseline)

    if baseline:
        regressions = _regressions(current, baseline)
        if regressions:
            print(f"\ntree_sitter_accuracy_audit: refusing to regenerate -- {len(regressions)} regression(s) present:")
            for line in regressions:
                print(f"  {line}")
            print("Fix the regression first, or if it's intentional/expected, explain why in the PR description.")
            return 1

    to_write = {k: current[k] for k in _ALL_BASELINE_KEYS}
    baseline_path = _get_baseline_path(lang)
    with open(baseline_path, "w", encoding="utf-8") as f:
        json.dump(to_write, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"\ntree_sitter_accuracy_audit: wrote new baseline to {baseline_path.relative_to(REPO_ROOT)}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lang", required=True, help="Language to audit (e.g. javascript).")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--ci", action="store_true", help="Terse baseline-gated regression check (what CI runs).")
    group.add_argument("--regenerate", action="store_true", help="Accept current numbers as the new baseline.")
    args = parser.parse_args()

    if args.regenerate:
        return run_regenerate(args.lang)
    if args.ci:
        return run_ci_check(args.lang)
    return run_full_report(args.lang)


if __name__ == "__main__":
    sys.exit(main())
