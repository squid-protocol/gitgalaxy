"""The append-only language-cost log merges as a union, so two PRs that each append a row never conflict."""

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LOG = "gitgalaxy/standards/language_addition_costs.jsonl"


def test_the_language_cost_log_is_merged_as_a_union():
    attrs = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert f"{LOG} merge=union" in attrs.splitlines()


def test_git_resolves_the_log_with_the_union_driver():
    out = subprocess.run(["git", "check-attr", "merge", "--", LOG], cwd=REPO_ROOT, capture_output=True, text=True)
    assert out.returncode == 0 and out.stdout.strip().endswith(": merge: union"), out.stdout


def test_every_row_is_one_complete_json_object_so_a_union_stays_valid():
    text = (REPO_ROOT / LOG).read_text(encoding="utf-8")
    assert text.endswith("\n")
    for line in text.splitlines():
        assert isinstance(json.loads(line), dict)
