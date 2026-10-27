# Fresh batch estates: blind candidate list and draw method

Pre-registration: [`estate_batch_preregistration.md`](estate_batch_preregistration.md) (#3806), adapting [`estate4_preregistration.md`](estate4_preregistration.md).

**Status: candidate list built 2026-10-24T01:21:26Z (metadata only); target rounds fixed below; the draw has NOT run.** Run it on the target rounds, not before.

> **Candidate repos must not be opened by anyone until the trial ends.** This file holds metadata only: no code, no README text. Descriptions are not reproduced here.

## Owner decisions
- 2026-10-23 (answered via Claude): approve the metadata-only draw per the pre-registration. Condition (LLC, commercial use): record each drawn estate's licence and tier BEFORE any code is read or anything is published. Breadth-stage priority.
- Number of estates: the owner left two-or-three open; this page fixes **three rounds** (the trial runs estate 1, then 2, and 3 only if the first two finish).
- "Tier" is read here as the draw-weight tier (`foreign` + `hard`, section 3 of the pre-registration), since it is the only tier metadata the tool holds. If the owner meant another tier, record it at the draw.

## Eligibility rules
Rules 1-3 and 5-8 are the CICS rules in [`estate4_candidates.md`](estate4_candidates.md) verbatim. Rule 4 is replaced:

4. **Batch evidence from file names only:** >= 1 file ending `.jcl`, `.proc` or `.prc` (case-insensitive), or any file under a folder named `jcl`. A repo is not excluded for also holding `.bms` / `.csd` files.

Implementation notes, the weighting formula (`weight = 1 + foreign + hard`) and the known limit (the pool is repos whose GitHub primary language is COBOL) are as on the CICS page. Rule 5/4 counts come from the default-branch git tree (paths only); no tree was truncated.

## Filter stages

| stage | count |
|---|---|
| Search pool: public, non-fork repos GitHub classifies as COBOL (`language:COBOL fork:false`), unique across date shards | 9638 |
| Rule 1: public, non-fork, owner not squid-protocol / jmesquib | 9636 |
| Rule 2 (search metadata): license in the allowed SPDX set | 1582 |
| Rule 2 (confirmed): `/license` SPDX id in set, `/repos` still public and non-fork | 1581 |
| Rule 3: COBOL >= 20,000 bytes | 681 |
| Rule 4 (batch): >= 1 `.jcl` / `.proc` / `.prc` file or a file under a `jcl/` folder | 212 |
| Rule 5: 5-300 COBOL program files | 179 |
| Rule 6: not on the ineligible list | 154 |
| Rule 7: not development data | 154 |
| Rule 8: not a copy of a burned estate | 37 |
| Eligible | 37 |

Total weight: **110** over 37 candidates.

## The draw

- drand chain: League of Entropy default chain, hash `8990e7a9aaed2ffed73dbd7092123d6f289930540d7651336225dc172e51b2ce`, period 30 s, genesis 1595431050; `draw` re-verifies these against `https://api.drand.sh/info`.
- Target time: first round at or after **2026-10-27 12:00:00 UTC**, chosen before the draw and after the list was built.
- **Round 1 = 6589046** (2026-10-27 12:00:00 UTC), **round 2 = 6589047** (12:00:30), **round 3 = 6589048** (12:01:00).
- `seed = sha256(randomness_hex + sha256(estate_batch_candidates.json bytes))`; `index = int(seed, 16) mod total_weight`; walk the sorted list adding weights, the winner is the first repo whose cumulative weight exceeds `index`.
- Without replacement: round 2 is drawn with `--exclude <round 1 winner>`, round 3 with both. The seed always hashes the full committed file; only the walked list shrinks.
  `python tests/tools/estate4_draw.py draw --kind batch --round 6589046`, then `... --round 6589047 --exclude <w1>`, then `... --round 6589048 --exclude <w1> --exclude <w2>`.
- Declared now, before the draw: a winner that is a mirror of an earlier winner (same `COBOL bytes`, `programs` and `jcl` counts as that winner, i.e. the pairs marked below) counts as the same estate and is skipped; the next consecutive round replaces it, with the mirror also excluded. A repo is also skipped, with the reason recorded, if its licence on the draw day is no longer in the allowed set.
- The candidates file hash is fixed by the merged commit of `estate_batch_candidates.json`: `001751e82ac3315cdc1847e327668d2b46cac6e2730ffaf249de7bc698ee0ab0`. Any rebuild before the draw voids the target rounds.

## Draw record (filled in after the target rounds, before any code is read)

| round | winner | commit sha | licence | tier (foreign / hard / weight) |
|---|---|---|---|---|
| 6589046 | pending | | | |
| 6589047 | pending | | | |
| 6589048 | pending | | | |

## Request log

`estate_batch_candidates_requests.json` lists every GitHub request made by `build` (5660 requests: method, URL, status). It contains no content endpoints; `tests/cobol_mainframe/test_estate4_draw.py` fails if any appear.

## Eligible candidates

Mirror pairs (identical counts, noted from the table only): `ibm/idz-utilities` / `ken206can/repo2`; `edge05/sampleapplication` / `vinniet/poly`; `z1ngo1/bob-cobol-modernizer` / `z1ngo1/cobol-practice-tasks`.

| repo | commit sha | licence | COBOL bytes | programs | jcl | bms | csd | foreign | hard | weight |
|---|---|---|---|---|---|---|---|---|---|---|
| aaronnt12/cobol-porfolio | `b8ce680f35f6cacd1e813dfb580b7ec62f8e9d8f` | MIT | 72188 | 38 | 5 | 0 | 0 | 1 | 1 | 3 |
| abdelkarimci/cobol | `de673ba6949f268434fa318d904dc7e03b7a64ea` | MIT | 137756 | 6 | 1 | 0 | 0 | 0 | 1 | 2 |
| aysuoner/cobol-exercices | `27f5d864bec57693017644d1ff9322bd1f5216fd` | MIT | 23359 | 5 | 8 | 0 | 0 | 1 | 1 | 3 |
| billybillymc/masquerade-cobol | `685c484124ffeb1f6a06447c54ed55ea152ec13b` | MIT | 4557921 | 290 | 161 | 31 | 5 | 0 | 4 | 5 |
| dhineshpalanisamy/fintechapp | `1e2e14a64b6df36ddb199575c96ce32199e35783` | Apache-2.0 | 735102 | 41 | 7 | 8 | 0 | 0 | 3 | 4 |
| edge05/sampleapplication | `e7cd4fe84288b3e2c9537a0310ac35a1c9dc25f7` | Apache-2.0 | 77437 | 18 | 20 | 0 | 0 | 0 | 2 | 3 |
| exyme/cobol-loan-management-system-lendwise- | `d6c689ba5d55303437fca8900d0b63ceb007eef5` | MIT | 136360 | 8 | 3 | 0 | 0 | 0 | 1 | 2 |
| fmarqueseti/coboldb2codelab | `900dfc97f714d8933d90c089ab9d38265900a89d` | MIT | 29830 | 6 | 4 | 0 | 0 | 1 | 2 | 4 |
| gadse/openmainframe-cobol-course | `bbe9a64f81cb6735522504b78eeadbecb715d44a` | MIT | 68305 | 16 | 20 | 0 | 0 | 1 | 1 | 3 |
| henryzheng1998/cobol-mainframe-courses | `df116fa60e3956a80c76d42896a7c412dd5d60fc` | MIT | 313735 | 34 | 2 | 5 | 0 | 0 | 1 | 2 |
| hlumelo-tata-ka-itha/pension-fund-system | `15417f168ee3000f89efdef326b39b0d1f1f2647` | MIT | 225973 | 13 | 1 | 0 | 0 | 0 | 1 | 2 |
| ibm/example-health-apis | `9cfe321e2028f4f91a780bbb7d4cbb8393565f76` | Apache-2.0 | 859630 | 58 | 17 | 1 | 0 | 0 | 2 | 3 |
| ibm/idz-utilities | `2bf82cd19a1e640f2f3802d6583de6dd06fd0f6a` | Apache-2.0 | 2166942 | 6 | 4 | 7 | 0 | 0 | 2 | 3 |
| ibm/open-enterprise-sdk-for-apache-kafka | `2664d6e2f1faa8535ebc6916cffb897d2f593575` | Apache-2.0 | 321257 | 26 | 36 | 0 | 0 | 0 | 1 | 2 |
| ikakunn-synthesy/legacy_acct | `b09be45f66a2a83e406b78f3af21f92478eebe3f` | Apache-2.0 | 389495 | 20 | 8 | 0 | 0 | 1 | 1 | 3 |
| itssnowmobile/cobol-enterprise-txn-processor | `5b328496120afbbc3e1bcadf60421598c19db2ea` | MIT | 259352 | 7 | 1 | 0 | 0 | 0 | 1 | 2 |
| jacobdrosol/learn-cobol | `bab2df28855a66378fff67f454bf1b52048a1e3c` | MIT | 22863 | 41 | 46 | 0 | 0 | 0 | 1 | 2 |
| jbansal2/fluxpay | `b11e091fcf18410545890bf1a7ad42c1e12cf51c` | MIT | 1573524 | 115 | 7 | 4 | 0 | 0 | 3 | 4 |
| jdgrillo/ghcp-modernization-labs | `801c5593d0e797bceff5e8c5e237e599984938b5` | MIT | 94519 | 8 | 6 | 2 | 0 | 0 | 2 | 3 |
| jonscobolcrew/destiny-auto-parts | `3e01850e7dafbb84445f843b66cf74a27a0be093` | BSD-3-Clause | 74558 | 16 | 2 | 0 | 0 | 0 | 1 | 2 |
| ken206can/repo2 | `18feee379db486d57e47816429e6d16fa07ae155` | Apache-2.0 | 2166942 | 6 | 4 | 7 | 0 | 0 | 2 | 3 |
| mcohen11/vscode-ispw | `7c17430f61a19c9726a31b4aa846d4633286f796` | MIT | 425283 | 36 | 20 | 0 | 0 | 0 | 3 | 4 |
| mrc6/cobol-check-automation | `d8cf714e21fe3918e2991ba8636644cdb5636828` | MIT | 93790 | 5 | 4 | 0 | 0 | 0 | 1 | 2 |
| phasechangesoftware/cobol-defects-suite | `8a4950ec8b7eaa158f44b2c9139ac70b1111e68a` | MIT | 144079 | 53 | 49 | 0 | 0 | 0 | 2 | 3 |
| pjfarleyiii/aoc2023 | `61f0a75351f7630b8852b94b9902d85ea44f4a05` | MIT | 563612 | 36 | 24 | 0 | 0 | 0 | 1 | 2 |
| rubenasuasoto/ledgerguard-zos | `5493b3c4d763dc9bda3422388c8cd6ec4a972436` | MIT | 69981 | 6 | 5 | 0 | 0 | 1 | 2 | 4 |
| serkutyildirim/cobol-to-java-modernization-skills | `da288cd5c23a51ef63e12029cc8a577e9e6a43d2` | MIT | 24891 | 7 | 3 | 0 | 0 | 0 | 1 | 2 |
| shinyay/code-to-code-workshop-260216 | `54684d569402839a544c0da1b2be8ea854152db0` | MIT | 117106 | 11 | 4 | 0 | 0 | 1 | 1 | 3 |
| siddhi-hi/relief360 | `32f2839e3bc556adf926c468029de51b8873b31c` | MIT | 24255 | 7 | 19 | 0 | 0 | 0 | 1 | 2 |
| steve-kansa/sxk1 | `07d0866f131037fa33e54392776734f78220e819` | MIT | 466957 | 43 | 19 | 0 | 0 | 0 | 1 | 2 |
| strongbacktraining/idz-git-training | `d847aff8cb70bfe3ac8c3598efa53dfe8fbe39d5` | Apache-2.0 | 79334 | 11 | 6 | 1 | 0 | 0 | 2 | 3 |
| tbattiva/reference-bank | `9f7d5f1655afa9ee78af3358a13c4c8761a05774` | MIT | 32136 | 7 | 8 | 1 | 3 | 0 | 1 | 2 |
| vinniet/poly | `4e8a196ad722587a4449d4538177969e52265ae5` | Apache-2.0 | 77437 | 18 | 20 | 0 | 0 | 0 | 2 | 3 |
| ynaka-accenture/raichodemo | `9e9a24c8dfcad6998f0fa98400eb0d4a1b736cee` | Apache-2.0 | 403072 | 42 | 5 | 6 | 0 | 0 | 3 | 4 |
| z1ngo1/bob-cobol-modernizer | `e795a5e05e2e8349c1c08ec974059f5a8fa01b93` | Apache-2.0 | 554127 | 31 | 64 | 0 | 0 | 2 | 2 | 5 |
| z1ngo1/cobol-practice-tasks | `59fe48670169a3455e0ce0bd5d137eab892a0ef8` | Apache-2.0 | 554127 | 31 | 64 | 0 | 0 | 2 | 2 | 5 |
| z1ngo1/release-promo-orchestrator | `a19b783c639fa5ffbc7149d79b5c9f1b7ffebb0c` | Apache-2.0 | 123658 | 5 | 2 | 0 | 0 | 1 | 2 | 4 |
