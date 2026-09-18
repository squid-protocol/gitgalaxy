# How to Block Autonomous LLM Agents from Executing RCE

If you are building autonomous coding agents or integrating LLMs into your CI/CD pipeline, your greatest security threat is **Agentic RCE** (Remote Code Execution) via Prompt Injection.

Standard static analysis tools (like SonarQube or Snyk) struggle to detect this because the vulnerability is structural. The danger occurs when untrusted external I/O flows directly into an LLM context window, and the LLM's output flows into a dynamic execution command (like `eval` or `os.system`).

GitGalaxy solves this mathematically by mapping the physical distance between these nodes.

## The GitGalaxy AI Guardrails

Instead of relying on rigid ASTs, GitGalaxy uses a specialized `security_lens.py` to hunt for the structural DNA of an RCE funnel.

### 1. Scan the Repository
Run the GitGalaxy engine against your agent framework:

```bash
galaxyscope /path/to/your/llm_agent_repo --ai-guardrails
```

(The `--ai-guardrails` flag enables the Zero-Trust Guardrails phase, which is off by default — an LLM agent repo is exactly the kind of target it exists for.)

### 2. Identify the Choke Points
GitGalaxy generates an `_llm.md` context brief and an `_audit.json` file. Look specifically for the **Injection Surface Risk Exposure**.

The engine calculates this by cross-multiplying the density of external network inputs against dangerous execution vectors, removing the "Agentic Shield" if the file is explicitly designed to handle LLM orchestration.

### 3. Deploy the Dev Agent Firewall
Once the high-risk files are identified, deploy the GitGalaxy Dev Agent Firewall (`gitgalaxy/security/dev_agent_firewall.py`). 

This script evaluates the token mass and blast radius of the target file. If a file is flagged as an RCE Funnel, the firewall restricts autonomous coding agents from modifying it, requiring a "Human in the Loop" (HITL) override.

> **Read the full technical specification for the AppSec Sensor:** [AI AppSec Sensor](../02-17-ai-appsec-sensor.md)

---

**[⬅️ Back to Master Index](../index.md)**
