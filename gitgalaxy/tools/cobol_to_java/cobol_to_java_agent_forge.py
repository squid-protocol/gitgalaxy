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
# ==============================================================================


from typing import Optional


def generate_java_agent_ticket(slice_json: dict, prog_id: str, ir_state: Optional[dict] = None) -> dict:
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
    formatted_rules = []
    for rule in rules:
        formatted_rules.append(f"// Context: {rule['paragraph']}\n{rule['statement']}")

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

    return ticket
