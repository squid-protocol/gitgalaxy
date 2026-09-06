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
Census probe: what does the DERIVED per-function census say, per language, per file?

`tests/tools/rule_probe.py` answers "what does this rule match" and cannot answer
anything about `unreferenced_by_name`, `duplicate_logic`, `api_declared_orphans`
or a function's `usage_status`: those are not rules. They are computed once per
file in `detector.py`'s splice, from the extracted function list and the code
stream. #2806 rebuilt this script from scratch to measure one of them, the same
way #2765 rebuilt the rule probe before it was committed. This is that script.

USAGE
    # per-file census for one language, with each function's verdict
    python tests/tools/census_probe.py jcl --detail

    # every language, both corpora, snapshotted
    python tests/tools/census_probe.py all --json /tmp/census-before.json

    # after the change: the table rows
    python tests/tools/census_probe.py all --compare /tmp/census-before.json /tmp/census-after.json

WHAT IT MEASURES
    `StructuralExtractor.splice()` over `Prism.split_streams(...)`, i.e. the raw
    per-file extraction, BEFORE galaxyscope.py's Contextual Baseline Fix converts
    an imported file's census into `api`. That is the right layer for auditing the
    census itself and the wrong one for predicting a recorded `arch_api`.

    IT IS ALSO NOT THE PIPELINE. `language_lens.py` compiles every string value in
    a registry's `rules` into a regex before a real scan sees it, and nothing here
    (or in any unit test) goes through the lens -- #2806's first attempt declared a
    string helper inside `rules`, measured 0 here, recorded a full census in a real
    scan, and blessed a wrong golden master before anyone noticed. When the change
    under test is a REGISTRY DECLARATION rather than a regex, confirm it end to end
    with a real scan before blessing anything:

        galaxyscope <one-file-dir> --output /tmp/x --db-only
        sqlite3 /tmp/x/*_master.db "select file_path, state_unreferenced from file_data;"

Run it from a worktree with PYTHONPATH pointing at that worktree, so the registry
you probe is the one you are editing.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tests" / "tools"))

import rule_probe  # noqa: E402  (corpus discovery, shared deliberately)

from gitgalaxy.core.detector import StructuralExtractor  # noqa: E402
from gitgalaxy.core.prism import Prism  # noqa: E402
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS  # noqa: E402
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS  # noqa: E402

# The derived per-file keys this probe reports. All are computed in splice(), none
# is a registry rule, and every one of them has had its own upstream issue.
CENSUS_KEYS = ("unreferenced_by_name", "duplicate_logic")
USAGE_STATUS = {0: "ok", 1: "UNREFERENCED", 2: "duplicate"}


def probe(lang: str, corpus: str, prism: Prism, detail: bool) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for corpus_name, root, path in rule_probe.corpus_files(lang, corpus):
        try:
            src = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        streams = prism.split_streams(src, lang)
        try:
            result = StructuralExtractor(lang, LANGUAGE_DEFINITIONS).splice(
                streams["code_stream"], streams.get("comment_stream", ""), raw_content=src
            )
        except Exception as exc:  # a probe reports failures, it does not raise them
            out.setdefault(corpus_name, []).append({"file": str(path.relative_to(root)), "error": repr(exc)[:160]})
            continue
        equations = result.get("equations", {})
        functions = result.get("functions", [])
        record = {
            "file": str(path.relative_to(root)),
            "functions": len(functions),
            "api": equations.get("api", 0),
            "api_declared_orphans": result.get("api_declared_orphans", 0),
            **{key: equations.get(key, 0) for key in CENSUS_KEYS},
        }
        if detail:
            record["verdicts"] = [
                (f.get("name", ""), USAGE_STATUS.get(f.get("usage_status", 0), "?")) for f in functions
            ]
        out.setdefault(corpus_name, []).append(record)
    return out


def per_file(records: list[dict], key: str) -> float | None:
    scored = [r for r in records if "error" not in r]
    if not scored:
        return None
    return round(sum(r.get(key, 0) for r in scored) / len(scored), 2)


def print_language(lang: str, data: dict[str, list[dict]], key: str, detail: bool) -> None:
    for corpus_name, records in data.items():
        rate = per_file(records, key)
        print(f"{lang:16s} [{corpus_name}] files={len(records):<4d} {key}/file={rate}")
        if not detail:
            continue
        for record in records:
            if "error" in record:
                print(f"      {record['file']}: ERROR {record['error']}")
                continue
            verdicts = " ".join(f"{name}:{verdict}" for name, verdict in record.get("verdicts", []))
            print(
                f"      {record['file']:<28s} f={record['functions']:<3d} {key}={record.get(key, 0):<3d} | {verdicts}"
            )


def compare(before: dict, after: dict, key: str) -> None:
    """The audit table rows, plus the corpus median each cell is judged against."""
    languages = sorted(set(before) | set(after))
    print(f"| language | crucible {key} | keyword-rosetta {key} |")
    print("|---|---|---|")
    medians: dict[str, list[float]] = {"crucible": [], "rosetta": []}
    for lang in languages:

        def cell(corpus: str, lang: str = lang) -> str:
            was = per_file(before.get(lang, {}).get(corpus, []), key)
            now = per_file(after.get(lang, {}).get(corpus, []), key)
            if now is not None:
                medians[corpus].append(now)
            if was is None and now is None:
                return "--"
            return f"{now}" if was == now else f"**{was} -> {now}**"

        print(f"| `{lang}` | {cell('crucible')} | {cell('rosetta')} |")
    for corpus, values in medians.items():
        if values:
            print(f"\ncorpus median ({corpus}): {statistics.median(values)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("lang", help="a registry key, or `all`")
    parser.add_argument("--key", default="unreferenced_by_name", choices=CENSUS_KEYS)
    parser.add_argument("--corpus", choices=("crucible", "rosetta", "both"), default="both")
    parser.add_argument("--detail", action="store_true", help="every function's verdict, per file")
    parser.add_argument("--json", help="write the per-language snapshot here")
    parser.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"), help="print audit-table rows")
    args = parser.parse_args(argv)

    if args.compare:
        before, after = (json.loads(Path(p).read_text()) for p in args.compare)
        compare(before, after, args.key)
        return 0

    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    languages = sorted(LANGUAGE_DEFINITIONS) if args.lang == "all" else [args.lang]
    snapshot: dict[str, dict] = {}
    for lang in languages:
        data = probe(lang, args.corpus, prism, args.detail)
        snapshot[lang] = data
        print_language(lang, data, args.key, args.detail)
    if args.json:
        Path(args.json).write_text(json.dumps(snapshot, indent=1))
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
