"""#4707: the LE / Db2 / CICS runtime option table -- every runtime option an estate options file can record is refused
by name, a declared difference, or says why no result depends on it (register C18; #4702 IBM is the reference).

Language Environment Programming Reference, "Runtime options" (STORAGE, TRAP, ABTERMENC); Db2 for z/OS Installation
Guide, panel DSNTIPF (DATE, TIME, DEC, DECPT) and DSNTIPF CCSIDs; CICS Resource Definition Guide (PROGRAM)."""

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

from gitgalaxy.core import estate_options as eo  # noqa: E402
from gitgalaxy.core.runtime_options import (
    BIND_OPTIONS,
    CICS_CONVENTIONS,
    CICS_OPTIONS,
    DB2_OPTIONS,
    LE_OPTIONS,
    RUNTIME_OPTION_TABLE,
    PRECOMPILE_OPTIONS,
    RUNTIME_USED_BY,
    TRANSLATOR_OPTIONS,
    bind_rows,
    calibration_problems,
    cics_rows,
    conventions_rows,
    db2_rows,
    le_rows,
    precompile_rows,
    precompile_tokens,
    runtime_effect,
    runtime_unhonoured,
    translator_rows,
    translator_tokens,
    used_by_rows,
)  # noqa: E402

ESTATES = sorted((ROOT / "tests" / "equivalence" / "estate_options").glob("*.json"))
PLAIN = "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. P.\n"
REFUSED = [
    ("le", "runtime_options.TRAP", "OFF"),
    ("le", "runtime_options.ABTERMENC", "RETCODE"),
    ("db2", "format.DATE", "USA"),
    ("db2", "format.TIME", "EUR"),
    ("db2", "format.DEC", "31"),
    ("db2", "format.DECPT", ","),
    ("db2", "ccsid.SQLCCSID", "YES"),
]
DECLARED = [
    ("le", "runtime_options.STORAGE", "00,NONE,NONE,0K"),
    ("db2", "ccsid.EBCDIC_CCSID", "285"),
    ("cics", "region.LOCALCCSID", "285"),
]
HONOURED = [
    ("le", "runtime_options.STORAGE", "NONE,NONE,NONE,0K"),
    ("le", "runtime_options.TRAP", "ON,SPIE"),
    ("le", "runtime_options.TRAP", "on"),
    ("le", "runtime_options.ABTERMENC", "ABEND"),
    ("db2", "format.DATE", "ISO"),
    ("db2", "format.TIME", "ISO"),
    ("db2", "format.DEC", "15"),
    ("db2", "format.DECPT", "."),
    ("db2", "ccsid.EBCDIC_CCSID", "037"),
    ("db2", "ccsid.EBCDIC_CCSID", "1140"),
    ("cics", "region.LOCALCCSID", "37"),
    ("db2", "bind.ISOLATION", "RR"),
    ("cics", "program_definition.EXECKEY", "CICS"),
]


def _estate(section: str, key: str, value: str) -> dict:
    group, name = key.split(".", 1)
    return {"estate": "t", section: {group: {name: {"value": value, "source": "t:1"}}}}


@pytest.fixture
def put_estate(tmp_path, monkeypatch):
    def put(section, key, value):
        (tmp_path / "t.json").write_text(json.dumps(_estate(section, key, value)))
        monkeypatch.setattr(eo, "ESTATE_OPTIONS_DIR", tmp_path)
        return {"corpus": "t", "program": "P"}

    return put


def _all_keys():
    for path in ESTATES:
        data = json.loads(path.read_text(encoding="utf-8"))
        for section in ("le", "db2", "cics"):
            for group, items in (data.get(section) or {}).items():
                for name, entry in (items or {}).items():
                    yield path.stem, f"{section}.{group}.{name}", entry


def test_every_recorded_option_has_a_row():
    missing = {key for _, key, _ in _all_keys() if key not in RUNTIME_OPTION_TABLE}
    assert not missing


def test_every_row_is_complete():
    for key, row in RUNTIME_OPTION_TABLE.items():
        assert row["reason"] and row["default"] is not None, key
        assert row["policy"] in (None, "refuse", "declare"), key
        assert row["kind"] in ("value", "ccsid"), key
        if row["policy"]:
            assert row["honoured"], key
        if row["policy"] == "declare":
            assert row["applied"], key


def test_the_register_lists_every_row():
    text = (ROOT / "docs" / "language_status" / "register" / "C18.md").read_text(encoding="utf-8")
    assert not [key for key in RUNTIME_OPTION_TABLE if f"| `{key}` " not in text]


@pytest.mark.parametrize("section,key,value", REFUSED)
def test_a_value_the_harness_cannot_honour_is_refused_by_name(put_estate, section, key, value):
    case = put_estate(section, key, value)
    with pytest.raises(common.UnsupportedOption, match=re.escape(f"{section}.{key}")):
        common.compile_options(case, PLAIN)


@pytest.mark.parametrize("section,key,value", DECLARED)
def test_a_value_the_harness_runs_differently_is_a_declared_difference(put_estate, section, key, value):
    case = put_estate(section, key, value)
    common.compile_options(case, PLAIN)  # proven, not refused
    (d,) = common.option_differences(case, PLAIN, None)
    assert d["option"] == f"{section}.{key}"
    assert d["applied"] == RUNTIME_OPTION_TABLE[f"{section}.{key}"]["applied"]


@pytest.mark.parametrize("section,key,value", HONOURED)
def test_a_default_or_no_effect_value_is_clean(put_estate, section, key, value):
    case = put_estate(section, key, value)
    assert common.option_differences(case, PLAIN, None) == []
    common.compile_options(case, PLAIN)
    assert eo.effective_options(case).unhonoured_runtime() == []


def test_a_ccsid_row_is_honoured_for_the_data_code_page():
    runtime = {"db2": {"ccsid.EBCDIC_CCSID": "285"}}
    assert runtime_unhonoured(runtime, None, "285") == []
    assert runtime_unhonoured(runtime, None, "37")[0]["policy"] == "declare"


def test_an_option_without_a_row_is_refused_by_name():
    (hit,) = runtime_unhonoured({"le": {"runtime_options.NEWOPT": "X"}}, {"le.runtime_options.NEWOPT": "f:9"})
    assert (hit["policy"], hit["source"]) == ("refuse", "f:9")
    assert "no row in the runtime option table" in hit["note"]
    assert runtime_effect("le.runtime_options.NEWOPT", "X") == "unjudged"


def test_validate_flags_an_option_without_a_row():
    data = json.loads(ESTATES[0].read_text(encoding="utf-8"))
    data["le"].setdefault("runtime_options", {})["NEWOPT"] = {"value": "X", "source": "f:1"}
    assert any("NEWOPT" in e for e in eo.validate(data))


@pytest.mark.parametrize("path", ESTATES, ids=lambda p: p.stem)
def test_no_estate_refuses_its_own_recorded_values(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    hits = eo.effective_options({"program": "P"}, data).unhonoured_runtime()
    assert [h for h in hits if h["policy"] == "refuse"] == []


def test_the_oracle_and_the_resolver_see_one_list(put_estate):
    case = put_estate("db2", "ccsid.EBCDIC_CCSID", "285")
    mine = eo.effective_options(case).unhonoured_runtime(common.data_ccsid(case))
    assert [d["option"] for d in common.option_differences(case, PLAIN, None)] == [h["option"] for h in mine]


def test_the_runtime_values_stay_in_the_fingerprint(put_estate):
    a = eo.effective_options(put_estate("le", "runtime_options.TRAP", "ON")).fingerprint()
    b = eo.effective_options(put_estate("le", "runtime_options.TRAP", "OFF")).fingerprint()
    assert a != b


# --- the CICS conventions table (#4707): EIB fields and abends the ports rely on ---

CORPORA = Path(os.environ.get("GITGALAXY_MAINFRAME_CORPORA", ""))
EIB_WORD = re.compile(r"\bEIB[A-Z0-9]+\b", re.IGNORECASE)
# EIB names that are not fields a program reads: the EIB copybook's own, and EIBTASKN12 (a CBSA user name).
NOT_FIELDS = {
    "EIBLK",
    "EIBTASKN12",
    "EIBDATE",
    "EIBTIME",
}  # EIBDATE / EIBTIME: set by the harness, read by no burned program


def _burned_eib_fields():
    """{field: {corpus}} for the EIB names the COBOL of each burned estate names."""
    out: dict[str, set[str]] = {}
    for path in sorted(ESTATES):
        corpus = CORPORA / path.stem
        if not corpus.is_dir():
            continue
        for src in corpus.rglob("*"):
            if src.suffix.lower() in (".cbl", ".cob", ".cpy") and src.is_file():
                for word in set(EIB_WORD.findall(src.read_text(encoding="latin-1"))):
                    out.setdefault(word.upper(), set()).add(path.stem)
    return out


def test_every_convention_row_is_complete_and_links_a_register_entry():
    register = ROOT / "docs" / "language_status" / "register"
    for key, row in CICS_CONVENTIONS.items():
        assert all(row[k] for k in ("changes", "cobc", "det", "otherwise")), key
        assert row["register"], key  # #4707: every convention is stated by a register entry
        for rid in row["register"]:
            assert (register / f"{rid}.md").is_file(), (key, rid)


def test_eibtrnid_is_stated_by_its_register_entry():
    entry = (ROOT / "docs" / "language_status" / "register" / "X68.md").read_text(encoding="utf-8")
    assert CICS_CONVENTIONS["EIBTRNID"]["register"] == ["X68"]
    assert "EIBTRNID" in entry and "not validated" in entry.lower()


def test_the_register_lists_every_convention_row():
    text = (ROOT / "docs" / "language_status" / "register" / "C18.md").read_text(encoding="utf-8")
    assert not [row for row in conventions_rows() if row not in text]


def test_every_eib_field_a_burned_corpus_names_has_a_row():
    fields = _burned_eib_fields()
    if not fields:
        pytest.skip("no burned corpus checked out (GITGALAXY_MAINFRAME_CORPORA)")
    missing = {f: sorted(c) for f, c in fields.items() if f not in CICS_CONVENTIONS and f not in NOT_FIELDS}
    assert not missing


def test_a_rows_used_by_names_only_corpora_that_use_the_field():
    fields = _burned_eib_fields()
    if not fields:
        pytest.skip("no burned corpus checked out (GITGALAXY_MAINFRAME_CORPORA)")
    for key, row in CICS_CONVENTIONS.items():
        if key.startswith("EIB"):
            assert set(row["used_by"]) <= fields.get(key, set()), key


def _stated():
    return {k: r["default"] for k, r in RUNTIME_OPTION_TABLE.items() if r["policy"]}


def test_a_measurement_under_the_defaults_calibrates():
    assert calibration_problems(_stated()) == []


@pytest.mark.parametrize(("section", "key", "value"), REFUSED)
def test_a_measurement_under_a_refused_value_does_not_calibrate(section, key, value):
    under = _stated()
    under[f"{section}.{key}"] = value
    (hit,) = calibration_problems(under)
    assert f"{section}.{key}={value}" in hit


def test_a_measurement_under_a_declared_value_names_the_difference():
    under = _stated() | {"db2.ccsid.EBCDIC_CCSID": "285"}
    (hit,) = calibration_problems(under)
    assert "declare" in hit


@pytest.mark.parametrize("path", [k for k, r in RUNTIME_OPTION_TABLE.items() if r["policy"]])
def test_a_measurement_must_state_every_judged_option(path):
    under = _stated()
    del under[path]
    (hit,) = calibration_problems(under)
    assert hit.startswith(path)


def test_a_measurement_may_state_a_no_effect_option_and_must_know_its_keys():
    assert calibration_problems(_stated() | {"db2.bind.ISOLATION": "RR"}) == []
    assert "no row" in calibration_problems(_stated() | {"cics.region.NEW": "x"})[0]
    assert calibration_problems(None) and calibration_problems({})


# --- which burned estates exercise each judged option (#4707) ---

SQL_BLOCK = re.compile(r"EXEC\s+SQL(.*?)END-EXEC", re.DOTALL | re.IGNORECASE)
# option path -> (where, pattern): "text" over the source, "sql" over each EXEC SQL block
EXERCISE = {
    "le.runtime_options.TRAP": ("text", re.compile(r"\b(DIVIDE|COMPUTE)\b", re.IGNORECASE)),
    "le.runtime_options.ABTERMENC": ("text", re.compile(r"EXEC\s+CICS\s+ABEND\b|CEE3ABD", re.IGNORECASE)),
    "db2.format.DATE": ("text", re.compile(r"\bCURRENT\s+DATE\b|^\s+\w+\s+DATE\s*,?\s*$", re.IGNORECASE | re.MULTILINE)),
    "db2.format.TIME": ("text", re.compile(r"\bCURRENT\s+TIME\b|^\s+\w+\s+TIME\s*,?\s*$", re.IGNORECASE | re.MULTILINE)),
    "db2.format.DEC": ("sql", re.compile(r"\bDEC(IMAL)?\s*\(\s*(1[6-9]|2\d|3[01])\b", re.IGNORECASE)),
    "db2.format.DECPT": ("sql", re.compile(r"(?<![\w.'-])\d+\.\d+")),
    "db2.ccsid.EBCDIC_CCSID": ("text", re.compile(r"EXEC\s+SQL", re.IGNORECASE)),
    "db2.ccsid.SQLCCSID": ("text", re.compile(r"EXEC\s+SQL", re.IGNORECASE)),
    "cics.region.LOCALCCSID": ("text", re.compile(r"EXEC\s+CICS", re.IGNORECASE)),
}  # fmt: skip
STATED_BY_REGISTER = {"le.runtime_options.STORAGE"}  # register L3 names the programs; no pattern finds a missing VALUE


def _burned_exercisers():
    """{option: {corpus}} for the burned estates whose COBOL (comment lines dropped) holds each option's construct."""
    out: dict[str, set[str]] = {path: set() for path in EXERCISE}
    for path in sorted(ESTATES):
        corpus = CORPORA / path.stem
        if not corpus.is_dir():
            continue
        for src in corpus.rglob("*"):
            if src.suffix.lower() not in (".cbl", ".cob", ".cpy") or not src.is_file():
                continue
            lines = src.read_text(encoding="latin-1").splitlines()
            text = "\n".join(line for line in lines if not (len(line) > 6 and line[6] in "*/"))
            blocks = SQL_BLOCK.findall(text)
            for option, (where, pattern) in EXERCISE.items():
                if (where == "text" and pattern.search(text)) or (
                    where == "sql" and any(pattern.search(b) for b in blocks)
                ):
                    out[option].add(path.stem)
    return out


def test_every_judged_option_says_which_burned_estates_exercise_it():
    judged = {key for key, row in RUNTIME_OPTION_TABLE.items() if row["policy"]}
    assert set(RUNTIME_USED_BY) == judged
    assert judged == set(EXERCISE) | STATED_BY_REGISTER
    burned = {path.stem for path in ESTATES}
    for key, corpora in RUNTIME_USED_BY.items():
        assert set(corpora) <= burned, key


def test_used_by_is_exactly_the_burned_corpora_that_hold_the_construct():
    found = _burned_exercisers()
    if not CORPORA.is_dir() or not any(found.values()):
        pytest.skip("no burned corpus checked out (GITGALAXY_MAINFRAME_CORPORA)")
    for option, corpora in found.items():
        assert sorted(corpora) == sorted(RUNTIME_USED_BY[option]), option


def test_storage_used_by_matches_the_programs_register_l3_names():
    text = (ROOT / "docs" / "language_status" / "register" / "L3.md").read_text(encoding="utf-8")
    assert "CardDemo" in text and "CBSA" in text
    assert RUNTIME_USED_BY["le.runtime_options.STORAGE"] == [
        "aws-mainframe-modernization-carddemo",
        "cics-banking-sample-application-cbsa",
    ]


def test_the_register_lists_every_used_by_row():
    text = (ROOT / "docs" / "language_status" / "register" / "C18.md").read_text(encoding="utf-8")
    assert not [row for row in used_by_rows() if row not in text]


@pytest.mark.parametrize("key", ["DATE", "TIME", "DEC", "DECPT"])
def test_a_db2_format_row_honours_only_its_default_and_names_it(key):
    """The row's claim about the cases ("run in ISO / DEC(15) / with a period") is its default, the one value honoured."""
    row = RUNTIME_OPTION_TABLE[f"db2.format.{key}"]
    assert row["honoured"] == (row["default"],) and row["policy"] == "refuse"
    claim = row["reason"].split("; the Db2 cases run ", 1)[1]
    assert {"DATE": "ISO", "TIME": "ISO", "DEC": "DEC(15)", "DECPT": "a period"}[key] in claim
    assert row["default"] in {"ISO", "15", "."}


# --- source members and CICS translator options (#4707) ---


def test_the_register_lists_every_source_and_translator_row():
    text = (ROOT / "docs" / "language_status" / "register" / "C18.md").read_text(encoding="utf-8")
    assert not [row for row in translator_rows() if row not in text]
    assert not [key for key in RUNTIME_OPTION_TABLE if key.startswith("le.source.") and f"| `{key}` " not in text]


def test_the_le_option_source_members_have_rows():
    assert {"le.source.CEEOPTS", "le.source.CEEUOPT", "le.source.CEEDOPT"} <= set(RUNTIME_OPTION_TABLE)
    assert all(RUNTIME_OPTION_TABLE[k]["policy"] is None for k in RUNTIME_OPTION_TABLE if k.startswith("le.source."))


def test_translator_tokens_split_a_recorded_value():
    assert translator_tokens("CICS('SP,EDF') via the program's CBL card") == ["CICS", "SP", "EDF"]
    assert translator_tokens("CICS via the compile OPTFILE") == ["CICS"]
    assert translator_tokens(None) == []


@pytest.mark.parametrize("path", ESTATES, ids=lambda p: p.stem)
def test_every_translator_token_an_estate_records_has_a_row_and_none_is_refused(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    value = data["cics"]["translator"]["options"]["value"]
    tokens = translator_tokens(value)
    assert tokens and all(t in TRANSLATOR_OPTIONS for t in tokens), tokens
    hits = eo.effective_options({"program": "P"}, data).unhonoured_runtime()
    assert [h for h in hits if h["option"] == "cics.translator.options"] == []


@pytest.mark.parametrize(
    ("value", "token"), [("CICS,COBOL3", "COBOL3"), ("CICS,NEWOPT", "NEWOPT"), ("GRAPHIC", "GRAPHIC")]
)
def test_a_translator_token_the_harness_cannot_honour_is_refused_by_name(value, token):
    (hit,) = runtime_unhonoured({"cics": {"translator.options": value}})
    assert (hit["policy"], hit["declared"]) == ("refuse", token)
    assert hit["option"] == "cics.translator.options"


def test_the_translator_table_rows_are_complete():
    for key, row in TRANSLATOR_OPTIONS.items():
        assert row["policy"] in (None, "refuse") and row["reason"], key
        assert key == key.upper(), key


# --- the Db2 precompiler PARM, judged token by token (#4707) ---

PARM = "db2.precompile.PARM"


def _parm(value, sources=None):
    return [h for h in runtime_unhonoured({"db2": {"precompile.PARM": value}}, sources) if h["option"] == PARM]


def test_the_register_lists_every_precompiler_parm_row():
    text = (ROOT / "docs" / "language_status" / "register" / "C18.md").read_text(encoding="utf-8")
    assert not [row for row in precompile_rows() if row not in text]


def test_precompile_tokens_split_a_recorded_value():
    assert precompile_tokens("HOST(IBMCOB),XREF,SOURCE,FLAG(I),APOST") == [
        ("HOST", "IBMCOB"), ("XREF", None), ("SOURCE", None), ("FLAG", "I"), ("APOST", None)]  # fmt: skip
    assert precompile_tokens("date( iso ), dec(31) via the DSNHPC step") == [("DATE", "ISO"), ("DEC", "31")]
    assert precompile_tokens(None) == [] and precompile_tokens("") == []


def test_the_precompile_table_rows_are_complete():
    for key, row in PRECOMPILE_OPTIONS.items():
        assert row["policy"] in (None, "refuse") and row["reason"], key
        assert key == key.upper(), key
        if row["policy"]:
            assert isinstance(row["honoured"], tuple), key


@pytest.mark.parametrize("path", ESTATES, ids=lambda p: p.stem)
def test_every_precompiler_token_an_estate_records_has_a_row_and_none_is_refused(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    entry = ((data.get("db2") or {}).get("precompile") or {}).get("PARM")
    if entry is None:
        pytest.skip("this estate records no precompiler PARM")
    names = [n for n, _ in precompile_tokens(entry["value"])]
    assert names and all(n in PRECOMPILE_OPTIONS for n in names), names
    hits = eo.effective_options({"program": "P"}, data).unhonoured_runtime()
    assert [h for h in hits if h["option"] == PARM] == []


@pytest.mark.parametrize(
    "value",
    [
        "HOST(IBMCOB),XREF,SOURCE,FLAG(I),APOST",
        "DATE(ISO),TIME(ISO),DEC(15),DECPT(.),CCSID(1140)",
        "SQL(DB2),STDSQL(NO),NOXREF",
    ],
)
def test_a_precompiler_parm_at_the_honoured_defaults_is_clean(value):
    assert _parm(value) == []


@pytest.mark.parametrize(
    ("value", "token"),
    [
        ("XREF,NEWTOK", "NEWTOK"),
        ("DATE(USA)", "DATE(USA)"),
        ("TIME(EUR)", "TIME(EUR)"),
        ("DEC(31)", "DEC(31)"),
        ("DECPT(,)", "DECPT(,)"),
        ("CCSID(285)", "CCSID(285)"),
        ("DATE", "DATE"),
        ("HOST(PLI)", "HOST(PLI)"),
        ("QUOTESQL", "QUOTESQL"),
        ("STDSQL(YES)", "STDSQL(YES)"),
        ("GRAPHIC", "GRAPHIC"),
    ],
)
def test_a_precompiler_token_the_harness_cannot_honour_is_refused_by_name(value, token):
    (hit,) = _parm(value, {PARM: "f:3"})
    assert (hit["policy"], hit["declared"], hit["source"]) == ("refuse", token, "f:3")
    assert token in hit["note"]


def test_only_the_offending_tokens_of_a_parm_are_refused():
    assert [h["declared"] for h in _parm("HOST(IBMCOB),DATE(USA),XREF,DEC(31)")] == ["DATE(USA)", "DEC(31)"]


def test_a_precompiler_refusal_reaches_the_oracle_and_the_resolver(put_estate):
    case = put_estate("db2", "precompile.PARM", "HOST(IBMCOB),DATE(USA)")
    with pytest.raises(common.UnsupportedOption, match=re.escape("DATE(USA)")):
        common.compile_options(case, PLAIN)
    common.compile_options(put_estate("db2", "precompile.PARM", "HOST(IBMCOB),XREF"), PLAIN)


# --- the Db2 bind options, judged per value (#4707) ---

BIND = "db2.bind."


def _bind(key, value, sources=None):
    return [h for h in runtime_unhonoured({"db2": {f"bind.{key}": value}}, sources) if h["option"].startswith(BIND)]


def test_the_register_lists_every_bind_row():
    text = (ROOT / "docs" / "language_status" / "register" / "C18.md").read_text(encoding="utf-8")
    assert not [row for row in bind_rows() if row not in text]


def test_the_bind_table_rows_are_complete_and_stay_unjudged_in_the_runtime_table():
    for key, row in BIND_OPTIONS.items():
        assert row["reason"] and row["values"] and all(v == v.upper() for v in row["values"]), key
        assert RUNTIME_OPTION_TABLE[BIND + key]["policy"] is None, key


@pytest.mark.parametrize("path", ESTATES, ids=lambda p: p.stem)
def test_every_bind_value_an_estate_records_is_accepted(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    bind = (data.get("db2") or {}).get("bind") or {}
    if not bind:
        pytest.skip("this estate records no bind option")
    assert all(BIND + name in RUNTIME_OPTION_TABLE for name in bind)
    hits = eo.effective_options({"program": "P"}, data).unhonoured_runtime()
    assert [h for h in hits if h["option"].startswith(BIND)] == []


@pytest.mark.parametrize(
    ("key", "value"),
    [
        *[("ISOLATION", v) for v in ("CS", "UR", "RR", "RS", "cs", " ur ")],
        *[("CURRENTDATA", v) for v in ("YES", "NO", "no")],
        *[("DYNAMICRULES", v) for v in ("RUN", "BIND", "bind")],
        *[("VALIDATE", v) for v in ("RUN", "BIND", "run")],
        ("ACTION", "REPLACE"), ("ACTION", "ADD"), ("packages", "none"), ("packages", "COLL.PKG"),
    ],
)  # fmt: skip
def test_an_accepted_bind_value_is_clean(key, value):
    assert _bind(key, value) == []


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("ISOLATION", "XX"), ("ISOLATION", "NC"), ("ISOLATION", ""), ("CURRENTDATA", "MAYBE"),
        ("DYNAMICRULES", "DEFINEBIND"), ("DYNAMICRULES", "INVOKERUN"), ("VALIDATE", "NEVER"), ("VALIDATE", ""),
    ],
)  # fmt: skip
def test_a_bind_value_the_harness_cannot_accept_is_refused_by_name(key, value):
    (hit,) = _bind(key, value, {BIND + key: "f:9"})
    assert (hit["policy"], hit["declared"], hit["source"], hit["applied"]) == (
        "refuse",
        value.strip().upper(),
        "f:9",
        None,
    )
    assert BIND + key in hit["note"] and "#4707" in hit["note"]


def test_a_bind_refusal_reaches_the_oracle_and_the_resolver(put_estate):
    with pytest.raises(common.UnsupportedOption, match=re.escape("db2.bind.ISOLATION")):
        common.compile_options(put_estate("db2", "bind.ISOLATION", "XX"), PLAIN)
    common.compile_options(put_estate("db2", "bind.ISOLATION", "UR"), PLAIN)
    assert eo.effective_options(put_estate("db2", "bind.ISOLATION", "UR")).unhonoured_runtime() == []


# --- the Language Environment options, judged for syntax (#4707) ---

LE = "le.runtime_options."


def _le(key, value, sources=None):
    return runtime_unhonoured({"le": {f"runtime_options.{key}": value}}, sources)


def test_the_register_lists_every_le_row():
    text = (ROOT / "docs" / "language_status" / "register" / "C18.md").read_text(encoding="utf-8")
    assert not [row for row in le_rows() if row not in text]


def test_the_le_syntax_rows_cover_exactly_the_judged_runtime_options():
    assert {LE + key for key in LE_OPTIONS} == {
        key for key, row in RUNTIME_OPTION_TABLE.items() if key.startswith(LE) and row["policy"] is not None
    }
    assert all(row["grammar"] for row in LE_OPTIONS.values())


@pytest.mark.parametrize("path", ESTATES, ids=lambda p: p.stem)
def test_every_le_value_an_estate_records_is_well_formed_and_honoured(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    recorded = ((data.get("le") or {}).get("runtime_options")) or {}
    if not recorded:
        pytest.skip("this estate records no LE runtime option")
    hits = eo.effective_options({"program": "P"}, data).unhonoured_runtime()
    assert [h for h in hits if h["option"].startswith(LE)] == []


@pytest.mark.parametrize(
    ("key", "value"),
    [
        *[("TRAP", v) for v in ("ON", "ON,SPIE", "ON,NOSPIE", "on")],
        ("ABTERMENC", "abend"),
        ("STORAGE", "NONE,NONE,NONE,0K"),
    ],
)  # fmt: skip
def test_a_well_formed_default_le_value_is_clean(key, value):
    assert _le(key, value) == []


@pytest.mark.parametrize(
    ("key", "value", "declared"),
    [("STORAGE", "NONE", "NONE"), ("STORAGE", "none,none,none", "NONE,NONE,NONE"), ("STORAGE", "00,NONE,NONE,0K", "00,NONE,NONE,0K"), ("STORAGE", "NONE,NONE,NONE,4K", "NONE,NONE,NONE,4K"),
     ("STORAGE", "ff", "FF"), ("TRAP", "OFF", "OFF"), ("TRAP", "off,nospie", "OFF,NOSPIE"),
     ("ABTERMENC", "RETCODE", "RETCODE")],
)  # fmt: skip
def test_a_well_formed_value_keeps_its_policy(key, value, declared):
    (hit,) = _le(key, value)
    assert hit["declared"] == declared
    assert hit["policy"] == RUNTIME_OPTION_TABLE[LE + key]["policy"]
    assert "not Language Environment syntax" not in hit["note"]


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("STORAGE", "garbage"), ("STORAGE", "ZZ,NONE,NONE,0K"), ("STORAGE", "0,NONE,NONE,0K"), ("STORAGE", "NONE,NONE,NONE,K"),
        ("STORAGE", "NONE,NONE,NONE,0K,1"), ("STORAGE", "NONE,NONE,NONE,0KB"), ("STORAGE", ""), ("STORAGE", "NONE,NONE,NONE,-1K"),
        ("TRAP", "XX"), ("TRAP", "ON,FOO"), ("TRAP", ""), ("TRAP", "ON,SPIE,NOSPIE"), ("TRAP", "SPIE"),
        ("ABTERMENC", "FOO"), ("ABTERMENC", ""), ("ABTERMENC", "ABEND,RETCODE"),
    ],
)  # fmt: skip
def test_a_value_that_is_not_le_syntax_is_refused_by_name_once(key, value):
    (hit,) = _le(key, value, {LE + key: "f:3"})
    assert (hit["policy"], hit["applied"], hit["source"]) == ("refuse", None, "f:3")
    assert LE + key in hit["note"] and "not Language Environment syntax" in hit["note"] and "#4707" in hit["note"]
    assert runtime_effect(LE + key, value) == "refused"


def test_a_malformed_le_value_reaches_the_oracle(put_estate):
    with pytest.raises(common.UnsupportedOption, match=re.escape("le.runtime_options.STORAGE")):
        common.compile_options(put_estate("le", "runtime_options.STORAGE", "garbage"), PLAIN)
    common.compile_options(put_estate("le", "runtime_options.STORAGE", "NONE,NONE,NONE,0K"), PLAIN)


# --- the Db2 format and CCSID options, judged for syntax (#4707) ---

DB2 = "db2."


def _db2(key, value, sources=None):
    return runtime_unhonoured({"db2": {key: value}}, sources)


def test_the_register_lists_every_db2_syntax_row():
    text = (ROOT / "docs" / "language_status" / "register" / "C18.md").read_text(encoding="utf-8")
    assert not [row for row in db2_rows() if row not in text]


def test_the_db2_syntax_rows_cover_exactly_the_judged_format_and_ccsid_options():
    assert {DB2 + key for key in DB2_OPTIONS} == {
        key
        for key, row in RUNTIME_OPTION_TABLE.items()
        if key.startswith(("db2.format.", "db2.ccsid.")) and row["policy"] is not None
    }
    assert all(row["grammar"] for row in DB2_OPTIONS.values())


@pytest.mark.parametrize("path", ESTATES, ids=lambda p: p.stem)
def test_every_db2_format_and_ccsid_value_an_estate_records_is_well_formed(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    db2 = data.get("db2") or {}
    recorded = {f"{g}.{k}": v for g in ("format", "ccsid") for k, v in (db2.get(g) or {}).items()}
    if not recorded:
        pytest.skip("this estate records no Db2 format or CCSID option")
    hits = eo.effective_options({"program": "P"}, data).unhonoured_runtime()
    assert [h for h in hits if "not Db2 syntax" in h["note"]] == []


@pytest.mark.parametrize(
    ("key", "value"),
    [("format.DATE", "USA"), ("format.DATE", "local"), ("format.TIME", "JIS"), ("format.DEC", "31"), ("format.DEC", "31."),
     ("format.DECPT", ","), ("format.DECPT", "comma"), ("ccsid.SQLCCSID", "YES")],
)  # fmt: skip
def test_a_well_formed_non_default_db2_value_keeps_its_refusal(key, value):
    (hit,) = _db2(key, value)
    assert hit["policy"] == "refuse"
    assert "not Db2 syntax" not in hit["note"]


@pytest.mark.parametrize(("value", "declared"), [("285", "285"), ("00285", "285")])
def test_a_well_formed_ccsid_keeps_its_declaration(value, declared):
    (hit,) = _db2("ccsid.EBCDIC_CCSID", value)
    assert (hit["policy"], hit["declared"].lstrip("0")) == ("declare", declared)
    assert _db2("ccsid.EBCDIC_CCSID", "037") == []


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("format.DATE", "FOO"), ("format.DATE", ""), ("format.DATE", "ISO,USA"), ("format.TIME", "25"),
        ("format.DEC", "16"), ("format.DEC", "abc"), ("format.DEC", ""), ("format.DEC", "15,31"),
        ("format.DECPT", ";"), ("format.DECPT", ""), ("format.DECPT", ".."),
        ("ccsid.SQLCCSID", "MAYBE"), ("ccsid.SQLCCSID", ""), ("ccsid.SQLCCSID", "YES,NO"),
        ("ccsid.EBCDIC_CCSID", "abc"), ("ccsid.EBCDIC_CCSID", "123456"), ("ccsid.EBCDIC_CCSID", "0"), ("ccsid.EBCDIC_CCSID", "-37"),
        ("ccsid.EBCDIC_CCSID", ""),
    ],
)  # fmt: skip
def test_a_value_that_is_not_db2_syntax_is_refused_by_name_once(key, value):
    (hit,) = _db2(key, value, {DB2 + key: "f:3"})
    assert (hit["policy"], hit["applied"], hit["source"]) == ("refuse", None, "f:3")
    assert DB2 + key in hit["note"] and "not Db2 syntax" in hit["note"] and "#4707" in hit["note"]
    assert runtime_effect(DB2 + key, value) == "refused"


def test_a_malformed_db2_value_reaches_the_oracle(put_estate):
    with pytest.raises(common.UnsupportedOption, match=re.escape("db2.format.DATE")):
        common.compile_options(put_estate("db2", "format.DATE", "FOO"), PLAIN)
    with pytest.raises(common.UnsupportedOption, match=re.escape("db2.ccsid.EBCDIC_CCSID")):
        common.compile_options(put_estate("db2", "ccsid.EBCDIC_CCSID", "abc"), PLAIN)
    common.compile_options(put_estate("db2", "format.DATE", "ISO"), PLAIN)


# --- the CICS region and program-definition options, judged for syntax (#4707) ---

CICS = "cics."


def _cics(key, value, sources=None):
    return runtime_unhonoured({"cics": {key: value}}, sources)


def test_the_register_lists_every_cics_syntax_row():
    text = (ROOT / "docs" / "language_status" / "register" / "C18.md").read_text(encoding="utf-8")
    assert not [row for row in cics_rows() if row not in text]


def test_the_cics_syntax_rows_cover_exactly_the_region_and_program_definition_options_with_a_value_grammar():
    assert {CICS + key for key in CICS_OPTIONS} == {
        key for key in RUNTIME_OPTION_TABLE if key.startswith(("cics.region.", "cics.program_definition."))
    }
    assert all(row["grammar"] for row in CICS_OPTIONS.values())


@pytest.mark.parametrize("path", ESTATES, ids=lambda p: p.stem)
def test_every_cics_value_an_estate_records_is_well_formed(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    hits = eo.effective_options({"program": "P"}, data).unhonoured_runtime()
    assert [h for h in hits if "not CICS syntax" in h["note"]] == []


@pytest.mark.parametrize(
    ("key", "value"),
    [("region.LOCALCCSID", "037"), ("region.LOCALCCSID", "1140"), ("region.DB2CONN", "yes"), ("region.DB2CONN", "NO"),
     ("region.CICS_TS", "4.2"), ("region.CICS_TS", "5"), ("region.CICS_TS", "6.1.0"),
     ("program_definition.CONCURRENCY", "THREADSAFE"), ("program_definition.CONCURRENCY", "required"),
     ("program_definition.EXECKEY", "USER"), ("program_definition.EXECKEY", "cics")],
)  # fmt: skip
def test_a_well_formed_cics_value_is_not_refused_for_syntax(key, value):
    assert not [h for h in _cics(key, value) if "not CICS syntax" in h["note"]]


def test_a_well_formed_other_ccsid_keeps_its_declaration():
    (hit,) = _cics("region.LOCALCCSID", "285")
    assert (hit["policy"], hit["applied"]) == ("declare", "data in the case's data_encoding")


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("region.LOCALCCSID", "abc"), ("region.LOCALCCSID", "123456"), ("region.LOCALCCSID", "0"), ("region.LOCALCCSID", ""),
        ("region.DB2CONN", "MAYBE"), ("region.DB2CONN", ""), ("region.DB2CONN", "YES,NO"),
        ("region.CICS_TS", "v4"), ("region.CICS_TS", ""), ("region.CICS_TS", "4..2"), ("region.CICS_TS", "1.2.3.4"),
        ("program_definition.CONCURRENCY", "FAST"), ("program_definition.CONCURRENCY", ""),
        ("program_definition.EXECKEY", "SUPER"), ("program_definition.EXECKEY", ""),
    ],
)  # fmt: skip
def test_a_value_that_is_not_cics_syntax_is_refused_by_name_once(key, value):
    (hit,) = _cics(key, value, {CICS + key: "f:3"})
    assert (hit["policy"], hit["applied"], hit["source"]) == ("refuse", None, "f:3")
    assert CICS + key in hit["note"] and "not CICS syntax" in hit["note"] and "#4707" in hit["note"]
    assert runtime_effect(CICS + key, value) == "refused"


def test_a_malformed_cics_value_reaches_the_oracle(put_estate):
    with pytest.raises(common.UnsupportedOption, match=re.escape("cics.region.DB2CONN")):
        common.compile_options(put_estate("cics", "region.DB2CONN", "MAYBE"), PLAIN)
    common.compile_options(put_estate("cics", "region.DB2CONN", "YES"), PLAIN)


# --- the calibration hook against every recorded measurement (#4702 part 2) ---

RULES = ROOT / "tests" / "tools" / "cobolrt_rules.json"
CAPTURES = sorted((ROOT / "tests" / "cobol_mainframe" / "zos_captures").glob("*.json"))


def _calibrated_under():
    """(where, calibrated_under) of every recorded z/OS measurement that states one."""
    found = []
    if RULES.is_file():
        for rule in json.loads(RULES.read_text(encoding="utf-8")).get("rules", []):
            if rule.get("calibration") == "z/OS-measured":
                found.append((f"{RULES.name}:{rule.get('id')}", rule.get("calibrated_under")))
    for cap in CAPTURES:
        text = cap.read_text(encoding="utf-8")
        for rec in json.loads(text).get("records", []) if text.lstrip().startswith("{") else []:
            if "calibrated_under" in rec:
                found.append((f"{cap.name}:{rec.get('id')}", rec["calibrated_under"]))
    return found


def test_every_recorded_measurement_calibrates_under_the_current_table():
    """A row added to the table makes an old measurement that does not state it fail here, not silently transfer."""
    for where, under in _calibrated_under():
        assert calibration_problems(under) == [], where


def test_a_recorded_measurement_missing_a_judged_key_would_fail():
    judged = _stated()
    for path in judged:
        assert calibration_problems({k: v for k, v in judged.items() if k != path}), path
