# Blocker report schema (#5054)

`python tests/tools/blocker_report.py PROOF_BLOCKERS.json --out DIR --salt-file FILE` writes two reports from one run:

| File | Who keeps it | Content |
|---|---|---|
| `blocker_report.full.{md,json}` | the customer only | every blocker with the programs, corpora, cases and details it names |
| `blocker_report.anon.{md,json}` | safe to send to us | the shape of each blocker, counts, no identifiers |

The input is `proof_blockers.py DIR --json` (#4270). `blocker_report.py --manifest` prints the field list below.

## Anonymized JSON, schema version 1.1 (1.1 adds the optional `repro`; rule catalogue 2)

Report fields: `schema_version`, `kind` (`anonymized`), `engine_version`, `rule_catalogue`, `estate` (salted hash),
`totals` (`whole`, `proven`), `blockers`, `redactions`, `manifest`.

Blocker fields: `id` (salted hash of the signature), `category`, `subclass`, `signature`, `repro` (optional), `programs_blocked`,
`programs_only_gap`, `programs_one_away`.

Categories: `unresolved-link`, `refusal`, `cics-command`, `runtime-fact`, `no-case`, `known-unproven`,
`scenario-differs`, `coverage`, `environment`, `other`.

## What is kept, removed and hashed

- **Kept:** the category and sub-class, the construct signature, counts, engine version, rule-catalogue version,
  refusal exception classes. A signature is assembled only from fixed vocabulary: CICS verbs and option names from
  `gitgalaxy/standards/cics/commands`, EIB fact names, refusal class names, fixed gap phrases.
- **Removed:** refusal messages, details, case names, corpus names, paths, literals, comments, source lines, and any
  gap text the classifier does not know (category `other`, signature `unclassified`, no text).
- **Hashed:** copybook, program, field, event and option names, and the estate name, as `KIND_xxxxxx`
  (`CPY_`, `PGM_`, `FLD_`, `EVT_`, `OPT_`, `EST_`, `BLK_`): the first 6 hex digits of
  `HMAC-SHA256(salt, KIND:NAME)`, name case-folded.

## Salt

One random 32-byte salt per customer, in the file given to `--salt-file` (created with mode 0600 when missing).
It is never written to either report. The same salt gives the same hashes on every run, so a blocker can be followed
across releases; a different salt gives different hashes, so nothing matches across customers, and the hash cannot
be reversed without the salt. Six hex digits keep reports short; a customer wanting fewer collisions can ask for more.

## Minimal repro

`repro` is a synthetic COBOL snippet rebuilt from the signature alone, so we can reproduce the blocker without the
customer's code. Present for `cics-command` (an `EXEC CICS ... END-EXEC` with the signature's verb and options),
`runtime-fact` (a `MOVE` of the EIB field) and `unresolved-link` (a `COPY` of the missing copybook); absent for every
other category. Fixed boilerplate (`PROGRAM-ID. REPRO1`, `WS-OUT`), CICS vocabulary, and names as `KIND-XXXXXX` hashes
(upper-cased, `_` as `-`, a legal COBOL name) are the only words it holds.

## `--redact-more`

`--redact-more subclass counts repro` drops those fields from every blocker.

## Checks

`tests/tools/test_blocker_report.py` and `test_blocker_ingest.py`: parity of categories and counts with the full report; the leak test over every
identifier of a synthetic estate and the real names in the burned estates (CardDemo, GenApp, CBSA, zECS, cics-crucible; `CICS_CRUCIBLE_PATH`, else `../cics-crucible`) when checked
out, over the repro text too; the repro holds only vocabulary, boilerplate and hashes; hash stability per salt; the manifest equals the emitted fields.

## Construct key (schema 1.2, #5865)

Each blocker carries `construct`: its key in `docs/language_status/gap_prevalence.md` (`gap_prevalence.scrub_key`, a closed
vocabulary: CICS command and spec options, SQL keywords, IBM routines, refusal classes, copybook family such as `missing
copybook: estate-owned`). A customer scan and our ranking therefore speak one vocabulary and join on it; no name survives
in it (a CICS option outside the command spec ends the key; `--redact-more subclass` drops it). Ingest (1.1 and 1.2 both accepted) refuses a construct that
holds a hash and copies it to the ledger row.

## Ingestion on our side

`python tests/tools/blocker_ingest.py blocker_report.anon.json --ledger FILE` turns each blocker into a row of a
customer-side ledger (`estate: customer:EST_xxxxxx`, `side`, `class` in the #5051 vocabulary, the signature, the counts,
`seen_in` engine versions). The rows never go into the committed `port_blockers.json`, which is burned estates only.

- The report is checked first: kind `anonymized`, a supported schema version, no field outside the manifest, every
  signature word in the allow-list or a `KIND_xxxxxx` hash. Anything else is refused with the reasons.
- A signature is matched to an issue by `tests/cobol_mainframe/blocker_signatures.json` (category plus a word prefix,
  hashes replaced by `KIND_*`, so the customer's salt does not matter); `known unproven: #N` links to #N. A blocker
  with no match gets `issue: null` and a drafted issue body on stdout, for the tick to file.
- **Opening a new issue.** `blocker_estate_feed.py queue --feed FILE --filed FILED.json` lists one item per distinct
  construct (category plus the salt-free signature), however many estates or customers report it, and leaves out any
  construct already in `FILED.json`. With `--open-issues` it opens one issue per item (REST `gh api`, never in CI) and
  records `{category|signature: issue}` in `FILED.json`; `blocker_ingest.py ... --filed FILED.json` then links every later
  report of that construct to the issue (the catalogue still wins), so it is neither re-queued nor re-opened.
- Re-ingesting a report changes nothing; a later engine version appends to `seen_in` ("still open after 3 releases").
- A row carries the #5051 shape (`summary`, `programs: []`, `refused_by_name: false`; a customer's program names never
  reach us) and a `status`. A blocker of the same estate that a newer engine version's report no longer lists becomes
  `closed` with that version in `absent_in`, and reopens if a later report lists it again. Reports are ingested in
  engine-version order; another estate's rows are never touched. `blocker_ingest.py X --ledger FILE --check` validates
  a ledger against the #5051 sides and classes.

## Not yet (Part of #5054)

A run with the readiness scanner (#4725). The census feed and the CI ingest over each burned estate's report
(`blocker_estate_feed.py`, nightly in `evidence-refresh.yml`) are in place. The leak scan over the real names of
CardDemo, GenApp, CBSA and zECS runs on every PR that reaches the ground-truth job
(`tests/cobol_mainframe/test_blocker_leak_burned_5054.py`); the cics-crucible leg runs in `cics-crucible.yml`.

## The harness report (#4493)

`python tests/tools/harness_report.py PROOF_BLOCKERS.json --out DIR` (or `--survey DIR`) writes `harness_report.{md,json}`
for the burned estates: coverage (programs, with a case, proven, paragraphs and branches exercised), run status per program
(`proven`, `differs`, `couldn't run`, `not attempted`, `ran, coverage open`), the input generation per case (generated from a
layout, shipped data, skipped), and the blockers stated as fixes. Each non-proven program is under exactly one blocker (its
highest-ranked gap). `tests_unlocked` counts the scenarios of the cases of programs for which the blocker is the only gap
left; `then_needs` lists what a program still needs after it. Non-burned programs are counted, never named. The page is
generated output and is not committed.

A fresh-estate trial's page (`trial.py report --write`, `docs/language_status/trials/<estate>.md`) uses the same vocabulary (proven / differs / couldn't run / not attempted) but is built from `trials.json` alone: its blockers are the failure causes (ticket, generator, engine, harness, model), and it has no paragraph or branch coverage (#4493).
