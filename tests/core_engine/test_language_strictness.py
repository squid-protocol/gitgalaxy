# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#2716 / #2718: the language-strictness table and the corpus-generated fidelity table
that replaced SignalProcessor._get_tier's three-bucket lookup.

Two properties the old mechanism lacked and these tests pin:
  * COMPLETENESS -- every language the registry defines has a strictness row (or resolves
    to one through LANGUAGE_FAMILY), so nothing can fall through to a default again.
  * BOUNDEDNESS  -- Irc is 0..4 and Ot 1.0..1.4 from the column count; an unknown or
    no-runtime language gets NO language-level term; every fidelity coefficient is in
    (0, 1] and is 1.0 for a signal the corpus never planted.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from gitgalaxy.metrics.signal_processor import SignalProcessor
from gitgalaxy.standards import analysis_lens as al
from gitgalaxy.standards.fidelity_table import FIDELITY_PROVENANCE, FIDELITY_SIGNALS, FIDELITY_TABLE
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS = Path(os.environ.get("KEYWORD_ROSETTA_PATH", REPO_ROOT.parent / "keyword-rosetta"))


# ---------------------------------------------------------------- strictness table
def test_every_registry_language_has_a_strictness_row():
    missing = [lang for lang in LANGUAGE_DEFINITIONS if al.resolve_language_family(lang) not in al.LANGUAGE_STRICTNESS]
    assert not missing, f"add rows to analysis_lens.LANGUAGE_STRICTNESS (or LANGUAGE_FAMILY) for: {missing}"


def test_strictness_rows_are_well_formed():
    for lang, row in al.LANGUAGE_STRICTNESS.items():
        if row is None:
            continue
        assert len(row) == len(al.STRICTNESS_COLUMNS), lang
        assert all(isinstance(flag, bool) for flag in row), lang


def test_family_members_resolve_to_a_defined_parent():
    for member, parent in al.LANGUAGE_FAMILY.items():
        assert parent in al.LANGUAGE_STRICTNESS, (member, parent)
        assert parent not in al.LANGUAGE_FAMILY, f"{member} -> {parent} chains; families are one level"


@pytest.mark.parametrize(
    ("lang", "expected"),
    [
        ("rust", (0, 1.0)),  # all four columns True
        ("haskell", (0, 1.0)),  # used to fall through to tier 3
        ("go", (1, 1.1)),  # unenforced errors
        ("python", (2, 1.2)),
        ("embedded_python", (2, 1.2)),  # #2653: reads python's row by family
        ("shell", (3, 1.3)),
        ("yacc", (4, 1.4)),
        ("yaml", (0, 1.0)),  # no runtime -> no language-level term
        ("no-such-language", (0, 1.0)),  # unknown -> none, not the harshest bucket
    ],
)
def test_strictness_constants(lang, expected):
    irc, ot = al.strictness_constants(lang)
    assert (irc, round(ot, 6)) == expected


def test_irc_and_ot_are_bounded_by_the_column_count():
    n = len(al.STRICTNESS_COLUMNS)
    for lang in al.LANGUAGE_STRICTNESS:
        irc, ot = al.strictness_constants(lang)
        assert 0 <= irc <= n * al.STRICTNESS_IRC_PER_GAP
        assert 1.0 <= ot <= 1.0 + n * al.STRICTNESS_OT_PER_GAP + 1e-9


def test_no_runtime_languages_carry_no_term():
    for lang in ("yaml", "json", "xml", "css", "html", "markdown", "csv", "proto"):
        assert al.LANGUAGE_STRICTNESS[lang] is None, lang
        assert al.strictness_constants(lang) == (0, 1.0), lang


# ---------------------------------------------------------------- fidelity table
def test_fidelity_coefficients_are_in_unit_interval():
    for lang, row in FIDELITY_TABLE.items():
        for sig, fc in row.items():
            assert 0.0 < fc <= 1.0, (lang, sig, fc)
            assert sig in FIDELITY_SIGNALS, (lang, sig)


def test_engine_reads_only_signals_the_corpus_plants():
    p = SignalProcessor()
    assert set(p.FIDELITY_SIGNALS) <= set(FIDELITY_SIGNALS), (
        "SignalProcessor scales a signal the corpus never plants -- it would always read 1.0"
    )


def test_language_constants_resolve_families_and_unknowns():
    p = SignalProcessor()
    # strictness follows the family; fidelity follows the dialect's OWN measured rule set
    irc_e, ot_e, fid_e = p._language_constants("embedded_python")
    irc_p, ot_p, _fid_p = p._language_constants("python")
    assert (irc_e, ot_e) == (irc_p, ot_p)
    assert fid_e == {sig: float(FIDELITY_TABLE["embedded_python"].get(sig, 1.0)) for sig in p.FIDELITY_SIGNALS}
    irc, ot, fid = p._language_constants("no-such-language")
    assert (irc, ot) == (0, 1.0)
    assert fid == dict.fromkeys(p.FIDELITY_SIGNALS, 1.0)


def test_fidelity_provenance_names_the_corpus():
    assert FIDELITY_PROVENANCE["corpus"] == "keyword-rosetta"
    assert int(FIDELITY_PROVENANCE["languages"]) >= 40


@pytest.mark.skipif(
    not (CORPUS / "docs" / "bias_data.json").exists(),
    reason="keyword-rosetta corpus not checked out as a sibling (set KEYWORD_ROSETTA_PATH)",
)
def test_committed_fidelity_table_is_fresh_against_the_corpus():
    """The table is generated data; a stale copy is the two-tables-that-disagree failure
    #2653 found in FIDELITY_TIERS all over again. Same bar as the audit runners: the
    tool exits 2 (not 0) when it could not actually check."""
    res = subprocess.run(  # noqa: S603 -- fixed args
        [sys.executable, str(REPO_ROOT / "tests" / "tools" / "fidelity_table.py"), "--check", "--corpus", str(CORPUS)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr
