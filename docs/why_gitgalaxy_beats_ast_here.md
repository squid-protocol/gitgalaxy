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
  it), not 3 isolated names.

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

## Where this doc is used

- README.md's "One Graph, Not Five Separate Tools" section links here as the narrow exceptions to
  its general "AST usually wins on precision" framing.
- `tests/tools/tree_sitter_accuracy_audit.py`'s own module docstring cites this doc next to the
  `#1518`/`#1519` writeup (Claim 1), the Cython `.pyx` note in its SCOPE & LIMITATIONS section
  (Claim 2), the `#1427` csharp `ref struct` parse-error writeup (Claim 3), and the haskell
  multi-clause counting writeup (Claim 4), so a future reader hitting any of those ground-truth
  code paths understands why it looks structurally different from the rest of
  `_get_param_count`/the recall comparison.
- Per `CLAUDE.md`'s standing instruction, any newly-found case of GitGalaxy's structural-signature
  output being more accurate than tree-sitter's/an AST's on some signal gets logged here as its own
  Claim N, evidenced the same way — not folded into the README's general framing uncredited, and
  not left undocumented because it's a narrow case.
