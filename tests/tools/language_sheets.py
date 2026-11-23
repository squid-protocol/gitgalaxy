#!/usr/bin/env python3
"""
language_sheets.py -- one evidence sheet per language: six independent stats, no overall score.

WHY
    How well GitGalaxy reads a language is not one number. Call links can be checked against a compiler
    for C and not at all for Easytrieve, and the corpora differ by orders of magnitude. A tier ladder
    would punish a language for the tooling that exists. So each language gets a sheet of independent
    stats. Every stat carries its value, its sample size, its method and its source. A separate,
    hand-written "what was possible" block says what the best available method for that language is,
    so a thin number reads as "at the ceiling" or "not yet" and never as a ranking.

THE SIX STATS (each a pure function of a committed file; nothing is measured here)
    detection   tests/detection_accuracy_baseline.json           vs a labelled corpus
    functions   tests/tree_sitter_accuracy_baseline_<lang>.json   vs tree-sitter (python: ast)
    calls       tests/call_graph_resolution_<lang>_baseline.json  vs a compiler/analyser reference,
                else tests/call_graph_accuracy_baseline.json      vs tree-sitter call nodes
    imports     tests/import_graph_accuracy_baseline.json         vs import statements
    keywords    tests/family_validity_baseline.json               families by score, plus decoy-only
    rosetta     docs/language_sheets/rosetta_snapshot.json        probe cells passed / failed

    Every number here is as the baseline holds it. The functions and imports figures are raw (before the
    disagreement ledgers are applied); graph_coverage_chart.py shows the ledger-validated ones.

HAND-WRITTEN PART
    docs/language_sheets/notes/<lang>.toml : context group, the "what was possible" block, per-stat notes.
    The generator refuses a method outside METHODS, and an `ensemble` or `llm-read` stat with no note.

USAGE
    python tests/tools/language_sheets.py --write                 # sheets, index and matrix under docs/language_sheets/
    python tests/tools/language_sheets.py --check                 # fail if the committed output is stale
    python tests/tools/language_sheets.py --refresh-rosetta PATH  # rebuild the Rosetta snapshot from keyword-rosetta's docs/bias_data.json
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from dataclasses import dataclass, field
from html import escape
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO_ROOT = TOOLS.parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

TESTS = REPO_ROOT / "tests"
OUT_DIR = REPO_ROOT / "docs" / "language_sheets"
NOTES_DIR = OUT_DIR / "notes"
ROSETTA_SNAPSHOT = OUT_DIR / "rosetta_snapshot.json"

STATS = ("detection", "functions", "calls", "imports", "keywords", "rosetta")
STAT_TITLE = {
    "detection": "Detection",
    "functions": "Functions",
    "calls": "Call links",
    "imports": "Imports",
    "keywords": "Keywords",
    "rosetta": "Rosetta",
}

# The fixed method vocabulary. `none` is split by reason in the notes ("none exists" / "not run").
METHODS = frozenset(
    {
        "exact-parser",
        "tree-sitter",
        "ctags",
        "analyser",
        "ensemble",
        "llm-read",
        "decoy-test",
        "hand-audit",
        "corpus-label",
        "answer-key",
        "keyword-rosetta",
        "none",
    }
)
NEEDS_NOTE = frozenset({"ensemble", "llm-read"})

# The keyword-quality chart's own colours (tests/tools/family_validity_chart.py): one blue, dark to bright; red is failure.
CHIP_EDGES = (50.0, 80.0, 90.0, 98.0)
CHIP_FILL = ("#3b1d1d", "#1f3b5c", "#2f6aa8", "#4f9be8", "#a9d1ff")
CHIP_TEXT = ("#ff8f88", "#ffffff", "#ffffff", "#06121f", "#06121f")
CHIP_LABEL = ("under 50%", "50-79%", "80-89%", "90-97%", "98-100%")
FAIL = "#e5534b"
GREY = "#8b949e"
TRACK = "#30363d"
# The keyword histogram's four bins, high to low: [>90, 90-75, 75-50, <50]
KW_EDGES = (0.90, 0.75, 0.50)
KW_LABELS = (">90", "90-75", "75-50", "<50")
KW_FILL = ("#4f9be8", "#2f6aa8", "#1f3b5c", FAIL)


@dataclass
class Stat:
    """One measurement. `metrics` is [(label, pct)]; a stat with no numbers has an empty list and a `text`."""

    metrics: list[tuple[str, float]] = field(default_factory=list)
    n: int | None = None
    unit: str = ""
    method: str = "none"
    reference: str = ""
    source: str = ""
    text: str = ""
    extra: dict = field(default_factory=dict)  # keywords bins / rosetta counts


def chip_bin(pct: float) -> int:
    return sum(pct >= edge for edge in CHIP_EDGES)


# ----------------------------------------------------------------------------- loaders


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def detection_stats() -> dict[str, Stat]:
    data = _read(TESTS / "detection_accuracy_baseline.json") or {}
    out = {}
    for lang, r in data.get("languages", {}).items():
        out[lang] = Stat(
            metrics=[("recall", round(100 * r["recall"], 1)), ("precision", round(100 * r["precision"], 1))],
            n=int(r["support"]),
            unit="files",
            method="corpus-label",
            reference="labelled language-crucible files",
            source="tests/detection_accuracy_baseline.json",
        )
    return out


def _ratio(num: float, den: float) -> float | None:
    return round(100.0 * num / den, 1) if den > 0 else None


def functions_stats() -> dict[str, Stat]:
    out = {}
    for path in sorted(TESTS.glob("tree_sitter_accuracy_baseline_*.json")):
        lang = path.stem.removeprefix("tree_sitter_accuracy_baseline_")
        b = _read(path)
        recall = _ratio(b["found_functions"], b["real_functions"])
        precision = _ratio(b["found_functions"], b["found_functions"] + b["extra_functions"])
        metrics = [(k, v) for k, v in (("recall", recall), ("precision", precision)) if v is not None]
        if metrics:
            out[lang] = Stat(
                metrics=metrics,
                n=int(b["real_functions"]),
                unit="functions",
                method="tree-sitter",
                reference="tree-sitter functions on language-crucible",
                source=f"tests/{path.name}",
            )
    ast = _read(TESTS / "ast_accuracy_baseline.json")
    if ast:
        metrics = [
            (k, v)
            for k, v in (
                ("recall", _ratio(ast["found_functions"], ast["real_functions"])),
                ("precision", _ratio(ast["found_functions"], ast["found_functions"] + ast["extra_functions"])),
            )
            if v is not None
        ]
        out["python"] = Stat(
            metrics=metrics,
            n=int(ast["real_functions"]),
            unit="functions",
            method="exact-parser",
            reference="Python ast on the stdlib corpus",
            source="tests/ast_accuracy_baseline.json",
        )
    return out


def calls_stats() -> dict[str, Stat]:
    import graph_coverage_chart as gcc

    out = {}
    for lang, c in gcc.call_cells().items():  # level 1: callee names vs tree-sitter call nodes
        metrics = [(k, v) for k, v in (("precision", c.precision), ("recall", c.recall)) if v is not None]
        if metrics:
            out[lang] = Stat(
                metrics=metrics,
                n=c.n_recall,
                unit="calls",
                method="tree-sitter",
                reference="tree-sitter call nodes (which names a function calls)",
                source="tests/call_graph_accuracy_baseline.json",
            )
    for lang, c in gcc.resolution_cells().items():  # level 2 wins: which definition a call reaches
        metrics = [(k, v) for k, v in (("precision", c.precision), ("recall", c.recall)) if v is not None]
        if metrics:
            file = (
                "call_graph_resolution_baseline.json"
                if lang == "python"
                else f"call_graph_resolution_{lang}_baseline.json"
            )
            out[lang] = Stat(
                metrics=metrics,
                n=c.n_recall,
                unit="reference edges",
                method="analyser",
                reference=c.reference,
                source=f"tests/{file}",
            )
    return out


def imports_stats() -> dict[str, Stat]:
    data = _read(TESTS / "import_graph_accuracy_baseline.json") or {}
    out = {}
    for lang, r in data.items():
        metrics = [(k, r[f"{k}_pct"]) for k in ("precision", "recall") if r.get(f"{k}_pct") is not None]
        if metrics:
            out[lang] = Stat(
                metrics=metrics,
                n=int(r.get("imports") or 0),
                unit="imports",
                method="tree-sitter",
                reference=f"import statements in {r.get('repos', 'pinned repos')}",
                source="tests/import_graph_accuracy_baseline.json",
            )
    return out


def kw_bin(score: float) -> int:
    """0..3 into KW_LABELS: >90, 90-75, 75-50, <50."""
    return sum(score < edge for edge in KW_EDGES)


def keywords_stats() -> dict[str, Stat]:
    import family_validity_chart as fvc

    families, languages, defined = fvc.engine_grid()
    cells, decoys = fvc.load_baseline(), fvc.load_decoys()
    out = {}
    for lang in languages:
        bins = [0, 0, 0, 0]
        scored = 0
        for fam in families:
            cell = cells.get(lang, {}).get(fam.key)
            score = fvc.cell_score(cell) if cell else None
            if score is not None:
                bins[kw_bin(score)] += 1
                scored += 1
        n_defined = len(defined.get(lang, set()))
        decoy_only = sum(
            1
            for k in decoys.get(lang, {})
            if not (k in cells.get(lang, {}) and fvc.cell_score(cells[lang][k]) is not None)
        )
        if not scored and not decoy_only:
            continue  # nothing measured for this language
        method = "tree-sitter" if scored else "decoy-test"
        out[lang] = Stat(
            n=sum(int(c.get("n_oracle") or 0) for c in cells.get(lang, {}).values()) or None,
            unit="oracle functions",
            method=method,
            reference="parser-labelled functions, lower of recall and precision per family" if scored else "",
            source="tests/family_validity_baseline.json",
            extra={"bins": bins, "scored": scored, "decoy_only": decoy_only, "defined": n_defined},
        )
    return out


def rosetta_stats() -> dict[str, Stat]:
    snap = _read(ROSETTA_SNAPSHOT)
    if not snap:
        return {}
    out = {}
    for lang, r in snap["languages"].items():
        out[lang] = Stat(
            n=r["comparable"],
            unit="comparable cells",
            method="keyword-rosetta",
            reference=f"the 12-probe program, engine {snap['engine_commit'][:10]}",
            source="docs/language_sheets/rosetta_snapshot.json",
            extra={"comparable": r["comparable"], "open": r["open"], "variation": r["variation"]},
        )
    return out


def refresh_rosetta(bias_data: Path, out: Path = ROSETTA_SNAPSHOT) -> None:
    """Per language: comparable cells (a gated metric with a value for the language), open defects (cause
    unexplained, extraction or correlation, as keyword-rosetta's OPEN_DEFECT_CATEGORIES) and validated
    variations (the other out-of-band causes). Everything else is in band."""
    d = json.loads(bias_data.read_text(encoding="utf-8"))
    open_cats = {"unexplained", "extraction", "correlation"}
    ungated = set(d.get("ungated_metrics", []))
    cats = d.get("cell_categories", {})
    langs = {}
    for lang in d["languages"]:
        comparable = open_n = variation = 0
        for metric, values in d["metrics"].items():
            if metric in ungated or not isinstance(values.get(lang), (int, float)):
                continue
            comparable += 1
            cat = cats.get(f"{metric}/{lang}")
            if cat in open_cats:
                open_n += 1
            elif cat:
                variation += 1
        if comparable:
            langs[lang] = {"comparable": comparable, "open": open_n, "variation": variation}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "engine_commit": d.get("engine_commit", ""),
                "source": "keyword-rosetta docs/bias_data.json",
                "languages": langs,
            },
            indent=1,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


GROUND_TRUTH = TESTS / "cobol_mainframe" / "ground_truth_ledger.json"
# (stat, ledger field, what the field is, unit). One answer-key field stands in for each of three stats, for the
# languages whose corpora are keyed (COBOL and CICS). A real tree-sitter or analyser measurement is never overridden.
GROUND_TRUTH_FIELDS = (
    ("functions", "units", "paragraphs and sections", "units"),
    ("calls", "intra-program edges", "PERFORM and GO TO edges inside a program", "edges"),
    ("imports", "copybook paths", "COPY members resolved to a file", "copybook paths"),
)
TIER_ORDER = ("draft", "sample_verified", "llm_verified", "cross_verified", "human_signed")


def ground_truth_stats(ledger: Path = GROUND_TRUTH) -> dict[str, dict[str, Stat]]:
    """{stat: {"cobol": Stat}} from the mainframe ground-truth ledger: the engine against hand-built answer keys that a
    separately written reader drafted and blind LLM reviewers re-read. Summed over the keyed corpora."""
    data = _read(ledger)
    if not data:
        return {}
    corpora = data.get("corpora", {})
    programs = sum(
        (rec["scoreboard"].get("program_id") or {}).get("engine", {}).get("truth", 0)
        for rec in corpora.values()
        if (rec.get("scoreboard", {}).get("program_id") or {}).get("engine")
    )
    out: dict[str, dict[str, Stat]] = {}
    for stat, fld, what, unit in GROUND_TRUTH_FIELDS:
        got = tp = truth = n_corpora = 0
        tiers: set[str] = set()
        for rec in corpora.values():
            row = rec.get("scoreboard", {}).get(fld)
            if not row or not row.get("engine"):
                continue
            e = row["engine"]
            got, tp, truth, n_corpora = got + e["got"], tp + e["tp"], truth + e["truth"], n_corpora + 1
            tiers.add(row["truth"])
        if not truth:
            continue
        weakest = min(tiers, key=TIER_ORDER.index)
        metrics = [(k, v) for k, v in (("precision", _ratio(tp, got)), ("recall", _ratio(tp, truth))) if v is not None]
        out[stat] = {
            "cobol": Stat(
                metrics=metrics,
                n=truth,
                unit=unit,
                method="answer-key",
                reference=f"answer key over {n_corpora} corpora, {programs} programs ({what}); weakest tier {weakest}",
                source="tests/cobol_mainframe/ground_truth_ledger.json",
            )
        }
    return out


LOADERS = {
    "detection": detection_stats,
    "functions": functions_stats,
    "calls": calls_stats,
    "imports": imports_stats,
    "keywords": keywords_stats,
    "rosetta": rosetta_stats,
}


def load_all() -> tuple[list[str], dict[str, dict[str, Stat]]]:
    import graph_coverage_chart as gcc

    langs = gcc.all_languages()
    stats = {name: fn() for name, fn in LOADERS.items()}
    for stat, by_lang in ground_truth_stats().items():
        for lang, st in by_lang.items():
            stats[stat].setdefault(lang, st)  # never replace an independent tree-sitter / analyser measurement
    return langs, stats


# ----------------------------------------------------------------------------- notes


def load_notes(notes_dir: Path = NOTES_DIR) -> dict[str, dict]:
    out = {}
    if notes_dir.exists():
        for p in sorted(notes_dir.glob("*.toml")):
            out[p.stem] = tomllib.loads(p.read_text(encoding="utf-8"))
    return out


def validate(stats: dict[str, dict[str, Stat]], notes: dict[str, dict]) -> list[str]:
    """Problems that fail the build: a method outside the vocabulary, or an ensemble / llm-read stat with no note."""
    bad = []
    for name, by_lang in stats.items():
        for lang, s in by_lang.items():
            if s.method not in METHODS:
                bad.append(f"{lang}/{name}: method {s.method!r} is not in the vocabulary")
            if s.method in NEEDS_NOTE and not notes.get(lang, {}).get("stat_notes", {}).get(name):
                bad.append(f"{lang}/{name}: method {s.method} needs a note naming its components and rule")
    for lang, note in notes.items():
        bad.extend(f"notes/{lang}.toml: unknown stat {key!r}" for key in note.get("stat_notes", {}) if key not in STATS)
    return bad


# ----------------------------------------------------------------------------- text rendering


def fmt_n(s: Stat) -> str:
    return f"{s.n:,} {s.unit}" if s.n else ""


def cell_text(name: str, s: Stat | None) -> str:
    if s is None:
        return "not measured"
    if name == "keywords":
        e = s.extra
        if not e["scored"]:
            return f"decoy test only ({e['decoy_only']})" if e["decoy_only"] else "not measured"
        parts = [f"{c} {lbl}" for c, lbl in zip(e["bins"], KW_LABELS, strict=True) if c]
        return f"{e['scored']} of {e['defined']} families: " + ", ".join(parts)
    if name == "rosetta":
        e = s.extra
        return f"{e['comparable'] - e['open']} of {e['comparable']} passed, {e['open']} failed"
    return " / ".join(f"{v:g}% {k}" for k, v in s.metrics)


def render_sheet(lang: str, stats: dict[str, dict[str, Stat]], note: dict) -> str:
    lines = [f"# {lang}", "", f"Context: {note.get('context', 'unclassified')}", ""]
    ceil = note.get("ceiling")
    if ceil:
        lines += ["## What was possible", ""]
        if ceil.get("status", "unconfirmed") == "unconfirmed":
            lines += ["> Unconfirmed: these statements are a draft until the search log is signed off.", ""]
        for key, label in (
            ("parsers", "Parsers found"),
            ("corpus", "Public corpus"),
            ("reference_analyser", "Reference analyser"),
            ("best_method", "Best method"),
            ("why", "Why"),
            ("searched_on", "Searched on"),
        ):
            if ceil.get(key):
                lines.append(f"- **{label}:** {ceil[key]}")
        lines.append("")
    lines += ["## Measured", "", "| stat | value | sample | method | against | source |", "|---|---|---|---|---|---|"]
    for name in STATS:
        s = stats[name].get(lang)
        if s is None:
            lines.append(f"| {STAT_TITLE[name]} | not measured | | | | |")
            continue
        lines.append(
            f"| {STAT_TITLE[name]} | {cell_text(name, s)} | {fmt_n(s)} | {s.method} | {s.reference} | `{s.source}` |"
        )
    notes = note.get("stat_notes", {})
    if notes:
        lines += ["", "## Notes", ""]
        lines += [f"- **{STAT_TITLE[k]}:** {v}" for k, v in notes.items() if k in STATS]
    lines += ["", "[All languages](README.md)", ""]
    return "\n".join(lines)


COVERAGE_MIN = 4  # measured on at least this many of the six stats: "well measured"


def coverage(lang: str, stats: dict[str, dict[str, Stat]]) -> int:
    """How many of the six stats have a measurement. A decoy-only keyword stat is not a measurement against a parser."""
    n = 0
    for name in STATS:
        s = stats[name].get(lang)
        if s is None or (name == "keywords" and not s.extra["scored"]):
            continue
        n += 1
    return n


def split_by_coverage(langs: list[str], stats: dict[str, dict[str, Stat]]) -> tuple[list[str], list[str]]:
    """(well measured, sparsely measured), each A to Z. This describes how much is measured, not how good it is."""
    well = sorted(lang for lang in langs if coverage(lang, stats) >= COVERAGE_MIN)
    sparse = sorted(lang for lang in langs if coverage(lang, stats) < COVERAGE_MIN)
    return well, sparse


def _table(rows: list[str], stats: dict[str, dict[str, Stat]], notes: dict[str, dict]) -> list[str]:
    lines = [
        "| language | measured | context | " + " | ".join(STAT_TITLE[n] for n in STATS) + " |",
        "|---|---|---|" + "---|" * len(STATS),
    ]
    lines.extend(
        f"| [{lang}]({lang}.md) | {coverage(lang, stats)} of {len(STATS)} | {notes.get(lang, {}).get('context', 'unclassified')} | "
        + " | ".join(cell_text(n, stats[n].get(lang)) for n in STATS)
        + " |"
        for lang in rows
    )
    return [*lines, ""]


def render_index(langs: list[str], stats: dict[str, dict[str, Stat]], notes: dict[str, dict]) -> str:
    well, sparse = split_by_coverage(langs, stats)
    lines = [
        "# Language evidence sheets",
        "",
        "Six independent measurements per language, each with its own method and sample size. There is no overall score:",
        "a language's number says how it did against the best reference that exists for it, and the sheet says what that",
        "reference is. Languages are grouped by how many of the six stats are measured, which says how much evidence",
        "exists and not how good the engine is. Generated by `tests/tools/language_sheets.py` from the committed baselines.",
        "",
        f"## Measured on {COVERAGE_MIN} or more of the six stats ({len(well)} languages)",
        "",
        "![Well-measured languages](matrix.svg)",
        "",
        "<details>",
        "<summary>The same table as text, with links to each sheet</summary>",
        "",
        *_table(well, stats, notes),
        "</details>",
        "",
        f"## Sparsely measured ({len(sparse)} languages)",
        "",
        f"Fewer than {COVERAGE_MIN} of the six stats are measured. For many of these the sheet says why: no parser or",
        "reference tool exists, or the public corpus is small.",
        "",
        "<details>",
        "<summary>Chart of the sparsely measured languages</summary>",
        "",
        "![Sparsely measured languages](matrix_sparse.svg)",
        "",
        "</details>",
        "",
        "<details>",
        "<summary>The same table as text, with links to each sheet</summary>",
        "",
        *_table(sparse, stats, notes),
        "</details>",
        "",
    ]
    return "\n".join(lines)


# ----------------------------------------------------------------------------- matrix svg

COLS = {"lang": 8, "detection": 130, "functions": 290, "calls": 450, "imports": 610, "keywords": 770, "rosetta": 960}
COL_W = 150
ROW_PLAIN, ROW_KW = 38, 52  # a row grows only when it carries a keyword bar
TOP = 58


def _chips(x: int, y: int, s: Stat) -> list[str]:
    out, cx = [], x
    for label, pct in s.metrics:
        b = chip_bin(pct)
        text = f"{pct:g}% {label[0]}"
        w = 8 + 6.4 * len(text)
        stroke = FAIL if b == 0 else GREY
        out.append(
            f'<rect x="{cx:.0f}" y="{y}" width="{w:.0f}" height="18" rx="4" fill="{CHIP_FILL[b]}" stroke="{stroke}" stroke-width="1"/>'
            f'<text x="{cx + 6:.0f}" y="{y + 13}" font-size="11" fill="{CHIP_TEXT[b]}">{escape(text)}</text>'
        )
        cx += w + 4
    return out


def _bar(x: int, y: int, parts: list[tuple[int, str]], total: int) -> list[str]:
    out, cx = [], float(x)
    for count, fill in parts:
        if count <= 0 or total <= 0:
            continue
        w = COL_W * count / total
        out.append(f'<rect x="{cx:.1f}" y="{y}" width="{w:.1f}" height="9" fill="{fill}"/>')
        cx += w
    return out


def _row_height(lang: str, stats: dict[str, dict[str, Stat]]) -> int:
    k = stats["keywords"].get(lang)
    return ROW_KW if k and k.extra["scored"] else ROW_PLAIN


def render_matrix_svg(rows: list[str], stats: dict[str, dict[str, Stat]]) -> str:
    heights = [_row_height(lang, stats) for lang in rows]
    height = TOP + sum(heights) + 8
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1130 {height}" width="1130" height="{height}" font-family="Inter,system-ui,sans-serif" role="img" aria-label="Per-language evidence matrix">',
        f'<rect width="1130" height="{height}" fill="#0f1117"/>',
    ]
    out.extend(
        f'<text x="{COLS[name]}" y="20" font-size="11" fill="{GREY}" font-weight="600">{STAT_TITLE[name].upper()}</text>'
        for name in STATS
    )
    out.append(f'<text x="{COLS["lang"]}" y="20" font-size="11" fill="{GREY}" font-weight="600">LANGUAGE</text>')
    lx = 8
    for i, lbl in enumerate(CHIP_LABEL):
        out.append(
            f'<rect x="{lx}" y="30" width="12" height="12" rx="3" fill="{CHIP_FILL[i]}" stroke="{FAIL if i == 0 else GREY}"/>'
        )
        out.append(f'<text x="{lx + 17}" y="40" font-size="10.5" fill="#c9d1d9">{lbl}</text>')
        lx += 100
    out.append(
        f'<text x="{lx + 10}" y="40" font-size="10.5" fill="{GREY}">p = precision, r = recall. Keywords: families by score, high to low.</text>'
    )
    y = TOP
    for lang, rh in zip(rows, heights, strict=True):
        out.append(f'<line x1="8" y1="{y - 4}" x2="1122" y2="{y - 4}" stroke="{TRACK}"/>')
        out.append(
            f'<text x="{COLS["lang"]}" y="{y + 14}" font-size="13" fill="#f0efec" font-weight="600">{escape(lang)}</text>'
        )
        out.append(
            f'<text x="{COLS["lang"]}" y="{y + 28}" font-size="10" fill="{GREY}">{coverage(lang, stats)} of {len(STATS)} stats</text>'
        )
        for name in ("detection", "functions", "calls", "imports"):
            s = stats[name].get(lang)
            x = COLS[name]
            if s is None:
                out.append(f'<text x="{x}" y="{y + 14}" font-size="11" fill="{GREY}">not measured</text>')
                continue
            out += _chips(x, y, s)
            out.append(f'<text x="{x}" y="{y + 31}" font-size="10" fill="{GREY}">{escape(fmt_n(s))}</text>')
        s = stats["keywords"].get(lang)
        x = COLS["keywords"]
        if s is None or not s.extra["scored"]:
            label = f"decoy test only ({s.extra['decoy_only']})" if s and s.extra["decoy_only"] else "not measured"
            out.append(f'<text x="{x}" y="{y + 14}" font-size="11" fill="{GREY}">{label}</text>')
        else:
            e = s.extra
            out += _bar(x, y + 3, list(zip(e["bins"], KW_FILL, strict=True)), e["scored"])
            cx = float(x)  # each count sits under its own segment; a wide segment also names its range
            for count, label in zip(e["bins"], KW_LABELS, strict=True):
                if not count:
                    continue
                w = COL_W * count / e["scored"]
                out.append(
                    f'<text x="{cx + w / 2:.1f}" y="{y + 22}" font-size="11" font-weight="600" fill="#f0efec" text-anchor="middle">{count}</text>'
                )
                if w >= 40:
                    out.append(
                        f'<text x="{cx + w / 2:.1f}" y="{y + 32}" font-size="9" fill="{GREY}" text-anchor="middle">{escape(label)}</text>'
                    )
                cx += w
            out.append(
                f'<text x="{x}" y="{y + 44}" font-size="10" fill="{GREY}">{e["scored"]} of {e["defined"]} families</text>'
            )
        s = stats["rosetta"].get(lang)
        x = COLS["rosetta"]
        if s is None:
            out.append(f'<text x="{x}" y="{y + 14}" font-size="11" fill="{GREY}">not measured</text>')
        else:
            e = s.extra
            passed = e["comparable"] - e["open"]
            out += _bar(x, y + 3, [(passed, "#4f9be8"), (e["open"], FAIL)], e["comparable"])
            text = f"{passed} passed, {e['open']} failed" if e["open"] else f"{passed} of {e['comparable']} passed"
            out.append(f'<text x="{x}" y="{y + 24}" font-size="10" fill="#c9d1d9">{text}</text>')
        y += rh
    out.append("</svg>")
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------------------- build


def build() -> tuple[dict[str, str], list[str]]:
    """{relative path under OUT_DIR: text}, and the validation problems."""
    langs, stats = load_all()
    notes = load_notes()
    problems = validate(stats, notes)
    well, sparse = split_by_coverage(langs, stats)
    files = {
        "README.md": render_index(langs, stats, notes),
        "matrix.svg": render_matrix_svg(well, stats),
        "matrix_sparse.svg": render_matrix_svg(sparse, stats),
    }
    for lang in langs:
        files[f"{lang}.md"] = render_sheet(lang, stats, notes.get(lang, {}))
    return files, problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="write the sheets, index and matrix")
    mode.add_argument("--check", action="store_true", help="fail if the committed output is stale")
    mode.add_argument("--refresh-rosetta", metavar="PATH", help="rebuild the Rosetta snapshot from bias_data.json")
    args = ap.parse_args(argv)
    if args.refresh_rosetta:
        refresh_rosetta(Path(args.refresh_rosetta))
        print(f"wrote {ROSETTA_SNAPSHOT.relative_to(REPO_ROOT)}")
        return 0
    files, problems = build()
    for p in problems:
        print(f"problem: {p}", file=sys.stderr)
    if problems:
        return 1
    if args.write:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        for rel, text in files.items():
            (OUT_DIR / rel).write_text(text, encoding="utf-8")
        print(f"wrote {len(files)} files under {OUT_DIR.relative_to(REPO_ROOT)}")
        return 0
    if args.check:
        stale = [
            rel
            for rel, text in files.items()
            if not (OUT_DIR / rel).exists() or (OUT_DIR / rel).read_text(encoding="utf-8") != text
        ]
        if stale:
            print(f"stale: {len(stale)} file(s), e.g. {stale[:5]}; run --write", file=sys.stderr)
            return 1
        print("language sheets are current")
        return 0
    print(files["README.md"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
