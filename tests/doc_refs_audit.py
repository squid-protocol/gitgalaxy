#!/usr/bin/env python3
"""
Doc Reference Auditor: hand-written markdown that names something the repo no longer has.

The 2026-11-03 docs sweep (#7617) fixed 113 files. About 80% of what it found was mechanical: a backticked path
that moved (`language_standards.py` became a package and stayed stale in ~30 files), a script flag or workflow that
was removed, a dead relative link, a package README with no row for a module added since. The one wiki page that had
not drifted was the CLI reference, because `test_cli_contract.py` pins it. This audit pins the rest.

USAGE
    python tests/doc_refs_audit.py                  # full report; exits 1 on any finding
    python tests/doc_refs_audit.py --ci             # baseline-gated: fails only on findings not in the baseline
    python tests/doc_refs_audit.py --write-baseline # accept the current findings (after fixing what you can)
    python tests/doc_refs_audit.py --json           # findings as JSON (the nightly drift job files issues from it)

CHECKS (each finding is `check | doc | target`; the key holds no line number, so editing elsewhere in a doc does
not churn the baseline)
    path    a backticked repo path (`tests/tools/x.py`, `docs/foo.md`, `gitgalaxy/core/`) that is not tracked,
            not a directory of tracked files, and not gitignored (an ignored path is produced at run time), when
            its folder exists here (`tests/http/x.py` in a note about another project has no folder here).
    link    a relative markdown link, or a github.com/squid-protocol/gitgalaxy blob|tree/main URL, whose target is
            missing.
    flag    `python <script>.py ... --flag` (or `python -m gitgalaxy.x.y --flag`) where the script's text, and
            the .py files beside it, never spell "--flag".
    name    a bare backticked `name.py` that no tracked file is called (not checked in ABOUT_OTHERS write-ups,
            whose names are other projects' files; .md / .yml names are left out, since docs name the reports and
            configs a run writes).
    skill   "the `x` skill" / "skill `x`" for a skill that has no .claude/skills/x/ and is not in the
            docs/ecosystem.md skills table (skills that live in a sibling repo are listed there).
    module  a package README (gitgalaxy/**/README.md) that never names one of the public .py modules beside it.

SCOPE
Generated pages are skipped (GENERATED below): fix their generator, not the page. A paragraph that names a sibling repo
(SIBLING_REPOS) skips the path / name / flag checks: `tools/bias_report.py` in a keyword-rosetta sentence is that
repo's path. Placeholders (`<lang>`, `*`, `{x}`, `$VAR`, `...`) are never checked. Text inside a fenced block is
checked for paths and flags but not for links.

To fix a finding, edit the doc (or the code, if the doc was right). If a finding is wrong, narrow the check here
rather than baselining it. Stdlib only: the workflow runs it without installing the package.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = Path(__file__).resolve().parent / "doc_refs_audit_baseline.json"

# Pages a script writes. Their drift is the generator's, and a hand edit is overwritten.
GENERATED = (
    "docs/language_status/*",
    "*/evidence_report/*",
    "docs/wiki/agents/*",
    "docs/wiki/LLM-reports/*",
    "docs/signal_contracts.md",
    "docs/self_scan/tri_comparison_points_of_interest.md",
    "docs/unicode_gauntlet/report.md",
    "docs/wiki/08-03-transforming-regex-counts.md",
    "language-crucible-local/*",
)
# Paths published only to the `generated` branch (tests/tools/generated_branch.py), never in a checkout.
GENERATED_BRANCH = (
    "docs/language_status/*",
    "docs/gitgalaxy_architecture_brief.md",
)
# Findings that are right as written, by key, with the reason. Prefer narrowing a check to growing this.
ALLOWED = {
    "path | CLAUDE.md | tests/core_engine/test_foo.py": "an example test id in the commands block",
    "path | tests/README.md | tests/__init__.py": "says the file must not exist",
    "path | docs/agents/language-signatures.md | tests/__init__.py": "says the file must not exist",
    "link | gitgalaxy/standards/how_to_add_a_language.md | gitgalaxy/standards/b.md": "example of the lit_links signal",
    "link | gitgalaxy/standards/how_to_add_a_language.md | gitgalaxy/standards/img.png": "example of the lit_links signal",
}
# Third-party and fixture markdown: not ours to keep current.
FOREIGN = (
    "tests/cics_crucible/fixture/*",
    "tests/cobol_mainframe/refraction_excerpts/*",
    "tests/cobol_mainframe/port_invariance/*",
    "tests/fixtures/*",
    "*/data/*",
)
# Write-ups about other projects' code (teardowns, studies): their bare file names are those projects' files.
ABOUT_OTHERS = ("docs/wiki/museum-of-code/*", "docs/research/*", "docs/benchmarks/*")
SIBLING_REPOS = (
    "keyword-rosetta",
    "language-crucible",
    "cics-crucible",
    "estate-crucible",
    "temporal-crucible",
    "population-analyses",
    "gitgalaxy-raw-output",
    "squid-telemetry",
    "squid-bot",
    "agent-habits",
    "promoter-bot",
)
REPO_DIRS = ("gitgalaxy", "tests", "docs", ".github", ".claude", "scripts", "ci", "site", "templates", "estate")
NAME_SUFFIXES = (".py",)  # output files (.md reports, .yml configs) are named in docs without existing here
GITHUB_URL = re.compile(r"https://github\.com/squid-protocol/gitgalaxy/(?:blob|tree)/main/([^\s)#?\"'>]+)")
LINK = re.compile(r"(?<!!)\[[^\]\n]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)|^\s*\[[^\]\n]+\]:\s*(\S+)", re.M)
IMAGE = re.compile(r"!\[[^\]\n]*\]\(([^)\s]+)\)")
SPAN = re.compile(r"`([^`\n]+)`")
FENCE = re.compile(r"^\s*(```|~~~)")
PLACEHOLDER = re.compile(r"[<>*{}$\[\]|]|\.\.\.|…|\bN\b|XXXX")
SKILL_REF = re.compile(r"`/?([a-z][a-z0-9-]+)`\s+skill\b|\bskill\s+`/?([a-z][a-z0-9-]+)`")
FLAG = re.compile(r"(?<![\w-])(--[a-z][a-z0-9-]*)")
SCRIPT = re.compile(r"(?:^|\s)(?:python3?\s+)?((?:\./)?[\w./-]+\.py)\b|python3?\s+-m\s+(gitgalaxy(?:\.\w+)+)")
COMMAND_END = re.compile(r"\s(?:\||&&|;|#|>)\s")


@dataclass(frozen=True)
class Finding:
    check: str
    doc: str
    line: int
    target: str

    @property
    def key(self) -> str:
        return f"{self.check} | {self.doc} | {self.target}"


class Repo:
    """Tracked files, their directories, and a gitignore oracle, read once."""

    def __init__(self, root: Path = REPO_ROOT, files: list[str] | None = None):
        self.root = root
        self.files = set(files if files is not None else _git(root, "ls-files", "-z").split("\0")) - {""}
        self.dirs = {p.rsplit("/", i)[0] for p in self.files for i in range(1, p.count("/") + 1)}
        self.basenames = {p.rsplit("/", 1)[-1] for p in self.files}
        self._ignored: dict[str, bool] = {}
        self._text: dict[str, str] = {}

    def exists(self, path: str) -> bool:
        path = path.strip("/")
        if _matches(path, GENERATED_BRANCH):
            return True
        return path in self.files or path in self.dirs or (self.root / path).exists() or self.ignored(path)

    def has_parent(self, path: str) -> bool:
        """Does the path's folder exist here? `tests/http/test_ws.py` in a note about another project has none."""
        path = path.strip("/")
        return "/" in path and path.rsplit("/", 1)[0] in self.dirs

    def ignored(self, path: str) -> bool:
        if path not in self._ignored:
            try:
                proc = subprocess.run(  # noqa: S603
                    ["git", "check-ignore", "--no-index", path, path.rstrip("/") + "/"],  # noqa: S607
                    cwd=self.root,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self._ignored[path] = bool(proc.stdout.strip())
            except OSError:
                self._ignored[path] = False
        return self._ignored[path]

    def text(self, path: str) -> str:
        if path not in self._text:
            try:
                self._text[path] = (self.root / path).read_text(
                    encoding="utf-8", errors="surrogateescape"
                )  # lossless (#3813); stdlib only
            except OSError:
                self._text[path] = ""
        return self._text[path]


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True)  # noqa: S603, S607
    return proc.stdout


def _matches(path: str, globs: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(path, g) for g in globs)


def docs_in_scope(repo: Repo) -> list[str]:
    return sorted(
        p for p in repo.files if p.lower().endswith(".md") and not _matches(p, GENERATED) and not _matches(p, FOREIGN)
    )


def _clean_token(tok: str) -> str:
    tok = tok.strip().strip("\"'(),;.")
    tok = re.sub(r"::.*$", "", tok)  # pytest node id
    tok = re.sub(r":\d+(?:-\d+)?$", "", tok)  # file:line
    tok = re.sub(r"#L\d+.*$", "", tok)
    return tok.removeprefix("./")


def _repo_path(tok: str) -> str | None:
    if PLACEHOLDER.search(tok) or "//" in tok or tok.startswith(("http", "~", "/")):
        return None
    head = tok.split("/", 1)[0]
    if head in REPO_DIRS and "/" in tok and re.fullmatch(r"[\w.@+/-]+", tok):
        return tok
    return None


def _skills(repo: Repo) -> set[str]:
    names = {p.split("/")[2] for p in repo.files if p.startswith(".claude/skills/") and p.count("/") >= 3}
    eco = repo.text("docs/ecosystem.md")
    names |= set(re.findall(r"`/?([a-z][a-z0-9-]+)`", eco))
    return names


def _flag_known(repo: Repo, script: str, flag: str) -> bool:
    """Is the flag spelled in the script, or in a .py beside it (a shared argument helper)? A prefix of a longer
    flag does not count: `--update` is not `--update-baseline`."""
    spelled = re.compile(rf"(?<![\w-]){re.escape(flag)}(?![\w-])")
    if spelled.search(repo.text(script)):
        return True
    folder = script.rsplit("/", 1)[0] if "/" in script else ""
    return any(
        spelled.search(repo.text(p))
        for p in repo.files
        if p.endswith(".py") and p.rsplit("/", 1)[0] == folder and p != script
    )


def _module_path(repo: Repo, module: str) -> str | None:
    base = module.replace(".", "/")
    for cand in (f"{base}.py", f"{base}/__main__.py", f"{base}/__init__.py"):
        if cand in repo.files:
            return cand
    return None


def _check_commands(repo: Repo, doc: str, lineno: int, text: str, out: list[Finding]) -> None:
    for segment in COMMAND_END.split(" " + text + " "):
        m = SCRIPT.search(segment)
        if not m:
            continue
        if m.group(2):
            script = _module_path(repo, m.group(2))
        else:
            tok = _clean_token(m.group(1))
            script = tok if tok in repo.files else None
        if not script:
            continue  # a missing script is the path check's finding, not a flag finding
        for flag in FLAG.findall(segment[m.end() :]):
            if flag in ("--help", "--version"):
                continue
            if not _flag_known(repo, script, flag):
                out.append(Finding("flag", doc, lineno, f"{script} {flag}"))


def _check_link(repo: Repo, doc: str, lineno: int, target: str, out: list[Finding]) -> None:
    gh = GITHUB_URL.match(target)
    if gh:
        path = gh.group(1).rstrip("/")
    elif target.startswith(("http:", "https:", "mailto:", "#", "data:")) or "://" in target:
        return
    else:
        target = target.split("#", 1)[0].split("?", 1)[0].strip("<>")
        if not target or PLACEHOLDER.search(target):
            return
        base = Path(doc).parent
        path = (base / target).as_posix() if not target.startswith("/") else target.lstrip("/")
        parts: list[str] = []
        for part in path.split("/"):
            if part == "..":
                if not parts:
                    out.append(Finding("link", doc, lineno, target))
                    return
                parts.pop()
            elif part not in ("", "."):
                parts.append(part)
        path = "/".join(parts)
    if not repo.exists(path):
        out.append(Finding("link", doc, lineno, path))


def _sibling_paragraphs(lines: list[str]) -> list[bool]:
    """Per line: does its paragraph (a run of non-blank lines) name a sibling repo? A sentence about keyword-rosetta's
    `docs/GATING.md` often wraps, so the repo's name and the path sit on different lines."""
    out = [False] * len(lines)
    start = 0
    for i in range(len(lines) + 1):
        if i == len(lines) or not lines[i].strip():
            hit = any(name in ln for ln in lines[start:i] for name in SIBLING_REPOS)
            for j in range(start, i):
                out[j] = hit
            start = i + 1
    return out


def audit_doc(repo: Repo, doc: str, skills: set[str]) -> list[Finding]:
    out: list[Finding] = []
    in_fence = False
    lines = repo.text(doc).splitlines()
    front = 0
    if lines and lines[0].strip() == "---":  # YAML frontmatter: SEO descriptions hold truncated link text
        front = next((i for i, ln in enumerate(lines[1:], 2) if ln.strip() == "---"), 0)
    about_others = _matches(doc, ABOUT_OTHERS)
    sibling_para = _sibling_paragraphs(lines)
    for lineno, line in enumerate(lines, 1):
        if lineno <= front:
            continue
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        sibling = sibling_para[lineno - 1]
        if not in_fence:
            prose = SPAN.sub("``", line)  # link syntax inside a code span is an example, not a link
            for m in LINK.finditer(prose):
                _check_link(repo, doc, lineno, m.group(1) or m.group(2), out)
            for m in IMAGE.finditer(prose):
                _check_link(repo, doc, lineno, m.group(1), out)
            for m in GITHUB_URL.finditer(prose):
                if not any(m.group(0) in (lm.group(1) or lm.group(2) or "") for lm in LINK.finditer(prose)):
                    _check_link(repo, doc, lineno, m.group(0), out)
            for m in SKILL_REF.finditer(line):
                name = m.group(1) or m.group(2)
                if name not in skills:
                    out.append(Finding("skill", doc, lineno, name))
        if sibling:
            continue
        spans = [line] if in_fence else SPAN.findall(line)
        for span in spans:
            for raw in span.split():
                tok = _clean_token(raw)
                path = _repo_path(tok)
                if path is not None:
                    missing = not repo.exists(path) and not repo.exists(f"{Path(doc).parent.as_posix()}/{path}")
                    if missing and repo.has_parent(path):
                        out.append(Finding("path", doc, lineno, path))
                elif (
                    not in_fence
                    and not about_others
                    and "/" not in tok
                    and tok.endswith(NAME_SUFFIXES)
                    and re.fullmatch(r"[\w.-]+", tok)
                    and not PLACEHOLDER.search(tok)
                    and tok not in repo.basenames
                    and not repo.ignored(tok)
                ):
                    out.append(Finding("name", doc, lineno, tok))
            _check_commands(repo, doc, lineno, span, out)
    return out


def audit_modules(repo: Repo, readme: str) -> list[Finding]:
    folder = readme.rsplit("/", 1)[0]
    text = repo.text(readme)
    out = []
    for p in sorted(repo.files):
        if not p.endswith(".py") or p.rsplit("/", 1)[0] != folder:
            continue
        stem = p.rsplit("/", 1)[-1][:-3]
        if stem.startswith("_") or stem.startswith("test_"):
            continue
        if not re.search(rf"(?<![\w]){re.escape(stem)}(?![\w])", text):
            out.append(Finding("module", readme, 0, p))
    return out


def audit(repo: Repo | None = None) -> list[Finding]:
    repo = repo or Repo()
    skills = _skills(repo)
    findings: list[Finding] = []
    for doc in docs_in_scope(repo):
        findings += audit_doc(repo, doc, skills)
        if doc.startswith("gitgalaxy/") and doc.rsplit("/", 1)[-1].lower() == "readme.md":
            findings += audit_modules(repo, doc)
    return [f for f in findings if f.key not in ALLOWED]


def load_baseline(path: Path | None = None) -> Counter:
    path = path or BASELINE_PATH
    if not path.exists():
        return Counter()
    return Counter(json.loads(path.read_text(encoding="utf-8")))


def write_baseline(findings: list[Finding], path: Path | None = None) -> None:
    counts = Counter(f.key for f in findings)
    (path or BASELINE_PATH).write_text(json.dumps(dict(sorted(counts.items())), indent=1) + "\n", encoding="utf-8")


def new_findings(findings: list[Finding], baseline: Counter) -> tuple[list[Finding], list[str]]:
    """Findings beyond the baseline's count for their key, and the baselined keys that no longer occur."""
    left = Counter(baseline)
    new = []
    for f in findings:
        if left[f.key] > 0:
            left[f.key] -= 1
        else:
            new.append(f)
    fixed = sorted(k for k, n in left.items() if n > 0)
    return new, fixed


def _print(findings: list[Finding]) -> None:
    for f in findings:
        where = f"{f.doc}:{f.line}" if f.line else f.doc
        print(f"  [{f.check}] {where}: {f.target}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--ci", action="store_true", help="fail only on findings not in the baseline")
    mode.add_argument("--write-baseline", action="store_true", help="write the current findings as the baseline")
    mode.add_argument("--json", action="store_true", help="print every finding as JSON")
    args = ap.parse_args(argv)

    findings = audit()
    if args.json:
        print(json.dumps([asdict(f) for f in findings], indent=1))
        return 0
    if args.write_baseline:
        write_baseline(findings)
        print(f"doc-refs: wrote {len(findings)} finding(s) to {BASELINE_PATH.relative_to(REPO_ROOT)}")
        return 0
    if not args.ci:
        _print(findings)
        print(f"doc-refs: {len(findings)} finding(s)")
        return 1 if findings else 0

    new, fixed = new_findings(findings, load_baseline())
    if fixed:
        print(
            f"doc-refs: FYI {len(fixed)} baselined finding(s) no longer occur; shrink the baseline with --write-baseline:"
        )
        for k in fixed[:20]:
            print(f"  {k}")
    if new:
        print(
            f"doc-refs: FAIL, {len(new)} new finding(s). Fix the doc (or the code), or narrow the check in this script:"
        )
        _print(new)
        return 1
    print(f"doc-refs: OK ({len(findings)} baselined finding(s), none new)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
