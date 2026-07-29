# Full API Network Map (Shadow & Ghost API Audit)

> **File Reference:** [gitgalaxy/tools/network_auditing/full_api_network_map.py](file:///home/joe/nyx_projects/gitgalaxy/gitgalaxy/tools/network_auditing/full_api_network_map.py)

The `full_api_network_map.py` module in `gitgalaxy/tools/network_auditing/` provides automated attack surface mapping for backend REST APIs. While internal dependency tools map file-to-file imports, the API Network Mapper evaluates the external network boundary of a repository. It compares executable router code signatures against official OpenAPI/Swagger documentation (`swagger.json`, `swagger.yaml`, `openapi.json`, `openapi.yaml`) to identify undocumented "Shadow APIs" and deprecated "Ghost APIs".

---

## Router Pattern Matching Across Frameworks

Rather than requiring a runtime environment or language-specific AST parsers, the mapper uses regular expression routing signatures (`FRAMEWORK_SIGNATURES`) to scan raw source files across major web frameworks:

* **Python (FastAPI / Flask / Django):** Scans `.py` files for route decorators (e.g., `@app.get(...)`, `@router.post(...)`, `@bp.delete(...)`).
* **Node.js (Express / Fastify / Koa):** Scans `.js` and `.ts` files for router registrations (e.g., `app.get(...)`, `router.post(...)`).
* **Java (Spring Boot):** Scans `.java` files for mapping annotations (e.g., `@GetMapping(...)`, `@PostMapping(...)`).
* **Golang (Gorilla Mux / Gin / Fiber):** Scans `.go` files for method handlers (e.g., `r.GET(...)`, `router.POST(...)`).
* **C# (.NET Controllers & Minimal APIs):** Scans `.cs` files for HTTP attributes and map helpers (e.g., `[HttpGet(...)]`, `app.MapPost(...)`).
* **PHP (Laravel / Symfony):** Scans `.php` files for route declarations (e.g., `Route::get(...)`, `Route::post(...)`).
* **Rust (Actix / Rocket):** Scans `.rs` files for attribute macros (e.g., `#[get(...)]`, `#[post(...)]`).
* **Ruby (Rails / Sinatra):** Scans `.rb` files for route directives (e.g., `get "..."`, `post "..."`).

---

## Endpoint Normalization & Path Parameter Matching

To prevent false discrepancies caused by formatting differences or parameter naming, the `normalize_endpoint()` function standardizes all discovered endpoints:

1. **Query String & Whitespace Removal:** Strips query parameters (`?key=val`) and surrounding whitespace.
2. **Dynamic Parameter Canonicalization:** Converts framework-specific path parameters to a universal `{var}` token:
   * Express / Fastify (`/users/:userId`) $\rightarrow$ `GET /users/{var}`
   * Flask (`/users/<int:user_id>`) $\rightarrow$ `GET /users/{var}`
   * Swagger / Spring (`/users/{userId}`) $\rightarrow$ `GET /users/{var}`
3. **Slash Uniformity:** Ensures leading root slashes and strips non-root trailing slashes.

Outputs are formatted as normalized `METHOD /path` strings (e.g., `GET /api/users/{var}`).

---

## Set Theory Validation & API Drift Analysis

The mapper performs set comparison between the documented specification set ($A$) and physical code endpoint set ($P$):

1. **Specification Parsing (`parse_official_swagger`):** Parses `swagger.json` or `openapi.yaml` to extract the set of approved endpoints ($A$).
2. **Shadow API Detection ($P \setminus A$):** Identifies endpoints present in source code but missing from official documentation. Shadow APIs represent unmonitored attack vectors and unreviewed entry points.
3. **Ghost API Detection ($A \setminus P$):** Identifies endpoints declared in Swagger documentation that no longer exist in executable code, flagging documentation decay.
4. **Topological Suffix Matching (`calculate_api_drift`):** Resolves router path prefix mismatches (e.g., matching a controller route `/profile` against full spec path `/api/v1/users/profile`).

---

## Specification Auto-Discovery & Test Guardrails

When run without an explicit `--swagger` argument, `auto_discover_swagger()` probes the target directory:

* Inspects filenames (`swagger.json`, `openapi.yaml`, etc.).
* Inspects the initial 1000 characters of JSON/YAML files to verify OpenAPI/Swagger schema headers without allocating large file buffers in memory.
* Segregates test directory specifications (`/test/`, `/tests/`) to avoid test-schema pollution.
* Supports monorepos with multiple microservices via the `--merge-all` flag.

---

## CLI & Programmatic Integration

The mapper can be invoked via CLI or programmatically within the main pipeline via `run_api_audit()`:

```bash
python3 -m gitgalaxy.tools.network_auditing.full_api_network_map /path/to/repo --swagger swagger.json
```

Programmatic callers receive a structured result dictionary containing audit status, detected frameworks, shadow counts, ghost counts, and endpoint lists.

---

### Ecosystem References

* **[GitHub Repository](https://github.com/squid-protocol/gitgalaxy)** - Source code for `full_api_network_map.py`.
* **[GitGalaxy Platform](https://gitgalaxy.io/)** - WebGPU repository visualization dashboard.

---

**[⬅️ Back to Master Index](index.md)**

