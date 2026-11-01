"""#7434: a file defined only in the CSD (a DSNAME, no IDCAMS DEFINE) is keyed by the case's stated vsam."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import equivalence_cics as ec

DSN = "CRUCIBLE.HC.RFILE"
VSAM = {
    "key_offset": 0,
    "key_length": 4,
    "reclen": 16,
    "why": "hc-file-read-set: HCRS.dat, 4-byte key, 16-byte records",
}


def _ir(record_format=None, defines=()):
    d = {"dsname": DSN}
    if record_format:
        d["record_format"] = record_format
    entry = {"program": "p.cbl", "name": "HCRS", "definitions": [d]}
    return SimpleNamespace(
        files={"x": SimpleNamespace(vsam_defines=list(defines))},
        cics_file_lineage=lambda: [entry],
        vsam_stores=lambda: [],
    )


def _run(vsam, **kw):
    return ec.stub_files(_ir(**kw), "p.cbl", {DSN: {"vsam": vsam}} if vsam is not None else {})


def test_a_csd_only_ksds_takes_the_stated_key_at_offset_zero():
    assert _run(VSAM) == [
        {
            "file": "HCRS",
            "dsname": DSN,
            "base": DSN,
            "key_offset": 0,
            "key_length": 4,
            "reclen": 16,
            "via": ["the case's vsam"],
        }  # fmt: skip
    ]


def test_a_key_at_a_non_zero_offset_is_kept():
    (f,) = _run({**VSAM, "key_offset": 6, "reclen": 40})
    assert (f["key_offset"], f["key_length"], f["reclen"]) == (6, 4, 40)


def test_nothing_stated_is_still_refused():
    with pytest.raises(ec.Unsupported, match="no IDCAMS DEFINE"):
        _run(None)


@pytest.mark.parametrize("missing", ["key_offset", "key_length", "reclen", "why"])
def test_an_incomplete_vsam_is_refused_by_name(missing):
    with pytest.raises(ec.Unsupported, match=DSN):
        _run({k: v for k, v in VSAM.items() if k != missing})


@pytest.mark.parametrize(
    "bad", [{"key_length": "4"}, {"key_length": 0}, {"reclen": 0}, {"key_offset": -1}, {"key_offset": True}]
)
def test_a_non_integer_or_empty_extent_is_refused(bad):
    with pytest.raises(ec.Unsupported):
        _run({**VSAM, **bad})


def test_a_variable_length_file_needs_variable_true():
    with pytest.raises(ec.Unsupported, match="variable-length"):
        _run(VSAM, record_format="V")
    (f,) = _run({**VSAM, "variable": True}, record_format="V")
    assert f["reclen"] == 16


def test_a_defined_cluster_wins_over_a_stated_vsam():
    define = SimpleNamespace(
        name=DSN, kind="CLUSTER", related=None, organization="INDEXED", key_offset=2, key_length=8,
        record_max=64, record_avg=None,
    )  # fmt: skip
    (f,) = _run(VSAM, defines=[define])
    assert (f["key_offset"], f["key_length"], f["reclen"], f["via"]) == (2, 8, 64, [])
