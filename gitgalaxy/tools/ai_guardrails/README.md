# GitGalaxy Security: Dual-Sided AI Guardrails & AppSec Sensors

Welcome to the **GitGalaxy AI Guardrails Suite**.

The rapid adoption of Generative AI has introduced two critical security and stability blind spots for modern enterprise teams. First, developers are deploying AI features that grant Large Language Models (LLMs) dangerous levels of system and execution access (The AppSec Threat). Second, developers are utilizing autonomous coding agents that can silently introduce architectural degradation into complex codebases (The DevSecOps Threat).

Legacy security scanners cannot solve this. They are designed to detect traditional SQL injections, not Prompt Injections or Agentic context exhaustion. They rely on slow AST (Abstract Syntax Tree) compilation cycles that fail to map the structural reality of AI-driven state mutation.

GitGalaxy maps the architectural reality of your code in seconds. We use AST-free mathematical heuristics to generate deep, contextual telemetry, allowing you to block dangerous AI architectures and sandbox autonomous agents before they compromise production.

---

## Engineering Highlights (Architectural Feats)

To protect repositories against non-deterministic AI behavior without slowing down CI/CD pipelines, we engineered these sensors to evaluate the mathematical topology of the codebase rather than relying on brittle semantic analysis:

* **Library-Identity Binding Detection (`ai_appsec_sensor.py`):** GitGalaxy is AST-free and does no data-flow/taint analysis, so it can't prove an LLM Orchestrator's output actually reaches a given I/O sink -- only that both exist in the same file. This sensor sticks to what a regex-only engine can honestly claim: it detects when a known agent-orchestration framework (e.g. langchain, llama_index) is imported into a file with raw network/disk write access and low defensive programming density, flagging an **Over-Permissioned Agent Binding**. (Two prior checks that inferred RCE/exfiltration from mere signature co-occurrence were removed in #1102 as unproven claims a regex engine can't back.)
* **Context Mass Validation (`dev_agent_firewall.py`):** Autonomous coding agents blindly attempt to refactor files regardless of size. This firewall calculates the physical Token Mass of a file and flags it once that mass exceeds what an agent's context window can safely hold. If the limit is breached, it raises a **Context Window Exhaustion** risk, mathematically proving the agent is about to hallucinate and corrupt the logic.
* **Blast Radius Sandboxing (`dev_agent_firewall.py`):** We strictly prohibit AI agents from modifying the structural load-bearing pillars of your architecture. By querying the Knowledge Graph for a file's **Dependency Blast Radius** (PageRank / Downstream Exposure), the firewall automatically mandates Human-In-The-Loop (HITL) reviews for any PRs targeting highly centralized nodes with existing Technical Debt.

---

## Side 1: The AI AppSec Sensor (`ai_appsec_sensor.py`)
*Protects your application from the AI features your developers build.*

**Why It Was Built:** Autonomous coding/tool-calling agents bound to raw state-mutation capability (network or disk writes) without adequate defensive programming represent a real operational risk. Because GitGalaxy has no data-flow or taint tracking, it cannot prove an LLM's output actually reaches a given execution or network sink -- only that a known agent-orchestration framework and raw I/O access coexist in the same file. This sensor is scoped to exactly that honest claim.

**What It Detects:**
* **Over-Permissioned Agent Binding:** Flags a file that imports an agent-orchestration framework (langchain/llama_index) and has raw Network/Disk IO write access, combined with critically low defensive programming density (e.g., missing `try/catch` blocks). Surfaces autonomous data-corruption risk before it reaches production tables.

**Removed in #1102** (epic #1025): two prior checks, "Autonomous Execution Vector" and "Agentic Exfiltration Vector," inferred an RCE or exfiltration vulnerability purely from unrelated regex categories (an LLM signal, a public-API/IO signal, an eval/secrets signal) co-occurring anywhere in a file -- with zero proof the data actually flows between them. That's the same unprovable pattern epic #1025 already removed from the core risk schema (issue #1020); it had simply been reimplemented here under different names.

---

## Side 2: The Dev Agent Firewall (`dev_agent_firewall.py`)
*Protects your codebase from the autonomous AI coding tools your developers use.*

**Why It Was Built:** Autonomous coding agents (e.g., Claude, Cursor) excel in isolated, pure-function environments but struggle with highly coupled, poorly documented, or dynamically generated logic. This firewall establishes Zero-Trust guardrails. It prevents AI agents from executing unchecked modifications in volatile sectors, mitigating the risk of cascading failures, context window exhaustion, and silent state mutations.

**What It Detects:**
* **Context Window Exhaustion:** Flags files whose token mass exceeds 8,000 tokens — large enough to exceed an agent's usable context window. Prevents the AI from losing context and inducing severe structural hallucinations.
* **Hallucination Risk:** Flags dynamic metaprogramming constructs (reflection, runtime codegen) with no documentation within 10 lines in the same function — a direct proximity check, not a file-wide documentation-density average. Flags zones where autonomous agents are highly likely to hallucinate missing methods.
* **Cascading State Flux:** Flags logic with high state mutation and dense downstream dependencies, but zero test coverage. Blocks unverifiable AI modifications where the agent cannot mathematically verify its own structural changes.
* **HITL Mandate:** Detects high **Dependency Blast Radius** combined with severe Technical Debt. Forces a strict Human-In-The-Loop (HITL) architectural review requirement for PRs generated by AI.

---

## Quickstart: CI/CD & Pipeline Integration

Currently, the AI Guardrails operate as deep-inspection middleware. Instead of running as standalone commands, these sensors seamlessly inject themselves into the primary GitGalaxy analysis pipeline to evaluate project telemetry in real-time.

### 1. Local CLI Execution
Run a standard scan using the global PyPI package. The guardrails will automatically evaluate the ecosystem and report critical Agentic vulnerabilities.
```bash
gitgalaxy /path/to/source/code
```

### 2. GitHub Actions CI/CD Integration
To block dangerous AI architectures or prevent AI agents from modifying complex code, run the main GitGalaxy engine on your pull requests. Create `.github/workflows/ai-guardrails.yml`:

```yaml
name: GitGalaxy AI Guardrails

on:
  pull_request:
    branches: [ "main" ]

jobs:
  gitgalaxy-ai-scan:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Run GitGalaxy Engine
        uses: squid-protocol/gitgalaxy@v2.0.7
        with:
          tool: 'core-engine'
          target: '.'
```

---

## The GitGalaxy Ecosystem (Powered by the blAST Engine)

GitGalaxy AI Guardrails is the autonomous defense layer of the broader **GitGalaxy Ecosystem**—an AST-free, LLM-free heuristic knowledge graph engine that scales to large repositories.

Explore the ecosystem:

* **[Official Documentation](https://squid-protocol.github.io/gitgalaxy/)** — Comprehensive deep dives into the engine's mathematics, pipeline architecture, and DevSecOps integration protocols.
* **[GitGalaxy Visualizer](http://gitgalaxy.io/)** — Render your codebase's topological network locally in interactive 3D using hardware-accelerated WebGPU.
* **[The blAST Paradigm](https://squid-protocol.github.io/gitgalaxy/docs/wiki/01-03-the-blast-paradigm/)** — The architectural thesis, academic research, and structural math that makes AST-free parsing possible at scale.
* **[Language Calibration Standards](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/standards/how_to_add_a_language.md)** — The definitive engineering guide to extending our comparative lexical taxonomy for custom enterprise dialects.