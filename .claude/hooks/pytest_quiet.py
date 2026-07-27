#!/usr/bin/env python3
"""
PreToolUse hook (Bash matcher): auto-adds `-q` to a bare pytest invocation so a
green run reports a summary line instead of dumping per-test scaffolding into
context. Declines to touch anything already carrying a verbosity flag (-v/-q)
or anything compound (piped/chained/redirected) -- appending a flag to the end
of e.g. `pytest tests/ | tee log.txt` would attach it to `tee`, not pytest.
"""

import json
import re
import sys

data = json.load(sys.stdin)
command = data.get("tool_input", {}).get("command", "")
stripped = command.strip()

# Only the final statement needs to be a bare pytest invocation -- commands
# commonly chain `cd`/`source` first via newlines or `&&` before the actual
# pytest call.
last_line = stripped.splitlines()[-1].strip() if stripped else ""
last_statement = re.split(r"&&", last_line)[-1].strip()

is_pytest = bool(re.match(r"^(python3?\s+-m\s+)?pytest\b", last_statement))
is_compound = bool(re.search(r"[|;>]", last_statement))
has_verbosity_flag = bool(re.search(r"(^|\s)(-v+|--verbose|-q|--quiet)(\s|$)", last_statement))

if is_pytest and not is_compound and not has_verbosity_flag:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": (
                        "Auto-added -q to keep a green pytest run from dumping "
                        "per-test scaffolding into context."
                    ),
                    "updatedInput": {"command": command + " -q"},
                }
            }
        )
    )
