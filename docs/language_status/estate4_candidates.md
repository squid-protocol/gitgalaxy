# 4th CICS estate: blind candidate list and draw method

Pre-registration: [`estate4_preregistration.md`](estate4_preregistration.md) (section 2, target selection).

> **Candidate repos must not be opened by anyone until the trial ends.** This file holds metadata only: no code, no README text. Descriptions appear only because the foreign heuristic reads them.

## Eligibility rules (verbatim)

1. Public, `fork == false`, not owned by `squid-protocol` or `jmesquib`.
2. License SPDX id in {MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, 0BSD, EPL-2.0}. No license or anything else means excluded.
3. GitHub language stats: COBOL >= 20,000 bytes.
4. CICS evidence from file names only: >= 1 file ending `.bms` or `.csd` (case-insensitive).
5. 5-300 COBOL program files (`.cbl`, `.cob`, `.cobol`; case-insensitive).
6. Not on the ineligible list (the 5 burned estates: aws-mainframe-modernization-carddemo, cics-banking-sample-application-cbsa, cics-genapp, zecs, dbb / MortgageApplication; plus the 9 census repos in `census/INELIGIBLE_FOR_BLIND_ESTATE.md`).
7. Not development data: exclude any repo that our own corpora were sourced from (`tests/cobol_mainframe/corpora.json`, the language-crucible `SOURCES.md` / `PROVENANCE.json` files, and the CICS / estate crucibles if they cite external sources).
8. Not a copy of a burned estate: exclude if the name or description matches (case-insensitive) `carddemo|genapp|cbsa|zecs|mortgage`, or if >= 30% of its COBOL file basenames match basenames in any burned estate.

Implementation notes (declared, deterministic):
- The search pool is `GET /search/repositories?q=language:COBOL fork:false is:public created:A..B`, sharded by `created:` ranges until each shard had fewer than 1000 results. GitHub's search matches a repo's *primary* language, so a repo whose top language is not COBOL is outside the pool.
- Rule 5/4 counts come from the default-branch git tree (paths only). If GitHub truncated a tree (`tree_truncated` in the JSON), counts are lower bounds.
- Rule 7 input: `estate4_devdata_repos.json` (every GitHub repo cited by our corpora provenance files, deliberately over-inclusive).
- Rule 8 basenames: lowercase file stem of `.cbl/.cob/.cobol/.cpy` files; the fraction is matches / the candidate's such files, against each burned estate separately (`estate4_burned_basenames.json`, names only). A repo named after a burned estate (`dbb`, `zecs`, ...) at any owner is also excluded under rule 6.
- The `default_branch_sha` field is the **root tree SHA** of the default branch. A commit SHA is not available from the allowed endpoints; it is resolved at trial start.

## Weighting (declared before the draw)

`weight = 1 + foreign + hard`.
- `foreign` (0-3): +1 if description/topics contain a non-ASCII letter or `non_english()` is true (>= 2 distinctive words from a small Portuguese/Spanish/French/German/Italian/Dutch/Turkish/Polish word list and more of them than English function words); +1 if any file path has a non-ASCII character; +1 if the owner's profile `location` names a place outside US/UK/Canada/Australia/Ireland/NZ (keyword tables `ANGLO_*` and `FOREIGN_*` in `tests/tools/estate4_draw.py`; empty or unrecognised locations score 0).
- `hard` (0-4): +1 each for JCL (`.jcl` or a `jcl/` folder), PL/I (`.pli`, `.pl1`), assembler (`.asm`, `.mac`, or `.s` under an `asm`/`assembler`/`assembly`/`hlasm` folder), Db2/IMS (`.dcl`, `.sql`, `.dbd`, `.psb`); +1 if COBOL programs >= 50. The brief says 0-4 but lists five +1 terms; all five are applied, so `hard` can reach 5 (owner to confirm).

## Filter stages

| stage | count |
|---|---|
| Search pool: public, non-fork repos GitHub classifies as COBOL (`language:COBOL fork:false`), unique across date shards | 9486 |
| Rule 1: public, non-fork, owner not squid-protocol / jmesquib | 9484 |
| Rule 2 (search metadata): license in the allowed SPDX set | 1548 |
| Rule 2 (confirmed): `/license` SPDX id in set, `/repos` still public and non-fork | 1547 |
| Rule 3: COBOL >= 20,000 bytes | 665 |
| Rule 4: >= 1 `.bms` or `.csd` file name | 173 |
| Rule 5: 5-300 COBOL program files | 163 |
| Rule 6: not on the ineligible list | 139 |
| Rule 7: not development data | 139 |
| Rule 8: not a copy of a burned estate | 17 |
| Eligible | 17 |

Total weight: **44**.

## The draw

Run on the target round, not before: `python tests/tools/estate4_draw.py draw --round R`.

- drand chain: League of Entropy default chain, hash `8990e7a9aaed2ffed73dbd7092123d6f289930540d7651336225dc172e51b2ce`, period 30 s, genesis 1595431050 (`2020-07-22T15:17:30+00:00`); `draw` re-verifies these against `https://api.drand.sh/info`.
- Target time: first round at or after **2026-10-07 12:00:00 UTC**. Round r is published at `genesis + (r-1)*period`.
- **Target round R = 6531446**, published at **2026-10-07 12:00:00 UTC**.
- `seed = sha256(randomness_hex + sha256(estate4_candidates.json bytes))` (hex strings concatenated as ASCII, then hashed); `index = int(seed, 16) mod total_weight`.
- Walk the list below (sorted by lowercase `owner/name`) adding weights; the winner is the first repo whose cumulative weight exceeds `index`.
- The candidates file hash is fixed by the merged commit of `estate4_candidates.json`.

## Request log

`estate4_candidates_requests.json` lists every GitHub request made by `build` (5450 requests: method, URL, status). It contains no content endpoints (`/contents`, `/readme`, `/git/blobs`, `raw.githubusercontent.com`, `/search/code`); `tests/cobol_mainframe/test_estate4_draw.py` fails if any appear.

## Eligible candidates

| repo | tree sha | license | COBOL bytes | programs | bms | csd | foreign | hard | weight |
|---|---|---|---|---|---|---|---|---|---|
| bhbandam/az-legacy-engineering | `4e3df78be3ad` | MIT | 573673 | 30 | 2 | 0 | 0 | 1 | 2 |
| billybillymc/masquerade-cobol | `685c484124ff` | MIT | 4557921 | 290 | 31 | 5 | 0 | 4 | 5 |
| dhineshpalanisamy/fintechapp | `1e2e14a64b6d` | Apache-2.0 | 735102 | 41 | 8 | 0 | 0 | 3 | 4 |
| henryzheng1998/cobol-mainframe-courses | `df116fa60e39` | MIT | 313735 | 34 | 5 | 0 | 0 | 1 | 2 |
| ibm/example-health-apis | `9cfe321e2028` | Apache-2.0 | 859630 | 58 | 1 | 0 | 0 | 2 | 3 |
| ibm/idz-utilities | `2bf82cd19a1e` | Apache-2.0 | 2166942 | 6 | 7 | 0 | 0 | 2 | 3 |
| jdgrillo/ghcp-modernization-labs | `801c5593d0e7` | MIT | 94519 | 8 | 2 | 0 | 0 | 2 | 3 |
| jvcampos-stf/murach-study | `d9e2e532ca96` | MIT | 224169 | 16 | 10 | 0 | 1 | 0 | 2 |
| ken206can/repo2 | `18feee379db4` | Apache-2.0 | 2166942 | 6 | 7 | 0 | 0 | 2 | 3 |
| replatformtech/murachos | `21472620d696` | MIT | 224169 | 16 | 10 | 0 | 0 | 0 | 1 |
| shubham-sn2/zos-connect-and-requester-api | `426abf6ad29b` | Apache-2.0 | 864343 | 8 | 0 | 1 | 0 | 1 | 2 |
| stf-app-test/murach-shopping-list | `39710ba85c39` | MIT | 224169 | 16 | 10 | 0 | 1 | 0 | 2 |
| strongbacktraining/idz-git-training | `d847aff8cb70` | Apache-2.0 | 79334 | 11 | 1 | 0 | 0 | 2 | 3 |
| tbattiva/reference-bank | `9f7d5f1655af` | MIT | 32136 | 7 | 1 | 3 | 0 | 1 | 2 |
| ynaka-accenture/raichodemo | `9e9a24c8dfca` | Apache-2.0 | 403072 | 42 | 6 | 0 | 0 | 3 | 4 |
| zosconnect/sample-cics-api-first | `85fb75dc4748` | Apache-2.0 | 168737 | 10 | 0 | 1 | 0 | 0 | 1 |
| zosconnect/sample-oas3-requester | `6d1053c29454` | Apache-2.0 | 864343 | 8 | 0 | 1 | 0 | 1 | 2 |
