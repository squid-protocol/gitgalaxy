---
description: "Instructions for automated CI monitoring and self-healing"
globs: "*"
---
# CI Monitoring and Self-Healing Directive

**CRITICAL INSTRUCTION: Never push code and forget about it.**

Whenever you push code to a branch, you MUST automatically monitor the GitHub Actions CI pipeline to ensure it passes. Do not rely on the user to tell you if the CI failed. 

**Steps to follow after pushing code:**
1. Spawn a background task using the `run_command` tool to run `gh pr checks --watch` (with `BypassSandbox: true` since it requires network access). 
2. **CRITICAL**: Do NOT use `&&`, `|`, or other complex shell syntax when running this command. Use clean, direct binary invocations so the user can use the "Always Allow" feature without being spammed with permission prompts.
3. Because it's running in the background, you and the user can continue conversing. When the CI pipeline finishes, the task will automatically complete and you will receive a notification with the results.
4. If the background task output shows that any checks failed, you MUST automatically investigate the failures (e.g., using `gh run list` and `gh run view <id> --log-failed`) and attempt to fix them.
5. Do not ask for permission to fix CI failures. Proceed immediately to resolving the issue.

This ensures you act as an adaptive, self-healing agent that takes full ownership of the PR lifecycle without bothering the user with sandbox permissions.
