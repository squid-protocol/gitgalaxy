# IBM DB2 SQL / SQL PL — Structural Signature Coverage

Snapshot written 2026-09-16 with the language's addition (#2511, under the legacy-mainframe
epic #2516). Source: `LANGUAGE_DEFINITIONS["db2_sql"]` in
`gitgalaxy/standards/language_standards/languages/db2_sql.py` and
`tests/extraction/languages/test_db2_sql_strict.py`. Re-run the `language-status` skill's
data-gathering commands before trusting these numbers if this doc looks old relative to
`last_updated` below.

**Scope note:** DB2 SQL is tree-sitter-blind to this repo's comparison tooling (the jcl/cobol/
sqlite position), and no ground-truth parser diff was run, so there is no §9. The pinned
language-crucible corpus carries no DB2 sources — its `.sql` files are all genuinely SQLite
(and stayed classified that way through this change; see §5). Adding a real DB2 schema dump to
the crucible is a follow-up. The rules were validated by the 141-case strict suite and by
end-to-end routing checks on synthetic mainframe/webapp trees, not yet by a large real-file
probe like pli's 1,560-file pass.

## 1. At a glance

| Field | Value |
|---|---|
| `_meta.status` | `production` |
| `_meta.target_version` | IBM Db2 13 for z/OS SQL / SQL PL (also Db2 12 FL 510 and LUW 11.5) |
| `_meta.blueprint_version` | v6.3 |
| `_meta.last_updated` | 2026-09-16 |
| `lexical_family` | `multi_style_dash` — `--` line comments plus non-nesting `/* */` blocks, sqlite's family. Issue #2511 said `standard_block`; that family is C's `//` shape and never strips `--` at all (the exact defect #621 fixed for sqlite), so the issue text was corrected at implementation. Pinned by a `Prism.split_streams()` test. |
| Structural signature keys wired | 43 / 53 (10 explicit `None`, see §4) |
| Extraction-gauntlet tests | — (strict suite drives the real extractor directly) |
| Strict-signature tests (`test_db2_sql_strict.py`) | 141 |

## 2. Identification surface — the `.sql` collision (#2511's core requirement)

`db2_sql` claims exactly the extensions sqlite already claimed (`.sql`, `.ddl`, `.dml`), on
purpose. All three are therefore registered in `_lens_config.py`'s `COLLISION_FREQUENCIES`, so
Tier 1 never locks them on extension alone (without that entry, `_calibrate_lookup_maps`'
registration-order overwrite would silently hand all three to whichever profile registered
last). Routing then resolves in order:

1. **Tier 2 — `internal_discriminator`** (raw content, pre-comment-strip): tokens no SQLite
   script can carry — z/OS storage DDL (`TABLESPACE`, `BUFFERPOOL`, `STOGROUP`,
   `CCSID EBCDIC`), special registers (`SET CURRENT SQLID`), `WLM ENVIRONMENT`, the
   `SYSIBM`/`SYSCAT`/`SYSPROC` catalog, SQL PL's `... HANDLER FOR`, `EXECUTE IMMEDIATE`,
   `LANGUAGE SQL`, and SPUFI/DSNTEP2's `--#SET` directive line. sqlite deliberately has no
   internal_discriminator, so a DB2 fingerprint wins outright and a plain SQLite script falls
   through.
2. **Tier 1.5 — ecosystem gravity**: discriminators `.cbl`, `.cob`, `.cpy`, `.jcl`, `.bms`,
   `.pli`, `.pl1` (the mainframe sources that live beside DB2 DDL). A fingerprint-less `.sql`
   file in a COBOL/JCL neighborhood routes to db2_sql; in a plain repo sqlite's own
   discriminators (`.sql` itself, `.db`, `.sqlite*`) keep it dominant. Disqualifiers
   `.sqlite`, `.sqlite3`, `.db3`, `.s3db`, `.sl3` collapse the DB2 claim to 0 in a repo
   carrying actual SQLite database artifacts.
3. **Tier 3 — lexical scan** as the last resort, over both candidates' rules.

No shebangs (SPUFI/DSNTEP2/CLP scripts have none), no exact filenames.

## 3. What GitGalaxy detects

The x/y/z coverage #2511 asked for, plus the rest of the baseline schema. Identifier guards
use `[\w#$@]` throughout — `#`, `$`, `@` are ordinary DB2 identifier characters on z/OS.
Delimited identifiers are double-quote only; the quotes stay inside capture group 1 and
`detector.py` strips the pair (sqlite's epic #813/#836 convention, extended to db2_sql).

### Topology (x)
- **`func_start`** — `CREATE [OR REPLACE] PROCEDURE | FUNCTION | TRIGGER`, with up-to-3-part
  qualified names (`location.schema.object`), vertical formatting gaps, and quoted names.
- **`class_start`** — `CREATE TABLE` (incl. `GLOBAL TEMPORARY`), `CREATE VIEW`, and
  `CREATE [LARGE] TABLESPACE` — the physical container an enterprise schema cannot exist
  without. Named-class extraction is enabled via `_CLASS_START_NAMED_EXTRACTION_LANGS`.
- **`args`** — the declared parameter list anchored to `PROCEDURE`/`FUNCTION` (a `CALL`'s
  argument list never counts), plus `?` markers and `:host` variables.
- Extraction runs through **Mode E terminator cleaving** (the `"db2_sql": "sql"` alias in
  `detector.py`), sqlite's `CREATE_Statement`/`Declarative_Block` bucket model (#2792).

### Business logic in stored procedures (y)
- **`branch`** — SQL PL `IF`/`ELSEIF`/`ELSE`, `CASE`/`WHEN`, `WHILE`, `REPEAT`/`UNTIL`, the
  cursor `FOR name AS` loop, plus `WHERE`/`HAVING`/`COALESCE`/`NULLIF`. `END IF`/`END WHILE`/
  `END REPEAT`/`END CASE` closers are excluded (#2822 C2); `LEAVE`/`ITERATE`/`GOTO` are
  unconditional transfers (GOTO is safety_bypasses').
- **`state_mutation`** — statement-anchored `INSERT INTO` / `UPDATE` / `MERGE INTO`, and SQL
  PL's `SET var =` at a statement start. One statement is one hit: a MERGE's internal
  `WHEN MATCHED THEN UPDATE SET` and a line-wrapped `UPDATE ... SET` clause do not double
  count (both pinned). `DELETE` is cleanup's — see §5's deviation ledger.

### Database mechanics (z)
- **`encapsulation`** — statement-anchored `GRANT` / `REVOKE`, and
  `DECLARE GLOBAL TEMPORARY TABLE` (session-private state).
- **`io`** — cursor `OPEN` and `FETCH` (with `FETCH FIRST` excluded as a query clause), plus
  the CLP's file-crossing `IMPORT FROM` / `EXPORT TO` / `LOAD FROM`. `CLOSE` is cleanup's —
  see §5.
- **`high_risk_execution`** (#2878) — dynamic SQL (`EXECUTE IMMEDIATE`, `PREPARE ... FROM`,
  `EXECUTE` of a prepared statement, guarded so the GRANT-list `EXECUTE` privilege never
  fires), utility handoff (`SYSPROC.ADMIN_CMD` / `DSNUTILU`), whole-store destruction
  (`DROP DATABASE|TABLESPACE|STOGROUP`, `TRUNCATE`), and the authorization switch
  `SET CURRENT SQLID` (dual with globals).
- **`memory_alloc`** — #2511's physical-storage dimension: `PRIQTY`/`SECQTY`/`PCTFREE`/
  `FREEPAGE` numbers, `BUFFERPOOL` and `STOGROUP` assignments, `ALLOCATE ... CURSOR`.
- **`safety`** — SQL PL condition handlers (`CONTINUE|EXIT|UNDO HANDLER FOR`), transactions,
  `BEGIN ATOMIC`, declared constraints. **`safety_bypasses`** — `NOT LOGGED [INITIALLY]`,
  `SET INTEGRITY ... IMMEDIATE UNCHECKED`, the DROP family, `GOTO`.
- **`globals`** (#2858) — special registers (`CURRENT SQLID|SCHEMA|SERVER|...`), the USER
  registers, the `SYSIBM`/`SYSCAT`/`SYSPROC` catalog, `CREATE VARIABLE`.
- Plus: `panics_and_aborts` (SIGNAL SQLSTATE/RESIGNAL/RAISE_ERROR), `sync_locks` (LOCK TABLE,
  SHARE/EXCLUSIVE modes, FOR UPDATE, WITH HOLD), `concurrency` (WITH UR/CS/RS/RR isolation,
  SKIP LOCKED DATA, CURRENT DEGREE), `telemetry` (RUNSTATS, MON_GET_*, event monitors),
  `serialization_parsing` (JSON_*/XML* built-ins), `regex_execution` (REGEXP_* family, LIKE),
  `explicit_casts` (CAST/XMLCAST), `time_date_logic` (registers + call-form built-ins;
  `TIMESTAMP(6)` column precision excluded), `import`/`_dependency_capture` (`CONNECT TO`),
  and the comment-stream rules (dead_code/doc/ownership/debt/spec_exposure, both `--` and
  `/* */` styles per Rule 12).

## 4. What GitGalaxy explicitly does not track (`None` keys, 10)

`ui_framework`, `closures`, `generics`, `hardcoded_secrets` (security lens covers it),
`dependency_injection`, `ssr_boundaries`, `pointers`, `inline_asm`, `test_skip`, and
**`macros`** — SPUFI's `--#SET TERMINATOR` directive is real but lives on a `--` comment line,
and code-stream rules never see the comment surface (Rule 18); the directive still anchors the
Tier-2 internal_discriminator, which runs on raw content.

## 5. Deliberate deviations from the issue text (ledgered)

1. **`lexical_family`** — `multi_style_dash`, not the issue's `standard_block` (§1).
2. **`CLOSE`** — cleanup's, not io's (#2841 C2: releasing a resource is cleanup's). The
   issue's io list said FETCH/OPEN/CLOSE; OPEN/FETCH stay io's.
3. **`DELETE`** — cleanup's, not state_mutation's (#2843/#2888 and sqlite parity: removal of
   entries from a live store). The issue's state_mutation list said
   INSERT/UPDATE/DELETE/SET/MERGE.
4. **`invocation_model: "positional"`** — sqlite's exact #2866 position (corollary 4), and
   a correction the rosetta control corpus forced during landing: the first draft kept the
   `by_name` default on the reasoning that `CALL SP1` reaches a procedure by name, but the
   units `func_start` feeds are Mode E's *statement buckets* (`CREATE_Statement`), and no
   syntax reaches a statement by its extracted name — `CALL SP1` invokes the database
   object, not the unit. The corpus exposed it empirically: `raw_state_unreferenced` read
   a flat 0 against a 2.50 by_name median (bucket labels always "recur"), exactly the
   too-clean census #2866 warns about. Declared positional; the census is not computed.

Each is pinned by a dedicated strict test. Intended duals also pinned: CREATE TRIGGER
(func_start+events), CREATE VIEW (class_start+api), SET CURRENT SQLID
(high_risk_execution+globals), DROP TABLE (safety_bypasses+cleanup), trigger timing clauses
(events+listeners).

## 6. Test depth

141 strict cases in `test_db2_sql_strict.py`: per-rule positive/negative coverage for every
non-`None` key, schema completeness against the 53-key baseline, registration and collision
wiring (COLLISION_FREQUENCIES membership, discriminator/disqualifier sets), a
`Prism.split_streams()` lexical-family proof, a re.M audit, internal-discriminator
separation on realistic DB2 vs SQLite scripts, an ecosystem-gravity arithmetic check
(mainframe repo ≥70% db2_sql, plain repo ≥70% sqlite, `.sqlite3` artifact collapses the
claim), one-statement-one-hit counting, the real extractor through Mode E with named-class
extraction, and a 36-payload ReDoS detonation sweep at n=200,000. The sweep caught one real
Rule-14 defect during authoring — sqlite's `CAST` idiom
(`(?:[^()]{0,500}|\(...\)){0,500}`) hangs on `CAST(` + a long unclosed run — and db2_sql
ships a linear replacement (sqlite's own copy is a candidate for the same fix; see
harden-strict-signatures).

## 7. Relevant work

- #2511 — this addition. #2516 — the legacy-mainframe epic it belongs to.
- #2502 (pli) — the sibling addition whose discriminator set and strict-test shape this
  follows. #621 — the multi_style_dash family sqlite's identical comment surface landed on.
- #2792 — sqlite's Mode E statement-bucket model, reused verbatim via the `"sql"` alias.
- Golden masters: regenerated in both environments with this change. All 320 fixture line
  changes are Artifact Identity metadata (Lock Tier / Identity Proof) on crucible `.sql`
  files whose *language did not change* — the expected effect of `.sql` becoming a contested
  extension (Tier-0/2 extension locks became Shebang-only or Ecosystem Consensus locks, and
  sqlite still wins its own corpus everywhere).

## 8. Rosetta cross-language consistency (control-corpus capstone)

Pending: the `data/db2_sql/` control folder is authored on keyword-rosetta branch
`corpus/db2sql-2511` (this change's companion PR, per `how_to_add_a_language.md`'s closing
section). The fidelity-table re-pin (`FIDELITY_PROVENANCE` corpus_sha + language count)
follows once that PR merges — pli is in the same waiting position.

## 9. Embedded SQL in COBOL / PL/I: fact channels (added 2026-09-25)

This doc covers standalone DB2 SQL / SQL PL files. **Embedded** `EXEC SQL` in COBOL and PL/I is
read by two fact channels (see [cics_mainframe_facts.md](cics_mainframe_facts.md)):

- **`core/db2_sql_statements.py` (#3446):** which program reads, inserts, updates or deletes which
  table. A cursor's OPEN / FETCH is joined to its DECLARE. Cross-verified on CardDemo (13 facts),
  CBSA (24) and GENAPP (21).
- **`core/db2_declare_table.py` (#3344):** `DECLARE TABLE` / DCLGEN column schemas. Draft on
  CardDemo (31) and CBSA (24): two independent readers agree, no blind review yet.

Not covered:
- dynamic SQL text built at runtime (`PREPARE` from a host variable), which gets no table fact;
- stored-procedure bodies' table access, which is not joined to the calling COBOL program;
- the BIND / plan → package mapping, which comes only from the CSD's DB2ENTRY / DB2TRAN, when the
  CSD is present.
