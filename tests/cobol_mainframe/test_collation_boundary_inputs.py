"""#4035 (layer 3): a field the program compares as alphanumeric is generated on the collation boundary.

COBOL orders alphanumerics by the collating sequence (EBCDIC: lower case < upper < digits) after padding the shorter
operand with spaces; String.compareTo does neither. Pinned without a corpus, on a hand-written program and layout:
which fields are found, the boundary classes the values cover, and that a `compareTo` port disagrees with the
EBCDIC order on them (so the field-by-field comparison catches it instead of passing by luck).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import equivalence_inputs as ei  # noqa: E402

PROGRAM = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. COLLTEST.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY CUSTREC.
       01  WS-N                 PIC 9(4).
       PROCEDURE DIVISION.
           IF CUST-GROUP > 'M' AND < 'T'
               DISPLAY 'MID'
           END-IF
           IF CUST-CODE = 'AB'
               DISPLAY 'AB'
           END-IF
           IF CUST-KIND-LETTER
               DISPLAY 'LETTER'
           END-IF
           IF CUST-NOTE IS ALPHABETIC
               DISPLAY 'ALPHA'
           END-IF
           IF CUST-COUNT > 5
               DISPLAY 'FIVE'
           END-IF
           IF WS-N > 5
               DISPLAY 'N'
           END-IF
           GOBACK.
"""
COPYBOOK = """\
       01  CUST-RECORD.
           05  CUST-ID              PIC X(4).
           05  CUST-GROUP           PIC X(1).
           05  CUST-CODE            PIC X(4).
           05  CUST-KIND            PIC X(1).
               88  CUST-KIND-LETTER VALUE 'A' THRU 'Z'.
           05  CUST-NOTE            PIC X(3).
           05  CUST-COUNT           PIC 9(3).
           05  CUST-EXP-DATE        PIC X(10).
"""


def _corpus(tmp_path: Path) -> tuple[dict, Path]:
    (tmp_path / "cbl").mkdir()
    (tmp_path / "cpy").mkdir()
    (tmp_path / "cbl" / "COLLTEST.cbl").write_text(PROGRAM)
    (tmp_path / "cpy" / "CUSTREC.cpy").write_text(COPYBOOK)
    case = {"program": "COLLTEST", "program_source": "cbl/COLLTEST.cbl", "copy_dirs": ["cpy"]}
    return case, tmp_path


def _layout():
    return [
        {"name": "CUST-ID", "offset": 0, "bytes": 4, "pic": "X(4)", "usage": None},
        {"name": "CUST-GROUP", "offset": 4, "bytes": 1, "pic": "X(1)", "usage": None},
        {"name": "CUST-CODE", "offset": 5, "bytes": 4, "pic": "X(4)", "usage": None},
        {"name": "CUST-KIND", "offset": 9, "bytes": 1, "pic": "X(1)", "usage": None},
        {"name": "CUST-NOTE", "offset": 10, "bytes": 3, "pic": "X(3)", "usage": None},
        {"name": "CUST-COUNT", "offset": 13, "bytes": 3, "pic": "9(3)", "usage": None},
        {"name": "CUST-EXP-DATE", "offset": 16, "bytes": 10, "pic": "X(10)", "usage": None},
    ]


def _spec(collation=True, fields=None):
    return {"reclen": 26, "organization": "sequential",
            "generate": {"records": 60, "seed": 3, "collation": collation, "fields": fields or {}}}  # fmt: skip


def _col(data, offset, n):
    return [data[i + offset : i + offset + n].decode("latin-1") for i in range(0, len(data), 26)]


def test_operands_are_the_alphanumeric_fields_with_their_literals(tmp_path):
    ops = ei.collation_operands(*_corpus(tmp_path))
    assert ops["CUST-GROUP"] == ["M", "T"]  # the abbreviated condition's subject carries forward
    assert ops["CUST-CODE"] == ["AB"]
    assert ops["CUST-KIND"] == ["A", "Z"]  # the level-88 THRU endpoints, over the item it tests
    assert "CUST-NOTE" not in ops  # a class condition is no comparison
    assert "CUST-COUNT" not in ops and "WS-N" not in ops  # numeric


def test_boundary_values_cover_the_disagreement_classes():
    vals = ei.boundary_values(4, ["AB"])
    assert all(len(v) == 4 for v in vals) and len(vals) == len(set(vals))
    assert "A   " in vals and "1   " in vals  # a letter and a digit, padded with blanks
    assert "a   " in vals and "AB  " in vals and "ab  " in vals  # lower against upper case
    assert "AB0 " in vals and "ABA " in vals and "A   " in vals  # the literal's neighbours and prefix
    assert "    " in vals  # blank
    assert "\x00" * 4 in vals and "\xff" * 4 in vals  # LOW- / HIGH-VALUES


def test_high_values_are_the_last_byte_in_ebcdic_data():
    vals = ei.boundary_values(3, [], "cp037")
    assert [v.encode("cp037") for v in vals if v.startswith("\x9f")] == [b"\xff\xff\xff"]
    assert b"\x00\x00\x00" in [v.encode("cp037") for v in vals]


def test_a_compare_to_port_disagrees_with_ebcdic_on_the_values():
    vals = ei.boundary_values(1, ["M", "T"])

    def ebcdic(a):
        return a.encode("cp037")

    pairs = [(a, b) for a in vals for b in vals if a != b]
    assert any((a < b) != (ebcdic(a) < ebcdic(b)) for a, b in pairs)  # UTF-16 order is not the code page's
    assert any((a < "M") != (ebcdic(a) < ebcdic("M")) for a in vals)  # at the literal itself
    assert any(a.isdigit() for a in vals) and any(a.isupper() for a in vals) and any(a.islower() for a in vals)


def test_generated_fields_take_boundary_values_and_others_do_not(tmp_path):
    case, corpus = _corpus(tmp_path)
    ops = ei.collation_operands(case, corpus)
    data, values = ei.generate_dataset("CUST", _spec(), _layout(), {}, collation=ops)
    assert set(_col(data, 4, 1)) >= {"A", "a", "M", "T", "1", " ", "\x00", "\xff"}  # CUST-GROUP
    assert {"AB  ", "ab  ", "AB0 "} <= set(_col(data, 5, 4))
    assert set(values["CUST.CUST-ID"]) != set(_col(data, 5, 4))
    assert all(c.isdigit() for c in _col(data, 13, 3))  # a numeric field is still numeric
    assert all(d[4] == d[7] == "-" for d in _col(data, 16, 10) if d.strip())  # a date-shaped name keeps its dates
    assert not {"\x00", "\xff"} & set("".join(_col(data, 0, 4)))  # a field the program never compares: plain values


def test_it_is_opt_in_deterministic_and_a_case_rule_wins(tmp_path):
    case, corpus = _corpus(tmp_path)
    ops = ei.collation_operands(case, corpus)
    off, _ = ei.generate_dataset("CUST", _spec(False), _layout(), {}, collation=ops)
    assert off == ei.generate_dataset("CUST", _spec(False), _layout(), {})[0]  # `collation` unset: as before
    a, _ = ei.generate_dataset("CUST", _spec(), _layout(), {}, collation=ops)
    b, _ = ei.generate_dataset("CUST", _spec(), _layout(), {}, collation=ops)
    assert a == b
    ruled, _ = ei.generate_dataset(
        "CUST", _spec(fields={"CUST-GROUP": {"values": ["Q"]}}), _layout(), {}, collation=ops
    )
    assert set(_col(ruled, 4, 1)) == {"Q"}


def test_a_key_part_stays_unique_and_never_a_boundary_blank(tmp_path):
    case, corpus = _corpus(tmp_path)
    spec = {**_spec(), "organization": "indexed", "keys": [{"offset": 5, "length": 4}]}
    data, _ = ei.generate_dataset("CUST", spec, _layout(), {}, collation={"CUST-CODE": ["AB"]})
    keys = _col(data, 5, 4)
    assert len(set(keys)) == len(keys) and all(k.strip() for k in keys)


def test_generate_all_reads_the_program_only_when_asked(tmp_path):
    case, corpus = _corpus(tmp_path)
    (corpus / "cpy" / "CUSTFILE.cpy").write_text(COPYBOOK)
    spec = {"input": "@generate", **_spec()}
    spec["generate"]["copybook"] = "cpy/CUSTFILE.cpy"
    case["datasets"] = {"CUSTIN": spec}
    on = ei.generate_inputs(case, corpus)["CUSTIN"]
    assert "a" in _col(on, 4, 1)
    spec["generate"]["collation"] = False
    off = ei.generate_inputs(case, corpus)["CUSTIN"]
    assert on != off
