---
description: "In modern microservice architectures, documentation drift is inevitable. Developers rapidly add endpoints to Express, FastAPI, or Spring Boot..."
---
# How to Hunt Shadow APIs and Undocumented Endpoints

In modern microservice architectures, documentation drift is inevitable. Developers rapidly add endpoints to Express, FastAPI, or Spring Boot controllers, but forget to update the official OpenAPI/Swagger specifications. 

When security teams audit the application, they only test the documented endpoints. This leaves undocumented **Shadow APIs** (like legacy `v1` routes or unauthenticated `/debug` endpoints) exposed to the public internet, creating a massive blind spot for attackers to exploit.

GitGalaxy closes this gap using the **Full API Network Map**, comparing the physical routing logic compiled in your source code against your official security documentation using mathematical Set Theory.

## The Network Mapper

Instead of relying on network traffic sniffing (which misses dormant endpoints), GitGalaxy uses AST-free structural parsing to extract the exact physical routing reality directly from the source code across Python, Node.js, Java, C#, PHP, Rust, Ruby, and Golang.

### 1. Execute the Scan (Auto-Discovery)
Point the mapper at your source code directory. The engine features a smart Auto-Discovery handshake that automatically hunts down your primary `swagger.json` or `openapi.yaml` file while safely ignoring fake schemas generated inside testing directories to prevent documentation pollution.

```bash
python gitgalaxy/tools/network_auditing/full_api_network_map.py /path/to/source_code
```

*(Note: If working in a complex monorepo with multiple valid schemas, you can still manually specify a target using the `--swagger /path/to/schema.json` flag, or union them all using the `--merge-all` flag).*

### 2. Analyze the Gap (Set Theory)
The engine builds two sets of data: the *Approved APIs* (from Swagger) and the *Physical APIs* (from the code). It then subtracts the sets to immediately highlight the discrepancies.

* **Shadow APIs:** Code that is physically active and listening for traffic, but hidden from the security team. 
* **Ghost APIs:** Endpoints that the security team thinks exist, but have actually been deleted from the codebase (Documentation Bloat).

```text
🗺️  GitGalaxy Network Mapper analyzing physical endpoints in: trpc...

 🔍 No --swagger file provided. Initiating auto-discovery...
 🎯 Auto-discovered Primary Swagger: examples/openapi-codegen/openapi.json
 🛡️  Safely bypassed 9 schemas detected in test directories:
    - [Assumed Test] packages/openapi/test/routers/mongoEjsonRouter.openapi.json
    - [Assumed Test] packages/openapi/test/routers/appRouter.openapi.json
    - [Assumed Test] packages/openapi/test/routers/edgeCaseRouter.openapi.json
    - [Assumed Test] packages/openapi/test/routers/errorFormatterRouter.openapi.json
    - [Assumed Test] packages/openapi/test/routers/descriptionsRouter.openapi.json
    - [Assumed Test] packages/openapi/test/routers/cyclicTypesRouter.openapi.json
    - [Assumed Test] packages/openapi/test/routers/amazonIonRouter.openapi.json
    - [Assumed Test] packages/openapi/test/routers/nodeModulesJsDocRouter.openapi.json
    - [Assumed Test] packages/openapi/test/routers/superjsonRouter.openapi.json

==========================================================
 📡 SHADOW API SECURITY AUDIT
==========================================================
 Physical Frameworks Tracked    : Node.js (Express/Fastify/Koa)
 Documented Endpoints (Swagger) : 3
 Physical Endpoints (Source)    : 1
----------------------------------------------------------
 🚨 SHADOW APIS DETECTED: 1 (Critical Risk)
    ↳ GET /                     [Found in: server.ts]

----------------------------------------------------------
 👻 GHOST APIS DETECTED: 3 (Documentation Bloat)
    ↳ GET /user.byId            [Missing from source code]
    ↳ GET /user.list            [Missing from source code]
    ↳ POST /user.create         [Missing from source code]
==========================================================
```

### 3. Security Remediation
Every Shadow API represents a critical security risk. Because the tool outputs the exact filename where the rogue route is defined (`server.ts`), DevSecOps can immediately open a ticket to either:
1. Delete the forgotten code.
2. Officially document the endpoint in the Swagger file so it falls under the jurisdiction of the Web Application Firewall (WAF) and authentication middleware.

> **Read the full technical specification:** [Full API Network Map](../04-01-full-api-network-map.md)

---

**[⬅️ Back to Master Index](../index.md)**
