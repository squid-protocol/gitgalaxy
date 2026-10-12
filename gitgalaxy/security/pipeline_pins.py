"""Unpinned dependency installs in CI / pipeline files (#4918).

A pipeline step that installs "whatever the registry serves today" (pip / npm / gem / go / cargo with no
version, `curl | bash`, a `uses:` that is not a commit SHA) runs unreviewed code in the job that holds the
repository's source and secrets. This is a line-bounded structural scan, like every other GitGalaxy sensor:
no YAML parse, no shell parse. It reads one logical shell line at a time (backslash continuations joined,
comment lines dropped), so every pattern is anchored to the invoking verb and has nothing to backtrack over.

The same rule runs on four surfaces (#4944): pipeline YAML, Dockerfiles (`RUN` lines), shell scripts, and GitLab CI
(`image:` without a digest, `include: project:` without a `ref:`, `include: component:` without a version). System
package installs (`apt-get` / `apt` / `apk add` / `brew install`) are checked on all three command surfaces. A
`$VAR` / `$(...)` / `${{ expr }}` package name is not flagged for those: its value is unknowable from the text.

Pinned means an exact version (`==1.2`, `@1.2.3`, `-v 1.2`), a commit SHA, a hash-checked requirements file
(`--require-hashes`), `pkg=1.2.3` (apt, apk), `formula@3.12` (brew), `image@sha256:...`, or a local path / lockfile-driven install (`npm ci`, bare `npm install`, `pip install -e .`).
`pip install -r file` / `-c file` is trusted: the file is the pin and is checked on its own.

`scan_pipeline(content)` returns the same {"counts", "snippets", "positions"} shape SecurityLens.scan_content
does, under one key, `unpinned_install`, so galaxyscope folds it into the shared threat ledger and the SARIF
recorder emits `GG-SAST-UNPINNED_INSTALL` with a line number per finding.
"""

from __future__ import annotations

import re
import shlex
from typing import Any

KEY = "unpinned_install"
MAX_FINDINGS = 100
# A finding is never reported for an unpinned install of one of these first-party shapes.
_SHA = re.compile(r"^[0-9a-f]{40}$")
_USES = re.compile(r"^\s*-?\s*uses:\s*['\"]?([^\s'\"#]+)")
_PIP = re.compile(r"\bpip3?[ \t]+install\b")
_NPM = re.compile(r"\b(npm|pnpm|yarn)[ \t]+(?:(?:install|i|add)\b|dlx\b)|\bnpx[ \t]")
_GEM = re.compile(r"\bgem[ \t]+install\b")
_GO = re.compile(r"\bgo[ \t]+(?:install|get)\b")
_CARGO = re.compile(r"\bcargo[ \t]+install\b")
_PIPE_SHELL = re.compile(
    r"\b(?:curl|wget)\b[^|\n]{0,300}\|[ \t]*(?:sudo[ \t]+)?(?:ba|z|da)?sh\b"
    r"|\b(?:ba|z)?sh[ \t]+<\([ \t]*(?:curl|wget)\b"
    r"|\b(?:ba|z)?sh[ \t]+-c[ \t]+[\"']?\$\([ \t]*(?:curl|wget)\b"
)
_APT = re.compile(r"\bapt(?:-get)?\b.{0,100}?[ \t]install\b")
_APK = re.compile(r"\bapk[ \t]+(?:-\S+[ \t]+)*add\b")
_BREW = re.compile(r"\bbrew[ \t]+install\b")
_SEMVER = re.compile(r"@(?:\d[\w.\-+]*|\$\{?\w+\}?)$")  # `@1.2.3`, or `@${PIN}` set by the script
_PIP_PINNED = re.compile(r"^[A-Za-z0-9_.\-]+(?:\[[^\]]+\])?==[^=<>!~]+$")
_VALUE_OPTS = {"-r", "--requirement", "-c", "--constraint", "-e", "--editable", "-i", "--index-url", "-t", "--target"}


def _logical_lines(content: str):
    """Yield (1-indexed first line, command text) for each shell logical line, split at && / ; / ||."""
    buf, start = "", 0
    for n, raw in enumerate(content.splitlines(), 1):
        if len(raw) > 2000:
            continue
        s = raw.strip()
        if not buf and s.startswith("#"):
            continue
        s = re.sub(r"^(?:-[ \t]+)+", "", s)
        if not buf:
            start = n
        if s.endswith("\\"):
            buf += s[:-1] + " "
            continue
        full, buf = buf + s, ""
        yield start, full


def _commands(line: str):
    for part in re.split(r"&&|;|\|\|", line):
        part = part.strip()
        if part:
            yield part


def _argv(command: str, verb: re.Pattern) -> list[str] | None:
    m = verb.search(command)
    if not m:
        return None
    try:
        return shlex.split(command[m.end() :])
    except ValueError:
        return command[m.end() :].split()


def _is_local(spec: str) -> bool:
    return (
        spec in (".", "..")
        or spec.startswith(("./", "../", "/", "file:"))
        or bool(re.match(r"^\.?/?[\w./\-]*\[[\w,\-]+\]$", spec))
    )


def _unpinned_pip(command: str) -> str | None:
    toks = _argv(command, _PIP)
    if toks is None or "--require-hashes" in toks:
        return None
    specs, i = [], 0
    while i < len(toks):
        t = toks[i]
        if t in _VALUE_OPTS:
            if t in ("-e", "--editable") and i + 1 < len(toks):
                specs.append(toks[i + 1])
            i += 2
            continue
        if not t.startswith("-"):
            specs.append(t)
        i += 1
    for spec in specs:
        if _is_local(spec) or _PIP_PINNED.match(spec) or re.match(r"^[\w\-.\[\],]+==\$\{?\w+\}?$", spec):
            continue
        if spec.startswith("git+") and re.search(r"@[0-9a-f]{40}\b", spec):
            continue
        return spec
    return None


def _unpinned_npm(command: str) -> str | None:
    m = _NPM.search(command)
    if not m:
        return None
    try:
        toks = shlex.split(command[m.end() :])
    except ValueError:
        toks = command[m.end() :].split()
    if m.group(0).startswith("npx") or m.group(0).split()[-1] == "dlx":
        pkgs = [t for t in toks if not t.startswith("-")][:1]
    else:
        pkgs = [t for t in toks if not t.startswith("-")]
    for pkg in pkgs:  # a bare `npm install` is lockfile-driven: no package named, nothing to flag
        if pkg.startswith((".", "/", "file:")) or _SEMVER.search(pkg):
            continue
        return pkg
    return None


def _unpinned_gem(command: str) -> str | None:
    m = _GEM.search(command)
    if not m:
        return None
    rest = command[m.end() :]
    if re.search(r"(?:^|[ \t])(?:-v|--version)(?:[ \t=]|$)", rest):
        return None
    names = [t for t in rest.split() if not t.startswith("-")]
    return names[0] if names and not _is_local(names[0]) else None


def _unpinned_go(command: str) -> str | None:
    m = _GO.search(command)
    if not m:
        return None
    for t in command[m.end() :].split():
        if t.startswith("-"):
            continue
        if _is_local(t) or t in ("all",) or t.startswith(("$", "-")):
            continue
        return t if not re.search(r"@v?\d", t) and not re.search(r"@[0-9a-f]{7,40}$", t) else None
    return None


def _unpinned_cargo(command: str) -> str | None:
    m = _CARGO.search(command)
    if not m:
        return None
    rest = command[m.end() :]
    if re.search(r"--(?:version|path|git)\b", rest) or re.search(r"\w@\d", rest):
        return None
    names = [t for t in rest.split() if not t.startswith("-")]
    return names[0] if names else None


def _system_specs(command: str, verb: re.Pattern, value_opts: frozenset[str]) -> list[str]:
    m = verb.search(command)
    if not m:
        return []
    rest = re.sub(r"\$\{\{.*?\}\}|\$\(.*?\)|`[^`]*`", "$X", command[m.end() :])
    try:
        toks = shlex.split(rest)
    except ValueError:
        toks = rest.split()
    specs, i = [], 0
    while i < len(toks):
        t = toks[i]
        if t in value_opts:
            i += 2
            continue
        if not t.startswith("-") and "$" not in t and "`" not in t:
            specs.append(t)
        i += 1
    return [s for s in specs if not _is_local(s) and not s.endswith(".deb")]


def _unpinned_apt(command: str) -> str | None:
    for spec in _system_specs(command, _APT, frozenset({"-o", "-t", "-c", "--target-release"})):
        if not re.match(r"^[\w.+\-:]+=[^=\s]+$", spec):  # `pkg=1.2.3`; `pkg/release` and bare `pkg` float
            return spec
    return None


def _unpinned_apk(command: str) -> str | None:
    opts = frozenset({"-t", "--virtual", "-X", "--repository", "-p", "--root"})
    for spec in _system_specs(command, _APK, opts):
        if not re.match(r"^[\w.+\-]+(?:=|~=)[^=\s]+$", spec):  # `pkg=1.2.3-r0`, `pkg~=1.2`
            return spec
    return None


def _unpinned_brew(command: str) -> str | None:
    for spec in _system_specs(command, _BREW, frozenset()):
        if not re.search(r"@\d[\w.]*$", spec):  # brew's only pin is a versioned formula, `python@3.12`
            return spec
    return None


def _unpinned_uses(line: str) -> str | None:
    m = _USES.match(line)
    if not m:
        return None
    ref = m.group(1)
    if ref.startswith("./") or "${{" in ref:
        return None
    if ref.startswith("docker://"):
        return None if "@sha256:" in ref else ref
    _, sep, version = ref.partition("@")
    return None if sep and _SHA.match(version) else ref


_GL_IMAGE = re.compile(r"^\s*image:[ \t]*(?:['\"]?([^\s'\"#]+))?")
_GL_NAME = re.compile(r"^\s*name:[ \t]*['\"]?([^\s'\"#]+)")
_GL_ITEM = re.compile(r"^(\s*)-\s+(\w+):[ \t]*(.*)")
_GL_KEY = re.compile(r"^(\s*)(\w+):[ \t]*['\"]?([^\s'\"#]*)")


def is_gitlab_ci(rel_path: str) -> bool:
    """`.gitlab-ci.yml`, `*.gitlab-ci.yml`, or any YAML under a `gitlab` / `.gitlab` directory."""
    parts = rel_path.replace("\\", "/").lower().split("/")
    return (
        parts[-1].startswith(".gitlab-ci")
        or parts[-1].endswith((".gitlab-ci.yml", ".gitlab-ci.yaml"))
        or any(p in ("gitlab", ".gitlab") for p in parts[:-1])
    )


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _unpinned_image(ref: str) -> bool:
    return "$" not in ref and "@sha256:" not in ref


def find_unpinned_gitlab(content: str) -> list[tuple[int, str, str]]:
    """GitLab CI: `image:` without a digest, `include: project:` without `ref:`, `include: component:` unversioned."""
    lines = [ln if len(ln) <= 2000 else "" for ln in content.splitlines()]
    found: list[tuple[int, str, str]] = []
    for i, raw in enumerate(lines):
        if len(found) >= MAX_FINDINGS:
            break
        if raw.lstrip().startswith("#"):
            continue
        m = _GL_IMAGE.match(raw)
        if m:
            ref = m.group(1)
            if ref is None:  # block form: `image:` then an indented `name:`
                for nxt in lines[i + 1 : i + 6]:
                    if nxt.strip() and _indent(nxt) <= _indent(raw):
                        break
                    n = _GL_NAME.match(nxt)
                    if n:
                        ref = n.group(1)
                        break
            if ref and _unpinned_image(ref):
                found.append((i + 1, "gitlab-image", f"image: {ref} (no @sha256 digest)"))
            continue
        item = _GL_ITEM.match(raw)
        if not item or item.group(2) not in ("project", "component", "file", "ref", "remote", "local", "template"):
            continue
        # the include item's keys: this line plus the following lines indented deeper than the dash
        dash = len(item.group(1))
        block = [(i, raw)]
        for j in range(i + 1, min(i + 12, len(lines))):
            if lines[j].strip() and _indent(lines[j]) <= dash:
                break
            block.append((j, lines[j]))
        keys: dict[str, str] = {}
        for k, (_, text) in enumerate(block):
            km = _GL_ITEM.match(text) if k == 0 else _GL_KEY.match(text)
            if km:
                keys.setdefault(km.group(2), km.group(3))
        if "project" in keys and "ref" not in keys:
            found.append((i + 1, "gitlab-include", f"include project: {keys['project']} (no ref:)"))
        comp = keys.get("component")
        if comp and "$" not in comp and not re.search(r"@(?!~?latest\b)[^\s@]+$", comp):
            found.append((i + 1, "gitlab-include", f"include component: {comp} (no version)"))
    return found


def find_unpinned(content: str, kind: str = "yaml", gitlab: bool = False) -> list[tuple[int, str, str]]:
    """(1-indexed line, kind, snippet) for every unpinned dependency install in a pipeline-ish file.

    `kind` is the surface: "yaml" (pipeline YAML, which also carries `uses:`), "dockerfile" or "shell"
    (command lines only). `gitlab` adds the GitLab CI image / include checks to a YAML surface.
    """
    found: list[tuple[int, str, str]] = []
    for lineno, line in _logical_lines(content):
        if len(found) >= MAX_FINDINGS:
            break
        if kind == "yaml":
            ref = _unpinned_uses(line)
            if ref is not None:
                found.append((lineno, "uses", f"uses: {ref}"))
                continue
        pipe = _PIPE_SHELL.search(line)
        if pipe:
            found.append((lineno, "curl-pipe-shell", pipe.group(0)[:120]))
            continue
        for cmd in _commands(line):
            for ckind, verb, check in (
                ("pip", _PIP, _unpinned_pip),
                ("npm", _NPM, _unpinned_npm),
                ("gem", _GEM, _unpinned_gem),
                ("go", _GO, _unpinned_go),
                ("cargo", _CARGO, _unpinned_cargo),
                ("apt", _APT, _unpinned_apt),
                ("apk", _APK, _unpinned_apk),
                ("brew", _BREW, _unpinned_brew),
            ):
                if verb.search(cmd):
                    spec = check(cmd)
                    if spec is not None:
                        found.append((lineno, ckind, f"{ckind} install {spec} (no pinned version)"))
    if gitlab and kind == "yaml":
        found = sorted(found + find_unpinned_gitlab(content))[:MAX_FINDINGS]
    return found


def scan_pipeline(content: str, lang_id: str = "yaml", rel_path: str = "") -> dict[str, Any]:
    """Same shape as SecurityLens.scan_content()'s return, for the single `unpinned_install` key."""
    hits = find_unpinned(content, lang_id, lang_id == "yaml" and is_gitlab_ci(rel_path))
    return {
        "counts": {KEY: len(hits)},
        "snippets": {KEY: [snip for _, _, snip in hits]},
        "positions": {KEY: [ln for ln, _, _ in hits]},
    }
