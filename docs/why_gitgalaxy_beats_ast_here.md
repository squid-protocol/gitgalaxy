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
(14,680 lines) declares `private ref struct DisposableResetPoint` at line 14575 — a C# 7.2+ `ref
struct`, ordinary modern C#, not an extension syntax the grammar has no notion of. The installed
grammar version fails to parse it (`tree.root_node.has_error == True`), and the resulting `ERROR`
node recovery leaves the ground-truth tree with zero `method_declaration` nodes for several real
methods elsewhere in the file, confirmed for three (`AccumulateExplicitInterfaceName`,
`CanFollowCast`, `CanReuseVariableDeclarator`) via three independent checks: a raw regex
`.finditer()` against the source, an isolated single-file `galaxyscope` scan, and a direct SQL
query against the resulting corpus DB — all three agree GitGalaxy finds exactly one occurrence of
each, correctly, while tree-sitter's parse has no record of any of them (#1427).

## Where Claim 3 does NOT apply

- This is a grammar-*implementation* limitation (a specific parser version's bug/gap on one
  construct), not a language-design property like Claim 1, or a dialect the grammar was never
  built to understand like Claim 2 — a fixed/newer `tree-sitter-c-sharp` release could close this
  exact gap entirely. Don't generalize this into "GitGalaxy beats tree-sitter on csharp" — it's
  narrow to files containing a construct the installed grammar version fails on, where recovery
  swallows otherwise-unrelated real code.
- True recovery (walking into the `ERROR` node for salvageable structure) wasn't feasible here —
  the node has no structural subtree at all, just flat unstructured tokens — so the fix in
  `tree_sitter_accuracy_audit.py` is a narrow, file+name-scoped ground-truth exclusion for the
  three confirmed-affected names, not a general "any `ERROR` node nearby" heuristic. Other
  functions elsewhere in the same corrupted region may still be silently affected but unconfirmed
  — noted as an open question in #1427, not chased further.

## Where this doc is used

- README.md's "One Graph, Not Five Separate Tools" section links here as the narrow exceptions to
  its general "AST usually wins on precision" framing.
- `tests/tools/tree_sitter_accuracy_audit.py`'s own module docstring cites this doc next to the
  `#1518`/`#1519` writeup (Claim 1), the Cython `.pyx` note in its SCOPE & LIMITATIONS section
  (Claim 2), and the `#1427` csharp `ref struct` parse-error writeup (Claim 3), so a future reader
  hitting any of those ground-truth code paths understands why it looks structurally different
  from the rest of `_get_param_count`/the recall comparison.
- Per `CLAUDE.md`'s standing instruction, any newly-found case of GitGalaxy's structural-signature
  output being more accurate than tree-sitter's/an AST's on some signal gets logged here as its own
  Claim N, evidenced the same way — not folded into the README's general framing uncredited, and
  not left undocumented because it's a narrow case.
