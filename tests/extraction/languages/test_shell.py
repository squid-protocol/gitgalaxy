"""
Shell extraction hardening (epic #813, issue #835). See
tests/extraction/how_to_harden_extraction.md for the methodology.

Covers three of the four extraction gauntlets for shell in one file:
func_start, args, _dependency_capture (shell has no `class_start` -- it's
strictly procedural, see LANGUAGE_DEFINITIONS["shell"]["rules"]["class_start"]
== None -- so there is no CLASS_CASES section here, matching the issue's own
scope). Migrated out of the two old monolithic dict files that had shell
entries (test_function_extraction_strict.py, test_dependency_extraction_strict.py
-- test_args_extraction_strict.py had no shell entry at all, args had zero
prior test coverage).
"""

import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

# tests/ has no __init__.py anywhere in this repo, so a dotted
# `tests.extraction._extraction_harness` import only works by accident
# locally (e.g. `python -m pytest` from the repo root happens to put the
# root on sys.path) and fails in CI, which invokes the `pytest` console
# script directly. Insert this file's parent (tests/extraction/) onto
# sys.path instead, so the harness imports as a plain top-level module.
_EXTRACTION_DIR = str(Path(__file__).resolve().parent.parent)
if _EXTRACTION_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTION_DIR)

from typing import Any

from _extraction_harness import (  # noqa: E402 # type: ignore
    assert_invalid_no_match,
    assert_pathological_dependency_match,
    assert_pathological_match,
    assert_redos_immune,
    assert_valid_dependency_match,
    assert_valid_match,
)

SHELL_RULES = LANGUAGE_DEFINITIONS["shell"]["rules"]

# Bash/Zsh's full word-based reserved-word set -- none of these can ever be a
# real POSIX function name (`done() { ... }` is a syntax error in a real
# shell), but this is a regex-only engine scanning arbitrary/malformed text,
# so func_start's keyword-exclusion lookahead needs to cover all of them, not
# just a handful. Shared between the invalid-tier cases and the dedicated
# regression test below.
SHELL_RESERVED_WORDS = [
    "if",
    "then",
    "elif",
    "else",
    "fi",
    "case",
    "esac",
    "while",
    "until",
    "for",
    "in",
    "do",
    "done",
    "function",
    "select",
    "time",
    "coproc",
]

# ==============================================================================
# FUNC_START (func_start)
# ==============================================================================
FUNCTION_CASES: dict[str, Any] = {
    "valid": [
        # Modern idiom (carried forward)
        ("function TargetFunc {", "TargetFunc"),
        ("TargetFunc() {", "TargetFunc"),
        # Syntax-era / shape coverage
        ("function TargetFunc() {", "TargetFunc"),  # function keyword AND parens together
        ("TargetFunc () {", "TargetFunc"),  # POSIX style, space before parens
        ("  TargetFunc() {", "TargetFunc"),  # indented (nested inside a conditional/loop)
        ("function _private.helper {", "_private.helper"),  # dotted namespacing convention
        ("foo-bar() {", "foo-bar"),  # hyphenated name -- valid bash identifier shape
    ],
    "invalid": [
        "TargetFunc=",  # assignment lookalike
        "if TargetFunc; then",  # control-flow lookalike
        "alias TargetFunc=",  # alias lookalike
        "if() {",  # excluded keyword (pre-existing)
        "while() {",
        "for() {",
        "case() {",
        "until() {",
        "then() {",  # excluded keyword -- was a real bug, now fixed
        "elif() {",
        "else() {",
        "fi() {",
        "esac() {",
        "in() {",
        "do() {",
        "done() {",
        "function() {",
        "select() {",
        "time() {",
        "coproc() {",
    ],
    "pathological": [
        ("function \t \n TargetFunc \n {", "TargetFunc"),  # carried-forward: vertical spacing
        ("function \n TargetFunc() \n {", "TargetFunc"),  # vertical + trailing parens
        ("TargetFunc \n () \n {", "TargetFunc"),  # POSIX style split before parens
        ("   \t  TargetFunc()   {", "TargetFunc"),  # extreme horizontal whitespace mix
        ("function\tTargetFunc\t{", "TargetFunc"),  # tabs only, no spaces
        ("_1.2-3_helper() {", "_1.2-3_helper"),  # digits/dots/hyphens mixed in one name
        (
            "function global_state.reset_all_the_things.now() {",
            "global_state.reset_all_the_things.now",
        ),  # long dotted namespaced name
    ],
}


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["valid"])
def test_shell_func_start_valid(payload, expected_name):
    assert_valid_match(SHELL_RULES["func_start"], payload, expected_name, "shell.func_start")


@pytest.mark.parametrize("payload", FUNCTION_CASES["invalid"])
def test_shell_func_start_invalid(payload):
    assert_invalid_no_match(SHELL_RULES["func_start"], payload, "shell.func_start")


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["pathological"])
def test_shell_func_start_pathological(payload, expected_name):
    assert_pathological_match(SHELL_RULES["func_start"], payload, expected_name, "shell.func_start")


def test_shell_func_start_reserved_word_exclusion_regression():
    """
    Regression test for a real bug (epic #813/#835): the POSIX `name()`
    branch's keyword-exclusion lookahead only listed 5 of bash's ~17
    word-based reserved words (if/while/for/case/until) -- `done() {`,
    `elif() {`, `select() {`, `function() {`, etc. all falsely matched as
    function definitions. None of these are ever valid bash (a reserved
    word can't be used as a POSIX function name -- the real parser errors
    on it), but this is a regex-only engine scanning arbitrary/malformed
    text, so the same defensive intent behind the original 5-word list
    applies equally to the rest. Widened to the full reserved-word set.
    """
    func_start = SHELL_RULES["func_start"]
    for word in SHELL_RESERVED_WORDS:
        payload = f"{word}() {{"
        assert not func_start.search(payload), f"reserved word incorrectly matched as a function definition: {word!r}"


def test_shell_func_start_redos_immunity():
    """ReDoS sweep for the widened keyword-exclusion lookahead."""
    func_start = SHELL_RULES["func_start"]
    assert_redos_immune(func_start, "x" * 200000 + "() {", timeout_sec=3.0)
    assert_redos_immune(func_start, "coproc" * 50000 + "() {", timeout_sec=3.0)
    assert func_start.search("TargetFunc() {")


# ==============================================================================
# ARGS (args)
# ==============================================================================
ARGS_CASES: dict[str, Any] = {
    "valid": [
        ("echo $1", "$1"),  # bare single-digit positional
        ("echo ${10}", "${10}"),  # braced two-digit positional
        ("echo $@", "$@"),  # bare all-args
        ('echo "$@"', "$@"),  # quoted all-args
        ("echo $#", "$#"),  # arg count
        ("echo ${1:-default}", "${1:-default}"),  # default value -- was a real bug, now fixed
        ("echo ${1:?msg}", "${1:?msg}"),  # error-if-unset -- was a real bug, now fixed
        ("echo ${1:=default}", "${1:=default}"),  # assign-if-unset -- was a real bug, now fixed
        ("echo ${1:+alt}", "${1:+alt}"),  # alternate value -- was a real bug, now fixed
    ],
    "invalid": [
        "echo $0",  # script name, NOT a positional parameter (deliberately excluded)
        "echo ${0}",  # braced script name, same exclusion
        "echo $name",  # named-variable lookalike (not a digit/@/*/# )
        "echo $VAR_NAME",  # named-variable lookalike, uppercase
    ],
    "pathological": [
        ("echo $1$2$3$4$5$6$7$8$9", "$1"),  # back-to-back positionals, no separators
        (
            "echo ${1:-${DEFAULT:-x}}",
            "${1:-${DEFAULT:-x}}",
        ),  # one-level-nested default value
        (
            "echo ${1:-$(echo fallback)}",
            "${1:-$(echo fallback)}",
        ),  # default value containing a command substitution (parens, not braces)
    ],
}


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["valid"])
def test_shell_args_valid(payload, expected_name):
    assert_valid_match(SHELL_RULES["args"], payload, expected_name, "shell.args")


@pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
def test_shell_args_invalid(payload):
    assert_invalid_no_match(SHELL_RULES["args"], payload, "shell.args")


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["pathological"])
def test_shell_args_pathological(payload, expected_name):
    assert_pathological_match(SHELL_RULES["args"], payload, expected_name, "shell.args")


def test_shell_args_default_value_expansion_regression():
    """
    Regression test for a real bug (epic #813/#835): the braced form
    (`${1}`/`${10}`) had no allowance for bash's default-value/error-message
    expansion operators (`:-`, `:=`, `:?`, `:+`) -- so `${1:-default}`,
    arguably the single most common real-world way a positional parameter
    actually appears in scripts, was entirely invisible to this rule. Fixed
    with an optional `:[-=?+]...` suffix using the same one-level-nesting-safe
    idiom already established elsewhere in this file's `safety` rule.
    """
    args = SHELL_RULES["args"]
    for operator in ("-", "=", "?", "+"):
        payload = f"echo ${{1:{operator}fallback}}"
        m = args.search(payload)
        assert m and m.group(0) == payload.removeprefix("echo "), (
            f"default-value operator {operator!r} regressed: {payload!r}"
        )


def test_shell_args_zero_is_not_a_positional_param_regression():
    """
    Documents deliberate, correct behavior (not a bug): `$0`/`${0}` is the
    script/command name in real bash semantics, not function argument
    "zero" -- the rule's `[1-9]` (not `[0-9]`) reflects that distinction on
    purpose. Locks it in so a future "helpful" widening to `[0-9]` gets
    caught as a regression, not shipped as a fix.
    """
    args = SHELL_RULES["args"]
    assert not args.search("echo $0"), "bare $0 must not be treated as a positional parameter"
    assert not args.search("echo ${0}"), "braced ${0} must not be treated as a positional parameter"


def test_shell_args_known_limitation_bare_two_digit_positional_matches_only_first_digit():
    """
    Documents a known, NOT-a-bug limitation that mirrors real bash semantics
    exactly: `$10` unbraced is genuinely `${1}0` in bash (parameter 1
    followed by a literal "0"), NOT the tenth positional parameter -- you
    MUST write `${10}` for that. The regex matching only `$1` out of a bare
    `$10` is therefore correct behavior, not a truncation bug.
    """
    args = SHELL_RULES["args"]
    m = args.search("echo $10")
    assert m and m.group(0) == "$1", "bare $10 must match only $1, matching real bash parameter-expansion semantics"


def test_shell_args_redos_immunity():
    """ReDoS sweep for the new default-value-operator alternative."""
    args = SHELL_RULES["args"]
    assert_redos_immune(args, "${1:-" + "a" * 200000, timeout_sec=3.0)
    assert_redos_immune(args, "${1:-" + "{" * 200000, timeout_sec=3.0)
    assert args.search("${1:-default}")


# ==============================================================================
# NOTE: shell has no class_start -- LANGUAGE_DEFINITIONS["shell"]["rules"]
# ["class_start"] is None ("Shell is strictly procedural."). No CLASS_CASES
# section, matching this issue's own scope (#835 only lists func_start, args,
# _dependency_capture as in-scope rules).
# ==============================================================================

# ==============================================================================
# DEPENDENCY (_dependency_capture)
# ==============================================================================
DEPENDENCY_CASES: dict[str, Any] = {
    "valid": [
        ("source .env", ".env"),  # carried-forward
        (". /etc/profile", "/etc/profile"),  # carried-forward
        ('source "lib/utils.sh"', "lib/utils.sh"),  # double-quoted path
        ("source 'lib/utils.sh'", "lib/utils.sh"),  # single-quoted path
        ("if [ -f .env ]; then source .env; fi", ".env"),  # mid-statement, after `;`
        ("test -f lib.sh && . lib.sh", "lib.sh"),  # mid-statement, after `&&`
        ("cmd1 | source lib.sh", "lib.sh"),  # mid-statement, after `|`
        ("cmd1 & source lib.sh", "lib.sh"),  # mid-statement, after `&`
    ],
    "invalid": [
        "echo 'source .env'",  # carried-forward: keyword inside an unrelated command's string arg
        "echo sourced",  # substring-of-keyword lookalike
    ],
    "pathological": [
        (". \t  '/opt/custom/script.sh'", "/opt/custom/script.sh"),  # carried-forward: extreme spacing
        ("&source /deep/nested/path/lib.sh", "/deep/nested/path/lib.sh"),  # no space after `&` boundary
        ("cmd;. /deep/nested/path/lib.sh", "/deep/nested/path/lib.sh"),  # no space, dot-source after `;`
    ],
}


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["valid"])
def test_shell_dependency_capture_valid(payload, expected_path):
    assert_valid_dependency_match(SHELL_RULES["_dependency_capture"], payload, expected_path, "shell._dependency_capture")


@pytest.mark.parametrize("payload", DEPENDENCY_CASES["invalid"])
def test_shell_dependency_capture_invalid(payload):
    assert_invalid_no_match(SHELL_RULES["_dependency_capture"], payload, "shell._dependency_capture")


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["pathological"])
def test_shell_dependency_capture_pathological(payload, expected_path):
    assert_pathological_dependency_match(
        SHELL_RULES["_dependency_capture"], payload, expected_path, "shell._dependency_capture"
    )


def test_shell_dependency_capture_redos_immunity():
    """ReDoS sweep for the statement-boundary alternation and quoted-path capture."""
    dep = SHELL_RULES["_dependency_capture"]
    assert_redos_immune(dep, "source '" + "a" * 200000, timeout_sec=3.0)
    assert_redos_immune(dep, "source " + "a" * 200000, timeout_sec=3.0)
    assert dep.search("source .env")


def test_shell_dependency_capture_known_limitation_commented_out_source_still_matches():
    """
    Documents a known, NOT-fixed limitation (recurring bug class 11 in
    how_to_harden_extraction.md: "_dependency_capture is matched against raw,
    unshielded file content for EVERY language"), newly confirmed for shell
    specifically. Unlike powershell's equivalent rule (which anchors strictly
    to `^[ \\t]*`, so a `#` at true line start structurally blocks any match --
    see test_powershell.py's "comment_lookalike_structurally_immune" test),
    shell's rule deliberately allows a boundary character ANYWHERE preceding
    the keyword -- not just true line-start -- specifically so mid-statement
    sourcing after `;`/`|`/`&`/`&&` is recognized (a real historical bug fix,
    see the rule's own inline comment). The side effect: a commented-out
    `# source .env` line still produces a phantom dependency-graph edge,
    because the space character immediately after `#` satisfies the boundary
    requirement regardless of the `#` itself. This is the exact same
    architectural gap as every other language's dependency-capture rule, not
    a shell-specific oversight -- fixing it requires the shared
    comment/string-shielding architecture, not a per-language regex patch.
    """
    dep = SHELL_RULES["_dependency_capture"]
    assert dep.search("# source .env"), "documents current (expected, pipeline-wide, not-yet-fixed) regex behavior"


def test_shell_dependency_capture_string_lookalike_boundary_is_incidental_not_real_immunity():
    """
    Documents that the earlier no-space case (`echo "source .env"`, in the
    invalid tier above) is NOT real string-awareness -- it's an incidental
    side effect of the opening `"` character not being in the boundary set.
    The moment there's a natural space between the quote and the keyword (an
    extremely common way this would actually appear in a real echo/log
    string), the immunity disappears and it matches anyway. Same
    architectural gap as the comment case above, not a fix to rely on.
    """
    dep = SHELL_RULES["_dependency_capture"]
    assert not dep.search('echo "source .env"'), "no-space case: incidental non-match (unchanged baseline)"
    assert dep.search('echo " source .env"'), "documents current (expected, not-yet-fixed) regex behavior"
