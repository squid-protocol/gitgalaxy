### Security & Auditing Test Suite

This directory contains the validation suite for GitGalaxy's security, auditing, and threat
intelligence sensors.

Most enterprise security tools rely on dynamic execution, sandboxing, or manifest-only
scanning, which misses typosquatting and hidden payloads. GitGalaxy's sensors work entirely
from static structural signals instead. This suite validates that the AST-free engine can
detect supply-chain anomalies, Shadow APIs, and algorithmic-complexity risks using pure static
analysis, without ever executing the target code — and, just as importantly, that it doesn't
claim to detect things a static, dataflow-free engine structurally can't (see the
`test_ai_appsec_sensor.py` entry below for a concrete example of that boundary).

---

### Running This Suite

These tests exercise the threat sensors against embedded malware signatures, corrupted JSON
schemas, and pathological input. To run this suite in isolation:

```bash
python -m pytest tests/security_auditing/ -v
```

---

### Test Index

#### 1. AI Governance & Agent Guardrails
Validates the sensors that monitor LLMs and autonomous agents interacting with the codebase.
* **`test_dev_agent_firewall.py`** — Validates the [Dev Agent Firewall](../../docs/wiki/02-18-dev-agent-firewall.md). Proves the engine flags files whose size/complexity would blow an agent's context budget ($O(N^3)$ files), flags mutations to files with low test coverage, and enforces human-in-the-loop gates based on calculated blast radius.
* **`test_ai_appsec_sensor.py`** — Validates the [AI AppSec Sensor](../../docs/wiki/02-17-ai-appsec-sensor.md). As of [#1102](https://github.com/squid-protocol/gitgalaxy/issues/1102), this only proves one signal: an over-permissioned agent binding — an LLM orchestration framework (LangChain, LlamaIndex) imported alongside raw network/disk I/O and below-threshold defensive-programming density. A regex-only engine with no dataflow tracing can't prove code execution or exfiltration actually occurs, so the sensor no longer claims to detect it; `test_report_no_longer_contains_removed_cooccurrence_keys` is a regression test guarding against that claim quietly coming back.
* **`test_neural_auditor.py`** — Validates the [Neural Auditor](../../docs/wiki/02-19-neural-auditor.md). Proves the local scanner can parse `.safetensors` and `.gguf` binary headers to extract quantization and parameter counts without loading the full model into memory.

#### 2. Supply Chain & Vault Security
Validates the perimeter defenses that block hostile dependencies and credential leaks.
* **`test_supply_chain_firewall.py`** — Validates the [Supply Chain Firewall](../../docs/wiki/04-03-supply-chain-firewall.md). Proves the import slicer enforces strict-mode allowlists, cross-references physical imports against known-bad packages, and correctly skips minified data files rather than misparsing them.
* **`test_vault_sentinel.py`** — Validates the [Vault Sentinel](../../docs/wiki/04-04-vault-sentinel.md). Proves the two-layer secrets scanner blocks forbidden file extensions outright and separately halts the pipeline on a deep-scan match for hardcoded `AKIA`-prefixed AWS keys in otherwise ordinary source code.
* **`test_binary_anomaly_detector.py`** — Validates the [Binary Anomaly Detector](../../docs/wiki/04-05-binary-anomaly-detector.md). Proves the binary inspector catches magic-byte mismatches (e.g. an executable disguised as a `.jpg`), flags high-entropy payloads consistent with encryption, and enforces the shebang check.
* **`test_sbom_generator.py`** — Validates the [SBOM Generator](../../docs/wiki/04-02-sbom-generator.md). Proves the manifest slicer translates threat state into compliant CycloneDX JSON without blindly trusting package names.

#### 3. Graph Analysis & Ecosystem Compliance
Validates the dependency-graph math and destructive-cleanup pipelines.
* **`test_security_auditor.py`** — Validates the [Security Auditor](../../docs/wiki/02-20-security-auditor.md). Proves the XGBoost multiclass inference engine correctly formats spatial data into pandas matrices for threat prediction, with an O(1) pure-Python fallback for dependency-graph resolution when NetworkX isn't installed.
* **`test_network_risk_sensor.py`** — Validates the [Network Risk Sensor](../../docs/wiki/02-16-network-risk-sensor.md). Proves the engine computes PageRank (blast radius) and betweenness centrality correctly across the dependency graph.
