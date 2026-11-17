#!/usr/bin/env python3
"""Inventory of every network step in .github/workflows/ (#8424, checklist item c:52afc1bf).

A step is classified by the kind of fetch it makes and by how it is guarded:

* ``wrapped``   - the command line goes through ``tests/tools/ci_retry.sh`` (bounded retry + INFRASTRUCTURE marker)
* ``advisory``  - the step carries ``continue-on-error: true`` (a miss does not fail the job)
* ``in-tool``   - the step runs a tool that retries its own fetches (docker_build, maven_exe, translator prefetch)
* ``action``    - a marketplace action does the fetch (cache, artifact, setup-*); retried by the action, not by us
* ``bare``      - none of the above: one hiccup fails the job

This is a line-level heuristic over parsed YAML, not a shell parser: a command is recognised at the start of a
statement (after ``;``, ``&&``, ``|``, ``--``, ``sudo`` ...), so a word inside an ``echo`` or a ``grep`` is not a fetch.

    python tests/tools/ci_network_inventory.py            # print the summary
    python tests/tools/ci_network_inventory.py --write    # regenerate docs/ci_network_inventory.md
    python tests/tools/ci_network_inventory.py --check    # exit 1 when the doc is stale
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO / ".github" / "workflows"
DOC = REPO / "docs" / "ci_network_inventory.md"

_START = (
    r"(?:^|[;&|(]\s*|--\s+|\bsudo\s+|\bthen\s+|\bdo\s+|\belse\s+|\$\(\s*|-c\s+[\x22\x27]\s*)(?:[A-Za-z_]\w*=\S+\s+)*"
)
_PY = r"(?:(?:python3?|py)\s+-m\s+|\S*/)?"
# (kind, regex) in match order; one line yields every kind that matches
LINE_KINDS: list[tuple[str, re.Pattern[str]]] = [
    ("pip", re.compile(_START + r"(?:uv\s+)?" + _PY + r"pip3?\s+(?:install|download|wheel)\b")),
    ("apt", re.compile(_START + r"apt(?:-get)?\s+(?:install|update)\b")),
    ("node-packages", re.compile(_START + r"(?:npm|pnpm|yarn)\s+(?:ci|install|add)\b")),
    (
        "toolchain",
        re.compile(_START + r"(?:rustup\s+(?:toolchain|component|target|update)|cargo\s+install|go\s+install)\b"),
    ),
    ("docker", re.compile(_START + r"docker\s+(?:pull|build|compose\s+(?:pull|build))\b")),
    ("maven-gradle", re.compile(_START + r"(?:\S*/)?(?:mvn|mvnw|gradle|gradlew)\b")),
    ("git-fetch", re.compile(_START + r"git\s+(?:clone|fetch|ls-remote|submodule\s+update|pull)\b")),
    ("http-download", re.compile(_START + r"(?:curl|wget)\b")),
    ("gh-download", re.compile(_START + r"gh\s+(?:release\s+download|run\s+download|release\s+upload)\b")),
    ("gh-api", re.compile(_START + r"gh\s+(?:api|pr|issue|run\s+(?:list|view)|release\s+(?:view|list))\b")),
    ("grammar", re.compile(r"get_parser\(|tree_sitter_language_pack")),
]
# tools a workflow calls that retry their own network (docker build, maven, the corpus fetchers)
TOOL_RETRY = re.compile(
    r"tests/tools/(?:equivalence\w*|det_port|proof_sweep|porting_loop|port_runner|db2_image_cache|crucible_pins|sync-pins)"
)
USES_KINDS = [
    ("artifact-upload", re.compile(r"^actions/upload-artifact\b")),
    ("artifact-download", re.compile(r"^actions/download-artifact\b")),
    ("cache", re.compile(r"^actions/cache(?:/restore|/save)?\b")),
    ("setup-toolchain", re.compile(r"^(?:actions/setup-\w+|dtolnay/\S+|docker/setup-\S+)")),
]
KINDS = [k for k, _ in LINE_KINDS] + [k for k, _ in USES_KINDS]


def _logical_lines(script: str) -> list[str]:
    """Join backslash continuations and lines inside an open single-quoted string (``ci_retry.sh ... bash -c '...'``)."""
    out: list[str] = []
    buf = ""
    for raw in script.splitlines():
        line = raw.rstrip()
        if not buf and line.lstrip().startswith("#"):
            continue
        # a line inside an open quote is a new statement; after a backslash it is the same one
        sep = " " if buf.endswith("\\") or not buf.count("'") % 2 else " ; "
        if buf.endswith("\\"):
            buf = buf[:-1].rstrip()
        buf = f"{buf}{sep}{line.strip()}" if buf else line.strip()
        if buf.endswith("\\"):
            continue
        if buf.count("'") % 2:
            continue
        out.append(buf)
        buf = ""
    if buf:
        out.append(buf)
    return out


def _guard(step: dict, line: str | None) -> str:
    if line is not None and "ci_retry.sh" in line:
        return "wrapped"
    if str(step.get("continue-on-error")).lower() == "true":
        return "advisory"
    if line is not None and TOOL_RETRY.search(line):
        return "in-tool"
    return "bare"


def classify_step(step: dict) -> list[tuple[str, str]]:
    """The (kind, guard) pairs one workflow step makes, sorted and de-duplicated."""
    found: set[tuple[str, str]] = set()
    uses = step.get("uses")
    if isinstance(uses, str):
        for kind, rx in USES_KINDS:
            if rx.search(uses):
                # an action's fetch is the action's own; a failed artifact upload is still a red step unless advisory
                guard = "advisory" if str(step.get("continue-on-error")).lower() == "true" else "action"
                found.add((kind, guard))
                break
    run = step.get("run")
    if isinstance(run, str):
        for line in _logical_lines(run):
            hit = [k for k, rx in LINE_KINDS if rx.search(line)]
            for kind in hit:
                found.add((kind, _guard(step, line)))
            if not hit and TOOL_RETRY.search(line) and "tool" not in {k for k, _ in found}:
                found.add(("tool-entry", "in-tool"))
    return sorted(found)


def inventory(workflows: Path = WORKFLOWS) -> list[dict]:
    """One record per (workflow, job, step, kind): the whole network surface of the workflow directory."""
    import yaml  # lazy: keeps the stdlib-only path importable

    rows: list[dict] = []
    for path in sorted(workflows.glob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for job, spec in sorted((data.get("jobs") or {}).items()):
            for idx, step in enumerate((spec or {}).get("steps") or []):
                if not isinstance(step, dict):
                    continue
                for kind, guard in classify_step(step):
                    rows.append(
                        {
                            "workflow": path.name,
                            "job": str(job),
                            "step": str(step.get("name") or f"step {idx + 1}"),
                            "kind": kind,
                            "guard": guard,
                        }
                    )
    return rows


def render(rows: list[dict]) -> str:
    guards = ["wrapped", "advisory", "in-tool", "action", "bare"]
    count = Counter((r["kind"], r["guard"]) for r in rows)
    kinds = [k for k in [*KINDS, "tool-entry"] if any(count[(k, g)] for g in guards)]
    lines = [
        "# CI network inventory (#8424)",
        "",
        "Generated by `python tests/tools/ci_network_inventory.py --write`; `test_ci_network_inventory.py` fails when it is",
        "stale. Do not hand-edit. Each row is one (workflow, job, step, kind): a step that fetches two kinds counts twice.",
        "",
        "Guards: `wrapped` = through `tests/tools/ci_retry.sh`; `advisory` = `continue-on-error: true`; `in-tool` = the tool",
        "it runs retries its own fetches; `action` = a marketplace action does the fetch; `bare` = one hiccup fails the job.",
        "",
        "## By kind",
        "",
        "| Kind | " + " | ".join(guards) + " |",
        "|---|" + "---|" * len(guards),
    ]
    lines.extend(f"| {k} | " + " | ".join(str(count[(k, g)]) for g in guards) + " |" for k in kinds)
    lines.append("| **total** | " + " | ".join(str(sum(count[(k, g)] for k in kinds)) for g in guards) + " |")
    lines += ["", "## Bare steps (the shrink-only backlog)", ""]
    bare = [r for r in rows if r["guard"] == "bare"]
    by_wf: dict[str, list[dict]] = {}
    for r in bare:
        by_wf.setdefault(r["workflow"], []).append(r)
    if not bare:
        lines.append("None.")
    for wf, items in sorted(by_wf.items()):
        lines.append(f"### {wf}")
        lines.append("")
        for r in items:
            lines.append(f"- `{r['kind']}` - {r['job']} / {r['step']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true", help="regenerate docs/ci_network_inventory.md")
    ap.add_argument("--check", action="store_true", help="exit 1 when the doc is stale")
    args = ap.parse_args(argv)
    text = render(inventory())
    if args.write:
        DOC.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {DOC.relative_to(REPO)}")
        return 0
    if args.check:
        if not DOC.exists() or DOC.read_text(encoding="utf-8") != text:
            print("docs/ci_network_inventory.md is stale: run ci_network_inventory.py --write", file=sys.stderr)
            return 1
        return 0
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
