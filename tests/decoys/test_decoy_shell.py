"""SOP-002-v1 gap-cell decoy suite for POSIX/Bash shell (#8863).

Protocol: docs/agents/decoy-spec-protocol.md (SOP-002-v1)
Covers the five code-stream families that had no decoy row before this suite: comprehensions,
dependency_injection, pointers, safety, state_mutation. Every check runs through the real
Prism.split_streams() + StructuralExtractor.splice() pipeline. Measurement only: no rule or
engine change; every leak found is pinned with a strict xfail that names its issue.

Shell comment forms (POSIX 2.3 / Bash manual): a `#` that begins a word starts a comment to the
end of the line (own line, indented, trailing, and the `#!` interpreter line). A `#` inside a
word is NOT a comment: `$#` (argument count), `${#x}` (length), `${x#pat}` / `${x##pat}` (prefix
strip), `$((16#ff))` (base prefix) and `echo a#b`. The language has no block comment. Here-documents
(`<<EOF`, `<<'EOF'`) and the `: '...'` idiom (the no-op builtin given a quoted string) are
strings, not comments, so a keyword inside them counts today (strings count by design, #2535):
recorded here, not endorsed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import family_decoy_runner as fdr
import family_validity_chart as fvc

from gitgalaxy.core.detector import StructuralExtractor
from gitgalaxy.core.prism import Prism
from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

_PRISM = Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS)
_EXTRACTOR = StructuralExtractor("shell", LANGUAGE_DEFINITIONS)
_BASELINE = Path(__file__).resolve().parents[1] / "family_validity_baseline.json"
_ISSUES = "https://github.com/squid-protocol/gitgalaxy/issues/"


def _hits(family: str, src: str) -> int:
    ref = _PRISM.split_streams(src, "shell")
    res = _EXTRACTOR.splice(
        code_stream=ref["code_stream"],
        comment_stream=ref["comment_stream"],
        raw_content=src,
    )
    return int((res.get("equations") or {}).get(family, 0))


def _xf(issue: int | None) -> list:
    """A strict xfail naming the issue, or no mark when the behaviour is correct."""
    if issue is None:
        return []
    return [pytest.mark.xfail(strict=True, reason=f"{_ISSUES}{issue}")]


ISSUE_SHEBANG = 9462  # the `#!` interpreter line is kept in the code stream

# Authentic positive control per family (Req C).
SHELL_FAMILIES: dict[str, str] = {
    "comprehensions": "for i in {1..5}; do",
    "dependency_injection": "target=${1:-production}",
    "pointers": "declare -n ref=target",
    "safety": "set -euo pipefail",
    "state_mutation": "retries=0",
}

# state_mutation is anchored to the start of a statement, so the mid-line tests use this form of it.
SAME_LINE: dict[str, str] = {**SHELL_FAMILIES, "state_mutation": "(( retries++ ))"}

BRANCH_POSITIVES: dict[str, dict[str, str]] = {
    "comprehensions": {
        "{N..M}": "for i in {1..5}; do",
        "{N,M}": "for i in {1,5}; do",
        "{N..M..S}": "for i in {1..10..2}; do",
        "{a..z}": "for c in {a..z}; do",
    },
    "dependency_injection": {
        "${1:-x}": "target=${1:-production}",
        "${2:-x}": "region=${2:-staging}",
        "command -v": "command -v git >/dev/null",
        "type -p": "type -p git",
    },
    "pointers": {
        "declare -n": "declare -n ref=target",
        "typeset -n": "typeset -n ref=target",
        "${!": "echo ${!ref}",
    },
    "safety": {
        "set -e": "set -e",
        "set -u": "set -u",
        "set -o pipefail": "set -o pipefail",
        "trap ... ERR": "trap 'cleanup' ERR",
        "trap ... EXIT": "trap 'cleanup' EXIT",
        "trap ... INT": "trap 'cleanup' INT",
        "trap ... TERM": "trap 'cleanup' TERM",
        "command -v": "command -v git",
        "${v:-d}": "level=${LOG_LEVEL:-info}",
        "${v:=d}": "level=${LOG_LEVEL:=info}",
        "${v:?m}": "level=${LOG_LEVEL:?must be set}",
    },
    "state_mutation": {
        "x=v": "retries=0",
        "x+=v": "retries+=1",
        "a[i]=v": "names[1]=bob",
        "let x=v": "let retries=1",
        "(( x++ ))": "(( retries++ ))",
        "(( x += n ))": "(( retries += 2 ))",
    },
}


def test_shell_covers_the_gap_families_and_they_are_defined():
    families, _, defined = fvc.engine_grid()
    code_stream = (defined["shell"] & {f.key for f in families}) - fdr.NON_DECOY_FAMILIES
    assert set(SHELL_FAMILIES) <= code_stream
    assert set(BRANCH_POSITIVES) == set(SHELL_FAMILIES)


def test_shell_baseline_has_a_sop002_row_for_every_covered_family():
    rows = json.loads(_BASELINE.read_text())["decoys"]["shell"]
    for family in SHELL_FAMILIES:
        assert rows[family]["protocol"] == "SOP-002-v1", family
        assert rows[family]["corpus"] == "decoy-spec", family


@pytest.mark.parametrize(("family", "src"), sorted(SHELL_FAMILIES.items()))
def test_shell_positive_control_fires(family: str, src: str):
    # G1 (Req C)
    assert _hits(family, src + "\n") >= 1, f"G1 positive control failed for shell.{family}: {src!r}"


@pytest.mark.parametrize(
    ("family", "branch", "src"),
    [(f, b, s) for f, branches in sorted(BRANCH_POSITIVES.items()) for b, s in branches.items()],
)
def test_shell_every_rule_branch_fires(family: str, branch: str, src: str):
    assert _hits(family, src + "\n") >= 1, f"shell.{family} branch {branch!r} is dead for {src!r}"


# ---------------------------------------------------------------------------------------------
# G2 (Req A): every shell comment form. {s} is the family's positive-control snippet.
# ---------------------------------------------------------------------------------------------
_COMMENT_FORMS: list[tuple[str, str, int | None]] = [
    ("line_comment", "# {s}\n", None),
    ("indented_line_comment", "    # {s}\n", None),
    ("trailing_comment", "true # {s}\n", None),
    ("comment_after_argument_count", "echo $# # {s}\n", None),
    ("comment_after_length_expansion", "echo ${{#x}} # {s}\n", None),
    ("comment_after_double_quote_hash", 'echo "a # b" # {s}\n', None),
    ("comment_after_single_quote_hash", "echo 'a # b' # {s}\n", None),
    ("comment_after_prefix_strip", "echo ${{x#*/}} # {s}\n", None),
    ("hash_bang_second_line", "true\n#!/bin/sh {s}\n", None),
    ("hash_bang_first_line", "#!/bin/sh {s}\n", ISSUE_SHEBANG),
]


def _comment_params():
    for family in sorted(SHELL_FAMILIES):
        for form, template, issue in _COMMENT_FORMS:
            # state_mutation is anchored to a statement start, so a keyword after `#!/bin/sh` never fires it
            mark = [] if family == "state_mutation" else _xf(issue)
            yield pytest.param(family, form, template, marks=mark, id=f"{family}-{form}")


@pytest.mark.parametrize(("family", "form", "template"), list(_comment_params()))
def test_shell_comment_forms_hide_the_keyword(family: str, form: str, template: str):
    assert _hits(family, template.format(s=SHELL_FAMILIES[family])) == 0, f"{form} leak for shell.{family}"


@pytest.mark.parametrize("family", sorted(SHELL_FAMILIES))
@pytest.mark.parametrize(
    "prefix",
    ["echo $#;", "echo ${#x};", "echo ${x#*/};", "echo ${x##*/};", "echo $((16#ff));", "echo a#b;"],
    ids=["argument_count", "length", "prefix_strip", "longest_prefix_strip", "base_prefix", "mid_word_hash"],
)
def test_shell_hash_inside_a_word_is_not_a_comment(family: str, prefix: str):
    """`$#`, `${#x}`, `${x#p}`, `$((16#ff))` and `a#b` do not start a comment, so the code after them counts."""
    assert _hits(family, f"{prefix} {SAME_LINE[family]}\n") >= 1


@pytest.mark.parametrize("family", sorted(SHELL_FAMILIES))
def test_shell_here_document_body_is_a_string_and_counts_today(family: str):
    """A here-document body is a string (strings count by design, #2535). Recorded, not endorsed."""
    assert _hits(family, "cat <<EOF\n" + SHELL_FAMILIES[family] + "\nEOF\n") >= 1
    assert _hits(family, "cat <<'EOF'\n" + SHELL_FAMILIES[family] + "\nEOF\n") >= 1


@pytest.mark.parametrize("family", sorted(SHELL_FAMILIES))
def test_shell_colon_quote_pseudo_comment_counts_today(family: str):
    """`: '...'` is the no-op builtin given a quoted string, not a comment: the engine counts it (recorded)."""
    assert _hits(family, ": '\n" + SHELL_FAMILIES[family] + "\n'\n") >= 1


# ---------------------------------------------------------------------------------------------
# G6: strings.
# ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("family", sorted(SHELL_FAMILIES))
def test_shell_keyword_in_a_string_counts_today(family: str):
    """Recorded per family: line-anchored `retries=0` is not at a statement start inside quotes, the rest count."""
    expected = 0 if family == "state_mutation" else 1
    assert _hits(family, 'echo "' + SHELL_FAMILIES[family] + '"\n') == expected


_STRING_PREFIXES = [
    ('url="http://x"', "url"),
    ('msg="a \\" b"', "escaped_dq"),
    ("msg='a # b'", "single_quote_hash"),
    ('msg="a # b"', "hash_in_string"),
]


@pytest.mark.parametrize("family", sorted(SHELL_FAMILIES))
@pytest.mark.parametrize(("prefix", "case"), _STRING_PREFIXES, ids=[c for _, c in _STRING_PREFIXES])
def test_shell_string_then_comment_boundary(family: str, prefix: str, case: str):
    # state_mutation: the prefix assignment itself is a hit, so measure the keyword on a non-assignment prefix
    if family == "state_mutation":
        prefix = "echo " + prefix.split("=", 1)[1]
    assert _hits(family, f"{prefix} # {SHELL_FAMILIES[family]}\n") == 0


@pytest.mark.parametrize("family", sorted(SHELL_FAMILIES))
def test_shell_hash_inside_a_string_does_not_start_a_comment(family: str):
    assert _hits(family, 'echo "a # b"; ' + SAME_LINE[family] + "\n") >= 1


# ---------------------------------------------------------------------------------------------
# G5 (Req B): every alternation branch embedded in a longer identifier must not count.
# ---------------------------------------------------------------------------------------------
_BOUNDARY: list[tuple[str, str]] = [
    # comprehensions: not a brace expansion without digits/letters joined by `..` or `,` and no spaces
    ("comprehensions", "echo { 1..5 }"),
    ("comprehensions", "echo {1, 5}"),
    ("comprehensions", "echo {1.5}"),
    ("comprehensions", "echo {1..}"),
    ("comprehensions", "echo {a..zz}"),
    ("comprehensions", "echo {1...5}"),
    # dependency_injection
    ("dependency_injection", "my_command -v git"),
    ("dependency_injection", "mycommand -v git"),
    ("dependency_injection", "command -vx git"),
    ("dependency_injection", "my_type -p git"),
    ("dependency_injection", "mytype -p git"),
    ("dependency_injection", "type -pa git"),
    ("dependency_injection", "target=${11:-production}"),
    ("dependency_injection", "target=${10:-production}"),
    ("dependency_injection", "target=${3:-production}"),
    # pointers
    ("pointers", "my_declare -n ref=target"),
    ("pointers", "mydeclare -n ref=target"),
    ("pointers", "declare -nx2 ref=target"),
    ("pointers", "my_typeset -n ref=target"),
    ("pointers", "mytypeset -n ref=target"),
    ("pointers", "declared -n ref=target"),
    # safety
    ("safety", "my_set -e"),
    ("safety", "reset -e"),
    ("safety", "set -o pipefailed"),
    ("safety", "my_trap 'cleanup' EXIT"),
    ("safety", "trap 'cleanup' EXITED"),
    ("safety", "trap 'cleanup' ERRORS"),
    ("safety", "trap 'cleanup' INTERRUPT"),
    ("safety", "trap 'cleanup' TERMINATE"),
    ("safety", "my_command -v git"),
    ("safety", "command -vx git"),
    # state_mutation
    ("state_mutation", "my_let retries=1"),
    ("state_mutation", "outlet retries=1"),
    ("state_mutation", "x==y"),
    ("state_mutation", "x=~y"),
]


@pytest.mark.parametrize(("family", "src"), _BOUNDARY)
def test_shell_identifier_boundaries(family: str, src: str):
    assert _hits(family, src + "\n") == 0


# ---------------------------------------------------------------------------------------------
# Req D: negative controls from the contracts and the validity checklist.
# ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("family", "src"),
    [
        # comprehensions: an awk program, a substring expansion and a command group are not brace expansion
        ("comprehensions", "awk '{print $1}' file"),
        ("comprehensions", "echo ${x:1:2}"),
        ("comprehensions", "{ echo a; echo b; }"),
        # dependency_injection: other positional defaults, other `command`/`type` options, other default operators
        ("dependency_injection", "command -V git"),
        ("dependency_injection", "type -t git"),
        ("dependency_injection", "target=${1:=production}"),
        ("dependency_injection", "target=$1"),
        # pointers: other declare options, the background pid and shell pid are not indirection
        ("pointers", "declare -a items"),
        ("pointers", "declare -A table"),
        ("pointers", "declare -x EXPORTED=1"),
        ("pointers", "wait $!"),
        ("pointers", "echo $$"),
        ("pointers", "echo ${#items[@]}"),
        # safety: tracing, positional reset and disabling are not defensive; substring/alternate expansions are not defaults
        ("safety", "set -x"),
        ("safety", 'set -- "$@"'),
        ("safety", "set +e"),
        ("safety", "trap 'cleanup' HUP"),
        ("safety", "name=${v:1:2}"),
        ("safety", "name=${v:+alt}"),
        # state_mutation: declarations (contract corollary 1), comparisons and non-assignment words are not writes
        ("state_mutation", "declare retries=1"),
        ("state_mutation", "local retries=1"),
        ("state_mutation", "readonly retries=1"),
        ("state_mutation", "export retries=1"),
        ("state_mutation", "echo a=b"),
        ("state_mutation", "curl --max-time=5 url"),
        ("state_mutation", "(( retries < 5 ))"),
        ("state_mutation", "echo $(( retries + 1 ))"),
        ("state_mutation", '[ "$a" == "b" ]'),
    ],
)
def test_shell_cross_family_negative_controls(family: str, src: str):
    assert _hits(family, src + "\n") == 0
