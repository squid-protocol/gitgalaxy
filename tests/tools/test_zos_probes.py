"""The z/OS probe corpus (#4702 Part 2): shape, register links, template, and the oracle's expected output."""

import json
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
    "M2": "SQLCA after an injected SQL fault: EXEC SQL is not a cobc statement (the Db2 probes are the Q family)",
}


# MATCHED entries (beyond the families above) with no cobc form, listed so a new MATCHED entry has to be sorted.
MATCHED_NO_COBC_FORM: dict[str, str] = {}


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


def test_every_differs_entry_is_probed_or_sorted_out():
    # A declared oracle-vs-IBM difference (status DIFFERS) is exactly what a z/OS run should measure.
    covered = {e for p in zos_probes.load().values() for e in p["entries"]}
    unsorted = [
        m["id"]
        for m, _ in register.load_entries()
        if m["status"].startswith("DIFFERS")
        and m["id"] not in covered
        and m["id"] not in NOT_PROBED_IDS
        and m["id"][0] not in NOT_PROBED_FAMILIES
    ]
    assert unsorted == [], f"probe these or add a reason to NOT_PROBED_*: {unsorted}"


def test_every_matched_entry_with_a_quote_only_basis_is_probed_or_sorted_out():
    # C8, D3, F2, L2 (and M2, sorted out) were MATCHED on an IBM quote alone. The rest of the MATCHED class below is
    # a Db2 / CICS / LE / control-block shape or an A/L entry with no cobc form; a new MATCHED entry must join one list.
    covered = {e for p in zos_probes.load().values() for e in p["entries"]}
    assert {"C8", "D3", "F2", "L2"} <= covered
    assert "M2" in NOT_PROBED_IDS
    unsorted = [
        m["id"]
        for m, _ in register.load_entries()
        if m["status"].startswith("MATCHED")
        and m["id"] not in covered
        and m["id"] not in NOT_PROBED_IDS
        and m["id"][0] not in NOT_PROBED_FAMILIES
        and m["id"] not in MATCHED_NO_COBC_FORM
    ]
    assert unsorted == [], f"probe these or add a reason to MATCHED_NO_COBC_FORM: {unsorted}"


def test_the_matched_probes_say_what_z_os_should_print():
    probes = zos_probes.load()
    ids = {
        "c8-display-signed-forms": "C8",
        "d3-ascii-overpunch-sign": "D3",
        "f2-file-status-conditions": "F2",
        "l2-cee3abd-user-abend": "L2",
    }
    for pid, entry in ids.items():
        assert entry in probes[pid]["entries"], pid
        assert "Expected z/OS" in probes[pid]["note"], pid


def test_the_le_and_assembler_matched_probes_say_what_z_os_should_print():
    # A1, L1 and L6 (#4702 slice 3): plain cobc has no such module (rc=1); each note carries the z/OS answer.
    probes = zos_probes.load()
    ids = {
        "a1-cobdatft-type-2-to-2": "A1",
        "l1-ceedays-blank-picture-tail": "L1",
        "l1-ceedays-date-past-span-ignored": "L1",
        "l1-ceedays-day-outside-month": "L1",
        "l6-ceedywk-weekdays": "L6",
        "l6-ceeqcen-default-window": "L6",
    }
    for pid, entry in ids.items():
        assert probes[pid]["entries"] == [entry], pid
        assert "Expected z/OS" in probes[pid]["note"], pid
        assert probes[pid]["oracle_expected"] == ["rc=1"], pid


def test_the_le_assumed_probes_say_what_z_os_should_print():
    # L4 (CEEIGZCT) and L5 (CEELOCT), #4702 slice 4: plain cobc has no such copybook or module (rc=1); each note
    # carries the z/OS answer.
    probes = zos_probes.load()
    ids = {
        "l4-ceeigzct-cee000-after-success": "L4",
        "l4-ceeigzct-cee000-after-failed-call": "L4",
        "l5-ceeloct-feedback-and-gregorian-shape": "L5",
        "l5-ceeloct-seconds-match-lilian": "L5",
        "l5-ceeloct-gregorian-tail": "L5",
    }
    for pid, entry in ids.items():
        assert probes[pid]["entries"] == [entry], pid
        assert "Expected z/OS" in probes[pid]["note"], pid
        assert probes[pid]["oracle_expected"] == ["rc=1"], pid
    assert not {"L4", "L5"} & set(NOT_PROBED_IDS)


def test_the_differs_probes_state_the_expected_zos_answer():
    # The oracle's output is the wrong side of a DIFFERS entry: each probe says what z/OS should print instead.
    probes = zos_probes.load()
    ids = {
        "c10-zoned-sign-zone-after-value-zero-and-initialize": "C10",
        "c16-comp5-one-and-two-digit-size": "C16",
        "c7-comp5-byte-order": "C7",
        "c9-pointer-size": "C9",
        "c17-initialize-replacing-table": "C17",
        "d1-ascii-vs-ebcdic-order": "D1",
    }
    for pid, entry in ids.items():
        assert entry in probes[pid]["entries"], pid
        assert "Expected z/OS" in probes[pid]["note"], pid


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


# --- ingest: an operator's filled template -> validated zos_calibration.json records ---

PROBES = {
    "p1": {"entries": ["C1"], "compile_options": "ARITH(COMPAT)", "oracle_expected": ["1", "2"]},
    "p2": {"entries": ["C2"], "compile_options": "OPT(0)", "oracle_expected": ["9"]},
}


def _rec(**kw):
    base = {"date": "2026-11-01", "compiler": "Enterprise COBOL 6.4", "options": "", "probe": "p1", "observed": "1 2",
            "verdict": "", "runtime_options": {k: v["default"] for k, v in RUNTIME_OPTION_TABLE.items()}}  # fmt: skip
    return {**base, **kw}


def test_ingest_derives_matched_and_differs_and_keeps_options():
    merged, _, bad = zos_probes.ingest_records({"C1": [_rec(), _rec(date="2026-11-02", observed="1 3")]}, PROBES, {})
    assert bad == []
    assert [r["verdict"] for r in merged["C1"]] == ["matched", "differs"]
    assert merged["C1"][0]["options"] == "ARITH(COMPAT)"


def test_ingest_skips_unfilled_and_keeps_operator_verdicts():
    merged, notes, bad = zos_probes.ingest_records(
        {"C1": [_rec(observed=""), _rec(observed="rc=0C7", verdict="abend")]}, PROBES, {}
    )
    assert bad == []
    assert [r["verdict"] for r in merged["C1"]] == ["abend"]
    assert any("unfilled" in n for n in notes)


def test_ingest_rejects_bad_verdict_unknown_probe_wrong_entry_and_missing_fields():
    filled = {
        "C1": [_rec(verdict="proven"), _rec(probe="nope"), _rec(probe="p2"), _rec(compiler=""), _rec(date="")],
    }
    _, _, bad = zos_probes.ingest_records(filled, PROBES, {})
    joined = "\n".join(bad)
    assert len(bad) == 5
    for text in ("verdict 'proven'", "unknown probe", "does not list entry C1", "lacks compiler", "lacks date"):
        assert text in joined


def test_ingest_is_idempotent_and_replaces_a_re_measured_record():
    first, _, _ = zos_probes.ingest_records({"C1": [_rec()]}, PROBES, {})
    again, _, _ = zos_probes.ingest_records({"C1": [_rec()]}, PROBES, first)
    assert again == first
    fixed, _, _ = zos_probes.ingest_records({"C1": [_rec(observed="1 3")]}, PROBES, first)
    assert [r["verdict"] for r in fixed["C1"]] == ["differs"]


def test_problems_flag_a_record_whose_probe_does_not_list_the_entry():
    found = zos_probes.problems(PROBES, set(), {"C2": [{"probe": "p1"}]})
    assert any("C2 records probe 'p1', which does not list that entry" in f for f in found)


def _real_probe():
    pid, p = sorted(zos_probes.load().items())[0]
    return pid, p["entries"][0], p


def test_ingest_command_dry_run_then_write_leaves_the_committed_ledger_alone(tmp_path):
    committed = register.ZOS_LEDGER.read_text(encoding="utf-8")
    pid, entry, p = _real_probe()
    filled = tmp_path / "filled.json"
    rec = _rec(probe=pid, observed=" ".join(p["oracle_expected"]), options=p["compile_options"])
    filled.write_text(json.dumps({"results": {entry: [rec]}}), encoding="utf-8")
    ledger = tmp_path / "zos_calibration.json"
    ledger.write_text(committed, encoding="utf-8")
    assert zos_probes.ingest(filled, ledger=ledger) == 0
    assert ledger.read_text(encoding="utf-8") == committed
    assert zos_probes.ingest(filled, write=True, ledger=ledger) == 0
    assert register.zos_problems(IDS, ledger) == []
    assert register.load_zos(ledger)[entry][0]["verdict"] == "matched"
    assert register.ZOS_LEDGER.read_text(encoding="utf-8") == committed


def test_ingest_command_writes_nothing_when_a_record_is_rejected(tmp_path):
    pid, entry, _ = _real_probe()
    filled = tmp_path / "filled.json"
    filled.write_text(json.dumps({"results": {entry: [_rec(probe=pid, verdict="proven")]}}), encoding="utf-8")
    ledger = tmp_path / "zos_calibration.json"
    ledger.write_text('{"results": {}}', encoding="utf-8")
    assert zos_probes.ingest(filled, write=True, ledger=ledger) == 1
    assert ledger.read_text(encoding="utf-8") == '{"results": {}}'


def test_ingest_rejects_a_record_with_a_wrong_runtime_option_set(tmp_path):
    pid, entry, p = _real_probe()
    filled = tmp_path / "filled.json"
    filled.write_text(json.dumps({"results": {entry: [_rec(probe=pid, runtime_options={"x": "1"})]}}), encoding="utf-8")
    ledger = tmp_path / "zos_calibration.json"
    ledger.write_text('{"results": {}}', encoding="utf-8")
    assert zos_probes.ingest(filled, write=True, ledger=ledger) == 1
