from gitgalaxy.tools.cobol_to_java.cobol_to_java_service_forge import (
    generate_service_skeleton,
)

# ==============================================================================
# INLINE FIXTURES
# ==============================================================================
MOCK_IR_STATE = {
    "metadata": {"file_name": "payroll-processor.cbl"},
    "analysis": {
        "lineage": {
            # Two distinct COBOL-style program names with hyphens
            "unresolved_calls": ["CALC-BENEFITS", "UPDATE-LEDGER"]
        }
    },
}

# ==============================================================================
# GOLDEN IMAGE
# ==============================================================================
GOLDEN_SERVICE_SKELETON = """package com.gitgalaxy.modernized.service;

import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Service
@RequiredArgsConstructor
public class PayrollProcessorService {

    private static final Logger log = LoggerFactory.getLogger(PayrollProcessorService.class);

    // ⚠️ UNRESOLVED EXTERNAL DEPENDENCIES (FROM DAG)
    // TODO: AI AGENT - Implement or mock interface call to: CalcBenefitsService
    // TODO: AI AGENT - Implement or mock interface call to: UpdateLedgerService

    public void executePayrollProcessor(/* Parameters mapped from Controller */) {
        log.info("Executing modernized business logic for payroll-processor");
        // TODO: [AI AGENT] Implement extracted business rules here.
    }
}"""

# ==============================================================================
# THE TESTS
# ==============================================================================


def test_service_skeleton_dag_resolver():
    """
    Feeds a mock IR state with unresolved COBOL calls into the Service Forge.
    Verifies that the Python script correctly translates COBOL hyphens into
    Java CamelCase so the downstream AI Agent knows exactly what to auto-wire.
    """
    # 1. Generate the code using the mock IR
    generated_java = generate_service_skeleton(MOCK_IR_STATE, "com.gitgalaxy.modernized")

    # 2. Compare against the Golden Image
    assert generated_java.strip() == GOLDEN_SERVICE_SKELETON.strip(), (
        "Service Forge drifted from the Golden Image! Did the CamelCase/Hyphen parsing break?"
    )
