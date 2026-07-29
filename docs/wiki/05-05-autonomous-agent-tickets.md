# Autonomous Agent Task Tickets

> **File Reference:** [`gitgalaxy/tools/cobol_to_java/cobol_to_java_agent_forge.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/tools/cobol_to_java/cobol_to_java_agent_forge.py)

> **Architecture: Structured LLM Task Orchestration & Prompt Bounding**
>
> **Summary:** To complete the Java modernization loop, generated `@Service` skeletons must be populated with translated business rules. Rather than feeding entire legacy source files directly to an LLM (which can cause hallucinated dependencies and missing state), `cobol_to_java_agent_forge.py` packages pre-sliced business logic into structured JSON Task Tickets (`{prog_id}_java_service_job.json`) designed for autonomous code generation agents.

## JSON Task Ticket Schema

The Task Generator constructs a bounded JSON ticket (`generate_java_agent_ticket`) that restricts AI code generation to a defined context:

* **Isolated Business Rules:** Contains only localized logic statements extracted by static analysis. The agent is provided only with the specific paragraphs required to implement logic for the target variable.
* **External Dependencies:** Explicitly enumerates unresolved subroutine calls (`unresolved_calls`) identified during static analysis.
* **Architectural Warnings:** Injects audit flags and edge-case warnings (such as system limit overrides or dynamic GOTOs) directly into the ticket context window, requiring the agent to address legacy edge cases explicitly.

## Anti-Hallucination Constraints & Prompt Bounding

The ticket embedded `system_prompt` enforces strict generation rules:
1. **No External System Synthesis:** The agent is explicitly prohibited from creating unlisted external systems or unmapped database tables.
2. **Interface Contract Enforcement:** For unresolved external dependencies, the agent is instructed to generate interface calls against Spring-managed dependencies rather than writing arbitrary implementations.
3. **Structured Response Format:** The agent must return its response as a structured JSON payload containing a `diagnosis` explanation string and a `java_code` string, enabling automated pipeline validation and insertion into generated `@Service` classes.

---

### Powered by GitGalaxy

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), a static analysis and knowledge graph engine for software modernization.

* [Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy) for code, tools, and updates.
* [Visualize your repository](https://gitgalaxy.io/) using our interactive WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**

