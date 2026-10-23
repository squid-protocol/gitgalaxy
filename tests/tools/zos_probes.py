"""The z/OS calibration probe corpus (#4702 Part 2): load, validate, template and run on the oracle.

zos_probes.py check      validate docs/language_status/zos_probes.json against the register
zos_probes.py template   print the empty zos_calibration.json records an operator fills in on z/OS
zos_probes.py oracle     run every probe on the pinned GnuCOBOL image and compare with oracle_expected (needs Docker)
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import equivalence_oracle
import register
from gitgalaxy.core.runtime_options import RUNTIME_OPTION_TABLE

PROBES = register.REPO / "docs" / "language_status" / "zos_probes.json"
PROBE_KEYS = ("entries", "compile_options", "question", "source", "oracle_expected")
LAST_COLUMN = 72


def load(path: Path | None = None) -> dict[str, dict]:
    return json.loads((path or PROBES).read_text(encoding="utf-8"))["probes"]


def load_runtime(path: Path | None = None) -> dict[str, str]:
    """The effective LE / Db2 / CICS option set every probe runs under (RUNTIME_OPTION_TABLE keys)."""
    return json.loads((path or PROBES).read_text(encoding="utf-8")).get("runtime_options", {})


def runtime_problems(base: dict[str, str], probes: dict[str, dict]) -> list[str]:
    out = [
        f"runtime_options: {k} is not in RUNTIME_OPTION_TABLE" for k in sorted(set(base) - set(RUNTIME_OPTION_TABLE))
    ]
    out += [f"runtime_options: lacks {k}" for k in sorted(set(RUNTIME_OPTION_TABLE) - set(base))]
    for pid, p in sorted(probes.items()):
        for n, var in enumerate(p.get("runtime_variants", [])):
            out += [
                f"{pid}: runtime_variants[{n}] names {k}, not in the manifest's runtime_options"
                for k in sorted(set(var) - set(base))
            ]
    return out


def problems(probes: dict[str, dict], ids: set[str], results: dict[str, list] | None = None) -> list[str]:
    out = []
    for pid, p in sorted(probes.items()):
        gaps = [k for k in PROBE_KEYS if not p.get(k)]
        if gaps:
            out.append(f"{pid}: lacks {', '.join(gaps)}")
            continue
        out += [f"{pid}: {e} is not a register entry" for e in p["entries"] if e not in ids]
        out += [
            f"{pid}: line {n} runs past column {LAST_COLUMN}"
            for n, line in enumerate(p["source"].splitlines(), 1)
            if len(line) > LAST_COLUMN
        ]
    for entry, recs in sorted((results or {}).items()):
        out += [
            f"zos_calibration.json: {entry} records unknown probe {r['probe']!r}"
            for r in recs
            if r.get("probe") not in probes
        ]
    return out


def template(probes: dict[str, dict], runtime: dict[str, str] | None = None) -> dict[str, list[dict]]:
    """One record per probe run: the base option set, then one per runtime_variants entry (its keys replace the base)."""
    runtime = runtime if runtime is not None else load_runtime()
    out: dict[str, list[dict]] = {}
    for pid, p in sorted(probes.items()):
        for entry in p["entries"]:
            for var in [{}, *p.get("runtime_variants", [])]:
                rec: dict = dict.fromkeys(register.ZOS_RECORD_KEYS, "")
                rec.update(probe=pid, options=p["compile_options"], runtime_options={**runtime, **var})
                out.setdefault(entry, []).append(rec)
    return out


def run_oracle(probes: dict[str, dict], image: str | None = None) -> dict[str, list[str]]:
    """Each probe's DISPLAY lines on cobc -std=ibm."""
    image = image or equivalence_oracle.IMAGE
    seen = {}
    with tempfile.TemporaryDirectory() as tmp:
        for pid, p in sorted(probes.items()):
            (Path(tmp) / "Q.cbl").write_text(p["source"], encoding="utf-8")
            cmd = ["docker", "run", "--rm", "-v", f"{tmp}:/w", "-w", "/w", image,
                   "sh", "-c", "cobc -x -std=ibm -o q Q.cbl && ./q"]  # fmt: skip
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)  # noqa: S603
            seen[pid] = proc.stdout.split() if proc.returncode == 0 else [f"rc={proc.returncode}"]
    return seen


def main(argv: list[str] | None = None) -> int:
    cmd = (argv if argv is not None else sys.argv[1:])[:1] or ["check"]
    probes = load()
    if cmd[0] == "template":
        print(json.dumps({"results": template(probes)}, indent=2))
        return 0
    if cmd[0] == "oracle":
        seen = run_oracle(probes)
        bad = [
            f"{pid}: {seen[pid]} != {p['oracle_expected']}"
            for pid, p in sorted(probes.items())
            if seen[pid] != p["oracle_expected"]
        ]
        print("\n".join(bad) or f"{len(probes)} probes match the oracle")
        return 1 if bad else 0
    found = problems(probes, {m["id"] for m, _ in register.load_entries()}, register.load_zos())
    found += runtime_problems(load_runtime(), probes)
    print("\n".join(found) or f"{len(probes)} probes ok")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
