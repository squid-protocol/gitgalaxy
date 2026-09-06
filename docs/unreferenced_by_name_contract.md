# The `unreferenced_by_name` census contract

> Filed as [#2806](https://github.com/squid-protocol/gitgalaxy/issues/2806). Same shape as
> `docs/api_rule_contract.md` (#2730), `docs/args_rule_contract.md` (#2773) and
> `docs/state_mutation_rule_contract.md` (#2765), with one difference worth stating up front:
> this signal is not a rule. No language registry produces it. It is computed once per file in
> `detector.py`'s splice, from the extracted function list and the code stream, so its contract
> is about a **census**, not about a regex. `gitgalaxy/standards/how_to_add_a_language.md`
> carries the one-line form (engine rule 19); this file carries the reasoning, the audit of all
> 46 corpus languages, and the rename.

## The contract

> **One hit is one extracted callable unit whose name occurs nowhere in the file outside its own
> definition.**

Six corollaries, each pinned by a test in
`tests/core_engine/test_unreferenced_by_name_contract_2806.py`:

1. **One unit is at most one hit.** The census counts callable units, not name occurrences. A
   function named ten more times leaves the census; it does not leave it nine times.
2. **A declaration is not a reference.** Where a language writes the name a second time as part
   of *declaring* the unit, that occurrence does not clear the flag: Ada's `end Probe_Globals;`,
   LiveCode's closing handler name, a K&R shell declaration that falls outside the slicer's own
   span (discounted implicitly when the span contains no occurrence, #2727), and any form a
   registry declares through `_visibility_export` — `export -f foo`, `namespace export foo`,
   `Export-ModuleMember -Function foo`, `module_function :foo`, `global foo` (#2774).
3. **A reference is not an invocation, and this census cannot tell them apart.** Any other
   occurrence of the name clears the flag — a call, a mention in a comment the prism left in the
   stream, a name inside a string literal (nothing shields string literals for any signal,
   #2535), an unrelated identifier that happens to match. That is a real limit, and it is why
   the signal is now named for what it measures. It says *nothing else in this file names this
   function*; it does not say *this function is dead*.
4. **Where the language has no invoke-by-name form, the census is not computed.** A registry
   declares `"invocation_model": "positional"` and the count is absent (0), not maximal. The
   default is `by_name` and needs no declaration. See "The positional family" below for the bar
   this has to clear, which is higher than it looks.
5. **The census sees one file.** Nothing about the repository's call graph enters here. The
   layer that knows whether anything imports this file is `galaxyscope.py`'s Contextual Baseline
   Fix, which converts an imported file's uncalled functions into `api` (crediting only the ones
   the language's own `api` rule did not already count, #2731). An exported-but-uncalled library
   function is genuinely unreferenced *in its own file*, and saying so is the input that layer
   needs.
6. **A synthetic slicer bucket is not a callable unit.** Mode D's `__global_context__`, Mode E's
   `<KEYWORD>_Statement`, and the igniter-keyword buckets a language's own `func_start` names
   after a keyword (dockerfile `RUN`, css `keyframes`, html `script`) are excluded: a keyword
   cannot be unreferenced, and counting it measures the slicer's bucketing rather than the code
   (#2547, #2728).

`kind` is a **census** over the extracted function population and its `unit` is **functions** —
not hits, and not lines. A formula that adds it to a rule's hit count is adding unlike things;
Phase 4's commensurability audit reads it here.

## The rename (#2806 shape (c))

| was | is |
| --- | --- |
| `equations["orphaned_logic"]` | `equations["unreferenced_by_name"]` |
| `file_data.state_slop_orphans` | `file_data.state_unreferenced` |
| `file_data.raw_state_slop_orphans` | `file_data.raw_state_unreferenced` |

Both old names asserted the count was dead weight — "orphaned", "slop" — which is a claim
corollary 3 says the measurement cannot make. `record_keeper.py` renames the columns of a
pre-#2806 database in place (`ALTER TABLE ... RENAME COLUMN`, guarded the same way the `doc_loc`
and `raw_arch_api` heals are): the recorded values were never wrong, only their label was, so
there is nothing to re-scan.

The consumers are unchanged by the rename and worth naming, because they are what makes the
reading matter:

- **`risk_tech_debt`** (`signal_processor.py`) weights each unit at 2.0 in `slop_stress`, and
  multiplies the whole stress by 1.5 when a file also carries acknowledged debt. jcl scored 48.8
  against a 38.7 corpus median almost entirely on this.
- **The orphan → api conversion** (`galaxyscope.py`) turns an imported file's census into public
  surface, which `risk_api_exposure` and `risk_documentation` then read.

## The positional family

A language joins by declaring the top-level `"invocation_model": "positional"`, and the bar is: **the
language has no syntax at all that reaches the units its own `func_start` extracts by naming
them.** Not "the corpus does not call them". Not "invocation is unusual". No form.

Exactly one corpus language clears it today:

**jcl.** A job's EXEC steps run in the order they are written, top to bottom, on every
submission. Nothing in JCL references a step to make it run. (The unit that *can* be named is
the PROC — `//DISPATCH EXEC ROSPROC` — which the `api` rule counts and the slicer does not
extract as a function.) Before the declaration, 334 of 376 crucible steps (89%) read as
unreferenced, and the 42 that cleared did so by accident rather than by being invoked: a step
named `CREATE` beside inline SQL in a `SYSIN DD *` block, `COBOL` beside the same word inside a
DSN, `CRTABS` repeated seven times in one job. Both the 89% and the 11% were noise, so
suppressing the census removes a false reading in both directions, not just the loud one.

**The four languages that did not clear it.** #2806 proposed the family as abap, jcl, m4,
makefile and objective-c, all sitting at 3.25 per file in keyword-rosetta — 13 of 13 probe
functions unreferenced, against a 2.50 median. The premise did not survive measurement. Each of
those four has an ordinary invoke-by-name form, and the crucible shows the census seeing it
(real-world ABAP reads 8 unreferenced subroutines in 124, a 6% rate, entirely through
`PERFORM`). What they had in common was the *corpus*: every median language's `main` dispatches
its three probes (`python`'s `entry()` calls `probe_branch`, `probe_io`, `probe_risk`), and in
these four `main` declared a `dispatch`/`entry` unit that called nothing. Planting the
language's own idiom — `PERFORM probe_branch CHANGING cv_argv.`, `[self probeBranch:argv];`,
bare macro expansion inside `probe_dispatch`, a make prerequisite list — moves all four to the
median with no engine change (keyword-rosetta PR; the cells are in the table below). Two of
those plants moved a gated neighbour and both were screened before landing: abap's
`args` cell 4 → 7, because abap's `args` rule counts the call site's `CHANGING` as a declared
parameter (a stated-contract violation, filed as #2824 and ledgered), and m4's `args` 6 → 8,
because m4 parameters ARE use sites and a forwarding macro genuinely has three
(`m4-parameters-are-use-sites`, already ledgered as intended morphology).

That is the general warning for the next language proposed for this family: **"the census reads
100%" and "the language cannot be asked" are different claims, and the first is much easier to
produce than the second.** Check the crucible before the control corpus — real code either
contains the invocation form or it does not.

## The audit — all 46 corpus languages

Per-file census over `keyword-rosetta/data`, engine `fix/2806-orphan-invocation-model` against
main `87cfc933`, corpus main `5cf94e7`. `before` is main + corpus main; `after` is this branch
plus the corpus PR's plants. The corpus median is 2.50 in both columns (13 probe functions per
language over 4 files, 3 of them dispatched from `main`, and the a/b/c probes are called only
across a file boundary the census deliberately cannot see — corollary 5).

| language | before | after | why it moved |
| --- | --- | --- | --- |
| `abap` | 3.25 | 2.50 | corpus: `FORM dispatch` now `PERFORM`s its three probes |
| `jcl` | 3.25 | 0.00 | engine: `_invocation_model: "positional"` — not computed |
| `m4` | 3.25 | 2.50 | corpus: `probe_dispatch` now expands `probe_branch`/`probe_io`/`probe_risk` |
| `makefile` | 3.25 | 2.75 | corpus: `probe_dispatch` now lists all three as prerequisites. 2.75 not 2.50 because `c.mk` carries a 14th unit (`clean`) no other language has |
| `objective-c` | 3.25 | 2.50 | corpus: `entry:` now sends `probeBranch:`/`probeIo:`/`probeRisk:` |
| `ada` `apex` `assembly` `c` `cpp` `csharp` `dart` `embedded_python` `fortran` `go` `groovy` `java` `javascript` `kotlin` `livecode` `lua` `matlab` `perl` `php` `powershell` `python` `ruby` `rust` `scala` `shell` `solidity` `swift` `tcl` `typescript` `zig` | 2.50 | 2.50 | on the median, unchanged |
| `cobol` | 2.75 | 2.75 | in band, and the plant was measured and then deliberately NOT made: `DISPATCH-PARA` calls nothing, and planting the canonical `PERFORM PROBE-IO.`/`PERFORM PROBE-RISK.` reads 2.25 (below the median, because `PROBE-RISK`'s `ALTER DISPATCH-PARA TO PROCEED TO PROBE-BRANCH` names the dispatch paragraph as well) at the cost of moving the **gated `branch` cell 3 → 5** — cobol's `branch` rule counts a bare out-of-line `PERFORM`, which is a call, not a branch (10% of its 21,549 crucible branch hits; recorded on #2822). Free to plant once that lands |
| `agc_assembly` | 2.75 | 2.75 | in band. Same shape as the four plant gaps and left alone deliberately: `DISPATCH TC PROBEBR` and `PROBEBR`'s branches reach `PROBEIO`, so only `PROBERISK` is unreached, and planting a `TC PROBERISK` would add a control-flow hit to a gated cell to fix a cell that is already in band |
| `yacc` | 3.00 | 3.00 | in band, same shape: `dispatch : probe_branch ;` names one of the three nonterminals |
| `css` `dockerfile` `html` `markdown` `sqlite` `yaml` | 0.00 | 0.00 | no callable units to census — either nothing is extracted (html, markdown) or every extracted unit is a synthetic bucket (corollary 6). This is the *undefined* family of #2549, not this contract's |
| `haskell` `scheme` | 0.25 | 0.25 | **open defect, filed as #2823.** The opposite sign: a Haskell module export list and type signature, and a Scheme `(export name)` with no `_visibility_export` declared, are declarations that corollary 2 says must not clear the flag, and they do. Scheme also carries the same plant gap as the four above, hidden behind it |

### What the audit found

1. **The 3.25 family was two different things wearing one number**, and only measurement
   separated them: one language that cannot answer the question, and four corpus files that
   never asked it. `tools/language_deviations.py` reports the cell; it cannot report which.
2. **The corpus's "identical planted intent in every language" premise is a claim to re-check,
   not a given.** It was false for five languages here (the four above plus scheme) and remains
   knowingly loose for two more (agc_assembly, yacc), which are recorded rather than fixed
   because both cells are in band and both plants would move a gated neighbour.
3. **Both tails of this metric are declaration-vs-reference errors.** #2727 fixed the
   whole-file token count, #2774 fixed export statements for five languages, this issue fixes
   the no-invocation case, and #2823 is the same shape once more for the two languages whose
   declaration syntax names a function twice before anything uses it.

## What the golden masters moved

Both fixtures were re-blessed (`crucible_check.py --update --yes`, scoped with
`tests/tools/bless_scope.py` and a full uncapped diff):

- **5,636 key renames**, one pair per parsed file: section 7's label `Orphaned Logic` becomes
  `Unreferenced By Name`. No value attached to them changed.
- **564 value differences, every one of them jcl.** 150 `Tech Debt Exposure` (the census was
  weighted 2.0 per unit and is now absent — `cics-java-jcics-samples` reads 0.0 where it read
  73.11), 34 `API Exposure` and 34 `Documentation Exposure` (the orphan → api conversion has
  nothing to convert), 33 `Structural Mass`, and 267 topological `X`/`Y`/`Z` coordinates, which
  re-solve corpus-wide whenever any node's mass changes. The three global aggregates that moved
  are the same change summed: `avg_tech_debt` 31.243 → 27.332, `avg_documentation` 7.942 →
  7.753, jcl's ecosystem impact 916.94 → 877.94.

No other language moved in either fixture, which is corollary 4's "unchanged by construction"
stated as a measurement.

## Notes for the next session

- The engine half is one registry key and one conditional. Nearly all of #2806's cost was
  measurement — 46 languages × two corpora — and `orphan_probe.py`-shaped work (run
  `splice()` per corpus file, read `usage_status` per function) is the tool that pays for
  itself; `tests/tools/rule_probe.py` cannot do it, because this signal is not a rule.
- **A string value inside `rules` is not a string by the time the detector reads it.**
  `language_lens.py`'s `_calibrate_lookup_maps` compiles every `str` rule value into a regex — a
  defensive guard for definitions loaded from external JSON — so the first version of this
  change, which put `_invocation_model: "positional"` in `rules` beside `_scope_filters`, reached
  `detector.py` as `re.compile("positional")` and compared unequal to `"positional"`. Every unit
  test passed (they build the extractor straight from `LANGUAGE_DEFINITIONS`, which the lens has
  not touched) and only a real `galaxyscope` run showed it: jcl still recorded a full census, and
  the first golden-master bless was silently wrong. `invocation_model` is a top-level language
  property now, beside `lexical_family`. A future non-pattern helper belongs there too, or it
  needs an exclusion in that pre-compiler.
- `duplicate_logic` (`state_slop_duplicates`) is the census's sibling and still carries the
  "slop" vocabulary. It was left alone deliberately: a duplicate really is what its name says
  (same name *and* materially the same body, #1498), so the name makes a claim the measurement
  supports.
- The next family in the roadmap order is #2822 (`branch`). #2823 is this one's own successor
  and needs a corpus plant in the same wave, so it is cheapest run as a pair.
