---
description: "In modern microservice architectures, documentation drift is inevitable. Developers rapidly add endpoints to Express, FastAPI, or Spring Boot..."
---
# How to Hunt Shadow APIs and Undocumented Endpoints

In modern microservice architectures, documentation drift is inevitable. Developers rapidly add endpoints to Express, FastAPI, or Spring Boot controllers, but forget to update the official OpenAPI/Swagger specifications. 

When security teams audit the application, they only test the documented endpoints. Undocumented **Shadow APIs** (legacy `v1` routes, `/debug` endpoints) can then go untested. Each one needs review: some are harmless internal routes, some are exposed and unauthenticated.

GitGalaxy's **Full API Network Map** lists the routes it can find in your source code and compares them with the routes in your OpenAPI/Swagger file.

## The Network Mapper

Instead of watching network traffic (which misses routes nobody calls), the mapper reads route definitions from source with one regex per framework: Python (FastAPI/Flask decorators), Node.js (Express/Fastify/Koa calls), Java (Spring `@...Mapping`), C# (`[Http...]` attributes and minimal-API `Map...` calls), PHP (`Route::...`), Rust (Actix/Rocket attributes), Ruby (Rails/Sinatra verbs) and Go (`.GET(...)`-style calls). Routes defined any other way are not seen; see the limits below. The mapper is tested on fixtures in `tests/` (`test_api_network_map.py`); its recall on real services has not been measured.

### 1. Execute the Scan (Auto-Discovery)
Point the mapper at your source code directory. The engine features a smart Auto-Discovery handshake that automatically hunts down your primary `swagger.json` or `openapi.yaml` file while safely ignoring fake schemas generated inside testing directories to prevent documentation pollution.

```bash
python gitgalaxy/tools/network_auditing/full_api_network_map.py /path/to/source_code
```

*(Note: If working in a complex monorepo with multiple valid schemas, you can still manually specify a target using the `--swagger /path/to/schema.json` flag, or union them all using the `--merge-all` flag).*

### 2. Analyze the Gap (Set Theory)
The tool builds two sets: the *Approved APIs* (from Swagger) and the *Physical APIs* (found in the code). A code route matches a documented one with the same method whose path is equal or ends with the code route's path (so a route missing its router prefix still matches). What is left over on each side is reported.

* **Shadow APIs:** routes found in the code but not in the spec.
* **Ghost APIs:** routes in the spec that the mapper did not find in the code. Either the code was deleted, or the route is defined in a way the mapper cannot read: check before deleting the spec entry.

For example, a small Express service whose `openapi.json` documents `GET /users`, `POST /users` and `GET /v1/orders`, and whose `server.js` defines:

```js
app.get('/users', listUsers);
app.post('/users', createUser);
router.get('/debug/config', dumpConfig);
app.use('/admin', router);
```

gives (license banner trimmed):

```text
🗺️  GitGalaxy API Network Mapper analyzing physical endpoints in: shadowdemo...

 🔍 No --swagger file provided. Initiating auto-discovery...
 [DISCOVERY] Primary Swagger specification identified: docs/openapi.json

==========================================================
 📡 SHADOW API SECURITY AUDIT
==========================================================
 Physical Frameworks Tracked    : Node.js (Express/Fastify/Koa)
 Documented Endpoints (Swagger) : 3
 Physical Endpoints (Source)    : 3
----------------------------------------------------------
 🚨 SHADOW APIs DETECTED: 1 (Critical Risk)
    ↳ GET /debug/config         [Found in: server.js]

----------------------------------------------------------
 👻 GHOST APIs DETECTED: 1 (Documentation Bloat)
    ↳ GET /v1/orders            [Missing from executable source code]
==========================================================
```

The route is reported as `/debug/config`, not `/admin/debug/config`: the mapper does not join a router's mount prefix (see the limits below).

### 3. Security Remediation
Each undocumented route needs review. The tool prints "(Critical Risk)" next to the count, but it does not check whether a route is exposed, authenticated or reachable. Because it names the file where the route is defined (`server.js` above), a reviewer can decide to either:
1. Delete the forgotten code.
2. Document the endpoint in the spec so it is covered by whatever testing, gateway or WAF rules are driven from that spec.

### Known limits
* **Frameworks it cannot read produce false Ghost APIs.** Routes declared as procedures or schemas rather than verb calls (tRPC routers, GraphQL resolvers, Django URLconf `path()` entries, Rails `resources`) are not extracted. On a tRPC codebase every documented procedure shows up as a Ghost API, which is a mapper miss, not dead documentation.
* **Node.js:** only `app.`, `router.` or `server.` followed by `get/post/put/delete/patch` with a literal string path is read. Other object names (`api.get(...)`, `r.get(...)`), route chains (`router.route('/x').get(...)`) and computed paths are missed.
* **Prefixes are not resolved.** Router mounts and class-level prefixes are not joined to the route, and the suffix match can hide a shadow route: a code route `/profile` counts as documented if the spec has `/admin/profile`, even when the code actually serves it under another prefix.
* **Go:** any `.GET(`/`.POST(`-style call with a string literal counts as a route, including HTTP client calls.
* **No reachability check:** a route that is defined but never mounted is still reported.

> **Read the full technical specification:** [Full API Network Map](../04-01-full-api-network-map.md)

---

**[⬅️ Back to Master Index](../index.md)**
