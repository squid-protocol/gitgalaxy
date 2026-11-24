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
    python tests/tools/family_rosetta_consistency.py --check-floor    # exit 1 when any silent cell exists (a --live cell resting on a raw reading alone is not counted)
    python tests/tools/family_rosetta_consistency.py --live           # planted families keep the manifest count; the rest are counted live
                                                                      # over the corpus sources, marked "(reading)" when silent
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
    return {
        (sig, lang)
        for e in entries
        for sig in str(e.get("signal", "")).split("|")
        for lang in e.get("languages_seen") or []
    }


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
    readings: set[tuple[str, str]] | None = None,
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
            **(
                {"reading_cells": rc}
                if (rc := sorted(lang for lang in cells if (fam, lang) in (readings or set())))
                else {}
            ),
            "not_applicable": sorted(f for f in mapped if fam not in defined[f]),
        }
    return result


def live_manifests(corpus: Path, folders: list[str], defined: dict[str, set[str]]) -> dict[str, dict[str, int]]:
    """{folder: {family: hits}} by running each defined rule over the Prism streams of the folder's source files.

    Unlike the blessed manifests this reaches every family the registry defines, planted or not. It counts raw rule hits (the comment
    surface too for the families `rule_probe` names), without the detector's post-filters, so it is a reading, not the engine's count.
    """
    import rule_probe as rp

    from gitgalaxy.core.prism import Prism
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    rp.ROSETTA = corpus / "data"
    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    out: dict[str, dict[str, int]] = {}
    for lang in folders:
        if lang not in defined:
            continue
        counts: dict[str, int] = dict.fromkeys(sorted(defined[lang]), 0)
        rules = LANGUAGE_DEFINITIONS[lang]["rules"]
        for _name, _root, path in rp.corpus_files(lang, "rosetta"):
            try:
                split = prism.split_streams(rp.read_source(path).text, lang)
            except OSError:
                continue
            for fam in counts:
                rule = rules.get(fam)
                if rule is None or not hasattr(rule, "finditer"):
                    continue
                counts[fam] += sum(len(list(rule.finditer(split[sn]))) for sn in rp.streams_for(fam, "auto"))
        out[lang] = counts
    return out


def merge_live(
    manifests: dict[str, dict[str, int]], live: dict[str, dict[str, int]]
) -> tuple[dict[str, dict[str, int]], set[tuple[str, str]]]:
    """(counts, readings): the blessed manifest count where a folder plants the family, else the live raw-rule count.

    The live count lacks the detector's post-filters, so it can disagree with the engine (six languages did in #9228). A planted family
    therefore keeps the engine's count; `readings` is the set of (family, language) cells that rest on the raw count alone.
    """
    merged: dict[str, dict[str, int]] = {}
    readings: set[tuple[str, str]] = set()
    for lang, counts in live.items():
        planted = manifests.get(lang, {})
        merged[lang] = {}
        for fam, n in counts.items():
            if fam in planted:
                merged[lang][fam] = planted[fam]
            else:
                merged[lang][fam] = n
                readings.add((fam, lang))
    return merged, readings


def drift(
    manifests: dict[str, dict[str, int]], live: dict[str, dict[str, int]]
) -> dict[str, dict[str, tuple[int, int]]]:
    """{language: {family: (manifest, live)}} where a family both sources read disagrees: a stale manifest or a post-filter."""
    return {
        lang: d
        for lang in sorted(live)
        if (
            d := {
                f: (manifests[lang][f], n)
                for f, n in live[lang].items()
                if f in manifests.get(lang, {}) and manifests[lang][f] != n
            }
        )
    }


def render_drift(drifted: dict) -> str:
    """The live-vs-manifest disagreements on planted families (manifest, live), one line per language."""
    if not drifted:
        return "\n## Live vs manifest\n\nEvery planted family reads the same live as in the manifests.\n"
    out = [
        "",
        "## Live vs manifest (manifest/live): the manifest count is used; the live count lacks a detector post-filter, or the manifest is stale",
        "",
    ]
    out += [
        f"- `{lang}`: " + ", ".join(f"{f}={m}/{n}" for f, (m, n) in sorted(d.items())) for lang, d in drifted.items()
    ]
    return "\n".join(out) + "\n"


def silent_cells(result: dict, include_readings: bool = True) -> list[tuple[str, str]]:
    """Silent (family, language) cells; `include_readings=False` drops those resting on a raw live count alone (not the engine's)."""
    return [
        (fam, lang)
        for fam, d in result["families"].items()
        for lang, v in d["verdicts"].items()
        if v == "silent" and (include_readings or lang not in d.get("reading_cells", ()))
    ]


def render_markdown(result: dict, corpus_sha: str = "") -> str:
    out = ["# keyword-rosetta cross-language consistency of the contracted families (#8863)", ""]
    out.append(f"Languages read: {result['languages']}" + (f"; corpus {corpus_sha}" if corpus_sha else "") + ".")
    out += [
        "",
        "| family | defined | fire | target | silent | over | under | ledgered | verdict |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
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
            tagged = [lang + (" (reading)" if lang in d.get("reading_cells", ()) else "") for lang in langs]
            out.append(
                f"- `{fam}` (target {d['target']}, fires in {d['fires']} of {d['defined']}): {', '.join(tagged)}"
            )
    if not silent:
        out.append("None.")
    for verdict in ("over", "under"):
        lines = [
            f"- `{fam}` (target {d['target']}): "
            + ", ".join(f"{lang}={d['counts'][lang]}" for lang, v in d["verdicts"].items() if v == verdict)
            for fam, d in sorted(result["families"].items())
            if verdict in d["verdicts"].values()
        ]
        out += ["", f"## {verdict.capitalize()} the target", ""] + (lines or ["None."])
    out += ["", "## Not judged", ""]
    out.append(
        "Contracted families the corpus does not plant (not testable here): "
        + (", ".join(f"`{f}`" for f in result["not_testable"]) or "none")
        + "."
    )
    nc = [
        f"`{f}` ({d['fires']} of {d['defined']})" for f, d in sorted(result["families"].items()) if not d["consensus"]
    ]
    out.append(
        "Families with no consensus (fire in under half of the languages that define them): "
        + (", ".join(nc) or "none")
        + "."
    )
    if result["unmapped_folders"]:
        out.append(
            "Corpus folders that are not a code language in the registry (skipped): "
            + ", ".join(result["unmapped_folders"])
            + "."
        )
    return "\n".join(out) + "\n"


def _corpus_sha(corpus: Path) -> str:
    try:
        r = subprocess.run(
            ["git", "-C", str(corpus), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=20
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--corpus",
        type=Path,
        default=None,
        help="keyword-rosetta checkout (default: $KEYWORD_ROSETTA_PATH or the sibling)",
    )
    ap.add_argument("--min-fire-share", type=float, default=MIN_FIRE_SHARE)
    ap.add_argument("--json", type=Path, default=None, help="also write the machine-readable result here")
    ap.add_argument(
        "--live",
        action="store_true",
        help="count every defined family's rule over the corpus sources, not the manifests",
    )
    ap.add_argument("--check-floor", action="store_true", help="exit 1 when any silent cell exists")
    args = ap.parse_args(argv)
    if not 0 < args.min_fire_share <= 1:
        print("--min-fire-share must be in (0, 1]", file=sys.stderr)
        return 2
    corpus = args.corpus or default_corpus()
    if not (corpus / "data").is_dir():
        print(
            f"keyword-rosetta corpus not found at {corpus} (set KEYWORD_ROSETTA_PATH): nothing was checked",
            file=sys.stderr,
        )
        return 2
    manifests, bad = load_corpus(corpus)
    if bad:
        print("unreadable manifests: " + ", ".join(bad), file=sys.stderr)
    if not manifests:
        print(f"no readable expected_signals.json under {corpus / 'data'}: nothing was checked", file=sys.stderr)
        return 2
    from family_validity_chart import engine_grid

    families, _languages, defined = engine_grid()
    drifted: dict = {}
    readings: set[tuple[str, str]] = set()
    if args.live:
        live = live_manifests(corpus, sorted(manifests), defined)
        drifted = drift(manifests, live)
        manifests, readings = merge_live(manifests, live)
    result = analyze(manifests, [f.key for f in families], defined, load_ledger(corpus), args.min_fire_share, readings)
    if not result["languages"]:
        print("no corpus folder maps to a registry language: nothing was checked", file=sys.stderr)
        return 2
    sys.stdout.write(render_markdown(result, _corpus_sha(corpus)))
    if args.live:
        sys.stdout.write(render_drift(drifted))
    if args.json:
        args.json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 1 if args.check_floor and silent_cells(result, include_readings=False) else 0


if __name__ == "__main__":
    sys.exit(main())
