#!/usr/bin/env python3
"""The environment of an equivalence / CICS crucible run from a worktree, printed or checked -- so a slice agent does
not hand-write an env.sh with the wrong JDK or a stale crucible path (#4270).

    python tests/tools/equivalence_env.py --shell                       # `export` lines: eval "$(... --shell)"
    python tests/tools/equivalence_env.py --shell --crucible-dir DIR --unpinned   # a private cics-crucible checkout
    python tests/tools/equivalence_env.py --check                       # PASS / FAIL per item, exit 1 on a FAIL

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
so it is checked too.
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
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
            "CICS_CRUCIBLE_ALLOW_UNPINNED", "JAVA_HOME", "JDK_17")  # fmt: skip


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


def checks(env: dict[str, str]) -> list[tuple[str, bool, str]]:
    """[(item, ok, detail)]."""
    out: list[tuple[str, bool, str]] = []
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
    import _cics_crucible_pin as cics_pin
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
    cc = Path(env["CICS_CRUCIBLE_PATH"])
    if not (cc / ".git").exists() and not (cc / "SPEC.md").is_file():
        out.append(("cics-crucible", False, f"no checkout at {cc} (set CICS_CRUCIBLE_PATH or --crucible-dir)"))
    else:
        msg = pin_message(cics_pin, cc, env)
        note = (
            "unpinned (CICS_CRUCIBLE_ALLOW_UNPINNED=1)"
            if env.get(cics_pin.ALLOW_UNPINNED_ENV)
            else f"at {cics_pin.PINNED_REF}"
        )
        out.append(("cics-crucible", msg is None, f"{cc} {note}" if msg is None else msg))
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--shell", action="store_true", help="print `export` lines (the default output)")
    ap.add_argument("--check", action="store_true", help="verify the environment: PASS / FAIL per item")
    ap.add_argument("--crucible-dir", type=Path, help="CICS_CRUCIBLE_PATH: a private cics-crucible checkout")
    ap.add_argument("--unpinned", action="store_true", help="CICS_CRUCIBLE_ALLOW_UNPINNED=1 (an off-pin checkout)")
    args = ap.parse_args(argv)
    try:
        env, notes = environment(args.crucible_dir, args.unpinned)
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
        print(f"{'PASS' if ok else 'FAIL'}  {item:<{width}}  {detail}")
    failed = [item for item, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} pass" + (f"; FAIL: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
