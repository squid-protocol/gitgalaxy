"""The per-estate work an equivalence run repeats for every case of a corpus, done once and kept.

Two products depend only on the corpus and on the engine, never on the case:

  scan      the engine's scan of the corpus (galaxy_ir.scan_to_db): a CICS case's file facts come from it;
  refactor  the corpus refactored into a clean room (java_target_matrix.refactor, with its own engine scan): the
            generated project every case's port is laid over is generated from it (and det_port.py's estate).

Each is built once per key and copied into the run's work directory. The key is everything that decides the
product: the corpus clone's commit and its working-tree state (`git status --porcelain`), every file of the engine
(gitgalaxy/, read byte for byte, so an uncommitted change is a new key), the Python version, and the GITGALAXY_*
environment. A refactor's clean room records absolute paths of the corpus copy it was made from (the IR state
dumps' metadata.path, which the generator makes estate-relative); a copy has them rewritten to its own location, so
it is the clean room a fresh refactor in that directory writes, byte for byte apart from the dated directory name
(test_equivalence_cache.py checks this, and that the projects generated from both are identical).

The cache lives under ~/.cache/gitgalaxy-equivalence ($GITGALAXY_EQUIV_CACHE; "off" builds every time). A lock per
key lets parallel runs build it once; the newest KEEP entries of each kind are kept."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows: no flock; parallel runs may then build one entry twice (the same bytes)
    fcntl = None  # type: ignore[assignment]

TOOLS = Path(__file__).resolve().parent
REPO_ROOT = TOOLS.parent.parent
ENGINE = REPO_ROOT / "gitgalaxy"
CACHE_ENV = "GITGALAXY_EQUIV_CACHE"
KEEP = 8  # entries kept per kind (a key changes with every engine edit)

_ENGINE_HASH: str | None = None


def root() -> Path | None:
    """The cache directory, or None when caching is off."""
    value = os.environ.get(CACHE_ENV, "")
    if value.lower() == "off":
        return None
    return Path(value) if value else Path.home() / ".cache" / "gitgalaxy-equivalence"


def engine_hash() -> str:
    """Every file of the engine, path and bytes (bytecode caches aside)."""
    global _ENGINE_HASH
    if _ENGINE_HASH is None:
        h = hashlib.sha256()
        for f in sorted(p for p in ENGINE.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
            h.update(f.relative_to(ENGINE).as_posix().encode() + b"\0")
            h.update(hashlib.sha256(f.read_bytes()).digest())
        _ENGINE_HASH = h.hexdigest()
    return _ENGINE_HASH


def _corpus_state(corpus: Path) -> str:
    def git(*args: str) -> str:
        proc = subprocess.run(["git", "-C", str(corpus), *args], capture_output=True, text=True, check=False)  # noqa: S603, S607
        return proc.stdout if proc.returncode == 0 else f"(no git: {proc.returncode})"

    return git("rev-parse", "HEAD") + git("status", "--porcelain")


def key(kind: str, corpus: Path, extra: str = "") -> str:
    env = {k: v for k, v in sorted(os.environ.items()) if k.startswith("GITGALAXY_") and k != CACHE_ENV}
    parts = [kind, str(corpus.resolve()), _corpus_state(corpus), engine_hash(), sys.version, json.dumps(env), extra]
    return hashlib.sha256("\0".join(parts).encode()).hexdigest()[:24]


def _entry(kind: str, corpus: Path, build, extra: str = "") -> Path:  # noqa: ANN001
    """The cache entry of `kind` for the corpus, built by build(directory) under the key's lock when missing."""
    base = root() / kind  # type: ignore[operator]
    base.mkdir(parents=True, exist_ok=True)
    k = key(kind, corpus, extra)
    entry = base / f"{corpus.name}-{k}"
    with (base / f"{corpus.name}-{k}.lock").open("w") as fh:
        if fcntl is not None:
            fcntl.flock(fh, fcntl.LOCK_EX)
        if not (entry / "DONE").is_file():
            shutil.rmtree(entry, ignore_errors=True)
            entry.mkdir(parents=True)
            build(entry)
            (entry / "DONE").write_text(k + "\n", encoding="utf-8")
            _prune(base, corpus.name)
    os.utime(entry / "DONE")  # (the newest-used are the ones kept)
    return entry


def _prune(base: Path, corpus_name: str) -> None:
    done = sorted(base.glob(f"{corpus_name}-*/DONE"), key=lambda f: f.stat().st_mtime, reverse=True)
    for old in done[KEEP:]:
        shutil.rmtree(old.parent, ignore_errors=True)
        old.parent.with_name(old.parent.name + ".lock").unlink(missing_ok=True)


# ---- the scan ------------------------------------------------------------------------------------------------
def scan_db(corpus: Path, out_dir: Path) -> Path:
    """galaxy_ir.scan_to_db(corpus, out_dir), from the cache: the master DB, as one file (its journal folded in)."""
    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import scan_to_db

    if root() is None:
        return scan_to_db(corpus, out_dir)

    def build(entry: Path) -> None:
        db = scan_to_db(corpus, entry / "scan")
        con = sqlite3.connect(db)
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        con.execute("PRAGMA journal_mode=DELETE")  # one file: a copy is the whole database
        con.close()
        for side in db.parent.glob(db.name + "-*"):
            side.unlink()

    entry = _entry("scan", corpus, build)
    (db,) = (entry / "scan").glob("*_galaxy_master.db")
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(db, out_dir / db.name)
    return out_dir / db.name


# ---- the refactor ----------------------------------------------------------------------------------------------
_ROOT_FILE = "ROOT"  # the directory the cached refactor ran in (the absolute paths its clean room records)


def refactor(corpus: Path, work: Path, scan: bool = False) -> Path:
    """java_target_matrix.refactor(corpus, work, scan), from the cache: the corpus copy and its clean room laid in
    `work`, their recorded paths rewritten to it; the clean room's path."""
    import java_target_matrix as jtm

    if root() is None:
        return jtm.refactor(corpus, work, scan=scan)

    def build(entry: Path) -> None:
        made = entry / "made"
        made.mkdir()
        jtm.refactor(corpus, made, scan=scan)
        (entry / _ROOT_FILE).write_text(str(made), encoding="utf-8")

    entry = _entry("refactor", corpus, build, extra=f"scan={scan}")
    made = entry / "made"
    old = (entry / _ROOT_FILE).read_text(encoding="utf-8").encode()
    new = str(work).encode()
    work.mkdir(parents=True, exist_ok=True)
    copied = []
    for item in made.iterdir():
        dest = work / item.name
        if item.is_dir():
            shutil.copytree(item, dest, symlinks=True)
        else:
            shutil.copy2(item, dest)
        copied.append(dest)
    try:
        for dest in copied:
            for f in [dest] if dest.is_file() else (p for p in dest.rglob("*") if p.is_file() and not p.is_symlink()):
                data = f.read_bytes()
                if old not in data:
                    continue
                if b"\0" in data:  # a path inside a binary file (a database) cannot be rewritten in place
                    raise ValueError(f"{f} records the cached refactor's path")
                f.write_bytes(data.replace(old, new))
    except ValueError:  # never seen: refactor afresh rather than hand over a copy that is not the same
        for dest in copied:
            shutil.rmtree(dest) if dest.is_dir() else dest.unlink()
        return jtm.refactor(corpus, work, scan=scan)
    return next(work.glob(f"{corpus.name}_gitgalaxy_clean_*"))
