# Global Regex and ReDoS Policy

Whenever you are writing, modifying, or reviewing Regular Expressions (Regex) in this codebase, you **MUST** adhere to the project's structural-extraction accuracy and ReDoS immunity standards.

1. **ReDoS Immunity & Boundary Correctness**: You must read and follow the 12 engine rules defined in `gitgalaxy/standards/how_to_add_a_language.md`. 
2. **Hardening Process**: You must follow the 5-stage pipeline checklist and avoid the recurring bug classes outlined in `tests/extraction/how_to_harden_extraction.md`.
3. **Use the Tooling**: Always verify regex empirically against the real compiled regex using `tests/extraction/tools/verify_candidates.py` and run the scaling checks. Do not guess whether a payload matches or scales.
4. **Skills**: If you are deepening or fixing a language's structural-extraction accuracy (e.g. `func_start`, `args`), you must activate and follow the `harden-language-extraction` skill.

# Core Engine Modification CI Checklist

When you are preparing to push a fix or open a PR that touches GitGalaxy's core parsing logic (`language_standards.py`, `detector.py`, `prism.py`), you **MUST** ensure the CI validation gauntlet is handled.

1. **Invoke the ci-push-checklist skill**: You must activate and follow the `.agents/skills/ci-push-checklist/SKILL.md` before pushing to ensure all Golden Masters, Tri-Comparison, and Tree-Sitter baselines are accurately regenerated and validated.

# GitHub Issue and Pull Request Management

Whenever you file issues or create pull requests, you **MUST** adhere to the following documentation and linking standards:

1. **Detailed PR Bodies**: When using `gh pr create`, always provide a detailed, well-formatted PR body describing the problem, the root cause, and the fix. Do not leave the body brief or empty.
2. **Auto-closing Issues**: Always include issue-closing keywords (e.g., `Resolves #123`, `Fixes #456`) in the **initial** PR body during creation. Do not rely on `gh pr edit` to add them later, as the PR may auto-merge before you do so, leaving the issues open.
3. **Issue Labels**: When using `gh issue create`, always apply appropriate labels using the `--label` flag (e.g., `--label "bug"`, `--label "upstream"`).

2. **Cross-Repo PRs**: This repo is the hub of a multi-repo constellation (`docs/ecosystem.md` is the canonical map — repos, skills, workflows, merge ordering). Any PR participating in a cross-repo workflow MUST include a "Cross-repo" section in its body naming the companion PR/issue in the other repo(s), which side merges first and why, and what must be re-run after the other side lands. Example: squid-protocol/gitgalaxy#2611 ↔ squid-protocol/keyword-rosetta#4.

# GitGalaxy Agent Workflow Guardrails

**1. Primary Source of Truth**
`CLAUDE.md` is the primary, continuously updated source of truth for the repository's architecture, CI procedures, and testing philosophy. Read `CLAUDE.md` first for deep project context before relying on other summary files.

**2. Git Worktrees**
This repository heavily utilizes `git worktree` for active feature development (e.g., `/nvme-data/projects/gitgalaxy-worktrees/`). If a branch fails to checkout with a `fatal: already used by worktree` error, or if files seem "missing" from `main`, always check `git worktree list` first.

**3. CI/CD Triage (Pipeline Manager)**
For CI/CD triage and Dependabot management, do not attempt to guess pipeline failures manually. Invoke the `pipeline-manager` subagent located at `.claude/agents/pipeline-manager.md`. Use this exact subagent when investigating failing GitHub Actions runs.

**4. Zero-Tolerance Lossy Read Policy**
GitGalaxy enforces a zero-tolerance policy against lossy reads (enforced by `tests/test_source_reads.py`). Never use `errors="ignore"` or `errors="replace"` in `.decode()` calls or file reads. Always use strict decoding wrapped in a `try...except UnicodeDecodeError` block to safely probe bytes.

# Formatting Pipeline

Before pushing code, you MUST always add `ruff format <files>` to your pre-commit pipeline to avoid failing the Ruff Audit CI checks. The strict zero-tolerance baseline will reject any code that `ruff` would reformat.

# Mainframe Internationalization & Precision Logging

**1. The "ID_START" Universal Unicode Rule**
When evaluating identifiers and boundaries in mainframe systems (COBOL, HLASM, PL/I), DO NOT hardcode restrictive EBCDIC definitions (e.g., just `ÆØÅÄÖÜÑ§£...`). We made a sweeping architectural upgrade by migrating our core `NATIONAL` character-class injection in `identifiers.py` to use `ID_START` (which natively includes all Unicode `Lo` categories like Kanji, Katakana, Hiragana, etc.). 
* **The Lesson:** This single injection unlocked native full-estate parsing for Japanese mainframe deployments (Fujitsu/opensourcecobol4j), eliminating truncation on Japanese `PROGRAM-ID`s and data names. Always leverage native `ID_START` rather than piecemeal ASCII/EBCDIC hacks when resolving legacy dialects.

**2. The IBM Underscore (`_`) Paradigm Shift**
By adopting `ID_START`, GitGalaxy gained implicit, native support for the underscore (`_`) character across all COBOL identifiers. While standard COBOL grammar does not officially support underscores, IBM Enterprise COBOL and HLASM allow it heavily. 
* **The Lesson:** Prior to this fix, variables like `COMPANY_PREFIX` were silently truncated to `COMPANY`, corrupting dataset bindings. Golden Crucible diffs proved that embracing `ID_START` correctly extracts thousands of previously-corrupted variables. If a dialect rule fails on a legacy repository, always verify if it's missing trailing underscores or lowercase letters that IBM compilers tolerate.

