#!/usr/bin/env python3
r"""Scan the language-crucible corpus from two parent paths and fail if the results differ (#4248).

#4058 (a scan's results depended on the checkout's absolute path) was fixed in #4232 and
#4249 hardened the last absolute-path ignore test. Unit coverage lives in
`tests/core_engine/test_scan_path_independence_4058.py` (a tiny tree); this is the same
check over the real corpus, so a new path-sensitive rule -- an ignore list matched on the
absolute path -- cannot regress silently.

The corpus is copied (hardlinked where possible) to two places under a work directory:

    <work>/neutral/data
    <work>/tmp/docs/vendor/src/data

The second parent carries every name the engine treats specially (`tmp`/`docs` are
IGNORED_DIRECTORIES, `vendor` a VENDOR_MINIFICATION_PATHS marker, `src` an
INTENT_BIASED_SECTORS name). Both are scanned with galaxyscope and the sanitized audits are
compared leaf by leaf (`golden_diff.deep_compare`). Any difference exits 1 and names the
leaves, so the differing files are visible. The default work directory is a sibling of the
repo checkout, never `/tmp`: the neutral parent must not itself contain a special name.

Usage:
    python tests/tools/crucible_path_check.py [--corpus DIR] [--work-dir DIR] [--keep]

Run by `.github/workflows/crucible-path-independence.yml` on engine changes. Bump checklist:
after moving the language-crucible pin (see `tests/_crucible_pin.py`), run this once with
the new corpus (it is the same corpus the golden-crucible check scans).
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests"))
import golden_diff  # noqa: E402
import golden_store  # noqa: E402

from gitgalaxy.core.source_text import read_source  # noqa: E402

NEUTRAL_PARENT = ("neutral",)
SPECIAL_PARENT = ("tmp", "docs", "vendor", "src")
SCAN_LOG = "scan.log"
_LOG_LINE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),(\d{3}) \[\w+\] \[[^\]]*\] (.*)$")
SCAN_TIMEOUT = int(os.environ.get("GITGALAXY_GOLDEN_SCAN_TIMEOUT", "600"))


def _link_or_copy(src: str, dst: str) -> None:
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def stage_corpus(corpus_data: Path, parent: Path) -> Path:
    """Place the corpus at `<parent>/data`; the scan root keeps its name so reports line up."""
    target = parent / corpus_data.name
    shutil.copytree(corpus_data, target, symlinks=True, copy_function=_link_or_copy)
    return target


def slowest_gaps(log_text: str, top: int = 6) -> tuple[float, list[tuple[float, str]]]:
    """(wall seconds, the `top` longest silences) of a scan's stderr log (#5500). Each silence is the
    time since the previous timestamped line, named by the line that ended it, so the single-threaded
    stretches after the extraction pool show up without a debug-level scan."""
    stamps: list[tuple[float, str]] = []
    for line in log_text.splitlines():
        m = _LOG_LINE.match(line)
        if m:
            t = datetime.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").timestamp() + int(m.group(2)) / 1000
            stamps.append((t, m.group(3)))
    if len(stamps) < 2:
        return 0.0, []
    gaps = [(b[0] - a[0], b[1]) for a, b in zip(stamps, stamps[1:], strict=False)]
    return stamps[-1][0] - stamps[0][0], sorted(gaps, reverse=True)[:top]


def timing_report(label: str, out: Path) -> str:
    """The slowest silences of the scan that wrote `out`/scan.log; empty when it has no log."""
    try:
        wall, gaps = slowest_gaps(read_source(out / SCAN_LOG).text)
    except OSError:
        return ""
    lines = [f"{label}: {wall:.0f} s between first and last log line; longest silences before:"]
    lines += [f"  {secs:6.1f} s  {msg[:110]}" for secs, msg in gaps]
    return "\n".join(lines)


def scan(target: Path, out: Path) -> tuple[dict, str | None]:
    """Scan `target`; returns (sanitized audit, error). The error is set when the sibling
    snapshots (DB/GPU/SARIF...) could not be read, in which case only the audit JSON is
    compared and the failure itself counts as a difference."""
    out.mkdir(parents=True)
    with open(out / SCAN_LOG, "w", encoding="utf-8") as log:  # stderr carries timestamped INFO lines (#5500)
        try:
            _run_scan(target, out, log)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            log.flush()  # the log was this scan's visible stderr before #5500: show its tail on failure
            tail = read_source(out / SCAN_LOG).text.splitlines()[-40:]
            print("\n".join(tail), file=sys.stderr)
            raise
    audit_path = str(out / f"{target.name}_galaxy_audit.json")
    try:
        return golden_diff.load_and_sanitize(audit_path), None
    except Exception as exc:  # any unreadable output is itself a finding
        return golden_diff.sanitize(golden_store.load(audit_path)), f"{type(exc).__name__}: {exc}"


def _run_scan(target: Path, out: Path, log) -> None:
    subprocess.run(  # noqa: S603 -- this interpreter + fixed module; paths are argv entries
        [sys.executable, "-m", "gitgalaxy.galaxyscope", str(target), "--output", str(out) + os.sep],
        check=True,
        timeout=SCAN_TIMEOUT,
        env={**os.environ, "GITGALAXY_LICENSE_KEY": "COMMUNITY_FREE_TIER", "GITGALAXY_DISABLE_GIT_HISTORY": "1"},
        stdout=subprocess.DEVNULL,
        stderr=log,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path(os.environ.get("LANGUAGE_CRUCIBLE_PATH", REPO_ROOT.parent / "language-crucible")) / "data",
    )
    parser.add_argument("--work-dir", type=Path, default=REPO_ROOT.parent, help="parent of the scratch dir (not /tmp)")
    parser.add_argument("--keep", action="store_true", help="keep the staged copies and outputs")
    args = parser.parse_args(argv)

    if not args.corpus.is_dir():
        print(f"corpus not found: {args.corpus}", file=sys.stderr)
        return 2
    work = Path(tempfile.mkdtemp(prefix=".crucible-path-check-", dir=args.work_dir)).resolve()
    try:
        neutral_dir = stage_corpus(args.corpus, work.joinpath(*NEUTRAL_PARENT))
        special_dir = stage_corpus(args.corpus, work.joinpath(*SPECIAL_PARENT))
        print(f"neutral : {neutral_dir}\nspecial : {special_dir}", flush=True)
        # #5500: the two scans share nothing (own staged copy, own output dir), and one scan leaves
        # cores idle outside its extraction pool, so run them together.
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            neutral_future = pool.submit(scan, neutral_dir, work / "out-neutral")
            special_future = pool.submit(scan, special_dir, work / "out-special")
            (neutral, neutral_error), (special, special_error) = neutral_future.result(), special_future.result()
        timings = [timing_report("neutral", work / "out-neutral"), timing_report("special", work / "out-special")]
    finally:
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)

    print("\n".join(t for t in timings if t), flush=True)
    diffs = golden_diff.deep_compare(neutral, special)
    if neutral_error != special_error:
        diffs.append(
            f"scan outputs: neutral read {neutral_error or 'cleanly'}; special read {special_error or 'cleanly'}"
        )
    if not diffs:
        print("PASS: the corpus scans identically from both parent paths.")
        return 0
    print(f"FAIL: scanning from {'/'.join(SPECIAL_PARENT)}/ changed {len(diffs)} leaf(s) versus a neutral parent:")
    print("\n".join(d[:300] + (" ..." if len(d) > 300 else "") for d in diffs[:50]))
    if len(diffs) > 50:
        print(f"... and {len(diffs) - 50} more.")
    print("\nThe scan depends on its own absolute path (#4058). Find the rule matching an absolute path.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
