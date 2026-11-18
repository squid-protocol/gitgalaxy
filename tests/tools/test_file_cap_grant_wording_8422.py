"""#8422: the worker rules and the orchestrator checklist agree on when a file-cap exception is granted."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CATEGORIES = ("atomic rename", "pin bump", "new language profile", "mechanical one-line change")


@pytest.mark.parametrize("rel", [".claude/agents/gitgalaxy-pr-worker.md", ".claude/skills/box-capacity/SKILL.md"])
def test_each_surface_names_every_grant_category(rel):
    text = (ROOT / rel).read_text(encoding="utf-8")
    for category in CATEGORIES:
        assert category in text, f"{rel}: grant category {category!r} missing"
    assert "--file-cap-exception" in text, rel


def test_worker_cannot_grant_itself_and_equivalence_is_one_program():
    worker = (ROOT / ".claude/agents/gitgalaxy-pr-worker.md").read_text(encoding="utf-8")
    assert "cannot grant yourself a file-cap exception" in worker
    assert "one program per PR" in worker
    assert "Needs a file-cap grant" in worker
    checklist = (ROOT / ".claude/skills/box-capacity/SKILL.md").read_text(encoding="utf-8")
    assert "one program per PR" in checklist
    assert "Needs a file-cap grant" in checklist
