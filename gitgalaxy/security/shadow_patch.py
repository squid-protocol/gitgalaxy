"""Shadow-patch detection (#8431): a file's content changed but its package version did not.

Compares, against a base git ref (a previous scan's commit or any ref), each tracked file's content and
the declared version of the nearest package manifest above it. A file whose content changed while that manifest's
version is unchanged is a shadow patch candidate. It is model-independent and is its own signal: it assigns no
threat class and no score. A changed file with a version bump, an unchanged file, a file with no manifest
and a manifest edit never flag.

Manifests read: package.json, pyproject.toml (`[project]`), Cargo.toml (`[package]`), a `version` key; a file
under any other manifest never flags.
"""

from __future__ import annotations

import json
import posixpath
import shutil
import subprocess
from collections.abc import Callable, Iterable

_GIT = shutil.which("git") or "git"
MANIFESTS = ("package.json", "pyproject.toml", "Cargo.toml")


def read_manifest_version(manifest_name: str, text: str) -> str | None:
    """The declared package version in a manifest's text, or None when absent or unparsable."""
    try:
        if manifest_name == "package.json":
            version = json.loads(text).get("version")
        else:
            import tomllib

            data = tomllib.loads(text)
            table = "package" if manifest_name == "Cargo.toml" else "project"
            version = (data.get(table) or {}).get("version")
    except (ValueError, AttributeError):
        return None
    return version if isinstance(version, str) and version else None


def nearest_manifest(rel_path: str, manifest_dirs: Iterable[str]) -> str | None:
    """The deepest directory in `manifest_dirs` ('' is the root) that contains `rel_path`."""
    best = None
    for d in manifest_dirs:
        inside = d == "" or rel_path.startswith(d + "/")
        if inside and (best is None or len(d) > len(best)):
            best = d
    return best


def find_shadow_patches(
    changed_files: Iterable[str],
    base_versions: dict[str, str | None],
    current_versions: dict[str, str | None],
) -> list[dict]:
    """Flag each changed file whose governing manifest version is the same at base and now.

    `changed_files`: files present at both base and now with different content.
    `base_versions` / `current_versions`: manifest directory ('' = root) -> declared version.
    """
    dirs = [d for d in current_versions if current_versions[d] is not None and d in base_versions]
    flagged = []
    for rel in sorted(changed_files):
        if posixpath.basename(rel) in MANIFESTS:
            continue
        d = nearest_manifest(rel, dirs)
        if d is None:
            continue
        if base_versions[d] is not None and base_versions[d] == current_versions[d]:
            flagged.append({"path": rel, "manifest_dir": d, "version": current_versions[d]})
    return flagged


def _git(repo: str, *args: str) -> str | None:
    try:
        return subprocess.check_output(  # noqa: S603
            [_GIT, "-c", "core.quotepath=off", *args], cwd=repo, text=True, stderr=subprocess.DEVNULL
        )
    except (subprocess.CalledProcessError, OSError):
        return None


def _read_working_tree(repo: str, rel: str) -> str | None:
    from gitgalaxy.core.source_text import read_source

    try:
        return read_source(posixpath.join(repo, rel)).text
    except OSError:
        return None


def detect_against_ref(repo: str, base_ref: str, read_current: Callable[[str], str | None] | None = None) -> list[dict]:
    """Shadow patches in the working tree of `repo` since `base_ref`; [] when the ref cannot be read."""
    diff = _git(repo, "diff", "--name-only", "--diff-filter=M", base_ref)
    tree = _git(repo, "ls-tree", "-r", "--name-only", base_ref)
    if diff is None or tree is None:
        return []
    base_versions: dict[str, str | None] = {}
    current_versions: dict[str, str | None] = {}
    for rel in tree.splitlines():
        name = posixpath.basename(rel)
        if name not in MANIFESTS:
            continue
        d = posixpath.dirname(rel)
        base_versions[d] = read_manifest_version(name, _git(repo, "show", f"{base_ref}:{rel}") or "")
        cur = read_current(rel) if read_current else _read_working_tree(repo, rel)
        current_versions[d] = read_manifest_version(name, cur) if cur is not None else None
    return find_shadow_patches(diff.splitlines(), base_versions, current_versions)
