"""#4825: every path-filtered workflow triggers on the scripts it runs and on the crucible pins it reads."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workflow_inputs as wi  # noqa: E402


@pytest.mark.parametrize(
    ("patterns", "path", "hit"),
    [
        (["tests/tools/*.py"], "tests/tools/x.py", True),
        (["tests/tools/*.py"], "tests/tools/sub/x.py", False),  # `*` stays in one segment
        (["gitgalaxy/**"], "gitgalaxy/a/b/c.py", True),
        (["**/*.md"], "README.md", True),
        (["gitgalaxy/**", "!gitgalaxy/tools/cobol_to_java/**"], "gitgalaxy/tools/cobol_to_java/det/x.py", False),
        (["gitgalaxy/**", "!gitgalaxy/x/**", "gitgalaxy/x/keep.py"], "gitgalaxy/x/keep.py", True),  # last match wins
        (["tests/tree_sitter_accuracy_baseline_*.json"], "tests/tree_sitter_accuracy_baseline_c.json", True),
    ],
)
def test_github_path_filter_globs(patterns, path, hit):
    assert wi.triggers(patterns, path) is hit


def test_inputs_finds_scripts_and_pins_and_drops_the_checkout_prefix():
    text = "run: |\n  ref=$(python3 gitgalaxy/tests/tools/crucible_pins.py get language)\n  python tests/tools/pr_check.py 1\n"
    assert wi.inputs(text) == {"tests/tools/crucible_pins.py", "tests/tools/pr_check.py", wi.PINS}


def test_every_path_filtered_workflow_triggers_on_what_it_reads():
    """A missed trigger means the gate silently does not run; a later, unrelated PR then fails instead."""
    gaps = wi.gaps()
    assert not gaps, "add these to the workflow's pull_request paths (or to ALLOW, with the reason): " + "; ".join(
        f"{wf}: {f}" for wf, f in gaps
    )
