# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""
Regression tests for issue #4917:
Aperture static-blob heuristic excluded 1,000+ line YAML files as
'Blocked (Static Asset Blob without Intent: N LOC)'.
Recognized CI/CD workflow and pipeline configurations are code, not static blobs.
Also tests that exclusions emit a single visible WARNING naming the file and reason.
"""

import logging
from pathlib import Path

import pytest

from gitgalaxy.core.aperture import ApertureFilter
from gitgalaxy.standards.gitgalaxy_config import APERTURE_CONFIG
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS


@pytest.fixture
def filter_engine(tmp_path):
    """Initializes ApertureFilter with real configuration and language definitions."""
    return ApertureFilter(
        root_dir=tmp_path,
        language_definitions=LANGUAGE_DEFINITIONS,
        aperture_config=APERTURE_CONFIG,
    )


def test_synthetic_workflow_under_github_workflows_not_excluded(filter_engine, tmp_path, caplog):
    """
    A 1,100-line synthetic GitHub workflow under .github/workflows/ is NOT excluded.
    No warning should be emitted for it.
    """
    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    workflow_file = workflow_dir / "ci.yml"

    lines = [
        "name: CI Workflow",
        "on:",
        "  push:",
        "    branches: [main]",
        "jobs:",
        "  build:",
        "    runs-on: ubuntu-latest",
        "    steps:",
        "      - name: Checkout",
        "        uses: actions/checkout@v4",
    ]
    step_num = 1
    while len(lines) < 1100:
        lines.append(f"      - name: Step {step_num}")
        lines.append(f"        run: echo 'running step {step_num}'")
        step_num += 1

    workflow_content = "\n".join(lines[:1100])
    workflow_file.write_text(workflow_content, encoding="utf-8")

    assert workflow_content.count("\n") + 1 == 1100

    with caplog.at_level(logging.WARNING):
        result = filter_engine.is_in_scope(workflow_file, content=workflow_content)

    assert result["is_in_scope"] is True
    assert result["classification"] == "source_code"
    assert result["reason"] is None
    assert "ci.yml" not in caplog.text


def test_synthetic_data_yaml_is_excluded_and_warns(filter_engine, tmp_path, caplog):
    """
    A 1,100-line synthetic data YAML (a long list of scalars) IS still excluded as a blob,
    and a visible WARNING line naming the file and reason is emitted.
    """
    data_file = tmp_path / "data.yml"

    lines = [f"- scalar_item_{i}" for i in range(1100)]
    data_content = "\n".join(lines)
    data_file.write_text(data_content, encoding="utf-8")

    assert data_content.count("\n") + 1 == 1100

    with caplog.at_level(logging.WARNING):
        result = filter_engine.is_in_scope(data_file, content=data_content)

    assert result["is_in_scope"] is False
    assert result["classification"] == "generated_noise"
    assert "Static Asset Blob without Intent: 1100 LOC" in (result.get("reason") or "")

    # The warning line is emitted naming the file and reason
    assert "data.yml" in caplog.text
    assert "Blocked (Static Asset Blob without Intent: 1100 LOC)" in caplog.text

    # Exactly one warning line per excluded file (no spam)
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 1
    assert "data.yml" in warnings[0].getMessage()
    assert "Static Asset Blob without Intent" in warnings[0].getMessage()


@pytest.mark.parametrize(
    "rel_path",
    [
        "action.yml",
        "action.yaml",
        ".gitlab-ci.yml",
        "bitbucket-pipelines.yml",
        "azure-pipelines.yml",
    ],
)
def test_recognized_pipeline_names_not_excluded(filter_engine, tmp_path, rel_path):
    """Recognized CI/CD filenames past 1,000 LOC are treated as code, not static blobs."""
    p = tmp_path / rel_path
    lines = ["jobs:", "  build:", "    steps:", "      - run: echo hello"]
    while len(lines) < 1100:
        lines.append(f"      - run: echo step_{len(lines)}")
    content = "\n".join(lines[:1100])
    p.write_text(content, encoding="utf-8")

    result = filter_engine.is_in_scope(p, content=content)
    assert result["is_in_scope"] is True


def test_custom_path_workflow_with_run_steps_keys_not_excluded(filter_engine, tmp_path):
    """A YAML file in a custom directory with many run:/steps:/jobs: keys is recognized as code."""
    custom_dir = tmp_path / "custom_ci"
    custom_dir.mkdir(parents=True)
    custom_file = custom_dir / "pipeline.yaml"

    lines = ["jobs:", "  test:", "    steps:"]
    lines.extend(f"      - run: echo step {i}" for i in range(1097))
    content = "\n".join(lines)
    custom_file.write_text(content, encoding="utf-8")

    result = filter_engine.is_in_scope(custom_file, content=content)
    assert result["is_in_scope"] is True


def test_evidence_refresh_workflow_dogfood(tmp_path):
    """Regression test for #4917 dogfooding: evidence-refresh.yml (1,010 lines) is admitted."""
    real_file = Path("/home/joe/Projects/gitgalaxy-agy-4917/.github/workflows/evidence-refresh.yml")
    if not real_file.is_file():
        pytest.skip("evidence-refresh.yml not found")

    content = real_file.read_text(encoding="utf-8")
    assert content.count("\n") + 1 >= 1000

    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    wf_copy = wf_dir / "evidence-refresh.yml"
    wf_copy.write_text(content, encoding="utf-8")

    engine = ApertureFilter(
        root_dir=tmp_path,
        language_definitions=LANGUAGE_DEFINITIONS,
        aperture_config=APERTURE_CONFIG,
    )
    result = engine.is_in_scope(wf_copy, content=content)
    assert result["is_in_scope"] is True
    assert result["classification"] == "source_code"
