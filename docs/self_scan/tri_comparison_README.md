# Tri-comparison: GitGalaxy vs. tree-sitter vs. ctags

This is the system `docs/self_scan/README.md` promised and never delivered — that file's
"tree-sitter as a baseline, not as infallible ground truth" section has said, since before this
system existed, "a universal-ctags-based comparison is in progress... this section will link to
it once it exists rather than describe it ahead of time." It exists now. This is that link.

## Why a third tool, and why no privileged ground truth

The 2-tool system (`tree_sitter_accuracy_audit.py`, documented in the main
[`README.md`](README.md)) treats tree-sitter's parse as ground truth and scores GitGalaxy against
it. That's a reasonable default — tree-sitter has real per-language grammars — but it has a
structural blind spot: whenever tree-sitter's own reading is wrong (a grammar gap, an
error-recovery artifact, a node-name-construction quirk), GitGalaxy gets scored as wrong too, even
when it's actually right. `docs/why_gitgalaxy_beats_ast_here.md` exists specifically because this
happens more than a "grammar = truth" framing would suggest.

Adding ctags as a third, independently-implemented reader turns disagreement from "GitGalaxy vs.
an assumed oracle" into "which of three differently-biased tools is actually correct here" — a
question with a real, checkable answer (read the source), not an assumed one. See
[`tests/tools/tri_comparison_reconcile.py`](../../tests/tools/tri_comparison_reconcile.py)'s own
module docstring (section `WHY THERE IS NO "GROUND TRUTH" HERE`) for the full reasoning; the short
version is: for every occurrence, if every available tool agrees it exists, that's consensus; each
matching tool gets credit. Where tools disagree, that occurrence contributes to a **discrepancy**,
not to any tool's score in either direction, until a human (or an agent standing in for one)
actually reads the source and the ledger records a verdict.

## How matching works

- **Primary match key is NAME**, not line position. `tri_comparison_reconcile.py`'s own
  `MATCHING METHODOLOGY` section documents the confirming probe: 153 matched-by-name Python
  functions in a real file showed zero line-offset drift once two tools agreed on a name — no
  positional-correction mechanism was needed or added.
- Where one name occurs more than once in a file (property getter/setter pairs, an overload set,
  a repeated macro expansion), each tool's occurrences of that name are sorted by line and paired
  by **rank** (1st with 1st, 2nd with 2nd) — the same instinct the 2-tool system's
  `_align_occurrences_by_line` already used, generalized to however many of the three tools are
  available for a given language.
- **Existence and args are reconciled separately.** A function's existence (does a symbol named X
  exist at roughly this position) and its parameter count are two different questions, scored
  independently — an args disagreement on an existence-agreed function only ever affects that
  language's args metric, never its func recall/precision. Confirmed empirically, not just
  asserted: a Python signature-parsing bug fix moved args agreement from 91.3% to 99.9% while
  existence agreement (97.3%) never moved at all.
- **ctags and tree-sitter are each independently optional per language.** ctags covers a subset of
  tree-sitter's baselined languages, plus 9 more tree-sitter has no grammar for at all (ada,
  agc_assembly, assembly, cobol, embedded_python, m4, scheme, sqlite, yacc). A language with
  neither reads as GitGalaxy-only, not scored against anything.

## The ledger: how a raw discrepancy becomes a validated finding

`docs/self_scan/tri_comparison_ledger.json` is the persistent record — one entry per
**discrepancy shape** (language / symbol type / metric / which tools agreed vs. dissented), not
per individual occurrence. A csharp shape with 271 raw occurrences behind it is very likely one
systematic cause (a real tree-sitter grammar recall gap), not 271 separate findings — see
`tri_comparison_ledger.py`'s own `ENTRY LIFECYCLE` docstring section for the full mechanics.
Every entry starts `status: "unvalidated"`; a human (or an agent following
[`how_to_investigate_a_discrepancy.md`](how_to_investigate_a_discrepancy.md)) reads the source at
a handful of recorded examples, determines what's actually true, and sets `status: "validated"`
plus a free-text `verdict` explaining what was found. Re-running the tool later refreshes
`last_seen_count`/`last_seen_examples` for a validated entry but never reverts its status or
overwrites the verdict — a fix landing that makes a shape stop reproducing sets
`still_reproduces: false` and keeps the historical record rather than deleting it.

A validated verdict can also move the actual score, not just suppress the chart's `*` marker —
see `tri_comparison_ledger.py`'s `VERIFIED ADJUSTMENTS` section for the `credit_tools`/
`debit_tools` mechanism and exactly when each applies (short version, learned the hard way in this
same repo: `credit_tools` only makes sense for a shape where ONE tool's claim was uncorroborated —
crediting a tool that's already in a 2-of-3 agreeing pair double-counts, since that pair already
gets precision credit from the base reconciliation).

## The recall audit: is GitGalaxy missing anything?

A validated shape verdict says what's true about a *pattern* — it does not, on its own, prove
that every occurrence in that pattern's bucket is a tree-sitter/ctags error and not a real
GitGalaxy miss hiding among them (cpp, 2026-08-29: ~164 "misses" in one bucket, ~162 tree-sitter
macro/parse artifacts, 2 genuine GitGalaxy recall gaps the "tree-sitter over-detects" verdict
would have buried). So the `tri-comparison-ledger-sweep` skill's **step 2.6** requires a
separate, occurrence-level pass: every function tree-sitter OR ctags reports that GitGalaxy does
not is individually read and sorted into either a filed GitHub issue (a real recall gap) or a
named tool/audit artifact (macro hallucination, `#if 0` dead code, bodyless declaration,
deliberate scope boundary, naming-convention mismatch, occurrence-alignment fuzz). Run
`python tests/tools/recall_audit.py` (no args = every language) to enumerate them; a language's
step 8 capstone is not done until its list is empty of unassessed entries.

**Standing answer — the only real GitGalaxy function-recall gaps across the whole corpus:**

<!-- RECALL_AUDIT:BEGIN -->
As of the 2026-08-29 full sweep (`recall_audit.py` over all 31 tree-sitter-comparable languages),
the five real recall gaps it found are all fixed and **every tree-sitter-comparable language now
has 100.0% function recall** against the pinned corpus — GitGalaxy ties or beats tree-sitter and
ctags on function detection everywhere.

| Language | Source form GitGalaxy missed | Issue | Fixed |
|---|---|---|---|
| shell | a control-flow keyword (`for`/`if`/…) as a plain unquoted argument word desyncs Mode-D (`echo … limit for $x …` → `t_[Truncated]`) | [#2459](https://github.com/squid-protocol/gitgalaxy/issues/2459) | ✅ command-position guard |
| cpp / c | return type supplied by a SAL / entry-point macro — `__control_entrypoint(x) STDAPI Foo()` | [#2460](https://github.com/squid-protocol/gitgalaxy/issues/2460) | ✅ macro-prefix shield |
| lua | (a) a `local function` not first on its line; (b) `local function lexerror` erased because a `[[`/`[=[` inside a string literal (`t("[=[alo]]")`) triggered the long-bracket shield, collapsing the real string to `""""` → phantom triple-quote swallowing 60+ lines | [#2461](https://github.com/squid-protocol/gitgalaxy/issues/2461) / [#2437](https://github.com/squid-protocol/gitgalaxy/issues/2437) | ✅ `;`-anchored opener + string-context guard on the long-bracket shield |
| dart | multi-line arrow methods, `<T extends State<Widget>>` generic methods, bodyless default constructors (`_Foo();`), a method literally named `extension` | [#2462](https://github.com/squid-protocol/gitgalaxy/issues/2462) | ✅ all 9 occurrences |
| typescript | object-literal method shorthand (`{ return: async () => … }`); `x = () => null` conditional-reassignment; bodyless overload signature with `=>` in its generic bound (`createInstance<Ctor extends new (...) => unknown>`) | [#2464](https://github.com/squid-protocol/gitgalaxy/issues/2464) | ✅ enclosing-container depth fix + `=>`-tolerant generic step-over + value-context body allowance |

Every other `tree-sitter-finds / GitGalaxy-misses` occurrence `recall_audit.py` prints was
individually assessed and is a comparison/audit-tool artifact — `#if 0` dead code (tree-sitter
has no preprocessor), function-like macro invocations (`OPCODE(X) {`), `_FORCE_INLINE_`-mangled
member parses, bodyless `= default` / `= delete`, tree-sitter naming a NeXT-era objc method by
its return type, or occurrence-alignment fuzz on a name defined many times. The accuracy audit
(`tree_sitter_accuracy_audit.py`) was corrected to stop folding those into GitGalaxy's recall
denominator; per-language detail is in each `docs/language_status/<lang>.md` §9.
<!-- RECALL_AUDIT:END -->

Everything else `recall_audit.py` prints is a comparison-tool artifact, catalogued per language
in that language's `docs/language_status/<lang>.md` §9.

## The catalog: confirmed, evidenced differences between the three tools

This is the part `docs/self_scan/README.md` was missing — not a live list of open questions (that's
what the ledger and `tri_comparison_points_of_interest.md` are for), but a durable catalog of
**confirmed mechanisms**, each backed by a real file:line citation, not a guess. Every category
below has already been investigated to the point of a ledger `verdict` or a fixed bug; treat this
section as a summary with pointers, not the full evidence trail — the ledger entries and the
per-file docstrings cited below carry the complete citations.

### Where ctags is wrong

- **Parses inside macro DEFINITION bodies as if they were real, already-expanded code.** A
  `#define`'d macro's body can contain text that looks exactly like a complete function or class
  declarator — ctags tags it as real regardless of whether the macro is ever actually invoked as
  written. Confirmed for cpp (`godot/object.h`'s `GDCLASS`/`_FORCE_INLINE_`-based macros) and
  documented per-language in
  [`ctags_reader.py`](../../tests/tools/ctags_reader.py)'s own module docstring (search `KIND
  MAPS`).
- **Mistags a macro INVOCATION as the function/class itself**, losing the real name that follows.
  Two shapes confirmed: a macro used as a return-type prefix (`IFACEMETHODIMP_(void)
  FancyZones::Run()`, cpp), and a macro used as a dispatch/case label
  (`OPCODE(OPCODE_OPERATOR) { ... }`, cpp — this one fools GitGalaxy and tree-sitter too, a genuine
  shared mistake, not corroboration). The identical class of bug is documented for `c`
  (`RICHCMP_WRAPPER`/`SLOT1` macro calls in cpython) and `m4` (`AC_DEFINE`/`AC_DEFINE_UNQUOTED`
  autoconf helpers).
- **Strips template arguments from a class name.** `HashMapComparatorDefault<Variant>` (as
  GitGalaxy and tree-sitter both read it, straight from source) becomes bare
  `HashMapComparatorDefault` in ctags' own tag — a naming-format difference, not a real existence
  disagreement about whether the class exists.
- **No formal distinction between a scoped and unscoped enum.** ctags' `"g"` (enum) kind tags
  `enum class Foo {}` and plain `enum Foo {}` identically — telling them apart (where a language
  like C++11 actually distinguishes the two) requires reading the tag's own verbatim source line,
  not anything in ctags' own tag data.
- **A macro-permissive kind can produce a placeholder name for an anonymous type**
  (`__anon2570bd640108` for `typedef struct { ... } Foo;`) — bookkeeping ctags needs internally,
  not a real name either GitGalaxy or tree-sitter would ever report.
- **Structural, permanent per-language gaps**, not bugs: no CLASS-ID/INTERFACE-ID-equivalent kind
  for cobol's OOP syntax, no scope/layout-rule awareness in the Haskell parser (misses `where`-
  clause helpers, `instance ... where` methods, `let`-bound names), no kind at all for scheme's
  SRFI-9 `define-record-type`. These are ceiling effects, not fixable bugs — `ctags_reader.py`'s
  `LANGUAGE COVERAGE` section has the current list.

### Where tree-sitter is wrong

- **A node type can cover both a real definition and a bare reference/declaration**, with no way
  to tell them apart except checking the grammar's own `body` field. Confirmed for C/C++
  (`struct_specifier`/`class_specifier` matches both `struct Foo { ... }` and a bare
  `struct Foo *ptr;` reference or `class Foo;` forward declaration) — this was, until fixed, the
  single largest shape in the whole ledger (525 occurrences for `c` alone).
- **Doesn't distinguish a scoped from an unscoped enum either**, for the same structural reason as
  ctags above but checkable a different way (a `class`/`struct` child token on the
  `enum_specifier` node) — fixed in this repo's own walker
  (`tri_comparison_gatherer.py`/`tree_sitter_accuracy_audit.py`'s `_is_cpp_unscoped_enum`).
- **Node-name construction can include tool-specific formatting GitGalaxy and ctags both omit.**
  cpp conversion operators are the confirmed case: tree-sitter's own name-building appends a
  trailing return-type/const suffix (`operator Variant() const`) where GitGalaxy and ctags both
  report the bare form (`operator Variant`) — a real naming-convention difference in
  `tsaa._get_node_name`, not an existence disagreement.
- **Grammar doesn't support every real-world extension.** GNU "labels as values" computed-goto
  syntax (`&&label`) inside a bytecode-interpreter dispatch loop (`godot/gdscript_vm.cpp`'s
  `GDScriptFunction::call`) is confirmed to make tree-sitter-cpp lose the entire enclosing
  function — ctags and GitGalaxy both still find it correctly, since neither needs to fully parse
  the body to recognize the signature.
- **Shared parameter-counting helper undercounts by exactly one for a defaulted parameter**
  (`int p_step = -1`) — confirmed 6/6 sampled cpp cases, ctags and GitGalaxy both counting
  correctly; not yet root-caused to the exact node-type gap
  ([#2014](https://github.com/squid-protocol/gitgalaxy/issues/2014)).
- **Error-recovery on malformed or macro-obscured input can hallucinate a function-shaped node
  from unrelated text** — a bare control-flow keyword (`for`, `if`) or bare `void` reported as a
  function NAME. The exact trigger wasn't fully traced for cpp (would need deeper grammar-level
  investigation), but the same general failure class is already confirmed and documented for other
  languages (javascript's Flow-typed-file misparse, `#1633`).
- **Occurrence pairing, Cython scope loss, synthetic placeholder names** — see
  `tree_sitter_accuracy_audit.py`'s own `SCOPE & LIMITATIONS` section (the 2-tool system's
  authoritative list, still accurate for the 3-tool system too since both share this reader).

### Where GitGalaxy is (or was) wrong

Unlike the two sections above, this list changes as bugs get fixed — check
`docs/language_status/<lang>.md`'s own "known limitations" section (once a language has one) or
search closed issues for the current, language-specific state rather than trusting this list to
stay current. As of this writing, confirmed and fixed for cpp: a `class_start` forward-declaration
false positive (`_CLASS_START_REQUIRES_BODY_ANCHOR` extended from C to cpp with a depth-aware
scanner, since C++ multiple inheritance breaks a naive copy of C's own flat lookahead — see
`_cpp_class_has_body` in `detector.py`), and a `func_start` false positive on a lambda passed as a
constructor argument or initializer-list entry (a bare `[` opening a "parameter list" is never
valid C++ syntax for a real parameter — only a lambda capture-list or, doubled, an attribute —
see the `LAMBDA-ARGUMENT SHIELD` comment on cpp's `func_start` rule). Confirmed and still open for
cpp: a member-initializer-list length cap causing a real recall gap
([#2009](https://github.com/squid-protocol/gitgalaxy/issues/2009)), no support for a
template/generic conversion-operator return type
([#2010](https://github.com/squid-protocol/gitgalaxy/issues/2010)), and args-counting bugs on
out-of-class methods and constructors with initializer-lists
([#2012](https://github.com/squid-protocol/gitgalaxy/issues/2012)).

### Naming/formatting differences that aren't existence disagreements at all

Worth its own bucket since it's a real, recurring pattern, not a one-off: the three tools don't
always agree on the exact STRING for something they all correctly agree exists. Confirmed cases:
ctags reporting a bare, unqualified method name where GitGalaxy/tree-sitter report the fully
`Class::method`-qualified form read straight from an out-of-class definition's own source text
(ctags splits this into a separate `class:`/`namespace:` scope field instead); ctags stripping
template arguments from a class name; tree-sitter appending a trailing return-type/const suffix to
a conversion operator's name. None of these are existence bugs in any tool — they're
name-construction CONVENTION differences the reconciler's name-based matching can be fooled by if
not accounted for (see `ctags_reader.py`'s `_QUALIFY_NAME_WITH_SCOPE` mechanism for how the cpp
case is handled: re-join name+scope from ctags' own tag data, gated on the qualified text actually
appearing in the tag's own verbatim source line).

## What the args data currently shows (2026-08-27)

A whole-corpus probe of the args metric (of the parameter counts GitGalaxy reports on
existence-agreed functions, how many at least one other tool corroborated) found **no open
backlog on GitGalaxy's side**: args agreement is ~100% for essentially every language with a real
second reader (c, cpp, csharp, rust, dart, php, typescript, java, javascript, kotlin, go,
fortran, python, ruby, solidity, tcl, zig, objective-c), and every language that sits below 100%
already has a *validated* ledger verdict, all of which land on "GitGalaxy's count is right":

| language | gg args agreement | validated verdict |
| --- | --- | --- |
| haskell | ~88% | both readings valid — GitGalaxy counts true logical arity from the type signature, tree-sitter counts only the patterns the aligned equation binds. Logged as [Claim 14](../why_gitgalaxy_beats_ast_here.md). |
| perl | ~93% | "GitGalaxy regex splits args appropriately" |
| powershell | ~95% | "GitGalaxy extracts args accurately" |
| matlab | ~96% | "GitGalaxy regex splits args more robustly than tree-sitter on MATLAB edge cases" |
| scala | ~97% | "GitGalaxy counts args accurately" |
| swift | ~99% | "GitGalaxy counts args accurately" |

Every *reproducing* args discrepancy shape in the ledger resolves the same way — a tree-sitter
limitation (Go grouped same-type parameters, Flow union-type parameter-list corruption, the
shared `_get_param_count` helper undercounting a defaulted parameter by one, Fortran truncating a
677-arg signature at 39), one ctags tuple-parameter mis-split in csharp, or a reconciliation
artifact (name-only pairing comparing two different same-named overloads' readings against each
other — see below) — **not** a GitGalaxy gap. The 2026-08-22 dart fix
([#2341](https://github.com/squid-protocol/gitgalaxy/issues/2341)) closed dart's last args shape;
it now reads 100%.

Two limits on how sharp this signal is:

- **Repeated-name pairing (#2359, mitigated).** Where one name has several unrelated definitions
  in a file (`build` across different Dart widgets, `constructor` across TypeScript classes, C#
  method overloads), plain rank pairing (zip the two tools' line-sorted occurrence lists by
  index) silently shifts every pairing after any occurrence one tool missed, comparing tool A's
  overload #2 against tool B's overload #3. Functions now pair by **line proximity** instead
  (`_pair_occurrences_by_line`): a genuinely-missed occurrence is left unpaired rather than
  shifting the rest, and a residual line-spread guard skips the args comparison for any pair too
  far apart to trust as the same function. Total slot count — and therefore existence
  recall/precision — is unchanged by construction. This removed the csharp/javascript/cpp
  spurious args shapes and recovered ~90 previously-mis-paired true args comparisons (all still
  100% agreement). A narrow residual remains: if one tool reports a name several times far from
  where the others place it (ctags mis-tagging a macro body, say), clustering can still split
  what rank merged — rare, and it only moves that tool's own recall, never GitGalaxy's precision.
- **Start-line agreement is not a usable correctness metric as-is.** The same probe measured
  per-tool start-line agreement and found the disagreements are almost all naming-convention
  offsets, not defects: ctags systematically reports the line one past GitGalaxy/tree-sitter in
  c/php/java/typescript, and GitGalaxy anchors at the attribute/decorator/signature line where
  tree-sitter starts at the keyword (Rust proc-macro attributes, decorated TS constructors,
  Haskell type signatures). `line` stays a rank-ordering input only, not a scored metric — see
  `tri_comparison_reconcile.py`'s `MATCHING METHODOLOGY` docstring.

## CI enforcement

This system was skill/human-driven only until it wasn't: any PR touching `detector.py` /
`prism.py` / `language_standards.py` (or this system's own tool files) now runs
`.github/workflows/tri-comparison-audit.yml`, a blocking PR-time check that fails if GitGalaxy's
own **validated** precision (`func_precision`/`class_precision`, read *after*
`apply_verified_adjustments()` has applied any ledger verdict — never a raw, unvalidated
disagreement) regresses against a committed baseline
(`tests/tri_comparison_baseline_<lang>.json`, one file per language, same convention as
`tests/tree_sitter_accuracy_baseline_<lang>.json`). Recall is deliberately not gated — see the
"RECALL AND ARGS-MATCH WERE REMOVED AS RATIOS" section of `tri_comparison_chart.py`'s own module
docstring for why that ratio's cross-tool denominator isn't trustworthy enough to regression-gate
on, the same reason it isn't rendered as a ranked bar on the chart itself.

That PR-time gate only measures — it never requires a contributor to regenerate and commit the
chart/ledger/report themselves. A separate push-to-main companion,
`.github/workflows/tri-comparison-history.yml`, does that automatically after a relevant change
lands on `main`: re-render `tri_comparison_chart.svg`, refresh `tri_comparison_ledger.json`
(`last_seen_count`/`last_seen_examples`/`still_reproduces` only — never a validated entry's
`status`/`verdict`), and regenerate `tri_comparison_points_of_interest.md`, opening an auto-merged
PR only when something actually changed. This is the same split
`tree-sitter-accuracy-audit.yml`/`tree-sitter-accuracy-history.yml` already use for the 2-tool
system, adopted here rather than requiring every PR author to run a full corpus scan + a real
`ctags` locally just to unblock their own merge.

Both workflows hard-fail if `ctags --version` doesn't print `Universal Ctags` before running
anything else — see PR #2111 above; a CI gate that could suffer the same silent degradation would
report false confidence instead of an honest failure. `tests/tri_comparison_baseline_<lang>.json`
baselines are populated incrementally, per language, via `tri_comparison_chart.py --regenerate
--languages <lang>` — a language with no committed baseline yet is skipped by `--all --ci`, not
failed.

## Files

- **`tri_comparison_ledger.json`** — the persistent, hand-editable record described above.
  Committed, reviewed like any other source file.
- **`tri_comparison_chart.svg`** — small-multiples bar chart, same visual language as the 2-tool
  system's chart: one row per language, five metric panels (func found/precision, class
  found/precision, args found), a bar per available tool. A `*` marks an unvalidated disagreement
  still open for that (language, metric); `**` marks a manually-verified single-tool language (no
  second comparison tool exists at all — see the fallback procedure in the
  `tri-comparison-ledger-sweep` skill). A colored badge marks the winning tool for a ranked panel;
  a rate-only tie is broken by each tied party's absolute count of validated-correct occurrences,
  not the raw claim count (`_winner_or_tie()` in `tri_comparison_chart.py`). Regenerate with
  `python tests/tools/tri_comparison_chart.py --all --write` — never with a partial `--languages`
  list, which overwrites the WHOLE file with only those languages.
- **`tri_comparison_points_of_interest.md`** — a rendered, ranked-by-signal-strength Markdown
  summary of the ledger, regenerated with `python tests/tools/tri_comparison_report.py --write`.
  For a quick "what's the biggest open question right now" read; the ledger JSON is still the
  primary source.
- **`docs/self_scan/manual_verification.json`** — the parallel papertrail for a language with NO
  second comparison tool at all (abap, dockerfile, jcl, livecode, yaml) — a ledger entry requires a
  discrepancy shape, which requires at least one other tool to disagree with; these languages have
  nothing to disagree with GitGalaxy at all, so they get a hand-written, hand-reviewed manual
  verification record instead, keyed the same way.

## Reproducing or updating this locally

**Bumping the pinned corpus tag?** Use the full ordered checklist in
[`BUMPING_THE_CRUCIBLE_PIN.md`](BUMPING_THE_CRUCIBLE_PIN.md) instead of just
the commands below — this system is only one of five things that need
regenerating together, in a specific order, with prerequisites that have
caused real CI failures when skipped.

```bash
# from the gitgalaxy repo root -- same corpus checkout the 2-tool system uses.
# check tests/_crucible_pin.py or the LANGUAGE_CRUCIBLE_REF repo variable first;
# the tag below drifts out of date as that pin gets bumped.
git clone --branch v1.1.0 --depth 1 https://github.com/squid-protocol/language-crucible.git ../language-crucible
pip install tree-sitter-language-pack

# universal-ctags must be on PATH and be the REAL thing -- Ubuntu's `arduino-ctags` shadows the
# `ctags` binary name but isn't universal-ctags at all; `ctags --version` must print
# "Universal Ctags", not error or print an Arduino banner
ctags --version

python tests/tools/tri_comparison_chart.py --languages cpp        # spot-check one language, no writes
python tests/tools/tri_comparison_chart.py --all --write          # full regen, all languages
python tests/tools/tri_comparison_report.py --write               # regen the points-of-interest doc
```

A missing `ctags` binary degrades every language gracefully to a 2-tool (GitGalaxy + tree-sitter)
comparison rather than erroring — the same shape a language with no tree-sitter grammar at all
already degrades to.

## Related reading

- [`docs/self_scan/README.md`](README.md) — the 2-tool (GitGalaxy vs. tree-sitter) system this one
  extends; read that one first for the baseline methodology this system inherits (recall vs.
  precision definitions, the `--history`/`--regenerate` workflow for that system specifically).
- [`docs/self_scan/how_to_investigate_a_discrepancy.md`](how_to_investigate_a_discrepancy.md) —
  the actual step-by-step process for turning an unvalidated ledger shape into a validated verdict.
- [`docs/why_gitgalaxy_beats_ast_here.md`](../why_gitgalaxy_beats_ast_here.md) — the standing,
  evidence-gated record of confirmed cases where GitGalaxy is more accurate than an AST-based
  reader, not just different.
- [`docs/language_status/README.md`](../language_status/README.md) — per-language coverage docs;
  some carry their own tri-comparison capstone section (search for "Tri-comparison findings")
  built from this same ledger, synthesized for that one language.
- This file is the canonical regen/operational doc for **both** coding agents working in this
  repo — `CLAUDE.md`'s "Comparative-correctness claims require verification" section and
  `ANTIGRAVITY.md`'s "Tri-Comparison Chart & Ledger" section both point here rather than
  duplicating the procedure. A regen skipping the "Reproducing or updating this locally" steps
  above (real `ctags` on PATH, `--all --write` only) caused a real incident, PR #2111
  (2026-08-22) — every language silently lost its ctags bars/badges, including cobol's already-
  validated full-precision badge, with no error at any point in the run. Check
  `ctags --version` before you trust any regen's output.
