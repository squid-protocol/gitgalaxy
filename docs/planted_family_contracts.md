---
description: "The five planted draft contracts of the keyword-family validity epic (#8863 / #8862) declared: safety_bypasses, doc, planned_debt, fragile_debt, telemetry -- sentence, measured incidence, contradictions listed."
---
# The `safety_bypasses`, `doc`, `planned_debt`, `fragile_debt` and `telemetry` contracts, declared (#8862)

Part of #8863 (keyword-family validity); the sequel to `docs/unplanted_family_contracts.md`. These were the last five
`draft` rows, and unlike the earlier batches they are **planted** in keyword-rosetta. They move to **`declared`**
(#2897): the sentence, `kind` and `unit` are fixed and language-independent; the sentence is contained verbatim in the
`# key:` comment of `gitgalaxy/standards/how_to_add_a_language.md`; incidence was measured on both corpora; every rule
that contradicts the sentence is **listed, not fixed**. No rule is edited, so no corpus cell moves, no keyword-rosetta
count moves and nothing is re-blessed. `declared` is not `stated`: the full family audit (rules edited to agree, a
`docs/<signal>_rule_contract.md`) is still owed for each, and `test_signal_contract_sheet.py` names these five as the
only planted rows allowed to be `declared`.

## The sentences

| signal | contract |
|---|---|
| `safety_bypasses` | A site that opts out of a safety check the language or its tooling would otherwise enforce -- a forced unwrap or unchecked cast, an escape-hatch type, a raw-memory reinterpretation, a swallowed error, or a lint or type-checker suppression -- in the construct's own syntax |
| `doc` | A comment block in the language's structured documentation form -- the form a documentation tool or IDE parses, such as a doc comment, a docstring or a tagged block -- read from the comment surface |
| `planned_debt` | A comment marker that records work the author intends to do later -- TODO, WIP, STUB or the language's equivalent -- read from the comment surface |
| `fragile_debt` | A comment marker in which the author admits the code beneath it is fragile, dangerous or a shortcut -- HACK, FIXME, XXX or the language's equivalent -- read from the comment surface |
| `telemetry` | A call that records a log line, a metric or a trace through a logging or observability framework, as opposed to a bare print to standard output -- in the framework's own call form |

`doc`, `planned_debt` and `fragile_debt` are `annotation` rows read from the comment stream (the Prism comment
surface); `safety_bypasses` and `telemetry` are `site` rows read from the code stream. Readings this settles (a reading
of the existing words; the maintainer can overrule it by editing the sentence):

1. **`telemetry` is not a print.** A bare print to standard output is `debug_prints`; `telemetry` is a call into a
   logging, metrics or tracing framework. This is the question #8862 left unanswered for the Python oracle.
2. **`safety_bypasses` counts a swallowed error and a suppression directive**, as the schema comment's own examples do
   (`any`, force unwrap, raw memory cast, `@ts-ignore`). `assert` is not a bypass (it adds a check).
3. **`doc` is the structured form a tool parses**, not any comment; `dead_code` and prose comments are not `doc`.

## What was measured

`tests/tools/rule_probe.py <rule> all --samples 3` over the Prism streams (the text `detector.py` hands the rule).
Crucible = `language-crucible` v1.8.0, rosetta = `keyword-rosetta` main (`2e67433`). 79 language definitions;
"defined" counts those that carry a rule (the rest record `None`, a contract-level absence).

| signal | defined / None | crucible hits | rosetta hits | densest languages (hits per file, >= 5 files) |
|---|---|---|---|---|
| `safety_bypasses` | 59 / 20 | 16114 | 101 | `dart` 96.1; `zig` 73.5; `scala` 32.9 |
| `doc` | 58 / 21 | 59562 | 48 | `dart` 1945.0; `rust` 271.0; `csharp` 220.8 |
| `planned_debt` | 61 / 18 | 1488 | 50 | `zig` 11.2; `dart` 8.0; `scheme` 6.2 |
| `fragile_debt` | 61 / 18 | 1316 | 50 | `perl` 15.5; `m4` 1.7; `c` 1.3 |
| `telemetry` | 58 / 21 | 1980 | 96 | `m4` 102.3; `powershell` 6.7; `perl` 4.1 |

## Contradictions found (listed, not fixed)

| signal | language | what the rule counts | reads the sentence? |
|---|---|---|---|
| `telemetry` | m4 | `AC_MSG_RESULT(yes)` (716 hits in 7 files) | no: a configure-script console message, not a log, metric or trace |
| `telemetry` | powershell | `Write-Verbose`, `Write-Log` (831 hits) | partly: `Write-Log` is a logger; `Write-Verbose` is a stream write, closer to a print |
| `telemetry` | python | fires in 4,899 functions where a parser sees a logger call in 1,389 (#8862, precision 0.28) | partly: extra forms unnamed |
| `fragile_debt` | perl | the bare word `bug` in code (`return $bug;`, 75 of 341 hits) | no: an identifier in the code stream, not a comment admission |
| `planned_debt` | zig | `.wip => |wip| wip` (132 of 413 hits come from the code stream) | no: an identifier, not a comment marker |
| `safety_bypasses` | zig | `unreachable` (256 `else => unreachable,` arms) | design question: an asserted-impossible branch, an opt-out of a check in release builds |
| `safety_bypasses` | dart | `x!` null assertions, `dynamic` | yes (the force unwrap and the escape-hatch type) |
| `doc` | dart, rust | the bare `///` line and `////////` banner lines (3,035 and 1,040 hits) | partly: a doc-comment line, but a banner is not documentation; hits count lines, not blocks, so density is not comparable across languages |

`tests/family_validity_baseline.json` carries parser-oracle scores for `doc`, `telemetry` and `safety_bypasses` only in
the languages with an oracle; `planned_debt` and `fragile_debt` have none (they need planted positives and negatives).

## What this does not do

- It edits no rule and writes no ledger entry; each contradiction above is a one-layer rule fix that can land with its
  own timing (and its own rosetta re-bless where the planted count moves).
- It does not promote any of the five to `stated`.

## Reproducing the measurement

```sh
export LANGUAGE_CRUCIBLE_PATH=<clean language-crucible v1.8.0> KEYWORD_ROSETTA_PATH=<keyword-rosetta main>
for r in safety_bypasses doc planned_debt fragile_debt telemetry; do
  python tests/tools/rule_probe.py $r all --samples 3 --json /tmp/$r.json
done
```
