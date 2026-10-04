"""#4309: the oracle every equivalence proof compares against -- pinned, recorded, checked.

The COBOL side of every proof (batch, CALL, CICS, the CICS crucible, det ports) runs in `gitgalaxy-gnucobol:3`,
built from tests/equivalence/gnucobol.Dockerfile. That file pins the oracle: the base image by digest
(`ARG BASE=...@sha256:...`), GnuCOBOL by its exact Debian package version (`ARG GNUCOBOL=...`) and the
`cobc --version` line that version prints (`ARG COBC=...`). The image carries the same three values as labels.

`fingerprint()` reads what the image in use actually is -- its id, its labels, `cobc --version` and the installed
`gnucobol3` package -- and compares it with the pin. Every proof report records the result under `oracle`, so a
proof names the GnuCOBOL that produced its expected outputs (and #4048's evidence record cites it).

A mismatch (an image built before the pin, a `--build-arg` override, a stale local image) is a warning on stderr;
with GITGALAXY_ORACLE_STRICT=1 (CI) it stops the run. `python tests/tools/equivalence_oracle.py [--strict]`
prints the fingerprint as JSON.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = REPO_ROOT / "tests" / "equivalence" / "gnucobol.Dockerfile"
IMAGE = "gitgalaxy-gnucobol:3"
STRICT_ENV = "GITGALAXY_ORACLE_STRICT"
FORMAT = "gitgalaxy-oracle/1"
LABEL = "org.gitgalaxy.oracle."
PIN_KEYS = ("base", "gnucobol3", "cobc")  # the Dockerfile ARG behind each: BASE, GNUCOBOL, COBC
_ARGS = {"BASE": "base", "GNUCOBOL": "gnucobol3", "COBC": "cobc"}
_ARG = re.compile(r'^ARG[ \t]+([A-Z]+)=(?:"([^"\n]*)"|(\S+))[ \t]*$', re.M)
_PROBE = "cobc --version | head -n 1; dpkg-query -W -f='${Version}\\n' gnucobol3"

_cache: dict[str, dict[str, Any]] = {}


class OracleMismatch(RuntimeError):
    """The image a proof would run on is not the pinned oracle (raised only when strict)."""


def pin(dockerfile: Path = DOCKERFILE) -> dict[str, str]:
    """The pinned oracle, read from the Dockerfile's ARG defaults: {base, gnucobol3, cobc}."""
    found: dict[str, str] = {}
    for m in _ARG.finditer(dockerfile.read_text(encoding="utf-8")):
        if m.group(1) in _ARGS:
            found[_ARGS[m.group(1)]] = m.group(2) if m.group(2) is not None else m.group(3)
    missing = [k for k in PIN_KEYS if k not in found]
    if missing:
        raise ValueError(f"{dockerfile}: no pinned {', '.join(missing)} (ARG BASE / GNUCOBOL / COBC)")
    return found


def mismatches(observed: dict[str, Any], pinned: dict[str, str]) -> list[str]:
    """How the image differs from the pin: one line per value, [] when it is the pinned oracle."""
    out = []
    for key in PIN_KEYS:
        want = pinned[key]
        got = observed.get(key) if key != "base" else observed.get("labels", {}).get(LABEL + "base")
        if got != want:
            out.append(f"{key}: the image has {got!r}, the pin is {want!r}")
    labels = observed.get("labels", {})
    for key in ("gnucobol3", "cobc"):  # the image's own labels: what it was BUILT as (a --build-arg shows here)
        if labels.get(LABEL + key) not in (None, pinned[key]):
            out.append(f"{key} label: the image was built as {labels.get(LABEL + key)!r}, the pin is {pinned[key]!r}")
    return out


def _inspect(image: str) -> dict[str, Any]:
    proc = subprocess.run(["docker", "image", "inspect", image, "--format", "{{json .}}"],  # noqa: S603, S607
                          capture_output=True, text=True, check=False)  # fmt: skip
    if proc.returncode != 0:
        raise RuntimeError(f"docker image inspect {image}: {proc.stderr.strip()}")
    data = json.loads(proc.stdout)
    return {"id": data.get("Id"), "labels": dict((data.get("Config") or {}).get("Labels") or {})}


def _probe(image: str) -> tuple[Optional[str], Optional[str]]:
    proc = subprocess.run(["docker", "run", "--rm", image, "sh", "-c", _PROBE],  # noqa: S603, S607
                          capture_output=True, text=True, check=False)  # fmt: skip
    lines = proc.stdout.splitlines()
    return (lines[0].strip() if lines else None), (lines[1].strip() if len(lines) > 1 else None)


def fingerprint(image: str = IMAGE, *, refresh: bool = False) -> dict[str, Any]:
    """The oracle `image` is, against the pin. Cached per image for the process (one docker run)."""
    if image in _cache and not refresh:
        return _cache[image]
    pinned = pin()
    seen = _inspect(image)
    cobc, gnucobol3 = _probe(image)
    observed = {"labels": seen["labels"], "cobc": cobc, "gnucobol3": gnucobol3}
    wrong = mismatches(observed, pinned)
    fp = {"format": FORMAT, "image": {"name": image, "id": seen["id"]}, "cobc": cobc, "gnucobol3": gnucobol3,
          "base": seen["labels"].get(LABEL + "base"), "pin": pinned, "matches_pin": not wrong,
          "mismatches": wrong}  # fmt: skip
    _cache[image] = fp
    return fp


def adopt(fp: Optional[dict[str, Any]], image: str = IMAGE) -> None:
    """`run --reuse EARLIER`: the COBOL outputs are EARLIER's, so its oracle is this run's."""
    if fp:
        _cache[image] = fp


def image_for(case: dict[str, Any]) -> str:
    """The image a case's COBOL side runs in: a Db2 case's is built FROM the oracle image (labels inherited)."""
    if case.get("db2"):
        import equivalence_db2  # noqa: PLC0415 -- only Db2 cases need it

        return str(equivalence_db2.COBOL_IMAGE)
    return IMAGE


def for_case(case: dict[str, Any]) -> Optional[dict[str, Any]]:
    """What a proof report records under `oracle` for `case` (checked against the pin)."""
    return checked(image_for(case))


def adopt_from(case: dict[str, Any], earlier: Path) -> None:
    """`run --reuse EARLIER`: the COBOL outputs are EARLIER's, so its recorded oracle is this run's."""
    report = earlier / "report.json"
    if report.is_file():
        adopt(json.loads(report.read_text(encoding="utf-8")).get("oracle"), image_for(case))


def strict() -> bool:
    return os.environ.get(STRICT_ENV, "").strip().lower() not in ("", "0", "false", "no")


def checked(image: str = IMAGE) -> Optional[dict[str, Any]]:
    """fingerprint(), with a mismatch warned about on stderr -- or raised under GITGALAXY_ORACLE_STRICT."""
    fp = fingerprint(image)
    if fp["mismatches"] and not fp.get("_warned"):
        msg = (f"oracle {image} ({fp['image']['id']}) is not the pinned GnuCOBOL oracle "
               f"(tests/equivalence/gnucobol.Dockerfile): " + "; ".join(fp["mismatches"]) +
               ". Rebuild it from tests/equivalence/gnucobol.Dockerfile (a Db2 case's image too: "
               "docker rmi gitgalaxy-gnucobol-db2:3)")  # fmt: skip
        if strict():
            raise OracleMismatch(msg)
        print(f"WARNING: {msg}", file=sys.stderr)
        fp["_warned"] = True
    return recorded(fp)


def recorded(fp: Optional[dict[str, Any]] = None, image: str = IMAGE) -> Optional[dict[str, Any]]:
    """The fingerprint as a report records it (no process-local keys); None when it was never taken."""
    fp = fp if fp is not None else _cache.get(image)
    return None if fp is None else {k: v for k, v in fp.items() if not k.startswith("_")}


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image", default=IMAGE)
    ap.add_argument("--strict", action="store_true", help=f"exit 1 on a mismatch (as {STRICT_ENV}=1)")
    args = ap.parse_args(argv)
    fp = recorded(fingerprint(args.image))
    print(json.dumps(fp, indent=1))
    if fp and fp["mismatches"]:
        print("MISMATCH: " + "; ".join(fp["mismatches"]), file=sys.stderr)
        return 1 if (args.strict or strict()) else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
