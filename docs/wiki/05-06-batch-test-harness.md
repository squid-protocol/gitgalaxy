# Batch Test Harness

> **File Reference:** [`gitgalaxy/tools/cobol_to_java/batch_test_harness.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/tools/cobol_to_java/batch_test_harness.py)

> **Architecture: Automated Pipeline Validation & Maven Build Testing**
>
> **Summary:** The Batch Test Harness (`batch_test_harness.py`) is an automated test validation tool designed to stress-test the modernization pipeline across multiple legacy repositories. It verifies that static analysis extraction and Java code generation produce 100% compilable Spring Boot applications across an entire software repository corpus.

## Three-Phase Validation Pipeline

The test harness iterates through target legacy repositories, executing a three-stage validation sequence for each codebase:

1. **Structural Extraction Phase:** Runs `cobol_refractor_controller.py` to parse legacy source files and generate JSON Intermediate Representation (IR) state dumps.
2. **Spring Boot Scaffolding Phase:** Runs `cobol_to_java_controller.py` to generate Java JPA entities, REST controllers, mock services, and Maven build configurations (`pom.xml`).
3. **Compilation Verification Phase:** Spawns a localized Maven subprocess (`mvn clean compile`) to attempt a clean compilation of the generated Java codebase.

## Environment Isolation & Process Controls

To ensure consistent execution across different CI/CD runners and environments:
* **JDK Path Standardization:** Clones host environment variables and forces `JAVA_HOME` to Java 17 OpenJDK (`/usr/lib/jvm/java-17-openjdk-amd64`) for deterministic compilation.
* **Process Timeout Enforcement:** Wraps subprocess executions with a 5-minute timeout (`timeout=300`) to terminate hung processes or infinite regex loops cleanly, logging failure states without blocking subsequent batch runs.

## Test Logging & Audit Reporting

The harness records detailed telemetry to support CI/CD pipeline auditing:
* **Batch Summary:** Tracks overall success and failure counts (`passed`, `failed_refractor`, `failed_java_forge`, `failed_maven`).
* **Error Log Capture:** Captures stdout and stderr for any failed step into dedicated log files under `batch_test_reports/{repo}_error_{timestamp}.log`, allowing developers to inspect Maven compilation logs or static analysis errors directly.

---

### Powered by GitGalaxy

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), a static analysis and knowledge graph engine for software modernization.

* [Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy) for code, tools, and updates.
* [Visualize your repository](https://gitgalaxy.io/) using our interactive WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**

