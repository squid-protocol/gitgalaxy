"""#5089: an IDCAMS define the engine reads, whose name keeps install placeholders, must not become the file's base."""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import equivalence_cics as ec

RAW = "@ECS_HLQ@.ZCEXPIRE.@ENVIRONMENT@"
RESOLVED = "ZECS.ZCEXPIRE.TEST"


def _ir():
    define = SimpleNamespace(
        name=RAW, kind="CLUSTER", related=None, organization="INDEXED", key_offset=0, key_length=4,
        record_max=2048, record_avg=None,
    )  # fmt: skip
    entry = {"program": "p.cbl", "name": "ZCEXPIRE", "definitions": [{"dsname": RAW, "record_format": "V"}]}
    return SimpleNamespace(files={"x": SimpleNamespace(vsam_defines=[define])}, cics_file_lineage=lambda: [entry])


def test_the_stated_vsam_wins_over_a_define_that_keeps_its_placeholders():
    vsam = {"key_offset": 0, "key_length": 4, "reclen": 70, "variable": True, "why": "ZX-RECORD is 70 bytes"}
    files = ec.stub_files(_ir(), "p.cbl", {RESOLVED: {"vsam": vsam}}, {"ECS_HLQ": "ZECS", "ENVIRONMENT": "TEST"})
    assert [(f["base"], f["reclen"]) for f in files] == [(RESOLVED, 70)]
