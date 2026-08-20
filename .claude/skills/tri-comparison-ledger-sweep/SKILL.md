---
name: tri-comparison-ledger-sweep
description: Run a Claude-mediated, Gemini-investigated sweep of GitGalaxy's tri-comparison ledger (docs/self_scan/tri_comparison_ledger.json) -- pick unvalidated discrepancy shapes (GitGalaxy vs. tree-sitter vs. ctags disagreements with no privileged ground truth), dispatch each to a read-only Gemini/agy subagent to read real corpus source and determine what's actually true, review and apply the returned verdict to the ledger, file a GitHub issue for any confirmed engine defect found along the way, and keep a pool of dispatches active until the backlog thins out. Use when the user asks to "investigate the ledger", "dispatch gemini for tri-comparison", "run a ledger sweep", "verify tri-comparison discrepancies", "earn some badges back", or similar recurring tri_comparison_ledger.json-driven work. Also covers validating a language with NO comparison tool at all (abap, dockerfile, jcl, livecode, yaml -- neither tree-sitter nor ctags) via the dedicated manual-verification fallback section, since that's still this skill's territory even though the ledger itself has nothing to dispatch. Not for implementing an already-diagnosed engine fix (that's a normal PR, or tree-sitter-accuracy-sweep if it's tree-sitter-accuracy-audit.py-shaped instead), and not for a single hand-picked shape with no candidate-selection step (just dispatch directly).
---

Source of truth for the underlying tool is `tests/tools/tri_comparison_reconcile.py`'s and
`tests/tools/tri_comparison_ledger.py`'s own module docstrings, and
`docs/self_scan/how_to_investigate_a_discrepancy.md` (the human-facing procedure this skill
automates the dispatch side of -- read it before starting, its lifecycle/verdict-format rules are
not repeated in full here). This skill is the operational playbook layered on top: how to pick
targets, brief a read-only Gemini dispatch, review what comes back, and land the result as a
committed, auditable ledger entry.

**Candidate selection and verdict review stay in the main conversation.** Only the investigation
itself -- reading corpus source at flagged locations and forming a hypothesis -- goes to a
dispatched agent. Applying the result to the ledger, deciding whether a verdict is well-evidenced
enough to mark `validated`, and filing issues for confirmed engine defects are judgment calls that
stay here, same principle as `tree-sitter-accuracy-sweep`'s "root-cause in the main session."

## Why this is a lighter pipeline than tree-sitter-accuracy-sweep

That skill dispatches Gemini to *write a code fix* in an isolated worktree, so it needs a prebuilt
venv, `agy` permission grants per worktree, and one PR per language. This skill dispatches Gemini
to *read* real source and existing tool output and report back a verdict -- no code changes, no
worktree, no venv, no permission-grant step. Every dispatch operates read-only against the main
checkout directly. The one thing this pipeline has that the other doesn't: **every verdict lands
in the SAME shared file** (`docs/self_scan/tri_comparison_ledger.json`), so parallel dispatches
must never write to it themselves -- they return text, the main session applies it serially. See
step 4.

## Before starting: confirm this language actually has a comparison tool

This whole pipeline assumes at least one other tool (tree-sitter or ctags) has a reading to
disagree with GitGalaxy about -- that's what populates a ledger shape in the first place. Five
languages have neither: **abap, dockerfile, jcl, livecode, yaml** (`ctags_reader.py`'s own
LANGUAGE COVERAGE docstring section names this exact set, confirmed current 2026-08-19). For these,
the step 1 query filtered to that language will always come back empty -- that's expected, not a
sign the sweep hasn't been run yet, and it's not worth spending a dispatch looking for shapes that
structurally can't exist.

For a language in this set, skip steps 1-7 entirely (there's no ledger shape to pick, no Gemini
dispatch to brief on a "shape", no `credit_tools`/`debit_tools` decision -- none of that machinery
has anything to act on) and do a **manual verification** instead:

1. Pick a real, non-trivial corpus for the language under `language-crucible/data/<lang>/` --
   confirmed workable on abapGit's 7 files / ~4000 lines (2026-08-19). Reserve this approach for a
   scoped corpus (single-digit files, low thousands of lines); it does not parallelize the way a
   Gemini dispatch of a pre-identified shape does, because there's no shape to hand off, only "go
   read the file."
2. Run GitGalaxy's actual regex rules against every file's raw text and record every match
   (func_start, class_start, or whichever signature you're checking) with its line number and
   captured text -- this is your first data point, but **it is NOT the same claim as "GitGalaxy
   correctly extracts this," and step 2b below is not optional:**
   ```python
   from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS
   rules = LANGUAGE_DEFINITIONS["<lang>"]["rules"]
   text = open(path, encoding="utf-8", errors="replace").read()
   for m in rules["func_start"].finditer(text):
       line_no = text[: m.start()].count("\n") + 1
       ...
   ```
2b. **Also run the real pipeline and check its actual DB output -- do not skip this step.** The raw
    regex in step 2 runs against unprocessed file text; the production pipeline runs the identical
    regex against text that has already gone through `prism.py`'s comment/code splitter and
    `detector.py`'s segment-routing/integration-mode logic first, and either stage can silently
    corrupt or drop real matches before the regex ever sees them (confirmed real, not hypothetical,
    2026-08-19: the abap pass's first draft skipped this step, reported "100% precision, zero
    defects" from step 2 alone, and was wrong -- see below). Run:
    ```bash
    galaxyscope language-crucible/data/<lang> --config .galaxyscope.yaml --db-only --output <tmp>/scan.json
    ```
    then query the resulting sqlite DB directly -- both the raw signal count (`file_data.
    struct_func_start`/`struct_class_start`/etc., computed independently of body-slicing) and the
    NAMED list that actually reaches consumers (`file_data.function_count`/`class_count`, backed by
    `function_data`/`class_data`). If the raw regex count (step 2) and the DB's raw signal count
    disagree, `prism.py` is corrupting the text before extraction. If the raw signal count and the
    named-list count disagree, `detector.py`'s segment-routing/integration-mode logic (not the
    regex) is dropping real matches during body-slicing -- an entirely different bug class from a
    regex miss, and the two need separate root-causing and separate issues.
3. Independently establish ground truth by reading the actual source, or a second, blunt,
   independent grep as a cross-check against the regex's own captures (this session's abap check:
   `grep -nE "^\s*METHOD\s+[a-zA-Z]"` per file, diffed against the regex output -- matched exactly,
   124/124). This is where "no tool to compare it to" becomes real, tedious reading rather than a
   one-line query. Also verify the language actually HAS the construct you're checking before
   treating a zero as expected -- ABAP has real classes (every `.clas.abap` file has a
   `CLASS ... DEFINITION`/`CLASS ... IMPLEMENTATION` pair) and a real `args` construct
   (`IMPORTING`/`EXPORTING`/etc.), so a flat 0 for either is a signal to investigate, not an
   assumed "this language doesn't have that." Not every language has every construct though (bash
   has no formal parameter list at all) -- check the language's own syntax, don't assume either way.
4. Compare: false positives (matched something that isn't real) and false negatives (missed
   something real) both need root-causing the same way a ledger verdict does -- file a GitHub issue
   for a confirmed defect, or note it's a genuine, already-expected engine limitation (e.g. a
   syntax branch the sampled corpus never exercises isn't a proven gap, just untested by this
   corpus -- say so rather than implying it was checked). A false negative found only at the step-2b
   pipeline level (not visible in the raw regex) still gets a real GitHub issue with an isolated
   repro -- don't undersell it just because "the regex itself was fine."
5. Before concluding something LOOKS like a bug, check whether it's actually consistent with an
   existing engine-wide convention established for a DIFFERENT language first -- this is the step
   most likely to get skipped because a single-language read has nothing to cross-reference. This
   genuinely resolved one apparent abap issue (a `class_start` double-count that turned out to match
   objective-c's own intentional `@interface`/`@implementation` convention) -- but don't let a
   correct application of this step earn unearned trust in the rest of the pipeline; it answers one
   specific question ("is this pattern intentional elsewhere too"), not "is everything else fine."
6. There is no ledger entry to write (no shape key exists for a single-tool language) and no
   `credit_tools`/`debit_tools` mechanism applies -- the papertrail is just the language_status doc
   (below) plus any GitHub issues / `why_gitgalaxy_beats_ast_here.md` entries from step 4, same
   three buckets as step 4.3 above, decided by hand instead of via a reviewed dispatch.
7. **Once a signature is genuinely verified (not just checked once -- re-checked per step 2b/5's
   discipline, ideally after any bugs found along the way are actually fixed), feed the real numbers
   into `docs/self_scan/manual_verification.json` and regenerate the chart** so the work shows up
   where a reader actually looks, not just in a doc nobody opens. This is a SEPARATE artifact from
   the ledger (`docs/self_scan/tri_comparison_ledger.json`) -- gg-only languages never get ledger
   entries at all (no second tool means no discrepancy shape to log), so this file is their entire
   parallel papertrail, keyed `{"languages": {"<lang>": {"function": {...}, "class": {...},
   "args": {...}}}}`. Each entry needs `total`, `verified`, `verified_at`, `verified_by`, and a
   `note` describing HOW it was checked (the actual method -- direct source read, an independent
   grep, hand-checking N functions across M files -- not just "verified", which isn't evidence).
   Never machine-generated or auto-updated by a gather run -- hand-write and hand-review it exactly
   like the ledger.
     - **The chart shows `verified/total**`** instead of the honest-but-uninformative `0/N` a
       1-tool language's precision panel would otherwise show. `**` is deliberately distinct from
       `*` (ledger_mod's "unvalidated cross-tool disagreement") -- a different evidentiary category
       (single-source manual/LLM review, not multi-tool corroboration), never blurred together in
       the chart or its legend.
     - **Staleness guard is mandatory, and its anchor is DIFFERENT per panel** -- a manual record
       must stop applying the instant the engine's live count no longer matches what was verified,
       rather than silently keep claiming a verification that's gone stale. Func/Class Found use
       `matched_consensus` (a real per-tool raw count even for 1 tool); Func/Class Precision use
       `total_slots` (ditto); but **Args Found's own `total_slots` is structurally always 0 for a
       1-tool language** (`reconcile_symbols` only increments it when 2+ tools are comparable at a
       slot -- there's no per-tool raw args count anywhere in `MetricScore` at all), so it needed
       its OWN live anchor (`LanguageChartData.gg_args_found`, populated straight from
       `Occurrence.args` in `run_pipeline`, independent of any cross-tool comparison machinery) --
       don't assume every panel's staleness check can reuse the same field just because two of them
       happen to.
     - **A fully-verified 1-tool language can now earn a real badge**, not just the `**` label --
       `_manual_verification_winner()` (a fallback used only when `_winner`/`_winner_or_tie` found
       no real 2+-tool comparison at all) awards GitGalaxy's own badge when `verified == total`
       EXACTLY, never for a partial verification (some slots checked, some not) -- partial credit
       earns the `**` label's honesty but not a badge's full confidence claim. This exists on
       purpose so GitGalaxy going after more tree-sitter/ctags-blind "frontier" languages doesn't
       mean permanent badge-lessness for them -- a real, rigorous manual verification earns the
       same "we know who's actually right" claim a cross-tool win earns, just via a different,
       equally rigorous method, not a lesser one.
     - Regenerate with the normal `--all --write` (step 6 below, same "never a partial
       `--languages` list" rule) and confirm the diff is scoped to the language you just verified
       plus expected ripple, same rigor as any other chart regeneration.

Write the result up the same way step 8 does for a cleared ledger backlog -- a manual-verification
section in `docs/language_status/<lang>.md` (not the tri-comparison template that assumes a second
tool exists to compare against), following the same split: sections 1-8 via the `language-status`
skill (dispatched separately, stopped before its own final section), this section written by hand
in parallel. **Real result of the full abap pass (2026-08-19/20), after step 2b/5's discipline
caught what a single pass would have missed:** SEVEN confirmed engine defects, not zero -- found in
three waves, each surfaced by re-verifying the previous fix rather than trusting it:
- Wave 1 (raw pipeline vs. regex-in-isolation): `prism.py`'s positional-comment stripper reused
  Fortran/COBOL's column-1 anchor set for ABAP, erasing every flush-left `CLASS ...
  DEFINITION`/`IMPLEMENTATION` line as a bogus comment before `class_start` ever ran
  ([#1898](https://github.com/squid-protocol/gitgalaxy/issues/1898)); ABAP had no
  `ScopeParsingRegistry` entry in `detector.py`, silently falling through to brace-based function
  slicing despite having no braces, dropping ~87% of real named functions
  ([#1899](https://github.com/squid-protocol/gitgalaxy/issues/1899)).
- Wave 2 (regenerating the chart after wave 1 merged, then verifying THAT fix): ABAP was missing
  from `_CLASS_START_NAMED_EXTRACTION_LANGS`, so the named class list stayed empty even after
  #1898's fix restored the raw signal
  ([#1904](https://github.com/squid-protocol/gitgalaxy/issues/1904)); the class-boundary resolver's
  brace search mistook ABAP's own string-template syntax (`|text { expr }|`) for a real body
  opener, truncating class scope and breaking method-to-class linkage
  ([#1907](https://github.com/squid-protocol/gitgalaxy/issues/1907)).
- Wave 3 (going back to close out an "open question, not yet root-caused" note instead of leaving
  it): the SAME `prism.py` stripper as #1898, a different unqualified character (`!`, ABAP's
  parameter-name escape prefix, mistaken for Fortran's inline-comment marker)
  ([#1911](https://github.com/squid-protocol/gitgalaxy/issues/1911)); the `args` regex itself had
  two independent correctness bugs (the `!` prefix broke matching entirely; `VALUE(...)` mis-
  captured the literal word `TYPE` as a second parameter)
  ([#1917](https://github.com/squid-protocol/gitgalaxy/issues/1917)); and even with the regex
  fixed, the per-function args COUNT searched the wrong section of the file (the sliced
  IMPLEMENTATION body instead of the DEFINITION section's real declaration) with a derivation
  mechanism that structurally couldn't produce a count from this regex's per-clause-existence
  shape at all ([#1918](https://github.com/squid-protocol/gitgalaxy/issues/1918)).

The raw `func_start` regex itself really was 100% correct in isolation from the very first pass
(124/124) -- that part was never wrong, it was just an incomplete claim mistaken for a complete
one. Every other signature needed at least one more layer of "fix it, then re-verify the fix
itself" before the chart could honestly show `**`/a badge.

## 0. Housekeeping before starting a new sweep

- `git fetch origin main && git checkout main && git pull --ff-only` (or rebase/merge an existing
  in-progress sweep branch onto it) -- work from a current base. Expect merge conflicts in
  `tri_comparison_chart.svg`/`tri_comparison_ledger.json` if another PR touched them since your
  branch forked (these are machine-generated, squash-merges make this common) -- resolve by taking
  your branch's version (`git checkout --ours -- docs/self_scan/tri_comparison_*`) then
  regenerating fresh (step 6), never by hand-merging the JSON/SVG.
- Confirm a real `universal-ctags` is on PATH, not Ubuntu's `arduino-ctags` shim (`ctags --version`
  must print "Universal Ctags", not error or print an Arduino banner). If missing and there's no
  root/sudo available, build one locally without it:
  ```bash
  mkdir -p /tmp/gitgalaxy-scratch/ctags-local && cd /tmp/gitgalaxy-scratch/ctags-local
  apt-get download universal-ctags && dpkg -x universal-ctags*.deb extracted/
  mkdir -p bin && ln -sf "$PWD/extracted/usr/bin/ctags-universal" bin/ctags
  export PATH="/tmp/gitgalaxy-scratch/ctags-local/bin:$PATH"
  ```
  Confirmed working this way with no root access (2026-08-19). Without it, every language with
  ctags coverage silently degrades to a 2-tool comparison and `tri_comparison_chart.py --all
  --write` marks every ctags-side entry `still_reproduces: False` -- not a real fix, just an
  environment gap that looks like one.
- Confirm `tree_sitter_language_pack` is importable in the venv you'll regenerate with (`python3
  -c "import tree_sitter_language_pack"`) -- `tri_comparison_gatherer.py` hard-requires it.

## 1. Pick candidates from the ledger, not by memory of a past sweep

```python
import json
d = json.load(open("docs/self_scan/tri_comparison_ledger.json"))["entries"]
open_qs = [
    (k, e) for k, e in d.items()
    if e["still_reproduces"] and e["status"] != "validated"
]
open_qs.sort(key=lambda kv: -kv[1]["last_seen_count"])
```
Prioritize within that sorted list:
1. Shapes where a tool is ALONE on one side (`agree[gitgalaxy]_vs[...]` or a 2-vs-1 with a small
   agreeing set) over big multi-way splits -- these are the ones actually gating a chart badge
   (see `ledger_mod.has_open_question`'s docstring) and tend to have one clean, checkable cause.
2. Higher `last_seen_count` first within a tier -- a bigger number behind one shape is worth more
   than a small one, and this repo's own precedent (`tree-sitter-accuracy-sweep`, csharp's
   271-occurrence shape) confirms a big count is usually ONE systematic cause, not many.
3. Skip a shape whose `last_seen_examples` are already screaming an obvious, already-documented
   answer (e.g. a language where `ctags_reader.py`'s own module docstring already explains the gap
   -- like haskell's class-kind and lexical-scope notes from this session) -- resolve those
   directly yourself, don't spend a dispatch on a question already answered in the codebase.

You do not need to investigate the whole queue up front -- see the pool algorithm in step 5.

## 2. Read `how_to_investigate_a_discrepancy.md`'s verdict-format rules once per sweep

Every dispatch prompt (step 3) restates the essentials inline since a fresh agent has no memory of
this conversation, but you should have the full doc loaded in your own context before writing
prompts, since you're the one reviewing what comes back against it (step 4).

## 3. Dispatch to Gemini -- read-only, no worktree, self-contained prompt

Use `Agent` with `subagent_type: gemini-analyzer`, `run_in_background: true`. One dispatch per
ledger shape. The prompt MUST include, every time:

- The exact shape key, its `last_seen_count`, and its FULL `last_seen_examples` list (file paths,
  names, per-tool readings) pasted inline -- don't make the agent re-derive what the ledger
  already recorded.
- The corpus root for this language: `language-crucible/data/<lang>/...` (absolute path from repo
  root).
- **Which files it may read**: the corpus files at the flagged locations, `docs/self_scan/
  how_to_investigate_a_discrepancy.md`, and (for cross-referencing an already-fixed mechanism, or
  a tool's own documented limitations) `tests/tools/tri_comparison_reconcile.py`,
  `tests/tools/ctags_reader.py`, `tests/tools/tri_comparison_gatherer.py`.
- If a live re-run of a tool would help confirm a hypothesis (e.g. "is this really ctags
  double-tagging, or something else"), give the exact `ctags`/other invocation and its path
  (see step 0's local-build recipe if it's not on PATH in the dispatch's own environment) -- but
  make clear this is optional confirmation, not required; reading source + the ledger's existing
  per-tool readings is enough for most shapes.
- **The required verdict format** (paste this into every prompt verbatim, it's what makes the
  output directly usable without rewriting):
  ```
  Report back:
  - Your overall verdict: one paragraph -- what's actually true, which tool(s) are right, why,
    and whether it generalizes to the full <N> occurrences or the sample is mixed.
  - Specific evidence for each sampled case (or grouped, if they share one cause) -- cite real
    file:line, quote the actual source, don't summarize without showing it.
  - Whether this points to a confirmed engine/tool defect worth a GitHub issue (name which
    tool/file), a known-and-already-documented limitation worth a doc note, or neither.
  ```
- **"DO NOT edit `docs/self_scan/tri_comparison_ledger.json` or any other file -- this is
  read-only investigation. Return your verdict as text; the main session applies it."** This is
  the one rule in this pipeline with no equivalent in tree-sitter-accuracy-sweep -- there's no
  worktree isolation here, so a dispatch that edits the shared ledger file directly can race with
  another dispatch's edit or with the main session's own apply step. Every prompt must say this
  explicitly, every time.
- The same three hard-won `agy` rules from `tree-sitter-accuracy-sweep` (identical failure modes,
  confirmed to recur regardless of task shape):
  - **"You must actually BLOCK and WAIT for the backgrounded `agy` process to fully exit before
    ending your turn. Do not report 'still running, I'll check back' as a final answer."** If a
    task-notification comes back describing launching/monitoring rather than an actual verdict,
    `SendMessage` back to that same agent with an explicit "you already did this, go check on the
    real process and block until it exits" instruction -- don't free the pool slot yet.
  - **"If you hit a permission/sandbox wall you can't get past, STOP and report the exact error.
    Do NOT attempt `--dangerously-skip-permissions`, and do NOT edit any config file to route
    around it."**
  - No network access in agy's sandbox -- irrelevant for pure Read/grep work, but worth stating if
    a dispatch's hypothesis-testing might reach for `pip install` or similar; redirect it to the
    already-available `ctags` binary/path instead.

## 4. Review every returned verdict before it touches the ledger

Never write a Gemini verdict straight into the ledger on trust -- read it the way step 7 of
`tree-sitter-accuracy-sweep` reads a code diff:

1. Does it cite real `file:line` and quote actual source, not just assert a conclusion? A verdict
   that reads as plausible-sounding prose without a concrete citation isn't ready -- send it back
   with "show the actual source for case N" rather than accepting it.
2. Does the "generalizes to the full N" claim have real support (cross-checked instances beyond
   the capped 10-example sample, like this session's haskell ctags investigations did) or is it an
   assumption? A verdict that's honest about "confirmed on the 10 sampled, plausible but unchecked
   beyond that" is fine and should be recorded that way -- don't silently upgrade its confidence
   when you apply it.
3. **Every verdict lands in exactly one of three buckets below -- decide which one BEFORE moving
   to the next candidate, not as an afterthought.** A verdict string sitting only in the JSON
   ledger is not enough on its own for any of these; each bucket has its own home, and skipping
   the write-through step is a real, confirmed failure mode (2026-08-19: a verdict said "worth a
   doc note in ctags_reader.py" and the note didn't actually get written until the user caught it
   missing in review -- don't let intent-in-a-verdict substitute for the actual edit).
     - **Confirmed GitGalaxy (or audit-tool) engine defect** -- file it as its own GitHub issue
       now, before moving on, same standing rule as `tree-sitter-accuracy-sweep` step 3's note and
       this repo's `file-incidental-findings-as-issues` practice. If it shares a root cause with an
       issue you already filed earlier in the same sweep, add it as a comment on that issue instead
       of a duplicate -- don't file two issues for one underlying bug just because two different
       ledger shapes surfaced it.
     - **Confirmed GitGalaxy correct, tree-sitter/ctags structurally can't** -- this is a
       `docs/why_gitgalaxy_beats_ast_here.md` finding. Check whether it fits an EXISTING claim
       first (this session found rust `struct`-inside-`macro_rules!` was the same mechanism as an
       existing claim's `fn`-inside-`quote!{}` example, one bucket, not two) and add concrete cited
       evidence to it; only write a new Claim N when the mechanism is genuinely novel. This doc's
       whole value is being narrow and evidence-backed -- a real finding from this sweep that never
       gets written here is a missed contribution to it, not a neutral no-op.
     - **Confirmed tool-side (ctags or tree-sitter) limitation, not a GitGalaxy defect** -- add a
       note to that tool's own reader module (`tests/tools/ctags_reader.py`'s per-language KIND MAPS
       bullets, or the equivalent spot in `tree_sitter_accuracy_audit.py`), matching the file's
       existing style exactly (one bullet per language/mechanism, cite the ledger shape that
       surfaced it). This is the bucket most likely to get silently skipped since it feels like
       "nothing to fix" -- it still needs writing down so the next person doesn't re-discover it.
4. **Decide `credit_tools`/`debit_tools` -- a SEPARATE decision from the bucket above, made every
   time, not just when a code fix or doc note happens to apply.** Validating a shape used to only
   change how the chart is READ (asterisk/badge suppression); it didn't move the actual precision
   number even after a verdict fully confirmed the truth -- a real, user-caught gap (2026-08-20):
   GitGalaxy's C func precision sat at 99.77% for functions the ledger had ALREADY confirmed were
   real. See `tri_comparison_ledger.py`'s own VERIFIED ADJUSTMENTS docstring section for the full
   mechanism; the decision at verdict-review time is:
     - Does the verdict cleanly confirm ONE specific tool's otherwise-uncorroborated claim is
       real, and the reason nobody else corroborates it is a confirmed limitation in THEM? -->
       `credit_tools: ["<that tool>"]`.
     - Does the verdict confirm TWO OR MORE agreeing tools' claim is a SHARED MISTAKE (both
       independently wrong for the same underlying reason, not real corroboration)? -->
       `debit_tools: ["<those tools>"]`.
     - Otherwise (the common case: a structural ambiguity, a genuinely mixed multi-cause shape, an
       agreement that IS real corroboration) -- leave both empty. Most validated shapes get
       neither adjustment; that's the correct, expected outcome, not a sign of an incomplete
       review. Never infer either field from the verdict's prose after the fact -- decide it with
       the same rigor as the verdict itself, at the same time.
5. Apply via a small Python script (see the worked example in this skill's own commit history, or
   just: load the ledger, set `status="validated"`, `verdict=<the reviewed text>`,
   `investigated_by="<model>, dispatched via tri-comparison-ledger-sweep"`, `investigated_at=<date>`,
   `credit_tools`/`debit_tools` per step 4 above, on the one entry, write back with
   `json.dumps(..., indent=2, sort_keys=True) + "\n"` to match the file's existing format exactly)
   -- never hand-edit the JSON inline, the sort/indent convention matters for a clean diff. Apply
   serially, one entry at a time, never in parallel with another dispatch's apply.

## 5. Pool mechanics

No worktree/venv build step means no real setup cost per dispatch -- a bigger pool than
`tree-sitter-accuracy-sweep`'s 5 is reasonable if you have enough candidates queued (step 1
doesn't need to be re-run until the queue empties). Default to 5 unless the backlog is large and
you have a reason to go higher; use `ListAgents` if you lose track of which dispatches are active.

Whenever a dispatch's task-notification represents a genuine completion (not the premature
interim-report false-completion from step 3):
1. Review it (step 4) and apply or send back for more evidence.
2. Immediately backfill from the candidate queue (step 1) to bring the active count back to
   target.
3. If the queue is empty, let the pool shrink -- that's the sweep winding down, not a bug.

## 6. Regenerate, verify, commit -- batch this, don't do it after every single verdict

After a batch of verdicts lands (not after each one -- the regeneration takes ~2 minutes and
churns the whole 45-language chart, no need to pay that cost per-entry):

```bash
export PATH="$PWD/.venv/bin:/tmp/gitgalaxy-scratch/ctags-local/bin:$PATH"   # or wherever ctags lives
python tests/tools/tri_comparison_chart.py --all --write   # background it, ~2min
python tests/ruff_audit.py --ci
python tests/mypy_audit.py --ci
```
Confirm the languages you just validated show fewer/zero asterisks and a real badge where earned
(this is the visible proof the sweep is working -- see this skill's own origin session, where
haskell going from 8 unvalidated shapes to 5 validated ones directly produced a clean Func
Precision badge with no asterisk). If this batch set any `credit_tools`/`debit_tools`, verify the
actual number moved by the right amount BEFORE trusting the regenerated chart -- run the pipeline
for just that language and print `matched_consensus`/`total_slots` per tool, confirm the delta
matches the shape's occurrence count exactly, and diff the full-chart SVG regeneration to confirm
ONLY the expected cell(s) changed anywhere in the whole 45-language chart (a credit/debit that
leaks into an unrelated language or panel is a real bug in the adjustment logic, not something to
wave through because the target cell looks right). Commit the code/ledger/chart changes together
with a message that names which shapes were validated and why, and separately names any
credit/debit applied (the ledger's own verdict text is the detailed record; the commit message is
the summary a `git log` skim should be able to trust).

## 7. One accumulating PR, not one per shape

Unlike `tree-sitter-accuracy-sweep` (one PR per language fix, since each is an independent code
diff), ledger verdicts all touch the same file and don't need independent review/merge -- keep
ONE PR open for the sweep's duration, push each verified batch to it, and let it accumulate. Open
a new one only when the prior one merges or when starting an unrelated piece of work. Expect the
false-conflict-from-squash-merge situation described in step 0 to recur across a long-running
sweep; resolve it the same way each time (`--ours` + regenerate), not by hand-merging.

**No auto-merge pre-authorization for this skill** (unlike `tree-sitter-accuracy-sweep`'s narrow
carve-out) -- a ledger verdict is a judgment call about what's TRUE, not a mechanically-verified
code fix with a green test suite to lean on; get the normal explicit go-ahead before merging.

## 8. Capstone: when a language's backlog clears, write it up before moving on

**Trigger:** every currently-reproducing shape for a language is `status: "validated"` (check with
the same query step 1 uses, filtered to that language, confirming zero results). Do this BEFORE
starting the next language, not as a someday follow-up -- the whole reason it's cheap right now is
that every file:line citation, every confirmed mechanism, and every "is this GitGalaxy's fault"
verdict is still loaded in this session's context. Reconstructing that same picture from a cold
read of the ledger later costs real tokens and real judgment a fresh session doesn't have for
free; this is a real, confirmed miss, not a hypothetical (2026-08-19: the `c` sweep's own capstone
pass surfaced a doc-note that was promised in a verdict but never actually written, AND a second,
unfiled instance of the same tooling bug pattern in a sibling language's ctags kind-map that
nobody would have thought to check without the language's full picture still fresh).

Two things to produce, both while the context is cheap:

1. **One more incidental-finding pass across sibling data structures.** If a fix this language's
   sweep made was a bug in a per-language MAP or TABLE (a ctags kind map, a node-type set, an
   exclusion list -- anything keyed by language), check whether the SAME bug shape exists for
   OTHER languages' entries in that same structure, not just the one you were investigating. This
   is exactly how the `cpp` `CTAGS_CLASS_KINDS` gap
   ([#1877](https://github.com/squid-protocol/gitgalaxy/issues/1877)) got found -- it would not
   have been found by a fresh session opening `ctags_reader.py` cold, only by someone who'd just
   spent an hour reasoning about C's identical map. File whatever turns up per step 4.3's buckets,
   same as any other finding -- this is still bucket-sorting, not a new category of work.
2. **A tri-comparison write-up in `docs/language_status/<lang>.md`.** This repo already has a
   `language-status` skill for a *different* kind of per-language doc (sections 1-8: what
   GitGalaxy detects, test depth, closed issues, real-world evidence -- built from
   `language_standards.py`/test counts/`gh issue list`, none of which this sweep's session context
   is specially positioned to write). The tri-comparison findings are a genuinely different,
   complementary section: a 3-way comparison with no privileged ground truth, which doesn't fit
   that skill's own "§9 measured accuracy vs. one ground-truth parser" template -- write it as its
   own numbered section (see `docs/language_status/c.md`'s §9 for the shape once it exists) rather
   than force-fitting the tri-comparison shape into that template. Content that belongs in it,
   all of which only this session actually has on hand:
   - Summary stats: shapes investigated, occurrences covered, confirmed GitGalaxy engine defects
     found (compare across languages -- `rust` found 2 real ones, `c` found zero, and that
     contrast IS the finding, not a gap in one or the other).
   - "Where GitGalaxy wins outright" -- the confirmed cases, with real file:line citations, not
     hand-wavy summaries.
   - "Where the other tools have real, documented gaps" -- same standard.
   - Any bugs found and fixed in the comparison tooling itself, separate from either.
   - A link to the ledger file (filtered to that language) and the rendered points-of-interest doc
     as the full record.
   If `docs/language_status/<lang>.md` doesn't exist yet for this language, dispatch the
   `language-status` skill (as its own background task, sections 1-8 only, explicitly told to stop
   before writing its own §9 and to leave the file ready for this section to be appended) while
   writing this section yourself in parallel -- don't wait for it serially when the two pieces
   don't depend on each other. If the doc already exists, just add/refresh this section in place.

Commit the language_status doc alongside (or right after) the final validated-verdict batch for
that language, same PR is fine.

## The papertrail, end to end

Seven layers, each serving a different reader -- step 4.3's three buckets map directly onto layers
2-4 below, so "which bucket" and "which papertrail layer" are the same decision, not two separate
ones:
1. **The ledger entry itself** (`status`, `verdict`, `investigated_by`, `investigated_at`,
   `last_seen_examples`) -- the permanent, hand-editable record of what was actually found, per
   discrepancy shape. This is the primary source; everything else derives from or points back to
   it. Every verdict gets one of these, regardless of which bucket it falls into.
2. **GitHub issues** for confirmed engine defects (step 4.3, bucket 1) -- the actionable,
   triageable trail for anything that needs an actual code fix.
3. **`docs/why_gitgalaxy_beats_ast_here.md`** for confirmed GitGalaxy-correct/tree-sitter-or-
   ctags-structurally-can't findings (step 4.3, bucket 2) -- this repo's standing, evidence-gated
   record of exactly this claim shape; don't let a real one go unwritten here.
4. **The relevant tool's reader module** (`ctags_reader.py`, `tree_sitter_accuracy_audit.py`) for
   confirmed tool-side limitations (step 4.3, bucket 3) -- so the next sweep doesn't re-discover
   the same ctags/tree-sitter gap from scratch.
5. **`docs/self_scan/tri_comparison_points_of_interest.md`** -- regenerate with `python
   tests/tools/tri_comparison_report.py --write` after a batch lands, so there's a human-scannable
   Markdown log ranked by signal strength, not just a JSON blob to query. Cuts across all of the
   above rather than being its own bucket.
6. **`docs/language_status/<lang>.md`**'s tri-comparison section (step 8, once a language's
   backlog fully clears) -- the synthesized, human-readable "what did we learn about this
   language" capstone, distinct from the per-shape ledger entries it's built from.
7. **`docs/self_scan/manual_verification.json`** (step 7 of the gg-only fallback procedure above)
   -- the layer-1 equivalent for a language that can never get a ledger entry at all (no second
   tool means no discrepancy shape to log). Same discipline as the ledger: hand-written, hand-
   reviewed, never machine-generated, and read directly by `tri_comparison_chart.py` to render the
   `**` label / earn a badge for a genuinely verified 1-tool language.

Commit messages should name the shapes validated, not just say "update ledger" -- a future reader
`git log`-ing this file should be able to tell what changed and why without opening the diff.

## Known gotchas checklist (recap, all confirmed this session)

- `arduino-ctags` shadows the `ctags` name on Ubuntu but isn't universal-ctags -- always confirm
  `ctags --version` says "Universal Ctags" before trusting a run, and use the no-root local-build
  recipe in step 0 if it's missing.
- `tri_comparison_chart.py --write` with a partial `--languages` list overwrites the WHOLE SVG
  with only those languages -- never `--write` anything but a full `--all` run; use plain
  (non-`--write`) output for spot-checks.
- Never let a dispatched agent edit `tri_comparison_ledger.json` directly -- it's read-only
  investigation only, applied by the main session, serially, every time (step 3/4).
- agy backgrounds itself and reports the interim "launched" status as final -- same failure mode
  as `tree-sitter-accuracy-sweep`, same fix (resend an explicit block-and-wait instruction).
- A false merge conflict from a squash-merged predecessor PR is expected on the two generated
  files, not a sign of a real content conflict -- resolve with `--ours` + regenerate, confirmed
  safe (byte-identical SVG regeneration) in this skill's origin session.
- Validating a shape does NOT automatically move its precision number -- that only happens if you
  also set `credit_tools`/`debit_tools` (step 4). It's easy to review a verdict thoroughly, apply
  it, and still leave a confirmed-correct tool sitting at an artificially low score because that
  separate decision got skipped -- this is exactly the gap the user caught that motivated adding
  the mechanism at all (2026-08-20), so treat step 4 as mandatory per verdict, not optional polish.
- Debit an agreeing pair together (not one of the two) when they're independently wrong for the
  SAME underlying reason, which is the normal shape once you find one (every real case seen so far
  -- two regex/grammar engines both fooled by the same macro-definition text is a shared mechanism,
  not a coincidence). Only split them if the verdict specifically distinguishes one as right and
  the other as coincidentally also wrong for an unrelated reason -- rare.
- Fixing one confirmed engine bug is not proof the surrounding extraction path is now fully
  correct -- re-verify the fix against the REAL pipeline/DB output (step 2b) before moving on,
  every time, not just once per language. ABAP's manual-verification pass (2026-08-19/20) found 7
  separate, independent bugs this way, not 1, across three waves: fixing #1898 (a `prism.py`
  comment-stripping bug) and re-checking its actual DB output surfaced #1899 (a completely
  different `detector.py` slicing-mode bug) sitting right next to it; fixing #1899 and regenerating
  the tri-comparison chart surfaced #1904 (a THIRD, independent bug -- a named-class-extraction
  allowlist gap); verifying #1904's own fix surfaced #1907 (a fourth -- a class-boundary detector
  confused by ABAP's own string-template syntax); going back to close out step 4's "noted as a
  known open question, not evidence-backed enough to file" item on `args` (rather than leaving it
  open indefinitely) found a fifth, #1911 (the exact same `prism.py` comment-stripper as #1898, a
  different unqualified character -- `!`, not `C`/`c`/`/`); and building the args `**` chart display
  on top of THAT fix (rather than assuming a green regex meant a green per-function count) found
  two more, #1917 (two more regex-correctness bugs in the same `args` pattern) and #1918 (the
  per-function count searched the wrong section of the file entirely, with a derivation mechanism
  that couldn't have produced a real count even in the right span). An "open question, not yet
  root-caused" note in step 4 is a lead to come back to, not a permanent resting state -- don't let
  a sweep close out with unresolved "probably related" questions still sitting in the doc if
  there's more budget to chase them down. Each bug was invisible until the previous one was fixed
  and re-checked against real output -- stopping at the first green result after fix #1 would have
  left 6 more silently in place. See `docs/language_status/abap.md` §9 for the full evidence trail.
- A manual-verification badge (step 7's `_manual_verification_winner()`) requires
  `verified == total` EXACTLY -- resist the temptation to award one for "verified most of it" or
  "spot-checked a representative sample and it all matched." A partial verification is real,
  useful evidence and belongs in the `**` label same as always, but a badge is a stronger claim
  ("we know who's actually right," matching what a real cross-tool win asserts) than "probably
  fine based on a sample" earns -- don't blur the two the way this skill's own `*`/`**` distinction
  already refuses to blur unvalidated-disagreement from manual-review.
