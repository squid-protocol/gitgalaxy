# The Dev Agent Firewall (AI Guardrail Engine)

> **File Reference:** [`gitgalaxy/tools/ai_guardrails/dev_agent_firewall.py`](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/tools/ai_guardrails/dev_agent_firewall.py)

The Dev Agent Firewall (`dev_agent_firewall.py`) evaluates codebase complexity and network graph metrics to determine safety boundaries for autonomous AI coding agents (such as Cursor, Claude, or Devin). Rather than enforcing syntax style rules, the firewall analyzes token mass, algorithmic complexity, graph topology, and documentation density to identify modules where autonomous code edits present high statistical probabilities of context window degradation, API hallucinations, or silent regressions.

---

## Token Density & Architectural Guardrails

The firewall scans file telemetry, risk vectors, and dependency graph metrics to evaluate compatibility with LLM context windows and reasoning capacities. It enforces four primary safety guardrails:

### 1. Context Window Exhaustion (`is_agentic_black_hole`)
Flags files exhibiting massive token footprints (`token_mass > 8000`) combined with severe algorithmic complexity ($O(N^3)$ or worse).
* **Engineering Risk:** Modifying these files inside an AI agent session consumes context window allocations, degrading LLM reasoning and leading to code truncation or structural omissions during refactoring.

### 2. Human-In-The-Loop Approval Gate (`requires_hitl`)
Triggers when a file possesses a high PageRank Blast Radius (`normalized_blast_radius > 1.0`) combined with high technical debt (`cumulative_risk > 200`).
* **Engineering Risk:** The module is both load-bearing and structurally fragile. Unvalidated autonomous edits present high risks of breaking downstream sub-systems. Automated modifications to these modules require explicit human code review.

### 3. Dynamic Logic Warning Zone (`hallucination_zone`)
Flags files relying heavily on reflection, dynamic dispatch, or metaprogramming (`heat_triggers > 2`) that lack sufficient documentation (`doc_density < 0.2`).
* **Engineering Risk:** Runtime behaviors depend on dynamic resolution rather than static interface contracts. Without inline documentation, LLM code generators frequently hallucinate missing functions or incorrect method signatures.

### 4. Silent Mutation Risk (`silent_mutation_risk`)
Identifies modules exhibiting high state volatility (`state_flux > 50`) that act as foundational producers (`in_degree > 5`) but lack unit test coverage.
* **Engineering Risk:** Autonomous refactoring of un-tested stateful producers risks introducing subtle runtime state corruption. Without automated unit test suites, agents cannot verify code correctness, propagating silent errors to downstream consumers.

---

## Telemetry Integration

Upon completing evaluation, the firewall compiles active guardrails and descriptive warning strings into an `ai_guardrails` object injected into the file's central telemetry map.

This telemetry is consumed by downstream components—specifically the `LLMRecorder` (`llm_recorder.py`)—to insert explicit agent constraint warnings into generated prompt briefs and SQLite knowledge graphs.

---

### Powered by GitGalaxy

This documentation is part of the [GitGalaxy Ecosystem](https://github.com/squid-protocol/gitgalaxy), an AST-free, LLM-free heuristic static analysis engine.

* **[Explore the GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** for source code and tools.
* **[Visualize your codebase at GitGalaxy.io](https://gitgalaxy.io/)** using the interactive WebGPU dashboard.

---

**[⬅️ Back to Master Index](index.md)**

