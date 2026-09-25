#!/usr/bin/env python3
# ==============================================================================

# galaxyscope:ignore sec_db_hooks, sec_io, sec_high_risk_execution
# GitGalaxy: COBOL Refractor Controller (v4.0 - Hybrid Enterprise Scale)
# Purpose: Orchestrates the Universal Translator suite using a Hybrid
#          Intermediate Representation (IR) State Manager. Dynamically toggles
#          between high-speed RAM and SQLite3 to prevent OOM crashes.
# ==============================================================================

# galaxyscope:ignore sec_db_hooks, sec_io, sec_high_risk_execution

# galaxyscope:ignore sec_db_hooks, sec_io, sec_high_risk_execution

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from gitgalaxy.tools.cobol_to_cobol.cobol_agent_task_forge import forge_agent_jobs
from gitgalaxy.tools.cobol_to_cobol.cobol_dag_architect import extract_lineage
from gitgalaxy.tools.cobol_to_cobol.cobol_graveyard_finder import x_ray_dead_code
from gitgalaxy.tools.cobol_to_cobol.cobol_jcl_auditor import audit_zero_trust_jcls

# Import the core logic functions directly
from gitgalaxy.tools.cobol_to_cobol.cobol_jcl_forge import (
    analyze_cobol_intent,
    generate_zero_trust_jcl,
)
from gitgalaxy.tools.cobol_to_cobol.cobol_lexical_patcher import patch_lexical_content
from gitgalaxy.tools.cobol_to_cobol.cobol_microservice_slicer import (
    slice_business_logic,
)
from gitgalaxy.tools.cobol_to_cobol.cobol_schema_forge import forge_schemas
from gitgalaxy.tools.cobol_to_cobol.cobol_system_limits_reporter import (
    scan_system_limits,
)
from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import (
    EngineFile,
    GalaxyIR,
    load_galaxy_ir,
    scan_to_db,
)
from gitgalaxy.tools.cobol_to_cobol.skeleton_export import write_skeletons

# ==============================================================================

# galaxyscope:ignore sec_db_hooks, sec_io, sec_high_risk_execution
# THE SCALE SENSOR & HYBRID STATE MANAGER
# ==============================================================================

# galaxyscope:ignore sec_db_hooks, sec_io, sec_high_risk_execution


def calibrate_ir_medium(
    target_path: Path,
    max_files=2000,
    max_mb=200,
    cobol_files: Optional[list[Path]] = None,
) -> tuple:
    """Scouts the repository to determine the safest IR storage medium.

    `cobol_files` is the program list when the engine's master DB supplied it
    (#3120); otherwise the programs are found by extension.
    """
    print("🛰️ Scouting repository mass...")

    if cobol_files is None:
        # Sorted by parts, which compare case-sensitively on every OS (WindowsPath's own order does not):
        # rglob order is the filesystem's, and it orders the report and the agent jobs (#3212)
        # `.cobol` too (#3491): navikt/DSF's batch programs, and a cobol extension the engine claims.
        found = [*target_path.rglob("*.cbl"), *target_path.rglob("*.cob"), *target_path.rglob("*.cobol")]
        cobol_files = sorted(found, key=lambda p: p.parts)
    file_count = len(cobol_files)

    total_bytes = sum(f.stat().st_size for f in cobol_files if f.is_file())
    total_mb = total_bytes / (1024 * 1024)

    print(f"   ↳ Found: {file_count} executable files ({total_mb:.2f} MB)")

    if file_count > max_files or total_mb > max_mb:
        print("   ↳ CRITICAL MASS REACHED: Engaging SQLite3 Storage Engine.")
        return "SQLITE", cobol_files
    else:
        print("   ↳ OPTIMAL MASS: Engaging High-Speed RAM Dictionary.")
        return "RAM", cobol_files


class IRStateManager:
    """Abstracts the IR storage so the spoke tools don't have to care if it's RAM or SQL."""

    def __init__(self, mode: str, db_path: Path):
        self.mode = mode
        self.ram_ir: dict[str, dict[str, Any]] = {}
        self.conn = None

        if self.mode == "SQLITE":
            self.db_file = db_path / "gitgalaxy_ir.db"
            self.conn = sqlite3.connect(self.db_file)
            self._init_sql_schema()

    def _init_sql_schema(self):
        """Sets up the relational structure for the massive codebase. (Maintains legacy schema names for downstream compatibility)"""
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Graveyard (
                program_id TEXT,
                entity_type TEXT,
                entity_name TEXT,
                UNIQUE(program_id, entity_type, entity_name)
            )
        """)
        self.conn.commit()

    def record_dead_code(self, program_id: str, dead_paras: set, orphaned_vars: set):
        if self.mode == "RAM":
            self.ram_ir[program_id] = {
                "dead_paras": dead_paras,
                "orphaned_vars": orphaned_vars,
            }
        elif self.mode == "SQLITE" and self.conn is not None:
            cursor = self.conn.cursor()
            for p in dead_paras:
                cursor.execute(
                    "INSERT OR IGNORE INTO Graveyard VALUES (?, 'PARAGRAPH', ?)",
                    (program_id, p),
                )
            for v in orphaned_vars:
                cursor.execute(
                    "INSERT OR IGNORE INTO Graveyard VALUES (?, 'VARIABLE', ?)",
                    (program_id, v),
                )
            self.conn.commit()

    def get_dead_paras(self, program_id: str) -> set:
        if self.mode == "RAM":
            return self.ram_ir.get(program_id, {}).get("dead_paras", set())
        elif self.mode == "SQLITE" and self.conn is not None:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT entity_name FROM Graveyard WHERE program_id=? AND entity_type='PARAGRAPH'",
                (program_id,),
            )
            return {row[0] for row in cursor.fetchall()}
        return set()

    def get_orphaned_vars(self, program_id: str) -> set:
        if self.mode == "RAM":
            return self.ram_ir.get(program_id, {}).get("orphaned_vars", set())
        elif self.mode == "SQLITE" and self.conn is not None:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT entity_name FROM Graveyard WHERE program_id=? AND entity_type='VARIABLE'",
                (program_id,),
            )
            return {row[0] for row in cursor.fetchall()}
        return set()

    def close(self):
        if self.conn:
            self.conn.close()


# ==============================================================================

# galaxyscope:ignore sec_db_hooks, sec_io, sec_high_risk_execution
# THE PROCESSING PIPELINE
# ==============================================================================

# galaxyscope:ignore sec_db_hooks, sec_io, sec_high_risk_execution


def _ir_to_json(ir_state: dict) -> str:
    """Serialises an IR dump. Sets are written sorted, so two runs on the same
    input produce byte-identical dumps regardless of hash randomisation (#3212)."""
    return json.dumps(ir_state, indent=2, default=lambda o: sorted(o, key=str) if isinstance(o, set) else o)


def _output_keys(cobol_files: list[Path], target_path: Path) -> dict[Path, str]:
    """Each program's name in the clean room's flat output directories and in the
    IR state: its stem when no other program in the run shares it, otherwise its
    path under the target flattened with `__` (`multiroot__sam__SAM2`). Keying by
    stem alone let same-named programs overwrite each other's outputs and, in
    SQLite mode, merge their dead code (#3218)."""
    stems = Counter(f.stem.upper() for f in cobol_files)
    keys = {}
    for f in cobol_files:
        if stems[f.stem.upper()] == 1:
            keys[f] = f.stem
        else:
            keys[f] = "__".join(_rel(f, target_path).with_suffix("").parts)
    return keys


def _rel(filepath: Path, root: Optional[Path]) -> Path:
    return filepath.relative_to(root) if root and filepath.is_relative_to(root) else Path(filepath.name)


def process_payload(
    filepath: Path,
    state_manager: IRStateManager,
    target_var: Optional[str] = None,
    engine_file: Optional[EngineFile] = None,
    patched_dir: Optional[Path] = None,
    source_root: Optional[Path] = None,
    program_key: Optional[str] = None,
) -> dict:
    """Processes a single COBOL payload through the enriched, shared-state pipeline.

    `engine_file` is this program's record from the engine's master DB (#3120).
    It supplies PROGRAM-ID, the COPY dependency graph and the paragraph
    inventory. Dead code, DD lineage and data items stay on the forge tools:
    the DB does not carry them (see galaxy_ir.py), and `usage_status` is a
    by-name test, not reachability, so it is recorded but never used for masking.

    `filepath` is never written. When the lexical patcher rewrites the program, the
    patched copy goes to `patched_dir` (mirroring its path under `source_root`) and
    the forge tools read that copy (#3206). Without `patched_dir` nothing is patched.
    `source_root` is also where copybooks are looked up. `program_key` names the
    program in the IR state (default: its stem; see `_output_keys`).
    """
    print(f" ⚙️ Analyzing {filepath.name}...")
    program_id = program_key or filepath.stem

    # 1. Initialize local file payload
    ir: dict[str, Any] = {
        "metadata": {
            "file_name": filepath.name,
            "path": str(filepath),
            "corporate_header": "",
        },
        "analysis": {},
        "generation": {},
    }

    # Check for the Corporate Header stamp
    header_file = filepath.parent / "corporate_header.txt"
    if header_file.exists():
        ir["metadata"]["corporate_header"] = header_file.read_text(encoding="utf-8", errors="ignore")

    try:
        source_text = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ir
    ir["metadata"]["loc"] = len(source_text.splitlines())

    # --- PHASE 0: PRE-PROCESSING (Sanitizing the code) ---
    # The patch lands in the clean room, never in the target repository (#3206).
    work_path = filepath
    patched_content = patch_lexical_content(source_text)
    if patched_content is not None:
        if patched_dir is None:
            print(
                f"   ↳ [!] {filepath.name} needs the Lexical Patcher but no patched_dir was given; analysing it unpatched"
            )
        else:
            work_path = patched_dir / _rel(filepath, source_root)
            work_path.parent.mkdir(parents=True, exist_ok=True)
            work_path.write_text(patched_content, encoding="utf-8")
            ir["metadata"]["patched_path"] = str(work_path)
            print(f"   ↳ [!] Lexical Patcher applied to a copy of {filepath.name} (NEXT SENTENCE neutralized)")

    # --- PHASE 1: RECONNAISSANCE & ANALYSIS ---

    # A. Deprecated Trails Analyzer (Identifies Dead Memory & Unreachable Logic)
    graveyard_data = x_ray_dead_code(work_path, copybook_root=source_root or filepath.parent, origin=filepath)
    ir["analysis"]["dead_code"] = graveyard_data

    if graveyard_data:
        # Save to the abstracted State Manager (RAM or SQL)
        state_manager.record_dead_code(
            program_id,
            dead_paras=graveyard_data.get("dead_paras", set()),
            orphaned_vars=graveyard_data.get("orphaned_vars", set()),
        )

    # Retrieve active context from the State Manager
    dead_paras = state_manager.get_dead_paras(program_id)
    orphans = state_manager.get_orphaned_vars(program_id)

    # B. DAG Architect (Maps I/O Intent - Utilizing Deprecated Trails RAM to deflect Hallucinated Dependencies!)
    ir["analysis"]["lineage"] = extract_lineage(work_path, dead_paras=dead_paras)

    # C. JCL Forge (Extracts Program ID and Subsystems)
    ir["analysis"]["base_intent"] = analyze_cobol_intent(work_path)

    ir["analysis"]["honesty_flags"] = scan_system_limits(work_path)

    if engine_file is not None:
        ir["metadata"]["ir_source"] = "galaxy_db"
        if engine_file.program_ids and ir["analysis"]["base_intent"]:
            ir["analysis"]["base_intent"]["program_id"] = engine_file.program_ids[0]
        ir["analysis"]["copy_dependencies"] = list(engine_file.copy_deps)
        ir["analysis"]["engine_units"] = [
            {"name": u.name, "start_line": u.start_line, "loc": u.loc, "usage_status": u.usage_status}
            for u in engine_file.units
        ]

    # --- PHASE 2: CONTEXT-AWARE GENERATION ---

    # A. Schema Forge (Injecting Deprecated Trails RAM to prevent Schema Bloat)
    ir["generation"]["schemas"] = forge_schemas(
        work_path,
        ignore_vars=orphans,
        corporate_header=ir["metadata"]["corporate_header"],
    )

    # B. JCL Forge (Injecting DAG RAM for Accurate DISP routing)
    dag_lineage = ir["analysis"]["lineage"] or {"inputs": set(), "outputs": set()}
    if ir["analysis"]["base_intent"]:
        ir["generation"]["jcl"] = generate_zero_trust_jcl(
            intent=ir["analysis"]["base_intent"],
            lineage=dag_lineage,
            job_name="GITGJOB",
            account_code="12345",
            corporate_header=ir["metadata"]["corporate_header"],
        )

    # C. Microservice Slicer (Injecting Deprecated Trails RAM to bypass dead execution blocks)
    if target_var:
        slice_result = slice_business_logic(
            work_path,
            initial_var=target_var,
            dead_paras=dead_paras,
            orphaned_vars=orphans,
        )
        if slice_result:
            logic_slice, aliases = slice_result
            ir["generation"]["microservice"] = {
                "target_var": target_var,
                "aliases_found": list(aliases) if isinstance(aliases, set) else aliases,
                "business_rules": logic_slice,
            }

    return ir


# ==============================================================================

# galaxyscope:ignore sec_db_hooks, sec_io, sec_high_risk_execution
# MAIN ORCHESTRATION LOOP
# ==============================================================================

# galaxyscope:ignore sec_db_hooks, sec_io, sec_high_risk_execution


def main():
    from gitgalaxy.licensing import enforce_licensing_guard

    enforce_licensing_guard("COBOL Refractor (The Legacy Forge)")

    parser = argparse.ArgumentParser(description="GitGalaxy COBOL Refractor Controller (v4)")
    parser.add_argument("target", help="The legacy repository or directory to scan")
    parser.add_argument(
        "--var",
        type=str,
        help="Optional: A target variable to slice across the entire repository",
    )
    ir_source = parser.add_mutually_exclusive_group()
    ir_source.add_argument(
        "--galaxy-db",
        type=Path,
        help="Use an existing galaxyscope <repo>_galaxy_master.db of TARGET as the IR source",
    )
    ir_source.add_argument(
        "--scan",
        action="store_true",
        help="Run galaxyscope on TARGET first and use its master DB as the IR source",
    )
    args = parser.parse_args()

    target_path = Path(args.target).resolve()
    if not target_path.exists():
        print(f"Error: Target {target_path} does not exist.")
        sys.exit(1)

    # Create the Clean-Room parallel directory
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    clean_dir = target_path.parent / f"{target_path.name}_gitgalaxy_clean_{timestamp}"

    # Define the sub-architecture
    jcl_dir = clean_dir / "01_zero_trust_jcls"
    schema_dir = clean_dir / "02_cloud_schemas"
    report_dir = clean_dir / "03_audit_reports"
    ir_dir = clean_dir / "04_ir_state_dumps"
    # Created on demand: only programs the lexical patcher rewrites are copied here (#3206)
    patched_dir = clean_dir / "00_patched_source"

    directories = [jcl_dir, schema_dir, report_dir, ir_dir]

    slice_dir = None
    if args.var:
        slice_dir = clean_dir / "05_microservice_slices"
        directories.append(slice_dir)

    # 0. Optional engine IR source (#3120)
    galaxy_ir: Optional[GalaxyIR] = None
    program_files: Optional[list[Path]] = None
    if args.galaxy_db or args.scan:
        db_path = scan_to_db(target_path, ir_dir) if args.scan else args.galaxy_db.resolve()
        galaxy_ir = load_galaxy_ir(db_path)
        program_files = [target_path / ef.file_path for ef in galaxy_ir.programs("cobol")]
        missing = [p for p in program_files if not p.is_file()]
        if missing:
            print(
                f"Error: {db_path.name} does not describe {target_path} ({len(missing)} programs missing, e.g. {missing[0]})."
            )
            sys.exit(1)
        print(f"🔭 IR source: {db_path.name} (commit {galaxy_ir.commit_hash[:8]})")

    for d in directories:
        d.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 70)
    print(" 🚀 COBOL REFRACTOR CONTROLLER (v4.0) ENGAGED")
    print(f" Target: {target_path.name}")
    if args.var:
        print(f" Global Taint Tracking Target: [{args.var.upper()}]")
    print("=" * 70 + "\n")

    # 1. Sense the scale of the repository
    ir_mode, cobol_files = calibrate_ir_medium(target_path, cobol_files=program_files)
    if not cobol_files:
        print("⚠️ No executable COBOL files found in the target location.")
        sys.exit(0)

    # 2. Initialize the Abstract State Manager
    state_manager = IRStateManager(mode=ir_mode, db_path=ir_dir)

    print(f"\n Forging Context-Aware Artifacts at: {clean_dir.name}\n" + "-" * 70)

    master_graveyard_stats = {"loc_saved": 0, "orphaned_vars": 0, "dead_paras": 0}
    master_honesty_flags = []  # Array to hold our edge-case warnings
    master_scaffold_stats = {
        "schemas_forged": 0,
        "jcls_forged": 0,
        "slices_extracted": 0,
    }

    output_keys = _output_keys(cobol_files, target_path)
    ir_keys: dict[str, str] = {}
    for file_path in cobol_files:
        key = output_keys[file_path]
        rel = _rel(file_path, target_path).as_posix()
        ir_keys[rel] = key
        # Process the payload, passing the state manager for global context
        engine_file = galaxy_ir.lookup(file_path, target_path) if galaxy_ir else None
        ir_state = process_payload(
            file_path,
            state_manager,
            target_var=args.var,
            engine_file=engine_file,
            patched_dir=patched_dir,
            source_root=target_path,
            program_key=key,
        )

        # Write JSON IR Dump for downstream visualizers
        ir_dump_file = ir_dir / f"{key}_ir.json"
        ir_dump_file.write_text(_ir_to_json(ir_state))

        # Write JCL Artifacts
        if ir_state["generation"].get("jcl"):
            jcl_output = jcl_dir / f"{key}.jcl"
            jcl_output.write_text(ir_state["generation"]["jcl"], encoding="utf-8")
            master_scaffold_stats["jcls_forged"] += 1

        # Write Schema Artifacts
        if ir_state["generation"].get("schemas"):
            schema_output = schema_dir / f"{key}_schema.sql"
            schema_output.write_text(ir_state["generation"]["schemas"]["sql"], encoding="utf-8")
            json_output = schema_dir / f"{key}_schema.json"
            json_output.write_text(
                json.dumps(ir_state["generation"]["schemas"]["json"], indent=2),
                encoding="utf-8",
            )
            master_scaffold_stats["schemas_forged"] += 1

        # Write Microservice Slices
        if args.var and ir_state["generation"].get("microservice"):
            slice_data = ir_state["generation"]["microservice"]
            if slice_data.get("business_rules"):
                slice_output = slice_dir / f"{key}_slice.json"
                slice_output.write_text(json.dumps(slice_data, indent=2), encoding="utf-8")
                master_scaffold_stats["slices_extracted"] += 1

        # Aggregate Deprecated Trails Stats
        gy = ir_state["analysis"].get("dead_code")
        if gy:
            master_graveyard_stats["loc_saved"] += gy.get("loc_saved", 0)
            master_graveyard_stats["orphaned_vars"] += len(gy.get("orphaned_vars", []))
            master_graveyard_stats["dead_paras"] += len(gy.get("dead_paras", []))

        # Aggregate Architectural Anomalies, tagged with the program's path under the
        # target so same-named programs stay apart (#3218)
        lineage = ir_state["analysis"].get("lineage")
        if lineage and lineage.get("unresolved_calls"):
            master_honesty_flags.extend(
                f"[{rel}] Unresolved Dynamic CALL to: {call}" for call in lineage["unresolved_calls"]
            )

        system_limits = ir_state["analysis"].get("honesty_flags")
        if system_limits:
            tag = f"[{file_path.name}"
            master_honesty_flags.extend(
                f"[{rel}{flag[len(tag) :]}" if flag.startswith(tag) else flag for flag in system_limits
            )

    # Close DB connection if applicable
    state_manager.close()

    # Run the Zero-Trust JCL Audit
    audit_metrics = audit_zero_trust_jcls(jcl_dir, target_path)

    # #3614: the engine's verified facts per program, for the code generators
    skeletons_written = 0
    if galaxy_ir is not None:
        skeletons_written = write_skeletons(galaxy_ir, ir_keys, clean_dir / "06_skeleton")

    # --- NEW: Forge the Autonomous Agent Job Tickets ---
    agent_jobs_created = forge_agent_jobs(clean_dir, target_path, master_honesty_flags, ir_keys=ir_keys)

    # Generate Master Audit Report
    report_file = report_dir / "master_refraction_audit.txt"
    with open(report_file, "w") as f:
        f.write("==========================================================\n")
        f.write(" GITGALAXY MODERNIZATION REPORT\n")
        f.write("==========================================================\n\n")

        f.write("[1] EXECUTIVE METRICS & DEPRECATED TRAILS REDUCTION\n")
        f.write("----------------------------------------------------------\n")
        f.write(f"  • Files Scanned           : {len(cobol_files)}\n")
        f.write(f"  • State Manager Mode      : {ir_mode}\n")
        f.write(f"  • Unused Memory Addresses : {master_graveyard_stats['orphaned_vars']} orphaned variables\n")
        f.write(f"  • Unreachable Logic Blocks: {master_graveyard_stats['dead_paras']} unreachable blocks\n")
        f.write(f"  ✂️ Estimated Bloat Removed: ~{master_graveyard_stats['loc_saved']} Lines of Code\n\n")

        f.write("[2] ZERO-TRUST JCL ARCHITECTURE\n")
        f.write("----------------------------------------------------------\n")
        f.write(f"  • Programs Audited           : {audit_metrics['audited']}\n")
        f.write(f"  • Original Legacy LOC        : {audit_metrics['original_loc']} lines\n")
        f.write(f"  • GitGalaxy Zero-Trust LOC   : {audit_metrics['forged_loc']} lines\n")
        f.write(f"  📉 Total Code Bloat Removed  : {audit_metrics.get('bloat_reduction_pct', 0)}%\n")
        f.write(f"  🛡️ Over-Permissioned I/O     : {audit_metrics['excess_dds_blocked']} physical files secured\n\n")

        f.write("[3] GENERATED CLOUD SCAFFOLDING\n")
        f.write("----------------------------------------------------------\n")
        f.write(f"  • PostgreSQL DDLs & JSON Schemas Forged : {master_scaffold_stats['schemas_forged']}\n")
        f.write(f"  • Zero-Trust Emulator JCLs Generated    : {master_scaffold_stats['jcls_forged']}\n")
        f.write(f"  • Isolated Microservice Slices Extracted: {master_scaffold_stats['slices_extracted']}\n\n")

        f.write("[4] ⚠️ MANUAL INTERVENTION AUDIT (ARCHITECTURAL ANOMALIES)\n")
        f.write("----------------------------------------------------------\n")
        f.write(f"  • AI Agent Job Tickets Generated : {agent_jobs_created}\n\n")

        if not master_honesty_flags:
            f.write("  ✅ No structural anomalies detected. DAG is highly deterministic.\n")
        else:
            f.write("  The following files contain structural anomalies that require architectural review:\n")
            for flag in master_honesty_flags:
                f.write(f"  [!] {flag}\n")

        if galaxy_ir is not None:
            f.write("\n[5] ENGINE INVENTORY (galaxyscope master DB)\n")
            f.write("----------------------------------------------------------\n")
            f.write(f"  • Source DB : {galaxy_ir.db_path.name} (commit {galaxy_ir.commit_hash[:8]})\n")
            for language, counts in galaxy_ir.inventory().items():
                status = {"cobol": "refracted", "hlasm": "detected, wrap-or-retire (not a migration target)"}.get(
                    language, "detected, not yet migratable"
                )
                f.write(f"  • {language:<10}: {counts['files']} files, {counts['units']} units ({status})\n")
            f.write(f"  • Verified skeletons (06_skeleton): {skeletons_written} programs + estate.json\n")
        f.write("\n==========================================================\n")

    print("=" * 70)
    print(" 🏁 REFRACTION COMPLETE: Hybrid Pipeline execution successful.")
    print(f" 📁 Location: {clean_dir}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
