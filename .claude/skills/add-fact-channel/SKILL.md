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

## Invariants that cost incidents (the whole reason this skill exists)

- **#2806**: declaration top-level, not `rules`.
- **Golden master is safe only because the JSON audit recorder ignores per-file payload extras** —
  confirm `grep <key> *_galaxy_audit.json` is 0, or you move the crucible-audit baseline. A channel
  touches only its own DB table.
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
