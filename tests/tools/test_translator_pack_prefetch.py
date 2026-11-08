"""#8100: a workflow that installs the `translator` extra fetches the tree-sitter COBOL grammar from GitHub on first
use; a timeout there failed a main run (Fact Cross-check). Each such workflow restores the pack cache and prefetches
the grammar through ci_retry.sh. A workflow not yet covered is listed in EXEMPT with the reason (a sibling gap)."""

import re
from pathlib import Path

import pytest

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
EXEMPT = {
    "det-sweep.yml": "3 jobs install the extra; pip is retried but the grammar fetch is not (sibling gap of #8100)",
    "ports-compile.yml": "builds a wheelhouse from the extra; no pack cache or prefetch yet (sibling gap of #8100)",
    "evidence-refresh.yml": "5 jobs install the extra; no pack cache or prefetch yet (sibling gap of #8100)",
}
INSTALLS = re.compile(r"\[translator\]")
CACHE = re.compile(r"path:\s*~/\.cache/tree-sitter-language-pack")
PREFETCH = re.compile(r"ci_retry\.sh\s+\d+\s+\d+\s+--\s+python\s+-c\s+.*get_parser\(")


def _installers():
    return sorted(p.name for p in WORKFLOWS.glob("*.yml") if INSTALLS.search(p.read_text(encoding="utf-8")))


def test_the_exempt_list_names_only_workflows_that_still_lack_the_prefetch():
    for name in EXEMPT:
        text = (WORKFLOWS / name).read_text(encoding="utf-8")
        assert INSTALLS.search(text), f"{name} no longer installs the translator: drop it from EXEMPT"
        assert not (CACHE.search(text) and PREFETCH.search(text)), f"{name} is covered now: drop it from EXEMPT"


@pytest.mark.parametrize("name", [n for n in _installers() if n not in EXEMPT])
def test_a_translator_workflow_caches_and_prefetches_the_grammar(name):
    text = (WORKFLOWS / name).read_text(encoding="utf-8")
    assert CACHE.search(text), f"{name}: restore ~/.cache/tree-sitter-language-pack (actions/cache/restore)"
    assert PREFETCH.search(text), f"{name}: prefetch with ci_retry.sh N S -- python -c '...get_parser(...)'"


def test_the_fact_crosscheck_workflow_is_covered():
    assert "fact-crosscheck.yml" in _installers()
    assert "fact-crosscheck.yml" not in EXEMPT
