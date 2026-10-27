#!/usr/bin/env python3
"""Manage hash-pinned, universal requirement lockfiles for CI and shipped templates (#4918).

Compiles and validates universal lockfiles valid across all supported OS and Python >= 3.11 matrices,
preserving multi-version environment markers (e.g. for numpy, xgboost, typing-extensions).

Usage:
    python tests/tools/pin_requirements.py                    # compile all ci/requirements/*.in
    python tests/tools/pin_requirements.py --target ci        # compile ci/requirements/*.in
    python tests/tools/pin_requirements.py --target templates # compile templates/requirements/*.in
    python tests/tools/pin_requirements.py --target all       # compile both sets
    python tests/tools/pin_requirements.py --check            # verify lockfiles match sources & have markers
    python tests/tools/pin_requirements.py --upgrade          # upgrade dependencies to latest matching
    python tests/tools/pin_requirements.py -P ruff            # upgrade a specific package only
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CI_REQS = ROOT / "ci" / "requirements"
TEMPLATE_REQS = ROOT / "templates" / "requirements"

# Packages known to require version splits across Python 3.11 / 3.12 matrices.
# A universal compile MUST preserve their python version markers, not collapse them to a single flat pin.
MULTIVERSION_PACKAGES = {"numpy", "xgboost"}

HEADER_DESCRIPTIONS = {
    CI_REQS: ("GitGalaxy's own CI", "tests/tools/pin_ci_requirements.sh"),
    TEMPLATE_REQS: ("the shipped GitGalaxy CI surface", "tests/tools/pin_shipped_requirements.sh"),
}


def find_uv() -> str:
    """Find the uv executable in PATH or standard user install locations."""
    found = shutil.which("uv")
    if found:
        return found
    candidates = [
        Path.home() / ".local" / "bin" / "uv",
        Path.home() / ".cargo" / "bin" / "uv",
        Path("/usr/local/bin/uv"),
        Path("/usr/bin/uv"),
    ]
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)
    raise FileNotFoundError(
        "uv executable not found. Install uv (e.g. `curl -LsSf https://astral.sh/uv/install.sh | sh`) "
        "or ensure it is on PATH."
    )


def verify_multiversion_markers(path: Path | str, content: str) -> list[str]:
    """Return errors if any multiversion packages in `content` are missing environment markers."""
    errors: list[str] = []
    name_str = Path(path).name
    # Match package blocks: name==version [; marker] \ ...
    blocks = re.findall(r"^([a-zA-Z0-9_.\-]+)==([^\s;\\]+)(?:[ \t]*;[ \t]*([^\n\\]+))?", content, re.M)
    by_pkg: dict[str, list[tuple[str, str]]] = {}
    for name, ver, marker in blocks:
        by_pkg.setdefault(name.lower(), []).append((ver, marker.strip() if marker else ""))

    for pkg in MULTIVERSION_PACKAGES:
        if pkg not in by_pkg:
            continue
        entries = by_pkg[pkg]
        # If there is only 1 entry and it has no python marker, universal resolution was lost
        # (e.g. a flat Dependabot compile on Python 3.12 pinned numpy==2.5.3 with no markers)
        if len(entries) == 1 and not any("python" in m for _, m in entries):
            errors.append(
                f"{name_str}: {pkg} is pinned to a single version ({entries[0][0]}) without "
                f"python_full_version markers. In a universal lockfile, {pkg} requires markers "
                "across the Python >= 3.11 matrix."
            )
        elif len(entries) > 1:
            for ver, marker in entries:
                if not marker or "python" not in marker:
                    errors.append(
                        f"{name_str}: {pkg}=={ver} has multiple versions but lacks python environment markers"
                    )
    return errors


def compile_lockfile(
    in_path: Path,
    uv_bin: str,
    upgrade: bool = False,
    upgrade_packages: list[str] | None = None,
) -> str:
    """Compile a single .in file to .txt using uv pip compile from its directory.

    The committed .txt is handed to uv as the output file (a scratch copy), so uv keeps every existing pin that still
    satisfies the .in file and moves only what the .in file, --upgrade or --upgrade-package asks for. Without it a
    regeneration floated every unpinned transitive dependency to the newest release, and --check reported STALE as
    soon as anything upstream published a release.
    """
    dir_path = in_path.parent
    desc, regen = HEADER_DESCRIPTIONS.get(
        dir_path,
        ("GitGalaxy requirements", f"pin_requirements.py (source: {in_path.name})"),
    )

    cmd = [
        uv_bin,
        "pip",
        "compile",
        in_path.name,
        "--generate-hashes",
        "--universal",
        "--python-version",
        "3.11",
        "--no-header",
        "-q",
    ]
    if upgrade:
        cmd.append("--upgrade")
    if upgrade_packages:
        for pkg in upgrade_packages:
            cmd.extend(["--upgrade-package", pkg])

    txt_path = in_path.with_suffix(".txt")
    with tempfile.TemporaryDirectory() as scratch:
        seed = Path(scratch) / txt_path.name
        if txt_path.is_file():
            shutil.copyfile(txt_path, seed)
        cmd.extend(["--output-file", str(seed)])
        res = subprocess.run(cmd, cwd=dir_path, capture_output=True, text=True, check=False)  # noqa: S603
        if res.returncode != 0:
            raise RuntimeError(f"Failed to compile {in_path}:\n{res.stderr.strip()}")
        body = seed.read_text(encoding="utf-8")

    header = (
        f"# Hash-pinned install set for {desc} (#4918). Do not edit by hand.\n"
        f"# Regenerate: {regen}  (source: {in_path.name})\n"
    )
    return header + body


def process_target(
    directory: Path,
    uv_bin: str,
    check: bool = False,
    upgrade: bool = False,
    upgrade_packages: list[str] | None = None,
    specific_files: list[str] | None = None,
) -> int:
    """Compile or check lockfiles in a directory."""
    in_files = sorted(directory.glob("*.in"))
    if specific_files:
        in_files = [f for f in in_files if f.name in specific_files or f.stem in specific_files]
        if not in_files:
            print(f"No matching .in files found in {directory} for: {specific_files}", file=sys.stderr)
            return 1

    failures = 0
    for in_file in in_files:
        txt_file = in_file.with_suffix(".txt")
        compiled = compile_lockfile(
            in_file,
            uv_bin,
            upgrade=upgrade,
            upgrade_packages=upgrade_packages,
        )

        marker_errors = verify_multiversion_markers(txt_file, compiled)
        if marker_errors:
            for err in marker_errors:
                print(f"ERROR  {err}", file=sys.stderr)
            failures += 1
            continue

        if check:
            if not txt_file.is_file():
                print(f"MISSING  {txt_file.relative_to(ROOT)} does not exist", file=sys.stderr)
                failures += 1
                continue
            current = txt_file.read_text(encoding="utf-8")
            disk_errors = verify_multiversion_markers(txt_file, current)
            if disk_errors:
                for err in disk_errors:
                    print(f"STALE/CORRUPT  {err}", file=sys.stderr)
                failures += 1
                continue
            if current != compiled:
                print(f"STALE  {txt_file.relative_to(ROOT)} is out of sync with {in_file.name}", file=sys.stderr)
                failures += 1
            else:
                print(f"OK     {txt_file.relative_to(ROOT)}")
        else:
            tmp = txt_file.with_suffix(".tmp")
            tmp.write_text(compiled, encoding="utf-8")
            tmp.replace(txt_file)
            print(f"WROTE  {txt_file.relative_to(ROOT)}")

    return 1 if failures > 0 else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--target",
        choices=["ci", "templates", "all"],
        default="ci",
        help="Which requirement set to manage (default: ci)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify lockfiles match .in files and contain valid multiversion markers (do not write)",
    )
    parser.add_argument(
        "--upgrade",
        "-U",
        action="store_true",
        help="Upgrade all packages to latest compatible versions",
    )
    parser.add_argument(
        "--upgrade-package",
        "-P",
        action="append",
        dest="upgrade_packages",
        metavar="PKG",
        help="Upgrade only specified package(s) (can be passed multiple times)",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Optional specific .in file stem(s) to compile (e.g. engines, pytest)",
    )
    args = parser.parse_args(argv)

    try:
        uv_bin = find_uv()
    except FileNotFoundError as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1

    rc = 0
    if args.target in ("ci", "all"):
        rc |= process_target(
            CI_REQS,
            uv_bin=uv_bin,
            check=args.check,
            upgrade=args.upgrade,
            upgrade_packages=args.upgrade_packages,
            specific_files=args.files or None,
        )

    if args.target in ("templates", "all"):
        rc |= process_target(
            TEMPLATE_REQS,
            uv_bin=uv_bin,
            check=args.check,
            upgrade=args.upgrade,
            upgrade_packages=args.upgrade_packages,
            specific_files=args.files or None,
        )

    return rc


if __name__ == "__main__":
    sys.exit(main())
