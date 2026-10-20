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

from gitgalaxy.core.runtime_options import calibration_problems  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import hfp as H  # noqa: E402

TABLE = Path(__file__).parent / "zos_captures" / "hfp.json"
SOURCES = ("ibm-publication", "zos-run")
OPS = {
    "encode": ("value",),
    "add": ("a", "b"),
    "sub": ("a", "b"),
    "mul": ("a", "b"),
    "div": ("a", "b"),
    "display": ("a",),
    "fixed": ("a", "scale"),
    "from_ieee": ("a",),
    "to_ieee": ("a",),
}
FUNC = {"add": H.add, "sub": H.sub, "mul": H.mul, "div": H.div}


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


def compute(r: dict) -> str:
    short = r["size"] == "short"
    if r["op"] == "encode":
        return H.encode(H.for_item(F(r["value"]), short), short).hex().upper()
    if r["op"] == "from_ieee":
        return H.from_ieee(int(r["a"], 16), 4 if short else 8).hex().upper()
    if r["op"] == "to_ieee":
        return f"{H.to_ieee(bytes.fromhex(r['a'])):0{8 if short else 16}X}"
    a = H.decode(bytes.fromhex(r["a"]))
    if r["op"] == "display":
        return H.display(a, not short)
    if r["op"] == "fixed":
        return str(H.to_fixed(a, r["scale"], 9 if short else 18))
    out = FUNC[r["op"]](a, H.decode(bytes.fromhex(r["b"])), not short)
    return H.encode(out, short).hex().upper()


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
    if r["op"] == "fixed":
        got, want = Decimal(got), Decimal(want)
    assert got == want, f"{r['source']} record {r['id']}: model {got}, recorded {want}"


def test_the_table_covers_both_sizes_and_every_op():
    recs = records()
    assert {r["op"] for r in recs} == set(OPS)
    assert {r["size"] for r in recs} == {"short", "long"}


def test_the_table_covers_every_op_in_both_sizes():
    pairs = {(r["op"], r["size"]) for r in records()}
    assert pairs == {(op, size) for op in OPS for size in ("short", "long")}


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
