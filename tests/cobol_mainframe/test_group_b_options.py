"""#4704 / #4706 group B: CODEPAGE, NSYMBOL / DBCS, DISPSIGN, AFP / FLOAT, SSRANGE, NUMCHECK / INITCHECK, OPTIMIZE have a
fate (refused by name, a declared difference, or recorded as no-effect), in every spelling and in both places an option
can come from (the PARM and a CBL / PROCESS card), and no value a burned estate records for them newly refuses.

Enterprise COBOL for z/OS 6.x Programming Guide, "Compiler options": the option's own section (CODEPAGE, NSYMBOL,
DISPSIGN, AFP, FLOAT, SSRANGE, NUMCHECK, INITCHECK, OPTIMIZE)."""

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
GROUP_B = ("CODEPAGE", "NSYMBOL", "DISPSIGN", "FLOAT", "AFP", "SSRANGE", "NUMCHECK", "INITCHECK", "OPTIMIZE")
SOURCE_SUFFIXES = {".cbl", ".cob", ".cobol"}
# spelling -> the option it names, by the policy the table gives it
REFUSED = {"NSYMBOL(DBCS)": "NSYMBOL", "NS(DBCS)": "NSYMBOL", "DISPSIGN(SEP)": "DISPSIGN", "DS(S)": "DISPSIGN",
           "DISPSIGN(S)": "DISPSIGN", "FLOAT(NATIVE)": "FLOAT"}  # fmt: skip
DECLARED = {"SSRANGE": "SSRANGE", "SSR": "SSRANGE", "SSRANGE(ZLEN,ABD)": "SSRANGE", "NUMCHECK": "NUMCHECK",
            "NC": "NUMCHECK", "NUMCHECK(ZON,MSG)": "NUMCHECK", "NC(PAC,ABD)": "NUMCHECK"}  # fmt: skip
NO_EFFECT = ["AFP", "AFP(VOLATILE)", "AFP(NOVOLATILE)", "NOAFP", "INITCHECK", "IC", "IC(STRICT)", "NOINITCHECK",
             "NOIC", "OPTIMIZE", "OPTIMIZE(0)", "OPT(1)", "OPT(2)", "OPT(STD)", "OPTIMIZE(FULL)", "OPT", "NOOPT",
             "FLOAT(HEX)", "FLOAT(S390)", "NSYMBOL(NATIONAL)", "NS(NAT)", "DISPSIGN(COMPAT)", "DS(C)",
             "CODEPAGE(1140)", "CODEPAGE(37)", "CP(37)", "NOSSRANGE", "NOSSR", "NONUMCHECK", "NONC"]  # fmt: skip


def _corpora() -> Path | None:
    env = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    for c in (Path(env) if env else None, ROOT / ".mainframe_corpora"):
        if c and c.is_dir():
            return c
    return None


def _names(estate: dict) -> list[str | None]:
    """None (the estate's default PARM) and every program the file overrides"""
    return [None, *sorted((estate.get("parm") or {}).get("programs") or {})]


def _where(option: str, where: str):
    return ({"compiler_options": [option]}, PLAIN) if where == "parm" else ({}, f"       CBL {option}\n" + PLAIN)


def test_every_group_b_option_has_a_fate():
    """a row in OPTION_TABLE with a policy (or none: no defined result) and a row in the C5 table"""
    assert set(GROUP_B) <= set(co.OPTION_TABLE)
    for o in GROUP_B:
        assert co.OPTION_TABLE[o]["policy"] in ("refuse", "declare", None), o
    assert {co.OPTION_TABLE[o]["policy"] for o in REFUSED.values()} == {"refuse"}
    assert {co.OPTION_TABLE[o]["policy"] for o in DECLARED.values()} == {"declare"}
    assert {o for o in GROUP_B if co.OPTION_TABLE[o]["policy"] is None} == {"AFP", "INITCHECK", "OPTIMIZE"}
    text = (ROOT / "docs/language_status/register/C5.md").read_text(encoding="utf-8")
    table = text.split("### Compile options: the table (#4706)")[1]
    rows = {m.group(1) for m in re.finditer(r"^\| `(?:NO)?([A-Z]+)", table, re.M)}
    assert set(GROUP_B) <= rows


@pytest.mark.parametrize("where", ["parm", "card"])
@pytest.mark.parametrize("option,name", sorted(REFUSED.items()))
def test_the_values_it_cannot_honour_are_refused_by_name(option, name, where):
    case, src = _where(option, where)
    with pytest.raises(common.UnsupportedOption, match=name):
        common.compile_options(case, src)


@pytest.mark.parametrize("where", ["parm", "card"])
@pytest.mark.parametrize("option,name", sorted(DECLARED.items()))
def test_the_run_only_options_are_proven_as_off_and_declared(option, name, where):
    case, src = _where(option, where)
    common.compile_options(case, src)
    (d,) = common.option_differences(case, src, None)
    assert (d["kind"], d["option"]) == ("option", name)
    assert d["applied"] == co.OPTION_TABLE[name]["applied"]


@pytest.mark.parametrize("where", ["parm", "card"])
@pytest.mark.parametrize("option", NO_EFFECT)
def test_the_default_and_no_effect_values_are_clean(option, where):
    case, src = _where(option, where)
    common.compile_options(case, src)
    assert common.option_differences(case, src, None) == []
    assert eo.effective_options(case).unhonoured(src) == []


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_no_value_an_estate_records_refuses_a_program(path):
    """installation defaults, the default PARM and every per-program override: a group-B option is at most declared"""
    estate = json.loads(path.read_text(encoding="utf-8"))
    for name in _names(estate):
        case = {"corpus": estate["corpus"], "program": name or "NOPROGRAM"}
        resolved = eo.effective_options(case)
        refused = [
            u["option"] for u in resolved.unhonoured(PLAIN) if u["policy"] == "refuse" and u["option"] in GROUP_B
        ]
        assert refused == [], (path.stem, name, refused)
        common.compile_options(case, PLAIN)


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_no_card_in_a_burned_estate_s_source_refuses_it(path):
    """every program's own CBL / PROCESS cards, over the estate's values: no group-B option newly refuses"""
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
        try:
            common.compile_options({"corpus": path.stem, "program": src.stem}, text)
        except common.UnsupportedOption as exc:
            refused.append(f"{src.name}: {exc}")
    assert [r for r in refused if any(o in r for o in GROUP_B)] == []
