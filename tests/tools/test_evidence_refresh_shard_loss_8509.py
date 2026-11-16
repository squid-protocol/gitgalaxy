"""#8509: a det-mutation shard whose runner the platform killed (shutdown signal, exit 143) skips every always() step, so it
uploads nothing, and failed the whole Evidence Refresh. The class: a lost shard versus a failed claim. The refresh job
reads a per-shard marker the stage step writes; these tests run the workflow's own shell over temp dirs."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "evidence-refresh.yml"
STEP = "Tell a det mutation shard lost to the runner from a failed claim (#8509)"


def _text():
    return WORKFLOW.read_text(encoding="utf-8")


def _step_block():
    lines = _text().splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.strip() == f"- name: {STEP}")
    end = next(
        i
        for i in range(start + 1, len(lines))
        if lines[i].startswith("      - name:") or lines[i].startswith("      #")
    )
    return lines[start:end]


def _script():
    block = _step_block()
    i = next(i for i, ln in enumerate(block) if ln.strip() == "run: |")
    return "\n".join(ln[10:] for ln in block[i + 1 :])


def test_the_stage_step_writes_a_marker_with_the_claim_outcome():
    text = _text()
    assert 'echo "${{ steps.detmut.outcome }}" > "$out/shard-${{ matrix.shard }}.done"' in text
    stage = text.index("- name: Stage the ledgers this job wrote", text.index("  det-mutation:"))
    assert "if: always()" in text[stage : stage + 120]


def test_the_gates_honour_a_lost_shard_but_still_fail_a_failed_claim():
    text = _text()
    assert "steps.shardloss.outputs.lost == 'true'" in text
    assert "needs.det-mutation.result != 'success' && steps.shardloss.outputs.lost != 'true'" in text
    # the lost-shard step only looks at a failed det-mutation job
    assert "needs.det-mutation.result == 'failure'" in "\n".join(_step_block())


@pytest.mark.skipif(sys.platform != "linux" or shutil.which("bash") is None, reason="needs bash on linux (#7312)")
@pytest.mark.parametrize(
    ("markers", "lost"),
    [
        ({1: "success", 3: "success"}, True),  # shard 2 lost: the 2026-11-16 shape
        ({1: "success", 2: "success", 3: "success"}, False),  # nothing missing
        ({1: "failure", 3: "success"}, False),  # a claim failed, and another shard was lost
        ({1: "success", 2: "failure"}, False),  # a claim failed in a present shard
        ({}, False),  # no artifact at all: download failed, nothing is tolerated
        ({2: "success"}, True),  # two lost
    ],
)
def test_the_marker_separates_a_lost_shard_from_a_failed_claim(tmp_path, markers, lost):
    d = tmp_path / "in"
    d.mkdir()
    for n, outcome in markers.items():
        (d / f"shard-{n}.done").write_text(outcome + "\n", encoding="utf-8")
    out = tmp_path / "out.txt"
    r = subprocess.run(
        ["bash", "-c", _script()],
        env={"PATH": "/usr/bin:/bin", "SHARDS": "1 2 3", "MARKER_DIR": str(d), "GITHUB_OUTPUT": str(out)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    assert out.read_text(encoding="utf-8").strip() == f"lost={'true' if lost else 'false'}"
    assert ("::warning" in r.stdout) == lost
