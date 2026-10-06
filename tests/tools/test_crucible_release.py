"""crucible_release: release-note counts / deltas / additivity from a fixture crucible repo, and pin-check's filter."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import crucible_release as cr

VALIDATE = """import json, sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
cases = sorted(root.glob("cases/*/*/case.json"))
bad = [c for c in cases if json.loads(c.read_text()).get("format") != "cics-crucible/case/1"]
print(f"{len(cases) - len(bad)}/{len(cases)} cases valid")
sys.exit(1 if bad else 0)
"""


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],  # noqa: S603, S607
                          capture_output=True, text=True, check=True).stdout  # fmt: skip


def put(repo: Path, rel: str, text: str) -> None:
    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / rel).write_text(text)


def case(repo: Path, trap: str, cid: str, scenarios: list[str], fmt: str = "cics-crucible/case/1") -> None:
    doc = {"format": fmt, "id": cid, "trap": trap, "title": f"title of {cid}",
           "sources": {"cobol": [f"src/{cid[:6].upper().replace('-', '')}.cbl"]},
           "scenarios": [{"id": s, "summary": f"{s} summary", "path": "happy"} for s in scenarios]}  # fmt: skip
    put(repo, f"cases/{trap}/{cid}/case.json", json.dumps(doc))
    for s in scenarios:
        put(repo, f"cases/{trap}/{cid}/expected/{s}.json", json.dumps({"scenario": s}))


@pytest.fixture
def crucible(tmp_path):
    repo = tmp_path / "cc"
    repo.mkdir()
    git(repo, "init", "-q")
    put(repo, "SPEC.md", "# format `cics-crucible/1`\n")
    put(repo, "schema/case.schema.json", '{"format": "cics-crucible/case/1"}')
    put(repo, "schema/expected.schema.json", '{"format": "cics-crucible/expected/1"}')
    put(repo, "tools/validate.py", VALIDATE)
    case(repo, "ghost-tasks", "gt-one", ["a", "b"])
    case(repo, "condition-handling", "hc-two", ["c"])
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "first")
    git(repo, "tag", "v0.1.0")
    case(repo, "ghost-tasks", "gt-new", ["x", "y", "z"])
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "cases: gt-new (#7)")
    put(repo, "SPEC.md", "# format `cics-crucible/1`\n\nA new optional key.\n")
    put(repo, "README.md", "readme")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "docs: SPEC addition (#8)")
    return repo


def test_notes_counts_deltas_and_additivity(crucible):
    n = cr.notes(crucible, "v0.1.0")
    assert (n["cases_before"], n["cases_after"], n["scenarios_before"], n["scenarios_after"]) == (2, 3, 3, 6)
    assert [c["id"] for c in n["added"]] == ["gt-new"] and n["added"][0]["added_by"] == "cases: gt-new (#7)"
    assert n["touched"] == {} and n["log_corrections"] == {}
    assert n["additive"] and n["old_cases_validate"][0] and n["validate"] == [True, "3/3 cases valid"]
    assert n["other_commits"] == ["docs: SPEC addition (#8)"]
    md = cr.notes_markdown(n, "v0.2.0")
    assert "**3 cases** (was 2) and **6 scenarios** (was 3)" in md
    assert "No log was corrected" in md and "additive SPEC additions only" in md
    assert "- **`gt-new`** (3 scenarios, #7;" in md and "  - `y` (happy): y summary" in md
    assert "| `v0.2.0` |" in md and "Adds `gt-new`" in md


def test_notes_flags_a_log_correction_and_a_format_bump(crucible):
    put(crucible, "cases/ghost-tasks/gt-one/expected/a.json", json.dumps({"scenario": "a", "fixed": True}))
    put(crucible, "SPEC.md", "# format `cics-crucible/2`\n")
    git(crucible, "add", "-A")
    git(crucible, "commit", "-qm", "fix a log")
    n = cr.notes(crucible, "v0.1.0")
    assert n["log_corrections"] == {"gt-one": ["cases/ghost-tasks/gt-one/expected/a.json"]}
    assert not n["additive"] and n["formats_after"] == ["1", "2"]
    md = cr.notes_markdown(n, "v0.2.0")
    assert "NOT ADDITIVE" in md and "## Log corrections" in md and "No log was corrected" not in md


def test_notes_cli_exits_1_when_validate_fails(crucible, capsys):
    case(crucible, "ghost-tasks", "gt-bad", ["q"], fmt="cics-crucible/case/9")
    git(crucible, "add", "-A")
    git(crucible, "commit", "-qm", "bad")
    assert cr.main(["notes", str(crucible), "--since", "v0.1.0", "--tag", "v0.2.0"]) == 1
    assert "**NO: 3/4 cases valid**" in capsys.readouterr().out


def test_pin_mentions_skip_provenance_history_and_split_contexts(tmp_path):
    repo = tmp_path / "gg"
    repo.mkdir()
    git(repo, "init", "-q")
    put(repo, "tests/cics_crucible/ports/c/P/provenance.json",
        '{\n "proof": {\n  "crucible_ref": "v0.4.0 (2d01)"\n }\n}\n')  # fmt: skip
    put(repo, "tests/cics_crucible/ports/c/P/evidence.json", '{\n "crucible_ref_proven": "v0.4.0 (2d01)"\n}\n')
    put(repo, "tests/tools/estate_crucible.py", "# copy_libraries, v0.4.0+\n# v0.4.01 is not v0.4.0's prefix\n")
    put(repo, "docs/x.md", "cics-crucible v0.4.10 is another tag\n")
    git(repo, "add", "-A")
    cics, other = cr.pin_mentions(repo, "v0.4.0")
    assert [r.split(":")[0] for r in cics] == ["tests/cics_crucible/ports/c/P/evidence.json"]
    assert [r.split(":")[0] for r in other] == ["tests/tools/estate_crucible.py", "tests/tools/estate_crucible.py"]
