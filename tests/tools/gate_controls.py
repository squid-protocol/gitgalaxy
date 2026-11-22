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
    trigger: str = "pr"  # when it runs: pr | main (push) | nightly | release
    job: str = ""  # the job inside the workflow when the workflow holds several gates ("" = the workflow itself)


HERE = "tests/tools/test_gate_controls.py"

GATES = (
    # Required
    Gate(
        "ruff-audit (lint)",
        "ruff-audit.yml",
        "new lint findings beyond the baseline",
        "tests/tools/test_content_keyed_baseline.py::test_ci_check_end_to_end",
        required=True,
        open_gap="only reads gitgalaxy/: tests/ is never linted",
    ),
    Gate(
        "ruff-audit (real ruff)",
        "ruff-audit.yml",
        "real ruff flags a planted unused import",
        f"{HERE}::test_ruff_audit_fails_on_a_planted_finding_with_real_ruff",
        required=True,
    ),
    Gate(
        "ruff-audit (format)",
        "ruff-audit.yml",
        "any file not ruff-format clean",
        f"{HERE}::test_ruff_audit_fails_on_format_alone",
        required=True,
    ),
    Gate(
        "mypy-audit",
        "mypy-audit.yml",
        "new type errors beyond the baseline",
        f"{HERE}::test_mypy_audit_fails_on_a_new_error",
        required=True,
        open_gap="only reads gitgalaxy/",
    ),
    Gate(
        "full-suite",
        "smoke-test.yml",
        "the pytest suite",
        "tests/tools/test_full_suite_control.py::test_a_part_that_did_not_pass_fails_the_check_whatever_the_skip_proofs_say",
        required=True,
        open_gap="a plan can narrow or skip the suite on a PR, and it still reads green",
    ),
    Gate(
        "det",
        "det-sweep.yml",
        "a det port stops proving, or a baselined case now proves",
        "tests/cobol_mainframe/test_proof_sweep.py::test_unexpected_failures_and_stale_entries_are_named",
        required=True,
        open_gap="the job's shell exits 0 when the plan finds nothing to prove",
    ),
    Gate(
        "ground-truth",
        "mainframe-ground-truth.yml",
        "a new mismatch against the answer keys",
        "tests/cobol_mainframe/test_ground_truth_ledger.py::test_new_mismatch_fails",
        required=True,
        open_gap="aggregator only string-matched; pending corpora aren't gated",
    ),
    Gate(
        "ci-gate",
        "shepherd-event.yml",
        "any real red check on the head",
        "tests/tools/test_shepherd_gh.py::test_a_red_path_filtered_check_turns_auto_merge_off_and_fails_the_gate",
        open_gap="sees only checks that ran: a path-filtered workflow that never starts is invisible",
    ),
    # Pre-gate
    Gate(
        "Vault Sentinel",
        "gitgalaxy.yml",
        "hardcoded secrets and denylisted files",
        "tests/security_auditing/test_vault_sentinel_control.py::test_the_real_detector_fails_ci_on_a_planted_secret",
        open_gap="tests/ is allowlisted; a scan error is printed, not failed",
    ),
    Gate(
        "X-Ray Inspector",
        "gitgalaxy.yml",
        "obfuscated payloads and denylisted files",
        "tests/security_auditing/test_xray_control.py::test_the_real_detector_fails_ci_on_a_dense_payload",
        open_gap="a plain XOR loop is not flagged, only repeated indexed XORs (#7187)",
    ),
    Gate(
        "Import Policy Gate",
        "gitgalaxy.yml",
        "banned packages and risky behaviour",
        "tests/security_auditing/test_import_policy_gate.py::test_behavioral_threat_evaluation",
        open_gap="no directory-mode end-to-end test; unknown packages pass by default",
    ),
    # Small audits
    Gate(
        "dead-key-audit",
        "small-audits.yml",
        "a dict key read but never written",
        "tests/test_dead_key_audit.py::test_ci_check_fails_on_a_key_not_in_the_baseline",
    ),
    Gate(
        "signal-contract-audit",
        "small-audits.yml",
        "a contract finding, or a stale rendered sheet",
        "tests/test_signal_contract_sheet.py::test_ci_mode_fails_on_a_stale_render",
        open_gap="baseline regressions have only a green test",
    ),
    Gate(
        "doc-refs-audit",
        "small-audits.yml",
        "a hand-written doc naming a path, link, flag, skill or module the repo no longer has",
        "tests/test_doc_refs_audit.py::test_ci_fails_only_beyond_the_baseline_and_reports_fixed_keys",
        open_gap="checks that a name exists, not that the prose around it is still true",
    ),
    Gate("ast-accuracy-audit", "small-audits.yml", "function extraction regressing against Python ast"),
    Gate("golden-master-guard", "small-audits.yml", "flags golden fixture changes", notice=True),
    # Scanners
    Gate(
        "CodeQL",
        "codeql.yml",
        "new CodeQL errors and warnings on a PR",
        "tests/tools/test_codeql_new_alerts.py::test_report_only_never_fails_and_enforce_does",
        open_gap="path-filtered: a PR changing Python only under tests/ never runs it",
    ),
    Gate("Muninn", "muninn.yml", "static security findings", open_gap="an external action; a sparse checkout on PRs"),
    # Notices
    Gate("answer-key-guard", "answer-key-guard.yml", "answer key changes without a re-census", notice=True),
    # Jobs inside a listed workflow that hold a PR on their own
    Gate(
        "suite-time",
        "smoke-test.yml",
        "a test over 15 s, or a baselined test past 2.5x its recorded time (#5166)",
        "tests/tools/test_time_ratchet.py::test_an_unmarked_test_fails_only_over_fifteen_seconds",
        job="suite-time",
        open_gap="a test gated on GITGALAXY_NIGHTLY is first timed on the scheduled run",
    ),
    Gate(
        "det-mutation",
        "det-sweep.yml",
        "a det-port mutant that survives and is not in the survivors ledger",
        job="detmut",
    ),
    Gate("db2", "det-sweep.yml", "a Db2 det port that stops proving against the real database", job="db2"),
    # Off the PR path: main, nightly and release checks that can fail
    Gate(
        "archetype-validation",
        "archetype-validation.yml",
        "archetype labels moving unseen after a push to main (#4100)",
        trigger="main",
        job="archetype-validation",
    ),
    Gate(
        "os-smoke-grid",
        "os-smoke-grid.yml",
        "an OS- or Python-version-sensitive break: package install, CLI entry points, syntax floor (#5130)",
        trigger="main",
        job="smoke-test",
    ),
    Gate(
        "full-suite-matrix",
        "full-suite-gate.yml",
        "any test failing on an OS x Python leg the PR run does not cover",
        trigger="nightly",
        job="full-suite-matrix",
    ),
    Gate(
        "evidence-refresh",
        "evidence-refresh.yml",
        "a det port or evidence record gone stale or no longer proving, found by the nightly re-proof (#4048)",
        trigger="nightly",
    ),
    Gate(
        "referee-panel",
        "referee-panel.yml",
        "the COBOL and CICS referee tools disagreeing with the engine (#4438)",
        trigger="nightly",
        job="panel",
    ),
    Gate(
        "publish-evidence-current",
        "publish.yml",
        "a release tag cut while the evidence report is stale",
        trigger="release",
        job="evidence-report-current",
    ),
    Gate(
        "assess-from-pypi",
        "publish-assess-check.yml",
        "the published package failing a clean install and `gitgalaxy assess` (#4726)",
        trigger="release",
        job="assess-from-pypi",
    ),
    # On a PR, no failure proof yet (#7155)
    Gate(
        "golden-crucible",
        "golden-crucible.yml",
        "structural drift over the pinned language-crucible corpus",
        job="crucible-audit",
    ),
    Gate(
        "call-graph-accuracy-audit",
        "call-graph-accuracy-audit.yml",
        "calls_out_to precision/recall dropping more than 0.5pp against tree-sitter call nodes (#3332)",
    ),
    Gate(
        "cics-crucible",
        "cics-crucible.yml",
        "a CICS crucible cell that passed and now fails, against tests/cics_crucible/baseline.json (#3989)",
    ),
    Gate(
        "crucible-path-independence",
        "crucible-path-independence.yml",
        "scan results that differ when the corpus is scanned from two parent paths (#4248)",
    ),
    Gate(
        "detection-accuracy-audit",
        "detection-accuracy-audit.yml",
        "language-detection accuracy dropping against its baseline (#3117)",
    ),
    Gate(
        "doom-rosetta",
        "doom-rosetta.yml",
        "any drift in the pinned DOOM ports against tests/golden_doom_rosetta, and call-graph regressions (#5619)",
    ),
    Gate(
        "equivalence-e2e",
        "equivalence-e2e.yml",
        "a mainframe test that needs the GnuCOBOL oracle, JDK 17 and Maven failing (#5954)",
    ),
    Gate(
        "estate-crucible",
        "estate-crucible.yml",
        "a horror or fact-channel check that passed against the estate key and now fails (#4317)",
    ),
    Gate(
        "fact-crosscheck",
        "fact-crosscheck.yml",
        "engine and det translator disagreeing on a COBOL fact the ledger does not list (#4273)",
    ),
    Gate(
        "generated-docs",
        "generated-docs.yml",
        "a generated aggregate page that no longer renders from its committed sources (#5057)",
    ),
    Gate(
        "graph-accuracy-audit",
        "graph-accuracy-audit.yml",
        "import-graph or call-resolution accuracy dropping against committed baselines",
    ),
    Gate(
        "java-compile",
        "java-compile.yml",
        "generated Spring Boot projects that fail to compile under a supported target config (#3613)",
    ),
    Gate(
        "ports-compile",
        "ports-compile.yml",
        "a committed port that no longer compiles against the generator at HEAD (#4423)",
    ),
    Gate(
        "rosetta-audit",
        "rosetta-audit.yml",
        "a keyword-rosetta language that passed against engine main and fails with this PR (#2557)",
    ),
    Gate(
        "tree-sitter-accuracy-audit",
        "tree-sitter-accuracy-audit.yml",
        "structural-signature recall or precision dropping against tree-sitter, per language",
    ),
    Gate(
        "tri-comparison-audit",
        "tri-comparison-audit.yml",
        "GitGalaxy's validated precision dropping against tree-sitter and ctags",
    ),
    Gate(
        "unicode-gauntlet",
        "unicode-gauntlet.yml",
        "a re-encoded or renamed variant whose scanned facts differ from its ASCII twin (#3812)",
    ),
)

# PR-triggered workflows that hold nothing: with the reason.
NOT_GATES = {
    "dependabot-relock.yml": "refreshes dependency locks on Dependabot PRs",
    "solver-check.yml": "informational: branch_solver verdicts in the job summary, never fails; the det sweep gates (#4175)",
}

# Workflows that never trigger on a PR and hold nothing: with the reason (every workflow is a Gate or listed in one of these).
NOT_GATES.update(
    {
        "blocker-baseline.yml": "ad hoc survey run; the nightly baseline is evidence-refresh's",
        "cache-prune.yml": "deletes stale Actions caches",
        "call-resolution-history.yml": "appends a measurement row after a push to main",
        "deploy-docs.yml": "publishes the docs site",
        "doc-drift.yml": "files documentation issues from the doc-refs backlog, never fails a change",
        "engine-coverage-map.yml": "records which test covers which module, for the suite plan",
        "evidence-pages.yml": "renders evidence pages from committed records",
        "flake-history.yml": "refreshes the learned-flake cache",
        "graph-comparison-history.yml": "appends measurements to the generated branch",
        "java-base-generation.yml": "seeds a cache for java-compile",
        "main-watch.yml": "reports another workflow's red run on main as an issue (its own control is #7155 part 2)",
        "mirror-tag-sync.yml": "manual: aligns the mirrors' tags",
        "post-merge.yml": "dispatches other workflows on main",
        "release-crucible-archive.yml": "archives release scan output",
        "shepherd-reconcile.yml": "the shepherd's own pass, which posts ci-gate (owner-only, #6694)",
        "tree-sitter-accuracy-history.yml": "appends measurements to the generated branch",
        "tri-comparison-history.yml": "appends measurements to the generated branch",
    }
)

# The ratchet: this only goes down. Raising it means a gate lost its proof, or one was added without one.
MAX_UNPROVEN = 28


def unproven() -> list[Gate]:
    return [g for g in GATES if not g.proof and not g.notice]


if __name__ == "__main__":
    print(f"{len(GATES)} checks, {len(unproven())} without a failure proof:")
    for g in unproven():
        print(f"  {g.name} ({g.workflow}){' [required]' if g.required else ''}: {g.open_gap or g.claims}")
