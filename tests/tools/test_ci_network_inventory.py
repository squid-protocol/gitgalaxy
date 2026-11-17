# ruff: noqa: S101
"""#8424: the CI network inventory classifies every fetch kind, and docs/ci_network_inventory.md is current."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ci_network_inventory as inv

RETRY = "tests/tools/ci_retry.sh 4 10 -- "


def _run(script, **extra):
    return inv.classify_step({"run": script, **extra})


@pytest.mark.parametrize(
    ("script", "kind"),
    [
        ("pip install -r requirements.txt", "pip"),
        ("python -m pip install --upgrade pip", "pip"),
        (".venv/bin/pip3 download foo", "pip"),
        ("sudo apt-get install -y universal-ctags", "apt"),
        ("npm install typescript@6.0.2", "node-packages"),
        ("rustup toolchain install 1.90.0", "toolchain"),
        ("docker pull ghcr.io/x/y:1", "docker"),
        ("docker build -q -t x .", "docker"),
        ("mvn -q package", "maven-gradle"),
        ("./gradlew build", "maven-gradle"),
        ("git clone --depth 1 https://example.invalid/r.git", "git-fetch"),
        ("curl -fsSL https://example.invalid/x -o x", "http-download"),
        ("gh release download v1 -R o/r", "gh-download"),
        ("gh api repos/o/r/issues/1", "gh-api"),
        ("python -c 'from tree_sitter_language_pack import get_parser; get_parser(\"cobol\")'", "grammar"),
        ("cd x && pip install foo", "pip"),
        ("FOO=1 pip install foo", "pip"),
    ],
)
def test_every_kind_is_recognised_and_bare_by_default(script, kind):
    assert (kind, "bare") in _run(script)


def test_ci_retry_wraps_the_command_including_across_a_quoted_block():
    assert _run(RETRY + "pip install foo") == [("pip", "wrapped")]
    multi = RETRY + "bash -c '\n  pip install foo\n  pip install bar\n'"
    assert _run(multi) == [("pip", "wrapped")]
    cont = RETRY + "docker pull \\\n  img:1"
    assert _run(cont) == [("docker", "wrapped")]


def test_continue_on_error_is_advisory_and_a_tool_that_retries_is_in_tool():
    assert _run("pip install foo", **{"continue-on-error": True}) == [("pip", "advisory")]
    assert ("tool-entry", "in-tool") in _run("python tests/tools/proof_sweep.py --cases x")


@pytest.mark.parametrize(
    "script",
    [
        "echo 'pip install foo'",
        "grep -n 'docker pull' f.yml",
        "# pip install foo",
        "pytest tests/tools/test_pip_install_lint.py",
    ],
)
def test_a_word_inside_a_comment_echo_or_grep_is_not_a_fetch(script):
    assert _run(script) == []


@pytest.mark.parametrize(
    ("uses", "kind"),
    [
        ("actions/upload-artifact@abc # v7", "artifact-upload"),
        ("actions/download-artifact@abc", "artifact-download"),
        ("actions/cache/restore@abc", "cache"),
        ("actions/setup-java@abc", "setup-toolchain"),
    ],
)
def test_action_steps_are_classified_and_advisory_when_continue_on_error(uses, kind):
    assert inv.classify_step({"uses": uses}) == [(kind, "action")]
    assert inv.classify_step({"uses": uses, "continue-on-error": True}) == [(kind, "advisory")]


def test_the_whole_workflow_directory_has_network_steps_of_every_guard():
    rows = inv.inventory()
    assert {r["guard"] for r in rows} == {"wrapped", "advisory", "in-tool", "action", "bare"}
    assert {"pip", "docker", "git-fetch", "grammar", "artifact-upload", "cache"} <= {r["kind"] for r in rows}


def test_the_inventory_doc_is_current():
    # a workflow change that adds, wraps or removes a network step regenerates the doc:
    #   python tests/tools/ci_network_inventory.py --write
    assert inv.DOC.read_text(encoding="utf-8") == inv.render(inv.inventory())
