"""Run the keyword-rosetta control corpus against the CURRENT engine build.

The corpus (squid-protocol/keyword-rosetta) plants an identical 12-probe program in every
signature-bearing language with exact expected signal counts. Its own `tools/verify_language.py`
is the per-language gate; this script runs that gate for every language folder and answers the
one question an engine PR actually needs answered:

    which languages does THIS build move, and were they already moving on engine main?

A language whose manifest fails against this build but PASSES against a baseline build (engine
main) is a **regression** this change introduces -- or an intentional, corpus-visible improvement
the corpus now owes a re-bless for (docs/self_scan/ROSETTA_AUDIT.md). A language that fails
against BOTH is **pre-existing drift**: engine main already moved past the corpus and the corpus
has not caught up yet. That is not this PR's problem and is reported as a notice, never a failure,
so an unrelated PR opened while the corpus is behind stays green.

Usage:
    python tests/tools/rosetta_audit.py                             # sibling ../keyword-rosetta, current galaxyscope
    python tests/tools/rosetta_audit.py --corpus <path> --baseline-bin <galaxyscope-of-engine-main>
    python tests/tools/rosetta_audit.py --allow-regressions         # report regressions as warnings, exit 0

Environment:
    GALAXYSCOPE_BIN   the CURRENT build's galaxyscope (default: `galaxyscope` on PATH)
    GITHUB_STEP_SUMMARY / GITHUB_ACTIONS   honoured when present (summary table + annotations)

Exit codes:
    0  every language passes, or the only failures are pre-existing drift (or --allow-regressions)
    1  at least one regression this build introduces
    2  the audit did not actually run: no galaxyscope, no corpus, zero languages, or a verifier
       that crashed instead of reporting PASS/FAIL. "0 languages checked, all OK" is a failure
       wearing a pass (gitgalaxy#2682) and this script refuses to print it.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CORPUS = REPO_ROOT.parent / "keyword-rosetta"

# Per-language outcome of one verifier run.
PASS = "pass"
FAIL = "fail"
ERROR = "error"  # the verifier crashed / never reported -- infrastructure, not drift

# Classification of a language after the (optional) baseline re-run.
CLEAN = "clean"
REGRESSION = "regression"  # fails here, passes on the baseline build
PRE_EXISTING = "pre-existing"  # fails on both builds: corpus is behind engine main
MOVED = "moved"  # fails here, no baseline given to classify against
BROKEN = "broken"  # a verifier run errored


@dataclass
class Outcome:
    language: str
    status: str
    tail: str = ""
    baseline_status: str | None = None
    verdict: str = field(default=CLEAN)


def _corpus_languages(corpus: Path) -> list[str]:
    data = corpus / "data"
    if not data.is_dir():
        return []
    return sorted(p.parent.name for p in data.glob("*/expected_signals.json"))


def _run_verifier(corpus: Path, language: str, galaxyscope_bin: str) -> tuple[str, str]:
    """Runs keyword-rosetta's verify_language.py once. Returns (status, output tail).

    PASS/FAIL come from the verifier's own final line, not from its exit code alone: a crash
    (no galaxyscope, a schema import error, a scan timeout) also exits nonzero, and treating
    that as "FAIL" would report an infrastructure problem as corpus drift.
    """
    env = {**os.environ, "GALAXYSCOPE_BIN": galaxyscope_bin, "GITGALAXY_PATH": str(REPO_ROOT)}
    try:
        result = subprocess.run(
            [sys.executable, str(corpus / "tools" / "verify_language.py"), language],
            cwd=corpus,
            env=env,
            capture_output=True,
            text=True,
            timeout=900,
        )
    except subprocess.TimeoutExpired:
        return ERROR, "verify_language.py timed out after 900s"
    out = (result.stdout + result.stderr).strip()
    lines = [ln for ln in out.splitlines() if ln.strip()]
    last = lines[-1] if lines else ""
    for ln in reversed(lines):
        if ln.startswith(f"PASS {language}"):
            return PASS, ln
        if ln.startswith(f"FAIL {language}"):
            return FAIL, "\n".join(lines[-12:])
    return ERROR, "\n".join(lines[-12:]) or f"no output (rc={result.returncode}); last line: {last!r}"


def classify(current: dict[str, str], baseline: dict[str, str] | None) -> dict[str, str]:
    """Pure classification of per-language statuses -- the part worth unit-testing.

    `current` maps language -> PASS/FAIL/ERROR for this build. `baseline` maps the languages
    that failed here -> their status on the baseline build (None when no baseline was run).
    """
    verdicts: dict[str, str] = {}
    for lang, status in current.items():
        if status == PASS:
            verdicts[lang] = CLEAN
        elif status == ERROR:
            verdicts[lang] = BROKEN
        elif baseline is None or lang not in baseline:
            verdicts[lang] = MOVED
        elif baseline[lang] == PASS:
            verdicts[lang] = REGRESSION
        elif baseline[lang] == FAIL:
            verdicts[lang] = PRE_EXISTING
        else:
            verdicts[lang] = BROKEN
    return verdicts


def _annotate(kind: str, message: str) -> None:
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::{kind}::{message}")


def _write_summary(outcomes: list[Outcome], baseline_used: bool, allow_regressions: bool) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    counts = {v: sum(1 for o in outcomes if o.verdict == v) for v in (CLEAN, REGRESSION, PRE_EXISTING, MOVED, BROKEN)}
    lines = [
        "## rosetta-audit",
        "",
        f"{len(outcomes)} languages checked against this build"
        + (" and against engine main for anything that failed." if baseline_used else "."),
        "",
        f"clean **{counts[CLEAN]}** · regression **{counts[REGRESSION]}** · pre-existing drift "
        f"**{counts[PRE_EXISTING]}** · moved (unclassified) **{counts[MOVED]}** · broken **{counts[BROKEN]}**",
        "",
    ]
    moved = [o for o in outcomes if o.verdict != CLEAN]
    if moved:
        lines += ["| language | this build | engine main | verdict |", "|---|---|---|---|"]
        for o in moved:
            lines.append(f"| {o.language} | {o.status} | {o.baseline_status or '-'} | {o.verdict} |")
        lines.append("")
        if counts[REGRESSION] or counts[MOVED]:
            lines.append(
                ("Regressions are allowed on this PR (`rosetta:rebless-owed`). " if allow_regressions else "")
                + "Intentional? Merge, then re-bless those languages in keyword-rosetta against engine main "
                "(its `docs/GATING.md`). Unintentional? Fix the engine change. "
                "See `docs/self_scan/ROSETTA_AUDIT.md`."
            )
        if counts[PRE_EXISTING]:
            lines.append(
                "Pre-existing drift is engine main already ahead of the corpus; not this PR's doing. "
                "keyword-rosetta's `bias-history` workflow tracks it as an open issue there."
            )
        lines.append("")
        lines.append("<details><summary>verifier output</summary>\n")
        for o in moved:
            lines.append(f"**{o.language}**\n\n```\n{o.tail}\n```\n")
        lines.append("</details>")
    Path(path).open("a", encoding="utf-8").write("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS, help="keyword-rosetta checkout")
    parser.add_argument(
        "--baseline-bin",
        help="galaxyscope of the baseline build (engine main); failing languages are re-run against it",
    )
    parser.add_argument(
        "--allow-regressions",
        action="store_true",
        help="report regressions as warnings and exit 0 (the PR carries the rosetta:rebless-owed label)",
    )
    parser.add_argument("--jobs", type=int, default=max(1, min(4, os.cpu_count() or 1)))
    args = parser.parse_args(argv)

    corpus: Path = args.corpus.resolve()
    if not (corpus / "tools" / "verify_language.py").is_file():
        print(f"rosetta_audit: no keyword-rosetta checkout at {corpus} (need tools/verify_language.py)")
        return 2
    languages = _corpus_languages(corpus)
    if not languages:
        print(f"rosetta_audit: zero language folders with expected_signals.json under {corpus / 'data'}")
        return 2

    current_bin = os.environ.get("GALAXYSCOPE_BIN") or shutil.which("galaxyscope") or ""
    if not current_bin or not Path(current_bin).exists():
        print("rosetta_audit: galaxyscope not found -- set GALAXYSCOPE_BIN or activate the venv (pip install -e .)")
        return 2
    baseline_bin: str | None = args.baseline_bin
    if baseline_bin and not Path(baseline_bin).exists():
        print(f"rosetta_audit: --baseline-bin {baseline_bin} does not exist")
        return 2

    print(f"rosetta_audit: {len(languages)} languages, corpus {corpus}, engine {current_bin}")
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(lambda lang: _run_verifier(corpus, lang, current_bin), languages))
    outcomes = [Outcome(lang, status, tail) for lang, (status, tail) in zip(languages, results)]
    current = {o.language: o.status for o in outcomes}

    failed = [o for o in outcomes if o.status == FAIL]
    baseline: dict[str, str] | None = None
    if baseline_bin and failed:
        print(f"rosetta_audit: {len(failed)} failed here; re-running those against the baseline build {baseline_bin}")
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            base_results = list(pool.map(lambda o: _run_verifier(corpus, o.language, baseline_bin), failed))
        baseline = {}
        for o, (status, _tail) in zip(failed, base_results):
            o.baseline_status = status
            baseline[o.language] = status

    verdicts = classify(current, baseline)
    for o in outcomes:
        o.verdict = verdicts[o.language]

    for o in outcomes:
        marker = {CLEAN: "ok  ", REGRESSION: "REG ", PRE_EXISTING: "pre ", MOVED: "MOV ", BROKEN: "ERR "}[o.verdict]
        print(f"  {marker} {o.language:18s} {o.tail.splitlines()[0] if o.tail else ''}")
        if o.verdict != CLEAN and o.tail.count("\n"):
            for ln in o.tail.splitlines()[1:]:
                print(f"       {ln}")

    n_reg = sum(1 for o in outcomes if o.verdict in (REGRESSION, MOVED))
    n_pre = sum(1 for o in outcomes if o.verdict == PRE_EXISTING)
    n_broken = sum(1 for o in outcomes if o.verdict == BROKEN)
    _write_summary(outcomes, baseline is not None, args.allow_regressions)

    print(
        f"\nrosetta_audit: {len(outcomes)} language(s) checked -- "
        f"{n_reg} regression(s), {n_pre} pre-existing, {n_broken} broken."
    )
    if n_broken:
        _annotate("error", f"rosetta-audit did not run cleanly: {n_broken} verifier run(s) crashed -- see the job log")
        return 2
    for o in outcomes:
        if o.verdict == PRE_EXISTING:
            _annotate("notice", f"{o.language}: corpus is behind engine main (pre-existing drift, not this PR)")
        elif o.verdict in (REGRESSION, MOVED):
            _annotate(
                "warning" if args.allow_regressions else "error",
                f"{o.language}: this build moves the control corpus -- {o.tail.splitlines()[0]}",
            )
    if n_reg and not args.allow_regressions:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
