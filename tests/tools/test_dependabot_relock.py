# ruff: noqa: S101
"""Tests for tests/tools/dependabot_relock.py (the pure parts; the git and uv steps run in the workflow)."""

from __future__ import annotations

from tests.tools.dependabot_relock import (
    bumped,
    outside_req_dirs,
    parse_dependabot_metadata,
    parse_pins,
    upgrade_args,
)

MAIN = """certifi==2026.7.22 \\
    --hash=sha256:aa
gitgalaxy==2.11.0 \\
    --hash=sha256:bb
numpy==2.2.6 ; python_full_version < '3.11' \\
    --hash=sha256:cc
numpy==2.5.4 ; python_full_version >= '3.12' \\
    --hash=sha256:dd
"""

# What Dependabot wrote on #5792: a certifi bump, plus a flattened numpy and an extras-spelled gitgalaxy pin.
DEPENDABOT = """certifi==2026.10.19 \\
    --hash=sha256:ee
gitgalaxy[full]==2.11.0 \\
    --hash=sha256:bb
numpy==2.5.4 \\
    --hash=sha256:dd
"""


def test_parse_pins_normalises_names_and_drops_extras():
    pins = parse_pins("Tree_Sitter.Language-Pack==1.21.1 \\\ngitgalaxy[full]==2.11.0 \\\n")
    assert pins == {"tree-sitter-language-pack": {"1.21.1"}, "gitgalaxy": {"2.11.0"}}


def test_only_the_real_bump_is_relocked():
    # the flattened numpy and the respelled gitgalaxy pin add no version main lacks: only certifi moves
    assert bumped(parse_pins(MAIN), parse_pins(DEPENDABOT)) == {"certifi": {"2026.10.19"}}


def test_upgrade_args_pin_an_exact_target_when_there_is_one():
    assert upgrade_args({"certifi": {"2026.10.19"}, "ruff": {"0.17.0"}}) == [
        "-P",
        "certifi==2026.10.19",
        "-P",
        "ruff==0.17.0",
    ]
    assert upgrade_args({"numpy": {"2.4.7", "2.5.5"}}) == ["-P", "numpy"]


def test_a_pr_outside_the_requirement_sets_is_refused():
    assert outside_req_dirs(["ci/requirements/lint.txt", "templates/requirements/full.txt"]) == []
    assert outside_req_dirs(["ci/requirements/lint.txt", "tests/tools/pin_requirements.py"]) == [
        "tests/tools/pin_requirements.py"
    ]


def test_parse_dependabot_metadata_catches_unsafe_package_bumps_dropped_from_txt():
    # On #6300 Dependabot's pip-compile deleted setuptools from bootstrap.txt instead of writing 84.1.0;
    # the commit/PR YAML footer still names the exact bump.
    commit_msg = (
        "build(deps): bump setuptools from 84.0.0 to 84.1.0 in /ci/requirements\n\n"
        "---\n"
        "updated-dependencies:\n"
        "- dependency-name: setuptools\n"
        "  dependency-version: 84.1.0\n"
        "  dependency-type: direct:production\n"
        "...\n"
    )
    assert parse_dependabot_metadata(commit_msg) == {"setuptools": {"84.1.0"}}


def test_parse_dependabot_metadata_skips_a_blank_version_without_reading_the_next_line():
    # #7119: a grouped update dropped setuptools and left dependency-version blank; the old pattern's \s* crossed the
    # newline and read `dependency-type:` as the version, which uv refused, so the relock never ran.
    commit_msg = (
        "---\n"
        "updated-dependencies:\n"
        "- dependency-name: pip\n"
        "  dependency-version: 26.2.2\n"
        "  dependency-type: direct:production\n"
        "- dependency-name: setuptools\n"
        "  dependency-version:\n"
        "  dependency-type: direct:production\n"
        "- dependency-name: ruff\n"
        "  dependency-version: 0.17.2\n"
        "...\n"
    )
    assert parse_dependabot_metadata(commit_msg) == {"pip": {"26.2.2"}, "ruff": {"0.17.2"}}
