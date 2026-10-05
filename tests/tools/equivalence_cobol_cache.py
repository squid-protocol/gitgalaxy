"""The oracle side of a proof, kept: a COBOL step's outputs, reused when nothing the step reads has changed (#4463).

A proof's COBOL side (compile under GnuCOBOL, run, unload) depends on the case's inputs and the oracle, never on the
Java port or the translator: re-proving a det port after a translator change reruns the same COBOL. A step is the
`run.sh` in a work directory and the files staged beside it (the program, copybooks, inputs, fault plans, the
stubs and models). Its key is a hash of

  inputs       every file of the work directory before the step runs (path and bytes: run.sh included), so a
               changed case input, program, copybook, clock, fault plan or stub is a new key;
  oracle       what `equivalence_oracle.fingerprint` says the image is: the base image's digest, the GnuCOBOL package
               and the `cobc --version` line -- NOT the image id, which a rebuild from the same Dockerfile changes;
  harness      FORMAT, and the bytes of the harness modules that decide what is staged and run.

A hit copies the files the step wrote (everything new or changed, but compiled binaries nobody reads) into the work
directory; a miss runs the step and stores them. Only a step that exits 0 on the pinned oracle image is stored; a
Db2 step (its state lives in a database, not the work directory) is never cached.

The cache lives under $GITGALAXY_COBOL_CACHE, else <$GITGALAXY_EQUIV_CACHE or ~/.cache/gitgalaxy-equivalence>/cobol;
"off" (either variable) runs every step. In CI it is restored and saved with actions/cache (det-sweep.yml)."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Optional

TOOLS = Path(__file__).resolve().parent
FORMAT = "gitgalaxy-cobol-step-cache/1"
ENV = "GITGALAXY_COBOL_CACHE"
# the modules that decide what a step stages and runs: a change to one is a new harness version
HARNESS_FILES = ("equivalence.py", "equivalence_call.py", "equivalence_cics.py", "equivalence_common.py",
                 "equivalence_inputs.py", "equivalence_oracle.py", "equivalence_cobol_cache.py")  # fmt: skip
KEEP_BYTES = 4 << 30  # `prune` default
_ELF = b"\x7fELF"


def root() -> Optional[Path]:
    """The cache directory, or None when caching is off."""
    value = os.environ.get(ENV, "")
    if value.lower() == "off":
        return None
    if value:
        return Path(value)
    base = os.environ.get("GITGALAXY_EQUIV_CACHE", "")
    if base.lower() == "off":
        return None
    return (Path(base) if base else Path.home() / ".cache" / "gitgalaxy-equivalence") / "cobol"


_HARNESS: Optional[str] = None


def harness_version() -> str:
    global _HARNESS
    if _HARNESS is None:
        h = hashlib.sha256(FORMAT.encode())
        for name in HARNESS_FILES:
            h.update(name.encode() + b"\0" + (TOOLS / name).read_bytes())
        _HARNESS = h.hexdigest()
    return _HARNESS


def oracle_identity(fp: dict[str, Any]) -> dict[str, Optional[str]]:
    """The parts of an oracle fingerprint that decide what GnuCOBOL does (not the image id)."""
    return {"base": fp.get("base"), "gnucobol3": fp.get("gnucobol3"), "cobc": fp.get("cobc")}


def snapshot(work: Path) -> dict[str, str]:
    """{relative path: sha256} of every regular file under `work`."""
    out = {}
    for f in sorted(work.rglob("*")):
        if f.is_file() and not f.is_symlink():
            out[f.relative_to(work).as_posix()] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


def step_key(pre: dict[str, str], oracle: dict[str, Optional[str]], harness: Optional[str] = None) -> str:
    """The key of a step: its inputs (a snapshot of the work directory), the oracle and the harness version."""
    h = hashlib.sha256()
    h.update(
        json.dumps({"inputs": pre, "oracle": oracle, "harness": harness or harness_version()}, sort_keys=True).encode()
    )
    return h.hexdigest()[:32]


def _is_binary_product(f: Path) -> bool:
    with f.open("rb") as fh:
        return fh.read(4) == _ELF


def lookup(base: Path, key: str, work: Path) -> bool:
    """Copy the stored step `key` into `work`; whether there was one."""
    entry = base / key
    if not (entry / "DONE").is_file():
        return False
    for line in (entry / "dirs.txt").read_text(encoding="utf-8").splitlines():
        (work / line).mkdir(parents=True, exist_ok=True)
    files = entry / "files"
    for f in sorted(files.rglob("*")):
        if f.is_file():
            dest = work / f.relative_to(files)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
    os.utime(entry / "DONE")  # (the newest-used are the ones kept)
    return True


def store(base: Path, key: str, work: Path, pre: dict[str, str], pre_dirs: set[str]) -> None:
    """Keep what the step wrote: every file new or changed since `pre`, bar compiled binaries; the new directories."""
    entry = base / key
    if (entry / "DONE").is_file():
        return
    base.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=key + ".", dir=base))
    try:
        (tmp / "files").mkdir()
        for f in sorted(work.rglob("*")):
            if not f.is_file() or f.is_symlink():
                continue
            rel = f.relative_to(work).as_posix()
            if pre.get(rel) == hashlib.sha256(f.read_bytes()).hexdigest() or _is_binary_product(f):
                continue
            dest = tmp / "files" / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
        dirs = sorted(d.relative_to(work).as_posix() for d in work.rglob("*") if d.is_dir() and not d.is_symlink())
        (tmp / "dirs.txt").write_text("".join(d + "\n" for d in dirs if d not in pre_dirs), encoding="utf-8")
        (tmp / "DONE").write_text(key + "\n", encoding="utf-8")
        try:
            tmp.rename(entry)
        except OSError:  # another run stored the same step first
            shutil.rmtree(tmp, ignore_errors=True)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def dirs_of(work: Path) -> set[str]:
    return {d.relative_to(work).as_posix() for d in work.rglob("*") if d.is_dir() and not d.is_symlink()}


def prune(base: Path, max_bytes: int = KEEP_BYTES) -> int:
    """Drop the least recently used steps until the cache is within `max_bytes`; the number dropped."""
    entries = []
    for d in base.glob("*/DONE"):
        size = sum(f.stat().st_size for f in d.parent.rglob("*") if f.is_file())
        entries.append((d.stat().st_mtime, size, d.parent))
    total = sum(e[1] for e in entries)
    dropped = 0
    for _, size, d in sorted(entries):
        if total <= max_bytes:
            break
        shutil.rmtree(d, ignore_errors=True)
        total -= size
        dropped += 1
    return dropped


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="the COBOL step cache")
    ap.add_argument("cmd", choices=("stats", "prune", "version"))
    ap.add_argument("--max-gb", type=float, default=KEEP_BYTES / (1 << 30))
    args = ap.parse_args()
    base = root()
    if args.cmd == "version":
        print(harness_version())
        return 0
    if base is None or not base.is_dir():
        print("cobol step cache: empty or off")
        return 0
    if args.cmd == "prune":
        print(f"dropped {prune(base, int(args.max_gb * (1 << 30)))}")
    n = len(list(base.glob("*/DONE")))
    size = sum(f.stat().st_size for f in base.rglob("*") if f.is_file())
    print(f"cobol step cache {base}: {n} steps, {size / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
