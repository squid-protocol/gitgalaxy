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
| DATA DIVISION record layouts | #3246 | `core/mainframe_boundary.py` | `record_data` | `EngineFile.records` |
| PL/I DECLARE structures (a second dialect on an existing table) | #3250 | `core/mainframe_boundary.py` (`_pli_records`) | `record_data` (+ `attributes`) | `EngineFile.records` |
| project-local idiom wrappers (global/resolved, NOT mainframe) | #3313 | `core/wrapper_extractor.py` + `core/wrapper_resolver.py` | `wrapper_data` (+ `file_data.wrapper_facts`) | per-file `idiom_wrappers` |
| DB2 `DECLARE TABLE` / DCLGEN schemas (own table: SQL types don't fit `record_data`) | #3344 | `core/db2_declare_table.py` (via `extract_boundary`, cobol + pli) | `sql_table_data` | `EngineFile.sql_tables` |

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

## Invariants (hard rules — each cost a real incident)

1. **Declaration is top level, not `rules`** (#2806). Config compiles `rules` strings to regexes.
2. **The full audit report carries the facts, so a channel MOVES the golden master — re-bless it.**
   (This reversed with #3246 step 4b: the forensic report used to omit these, which is why the
   original channels were golden-master-neutral.) `*_galaxy_audit.json` is `crucible-audit`'s
   fixture, and the crucible corpus contains cobol/jcl, so adding your block changes
   `golden_master_audit.json` + `golden_master_zero_dep_audit.json`. Regenerate BOTH with
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
