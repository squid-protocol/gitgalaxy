"""
#3120: the differential between the refraction pipeline's own COBOL parsers
(gitgalaxy/tools/cobol_to_cobol/) and the engine's master DB (read through
gitgalaxy/tools/cobol_to_cobol/galaxy_ir.py).

Neither side is the oracle. A delta is a finding to EXPLAIN (old-parser defect,
engine defect, semantic difference, or stated absence), never a verdict that the
DB value is better. docs/refraction_engine_differential.md records the explained
run over the two cobol_corpus repos.

    # the raw #3120 report over one repo
    python tests/tools/refraction_differential.py <repo> --db <repo>_galaxy_master.db \
        [--json out.json] [--md out.md]

Omit --db to scan <repo> first (galaxyscope --db-only into a temp dir).

#3211: every delta now carries a `cause` code, so "explained" is a run, not an
afternoon of reading source. classify() attributes each delta by mechanism
(scope_terminator, area_b_header, section_header, entry_point,
usage_status_not_reachability, program_inlined_as_copybook,
ambiguous_copy_target, exec_sql_include, sequence_number_field,
system_copybook, bms_symbolic_map) or as stated_absence
by construction; where the corpus has a validated answer key (#3210), an
INDEPENDENT-field delta (program_id, copybook) is also adjudicated to a verdict
from the key directly. The gate counts what neither explains -- `unexplained` --
and fails when a run adds any over a committed per-corpus baseline.

    python tests/tools/refraction_differential.py --ci               # gate the committed excerpts
    python tests/tools/refraction_differential.py --update-baseline  # bless the excerpt baseline
    python tests/tools/refraction_differential.py --corpus NAME ...   # gate the full pinned corpora (local)
"""

import argparse
import contextlib
import json
import os
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Optional

# Import the engine from this checkout whether run as a script or imported by a
# test, without an editable install (as mainframe_corpus.py / refraction_snapshot.py do).
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gitgalaxy.tools.cobol_to_cobol.cobol_dag_architect import extract_lineage  # noqa: E402
from gitgalaxy.tools.cobol_to_cobol.cobol_graveyard_finder import (  # noqa: E402
    _NOT_A_PARAGRAPH,
    x_ray_dead_code,
)
from gitgalaxy.tools.cobol_to_cobol.cobol_jcl_forge import analyze_cobol_intent  # noqa: E402
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import GalaxyIR, load_galaxy_ir, scan_to_db  # noqa: E402

# The sibling readers/scorer. It has no top-level engine imports, so importing it
# here is cheap and one-directional -- it no longer imports this module (#3211).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cobol_answer_key as ak  # noqa: E402
from cobol_answer_key import old_copybooks, old_paragraphs  # noqa: E402

MAINFRAME = REPO_ROOT / "tests" / "cobol_mainframe"
EXCERPTS = MAINFRAME / "refraction_excerpts"
BASELINE = MAINFRAME / "refraction_differential_baseline.json"

# Cause codes (#3211). The first ten are mechanisms read off the source; the last
# is the DB carrying no equivalent at all (galaxy_ir.py SCOPE). A delta that fits
# none of them is `unexplained` unless the answer key adjudicates it (see below).
CAUSES = (
    "scope_terminator",
    "program_inlined_as_copybook",
    "section_header",
    "area_b_header",
    "entry_point",
    "usage_status_not_reachability",
    "ambiguous_copy_target",
    "exec_sql_include",
    "sequence_number_field",
    "system_copybook",
    "bms_symbolic_map",
    "stated_absence",
)
UNEXPLAINED = "unexplained"
# Fields where the answer key is an INDEPENDENT oracle -- its drafter reads them
# with its own fixed-format pass, not the forge's control-flow model. For
# units/dead the key's `draft` DOES share that model (#3219), so an agreement
# there is not evidence about the forge and never clears `unexplained` on its own.
INDEPENDENT_FIELDS = {"program_id", "copybook", "dataset_dd", "dataset_input", "dataset_output", "dynamic_call"}


def compare(repo: Path, ir: GalaxyIR) -> list[dict[str, Any]]:
    rows = []
    for ef in ir.programs("cobol"):
        path = repo / ef.file_path
        intent = analyze_cobol_intent(path)
        graveyard = x_ray_dead_code(path, copybook_root=repo) or {}
        dead_old = set(graveyard.get("dead_paras", set()))
        lineage = extract_lineage(path, dead_paras=dead_old) or {}
        paras_old = old_paragraphs(path, repo)
        paras_new = {u.name.upper() for u in ef.units}
        copy_named, copy_old = old_copybooks(path, repo)
        copy_new = {Path(p).stem.upper() for p in ef.copy_deps}
        # #3200/#3201: the DB now carries the call graph and dataset lineage, so
        # these are COMPARED, not stated absences. A COBOL dataset row is a
        # SELECT/ASSIGN (is_binding is False; the JCL DD bindings are the engine's
        # other half). Input/output split mirrors cobol_answer_key.score().
        eng_ds = [d for d in ef.datasets if not d.is_binding]
        eng_dd = {d.dd_name for d in eng_ds}
        eng_in = {d.dd_name for d in eng_ds if set(d.modes) & {"INPUT", "I-O", "EXTEND"}}
        eng_out = {d.dd_name for d in eng_ds if set(d.modes) & {"OUTPUT", "I-O", "EXTEND"}}
        # Scope to COBOL CALL, identifier form -- what the forge's DAG architect
        # reports as unresolved_calls and what the key counts. The engine's call
        # graph also carries CICS LINK/XCTL and literal targets, but the forge has
        # no comparable set for those, so diffing them would be apples-to-oranges.
        eng_dyn = {c.operand for c in ef.calls if c.verb == "CALL" and c.form == "identifier" and c.operand}
        rows.append(
            {
                "file": ef.file_path,
                "program_id": {"old": intent["program_id"], "db": ef.program_ids},
                "paragraphs": {
                    "old_count": len(paras_old),
                    "db_count": len(paras_new),
                    "old_only": sorted(paras_old - paras_new),
                    "db_only": sorted(paras_new - paras_old),
                },
                "dead": {
                    "old": sorted(dead_old),
                    "db_usage_status_1": sorted(u.name for u in ef.units if u.usage_status == 1),
                },
                "copybooks": {
                    "named": sorted(copy_named),
                    "old_resolved": sorted(copy_old),
                    "db_edges": sorted(copy_new),
                },
                "subsystems": {
                    "old_cics": intent["cics_calls"],
                    "old_sql": intent["sql_calls"],
                    "db_signals": ef.signals,
                },
                # Dataset lineage (#3201) and the dynamic call graph (#3200): both
                # sides carry these now, so they are compared like the others.
                "datasets": {
                    "dd_old": sorted(f["dd_name"] for f in intent["files_requested"]),
                    "dd_db": sorted(eng_dd),
                    "inputs_old": sorted(lineage.get("inputs", set())),
                    "inputs_db": sorted(eng_in),
                    "outputs_old": sorted(lineage.get("outputs", set())),
                    "outputs_db": sorted(eng_out),
                },
                "calls": {
                    "dynamic_old": sorted(lineage.get("unresolved_calls", [])),
                    "dynamic_db": sorted(eng_dyn),
                },
                # Still a stated absence -- data items / FD record layouts are the
                # one structural datum the DB does not carry (galaxy_ir.py SCOPE, #3246).
                "forge_only": {
                    "orphaned_vars": len(graveyard.get("orphaned_vars", set())),
                },
            }
        )
    return rows


def summarize(ir: GalaxyIR, rows: list[dict[str, Any]]) -> dict[str, Any]:
    def count(pred) -> int:
        return sum(1 for r in rows if pred(r))

    return {
        "repo": ir.repo_name,
        "commit": ir.commit_hash,
        "inventory": ir.inventory(),
        "cobol_programs": len(rows),
        "program_id_mismatch": count(lambda r: r["program_id"]["old"] not in r["program_id"]["db"]),
        "paragraph_set_differs": count(lambda r: r["paragraphs"]["old_only"] or r["paragraphs"]["db_only"]),
        "paragraphs_old_only": sum(len(r["paragraphs"]["old_only"]) for r in rows),
        "paragraphs_db_only": sum(len(r["paragraphs"]["db_only"]) for r in rows),
        "dead_old_total": sum(len(r["dead"]["old"]) for r in rows),
        "dead_db_total": sum(len(r["dead"]["db_usage_status_1"]) for r in rows),
        "dead_agree": sum(len(set(r["dead"]["old"]) & set(r["dead"]["db_usage_status_1"])) for r in rows),
        "copy_named": sum(len(r["copybooks"]["named"]) for r in rows),
        "copy_old_resolved": sum(len(r["copybooks"]["old_resolved"]) for r in rows),
        "copy_db_edges": sum(len(r["copybooks"]["db_edges"]) for r in rows),
        "cics_programs_old": count(lambda r: r["subsystems"]["old_cics"] > 0),
        "sql_programs_old": count(lambda r: r["subsystems"]["old_sql"] > 0),
        "dd_agree": sum(len(set(r["datasets"]["dd_old"]) & set(r["datasets"]["dd_db"])) for r in rows),
        "dd_old_only": sum(len(set(r["datasets"]["dd_old"]) - set(r["datasets"]["dd_db"])) for r in rows),
        "dd_db_only": sum(len(set(r["datasets"]["dd_db"]) - set(r["datasets"]["dd_old"])) for r in rows),
        "dynamic_calls_old": sum(len(r["calls"]["dynamic_old"]) for r in rows),
        "dynamic_calls_db": sum(len(r["calls"]["dynamic_db"]) for r in rows),
    }


def to_markdown(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    out = [f"## {summary['repo']} @ {summary['commit'][:8]}", "", "| metric | value |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in summary.items() if k not in ("repo", "commit")]
    out += [
        "",
        "| file | PROGRAM-ID old / db | paras old / db (old-only, db-only) | dead old / db | COPY named / old / db | CICS/SQL old |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        p, d, c, s = r["paragraphs"], r["dead"], r["copybooks"], r["subsystems"]
        out.append(
            f"| {r['file']} | {r['program_id']['old']} / {','.join(r['program_id']['db'])} "
            f"| {p['old_count']} / {p['db_count']} ({len(p['old_only'])}, {len(p['db_only'])}) "
            f"| {len(d['old'])} / {len(d['db_usage_status_1'])} "
            f"| {len(c['named'])} / {len(c['old_resolved'])} / {len(c['db_edges'])} "
            f"| {s['old_cics']}/{s['old_sql']} |"
        )
    return "\n".join(out) + "\n"


# ==============================================================================
# Classification (#3211)
# ==============================================================================
Delta = dict[str, Any]  # {program, field, side: "old"|"db", value, [unresolved]}

# A `COPY name` / `EXEC SQL INCLUDE name` whose line carries a cols-1..6 sequence
# field. Read off the raw source (the offsets the sequence area lives at), not the
# blanked twin. #3203 defect 4: `R2     COPY SAM2PARM.`.
_SEQ_COPY = re.compile(r"\b(?:COPY|EXEC\s+SQL\s+INCLUDE)\s+['\"]?([A-Z0-9@#$_-]+)", re.IGNORECASE)


def flatten(rows: list[dict[str, Any]]) -> list[Delta]:
    """One record per set-difference element in `compare()`'s rows."""
    deltas: list[Delta] = []
    for r in rows:
        prog = r["file"]
        pid = r["program_id"]
        # Only the genuine mismatch. A db file legitimately carrying several
        # PROGRAM-IDs is not a per-id finding.
        if pid["old"] and pid["old"] not in pid["db"]:
            deltas.append({"program": prog, "field": "program_id", "side": "old", "value": pid["old"]})
        para = r["paragraphs"]
        deltas += [{"program": prog, "field": "paragraph", "side": "old", "value": v} for v in para["old_only"]]
        deltas += [{"program": prog, "field": "paragraph", "side": "db", "value": v} for v in para["db_only"]]
        dead_old = {x.upper() for x in r["dead"]["old"]}
        dead_db = {x.upper() for x in r["dead"]["db_usage_status_1"]}
        deltas += [{"program": prog, "field": "dead", "side": "old", "value": v} for v in sorted(dead_old - dead_db)]
        deltas += [{"program": prog, "field": "dead", "side": "db", "value": v} for v in sorted(dead_db - dead_old)]
        # compare() gives db_edges as stems but old_resolved keyed by name; both
        # are already upper here, normalise to stems so an identical resolution is
        # not read as a delta.
        old_res = {x.upper() for x in r["copybooks"]["old_resolved"]}
        db_edges = {x.upper() for x in r["copybooks"]["db_edges"]}
        named = {x.upper() for x in r["copybooks"]["named"]}
        deltas += [
            {"program": prog, "field": "copybook", "side": "old", "value": v} for v in sorted(old_res - db_edges)
        ]
        deltas += [{"program": prog, "field": "copybook", "side": "db", "value": v} for v in sorted(db_edges - old_res)]
        deltas += [
            {"program": prog, "field": "copybook", "side": "old", "value": v, "unresolved": True}
            for v in sorted(named - old_res - db_edges)
        ]
        # Dataset lineage (#3201) and dynamic calls (#3200): compared, both sides.
        ds = r["datasets"]
        for kind, fld in (("dd", "dataset_dd"), ("inputs", "dataset_input"), ("outputs", "dataset_output")):
            old = {x.upper() for x in ds[f"{kind}_old"]}
            db = {x.upper() for x in ds[f"{kind}_db"]}
            deltas += [{"program": prog, "field": fld, "side": "old", "value": v} for v in sorted(old - db)]
            deltas += [{"program": prog, "field": fld, "side": "db", "value": v} for v in sorted(db - old)]
        c_old = {x.upper() for x in r["calls"]["dynamic_old"]}
        c_db = {x.upper() for x in r["calls"]["dynamic_db"]}
        deltas += [{"program": prog, "field": "dynamic_call", "side": "old", "value": v} for v in sorted(c_old - c_db)]
        deltas += [{"program": prog, "field": "dynamic_call", "side": "db", "value": v} for v in sorted(c_db - c_old)]
        # D4: presence agrees, but the DB's hit columns cannot give a clean flag.
        ss = r["subsystems"]
        deltas += [
            {"program": prog, "field": "subsystem", "side": "old", "value": v}
            for v, on in (("cics", ss["old_cics"] > 0), ("sql", ss["old_sql"] > 0))
            if on
        ]
        # Still a stated absence: data items / FD record layouts (galaxy_ir.py SCOPE, #3246).
        fo = r["forge_only"]
        if fo["orphaned_vars"]:
            deltas.append(
                {"program": prog, "field": "forge_only:orphaned_vars", "side": "old", "value": str(fo["orphaned_vars"])}
            )
    return deltas


def _seq_field_copies(path: Path) -> set[str]:
    """Names of members COPY'd on a line that carries a cols-1..6 sequence field."""
    out: set[str] = set()
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if len(raw) > 6 and raw[6] in "*/Dd":
            continue
        if not raw[:6].strip():
            continue
        m = _SEQ_COPY.search(raw[7:72].upper())
        if m:
            out.add(m.group(1).upper())
    return out


def _build_ctx(repo: Path, rel: str, ak, files: list[Path], stem_counts: Counter) -> dict[str, Any]:
    """Per-program source facts a classifier reads, computed once and cached.

    Uses the answer key's own fixed-format reader so a cause is decided by the
    same model the key is, not a fourth parser."""
    path = repo / rel
    src = ak.Source(path)
    units = ak._units(src)
    unit_kind = {u["name"]: u["kind"] for u in units if u["name"]}
    reached = set(ak.reachability(units))
    copies: dict[str, dict[str, Any]] = {}
    for rx, via in ((ak._COPY, "COPY"), (ak._SQL_INCLUDE, "SQL INCLUDE")):
        for m in rx.finditer(src.text):
            name = m.group(1).upper()
            if name in copies:
                continue
            library = m.group(2) if via == "COPY" else None
            info = ak.resolve_copybook(name, library, path, repo, files)
            copies[name] = {"via": via, "why": info["why"] or "", "resolves_to": info["resolves_to"]}
    return {
        "unit_kind": unit_kind,
        "own_units": set(unit_kind),
        "reached": reached,
        "copies": copies,
        "seq_copies": _seq_field_copies(path),
        "stem_counts": stem_counts,
    }


def _classify_copybook(d: Delta, ctx: dict[str, Any]) -> str:
    v, side = d["value"], d["side"]
    info = ctx["copies"].get(v, {})
    why, via = info.get("why", ""), info.get("via")
    if via == "SQL INCLUDE":
        return "exec_sql_include"
    if why.startswith("AMBIGUOUS:"):
        return "ambiguous_copy_target"
    if "symbolic map generated from" in why:
        return "bms_symbolic_map"
    if why.endswith("supplied"):  # CICS-/Language Environment-/DB2 precompiler-supplied
        return "system_copybook"
    if v in ctx["seq_copies"]:
        return "sequence_number_field"
    # The forge resolved it (whole-repo, nearest, same language); the engine drops
    # a target whose stem is shared across extensions (#3199).
    if side == "old" and ctx["stem_counts"].get(v, 0) > 1:
        return "ambiguous_copy_target"
    return UNEXPLAINED


def _classify_cause(d: Delta, ctx: dict[str, Any]) -> str:
    field, side, v = d["field"], d["side"], d["value"]
    if field.startswith("forge_only:") or field == "subsystem":
        return "stated_absence"  # by construction
    if field == "program_id":
        return UNEXPLAINED  # left to the key verdict (independent field)
    if field in ("paragraph", "dead"):
        if side == "old":
            if _NOT_A_PARAGRAPH.fullmatch(v):
                return "scope_terminator"
            if v not in ctx["own_units"]:  # came from an inlined member, not this program
                return "program_inlined_as_copybook"
            if field == "dead":
                # The forge's reachability calls this unit dead; the engine's
                # usage_status is unreferenced-BY-NAME, a deliberately different
                # signal (#3198, by design -- see unreferenced_by_name_contract.md).
                # The two disagreeing IS the semantic difference, not a bug; whether
                # the forge is right is the answer key's job, not the differential's.
                return "usage_status_not_reachability"
            return UNEXPLAINED
        # db-only: the engine saw a name the forge did not
        if v not in ctx["own_units"]:
            return "area_b_header"  # a lone NAME. the engine read in Area B
        if field == "dead":
            return "entry_point"  # a real unit reached by fall-through/entry, flagged by name-only usage_status
        return "section_header" if ctx["unit_kind"].get(v) == "section" else UNEXPLAINED
    if field == "copybook":
        return _classify_copybook(d, ctx)
    return UNEXPLAINED


def _key_verdict(d: Delta, key: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """The answer key's verdict on a delta, or None when it cannot adjudicate."""
    if not key:
        return None
    prog = key.get("programs", {}).get(d["program"])
    if not prog or prog.get("verification", {}).get("status") != "validated":
        return None
    field, side, v = d["field"], d["side"], d["value"]
    if field == "program_id":
        truth = {prog["program_id"]}
    elif field == "paragraph":
        truth = {u["name"] for u in prog["units"]}
    elif field == "dead":
        truth = set(prog["dead"])
    elif field == "copybook":
        truth = {Path(c["resolves_to"]).stem.upper() for c in prog["copybooks"] if c.get("resolves_to")}
    elif field in ("dataset_dd", "dataset_input", "dataset_output"):
        want = {"dataset_input": {"INPUT", "I-O", "EXTEND"}, "dataset_output": {"OUTPUT", "I-O", "EXTEND"}}.get(field)
        truth = {f["dd"] for f in prog["files"] if want is None or set(f["modes"]) & want}
    elif field == "dynamic_call":
        truth = {c["operand"] for c in prog["calls"] if c["verb"] == "CALL" and c["form"] == "identifier"}
    else:
        return None
    present = v in truth
    # db side claims v; old side claims v. The wrong side owns the defect.
    verdict = (
        ("old-parser defect" if present else "engine defect")
        if side == "db"
        else ("engine defect" if present else "old-parser defect")
    )
    confidence = "independent" if field in INDEPENDENT_FIELDS else "shared_model"
    return {"verdict": verdict, "confidence": confidence, "decided": True}


def classify(repo: Path, rows: list[dict[str, Any]], key: Optional[dict[str, Any]]) -> list[Delta]:
    """Attaches a `cause` (and, where a validated key adjudicates, a `verdict`) to
    every delta, reading source with the answer key's own fixed-format model."""
    files = [p for p in repo.rglob("*") if p.is_file() and ".git" not in p.parts]
    stem_counts = Counter(p.stem.upper() for p in files)
    ctx_cache: dict[str, dict[str, Any]] = {}
    out: list[Delta] = []
    for d in flatten(rows):
        ctx = ctx_cache.get(d["program"])
        if ctx is None:
            ctx = ctx_cache[d["program"]] = _build_ctx(repo, d["program"], ak, files, stem_counts)
        out.append({**d, "cause": _classify_cause(d, ctx), "verdict": _key_verdict(d, key)})
    return out


def _resolved_by_key(d: Delta) -> bool:
    v = d.get("verdict")
    return bool(v and v.get("decided") and v.get("confidence") == "independent")


def effective_cause(d: Delta) -> str:
    """The cause the gate counts under: a mechanism, an INDEPENDENT key verdict, or
    UNEXPLAINED. A shared-model key agreement never clears UNEXPLAINED (#3219)."""
    if d["cause"] == UNEXPLAINED and _resolved_by_key(d):
        return "key:" + d["verdict"]["verdict"]
    return d["cause"]


def summarize_causes(classified: list[Delta]) -> dict[str, Any]:
    by_cause: dict[str, int] = {}
    for d in classified:
        eff = effective_cause(d)
        by_cause[eff] = by_cause.get(eff, 0) + 1
    return {"unexplained": by_cause.get(UNEXPLAINED, 0), "by_cause": dict(sorted(by_cause.items()))}


# ==============================================================================
# Baseline gate (#3211)
# ==============================================================================
_ABOUT = (
    "Per-corpus unexplained-delta baseline for the refraction differential (#3211). "
    "`--ci` gates the committed `excerpts` (what CI runs); `--corpus NAME` gates the `full` pinned "
    "corpora (local, needs a fetch+scan). A run fails when it ADDS unexplained deltas over these "
    "counts; --update-baseline blesses the matching scope (existing notes are carried forward). "
    "Every entry with unexplained > 0, or no answer key, needs a note saying why it stands, with "
    "the issue that owns the fix. `by_cause` is recorded for visibility and does not gate."
)


def _load_baseline() -> dict[str, Any]:
    if BASELINE.is_file():
        return json.loads(BASELINE.read_text(encoding="utf-8"))
    return {"about": _ABOUT, "excerpts": {}, "full": {}}


def _write_baseline(results: dict[str, dict[str, Any]], previous: dict[str, Any], scope: str) -> None:
    """Merges `results` into `scope` (excerpts | full), preserving the other scope
    and carrying each corpus's existing note forward."""
    doc = {
        "about": previous.get("about") or _ABOUT,
        "excerpts": dict(previous.get("excerpts", {})),
        "full": dict(previous.get("full", {})),
    }
    section = doc[scope]
    for name, s in results.items():
        section[name] = {
            "unexplained": s["unexplained"],
            "by_cause": s["by_cause"],
            "note": section.get(name, {}).get("note"),
        }
    BASELINE.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _manifest():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import mainframe_corpus as mc  # lazy: only the gate needs the manifest

    keys: dict[str, Optional[dict[str, Any]]] = {}
    for c in mc.load_manifest():
        key = None
        if c.get("answer_key") and (REPO_ROOT / c["answer_key"]).is_file():
            key = json.loads((REPO_ROOT / c["answer_key"]).read_text(encoding="utf-8"))
        keys[c["name"]] = key
    return mc, keys


def _targets(names: Optional[list[str]]) -> list[tuple[str, Path, Optional[dict[str, Any]], Optional[Path]]]:
    """(name, source, key, db). db is None for excerpts (scanned into a tempdir);
    for the full corpora it is the cache from mainframe_corpus (scanned per engine)."""
    mc, keys = _manifest()
    if names:
        return [(c["name"], mc.require_clone(c), keys[c["name"]], mc.scan(c)) for c in mc.select(names)]
    return [(d.name, d, keys.get(d.name), None) for d in sorted(p for p in EXCERPTS.iterdir() if p.is_dir())]


@contextlib.contextmanager
def _scan_env():
    """Set the scan environment for the in-process `scan_to_db`, then restore it.

    An excerpt lives inside this repository, so the scan must not read the parent's
    git history, and it should not need a license. These are set process-wide, so
    they MUST be restored: `GITGALAXY_DISABLE_GIT_HISTORY` would otherwise disable
    git for every later test in a pytest session (it broke test_chronometer)."""
    keys = ("GITGALAXY_LICENSE_KEY", "GITGALAXY_DISABLE_GIT_HISTORY")
    saved = {k: os.environ.get(k) for k in keys}
    os.environ.setdefault("GITGALAXY_LICENSE_KEY", "COMMUNITY_FREE_TIER")
    os.environ["GITGALAXY_DISABLE_GIT_HISTORY"] = "1"
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def run_target(source: Path, key: Optional[dict[str, Any]], db: Optional[Path]) -> tuple[dict[str, Any], list[Delta]]:
    """Scan (or load) one target and classify its deltas. The full corpora arrive
    with a `db` already scanned by mainframe_corpus (its own subprocess env); only
    the in-process excerpt scan needs, and scopes, the scan environment."""
    if db is not None:
        ir = load_galaxy_ir(db)
        classified = classify(source, compare(source, ir), key)
    else:
        with _scan_env(), tempfile.TemporaryDirectory() as tmp:
            ir = load_galaxy_ir(scan_to_db(source, Path(tmp)))
            classified = classify(source, compare(source, ir), key)
    return summarize_causes(classified), classified


def _gate(args: argparse.Namespace) -> int:
    scope = "full" if args.corpus else "excerpts"
    baseline = _load_baseline()
    base_c = baseline.get(scope, {})
    results: dict[str, dict[str, Any]] = {}
    failed = False
    for name, source, key, db in _targets(args.corpus):
        summary, classified = run_target(source, key, db)
        results[name] = summary
        base = base_c.get(name, {}).get("unexplained", 0)
        run = summary["unexplained"]
        flag = "OK" if run == base else ("REGRESSED" if run > base else "improved (lower the baseline)")
        print(f"{name} [{scope}]: unexplained {run} (baseline {base}) — {flag}")
        print(f"  by_cause: {summary['by_cause']}")
        if run > base:
            failed = True
            for d in classified:
                if effective_cause(d) == UNEXPLAINED:
                    print(f"    UNEXPLAINED {d['program']}  {d['field']}/{d['side']}  {d['value']}")
    if args.update_baseline:
        _write_baseline(results, baseline, scope)
        print(f"blessed {scope} in {BASELINE.relative_to(REPO_ROOT)} ({len(results)} corpora)")
        return 0
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo", nargs="?", type=Path, help="one repo to report on (omit for the gate modes)")
    ap.add_argument("--db", type=Path, help="existing <repo>_galaxy_master.db (scans the repo if omitted)")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--md", type=Path)
    ap.add_argument("--ci", action="store_true", help="gate the committed excerpts against the baseline")
    ap.add_argument("--update-baseline", action="store_true", help="rewrite the baseline from a fresh run")
    ap.add_argument("--corpus", nargs="+", metavar="NAME", help="gate the full pinned corpora instead of excerpts")
    args = ap.parse_args()

    if args.ci or args.update_baseline or args.corpus:
        return _gate(args)
    if args.repo is None:
        ap.error("a repo is required unless --ci / --update-baseline / --corpus is given")

    repo = args.repo.resolve()
    if args.db:
        ir = load_galaxy_ir(args.db)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            ir = load_galaxy_ir(scan_to_db(repo, Path(tmp)))

    rows = compare(repo, ir)
    summary = summarize(ir, rows)
    classified = classify(repo, rows, None)
    if args.json:
        payload = {"summary": summary, "causes": summarize_causes(classified), "programs": rows, "deltas": classified}
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md = to_markdown(summary, rows)
    if args.md:
        args.md.write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
