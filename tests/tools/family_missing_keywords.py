#!/usr/bin/env python3
"""
family_missing_keywords.py -- missing-keyword mining per family and language (#8863, step 3). Report only.

family_oracle.py asks a real parser what each function does and scores every keyword family against it. Where the parser sees the
construct and the family column reads 0, the tokens that triggered the oracle are the candidate additions to the family's rule. This tool
ranks those tokens per (language, family) cell and merges the ones that recur across languages. It adds no oracle logic: it reads
`family_oracle.score()` results.

WHAT IT READS
    --scan LANG:DB:SRC    a finished scan database and the directory that was scanned (scored with family_oracle.score, language LANG)
    --result LANG:FILE    a saved `family_oracle.py --json` result for LANG. That file holds only the top N tokens the run asked for
                          (default 5): a result capped at 5 is flagged, mine it with a larger --top for a full list.
    Both repeat, and may be mixed.

WHAT A ROW MEANS
    token    the oracle's name for the callee/keyword/operator it saw in a function the family read 0 for
    count    occurrences of the token across those missed functions (occurrences, not distinct functions)
    per fn   count / missed functions: about 1 or more means the token is in most missed functions
    A cell with fewer than --min-functions oracle functions is "thin": listed, never ranked. A cell with no missed function is omitted.
    The oracle's callee lists are a second reading of the contract, not independent proof: a candidate is a question, and each one is to be
    timed on keyword-rosetta and language-crucible before it is merged (step 4).

USAGE
    python tests/tools/family_missing_keywords.py --scan go:scan_master.db:/path/to/src --top 25
    python tests/tools/family_missing_keywords.py --result rust:rust.json --json OUT.json

EXIT   0 report written, 2 nothing ran (no input, a bad spec, an unreadable result, a language with no oracle in every input).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

DEFAULT_TOP = 25
DEFAULT_MIN_FUNCTIONS = 10
CAPPED_AT = 5  # family_oracle.py's default --top: a saved result with exactly this many tokens may be cut short


def missed_functions(fam: dict) -> int:
    """The functions where the oracle saw the construct and the family did not: oracle functions times (1 - recall)."""
    n = fam.get("oracle_functions") or 0
    recall = fam.get("recall")
    return n if recall is None else round(n * (1 - recall))


def mine(results: dict[str, dict], top: int = DEFAULT_TOP, min_functions: int = DEFAULT_MIN_FUNCTIONS) -> dict:
    """The mining table, a pure function of {language: family_oracle.score() result}.

    {"cells": [{language, family, rule, oracle_functions, recall, status, missed, thin, capped, tokens: [{token, count, per_fn}]}],
     "shared": {family: [{token, count, languages}]}}
    """
    cells = []
    for lang in sorted(results):
        for fam in results[lang].get("families", []):
            tokens = [(str(t), int(c)) for t, c in fam.get("missed_tokens") or []]
            missed = missed_functions(fam)
            if missed <= 0 and not tokens:
                continue
            tokens.sort(key=lambda tc: (-tc[1], tc[0]))
            thin = (fam.get("oracle_functions") or 0) < min_functions
            cell = {
                "language": lang,
                "family": fam["family"],
                "rule": fam.get("rule"),
                "oracle_functions": fam.get("oracle_functions") or 0,
                "recall": fam.get("recall"),
                "status": fam.get("status"),
                "missed": missed,
                "thin": thin,
                "tokens": [
                    {"token": t, "count": c, "per_fn": round(c / missed, 2) if missed else None}
                    for t, c in tokens[:top]
                ],
            }
            if len(tokens) == CAPPED_AT and top > CAPPED_AT:
                cell["capped"] = True  # added only when set (an always-present empty key breaks equality tests)
            cells.append(cell)
    merged: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(lambda: [0, []]))
    for cell in cells:
        if cell["thin"]:
            continue
        for t in cell["tokens"]:
            slot = merged[cell["family"]][t["token"]]
            slot[0] += t["count"]
            slot[1].append(cell["language"])
    shared = {
        fam: sorted(
            (
                {"token": tok, "count": n, "languages": sorted(langs)}
                for tok, (n, langs) in toks.items()
                if len(langs) > 1
            ),
            key=lambda r: (-len(r["languages"]), -r["count"], r["token"]),
        )
        for fam, toks in sorted(merged.items())
    }
    return {"cells": cells, "shared": {f: rows for f, rows in shared.items() if rows}}


def render_markdown(mined: dict, skipped: list[str] | None = None) -> str:
    out = ["# Missing-keyword mining per family and language (#8863, report only)", ""]
    out.append(
        "Tokens the parser oracle saw in functions where the family read 0: candidate additions, each to be timed on "
        "keyword-rosetta and language-crucible before merging. Counts are occurrences, not distinct functions."
    )
    if skipped:
        out += ["", "Languages with no oracle (skipped): " + ", ".join(sorted(skipped)) + "."]
    ranked = [c for c in mined["cells"] if not c["thin"] and c["tokens"]]
    thin = [c for c in mined["cells"] if c["thin"]]
    out += ["", f"## Cells with missed functions ({len(ranked)})", ""]
    for c in ranked:
        recall = "n/a" if c["recall"] is None else f"{c['recall']:.2f}"
        out.append(
            f"### {c['language']} / {c['family']}: {c['missed']} of {c['oracle_functions']} missed (recall {recall}, {c['status']})"
        )
        if c.get("capped"):
            out.append("(the saved result was capped at 5 tokens: rerun with a larger --top)")
        out += ["", "| token | count | per fn |", "|---|---|---|"]
        out += [f"| `{t['token']}` | {t['count']} | {t['per_fn']} |" for t in c["tokens"]]
        out.append("")
    if not ranked:
        out.append("None.")
    out += ["", "## Shared across languages", ""]
    if mined["shared"]:
        for fam, rows in mined["shared"].items():
            out.append(
                f"- `{fam}`: " + ", ".join(f"`{r['token']}` ({r['count']}; {', '.join(r['languages'])})" for r in rows)
            )
    else:
        out.append("None.")
    out += ["", f"## Thin cells, not ranked ({len(thin)})", ""]
    out.append(
        "; ".join(f"{c['language']}/{c['family']} ({c['oracle_functions']} fn)" for c in thin) + "."
        if thin
        else "None."
    )
    return "\n".join(out) + "\n"


def _split(spec: str, parts: int) -> list[str]:
    raw = spec.split(":")
    bits: list[str] = []
    for tok in raw:
        # a Windows drive letter ("C" then "\\x" or "/x") belongs to the path before it, not a field of its own
        if len(bits) > 1 and len(bits[-1]) == 1 and bits[-1].isalpha() and tok[:1] in ("\\", "/"):
            bits[-1] += ":" + tok
        else:
            bits.append(tok)
    if len(bits) > parts:
        bits = [*bits[: parts - 1], ":".join(bits[parts - 1 :])]
    if len(bits) != parts or not all(bits):
        raise ValueError(f"bad spec {spec!r}")
    return bits


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--scan", action="append", default=[], metavar="LANG:DB:SRC")
    ap.add_argument("--result", action="append", default=[], metavar="LANG:FILE")
    ap.add_argument("--top", type=int, default=DEFAULT_TOP, help="tokens kept per cell (and asked of --scan)")
    ap.add_argument("--min-functions", type=int, default=DEFAULT_MIN_FUNCTIONS)
    ap.add_argument("--json", type=Path, default=None, help="also write the machine-readable result here")
    args = ap.parse_args(argv)
    if not args.scan and not args.result:
        print("give at least one --scan LANG:DB:SRC or --result LANG:FILE: nothing was checked", file=sys.stderr)
        return 2
    if args.top < 1:
        print("--top must be at least 1", file=sys.stderr)
        return 2
    results: dict[str, dict] = {}
    skipped: list[str] = []
    try:
        for spec in args.result:
            lang, path = _split(spec, 2)
            results[lang] = json.loads(Path(path).read_text(encoding="utf-8"))
        scans = [_split(spec, 3) for spec in args.scan]
    except (ValueError, OSError) as exc:
        print(f"unreadable input: {exc}", file=sys.stderr)
        return 2
    if scans:
        import family_oracle

        for lang, db, src in scans:
            try:
                results[lang] = family_oracle.score(Path(db), Path(src), lang, top=args.top)
            except SystemExit:
                skipped.append(lang)
            except Exception as exc:
                print(f"{lang}: could not score {db}: {exc}", file=sys.stderr)
                return 2
    if not results:
        print("no language had an oracle: nothing was checked", file=sys.stderr)
        return 2
    mined = mine(results, args.top, args.min_functions)
    sys.stdout.write(render_markdown(mined, skipped))
    if args.json:
        args.json.write_text(json.dumps(mined, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
