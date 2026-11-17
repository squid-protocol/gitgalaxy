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


def _put_in_place_script():
    lines = _text().splitlines()
    start = next(
        i for i, ln in enumerate(lines) if ln.strip() == "- name: Put the renewed det mutation ledgers in place (#5862)"
    )
    i = next(i for i in range(start, len(lines)) if lines[i].strip() == "run: |")
    body = []
    for ln in lines[i + 1 :]:
        if ln.strip() and not ln.startswith(" " * 10):
            break
        body.append(ln[10:])
    return "\n".join(body)


def _run_put_in_place(tmp_path, files, symlink=None):
    temp = tmp_path / "tmp"
    base = temp / "detmut-in"
    ledgers = base / "records" / "tests" / "equivalence" / "det_mutation"
    ledgers.mkdir(parents=True)
    for rel in files:
        (base / rel).parent.mkdir(parents=True, exist_ok=True)
        (base / rel).write_text("{}", encoding="utf-8")
    if symlink:
        (base / symlink).symlink_to(base)
    dest = tmp_path / "gitgalaxy" / "tests" / "equivalence" / "det_mutation"
    dest.mkdir(parents=True)
    r = subprocess.run(
        ["bash", "-c", _put_in_place_script()],
        env={"PATH": "/usr/bin:/bin", "RUNNER_TEMP": str(temp)},
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    return r, dest


@pytest.mark.skipif(sys.platform != "linux" or shutil.which("bash") is None, reason="needs bash on linux (#7312)")
def test_the_shard_markers_do_not_fail_the_put_in_place_filter(tmp_path):
    """The 2026-11-16 shape: markers share the artifact dir with the ledgers and the filter rejected them."""
    files = ["shard-1.done", "shard-2.done", "records/tests/equivalence/det_mutation/case.json"]
    r, dest = _run_put_in_place(tmp_path, files)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (dest / "case.json").is_file()


@pytest.mark.skipif(sys.platform != "linux" or shutil.which("bash") is None, reason="needs bash on linux (#7312)")
@pytest.mark.parametrize(
    ("files", "symlink"),
    [
        (["stray.txt"], None),
        (["shard-1.done.sh"], None),
        (["other.done"], None),
        ([], "link.json"),
    ],
)
def test_the_put_in_place_filter_still_rejects_anything_else(tmp_path, files, symlink):
    r, _ = _run_put_in_place(tmp_path, files, symlink)
    assert r.returncode == 1
    assert "unexpected files in the artifact" in r.stdout
