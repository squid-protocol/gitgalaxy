"""#7965 (X22): a case can state a region that installs several instances of one template.

`install_symbols` resolves a template (`ZC@ID@FILE`) to ONE instance (`ZC01FILE`). `region_instances` names the others the
region also defines (`ZC02FILE`): the stub's files.cfg gives each an empty data set and the port's region set holds it.
One generated table still stands behind every instance (register X22), so the port refuses a task that reaches one.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import equivalence_cics as EC  # noqa: E402

FILES = [
    {"file": "ZC@ID@FILE", "base": "zcfile", "reclen": 80, "key_offset": 0, "key_length": 8},
    {"file": "ZC@ID@KEY", "base": "zckey", "reclen": 40, "key_offset": 0, "key_length": 8},
    {"file": "PLAINFIL", "base": "plain", "reclen": 10, "key_offset": 0, "key_length": 2},
]
SYMBOLS = {"values": {"ID": "01"}, "why": "instance 01"}


def _case(values=None, **extra):
    case = {"install_symbols": SYMBOLS, **extra}
    if values is not None:
        case["region_instances"] = {"values": values, "why": "the region also installs instance 02"}
    return case


def test_no_key_is_no_extra_instance():
    assert EC.region_instances(_case(), FILES) == []
    assert EC._instance_cfg(_case(), FILES, "/work/files") == ""


def test_each_template_takes_its_own_extra_instance():
    got = EC.region_instances(_case(["ZC02FILE", "ZC02KEY", "ZC03FILE"]), FILES)
    assert [(n, f["base"]) for n, f in got] == [("ZC02FILE", "zcfile"), ("ZC02KEY", "zckey"), ("ZC03FILE", "zcfile")]
    cfg = EC._instance_cfg(_case(["ZC02FILE", "ZC02KEY"]), FILES, "/work/files").splitlines()
    assert cfg[0].startswith("ZC02FILE /work/files/zcfile.ZC02FILE 80 0 8")
    assert cfg[1].startswith("ZC02KEY /work/files/zckey.ZC02KEY 40 0 8")


@pytest.mark.parametrize(
    "bad",
    [
        ["ZC01FILE"],  # the case's own instance
        ["PLAINFIL"],  # a plain file is not a template instance
        ["NOSUCH"],  # fits no template
        ["zc02file"],  # not upper case
        ["ZC02FILE", "ZC02FILE"],  # twice
        [],
        "ZC02FILE",
        [7],
    ],
)
def test_a_value_that_is_not_another_instance_of_one_template_is_refused(bad):
    with pytest.raises(EC.Unsupported):
        EC.region_instances(_case(bad), FILES)


def test_the_statement_needs_a_reason_and_no_other_key():
    for spec in ({"values": ["ZC02FILE"]}, {"values": ["ZC02FILE"], "why": "x", "more": 1}, ["ZC02FILE"]):
        case = {**_case(), "region_instances": spec}
        with pytest.raises(EC.Unsupported):
            EC.region_instances(case, FILES)
