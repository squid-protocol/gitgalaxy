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
- **2026-08-20/21, via the `tri-comparison-ledger-sweep` skill's manual-verification fallback** (dockerfile has no tree-sitter/ctags comparison tool): found and fixed a real function-existence recall bug (dockerfile was silently routed to brace-based body slicing despite having no braces — PR #1976), then found and fixed three follow-on issues surfaced while re-verifying that fix: **#1972** (`file_data.class_count` sourced from the raw signal instead of the real named list — general, cross-language bug, PR #1980), **#1973** (Mode A's per-function args search unbounded, misattributing unrelated later text as a function's own parameter count — PR #1985), and **#1974** (dockerfile had no named class/build-stage extraction at all — PR #1988). All four are merged; see §9 for the full evidence trail.

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
| `class_start` (FROM) | **77/77 exact match**, zero discrepancies | Pre-#1974: raw signal matched (77/77) but `class_data` was always empty. Post-#1974: `class_data` row counts match exactly too (77/77), with real stage names, not the literal string `FROM`. | Yes (as of #1974) — `manual_verification.json`'s `class` entry, earns the `**`/badge on **Classes Found** |
| `args` (ARG, file-scoped) | **73/73 exact match**, zero discrepancies | Pre-#1973: several `RUN`/etc. instructions spuriously showed nonzero per-function args (an unrelated later `ARG` line swept into the greedy body span). Post-#1973: every function correctly shows 0 args. | N/A — `none` granularity, `‡`-marked not badged |

**On the "feeds a chart badge?" column:** `docs/self_scan/tri_comparison_chart.svg`'s "Classes
Found"/"Class Precision" panels read `class_data` (the real named build-stage list) directly via
`tri_comparison_gatherer.gather_language()`, not the raw `struct_class_start` signal. Before #1974,
those two panels correctly rendered **empty** for dockerfile (0 real named classes existed at all,
regardless of the regex's own 100% accuracy) — this doc's own first draft briefly had a `"class"`
manual-verification entry claiming 77/77 "verified" at that point, which was wrong (it verified the
signal, not what those panels actually measure) and was corrected before merge. #1974 closed that
gap for real: `class_data` now genuinely exists and matches, so the `manual_verification.json`
`"class"` entry added afterward is a real, earned claim, not the earlier mistaken one.

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

`class_start`'s raw signal (`FROM`) was always 100% accurate and matched the pipeline's own
`struct_class_start` count exactly. But dockerfile was **not** in `detector.py`'s
`_CLASS_START_NAMED_EXTRACTION_LANGS`, so it never got a real *named* class (build-stage) list —
`class_data` stayed completely empty for every Dockerfile scanned despite `file_data.class_count`
reporting a nonzero number. Two distinct issues came out of chasing this down, **both since fixed**:
- **#1974 (fixed, PR #1988)** — dockerfile had no named build-stage extraction at all. The
  `class_start` regex's only capture group used to be the literal keyword `FROM` itself, not the
  `AS <stage-alias>` name; extended it to an alternation shape (group 1 = alias when `AS` is
  present, group 2 = the bare base-image reference for an unaliased stage — mirroring the existing
  Fortran/Lua/ABAP convention), added `dockerfile` to `_CLASS_START_NAMED_EXTRACTION_LANGS`, and
  added it to the flat (never-nested) boundary-resolution skip alongside `abap`. `class_data` now
  matches `struct_class_start` exactly (77/77) with real stage names, independently re-verified
  against direct source reading — see the Results table above.
- **#1972 (fixed, PR #1980)** — separately, `file_data.class_count` was found to be sourced from
  the raw signal count (`hv[class_idx]`) rather than `len(classes)` (the real named list) in
  `record_keeper.py` — a general bug affecting `class_count`'s accuracy for *every* language, not
  dockerfile-specific, fixed as its own scoped PR.

One known, accepted side effect of #1974's alternation-shaped regex: THE LINEAGE EXTRACTOR (a
different, generic mechanism in `detector.py` that treats any `class_start` match's group 2 as an
inheritance parent) doesn't know groups 1/2 here are alternation-exclusive, not name-then-parent —
a bare `FROM <image>` (no alias) sweeps the image reference into that file's `parent_entity`
metadata. Confirmed pre-existing (fortran's own `class_start` has the identical shape and already
triggers this for bare `TYPE` declarations in production) — tracked separately as #1983, not
blocking.

### Args granularity

Dockerfile's `args` metric is `none` granularity in the `tri-comparison-ledger-sweep` skill's
taxonomy: `func_start` matches `RUN`/`CMD`/`ENTRYPOINT`/`HEALTHCHECK` instruction *keywords*
themselves as pseudo-callables (the same "one comparable schema across every language" reason
non-function-shaped languages get a `func_start` rule at all) — none of these instructions have
anything resembling a formal parameter list. `ARG` is a real, separate, file-scoped build
argument, unrelated to any specific instruction's own "signature." A **secondary** finding came
out of re-verifying the func_start fix: because Mode A's per-function body now legitimately spans
wider (to the next real instruction), the generic per-function args-count derivation in
`_calculate_block_metrics` was spuriously attributing an unrelated `ARG` line that happened to fall
inside that span to the preceding instruction's "parameter count" — filed and **fixed as #1973**
(PR #1985), a pre-existing, generic Mode A characteristic (shared by cobol/fortran, both also
verified clean afterward) that was simply far less visible under dockerfile's old, badly-broken
routing. Fixed via `_mode_a_args_window_end`, which bounds the args search to the matched
instruction's own statement span (following real Dockerfile `\`-continuation and heredoc syntax)
instead of the whole unbounded greedy block.

The chart's own "Args Found" panel corroborates the fix: pre-#1973 it showed **52** for
dockerfile (a `none`-granularity language whose true args count is 0 by construction, since no
`RUN`/`CMD`/`ENTRYPOINT`/`HEALTHCHECK` instruction can legitimately claim "its own" parameters) —
post-fix it correctly reads **0**, independently confirming the fix in the pipeline's own live
output, re-verified directly against the real corpus (`SELECT COUNT(*) FROM function_data WHERE
args > 0` returns 0 across all 4 files).

See `docs/self_scan/manual_verification.json`'s `"dockerfile"` entry (`function` and, as of
#1974, `class` too) for the full evidence trail in the same format used by abap/agc_assembly, and
`docs/self_scan/tri_comparison_chart.svg` for the rendered `71/71**`/`77/77**` **G** badges this
verification earns on both the **Functions Found** and **Classes Found** panels.
