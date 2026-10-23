#!/usr/bin/env python3
"""Clean-machine install check for `gitgalaxy assess` (#4726). Stdlib only, no network, no .github edits.

Builds the wheel from this checkout, installs it into a fresh virtual environment (no PYTHONPATH, `--no-index`), then
runs the installed `gitgalaxy assess` on a small planted estate and asserts the report: exit 0, schema-valid,
the expected counts, a copybook gap, no planted source text, and the estate left untouched. Network is cut by proxy
variables pointing at a dead port on top of `--no-index` (assess also blocks sockets itself).

    python scripts/check_assess_install.py [--wheel-dir DIR] [--wheelhouse DIR] [--keep]

--wheelhouse DIR installs the `translator` extra from local wheels (`pip wheel "gitgalaxy[translator]" -w DIR`), which
turns the translate-only dry run on; without it the dry run is skipped with its notice, and that is asserted instead.
Exit 0 = pass, 1 = a failed assertion, 2 = the build or install itself failed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MARK = "ZQXINSTALL"
NOTICE = "translate-only dry run skipped: pip install gitgalaxy[translator]"
PROGRAMS = {
    "BATCH1.cbl": (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. BATCH1.\n"
        f"      * {MARK} COMMENT\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        f"       01 WS-{MARK}-NAME PIC X(20) VALUE '{MARK} LITERAL'.\n"
        "       COPY MISSCPY.\n"
        "       PROCEDURE DIVISION.\n"
        f"       {MARK}-PARA.\n"
        f"           DISPLAY WS-{MARK}-NAME.\n"
        "           GOBACK.\n"
    ),
    "ONLINE1.cbl": (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. ONLINE1.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01 WS-AREA PIC X(10).\n"
        "       PROCEDURE DIVISION.\n"
        "           EXEC CICS RETURN END-EXEC.\n"
    ),
}


def run(cmd: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=env, check=False, timeout=1200)  # noqa: S603


def fingerprint(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*"))}


def check(cond: bool, msg: str, failures: list[str]) -> None:
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--wheel-dir", type=Path, help="reuse the gitgalaxy wheel in this directory instead of building")
    ap.add_argument("--wheelhouse", type=Path, help="local wheels for the translator extra (installs it)")
    ap.add_argument("--keep", action="store_true", help="keep the work directory and print its path")
    args = ap.parse_args()

    base = Path(tempfile.mkdtemp(prefix="gitgalaxy-assess-install-"))
    try:
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "VIRTUAL_ENV", "PYTHONHOME")}
        env["GITGALAXY_LICENSE_KEY"] = "COMMUNITY_FREE_TIER"
        for var in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
            env[var] = "http://127.0.0.1:9"
        work = base / "work"
        work.mkdir()

        wheel_dir = args.wheel_dir or base / "wheels"
        if args.wheel_dir is None:
            try:
                import setuptools  # noqa: F401

                isolation = ["--no-build-isolation"]  # offline build when setuptools is here
            except ImportError:
                isolation = []
            built = run(
                [sys.executable, "-m", "pip", "wheel", "--no-deps", *isolation, "-w", str(wheel_dir), str(REPO)],
                work,
                env,
            )
            if built.returncode:
                print("build failed:\n" + built.stderr[-3000:])
                return 2
        wheels = sorted(wheel_dir.glob("gitgalaxy-*.whl"))
        if not wheels:
            print(f"no gitgalaxy wheel in {wheel_dir}")
            return 2

        venv = base / "venv"
        if run([sys.executable, "-m", "venv", str(venv)], work, env).returncode:
            print("venv creation failed")
            return 2
        bindir = venv / ("Scripts" if os.name == "nt" else "bin")
        py = str(bindir / ("python.exe" if os.name == "nt" else "python"))
        spec = f"{wheels[-1]}[translator]" if args.wheelhouse else str(wheels[-1])
        find = ["--find-links", str(args.wheelhouse)] if args.wheelhouse else ["--no-deps"]
        done = run([py, "-m", "pip", "install", "--no-index", *find, spec], work, env)
        if done.returncode:
            print("install failed:\n" + done.stderr[-3000:])
            return 2

        estate = base / "estate"
        estate.mkdir()
        for name, text in PROGRAMS.items():
            (estate / name).write_text(text)
        before = fingerprint(estate)
        out = work / "report.json"
        exe = str(bindir / ("gitgalaxy.exe" if os.name == "nt" else "gitgalaxy"))
        res = run([exe, "assess", str(estate), "--redact", "--out", str(out)], work, env)

        failures: list[str] = []
        where = run([py, "-I", "-c", "import gitgalaxy; print(gitgalaxy.__file__)"], work, env).stdout.strip()
        check(
            "site-packages" in where and str(REPO) not in where, f"gitgalaxy imports from the venv ({where})", failures
        )
        check(res.returncode == 0, f"gitgalaxy assess exits 0 (got {res.returncode})", failures)
        text = out.read_text(encoding="utf-8") if out.exists() else ""
        check(bool(text), "the report was written", failures)
        if text:
            report = json.loads(text)
            valid = run(
                [
                    py,
                    "-I",
                    "-c",
                    (
                        "import json,sys;from gitgalaxy.tools.readiness import schema;"
                        "e=schema.validate(json.load(open(sys.argv[1])));print(e);sys.exit(bool(e))"
                    ),
                    str(out),
                ],
                work,
                env,
            )
            check(
                valid.returncode == 0,
                f"the installed schema.validate accepts the report {valid.stdout.strip()}",
                failures,
            )
            check(report["totals"]["programs"] == len(PROGRAMS), "the report counts both programs", failures)
            gaps = report.get("copybook_gaps", [])
            check(
                len(gaps) == 1 and gaps[0]["name"].startswith("C-"),
                "the missing copybook is one redacted gap",
                failures,
            )
            check(
                all(p["name"].startswith("P-") for p in report["programs"]), "--redact: programs are labels", failures
            )
            translated = "translation" in report["totals"]
            check(
                translated == bool(args.wheelhouse),
                f"translate-only dry run {'ran' if translated else 'skipped'} as expected",
                failures,
            )
            check(
                (NOTICE in res.stderr) == (not args.wheelhouse),
                "the skip notice appears exactly when the extra is absent",
                failures,
            )
        everything = text + res.stdout + res.stderr
        check(
            MARK not in everything and "BATCH1" not in text,
            "no planted source text or program name in the output",
            failures,
        )
        check(fingerprint(estate) == before, "the estate is unchanged", failures)

        if failures:
            print(f"\n{len(failures)} check(s) failed; stderr tail:\n{res.stderr[-1500:]}")
            return 1
        print("\nclean-install check passed")
        return 0
    finally:
        if args.keep:
            print(f"kept {base}")
        else:
            shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
