#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy
# Copyright (c) 2026 Joe Esquibel
#
# This source code is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this file except in compliance with the License.
# A copy of the license can be found in the LICENSE file in the root directory
# of this project, or at https://polyformproject.org/licenses/noncommercial/1.0.0/
# ==============================================================================
"""
One CLI for the engine bug-fix loop: golden bless (both CI legs in parallel, via crucible_check.py), the
mainframe ground-truth ledger, the estate-crucible horror scorecard, the audits, and the
PR-body evidence -- for one fix, or for a "train" of several fixes blessed together.

    python tests/tools/bugfix_kit.py setup    <worktree>
    python tests/tools/bugfix_kit.py bless    <worktree> [--leg full|zero|both] [--no-verify]
    python tests/tools/bugfix_kit.py scope    <worktree> [--expect cobol,jcl] [--mode full|zero|both]
    python tests/tools/bugfix_kit.py ledger   <worktree>
    python tests/tools/bugfix_kit.py estate   <worktree> [--base origin/main]
    python tests/tools/bugfix_kit.py audit    <worktree> [-k EXPR] [TEST_PATH ...]
    python tests/tools/bugfix_kit.py evidence <worktree> [--base origin/main] [--template] [--out FILE]
    python tests/tools/bugfix_kit.py all      <worktree> [--base origin/main] [--expect LANGS] [--skip STEP,...]
    python tests/tools/bugfix_kit.py train    <train-worktree> BRANCH [BRANCH ...] [--base origin/main]

<worktree> is any checkout of this repo; the kit always runs THAT checkout's own tools and
engine. The skill `.claude/skills/engine-bugfix/SKILL.md` is the checklist around it.

GOLDENS. The kit does not re-implement the golden-master workflow: `bless` runs the
worktree's own `tests/tools/crucible_check.py --mode <leg> --update --yes` and then
`crucible_check.py --mode <leg>` (the CI-equivalent check), once per leg, the two legs as two
concurrent processes. crucible_check owns the per-worktree venvs (.crucible_venvs/, CI's
Python via uv, editable install re-pointed and verified), the corpus-pin check and the
unsafe-path warning. What the kit adds is a separate language-crucible clone per leg (so the
concurrent legs never share a tree; under the kit home, which has no `tmp`-like path
component), the artifact check crucible_check's --update exit code does not give, and a
channel/file summary of what moved. `scope` wraps `scope_check.py` the same way.

The ledger, estate and audit steps run in two kit venvs mirroring their workflows (the engine
selected with PYTHONPATH=<worktree>, exactly as mainframe-ground-truth.yml does). An existing
venv that does not match is an error, never silently reinstalled (--recreate rebuilds it).

CONFIGURATION (flag, else environment variable, else default):

    --home            BUGFIX_KIT_HOME              <main checkout>/../bugfix-kit-home
    --venv-ledger     BUGFIX_KIT_VENV_LEDGER       <home>/venvs/ledger   (mainframe-ground-truth.yml)
    --venv-audit      BUGFIX_KIT_VENV_AUDIT        <home>/venvs/audit    (mypy + ruff==0.16.0)
    --corpora         BUGFIX_KIT_MAINFRAME_CORPORA <main checkout>/.mainframe_corpora
    --estate-crucible ESTATE_CRUCIBLE_PATH         <main checkout>/../estate-crucible
    --crucible-source BUGFIX_KIT_CRUCIBLE_SOURCE   https://github.com/squid-protocol/language-crucible.git

The home holds the per-leg corpus clones, the estate scorecard cache (one JSON per engine
commit, so the base side is scanned once per main commit), train state and the run logs
(<home>/runs/<worktree>/<stamp>-<command>/). Nothing the kit writes lands inside a worktree
except what the repo's own tools write there (the golden fixtures, the ledger) and the
.mainframe_corpora symlink, which `setup` adds to the repository's info/exclude.

TRAIN. `train` merges fix branches one at a time onto a train branch cut from --base. After
each merge it re-scans the full-precision golden leg and diffs it against the previous step
(and, by default, re-scores estate-crucible), so each fix's golden and horror changes stay
attributable; then it runs `all` once on the tip. Conflicts confined to generated artifacts
(golden fixtures, the ledger) resolve to the train's side, because the final bless regenerates
them; any other conflict aborts that merge and stops the train. Re-running `train` with more
branches appends to the same train.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as _dt
import filecmp
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

# ----------------------------------------------------------------------------- constants

FIXTURES = {"full": "tests/golden_master_audit", "zero": "tests/golden_master_zero_dep_audit"}
LEG_LABEL = {"full": "full-precision", "zero": "zero-dependency"}
LEDGER_REL = "tests/cobol_mainframe/ground_truth_ledger.json"
# Generated artifacts a train merge may resolve to the train's side: the final bless /
# ledger update regenerates every one of them from the merged engine.
GENERATED_PREFIXES = (FIXTURES["full"] + "/", FIXTURES["zero"] + "/", LEDGER_REL)
UNTRIAGED = "UNTRIAGED"
GROUP_FILES = "Files"  # golden_store.GROUP_FILES_KEY: the parsed-file index's per-group file list
CRUCIBLE_URL = "https://github.com/squid-protocol/language-crucible.git"
RUFF_PIN = "0.16.0"
STEPS = ("setup", "bless", "scope", "ledger", "estate", "audit", "evidence")

# What each venv must look like. `flags` is what the engine itself reports (the same
# HAS_PYYAML / HAS_TIKTOKEN / ML_AVAILABLE test_golden_crucible.py picks its fixture by).
VENV_SPECS: dict[str, dict[str, Any]] = {
    "ledger": {"workflow": "mainframe-ground-truth.yml", "python": "3.12", "packages": ["pytest"], "flags": {}},
    "audit": {
        "workflow": "mypy-audit.yml",
        "python": "3.12",
        "packages": ["mypy", "PyYAML", f"ruff=={RUFF_PIN}", "pytest"],
        "flags": {},
    },
}

_PROBE = r"""
import json, sys
out = {"python": "%d.%d" % sys.version_info[:2]}
try:
    import gitgalaxy
    out["gitgalaxy"] = gitgalaxy.__file__
except Exception as exc:  # noqa: BLE001
    out["error"] = repr(exc)
if "flags" in sys.argv:
    try:
        from gitgalaxy.galaxyscope import HAS_PYYAML, HAS_TIKTOKEN
        from gitgalaxy.security.security_auditor import ML_AVAILABLE
        out["flags"] = {"HAS_PYYAML": bool(HAS_PYYAML), "HAS_TIKTOKEN": bool(HAS_TIKTOKEN), "ML_AVAILABLE": bool(ML_AVAILABLE)}
    except Exception as exc:  # noqa: BLE001
        out["error"] = repr(exc)
for mod in ("pytest", "mypy", "yaml"):
    try:
        __import__(mod)
        out[mod] = True
    except Exception:  # noqa: BLE001
        out[mod] = False
print(json.dumps(out))
"""


class KitError(RuntimeError):
    """An environment problem with an actionable message (exit 2)."""


# ============================================================================= pure parts
# Everything in this block is side-effect free and covered by test_bugfix_kit.py.


def fmt_secs(secs: float) -> str:
    secs = round(secs)
    return f"{secs // 60}m{secs % 60:02d}s" if secs >= 60 else f"{secs}s"


def language_of(scanned_path: str) -> str:
    """Corpus files are `<language>/<project>/...`; the first component is the bucket."""
    return scanned_path.split("/", 1)[0] if "/" in scanned_path else "(root)"


def count_leaf_diffs(old: Any, new: Any) -> int:
    """Number of differing leaves between two JSON values (a missing side counts its leaves)."""
    if isinstance(old, dict) and isinstance(new, dict):
        return sum(count_leaf_diffs(old.get(k), new.get(k)) for k in set(old) | set(new))
    if isinstance(old, list) and isinstance(new, list):
        n = sum(count_leaf_diffs(a, b) for a, b in zip(old, new))
        longer = old[len(new) :] if len(old) > len(new) else new[len(old) :]
        return n + sum(_leaves(x) for x in longer)
    if old is None and new is not None:
        return _leaves(new)
    if new is None and old is not None:
        return _leaves(old)
    return 0 if old == new else 1


def _leaves(v: Any) -> int:
    if isinstance(v, dict):
        return sum(_leaves(x) for x in v.values()) or 1
    if isinstance(v, list):
        return sum(_leaves(x) for x in v) or 1
    return 1


@dataclass
class ChannelDelta:
    channel: str
    changed: set[str] = field(default_factory=set)  # scanned files whose value changed
    added: set[str] = field(default_factory=set)  # scanned files that newly carry the channel
    removed: set[str] = field(default_factory=set)  # scanned files that lost it
    leaves: int = 0
    note: str = ""

    @property
    def files(self) -> set[str]:
        return self.changed | self.added | self.removed


@dataclass
class GoldenSummary:
    docs_changed: int = 0
    channels: dict[str, ChannelDelta] = field(default_factory=dict)
    newly_parsed: set[str] = field(default_factory=set)
    no_longer_parsed: set[str] = field(default_factory=set)
    errors: list[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not self.docs_changed and not self.errors

    def scanned_files(self) -> Counter:
        """scanned file -> number of channels it moved in."""
        c: Counter = Counter()
        for ch in self.channels.values():
            for f in ch.files:
                c[f] += 1
        return c

    def to_json(self) -> dict[str, Any]:
        return {
            "docs_changed": self.docs_changed,
            "channels": {
                k: {
                    "changed": sorted(v.changed),
                    "added": sorted(v.added),
                    "removed": sorted(v.removed),
                    "leaves": v.leaves,
                    "note": v.note,
                }
                for k, v in self.channels.items()
            },
            "newly_parsed": sorted(self.newly_parsed),
            "no_longer_parsed": sorted(self.no_longer_parsed),
            "errors": self.errors,
        }

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> GoldenSummary:
        s = cls(docs_changed=d.get("docs_changed", 0), errors=list(d.get("errors", [])))
        for k, v in d.get("channels", {}).items():
            s.channels[k] = ChannelDelta(
                k, set(v["changed"]), set(v["added"]), set(v["removed"]), v["leaves"], v.get("note", "")
            )
        s.newly_parsed = set(d.get("newly_parsed", []))
        s.no_longer_parsed = set(d.get("no_longer_parsed", []))
        return s


def _flatten_groups(doc: dict[str, Any] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for per_path in ((doc or {}).get("groups") or {}).values():
        if isinstance(per_path, dict):
            out.update(per_path)
    return out


def _channel_name(doc: dict[str, Any] | None, rel: str) -> list[str]:
    path = (doc or {}).get("path")
    return [str(p) for p in path] if isinstance(path, list) and path else [rel]


def summarize_golden(changes: Iterable[tuple[str, bytes | None, bytes | None]]) -> GoldenSummary:
    """Summarize changed split-fixture files (tests/golden_store.py layout) by channel.

    `changes` yields (path relative to the fixture dir, old bytes or None, new bytes or None).
    A per-file section doc ({"path": [P, section, sub], "groups": {group: {file: value}}}) is
    reported as the scanned files whose value moved; the parsed-files index (_groups.json)
    as files newly parsed / no longer parsed; anything else as a leaf-diff count.
    """
    s = GoldenSummary()
    for rel, old_b, new_b in changes:
        if old_b == new_b:
            continue
        s.docs_changed += 1
        try:
            old = json.loads(old_b) if old_b is not None else None
            new = json.loads(new_b) if new_b is not None else None
        except ValueError as exc:
            s.errors.append(f"{rel}: unparseable ({exc.__class__.__name__}; merge-conflict markers?)")
            continue
        if not isinstance(old, (dict, type(None))) or not isinstance(new, (dict, type(None))):
            s.errors.append(f"{rel}: not a golden_store document")
            continue
        path = _channel_name(new or old, rel)
        if rel == "_layout.json":
            s.errors.append("_layout.json changed: the fixture format itself moved")
            continue
        is_groups = "groups" in (new or old or {})
        if is_groups and len(path) == 1:  # the parsed-files index
            o_idx, n_idx = (old or {}).get("groups") or {}, (new or {}).get("groups") or {}
            o_files = {f for g in o_idx.values() for f in (g.get(GROUP_FILES) or [])}
            n_files = {f for g in n_idx.values() for f in (g.get(GROUP_FILES) or [])}
            s.newly_parsed |= n_files - o_files
            s.no_longer_parsed |= o_files - n_files
            ch = s.channels.setdefault(
                "(parsed-file index: group stats)", ChannelDelta("(parsed-file index: group stats)")
            )
            for g in set(o_idx) | set(n_idx):
                a = {k: v for k, v in (o_idx.get(g) or {}).items() if k != GROUP_FILES}
                b = {k: v for k, v in (n_idx.get(g) or {}).items() if k != GROUP_FILES}
                ch.leaves += count_leaf_diffs(a, b)
            if not ch.leaves:
                del s.channels[ch.channel]
            continue
        name = " / ".join(path[1:]) if is_groups else " / ".join(path)
        ch = s.channels.setdefault(name, ChannelDelta(name))
        if old is None:
            ch.note = "new channel"
        elif new is None:
            ch.note = "channel removed"
        if is_groups:
            o, n = _flatten_groups(old), _flatten_groups(new)
            ch.added |= set(n) - set(o)
            ch.removed |= set(o) - set(n)
            for f in set(o) & set(n):
                if o[f] != n[f]:
                    ch.changed.add(f)
                    ch.leaves += count_leaf_diffs(o[f], n[f])
            ch.leaves += sum(_leaves(n[f]) for f in set(n) - set(o)) + sum(_leaves(o[f]) for f in set(o) - set(n))
        else:
            ch.leaves += count_leaf_diffs((old or {}).get("value"), (new or {}).get("value"))
    return s


def _sample(files: Iterable[str], n: int = 3) -> str:
    files = sorted(files)
    more = f" (+{len(files) - n})" if len(files) > n else ""
    return ", ".join(f"`{f}`" for f in files[:n]) + more


def render_golden(summary: GoldenSummary, label: str, max_rows: int = 25) -> str:
    """Compact markdown for one leg: channel table, languages, most-touched files."""
    if summary.empty:
        return f"**{label}**: unchanged.\n"
    files = summary.scanned_files()
    langs = Counter(language_of(f) for f in files)
    lang_txt = ", ".join(f"{lang} {n}" for lang, n in langs.most_common(8))
    out = [
        f"**{label}**: {summary.docs_changed} fixture file(s), {len(summary.channels)} channel(s), "
        f"{len(files)} scanned file(s) moved" + (f" ({lang_txt})" if lang_txt else "") + ".",
        "",
    ]
    for err in summary.errors:
        out.append(f"- :warning: {err}")
    if summary.newly_parsed or summary.no_longer_parsed:
        out.append(
            f"- parsed-file set: +{len(summary.newly_parsed)} newly parsed {_sample(summary.newly_parsed)}"
            f"; -{len(summary.no_longer_parsed)} no longer parsed {_sample(summary.no_longer_parsed)}"
        )
    if summary.errors or summary.newly_parsed or summary.no_longer_parsed:
        out.append("")
    if summary.channels:
        out += ["| channel | files changed | +added | -removed | leaves | sample |", "|---|--:|--:|--:|--:|---|"]
        rows = sorted(summary.channels.values(), key=lambda c: (-len(c.files), -c.leaves, c.channel))
        for c in rows[:max_rows]:
            note = f" *({c.note})*" if c.note else ""
            out.append(
                f"| {c.channel}{note} | {len(c.changed)} | {len(c.added)} | {len(c.removed)} | {c.leaves} | "
                f"{_sample(c.files) if c.files else ''} |"
            )
        if len(rows) > max_rows:
            out.append(f"| ... {len(rows) - max_rows} more channel(s) | | | | | |")
    if files:
        top = ", ".join(f"`{f}` ({n})" for f, n in files.most_common(5))
        out += ["", f"Most-moved scanned files (channels): {top}"]
    return "\n".join(out) + "\n"


def ledger_delta(old: dict[str, Any] | None, new: dict[str, Any] | None) -> dict[str, Any]:
    """Per corpus: entries fixed / introduced (with cause), scoreboard cells that moved."""
    old_c = (old or {}).get("corpora") or {}
    new_c = (new or {}).get("corpora") or {}
    out: dict[str, Any] = {}
    for name in sorted(set(old_c) | set(new_c)):
        o, n = old_c.get(name) or {}, new_c.get(name) or {}
        om, nm = o.get("mismatches") or {}, n.get("mismatches") or {}
        fixed = sorted(set(om) - set(nm))
        introduced = {k: nm[k] for k in sorted(set(nm) - set(om))}
        recaused = {k: (om[k], nm[k]) for k in sorted(set(om) & set(nm)) if om[k] != nm[k]}
        board: list[str] = []
        ob, nb = o.get("scoreboard") or {}, n.get("scoreboard") or {}
        for fld in sorted(set(ob) | set(nb)):
            for side in ("engine", "forge"):
                a = (ob.get(fld) or {}).get(side)
                b = (nb.get(fld) or {}).get(side)
                if a != b:
                    board.append(f"{fld} [{side}] {_tgt(a)} -> {_tgt(b)}")
            ta, tb = (ob.get(fld) or {}).get("truth"), (nb.get(fld) or {}).get("truth")
            if ta != tb:
                board.append(f"{fld} [truth tier] {ta} -> {tb}")
        if fixed or introduced or recaused or board or (name in old_c) != (name in new_c):
            out[name] = {
                "fixed": fixed,
                "introduced": introduced,
                "recaused": recaused,
                "scoreboard": board,
                "corpus": "added" if name not in old_c else "removed" if name not in new_c else "",
            }
    return out


def _tgt(cell: dict[str, Any] | None) -> str:
    if not cell:
        return "-"
    return f"tp {cell.get('tp')}/got {cell.get('got')}/truth {cell.get('truth')}"


def render_ledger(delta: dict[str, Any], max_entries: int = 8) -> str:
    if not delta:
        return "Ground-truth ledger: no change.\n"
    fixed = sum(len(d["fixed"]) for d in delta.values())
    intro = sum(len(d["introduced"]) for d in delta.values())
    untriaged = sum(1 for d in delta.values() for c in d["introduced"].values() if c == UNTRIAGED)
    out = [
        f"Ground-truth ledger: **{fixed} mismatch(es) fixed, {intro} introduced**"
        + (f" (**{untriaged} UNTRIAGED** -- `check` fails until assigned)" if untriaged else "")
        + ".",
        "",
        "| corpus | fixed | introduced | scoreboard |",
        "|---|--:|--:|---|",
    ]
    for name, d in delta.items():
        tag = f" *({d['corpus']})*" if d["corpus"] else ""
        out.append(f"| {name}{tag} | {len(d['fixed'])} | {len(d['introduced'])} | {'<br>'.join(d['scoreboard'])} |")
    listed = [(n, e, "fixed") for n, d in delta.items() for e in d["fixed"]]
    listed += [(n, f"{e} -> {c}", "new") for n, d in delta.items() for e, c in d["introduced"].items()]
    if listed:
        out.append("")
        for n, e, kind in listed[:max_entries]:
            out.append(f"- {kind}: `{n} :: {e}`")
        if len(listed) > max_entries:
            out.append(f"- ... {len(listed) - max_entries} more")
    return "\n".join(out) + "\n"


def estate_delta(before: dict[str, Any] | None, after: dict[str, Any] | None) -> dict[str, Any]:
    """Horror verdicts and channel totals, before -> after (either side may be None)."""

    def horrors(sc: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
        return {h["id"]: h for h in (sc or {}).get("horrors", [])}

    hb, ha = horrors(before), horrors(after)
    rows = []
    for hid in sorted(set(hb) | set(ha)):
        b, a = hb.get(hid), ha.get(hid)
        bv = (b["verdict"], len(b.get("failing", []))) if b else None
        av = (a["verdict"], len(a.get("failing", []))) if a else None
        if bv != av:
            rows.append(
                {
                    "id": hid,
                    "issue": (a or b or {}).get("issue"),
                    "title": (a or b or {}).get("title", ""),
                    "before": bv,
                    "after": av,
                }
            )

    def totals(sc: dict[str, Any] | None) -> dict[str, int]:
        t: Counter = Counter()
        for cnt in ((sc or {}).get("channels") or {}).values():
            t.update(cnt)
        return dict(t)

    def passing(h: dict[str, dict[str, Any]]) -> int:
        return sum(1 for x in h.values() if x["verdict"] == "PASS")

    channels = []
    cb, ca = (before or {}).get("channels") or {}, (after or {}).get("channels") or {}
    for ch in sorted(set(cb) | set(ca)):
        if cb.get(ch) != ca.get(ch):
            channels.append({"channel": ch, "before": cb.get(ch), "after": ca.get(ch)})
    return {
        "before_commit": (before or {}).get("engine_commit"),
        "after_commit": (after or {}).get("engine_commit"),
        "pass_before": passing(hb) if before else None,
        "pass_after": passing(ha) if after else None,
        "n_horrors": len(set(hb) | set(ha)),
        "totals_before": totals(before) if before else None,
        "totals_after": totals(after) if after else None,
        "horrors": rows,
        "channels": channels,
    }


def _verdict(v: tuple[str, int] | None) -> str:
    if v is None:
        return "-"
    return v[0] if v[0] == "PASS" else f"{v[0]} ({v[1]} not passing)"


def render_estate(d: dict[str, Any]) -> str:
    if d["pass_after"] is None:
        return "Estate-crucible: not scored (run `bugfix_kit.py estate`).\n"
    if d["pass_before"] is None:
        return f"Estate-crucible: {d['pass_after']}/{d['n_horrors']} horrors pass (no base scorecard).\n"
    keys = ("pass", "fail", "missing", "phantom")
    tb, ta = d["totals_before"] or {}, d["totals_after"] or {}
    tot = ", ".join(f"{k} {tb.get(k, 0)}->{ta.get(k, 0)}" for k in keys if tb.get(k, 0) != ta.get(k, 0))
    out = [
        f"Estate-crucible (`{d['before_commit']}` -> `{d['after_commit']}`): horrors passing "
        f"**{d['pass_before']}/{d['n_horrors']} -> {d['pass_after']}/{d['n_horrors']}**"
        + (f"; checks {tot}" if tot else "; check totals unchanged")
        + "."
    ]
    if d["horrors"]:
        out += ["", "| horror | issue | before | after | title |", "|---|---|---|---|---|"]
        for h in d["horrors"]:
            issue = f"#{h['issue']}" if h["issue"] else ""
            out.append(f"| {h['id']} | {issue} | {_verdict(h['before'])} | {_verdict(h['after'])} | {h['title']} |")
    if d["channels"]:
        out += ["", "| channel | before (pass/fail/missing/phantom) | after |", "|---|---|---|"]
        for c in d["channels"]:

            def cell(x: dict[str, int] | None) -> str:
                return "/".join(str((x or {}).get(k, 0)) for k in keys)

            out.append(f"| {c['channel']} | {cell(c['before'])} | {cell(c['after'])} |")
    return "\n".join(out) + "\n"


def render_train(state: dict[str, Any]) -> str:
    """Per-fix attribution for a train: each step's golden (full-precision) and estate delta."""
    steps = state.get("steps") or []
    if not steps:
        return ""
    out = [
        (
            f"Train `{state.get('branch')}` on base `{str(state.get('base_sha'))[:12]}` -- "
            f"each row is the delta that merge alone introduced (full-precision scan vs the previous step)."
        ),
        "",
        "| # | branch | golden channels | scanned files moved | estate horrors | notes |",
        "|--:|---|--:|--:|---|---|",
    ]
    details = []
    for i, st in enumerate(steps, 1):
        gs = GoldenSummary.from_json(st["golden"]) if st.get("golden") else None
        ed = st.get("estate")
        est = ""
        if ed and ed.get("pass_after") is not None:
            est = f"{ed.get('pass_before')}->{ed.get('pass_after')}"
            if ed.get("horrors"):
                est += " (" + ", ".join(h["id"] for h in ed["horrors"]) + ")"
        notes = "; ".join(st.get("notes", []))
        gcol = str(len(gs.channels)) if gs else "n/a"
        fcol = str(len(gs.scanned_files())) if gs else "n/a"
        out.append(f"| {i} | `{st['branch']}` @ `{st['sha'][:10]}` | {gcol} | {fcol} | {est} | {notes} |")
        if gs and not gs.empty:
            details.append(
                f"<details><summary>{i}. {st['branch']}</summary>\n\n{render_golden(gs, 'full-precision', 12)}</details>"
            )
    return "\n".join([*out, "", *details]) + "\n"


EVIDENCE_TEMPLATE = """## What was broken
<!-- the issue's reproduction: input, what the engine emitted, what it should emit -->

## Fix
<!-- the narrowest root cause, and why the change is the right layer -->

## Before -> after
<!-- the repro (and the regression tests that pin it), before and after -->

"""


def render_evidence(
    golden: dict[str, GoldenSummary],
    base_sha: str,
    ledger: dict[str, Any] | None,
    estate: dict[str, Any] | None,
    train: dict[str, Any] | None = None,
    template: bool = False,
) -> str:
    out = [EVIDENCE_TEMPLATE] if template else []
    out.append(f"## Golden masters (vs `{base_sha[:12]}`)\n")
    for leg in ("full", "zero"):
        if leg in golden:
            out.append(render_golden(golden[leg], f"{LEG_LABEL[leg]} (`{FIXTURES[leg]}`)"))
    if train and train.get("steps"):
        out.append("## Per-fix attribution\n")
        out.append(render_train(train))
    out.append("## Ground-truth ledger\n")
    out.append(render_ledger(ledger) if ledger is not None else "Ground-truth ledger: not measured.\n")
    out.append("## Estate-crucible horrors\n")
    out.append(render_estate(estate) if estate is not None else "Estate-crucible: not scored.\n")
    return "\n".join(out)


def split_conflicts(paths: Iterable[str]) -> tuple[list[str], list[str]]:
    """(generated, source) -- generated artifacts may resolve to the train's side."""
    gen, src = [], []
    for p in paths:
        (gen if any(p == g or p.startswith(g) for g in GENERATED_PREFIXES) else src).append(p)
    return gen, src


def read_pin(text: str, name: str) -> str | None:
    """`NAME = "value"` on one line (the same shape the workflows' sed relies on)."""
    m = re.search(rf'^{name} = "([^"]+)"', text, re.M)
    return m.group(1) if m else None


def workflow_python(text: str) -> str | None:
    m = re.search(r"python-version:\s*['\"]?(\d+\.\d+)", text)
    return m.group(1) if m else None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    common = argparse.ArgumentParser(add_help=False)
    g = common.add_argument_group("environment (flag > env var > default)")
    g.add_argument("--home", type=Path, help="kit home: venvs, corpus clones, caches, logs (BUGFIX_KIT_HOME)")
    for v in ("ledger", "audit"):
        g.add_argument(f"--venv-{v}", type=Path, help=f"{v} venv (BUGFIX_KIT_VENV_{v.upper()})")
    g.add_argument("--corpora", type=Path, help="mainframe corpora cache (BUGFIX_KIT_MAINFRAME_CORPORA)")
    g.add_argument("--estate-crucible", type=Path, help="estate-crucible checkout (ESTATE_CRUCIBLE_PATH)")
    g.add_argument("--crucible-source", help="language-crucible clone source (BUGFIX_KIT_CRUCIBLE_SOURCE)")
    g.add_argument("--recreate", action="store_true", help="rebuild a venv that exists but does not match its leg")

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name: str, help_: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, parents=[common], help=help_)
        p.add_argument("worktree", type=Path)
        return p

    add("setup", "corpora symlink, venvs, crucible clones, pins")
    p = add("bless", "regenerate both golden legs in parallel, then verify each")
    p.add_argument("--leg", choices=("full", "zero", "both"), default="both")
    p.add_argument("--no-verify", action="store_true", help="skip the golden_crucible pytest after the bless")
    p = add("scope", "scope_check.py: language-bucketed scan diff vs --base (slow: scans both sides)")
    p.add_argument("--base", default="origin/main")
    p.add_argument("--expect", help="comma-separated languages the fix may touch (fail on any other)")
    p.add_argument("--mode", choices=("full", "zero", "both"), default="full")
    add("ledger", "mainframe corpus fetch + ground-truth ledger update + check")
    p = add("estate", "estate-crucible horror scorecard, base vs worktree")
    p.add_argument("--base", default="origin/main")
    p.add_argument("--refresh", action="store_true", help="ignore cached scorecards")
    p = add("audit", "mypy / ruff / dead-key audits, plus a test selection")
    p.add_argument("-k", dest="keyword", help="pytest -k expression")
    p.add_argument("tests", nargs="*", help="test paths (default: test files changed vs --base)")
    p.add_argument("--base", default="origin/main")
    p.add_argument("--no-tests", action="store_true", help="audits only")
    p = add("evidence", "markdown for the PR body")
    p.add_argument("--base", default="origin/main")
    p.add_argument("--template", action="store_true", help="prepend the PR body skeleton")
    p.add_argument("--out", type=Path, help="also write the markdown here")
    p = add("all", "setup, bless, ledger, estate, audit, evidence")
    p.add_argument("--base", default="origin/main")
    p.add_argument("--skip", default="", help=f"comma-separated steps to skip ({','.join(STEPS)})")
    p.add_argument("-k", dest="keyword", help="pytest -k expression for the audit step")
    p.add_argument("--expect", help="run the scope step (scope_check.py --expect LANGS); skipped without it")
    p = add("train", "merge fix branches one at a time with per-fix attribution, then `all`")
    p.add_argument("branches", nargs="+")
    p.add_argument("--base", default="origin/main")
    p.add_argument("--branch", help="train branch name (default: train/<worktree dir name>)")
    p.add_argument("--no-estate-per-step", action="store_true")
    p.add_argument("--ledger-per-step", action="store_true", help="also re-measure the ledger after each merge")
    p.add_argument("--no-final", action="store_true", help="stop after the merges and attribution")
    p.add_argument("--skip-conflicting", action="store_true", help="drop a branch that conflicts, keep going")
    # argparse binds a trailing `nargs="*"` positional at the first positional it sees, so test
    # paths written after an option (`audit WT -k x tests/a.py`) arrive as extras.
    args, extra = ap.parse_known_args(argv)
    if extra:
        if args.cmd == "audit" and not any(x.startswith("-") for x in extra):
            args.tests = [*args.tests, *extra]
        else:
            ap.error(f"unrecognized arguments: {' '.join(extra)}")
    if getattr(args, "skip", ""):
        bad = set(args.skip.split(",")) - set(STEPS)
        if bad:
            ap.error(f"--skip: unknown step(s) {sorted(bad)}; choose from {','.join(STEPS)}")
    return args


# ============================================================================= environment


def _git(wt: Path, *args: str, check: bool = True) -> str:
    r = subprocess.run(["git", "-C", str(wt), *args], capture_output=True, text=True)  # noqa: S603,S607
    if check and r.returncode != 0:
        raise KitError(f"git {' '.join(args)} failed in {wt}: {r.stderr.strip()}")
    return r.stdout.strip()


@dataclass
class Kit:
    wt: Path
    main: Path  # the main checkout (parent of the git common dir)
    home: Path
    venvs: dict[str, Path]
    corpora: Path
    estate_crucible: Path
    crucible_source: str
    recreate: bool = False
    run_dir: Path = Path()
    timings: list[tuple[str, float, str]] = field(default_factory=list)

    @classmethod
    def from_args(cls, args: argparse.Namespace, cmd: str) -> Kit:
        wt = args.worktree.resolve()
        if not (wt / "gitgalaxy").is_dir() or not (wt / "tests").is_dir():
            raise KitError(f"{wt} is not a gitgalaxy checkout (no gitgalaxy/ and tests/)")
        common = Path(_git(wt, "rev-parse", "--path-format=absolute", "--git-common-dir"))
        main = common.parent
        env = os.environ.get
        home = (args.home or Path(env("BUGFIX_KIT_HOME") or main.parent / "bugfix-kit-home")).resolve()
        venvs = {
            v: Path(getattr(args, f"venv_{v}") or env(f"BUGFIX_KIT_VENV_{v.upper()}") or home / "venvs" / v)
            for v in ("ledger", "audit")
        }
        kit = cls(
            wt=wt,
            main=main,
            home=home,
            venvs=venvs,
            corpora=Path(args.corpora or env("BUGFIX_KIT_MAINFRAME_CORPORA") or main / ".mainframe_corpora"),
            estate_crucible=Path(
                args.estate_crucible or env("ESTATE_CRUCIBLE_PATH") or main.parent / "estate-crucible"
            ),
            crucible_source=args.crucible_source or env("BUGFIX_KIT_CRUCIBLE_SOURCE") or CRUCIBLE_URL,
            recreate=args.recreate,
        )
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        kit.run_dir = home / "runs" / wt.name / f"{stamp}-{cmd}"
        kit.run_dir.mkdir(parents=True, exist_ok=True)
        latest = home / "runs" / wt.name / "latest"
        try:
            if latest.is_symlink() or latest.exists():
                latest.unlink()
            latest.symlink_to(kit.run_dir.name)
        except OSError:
            pass
        return kit

    # ------------------------------------------------------------------ logging / running

    def say(self, msg: str) -> None:
        print(f"[kit] {msg}", flush=True)

    def log(self, name: str) -> Path:
        return self.run_dir / f"{name}.log"

    def run(
        self,
        cmd: list[str],
        log: Path,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> int:
        with log.open("a", encoding="utf-8") as fh:
            fh.write(f"\n$ {' '.join(cmd)}\n# cwd={cwd or self.wt}\n")
            fh.flush()
            try:
                r = subprocess.run(  # noqa: S603
                    cmd,
                    cwd=str(cwd or self.wt),
                    env=env,
                    stdout=fh,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                fh.write(f"\n# TIMEOUT after {timeout}s\n")
                return 124
            fh.write(f"# exit {r.returncode}\n")
            return r.returncode

    def timed(self, name: str, fn: Callable[[], bool]) -> bool:
        t0 = time.monotonic()
        try:
            ok = fn()
        except KitError as exc:
            self.say(f"{name}: ERROR {exc}")
            ok = False
        dt = time.monotonic() - t0
        self.timings.append((name, dt, "ok" if ok else "FAIL"))
        self.say(f"{name}: {'ok' if ok else 'FAIL'} ({fmt_secs(dt)})")
        return ok

    def env_for(self, venv: str, wt: Path | None = None, **extra: str) -> dict[str, str]:
        """A venv's environment with THIS worktree's engine first on the path."""
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "VIRTUAL_ENV", "PYTHONHOME")}
        bin_ = self.venvs[venv] / "bin"
        env["PATH"] = f"{bin_}{os.pathsep}{env.get('PATH', '')}"
        env["VIRTUAL_ENV"] = str(self.venvs[venv])
        env["PYTHONPATH"] = str(wt or self.wt)
        env["GITGALAXY_LICENSE_KEY"] = "COMMUNITY_FREE_TIER"
        env["PYTHONUTF8"] = "1"
        env["GITGALAXY_MAINFRAME_CORPORA"] = str(self.corpora)
        env.update(extra)
        return env

    def py(self, venv: str) -> str:
        return str(self.venvs[venv] / "bin" / "python")

    # ------------------------------------------------------------------ setup pieces

    def wanted_python(self, venv: str) -> str:
        spec = VENV_SPECS[venv]
        wf = self.wt / ".github" / "workflows" / spec["workflow"]
        return (workflow_python(wf.read_text(encoding="utf-8")) if wf.exists() else None) or spec["python"]

    def probe(self, venv: str, flags: bool) -> dict[str, Any]:
        r = subprocess.run(  # noqa: S603
            [self.py(venv), "-c", _PROBE] + (["flags"] if flags else []),
            cwd=str(self.venvs[venv]),
            env=self.env_for(venv),
            capture_output=True,
            text=True,
        )
        try:
            return json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            return {"error": (r.stderr or r.stdout).strip()[-400:]}

    def venv_problems(self, venv: str) -> list[str]:
        spec = VENV_SPECS[venv]
        if not Path(self.py(venv)).exists():
            return ["missing"]
        info = self.probe(venv, bool(spec["flags"]))
        probs = []
        if "error" in info:
            probs.append(f"import probe failed: {info['error']}")
        want_py = self.wanted_python(venv)
        if info.get("python") and info["python"] != want_py:
            probs.append(f"python {info['python']} but CI pins {want_py}")
        got = info.get("gitgalaxy")
        if got and not Path(got).resolve().is_relative_to(self.wt):
            probs.append(f"`import gitgalaxy` resolves to {got}, not into {self.wt}")
        for flag, want in spec["flags"].items():
            have = (info.get("flags") or {}).get(flag)
            if have is not None and have != want:
                probs.append(f"{flag}={have} (this leg needs {want})")
        if "pytest" in spec["packages"] and not info.get("pytest"):
            probs.append("pytest not installed")
        if venv == "audit":
            if not info.get("mypy"):
                probs.append("mypy not installed")
            ruff = self.venvs[venv] / "bin" / "ruff"
            ver = (
                subprocess.run([str(ruff), "--version"], capture_output=True, text=True).stdout if ruff.exists() else ""
            )
            if RUFF_PIN not in ver:
                probs.append(f"ruff is {ver.strip() or 'missing'}, CI pins {RUFF_PIN}")
        return probs

    def create_venv(self, venv: str) -> None:
        spec = VENV_SPECS[venv]
        path = self.venvs[venv]
        want = self.wanted_python(venv)
        uv = shutil.which("uv")
        interp = None
        if uv:
            r = subprocess.run([uv, "python", "find", want], capture_output=True, text=True)  # noqa: S603
            if r.returncode != 0:
                subprocess.run([uv, "python", "install", want], capture_output=True)  # noqa: S603
                r = subprocess.run([uv, "python", "find", want], capture_output=True, text=True)  # noqa: S603
            interp = r.stdout.strip() or None
        if not interp:
            if f"{sys.version_info.major}.{sys.version_info.minor}" != want:
                raise KitError(f"no Python {want} for the {venv} venv (install uv, or pass --venv-{venv})")
            interp = sys.executable
        if path.exists():
            shutil.rmtree(path)
        log = self.log(f"venv-{venv}")
        self.say(f"creating {venv} venv at {path} (Python {want}; log {log.name})")
        if self.run([interp, "-m", "venv", str(path)], log) != 0:
            raise KitError(f"venv creation failed, see {log}")
        pkgs = ["-e", str(self.wt), *spec["packages"]]
        if uv:
            rc = self.run([uv, "pip", "install", "--python", self.py(venv), *pkgs], log, env=self.env_for(venv))
        else:
            rc = self.run([self.py(venv), "-m", "pip", "install", "-q", *pkgs], log, env=self.env_for(venv))
        if rc != 0:
            raise KitError(f"installing {venv} venv packages failed, see {log}")

    def ensure_venv(self, venv: str) -> None:
        probs = self.venv_problems(venv)
        if probs == ["missing"]:
            self.create_venv(venv)
        elif probs and self.recreate:
            self.say(f"{venv} venv mismatched ({'; '.join(probs)}) -- recreating (--recreate)")
            self.create_venv(venv)
        elif probs:
            raise KitError(
                f"{venv} venv at {self.venvs[venv]} does not match its CI leg: {'; '.join(probs)}. "
                f"Fix it, pass --recreate, or point --venv-{venv}/BUGFIX_KIT_VENV_{venv.upper()} elsewhere."
            )
        probs = self.venv_problems(venv)
        if probs:
            raise KitError(f"{venv} venv still wrong after creation: {'; '.join(probs)}")

    def crucible_tag(self) -> str:
        tag = read_pin((self.wt / "tests" / "_crucible_pin.py").read_text(encoding="utf-8"), "PINNED_TAG")
        if not tag:
            raise KitError("could not read PINNED_TAG from tests/_crucible_pin.py")
        return tag

    def corpus_path(self, leg: str) -> Path:
        return self.home / "corpus" / f"language-crucible-{leg}"

    def ensure_corpus(self, leg: str) -> Path:
        """A kit-owned language-crucible clone per leg, at the pin, scrubbed clean."""
        tag = self.crucible_tag()
        dest = self.corpus_path(leg)
        log = self.log(f"corpus-{leg}")
        src = self.crucible_source
        if Path(src).is_dir():
            src = Path(src).resolve().as_uri()
        if not (dest / ".git").exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            if self.run(["git", "clone", "-q", "--depth", "1", "--branch", tag, src, str(dest)], log, cwd=dest.parent):
                raise KitError(f"cloning language-crucible {tag} from {src} failed, see {log}")
        head = _git(dest, "rev-parse", "HEAD")
        want = _git(dest, "rev-parse", "--verify", "--quiet", f"{tag}^{{commit}}", check=False)
        if head != want:
            self.say(f"corpus-{leg}: moving clone to {tag}")
            if self.run(
                ["git", "fetch", "-q", "--depth", "1", "origin", f"refs/tags/{tag}:refs/tags/{tag}"], log, cwd=dest
            ):
                raise KitError(f"fetching {tag} into {dest} failed, see {log}")
            _git(dest, "checkout", "-q", "--detach", tag)
        _git(dest, "checkout", "-q", "--", ".")
        _git(dest, "clean", "-fdxq")
        if _git(dest, "rev-parse", "HEAD") != _git(dest, "rev-parse", f"{tag}^{{commit}}"):
            raise KitError(f"corpus clone {dest} is off-pin ({tag})")
        return dest

    def check_safe_paths(self) -> None:
        """An IGNORED_DIRECTORIES name anywhere in the corpus path silently zeroes doc coverage."""
        sys.path.insert(0, str(self.wt))
        try:
            from gitgalaxy.standards.gitgalaxy_config import APERTURE_CONFIG

            ignored = {d.lower() for d in APERTURE_CONFIG["IGNORED_DIRECTORIES"]}
        except Exception:
            return
        finally:
            sys.path.pop(0)
        for leg in ("full", "zero"):
            bad = [p for p in self.corpus_path(leg).resolve().parts if p.lower() in ignored]
            if bad:
                raise KitError(
                    f"corpus path {self.corpus_path(leg)} has ignored-directory component(s) {bad}: "
                    "it would silently zero documentation coverage. Use --home somewhere else."
                )

    def link_corpora(self) -> None:
        link = self.wt / ".mainframe_corpora"
        if self.wt.resolve() != self.main.resolve():
            if link.is_symlink() and Path(os.readlink(link)) != self.corpora:
                link.unlink()
            if not link.exists() and not link.is_symlink():
                self.corpora.mkdir(parents=True, exist_ok=True)
                link.symlink_to(self.corpora)
        # `.mainframe_corpora/` in .gitignore matches a directory, not a symlink.
        exclude = Path(_git(self.wt, "rev-parse", "--path-format=absolute", "--git-common-dir")) / "info" / "exclude"
        exclude.parent.mkdir(parents=True, exist_ok=True)
        lines = exclude.read_text(encoding="utf-8").splitlines() if exclude.exists() else []
        if "/.mainframe_corpora" not in lines:
            with exclude.open("a", encoding="utf-8") as fh:
                fh.write("/.mainframe_corpora\n")

    def estate_pin_problem(self) -> str | None:
        pin_file = self.wt / "tests" / "_estate_crucible_pin.py"
        if not pin_file.exists():
            return "this checkout has no estate-crucible pin"
        ref = read_pin(pin_file.read_text(encoding="utf-8"), "PINNED_REF")
        if not (self.estate_crucible / "key" / "manifest.json").exists():
            return f"no estate-crucible checkout at {self.estate_crucible}"
        head = _git(self.estate_crucible, "rev-parse", "HEAD", check=False)
        want = _git(self.estate_crucible, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False)
        if head != want:
            return f"estate-crucible at {self.estate_crucible} is not on {ref} (git -C ... checkout {ref})"
        return None


# ============================================================================= commands


def cmd_setup(kit: Kit, legs: Iterable[str] = ("full", "zero", "ledger", "audit")) -> bool:
    kit.link_corpora()
    for v in legs:
        if v in kit.venvs:
            kit.ensure_venv(v)
    golden = [v for v in legs if v in ("full", "zero")]
    for leg in golden:
        kit.ensure_corpus(leg)
    if golden:
        kit.check_safe_paths()
    lines = [f"worktree {kit.wt} @ {_git(kit.wt, 'rev-parse', '--short=12', 'HEAD')}"]
    for v in legs:
        if v in kit.venvs:
            lines.append(f"venv {v:<6} {kit.venvs[v]}")
        else:
            cv = kit.wt / ".crucible_venvs" / ("full_precision" if v == "full" else "zero_dependency")
            state = "present" if (cv / "bin" / "python").exists() else "built by crucible_check on first bless"
            lines.append(f"venv {v:<6} {cv} ({state})")
    if golden:
        lines.append(f"crucible {kit.crucible_tag()} -> {kit.home / 'corpus'}")
    lines.append(f"mainframe corpora {kit.corpora}")
    problem = kit.estate_pin_problem()
    lines.append(f"estate-crucible {kit.estate_crucible}" + (f"  (!) {problem}" if problem else " (on pin)"))
    for line in lines:
        kit.say("  " + line)
    return True


def _crucible_env(kit: Kit, leg: str, wt: Path) -> dict[str, str]:
    """crucible_check.py's own environment: no PYTHONPATH (it strips it too), this leg's corpus
    clone, an isolated pytest basetemp so the two legs never share one."""
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "VIRTUAL_ENV", "PYTHONHOME")}
    env["LANGUAGE_CRUCIBLE_PATH"] = str(kit.corpus_path(leg))
    env.setdefault("GITGALAXY_GOLDEN_SCAN_TIMEOUT", "1200")
    env["PYTEST_ADDOPTS"] = f"-p no:cacheprovider --basetemp={kit.run_dir / f'pytest-{leg}-{wt.name}'}"
    return env


def _bless_leg(kit: Kit, leg: str, verify: bool, wt: Path | None = None) -> tuple[bool, str]:
    """`crucible_check.py --mode <leg> --update --yes`, then `crucible_check.py --mode <leg>`
    (the CI-equivalent golden_crucible test) -- the worktree's own wrapper, in its own
    .crucible_venvs/, against this leg's corpus clone."""
    wt = wt or kit.wt
    corpus = kit.ensure_corpus(leg)
    env = _crucible_env(kit, leg, wt)
    tool = str(wt / "tests" / "tools" / "crucible_check.py")
    log = kit.log(f"bless-{leg}")
    rc = kit.run([sys.executable, tool, "--mode", leg, "--update", "--yes"], log, cwd=wt, env=env)
    text = log.read_text(encoding="utf-8", errors="backslashreplace")
    # crucible_check --update exits 0 even when the update crashed: verify the artifact message.
    if rc != 0 or not ("✅ Updated" in text or "No drift detected" in text):
        return False, f"crucible_check --update failed (exit {rc}), see {log}"
    if "Traceback" in text or "<<<<<<<" in text:
        return False, f"crucible_check --update logged an error, see {log}"
    if not verify:
        return True, "blessed (unverified)"
    _git(corpus, "clean", "-fdxq")
    vlog = kit.log(f"verify-{leg}")
    rc = kit.run([sys.executable, tool, "--mode", leg], vlog, cwd=wt, env=env)
    vtext = vlog.read_text(encoding="utf-8", errors="backslashreplace")
    if rc != 0 or ": PASS" not in vtext:
        return False, f"crucible_check --mode {leg} FAILED after the bless, see {vlog}"
    return True, "crucible_check PASS"


CRUCIBLE_VENV_DIRS = {"full": "full_precision", "zero": "zero_dependency"}


def crucible_venv_python(wt: Path, leg: str) -> Path:
    """The interpreter of `wt`'s own crucible venv for a leg ("full" | "zero")."""
    return wt / ".crucible_venvs" / CRUCIBLE_VENV_DIRS[leg] / "bin" / "python"


def scope_leg(mode: str) -> str:
    """scope_check imports golden_diff -> gitgalaxy in its own process, so it needs one venv:
    full-precision for full/both, zero-dependency for a zero-only run."""
    return "full" if mode in ("full", "both") else "zero"


def venv_env(base: dict[str, str], py: Path) -> dict[str, str]:
    """`base` as seen from inside the venv of `py`: no inherited PYTHONPATH / VIRTUAL_ENV /
    PYTHONHOME (they shadow the venv's editable install), venv bin first on PATH."""
    env = {k: v for k, v in base.items() if k not in ("PYTHONPATH", "VIRTUAL_ENV", "PYTHONHOME")}
    env["VIRTUAL_ENV"] = str(py.parent.parent)
    env["PATH"] = f"{py.parent}{os.pathsep}{env.get('PATH', '')}"
    return env


def ensure_crucible_venv(kit: Kit, leg: str) -> Path:
    """The worktree's own crucible venv python for `leg`, built by crucible_check.ensure_venv
    (which also repoints its editable install at this worktree) when absent."""
    py = crucible_venv_python(kit.wt, leg)
    tools = kit.wt / "tests" / "tools"
    if not (tools / "crucible_check.py").exists():
        raise KitError(f"{tools / 'crucible_check.py'} is missing; cannot build the {leg} crucible venv")
    log = kit.log(f"venv-crucible-{leg}")
    code = f"import sys; sys.path.insert(0, {str(tools)!r}); import crucible_check; crucible_check.ensure_venv({leg!r})"
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "VIRTUAL_ENV", "PYTHONHOME")}
    env["LANGUAGE_CRUCIBLE_PATH"] = str(kit.corpus_path(leg))
    rc = kit.run([sys.executable, "-c", code], log, cwd=kit.wt, env=env)
    if rc != 0 or not py.exists():
        raise KitError(f"the {leg} crucible venv {py} is missing and could not be built (exit {rc}), see {log}")
    return py


def cmd_scope(kit: Kit, base: str, expect: str | None, mode: str) -> bool:
    """`scope_check.py`: scan this worktree and --base side by side, bucket the diff by
    language, and (with --expect) fail on anything outside the expected languages. Runs under
    THIS worktree's crucible venv, never the interpreter the kit was started with."""
    leg = scope_leg(mode)
    corpus = kit.ensure_corpus(leg)
    py = ensure_crucible_venv(kit, leg)
    env = venv_env(_crucible_env(kit, leg, kit.wt), py)
    env["LANGUAGE_CRUCIBLE_PATH"] = str(corpus)
    cmd = [str(py), str(kit.wt / "tests" / "tools" / "scope_check.py"), "--base", base, "--mode", mode]
    if expect:
        cmd += ["--expect", expect]
    log = kit.log("scope")
    rc = kit.run(cmd, log, env=env)
    for ln in log.read_text(encoding="utf-8", errors="backslashreplace").splitlines():
        if ln.startswith(("===", "Total differences", "  ", "✅", "❌")) and len(ln) < 200:
            kit.say("  " + ln.strip())
    return rc == 0


def golden_changes_vs_rev(wt: Path, rev: str, leg: str) -> list[tuple[str, bytes | None, bytes | None]]:
    """Changed files of one fixture between `rev` and the working tree."""
    fx = FIXTURES[leg]
    names = set(filter(None, _git(wt, "diff", "--name-only", "--no-renames", rev, "--", fx).splitlines()))
    names |= set(filter(None, _git(wt, "ls-files", "--others", "--exclude-standard", "--", fx).splitlines()))
    names = {n for n in names if n.endswith(".json")}
    old = _cat_files(wt, rev, sorted(names))
    out = []
    for n in sorted(names):
        p = wt / n
        out.append((n[len(fx) + 1 :], old.get(n), p.read_bytes() if p.exists() else None))
    return out


def _cat_files(wt: Path, rev: str, paths: list[str]) -> dict[str, bytes | None]:
    if not paths:
        return {}
    req = "".join(f"{rev}:{p}\n" for p in paths).encode()
    r = subprocess.run(  # noqa: S603
        ["git", "-C", str(wt), "cat-file", "--batch"],  # noqa: S607
        input=req,
        capture_output=True,
        check=True,
    )
    out: dict[str, bytes | None] = {}
    buf, i = r.stdout, 0
    for p in paths:
        nl = buf.index(b"\n", i)
        header = buf[i:nl].decode()
        i = nl + 1
        if header.endswith("missing"):
            out[p] = None
            continue
        size = int(header.split()[2])
        out[p] = buf[i : i + size]
        i += size + 1
    return out


def golden_changes_between_dirs(old: Path, new: Path) -> list[tuple[str, bytes | None, bytes | None]]:
    def files(root: Path) -> set[str]:
        return {str(p.relative_to(root)) for p in root.rglob("*.json")} if root.exists() else set()

    a, b = files(old), files(new)
    out = []
    for rel in sorted(a | b):
        pa, pb = old / rel, new / rel
        if rel in a and rel in b and filecmp.cmp(pa, pb, shallow=False):
            continue
        out.append((rel, pa.read_bytes() if rel in a else None, pb.read_bytes() if rel in b else None))
    return out


def cmd_bless(kit: Kit, legs: list[str], verify: bool) -> bool:
    for leg in legs:
        kit.ensure_corpus(leg)
    kit.check_safe_paths()
    t0 = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(legs)) as pool:
        futs = {leg: pool.submit(_bless_leg, kit, leg, verify) for leg in legs}
        results = {leg: f.result() for leg, f in futs.items()}
    kit.say(f"bless wall time {fmt_secs(time.monotonic() - t0)} ({' + '.join(legs)} in parallel)")
    ok = True
    for leg in legs:
        good, msg = results[leg]
        ok &= good
        summ = summarize_golden(golden_changes_vs_rev(kit.wt, "HEAD", leg))
        moved = "unchanged vs HEAD" if summ.empty else f"{len(summ.channels)} channel(s) moved vs HEAD"
        kit.say(f"  {LEG_LABEL[leg]}: {'PASS' if good else 'FAIL'} -- {msg}; fixture {moved}")
    return ok


def cmd_ledger(kit: Kit, wt: Path | None = None, fetch: bool = True, check: bool = True) -> bool:
    wt = wt or kit.wt
    kit.ensure_venv("ledger")
    env = kit.env_for("ledger", wt)
    log = kit.log("ledger")
    py = kit.py("ledger")
    if fetch and kit.run([py, "tests/tools/mainframe_corpus.py", "fetch"], log, cwd=wt, env=env):
        kit.say(f"  mainframe corpus fetch failed, see {log}")
        return False
    if kit.run([py, "tests/tools/ground_truth_ledger.py", "update"], log, cwd=wt, env=env):
        kit.say(f"  ledger update failed, see {log}")
        return False
    if not check:
        return True
    rc = kit.run(
        [py, "tests/tools/ground_truth_ledger.py", "check", "--summary", str(kit.run_dir / "ledger.md")],
        log,
        cwd=wt,
        env=env,
    )
    changed = bool(_git(wt, "status", "--porcelain", "--", LEDGER_REL))
    kit.say(f"  ledger {'changed (commit it)' if changed else 'unchanged'}; check {'PASS' if rc == 0 else 'FAIL'}")
    if rc:
        bad = [ln for ln in log.read_text(encoding="utf-8").splitlines() if "UNTRIAGED" in ln or "FAIL" in ln][:5]
        for ln in bad:
            kit.say("    " + ln.strip()[:160])
    return rc == 0


def engine_state(wt: Path) -> str:
    """HEAD, plus a hash of uncommitted engine edits (mirrors mainframe_corpus.engine_key)."""
    head = _git(wt, "rev-parse", "HEAD")
    diff = subprocess.run(  # noqa: S603
        ["git", "-C", str(wt), "diff", "HEAD", "--", "gitgalaxy"],
        capture_output=True,
        check=True,
    ).stdout
    untracked = _git(wt, "ls-files", "--others", "--exclude-standard", "--", "gitgalaxy").splitlines()
    h = hashlib.sha1(diff, usedforsecurity=False)
    for u in sorted(untracked):
        h.update(u.encode())
        h.update((wt / u).read_bytes())
    return head if not diff and not untracked else f"{head}+{h.hexdigest()[:12]}"


def estate_cache(kit: Kit, state: str) -> Path:
    pin = read_pin((kit.wt / "tests" / "_estate_crucible_pin.py").read_text(encoding="utf-8"), "PINNED_REF") or "nopin"
    return kit.home / "estate" / f"{state}-{pin}.json"


def score_estate(kit: Kit, wt: Path, out: Path, label: str) -> bool:
    if not (wt / "tests" / "tools" / "estate_crucible.py").exists():
        kit.say(f"  {label}: no tests/tools/estate_crucible.py at this commit")
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    log = kit.log(f"estate-{label}")
    tmp = out.with_suffix(".tmp")
    rc = kit.run(
        [
            kit.py("ledger"),
            "tests/tools/estate_crucible.py",
            "--crucible",
            str(kit.estate_crucible),
            "--json",
            str(tmp),
        ],
        log,
        cwd=wt,
        env=kit.env_for("ledger", wt),
    )
    if rc or not tmp.exists():
        kit.say(f"  {label}: estate_crucible failed (exit {rc}), see {log}")
        return False
    tmp.replace(out)
    return True


def base_sha(kit: Kit, base: str, wt: Path | None = None) -> str:
    wt = wt or kit.wt
    if base.startswith("origin/"):
        _git(wt, "fetch", "-q", "origin", base.split("/", 1)[1], check=False)
    sha = _git(wt, "merge-base", base, "HEAD", check=False)
    if not sha:
        raise KitError(f"no merge-base between {base} and HEAD in {wt}")
    return sha


def ensure_base_estate(kit: Kit, sha: str, refresh: bool = False) -> Path | None:
    cache = estate_cache(kit, sha)
    if cache.exists() and not refresh:
        return cache
    tree = kit.home / "basetrees" / sha[:12]
    if tree.exists():
        _git(kit.wt, "worktree", "remove", "--force", str(tree), check=False)
        shutil.rmtree(tree, ignore_errors=True)
    _git(kit.wt, "worktree", "add", "-q", "--detach", str(tree), sha)
    try:
        ok = score_estate(kit, tree, cache, f"base-{sha[:10]}")
    finally:
        _git(kit.wt, "worktree", "remove", "--force", str(tree), check=False)
    return cache if ok else None


def cmd_estate(kit: Kit, base: str, refresh: bool = False, wt: Path | None = None) -> bool:
    wt = wt or kit.wt
    kit.ensure_venv("ledger")
    problem = kit.estate_pin_problem()
    if problem:
        raise KitError(problem)
    sha = base_sha(kit, base, wt)
    before = ensure_base_estate(kit, sha, refresh)
    after = estate_cache(kit, engine_state(wt))
    if (refresh or not after.exists() or "+" in after.name) and not score_estate(kit, wt, after, "after"):
        return False
    d = estate_delta(_load(before), _load(after))
    kit.say(
        f"  horrors passing {d['pass_before']}/{d['n_horrors']} (base {sha[:10]}) -> "
        f"{d['pass_after']}/{d['n_horrors']}; {len(d['horrors'])} horror(s) moved"
    )
    for h in d["horrors"][:10]:
        kit.say(f"    {h['id']}: {_verdict(h['before'])} -> {_verdict(h['after'])}  {h['title'][:60]}")
    return True


def _load(p: Path | None) -> dict[str, Any] | None:
    return json.loads(p.read_text(encoding="utf-8")) if p and p.exists() else None


def cmd_audit(kit: Kit, base: str, keyword: str | None, tests: list[str], run_tests: bool = True) -> bool:
    kit.ensure_venv("audit")
    env = kit.env_for("audit")
    audits = ("mypy_audit", "ruff_audit", "dead_key_audit")
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futs = {
            a: pool.submit(kit.run, [kit.py("audit"), f"tests/{a}.py", "--ci"], kit.log(a), None, env) for a in audits
        }
        rcs = {a: f.result() for a, f in futs.items()}
    ok = True
    for a in audits:
        ok &= rcs[a] == 0
        kit.say(f"  {a}: {'PASS' if rcs[a] == 0 else 'FAIL -- see ' + str(kit.log(a))}")
    if not run_tests:
        return ok
    if not tests and not keyword:
        sha = base_sha(kit, base)
        changed = _git(kit.wt, "diff", "--name-only", sha, "--", "tests").splitlines()
        changed += _git(kit.wt, "ls-files", "--others", "--exclude-standard", "--", "tests").splitlines()
        tests = sorted({t for t in changed if re.search(r"(^|/)test_[^/]*\.py$", t) and (kit.wt / t).exists()})
        tests = [t for t in tests if not t.endswith("test_golden_crucible.py")]
    if not tests and not keyword:
        kit.say("  tests: none selected (no test files changed vs base; pass paths or -k)")
        return ok
    # the worktree's full-precision crucible venv when it exists (it has every optional
    # engine), else the audit venv; PYTHONPATH pins the worktree's engine either way
    crucible_py = kit.wt / ".crucible_venvs" / "full_precision" / "bin" / "python"
    py = str(crucible_py) if crucible_py.exists() else kit.py("audit")
    cmd = [py, "-m", "pytest", "-q", "-p", "no:cacheprovider", *tests]
    if keyword:
        cmd += ["-k", keyword]
    log = kit.log("tests")
    rc = kit.run(cmd, log, env=kit.env_for("audit"))
    lines = [ln for ln in log.read_text(encoding="utf-8", errors="backslashreplace").splitlines() if " in " in ln]
    kit.say(
        f"  tests ({len(tests)} path(s){', -k ' + keyword if keyword else ''}): {lines[-1].strip('= ') if lines else rc}"
    )
    # exit 5 = nothing collected, acceptable only for a bare -k selection
    return ok and (rc == 0 or (rc == 5 and not tests))


def train_state_path(kit: Kit, wt: Path | None = None) -> Path:
    return kit.home / "trains" / (wt or kit.wt).name / "state.json"


def load_train(kit: Kit) -> dict[str, Any] | None:
    p = train_state_path(kit)
    if not p.exists():
        return None
    state = json.loads(p.read_text(encoding="utf-8"))
    for st in state.get("steps", []):  # only if this worktree still carries those merges
        r = subprocess.run(["git", "-C", str(kit.wt), "merge-base", "--is-ancestor", st["merge"], "HEAD"])  # noqa: S603,S607
        if r.returncode != 0:
            return None
    return state


def build_evidence(kit: Kit, base: str, template: bool = False) -> str:
    sha = base_sha(kit, base)
    golden = {leg: summarize_golden(golden_changes_vs_rev(kit.wt, sha, leg)) for leg in ("full", "zero")}
    old_ledger = _cat_files(kit.wt, sha, [LEDGER_REL]).get(LEDGER_REL)
    new_ledger_p = kit.wt / LEDGER_REL
    ledger = None
    if new_ledger_p.exists():
        ledger = ledger_delta(json.loads(old_ledger) if old_ledger else None, json.loads(new_ledger_p.read_bytes()))
    before = estate_cache(kit, sha)
    after = estate_cache(kit, engine_state(kit.wt))
    estate = estate_delta(_load(before), _load(after)) if after.exists() else None
    return render_evidence(golden, sha, ledger, estate, load_train(kit), template)


def cmd_evidence(kit: Kit, base: str, template: bool, out: Path | None) -> bool:
    md = build_evidence(kit, base, template)
    (kit.run_dir / "evidence.md").write_text(md, encoding="utf-8")
    if out:
        out.write_text(md, encoding="utf-8")
    print(md)
    return True


def cmd_all(kit: Kit, base: str, skip: set[str], keyword: str | None = None, expect: str | None = None) -> bool:
    results: dict[str, bool] = {}
    t0 = time.monotonic()
    steps: list[tuple[str, Callable[[], bool]]] = [
        ("setup", lambda: cmd_setup(kit)),
        ("bless", lambda: cmd_bless(kit, ["full", "zero"], verify=True)),
        ("scope", lambda: cmd_scope(kit, base, expect, "full")),
        ("ledger", lambda: cmd_ledger(kit)),
        ("estate", lambda: cmd_estate(kit, base)),
        ("audit", lambda: cmd_audit(kit, base, keyword, [])),
    ]
    for name, fn in steps:
        if name in skip or (name == "scope" and not expect):
            continue
        results[name] = kit.timed(name, fn)
        if name == "setup" and not results[name]:
            break
    if "evidence" not in skip and results.get("setup", True):
        md = build_evidence(kit, base, template=True)
        (kit.run_dir / "evidence.md").write_text(md, encoding="utf-8")
        kit.say(f"evidence -> {kit.run_dir / 'evidence.md'}")
    total = time.monotonic() - t0
    kit.say("summary: " + ", ".join(f"{n} {s} {fmt_secs(t)}" for n, t, s in kit.timings) + f"; total {fmt_secs(total)}")
    (kit.run_dir / "summary.json").write_text(
        json.dumps({"timings": kit.timings, "total": total, "results": results}, indent=1), encoding="utf-8"
    )
    return all(results.values())


# ----------------------------------------------------------------------------- train


def _resolve_branch(wt: Path, b: str) -> str:
    for ref in (b, f"origin/{b}"):
        sha = _git(wt, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False)
        if sha:
            return sha
    raise KitError(f"branch {b!r} not found (locally or as origin/{b}); git fetch first")


def _restore_generated(wt: Path) -> None:
    paths = [FIXTURES["full"], FIXTURES["zero"], LEDGER_REL]
    _git(wt, "checkout", "HEAD", "--", *paths, check=False)
    _git(wt, "clean", "-fdq", "--", FIXTURES["full"], FIXTURES["zero"], check=False)


def _merge(kit: Kit, wt: Path, branch: str, sha: str) -> tuple[bool, list[str]]:
    log = kit.log("train-merges")
    rc = kit.run(["git", "merge", "--no-ff", "--no-edit", "-m", f"train: merge {branch}", sha], log, cwd=wt)
    if rc == 0:
        return True, []
    conflicted = _git(wt, "diff", "--name-only", "--diff-filter=U").splitlines()
    gen, src = split_conflicts(conflicted)
    if not conflicted or src:
        kit.run(["git", "merge", "--abort"], log, cwd=wt)
        return False, src or ["(merge failed without conflicts -- see log)"]
    for p in gen:
        in_head = subprocess.run(["git", "-C", str(wt), "cat-file", "-e", f"HEAD:{p}"]).returncode == 0  # noqa: S603,S607
        if in_head:
            _git(wt, "checkout", "HEAD", "--", p)
            _git(wt, "add", "--", p)
        else:
            _git(wt, "rm", "-q", "--cached", "--ignore-unmatch", "--", p)
            (wt / p).unlink(missing_ok=True)
    if kit.run(["git", "commit", "--no-edit", "-q"], log, cwd=wt):
        kit.run(["git", "merge", "--abort"], log, cwd=wt)
        return False, ["(commit after resolving generated conflicts failed)"]
    return True, [f"{len(gen)} generated-artifact conflict(s) resolved to the train side"]


def cmd_train(kit: Kit, args: argparse.Namespace) -> bool:
    wt = kit.wt
    state_p = train_state_path(kit)
    state: dict[str, Any] = json.loads(state_p.read_text(encoding="utf-8")) if state_p.exists() else {}
    if _git(wt, "status", "--porcelain", "--untracked-files=no"):
        raise KitError(f"train worktree {wt} has uncommitted changes; commit or reset them first")
    if not state:
        sha = base_sha(kit, args.base)
        if _git(wt, "rev-parse", "HEAD") != sha:
            raise KitError(
                f"train worktree HEAD is not at {args.base} ({sha[:12]}); start a train from a fresh worktree"
            )
        branch = args.branch or f"train/{wt.name}"
        if _git(wt, "rev-parse", "--abbrev-ref", "HEAD") != branch:
            _git(wt, "switch", "-q", "-c", branch)
        state = {"branch": branch, "base": args.base, "base_sha": sha, "steps": []}
    state_p.parent.mkdir(parents=True, exist_ok=True)
    cmd_setup(kit, ("full", "ledger") if (not args.no_estate_per_step or args.ledger_per_step) else ("full",))
    if args.ledger_per_step:
        cmd_ledger(kit, fetch=True, check=False)
        _restore_generated(wt)
    snap_dir = state_p.parent / "snapshot-full"
    estate_ok = not args.no_estate_per_step and kit.estate_pin_problem() is None
    if not args.no_estate_per_step and not estate_ok:
        kit.say(f"estate per step disabled: {kit.estate_pin_problem()}")
    for b in args.branches:
        sha = _resolve_branch(wt, b)
        if subprocess.run(["git", "-C", str(wt), "merge-base", "--is-ancestor", sha, "HEAD"]).returncode == 0:  # noqa: S603,S607
            kit.say(f"{b}: already on the train, skipping")
            continue
        t0 = time.monotonic()
        prev_merge = _git(wt, "rev-parse", "HEAD")
        merged, notes = _merge(kit, wt, b, sha)
        if not merged:
            kit.say(f"{b}: CONFLICTS outside generated artifacts: {', '.join(notes[:6])}")
            if args.skip_conflicting:
                continue
            state_p.write_text(json.dumps(state, indent=1), encoding="utf-8")
            return False
        step: dict[str, Any] = {"branch": b, "sha": sha, "merge": _git(wt, "rev-parse", "HEAD"), "notes": notes}
        # golden attribution: full-precision scan after this merge vs the previous step
        _restore_generated(wt)
        ok, msg = _bless_leg(kit, "full", verify=False, wt=wt)
        if ok:
            if state["steps"] and snap_dir.exists():
                changes = golden_changes_between_dirs(snap_dir, wt / FIXTURES["full"])
            else:
                changes = golden_changes_vs_rev(wt, state["base_sha"], "full")
            summ = summarize_golden(changes)
            step["golden"] = summ.to_json()
            tmp = snap_dir.with_name("snapshot-full.tmp")
            shutil.rmtree(tmp, ignore_errors=True)
            shutil.copytree(wt / FIXTURES["full"], tmp)
            shutil.rmtree(snap_dir, ignore_errors=True)
            tmp.rename(snap_dir)
        else:
            step["notes"].append(f"golden attribution failed: {msg}")
        if args.ledger_per_step:
            prev_ledger = (
                json.loads(Path(state["steps"][-1]["ledger_file"]).read_text(encoding="utf-8"))
                if state["steps"] and state["steps"][-1].get("ledger_file")
                else json.loads(_cat_files(wt, prev_merge, [LEDGER_REL])[LEDGER_REL] or b"{}")
            )
            if cmd_ledger(kit, fetch=False, check=False):
                lf = state_p.parent / f"ledger-{len(state['steps']) + 1}.json"
                shutil.copy(wt / LEDGER_REL, lf)
                step["ledger_file"] = str(lf)
                step["ledger"] = ledger_delta(prev_ledger, json.loads(lf.read_text(encoding="utf-8")))
        _restore_generated(wt)
        if estate_ok:
            prev = estate_cache(kit, prev_merge) if state["steps"] else ensure_base_estate(kit, state["base_sha"])
            after = estate_cache(kit, step["merge"])
            if after.exists() or score_estate(kit, wt, after, f"step{len(state['steps']) + 1}"):
                step["estate"] = estate_delta(_load(prev), _load(after))
        step["seconds"] = round(time.monotonic() - t0, 1)
        state["steps"].append(step)
        state_p.write_text(json.dumps(state, indent=1), encoding="utf-8")
        gs = GoldenSummary.from_json(step["golden"]) if step.get("golden") else None
        est = step.get("estate") or {}
        kit.say(
            f"{b}: merged; golden "
            + (f"{len(gs.channels)} channel(s) / {len(gs.scanned_files())} file(s)" if gs else "n/a")
            + (f"; horrors {est.get('pass_before')}->{est.get('pass_after')}" if est else "")
            + f" ({fmt_secs(step['seconds'])})"
        )
    if args.no_final:
        return True
    return cmd_all(kit, state["base_sha"], set())


# ============================================================================= main


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.cmd == "train":
            wt = args.worktree
            if not wt.exists():
                # a fresh train worktree off --base: `git worktree add` from the checkout the kit lives in
                here = Path(__file__).resolve().parents[2]
                if args.base.startswith("origin/"):
                    _git(here, "fetch", "-q", "origin", args.base.split("/", 1)[1], check=False)
                _git(here, "worktree", "add", "-q", "--detach", str(wt), args.base)
        kit = Kit.from_args(args, args.cmd)
        kit.say(f"{args.cmd} {kit.wt}  (logs: {kit.run_dir})")
        if args.cmd == "setup":
            ok = kit.timed("setup", lambda: cmd_setup(kit))
        elif args.cmd == "bless":
            legs = ["full", "zero"] if args.leg == "both" else [args.leg]
            ok = kit.timed("bless", lambda: cmd_bless(kit, legs, not args.no_verify))
        elif args.cmd == "scope":
            ok = kit.timed("scope", lambda: cmd_scope(kit, args.base, args.expect, args.mode))
        elif args.cmd == "ledger":
            ok = kit.timed("ledger", lambda: cmd_ledger(kit))
        elif args.cmd == "estate":
            ok = kit.timed("estate", lambda: cmd_estate(kit, args.base, args.refresh))
        elif args.cmd == "audit":
            ok = kit.timed("audit", lambda: cmd_audit(kit, args.base, args.keyword, args.tests, not args.no_tests))
        elif args.cmd == "evidence":
            ok = cmd_evidence(kit, args.base, args.template, args.out)
        elif args.cmd == "all":
            ok = cmd_all(kit, args.base, set(filter(None, args.skip.split(","))), args.keyword, args.expect)
        else:
            ok = cmd_train(kit, args)
    except KitError as exc:
        print(f"[kit] ERROR: {exc}", file=sys.stderr)
        return 2
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
