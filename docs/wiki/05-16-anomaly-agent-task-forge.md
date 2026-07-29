# Autonomous Agent Remediation Task Generator

> **File Reference:** [gitgalaxy/tools/cobol_to_cobol/cobol_agent_task_forge.py](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/tools/cobol_to_cobol/cobol_agent_task_forge.py)

## Engineering Summary
The Autonomous Agent Remediation Task Generator orchestrates LLM-based refactoring by packaging static analysis results and local code context into bounded execution constraints. It solves the problem of AI hallucination and context window exhaustion when attempting to refactor legacy monoliths in a single pass. This system acts as a dispatch router in GitGalaxy, transforming raw structural violation data into structured tasks for automated agent workers. It is known internally as the Anomaly Agent Task Forge.

## Purpose
To convert static analysis anomaly flags and intermediate representation (IR) lineage metadata into structured JSON task tickets that provide safe, constrained execution boundaries for automated LLM agents tasked with resolving code anomalies.

## Problem Being Solved
Passing unconstrained legacy monoliths to LLM agents frequently causes context window exhaustion and leads models to hallucinate dependencies. Agents need isolated, well-defined boundaries to safely modify code without mutating critical business logic.

## Design
### Contextual Lineage Aggregation
The task generator bounds agent scope by gathering local context before creating a job ticket:
* **File-Based Anomaly Grouping:** Groups detected structural violations (`architectural_anomalies`) by target source file.
* **Lineage & Dependency Extraction:** Queries intermediate representation files (`*_ir.json`) to pull pre-resolved dependency lineage (required input files, produced output files, and unresolved external subroutine calls).

### JSON Job Ticket Specification
The `generate_agent_ticket` function compiles a JSON contract (`{prog_id}_agent_job.json`) placed into `06_ai_agent_jobs/`:
* **`job_id`:** Unique task identifier (e.g., `PROGNAME_REMEDIATION`).
* **`status`:** Initial ticket state (`PENDING`).
* **`task_type`:** Standardized action category (`STRUCTURAL_ANOMALY_RESOLUTION`).
* **`target_file`:** Absolute file system path to the target source payload.
* **`context`:** Contains arrays for `detected_anomalies`, `inputs_required`, `outputs_produced`, and `external_calls`.

### Prompt System & Output Constraints
To ensure LLM dispatchers return deterministic code patches without mutating business logic, the job ticket embeds a strict system prompt:
1. **Role Instruction:** Directs the model to act as a legacy systems architect.
2. **Logic Preservation Constraint:** Commands that the model must exclusively address listed structural anomalies and must not alter underlying business logic.
3. **Structured JSON Output:** Requires the agent to return its solution as a JSON payload containing `diagnosis` and `patched_code` keys, allowing automated integration tools to consume and apply patches without manual intervention.

## Pipeline Integration
**Inputs:** Static analysis structural anomaly flags (`architectural_anomalies`), Intermediate Representation files (`*_ir.json`).
**Outputs:** JSON job tickets (`{prog_id}_agent_job.json`) containing system prompts, isolated code blocks, and lineage metadata.
**Dependencies:** Requires upstream generation of structural anomaly reports and pre-resolved IR dependency graphs.

**Flow:**
Structural Anomalies + IR Dependencies -> Anomaly Agent Task Forge -> JSON Agent Job Tickets

## Tradeoffs
* **JSON Payloads vs Direct Prompting:** By wrapping instructions and code within structured JSON constraints, the system ensures deterministic agent responses for automated CI/CD patch application, rejecting direct natural language interactions that cannot be programmatically consumed.
* **Per-File Boundary vs Cross-File Refactoring:** The generator strictly isolates scope per-file. This sacrifices the ability for the agent to perform sweeping architectural redesigns across multiple modules in exchange for safely bounding changes and preventing context window exhaustion.

## Limitations
* Constrained to localized file-level remediation tasks.
* Model output heavily depends on the precision of the upstream dependency graph provided in the IR context.

## Performance Notes
Agent ticket generation performs efficiently since all heavy static analysis and dependency resolution are pushed upstream, keeping the packaging step $O(1)$ per flagged anomaly.

## Future Work
* Implementation of verification loops that automatically apply the returned patch to an isolated container, run tests, and prompt the agent again upon failure.
* Expansion of tasks beyond `STRUCTURAL_ANOMALY_RESOLUTION` to include variable modernization and automated documentation generation.

## Related Components
* Intermediate Representation Generator
* System Limits Reporter

