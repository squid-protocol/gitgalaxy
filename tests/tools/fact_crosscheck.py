#!/usr/bin/env python3
r"""#4273: the engine and the det translator, cross-checked fact by fact, and gated.

The engine (the scanner's master DB, read through GalaxyIR) and the det COBOL-to-Java translator
(gitgalaxy/tools/cobol_to_java/det, tree-sitter) each derive the same facts from the same COBOL:
paragraphs and their extents, PERFORM / GO TO edges, CALL / LINK / XCTL, COPY members and the files
they resolve to, data items with PIC / USAGE / OCCURS / REDEFINES / VALUE, record offsets, MOVEs,
EXEC CICS commands. Where the two disagree one of them is wrong (or the fact is defined differently),
and a translation could silently build on the wrong one. This tool compares them per program and
per channel, scores each side against the answer keys, and gates on disagreements nobody explained.

    python tests/tools/fact_crosscheck.py run    [--md out.md] [--json out.json]   # report only
    python tests/tools/fact_crosscheck.py check  [--md out.md]                      # the CI gate
    python tests/tools/fact_crosscheck.py update                                    # rewrite the ledger
    python tests/tools/fact_crosscheck.py assign CAUSE 'REGEX' [--untriaged-only]   # triage

Universe: every program of each keyed corpus (tests/cobol_mainframe/corpora.json), every program a
det-port equivalence case translates (tests/equivalence/*/case.json, with the case's own copy
directories), the keyed copybooks (`layouts`), and estate-crucible's COBOL programs at its pin
(tests/_estate_crucible_pin.py; --crucible / $ESTATE_CRUCIBLE_PATH; --no-crucible to leave it out).
Scans are cached per engine state (mainframe_corpus.py); the translator side takes ~2 s a corpus.

Sides: tests/tools/referees/engine_adapter.py (engine) and referees/translator_adapter.py
(translator), both referee-facts/1, plus three channels this tool adds: `offsets` (every record
the translator lays out, against GalaxyIR.record_layout of the engine entry at the same file,
line and level), `moves` (MOVE pairs, canonical operands) and `copy_resolution`.

Comparison rules:
- A channel is compared on a file when both sides produced it. A side that refused the file (the
  translator's CopyNotFound / LayoutError / ExprError, #4411; the engine's missing file) records one
  `status` disagreement instead, and the refused division's channels are not compared.
- `cics_commands` is compared over the verbs the corpus's key censuses (score.py's rule): an
  ASKTIME the translator reads and the key never asks about is not a disagreement.
- Agreement = |E & T| / |E | T| over (file, value) pairs.

The gate: tests/cobol_mainframe/fact_crosscheck_ledger.json lists every known disagreement
(`<corpus> :: <channel> | <file> | <only side> | <value>`) with its cause; each cause names the side
that is wrong (`engine`, `translator`, or `definitional`: both right under their own definition) and
its issue. `check` fails on a disagreement the ledger does not list (a regression on either side, or a
new estate shape), and on a ledger entry with no cause. One the ledger lists that no longer
reproduces does not fail: it is reported, and `update` drops it (the ratchet). Ownership per channel,
with the numbers: docs/language_status/fact_ownership.md.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Optional

TOOLS = Path(__file__).resolve().parent
REPO_ROOT = TOOLS.parent.parent
for p in (str(REPO_ROOT), str(TOOLS), str(TOOLS / "referees")):
    if p not in sys.path:
        sys.path.insert(0, p)

import engine_adapter as EA
import estate_key as EK
import facts as F
import mainframe_corpus as MC
import translator_adapter as TA

LEDGER = REPO_ROOT / "tests" / "cobol_mainframe" / "fact_crosscheck_ledger.json"
CASES = REPO_ROOT / "tests" / "equivalence"
SCHEMA = "fact-crosscheck-ledger/1"
CRUCIBLE = "estate-crucible"
SIDES = ("engine", "translator", "definitional")
DATA_CHANNELS = frozenset({"data_items", "pic", "usage", "occurs", "redefines", "value", "offsets"})
COPY_CHANNELS = frozenset({"copybooks", "copy_resolution"})
PROC_CHANNELS = frozenset({"units", "unit_extents", "edges", "calls", "moves", "cics_commands", "cics_files"})
COMPARED = tuple(ch for ch in TA.CHANNELS)  # every channel the translator produces; the engine produces all


# ------------------------------------------------------------------------------
# The universe
# ------------------------------------------------------------------------------
def case_programs() -> dict[str, dict[str, list[str]]]:
    """corpus -> {program path: the copy directories its det-port case names}."""
    out: dict[str, dict[str, list[str]]] = defaultdict(dict)
    for cj in sorted(CASES.glob("*/case.json")):
        d = json.loads(cj.read_text(encoding="utf-8"))
        if not d.get("program_source") or not d.get("corpus"):
            continue
        dirs = list(d.get("copy_dirs", [])) + list((d.get("db2") or {}).get("include_dirs", []))
        for src in [
            d["program_source"],
            *[p["program_source"] for p in d.get("programs", []) if p.get("program_source")],
        ]:
            out[d["corpus"]].setdefault(src, dirs)
    return dict(out)


def augmented_key(key: dict[str, Any], extra: list[str]) -> dict[str, Any]:
    """The key with each extra program (a det-port case's, unkeyed) added as an empty entry: both sides
    produce facts for it; no key score counts it."""
    progs = dict(key.get("programs", {}))
    for rel in extra:
        progs.setdefault(rel, {})
    return {**key, "programs": progs}


# ------------------------------------------------------------------------------
# The engine's extra channels
# ------------------------------------------------------------------------------
def _closure(ir: Any, ef: Any) -> list[Any]:
    seen: dict[str, Any] = {}
    todo = [ef]
    while todo:
        f = todo.pop()
        for c in ir._copy_files(f):
            if c.file_path not in seen:
                seen[c.file_path] = c
                todo.append(c)
    return list(seen.values())


def engine_extras(ir: Any, ef: Any, records: list[tuple[Any, str, int]]) -> dict[str, set[str]]:
    """offsets (for every record the translator laid out: the engine entry at the same file / line / level,
    through GalaxyIR.record_layout), moves and copy_resolution."""
    out: dict[str, set[str]] = {"offsets": set(), "moves": set(), "copy_resolution": set()}
    closure = _closure(ir, ef)
    by_loc: dict[tuple[str, int, int], tuple[Any, Any]] = {}
    for f in [ef, *closure]:
        for it in f.data_items:
            by_loc.setdefault((f.file_path, it.line, it.level), (f, it))
    # #4472: a section-level COPY ... REPLACING lays out the REPLACED records (ef.records, entries in
    # ef.copied_items), not the copybook's own: key each replaced root by the copybook root it came from.
    replaced_at: dict[tuple[str, int, int], list[Any]] = {}
    for st in sorted(ef.copy_statements, key=lambda c: c.line):
        cb, roots = ir._copy_roots(st.member, ef, ef, 0, st.library)
        roots = roots or (cb.template_records if cb is not None else [])
        copied = {id(it) for it in ef.copied_items}
        replaced = [r for r in ef.records if r.line == st.line and id(r) in copied]
        if cb is None or len(replaced) != len(roots):
            continue
        for src, new in zip(roots, replaced):  # one COPY per statement: the record's name picks among them
            replaced_at.setdefault((cb.file_path, src.line, src.level), []).append(new)
    for rec, file, line in records:
        hit = by_loc.get((file, line, rec.level))
        cands = replaced_at.get((file, line, rec.level))
        if cands:
            new = next((r for r in cands if (r.name or "").upper() == rec.name.upper()), None)
            hit = (ef, new) if new is not None else hit
        if hit is None:
            out["offsets"].add(f"{rec.name} (record) not read")
            continue
        owner, item = hit
        ext = None
        if owner is not ef:
            roots = [r for r in owner.records if r.level not in (66, 88)]
            if roots and roots[-1] is item:
                ext = ir._copy_extension(ef, owner) or None
        try:
            lay = ir.record_layout(owner, item, ext)
        except Exception as e:  # noqa: BLE001 -- a layout the engine cannot build is the fact
            out["offsets"].add(f"{rec.name} (record) raised {type(e).__name__}")
            continue
        name = (item.name or "FILLER").upper()
        for fld in lay["fields"]:
            if fld.get("pic") and fld.get("name") and fld["name"].upper() != "FILLER":
                out["offsets"].add(f"{name}/{fld['name'].upper()} @{fld['offset']}+{fld['bytes']}")
        out["offsets"].add(f"{name} (record) +{lay['bytes'] if lay['bytes'] is not None else '?'}")
    for m in ef.data_moves:
        if m.verb == "MOVE" and not m.corresponding and m.target:
            out["moves"].add(TA.move_value(m.line, TA.canon_text_operand(m.source), TA.canon_name(m.target)))
    for path in ef.copy_deps:
        if "#" not in path:
            out["copy_resolution"].add(f"{Path(path).stem.upper()} -> {path}")
    return out


def engine_side(db: Path, corpus: str, key: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir

    doc = EA.engine_doc(db, corpus, key)
    doc["channels"] = sorted(set(doc["channels"]) | set(TA.EXTRA_CHANNELS))
    ir = load_galaxy_ir(db)
    for rel, entry in doc["files"].items():
        ef = ir.files.get(rel)
        if ef is None or "program_ids" not in entry["facts"]:
            continue
        records = ctx.get(rel, {}).get("records", [])
        for ch, vals in engine_extras(ir, ef, records).items():
            entry["facts"][ch] = sorted(vals)
    return doc


# ------------------------------------------------------------------------------
# The key's side of the extra channels
# ------------------------------------------------------------------------------
_KEY_MOVE = re.compile(r"^L(\d+) MOVE (.+?)(?:\(:\))? -> (.+?)(?:\(:\))?$")


def key_side(key: dict[str, Any], crucible_members: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """facts.key_doc plus moves (the key's validated `data_moves`, MOVE only), copy_resolution (each COPY's
    `resolves_to`) and, on estate-crucible, offsets (its per-record `layouts`)."""
    doc = F.key_doc(key)
    doc["channels"] = sorted(set(doc["channels"]) | set(TA.EXTRA_CHANNELS))
    for rel, prog in key.get("programs", {}).items():
        entry = doc["files"].get(rel)
        if entry is None:
            continue
        entry["facts"]["copy_resolution"] = sorted(
            f"{c['name'].upper()} -> {c['resolves_to']}" for c in prog.get("copybooks", []) if c.get("resolves_to")
        )
        dm = key.get("data_moves", {}).get(rel)
        if dm is not None:
            moves = set()
            for v in dm.get("moves", []):
                m = _KEY_MOVE.match(v)
                if m and " CORR " not in v:
                    moves.add(
                        TA.move_value(int(m.group(1)), TA.canon_text_operand(m.group(2)), TA.canon_name(m.group(3)))
                    )
            entry["facts"]["moves"] = sorted(moves)
        if crucible_members is not None and rel in crucible_members:
            entry["facts"]["copy_resolution"] = sorted(
                f"{c['member'].upper()} -> {c['resolves_to']}"
                for c in crucible_members[rel].get("copies", []) if c.get("resolves_to")
            )  # fmt: skip
            offs = set()
            for lay in crucible_members[rel].get("layouts", []):
                r = lay["record"].upper()
                offs.add(f"{r} (record) +{lay['bytes'] if lay.get('bytes') is not None else '?'}")
                kept: list[tuple[int, int]] = []
                for fld in lay.get("fields", []):
                    lo, hi = fld["offset"], fld["offset"] + fld["bytes"]
                    if any(lo < b and a < hi for a, b in kept):
                        continue  # a REDEFINES overlay: unscored on both sides (record_layout skips overlays)
                    kept.append((lo, hi))
                    if fld.get("pic") and fld.get("name") and fld["name"].upper() != "FILLER":
                        offs.add(f"{r}/{fld['name'].upper()} @{fld['offset']}+{fld['bytes']}")
            entry["facts"]["offsets"] = sorted(offs)
    return doc


# ------------------------------------------------------------------------------
# Comparison
# ------------------------------------------------------------------------------
def dis_id(corpus: str, channel: str, rel: str, only: str, value: str) -> str:
    return f"{corpus} :: {channel} | {rel} | {only} | {value}"


def _vals(entry: dict[str, Any], ch: str, verbs: Optional[set[str]]) -> set[str]:
    v = set(entry["facts"].get(ch, []))
    if verbs is not None:
        v = {x for x in v if x.split(" ", 1)[-1] in verbs}
    return v


def _record_of(value: str) -> str:
    return re.split(r"/| \(record\)", value, maxsplit=1)[0]


def _records(values: set[str]) -> set[str]:
    return {_record_of(v) for v in values}


def _only_records(values: set[str], records: set[str]) -> set[str]:
    return {v for v in values if _record_of(v) in records}


def compare(
    corpus: str, eng: dict[str, Any], tr: dict[str, Any], key: dict[str, Any], keyed: set[str]
) -> dict[str, Any]:
    """Per channel: compared files, both / engine-only / translator-only counts, each side's tp / reported /
    true against the key (keyed files only), and the disagreements."""
    verbs = {v.split(" ", 1)[-1] for e in key["files"].values() for v in e["facts"].get("cics_commands", [])}
    stats: dict[str, Counter] = {ch: Counter() for ch in COMPARED}
    dis: list[dict[str, str]] = []
    for rel in sorted(set(eng["files"]) & set(tr["files"])):
        e, t = eng["files"][rel], tr["files"][rel]
        is_program = "program_ids" in e["facts"] or rel in key["files"] and "program_ids" in key["files"][rel]["facts"]
        failed = set(t.get("failed", []))
        if t["status"] == "fail" and not failed:
            failed = {"copy", "data", "procedure"}
        if e["status"] == "fail":
            dis.append({"channel": "status", "file": rel, "only": "translator", "value": f"engine: {e['error']}"})
            continue
        if {"data", "procedure"} <= failed:
            failed.add("copy")  # a program refused whole was not read as COBOL (code page, free format ...)
        if failed:
            dis.append(
                {"channel": "status", "file": rel, "only": "engine", "value": f"translator refused: {t['error']}"}
            )
        kentry = key["files"].get(rel) if rel in keyed else None
        for ch in COMPARED:
            if (ch in DATA_CHANNELS and "data" in failed) or (ch in PROC_CHANNELS and "procedure" in failed):
                continue
            if ch in COPY_CHANNELS and "copy" in failed:
                continue
            if ch == "layouts" and (is_program or "layouts" not in e["facts"]):
                continue
            if ch != "layouts" and not is_program:
                continue
            if t["status"] == "fail" and ch == "layouts":
                continue
            v = verbs if ch == "cics_commands" else None
            ev, tv = _vals(e, ch, v), _vals(t, ch, v)
            s = stats[ch]
            s["files"] += 1
            s["both"] += len(ev & tv)
            s["engine_only"] += len(ev - tv)
            s["translator_only"] += len(tv - ev)
            for only, vals in (("engine", ev - tv), ("translator", tv - ev)):
                for val in sorted(vals):
                    dis.append({"channel": ch, "file": rel, "only": only, "value": val})
            if kentry is not None and ch in kentry["facts"]:
                truth = _vals(kentry, ch, v)
                if ch == "offsets":
                    # the records the key lays out (every 01 a program writes) that both sides laid out
                    both_recs = _records(ev) & _records(tv) & _records(truth)
                    truth, ev, tv = (_only_records(x, both_recs) for x in (truth, ev, tv))
                s["key_files"] += 1
                s["true"] += len(truth)
                s["engine_reported"] += len(ev)
                s["engine_tp"] += len(ev & truth)
                s["translator_reported"] += len(tv)
                s["translator_tp"] += len(tv & truth)
    for d in dis:
        d["id"] = dis_id(corpus, d["channel"], d["file"], d["only"], d["value"])
        d["corpus"] = corpus
    return {"stats": {ch: dict(s) for ch, s in stats.items()}, "disagreements": dis}


# ------------------------------------------------------------------------------
# Running every corpus
# ------------------------------------------------------------------------------
def _crucible_db(crucible: Path) -> Path:
    import estate_crucible as EC

    ref = subprocess.run(["git", "-C", str(crucible), "rev-parse", "--short=12", "HEAD"],  # noqa: S607
                         capture_output=True, text=True, check=False).stdout.strip() or "unpinned"  # fmt: skip
    scan_dir = MC.cache_root() / "_scans" / CRUCIBLE / f"{ref}-{MC.engine_key()}"
    db = scan_dir / f"estate_galaxy_master.db"
    if db.is_file():
        return db
    found = sorted(scan_dir.glob("*_galaxy_master.db")) if scan_dir.is_dir() else []
    if found:
        return found[0]
    return EC.scan(crucible, scan_dir)


def run_all(crucible: Optional[Path], cache: Path, only: Optional[list[str]] = None, log=print) -> dict[str, Any]:
    TA.det()  # the translator extra must be installed: fail here, never skip
    cases = case_programs()
    corpora = [c for c in MC.load_manifest() if c.get("answer_key")]
    out: dict[str, Any] = {"corpora": {}, "disagreements": [], "seconds": {}}
    for c in corpora:
        if only and c["name"] not in only:
            continue
        t0 = time.monotonic()
        root = MC.require_clone(c)
        key = json.loads((REPO_ROOT / c["answer_key"]).read_text(encoding="utf-8"))
        extra = sorted(set(cases.get(c["name"], {})) - set(key.get("programs", {})))
        missing = [r for r in extra if not (root / r).is_file()]
        if missing:
            raise SystemExit(f"{c['name']}: det-port case programs not in the clone: {missing}")
        akey = augmented_key(key, extra)
        db = MC.scan(c)
        t_scan = time.monotonic() - t0
        tr, ctx = TA.translator_doc(root, c["name"], akey, cache, cases.get(c["name"]))
        eng = engine_side(db, c["name"], akey, ctx)
        kdoc = key_side(key)
        res = compare(c["name"], eng, tr, kdoc, set(key.get("programs", {})) | set(key.get("copybook_layouts", {})))
        res["programs"] = len(akey["programs"])
        res["case_programs"] = len(cases.get(c["name"], {}))
        res["translator_status"] = dict(Counter(f["status"] for f in tr["files"].values()))
        out["corpora"][c["name"]] = res
        out["disagreements"] += res["disagreements"]
        out["seconds"][c["name"]] = {"scan": round(t_scan, 1), "total": round(time.monotonic() - t0, 1)}
        log(f"{c['name']}: {res['programs']} programs, {len(res['disagreements'])} disagreements "
            f"({out['seconds'][c['name']]['total']} s)")  # fmt: skip
    if crucible is not None and (not only or CRUCIBLE in only):
        from _estate_crucible_pin import pin_mismatch

        bad = pin_mismatch(crucible)
        if bad:
            raise SystemExit(bad)
        t0 = time.monotonic()
        key = EK.convert(crucible)
        members = {}
        for app in sorted((crucible / "key" / "apps").glob("*.json")):
            members.update(json.loads(app.read_text(encoding="utf-8"))["members"])
        db = _crucible_db(crucible)
        t_scan = time.monotonic() - t0
        root = crucible / "estate"
        tr, ctx = TA.translator_doc(root, CRUCIBLE, key, cache)
        eng = engine_side(db, CRUCIBLE, key, ctx)
        kdoc = key_side(key, members)
        res = compare(CRUCIBLE, eng, tr, kdoc, set(key["programs"]))
        res["programs"] = len(key["programs"])
        res["case_programs"] = 0
        res["translator_status"] = dict(Counter(f["status"] for f in tr["files"].values()))
        out["corpora"][CRUCIBLE] = res
        out["disagreements"] += res["disagreements"]
        out["seconds"][CRUCIBLE] = {"scan": round(t_scan, 1), "total": round(time.monotonic() - t0, 1)}
        log(f"{CRUCIBLE}: {res['programs']} programs, {len(res['disagreements'])} disagreements")
    return out


# ------------------------------------------------------------------------------
# The ledger
# ------------------------------------------------------------------------------
def load_ledger(path: Path = LEDGER) -> dict[str, Any]:
    if not path.is_file():
        return {"schema": SCHEMA, "causes": {}, "disagreements": {}}
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise SystemExit(f"{path}: not a {SCHEMA} ledger")
    return doc


def save_ledger(doc: dict[str, Any], path: Path = LEDGER) -> None:
    doc = {"schema": SCHEMA, "about": doc.get("about", ABOUT), "causes": dict(sorted(doc["causes"].items())),
           "disagreements": dict(sorted(doc["disagreements"].items()))}  # fmt: skip
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


ABOUT = ("Every known engine-vs-translator fact disagreement (tests/tools/fact_crosscheck.py, #4273): id -> cause. "
         "A cause names the side that is wrong (engine / translator / definitional) and its issue. "
         "A two-way ratchet: CI fails on a new disagreement AND on one listed here that no longer reproduces, so a "
         "PR that fixes a disagreement must lower this ledger (`fact_crosscheck.py update`) in the same PR. "
         "Triage new ones with `assign`.")  # fmt: skip


def validate_ledger(doc: dict[str, Any]) -> list[str]:
    errs = []
    for cid, c in doc["causes"].items():
        if c.get("side") not in SIDES:
            errs.append(f"cause {cid}: side must be one of {SIDES}")
        if not isinstance(c.get("issue"), int):
            errs.append(f"cause {cid}: no issue number")
        if not c.get("summary"):
            errs.append(f"cause {cid}: no summary")
    used = set(doc["disagreements"].values())
    for did, cid in doc["disagreements"].items():
        if cid is None:
            errs.append(f"UNTRIAGED {did}")
        elif cid not in doc["causes"]:
            errs.append(f"unknown cause {cid!r} for {did}")
    for cid in doc["causes"]:
        if cid not in used:
            errs.append(f"cause {cid} is used by no disagreement (run update)")
    return errs


def gate(ledger: dict[str, Any], now: list[dict[str, str]]) -> tuple[list[str], list[str], list[str]]:
    """(new disagreements, ledger problems, entries that no longer reproduce)."""
    ids = {d["id"] for d in now}
    known = ledger["disagreements"]
    new = sorted(ids - set(known))
    gone = sorted(set(known) - ids)
    problems = [e for e in validate_ledger(ledger) if "is used by no disagreement" not in e or not gone]
    return new, problems, gone


def gate_failures(new: list[str], problems: list[str], gone: list[str]) -> list[str]:
    """Why `check` fails: the ledger is a two-way ratchet. A new disagreement fails (a regression on either
    side, or a new shape), and so does a ledgered one that no longer reproduces: a fix must lower the ledger
    in the same PR, so the ledger only shrinks and a later regression cannot hide behind a stale id."""
    out = []
    if new:
        out.append(f"{len(new)} new disagreement(s). Read the source: fix the side that is wrong, or `update` and "
                   "`assign` the disagreement a cause (side + issue).")  # fmt: skip
    if gone:
        out.append(f"{len(gone)} ledgered disagreement(s) no longer reproduce (listed as GONE). Run "
                   "`python tests/tools/fact_crosscheck.py update` (no --corpus: it drops them from every corpus) to lower "
                   "the ledger, and commit it in this PR.")  # fmt: skip
    if problems:
        out.append(f"{len(problems)} ledger problem(s) (listed as LEDGER).")
    return out


# ------------------------------------------------------------------------------
# Reporting
# ------------------------------------------------------------------------------
def _pct(n: int, d: int) -> str:
    return f"{100 * n / d:.1f}%" if d else "n/a"


def totals(result: dict[str, Any]) -> dict[str, Counter]:
    out: dict[str, Counter] = defaultdict(Counter)
    for res in result["corpora"].values():
        for ch, s in res["stats"].items():
            out[ch].update(s)
    return out


def markdown(
    result: dict[str, Any], ledger: dict[str, Any], new: list[str], problems: list[str], gone: list[str]
) -> str:
    tot = totals(result)
    lines = ["# Engine vs translator fact cross-check (#4273)", ""]
    lines.append(
        "| channel | files | both | engine only | translator only | agreement | engine vs key P / R | translator vs key P / R |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for ch in COMPARED:
        s = tot.get(ch, Counter())
        if not s.get("files"):
            continue
        union = s["both"] + s["engine_only"] + s["translator_only"]
        ek = (
            f"{_pct(s['engine_tp'], s['engine_reported'])} / {_pct(s['engine_tp'], s['true'])}"
            if s.get("key_files")
            else "n/a"
        )
        tk = (
            f"{_pct(s['translator_tp'], s['translator_reported'])} / {_pct(s['translator_tp'], s['true'])}"
            if s.get("key_files")
            else "n/a"
        )
        lines.append(f"| {ch} | {s['files']} | {s['both']} | {s['engine_only']} | {s['translator_only']} | "
                     f"{_pct(s['both'], union)} | {ek} | {tk} |")  # fmt: skip
    lines += ["", "| corpus | programs | det-port case programs | translator status | disagreements | seconds |",
              "|---|---:|---:|---|---:|---:|"]  # fmt: skip
    for name, res in result["corpora"].items():
        st = ", ".join(f"{k} {v}" for k, v in sorted(res["translator_status"].items()))
        lines.append(f"| {name} | {res['programs']} | {res['case_programs']} | {st} | {len(res['disagreements'])} | "
                     f"{result['seconds'][name]['total']} |")  # fmt: skip
    by_cause = Counter(ledger["disagreements"].get(d["id"]) for d in result["disagreements"])
    lines += [
        "",
        "## Known disagreements by cause",
        "",
        "| cause | side wrong | issue | count | summary |",
        "|---|---|---|---:|---|",
    ]
    for cid, n in sorted(by_cause.items(), key=lambda kv: (-kv[1], str(kv[0]))):
        if cid is None:
            continue
        c = ledger["causes"].get(cid, {})
        lines.append(f"| `{cid}` | {c.get('side', '?')} | #{c.get('issue', '?')} | {n} | {c.get('summary', '')} |")
    lines += ["", f"**{len(new)} new** disagreement(s), {len(problems)} ledger problem(s), "
              f"{len(gone)} ledgered disagreement(s) no longer reproduce."]  # fmt: skip
    for title, items in (
        ("New (not in the ledger)", new),
        ("Ledger problems", problems),
        ("No longer reproduce", gone),
    ):
        if items:
            lines += ["", f"### {title}", ""] + [f"- `{x}`" for x in items[:200]]
            if len(items) > 200:
                lines.append(f"- ... {len(items) - 200} more")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------------------
def _crucible_arg(args: argparse.Namespace) -> Optional[Path]:
    if args.no_crucible:
        return None
    import estate_crucible as EC

    path = EC.crucible_path(args.crucible)
    if not (path / "key" / "manifest.json").is_file():
        raise SystemExit(f"estate-crucible not found at {path} (--crucible, ${EC.PATH_ENV}, or --no-crucible)")
    return path


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("run", "check", "update"):
        s = sub.add_parser(name)
        s.add_argument("--crucible", type=Path)
        s.add_argument("--no-crucible", action="store_true")
        s.add_argument("--corpus", action="append", help="only these corpora (repeatable; `estate-crucible` too)")
        s.add_argument("--md", type=Path)
        s.add_argument("--json", type=Path)
        s.add_argument("--ledger", type=Path, default=LEDGER)
        s.add_argument("--cache", type=Path, default=Path(os.environ.get(
            "REFEREES_CACHE", Path.home() / ".cache" / "gitgalaxy-referees")))  # fmt: skip
    a = sub.add_parser("assign")
    a.add_argument("cause")
    a.add_argument("pattern", help="a regular expression searched in each disagreement id")
    a.add_argument("--untriaged-only", action="store_true")
    a.add_argument("--side", choices=SIDES)
    a.add_argument("--issue", type=int)
    a.add_argument("--summary")
    a.add_argument("--ledger", type=Path, default=LEDGER)
    args = ap.parse_args(argv)

    if args.cmd == "assign":
        led = load_ledger(args.ledger)
        if args.side or args.issue or args.summary:
            c = led["causes"].setdefault(args.cause, {})
            c.update(
                {
                    k: v
                    for k, v in (("side", args.side), ("issue", args.issue), ("summary", args.summary))
                    if v is not None
                }
            )
        elif args.cause not in led["causes"]:
            raise SystemExit(f"cause {args.cause} is new: give --side, --issue and --summary")
        rx = re.compile(args.pattern)
        n = 0
        for did, cid in led["disagreements"].items():
            if rx.search(did) and (cid is None or not args.untriaged_only):
                led["disagreements"][did] = args.cause
                n += 1
        save_ledger(led, args.ledger)
        print(f"{args.cause}: {n} disagreement(s)")
        return 0

    t0 = time.monotonic()
    result = run_all(_crucible_arg(args), args.cache, args.corpus)
    result["seconds"]["all"] = round(time.monotonic() - t0, 1)
    led = load_ledger(args.ledger)
    if args.corpus:  # a partial run judges only the corpora it ran
        keep = tuple(f"{c} :: " for c in args.corpus)
        led = {**led, "disagreements": {k: v for k, v in led["disagreements"].items() if k.startswith(keep)}}
    if args.cmd == "update":
        full = load_ledger(args.ledger)
        ids = {d["id"] for d in result["disagreements"]}
        # a full run judges every corpus it ran (so stale entries drop); `--corpus` only those named
        ran = tuple(f"{c} :: " for c in result["corpora"])
        kept = {k: v for k, v in full["disagreements"].items() if not k.startswith(ran)}
        kept.update({i: full["disagreements"].get(i) for i in ids})
        full["disagreements"] = kept
        used = set(kept.values())
        full["causes"] = {k: v for k, v in full["causes"].items() if k in used}
        save_ledger(full, args.ledger)
        untriaged = sum(1 for v in kept.values() if v is None)
        print(f"ledger: {len(kept)} disagreements, {untriaged} untriaged")
        return 0
    new, problems, gone = gate(led, result["disagreements"])
    md = markdown(result, led, new, problems, gone)
    if args.md:
        args.md.write_text(md, encoding="utf-8")
    if args.json:
        args.json.write_text(
            json.dumps({k: v for k, v in result.items()}, indent=1, default=str) + "\n", encoding="utf-8"
        )
    print(md if args.cmd == "run" else md.split("## Known disagreements")[0])
    print(f"total {result['seconds']['all']} s")
    if args.cmd == "check":
        for x in new[:50]:
            print(f"NEW {x}")
        for x in problems[:50]:
            print(f"LEDGER {x}")
        for x in gone[:50]:
            print(f"GONE {x}")
        fail = gate_failures(new, problems, gone)
        for line in fail:
            print(f"FAIL: {line}")
        if fail:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
