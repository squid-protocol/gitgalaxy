"""#4704 slice 1: an estate's compile and runtime options are one input.

- the estate options files (tests/equivalence/estate_options/<corpus>.json) match the schema: every value carries
  provenance, unknown is "assumed", and a value found in a corpus is really on the line the file names;
- one resolver (gitgalaxy.core.estate_options.effective_options): installation defaults < the compile step's PARM <
  the case's compiler_options < the program's CBL / PROCESS cards (IBM's order);
- the oracle's cobc flags and the det port resolve the SAME effective options for every committed case;
- the evidence fingerprint carries the options (BLOCKING): changing what an estate compiles under makes its proofs
  stale, while a record from before the input existed stays current while no option cobc acts on changes.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import equivalence_common as common  # noqa: E402
import evidence as ev  # noqa: E402

from gitgalaxy.core import estate_options as eo  # noqa: E402

CASES = sorted((ROOT / "tests" / "equivalence").glob("*/case.json"))
FILES = sorted(eo.ESTATE_OPTIONS_DIR.glob("*.json"))
BURNED = {
    "aws-mainframe-modernization-carddemo", "cics-banking-sample-application-cbsa", "cics-genapp",
    "dbb-mortgage-application", "cics-async-api-credit-card-application-example", "zecs",
}  # fmt: skip


def _corpora() -> Path | None:
    env = os.environ.get("GITGALAXY_MAINFRAME_CORPORA")
    for c in (Path(env) if env else None, ROOT / ".mainframe_corpora"):
        if c and c.is_dir():
            return c
    return None


def _entry(value, source="assumed: IBM default", note="n"):
    return {"value": value, "source": source, "note": note}


def _parm(option, value=None, **kw):
    return {"option": option, "value": value, "source": "assumed: owner decision", "note": "t", **kw}


def _estate(parm=None, installation=None, programs=None):
    return {
        "format": eo.FORMAT, "estate": "t", "corpus": "t",
        "compiler": {"product": _entry("Enterprise COBOL"), "version": _entry("6.3"),
                     "installation_defaults": installation or {}},
        "parm": {"default": parm or [], "programs": programs or {}},
        "le": {}, "db2": {}, "cics": {},
    }  # fmt: skip


# ---- the files ---------------------------------------------------------------------------------------------------
def test_every_burned_estate_has_an_options_file():
    assert {p.stem for p in FILES} == BURNED


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_estate_file_matches_the_schema(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    assert eo.validate(data) == []
    assert data["estate"] == data["corpus"] == path.stem


def test_every_case_corpus_has_an_options_file():
    corpora = {json.loads(c.read_text(encoding="utf-8"))["corpus"] for c in CASES}
    assert corpora <= {p.stem for p in FILES}, (
        "a case's corpus has no estate options file (tests/equivalence/estate_options)"
    )


def test_the_template_is_valid():
    assert eo.validate(eo.TEMPLATE) == []


def test_schema_refuses_a_value_without_provenance():
    data = _estate()
    data["le"] = {"runtime_options": {"STORAGE": {"value": "NONE", "note": "x"}, "TRAP": _entry("ON", "guess")}}
    data["compiler"]["version"] = {"value": None, "source": "somewhere", "note": "n"}
    errs = eo.validate(data)
    assert any("le.runtime_options.STORAGE" in e for e in errs)  # no source
    assert any("le.runtime_options.TRAP" in e for e in errs)  # a source that is neither a file:line nor assumed
    assert any("compiler.version" in e for e in errs)
    assert eo.validate(
        {**_estate(), "parm": {"default": [_parm("TRUNC", "OPT", applied_value="STD")]}}
    )  # no applied_note


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_found_values_are_on_the_line_the_file_names(path):
    """A value found in a corpus names `<file>:<line>` and quotes what is there; read at the corpus pin."""
    corpora = _corpora()
    if corpora is None or not (corpora / path.stem).is_dir():
        pytest.skip("needs the corpus checkout (GITGALAXY_MAINFRAME_CORPORA)")
    ref = next(
        c["ref"]
        for c in json.loads((ROOT / "tests/cobol_mainframe/corpora.json").read_text())["corpora"]
        if c["name"] == path.stem
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    found = []

    def visit(o):
        if isinstance(o, dict):
            if "value" in o and "source" in o:
                if not str(o["source"]).startswith("assumed:"):
                    found.append(o)
            else:
                [visit(v) for v in o.values()]
        elif isinstance(o, list):
            [visit(v) for v in o]

    visit({k: data[k] for k in eo.SECTIONS})
    if not found:
        pytest.skip("every value of this estate is assumed (its corpus ships no build inputs)")
    bad = []
    for e in found:
        rel, _, line = e["source"].rpartition(":")
        got = subprocess.run(["git", "-C", str(corpora / path.stem), "show", f"{ref}:{rel}"], capture_output=True)
        if got.returncode:
            pytest.skip(f"the corpus checkout has no pin {ref[:8]}")
        lines = got.stdout.decode("utf-8", "replace").splitlines()
        if int(line) > len(lines) or e["quote"] not in lines[int(line) - 1]:
            bad.append(f"{e['source']}: {e['quote']!r} not on that line")
    assert not bad


# ---- the resolver ------------------------------------------------------------------------------------------------
CARD_TRUNC_BIN = "       CBL TRUNC(BIN)\n       IDENTIFICATION DIVISION.\n"
PLAIN = "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. P.\n"


def test_precedence_installation_then_parm_then_case_then_cards():
    est = _estate(installation={"TRUNC": _entry("BIN")}, parm=[_parm("NUMPROC", "PFD")])
    r = eo.effective_options({"program": "P"}, est)
    assert r.values(PLAIN)["TRUNC"] == "BIN"  # the shop's installation default beats IBM's STD
    assert r.values(PLAIN)["NUMPROC"] == "PFD"  # the PARM
    assert r.values(PLAIN)["ARITH"] == "COMPAT"  # nothing names it: IBM's default
    r = eo.effective_options({"program": "P", "compiler_options": ["NUMPROC(NOPFD)", "TRUNC(OPT)"]}, est)
    assert (r.values(PLAIN)["NUMPROC"], r.values(PLAIN)["TRUNC"]) == (
        "NOPFD",
        "OPT",
    )  # the case beats the estate's PARM
    assert r.values("       CBL TRUNC(STD)\n" + PLAIN)["TRUNC"] == "STD"  # the program's card beats everything


def test_a_program_with_its_own_parm_replaces_the_default():
    est = _estate(parm=[_parm("NUMPROC", "PFD")], programs={"q": [_parm("TRUNC", "BIN")]})
    assert eo.effective_options({"program": "P"}, est).values(PLAIN)["NUMPROC"] == "PFD"
    other = eo.effective_options({"program": "Q"}, est).values(PLAIN)
    assert other["TRUNC"] == "BIN" and other["NUMPROC"] == "NOPFD"


def test_a_no_form_cancels_and_the_card_can_cancel_a_parm_option():
    est = _estate(parm=[_parm("NUMPROC", "PFD")])
    assert (
        eo.effective_options({"program": "P"}, est).values("       CBL NONUMPROC\n" + PLAIN).get("NUMPROC") == "NOPFD"
    )


def test_a_declared_difference_is_applied_and_listed():
    est = _estate(parm=[_parm("TRUNC", "OPT", applied_value="STD", applied_note="no cobc equivalent")])
    r = eo.effective_options({"program": "P"}, est)
    assert r.values(PLAIN)["TRUNC"] == "STD"
    assert [(d["option"], d["declared"], d["applied"]) for d in r.deviations(PLAIN)] == [("TRUNC", "OPT", "STD")]
    # a card that names the option itself leaves no difference
    assert r.deviations("       CBL TRUNC(STD)\n" + PLAIN) == []


def test_the_case_compiler_block_overrides_the_estate_compiler():
    est = _estate()
    assert eo.effective_options({"program": "P"}, est).compiler["version"] == "6.3"
    case = {"program": "P", "compiler": {"product": "Enterprise COBOL", "version": "6.1"}}
    assert eo.effective_options(case, est).compiler["version"] == "6.1"
    assert common.compiler_version({"corpus": "dbb-mortgage-application", "program": "X"}) == (6, 1)  # from the estate


def test_mortgage_mpmt_still_resolves_mig_from_its_case_compiler_block():
    case = json.loads((ROOT / "tests/equivalence/mortgage-mpmt/case.json").read_text())
    assert common.numproc(case, "       CBL NUMPROC(MIG)\n" + PLAIN) == "NOPFD"
    assert eo.effective_options(case).compiler == {"product": "Enterprise COBOL", "version": "6.1"}


# ---- the oracle and the det port resolve the same options -----------------------------------------------------------
def test_oracle_and_det_port_resolve_the_same_options_for_every_case():
    pytest.importorskip("tree_sitter_language_pack")
    from gitgalaxy.tools.cobol_to_java.det import program as P  # noqa: PLC0415

    corpora = _corpora()
    if corpora is None:
        pytest.skip("needs the corpus checkouts (GITGALAXY_MAINFRAME_CORPORA)")
    checked = 0
    for c in CASES:
        case = json.loads(c.read_text(encoding="utf-8"))
        src = corpora / case["corpus"] / case["program_source"]
        if not src.is_file():
            continue
        text = common.read_program(case, src)[0]
        r = eo.effective_options(case)
        eff = r.values(text)
        flags = common.compile_options(case, text)[1]
        assert ("-fbinary-truncate" in flags) == (eff["TRUNC"].upper() == "STD"), c.parent.name
        assert common.numproc(case, text) == ("NOPFD" if eff["NUMPROC"].upper() == "MIG" else eff["NUMPROC"].upper())
        assert P.trunc_std(src, r.layers) == (eff["TRUNC"].upper() == "STD"), c.parent.name
        assert P.numproc_pfd(src, r.layers) == (eff["NUMPROC"].upper() == "PFD"), c.parent.name
        checked += 1
    assert checked, "no case's program was readable"


# ---- the evidence fingerprint -------------------------------------------------------------------------------------
def test_options_is_a_blocking_evidence_input():
    assert "options" in ev.INPUTS and "options" in ev.BLOCKING


def _now(case_key="cbsa-inqacc"):
    t = ev.target(case_key)
    return t, ev.compute_inputs(t)


def test_a_record_with_options_goes_stale_when_an_option_changes(monkeypatch):
    t, now = _now()
    stored = copy.deepcopy(now)
    assert ev.changed(stored, now) == []
    real = eo.load_estate

    def changed_estate(corpus, directory=None):
        data = copy.deepcopy(real(corpus, directory))
        for e in data["parm"]["default"]:
            if e["option"] == "RENT":
                e["option"], e["value"] = "NORENT", None  # a non-semantic option still changes the proof's inputs
        return data

    monkeypatch.setattr(eo, "load_estate", changed_estate)
    after = ev.compute_inputs(t)
    assert ev.changed(stored, after) == ["options"]
    assert "options" in ev.BLOCKING


def test_a_record_from_before_the_input_stays_current_while_no_cobc_option_changes(monkeypatch):
    t, now = _now()
    legacy = {k: v for k, v in copy.deepcopy(now).items() if k != "options"}
    assert ev.changed(legacy, now) == []  # the estate file changes no option the harness acts on
    real = eo.load_estate

    def with_trunc_bin(corpus, directory=None):
        data = copy.deepcopy(real(corpus, directory))
        for e in data["parm"]["default"]:
            if e["option"] == "TRUNC":
                e["applied_value"] = "BIN"  # the proof would now run under TRUNC(BIN)
        return data

    monkeypatch.setattr(eo, "load_estate", with_trunc_bin)
    assert ev.changed(legacy, ev.compute_inputs(t)) == ["options"]


def test_the_options_input_is_stored_in_new_records_without_provenance():
    t, now = _now("cbsa-updcust")
    got = now["options"]
    assert got["estate"] == "cics-banking-sample-application-cbsa"
    assert "TRUNC(OPT)" in got["effective"]["declared_parm"] and "TRUNC(STD)" in got["effective"]["parm"]
    assert "source" not in json.dumps(got["effective"])  # a changed note is not a changed option
