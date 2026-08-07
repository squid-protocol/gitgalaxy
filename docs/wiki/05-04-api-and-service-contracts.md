# API & Service Contracts

> **File Reference:** [`gitgalaxy/tools/cobol_to_java/cobol_to_java_api_contract_forge.py`](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/tools/cobol_to_java/cobol_to_java_api_contract_forge.py)

## Engineering Summary
This subsystem constructs the network interfaces and dependency injection scaffolding for modernized microservices. It solves the problem of exposing legacy procedural entry points over modern HTTP protocols and wiring inter-module dependencies. It exists to provide the structural skeleton required before business logic can be injected. In GitGalaxy, this layer connects the web controllers to the underlying business services.

## Purpose
To translate structural static analysis into Spring Boot `@RestController` endpoints and `@Service` components.

## Problem Being Solved
Legacy applications run as CICS transactional modules or JCL batch jobs. These paradigms must be mapped to appropriate REST interface patterns and Spring dependency injection graphs to function in a cloud-native environment.

## Design
- **Execution Paradigm Detection**: 
  - **Transactional**: If processing in-memory data without file allocations, generates a JSON POST endpoint (`/api/v1/{module}/execute`) accepting `@RequestBody` DTOs.
  - **Batch**: If dataset file bindings (`DD` allocations) exist, generates a multipart POST endpoint (`/api/v1/{module}/execute-batch`) accepting `@RequestParam MultipartFile` arguments.
- **Service Layer Auto-Wiring**: Constructs `{ModuleName}Service.java`. External COBOL subroutines are injected via Lombok `@RequiredArgsConstructor`.
- **Mock Service Generation**: For unresolved external module calls, generates inline interface stubs (`TODO: IMPLEMENT SUBROUTINE CALL`) and mock `@Service` classes that intercept calls, log warnings, and return execution to prevent context initialization failure on startup.

## Pipeline Integration
**Inputs received:** Execution paradigms and inter-module dependency graphs from the IR.
**Outputs produced:** `@RestController` and `@Service` Java source files, Mock services.
**Dependencies:** Upstream static analysis IR; downstream business logic insertion and compilation.

```mermaid
graph TD
    A[IR Dependency Graph] --> B[API Contract Generator]
    B --> C[@RestController]
    B --> D[@Service Skeletons]
    B --> E[Mock Services]
```

## Tradeoffs
- Emitting mock services for unresolved dependencies rather than halting generation. Chosen to guarantee a compilable scaffolding state for the developer, sacrificing immediate runtime correctness for a smoother developer experience.

## Limitations
- Detection between batch and transactional paradigms relies on heuristic inspection of CICS indicators and dataset definitions, which may misclassify hybrid modules.

## Performance Notes
Analyzes the pre-computed dependency graph from the IR in $O(E)$ time, where $E$ is the number of module edges, ensuring fast generation regardless of codebase size.

## Future Work
- Integration with OpenAPI/Swagger generation for the emitted `@RestController` endpoints.

## Related Components
- `cobol_to_java_service_forge.py`
- `cobol_to_java_controller.py`
