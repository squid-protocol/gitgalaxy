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
Scope a golden-master bless: bucket the uncapped diff by report section, by
corpus language and by leaf key, and list the artifacts that moved between the
parsed and the excluded queue.

CLAUDE.md ("Scoping a bless") explains why crucible_check.py's output cannot be
used for this -- it prints at most 50 of what is routinely 5,000+ differences.
The recipe it gives (load_and_sanitize + deep_compare) is what this tool runs,
plus the bucketing every bless review does by hand.

USAGE
    git show HEAD:tests/golden_master_zero_dep_audit.json > /tmp/old.json
    LANGUAGE_CRUCIBLE_PATH=... python tests/tools/crucible_check.py --update --yes   # bless
    python tests/tools/bless_scope.py /tmp/old.json tests/golden_master_zero_dep_audit.json
    python tests/tools/bless_scope.py /tmp/old.json tests/golden_master_zero_dep_audit.json --show 20 --grep "State Mutations"

Read the output top-down: the topological X/Y/Z volume is the corpus-wide 3D
re-solve and is attributable as a class; the per-file section-7 keys say WHICH
signals moved; the language bucket says WHERE; "newly parsed / newly excluded"
catches a rule change that pushed a file across the aperture's density guard
(#2765: a cobol copybook lost 500 phantom END-STRING hits and started parsing).
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import golden_diff as gd

_AT = re.compile(r"MISMATCH at (/[^:]+):")
_LANG = re.compile(r"/([a-z_\-]+)/[^/]+/[^/]*\.[a-zA-Z0-9]+")


def _unparsable(doc: dict) -> dict[str, str]:
    for k, v in doc.items():
        if str(k).startswith("5. Unparsable"):
            return {x.get("Path"): x.get("Diagnostic Reason") for x in v}
    return {}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("old", nargs="?", help="pre-bless fixture (omit with --from-head)")
    ap.add_argument("new")
    ap.add_argument(
        "--from-head",
        action="store_true",
        help="#2916: take the pre-bless fixture from `git show HEAD:<new>` itself, "
        "so the whole recipe is one command run after the bless",
    )
    ap.add_argument("--show", type=int, default=8, help="substantive diff lines to print")
    ap.add_argument("--grep", help="only print diff lines containing this text")
    ap.add_argument(
        "--summary",
        action="store_true",
        help="#2916: append the PR-body block -- one line per (file x leaf keys)",
    )
    args = ap.parse_args(argv)

    if args.from_head:
        if args.old is not None:
            ap.error("--from-head takes only the NEW fixture path")
        import subprocess
        import tempfile

        rel = str(Path(args.new).resolve().relative_to(Path.cwd().resolve()))
        blob = subprocess.run(
            ["git", "show", f"HEAD:{rel}"], capture_output=True, text=True, check=True
        ).stdout
        tf = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        tf.write(blob)
        tf.close()
        args.old = tf.name
    elif args.old is None:
        ap.error("old fixture required (or pass --from-head)")

    old, new = gd.load_and_sanitize(args.old), gd.load_and_sanitize(args.new)
    diffs = [str(d) for d in gd.deep_compare(old, new)]
    topo_set = {d for d in diffs if "Topological Coordinates" in d or re.search(r"/[XYZ]:", d)}
    rest = [d for d in diffs if d not in topo_set]
    print(f"{len(diffs)} differences: {len(topo_set)} topological (X/Y/Z re-solve), {len(rest)} substantive")

    sections: collections.Counter = collections.Counter()
    langs: collections.Counter = collections.Counter()
    leaves: collections.Counter = collections.Counter()
    for d in rest:
        m = _AT.search(d)
        path = m.group(1) if m else "?"
        segs = path.strip("/").split("/")
        sections[segs[0]] += 1
        leaves[segs[-1][:48]] += 1
        ml = _LANG.search(path)
        if ml:
            langs[ml.group(1)] += 1

    def table(title: str, counter: collections.Counter, n: int) -> None:
        print(f"\n{title}")
        for k, v in counter.most_common(n):
            print(f"  {v:6d}  {k}")

    table("by section", sections, 10)
    table("by leaf key", leaves, 25)
    table("by language (per-file entries)", langs, 60)

    o = _unparsable(json.loads(Path(args.old).read_text(encoding="utf-8")))
    nw = _unparsable(json.loads(Path(args.new).read_text(encoding="utf-8")))
    moved_in = [(p, o[p]) for p in o if p not in nw]
    moved_out = [(p, nw[p]) for p in nw if p not in o]
    print(f"\nnewly parsed (was excluded): {moved_in or 'none'}")
    print(f"newly excluded (was parsed): {moved_out or 'none'}")

    shown = [d for d in rest if not args.grep or args.grep in d][: args.show]
    if shown:
        print(f"\nfirst {len(shown)} substantive lines{' matching ' + repr(args.grep) if args.grep else ''}:")
        for d in shown:
            print("  " + d[:240])

    if args.summary:
        # #2916: the PR-body block -- one line per file, listing the leaf keys that
        # moved in it, so a reviewer sees the bless's shape without the raw diff.
        by_file: dict[str, set] = collections.defaultdict(set)
        for d in rest:
            m = _AT.search(d)
            if not m:
                continue
            segs = m.group(1).strip("/").split("/")
            ml = _LANG.search(m.group(1))
            fname = next(
                (s for s in segs if re.search(r"\.[A-Za-z0-9]{1,8}$", s) and not s[:1].isdigit()),
                segs[0],
            )
            key = f"{ml.group(1) + '/' if ml else ''}{fname}"
            by_file[key].add(segs[-1][:40])
        print(f"\n--summary ({len(by_file)} files moved):")
        for f in sorted(by_file):
            keys = sorted(by_file[f])
            head = ", ".join(keys[:6])
            more = f" (+{len(keys) - 6} more)" if len(keys) > 6 else ""
            print(f"  {f}: {head}{more}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
