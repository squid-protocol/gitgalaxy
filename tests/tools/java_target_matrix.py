"""
Compile-check the COBOL -> Java generator under a matrix of target configs (#3613).

For each config below, generate the Spring Boot project from one refactored staging
directory and run the real build (`mvn compile` or `gradle compileJava`). A config
passes only when the generated project compiles. Needs a JDK (JAVA_HOME, per Java
version: JDK_17 / JDK_21 env vars override) plus Maven, and Gradle for the gradle rows.

    python tests/tools/java_target_matrix.py <corpus dir> [--work DIR] [--only NAME ...]

The same runner is what #3121 puts in CI.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

MATRIX: dict[str, dict] = {
    "default": {},
    "java21": {"java": {"version": 21}},
    "plain-classes": {"java": {"data_classes": "plain"}},
    "plain-records": {"java": {"data_classes": "plain", "dto_style": "record"}},
    "lombok-records": {"java": {"dto_style": "record"}},
    "boot-3.3": {"spring_boot": {"version": "3.3.5"}},
    "db2": {"database": {"engine": "db2", "ddl_auto": "validate"}},
    "oracle": {"database": {"engine": "oracle"}},
    "mysql": {"database": {"engine": "mysql"}},
    "h2": {"database": {"engine": "h2", "ddl_auto": "create-drop"}},
    "minimal": {
        "features": {
            "batch": False,
            "ebcdic_decoder": False,
            "rest_controllers": False,
            "mock_services": False,
            "agent_tickets": False,
        }
    },  # fmt: skip
    "gradle": {"java": {"build_tool": "gradle"}},
    "gradle-plain-21": {"java": {"build_tool": "gradle", "data_classes": "plain", "version": 21}},
}


def _jdk(version: int) -> str:
    return os.environ.get(f"JDK_{version}") or os.environ.get("JAVA_HOME", "")


def refactor(corpus: Path, work: Path) -> Path:
    from gitgalaxy import cobol_refractor_controller

    src = work / corpus.name
    shutil.copytree(corpus, src, ignore=shutil.ignore_patterns(".git"))
    with patch("sys.argv", ["cobol-refractor", str(src)]):
        cobol_refractor_controller.main()
    return next(work.glob(f"{corpus.name}_gitgalaxy_clean_*"))


def generate(clean: Path, name: str, config: dict, work: Path) -> Path:
    import json

    from gitgalaxy import cobol_to_java_controller

    cfg = work / f"{name}.json"
    cfg.write_text(json.dumps(config), encoding="utf-8")
    for old in clean.parent.glob(f"{clean.name.replace('clean', 'java_spring')}"):
        shutil.rmtree(old)
    with patch("sys.argv", ["cobol-to-java", str(clean), "--config", str(cfg), "--header", str(work / "none.txt")]):
        cobol_to_java_controller.main()
    out = clean.parent / clean.name.replace("clean", "java_spring")
    dest = work / f"java_{name}"
    if dest.exists():
        shutil.rmtree(dest)
    out.rename(dest)
    return dest


def build(project: Path, version: int, m2: Path) -> tuple[bool, str]:
    env = dict(os.environ, JAVA_HOME=_jdk(version))
    env["PATH"] = str(Path(env["JAVA_HOME"]) / "bin") + os.pathsep + env["PATH"]
    if (project / "build.gradle").exists():
        cmd = [
            "gradle",
            "-q",
            "--no-daemon",
            "compileJava",
            f"-Dorg.gradle.java.installations.paths={env['JAVA_HOME']}",
        ]
    else:
        cmd = ["mvn", "-q", "-B", "compile", f"-Dmaven.repo.local={m2}"]
    proc = subprocess.run(cmd, cwd=project, env=env, capture_output=True, text=True, timeout=1800)  # noqa: S603
    errors = [ln for ln in (proc.stdout + proc.stderr).splitlines() if "ERROR" in ln or "error:" in ln]
    return proc.returncode == 0, "\n".join(errors[:8])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("corpus", type=Path)
    ap.add_argument("--work", type=Path, default=None)
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--m2", type=Path, default=Path.home() / ".m2" / "repository")
    ap.add_argument(
        "--summary", type=Path, default=None, help="append a Markdown results table (e.g. $GITHUB_STEP_SUMMARY)"
    )
    args = ap.parse_args()
    unknown = sorted(set(args.only or []) - set(MATRIX))
    if unknown:
        ap.error(f"unknown config(s) {unknown}; configs are {', '.join(MATRIX)}")
    work = args.work or Path(tempfile.mkdtemp(prefix="java_matrix_"))
    work.mkdir(parents=True, exist_ok=True)
    clean = refactor(args.corpus.resolve(), work)
    failed = 0
    rows = [f"### Generated Java compiles: {args.corpus.name}", "", "| config | result |", "|---|---|"]
    for name, config in MATRIX.items():
        if args.only and name not in args.only:
            continue
        project = generate(clean, name, config, work)
        version = config.get("java", {}).get("version", 17)
        ok, errors = build(project, version, args.m2)
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"\n{errors}" if errors and not ok else ""), flush=True)
        detail = "" if ok else " -- " + " / ".join(errors.splitlines()[:3]).replace("|", "/")
        rows.append(f"| `{name}` | {'PASS' if ok else 'FAIL'}{detail} |")
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(rows) + "\n\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
