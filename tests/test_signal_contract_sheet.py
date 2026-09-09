"""
The contract sheet's own invariants (gitgalaxy/standards/signal_contracts.py).

signal_contract_audit.py checks the sheet against the registry and the authoring
doc; these tests pin the lifecycle rules the sheet promises about itself, so a
row cannot be flipped to `declared` or `stated` without the evidence the state
names (#2897: the declared state).
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tests"))

import signal_contract_audit as audit  # noqa: E402

from gitgalaxy.standards import signal_contracts as sc  # noqa: E402

STATES = ("draft", "declared", "stated")
# The AI/ML pack rules are `_IMPORT_WRAPPER` regexes: they fire on the import
# statement, never on a use, so their unit is the import contract's.
IMPORT_ANCHORED = (
    "llm_orchestrator",
    "llm_vector_store",
    "ml_traditional",
    "dl_frameworks",
    "hardware_bridge",
    "cryptography",
)


def _rows(status: str) -> list[sc.SignalContract]:
    return [c for c in sc.CONTRACTS.values() if c.status == status]


# ==============================================================================
# TEST 1: THE LIFECYCLE HAS EXACTLY THREE STATES
# ==============================================================================
def test_every_row_has_a_known_status():
    bad = {c.name: c.status for c in sc.CONTRACTS.values() if c.status not in STATES}
    assert bad == {}


# ==============================================================================
# TEST 2: A DECLARED OR STATED ROW POINTS AT EVIDENCE THAT EXISTS
# ==============================================================================
@pytest.mark.parametrize("status", ["declared", "stated"])
def test_non_draft_rows_have_an_existing_doc(status):
    missing = [c.name for c in _rows(status) if not c.doc or not (REPO_ROOT / c.doc).is_file()]
    assert missing == [], f"{status} rows without an evidence doc on disk: {missing}"


def test_non_draft_rows_name_their_issue():
    missing = [c.name for c in sc.CONTRACTS.values() if c.status != "draft" and not c.issue]
    assert missing == []


# ==============================================================================
# TEST 3: DECLARED IS THE STATE FOR UNPLANTED, UNGATED ROWS ONLY
# ==============================================================================
def test_declared_rows_are_unplanted():
    """A planted row has a corpus cell to hold equal -- it needs the family audit, not a batch sentence."""
    planted = [c.name for c in _rows("declared") if c.planted]
    assert planted == []


def test_encapsulation_is_carved_out_of_the_batch():
    """The #2897 batch carved encapsulation out as `draft` because it governs
    _calc_api_exposure and a sentence without the rule audit would have been the
    false `stated`. The family audit landed with #2766 (46 languages, rules edited
    in the same PR, docs/encapsulation_rule_contract.md) -- the carve-out's exit
    condition -- so the row is `stated` now, and this test pins that the promotion
    came WITH its doc rather than by sentence alone."""
    assert sc.CONTRACTS["encapsulation"].status == "stated"
    assert sc.CONTRACTS["encapsulation"].issue == 2766
    assert sc.CONTRACTS["encapsulation"].doc == "docs/encapsulation_rule_contract.md"


# ==============================================================================
# TEST 4: THE SENTENCE IS WHAT THE AUTHORING PROMPT SAYS (the audit's containment check,
#         pinned here for declared rows so a later prompt edit cannot silently drift)
# ==============================================================================
def test_declared_sentences_are_contained_in_the_schema_comment():
    comments = audit.schema_comments()
    drift = []
    for c in _rows("declared"):
        if c.name in sc.EXTENSION_SIGNALS:
            continue  # documented as pack bullets, not `# key:` lines; allowlisted by the audit
        comment = comments.get(c.name)
        if comment is None or audit._normalise(c.contract) not in audit._normalise(comment):
            drift.append(c.name)
    assert drift == []


# ==============================================================================
# TEST 5: KIND FOLLOWS THE RULE'S ANCHOR
# ==============================================================================
def test_import_anchored_pack_rows_are_declarations():
    assert {n: sc.CONTRACTS[n].kind for n in IMPORT_ANCHORED} == dict.fromkeys(IMPORT_ANCHORED, "declaration")
    assert {sc.CONTRACTS[n].unit for n in IMPORT_ANCHORED} == {"declarations"}


def test_structural_boundaries_is_the_only_tally():
    """A tally is never a denominator (count contract corollary 5); #2770 is the one formula that divides by it."""
    assert [c.name for c in sc.CONTRACTS.values() if c.kind == "tally"] == ["structural_boundaries"]


# ==============================================================================
# TEST 6: THE BATCH DID NOT REGRESS THE AUDIT
# ==============================================================================
def test_audit_has_no_findings_outside_its_baseline():
    baseline = audit.load_baseline()
    new = sorted(audit._key(f) for f in audit.run_audit() if audit._key(f) not in baseline)
    assert new == []
