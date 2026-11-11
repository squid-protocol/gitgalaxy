# Pre-registration: the 4th CICS estate, a one-shot COBOL/CICS → Java attempt

*Status: registered 2026-10-05, before any target was chosen or opened. The ⚖️ decisions below use the recommended options (accepted by the owner). Any change after the target is chosen counts as a deviation and is recorded as one in the trial entry (`tests/cobol_mainframe/trials.json`), which cites this file's commit.*

## Amendment 1 (owner, 2026-11-07, before the draw)

Made before any target was drawn or opened, so it amends this registration rather than deviating from it.

- **The first trial on the drawn estate is an L1 translation trial.** It measures the share of programs the det
  translator takes whole, with tools only, following the `estate-trial` skill and `.claude/rules/mainframe-evidence-policy.md`
  (rule 2: no cases on an estate that is not burned; rule 3: nobody reads the estate's code).
- The headline is **whole / programs** at first contact, then **whole** and **accounted** (whole + named source defects,
  each with an IBM citation and a review, rule 10) at close-out, 14 days from T0. No claim above L1 is made.
- **The proof claim in sections 1, 4 and 6 below is deferred** to a later phase on the same drawn estate. Running it
  needs an explicit owner exception to rule 2 for that one repository, recorded here as Amendment 2 before it starts.
- **The draw runs only at T0**: after the census preflight passes and main is frozen with its SHA recorded. The drand
  round below is already public, so running `estate4_draw.py draw` earlier would reveal the target.
- Calibration, stated in advance: the 39-program census mock trial (#7709) reached about 20% whole at first contact and
  about 30% whole / 90% accounted after about two days of fleet work.

## Amendment 2 (owner, 2026-11-08): correction of the first blind estate's program count

The first blind estate (`ibm/example-health-apis`, #8073) was counted at T0 as 58 programs. 29 of those were
`.expanded/` compile-listing copies of the real programs (hidden directories, copybooks inlined; PR #8081). The
eligibility in section 5 is *programs*, so the basis is **29**. This corrects the count, not the rules, and both
numbers stay published:
- first contact: **0 of 29** whole (14 of 58 as first reported);
- accounted: 7 of 29 as measured, 1 of 29 in hindsight, because 6 "missing copybook" labels were the engine's
  resolver failing.

The class fix is #8112: listings, expanded copies and duplicates are not programs. The method for corrections is in
[estate_trial_methodology.md](estate_trial_methodology.md).

## Amendment 3 (owner, 2026-11-08): the proof phase on the first blind estate

The owner's exception to rule 2 (`.claude/rules/mainframe-evidence-policy.md`: no cases on an estate that is not
burned) and to rule 3 (nobody reads its code), as Amendment 1 requires, for **one repository only**:
`ibm/example-health-apis` at `9cfe321e2028f4f91a780bbb7d4cbb8393565f76` (Blind 1, #8073), from 2026-11-08.

- **Owner decision (2026-11-08): take `ibm/example-health-apis` to L2.** The exception covers writing cases and reading
  this repository's code, and nothing else: every other non-burned repository stays under rules 2 and 3. Reading the
  code starts only after `trial.py start`, and only as section 7 allows. Until start, rule 3 holds.
- **The L1 result closed before any reading.** First contact (0 of 29 whole) and the close-out on #8073 (25 of 29
  whole, 26 of 29 accounted, at `3b5c59556`) are final. Nothing learned in the proof phase changes them.
- **Sections 3 to 8 apply from `trial.py start`.** Start freezes the system (section 3), declares eligibility from
  the scan alone (section 5), and marks the estate development for good. The first attempt is measured as section 4
  states: the det translator alone is the headline, and det followed by the porting loop is reported beside it.
  Section 7 allows one retry of a model step, and section 8 publishes whatever the result. Rule 3 holds until start;
  after start, section 7 says what is allowed.
- **The program that COPYs the absent `LGCMAREA` member is declared out of scope** at start under the missing-source
  rule (section 5; owner ruling 2026-11-08, #8119). The member is absent from the clone at every path, and no other
  repository's copy is assumed. The ceiling for this estate is 28 of 29.
- **Eligibility code aligned with section 5 before start (#8119).** Until this amendment, `trial.py`'s rules
  described the batch-only harness of 2026-10-05. They put every program with EXEC CICS, EXEC SQL, DL/I or MQ calls
  out of scope, although section 5 scopes "CICS online and batch COBOL" and the harness now has a CICS, Db2, IMS and
  MQ leg. The rules now follow the registered text and the harness: a program is out of scope only if it is not COBOL,
  its source is missing from the repo (a COPY or EXEC SQL INCLUDE member that is neither an estate file nor shipped by
  the translator), it has no output to compare, or it has an input file with no record layout. The change was made
  from the registered text and the harness legs, not from the estate. The only facts used about the estate are tool
  counts: every one of its COBOL files holds EXEC CICS, so the old rules would have declared 0 eligible. The frozen
  harness fingerprint (`HARNESS_PATHS`) now covers the Db2, IMS and MQ legs and their stubs. A `trial.py preview`
  rehearsal with these rules declares 28 of the 29 programs eligible; the other one is out because a copybook is
  missing from the repo.
- **Start is gated (owner, 2026-11-08, #8119).** `trial.py start` runs only after #8076 (the scrubbed EXEC CICS keys,
  including the COMP-1 / COMP-2 DTO slice) is closed and a `cics_census.py survey --blind-root` re-measure shows the
  expected 28 of 29 whole, so the stragglers enter the proof trial translated, not refused. Start is irreversible: it
  marks the estate development for good.
- **Start runs on a main commit** that already holds this change. `fix_commits` counts the fixes made after the
  engine commit, so a branch commit, which the squash merge drops, cannot be the frozen system.
- **Start record (2026-11-09, #8119).** `trial.py start` ran as `trial-001` on main `5e4575d77` (v2.12.0) with
  `claude-sonnet-5-5` via the anthropic backend: 28 programs eligible, 1 out of scope by the missing-source rule. The
  ledger is `tests/cobol_mainframe/trials.json` (#8154). The frozen-system line and the eligible list are posted on
  #8073 (comment 6730880491).

## Amendment 4 (owner, 2026-11-11): the measuring instrument moves, the system under test does not

Recorded before the first porting attempt of the proof phase on `trial-001` (#8322, #8073), and a deviation from section 3,
which froze the harness with the system. No attempt has run. No attempt starts until this amendment is on main.

**Two runs, both reported (owner ruling, 2026-11-11: "keep the frozen harness number too, report both ... I'm happy
reporting that lower number first, that seems more honest").**
- **Run A, reported FIRST: the frozen instrument.** Harness `c58cb3a69` and everything else as frozen at T0.
- **Run B: the frozen system, the instrument at current `main`.** The split below.
- Run A's result is published before Run B's, in the same report, and neither replaces the other.

**The split (Run B).**
- **System under test: frozen, unchanged.** Engine `5e4575d77` (v2.12.0), porting rules hash `23338a4462cb` (ticket v1),
  model `claude-sonnet-5-5` via the `anthropic` backend. This is what the metric measures.
- **Measuring instrument: current `main`.** The equivalence harness and the oracle. Running strictly at the harness
  freeze (`c58cb3a69`) would measure some programs against a reference known to be defective, which is worse than moving it.

**Why the instrument moved.** Six commits touched `HARNESS_PATHS` after `c58cb3a69`. Four were driven by this estate
(`Part of #8121` / `#8230`) and are named and classified here:

| commit | change | class |
|---|---|---|
| `7effbf68c` (#8231) | a `layout_only` COMMAREA's RETURN is read as the bytes it passed (`raw_commarea`) | instrument capability: makes a comparison possible |
| `4bed49868` (#8317) | the facade routes a no-`DFHCOMMAREA` program's raw-bytes re-entry through `runTask` instead of throwing `FacadeRefused` | instrument capability: makes a comparison possible |
| `405a2e658` (#8170) | `ddl_text` ends an in-stream block at any `//` card and filters a JCL-shaped `.txt` | instrument capability: reads the DDL correctly |
| `2c3c7b488` (#8217) | `inline_exec_copies`: a PROCEDURE DIVISION `COPY` member holding `EXEC CICS` / `EXEC SQL` (`HCERRSPD`) is inlined before the SQL precompile and CICS translation | oracle correctness fix |

- None of the four changes what counts as equal. The three capability changes decide whether a comparison can run,
  never who wins it.
- The fourth is the one that decides the configuration. On z/OS, `COPY` expansion happens before the precompiler, so
  inlining is the faithful behaviour (IBM is the reference). Without it the frozen harness compiles some programs
  missing their `EXEC CICS` / `EXEC SQL` statements: the oracle itself is wrong.
- The other two post-freeze `HARNESS_PATHS` commits, `dfa83bf2d` (#8187) and `0386439ea` (#8198), were not driven by
  this estate. They are part of the current-`main` instrument and are listed so the set is complete.
- Section 7 stands. Anything the instrument still cannot judge gets the registered cause `harness`. A fix made during
  the run carries `Trial-Cause: <ticket|generator|engine|harness> <PROGRAM>` and disqualifies that program from first-try.
- No case holds an expected value: the oracle computes every expected result at run time, so a case cannot have been
  tuned to the target. Case revisions after they were added only widened coverage or comparison.

**Run A is not a lower bound on the engine.** `HCERRSPD.cpy` is the estate's only copy member holding `EXEC CICS` /
`EXEC SQL`. Running the harness's own `inline_exec_copies` over each eligible source, the compiled COBOL differs for
**18 of the 28** (64% of the denominator):
`HCAPDB01 HCAPDB02 HCATDB01 HCAVDB01 HCIMDB01 HCIPDB01 HCITDB01 HCIVDB01 HCM1BI01 HCMABA01 HCMADB01 HCMADB02 HCP1BA01
HCP1BI01 HCT1BA01 HCT1BI01 HCV1BA01 HCV1BI01`. Under the frozen harness the reference for these is most likely absent
(untranslated `EXEC` reaches `cobc`, which GnuCOBOL cannot compile), so the expected outcome there is cause `harness`,
not a port verdict.

**Run A is published decomposed, never as a bare rate:**
- proven first try;
- not proven, by genuine cause;
- not judged: cause `harness` (the 18 named above, where the oracle did not compile);
- **flagged: any of the 18 whose oracle compiled anyway.** A wrong reference can make a wrong port pass as readily as
  fail, so these are unsound in both directions and are counted in neither the proven nor the not-proven group.

**Oracle compile status is recorded mechanically, per program, in both runs.** The run writes whether the oracle
(`cobc`) compiled the reference for each program, beside the attempt record, so an oracle failure can never be booked as
a port failure. This is Run A's one real hazard and it must not depend on reading logs afterwards. Precondition: no
attempt of Run A starts until the run records this field (`trial.py` and `port_runner` carry none today; tracked as a
sibling issue of #8322).

**The denominator, restated before any result.** 28 programs eligible.
- `HCP1BU01` is out of scope by the missing-source rule (Amendment 3).
- The three REST wrappers `HCPRESTW`, `HCTRESTW` and `HCMRESTW` have error-path cases only. Their success paths were
  never cased, so they are judged on error paths only. A "proven" for one of them says nothing about its success path.
- The headline stays the det translator alone, with det then the model reported beside it (section 4), published
  whatever the result (section 8). Each is given for Run A first, then Run B.
- n=1: one estate's first-try rate is a data point, not a rate. It is aggregated per engine version across trials.

**Pre-run verification (2026-11-11, before any attempt).** Facts checked on main, recorded so a later drift is visible:
- `porting_rules_hash()` computes `23338a4462cb267476a15711126fc61b5a4f1bd6b5f3bde381ee43b5270af4ed` (ticket v1), the
  frozen value; `cobol_to_java_port_tickets.py` has no diff against the frozen engine `5e4575d77`.
- `declaration_hash` recomputed from the `trial-001` eligible and out-of-scope lists equals the ledger's `declared`
  value (`ffa129cd16a8fe6ba876d61298efc52dd3ca26f11b63a911453c32706ef69560`).
- The frozen engine `5e4575d77` and the frozen harness `c58cb3a69` both exist as commits; the `gitgalaxy-gnucobol:3`
  oracle image is present locally.
- The ledger holds no ticket work directory, so the tickets are regenerated at the frozen engine (never at current
  `main`) before the first `port_runner run`. The oracle compile-status recorder (#8325) lands first.

## 1. Claim under test
GitGalaxy translates a CICS estate it has never seen into Java that is **byte-for-byte equivalent** to the COBOL on the proof scenarios, **in one shot**, i.e. without changing GitGalaxy in response to what the estate contains.

## 2. Target selection (blind)
- The target is a public CICS (COBOL) repository **not** in the excluded list: the burned estates (CardDemo, CBSA, GenApp, zECS, DBB MortgageApplication) and the 9 census-counted repos in `census/INELIGIBLE_FOR_BLIND_ESTATE.md`.
- ⚖️ **How the target is chosen: a random draw from a pre-declared candidate list.** The candidates are public repositories with CICS COBOL, chosen only from metadata (name, license, size, language stats), never from code. The list and the drawing method (e.g. a hash of a future public value) are committed before the draw.
- The repository URL and commit SHA are recorded at trial start. Nobody (human or agent) reads its code before the system is frozen.
- *Public code may be in a model's training data*, as the existing trials page already states. A private estate is the only uncontaminated test.

## 3. What is frozen at trial start
Recorded in the trial entry: the GitGalaxy commit (engine + det translator + generator + harness), the porting rules / tickets version, the model(s) and version(s) for any model-assisted step, the oracle fingerprint (`tests/tools/equivalence_oracle.py`: base image digest, `gnucobol3` package, `cobc --version`), the crucible pins, and the evidence-record policy (`PORTED_UNPROVEN_POLICY = "block"`).

## 4. Pipeline under test
- ⚖️ **Which "one shot": both, reported separately.** The **det translator only** rate (deterministic, reproducible) is the headline. The **det, then the model porting loop for what det refuses** rate is reported alongside. Each program is attributed to the path that produced it.
- Scan → generate → port → prove → evidence record, exactly as the existing tools run it, with the commands listed in the trial entry.
- The estate's harness page (`docs/language_status/trials/<estate>.md`: coverage, run status per program, blockers stated as fixes) is regenerated by `trial.py start`, `sync` and `close` and checked by `trial.py check`, so it is published with the trial, carrying the training-data caveat. `sync` and `close` also take `--case PROGRAM=CASE` and `--proof-blockers FILE`, kept in the trial's `harness` block, so the committed page reports input generation, measured coverage, input limits and untranslated programs like a rehearsal page does (burned-estate cases only; blind-estate code is never read).
  - Page runbook for a fresh estate: `trial.py start` (page with every eligible program "not attempted"), then after each porting-loop run `trial.py sync TRIAL --project DIR [--case PROGRAM=CASE ...] [--proof-blockers FILE]`, then `trial.py close TRIAL --cause PROGRAM=cause ...`; each step rewrites `docs/language_status/trials/<estate>.md`. Commit the ledger and the page together (`trial.py check` fails on a stale page); `generated-docs.yml` publishes them to the `generated` branch from main. Each non-proven program sits under exactly one blocker, sorted by tests unlocked. `test_the_page_of_real_burned_cases_reports_each_program_once_and_the_unlock_counts_add_up` rehearses this on the committed CardDemo cases.

## 5. Eligibility (declared up front, before any result)
- ⚖️ **Scope: CICS online and batch COBOL programs** in the repository.
- Out of scope by rule, not by outcome: programs whose source is missing from the repo, assembler / PL/I programs (the translator is COBOL-only), and programs needing a resource the harness cannot provide (stated per program at trial start, from the scan only).
- The eligible list is fixed before any translation runs. "Out of scope" cannot be used afterwards to hide a failure.

## 6. Outcome classes per program
| class | meaning |
|---|---|
| **proven** | byte-identical on every proof scenario; evidence record "proven" (no `ported_unproven` methods) |
| **refused** | the translator declined by name (an unsupported construct); a visible hole, not a failure of honesty |
| **diverged** | the translation ran but the proof found a difference from the COBOL |
| **failed** | the pipeline crashed or produced no runnable port |
| **not provable** | no scenario could exercise the program with the harness (stated with the reason) |

The headline is the share **proven on the first attempt**. Refusals, divergences and failures are reported with their constructs and causes. **A silent divergence (a wrong port that passed) found later is reported as a correction to the trial, never dropped.**

## 7. What is allowed during the attempt
- ⚖️ **Fixes during the attempt: allowed, but never first-try.** Every attempt after a post-freeze change counts as **not** first-try and carries a `Trial-Cause:` trailer, as `trial.py` already supports. The first-try rate is computed only from attempts on the frozen system.
- ⚖️ **Retries: one retry** of a nondeterministic model step per program, counted and reported. The det path has none.
- ⚖️ **Human involvement:** a person may read refusals and divergences during the trial, **only to file issues**, never to change inputs, scenarios or eligibility.
- Scenario generation follows the existing rules (inputs only; expected results come from running the COBOL oracle); nothing is hand-tuned to the target.

## 8. What gets published
The trial entry in `trials.json` and the regenerated `fresh_estate_trials.md` / `.svg`: per-program outcome, the first-try rate, the causes of every non-first-try attempt, the frozen versions, the oracle fingerprint, and links to the evidence records. Published whatever the result. After the trial, the estate is marked "trialled" and counts as development data from then on.

## 9. Known limits, stated in advance
- The oracle is GnuCOBOL 3.1.2 with an emulated CICS runtime, not IBM Enterprise COBOL on z/OS (#4050 would close this).
- "Proven" means equal on the scenarios run; branch coverage per program is published with each record.
- Expected weak spots, from the 2026-10-05 CICS/SQL census: channels and containers, SEND CONTROL, plain RECEIVE, HANDLE AID, START/RETRIEVE (#4270, #4413-#4415). These are listed *before* the trial, so they can't be explained away after it.
