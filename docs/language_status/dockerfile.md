# Dockerfile — Structural Signature Coverage

## 1. At a glance

| Field | Value |
|---|---|
| Status | `production` |
| Target version | Dockerfile (BuildKit) |
| Last updated | 2026-02-27 |
| Lexical family | `line_exclusive` (Docker uses `#` exclusively for line comments) |
| Rule keys wired | 43 / 52 possible signature keys (9 are `None` — see §4) |
| Extraction-gauntlet tests | 34 (`tests/extraction/languages/test_dockerfile.py`) |
| Strict-signature tests | 86 (`tests/extraction/languages/test_dockerfile_strict.py`) |
| Tri-comparison tool coverage | **None** — one of 5 gg-only languages (abap, dockerfile, jcl, livecode, yaml) with neither a tree-sitter grammar nor `ctags` support; verified via direct manual cross-check instead (§9) |

## 2. Identification surface

- **Extensions:** `.dockerfile`, `.containerfile`
- **Exact matches (extensionless anchors):** `Dockerfile`, `Containerfile`, `Dockerfile.prod`, `Dockerfile.dev`, `Dockerfile.build`, `Dockerfile.test`, `Dockerfile.local`
- **Discriminators:** `docker-compose.yml`/`.yaml`, `.dockerignore`, `compose.yaml` — ecosystem anchors, not required for a Dockerfile itself to be identified
- **Shebangs:** none — Docker uses BuildKit's own `# syntax=` parser directive instead of a shebang line

## 3. What GitGalaxy detects

**Topology / structure**
- `branch` — control flow inside `RUN` shell blocks (`if`/`elif`/`else`/`fi`/`case`/`esac`/`for`/`while`/`do`/`done`/`until`, `&&`, `||`)
- `args` — `ARG` build-argument declarations (file-scoped, not per-instruction — see the args-granularity note in §9)
- `structural_boundaries` — `WORKDIR`/`USER`/`VOLUME`/`STOPSIGNAL`/`SHELL`/`LABEL` (deliberately excludes `FROM`/`RUN`/`CMD` to keep them dedicated to `class_start`/`func_start`)
- `func_start` — `RUN`/`CMD`/`ENTRYPOINT`/`HEALTHCHECK`, the instructions that actually execute logic and generate an image layer
- `class_start` — `FROM`, one per build stage (multi-stage builds treated as a "class wrapper" boundary)

**Risk / structural integrity**
- `safety` — `HEALTHCHECK`, `--chown=`, non-root `USER`, shell crash flags (`set -exuo`)
- `safety_bypasses` — `:latest` tags, `USER root`/`USER 0`, `chmod 777`, `--privileged`, curl/wget-piped-to-shell
- `high_risk_execution` — `rm -rf /`, `eval`, `exec`
- `io` — `COPY`/`ADD`, and shell-level network/package-manager commands (`curl`, `wget`, `apt-get`, `apk`, `yum`, `dnf`, `git clone`, `tar`, `unzip`, `pip install`, `npm install`)
- `api` — `EXPOSE <port>`
- `state_mutation` — `ENV` assignments, shell `export`
- `dead_code` — commented-out Dockerfile instructions
- `doc` — `LABEL maintainer=`/`org.opencontainers.*`/`version=`/`description=`, or `# Description:`/`Usage:`/`Author:`/`Maintainer:` comments
- `test` — test-runner invocations inside a build layer (`npm test`, `pytest`, `go test`, `cargo test`, `make test`, etc.)

**Architecture / domain sensors**
- `concurrency` — trailing `&`, `nohup`/`parallel`, `make -j`/`xargs -P`
- `ui_framework` — GUI/X11/Wayland/GTK/Qt package installs
- `globals` — `ENV` variable declarations
- `scientific` — CUDA/PyTorch/TensorFlow/Jupyter base images
- `reflection_metaprogramming` — `ONBUILD`, BuildKit `--mount=type=cache|secret|bind|ssh`, `--platform=`, heredoc (`<<EOF`) — the "high cognitive load" advanced-BuildKit bucket
- `import` / `_dependency_capture` — base images pulled via `FROM`, and cross-stage `COPY --from=`
- `ownership` — `MAINTAINER`, `LABEL maintainer=`/`org.opencontainers.image.authors=`

**Specialized subsystems**
- `planned_debt` / `fragile_debt` — shared global TODO/FIXME patterns
- `spec_exposure` — `[SPEC-###]`/`[audit]`/`[CVE-YYYY-NNNN]` traceability tags
- `events` — `STOPSIGNAL`
- `dependency_injection` — BuildKit secret/SSH mounts (`--mount=type=secret|ssh`)
- `macros` — BuildKit `# syntax=`/`# escape=` parser directives

**Resource management / stability**
- `telemetry` — `LOG_LEVEL`, `--log-level`, symlinking to `/dev/stdout`
- `debug_prints` — `echo`/`printf`
- `panics_and_aborts` — `exit <nonzero>`, `kill -N`
- `thread_sleeps` — `sleep N`
- `sync_locks` — `flock`
- `immutability_locks` — `@sha256:<64 hex>` digest pins, `--read-only`, `:ro`
- `cleanup` — `apt-get clean`, purging `/var/lib/apt/lists`, `apk cache clean`, `yum clean all`, `npm cache clean`
- `encapsulation` — `FROM ... AS <stage>` (multi-stage build aliasing)
- `listeners` — `EXPOSE <port>`
- `test_skip` — `|| true`, `--passWithNoTests`, `skipTests`, `-Dmaven.test.skip=true`, `--no-audit`

**Dockerfile-specific hybrid sensors** (own phase, added later than the rest of the schema)
- `serialization_parsing` — `ADD`/`COPY` of an archive (`.tar.gz`/`.zip`/`.tgz`/`.tar`), which Docker auto-extracts
- `regex_execution` — shell-delegated `grep`/`sed`/`awk` inside a `RUN`
- `time_date_logic` — `HEALTHCHECK --interval`/`--timeout`, or `sleep` inside a `RUN`
- `ipc_rpc_bridges` — `EXPOSE`/`VOLUME`/`ENTRYPOINT`/`CMD`/`STOPSIGNAL`

## 4. What GitGalaxy explicitly does not track

- `closures` — Dockerfiles are purely declarative; no closures/anonymous-function concept exists.
- `decorators` — not natively applicable.
- `generics` — no type-parameter concept.
- `comprehensions` — no iterator/comprehension concept.
- `ssr_boundaries` — no server-side-rendering concept.
- `pointers` — no pointer/memory-addressing concept.
- `inline_asm` — no bare-metal/inline-assembly concept.
- `explicit_casts` — no type-casting concept.
- `bitwise_ops` — no bitwise-operator concept.

## 5. Known limitations (accepted, not fixed)

None found — `test_dockerfile.py`/`test_dockerfile_strict.py` carry no tests named `known_limitation` as of this writing.

## 6. Test depth

- **Extraction gauntlet** (`tests/extraction/languages/test_dockerfile.py`): 34 cases — valid/invalid/pathological/ReDoS coverage for `func_start`, `class_start`, `args`, and `_dependency_capture`.
- **Strict signatures** (`tests/extraction/languages/test_dockerfile_strict.py`): 86 cases — the remaining structural-signature keys (branch/io/safety/safety_bypasses/etc.) plus ReDoS immunity.
- Both files are already fully migrated to the per-language layout (epic #813) — no gauntlet cases remain in the old monolithic `test_function_extraction.py`-style files for this language.

## 7. Relevant closed work

- **#842 — "Extraction hardening: dockerfile"** (epic #813 sub-issue), closed via **PR #959**.
- **#579 — "Strict parsing tests: `dockerfile` structural signatures"**, closed via **PR #723**.
- Several dated inline comments in `language_standards.py` (Rule 9's shared-`\b`-boundary fix on `high_risk_execution`/`concurrency`/`ui_framework`; the `immutability_locks` bare-digest-vs-`@sha256:` fix; the hybrid-sensor `re.M` fix so `ipc_rpc_bridges`/etc. could fire on real files at all) reflect bug fixes folded into the same hardening passes rather than separate tracked issues.
- **This session (2026-08-20), via the `tri-comparison-ledger-sweep` skill's manual-verification fallback** (dockerfile has no tree-sitter/ctags comparison tool): found and fixed a real function-existence recall bug (dockerfile was silently routed to brace-based body slicing despite having no braces — see §9), and filed two follow-on issues (#1972, #1973) plus a scope-gap issue (#1974) found along the way. No PR number yet at doc-write time — see §9 for the fix detail.

## 8. Real-world evidence (`gitgalaxy-raw-output`)

- [`moby/moby_galaxy_llm.md`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/moby/moby_galaxy_llm.md) — moby/moby (Docker Engine itself): 15 real Dockerfiles, 861 total LOC (0.7% of the repo). Dense, real-world multi-stage builds with heredocs, `--mount=` cache/secret directives, and dozens of build stages per file — the same upstream project this session's own manual-verification corpus (`language-crucible/data/dockerfile/moby/test_targets/`) is drawn from.
- [`kubernetes/kubernetes_galaxy_llm.md`](https://github.com/squid-protocol/gitgalaxy-raw-output/blob/main/v2.4.7/kubernetes/kubernetes_galaxy_llm.md) — kubernetes/kubernetes: 10 Dockerfiles, only 45 total LOC. A useful sparse/small-file contrast to moby's dense set (mostly trivial single-`FROM`/single-`RUN` files).

## 9. Manual verification (no tree-sitter or ctags ground truth exists for this language)

Dockerfile is one of only 5 languages (abap, dockerfile, jcl, livecode, yaml) with neither a
tree-sitter grammar nor `ctags` support, so it can never get a `tri_comparison_ledger.json` entry
— there's no second tool to disagree with GitGalaxy in the first place. Verified instead via the
`tri-comparison-ledger-sweep` skill's dedicated manual-verification procedure: raw regex applied
directly to source text, cross-checked against an independent hand-written grep, AND against the
real pipeline's own DB output (`galaxyscope --db-only`) — the second check is what actually
caught a real bug the first one couldn't see.

**Corpus:** the 4 real Dockerfiles in `language-crucible/data/dockerfile/moby/test_targets/`
(`syscall.Dockerfile`, `generate-files.Dockerfile`, `windows.Dockerfile`, `daemon.Dockerfile` —
1,030 total lines, real production multi-stage builds from moby/moby).

### Results

| Signal | Raw regex vs. independent grep | Raw signal vs. pipeline DB (`struct_*` vs. named list) | Feeds a chart badge? |
|---|---|---|---|
| `func_start` (RUN/CMD/ENTRYPOINT/HEALTHCHECK) | **71/71 exact match**, zero discrepancies | Pre-fix: **15/71** (79% recall loss). Post-fix: **71/71**. | Yes — `manual_verification.json`'s `function` entry, earns the `**`/badge on **Functions Found** |
| `class_start` (FROM) | **77/77 exact match**, zero discrepancies | Raw signal matches exactly (77/77) — but **not** the named list (see caveat below) | **No** — see caveat |
| `args` (ARG, file-scoped) | **73/73 exact match**, zero discrepancies | matches raw signal; no per-function args concept exists for this language (see granularity note) | N/A — `none` granularity, `‡`-marked not badged |

**On the "feeds a chart badge?" column:** `docs/self_scan/tri_comparison_chart.svg`'s "Classes
Found"/"Class Precision" panels read `class_data` (the real named build-stage list) directly via
`tri_comparison_gatherer.gather_language()`, not the raw `struct_class_start` signal this
section's regex/grep check verified — so despite the regex itself being 100% accurate, those two
panels correctly render **empty** for dockerfile today (0 real named classes exist yet, see the
caveat below), and no `manual_verification.json` `"class"` entry was added for it (an earlier
draft of this doc's supporting JSON briefly had one claiming 77/77 "verified" — that was wrong:
it verified the signal, not what those two panels actually measure, and was corrected before
merge). The regex/signal check is still real, useful evidence (it's what backs `structural_mass`,
risk scoring, and the "Classes Found" *signal*-level count elsewhere in the pipeline) — it just
isn't the same claim as "named build-stage extraction is verified correct," which doesn't exist
yet (#1974).

### The func_start bug (found, fixed, and re-verified this session)

The raw `func_start` regex itself was **100% correct in isolation** from the first check — the
bug was entirely in how the real pipeline turned those 71 raw matches into a *named* function
list. Dockerfile has no `ScopeParsingRegistry` entry and no brace-delimited function bodies at
all (a `RUN`/`CMD`/`ENTRYPOINT`/`HEALTHCHECK` instruction's real boundary is simply "ends at the
next instruction"), so it was silently falling through to `Mode_B_Braces` — which only
"succeeded" in producing a named function when a literal `{` happened to appear by *coincidence*
within its bounded search window. In practice that was almost always an unrelated **later**
instruction's `${VAR}` template-substitution brace, not anything belonging to the matched
instruction's own body: `daemon.Dockerfile`'s `RUN` at line 57 was "sliced" using the `{`/`}`
from an unrelated `FROM`'s `${GOLANG_IMAGE}` five lines and one build-stage boundary later, and a
plain `RUN apt-get update && ...` with no nearby brace anywhere was silently dropped from the
named list entirely, despite the raw regex having matched it correctly.

**Fix:** routed `dockerfile` to Mode A (`_slice_by_labels`, the same "greedy to the next
`func_start` match" heuristic already proven for abap/cobol/fortran/assembly — see
`docs/language_status/abap.md` §9 for the identical bug shape there, tracked as #1899). This is a
direct, correct fit: every Dockerfile instruction (including a `RUN <<EOF ... EOF` heredoc body)
really does span exactly from its own keyword to the next `RUN`/`CMD`/`ENTRYPOINT`/`HEALTHCHECK`
match, or EOF.

**Verification chain run:** dockerfile extraction gauntlet + strict tests (120 passed), core
detector tests (141 passed), `ruff_audit.py --ci` / `mypy_audit.py --ci` (clean against baseline),
`crucible_check.py` against the full ~80-repo corpus (confirmed the fix generalizes — a **5th**
real occurrence, `shell/brew/Dockerfile`, embedded in an unrelated repo whose dominant language is
shell, was also corrected, with zero diffs in any other language), both golden master fixtures
re-blessed.

### The class_start caveat (not a bug in the regex — a missing feature, filed separately)

`class_start`'s raw signal (`FROM`) is 100% accurate and always matches the pipeline's own
`struct_class_start` count exactly. But dockerfile is **not** in `detector.py`'s
`_CLASS_START_NAMED_EXTRACTION_LANGS`, so it never gets a real *named* class (build-stage) list —
`class_data` stays completely empty for every Dockerfile scanned despite `file_data.class_count`
reporting a nonzero number. Two distinct issues came out of chasing this down:
- **#1974** — dockerfile has no named build-stage extraction at all (a missing feature: the
  current `class_start` regex's only capture group is the literal keyword `FROM`, not the
  `AS <stage-alias>` name, so implementing this needs a regex change, not just an allowlist
  addition).
- **#1972** — separately, `file_data.class_count` was found to be sourced from the raw signal
  count (`hv[class_idx]`) rather than `len(classes)` (the real named list) in
  `record_keeper.py` — a general bug affecting `class_count`'s accuracy for *every* language, not
  dockerfile-specific, so it's tracked and will be fixed as its own scoped PR rather than bundled
  here.

### Args granularity

Dockerfile's `args` metric is `none` granularity in the `tri-comparison-ledger-sweep` skill's
taxonomy: `func_start` matches `RUN`/`CMD`/`ENTRYPOINT`/`HEALTHCHECK` instruction *keywords*
themselves as pseudo-callables (the same "one comparable schema across every language" reason
non-function-shaped languages get a `func_start` rule at all) — none of these instructions have
anything resembling a formal parameter list. `ARG` is a real, separate, file-scoped build
argument, unrelated to any specific instruction's own "signature." A **secondary** finding came
out of re-verifying the func_start fix: because Mode A's per-function body now legitimately spans
wider (to the next real instruction), the generic per-function args-count derivation in
`_calculate_block_metrics` can spuriously attribute an unrelated `ARG` line that happens to fall
inside that span to the preceding instruction's "parameter count" — filed as **#1973**, a
pre-existing, generic Mode A characteristic (shared by cobol/fortran/assembly too) that was simply
far less visible under dockerfile's old, badly-broken routing. It doesn't affect this section's
function/class *existence* verification, which is unaffected by args attribution.

The regenerated chart's own "Args Found" panel corroborates this independently: a `none`-
granularity language's true args count is 0 by construction (nothing a `RUN`/`CMD`/`ENTRYPOINT`/
`HEALTHCHECK` instruction could legitimately claim as "its own" parameters), yet dockerfile's
post-fix live reading (`LanguageChartData.gg_args_found`, the sum of every named function's own
`args` field) shows **52**, not 0 — visible, independent confirmation that #1973's spurious
ARG-attribution is real and currently live in the pipeline's output, not just a theoretical
concern found by reading code. Expect this number to drop to 0 once #1973 is fixed.

See `docs/self_scan/manual_verification.json`'s `"dockerfile"` entry (`function` only — see the
class caveat above for why there's no `class` entry) for the full evidence trail in the same
format used by abap/agc_assembly, and `docs/self_scan/tri_comparison_chart.svg` for the rendered
`71/71**` **G** badge this verification earns on the **Functions Found** panel.
