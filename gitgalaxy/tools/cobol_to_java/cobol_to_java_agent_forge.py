#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: Java Agent Task Generator
#
# PURPOSE:
# Packages isolated COBOL logic slices into strict, highly constrained JSON
# task tickets for autonomous LLM agents to translate into Java.
#
# ARCHITECTURAL DECISION:
# Autonomous agents are highly susceptible to "hallucinating" external system
# calls or modifying core business logic when given an entire legacy file at once.
# By pre-slicing the business rules via static analysis and injecting unresolved
# dependencies as strict constraints, we force the LLM to generate pure,
# side-effect-free @Service classes that rely on Spring's Dependency Injection (DI)
# for external integration.
#
# #3614: when the refractor ran against the engine (--scan / --galaxy-db), the
# program's verified skeleton (06_skeleton/<key>_skeleton.json) rides along as
# `verified_skeleton`: the calls, contracts, resources, screens and transactions
# the engine extracted, each tagged with its field-testing status. The agent
# implements against those facts instead of inferring them from the slice.
# ==============================================================================


from typing import Optional

# Data-level sections left out of a ticket: the agent translates one slice, and these run
# to thousands of rows per program. They stay in the skeleton file the ticket names.
_BULK_SECTIONS = ("records", "data_flows", "units")


def ticket_skeleton(skeleton: dict, skeleton_file: Optional[str] = None) -> dict:
    """The ticket's view of a program skeleton: its non-empty, non-bulk sections."""
    sections = {
        name: {
            "field_testing": sec["field_testing"],
            "tested_on_public": sec["tested_on_public"],
            "tested_on_private": sec["tested_on_private"],
            "facts": sec["facts"],
        }
        for name, sec in skeleton.get("sections", {}).items()
        if sec.get("facts") and name not in _BULK_SECTIONS
    }
    view = {"program": skeleton.get("program", {}), "sections": sections}
    if skeleton_file:
        view["full_skeleton"] = skeleton_file
    return view


def generate_java_agent_ticket(
    slice_json: dict,
    prog_id: str,
    ir_state: Optional[dict] = None,
    skeleton: Optional[dict] = None,
    skeleton_file: Optional[str] = None,
) -> dict:
    """Generates a structured JSON task ticket for Java service generation."""
    target_var = slice_json.get("target_var", "UNKNOWN")
    rules = slice_json.get("business_rules", [])

    # Extract Architectural Anomalies & Data Lineage
    honesty_flags = []
    unresolved_calls = []
    if ir_state:
        analysis = ir_state.get("analysis", {})
        honesty_flags = analysis.get("honesty_flags", [])  # Preserved internal variable name
        lineage = analysis.get("lineage", {})
        unresolved_calls = lineage.get("unresolved_calls", [])

    # Format business rules for the JSON payload
    formatted_rules = [f"// Context: {rule['paragraph']}\n{rule['statement']}" for rule in rules]

    ticket = {
        "job_id": f"{prog_id.upper()}_JAVA_SERVICE_TRANSLATION",
        "status": "PENDING",
        "task_type": "SPRING_BOOT_SERVICE_GENERATION",
        "target_program": prog_id,
        "target_variable": target_var,
        "context": {
            "business_rules_to_translate": formatted_rules,
            "external_dependencies": unresolved_calls,
            "architectural_warnings": [a.split("]", 1)[-1].strip() if "]" in a else a for a in honesty_flags],
        },
        "system_prompt": (
            "You are a strict, deterministic code translator. You must implement the provided "
            f"COBOL business logic into a Java Spring Boot `@Service` class named `{prog_id.capitalize()}Service`. "
            "CONSTRAINTS: 1. Do not hallucinate external systems. 2. If 'external_dependencies' exist, "
            "implement interface calls to them; do not write them. 3. Account for 'architectural_warnings'. "
            "Return your proposed solution as a valid JSON object containing a 'diagnosis' string and a "
            "'java_code' string."
        ),
    }
    if skeleton:
        ticket["context"]["verified_skeleton"] = ticket_skeleton(skeleton, skeleton_file)
        ticket["system_prompt"] += (
            " 'verified_skeleton' holds the facts GitGalaxy's engine extracted about this program: use its "
            "calls, contracts, resources, screens and transactions as given, and do not invent others. A "
            "section whose field_testing is not 'field-tested' is verified on reference estates but still "
            "being field-tested: where the slice contradicts it, report that in 'diagnosis'."
        )

    return ticket
