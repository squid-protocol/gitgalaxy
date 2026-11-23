"""#8430: the XGBoost malware classifier is removed; no shipped CI surface may still name it or gate on it."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SURFACE = [
    "action.yml",
    "azure-pipelines.yml",
    "bitbucket-pipelines.yml",
    ".github/workflows/gitgalaxy.yml",
    "templates/scan.yml",
    "templates/gitlab/scan.yml",
    "templates/azure/azure-pipelines.yml",
    "templates/bitbucket/bitbucket-pipelines.yml",
    "templates/github/gitgalaxy-pipeline.yml",
]
GONE = ("fail-on-malware", "ML Malware Gate", "ML Threat Inference", "xgboost")


@pytest.mark.parametrize("rel", SURFACE)
def test_shipped_surface_has_no_removed_classifier_claim(rel):
    text = (ROOT / rel).read_text(encoding="utf-8").lower()
    found = [g for g in GONE if g.lower() in text]
    assert not found, f"{rel} still mentions the removed classifier: {found}"
