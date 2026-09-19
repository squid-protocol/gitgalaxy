"""
#3213: the pinned real mainframe corpora (tests/cobol_mainframe/corpora.json) as
commands -- fetch each at its pinned ref, scan it into a master DB cached per
engine state, and score it against its answer key.

    python tests/tools/mainframe_corpus.py list
    python tests/tools/mainframe_corpus.py fetch [NAME ...]
    python tests/tools/mainframe_corpus.py scan  [NAME ...] [--force]
    python tests/tools/mainframe_corpus.py score [NAME ...] [--md out.md]
    python tests/tools/mainframe_corpus.py path  NAME [--db]
    python tests/tools/mainframe_corpus.py excerpt [NAME ...]

NAME defaults to every corpus in the manifest. `path` prints the clone (or, with
--db, the cached master DB) for composing with the other harnesses:

    python tests/tools/refraction_differential.py "$(... path NAME)" --db "$(... path NAME --db)"

CACHE. Clones and scans live under `.mainframe_corpora/` at the root of this
checkout (gitignored; a dot-directory, so galaxyscope's self-scan never walks
it), or under $GITGALAXY_MAINFRAME_CORPORA. The layout is

    <cache>/<name>/                               shallow clone, detached at `ref`
    <cache>/_scans/<name>/<ref12>-<engine>/        <name>_galaxy_master.db

`<engine>` is this checkout's HEAD, plus a hash of the uncommitted diff under
gitgalaxy/ when there is one, so an engine edit never reuses a stale DB.

ENGINE. The scan runs `python -m gitgalaxy.galaxyscope` in a subprocess. This
tool puts its own checkout first on PYTHONPATH, so a worktree scans with the
worktree's engine and not whatever the venv's editable install points at.

EXCERPTS. `excerpt` copies each corpus's `excerpt.files` (plus its LICENSE and
NOTICE files) from the pinned clone into tests/cobol_mainframe/refraction_excerpts/
<name>/, the committed input of the CI snapshot test (refraction_snapshot.py).
Edit the list in the manifest, never the copied files.

The clones are read-only inputs. `cobol-refractor` writes its clean room next to
its target, so run it on a copy (tests/tools/refraction_snapshot.py does).
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "tests" / "cobol_mainframe" / "corpora.json"
EXCERPTS = REPO_ROOT / "tests" / "cobol_mainframe" / "refraction_excerpts"
PROVENANCE = "SOURCE.md"
CACHE_ENV = "GITGALAXY_MAINFRAME_CORPORA"

# In-process imports must see this checkout's engine (see ENGINE above; scan() does the same for its subprocess).
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def load_manifest(path: Path = MANIFEST) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))["corpora"]


def cache_root() -> Path:
    return Path(os.environ.get(CACHE_ENV) or REPO_ROOT / ".mainframe_corpora").resolve()


def select(names: list[str], corpora: Optional[list[dict[str, Any]]] = None) -> list[dict[str, Any]]:
    corpora = load_manifest() if corpora is None else corpora
    if not names:
        return corpora
    by_name = {c["name"]: c for c in corpora}
    unknown = [n for n in names if n not in by_name]
    if unknown:
        sys.exit(f"unknown corpus {', '.join(unknown)}; the manifest has {', '.join(by_name)}")
    return [by_name[n] for n in names]


def _git(*args: str, cwd: Path, check: bool = True) -> str:
    result = subprocess.run(  # noqa: S603 -- fixed "git" binary, argv only, no shell
        ["git", *args],  # noqa: S607
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {cwd}:\n{result.stderr.strip()}")
    return result.stdout.strip()


def clone_path(corpus: dict[str, Any]) -> Path:
    return cache_root() / corpus["name"]


def unsafe_path_parts(path: Path) -> list[str]:
    """Components of `path` that galaxyscope treats as ignored directories. A corpus
    under one (e.g. a `tmp` scratch dir) silently loses documentation-coverage
    scoring for every file; see crucible_check.py's _check_unsafe_corpus_path."""
    from gitgalaxy.standards.gitgalaxy_config import APERTURE_CONFIG

    ignored = {d.lower() for d in APERTURE_CONFIG["IGNORED_DIRECTORIES"]}
    return [p for p in path.parts if p.lower() in ignored]


def fetch(corpus: dict[str, Any], force: bool = False) -> Path:
    """Shallow-clones `corpus` at its pinned ref (a no-op when already there) and
    returns the clone. Refuses to discard local edits unless `force`."""
    dest = clone_path(corpus)
    dest.mkdir(parents=True, exist_ok=True)
    if not (dest / ".git").exists():
        _git("init", "-q", cwd=dest)
        _git("remote", "add", "origin", corpus["url"], cwd=dest)
    dirty = _git("status", "--porcelain", cwd=dest, check=False)
    if dirty and _git("rev-parse", "HEAD", cwd=dest, check=False):
        if not force:
            sys.exit(f"{dest} has local changes; re-run fetch with --force to discard them:\n{dirty}")
        _git("reset", "-q", "--hard", cwd=dest)
        _git("clean", "-qfdx", cwd=dest)
    if _git("rev-parse", "HEAD", cwd=dest, check=False) != corpus["ref"]:
        # GitHub serves any reachable commit by SHA, so no branch walk is needed.
        _git("fetch", "-q", "--depth", "1", "origin", corpus["ref"], cwd=dest)
        _git("checkout", "-q", "--detach", "FETCH_HEAD", cwd=dest)
    head = _git("rev-parse", "HEAD", cwd=dest)
    if head != corpus["ref"]:
        raise RuntimeError(f"{dest} is at {head}, not the pinned {corpus['ref']}")
    return dest


def require_clone(corpus: dict[str, Any]) -> Path:
    dest = clone_path(corpus)
    head = _git("rev-parse", "HEAD", cwd=dest, check=False) if (dest / ".git").exists() else ""
    if head != corpus["ref"]:
        sys.exit(f"{corpus['name']} is not fetched at its pinned ref; run: mainframe_corpus.py fetch {corpus['name']}")
    return dest


def engine_key() -> str:
    """This checkout's HEAD, suffixed with a hash of any uncommitted diff under gitgalaxy/."""
    head = _git("rev-parse", "--short=12", "HEAD", cwd=REPO_ROOT)
    diff = _git("diff", "HEAD", "--", "gitgalaxy", cwd=REPO_ROOT)
    untracked = _git("ls-files", "--others", "--exclude-standard", "--", "gitgalaxy", cwd=REPO_ROOT)
    if not diff and not untracked:
        return head
    h = hashlib.sha256(diff.encode())
    for rel in sorted(untracked.splitlines()):
        h.update(rel.encode())
        h.update((REPO_ROOT / rel).read_bytes())
    return f"{head}-dirty{h.hexdigest()[:8]}"


def db_path(corpus: dict[str, Any], engine: Optional[str] = None) -> Path:
    scan_dir = cache_root() / "_scans" / corpus["name"] / f"{corpus['ref'][:12]}-{engine or engine_key()}"
    return scan_dir / f"{corpus['name']}_galaxy_master.db"


def scan(corpus: dict[str, Any], force: bool = False) -> Path:
    """The corpus's master DB for the current engine state, scanning only on a cache miss."""
    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import scan_to_db

    repo = require_clone(corpus)
    db = db_path(corpus)
    if db.is_file() and not force:
        return db
    if db.exists():
        db.unlink()
    saved = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = os.pathsep.join(p for p in (str(REPO_ROOT), saved) if p)
    try:
        written = scan_to_db(repo, db.parent)
    finally:
        if saved is None:
            os.environ.pop("PYTHONPATH")
        else:
            os.environ["PYTHONPATH"] = saved
    if written != db:
        raise RuntimeError(f"scan wrote {written}, expected {db}")
    return db


def score(corpus: dict[str, Any], force_scan: bool = False) -> tuple[dict[str, Any], str]:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from cobol_answer_key import score as score_key

    if not corpus.get("answer_key"):
        raise ValueError(f"{corpus['name']} has no answer key")
    key = json.loads((REPO_ROOT / corpus["answer_key"]).read_text(encoding="utf-8"))
    if key["ref"] != corpus["ref"]:
        raise ValueError(
            f"{corpus['answer_key']} was verified at {key['ref'][:12]}, the manifest pins {corpus['ref'][:12]}"
        )
    return score_key(require_clone(corpus), key, scan(corpus, force=force_scan))


def excerpt(corpus: dict[str, Any], dest_root: Path = EXCERPTS) -> Path:
    """Rewrites `<dest_root>/<name>/` from the pinned clone: the manifest's excerpt
    files at their corpus paths, the corpus's LICENSE/NOTICE files, and a provenance note."""
    repo = require_clone(corpus)
    dest = dest_root / corpus["name"]
    if dest.exists():
        shutil.rmtree(dest)
    legal = sorted(p.name for p in repo.iterdir() if p.is_file() and p.name.upper().startswith(("LICENSE", "NOTICE")))
    for rel in [*corpus["excerpt"]["files"], *legal]:
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repo / rel, target)
    # write_bytes: LF on every OS (write_text's newline= needs Python 3.10)
    (dest / PROVENANCE).write_bytes(
        f"# {corpus['name']} (excerpt)\n\n"
        f"{len(corpus['excerpt']['files'])} files from <{corpus['url']}> at `{corpus['ref']}`, "
        f"unmodified, under that project's license ({corpus['license']}; {', '.join(legal)} copied alongside).\n\n"
        f"{corpus['excerpt']['why']}\n\n"
        "Regenerate with `python tests/tools/mainframe_corpus.py excerpt "
        f"{corpus['name']}` after editing `excerpt.files` in tests/cobol_mainframe/corpora.json.\n".encode()
    )
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    f = sub.add_parser("fetch")
    f.add_argument("names", nargs="*")
    f.add_argument("--force", action="store_true", help="discard local changes in a clone")
    s = sub.add_parser("scan")
    s.add_argument("names", nargs="*")
    s.add_argument("--force", action="store_true", help="rescan even when a cached DB exists")
    sc = sub.add_parser("score")
    sc.add_argument("names", nargs="*")
    sc.add_argument("--force-scan", action="store_true")
    sc.add_argument("--md", type=Path, help="write the combined markdown here")
    e = sub.add_parser("excerpt")
    e.add_argument("names", nargs="*")
    p = sub.add_parser("path")
    p.add_argument("name")
    p.add_argument("--db", action="store_true", help="print the cached master DB instead of the clone")
    args = ap.parse_args()

    if args.cmd == "list":
        for c in load_manifest():
            key = c["answer_key"] or "no answer key"
            print(f"{c['name']:<40} {c['ref'][:12]} ({c['branch']})  {','.join(c['languages'])}  [{key}]")
        return 0

    if args.cmd == "path":
        corpus = select([args.name])[0]
        print(db_path(corpus) if args.db else clone_path(corpus))
        return 0

    bad = unsafe_path_parts(cache_root())
    if bad:
        print(f"⚠️  {cache_root()} has ignored-directory component(s) {bad}; set {CACHE_ENV} elsewhere.")

    if args.cmd == "fetch":
        for c in select(args.names):
            print(f"{c['name']}: {fetch(c, force=args.force)} @ {c['ref'][:12]}")
        return 0

    if args.cmd == "excerpt":
        for c in select(args.names):
            print(f"{c['name']}: {excerpt(c).relative_to(REPO_ROOT)}")
        return 0

    if args.cmd == "scan":
        for c in select(args.names):
            print(f"{c['name']}: {scan(c, force=args.force)}")
        return 0

    chunks = []
    for c in select(args.names):
        if not c.get("answer_key"):
            print(f"{c['name']}: no answer key, skipped")
            continue
        _, md = score(c, force_scan=args.force_scan)
        chunks.append(md)
        print(md)
    if args.md:
        args.md.write_text("\n".join(chunks), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
