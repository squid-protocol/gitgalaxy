# ==============================================================================
# GitGalaxy Tool: the refractor's engine-sourced analysis (#3348)
#
# With a master DB, the refractor reads a program's DD lineage, its record layouts
# (the schemas) and its dynamic CALLs from the engine's fact channels -- dataset_data,
# record_data, call_site_data -- instead of re-parsing the source. Each builder
# returns the shape the forge reader it replaces returns (extract_lineage,
# forge_schemas), or None when the DB predates the channel, so the caller keeps the
# forge for that field and says so in `ir_sources`.
#
# Dead code stays on the forge (docs/unreferenced_by_name_contract.md): the forge's
# reachability analysis names the dead paragraphs, and a fact is dropped when its
# line falls in one. The engine's units give each paragraph's span; `usage_status`
# is never used for masking.
# ==============================================================================
from __future__ import annotations

from typing import Any

from gitgalaxy.tools.cobol_to_cobol.cobol_schema_forge import render_schemas


def _unit_at(units: list, line: int) -> str | None:
    """The paragraph or section a PROCEDURE DIVISION line belongs to: the last unit that
    starts at or before it (a section's paragraphs start after it, so they win), or None
    before the first one -- the forge's `MAIN-ENTRY`, which no dead set names."""
    name = None
    for u in sorted(units, key=lambda u: u.start_line):
        if 0 < u.start_line <= line:
            name = u.name
    return name


def engine_lineage(ef: Any, dead_paras: set | None = None) -> dict | None:
    """`extract_lineage` from the DB: the DDs a program OPENs for input and for output, and
    its dynamic CALLs, the ones in dead paragraphs dropped. None when the DB has no OPEN
    sites (written before #3348) or the program has no PROGRAM-ID (the forge's own None)."""
    rows = [d for d in ef.datasets if d.internal_name is not None]
    if any(d.open_sites is None for d in rows) or not ef.program_ids:
        return None
    dead = {p.upper() for p in dead_paras or ()}
    live = lambda line: (_unit_at(ef.units, line) or "").upper() not in dead  # noqa: E731
    inputs, outputs = set(), set()
    for d in rows:
        for mode, line in d.open_sites:
            if not live(line):
                continue
            # I-O and EXTEND need the file to exist (input) and change it (output).
            if mode in ("INPUT", "I-O", "EXTEND"):
                inputs.add(d.dd_name)
            if mode in ("OUTPUT", "I-O", "EXTEND"):
                outputs.add(d.dd_name)
    dynamic = {
        c.operand for c in ef.calls if c.verb == "CALL" and c.form == "identifier" and c.operand and live(c.line)
    }
    return {
        "program_id": ef.program_ids[0].upper(),
        "inputs": inputs,
        "outputs": outputs,
        "unresolved_calls": sorted(dynamic),
    }


def engine_schemas(ef: Any, table_name: str, ignore_vars: set | None = None, corporate_header: str = "") -> Any:
    """`forge_schemas` from the DB's record_data: the same rendering over the engine's data
    description entries in source order. False when the DB predates record_data (the
    caller keeps the forge); otherwise the schemas, or None when there are no columns."""
    if not ef.records_read:
        return False
    entries = [
        {
            "level": f"{it.level:02d}",
            "name": it.name.upper() if it.name else None,
            "pic": it.pic.upper() if it.pic else None,
            "usage": it.usage.upper() if it.usage else None,
            "depending": it.occurs_depending_on is not None,
        }
        for it in sorted(ef.data_items, key=lambda it: it.ordinal)
    ]
    return render_schemas(entries, table_name, ignore_vars, corporate_header)
