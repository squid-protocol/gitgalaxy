"""
The agent porter's one non-file tool: `prove`, served over MCP (stdio, newline-delimited JSON-RPC).

The agent gets no shell. Claude Code approves read-only shell commands on its own, so with Bash the agent could have
read anything on the machine -- this repository's committed ports included -- whatever its file tools were confined
to. Its only way to run something is this tool, which runs the proof script it was started with and nothing else.

    python -m gitgalaxy.tools.cobol_to_java.agent_prove_mcp /path/to/tools/prove.sh
"""

from __future__ import annotations

import json
import subprocess
import sys

PROTOCOL = "2025-06-18"
TOOL = {
    "name": "prove",
    "description": (
        "Compile port/<Service>.java into the generated project and run the equivalence proof: the original program "
        "and the port on the same inputs, every output compared. Returns PROVEN, or what differs (or the compile "
        "errors). Takes no arguments."
    ),
    "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
}


def _reply(msg_id: object, result: dict | None = None, error: dict | None = None) -> None:
    out = {"jsonrpc": "2.0", "id": msg_id, **({"error": error} if error else {"result": result or {}})}
    sys.stdout.write(json.dumps(out) + "\n")
    sys.stdout.flush()


def _prove(script: str) -> dict:
    proc = subprocess.run([script], capture_output=True, text=True, check=False)  # noqa: S603
    text = (proc.stdout + ("\n" + proc.stderr if proc.stderr.strip() else "")).strip()[-14000:]
    return {"content": [{"type": "text", "text": text or f"(no output, exit {proc.returncode})"}],
            "isError": proc.returncode != 0}  # fmt: skip


def serve(script: str) -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        method, msg_id = msg.get("method"), msg.get("id")
        if msg_id is None:  # a notification (notifications/initialized, ...): no reply
            continue
        if method == "initialize":
            _reply(msg_id, {"protocolVersion": msg.get("params", {}).get("protocolVersion", PROTOCOL),
                            "capabilities": {"tools": {}},
                            "serverInfo": {"name": "porter", "version": "1"}})  # fmt: skip
        elif method == "tools/list":
            _reply(msg_id, {"tools": [TOOL]})
        elif method == "tools/call":
            if (msg.get("params") or {}).get("name") != "prove":
                _reply(msg_id, error={"code": -32602, "message": "the only tool is prove"})
            else:
                _reply(msg_id, _prove(script))
        elif method == "ping":
            _reply(msg_id, {})
        else:
            _reply(msg_id, error={"code": -32601, "message": f"method not found: {method}"})


if __name__ == "__main__":
    serve(sys.argv[1])
