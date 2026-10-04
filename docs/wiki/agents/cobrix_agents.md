---
description: "You are operating within `cobrix`, a specialized data source and parser that allows Apache Spark to read mainframe COBOL data files (EBCDIC/ASCII). The..."
---
# AGENTS.md: cobrix Architectural Context & Engagement Rules

## 1. System Context & Paradigm
You are operating within `cobrix`, a specialized data source and parser that allows Apache Spark to read mainframe COBOL data files (EBCDIC/ASCII). The repository is primarily composed of Scala (71.5%) and relies on generated Java code via ANTLR for parsing.
* **Architectural Paradigm:** This repository functions as a "Cluster 3" macro-species and exhibits a high Architectural Drift Z-Score of 5.548. The network topology demonstrates a completely flat Modularity (0.0) and Assortativity (0.0). This indicates a highly coupled, monolithic core without clear micro-boundaries. The parsing engine relies on a deeply interconnected set of AST (Abstract Syntax Tree) processors and Spark integration layers. Do NOT attempt to decouple this into isolated micro-services; the architecture requires tight, synchronous execution between the ANTLR parsing layer and the Spark DataFrame construction.

## 2. Architectural Guardrails (Do's and Don'ts)
* **Algorithmic Complexity Limit:** Core parsing and AST transformation routines (`process` in `CobolProcessor.scala`, `flattenSchema` in `SparkUtils.scala`, and `parseTree` in `CopybookParser.scala`) operate at extreme O(2^N) recursive time complexities. You MUST NOT introduce additional nested recursion, unbounded iterations, or heavy runtime reflection into the AST walkers, copybook parsers, or record extraction paths.
* **Orchestrator Fragility:** Central orchestrators such as `spark-cobol/src/main/scala/za/co/absa/cobrix/spark/cobol/SparkCobolProcessor.scala` (24 outbound dependencies) and `cobol-parser/src/main/scala/za/co/absa/cobrix/cobol/parser/antlr/ParserVisitor.scala` (18 outbound dependencies) are highly fragile. Any changes to data contracts, EBCDIC-to-ASCII type casting, or Spark DataFrame schemas within these files require immediate, comprehensive verification of downstream integration.
* **Avoid Dead Code Pruning:** The ANTLR-generated code (`copybookParserBaseVisitor.java` with 55 orphaned functions, `jsonBaseVisitor.java`) and binary decoders (`BinaryNumberDecoders.scala`) contain massive volumes of logic flagged as "dead code." DO NOT autonomously attempt to prune, format, or clean up these files. The parser relies on dynamic dispatch and generated visitor patterns that bypass static dependency trees.

## 3. Restricted Zones (The God Nodes)
The following files are load-bearing "God Nodes." They possess extreme cumulative risk, massive structural mass, volatile churn, or 100% isolated human ownership (Key Person Silos). 

**MANDATORY RULE:** You require explicit human permission and downstream Spark cluster testing before modifying the structural signatures, recursive AST walkers, or public APIs of these files:
* `spark-cobol/src/main/scala/za/co/absa/cobrix/spark/cobol/utils/SparkUtils.scala` (Key Person Silo - 100% isolated ownership by Ruslan Iushchenko, Massive Structural Mass: 1360.92)
* `cobol-parser/src/main/scala/za/co/absa/cobrix/cobol/parser/decoders/StringDecoders.scala` (Key Person Silo - 100% isolated ownership by Ruslan Iushchenko)
* `cobol-parser/src/main/scala/za/co/absa/cobrix/cobol/parser/antlr/ParserVisitor.scala` (Key Person Silo - 100% isolated ownership by Ruslan Iushchenko)
* `cobol-parser/src/test/scala/za/co/absa/cobrix/cobol/utils/UsingUtilsSuite.scala` (Highest Cumulative Risk: 574.51, 100% Logic Bomb Exposure)
* `cobol-parser/src/main/scala/za/co/absa/cobrix/cobol/parser/antlr/ANTLRParser.scala` (Severe Blind Bottleneck - 100% Documentation Risk)

## 4. Threat & Security Boundaries
**Status: SECURE PERIMETER (WITH PARSER CAVEATS).** Structural XGBoost Threat Intelligence audits have flagged 0 malicious artifacts and 0 Agentic RCE funnels. 

**CRITICAL WARNINGS:**
1. **Exploit Generation Surface:** Files related to ANTLR parsing (`cobol-parser/src/main/scala/za/co/absa/cobrix/cobol/parser/antlr/copybookParser.java`) and internal test utilities (`UsingUtilsSuite.scala`) possess a 100% Exposure score for Exploit Generation and Injection. Because Cobrix ingests untrusted mainframe copybooks and binary data files, you MUST ensure strict input validation and boundary checking to prevent resource exhaustion (e.g., Billion Laughs style attacks) or buffer overflows during record extraction.
2. **Supply Chain / Binary Data:** There are 2 binary anomalies identified by X-Ray (likely mainframe EBCDIC test fixtures or zipped test data, e.g., `data/test15_data/a/example.bin`). Do not alter or attempt to scan these binary blobs without explicit architectural review, as they are essential integrity tests for the parser.

## 5. Environmental Tooling (The Oracle)
Do not guess trait implementations, hallucinate Scala-to-Java interop paths, or rely on generalized Spark knowledge to determine blast radius within this 48k+ LOC codebase. 

You have access to a deterministic GitGalaxy SQLite database that maps the absolute syntactic physics of this repository. Before modifying any file listed in the **Restricted Zones**, you MUST query the database for dependency mapping. 
* To map inbound dependencies (Blast Radius), query the `function_edges` or `file_edges` tables for all callers targeting your target file.
* Do not proceed with structural modifications until the specific blast radius has been statically confirmed via the database.


---

**[⬅️ Back to Master Index](../index.md)**
