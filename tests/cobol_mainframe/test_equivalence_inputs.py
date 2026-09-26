"""#3804: equivalence inputs generated from record layouts.

Pinned without a corpus, on hand-written layouts: values round-trip through each storage
(the diff reads what the generator wrote), numeric edges come first, primary keys are
unique and in key order, a `from` join draws only values the other file holds (and
`miss` makes some that it does not), `every` fills a cartesian product, FILLER stays
blank, and the same seed makes the same bytes.
"""

import random
import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence as eq  # noqa: E402
import equivalence_inputs as ei  # noqa: E402

ACCOUNT = [
    {"name": "ACCT-ID", "offset": 0, "bytes": 5, "pic": "9(05)", "usage": None},
    {"name": "ACCT-BAL", "offset": 5, "bytes": 7, "pic": "S9(05)V99", "usage": None},
    {"name": "ACCT-LIMIT", "offset": 12, "bytes": 4, "pic": "S9(05)V99", "usage": "COMP-3"},
    {"name": "ACCT-GROUP", "offset": 16, "bytes": 4, "pic": "X(04)", "usage": None},
    {"name": "FILLER", "offset": 20, "bytes": 5, "pic": "X(05)", "usage": None},
]
XREF = [
    {"name": "XREF-CARD", "offset": 0, "bytes": 6, "pic": "X(06)", "usage": None},
    {"name": "XREF-ACCT", "offset": 6, "bytes": 5, "pic": "9(05)", "usage": None},
]


def _spec(records, fields=None, seed=1, key_len=5):
    return {"reclen": 25, "organization": "indexed", "keys": [{"offset": 0, "length": key_len}],
            "generate": {"records": records, "seed": seed, "fields": fields or {}}}  # fmt: skip


def _rows(data, reclen):
    return [data[i : i + reclen] for i in range(0, len(data), reclen)]


@pytest.mark.parametrize("value, pic, usage, n", [("12.34", "S9(5)V99", None, 7), ("-5", "S9(3)", "COMP-3", 2),
                                                  ("300", "S9(4)", "COMP", 2), ("7", "9(1)", None, 1),
                                                  ("-0.01", "S9(3)V99", "COMP-3", 3)])  # fmt: skip
def test_a_generated_value_reads_back_through_the_diff(value, pic, usage, n):
    assert eq.decode_field(ei.encode_field(value, pic, usage, n), pic, usage) == Decimal(value)


def test_numeric_edges_come_first():
    rng = random.Random(0)
    got = [ei._numeric_value(rng, True, 7, 2, row) for row in range(6)]
    assert got == [Decimal(0), Decimal(1), Decimal("99999.99"), Decimal("0.01"), Decimal("-99999.99"),
                   Decimal("-0.01")]  # fmt: skip


def test_keys_are_unique_in_key_order_and_filler_is_blank():
    data, values = ei.generate_dataset("ACCT", _spec(20), ACCOUNT, {})
    rows = _rows(data, 25)
    keys = [r[:5] for r in rows]
    assert len(rows) == 20 and len(set(keys)) == 20 and keys == sorted(keys)
    assert all(r[20:25] == b"     " for r in rows)
    assert all(k.strip() for k in keys)  # a key is never blank
    assert len(values["ACCT.ACCT-BAL"]) == 20


def test_a_join_draws_from_the_other_file_and_a_miss_does_not():
    _, pool = ei.generate_dataset("ACCT", _spec(10), ACCOUNT, {})
    accounts = {int(v) for v in pool["ACCT.ACCT-ID"]}
    xref = _spec(30, {"XREF-ACCT": {"from": "ACCT.ACCT-ID"}}, key_len=6)
    data, _ = ei.generate_dataset("XREF", {**xref, "reclen": 11}, XREF, pool)
    assert {int(r[6:11]) for r in _rows(data, 11)} <= accounts
    missing = _spec(30, {"XREF-ACCT": {"from": "ACCT.ACCT-ID", "miss": 0.5}}, key_len=6)
    data, _ = ei.generate_dataset("XREF", {**missing, "reclen": 11}, XREF, pool)
    assert {int(r[6:11]) for r in _rows(data, 11)} - accounts  # some joins miss, on purpose


def test_every_fills_a_cartesian_product():
    fields = {"ACCT-GROUP": {"values": ["A", "B"], "every": 3}, "ACCT-BAL": {"values": [1, 2, 3]}}
    data, values = ei.generate_dataset("ACCT", {**_spec(6, fields), "organization": "sequential"}, ACCOUNT, {})
    pairs = list(zip(values["ACCT.ACCT-GROUP"], values["ACCT.ACCT-BAL"]))
    assert pairs == [("A", 1), ("A", 2), ("A", 3), ("B", 1), ("B", 2), ("B", 3)]


def test_the_same_seed_makes_the_same_bytes_and_another_does_not():
    a, _ = ei.generate_dataset("ACCT", _spec(15, seed=7), ACCOUNT, {})
    b, _ = ei.generate_dataset("ACCT", _spec(15, seed=7), ACCOUNT, {})
    c, _ = ei.generate_dataset("ACCT", _spec(15, seed=8), ACCOUNT, {})
    assert a == b and a != c


def test_joins_are_generated_after_what_they_draw_on_and_cycles_are_refused():
    ds = {"XREF": {"generate": {"fields": {"XREF-ACCT": {"from": "ACCT.ACCT-ID"}}}}, "ACCT": {"generate": {}}}
    assert ei._order(ds) == ["ACCT", "XREF"]
    ds["ACCT"]["generate"] = {"fields": {"ACCT-ID": {"from": "XREF.XREF-ACCT"}}}
    with pytest.raises(ValueError, match="cycle"):
        ei._order(ds)


@pytest.mark.skipif(__import__("os").environ.get("EQUIVALENCE_E2E") != "1",
                    reason="needs Docker (GnuCOBOL) and a JDK + Maven")  # fmt: skip
def test_the_intcalc_port_holds_on_generated_inputs(tmp_path):
    """The carddemo-intcalc port, written against CardDemo's data, proven on generated inputs: edge
    balances and rates, and a group with no rates of its own (the DEFAULT fallback)."""
    import json
    import subprocess

    proc = subprocess.run([sys.executable, str(Path(eq.__file__)), "run", "carddemo-intcalc-generated",  # noqa: S603
                           "--keep", str(tmp_path)], capture_output=True, text=True, check=False)  # fmt: skip
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-3000:]
    report = json.loads((tmp_path / "report.json").read_text())
    assert {dd: (o["equal"], o["records"]) for dd, o in report["outputs"].items()} == {
        "ACCTFILE": (30, 30), "TRANSACT": (37, 37)}  # fmt: skip
    assert "DISCLOSURE GROUP RECORD MISSING" in (tmp_path / "cobol" / "stdout.txt").read_text()
