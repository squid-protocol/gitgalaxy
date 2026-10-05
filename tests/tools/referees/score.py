r"""Scorecard for the COBOL / CICS referee panel (#4377).

Reads referee-facts/1 documents (facts.py) -- the engine's, each referee's -- and the answer key,
and scores every source per fact channel against the key (ground truth) and against each other.

    python tests/tools/referees/score.py --facts <dir> [--md scorecard.md] [--json scorecard.json] \
        [--disagreements disagreements.json]

`<dir>` holds one sub-directory per corpus (`<dir>/<corpus>/<source>.json`); the key is read from
tests/cobol_mainframe/answer_key/<corpus>.json unless `<dir>/<corpus>/key.json` exists.

Scoring rules (pinned by tests/cobol_mainframe/test_referee_score.py):
- The universe of a channel is the key's files: its programs, or its keyed copybooks for
  `layouts`. A source's facts on other files are ignored.
- P = correct / reported, R = correct / true, over (file, value) pairs. A file a source failed to
  parse reports nothing, so its truth counts against R. `R(parsed)` is R over the files the source
  parsed, which separates "could not parse" from "parsed, and got it wrong".
- A channel a source cannot produce at all (not in its `channels`) is n/a, not zero.
- `cics_commands` is scored over the verbs the key censuses in that corpus (file control, BMS
  SEND/RECEIVE MAP, queues, LINK / XCTL, task control): a referee's ASKTIME is not a false positive.
- Agreement between two sources is |A & B| / |A | B| over the files both parsed.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import facts as F

KEY_DIR = REPO_ROOT / "tests" / "cobol_mainframe" / "answer_key"


def universe(key: dict[str, Any], channel: str) -> list[str]:
    files = key["files"]
    if channel in F.COPYBOOK_CHANNELS:
        return sorted(r for r, e in files.items() if channel in e["facts"])
    return sorted(r for r, e in files.items() if "program_ids" in e["facts"])


def _verb(value: str) -> str:
    return value.split(" ", 1)[1] if " " in value else value


def file_values(doc: dict[str, Any], rel: str, channel: str, verbs: Optional[set[str]] = None) -> Optional[set[str]]:
    """The source's values for one file and channel; None when it did not parse the file."""
    entry = doc["files"].get(rel)
    if entry is None or entry["status"] == "fail":
        return None
    vals = set(entry["facts"].get(channel, []))
    if verbs is not None:
        vals = {v for v in vals if _verb(v) in verbs}
    return vals


def key_verbs(key: dict[str, Any]) -> set[str]:
    return {_verb(v) for e in key["files"].values() for v in e["facts"].get("cics_commands", [])}


def score_channel(key: dict[str, Any], doc: dict[str, Any], channel: str) -> Optional[dict[str, int]]:
    """tp / reported / true over the channel's universe, plus the parsed-only counterparts."""
    if channel not in doc["channels"]:
        return None
    verbs = key_verbs(key) if channel == "cics_commands" else None
    out = {"tp": 0, "reported": 0, "true": 0, "true_parsed": 0, "files": 0, "files_parsed": 0}
    for rel in universe(key, channel):
        truth = file_values(key, rel, channel) or set()
        got = file_values(doc, rel, channel, verbs)
        out["files"] += 1
        out["true"] += len(truth)
        if got is None:
            continue
        out["files_parsed"] += 1
        out["true_parsed"] += len(truth)
        out["reported"] += len(got)
        out["tp"] += len(truth & got)
    return out


def agreement(key: dict[str, Any], a: dict[str, Any], b: dict[str, Any], channel: str) -> Optional[dict[str, int]]:
    if channel not in a["channels"] or channel not in b["channels"]:
        return None
    verbs = key_verbs(key) if channel == "cics_commands" else None
    both = union = 0
    for rel in universe(key, channel):
        va, vb = file_values(a, rel, channel, verbs), file_values(b, rel, channel, verbs)
        if va is None or vb is None:
            continue
        both += len(va & vb)
        union += len(va | vb)
    return {"both": both, "union": union}


def disagreements(key: dict[str, Any], a: dict[str, Any], b: dict[str, Any], channel: str) -> list[dict[str, Any]]:
    """Every value exactly one of `a` / `b` reports on a file both parsed, with the key's verdict."""
    if channel not in a["channels"] or channel not in b["channels"]:
        return []
    verbs = key_verbs(key) if channel == "cics_commands" else None
    out = []
    for rel in universe(key, channel):
        va, vb = file_values(a, rel, channel, verbs), file_values(b, rel, channel, verbs)
        if va is None or vb is None:
            continue
        truth = file_values(key, rel, channel) or set()
        for v in sorted(va ^ vb):
            out.append({"file": rel, "value": v, "only": a["source"] if v in va else b["source"], "in_key": v in truth})
    return out


def _pct(n: int, d: int) -> str:
    return "—" if d == 0 else f"{100.0 * n / d:.1f}%"


def _cell(s: Optional[dict[str, int]]) -> str:
    if s is None:
        return "n/a"
    if s["true"] == 0 and s["reported"] == 0:
        return "—"
    cell = f"P {_pct(s['tp'], s['reported'])} · R {_pct(s['tp'], s['true'])}"
    if s["files_parsed"] < s["files"]:
        cell += f" (R parsed {_pct(s['tp'], s['true_parsed'])})"
    return cell


def _sum(a: Optional[dict[str, int]], b: Optional[dict[str, int]]) -> Optional[dict[str, int]]:
    if a is None:
        return b
    if b is None:
        return a
    return {k: a[k] + b[k] for k in a}


def load_corpora(facts_dir: Path) -> dict[str, dict[str, Any]]:
    """corpus -> {"key": key doc, "sources": {name: doc}}."""
    out: dict[str, dict[str, Any]] = {}
    for cdir in sorted(p for p in facts_dir.iterdir() if p.is_dir()):
        kp = cdir / "key.json"
        if kp.is_file():
            key = F.load(kp)
        else:
            raw = KEY_DIR / f"{cdir.name}.json"
            if not raw.is_file():
                continue
            key = F.key_doc(json.loads(raw.read_text(encoding="utf-8")))
        sources = {d["source"]: d for d in (F.load(p) for p in sorted(cdir.glob("*.json")) if p.name != "key.json")}
        out[cdir.name] = {"key": key, "sources": sources}
    return out


def source_order(corpora: dict[str, dict[str, Any]]) -> list[str]:
    names = {s for c in corpora.values() for s in c["sources"]}
    return (["engine"] if "engine" in names else []) + sorted(names - {"engine"})


def parse_stats(corpora: dict[str, dict[str, Any]], source: str) -> dict[str, Any]:
    counts = {"ok": 0, "partial": 0, "fail": 0, "missing": 0}
    secs: list[float] = []
    for c in corpora.values():
        doc = c["sources"].get(source)
        if doc is None:
            continue
        files: set[str] = set()
        for ch in doc["channels"]:
            files.update(universe(c["key"], ch))
        for rel in files:
            entry = doc["files"].get(rel)
            if entry is None:
                counts["missing"] += 1
                continue
            counts[entry["status"]] += 1
            if entry.get("seconds") is not None:
                secs.append(entry["seconds"])
    return {**counts, "median_s": statistics.median(secs) if secs else None, "total_s": sum(secs) if secs else None}


def scorecard(corpora: dict[str, dict[str, Any]], seed: int = 4377) -> tuple[str, dict[str, Any], dict[str, Any]]:
    sources = source_order(corpora)
    data: dict[str, Any] = {"sources": {}, "channels": {}, "agreement": {}, "per_corpus": {}}
    md = ["## Referee panel scorecard (#4377)", ""]
    md.append("Corpora: " + ", ".join(f"`{n}` @ `{c['key']['version']}`" for n, c in corpora.items()) + ".")
    md.append("")
    md.append("### Parse success and speed (the key-covered members each source reads: programs and / or keyed copybooks)")
    md.append("")
    md.append("| source | version(s) | clean | partial | failed | not attempted | median s / member |")
    md.append("|---|---|---|---|---|---|---|")
    for s in sources:
        st = parse_stats(corpora, s)
        vers = sorted({c["sources"][s]["version"] for c in corpora.values() if s in c["sources"]})
        data["sources"][s] = {**st, "versions": vers}
        med = "—" if st["median_s"] is None else f"{st['median_s']:.3f}"
        md.append(f"| {s} | {', '.join(vers)} | {st['ok']} | {st['partial']} | {st['fail']} | {st['missing']} | {med} |")
    md.append("")
    md.append("Per corpus, clean / partial / failed:")
    md.append("")
    md.append("| source | " + " | ".join(corpora) + " |")
    md.append("|---|" + "---|" * len(corpora))
    for s in sources:
        cells = []
        for c in corpora.values():
            st = parse_stats({"one": c}, s) if s in c["sources"] else None
            cells.append("—" if st is None else f"{st['ok']} / {st['partial']} / {st['fail']}")
        md.append(f"| {s} | " + " | ".join(cells) + " |")
    md.append("")
    md.append("### Each source vs the answer keys (ground truth), all corpora pooled")
    md.append("")
    md.append("| channel | " + " | ".join(sources) + " |")
    md.append("|---|" + "---|" * len(sources))
    for ch in F.CHANNELS:
        row = []
        data["channels"][ch] = {}
        for s in sources:
            tot: Optional[dict[str, int]] = None
            for name, c in corpora.items():
                if s in c["sources"]:
                    sc = score_channel(c["key"], c["sources"][s], ch)
                    data["per_corpus"].setdefault(name, {}).setdefault(ch, {})[s] = sc
                    tot = _sum(tot, sc)
            data["channels"][ch][s] = tot
            row.append(_cell(tot))
        md.append(f"| {ch} | " + " | ".join(row) + " |")
    md.append("")
    md.append("P = correct / reported, R = correct / true over (file, value) pairs; `R parsed` counts only "
              "the files the source parsed. n/a = the source does not produce that channel.")  # fmt: skip
    if "engine" in sources and len(sources) > 1:
        md.append("")
        md.append("### Agreement with the engine (|A ∩ B| / |A ∪ B| on files both parsed)")
        md.append("")
        refs = [s for s in sources if s != "engine"]
        md.append("| channel | " + " | ".join(refs) + " |")
        md.append("|---|" + "---|" * len(refs))
        for ch in F.CHANNELS:
            row = []
            for r in refs:
                tot = None
                for c in corpora.values():
                    if r in c["sources"] and "engine" in c["sources"]:
                        tot = _sum(tot, agreement(c["key"], c["sources"]["engine"], c["sources"][r], ch))
                data["agreement"].setdefault(ch, {})[r] = tot
                row.append("n/a" if tot is None else _pct(tot["both"], tot["union"]))
            md.append(f"| {ch} | " + " | ".join(row) + " |")
    dis: dict[str, Any] = {}
    if "engine" in sources:
        rng = random.Random(seed)
        for r in [s for s in sources if s != "engine"]:
            for ch in F.CHANNELS:
                rows = []
                for name, c in corpora.items():
                    if r in c["sources"] and "engine" in c["sources"]:
                        rows += [{"corpus": name, **d} for d in disagreements(c["key"], c["sources"]["engine"], c["sources"][r], ch)]  # fmt: skip
                if rows:
                    by = {}
                    for d in rows:
                        by.setdefault(f"{d['only']}-only, {'in key' if d['in_key'] else 'not in key'}", []).append(d)
                    dis.setdefault(r, {})[ch] = {pat: {"count": len(v), "sample": rng.sample(v, min(8, len(v)))}
                                                 for pat, v in sorted(by.items())}  # fmt: skip
    return "\n".join(md) + "\n", data, dis


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--facts", type=Path, required=True)
    ap.add_argument("--md", type=Path)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--disagreements", type=Path)
    args = ap.parse_args()
    md, data, dis = scorecard(load_corpora(args.facts))
    print(md)
    if args.md:
        args.md.write_text(md, encoding="utf-8")
    if args.json:
        args.json.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if args.disagreements:
        args.disagreements.write_text(json.dumps(dis, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
