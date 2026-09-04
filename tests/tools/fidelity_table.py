# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""Generate gitgalaxy/standards/fidelity_table.py from the keyword-rosetta control corpus.

The corpus plants an identical program in every language and records, per language and
per signal, how many hits the engine measured (`docs/bias_data.json`, summed over the
language's shell files) against how many the SPEC planted (the corpus-wide median of the
`data/<lang>/expected_signals.json` manifests -- a language's own manifest is measured by
construction and cannot be its reference). The per-signal Fidelity Coefficient is

    fc(lang, signal) = min(1.0, planted / measured)

so a rule that fires 3 times on 2 planted constructs credits each hit at 2/3 and
identical planted defence earns identical defence credit in every language -- the
alignment keyword-rosetta gates, applied at the measurement layer (#2716). Under-firing
(measured < planted) stays at 1.0 on purpose: that is a rule to fix, and a coefficient
that compensates for a fixable gap is a way to stop fixing it. Ledgered n/a, unplanted
and unmeasured cells are 1.0 as well -- there is nothing to credit.

Usage:
    python tests/tools/fidelity_table.py            # rewrite the module from ../keyword-rosetta
    python tests/tools/fidelity_table.py --check    # exit 1 if the committed module is stale
    python tests/tools/fidelity_table.py --docs     # refresh the generated tables in docs/wiki/08-03
    KEYWORD_ROSETTA_PATH=/path python tests/tools/fidelity_table.py

Only the signals the engine actually scales are load-bearing today (safety, test, doc,
ownership -- see SignalProcessor.FIDELITY_SIGNALS); the full intersection is emitted so
#2719 can read the rest without a second generator.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import importlib
import json
import os
import shutil
import statistics
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = Path(os.environ.get("KEYWORD_ROSETTA_PATH", REPO_ROOT.parent / "keyword-rosetta"))
OUTPUT = REPO_ROOT / "gitgalaxy" / "standards" / "fidelity_table.py"
WIKI_PAGE = REPO_ROOT / "docs" / "wiki" / "08-03-transforming-regex-counts.md"
GENERATED_LINE = "# generated:"


_GIT_BIN = shutil.which("git")


def _corpus_sha(corpus: Path) -> str:
    if not _GIT_BIN:
        return "unknown"
    try:
        out = subprocess.run(  # noqa: S603 -- _GIT_BIN resolved absolute, fixed args
            [_GIT_BIN, "-C", str(corpus), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def build_table(corpus: Path) -> tuple[dict[str, dict[str, float]], list[str], dict[str, str]]:
    bias = json.loads((corpus / "docs" / "bias_data.json").read_text())
    metrics: dict[str, dict[str, float | None]] = bias["metrics"]
    na: dict[str, dict[str, str]] = bias.get("na", {})
    languages: list[str] = sorted(bias["languages"])
    if not languages:
        raise SystemExit("fidelity_table: corpus lists zero languages -- refusing to generate an empty table")

    planted: dict[str, dict[str, int]] = {}
    for lang in languages:
        manifest = corpus / "data" / lang / "expected_signals.json"
        if not manifest.exists():
            continue
        files = json.loads(manifest.read_text()).get("files", {})
        totals: dict[str, int] = {}
        for counts in files.values():
            for sig, n in counts.items():
                if isinstance(n, int):
                    totals[sig] = totals.get(sig, 0) + n
        planted[lang] = totals

    signals = sorted({s for t in planted.values() for s in t} & set(metrics))
    if not signals:
        raise SystemExit("fidelity_table: no planted signal is also measured -- corpus layout changed?")

    # The planted reference is the SPEC's plant, which every language's manifest
    # carries identically except where a ledger entry blesses a deviation -- so the
    # corpus-wide median of the manifests IS the plant (safety 2, test 2, doc 1,
    # ownership 1, ...), and it is what bias_report.py bands against. A language's
    # own manifest cannot be its reference: that is measured-by-construction.
    reference: dict[str, float] = {}
    for sig in signals:
        vals = [t[sig] for lang, t in planted.items() if sig in t and not na.get(sig, {}).get(lang)]
        reference[sig] = statistics.median(vals) if vals else 0.0

    table: dict[str, dict[str, float]] = {}
    for lang in languages:
        row: dict[str, float] = {}
        for sig in signals:
            p = reference[sig]
            m = metrics.get(sig, {}).get(lang)
            if na.get(sig, {}).get(lang) or not p or not isinstance(m, (int, float)) or m <= 0:
                row[sig] = 1.0
            else:
                row[sig] = round(min(1.0, p / m), 4)
        table[lang] = row

    prov = {
        "corpus": "keyword-rosetta",
        "corpus_sha": _corpus_sha(corpus),
        "engine_mode": str(bias.get("engine_mode", "unknown")),
        "languages": str(len(table)),
        "signals": str(len(signals)),
    }
    return table, signals, prov


def render(table: dict[str, dict[str, float]], signals: list[str], prov: dict[str, str]) -> str:
    lines = [
        "# ==============================================================================",
        "# GitGalaxy",
        "# Copyright (c) 2026 Joe Esquibel",
        "#",
        "# This source code is licensed under the PolyForm Noncommercial License 1.0.0.",
        "# You may not use this file except in compliance with the License.",
        "# A copy of the license can be found in the LICENSE file in the root directory",
        "# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/",
        "# ==============================================================================",
        "# GENERATED by tests/tools/fidelity_table.py from the keyword-rosetta control corpus.",
        "# Do not edit by hand -- rerun the tool; `--check` fails CI when this is stale.",
        f"# corpus: {prov['corpus']} {prov['corpus_sha']} | engine_mode: {prov['engine_mode']}",
        f"{GENERATED_LINE} {_dt.datetime.now(_dt.timezone.utc).date().isoformat()}",
        '"""Per-language, per-signal Fidelity Coefficients: fc = min(1, planted / measured).',
        "",
        "Scales the credit a detected hit earns so that identical planted defence earns identical",
        "credit in every language (#2716). 1.0 means the rule reads exactly on plant, under-fires",
        "(a rule to fix, never compensated), or the signal is ledgered n/a for the language.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "FIDELITY_PROVENANCE: dict[str, str] = " + json.dumps(prov, indent=4).replace("\n", "\n") + "",
        "",
        "FIDELITY_SIGNALS: tuple[str, ...] = (",
    ]
    lines += [f'    "{s}",' for s in signals]
    lines += [")", "", "FIDELITY_TABLE: dict[str, dict[str, float]] = {"]
    for lang in sorted(table):
        row = table[lang]
        nonunit = {s: v for s, v in row.items() if v != 1.0}
        if nonunit:
            body = ", ".join(f'"{s}": {v}' for s, v in sorted(nonunit.items()))
            lines.append(f'    "{lang}": {{{body}}},')
        else:
            lines.append(f'    "{lang}": {{}},')
    lines += ["}", ""]
    return "\n".join(lines)


def render_docs() -> dict[str, str]:
    """Markdown tables for the wiki, straight from the data the engine reads -- a
    hand-written table is how the repo ended up with two that disagreed (#2653)."""
    from gitgalaxy.standards import analysis_lens as al
    from gitgalaxy.standards.fidelity_table import FIDELITY_PROVENANCE, FIDELITY_TABLE

    cols = " | ".join(c.replace("_", " ") for c in al.STRICTNESS_COLUMNS)
    strict = [f"| language | {cols} | Irc | Ot |", "|---|" + "---|" * len(al.STRICTNESS_COLUMNS) + "---|---|"]
    for lang in sorted(al.LANGUAGE_STRICTNESS):
        row = al.LANGUAGE_STRICTNESS[lang]
        irc, ot = al.strictness_constants(lang)
        if row is None:
            cells = " | ".join("—" for _ in al.STRICTNESS_COLUMNS) + " | 0 | 1.00 |"
            strict.append(f"| `{lang}` *(no runtime)* | {cells}")
        else:
            cells = " | ".join("yes" if f else "**no**" for f in row)
            strict.append(f"| `{lang}` | {cells} | {irc} | {ot:.2f} |")
    fam = ", ".join(f"`{m}` → `{p}`" for m, p in sorted(al.LANGUAGE_FAMILY.items()))
    strict.append("")
    strict.append(f"Dialects read their family's row: {fam}.")

    engine_sigs = ("safety", "test", "doc", "ownership")
    fid = [
        "| language | " + " | ".join(f"`{s}`" for s in engine_sigs) + " |",
        "|---|" + "---|" * len(engine_sigs),
    ]
    for lang in sorted(FIDELITY_TABLE):
        row = FIDELITY_TABLE[lang]
        if all(row.get(s, 1.0) == 1.0 for s in engine_sigs):
            continue
        fid.append(
            f"| `{lang}` | "
            + " | ".join(f"**{row[s]:.2f}**" if row.get(s, 1.0) != 1.0 else "1.00" for s in engine_sigs)
            + " |"
        )
    fid.append("")
    fid.append(
        f"Every language and signal not listed reads 1.00. Source: keyword-rosetta `{FIDELITY_PROVENANCE['corpus_sha'][:8]}` "
        f"({FIDELITY_PROVENANCE['languages']} languages), regenerated by `tests/tools/fidelity_table.py`."
    )
    return {"strictness": "\n".join(strict), "fidelity": "\n".join(fid)}


def write_docs() -> int:
    text = WIKI_PAGE.read_text()
    for name, body in render_docs().items():
        start, end = f"<!-- generated:{name} -->", f"<!-- /generated:{name} -->"
        if start not in text or end not in text:
            print(f"fidelity_table: markers for {name!r} missing from {WIKI_PAGE.name}", file=sys.stderr)
            return 1
        head, rest = text.split(start, 1)
        _old, tail = rest.split(end, 1)
        text = f"{head}{start}\n{body}\n{end}{tail}"
    WIKI_PAGE.write_text(text)
    print(f"fidelity_table: refreshed generated tables in {WIKI_PAGE.relative_to(REPO_ROOT)}")
    return 0


def _committed() -> tuple[dict[str, dict[str, float]], list[str], str] | None:
    """(table, signals, corpus_sha) from the committed module, or None if it is missing."""
    if not OUTPUT.exists():
        return None
    mod = importlib.import_module("gitgalaxy.standards.fidelity_table")
    importlib.reload(mod)
    table = {lang: dict(row) for lang, row in mod.FIDELITY_TABLE.items()}
    return table, list(mod.FIDELITY_SIGNALS), mod.FIDELITY_PROVENANCE.get("corpus_sha", "")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ap.add_argument("--check", action="store_true", help="exit 1 if the committed module differs")
    ap.add_argument("--docs", action="store_true", help="refresh the generated tables in the wiki page")
    args = ap.parse_args(argv)
    if args.docs:
        return write_docs()
    if not (args.corpus / "docs" / "bias_data.json").exists():
        print(f"fidelity_table: no corpus at {args.corpus} (set KEYWORD_ROSETTA_PATH)", file=sys.stderr)
        return 2
    table, signals, prov = build_table(args.corpus)
    text = render(table, signals, prov)
    if args.check:
        # Compare the DATA the committed module carries (the module is ruff-formatted after
        # generation, so byte equality would be brittle). The 1.0 cells are elided on write,
        # so compare the below-1.0 cells and the signal list.
        committed = _committed()
        want = {lang: {s: v for s, v in row.items() if v != 1.0} for lang, row in table.items()}
        if committed is None or committed[0] != want or committed[1] != signals:
            print(f"fidelity_table: {OUTPUT.relative_to(REPO_ROOT)} is stale against {args.corpus}", file=sys.stderr)
            return 1
        if committed[2] != prov["corpus_sha"]:
            print(
                f"fidelity_table: data fresh but provenance sha {committed[2][:8]} != corpus {prov['corpus_sha'][:8]}"
            )
        print(f"fidelity_table: fresh ({prov['languages']} languages x {prov['signals']} signals)")
        return 0
    OUTPUT.write_text(text)
    below = sum(1 for r in table.values() for v in r.values() if v < 1.0)
    print(
        f"fidelity_table: wrote {OUTPUT.relative_to(REPO_ROOT)} -- {prov['languages']} languages x "
        f"{prov['signals']} signals, {below} cells below 1.0"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
