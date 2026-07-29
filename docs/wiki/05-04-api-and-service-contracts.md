# API & Service Contracts

> **File Reference:** [`gitgalaxy/tools/cobol_to_java/cobol_to_java_api_contract_forge.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/tools/cobol_to_java/cobol_to_java_api_contract_forge.py)

> **Architecture: Dual-Paradigm Execution & Dependency Injection Auto-Wiring**
>
> **Summary:** The API Contract Generator (`cobol_to_java_api_contract_forge.py`) and Service Generator (`cobol_to_java_service_forge.py`) translate structural static analysis into modern Spring Boot `@RestController` endpoints and `@Service` components. They automatically detect execution paradigms (Batch vs. Transactional) and establish dependency injection wiring.

## Execution Paradigm Detection

Legacy COBOL applications execute primarily as CICS transactional modules or JCL batch jobs. The API generator inspects file allocation requests and CICS indicators in the IR state to determine the appropriate REST interface pattern:

* **Transactional Paradigm:** When a module processes structured in-memory data structures without physical dataset requests, the generator produces a JSON POST endpoint (`/api/v1/{module}/execute`) accepting `@RequestBody` DTO objects.
* **Batch Paradigm:** When dataset file bindings (`DD` allocations) are present, the generator produces a multipart POST endpoint (`/api/v1/{module}/execute-batch`) accepting `@RequestParam MultipartFile` arguments mapped to legacy dataset definitions.

## Service Layer Auto-Wiring

The Service Generator constructs the `@Service` business logic skeleton (`{ModuleName}Service.java`) and maps cross-module dependencies:
* **Resolved Subroutines:** References to external COBOL subroutines found in the repository scan are injected into the service constructor via Lombok `@RequiredArgsConstructor` for Spring Dependency Injection.
* **Unresolved Subroutines:** When dynamic or external module calls cannot be statically resolved, the generator injects inline interface stubs (`TODO: IMPLEMENT SUBROUTINE CALL`) to preserve compilability.

## Mock Service Generation

To prevent missing subroutines from breaking Spring Application Context initialization on startup, the controller (`cobol_to_java_controller.py`) generates mock `@Service` classes for unresolved calls. These mock services intercept calls, log diagnostic warnings (`"Mock Service invoked. Implementation missing."`), and safely return execution to the caller.

---

### Powered by GitGalaxy

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), a static analysis and knowledge graph engine for software modernization.

* [Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy) for code, tools, and updates.
* [Visualize your repository](https://gitgalaxy.io/) using our interactive WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**

