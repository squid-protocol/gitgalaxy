"""
YAML (GitHub Actions / GitLab CI) extraction hardening (epic #813, issue
#843). See tests/extraction/how_to_harden_extraction.md for the methodology.

Covers all four extraction gauntlets for yaml in one file: func_start, args,
class_start, _dependency_capture. Migrated out of the four old monolithic
dict files (test_function_extraction_strict.py, test_args_extraction_strict.py,
test_class_extraction_strict.py, test_dependency_extraction_strict.py) --
yaml's entries were removed from those four when this file was added.
(test_args_extraction_strict.py and test_class_extraction_strict.py had no
yaml entry at all -- args and class_start had zero prior test coverage.)

Unlike most other languages in this epic, yaml's four rules don't map onto
"function/args/class/dependency" in the traditional sense -- this dict's
`_meta.target_version` scopes it specifically to CI/CD YAML (GitHub Actions /
GitLab CI), so the four gauntlets instead detect: a step's run/script block
(func_start), a step's `with:` input block (args), a job-block boundary
(class_start, including the reusable-workflow-call/container-job shape),
and an action/image reference (_dependency_capture). None of class_start's
alternatives capture a name (whole-match only, `pattern.groups == 0`), so
its cases use `expected_name=None` throughout.
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

YAML_RULES = LANGUAGE_DEFINITIONS["yaml"]["rules"]

# ==============================================================================
# FUNC_START (func_start) -- a step's run:/script: execution block
# ==============================================================================
FUNCTION_CASES: dict[str, Any] = {
    "valid": [
        # Modern idiom (carried forward)
        ("- run: echo hello", "run:"),
        ("script:", "script:"),
        # Syntax-era / dialect coverage
        ("- run: |\n    npm ci\n    npm test", "run:"),  # GH Actions block-scalar multi-line run
        ("before_script:\n  - npm ci", "before_script:"),  # GitLab CI
        ("after_script:\n  - cleanup.sh", "after_script:"),  # GitLab CI
        ("- name: Build\n  run: make", "run:"),  # run: as the second key under a named step
    ],
    "invalid": [
        "TargetFunc:",  # carried-forward: unrelated key lookalike
        "steps:",  # carried-forward: structural key, not an execution block
        "runs-on: ubuntu-latest",  # `run` substring lookalike -- must not match "run:"
        "# - run: rm -rf /",  # commented-out step
        "my-run: foo",  # `run:` substring lookalike inside a longer key name
    ],
    "pathological": [
        ("- \t run: \n", "run:"),  # carried-forward
        ("-   run:   |\n  npm test", "run:"),  # extreme horizontal spacing before block scalar
        ("  -\trun:\t>\n    echo hi", "run:"),  # tab spacing, folded-scalar indicator
    ],
}


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["valid"])
def test_yaml_func_start_valid(payload, expected_name):
    assert_valid_match(YAML_RULES["func_start"], payload, expected_name, "yaml.func_start")


@pytest.mark.parametrize("payload", FUNCTION_CASES["invalid"])
def test_yaml_func_start_invalid(payload):
    assert_invalid_no_match(YAML_RULES["func_start"], payload, "yaml.func_start")


@pytest.mark.parametrize("payload,expected_name", FUNCTION_CASES["pathological"])
def test_yaml_func_start_pathological(payload, expected_name):
    assert_pathological_match(YAML_RULES["func_start"], payload, expected_name, "yaml.func_start")


def test_yaml_func_start_redos_immunity():
    func_start = YAML_RULES["func_start"]
    assert_redos_immune(func_start, "- " * 100000 + "run:", timeout_sec=3.0)
    assert func_start.search("- run: echo hello")


# ==============================================================================
# ARGS (args) -- a step's `with:` input block
# ==============================================================================
ARGS_CASES: dict[str, Any] = {
    "valid": [
        (
            "- uses: actions/setup-node@v4\n  with:\n    node-version: '18'\n    cache: 'npm'",
            "with:",
        ),
        (
            "with: # inputs for this action\n  node-version: '18'",
            "with:",
        ),  # trailing same-line comment on the `with:` header -- was a real bug, now fixed
    ],
    "invalid": [
        "with: []",  # empty inline mapping, no indented key:value lines follow
        "steps:\n  - run: npm test",  # unrelated section
    ],
    "pathological": [
        (
            "- uses: actions/setup-node@v4\n  with: #\n    node-version: '18'\n    cache: 'npm'\n    always-auth: 'false'",
            "with:",
        ),  # bare trailing `#` with no comment text, plus a deep multi-key block
    ],
}


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["valid"])
def test_yaml_args_valid(payload, expected_name):
    assert_valid_match(YAML_RULES["args"], payload, expected_name, "yaml.args")


@pytest.mark.parametrize("payload", ARGS_CASES["invalid"])
def test_yaml_args_invalid(payload):
    assert_invalid_no_match(YAML_RULES["args"], payload, "yaml.args")


@pytest.mark.parametrize("payload,expected_name", ARGS_CASES["pathological"])
def test_yaml_args_pathological(payload, expected_name):
    assert_pathological_match(YAML_RULES["args"], payload, expected_name, "yaml.args")


def test_yaml_args_trailing_comment_regression():
    """
    Regression test for a real bug (epic #813/#843): `with:` required an
    immediately-following newline, so a trailing same-line comment (`with: #
    inputs for this action`, a real authoring style) broke the match
    entirely.
    """
    args = YAML_RULES["args"]
    assert args.search("with: # inputs\n  node-version: '18'"), "trailing comment on with: header regressed"


def test_yaml_args_comment_only_line_before_first_key_supported():
    """
    Documents that a full-line comment BETWEEN the `with:` header and the
    first real input key (`with:\\n  # first input\\n  node-version: '18'`)
    NOW matches, thanks to the fix that allows up to 10 lines of comments
    or blank lines before the first key-value pair.
    """
    args = YAML_RULES["args"]
    comment_before_first_key = "with:\n  # first input\n  node-version: '18'"
    assert args.search(comment_before_first_key), "regex should now support this previously known limitation"


def test_yaml_args_redos_immunity():
    args = YAML_RULES["args"]
    assert_redos_immune(args, "with:\n" + "  key: val\n" * 100000, timeout_sec=3.0)
    assert args.search("with:\n  node-version: '18'")


# ==============================================================================
# CLASS_START (class_start) -- a job-block boundary (jobs:, workflow_call:,
# or a reusable-workflow-call/container job identified by its uses:/image:)
# ==============================================================================
CLASS_CASES: dict[str, Any] = {
    "valid": [
        ("jobs:\n  build:\n    runs-on: ubuntu-latest", None),
        ("on:\n  workflow_call:", None),
        (
            "test:\n  image: node:18\n  script:\n    - npm test",
            None,
        ),  # GitLab CI job with a direct image: child
        (
            "call-workflow:\n  uses: ./.github/workflows/reusable.yml",
            None,
        ),  # reusable-workflow-call job, uses: as the immediate first key
    ],
    "invalid": [
        "deploy:\n  runs-on: ubuntu-latest\n  steps:\n    - run: echo hi",  # ordinary job, not a call/container shape
        "# jobs:",  # commented-out declaration
    ],
    "pathological": [
        (
            "call-workflow:\n  needs: [build]\n  if: success()\n  uses: ./.github/workflows/reusable.yml",
            None,
        ),  # reusable-workflow-call job with intervening keys before uses: -- was a real bug, now fixed
        (
            "call-workflow:\n  needs: [build]\n  if: success()\n  permissions:\n    contents: read\n  uses: ./.github/workflows/reusable.yml",
            None,
        ),  # deeper intervening-key stacking
    ],
}


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["valid"])
def test_yaml_class_start_valid(payload, expected_name):
    assert_valid_match(YAML_RULES["class_start"], payload, expected_name, "yaml.class_start")


@pytest.mark.parametrize("payload", CLASS_CASES["invalid"])
def test_yaml_class_start_invalid(payload):
    assert_invalid_no_match(YAML_RULES["class_start"], payload, "yaml.class_start")


@pytest.mark.parametrize("payload,expected_name", CLASS_CASES["pathological"])
def test_yaml_class_start_pathological(payload, expected_name):
    assert_pathological_match(YAML_RULES["class_start"], payload, expected_name, "yaml.class_start")


def test_yaml_class_start_intervening_keys_regression():
    """
    Regression test for a real bug (epic #813/#843): the reusable-workflow-
    call/container-job detection required `uses:`/`image:` to be the
    LITERAL FIRST line after the job name -- but real jobs of this shape
    routinely have other keys (`needs:`, `if:`, `permissions:`, etc.)
    before `uses:`/`image:`. Fixed with a bounded (max 10) step-over for
    intervening key:value lines.
    """
    class_start = YAML_RULES["class_start"]
    assert class_start.search("call-workflow:\n  needs: [build]\n  uses: ./.github/workflows/reusable.yml"), (
        "intervening-key job detection regressed"
    )
    # Must still NOT match an ordinary job with a steps: list -- the bounded
    # step-over must not bleed past unrelated job content into a false positive.
    assert not class_start.search(
        "deploy:\n  runs-on: ubuntu-latest\n  steps:\n    - name: Deploy\n      run: ./deploy.sh"
    ), "bounded intervening-key step-over incorrectly matched an ordinary job"


def test_yaml_class_start_redos_immunity():
    class_start = YAML_RULES["class_start"]
    assert_redos_immune(class_start, "job:\n" + "  key: val\n" * 100000, timeout_sec=3.0)
    assert class_start.search("call-workflow:\n  needs: [build]\n  uses: ./.github/workflows/reusable.yml")


# ==============================================================================
# DEPENDENCY (_dependency_capture) -- an action or container image reference
# ==============================================================================
DEPENDENCY_CASES: dict[str, Any] = {
    "valid": [
        ("uses: actions/checkout@v3", "actions/checkout@v3"),
        ("image: node:18-alpine", "node:18-alpine"),
        (
            'uses: "actions/checkout@v4"',
            "actions/checkout@v4",
        ),  # double-quoted value -- was a real bug, now fixed
        (
            "uses: 'actions/checkout@v4'",
            "actions/checkout@v4",
        ),  # single-quoted variant of the same fix
        ("- uses: actions/checkout@v4 # pinned", "actions/checkout@v4"),  # trailing comment must not get swallowed
    ],
    "invalid": [
        "description: 'image setup'",  # carried-forward: unrelated key lookalike
        "important: uses",  # substring-of-keyword lookalike
    ],
    "pathological": [
        ("image: \n postgres:15", "postgres:15"),  # carried-forward: vertical spacing
        ("uses: \n  'actions/checkout@v4'", "actions/checkout@v4"),  # vertical spacing + quoted value
    ],
}


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["valid"])
def test_yaml_dependency_capture_valid(payload, expected_path):
    assert_valid_dependency_match(YAML_RULES["_dependency_capture"], payload, expected_path, "yaml._dependency_capture")


@pytest.mark.parametrize("payload", DEPENDENCY_CASES["invalid"])
def test_yaml_dependency_capture_invalid(payload):
    assert_invalid_no_match(YAML_RULES["_dependency_capture"], payload, "yaml._dependency_capture")


@pytest.mark.parametrize("payload,expected_path", DEPENDENCY_CASES["pathological"])
def test_yaml_dependency_capture_pathological(payload, expected_path):
    assert_pathological_dependency_match(
        YAML_RULES["_dependency_capture"], payload, expected_path, "yaml._dependency_capture"
    )


def test_yaml_dependency_capture_quoted_value_regression():
    """
    Regression test for a real bug (epic #813/#843): the bare capture class
    required the value to start immediately with an identifier character, so
    a quoted `uses:`/`image:` value (a real, if less common, authoring style
    -- e.g. for yamllint rules requiring consistent scalar quoting) never
    matched at all.
    """
    dep = YAML_RULES["_dependency_capture"]
    m = dep.search('uses: "actions/checkout@v4"')
    captured = next((g for g in m.groups() if g), None) if m else None
    assert captured == "actions/checkout@v4", "quoted uses: value capture regressed"


def test_yaml_dependency_capture_known_limitation_templated_value_not_supported():
    """
    Documents a known, deliberately-NOT-fixed limitation: a GitHub Actions
    expression used as the entire image reference (`image: ${{
    vars.REGISTRY }}/myimage:latest`, a real but comparatively rare pattern
    for dynamic/templated container images in advanced reusable workflows)
    does not match -- `${`/`}` aren't in the identifier character class.
    Judged out of scope: broadening the class to admit `$`/`{`/`}` risks
    capturing unrelated GitHub Actions expression syntax as if it were part
    of a plain path, for a pattern that's uncommon relative to the
    quoted-value fix above.
    """
    dep = YAML_RULES["_dependency_capture"]
    templated = "image: ${{ vars.REGISTRY }}/myimage:latest"
    assert not dep.search(templated), "documents current (expected, not-yet-fixed) regex behavior"


def test_yaml_dependency_capture_redos_immunity():
    dep = YAML_RULES["_dependency_capture"]
    assert_redos_immune(dep, "uses: '" + "a" * 100000, timeout_sec=3.0)
    assert dep.search("uses: actions/checkout@v4")
