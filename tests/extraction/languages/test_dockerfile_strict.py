"""dockerfile strict structural-signature coverage.

Migrated out of tests/core_engine/test_language_standards_strict.py, then
colocated here in tests/extraction/languages/ alongside the extraction
gauntlets' own test_<lang>.py files (the `_strict` suffix on this filename
avoids a basename collision between the two under pytest's default import
mode). See tests/core_engine/test_language_standards_strict.py's git history
for the original single-file layout and section banners (Issue references, etc).
"""

import sys
from pathlib import Path

import pytest
import re

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune  # noqa: E402 # type: ignore


# ==============================================================================
# DOCKERFILE: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #579, part of epic #518)
# ==============================================================================
DOCKERFILE_RULES = LANGUAGE_DEFINITIONS["dockerfile"]["rules"]

_DOCKERFILE_DEEP_CASES = [
    # --- branch ---
    ("branch", "RUN command1 \\\n && command2", "ENV MY_VAR=iffy"),
    ("branch", "RUN if [ -z \"$foo\" ]; then \\", "RUN echo diff"),
    ("branch", "RUN while true; do sleep 1; done", "LABEL specific=\"value\""),
    ("branch", "RUN command || exit 1", "RUN echo '|'"),
    ("branch", "RUN case \"$1\" in start) ;; esac", "ENV casey=1"),
    
    # --- args ---
    ("args", "ARG VERSION=latest", "ENV ARG=1"),
    ("args", "ARG \\\n NAME=value", "RUN echo ARG"),
    ("args", "  arg   foo", "ARG"),  # ARG with no name is invalid/should not match
    ("args", "ARG\t_my_arg", "ARGH=1"),
    ("args", "ARG\\\nNAME", "RUN ARG=1"),
    
    # --- func_start ---
    ("func_start", "CMD[\"executable\"]", "FROM ubuntu"),
    ("func_start", "RUN\\\n apt-get update", "RUNNING_CMD=yes"),
    ("func_start", "ENTRYPOINT \\\n [\"/bin/sh\"]", "# RUN apt-get"),
    ("func_start", "HEALTHCHECK --interval=5m CMD curl", "RUN=foo"),
    ("func_start", "  cMd [\"executable\"]", "FROM\\\nubuntu"),
    
    # --- class_start ---
    ("class_start", "FROM ubuntu", "FROM_IMAGE=ubuntu"),
    ("class_start", "FROM \\\n ubuntu", "RUN echo FROM"),
    ("class_start", "FROM\\\nscratch", "# FROM ubuntu"),
    ("class_start", "  from   ubuntu", "FROM"),
    ("class_start", "FROM --platform=linux/amd64 ubuntu", "ENFROM=1"),
    
    # --- structural_boundaries ---
    ("structural_boundaries", "WORKDIR /app", "RUN echo WORKDIR"),
    ("structural_boundaries", "USER root", "CMD [\"USER\", \"root\"]"),
    ("structural_boundaries", "VOLUME [\"/data\"]", "ENV VOLUME=1"),
    ("structural_boundaries", "STOPSIGNAL SIGKILL", "RUN STOPSIGNAL=1"),
    ("structural_boundaries", "SHELL [\"/bin/bash\"]", "RUN SHELL=1"),
    ("structural_boundaries", "LABEL version=\"1.0\"", "RUN LABEL=1"),
]


_DOCKERFILE_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    # --- PHASE 1 ---
    ("branch", "RUN if [ -f file ]; then echo hi; fi", "RUN echo hello"),
    ("args", "ARG VERSION=1.0", "ENV VERSION=1.0"),
    ("structural_boundaries", "WORKDIR /app", "RUN echo hi"),
    ("func_start", "RUN echo hi", "FROM python:3.12"),
    ("class_start", "FROM python:3.12", "RUN echo hi"),
    # --- PHASE 2 ---
    ("safety", "USER appuser", "USER root"),
    ("safety_bypasses", "FROM node:latest", "FROM node:18-alpine"),
    ("high_risk_execution", "RUN rm -rf /", "RUN rm -rf /app/tmp"),
    ("io", "COPY . .", "WORKDIR /app"),
    ("api", "EXPOSE 8080", "WORKDIR /app"),
    ("state_mutation", "ENV NODE_ENV production", "ARG NODE_ENV"),
    ("dead_code", "# RUN old-command", "# just a note"),
    ("doc", 'LABEL maintainer="dev@example.com"', "LABEL env=prod"),
    ("test", "RUN pytest tests/", "RUN echo done"),
    # --- PHASE 3 ---
    ("concurrency", "RUN make -j4", "RUN echo hi"),
    ("ui_framework", "RUN apt-get install -y xvfb", "RUN apt-get install -y curl"),
    ("globals", "ENV APP_HOME /app", "ARG APP_HOME"),
    ("scientific", "FROM nvidia/cuda:12.0-base", "FROM python:3.12"),
    (
        "reflection_metaprogramming",
        "RUN --mount=type=cache,target=/root/.cache pip install -r requirements.txt",
        "RUN pip install -r requirements.txt",
    ),
    ("import", "FROM golang:1.22 AS builder", "RUN go build ."),
    ("ownership", "MAINTAINER Jane Doe <jane@example.com>", "LABEL version=1.0"),
    # --- PHASE 4 ---
    ("planned_debt", "# TODO: fix this later", "# just a note"),
    ("fragile_debt", "# HACK: workaround", "# clean"),
    ("spec_exposure", "# [SPEC-123] compliance tag", "# just a note"),
    ("events", "STOPSIGNAL SIGTERM", 'CMD ["nginx"]'),
    (
        "dependency_injection",
        "RUN --mount=type=secret,id=mysecret cat /run/secrets/mysecret",
        "RUN --mount=type=cache,target=/cache pip install foo",
    ),
    ("macros", "# syntax=docker/dockerfile:1", "# just a comment"),
    ("memory_alloc", 'ENV JAVA_OPTS="-Xmx512m"', "ENV APP_ENV=production"),
    # --- PHASE 5 ---
    ("telemetry", "ENV LOG_LEVEL=info", "ENV APP_ENV=production"),
    ("debug_prints", "RUN echo Building...", "RUN true"),
    ("panics_and_aborts", "RUN test -f file || exit 1", "RUN exit 0"),
    ("thread_sleeps", "RUN sleep 5", "RUN date"),
    ("sync_locks", "RUN flock /var/lock/mylock.lock echo done", "RUN echo done"),
    ("immutability_locks", "FROM alpine@sha256:" + "a" * 64, "FROM node:latest"),
    ("cleanup", "RUN apt-get clean", "RUN apt-get update"),
    ("encapsulation", "FROM golang:1.22 AS builder", "FROM golang:1.22"),
    ("listeners", "EXPOSE 443", "WORKDIR /app"),
    ("test_skip", "RUN npm test || true", "RUN npm test"),
    # --- HYBRID ---
    ("serialization_parsing", "ADD archive.tar.gz /opt/", "COPY . ."),
    ("regex_execution", "RUN grep -r TODO .", "RUN echo done"),
    (
        "time_date_logic",
        "HEALTHCHECK --interval=30s CMD curl -f http://localhost/",
        "HEALTHCHECK CMD curl -f http://localhost/",
    ),
    ("ipc_rpc_bridges", "EXPOSE 8080", "WORKDIR /app"),
]


@pytest.mark.parametrize("signature,positive,negative", _DOCKERFILE_SIMPLE_CASES + _DOCKERFILE_DEEP_CASES)
def test_dockerfile_signature_positive_and_negative(signature, positive, negative):
    pattern = DOCKERFILE_RULES[signature]
    assert pattern is not None, f"dockerfile's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"dockerfile {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"dockerfile {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_dockerfile_dependency_capture_extracts_base_image_and_build_stage():
    """
    `_dependency_capture` is the capture-group sibling of `import`, used by
    the Network Graph / Supply Chain Firewall to extract the exact base
    image (group 1, from `FROM`) or build-stage name (group 2, from
    `COPY --from=`) rather than just detecting presence. Covers plain
    `FROM`, `FROM` with a BuildKit flag (`--platform=`) before the image,
    and `--from=` referencing an earlier stage.
    """
    pattern = DOCKERFILE_RULES["_dependency_capture"]
    m = pattern.search("FROM python:3.12-slim")
    assert m and m.group(1) == "python:3.12-slim"

    m2 = pattern.search("FROM --platform=linux/amd64 golang:1.22 AS builder")
    assert m2 and m2.group(1) == "golang:1.22"

    m3 = pattern.search("COPY --from=builder /app/bin /usr/local/bin")
    assert m3 and m3.group(2) == "builder"


def test_dockerfile_dead_code_single_comment_style_confirmed_no_second_style():
    """
    Comment-style audit (Rule 12): dockerfile's lexical_family is
    `line_exclusive` -- Docker natively uses `#` exclusively for line-level
    comments and parser directives, with no block-comment delimiter to wire
    up in parallel. Unlike a `standard_block` language (which must cover
    both `//` and `/* */`), there is no second comment style for
    `dead_code` to silently miss. This test documents that the check was
    performed, not skipped.
    """
    pattern = DOCKERFILE_RULES["dead_code"]
    assert pattern.search("# RUN old-build-step")
    assert pattern.search("    # COPY old-file /app")
    assert pattern.search("# FROM ubuntu:20.04")


def test_dockerfile_lexical_family_no_block_terminator_state_to_confuse():
    """
    Lexical-family audit: because dockerfile is `line_exclusive` (no block
    comment delimiters at all), none of its structural regexes track
    open/close block-comment state -- every keyword-presence rule matches
    via flat line-anchored scanning, not depth-tracking. Docker's one real
    multi-line construct is BuildKit's `<<EOF ... EOF` heredoc (mapped to
    `reflection_metaprogramming`); since the engine performs no
    special-casing of heredoc bodies either, a stray instruction-shaped
    line or a bare `EOF` closing token inside one is scanned exactly the
    same as anywhere else in the file -- there is no block-state tracker
    for it to fool.
    """
    func_start = DOCKERFILE_RULES["func_start"]
    heredoc_with_stray_run = "RUN <<EOF\nRUN this-is-just-text-inside-the-heredoc-body\nEOF\necho done\n"
    matches = [m.group(1) for m in func_start.finditer(heredoc_with_stray_run)]
    assert matches.count("RUN") == 2, (
        "func_start should see both the real RUN <<EOF opener and the stray RUN-shaped line "
        "inside the heredoc body -- there is no block-state tracker for it to be fooled by"
    )


def test_dockerfile_hybrid_sensors_missing_multiline_flag_regression():
    """
    Regression test for the most severe bug found in this sweep: all four
    Hybrid Domain Sensor rules (`serialization_parsing`, `regex_execution`,
    `time_date_logic`, `ipc_rpc_bridges`) were compiled with only the
    inline `(?i)` flag, never `re.M`. Under Python's `re`, `^` without
    MULTILINE anchors to the true start of the *whole* string, not the
    start of each line -- so on any real multi-instruction Dockerfile
    (where `FROM` is always the literal first line), every one of these
    four sensors could only ever fire if its own instruction happened to be
    the literal first line of the file. For `ipc_rpc_bridges`
    (EXPOSE/VOLUME/ENTRYPOINT/CMD/STOPSIGNAL) that is a structural
    impossibility in any valid Dockerfile, since `FROM` must always precede
    them -- meaning it could never fire on any real file at all. Confirmed
    directly (per the issue) against the actual old compiled patterns
    before writing this test: all four had `.flags == 34`
    (IGNORECASE|UNICODE, no MULTILINE) and all four failed to match a
    normal multi-instruction Dockerfile.
    """
    old_serialization_parsing = re.compile(r"(?i)^(?:ADD|COPY)\s+.*\.(?:tar\.gz|zip|tgz|tar)\b")
    old_regex_execution = re.compile(r"(?i)^RUN\s+.*(?:grep|sed|awk)\b")
    old_time_date_logic = re.compile(r"(?i)^(?:HEALTHCHECK.*(?:--interval|--timeout)|RUN\s+.*sleep)\b")
    old_ipc_rpc_bridges = re.compile(r"(?i)^(?:EXPOSE|VOLUME|ENTRYPOINT|CMD|STOPSIGNAL)\b")

    normal_dockerfile = (
        "FROM python:3.12\n"
        "WORKDIR /app\n"
        "ADD app.tar.gz /app\n"
        "HEALTHCHECK --interval=30s CMD curl -f http://localhost/ || exit 1\n"
        "RUN grep -q foo bar.txt\n"
        "EXPOSE 8080\n"
        'CMD ["python", "app.py"]\n'
    )

    # Sanity check: bug must reproduce against the old (re.M-less) patterns.
    assert old_serialization_parsing.flags == 34, "sanity check: old pattern had no re.M"
    assert not old_serialization_parsing.search(normal_dockerfile)
    assert not old_regex_execution.search(normal_dockerfile)
    assert not old_time_date_logic.search(normal_dockerfile)
    assert not old_ipc_rpc_bridges.search(normal_dockerfile), (
        "sanity check: old ipc_rpc_bridges must reproduce the 'can never fire on a real "
        "Dockerfile' bug, since EXPOSE/CMD always come after the mandatory first-line FROM"
    )

    # The fixed patterns all carry re.M and correctly see past the first line.
    for key in ("serialization_parsing", "regex_execution", "time_date_logic", "ipc_rpc_bridges"):
        pattern = DOCKERFILE_RULES[key]
        assert pattern.flags & re.MULTILINE, f"dockerfile {key!r} is still missing re.M"
        assert pattern.search(normal_dockerfile), f"dockerfile {key!r} still fails to match a normal Dockerfile"


def test_dockerfile_hybrid_sensors_continuation_crossing_regression():
    """
    Regression test for a second real bug in the same three body-scanning
    Hybrid sensors (`serialization_parsing`, `regex_execution`,
    `time_date_logic`'s RUN branch), found while checking the issue's
    explicit callout to verify `\\`-continued multi-line RUN instructions:
    Python's `.` never matches `\\n` (no DOTALL), so even after adding
    re.M, the old `.*` body-scan only ever looked at the first physical
    line after the instruction keyword. A classic multi-line `RUN a && \\`
    / `    b && \\` / `    grep ...` chain -- extremely common in real
    Dockerfiles for apt/apk package chains -- silently hid any
    grep/sed/awk/sleep/archive-extension keyword that landed on a
    continuation line rather than the first one.

    Fixed with a bounded continuation-crossing body scan
    (`[^\\n]*(?:\\\\\\r?\\n[^\\n]*){0,50}`, capped at 50 continued lines) that
    still sees across a `\\`-continued instruction while remaining
    ReDoS-safe (verified separately). Must NOT bleed into a *different*,
    non-continued instruction on a later line.
    """
    old_regex_execution = re.compile(r"(?im)^RUN\s+.*(?:grep|sed|awk)\b")
    old_time_date_logic = re.compile(r"(?im)^(?:HEALTHCHECK.*(?:--interval|--timeout)|RUN\s+.*sleep)\b")
    old_serialization_parsing = re.compile(r"(?im)^(?:ADD|COPY)\s+.*\.(?:tar\.gz|zip|tgz|tar)\b")

    multiline_run_grep = "RUN apt-get update && \\\n    apt-get install -y curl && \\\n    grep foo bar\n"
    assert not old_regex_execution.search(multiline_run_grep), "sanity check: bug must reproduce against old pattern"
    regex_execution = DOCKERFILE_RULES["regex_execution"]
    assert regex_execution.search(multiline_run_grep), "should see grep across a backslash continuation"

    multiline_run_sleep = "RUN echo start && \\\n    sleep 5 && \\\n    echo done\n"
    assert not old_time_date_logic.search(multiline_run_sleep), "sanity check: bug must reproduce against old pattern"
    time_date_logic = DOCKERFILE_RULES["time_date_logic"]
    assert time_date_logic.search(multiline_run_sleep), "should see sleep across a backslash continuation"

    multiline_add = "ADD \\\n    app.tar.gz /app\n"
    assert not old_serialization_parsing.search(multiline_add), "sanity check: bug must reproduce against old pattern"
    serialization_parsing = DOCKERFILE_RULES["serialization_parsing"]
    assert serialization_parsing.search(multiline_add), "should see the archive extension across continuation"

    # Must not bleed into a later, unrelated, non-continued instruction.
    no_bleed = "RUN echo hi\nCOPY grep_tool /usr/bin/grep\n"
    assert not regex_execution.search(no_bleed), "must not bleed grep from a later, non-continued COPY line"

    only_first_run_no_sleep = "RUN echo hi\n"
    assert not time_date_logic.search(only_first_run_no_sleep)

    # Same-line (non-continued) forms must still work exactly as before.
    assert regex_execution.search("RUN grep -q foo bar.txt")
    assert time_date_logic.search("RUN sleep 5")
    assert time_date_logic.search("HEALTHCHECK --interval=30s CMD curl -f http://x")
    assert serialization_parsing.search("ADD app.tar.gz /app")


def test_dockerfile_hybrid_sensors_continuation_redos_immunity():
    """
    ReDoS immunity for the Rule 5 bound (`{0,50}`) added by the
    continuation-crossing fix above. Confirmed via direct scaling
    measurement before writing this test, on `regex_execution` against two
    adversarial shapes with no keyword anywhere:

    1. A single huge physical line (`"RUN " + "x" * n`, no newline at all):
       n=2000/4000/8000/16000/32000 -> 0.000198s/0.000374s/0.000754s/
       0.001496s/0.002998s -- a clean ~2x per doubling (linear), because
       `[^\\n]*` followed by a required literal has no adjacent quantifier
       to backtrack against.
    2. Many real backslash-continued lines, well past the `{0,50}` cap
       (`"RUN " + "a && \\\\\\n" * n`): n=2000/4000/8000/16000/32000 ->
       0.000154s/0.000256s/0.000480s/0.000941s/0.001827s -- also a clean
       ~2x per doubling, confirming the numeric clamp bounds the outer
       repetition without the pattern degrading on inputs far larger than
       the cap.

    An earlier draft of this fix (`(?:[ \\t]*\\\\\\r?\\n|[^\\n])*` -- a
    single alternation-based repeat instead of two separately-bounded
    pieces) was tried and rejected during investigation: it hung
    (>120s) on the very first measurement at n=500, because `[ \\t]*`
    nested inside the alternation created the classic ambiguous-tiling
    ReDoS shape (many ways to partition a run of spaces between the two
    alternatives). The shipped fix avoids that by keeping the per-line
    scan (`[^\\n]*`) and the continuation-detector (`\\\\\\r?\\n`) as two
    non-overlapping, separately-quantified pieces instead.
    """
    regex_execution = DOCKERFILE_RULES["regex_execution"]
    serialization_parsing = DOCKERFILE_RULES["serialization_parsing"]
    time_date_logic = DOCKERFILE_RULES["time_date_logic"]

    assert_redos_immune(regex_execution, "RUN " + "x" * 100000, timeout_sec=3.0)
    assert_redos_immune(regex_execution, "RUN " + ("a && \\\n" * 20000), timeout_sec=3.0)
    assert_redos_immune(regex_execution, "RUN " + ("\\" * 50000), timeout_sec=3.0)
    assert_redos_immune(serialization_parsing, "ADD " + "x" * 100000, timeout_sec=3.0)
    assert_redos_immune(time_date_logic, "RUN " + "x" * 100000, timeout_sec=3.0)
    assert_redos_immune(time_date_logic, "HEALTHCHECK " + "x" * 100000, timeout_sec=3.0)

    assert regex_execution.search("RUN grep -q foo bar.txt")


def test_dockerfile_immutability_locks_sha256_prefix_regression():
    """
    Regression test for a real bug: `immutability_locks`' digest-pinning
    alternative required a bare `@` followed directly by 64 hex chars
    (`@[a-f0-9]{64}\\b`), but that is not valid Docker/OCI digest syntax at
    all -- a real pinned image reference is *always* written with the
    algorithm prefix, `@sha256:<64 hex chars>` (e.g.
    `alpine@sha256:e4355b...`). The old pattern could therefore never match
    a real digest-pinned image reference, while it WOULD incorrectly match
    the fictional bare-hex form that no real Dockerfile ever produces.
    """
    old_pattern = re.compile(r"@[a-f0-9]{64}\b|--read-only|:ro\b", re.I)
    hex64 = "e4355b66995c96b4b468159fc5c7e3540fcef961189ca13fee877798dc17daab"
    assert len(hex64) == 64

    real_pin = f"FROM alpine@sha256:{hex64}"
    unrealistic_pin = f"FROM alpine@{hex64}"

    assert not old_pattern.search(real_pin), "sanity check: bug must reproduce against the old pattern"
    assert old_pattern.search(unrealistic_pin), "sanity check: old pattern matched the fictional bare-hex form"

    pattern = DOCKERFILE_RULES["immutability_locks"]
    assert pattern.search(real_pin), "real Docker digest pin (with sha256: prefix) still didn't match"
    assert not pattern.search(unrealistic_pin), "fictional bare-hex form should no longer match"

    # COPY --from= with a real digest reference also works.
    copy_digest = f"COPY --from=alpine@sha256:{hex64} /x /y"
    assert pattern.search(copy_digest)

    # Non-digest forms are unaffected.
    assert pattern.search("--read-only")
    assert pattern.search("- data:/data:ro")
    assert not pattern.search("FROM myimage:robot"), ":ro should not match inside 'robot' (word boundary)"


def test_dockerfile_high_risk_execution_rm_rf_root_regression():
    """
    Regression test for a real bug, and arguably the most severe
    correctness bug in this sweep given what it's meant to detect: the
    `rm -rf /` alternative inside `high_risk_execution` ends on the
    symbolic `/` character, but the whole alternation group shared a single
    trailing `\\b` (Rule 9's canonical defect shape). A `\\b` can only fire
    between a word char and a non-word char -- but in every realistic
    Dockerfile, `rm -rf /` is followed by end-of-instruction, whitespace,
    or `&&`, none of which are word characters, so the trailing `\\b` could
    never actually fire. The single most catastrophic command a Dockerfile
    could contain was silently never detected.
    """
    old_pattern = re.compile(r"\b(?:rm[ \t]+-rf[ \t]+/(?![A-Za-z])|eval|exec)\b", re.M | re.I)
    assert not old_pattern.search("RUN rm -rf /"), "sanity check: bug must reproduce against the old pattern"
    assert not old_pattern.search("RUN rm -rf / && echo done"), "sanity check: bug must reproduce (trailing &&)"

    pattern = DOCKERFILE_RULES["high_risk_execution"]
    assert pattern.search("RUN rm -rf /"), "end-of-instruction 'rm -rf /' still didn't match"
    assert pattern.search("RUN rm -rf / && echo done"), "'rm -rf /' followed by && still didn't match"
    assert not pattern.search("RUN rm -rf /app/tmp"), "scoped rm -rf of a real subdirectory incorrectly matched"
    assert pattern.search("RUN eval $CMD"), "eval regressed"
    assert pattern.search("RUN exec myapp"), "exec regressed"


def test_dockerfile_concurrency_compact_flag_regression():
    """
    Regression test for a real bug: `make -j`/`xargs -P` both end on a word
    char (`j`/`P`) immediately followed by a digit in the compact,
    idiomatic real-world form (`make -j4`, `xargs -P4`) -- a `\\b` cannot
    fire between two adjacent word characters, so the shared trailing `\\b`
    around the whole alternation group only ever matched the spaced-out
    form (`make -j 4`), silently missing the far more common compact one.
    """
    old_pattern = re.compile(r"&[ \t]*$|\b(?:nohup|parallel|make[ \t]+-j|xargs[ \t]+-P)\b", re.M)
    assert not old_pattern.search("RUN make -j4"), "sanity check: bug must reproduce against the old pattern"
    assert old_pattern.search("RUN make -j 4"), "sanity check: spaced-out form already worked"

    pattern = DOCKERFILE_RULES["concurrency"]
    assert pattern.search("RUN make -j4"), "compact 'make -j4' form still didn't match"
    assert pattern.search("RUN make -j 4"), "spaced-out 'make -j 4' form regressed"
    assert pattern.search("RUN xargs -P4 -n1 echo"), "compact 'xargs -P4' form still didn't match"
    assert pattern.search("RUN nohup myserver &"), "nohup regressed"
    assert not pattern.search("RUN echo hi"), "plain recipe incorrectly matched"


def test_dockerfile_ui_framework_lib_prefix_regression():
    """
    Regression test for a real bug: real Debian/Ubuntu apt package names
    for these GUI libraries are almost always `lib`-prefixed
    (`libgtk-3-dev`, `libx11-6`, `libwayland-client0`) -- both "lib" and
    the library tag are word characters, so the old pattern's leading `\\b`
    could never fire partway through a word (`lib|gtk` has no boundary
    between `b` and `g`), silently missing the dominant real-world
    package-name form entirely.
    """
    old_pattern = re.compile(r"\b(?:xvfb|x11|wayland|gtk|qt5?|libgl1-mesa)\b", re.I)
    for line in (
        "RUN apt-get install -y libgtk-3-dev",
        "RUN apt-get install -y libgtk2.0-dev",
        "RUN apt-get install -y libx11-6",
        "RUN apt-get install -y libwayland-client0",
    ):
        assert not old_pattern.search(line), f"sanity check: bug must reproduce against old pattern for {line!r}"

    pattern = DOCKERFILE_RULES["ui_framework"]
    assert pattern.search("RUN apt-get install -y libgtk-3-dev")
    assert pattern.search("RUN apt-get install -y libgtk2.0-dev")
    assert pattern.search("RUN apt-get install -y libx11-6")
    assert pattern.search("RUN apt-get install -y libwayland-client0")
    # Bare (non-lib-prefixed) forms and libgl1-mesa still work as before.
    assert pattern.search("RUN apt-get install -y xvfb")
    assert pattern.search("RUN apt-get install -y qt5-default")
    assert pattern.search("RUN apt-get install -y libgl1-mesa-glx")
    assert not pattern.search("RUN apt-get install -y curl")


def test_dockerfile_func_start_and_macros_no_false_collision():
    """
    Known ambiguity pattern from the issue template (a multi-line macro
    construct hallucinating a function match, as seen with C++'s `#define`
    spiral): dockerfile's `macros` maps to `# syntax=`/`# escape=`
    parser-directive comment lines. Verified empirically that a run of
    these directive lines cannot fool `func_start` (RUN/CMD/ENTRYPOINT/
    HEALTHCHECK) -- a `#`-prefixed comment line never satisfies
    func_start's `^[ \\t]*(RUN|CMD|ENTRYPOINT|HEALTHCHECK)` anchor, and a
    real RUN instruction is unaffected by however many directive lines
    precede it.
    """
    func_start = DOCKERFILE_RULES["func_start"]
    macros = DOCKERFILE_RULES["macros"]

    directive_spiral = "# syntax=docker/dockerfile:1\n" * 50 + "RUN echo hi\n"
    assert len(list(macros.finditer(directive_spiral))) == 50, "all 50 directive lines should satisfy macros"
    func_matches = list(func_start.finditer(directive_spiral))
    assert len(func_matches) == 1 and func_matches[0].group(1) == "RUN", (
        "the directive spiral should not hallucinate extra func_start matches -- only the "
        "real RUN instruction should match"
    )

    single_directive = "# syntax=docker/dockerfile:1\n"
    assert macros.search(single_directive)
    assert not func_start.search(single_directive)


def test_dockerfile_test_and_regex_execution_no_false_collision():
    """
    Known ambiguity pattern from the issue template (a `.test(`-style regex
    method miscounted as a test-framework call, as seen in TypeScript):
    verified empirically rather than assumed. Dockerfile's `test` signature
    is scoped to specific external test-runner invocations (`npm test`,
    `pytest`, `go test`, `cargo test`, `make test`) -- it does not include
    bare `grep`/`sed`/`awk` at all, so it structurally cannot collide with
    `regex_execution`. Also verified the reverse direction: `RUN npm test`
    does not accidentally satisfy `regex_execution` either.
    """
    test_ = DOCKERFILE_RULES["test"]
    regex_execution = DOCKERFILE_RULES["regex_execution"]

    grep_line = "RUN grep -r TODO src/"
    assert regex_execution.search(grep_line)
    assert not test_.search(grep_line)

    npm_test_line = "RUN npm test"
    assert test_.search(npm_test_line)
    assert not regex_execution.search(npm_test_line)


def test_dockerfile_spec_exposure_nested_bracket_no_functional_bug():
    """
    Nested-delimiter audit (Rule 11): `spec_exposure` uses a flat negated
    class (`[^\\]]*`) as its closing-bracket matcher, which cannot
    represent one level of legitimate nesting (e.g. a spec tag that itself
    references an audit tag: `[SPEC-123 ref [audit-9] finding]`).
    Confirmed empirically that this DOES truncate the captured match text
    at the first `]` rather than the outer one -- but confirmed it is NOT a
    functional bug in this codebase: `detector.py`'s comment-stream pass
    (`_analyze_comment_intent`) only ever calls `pattern.findall(...)` and
    takes `len(...)` of the result for `spec_exposure` -- the captured
    substring itself is never read or stored. Truncation therefore has no
    effect on the actual signal the engine records (one bracketed tag still
    counts as one match either way), so this is intentionally left as-is
    rather than upgraded to the one-level-nesting form.
    """
    pattern = DOCKERFILE_RULES["spec_exposure"]
    nested = "[SPEC-123 related to [audit] finding]"
    m = pattern.search(nested)
    assert m is not None
    assert m.group() == "[SPEC-123 related to [audit]", "confirms the truncation behavior exists as documented"

    # Count-based usage (the only way detector.py consumes this rule) is unaffected:
    # exactly one tag in, one match out, regardless of the internal nesting.
    assert len(pattern.findall(nested)) == 1


def test_dockerfile_globals_and_state_mutation_intentional_double_classification():
    """
    Ambiguity sweep: `globals` and `state_mutation` both fire on the same
    `ENV NAME value` line (both anchor `^[ \\t]*ENV[ \\t]+[a-zA-Z0-9_]+`).
    Confirmed genuine, intentional double-classification, not a bug: an
    `ENV` instruction is simultaneously a global-state declaration
    (globals) AND a state mutation that permanently alters the image layer
    (state_mutation) -- both are structurally true at once, the same
    accepted double-classification shape used elsewhere in this codebase
    (e.g. JS's arrow-function call matching both comprehensions and
    closures).
    """
    globals_ = DOCKERFILE_RULES["globals"]
    state_mutation = DOCKERFILE_RULES["state_mutation"]

    env_line = "ENV APP_ENV=production"
    assert globals_.search(env_line)
    assert state_mutation.search(env_line)

    # ARG is deliberately excluded from both (build-time only, not a persisted global).
    arg_line = "ARG APP_ENV=production"
    assert not globals_.search(arg_line)
    assert not state_mutation.search(arg_line)


def test_dockerfile_listeners_and_api_identical_pattern_intentional():
    """
    Ambiguity sweep: `listeners` and `api` are compiled from the literal
    same pattern (`^[ \\t]*EXPOSE[ \\t]+[0-9]+`). Confirmed intentional per
    the source comments: `EXPOSE` is simultaneously part of the container's
    public network surface area (api) AND a declaration that the container
    listens for external network consumption (listeners) -- the same single
    instruction is correctly both, not an accidental duplication.
    """
    listeners = DOCKERFILE_RULES["listeners"]
    api = DOCKERFILE_RULES["api"]
    assert listeners.pattern == api.pattern

    expose_line = "EXPOSE 8080"
    assert listeners.search(expose_line)
    assert api.search(expose_line)


def test_dockerfile_safety_bypasses_curl_pipe_redos_immunity():
    """
    ReDoS immunity for `safety_bypasses`' explicit curl/wget-pipe-to-shell
    guardrail (`\\b(?:curl|wget)[ \\t]+[^|\\n]{1,200}\\|...`), which the
    source comments already claim is ReDoS-safe via the `{1,200}` bound --
    verified directly via scaling measurement rather than trusting the
    comment. Adversarial payload: a `curl` invocation with a very long
    argument string and no closing `|` anywhere.
    """
    pattern = DOCKERFILE_RULES["safety_bypasses"]
    for n in (2000, 8000, 32000):
        assert_redos_immune(pattern, "RUN curl " + "a" * n, timeout_sec=3.0)
    assert pattern.search("RUN curl -fsSL https://get.example.com | bash")


def test_dockerfile_ownership_and_spec_exposure_redos_immunity():
    """
    ReDoS immunity for `ownership`'s trailing `(.*)` capture group and
    `spec_exposure`'s `[^\\]]*` unbounded-then-unanchored class -- both
    flagged in the issue as worth a direct scaling check rather than
    assuming they're safe because they "look bounded by the line". Both
    have exactly one quantified segment with no adjacent quantifier to
    backtrack against, so a long run of non-terminating characters should
    resolve linearly.
    """
    ownership = DOCKERFILE_RULES["ownership"]
    assert_redos_immune(ownership, "MAINTAINER " + "a" * 100000, timeout_sec=3.0)
    m = ownership.search("MAINTAINER Jane Doe <jane@example.com>")
    assert m and m.group(1) == "Jane Doe <jane@example.com>"

    spec_exposure = DOCKERFILE_RULES["spec_exposure"]
    assert_redos_immune(spec_exposure, "[SPEC-123 " + "a" * 100000, timeout_sec=3.0)
    assert spec_exposure.search("[SPEC-123] compliance tag")


def test_dockerfile_updated_signatures_redos_immunity():
    """
    Verify ReDoS immunity for the deepened high-ambiguity signatures (Rule 5 bounds check).
    """
    args_pattern = DOCKERFILE_RULES["args"]
    func_start = DOCKERFILE_RULES["func_start"]
    class_start = DOCKERFILE_RULES["class_start"]
    
    # args: test long strings of continuations
    assert_redos_immune(args_pattern, "ARG " + "\\\n" * 20000, timeout_sec=3.0)
    
    # func_start: test long strings of continuations
    assert_redos_immune(func_start, "RUN " + "\\\n" * 20000, timeout_sec=3.0)
    
    # class_start: test long strings of continuations
    assert_redos_immune(class_start, "FROM " + "\\\n" * 20000, timeout_sec=3.0)
