# GitGalaxy Recorders: Telemetry & Data Serialization Engine

This directory houses the high-speed data serialization and export engines for GitGalaxy. 

As the final phase of the pipeline, the `recorders` directory translates the in-memory topological graphs and structural risk vectors into compact payloads for downstream consumers. GitGalaxy is headless and API-first; these modules format the data for interactive 3D WebGPU visualizers, autonomous AI coding agents, SIEM pipelines, and enterprise data warehouses to consume directly.

## Architectural Philosophy & Defensive Engineering

Converting a multi-dimensional graph of 50,000+ files into a portable format presents a severe memory and I/O bottleneck. Standard serialization libraries will duplicate the graph in RAM, triggering immediate OS-level Out-Of-Memory (OOM) kills. The Recorders are defensively engineered to mitigate these constraints:

### 1. Destructive RAM Eviction (Memory Management)
To process monolithic repositories on standard hardware, the `gpu_recorder.py` employs a "Destructive Pivot." Instead of copying data, it systematically `.pop()`s elements from the main Orchestrator arrays to build its new schema, manually invoking Python's Garbage Collector (`gc.collect()`) at phase boundaries. This ensures the pipeline's memory footprint strictly decreases during the export phase, preventing OOM crashes.

### 2. Columnar Pivoting & Text Interning (AoS to SoA)
WebGPU and frontend rendering engines struggle with deeply nested, row-based JSON (Array of Structs). The engine structurally pivots the telemetry into flat, numerical columns (Structure of Arrays). Repetitive metadata—such as file extensions, author names, or diagnostic reasons—are minified into O(1) integer arrays using Text Interning. This reduces the network payload size and client-side RAM overhead.

### 3. Zero-Overhead Relational Mapping
The `record_keeper.py` bypasses intermediate JSON/CSV dumping entirely. It maps the in-memory Python dictionaries directly into a native SQLite3 database. To prevent I/O deadlocks during massive batch inserts, it explicitly enforces `PRAGMA journal_mode = WAL;` (Write-Ahead Logging) and relaxed synchronous modes, without sacrificing relational integrity.

### 4. Token-Density Optimization for LLMs
Dumping raw telemetry into an LLM context window saturates the agent with noise and wastes tokens. The `llm_recorder.py` acts as a statistical translation layer. It mathematically isolates the repository's structural dependencies (high blast radius), undocumented choke points (high centrality, zero documentation), and cascading mutations (high centrality, high state flux), generating a dense, highly opinionated Markdown brief that maximizes AI comprehension per token.

---

## The Core Pipeline (Exit Strategies)

Each file in this directory represents a specialized data exit strategy, tailored for a specific downstream consumer:

* **`gpu_recorder.py` (The Visual Payload Generator):** Generates the `_gpu.json` payload. It performs the Destructive RAM Eviction and Columnar Pivot, compressing the multi-dimensional graph into a minified manifest built strictly for high-performance WebGPU rendering engines.
* **`record_keeper.py` (The SQL Telemetry Layer):** Generates the `_master.db` artifact. A native SQLite3 recorder that captures the complete forensic state of the scan. It creates a robust, time-series schema designed for Enterprise Data Warehouse (EDW) aggregation, SQL-based security auditing, and delta-scan rehydration.
* **`sarif_recorder.py` (The Enterprise CI/CD Layer):** Generates the `_sarif.json` payload. Translates the XGBoost threat classifications, AI AppSec guardrails, and structural risk thresholds into the industry-standard Static Analysis Results Interchange Format (SARIF 2.1.0), enabling native integration with GitHub Advanced Security and GitLab Ultimate.
* **`sbom_recorder.py` (The Supply Chain Manifest):** Generates the `_sbom.json` payload. Transforms the resolved repository dependency graph into a formalized CycloneDX 1.4 manifest. Integrates a Zero-Trust physical audit to flag locally spoofed or maliciously packed dependencies.
* **`llm_recorder.py` (The AI Context Layer):** Generates the `_llm.md` and `_graph.sqlite` artifacts. It calculates repository-wide statistical metrics (Min/Max/Mean for all 18 risk dimensions) and produces a targeted brief that grants autonomous AI agents (like Claude or Cursor) total ecosystem awareness before they write a single line of code.
* **`audit_recorder.py` (The Compliance & Forensic Layer):** Generates the `_audit.json` log. Designed for compliance, security debugging, and human review. It cryptographically binds the scan to a specific Git Commit Hash (acting as a Structural Health Bill of Materials), decodes the internal XGBoost ML Threat taxonomy, and maps raw integers back to descriptive, enterprise-friendly terminology.

---

## The Dependency Graph in `_master.db` (`edge_data`, #2992)

`network_risk_sensor.py` builds the file-to-file import graph every scan. Besides the per-node summaries in `file_data` (`popularity` = in-degree, `internal_dependency_links` = out-degree, `pagerank_score`, ...), `record_keeper.py` persists the edges themselves, keyed like every other snapshot table:

| column | meaning |
|---|---|
| `repo_name`, `commit_hash` | the snapshot |
| `src_file_id` → `file_data.id` | the importing file |
| `dst_file_id` → `file_data.id` | the imported file |
| `edge_kind` | `'import'` (the dependency graph), or `'call'` / `'exec'` (the mainframe call graph, #3200). **Always filter on this.** |
| `import_statements` | resolved import captures from src to dst (repeats collapse into one row) |
| `entity_imports` | how many of those were the entity (`from x import y`) form |
| `weight` | the edge weight pagerank/betweenness read (1.0 per plain import, 1.5 per entity import) |

In both modes, per file, `COUNT(*)` of rows **with `edge_kind = 'import'`** and `src_file_id = f.id` equals `internal_dependency_links`, and rows with `dst_file_id = f.id` equals `popularity`. (Before #3024, zero-dependency mode counted import statements instead of distinct neighbours; for those older snapshots, reconcile with `SUM(import_statements)`. See `docs/zero_dependency_mode.md` for everything else that differs between the modes.) An edge is only recorded when both endpoints have a `file_data` row. The statistical audit can relegate a graph node to `excluded_artifacts` after the graph is built, and the edges that loses are counted in `repo_data.network_edges_unrecorded` (NULL when the caller supplied no edge list).

```sql
-- Neighbourhood marker load: what a file's direct imports carry, beside its own load.
SELECT f.file_path, f.arch_concurrency AS own_concurrency,
       SUM(d.arch_globals + d.state_flux) AS neighbour_shared_state
FROM file_data f
JOIN edge_data e ON e.src_file_id = f.id AND e.edge_kind = 'import'
JOIN file_data d ON d.id = e.dst_file_id
WHERE f.repo_name = ? AND f.commit_hash = ?
GROUP BY f.id;

-- Per-language edge coverage: how much of the raw import surface resolves to an in-scan edge.
SELECT f.language, COUNT(*) AS files, SUM(f.import_count) AS captures,
       SUM(f.import_count > 0) AS files_with_captures,
       SUM(EXISTS (SELECT 1 FROM edge_data e WHERE e.src_file_id = f.id AND e.edge_kind = 'import')) AS files_with_edges,
       (SELECT COUNT(*) FROM edge_data e JOIN file_data s ON s.id = e.src_file_id
         WHERE e.edge_kind = 'import' AND s.language = f.language
           AND s.repo_name = f.repo_name AND s.commit_hash = f.commit_hash) AS edges
FROM file_data f
WHERE f.repo_name = ? AND f.commit_hash = ?
GROUP BY f.language ORDER BY captures DESC;
```

---

## Idiom Wrappers in `_master.db` (`wrapper_data`, epic #3313)

A literal-vocabulary rule (`debug_prints`, `panics_and_aborts`, `memory_alloc`) counts calls to a primitive by name, so a project's own helper hides every call site behind it (fortran/wrf's `wrf_error_fatal`; curl 8.18's `curlx_*` allocator macros; see `docs/known_blind_spots.md`). `wrapper_data` records those helpers as **facts**, one row per wrapper and rule, with the call sites resolved to it repo-wide. The literal signals are unchanged and no score reads this table.

| column | meaning |
|---|---|
| `file_id` → `file_data.id` | the file that DEFINES the wrapper (a macro's first definition) |
| `wrapper_name`, `kind` | the name, and `function` or `macro` (a function-like `#define`) |
| `rule` | the literal rule it hides |
| `via` | `primitive` (its body hits the rule) or `via <wrapper>` (it reaches the rule through another wrapper) |
| `call_sites`, `calling_files` | unqualified call sites resolved to it, and how many files they are in |

Scope, from measurement (`core/wrapper_resolver.py`'s header): `debug_prints`/`panics_and_aborts` are short, branchless function wrappers in every by-name language; `memory_alloc` is C/C++/Objective-C only, with function wrappers, `#define` aliases and the closure between them. Each file's raw input is `file_data.wrapper_facts` (JSON), restored on delta scans.

## The Mainframe Boundary in `_master.db` (`call_site_data`, `dataset_data`, `transaction_data`, #3200/#3201/#3211-followup)

`ipc_rpc_bridges` and `io` count *that* a COBOL program calls out and touches files. These tables carry *what*, extracted by `core/mainframe_boundary.py` off the prism code stream and resolved by `core/invocation_resolver.py`. A language opts in with a top-level `boundary_extraction` declaration (cobol, jcl, csd, pli).

`record_data` (#3246) carries COBOL DATA DIVISION items and, since #3250, PL/I `DECLARE`d structures in the same columns: `pic` is the PICTURE, `usage` the data type as written (`FIXED DEC(7,2)`, `CHAR(10) VARYING`), `section` the root's storage class (`STATIC`/`AUTOMATIC`/`BASED`/`CONTROLLED`), `redefines` the `DEFINED` base, `occurs_*` the first dimension and `occurs_depending_on` its `REFER`, `value_literal` the `INIT`. `attributes` holds a PL/I item's full attribute text (`BASED(ADDR(REC)) UNALIGNED`) and is NULL for COBOL.

`dataset_data` (#3201) carries, since #3345, `dsn_resolved` (the JCL DSN with its SET / PROC-default / EXEC-override symbols substituted, NULL unless every one resolved) and `dsn_resolution` (`literal`, `resolved`, `proc_default` — only a PROC's own defaults, a caller elsewhere may override — `ambiguous` or `unresolved`) beside the raw `dsn`; both NULL on a COBOL row. `galaxy_ir` joins lineage on the resolved name (`shared_datasets`, `dataset_flows`).

### `sql_table_data` — DB2 DECLARE TABLE / DCLGEN schemas (#3344)

One row per column of an `EXEC SQL DECLARE <table> TABLE (...)`, inline in a COBOL/PL/I program or DCLGEN-generated into a copybook/include member: `table_name` (as declared, `owner.table` whole), `table_line`, `colno` (1-based, SYSCOLUMNS.COLNO), `column_name`, `sql_type` as written (`DECIMAL`, `VARCHAR`, `TIMESTAMP WITH TIME ZONE`), `length` (length/precision, LOB K/M/G applied) and `scale` -- both NULL when the source writes none -- `nullable` (0 exactly on NOT NULL), `attributes` (the option text after the type) and `line_number`. Per-file, cascade-deleted with `file_data`, restored on delta scans. Same-file only: a program reaches its DCLGEN member through the `EXEC SQL INCLUDE` edge.

### `screen_field_data` — BMS screen-field layouts (#3347)

One row per `DFHMSD` (`kind` 'mapset'), `DFHMDI` ('map') and `DFHMDF` ('field') of a BMS map source, the tree in `ordinal`/`parent_ordinal`. A field has its geometry in `pos_line`/`pos_column`/`length`, its `attrb` list, `picin`/`picout`, `initial_value` (the INITIAL literal, continuations rejoined) and `occurs`; `field_name` is NULL for a screen literal (an unnamed field, which never reaches the symbolic map). Every other operand stays as written in `attributes` (`COLOR=`, `HILIGHT=`, a map's `SIZE=`, a mapset's `MODE=`/`LANG=`). A dedicated table rather than a `record_data` dialect: screen geometry and 3270 attributes have no record column, and a map is not storage.

### `transaction_data` — the CICS transaction map (#3211-followup)

The CSD `DEFINE TRANSACTION(TTTT) ... PROGRAM(PPPP)` records (and PROGRAM autoinstall `TRANSID(...)` pairings), from `.csd` decks and DFHCSDUP SYSIN inside JCL. This is the external front door: which 4-char transaction id a user submits and which program CICS routes it to — the entry points a modernizer turns into service/API boundaries.

| column | meaning |
|---|---|
| `file_id` → `file_data.id` | the `.csd`/JCL deck the definition lives in |
| `transid` | the transaction id (a name, not a file — like `dataset_data.dd_name`) |
| `program` | the PROGRAM-ID it routes to, as written |
| `dst_file_id` → `file_data.id` | the file declaring that PROGRAM-ID, or NULL for a program not in this repository |
| `group_name` / `profile` | the CSD GROUP and PROFILE attributes |

The in-source routing (`EXEC CICS RETURN/START/RUN TRANSID(...)`) rides in `call_site_data` under its own verbs; `galaxy_ir.transaction_map` joins the two. Like `dataset_data`, this is deliberately *not* an `edge_data` kind — a transaction id is not a file.

### `call_site_data` — one row per invocation site

COBOL `CALL`, CICS `LINK`/`XCTL PROGRAM(...)`, JCL `EXEC PGM=`.

| column | meaning |
|---|---|
| `src_file_id` → `file_data.id` | the calling file |
| `verb` | `CALL`, `LINK`, `XCTL`, `EXEC PGM` |
| `form` | `literal` (static, link-edited) or `identifier` (dynamic dispatch, read through the data item's `VALUE` clause) |
| `operand` | the operand as written (`WS-ABEND-PGM`) |
| `target` | the program name it denotes (`ABNDPROC`), or NULL when even the name could not be read |
| `dst_file_id` → `file_data.id` | the file declaring that PROGRAM-ID, or NULL |
| `line_number` | the source line of the verb |

The unresolved rows are the point, not a gap — they are what the refraction pipeline's `unresolved_calls` used to be, with the level of failure distinguishable:

| shape | meaning |
|---|---|
| `target IS NULL` | dynamic dispatch the engine could not follow (the `VALUE` clause lives in a copybook) |
| `target NOT NULL, dst_file_id IS NULL` | named, but external — an LE service (`CEEGMT`), a system utility (`IEFBR14`), or a module this repository does not contain |
| `dst_file_id NOT NULL` | resolved; there is a matching `edge_data` row of kind `'call'`/`'exec'` |

Resolution is by **PROGRAM-ID** (`class_data`), not by filename, and when a PROGRAM-ID is shared the **nearest** declaration wins — a different rule from the import resolver, which disqualifies any candidate declaring a PROGRAM-ID and draws nothing when its own narrowing leaves a tie (#3199). The two relations differ: a copybook is named by file, a called program is chosen by library concatenation order.

### `dataset_data` — one row per dataset boundary fact

| column | COBOL row | JCL row |
|---|---|---|
| `internal_name` | the `SELECT` file name (`CUSTOMER-FILE`) | NULL |
| `assign_name` | the `ASSIGN TO` operand as written (`UT-S-CUSTFILE`) | NULL |
| `dd_name` | that operand with its device prefix stripped (`CUSTFILE`) | the ddname |
| `access_modes` | the `OPEN` modes actually used, comma-joined (`INPUT`, `I-O,OUTPUT`) | NULL |
| `step_name` | NULL | the `EXEC` step the DD belongs to |
| `dsn` | NULL (`dsn IS NULL` identifies a COBOL row) | the dataset the DD binds |

Joining the two halves on `dd_name` is the dataset lineage:

```sql
-- "program P opens DD X for MODE; job J step S binds DD X to dataset D"
SELECT pf.file_path AS program, p.dd_name, p.access_modes,
       jf.file_path AS job, j.step_name, j.dsn AS dataset
FROM dataset_data p
JOIN file_data pf ON p.file_id = pf.id
JOIN call_site_data c ON c.dst_file_id = pf.id AND c.verb = 'EXEC PGM'
JOIN file_data jf ON c.src_file_id = jf.id
JOIN dataset_data j ON j.file_id = jf.id AND j.dd_name = p.dd_name
WHERE p.dsn IS NULL;
```

`gitgalaxy/tools/cobol_to_cobol/galaxy_ir.py` exposes both as `GalaxyIR.dataset_lineage()` and `GalaxyIR.unresolved_calls()`.

**Delta mode.** `state_rehydrator.py` restores both tables for unchanged files, the same way it restores `raw_imports` (#3220) — without that, an incremental scan would describe only the files that changed in the last commit. Resolution (`dst_file_id` / `resolved_path`) is deliberately *not* restored and is redone every scan, because a file added or deleted this commit can change what an unchanged file's `CALL` resolves to.

**What these tables are not.** The call edges are a separate `edge_kind` and are never handed to the DiGraph, so `pagerank_score`, `popularity`, `internal_dependency_links`, betweenness and every risk score are unchanged by them. There is no reachability here: an `OPEN` inside an unreachable paragraph is still extracted, because the engine has no reachability model (`docs/unreferenced_by_name_contract.md` corollary 3). FD/01 record layouts are not extracted.

---

## Standard Orchestrator Output
When running the `galaxyscope.py` orchestrator without exclusive flags, the engine automatically routes the centralized RAM state through all recorders, emitting the following standard artifacts for a given target (e.g., `project-name`):

* `project-name_galaxy_gpu.json` (WebGL UI Payload)
* `project-name_galaxy_master.db` (Relational SQL Database)
* `project-name_galaxy_sarif.json` (CI/CD Security Alerts)
* `project-name_galaxy_sbom.json` (CycloneDX Dependency Manifest)
* `project-name_galaxy_audit.json` (Human-Readable Compliance Log)
* `project-name_galaxy_llm.md` (Compressed Context Window Brief)

---

## Powered by the blAST Engine

This documentation is part of the [GitGalaxy Ecosystem](https://squid-protocol.github.io/gitgalaxy/), an AST-free, LLM-free heuristic knowledge graph engine.

* **[GitGalaxy Official Documentation](https://squid-protocol.github.io/gitgalaxy/)** - Deep dives into the mathematics and pipeline architecture.
* **[GitGalaxy Visualizer](http://gitgalaxy.io/)** - Render your codebase locally in 3D using WebGPU.
* **[The blAST Paradigm Wiki](https://squid-protocol.github.io/gitgalaxy/docs/wiki/01-03-the-blast-paradigm/)** - The academic and structural thesis backing the engine.
* **[Language Calibration Standards](https://github.com/squid-protocol/gitgalaxy/blob/main/gitgalaxy/standards/how_to_add_a_language.md)** - Guide to extending the comparative lexical taxonomy.