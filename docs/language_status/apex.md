# Apex — Structural Signature Coverage

Snapshot generated 2026-08-20 against `main`. Source: `LANGUAGE_DEFINITIONS["apex"]` in
`gitgalaxy/standards/language_standards.py`, `tests/extraction/languages/test_apex.py` /
`test_apex_strict.py`, closed/open GitHub issues, and
[`gitgalaxy-raw-output`](https://github.com/squid-protocol/gitgalaxy-raw-output). Re-run the
`language-status` skill's data-gathering commands before trusting these numbers if this doc looks
old relative to `last_updated` below.

## 1. At a glance

| Field | Value |
|---|---|
| `_meta.status` | `production` |
| `_meta.target_version` | Salesforce Apex 24.2 (API v62.0+) |
| `_meta.blueprint_version` | v5.0 |
| `_meta.last_updated` | 2026-02-18 |
| `lexical_family` | `standard_block` (`//` line comments, `/* */` block comments) |
| Structural signature keys wired | 43 / 48 (5 explicit `None`, see §4) |
| Extraction-gauntlet tests (`test_apex.py`) | 4 |
| Strict-signature tests (`test_apex_strict.py`) | 93 |
| Total dedicated Apex test cases | 97 |

Apex's `rules` dict has 48 total keys, not the fuller 52-key shape some other languages (e.g. C,
COBOL) use — it has no `serialization_parsing` / `regex_execution` / `time_date_logic` /
`ipc_rpc_bridges` entries at all, not even as explicit `None`. Those four keys are the "Hybrid
domain sensors" group `how_to_add_a_language.md` documents as optional per-language extras, and
Apex's blueprint simply never added them (SOQL/SOSL query parsing, HTTP callouts, and time/date
math on the platform are already captured under `io`/`scientific`/other keys below, so the gap
isn't a functional hole so much as an unclaimed classification bucket).

## 2. Identification surface

- **Extensions:** `.cls .trigger` — standard Apex classes and database triggers, the only two
  source-file shapes the Salesforce platform executes.
- **Exact filenames:** none — Apex code lives and executes exclusively on the Salesforce
  platform; there's no extensionless canonical entry-point convention the way Python (`setup.py`)
  or PHP (`artisan`) have.
- **Discriminators:** `.cls-meta.xml`, `.trigger-meta.xml`, `sfdx-project.json`, `package.xml` —
  Salesforce metadata XML sidecars and SFDX project config, used as gravity anchors because `.cls`
  alone is a highly contested extension (Windows `.cls` class modules, WordStar files, etc.).
- **Shebangs:** none — Apex is executed exclusively on the Salesforce platform; no interpreter
  invokes it via a line-1 shebang.

## 3. What GitGalaxy detects

Grouped by the phase headers `language_standards.py` uses for Apex. Description is what Apex's
*actual* regex matches, not the generic cross-language definition.

**Phase 1: Logic topology & structure**
| Key | What it captures for Apex |
|---|---|
| `branch` | `if else switch on when for while do try catch finally break continue return`, plus `&& \|\| ? ??` |
| `args` | Parameter-list capture for method signatures (with up to 5 stacked annotations, up to 5 access/sharing modifiers, and a typed return-type prefix) and for `trigger Name on Object (events) {` headers; #1209 wrapped the parenthesized span in its own capture group in both alternatives so `detector.py`'s counter isolates just `(...)` instead of overcounting via the whole-match fallback |
| `structural_boundaries` | `class interface trigger enum final transient implements extends virtual abstract return` — deliberately excludes access modifiers and sharing keywords |
| `func_start` | Anchors method/constructor definitions and trigger headers. #1221's "Invocation Shield" gates the method branch on seeing at least one of an annotation, a modifier, or a typed return-type prefix before the name — a bare call statement (`next();`) carries none of the three and no longer misparses as a definition. Up to 5 stacked annotations and 5 modifiers are consumed before the name; a negative lookahead excludes `class interface enum if for while switch catch` from being read as the method name itself |
| `class_start` | Anchors `class`/`interface`/`enum`, optionally preceded by up to 5 stacked annotations and access/sharing modifiers (`public private global virtual abstract with sharing without sharing inherited sharing`); captures the entity name via a lookahead for `implements`/`extends`/`{`/end-of-line |

**Phase 2: Risk & structural integrity**
| Key | What it captures for Apex |
|---|---|
| `safety` | `with sharing inherited sharing isAccessible isCreateable isUpdateable isDeletable StripInaccessible try catch finally LIMIT n Security.stripInaccessible`, plus safe-navigation `?.` |
| `safety_bypasses` | `without sharing`, `Database.query(...)` *not* paired with `WITH SECURITY_ENFORCED`, `@SuppressWarnings`, and raw parenthesized-type casts (`(Type) var`) |
| `high_risk_execution` | `Database.query delete undelete emptyRecycleBin purgeOldAsyncJobs`, plus bare 15-18 char quoted Salesforce record IDs (hardcoded-ID smell) |
| `io` | Bracketed inline SOQL/SOSL (`[SELECT ...]` / `[FIND ...]`), plus `Http HttpRequest HttpResponse Database.executeBatch HTLoad HTGet ENQUIRE` |
| `api` | `global webservice`, plus `@RestResource @HttpGet @HttpPost @HttpPut @HttpDelete @HttpPatch @AuraEnabled @InvocableMethod @RemoteAction` |
| `state_mutation` | `insert update upsert delete merge` DML verbs, bare line-start assignment (`x = ...` / `x += ...`), and collection mutators (`.add( .addAll( .remove( .put( .clear( .set(`) |
| `dead_code` | Commented-out (`//` or `/*`) `class trigger public private if for while System.debug [SELECT insert update` |
| `doc` | `/**`, `@description @param @return @author @date @example` |
| `test` | `@isTest @TestSetup @TestVisible Test.startTest Test.stopTest System.assert Assert.isTrue Assert.isNotNull Assert.areEqual Test.setMock` |

**Phase 3: Architecture & domain sensors**
| Key | What it captures for Apex |
|---|---|
| `concurrency` | `@future Queueable Schedulable Batchable System.enqueueJob Database.executeBatch System.schedule` — Apex's async execution contexts |
| `ui_framework` | `ApexPages PageReference StandardController Dom.Document`, plus `SGML HyperText WorldWideWeb BrowserView` (Visualforce/legacy-web-standard vocabulary) |
| `closures` | `None` — see §4 |
| `globals` | `UserInfo System.Label Organization Cache.Org Cache.Session`, plus Custom Setting/Custom Metadata Type accessors (`X__c.getInstance` / `X__mdt.getInstance`, bounded `{1,100}` after a 2026 quadratic-blowup fix) |
| `decorators` | Any `@identifier` optionally followed by `(...)` — Apex's annotation syntax |
| `generics` | `List<T> Set<T> Map<K,V> Iterable<T> Iterator<T>` parameterized-collection literals |
| `comprehensions` | Inline SOQL `for` loops (`for (x : [SELECT ...])`) — Apex's closest analogue to a comprehension |
| `scientific` | `Math.abs Math.sin Math.cos Math.tan Math.exp Math.log Math.pow Math.sqrt Decimal setScale setRoundingMode` |
| `reflection_metaprogramming` | `Database.query Type.forName Schema.getGlobalDescribe Schema.describeSObjects SObject.put SObject.get JSON.deserializeUntyped` |
| `import` | Namespaced static-member access (`Namespace.Type`), excluding calls into Apex's own built-in namespaces (`System Database Schema Auth Cache Chatter EventBus Limits Messaging RestContext Test`) — Apex has no native `import` keyword, so cross-package coupling is inferred from qualified-name usage instead |
| `_dependency_capture` | Extracts the class name (and optional namespace) from `Type.forName('X')` / `Type.forName('ns', 'X')` reflection calls |
| `ownership` | `@author Author: Created by: Maintainer: Copyright:` |

**Phase 4: Specialized sub-systems**
| Key | What it captures for Apex |
|---|---|
| `planned_debt` / `fragile_debt` | Shared `GLOBAL_` TODO/FIXME-family markers |
| `spec_exposure` | `[SPEC-123]`/`[spec ...]`/`[audit ...]` traceability tags, plus `WorldWideWeb RFC W3C CERN TBL ENQUIRE` |
| `ssr_boundaries` | `RestContext.request RestContext.response RestRequest RestResponse renderAs` |
| `events` | `EventBus.publish PlatformEvent`, plus `trigger X on YEvent__e` (Platform Event trigger headers) |
| `dependency_injection` | `fflib_ApexMocks fflib_SObjectUnitOfWork Injector di_Injector Application.Service Type.newInstance` |
| `macros` | `None` — see §4 |
| `pointers` | `None` — see §4 |
| `memory_alloc` | `Limits.getHeapSize Limits.getLimitHeapSize`, plus any `new Identifier(...)` object-instantiation expression |
| `inline_asm` | `None` — see §4 |

**Phase 5: Resource management & stability**
| Key | What it captures for Apex |
|---|---|
| `telemetry` | `Logger.\|Log.\|AppLog.\|NebulaLogger.` info/error/warn/debug/trace calls, plus `insert new Log__c` |
| `debug_prints` | `System.debug` |
| `explicit_casts` | `(Type) identifier` for `int Id String Decimal Boolean Double Long Blob Date Datetime Time` and capitalized custom type names |
| `panics_and_aborts` | `throw Database.rollback purgeOldAsyncJobs` |
| `thread_sleeps` | `None` — see §4 |
| `bitwise_ops` | `& \| << >> ^ ~` (single-`&`/single-`\|` only, guarded against `&&`/`\|\|`) |
| `sync_locks` | `FOR UPDATE` — SOQL row-level locking, Apex's only concurrency-control primitive |
| `immutability_locks` | `static final final const` |
| `cleanup` | `emptyRecycleBin( Database.rollback( clear(` |
| `encapsulation` | `private protected` |
| `listeners` | `trigger X on Y` (any trigger header — triggers are Apex's event-listener construct) |
| `test_skip` | `StubProvider Test.setMock @SuppressWarnings` |

## 4. What GitGalaxy explicitly does not track

Five keys are hard-set to `None` in Apex's `rules` dict (Rule 4 of the engine's generation rules:
explicitly `None`, never a forced-fit regex, when a dimension doesn't exist natively):

- **`closures`** — Apex has no true anonymous-function/closure construct.
- **`macros`** — Apex has no preprocessor; there's nothing analogous to `#define`.
- **`pointers`** — Apex is a fully managed, garbage-collected language with no pointer/address
  arithmetic surface at all.
- **`inline_asm`** — Apex runs exclusively inside the Salesforce platform sandbox; there is no
  bare-metal or inline-assembly escape hatch.
- **`thread_sleeps`** — Apex has no native synchronous sleep/delay primitive (its only "wait"
  shapes are asynchronous scheduling via `@future`/`Queueable`/`System.schedule`, already covered
  under `concurrency`).

Additionally (distinct from the five `None` keys above — see §1), Apex's `rules` dict never
defines `serialization_parsing`, `regex_execution`, `time_date_logic`, or `ipc_rpc_bridges` at
all, the "Hybrid domain sensors" group some other languages (e.g. C) wire up. No inline comment
explains the omission; it reads as the blueprint simply not having claimed that optional group
for Apex rather than a deliberate exclusion.

## 5. Known limitations (accepted, not fixed)

No test in either file is named with the `known_limitation` convention. Two gaps are, however,
documented via `xfail`-marked (though currently dead, non-executing — see note) case lists in
`test_apex.py`, which is the closest thing this language has to an accepted-not-fixed record:

1. **`args` bare-call ambiguity.** `TargetFunc(a, b);` (a plain call statement, not a definition)
   is listed in `test_apex_args`'s `xfail_invalid` as a case the `args` regex alone cannot
   distinguish from a real signature — unlike `func_start`, which gained the "Invocation Shield"
   gate via #1221 specifically to close this ambiguity for *itself*, `args` was never given the
   equivalent gate.
2. **`_dependency_capture` has no comment/string-literal shielding (recurring bug class 3).**
   `Type.forName('MyClass')` text sitting inside a string literal or a `//`/`/* */` comment still
   matches and gets attributed as a real dependency — three cases are listed in
   `test_apex_dependency_capture`'s `xfail_invalid` (a string-literal-embedded call, a `//`
   comment, and a `/* */` comment).

Note: in both cases the `xfail_invalid` list is only iterated to build (and discard) a
`pytest.param(...)` object — the loop never actually parametrizes a running test, so these cases
aren't currently exercised as live xfail assertions. They're accurate as documented intent, not as
enforced regression coverage; a future harden-strict-signatures/harden-language-extraction pass on
Apex should either wire them into real `@pytest.mark.parametrize` cases or resolve the underlying
regex gaps directly.

## 6. Test depth

- **Extraction gauntlet** (`func_start`/`args`/`class_start`/`_dependency_capture`): 4 test
  functions in `tests/extraction/languages/test_apex.py`, each covering multiple inline
  valid/invalid/pathological cases per rule (not individually parametrized, so pytest's collected
  count is 4 rather than the true per-case count). Fully migrated to the per-language file (epic
  #813, issue #849) — no `apex` references remain in the old monolithic gauntlet files
  (`test_function_extraction.py`, `test_args_extraction.py`, `test_class_extraction.py`,
  `test_dependency_extraction.py`).
- **Strict signature suite** (all other wired keys): 93 tests in
  `tests/extraction/languages/test_apex_strict.py` (epic #518, issue #573) — positive/negative
  match coverage per signature, a dedicated ReDoS-immunity sweep
  (`test_apex_redos_immunity_sweep`), a lexical-family block-comment regression test
  (`test_apex_lexical_family_block_comment_does_not_confuse_structural_rules`), and an
  intentional-double-classification test for `safety_bypasses` vs. `test_skip`'s shared
  `@SuppressWarnings` match (`test_apex_safety_bypasses_and_test_skip_suppresswarnings_intentional_double_classification`).

## 7. Relevant closed work

**Epic-level hardening passes:**
- [#849](https://github.com/squid-protocol/gitgalaxy/issues/849) (CLOSED, merged
  [#1005](https://github.com/squid-protocol/gitgalaxy/pull/1005)) — Extraction hardening for Apex
  (epic #813). Migrated test cases into the dedicated `test_apex.py` file, expanded the `generics`
  pattern to support up to 4 levels of inner nesting (`Map<String, List<Map<Id, Account>>>`), and
  added missing edge cases for properties, package-private classes, and namespace dot-notation.
- [#573](https://github.com/squid-protocol/gitgalaxy/issues/573) (CLOSED, merged
  [#762](https://github.com/squid-protocol/gitgalaxy/pull/762)) — Strict parsing tests for Apex
  structural signatures (epic #518). Coverage-only pass (55 tests at the time); confirmed no false
  collision between `func_start` and `generics` (`List<Account> accs = new List<Account>();`
  doesn't fire `func_start`, and `generics` doesn't fire on a bare method signature).

**Real bugs found and fixed (Apex-specific or Apex-included):**
- [#1264](https://github.com/squid-protocol/gitgalaxy/issues/1264) (CLOSED, fixed via
  [#1296](https://github.com/squid-protocol/gitgalaxy/pull/1296)) — `class_start` recall was 0%
  for apex (alongside csharp/fortran/solidity) despite near-100% `func_start` recall on the same
  corpus. Root cause wasn't any of the four languages' regexes: the class extractor never
  consulted per-language `class_start` patterns at all. Fixed centrally in `detector.py`, not in
  Apex's own rule definition.
- [#1221](https://github.com/squid-protocol/gitgalaxy/issues/1221) (CLOSED, fixed via
  [#1226](https://github.com/squid-protocol/gitgalaxy/pull/1226)) — `func_start`'s
  method-shorthand branch had no requirement that a real annotation/modifier/return-type prefix
  actually precede the name (all three were independently optional), so a bare call statement like
  `next();` satisfied the pattern identically to a real signature, across 6 languages including
  Apex. Fixed with the "Invocation Shield" gate described in §3 above.

**Cross-language fixes that touched Apex along the way:**
- [#1209](https://github.com/squid-protocol/gitgalaxy/issues/1209) (fixed via
  [#1212](https://github.com/squid-protocol/gitgalaxy/pull/1212)) — the `args` regex's
  whole-match fallback overcounted every zero/one-arg signature by +1 across 13 languages
  including Apex; fixed by wrapping the parenthesized parameter span in its own capture group.

**Real bugs found and fixed the same day, follow-on to the tri-comparison sweep:**
- [#1963](https://github.com/squid-protocol/gitgalaxy/issues/1963) (CLOSED same day) —
  `func_start` (and, confirmed separately, `args`) false-positived on `new ClassName(...)`
  object-instantiation expressions inside multi-line constructor-call arguments (e.g.
  `TestFactory.createSObject(\n  new Account(name = 'X'),\n  true\n)` misparsed `new Account(...)`
  as a method definition named `Account`, with a bogus 1-parameter arg count). Root cause: both
  regexes' optional return-type/modifier prefix group accepted *any* identifier-shaped token
  followed by whitespace, with nothing excluding the reserved `new` keyword — unlike
  csharp/java/groovy/dart, whose equivalent prefix groups already exclude it. Diagnosed via the
  tri-comparison ledger (`apex/function/existence/agree[gitgalaxy]_vs[tree_sitter]`), confirmed
  against the local `language-crucible` apex corpus (6 occurrences across
  `AuraEnabledRecipes_Tests.cls` and `SOQLRecipes_Tests.cls`), and fixed with a `(?!new\b)`
  negative lookahead in both regexes, mirroring csharp's own GHOST ARGS SHIELD precedent.
  `crucible_check.py`'s ~80-repo differential scan surfaced a third, independent instance of the
  same bug (`xml/apex/IterationRecipes_Tests.cls`, 3 more `new Account(...)` false positives
  inside a `List<Account>{...}` initializer) that neither the ledger sample nor the local corpus
  had shown — also resolved by the same fix, confirming it generalizes correctly. GitGalaxy's
  function count on the local corpus now matches tree-sitter exactly (38/38, zero name diffs).

Search performed via `gh issue list --search 'in:title "Extraction hardening: apex"'` /
`'in:title "Strict parsing tests: \`apex\`"'` / `'in:title apex'` (2026-08-20), cross-checked
against the PRs each closed issue links to.

## 8. Real-world evidence (`gitgalaxy-raw-output`)

Only two Apex repos exist in the `v2.4.7` corpus batch — a reflection of Apex's niche,
platform-locked ecosystem (no large public monorepos the way JavaScript/Python have; almost all
real-world Apex lives inside private Salesforce orgs, not public GitHub):

- **[`apex-recipes`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/apex-recipes/apex-recipes_galaxy_llm.md)**
  — Salesforce's own official recipes/demo repository
  (`trailheadapps/apex-recipes`), a curated collection of idiomatic Apex patterns (triggers,
  batch/queueable async jobs, SOQL/SOSL, testing conventions) maintained by Salesforce itself.
  Scanned in 0.71s.
- **[`fflib-apex-common`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/fflib-apex-common/fflib-apex-common_galaxy_llm.md)**
  — FinancialForce's widely-adopted enterprise Apex patterns library (`fflib`: Unit of Work,
  Application Factory/Service Locator, mocking via `fflib_ApexMocks`), the real-world source for
  the `dependency_injection` signature's `fflib_*` vocabulary in §3 above. Scanned in 0.1s.

Each `_galaxy_llm.md` is the human-readable architectural brief; `_galaxy_audit.json.gz` and
`_galaxy_sbom.json.gz` in the same directory carry the raw per-file signature counts and SBOM if
deeper inspection is needed.

## 9. Tri-comparison: GitGalaxy vs. tree-sitter (no ctags coverage)

Apex is one of 7 tree-sitter-baselined languages with no `universal-ctags` parser at all (see
`tests/tools/ctags_reader.py`'s own LANGUAGE COVERAGE docstring — Apex, Dart, Groovy, Scala, and
three others), so this is a 2-tool comparison (`gitgalaxy` vs. `tree_sitter`), not the 3-way shape
python.md/c.md's §9 use. Neither tool is treated as ground truth — every discrepancy the two
produced against each other was investigated by reading real source
(`docs/self_scan/how_to_investigate_a_discrepancy.md`'s process), not assumed. The full record is
`docs/self_scan/tri_comparison_ledger.json`, filterable to `"language": "apex"`.

**Result: 1 of 1 discrepancy shape (6 individual occurrences corpus-wide) resolved, 1 confirmed
GitGalaxy engine defect — found, root-caused, and fixed the same day** (see
[#1963](https://github.com/squid-protocol/gitgalaxy/issues/1963), closed). Current measured
numbers post-fix (`tests/tools/tri_comparison_chart.py --languages apex`,
`language-crucible/data/apex/apex-recipes/`):

| Signal | GitGalaxy | tree-sitter | Read as |
|---|---|---|---|
| Functions found (of 38 total claimed by either tool) | 38 | 38 | exact agreement, zero name diffs post-fix |
| Function precision (of what each tool claimed, how much corroborates) | **100%** (38/38) | **100%** (38/38) | tied — no badge |
| Class recall/precision | 4/4 | 4/4 | tied — no badge |
| Args exact-match | 38 | 38 | unranked found-count panel, no badge |

Before the fix, GitGalaxy over-claimed at 40/38 (95.0% precision) while tree-sitter sat at 100%
(38/38) — see the fix writeup below for what closed that gap.

### The one confirmed bug this pass found (root-caused and fixed)

- **`new ClassName(...)` constructor calls misparsed as function definitions.** The apex
  `func_start` regex's optional return-type/modifier prefix accepted any identifier-shaped token
  followed by whitespace at the start of a line, with no exclusion for Apex's `new` keyword — so a
  multi-line SObject-builder call like:
  ```apex
  Account acct = (Account) TestFactory.createSObject(
      new Account(name = 'Original Name'),
      true
  );
  ```
  had its `new Account(` line parsed as "return type = `new`, function name = `Account`" (with a
  bogus 1-parameter arg count derived from the constructor's own named-parameter assignment).
  tree-sitter's grammar correctly distinguishes `object_creation_expression` from
  `method_declaration` and never made this mistake. Confirmed via direct source read
  (`apex-recipes/AuraEnabledRecipes_Tests.cls:25,43`, the ledger's sampled pair), via running the
  regex standalone against the local corpus (6 total instances across 2 files:
  `AuraEnabledRecipes_Tests.cls:6,25,43`, `SOQLRecipes_Tests.cls:226,235,504`), and — separately —
  in the `args` regex itself, which shared the identical unshielded prefix shape (confirmed to
  false-positive on the same 6 lines standalone, though it never surfaced its own ledger shape
  since `args_count` is only derived within a scope `func_start` already anchored).
  An incidental-finding pass across sibling C-family/OOP languages (csharp, java, groovy, dart,
  kotlin, scala, php) found none of them reproduce this — csharp/java/groovy/dart already carry an
  explicit `(?!new[ \t\n]+...)` exclusion for exactly this shape (csharp's own "GHOST ARGS SHIELD"),
  so the fix applied an already-proven pattern from a sibling language rather than designing a new
  one: a `(?!new\b)` negative lookahead immediately before the optional prefix-consuming group in
  both `func_start` and `args`.

  `crucible_check.py`'s ~80-repo differential scan (required for any `language_standards.py`
  change per this repo's PR protocol) surfaced a **third, independent instance** of the same bug
  neither the ledger sample nor the local `apex-recipes/` corpus had shown:
  `xml/apex/IterationRecipes_Tests.cls`, 3 more `new Account(...)` false positives inside a
  `List<Account>{...}` collection initializer (lines 9–11). Also resolved by the same fix,
  confirming it generalizes correctly rather than being narrowly tailored to the two files
  originally found. Both `tests/golden_master_audit.json` and
  `tests/golden_master_zero_dep_audit.json` were re-blessed to reflect the intentional,
  correct output change (function/param counts, and their downstream derived metrics —
  topological coordinates, structural magnitude, testing-exposure percentage — recomputing
  from the corrected counts).

### Ties

- **Function existence/precision** — post-fix, both tools agree on all 38 real functions in the
  sampled corpus, 100%/100%, no badge (a tie).
- **Class existence/precision** — both tools agree on all 4 real classes in the sampled corpus,
  100%/100%, no badge.

### Scope caveat

This corpus (`apex-recipes/`) is small (2 `.cls` files with hits, single-digit class count) — the
1 discrepancy shape and its 6 (plus 3 more found via the wider crucible corpus) occurrences are
everything this methodology surfaced on the currently-available corpus, not a claim that apex's
`func_start`/`args` regexes have no other gaps a larger corpus might reveal. See the ledger entry
`apex/function/existence/agree[gitgalaxy]_vs[tree_sitter]` for the full investigation writeup.
