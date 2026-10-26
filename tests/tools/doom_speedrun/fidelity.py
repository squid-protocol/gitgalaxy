#!/usr/bin/env python3
"""DOOM study fidelity (#5620): what each port's own README says about its fidelity to the original.

    python tests/tools/doom_speedrun/fidelity.py check  [--work DIR] [--strict]
    python tests/tools/doom_speedrun/fidelity.py report [--work DIR]

``manifest.csv`` carries three columns beside ``lineage``: ``fidelity`` (a value of ``VOCAB``), ``fidelity_file`` (the
README the claim is read from) and ``fidelity_phrase`` (a short phrase quoted from it, brief and attributed to that
port). ``check`` reads each pinned clone under ``<work>/repos`` and fails when the vocabulary is wrong, a claim has no
phrase, or the phrase is not in the README (whitespace, case and markdown emphasis ignored), so the column can be
re-derived from the pinned clone by one command. A port whose clone is absent is listed as unchecked, not passed
(``--strict`` makes it an error). ``report`` prints the port counts per ``class`` x ``fidelity``. A port that says nothing is ``unstated`` and names why
in ``fidelity_reason`` (``REASONS``), so no port is left without either a statement or a stated reason.

The column records what the README *states*, never a measurement: a port marked ``faithful`` has not been shown to be.
Lineage (``lineage.py``) and the distributions (``distribution.py``) are the measurements to hold it against.
"""

import argparse
import collections
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
sys.path.insert(0, str(REPO_ROOT))  # before any gitgalaxy import: a shared venv may editable-install another checkout
sys.path.insert(0, str(HERE))

import doom_speedrun  # noqa: E402
from gitgalaxy.core.source_text import read_source  # noqa: E402

VOCAB = {
    "original": "the id Software release the study measures against",
    "faithful": "README states the aim of accurately reproducing the original, bugs included",
    "compatible": "README states compatibility with the original's demos, data or behaviour while changing or adding",
    "enhanced": "README states added features or improvements and makes no claim of fidelity",
    "divergent": "README disclaims being a port of, or exact to, the original (a rewrite, a recreation, 'not 100%')",
    "unstated": "no README, or the README says nothing about fidelity to the original",
}
REASONS = {
    "no-readme": "the repository has no README (or any prose) to read a claim from",
    "readme-silent": "the README (or release notes) never says how the port relates to the original's behaviour",
}
COLUMNS = ("fidelity", "fidelity_file", "fidelity_phrase")
CLAIMED = frozenset(VOCAB) - {"original", "unstated"}  # these need a README phrase
_MARKUP = re.compile(r"[*_`]")


def normalise(text):
    """Comparison form: markdown emphasis dropped, whitespace collapsed, case folded."""
    return " ".join(_MARKUP.sub("", text).split()).casefold()


def phrase_in(readme_text, phrase):
    return normalise(phrase) in normalise(readme_text)


def check_rows(rows, repos):
    """(problems, unchecked) for manifest ``rows``; ``repos`` is the directory of pinned clones."""
    problems, unchecked = [], []
    for row in rows:
        name = row["name"]
        value, file, phrase = (row.get(c) or "" for c in COLUMNS)
        if value not in VOCAB:
            problems.append(f"{name}: fidelity {value!r} is not one of {', '.join(VOCAB)}")
            continue
        reason = row.get("fidelity_reason") or ""
        if value == "unstated" and reason not in REASONS:
            problems.append(f"{name}: fidelity unstated needs a fidelity_reason, one of {', '.join(REASONS)}")
            continue
        if value != "unstated" and reason:
            problems.append(f"{name}: fidelity {value} must not carry a fidelity_reason")
            continue
        if value in CLAIMED and not (file and phrase):
            problems.append(f"{name}: fidelity {value} needs fidelity_file and fidelity_phrase")
            continue
        if value not in CLAIMED and (file or phrase):
            problems.append(f"{name}: fidelity {value} must not carry a README file or phrase")
            continue
        if not file:
            continue
        path = repos / name / file
        if not path.is_file():
            unchecked.append(name)
            continue
        if not phrase_in(read_source(path).text, phrase):
            problems.append(f"{name}: {file} no longer contains {phrase!r}")
    return problems, unchecked


def report(rows):
    """Markdown table of port counts per class x fidelity, each cell naming its ports."""
    cells = collections.defaultdict(list)
    for row in rows:
        cells[(row["class"], row.get("fidelity") or "unstated")].append(row["name"])
    lines = ["| class | " + " | ".join(VOCAB) + " |", "|---|" + "---|" * len(VOCAB)]
    for cls in sorted({c for c, _ in cells}):
        lines.append(
            f"| {cls} | " + " | ".join(", ".join(sorted(cells.get((cls, v), []))) or "-" for v in VOCAB) + " |"
        )
    totals = collections.Counter({v: sum(len(n) for (_, f), n in cells.items() if f == v) for v in VOCAB})
    lines.append("| **ports** | " + " | ".join(str(totals[v]) for v in VOCAB) + " |")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("action", choices=("check", "report"))
    ap.add_argument("--work", type=Path, default=doom_speedrun.DEFAULT_WORK, help="doom_speedrun work dir")
    ap.add_argument("--manifest", type=Path, help="alternate manifest CSV")
    ap.add_argument("--strict", action="store_true", help="a port whose clone is absent is an error")
    args = ap.parse_args(argv)
    rows = doom_speedrun.read_manifest(args.manifest)
    if args.action == "report":
        print(report(rows), end="")
        return 0
    problems, unchecked = check_rows(rows, args.work.resolve() / "repos")
    for p in problems:
        print(f"fidelity: {p}")
    if unchecked:
        print(f"fidelity: {len(unchecked)} unchecked (no clone under {args.work}/repos): {', '.join(unchecked)}")
    if args.strict and unchecked:
        return 1
    print(f"fidelity: {len(rows)} ports, {len(problems)} problems, {len(unchecked)} unchecked")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
