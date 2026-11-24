#!/usr/bin/env python3
"""
family_rosetta_consistency.py -- cross-language consistency of the contracted keyword families on keyword-rosetta (#8863, step 2).

keyword-rosetta writes the same 12-probe program in every signature-bearing language and records the count each signal reads in
`data/<lang>/expected_signals.json` (the blessed engine output; `rosetta_audit.py` keeps it equal to the engine). A family that fires
for the probe in most languages that have a rule for it, and reads 0 in a few, has a gap in those few without any parser oracle.

WHAT IT READS
    Families:   the contracts in gitgalaxy/standards/signal_contracts.py that appear as a key in at least one manifest (a family the
                corpus does not plant is listed as "not testable here", never dropped).
    Languages:  a corpus folder that maps to a registry language; the family counts only where the language has a rule for it
                (a language without a rule is N/A, not a gap).
    Counts:     the manifest counts summed over the folder's files (the probe plants are spread over main, a, b and c).
    Target:     the most frequent non-zero count among the languages that define the rule (ties: the smaller count). It is a reading
                of the corpus, not a claim about the contract.

CELL VERDICTS
    agrees    the count equals the target
    silent    the language has a rule, the family fires in at least --min-fire-share of the defined languages, and it reads 0 here: the gap
    over      above the target        under   non-zero and below it
    ledgered  a deviation (not the target) that keyword-rosetta's deviation_ledger.json names for this (signal, language): known and
              explained, never called a gap
    A family that fires in fewer than --min-fire-share of its defined languages has "no consensus": its cells are listed, not judged.

USAGE
    python tests/tools/family_rosetta_consistency.py                  # markdown report to stdout
    python tests/tools/family_rosetta_consistency.py --json OUT.json  # also write the machine-readable result
    python tests/tools/family_rosetta_consistency.py --check-floor    # exit 1 when any silent cell exists
    KEYWORD_ROSETTA_PATH=<checkout> overrides the default sibling ../keyword-rosetta.

EXIT   0 report written, 1 --check-floor and a silent cell, 2 the report did not run (no corpus, no manifests, bad arguments).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

MIN_FIRE_SHARE = 0.5
VERDICTS = ("agrees", "silent", "over", "under", "ledgered")


def default_corpus() -> Path:
    """$KEYWORD_ROSETTA_PATH, else ../keyword-rosetta from the checkout, else ../../keyword-rosetta from a worktree."""
    if os.environ.get("KEYWORD_ROSETTA_PATH"):
        return Path(os.environ["KEYWORD_ROSETTA_PATH"])
    for base in (REPO_ROOT.parent, REPO_ROOT.parent.parent):
        if (base / "keyword-rosetta" / "data").is_dir():
            return base / "keyword-rosetta"
    return REPO_ROOT.parent / "keyword-rosetta"


def _folder_counts(files: dict) -> dict[str, int]:
    """The integer signal counts of every file in a manifest, summed per key (the plants are spread over main, a, b and c)."""
    total: Counter = Counter()
    for entry in files.values():
        total.update({k: v for k, v in entry.items() if isinstance(v, int) and not isinstance(v, bool)})
    return dict(total)


def load_corpus(corpus: Path) -> tuple[dict[str, dict[str, int]], list[str]]:
    """({folder: {family: count}}, folders whose manifest is unreadable) from `data/*/expected_signals.json`."""
    manifests: dict[str, dict[str, int]] = {}
    bad: list[str] = []
    for path in sorted((corpus / "data").glob("*/expected_signals.json")):
        try:
            counts = _folder_counts(json.loads(path.read_text(encoding="utf-8")).get("files") or {})
        except (OSError, ValueError, AttributeError):
            bad.append(path.parent.name)
            continue
        manifests[path.parent.name] = counts
    return manifests, bad


def load_ledger(corpus: Path) -> set[tuple[str, str]]:
    """{(signal, language folder)} the deviation ledger explains; a missing or unreadable ledger explains nothing."""
    try:
        entries = json.loads((corpus / "deviation_ledger.json").read_text(encoding="utf-8")).get("entries") or []
    except (OSError, ValueError, AttributeError):
        return set()
    return {(sig, lang) for e in entries for sig in str(e.get("signal", "")).split("|") for lang in e.get("languages_seen") or []}


def target_count(counts: list[int]) -> int:
    """The most frequent non-zero count (ties: the smaller); 0 when nothing fires."""
    nonzero = Counter(c for c in counts if c > 0)
    if not nonzero:
        return 0
    return min(nonzero, key=lambda c: (-nonzero[c], c))


def analyze(
    manifests: dict[str, dict[str, int]],
    families: list[str],
    defined: dict[str, set[str]],
    ledger: set[tuple[str, str]] | None = None,
    min_fire_share: float = MIN_FIRE_SHARE,
) -> dict:
    """The consistency table: a pure function of the manifests, the contracted families, the registry's defined rules and the ledger."""
    ledger = ledger or set()
    unmapped = sorted(f for f in manifests if f not in defined)
    mapped = [f for f in sorted(manifests) if f not in unmapped]
    planted = {k for m in manifests.values() for k in m}
    result: dict = {
        "languages": len(mapped),
        "unmapped_folders": unmapped,
        "not_testable": sorted(f for f in families if f not in planted),
        "families": {},
    }
    for fam in families:
        if fam not in planted:
            continue
        rows = {f: manifests[f][fam] for f in mapped if fam in defined[f] and fam in manifests[f]}
        n_defined = len(rows)
        fires = sum(1 for c in rows.values() if c > 0)
        target = target_count(list(rows.values()))
        consensus = n_defined > 0 and fires >= min_fire_share * n_defined
        cells: dict[str, str] = {}
        for lang, count in rows.items():
            if not consensus:
                continue
            if count == target:
                cells[lang] = "agrees"
            elif (fam, lang) in ledger:
                cells[lang] = "ledgered"
            elif count == 0:
                cells[lang] = "silent"
            else:
                cells[lang] = "over" if count > target else "under"
        result["families"][fam] = {
            "defined": n_defined,
            "fires": fires,
            "target": target,
            "consensus": consensus,
            "counts": dict(sorted(rows.items())),
            "verdicts": dict(sorted(cells.items())),
            "not_applicable": sorted(f for f in mapped if fam not in defined[f]),
        }
    return result


def silent_cells(result: dict) -> list[tuple[str, str]]:
    return [(fam, lang) for fam, d in result["families"].items() for lang, v in d["verdicts"].items() if v == "silent"]


def render_markdown(result: dict, corpus_sha: str = "") -> str:
    out = ["# keyword-rosetta cross-language consistency of the contracted families (#8863)", ""]
    out.append(f"Languages read: {result['languages']}" + (f"; corpus {corpus_sha}" if corpus_sha else "") + ".")
    out += ["", "| family | defined | fire | target | silent | over | under | ledgered | verdict |", "|---|---|---|---|---|---|---|---|---|"]
    for fam, d in sorted(result["families"].items()):
        tally = Counter(d["verdicts"].values())
        state = "consensus" if d["consensus"] else "no consensus"
        row = [fam, d["defined"], d["fires"], d["target"]] + [tally[v] for v in ("silent", "over", "under", "ledgered")]
        out.append("| " + " | ".join(str(x) for x in row) + f" | {state} |")
    silent = silent_cells(result)
    out += ["", f"## Silent cells ({len(silent)}): the language has a rule, most languages fire, this one reads 0", ""]
    for fam, d in sorted(result["families"].items()):
        langs = [lang for lang, v in d["verdicts"].items() if v == "silent"]
        if langs:
            out.append(f"- `{fam}` (target {d['target']}, fires in {d['fires']} of {d['defined']}): {', '.join(langs)}")
    if not silent:
        out.append("None.")
    for verdict in ("over", "under"):
        lines = [
            f"- `{fam}` (target {d['target']}): " + ", ".join(f"{lang}={d['counts'][lang]}" for lang, v in d["verdicts"].items() if v == verdict)
            for fam, d in sorted(result["families"].items())
            if verdict in d["verdicts"].values()
        ]
        out += ["", f"## {verdict.capitalize()} the target", ""] + (lines or ["None."])
    out += ["", "## Not judged", ""]
    out.append("Contracted families the corpus does not plant (not testable here): " + (", ".join(f"`{f}`" for f in result["not_testable"]) or "none") + ".")
    nc = [f"`{f}` ({d['fires']} of {d['defined']})" for f, d in sorted(result["families"].items()) if not d["consensus"]]
    out.append("Planted families with no consensus (fire in under half of the languages that define them): " + (", ".join(nc) or "none") + ".")
    if result["unmapped_folders"]:
        out.append("Corpus folders that are not a code language in the registry (skipped): " + ", ".join(result["unmapped_folders"]) + ".")
    return "\n".join(out) + "\n"


def _corpus_sha(corpus: Path) -> str:
    try:
        r = subprocess.run(["git", "-C", str(corpus), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--corpus", type=Path, default=None, help="keyword-rosetta checkout (default: $KEYWORD_ROSETTA_PATH or the sibling)")
    ap.add_argument("--min-fire-share", type=float, default=MIN_FIRE_SHARE)
    ap.add_argument("--json", type=Path, default=None, help="also write the machine-readable result here")
    ap.add_argument("--check-floor", action="store_true", help="exit 1 when any silent cell exists")
    args = ap.parse_args(argv)
    if not 0 < args.min_fire_share <= 1:
        print("--min-fire-share must be in (0, 1]", file=sys.stderr)
        return 2
    corpus = args.corpus or default_corpus()
    if not (corpus / "data").is_dir():
        print(f"keyword-rosetta corpus not found at {corpus} (set KEYWORD_ROSETTA_PATH): nothing was checked", file=sys.stderr)
        return 2
    manifests, bad = load_corpus(corpus)
    if bad:
        print("unreadable manifests: " + ", ".join(bad), file=sys.stderr)
    if not manifests:
        print(f"no readable expected_signals.json under {corpus / 'data'}: nothing was checked", file=sys.stderr)
        return 2
    from family_validity_chart import engine_grid

    families, _languages, defined = engine_grid()
    result = analyze(manifests, [f.key for f in families], defined, load_ledger(corpus), args.min_fire_share)
    if not result["languages"]:
        print("no corpus folder maps to a registry language: nothing was checked", file=sys.stderr)
        return 2
    sys.stdout.write(render_markdown(result, _corpus_sha(corpus)))
    if args.json:
        args.json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 1 if args.check_floor and silent_cells(result) else 0


if __name__ == "__main__":
    sys.exit(main())
