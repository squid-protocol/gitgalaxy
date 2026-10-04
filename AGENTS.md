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

# Third-Party Material (comparing other translators)

When working with other people's code, tools, papers or artifacts (IBM, Devin, SENTINEL, Lightyear, AWS, etc.), you **MUST** follow `docs/research/third-party-material-policy.md`:
1. **Flag first:** stop and ask before copying third-party code, using unlicensed material, quoting at length, or shipping a vendor-inspired feature commercially.
2. **Borrow ideas, not code:** implement techniques yourself and record where each idea came from. Never commit third-party code without explicit maintainer approval for that specific case.
3. **Unlicensed sources:** run them locally from pinned commits, never commit them, and quote briefly with attribution.
4. **Scanning others' code:** scan only what we may lawfully see; check product terms for benchmark or reverse-engineering clauses before publishing comparisons; publish measurements, not reconstructions; disclose security findings privately first.

# Agent Tooling & Native File Operations Guardrails

You **MUST** prioritize native API tools for file and text manipulation. 
1. **File Editing**: NEVER use bash commands like `cat << 'EOF' > ...`, `echo "..." >> file`, or `sed` to edit files. These commands trigger strict terminal permission guardrails and interrupt the user. Instead, ALWAYS use your native tools (`write_to_file` and `replace_file_content`).
2. **File Searching**: Avoid using bash `grep` or `find` when native tools like `grep_search` are available and more appropriate for the task.

# Documentation SEO & Frontmatter

Whenever you create a new markdown file in the `docs/` directory (or edit one that lacks frontmatter), you **MUST** include a YAML frontmatter block at the very top of the file containing a unique, 150-160 character `description`. 
Example:
---
description: "A concise summary of the page's specific content for SEO..."
---
Never rely on the global `mkdocs.yml` site description for individual pages.

# CI Pipeline & Skill Documentation Rule

You **MUST** consult and follow existing skill documentation before executing CI scripts, fixing tests, or regenerating golden masters.
1. **Always read the manual:** Before running complex pipeline scripts like `update_golden_master.py`, `tri_comparison_chart.py`, or `ground_truth_ledger.py`, you must `cat` and read the relevant guides inside `.claude/skills/` (specifically `.claude/skills/ci-push-checklist/SKILL.md`).
2. **Never guess CI environments:** The CI environment uses strict dependency gating (e.g., zero-dependency vs. full-precision ML modes) and pinned versions of testing corpora (e.g., `tests/_crucible_pin.py`). Do not guess environment flags or assume your local python dependencies mirror the CI. Reference the documentation to execute the exact commands required for full replication.
