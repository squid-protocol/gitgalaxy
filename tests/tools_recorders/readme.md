### Tools, Recorders & Code Forges Test Suite

This directory contains the validation suite for GitGalaxy's output-generation layer — the
stage that turns extracted structural data into 3D visualization payloads, generated Java
services, and AI-agent remediation tickets.

Structural extraction is only half the pipeline. If the recorder leaks memory building the 3D
visualization payload, or a code generator lets an LLM fill in a legacy boundary it shouldn't,
the output stops being trustworthy regardless of how correct the extraction was. This suite
validates that GitGalaxy translates extracted data into WebGL arrays, Java microservices, and
bounded AI remediation tickets without losing or corrupting it along the way.

---

### Running This Suite

These tests cover memory-eviction behavior, batch-execution timeout handling, and byte-for-byte
comparison against golden output fixtures. To run this suite in isolation:

```bash
python -m pytest tests/tools_recorders/ -v
```

---

### Test Index

#### 1. Telemetry & Hardware Constraints
* **`test_gpu_recorder.py`** — Validates the [GPU Recorder](../../docs/wiki/02-13-gpu-recorder.md). Proves the engine correctly performs the memory layout pivot (array-of-structs to struct-of-arrays) required for WebGL 3D rendering, and specifically verifies that Python references are actively popped from memory during that pivot (Stage 3.3) to prevent out-of-memory crashes on large repositories.
* **`test_batch_test_harness.py`** — Validates the [Batch Test Harness](../../docs/wiki/05-06-batch-test-harness.md). Proves the multi-repository batch orchestrator survives hostile environments — catching fatal Maven compilation errors and triggering a 5-minute kill-switch on frozen external subprocesses without crashing the master loop.

#### 2. Legacy Scaffolding Forges (Golden Images)
These tests check the translation layer's output byte-for-byte against known-good golden
fixtures.
* **`test_decoder_forge.py`** — Validates the [ETL Unpacker](../../docs/wiki/05-09-etl-unpacker.md). Proves the auto-generated Java utility correctly unpacks legacy EBCDIC arrays and validates hex boundaries on `COMP-3` (packed decimal) data, so malformed mainframe data fails cleanly instead of crashing the generated code at runtime.
* **`test_golden_forge.py`** — Validates the [Spring Boot Scaffolding](../../docs/wiki/05-02-spring-boot-scaffolding.md). Proves GitGalaxy's intermediate-representation (IR) state and JSON schemas translate deterministically into valid, production-ready Spring Boot `@RestController` interfaces and JPA `@Entity` classes (including translated `PIC`-clause database constraints).
* **`test_service_forge.py`** — Validates the [API & Service Contracts](../../docs/wiki/05-04-api-and-service-contracts.md). Proves the service-skeleton DAG resolver correctly translates legacy COBOL hyphenated names into Java camelCase to scaffold autowired `@Service` classes, and explicitly marks scaffolding boundaries for unresolved external calls rather than guessing at them.

#### 3. Autonomous Agent Scaffolding
* **`test_agent_forge.py`** — Validates the [Autonomous Agent Tickets](../../docs/wiki/05-05-autonomous-agent-tickets.md). Proves the ticket forge extracts real architectural constraints (e.g. external database dependencies) and legacy caveats (e.g. EBCDIC encoding warnings) from the IR state and includes them in the generated JSON ticket, so the downstream AI agent isn't working from an incomplete picture.
