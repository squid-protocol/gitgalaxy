# How to add a fact channel

A **fact channel** carries a *named, system-defined relation or schema* out of the engine and
into the master DB — the kind of knowledge the per-file structural **signal counts** flatten. The
counted rules tell you **that** a program calls out, touches a file, or declares data; a fact
channel tells you **what**: which program it calls, which dataset a DD binds, what the record
layout is. These are facts about a **platform** (the mainframe family: COBOL/JCL/CICS/BMS/…), not
about one language's grammar.

Three channels exist today and are the worked references — read the one closest to your case
before writing anything:

| channel | issue | extractor | table | IR accessor |
|---|---|---|---|---|
| invocation (call graph) | #3200 | `core/mainframe_boundary.py` + `core/invocation_resolver.py` | `call_site_data` | `EngineFile.calls` |
| dataset boundary/lineage | #3201 | `core/mainframe_boundary.py` | `dataset_data` | `EngineFile.datasets` |
| JCL PROC/SET symbol resolution (resolved columns beside a raw one) | #3345 | `core/mainframe_boundary.py` (`_jcl_resolve_datasets`) | `dataset_data` (+ `dsn_resolved`, `dsn_resolution`) | `EngineFile.datasets` (`dataset_name`; `GalaxyIR.shared_datasets`/`dataset_flows`) |
| CICS COMMAREA contract (operand columns on an existing global table + a reader-side join) | #3355 | `core/mainframe_boundary.py` (`_cics_contract_operands`, `copy_members` on records) | `call_site_data` (+ `commarea`, `commarea_length`, `commarea_datalength`), `record_data` (+ `copy_members`) | `EngineCall.commarea*`; `GalaxyIR.commarea_contracts`/`record_layout` |
| DATA DIVISION record layouts | #3246 | `core/mainframe_boundary.py` | `record_data` | `EngineFile.records` |
| PL/I DECLARE structures (a second dialect on an existing table) | #3250 | `core/mainframe_boundary.py` (`_pli_records`) | `record_data` (+ `attributes`) | `EngineFile.records` |
| CSD resource definitions of every type (one generic table beside the resolved transaction map) | #3356 | `core/mainframe_boundary.py` (`_csd_resources`) | `csd_resource_data` | `EngineFile.csd_resources` (`GalaxyIR.cics_file_datasets`/`tdqueue_datasets`/`transaction_db2_plans`) |
| BMS screen-field layouts (its own table: geometry has no record column) | #3347 | `core/bms_screen_fields.py` (dispatched from `mainframe_boundary`) | `screen_field_data` | `EngineFile.screen_fields` |
| CICS resource operations: FILE / MAP / QUEUE / CONTAINER / CHANNEL (one table for four issues; cross-file joins in the reader) | #3351-#3354 | `core/cics_resources.py` (via `extract_boundary`, cobol + pli) | `cics_resource_data` | `EngineFile.cics_resources` (`GalaxyIR.screen_bindings`/`queue_flows`/`container_flows`) |
| project-local idiom wrappers (global/resolved, NOT mainframe) | #3313 | `core/wrapper_extractor.py` + `core/wrapper_resolver.py` | `wrapper_data` (+ `file_data.wrapper_facts`) | per-file `idiom_wrappers` |
| DB2 `DECLARE TABLE` / DCLGEN schemas (own table: SQL types don't fit `record_data`) | #3344 | `core/db2_declare_table.py` (via `extract_boundary`, cobol + pli) | `sql_table_data` | `EngineFile.sql_tables` |
| embedded SQL statements: which tables a program reads / inserts / updates / deletes (cursor OPEN/FETCH joined to its DECLARE in the reader) | #3446 | `core/db2_sql_statements.py` (via `extract_boundary`, cobol + pli) | `sql_statement_data` | `EngineFile.sql_statements` (`GalaxyIR.sql_table_access`) |
| CICS task control: RUN/START children (a STRING-built transid kept as a PIC-sized fnmatch pattern), FETCH/FREE joins, RETRIEVE, DELAY, POST, WAIT, ENQ/DEQ (children joined to the CSD in the reader) | #3449 | `core/cics_tasks.py` (via `extract_boundary`, cobol + pli) | `cics_task_data` | `EngineFile.cics_tasks` (`GalaxyIR.async_tasks`) |
| job submission through the internal reader: JCL JOB/EXEC card literals in COBOL, JCL DDs routed to SYSOUT=(x,INTRDR) (WRITEQ TD -> extrapartition TDQUEUE -> job joined in the reader) | #3448 | `core/job_submits.py` (via `extract_boundary`, cobol + jcl) | `job_submit_data` | `EngineFile.job_submits` (`GalaxyIR.job_submissions`) |
| IBM MQ calls: queue through the descriptor's OBJECTNAME (trigger / reply_to named, never guessed), direction, options, handle -> its MQOPEN (producer/consumer pairing in the reader) | #3447 | `core/mq_calls.py` (via `extract_boundary`, cobol) | `mq_call_data` | `EngineFile.mq_calls` (`GalaxyIR.mq_queues`/`mq_flows`) |
| units of work and error handling: SYNCPOINT / SQL COMMIT / ROLLBACK, HANDLE CONDITION / ABEND / AID, explicit ABEND, RESP checks tied to their command (owning paragraph and TD trigger starts in the reader) | #3453 | `core/uow_handlers.py` (via `extract_boundary`, cobol) | `uow_handler_data` | `EngineFile.uow_handlers` (`GalaxyIR.units_of_work`/`error_handlers`/`unchecked_responses`/`tdq_trigger_starts`) |
| file definitions: FILE-CONTROL SELECT organisation / access / keys / FD COPY members (cobol) and IDCAMS DEFINE CLUSTER / AIX / PATH (jcl in-stream); the reader checks each RECORD KEY's offset/length against the cluster's KEYS | #3455 | `core/file_control.py` (via `extract_boundary`, cobol + jcl) | `file_control_data`, `vsam_define_data` | `EngineFile.file_control` / `vsam_defines` (`GalaxyIR.vsam_files`) |
| JCL job flow: step order, COND= / IF-ELSE conditions, PROC calls (expanded in the reader), each DSN DD's DISP and GDG generation (dataset producer -> consumer edges in the reader; scheduler order out of scope) | #3451 | `core/job_flow.py` (via `extract_boundary`, jcl) | `job_flow_data` | `EngineFile.job_flow` (`GalaxyIR.job_steps`/`job_dataset_flow`) |
| batch CALL USING contracts: each CALL's USING list (a column on call_site_data, like #3355's COMMAREA) and each PROCEDURE DIVISION / ENTRY USING parameter list (paired by position, arity and byte length in the reader) | #3454 | `core/call_using.py` (via `extract_boundary`, cobol) | `call_site_data.using_args`, `entry_point_data` | `EngineCall.using_args`, `EngineFile.entry_points` (`GalaxyIR.call_contracts`) |
| IMS DL/I calls: EXEC DLI and CALL 'CBLTDLI' with operands as written (function codes and SSAs resolved through COPY-expanded VALUEs, and the program x segment matrix, in the reader; the PSB / DBD check is #3477's) | #3450 | `core/dli_calls.py` (via `extract_boundary`, cobol) | `dli_call_data` | `EngineFile.dli_calls` (`GalaxyIR.ims_calls`/`ims_segment_access`) |
| IMS PSB / DBD definitions: PSBGEN / PCB / SENSEG / DBD / SEGM / FIELD / LCHILD / DATASET macros of `.psb` / `.dbd` members (hlasm), and JCL `DFSRRC00` region steps (program + PSB); the program -> PSB join (region or EXEC DLI SCHD) and each segment access checked against SENSEGs and PROCOPT in the reader | #3477 | `core/ims_gen.py` (via `extract_boundary`, hlasm + jcl) | `ims_gen_data` | `EngineFile.ims_gen` (`GalaxyIR.ims_psbs`/`ims_databases`/`ims_program_psbs`/`ims_access_check`) |
| field-level data movement: one source -> target row per MOVE / COMPUTE / ADD / SUBTRACT / MULTIPLY / DIVIDE / STRING / UNSTRING / INITIALIZE, and (#3492) READ / RETURN INTO, WRITE / REWRITE / RELEASE FROM, ACCEPT, operands as written (storage resolution -- record, offset, width, so group moves and REDEFINES meet by storage -- truncation, and cross-program lineage to the channel endpoints in the reader) | #3452 | `core/data_moves.py` (via `extract_boundary`, cobol) | `data_move_data` | `EngineFile.data_moves` (`GalaxyIR.data_flows`/`field_lineage`) |
| COBOL symbolic maps of BMS mapsets (a reader derivation, no table): the DFHMAPS layout generated from `screen_field_data` for a `COPY <mapset>` no real copybook answers | #3490 | `core/bms_symbolic.py` (from the #3347 screen fields) | -- (`screen_field_data`) | `EngineFile.symbolic_copies` (`GalaxyIR.symbolic_map_layouts`; resolved by `_find_item` / `_storage_spans`) |
| remote programs / function shipping (a column + reader joins): a CICS LINK / START's `SYSID(...)`, joined with the CSD's REMOTESYSTEM / REMOTENAME definitions of PROGRAM / TRANSACTION / FILE / TDQUEUE / TSMODEL | #3494 | `core/mainframe_boundary.py` (`_CICS_CONTRACT_OPERANDS`) | `call_site_data.sysid` (+ `csd_resource_data`) | `EngineCall.sysid` (`GalaxyIR.remote_programs`/`remote_calls`/`remote_resources`; `navigation` edges' `remote_systems`) |
| web / API services: the CICS web-services assistant steps (DFHLS2WS / DFHLS2JS providers, DFHWS2LS / DFHJS2LS requesters) with PGMNAME / URI / REQMEM / RESPMEM / PGMINT / WSBIND / WSDL from their in-stream parameters; program + copybook joins and the CSD URIMAP / PIPELINE / WEBSERVICE / TCPIPSERVICE definitions in the reader (program-side WEB / INVOKE / TRANSFORM: 3512) | #3496 | `core/web_services.py` (via `extract_boundary`, jcl) | `web_service_data` | `EngineFile.web_services` (`GalaxyIR.api_surface`; completeness counts exposed programs reached) |

The wrapper channel (#3313) is the first global/resolved channel whose raw per-file input is not
itself a table: `file_data.wrapper_facts` (JSON, the #3220 `raw_imports` precedent) carries each
file's candidates and call sites, the rehydrator restores it, and `wrapper_resolver` re-resolves the
whole repository every scan. Its decision rules were measured with a probe and hand labels first
(`tests/tools/wrapper_probe.py`, `wrapper_labels.json`) and the engine stays inside that measured
scope -- see the resolver's header.

A **sibling dialect feeding an existing table** (#3250) is the cheapest channel: a new extractor, a
new `boundary_extraction` value, and the spine as built. Map its attributes onto the existing
columns only where the meaning is the same (PL/I `DEFINED` is COBOL `REDEFINES`; `BASED(p)` names a
pointer, so it is not), and carry the rest in one generic text column rather than forcing it into a
column shaped for the first dialect. A new column needs `_ensure_columns` (an older DB heals on the
next record) and a column-gated read in the rehydrator and reader (an older baseline still loads).
If no forge reads the new dialect, the differential's compared side is an INDEPENDENT reader in the
answer key -- a separately written parser over the raw file -- which is also how #3250 caught an
engine gap (orphaned sequence numbers hid 179 of navikt/DSF's 1,473 files) before it shipped.

## Is it a fact channel? (the decision that comes first)

Ask: **is this a count, or a named relation/schema?**

- A **count** (a new operator, a comment form, a loop kind) is a *signal*. It belongs in the
  per-language rules — use the `add-signal` / `add-language` skills, **not** this doc. Signals are
  syntax-derived and cross-language comparable by design; that is the whole "one graph, not five
  tools" thesis and it must not be diluted with bespoke per-language data.
- A **named relation** ("A calls B", "job J binds DD X to dataset D") or a **schema** (a record
  layout, a message definition, a table's columns) is a *fact*. It has no meaningful flat count and
  no cross-language comparability — it is a channel.

If the answer is "a count", stop; you are in the wrong doc.

## Two halves: a bespoke extractor, a reusable spine

A channel is **not** symmetric. Only half of it is generic.

- **The extractor is always bespoke and always syntax-specific.** `_cobol_records()` parses PIC
  clauses and level numbers — that is irreducibly COBOL. Every channel writes its own extractor to
  the ReDoS-bounded regex discipline (see `how_to_add_a_language.md`'s 12 rules; a fact extractor
  obeys them too — bound every scan, never span lines with `[^.]*`).
- **The spine is generic and already built:** a per-file child table with a fixed insert helper, a
  delta-scan restore helper, an IR reader shape, a differential datum, and an answer-key field. The
  spine does not know or care which language produced the facts.

So "adding a channel" is mostly: **write one bounded extractor, then thread its output through the
spine's fixed slots.**

## The spine, step by step (exact seams)

### 1. Declare the dialect — TOP LEVEL, never in `rules`

A language opts in with a top-level key in its definition
(`standards/language_standards/languages/<lang>.py`), e.g. `"boundary_extraction": "cobol"`. It is
a **dialect**, not the language id, so a sibling dialect can share one reading (jcl reuses the
boundary channel; a future pli record reader could reuse cobol's).

> **TRAP #2806 — the single most common failure.** `language_lens.py._calibrate_lookup_maps`
> `re.compile()`s **every string value inside `rules`**. A helper/declaration key put in `rules`
> silently becomes `re.compile("cobol")` and your extractor is never invoked — with every unit test
> still green, because tests build the extractor directly and skip the config pipeline. The
> declaration MUST sit beside `lexical_family` at the top level.

### 2. Write the extractor and return it from the dispatcher

Add your builder to `core/mainframe_boundary.py` (or a sibling core module) and return its output
as a new key from `extract_boundary(dialect, code_stream)`. Read the **PRISM code stream**, never
the raw file (a commented-out construct must not produce a fact). Emit a **flat list of dicts in
source order**; if the fact is a tree, carry `ordinal` + `parent_ordinal` and let the reader
rebuild it — do not nest in the payload.

### 3. Wire the payload key in `galaxyscope.py`

In the boundary block (~L706, where `call_sites`/`dataset_bindings` are set), read your key with a
default and add it to `data_payload` (~L764). `boundary.get("records", [])` — a default, so a
dialect that predates the channel is not a missing-key error. It then propagates via
`data_payload.update(logic_data)` into `parsed_files`.

### 4. Persist a per-file child table (`record_keeper.py`)

- `CREATE TABLE IF NOT EXISTS <name>_data (…, file_id INTEGER, …, FOREIGN KEY(file_id) REFERENCES
  file_data(id) ON DELETE CASCADE)` next to `dataset_data`, plus `idx_<name>_file_id` and
  `idx_<name>_snapshot`. The FK cascade is load-bearing: the idempotent per-snapshot wipe deletes
  `file_data` rows and your children go with them — no explicit DELETE needed.
- Insert with the shared helper `_insert_per_file_child(cursor, parsed_files, path_to_file_id,
  repo_name, commit_hash, table, columns, payload_key, to_row)`. Pass the columns *after* the
  standard `(repo_name, commit_hash, file_id)` and a `to_row(item)` mapping each payload dict to
  those columns. (This is for **per-file** facts. The call graph is different — see "Per-file vs
  global" below.)

### 4b. Report it in the two output surfaces (both optional/presence-keyed)

The master DB is the machine-readable store; two human/LLM-facing reports also carry the fact,
each rendering **nothing** for a file that has none (so a non-mainframe scan is unchanged):

- **Full audit report (`audit_recorder.py`)** — the VERBOSE forensic JSON. Add a
  `_<name>_facts_block(file_data)` returning the FULL detail (every item/edge, mirroring the DB
  table) and attach it as a numbered per-file key only when non-empty. **This is the golden-master
  source (`data_galaxy_audit.json`)** — see invariant #2: adding it here DOES move the golden
  master for any mainframe file in the crucible corpus, so re-bless (`crucible_check.py --update`).
- **LLM brief (`llm_recorder.py`)** — the TOKEN-OPTIMIZED markdown. Add a presence-keyed
  `_<name>_facts_lines(parsed_files)` that returns `[]` unless a file carries the fact, and
  SUMMARISE (e.g. record *roots* with a field count, not the whole tree). Not golden-mastered.

### 5. Restore on delta scans (`state_rehydrator.py`) — NOT optional

An unchanged file is never re-parsed, so without this an incremental scan drops every fact for
unchanged files and the DB ends up describing only what changed last commit. Use the shared helper
`_restore_child_table(cursor, repo_name, baseline_hash, table, select_sql, to_payload)` and assign
`node["<payload_key>"]` in the `ram_state` loop. The `select_sql` aliases the file path `AS _fp`,
aliases every other column to the extractor's payload key names, and takes `(repo, hash)`. Do
**not** restore any repo-wide *resolution* column (see #3200: a `CALL`'s resolved target is redone
every scan). Prove it: a full scan and an incremental scan must produce byte-identical rows
(excluding the autoincrement `id`, which legitimately drifts on delete+reinsert).

### 6. Expose it in the IR reader (`tools/cobol_to_cobol/galaxy_ir.py`)

Add an `@dataclass Engine<Fact>`, a `<facts>: list` field on `EngineFile`, and a read block in
`load_galaxy_ir` **gated by `_has_table(cur, "<name>_data")`** so a pre-channel DB still loads
("no data", never an error). For a tree, rebuild parent/child from `ordinal`/`parent_ordinal` after
loading the flat rows. **Update the `SCOPE` comment** at the top of the file: move the datum from
"NOT in the DB" to "Taken from the DB here". That comment is the contract other tools read.

**Storing the fact is not the same as wiring it in — add the join that actually consumes it.** An
accessor that just hands back rows nobody joins on is dead weight the differential eventually flags
as unused. If the fact resolves something a sibling channel or consumer needs, add or extend the
`galaxy_ir` join, not just the raw field:

- #3345's dataset lineage join is on the **resolved** DSN (`dataset_data.dsn_resolved`), not the
  raw `&HLQ..SAMPLE.CUSTFILE` template — a template can't be joined across two jobs.
- #3368's `cics_file_datasets()` joins CSD `FILE` resource definitions to the batch dataset lineage;
  #3356/#3351-#3354 both feed it, and whichever PR merges second is the one that adds the join.
- #3369's COMMAREA contract exists specifically so a caller's `LINK`/`XCTL` site can be joined to
  the callee's `record_data` LINKAGE layout — the raw `commarea`/`commarea_length` columns alone
  answer "was a COMMAREA passed", the join answers "which record".

Name the join(s) your channel adds or feeds in the PR body, even if it's "none yet — this channel
has no consumer join until <issue>" — an intentionally join-less channel and a forgotten one look
identical in a diff, so say which one this is.

### 7. Make it a compared datum (`tests/tools/refraction_differential.py`)

Add the fact to `compare()` with **both** a forge source and the engine source
(`ef.<facts>`), flatten per-element deltas, and give it a real `cause` in `_classify_cause()`. A
fact the DB now carries is **never** `stated_absence` — that classification is only for datums with
no DB equivalent. A field the engine has that the forge's lossy reader drops is an explained
mechanism (`forge_flat_schema` for record layouts); a field the forge has that the engine missed is
a real engine gap and stays `unexplained` until a validated key adjudicates it. Re-bless:
`refraction_differential.py --update-baseline` (and `--corpus NAME` for the full corpora);
`unexplained` must not rise.

### 8. Grade it against the answer key (`tests/tools/cobol_answer_key.py`)

Add candidate generation to `draft_program()` (using the key's **own** independent reader —
never import the engine or the forge, or the key stops being an oracle), a field to the `fields`
list, and an `add(...)` row in `score()`. Populate the committed keys with the `draft` command; new
fields are committed **drafted** and validated incrementally. If the field is an independent oracle,
add it to `INDEPENDENT_FIELDS` and `_key_verdict()`, and gate the verdict behind an explicit
per-program flag (record layouts use `records_validated`) so drafted truth never adjudicates.

### 9. Tests — mirror the reference trio

`tests/core_engine/test_<extractor>.py` (real corpus shapes, every hard case),
`tests/tools_recorders/test_<name>_data.py` (write path + cascade + no-duplicate on re-record),
`tests/cobol_mainframe/test_galaxy_ir.py` (reader tree + the pre-channel `_has_table` path), and
classifier/scorer cases in the differential + answer-key tests.

## Per-file vs global vs cross-file

- **Per-file** (dataset, record): the fact is fully determined by one file. Use
  `_insert_per_file_child` and `_restore_child_table`. This is the common case.
- **Global/resolved** (the #3200 call graph): the fact needs the whole repository (name → file).
  Extraction is per-file, but resolution runs in `invocation_resolver.py` after all files are seen,
  and `record_mission` takes it as an explicit `call_sites=` parameter, not off the file payload.
  Do resolution repo-wide and redo it every scan; restore only the unresolved half.
- **Cross-file schema** (a future Protobuf/OpenAPI-style channel): the schema in file A is
  referenced by file B. The engine extracts per file (same-file only, like copybooks — a `.cpy`
  carries its own layout); **assembling across files is a consumer's job**, exactly as `copy_deps`
  works. Do not try to expand includes in the extractor.

## Who actually consumes a channel (state this in the PR)

The spine gives a channel four consumers by construction: the differential
(`refraction_differential.py`), the answer key (`cobol_answer_key.py`), the audit JSON, and the LLM
brief. It does **not** automatically reach the forge/refactor pipeline. As of #3348,
`cobol_refractor_controller.process_payload` reads only `program_ids`, `copy_deps`, and `units` off
`EngineFile` — lineage, schemas, and call/transaction routing are still re-derived by the forge's
own parsers from the raw file, even for channels the DB has carried since #3200/#3201/#3246. A new
channel does not close that gap by itself. State the real consumer list in the PR body ("consumed
by: differential, answer key, audit/LLM recorders; not yet the refactor pipeline — #3348") instead
of letting the reader assume the fact is live end to end.

## Rebase / re-bless after a sibling merges

Every #3249-round channel PR (#3349, #3350, #3357, #3368, #3369, #3375) touched the same shared
seams — this doc's channel table, `galaxy_ir.py`'s SCOPE comment and accessors,
`refraction_differential.py`, `cobol_answer_key.py`, `record_keeper.py`, `state_rehydrator.py`,
`audit_recorder.py`/`llm_recorder.py`, and both golden masters — and conflicted with every sibling
PR on exactly those seams (tracked as the shared-seam problem in #3383, the golden-master/ruff-
baseline layout problem in #3384). That cost roughly 8 rebase cycles of 15–40 minutes each in that
round, and one answer-key merge had to be redone by hand. Until #3383's channel registry removes
the shared seams, rebase like this:

1. `git fetch origin` and rebase onto `origin/main` — take **main's side** of any golden-master or
   ruff-baseline conflict wholesale, never hand-merge JSON/baseline entries.
2. Regenerate: `crucible_check.py --update --yes` (both fixtures) and `audit_check.py --regenerate`.
3. **Re-bless only your own drift.** Diff the regenerated golden masters against main and confirm
   every changed key is one your channel added (plus the expected topological X/Y/Z ripple) — if
   anything else moved, you're about to revert a sibling's already-merged channel.
4. `git push --force-with-lease` only — never plain `--force` — since a sibling agent may be
   pushing to overlapping branches concurrently.

`tests/tools/rebase_rebless.py` (#3385, in progress) will automate steps 1–3, including the
own-drift verification, so this stops being a manual, error-prone procedure — until it lands, don't
skip step 3.

## Invariants (hard rules — each cost a real incident)

1. **Declaration is top level, not `rules`** (#2806). Config compiles `rules` strings to regexes.
2. **The full audit report carries the facts, so a channel MOVES the golden master — re-bless it.**
   (This reversed with #3246 step 4b: the forensic report used to omit these, which is why the
   original channels were golden-master-neutral.) `*_galaxy_audit.json` is `crucible-audit`'s
   fixture, and the crucible corpus contains cobol/jcl, so adding your block changes
   `golden_master_audit/` + `golden_master_zero_dep_audit/`. Regenerate BOTH with
   `crucible_check.py --update` and confirm the diff is only your new fact keys (plus the usual
   topological X/Y/Z ripple). Do NOT put the facts in the LLM brief's SQLite graph or hand-edit the
   fixtures.
3. **FK cascade + delta-scan restore, or incremental scans lie.** Both are required; prove
   byte-identical full-vs-incremental.
4. **COBOL/mainframe hyphen boundary:** `-` is a name character, so `\bBINARY\b` matches inside
   `TWO-BYTES-BINARY`. Delimit keywords with `(?<![A-Z0-9-])…(?![A-Z0-9-])`, never `\b`.
5. **Answer keys cover the full pinned corpora, not the committed excerpts.** `mainframe_corpus.py
   fetch` the corpus, and *add* the field to existing keys without regenerating (regenerating wipes
   `validated` status). New fields commit as `draft`.
6. **The answer key is an independent oracle only if it stays independent.** Its reader must not
   import the engine or the forge, and a drafted field must not adjudicate a verdict until signed
   off.
7. **Match CI's pinned tool versions before regenerating ANY baseline.** ruff is pinned in
   `.github/workflows/ruff-audit.yml`; a newer local ruff produces a different finding set, so a
   full local regen drops entries CI still emits and silently breaks the ruff gate. `pip install
   "ruff==<pinned>"` first, or update only the specific line-shifted keys your edit caused.

## Verify (the full gate)

```sh
# extractor + write path + reader
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m pytest \
  tests/core_engine/test_<extractor>.py tests/tools_recorders/test_<name>_data.py \
  tests/cobol_mainframe/test_galaxy_ir.py -q
# real scan → the table is populated
GITGALAXY_DISABLE_GIT_HISTORY=1 GITGALAXY_LICENSE_KEY=COMMUNITY_FREE_TIER \
  .venv/bin/python -m gitgalaxy.galaxyscope <corpus> --db-only --output /tmp/gg
sqlite3 /tmp/gg/<name>_galaxy_master.db "SELECT * FROM <name>_data LIMIT 20;"
# differential: a compared datum, unexplained within baseline
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python tests/tools/refraction_differential.py --ci
# no signal regression + no new lint/dead-key
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python tests/tools/crucible_check.py
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python tests/tools/audit_check.py
```
