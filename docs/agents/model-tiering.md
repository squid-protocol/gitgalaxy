---
description: "Model tiering for this repo: which model to use for the main session, which are pinned for subagents (Haiku vs Sonnet), and the default for new subagents."
---
# Model tiering (token budget)

Moved verbatim from CLAUDE.md (kept out of the always-loaded context). CLAUDE.md links here.

This repo pins models per-role instead of running everything on one tier, so the expensive
model is only spent where the extra judgment actually pays for itself.

**Main session (manual `/model` switch)**
- **Sonnet (default)**: everyday coding, debugging, code review, regex/rule work.
- **Opus**: switch in manually for architecture-level planning, high-ambiguity design
  decisions, or multi-system tradeoffs (e.g. redesigning the core pipeline stage boundaries,
  not writing one more detector rule) — the extra compute is worth it there.

**Subagents (pinned in each agent's frontmatter)**
- **Haiku**: mechanical, read-heavy, well-defined output shape, no judgment calls beyond
  "escalate if ambiguous" — `issue-triage`, `pipeline-manager`. Both are written to hand
  anything ambiguous (duplicate calls, label taxonomy, destructive actions) back to the main
  conversation rather than guess, which is what makes Haiku safe here.
- **Sonnet**: anything requiring nuanced judgment, synthesis across multiple sources, or
  writing/reviewing code on the subagent's own authority.

When adding a new subagent, default it to Haiku unless the task demonstrably needs more
judgment than "read input, produce well-formed output, escalate ambiguity" — don't pin Sonnet
out of caution alone.
