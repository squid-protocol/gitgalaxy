# GitGalaxy Security: Dual-Sided AI Guardrails & AppSec Sensors

[![Defense](https://img.shields.io/badge/Defense-Dual--Sided_AI_Guardrails-00BFFF.svg)](#)
[![Velocity](https://img.shields.io/badge/Velocity-No_Compilation_Required-00C957.svg)](#)
[![Reporting](https://img.shields.io/badge/Reporting-Contextual_Telemetry-8A2BE2.svg)](#)

Welcome to the **GitGalaxy AI Guardrails Suite**.

The rapid adoption of Generative AI has introduced two critical security and stability blind spots for modern enterprise teams. First, developers are deploying AI features that grant Large Language Models (LLMs) dangerous levels of system and execution access (The AppSec Threat). Second, developers are utilizing autonomous coding agents that can silently introduce architectural degradation into complex codebases (The DevSecOps Threat).

Legacy security scanners cannot solve this. They are designed to detect traditional SQL injections, not Prompt Injections or Agentic context exhaustion. They rely on slow AST (Abstract Syntax Tree) compilation cycles that fail to map the structural reality of AI-driven state mutation.

GitGalaxy maps the architectural reality of your code in seconds. We use AST-free mathematical heuristics to generate deep, contextual telemetry, allowing you to block dangerous AI architectures and sandbox autonomous agents before they compromise production.

---

## 🧠 Engineering Highlights (Architectural Feats)

To protect repositories against non-deterministic AI behavior without slowing down CI/CD pipelines, we engineered these sensors to evaluate the mathematical topology of the codebase rather than relying on brittle semantic analysis:

* **Topological Threat Intersection (`ai_appsec_sensor.py`):** Standard scanners evaluate vulnerabilities in isolation. This sensor cross-references multi-dimensional structural topologies. It mathematically proves when an LLM Orchestrator node sits on the same execution path as an OS-level `subprocess` call and a Public API router. By mapping these intersections, it deterministically flags **Autonomous Execution Vectors** without requiring dynamic runtime execution.
* **Context Mass Validation (`dev_agent_firewall.py`):** Autonomous coding agents blindly attempt to refactor files regardless of size. This firewall calculates the physical Token Mass of a file and flags it once that mass exceeds what an agent's context window can safely hold. If the limit is breached, it raises a **Context Window Exhaustion** risk, mathematically proving the agent is about to hallucinate and corrupt the logic.
* **Blast Radius Sandboxing (`dev_agent_firewall.py`):** We strictly prohibit AI agents from modifying the structural load-bearing pillars of your architecture. By querying the Knowledge Graph for a file's **Dependency Blast Radius** (PageRank / Downstream Exposure), the firewall automatically mandates Human-In-The-Loop (HITL) reviews for any PRs targeting highly centralized nodes with existing Technical Debt.

---

## 🛡️ Side 1: The AI AppSec Sensor (`ai_appsec_sensor.py`)
*Protects your application from the AI features your developers build.*

**Why It Was Built:** AI agents with unconstrained execution boundaries represent a critical security risk. Traditional Static Analysis (SAST) misses the intersection of LLM logic and system APIs. By analyzing the structural topology of the codebase, this sensor deterministically identifies intersections where LLMs (which are inherently vulnerable to Prompt Injection) are dangerously close to OS commands or database writes.

**What It Detects:**
* **Autonomous Execution Vector:** Detects LLM logic that is adjacent to OS-level execution (`eval`, `subprocess`) and exposed via a public API router. This allows you to aggressively block Prompt-Injection-to-RCE attacks in your CI/CD pipeline.
* **Over-Permissioned Agent Binding:** Flags autonomous tools bound to raw Database/IO write access with critically low defensive programming density (e.g., missing `try/catch` blocks). Blocks autonomous data corruption before it reaches production tables.
* **Agentic Exfiltration Vector:** Identifies LLM logic with access to both unfiltered network sockets and hardcoded environment secrets, neutralizing SSRF and autonomous key exfiltration vectors.

---

## 🤖 Side 2: The Dev Agent Firewall (`dev_agent_firewall.py`)
*Protects your codebase from the autonomous AI coding tools your developers use.*

**Why It Was Built:** Autonomous coding agents (e.g., Claude, Cursor) excel in isolated, pure-function environments but struggle with highly coupled, poorly documented, or dynamically generated logic. This firewall establishes Zero-Trust guardrails. It prevents AI agents from executing unchecked modifications in volatile sectors, mitigating the risk of cascading failures, context window exhaustion, and silent state mutations.

**What It Detects:**
* **Context Window Exhaustion:** Identifies files exceeding standard token limits combined with extreme algorithmic complexity. Prevents the AI from losing context and inducing severe structural hallucinations.
* **Hallucination Risk:** Highlights codebases with heavy dynamic metaprogramming and severe Documentation Risk Exposure (< 20% density). Flags zones where autonomous agents are mathematically highly likely to hallucinate missing methods.
* **Cascading State Flux:** Flags logic with high state mutation and dense downstream dependencies, but zero test coverage. Blocks unverifiable AI modifications where the agent cannot mathematically verify its own structural changes.
* **HITL Mandate:** Detects high **Dependency Blast Radius** combined with severe Technical Debt. Forces a strict Human-In-The-Loop (HITL) architectural review requirement for PRs generated by AI.

---

## 🚀 Quickstart: CI/CD & Pipeline Integration

Currently, the AI Guardrails operate as deep-inspection middleware. Instead of running as standalone commands, these sensors seamlessly inject themselves into the primary GitGalaxy analysis pipeline to evaluate project telemetry in real-time.

### 1. Local CLI Execution
Run a standard scan using the global PyPI package. The guardrails will automatically evaluate the ecosystem and report critical Agentic vulnerabilities.
###bash
gitgalaxy /path/to/source/code
###

### 2. GitHub Actions CI/CD Integration
To block dangerous AI architectures or prevent AI agents from modifying complex code, run the main GitGalaxy engine on your pull requests. Create `.github/workflows/ai-guardrails.yml`:

###yaml
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
###

---

## 🌌 The GitGalaxy Ecosystem (Powered by the blAST Engine)

GitGalaxy AI Guardrails is the autonomous defense layer of the broader **GitGalaxy Ecosystem**—a high-velocity, AST-free, LLM-free heuristic knowledge graph engine designed for planetary-scale repositories.

Explore the ecosystem:

* 🪐 **[Official Documentation](https://squid-protocol.github.io/gitgalaxy/)** — Comprehensive deep dives into the engine's mathematics, pipeline architecture, and DevSecOps integration protocols.
* 🔭 **[GitGalaxy Visualizer](http://gitgalaxy.io/)** — Render your codebase's topological network locally in interactive 3D using hardware-accelerated WebGPU.
* 📖 **[The blAST Paradigm](https://squid-protocol.github.io/gitgalaxy/docs/wiki/01-03-the-blast-paradigm/)** — The architectural thesis, academic research, and structural math that makes AST-free parsing possible at scale.
* ⚙️ **[Language Calibration Standards](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/standards/how_to_add_a_language.md)** — The definitive engineering guide to extending our comparative lexical taxonomy for custom enterprise dialects.