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
import equivalence_common as common  # noqa: E402
import equivalence_java as ej  # noqa: E402

from gitgalaxy.core.job_flow import _parm, jcl_job_flow  # noqa: E402
from gitgalaxy.tools.cobol_to_java.cobol_to_java_repository_forge import (  # noqa: E402
    Field,
    _codec_get,
    _codec_kind,
    _codec_put,
)


def _cobol(*lines: str) -> str:
    return "".join(f"       {line}\n" for line in lines)


def test_layout_fields_expands_a_nested_copy_so_later_fields_keep_their_offsets(tmp_path):
    """#4010: CALINK's WS-BLOCK -- a COPY inside the record, then more fields. Dropping the COPY
    put WS-AFTER-FLAG at offset 0 instead of 100."""
    (tmp_path / "src").mkdir()
    (tmp_path / "copy").mkdir()
    (tmp_path / "copy/CAHDR.cpy").write_text(
        _cobol(
            "    10  HDR-EYE        PIC X(4).",
            "    10  HDR-INNER.",
            "        COPY CATAIL.",
            "    10  HDR-LEN        PIC S9(4) COMP.",
        )
    )
    (tmp_path / "copy/CATAIL.cpy").write_text(_cobol("        15  TAIL-TXT   PIC X(94)."))
    (tmp_path / "src/CALINK.cbl").write_text(_cobol(
        "IDENTIFICATION DIVISION.", "PROGRAM-ID. CALINK.", "DATA DIVISION.", "WORKING-STORAGE SECTION.",
        "01  WS-BLOCK.", "    05  WS-HEAD.", "    COPY CAHDR.", "    05  WS-AFTER-FLAG   PIC X.",
        "01  WS-OTHER             PIC X(3).", "PROCEDURE DIVISION.", "    GOBACK."))  # fmt: skip
    fields = common.layout_fields(tmp_path, "src/CALINK.cbl", "WS-BLOCK", copy_dirs=[tmp_path / "copy"])
    assert [(f["name"], f["offset"], f["bytes"]) for f in fields] == [
        ("HDR-EYE", 0, 4), ("TAIL-TXT", 4, 94), ("HDR-LEN", 98, 2), ("WS-AFTER-FLAG", 100, 1)]  # fmt: skip
    # the default search: the file's own directory, then the corpus root
    (tmp_path / "copy/CATAIL.cpy").rename(tmp_path / "CATAIL.cpy")
    (tmp_path / "copy/CAHDR.cpy").rename(tmp_path / "src/cahdr.cpy")
    assert common.layout_fields(tmp_path, "src/CALINK.cbl", "WS-BLOCK") == fields


def test_layout_fields_fails_loudly_on_a_copy_it_cannot_expand(tmp_path):
    """#4010: an unresolved COPY inside the record raises instead of shifting every later field;
    one outside it (before the record, or past a section header) is harmless. REPLACING is refused
    by name."""
    (tmp_path / "P.cbl").write_text(_cobol(
        "DATA DIVISION.", "WORKING-STORAGE SECTION.", "COPY DFHAID.", "01  WS-A.", "    05  A-1   PIC X.",
        "    COPY GONE.", "    05  A-2   PIC X.", "01  WS-B.", "    05  B-1   PIC X(2).", "LINKAGE SECTION.",
        "COPY DFHEIBLK.", "PROCEDURE DIVISION."))  # fmt: skip
    with pytest.raises(common.LayoutError, match="COPY GONE inside WS-A"):
        common.layout_fields(tmp_path, "P.cbl", "WS-A")
    assert [(f["name"], f["offset"]) for f in common.layout_fields(tmp_path, "P.cbl", "WS-B")] == [("B-1", 0)]
    with pytest.raises(common.LayoutError, match="no record WS-C"):
        common.layout_fields(tmp_path, "P.cbl", "WS-C")
    (tmp_path / "R.cbl").write_text(_cobol("01  WS-R.", "    COPY HDR", "        REPLACING ==:X:== BY ==WS==."))
    (tmp_path / "HDR.cpy").write_text(_cobol("    05  :X:-A   PIC X."))
    with pytest.raises(common.LayoutError, match="COPY HDR REPLACING"):
        common.layout_fields(tmp_path, "R.cbl", "WS-R")


def test_decode_field_reads_cobol_storage_exactly():
    assert eq.decode_field(b"0000000194{", "S9(09)V99", None) == Decimal("19.40")  # { = +0
    assert eq.decode_field(b"0000001234J", "S9(09)V99", None) == Decimal("-123.41")  # J = -1
    assert eq.decode_field(b"00042", "9(05)", None) == Decimal("42")
    assert eq.decode_field(bytes.fromhex("12345c"), "S9(3)V99", "COMP-3") == Decimal("123.45")
    assert eq.decode_field(bytes.fromhex("00001d"), "S9(3)", "COMP-3") == Decimal("-1")
    assert eq.decode_field(b"\xff\xfe", "S9(4)", "COMP") == Decimal("-2")
    assert eq.decode_field(b"System    ", "X(10)", None) == "System    "
    assert str(eq.decode_field(b"00 00", "9(05)", None)).startswith("<invalid")  # a space is not a zero


@pytest.mark.parametrize("raw, pic, usage", [(b"  12", "9(4)", None), (b"+012", "9(4)", None), (b"1_20", "9(4)", None),
                                         ("١٢٣٤".encode(), "9(8)", None), (b" 12{", "S9(4)", None),
                                         (bytes.fromhex("1a2c"), "S9(3)", "COMP-3"), (bytes.fromhex("0123"), "S9(3)", "COMP-3")])  # fmt: skip
def test_storage_a_numeric_test_would_reject_is_never_a_number(raw, pic, usage):
    """#3830: `int()` takes spaces, `+`, `_` and non-ASCII digits; COBOL's NUMERIC does not."""
    assert str(eq.decode_field(raw, pic, usage)).startswith("<invalid")


def test_a_separate_sign_is_read_at_either_end():
    assert eq.decode_field(b"+0012", "S9(4)", None, sign_separate=True) == Decimal("12")
    assert eq.decode_field(b"0012-", "S9(4)", None, sign_separate=True) == Decimal("-12")
    assert str(eq.decode_field(b"00012", "S9(4)", None, sign_separate=True)).startswith("<invalid")


def test_same_value_other_bytes_is_a_difference_shown_as_bytes():
    """#3830: a C vs F sign nibble, or -0 vs +0, decodes to the same number -- but the files differ."""
    fields = [{"name": "AMT", "offset": 0, "bytes": 2, "pic": "S9(3)", "usage": "COMP-3"}]
    d = eq.diff_records(bytes.fromhex("012c"), bytes.fromhex("012f"), 2, fields)
    assert d["equal"] == 0 and d["diffs"] == [
        {"record": 1, "fields": [{"field": "AMT", "cobol": "012c", "java": "012f", "raw": True}]}]  # fmt: skip
    assert eq.diff_records(bytes.fromhex("000d"), bytes.fromhex("000c"), 2, fields)["equal"] == 0  # -0 vs +0
    assert "AMT (bytes; same value)" in eq.report_markdown(
        {"program": "P", "name": "c", "corpus": "x", "program_source": "p"}, {"java": "j", "outputs": {"OUT": d}}
    )


def test_diff_pairs_records_and_names_the_differing_fields():
    fields = [{"name": "ID", "offset": 0, "bytes": 3, "pic": "9(3)", "usage": None},
              {"name": "AMT", "offset": 3, "bytes": 5, "pic": "S9(3)V99", "usage": None}]  # fmt: skip
    cobol = b"0010001{" + b"0020002{"
    d = eq.diff_records(cobol, b"0010001{" + b"0020003{", 8, fields)
    assert (d["equal"], d["records"]) == (1, 2)
    assert d["diffs"] == [{"record": 2, "fields": [{"field": "AMT", "cobol": "0.20", "java": "0.30"}]}]
    assert eq.diff_records(cobol, b"0010001{", 8, fields)["diffs"] == [{"record": 2, "missing": "java"}]


def test_a_filler_difference_is_counted_apart_not_as_a_failure():
    fields = [{"name": "ID", "offset": 0, "bytes": 3, "pic": "9(3)", "usage": None},
              {"name": "FILLER", "offset": 3, "bytes": 2, "pic": "X(2)", "usage": None}]  # fmt: skip
    d = eq.diff_records(b"00100" + b"00200", b"001  " + b"003  ", 5, fields)
    assert (d["equal"], d["filler_differs"]) == (1, 2)
    assert d["diffs"] == [{"record": 2, "fields": [{"field": "ID", "cobol": "2", "java": "3"}]}]


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


def test_a_corrupted_field_after_a_currency_edited_field_is_reported():
    """#3820: `05 A PIC X(3). 05 AMT PIC £££,££9.99. 05 B PIC X(4).` -- AMT is 10 bytes, so B
    sits at 13; a corrupted B is a difference whether the layout places it right or not."""
    right = [{"name": "A", "offset": 0, "bytes": 3, "pic": "X(3)", "usage": None},
             {"name": "AMT", "offset": 3, "bytes": 10, "pic": "£££,££9.99", "usage": None},
             {"name": "B", "offset": 13, "bytes": 4, "pic": "X(4)", "usage": None}]  # fmt: skip
    cobol = b"ABC" + b" \xa31,234.56" + b"WXYZ"
    java = b"ABC" + b" \xa31,234.56" + b"WXQZ"
    d = eq.diff_records(cobol, java, 17, right)
    assert d["diffs"] == [{"record": 1, "fields": [{"field": "B", "cobol": "WXYZ", "java": "WXQZ"}]}]
    assert d["layout_bytes"] == 17
    # The pre-#3820 reader lost AMT's PIC: its layout stopped at A, so B was never compared --
    # the corruption now surfaces as bytes outside the layout instead of a false pass.
    short = right[:1]
    d = eq.diff_records(cobol, java, 17, short)
    assert d["equal"] == 0 and d["layout_bytes"] == 3
    assert d["diffs"] == [
        {"record": 1, "fields": [{"field": "(bytes outside the layout @15..16)", "cobol": "b'Y'", "java": "b'Q'"}]}
    ]
    # Identical records still pass with a short layout.
    assert eq.diff_records(cobol, cobol, 17, short)["equal"] == 1
