# Pre-registration: fresh public batch estates (#3806), a one-shot COBOL batch → Java attempt

*Status: registered 2026-10-20 before any crawl, draw or target. The crawl ran 2026-10-23 after the owner's approval (section 0); the draw waits for the target rounds on the candidates page. Any change after a target is chosen counts as a deviation and is recorded in the trial entry (`tests/cobol_mainframe/trials.json`), which cites this file's commit.*

This file adapts [`estate4_preregistration.md`](estate4_preregistration.md) (the CICS estate) to **batch**: COBOL programs run from JCL, with copybooks and VSAM / sequential I/O. Sections not restated here (claim under test, frozen state, pipeline, outcome classes, allowed changes, publication) apply unchanged, with "batch program" for "CICS program". The harness channel set is the batch one (stdout, files; see `docs/agents/mainframe.md`).

## 0. Owner decisions
- (a) **Answered 2026-10-23:** the metadata-only draw is approved, with the condition that each drawn estate's licence and tier are recorded before any code is read or anything is published. The candidate list is built and three target rounds are fixed in [`estate_batch_candidates.md`](estate_batch_candidates.md); the draw runs on those rounds. The two-or-three count stays open: three rounds are drawn, the trial uses them in order.
Still pending:
- (b) Does opensourcecobol4j count as a fresh estate or a development estate? Until answered it is **not** a candidate and is not added to the lists.
- (c) Include a private (pilot) estate as the uncontaminated point?
- (d) Licence and publishing hold (Q16).

`tests/tools/estate4_draw.py build --kind batch` refuses to run without `--approved-by-owner`; the flag is set only after (a) is answered.

## 1. Target selection (blind)
- Targets are public COBOL repositories with batch evidence, **not** on the ineligible list (`INELIGIBLE_LIST` / `BURNED_NAMES` in `tests/tools/estate4_draw.py`) and not development data (`estate4_devdata_repos.json`).
- Candidates are chosen from metadata only (name, licence, size, language stats, file names). **Nobody, human or agent, opens a candidate repository's code or README** before the system is frozen; the tool counts only.
- Method: a weighted random draw with a drand round fixed in advance, exactly as for the CICS estate (`seed = sha256(randomness + sha256(candidates file bytes))`). With two or three estates the draw is repeated on successive rounds without replacement. The target round is **not set** until (a) is answered; it is written into the candidates page before the draw.

## 2. Eligibility rules for the candidate list
Rules 1-3 and 5-8 are the CICS rules verbatim (public non-fork, not owned by `squid-protocol` / `jmesquib`; SPDX in {MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, 0BSD, EPL-2.0}; COBOL >= 20,000 bytes; 5-300 COBOL program files; not ineligible; not development data; not a copy of a burned estate). Rule 4 changes:

4. **Batch evidence from file names only:** >= 1 file ending `.jcl`, `.proc` or `.prc` (case-insensitive), or any file under a folder named `jcl`. A repository is not excluded for also holding `.bms` / `.csd` files.

The search pool has the same known limit: only repositories whose GitHub primary language is COBOL.

## 3. Weighting (declared before the draw)
Same as the CICS draw, `weight = 1 + foreign + hard`. `hard` counts JCL as one of its five items, so every batch candidate scores at least 1 there; this is unchanged on purpose so one function serves both kinds.

## 4. Eligibility of programs inside the target
Batch COBOL programs only: those the harness can run as a job step. Out of scope by rule, stated from the scan before any translation: missing source, assembler / PL/I, CICS programs (the CICS estate covers them), and programs needing a resource the harness cannot provide. The eligible list is fixed before translation runs.

## 5. Known limits, stated in advance
- Oracle: GnuCOBOL plus our stub, not z/OS (#4050).
- Public code may be in a model's training data; each published histogram carries that caveat. A private estate (decision c) is the uncontaminated point.
- Weak spots known before the trial are listed by the batch census, not by the trial result.

## 6. What this PR does
It adds the batch kind to the draw tool (`--kind batch`, separate output files, the rule-4 test above, the owner-approval guard) and this file. It does not crawl, list candidates, or draw.
