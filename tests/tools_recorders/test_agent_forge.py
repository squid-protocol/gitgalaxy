from gitgalaxy.tools.cobol_to_java.cobol_to_java_agent_forge import (
    generate_java_agent_ticket,
)


def test_llm_hallucination_prevention():
    """
    Verifies that the Agent Forge correctly extracts strict architectural constraints
    (external dependencies and honesty flags) from the IR state and injects them
    into the JSON ticket. This proves the LLM will not fly blind and hallucinate.
    """
    # 1. Setup the Mock Inputs
    prog_id = "calc-payroll"

    # Mock a specific COBOL slice
    mock_slice = {
        "target_var": "WS-NET-PAY",
        "business_rules": [
            {
                "paragraph": "0100-CALC-TAXES",
                "statement": "COMPUTE WS-TAX = WS-GROSS * 0.20",
            },
            {
                "paragraph": "0200-FINALIZE",
                "statement": "SUBTRACT WS-TAX FROM WS-GROSS GIVING WS-NET-PAY",
            },
        ],
    }

    # Mock the Global IR State containing the guardrails
    mock_ir_state = {
        "analysis": {
            "honesty_flags": [
                "[CRITICAL] Do not use Java floats for currency, use BigDecimal.",
                "This module assumes EBCDIC encoding.",
            ],
            "lineage": {"unresolved_calls": ["TAX-RATES-DB", "AUDIT-LOGGER"]},
        }
    }

    # 2. Forge the Ticket
    ticket = generate_java_agent_ticket(mock_slice, prog_id, mock_ir_state)

    # =====================================================================
    # 3. INVARIANT ASSERTIONS (The Proof)
    # =====================================================================

    # A) Verify the Job ID was formatted correctly
    assert ticket["job_id"] == "CALC-PAYROLL_JAVA_SERVICE_TRANSLATION"
    assert ticket["target_variable"] == "WS-NET-PAY"

    # B) Verify Business Rules were translated into the context array
    context = ticket["context"]
    assert len(context["business_rules_to_translate"]) == 2
    assert "// Context: 0100-CALC-TAXES" in context["business_rules_to_translate"][0]

    # C) THE HALLUCINATION GUARDS: Verify Dependencies were passed perfectly
    assert len(context["external_dependencies"]) == 2
    assert "TAX-RATES-DB" in context["external_dependencies"]

    # D) THE HONESTY GUARDS: Verify warnings were passed AND cleaned
    # The script has a specific line: `a.split(']', 1)[-1].strip() if ']' in a else a`
    # We must prove this strip logic works so the LLM doesn't get confused by internal bracket tags
    assert len(context["architectural_warnings"]) == 2
    assert (
        context["architectural_warnings"][0] == "Do not use Java floats for currency, use BigDecimal."
    )  # The [CRITICAL] tag should be stripped!
    assert context["architectural_warnings"][1] == "This module assumes EBCDIC encoding."
