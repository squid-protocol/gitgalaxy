"""
#3212: a snapshot of everything `cobol-refractor` and `cobol-to-java` generate
for a COBOL repository -- the clean room (JCL, schemas, IR dumps, audit report,
agent jobs) and the Spring Boot tree -- diffed against a committed copy.

    python tests/tools/refraction_snapshot.py check  [--excerpts | --corpus NAME ...]
    python tests/tools/refraction_snapshot.py update [--excerpts | --corpus NAME ...]

Two inputs, one mechanism:

  --excerpts (default)  tests/cobol_mainframe/refraction_excerpts/<corpus>/, small
                        committed slices of the pinned corpora. CI runs this through
                        tests/cobol_mainframe/test_refraction_snapshot.py.
  --corpus NAME         the full pinned corpus from tests/tools/mainframe_corpus.py
                        (fetch it first). Local only: CI does not clone the corpora.

Snapshots live in tests/cobol_mainframe/refraction_snapshot/{excerpts,full}/<corpus>/
as one `<path>.snap` file per generated file, so a PR diff shows exactly which JCL,
schema, IR or Java lines a change moved. `update` is the bless: run it only after
reading the `check` diff, and say in the PR description what moved and why.

Both controllers run in-process on a COPY of the input (the refractor writes its
clean room next to its target). Normalisation: the scratch directory becomes
`<WORK>` with `/` separators, the clean-room timestamp becomes `<TS>`, JSON is
re-serialised canonically, and a binary file (the SQLite-mode IR DB) is recorded
by name only.
"""

import argparse
import contextlib
import difflib
import io
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

MAINFRAME = REPO_ROOT / "tests" / "cobol_mainframe"
EXCERPTS = MAINFRAME / "refraction_excerpts"
SNAPSHOTS = MAINFRAME / "refraction_snapshot"
SUFFIX = ".snap"

_TIMESTAMP = re.compile(r"_gitgalaxy_(clean|java_spring)_\d{8}_\d{6}")
_BINARY_SUFFIXES = {".db", ".sqlite"}


def _work_variants(work: Path) -> list[str]:
    """Every spelling of the scratch directory an output can contain, longest first."""
    spellings = {str(work), str(work.resolve()), work.as_posix(), work.resolve().as_posix()}
    spellings |= {s.replace("\\", "\\\\") for s in list(spellings)}  # as escaped inside JSON text
    return sorted(spellings, key=len, reverse=True)


def _normalise_str(text: str, variants: list[str]) -> str:
    for v in variants:
        if v in text:
            head, *rest = text.split(v)
            text = head + "".join("<WORK>" + _slashes(part) for part in rest)
    return _TIMESTAMP.sub(r"_gitgalaxy_\1_<TS>", text)


def _slashes(tail: str) -> str:
    """`\\` -> `/` in the path that follows a <WORK> prefix, up to the first whitespace or quote."""
    m = re.match(r"[^\s\"'\]\)]*", tail)
    return tail[: m.end()].replace("\\", "/") + tail[m.end() :] if m else tail


def _normalise_json(obj: Any, variants: list[str]) -> Any:
    if isinstance(obj, str):
        return _normalise_str(obj, variants)
    if isinstance(obj, list):
        return [_normalise_json(v, variants) for v in obj]
    if isinstance(obj, dict):
        return {k: _normalise_json(v, variants) for k, v in obj.items()}
    return obj


def run_pipeline(source: Path, work: Path) -> dict[str, str]:
    """Runs cobol-refractor, then cobol-to-java on its clean room, over a copy of
    `source`; returns every generated file as {normalised relative path: text}."""
    from gitgalaxy import cobol_refractor_controller, cobol_to_java_controller

    target = work / source.name
    shutil.copytree(source, target, ignore=shutil.ignore_patterns(".git"))
    os.environ.setdefault("GITGALAXY_LICENSE_KEY", "COMMUNITY_FREE_TIER")
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        with patch("sys.argv", ["cobol-refractor", str(target)]):
            cobol_refractor_controller.main()
        clean = next(work.glob(f"{source.name}_gitgalaxy_clean_*"))
        # A missing header file keeps the output independent of the caller's cwd.
        with patch("sys.argv", ["cobol-to-java", str(clean), "--header", str(work / "no_header.txt")]):
            cobol_to_java_controller.main()
    java = next(work.glob(f"{source.name}_gitgalaxy_java_spring_*"))

    variants = _work_variants(work)
    out: dict[str, str] = {}
    for label, root in (("clean", clean), ("java", java)):
        for path in sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: p.parts):
            rel = f"{label}/{path.relative_to(root).as_posix()}"
            if path.suffix in _BINARY_SUFFIXES:
                out[rel] = "<binary>\n"
            elif path.suffix == ".json":
                obj = _normalise_json(json.loads(path.read_text(encoding="utf-8")), variants)
                out[rel] = json.dumps(obj, indent=2, ensure_ascii=False) + "\n"
            else:
                out[rel] = _normalise_str(path.read_text(encoding="utf-8", errors="replace"), variants)
    return out


def generate(source: Path) -> dict[str, str]:
    with tempfile.TemporaryDirectory(prefix="refraction_snapshot_") as tmp:
        return run_pipeline(source, Path(tmp))


def read_snapshot(snap_dir: Path) -> dict[str, str]:
    if not snap_dir.is_dir():
        return {}
    return {
        p.relative_to(snap_dir).as_posix()[: -len(SUFFIX)]: p.read_text(encoding="utf-8")
        for p in sorted(snap_dir.rglob(f"*{SUFFIX}"))
    }


def write_snapshot(snap_dir: Path, outputs: dict[str, str]) -> None:
    if snap_dir.exists():
        shutil.rmtree(snap_dir)
    for rel, text in outputs.items():
        path = snap_dir / f"{rel}{SUFFIX}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))  # LF on every OS; write_text(newline=) needs Python 3.10


def diff(expected: dict[str, str], actual: dict[str, str]) -> list[str]:
    """One entry per differing file: a unified diff, or a missing/unexpected note."""
    out = []
    for rel in sorted(expected.keys() | actual.keys()):
        if rel not in actual:
            out.append(f"missing (in the snapshot, not generated): {rel}")
        elif rel not in expected:
            out.append(f"unexpected (generated, not in the snapshot): {rel}")
        elif expected[rel] != actual[rel]:
            lines = difflib.unified_diff(
                expected[rel].splitlines(keepends=True),
                actual[rel].splitlines(keepends=True),
                f"snapshot/{rel}",
                f"generated/{rel}",
            )
            out.append("".join(lines))
    return out


def targets(args: argparse.Namespace) -> list[tuple[str, Path, Path]]:
    """(label, source, snapshot dir) for each requested input."""
    if args.corpus:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import mainframe_corpus

        return [
            (c["name"], mainframe_corpus.require_clone(c), SNAPSHOTS / "full" / c["name"])
            for c in mainframe_corpus.select(args.corpus)
        ]
    return [(p.name, p, SNAPSHOTS / "excerpts" / p.name) for p in sorted(EXCERPTS.iterdir()) if p.is_dir()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["check", "update"])
    which = ap.add_mutually_exclusive_group()
    which.add_argument("--excerpts", action="store_true", help="the committed excerpts (default)")
    which.add_argument("--corpus", nargs="+", metavar="NAME", help="full pinned corpora (see mainframe_corpus.py)")
    args = ap.parse_args()

    failed = False
    for label, source, snap_dir in targets(args):
        actual = generate(source)
        if args.cmd == "update":
            write_snapshot(snap_dir, actual)
            print(f"{label}: {len(actual)} files -> {snap_dir.relative_to(REPO_ROOT)}")
            continue
        diffs = diff(read_snapshot(snap_dir), actual)
        print(f"{label}: {len(actual)} files, {len(diffs)} differ")
        for d in diffs:
            print(d)
        failed |= bool(diffs)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
