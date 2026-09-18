# How to Sandbox Autonomous Coding Agents (Dev Agent Firewall)

Enterprise adoption of autonomous coding agents (like Cursor, Devin, or SWE-agent) is accelerating, but these agents introduce massive architectural risk. 

If an agent modifies a highly-coupled "God Node," it can shatter the dependency graph. If it modifies a file with high algorithmic complexity (O(N^3)), it will drain its own token context window and hallucinate the fix. 

GitGalaxy prevents this by deploying a deterministic **Dev Agent Firewall** to evaluate the "Token Physics" and "Blast Radius" of a file *before* the agent is allowed to touch it.

## The Agentic Guardrails

GitGalaxy calculates the safety of agentic modification using `dev_agent_firewall.py`. It evaluates the repository's 3D spatial graph to trigger specific guardrails.

### 1. Identify the AI Black Holes
Before assigning a ticket to an agent, run the GitGalaxy scanner:

```bash
galaxyscope /path/to/repo --ai-guardrails
```

The Dev Agent Firewall is part of the engine's "Phase 5: Zero-Trust Guardrails", which is off by default — the `--ai-guardrails` flag enables it for repositories with a real AI/agentic surface.

The engine looks for **The Context Window Shredder**. If a file exceeds 8,000 tokens of mass AND contains `O(N^3)` or recursive algorithmic complexity, it is flagged as an `agentic_black_hole`. The AI will inevitably lose context and corrupt the file.

### 2. Enforce Human-in-the-Loop (HITL)
GitGalaxy calculates the exact PageRank (Blast Radius) of every file. If an agent attempts to modify a foundational file (PageRank > 1.0) that also carries severe Technical Debt or Cognitive Load (> 200 combined risk), the firewall triggers `requires_hitl`. 

The agent is blocked from committing, and a human architect must manually review the proposed diff.

### 3. Block Silent Mutations
Agents are prone to "silent mutations"—introducing subtle logic errors that don't immediately crash the compiler. If GitGalaxy detects a file with high State Flux (constant variable mutation), high inbound dependencies, and **zero unit tests**, it flags the file with `silent_mutation_risk`. 

Because the AI cannot verify its own fixes programmatically, modifications to this file are restricted until test coverage is established.

> **Read the full technical specification:** [Dev Agent Firewall](../02-18-dev-agent-firewall.md)

---

**[⬅️ Back to Master Index](../index.md)**
