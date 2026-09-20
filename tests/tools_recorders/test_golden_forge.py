# Import your Forge generators
from gitgalaxy.tools.cobol_to_java.cobol_to_java_api_contract_forge import (
    generate_rest_controller,
)
from gitgalaxy.tools.cobol_to_java.cobol_to_java_spring_forge import (
    generate_java_dto,
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

# #3233: a DFHCOMMAREA is a transient CICS communication area, not a table, so it
# becomes a plain DTO (no @Entity/@Table/@Id/@Column, no jakarta.persistence import).
MOCK_DFHCOMMAREA_STATE = {
    "title": "DFHCOMMAREA",
    "properties": {
        "WS-CUSTNO": {"type": "number", "description": "PIC 9(10)"},
        "WS-ACCTYPE": {"type": "string", "description": "PIC X(8)"},
        "WS-BALANCE": {"type": "decimal", "description": "PIC S9(10)V99"},
        "WS-FILLER": {"type": "string", "description": "PIC X(8) REDEFINES WS-ACCTYPE"},
        "WS-HISTORY": {"type": "number", "description": "PIC 9(6) OCCURS 12"},
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

GOLDEN_DTO = """package com.gitgalaxy.modernized.dto;

import lombok.Data;
import lombok.NoArgsConstructor;
import java.math.BigDecimal;
import java.util.List;

@Data
@NoArgsConstructor
public class Bnk1cacDfhcommareaDto {

    private BigDecimal wsCustno;

    private String wsAcctype;

    private BigDecimal wsBalance;

    // ⚠️ REDEFINES ALIAS: Maps to ws-acctype in memory
    private String wsFiller;

    // ⚠️ ARRAY: OCCURS 12 TIMES
    private List<BigDecimal> wsHistory;

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


def test_spring_dto_golden_image():
    """
    #3233: a DFHCOMMAREA schema is a transient communication area, so the forge
    emits a plain Lombok POJO DTO (no @Entity/@Table/@Id/@Column, no jakarta
    import) in the .dto package. Verifies the DTO matches its Golden Image and,
    explicitly, that no JPA persistence markers leaked in.
    """
    # 1. Generate the DTO using the mock DFHCOMMAREA schema
    generated_java = generate_java_dto(MOCK_DFHCOMMAREA_STATE, "com.gitgalaxy.modernized", unit_key="BNK1CAC")

    # 2. Compare against the Golden Image
    assert " ".join(generated_java.split()) == " ".join(GOLDEN_DTO.split()), (
        "Spring DTO generation drifted from the Golden Image! Check the transient-record (#3233) path."
    )

    # 3. A DTO must carry no persistence mapping.
    for marker in ("@Entity", "@Table", "@Id", "@Column", "jakarta.persistence"):
        assert marker not in generated_java, f"DTO unexpectedly contains JPA marker {marker!r}"
