"""
Compile-check the COBOL -> Java generator under a matrix of target configs (#3613).

For each config below, generate the Spring Boot project from one refactored staging
directory and run the real build (`mvn compile` or `gradle compileJava`). A config
passes only when the generated project compiles. Needs a JDK (JAVA_HOME, per Java
version: JDK_17 / JDK_21 env vars override) plus Maven, and Gradle for the gradle rows.

    python tests/tools/java_target_matrix.py <corpus dir> [--work DIR] [--only NAME ...] [--scan]

--scan refactors against a fresh engine scan, so the generator also builds from the
verified skeleton (#3614): CICS endpoints and COMMAREA / channel DTOs (#3615).

    python tests/tools/java_target_matrix.py <corpus dir> --same-as <base checkout> [--only ...]

--same-as decides whether a build is needed at all: it generates the Java (both the
plain and the --scan path, every selected config) with this checkout's code and with
the code at <base checkout>, and exits 0 when every file is identical -- the base
already compiled, so compiling again proves nothing. It exits 1 when anything differs
or either side fails to generate (then build). With GITHUB_OUTPUT set it writes
`identical=true|false`. --no-build generates without compiling. GITGALAXY_CODE_ROOT
chooses the checkout whose `gitgalaxy` package is imported (default: this one).

The same runner is what #3121 puts in CI.
"""

from __future__ import annotations

import argparse
import filecmp
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(os.environ.get("GITGALAXY_CODE_ROOT") or Path(__file__).resolve().parents[2]).resolve()
sys.path.insert(0, str(REPO_ROOT))
_TIMESTAMP = re.compile(rb"gitgalaxy_(clean|java_spring)_[0-9]{8}_[0-9]{6}")

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
    "ui-thymeleaf": {"ui": {"flavour": "thymeleaf"}},  # #3619: BMS screens as web pages
    "ui-openapi-plain": {"ui": {"flavour": "openapi-only"}, "java": {"data_classes": "plain"}},  # + REST, plain
}


def _jdk(version: int) -> str:
    return os.environ.get(f"JDK_{version}") or os.environ.get("JAVA_HOME", "")


def refactor(corpus: Path, work: Path, scan: bool = False) -> Path:
    from gitgalaxy import cobol_refractor_controller

    src = work / corpus.name
    shutil.copytree(corpus, src, ignore=shutil.ignore_patterns(".git"))
    with patch("sys.argv", ["cobol-refractor", str(src), *(["--scan"] if scan else [])]):
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


def normalize(project: Path) -> None:
    """Blank the run's timestamps (the clean-room name the audit and tickets cite) so two runs compare."""
    for f in project.rglob("*"):
        if f.is_file():
            data = f.read_bytes()
            fixed = _TIMESTAMP.sub(rb"gitgalaxy_\1_TIMESTAMP", data)
            if fixed != data:
                f.write_bytes(fixed)


def _same_tree(a: Path, b: Path) -> list[str]:
    """Relative paths that differ between two trees (missing on either side, or different bytes)."""
    diffs: list[str] = []

    def walk(cmp: filecmp.dircmp, rel: str) -> None:
        diffs.extend(f"{rel}{n}" for n in cmp.left_only + cmp.right_only + cmp.funny_files)
        _match, mismatch, errors = filecmp.cmpfiles(cmp.left, cmp.right, cmp.common_files, shallow=False)
        diffs.extend(f"{rel}{n}" for n in mismatch + errors)
        for name, sub in cmp.subdirs.items():
            walk(sub, f"{rel}{name}/")

    walk(filecmp.dircmp(a, b), "")
    return diffs


def same_as(corpus: Path, base: Path, only: list[str] | None, work: Path) -> tuple[bool, str]:
    """(identical, why): generate with this checkout and with `base`, both paths, and compare."""
    me = Path(__file__).resolve()
    trees: dict[str, Path] = {}
    for side, root in (("head", REPO_ROOT), ("base", base.resolve())):
        for scan in (False, True):
            out = work / f"{side}{'_scan' if scan else ''}"
            cmd = [sys.executable, str(me), str(corpus), "--work", str(out), "--no-build"]
            cmd += (["--scan"] if scan else []) + (["--only", *only] if only else [])
            env = dict(os.environ, GITGALAXY_CODE_ROOT=str(root), PYTHONPATH=str(root))
            proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=3600)  # noqa: S603
            if proc.returncode != 0:
                return False, f"{side} failed to generate ({'scan' if scan else 'plain'} path): {proc.stderr[-400:]}"
            trees[out.name] = out
    diffs: list[str] = []
    for path in ("", "_scan"):
        head, base_tree = trees[f"head{path}"], trees[f"base{path}"]
        projects = sorted(p.name for p in head.glob("java_*")) or ["(none)"]
        if projects != sorted(p.name for p in base_tree.glob("java_*")):
            return False, f"different configs generated{path}"
        for name in projects:
            diffs += [f"{name}{path}/{d}" for d in _same_tree(head / name, base_tree / name)]
    if diffs:
        return False, f"{len(diffs)} generated file(s) differ, e.g. {', '.join(diffs[:5])}"
    return True, "every generated file is identical to the base's"


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
    ap.add_argument("--scan", action="store_true", help="refactor against an engine scan (the skeleton path)")
    ap.add_argument(
        "--summary", type=Path, default=None, help="append a Markdown results table (e.g. $GITHUB_STEP_SUMMARY)"
    )
    ap.add_argument("--no-build", action="store_true", help="generate (and normalize) without compiling")
    ap.add_argument("--same-as", type=Path, default=None, metavar="BASE", help="exit 0 when the Java is unchanged")
    args = ap.parse_args()
    unknown = sorted(set(args.only or []) - set(MATRIX))
    if unknown:
        ap.error(f"unknown config(s) {unknown}; configs are {', '.join(MATRIX)}")
    work = args.work or Path(tempfile.mkdtemp(prefix="java_matrix_"))
    work.mkdir(parents=True, exist_ok=True)
    if args.same_as:
        identical, why = same_as(args.corpus.resolve(), args.same_as, args.only, work)
        print(f"{'IDENTICAL' if identical else 'CHANGED'}: {args.corpus.name}: {why}", flush=True)
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
                fh.write(f"identical={'true' if identical else 'false'}\n")
        if args.summary:
            with args.summary.open("a", encoding="utf-8") as fh:
                verdict = (
                    "unchanged: compile skipped (the base already compiles)" if identical else "changed: compiling"
                )
                fh.write(f"### Generated Java: {args.corpus.name}: {verdict}\n\n{why}\n\n")
        return 0 if identical else 1
    spec = importlib.util.find_spec("gitgalaxy")
    origin = Path(spec.origin).resolve() if spec and spec.origin else None
    if origin is None or origin.parents[1] != REPO_ROOT:
        print(f"error: gitgalaxy would be imported from {origin}, not {REPO_ROOT}", file=sys.stderr)
        return 2
    clean = refactor(args.corpus.resolve(), work, scan=args.scan)
    failed = 0
    rows = [
        f"### Generated Java compiles: {args.corpus.name}{' (engine scan)' if args.scan else ''}",
        "",
        "| config | result |",
        "|---|---|",
    ]
    for name, config in MATRIX.items():
        if args.only and name not in args.only:
            continue
        project = generate(clean, name, config, work)
        if args.no_build:
            normalize(project)
            continue
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
