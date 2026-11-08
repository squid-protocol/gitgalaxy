---
description: "When translating legacy COBOL monoliths into modern Java microservices, translating the procedural business logic is only half of the architectural..."
---
# Cookbook: Mainframe Data Serialization Forge via Deterministic RAG Pipelines

## 1. The Mainframe Serialization Crisis in Legacy Modernization

When translating legacy COBOL monoliths into modern Java microservices, translating the procedural business logic is only half of the architectural equation. Mainframes serialize physical data using fundamental computing paradigms that do not exist natively within the Java Virtual Machine (JVM). Specifically, strings are encoded in EBCDIC (not ASCII or UTF-8), and numeric variables are frequently compressed into Packed Decimals (COMP-3) to conserve disk space.

If a modernization pipeline relies purely on Large Language Models (LLMs) to rewrite the data ingestion layer, the result is almost always catastrophic. LLMs routinely hallucinate standard `Integer.parseInt()` or native String constructors for mainframe payloads. When the compiled Java application attempts to process a production mainframe dataset, it immediately throws memory overflow exceptions or silently corrupts the data state due to byte-misalignment.

To solve this, the GitGalaxy ecosystem enforces a deterministic physical boundary. Using the blAST (Bypassing LLMs and ASTs) engine, the knowledge graph calculates the exact byte-lengths and types of the legacy data division. In a Retrieval-Augmented Generation (RAG) pipeline, this deterministic state needs a decoding utility to bridge the physical memory layer into the JVM.

## 2. The Java Spring EBCDIC & COMP-3 Decoder Forge

The `cobol_to_java_decoder_forge.py` script is a structural spoke within the GitGalaxy pipeline. Rather than expecting an LLM to reliably generate complex bitwise shift operators, this script deterministically scaffolds a production-ready Java utility class (`EbcdicDecoderUtil`). 

This utility acts as the physical translation layer for the modernized Spring Boot application. It allows the ported business logic to ingest raw mainframe byte arrays, unpacking legacy COMP-3 and EBCDIC structures into standard Java `BigDecimal` and `String` objects, and failing by name on invalid packed data.

### 2.1 Information Flow & Processing Pipeline

The generated Java artifact executes a strict, bitwise deterministic extraction to convert physical mainframe storage into cloud-native JVM objects.

| Processing Stage | Deterministic Operation | Architectural Purpose | Legacy Modernization Value |
| :--- | :--- | :--- | :--- |
| **Code Page Translation** | Code-page Charset Decoding (`data.code_page`, default `IBM037`) | Translates 8-bit IBM EBCDIC characters into native Java UTF-8 strings. | Eliminates silent data corruption caused by ASCII-biased native Java decoders handling legacy text payloads. |
| **Nibble Extraction** | Bitwise Shifts (`>>> 4`, `& 0x0F`) | Isolates the high and low 4-bit nibbles from a single compressed byte. | Rehydrates the original decimal values from the dense COMP-3 physical storage architecture. |
| **Sign Evaluation** | Hexadecimal Boundary Checks | Evaluates the final low nibble of the byte array for specific IBM sign markers (`0x0D` or `0x0B`). | Decides whether the rehydrated `BigDecimal` carries a negative value. |
| **Precision Scaling** | `BigDecimal.movePointLeft()` | Injects the implied decimal precision extracted previously from the COBOL `V99` declarations. | Restores the exact financial precision of the mainframe application without relying on unstable floating-point math. |
| **Invalid Data** | Strict Hex-Boundary Validation | Evaluates every digit nibble to ensure it falls within `0-9` and the sign nibble within `A-F`. Throws `PackedDecimalDataException` (a `NumberFormatException`) naming the field, byte and nibble on invalid data (#3949); only an empty or null field returns `BigDecimal.ZERO`. | Mirrors the mainframe's S0C7 data exception instead of turning corrupt money into zero and carrying on. |

## 3. Notable Structures & Execution Logic

The Python script scaffolds a Java utility governed by two primary operational pillars:

### EBCDIC Decoding (decodeEbcdicString)
Mainframe text relies on specific IBM code pages. The Forge decodes with the conversion's declared code page (`data.code_page`: cp037 becomes `IBM037`, cp277 `IBM277`, cp1140 `IBM01140`), so national letters and `[ ] ! ^ |` come out as the estate wrote them. By wrapping the byte array conversion in a standard try-catch block and explicitly trimming trailing whitespace (a common artifact of fixed-length COBOL string allocation), the generated method ensures that the Spring Boot application receives sanitized, sanitized UTF-8 strings.

### COMP-3 Unpacking (unpackComp3)
This is the most critical logic block scaffolded by the Forge. Packed decimal formats store two digits per byte, utilizing the final nibble (half-byte) to store the numeric sign. The generated Java code uses bitwise operators to iterate through the payload. 

Crucially, the Forge implements defensive guardrails for dirty data. In mainframe environments, memory is frequently overridden or improperly initialized, leading to non-numeric hex values inside a COMP-3 field. The scaffolded Java method validates that every data nibble is between `0-9` and that the sign nibble is a valid hex character (`A-F`). If a nibble is invalid it throws `PackedDecimalDataException`, as the mainframe raises a data exception (S0C7) and abends the step, rather than turn corrupt data into zero (#3949).

## 4. Execution Interface

The forge has no command of its own (the module has no `__main__`). The `cobol-to-java` pipeline (`gitgalaxy/cobol_to_java_controller.py`) calls `generate_decoder_util(pkg, target.data.code_page)` and writes `EbcdicDecoderUtil.java` into the generated project, alongside the other forges (see "The forges" in the [`cobol-to-java` README](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/tools/cobol_to_java/README.md#the-forges)):

```bash
cobol-to-java /path/to/legacy_repo_gitgalaxy_clean_20260419 --pkg "com.enterprise.modernized" [--config target.yaml]
```

To call it directly from Python:

```python
from gitgalaxy.tools.cobol_to_java.cobol_to_java_decoder_forge import generate_decoder_util

java_utility_code = generate_decoder_util("com.enterprise.modernized", code_page="cp037")
```

## 5. Recommended Next Steps (Refactoring for Enterprise Scale)

To mature this specific artifact generator for high-throughput enterprise data processing, the following architectural enhancements should be implemented:

1. **Zoned Decimal Support:** The current Forge focuses exclusively on COMP-3 and EBCDIC strings. Extend the generator to scaffold decoders for standard PIC 9 numerics (Zoned Decimals) and COMP-1/COMP-2 floating points, to cover more of the mainframe data types.
2. **Configurable Endianness:** The code page already follows the conversion's `data.code_page`; mainframes on different hardware architectures (e.g., AS/400 vs z/OS) can also use alternative Endian byte-orders.
3. **High-Performance Buffer Optimization:** The current `unpackComp3` method utilizes a `StringBuilder` to parse digits before casting to a `BigDecimal`. For microservices handling multi-gigabyte batch files, this creates excessive garbage collection pressure. Refactor the generated template to construct a `BigInteger` directly via bitwise accumulation, bypassing string instantiation entirely to reduce heap allocations.

- - - -
this was accomplished by the blAST engine - - - -🌌 Powered by the blAST Engine
## Where the business logic comes from

This forge generates the decoder the rest of the project uses for mainframe bytes. The deterministic ports also carry their own runtime codec (`cobolrt`), which keeps working storage as bytes. Each program's PROCEDURE DIVISION is then ported in one of two ways: by the deterministic translator (no model; every statement becomes a call into a runtime that follows COBOL's rules byte for byte, and anything it cannot translate is a named `Hole`), or by a person or model from a porting ticket. Either way, the port is checked against the original COBOL by the equivalence harness (GnuCOBOL, GitGalaxy's CICS models and a real Db2; not z/OS) and reported by [evidence level](https://github.com/squid-protocol/gitgalaxy/blob/main/docs/language_status/definition_of_done.md), from L1 (translated whole) to L5 (surviving mutants accounted for), before a person approves it. A forge's output compiling says nothing about equivalence. Current counts are on the generated [progress page](https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/progress.md). See [Ported COBOL-to-Java programs and their evidence](../05-19-proven-cobol-to-java-ports.md) for how ports are checked, and the limits.

This documentation is part of the GitGalaxy Ecosystem, an AST-free, LLM-free heuristic knowledge graph engine.

🪐 Explore the GitHub Repository for code, tools, and updates.
🔭 Visualize your own repository at GitGalaxy.io using our interactive 3D WebGPU dashboard.

---

**[⬅️ Back to Master Index](../index.md)**
