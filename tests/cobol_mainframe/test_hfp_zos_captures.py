"""#4271 / #4050: the capture-vector table for IBM hexadecimal floating point, checked against the translator's model.

`zos_captures/hfp.json` holds expected HFP results. A `zos-run` record is a result captured from z/OS (the calibration
oracle, register C6): a model that disagrees with one is a finding against the model, never a record to edit. The Java
runtime is held to this same model bit for bit by test_det_hfp.py, so the table is checked against the model only.
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from fractions import Fraction as F
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "tools"))

from gitgalaxy.core.runtime_options import calibration_problems  # noqa: E402
from hfp_capture_kit import compute  # noqa: E402

TABLE = Path(__file__).parent / "zos_captures" / "hfp.json"
SOURCES = ("ibm-publication", "model-assumption", "zos-run")
OPS = {
    "encode": ("value",),
    "add": ("a", "b"),
    "sub": ("a", "b"),
    "mul": ("a", "b"),
    "div": ("a", "b"),
    "display": ("a",),
    "fixed": ("a", "scale"),
    "store": ("a", "b", "arith", "scale"),
    "from_ieee": ("a",),
    "to_ieee": ("a",),
    "round_short": ("a",),
    "compare": ("a", "b"),
}
# round_short: a long item MOVEd to a COMP-1, the result is always short; store: a fixed-point receiver is long
SIZES = {"round_short": ("short",), "store": ("long",)}


def records() -> list[dict]:
    return json.loads(TABLE.read_text(encoding="utf-8"))["records"]


def problems(r: dict) -> list[str]:
    """What is wrong with a record's shape (a captured one also needs its evidence and the options it ran under)."""
    probs = []
    if r.get("source") not in SOURCES:
        probs.append(f"source is one of {SOURCES}")
    if r.get("op") not in OPS:
        return probs + [f"op is one of {sorted(OPS)}"]
    if r.get("size") not in ("short", "long"):
        probs.append("size is short or long")
    probs += [f"missing {k}" for k in (*OPS[r["op"]], "want") if k not in r]
    if r.get("source") == "zos-run":
        if not r.get("evidence"):
            probs.append("a zos-run record needs `evidence` (job, step, output hash)")
        probs += calibration_problems(r.get("calibrated_under"))
    return probs


def test_every_record_is_well_formed_and_ids_are_unique():
    recs = records()
    assert recs
    ids = [r["id"] for r in recs]
    assert len(ids) == len(set(ids))
    assert {r["id"]: problems(r) for r in recs if problems(r)} == {}


@pytest.mark.parametrize("r", records(), ids=lambda r: r["id"])
def test_the_model_gives_the_recorded_result(r):
    want = r["want"]
    got = compute(r)
    if r["op"] in ("fixed", "store"):
        got, want = Decimal(got), Decimal(want)
    assert got == want, f"{r['source']} record {r['id']}: model {got}, recorded {want}"


def test_the_table_covers_both_sizes_and_every_op():
    recs = records()
    assert {r["op"] for r in recs} == set(OPS)
    assert {r["size"] for r in recs} == {"short", "long"}


def test_the_table_covers_every_op_in_both_sizes():
    pairs = {(r["op"], r["size"]) for r in records()}
    assert pairs == {(op, size) for op in OPS for size in SIZES.get(op, ("short", "long"))}


def test_a_captured_record_without_evidence_or_options_is_refused():
    r = {"id": "x", "source": "zos-run", "op": "encode", "value": "1", "size": "short", "want": "41100000"}
    probs = problems(r)
    assert any("evidence" in p for p in probs)
    assert any("calibrated_under" in p for p in probs)


def test_a_malformed_record_is_refused():
    assert problems({"source": "guess", "op": "encode"})
    assert problems({"source": "ibm-publication", "op": "sqrt"})
    assert problems({"source": "ibm-publication", "op": "add", "size": "short", "a": "00000000"}) == [
        "missing b",
        "missing want",
    ]


def test_a_disagreeing_capture_would_fail():
    r = {
        "id": "x",
        "source": "zos-run",
        "op": "add",
        "a": "41100000",
        "b": "41100000",
        "size": "short",
        "want": "41300000",
    }
    assert compute(r) != r["want"]


def test_a_compare_record_states_one_of_three_signs_and_a_round_record_a_long_operand():
    for r in records():
        if r["op"] == "compare":
            assert r["want"] in ("<", "=", ">")
        if r["op"] == "round_short":
            assert len(r["a"]) == 16 and len(r["want"]) == 8


def test_a_model_assumption_record_is_never_ibm_evidence():
    """Its `want` is the model's own answer: it stays a separate source until a z/OS run states the result."""
    asm = [r for r in records() if r["source"] == "model-assumption"]
    assert asm and all(r["id"].startswith("asm-") for r in asm)
    assert not [r for r in records() if r["source"] == "ibm-publication" and r["id"].startswith("asm-")]
    assert {r["op"] for r in asm} >= {"encode", "display", "store"}


def test_a_store_record_separates_truncation_from_rounding():
    store = {r["id"]: r for r in records() if r["op"] == "store"}
    assert (
        store["asm-store-add-0.1-0.2-2"]["want"] == "0.29"
        and store["asm-store-add-0.1-0.2-2-rounded"]["want"] == "0.30"
    )
    assert store["asm-store-div-2-3-2"]["want"] == "0.66" and store["asm-store-div-2-3-2-rounded"]["want"] == "0.67"


def test_the_bnk1tfn_non_exact_float_to_fixed_shape_is_asked():
    """#4271 (BNK1TFN): 12.34 / 0.01 / 9999999999.99 as COMP-2 (and the first two as COMP-1) moved to a 2-decimal field.

    GnuCOBOL truncates the float, the model rounds in the receiver's low-order position; each value is asked as an
    encode and a fixed record, so a z/OS run states both the image and the digits.
    """
    by_id = {r["id"]: r for r in records()}
    for v, sizes in (("12.34", ("long", "short")), ("0.01", ("long", "short")), ("9999999999.99", ("long",))):
        for sz in sizes:
            enc, fix = by_id[f"asm-enc-{v}-{sz}"], by_id[f"asm-fixed-{v}-{sz}-2"]
            assert enc["source"] == fix["source"] == "model-assumption"
            assert fix["a"] == enc["want"] and Decimal(fix["want"]) == Decimal(v)


def test_the_bankdata_le_seconds_shape_is_asked():
    """#4271 (BANKDATA TIMESTAMP, CRECUST CEELOCT): LE seconds as a COMP-2, MOVEd to a `9(14)` field.

    The source comment wants no rounding up; the model rounds a float MOVEd to fixed point (IBM "Conversions and
    precision"), GnuCOBOL truncates. A whole second is exact in long HFP, a .6 second rounds up to the next one.
    """
    by_id = {r["id"]: r for r in records()}
    for secs, rounded in (("13987654321", "13987654321"), ("13987654321.6", "13987654322")):
        enc, fix = by_id[f"asm-enc-{secs}-long"], by_id[f"asm-fixed-{secs}-long-0"]
        assert enc["source"] == fix["source"] == "model-assumption" and enc["size"] == fix["size"] == "long"
        assert fix["a"] == enc["want"] and fix["scale"] == 0 and Decimal(fix["want"]) == Decimal(rounded)
