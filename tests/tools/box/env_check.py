#!/usr/bin/env python3
"""env_check.py: is THIS machine set up the way the opt-in tests expect? (2026-11-23)

    python tests/tools/box/env_check.py            # check, print a PASS/MISSING table, exit 1 if a required item is missing
    python tests/tools/box/env_check.py --fix      # also do what can be done without sudo: sync the crucible pins and
                                                   # fetch the mainframe corpora this checkout's e2e cases read
    python tests/tools/box/env_check.py --exports  # only the `export ...` lines to source (run `eval "$(... --exports)"`)

Why: the porting-loop / equivalence e2e tests skip silently unless EQUIVALENCE_E2E=1, and fail on "not fetched at its pinned
ref" unless each checkout has fetched its corpora. On 2026-11-23 that read as "this box is missing Docker/Maven" when it had
both: one repo runs on two computers and they must behave alike. This checks the same things on any machine and prints the
exact command for each gap. It never installs system packages (no sudo): it reports them.

Stdlib only; works from any worktree (siblings are found through the git common dir, as sync-pins.sh does).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CRUCIBLES = {"language": "LANGUAGE_CRUCIBLE_PATH", "cics": "CICS_CRUCIBLE_PATH", "estate": "ESTATE_CRUCIBLE_PATH"}
CRUCIBLE_CORPORA = {"cics-crucible", "estate-crucible"}  # sibling checkouts, not clones under the corpora cache
CACHE_ENV = "GITGALAXY_MAINFRAME_CORPORA"  # tests/tools/mainframe_corpus.py's cache override
PREFERRED_JDK = 17  # the CI pin; melek also has 21 (a runtime that works for Maven only some of the time)


@dataclass
class Item:
    name: str
    ok: bool
    detail: str
    fix: str = ""
    required: bool = True


# ---- pure parts (unit-tested) ------------------------------------------------------------------------------------


def jdk_major(text: str) -> int | None:
    """Major version from `java -version` text or a /usr/lib/jvm directory name ('openjdk version "17.0.9"', 'java-21-...')."""
    m = re.search(r'version "(\d+)(?:\.(\d+))?', text)
    if m:
        major = int(m.group(1))
        return int(m.group(2) or 0) if major == 1 else major  # "1.8.0" is Java 8
    m = re.search(r"(?:java|jdk|openjdk)[-_]?(?:1\.)?(\d+)", text)
    return int(m.group(1)) if m else None


def pick_jdk(dirs: list[str], has_javac) -> str | None:
    """The JDK directory to use as JAVA_HOME: the preferred major (17) with a javac, else the lowest newer one with a javac."""
    found = sorted(((jdk_major(os.path.basename(d)), d) for d in dirs if has_javac(d)), key=lambda t: (t[0] or 0, t[1]))
    found = [(m, d) for m, d in found if m]
    for m, d in found:
        if m == PREFERRED_JDK:
            return d
    for m, d in found:
        if m > PREFERRED_JDK:
            return d
    return None


def corpora_needed(cases_dir: Path) -> list[str]:
    """Corpus names the committed equivalence cases read (their `corpus` field), minus the sibling crucibles."""
    names: set[str] = set()
    for p in sorted(cases_dir.glob("*/case.json")):
        try:
            c = json.loads(p.read_text(encoding="utf-8")).get("corpus")
        except (OSError, ValueError):
            continue
        if isinstance(c, str) and c not in CRUCIBLE_CORPORA:
            names.add(c)
    return sorted(names)


def ref_matches(head: str, ref: str) -> bool:
    """A clone's HEAD sha against a manifest ref (the manifest may hold a short sha)."""
    head, ref = head.strip().lower(), ref.strip().lower()
    return bool(head and ref) and (head.startswith(ref) or ref.startswith(head))


def render_table(items: list[Item]) -> str:
    width = max((len(i.name) for i in items), default=4)
    lines = []
    for i in items:
        state = "PASS   " if i.ok else ("MISSING" if i.required else "optional")
        lines.append(f"{state:8} {i.name:<{width}}  {i.detail}")
        if not i.ok and i.fix:
            lines.append(f"{'':8} {'':<{width}}  fix: {i.fix}")
    return "\n".join(lines)


def export_lines(env: dict[str, str]) -> str:
    return "\n".join(f"export {k}={shlex_quote(v)}" for k, v in env.items() if v)


def shlex_quote(v: str) -> str:
    return "'" + v.replace("'", "'\"'\"'") + "'" if re.search(r"[^\w@%+=:,./-]", v) else v


# ---- machine facts ----------------------------------------------------------------------------------------------


def sh(cmd: list[str], timeout: int = 30) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)  # noqa: S603
        return r.returncode, (r.stdout + r.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, str(e)


def primary_checkout() -> Path:
    rc, common = sh(["git", "-C", str(REPO), "rev-parse", "--git-common-dir"])
    p = Path(common) if rc == 0 else REPO / ".git"
    p = p if p.is_absolute() else REPO / p
    return p.resolve().parent


def sibling_dir() -> Path:
    return primary_checkout().parent


def venv_python() -> Path | None:
    for c in (os.environ.get("GG_VENV"), str(sibling_dir() / "venvs" / "selfscan"), str(REPO / ".venv")):
        if c and (Path(c) / "bin" / "python").exists():
            return Path(c) / "bin" / "python"
    return None


def crucible_path(key: str) -> Path:
    return Path(os.environ.get(CRUCIBLES[key]) or sibling_dir() / f"{key}-crucible")


def jvm_dirs() -> list[str]:
    return sorted(str(p) for p in Path("/usr/lib/jvm").glob("*") if p.is_dir() and not p.is_symlink())


def chosen_java_home() -> str | None:
    cur = os.environ.get("JAVA_HOME")
    if (
        cur
        and (Path(cur) / "bin" / "javac").exists()
        and jdk_major(sh([str(Path(cur) / "bin" / "java"), "-version"])[1]) == PREFERRED_JDK
    ):
        return cur
    return pick_jdk(jvm_dirs(), lambda d: (Path(d) / "bin" / "javac").exists())


def cache_root() -> Path:
    return Path(os.environ.get(CACHE_ENV) or REPO / ".mainframe_corpora").resolve()


def corpus_pins() -> dict[str, str]:
    data = json.loads((REPO / "tests" / "cobol_mainframe" / "corpora.json").read_text(encoding="utf-8"))
    return {c["name"]: str(c["ref"]) for c in data["corpora"]}


def seed_from_primary(name: str, ref: str, cache: Path) -> bool:
    """Fetch `ref` of corpus `name` from the primary checkout's own cache into this cache. True when HEAD is then at the pin."""
    src = primary_checkout() / ".mainframe_corpora" / name
    dest = cache / name
    if src.resolve() == dest.resolve() or not (src / ".git").exists() or not dest.exists():
        return False
    if sh(["git", "-C", str(dest), "fetch", "-q", "--depth", "1", str(src), ref], timeout=300)[0] != 0:
        return False
    if sh(["git", "-C", str(dest), "checkout", "-q", "--detach", "FETCH_HEAD"])[0] != 0:
        return False
    head = sh(["git", "-C", str(dest), "rev-parse", "HEAD"])
    return head[0] == 0 and ref_matches(head[1], ref)


# ---- the checks -------------------------------------------------------------------------------------------------


def check_all(fix: bool) -> tuple[list[Item], dict[str, str]]:
    items: list[Item] = []
    env: dict[str, str] = {}

    py = venv_python()
    items.append(
        Item(
            "python venv (selfscan)",
            py is not None,
            str(py) if py else "no venv found",
            f"python3 -m venv {sibling_dir() / 'venvs' / 'selfscan'} && <that>/bin/pip install -e {REPO}  (or set GG_VENV)",
        )
    )
    if py:
        env["PATH_PREPEND"] = str(py.parent)

    items.append(Item("git", shutil.which("git") is not None, shutil.which("git") or "not on PATH", "install git"))

    docker = shutil.which("docker")
    rc, out = sh(["docker", "info", "--format", "{{.ServerVersion}}"]) if docker else (127, "")
    items.append(
        Item(
            "docker",
            docker is not None and rc == 0,
            f"server {out}" if rc == 0 else (out[:80] or "not on PATH"),
            "install Docker and add your user to the docker group (needs sudo; not done here)",
        )
    )

    jh = chosen_java_home()
    jmaj = jdk_major(sh([f"{jh}/bin/java", "-version"])[1]) if jh else None
    items.append(
        Item(
            "JDK 17 + javac",
            jh is not None,
            f"JAVA_HOME={jh} (Java {jmaj})" if jh else "no JDK with javac under /usr/lib/jvm",
            "sudo apt install openjdk-17-jdk (needs sudo; not done here)",
        )
    )
    if jh:
        env["JAVA_HOME"] = jh

    mvn = shutil.which("mvn")
    items.append(
        Item("maven", mvn is not None, mvn or "not on PATH", "sudo apt install maven (needs sudo; not done here)")
    )

    rc, out = sh(["ctags", "--version"]) if shutil.which("ctags") else (127, "")
    items.append(
        Item(
            "universal-ctags",
            "Universal" in out,
            out.splitlines()[0][:60] if out else "not on PATH",
            "sudo apt install universal-ctags (needs sudo; not done here)",
        )
    )

    # crucible siblings at their pins
    pins_py = REPO / "tests" / "tools" / "crucible_pins.py"
    rc, out = sh([sys.executable, str(pins_py), "check", "--no-gh"], timeout=60)
    if rc != 0 and fix:
        sh(["bash", str(REPO / "tests" / "tools" / "box" / "sync-pins.sh")], timeout=900)
        rc, out = sh([sys.executable, str(pins_py), "check", "--no-gh"], timeout=60)
    bad = [ln for ln in out.splitlines() if not ln.startswith(("ok", "note"))]
    items.append(
        Item(
            "crucible checkouts at pins",
            rc == 0,
            "language, cics, estate on their pins" if rc == 0 else "; ".join(bad)[:160],
            "bash tests/tools/box/sync-pins.sh   (or re-run this with --fix)",
        )
    )
    for key, var in CRUCIBLES.items():
        env[var] = str(crucible_path(key))
    env["EQUIVALENCE_E2E"] = "1"

    # mainframe corpora this checkout's cases read
    needed = corpora_needed(REPO / "tests" / "equivalence")
    pins = corpus_pins()
    cache = cache_root()

    def present(name: str) -> bool:
        head = sh(["git", "-C", str(cache / name), "rev-parse", "HEAD"])
        return head[0] == 0 and name in pins and ref_matches(head[1], pins[name])

    missing = [n for n in needed if n in pins and not present(n)]
    if missing and fix and py:
        sh([str(py), str(REPO / "tests" / "tools" / "mainframe_corpus.py"), "fetch", *missing], timeout=1800)
        missing = [n for n in needed if n in pins and not present(n)]
    if (
        missing and fix
    ):  # an upstream that vanished (example-health-apis, 2026-11): copy the pinned commit from the primary checkout's cache
        seeded = [n for n in missing if seed_from_primary(n, pins[n], cache)]
        missing = [n for n in missing if n not in seeded]
    items.append(
        Item(
            "mainframe corpora (this checkout)",
            not missing,
            f"{len(needed) - len(missing)}/{len(needed)} fetched at their pins in {cache}"
            + (f"; missing: {', '.join(missing)}" if missing else ""),
            f"python tests/tools/mainframe_corpus.py fetch {' '.join(missing)}   (or --fix; set {CACHE_ENV} to share one cache across worktrees)",
        )
    )
    if os.environ.get(CACHE_ENV):
        env[CACHE_ENV] = os.environ[CACHE_ENV]
    return items, env


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fix", action="store_true", help="sync crucible pins and fetch missing corpora (no sudo)")
    ap.add_argument("--exports", action="store_true", help="print only the export lines")
    args = ap.parse_args(argv)
    items, env = check_all(fix=args.fix)
    path_prepend = env.pop("PATH_PREPEND", "")
    lines = export_lines(env)
    if path_prepend:
        lines += f'\nexport PATH={shlex_quote(path_prepend)}:"$PATH"'
    if args.exports:
        print(lines)
        return 0
    print(f"environment check: {REPO}\n")
    print(render_table(items))
    print(
        '\nTo use this setup in your shell:\n  eval "$(python tests/tools/box/env_check.py --exports)"\nwhich sets:\n'
        + "\n".join("  " + ln for ln in lines.splitlines())
    )
    gaps = [i for i in items if i.required and not i.ok]
    print(f"\n{'ALL REQUIRED ITEMS PRESENT' if not gaps else f'{len(gaps)} required item(s) missing'}")
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
