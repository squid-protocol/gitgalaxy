r"""One-command referee panel for a nightly run (#4438, item 4). Scratch results only: nothing is published.

    python tests/tools/referees/run_panel.py [--out DIR] [--corpus NAME ...] [--dry-run]

Runs the recipe in README.md ("Running the panel") for every burned, keyed mainframe corpus: scan with this
checkout, extract the engine's facts, run each referee adapter, then write the scorecard, its JSON and the
disagreements into `<out>/` plus a `run.json` (engine key, referee versions, per-step exit code and seconds,
per-source member status counts). The default `<out>` is `/tmp/gitgalaxy-scratch/referees/<engine key>`; a
directory inside the checkout is refused (it would poison the scanner and the golden masters).

The referees are external tools (README.md): each needs its environment variable, and a missing one is a loud
failure, never a skip. A step that exits non-zero, or a referee that parsed no member of a corpus, makes the run
exit 1 after the remaining corpora have run, so one JVM hang costs one corpus. `--dry-run` prints the commands.
Publishing the scorecard is on hold (owner, #4438): this tool writes files and posts nowhere.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
TOOLS = HERE.parent
for _p in (HERE, TOOLS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import estate4_draw  # noqa: E402
import facts as F  # noqa: E402
import mainframe_corpus as MC  # noqa: E402

KEY_DIR = REPO_ROOT / "tests" / "cobol_mainframe" / "answer_key"
SCRATCH = Path("/tmp/gitgalaxy-scratch/referees")
REFEREES = ("cobrix", "treesitter", "che4z", "mapa")
# the environment variable each referee needs (README.md, "Installing the referees")
REFEREE_ENV = {
    "cobrix": "COBRIX_CLASSPATH",
    "treesitter": "TS_COBOL_ENTERPRISE_LIB",
    "che4z": "CHE4Z_SERVER_JAR",
    "mapa": "MAPA_CALLTREE_JAR",
}
STEP_TIMEOUT_S = 3 * 3600

Runner = Callable[[Sequence[str], Path], int]


def panel_corpora(names: Sequence[str] = ()) -> list[dict[str, Any]]:
    """The burned corpora with an answer key (or the named ones, which must be among them)."""
    burned = [c for c in MC.load_manifest() if c.get("answer_key") and c["name"].lower() in estate4_draw.BURNED_NAMES]
    if not names:
        return burned
    by_name = {c["name"]: c for c in burned}
    unknown = [n for n in names if n not in by_name]
    if unknown:
        raise SystemExit(f"not a burned, keyed corpus: {', '.join(unknown)} (known: {', '.join(sorted(by_name))})")
    return [by_name[n] for n in names]


def preflight(env: Mapping[str, str], referees: Sequence[str] = REFEREES) -> list[str]:
    """One problem per referee whose environment variable is unset or names nothing on disk."""
    problems = []
    for r in referees:
        var = REFEREE_ENV[r]
        value = env.get(var, "")
        if not value:
            problems.append(f"{var} is not set ({r}; see tests/tools/referees/README.md)")
            continue
        # COBRIX_CLASSPATH is a path list; the others name one file
        parts = value.split(os.pathsep) if r == "cobrix" else [value]
        missing = [p for p in parts if not Path(p).exists()]
        if missing:
            problems.append(f"{var}: {missing[0]} does not exist ({r})")
    return problems


def check_out(out: Path) -> Path:
    out = out.resolve()
    if out == REPO_ROOT or REPO_ROOT in out.parents:
        raise SystemExit(f"--out {out} is inside the checkout; results go to scratch (e.g. {SCRATCH})")
    return out


def steps(corpus: dict[str, Any], out: Path, py: str = sys.executable) -> list[tuple[str, list[str]]]:
    """The commands for one corpus, in order: scan, engine facts, each referee."""
    name = corpus["name"]
    key = str(REPO_ROOT / corpus["answer_key"])
    mc = str(TOOLS / "mainframe_corpus.py")
    facts_dir = out / "facts" / name

    def adapter(a: str) -> str:
        return str(HERE / f"{a}_adapter.py")

    plan = [
        (f"{name}:fetch", [py, mc, "fetch", name]),
        (f"{name}:scan", [py, mc, "scan", name]),
        (
            f"{name}:engine",
            [
                py,
                adapter("engine"),
                "--db",
                str(MC.db_path(corpus)),
                "--corpus",
                name,
                "--key",
                key,
                "--out",
                str(facts_dir / "engine.json"),
            ],
        ),  # fmt: skip
    ]
    for r in REFEREES:
        plan.append(
            (
                f"{name}:{r}",
                [
                    py,
                    adapter(r),
                    "--corpus",
                    name,
                    "--root",
                    str(MC.clone_path(corpus)),
                    "--key",
                    key,
                    "--out",
                    str(facts_dir / f"{r}.json"),
                ],
            )  # fmt: skip
        )
    return plan


def score_step(out: Path, py: str = sys.executable) -> list[str]:
    return [py, str(HERE / "score.py"), "--facts", str(out / "facts"), "--md", str(out / "scorecard.md"),
            "--json", str(out / "scorecard.json"), "--disagreements", str(out / "disagreements.json")]  # fmt: skip


def status_counts(path: Path) -> dict[str, Any]:
    """How a referee fared on a corpus: member statuses, and the version it ran."""
    doc = F.load(path)
    counts: dict[str, int] = {}
    for entry in doc["files"].values():
        counts[entry["status"]] = counts.get(entry["status"], 0) + 1
    return {"version": doc.get("version"), "members": len(doc["files"]), "status": counts}


def subprocess_runner(cmd: Sequence[str], cwd: Path) -> int:
    try:
        return subprocess.run(list(cmd), cwd=cwd, timeout=STEP_TIMEOUT_S, check=False).returncode
    except subprocess.TimeoutExpired:
        return 124


def run_panel(
    corpora: Sequence[dict[str, Any]], out: Path, runner: Runner = subprocess_runner, py: str = sys.executable
) -> tuple[dict[str, Any], int]:
    """Run every step; returns (run.json content, exit code). A failed step does not stop the other corpora."""
    report: dict[str, Any] = {"engine": MC.engine_key(), "steps": [], "corpora": {}, "problems": []}
    parsed: dict[str, int] = {}
    unparsed: list[tuple[str, str]] = []
    for corpus in corpora:
        name = corpus["name"]
        info: dict[str, Any] = {}
        for label, cmd in steps(corpus, out, py):
            if "--out" in cmd:
                Path(cmd[cmd.index("--out") + 1]).parent.mkdir(parents=True, exist_ok=True)
            t0 = time.monotonic()
            rc = runner(cmd, REPO_ROOT)
            report["steps"].append({"step": label, "exit": rc, "seconds": round(time.monotonic() - t0, 1)})
            if rc:
                report["problems"].append(f"{label} exited {rc}")
        for src in ("engine", *REFEREES):
            path = out / "facts" / name / f"{src}.json"
            if not path.is_file():
                continue
            info[src] = status_counts(path)
            if src in REFEREES and info[src]["members"]:
                parsed[src] = parsed.get(src, 0) + info[src]["members"] - info[src]["status"].get("fail", 0)
                if info[src]["status"].get("fail", 0) == info[src]["members"]:
                    unparsed.append((src, f"{name}: {src} parsed none of {info[src]['members']} members"))
        report["corpora"][name] = info
    # A referee that parsed nothing anywhere is a broken install (a problem); one that cannot parse a single
    # corpus's dialect (tree-sitter on CBL / PROCESS cards) is a finding, kept as a note in run.json.
    for src, line in unparsed:
        if parsed[src]:
            report.setdefault("notes", []).append(line)
        else:
            report["problems"].append(line)
    t0 = time.monotonic()
    rc = runner(score_step(out, py), REPO_ROOT)
    report["steps"].append({"step": "score", "exit": rc, "seconds": round(time.monotonic() - t0, 1)})
    if rc:
        report["problems"].append(f"score exited {rc}")
    return report, 1 if report["problems"] else 0


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, help=f"scratch directory (default {SCRATCH}/<engine key>)")
    ap.add_argument("--corpus", action="append", default=[], help="a burned keyed corpus (default: all of them)")
    ap.add_argument("--dry-run", action="store_true", help="print the commands and run nothing")
    args = ap.parse_args(argv)

    corpora = panel_corpora(args.corpus)
    out = check_out(args.out or SCRATCH / MC.engine_key())
    if args.dry_run:
        for corpus in corpora:
            for label, cmd in steps(corpus, out):
                print(f"{label}: {' '.join(cmd)}")
        print(f"score: {' '.join(score_step(out))}")
        return 0
    problems = preflight(os.environ if env is None else env)
    if problems:
        print("referee panel not runnable:", *problems, sep="\n  ", file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    report, code = run_panel(corpora, out)
    (out / "run.json").write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    for p in report["problems"]:
        print(f"PROBLEM: {p}", file=sys.stderr)
    print(f"referee panel: {len(corpora)} corpora, scratch results in {out} (nothing published)")
    return code


if __name__ == "__main__":
    sys.exit(main())
