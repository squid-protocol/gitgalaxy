---
name: cobol-modernization
description: Work on the COBOL modernization track (epic #3122) -- the refraction tools in gitgalaxy/tools/cobol_to_cobol/ + cobol_to_java/ and both controllers ("the forge"), or the engine's COBOL/mainframe extraction that the forge reads through galaxy_ir.py. Covers the loop (fetch pinned corpus -> scan -> differential -> explain deltas -> score against the answer key -> bless the refraction snapshot), how to prove a forge-side vs an engine-side change, and which open issue owns which gap. Use when the user says "work on #3197/#3198/#3199/#3200/#3201/#3202/#3221/#3222", "fix the refractor/forge/graveyard/JCL forge", "score against the answer key", "run the differential", or anything under #3122/#3120. Not for adding a mainframe language (add-language) or a per-signal contract audit with no refraction consumer (rule-contract-audit).
---

The pipeline is `cobol-refractor` → clean room (JCL, schemas, IR dumps, agent jobs) → `cobol-to-java` → a Spring Boot tree. It can take its program list, PROGRAM-IDs, COPY edges and paragraph inventory from the engine's master DB (`--galaxy-db/--scan`, #3120). Dead code and dataset lineage still come from the forge's own parsers, because the engine does not carry them yet.

**Neither side is the oracle.** The answer key is.

## Read first (canonical, don't re-derive)

| doc | what it settles |
|---|---|
| `tests/cobol_mainframe/answer_key/README.md` | what the key records, how it was verified, current scores per field |
| `docs/refraction_engine_differential.md` | the four delta causes, D1–D4, and which issue owns each gap |
| `tests/cobol_mainframe/readme.md` §7 | the corpus, snapshot and ReDoS tooling |
| `gitgalaxy/tools/cobol_to_cobol/galaxy_ir.py` `SCOPE` | exactly what the DB does and does not carry |

## The loop

All commands run from the checkout you are changing. The scan subprocess gets that checkout on `PYTHONPATH`, so a worktree measures its own engine.

```sh
python tests/tools/mainframe_corpus.py fetch                 # 3 pinned corpora into .mainframe_corpora/ (~5s)
python tests/tools/mainframe_corpus.py scan                  # master DBs, cached per ref + engine HEAD + dirty-diff hash
python tests/tools/mainframe_corpus.py score --md score.md   # forge AND engine DB vs the answer key (zopeneditor, CBSA)

# explain every tool-vs-engine delta on one corpus
python tests/tools/refraction_differential.py "$(python tests/tools/mainframe_corpus.py path <corpus>)" \
    --db "$(python tests/tools/mainframe_corpus.py path <corpus> --db)" --md diff.md

python tests/tools/refraction_snapshot.py check              # committed excerpts (what CI runs)
python tests/tools/refraction_snapshot.py check --corpus zopeneditor-sample cics-banking-sample-application-cbsa aws-mainframe-modernization-carddemo
python tests/tools/tool_regex_redos.py --ci                  # every forge regex, vs the baseline
```

**Baseline first.** Run `score` and both snapshot checks on unmodified `origin/main` before editing. Every number in the PR is then a before → after, and nothing is reconstructed later.

## Which side is the change on?

| | forge (tools, controllers) | engine (`languages/cobol.py`, `detector.py`, `usage_status`, dependency resolver) |
|---|---|---|
| proof | `score` forge column moves; snapshot diff explained | `score` engine-DB column moves; `refraction_differential.py` deltas re-attributed |
| bless | `refraction_snapshot.py update` (+ `--corpus …` locally): commit the `.snap` diff, say in the PR what moved and why | the full `ci-push-checklist` gauntlet: `crucible_check.py --update --yes` after scoping, rosetta/contract checks if a signal's meaning changed |
| snapshot | must move only where intended | must NOT move (the default refractor path doesn't read the DB); if it does, something leaked |
| ReDoS | any new or edited regex: `tool_regex_redos.py --ci` | the engine's own strict suites + `sweep_redos_scaling.py` |

An engine change that exists to enable a forge switch (e.g. #3198 → dead code from the DB) is **two PRs**:
1. The engine fix, scored on the engine column.
2. The forge switch, proven by the differential and the snapshot.

Don't bundle them. The golden-master bless and the snapshot bless have to be reviewable separately.

## Reading a delta

Attribute every difference to one of the differential doc's four causes: old-parser defect, engine defect, semantic difference, stated absence. **Check each one against the real source lines.**
- A delta is a finding to explain, never a verdict that the DB is better.
- Record new attributions in `docs/refraction_engine_differential.md` as a dated `## Update:` section with a before → after score table, matching the existing ones.

## Gotchas (each cost a session once)

- **CBSA's ref is on branch `July2024Refresh`.** Its `main` was emptied at the 2024 sunset. The manifest handles it; don't re-clone by hand.
- **The refractor writes its clean room next to its target.** Run it on a copy (the snapshot harness does). It no longer edits the target in place (#3206), but siblings still appear.
- **`usage_status` is a by-name census, not reachability** (#3198). Never mask or report dead code from it.
- **`edge_data` holds COPY/INCLUDE edges only.** It has no CALL, `EXEC PGM=` or SELECT/OPEN edges (#3200, #3201).
- **The engine stores OS-native path separators.** `galaxy_ir` normalises them to `/` on load. Read the DB through it (`load_galaxy_ir`, then `lookup(file, root)`), not raw `sqlite3`, or Windows scans won't join.
- **The forge's reachability pass and the answer key's `draft` share one control-flow model** (#3219). The forge's 680/680 and 62/62 on CBSA are therefore not independent evidence. A model defect would be invisible, so hand-check the source when a change touches reachability.
- **Program keys:** outputs are keyed by stem when unique, else `a__b__STEM` (#3218). `cobol-to-java` still keys by file name (#3221).
- **Determinism:**
  - Sort every set you serialise and every `glob`/`rglob` you iterate.
  - Sort by `p.parts` or `p.name`, never bare `Path`, because WindowsPath sorts case-insensitively (#3223 went red on Windows over exactly this).
  - Check a new output with two `PYTHONHASHSEED` values.
- **Repo `.gitignore` has a global `*.json`.** A new committed JSON needs a `!` whitelist line, or the PR ships without its data.
- **Python 3.9 is in the matrix.** No `write_text(newline=)`, no `match`, no `X | Y` at runtime.
- **The Full Suite Gate matrix runs only on a `labeled` event** (#3209). After a push, remove and re-add a label to re-run Windows.
- **X-Ray fails on a dense string literal** over 64 chars. Build long regexes from short named fragments.

## Who owns what (open, as of 2026-09-19)

| issue | side | gap | unblocks |
|---|---|---|---|
| #3197 | engine | Area-B continuation lines ending in `.` become paragraphs (the 26 extra CBSA units) | clean unit inventory |
| #3198 | engine | `usage_status`: entry flagged, case-sensitive, `NAME-EXIT` counts as a reference to `NAME` | dead-code switch (#3120) |
| #3199 | engine | resolver drops ambiguous COPY targets (78/114 CBSA copybooks) | copybook switch |
| #3200 | engine | no CALL / CICS LINK / XCTL / `EXEC PGM=` edges | lineage switch (#3120) |
| #3201 | engine | no named SELECT/ASSIGN, OPEN modes or DD bindings | lineage switch (#3120) |
| #3202 | engine | `calls_out_to` meaningless for COBOL | — |
| #3211 | tooling | differential deltas carry no cause code; no unexplained-count gate | gating engine changes |
| #3221 | forge | `cobol-to-java` collapses same-name programs | — |
| #3222 | forge | 3 quadratic regexes (baselined) | — |
| #3121 | CI | generated Spring Boot is never compiled | "generates" = "compiles" |

Update this table when an issue closes. The current scores live in the answer-key README, not here.

## Done means

- `score` before → after in the PR description, for the column you moved and the column you didn't.
- Snapshot:
  - forge PR: blessed and explained;
  - engine PR: unchanged.
- `tool_regex_redos.py --ci` passes, and any baseline entry you fixed is removed.
- `docs/refraction_engine_differential.md` has an `## Update:` section if an attribution changed.
- The ownership table above is still true.
