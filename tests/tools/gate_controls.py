#!/usr/bin/env python3
"""Every check that can hold a PR, and the test that proves it can fail (#7155).

A green gate means something only if it can go red. CodeQL read "No new alerts" on every PR while its analysis held no
results (#7153), and nothing noticed, because no test ever asked it to fail. Each gate below names its negative control:
a test that feeds it bad input and asserts failure. `proof=""` says plainly that none exists yet. test_gate_controls.py
fails when a PR workflow is missing here, when a named test is gone, or when the unproven count rises.

A proof covers the gate's logic, not the workflow around it: the job's shell, its skip paths and its reach are the
weekly control PR's to test. `notice` marks a check that cannot fail by design, so it holds nothing and needs no proof.
Stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Gate:
    name: str
    workflow: str
    claims: str
    proof: str = ""  # "path::test_name"; empty = no proof yet
    required: bool = False  # named in REQUIRED_CHECKS
    notice: bool = False  # reports only, never fails
    open_gap: str = ""  # what it can miss even when proven


HERE = "tests/tools/test_gate_controls.py"

GATES = (
    # Required
    Gate("ruff-audit (lint)", "ruff-audit.yml", "new lint findings beyond the baseline",
         "tests/tools/test_content_keyed_baseline.py::test_ci_check_end_to_end", required=True,
         open_gap="only reads gitgalaxy/: tests/ is never linted"),
    Gate("ruff-audit (real ruff)", "ruff-audit.yml", "real ruff flags a planted unused import",
         f"{HERE}::test_ruff_audit_fails_on_a_planted_finding_with_real_ruff", required=True),
    Gate("ruff-audit (format)", "ruff-audit.yml", "any file not ruff-format clean",
         f"{HERE}::test_ruff_audit_fails_on_format_alone", required=True),
    Gate("mypy-audit", "mypy-audit.yml", "new type errors beyond the baseline",
         f"{HERE}::test_mypy_audit_fails_on_a_new_error", required=True, open_gap="only reads gitgalaxy/"),
    Gate("full-suite", "smoke-test.yml", "the pytest suite", required=True,
         open_gap="aggregator shell untested; a plan can narrow or skip the suite"),
    Gate("det", "det-sweep.yml", "a det port stops proving, or a baselined case now proves",
         "tests/cobol_mainframe/test_proof_sweep.py::test_unexpected_failures_and_stale_entries_are_named", required=True,
         open_gap="the job's shell exits 0 when the plan finds nothing to prove"),
    Gate("ground-truth", "mainframe-ground-truth.yml", "a new mismatch against the answer keys",
         "tests/cobol_mainframe/test_ground_truth_ledger.py::test_new_mismatch_fails", required=True,
         open_gap="aggregator only string-matched; pending corpora aren't gated"),
    Gate("ci-gate", "shepherd-event.yml", "any real red check on the head",
         "tests/tools/test_shepherd_gh.py::test_a_red_path_filtered_check_turns_auto_merge_off_and_fails_the_gate",
         open_gap="sees only checks that ran: a path-filtered workflow that never starts is invisible"),
    # Pre-gate
    Gate("Vault Sentinel", "gitgalaxy.yml", "hardcoded secrets and denylisted files",
         "tests/security_auditing/test_vault_sentinel.py::test_sentinel_content_breach",
         open_gap="the proof mocks the detector; tests/ is allowlisted"),
    Gate("X-Ray Inspector", "gitgalaxy.yml", "obfuscated payloads and denylisted files",
         "tests/security_auditing/test_binary_anomaly_detector.py::test_main_anomaly_detected",
         open_gap="the proof mocks the detector"),
    Gate("Supply Chain Firewall", "gitgalaxy.yml", "banned packages and risky behaviour",
         "tests/security_auditing/test_supply_chain_firewall.py::test_behavioral_threat_evaluation",
         open_gap="no directory-mode end-to-end test; unknown packages pass by default"),
    # Small audits
    Gate("dead-key-audit", "small-audits.yml", "a dict key read but never written",
         "tests/test_dead_key_audit.py::test_ci_check_fails_on_a_key_not_in_the_baseline"),
    Gate("signal-contract-audit", "small-audits.yml", "a contract finding, or a stale rendered sheet",
         "tests/test_signal_contract_sheet.py::test_ci_mode_fails_on_a_stale_render",
         open_gap="baseline regressions have only a green test"),
    Gate("ast-accuracy-audit", "small-audits.yml", "function extraction regressing against Python ast"),
    Gate("golden-master-guard", "small-audits.yml", "flags golden fixture changes", notice=True),
    # Scanners
    Gate("CodeQL", "codeql.yml", "new CodeQL results on a PR",
         open_gap="report-only: --enforce is not wired, so a finding can't fail the job"),
    Gate("Muninn", "muninn.yml", "static security findings", open_gap="an external action; a sparse checkout on PRs"),
    # Notices
    Gate("answer-key-guard", "answer-key-guard.yml", "answer key changes without a re-census", notice=True),
    # On a PR, not audited yet (#7155)
    Gate("golden-crucible", "golden-crucible.yml", "structural drift over the pinned corpus"),
    Gate("call-graph-accuracy-audit", "call-graph-accuracy-audit.yml", "not audited yet"),
    Gate("cics-crucible", "cics-crucible.yml", "not audited yet"),
    Gate("crucible-path-independence", "crucible-path-independence.yml", "not audited yet"),
    Gate("detection-accuracy-audit", "detection-accuracy-audit.yml", "not audited yet"),
    Gate("doom-rosetta", "doom-rosetta.yml", "not audited yet"),
    Gate("equivalence-e2e", "equivalence-e2e.yml", "not audited yet"),
    Gate("estate-crucible", "estate-crucible.yml", "not audited yet"),
    Gate("fact-crosscheck", "fact-crosscheck.yml", "not audited yet"),
    Gate("generated-docs", "generated-docs.yml", "not audited yet"),
    Gate("graph-accuracy-audit", "graph-accuracy-audit.yml", "not audited yet"),
    Gate("java-compile", "java-compile.yml", "not audited yet"),
    Gate("ports-compile", "ports-compile.yml", "not audited yet"),
    Gate("rosetta-audit", "rosetta-audit.yml", "not audited yet"),
    Gate("tree-sitter-accuracy-audit", "tree-sitter-accuracy-audit.yml", "not audited yet"),
    Gate("tri-comparison-audit", "tri-comparison-audit.yml", "not audited yet"),
    Gate("unicode-gauntlet", "unicode-gauntlet.yml", "not audited yet"),
)

# PR-triggered workflows that hold nothing: with the reason.
NOT_GATES = {"dependabot-relock.yml": "refreshes dependency locks on Dependabot PRs"}

# The ratchet: this only goes down. Raising it means a gate lost its proof, or one was added without one.
MAX_UNPROVEN = 21


def unproven() -> list[Gate]:
    return [g for g in GATES if not g.proof and not g.notice]


if __name__ == "__main__":
    print(f"{len(GATES)} checks, {len(unproven())} without a failure proof:")
    for g in unproven():
        print(f"  {g.name} ({g.workflow}){' [required]' if g.required else ''}: {g.open_gap or g.claims}")
