"""#3624: the behavioural equivalence harness and the pieces it needs from the generator.

Pure parts are pinned here: the field decoder the diff uses (zoned with an overpunched
sign, COMP-3, COMP, text), the record-by-record diff, the generated GnuCOBOL loader /
driver, the generated JUnit run, the entities' record codecs (which item kinds get a
codec, and why an entity gets none), and the JCL PARM a step now hands runBatch. The
end-to-end run -- GnuCOBOL in a container, Maven -- is `tests/tools/equivalence.py run
carddemo-intcalc` (CardDemo CBACT04C: 100/100 records equal with the port, 4/100 as
generated); it runs here only when EQUIVALENCE_E2E=1, as it needs Docker and a JDK.
"""

import json
import os
import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence as eq  # noqa: E402
import equivalence_java as ej  # noqa: E402

from gitgalaxy.core.job_flow import _parm, jcl_job_flow  # noqa: E402
from gitgalaxy.tools.cobol_to_java.cobol_to_java_repository_forge import (  # noqa: E402
    Field,
    _codec_get,
    _codec_kind,
    _codec_put,
)


def test_decode_field_reads_cobol_storage_exactly():
    assert eq.decode_field(b"0000000194{", "S9(09)V99", None) == Decimal("19.40")  # { = +0
    assert eq.decode_field(b"0000001234J", "S9(09)V99", None) == Decimal("-123.41")  # J = -1
    assert eq.decode_field(b"00042", "9(05)", None) == Decimal("42")
    assert eq.decode_field(bytes.fromhex("12345c"), "S9(3)V99", "COMP-3") == Decimal("123.45")
    assert eq.decode_field(bytes.fromhex("00001d"), "S9(3)", "COMP-3") == Decimal("-1")
    assert eq.decode_field(b"\xff\xfe", "S9(4)", "COMP") == Decimal("-2")
    assert eq.decode_field(b"System    ", "X(10)", None) == "System    "
    assert str(eq.decode_field(b"00 00", "9(05)", None)).startswith("<invalid")  # a space is not a zero


def test_diff_pairs_records_and_names_the_differing_fields():
    fields = [{"name": "ID", "offset": 0, "bytes": 3, "pic": "9(3)", "usage": None},
              {"name": "AMT", "offset": 3, "bytes": 5, "pic": "S9(3)V99", "usage": None}]  # fmt: skip
    cobol = b"0010001{" + b"0020002{"
    d = eq.diff_records(cobol, b"0010001{" + b"0020003{", 8, fields)
    assert (d["equal"], d["records"]) == (1, 2)
    assert d["diffs"] == [{"record": 2, "fields": [{"field": "AMT", "cobol": "0.20", "java": "0.30"}]}]
    assert eq.diff_records(cobol, b"0010001{", 8, fields)["diffs"] == [{"record": 2, "missing": "java"}]


def test_generated_cobol_loader_keys_like_the_program_and_fits_the_columns():
    src = eq.cobol_loader("XREFFILE", 50, [{"offset": 0, "length": 16},
                                           {"offset": 25, "length": 11, "duplicates": True}])  # fmt: skip
    assert "ALTERNATE RECORD KEY IS XREFFILE-K1 WITH DUPLICATES" in src
    assert "05 FILLER PIC X(25)." in src and "05 XREFFILE-K1 PIC X(11)." in src
    assert all(len(line) <= 72 for line in src.splitlines())
    drv = eq.cobol_driver("CBACT04C", "2022071800")
    assert "PARM-LEN PIC S9(4) COMP VALUE 10" in drv and "CALL 'CBACT04C' USING JCL-PARM" in drv


def test_the_generated_run_loads_through_codecs_runs_the_step_and_dumps():
    case = json.loads((eq.CASES / "carddemo-intcalc" / "case.json").read_text())
    case["name"] = "carddemo-intcalc"
    java = ej.equivalence_test(case)
    assert 'load("ACCTFILE", 300, AccountRecord::fromRecord, accountRecordRepository);' in java
    assert "cbact04cService.runBatch(List.of(" in java and '"2022071800")' in java
    assert '"gitgalaxy.clock=2022-07-18T10:30:15.00"' in java
    assert 'dump("ACCTFILE", accountRecordRepository.findAll()' in java
    assert 'out.resolve("TRANSACT.out")' in java


def test_record_codec_kinds_and_expressions():
    def f(pic, jtype, usage=None, occurs=None):
        return Field("X-Y", "xY", jtype, 4, 6, pic, occurs, None, usage)

    assert [_codec_kind(f("X(06)", "String")), _codec_kind(f("S9(09)V99", "BigDecimal")),
            _codec_kind(f("S9(07)V99", "BigDecimal", "COMP-3")), _codec_kind(f("9(04)", "Integer", "COMP")),
            _codec_kind(f("ZZ9.99", "String")), _codec_kind(f(None, "Double", "COMP-2"))] == [
        "text", "zoned", "packed", "binary", "text", None]  # fmt: skip
    assert _codec_get(f("9(11)", "Long")) == "CobolRecords.toLong(CobolRecords.zoned(rec, 4, 6, 0, text))"
    assert _codec_put(f("S9(10)V99", "BigDecimal"), "bal") == (
        "CobolRecords.putZoned(rec, 4, 12, 2, true, CobolRecords.decimal(bal), text)")  # fmt: skip
    assert _codec_put(f("S9(07)V99", "BigDecimal", "COMP-3"), "amt") == (
        "CobolRecords.putPacked(rec, 4, 6, 2, true, CobolRecords.decimal(amt))")  # fmt: skip


def test_a_step_hands_runbatch_its_parm():
    assert [_parm("'2022071800'"), _parm("(A,B)"), _parm("'IT''S'"), _parm(None)] == [
        "2022071800", "A,B", "IT'S", None]  # fmt: skip
    rows = jcl_job_flow("//J JOB (A)\n//STEP15 EXEC PGM=CBACT04C,PARM='2022071800'\n")
    assert next(r for r in rows if r["kind"] == "STEP")["parm"] == "2022071800"


@pytest.mark.skipif(os.environ.get("EQUIVALENCE_E2E") != "1", reason="needs Docker (GnuCOBOL) and a JDK + Maven")
def test_carddemo_intcalc_is_equivalent_end_to_end(tmp_path):
    import subprocess

    proc = subprocess.run([sys.executable, str(Path(eq.__file__)), "run", "carddemo-intcalc", "--keep",  # noqa: S603
                           str(tmp_path)], capture_output=True, text=True, check=False)  # fmt: skip
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-3000:]
    report = json.loads((tmp_path / "report.json").read_text())
    assert all(o["equal"] == o["records"] == 50 for o in report["outputs"].values())


def test_the_two_sides_share_the_cases_directory():
    assert ej.CASES == eq.CASES and (eq.CASES / "carddemo-intcalc" / "case.json").is_file()


def test_publish_examples_scan_comparison_and_compile_workflow():
    import publish_examples as pe

    src = {k: 1 for k, _ in pe._ROWS} | {"languages": {"cobol": 3, "jcl": 2}}
    java = {k: 2 for k, _ in pe._ROWS} | {"languages": {"java": 9}}
    md = pe.comparison_markdown("demo", src, java, ("cobol",))
    assert "| Source files | 1 | 2 |" in md and "Source estate by language: cobol 3, jcl 2." in md
    wf = pe.compile_workflow(["carddemo", "zecs"])
    assert "example: [carddemo, zecs]" in wf and "working-directory: examples/${{ matrix.example }}/java" in wf
    assert "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1" in wf  # pinned by SHA, as gitgalaxy's own
    assert [s for s, _, _ in pe.EXAMPLES] == ["carddemo", "cbsa", "genapp", "zecs", "zopeneditor", "dsf-pli"]


def test_published_examples_carry_their_sources_licences(tmp_path):
    import publish_examples as pe

    for name in ("LICENSE", "NOTICE", "LICENSE.md", "README.md", "COPYING"):
        (tmp_path / name).write_text("x")
    assert [p.name for p in pe.legal_files(tmp_path)] == ["COPYING", "LICENSE", "LICENSE.md", "NOTICE"]
    entry = {"name": "cbsa", "url": "https://example.org/cbsa", "ref": "4" * 40, "license": "EPL-2.0"}
    header = pe.file_header(entry)
    assert "licensed EPL-2.0" in header and "4" * 40 in header and "modified in" in header
    notices = pe.third_party_notices([{"slug": "cbsa", "corpus": entry, "legal": ["LICENSE", "NOTICES"]}], [])
    assert (
        "| `examples/cbsa/` | [cbsa](https://example.org/cbsa) at `444444444444` | EPL-2.0 | LICENSE, NOTICES |"
        in notices
    )
    assert "not affiliated with, sponsored or endorsed" in notices
    case = eq.CASES / "carddemo-intcalc"
    assert (case / "LICENSE").is_file() and (case / "NOTICE").is_file()  # the port and data are CardDemo-derived
    assert "licensed Apache-2.0" in (case / "port/service/Cbact04cService.java").read_text()[:600]
