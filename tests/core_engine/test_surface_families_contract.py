# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""The `SURFACE_FAMILIES` contract (gitgalaxy#2994), pinned in one module.

The measurement-tier reform's Tier 1 is a declarative {family: [signal, ...]}
map over SIGNAL_SCHEMA (analysis_lens.py section 7b). This is the arbiter of
that map, not the comment above its definition:

    1. Every SIGNAL_SCHEMA name appears in EXACTLY ONE family XOR in
       SURFACE_FAMILY_EXEMPT -- never both, never neither.
    2. Every family member and every exempt entry is a real SIGNAL_SCHEMA
       name (no typos silently doing nothing).
    3. Every SURFACE_FAMILY_EXEMPT entry carries a non-empty one-line reason.
    4. No fam_*/pct_fam_*/pct_vec_*/rel_* column name (the DB columns
       record_keeper.py generates from SURFACE_FAMILIES/RISK_SCHEMA)
       collides with an existing, hardcoded file_data column.

A failure here means the family map (or the exempt ledger) drifted out of
sync with SIGNAL_SCHEMA -- fix the map, not this test.
"""

from __future__ import annotations

import re

from gitgalaxy.recorders.record_keeper import RecordKeeper
from gitgalaxy.standards.analysis_lens import RECORDING_SCHEMAS, SURFACE_FAMILIES, SURFACE_FAMILY_EXEMPT

SIGNAL_SCHEMA = RECORDING_SCHEMAS["SIGNAL_SCHEMA"]
RISK_SCHEMA = RECORDING_SCHEMAS["RISK_SCHEMA"]


def _all_family_members() -> list[str]:
    members: list[str] = []
    for family_members in SURFACE_FAMILIES.values():
        members.extend(family_members)
    return members


def test_surface_families_is_not_empty():
    """Sanity guard: a typo'd import/empty dict would make every other test
    in this module vacuously pass."""
    assert len(SURFACE_FAMILIES) > 0
    assert len(SURFACE_FAMILY_EXEMPT) > 0


def test_no_signal_belongs_to_more_than_one_family():
    """A signal double-counted into two families would silently inflate both
    family sums whenever that signal fires."""
    members = _all_family_members()
    seen: set[str] = set()
    dupes: set[str] = set()
    for m in members:
        if m in seen:
            dupes.add(m)
        seen.add(m)
    assert not dupes, f"signal(s) counted in more than one family: {sorted(dupes)}"


def test_no_signal_is_both_a_family_member_and_exempt():
    """The XOR half of the contract: a name cannot simultaneously be counted
    (in a family) and declared deliberately uncounted (exempt)."""
    overlap = set(_all_family_members()) & set(SURFACE_FAMILY_EXEMPT.keys())
    assert not overlap, f"signal(s) both in a family and exempt: {sorted(overlap)}"


def test_every_family_member_is_a_real_signal_schema_name():
    """A typo'd family member would silently sum to 0 forever -- catch it here
    instead of finding out from a suspiciously-zero family in production."""
    unknown = set(_all_family_members()) - set(SIGNAL_SCHEMA)
    assert not unknown, f"family member(s) not in SIGNAL_SCHEMA: {sorted(unknown)}"


def test_every_exempt_entry_is_a_real_signal_schema_name():
    unknown = set(SURFACE_FAMILY_EXEMPT.keys()) - set(SIGNAL_SCHEMA)
    assert not unknown, f"exempt entr(y/ies) not in SIGNAL_SCHEMA: {sorted(unknown)}"


def test_every_signal_schema_name_is_covered_exactly_once():
    """The full XOR contract in one assertion: every one of SIGNAL_SCHEMA's
    95 names is in a family or exempt, never neither."""
    covered = set(_all_family_members()) | set(SURFACE_FAMILY_EXEMPT.keys())
    missing = set(SIGNAL_SCHEMA) - covered
    assert not missing, f"SIGNAL_SCHEMA name(s) neither in a family nor exempt: {sorted(missing)}"


def test_every_exempt_entry_has_a_nonempty_reason():
    for name, reason in SURFACE_FAMILY_EXEMPT.items():
        assert isinstance(reason, str) and reason.strip(), f"{name!r} has no one-line exemption reason"


def test_family_names_are_lowercase_identifiers():
    """Family names become fam_<name>/pct_fam_<name> SQL column suffixes --
    they must be safe, boring identifiers, not display strings."""
    ident = re.compile(r"^[a-z][a-z0-9_]*$")
    for family in SURFACE_FAMILIES:
        assert ident.match(family), f"family name {family!r} is not a safe lowercase identifier"


def test_new_tier_columns_do_not_collide_with_existing_file_data_columns():
    """The hard constraint from the plan: no fam_*/pct_fam_*/pct_vec_*/rel_*
    column collides with a column record_keeper.py already emits (the fixed
    hardcoded file_data columns, the risk_* columns, or the SHORT_KEY_MAP-
    derived hit columns)."""
    rk = RecordKeeper()

    new_cols = set()
    for family in SURFACE_FAMILIES:
        new_cols.add(f"fam_{family}")
        new_cols.add(f"pct_fam_{family}")
    for slug in RISK_SCHEMA:
        new_cols.add(f"pct_vec_{slug.replace('-', '_')}")
    new_cols.add("rel_guard_balance")
    new_cols.add("rel_alloc_cleanup")

    # The fixed, hardcoded file_data columns (everything in the CREATE TABLE
    # statement that isn't dynamically generated from RISK_SCHEMA/
    # SIGNAL_SCHEMA/SURFACE_FAMILIES). Kept as a literal, mirroring the
    # #2904 EXTERNAL_ENTRY_POINT_LANGUAGES pattern: widening it is a
    # deliberate edit reviewed against this contract, not a side effect of
    # an unrelated record_keeper.py change.
    fixed_columns = {
        "id",
        "repo_name",
        "commit_date",
        "commit_hash",
        "file_name",
        "file_path",
        "parent_entity",
        "language",
        "directory_group",
        "total_loc",
        "coding_loc",
        "doc_loc",
        "structural_mass",
        "cog_raw",
        "ownership_entropy",
        "silo_risk",
        "raw_churn_freq",
        "popularity",
        "import_count",
        "internal_dependency_links",
        "pagerank_score",
        "normalized_blast_radius",
        "betweenness_score",
        "closeness_score",
        "producer_ratio",
        "ecosystem_role",
        "control_flow_ratio",
        "function_count",
        "class_count",
        "func_complexity_vector",
        "avg_func_loc",
        "avg_func_complexity",
        "max_func_complexity",
        "avg_func_args",
        "func_complexity_gini",
        "func_internal_density",
        "dependency_density",
        "encapsulation_ratio",
        "author",
        "ai_threat_class",
        "ai_threat_confidence",
        "func_z_max",
        "func_z_mean",
        "func_z_median",
        "pct_z_above_5",
        "pct_z_above_15",
        "file_archetype",
        "file_fingerprint",
        "ecosystem_baseline",
        "repo_z_score",
        "ai_threat_score",
        "is_malware",
        "has_credentials",
        "binary_anomaly",
        "obfuscation_flag",
        "token_mass",
        "financial_read_cost",
        "agentic_isolation_risk",
        "requires_hitl",
        "appsec_god_mode",
        "hallucination_zone",
        "silent_mutation_risk",
        "raw_arch_api",
        "raw_state_unreferenced",
    }
    risk_columns = {f"risk_{r.replace('-', '_')}" for r in rk.RISK_SCHEMA}
    hit_columns = {rk.SHORT_KEY_MAP.get(h, h) for h in rk.SIGNAL_SCHEMA}

    existing = fixed_columns | risk_columns | hit_columns
    collisions = new_cols & existing
    assert not collisions, f"new tier column(s) collide with an existing file_data column: {sorted(collisions)}"


def test_family_count_and_member_totals_match_the_reconciled_design():
    """Pins the reconciliation performed for gitgalaxy#2994: 22 families
    covering 63 of SIGNAL_SCHEMA's 95 names, the remaining 32 exempt. A
    change to either number is a deliberate edit to the taxonomy, not an
    accident -- update this pin alongside the map."""
    assert len(SIGNAL_SCHEMA) == 95, f"SIGNAL_SCHEMA grew/shrank ({len(SIGNAL_SCHEMA)}); re-reconcile the tier map"
    assert len(SURFACE_FAMILIES) == 22
    assert len(_all_family_members()) == 63
    assert len(SURFACE_FAMILY_EXEMPT) == 32
