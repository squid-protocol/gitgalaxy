#!/usr/bin/env python3
"""The environment of an equivalence / CICS crucible run from a worktree, printed or checked -- so a slice agent does
not hand-write an env.sh with the wrong JDK or a stale crucible path (#4270).

    python tests/tools/equivalence_env.py --shell                       # `export` lines: eval "$(... --shell)"
    python tests/tools/equivalence_env.py --shell --crucible-dir DIR --unpinned   # a private cics-crucible checkout
    python tests/tools/equivalence_env.py --check                       # PASS / WARN / FAIL per item, exit 1 on a FAIL
    eval "$(python tests/tools/equivalence_env.py --provision [--root DIR])"   # private crucible + census clones

The paths come from pr_gates.environment() (the corpora beside the main checkout, PYTHONPATH = this worktree, the
interpreter's bin on PATH, the community licence key); this tool adds what the equivalence and crucible runs need on
top: ESTATE_CRUCIBLE_PATH / CICS_CRUCIBLE_PATH (an explicit value wins, else the sibling of the main checkout, as the
crucible tools and box/sync-pins.sh resolve them), and a JDK 17 as JAVA_HOME and JDK_17.

The JDK trap: Maven under a JDK other than 17 FALSELY fails every forge-compile / java cell ("release version 17 not
supported"), and det_survey / cics_crucible compile with JDK_17 / JAVA_HOME. So a JDK 17 is found ($JDK_17,
$JAVA_HOME, /usr/lib/jvm/*17*) and verified by running its `java -version`; when only another JDK exists the tool
refuses (exit 2) instead of printing an environment that fails later for no visible reason.

--crucible-dir DIR points CICS_CRUCIBLE_PATH at a private checkout (a case branch, an untagged release commit);
--unpinned adds CICS_CRUCIBLE_ALLOW_UNPINNED=1 for one that is deliberately not at tests/_cics_crucible_pin.py.

--check verifies: the JDK is 17; mvn on PATH; Docker answers and has the GnuCOBOL image; the mainframe corpora,
language-crucible, estate-crucible and cics-crucible checkouts exist (cics-crucible at the pin unless --unpinned);
tree_sitter_language_pack is importable (the det translator's `translator` extra -- without it det tests SKIP);
`import gitgalaxy` resolves to this worktree. A LANGUAGE_CRUCIBLE_PATH that is wrong fails the golden check falsely,
so it is checked too. The SHARED cics-crucible checkout (the one beside the main checkout) off its pin is a WARN, not a
FAIL: other agents use it, so do not move it -- provision a private clone at the pin instead (below).

--provision (#4270) makes, idempotently, under the shared scratch root (--root, else $GG_SCRATCH, else
<worktrees dir>/_shared-scratch; the worktrees dir is $GITGALAXY_WORKTREES, else the directory holding this
worktree, else <main checkout>/../gitgalaxy-worktrees):
  <root>/cics-crucible   a private cics-crucible clone checked out at the PINNED ref (tests/_cics_crucible_pin.py)
  <root>/census/<repo>   the census clones: ONLY estate4_draw.INELIGIBLE_LIST minus the burned estates. A repo whose
                         name is among the blind 4th-estate candidates (docs/language_status/estate4_candidates.json,
                         names compared, nothing else read) is refused: reading it through the translator burns it.
  <root>/provision.json  each clone's URL and commit SHA
and prints the `--shell` exports for them (CICS_CRUCIBLE_PATH, CICS_CENSUS_CORPORA, GG_SCRATCH, ...). Progress goes to
stderr, so `eval "$(... --provision)"` works. `--shell --root DIR` exports an existing provision without touching it.
Nothing from the census clones is ever committed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO / "tests"))

import pr_gates  # noqa: E402

GNUCOBOL_IMAGE = "gitgalaxy-gnucobol:3"  # tests/tools/equivalence_common.IMAGE (not imported: it pulls the harness)
EXPORTED = ("PYTHONPATH", "GITGALAXY_LICENSE_KEY", "PATH", "KEYWORD_ROSETTA_PATH", "LANGUAGE_CRUCIBLE_PATH",
            "GITGALAXY_MAINFRAME_CORPORA", "ESTATE_CRUCIBLE_PATH", "CICS_CRUCIBLE_PATH",
            "CICS_CRUCIBLE_ALLOW_UNPINNED", "JAVA_HOME", "JDK_17", "CICS_CENSUS_CORPORA", "GG_SCRATCH")  # fmt: skip
SCRATCH_ENV = "GG_SCRATCH"
GIT_BASE_ENV = "GG_PROVISION_GIT_BASE"  # where the clones come from (default https://github.com; tests: a local dir)
CRUCIBLE_REPO = "squid-protocol/cics-crucible"
CANDIDATES_JSON = REPO / "docs" / "language_status" / "estate4_candidates.json"
PROVISION_HINT = ("provision a private clone at the pin instead: eval \"$(python tests/tools/equivalence_env.py "
                  "--provision)\" (do not move the shared checkout: other agents use it)")  # fmt: skip


class JdkError(Exception):
    """No JDK 17 on this box (only other versions)."""


def java_major(home: Path) -> int | None:
    """The major version `<home>/bin/java -version` reports, or None when it does not run."""
    java = home / "bin" / "java"
    if not java.is_file():
        return None
    try:
        out = subprocess.run([str(java), "-version"], capture_output=True, text=True, check=False, timeout=30)  # noqa: S603
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.search(r'version "(\d+)(?:\.(\d+))?', out.stderr + out.stdout)
    if not m:
        return None
    major = int(m.group(1))
    return int(m.group(2) or 0) if major == 1 else major  # "1.8.0" is 8


def jdk_candidates(env: dict[str, str], jvm_root: Path = Path("/usr/lib/jvm")) -> list[Path]:
    seen = [Path(env[var]) for var in ("JDK_17", "JAVA_HOME") if env.get(var)]
    if jvm_root.is_dir():
        seen += sorted(p for p in jvm_root.iterdir() if "17" in p.name and p.is_dir())
        seen += sorted(p for p in jvm_root.iterdir() if "17" not in p.name and p.is_dir())
    out: list[Path] = []
    for p in seen:
        if p not in out:
            out.append(p)
    return out


def find_jdk17(env: dict[str, str], jvm_root: Path = Path("/usr/lib/jvm"),
               major: Callable[[Path], int | None] = java_major) -> tuple[Path, list[str]]:  # fmt: skip
    """(the JDK 17 home, notes). Raises JdkError, naming what was found, when there is none."""
    notes: list[str] = []
    others: list[str] = []
    for home in jdk_candidates(env, jvm_root):
        v = major(home)
        if v == 17:
            notes += [f"{var}={env[var]} is not a JDK 17; using {home}" for var in ("JAVA_HOME", "JDK_17")
                      if env.get(var) and Path(env[var]) != home]  # fmt: skip
            return home, notes
        if v is not None:
            others.append(f"{home} (JDK {v})")
    raise JdkError(
        "no JDK 17 found -- only: " + (", ".join(others) or "none") + ". A JDK other than 17 FALSELY fails every "
        "forge-compile / java cell ('release version 17 not supported'). Install openjdk-17-jdk or set JDK_17."
    )


def environment(crucible_dir: Path | None = None, unpinned: bool = False,
                jvm_root: Path = Path("/usr/lib/jvm")) -> tuple[dict[str, str], list[str]]:  # fmt: skip
    """(the full environment, notes). Raises JdkError."""
    env = pr_gates.environment(e2e=True)
    main = pr_gates._main_checkout()
    if crucible_dir is not None:
        env["CICS_CRUCIBLE_PATH"] = str(crucible_dir.resolve())
    for var, name in (("ESTATE_CRUCIBLE_PATH", "estate-crucible"), ("CICS_CRUCIBLE_PATH", "cics-crucible")):
        env.setdefault(var, str(main.parent / name))
    if unpinned:
        env["CICS_CRUCIBLE_ALLOW_UNPINNED"] = "1"
    home, notes = find_jdk17(env, jvm_root)
    env["JAVA_HOME"] = env["JDK_17"] = str(home)
    env["PATH"] = str(home / "bin") + os.pathsep + env["PATH"]
    return env, notes


def shell_lines(env: dict[str, str]) -> list[str]:
    return [f"export {var}={shlex.quote(env[var])}" for var in EXPORTED if env.get(var)]


# ---- --check -----------------------------------------------------------------------------------------------------
def _run(argv: list[str], env: dict[str, str], timeout: int = 60) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(argv, capture_output=True, text=True, env=env, check=False, timeout=timeout)  # noqa: S603
    except (OSError, subprocess.TimeoutExpired):
        return None


def pin_message(pin, path: Path, env: dict[str, str]) -> str | None:
    """`pin.pin_mismatch(path)` (tests/_crucible_pin.py, tests/_cics_crucible_pin.py) under `env`'s escape hatch."""
    var = pin.ALLOW_UNPINNED_ENV
    saved = os.environ.get(var)
    if env.get(var):
        os.environ[var] = env[var]
    else:
        os.environ.pop(var, None)
    try:
        msg = pin.pin_mismatch(path)
    finally:
        if saved is None:
            os.environ.pop(var, None)
        else:
            os.environ[var] = saved
    return msg.replace("\n", " ") if msg else None


def crucible_check(env: dict[str, str]) -> tuple[str, bool | None, str]:
    """The cics-crucible item of --check. The SHARED checkout (beside the main checkout) off its pin is a WARN with the
    provision hint -- other agents use it, so it is never moved for one run; any other checkout off its pin FAILs."""
    import _cics_crucible_pin as cics_pin

    cc = Path(env["CICS_CRUCIBLE_PATH"])
    if not (cc / ".git").exists() and not (cc / "SPEC.md").is_file():
        return ("cics-crucible", False, f"no checkout at {cc} (set CICS_CRUCIBLE_PATH or --crucible-dir)")
    msg = pin_message(cics_pin, cc, env)
    if msg is None:
        note = ("unpinned (CICS_CRUCIBLE_ALLOW_UNPINNED=1)" if env.get(cics_pin.ALLOW_UNPINNED_ENV)
                else f"at {cics_pin.PINNED_REF}")  # fmt: skip
        return ("cics-crucible", True, f"{cc} {note}")
    if cc.resolve() == (pr_gates._main_checkout().parent / "cics-crucible").resolve():
        return (
            "cics-crucible",
            None,
            f"the SHARED checkout {cc} is off the pin {cics_pin.PINNED_REF}: {PROVISION_HINT}",
        )
    return ("cics-crucible", False, msg)


def checks(env: dict[str, str]) -> list[tuple[str, bool | None, str]]:
    """[(item, ok, detail)]: ok None is a WARN (reported, not a failure)."""
    out: list[tuple[str, bool | None, str]] = []
    v = java_major(Path(env["JAVA_HOME"]))
    out.append(("java -version is 17", v == 17, f"{env['JAVA_HOME']}: JDK {v}"))
    mvn = shutil.which("mvn", path=env.get("PATH"))
    out.append(("mvn on PATH", bool(mvn), mvn or "not found (Maven: forge-compile / java cells)"))
    r = _run(["docker", "info", "--format", "{{.ServerVersion}}"], env)
    docker = bool(r and r.returncode == 0)
    out.append(("docker daemon", docker, (r.stdout.strip() if docker and r else "docker info failed (cobol-stub)")))
    if docker:
        r = _run(["docker", "image", "inspect", GNUCOBOL_IMAGE, "--format", "{{.Id}}"], env)
        ok = bool(r and r.returncode == 0)
        out.append((f"image {GNUCOBOL_IMAGE}", ok, "present" if ok else "missing: built on first equivalence run "
                    "(tests/equivalence/gnucobol.Dockerfile)"))  # fmt: skip
    corpora = Path(env.get("GITGALAXY_MAINFRAME_CORPORA", ""))
    n = len(list(corpora.glob("*/.git"))) if env.get("GITGALAXY_MAINFRAME_CORPORA") else 0
    out.append(("mainframe corpora", n > 0, f"{corpora}: {n} corpora" if n else
                "GITGALAXY_MAINFRAME_CORPORA unset or empty (python tests/tools/mainframe_corpus.py fetch)"))  # fmt: skip
    import _crucible_pin as lang_pin

    lc = Path(env.get("LANGUAGE_CRUCIBLE_PATH", ""))
    if not (env.get("LANGUAGE_CRUCIBLE_PATH") and (lc / "data").is_dir()):
        out.append(("language-crucible", False,
                    f"LANGUAGE_CRUCIBLE_PATH={lc or '(unset)'} has no data/: the golden check would fail falsely"))  # fmt: skip
    else:
        msg = pin_message(lang_pin, lc, env)
        out.append(("language-crucible", msg is None, f"{lc} at {lang_pin.PINNED_TAG}" if msg is None else msg))
    ec = Path(env["ESTATE_CRUCIBLE_PATH"])
    ok = (ec / "key" / "manifest.json").is_file()
    out.append(("estate-crucible", ok, str(ec) if ok else f"no checkout at {ec} (set ESTATE_CRUCIBLE_PATH)"))
    out.append(crucible_check(env))
    py = sys.executable
    r = _run([py, "-c", "import tree_sitter_language_pack"], env)
    ok = bool(r and r.returncode == 0)
    out.append(("tree_sitter_language_pack", ok, py if ok else
                f"not importable by {py}: the det tests SKIP (pip install -e .[full,translator])"))  # fmt: skip
    r = _run([py, "-c", "import os, gitgalaxy; print(os.path.dirname(gitgalaxy.__file__))"], env)
    where = r.stdout.strip() if r and r.returncode == 0 else ""
    ok = bool(where) and Path(where).resolve() == (REPO / "gitgalaxy").resolve()
    out.append(("gitgalaxy imports from this worktree", ok, where or "import gitgalaxy failed"))
    return out


# ---- --provision (#4270) -----------------------------------------------------------------------------------------
class ProvisionRefused(Exception):
    """A census repo is a blind 4th-estate candidate, or a private clone has local changes."""


def worktrees_dir() -> Path:
    """$GITGALAXY_WORKTREES, else the directory holding this worktree (run from a linked worktree), else
    <main checkout>/../gitgalaxy-worktrees (worktree_env.sh's default)."""
    if os.environ.get("GITGALAXY_WORKTREES"):
        return Path(os.environ["GITGALAXY_WORKTREES"])
    main = pr_gates._main_checkout()
    return REPO.resolve().parent if REPO.resolve() != main.resolve() else main.parent / "gitgalaxy-worktrees"


def scratch_root(arg: Path | None = None) -> Path:
    """The scratch root shared by the worktrees of this box: --root, else $GG_SCRATCH, else <worktrees>/_shared-scratch."""
    if arg is not None:
        return arg.resolve()
    if os.environ.get(SCRATCH_ENV):
        return Path(os.environ[SCRATCH_ENV]).resolve()
    return worktrees_dir() / "_shared-scratch"


def candidate_names(path: Path | None = None) -> set[str]:
    """The blind 4th-estate candidates' names (owner/repo and repo, lower case) -- nothing else of the file is read."""
    path = path or CANDIDATES_JSON
    if not path.is_file():
        return set()
    names = {str(c["full_name"]).lower() for c in json.loads(path.read_text(encoding="utf-8"))["candidates"]}
    return names | {n.split("/")[-1] for n in names}


def census_repos() -> list[str]:
    """owner/repo of the census-counted repos: estate4_draw.INELIGIBLE_LIST minus the burned estates."""
    import estate4_draw

    burned = {n.lower() for n in estate4_draw.BURNED_NAMES}
    return [r for r in estate4_draw.INELIGIBLE_LIST if r.split("/")[-1].lower() not in burned]


def _git(argv: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *argv], cwd=cwd, capture_output=True, text=True, check=False)  # noqa: S603, S607


def _rev(path: Path, ref: str) -> str | None:
    r = _git(["-C", str(path), "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"])
    return r.stdout.strip() if r.returncode == 0 else None


def _clone(url: str, dest: Path, shallow: bool) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = _git(["clone", "-q", *(["--depth", "1"] if shallow else []), url, str(dest)])
    if r.returncode:
        raise RuntimeError(f"git clone {url} failed: {r.stderr.strip()[:300]}")


def provision(root: Path, git_base: str | None = None, log=print) -> dict:
    """The private cics-crucible clone at the pin and the census clones under `root` (idempotent); returns and writes
    <root>/provision.json. Raises ProvisionRefused before cloning anything if a census repo is an estate4 candidate."""
    import _cics_crucible_pin as cics_pin

    base = (git_base or os.environ.get(GIT_BASE_ENV) or "https://github.com").rstrip("/")
    repos = census_repos()
    cands = candidate_names()
    bad = [r for r in repos if r.lower() in cands or r.split("/")[-1].lower() in cands]
    if bad:
        raise ProvisionRefused(f"refused: {', '.join(bad)} named among the blind 4th-estate candidates "
                               f"({CANDIDATES_JSON.name}): never clone or read a candidate")  # fmt: skip
    root.mkdir(parents=True, exist_ok=True)
    record: dict = {"root": str(root), "pinned_ref": cics_pin.PINNED_REF, "census": {}, "errors": []}
    crucible = root / "cics-crucible"
    if not (crucible / ".git").exists():
        log(f"cloning {CRUCIBLE_REPO} -> {crucible}")
        _clone(f"{base}/{CRUCIBLE_REPO}", crucible, shallow=False)
    pinned = _rev(crucible, cics_pin.PINNED_REF)
    if pinned is None:
        _git(["-C", str(crucible), "fetch", "-q", "--tags", "origin"])
        pinned = _rev(crucible, cics_pin.PINNED_REF)
    if pinned is None:
        raise RuntimeError(f"{crucible}: the pinned ref {cics_pin.PINNED_REF} is not in the clone, even after a fetch")
    if _rev(crucible, "HEAD") != pinned:
        if _git(["-C", str(crucible), "status", "--porcelain", "--untracked-files=no"]).stdout.strip():
            raise ProvisionRefused(f"{crucible} has local changes and is off the pin: commit or stash them first")
        log(f"{crucible}: checking out {cics_pin.PINNED_REF}")
        r = _git(["-C", str(crucible), "checkout", "-q", "--detach", cics_pin.PINNED_REF])
        if r.returncode:
            raise RuntimeError(f"checkout {cics_pin.PINNED_REF} failed: {r.stderr.strip()[:300]}")
    record["crucible"] = {"path": str(crucible), "url": f"{base}/{CRUCIBLE_REPO}", "ref": cics_pin.PINNED_REF,
                          "sha": pinned}  # fmt: skip
    census = root / "census"
    for repo in repos:
        dest = census / repo.split("/")[-1]
        try:
            if not (dest / ".git").exists():
                log(f"cloning {repo} -> {dest}")
                _clone(f"{base}/{repo}", dest, shallow=True)
            record["census"][dest.name] = {"repo": repo, "path": str(dest), "sha": _rev(dest, "HEAD")}
        except RuntimeError as e:
            record["errors"].append(str(e))
    known = {r.split("/")[-1].lower() for r in repos}
    stray = (
        sorted(p.name for p in census.iterdir() if p.is_dir() and p.name.lower() not in known)
        if census.is_dir()
        else []
    )
    if stray:
        record["errors"].append(f"not on the census list (left alone, not surveyed by you): {', '.join(stray)}")
    record["provisioned_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (root / "provision.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    return record


def provisioned_env(env: dict[str, str], root: Path) -> dict[str, str]:
    """`env` pointed at the provision under `root` (its private crucible, census clones, GG_SCRATCH)."""
    env = dict(env, GG_SCRATCH=str(root))
    if (root / "cics-crucible").is_dir():
        env["CICS_CRUCIBLE_PATH"] = str(root / "cics-crucible")
    if (root / "census").is_dir():
        env["CICS_CENSUS_CORPORA"] = str(root / "census")
    return env


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--shell", action="store_true", help="print `export` lines (the default output)")
    ap.add_argument("--check", action="store_true", help="verify the environment: PASS / FAIL per item")
    ap.add_argument("--crucible-dir", type=Path, help="CICS_CRUCIBLE_PATH: a private cics-crucible checkout")
    ap.add_argument("--unpinned", action="store_true", help="CICS_CRUCIBLE_ALLOW_UNPINNED=1 (an off-pin checkout)")
    ap.add_argument("--provision", action="store_true", help="clone (idempotently) the private cics-crucible at the "
                    "pin and the census repos under --root, then print the exports")  # fmt: skip
    ap.add_argument("--root", type=Path, help="the shared scratch root (default: $GG_SCRATCH, else "
                    "<worktrees dir>/_shared-scratch)")  # fmt: skip
    args = ap.parse_args(argv)
    root = scratch_root(args.root) if (args.provision or args.root) else None
    if args.provision and root is not None:
        try:
            rec = provision(root, log=lambda m: print(m, file=sys.stderr, flush=True))
        except ProvisionRefused as e:
            print(f"REFUSED: {e}", file=sys.stderr)
            return 2
        print(f"# provisioned {root}: cics-crucible {rec['pinned_ref']} ({rec['crucible']['sha'][:12]}), "
              f"{len(rec['census'])} census clones (provision.json)", file=sys.stderr)  # fmt: skip
        for err in rec["errors"]:
            print(f"# WARN: {err}", file=sys.stderr)
    try:
        env, notes = environment(args.crucible_dir or (root / "cics-crucible" if root and (root / "cics-crucible").is_dir()
                                                       else None), args.unpinned)  # fmt: skip
        if root is not None:
            env = provisioned_env(env, root)
    except JdkError as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2
    for n in notes:
        print(f"# note: {n}", file=sys.stderr)
    if not args.check:
        print("\n".join(shell_lines(env)))
        return 0
    results = checks(env)
    width = max(len(item) for item, _, _ in results)
    for item, ok, detail in results:
        print(f"{'WARN' if ok is None else 'PASS' if ok else 'FAIL'}  {item:<{width}}  {detail}")
    failed = [item for item, ok, _ in results if ok is False]
    warned = [item for item, ok, _ in results if ok is None]
    print(
        f"\n{sum(ok is True for _, ok, _ in results)}/{len(results)} pass"
        + (f"; WARN: {', '.join(warned)}" if warned else "")
        + (f"; FAIL: {', '.join(failed)}" if failed else "")
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
