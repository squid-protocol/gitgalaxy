"""Unpinned dependency installs in CI / pipeline files (#4918).

A pipeline step that installs "whatever the registry serves today" (pip / npm / gem / go / cargo with no
version, `curl | bash`, a `uses:` that is not a commit SHA) runs unreviewed code in the job that holds the
repository's source and secrets. This is a line-bounded structural scan, like every other GitGalaxy sensor:
no YAML parse, no shell parse. It reads one logical shell line at a time (backslash continuations joined,
comment lines dropped), so every pattern is anchored to the invoking verb and has nothing to backtrack over.

Pinned means an exact version (`==1.2`, `@1.2.3`, `-v 1.2`), a commit SHA, a hash-checked requirements file
(`--require-hashes`), or a local path / lockfile-driven install (`npm ci`, bare `npm install`, `pip install -e .`).
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
_SEMVER = re.compile(r"@\d[\w.\-+]*$")
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


def find_unpinned(content: str) -> list[tuple[int, str, str]]:
    """(1-indexed line, kind, snippet) for every unpinned dependency install in a pipeline file."""
    found: list[tuple[int, str, str]] = []
    for lineno, line in _logical_lines(content):
        if len(found) >= MAX_FINDINGS:
            break
        ref = _unpinned_uses(line)
        if ref is not None:
            found.append((lineno, "uses", f"uses: {ref}"))
            continue
        pipe = _PIPE_SHELL.search(line)
        if pipe:
            found.append((lineno, "curl-pipe-shell", pipe.group(0)[:120]))
            continue
        for cmd in _commands(line):
            for kind, verb, check in (
                ("pip", _PIP, _unpinned_pip),
                ("npm", _NPM, _unpinned_npm),
                ("gem", _GEM, _unpinned_gem),
                ("go", _GO, _unpinned_go),
                ("cargo", _CARGO, _unpinned_cargo),
            ):
                if verb.search(cmd):
                    spec = check(cmd)
                    if spec is not None:
                        found.append((lineno, kind, f"{kind} install {spec} (no pinned version)"))
    return found


def scan_pipeline(content: str) -> dict[str, Any]:
    """Same shape as SecurityLens.scan_content()'s return, for the single `unpinned_install` key."""
    hits = find_unpinned(content)
    return {
        "counts": {KEY: len(hits)},
        "snippets": {KEY: [snip for _, _, snip in hits]},
        "positions": {KEY: [ln for ln, _, _ in hits]},
    }
