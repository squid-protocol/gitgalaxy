# Golden-master signal coverage: verdict per zero/thin signal (#4108, item 3)

Question per signal: is its low coverage a **corpus gap** (the rule works, the crucible lacks the construct) or **broken
detection** (the construct is in the crucible or a plant and the rule misses it)? Coverage numbers come from
`python tests/tools/signal_coverage.py report` (3,364 files, #5672); the live floors are in
`tests/signal_coverage_baseline.json`.

| Signal | Coverage now | Verdict | Evidence / action |
|---|---|---|---|
| Hyperlinked Literature References | 34 files | **Healthy**: the #4108 zero is stale | Planted inline links and images fire; reference-style `[a][b]` and autolinks are outside the contract (`lit_links` = inline `[text](target)`). |
| Structured Literature Headers | 110 files | **Healthy**: stale | ATX headings fire; setext (`Title` over `====`) is outside the contract (`lit_headers` = ATX). |
| Feature Flags | retired | **Retired** (#4111, PR #5487) | No key to cover. |
| Architectural Diagrams (Mermaid/PlantUML) | 2 files | **Corpus gap + one real bug, fixed here** | The crucible has `mermaid` fences in only two markdown files and both fire. The rule missed tilde fences (`~~~mermaid`), a space before the info string (```` ``` mermaid````) and brace info strings (```` ```{mermaid} ````); `lit_diagrams` now matches them (`test_markdown_lit_diagrams_fence_variants_4108`). |
| Hardware Bridge | 1 file | **Broken detection (python), fixed here** | `PY_HARDWARE_BRIDGE` named the JS package `serialport` but not python's `serial` (pyserial) or `bleak`; the crucible's `import serial` (`cpp/NVDA/braille.py`) and `from bleak ...` (`homeassistant_ble_integrations`) read 0. Added with near-miss controls; the golden gained both hits (1 -> 3 files, floor raised). |
| Agentic Rce, Prompt Injection, Sec Tainted Injection | 0 | Retired placeholders (#1020, #3101) | Key kept for `SIGNAL_SCHEMA` positions. |
| Invisible Unicode Payload Smuggling, Non-Standard Unicode / Homoglyphs, Sec Extension Mismatch | 0 | Corpus gap, rule proven by planted files | `tests/core_engine/test_zero_coverage_signals_4108.py`. |
| AI Orchestration Frameworks | 3 -> 4 files | **Broken detection (js/ts), fixed here** | `JS_LLM_ORCHESTRATOR` named only langchain/llamaindex, so `nx_util_ai/nx-dev_pages_api_query-ai-handler.ts` (`from 'ai'`, the Vercel AI SDK) read 0. Added `ai`, `@ai-sdk/*`, `@mastra/*`; python gained `langgraph`, `crewai`, `autogen`, `haystack`, `semantic_kernel`, `dspy`, `pydantic_ai`, `smolagents` (the langchain_agents `tool_emulator.py` gains its `from langgraph.types` line). Near-miss controls in `test_ai_ml_import_anchor_4150.py`. |
| Vector Databases (RAG), Cloud LLM API Integrations, Deep Learning, Traditional ML | 3 / 5 / 4 / 4 files | **Healthy, corpus-thin** | Every crucible import of pinecone, openai/anthropic, torch/tensorflow/onnx and sklearn was checked against the golden and fires. More files need a crucible release. |
| Local Inference & Tensor Math | 2 files | **Broken detection (checkpoint extensions), fixed here** | The signal comes only from the aperture's model-weight shunt (`core/model_magic.py`), which sniffed no `.ckpt` (Lightning / stable-diffusion checkpoints are `torch.save` files) or `.hdf5` (Keras). Both now go through the existing header proof, so a non-model `.ckpt` / `.hdf5` still falls through (`test_signal_probes_4108_slice4.py`). |
| Safety & Constraint Bypasses | 4 files | **Broken detection, fixed here** | The rule's own purpose is "disabling TLS verification", yet Go `InsecureSkipVerify: true`, python `ssl._create_unverified_context()` / `CERT_NONE` / `check_hostname = False`, `curl -k` / `--insecure`, shell `NODE_TLS_REJECT_UNAUTHORIZED=0`, `PYTHONHTTPSVERIFY=0`, `verify_ssl = false`, `git config http.sslVerify false` and `CURLOPT_SSL_VERIFYPEER, 0L` read 0. Added with near-miss controls (`curl -K`, `CERT_REQUIRED`, `InsecureSkipVerify: false`). |
| Self-Referential File Copy/Overwrite (Worm Pattern) | 4 files | **Broken detection, fixed here** | The self-reference token list lacked `sys.argv[0]`, `${BASH_SOURCE[0]}` / `$BASH_SOURCE`, PHP `$_SERVER["SCRIPT_FILENAME"]`, and the copy-call list lacked node `fs.copyFile` / `fs.cpSync`, `File/IO.copy_stream` and the paren-less ruby `FileUtils.cp __FILE__, d`. |
| Inline Assembly Blocks | 6 files | **Broken detection, fixed here** (#6249) | C, C++ and objectivec allowed one qualifier only, so `asm volatile goto (`, `asm goto (`, `asm inline (` and objectivec `__asm__ __volatile__ (` read 0; rust missed `naked_asm!` / `llvm_asm!`. The rules now take a bounded chain of `volatile`/`inline`/`goto` qualifiers (and their `__` spellings) and rust matches both macros (`tests/extraction/languages/test_inline_asm_4108.py`, with near-miss and ReDoS controls). The crucible holds none of the new forms, so the golden did not move and the count stays 6. Not fixed: objectivec never matched the MSVC `__asm {` block form. |
| Low-Level Bitwise / Cryptographic Math | 3 files | **Rule-scope question, not changed** | `sec_bitwise_ops` needs a 4+ operand xor chain or a `buf[i] ^= k;` run, so `x = a ^ b ^ c` and `h ^= h >> 16` read 0. Loosening it risks false positives on every hash/shift idiom: needs a contract decision first. |
| The other thin signals (Embedded Credentials, Steganographic Imports, Public API near DB Sink, Global Env Mutation, Instructional Examples, Auth Middleware, System Config Mutation, Vectorized Math) | 7-13 | **Not probed in this slice** | They fire and are floor-guarded; each still needs a per-signal probe like the ones above. |

## Sibling gaps (not fixed here)

* `lit_code_blocks` has the same fence shape gap as `lit_diagrams` (tilde fences, indented list fences not counted).
* The `hardware_bridge` Python list still lacks `smbus`, `spidev`, `RPi.GPIO`, `gpiozero`: contract-eligible peripheral I/O.
* Crucible additions (needs a release and pin bump, `docs/ecosystem.md`): mermaid/plantuml docs in more repos, a
  feature-flagged, RAG and LLM-app service, pyserial/BLE code under `data/python`.
* Safety bypass forms still unread: none known among the TLS-verification set of #6239 (Java trust-all, .NET and PowerShell accept-any callbacks and policies, `-SkipCertificateCheck`, `wget --no-check-certificate`, all read since #6414 / #6531 and this slice).
