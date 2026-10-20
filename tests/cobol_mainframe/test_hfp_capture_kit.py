"""#4271 / #4050: the z/OS capture kit for HFP (tests/tools/hfp_capture_kit.py): the program it emits, and the ingest."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import hfp_capture_kit as K  # noqa: E402
from gitgalaxy.core.runtime_options import RUNTIME_OPTION_TABLE  # noqa: E402


@pytest.fixture
def table(tmp_path):
    t = tmp_path / "hfp.json"
    shutil.copy(K.TABLE, t)
    return t


def _under():
    """The options a calibration run states: every option the table judges, at its default."""
    return {p: row["default"] for p, row in RUNTIME_OPTION_TABLE.items() if row["policy"]}


def _sysout(recs, skip=()):
    lines = ["IEF142I HFPCAP GO - STEP WAS EXECUTED"]
    for r in K.askable(recs):
        if r["id"] not in skip:
            lines.append(f"{r['id']}|{K.compute(r)}")
    return "\n".join(lines) + "\n"


def test_every_record_is_asked_or_skipped_with_a_reason():
    recs = K.records()
    ids = {r["id"] for r in recs}
    assert {r["id"] for r in K.askable(recs)} | set(K.skipped(recs)) == ids
    assert all(K.skipped(recs).values())
    assert {r["op"] for r in K.askable(recs)} >= {
        "encode",
        "add",
        "sub",
        "mul",
        "div",
        "display",
        "fixed",
        "store",
        "round_short",
        "compare",
    }
    assert {(r["op"], r["size"]) for r in recs if r["id"] in K.skipped(recs)} == {
        ("from_ieee", "short"),
        ("from_ieee", "long"),
        ("to_ieee", "short"),
        ("to_ieee", "long"),
        ("mul", "short"),
        ("div", "short"),
    }


def test_the_emitted_program_is_deterministic_fixed_format_and_names_every_asked_id():
    recs = K.records()
    src = K.emit_program(recs)
    assert src == K.emit_program(recs)
    assert all(len(line) <= 72 and line[:6] == "      " for line in src.splitlines())
    for r in K.askable(recs):
        assert f'"{r["id"]}|"' in src
    for r in K.skipped(recs):
        assert f'"{r}|"' not in src
    assert "COMP-1" in src and "COMP-2" in src and "FUNCTION HEX-OF" in src
    assert src.rstrip().endswith("GOBACK.")


def test_each_op_becomes_the_statement_its_row_states():
    one = {"id": "t", "source": "ibm-publication", "size": "long", "a": "4110000000000000", "b": "4120000000000000"}
    assert "COMPUTE LR = LA * LB" in "".join(K.statements({**one, "op": "mul"}))
    short = {**one, "size": "short", "a": "41100000", "b": "41200000"}
    assert "COMPUTE SR = SA - SB" in "".join(K.statements({**short, "op": "sub"}))
    assert "MOVE -118.625 TO SR" in "".join(K.statements({**short, "op": "encode", "value": "-118.625"}))
    assert "MOVE LA TO E17" in "".join(K.statements({**one, "op": "fixed", "scale": 17}))
    rounded = "".join(K.statements({**one, "op": "round_short"}))
    assert "MOVE LA TO SR" in rounded and "HEX-OF(SR-X)" in rounded
    cmp_ = "".join(K.statements({**short, "op": "compare"}))
    assert all(f"IF SA {sign} SB" in cmp_ for sign in "<=>")
    with pytest.raises(ValueError):
        K.statements({**one, "op": "encode", "value": "1e5"})


def test_a_store_record_becomes_a_compute_into_a_numeric_receiver_shown_through_an_edited_one():
    r = next(x for x in K.records() if x["id"] == "asm-store-div-2-3-2-rounded")
    text = "".join(K.statements(r))
    assert "COMPUTE Q2 ROUNDED = LA / LB" in text and "MOVE Q2 TO E2" in text
    plain = "".join(K.statements(next(x for x in K.records() if x["id"] == "asm-store-div-2-3-2")))
    assert "COMPUTE Q2 = LA / LB" in plain
    src = K.emit_program(K.records())
    assert "01  Q2 PIC S9(16)V9(2)." in src and "01  E2 PIC" in src
    assert "asm-store-div-2-3-2|" in src


def test_ingest_appends_captured_records_and_leaves_every_existing_line(table):
    recs = K.records(table)
    before = table.read_text(encoding="utf-8")
    res = K.ingest(_sysout(recs), table, "JOB01234", "GO", _under())
    after = table.read_text(encoding="utf-8")
    assert res["findings"] == [] and res["missing"] == [] and res["kept"] == []
    assert {x.rstrip(",") for x in before.splitlines()} <= {x.rstrip(",") for x in after.splitlines()}
    new = [r for r in K.records(table) if r["source"] == "zos-run"]
    assert [r["id"] for r in new] == ["zos-" + r["id"] for r in K.askable(recs)]
    assert all(r["evidence"]["job"] == "JOB01234" and len(r["evidence"]["output_sha256"]) == 64 for r in new)
    assert not [r for r in new if K.calibration_problems(r["calibrated_under"])]
    assert all(K.compute(r) == r["want"] or r["op"] in ("fixed", "store") for r in new)
    json.loads(after)


def test_a_second_ingest_rewrites_nothing(table):
    recs = K.records(table)
    K.ingest(_sysout(recs), table, "J1", "GO", _under())
    once = table.read_text(encoding="utf-8")
    res = K.ingest(_sysout(recs), table, "J2", "GO", _under())
    assert res["added"] == [] and len(res["kept"]) == len(K.askable(recs))
    assert table.read_text(encoding="utf-8") == once


def test_a_result_that_disagrees_with_the_model_is_a_finding_and_the_record_stays(table):
    recs = K.records(table)
    out = _sysout(recs, skip={"enc-1"}) + "enc-1|41200000\n"
    res = K.ingest(out, table, "J1", "GO", _under())
    assert len(res["findings"]) == 1 and "zos-enc-1" in res["findings"][0]
    assert [r["want"] for r in K.records(table) if r["id"] == "zos-enc-1"] == ["41200000"]


def test_a_missing_result_is_reported_and_a_display_keeps_its_leading_space(table):
    recs = K.records(table)
    res = K.ingest(_sysout(recs, skip={"enc-1"}), table, "J1", "GO", _under())
    assert res["missing"] == ["enc-1"]
    assert [r["want"] for r in K.records(table) if r["id"] == "zos-disp-1.5"] == [" .15000000E 01"]


def test_ingest_without_evidence_or_options_is_refused_and_writes_nothing(table):
    before = table.read_text(encoding="utf-8")
    recs = K.records(table)
    with pytest.raises(ValueError, match="calibrated_under"):
        K.ingest(_sysout(recs), table, "J1", "GO", {})
    with pytest.raises(ValueError, match="evidence"):
        K.ingest(_sysout(recs), table, "", "GO", _under())
    assert table.read_text(encoding="utf-8") == before


def test_the_cli_emits_the_program_and_the_jcl(tmp_path):
    assert K.main(["emit", str(tmp_path)]) == 0
    assert (tmp_path / "HFPCAP.cbl").read_text() == K.emit_program(K.records())
    assert "EXEC" in (tmp_path / "HFPCAP.jcl").read_text()


def test_a_model_assumption_is_asked_and_a_disagreeing_capture_is_a_finding_against_it(table):
    recs = K.records(table)
    assert {"asm-store-add-0.1-0.2-2", "asm-enc-0.3-long"} <= {r["id"] for r in K.askable(recs)}
    out = _sysout(recs, skip={"asm-store-add-0.1-0.2-2"}) + "asm-store-add-0.1-0.2-2|0.30\n"
    res = K.ingest(out, table, "J1", "GO", _under())
    assert len(res["findings"]) == 1 and "zos-asm-store-add-0.1-0.2-2" in res["findings"][0]
