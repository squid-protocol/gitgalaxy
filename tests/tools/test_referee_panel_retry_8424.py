"""#8424: every network line of the referee-panel installs and the cache-prune usage reads goes through ci_retry.sh."""

import re
from pathlib import Path

import yaml

WF = Path(__file__).resolve().parents[2] / ".github" / "workflows"
NET = re.compile(r"^\s*(?:git fetch|mvn |gh release download|gh api)")
CONTINUATION = re.compile(r"\\\s*$")


def _lines(name):
    wf = yaml.safe_load((WF / name).read_text(encoding="utf-8"))
    for job in wf["jobs"].values():
        for step in job.get("steps", []):
            for line in step.get("run", "").splitlines():
                yield step.get("name", ""), line


def test_referee_panel_fetches_are_wrapped():
    seen = [(n, ln) for n, ln in _lines("referee-panel.yml") if re.search(r"git fetch|\bmvn |gh release download", ln)]
    assert len(seen) == 6  # 3 git fetches, 2 mvn goals, 1 release download
    assert [ln for _, ln in seen if "ci_retry.sh" not in ln] == []


def test_cache_prune_usage_reads_are_wrapped_and_the_script_is_checked_out():
    text = (WF / "cache-prune.yml").read_text(encoding="utf-8")
    reads = [ln for ln in text.splitlines() if "gh api" in ln]
    assert len(reads) == 2 and all("ci_retry.sh" in ln for ln in reads)
    assert "tests/tools/ci_retry.sh" in text.split("sparse-checkout:")[1].split("sparse-checkout-cone-mode")[0]
