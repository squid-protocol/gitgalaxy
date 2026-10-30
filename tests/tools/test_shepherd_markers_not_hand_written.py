"""#6694: an agent never writes a shepherd marker. Only the shepherd's own code may spell one out.

Every agent-facing surface (rules, agent briefs, skills, docs, non-shepherd workflows, tool scripts) is scanned for a
marker comment. The two files that forbid it by name and the shepherd itself are the only places allowed to hold one.
"""

import re
import subprocess
from pathlib import Path

from gitgalaxy.core.source_text import read_source

REPO = Path(__file__).resolve().parents[2]

MARKER = re.compile(r"<!--\s*shepherd[:-](?:approved|update|main-merge|digest)")
# Where a marker string is legitimate: the shepherd that writes and parses it, its tests, and the files that forbid it.
ALLOWED = {
    "tests/tools/shepherd_gh.py",
    "tests/tools/test_shepherd_gh.py",
    "tests/tools/test_shepherd_markers_not_hand_written.py",
    ".claude/rules/shepherd-markers.md",
    ".claude/agents/gitgalaxy-pr-worker.md",
}
SURFACES = (".claude/", "docs/", ".github/", "tests/tools/", "gitgalaxy/tools/")
TEXT = (".md", ".yml", ".yaml", ".py", ".sh", ".txt", ".toml")


def _tracked():
    out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True).stdout
    return [p for p in out.splitlines() if p.startswith(SURFACES) and p.endswith(TEXT)]


def test_no_agent_surface_spells_a_shepherd_marker():
    offenders = []
    for rel in _tracked():
        if rel in ALLOWED or Path(rel).name.startswith("shepherd-"):
            continue
        path = REPO / rel
        if path.is_file() and MARKER.search(read_source(path).text):
            offenders.append(rel)
    assert not offenders, (
        "a shepherd marker is the shepherd's to write (.claude/rules/shepherd-markers.md, #6694); "
        f"remove it from: {offenders}"
    )


def test_the_rule_and_the_worker_brief_both_forbid_hand_written_markers():
    for rel in (".claude/rules/shepherd-markers.md", ".claude/agents/gitgalaxy-pr-worker.md"):
        text = (REPO / rel).read_text(encoding="utf-8")
        assert "shepherd:merge" in text and "shepherd:approved" in text, rel
        assert re.search(r"(?i)never[^.\n]{0,80}(marker|shepherd:approved)", text), rel


def test_the_scan_catches_a_marker_and_ignores_the_label():
    assert MARKER.search("gh pr comment 7 --body '<!-- shepherd:approved sha=abc by=me -->'")
    assert MARKER.search("<!-- shepherd-update from=abc -->")
    assert not MARKER.search("add the `shepherd:merge` label")
