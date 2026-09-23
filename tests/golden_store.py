#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""
Split on-disk layout for the golden-master fixtures (#3384).

The two golden masters used to be single ~88 MB JSON files. Every fact-channel
PR adds keys to the same per-file region ("10. Mainframe System Facts"), so
any two of them conflicted on the fixture even when their keys never touched.
This module stores each fixture as a directory of small, deterministic files
instead, laid out so that ADDING a key -- a new top-level report section, a new
global-summary entry, a new per-file section, or a new sub-key inside a
per-file section (a new fact channel, a new structural signal) -- only ever
creates a NEW file. Two PRs that each add a different key therefore touch
disjoint paths and merge without conflicts.

Every reader and writer goes through `load()` / `write()`, and `load()`
reassembles exactly the dict the monolithic file used to hold, so
golden_diff.py / crucible_check.py / bless_scope.py semantics are unchanged.

LAYOUT (paths relative to the fixture directory; <x> is slug(x))

    _layout.json                       format marker + version (never changes)
    <K>.json                           top-level key K whose value is not a
                                       non-empty dict (e.g. "Audit Protocol")
    <K>/<k>.json                       one file per sub-key k of a top-level
                                       dict section K (e.g. "2. Global
                                       Ecosystem Summary"/"summary")
    <P>/_groups.json                   P = "6. Parsed Files (Scanned
                                       Artifacts)": every directory group's own
                                       keys, plus its sorted file list
    <P>/files/<S>/<k>.json             per-file section S, sub-key k, for every
                                       file that has it: {group: {path: value}}
    <P>/files/<S>/_values.json         per-file section S for files whose value
                                       is not a non-empty dict (a list, a
                                       string, or {}), stored whole

Each file embeds its own logical path ("path": [...]), so the directory can be
reassembled without trusting file names; the file name is only a
deterministic, filesystem-safe slug of that path. Output is canonical:
sort_keys, indent=2, UTF-8, trailing newline -- re-writing unchanged data is
byte-identical.

STRICTNESS: `load()` fails loudly (GoldenStoreError) on a missing `_layout.json`,
an unknown format version, a stray or misplaced file (anything whose location
isn't exactly where `write()` would put its content), a duplicate logical path,
or a per-file value for a file the `_groups.json` index doesn't list. A MISSING
section file is not silently tolerated either: the reassembled dict lacks that
key, and golden_diff.deep_compare reports it against a fresh scan like any
other drift.

CLI
    python tests/golden_store.py split  <monolith.json> <fixture-dir>
    python tests/golden_store.py join   <fixture-dir>   <out.json>
    python tests/golden_store.py export --rev HEAD <fixture-dir> <out.json>
    python tests/golden_store.py check  <fixture-dir>   # canonical-bytes check
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path, PurePosixPath
from typing import Any

FORMAT_NAME = "gitgalaxy-golden-master-split"
FORMAT_VERSION = 1
LAYOUT_FILE = "_layout.json"
GROUPS_FILE = "_groups.json"
VALUES_FILE = "_values.json"
FILES_DIR = "files"

# The one top-level section that is split per file-section instead of per key.
PARSED_FILES_KEY = "6. Parsed Files (Scanned Artifacts)"
GROUP_FILES_KEY = "Files"

# Repo-relative fixture directories. Every consumer should use these rather than
# spelling the paths out again.
FULL_PRECISION = "tests/golden_master_audit"
ZERO_DEPENDENCY = "tests/golden_master_zero_dep_audit"
GOLDEN_MASTERS = (FULL_PRECISION, ZERO_DEPENDENCY)

_SLUG_MAX = 64


class GoldenStoreError(ValueError):
    """The fixture directory is malformed -- never silently skipped."""


# --------------------------------------------------------------------------
# naming
# --------------------------------------------------------------------------


def slug(name: str) -> str:
    """Lowercase ASCII [a-z0-9_] slug. Never starts with '_' (reserved for the
    layout's own index files) and never empty."""
    s = re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_")[:_SLUG_MAX].rstrip("_")
    return s or "key"


def _unique_names(keys: Iterable[str]) -> dict[str, str]:
    """key -> file stem, deterministic. Keys whose slugs collide (or are
    lossy duplicates) all get an 8-hex suffix of their exact name's hash."""
    keys = sorted(keys)
    by_slug: dict[str, list] = {}
    for k in keys:
        by_slug.setdefault(slug(k), []).append(k)
    out = {}
    for s, members in by_slug.items():
        if len(members) == 1:
            out[members[0]] = s
        else:
            for k in members:
                out[k] = f"{s}_{hashlib.sha1(k.encode('utf-8')).hexdigest()[:8]}"
    return out


def is_golden_master_path(path: str) -> bool:
    """True for a repo-relative path inside (or equal to) a golden-master
    fixture -- including the pre-#3384 monolithic `<dir>.json` names."""
    p = path.replace("\\", "/").strip("/")
    for d in GOLDEN_MASTERS:
        if p == d or p == d + ".json" or p.startswith(d + "/"):
            return True
    return False


# --------------------------------------------------------------------------
# dict <-> {relpath: object}
# --------------------------------------------------------------------------


def _is_nonempty_dict(v: Any) -> bool:
    return isinstance(v, dict) and bool(v)


def _parsed_files_splittable(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    for group in value.values():
        if not isinstance(group, dict) or not isinstance(group.get(GROUP_FILES_KEY), dict):
            return False
        if not all(isinstance(f, dict) for f in group[GROUP_FILES_KEY].values()):
            return False
    return True


def split(data: Mapping[str, Any]) -> dict[str, Any]:
    """Pure: the monolithic dict -> {posix relpath: JSON-able object}."""
    if not isinstance(data, dict):
        raise GoldenStoreError(f"golden master must be a JSON object, got {type(data).__name__}")
    files: dict[str, Any] = {LAYOUT_FILE: {"format": FORMAT_NAME, "version": FORMAT_VERSION}}
    top_names = _unique_names(data.keys())
    for key, value in data.items():
        tname = top_names[key]
        if key == PARSED_FILES_KEY and _parsed_files_splittable(value):
            files.update(_split_parsed_files(key, tname, value))
        elif _is_nonempty_dict(value):
            sub_names = _unique_names(value.keys())
            for sub, sub_value in value.items():
                files[f"{tname}/{sub_names[sub]}.json"] = {"path": [key, sub], "value": sub_value}
        else:
            files[f"{tname}.json"] = {"path": [key], "value": value}
    return files


def _split_parsed_files(key: str, tname: str, value: dict[str, Any]) -> dict[str, Any]:
    files: dict[str, Any] = {}
    groups_index: dict[str, Any] = {}
    # section -> sub-key -> group -> path -> value ; section -> group -> path -> whole value
    columns: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    whole: dict[str, dict[str, dict[str, Any]]] = {}
    for group, gval in value.items():
        entry = {k: v for k, v in gval.items() if k != GROUP_FILES_KEY}
        entry[GROUP_FILES_KEY] = sorted(gval[GROUP_FILES_KEY])
        groups_index[group] = entry
        for fpath, fentry in gval[GROUP_FILES_KEY].items():
            for section, svalue in fentry.items():
                if _is_nonempty_dict(svalue):
                    cols = columns.setdefault(section, {})
                    for sub, sub_value in svalue.items():
                        cols.setdefault(sub, {}).setdefault(group, {})[fpath] = sub_value
                else:
                    whole.setdefault(section, {}).setdefault(group, {})[fpath] = svalue
    files[f"{tname}/{GROUPS_FILE}"] = {"path": [key], "groups": groups_index}
    section_names = _unique_names(set(columns) | set(whole))
    for section, sname in section_names.items():
        base = f"{tname}/{FILES_DIR}/{sname}"
        if section in whole:
            files[f"{base}/{VALUES_FILE}"] = {"path": [key, section], "groups": whole[section]}
        if section in columns:
            sub_names = _unique_names(columns[section].keys())
            for sub, per_group in columns[section].items():
                files[f"{base}/{sub_names[sub]}.json"] = {"path": [key, section, sub], "groups": per_group}
    return files


def _need(obj: Any, rel: str, *fields: str) -> None:
    if not isinstance(obj, dict) or any(f not in obj for f in fields):
        raise GoldenStoreError(f"{rel}: malformed golden-master part (expected fields {list(fields)})")


def assemble(files: Mapping[str, Any]) -> dict[str, Any]:
    """{relpath: parsed object} -> the monolithic dict. Strict: see module doc."""
    layout = files.get(LAYOUT_FILE)
    if layout is None:
        raise GoldenStoreError(f"missing {LAYOUT_FILE} -- not a split golden-master directory")
    if layout != {"format": FORMAT_NAME, "version": FORMAT_VERSION}:
        raise GoldenStoreError(f"{LAYOUT_FILE}: unsupported layout {layout!r}")

    data: dict[str, Any] = {}
    seen: dict[tuple, str] = {}
    parsed_groups: dict[str, dict[str, Any]] = {}
    parsed_parts: list = []

    def claim(path: tuple, rel: str) -> None:
        if path in seen:
            raise GoldenStoreError(f"duplicate logical path {list(path)} in {seen[path]} and {rel}")
        seen[path] = rel

    for rel in sorted(files):
        if rel == LAYOUT_FILE:
            continue
        obj = files[rel]
        _need(obj, rel, "path")
        path = obj["path"]
        if not isinstance(path, list) or not path or not all(isinstance(p, str) for p in path):
            raise GoldenStoreError(f"{rel}: 'path' must be a non-empty list of strings")
        if "groups" in obj:
            if path[0] != PARSED_FILES_KEY or len(path) > 3:
                raise GoldenStoreError(f"{rel}: per-file part outside {PARSED_FILES_KEY!r}")
            if len(path) == 1:
                claim(tuple(path), rel)
                parsed_groups[rel] = obj["groups"]
            else:
                parsed_parts.append((rel, path, obj["groups"]))
            continue
        _need(obj, rel, "value")
        if len(path) == 1:
            claim(tuple(path), rel)
            if path[0] in data:
                raise GoldenStoreError(f"{rel}: top-level key {path[0]!r} also stored as a directory")
            data[path[0]] = obj["value"]
        elif len(path) == 2:
            claim(tuple(path), rel)
            section = data.setdefault(path[0], {})
            if not isinstance(section, dict) or (path[0],) in seen:
                raise GoldenStoreError(f"{rel}: top-level key {path[0]!r} also stored as a single file")
            section[path[1]] = obj["value"]
        else:
            raise GoldenStoreError(f"{rel}: 'path' too deep for a top-level part: {path}")

    if parsed_parts and not parsed_groups:
        raise GoldenStoreError(f"per-file parts present but {PARSED_FILES_KEY!r}/{GROUPS_FILE} is missing")
    if parsed_groups:
        (groups,) = parsed_groups.values()
        if not isinstance(groups, dict):
            raise GoldenStoreError(f"{GROUPS_FILE}: 'groups' must be an object")
        pf: dict[str, Any] = {}
        for group, entry in groups.items():
            if not isinstance(entry, dict) or not isinstance(entry.get(GROUP_FILES_KEY), list):
                raise GoldenStoreError(f"{GROUPS_FILE}: group {group!r} has no {GROUP_FILES_KEY!r} list")
            g = {k: v for k, v in entry.items() if k != GROUP_FILES_KEY}
            g[GROUP_FILES_KEY] = {fp: {} for fp in entry[GROUP_FILES_KEY]}
            pf[group] = g
        for rel, path, per_group in parsed_parts:
            claim(tuple(path), rel)
            if not isinstance(per_group, dict):
                raise GoldenStoreError(f"{rel}: 'groups' must be an object")
            section = path[1]
            for group, per_file in per_group.items():
                if group not in pf:
                    raise GoldenStoreError(f"{rel}: group {group!r} is not in {GROUPS_FILE}")
                for fp, value in per_file.items():
                    entry = pf[group][GROUP_FILES_KEY].get(fp)
                    if entry is None:
                        raise GoldenStoreError(f"{rel}: file {fp!r} is not listed under group {group!r}")
                    if len(path) == 2:
                        if section in entry:
                            raise GoldenStoreError(f"{rel}: {fp!r} section {section!r} stored twice")
                        entry[section] = value
                    else:
                        target = entry.setdefault(section, {})
                        if not isinstance(target, dict) or path[2] in target:
                            raise GoldenStoreError(f"{rel}: {fp!r} section {section!r} stored twice")
                        target[path[2]] = value
        data[PARSED_FILES_KEY] = pf

    # Placement check: every file must sit exactly where write() would put
    # its content, and nothing else may be in the directory.
    expected = set(split(data))
    actual = set(files)
    if expected != actual:
        stray = sorted(actual - expected)
        missing = sorted(expected - actual)
        raise GoldenStoreError(
            "golden-master directory is not in canonical layout (hand-edited or partially merged?): "
            f"unexpected={stray[:10]} missing={missing[:10]} -- regenerate with "
            "`python tests/tools/crucible_check.py --update --yes`"
        )
    return data


# --------------------------------------------------------------------------
# serialization + filesystem
# --------------------------------------------------------------------------


def dumps(obj: Any) -> bytes:
    """Canonical bytes: sorted keys, 2-space indent, UTF-8, trailing newline."""
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def render(data: Mapping[str, Any]) -> dict[str, bytes]:
    return {rel: dumps(obj) for rel, obj in split(data).items()}


def _read_dir(root: Path) -> dict[str, Any]:
    files: dict[str, Any] = {}
    for p in sorted(root.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(root).as_posix()
        if not rel.endswith(".json"):
            raise GoldenStoreError(f"{root}: stray non-JSON file {rel!r} in golden-master directory")
        try:
            files[rel] = json.loads(p.read_bytes().decode("utf-8"))
        except json.JSONDecodeError as e:
            raise GoldenStoreError(f"{root / rel}: invalid JSON ({e})") from e
    return files


def is_split_dir(path: str | os.PathLike) -> bool:
    return Path(path).is_dir()


def exists(path: str | os.PathLike) -> bool:
    return Path(path).exists()


def load(path: str | os.PathLike) -> dict[str, Any]:
    """A split fixture directory -> the monolithic dict; a plain JSON file (a
    fresh scan's data_galaxy_audit.json, or a pre-#3384 monolith) is loaded
    as-is."""
    p = Path(path)
    if p.is_dir():
        return assemble(_read_dir(p))
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def write(data: Mapping[str, Any], path: str | os.PathLike) -> None:
    """Replace the fixture directory at `path` with the split form of `data`.
    Built in a sibling temp dir first, so a failure never leaves a half-written
    fixture; stale files from a previous layout are removed."""
    root = Path(path)
    rendered = render(data)
    root.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f".{root.name}.", dir=root.parent))
    try:
        for rel, blob in rendered.items():
            target = tmp / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(blob)
        backup = None
        if root.exists():
            backup = root.parent / f".{root.name}.old-{os.getpid()}"
            root.rename(backup)
        tmp.rename(root)
        if backup is not None:
            shutil.rmtree(backup)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def check_canonical(path: str | os.PathLike) -> list[str]:
    """Paths (relative) whose bytes differ from what write() would produce.
    Empty list == canonical. Raises GoldenStoreError if unloadable."""
    root = Path(path)
    rendered = render(load(root))
    bad = []
    for rel, blob in rendered.items():
        if (root / rel).read_bytes() != blob:
            bad.append(rel)
    return bad


# --------------------------------------------------------------------------
# git
# --------------------------------------------------------------------------


def load_from_git(rev: str, rel: str, repo: str | os.PathLike | None = None) -> dict[str, Any] | None:
    """The fixture at `rev` (repo-relative `rel`), or None if absent there.

    Accepts the split directory name or the legacy `<dir>.json`; if `rev`
    predates #3384 (only the monolith exists), the monolith is loaded instead,
    so diffing across the migration commit keeps working."""
    cwd = str(repo) if repo is not None else None
    rel = rel.replace("\\", "/").strip("/")
    dir_rel = rel[: -len(".json")] if rel.endswith(".json") else rel
    ls = subprocess.run(
        ["git", "ls-tree", "-r", "-z", "--full-tree", rev, "--", dir_rel + "/"],
        cwd=cwd,
        capture_output=True,
        check=False,
    )
    if ls.returncode != 0:
        raise GoldenStoreError(f"git ls-tree {rev} failed: {ls.stderr.decode(errors='replace')}")
    entries = []
    for rec in ls.stdout.split(b"\0"):
        if not rec:
            continue
        meta, name = rec.split(b"\t", 1)
        _mode, kind, sha = meta.split()
        if kind == b"blob":
            entries.append((name.decode("utf-8"), sha.decode()))
    if entries:
        blobs = _cat_blobs([sha for _, sha in entries], cwd)
        files: dict[str, Any] = {}
        for name, sha in entries:
            sub = str(PurePosixPath(name).relative_to(dir_rel))
            if not sub.endswith(".json"):
                raise GoldenStoreError(f"{rev}:{name}: stray non-JSON file in golden-master directory")
            files[sub] = json.loads(blobs[sha].decode("utf-8"))
        return assemble(files)
    legacy = subprocess.run(["git", "show", f"{rev}:{dir_rel}.json"], cwd=cwd, capture_output=True, check=False)
    if legacy.returncode == 0:
        return json.loads(legacy.stdout.decode("utf-8"))
    return None


def _cat_blobs(shas: list, cwd: str | None) -> dict[str, bytes]:
    proc = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=cwd,
        input=("\n".join(shas) + "\n").encode(),
        capture_output=True,
        check=True,
    )
    out: dict[str, bytes] = {}
    buf = io.BytesIO(proc.stdout)
    for _ in shas:
        header = buf.readline().split()
        sha, size = header[0].decode(), int(header[2])
        out[sha] = buf.read(size)
        buf.read(1)  # trailing LF
    return out


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _write_monolith(data: dict[str, Any], out: str) -> None:
    Path(out).write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("split", help="monolithic JSON -> split fixture directory")
    s.add_argument("src")
    s.add_argument("dst")
    j = sub.add_parser("join", help="split fixture directory -> monolithic JSON")
    j.add_argument("src")
    j.add_argument("dst")
    e = sub.add_parser("export", help="a fixture at a git rev -> monolithic JSON")
    e.add_argument("--rev", default="HEAD")
    e.add_argument("src")
    e.add_argument("dst")
    c = sub.add_parser("check", help="fail unless the directory is byte-canonical")
    c.add_argument("src")
    args = ap.parse_args(argv)

    if args.cmd == "split":
        write(load(args.src), args.dst)
    elif args.cmd == "join":
        _write_monolith(load(args.src), args.dst)
    elif args.cmd == "export":
        data = load_from_git(args.rev, args.src)
        if data is None:
            print(f"{args.src} does not exist at {args.rev}", file=sys.stderr)
            return 1
        _write_monolith(data, args.dst)
    elif args.cmd == "check":
        bad = check_canonical(args.src)
        if bad:
            print(f"{args.src}: {len(bad)} file(s) not canonical: {bad[:10]}", file=sys.stderr)
            return 1
        print(f"{args.src}: canonical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
