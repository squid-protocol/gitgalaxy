#!/usr/bin/env python3
"""Does a pull request move a per-language accuracy audit? (the "plan" job of call-graph-accuracy-audit.yml,
detection-accuracy-audit.yml, tree-sitter-accuracy-audit.yml, tree-sitter-accuracy-history.yml,
tri-comparison-audit.yml, tri-comparison-history.yml and graph-comparison-history.yml, #6501)

    python tests/tools/accuracy_audit_plan.py --audit {call-graph,detection,tree-sitter,tree-sitter-history,
                                                       tri-comparison,tri-comparison-history,graph-comparison-history}
                                              [--event pull_request|push] [--base origin/main]
                                              [--files FILE ...] [--github-output PATH]
    python tests/tools/accuracy_audit_plan.py --audit detection --replay 50

Both audits start on any change under gitgalaxy/standards/language_standards/**, then clone the crucible and scan it. Most
of those changes are one language's rules. This planner reads the DIFF of a changed `languages/<lang>.py` (stdlib only: the
job runs before anything is installed, as graph_accuracy_plan.py does) and decides whether it can move the audit:

  detection   the lens scores every language's non-underscore `rules` and reads a fixed set of top-level keys
              (DETECTION_KEYS, pinned against language_lens.py by the tests). A diff that touches only comments, blank
              lines, `_meta`, underscore-prefixed rules or a key the lens never reads cannot move it.
  call-graph  Level 1 scores the languages in tests/call_graph_accuracy_baseline.json. For one of them any diff beyond
              comments, blank lines and `_meta` runs the audit; for any other language the detection rule above applies
              (a rule or extension change can still move which language a crucible file is read as).

  tree-sitter the audit scans each baselined language's crucible corpus (tests/tree_sitter_accuracy_baseline_<lang>.json) and
              compares it with tree-sitter, so a change selects the languages it can move (output `langs`, `all` or a
              comma list; `run` is false when it is empty). Comments and `_meta` are inert, but an underscore rule is
              not (`_dependency_capture` is read). A languages/<lang>.py diff selects <lang> (when it has a baseline),
              unless it touches a key the lens reads, which can reclassify any language's files: then all. A baseline
              file selects its language. A rule that scores another language's ambiguous files differently is not
              chased: the nightly run and the detection audit cover it.
  tree-sitter-history  the push-to-main companion: the same selection, planned on the diff since the last successful run (`--event
              push --base <that run's commit>`; github.event.before would miss a push whose queued run was replaced). It re-measures every language, but `--history` appends nothing when
              the numbers are unchanged, so a push that cannot move a language needs no run.

  tri-comparison  the tree-sitter rule with the committed tests/tri_comparison_baseline_<lang>.json files as the language set
              (output `langs`): a language with no tri baseline is not gated, so its rule edits select nothing.
  tri-comparison-history  push-to-main: `--all --write` re-measures every corpus language into an in-place chart and ledger,
              so any languages/<lang>.py hunk beyond comments and `_meta` runs it (an underscore rule counts); no `langs`.
  graph-comparison-history  push-to-main: refreshes the call ledger (languages in the call baseline) and the import ledger
              (languages in tests/import_graph_corpus.json). A diff beyond comments and `_meta` to one of those languages
              runs it; any other language falls back to the detection rule.

Anything the planner cannot place runs the audit: a new, deleted or unreadable file, a hunk outside the DEFINITION dict,
a non-pull_request event, an empty diff, a failed git call. Every other path in the audit's own list (EVERYTHING) runs it;
any file the workflow's `paths:` lists but this module does not know also runs it. Output: `run=true|false` for the job.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import change_classifier  # noqa: E402
from graph_accuracy_plan import _glob, _norm, corpus_languages  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
T = "tests/tools/"
LANG_DIR = "gitgalaxy/standards/language_standards/languages/"
LANG_STANDARDS = "gitgalaxy/standards/language_standards/"
CALL, DETECTION, TREE, HISTORY = "call-graph", "detection", "tree-sitter", "tree-sitter-history"
TRI, TRI_HISTORY, GRAPH_HISTORY = "tri-comparison", "tri-comparison-history", "graph-comparison-history"
WORKFLOWS = {
    CALL: "call-graph-accuracy-audit.yml",
    DETECTION: "detection-accuracy-audit.yml",
    TREE: "tree-sitter-accuracy-audit.yml",
    HISTORY: "tree-sitter-accuracy-history.yml",
    TRI: "tri-comparison-audit.yml",
    TRI_HISTORY: "tri-comparison-history.yml",
    GRAPH_HISTORY: "graph-comparison-history.yml",
}
# The only event each audit is planned on; any other event (schedule, workflow_dispatch, ...) runs it.
EVENTS = {
    CALL: "pull_request",
    DETECTION: "pull_request",
    TREE: "pull_request",
    HISTORY: "push",
    TRI: "pull_request",
    TRI_HISTORY: "push",
    GRAPH_HISTORY: "push",
}
BASELINE = "tests/call_graph_accuracy_baseline.json"
TREE_BASELINE = "tests/tree_sitter_accuracy_baseline_"
TRI_BASELINE = "tests/tri_comparison_baseline_"
ALL_LANGS = "all"
# The audits that gate a per-language baseline set and so emit `langs`, with the baseline file prefix that names the set.
SELECTING = {TREE: TREE_BASELINE, HISTORY: TREE_BASELINE, TRI: TRI_BASELINE}

_COMMON = (
    "tests/crucible_pins.toml",
    T + "crucible_pins.py",
    T + "accuracy_audit_plan.py",
    T + "graph_accuracy_plan.py",
    T + "change_classifier.py",
)
# Every path here runs the audit (the tool, its baseline, the shared engine files and the workflow itself).
EVERYTHING = {
    CALL: (
        *_COMMON,
        "gitgalaxy/core/detector.py",
        "gitgalaxy/core/prism.py",
        T + "call_graph_accuracy.py",
        BASELINE,
        ".github/workflows/call-graph-accuracy-audit.yml",
    ),
    DETECTION: (
        *_COMMON,
        "gitgalaxy/standards/language_lens.py",
        "gitgalaxy/standards/gitgalaxy_config.py",
        T + "detection_accuracy_audit.py",
        "tests/detection_accuracy_baseline.json",
        ".github/workflows/detection-accuracy-audit.yml",
    ),
    TREE: (
        *_COMMON,
        "gitgalaxy/core/detector.py",
        "gitgalaxy/core/prism.py",
        T + "tree_sitter_accuracy_audit.py",
        ".github/workflows/tree-sitter-accuracy-audit.yml",
    ),
    HISTORY: (
        *_COMMON,
        "gitgalaxy/core/detector.py",
        "gitgalaxy/core/prism.py",
        T + "tree_sitter_accuracy_audit.py",
        ".github/workflows/tree-sitter-accuracy-history.yml",
    ),
    TRI: (
        *_COMMON,
        "gitgalaxy/core/detector.py",
        "gitgalaxy/core/prism.py",
        T + "tri_comparison_chart.py",
        T + "tri_comparison_gatherer.py",
        T + "tri_comparison_reconcile.py",
        T + "tri_comparison_ledger.py",
        ".github/workflows/tri-comparison-audit.yml",
    ),
    TRI_HISTORY: (
        *_COMMON,
        "gitgalaxy/core/detector.py",
        "gitgalaxy/core/prism.py",
        T + "tri_comparison_chart.py",
        T + "tri_comparison_gatherer.py",
        T + "tri_comparison_reconcile.py",
        T + "tri_comparison_ledger.py",
        "tests/tri_comparison_baseline_*.json",
        ".github/workflows/tri-comparison-history.yml",
    ),
    GRAPH_HISTORY: (
        *_COMMON,
        "gitgalaxy/core/detector.py",
        "gitgalaxy/core/prism.py",
        "gitgalaxy/core/network_risk_sensor.py",
        "gitgalaxy/galaxyscope.py",
        T + "call_graph_accuracy.py",
        T + "import_graph_accuracy.py",
        T + "graph_ledger.py",
        T + "tri_comparison_ledger.py",
        T + "graph_coverage_chart.py",
        BASELINE,
        "tests/import_graph_accuracy_baseline.json",
        "tests/import_graph_corpus.json",
        "tests/call_graph_resolution*_baseline.json",
        ".github/workflows/graph-comparison-history.yml",
    ),
}
# The top-level keys of a language DEFINITION that language_lens.py reads (test_accuracy_audit_plan pins this set
# against the keys the lens, the registry and the overrides quote). `rules` is separate: its underscore-prefixed
# entries are metadata the lens skips.
DETECTION_KEYS = frozenset(
    {
        "discriminators",
        "disqualifiers",
        "exact_matches",
        "extensions",
        "extensions_needing_discriminator",
        "internal_discriminator",
        "internal_discriminator_extensions",
        "lexical_family",
        "shared_extension_evidence",
        "shebangs",
    }
)

_TOP = re.compile(r'^    "([^"\n]+)"\s*:')
_RULE = re.compile(r'^        "([^"\n]+)"\s*:')
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

Place = tuple[str, str | None]  # (top-level key, the rule inside `rules` or None)


def baseline_languages(root: Path = REPO_ROOT) -> frozenset[str]:
    return frozenset(_norm(k) for k in json.loads((root / BASELINE).read_text(encoding="utf-8")))


def tree_sitter_languages(root: Path = REPO_ROOT, baseline: str = TREE_BASELINE) -> dict[str, str]:
    """Normalised language -> the name in its baseline file (`objectivec` -> `objective-c`), one per committed baseline
    (the tree-sitter ones, or `baseline=TRI_BASELINE` for the tri-comparison ones)."""
    prefix = baseline.rsplit("/", 1)[1]
    return {_norm(p.stem[len(prefix) :]): p.stem[len(prefix) :] for p in (root / "tests").glob(f"{prefix}*.json")}


def scored_languages(audit: str, root: Path = REPO_ROOT) -> frozenset[str]:
    """The normalised languages whose diff is judged by more than the detection rule: the call baseline, plus (for the
    graph ledger history) the import corpus."""
    langs = baseline_languages(root)
    return langs | corpus_languages(root) if audit == GRAPH_HISTORY else langs


def locate(lines: list[str], lineno: int) -> Place | None:
    """The DEFINITION key (and `rules` entry) that source line `lineno` (1-based) belongs to; None when unplaceable
    (before DEFINITION, after its close, or inside some other module-level object)."""
    top = rule = None
    for i in range(min(lineno, len(lines)) - 1, -1, -1):
        raw = lines[i]
        text = raw.strip()
        if not text or text.startswith("#"):
            continue
        if not raw[0].isspace():  # a module-level line: the container of everything walked past
            return (top, rule) if top is not None and raw.startswith("DEFINITION") else None
        if rule is None and top is None and (m := _RULE.match(raw)):
            rule = m.group(1)
        if top is None and (m := _TOP.match(raw)):
            top = m.group(1)
            if top != "rules":
                rule = None
            # keep walking up: the module-level line proves the container is DEFINITION
    return None


def _changed_lines(diff: str) -> tuple[list[int], list[int]]:
    """(removed old-file line numbers, added new-file line numbers) of a `git diff -U0` of one file."""
    old: list[int] = []
    new: list[int] = []
    for ln in diff.splitlines():
        if m := _HUNK.match(ln):
            a, b, c, d = int(m[1]), int(m[2] or 1), int(m[3]), int(m[4] or 1)
            old += range(a, a + b)
            new += range(c, c + d)
    return old, new


def touched(old_text: str, new_text: str, diff: str) -> list[Place | None]:
    """The place of every non-comment, non-blank line the diff removes or adds (None = unplaceable)."""
    old_lines, new_lines = old_text.splitlines(), new_text.splitlines()
    removed, added = _changed_lines(diff)
    out: list[Place | None] = []
    for lines, numbers in ((old_lines, removed), (new_lines, added)):
        for n in numbers:
            text = lines[n - 1].strip() if 0 < n <= len(lines) else ""
            if text and not text.startswith("#"):
                out.append(locate(lines, n))
    return out


def moves_detection(place: Place | None) -> bool:
    if place is None:
        return True
    top, rule = place
    if top == "rules":
        return rule is None or not rule.startswith("_")
    return top in DETECTION_KEYS


def moves_call_graph(place: Place | None) -> bool:
    return place is None or place[0] != "_meta"


def _git(*args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False)  # noqa: S603, S607
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git {args[0]} failed")
    return proc.stdout


def git_places(path: str, base: str, head: str) -> list[Place | None]:
    """The places a change of `path` between two commits touches (RuntimeError when git cannot say)."""
    old, new = _git("show", f"{base}:{path}"), _git("show", f"{head}:{path}")
    return touched(old, new, _git("diff", "-U0", base, head, "--", path))


def language_moves(
    audit: str, path: str, baseline: frozenset[str], places: Callable[[str], list[Place | None]]
) -> bool:
    """Whether the change of languages/<lang>.py can move `audit`."""
    stem = path[len(LANG_DIR) : -3]
    if stem.startswith("_"):  # __init__ and helpers: shared by the languages
        return True
    try:
        found = places(path)
    except (RuntimeError, OSError, ValueError):  # a new or deleted file, an unreadable base: when in doubt, run
        return True
    if audit == TRI_HISTORY or (audit in (CALL, GRAPH_HISTORY) and _norm(stem) in baseline):
        return any(moves_call_graph(p) for p in found)
    return any(moves_detection(p) for p in found)


def tree_languages(path: str, langs: dict[str, str], places: Callable[[str], list[Place | None]]) -> set[str] | None:
    """The tree-sitter languages a change of languages/<lang>.py can move; None = all of them."""
    stem = path[len(LANG_DIR) : -3]
    if stem.startswith("_"):
        return None
    try:
        found = places(path)
    except (RuntimeError, OSError, ValueError):  # a new or deleted file, an unreadable base: when in doubt, run
        return None
    if any(p is None or p[0] in DETECTION_KEYS for p in found):  # unplaceable, or a key that reclassifies files
        return None
    if any(p[0] != "_meta" for p in found if p) and _norm(stem) in langs:
        return {langs[_norm(stem)]}
    return set()


def plan(
    files: list[str],
    event: str,
    audit: str,
    places: Callable[[str], list[Place | None]],
    baseline: frozenset[str] | None = None,
    langs: dict[str, str] | None = None,
) -> dict:
    tree = audit in SELECTING
    every = {"langs": ALL_LANGS} if tree else {}
    if event != EVENTS[audit]:
        return {"run": True, "reason": f"{event}: always", "inputs": [], **every}
    if not files:
        return {
            "run": True,
            "reason": "no changed files found (the diff is unreadable or empty)",
            "inputs": [],
            **every,
        }
    baseline = scored_languages(audit) if baseline is None else baseline
    prefix = SELECTING.get(audit, "")
    langs = (tree_sitter_languages(baseline=prefix) if langs is None else langs) if tree else {}
    inputs: list[str] = []
    selected: set[str] = set()
    everything = False
    for f in sorted(files):
        if _glob(f, list(EVERYTHING[audit])):
            inputs.append(f)
            everything = True
        elif tree and f.startswith(prefix) and f.endswith(".json"):
            inputs.append(f)
            selected.add(f[len(prefix) : -5])
        elif f.startswith(LANG_DIR) and f.endswith(".py") and "/" not in f[len(LANG_DIR) :]:
            if tree:
                moved = tree_languages(f, langs, places)
                if moved is None or moved:
                    inputs.append(f)
                    everything = everything or moved is None
                    selected |= moved or set()
            elif language_moves(audit, f, baseline, places):
                inputs.append(f)
        elif f.startswith(LANG_STANDARDS):  # identifiers, _shared_patterns, a registry or a data file
            inputs.append(f)
            everything = True
    if not inputs:
        areas = sorted({change_classifier.area(f) for f in files})
        reason = f"no changed file can move {audit} (areas: {', '.join(areas)})"
        return {"run": False, "reason": reason, "inputs": [], **({"langs": ""} if tree else {})}
    out = {"run": True, "reason": f"{len(inputs)} changed file(s) feed it, first: {inputs[0]}", "inputs": inputs[:20]}
    if tree:
        out["langs"] = ALL_LANGS if everything or not langs else ",".join(sorted(selected))
    return out


def changed_files(base: str, event: str = "pull_request") -> list[str]:
    """A pull request's files are `base...HEAD`; a push's are everything since the commit before it (`base`)."""
    span = f"{base}...HEAD" if event == "pull_request" else base
    return [
        ln
        for ln in _git("diff", "--name-only", span, *([] if event == "pull_request" else ["HEAD"])).splitlines()
        if ln.strip()
    ]


def pr_places(base: str, event: str = "pull_request") -> Callable[[str], list[Place | None]]:
    start = _git("merge-base", base, "HEAD").strip() if event == "pull_request" else base
    return lambda path: git_places(path, start, "HEAD")


def workflow_paths(audit: str) -> list[str]:
    """The `paths:` filter of the audit's workflow, read as text (stdlib only: no yaml)."""
    text = (REPO_ROOT / ".github/workflows" / WORKFLOWS[audit]).read_text(encoding="utf-8")
    block = text.split("    paths:\n", 1)[1].split("\n\npermissions:", 1)[0]
    return re.findall(r'^\s+- "([^"]+)"', block, flags=re.M)


def replay(prs: list[dict], audit: str, baseline: frozenset[str]) -> dict:
    """Of the merged pull requests in `prs` (`gh pr list --json number,files,mergeCommit`): how many the workflow's
    `paths:` filter starts BEFORE, and how many run the audit AFTER (the diff read from the merge commit)."""
    paths = workflow_paths(audit)
    before = after = 0
    ran_after: list[int] = []
    tree = audit in SELECTING
    n_langs = len(tree_sitter_languages(baseline=SELECTING[audit])) if tree else 0
    langs_before = langs_after = 0  # tree-sitter: language corpora scanned
    for pr in prs:
        files = [f["path"] for f in pr.get("files") or [] if f.get("path")]
        oid = (pr.get("mergeCommit") or {}).get("oid")
        selected = ALL_LANGS
        if len(files) >= 100:  # gh cuts the list: count it as running
            triggered, run = True, True
        else:
            triggered = any(_glob(f, paths) for f in files)
            if triggered and oid:
                found = plan(files, EVENTS[audit], audit, lambda p, o=oid: git_places(p, f"{o}^", o), baseline)
                run, selected = found["run"], found.get("langs", ALL_LANGS)
            else:
                run = triggered
        before += triggered
        after += bool(triggered and run)
        if tree and triggered:
            langs_before += n_langs
            langs_after += (n_langs if selected == ALL_LANGS else len(selected.split(","))) if run and selected else 0
        if triggered and run:
            ran_after.append(pr["number"])
    n = len(prs)
    langs = {"language_corpora_before": langs_before, "language_corpora_now": langs_after} if tree else {}
    return {
        "audit": audit,
        **langs,
        "prs": n,
        "ran_before": before,
        "runs_now": after,
        "share_before": round(before / n, 3) if n else 0.0,
        "share_now": round(after / n, 3) if n else 0.0,
        "prs_that_still_run": ran_after,
    }


def run_replay(n: int, audit: str) -> dict:
    proc = subprocess.run(  # noqa: S603
        ["gh", "pr", "list", "--state", "merged", "-L", str(n), "--json", "number,files,mergeCommit"],  # noqa: S607
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "gh pr list failed")
    return replay(json.loads(proc.stdout), audit, scored_languages(audit))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--audit", required=True, choices=sorted(WORKFLOWS))
    ap.add_argument("--event", default="pull_request")
    ap.add_argument(
        "--base", default="origin/main", help="the branch (pull_request) or the commit before the push (push)"
    )
    ap.add_argument("--files", nargs="*", help="the changed files, instead of git diff --name-only BASE...HEAD")
    ap.add_argument("--github-output", type=Path, help="append `run=true|false` for later steps")
    ap.add_argument("--replay", type=int, metavar="N", help="plan the last N merged PRs (needs gh and the history)")
    args = ap.parse_args()
    if args.replay:
        try:
            print(json.dumps(run_replay(args.replay, args.audit), indent=1))
        except (RuntimeError, OSError, ValueError) as e:
            print(f"replay failed: {e}", file=sys.stderr)
            return 1
        return 0
    try:
        planned = args.event == EVENTS[args.audit]
        files = args.files if args.files is not None else (changed_files(args.base, args.event) if planned else [])
        p = plan(files, args.event, args.audit, pr_places(args.base, args.event) if planned else (lambda _p: []))
    except (RuntimeError, OSError, ValueError, KeyError) as e:  # cannot tell what changed: run
        p = {
            "run": True,
            "reason": f"cannot plan ({e})",
            "inputs": [],
            **({"langs": ALL_LANGS} if args.audit in SELECTING else {}),
        }
    print(json.dumps(p, indent=1))
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as fh:
            fh.write(f"run={'true' if p['run'] else 'false'}\n")
            if "langs" in p:
                fh.write(f"langs={p['langs']}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
