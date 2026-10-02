#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""
Golden-master coverage for the scan DB (#4109).

The golden master used to snapshot only ``<repo>_galaxy_audit.json``. Most of
what the engine computes per FUNCTION exists only in ``<repo>_galaxy_master.db``
-- the function archetype, its z-score, the call list, fan-in/out, PageRank,
usage status -- along with the resolved import graph (``edge_data``). None of
it was regression-tested on the corpus.

``attach`` folds a canonical, sanitized slice of the DB into the audit dict as
a new per-file section, ``SECTION``. Because ``golden_store`` already splits
every per-file section into one part file per sub-key, the slice inherits the
whole golden toolchain unchanged: ``golden_diff.deep_compare`` diffs it,
``update_golden_master.py`` blesses it, and each column lands in its own
fixture file. ``golden_diff.load_and_sanitize`` calls ``attach`` whenever it
loads a fresh audit JSON that has its sibling ``*_master.db``, so every reader
of a fresh scan sees the same shape as the committed fixture.

Rows are keyed ``"<func_name>@<start_line>"`` (``#<n>`` appended on the rare
exact collision); ids, timestamps and mode-dependent columns (token mass) are
left out so the slice is identical in full-precision and zero-dependency mode.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

SECTION = "11. Scan DB Snapshot"
PARSED = "6. Parsed Files (Scanned Artifacts)"

# Sub-key -> function_data column. Each becomes one fixture file.
FUNCTION_COLUMNS: dict[str, str] = {
    "Function Archetype": "func_archetype",
    "Function Z-Score": "func_z_score",
    "Calls Out To": "calls_out_to",
    "Fan In": "func_fan_in",
    "Fan Out": "func_fan_out",
    "PageRank": "func_pagerank",
    "Usage Status": "usage_status",
}
EDGES_KEY = "Import Edges"


def db_for_audit(audit_path: str | Path) -> Path | None:
    """``<x>_galaxy_audit.json`` -> sibling ``<x>_galaxy_master.db`` if present."""
    p = Path(audit_path)
    if p.is_dir() or not p.name.endswith("_audit.json"):
        return None
    db = p.with_name(p.name[: -len("_audit.json")] + "_master.db")
    return db if db.exists() else None


def _value(column: str, raw: Any) -> Any:
    if raw is None:
        return None
    if column == "calls_out_to":
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return raw
    if isinstance(raw, float):
        return round(raw, 6)
    return raw


def snapshot(db_path: str | Path) -> dict[str, dict[str, Any]]:
    """{file path: {sub-key: value}} for every file with functions or edges."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cols = ", ".join(f"f.{c}" for c in FUNCTION_COLUMNS.values())
        rows = conn.execute(
            f"SELECT fd.file_path, f.func_name, f.start_line, {cols} "  # noqa: S608 -- fixed column list
            "FROM function_data f JOIN file_data fd ON f.file_id = fd.id "
            "ORDER BY fd.file_path, f.start_line, f.func_name, f.id"
        ).fetchall()
        out: dict[str, dict[str, Any]] = {}
        for path, name, line, *values in rows:
            per_file = out.setdefault(path, {k: {} for k in FUNCTION_COLUMNS})
            key = f"{name}@{line}"
            n = 1
            while key in per_file["Function Archetype"]:
                n += 1
                key = f"{name}@{line}#{n}"
            for (label, column), raw in zip(FUNCTION_COLUMNS.items(), values):
                per_file[label][key] = _value(column, raw)
        edges = conn.execute(
            "SELECT s.file_path, d.file_path, e.edge_kind FROM edge_data e "
            "JOIN file_data s ON e.src_file_id = s.id JOIN file_data d ON e.dst_file_id = d.id"
        ).fetchall()
        for src, dst, kind in edges:
            per_file = out.setdefault(src, {})
            per_file.setdefault(EDGES_KEY, []).append(f"{kind}:{dst}")
        for per_file in out.values():
            if EDGES_KEY in per_file:
                per_file[EDGES_KEY] = sorted(per_file[EDGES_KEY])
        return out
    finally:
        conn.close()


def attach(audit: dict[str, Any], db_path: str | Path) -> dict[str, Any]:
    """Add ``SECTION`` to every audit file the DB has rows for. In place; returns
    ``audit``. A DB path absent from the audit is ignored (the audit governs
    which files exist)."""
    snap = snapshot(db_path)
    for group in (audit.get(PARSED) or {}).values():
        for path, record in (group.get("Files") or {}).items():
            if path in snap:
                record[SECTION] = snap[path]
    return audit
