# Pre-registration: the 4th CICS estate, a one-shot COBOL/CICS → Java attempt

*Status: registered 2026-10-05, before any target was chosen or opened. The ⚖️ decisions below use the recommended options (accepted by the owner). Any change after the target is chosen counts as a deviation and is recorded as one in the trial entry (`tests/cobol_mainframe/trials.json`), which cites this file's commit.*

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
