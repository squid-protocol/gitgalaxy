#!/usr/bin/env python3
"""db2_snapshot.py <key|save|restore> DIR   (#5882)

A Db2 shard started the pinned Db2 image from scratch: the instance's setup, then each pool database's CREATE DATABASE
one at a time (run 39696713590: the first database after 135-180 s, all of them after 302-440 s). This keeps that start
once: the container's own changes over the pinned image (`docker diff`: the instance owner and its home, ~40 MB) and
its /database volume (the instance and its empty databases), which restore onto the pinned image in ~35 s.

  key          print the cache key: the image digest and the parts of equivalence_db2.py that make the container and databases (KEYED_*)
  save DIR     a FRESH container of the pinned image (never one a case has used: it would carry the case's tables), every
               pool database created as equivalence_db2 creates it, Db2 stopped cleanly; DIR gets delta.tar,
               database.tar and snapshot.json. The container is removed afterwards.
  restore DIR  the container equivalence_db2 runs (equivalence_db2.run_args), made from the pinned image with DIR's
               /database and delta, started; equivalence_db2 then waits for it as for any container. Exit 1 with nothing
               left behind when DIR holds no snapshot of this key or the restore fails: the caller starts Db2 as before.

`key` is stdlib only (the workflow runs it before anything is installed); save / restore import equivalence_db2.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
SOURCE = TOOLS / "equivalence_db2.py"
POOL = 4  # the most databases a shard runs (GITGALAXY_DB2_POOL); a smaller pool leaves the rest unused
DELTA, DATA, META = "delta.tar", "database.tar", "snapshot.json"


# What a snapshot's bytes depend on: the container's options, the instance owner, and how a pool database is created.
# Everything else in equivalence_db2.py (readiness waits, locks, the proof side) is not in the key: a harness edit that
# leaves these alone keeps the cached snapshot, instead of a miss until the next main run that makes one.
KEYED_ASSIGNS = ("CONTAINER", "NETWORK", "USER", "PASSWORD", "PORT", "DATABASE0", "POOL_ENV")
KEYED_FUNCTIONS = ("run_args", "pool", "_instance", "_db_cfg", "_ensure_database")


def keyed_source(text: str) -> str:
    """The source of KEYED_ASSIGNS and KEYED_FUNCTIONS in `text`; a missing one raises (a rename must not shrink the key)."""
    found: dict[str, str] = {}
    for node in ast.parse(text).body:
        if isinstance(node, ast.FunctionDef):
            names = [node.name]
        elif isinstance(node, ast.Assign):
            names = [n.id for t in node.targets for n in ast.walk(t) if isinstance(n, ast.Name)]  # USER, PASSWORD = ...
        else:
            continue
        for name in names:
            if name in KEYED_ASSIGNS + KEYED_FUNCTIONS:
                found[name] = ast.get_source_segment(text, node) or ""
    missing = [n for n in KEYED_ASSIGNS + KEYED_FUNCTIONS if n not in found]
    if missing:
        raise ValueError(f"equivalence_db2.py no longer defines {missing}: update db2_snapshot.KEYED_*")
    return "\n".join(dict.fromkeys(found[n] for n in KEYED_ASSIGNS + KEYED_FUNCTIONS))  # USER, PASSWORD: one node


def key() -> str:
    text = SOURCE.read_text(encoding="utf-8")
    digest = re.search(r'^IMAGE = "icr\.io/db2_community/db2@sha256:([0-9a-f]{64})"', text, re.M).group(1)
    return f"db2-snapshot-{digest[:16]}-{hashlib.sha256(keyed_source(text).encode()).hexdigest()[:16]}-pool{POOL}"


def _db2():
    sys.path.insert(0, str(TOOLS))
    os.environ["GITGALAXY_DB2_POOL"] = str(POOL)
    import equivalence_db2 as d

    return d


def _volume(d) -> str:
    return f"{d.CONTAINER}-data"


def _run(argv: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(argv, check=True, **kw)  # noqa: S603


def save(directory: Path) -> None:
    d = _db2()
    subprocess.run(["docker", "rm", "-f", d.CONTAINER], capture_output=True, check=False)  # noqa: S603, S607
    d._CONTAINER_READY = False
    d.READY_MARK.unlink(missing_ok=True)
    d._ensure_container()
    for db in d.pool():
        d._ensure_database(db)
    d._instance("db2 terminate; db2stop force")
    _run(["docker", "stop", "-t", "60", d.CONTAINER], capture_output=True)
    diff = [ln.split(" ", 1) for ln in d._docker("diff", d.CONTAINER).splitlines() if ln.strip()]
    if any(kind == "D" for kind, _ in diff):  # a deletion cannot be replayed by a tar
        raise SystemExit(f"Db2 snapshot: the container deleted files: {[p for k, p in diff if k == 'D'][:5]}")
    paths = [p.lstrip("/") for _, p in diff if not re.match(r"/database(/|$)", p)]
    directory.mkdir(parents=True, exist_ok=True)
    image = f"{d.CONTAINER}-snapshot:tmp"
    _run(["docker", "commit", d.CONTAINER, image], capture_output=True)
    try:  # tar as root inside: the files keep their owners (the instance owner's, root's)
        with (directory / DELTA).open("wb") as out:
            proc = subprocess.run(["docker", "run", "--rm", "-i", "--entrypoint", "tar", image, "-C", "/", "-cpf", "-",  # noqa: S603, S607
                                   "--no-recursion", "--ignore-failed-read", "-T", "-"],
                                  input="\n".join(paths).encode(), stdout=out, stderr=subprocess.PIPE, check=False)  # fmt: skip
        if proc.returncode not in (0, 1):  # 1: a socket the stopped container no longer has
            raise SystemExit(f"Db2 snapshot: tar of the delta failed: {proc.stderr.decode()[-400:]}")
        with (directory / DATA).open("wb") as out:
            _run(["docker", "run", "--rm", "--volumes-from", d.CONTAINER, "--entrypoint", "tar", d.run_ref(),
                  "-C", "/", "-cpf", "-", "database"], stdout=out)  # fmt: skip
    finally:
        subprocess.run(["docker", "rmi", image], capture_output=True, check=False)  # noqa: S603, S607
    meta = {"key": key(), "image": d._docker("image", "inspect", "-f", "{{.Id}}", d.run_ref()).strip(),
            "databases": d.pool(), "delta_paths": len(paths)}  # fmt: skip
    (directory / META).write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    subprocess.run(["docker", "rm", "-f", d.CONTAINER], capture_output=True, check=False)  # noqa: S603, S607
    print(f"Db2 snapshot {meta['key']}: {len(paths)} changed paths, databases {', '.join(meta['databases'])}")


def restore(directory: Path) -> bool:
    try:
        meta = json.loads((directory / META).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print("Db2 snapshot: none here")
        return False
    if meta.get("key") != key() or not (directory / DELTA).is_file() or not (directory / DATA).is_file():
        print(f"Db2 snapshot: {meta.get('key')} is not {key()}")
        return False
    d = _db2()
    ref = d.run_ref()
    if d._docker("image", "inspect", "-f", "{{.Id}}", ref, check=False).strip() != meta["image"]:
        print("Db2 snapshot: made from another image than the pinned one here")
        return False
    if d._docker("inspect", "-f", "{{.State.Running}}", d.CONTAINER, check=False).strip():
        print(f"Db2 snapshot: {d.CONTAINER} exists already; not replaced")
        return False
    vol = _volume(d)
    try:
        if not d._docker("network", "ls", "-q", "-f", f"name=^{d.NETWORK}$").strip():
            d._docker("network", "create", d.NETWORK)
        d._docker("volume", "create", vol)
        with (directory / DATA).open("rb") as src:
            _run(["docker", "run", "--rm", "-i", "-v", f"{vol}:/database", "--entrypoint", "tar", ref,
                  "-C", "/", "-xpf", "-"], stdin=src, capture_output=True)  # fmt: skip
        d._docker("create", *d.run_args(vol), ref)
        with (directory / DELTA).open("rb") as src:
            _run(["docker", "cp", "-a", "-", f"{d.CONTAINER}:/"], stdin=src, capture_output=True)
        d._docker("start", d.CONTAINER)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as e:
        print(f"Db2 snapshot: restore failed ({e}); starting Db2 from scratch instead")
        subprocess.run(["docker", "rm", "-f", d.CONTAINER], capture_output=True, check=False)  # noqa: S603, S607
        subprocess.run(["docker", "volume", "rm", vol], capture_output=True, check=False)  # noqa: S603, S607
        return False
    print(f"Db2 snapshot {meta['key']} restored: databases {', '.join(meta['databases'])}")
    return True


def main(argv: list[str]) -> int:
    if argv[:1] == ["key"]:
        print(key())
        return 0
    if len(argv) == 2 and argv[0] == "save":
        save(Path(argv[1]))
        return 0
    if len(argv) == 2 and argv[0] == "restore":
        return 0 if restore(Path(argv[1])) else 1
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
