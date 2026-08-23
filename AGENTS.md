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
