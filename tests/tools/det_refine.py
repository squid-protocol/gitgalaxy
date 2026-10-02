#!/usr/bin/env python3
"""A model refactors a proven deterministic port, one paragraph method at a time, every step proven.

    python tests/tools/det_refine.py run CASE --port DIR --work DIR [--backend command|anthropic|openai]
                                     [--model M] [--command "..."] [--methods NAME,...] [--retries 1]

The port (a `det_port.py --style structured` port, already proven) is copied to DIR/port. For each paragraph
method the model gets the method, the COBOL each statement came from (its comments), the fields it touches and
the runtime's contract, and returns the method rewritten for a reader -- same signature, same behaviour. The
rewrite is applied and the case proven (equivalence.py, the first run's build reused); kept when proven, else
retried once with the proof's feedback, else reverted. The port is proven after every kept step.

The model is the customer's (gitgalaxy.tools.cobol_to_java.port_runner backends: an OpenAI-compatible endpoint,
Anthropic's API, or any command). DIR/refine.json: per method, the verdict and the size before / after; DIR/port:
the refined port."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO_ROOT = TOOLS.parent.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO_ROOT))

CLAUDE = ("bash -c \"cd {prompt_dir} && exec claude -p --model MODEL --tools '' --strict-mcp-config "
          "--disable-slash-commands --no-session-persistence --output-format text < {prompt_file}\"")  # fmt: skip


def prove(case: str, port: Path, keep: Path, reuse: Path | None, faults: str) -> tuple[bool, str]:
    shutil.rmtree(keep, ignore_errors=True)
    argv = [sys.executable, str(TOOLS / "equivalence.py"), "run", case, "--port", str(port), "--keep", str(keep),
            "--faults", faults, *(["--reuse", str(reuse)] if reuse else [])]  # fmt: skip
    proc = subprocess.run(argv, capture_output=True, text=True, cwd=REPO_ROOT, check=False, timeout=3600)  # noqa: S603
    report = keep / "report.json"
    rep = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}
    ok = proc.returncode == 0 and bool(rep) and bool(rep.get("proven", True)) and not rep.get("java_failed")
    return ok, (rep.get("feedback") or proc.stdout[-3000:] + proc.stderr[-2000:])


def run(opts: argparse.Namespace) -> dict[str, Any]:
    from gitgalaxy.tools.cobol_to_java import port_runner
    from gitgalaxy.tools.cobol_to_java.det import refine as R

    work: Path = opts.work.resolve()
    port = work / "port"
    shutil.rmtree(port, ignore_errors=True)
    shutil.copytree(opts.port, port)
    service = next(port.glob("service/*.java"))
    ok, fb = prove(opts.case, port, work / "baseline", None, opts.faults)
    if not ok:
        raise SystemExit(f"the starting port does not prove -- refine a proven port only:\n{fb[:2000]}")
    opts.command = opts.command or CLAUDE.replace("MODEL", opts.model)
    steps = iter(range(1, 1_000_000))

    def ask(system: str, user: str, pdir: Path) -> str:
        return port_runner.ask(opts.backend, system, user, opts, pdir)

    def prove_now() -> tuple[bool, str]:
        return prove(opts.case, port, work / "steps" / f"{next(steps):03d}", work / "baseline", opts.faults)

    def on_step(step: dict[str, Any]) -> None:
        print(f"{step['method']}: {step.get('verdict')} ({step['attempts']} attempt(s))", flush=True)

    record = R.refine(service, ask, prove_now, work, only=opts.methods.split(",") if opts.methods else None,
                      skip=opts.skip.split(",") if opts.skip else None, largest=opts.largest, retries=opts.retries,
                      on_step=on_step)  # fmt: skip
    record = {"case": opts.case, "backend": opts.backend, "model": opts.model, **record}
    (work / "refine.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    return record


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("case")
    r.add_argument("--port", type=Path, required=True, help="a proven det port directory (service/ + cobolrt/)")
    r.add_argument("--work", type=Path, required=True)
    r.add_argument("--backend", default="command", choices=("command", "anthropic", "openai"))
    r.add_argument("--model", default="claude-sonnet-5-5")
    r.add_argument("--command", help="the command backend ({prompt_file} / {prompt_dir}); default: claude -p")
    r.add_argument("--base-url", help="the openai backend's endpoint")
    r.add_argument("--api-key-env", help="the environment variable holding the API key")
    r.add_argument("--methods", help="only these methods (comma-separated)")
    r.add_argument("--largest", type=int, help="only the N largest methods")
    r.add_argument("--skip", help="not these methods (comma-separated; e.g. those an earlier run refined)")
    r.add_argument("--retries", type=int, default=1)
    r.add_argument("--faults", default="all")
    r.add_argument("--timeout", type=int, default=600)
    r.add_argument("--max-tokens", type=int, default=16000)
    opts = r.parse_args(sys.argv[2:]) if len(sys.argv) > 1 and sys.argv[1] == "run" else ap.parse_args()
    record = run(opts)
    b, a = record["before"], record["after"]
    kept = sum(1 for s in record["steps"] if s.get("verdict") == "kept")
    print(f"{record['case']}: {kept}/{len(record['steps'])} methods refactored and proven; lines {b['lines']} -> "
          f"{a['lines']}, Cobol.* calls {b['cobol_calls']} -> {a['cobol_calls']}, if(true) {b['if_true']} -> "
          f"{a['if_true']}, {record['seconds']} s")  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
