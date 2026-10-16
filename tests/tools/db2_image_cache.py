#!/usr/bin/env python3
"""db2_image_cache.py <key|load|save> [DIR]   (#5262)

CI keeps the digest-pinned Db2 image in actions/cache instead of pulling icr.io in every shard (icr.io outages outlast
the #5048 retry). Stdlib only: the workflows run it before the project is installed.

  key        print the cache key, `db2-image-<64 hex digest>` (the pin is the key, so a new pin is a new entry)
  load DIR   exit 0 when the pinned image is on this host, or was restored from DIR (`docker save | zstd`, image id checked
             against the one recorded at save time, tagged IMAGE_ALIAS: a digest cannot be a local tag, and the harness runs
             from the alias, equivalence_db2.run_ref). Exit 1 on a miss or a mismatch: the caller then pulls with ci_retry.sh.
  save DIR   export the pulled, pinned image to DIR (image.tar.zst + image.id); main-only, one shard (the workflow decides)
"""

import re
import subprocess
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().with_name("equivalence_db2.py")
IMAGE = re.search(
    r'^IMAGE = "(icr\.io/db2_community/db2@sha256:[0-9a-f]{64})"', SOURCE.read_text(encoding="utf-8"), re.M
).group(1)
DIGEST = IMAGE.rsplit(":", 1)[1]
ALIAS = "gitgalaxy-db2-pinned:" + DIGEST[:12]
TAR = "image.tar.zst"
IDFILE = "image.id"


def key() -> str:
    return "db2-image-" + DIGEST


def _image_id(ref: str) -> str:
    proc = subprocess.run(
        ["docker", "image", "inspect", "-f", "{{.Id}}", ref], capture_output=True, text=True, check=False
    )  # noqa: S603, S607
    return proc.stdout.strip() if proc.returncode == 0 else ""


def load(directory: Path) -> bool:
    if _image_id(IMAGE) or _image_id(ALIAS):
        print("db2 image: already on this host")
        return True
    tar, idfile = directory / TAR, directory / IDFILE
    if not tar.is_file() or not idfile.is_file():
        print("db2 image cache: miss")
        return False
    want = idfile.read_text(encoding="utf-8").strip()
    with tar.open("rb") as src:
        zstd = subprocess.Popen(["zstd", "-dc"], stdin=src, stdout=subprocess.PIPE)  # noqa: S603, S607
        loaded = subprocess.run(["docker", "load", "-q"], stdin=zstd.stdout, capture_output=True, check=False)  # noqa: S603, S607
        zstd.stdout.close()
        zstd_rc = zstd.wait()
    if loaded.returncode != 0 or zstd_rc != 0:
        print(f"db2 image cache: load failed (docker {loaded.returncode}, zstd {zstd_rc}); falling back to a pull")
        return False
    got = re.search(rb"Loaded image ID: (sha256:[0-9a-f]{64})", loaded.stdout)
    if not want.startswith("sha256:") or not got or got.group(1).decode("ascii") != want or _image_id(want) != want:
        print("db2 image cache: the loaded image id is not the recorded one; falling back to a pull")
        return False
    subprocess.run(["docker", "tag", want, ALIAS], check=True)  # noqa: S603, S607
    print(f"db2 image cache: hit, loaded {want[:19]} as {ALIAS} (no registry request)")
    return True


def save(directory: Path) -> bool:
    ident = _image_id(IMAGE)
    if not ident.startswith("sha256:"):
        print("db2 image cache: the pinned image is not on this host (pulled by digest); nothing to save")
        return False
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / TAR).open("wb") as out:
        save_p = subprocess.Popen(["docker", "save", IMAGE], stdout=subprocess.PIPE)  # noqa: S603, S607
        zstd = subprocess.run(["zstd", "-3", "-T0", "-q"], stdin=save_p.stdout, stdout=out, check=False)  # noqa: S603, S607
        save_p.stdout.close()
        save_rc = save_p.wait()
    if save_rc != 0 or zstd.returncode != 0:
        (directory / TAR).unlink(missing_ok=True)
        print(f"db2 image cache: save failed (docker {save_rc}, zstd {zstd.returncode})")
        return False
    (directory / IDFILE).write_text(ident + "\n", encoding="utf-8")
    print(f"db2 image cache: saved {ident[:19]}, {(directory / TAR).stat().st_size / 1e6:.0f} MB compressed")
    return True


def main(argv: list[str]) -> int:
    if argv[:1] == ["key"]:
        print(key())
        return 0
    if len(argv) == 2 and argv[0] in ("load", "save"):
        return 0 if (load if argv[0] == "load" else save)(Path(argv[1])) else 1
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
