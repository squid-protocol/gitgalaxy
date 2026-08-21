# Where GitGalaxy's Signal Beats a Plain AST — and Where It Doesn't

`README.md`'s ["One Graph, Not Five Separate Tools"](../README.md#one-graph-not-five-separate-tools)
section is upfront about the general trade GitGalaxy makes: tree-sitter (and AST parsing in
general) is *more precise per file* than GitGalaxy's regex-based structural signatures, in
exchange for one comparable signal set across every language in a repo without a per-language
toolchain. That's still true as the general rule. This doc tracks the specific, measured
exceptions to it, so none of them get overstated into "GitGalaxy is more accurate than
tree-sitter" — it isn't, in general — or hidden because they're inconvenient for the general
narrative. Each exception below is its own narrow, evidence-backed claim, not a cumulative case
that the general rule is wrong.

## Claim 1: `args` counting where the grammar has no formal parameter list

For counting a function's **arguments** in languages/idioms where the grammar has **no formal
parameter-list syntax at all**, GitGalaxy's body-aware regex signal produces a more useful number
than a plain AST/tree-sitter read of the declaration, because the declaration has nothing there to
read. This is narrow on purpose: it's one signal (`args`), in specific circumstances (no formal
signature exists), not a general claim about parsing quality.

## Plain-language version

Bash and traditional-style Perl don't have a "parameter list" the way Python, Java, or JavaScript
do. `quiet_cd()` in bash and `sub foo { }` in Perl are permanently, structurally zero-argument as
far as the formal grammar is concerned — that's not a parsing gap, it's just what the language
looks like. A real function still takes real inputs, though: bash reads them out of `$1`, `$2`,
`"$@"` inside the function body; traditional Perl reads them out of `my ($x, $y) = @_;` or a
`shift` call, also inside the body.

A tool that only looks at the declaration (a plain AST walk asking "does this function node have a
parameters field") finds nothing for either of these and correctly reports 0 — correct, because
there genuinely is no formal signature, but useless as a coupling/complexity signal, since it
reports 0 for every single such function regardless of how many arguments it actually consumes.

GitGalaxy's `args` structural signature reads the function's *body* instead of its declaration,
using the same idiom a human reading the code would: how many distinct `$N` positions does this
bash function reference? How many variables does that `my (...) = @_` line unpack? That produces a
real, differentiated number per function — exactly the kind of signal risk-scoring and coupling
analysis need, and exactly what a declaration-only AST read cannot produce here because the
information was never in the declaration to begin with.

## The evidence

This started as a measurement bug, not a marketing claim, and the fix is what makes the claim
checkable. `tests/tools/tree_sitter_accuracy_audit.py` grades GitGalaxy's `args` signal against
tree-sitter's own parse as ground truth — but its original `_get_param_count` only ever checked
the declaration node for a formal parameter field, the same declaration-only view a plain AST tool
would use. For shell and perl that made the "ground truth" itself blind to the same body idiom
GitGalaxy was reading, so the comparison was comparing GitGalaxy's real signal against an
artificially empty baseline:

| Language | Before (ground truth = declaration only) | After (ground truth = body-aware, same idiom GitGalaxy reads) |
|---|---|---|
| shell | 0% (0/3) | **100% (3/3)** |
| perl | 14.6% (137/937) | **82.1% (769/937)** |

The fix (`_count_shell_real_positional_max` / `_count_perl_real_args` in the audit tool) makes the
*ground truth* walk the same body text for the same idiom, using tree-sitter's own real parse (it
parses `$1`/`my (...) = @_`/`shift` fine — nothing here requires a special grammar). Once both
sides are asked the same question, they agree almost all of the time. The residual gap in each
case is documented in the tool's own module docstring (`tests/tools/tree_sitter_accuracy_audit.py`,
`#1518`/`#1519`) — mostly a known, hard-to-fix-without-real-scope-tracking case where a nested
anonymous Perl sub's own `my (...) = @_` gets counted as if it belonged to the outer sub, since a
flat regex scan has no real block-nesting awareness. Not hidden, just not chased further yet.

## Other confirmed and candidate instances of this same shape

Claim 1 is about a *property of the language*, not a one-off pair of languages, so it's worth
tracking where else it shows up rather than letting bash/perl stand in as the only examples.

- **m4** — confirmed, already implemented, no further work needed. `define(foo, ...)` macros have
  no parameter-list syntax at all, identical to bash's situation; GitGalaxy's m4 `args` rule
  already reads the same `$1`/`$2`/`$@`/`$#` body idiom (`gitgalaxy/standards/language_standards.py`,
  m4's `"args"` rule) — this is a second, real instance of Claim 1, just never separately logged
  until now.
- **batch** (`.bat`/`.cmd`) — same shape again (`%1`-`%9`, `%*` read from the body, no declared
  parameter list), but **not yet implemented**: batch's entry in `language_standards.py` currently
  has `"rules": {}` — no `func_start`, no `args`, no structural signatures of any kind extracted
  from batch files today. This isn't a measured win (there's nothing running to measure), it's an
  open, scoped opportunity for a future `harden-language-extraction` pass — noted here so it
  doesn't get lost as a one-off observation.

## Where Claim 1 does NOT apply

- Any language with real formal parameter-list syntax (Python, Java, Rust, Go, JavaScript, most
  of the 31 languages this tool baselines) — there, tree-sitter's declaration-based ground truth
  *is* the fair comparison, and a GitGalaxy/tree-sitter mismatch there is a real GitGalaxy
  precision bug to fix, not a "different question" situation. See the six prior fixes in this same
  file's docstring (solidity #1503, tcl #1504, haskell #1505/#1511, ruby #1506) — those were all
  real bugs, found and fixed the normal way.
- Modern Perl 5.20+ explicit signatures (`sub foo($x, $y) { ... }`) — these DO have a real formal
  parameter list, and both GitGalaxy and the ground truth already prefer it over the body-idiom
  fallback when present.
- Function *recall/precision* (finding the right set of functions at all) — Claim 1 is
  specifically about the `args` (parameter count) signal, not `func_start`/`class_start` accuracy,
  where tree-sitter's grammar-based approach is generally the better ground truth. Claim 2 below is
  the one narrow, separately-evidenced exception to that.

## Claim 2: function recall inside dialect/extension syntax the base grammar doesn't parse

For source that uses a language *dialect or extension* a plain tree-sitter grammar has no concept
of, GitGalaxy's dialect-agnostic regex still finds every function; a grammar built for the base
language alone can lose track of scope at the dialect boundary and silently drop real occurrences
inside it. This is a recall claim (finding functions at all), the specific case Claim 1 above
says tree-sitter usually wins — narrow for the same reason: it only applies where the file's
syntax genuinely diverges from the grammar being used as ground truth, not as a general recall
claim.

**The evidence:** `tests/tools/tree_sitter_accuracy_audit.py` measures python against
tree-sitter-python — a pure-Python grammar with no notion of Cython's `cdef class` syntax.
`language-crucible/data/python/cython/MemoryView.pyx` has 4 separate `cdef class` blocks
(`array`, `Enum`, `memoryview`, `_memoryviewslice`), each defining its own `__dealloc__`,
`__cinit__`, `__getbuffer__`, etc. GitGalaxy's regex-based `func_start` doesn't care what kind of
`class`/`cdef class` block a `def` sits inside and correctly finds all of them. tree-sitter-python
loses track of scope at each `cdef class` boundary and doesn't reliably re-emit a
`function_definition` node for every same-named method across those blocks, undercounting the
"real" occurrence count it's supposed to be the ground truth for. Confirmed via #1526's
per-occurrence line-based pairing (previously, collapsing same-named occurrences onto one dict
slot per file masked this almost entirely) — every one of the resulting "extra" (GitGalaxy found,
tree-sitter didn't) occurrences on this corpus traces to this one file and this one cause.

**The same mechanism, one level up (2026-08-20, tri-comparison-ledger-sweep):** tree-sitter-python
doesn't just lose track of scope *inside* a `cdef class` block, it fails to recognize the `cdef
class` declaration itself as a class at all — `tree_sitter_accuracy_audit`'s own walk over
`MemoryView.pyx` reports 0 class nodes for the file, missing all 4 (`array`, `Enum`, `memoryview`,
`_memoryviewslice`), while both GitGalaxy's `class_start` regex and ctags correctly identify all 4
by name (`python/class/existence/agree[ctags,gitgalaxy]_vs[tree_sitter]`,
`tri_comparison_ledger.json`). Same underlying cause as the function-recall case above (the base
grammar has no concept of the `cdef class` construct at all), just one syntactic level higher.

**A third instance, same file family (2026-08-21, tree-sitter-accuracy-audit `--all` sweep):**
`language-crucible/data/python/cython/MemoryView.pxd` (a Cython header/declaration file, not the
`.pyx` implementation file the two cases above are drawn from) has 16 bare, top-level `cdef`
function declarations with no enclosing `cdef class` at all — `array_cwrapper`, `memoryview_check`,
`get_memview`, `transpose_memslice`, etc. (e.g. line 91: `cdef inline bint
memoryview_check(object o) noexcept:`). tree-sitter-python doesn't parse a `cdef`-prefixed
declaration as a `function_definition` node under any circumstance, inside a class or not — it has
no concept of the keyword at all, confirmed via a direct walk showing zero tree-sitter nodes for
any of the 16. GitGalaxy's regex-based `func_start` doesn't care about the `cdef`/`cpdef`/`def`
prefix distinction and correctly finds all 16. Surfaced as a `tree_sitter_accuracy_baseline_
python.json` "regression" (`extra_functions: 0 -> 16`) purely because the baseline metric treats
tree-sitter as ground truth — reviewed and re-blessed rather than treated as a real defect, same
"ground truth can be wrong" precedent as csharp/cpp/c's own baseline entries in this file's SCOPE
& LIMITATIONS section.

## Claim 3: function recall when a grammar's own parse error cascades into unrelated real code

For a file where the grammar hits a genuine parse error on some in-scope, valid construct it
doesn't (yet) support, tree-sitter's error-recovery can lose track of real functions elsewhere in
the file — including code with no syntactic relationship at all to whatever failed to parse —
because the resulting `ERROR` node swallows a large downstream region. GitGalaxy's regex-based
`func_start` never builds or depends on a parse tree, so it isn't affected by this cascade and
keeps finding real occurrences the grammar's own output can no longer see. This is a *different*
mechanism from Claim 2: Claim 2 is a grammar that has no *concept* of a dialect at all (Cython's
`cdef class`); Claim 3 is a grammar that's *supposed* to support the construct — this is standard,
valid, modern C# — but has an actual parsing bug/gap in the installed version that corrupts
recovery for unrelated surrounding code.

**The evidence:** `tests/tools/tree_sitter_accuracy_audit.py` measures csharp against
tree-sitter-c-sharp (via `tree_sitter_language_pack`). `language-crucible/data/csharp/roslyn/LanguageParser.cs`
(14,680 lines) was first flagged for this in #1427, which found the ground-truth tree missing
`method_declaration` nodes for three real methods (`AccumulateExplicitInterfaceName`,
`CanFollowCast`, `CanReuseVariableDeclarator`) and attributed it to `private ref struct
DisposableResetPoint` at line 14575 (`tree.root_node.has_error == True`).

**Correction (2026-08-14):** that attribution was wrong, and the real scope is far larger than
three names. Re-bisecting the file confirms the `ref struct` at line 14575 parses cleanly in
isolation — tested standalone (`private ref struct DisposableResetPoint : IDisposable { ... }`
inside a plain class), `has_error` is `False`. The actual trigger is a C# 11 list pattern
combined with a property pattern, over 9,000 lines earlier, at line 5198:
```csharp
if (modifiers is [.., SyntaxToken { Kind: SyntaxKind.ScopedKeyword } scopedKeyword])
```
Tested in isolation, this single construct alone produces `has_error == True`. Once tree-sitter
hits it, recovery never resynchronizes for the rest of the file: `real_functions` ground truth is
157 (matching GitGalaxy almost exactly — only 2 "extra") for everything *before* line 5198, and
exactly **0** for everything from line 5198 to the end of the file (line 14680) — despite that
region containing hundreds of ordinary, valid methods (`GetOriginalModifiers`,
`ParseEventFieldDeclaration`, `HasEntryPointSignature`, `TryGetInterceptor`, and on). Every one of
csharp's 316 "extra" (false-positive) functions reported by the audit tool falls in this region;
GitGalaxy finds all of them correctly (spot-checked several against the source directly) — the
`ref struct` at 14575 was never the cause, just one more casualty deep inside the same
already-corrupted 9,500-line stretch. #1427's 3-name exclusion undersold this by roughly two
orders of magnitude; a proper fix needs to exclude the whole post-5198 region of this one file,
not name-list three functions within it.

### How long can a gap like this actually last?

*Note: the tracker research below was done against the original (incorrect) `ref struct`
attribution, before the 2026-08-14 correction above identified the real trigger as a list-pattern
+ property-pattern construct instead. It's kept as background evidence that tree-sitter-c-sharp
has a real, independently-confirmed class of "one bad construct corrupts recovery for the rest of
the file" bugs — the general mechanism still holds — but none of the specific issues cited below
were checked against the list-pattern construct itself; that tracker research hasn't been done.*

Checked this against the upstream grammar's own bug tracker rather than assuming it's a
one-off, since the answer changes how much weight this claim should carry. `tree-sitter-language-pack`
pins an exact commit hash per grammar in a manifest (not "always latest"), so staleness here has
two independent layers: whatever the upstream grammar itself hasn't fixed yet, *plus* whatever gap
opens up between that and whenever this repo's pinned pack version last got bumped. Tracing the
first layer for `ref struct` specifically, on `tree-sitter/tree-sitter-c-sharp`:

- **Issue #14** ("Add ref_type," filed Nov 2019) — closed via a real fix, **PR #251** ("Add
  ref/ref readonly types," Dec 2022). So basic `ref`-type support isn't an abandoned, decade-old
  gap — it landed a bit over 3 years after being reported.
- **Issue #361** ("`struct`'s modifiers are too sensitive to order," filed Dec 2024, **still open**
  as of the most recent activity) — this is the live mechanism, reported independently by the
  grammar's own users: if `ref` isn't textually adjacent to `struct` (other modifiers like
  `private`/`partial` sitting between them), the grammar misparses the whole declaration as a
  `ref_type` variable declaration instead of a `struct_declaration`. The reporter's own words:
  *"It's enough to have just one such error in a file to completely mess up its parsing"* —
  independent confirmation, from the people who wrote the grammar, of exactly the cascade Claim 3
  describes.
- **PR #439** (Aug 2026, days before this was written) — the maintainers shipped a set of
  *deliberately failing* corpus tests documenting 8 more known parse gaps, explicitly framed as
  "a bug report expressed as executable tests," not fixes.

So the honest answer is **years, even against an actively-maintained grammar** — this repo had
real commits within the month this was written. These aren't neglect; they're genuine parsing
ambiguities (grammar conflicts that are hard to resolve without breaking something else), and the
maintainers are transparent that a backlog of them exists on purpose rather than hidden.

(Sources: [tree-sitter-c-sharp#14](https://github.com/tree-sitter/tree-sitter-c-sharp/issues/14),
[#361](https://github.com/tree-sitter/tree-sitter-c-sharp/issues/361),
[#439](https://github.com/tree-sitter/tree-sitter-c-sharp/pull/439),
[xberg-io/tree-sitter-language-pack](https://github.com/xberg-io/tree-sitter-language-pack) — checked
directly via `gh api`/`WebFetch`, not recalled from memory.)

### Why GitGalaxy doesn't hit this particular wall

This is the more general point Claim 3 is really an instance of. GitGalaxy commits to exactly four
things per file — classes, functions, arguments, and a fixed set of structural signatures
(branch/io/safety_bypasses/etc.) — never a complete, general-purpose parse tree. That narrower
contract is what frees it from several constraints a real grammar has no choice but to carry:

- **No obligation to resolve every valid ordering/combination into one canonical tree.** A grammar
  has to decide, unambiguously, what `private ref partial readonly struct Foo` parses into for
  *every* legal permutation of C#'s modifier keywords, because downstream consumers (LSPs,
  refactoring tools, syntax highlighters) need one authoritative tree to build on. A regex only
  needs to recognize "roughly this shape, in roughly this area" — modifier order essentially never
  matters to it, because it was never trying to build a tree in the first place.
- **No global coherence requirement.** A parse tree is one connected structure; an error anywhere
  in it has to be *recovered from* somehow, and recovery can misattribute large stretches of
  otherwise-normal code to the wrong node (exactly what happened here). GitGalaxy's regex matches
  are independent per-occurrence — a construct it can't parse just doesn't match, and every other
  match in the file is completely unaffected, because there's no shared tree state for the failure
  to propagate through.
- **No obligation to track the full, versioned grammar surface.** A real grammar has to be
  extended and re-validated against every new construct a language ever adds, forever, or it
  starts silently misparsing modern code (exactly the `ref struct` gap here). The *shape* of a
  function or class declaration — a name, a parameter list, an opening brace — is far more stable
  across decades of language evolution than the full grammar surface is, which is a large part of
  why the regex approach ages better on this specific axis even as it loses on parsing depth.

None of this makes GitGalaxy's structural-signature engine more *capable* than a real parser —
it still can't tell you a variable's inferred type, walk an expression tree, or resolve a symbol.
It's a narrower promise, and Claims 1 through 3 are exactly the places where that narrower promise
turns out to be an advantage instead of a limitation.

### Second instance (2026-08-14): javascript, where the same cascade *hallucinates* instead of going blind

`#1633` found the identical root mechanism — one unparseable construct corrupting error recovery
for unrelated real code elsewhere in the file — in `tree-sitter-javascript`, but with the opposite
symptom shape. csharp's cascade (above) goes *blind*: the corrupted region yields zero structure,
so GitGalaxy's real matches there look like false positives (inflated "extra"). javascript's
cascade *hallucinates*: recovery keeps emitting structured-looking nodes in the corrupted region,
some of which are garbage that resembles a real function definition closely enough to be counted
as one.

**The evidence:** `language-crucible/data/javascript/react/ReactFiberBeginWork.js` uses Flow type
annotations (`function f(x: Type): ReturnType {`) that the plain (non-Flow) `tree-sitter-javascript`
grammar can't parse — 626 separate `ERROR` nodes, the first at line 10. During recovery, the
grammar repeatedly emits `method_definition` nodes whose "name" field resolves to a plain
control-flow keyword: eleven separate `if (...) { ... }` statements (lines 346, 3243, 3305, 3668,
3770, 3775, 3811, 3980, 4077, 4150, 4169) each parse as a `method_definition` literally named
`if`, its `(...)` condition standing in for a formal parameter list. GitGalaxy, correctly, never
reports a function named `if` — so each of these became a permanent, unfindable "missing" entry in
`tree_sitter_accuracy_audit.py`'s ground truth, deflating measured javascript func_recall for
something GitGalaxy was never wrong about (704 phantom-inflated "real" functions measured vs. the
619 that remain once these are excluded, on top of a 596-vs-598-ish separate accounting of the
already-documented "invisible Flow-typed function" gap described earlier in this doc — recall on
this corpus moved from 85.1% to 96.6% purely from removing ground-truth garbage, GitGalaxy's own
`found_functions`/`extra_functions`/`args_exact_match` numbers unchanged).

**Why "hallucinates" needed a narrower fix than "goes blind."** csharp's cascade region has *no*
salvageable structure at all — the fix there is a flat file+line-range exclusion. javascript's
error recovery resyncs locally instead of staying corrupted for the rest of the file, so a first
attempt at the equivalent fix (excluding everything past the file's detected cascade-start line
from ground truth, mirroring csharp's fix exactly) was tried and reverted: it discarded far more
genuinely-real, genuinely-matched functions than the handful of phantom entries it removed
(`found_functions` dropped 599→491 while `extra_functions` went *up* — a net regression, not an
improvement). The fix that actually worked is a targeted name+node-type filter instead of a
region exclusion: reserved words (`if`/`for`/`while`/`switch`/`catch`/`else`/`do`) can never
legally be a real JS identifier, but *are* legal as an object-literal property/method name written
with an explicit `function` keyword (`catch: function(fn) { ... }`, confirmed real and common in
`jquery/deferred.js:66`) — so the filter is scoped specifically to the ES6 shorthand-method node
shape (`method_definition`), not the broader `function_expression`/`pair` shape that legitimate
`catch: function(){}` uses. An earlier, broader version of the filter (any reserved-word name,
any node type) wrongly dropped that legitimate `catch` ground-truth entry too, which then made
GitGalaxy's own correct detection of it look like a new false positive — caught by re-running the
audit tool after the change, not assumed correct from the diff alone.

Fixed in `tests/tools/tree_sitter_accuracy_audit.py`'s `measure()` (`walk()` closure), not
GitGalaxy's engine — this is purely a measurement-tool correction; GitGalaxy's own detected
function set for this corpus is byte-for-byte identical before and after.

## A third confirmed instance: C, local single-function recovery (2026-08-19)

A narrower version of this same mechanism, found via the tri-comparison ledger
(`c/function/existence/agree[gitgalaxy]_vs[ctags,tree_sitter]`, 4 occurrences,
`cpython/typeobject.c`): a bare macro-invocation LINE at file scope with no expansion available to
a raw grammar walk (`SLOT1(slot_mp_subscript, __getitem__, PyObject *)`, `SLOT0(slot_tp_str,
__str__)` — real CPython macros that generate a wrapper function, but aren't themselves valid
freestanding C without expansion) locally confuses both tree-sitter's and ctags' parse of the
SINGLE function immediately following it. Confirmed directly at 4 sites, same shape every time —
`slot_mp_ass_subscript` (line 10544), `slot_nb_inplace_power` (10697), `slot_tp_repr` (10714),
`slot_tp_hash` (10730) are all ordinary, unremarkable `static ... name(...) { ... }` definitions
with nothing unusual about them individually; each sits directly after one of these bare macro
lines. GitGalaxy's regex has no such adjacency sensitivity and finds all 4 correctly; ctags and
tree-sitter both miss all 4. Unlike the csharp/javascript cascades above, this recovers
immediately (only the one adjacent function is lost, not everything downstream) — a third,
narrower recovery shape worth naming alongside the other two rather than assuming either.

## Where Claim 3 does NOT apply

- This is a grammar-*implementation* limitation (a specific parser version's bug/gap on one
  construct), not a language-design property like Claim 1, or a dialect the grammar was never
  built to understand like Claim 2 — a fixed/newer `tree-sitter-c-sharp` release could close this
  exact gap entirely. Don't generalize this into "GitGalaxy beats tree-sitter on csharp" — it's
  narrow to files containing a construct the installed grammar version fails on, where recovery
  swallows otherwise-unrelated real code.
- True recovery (walking into the `ERROR` node for salvageable structure) wasn't feasible here —
  the node has no structural subtree at all, just flat unstructured tokens — so the fix in
  `tree_sitter_accuracy_audit.py` needs to be a file+line-range-scoped ground-truth exclusion (the
  whole region from the line-5198 trigger to end of file), not a name list. #1427's original
  3-name exclusion was confirmed too narrow by the 2026-08-14 correction above: the real scope is
  the entire back half of the file (0 real_functions recognized past line 5198, vs. 157 before
  it), not 3 isolated names. **Don't assume this generalizes to every language's cascade** — the
  javascript instance above (`#1633`) is the counter-example: its error recovery keeps producing
  salvageable (if occasionally garbage) structure well past the first parse error instead of going
  fully flat, so the same region-exclusion approach actually *lost* real signal there and had to be
  replaced with a narrower name+node-type filter. Check which shape a new instance is before
  picking a fix, don't default to the csharp shape.

## Claim 4: counting one function once, when a grammar's node granularity is per-clause

For a language where a single function definition is legally written as multiple separate
equations (Haskell's pattern-matching clauses: `f (Just x) = ...` / `f Nothing = ...`, still one
function `f`), GitGalaxy's regex-based extraction already reports it the way a human — or the
language's own compiler — counts it: **one** function. Tree-sitter's grammar, by contrast, gives
each clause its own distinct node, because that's the right granularity for a syntax tree, not for
"how many functions are here." Read naively as ground truth for function *count*, that per-clause
granularity overcounts real functions by roughly (clauses − 1) for every multi-clause definition —
a systematic measurement distortion, not a difference in what either side actually detects. This
is a *counting-semantics* claim, distinct from Claims 1-3: not a missing signal (Claim 1), not a
dialect the grammar can't parse (Claim 2), and not a parser bug corrupting recovery (Claim 3) — the
grammar parses every clause correctly; the mismatch is purely in what one tree node is defined to
represent versus what one "function" means to the language.

**The evidence:** `tests/tools/tree_sitter_accuracy_audit.py`'s haskell `func_node_types` includes
`"function"` — tree-sitter-haskell's node for a single pattern-matched equation. Parsing a minimal
three-clause definition directly confirms each clause is its own sibling `function` node under the
same `declarations` parent:

```haskell
deNote :: Inline -> Inline
deNote (Note _) = Str ""
deNote x        = x
```

produces one `signature` node plus **two separate** `function` nodes (rows 1 and 2) — tree-sitter
has no single node representing "`deNote`, the function" as one unit; GitGalaxy's own
`_slice_by_indentation` (detector.py) already merges exactly this shape into one `FunctionNode`
by design (#1442's own comment: "clauses 2..N would otherwise each spawn their own duplicate,
overlapping FunctionNode").

Measured on `language-crucible/data/haskell/pandoc` (the audit tool's pinned 7-file corpus,
2026-08-14): before this was fixed, the shipped baseline reported `real_functions=275,
found_functions=139` — **50.5% recall**. Filed as #1614 and fixed in the audit tool itself (not
GitGalaxy) via #1618: `measure()`'s `walk()` now collapses consecutive same-name `function`/`bind`
siblings under one parent into a single occurrence, keyed by the first clause's line — asking the
ground truth the same question GitGalaxy's own `detector.py` already answers, gated strictly to
`lang == "haskell"` (verified zero behavior change across all other 30 baselined languages via
`--all --ci`). Post-fix, the committed baseline reads `real_functions=146, found_functions=139` —
**95.2% recall**, same alignment algorithm (`_align_occurrences_by_line`), same GitGalaxy output,
unchanged. Every one of the ~40 names the pre-fix (per-clause) measurement listed as "missing" in
this corpus (`deNote`, `blockToInlines`, `isPara`, `toJSON`, `tabFilter`, `compactify`, and so on)
was a multi-clause definition GitGalaxy had found in full — the "miss" was always the (N−1)th
clause of a function GitGalaxy had already reported once, correctly.

The residual, genuine gap after collapsing (7 real misses, not a counting artifact) is a
different, much smaller problem, filed separately: local `where`/`let`-introduced helpers whose
first clause has no `=` on its own line at all (guard-only equations like
`isAllowedPunct c | cond = ... | otherwise = ...`, #1616), and single-line `where name args = expr`
openers (the same shape #1564 already fixed for `let`, not yet extended to `where`, #1615).

## Where Claim 4 does NOT apply

- This is specific to languages whose grammar represents one logical function as multiple
  sibling nodes (Haskell's equation clauses). Languages with one node per function declaration
  (the overwhelming majority of the 45 languages this tool baselines) have no such mismatch —
  there, a tree-sitter node count and a real function count already agree, and a GitGalaxy/
  tree-sitter mismatch is a real bug to chase, same caveat as every other claim in this doc.
  Prolog and Erlang have the same clause-based shape and would likely exhibit this if ever added
  to `NODE_MAPS`; not yet checked, noted here so it isn't rediscovered from scratch.
- Doesn't excuse GitGalaxy from genuine recall gaps found *after* collapsing — the 7 residual
  guard-only/inline-`where` misses above (#1615, #1616) are real GitGalaxy defects, not an
  audit-tool artifact, and are tracked as their own issues rather than folded into this claim.
- The fix belonged in the audit tool's ground-truth extraction (collapse consecutive same-name
  clause siblings before counting), not in GitGalaxy — GitGalaxy's one-function-per-name behavior
  was the thing already correct here. Implemented in #1618.

## Claim 5: uniform recognition of "function-shaped" declarations a grammar splits into a distinct, unnamed wrapper layer

For a language where the grammar represents getters, setters, and operator overloads as *nested*
node types one level *below* a generic, unnamed "method" wrapper — rather than as first-class
siblings of a plain function/method declaration — GitGalaxy's flat regex recognizes all of them
uniformly, with zero per-shape special-casing, because it never had a node hierarchy to consult in
the first place. A ground-truth walk built the "obvious" way (recognize the wrapper node type,
read its `name` field) misses every one of them, not because the grammar failed to parse them —
it parsed them perfectly — but because the identifying field sits one level deeper than the node
type being matched. This is a *different* mechanism from Claim 4: Claim 4 is a grammar splitting
one logical function into too many nodes (over-counting real occurrences); Claim 5 is a grammar
nesting one logical function inside a node whose own outer layer looks unnamed (undercounting a
naive ground truth's real occurrences to zero for that whole shape).

**The evidence:** `tests/tools/tree_sitter_accuracy_audit.py` measures dart against
tree-sitter-dart. Every dart method — a plain function, a getter, a setter, an operator overload —
parses as a `method_signature` node, but `method_signature` itself carries **no `name` field of
its own**; it wraps exactly one inner node (`function_signature`, `getter_signature`,
`setter_signature`, or `operator_signature`) that carries the real, field-tagged name. Confirmed by
direct parse:

```dart
int get bar => 1;
set bar(int v) {}
bool operator==(Object other) => true;
```

produces `method_signature → getter_signature → [name] identifier "bar"`,
`method_signature → setter_signature → [name] identifier "bar"`, and
`method_signature → operator_signature → (no field-tagged name at all — the symbol `==` sits as a
plain child right after the literal `operator` keyword token)`. `NODE_MAPS["dart"]`'s
`func_node_types` (the same registry Claim 4 lives in) originally listed `method_signature` and
`function_signature` — covering plain functions/methods correctly — but never `getter_signature`,
`setter_signature`, or `operator_signature`, so ground truth structurally could not see a getter,
setter, or operator overload as a "real function" at all, regardless of how correctly GitGalaxy's
own `func_start` regex found them (its `(?:(?:get|set|factory|const)[ \t\n]+)?` prefix and
`operator[ \t\n]+[^\s\w]+` alternative treat all four shapes identically — no dart-specific
node-hierarchy knowledge required, because a regex was never walking a hierarchy to begin with).

Measured on `language-crucible/data/dart/flutter` (the audit tool's pinned 7-file corpus,
2026-08-14):

| Metric | Before (ground truth blind to getter/setter/operator) | After (all 3 node types added to `NODE_MAPS`) |
|---|---|---|
| `real_functions` | 1172 | 1748 |
| `found_functions` | 1108 | 1340 |
| `extra_functions` | 418 | **186** |
| func precision | 72.6% | **87.8%** |
| args_exact_match | 960 | 1175 (86.6% → 87.7%) |

`extra_functions` — GitGalaxy names ground truth had no record of — dropped by more than half
(418 → 186) purely from teaching the ground truth to look one node deeper for these three shapes;
GitGalaxy's own output was unchanged throughout. Fixed in `_get_node_name` (a new
`operator_signature` branch joining the literal "operator" keyword with the following symbol
child's text, matching how `detector.py` normalizes internal whitespace out of its own captured
`"operator=="`-style names) and `_get_param_count` (extending the existing no-`"parameters"`-field
`function_signature` branch to `setter_signature`/`operator_signature`, which share the identical
direct-`formal_parameter_list`-child shape; `getter_signature` needs no branch at all since a Dart
getter can never declare parameters).

**A real gap this surfaced, filed separately, not part of this claim:** fixing the ground truth's
blind spot also revealed that when a getter and setter (or any two same-name declarations) share
one identifier within a file, GitGalaxy's own `detector.py` records only **one** of the two
occurrences — confirmed directly against the real corpus DB: `editable_text.dart` has both
`bool get enabled => _enabled;` (line 153) and `set enabled(bool newValue) {` (line 155), but
`function_data` contains exactly one row for `enabled` (the setter, line 155). This is why
measured func *recall* moved the *wrong* direction alongside the precision win (94.5% → 76.7%,
+576 newly-real occurrences but only +232 newly-matched) — a genuine GitGalaxy recall defect, not
a byproduct of this claim's ground-truth fix, and not folded into Claim 5's own evidence. Filed as
#1626, alongside four other real `func_start` false-positive bugs this same investigation turned up
(#1622 `try`/`finally` misdetected as phantom functions, #1623 bare field/local-var declarations
misdetected as function stubs, #1624 closure-literal-argument call sites misdetected as
definitions, #1625 bodyless zero-prefix constructors not found) — none of those five are part of
this claim either; they're real GitGalaxy defects to fix, not ground-truth artifacts.

## Where Claim 5 does NOT apply

- This is specific to grammars that nest a function-like construct's identifying node *below* the
  generic node type a naive walk would match on (dart's `method_signature` wrapper). Grammars
  where the function-like node itself carries the name field directly have no such gap — there, a
  GitGalaxy/tree-sitter mismatch is a real bug to chase, same caveat as every other claim in this
  doc.
- Doesn't excuse the same-name-collision recall defect surfaced above — that's a real GitGalaxy
  bug, tracked separately, not evidence for this claim.
- The fix belonged in the audit tool's ground-truth node registry (`NODE_MAPS`) and name/arity
  resolution (`_get_node_name`/`_get_param_count`), not in GitGalaxy — GitGalaxy's uniform
  getter/setter/operator recognition was the thing already correct here.

## Claim 6: structure recall inside opaque macro bodies (Rust)

For languages with powerful macro systems, tree-sitter often treats the bodies of macro definitions and invocations as opaque token trees. GitGalaxy's regex-based structural signatures are completely unaffected by the macro wrapper and correctly parse these definitions, resulting in higher recall than tree-sitter.

**The evidence:** The `tree-sitter-rust` parser treats the bodies of `macro_rules!` definitions and function-like macro invocations (e.g., `quote!`, `ast_struct!`) as opaque token trees. It does not emit nested `struct_item`, `enum_item`, or `function_item` nodes. GitGalaxy correctly parses these structural definitions, which the audit script misclassifies as false positive "extra" structures. Confirmed concrete instances of both shapes, independently verified (tri-comparison ledger,
2026-08-19): `bevy/bevy_ecs_macros.rs:456` -- real `fn get_param`/`init_access`/`apply`/etc.
definitions inside a `quote! { ... }` invocation body; `serde/serde_core_de_impls.rs:90,112,136,
998,1036,1403` -- real `struct NonZeroVisitor`/`SaturatingVisitor`/`SeqVisitor`/etc. definitions
inside `macro_rules!` bodies (`impl_deserialize_num!`, `seq_impl!`, `tuple_impl_body!`), each
immediately followed by a real `impl Visitor for <Name>` block confirming they're genuine,
complete struct definitions, not fragments. ctags' Rust parser has the identical blind spot for
both shapes, for the same reason (it reads macro bodies as raw tokens too, not just tree-sitter).

## Claim 7: function recall in the presence of heavy preprocessor directives (Fortran/C++)

For codebases that rely heavily on C Preprocessor (CPP) directives, grammar-based parsers like tree-sitter can fail to build a valid syntax tree, missing large sections of code. GitGalaxy's regex is entirely unaffected by CPP noise and extracts these functions perfectly.

**The evidence:** The `tree-sitter-fortran` ground truth parser completely fails on files that rely heavily on C Preprocessor directives (like `#if ( EM_CORE == 1 )` in the WRF corpus), throwing errors and missing entire sections of code that contain valid functions. GitGalaxy is completely unaffected by the CPP noise and extracts these subroutines perfectly, resulting in false positive 'extra functions' reported by the audit.

**C instance, narrower in scale (2026-08-19, tri-comparison ledger
`c/function/existence/agree[ctags,gitgalaxy]_vs[tree_sitter]`, 13 occurrences):** where Fortran's
gap swallows entire trailing sections of a file, tree-sitter-c's version is local -- one function
lost per trigger, not a cascading region -- but the same "CPP directive breaks the grammar's parse"
root cause, confirmed at 3 distinct trigger shapes (all cpython/micropython, all GitGalaxy+ctags
correct, tree-sitter alone missing the function): (1) an `#if`/`#else` pair splitting a single `if`
condition inside a function body (`cpython/ceval.c:33`, `_Py_ReachedRecursionLimitWithMargin`'s
`#if _Py_STACK_GROWS_DOWN` / `#else` around its recursion-limit check); (2) an `#if`/`#endif`
wrapping only the `static` storage-class specifier, separated from the rest of the signature
(`micropython/compile.c:3473-3476`, `mp_compile_to_raw_code`); (3) bare, un-semicoloned macro
invocations (`_Py_COMP_DIAG_PUSH`/`_Py_COMP_DIAG_IGNORE_DEPR_DECLS`/`_Py_COMP_DIAG_POP`,
`cpython/object.c:1269-1271`) whose lack of a trailing `;` the grammar can't cleanly recover from,
losing the next real function (`_PyObject_SetAttributeErrorContext`).

## Claim 8: precision under C preprocessor noise — dead-code shielding and macro hallucinations

For C, the preprocessor adds a meta-layer of syntax (conditional compilation, macro definitions)
that a plain AST read can mistake for real function definitions. This is the PRECISION mirror of
Claim 7's recall claim: Claim 7 is about tree-sitter *missing* real functions when CPP breaks its
parse; this is about tree-sitter's raw node stream *hallucinating* functions that were never real
to begin with — a dead `#if 0` block, a macro definition, a bytecode switch-case label that merely
looks structural.

**The evidence:** `tests/tools/tree_sitter_accuracy_audit.py`'s `_C_KNOWN_MACRO_HALLUCINATIONS`
skip list (added while chasing false "extra" reports for CPython/SQLite/MicroPython in the c
corpus) exists because tree-sitter's raw C grammar parse genuinely reports these as
`function_definition` nodes — `#if 0`-guarded dead code (`print_stack`, `PlinkPrint`,
`tos_char`), and macro-shaped constructs that only look like a definition
(`DICT___REVERSED___METHODDEF`, `MP_BC_BINARY_OP_MULTI`). #1849's dual-bar instrumentation in
`measure()` now measures this directly instead of requiring a one-off count: on the committed c
baseline (`tests/tree_sitter_accuracy_baseline_c.json`), GitGalaxy's own `extra_functions` is 9
(genuine regex false positives) while tree-sitter's raw, uncorrected reading has
`ts_extra_functions` = 71 — the gap is exactly the skip-list corrections, i.e. exactly this claim,
now a live measured number instead of a doc snapshot. The same file's c `class_data` shows the
same shape for bodyless forward-declared structs: `extra_classes` is 0 for GitGalaxy vs.
`ts_extra_classes` = 27 for tree-sitter's raw reading.

Confirmed again independently via the tri-comparison ledger (`c/function/existence/agree[
tree_sitter]_vs[ctags,gitgalaxy]`, 74 occurrences, 2026-08-19), with exact citations this time:
`language-crucible/data/c/cpython/dictobject.c:522-527`'s `#if SIZEOF_VOID_P > 4 / else if (...) /
#endif` desyncs tree-sitter's parse into misreading the bare `if` keyword as a function name;
`dictobject.c:5102`'s `DICT___REVERSED___METHODDEF` sits inside a `PyMethodDef` array initializer,
not a definition; `dictobject.c:7396`'s `_PyObject_ManagedDictValidityCheck` and
`frameobject.c:1264-1313`'s `tos_char`/`print_stack`/`print_stacks` are all genuinely
well-formed function definitions living entirely inside an `#if 0 ... #endif` dead-code guard
("useful for debugging the stack marking code"). GitGalaxy and ctags both correctly exclude all
six; tree-sitter's raw parse has no preprocessor model and reads the dead branch as live.

## Claim 9: argument counting across grouped parameter declarations (Go)

Go allows grouping consecutive same-typed parameters under one shared type annotation
(`func makePos(b *src.PosBase, line, col uint) Pos`) — `line` and `col` share `uint` without
repeating it. `tree-sitter-go` wraps this whole group in a single `parameter_declaration` AST
node containing multiple identifier children, which a naive "one node, one parameter" AST walk
undercounts as a single parameter. GitGalaxy's args counter reads the actual comma-separated
identifiers inside the group, not the wrapper node count.

**The evidence:** Scanning `func makePos(b *src.PosBase, line, col uint) Pos { ... }` in isolation
(2026-08-18, current `gitgalaxy/core/detector.py`) reports `args=3` (`b`, `line`, `col`), matching
the true arity — a wrapper-node-count read would report 2 (one per `parameter_declaration`, not
per identifier).

## Claim 10: excluding anonymous closures from named-function counts (Ruby)

`tree-sitter-ruby` parses `lambda { ... }`/`-> { ... }` closures using its `method` node type —
the same node type real named `def`-declared methods use — so a plain "count every `method` node"
AST read conflates anonymous closures with real named function declarations, inflating the
function count. GitGalaxy's `func_start` only matches named `def`/`class`-scoped declarations;
`lambda`/`->`/`Proc.new` closures are a separate, deliberately distinct signal
(`closures` in the structural-signature set), not counted as functions.

**The evidence:** Scanning a file with one real method containing two closures
(`def bar; x = -> { 1 }; y = lambda { 2 }; end`) (2026-08-18, current `gitgalaxy/core/detector.py`)
reports exactly one function (`bar`) — the two closures are correctly excluded from
`function_data`, not counted as two additional (anonymous, unnamed) function rows the way a plain
`method`-node walk would.

## Claim 11: disambiguating a generic trait-bound arrow from a return-type arrow (Rust)

Rust's generic trait bounds can themselves contain a `->` (e.g. `Fn(&Token) -> bool` inside
`F: Fn(&Token) -> bool`), sitting between the parameter list's opening paren and the function's
OWN return-type arrow. A parameter-list scanner that stops at the first `->` it sees, or gets
confused by the bound's nested parens, can misparse the boundary between the generic bound and
the real parameter list. GitGalaxy's args counter correctly treats the bound's arrow as opaque and
still resolves the real parameter list.

**The evidence:** Scanning `fn eat<F: Fn(&Token) -> bool>(f: F) -> bool { ... }` in isolation
(2026-08-18, current `gitgalaxy/core/detector.py`) reports `args=1` (`f`), the true arity — a
scanner confused by the bound's internal `->`/parens would either miscount or fail to find the
real parameter list at all.

## Claim 12: recognizing dialect-specific label syntax a generic ctags parser's identifier convention excludes

For a language/dialect whose real identifier syntax is broader than the conventional
letter-first, no-punctuation identifier shape most parsers assume, GitGalaxy's regex-based
`func_start` recognizes it correctly (because its character class is written for the actual
dialect) while a generic ctags language parser — built for the common case, not this specific
historical dialect — silently declines to tag it at all. This is a *lexical-coverage* claim,
distinct from every other claim in this doc: it isn't about macro opacity (Claim 6), CPP noise
(Claims 7/8), node granularity (Claim 4), or a nested wrapper node (Claim 5) — the construct isn't
hidden inside anything; ctags' parser looks straight at the label and rejects the token shape
itself.

**The evidence:** AGC (Apollo Guidance Computer) assembly — the real Apollo 11 flight software in
`language-crucible/data/agc_assembly/apollo-11/` — uses two label conventions no generic assembler
identifier syntax anticipates: (1) an embedded hyphen naming a point relative to an event, e.g.
`TIG-35`/`TIG-30`/`CALLT-35` in `BURN_BABY_BURN--MASTER_IGNITION_ROUTINE.agc:250,292,222` ("35/30
seconds before Time of Ignition" — a real, common AGC idiom, not a one-off); (2) a label starting
with a digit or a leading minus sign, e.g. `1CHK`/`2EBANK`/`-1CHK` in
`AGC_BLOCK_TWO_SELF-CHECK.agc:184` (the real label text is `-1CHK`, one of several numbered
variants of a `CHK`-suffixed check routine). GitGalaxy's `func_start` regex for this language
matches on `^([A-Z0-9_-]+)` at line start, deliberately including digits and hyphens because
that's what real AGC label syntax allows. `ctags_reader.py` maps `agc_assembly` to Universal
Ctags' generic `Asm` parser (there is no dedicated AGC ctags parser) with kind `l` (labels) as the
function-analog. Directly confirmed by running `ctags --language-force=Asm --kinds-Asm=l` against
the real corpus files: it emits **zero** tags for any hyphenated or digit/minus-leading label
sampled, while emitting tags normally for every plain-alphanumeric sibling in the same file (e.g.
`CNTRCHK`, `ERASCHK`, `SELFCHK` are all tagged; `-1CHK` is not) — a corpus-wide cross-reference
found this holds for the full discrepancy set, not just the sample (14/35 hyphenated + 21/35
digit/minus-leading = 35/35, tri-comparison ledger
`agc_assembly/function/existence/agree[gitgalaxy]_vs[ctags]`, validated 2026-08-20). Ctags' `Asm`
parser's tag-name validation requires a leading letter and no internal hyphen — a completely
reasonable default for the assembly dialects it was actually built against, just not for AGC's.

## Where Claim 12 does NOT apply

- This is specific to a dialect whose real lexical grammar (what counts as a valid identifier)
  diverges from the generic parser's assumption, not a general claim that GitGalaxy out-recalls
  ctags on assembly. The *majority* of this same ledger shape's sibling
  (`agc_assembly/function/existence/agree[ctags]_vs[gitgalaxy]`, 265 occurrences) is the opposite
  situation: ctags' `Asm` parser tags every line-start label unconditionally (including pure
  data/constant-definition labels GitGalaxy's `func_start` deliberately excludes because they're
  never followed by a real instruction), so ctags is the more *recall*-permissive of the two there
  — a genuine, honest granularity difference, not evidence for this claim. Don't read Claim 12 as
  "GitGalaxy beats ctags on AGC assembly" in general; it's narrow to the specific label-punctuation
  shapes ctags' identifier convention structurally cannot admit.
- A real subset of GitGalaxy's own miss side of that same shape (50/265) is a confirmed GitGalaxy
  defect in `detector.py`'s `_slice_by_labels`, not something this claim covers — see the filed
  GitHub issue for the `RELINT`-as-terminator and single-line-block-discard bugs. Two independent
  root causes, both real bugs, tracked separately from this claim.

## Where this doc is used

- README.md's "One Graph, Not Five Separate Tools" section links here as the narrow exceptions to
  its general "AST usually wins on precision" framing.
- `tests/tools/tree_sitter_accuracy_audit.py`'s own module docstring cites this doc next to the
  `#1518`/`#1519` writeup (Claim 1), the Cython `.pyx` note in its SCOPE & LIMITATIONS section
  (Claim 2), the `#1427` csharp `ref struct` parse-error writeup (Claim 3), the haskell
  multi-clause counting writeup (Claim 4), and the dart `NODE_MAPS["dart"]["func_node_types"]`
  comment next to `getter_signature`/`setter_signature`/`operator_signature` (Claim 5), so a future
  reader hitting any of those ground-truth code paths understands why it looks structurally
  different from the rest of `_get_param_count`/the recall comparison.
- Per `CLAUDE.md`'s standing instruction, any newly-found case of GitGalaxy's structural-signature
  output being more accurate than tree-sitter's/an AST's on some signal gets logged here as its own
  Claim N, evidenced the same way — not folded into the README's general framing uncredited, and
  not left undocumented because it's a narrow case.
- #1849 added a second, symmetric measurement to `tree_sitter_accuracy_audit.py`: `ts_found_*`/
  `ts_extra_*`/`ts_args_exact_match`, tree-sitter's own raw (uncorrected) reading scored against
  the same reconciled ground truth GitGalaxy is scored against, rendered as a second bar per
  language on `docs/self_scan/tree_sitter_accuracy_chart.svg`. Claim 8 is the first claim in this
  doc backed directly by that live measurement (`ts_extra_functions`/`ts_extra_classes` on the c
  baseline) rather than a one-off manual count — future claims of this shape (tree-sitter's raw
  reading being noisier than GitGalaxy's) should cite the same fields instead of re-deriving a
  fresh count by hand. The recall side (`ts_found_functions` vs. `real_functions`) reads 100% by
  construction for most languages (ground truth is walked from tree-sitter's own tree, so it can't
  miss what it defines) — except csharp/fortran/rust, where `measure()`'s promotion step adds
  already-source-verified blind-spot/cascade-region GitGalaxy matches (Claims 3/6/7) directly into
  ground truth, so tree-sitter's real recall loss there shows as a genuine gap instead of reading
  artificially perfect. That promotion is deliberately NOT applied to every language that happens
  to trigger the general cascade detector — javascript is the documented counter-example (Claim 3:
  its cascade "resyncs locally" rather than going fully blind), so blind-promoting there risks
  blessing a genuine GitGalaxy false positive as ground truth. Scoped to csharp specifically (the
  one language independently verified fully-blind) until another language gets the same
  source-level verification.
- Claims 9-11 (Go grouped parameters, Ruby closures, Rust generic-bound arrows) consolidate and
  fact-check content from a since-deleted root-level `why_we_are_better_than_tree_sitter.md`,
  which didn't follow this doc's narrow/dated/evidenced-claim discipline (blanket "GitGalaxy is
  better than tree-sitter" framing, unverifiable snapshot numbers). Its TypeScript-signature-
  parsing content (bodyless overloads, nested generics, curried arrows) was deliberately NOT
  carried forward here — the ground-truth construction in `measure()` treats those specifically as
  *not* comparable to tree-sitter's output at all (an intentional exclusion, not tree-sitter
  "missing" them), so restating it as a tree-sitter-beats-tree-sitter claim would itself be an
  overstatement of exactly the kind this doc exists to avoid. Revisit only with a clean,
  independently-verified before/after.
