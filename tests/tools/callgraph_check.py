"""
The call-graph verification chain as one command (#3775, epic #3772).

Every call-graph PR runs the same checks. Run by hand they are six commands and
several thousand lines of output; this runs them in order and prints ONE line
per step, keeping each step's full output in a log file:

  gate:<lang>   call_graph_resolution.py <lang> --ci, per registered reference
  tests         the resolver / detector / recorder / call-graph tool tests (--full: all of tests/)
  crucible      crucible_check.py -- both modes when tiktoken's encoding is reachable,
                zero-dependency otherwise (and it says which, and why)
  tree-sitter   tree_sitter_accuracy_audit.py --ci --all
  lint          ruff / dead-key / mypy audits (--ci) and ruff format on the changed files

A missing tool, corpus or pinned version never reads as a pass (#2682): the step
is MISSING and the run fails. --regenerate rewrites the per-language baselines,
and only after every other step has passed.

    python tests/tools/callgraph_check.py                          # everything
    python tests/tools/callgraph_check.py --langs typescript --skip crucible,tree-sitter
    python tests/tools/callgraph_check.py --regenerate             # lock in an improvement
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import sysconfig
import tempfile
import time
import urllib.request
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO_ROOT = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))

from callgraph_refs import REFERENCES  # noqa: E402

TIKTOKEN_URL = "https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken"
FOCUSED_TESTS = (
    "tests/core_engine/test_call_resolver.py",
    "tests/core_engine/test_detector.py",
    "tests/tools_recorders/test_fcall_data.py",
    "tests/tools/test_call_graph_resolution_gate.py",
    "tests/tools/test_callgraph_tools.py",
)
STEPS = ("gate", "tests", "crucible", "tree-sitter", "lint")


def _tiktoken_reachable() -> tuple[bool, str]:
    """Full-precision crucible needs tiktoken's cl100k_base: cached locally, or downloadable."""
    for cache in (os.environ.get("TIKTOKEN_CACHE_DIR"), os.path.join(tempfile.gettempdir(), "data-gym-cache")):
        if cache and Path(cache).is_dir() and any(Path(cache).iterdir()):
            return True, f"cached in {cache}"
    try:
        req = urllib.request.Request(TIKTOKEN_URL, method="HEAD")
        with urllib.request.urlopen(req, timeout=8) as resp:  # noqa: S310
            return resp.status == 200, f"HTTP {resp.status}"
    except Exception as exc:  # proxy 403, DNS, timeout: all mean "not here"
        return (
            False,
            f"{TIKTOKEN_URL.split('/')[2]} unreachable ({type(exc).__name__}) -- allow it in the environment's network settings",
        )


def _changed_py() -> list[str]:
    """Python files changed against origin/main, committed or not."""
    names: set[str] = set()
    for args in (
        ["diff", "--name-only", "origin/main...HEAD"],
        ["diff", "--name-only", "HEAD"],
        ["ls-files", "--others", "--exclude-standard"],
    ):
        out = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True)  # noqa: S603, S607
        names.update(n for n in out.stdout.split() if n.endswith(".py") and (REPO_ROOT / n).is_file())
    return sorted(names)


class Runner:
    def __init__(self, log_dir: Path) -> None:
        self.log_dir = log_dir
        self.failed = False
        self.env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
        # For the python tool steps only: this interpreter's scripts first, so the
        # audits run ITS mypy / ruff / galaxyscope rather than a same-named shim
        # earlier on PATH (a uv tool's mypy without the stubs CI has). Not for the
        # gates: the same directory can hold another `node`/`npm`, whose global
        # modules have no typescript.
        self.py_env = {
            **self.env,
            "PATH": os.pathsep.join([sysconfig.get_path("scripts"), os.environ.get("PATH", "")]),
        }

    def run(self, name: str, cmd: list[str], detail=None, py_tools: bool = False) -> tuple[bool, str]:
        log = self.log_dir / f"{name.replace(':', '_')}.log"
        t0 = time.time()
        proc = subprocess.run(  # noqa: S603 -- this repo's own tools
            cmd, cwd=REPO_ROOT, env=self.py_env if py_tools else self.env, capture_output=True, text=True
        )
        out = proc.stdout + proc.stderr
        log.write_text(f"$ {' '.join(cmd)}\n\n{out}")
        ok = proc.returncode == 0
        note = detail(out) if detail else ""
        self.report(name, "PASS" if ok else "FAIL", f"{note}  ({time.time() - t0:.0f}s)", None if ok else log)
        return ok, out

    def report(self, name: str, status: str, note: str = "", log: Path | None = None) -> None:
        if status in ("FAIL", "MISSING"):
            self.failed = True
        tail = f"  -> {log}" if log else ""
        print(f"{status:8} {name:18} {note}{tail}", flush=True)


def _gate_detail(lang: str):
    def detail(out: str) -> str:
        row = re.search(
            rf"^\| {lang} \| [^|]+ \| ([\d.]+%) \((\d+) judged\) \| [^|]+ \| ([\d.]+%) \| ([\d.]+%) \|", out, re.M
        )
        base = (
            REPO_ROOT
            / "tests"
            / (
                "call_graph_resolution_baseline.json"
                if lang == "python"
                else f"call_graph_resolution_{lang}_baseline.json"
            )
        )
        if not row:
            return ""
        now = f"precision {row.group(1)} ({row.group(2)}) recall {row.group(3)} resolution {row.group(4)}"
        if base.is_file():
            b = json.loads(base.read_text())
            now += (
                f"  [baseline {b.get('confident_precision_pct')}% / {b.get('recall_pct')}% / "
                f"{b.get('resolution_recall_pct')}%]"
            )
        return now

    return detail


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--langs", default=",".join(sorted(REFERENCES)), help="comma list (default: every reference)")
    ap.add_argument("--skip", default="", help=f"comma list of steps to skip: {', '.join(STEPS)}")
    ap.add_argument("--full", action="store_true", help="the whole test suite, not the focused call-graph tests")
    ap.add_argument("--regenerate", action="store_true", help="rewrite the per-language baselines if all else passes")
    ap.add_argument("--no-cache", action="store_true", help="rebuild the reference graphs")
    ap.add_argument("--log-dir", type=Path, default=None)
    a = ap.parse_args(argv)
    langs = [x for x in a.langs.split(",") if x]
    unknown = [x for x in langs if x not in REFERENCES]
    if unknown:
        ap.error(f"no reference registered for {unknown} (callgraph_refs.REFERENCES)")
    skip = {x for x in a.skip.split(",") if x}
    log_dir = a.log_dir or Path(tempfile.mkdtemp(prefix="callgraph_check_"))
    log_dir.mkdir(parents=True, exist_ok=True)
    r = Runner(log_dir)
    py = sys.executable
    print(f"callgraph_check: logs in {log_dir}")

    if "gate" not in skip:
        for lang in langs:
            ref = REFERENCES[lang]
            installed = ref.installed()
            if not installed:
                r.report(f"gate:{lang}", "MISSING", f"{ref.tool} not installed -- {ref.install_hint}")
                continue
            if installed != ref.version:
                r.report(f"gate:{lang}", "MISSING", f"{ref.tool} {installed} is not the pinned {ref.version}")
                continue
            cmd = [py, "tests/tools/call_graph_resolution.py", lang, "--ci", "--samples", "0"]
            r.run(f"gate:{lang}", cmd + (["--no-cache"] if a.no_cache else []), _gate_detail(lang))

    if "tests" not in skip:
        targets = ["tests"] if a.full else [t for t in FOCUSED_TESTS if (REPO_ROOT / t).is_file()]
        xdist = ["-n", "auto"] if a.full else []
        r.run(
            "tests",
            [py, "-m", "pytest", "-q", "-p", "no:cacheprovider", *xdist, *targets],
            lambda out: (re.findall(r"^=*\s*(\d+ (?:passed|failed).*?) in [\d.]+s", out, re.M) or [""])[-1],
        )

    if "crucible" not in skip:
        full, why = _tiktoken_reachable()
        mode = "both" if full else "zero"
        r.run(
            "crucible",
            [py, "tests/tools/crucible_check.py", "--mode", mode],
            lambda _out, m=mode, w=why: f"mode {m} (tiktoken: {w})",
        )

    if "tree-sitter" not in skip:
        r.run(
            "tree-sitter",
            [py, "tests/tools/tree_sitter_accuracy_audit.py", "--ci", "--all"],
            lambda out: (re.findall(r"(\d+ language\(s\) checked)", out) or [""])[-1],
            py_tools=True,
        )

    if "lint" not in skip:
        for name, cmd in (
            ("lint:ruff", [py, "tests/ruff_audit.py", "--ci"]),
            ("lint:dead-key", [py, "tests/dead_key_audit.py", "--ci"]),
            ("lint:mypy", [py, "tests/mypy_audit.py", "--ci"]),
        ):
            r.run(name, cmd, py_tools=True)
        changed = _changed_py()
        if changed:
            r.run(
                "lint:format", [py, "-m", "ruff", "format", "--check", *changed], lambda _out: f"{len(changed)} files"
            )
        else:
            r.report("lint:format", "PASS", "no changed python files")

    if a.regenerate:
        if r.failed:
            r.report("regenerate", "SKIPPED", "a step failed -- baselines left as they are")
        else:
            for lang in langs:
                cmd = [py, "tests/tools/call_graph_resolution.py", lang, "--regenerate", "--samples", "0"]
                r.run(f"regenerate:{lang}", cmd, _gate_detail(lang))

    print("callgraph_check: " + ("FAILED" if r.failed else "all passed"))
    return 1 if r.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
