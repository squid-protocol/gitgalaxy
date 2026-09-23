---
name: add-fact-channel
description: Add a NAMED SYSTEM FACT to the master DB -- a platform-defined relation or schema the per-file signal counts flatten (the #3200 call graph, #3201 dataset lineage, #3246 record-layout shape), not a syntactic count. Covers the full spine: a top-level dialect declaration, a bounded per-file extractor, a `*_data` child table (via `_insert_per_file_child`), delta-scan restore (via `_restore_child_table`), the `galaxy_ir.EngineFile` reader + SCOPE update, a `refraction_differential` compared datum with a real cause code, and a drafted answer-key field. Use when the user says "add a fact channel", "carry <relation/schema> in the DB", "extract <named relation> the counts flatten", "the forge still re-parses X -- move it to the engine", or names a system-fact issue under epic #3122. NOT for a syntactic signal/count (add-signal), a whole language (add-language), or deepening one language's rules (harden-language-extraction).
---

A **fact channel** carries a *named, system-defined relation or schema* — the "**what**" the
counted signals flatten to a "**that**". Counts (branches, io, a new operator) are signals and stay
cross-language comparable; named relations ("A calls B", "job binds DD to dataset") and schemas
(record layouts, message definitions, table columns) are facts and get a channel. **If it's a
count, you're in the wrong skill — use `add-signal`.**

## Read first (canonical, do not re-derive)

| source | what it settles |
|---|---|
| `gitgalaxy/core/how_to_add_a_fact_channel.md` | THE recipe: the 9 steps, the 6 invariants, the verify gate. Read it fully before writing code. |
| `gitgalaxy/core/mainframe_boundary.py` | the reference extractor (calls, datasets, records) + the bounded-regex discipline |
| `gitgalaxy/tools/cobol_to_cobol/galaxy_ir.py` `SCOPE` | what the DB does and does not carry — the contract you extend |
| the channel closest to yours: #3200 (call graph, global/resolved), #3201 (dataset, per-file), #3246 (record layouts, per-file tree) | which of the three shapes you are copying |

## The shape decision (before anything)

- **Per-file** (dataset, record): the fact is determined by one file. Insert with
  `record_keeper._insert_per_file_child`, restore with `state_rehydrator._restore_child_table`. The
  common case.
- **Global/resolved** (call graph, #3200): needs the whole repo (name → file). Extract per file,
  resolve in `invocation_resolver.py` after all files are seen, pass to `record_mission` as an
  explicit parameter; restore only the unresolved half.
- **Cross-file schema** (a future Protobuf/OpenAPI channel): extract same-file only (a copybook
  carries its own layout); assembling across files is the consumer's job, like `copy_deps`.

## The spine (each slot is fixed; the doc has exact seams)

1. Top-level dialect declaration in `languages/<lang>.py` — **beside `lexical_family`, NEVER in
   `rules`** (#2806: `rules` strings are `re.compile()`d; a key there extracts nothing, tests still
   green).
2. Bounded extractor in `core/mainframe_boundary.py`, returned as a new key from
   `extract_boundary()`. Read the PRISM code stream; emit a flat, source-ordered dict list (tree →
   `ordinal`/`parent_ordinal`, rebuilt by the reader).
3. `galaxyscope.py` boundary block: read the key with a default, add to `data_payload`.
4. `record_keeper.py`: `CREATE TABLE <name>_data (… file_id … ON DELETE CASCADE)` + two indexes;
   insert via `_insert_per_file_child`.
5. `state_rehydrator.py`: restore via `_restore_child_table` and set `node["<key>"]` — mandatory, or
   incremental scans drop unchanged files' facts.
6. `galaxy_ir.py`: `Engine<Fact>` dataclass, `EngineFile.<facts>` field, `_has_table`-gated read,
   and **update the SCOPE comment**.
7. `refraction_differential.py`: a real forge-vs-engine compared datum with a real cause (never
   `stated_absence` once the DB carries it); re-bless the baseline, `unexplained` must not rise.
8. `cobol_answer_key.py`: drafted field via the key's OWN independent reader; INDEPENDENT verdict
   gated behind an explicit per-program flag.
9. Tests mirroring the trio: `test_<extractor>.py`, `test_<name>_data.py`, `test_galaxy_ir.py`, +
   differential/answer-key cases.

## End-to-end wiring checklist

The #3249 round shipped several channels where the spine's write-side (table + extractor) landed
clean but a *read*-side or *proof*-side slot was missed or left thin, and the orchestrator had to
add the requirement back mid-flight. Check every line before opening the PR — each maps to a spine
step above, but the spine describes *how*, this is *did you actually do it*:

- [ ] **Extractor** reads the PRISM stream (never the raw file) and is dispatched from
  `extract_boundary()` under a new key.
- [ ] **Table + columns**: `CREATE TABLE IF NOT EXISTS <name>_data` with the FK cascade, AND
  `_ensure_columns` for any column added to an *existing* table (a sibling-dialect or
  resolved-column channel, e.g. #3345's `dsn_resolved`) so an older DB heals on the next record
  instead of erroring.
- [ ] **Column-gated reads**: every reader of a widened table (rehydrator, `galaxy_ir`, recorders)
  checks the column exists / defaults to `NULL`/`[]` rather than assuming a fresh schema — a
  pre-channel DB and a pre-column DB must both still load.
- [ ] **Rehydrator restore** (`state_rehydrator._restore_child_table`) sets `node["<key>"]` for
  every touched table, including widened existing tables, not just new ones.
- [ ] **Cascade/delete**: the child table's `FOREIGN KEY(file_id) REFERENCES file_data(id) ON
  DELETE CASCADE` is present and exercised by a re-record test (no duplicate/orphan rows).
- [ ] **`galaxy_ir.EngineFile` accessor**: a dataclass + field, `_has_table`-gated read, and the
  **SCOPE comment updated** — this is the contract other tools read and is easy to forget once the
  accessor itself works.
- [ ] **`galaxy_ir` joins that actually consume the fact** — storing the fact is not the same as
  wiring it in. If the fact resolves something a sibling join needs (e.g. lineage joining on a
  *resolved* DSN, not the raw template; CICS file → dataset → batch lineage; transaction → DB2
  plan), add or update that join, not just the raw accessor. A column nobody joins on is dead
  weight the differential will flag as unused.
- [ ] **Differential datum with an independent answer-key reader**: `refraction_differential.py`
  compares a real forge-vs-engine value with a real `cause` — never `stated_absence` once the DB
  carries it — and the answer-key side (`cobol_answer_key.py`) generates its candidate from its
  **own** reader (never importing the engine or forge), or the differential's "independent"
  verdict isn't actually independent.
- [ ] **Drafted answer-key field**: a `fields` entry + `add(...)` row in `score()`, populated
  `draft` (not `validated`) on new corpora, added without regenerating existing committed keys.
- [ ] **`audit_recorder.py` JSON section**: a `_<name>_facts_block(file_data)` with the full detail
  (mirrors the DB table), numbered, presence-keyed (nothing for a file with none). This moves the
  golden master — see invariants below.
- [ ] **`llm_recorder.py` brief section**: a `_<name>_facts_lines(parsed_files)` that summarizes
  (roots + counts, not the full tree) and returns `[]` when absent. Not golden-mastered, but still
  required — a channel with only the audit block leaves the LLM brief blind to it.
- [ ] **Recipe channel table** (`gitgalaxy/core/how_to_add_a_fact_channel.md`'s table) and any
  **README** that lists channels (`gitgalaxy/core/README.md`, `docs/ecosystem.md` if the channel
  changes cross-repo consumers) get a new row — a channel that only exists in code and not in the
  reference table gets re-discovered from scratch by the next agent.

## PR-body evidence template

A description of what you built is not proof it works end to end. Paste real command output into
the PR body, not a paraphrase of what you expect it to say:

```markdown
## Evidence

**DB rows from a real galaxyscope scan** (not a unit test):
    galaxyscope <corpus-path> --db-only --output /tmp/gg
    sqlite3 /tmp/gg/<repo>_galaxy_master.db "SELECT * FROM <name>_data LIMIT 20;"
<paste the actual rows>

**Accessor output** — load the DB through `galaxy_ir.py` and print the new field for one real file:
<paste the actual EngineFile.<facts> output, not a description of its shape>

**Audit JSON excerpt** — the new `_<name>_facts_block` for one file from a real `--full` scan's
`*_galaxy_audit.json`:
<paste the actual JSON fragment>

**LLM brief excerpt** — the new `_<name>_facts_lines` for the same file:
<paste the actual brief lines>

**Differential verdict** — `refraction_differential.py --ci` output showing the new datum with a
REAL cause (an explained mechanism or a genuine `unexplained`), never `stated_absence`:
<paste the classifier's line for this datum>

**Full vs `--incremental` scan: identical rows** — run both against the same corpus, diff the
child table (excluding autoincrement `id`), confirm zero differences:
<paste the diff command and its empty/expected output>
```

A PR that only asserts "the differential is green" without one of these five blocks pasted in is
missing proof that the specific new wiring — not just the write path — actually works.

## Consumers

State who reads this fact **today**, not who plausibly could. As of #3348, `cobol_refractor_
controller.process_payload` (the forge/refactor pipeline) does **not** read `EngineFile` fact
channels for anything beyond `program_ids`/`copy_deps`/`units` — it still re-parses lineage,
schemas, and call/transaction routing from the raw file even though the DB already carries them.
So today's real consumers of a new channel are: the differential (`refraction_differential.py`),
the answer key (`cobol_answer_key.py`), the audit JSON, and the LLM brief — plus any `galaxy_ir`
join another *channel* depends on. Say this plainly in the PR body ("consumed by: differential,
answer key, audit/LLM recorders; NOT yet the refactor pipeline, tracked in #3348") rather than
implying the new fact is live in the forge output — it isn't, until #3348 lands.

## Rebase / re-bless after a sibling merges

Every #3249-round channel PR touched the same shared seams (`galaxy_ir.py` SCOPE + accessors,
`refraction_differential.py`, `cobol_answer_key.py`, `record_keeper.py`, `state_rehydrator.py`,
`audit_recorder.py`/`llm_recorder.py`, both golden masters, the ruff baseline) and conflicted with
every sibling on exactly those seams (#3383, #3384) — 8 rebase cycles of 15–40 min each in that
round, one answer-key merge redone by hand. Until the channel registry (#3383) removes the shared
seams:

1. `git fetch origin` and rebase your branch onto `origin/main`.
2. On a golden-master or ruff-baseline conflict, take **main's side wholesale** — do not hand-merge
   JSON/baseline entries — then regenerate (`crucible_check.py --update --yes`, `audit_check.py
   --regenerate`).
3. Diff the regenerated golden masters against main and confirm the drift is **only your own fact
   keys** (plus the usual topological X/Y/Z ripple) — re-bless someone else's drift and you've
   silently reverted their channel.
4. Push with `git push --force-with-lease` only — never plain `--force` — since a sibling agent may
   have pushed to the same branch name space independently.

`tests/tools/rebase_rebless.py` (#3385, in progress) will automate steps 1–3 and verify the
own-drift constraint automatically; until it lands, do this by hand and don't skip step 3.

## Invariants that cost incidents (the whole reason this skill exists)

- **#2806**: declaration top-level, not `rules`.
- **The full audit report carries the facts (#3246 step 4b), so a channel MOVES the golden master**
  — `*_galaxy_audit.json` is crucible-audit's fixture and the corpus has cobol/jcl, so re-bless BOTH
  `golden_master_audit/` + `golden_master_zero_dep_audit/` with `crucible_check.py --update`
  and confirm the diff is only your fact keys (plus the topological X/Y/Z ripple).
- **Match CI's pinned tool versions before regenerating any baseline** — ruff is pinned in
  `.github/workflows/ruff-audit.yml` (a newer local ruff drops findings CI still emits, so a local
  regen silently breaks CI). `pip install "ruff==<pinned>"` first.
- **FK cascade + delta-scan restore** both required; prove byte-identical full-vs-incremental
  (excluding the autoincrement `id`, which drifts on delete+reinsert).
- **Hyphen boundary**: `\bBINARY\b` matches inside `TWO-BYTES-BINARY`; use
  `(?<![A-Z0-9-])…(?![A-Z0-9-])`.
- **Answer keys cover full corpora** (`mainframe_corpus.py fetch`), not the committed excerpts; ADD
  fields without regenerating (regen wipes `validated`); commit `draft`.
- **The key stays an oracle** only if its reader imports neither the engine nor the forge, and a
  drafted field never adjudicates.

## Environment & verify

    eval "$(tests/tools/worktree_env.sh fact-<issue> --corpus 2>/dev/null)"   # if in a worktree

Batch/corpus scans: Bash sandbox off (mega-repos get reaped) and
`GITGALAXY_LICENSE_KEY=COMMUNITY_FREE_TIER`. Gate before pushing (the doc's "Verify" block):
extractor+recorder+reader pytest, a real `--db-only` scan that populates `<name>_data`,
`refraction_differential.py --ci`, then `crucible_check.py` (no signal regression) and
`audit_check.py` (no new lint/dead-key). This is a `cobol-modernization` epic (#3122) change on the
engine side; the forge sourcing the new fact from the DB instead of re-parsing is the follow-up.
