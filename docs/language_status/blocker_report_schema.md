# Blocker report schema (#5054)

`python tests/tools/blocker_report.py PROOF_BLOCKERS.json --out DIR --salt-file FILE` writes two reports from one run:

| File | Who keeps it | Content |
|---|---|---|
| `blocker_report.full.{md,json}` | the customer only | every blocker with the programs, corpora, cases and details it names |
| `blocker_report.anon.{md,json}` | safe to send to us | the shape of each blocker, counts, no identifiers |

The input is `proof_blockers.py DIR --json` (#4270). `blocker_report.py --manifest` prints the field list below.

## Anonymized JSON, schema version 1.0

Report fields: `schema_version`, `kind` (`anonymized`), `engine_version`, `rule_catalogue`, `estate` (salted hash),
`totals` (`whole`, `proven`), `blockers`, `redactions`, `manifest`.

Blocker fields: `id` (salted hash of the signature), `category`, `subclass`, `signature`, `programs_blocked`,
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

## `--redact-more`

`--redact-more subclass counts` drops those fields from every blocker.

## Checks

`tests/tools/test_blocker_report.py`: parity of categories and counts with the full report; the leak test over every
identifier of a synthetic estate and the real names in the burned estates (CardDemo, GenApp, CBSA, zECS) when checked
out; hash stability per salt; the manifest equals the emitted fields.

## Not yet (Part of #5054)

Ingestion into the #5051 ledger (`estate: customer:<hash>`), matching a signature to an issue, the minimal-repro
generator, and a leak test on the cics-crucible and a run with the readiness scanner (#4725).
