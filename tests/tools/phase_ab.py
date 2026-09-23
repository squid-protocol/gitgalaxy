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
Phase A/B harness: measure the per-phase CPU impact of an engine change on a
real repo, honestly.

This is the reusable version of the ad-hoc worktree-A/B loops used to land
#3069/#3072/#3173. It runs galaxyscope over one target repo with two-or-more
engine checkouts (each a git worktree / any dir on PYTHONPATH), ALTERNATING the
engines every round so machine drift hits both equally, then reports each
`--file-speed --splicing-speed` macro-phase total per engine with the delta vs
the baseline engine.

Why the ceremony (learned the hard way -- see the perf-ab skill):
  * ALTERNATING rounds, not "all A then all B": background load drifts, and
    blocking it into A-then-B aliases that drift onto the comparison.
  * An A-vs-A CONTROL (`--control`): re-runs the baseline under a second label
    so you can see the noise floor before reading any A-vs-B delta as real.
  * Artifact identity on the DETERMINISTIC surface: master.db call lists carry
    hash-seed nondeterminism, so this diffs `*_galaxy_audit.json` (ignoring the
    `Analysis ISO Timestamp` / `Total Scan Duration` keys) and `*_galaxy_sarif.json`
    byte-for-byte. A change that claims output-identity must show CLEAN here.
  * The engine is driven by importing `gitgalaxy.galaxyscope.main()` over
    PYTHONPATH -- never the installed console script, which would silently run
    whatever is on PATH. Each run prints `gitgalaxy.__file__` so you can confirm.

USAGE
    # de-double-sweep vs its base, 3 rounds, on curl, with A-vs-A control:
    python tests/tools/phase_ab.py \\
        --repo /path/to/curl --rounds 3 --control \\
        --engine main=/path/to/worktree-main \\
        --engine mine=/path/to/v6

Engines are `name=path`; the FIRST is the baseline every delta is measured
against. Default phases are the two dominant ones; pass `--phase` to add more
(substring match against the chart label, e.g. `--phase Cartography_Mode_B`).

Requires: GITGALAXY_LICENSE_KEY=COMMUNITY_FREE_TIER (set automatically if unset),
Bash sandbox OFF for mega-repo scans. Zero-dependency mode is fine and matches
the historical baselines; note it in any write-up.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

_PHASE_RE = re.compile(r"^\s*([0-9.]+)s\s*\|\s*[^\|]*\|\s*(.+?)(?:\s*\(Avg:.*)?$")
_WALL_RE = re.compile(r"PIPELINE_SUCCESS:\s*(\d+)\s*files mapped in\s*([0-9.]+)s")
# audit.json keys that legitimately differ run-to-run; ignored in the identity diff.
_VOLATILE_KEYS = {"Analysis ISO Timestamp", "Total Scan Duration"}

DEFAULT_PHASES = ("5_Optical_Detector", "5.5_Security_Lens")

_DRIVER = (
    "import sys; import gitgalaxy; "
    "sys.stderr.write('ENGINE ' + gitgalaxy.__file__ + '\\n'); "
    "from gitgalaxy.galaxyscope import main; "
    "sys.argv = {argv!r}; main()"
)


def _run(engine_path: Path, repo: Path, out_dir: Path) -> tuple[str, dict]:
    """One scan. Returns (raw_stdout, {'wall': float|None, 'files': int|None,
    'phases': {label: seconds}})."""
    out_dir.mkdir(parents=True, exist_ok=True)
    argv = ["galaxyscope", str(repo), "--output", str(out_dir) + "/", "--file-speed", "--splicing-speed"]
    env = {
        **os.environ,
        "PYTHONPATH": str(engine_path),
        "GITGALAXY_LICENSE_KEY": os.environ.get("GITGALAXY_LICENSE_KEY", "COMMUNITY_FREE_TIER"),
    }
    # Args are all internal: our own interpreter, a fixed driver string, and
    # operator-supplied engine/repo paths -- no untrusted network/user input.
    # cwd=engine_path: `python -c` puts the CURRENT directory at sys.path[0],
    # ahead of PYTHONPATH -- launched from inside an engine checkout, every
    # label silently imported THAT checkout (#3182: a "main vs mine" A/B that
    # was really mine vs mine). Running from the engine's own root makes the
    # cwd entry and PYTHONPATH agree.
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _DRIVER.format(argv=argv)],
        env=env,
        cwd=engine_path,
        capture_output=True,
        text=True,
        timeout=1800,
    )
    text = proc.stdout + proc.stderr
    parsed = _parse(text)
    if parsed["wall"] is None and proc.returncode != 0:
        sys.stderr.write(f"  !! scan failed (rc={proc.returncode}); tail:\n")
        sys.stderr.write("\n".join(text.splitlines()[-15:]) + "\n")
    return text, parsed


def _parse(text: str) -> dict:
    # Order-independent: every `NNs | bars | label` line becomes label->seconds
    # (first occurrence wins, so the macro-phase chart's `5.5_Security_Lens` is
    # kept even though a same-named line never recurs). Callers look up only the
    # labels they asked for, so the per-file/per-regex bar lines are harmless.
    phases: dict[str, float] = {}
    wall = files = None
    for line in text.splitlines():
        wm = _WALL_RE.search(line)
        if wm:
            files, wall = int(wm.group(1)), float(wm.group(2))
        pm = _PHASE_RE.match(line)
        if pm:
            phases.setdefault(pm.group(2).strip(), float(pm.group(1)))
    return {"wall": wall, "files": files, "phases": phases}


def _match_phase(phases: dict[str, float], wanted: str) -> float | None:
    if wanted in phases:
        return phases[wanted]
    hits = [v for k, v in phases.items() if wanted in k]
    return hits[0] if len(hits) == 1 else None


def _strip_volatile(obj):
    """Recursively drop run-to-run volatile keys (they nest under the Forensic
    Trail's Analysis Context, not just the top level)."""
    if isinstance(obj, dict):
        return {k: _strip_volatile(v) for k, v in obj.items() if k not in _VOLATILE_KEYS}
    if isinstance(obj, list):
        return [_strip_volatile(v) for v in obj]
    return obj


def _canonical_audit(path: Path) -> str:
    return json.dumps(_strip_volatile(json.loads(path.read_text())), sort_keys=True, indent=1)


def _one(out_dir: Path, suffix: str) -> Path | None:
    hits = sorted(out_dir.glob(f"*_galaxy_{suffix}"))
    return hits[0] if hits else None


def _identity(base_dir: Path, other_dir: Path) -> list[str]:
    notes = []
    for suffix, canon in (("audit.json", _canonical_audit), ("sarif.json", lambda p: p.read_text())):
        a, b = _one(base_dir, suffix), _one(other_dir, suffix)
        if a is None or b is None:
            notes.append(f"{suffix}: MISSING ({'base' if a is None else 'other'})")
            continue
        notes.append(f"{suffix}: {'IDENTICAL' if canon(a) == canon(b) else 'DIFFERS'}")
    return notes


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--repo", type=Path, required=True, help="target repo to scan")
    ap.add_argument(
        "--engine", action="append", required=True, metavar="name=path", help="engine checkout; first is baseline"
    )
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--phase", action="append", default=[], help="extra phase label (substring ok); repeatable")
    ap.add_argument(
        "--control", action="store_true", help="also run the baseline under a 2nd label (A-vs-A noise floor)"
    )
    ap.add_argument("--json", type=Path, help="write full results")
    args = ap.parse_args(argv)

    engines: list[tuple[str, Path]] = []
    for spec in args.engine:
        name, _, path = spec.partition("=")
        if not path:
            ap.error(f"--engine must be name=path, got {spec!r}")
        engines.append((name, Path(path).resolve()))
    if args.control:
        engines.insert(1, (f"{engines[0][0]}#ctl", engines[0][1]))
    phases = list(DEFAULT_PHASES) + [p for p in args.phase if p not in DEFAULT_PHASES]

    args.repo = args.repo.resolve()  # scans run with cwd=<engine>, so relative paths would drift
    work = Path(tempfile.mkdtemp(prefix="phase_ab_"))
    print(f"target={args.repo}  rounds={args.rounds}  engines={[n for n, _ in engines]}")
    print(f"phases={phases}\nscratch={work}\n")

    samples: dict[str, dict] = {n: {"wall": [], **{p: [] for p in phases}} for n, _ in engines}
    last_dir: dict[str, Path] = {}
    for rnd in range(1, args.rounds + 1):
        for name, epath in engines:
            out_dir = work / f"{name.replace('#', '_')}_{rnd}"
            _text, parsed = _run(epath, args.repo, out_dir)
            last_dir[name] = out_dir
            samples[name]["wall"].append(parsed["wall"])
            row = [f"wall={parsed['wall']}s" if parsed["wall"] else "wall=FAIL"]
            for p in phases:
                v = _match_phase(parsed["phases"], p)
                samples[name][p].append(v)
                row.append(f"{p}={v}s")
            print(f"round {rnd:>2} {name:14s} " + "  ".join(row))
    print()

    def _mean(xs):
        good = [x for x in xs if x is not None]
        return statistics.mean(good) if good else None

    base_name = engines[0][0]
    base_means = {m: _mean(samples[base_name][m]) for m in ["wall", *phases]}
    print(f"{'engine':16s} {'metric':22s} {'mean':>10s} {'Δ vs base':>14s}")
    for name, _ in engines:
        for metric in ["wall", *phases]:
            mean = _mean(samples[name][metric])
            base = base_means[metric]
            if mean is None:
                delta = "n/a"
            elif name == base_name or base in (None, 0):
                delta = "--"
            else:
                delta = f"{mean - base:+.2f}s ({100 * (mean - base) / base:+.1f}%)"
            ms = f"{mean:.2f}s" if mean is not None else "FAIL"
            print(f"{name:16s} {metric:22s} {ms:>10s} {delta:>14s}")
        print()

    print("artifact identity (deterministic surface, vs baseline's last round):")
    for name, _ in engines:
        if name == base_name:
            continue
        for note in _identity(last_dir[base_name], last_dir[name]):
            print(f"  {base_name} vs {name:14s} {note}")

    if args.json:
        args.json.write_text(
            json.dumps({"engines": [n for n, _ in engines], "phases": phases, "samples": samples}, indent=2)
        )
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
