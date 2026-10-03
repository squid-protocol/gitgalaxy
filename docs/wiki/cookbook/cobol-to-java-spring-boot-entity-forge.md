# Cookbook: Spring Boot Entity Forge via Deterministic RAG Pipelines

## 1. The Memory Paradigm Crisis in Legacy Modernization

Migrating the business logic of a legacy COBOL application is secondary to the challenge of migrating its memory model. COBOL utilizes a contiguous, flat memory architecture where variables act as positional byte-maps. Java, conversely, relies on heap-allocated, strongly typed object references. 

When modernization pipelines rely on Large Language Models (LLMs) to bridge this paradigm gap, they encounter immediate structural collapse. Probabilistic engines cannot reliably translate legacy memory overlays (`REDEFINES`), fixed-length contiguous arrays (`OCCURS`), or implied decimal precisions (`PIC 9(5)V99`) into valid Object-Relational Mapping (ORM) targets. An LLM will typically flatten an `OCCURS` clause into a concatenated string or map a `REDEFINES` block into redundant database columns, permanently destroying data normalization.

To safely transition from mainframe memory to cloud-native persistence, the data layer must be scaffolded mathematically. 

The GitGalaxy ecosystem resolves this using a deterministic function-level knowledge graph. The blAST (Bypassing LLMs and ASTs) engine extracts the absolute structural constraints of the COBOL `DATA DIVISION` into a standardized JSON schema. In a Retrieval-Augmented Generation (RAG) pipeline, the Java Spring Entity Forge consumes this schema to automatically generate production-ready JPA (Java Persistence API) Entities. This enforces strict data integrity before the LLM is permitted to translate the procedural business logic.

## 2. The Java Spring Entity Forge

The `cobol_to_java_spring_forge.py` script operates as the Object-Relational persistence layer within the modernization ecosystem. 

Rather than relying on semantic translation, the Forge programmatically maps exact COBOL byte allocations to Spring Boot JPA annotations. It guarantees that the resulting Java class perfectly mirrors the constraints of the generated PostgreSQL Data Definition Language (DDL). Furthermore, it proactively sanitizes legacy variable names to prevent compilation failures caused by collisions with Java reserved keywords or invalid syntax structures.

### 2.1 Information Flow & Processing Pipeline

The pipeline executes a deterministic translation of flat-file schema definitions into a relational Java object model.

| Processing Stage | Deterministic Operation | Architectural Purpose | Legacy Modernization Value |
| :--- | :--- | :--- | :--- |
| **Precision Mapping** | `PIC` Parsing | Translates legacy alphanumeric and implied decimal constraints into `@Column(length=X, precision=Y, scale=Z)` annotations. | Prevents silent data truncation and rounding errors when migrating highly precise financial mainframe workloads to the JVM. |
| **Array Normalization** | `OCCURS` Translation | Detects repeating memory blocks and scaffolds them as `@ElementCollection` Lists with explicit `@CollectionTable` joins. | Normalizes flat legacy arrays into strictly relational database structures without requiring manual schema redesign. |
| **Memory Overlay Detection** | `REDEFINES` Isolation | Flags variables that share the same physical memory block as another variable and decorates them with `@Transient`. | Prevents JPA from attempting to persist redundant or conflicting columns to the database, maintaining single-source-of-truth integrity. |
| **Lexical Sanitization** | Keyword Collision Check | Evaluates generated variable names against a comprehensive set of Java reserved words and primitive types, appending safe suffixes where necessary. | Ensures the auto-generated code compiles immediately, eliminating the manual friction of fixing syntax errors in thousands of migrated files. |

## 3. Notable Structures & Execution Logic

The script operates on two primary analytical components to ensure absolute structural alignment:

### Structural Constraint Parsing (parse_pic_clause)
This function acts as the constraint resolver. It evaluates the raw COBOL descriptions embedded in the intermediate JSON schema. By executing deterministic regular expressions against the legacy `PIC` clauses, it mathematically separates the total precision from the fractional scale (e.g., parsing `9(7)V99` into `precision=9, scale=2`). It actively hunts for `OCCURS` and `REDEFINES` directives, packaging these physical memory instructions into a standardized constraint dictionary for the downstream generator.

### Entity Orchestration (generate_java_entity)
This function acts as the bytecode architect. It iterates through the normalized schema properties, mapping base JSON types to strict Java wrappers (`Long`, `Integer`, `BigDecimal`). It implements rigorous guardrails: replacing hyphens with underscores, enforcing camelCase conventions, and prepending a character (`v`) if a legacy variable name begins with an integer. Finally, it constructs the `@Entity` file, injecting Lombok annotations (`@Data`, `@NoArgsConstructor`) to minimize boilerplate, and assigns a primary surrogate key (`sys_id`) to decouple the object from legacy operational identifiers.

## 4. Execution Interface

The forge is designed to run in a headless CI/CD environment, consuming the output of the Cloud Schema Forge before the business logic is ported agents.

```bash
# Execute the forge against a deterministic GitGalaxy schema dump
python3 cobol_to_java_spring_forge.py ./schemas/CUSTOMER_schema.json --pkg com.enterprise.modernized
```

## 5. Recommended Next Steps (Refactoring for Enterprise Scale)

To mature this script for high-throughput, enterprise-wide database modernization, the following architectural enhancements should be prioritized:

1. **Composite Key Generation (VSAM to JPA):** Mainframe VSAM files frequently rely on multi-column composite keys for indexing. The Forge should be extended to read index constraints from the GitGalaxy graph and automatically generate corresponding `@Embeddable` and `@EmbeddedId` classes to maintain native database indexing strategies.
2. **Custom Type Converter Injection:** Legacy systems often store dates as packed integers (e.g., `CYYMMDD`) rather than native timestamps. The Forge should identify date-oriented naming conventions or schema tags and automatically scaffold JPA `@Convert` annotations and `AttributeConverter` implementations to parse these values into `java.time.LocalDate` objects seamlessly on read/write.
3. **Builder Pattern Scaffolding:** While `@Data` provides standard getters and setters, enterprise microservices benefit from immutable object creation. Injecting the Lombok `@Builder` annotation into the class definition will provide the downstream LLM agents with a cleaner, thread-safe API for instantiating complex legacy records.

- - - -
this was accomplished by the blAST engine - - - -🌌 Powered by the blAST Engine
## Where the business logic comes from

This forge generates the entities the ports read and write. Each program's PROCEDURE DIVISION is then ported in one of two ways: by the deterministic translator (no model; every statement becomes a call into a runtime that follows COBOL's rules byte for byte, and anything it cannot translate is a named `Hole`), or by a person or model from a porting ticket. Either way, the port is proven against the original COBOL by the equivalence harness (GnuCOBOL, a CICS model and a real Db2) before a person approves it. As of 2026-10-02, 48 programs from CardDemo, CBSA and GenApp are proven as deterministic ports. See [Proven COBOL-to-Java Ports](../05-19-proven-cobol-to-java-ports.md) for what is proven, how, and the limits.

This documentation is part of the GitGalaxy Ecosystem, an AST-free, LLM-free heuristic knowledge graph engine.

🪐 Explore the GitHub Repository for code, tools, and updates.
🔭 Visualize your own repository at GitGalaxy.io using our interactive 3D WebGPU dashboard.

---

**[⬅️ Back to Master Index](../index.md)**
