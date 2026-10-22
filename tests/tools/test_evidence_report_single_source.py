"""#5206: the evidence report has one copy, on the `generated` branch. No doc, agent or skill on main links or names a
file of it that only `generated` keeps current (the stub README is the one allowed target), the directory holds no
other tracked file, and the stub says where the report is."""

import re
import subprocess
from pathlib import Path

from gitgalaxy.core.source_text import read_source

REPO = Path(__file__).resolve().parents[2]
REPORT_DIR = "docs/language_status/evidence_report"
# A path into the report directory naming a file or estate, `<estate>` placeholders included; the bare directory and
# the stub README are fine. The snapshot the tests read lives under tests/fixtures and is not matched.
FILE_REF = re.compile(r"(?<![\w/.-])(?:docs/language_status/)?evidence_report/(?!README\.md)[^\s`)\]>\"'|]+")


def _tracked(*patterns: str) -> list[str]:
    out = subprocess.run(["git", "ls-files", *patterns], cwd=REPO, capture_output=True, text=True, check=True)
    return out.stdout.splitlines()


def test_only_the_stub_readme_is_tracked_in_the_report_directory():
    assert _tracked(REPORT_DIR) == [f"{REPORT_DIR}/README.md"]


def test_no_doc_agent_or_skill_references_a_generated_only_report_file():
    hits = []
    for rel in _tracked("*.md", ".claude/*"):
        if rel.startswith(("tests/fixtures/", REPORT_DIR + "/")) or not (REPO / rel).is_file():
            continue
        for n, line in enumerate(read_source(REPO / rel).text.splitlines(), 1):
            for m in FILE_REF.finditer(line):
                # reading it through `generated_branch.py show` is the sanctioned way
                if "generated_branch.py show" not in line:
                    hits.append(f"{rel}:{n}: {m.group(0)}")
    assert not hits, "main must not link a file only `generated` keeps current (#5206):\n" + "\n".join(hits)


def test_the_stub_names_the_generated_branch_and_the_reader():
    text = read_source(REPO / REPORT_DIR / "README.md").text
    assert "generated" in text and "generated_branch.py show" in text


def test_the_gitignore_keeps_the_directory_ignored_but_for_the_stub():
    ign = read_source(REPO / ".gitignore").text
    assert f"{REPORT_DIR}/*\n!{REPORT_DIR}/README.md" in ign
    assert f"!{REPORT_DIR}/*/report.json" not in ign
