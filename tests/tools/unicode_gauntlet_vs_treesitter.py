#!/usr/bin/env python3
"""
The Unicode Gauntlet, GitGalaxy vs tree-sitter (epic #3811): the same metamorphic oracle, both engines.

The gauntlet (unicode_gauntlet.py) writes every cell -- a seed language's estate with its unit names
renamed into another script and/or its files re-encoded -- and checks GitGalaxy's facts on it:

    facts(T(seed)) == T(facts(seed))

This tool reuses those cells and GitGalaxy's scans of them, and runs the same oracle on the one
channel both engines produce: the FUNCTION NAMES of every file tree-sitter can read. A cell passes
for an engine when the multiset of function names it reads from the cell equals the multiset it reads
from the cell's reference (the seed, or the seed renamed with the script's ASCII twin) with the
cell's renaming applied -- same count, every name whole. A name cut at a combining mark, a name in
mojibake, a missing or an extra function: the cell fails.

Three readings per cell:

  gitgalaxy       the gauntlet's own scan of the cell (its master DB's function_data).
  ts-raw          tree-sitter parses the cell's RAW FILE BYTES -- tree-sitter reads bytes as UTF-8,
                  which is how tree-sitter-based tools consume files -- and functions are extracted
                  with tree_sitter_accuracy_audit's NODE_MAPS / _get_node_name. A name whose bytes
                  are not UTF-8 is recorded as broken (`<invalid UTF-8 b'...'>`), never repaired.
  ts-decode       the same, after decoding the file with the cell's TRUE encoding and re-encoding it
                  as UTF-8: the best a careful integrator could do. The gap between ts-raw and
                  ts-decode is the byte pipeline; what ts-decode still fails is the grammar.

A cell counts only where both engines can attempt it: the language has a NODE_MAPS entry and a
grammar in tree_sitter_language_pack (otherwise `ts-no-grammar`, listed, not a failure), and each
engine passes its CONTROL -- on the untouched UTF-8 seed it finds every function keyword-rosetta's
hand-verified answer key lists (`expected_function_nodes`) in the files tree-sitter reads. A
language whose control fails is excluded (`control-fail`) for both: its cells would measure the
extractor, not the text foundation. A rename the language's own spec forbids (Dart identifiers are
ASCII-only, though legality.json lists Dart) is not a program at all: `not-legal`, listed, excluded.

    python tests/tools/unicode_gauntlet_vs_treesitter.py --out DIR [--full] [--only python java] [--jobs 8]

writes DIR/results.json (per cell: each reading's verdict and first difference), DIR/summary.json
(engine x script and engine x encoding pass rates, chart-ready) and DIR/report.md.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import unicode_gauntlet as ug  # noqa: E402

ENGINES = ("gitgalaxy", "ts_raw", "ts_decode")
# Languages whose own spec forbids the gauntlet's non-ASCII renames (legality.json lists them as
# Unicode-identifier languages): such a cell is not a program, so a grammar that refuses it is right.
# Excluded from the comparison (`not-legal`) and listed, never counted against either engine.
NOT_LEGAL = {"dart": "Dart identifiers are ASCII-only (spec: LETTER is 'a'..'z' | 'A'..'Z')"}
ENGINE_LABEL = {"gitgalaxy": "GitGalaxy", "ts_raw": "tree-sitter (raw bytes)", "ts_decode": "tree-sitter + decode"}
# How a careful integrator decodes each gauntlet encoding before handing tree-sitter UTF-8. EBCDIC
# pages are fixed-block records (see _decode_for_ts); every other one is a plain Python codec.
_CODEC = {"utf-8-sig": "utf-8-sig", "utf-16": "utf-16", "utf-16-be": "utf-16", "crlf": "utf-8", ug.NFD_PATHS: "utf-8"}


def _tsa() -> Any:
    """tree_sitter_accuracy_audit, imported on first use: it needs tree_sitter_language_pack."""
    import tree_sitter_accuracy_audit as tsa

    return tsa


# ---- tree-sitter's reading ----------------------------------------------------------------
_PARSERS: dict[str, Any] = {}


def ts_parser(gg_lang: str) -> tuple[Any, str]:
    """(parser or None, why not) for a GitGalaxy language: None without a NODE_MAPS entry or a grammar."""
    tsa = _tsa()
    if gg_lang not in tsa.NODE_MAPS:
        return None, f"no NODE_MAPS entry for {gg_lang}"
    ts_lang = tsa.NODE_MAPS[gg_lang].get("ts_lang", gg_lang)
    if ts_lang not in _PARSERS:
        try:
            _PARSERS[ts_lang] = tsa.tree_sitter_language_pack.get_parser(ts_lang)
        except Exception as exc:  # the pack raises its own download / lookup errors
            _PARSERS[ts_lang] = None
            return None, f"grammar {ts_lang} unavailable ({type(exc).__name__})"
    parser = _PARSERS[ts_lang]
    return parser, "" if parser is not None else f"grammar {ts_lang} unavailable"


def _name(node: Any) -> str | None:
    """The function's name as tree-sitter hands it over. Its bytes are the file's bytes: when they
    are not UTF-8 (a cp1252 é, a Shift-JIS kana) the name is recorded broken, with its bytes."""
    tsa = _tsa()
    try:
        return tsa._get_node_name(node)
    except UnicodeDecodeError:
        return f"<invalid UTF-8 {_undecodable(node)!r}>"


def _undecodable(node: Any) -> bytes:
    """The bytes of the innermost identifier-like node under `node` that are not UTF-8 (the name
    itself, not the whole function), else the node's first bytes."""
    stack = [node]
    while stack:
        n = stack.pop()
        if n.child_count == 0 and ("identifier" in n.type or n.type in ("name", "word", "ERROR")):
            try:
                n.text.decode("utf-8")
            except UnicodeDecodeError:
                return n.text[:48]
        stack.extend(reversed(n.children))
    return node.text[:48]


def ts_functions(data: bytes, gg_lang: str) -> list[str]:
    """Function names in a file, tree-sitter's own raw reading (the audit's raw_ts_funcs walk):
    every NODE_MAPS function node's name, HTML's embedded <script> functions, and a Haskell
    equation clause continuing the previous one's name counted once."""
    tsa = _tsa()
    parser, _ = ts_parser(gg_lang)
    types = tsa.NODE_MAPS[gg_lang]["func_node_types"]
    out: list[str] = []

    def walk(node: Any, continuation: bool = False) -> None:
        if gg_lang == "html" and node.type in tsa._HTML_EMBEDDED_LANG:
            try:
                out.extend(name for name, *_ in tsa._html_embedded_ts_funcs(node))
            except UnicodeDecodeError:
                out.append(f"<invalid UTF-8 in {node.type}>")
            return
        if node.type in types and not continuation:
            name = _name(node)
            if name:
                out.append(name)
        last: str | None = None
        for child in node.children:
            cont = False
            if gg_lang == "haskell" and child.type in types:
                child_name = _name(child)
                cont = child_name is not None and child_name == last
                last = child_name
            elif not (gg_lang == "haskell" and child.type == "comment"):
                last = None
            walk(child, cont)

    walk(parser.parse(data).root_node)
    return out


def _decode_for_ts(data: bytes, encoding: str) -> bytes:
    """The file as UTF-8, decoded with the encoding the cell was written in. A fixed-block EBCDIC
    download is split into its 80-byte records first, each record's padding trimmed."""
    try:
        if encoding in ug.EBCDIC:
            recs = [data[i : i + ug.FB_LRECL] for i in range(0, len(data), ug.FB_LRECL)]
            return "".join(r.decode(encoding).rstrip(" ") + "\n" for r in recs).encode("utf-8")
        return data.decode(_CODEC.get(encoding, encoding)).encode("utf-8")
    except UnicodeDecodeError:  # a file the gauntlet copied as it was (not text it could transform)
        return data


# ---- the two engines' names per estate ------------------------------------------------------
def _suffix_langs(seed_db: Path) -> dict[str, dict[str, str]]:
    """{seed language: {file suffix: the GitGalaxy language of the seed's files with it}}. A cell's
    files are the seed's, renamed in the stem only, so the suffix says which grammar reads them."""
    out: dict[str, Counter[tuple[str, str]]] = {}
    conn = sqlite3.connect(seed_db)
    for path, lang in conn.execute("SELECT file_path, language FROM file_data"):
        seed, _, rest = path.partition("/")
        out.setdefault(seed, Counter())[(Path(rest).suffix.lower(), lang)] += 1
    conn.close()
    result: dict[str, dict[str, str]] = {}
    for seed, counts in out.items():
        for (suffix, lang), _n in counts.most_common():
            result.setdefault(seed, {}).setdefault(suffix, lang)
    return result


class Readings:
    """Function names per (estate, seed language), read once and cached: a reference estate is
    shared by every cell of its script."""

    def __init__(self, work: Path, suffixes: dict[str, dict[str, str]]):
        self.root, self.scans, self.suffixes = work / "estates", work / "scans", suffixes
        self._gg: dict[str, dict[str, list[str]]] = {}
        self._ts: dict[tuple[str, str, str], list[str]] = {}

    def readable(self, lang: str) -> set[str]:
        """The suffixes of this seed tree-sitter can read (a NODE_MAPS entry and a grammar)."""
        return {s for s, gl in self.suffixes.get(lang, {}).items() if ts_parser(gl)[0] is not None}

    def gitgalaxy(self, estate: str, lang: str) -> list[str]:
        if estate not in self._gg:
            db = self.scans / estate / f"{estate}_galaxy_master.db"
            names: dict[str, list[str]] = {}
            conn = sqlite3.connect(db)
            rows = conn.execute("SELECT f.file_path, fn.func_name FROM function_data fn "
                                "JOIN file_data f ON f.id = fn.file_id")  # fmt: skip
            for path, name in rows:
                seed, _, rest = path.partition("/")
                if name is not None and Path(rest).suffix.lower() in self.readable(seed):
                    names.setdefault(seed, []).append(name)
            conn.close()
            self._gg[estate] = names
        return self._gg[estate].get(lang, [])

    def tree_sitter(self, estate: str, lang: str, encoding: str | None) -> list[str]:
        """tree-sitter's names in the estate's `lang` files: raw bytes when `encoding` is None,
        else decoded from `encoding` and re-encoded as UTF-8 first."""
        key = (estate, lang, encoding or "")
        if key not in self._ts:
            names: list[str] = []
            folder = self.root / estate / lang
            for path in sorted(folder.rglob("*")) if folder.is_dir() else []:
                gl = self.suffixes.get(lang, {}).get(path.suffix.lower())
                if not path.is_file() or gl is None or path.suffix.lower() not in self.readable(lang):
                    continue
                data = path.read_bytes()
                names += ts_functions(data if encoding is None else _decode_for_ts(data, encoding), gl)
            self._ts[key] = names
        return self._ts[key]


# ---- the oracle -----------------------------------------------------------------------------
def verdict(want: Counter[str], got: Counter[str]) -> dict[str, Any]:
    """Pass when the multisets agree; else the first difference, readable."""
    if want == got:
        return {"pass": True, "diff": ""}
    missing = sorted((want - got).elements())[:3]
    extra = sorted((got - want).elements())[:3]
    n_want, n_got = sum(want.values()), sum(got.values())
    return {"pass": False, "diff": f"{n_want} -> {n_got} functions; missing {missing} extra {extra}"}


def _fold(names: list[str], rename: Any = None) -> Counter[str]:
    return Counter((rename(n) if rename else n).casefold() for n in names)


def controls(readings: Readings, langs: set[str], seeds: dict[str, Path]) -> dict[str, dict[str, Any]]:
    """Per seed language and engine: does it find every hand-verified function of the UTF-8 seed
    (keyword-rosetta's expected_function_nodes, in the files tree-sitter reads)?"""
    out: dict[str, dict[str, Any]] = {}
    for lang in sorted(langs):
        readable = readings.readable(lang)
        key_file = seeds[lang] / "expected_signals.json"
        truth: list[str] = []
        if key_file.is_file():
            files = json.loads(key_file.read_text(encoding="utf-8")).get("files", {})
            truth = [n for f, sig in files.items() if Path(f).suffix.lower() in readable
                     for n in sig.get("expected_function_nodes", {})]  # fmt: skip
        row: dict[str, Any] = {"answer_key": len(truth)}
        found = {"gitgalaxy": readings.gitgalaxy("seed", lang), "ts_raw": readings.tree_sitter("seed", lang, None)}
        for engine, names in found.items():
            have = {n.casefold() for n in names}
            missed = sorted({n for n in truth if n.casefold() not in have})
            row[engine] = {"pass": bool(truth) and not missed, "found": len(names), "missed": missed[:5]}
        out[lang] = row
    return out


def compare(corpus: Path, only: set[str] | None, full: bool, work: Path, jobs: int) -> dict[str, Any]:
    """Run the gauntlet (GitGalaxy's scans), then read every cell with tree-sitter both ways."""
    cells: list[dict[str, Any]] = []
    gauntlet = ug.run(corpus, only, full, work, jobs, cells_out=cells)
    seeds = ug.rosetta_seeds(corpus)
    readings = Readings(work, _suffix_langs(work / "scans" / "seed" / "seed_galaxy_master.db"))
    ctl = controls(readings, {c["language"] for c in cells if readings.readable(c["language"])}, seeds)
    results: dict[str, Any] = {}
    for cell in cells:
        lang, estate, ref, enc = cell["language"], cell["estate"], cell["reference"], cell["encoding"]
        rename = ug.renamer({k.casefold(): v for k, v in cell["mapping"].items()} | cell["mapping"], cell["id_chars"])
        row: dict[str, Any] = {k: cell[k] for k in ("language", "script", "encoding")}
        row["gauntlet_all_channels_pass"] = not gauntlet[cell["id"]]["diffs"]
        if not readings.readable(lang):
            langs = sorted(set(readings.suffixes.get(lang, {}).values()))
            why = "; ".join(sorted({ts_parser(gl)[1] for gl in langs})) or "no files"
            results[cell["id"]] = {**row, "outcome": "ts-no-grammar", "outcome_decode": "ts-no-grammar", "why": why}
            continue
        row["gitgalaxy"] = verdict(
            _fold(readings.gitgalaxy(ref, lang), rename), _fold(readings.gitgalaxy(estate, lang))
        )
        want_ts = _fold(readings.tree_sitter(ref, lang, None), rename)
        row["ts_raw"] = verdict(want_ts, _fold(readings.tree_sitter(estate, lang, None)))
        row["ts_decode"] = verdict(want_ts, _fold(readings.tree_sitter(estate, lang, enc)))
        if not (ctl[lang]["gitgalaxy"]["pass"] and ctl[lang]["ts_raw"]["pass"]):
            row["outcome"] = row["outcome_decode"] = "control-fail"
        elif lang in NOT_LEGAL and cell["script"] != "ascii":
            row["outcome"] = row["outcome_decode"] = "not-legal"
            row["why"] = NOT_LEGAL[lang]
        else:
            row["outcome"] = _outcome(row["gitgalaxy"]["pass"], row["ts_raw"]["pass"])
            row["outcome_decode"] = _outcome(row["gitgalaxy"]["pass"], row["ts_decode"]["pass"])
        results[cell["id"]] = row
    return {"cells": results, "controls": ctl}


def _outcome(gg: bool, ts: bool) -> str:
    return {(True, True): "both-pass", (True, False): "gg-only", (False, True): "ts-only"}.get((gg, ts), "both-fail")


# ---- summary and report -----------------------------------------------------------------------
def attemptable(cells: dict[str, Any]) -> dict[str, Any]:
    return {cid: r for cid, r in cells.items() if r["outcome"] not in _EXCLUDED}


_EXCLUDED = ("ts-no-grammar", "control-fail", "not-legal")


def _rates(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    return {"cells": n, **{e: {"pass": sum(r[e]["pass"] for r in rows),
                               "rate": round(sum(r[e]["pass"] for r in rows) / n, 4) if n else None}
                           for e in ENGINES}}  # fmt: skip


def summary(data: dict[str, Any]) -> dict[str, Any]:
    """Chart-ready: engine x script and engine x encoding pass rates on the attemptable cells."""
    cells, att = data["cells"], attemptable(data["cells"])
    by: dict[str, dict[str, list[dict[str, Any]]]] = {"script": {}, "encoding": {}, "language": {}}
    for r in att.values():
        for axis in by:
            by[axis].setdefault(r[axis], []).append(r)
    ctl = data["controls"]
    ctl_langs = [lang for lang, c in ctl.items() if c["answer_key"]]
    return {
        "engines": ENGINE_LABEL,
        "cells_total": len(cells),
        "outcomes": dict(Counter(r["outcome"] for r in cells.values())),
        "outcomes_decode": dict(Counter(r["outcome_decode"] for r in cells.values())),
        "headline": _rates(list(att.values())),
        "by_script": {k: _rates(v) for k, v in sorted(by["script"].items())},
        "by_encoding": {k: _rates(v) for k, v in sorted(by["encoding"].items())},
        "by_language": {k: _rates(v) for k, v in sorted(by["language"].items())},
        "controls": {
            e: {"pass": sum(ctl[lang][e]["pass"] for lang in ctl_langs), "languages": len(ctl_langs)}
            for e in ("gitgalaxy", "ts_raw")
        },
        "ts_no_grammar": sorted({r["language"] for r in cells.values() if r["outcome"] == "ts-no-grammar"}),
        "control_fail": sorted({r["language"] for r in cells.values() if r["outcome"] == "control-fail"}),
        "not_legal": sorted({r["language"] for r in cells.values() if r["outcome"] == "not-legal"}),
    }


def _pct(block: dict[str, Any], engine: str) -> str:
    e = block[engine]
    return f"{e['pass']}/{block['cells']} ({100 * e['rate']:.1f}%)" if block["cells"] else "-"


def _table(title: str, rows: dict[str, Any]) -> list[str]:
    out = [f"| {title} | cells | " + " | ".join(ENGINE_LABEL[e] for e in ENGINES) + " |", "|---|---:|---:|---:|---:|"]
    for key, block in rows.items():
        out.append(f"| {key} | {block['cells']} | " + " | ".join(_pct(block, e) for e in ENGINES) + " |")
    return out


def _examples(att: dict[str, Any], engine: str, limit: int = 16) -> list[str]:
    """Failing cells, one per encoding and then one per script of the UTF-8 cells (the grammar's own
    failures), each from a language not shown yet where one fails too: the widest spread, not the
    first language alphabetically."""
    failing = sorted((cid for cid, r in att.items() if not r[engine]["pass"]), key=lambda c: c.split("|")[::-1])
    kinds = [("encoding", e) for e in sorted({att[c]["encoding"] for c in failing})]
    kinds += [("script", s) for s in sorted({att[c]["script"] for c in failing if att[c]["encoding"] == "utf-8"})]
    shown: list[str] = []
    langs: set[str] = set()
    for axis, value in kinds:
        pool = [c for c in failing if att[c][axis] == value and (axis == "encoding" or att[c]["encoding"] == "utf-8")]
        pick = next((c for c in pool if att[c]["language"] not in langs and c not in shown), None)
        pick = pick or next((c for c in pool if c not in shown), None)
        if pick and len(shown) < limit:
            shown.append(pick)
            langs.add(att[pick]["language"])
    return [f"- `{c}`: {att[c][engine]['diff'][:400]}" for c in shown] or ["- (none)"]


def report_md(data: dict[str, Any], summ: dict[str, Any], seconds: float | None = None) -> str:
    cells, att = data["cells"], attemptable(data["cells"])
    head = summ["headline"]
    lines = ["# Unicode Gauntlet: GitGalaxy vs tree-sitter", "",
             f"{summ['cells_total']} gauntlet cells; {head['cells']} both engines can attempt "
             f"(tree-sitter has a grammar and node map for the language, and both engines pass its control)."
             + (f" Wall time {seconds:.0f} s." if seconds is not None else ""), "",
             "## 1. Headline (attemptable cells, function-name channel)", "",
             *[f"- **{ENGINE_LABEL[e]}**: {_pct(head, e)}" for e in ENGINES], "",
             f"Outcomes (GitGalaxy vs tree-sitter raw): {summ['outcomes']}", "",
             f"Outcomes (GitGalaxy vs tree-sitter + decode): {summ['outcomes_decode']}", "",
             f"Controls (UTF-8 seed finds every answer-key function): GitGalaxy "
             f"{summ['controls']['gitgalaxy']['pass']}/{summ['controls']['gitgalaxy']['languages']} languages, "
             f"tree-sitter {summ['controls']['ts_raw']['pass']}/{summ['controls']['ts_raw']['languages']}.", "",
             "## 2. By script", "", *_table("script", summ["by_script"]), "",
             "## By encoding", "", *_table("encoding", summ["by_encoding"]), "",
             "## By language (largest GitGalaxy - tree-sitter raw gap first)", ""]  # fmt: skip
    by_lang = sorted(summ["by_language"].items(),
                     key=lambda kv: (-(kv[1]["gitgalaxy"]["pass"] - kv[1]["ts_raw"]["pass"]), kv[0]))  # fmt: skip
    lines += _table("language", dict(by_lang))
    lines += ["", "## 3. Why: representative failures", ""]
    for e in ENGINES:
        lines += [f"### {ENGINE_LABEL[e]}", "", *_examples(att, e), ""]
    ts_wins = {cid: r for cid, r in att.items() if not r["gitgalaxy"]["pass"] and (r["ts_raw"]["pass"]
               or r["ts_decode"]["pass"])}  # fmt: skip
    lines += ["### Cells where tree-sitter beats GitGalaxy", ""]
    lines += [f"- `{cid}` (raw {'pass' if r['ts_raw']['pass'] else 'fail'}, +decode "
              f"{'pass' if r['ts_decode']['pass'] else 'fail'}): GitGalaxy {r['gitgalaxy']['diff']}"
              for cid, r in sorted(ts_wins.items())] or ["- (none)"]  # fmt: skip
    ctl = data["controls"]
    lines += ["", "## Controls", "", "| language | answer key | GitGalaxy | tree-sitter |", "|---|---:|---|---|"]
    for lang, c in ctl.items():
        cols = [("pass" if c[e]["pass"] else f"FAIL missed {c[e]['missed']}" if c["answer_key"]
                 else "no answer-key functions: nothing to measure") + f" ({c[e]['found']} found)"
                for e in ("gitgalaxy", "ts_raw")]  # fmt: skip
        lines.append(f"| {lang} | {c['answer_key']} | " + " | ".join(cols) + " |")
    no_grammar = {r["language"]: r["why"] for r in cells.values() if r["outcome"] == "ts-no-grammar"}
    not_legal = {r["language"]: r["why"] for r in cells.values() if r["outcome"] == "not-legal"}
    lines += ["", "## Not a legal program (`not-legal`)", ""]
    lines += [f"- {lang}: {why}" for lang, why in sorted(not_legal.items())] or ["- (none)"]
    lines += ["", "## Not attempted by tree-sitter (`ts-no-grammar`)", ""]
    lines += [f"- {lang}: {why}" for lang, why in sorted(no_grammar.items())] or ["- (none)"]
    lines += ["", "## 4. Methodology and caveats", "", *METHODOLOGY]
    return "\n".join(lines) + "\n"


METHODOLOGY = [
    "- The oracle is the gauntlet's own metamorphic design, `facts(T(seed)) == T(facts(seed))`, applied to one "
    "channel: the multiset of function names (case-folded, as the gauntlet compares) in the files tree-sitter "
    "reads. Each engine is compared with ITSELF on the cell's reference, so a construct an extractor misses on "
    "both sides cancels out; only what the script or the encoding changes counts.",
    "- The gauntlet (and so the rename list) was designed around GitGalaxy: the renamed units are the functions "
    "GitGalaxy found in the seed. Controls guard the other side: a language counts only where tree-sitter finds "
    "every function keyword-rosetta's hand-verified answer key lists on the UTF-8 seed.",
    "- tree-sitter's side is its raw reading through tree_sitter_accuracy_audit's NODE_MAPS / `_get_node_name` -- "
    "not the audit's reconciled ground truth. A language absent from NODE_MAPS is `ts-no-grammar` even when the "
    "pack has a grammar (objective-c, cobol, ...), because writing node maps here would be a new extractor.",
    "- `ts-raw` hands tree-sitter the file's bytes, as tree-sitter-based tools do. It has no notion of a BOM, "
    "UTF-16 or a legacy code page; `ts-decode` shows what a careful integrator gets by decoding first. A name "
    "whose bytes are not UTF-8 is recorded as broken, never decoded with a lossy handler.",
    "- GitGalaxy decodes Shift-JIS, GB18030 and EBCDIC cells because the scan DECLARES the page "
    "(`--source-encoding`, as the gauntlet runs them); cp1252 is undeclared (its fallback is what those cells "
    "test). `ts-decode` gets the same knowledge of the true encoding; `ts-raw` gets none.",
    "- Legality: the renames follow the gauntlet's legality.json. Dart is excluded (`not-legal`): its spec allows "
    "ASCII letters only, so a grammar refusing `probeBranch名前` is correct. Other languages' rules for combining "
    "marks (Mn / Mc: Devanagari, Tamil, NFD) were NOT checked against each spec here -- Kotlin's grammar names "
    "only L* letters and Nd digits, so some of tree-sitter-kotlin's Devanagari / Tamil / NFD failures may be "
    "the grammar rejecting code its compiler would too. Han / Hangul (Lo letters) are legal where Unicode is.",
    "- The file-to-grammar choice uses the seed's GitGalaxy language per suffix (a slight help to tree-sitter).",
    "- Parameter counts, classes and the other channels are not compared; `gauntlet_all_channels_pass` in "
    "results.json carries GitGalaxy's full gauntlet verdict for reference.",
    "- The default plan samples two encodings per script (the gauntlet's CI plan); `--full` runs every "
    "(script, encoding) pair, including cp1252.",
]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", type=Path,
                    default=Path(os.environ.get("KEYWORD_ROSETTA_PATH", ug.REPO_ROOT.parent / "keyword-rosetta")))  # fmt: skip
    ap.add_argument("--only", nargs="*", help="seed languages to run (default: all)")
    ap.add_argument("--full", action="store_true", help="every encoding for every script (default: two each)")
    ap.add_argument("--out", type=Path, required=True, help="write results.json, summary.json and report.md here")
    ap.add_argument("--work", type=Path, help="keep the estates and scans here")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 4, help="cells scanned in parallel")
    args = ap.parse_args(argv)
    work = args.work or Path(tempfile.mkdtemp(prefix="unicode_gauntlet_vs_ts_"))
    start = time.monotonic()
    data = compare(args.corpus, set(args.only) if args.only else None, args.full, work, args.jobs)
    seconds = time.monotonic() - start
    summ = summary(data)
    summ["wall_seconds"] = round(seconds, 1)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    (args.out / "summary.json").write_text(json.dumps(summ, indent=1, ensure_ascii=False), encoding="utf-8")
    (args.out / "report.md").write_text(report_md(data, summ, seconds), encoding="utf-8")
    head = summ["headline"]
    print(f"{head['cells']} attemptable cells: " + ", ".join(f"{ENGINE_LABEL[e]} {_pct(head, e)}" for e in ENGINES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
