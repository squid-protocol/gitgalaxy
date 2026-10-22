"""The z/OS probe corpus (#4702 Part 2): shape, register links, template, and the oracle's expected output."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import equivalence_oracle
import register
import zos_probes

IDS = {m["id"] for m, _ in register.load_entries()}


def test_committed_corpus_is_valid():
    probes = zos_probes.load()
    assert probes
    assert zos_probes.problems(probes, IDS, register.load_zos()) == []


def test_every_probe_is_fixed_format_ending_in_stop_run():
    for pid, p in zos_probes.load().items():
        lines = p["source"].splitlines()
        assert all(line.startswith("       ") for line in lines), pid
        assert lines[-1].strip() == "STOP RUN.", pid


def test_problems_are_named():
    bad = {
        "a": {
            "entries": ["ZZ9"],
            "compile_options": "x",
            "question": "q",
            "source": "x" * 80,
            "oracle_expected": ["1"],
        },
        "b": {"entries": ["C1"]},
    }
    found = zos_probes.problems(bad, IDS, {"C1": [{"probe": "nope"}]})
    assert any("a: ZZ9 is not a register entry" in f for f in found)
    assert any("a: line 1 runs past column 72" in f for f in found)
    assert any("b: lacks compile_options" in f for f in found)
    assert any("unknown probe 'nope'" in f for f in found)


def test_template_fills_a_valid_ledger_once_observed():
    t = zos_probes.template(zos_probes.load())
    assert set(t) <= IDS
    for recs in t.values():
        for r in recs:
            assert tuple(r) == register.ZOS_RECORD_KEYS
            assert r["probe"] and r["options"] and not r["observed"]


@pytest.mark.skipif(not shutil.which("docker") or os.environ.get("EQUIVALENCE_E2E") != "1",
                    reason="needs Docker and the oracle image (EQUIVALENCE_E2E=1)")  # fmt: skip
def test_oracle_output_is_the_recorded_expectation():
    if subprocess.run(["docker", "image", "inspect", equivalence_oracle.IMAGE], capture_output=True).returncode:  # noqa: S603, S607
        pytest.skip("oracle image not built")
    probes = zos_probes.load()
    seen = zos_probes.run_oracle(probes)
    assert {k: seen[k] for k in probes} == {k: p["oracle_expected"] for k, p in probes.items()}
