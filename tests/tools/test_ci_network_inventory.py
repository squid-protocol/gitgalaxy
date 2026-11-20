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


# --- the shrink-only lint (#8424, checklist c:2a39ee9b and c:2f8322e8) ---------------------------------------------

_FETCHES = [
    "pip install foo",
    "sudo apt-get install -y x",
    "npm install x",
    "rustup toolchain install 1.90.0",
    "docker pull x:1",
    "mvn -q package",
    "git clone https://example.invalid/r.git",
    "curl -fsSL https://example.invalid/x",
    "gh release download v1 -R o/r",
    "gh api repos/o/r/issues/1",
]


def _keys(script, **extra):
    rows = [
        {"workflow": "w.yml", "job": "j", "step": "s", "kind": k, "guard": g}
        for k, g in inv.classify_step({"run": script, **extra})
    ]
    return inv.bare_keys(rows)


@pytest.mark.parametrize("script", _FETCHES)
def test_a_bare_fetch_of_every_kind_is_a_lint_key_and_a_wrapped_or_advisory_one_is_not(script):
    assert _keys(script)
    assert not _keys(RETRY + script)
    assert not _keys(script, **{"continue-on-error": True})


def test_every_bare_step_and_advisory_upload_is_in_the_baseline_and_the_baseline_only_shrinks():
    import json

    base = json.loads(inv.BASELINE.read_text(encoding="utf-8"))
    # NEW: wrap the step in tests/tools/ci_retry.sh (or mark an advisory upload continue-on-error: true).
    # STALE: delete the entry (python tests/tools/ci_network_inventory.py --write-baseline).
    assert inv.baseline_problems(base, inv.current_baseline()) == []


def test_baseline_problems_names_new_and_stale_entries():
    now = {"bare": ["a|j|s|pip"], "advisory_uploads": []}
    assert inv.baseline_problems({"bare": ["a|j|s|pip"], "advisory_uploads": []}, now) == []
    assert inv.baseline_problems({"bare": [], "advisory_uploads": []}, now) == ["NEW bare: a|j|s|pip"]
    stale = inv.baseline_problems({"bare": ["a|j|s|pip"], "advisory_uploads": ["w|j|s"]}, now)
    assert stale == ["STALE advisory_uploads (fixed, delete the entry): w|j|s"]


def _wf(tmp_path, steps, name="w.yml"):
    import yaml

    (tmp_path / name).write_text(yaml.safe_dump({"jobs": {"j": {"steps": steps}}}), encoding="utf-8")
    return tmp_path


def _up(name, art, **extra):
    return {"name": name, "uses": "actions/upload-artifact@x", "with": {"name": art}, **extra}


def test_an_advisory_named_upload_must_be_non_fatal(tmp_path):
    wf = _wf(tmp_path, [_up("Keep the logs", "logs"), _up("Upload test times", "t", **{"continue-on-error": True})])
    assert inv.advisory_upload_offenders(wf) == ["w.yml|j|Keep the logs"]


def test_an_upload_a_later_job_downloads_is_a_hand_off_not_advisory(tmp_path):
    handoff = {"uses": "actions/download-artifact@x", "with": {"name": "det-durations"}}
    wf = _wf(tmp_path, [_up("Hand the durations on", "det-durations"), handoff])
    assert inv.advisory_upload_offenders(wf) == []
    pattern = {"uses": "actions/download-artifact@x", "with": {"pattern": "shard-*"}}
    wf = _wf(tmp_path, [_up("Keep this shard's results", "shard-${{ i }}"), pattern], name="p.yml")
    assert inv.advisory_upload_offenders(wf) == []


def test_an_upload_that_is_not_advisory_by_name_is_left_alone(tmp_path):
    assert inv.advisory_upload_offenders(_wf(tmp_path, [_up("Upload the SBOM", "sbom")])) == []
