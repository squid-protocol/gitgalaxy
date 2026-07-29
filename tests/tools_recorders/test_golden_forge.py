# Import your Forge generators
from gitgalaxy.tools.cobol_to_java.cobol_to_java_api_contract_forge import (
    generate_rest_controller,
)
from gitgalaxy.tools.cobol_to_java.cobol_to_java_spring_forge import (
    generate_java_entity,
)

# ==============================================================================
# INLINE FIXTURES (The "Known Good" Inputs)
# ==============================================================================
MOCK_IR_STATE = {
    "metadata": {"file_name": "process-payroll.cbl"},
    "analysis": {
        "base_intent": {"files_requested": [], "is_cics": False},
        "lineage": {
            "inputs": ["EMPLOYEE-RECORD", "TIMECARD-DATA"],
            "outputs": ["PAYROLL-RECEIPT"],
        },
    },
}

MOCK_SCHEMA_STATE = {
    "title": "EMPLOYEE_TABLE",
    "properties": {
        "EMP-ID": {"type": "integer", "description": "PIC 9(6)"},
        "EMP-NAME": {"type": "string", "description": "PIC X(50)"},
        "SALARY": {"type": "decimal", "description": "PIC 9(5)V99"},
    },
}

# ==============================================================================
# GOLDEN IMAGES (The "Perfect" Expected Outputs)
# ==============================================================================
GOLDEN_CONTROLLER = """package com.gitgalaxy.modernized.controller;

import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import lombok.RequiredArgsConstructor;
import com.gitgalaxy.modernized.service.ProcessPayrollService;

@RestController
@RequestMapping("/api/v1/process-payroll")
@RequiredArgsConstructor
public class ProcessPayrollController {

    private final ProcessPayrollService processPayrollService;

    @PostMapping("/execute")
    public ResponseEntity<?> executeProcessPayroll(
        @RequestBody EmployeeRecordDTO employeeRecordData,
        @RequestBody TimecardDataDTO timecardDataData
    ) {
        // TRANSACTIONAL PARADIGM DETECTED
        processPayrollService.executeProcessPayroll(/* pass DTOs here */);
        // Expected Outputs: PAYROLL-RECEIPT
        return ResponseEntity.ok().build();
    }
}"""

GOLDEN_ENTITY = """package com.gitgalaxy.modernized.entity;

import lombok.Data;
import lombok.NoArgsConstructor;
import jakarta.persistence.*;
import java.math.BigDecimal;

@Data
@NoArgsConstructor
@Entity
@Table(name = "EMPLOYEE_TABLE")
public class EmployeeTable {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "sys_id")
    private Long sysId;

    @Column(name = "EMP-ID")
    private Integer empId;

    @Column(name = "EMP-NAME", length = 50)
    private String empName;

    @Column(name = "SALARY", precision = 7, scale = 2)
    private BigDecimal salary;

}"""

# ==============================================================================
# THE TESTS
# ==============================================================================


def test_api_contract_golden_image():
    """
    Feeds a known IR state into the API Contract Forge and verifies the
    resulting Java code matches our Golden Image byte-for-byte.
    """
    # 1. Generate the code using the mock IR
    generated_java = generate_rest_controller(MOCK_IR_STATE, "com.gitgalaxy.modernized")

    # 2. Compare against the Golden Image
    # We collapse whitespace to prevent OS line-ending differences (CRLF vs LF) from failing the test
    assert " ".join(generated_java.split()) == " ".join(GOLDEN_CONTROLLER.split()), (
        "API Contract generation drifted from the Golden Image! Did someone alter the string formatting?"
    )


def test_spring_entity_golden_image():
    """
    Feeds a known Schema state into the Spring Entity Forge and verifies the
    resulting JPA Entity (with PIC constraints) matches our Golden Image.
    """
    # 1. Generate the entity using the mock schema
    generated_java = generate_java_entity(MOCK_SCHEMA_STATE, "com.gitgalaxy.modernized")

    # 2. Compare against the Golden Image
    assert " ".join(generated_java.split()) == " ".join(GOLDEN_ENTITY.split()), (
        "Spring Entity generation drifted from the Golden Image! Check PIC clause parsing logic."
    )
