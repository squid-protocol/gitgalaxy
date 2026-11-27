"""SOP-002-v1 gap-cell decoy suite for Ruby (#8863).

Protocol: docs/agents/decoy-spec-protocol.md (SOP-002-v1)
Covers the four code-stream families that had no decoy row before this suite:
auth_middleware, comprehensions, import, telemetry. Every check runs through the real
Prism.split_streams() + StructuralExtractor.splice() pipeline. Measurement only: no rule or
engine change; every leak found is pinned with a strict xfail that names its issue.

Ruby comment forms (Programming Ruby / ruby-lang syntax): `#` line comment (own line,
indented, trailing), `=begin ... =end` block comment (the markers must start in column 0),
and `__END__` (everything after it is the DATA section, never code). Ruby block comments do
not nest. Heredocs (`<<~EOS`) are strings, not comments, so a keyword inside one counts today
(strings count by design, #2535); that is recorded, not asserted as correct.
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
_EXTRACTOR = StructuralExtractor("ruby", LANGUAGE_DEFINITIONS)
_BASELINE = Path(__file__).resolve().parents[1] / "family_validity_baseline.json"
_ISSUES = "https://github.com/squid-protocol/gitgalaxy/issues/"


def _hits(family: str, src: str) -> int:
    ref = _PRISM.split_streams(src, "ruby")
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


# Issues filed by this suite (one per root cause).
ISSUE_BEGIN_END = 9435  # =begin ... =end block comment leaks into the code stream
ISSUE_DATA_SECTION = 9436  # everything after __END__ (the DATA section) counts as code
ISSUE_BARE_LOGGER = 9437  # telemetry: a bare `logger.info` receiver never fires
ISSUE_LOAD_RECEIVER = 9438  # import: `YAML.load("..")`, `load = 'x'` count as an import
ISSUE_AUTH_DEF = 9440  # auth_middleware: `def authenticate_user!` (a definition) counts
ISSUE_BLOCK_ARGS = 9442  # comprehensions: `.inject(0) { }` / `.each_with_object([]) { }` never fire

# Authentic positive control per family (Req C).
RUBY_FAMILIES: dict[str, str] = {
    "auth_middleware": "before_action :authenticate_user!",
    "comprehensions": "names = items.map { |item| item.name }",
    "import": "require 'json'",
    "telemetry": "Rails.logger.info(message)",
}

# Every literal alternation branch of each rule, with an authentic line that must fire (proves
# the boundary decoys below are not vacuous).
BRANCH_POSITIVES: dict[str, dict[str, str]] = {
    "auth_middleware": {
        "before_action :authenticate_x": "before_action :authenticate_user!",
        "authenticate_x!": "authenticate_user!",
        "user_signed_in?": "redirect_to root_path unless user_signed_in?",
        "can? :": "head :forbidden unless can? :read, @post",
        "authorize @x": "authorize @post",
        ".valid_password?(": "user.valid_password?(params[:password])",
    },
    "comprehensions": {
        branch: f"result = items.{branch} {{ |item| item }}"
        for branch in (
            "map collect select reject reduce inject filter_map flat_map each_with_object partition group_by".split()
        )
    },
    "import": {
        "require": "require 'json'",
        "require_relative": "require_relative 'helper'",
        "load": "load 'tasks/seed.rb'",
        "autoload": "autoload :Parser, 'my/parser'",
    },
    "telemetry": {
        "Rails.logger.": "Rails.logger.warn(message)",
        "Logger.new.": "Logger.new.error(message)",
        "SemanticLogger.": "SemanticLogger.fatal(message)",
        "<id>logger.": "app_logger.debug(message)",
    },
}


def test_ruby_covers_the_gap_families_and_they_are_defined():
    families, _, defined = fvc.engine_grid()
    code_stream = (defined["ruby"] & {f.key for f in families}) - fdr.NON_DECOY_FAMILIES
    assert set(RUBY_FAMILIES) <= code_stream
    assert set(BRANCH_POSITIVES) == set(RUBY_FAMILIES)


def test_ruby_baseline_has_a_sop002_row_for_every_covered_family():
    rows = json.loads(_BASELINE.read_text())["decoys"]["ruby"]
    for family in RUBY_FAMILIES:
        assert rows[family]["protocol"] == "SOP-002-v1", family
        assert rows[family]["corpus"] == "decoy-spec", family


@pytest.mark.parametrize(("family", "src"), sorted(RUBY_FAMILIES.items()))
def test_ruby_positive_control_fires(family: str, src: str):
    # G1 (Req C)
    assert _hits(family, src + "\n") >= 1, f"G1 positive control failed for ruby.{family}: {src!r}"


@pytest.mark.parametrize(
    ("family", "branch", "src"),
    [(f, b, s) for f, branches in sorted(BRANCH_POSITIVES.items()) for b, s in branches.items()],
)
def test_ruby_every_rule_branch_fires(family: str, branch: str, src: str):
    assert _hits(family, src + "\n") >= 1, f"ruby.{family} branch {branch!r} is dead for {src!r}"


# ---------------------------------------------------------------------------------------------
# G2 (Req A): every Ruby comment form. {s} is the family's positive-control snippet.
# ---------------------------------------------------------------------------------------------
_LINE_FORMS: list[tuple[str, str]] = [
    ("line_comment", "# {s}\n"),
    ("indented_line_comment", "  # {s}\n"),
    ("trailing_comment", "value = 1 # {s}\n"),
    ("comment_after_interpolation", 'value = "#{{1}}" # {s}\n'),
    ("comment_after_hash_in_string", 'value = "a # b" # {s}\n'),
]
_BLOCK_FORMS: list[tuple[str, str, int | None]] = [
    ("begin_end", "=begin\n{s}\n=end\n", ISSUE_BEGIN_END),
    ("begin_end_rdoc_tag", "=begin rdoc\n{s}\n=end\n", ISSUE_BEGIN_END),
    ("begin_end_then_code", "=begin\nnote\n{s}\nmore\n=end\nvalue = 1\n", ISSUE_BEGIN_END),
    ("data_section", "value = 1\n__END__\n{s}\n", ISSUE_DATA_SECTION),
]


@pytest.mark.parametrize("family", sorted(RUBY_FAMILIES))
@pytest.mark.parametrize(("form", "template"), _LINE_FORMS)
def test_ruby_line_comment_forms_hide_the_keyword(family: str, form: str, template: str):
    assert _hits(family, template.format(s=RUBY_FAMILIES[family])) == 0, f"{form} leak for ruby.{family}"


def _block_params():
    for family in sorted(RUBY_FAMILIES):
        for form, template, issue in _BLOCK_FORMS:
            yield pytest.param(family, form, template, marks=_xf(issue), id=f"{family}-{form}")


@pytest.mark.parametrize(("family", "form", "template"), list(_block_params()))
def test_ruby_block_comment_forms_hide_the_keyword(family: str, form: str, template: str):
    assert _hits(family, template.format(s=RUBY_FAMILIES[family])) == 0, f"{form} leak for ruby.{family}"


@pytest.mark.parametrize("family", sorted(RUBY_FAMILIES))
def test_ruby_indented_begin_is_not_a_comment(family: str):
    """Spec: `=begin` / `=end` only open a comment in column 0; indented they are a syntax error, not a comment."""
    src = " =begin\n " + RUBY_FAMILIES[family] + "\n =end\n"
    assert _hits(family, src) >= 1


@pytest.mark.parametrize("family", sorted(RUBY_FAMILIES))
def test_ruby_heredoc_body_is_a_string_and_counts_today(family: str):
    """A heredoc is a string (strings count by design, #2535). Recorded, not endorsed."""
    src = "value = <<~EOS\n  " + RUBY_FAMILIES[family] + "\nEOS\n"
    assert _hits(family, src) >= 1


# ---------------------------------------------------------------------------------------------
# G6: strings.
# ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("family", sorted(RUBY_FAMILIES))
def test_ruby_keyword_in_a_string_counts_today(family: str):
    assert _hits(family, 'value = "' + RUBY_FAMILIES[family] + '"\n') >= 1


@pytest.mark.parametrize("family", sorted(RUBY_FAMILIES))
@pytest.mark.parametrize(
    "prefix",
    ['url = "http://x"', 'url = "a \\" b"', "url = 'it\\'s'", 'url = "a # b"'],
    ids=["url", "escaped_dq", "escaped_sq", "hash_in_string"],
)
def test_ruby_string_then_comment_boundary(family: str, prefix: str):
    assert _hits(family, f"{prefix} # {RUBY_FAMILIES[family]}\n") == 0


@pytest.mark.parametrize("family", sorted(RUBY_FAMILIES))
def test_ruby_hash_inside_a_string_does_not_start_a_comment(family: str):
    assert _hits(family, 'url = "a # b"; ' + RUBY_FAMILIES[family] + "\n") >= 1


# ---------------------------------------------------------------------------------------------
# G5 (Req B): every alternation branch embedded in a longer identifier must not count.
# ---------------------------------------------------------------------------------------------
_BOUNDARY: list[tuple[str, str]] = (
    [
        # auth_middleware: prefix and suffix on every branch
        ("auth_middleware", "my_before_action :authenticate_user"),
        ("auth_middleware", "my_authenticate_user!"),
        ("auth_middleware", "redirect_to root_path unless my_user_signed_in?"),
        ("auth_middleware", "redirect_to root_path unless user_signed_in_x?"),
        ("auth_middleware", "head :forbidden unless scan? :read"),
        ("auth_middleware", "my_authorize @post"),
        ("auth_middleware", "authorized @post"),
        ("auth_middleware", "user.my_valid_password?(params[:password])"),
        # import: prefix and suffix on every branch
        ("import", "my_require 'json'"),
        ("import", "requires 'json'"),
        ("import", "my_require_relative 'helper'"),
        ("import", "my_load 'tasks/seed.rb'"),
        ("import", "payload 'tasks/seed.rb'"),
        ("import", "my_autoload :Parser, 'my/parser'"),
        ("import", "autoloaded :Parser, 'my/parser'"),
        # telemetry: prefix on the capitalised class branches, suffix on the level
        ("telemetry", "MyLogger.new.error(message)"),
        ("telemetry", "MySemanticLogger.fatal(message)"),
        ("telemetry", "Rails.logger.information(message)"),
        ("telemetry", "app_logger.debugging(message)"),
    ]
    + [("comprehensions", f"result = items.my_{b} {{ |item| item }}") for b in BRANCH_POSITIVES["comprehensions"]]
    + [("comprehensions", f"result = items.{b}_x {{ |item| item }}") for b in BRANCH_POSITIVES["comprehensions"]]
)


@pytest.mark.parametrize(("family", "src"), _BOUNDARY)
def test_ruby_identifier_boundaries(family: str, src: str):
    assert _hits(family, src + "\n") == 0


# ---------------------------------------------------------------------------------------------
# Req D: negative controls from the contracts and the validity checklist.
# ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("family", "src"),
    [
        # telemetry: a bare print / puts / warn is debug_prints, not telemetry; level/constants are not log calls
        ("telemetry", "puts 'starting'"),
        ("telemetry", "$stdout.puts 'starting'"),
        ("telemetry", "warn 'starting'"),
        ("telemetry", "app_logger.level = Logger::INFO"),
        ("telemetry", "user.info"),
        # comprehensions: a definition or a longer method name is not a transform call
        ("comprehensions", "def map\n  yield\nend"),
        ("comprehensions", "items.map_with_index { |item, i| item }"),
        # import: a require whose argument is not a literal path is not a binding of a file
        ("import", "require name"),
        ("import", "def require_all(dir)"),
        # auth_middleware: a filter that is not authentication, a stem without the bang
        ("auth_middleware", "before_action :set_user"),
        ("auth_middleware", "authenticate_user.name"),
    ],
)
def test_ruby_cross_family_negative_controls(family: str, src: str):
    assert _hits(family, src + "\n") == 0


# Leaks and false negatives found by this suite (each pinned to its issue).
@pytest.mark.parametrize(
    ("family", "src"),
    [
        pytest.param("import", 'data = YAML.load("a: 1")', marks=_xf(ISSUE_LOAD_RECEIVER), id="yaml_load_is_parsing"),
        pytest.param("import", 'data = JSON.load("{}")', marks=_xf(ISSUE_LOAD_RECEIVER), id="json_load_is_parsing"),
        pytest.param("import", "load = 'x'", marks=_xf(ISSUE_LOAD_RECEIVER), id="load_variable"),
        pytest.param(
            "auth_middleware", "def authenticate_user!", marks=_xf(ISSUE_AUTH_DEF), id="definition_is_not_invocation"
        ),
    ],
)
def test_ruby_precision_leaks_pinned(family: str, src: str):
    assert _hits(family, src + "\n") == 0


@pytest.mark.parametrize(
    ("family", "src"),
    [
        pytest.param("telemetry", "logger.info(message)", marks=_xf(ISSUE_BARE_LOGGER), id="bare_logger_info"),
        pytest.param("telemetry", "@logger.warn(message)", marks=_xf(ISSUE_BARE_LOGGER), id="ivar_logger_warn"),
        pytest.param(
            "comprehensions",
            "total = items.inject(0) { |sum, item| sum + item }",
            marks=_xf(ISSUE_BLOCK_ARGS),
            id="inject_with_initial_value",
        ),
        pytest.param(
            "comprehensions",
            "groups = items.each_with_object([]) { |item, acc| acc << item }",
            marks=_xf(ISSUE_BLOCK_ARGS),
            id="each_with_object_always_takes_a_memo",
        ),
    ],
)
def test_ruby_authentic_forms_the_rule_misses_pinned(family: str, src: str):
    assert _hits(family, src + "\n") >= 1
