"""#4704 / #4706 group A: ZONEDATA / INVDATA, TRUNC(OPT), ARITH(EXTEND), INTDATE(LILIAN) have a fate, and no value a
burned estate records for them newly refuses (the harness stops by name only on a value it cannot honour, and the
estates' own values never are one).

Enterprise COBOL for z/OS 6.x Programming Guide, "Compiler options": the option's own section (TRUNC, ARITH, INTDATE,
ZONEDATA, INVDATA)."""

from __future__ import annotations

import json
import os
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
FILES = sorted(eo.ESTATE_OPTIONS_DIR.glob("*.json"))
GROUP_A = ("ZONEDATA", "INVDATA", "TRUNC", "ARITH", "INTDATE")
SOURCE_SUFFIXES = {".cbl", ".cob", ".cobol"}


def _corpora() -> Path | None:
    env = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    for c in (Path(env) if env else None, ROOT / ".mainframe_corpora"):
        if c and c.is_dir():
            return c
    return None


def _names(estate: dict) -> list[str | None]:
    """None (the estate's default PARM) and every program the file overrides"""
    return [None, *sorted((estate.get("parm") or {}).get("programs") or {})]


def test_every_group_a_option_has_a_fate():
    """modelled / honoured by cobc (COBC_OPTIONS), or refused / declared in OPTION_TABLE; and a row in the C5 table"""
    decided = {opt for opt, _ in common.COBC_OPTIONS}
    assert {"TRUNC", "ARITH", "INTDATE"} <= decided
    assert {"ZONEDATA", "INVDATA"} <= set(co.OPTION_TABLE)
    assert all(co.OPTION_TABLE[o]["policy"] == "refuse" for o in ("ZONEDATA", "INVDATA"))
    text = (ROOT / "docs/language_status/register/C5.md").read_text(encoding="utf-8")
    table = text.split("### Compile options: the table (#4706)")[1]
    rows = {m.group(1) for m in re.finditer(r"^\| `(?:NO)?([A-Z]+)", table, re.M)}
    assert set(GROUP_A) <= rows


@pytest.mark.parametrize(
    "option,value",
    [
        ("TRUNC", "OPT"),
        ("TRUNC", "STD"),
        ("TRUNC", "BIN"),
        ("ARITH", "EXTEND"),
        ("ARITH", "COMPAT"),
        ("INTDATE", "ANSI"),
    ],
)
def test_the_values_cobc_decides_are_honoured(option, value):
    common.compile_options({"compiler_options": [f"{option}({value})"]}, PLAIN)


@pytest.mark.parametrize(
    "option,name", [("INTDATE(LILIAN)", "INTDATE"), ("ZONEDATA(MIG)", "ZONEDATA"), ("INVDATA", "INVDATA")]
)
def test_the_values_it_cannot_honour_are_refused_by_name(option, name):
    with pytest.raises(common.UnsupportedOption, match=name):
        common.compile_options({"compiler_options": [option]}, PLAIN)


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_no_value_an_estate_records_refuses_a_program(path):
    """installation defaults, the default PARM and every per-program override resolve and compile without a refusal"""
    estate = json.loads(path.read_text(encoding="utf-8"))
    for name in _names(estate):
        case = {"corpus": estate["corpus"], "program": name or "NOPROGRAM"}
        resolved = eo.effective_options(case)
        assert resolved.unhonoured(PLAIN) == [] or all(u["policy"] == "declare" for u in resolved.unhonoured(PLAIN))
        common.compile_options(case, PLAIN)
        assert not resolved.version_conflicts(PLAIN), (path.stem, name)


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_no_card_in_a_burned_estate_s_source_refuses_it(path):
    """every program's own CBL / PROCESS cards, over the estate's values: no group-A option newly refuses"""
    corpora = _corpora()
    if corpora is None or not (corpora / path.stem).is_dir():
        pytest.skip("needs the corpus checkouts (GITGALAXY_MAINFRAME_CORPORA)")
    refused: list[str] = []
    for src in sorted((corpora / path.stem).rglob("*")):
        if src.suffix.lower() not in SOURCE_SUFFIXES or not src.is_file():
            continue
        text = common.read_program({"corpus": path.stem}, src)[0]
        if not co.compiler_options(text):
            continue
        case = {"corpus": path.stem, "program": src.stem}
        try:
            common.compile_options(case, text)
        except common.UnsupportedOption as exc:
            refused.append(f"{src.name}: {exc}")
    assert [r for r in refused if any(o in r for o in GROUP_A)] == []
