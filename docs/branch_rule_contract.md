# The `branch` rule contract (#2822)

> **One hit is a keyword or operator that opens a runtime choice between
> control-flow paths: the choosing construct or one of its alternative arms.**

Stated 2026-09-06 by the #2822 audit (roadmap Phase 3, epic #2812). Precedents:
`docs/api_rule_contract.md` (#2730), `docs/args_rule_contract.md` (#2773),
`docs/state_mutation_rule_contract.md` (#2765). The machine-readable row is
`gitgalaxy/standards/signal_contracts.py`; the cross-language pins are
`tests/extraction/languages/test_branch_contract_2822.py`.

`branch` is a **site**-kind signal: it feeds decision-density metrics only
(`_calc_cog_load`, `control_flow_ratio`, `risk_cognitive_load`, per-function
complexity) plus the score-layer proximity views (`spatial_correlation.py`'s
cascading-flux and silencer pairs read branch *positions*). Before this contract
it was the corpus's largest open-defect metric: 11 of 45 comparable cells
(24%) were out of band, every one an instance of the three shapes below.

## Corollaries

**1 · A handler is not a decision.** `catch`/`rescue`/`except`/`finally`/
`ensure`/`trap`, the guarded-region opener (`try`, `@try`, ABAP `TRY.`, ruby
`begin`, swift's do-catch `do`) and the raiser (`throw`) mark where control
*leaves* or *arrives*; the decision was made by the throw. They are `safety`'s
constructs (count contract corollary 4), and 27 of 46 rules counted some of
them while 38 corpus languages proved they shouldn't: a planted try/catch read
branch +1 in cpp (`catch`), ruby (`rescue`), tcl/powershell (`trap`), livecode
(`throw`) and nowhere else. Retired from every rule; where no other rule owned
the token it moved to `structural_boundaries` (kotlin, scala, solidity, swift,
ruby `begin`/`retry`, powershell `throw`).

**2 · One conditional is one hit per arm-opener.** The words that *continue* or
*close* a construct already counted do not count again: `then`/`of` (haskell,
lua, livecode, scala 3), `fi`/`esac`/`done`/loop-body `do` (shell, dockerfile,
yaml), `THEN`/`END` (sqlite), `ENDIF` (jcl, makefile), the shell test brackets
(`[`, `]`, `[[`, `]]` — the conditional's syntax, not a second decision), the
closer's re-match of the opening keyword (ada `end if`, livecode `end repeat`,
fortran `END IF`/`END DO`, cobol `END-IF`/`END-EVALUATE` — all now guarded with
lookbehinds), and a syntax word an already-counted construct mandates (a swift
guard's own `else`; swift's `else` now anchors on `}\s*else`, which is every
real else arm). Arm-openers still count: `else`, `elsif`/`elif`/`elseif`,
`case`/`when`/`WHEN`/`default`/`otherwise`, sqlite's `CASE` and its `ELSE`.
These words moved to `structural_boundaries` (they are boundary vocabulary —
lua and matlab already kept `end` there) except in yaml, whose branch rule
reads embedded shell and whose crucible incidence is zero.

**3 · An unconditional transfer is not a decision.** Decided for `return`
(#2545/#2634) and for assembly's `jmp`/`call`/`ret` (#2764/#2779); `goto` is
the same shape. Removed from c (owned by `reflection_metaprogramming`), csharp
and fortran (owned by `high_risk_execution`), and relocated to
`structural_boundaries` in cpp, go, lua, objective-c, perl, php. ABAP's
`RETURN` — the #2545 shape that rule had kept — went to `structural_boundaries`
the same way. **COBOL's bare `PERFORM <paragraph>` / `PERFORM A THRU B` is the
language's call form, not a branch** (10% of its 21,549 crucible hits); the
loop forms still count, anchored on their condition words
(`UNTIL`/`VARYING`/`TIMES`/`DEPENDING ON`), and `PERFORM` itself moved to
`structural_boundaries` beside COBOL's other straight-line verbs.

**Mirror (safety side).** typescript's `safety` counted `unknown`/`never`/
`void` — compile-time type keywords are not runtime guards (the same
corollary-4 question from the other side). They moved to
`structural_boundaries` beside `type`/`interface`/`declare`.

## Deliberate duals and deferred residue

- **Value-selection operators stay dual.** `?:`/`??`/`orelse`/kotlin `?:` are
  runtime decisions *and* defensive idioms; they count `branch` and may count
  `safety` (typescript `??`, zig `orelse`). This is a stated exception to
  corollary 4, recorded here.
- **The break/continue family is deferred** (`break`, `continue`, perl
  `next`/`last`/`redo`, fortran `EXIT`/`CYCLE`, go `fallthrough`, livecode
  `next repeat`, …) along with the two-keyword loop headers (C-family
  `do…while` counts 2; ada `while … loop` counts 2): **#2832**. Uniform across
  the family today, so no corpus cell reads out of band on them.
- **Measured but out of scope:** ruby's bare `?` (predicate method names),
  java's bare `:` (`::` method references), python's `with`: **#2833**.
- go's `range` rides the `for` it continues (removed, boundaries); fortran's
  `WHILE` only ever follows `DO` (removed, boundaries).

## The 46-language audit

`tests/tools/rule_probe.py branch all` before/after (crucible = incidence on
the language-crucible corpus v1.2.0; rosetta = the planted-cell total across
the four control files, target 3 + 0 + 0 + 0). "—" = no crucible presence.

| language | crucible | rosetta | what changed |
|---|---|---|---|
| abap | 318 → 259 | 3 | TRY/CATCH/CLEANUP (safety's), RETURN (#2545 shape) |
| ada | — | 4 → 3 | `end if`/`end case`/`end loop` re-matches guarded |
| agc_assembly | 398 | 3 | clean since #2779 |
| apex | 23 → 12 | 3 | try/catch/finally |
| assembly | 1213 | 3 | clean since #2779 |
| c | 10093 → 9720 | 3 | goto (reflection owns it) |
| cobol | 21549 → 10087 | 3 | END-IF/END-EVALUATE re-matches; bare PERFORM |
| cpp | 8346 → 8256 | 4 → 3 | catch; goto relocated |
| css | 774 | 3 | clean |
| csharp | 3941 → 3849 | 4 → 3 | try/catch/finally; goto (high_risk owns it) |
| dart | 6809 → 6729 | 3 | try/catch/finally |
| dockerfile | 91 → 88 | 3 | fi/esac/done/do; re-plant added the else arm |
| embedded_python | 772 → 659 | 3 | try/finally |
| fortran | 5457 → 4177 | 4 → 3 | END-rematches guarded; GOTO (high_risk); WHILE rides DO |
| go | 3552 → 3378 | 3 | goto, range relocated |
| groovy | 552 → 533 | 3 | try/catch/finally |
| haskell | 252 → 174 | 3 | then/of; re-plant added a case |
| html | 11 | 3 | clean |
| java | 487 → 428 | 3 | try/catch/finally |
| javascript | 5235 → 5105 | 3 | try/catch/finally |
| jcl | 81 → 52 | 3 | ENDIF; re-plant added a second IF |
| kotlin | 45 | 3 | try/catch/finally relocated |
| livecode | 8329 → 4407 | 5 → 3 | then/while/until/times, throw, end-rematches; re-plant added a repeat |
| lua | 6090 → 4036 | 3 | then/do/until/in/goto; re-plant added a while |
| m4 | 50 | 3 | clean |
| makefile | — | 4 → 3 | endif; recipe-prefix run bounded (ReDoS) |
| matlab | 1078 → 1014 | 3 | try/catch |
| objective-c | 311 | 3 | @try/@catch/@finally; goto relocated |
| perl | 8808 → 8771 | 3 | try/catch/finally/defer; goto relocated |
| php | 6365 → 6240 | 3 | try/catch/finally; goto relocated |
| powershell | 6400 → 5761 | 5 → 3 | try/catch/finally/trap/throw; trap plant body |
| python | 8371 → 8177 | 3 | try/finally |
| ruby | 207 → 205 | 4 → 3 | rescue/ensure; begin/retry relocated |
| rust | 2749 | 3 | already contract-clean |
| scala | 2064 → 1850 | 3 | try/catch/finally/throw/then relocated |
| scheme | 4105 | 3 | clean |
| shell | 9737 → 3502 | 5 → 3 | then/fi/esac/done/do, test brackets; re-plant added else + while |
| solidity | 69 | 3 | try/catch relocated |
| sqlite | 161 → 45 | 5 → 3 | THEN/END relocated; one CASE = CASE + its arms |
| swift | 871 → 781 | 4 → 3 | catch/try/throws/defer/do; else anchored on `}` |
| tcl | 2330 → 2124 | 4 → 3 | catch/try/trap/finally |
| typescript | 14879 → 14751 | 3 | try/catch/finally (+ safety mirror) |
| yacc | 93 | 3 | clean (`\|` is yacc's real alternation decision) |
| yaml | 0 | 3 | fi/esac/do/done; re-plant added the elif arm |
| zig | 25311 → 16340 | 3 | try/catch (zig safety owns both) |

Every rosetta cell above lands on its plant with no residue; the corpus
re-bless (keyword-rosetta, branch `rebless/gitgalaxy-2822-branch`) carries the
manifest moves, the re-plants, the retirement of
`branch-counts-non-decision-keywords`, `typescript-type-keywords-count-as-safety`,
`ada-end-if-branch-inflation` and `shell-test-brackets-in-branch`, and the
edits to `fortran-goto-dual-branch-highrisk` and `batch4-dual-keyword-overlaps`.
