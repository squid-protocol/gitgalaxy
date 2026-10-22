"""#4271 / #4050: the z/OS capture kit for HFP (tests/tools/hfp_capture_kit.py): the program it emits, and the ingest."""

from __future__ import annotations

import json
import shutil
import sys
from fractions import Fraction as F
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


def test_a_pow_record_becomes_a_compute_with_the_exponentiation_operator():
    r = next(x for x in K.records() if x["id"] == "asm-pow-eps-5pct-monthly-360")
    text = "".join(K.statements(r))
    assert "COMPUTE LR = LA ** LB" in text and "HEX-OF(LR-X)" in text and "asm-pow-eps-5pct-monthly-360|" in text
    assert r["id"] in {x["id"] for x in K.askable(K.records())}
    assert K.skip_reason({**r, "size": "short"}) == K.SKIP_SHORT


def test_the_pow_reference_is_exact_for_an_integer_exponent_and_truncates_to_long():
    two, three = K.H.of(2), K.H.of(3)
    assert K.power(two, three) == 8 and K.power(two, K.H.of(-3)) == F(1, 8)
    root = K.power(K.H.of(4), K.H.decode(bytes.fromhex("4080000000000000")))  # 4 ** 0.5
    assert abs(root - 2) < F(1, 10**15) and root <= 2
    with pytest.raises(ValueError):
        K.power(K.H.of(-4), K.H.decode(bytes.fromhex("4080000000000000")))


def test_a_pow_capture_that_disagrees_with_the_reference_is_a_finding(table):
    recs = K.records(table)
    ident = "asm-pow-eps-5pct-monthly-12"
    out = _sysout(recs, skip={ident}) + f"{ident}|4110D18F228CDE63\n"
    res = K.ingest(out, table, "J1", "GO", _under())
    assert len(res["findings"]) == 1 and f"zos-{ident}" in res["findings"][0]


def test_verify_reports_what_ingest_would_and_writes_nothing(table, tmp_path, capsys):
    recs = K.records(table)
    before = table.read_text(encoding="utf-8")
    ok = tmp_path / "ok.txt"
    ok.write_text(_sysout(recs), encoding="utf-8")
    assert K.main(["verify", str(ok), "--table", str(table)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["added"] == ["zos-" + r["id"] for r in K.askable(recs)] and report["findings"] == []
    bad = tmp_path / "bad.txt"
    bad.write_text(_sysout(recs, skip={"enc-1", "disp-1.5"}) + "enc-1|41200000\n", encoding="utf-8")
    assert K.main(["verify", str(bad), "--table", str(table)]) == 1
    report = json.loads(capsys.readouterr().out)
    assert "zos-enc-1" in report["findings"][0] and report["missing"] == ["disp-1.5"]
    assert table.read_text(encoding="utf-8") == before


def test_a_dry_run_ingest_needs_no_evidence_and_a_real_one_still_does(table):
    recs = K.records(table)
    assert K.ingest(_sysout(recs), table, "", "", {}, dry_run=True)["added"]
    with pytest.raises(ValueError):
        K.ingest(_sysout(recs), table, "", "", {})


def _asm_sysout(recs):
    return "\n".join(f"{r['id']}|{K.compute(r)}" for r in K.asm_askable(recs)) + "\n"


def test_the_assembler_kit_asks_exactly_the_records_the_cobol_kit_skips():
    recs = K.records()
    skipped_by_cobol = set(K.skipped(recs))
    asm = {r["id"] for r in K.asm_askable(recs)}
    assert asm == skipped_by_cobol and len(asm) == 28
    assert not K.skipped(recs, "asm")
    assert not asm & {r["id"] for r in K.askable(recs)}


def test_each_skipped_op_becomes_the_instruction_its_row_states():
    by_id = {r["id"]: r for r in K.records()}
    one = lambda i: "\n".join(K.asm_statements(by_id[i], 1))  # noqa: E731
    assert "THDER 2,0" in one("from_ieee-1-short") and "STD   2,RES" in one("from_ieee-1-short")
    assert "THDR  2,0" in one("from_ieee-1-long")
    assert "TBEDR 2,4,0" in one("to_ieee-1-short") and "STE   2,RES" in one("to_ieee-1-short")
    assert "TBDR  2,4,0" in one("to_ieee-1-long") and "STD   2,RES" in one("to_ieee-1-long")
    assert "MEER  0,2" in one("mul-1-half") and "DER   0,2" in one("div-1-2")
    assert "LA    4,2" in one("from_ieee-1-long") and "LA    4,1" in one("mul-1-half")
    with pytest.raises(ValueError, match="cannot ask"):
        K.asm_statements({"id": "x", "op": "add", "size": "long", "a": "00"}, 1)


def test_the_emitted_assembler_is_deterministic_within_column_71_and_prints_every_id():
    recs = K.records()
    src = K.emit_asm(recs)
    assert src == K.emit_asm(recs)
    assert all(len(line) <= 71 for line in src.splitlines())
    assert src.splitlines()[0] == "*PROCESS OPTABLE(UNI)" and src.rstrip().endswith("END")
    for r in K.asm_askable(recs):
        assert f"=C'{r['id']}|'" in src
    assert src.count("PUT   SYSPRINT,LINE") == len(K.asm_askable(recs))
    assert src.count("DC    XL8'") >= len(K.asm_askable(recs))
    assert "TBEDR" in src and "THDR" in src and "MEER" in src and "DER" in src


def test_verify_and_ingest_of_the_assembler_output_use_the_kit_flag(table, tmp_path, capsys):
    recs = K.records()
    out = tmp_path / "sysout.txt"
    out.write_text(_asm_sysout(recs), encoding="utf-8")
    before = table.read_bytes()
    assert K.main(["verify", str(out), "--table", str(table), "--kit", "asm"]) == 0
    assert table.read_bytes() == before
    assert len(json.loads(capsys.readouterr().out)["added"]) == 28
    # the COBOL kit's report of the same output names no asm record: they are not its to ask
    assert not K.ingest(out.read_text(), table, "", "", {}, dry_run=True)["added"]
    res = K.ingest(out.read_text(), table, "JOB1", "GO", _under(), kit="asm")
    assert len(res["added"]) == 28 and not res["findings"] and not res["missing"]
    assert all(r["source"] == "zos-run" for r in K.records(table) if r["id"].startswith("zos-"))


def test_an_assembler_result_that_disagrees_with_the_model_is_a_finding(table):
    recs = K.records()
    text = _asm_sysout(recs).replace("from_ieee-1-short|41100000", "from_ieee-1-short|41100001")
    res = K.ingest(text, table, "", "", {}, dry_run=True, kit="asm")
    assert [f for f in res["findings"] if f.startswith("zos-from_ieee-1-short")]
    assert len(res["findings"]) == 1


def test_the_cli_also_emits_the_assembler_kit(tmp_path):
    assert K.main(["emit", str(tmp_path)]) == 0
    assert (tmp_path / "HFPCAPA.asm").read_text() == K.emit_asm(K.records())
    assert "ASMACLG" in (tmp_path / "HFPCAPA.jcl").read_text()


# HFPCAPA is never assembled here (no HLASM): this lint holds what a first z/OS assembly would reject or truncate.
_REG = r"(?:1[0-5]|[0-9])"
_ADDR = rf"[A-Z@#$][A-Z0-9@#$]*(?:[+-]\d+)?|\d+\({_REG}?,?{_REG}?\)|\d+\({_REG}\)|\d+\(,{_REG}\)|\d+"
# mnemonic -> (operand regex, bytes of object code); macros get a generous size
_ASM_SHAPES = {
    "LE": (rf"{_REG},({_ADDR})", 4),
    "LD": (rf"{_REG},({_ADDR})", 4),
    "STE": (rf"{_REG},({_ADDR})", 4),
    "STD": (rf"{_REG},({_ADDR})", 4),
    "ST": (rf"{_REG},({_ADDR})", 4),
    "LA": (rf"{_REG},({_ADDR})", 4),
    "L": (rf"{_REG},({_ADDR})", 4),
    "STM": (rf"{_REG},{_REG},({_ADDR})", 4),
    "LM": (rf"{_REG},{_REG},({_ADDR})", 4),
    "LR": (rf"{_REG},{_REG}", 2),
    "SLR": (rf"{_REG},{_REG}", 2),
    "BR": (_REG, 2),
    "BAS": (rf"{_REG},([A-Z]\w*)", 4),
    "BCT": (rf"{_REG},([A-Z]\w*)", 4),
    "THDER": (rf"{_REG},{_REG}", 4),
    "THDR": (rf"{_REG},{_REG}", 4),
    "TBEDR": (rf"{_REG},[0-9],{_REG}", 4),
    "TBDR": (rf"{_REG},[0-9],{_REG}", 4),
    "MEER": (rf"{_REG},{_REG}", 4),
    "DER": (rf"{_REG},{_REG}", 2),
    "MVC": (r"(?:[A-Z]\w*(?:\(\d+\))?|\d+\(\d+,\d+\)),(=C'[^']*'|[A-Z]\w*|\d+\(\d+\))", 6),
    "UNPK": (r"[A-Z]\w*\(\d+\),[A-Z]\w*\(\d+\)", 6),
    "TR": (r"[A-Z]\w*\(\d+\),[A-Z]\w*-\d+", 6),
    "OPEN": (r"\(SYSPRINT,\(OUTPUT\)\)", 40),
    "CLOSE": (r"\(SYSPRINT\)", 40),
    "PUT": (r"SYSPRINT,LINE", 40),
}
_ASM_DIRECTIVES = {"CSECT", "AMODE", "RMODE", "YREGS", "USING", "LTORG", "DS", "DC", "DCB", "END"}


def _asm_parse(src):
    stmts = []
    for line in src.splitlines():
        if not line or line.startswith("*"):
            continue
        label, rest = line[:8].strip(), line[9:].split(None, 1)
        assert line[8] == " " and rest, line
        stmts.append((label, rest[0], rest[1] if len(rest) > 1 else ""))
    return stmts


def test_the_assembler_kit_passes_a_static_hlasm_lint():
    import re

    stmts = _asm_parse(K.emit_asm(K.records()))
    labels = [s[0] for s in stmts if s[0] and s[1] not in ("AMODE", "RMODE")]  # their name field names the CSECT
    assert len(labels) == len(set(labels)), "a label defined twice"
    assert all(len(lab) <= 8 and re.fullmatch(r"[A-Z@#$][A-Z0-9@#$]*", lab) for lab in labels)
    refs, size = set(), 0
    for _label, op, operands in stmts:
        if op in _ASM_DIRECTIVES:
            continue
        assert op in _ASM_SHAPES, f"unknown mnemonic {op}"
        shape, nbytes = _ASM_SHAPES[op]
        m = re.fullmatch(shape, operands)
        assert m, f"{op} operands {operands!r} do not fit the instruction format"
        size += nbytes
        refs |= {
            g for g in m.groups() if g and re.fullmatch(r"[A-Z@#$][A-Z0-9@#$]*", g) and g not in {"LINE"} | set(labels)
        }
        refs |= {g for g in re.findall(r"[A-Z@#$][A-Z0-9@#$]+", operands) if not g.startswith("C") or g in labels}
    undefined = {r for r in refs if r not in labels and r not in {"SYSPRINT", "OUTPUT"}}
    assert not undefined, f"operands name labels nobody defines: {sorted(undefined)}"
    # data: one XL8 per operand, the literal pool and the work areas
    size += sum(8 for _l, op, o in stmts if op == "DC" and o.startswith("XL8")) + 400
    assert size < 8192 - 256, f"HFPCAPA (~{size} bytes) outgrows the two base registers' 8192 bytes"


def test_every_assembler_data_constant_is_an_even_run_of_upper_hex_digits():
    import re

    for _label, op, operands in _asm_parse(K.emit_asm(K.records())):
        m = re.fullmatch(r"XL8'([0-9A-F]*)'", operands) if op == "DC" and operands.startswith("XL8") else None
        if m:
            assert len(m.group(1)) == 16
