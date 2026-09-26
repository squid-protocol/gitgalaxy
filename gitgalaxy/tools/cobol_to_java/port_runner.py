#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: the porting loop (#3753) -- bring-your-own LLM, a person approves,
# the equivalence harness proves.
#
#   python -m gitgalaxy.tools.cobol_to_java.port_runner run    <java project> --ticket KEY --backend ...
#   python -m gitgalaxy.tools.cobol_to_java.port_runner submit <java project> --ticket KEY --file PORT.java --by NAME
#   python -m gitgalaxy.tools.cobol_to_java.port_runner prove  <java project> --ticket KEY --command "..."
#   python -m gitgalaxy.tools.cobol_to_java.port_runner review <java project> --ticket KEY --approve|--reject --by NAME
#   python -m gitgalaxy.tools.cobol_to_java.port_runner status <java project>
#
# `run` turns a porting ticket (#3752, ai_agent_jobs/<KEY>_port_ticket.json) into one prompt --
# the rules, the service to fill, the source of every generated class it imports (entities with
# their record codecs, repositories, runtime), the program's and copybooks' numbered listings, the
# verified facts and worklist items -- and hands it to the backend the customer chose:
#   openai     any OpenAI-compatible chat endpoint (vLLM, Ollama, Azure, a gateway): --base-url, --model,
#              --api-key-env (the NAME of the variable holding the key; the key is never stored,
#              goes only over https -- or plain http to localhost -- and never follows a redirect)
#   anthropic  the Anthropic Messages API: --model, --api-key-env
#   command    any CLI that reads the prompt file and prints the answer: --command, with {prompt_file}
#              and {prompt_dir} placeholders (an in-house model, `agy -p`, `ollama run` ...)
# or a person writes the port and `submit`s it. The Java the answer carries is stored as a PROPOSED
# port, ai_agent_jobs/ports/<KEY>/overlay/service/<Service>.java -- an overlay; the generated sources are
# never edited. `prove` runs a proof command on it (the equivalence harness: the original COBOL and
# the port on the same inputs, every output record compared) and records its verdict; `review`
# records a person's decision. Nothing is accepted without one. Every event is a line of
# ai_agent_jobs/ports/port_log.jsonl (who, when, which backend and model, what happened), and
# `status` counts, per ticket and per model, what was proposed, proven, approved and rejected --
# "percent automated" as evidence rather than a claim.
# ==============================================================================
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

PORTS = Path("ai_agent_jobs") / "ports"


# ---- the prompt ----------------------------------------------------------------------
def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


# The generated runtime a port reads datasets, the pinned clock and record fields through.
_RUNTIME_HELPERS = ("batch/DatasetResolver.java", "batch/MainframeClock.java", "entity/vsam/CobolRecords.java")


def build_prompt(project: Path, ticket: dict[str, Any]) -> tuple[str, str]:
    """(system, user) messages for one ticket."""
    tg, prog = ticket["target"], ticket["program"]
    jobs = project / "ai_agent_jobs"
    system = "\n".join([
        "You port one mainframe program's business logic into Java, onto a Spring project generated from",
        "the whole estate. The structure (entities with record codecs, repositories, DTOs, services, batch",
        "runtime) is generated and must be used as it is. Your port will be PROVEN: the original program and",
        "your Java run on the same inputs and every output record is compared field by field, decimals",
        "exact; then a person reviews it. Follow these rules:",
        *[f"{i}. {r}" for i, r in enumerate(ticket["rules"], 1)],
        "",
        "Answer with exactly one ```java fenced block holding the complete file, then a short ```notes",
        "block listing any defect of the original you kept and any fact you found contradicted.",
    ])  # fmt: skip
    parts = [
        f"# Ticket {ticket['ticket']}: port {prog['key']} ({prog['language']}, {prog['file']})",
        "",
        f"Deliverable: {ticket['deliverable']['return']}",
        f"Methods to port: {', '.join(tg['methods_to_port']) or '(see the worklist)'}",
        f"Target stack: {json.dumps(tg['config'], sort_keys=True)}",
        "",
        f"## The generated service to fill: {tg['file']}",
        "```java",
        _read(project / tg["file"]),
        "```",
    ]
    files = [g["file"] for g in ticket["generated"]["imports"]]
    root = Path(tg["file"]).parent.parent  # the package root: the runtime helpers every port may need
    runtime = [str(root / r) for r in _RUNTIME_HELPERS]
    files += [f for f in runtime if (project / f).is_file() and f not in files]
    for f in files:
        parts += ["", f"## Generated class it may use: {f}", "```java", _read(project / f), "```"]
    for s in [ticket["source"]["program"], *ticket["source"]["copybooks"]]:
        text = _read(jobs / s["listing"]) if s.get("listing") else "(listing not available)"
        parts += ["", f"## Source: {s['file']} (numbered, columns 1-72)", "```", text, "```"]
    parts += ["", "## Verified facts (the engine's skeleton; field-testing status per section)", "```json",
              json.dumps(ticket["facts"], indent=1, sort_keys=True), "```", "", "## Worklist items", ""]  # fmt: skip
    parts += [f"- {w['id']} ({w['category']}) {w['file']}:{w['line']}: {w['text']}" for w in ticket["worklist"]]
    return system, "\n".join(parts) + "\n"


# ---- the backends --------------------------------------------------------------------
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """urllib follows a POST's 301/302/303 and carries every header along -- the API key
    included -- to wherever it points. A backend call never follows one."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ARG002
        raise urllib.error.HTTPError(req.full_url, code, f"redirect to {newurl} refused", headers, fp)


_LOOPBACK = ("localhost", "127.0.0.1", "::1")


def check_url(url: str) -> str:
    """https, or plain http only to this machine (a local vLLM / Ollama): the key never crosses
    a network unencrypted, and never goes to file: or a custom scheme."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme == "https" or (parts.scheme == "http" and parts.hostname in _LOOPBACK):
        return url
    raise SystemExit(f"backend URL must be https (or http to localhost): {url}")


def _post(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int) -> dict[str, Any]:
    headers = {"Content-Type": "application/json", **headers}
    req = urllib.request.Request(check_url(url), data=json.dumps(payload).encode(), headers=headers)  # noqa: S310
    opener = urllib.request.build_opener(_NoRedirect)
    # The operator's own endpoint: https (or loopback http) per check_url, and no redirects.
    # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
    with opener.open(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _key(env: str | None) -> str:
    if not env:
        return ""
    value = os.environ.get(env)
    if not value:
        raise SystemExit(f"the API key variable {env} is not set")
    return value


def ask(backend: str, system: str, user: str, opts: argparse.Namespace, work: Path) -> str:
    """The backend's answer text."""
    if backend == "openai":
        key = _key(opts.api_key_env)
        body = {"model": opts.model, "temperature": 0,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}  # fmt: skip
        if not opts.base_url:
            raise SystemExit("the openai backend needs --base-url (the OpenAI-compatible endpoint)")
        out = _post(opts.base_url.rstrip("/") + "/chat/completions", body,
                    {"Authorization": f"Bearer {key}"} if key else {}, opts.timeout)  # fmt: skip
        return out["choices"][0]["message"]["content"]
    if backend == "anthropic":
        body = {"model": opts.model, "max_tokens": opts.max_tokens, "system": system,
                "messages": [{"role": "user", "content": user}]}  # fmt: skip
        out = _post((opts.base_url or "https://api.anthropic.com").rstrip("/") + "/v1/messages", body,
                    {"x-api-key": _key(opts.api_key_env or "ANTHROPIC_API_KEY"), "anthropic-version": "2023-06-01"},
                    opts.timeout)  # fmt: skip
        return "".join(b.get("text", "") for b in out.get("content", []))
    if backend == "command":
        prompt = work / "prompt.md"
        prompt.write_text(f"{system}\n\n{user}", encoding="utf-8")
        argv = [a.format(prompt_file=prompt, prompt_dir=work) for a in shlex.split(opts.command)]
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=opts.timeout, stdin=subprocess.DEVNULL,  # noqa: S603
                              check=False)  # fmt: skip
        if proc.returncode != 0:
            raise SystemExit(f"the backend command failed ({proc.returncode}): {proc.stderr[-2000:]}")
        return proc.stdout
    raise SystemExit(f"unknown backend {backend!r}")


def extract_java(answer: str) -> tuple[str | None, str]:
    """(the Java file the answer carries, its notes)."""
    blocks = re.findall(r"```java[ \t]*\n(.*?)```", answer, re.S)
    java = blocks[-1] if blocks else (answer if answer.lstrip().startswith(("package ", "/*", "//")) else None)
    notes = re.findall(r"```notes[ \t]*\n(.*?)```", answer, re.S)
    return java, (notes[-1].strip() if notes else "")


# ---- the log -------------------------------------------------------------------------
def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def log_event(project: Path, event: dict[str, Any]) -> None:
    log = project / PORTS / "port_log.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": _now(), **event}, sort_keys=True) + "\n")


def events(project: Path) -> list[dict[str, Any]]:
    log = project / PORTS / "port_log.jsonl"
    return (
        [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
        if log.is_file()
        else []
    )


def load_ticket(project: Path, key: str) -> dict[str, Any]:
    path = project / "ai_agent_jobs" / f"{key}_port_ticket.json"
    if not path.is_file():
        raise SystemExit(f"no porting ticket {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _store(project: Path, ticket: dict[str, Any], java: str, attempt: int) -> Path:
    """The proposed port as an overlay: ports/<KEY>/overlay/service/<Service>.java -- the tree a proof lays over
    the generated project, nothing else in it -- and a copy per attempt under ports/<KEY>/attempts/."""
    base = project / PORTS / ticket["program"]["key"]
    dest = base / "overlay" / "service" / f"{ticket['target']['service']}.java"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(java, encoding="utf-8")
    (base / "attempts").mkdir(exist_ok=True)
    (base / "attempts" / f"{attempt:03d}_{ticket['target']['service']}.java").write_text(java, encoding="utf-8")
    return dest


def _attempt(project: Path, key: str) -> int:
    return 1 + sum(1 for e in events(project) if e.get("ticket") == key and e.get("event") == "proposed")


# ---- the commands --------------------------------------------------------------------
def cmd_run(opts: argparse.Namespace) -> int:
    project = opts.project.resolve()
    ticket = load_ticket(project, opts.ticket)
    attempt = _attempt(project, opts.ticket)
    work = project / PORTS / opts.ticket / "attempts" / f"{attempt:03d}_work"
    work.mkdir(parents=True, exist_ok=True)
    system, user = build_prompt(project, ticket)
    (work / "prompt.md").write_text(f"{system}\n\n{user}", encoding="utf-8")
    started = _now()
    answer = ask(opts.backend, system, user, opts, work)
    (work / "answer.md").write_text(answer, encoding="utf-8")
    java, notes = extract_java(answer)
    model = opts.model or (shlex.split(opts.command)[0] if opts.command else None)
    if java is None:
        log_event(project, {"event": "no-port", "ticket": opts.ticket, "attempt": attempt, "backend": opts.backend,
                            "model": model, "started": started})  # fmt: skip
        print(f"{opts.ticket}: the backend returned no Java (see {work / 'answer.md'})")
        return 1
    dest = _store(project, ticket, java, attempt)
    log_event(project, {"event": "proposed", "ticket": opts.ticket, "attempt": attempt, "backend": opts.backend,
                        "model": model, "started": started, "port": str(dest.relative_to(project)), "notes": notes})  # fmt: skip
    print(f"{opts.ticket}: proposed port {dest.relative_to(project)} (attempt {attempt}); prove it, then review it")
    return 0


def cmd_submit(opts: argparse.Namespace) -> int:
    project = opts.project.resolve()
    ticket = load_ticket(project, opts.ticket)
    attempt = _attempt(project, opts.ticket)
    dest = _store(project, ticket, opts.file.read_text(encoding="utf-8"), attempt)
    log_event(project, {"event": "proposed", "ticket": opts.ticket, "attempt": attempt, "backend": "manual",
                        "model": f"person:{opts.by}", "port": str(dest.relative_to(project)), "notes": opts.note or ""})  # fmt: skip
    print(f"{opts.ticket}: port by {opts.by} recorded as {dest.relative_to(project)} (attempt {attempt})")
    return 0


def cmd_prove(opts: argparse.Namespace) -> int:
    """Run the proof command on the latest proposed port; {port_dir} and {report_dir} are filled in. A
    report.json the command writes (the equivalence harness's) is summarised into the log."""
    project = opts.project.resolve()
    load_ticket(project, opts.ticket)
    port_dir = project / PORTS / opts.ticket
    overlay = port_dir / "overlay"
    attempt = _attempt(project, opts.ticket) - 1
    if attempt < 1:
        raise SystemExit(f"{opts.ticket}: no proposed port to prove")
    report_dir = port_dir / "attempts" / f"{attempt:03d}_proof"
    if report_dir.exists():  # a re-proof of the same attempt starts clean; the log keeps every outcome
        shutil.rmtree(report_dir)
    argv = [a.format(port_dir=overlay, report_dir=report_dir) for a in shlex.split(opts.command)]
    proc = subprocess.run(argv, capture_output=True, text=True, check=False)  # noqa: S603 -- the operator's command
    (port_dir / "attempts" / f"{attempt:03d}_proof.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
    report = report_dir / "report.json"
    summary = None
    if report.is_file():
        r = json.loads(report.read_text(encoding="utf-8"))
        summary = {dd: f"{o['equal']}/{o['records']}" for dd, o in r.get("outputs", {}).items()}
    proven = proc.returncode == 0
    log_event(project, {"event": "proven" if proven else "proof-failed", "ticket": opts.ticket, "attempt": attempt,
                        "summary": summary, "exit": proc.returncode})  # fmt: skip
    print(f"{opts.ticket} attempt {attempt}: {'PROVEN' if proven else 'NOT proven'} {summary or ''}")
    return 0 if proven else 1


def cmd_review(opts: argparse.Namespace) -> int:
    project = opts.project.resolve()
    load_ticket(project, opts.ticket)
    attempt = _attempt(project, opts.ticket) - 1
    if attempt < 1:
        raise SystemExit(f"{opts.ticket}: no proposed port to review")
    decision = "approved" if opts.approve else "rejected"
    log_event(project, {"event": decision, "ticket": opts.ticket, "attempt": attempt, "by": opts.by,
                        "note": opts.note or ""})  # fmt: skip
    print(f"{opts.ticket} attempt {attempt}: {decision} by {opts.by}")
    return 0


def status(project: Path) -> dict[str, Any]:
    """Per ticket its latest attempt's state; per model how many ports it proposed / got proven / approved."""
    tickets = sorted(
        p.name[: -len("_port_ticket.json")] for p in (project / "ai_agent_jobs").glob("*_port_ticket.json")
    )
    # #3237: in port order when the project has one -- the most-depended-on programs first.
    order_file = project / "ai_agent_jobs" / "port_order.json"
    if order_file.is_file():
        rank = {o["key"]: o["rank"] for o in json.loads(order_file.read_text(encoding="utf-8"))}
        tickets.sort(key=lambda t: (rank.get(t, len(rank) + 1), t))
    state: dict[str, dict[str, Any]] = {t: {"state": "open", "attempts": 0, "model": None} for t in tickets}
    models: dict[str, dict[str, int]] = {}
    model_of: dict[tuple[str, int], str] = {}
    for e in events(project):
        t = e.get("ticket")
        if t not in state:
            continue
        s = state[t]
        if e["event"] == "proposed":
            s.update(state="proposed", attempts=e["attempt"], model=e.get("model"))
            model_of[(t, e["attempt"])] = e.get("model") or "?"
            models.setdefault(e.get("model") or "?", {"proposed": 0, "proven": 0, "approved": 0, "rejected": 0})[
                "proposed"] += 1  # fmt: skip
        elif e["event"] in ("proven", "proof-failed", "approved", "rejected") and e.get("attempt") == s["attempts"]:
            s["state"] = e["event"]
            if e.get("summary"):
                s["summary"] = e["summary"]
            m = model_of.get((t, e["attempt"]), "?")
            if e["event"] in ("proven", "approved", "rejected"):
                models.setdefault(m, {"proposed": 0, "proven": 0, "approved": 0, "rejected": 0})[e["event"]] += 1
    counts: dict[str, int] = {}
    for s in state.values():
        counts[s["state"]] = counts.get(s["state"], 0) + 1
    # The next ticket to take: the first, in port order, that no one has a port for yet.
    nxt = next((t for t, s in state.items() if s["state"] == "open"), None)
    return {"tickets": state, "models": models, "counts": counts, "total": len(tickets), "next": nxt}


def cmd_status(opts: argparse.Namespace) -> int:
    st = status(opts.project.resolve())
    print(f"{st['total']} tickets: " + ", ".join(f"{n} {k}" for k, n in sorted(st["counts"].items())))
    for m, c in sorted(st["models"].items()):
        print(
            f"  {m}: {c['proposed']} proposed, {c['proven']} proven, {c['approved']} approved, {c['rejected']} rejected"
        )
    if st["next"]:
        print(f"  next in port order: {st['next']}")
    for t, s in st["tickets"].items():
        if s["state"] != "open":
            print(f"  {t}: {s['state']} (attempt {s['attempts']}, {s['model']}) {s.get('summary') or ''}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="ask a backend to port a ticket")
    s = sub.add_parser("submit", help="record a port a person wrote")
    p = sub.add_parser("prove", help="run the proof command on the latest proposed port")
    v = sub.add_parser("review", help="record a person's decision on the latest proposed port")
    st = sub.add_parser("status", help="per ticket and per model: proposed / proven / approved / rejected")
    for x in (r, s, p, v, st):
        x.add_argument("project", type=Path, help="the generated Java project")
    for x in (r, s, p, v):
        x.add_argument("--ticket", required=True, help="the program key, e.g. CBACT04C")
    r.add_argument("--backend", choices=("openai", "anthropic", "command"), required=True)
    r.add_argument("--model")
    r.add_argument("--base-url", help="openai: the endpoint (required); anthropic: default https://api.anthropic.com")
    r.add_argument("--api-key-env", help="the NAME of the environment variable holding the key")
    r.add_argument("--command", help="command backend: argv with {prompt_file} / {prompt_dir}")
    r.add_argument("--timeout", type=int, default=3600)
    r.add_argument("--max-tokens", type=int, default=32000)
    s.add_argument("--file", type=Path, required=True)
    s.add_argument("--by", required=True)
    s.add_argument("--note")
    p.add_argument("--command", required=True, help="the proof command, with {port_dir} / {report_dir}")
    g = v.add_mutually_exclusive_group(required=True)
    g.add_argument("--approve", action="store_true")
    g.add_argument("--reject", action="store_true")
    v.add_argument("--by", required=True)
    v.add_argument("--note")
    opts = ap.parse_args(argv)
    return {"run": cmd_run, "submit": cmd_submit, "prove": cmd_prove, "review": cmd_review, "status": cmd_status}[
        opts.cmd](opts)  # fmt: skip


if __name__ == "__main__":
    sys.exit(main())
