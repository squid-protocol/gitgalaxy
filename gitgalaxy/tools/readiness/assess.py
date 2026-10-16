# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""#4726: `gitgalaxy assess ESTATE` -- the readiness scanner a customer runs on their own machine.

    gitgalaxy assess ESTATE [--options FILE] [--redact [--redact-key-file FILE]] [--out FILE] [--verbose]
    python -m gitgalaxy.cli assess ...                       (the same, without the console script)

Offline: the network guard (`offline.install`) is in place before anything reads the estate, in this process and in
the scan it runs. Read-only: the estate is only read; the scan's database and the BMS copybooks go to a private
temporary directory removed afterwards, and `--out` may not point inside the estate. The report is built by
`schema.project` only and checked by `schema.validate` before it is written; a report that fails is not written
(exit 3). No Docker, Db2 or JDK: the inventory parses COBOL with the det parser (the `translator` extra).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

EXIT_USAGE, EXIT_INVALID_REPORT = 2, 3


def tool_version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("gitgalaxy")
    except PackageNotFoundError:
        return "unknown"


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("estate", type=Path, help="the estate's directory (programs, copybooks, BMS maps), read only")
    p.add_argument("--options", type=Path, help="the estate options file (compiler / LE / Db2 / CICS options, #4704)")
    p.add_argument("--jcl", type=Path, help="not supported yet: reading options from the estate's JCL is a follow-up")
    p.add_argument("--redact", action="store_true", help="program and copybook names as keyed-hash labels")
    p.add_argument(
        "--redact-key-file",
        type=Path,
        help="the key for --redact (same key, same labels across runs); default: a random key, unlinkable labels",
    )
    p.add_argument("--out", type=Path, help="write the report here (default: standard output); not inside the estate")
    p.add_argument("--verbose", action="store_true", help="show the scan's own console output")


def _fail(msg: str, code: int = EXIT_USAGE) -> int:
    print(f"gitgalaxy assess: {msg}", file=sys.stderr)
    return code


def _inside(path: Path, root: Path) -> bool:
    return path.resolve().is_relative_to(root.resolve())


def build(
    estate: Path,
    options: dict[str, Any] | None = None,
    redact_key: bytes | None = None,
    verbose: bool = False,
) -> dict[str, Any]:
    """The report of `estate`, offline. Raises on a scan failure."""
    from gitgalaxy.tools.readiness import offline

    offline.install()
    from gitgalaxy.tools.readiness.inventory import scan_estate
    from gitgalaxy.tools.readiness.schema import project

    def scan(target: Path, out_dir: Path) -> Path:
        return offline.guarded_scan(target, out_dir, verbose=verbose)

    with tempfile.TemporaryDirectory(prefix="gitgalaxy-assess-") as tmp:
        if _inside(Path(tmp), estate):
            raise RuntimeError("the temporary directory is inside the estate: set TMPDIR elsewhere")
        inv = scan_estate(estate.resolve(), Path(tmp), scan=scan, estate_opt=options)
    return project(inv, redact_key=redact_key, tool_version=tool_version())


def run(args: argparse.Namespace) -> int:
    estate: Path = args.estate
    if not estate.is_dir():
        return _fail(f"{estate} is not a directory")
    if args.jcl is not None:
        return _fail("--jcl is not supported yet (#4726 follow-up): pass the options it sets with --options")
    if args.out is not None and _inside(args.out, estate):
        return _fail("--out is inside the estate; the estate is read only")
    if args.redact_key_file is not None and not args.redact:
        return _fail("--redact-key-file needs --redact")
    options = None
    if args.options is not None:
        from gitgalaxy.core.estate_options import validate
        from gitgalaxy.core.source_text import read_source

        options = json.loads(
            read_source(args.options).text
        )  # the site's file: a BOM or code page decodes as the estate's
        errs = validate(options)
        if errs:
            return _fail(f"{args.options}: " + "; ".join(errs))
    key = None
    if args.redact:
        key = args.redact_key_file.read_bytes().strip() if args.redact_key_file else os.urandom(32)
        if not key:
            return _fail(f"{args.redact_key_file} is empty")

    from gitgalaxy.tools.readiness.schema import validate as check

    report = build(estate, options=options, redact_key=key, verbose=args.verbose)
    problems = check(report)
    if problems:
        for line in problems[:20]:
            print(f"  {line}", file=sys.stderr)
        return _fail(f"the report breaks its schema in {len(problems)} place(s); nothing written", EXIT_INVALID_REPORT)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out is None:
        sys.stdout.write(text)
    else:
        args.out.write_text(text, encoding="utf-8")
        print(f"gitgalaxy assess: wrote {args.out}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="gitgalaxy assess", description=__doc__.split("\n\n")[0])
    add_arguments(p)
    return run(p.parse_args(argv))
