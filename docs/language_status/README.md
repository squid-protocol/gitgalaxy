---
description: "One doc per language describing what GitGalaxy's structural-signature engine actually covers —"
---
# Language Status

One doc per language describing what GitGalaxy's structural-signature engine actually covers —
what it detects, what it explicitly doesn't, how deep the test evidence is, which closed
issues/PRs shaped it, and real-world scan output proving it runs on production code in that
language. Built entirely from primary sources (the `gitgalaxy/standards/language_standards/` package, the
`tests/extraction/languages/` suite, closed GitHub issues, and the
[`gitgalaxy-raw-output`](https://github.com/squid-protocol/gitgalaxy-raw-output) corpus) — see the
`language-status` skill (`.claude/skills/language-status/SKILL.md`) for the exact process and
commands used to produce each one.

**These are snapshots, not a live view.** The per-language docs record what was measured when they
were written. `language_standards.py`, the test suite, and issue history all keep moving — re-run
the skill's data-gathering commands rather than trusting a stale page if the answer matters. This
page keeps no counts; current estate and proof numbers are on the generated
[`progress.md`](https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/progress.md).

**`python.md` also has a "Measured accuracy" section (§9)** — a real-corpus diff of GitGalaxy's
own extraction against Python's `ast` module as ground truth, not just the isolated-snippet unit
tests every other section describes. Across two rounds of measurement it found four real defects
([#1182](https://github.com/squid-protocol/gitgalaxy/issues/1182),
[#1183](https://github.com/squid-protocol/gitgalaxy/issues/1183), and
[#1184](https://github.com/squid-protocol/gitgalaxy/issues/1184) — all now fixed — plus
[#1193](https://github.com/squid-protocol/gitgalaxy/issues/1193), still open) and measured
function recall on real code well below what the unit-test suite alone would suggest — read it
before assuming "tests pass" means "finds everything on real code." It's also a worked example of
a subtler lesson: #1184 is a fully-verified fix (the component it touches is provably 100%
correct in isolation now), but real-pipeline recall barely moved, because #1193 — undiscovered
until the *second* measurement round — sits upstream of it and corrupts the input before #1184's
fix ever gets a chance to run. Worth repeating for other languages with an available AST/grammar
(see §9's `tree-sitter-language-pack` note) once a language's base doc exists.

**`javascript.md`'s §9 is the first repeat of that methodology via `tree-sitter-language-pack`**
(python.md's own §9 flagged this as the path to scale beyond Python's stdlib `ast`) — confirms
#1209/#1216's `args` capture-group fix works on real code (100% args-count exact match across two
corpora), and found one blocking infra bug (fixed same-day,
[#1220](https://github.com/squid-protocol/gitgalaxy/pull/1220)) plus two open extraction defects
([#1221](https://github.com/squid-protocol/gitgalaxy/issues/1221) — phantom functions from
unguarded bare call statements, also affects `typescript`/`java`/`csharp`/`apex`/`dart`/`groovy`;
[#1222](https://github.com/squid-protocol/gitgalaxy/issues/1222) — real functions silently dropped
from class bodies, tied to a previously-unfixed diagnosis in #789). Worth reading before assuming
`tree-sitter-language-pack` is a trivial drop-in for the next language's §9 — javascript's pass
needed a from-scratch tree-sitter node-walker (no existing helper), and surfaced a genuine,
separate infra bug along the way.

**`jcl.md`'s §10 is the first "Rosetta cross-language consistency" capstone section** — the
[keyword-rosetta](https://github.com/squid-protocol/keyword-rosetta) control-corpus counterpart
of §9: not "is extraction accurate on real code?" but "does the engine measure identical planted
intent the same in this language as in the other 45?" It records the language's measured-bias
standing (epic [#2560](https://github.com/squid-protocol/gitgalaxy/issues/2560)'s per-language
tracking issue), with every deviation classified by cause — real engine bug, missing rule with
genuine morphology, corpus authoring gap, ledgered intended morphology, or median inflation by
*other* languages' bugs — so a deliberately-absent rule reads differently from an unexamined gap.
The jcl pass found one engine-wide bug this way (#2610: `//*` comments never reached the comment
surface) and took jcl from 4th-worst of 46 to mid-pack. Write this section via the
keyword-rosetta repo's `rosetta-language-sweep` skill once a language's rosetta issue gets a real
sweep; the section template is in the `language-status` skill.

**CICS / mainframe estates: read [`cics_mainframe_facts.md`](cics_mainframe_facts.md)** (added
2026-09-25). The per-language docs cover structural signals. That page covers the mainframe
**fact channels**: call graph, transactions, CICS resource operations, units of work, DB2 / IMS / MQ
access and field lineage. For each it gives the verification tier (cross-verified, sample-verified
or draft) per keyed corpus, the estate-completeness scores, and a plain list of what is unsupported
or unproven. It also covers BMS and CSD, which have no signal doc of their own. `cobol.md`,
`pli.md`, `hlasm.md` and `jcl.md` each have a §11 summarising their part (`db2_sql.md` §9,
`java.md` §10).

**CICS translation: [`cics_crucible.md`](cics_crucible.md)** (added 2026-09-29, #3989) is generated
by `tests/tools/cics_crucible.py`. It measures the CICS pipeline against
[cics-crucible](https://github.com/squid-protocol/cics-crucible)'s hand-written expected logs, per
case and scenario: engine facts, whether the generated project compiles, the COBOL on the stub
runtime, and the generated Java. It also lists the harness work each unsupported cell waits on.

**Definition of done (#4722): [`definition_of_done.md`](definition_of_done.md).** What "done" means for a COBOL / CICS / Db2 migration: scope, the acceptable outcomes per program (a stated evidence level, or a refusal by name), what an estate needs to be done, and what "supported" means for the readiness scanner.

**CICS command specification (#4270): [`cics_command_spec.md`](cics_command_spec.md) and [`gitgalaxy/standards/cics/README.md`](../../gitgalaxy/standards/cics/README.md).** One declarative specification for the `EXEC CICS` commands, each marked full on both runtimes, engine-only or a name-only refusal, generating both `CicsSpec.java` and `tests/equivalence/cics/ggcics_spec.h`. The live per-command status table and its counts (with census counts and crucible coverage) is published on the `generated` branch at [`cics_spec_status.md`](https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/cics_spec_status.md).

**Offline readiness scanner & CICS era tagging (#4724, #4725, #4726, #5117): [`feature_inventory.md`](feature_inventory.md) and [`gitgalaxy/tools/readiness/README.md`](../../gitgalaxy/tools/readiness/README.md).** `gitgalaxy assess` inventories a customer estate offline and read-only, tags each program and copybook across `Era 0` (CICS macro level) through `Era 4` (Enterprise COBOL channels, containers, web, and async) from concrete source tells (`era_tags.py`), and projects the output through a closed-vocabulary schema with zero source text leakage. `tests/tools/support_matrix.py` and `tests/tools/era_distribution.py` render the burned-estate support matrices and non-burned era distributions.

**Evidence reports & per-program records (#4048, #4054, #5206): [`evidence_records.md`](evidence_records.md) and [`evidence_report/README.md`](evidence_report/README.md).** `tests/tools/evidence_report.py` measures the `L0–L5` deterministic translation ladder across the burned estates, regenerated on every push to `main` onto the `generated` branch. `tests/tools/estate_evidence.py` rolls up the committed `evidence.json` records onto the `E0–E4` ladder (coverage and mutation scores, lines), published nightly on `generated` (`estate_evidence/`).

**COBOL-to-Java proofs: [`oracle_assumptions.md`](https://github.com/squid-protocol/gitgalaxy/blob/generated/docs/language_status/oracle_assumptions.md)** (added 2026-10-02). A proof compares the
Java port with the COBOL program run by GnuCOBOL plus our CICS, Db2 and LE models, not by IBM z/OS. That page lists
every known or suspected difference between the two, its status (matched, refused, differs, assumed), whether a
proven program reaches it, and what would settle it. It is generated from one file per entry in
[`register/`](register/): add or edit an entry there, take a new ID with `python tests/tools/register.py next X`, and run
commit the entry file only: the page is not committed (#5057); CI renders it and shows the diff, and it is published
to the `generated` branch after merge (`register.py render` writes a local copy to read).

**A third-party translation through the same harness: [`ibm_wca4z_lgacdb01.md`](ibm_wca4z_lgacdb01.md)** (added
2026-10-02). IBM's published watsonx Code Assistant for Z translation of GenApp's LGACDB01 (INSERT-CUSTOMER), run
inside our det port with a thin adapter (`tests/tools/ibm_wca4z_port.py`): not proven. Its INSERT never binds
DATEOFBIRTH, and it swallows the failure. The page also compares IBM's paragraph-level, mocked validation with ours.

**What each COBOL construct becomes in Java: [`construct_correspondence.md`](construct_correspondence.md)**
(added 2026-10-02) is generated by `tests/tools/construct_map.py`. It lines up every converted program's
paragraphs with the det port's methods (exactly) and the model port's (by evidence), and measures each construct
on both sides. It shows where the det port grows, and ranks candidate rewrite rules for its readability layers.
Each rule lists the cases it must be proven on.

The other COBOL-to-Java pages here: [`gitgalaxy/tools/cobol_to_java/README.md`](../../gitgalaxy/tools/cobol_to_java/README.md) (the full CICS-to-Java pipeline, era coverage, and scorecards), [`det_port_design.md`](det_port_design.md) (the deterministic translator, its
runtime contract and every proven result), [`det_survey.md`](det_survey.md) (how much of six estates it translates),
[`statement_inventory.md`](statement_inventory.md) (what a deterministic translator could take over, by statement
kind), [`porting_loop.md`](porting_loop.md) (model-written ports), [`mutation_testing.md`](mutation_testing.md) and
[`cics_crucible.md`](cics_crucible.md). [`estate4_dbb_mortgage.md`](estate4_dbb_mortgage.md): the fourth estate (IBM DBB MortgageApplication), what was proven and what onboarding it needed. [`estate4_async_creditcard.md`](estate4_async_creditcard.md): the cicsdev async credit-card example, pinned as a development (burned) estate (#4270). [`transferability.md`](transferability.md): a dated record of how far burned-estate translation carried over to non-burned code (#6069). The wiki's summary is `docs/wiki/05-19-proven-cobol-to-java-ports.md`.

## Signature-bearing languages

These languages have at least one non-`None` structural-signature rule
(`func_start`/`branch`/`io`/etc.), the ones a per-language status doc in this folder is actually
for. No counts are kept here (they drifted): read the rule counts from the language's `rules` dict
in `gitgalaxy/standards/language_standards/languages/<lang>.py`, and the test counts live with
`pytest --collect-only tests/extraction/languages/test_<lang>.py` / `test_<lang>_strict.py`.

| Language | Status | Lexical family | Status doc |
|---|---|---|---|
| **[abap](abap.md)** | production | positional_abap | **written** |
| **[acs](acs.md)** | production | standard_block | **written** (#5465) |
| ada | production | line_exclusive_dash | not written |
| **[agc_assembly](agc_assembly.md)** | production | line_exclusive | **written** |
| **[apex](apex.md)** | production | standard_block | **written** |
| **[assembly](assembly.md)** | production | line_exclusive | **written** |
| **[c](c.md)** | production | standard_block | **written** |
| **[cobol](cobol.md)** | production | positional_anchored | **written** |
| **[cpp](cpp.md)** | production | standard_block | **written** |
| **[crystal](crystal.md)** | production | line_exclusive | **written** (#5623) |
| **[csharp](csharp.md)** | production | standard_block | **written** |
| **[css](css.md)** | production | standard_block | **written** |
| dart | production | standard_block | not written |
| **[db2_sql](db2_sql.md)** | production | multi_style_dash | **written** (#2511) |
| dockerfile | production | line_exclusive | [dockerfile.md](dockerfile.md) |
| easytrieve | production | line_exclusive | not written |
| embedded_python | production | line_exclusive | [embedded_python.md](embedded_python.md) |
| **[fortran](fortran.md)** | production | positional_anchored | **written** |
| **[fsharp](fsharp.md)** | production | recursive_block | **written** (#5623) |
| go | production | standard_block | not written |
| **[groovy](groovy.md)** | production | standard_block | **written** |
| haskell | production | recursive_block_haskell | not written |
| **[hlasm](hlasm.md)** | production | positional_anchored | **written** (#2503) |
| html | production | block_exclusive | [html.md](html.md) |
| **[java](java.md)** | production | standard_block | **written** |
| **[javascript](javascript.md)** | production | standard_block | **written** |
| **[jcl](jcl.md)** | production | line_exclusive | **written** |
| **[kotlin](kotlin.md)** | production | standard_block | **written** |
| **[livecode](livecode.md)** | production | multi_style_live | **written** |
| **[lua](lua.md)** | production | multi_style_dash | **written** (§9 via tri-comparison sweep) |
| m4 | production | line_exclusive | not written |
| makefile | production | line_exclusive | not written |
| markdown | production | line_exclusive | [markdown.md](markdown.md) |
| matlab | production | line_exclusive | not written |
| objective-c | production | standard_block | not written |
| perl | production | line_exclusive | not written |
| php | production | standard_block | not written |
| **[pli](pli.md)** | production | standard_block | **written** (#2502) |
| postgresql | production | multi_style_dash | not written |
| powershell | production | embedded_syntax | not written |
| **[python](python.md)** | production | line_exclusive | **written** |
| **[rexx](rexx.md)** | production | recursive_block_rexx | **written** (#2504) |
| ruby | production | line_exclusive | not written |
| rust | production | recursive_block | not written |
| scala | production | recursive_block | not written |
| scheme | production | recursive_block_lisp | not written |
| shell | production | line_exclusive | not written |
| solidity | production | standard_block | not written |
| sqlite | production | multi_style_dash | not written |
| swift | production | recursive_block | not written |
| **[tcl](tcl.md)** | production | line_exclusive | **written** (§9 via tri-comparison sweep) |
| typescript | production | standard_block | not written |
| **[yacc](yacc.md)** | production | standard_block | **written** (§9 via tri-comparison sweep) |
| yaml | production | line_exclusive | not written |
| zig | production | line_exclusive | not written |
| **[zscript](zscript.md)** | production | standard_block | **written** (#5535) |

## Data formats (out of scope for a full doc)

`batch`, `blp`, `csv`, `glsl`, `hlo`, `json`, `mlir`, `nix`, `pbtxt`, `plaintext`, `proto`, `td`,
`xml` — recognized by the engine for identification/routing purposes but carry no structural
signatures (`rules` is empty or all keys are pure boilerplate), because there's no executable
logic to structurally signature-match. These don't get a per-language prose doc.

## Writing the next one

See `.claude/skills/language-status/SKILL.md`. Full rollout across all of them is tracked as follow-on
work (one sub-issue per language, same shape as epic #813/#1069) rather than attempted in one
pass — `python.md` is the worked template.
