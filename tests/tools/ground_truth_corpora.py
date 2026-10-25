#!/usr/bin/env python3
"""Which pinned corpora a ground-truth part must scan before its pytest share runs (#5543, option (b)).

    python3 tests/tools/ground_truth_corpora.py [--all] [--collected FILE]      # prints one corpus name per line

A part with no warm job scans its corpora itself. Only a few tests read a scan DB (`mainframe_corpus.scan`); the rest read
the clone. READERS names those tests, so a part scans the corpora its share reads, not all of them. `--collected` is the
output of `pytest --collect-only -q` with the part's --splits / --group. `--all` is for the part that runs the ledger gate
(it scores every corpus). A missing or empty file, or an id the table cannot place, means every corpus: over-scanning
costs time, never a result, because `mainframe_corpus.scan` is lazy and lock-protected, so an under-scan is also only slow.
Stdlib only: this runs before anything else is known to import.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CORPORA = Path(__file__).resolve().parents[1] / "cobol_mainframe" / "corpora.json"

PER_CORPUS = None  # the test is parametrized by corpus: the id in brackets is the corpus name

# test module -> {test function: PER_CORPUS or the corpora its body scans}; tests/tools/test_ground_truth_corpora.py
# fails when a module under tests/cobol_mainframe/ scans a corpus and is not listed here
READERS: dict[str, dict[str, tuple[str, ...] | None]] = {
    "test_completeness.py": {"test_pinned_corpus_completeness": PER_CORPUS},
    "test_refraction_differential.py": {"test_full_corpus_no_new_unexplained": PER_CORPUS},
    "test_template_file_lineage_4771.py": {"test_zecs_003_file_op_reaches_the_zc_id_file_store": ("zecs",)},
}


def corpus_names(path: Path = CORPORA) -> list[str]:
    return [c["name"] for c in json.loads(path.read_text(encoding="utf-8"))["corpora"]]


def corpora_for(node_ids: list[str], names: list[str]) -> list[str]:
    """The corpora (manifest order) the given pytest node ids read; every corpus when there is nothing to go by."""
    ids = [n.strip() for n in node_ids if "::" in n]
    if not ids:
        return list(names)
    need: set[str] = set()
    for nid in ids:
        path, _, rest = nid.partition("::")
        func = rest.split("[", 1)[0].rsplit("::", 1)[-1]
        readers = READERS.get(path.rsplit("/", 1)[-1], {})
        if func not in readers:
            continue
        fixed = readers[func]
        if fixed is not PER_CORPUS:
            need.update(fixed)
            continue
        param = re.search(r"\[([^\]]*)\]$", rest)
        if not param or param.group(1) not in names:
            return list(names)
        need.add(param.group(1))
    return [n for n in names if n in need]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true", help="every corpus (the part that runs the ledger gate)")
    ap.add_argument("--collected", type=Path, help="pytest --collect-only -q output for this part's share")
    args = ap.parse_args(argv)
    names = corpus_names()
    if args.all or not args.collected or not args.collected.is_file():
        picked = names
    else:
        picked = corpora_for(args.collected.read_text(encoding="utf-8").splitlines(), names)
    print(f"scanning {len(picked)} of {len(names)} corpora", file=sys.stderr)
    for n in picked:
        print(n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
