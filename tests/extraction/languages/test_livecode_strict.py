"""livecode strict structural-signature coverage.

Migrated out of tests/core_engine/test_language_standards_strict.py, then
colocated here in tests/extraction/languages/ alongside the extraction
gauntlets' own test_<lang>.py files (the `_strict` suffix on this filename
avoids a basename collision between the two under pytest's default import
mode). See tests/core_engine/test_language_standards_strict.py's git history
for the original single-file layout and section banners (Issue references, etc).
"""

import multiprocessing
import re
import sys
from pathlib import Path

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_LANGUAGES_DIR = str(Path(__file__).resolve().parent)
if _LANGUAGES_DIR not in sys.path:
    sys.path.insert(0, _LANGUAGES_DIR)

from _strict_harness import _detonate, assert_redos_immune  # noqa: E402 # type: ignore

# NOTE: this test was originally grouped under a shared "cross-language sweep"
# section in tests/core_engine/test_language_standards_strict.py (before that file
# was split into tests/extraction/languages/, one file per language) alongside
# equivalent regressions for several other languages, all fixing the same bug
# *shape* found by one systematic sweep. Shared context below, duplicated into
# every language file that sweep touched -- see git history for the original,
# single copy.
# ==============================================================================
# CROSS-LANGUAGE SYMBOLIC-\b SWEEP (companion to #585's haskell =~ fix)
# ==============================================================================
# Found by a systematic scan for the same bug shape as haskell's
# regex_execution `=~` fix and javascript/typescript's encapsulation `#`
# fix: a purely-symbolic alternative (no letters/digits/underscore) wrapped
# in a shared \b(...)\b group. \b requires a word/non-word transition, so a
# symbolic alternative flanked by \b can only match with NO surrounding
# whitespace/punctuation at either edge -- never how real code is
# idiomatically formatted (operators and superglobals are almost always
# spaced or preceded by other punctuation, not bare word characters).


def test_livecode_ssr_boundaries_superglobals_and_tags():
    """
    Regression test: `<?lc`, `?>`, and every `$_POST`-style superglobal start
    with a non-word character, so the leading \\b in the old shared wrapper
    could never match once preceded by anything else non-word (a space or
    line start) -- meaning none of those 6 alternatives (everything except
    the plain-word "put header") ever actually matched.
    """
    pattern = LANGUAGE_DEFINITIONS["livecode"]["rules"]["ssr_boundaries"]
    assert pattern.search('put $_POST["x"]'), "Failed to match $_POST in realistic surrounding code"
    assert pattern.search("<?lc\ncode"), "Failed to match the <?lc open tag"
    assert pattern.search("code ?>"), "Failed to match the ?> close tag"
    assert pattern.search('put header "X"')
    assert not pattern.search("computed headers"), "Incorrectly matched 'header' as a substring of 'headers'"


# ==============================================================================
# LIVECODE: STRICT STRUCTURAL SIGNATURE COVERAGE (Issue #593)
# ==============================================================================
LIVECODE_RULES = LANGUAGE_DEFINITIONS["livecode"]["rules"]

_LIVECODE_SIMPLE_CASES = [
    # (signature, positive snippet, text expected to NOT match / None to skip)
    ("branch", "if tCount > 0 then\n  put 1 into x\nend if", 'put "hello" into x'),
    ("args", "on mouseUp pButtonNumber", "on mouseUp"),
    ("structural_boundaries", "put tValue into tField", "constant kMaxRetries"),
    ("func_start", 'on mouseUp\n  answer "hi"\nend mouseUp', "put 1 into x"),
    ("class_start", "module com.livecode.string", "on mouseUp"),
    ("safety", "try\n  put 1 into x\ncatch e\nend try", "put 1 into x"),
    ("safety_bypasses", 'do "put 1 into x"', "put 1 into x"),
    ("high_risk_execution", 'answer "hello"', "put 1 into x"),
    ("io", "open file tFilePath for read", "put 1 into x"),
    ("api", 'on mouseUp\n  answer "hi"\nend mouseUp', "private command foo"),
    ("state_mutation", "put the effective filename of this stack into tPath", "answer 1"),
    ("dead_code", "-- put 1 into x", "put 1 into x"),
    ("doc", "-- Author: Jane Doe", "put 1 into x"),
    ("test", "command testLogin", "put 1 into x"),
    ("concurrency", 'send "myHandler" to me in 2 seconds', "put 1 into x"),
    ("ui_framework", 'put the label of button "OK" into tLabel', "put 1 into x"),
    ("globals", "put $ENV into tEnv", "put 1 into x"),
    ("decorators", "@metadata author", "put 1 into x"),
    ("comprehensions", "repeat for each item tItem in tList", "put 1 into x"),
    ("scientific", "put sqrt(4) into x", "put 1 into x"),
    ("reflection_metaprogramming", 'do "put 1 into x"', "put 1 into x"),
    ("import", 'start using stack "MyLib"', "put 1 into x"),
    ("ownership", "-- Author: Jane Doe", "put 1 into x"),
    ("planned_debt", "-- TODO: refactor this", "put 1 into x"),
    ("fragile_debt", "-- HACK: workaround", "put 1 into x"),
    ("spec_exposure", "-- [SPEC-123] audit trail requirements", "put 1 into x"),
    ("ssr_boundaries", "<?lc echo 1; ?>", "put 1 into x"),
    ("events", 'on mouseUp\n  answer "hi"\nend mouseUp', "on customMessage"),
    ("dependency_injection", "set the behavior of me to tBehavior", "put 1 into x"),
    ("pointers", "command updateList @pList", "put 1 into x"),
    ("telemetry", 'revLog "error occurred"', "put 1 into x"),
    ("debug_prints", 'put "debug: entered handler"', "put tValue into tField"),
    ("explicit_casts", "if tValue is a number then", "put 1 into x"),
    ("panics_and_aborts", 'throw "custom error"', "put 1 into x"),
    ("thread_sleeps", "wait 2 seconds", "wait 2 seconds with messages"),
    ("bitwise_ops", "put bitAnd(5,3) into x", "put 1 into x"),
    ("sync_locks", "lock screen", "put 1 into x"),
    ("immutability_locks", "constant kMaxRetries = 5", "put 1 into x"),
    ("cleanup", "close file tFile", "put 1 into x"),
    ("encapsulation", "private command foo", "public command foo"),
    ("listeners", 'on mouseUp\n  answer "hi"\nend mouseUp', "put 1 into x"),
    ("test_skip", "skip test", "put 1 into x"),
    ("serialization_parsing", "put jsonImport(tJson) into tArray", "put 1 into x"),
    ("regex_execution", 'matchText(tString, "^[0-9]+$")', "put 1 into x"),
    ("time_date_logic", "put the seconds into tNow", "put 1 into x"),
    ("ipc_rpc_bridges", 'put shell("ls -la") into tOutput', "put 1 into x"),

    # --- DEEP ADVERSARIAL CASES: branch ---
    ("branch", "next   repeat", "put the next_repeat into x"),
    ("branch", "repeat for each item tItem in tList", "put 1 into switcharoo"),
    ("branch", "try\n  put 1\ncatch tError", "command notAFunction"),
    ("branch", "finally", "put branching into x"),
    ("branch", "if (x = 1) and (y = 2) then", "put 1 into if_func"),

    # --- DEEP ADVERSARIAL CASES: args ---
    ("args", "on myHandler p1, p2, p3", "on myHandler"),
    ("args", "function calculateTotal pPrice, pTax", "command myCmd\n  put 1 into x"),
    ("args", "command doThing pArg1 -- inline comment", "function"),
    ("args", "getprop myProp pIndex", "put 1 into x -- on myHandler pArg"),
    ("args", "on myCmd arg1\r\n", "on myCmd  \r\n"),
    ("args", "on myHandler   p1,p2   ", "command myCmd  -- comment"),

    # --- DEEP ADVERSARIAL CASES: func_start ---
    ("func_start", "private command myCmd", "put on into x"),
    ("func_start", "on my-Command_123", "command_not_start"),
    ("func_start", "function myFunc\r\n", "on  \r\n"),
    ("func_start", "public   getprop   myProp", "private  put 1 into x"),
    ("func_start", "setprop myProp", "functionality_test"),

    # --- DEEP ADVERSARIAL CASES: class_start ---
    ("class_start", "widget com.livecode.widget.button", "widget_button"),
    ("class_start", "module myMod -- comment", "library_not_start"),
    ("class_start", "behavior myBehavior\r\n", "script  \r\n"),
    ("class_start", "library com.livecode.library", "module  "),
    ("class_start", "script myScript /* block */", "behavioral_test"),

    # --- DEEP ADVERSARIAL CASES: structural_boundaries ---
    ("structural_boundaries", "visual   effect", "constant visual_effect = 1"),
    ("structural_boundaries", "go card 2", "going to card 2"),
    ("structural_boundaries", "dispatch \"myMessage\"", "dispatcher"),
    ("structural_boundaries", "pass myHandler", "passing value"),
    ("structural_boundaries", "replace \"a\" with \"b\"", "replacement"),
]


@pytest.mark.parametrize("signature,positive,negative", _LIVECODE_SIMPLE_CASES)
def test_livecode_signature_positive_and_negative(signature, positive, negative):
    pattern = LIVECODE_RULES[signature]
    assert pattern is not None, f"livecode's {signature!r} rule is unexpectedly None"
    assert pattern.search(positive), f"livecode {signature!r} failed to match its own documented positive case"
    if negative is not None:
        assert not pattern.search(negative), (
            f"livecode {signature!r} incorrectly matched an excluded/negative case: {negative!r}"
        )


def test_livecode_dependency_capture_extracts_path():
    """
    _dependency_capture is paired with `import` and must extract the exact
    dependency path/module string into a capture group, not just detect
    presence. Covers all four import shapes livecode supports.
    """
    pattern = LIVECODE_RULES["_dependency_capture"]

    m = pattern.search('start using stack "MyLib"')
    assert m and (m.group(1) or m.group(2)) == "MyLib"

    m = pattern.search('require "com.livecode.string"')
    assert m and (m.group(1) or m.group(2)) == "com.livecode.string"

    m = pattern.search('include "utils.lc"')
    assert m and (m.group(1) or m.group(2)) == "utils.lc"

    m = pattern.search("module com.livecode.string")
    assert m and (m.group(1) or m.group(2)) == "com.livecode.string", "dotted module path capture regressed"


# ==============================================================================
# REGRESSION TESTS -- one per confirmed bug found during the #593 audit
# ==============================================================================


def test_livecode_structural_boundaries_immutability_locks_duplicate_regression():
    """
    Ambiguity-sweep finding, confirmed a real bug: `structural_boundaries`
    listed `constant` as one of its own alternatives, duplicating
    `immutability_locks` and directly violating this key's own documented
    EXCLUDES rule ("Immutability keywords (const, final) -- these belong
    in immutability_locks", per how_to_add_a_language.md's schema comment
    for structural_boundaries). Every `constant` declaration was double-
    counted as both a structural boundary and an immutability lock. Fixed
    by removing `constant` from structural_boundaries; it now lives only
    in immutability_locks.
    """
    structural = LIVECODE_RULES["structural_boundaries"]
    locks = LIVECODE_RULES["immutability_locks"]

    assert not structural.search("constant kMaxRetries = 5"), (
        "structural_boundaries incorrectly still matches 'constant' (should be immutability_locks-only)"
    )
    assert locks.search("constant kMaxRetries = 5"), "immutability_locks regressed on 'constant'"
    # Other structural_boundaries alternatives must be unaffected.
    assert structural.search("put tValue into tField"), "unrelated structural_boundaries alternative regressed"


def test_livecode_class_start_dotted_module_name_regression():
    """
    Regression test (Rule 11-class nested/multi-segment coverage): the name
    capture `["\\'a-zA-Z_]\\w*` stopped at the first non-word character, so
    it could never consume a dotted reverse-DNS module/widget name --
    LiveCode Builder's real, dominant declaration form (confirmed directly
    against the language-crucible corpus's data/livecode/core/string.lcb,
    whose first real line is `module com.livecode.string`). The trailing
    lookahead then required whitespace/EOL immediately after the partial
    match, which a `.` never satisfies, so the whole match failed. Fixed by
    widening the name pattern to allow up to 10 dotted segments.
    """
    pattern = LIVECODE_RULES["class_start"]
    m = pattern.search("module com.livecode.string")
    assert m, "dotted module name still didn't match"
    assert m.group(1) == "com.livecode.string"

    m = pattern.search("widget com.livecode.widget.myWidget")
    assert m, "multi-segment dotted widget name still didn't match"
    assert m.group(1) == "com.livecode.widget.myWidget"

    m = pattern.search("behavior myBehavior")
    assert m and m.group(1) == "myBehavior", "plain non-dotted name regressed"


def test_livecode_doc_author_colon_trailing_boundary_regression():
    """
    Regression test (Rule 9/10-class trailing-boundary bug): the
    `Description|Purpose|Author|Summary` alternation had a trailing `\\b`
    placed immediately after the literal `:` it requires. `:` is a
    non-word character, so that `\\b` only fires if the very next character
    is a word character -- but the near-universal real form is
    "Author: John Doe" (colon then a space), which is non-word on both
    sides of that exact position, so the tag never matched. Fixed by
    dropping the trailing `\\b` (`:` is already self-delimiting).
    """
    pattern = LIVECODE_RULES["doc"]
    assert pattern.search("-- Author: John Doe"), "'Author: ' (colon-space) form still didn't match"
    assert pattern.search("-- Description: Handles login"), "'Description: ' form still didn't match"
    assert pattern.search("-- Purpose: Validates input"), "'Purpose: ' form still didn't match"
    assert pattern.search("-- Summary: Entry point"), "'Summary: ' form still didn't match"
    # The doc-block tag forms must be unaffected.
    assert pattern.search("--| @param pName the user name"), "'--|' doc-block form regressed"


def test_livecode_state_mutation_multiword_expression_regression():
    """
    Regression test: put/add/subtract's source-expression matcher used
    `[^ \\t\\n]+?`, which excludes spaces -- so the dominant real form of a
    LiveCode expression (`the effective filename of this stack`, `the
    number of items of tList`, a string concatenation) never matched;
    only a single bare token before "into"/"to"/"from" did. Fixed by
    widening to `[^\\n]{1,300}?` (bounded per Rule 5) so it spans the whole
    single-line expression instead of stopping at the first space.
    """
    pattern = LIVECODE_RULES["state_mutation"]
    assert pattern.search("put the effective filename of this stack into tPath"), (
        "multi-word 'put ... into' expression still didn't match"
    )
    assert pattern.search('put "hello" & " " & "world" into tGreeting'), "concatenation expression still didn't match"
    assert pattern.search("add the number of lines of tList to tTotal"), "multi-word 'add ... to' still didn't match"
    assert pattern.search('subtract the value of field "x" from tTotal'), (
        "multi-word 'subtract ... from' still didn't match"
    )
    assert pattern.search("put empty into tField"), "single-token form regressed"


def test_livecode_io_post_multiword_payload_regression():
    """
    Regression test: `io`'s "post ... to url" matcher used
    `[^ \\t\\n]+?`, which excludes spaces -- so a realistic multi-word/
    concatenated payload expression (`post "action=" & tAction to url
    tURL`) never matched; only a single bare variable did. Fixed by
    widening to `[^\\n]{1,300}?` (bounded per Rule 5).
    """
    pattern = LIVECODE_RULES["io"]
    assert pattern.search('post "action=" & tAction to url tURL'), "concatenated post payload still didn't match"
    assert pattern.search('post tData to url "http://example.com/api"'), "single-token post payload regressed"


def test_livecode_concurrency_send_multiword_target_regression():
    """
    Regression test: `concurrency`'s "send X in Y seconds" target matcher
    used `[^ \\t\\n]+?`, which excludes spaces -- so the dominant real
    scheduled-message form (`send "myHandler" to me in 2 seconds`, target
    object references being multi-word) never matched; only a single bare
    token did. Fixed by widening to `[^\\n]{1,300}?` (bounded per Rule 5).
    """
    pattern = LIVECODE_RULES["concurrency"]
    assert pattern.search('send "myHandler" to me in 2 seconds'), "multi-word send target still didn't match"
    assert pattern.search('send "doThing" to button "Go" in 500 milliseconds'), (
        "multi-word send target with object reference still didn't match"
    )
    assert pattern.search("dispatch"), "unrelated concurrency alternative regressed"


def test_livecode_comprehensions_filter_multiword_target_regression():
    """
    Regression test: `comprehensions`'s `filter` target matcher used
    `[^ \\t\\n]+?`, which excludes spaces -- so the common multi-word
    target form (`filter lines of tData with "*.txt"`) never matched; only
    a single bare token did. Fixed by widening to `[^\\n]{1,300}?`
    (bounded per Rule 5).
    """
    pattern = LIVECODE_RULES["comprehensions"]
    assert pattern.search('filter lines of tData with "*.txt"'), "multi-word filter target still didn't match"
    assert pattern.search("repeat for each item tItem in tList"), "'repeat for each' form regressed"


def test_livecode_globals_env_leading_boundary_regression():
    """
    Regression test (Rule 9): `$ENV` started with the symbolic `$`, which
    can never satisfy a leading `\\b` -- real usage is always preceded by
    whitespace or line-start (non-word on both sides of that position), so
    it never matched. Fixed by pulling `$ENV` out of the group with only a
    trailing `\\b` (the `$` is self-delimiting on the left).
    """
    pattern = LIVECODE_RULES["globals"]
    assert pattern.search("put $ENV into tEnv"), "'$ENV' preceded by whitespace still didn't match"
    assert pattern.search("the value of $ENV in this script"), "'$ENV' mid-sentence still didn't match"
    assert pattern.search("global gMyVar"), "unrelated globals alternative regressed"


def test_livecode_pointers_leading_boundary_regression():
    """
    Regression test (Rule 9): the leading `\\b` sat directly in front of
    the symbolic `@` sigil used for pass-by-reference parameters. Real
    usage is always preceded by whitespace, a comma, or an opening paren
    (non-word on both sides of that position), so the leading boundary
    never fired -- `@pList` never matched except in the contrived case of
    a word character glued directly onto the `@`. Fixed by dropping the
    leading `\\b` (the `@` is self-delimiting).
    """
    pattern = LIVECODE_RULES["pointers"]
    assert pattern.search("command updateList @pList"), "'@pList' preceded by whitespace still didn't match"
    assert pattern.search("function bar pValue, @pResult"), "'@pResult' preceded by comma-space still didn't match"


def test_livecode_reflection_metaprogramming_paren_trailing_boundary_regression():
    """
    Regression test (Rule 10): `value(` and `evaluate(` end on the
    self-delimiting `(`, but the shared trailing `\\b` required a word
    character immediately after it -- so the dominant real call shape (a
    quoted expression, e.g. `value("1+1")`) never matched; only an
    unquoted bare-identifier argument (`value(tExpr)`) did. Fixed by
    pulling both out of the group with the trailing `\\b` dropped.
    """
    pattern = LIVECODE_RULES["reflection_metaprogramming"]
    assert pattern.search('value("1+1")'), 'value("...") quoted-argument form still didn\'t match'
    assert pattern.search('evaluate("1+1")'), 'evaluate("...") quoted-argument form still didn\'t match'
    assert pattern.search("value(tExpression)"), "value(identifier) form regressed"
    assert pattern.search("evaluate(tScript)"), "evaluate(identifier) form regressed"


def test_livecode_do_alternative_trailing_boundary_regression():
    """
    Regression test (Rule 9/10-class trailing-boundary bug), affecting two
    separate rules that both use a `do\\s+...` alternative:

    `safety_bypasses`'s "do" alternative uses a negative lookahead
    specifically to target "do" followed by a NON-identifier (a raw
    string/expression -- the actual dynamic-eval bypass), yet the shared
    trailing `\\b` on the outer group required a WORD character right
    after the consumed whitespace. Since the realistic target is almost
    always a quote or paren (both non-word), that boundary could never be
    satisfied for the alternative's own intended match -- `do "put 1 into
    x"` and `do (tExpr)` both silently never matched.

    `reflection_metaprogramming`'s bare `do\\s+` alternative (meant to
    catch every "do X" form) had the identical defect: `do "put 1 into
    x"` never matched, only `do <bareIdentifier>` did, even though the
    quoted-string form is the dominant real dynamic-script-execution
    idiom.

    Both fixed by pulling `do\\s+...` out of the wrapped group (already
    self-delimited by `\\s+` plus, for safety_bypasses, its own lookahead;
    no trailing `\\b` needed).
    """
    bypasses = LIVECODE_RULES["safety_bypasses"]
    reflection = LIVECODE_RULES["reflection_metaprogramming"]

    assert bypasses.search('do "put 1 into x"'), 'safety_bypasses: do "..." quoted-string form still didn\'t match'
    assert bypasses.search("do (tExpr)"), "safety_bypasses: do (...) paren form still didn't match"
    assert not bypasses.search("do tScriptText"), (
        "safety_bypasses incorrectly matched 'do <bareIdentifier>' (excluded by design; see reflection_metaprogramming)"
    )

    assert reflection.search('do "put 1 into x"'), (
        'reflection_metaprogramming: do "..." quoted-string form still didn\'t match'
    )
    assert reflection.search("do tScriptText"), "reflection_metaprogramming: do <identifier> form regressed"


def test_livecode_ipc_rpc_bridges_shell_trailing_boundary_regression():
    """
    Regression test (Rule 10): `shell\\s*\\(` ends on the self-delimiting
    `(`, but the shared trailing `\\b` required a word character
    immediately after it -- so the dominant real call shape (a quoted
    command string, e.g. `shell("ls -la")`) never matched; only an
    unquoted bare-identifier argument (`shell(tCmd)`) did. Fixed by
    pulling it out of the group with the trailing `\\b` dropped.
    """
    pattern = LIVECODE_RULES["ipc_rpc_bridges"]
    assert pattern.search('put shell("ls -la") into tOutput'), 'shell("...") quoted-argument form still didn\'t match'
    assert pattern.search("put shell(tCommand) into tOutput"), "shell(identifier) form regressed"
    assert pattern.search('open socket "127.0.0.1:8080"'), "unrelated ipc_rpc_bridges alternative regressed"


# ==============================================================================
# COMMENT-STYLE COMPLETENESS (Rule 12)
# ==============================================================================


def test_livecode_dead_code_comment_style_completeness():
    pattern = LIVECODE_RULES["dead_code"]
    assert pattern.search("-- put 1 into x"), "'--' style regressed"
    assert pattern.search("# on mouseUp"), "'#' style regressed"
    assert pattern.search("// function foo"), "'//' style regressed"


def test_livecode_doc_comment_style_completeness():
    pattern = LIVECODE_RULES["doc"]
    assert pattern.search("--| @param pName the user name"), "'--|' doc-block style regressed"
    assert pattern.search("--@ @author Jane Doe"), "'--@' doc-block style regressed"
    assert pattern.search("/** @param pName the user name\n@return true */"), "'/**' doc-block style regressed"
    assert pattern.search("//! @author Jane Doe"), "'//!' doc-block style regressed"
    assert pattern.search("-- Author: Jane Doe"), "'--' plain Author: tag regressed"


def test_livecode_ownership_comment_style_completeness():
    pattern = LIVECODE_RULES["ownership"]
    assert pattern.search("-- Author: Jane Doe"), "'--' style regressed"
    assert pattern.search("# Author: Jane Doe"), "'#' style regressed"
    assert pattern.search("// Author: Jane Doe"), "'//' style regressed"


# ==============================================================================
# AMBIGUITY SWEEP
# ==============================================================================


def test_livecode_ambiguity_safety_vs_explicit_casts_is_a_dual_classification():
    """
    Confirmed intentional dual-classification, not a bug: LiveCode's
    "is a"/"is strictly" type-check assertion genuinely serves both
    `safety` (a defensive runtime guard) and `explicit_casts` (a type
    introspection) at once -- the same construct legitimately plays two
    roles, the same shape as the Pester `Should -Match` dual-classification
    called out in how_to_add_a_language.md's ambiguity-sweep guidance.
    """
    safety = LIVECODE_RULES["safety"]
    casts = LIVECODE_RULES["explicit_casts"]
    text = "if tValue is a number then"
    assert safety.search(text) and casts.search(text)


def test_livecode_ambiguity_safety_vs_sync_locks_lock_dual_classification():
    """
    Confirmed intentional dual-classification, not a bug: `lock screen` /
    `lock messages` / `lock errorDialogs` are listed verbatim in both
    `safety` (defensive UI-update suppression) and `sync_locks` (explicit
    coordination to prevent race conditions) -- LiveCode is single-
    threaded, so these constructs really do serve both purposes
    simultaneously (suppressing UI/message races during a critical
    section), matching Rule 1's guidance to capture practical semantic
    reality over one-key-per-construct purity.
    """
    safety = LIVECODE_RULES["safety"]
    locks = LIVECODE_RULES["sync_locks"]
    text = "lock screen"
    assert safety.search(text) and locks.search(text)


def test_livecode_ambiguity_listeners_func_start_events_full_overlap():
    """
    Confirmed structurally-forced (not a bug to "fix" at the regex level):
    every handler declaration ("on X") matches `func_start` (its
    structural anchor), `listeners` (LiveCode's message-passing paradigm
    means every handler IS a de facto broadcast listener for that
    message), and -- for the specific enumerated UI/lifecycle event names
    -- `events` too. There is no syntactic distinction in HyperTalk
    between "a handler" and "a listener registration"; they are the same
    construct. Narrowing `listeners` to avoid this would require inventing
    a distinction the language doesn't actually have, which
    how_to_add_a_language.md's "don't force a fit" guidance warns against.
    """
    func_start = LIVECODE_RULES["func_start"]
    listeners = LIVECODE_RULES["listeners"]
    events = LIVECODE_RULES["events"]
    text = "on mouseUp"
    assert func_start.search(text) and listeners.search(text) and events.search(text)


def test_livecode_ambiguity_doc_vs_ownership_author_dual_classification():
    """
    Confirmed intentional dual-classification, not a bug: an "Author:"
    tag is simultaneously structured documentation (`doc`) and authorship
    metadata (`ownership`) -- the same real-world convention JSDoc's
    `@author` tag represents in other languages, where both signatures
    are expected to co-fire on the same line.
    """
    doc = LIVECODE_RULES["doc"]
    ownership = LIVECODE_RULES["ownership"]
    text = "-- Author: Jane Doe"
    assert doc.search(text) and ownership.search(text)


def test_livecode_ambiguity_io_vs_ipc_rpc_bridges_url_dual_classification():
    """
    Confirmed intentional dual-classification, not a bug: `io` and
    `ipc_rpc_bridges` are a baseline signal and a Hybrid Domain Sensor
    layered on top of it (per how_to_add_a_language.md's "Hybrid Domain
    Sensors are explicitly additional specialized lenses" framing) --
    URL/socket/process operations are expected to fire both, since a
    network call genuinely is both raw I/O and an inter-process/RPC
    bridge.
    """
    io = LIVECODE_RULES["io"]
    ipc = LIVECODE_RULES["ipc_rpc_bridges"]
    text = 'get url "http://example.com"'
    assert io.search(text) and ipc.search(text)


def test_livecode_ambiguity_test_vs_regex_execution_no_collision():
    """
    Known cross-language ambiguity pattern (TypeScript's `.test(` vs
    `regex_execution` collision) checked and confirmed NOT present here:
    livecode's `test` signature keys off `command test*`/`pass test`/
    `fail test`/framework names (Levure/LcU/runTests), none of which
    overlap with `regex_execution`'s `matchText`/`matchChunk`/
    `replaceText`/`filter ... with regex` keywords.
    """
    test = LIVECODE_RULES["test"]
    regex_exec = LIVECODE_RULES["regex_execution"]
    assert test.search("command testLogin") and not regex_exec.search("command testLogin")
    assert regex_exec.search('matchText(tString, "^[0-9]+$")') and not test.search('matchText(tString, "^[0-9]+$")')


def test_livecode_ambiguity_explicit_casts_vs_pointers_no_collision():
    """
    Known cross-language ambiguity pattern (C's cast-syntax vs
    pointer-asterisk collision) checked and confirmed NOT present here:
    livecode's `explicit_casts` keys off the English-style "is a"/"is
    strictly" assertions, and `pointers` keys off the `@identifier`
    pass-by-reference sigil -- disjoint token shapes, no overlap.
    """
    casts = LIVECODE_RULES["explicit_casts"]
    pointers = LIVECODE_RULES["pointers"]
    assert casts.search("if tValue is a number then") and not pointers.search("if tValue is a number then")
    assert pointers.search("command updateList @pList") and not casts.search("command updateList @pList")


# ==============================================================================
# REDOS SCALING VERIFICATION
# ==============================================================================
# Reuses the _detonate() subprocess primitive that assert_redos_immune() (top
# of file) is built on, but captures the actual per-size duration so growth
# can be measured across several geometrically increasing sizes -- a single
# pass/fail timing (as assert_redos_immune alone gives) can't distinguish
# "fast because linear" from "fast because still below the O(n^2) knee at
# this size", so #593 asks for explicit multi-point scaling instead.


def _measure_scaling_point(pattern: re.Pattern, payload: str, timeout_sec: float = 2.0) -> float:
    ctx = multiprocessing.get_context("spawn")
    result_queue = ctx.Queue()
    p = ctx.Process(target=_detonate, args=(pattern, payload, result_queue))
    p.start()
    p.join(timeout_sec)
    if p.is_alive():
        p.terminate()
        p.join()
        raise AssertionError(f"ReDoS TRIGGERED at scaling checkpoint! payload len={len(payload)}\n{pattern.pattern}")
    if result_queue.empty():
        raise AssertionError("Scaling checkpoint process produced no timing (crashed?)")
    return result_queue.get()


def assert_linear_redos_scaling(pattern: re.Pattern, payload_fn, sizes=(2000, 4000, 8000, 16000, 32000)):
    """
    Measures pattern.search() time at each size in `sizes` (each isolated
    in its own subprocess via the shared _detonate primitive) and asserts
    the growth between consecutive sizes stays roughly linear (~2x per
    doubling). A ~4x-per-doubling signature is O(n^2) catastrophic
    backtracking and fails the assertion.
    """
    timings = [_measure_scaling_point(pattern, payload_fn(n)) for n in sizes]
    for i in range(1, len(timings)):
        prev, cur = timings[i - 1], timings[i]
        if prev < 0.0005:
            continue  # too fast at this size to derive a meaningful ratio
        ratio = cur / prev
        assert ratio < 3.5, (
            f"Possible catastrophic backtracking: {sizes[i - 1]}->{sizes[i]} chars grew "
            f"{ratio:.2f}x (expected ~2x for linear scaling). Timings: {list(zip(sizes, timings))}"
        )
    return timings


_LIVECODE_REDOS_SCALING_TARGETS = [
    ("args", lambda n: "on foo " + "x" * n),
    ("state_mutation", lambda n: "put " + "x" * n),
    ("io", lambda n: "post " + "x" * n),
    ("concurrency", lambda n: "send " + "x" * n),
    ("comprehensions", lambda n: "filter " + "x" * n),
    ("class_start", lambda n: "module " + "a." * n),
    ("doc", lambda n: "--| " + "x" * n),
    ("regex_execution", lambda n: "filter " + "x" * n),
    ("ipc_rpc_bridges", lambda n: "post " + "x" * n),
    ("_dependency_capture", lambda n: "require " + "x" * n),
]


@pytest.mark.parametrize("key,payload_fn", _LIVECODE_REDOS_SCALING_TARGETS)
def test_livecode_redos_linear_scaling(key, payload_fn):
    pattern = LIVECODE_RULES[key]
    assert_linear_redos_scaling(pattern, payload_fn)


def test_livecode_pointers_redos_immune():
    """Dedicated single-shot check (ceiling guard) on top of the scaling sweep above."""
    pattern = LIVECODE_RULES["pointers"]
    assert_redos_immune(pattern, "@" * 40000, timeout_sec=3.0)


def test_livecode_globals_redos_immune():
    pattern = LIVECODE_RULES["globals"]
    assert_redos_immune(pattern, "the " * 20000, timeout_sec=3.0)
