# Security claims inventory (2026-11-13)

Every security, malware, supply-chain and secrets claim in GitGalaxy's hand-written docs, checked against the code and
tests at `origin/main` `6dfb82682`. The point is to separate what is shown from what is only said, before any new
security work or any external claim.

Scope: README.md, SECURITY.md, github-action-readme.md, the security wiki pages (02-06, 02-20, 04-00, 04-02, 04-03,
04-04, 04-05, 08-19, 08-21, 08-23, index, CLI reference, three cookbooks), gitgalaxy/security/README.md,
gitgalaxy/tools/supply_chain_security/README.md, gitgalaxy/tools/README.md, tests/security_auditing/readme.md, and the
security parts of docs/signals.md, docs/validation.md, docs/signal_coverage_verdicts.md, docs/zero_dependency_mode.md,
docs/vectors.md, docs/vector_formulas.md, docs/known_blind_spots.md and docs/readme_evidence_roadmap.md. Generated
pages (museum-of-code teardowns, per-repo agent pages, LLM reports) are out of scope.

## Tags

| Tag | Meaning |
|---|---|
| MEASURED | An effectiveness number (recall, precision, false-positive rate) from a labelled evaluation on real-world samples, with a committed script or artifact. |
| TESTED | Tests exercise the behaviour on constructed inputs (planted files, fixtures, mocks). Says the code does what it says; says nothing about how often it catches real attacks. |
| UNTESTED | The code implements it; no test exercises the claim. |
| FALSE | The code does not do what the doc says, or the feature never runs. |
| VAGUE | Unfalsifiable or marketing wording ("zero-day detection", "Zero-Trust"). Needs rewording, not testing. |

## Headline

112 claims: **5 MEASURED** (all about whether structural vectors predict defects; none about detection), **44
TESTED**, **10 UNTESTED**, **39 FALSE**, **14 VAGUE**.

- **No security detector has a measured recall, precision or false-positive rate on real-world samples.** Nothing in
  this inventory is MEASURED for detection. `docs/readme_evidence_roadmap.md:36` already says "No labeled ground truth
  exists".
- **The only real-world security measurements are negative, and honest:** per-file structural risk does not predict
  CVEs or defects (temporal-crucible: security-fix structural delta +0.000, 26-signal vector AUC 0.479 vs LOC 0.531,
  nDPI TOST effect 0.000). The removed taint tracker measured about 0% precision and recall (#3101) and the API-near-SQL
  correlation about 0% precision (#3018); those two numbers live only in issues and code comments, with no committed
  artifact.
- **Most detector claims are TESTED**: the #4108 planted-probe series, the TLS-bypass tests (#6239), the sentinel and
  X-Ray control tests, pipeline pins, manifest parser. That is a good base; it is not evidence of catching malware.
- **39 claims are FALSE**, several of them about features that do not run at all (below).

## Most serious problems (fix first)

1. **The XGBoost malware classifier never runs.** `security_auditor.py:72` loads
   `gitgalaxy_malware_xgb_multiclass.json`, which is not in the repo; both golden masters record
   `"Inference Ran": false`. Every test uses a mock or a synthetic stand-in model (`test_ml_real_model_2986.py`: "says
   nothing about detection quality"). Yet 02-20, 04-00 (text and diagram), README (`[full]` extra),
   zero_dependency_mode.md (short version), github-action-readme.md (`full_precision`) and wiki/index.md describe a
   working Trojan/Stealer/Dropper/Botnet classifier. The Action's `full.txt` also lacks scikit-learn, so it could not run
   even with a model. The pipeline template's "ML Malware Gate" job gates on `--fail-on-malware`, which cannot fire.
2. **The standalone `supply-chain-firewall` CLI (and `tool: supply-chain-firewall` in the Action) never blocks on real
   input.** `run_firewall_audit` reads `raw_imports` and `risk_vector` (`supply_chain_firewall.py:125,244`); the audit
   JSON stores them as `"9. Extracted Dependencies"` and `"4. Vulnerability & Risk Exposures"` and drops `risk_vector`
   (`audit_recorder.py:709,811,859`). Reproduced: strict mode with `requests` blacklisted passes with 0 unknown, 0
   threats, exit 0. Its tests feed only the old JSON shape. This repo's own CI pre-gate runs it
   (`.github/workflows/gitgalaxy.yml:92-96`). The engine-internal firewall path works.
3. **Lines of 250+ characters are invisible to every engine security regex**, and no doc or known_blind_spots.md says
   so. `SecurityLens._armor` (`security_lens.py:808-814`) blanks them; `long_lines.chunk_long_lines` is used only by
   Vault Sentinel. Reproduced: an AWS key alone reads `hardcoded_secrets: 1`; on a 300-character line it reads nothing.
   Entropy also scans the armored text, so string literals longer than about 248 characters are never entropy-checked,
   which contradicts "payloads hidden inside massive string literals" (gitgalaxy/security/README.md).
4. **Removed features documented as live:** taint/data-flow analysis (02-06, 08-21, SecurityLens docstrings; removed
   #3101), Obscured Payload Exposure (08-19; `_calc_obscured_payload` no longer exists, removed #1020), agentic-RCE and
   "RCE Funnels" (02-06, wiki/index.md; removed #1020/#1102).
5. **"Shadow patch detection" detects nothing.** `--shadow-patch-detected` is a manual flag; no hash or version is
   compared, yet the alert text says "Hash mutated without version bump!" (`security_auditor.py:191-198`). It labels
   every file with `file_impact > 0.5` a Trojan, and it sits after `if not self.model: return` (`:146`), so it never
   fires.
6. **The firewall's documented scope is mostly fiction.** Its only behavioural input is `secrets_risk`
   (`_FIREWALL_RISK_MAP`, `supply_chain_firewall.py:33-35`), a vector docs/vectors.md marks REWORK. Claims of malware,
   data injection, network calls, I/O hooks, typosquatting, homoglyphs, steganography, tainted I/O and npm install hooks
   are false. `package.json` is skipped by the `.json` shield before the 10x build-script multiplier applies;
   `node_modules`/`venv` are excluded from the scan; manifest-parser flags (insecure registry, ngrok, direct URI) are
   written but never read. It also skips any path containing `/test/`, `/tests/`, `test_` or `_test`, an evasion path
   that is not disclosed.
7. **Privacy statements are too broad.** wiki/index.md:216-218 says source "is never transmitted to any API … or
   third-party LLM" and is processed in "a volatile memory buffer". `tools/cobol_to_java/port_runner.py` can POST source
   to OpenAI-compatible or Anthropic endpoints (opt-in), zips are extracted to an on-disk `mkdtemp`, and scans write
   `<target>/.gitgalaxy/dependency_cache.db`.
8. **Claims that contradict temporal-crucible's own results:** vectors.md:41-43 and validation.md:320-322, :468 say the
   vectors "cleanly"/"reliably" track a security-fix gradient; temporal-crucible's ledger says that gradient collapses at
   patch grain into fix-vs-nonfix (bystander artifact), and the openssl replication is pending. validation.md still
   lists the security-fix experiment as future work while reporting its results on the same page.

Docs that undersell (also wrong): signals.md calls `threat_extension_mismatch` "never set", but the disguised-executable
check (#4126) sets it and is tested; signal_coverage_verdicts.md:39 lists camelCase secret names as missed although :24
and the tests show them fixed. github-action-readme.md:71 says gates do not run on `--incremental` scans; they do
(`galaxyscope.py:4234`, `test_cli_contract.py::test_gates_run_on_an_incremental_scan_and_catch_an_added_secret`).

## A. Engine security lens, ML auditor, exposure pages

| Claim | Where | Tag | Evidence | Fix |
|---|---|---|---|---|
| Lens scans 13 structural threat patterns | 02-06:18; security/README.md:32 | TESTED | 13 keys in `THREAT_SIGNATURES` (`security_lens.py:309-640`); `test_security_lens.py::test_signature_gate_registry_covers_every_signature` | Keep the count; list the real keys |
| The 13 include "memory overrides, and agentic RCE paths" | 02-06:18 | FALSE | No such keys; agentic RCE removed (#1020) | List the real 13 keys |
| Detects prototype poisoning, safety bypasses, eval/dynamic execution, shadow imports, hardcoded secrets | 02-06:15,18; security/README.md:32 | TESTED | `test_security_lens.py::test_sast_vulnerability_signatures`, `test_tls_bypass_*_6239.py`, `test_global_env_mutation_probe_4108.py`, `test_stego_imports_probe_4108.py` | Add "no measured recall" |
| Multilingual secret names (`senha`, `PASSWORT`), compound and JSON-quoted keys, token formats (JWT, `github_pat_`, `glpat-`, `sk-ant-`) | security/README.md:36; signal_coverage_verdicts.md:24 | TESTED | `credential_lexicon.py`; `test_embedded_credentials_probe_4108.py`, `test_embedded_credentials_real_scan_4108.py` | Link the known misses |
| Self-propagation flags a file copying itself | security/README.md:51; signal_coverage_verdicts.md:21 | TESTED | `security_lens.py:615-645`; `test_security_lens.py::test_self_propagation_*`, `test_signal_probes_4108_slice4.py` | — |
| Unicode steganography, zero-width and homoglyph detection | 02-06:15; security/README.md:51; signal_coverage_verdicts.md:16 | TESTED | `test_hidden_text_*_4108.py`, `test_zero_coverage_signals_4108.py::test_planted_file_fires_exactly_its_signal` | — |
| Data-flow taint analysis from untrusted I/O into sinks | 02-06:9,18,39,45; 08-21:39; `security_lens.py:264,820` docstrings | FALSE | Removed #3101 (`security_lens.py:979-980`); column always 0 | Delete; mark the column a retired placeholder |
| `threat_api_near_db_sink` has about 0% precision | 08-21:43-46 | UNTESTED | Number cited only to #3018/#3019; no artifact | Commit the count or cite as issue-reported |
| Threat density "scaled exponentially by network centrality" | 02-06:18,21,23; README.md:5 | FALSE | Lens never reads centrality; only the opt-in firewall applies a linear multiplier (`supply_chain_firewall.py:225-240`) | Scope to the firewall, linear, opt-in |
| Entropy threshold "> 7.9" detects packing | 02-06:34 | FALSE | Strings use 4.8 (`security_lens.py:970`); 7.95 is `scan_binary` (`:1019`), reached only from X-Ray | State 4.8 for strings, 7.95 for binaries in X-Ray |
| Entropy finds payloads in "massive string literals"; "thousands of strings in milliseconds" | security/README.md:20,50 | FALSE | Literal extractor caps at 1024 chars and reads armored text; nothing past ~248 chars is checked; no benchmark | "String literals of 64 to ~248 chars" |
| Entropy skips machine-generated files | 02-06:34 | UNTESTED | `security_lens.py:279-283,962`; the auto-gen test does not assert entropy | Add the assertion |
| "C-level" / "C-optimized" entropy | security/README.md:19-20,50 | VAGUE | Pure Python `Counter` (`security_lens.py:708-720`) | "Single-pass Counter-based entropy" |
| Minification guard (>250 chars) avoids ReDoS | 02-06:38,42 | TESTED | `test_security_lens.py::test_minified_fallback_*`, `test_redos_poison.py` | Say it blanks every long line in every file |
| "Hardware-optimized regular expression engines" | 02-06:42 | FALSE | Stdlib `re` only | "Stdlib regex with literal prefilter gates" |
| Detects zero-days and custom obfuscation that bypasses standard signatures | 02-06:9,15; security/README.md:9,50; 02-20:8,14 | VAGUE | No evaluation set exists | "Flags structural shapes worth review" |
| XGBoost multiclass model predicts Trojans, Stealers, Droppers, Botnets | 02-20:8,11,20,29; tests/security_auditing/readme.md:44 | FALSE | Model not shipped; goldens `"Inference Ran": false` | Lead 02-20 with "no model ships; never runs" |
| ML skipped gracefully without xgboost/pandas; columns NULL, not "Safe" | 02-20:22; security/README.md:34,41 | TESTED | `test_security_auditor.py::test_audit_repository_no_model`, `test_ml_boundary_2986.py` | — |
| Shadow patch: hash mutated without version bump, overrides ML | security/README.md:23,53; 02-20:21; CLI ref:83 | FALSE | Manual flag; no hash/version logic; unreachable without the model | Describe as a manual flag, or implement it |
| Feature vector integrates Gini, signature counts and "global architectural distances" | 02-20:19 | FALSE (partly) | Distances are frozen constants (`security_auditor.py:453-458`, #1159) | Say so |
| Exact transitive upstream/downstream counts, no 500-file cap | 02-20:18; security/README.md:34,52 | TESTED | `test_security_auditor.py::test_dependency_graph_*` | — |
| "Graph BFS capped at 10,000 nodes" | 02-20:48 | FALSE | No BFS; a 50M work budget (`network_risk_sensor.py:186`) | Describe the work budget |
| ML "introduces non-deterministic confidence scores" | 02-20:40 | VAGUE | `predict_proba` is deterministic; error rate is what is unknown | "Probabilistic scores, unmeasured error rate" |
| Over-permissioned agent binding (orchestrator import + IO + low safety), opt-in | security/README.md:16-18,38,41,54 | TESTED | `test_ai_appsec_sensor.py` | — |
| Dev agent firewall: context exhaustion, hallucination risk, state flux, HITL | security/README.md:39,55-56 | TESTED | `test_dev_agent_firewall.py` (state flux: `test_silent_mutation_risk_detection`) | "Summed risk > 200", not "Technical Debt" |
| Context budget check flags "O(N^3) files" | tests/security_auditing/readme.md:31 | FALSE | Only `token_mass > 8000` | "Token mass > 8,000" |
| Pipeline pins flag unpinned installs across YAML, Docker, shell, GitLab | security/README.md:33 | TESTED | `tests/core_engine/test_pipeline_pins.py` | — |
| Manifest parser flags non-standard registries, VCS/file/http refs, ngrok | security/README.md:31 | TESTED | `tests/core_engine/test_manifest_parser.py` | "Prevents" → "flags" |
| Obscured Payload Exposure metric (biaxial mass, sigmoid 15/2) | 08-19:8-129 | FALSE | `_calc_obscured_payload` no longer exists; removed #1020 | Mark REMOVED like 08-21 |
| Hardcoded Secrets Exposure formula (base, amplifiers, LLM x3, sigmoid 3.0/1.0; paranoid 0.5/2.0) | 08-23:28-89 | TESTED | Matches `signal_processor.py:1964-2008`; `test_signal_processor.py::test_signal_processor_*secrets*` | Document the 100.0 override |
| Amplifiers are prints "near" secrets, dead code "containing" keys | 08-23:23-25 | FALSE | Whole-file counts, no proximity | "File-level counts" |
| Risk bands mean env-var retrieval / test secrets | 08-23:92-94 | VAGUE | No such distinction computed | Plain score bands |
| Secrets score pegged to 100 for critical leaks and synthetic artifacts | (undocumented) | UNTESTED by docs | `signal_processor.py:377-380`, `galaxyscope.py:3784-3800`; code tested | Document it |

## B. README, landing pages, GitHub Action, CLI

| Claim | Where | Tag | Evidence | Fix |
|---|---|---|---|---|
| ML threat classification of Trojans; `[full]` enables it; complements Semgrep | 04-00:37-38,46,57,75; README.md:372-373; zero_dependency_mode.md:10,16,65-74,82 | FALSE | Model not shipped (problem 1) | Say no model ships |
| Action runs ML inference with `full_precision` and a supplied model | github-action-readme.md:71,99 | FALSE | No model input; `full.txt` lacks scikit-learn | Drop |
| Gates do not run on `--incremental` scans | github-action-readme.md:71 | FALSE | They do (`galaxyscope.py:4234`; `test_cli_contract.py`) | Delete the sentence |
| `--fail-on-malware` cannot fire without the model | CLI ref:71; zero_dependency_mode.md:71-77,83 | TESTED | `test_ml_boundary_2986.py::test_no_model_scan_reads_unexercised_not_safe` | Also say the template's malware gate is a no-op |
| `--fail-on-secrets` fails on "any" unmitigated hardcoded secret | CLI ref:70,176; github-action-readme.md:71 | TESTED | `test_cli_contract.py::test_a_tripped_gate_exits_1_with_every_report_written`; misses long lines and some config types | "A detected secret"; link blind spots |
| `--max-risk-exposure`; gates off by default | github-action-readme.md:71; CLI ref:66-68,152 | TESTED | `test_cli_contract.py` | — |
| `--max-systemic-threat` | CLI ref:73 | UNTESTED | `test_galaxyscope.py::test_cicd_policy_enforcement_gates` reimplements the logic inline and never calls the gate | Add a CLI-contract test |
| `--paranoid` changes only secrets thresholds | CLI ref:81; github-action-readme.md:103-106 | TESTED | `test_signal_processor.py::..._paranoid_mode_skips_clamp`; log line overstates; `ThreatPolicy` "paranoid" is dead code | Fix the log line |
| `--ai-guardrails` off by default; NULL vs 0 columns | CLI ref:82 | TESTED | `test_record_keeper.py`, `test_galaxyscope.py::test_ai_guardrails_off_by_default` | — |
| AI sensors hunt "RCE Funnels, God-Mode Agents, Context Window Shredders" | wiki/index.md:52 | FALSE | RCE detectors removed | Describe the heuristics plainly |
| Sentinel tools exit 1 and break the build | github-action-readme.md:17,74 | TESTED | `test_vault_sentinel_control.py`, `test_xray_control.py`, `test_supply_chain_firewall.py::test_strict_mode_enforcement` (the firewall CLI part is FALSE, problem 2) | — |
| SARIF output | README.md:40,235 | TESTED | `test_sarif_recorder.py`, golden `sarif.json` | — |
| Per-file vectors show where secrets and unsafe calls concentrate | README.md:224 | TESTED | Goldens, planted probes | — |
| Analysis is "identifying potential vulnerabilities", outputs "vulnerability flags" | 04-00:25,51,58 | MEASURED (negative) | validation.md:309-318: per-file risk does not predict defects | Reword as surface description; cite the result |
| Security analysis across "50+ languages" | 04-00:25,45; github-action-readme.md:7 | FALSE | The lens covers 44 (validation.md:193-194) | Derive the number from code |
| Heuristics allow "zero-day detection" | 04-00:63 | VAGUE | No evaluation | Delete |
| "False positive rates are controlled via allowlists" | 04-00:63,68 | VAGUE | Allowlists exist; no FP rate is measured | "Findings can be suppressed" |
| Reachability comparable to Endor Labs / govulncheck | 04-00:42,45,74 | VAGUE | Call graph exists but is not linked to vulnerable symbols | Drop the comparison |
| Relies on NetworkX | 04-00:51 | FALSE | `test_no_networkx_runtime.py` | "Native graph traversal" |
| Scanner runs offline | README.md:345-349; 04-00:41,48,71 | TESTED | `readiness/offline.py`; `test_assess.py` offline probes; tiktoken download caveat | Note `TIKTOKEN_CACHE_DIR` |
| Source "never transmitted to any API … or third-party LLM"; "entire suite" air-gap ready | wiki/index.md:216-217 | FALSE | `port_runner.py` sends source to LLM endpoints (opt-in) | Scope to the scanner; name the exception |
| "Volatile memory buffer", purged after use | wiki/index.md:218 | FALSE | On-disk `mkdtemp`; cache written into the target | Describe actual behaviour |
| "Zero-Trust" labels | github-action-readme.md:1,5,114; wiki/index.md:21,214 | VAGUE | No defined property | Remove or define |
| Private vulnerability reporting; 48-hour response | SECURITY.md:4-16 | UNTESTED | Reporting is enabled on GitHub; SLA unverifiable | "Aim to respond" |

## C. Supply-chain tools (firewall, Vault Sentinel, X-Ray, SBOM, shadow APIs)

| Claim | Where | Tag | Evidence | Fix |
|---|---|---|---|---|
| Standalone firewall blocks blacklisted/unknown imports and behavioural threats, exit 1 | enforce-supply-chain-firewall.md:39-67; supply_chain_security/README.md:79-98,123-139; 04-03:55 | FALSE | Reads keys the audit JSON lacks (problem 2) | Fix the reader; add an end-to-end test |
| Firewall scans every dependency file inside `node_modules`/`venv` | supply_chain_security/README.md:7,16; enforce…md:10,17 | FALSE | Both are excluded by config (`gitgalaxy_config.py:191,212`) | "Gates the repo's own imports" |
| Firewall flags network requests, typosquatting, I/O hooks, install-time hooks | supply_chain_security/README.md:16,30; tools/README.md:46,72 | FALSE | Gate reads only `secrets_risk`; the engine's typosquat radar only logs | List only what is gated |
| Risk categories "Hidden Malware, Data Injection, Secrets Leak" | 04-03:24 | FALSE | One mapped vector, `secrets_risk` | Name it; link the vectors.md caveat |
| Firewall hunts homoglyphs, shadow-import steganography, tainted I/O | enforce…md:23-28 | FALSE | Never calls SecurityLens; taint removed | Delete the section |
| 10x multiplier on `package.json` hooks and setup scripts trips on any I/O or execution | supply_chain_security/README.md:40; 04-03:27,49 | FALSE | `package.json` skipped by the `.json` shield; npm scripts never parsed; multiplier scales only secrets risk. setup.py/build.rs/*install.js part tested (`test_build_time_execution_multiplier`) | "10x on secrets risk for setup.py, build.rs, *install.js" |
| Audit mode blocks blacklist; strict mode blocks anything not approved | enforce…md:19-20; 04-03:48 | TESTED | `test_supply_chain_firewall.py::test_zero_trust_import_verification`, `::test_strict_mode_enforcement`; logic only | Add a real-scan test |
| Alias dereferencing catches dependency confusion | 04-03:21; supply_chain_security/README.md:41 | TESTED | `test_alias_spoofing_detection`; engine path only, needs a blacklist entry | Say so |
| Manifest flags hand entries to the firewall to block | supply_chain_security/README.md:33,41 | FALSE | Detection tested; nothing reads the flags | Wire them in, or say "logged only" |
| Centrality multiplier | 04-03:28 | TESTED | `test_network_weighting_*`; off by default, undisclosed | Say opt-in |
| "RAM-exclusive, zero disk I/O, sub-second across tens of thousands of dependencies" | supply_chain_security/README.md:39; 04-03:52 | VAGUE | CLI spawns a full scan; no benchmark | Drop scale claims |
| Showcase results (Terraform, tRPC, pwntools) | supply_chain_security/README.md:51,58,79-98 | UNTESTED | No committed command or output; current code would report 0 unknown | Re-run and commit, or remove |
| Sentinel Tier 0 blocks `.pem`, `id_rsa`, `.env` by path | supply_chain_security/README.md:19,32; 04-04:22; deploy-vault-sentinel.md:25 | TESTED | `test_vault_sentinel_control.py::test_a_secret_file_fails_by_its_name_alone`; not zero-I/O | Drop "zero-I/O" |
| Sentinel Tier 1 catches cloud keys, tokens, private keys, passwords | 04-04:9,23; deploy-vault-sentinel.md:6 | TESTED | `test_the_real_detector_fails_ci_on_a_planted_secret` (9 kinds), `test_a_secret_on_a_long_line_fails` | Real-leak eval before effectiveness claims |
| Sentinel catches secrets in commented-out code | supply_chain_security/README.md:19; 04-04:23 | UNTESTED | Raw text is read; no test plants one | Add a case |
| Sentinel uses Shannon entropy | tools/README.md:73; deploy-vault-sentinel.md:14 | FALSE | Reads only `hardcoded_secrets` and `EXTRA_SECRETS`; 04-04:42 itself says no entropy | Remove |
| Sentinel scans `dead_code` too | 04-04:19,41 | FALSE | `restrict_signatures(("hardcoded_secrets",))` | Fix |
| Sentinel outputs the exact secret | deploy-vault-sentinel.md:27,42-43 | FALSE | Code redacts (`vault_sentinel.py:163-165`); no test asserts it | Fix the example; add an assert |
| Allowlist bypasses mock credentials | deploy-vault-sentinel.md:49-53; 04-04:26 | TESTED | `test_sentinel_allowlist_bypass`; default allowlist exempts all `tests/`, undisclosed | Disclose |
| Sentinel "milliseconds" / "thousands of files per second" | supply_chain_security/README.md:18-19; 04-04:15,49 | VAGUE | No artifact | Measure or drop |
| X-Ray flags magic-byte mismatch and embedded executable headers | 04-05:26; supply_chain_security/README.md:22,31 | TESTED | `test_xray_control.py`, `test_disguised_executable_4126.py` | — |
| X-Ray shebang and test-folder exemptions | 04-05:19,27 | TESTED | `test_xray_shebang_shield`, `test_a_real_test_folder_stays_exempt` | — |
| "Entropy > 4.8" flags packed malware | supply_chain_security/README.md:22,31; 04-05:28,49 | FALSE | 4.8 is for string literals; binaries 7.95; dense text runs 5.0; images and archives skip entropy | State each threshold and its scope |
| Reads only the first 8 KB, "O(1) memory", "guarantees" no OOM | supply_chain_security/README.md:42; 04-05:22,48,52,56 | FALSE | Text files up to 5 MB read whole (`_dense_run`); `test_a_large_payload_after_the_first_8_kb_fails` | "8 KB head for binaries; whole text ≤5 MB" |
| Detects steganographic payloads | supply_chain_security/README.md:13; 04-05:9 | FALSE | Images get a header check only | Remove |
| XOR trap: three or more `buf[i] ^= k` | 04-05:29 | TESTED | `test_repeated_indexed_xor_is_flagged_and_named_as_such` | — |
| SBOM `SPOOF_DETECTED` / `UNVERIFIED_MISSING_ON_DISK` | 04-02:22-26 | TESTED | `test_sbom_generator.py` (lens mocked); reads 8 KB per file; any dense 64+ char string marks a package | Rename to "anomaly"; measure FP rate |
| SCA tools "blindly trust" manifests | 04-02:15; supply_chain_security/README.md:5 | VAGUE | No comparison | Reword |
| Blocks compromised packages like xz and colors.js | enforce…md:8,10 | VAGUE | No replay; xz was in build-time test files, not imports | Remove unless replayed |
| Shadow API mapper across 8 frameworks vs Swagger | hunt-shadow-apis.md:14-29 | TESTED | `test_api_network_map.py` | Add known limits |
| tRPC example: three "Ghost APIs" | hunt-shadow-apis.md:50-61 | FALSE | The regex does not read tRPC procedures; these are mapper misses shown as findings | Replace the example |
| "Every Shadow API is a critical security risk" | hunt-shadow-apis.md:8,66 | VAGUE | — | "Each needs review" |

## D. Signals, validation and coverage docs

| Claim | Where | Tag | Evidence | Fix |
|---|---|---|---|---|
| Inference plumbing works; detection quality unproven | zero_dependency_mode.md:81 | TESTED | `test_ml_real_model_2986.py`, `test_ml_boundary_2986.py` | Keep; move it to the short version |
| Rule-based detection unaffected by missing deps | zero_dependency_mode.md:86 | TESTED | zero-dep golden; `test_cli_contract.py` | — |
| `binary_anomaly` / `obfuscation_flag` come from regex signals | zero_dependency_mode.md:84 | TESTED | `record_keeper.py:1859-1897`; `test_record_keeper.py` | — |
| `threat_extension_mismatch` "never set" | signals.md:113,163; `analysis_lens.py:1903` | FALSE (undersells) | Set by #4126 (`galaxyscope.py:781`); tested | "Zero in the population", not "never set" |
| Tainted-injection, prompt-injection, agentic-RCE columns are placeholders | signals.md:115-117,164-166; signal_coverage_verdicts.md:15; vectors.md:572 | TESTED | `security_lens.py:979-980`; `test_surface_families_contract.py` | Say why (about 0% P/R) |
| Security signals are file-level only | signals.md:12-13,103-162 | TESTED | `test_function_level_scope_8012.py` | — |
| TLS-verification bypass across Go, Python, curl, env, Java, .NET, PowerShell, wget | signal_coverage_verdicts.md:20,44 | TESTED | `test_tls_bypass_*_6239.py` | Add "planted samples only" |
| camelCase secret names still missed | signal_coverage_verdicts.md:39 | FALSE (undersells) | Fixed; `test_embedded_credentials_real_scan_4108.py:32-33` | Remove from the gap list |
| Environment mutation (`__proto__`, LD_PRELOAD, NODE_OPTIONS) | signal_coverage_verdicts.md:25,38 | TESTED | `test_global_env_mutation_probe_4108.py` | — |
| Public API near raw DB call | signal_coverage_verdicts.md:28 | TESTED | `test_api_near_db_sink_real_scan_4108.py` | Note the about 0% precision ancestry |
| Bitwise/crypto needs a 4+ operand XOR chain | signal_coverage_verdicts.md:23 | UNTESTED | No near-miss test | Add one |
| Uniform `risk_secrets_risk` across 44 lens languages | validation.md:192-200 | TESTED | keyword-rosetta planted corpus | — |
| `credential_material` is size-correlated and orthogonal to CVEs | vectors.md:390-413; validation.md:202 | MEASURED | temporal-crucible `exposure_history_report.md`, `ndpi_exposure_report.md`; #2979 | Note nDPI fired on 0 rows |
| `credential_material` will become a count-based flag | vectors.md:402-403; vector_formulas.md:40,169-177 | UNTESTED | Still a density sigmoid; stale line refs | "Planned"; fix refs |
| Structural vectors do not predict defects or CVEs | vectors.md:17-44,114-128; validation.md:293-317,372-386,464 | MEASURED | temporal-crucible HYPOTHESES.md (AUC 0.479 vs LOC 0.531; TOST 0.000) | — |
| `guard_balance` moved after curl security fixes, did not replicate on nDPI | vectors.md:140-162 | MEASURED | HYPOTHESES.md (p 0.0072; nDPI p 0.71) | — |
| Vectors "cleanly"/"reliably" track a security-fix gradient | vectors.md:41-43; validation.md:320-322,468 | FALSE | Gradient collapses at patch grain (problem 8) | "Fix vs non-fix separates; security-specific gradient did not hold" |
| Recidivism and change entropy predict CVE/bug files | vectors.md:31-36,427-437; validation.md:323-334 | MEASURED | HYPOTHESES.md; bh_eval.md (AUC 0.868 vs LOC 0.830) | Both are zero in shipped scans (already stated) |
| Security-fix experiment is "future work" / "planned harness" | validation.md:276-282,400-449 | FALSE | Already run (same page :293, :372) | Rewrite as done |
| Signatures cover secrets, injection surface, dynamic execution, entropy, "other characteristics" | validation.md:350-363 | VAGUE | Injection surface removed | Use the concrete signal list |
| Firewall 50.0 cutoff is an uncalibrated sigmoid midpoint | vectors.md:612-622 | TESTED | `test_supply_chain_firewall.py` | — (honest) |
| FP/FN rates are gated on labelled ground truth | readme_evidence_roadmap.md:36 | TESTED (honest) | No labelled security artifact exists | List the security detectors as gated |
| known_blind_spots.md covers the engine's blind spots | known_blind_spots.md | UNTESTED (omission) | Omits the 250-char blind spot (problem 3) | Add it |

## What exists as evidence today

- **Real-world, labelled, negative:** temporal-crucible's exposure studies (curl and nDPI, about 3,550 snapshots,
  preregistered). Structural exposure does not predict CVEs or defects; `credential_material` fired on 6 of 392 curl
  CVE/control files and 0 of 197 on nDPI. Files: temporal-crucible `docs/HYPOTHESES.md`,
  `docs/exposure_history_report.md`, `docs/ndpi_exposure_report.md`, `docs/bh_eval.md`.
- **Numbers with no committed artifact:** taint about 0% precision and recall (#3101); API-near-SQL about 0% precision
  (#3018); `scan_binary()` flagged 10.5% of ordinary denied files (`galaxyscope.py:773`).
- **Golden-master regression, not effectiveness:** the language-crucible golden flags 7 "Secrets Risk" files, 5 of them
  test fixtures, and reads `CRITICAL_THREATS_DETECTED (Rule-Based)` on a benign corpus.
- **Planted and constructed tests:** the #4108 probe series, `test_tls_bypass_*_6239.py`, `test_hidden_text_*_4108.py`,
  `test_disguised_executable_4126.py`, `test_vault_sentinel_control.py`, `test_xray_control.py`,
  `test_pipeline_pins.py`, `test_manifest_parser.py`, and the synthetic-model `test_ml_real_model_2986.py`.

## Next steps

1. **Fix the FALSE claims**, smallest blast radius first: remove or reword the ML classifier, taint, Obscured Payload,
   shadow-patch, privacy and firewall-scope claims. Split into PRs of at most 5 files each.
2. **Code bugs this audit found** (issues, not doc edits): the firewall CLI JSON-key mismatch; the 250-char blind spot
   in the engine security pass; shadow patch unreachable and mislabelled; manifest-parser flags never enforced;
   `package.json` install hooks never read; the tautological `--max-systemic-threat` test.
3. **Then measure.** A labelled benchmark (known malicious npm and PyPI packages plus reconstructions of recent
   incidents, against benign packages and the population corpus), recall and false alarms per layer, GuardDog as the
   comparison, and a test set locked by date so tuning cannot see it. Until that exists, no security doc should claim
   effectiveness.
