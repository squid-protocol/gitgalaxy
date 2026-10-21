"""#4270 acceptance 3: every modelled EXEC CICS command has a recorded line of evidence -- a register entry (its
`reached:` states the proof level), a cics-crucible case, or a named unit-proof test that exercises it -- so a
command cannot be modelled with nothing on record. The refusal side is test_cics_refusals_registered_4270.py."""

from __future__ import annotations

import json
from pathlib import Path

from gitgalaxy.standards.cics.commands import COMMANDS

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "docs" / "language_status" / "register"
STATUS = ROOT / "docs" / "language_status" / "cics_spec_status.json"

# Modelled commands with no register entry and no crucible case in the committed status file: the unit-proof test
# that exercises each. The list only shrinks (a command gaining a register entry or a case leaves it).
UNIT_PROOF = {
    "STARTBR": "tests/cics_crucible/test_file_fault_conditions.py",
    "ENDBR": "tests/cics_crucible/test_file_fault_conditions.py",
    "WRITE": "tests/cics_crucible/test_update_token_runtimes_5078.py",
    "WRITEQ TD": "tests/cics_crucible/test_td_queue_5079.py",
    "ENQ": "tests/cics_crucible/test_enq_fault_5089.py",
    "DEQ": "tests/cics_crucible/test_enq_fault_5089.py",
    "DELAY": "tests/cics_crucible/test_cics_runtimes.py",
    "ASKTIME": "tests/cics_crucible/test_cics_runtimes.py",
}


def _modelled():
    return {k: c for k, c in COMMANDS.items() if c.status == "modelled"}


def _crucible_cases():
    return json.loads(STATUS.read_text(encoding="utf-8")).get("crucible", {})


def test_every_register_entry_a_modelled_command_names_exists():
    unknown = sorted(
        f"{k}: {c.register}"
        for k, c in _modelled().items()
        if c.register and not (REGISTER / f"{c.register}.md").exists()
    )
    assert unknown == []


def test_every_modelled_command_has_evidence():
    cases = _crucible_cases()
    bare = sorted(k for k, c in _modelled().items() if not c.register and not cases.get(k))
    assert [k for k in bare if k not in UNIT_PROOF] == []


def test_each_unit_proof_names_a_real_test_that_issues_the_command():
    cases = _crucible_cases()
    modelled = _modelled()
    for key, rel in UNIT_PROOF.items():
        assert key in modelled, f"{key} is no longer a modelled command: drop it from UNIT_PROOF"
        path = ROOT / rel
        assert path.is_file(), f"{key}: {rel} does not exist"
        assert key in path.read_text(encoding="utf-8"), f"{key} is not exercised in {rel}"
        assert not (modelled[key].register or cases.get(key)), (
            f"{key} now has a register entry or case: drop it from UNIT_PROOF"
        )
