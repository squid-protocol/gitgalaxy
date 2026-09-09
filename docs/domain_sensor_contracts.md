# The domain-sensor contracts, declared in one batch (#2897)

Phase 3 of the contract roadmap (`docs/contract_roadmap.md`, epic #2812): the sheet's last
bucket, the **40 unplanted, ungated domain sensors**, goes from `draft` to **`declared`** in one
PR. This document is the batch's evidence -- what each row's sentence became, what its rules
measure today, and which of them contradict the sentence. It is the `declared` analogue of the
per-signal `docs/<signal>_rule_contract.md` that a `stated` row carries; it does not replace one.

## Why `declared`, not `stated`

`gitgalaxy/standards/signal_contracts.py` defines `stated` as *audited against every corpus
language, with the per-language verdicts, and the rules edited to agree in the same PR*. Every
one of the 15 stated rows earned it that way, one family per session, because each had a
keyword-rosetta plant -- a cell the audit could hold equal across 46 languages.

None of these 40 rows has a plant, and none feeds a gated formula (the one that does,
`encapsulation`, is carved out below). There is no cell to move, so a per-family audit has
nothing to hold equal -- which is why the roadmap scheduled them as a batch of sentences. But a
sentence alone would have let the sheet say `stated` about rules that the first measurement
shows disagreeing with it as hard as `rust pub` did in #2766: zig `panics_and_aborts` counts
`return` (7538 hits), perl `decorators` counts `::` (2760), dart `closures` counts `if (...) {`
(3282), python `vectorized_math` counts the decorator `@` (892), php `bitwise_ops` counts `&`
inside HTML-entity strings (12316 of 15137).

So the batch adds the third lifecycle state the roadmap's own bucket table implied:

> **`declared`** -- the sentence, `kind` and `unit` are fixed and language-independent, the
> schema comment in `how_to_add_a_language.md` contains the sentence (the audit's containment
> check holds), incidence was measured on both corpora, and every rule the measurement shows
> contradicting the sentence is **filed**, not fixed. The rules have not been brought into line.
> A declared row becomes `stated` the day it gains a plant or a gated consumer and gets the
> family audit.

`draft` and `stated` keep their meanings. The epic's close criterion -- open-defect share 0 and
no `draft` row -- is unchanged; a `declared` row says exactly how far it was taken.

## Carve-out: `encapsulation` stays `draft`

It is in this bucket by the sheet's flags (unplanted), but it governs `_calc_api_exposure` and is
the derivation edge behind `def_encapsulation`; #2766 already documents that rust counts `pub`
(the complement of what every other language counts) and agc_assembly matches every column-0
token. It needs the family audit, not a sentence. Left `draft`, `issue=2766`.

## What was measured

One pass over both corpora with every domain-sensor rule applied to each file's `Prism` code
stream -- the same measurement `tests/tools/rule_probe.py` makes, done for all 41 rules per
split instead of one rule per run (41 x 46 languages would have re-split every file 41 times).
Crucible = `language-crucible` v1.2.0 (a clean worktree of the pinned tag); rosetta =
`keyword-rosetta` main (`00cd187`). The four `lit_*` rules read 0 on every file in that pass,
which is the finding recorded in the stream contract's corollary 2: markdown's whole file is
`comment_stream` under the Prose Bypass and `detector.comment_analysis` runs them there; they
were re-measured with `rule_probe.py lit_* markdown --stream both`. The crucible has no markdown
directory, so their crucible column is n/a.

Two things the table cannot show and the reader should know:

- **A zero is usually honest.** `hardcoded_secrets` reads 0 in all three languages that define
  it because the rules demand a credential-length literal and the corpus has none; the AI/ML
  pack reads 0 because no crucible python/javascript/typescript file imports `torch`, `sklearn`,
  `langchain` or `openai` (grepped directly); `rce_funnel`, `exfiltration_camouflage` and
  `memory_scraping` are attack shapes the crucible does not contain; `test_skip` reads 0 in 27
  languages because the crucible carries no skipped tests. None of those is a defect.
- **Kind was corrected where the rule's anchor said so.** The six import-anchored pack rules
  (`llm_orchestrator`, `llm_vector_store`, `ml_traditional`, `dl_frameworks`, `hardware_bridge`,
  `cryptography` -- all `_IMPORT_WRAPPER` regexes) fire on the import statement and never on a
  use, so their kind is `declaration` (the import contract's unit, #2875), not `site`.

## The rows

`defined / None` counts the 46 corpus languages: how many carry the rule key at all, and how
many of those set it to `None` (a contract-level absence). *densest language* is the highest
crucible hits-per-file and its most frequent matched token -- where a rule is too broad, that
is where it shows. The verdict names the filed issue where the densest match is not what the
sentence names: **#2898** = the rule's densest match is a different construct; **#2899** = the
rule fires on a bare word or string content.

| signal | phase | kind | defined / None | crucible hits (files) | rosetta hits | densest language: top token | verdict |
|---|---|---|---|---|---|---|---|
| `structural_boundaries` | structure | `tally` | 44 / 0 | 168404 (2284f) | 876 | `typescript` 776/file: `return` | tally by design; `module` as an identifier rides along (#2899); agc counts every opcode -- its only structure. The one consumer is `control_flow_ratio`'s denominator, #2770 (Phase 4). |
| `closures` | architecture | `declaration` | 44 / 19 | 14758 (443f) | 30 | `scheme` 494/file: `lambda` | scheme/scala/php read the sentence; dart counts `if (...) {` and every parameter list (#2898) |
| `comprehensions` | architecture | `site` | 44 / 10 | 3809 (328f) | 1 | `scheme` 113/file: `for-each` | scheme/perl read the sentence; dart counts `{ if (`/`{ for (` block openers (#2898) |
| `decorators` | architecture | `annotation` | 44 / 14 | 7969 (506f) | 22 | `perl` 131/file: `:SpamAssassin` | dart `@override`, rust `#[inline]`, fortran `!$OMP` read the sentence; perl counts `::` package separators (#2898) |
| `generics` | architecture | `annotation` | 44 / 13 | 16402 (337f) | 1 | `typescript` 258/file: `<ModifierLike>` | typescript/dart/scala/csharp read the sentence |
| `scientific` | architecture | `site` | 44 / 3 | 2687 (265f) | 2 | `fortran` 28/file: `sum` | dart `Matrix4`/`dart:math` reads the sentence; fortran `sum`, scheme `exp` are variable names (#2899) |
| `ui_framework` | architecture | `site` | 44 / 11 | 5752 (168f) | 4 | `dart` 118/file: `BuildContext` | dart `BuildContext` reads it, dart `widget`/`text` in strings do not (#2899); typescript counts generic type arguments and perl counts POD `C<%Y>` (#2898); css counts layout properties, which the sentence admits ("layout directive") |
| `dependency_injection` | subsystems | `annotation` | 43 / 14 | 1035 (237f) | 3 | `m4` 6/file: `AC_REQUIRE` | java `@Bean`/`@Configuration` read the sentence; m4 `AC_REQUIRE` is a macro prerequisite -- borderline, listed on #2898 for the decision |
| `events` | subsystems | `site` | 43 / 3 | 811 (148f) | 2 | `typescript` 9/file: `emit` | typescript's `emit(` is the compiler's own function -- by name indistinguishable, recorded on #2899; cpp `signal` inside strings (#2899) |
| `hardcoded_secrets` | subsystems | `site` | 3 / 0 | 0 | 0 | -- | honest zero: the three rules (ada, solidity, yaml) demand a credential-length literal; every other language is the security lens's `sec_hardcoded_secrets`, not a registry rule |
| `inline_asm` | subsystems | `site` | 43 / 34 | 4 (3f) | 1 | `solidity`: `assembly {` | honest: 34 languages record the absence, the crucible has four embedded-assembly sites |
| `macros` | subsystems | `declaration` | 43 / 15 | 4470 (130f) | 1 | `scheme` 96/file: `syntax-rules` | c/fortran `#if`/`#endif`, scheme `define-syntax`, m4 `define` read the sentence |
| `memory_alloc` | subsystems | `site` | 43 / 10 | 3840 (207f) | 15 | `scheme` 150/file: `cons` | java/kotlin/scala/dart count unmanaged forms only (`Arena`, `memScoped`, `ffi.Allocator`) and read 0; javascript/typescript count every `new Error(`/`new Promise(` and scheme every `cons` -- the wrong side of a decision the registry already made (#2898); c `"malloc failed"` in a string (#2899). Feeds the `mitigated_memory_allocs` proximity tally. |
| `pointers` | subsystems | `site` | 43 / 13 | 41806 (306f) | 18 | `c` 520/file: `*tstate` | c/cpp/zig read the sentence; perl counts `->{key}`/`$$ref` managed references (#2898) |
| `ssr_boundaries` | subsystems | `site` | 43 / 14 | 456 (57f) | 0 | `swift` 8/file: `Request` | 21 languages read 0 honestly (no SSR framework in the corpus); swift `Request` and perl `template` are bare words (#2899) |
| `bitwise_ops` | resources | `site` | 43 / 7 | 31924 (413f) | 0 | `php` 432/file: `&` | php: 12316 of 15137 are `&` inside HTML-entity strings, perl `\|` inside regex strings (#2899); zig `&` address-of and `\|err\|` captures (#2898) |
| `explicit_casts` | resources | `site` | 43 / 7 | 9251 (627f) | 2 | `zig` 44/file: `@bitCast` | zig/go/typescript read the sentence; agc `EXTEND` is an opcode prefix (#2898) |
| `listeners` | resources | `site` | 43 / 6 | 1048 (236f) | 20 | `cpp` 7/file: `on` | cpp `on` inside strings and `callback` as an identifier (#2899) |
| `panics_and_aborts` | resources | `site` | 43 / 0 | 15722 (943f) | 67 | `zig` 209/file: `unreachable` | csharp `throw`, m4 `AC_MSG_ERROR` read the sentence; zig also counts `return` (7538) and lua counts `assert` (#2898). Deliberate dual with high_risk_execution's termination family on `exit` (#2878). |
| `test_skip` | resources | `annotation` | 43 / 5 | 141 (35f) | 3 | `typescript` 1/file: `stub` | 27 languages read 0 honestly; perl `skip` as a hash key/POD item (#2899) |
| `thread_sleeps` | resources | `site` | 43 / 3 | 216 (94f) | 1 | `typescript` 2/file: `setTimeout` | reads the sentence |
| `ipc_rpc_bridges` | hybrid | `site` | 32 / 0 | 1569 (269f) | 30 | `swift` 6/file: `DispatchQueue` | swift `DispatchQueue`, lua `coroutine.yield`, embedded_python `machine.Pin`, solidity `emit Event(` are all in-process or another row's (#2898) |
| `regex_execution` | hybrid | `site` | 32 / 0 | 3917 (403f) | 0 | `perl` 51/file: `!~` | perl/php/powershell read the sentence; fortran `INDEX`/`VERIFY` take no pattern (5 hits, #2898) |
| `serialization_parsing` | hybrid | `site` | 32 / 1 | 2117 (230f) | 7 | `fortran` 49/file: `READ (` | fortran counts formatted record I/O -- io's (#2898); shell counts `sed` (529 hits), a text processor, not a format codec (#2898) |
| `time_date_logic` | hybrid | `site` | 32 / 0 | 757 (181f) | 0 | `perl` 7/file: `time` | go/java read the sentence; perl `$time[5]` is an array variable (#2899) |
| `cryptography` | ai-ml | `declaration` | 2 / 0 | 0 | 0 | -- | too narrow: the name list has no `hashlib`/`hmac`, so six python files that import them read 0 (#2898) |
| `dl_frameworks` | ai-ml | `declaration` | 3 / 0 | 0 | 0 | -- | honest zero (no such import in the crucible) |
| `hardware_bridge` | ai-ml | `declaration` | 2 / 0 | 26 (1f) | 0 | `javascript`: `import ... './webgl/...'` | the name list includes `webgl`, a renderer, not a peripheral (#2898) |
| `lazy_evaluation` | ai-ml | `site` | 3 / 0 | 251 (31f) | 0 | `typescript` 1/file: `Iterable` | python `yield` reads the sentence |
| `llm_orchestrator` | ai-ml | `declaration` | 3 / 0 | 0 | 0 | -- | honest zero |
| `llm_vector_store` | ai-ml | `declaration` | 3 / 0 | 0 | 0 | -- | honest zero |
| `ml_traditional` | ai-ml | `declaration` | 3 / 0 | 0 | 0 | -- | honest zero |
| `vectorized_math` | ai-ml | `site` | 3 / 0 | 898 (212f) | 0 | `python` 3/file: `@` | the python rule's operand lookbehind accepts `)` across a newline, so 892 of the 898 hits are decorator lines (#2898) |
| `exfiltration_camouflage` | appsec | `site` | 3 / 0 | 0 | 0 | -- | honest zero |
| `memory_scraping` | appsec | `site` | 1 / 0 | 0 | 0 | -- | honest zero |
| `rce_funnel` | appsec | `site` | 2 / 0 | 0 | 0 | -- | honest zero |
| `lit_code_blocks` | literate | `site` | 1 / 0 | n/a | 10 (comment stream) | `markdown`: ` ``` ` | reads the sentence; opener and closer both count |
| `lit_diagrams` | literate | `site` | 1 / 0 | n/a | 1 (comment stream) | `markdown`: ` ```mermaid ` | reads the sentence; deliberate dual with lit_code_blocks on the opener |
| `lit_headers` | literate | `declaration` | 1 / 0 | n/a | 16 (comment stream) | `markdown`: `#`, `##` | reads the sentence on the rosetta files; not fence-aware by construction -- a `#` comment inside a fenced block is a heading (#2898) |
| `lit_links` | literate | `site` | 1 / 0 | n/a | 3 (comment stream) | `markdown`: `[b](b.md)` | reads the sentence |

## What each row now says

The sentences are in the sheet (`docs/signal_contracts.md` is the rendered table) and, verbatim,
in the `# key:` comment of `how_to_add_a_language.md`'s OUTPUT SCHEMA, followed by the prompt's
Includes / EXCLUDES. Three decisions taken across the batch, stated once here:

1. **Duals are named, not hidden.** `panics_and_aborts` and `high_risk_execution` both count
   process termination (#2878 kept it); `rce_funnel` and `exfiltration_camouflage` are
   refinements that count alongside `high_risk_execution` and `io`; `lit_diagrams` shares its
   opener with `lit_code_blocks`. A dual the sentence names is a design; one it does not is a
   defect (fortran `serialization_parsing` on io's `READ`, lua `panics_and_aborts` on safety's
   `assert`, solidity `ipc_rpc_bridges` on events' `emit`).
2. **A language without the construct records `None`.** The sentence says so for every row where
   the measurement found a `None` (closures 19, inline_asm 34, decorators 14 ...). Ledger entries
   are not written for these: the row is ungated, so there is no cell for the entry to excuse.
3. **The managed side of `memory_alloc` is settled by precedent, not by this batch.** Four
   languages already count unmanaged forms only; the three that count every constructor are
   filed as the defect (#2898), because count contract corollary 3 forbids both answers inside
   one row.

## What this batch does not do

- It edits no rule. Every disagreement is on #2898 or #2899 with its measured line, and each is
  a one-layer fix that can land whenever someone wants it -- none moves a corpus cell.
- It writes no ledger entry and no corpus PR.
- It does not touch the 13 rows still `draft`: the five planted ones (`safety_bypasses`, `doc`,
  `planned_debt`, `fragile_debt`, `telemetry`) and the seven unplanted risk inputs
  (`concurrency`, `dead_code`, `debug_prints`, `llm_api`, `reflection_metaprogramming`,
  `spec_exposure`, `sync_locks`) need the family audit, plus `encapsulation` (#2766).

## Reproducing the measurement

```sh
cd ~/nyx_projects/gitgalaxy-worktrees/<wt>
export PYTHONPATH=$PWD LANGUAGE_CRUCIBLE_PATH=~/nyx_projects/language-crucible-worktrees/v1.2.0 \
       KEYWORD_ROSETTA_PATH=<a detached worktree of keyword-rosetta origin/main>
# one rule, with matched lines:
python tests/tools/rule_probe.py panics_and_aborts zig --samples 8
# the literate pack, on the stream the detector uses:
python tests/tools/rule_probe.py lit_headers markdown --stream both
```

## Resolution (#2898 / #2899)

The filed one-layer fixes landed in one PR (2026-09-09); the table above remains the
batch's measurement record — these are the deltas against it:

- **Cross-sensor double-counts removed** (the receiving rule already counts the token):
  zig `return` (7538), lua `assert` + the `coroutine.*` family, swift `DispatchQueue`,
  solidity `emit Event(`, embedded_python's peripheral handles (a socket remains its one
  bridge), fortran `READ(`/`WRITE(`/`OPEN(`, shell `sed`/`awk`.
- **Registry-consistent narrowing**: javascript/typescript `memory_alloc` now counts
  unmanaged forms only (`ArrayBuffer`/`SharedArrayBuffer`/`WebAssembly.Memory`/
  `Buffer.alloc*`), joining the java/kotlin/scala/dart reading; perl `decorators` no
  longer counts `::`; dart `closures`/`comprehensions` anchor to expression position;
  zig `bitwise_ops` requires zig-fmt operator spacing; python `vectorized_math`'s `@`
  gap no longer crosses newlines; python `cryptography` gains `hashlib`/`hmac`.
- **Contract-level absences declared** (`None`): fortran `regex_execution`,
  agc_assembly `explicit_casts`, scheme `memory_alloc`, perl `pointers`.
- **String/bare-word anchors** (#2899): fortran/scheme `scientific` call/head anchors,
  c `memory_alloc` call anchor, cpp `signal(`/`on(`/`callback(`, typescript `.emit(`,
  swift/perl `ssr_boundaries` type/call anchors, dart `ui_framework` exact case,
  php `&` entity guard, perl `|` spacing, perl `skip`/`time` shapes, perl `<%` POD guard.
- **Parked**: markdown `lit_headers` fence-awareness is a stream-level change
  (`detector.comment_analysis`), not a regex anchor — still open on #2898's margin;
  typescript `.emit(` is best-effort, the compiler's own `emit` calls remain
  by-name indistinguishable.
