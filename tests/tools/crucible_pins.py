#!/usr/bin/env python3
"""One place to read, verify, sync and bump the crucible pins (tests/crucible_pins.toml). Stdlib only.

    crucible_pins.py get NAME            print the pinned ref (language | estate | cics); what workflows call
    crucible_pins.py check [--no-gh]     each shared checkout: on/off pin, dirty or clean; exit 1 if any is off
    crucible_pins.py sync [NAME...]      fetch the pinned ref and check it out (detached) in each shared
                                         checkout, under tests/tools/box/golden-lock.sh; refuses a checkout with
                                         tracked modifications or commits no remote has; prints before -> after
    crucible_pins.py bump NAME REF       edit the manifest and list what else a bump needs
    crucible_pins.py check-var VALUE     compare the LANGUAGE_CRUCIBLE_REF repo variable's value with the manifest

A checkout is found through the crucible's path env var (LANGUAGE_CRUCIBLE_PATH, ESTATE_CRUCIBLE_PATH,
CICS_CRUCIBLE_PATH), else `<default_dir>` beside the main gitgalaxy checkout -- no machine path is committed.
`--manifest PATH` points every command at another manifest (tests).
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _crucible_manifest as manifest  # noqa: E402

REPO = HERE.parent.parent
LOCK = HERE / "box" / "golden-lock.sh"
VARIABLE = "LANGUAGE_CRUCIBLE_REF"
VARIABLE_API = f"repos/squid-protocol/gitgalaxy/actions/variables/{VARIABLE}"
REF_RE = re.compile(r"v\d+(\.\d+)*|[0-9a-f]{40}")

BUMP_REMINDERS = {
    "language": [
        "regenerate the golden masters FIRST: golden-lock.sh python tests/tools/crucible_check.py --update --yes (both legs; language-crucible RELEASING.md)",
        "check docs/self_scan/BUMPING_THE_CRUCIBLE_PIN.md for the baselines that move with the corpus",
        "the repo variable LANGUAGE_CRUCIBLE_REF is NOT read by workflows any more; `check` warns if it lags",
    ],
    "estate": [
        "run `python tests/tools/estate_crucible.py` at the new tag and put the scorecard in the PR body",
        "re-baseline: python tests/tools/estate_crucible_gate.py --update-baseline (tests/estate_crucible/baseline.json)",
        "fact-crosscheck ledger: python tests/tools/fact_crosscheck.py update (tests/cobol_mainframe/fact_crosscheck_ledger.json)",
    ],
    "cics": [
        "re-baseline: python tests/tools/cics_crucible.py --update-baseline (tests/cics_crucible/baseline.json, docs/language_status/cics_crucible.md)",
        "re-prove the ports: python tests/tools/crucible_port_provenance.py reprove (#4308)",
        "cics-crucible RELEASING.md Phase B; `python tests/tools/crucible_release.py` has the pin-check for the release",
        "ports-compile / fact ledgers move with the crucible: pr_gates.py --ratchets lists them",
    ],
}


def die(message: str, code: int = 2) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def git(path: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: S603 -- fixed argv
        ["git", "-C", str(path), *args], capture_output=True, text=True, check=check
    )


def canonical(name: str) -> str:
    short = name.removesuffix("-crucible")
    if short not in manifest.NAMES:
        die(f"unknown crucible {name!r}; choose from {', '.join(manifest.NAMES)}")
    return short


def pin_of(name: str, path: Path) -> dict:
    try:
        return manifest.entry(name, path)
    except KeyError as exc:
        die(str(exc.args[0]))
    return {}


def primary_checkout() -> Path:
    """The main gitgalaxy checkout (a worktree's git-common-dir parent), else this repo."""
    common = git(REPO, "rev-parse", "--git-common-dir").stdout.strip()
    if not common:
        return REPO
    return Path(common if os.path.isabs(common) else REPO / common).resolve().parent


def checkout_path(name: str, entry: dict, env: dict[str, str] | None = None) -> Path:
    env = (os.environ if env is None else env).get(entry["path_env"])
    return Path(env) if env else primary_checkout().parent / entry["default_dir"]


def rev(path: Path, ref: str) -> str | None:
    out = git(path, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    return out.stdout.strip() if out.returncode == 0 else None


def describe(path: Path) -> str:
    return git(path, "describe", "--tags", "--always").stdout.strip() or "unknown"


def is_checkout(path: Path) -> bool:
    return (path / ".git").exists()


def tracked_dirty(path: Path) -> list[str]:
    return [ln for ln in git(path, "status", "--porcelain", "--untracked-files=no").stdout.splitlines() if ln]


def unpushed(path: Path) -> int:
    """Commits reachable from HEAD that no remote-tracking ref has: checking out elsewhere would strand them."""
    out = git(path, "rev-list", "--count", "HEAD", "--not", "--remotes")
    return int(out.stdout.strip() or 0) if out.returncode == 0 else 0


def variable_value() -> str | None:
    if shutil.which("gh") is None:
        return None
    try:
        out = subprocess.run(  # noqa: S603 -- fixed argv
            ["gh", "api", VARIABLE_API, "-q", ".value"], capture_output=True, text=True, timeout=20, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 and out.stdout.strip() else None


def cmd_get(args) -> int:
    print(pin_of(canonical(args.name), args.manifest)["ref"])
    return 0


def check_rows(manifest_path: Path = manifest.MANIFEST, env: dict[str, str] | None = None) -> list[dict]:
    """One row per crucible: {name, ref, path, state ok|off|skip, dirty, detail}. `env` (default os.environ) names
    the checkouts and carries each crucible's allow_unpinned_env escape hatch (an off-pin checkout is then ok)."""
    env = dict(os.environ if env is None else env)
    rows = []
    for name in manifest.NAMES:
        entry = pin_of(name, manifest_path)
        ref, path = entry["ref"], checkout_path(name, entry, env)
        row = {"name": name, "ref": ref, "path": path, "dirty": [], "env": entry["path_env"]}
        if not is_checkout(path):
            rows.append({**row, "state": "skip", "detail": f"no checkout at {path} (set {entry['path_env']})"})
            continue
        want, head = rev(path, ref), rev(path, "HEAD")
        row["dirty"] = tracked_dirty(path)
        if want and want == head:
            state, detail = "ok", f"on pin {ref}"
        elif env.get(entry["allow_unpinned_env"]) == "1":
            state, detail = "ok", f"unpinned ({entry['allow_unpinned_env']}=1), pin is {ref}"
        else:
            state = "off"
            detail = f"on {describe(path)}" + ("" if want else f"; {ref} not fetched here")
            detail += f"; fix: python tests/tools/crucible_pins.py sync {name}"
        rows.append({**row, "state": state, "detail": detail})
    return rows


def cmd_check(args) -> int:
    off = 0
    for row in check_rows(args.manifest):
        name, ref, path, dirty = row["name"], row["ref"], row["path"], row["dirty"]
        state = "clean" if not dirty else f"DIRTY ({len(dirty)} tracked change{'s' * (len(dirty) != 1)})"
        if row["state"] == "skip":
            print(f"skip  {name:<9} {ref:<8} {row['detail']}")
        elif row["state"] == "ok":
            print(f"ok    {name:<9} {ref:<8} {path}  {row['detail']}, {state}")
        else:
            off += 1
            print(f"OFF   {name:<9} {ref:<8} {path}  {row['detail']}, {state}")
    if not args.no_gh:
        value = variable_value()
        if value is None:
            print(f"note  {VARIABLE} not readable (offline, no gh, or unset): skipped")
        else:
            warn = variable_problem(value, args.manifest)
            print(warn if warn else f"ok    {VARIABLE} = {value} matches the manifest")
    return 1 if off else 0


def variable_problem(value: str, manifest_path: Path) -> str | None:
    want = pin_of("language", manifest_path)["ref"]
    if value == want:
        return None
    return (
        f"WARN  {VARIABLE} is {value!r} but tests/crucible_pins.toml pins {want!r}. No workflow reads the "
        f"variable any more (the manifest wins); update it with `gh variable set {VARIABLE} --body {want} "
        f"--repo squid-protocol/gitgalaxy` or delete it."
    )


def cmd_check_var(args) -> int:
    if not args.value:
        print(f"{VARIABLE} is empty or unset (a fork run, or the variable was deleted): nothing to compare")
        return 0
    problem = variable_problem(args.value, args.manifest)
    if not problem:
        print(f"{VARIABLE} = {args.value} matches the manifest")
        return 0
    print(problem)
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::warning title={VARIABLE} differs from the manifest::{problem}")
    return 1 if args.strict else 0


def cmd_sync(args) -> int:
    names = [canonical(n) for n in args.names] or list(manifest.NAMES)
    if not args.no_lock and not os.environ.get("GG_SYNC_LOCKED") and LOCK.exists() and shutil.which("flock"):
        env = {**os.environ, "GG_SYNC_LOCKED": "1"}
        return subprocess.run([str(LOCK), sys.executable, *sys.argv], env=env, check=False).returncode  # noqa: S603
    plans, bad = [], 0
    for name in names:  # pass 1: refuse before touching anything
        entry = pin_of(name, args.manifest)
        path = checkout_path(name, entry)
        if not is_checkout(path):
            print(f"SKIP   {name}: no checkout at {path} (set {entry['path_env']})")
            continue
        dirty, ahead = tracked_dirty(path), unpushed(path)
        if dirty:
            print(
                f"REFUSE {name} ({path}): {len(dirty)} tracked modification(s); commit or stash them", file=sys.stderr
            )
            bad = 1
        elif ahead:
            print(
                f"REFUSE {name} ({path}): {ahead} commit(s) on {describe(path)} that no remote has; push them first",
                file=sys.stderr,
            )
            bad = 1
        else:
            plans.append((name, entry, path))
    if bad:
        return 1
    for name, entry, path in plans:
        ref, before = entry["ref"], describe(path)
        fetch = git(path, "fetch", "-q", "--tags", "origin")
        if fetch.returncode != 0 and not rev(path, ref):
            print(
                f"ERROR  {name}: git fetch failed and {ref} is not known locally: {fetch.stderr.strip()}",
                file=sys.stderr,
            )
            return 1
        if not rev(path, ref):
            git(path, "fetch", "-q", "origin", ref)
        done = git(path, "checkout", "-q", "--detach", ref)
        if done.returncode != 0:
            print(f"ERROR  {name}: cannot check out {ref}: {done.stderr.strip()}", file=sys.stderr)
            return 1
        print(f"SYNCED {name}: {before} -> {describe(path)} ({ref}) at {path}")
    return 0


def cmd_bump(args) -> int:
    name = canonical(args.name)
    if not REF_RE.fullmatch(args.ref):
        die(f"{args.ref!r} is not a release tag (vX.Y.Z) or a 40-hex commit SHA")
    old = pin_of(name, args.manifest)["ref"]
    text = args.manifest.read_text(encoding="utf-8")
    pattern = re.compile(rf'(^\[{name}\]\n(?:(?!\[).*\n)*?ref = ")[^"]*(")', re.M)
    new_text, count = pattern.subn(rf"\g<1>{args.ref}\g<2>", text)
    if count != 1:
        die(f"could not find the ref line of [{name}] in {args.manifest}")
    args.manifest.write_text(new_text, encoding="utf-8")
    print(f"{name}: {old} -> {args.ref} in {args.manifest}")
    print("A bump is not just this line. Same PR:")
    for item in BUMP_REMINDERS[name]:
        print(f"  - {item}")
    print(f"  - afterwards: crucible_pins.py sync {name}  (shared checkouts are never moved for you)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=Path, default=manifest.MANIFEST)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("get").add_argument("name")
    check = sub.add_parser("check")
    check.add_argument("--no-gh", action="store_true", help="skip the LANGUAGE_CRUCIBLE_REF variable lookup")
    sync = sub.add_parser("sync")
    sync.add_argument("names", nargs="*")
    sync.add_argument("--no-lock", action="store_true", help="do not take golden-lock.sh (tests)")
    bump = sub.add_parser("bump")
    bump.add_argument("name")
    bump.add_argument("ref")
    var = sub.add_parser("check-var")
    var.add_argument("value", nargs="?", default="")
    var.add_argument("--strict", action="store_true", help="exit 1 on a mismatch (default: warn only)")
    args = parser.parse_args(argv)
    return {"get": cmd_get, "check": cmd_check, "sync": cmd_sync, "bump": cmd_bump, "check-var": cmd_check_var}[
        args.cmd
    ](args)


if __name__ == "__main__":
    sys.exit(main())
