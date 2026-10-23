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
