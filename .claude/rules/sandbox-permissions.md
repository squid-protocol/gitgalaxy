---
description: "Rules for minimizing sandbox permission prompts"
globs: "*"
---
# Sandbox Permission Minimization

**CRITICAL INSTRUCTION: Avoid Permission Spam.**

The Antigravity terminal sandbox includes an "Always Allow" feature that auto-approves commands based on a prefix match of the binary (e.g., `git`, `gh`, `python3`).

However, complex shell syntax breaks this cache and forces the user to manually approve the command EVERY single time.

**To avoid spamming the user with permission prompts, follow these rules for `run_command`:**
1. **NEVER use chained commands** (`&&`, `||`, `;`) unless absolutely unavoidable. Run them as separate tool calls.
2. **NEVER use pipes** (`|`). If you need to process output, save it to a file or process it in Python.
3. **NEVER use command substitution** (`$(...)` or backticks).
4. **Avoid inline environment variables** (`VAR=val cmd`). If you need them, use `RunPersistent=True` to create a terminal, `export` the variables in one call, and run the command in the next call.
5. **Use direct binary invocations** (e.g., `.venv-zerodep/bin/python3 script.py`).

By keeping commands clean and simple, you ensure the user's "Always Allow" selections are respected, vastly improving iteration speed.
