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

    gitgalaxy assess ESTATE [--options FILE | --jcl FILE_OR_DIR] [--redact [--redact-key-file FILE]] [--no-translate] [--out FILE] [--verbose]
    python -m gitgalaxy.cli assess ...                       (the same, without the console script)

Offline: the network guard (`offline.install`) is in place before anything reads the estate, in this process and in
the scan it runs. Read-only: the estate is only read; the scan's database and the BMS copybooks go to a private
temporary directory removed afterwards, and `--out` may not point inside the estate. The report is built by
`schema.project` only and checked by `schema.validate` before it is written; a report that fails is not written
(exit 3). No Docker, Db2 or JDK: the inventory parses COBOL with the det parser (the `translator` extra), and the translate-only
dry run (dryrun.py) runs the det translator against a synthetic stub, keeping only whole / holes / refused and counts.
"""

from __future__ import annotations

import argparse
import importlib.util
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
    p.add_argument(
        "--jcl",
        type=Path,
        help="the estate's compile JCL (a member or a directory): the PARM of its IGYCRCTL steps sets the compiler options",
    )
    p.add_argument("--redact", action="store_true", help="program and copybook names as keyed-hash labels")
    p.add_argument(
        "--redact-key-file",
        type=Path,
        help="the key for --redact (same key, same labels across runs); default: a random key, unlinkable labels",
    )
    p.add_argument("--out", type=Path, help="write the report here (default: standard output); not inside the estate")
    p.add_argument(
        "--summary-md",
        type=Path,
        help="also write a human-readable Markdown summary here; not inside the estate",
    )
    p.add_argument(
        "--no-translate",
        action="store_true",
        help="skip the translate-only dry run (whole / holes / refused per program); the inventory alone",
    )
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
    translate: bool = True,
) -> dict[str, Any]:
    """The report of `estate`, offline. Raises on a scan failure."""
    from gitgalaxy.tools.readiness import offline

    offline.install()
    from gitgalaxy.tools.readiness.inventory import scan_estate
    from gitgalaxy.tools.readiness.schema import project

    scans: list[Path] = []

    def scan(target: Path, out_dir: Path) -> Path:
        scans.append(offline.guarded_scan(target, out_dir, verbose=verbose))
        return scans[-1]

    with tempfile.TemporaryDirectory(prefix="gitgalaxy-assess-") as tmp:
        if _inside(Path(tmp), estate):
            raise RuntimeError("the temporary directory is inside the estate: set TMPDIR elsewhere")
        root = estate.resolve()
        inv = scan_estate(root, Path(tmp), scan=scan, estate_opt=options)
        outcomes = _translate_only(root, Path(tmp), options, inv, scans[-1] if scans else None) if translate else None
    return project(inv, redact_key=redact_key, tool_version=tool_version(), translation=outcomes)


def _translate_only(
    estate: Path, tmp: Path, options: dict[str, Any] | None, inv: dict[str, Any], scan_db: Path | None = None
):
    """The translate-only dry run (dryrun.py) of every COBOL program the inventory parsed: no Docker, Db2 or JDK.
    #5649: on the engine's record layouts from the inventory's own scan (`scan_db`), the translator's checked against them."""
    from gitgalaxy.tools.cobol_to_java.det import cics as C
    from gitgalaxy.tools.readiness.dryrun import dry_run
    from gitgalaxy.tools.readiness.inventory import copy_dirs

    unparsed = {u["program"] for u in inv.get("unparsed_programs", [])}
    programs = [estate / rel for rel in sorted(inv.get("eras", {}).get("programs", {})) if rel not in unparsed]
    return dry_run(estate, [*copy_dirs(estate), tmp / "bms", C.COPY], options, programs, scan_db=scan_db)


def run(args: argparse.Namespace) -> int:
    estate: Path = args.estate
    if not estate.is_dir():
        return _fail(f"{estate} is not a directory")
    if args.jcl is not None and args.options is not None:
        return _fail("--jcl and --options both set the options: pass one")
    if args.jcl is not None and not args.jcl.exists():
        return _fail(f"{args.jcl} does not exist")
    if args.out is not None and _inside(args.out, estate):
        return _fail("--out is inside the estate; the estate is read only")
    if getattr(args, "summary_md", None) is not None and _inside(args.summary_md, estate):
        return _fail("--summary-md is inside the estate; the estate is read only")
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
    if args.jcl is not None:
        from gitgalaxy.tools.readiness.jcl_options import options_from_jcl

        options, notices = options_from_jcl(args.jcl)
        for line in notices:
            print(f"gitgalaxy assess: --jcl: {line}", file=sys.stderr)
    key = None
    if args.redact:
        key = args.redact_key_file.read_bytes().strip() if args.redact_key_file else os.urandom(32)
        if not key:
            return _fail(f"{args.redact_key_file} is empty")

    from gitgalaxy.tools.readiness.schema import validate as check

    translate = not args.no_translate
    if translate and importlib.util.find_spec("tree_sitter_language_pack") is None:
        # a clean `pip install gitgalaxy` has no COBOL parser: say so, rather than report every program as refused
        print("gitgalaxy assess: translate-only dry run skipped: pip install gitgalaxy[translator]", file=sys.stderr)
        translate = False
    report = build(estate, options=options, redact_key=key, verbose=args.verbose, translate=translate)
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
    if getattr(args, "summary_md", None) is not None:
        args.summary_md.write_text(render_markdown(report), encoding="utf-8")
        print(f"gitgalaxy assess: wrote {args.summary_md}", file=sys.stderr)
    return 0


def render_markdown(report: dict[str, Any]) -> str:
    """Format a customer-readable Markdown summary from a validated ``gitgalaxy assess`` report (#5054)."""
    totals = report.get("totals", {})
    tr = totals.get("translation", {})
    eras = report.get("eras", {})
    by_era = eras.get("by_era", {})
    tells = eras.get("tells", {})
    redacted = bool(report.get("redacted"))
    lines = [
        f"# Estate Readiness Summary ({'redacted' if redacted else 'full'})",
        "",
        f"- **Tool version:** `{report.get('tool_version', 'unknown')}` | **Schema:** `{report.get('schema', '')}`",
        f"- **Programs:** `{totals.get('programs', 0)}` total (`{totals.get('parsed', 0)}` parsed, `{totals.get('unparsed', 0)}` unparsed)",
    ]
    if tr:
        lines.append(
            f"- **Dry-run translation:** `{tr.get('whole', 0)}` whole, "
            f"`{tr.get('holes', 0)}` with holes, `{tr.get('refused', 0)}` refused"
        )
    if by_era:
        lines += ["", "## CICS Eras", "", "| Era | Programs |", "|---|---:|"]
        for era_k, cnt in sorted(by_era.items(), key=lambda kv: str(kv[0])):
            lines.append(f"| Era {era_k} | {cnt} |")
    if tells:
        lines += ["", "## Detected Construct Tells", "", "| Tell | Programs |", "|---|---:|"]
        for tell, cnt in sorted(tells.items(), key=lambda kv: (-int(kv[1]), kv[0])):
            lines.append(f"| `{tell}` | {cnt} |")
    rules = report.get("rules", {})
    if isinstance(rules, dict) and rules:
        lines += ["", "## Top Blocker Rules", "", "| Rule | Count |", "|---|---:|"]
        top_rules = sorted(
            rules.items(),
            key=lambda kv: (-(kv[1].get("programs", 0) if isinstance(kv[1], dict) else int(kv[1] or 0)), str(kv[0])),
        )[:15]
        for rule_id, info in top_rules:
            cnt = info.get("programs", 0) if isinstance(info, dict) else int(info or 0)
            lines.append(f"| `{rule_id}` | {cnt} |")
    lines += [
        "",
        "---",
        "To walk through a `--redact` report together before sharing any source code, contact `joe@gitgalaxy.io`.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="gitgalaxy assess", description=__doc__.split("\n\n")[0])
    add_arguments(p)
    return run(p.parse_args(argv))
