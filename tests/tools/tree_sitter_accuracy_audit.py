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
    python tests/tools/tree_sitter_accuracy_audit.py --all --ci
        Runs --ci for every language that has a committed baseline file
        (tests/tree_sitter_accuracy_baseline_<lang>.json), not just one --lang.
        This is what the tree-sitter-accuracy-audit CI workflow runs.
    python tests/tools/tree_sitter_accuracy_audit.py --summary-table
        Regenerates the Markdown table between the
        <!-- TREE_SITTER_ACCURACY_TABLE:BEGIN/END --> markers in
        gitgalaxy/standards/language_standards.py's module docstring from the
        COMMITTED baselines (no live scan, no corpus needed). Languages with
        no committed baseline are simply absent from the table -- it never
        fabricates a row.
    python tests/tools/tree_sitter_accuracy_audit.py --history
        Live-measures every baselined language and appends one row each to
        docs/self_scan/tree_sitter_accuracy_history.csv (gitignored nowhere on
        purpose -- unlike the self-scan DB, this is meant to accumulate across
        runs so it can be graphed over time). Never touches the gating
        baseline files -- only --regenerate does that, and only per language.

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
import csv
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
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
    "c": {
        "ts_lang": "c",
        "func_node_types": {"function_definition"},
        "class_node_types": {"struct_specifier"},
    },
    "cpp": {
        "ts_lang": "cpp",
        "func_node_types": {"function_definition", "template_function"},
        "class_node_types": {"class_specifier", "struct_specifier"},
    },
    "csharp": {
        "ts_lang": "csharp",
        "func_node_types": {"method_declaration", "local_function_statement"},
        "class_node_types": {"class_declaration", "struct_declaration", "interface_declaration"},
    },
    "java": {
        "ts_lang": "java",
        "func_node_types": {"method_declaration", "constructor_declaration"},
        "class_node_types": {"class_declaration", "interface_declaration", "enum_declaration"},
    },
    "go": {
        "ts_lang": "go",
        "func_node_types": {"function_declaration", "method_declaration"},
        "class_node_types": {"type_declaration"},
    },
    "rust": {
        "ts_lang": "rust",
        "func_node_types": {"function_item"},
        "class_node_types": {"struct_item", "trait_item", "impl_item", "enum_item"},
    },
    "scala": {
        "ts_lang": "scala",
        "func_node_types": {"function_definition", "function_declaration"},
        "class_node_types": {"class_definition", "trait_definition", "object_definition"},
    },
    "haskell": {
        "ts_lang": "haskell",
        "func_node_types": {"function"},
        "class_node_types": {"class_decl", "class"},
    },
    "kotlin": {
        "ts_lang": "kotlin",
        "func_node_types": {"function_declaration", "anonymous_function"},
        "class_node_types": {"class_declaration"},
    },
    "swift": {
        "ts_lang": "swift",
        "func_node_types": {"function_declaration"},
        "class_node_types": {"class_declaration"},
    },
    "dart": {
        "ts_lang": "dart",
        "func_node_types": {"function_signature", "local_function_declaration", "method_signature"},
        "class_node_types": {"class_definition", "mixin_application_class"},
    },
    "objective-c": {
        "ts_lang": "objc",
        "func_node_types": {"function_definition", "method_definition", "method_declaration"},
        "class_node_types": {"class_declaration", "class_implementation", "class_interface"},
    },
    "typescript": {
        "ts_lang": "typescript",
        "func_node_types": {
            "function_declaration",
            "method_definition",
            "arrow_function",
            "function_expression",
            "generator_function",
            "generator_function_declaration",
        },
        "class_node_types": {"class_declaration", "abstract_class_declaration"},
    },
    "html": {
        "ts_lang": "html",
        "func_node_types": {"script_element", "style_element"},
        "class_node_types": {"element"},
    },
    "css": {
        "ts_lang": "css",
        "func_node_types": {"at_rule"},
        "class_node_types": {"rule_set"},
    },
    "powershell": {
        "ts_lang": "powershell",
        "func_node_types": {"function_statement", "class_method_definition"},
        "class_node_types": {"class_statement"},
    },
    "solidity": {
        "ts_lang": "solidity",
        "func_node_types": {"function_definition", "modifier_definition", "constructor_definition"},
        "class_node_types": {"contract_declaration", "interface_declaration", "library_declaration"},
    },
    "groovy": {
        "ts_lang": "groovy",
        "func_node_types": {"func"},
        "class_node_types": {"generics_class"},
    },
    "zig": {
        "ts_lang": "zig",
        "func_node_types": {"FnProto"},
        "class_node_types": {"ContainerDecl"},
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
        print(
            f"tree_sitter_accuracy_audit: OK -- improved on {', '.join(improved)} (consider --regenerate to lock it in)."
        )
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


def _all_baseline_langs() -> list[str]:
    """Every language with a committed tests/tree_sitter_accuracy_baseline_<lang>.json, sorted."""
    prefix = "tree_sitter_accuracy_baseline_"
    return sorted(p.stem[len(prefix) :] for p in (REPO_ROOT / "tests").glob(f"{prefix}*.json"))


def run_all(mode_fn) -> int:
    """Runs a single-language mode function (run_ci_check/run_regenerate/run_full_report)
    across every baselined language, in one process. See `_all_baseline_langs`."""
    langs = _all_baseline_langs()
    failed = []
    for lang in langs:
        print(f"\n=== {lang} ===")
        if mode_fn(lang) != 0:
            failed.append(lang)

    print(f"\ntree_sitter_accuracy_audit --all: {len(langs)} language(s) checked.")
    if failed:
        print(f"tree_sitter_accuracy_audit --all: {len(failed)} FAILED: {', '.join(failed)}")
        return 1
    print("tree_sitter_accuracy_audit --all: all OK.")
    return 0


# ----------------------------------------------------------------------------
# --summary-table: regenerate the Markdown table in language_standards.py's
# docstring purely from committed baselines (no live scan, no corpus needed).
# ----------------------------------------------------------------------------

_TABLE_BEGIN = "<!-- TREE_SITTER_ACCURACY_TABLE:BEGIN -->"
_TABLE_END = "<!-- TREE_SITTER_ACCURACY_TABLE:END -->"
_LANGUAGE_STANDARDS_PATH = REPO_ROOT / "gitgalaxy" / "standards" / "language_standards.py"


def _ratio_pct(numerator: int, denominator: int) -> Optional[float]:
    """None (-> "N/A") when the denominator is 0, same convention the baseline JSON itself uses."""
    if denominator <= 0:
        return None
    return round(100.0 * numerator / denominator, 1)


def _fmt_pct(value: Optional[float]) -> str:
    return "N/A" if value is None else f"{value}%"


def generate_summary_table() -> str:
    """Builds the Markdown table from committed baselines only. A language with no committed
    baseline is simply absent -- unlike the hand-written table this replaced, it never emits a
    fabricated all-N/A row for a language nobody has actually measured yet."""
    lines = [
        "| Language | Func Recall | Func Precision | Class Recall | Class Precision |",
        "| -------- | ----------- | -------------- | ------------ | --------------- |",
    ]
    for lang in _all_baseline_langs():
        b = load_baseline(lang)
        if not b:
            continue
        func_recall = _fmt_pct(_ratio_pct(b["found_functions"], b["real_functions"]))
        func_precision = _fmt_pct(_ratio_pct(b["found_functions"], b["found_functions"] + b["extra_functions"]))
        class_recall = _fmt_pct(_ratio_pct(b["found_classes"], b["real_classes"]))
        class_precision = _fmt_pct(_ratio_pct(b["found_classes"], b["found_classes"] + b["extra_classes"]))
        lines.append(f"| {lang.title()} | {func_recall} | {func_precision} | {class_recall} | {class_precision} |")
    return "\n".join(lines)


def update_docstring_table() -> bool:
    """Rewrites the table between the BEGIN/END markers in language_standards.py in place.
    Returns True if the file's content actually changed."""
    text = _LANGUAGE_STANDARDS_PATH.read_text(encoding="utf-8")
    if _TABLE_BEGIN not in text or _TABLE_END not in text:
        sys.exit(
            f"tree_sitter_accuracy_audit: markers {_TABLE_BEGIN!r}/{_TABLE_END!r} not found in "
            f"{_LANGUAGE_STANDARDS_PATH.relative_to(REPO_ROOT)} -- was the docstring edited by hand?"
        )
    replacement = f"{_TABLE_BEGIN}\n{generate_summary_table()}\n{_TABLE_END}"
    pattern = re.compile(re.escape(_TABLE_BEGIN) + r".*?" + re.escape(_TABLE_END), re.DOTALL)
    new_text = pattern.sub(replacement, text, count=1)

    changed = new_text != text
    if changed:
        _LANGUAGE_STANDARDS_PATH.write_text(new_text, encoding="utf-8")
    return changed


def run_summary_table() -> int:
    changed = update_docstring_table()
    rel = _LANGUAGE_STANDARDS_PATH.relative_to(REPO_ROOT)
    if changed:
        print(f"tree_sitter_accuracy_audit: updated the summary table in {rel}.")
    else:
        print(f"tree_sitter_accuracy_audit: {rel} already matches the committed baselines, no change.")
    return 0


# ----------------------------------------------------------------------------
# --history: live-measure every baselined language and append one row each to
# a growing CSV, for graphing accuracy trends over time across pushes.
# ----------------------------------------------------------------------------

_HISTORY_PATH = REPO_ROOT / "docs" / "self_scan" / "tree_sitter_accuracy_history.csv"
_HISTORY_FIELDS = [
    "timestamp_utc",
    "commit_sha",
    "language",
    "files_scanned",
    "real_functions",
    "found_functions",
    "extra_functions",
    "real_classes",
    "found_classes",
    "extra_classes",
    "args_comparable",
    "args_exact_match",
    "func_recall_pct",
    "func_precision_pct",
    "class_recall_pct",
    "class_precision_pct",
]


def _current_commit_sha() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def run_history() -> int:
    """Live-measures (not baseline-read) every language that has BOTH a committed baseline and
    a NODE_MAPS entry, and appends a row per language. Intentionally never writes to the gating
    baseline JSON files -- this is purely additive, observational data for graphing."""
    langs = [lang for lang in _all_baseline_langs() if lang in NODE_MAPS]
    skipped = [lang for lang in _all_baseline_langs() if lang not in NODE_MAPS]
    if skipped:
        print(
            f"tree_sitter_accuracy_audit --history: skipping {', '.join(skipped)} "
            f"(baseline committed but no NODE_MAPS entry to re-scan)."
        )

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    commit_sha = _current_commit_sha()

    _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_header = not _HISTORY_PATH.exists()
    with open(_HISTORY_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_HISTORY_FIELDS)
        if write_header:
            writer.writeheader()
        for lang in langs:
            print(f"tree_sitter_accuracy_audit --history: measuring {lang}...")
            m = measure(lang, verbose=False)
            writer.writerow(
                {
                    "timestamp_utc": timestamp,
                    "commit_sha": commit_sha,
                    "language": lang,
                    "files_scanned": m["files_scanned"],
                    "real_functions": m["real_functions"],
                    "found_functions": m["found_functions"],
                    "extra_functions": m["extra_functions"],
                    "real_classes": m["real_classes"],
                    "found_classes": m["found_classes"],
                    "extra_classes": m["extra_classes"],
                    "args_comparable": m["args_comparable"],
                    "args_exact_match": m["args_exact_match"],
                    "func_recall_pct": _ratio_pct(m["found_functions"], m["real_functions"]),
                    "func_precision_pct": _ratio_pct(m["found_functions"], m["found_functions"] + m["extra_functions"]),
                    "class_recall_pct": _ratio_pct(m["found_classes"], m["real_classes"]),
                    "class_precision_pct": _ratio_pct(m["found_classes"], m["found_classes"] + m["extra_classes"]),
                }
            )

    print(
        f"tree_sitter_accuracy_audit --history: appended {len(langs)} row(s) to {_HISTORY_PATH.relative_to(REPO_ROOT)}."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lang", help="Language to audit (e.g. javascript). Omit when using --all.")
    parser.add_argument(
        "--all", action="store_true", help="Run across every language with a committed baseline instead of one --lang."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--ci", action="store_true", help="Terse baseline-gated regression check (what CI runs).")
    group.add_argument("--regenerate", action="store_true", help="Accept current numbers as the new baseline.")
    group.add_argument(
        "--summary-table",
        action="store_true",
        help="Regenerate language_standards.py's summary table from committed baselines. Ignores --lang/--all.",
    )
    group.add_argument(
        "--history",
        action="store_true",
        help="Append current measured metrics for every baselined language to the history CSV. Ignores --lang.",
    )
    args = parser.parse_args()

    if args.summary_table:
        return run_summary_table()
    if args.history:
        return run_history()

    if bool(args.lang) == bool(args.all):
        parser.error("exactly one of --lang or --all is required")

    if args.all:
        mode_fn = run_regenerate if args.regenerate else run_ci_check if args.ci else run_full_report
        return run_all(mode_fn)

    if args.regenerate:
        return run_regenerate(args.lang)
    if args.ci:
        return run_ci_check(args.lang)
    return run_full_report(args.lang)


if __name__ == "__main__":
    sys.exit(main())
