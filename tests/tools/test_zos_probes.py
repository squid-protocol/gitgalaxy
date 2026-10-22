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
from gitgalaxy.core.runtime_options import RUNTIME_OPTION_TABLE

IDS = {m["id"] for m, _ in register.load_entries()}


def test_committed_corpus_is_valid():
    probes = zos_probes.load()
    assert probes
    assert zos_probes.problems(probes, IDS, register.load_zos()) == []


def test_every_part_one_entry_has_a_probe():
    covered = {e for p in zos_probes.load().values() for e in p["entries"]}
    assert {"C1", "C2", "C3", "C4", "C11", "C13", "C14", "D2"} <= covered


def test_burned_estate_assumed_entries_have_a_probe():
    # C5: DBB MortgageApplication (NUMPROC); C12: CBSA (RANDOM). C6 is not reached by a burned program yet.
    covered = {e for p in zos_probes.load().values() for e in p["entries"]}
    assert {"C5", "C12"} <= covered


def test_the_4688_float_differences_have_probes():
    # The three oracle-vs-IBM shapes the #4675 fuzz found (register C6), as z/OS-runnable probes.
    probes = zos_probes.load()
    ids = {"c6-float-move-to-edited", "c6-compound-float-compute", "c6-float-zero-add-to-packed"}
    assert ids <= set(probes)
    assert all(probes[i]["entries"] == ["C6"] for i in ids)


def test_file_and_storage_assumed_entries_with_burned_reach_have_a_probe():
    # F1: CardDemo indexed FILE STATUS; F3: CardDemo READACCT VBRCFILE; L3: CardDemo READACCT OUTFILE, CBSA CRDTAGY.
    covered = {e for p in zos_probes.load().values() for e in p["entries"]}
    assert {"F1", "F3", "L3"} <= covered


# ASSUMED entries no cobc program can express (a CICS / IMS / MQ / Db2 / LE service, a control block or a database
# the oracle only stubs), by register family, and single entries with their reason.
NOT_PROBED_FAMILIES = {
    "X": "CICS API behaviour: the oracle runs the stub, not a region",
    "I": "IMS DL/I: no CBLTDLI in cobc",
    "W": "MQ: no queue manager in cobc",
    "Q": "Db2 / SQL: not a cobc statement",
}
NOT_PROBED_IDS = {
    "A2": "z/OS control blocks (PSA / TCB / TIOT): stand-ins, no cobc equivalent",
    "J1": "VSAM on H2: no burned reach",
    "L4": "CEEIGZCT stand-in: LE service, no cobc equivalent",
    "L5": "CEELOCT: LE service, no cobc equivalent",
}


def test_every_assumed_entry_is_probed_or_sorted_out():
    covered = {e for p in zos_probes.load().values() for e in p["entries"]}
    unsorted = [
        m["id"]
        for m, _ in register.load_entries()
        if m["status"].startswith("ASSUMED")
        and m["id"] not in covered
        and m["id"] not in NOT_PROBED_IDS
        and m["id"][0] not in NOT_PROBED_FAMILIES
    ]
    assert unsorted == [], f"probe these or add a reason to NOT_PROBED_*: {unsorted}"


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
            assert tuple(r) == (*register.ZOS_RECORD_KEYS, "runtime_options")
            assert set(r["runtime_options"]) == set(RUNTIME_OPTION_TABLE)
            assert r["probe"] and r["options"] and not r["observed"]


def test_manifest_holds_the_ibm_default_of_every_judged_option():
    base = zos_probes.load_runtime()
    assert base == {k: v["default"] for k, v in RUNTIME_OPTION_TABLE.items()}
    assert zos_probes.runtime_problems(base, zos_probes.load()) == []


def test_runtime_problems_are_named():
    base = {"le.runtime_options.NOPE": "1"}
    probes = {"p": {"runtime_variants": [{"le.runtime_options.STORAGE": "00"}]}}
    found = zos_probes.runtime_problems(base, probes)
    assert any("le.runtime_options.NOPE is not in RUNTIME_OPTION_TABLE" in f for f in found)
    assert any("runtime_options: lacks le.runtime_options.STORAGE" in f for f in found)
    assert any("p: runtime_variants[0] names le.runtime_options.STORAGE" in f for f in found)


def test_a_variant_run_replaces_only_its_keys():
    t = zos_probes.template(zos_probes.load())
    runs = [r for r in t["L3"] if r["probe"] == "l3-no-value-working-storage"]
    assert [r["runtime_options"]["le.runtime_options.STORAGE"] for r in runs] == ["NONE,NONE,NONE,0K", "00"]
    assert {k: v for k, v in runs[0]["runtime_options"].items() if k != "le.runtime_options.STORAGE"} == {
        k: v for k, v in runs[1]["runtime_options"].items() if k != "le.runtime_options.STORAGE"
    }


@pytest.mark.skipif(not shutil.which("docker") or os.environ.get("EQUIVALENCE_E2E") != "1",
                    reason="needs Docker and the oracle image (EQUIVALENCE_E2E=1)")  # fmt: skip
def test_oracle_output_is_the_recorded_expectation():
    if subprocess.run(["docker", "image", "inspect", equivalence_oracle.IMAGE], capture_output=True).returncode:  # noqa: S603, S607
        pytest.skip("oracle image not built")
    probes = zos_probes.load()
    seen = zos_probes.run_oracle(probes)
    assert {k: seen[k] for k in probes} == {k: p["oracle_expected"] for k, p in probes.items()}
