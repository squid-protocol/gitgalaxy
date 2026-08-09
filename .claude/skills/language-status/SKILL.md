---
name: language-status
description: Create or refresh a per-language coverage doc under docs/language_status/<lang>.md -- what GitGalaxy's structural-signature engine actually detects for that language, what it explicitly doesn't, how deep the test coverage is, which closed issues/PRs shaped it, and real-world scan evidence from gitgalaxy-raw-output. Use when the user asks "what does gitgalaxy support for X", "document language status", "write a coverage doc for <lang>", "is python/rust/cobol fully covered", or similar. Not for changing engine behavior -- that's harden-language-extraction or harden-strict-signatures.
---

Closed epics (#518, #813, #1069, #1071...) already did the hard work of finding and fixing
per-language gaps, but that history is scattered across ~150 individual issues with no single
place a reader (or a future Claude session) can go to answer "what does this scanner actually do
for Python?" without re-deriving it from `language_standards.py` and a pile of `gh issue list`
searches. `docs/language_status/<lang>.md` is that place: one file per language, built entirely
from primary sources (never from memory of a past pass, since coverage keeps changing), with
`docs/language_status/README.md` as the index. See `docs/language_status/python.md` for a
finished example of what "done" looks like.

**Scope discipline:** this skill only writes documentation. If gathering the material for a doc
surfaces a real gap worth fixing (a missing signature, a stale test count, a regex bug), that's a
finding for `harden-language-extraction` / `harden-strict-signatures` / a filed issue
(`issue-generation` skill, or `gh issue create` directly if you already have the full technical
detail from the investigation) -- don't fix it inline as a side effect of a docs pass, and don't
let the doc quietly launder an unfixed gap into looking resolved. The §9 measured-accuracy pass
below is *expected* to surface exactly this kind of finding -- filing real issues from it (see
python.md's #1182/#1183/#1184) is the correct outcome, not scope creep.

## Where the material lives (read these fresh every time, don't trust a prior doc's numbers)

1. **`gitgalaxy/standards/language_standards.py`** -- `LANGUAGE_DEFINITIONS["<lang>"]`. This is
   the ground truth for: `_meta` (target_version, blueprint_version, status, last_updated),
   `extensions`/`exact_matches`/`discriminators`/`shebangs` (identification surface),
   `lexical_family`, and the `rules` dict (every structural-signature key, `None` for the ones
   the language doesn't have -- read the inline comment next to each `None`, it usually explains
   why, e.g. `"macros": None,  # Python lacks a C-style preprocessor.`). The ~66 possible rule
   keys and what each one is *supposed* to mean are documented in
   `gitgalaxy/standards/how_to_add_a_language.md`'s OUTPUT SCHEMA section -- read that once for
   vocabulary, then describe what the language's *actual* regex captures (its own comments and
   alternation list), not the generic schema definition.
2. **`tests/extraction/languages/test_<lang>.py`** and **`test_<lang>_strict.py`** -- the
   evidentiary test depth. Get real counts with pytest collection, not `grep -c "^def test_"`
   (parametrized cases don't show up as separate `def`s):
   ```bash
   source venv/bin/activate   # or whatever this checkout's env is called
   python -m pytest tests/extraction/languages/test_<lang>.py tests/extraction/languages/test_<lang>_strict.py --collect-only -q | tail -1
   ```
   If a language hasn't been migrated to the per-language file yet (extraction epic #813 isn't
   100% closed out across every language), its extraction-gauntlet cases may still be sitting in
   the four old monolithic files (`test_function_extraction.py`, `test_args_extraction.py`,
   `test_class_extraction.py`, `test_dependency_extraction.py`) -- grep those for the language's
   dict key before reporting a suspiciously low or missing count.
   Also grep both files for `known_limitation` in the test name -- those are documented,
   deliberately-not-fixed gaps and are exactly the "what it doesn't do" material a status doc
   needs; don't skip past them as just more passing tests.
3. **Closed issues/PRs** -- search, don't guess from memory (issue numbers drift and get
   reused-in-spirit across epics):
   ```bash
   gh issue list --repo squid-protocol/gitgalaxy --search 'in:title "Extraction hardening: <lang>"' --state all --json number,title,state
   gh issue list --repo squid-protocol/gitgalaxy --search 'in:title "Strict parsing tests: `<lang>`"' --state all --json number,title,state
   gh issue list --repo squid-protocol/gitgalaxy --search 'in:title <lang>' --state closed --json number,title
   ```
   The third query is noisy (matches unrelated issues that merely mention the language name) --
   skim titles and keep only ones that actually changed behavior for this language (a regex bug
   fix, a new signature key, a ReDoS fix). Cross-check against the epic parents (#518, #813,
   #1069, #1071) if the language's sub-issue number isn't obvious from title search alone.
4. **`gitgalaxy-raw-output`** (separate repo, `squid-protocol/gitgalaxy-raw-output`) -- real,
   unedited scan output on production code, for the "see it in action" close-out section. Find
   2-4 well-known repos whose primary language is the one you're documenting:
   ```bash
   gh api repos/squid-protocol/gitgalaxy-raw-output/contents/v2.4.7 --jq '.[].name' > /tmp/raw_output_repos.txt
   grep -i -E '<candidate1>|<candidate2>|...' /tmp/raw_output_repos.txt   # match against well-known projects in that language's ecosystem
   ```
   (bump `v2.4.7` to whatever the newest version directory is -- `gh api
   repos/squid-protocol/gitgalaxy-raw-output/contents/` lists them). Each matched repo directory
   contains `<repo>_galaxy_llm.md`, `_galaxy_audit.json.gz`, `_galaxy_sbom.json.gz`, etc. -- link
   the `_galaxy_llm.md` (human-readable) as the primary reference. Don't invent candidate names;
   pick ones you can actually confirm exist in the listing, and prefer a size/era spread (a small
   library, a large framework, and something adversarial like the language's own reference
   implementation if it's in the corpus) over four similar mid-size web apps.
5. **Real-world measured accuracy** (optional, deeper pass -- see python.md §9 for the finished
   example) -- everything above describes what's wired and how it's tested *in isolation*. The
   strongest possible evidence is diffing GitGalaxy's actual extraction against an independent
   ground-truth parser on real code, because that's the only thing that exercises the
   segment-routing/scope-boundary machinery the isolated per-rule tests don't touch. For Python
   this is `ast` (stdlib, zero setup). For other languages, check what's actually available before
   promising this section -- don't guess a package name, verify it:
   ```bash
   pip index versions <candidate-package-name>   # confirms it's real before you rely on it
   ```
   `tree-sitter-language-pack` (verified on PyPI, ships pre-compiled grammars for 371 languages,
   no per-language compiler/JDK/Go-toolchain needed) is the broadest single option. A handful of
   languages also have lighter pure-Python parsers worth checking first (confirmed to exist at
   time of writing: `bashlex` for shell, `javalang` for Java, `luaparser` for Lua, `sqlparse` for
   SQL/SQLite -- weaker, it's more tokenizer than strict grammar, `dockerfile-parse` for
   Dockerfile, `esprima` for JavaScript ES5, `solidity-parser` for Solidity). Genuinely no
   practical ground truth exists for `cobol`, `jcl`, `fortran`, `assembly`, `agc_assembly`,
   `abap`, `matlab`, `livecode`, `apex` -- the same legacy/esoteric languages that are GitGalaxy's
   own reason to exist; don't force this section for them, note its absence instead.
   Methodology once a parser is confirmed: diff function/class *names* (watch for a truncation
   cap skewing an apparent name mismatch into a false "hallucination" reading -- confirm exact
   vs. truncated before concluding either way), diff per-function arg counts, and cross-check at
   least one keyword-style rule (e.g. `branch`) two ways -- against the ground-truth parser's own
   token/node stream, AND by running the compiled rule directly against `prism`-shielded
   `code_stream` (bypassing any recorder/aggregation layer) -- because keyword rules and
   boundary-extraction rules can have very different accuracy profiles, and conflating them
   produces a misleading single number. If a measured gap doesn't have an obvious cause, say so
   plainly and file it as a confirmed-but-undiagnosed pattern (see #1184) rather than guessing at
   a root cause you haven't verified.

## Per-language doc structure (`docs/language_status/<lang>.md`)

Follow `python.md`'s section order:
1. **At a glance** -- one table: status, target/blueprint version, last_updated, lexical_family,
   rule keys wired/total, extraction-gauntlet test count, strict-signature test count.
2. **Identification surface** -- extensions/exact_matches/discriminators/shebangs, terse.
3. **What GitGalaxy detects** -- every wired (non-`None`) rule key, grouped by the same phase
   headers `language_standards.py` and `how_to_add_a_language.md` already use (topology/
   structure, safety/risk, architecture/domain sensors, specialized subsystems, resource
   management), one line each describing what the language's *actual* pattern matches -- not the
   generic cross-language definition.
4. **What GitGalaxy explicitly does not track** -- every `None` key plus its inline reason.
5. **Known limitations (accepted, not fixed)** -- from the `known_limitation`-named tests found
   in step 2 above. If there are none for this language, say so plainly rather than omitting the
   section -- an absent section reads as "not checked," not "nothing found."
6. **Test depth** -- the counts from step 2, with a one-line note on where the extraction-gauntlet
   cases live if not yet migrated to the per-language file.
7. **Relevant closed work** -- the issues/PRs from step 3, grouped (epic-level hardening passes vs.
   real bugs found along the way vs. cross-language fixes that happened to touch this language).
8. **Real-world evidence** -- the `gitgalaxy-raw-output` links from step 4, one line each on what
   makes that particular repo a useful data point (size, age, adversarial shape).
9. **Measured accuracy** (only if step 5's ground-truth parser exists and you actually ran the
   comparison) -- the methodology in one paragraph, a results table (recall/precision per signal,
   not just one aggregate number), and any confirmed defects with links to the issues filed for
   them. Omit this section entirely rather than writing a stub if no ground-truth parser was
   available -- an absent §9 reads as "not attempted yet," not "verified clean."

## Process

1. Confirm the language exists in `LANGUAGE_DEFINITIONS` and whether it has any non-`None` rules
   at all -- ~13 entries (`json`, `xml`, `csv`, `plaintext`, ...) are pure data/text formats with
   nothing to structurally signature-match. Those don't get a full doc; note them in the index
   table only (see `docs/language_status/README.md`'s "Data formats" section) rather than writing
   an empty prose doc for each.
2. Gather source categories 1-4 above for the target language before writing anything -- writing
   section-by-section from a half-gathered picture is how a doc ends up contradicting itself
   between "what it detects" and "known limitations." Category 5 (measured accuracy) is a
   separate, heavier pass -- fine to ship a doc without it (sections 1-8) and add §9 later once a
   ground-truth parser is confirmed and the comparison is actually run.
3. Write the doc following the structure above. Keep descriptions grounded in what you actually
   read (the regex's own alternation list, the comment next to it) -- don't paraphrase the
   generic schema definition from `how_to_add_a_language.md` as if it were language-specific.
4. Add or update the language's row in `docs/language_status/README.md`'s index table (same
   columns as the "at a glance" table above, plus a link to the new doc).
5. This is documentation, not a parsing-logic change -- no `crucible_check.py` or
   `audit_check.py` needed. Normal commit/PR discipline still applies (CLAUDE.md's "Working
   autonomously" section pre-authorizes commits/PRs against `main` in this repo).
6. If §9 surfaced confirmed defects, file them as real issues (`gh issue create` or
   `issue-generation`) with the concrete reproduction, before or alongside the doc PR -- link the
   issue numbers back into §9 rather than describing the bugs only in prose.

## Rolling this out across all languages

Writing all ~46 signature-bearing languages' docs in one sitting is exactly the kind of work
epic #813 and epic #1069 already proved goes better as one-sub-issue-per-language than one giant
PR -- if the user wants full coverage, propose the same shape (an epic + per-language sub-issues,
via the `issue-generation` skill) rather than attempting all of them inline. This skill handles
one language's doc at a time, same granularity as `harden-language-extraction` and
`harden-strict-signatures`.

## Keeping docs from going stale

A language's status doc is a snapshot, not a live view. Re-run this skill for a language whenever
`harden-language-extraction` or `harden-strict-signatures` closes a pass on it (new test counts,
possibly closed "known limitations"), or when a `language_standards.py` PR changes its `rules`
dict. There's no automated staleness check -- if the user asks for a "status check" on a language
whose doc looks old (compare its "last_updated"/test counts against a fresh run of step 2 above),
say so explicitly rather than presenting stale numbers as current.
