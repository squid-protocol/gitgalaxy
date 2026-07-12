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
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime

# Import the core logic functions directly
from gitgalaxy.tools.cobol_to_cobol.cobol_jcl_forge import (
    analyze_cobol_intent,
    generate_zero_trust_jcl,
)
from gitgalaxy.tools.cobol_to_cobol.cobol_dag_architect import extract_lineage
from gitgalaxy.tools.cobol_to_cobol.cobol_graveyard_finder import x_ray_dead_code
from gitgalaxy.tools.cobol_to_cobol.cobol_schema_forge import forge_schemas
from gitgalaxy.tools.cobol_to_cobol.cobol_microservice_slicer import (
    slice_business_logic,
)
from gitgalaxy.tools.cobol_to_cobol.cobol_system_limits_reporter import (
    scan_system_limits,
)
from gitgalaxy.tools.cobol_to_cobol.cobol_lexical_patcher import patch_lexical_traps
from gitgalaxy.tools.cobol_to_cobol.cobol_jcl_auditor import audit_zero_trust_jcls
from gitgalaxy.tools.cobol_to_cobol.cobol_agent_task_forge import forge_agent_jobs

# ==============================================================================

# galaxyscope:ignore sec_db_hooks, sec_io, sec_high_risk_execution
# THE SCALE SENSOR & HYBRID STATE MANAGER
# ==============================================================================

# galaxyscope:ignore sec_db_hooks, sec_io, sec_high_risk_execution


def calibrate_ir_medium(target_path: Path, max_files=2000, max_mb=200) -> tuple:
    """Scouts the repository to determine the safest IR storage medium."""
    print("🛰️ Scouting repository mass...")

    cobol_files = list(target_path.rglob("*.cbl")) + list(target_path.rglob("*.cob"))
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
        self.ram_ir = {}
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
        elif self.mode == "SQLITE":
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
        elif self.mode == "SQLITE":
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT entity_name FROM Graveyard WHERE program_id=? AND entity_type='PARAGRAPH'",
                (program_id,),
            )
            return {row[0] for row in cursor.fetchall()}

    def get_orphaned_vars(self, program_id: str) -> set:
        if self.mode == "RAM":
            return self.ram_ir.get(program_id, {}).get("orphaned_vars", set())
        elif self.mode == "SQLITE":
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT entity_name FROM Graveyard WHERE program_id=? AND entity_type='VARIABLE'",
                (program_id,),
            )
            return {row[0] for row in cursor.fetchall()}

    def close(self):
        if self.conn:
            self.conn.close()


# ==============================================================================

# galaxyscope:ignore sec_db_hooks, sec_io, sec_high_risk_execution
# THE PROCESSING PIPELINE
# ==============================================================================

# galaxyscope:ignore sec_db_hooks, sec_io, sec_high_risk_execution


def process_payload(filepath: Path, state_manager: IRStateManager, target_var: str = None) -> dict:
    """Processes a single COBOL payload through the enriched, shared-state pipeline."""
    print(f" ⚙️ Analyzing {filepath.name}...")
    program_id = filepath.stem

    # 1. Initialize local file payload
    ir = {
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
        ir["metadata"]["loc"] = len(filepath.read_text(encoding="utf-8", errors="ignore").splitlines())
    except Exception:
        return ir

    # --- PHASE 0: PRE-PROCESSING (Sanitizing the code) ---
    was_patched = patch_lexical_traps(filepath)
    if was_patched:
        print(f"   ↳ [!] Lexical Patcher applied to {filepath.name} (NEXT SENTENCE neutralized)")

    # --- PHASE 1: RECONNAISSANCE & ANALYSIS ---

    # A. Deprecated Trails Analyzer (Identifies Dead Memory & Unreachable Logic)
    graveyard_data = x_ray_dead_code(filepath)
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
    ir["analysis"]["lineage"] = extract_lineage(filepath, dead_paras=dead_paras)

    # C. JCL Forge (Extracts Program ID and Subsystems)
    ir["analysis"]["base_intent"] = analyze_cobol_intent(filepath)

    ir["analysis"]["honesty_flags"] = scan_system_limits(filepath)

    # --- PHASE 2: CONTEXT-AWARE GENERATION ---

    # A. Schema Forge (Injecting Deprecated Trails RAM to prevent Schema Bloat)
    ir["generation"]["schemas"] = forge_schemas(
        filepath,
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
            filepath,
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
    args = parser.parse_args()

    target_path = Path(args.target).resolve()
    if not target_path.exists():
        print(f"Error: Target {target_path} does not exist.")
        sys.exit(1)

    # Create the Clean-Room parallel directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_dir = target_path.parent / f"{target_path.name}_gitgalaxy_clean_{timestamp}"

    # Define the sub-architecture
    jcl_dir = clean_dir / "01_zero_trust_jcls"
    schema_dir = clean_dir / "02_cloud_schemas"
    report_dir = clean_dir / "03_audit_reports"
    ir_dir = clean_dir / "04_ir_state_dumps"

    directories = [jcl_dir, schema_dir, report_dir, ir_dir]

    slice_dir = None
    if args.var:
        slice_dir = clean_dir / "05_microservice_slices"
        directories.append(slice_dir)

    for d in directories:
        d.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 70)
    print(" 🚀 COBOL REFRACTOR CONTROLLER (v4.0) ENGAGED")
    print(f" Target: {target_path.name}")
    if args.var:
        print(f" Global Taint Tracking Target: [{args.var.upper()}]")
    print("=" * 70 + "\n")

    # 1. Sense the scale of the repository
    ir_mode, cobol_files = calibrate_ir_medium(target_path)
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

    for file_path in cobol_files:
        # Process the payload, passing the state manager for global context
        ir_state = process_payload(file_path, state_manager, target_var=args.var)

        # Write JSON IR Dump for downstream visualizers
        ir_dump_file = ir_dir / f"{file_path.stem}_ir.json"
        safe_ir = json.loads(json.dumps(ir_state, default=lambda o: list(o) if isinstance(o, set) else o))
        ir_dump_file.write_text(json.dumps(safe_ir, indent=2))

        # Write JCL Artifacts
        if ir_state["generation"].get("jcl"):
            jcl_output = jcl_dir / f"{file_path.stem}.jcl"
            jcl_output.write_text(ir_state["generation"]["jcl"], encoding="utf-8")
            master_scaffold_stats["jcls_forged"] += 1

        # Write Schema Artifacts
        if ir_state["generation"].get("schemas"):
            schema_output = schema_dir / f"{file_path.stem}_schema.sql"
            schema_output.write_text(ir_state["generation"]["schemas"]["sql"], encoding="utf-8")
            json_output = schema_dir / f"{file_path.stem}_schema.json"
            json_output.write_text(
                json.dumps(ir_state["generation"]["schemas"]["json"], indent=2),
                encoding="utf-8",
            )
            master_scaffold_stats["schemas_forged"] += 1

        # Write Microservice Slices
        if args.var and ir_state["generation"].get("microservice"):
            slice_data = ir_state["generation"]["microservice"]
            if slice_data.get("business_rules"):
                slice_output = slice_dir / f"{file_path.stem}_slice.json"
                slice_output.write_text(json.dumps(slice_data, indent=2), encoding="utf-8")
                master_scaffold_stats["slices_extracted"] += 1

        # Aggregate Deprecated Trails Stats
        gy = ir_state["analysis"].get("dead_code")
        if gy:
            master_graveyard_stats["loc_saved"] += gy.get("loc_saved", 0)
            master_graveyard_stats["orphaned_vars"] += len(gy.get("orphaned_vars", []))
            master_graveyard_stats["dead_paras"] += len(gy.get("dead_paras", []))

        # Aggregate Architectural Anomalies
        lineage = ir_state["analysis"].get("lineage")
        if lineage and lineage.get("unresolved_calls"):
            for call in lineage["unresolved_calls"]:
                master_honesty_flags.append(f"[{file_path.name}] Unresolved Dynamic CALL to: {call}")

        system_limits = ir_state["analysis"].get("honesty_flags")
        if system_limits:
            master_honesty_flags.extend(system_limits)

    # Close DB connection if applicable
    state_manager.close()

    # Run the Zero-Trust JCL Audit
    audit_metrics = audit_zero_trust_jcls(jcl_dir, target_path)

    # --- NEW: Forge the Autonomous Agent Job Tickets ---
    agent_jobs_created = forge_agent_jobs(clean_dir, target_path, master_honesty_flags)

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
        f.write("\n==========================================================\n")

    print("=" * 70)
    print(" 🏁 REFRACTION COMPLETE: Hybrid Pipeline execution successful.")
    print(f" 📁 Location: {clean_dir}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()