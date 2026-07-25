#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: Autonomous Agent Task Generator
#
# PURPOSE:
# Converts Architectural Anomalies and legacy structural dependencies into 
# highly constrained, structured JSON task tickets designed for automated 
# LLM agent dispatchers.
#
# ARCHITECTURAL DECISION:
# Providing an autonomous AI agent with raw, unconstrained legacy code often 
# leads to Context Window Exhaustion and severe hallucinations (e.g., hallucinating 
# missing copybooks or external dependencies). By structuring the remediation 
# tasks into strict JSON tickets with pre-resolved data lineage (inputs/outputs) 
# and explicitly identified anomalies, we mathematically bound the agent's scope, 
# ensuring deterministic and safe code modifications.
# ==============================================================================
import json
from pathlib import Path
from typing import Dict, List, Optional


def generate_agent_ticket(
    file_name: str, source_file: Path, anomalies: list, ir_state: Optional[dict]
) -> dict:
    """Generates a structured JSON task ticket for an autonomous agent."""

    # Extract Dependency Graph lineage to provide the agent with strict I/O context
    lineage = {}
    if ir_state:
        lineage = ir_state.get("analysis", {}).get("lineage", {})

    clean_anomalies = [a.split("]", 1)[-1].strip() if "]" in a else a for a in anomalies]

    ticket = {
        "job_id": f"{file_name.split('.')[0]}_REMEDIATION",
        "status": "PENDING",
        "task_type": "STRUCTURAL_ANOMALY_RESOLUTION",
        "target_file": str(source_file.resolve()),
        "context": {
            "detected_anomalies": clean_anomalies,
            "inputs_required": list(lineage.get("inputs", [])),
            "outputs_produced": list(lineage.get("outputs", [])),
            "external_calls": list(lineage.get("unresolved_calls", [])),
        },
        "system_prompt": (
            "You are a deterministic legacy systems architect. Your task is to analyze the "
            "provided 'target_file' and resolve the structural issues listed in 'detected_anomalies'. "
            "Do not alter the core business logic. Return your proposed solution as a valid JSON "
            "object containing a 'diagnosis' string and a 'patched_code' string."
        ),
    }

    return ticket


def forge_agent_jobs(staging_dir: Path, source_dir: Path, architectural_anomalies: list):
    """
    Parses global architectural anomalies and generates individual JSON task tickets per file.
    (Function name preserved for downstream pipeline compatibility).
    """
    if not architectural_anomalies:
        return 0

    out_dir = staging_dir / "06_ai_agent_jobs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ir_dir = staging_dir / "04_ir_state_dumps"

    # Group anomalies by their target file
    file_anomalies: Dict[str, List[str]] = {}
    for anomaly in architectural_anomalies:
        if anomaly.startswith("[") and "]" in anomaly:
            file_name = anomaly[1 : anomaly.index("]")]
            if file_name not in file_anomalies:
                file_anomalies[file_name] = []
            file_anomalies[file_name].append(anomaly)

    jobs_generated = 0
    for file_name, anomalies in file_anomalies.items():
        source_file = next(source_dir.rglob(file_name), None)
        if not source_file:
            continue

        # Extract the Intermediate Representation (IR) state for dependency context
        prog_id = file_name.split(".")[0]
        ir_file = ir_dir / f"{prog_id}_ir.json"
        ir_state = json.loads(ir_file.read_text(encoding="utf-8")) if ir_file.exists() else None

        ticket = generate_agent_ticket(file_name, source_file, anomalies, ir_state)

        ticket_file = out_dir / f"{prog_id}_agent_job.json"
        ticket_file.write_text(json.dumps(ticket, indent=2), encoding="utf-8")
        jobs_generated += 1

    return jobs_generated