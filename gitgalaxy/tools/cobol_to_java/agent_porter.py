"""
The agent porter: Claude Code, with its own file tools, ports one ticket in a sandboxed workspace.

The single-shot backends send the whole ticket in one prompt and need the whole port back in one answer -- which a
large program breaks on both sides (CardDemo's COACTUPC: a 155k-token prompt, and an answer longer than one
message, of which only the tail came back). An agent does not: it reads the ticket, then opens only the listings,
copybooks and generated classes it needs, builds its file through many small edits, and runs the proof itself as
often as it likes.

What keeps its port honest is unchanged:

- **Isolation.** The workspace holds the ticket, the program's numbered listings, a read-only copy of the generated
  project's sources and the one file it ports -- not this repository, not the committed ports, not the harness.
  Claude Code runs there with --restricted (file tools confined to the workspace, no user / project settings),
  no MCP servers, nothing persisted.
- **Narrow tools.** Read, Glob, Grep, Edit, Write inside the workspace; Bash only for ./prove.sh. Only
  port/<Svc>.java is taken from the workspace.
- **Its verdict is not trusted.** ./prove.sh lets it see what the harness finds; whatever it says, the port it leaves
  is proven again by the porting loop, independently, exactly like a single-shot port.
- **Provenance.** Its whole session (stream-json) is kept as transcript.jsonl beside the attempt.

    workspace/
      TICKET.md         the rules, the deliverable, the paragraph map, the worklist, how to work
      facts.json        the engine's verified facts (the skeleton)
      FEEDBACK.md       on a later attempt: what the last proof found
      cobol/            the program's and its copybooks' numbered listings
      java/             the generated project's src/main/java (read-only: the classes it may use)
      port/<Svc>.java   the one file to write (starts as the generated service, or the last attempt's port)
      port/NOTES.md     its notes: defects of the original kept, facts it found contradicted
      prove.sh          lays port/<Svc>.java over the generated project and runs the equivalence proof
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

# Claude Code as a sandboxed agent. {model} is filled in; the prompt arrives on stdin.
AGENT_ARGV = [
    "claude", "-p", "--model", "{model}", "--restricted", "--strict-mcp-config", "--disable-slash-commands",
    "--no-session-persistence", "--permission-mode", "acceptEdits",
    "--tools", "Read,Glob,Grep,Edit,Write,Bash",
    "--allowedTools", "Read", "Glob", "Grep", "Bash(./prove.sh)",
    "--output-format", "stream-json", "--verbose",
]  # fmt: skip
# Edits are accepted anywhere in the workspace (--restricted keeps the file tools inside it): only port/<Svc>.java
# is taken from it, and that is proven again against the real generated project -- an agent that edited prove.sh
# or its copy of java/ would only mislead itself. Bash runs ./prove.sh and nothing else.

KICKOFF = (
    "Port the program described in TICKET.md. Read TICKET.md first and follow it exactly: write the port in "
    "port/{service}.java (the only file you may change), run ./prove.sh to see what the equivalence harness finds, "
    "and fix the port until ./prove.sh reports PROVEN or you cannot make progress. Then write port/NOTES.md and stop."
)


def _ticket_md(ticket: dict[str, Any], system: str, service_file: str) -> str:
    tg, prog = ticket["target"], ticket["program"]
    parts = [
        f"# Ticket {ticket['ticket']}: port {prog['key']} ({prog['language']}, {prog['file']})",
        "",
        "## How to work",
        "",
        f"- The one file you write is `port/{Path(service_file).name}`. It starts as the generated service (or, "
        "when FEEDBACK.md is there, as your previous attempt's port). Edit it in steps as you go.",
        "- The program's source is in `cobol/` as numbered listings (columns 1-72), the program first, then its "
        "copybooks. The paragraph map below gives each paragraph's first line and length: read the paragraphs "
        "you are porting, not the whole file at once.",
        "- `java/` holds the generated project's sources, read-only: the entities and their record codecs, "
        "repositories, DTOs, the runtime helpers. Use them as they are; grep for what you need.",
        "- `facts.json` holds the engine's verified facts about the program (its files, COMMAREA, calls, ...).",
        "- `./prove.sh` compiles your port into the generated project and runs the equivalence proof: the original "
        "program and your Java on the same inputs, every output compared. It prints PROVEN, or what differs. Run it "
        "whenever you want (run exactly `./prove.sh`, from the workspace: no other shell command is allowed); a "
        "compile error is reported the same way.",
        "- When it is proven, or you cannot make progress: write `port/NOTES.md` (the defects of the original you "
        "kept, each with its one-line fix; any fact you found contradicted) and stop.",
        "",
        "## The rules (your port will be proven, then reviewed)",
        "",
        system,
        "",
        f"## Deliverable\n\n{ticket['deliverable']['return']}",
        "",
        f"Methods to port: {', '.join(tg['methods_to_port']) or '(see the worklist)'}",
        f"Target stack: {json.dumps(tg['config'], sort_keys=True)}",
        "",
        "## Paragraph map (the program listing's line numbers)",
        "",
        "| paragraph | first line | lines |",
        "|---|---|---|",
        *[f"| {u['name']} | {u['start_line']} | {u['lines']} |" for u in ticket.get("paragraphs", [])],
        "",
        "## Worklist",
        "",
        *[f"- {w['id']} ({w['category']}) {w['file']}:{w['line']}: {w['text']}" for w in ticket["worklist"]],
    ]
    return "\n".join(parts) + "\n"


def _prove_sh(service: str, prove_command: str) -> str:
    """./prove.sh: the service laid as a port overlay, the proof run, its verdict and feedback printed."""
    cmd = prove_command.format(port_dir='"$PWD/.overlay"', report_dir='"$PWD/.proofs/$n"')
    return f"""#!/bin/bash
# Lays port/{service}.java over the generated project and runs the equivalence proof.
cd "$(dirname "$0")"
n=$(( $(ls -d .proofs/* 2>/dev/null | wc -l) + 1 ))
rm -rf .overlay && mkdir -p .overlay/service .proofs
cp "port/{service}.java" ".overlay/service/{service}.java"
{cmd} > ".proofs/$n.log" 2>&1
rc=$?
python3 - "$rc" ".proofs/$n" ".proofs/$n.log" <<'EOF'
import json, sys
from pathlib import Path
rc, report, log = int(sys.argv[1]), Path(sys.argv[2]) / "report.json", Path(sys.argv[3])
if rc == 0:
    print("PROVEN: every output equal, every fault run equal.")
    sys.exit(0)
r = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {{}}
text = (r.get("feedback") or "").strip() or log.read_text(encoding="utf-8", errors="replace")[-6000:]
print("NOT PROVEN.\\n" + text[:12000])
sys.exit(1)
EOF
"""


def build_workspace(project: Path, ticket: dict[str, Any], system: str, work: Path, prove_command: str,
                    start_from: Path | None, feedback: str) -> Path:  # fmt: skip
    """The sandboxed workspace for one attempt; its port/ file."""
    jobs = project / "ai_agent_jobs"
    tg = ticket["target"]
    service = tg["service"]
    # Its own temporary directory, wherever the project lives: Claude Code refuses writes under ~/.claude, and the
    # agent needs nothing of the project's location. collect() copies what it leaves back into `work`.
    ws = Path(tempfile.mkdtemp(prefix=f"gg-port-{ticket['program']['key']}-"))
    (work / "agent_workspace").write_text(str(ws) + "\n", encoding="utf-8")
    (ws / "cobol").mkdir(parents=True)
    (ws / "port").mkdir()
    (ws / "TICKET.md").write_text(_ticket_md(ticket, system, tg["file"]), encoding="utf-8")
    (ws / "facts.json").write_text(json.dumps(ticket["facts"], indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if feedback.strip():
        (ws / "FEEDBACK.md").write_text(feedback, encoding="utf-8")
    for s in [ticket["source"]["program"], *ticket["source"]["copybooks"]]:
        if s.get("listing") and (jobs / s["listing"]).is_file():
            shutil.copyfile(jobs / s["listing"], ws / "cobol" / Path(s["listing"]).name)
    shutil.copytree(project / "src/main/java", ws / "java")
    port = ws / "port" / f"{service}.java"
    shutil.copyfile(start_from if start_from is not None and start_from.is_file() else project / tg["file"], port)
    script = ws / "prove.sh"
    script.write_text(_prove_sh(service, prove_command), encoding="utf-8")
    script.chmod(0o755)
    (ws / ".transcript").write_text(str(work / "transcript.jsonl") + "\n", encoding="utf-8")
    return port


def run_agent(ws: Path, model: str, service: str, timeout: int) -> dict[str, Any]:
    """Claude Code in the workspace; {returncode, result, turns, cost_usd}. The session goes to transcript.jsonl."""
    argv = [a.format(model=model) for a in AGENT_ARGV]
    transcript = Path((ws / ".transcript").read_text(encoding="utf-8").strip())
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE_CODE_") or k == "CLAUDE_CODE_OAUTH_TOKEN"}
    with transcript.open("w", encoding="utf-8") as out:
        proc = subprocess.run(argv, input=KICKOFF.format(service=service), text=True, stdout=out,  # noqa: S603
                              stderr=subprocess.PIPE, cwd=ws, env=env, timeout=timeout, check=False)  # fmt: skip
    result: dict[str, Any] = {"returncode": proc.returncode, "stderr": proc.stderr[-2000:]}
    for line in transcript.read_text(encoding="utf-8").splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "result":
            result.update({"result": ev.get("result"), "turns": ev.get("num_turns"),
                           "cost_usd": ev.get("total_cost_usd"), "is_error": ev.get("is_error")})  # fmt: skip
    result["proofs_run"] = len(list((ws / ".proofs").glob("*.log"))) if (ws / ".proofs").is_dir() else 0
    return result


def collect(ws: Path, work: Path) -> Path:
    """The agent's port, notes and the proofs it ran, copied into the attempt's `work/agent`; the temporary
    workspace removed. The copied port file."""
    dest = work / "agent"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(ws / "port", dest / "port")
    if (ws / ".proofs").is_dir():
        shutil.copytree(ws / ".proofs", dest / "proofs", ignore=shutil.ignore_patterns("java", "cobol", "faults"))
    shutil.copyfile(ws / "TICKET.md", dest / "TICKET.md")
    shutil.rmtree(ws, ignore_errors=True)
    return dest / "port"


def describe_command() -> str:
    """The agent's command line, for the log."""
    return shlex.join(AGENT_ARGV)
