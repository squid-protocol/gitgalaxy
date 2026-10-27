#!/usr/bin/env python3
"""Clean-machine install check for `gitgalaxy assess` (#4726). Stdlib only, no network, no .github edits.

Builds the wheel from this checkout, installs it into a fresh virtual environment (no PYTHONPATH, `--no-index`), then
runs the installed `gitgalaxy assess` on a small planted estate and asserts the report: exit 0, schema-valid,
the expected counts, a copybook gap, no planted source text, and the estate left untouched. Network is cut by proxy
variables pointing at a dead port on top of `--no-index` (assess also blocks sockets itself).

    python scripts/check_assess_install.py [--wheel-dir DIR] [--wheelhouse DIR] [--estates CORPORA] [--keep]
    python scripts/check_assess_install.py --from-pypi VERSION

--wheelhouse DIR installs the `translator` extra from local wheels (`pip wheel "gitgalaxy[translator]" -w DIR`), which
turns the translate-only dry run on; without it the dry run is skipped with its notice, and that is asserted instead.
--estates CORPORA also runs the installed command, plain and redacted, on each of the six burned estates under CORPORA
(`.mainframe_corpora`): exit 0, schema-valid report, programs found, labels under --redact, and no program name in the
redacted report. A missing estate directory is a failure, not a skip.
--from-pypi VERSION is the post-publish check (publish-assess-check.yml): nothing is built; `gitgalaxy[translator]==VERSION`
is installed from PyPI (the only networked step, retried while the index catches up), the report's `tool_version` must be
VERSION, and the planted-estate assertions run with the translator extra on. Not combinable with --wheel-dir/--wheelhouse.
Exit 0 = pass, 1 = a failed assertion, 2 = the build or install itself failed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MARK = "ZQXINSTALL"
NOTICE = "translate-only dry run skipped: pip install gitgalaxy[translator]"
BURNED = (  # estate4_draw.BURNED_NAMES, as their corpus directories
    "aws-mainframe-modernization-carddemo",
    "cics-banking-sample-application-cbsa",
    "cics-genapp",
    "zecs",
    "dbb-mortgage-application",
    "cics-async-api-credit-card-application-example",
)
VALIDATE = (
    "import json,sys;from gitgalaxy.tools.readiness import schema;"
    "e=schema.validate(json.load(open(sys.argv[1])));print(e);sys.exit(bool(e))"
)
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
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def check(cond: bool, msg: str, failures: list[str]) -> None:
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def check_burned(
    estate: Path, py: str, exe: str, work: Path, env: dict[str, str], translated: bool, failures: list[str]
) -> None:
    """The installed command on one burned estate, plain and redacted."""
    if not estate.is_dir():
        check(False, f"{estate.name}: the estate directory exists", failures)
        return
    before = fingerprint(estate)
    stems = {p.stem.upper() for p in estate.rglob("*") if p.suffix.lower() in (".cbl", ".cob", ".cobol")}
    for flag in ("", "--redact"):
        out = work / f"{estate.name}{flag}.json"
        res = run([exe, "assess", str(estate), "--out", str(out), *([flag] if flag else [])], work, env)
        tag = f"{estate.name} {flag or 'plain'}"
        check(res.returncode == 0, f"{tag}: exits 0 (got {res.returncode})", failures)
        if not out.exists():
            check(False, f"{tag}: the report was written", failures)
            continue
        text = out.read_text(encoding="utf-8")
        report = json.loads(text)
        valid = run([py, "-I", "-c", VALIDATE, str(out)], work, env)
        check(valid.returncode == 0, f"{tag}: schema.validate accepts it {valid.stdout.strip()}", failures)
        check(report["totals"]["programs"] > 0, f"{tag}: {report['totals']['programs']} programs", failures)
        check(("translation" in report["totals"]) == translated, f"{tag}: dry run present == {translated}", failures)
        if flag:
            check(all(p["name"].startswith("P-") for p in report["programs"]), f"{tag}: names are labels", failures)
            check(
                not any(f'"{stem}"' in text.upper() for stem in stems),
                f"{tag}: no program name in the report",
                failures,
            )
    check(fingerprint(estate) == before, f"{estate.name}: the estate is unchanged", failures)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--wheel-dir", type=Path, help="reuse the gitgalaxy wheel in this directory instead of building")
    ap.add_argument("--wheelhouse", type=Path, help="local wheels for the translator extra (installs it)")
    ap.add_argument(
        "--estates", type=Path, help="corpora root: also assess each burned estate with the installed command"
    )
    ap.add_argument("--from-pypi", metavar="VERSION", help="install gitgalaxy[translator]==VERSION from PyPI, no build")
    ap.add_argument("--keep", action="store_true", help="keep the work directory and print its path")
    args = ap.parse_args()
    if args.from_pypi and (args.wheel_dir or args.wheelhouse):
        ap.error("--from-pypi installs the published package: drop --wheel-dir and --wheelhouse")

    base = Path(tempfile.mkdtemp(prefix="gitgalaxy-assess-install-"))
    try:
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "VIRTUAL_ENV", "PYTHONHOME")}
        env["GITGALAXY_LICENSE_KEY"] = "COMMUNITY_FREE_TIER"
        for var in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
            env[var] = "http://127.0.0.1:9"
        work = base / "work"
        work.mkdir()

        wheel_dir = args.wheel_dir or base / "wheels"
        if args.wheel_dir is None and not args.from_pypi:
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
        wheels = [] if args.from_pypi else sorted(wheel_dir.glob("gitgalaxy-*.whl"))
        if not wheels and not args.from_pypi:
            print(f"no gitgalaxy wheel in {wheel_dir}")
            return 2

        venv = base / "venv"
        if run([sys.executable, "-m", "venv", str(venv)], work, env).returncode:
            print("venv creation failed")
            return 2
        bindir = venv / ("Scripts" if os.name == "nt" else "bin")
        py = str(bindir / ("python.exe" if os.name == "nt" else "python"))
        if args.from_pypi:
            install_env = {k: v for k, v in env.items() if "proxy" not in k.lower()}  # PyPI is reachable only here
            cmd = [py, "-m", "pip", "install", "--no-cache-dir", f"gitgalaxy[translator]=={args.from_pypi}"]
            for attempt in range(10):  # the index can lag the publish by a few minutes
                done = run(cmd, work, install_env)
                if not done.returncode:
                    break
                print(f"install attempt {attempt + 1} failed; retrying in 30 s")
                time.sleep(30)
        else:
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
        if not Path(exe).exists():
            print(f"the installed package has no `gitgalaxy` command ({exe}); a release without `assess`?")
            return 1
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
                    VALIDATE,
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
            with_extra = bool(args.wheelhouse or args.from_pypi)
            if args.from_pypi:
                check(
                    report.get("tool_version") == args.from_pypi,
                    f"tool_version is {report.get('tool_version')!r}, published {args.from_pypi!r}",
                    failures,
                )
            check(
                translated == with_extra,
                f"translate-only dry run {'ran' if translated else 'skipped'} as expected",
                failures,
            )
            check(
                (NOTICE in res.stderr) == (not with_extra),
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

        for name in BURNED if args.estates else ():
            check_burned(args.estates / name, py, exe, work, env, bool(args.wheelhouse), failures)

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
