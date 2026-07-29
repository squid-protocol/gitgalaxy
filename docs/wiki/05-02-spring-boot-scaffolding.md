# Spring Boot Scaffolding Architecture

> **File Reference:** [`gitgalaxy/cobol_to_java_controller.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/cobol_to_java_controller.py)

> **Architecture: Automated Build Systems & Legacy Data Decoders**
>
> **Summary:** The Java Translation Controller (`cobol_to_java_controller.py`) orchestrates the cloud migration pathway. It ingests JSON Intermediate Representation (IR) dumps produced during static analysis and generates a complete, compilable Spring Boot microservice project structure. This automates the transition from legacy procedural execution to modern Object-Oriented and RESTful paradigms.

## Build System Scaffolding

The orchestrator automatically generates the foundational project structure and configuration files required to compile and boot the Spring Boot application:

* **`pom.xml`**: Configures Maven dependencies for Spring Boot Starter Web, Spring Data JPA, Spring Batch, Lombok, and PostgreSQL, aligned with Java 17 standards.
* **`application.yml`**: Automatically configures database connections, Hibernate schema DDL properties (`update`), and logging parameters.
* **Application Entry Point**: Generates the standard `@SpringBootApplication` main class (`{ArtifactName}Application.java`).
* **Header & Compliance Injection**: Scans for a corporate header configuration file (`header.txt`) and wraps legal headers into Java block comments placed at the top of every generated source file.

## EBCDIC & COMP-3 Data Decoder Utility

Legacy mainframes store data in EBCDIC character encoding and Packed Decimal (COMP-3) binary formats, whereas modern cloud infrastructure relies on UTF-8 text and standard numerical primitives (`BigDecimal`). To parse binary legacy payloads safely within Java applications, the controller generates `EbcdicDecoderUtil.java`.

### Hex-Boundary & Nibble Validation
The decoder unpacks COMP-3 byte arrays into Java `BigDecimal` objects:
* **High Nibble Verification:** Verifies that the high nibble of each byte represents a valid numeric character (0–9).
* **Sign Nibble Verification:** Validates that the final low nibble represents a valid sign identifier (`A`–`F`).
* **Corrupt Data Handling:** If malformed or corrupted bytes are encountered, the utility intercepts the error, logs a hex-dump diagnostic message, and safely returns `BigDecimal.ZERO` to prevent application crashes.

---

### Powered by GitGalaxy

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), a static analysis and knowledge graph engine for software modernization.

* [Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy) for code, tools, and updates.
* [Visualize your repository](https://gitgalaxy.io/) using our interactive WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**

