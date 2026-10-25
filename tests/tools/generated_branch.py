#!/usr/bin/env python3
"""The `generated` data branch (#4847, the pattern of #4827's evidence-pages.yml): read and write bot output there.

Bot-written history and chart files used to be committed to main through auto-merged PRs (40 of 322 main commits in
a week, each one queuing every open PR behind it). Their writers now publish to the `generated` branch instead and
main never moves for them:

    fetch    PATH...   copy each PATH from generated into the working tree (a CSV the writer appends to starts from
                       the last published batch). A path generated does not have yet is left alone, so the copy
                       committed on main is the seed and the fallback.
    publish  PATH...   commit those working-tree files (a directory: every file beneath it) to generated, on top of its tip, and push it. Nothing is
                       committed when no file differs from the tip. Writers own disjoint paths, so a push rejected
                       because another writer got in first is retried on the new tip.
    push-head          push the checked-out commit (a writer that builds its own commit on a generated checkout) to generated;
                       a rejected push is fetched and rebased onto the new tip, then retried (#6563).
    show     PATH      print PATH as published on generated, else the committed copy (what a reader should use).

Plumbing only (a scratch index, `commit-tree`, `push <sha>:refs/heads/generated`): the working tree, HEAD and the
checked-out branch are never touched. The push uses whatever credentials the checkout carries.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BRANCH = "generated"
STAMP_DIR = ".generated_from"  # one small file per writer; GENERATED_FROM itself belongs to evidence-pages.yml
_IDENT = {
    "GIT_AUTHOR_NAME": "github-actions[bot]",
    "GIT_AUTHOR_EMAIL": "41898282+github-actions[bot]@users.noreply.github.com",
    "GIT_COMMITTER_NAME": "github-actions[bot]",
    "GIT_COMMITTER_EMAIL": "41898282+github-actions[bot]@users.noreply.github.com",
}


def _git(root: Path, *args: str, env: dict[str, str] | None = None, check: bool = True) -> str:
    p = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, env={**os.environ, **(env or {})}, check=False
    )
    if check and p.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed ({p.returncode}): {p.stderr.strip()}")
    return p.stdout.strip() if p.returncode == 0 else ""


RETRY_DELAYS = (1.0, 3.0)  # #5312: seconds before each retry of a network git call; a test sets it to ()


def _git_net(root: Path, *args: str) -> str:
    """`_git` for a call that crosses the network: one transient failure (a runner's dropped connection) is retried."""
    for delay in RETRY_DELAYS:
        try:
            return _git(root, *args)
        except RuntimeError:
            time.sleep(delay)
    return _git(root, *args)


def fetch_tip(root: Path = REPO_ROOT, remote: str = "origin") -> str | None:
    """Fetch generated's tip and return its sha, or None when the branch does not exist (yet)."""
    if not _git_net(root, "ls-remote", remote, f"refs/heads/{BRANCH}"):
        return None
    _git_net(root, "fetch", "--quiet", "--depth", "1", remote, BRANCH)
    return _git(root, "rev-parse", "FETCH_HEAD")


def read_at(tip: str, relpath: str, root: Path = REPO_ROOT) -> bytes | None:
    """The bytes of relpath at the fetched `tip` commit, or None when the file is not there."""
    p = subprocess.run(["git", "show", f"{tip}:{relpath}"], cwd=root, capture_output=True, check=False)
    return p.stdout if p.returncode == 0 else None


def read_published(relpath: str, root: Path = REPO_ROOT, remote: str = "origin") -> bytes | None:
    """The bytes of relpath on generated's tip, or None when the branch or the file is not there."""
    tip = fetch_tip(root, remote)
    return None if tip is None else read_at(tip, relpath, root)


def fetch(paths: list[str], root: Path = REPO_ROOT, remote: str = "origin") -> list[str]:
    """Copy each path from generated into the working tree; return the ones restored."""
    restored = []
    for rel in paths:
        data = read_published(rel, root, remote)
        if data is None:
            continue
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        restored.append(rel)
    return restored


def show(relpath: str, root: Path = REPO_ROOT, remote: str = "origin") -> bytes:
    """Published copy, else the committed one: the clean fallback for any reader of a moved file."""
    data = read_published(relpath, root, remote)
    return data if data is not None else (root / relpath).read_bytes()


def _build_commit(root: Path, tip: str | None, paths: list[str], message: str, stamp: str | None) -> str | None:
    """A commit on `tip` carrying `paths` from the working tree, or None when nothing differs from the tip."""
    with tempfile.TemporaryDirectory() as td:
        env = {**_IDENT, "GIT_INDEX_FILE": str(Path(td) / "index")}
        if tip:
            _git(root, "read-tree", tip, env=env)
        for rel in paths:
            blob = _git(root, "hash-object", "-w", "--", rel, env=env)
            _git(root, "update-index", "--add", "--cacheinfo", f"100644,{blob},{rel}", env=env)
        tree = _git(root, "write-tree", env=env)
        if tip and tree == _git(root, "rev-parse", f"{tip}^{{tree}}"):
            return None
        if stamp:
            sha = os.environ.get("GITHUB_SHA") or _git(root, "rev-parse", "HEAD")
            note = Path(td) / "stamp"
            note.write_text(f"Generated output only, never edit by hand. Source: main @ {sha}\nWriter: {stamp}\n")
            blob = _git(root, "hash-object", "-w", "--", str(note), env=env)
            _git(root, "update-index", "--add", "--cacheinfo", f"100644,{blob},{STAMP_DIR}/{stamp}.txt", env=env)
            tree = _git(root, "write-tree", env=env)
        parent = ["-p", tip] if tip else []
        return _git(root, "commit-tree", tree, *parent, "-m", message, env=env)


def expand(paths: list[str], root: Path = REPO_ROOT) -> list[str]:
    """Each directory among `paths` becomes the files beneath it (sorted, repo-relative); a file stays as given."""
    out: list[str] = []
    for rel in paths:
        d = root / rel
        if d.is_dir():
            out.extend(sorted(f.relative_to(root).as_posix() for f in d.rglob("*") if f.is_file()))
        else:
            out.append(rel)
    return out


def publish(
    paths: list[str],
    message: str,
    root: Path = REPO_ROOT,
    remote: str = "origin",
    stamp: str | None = None,
    retries: int = 5,
) -> str | None:
    """Push `paths` to generated. Returns the pushed commit sha, or None when nothing changed."""
    paths = expand(paths, root)
    missing = [p for p in paths if not (root / p).is_file()]
    if missing:
        raise FileNotFoundError(f"cannot publish, not in the working tree: {', '.join(missing)}")
    for _ in range(retries):
        tip = fetch_tip(root, remote)
        commit = _build_commit(root, tip, paths, message, stamp)
        if commit is None:
            return None
        pushed = subprocess.run(
            ["git", "push", "--quiet", remote, f"{commit}:refs/heads/{BRANCH}"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if pushed.returncode == 0:
            return commit
        print(f"push to {BRANCH} rejected ({pushed.stderr.strip()[:200]}); retrying on the new tip", file=sys.stderr)
    raise RuntimeError(f"could not push to {BRANCH} after {retries} attempts")


def push_head(root: Path = REPO_ROOT, remote: str = "origin", retries: int = 5) -> str:
    """#6563: push root's HEAD to generated. A push rejected because another writer got in first is rebased onto the
    new tip and retried; a rebase conflict (same path edited by both) is aborted and raised."""
    for attempt in range(retries):
        pushed = subprocess.run(
            ["git", "push", "--quiet", remote, f"HEAD:refs/heads/{BRANCH}"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if pushed.returncode == 0:
            return _git(root, "rev-parse", "HEAD")
        print(f"push to {BRANCH} rejected ({pushed.stderr.strip()[:200]}); rebasing onto the new tip", file=sys.stderr)
        if attempt < retries - 1:
            _git_net(root, "fetch", "--quiet", remote, BRANCH)
            rebased = subprocess.run(
                ["git", "rebase", "FETCH_HEAD"],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
                env={**os.environ, **_IDENT},
            )
            if rebased.returncode:
                _git(root, "rebase", "--abort", check=False)
                raise RuntimeError(f"rebase onto {BRANCH} conflicts: {rebased.stderr.strip()[:200]}")
    raise RuntimeError(f"could not push to {BRANCH} after {retries} attempts")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="restore paths from generated into the working tree")
    f.add_argument("paths", nargs="+")
    s = sub.add_parser("show", help="print a path as published, else as committed")
    s.add_argument("path")
    p = sub.add_parser("publish", help="commit working-tree paths to generated and push")
    p.add_argument("paths", nargs="+")
    p.add_argument("--message", required=True)
    p.add_argument("--stamp", help="writer name; records the source main sha in .generated_from/<name>.txt")
    h = sub.add_parser("push-head", help="push the checked-out commit to generated, rebasing on a rejected push")
    h.add_argument("--root", default=str(REPO_ROOT), help="the generated checkout")
    a = ap.parse_args(argv)
    if a.cmd == "push-head":
        print(f"pushed {push_head(Path(a.root))} to {BRANCH}")
    elif a.cmd == "fetch":
        got = fetch(a.paths)
        print(f"restored from {BRANCH}: {', '.join(got) or 'nothing (seeding from the committed copy)'}")
    elif a.cmd == "show":
        sys.stdout.buffer.write(show(a.path))
    else:
        sha = publish(a.paths, a.message, stamp=a.stamp)
        print(f"published {len(a.paths)} file(s) to {BRANCH}: {sha}" if sha else f"{BRANCH} already up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
