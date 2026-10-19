"""Compare two DOOM Port Speedrun ``clean_check.csv`` files (#5468): before/after per fix, or against round 2.

A run's CSV is identified by a path to the CSV, a results directory, or an engine SHA under ``<work>/results``.
The word ``round2`` names the round-2 study's CSV (engine 585c243e9), which predates the tree-sitter columns:
only columns present in both files are compared. A *regression* is a port whose failed-check set gained a check,
or that is missing from the newer file.
"""

import csv
import os
from pathlib import Path

ROUND2_CSV = Path(os.environ.get("DOOM_ROUND2_CSV", "/srv/storage_16tb/projects/gitgalaxy/doom-study/clean_check.csv"))
KEY = "variant"
# Columns whose change is worth a line; ``verdict`` is derived from ``fails`` and is shown, not compared.
COMPARED = [
    "fails", "first_party_src", "missed_src", "excluded_by_design", "data_files_excluded", "vendor_files_mapped", "wrong_language",
    "gg_functions", "ctags_functions", "func_delta_pct", "files_func_mismatch", "typosquat", "sarif_errors",
    "credential_files", "log_problems",
]  # fmt: skip


def resolve_csv(ref, work):
    """A CSV path, a results dir, an engine SHA under ``<work>/results``, or ``round2``."""
    if ref == "round2":
        return ROUND2_CSV
    p = Path(ref)
    if p.is_dir():
        p = p / "clean_check.csv"
    elif not p.is_file():
        p = Path(work) / "results" / ref / "clean_check.csv"
    if not p.is_file():
        raise SystemExit(f"doom_diff: no clean_check.csv for {ref!r} (looked at {p})")
    return p


def load(path):
    with open(path, newline="") as fh:
        return {r[KEY]: r for r in csv.DictReader(fh)}


def _fails(row):
    return set((row.get("fails") or "").split())


def diff_rows(old, new):
    """Per-port changes between two loaded CSVs: ``{port: {column: (old, new)}}`` plus added/removed port names."""
    shared = {c for r in old.values() for c in r} & {c for r in new.values() for c in r}
    cols = [c for c in COMPARED if c in shared]
    changes = {}
    for port in sorted(old.keys() & new.keys()):
        moved = {c: (old[port].get(c, ""), new[port].get(c, "")) for c in cols if old[port].get(c) != new[port].get(c)}
        if moved:
            changes[port] = moved
    return changes, sorted(new.keys() - old.keys()), sorted(old.keys() - new.keys())


def regressions(old, new):
    """Ports that gained a failed check, or vanished from the newer file."""
    gained = {p: sorted(_fails(new[p]) - _fails(old[p])) for p in old.keys() & new.keys()}
    out = [f"{p}: new fail {', '.join(g)}" for p, g in sorted(gained.items()) if g]
    out += [f"{p}: missing from the newer file" for p in sorted(old.keys() - new.keys())]
    return out


def _perfect(rows):
    return sum(r.get("verdict") == "PERFECT" for r in rows.values())


def render(old_name, new_name, old, new):
    changes, added, removed = diff_rows(old, new)
    lines = [
        f"# DOOM clean-scan diff: `{old_name}` -> `{new_name}`",
        "",
        f"PERFECT: {_perfect(old)}/{len(old)} -> {_perfect(new)}/{len(new)}; "
        f"{len(changes)} port(s) changed, {len(added)} added, {len(removed)} removed",
        "",
    ]
    for port, moved in changes.items():
        verdict = f"{old[port].get('verdict', '')} -> {new[port].get('verdict', '')}"
        lines.append(
            f"- **{port}** ({verdict}): " + "; ".join(f"{c} {a or '-'} -> {b or '-'}" for c, (a, b) in moved.items())
        )
    lines += [f"- added: {p}" for p in added] + [f"- removed: {p}" for p in removed]
    bad = regressions(old, new)
    lines += ["", f"Regressions: {len(bad)}"] + [f"- {b}" for b in bad]
    return "\n".join(lines) + "\n", bad


def run(old_ref, new_ref, work, fail_on_regression=False):
    """Print the diff; return 1 when ``fail_on_regression`` and the newer file regressed."""
    old_path, new_path = resolve_csv(old_ref, work), resolve_csv(new_ref, work)
    text, bad = render(old_ref, new_ref, load(old_path), load(new_path))
    print(text, end="")
    return 1 if (bad and fail_on_regression) else 0
