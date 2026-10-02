#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# ==============================================================================
"""
Golden fixture for the git-history and spec-alignment equations (#4107).

The crucible golden master scans with git history ablated
(GITGALAXY_DISABLE_GIT_HISTORY=1, #2985) and without spec alignment (opt-in,
#3111), so Authorship Centralization, Ownership Entropy, Raw Churn Frequency,
Instability / Volatility / Specification Exposure and the Architect are constant
there and nothing regression-tests them.

This builds a tiny repository with a SCRIPTED history -- fixed authors, fixed
UTC epoch dates, no merges, branch ``main`` -- scans it with history enabled,
``--spec-alignment``, and "today" pinned via GITGALAXY_HISTORY_NOW, and
snapshots those fields per file. Every input that could vary is pinned, so the
snapshot is byte-stable on any machine and any date.

One commit is dated more than a year before the pinned "now": it must fall
outside the history window, which proves the pin is honoured.

    python tests/history_golden.py --bless     # rewrite the snapshot
    python tests/history_golden.py             # print the diff, exit 1 on drift
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

BASELINE_PATH = Path(__file__).resolve().parent / "history_golden_baseline.json"

DAY = 24 * 3600
JAN_1_2026 = 1767225600
NOW = JAN_1_2026 + 181 * DAY  # 2026-07-01T00:00:00Z: the pinned "today"
OUT_OF_WINDOW = JAN_1_2026 - 300 * DAY  # 2025-03-07: > 1 year before NOW

AUTHORS = {
    "alice": ("Alice Archer", "alice@example.com"),
    "bob": ("Bob Builder", "bob@example.com"),
    "carol": ("Carol Coder", "carol@example.com"),
    "dave": ("Dave Debugger", "dave@example.com"),
}

# (epoch, author, path, appended source). Chronological. Every scanned file gets
# at least one commit inside the window, so the getmtime fallback never runs.
HISTORY: list[tuple[int, str, str, str]] = [
    (OUT_OF_WINDOW, "dave", "engine/core.py", "def bootstrap():\n    return 0\n"),
    (JAN_1_2026 + 9 * DAY, "carol", "legacy/old.py", "def legacy_entry(x):\n    return x\n"),
    (JAN_1_2026 + 20 * DAY, "alice", "engine/core.py", "def load(path):\n    return open(path).read()\n"),
    (JAN_1_2026 + 31 * DAY, "alice", "engine/util.py", "def clamp(v, lo, hi):\n    return max(lo, min(v, hi))\n"),
    (
        JAN_1_2026 + 45 * DAY,
        "bob",
        "engine/core.py",
        "def parse(text):\n    if not text:\n        return []\n    return text.split()\n",
    ),
    (
        JAN_1_2026 + 60 * DAY,
        "bob",
        "web/app.js",
        "function render(el) {\n  if (!el) { return; }\n  el.hidden = false;\n}\n",
    ),
    (
        JAN_1_2026 + 70 * DAY,
        "alice",
        "engine/core.py",
        "def save(path, data):\n    with open(path, 'w') as f:\n        f.write(data)\n",
    ),
    (
        JAN_1_2026 + 85 * DAY,
        "carol",
        "engine/core.py",
        "def validate(rows):\n    for r in rows:\n        if r is None:\n            raise ValueError('row')\n",
    ),
    (JAN_1_2026 + 100 * DAY, "dave", "web/app.js", "function hide(el) {\n  el.hidden = true;\n}\n"),
    (JAN_1_2026 + 110 * DAY, "alice", "engine/util.py", "def lerp(a, b, t):\n    return a + (b - a) * t\n"),
    (
        JAN_1_2026 + 120 * DAY,
        "carol",
        "engine/spec_module.py",
        "# [SPEC-1] intake contract\ndef intake(req):\n    return req\n\ndef route(req):\n    return req\n\ndef audit_log(req):\n    return req\n",
    ),
    (JAN_1_2026 + 150 * DAY, "bob", "engine/core.py", "def merge(a, b):\n    return a + b\n"),
    (JAN_1_2026 + 165 * DAY, "bob", "web/app.js", "function toggle(el) {\n  el.hidden = !el.hidden;\n}\n"),
    (JAN_1_2026 + 175 * DAY, "alice", "engine/core.py", "def close():\n    return None\n"),
]

PARSED = "6. Parsed Files (Scanned Artifacts)"
# (section, field) pairs snapshotted per file.
FIELDS = [
    ("1. Artifact Identity", "Architect"),
    ("3. Architectural Profile", "Authorship Centralization"),
    ("3. Architectural Profile", "Ownership Entropy"),
    ("3. Architectural Profile", "Raw Churn Frequency"),
    ("4. Vulnerability & Risk Exposures", "Instability Exposure"),
    ("4. Vulnerability & Risk Exposures", "Volatility Exposure"),
    ("4. Vulnerability & Risk Exposures", "Specification Exposure"),
]


def _git_env(home: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"HOME": str(home), "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "TZ": "UTC"})
    return env


def build_repo(root: Path) -> Path:
    """Create the scripted repository at ``root`` (which must not exist)."""
    root.mkdir(parents=True)
    env = _git_env(root.parent)
    run = lambda *a, **kw: subprocess.run(["git", *a], cwd=root, check=True, capture_output=True, **kw)  # noqa: E731,S603,S607
    run("init", "-q", "-b", "main", env=env)
    for epoch, who, rel, source in HISTORY:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(source)
        name, email = AUTHORS[who]
        stamp = f"@{epoch} +0000"
        commit_env = {
            **env,
            "GIT_AUTHOR_NAME": name,
            "GIT_AUTHOR_EMAIL": email,
            "GIT_COMMITTER_NAME": name,
            "GIT_COMMITTER_EMAIL": email,
            "GIT_AUTHOR_DATE": stamp,
            "GIT_COMMITTER_DATE": stamp,
        }
        run("add", rel, env=commit_env)
        run("commit", "-q", "--no-gpg-sign", "-m", f"{who}: {rel}", env=commit_env)
    return root


def scan(repo: Path, out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k != "GITGALAXY_DISABLE_GIT_HISTORY"}
    env.update({"GITGALAXY_LICENSE_KEY": "COMMUNITY_FREE_TIER", "GITGALAXY_HISTORY_NOW": str(NOW), "TZ": "UTC"})
    subprocess.run(  # noqa: S603 -- fixed args
        [
            sys.executable,
            "-m",
            "gitgalaxy.galaxyscope",
            str(repo),
            "--output",
            str(out_dir) + os.sep,
            "--spec-alignment",
            "--file-speed",
            "--splicing-speed",
        ],
        check=True,
        capture_output=True,
        env=env,
        timeout=300,
    )
    audit = out_dir / f"{repo.name}_galaxy_audit.json"
    return json.loads(audit.read_text(encoding="utf-8"))


def extract(audit: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for group in (audit.get(PARSED) or {}).values():
        for path, record in (group.get("Files") or {}).items():
            out[path] = {
                f"{sec.split('. ', 1)[1]} / {field}": (record.get(sec) or {}).get(field) for sec, field in FIELDS
            }
    return dict(sorted(out.items()))


def current_snapshot() -> dict[str, dict[str, Any]]:
    with tempfile.TemporaryDirectory() as tmp:
        repo = build_repo(Path(tmp) / "history_repo")
        return extract(scan(repo, Path(tmp) / "out"))


def diff(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    lines = []
    for path in sorted(set(expected) | set(actual)):
        e, a = expected.get(path), actual.get(path)
        if e is None or a is None:
            lines.append(f"{path}: {'missing from scan' if a is None else 'not in baseline'}")
            continue
        lines += [
            f"{path} / {k}: expected {e.get(k)!r}, got {a.get(k)!r}"
            for k in sorted(set(e) | set(a))
            if e.get(k) != a.get(k)
        ]
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bless", action="store_true", help="rewrite tests/history_golden_baseline.json")
    args = parser.parse_args(argv)
    snap = current_snapshot()
    if args.bless:
        BASELINE_PATH.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {BASELINE_PATH.name}: {len(snap)} files")
        return 0
    found = diff(json.loads(BASELINE_PATH.read_text(encoding="utf-8")), snap)
    print("\n".join(found) or "history golden: no drift")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
