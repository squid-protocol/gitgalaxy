#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: the porting loop (#3753) -- bring-your-own LLM, a person approves,
# the equivalence harness proves.
#
#   python -m gitgalaxy.tools.cobol_to_java.port_runner run    <java project> --ticket KEY --backend ...
#   python -m gitgalaxy.tools.cobol_to_java.port_runner run    <java project> --ticket KEY --backend det --source-root DIR
#   python -m gitgalaxy.tools.cobol_to_java.port_runner refine <java project> --ticket KEY --backend ... --prove-command "..."
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
#   det        no model: the deterministic translator (cobol_to_java/det) writes the port from the COBOL
#              source (--source-root, the estate the project was generated from) -- faithful by construction,
#              the same port every time; --style structured / --typed make it readable without a model
# or a person writes the port and `submit`s it. `refine` takes the latest PROVEN port and has a model rewrite it
# one method at a time for a reader, every rewrite proven with the operator's proof command and kept only if it
# proves (else retried, else reverted); each step is logged, and the result is a new attempt, proven again. The Java the answer carries is stored as a PROPOSED
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

from gitgalaxy.core.source_text import decode_bytes, read_source
from gitgalaxy.tools.cobol_to_java import proof_reach
from gitgalaxy.tools.cobol_to_java.cobol_to_java_port_tickets import count_tokens

PORTS = Path("ai_agent_jobs") / "ports"


# ---- the prompt ----------------------------------------------------------------------
def _read(path: Path) -> str:
    return read_source(path).text if path.is_file() else ""


# The generated runtime a port reads datasets, the pinned clock and record fields through.
_RUNTIME_HELPERS = (
    "batch/DatasetResolver.java",
    "batch/CobolFiles.java",  # #4023 follow-up: every file I/O statement's FILE STATUS (the porting rules)
    "batch/CobolAbend.java",  # an abend (CALL 'CEE3ABD')
    "batch/Sysout.java",  # DISPLAY (#4056)
    "batch/MainframeClock.java",
    "entity/vsam/CobolRecords.java",
    "entity/vsam/CobolEdit.java",
    "repository/db2/Db2Dates.java",  # #3828
    "util/CobolCompare.java",  # #3986
)


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
        *(
            [f"Leave as generated (no proof runs them, #4255): {', '.join(tg['left_as_generated'])}"]
            if tg.get("left_as_generated")
            else []
        ),
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


def feedback(project: Path, key: str) -> tuple[int | None, str]:
    """(attempt, prompt section) for `run --feedback`: the latest attempt whose proof failed, with what the proof
    found -- its report.json's `feedback` (the harness's first divergences), else the tail of its proof log -- and
    the port itself, so the next attempt fixes that port rather than starting over. (None, "") when no attempt of
    this ticket has a failed proof."""
    failed = [e["attempt"] for e in events(project) if e.get("ticket") == key and e.get("event") == "proof-failed"]
    if not failed:
        return None, ""
    attempt = max(failed)
    attempts = project / PORTS / key / "attempts"
    report = attempts / f"{attempt:03d}_proof" / "report.json"
    found = ""
    if report.is_file():
        found = str(json.loads(report.read_text(encoding="utf-8")).get("feedback") or "")
    if not found.strip():
        found = "```\n" + _read(attempts / f"{attempt:03d}_proof.log")[-6000:] + "\n```"
    port = next(iter(sorted(attempts.glob(f"{attempt:03d}_*.java"))), None)
    parts = [
        "",
        f"## Your previous attempt ({attempt}) was not proven",
        "",
        "The equivalence harness ran it against the expected behaviour. What it found, per scenario that did not"
        " pass (the first divergence only: later ones may hide behind it):",
        "",
        found.strip(),
    ]
    if port is not None:
        parts += ["", f"### Attempt {attempt}'s port", "```java", _read(port), "```"]
    parts += ["", "Fix the port and answer again with the complete file, as the instructions above say."]
    return attempt, "\n".join(parts) + "\n"


def ticket_hash(project: Path, key: str) -> str:
    """sha256 of the ticket JSON a port was made from (provenance: which ticket, byte for byte)."""
    import hashlib

    return hashlib.sha256((project / "ai_agent_jobs" / f"{key}_port_ticket.json").read_bytes()).hexdigest()


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


def _store(project: Path, ticket: dict[str, Any], java: str, attempt: int,
           extra: dict[str, str] | None = None) -> Path:  # fmt: skip
    """The proposed port as an overlay: ports/<KEY>/overlay/service/<Service>.java -- the tree a proof lays over
    the generated project, nothing else in it but `extra` (a deterministic port's runtime, {relative path: text})
    -- and a copy per attempt under ports/<KEY>/attempts/. The overlay holds only the latest attempt."""
    base = project / PORTS / ticket["program"]["key"]
    overlay = base / "overlay"
    if overlay.exists():
        shutil.rmtree(overlay)
    dest = overlay / "service" / f"{ticket['target']['service']}.java"
    for rel, text in {**(extra or {}), str(dest.relative_to(overlay)): java}.items():
        (overlay / rel).parent.mkdir(parents=True, exist_ok=True)
        (overlay / rel).write_text(text, encoding="utf-8")
    (base / "attempts").mkdir(parents=True, exist_ok=True)
    (base / "attempts" / f"{attempt:03d}_{ticket['target']['service']}.java").write_text(java, encoding="utf-8")
    return dest


def _attempt(project: Path, key: str) -> int:
    return 1 + sum(1 for e in events(project) if e.get("ticket") == key and e.get("event") == "proposed")


# ---- the commands --------------------------------------------------------------------
def _service_file(project: Path, ticket: dict[str, Any]) -> Path:
    svc = ticket["target"]["service"]
    found = sorted((project / "src" / "main" / "java").rglob(f"service/{svc}.java"))
    if not found:
        raise SystemExit(f"the generated project has no service {svc}.java")
    return found[0]


def _translator_version() -> str:
    """The translator's commit when it runs from a checkout (the port is a function of the source and this)."""
    here = Path(__file__).resolve().parent
    proc = subprocess.run(["git", "-C", str(here), "rev-parse", "--short=12", "HEAD"],  # noqa: S603, S607
                          capture_output=True, text=True, check=False)  # fmt: skip
    return f"det-port@{proc.stdout.strip()}" if proc.returncode == 0 and proc.stdout.strip() else "det-port"


def det_port(project: Path, ticket: dict[str, Any], source_root: Path, work: Path, style: str,
             typed: bool, groups: bool = False) -> tuple[str, dict[str, str], dict[str, Any]]:  # fmt: skip
    """The deterministic translator's port of the ticket's program: (service Java, runtime files, stats). The
    copybook directories are the ticket's copybooks' own, then symbolic maps generated from the estate's BMS."""
    from gitgalaxy.tools.cobol_to_java.det import program as P
    from gitgalaxy.tools.cobol_to_java.det.source import bms_copybooks

    src = ticket.get("source") or {}
    program = source_root / (src.get("program", {}).get("file") or ticket["program"]["file"])
    if not program.is_file():
        raise SystemExit(f"no COBOL source {program} (--source-root is the estate the project was generated from)")
    dirs: list[Path] = []
    for cb in src.get("copybooks") or []:
        d = (source_root / cb["file"]).parent
        if d not in dirs:
            dirs.append(d)
    bms = work / "bms"
    bms_copybooks([p for p in source_root.rglob("*") if p.is_file() and p.suffix.lower() == ".bms"
                   and ".git" not in p.relative_to(source_root).parts], bms)  # fmt: skip
    dirs.append(bms)
    stub_file = _service_file(project, ticket)
    stub = stub_file.read_text(encoding="utf-8")
    m = re.search(r"^package\s+([\w.]+)\.service\s*;", stub, re.M)
    if not m:
        raise SystemExit(f"{stub_file}: no `package ....service;` line")
    r = P.translate(program, dirs, stub, m.group(1), P.estate_files(project), project, style, typed, groups)
    stats = {"statements": r.stats["statements"], "translated": r.stats["translated"],
             "holes": len(r.stats["holes"]), "style": style, "typed": typed, "groups": groups}  # fmt: skip
    return r.java, P.runtime_files(m.group(1), P.has_batch(project)), stats


def cmd_run(opts: argparse.Namespace) -> int:
    project = opts.project.resolve()
    ticket = load_ticket(project, opts.ticket)
    attempt = _attempt(project, opts.ticket)
    if opts.backend == "det":
        if not opts.source_root:
            raise SystemExit("--backend det needs --source-root: the COBOL estate the project was generated from")
        work = project / PORTS / opts.ticket / "attempts" / f"{attempt:03d}_work"
        work.mkdir(parents=True, exist_ok=True)
        started = _now()
        port_java, runtime, stats = det_port(
            project, ticket, opts.source_root.resolve(), work, opts.style, opts.typed, opts.groups
        )
        dest = _store(project, ticket, port_java, attempt, runtime)
        log_event(project, {"event": "proposed", "ticket": opts.ticket, "attempt": attempt, "backend": "det",
                            "model": _translator_version(), "started": started, "port": str(dest.relative_to(project)),
                            "notes": "", "translation": stats})  # fmt: skip
        holes = f", {stats['holes']} statement(s) left as holes" if stats["holes"] else ""
        print(f"{opts.ticket}: deterministic port {dest.relative_to(project)} (attempt {attempt}): "
              f"{stats['translated']}/{stats['statements']} statements{holes}; prove it, then review it")  # fmt: skip
        return 0
    work = project / PORTS / opts.ticket / "attempts" / f"{attempt:03d}_work"
    work.mkdir(parents=True, exist_ok=True)
    system, user = build_prompt(project, ticket)
    fed_from = None
    if opts.feedback:
        fed_from, section = feedback(project, opts.ticket)
        user += section
    _, prompt_tokens, counter = count_tokens(f"{system}\n\n{user}")
    print(f"{opts.ticket}: sending {prompt_tokens} prompt tokens (measured with {counter})")
    (work / "prompt.md").write_text(f"{system}\n\n{user}", encoding="utf-8")
    started = _now()
    try:
        answer = ask(opts.backend, system, user, opts, work)
    except urllib.error.HTTPError as e:
        error_msg = f"HTTP Error {e.code}: {decode_bytes(e.read())}"
        log_event(
            project,
            {
                "event": "no-port",
                "ticket": opts.ticket,
                "attempt": attempt,
                "backend": opts.backend,
                "model": opts.model,
                "started": started,
                "error": error_msg,
            },
        )
        print(f"{opts.ticket}: the backend failed with an error: {error_msg}")
        return 1
    except Exception as e:
        log_event(
            project,
            {
                "event": "no-port",
                "ticket": opts.ticket,
                "attempt": attempt,
                "backend": opts.backend,
                "model": opts.model,
                "started": started,
                "error": str(e),
            },
        )
        print(f"{opts.ticket}: the backend failed with an error: {e}")
        return 1
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
                        "model": model, "started": started, "port": str(dest.relative_to(project)), "notes": notes,
                        "ticket_sha256": ticket_hash(project, opts.ticket), "prompt_tokens": prompt_tokens,
                        "feedback_from": fed_from})  # fmt: skip
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
    ticket = load_ticket(project, opts.ticket)
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
    unproven = unproven_methods(project, ticket, overlay)
    log_event(project, {"event": "proven" if proven else "proof-failed", "ticket": opts.ticket, "attempt": attempt,
                        "summary": summary, "exit": proc.returncode, "unproven": unproven})  # fmt: skip
    print(f"{opts.ticket} attempt {attempt}: {'PROVEN' if proven else 'NOT proven'} {summary or ''}")
    if unproven:
        print(f"{opts.ticket}: proven through {' / '.join(proof_reach.PROOF_ROOTS)} only -- {len(unproven)} ported "
              f"method(s) no proof runs (#4255): {', '.join(unproven)}")  # fmt: skip
    return 0 if proven else 1


def unproven_methods(project: Path, ticket: dict[str, Any], overlay: Path) -> list[str]:
    """#4255: the methods of the port the proof never runs that the port changed from the generated service
    (proof_reach): behaviour that would ship in the Java with no proof behind it."""
    if not overlay.is_dir():
        return []
    report = proof_reach.analyse([overlay], generated=[project / ticket["target"]["file"]])
    return sorted({f"{cls}.{m}" for cls, r in report.items() for m in r["ported_unproven"]})


def _latest_state(project: Path, key: str) -> tuple[int, str | None]:
    """(the latest attempt, its latest event: proposed / proven / proof-failed / approved / rejected)."""
    attempt = _attempt(project, key) - 1
    state = None
    for e in events(project):
        if e.get("ticket") == key and e.get("attempt") == attempt and e.get("event") in (
                "proposed", "proven", "proof-failed", "approved", "rejected"):  # fmt: skip
            state = e["event"]
    return attempt, state


def cmd_refine(opts: argparse.Namespace) -> int:
    """A model refactors the latest proven port, one method at a time, every rewrite proven with the operator's
    proof command (det.refine). Each method's outcome is a `refine-step` event; the result is a new attempt,
    `proposed` by the refining model, then proven again from scratch as `prove` would."""
    from gitgalaxy.tools.cobol_to_java.det import refine as R

    project = opts.project.resolve()
    ticket = load_ticket(project, opts.ticket)
    base, state = _latest_state(project, opts.ticket)
    if state not in ("proven", "approved"):
        raise SystemExit(f"{opts.ticket}: refine a proven port only (attempt {base} is {state or 'absent'})")
    attempt = base + 1
    port_dir = project / PORTS / opts.ticket
    work = port_dir / "attempts" / f"{attempt:03d}_refine"
    if work.exists():
        shutil.rmtree(work)
    port = work / "port"
    shutil.copytree(port_dir / "overlay", port)
    service = port / "service" / f"{ticket['target']['service']}.java"
    model = opts.model or (shlex.split(opts.command)[0] if opts.command else None)
    n = iter(range(1, 1_000_000))

    def ask_model(system: str, user: str, pdir: Path) -> str:
        return ask(opts.backend, system, user, opts, pdir)

    def prove() -> tuple[bool, str]:
        report_dir = work / "steps" / f"{next(n):03d}"
        argv = [a.format(port_dir=port, report_dir=report_dir) for a in shlex.split(opts.prove_command)]
        proc = subprocess.run(argv, capture_output=True, text=True, check=False)  # noqa: S603 -- the operator's command
        report = report_dir / "report.json"
        fb = json.loads(report.read_text(encoding="utf-8")).get("feedback") if report.is_file() else None
        return proc.returncode == 0, fb or (proc.stdout[-3000:] + proc.stderr[-2000:])

    def on_step(step: dict[str, Any]) -> None:
        log_event(project, {"event": "refine-step", "ticket": opts.ticket, "attempt": attempt, "base": base,
                            "backend": opts.backend, "model": model, **step})  # fmt: skip
        print(f"{opts.ticket} {step['method']}: {step.get('verdict')} ({step['attempts']} attempt(s))", flush=True)

    started = _now()
    record = R.refine(service, ask_model, prove, work, only=opts.only.split(",") if opts.only else None,
                      skip=opts.skip.split(",") if opts.skip else None, largest=opts.largest, retries=opts.retries,
                      on_step=on_step)  # fmt: skip
    extra = {str(p.relative_to(port)): p.read_text(encoding="utf-8") for p in sorted(port.rglob("*.java"))
             if p != service}  # fmt: skip
    dest = _store(project, ticket, service.read_text(encoding="utf-8"), attempt, extra)
    kept = sum(1 for s in record["steps"] if s.get("verdict") == "kept")
    log_event(project, {"event": "proposed", "ticket": opts.ticket, "attempt": attempt, "backend": opts.backend,
                        "model": model, "started": started, "port": str(dest.relative_to(project)), "notes": "",
                        "refined_from": base, "refinement": {"kept": kept, "steps": len(record["steps"]),
                        "before": record["before"], "after": record["after"], "seconds": record["seconds"]}})  # fmt: skip
    print(f"{opts.ticket}: {kept}/{len(record['steps'])} methods refactored and proven; Cobol.* calls "
          f"{record['before']['cobol_calls']} -> {record['after']['cobol_calls']}; proving attempt {attempt} again")  # fmt: skip
    return cmd_prove(argparse.Namespace(project=opts.project, ticket=opts.ticket, command=opts.prove_command))


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
            if "unproven" in e:  # #4255: what the latest proof of this attempt cannot reach
                s["unproven"] = e["unproven"]
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
            if s.get("unproven"):
                print(f"    not run by the proof (#4255): {', '.join(s['unproven'])}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="ask a backend to port a ticket")
    s = sub.add_parser("submit", help="record a port a person wrote")
    p = sub.add_parser("prove", help="run the proof command on the latest proposed port")
    v = sub.add_parser("review", help="record a person's decision on the latest proposed port")
    st = sub.add_parser("status", help="per ticket and per model: proposed / proven / approved / rejected")
    f = sub.add_parser("refine", help="a model refactors the latest proven port, every rewrite proven")
    for x in (r, s, p, v, st, f):
        x.add_argument("project", type=Path, help="the generated Java project")
    for x in (r, s, p, v, f):
        x.add_argument("--ticket", required=True, help="the program key, e.g. CBACT04C")
    r.add_argument("--backend", choices=("openai", "anthropic", "command", "det"), required=True)
    f.add_argument("--backend", choices=("openai", "anthropic", "command"), required=True)
    for x in (r, f):
        x.add_argument("--model")
        x.add_argument(
            "--base-url", help="openai: the endpoint (required); anthropic: default https://api.anthropic.com"
        )
        x.add_argument("--api-key-env", help="the NAME of the environment variable holding the key")
        x.add_argument("--command", help="command backend: argv with {prompt_file} / {prompt_dir}")
        x.add_argument("--timeout", type=int, default=3600)
        x.add_argument("--max-tokens", type=int, default=32000)
    r.add_argument("--source-root", type=Path, help="det: the COBOL estate the project was generated from")
    r.add_argument("--style", choices=("dispatch", "structured"), default="structured",
                   help="det: paragraphs as named methods where the program allows (structured), or a dispatcher")  # fmt: skip
    r.add_argument(
        "--typed",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="det: WORKING-STORAGE items as typed Java fields where every use allows (default; --no-typed: bytes)",
    )
    r.add_argument(
        "--groups",
        action="store_true",
        help="det, with --typed: items in groups used whole too (COMMAREAs, records), the group's bytes synced",
    )
    f.add_argument("--prove-command", required=True, help="the proof command, with {port_dir} / {report_dir}")
    f.add_argument("--only", help="only these methods (comma-separated)")
    f.add_argument("--skip", help="not these methods (comma-separated)")
    f.add_argument("--largest", type=int, help="only the N largest methods")
    f.add_argument("--retries", type=int, default=1)
    r.add_argument("--feedback", action="store_true",
                   help="give the backend the latest failed proof of this ticket: what it found and that attempt's port")  # fmt: skip
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
    return {"run": cmd_run, "submit": cmd_submit, "prove": cmd_prove, "review": cmd_review, "status": cmd_status,
            "refine": cmd_refine}[opts.cmd](opts)  # fmt: skip


if __name__ == "__main__":
    sys.exit(main())
