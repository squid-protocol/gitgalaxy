# C# — Structural Signature Coverage

Snapshot generated 2026-08-21 against `main`. Source: `LANGUAGE_DEFINITIONS["csharp"]` in
`gitgalaxy/standards/language_standards.py`, `tests/extraction/languages/test_csharp.py` /
`test_csharp_strict.py`, closed GitHub issues, `docs/self_scan/tree_sitter_accuracy_history.csv` /
`tests/tree_sitter_accuracy_baseline_csharp.json`, and
[`gitgalaxy-raw-output`](https://github.com/squid-protocol/gitgalaxy-raw-output). Re-run the
`language-status` skill's data-gathering commands before trusting these numbers if this doc looks
old relative to `last_updated` below.

## 1. At a glance

| Field | Value |
|---|---|
| `_meta.status` | `production` |
| `_meta.target_version` | C# 14 / .NET 10 / Modern ASP.NET Core & Blazor |
| `_meta.blueprint_version` | v5.0 |
| `_meta.last_updated` | 2026-02-18 |
| `lexical_family` | `standard_block` (`//` line comments, `/* */` block comments) |
| Structural signature keys wired | 51 / 52 (1 explicit `None`, see §4) |
| Extraction-gauntlet tests (`test_csharp.py`) | 61 |
| Strict-signature tests (`test_csharp_strict.py`) | 106 |
| Total dedicated C# test cases | 167 |
| Real-world function recall vs. tree-sitter ground truth (`tree_sitter_accuracy_audit.py`) | 100.0% (964/964) — see §9 |
| Real-world function precision vs. tree-sitter ground truth | 99.9% (964/965 claims) — see §9 |
| Real-world class recall / precision vs. tree-sitter ground truth | 100.0% / 100.0% (33/33) — see §9 |
| Real-world args-count exact match (for functions found) | 97.3% (938/964) — see §9 |

## 2. Identification surface

- **Extensions:** `.cs .csx .razor .cshtml .cake .linq .ashx .asmx .ascx .svc` — modern C#,
  C# scripting, Razor/Blazor views, Cake build scripts, LINQPad scratch files, and legacy
  ASP.NET generic/web-service handler formats.
- **Exact filenames:** `build.cake` — extensionless Cake build script.
- **Discriminators:** `.cs`, `.csproj`, `.sln`, `packages.config`, `nuget.config`, `global.json`,
  `App.config`, `Web.config`, `project.json` — ecosystem/project-file anchors.
- **Shebangs:** `dotnet-script`, `csi` (C# Interactive).

## 3. What GitGalaxy detects

Grouped by the phase headers `language_standards.py` and `how_to_add_a_language.md` use.
Description is what C#'s *actual* regex matches, not the generic cross-language definition.

**Topology & structure**
| Key | What it captures for C# |
|---|---|
| `branch` | `if else switch case default for foreach while do catch finally continue break goto try yield return yield break`, pattern-matching `and or not`, `?? ?. ` and the standalone ternary `?` |
| `args` | Three signature shapes via the "Ghost Args Shield": Branch 1 standard methods (requires a return type before the name), Branch 2 constructors (no return type, so anchored instead to a trailing `:`/`{` or `base`/`this` initializer), Branch 3 fat-arrow lambdas — designed to demand structural proof rather than hallucinate ordinary invocations as definitions |
| `structural_boundaries` | `var return class interface struct record enum using namespace yield await delegate event init required field implements extends declare`, `=>` |
| `func_start` | The "Iron Wall" extractor: steps over up to 5 stacked `[Attribute]` lines (including vertically-split ones), an "Instantiation Shield" rejecting `new Foo(...)` as a false constructor match, bounded modifier/return-type walking immune to ReDoS, an "explicit interface implementation" name form (`IFoo.DoWork`), and a bare-`;`-terminated "zero-prefix" branch gated behind an Invocation Shield requiring the signature to actually open a block (`{` or `=>`) |
| `class_start` | `class interface struct record enum` (including `record struct`/`record class`), with generic-parameter and primary-constructor `(...)` step-overs before the base-list `:` check, and `readonly`/`ref` struct modifiers |

**Safety & risk**
| Key | What it captures for C# |
|---|---|
| `safety` | `try catch finally checked is as nameof required ArgumentNullException ThrowIfNull ThrowIfNullOrWhiteSpace`, `[Required]`/`[NotNull]`/`[Authorize]` attributes, `?? ?.` |
| `safety_bypasses` | Null-forgiving `!.`/`null!`, `#pragma warning disable`, `.Result`/`.Wait()` (sync-over-async blocking), `dynamic` |
| `high_risk_execution` | `Thread.Abort Process.Start Environment.FailFast Environment.Exit goto` |
| `io` | `File Directory Stream HttpClient Path SqlConnection SqlCommand DbContext DbSet HttpRequest HttpResponse` (dotted member access), `[Table(` |
| `api` | `public`/`internal` modifiers, `[HttpGet/HttpPost/HttpPut/HttpDelete/Route/ApiController/HubMethodName]` attributes, minimal-API `app.MapGet/Post/Put/Delete/Group` |
| `state_mutation` | `set`/`field` accessor blocks, `volatile`, `ref `/`out ` parameter modifiers, line-start `field = value;` assignment, collection mutators (`Add Remove Clear Insert Push Pop Update`) |
| `dead_code` | Commented-out (`//` or `/* */`) `public private protected internal class void if for foreach while return using` |
| `doc` | `///` XML doc comments, `<summary>`/`<param>`/`<returns>`/`<remarks>` tags |
| `test` | `[Test Fact Theory TestMethod TestClass SetUp TearDown]` attributes, `Assert. Mock. Substitute.For`, FluentAssertions' `Should()` |

**Architecture & domain sensors**
| Key | What it captures for C# |
|---|---|
| `concurrency` | `async await Task ValueTask Thread Parallel SemaphoreSlim Mutex Channel IAsyncEnumerable Interlocked` |
| `ui_framework` | `ControllerBase IActionResult Binding ObservableCollection DependencyProperty ComponentBase RenderFragment MonoBehaviour` (ASP.NET MVC/WPF/Blazor/Unity) |
| `closures` | `=>`, `delegate {` |
| `globals` | `ConfigurationManager AsyncLocal`, `Environment.`, `public static [readonly] TYPE UPPER_NAME =`, `[ThreadStatic]` |
| `decorators` | Any line-start `[Attribute(...)]` |
| `generics` | `<Uppercase...>` type-parameter shapes, `where T :` constraint clauses |
| `comprehensions` | LINQ method-syntax chain (`.Select/.Where/.OrderBy/.GroupBy/.Aggregate/.Any/.All/.ToList/.ToArray/.SelectMany(`) or query-syntax `from x in` |
| `scientific` | `Math. MathF. Vector2/3/4 Matrix4x4 Random Complex Tensor TensorPrimitives` |
| `reflection_metaprogramming` | `System.Reflection DllImport LibraryImport MethodInfo Activator Marshal. Emit ILGenerator` |
| `import` / `_dependency_capture` | `using [static] Namespace;` (including `global using`); `_dependency_capture` also resolves alias directives (`using Alias = Target.Namespace;`) to the real target and steps over a closed generic suffix |
| `ownership` | `<author>`, `Author:`, `Created by` |

**Specialized subsystems**
| Key | What it captures for C# |
|---|---|
| `planned_debt` / `fragile_debt` | Shared `GLOBAL_` TODO/FIXME-family markers |
| `spec_exposure` | `[SPEC-123]`, `[spec ...]`, `[audit ...]` traceability tags, ReDoS-bounded |
| `ssr_boundaries` | `@page @rendermode @code @layout` Razor directives, `[Route]`/`[CascadingParameter]`, `RenderFragment ComponentBase IViewComponentResult` (the Blazor/Razor rendering boundary) |
| `events` | `event TYPE name`, `EventHandler Invoke Raise MediatR INotification IRequest Publish`, spaced `+=`/`-=` subscribe/unsubscribe |
| `dependency_injection` | `IServiceCollection AddTransient AddScoped AddSingleton AddKeyed [Inject] FromServices IServiceProvider` |
| `macros` | Line-start C preprocessor-style directives: `#define #undef #if #elif #else #endif #region #endregion #pragma #warning #error` |
| `pointers` | `fixed stackalloc Unsafe.AsPointer IntPtr UIntPtr nint nuint`, `->` |
| `memory_alloc` | `Marshal.AllocHGlobal GC.AllocateArray MemoryPool ArrayPool<...>.Shared.Rent`, `ref struct`, `scoped ref` |

**Resource management & stability**
| Key | What it captures for C# |
|---|---|
| `telemetry` | `ILogger`/`_logger`/`Log`/`TelemetryClient`/`ActivitySource` `.LogInformation/.LogError/.LogWarning/.LogDebug/.StartActivity/.TrackEvent`, `[LoggerMessage` |
| `debug_prints` | `Console.Write/WriteLine/Error`, `Debug.Write/WriteLine/Print` |
| `explicit_casts` | `as UppercaseType`, C-style cast `(int|long|short|byte|char|float|double|decimal|bool|string|Type) identifier` |
| `panics_and_aborts` | `throw abort FailFast Environment.Exit` |
| `thread_sleeps` | `sleep delay Task.Delay Thread.Sleep`, `Wait()` |
| `bitwise_ops` | `<< >> ^ ~` |
| `sync_locks` | `mutex lock Monitor Semaphore Interlocked SpinLock ReaderWriterLockSlim` (case-insensitive) |
| `immutability_locks` | `const readonly init Immutable*` |
| `cleanup` | `dispose close free delete GC.Collect GC.SuppressFinalize(` (case-insensitive, matches idiomatic PascalCase `.Dispose()`) |
| `encapsulation` | `private protected internal file` |
| `listeners` | `on addEventListener subscribe EventHandler` (case-insensitive, matches Rx.NET `.Subscribe`/SignalR `.On<T>`), `+=` |
| `test_skip` | `[Ignore]`/`[Skipped]`, xUnit `[Fact(Skip = ...)]`/`[Theory(Skip = ...)]`, `test.skip( mock( stub(`, `Substitute.For` |

**Hybrid domain sensors (C# specifics)**
| Key | What it captures for C# |
|---|---|
| `serialization_parsing` | `JsonSerializer.Deserialize JsonConvert.DeserializeObject XmlSerializer BinaryFormatter` |
| `regex_execution` | `Regex.Match(es) Regex.Replace Regex.IsMatch new Regex` |
| `time_date_logic` | `DateTime.Now DateTime.UtcNow DateTimeOffset TimeSpan Stopwatch.StartNew` |
| `ipc_rpc_bridges` | `Process.Start NamedPipeServerStream ChannelFactory GrpcChannel` |

C# has no `llm_api`/`llm_orchestrator`/`ml_traditional`/`dl_frameworks`/`vectorized_math`/
`lazy_evaluation`/`hardware_bridge`/`cryptography`/`exfiltration_camouflage`/`memory_scraping`/
`rce_funnel`/`_named_token_capture` keys in its `rules` dict at all — unlike Python/JavaScript's
64-key entries, C#'s entry defines only the 52 keys applicable to it (51 wired + `inline_asm`).
This is not a coverage gap to close; it reflects which signature dimensions this language's entry
was built with, per the engine's Strict Feature Parity rule.

## 4. What GitGalaxy explicitly does not track

One key is hard-set to `None` in C#'s `rules` dict (Rule 4 of the engine's generation rules:
explicitly `None`, never a forced-fit regex, when a dimension doesn't exist natively):

- **`inline_asm`** — no native inline-assembly construct (unlike C/C++'s `asm`/`__asm` blocks).

## 5. Known limitations (accepted, not fixed)

Two gaps are deliberately documented rather than fixed, via `known_limitation`-named tests in
`test_csharp.py`:

1. **`func_start` has no string/comment awareness at the regex level.** Function-shaped text
   inside a C# verbatim string (`@"..."`) or a C# 11+ raw string literal (`"""..."""`) that
   happens to land at true line start still matches the raw regex — the same architectural class
   of bug already confirmed for javascript/typescript template literals, Java text blocks, Go raw
   strings, and Rust raw strings (recurring bug class 3 in `how_to_harden_extraction.md`), now
   confirmed on a fifth language. C# routes through Mode B (`_slice_by_braces`, lexical family
   `standard_block`), which is currently gated to javascript/typescript only. Not fixed here —
   tracked as its own future audited follow-up in the epic.
2. **`_dependency_capture` matches inside verbatim strings.** Companion to the limitation above:
   `_dependency_capture` runs against fully unshielded raw file content for every language,
   unconditionally, so a `using ...;`-shaped line inside a C# verbatim string at true line start
   still produces a phantom dependency-graph edge (recurring bug class 10 in
   `how_to_harden_extraction.md`, present for every language, not C#-specific).

## 6. Test depth

- **Extraction gauntlet** (`func_start`/`args`/`class_start`/`_dependency_capture`): 61 tests in
  `tests/extraction/languages/test_csharp.py` — valid/invalid/pathological cases per rule, the two
  known-limitation tests above, and a dedicated regression test for issue #1428's lambda-arrow-
  inside-multi-line-call-arguments shield bypass. Fully migrated to the per-language file (epic
  #813, issue #820) — nothing left in the old monolithic gauntlet files for C#.
- **Strict signature suite** (all other wired keys): 106 tests in
  `tests/extraction/languages/test_csharp_strict.py`, including a dedicated `spec_exposure` ReDoS
  regression test and a broader `redos_immunity_sweep` (epic #518, issue #775; migrated out of
  `tests/core_engine/test_language_standards_strict.py`'s original single-file layout).

## 7. Relevant closed work

**Epic-level hardening passes:**
- [#775](https://github.com/squid-protocol/gitgalaxy/issues/775) — Strict parsing tests for C#
  structural signatures (epic #518). Folded four pre-existing scattered regression tests
  (`test_csharp_iron_wall_redos`, `test_csharp_args_lambda_redos_immunity`,
  `test_csharp_events_plus_minus_equals_operators`,
  `test_csharp_should_and_wait_boundary_regression`) into the new full per-signature suite.
- [#820](https://github.com/squid-protocol/gitgalaxy/issues/820) — Extraction hardening for C#
  (epic #813): the generic-parameter/primary-constructor `class_start` base-list fix, the
  `using`-alias-directive `_dependency_capture` fix, and the `spec_exposure` ReDoS bound (the
  10th language in the epic to hit that same adjacent-unbounded-quantifier shape).

**Real bugs found and fixed via accuracy-audit and precision-investigation work:**
- [#789](https://github.com/squid-protocol/gitgalaxy/issues/789) — `func_start` never matched
  expression-bodied methods, and could hallucinate a bare call with no enclosing brace as a
  function. First documented diagnosis of the "bare call statement misidentified as a definition"
  failure shape later confirmed to recur across javascript/typescript/java/apex/dart/groovy
  (issue #1221).
- [#1264](https://github.com/squid-protocol/gitgalaxy/issues/1264) (PR
  [#1296](https://github.com/squid-protocol/gitgalaxy/pull/1296)) — `[TIER 1]` class detection
  was 0% across apex/csharp/fortran/solidity despite near-perfect function detection — C#'s
  `class_start` regex existed but the audit tooling wasn't reconciling it correctly at the time.
- [#1314](https://github.com/squid-protocol/gitgalaxy/issues/1314) (PR
  [#1328](https://github.com/squid-protocol/gitgalaxy/pull/1328)) — confirmed C#'s func_start
  precision (58.2% at the time) as a genuine engine false-positive problem, not a ground-truth
  artifact (unlike the objective-c half of the same issue, which turned out to be 100%
  ground-truth-tool bug).
- [#1418](https://github.com/squid-protocol/gitgalaxy/issues/1418) (PR
  [#1429](https://github.com/squid-protocol/gitgalaxy/pull/1429)) — the args "Invocation Shield"
  didn't cover multi-line bare call statements ending in `;`; extended `func_start`'s zero-prefix
  branch with the same shield.
- [#1427](https://github.com/squid-protocol/gitgalaxy/issues/1427) (PR
  [#1551](https://github.com/squid-protocol/gitgalaxy/pull/1551)) /
  [#1567](https://github.com/squid-protocol/gitgalaxy/issues/1567) (PR
  [#1585](https://github.com/squid-protocol/gitgalaxy/pull/1585)) — the tree-sitter-c-sharp
  grammar itself has a parse-error cascade in `roslyn/LanguageParser.cs` (a C# 11 list-pattern +
  property-pattern construct at line 5198) that corrupts ground truth for ~9,500 unrelated lines
  downstream; #1427's original 3-name hand-exclusion undersold the scope by roughly two orders of
  magnitude, #1567 replaced it with a general "trailing error cascade" detector. Not a GitGalaxy
  defect — see §9 and `docs/why_gitgalaxy_beats_ast_here.md` Claim 3.
- [#1428](https://github.com/squid-protocol/gitgalaxy/issues/1428) (PR
  [#1454](https://github.com/squid-protocol/gitgalaxy/pull/1454)) — `detector.py`'s `;` vs.
  `{`/`=>` terminator shield was fooled by a lambda arrow inside multi-line call arguments,
  causing a call statement to be misread as an expression-bodied member.
- [#1473](https://github.com/squid-protocol/gitgalaxy/issues/1473) — the accuracy audit tool's
  `NODE_MAPS` ground truth omitted `enum_declaration`, understating `class_precision` (a
  measurement-tooling bug, not an engine defect).
- [#1642](https://github.com/squid-protocol/gitgalaxy/issues/1642) (PR
  [#1643](https://github.com/squid-protocol/gitgalaxy/pull/1643)) — `extra_classes` was counting
  real, correctly-found classes that happened to sit inside `LanguageParser.cs`'s known
  parse-error cascade region (same family as #1427/#1567, extended to the class-detection side of
  the audit tool for the first time).
- [#1708](https://github.com/squid-protocol/gitgalaxy/issues/1708) (PR
  [#1710](https://github.com/squid-protocol/gitgalaxy/pull/1710)) — `class_start`'s modifier
  alternation was missing `readonly`/`ref`, so C# 7.2+ `readonly struct`/`ref struct`/
  `readonly ref struct` declarations structurally failed to match; class recall 91.7% → 100%.

Search performed via `gh issue list --search 'in:title "Extraction hardening: csharp"'` /
`'in:title "Strict parsing tests: \`csharp\`"'` / `'in:title csharp'` (2026-08-21). Issues
#2035/#2036/#2051 and PRs #2037/#2039/#2040/#2047/#2052 are this doc's own companion
tri-comparison-ledger-sweep pass and are covered in §10 rather than here.

## 8. Real-world evidence (`gitgalaxy-raw-output`)

Three repos from the `v2.4.7` batch, chosen for a size/shape spread:

- **[`roslyn`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/roslyn/roslyn_galaxy_llm.md)**
  — the C# compiler's own reference implementation (`dotnet/roslyn`). The most adversarial C#
  codebase available: hand-written parsers/binders, deep generic type machinery, and (per §9's
  Claim 3 discussion) at least one construct the tree-sitter grammar itself doesn't fully parse
  yet. Scanned in 103.53s.
- **[`PowerToys`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/PowerToys/PowerToys_galaxy_llm.md)**
  — large, long-lived Microsoft production application; a mix of WPF/WinUI UI code, native
  interop (`pointers`/`reflection_metaprogramming`-relevant patterns), and modular
  plugin-per-feature architecture. Scanned in 16.72s.
- **[`port_csharp_manageddoom`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/port_csharp_manageddoom/port_csharp_manageddoom_galaxy_llm.md)**
  — a small, single-purpose C# port of the DOOM engine (`sinshu/managed-doom`); low-level,
  performance-sensitive game-loop code, a useful low-noise contrast to the other two. Scanned in
  0.99s.

Each `_galaxy_llm.md` is the human-readable architectural brief; `_galaxy_audit.json.gz` and
`_galaxy_sbom.json.gz` in the same directory carry the raw per-file signature counts and SBOM if
deeper inspection is needed.

## 9. Measured accuracy (real-world corpus, vs. tree-sitter ground truth)

Unlike python.md's and javascript.md's §9 (each a one-off, hand-built diff against `ast` /
`tree-sitter-language-pack`), C# already has a maintained, CI-wired measurement:
`tests/tools/tree_sitter_accuracy_audit.py`, run against the pinned
[`language-crucible`](https://github.com/squid-protocol/language-crucible) corpus (`v1.0`) —
6 real C# files, dominated by `roslyn/LanguageParser.cs` and `roslyn/CSharpCompilation.cs`
(mainstream Roslyn source, not synthetic fixtures). tree-sitter's own parse of each file becomes
the reconciled ground truth (real function/class names, positions, and parameter counts);
GitGalaxy's regex-based extraction is diffed against it for recall, precision, and args
exact-match. Tree-sitter's own raw reading is scored against that same reconciled ground truth
too (the `ts_*` columns below) — it is not treated as infallible, see the Claim 3 discussion
below for a concrete case where the reconciliation step had to correct for a bug in the grammar's
own parse.

**Current committed baseline** (`tests/tree_sitter_accuracy_baseline_csharp.json`, matching the
latest row in `docs/self_scan/tree_sitter_accuracy_history.csv` as of commit `b483d16f`, after
issues #2035/#2036 landed and the baseline was re-blessed in PR #2047):

| Signal | GitGalaxy | tree-sitter's own reading | Read as |
|---|---|---|---|
| Real functions (reconciled ground truth) | 964 | 964 | — |
| Function recall | **100.0%** (964/964) | 67.1% (647/964) | GitGalaxy finds every real function on this corpus; tree-sitter's own raw parse doesn't — see Claim 3 below |
| Extra (phantom) functions | 1 | 0 | Effectively noise-free on this corpus |
| Function precision | **99.9%** (964/965 claims) | 100.0% | Both essentially precise; tree-sitter trivially so since it only ever reports what it actually parsed |
| Real classes (reconciled ground truth) | 33 | 33 | — |
| Class recall | **100.0%** (33/33) | 72.7% (24/33) | Same cascade mechanism as function recall — see below |
| Class precision | **100.0%** | 100.0% | — |
| Args-count exact match (functions found) | **97.3%** (938/964) | 67.1% (647/964, i.e. only for the subset it found at all) | Strong but not perfect — see the open follow-up note below |

**Read as:** function and class recall are the standout result, and the reason *why* is itself
evidence for this repo's `docs/why_gitgalaxy_beats_ast_here.md` — this is **Claim 3**:
`language-crucible/data/csharp/roslyn/LanguageParser.cs` (14,680 lines) contains a valid, modern
C# 11 list-pattern + property-pattern construct at line 5198
(`if (modifiers is [.., SyntaxToken { Kind: SyntaxKind.ScopedKeyword } scopedKeyword])`) that the
installed tree-sitter-c-sharp grammar fails to parse (confirmed in isolation:
`tree.root_node.has_error == True` for that construct alone). Once the grammar hits it, error
recovery never resynchronizes for the rest of the file — real, ordinary, syntactically-unrelated
methods and classes from line 5198 to 14680 (`GetOriginalModifiers`, `ParseEventFieldDeclaration`,
`HasEntryPointSignature`, `TryGetInterceptor`, and hundreds more) are invisible to tree-sitter's
own raw parse, while GitGalaxy's regex-based `func_start`/`class_start` — which never builds or
depends on a parse tree — keeps finding them correctly (spot-checked against source directly,
issues #1427/#1567/#1642). This is a *different* failure mode from a grammar simply lacking a
dialect concept (Claim 2, e.g. Cython): C# 11 pattern matching is standard, current-generation
syntax the grammar is *supposed* to support, just has an actual, confirmed parsing gap in the
pinned version. The reconciliation logic in `tree_sitter_accuracy_audit.py` (`_find_trailing_error_cascade_start`,
added in #1567) corrects the *ground truth* for this — it still counts the post-cascade functions
as real — which is why GitGalaxy's own recall reads 100% rather than being penalized for
tree-sitter's blind spot; the `ts_func_recall_pct`/`ts_class_recall_pct` columns above are what
expose the raw magnitude of that blind spot on its own terms.

**The one open item:** args exact-match (97.3%) is the only signal below 99% on this corpus. A
follow-up investigation (issue #2051, opened as part of this doc's own companion
tri-comparison-ledger-sweep pass) found the `args` regex — unlike its `func_start` sibling, which
received targeted fixes for tuple return types and nested-paren parameter lists — was never
updated for the same shapes. That investigation and its fix status are covered in §10 rather than
here, since it was found and worked through the tri-comparison ledger process specifically, not
this section's tree-sitter-only measurement.

## 10. Tri-comparison findings (GitGalaxy vs. tree-sitter vs. ctags)

Section 9 measures GitGalaxy against one privileged ground truth (tree-sitter). This section is
different: a 3-way comparison where *no* tool is privileged (`tests/tools/
tri_comparison_gatherer.py`/`tri_comparison_reconcile.py`), logged per-discrepancy-shape in
`docs/self_scan/tri_comparison_ledger.json` and worked through via the `tri-comparison-ledger-sweep`
skill. As of 2026-08-21, **every currently-reproducing csharp shape is `status: "validated"` —
0 open questions left** (11 shapes at the start of this pass, covering ~330 raw occurrences).

**Current standing, all validated:**

| Category | Winner |
|---|---|
| Func recall | **GitGalaxy** (99.9% vs. ctags 84.0%, tree-sitter 67.0%) |
| Func precision | **GitGalaxy** (95.1% vs. ctags 99.9%, tree-sitter 100% — see the honest caveat below) |
| Class recall | tie (GitGalaxy = ctags, both 100%, tree-sitter 72.7%) |
| Class precision | tie (GitGalaxy = ctags, both 100%, tree-sitter 100%) |
| Args | tree-sitter (99.6% vs. ctags 99.1%, GitGalaxy 98.5% — root-caused, #2051 open for the fix) |

GitGalaxy's func precision (95.1%) reads *lower* than ctags/tree-sitter's here despite GitGalaxy
having found real bugs in both of them elsewhere in this section — this is not a contradiction.
Precision counts a tool's own uncorroborated claims against it; GitGalaxy correctly finds ~44 real
local (nested) functions inside `LanguageParser.cs`'s tree-sitter parse-error cascade region (see
§9's Claim 3) that ctags structurally cannot see either (no local-function concept in its csharp
kind map) — those are real, genuine GitGalaxy-only finds with zero possible corroboration, so they
count against precision by the metric's own honest definition, not because GitGalaxy is wrong.

**Where GitGalaxy had real, confirmed bugs — two fixed, two filed:**
- **[#2035](https://github.com/squid-protocol/gitgalaxy/issues/2035) (fixed, PR
  [#2039](https://github.com/squid-protocol/gitgalaxy/pull/2039))** — `func_start`'s return-type
  loop allowed unbalanced parens/commas in a single token, letting it swallow a real nested call
  expression as if it were part of a return type and capture an unrelated identifier as a phantom
  function (`GetWellKnownType(`, `this.EatToken(`). Bounded each token to a single character or one
  balanced non-nested paren group.
- **[#2036](https://github.com/squid-protocol/gitgalaxy/issues/2036) (fixed, PR
  [#2040](https://github.com/squid-protocol/gitgalaxy/pull/2040))** — `detector.py` unconditionally
  dropped every bodyless interface/abstract method declaration (any `;`-terminated `func_start`
  match), guarding against a C# 9+ top-level-statement false positive that regex hardening since
  then had already independently closed. A `;`-terminated match with a real modifier keyword
  (`match.lastindex == 1`) is now trusted as a genuine bodyless declaration. Recovered real
  functions GitGalaxy had never counted (`GetRoot`, `TryGetRoot`, `Initialize`, and — as an
  unexplained side effect discovered during re-verification — also fixed two more (`Matches`,
  `ShouldCheckTypeForMembers`) whose drop was never independently root-caused).
- **[#2051](https://github.com/squid-protocol/gitgalaxy/issues/2051) (open, not fixed)** — the
  `args` regex was never given the same tuple/generic-method treatment `func_start` received. Three
  independent, confirmed mechanisms: (1) the return-type-loop character class has no parens, so any
  tuple-shaped or generic-wrapped-tuple return type fails to match Branch 1 at all; (2) the shared
  capture group `(\([^)]*\))` truncates at the first unbalanced `)`, breaking on any tuple-typed
  *parameter*; (3) the name-capture has no generic-type-parameter stepper (`func_start`'s already
  does), so `Method<T>(...)` fails to match. Real corpus impact: `HasEntryPointSignature` (2 real
  params, GitGalaxy reports 0), `SetCurrentSolutionAsync<TData>` (7 real, reports 0), and several
  more — see the issue for the full per-mechanism evidence. Needs real design work across the regex
  plus full corpus verification, deliberately not attempted as a quick patch.
- **[#2054](https://github.com/squid-protocol/gitgalaxy/issues/2054) (open, not fixed)** — found
  during post-#2035 re-verification (a full, uncapped corpus diff, not just the ledger's capped
  example sample): two *more* `func_start` false positives survive, distinct from #2035's specific
  mechanism. `ref mdName` (a real call-argument prefix) gets misread as a declaration modifier
  because `ref` is also a legitimate Branch A modifier keyword; a ternary `?` operator gets consumed
  by the same return-type loop's nullable-type-marker allowance (`string?`), letting the walk skip
  past it onto `_syntaxFactory.TypeConstraint(` as a phantom function. Confirms the underlying
  "return-type-or-modifier walk can't always distinguish declaration syntax from call/expression
  syntax" shape has more edge cases than #2035 closed alone — filed for a dedicated pass rather than
  another one-off patch.

**Where ctags has real, structural limitations (not a GitGalaxy defect):**
- No concept of a local/nested function at all — its csharp kind map is only `m` (top-level
  methods; "C# has no free functions" per its own comment). Every local function GitGalaxy finds
  inside `LanguageParser.cs`'s cascade region (`validateSignature`, `isSupportedType`, dozens more)
  is invisible to ctags by construction, not a missed edge case.
- Isolated misses on ordinary top-level methods with complex signatures — nullable types, generic
  `out` parameters, or multiple default-valued parameters with a `Func<...>` delegate type
  (`FindEntryPoint`, `GetSourceDeclarationDiagnostics`) get no tag at all, confirmed via `ctags -x`
  showing tags immediately before/after but not at the affected line.
- An overload-name collision — `ReportUnusedImports` has two overloads at different lines; ctags
  tags only the first.
- A genuine false positive — a tuple-parameter `Equals` overload
  (`Equals((ImmutableArray<byte> ContentHash, int Position) x, ...)`) gets tagged under the name
  `bool` instead of `Equals`, apparently misreading the return-type/tuple-parameter boundary. The
  same tuple-parameter-splitting limitation separately mis-splits `GetHashCode`'s tuple-typed
  parameter into 2 counted params instead of 1.

All four documented in `tests/tools/ctags_reader.py`'s csharp KIND MAPS bullet.

**Where GitGalaxy wins outright, tree-sitter structurally can't (already documented in
`docs/why_gitgalaxy_beats_ast_here.md`, Claim 3):** the `LanguageParser.cs` parse-error cascade
described in §9 above — tree-sitter's own parse goes fully blind (`tree.root_node.type ==
"ERROR"`) for ~9,500 lines after the trigger construct, while GitGalaxy's regex-based extraction,
which never depends on a parse tree, keeps finding real functions and classes correctly throughout.
This is the single largest contributor to GitGalaxy's func-recall/class-recall lead in the table
above (271 function occurrences, 9 class occurrences).

**A real methodological bug in the ledger-sweep process itself, caught and fixed mid-pass:** the
`credit_tools` mechanism (see `tri_comparison_ledger.py`'s VERIFIED ADJUSTMENTS docstring) is only
mathematically valid for a shape where a tool is *completely alone* and otherwise uncorroborated —
crediting it converts an unconfirmed claim into a confirmed one. This pass initially misapplied it
to two 2-tool-*already-mutually-agreeing* shapes (`agree[ctags,gitgalaxy]_vs[tree_sitter]`,
`agree[gitgalaxy,tree_sitter]_vs[ctags]`), whose occurrences were already counted in base precision
before any credit — adding credit on top double-counted them, pushing GitGalaxy's func precision to
1297/965 (>100%), a real, user-visible chart-rendering bug (bars spilling past their container).
Caught by a user report, root-caused, and fixed by resetting `credit_tools` to empty on both
shapes and re-verifying every language's precision math stays ≤100% across the whole ledger, not
just csharp — worth recording here since it's a real trap in the sweep methodology itself, not
just a csharp-specific mistake.

Full record: `docs/self_scan/tri_comparison_ledger.json` (filter keys starting `csharp/`) and
`docs/self_scan/tri_comparison_points_of_interest.md`.
