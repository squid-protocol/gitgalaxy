# Autonomous Agent Remediation Task Generator

> **File Reference:** [gitgalaxy/tools/cobol_to_cobol/cobol_agent_task_forge.py](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/tools/cobol_to_cobol/cobol_agent_task_forge.py)
>
> **Architecture: Structured Remediation Ticket & Boundary Generation**
>
> **Summary:** The Autonomous Agent Task Generator converts static analysis anomaly flags and intermediate representation (IR) lineage metadata into structured JSON task tickets. These tickets provide constrained execution context for automated LLM agents tasked with resolving code anomalies.

## Contextual Lineage Aggregation

Passing unconstrained monoliths to LLM agents can cause context window exhaustion and hallucinated dependencies. The task generator bounds agent scope by gathering local context before creating a job ticket:

* **File-Based Anomaly Grouping:** Groups detected structural violations (`architectural_anomalies`) by target source file.
* **Lineage & Dependency Extraction:** Queries intermediate representation files (`*_ir.json`) to pull pre-resolved dependency lineage (required input files, produced output files, and unresolved external subroutine calls).

## JSON Job Ticket Specification

The `generate_agent_ticket` function compiles a JSON contract (`{prog_id}_agent_job.json`) placed into `06_ai_agent_jobs/`:

* **`job_id`:** Unique task identifier (e.g., `PROGNAME_REMEDIATION`).
* **`status`:** Initial ticket state (`PENDING`).
* **`task_type`:** Standardized action category (`STRUCTURAL_ANOMALY_RESOLUTION`).
* **`target_file`:** Absolute file system path to the target source payload.
* **`context`:** Contains arrays for `detected_anomalies`, `inputs_required`, `outputs_produced`, and `external_calls`.

## Prompt System & Output Constraints

To ensure LLM dispatchers return deterministic code patches without mutating business logic, the job ticket embeds a strict system prompt:

1. **Role Instruction:** Directs the model to act as a legacy systems architect.
2. **Logic Preservation Constraint:** Command that the model must exclusively address listed structural anomalies and must not alter underlying business logic.
3. **Structured JSON Output:** Requires the agent to return its solution as a JSON payload containing `diagnosis` and `patched_code` keys, allowing automated integration tools to consume and apply patches without manual intervention.

<br><br>

---

### Ecosystem Integration

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), a static analysis and heuristic dependency mapping engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for code, tools, and updates.
* **[Visualize your repository at GitGalaxy.io](https://gitgalaxy.io/)** using the interactive dashboard.

---

**[⬅️ Back to Master Index](index.md)**

