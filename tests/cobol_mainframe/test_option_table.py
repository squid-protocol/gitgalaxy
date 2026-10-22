"""#4706: the compiler option table -- every result-changing option the estate's PARM / defaults / cards can carry is
refused by name or declared, never silently recorded (register C5; #4702 IBM is the reference, GnuCOBOL the instrument).

Enterprise COBOL for z/OS 6.x Programming Guide, "Compiler options": each option's own section (ZONEDATA, INVDATA,
CODEPAGE, NSYMBOL, DISPSIGN, AFP, FLOAT, SSRANGE, NUMCHECK, INITCHECK, OPTIMIZE)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import equivalence_common as common  # noqa: E402

from gitgalaxy.core import compiler_options as co  # noqa: E402
from gitgalaxy.core import estate_options as eo  # noqa: E402

PLAIN = "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. P.\n"
REFUSED = {"ZONEDATA(NOPFD)": "ZONEDATA", "ZONEDATA(MIG)": "ZONEDATA", "INVDATA": "INVDATA", "INVD(FNC,CS)": "INVDATA",
           "NSYMBOL(DBCS)": "NSYMBOL", "DISPSIGN(SEP)": "DISPSIGN", "DS(S)": "DISPSIGN", "FLOAT(NATIVE)": "FLOAT", "NOZWB": "NOZWB"}  # fmt: skip
DECLARED = {
    "SSRANGE": "NOSSRANGE",
    "SSR(ZLEN,ABD)": "NOSSRANGE",
    "NUMCHECK(ZON,MSG)": "NONUMCHECK",
    "NC(BIN,ABD)": "NONUMCHECK",
}
HONOURED = ["ZONEDATA(PFD)", "NOINVDATA", "CODEPAGE(1140)", "CP(37)", "NSYMBOL(NATIONAL)", "NS(NAT)", "DISPSIGN(COMPAT)",
            "FLOAT(HEX)", "AFP(VOLATILE)", "AFP(NOVOLATILE)", "NOSSRANGE", "NOSSR", "NONUMCHECK", "NONC", "INITCHECK",
            "IC(STRICT)", "NOINITCHECK", "ZWB", "OPTIMIZE(0)", "OPT(2)", "OPTIMIZE(FULL)", "OPT"]  # fmt: skip


def _case(*options: str, **extra):
    return {"compiler_options": list(options), **extra}


@pytest.mark.parametrize("option,name", sorted(REFUSED.items()))
@pytest.mark.parametrize("where", ["parm", "card"])
def test_an_option_the_harness_cannot_honour_is_refused_by_name(option, name, where):
    case, src = (_case(option), PLAIN) if where == "parm" else ({}, f"       CBL {option}\n" + PLAIN)
    with pytest.raises(common.UnsupportedOption, match=re.escape(name)):
        common.compile_options(case, src)


@pytest.mark.parametrize("option,applied", sorted(DECLARED.items()))
@pytest.mark.parametrize("where", ["parm", "card"])
def test_an_option_that_only_matters_on_a_violation_is_a_declared_difference(option, applied, where):
    case, src = (_case(option), PLAIN) if where == "parm" else ({}, f"       CBL {option}\n" + PLAIN)
    common.compile_options(case, src)  # proven, not refused
    (d,) = common.option_differences(case, src, None)
    assert (d["kind"], d["applied"]) == ("option", applied)
    assert d["option"] in ("SSRANGE", "NUMCHECK") and d["declared"].startswith(d["option"])


@pytest.mark.parametrize("option", HONOURED)
def test_default_and_no_effect_values_are_clean(option):
    case = _case(option)
    assert common.option_differences(case, PLAIN, None) == []
    common.compile_options(case, PLAIN)
    assert eo.effective_options(case).unhonoured(PLAIN) == []


def test_a_later_card_cancels_an_earlier_parm():
    case = _case("SSRANGE", "ZONEDATA(MIG)")
    src = "       PROCESS NOSSRANGE,ZONEDATA(PFD)\n" + PLAIN
    assert common.option_differences(case, src, None) == []
    common.compile_options(case, src)
    with pytest.raises(common.UnsupportedOption):  # the other way: the card turns it on
        common.compile_options(_case("ZONEDATA(PFD)"), "       CBL ZD(NOPFD)\n" + PLAIN)


def test_nothing_named_is_ibms_defaults_and_clean():
    assert eo.effective_options({}).unhonoured(PLAIN) == []
    assert common.option_differences({}, PLAIN, None) == []


def test_codepage_is_honoured_for_the_default_or_the_data_s_own_ccsid():
    assert common.data_ccsid({}) is None  # Latin-1: no CCSID page
    assert common.data_ccsid({"data_encoding": "cp037"}) == "37"
    assert common.data_ccsid({"data_encoding": "cp285"}) == "285"
    (d,) = common.option_differences(_case("CODEPAGE(285)"), PLAIN, None)
    assert (d["option"], d["declared"]) == ("CODEPAGE", "285") and "no CCSID page" in d["applied"]
    assert common.option_differences(_case("CODEPAGE(285)", data_encoding="cp285"), PLAIN, None) == []
    assert common.option_differences(_case("CODEPAGE(1140)", data_encoding="cp285"), PLAIN, None) == []


def test_the_estates_own_values_are_resolved_not_merely_recorded():
    genapp = eo.effective_options({"corpus": "cics-genapp", "program": "LGACDB01"})
    assert [u["option"] for u in genapp.unhonoured(PLAIN)] == ["CODEPAGE"]
    assert genapp.unhonoured(PLAIN)[0]["source"].endswith("cobol.jcl:49")
    for corpus in json.loads((ROOT / "tests/cobol_mainframe/corpora.json").read_text(encoding="utf-8"))["corpora"]:
        if (eo.ESTATE_OPTIONS_DIR / f"{corpus['name']}.json").is_file():
            for u in eo.effective_options({"corpus": corpus["name"]}).unhonoured(PLAIN):
                assert u["policy"] == "declare", u  # an estate whose own default is refused could prove nothing


def test_the_fingerprint_of_an_unchanged_option_set_is_untouched():
    """the evidence option fingerprint hashes SEMANTIC_OPTIONS only: this table adds none"""
    assert set(co.SEMANTIC_OPTIONS) == {"ARITH", "INTDATE", "NUMPROC", "TRUNC", "YEARWINDOW"}
    assert not set(co.OPTION_TABLE) & set(co.SEMANTIC_OPTIONS)


def test_every_table_row_has_a_policy_a_default_and_a_reason():
    for name, row in co.OPTION_TABLE.items():
        assert row["policy"] in ("refuse", "declare", None), name
        assert row["default"] and row["reason"], name
        assert (row["policy"] is None) == (row["honoured"] is None), name
        if row["policy"] == "declare":
            assert row.get("applied") or name == "CODEPAGE", name


def test_the_register_table_lists_every_option():
    """docs/language_status/register/C5.md's table has one row per OPTION_TABLE option and per cobc-decided option"""
    text = (ROOT / "docs/language_status/register/C5.md").read_text(encoding="utf-8")
    table = text.split("### Compile options: the table (#4706)")[1]
    rows = {m.group(1) for m in re.finditer(r"^\| `(?:NO)?([A-Z]+)", table, re.M)}
    assert {o.removeprefix("NO") for o in co.OPTION_TABLE} | set(co.COBC_DECIDED_OPTIONS) <= rows


def test_a_later_zwb_cancels_nozwb_and_the_reverse_refuses():
    src = "       CBL ZWB\n" + PLAIN
    common.compile_options(_case("NOZWB"), src)  # the card cancels the PARM
    assert common.option_differences(_case("NOZWB"), src, None) == []
    with pytest.raises(common.UnsupportedOption, match="NOZWB"):
        common.compile_options(_case("ZWB"), "       PROCESS NOZWB\n" + PLAIN)


def test_optimize_changes_no_defined_result_and_cites_the_zero_divisor_stance():
    """OPTIMIZE is recorded only; its row says a zero divisor is followed from cobc at any level (C14), in code and register"""
    row = co.OPTION_TABLE["OPTIMIZE"]
    assert row["policy"] is None and "C14" in row["reason"]
    text = (ROOT / "docs/language_status/register/C5.md").read_text(encoding="utf-8")
    line = next(ln for ln in text.splitlines() if ln.startswith("| `OPTIMIZE("))
    assert "C14" in line and "follows cobc" in line
    for level in ("0", "1", "2", "STD", "FULL"):
        eff = co.effective_with_defaults([f"OPTIMIZE({level})"])
        assert not [u for u in co.unhonoured(eff) if u["option"] == "OPTIMIZE"], level
