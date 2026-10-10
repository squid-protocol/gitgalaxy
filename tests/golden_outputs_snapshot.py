#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""
Golden-master coverage for the remaining scan outputs (#4109).

``golden_db_snapshot`` folds the scan DB into the golden master. This module
does the same for the other five artifacts a scan writes next to
``<repo>_galaxy_audit.json``: SARIF, the CycloneDX SBOM, the graph sqlite, the
GPU JSON and the LLM brief. ``attach`` adds one top-level section, ``SECTION``,
with one sub-key per output; ``golden_store`` writes each sub-key as its own
fixture file, so the toolchain (``deep_compare``, ``update_golden_master.py``,
``crucible_check.py``) needs no change. ``golden_diff.load_and_sanitize`` calls
``attach`` for every fresh scan that has the sibling files, never for a fixture
directory.

MASKS (everything else is compared). Each is a field that differs between two
scans of the same corpus, or that other automation refreshes independently of
engine output:

* SBOM ``serialNumber`` (a fresh UUID per scan) and ``metadata.timestamp``.
* Graph sqlite ``meta``: ``timestamp``, ``commit`` and ``branch`` -- the same
  facts ``golden_diff.sanitize`` already masks in the audit (clone-dependent).
* GPU ``meta.session``: ``timestamp``, ``duration_seconds``,
  ``target_directory`` and ``git_audit`` -- same reason (and the machine path).
* LLM brief section 0: the ``Git Remote`` row (clone-dependent) and the
  archetype-validation rows (``Archetype Brains``, ``Function archetypes``,
  ``File archetypes``, ``Composition (file)``, ``Composition (repo)``), which
  ``archetype-validation.yml`` refreshes on main independently of engine output
  (the audit's ``Archetype Validation`` block is masked for the same reason).
  The brain-provenance rows stay: they only change when a brain is retrained.

NORMALISATION (order and id noise, not content):

* SARIF results, SBOM components and GPU singularity rows are sorted -- the
  parallel scan emits them in completion order.
* The GPU file table is rebuilt per file path with its interned ids (language,
  author, import, archetype, ...) and file indices resolved to strings, then
  digested; the raw arrays are in scan order and their ids depend on it.
* Graph sqlite rows are keyed by file path, not by autoincrement id.
* Floats are rounded to 6 places (``golden_diff`` tolerance).

NOT SNAPSHOTTED: GPU ``pos_x/pos_y/pos_z``. They come from a corpus-wide layout
solve, so any change to any file moves every coordinate; the audit already
fails on the real cause, and a layout digest would only restate it as noise.

DIGESTS keep the fixtures compact: the graph sqlite and GPU file table store a
12-hex-digit SHA-256 prefix per file (and per GPU column) rather than the rows.
A drifted digest names the file or column; the DB snapshot or audit shows why.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

SECTION = "12. Scan Output Snapshots"
SARIF_KEY = "SARIF"
SBOM_KEY = "SBOM (CycloneDX)"
GRAPH_KEY = "Graph SQLite"
GPU_KEY = "GPU JSON"
LLM_KEY = "LLM Brief"

# (key, sibling suffix after "<x>_galaxy_", loader)
MASKED = "<masked>"
GRAPH_META_MASKED = ("timestamp", "commit", "branch")
GPU_SESSION_MASKED = ("timestamp", "duration_seconds", "target_directory", "git_audit")
LLM_MASKED_ROWS = (
    "Git Remote",
    "Archetype Brains",
    "Function archetypes",
    "File archetypes",
    "Composition (file)",
    "Composition (repo)",
)
GPU_COORDINATES = ("pos_x", "pos_y", "pos_z")
# galaxy column -> meta.schemas.lookups table its integer ids index into
GPU_LOOKUP_COLUMNS = {
    "lang_ids": "languages",
    "tel_aid": "authors",
    "tel_pid": "proofs",
    "tel_purp": "purposes",
    "c_ids": "constellations",
    "a_ids": "archetypes",
    "imports": "imports",
}
GPU_PATH_COLUMNS = ("edges", "outbound_edges")  # lists of file indices
GPU_FLAT_COLUMNS = ("risks_flat", "hits_flat")  # fixed stride per file
GPU_SINGULARITY_LOOKUPS = {"exts": "exts", "reasons": "reasons"}


def _digest(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _round(obj: Any) -> Any:
    if isinstance(obj, float):
        return round(obj, 6)
    if isinstance(obj, dict):
        return {k: _round(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round(v) for v in obj]
    return obj


def siblings(audit_path: str | Path) -> dict[str, Path]:
    """``<x>_galaxy_audit.json`` -> {section key: sibling output} for those that exist."""
    p = Path(audit_path)
    if p.is_dir() or not p.name.endswith("_audit.json"):
        return {}
    stem = p.name[: -len("_audit.json")]
    wanted = {
        SARIF_KEY: "_sarif.json",
        SBOM_KEY: "_sbom.json",
        GRAPH_KEY: "_graph.sqlite",
        GPU_KEY: "_gpu.json",
        LLM_KEY: "_llm.md",
    }
    found = {key: p.with_name(stem + suffix) for key, suffix in wanted.items()}
    return {k: v for k, v in found.items() if v.exists()}


def sarif(path: str | Path) -> dict[str, Any]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    runs = []
    for run in doc.get("runs", []):
        run = dict(run)
        run["results"] = sorted(json.dumps(r, sort_keys=True, separators=(",", ":")) for r in run.get("results", []))
        runs.append(run)
    return _round({**doc, "runs": runs})


def sbom(path: str | Path) -> dict[str, Any]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    doc.pop("serialNumber", None)
    (doc.get("metadata") or {}).pop("timestamp", None)
    doc["components"] = sorted(json.dumps(c, sort_keys=True, separators=(",", ":")) for c in doc.get("components", []))
    return _round(doc)


def graph(path: str | Path) -> dict[str, Any]:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        meta = {k: (MASKED if k in GRAPH_META_MASKED else v) for k, v in conn.execute("SELECT key, value FROM meta")}
        out: dict[str, Any] = {"Meta": meta, "Row Counts": {}}
        tables = {
            "Artifacts": ("SELECT * FROM artifacts", "path"),
            "Directory Groups": ("SELECT * FROM directory_groups", "name"),
        }
        for label, (sql, key) in tables.items():
            cur = conn.execute(sql)
            cols = [d[0] for d in cur.description]
            rows = {}
            for row in cur:
                rec = dict(zip(cols, row, strict=False))  # reason: length may differ
                rec.pop("id", None)
                rows[rec[key]] = _digest(_round(rec))
            out[label] = rows
            out["Row Counts"][label] = len(rows)
        child_tables = {
            "Functions": "SELECT a.path, t.name, t.type_id, t.loc, t.impact, t.docstring, t.calls_out_to "
            "FROM functions t JOIN artifacts a ON t.artifact_id = a.id",
            "DNA Hits": "SELECT a.path, t.signal_type, t.hit_count FROM dna_hits t JOIN artifacts a ON t.artifact_id = a.id",
            "Outbound Dependencies": "SELECT a.path, t.imported_path FROM outbound_dependencies t "
            "JOIN artifacts a ON t.artifact_id = a.id",
            "Inbound Dependencies": "SELECT a.path, t.imported_by_path FROM inbound_dependencies t "
            "JOIN artifacts a ON t.artifact_id = a.id",
        }
        for label, sql in child_tables.items():  # noqa: S608 -- fixed SQL
            per_file: dict[str, list] = {}
            n = 0
            for path_, *rest in conn.execute(sql):
                per_file.setdefault(path_, []).append(json.dumps(_round(rest), default=str))
                n += 1
            out[label] = {p: _digest(sorted(rows)) for p, rows in per_file.items()}
            out["Row Counts"][label] = n
        return out
    finally:
        conn.close()


def gpu(path: str | Path) -> dict[str, Any]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    meta = json.loads(json.dumps(doc["meta"]))
    for k in GPU_SESSION_MASKED:
        if k in (meta.get("session") or {}):
            meta["session"][k] = MASKED
    lookups = doc["meta"]["schemas"]["lookups"]
    gal = doc["galaxy"]
    paths = gal["paths"]
    n = len(paths)

    def resolve(col: str, i: int) -> Any:
        v = gal[col][i]
        if col in GPU_LOOKUP_COLUMNS:
            table = lookups[GPU_LOOKUP_COLUMNS[col]]
            return [table[x] for x in v] if isinstance(v, list) else table[v]
        if col in GPU_PATH_COLUMNS:
            return sorted(paths[x] for x in v)
        if col in GPU_FLAT_COLUMNS:
            stride = len(gal[col]) // n if n else 0
            return gal[col][i * stride : (i + 1) * stride]
        if col == "satellite_data_flat":
            off = gal["satellite_offsets"]
            total = off[-1] if off else 0
            stride = len(gal[col]) // total if total else 0
            return gal[col][off[i] * stride : off[i + 1] * stride]
        return v

    cols = [c for c in gal if c not in GPU_COORDINATES and c not in ("satellite_offsets", "paths")]
    # Row-indexed columns: everything but the flat ones is length n.
    files: dict[str, str] = {}
    col_rows: dict[str, list] = {c: [] for c in cols}
    for i in range(n):
        row = {c: resolve(c, i) for c in cols}
        files[paths[i]] = _digest(_round(row))
        for c in cols:
            col_rows[c].append((paths[i], row[c]))
    columns = {c: _digest(_round(sorted(rows, key=lambda r: r[0]))) for c, rows in col_rows.items()}
    sing = doc["singularity"]
    sing_rows = sorted(
        json.dumps(
            [
                sing["paths"][i],
                lookups[GPU_SINGULARITY_LOOKUPS["exts"]][sing["exts"][i]],
                lookups[GPU_SINGULARITY_LOOKUPS["reasons"]][sing["reasons"][i]],
                sing["sizes"][i],
                sing["confidences"][i],
            ]
        )
        for i in range(len(sing["paths"]))
    )
    return {
        "Meta": _round(meta),
        "Global Summary": {k: _digest(_round(v)) for k, v in doc["global_summary"].items()},
        "Story": doc.get("story"),
        "Galaxy Row Count": n,
        "Galaxy Column Digests": columns,
        "Galaxy Files": files,
        "Singularity": sing_rows,
    }


def llm(path: str | Path) -> list[str]:
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.startswith("| **"):
            name = line[4:].partition("**")[0]
            if name in LLM_MASKED_ROWS:
                line = f"| **{name}** | {MASKED} |"
        out.append(line)
    return out


_LOADERS = {SARIF_KEY: sarif, SBOM_KEY: sbom, GRAPH_KEY: graph, GPU_KEY: gpu, LLM_KEY: llm}


def snapshot(audit_path: str | Path) -> dict[str, Any]:
    return {key: _LOADERS[key](p) for key, p in siblings(audit_path).items()}


def attach(audit: dict[str, Any], audit_path: str | Path) -> dict[str, Any]:
    """Add ``SECTION`` (one sub-key per sibling output present). In place."""
    snap = snapshot(audit_path)
    if snap:
        audit[SECTION] = snap
    return audit
