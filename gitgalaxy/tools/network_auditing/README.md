# GitGalaxy: API Network Map & Shadow API Hunter

[![Frameworks](https://img.shields.io/badge/Supported-Python_|_Node_|_Java_|_Go_|_C%23_|_Rust_|_Ruby_|_PHP-00C957.svg)](https://squid-protocol.github.io/gitgalaxy/04-01-full-api-network-map/)
[![Architecture](https://img.shields.io/badge/Architecture-AST--Free_Heuristics-00BFFF.svg)](https://squid-protocol.github.io/gitgalaxy/docs/wiki/01-03-the-blast-paradigm/)

Welcome to the **GitGalaxy Full API Network Map**.

Security documentation is often strictly theoretical, whereas compiled source code represents physical reality. Attackers do not exploit the APIs you have documented; they hunt for the forgotten, undocumented endpoints left exposed in your codebase.

Standard DevSecOps scanners rely on approved Swagger or OpenAPI files to dictate what should be tested. GitGalaxy provides a deterministic source of truth. By scanning the raw codebase directly, we reveal the exact routing logic that is actively exposed to the network, regardless of what the documentation claims.

---

### What It Is

The **Full API Network Map** is a language-agnostic static analysis tool that automatically compares your physical source code routing signatures against your official OpenAPI/Swagger documentation. 

It deterministically maps the delta between theoretical documentation and physical execution to expose critical security gaps:
* **🚨 Shadow APIs (Critical Risk):** Undocumented, active endpoints that evade standard Web Application Firewalls (WAFs) and security audits.
* **👻 Ghost APIs (Audit Bloat):** Documented but non-existent or deprecated endpoints that waste security team resources and cause integration failures.

---

### Why It Was Built (Architectural Decisions)

API documentation inevitably drifts from the compiled reality of the codebase. Traditional solutions to this problem rely on heavy Abstract Syntax Tree (AST) parsers, which require specific compiler environments, crash on malformed code, and struggle across polyglot microservice architectures.

We built this engine to prioritize **velocity, resilience, and scale**:
* **AST-Free Regex Signatures:** By utilizing bounded structural signatures, we can deterministically identify framework routing intents (e.g., `@GetMapping`, `app.post`) across 9+ languages simultaneously, bypassing the need for complex compilation environments.
* **O(1) Memory Shield for Auto-Discovery:** Reading entire massive JSON/YAML specification blobs into memory can cause Out-Of-Memory (OOM) crashes in CI/CD pipelines. Our auto-discovery engine restricts read buffers to the first 1000 characters, verifying Swagger signatures instantly without consuming excessive RAM.
* **Test-Schema Pollution Mitigation:** Enterprise monorepos are often littered with mock Swagger files used for unit testing. The engine automatically segregates and ignores schemas located in `test/` or `__tests__/` directories, preventing test stubs from polluting the production audit.

---

### How It Works (The Core Methodology)

1. **Auto-Discovery:** The engine recursively hunts for OpenAPI specifications in the target directory. It intelligently bypasses test directories and provides ambiguity warnings if multiple primary schemas are detected.
2. **Physical Codebase Mapping:** The engine scans raw source files, matching physical routing intents against a library of polyglot framework signatures (Spring Boot, Express, FastAPI, Gorilla Mux, .NET, Laravel, Actix, etc.).
3. **Mathematical Resolution:** Strict set theory is applied. The physical endpoints are subtracted from the documented endpoints (and vice-versa) to isolate the exact Shadow and Ghost APIs.
4. **Dashboard Presentation:** Generates a clean, actionable report of the exact files and endpoints violating the architectural contract.

---

### Usage & Clear Examples

#### 1. Local CLI Execution
Execute the tool directly against your physical source code. The engine will auto-discover your Swagger file and generate an immediate gap analysis:

```bash
python3 full_api_network_map.py /path/to/source/code
```

#### 2. Handling Microservice Monorepos
If your repository contains multiple microservices, each with its own Swagger file, you can instruct the engine to union them into a single mathematical truth state:

```bash
python3 full_api_network_map.py /path/to/source/code --merge-all
```

#### 3. Explicit Specification Targeting
Bypass the auto-discovery engine and audit the codebase against a highly specific, mandated architectural contract:

```bash
python3 full_api_network_map.py /path/to/source/code --swagger /path/to/official_swagger.json
```

#### Example Output Dashboard
Below is an example of the CLI output when the engine detects OpenAPI drift within a modern web application:

```text
🗺️  GitGalaxy API Network Mapper analyzing physical endpoints in: backend-monorepo...

 [DISCOVERY] Auto-discovered Swagger specification: docs/openapi.json

==========================================================
 📡 SHADOW API SECURITY AUDIT
==========================================================
 Physical Frameworks Tracked    : Python (FastAPI/Flask/Django), Node.js (Express/Fastify/Koa)
 Documented Endpoints (Swagger) : 24
 Physical Endpoints (Source)    : 26
----------------------------------------------------------
 🚨 SHADOW APIs DETECTED: 2 (Critical Risk)
    ↳ POST /api/v1/debug_admin    [Found in: server.js]
    ↳ GET /api/v1/legacy_export   [Found in: routes.py]

----------------------------------------------------------
 👻 GHOST APIs DETECTED: 1 (Documentation Bloat)
    ↳ DELETE /api/v1/users        [Missing from executable source code]
==========================================================
```

---

### GitHub Actions CI/CD Integration

You can automatically audit your API surface area on every Pull Request to ensure developers aren't silently exposing new endpoints without updating the Swagger documentation.

Create `.github/workflows/api-audit.yml`:

```yaml
name: Shadow API Audit

on:
  pull_request:
    branches: [ "main" ]

jobs:
  gitgalaxy-api-scan:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Run Shadow API Hunter
        run: |
          pip install pyyaml
          python3 full_api_network_map.py .
```

---
### Powered by the blAST Engine
This tool is a modular enterprise integration within the broader GitGalaxy architecture. It is driven by our custom mathematical heuristics engine, mapping multi-dimensional relationships without requiring an LLM or an AST/compiler toolchain. Read the official documentation to explore the underlying architecture:

* **[The blAST Paradigm (ASTs vs LLMs)](https://squid-protocol.github.io/gitgalaxy/01-03-the-blast-paradigm/)**
* **[Full API Network Map Architecture](https://squid-protocol.github.io/gitgalaxy/04-01-full-api-network-map/)**
* **[The Network Risk Sensor Mechanics](https://squid-protocol.github.io/gitgalaxy/02-16-network-risk-sensor/)**
* **[Return to the Main GitGalaxy Hub](https://github.com/squid-protocol/gitgalaxy)**