"""#4704 acceptance audit: every option the issue's Gap 1 names has a row (modelled / honoured by cobc, refused by name,
or a declared difference), and the estate-intake checklist asks the customer for the input that states it. A new
Gap-1 option is added to GAP1 here with its row, or the audit names it."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import equivalence_common as common  # noqa: E402

from gitgalaxy.core import compiler_options as co  # noqa: E402
from gitgalaxy.core.runtime_options import RUNTIME_OPTION_TABLE  # noqa: E402

INTAKE = (ROOT / "docs/language_status/estate_intake.md").read_text(encoding="utf-8")

# (Gap-1 option, where its row lives, the key there, the intake term that asks for the input stating it)
GAP1 = [
    ("ZONEDATA", "compile", "ZONEDATA", "ZONEDATA"),
    ("INVDATA", "compile", "INVDATA", "INVDATA"),
    ("CODEPAGE", "compile", "CODEPAGE", "CODEPAGE"),
    ("NSYMBOL / DBCS", "compile", "NSYMBOL", "NSYMBOL"),
    ("DISPSIGN", "compile", "DISPSIGN", "DISPSIGN"),
    ("AFP", "compile", "AFP", "AFP"),
    ("FLOAT", "compile", "FLOAT", "FLOAT"),
    ("SSRANGE", "compile", "SSRANGE", "SSRANGE"),
    ("NUMCHECK", "compile", "NUMCHECK", "NUMCHECK"),
    ("INITCHECK", "compile", "INITCHECK", "INITCHECK"),
    ("OPTIMIZE", "compile", "OPTIMIZE", "OPTIMIZE"),
    ("TRUNC(OPT)", "cobc", "TRUNC", "TRUNC"),
    ("ARITH(EXTEND)", "cobc", "ARITH", "ARITH"),
    ("INTDATE(LILIAN)", "cobc", "INTDATE", "INTDATE"),
    ("compiler version", "compile", None, "IGY630"),
    ("installation defaults", "compile", None, "IGYCDOPT"),
    ("LE STORAGE", "runtime", "le.runtime_options.STORAGE", "STORAGE"),
    ("LE TRAP", "runtime", "le.runtime_options.TRAP", "TRAP"),
    ("LE ABTERMENC", "runtime", "le.runtime_options.ABTERMENC", "ABTERMENC"),
    ("CEEOPTS", "runtime", "le.source.CEEOPTS", "CEEOPTS"),
    ("CEEUOPT", "runtime", "le.source.CEEUOPT", "CEEUOPT"),
    ("Db2 DATE", "runtime", "db2.format.DATE", "DATE and TIME"),
    ("Db2 TIME", "runtime", "db2.format.TIME", "DATE and TIME"),
    ("Db2 DEC", "runtime", "db2.format.DEC", "DEC (15 / 31)"),
    ("Db2 DECPT", "runtime", "db2.format.DECPT", "DECPT"),
    ("Db2 SQLCCSID", "runtime", "db2.ccsid.SQLCCSID", "SQLCCSID"),
    ("Db2 CCSID", "runtime", "db2.ccsid.EBCDIC_CCSID", "CCSIDs"),
    ("Db2 ISOLATION", "runtime", "db2.bind.ISOLATION", "ISOLATION"),
    ("CICS translator options", "runtime", "cics.translator.options", "CICS translator options"),
    ("CICS region code page", "runtime", "cics.region.LOCALCCSID", "LOCALCCSID"),
]


@pytest.mark.parametrize("name,kind,key,_term", GAP1, ids=[g[0] for g in GAP1])
def test_every_gap1_option_has_a_row(name, kind, key, _term):
    if kind == "compile" and key:
        row = co.OPTION_TABLE[key]
        assert row["reason"] and row["default"], name
    elif kind == "cobc":
        assert key in {opt for opt, _ in common.COBC_OPTIONS}, name
    elif kind == "runtime":
        row = RUNTIME_OPTION_TABLE[key]
        assert row["policy"] in ("refuse", "declare", None) and row["reason"], name


@pytest.mark.parametrize("name,_kind,_key,term", GAP1, ids=[g[0] for g in GAP1])
def test_the_intake_checklist_asks_for_every_gap1_option(name, _kind, _key, term):
    assert term in INTAKE, f"{name}: estate_intake.md never asks for {term}"


# ---- the table-coverage and per-estate halves (#4704 acceptance audit) -------------------------------------------
# Table rows that are not a Gap-1 option: each is named so a NEW row fails until someone classifies it.
NOT_GAP1 = {
    "NOZWB": "a ZONEDATA companion flag, covered by the ZONEDATA row",
    "le.source.CEEDOPT": "the installation LE defaults member; read with the IGYCDOPT-class installation inputs",
    "db2.bind.ACTION": "bind subcommand option beyond Gap 1",
    "db2.bind.CURRENTDATA": "bind option beyond Gap 1",
    "db2.bind.DYNAMICRULES": "bind option beyond Gap 1",
    "db2.bind.VALIDATE": "bind option beyond Gap 1",
    "db2.bind.packages": "package list, not an option value",
    "db2.precompile.PARM": "precompile PARM, beyond Gap 1",
    "db2.precompile.coprocessor": "precompile versus coprocessor, beyond Gap 1",
    "cics.region.CICS_TS": "region release, beyond Gap 1",
    "cics.region.DB2CONN": "region Db2 connection, beyond Gap 1",
    "cics.program_definition.CONCURRENCY": "program definition, beyond Gap 1",
    "cics.program_definition.EXECKEY": "program definition, beyond Gap 1",
}

# Gap-1 runtime keys a burned estate's options file does not record, and why that is the honest answer.
_NO_LE_SOURCE = "no CEEOPTS / CEEUOPT member in the corpus (#5307): nothing reads one"
_NO_DB2 = "the estate has no Db2 (no EXEC SQL, no bind or precompile step)"
LE_SOURCES = ("le.source.CEEOPTS", "le.source.CEEUOPT")
ABSENT_OK = {
    "aws-mainframe-modernization-carddemo": {"db2.ccsid.EBCDIC_CCSID": "no bind card or precompile PARM names one"},
    "cics-async-api-credit-card-application-example": {
        "db2.ccsid.EBCDIC_CCSID": _NO_DB2,
        "db2.bind.ISOLATION": _NO_DB2,
    },
    "cics-banking-sample-application-cbsa": {"db2.ccsid.EBCDIC_CCSID": "DB2BIND.jcl names no EBCDIC CCSID"},
    "cics-genapp": {"db2.ccsid.SQLCCSID": "no precompile PARM names SQLCCSID"},
    "dbb-mortgage-application": {
        "db2.ccsid.EBCDIC_CCSID": "no bind card or precompile PARM names one",
        "db2.bind.ISOLATION": "no bind card in the corpus names an isolation",
    },
    "zecs": dict.fromkeys(
        ("db2.format.DATE", "db2.format.TIME", "db2.format.DEC", "db2.format.DECPT",
         "db2.ccsid.SQLCCSID", "db2.ccsid.EBCDIC_CCSID", "db2.bind.ISOLATION"), _NO_DB2),
}  # fmt: skip
for _estate in ABSENT_OK:
    ABSENT_OK[_estate].update(dict.fromkeys(LE_SOURCES, _NO_LE_SOURCE))


def _recorded(data: dict) -> set[str]:
    out: set[str] = set()

    def visit(o, path):
        if isinstance(o, dict):
            if "source" in o and "value" in o:
                out.add(path)
                return
            for k, v in o.items():
                visit(v, f"{path}.{k}" if path else k)

    visit({s: data.get(s) for s in ("le", "db2", "cics")}, "")
    return out


def test_every_table_row_is_gap1_or_named_as_not():
    keys = {k for _, kind, k, _ in GAP1 if k and kind in ("compile", "runtime")}
    rows = set(co.OPTION_TABLE) | set(RUNTIME_OPTION_TABLE)
    assert not (rows - keys - set(NOT_GAP1)), f"unclassified rows: {sorted(rows - keys - set(NOT_GAP1))}"
    assert not (set(NOT_GAP1) - rows), "NOT_GAP1 names a row the tables no longer have"
    assert not (set(NOT_GAP1) & keys)


def _estate_files():
    return sorted((ROOT / "tests" / "equivalence" / "estate_options").glob("*.json"))


def test_the_absent_map_names_exactly_the_burned_estates():
    assert {p.stem for p in _estate_files()} == set(ABSENT_OK)


@pytest.mark.parametrize("path", _estate_files(), ids=lambda p: p.stem)
def test_every_gap1_runtime_option_is_recorded_or_absent_with_a_reason(path):
    import json

    recorded = _recorded(json.loads(path.read_text(encoding="utf-8")))
    absent = ABSENT_OK[path.stem]
    gap1_runtime = {k for _, kind, k, _ in GAP1 if kind == "runtime"}
    assert not (gap1_runtime - recorded - set(absent)), sorted(gap1_runtime - recorded - set(absent))
    stale = {k for k in absent if k in recorded}
    assert not stale, f"{path.stem}: recorded now, drop from ABSENT_OK: {sorted(stale)}"
    assert all(absent.values())
    assert set(absent) <= gap1_runtime
