"""#7065: no key field may be silently ignored by the estate-crucible scorer.

A key states a fact; the scorer must either score it or report it `unscored` with a reason
(tests/tools/estate_crucible.py). Both paths name the field as a string literal in the scorer,
so a key field whose name appears nowhere in the scorer source is one the scorer drops without a
trace. The walk reads the checkout at the pin and skips cleanly when there is none.
"""

import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
sys.path.insert(0, str(TESTS))
import _estate_crucible_pin as pin  # noqa: E402
import estate_crucible as ec  # noqa: E402

# Descriptive fields the scorer never compares by design (the key's own bookkeeping).
BOOKKEEPING = {"horror", "era", "era_evidence", "generated_from", "note", "notes", "source", "quote", "citation"}


def field_names(entry: dict) -> set[str]:
    """Every channel name of a member entry and every field name of the rows under it."""
    names: set[str] = set()

    def walk(obj: object) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                names.add(k)
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    for channel, value in entry.items():
        names.add(channel)
        # Only rows (lists of dicts) carry field names; scalar-keyed maps hold data, not fields.
        if isinstance(value, list):
            walk(value)
    return names


def unaccounted(names: set[str], source: str) -> list[str]:
    return sorted(n for n in names - BOOKKEEPING if f'"{n}"' not in source and f"'{n}'" not in source)


def test_the_walk_finds_a_field_the_scorer_does_not_name():
    entry = {"jcl_steps": [{"name": "S1", "zz_new_field": 1}]}
    assert unaccounted(field_names(entry), '"jcl_steps" "name"') == ["zz_new_field"]


def test_the_walk_ignores_bookkeeping_and_named_fields():
    entry = {"jcl_steps": [{"name": "S1", "horror": "H-0001"}]}
    assert unaccounted(field_names(entry), '"jcl_steps" "name"') == []


def test_the_not_compared_table_names_each_field_once():
    assert len(set(ec.KEY_FIELDS_NOT_COMPARED)) == len(ec.KEY_FIELDS_NOT_COMPARED)


def test_every_key_field_is_named_in_the_scorer():
    path = ec.crucible_path(None)
    if not (path / "key" / "manifest.json").is_file():
        pytest.skip(f"no estate-crucible checkout at {path} (set {pin.PATH_ENV})")
    msg = pin.pin_mismatch(path)
    if msg:
        pytest.skip(msg)
    _manifest, members = ec.load_key(path)
    source = Path(ec.__file__).read_text(encoding="utf-8")
    missing: dict[str, list[str]] = {}
    for member, entry in members.items():
        for name in unaccounted(field_names(entry), source):
            missing.setdefault(name, []).append(member)
    assert not missing, {k: v[:3] for k, v in missing.items()}


def test_the_six_jcl_fields_are_no_longer_listed_as_uncompared():
    listed = set(ec.KEY_FIELDS_NOT_COMPARED)
    for field in [
        ("jcl_steps", "job"),
        ("jcl_dds", "job"),
        ("jcl_dds", "symbolic"),
        ("jcl_dds", "added"),
        ("jcl_utility_cards", "utility"),
        ("jcl_utility_cards", "every"),
    ]:
        assert field not in listed
