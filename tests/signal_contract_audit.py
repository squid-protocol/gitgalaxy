#!/usr/bin/env python3
"""
Signal Contract Audit (docs/contract_roadmap.md, Phase 1)

Every structural signal the registry can report must have a stated contract in
gitgalaxy/standards/signal_contracts.py: one language-independent sentence saying
what one hit is, a `kind` (what population the hit is drawn from) and a `unit`
(what the count may be compared with). That module is the source of truth; the
one-line comments in gitgalaxy/standards/how_to_add_a_language.md's OUTPUT SCHEMA
are the same sentences in the form the language-authoring prompt needs, and this
audit keeps the two from drifting apart.

USAGE
    python tests/signal_contract_audit.py            # full report, exits 1 on any finding
    python tests/signal_contract_audit.py --ci       # baseline-gated regression check
    python tests/signal_contract_audit.py --render   # rewrite docs/signal_contracts.md
    python tests/signal_contract_audit.py --regenerate-baseline

FINDINGS
    missing-contract   a registry rule key (any language) with no SignalContract
    orphan-contract    a SignalContract naming a key no language defines
    schema-drift       the how_to_add_a_language.md comment for a signal does not
                       contain the contract sentence (case-insensitive); a stated
                       contract and the authoring prompt must say the same thing
    missing-schema     a signal with a contract but no comment line in the schema
                       (extension-pack signals live in their own section and are
                       allowlisted below)
    draft              a contract transcribed from the schema comment and not yet
                       audited across the corpus languages -- see the
                       `rule-contract-audit` skill for how one becomes `stated`

BASELINE (same philosophy as dead_key_audit.py, #325)
The day this audit was wired in, 2 of ~56 signals had a stated contract (api
#2730, args #2773) and the rest were drafts. `--ci` is a REGRESSION gate: it fails
only on findings not already in tests/signal_contract_audit_baseline.json. A
draft becoming stated shrinks the baseline -- that is a deliberate, reviewable
edit made with --regenerate-baseline in the same PR as the contract doc, never a
silent overwrite. `--ci` prints already-resolved baseline entries as an FYI.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from gitgalaxy.standards import signal_contracts as sc  # noqa: E402
from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS  # noqa: E402

BASELINE_PATH = Path(__file__).resolve().parent / "signal_contract_audit_baseline.json"
SCHEMA_DOC = REPO_ROOT / "gitgalaxy" / "standards" / "how_to_add_a_language.md"
RENDER_PATH = REPO_ROOT / "docs" / "signal_contracts.md"

# Schema comment lines look like `        # name: sentence` or
# `        # name (Display Label): sentence`, one per rule key.
_SCHEMA_LINE = re.compile(r"^\s*#\s*([a-z_]+)(?:\s*\([^)]*\))?\s*:\s*(.+?)\s*$")


def registry_keys() -> set[str]:
    keys: set[str] = set()
    for definition in LANGUAGE_DEFINITIONS.values():
        keys.update(definition.get("rules", {}).keys())
    return keys


def schema_comments() -> dict[str, str]:
    """{signal: comment sentence} from the OUTPUT SCHEMA block of the authoring doc."""
    out: dict[str, str] = {}
    for line in SCHEMA_DOC.read_text(encoding="utf-8").splitlines():
        m = _SCHEMA_LINE.match(line)
        if m and m.group(1) not in out:
            out[m.group(1)] = m.group(2)
    return out


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().rstrip(".").lower()


def run_audit() -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    keys = registry_keys()
    contracts = sc.CONTRACTS
    comments = schema_comments()

    for key in sorted(keys):
        if key.startswith("_"):
            if key not in sc.HELPER_KEYS:
                findings.append(
                    {"kind": "missing-contract", "signal": key, "detail": "helper key not described in HELPER_KEYS"}
                )
            continue
        if key not in contracts:
            findings.append(
                {"kind": "missing-contract", "signal": key, "detail": "registry rule key with no SignalContract"}
            )

    for name, c in sorted(contracts.items()):
        if name not in keys:
            findings.append({"kind": "orphan-contract", "signal": name, "detail": "no language defines this rule key"})
        comment = comments.get(name)
        if comment is None:
            if name not in sc.EXTENSION_SIGNALS:
                findings.append(
                    {"kind": "missing-schema", "signal": name, "detail": "no comment line in how_to_add_a_language.md"}
                )
        elif _normalise(c.contract) not in _normalise(comment):
            findings.append(
                {"kind": "schema-drift", "signal": name, "detail": f"schema comment does not contain: {c.contract!r}"}
            )
        if c.status == "draft":
            findings.append(
                {"kind": "draft", "signal": name, "detail": "transcribed, not yet audited across languages"}
            )
    return findings


def _key(f: dict[str, str]) -> str:
    return f"{f['kind']}:{f['signal']}"


def load_baseline() -> set[str]:
    if not BASELINE_PATH.exists():
        return set()
    return set(json.loads(BASELINE_PATH.read_text(encoding="utf-8"))["findings"])


def write_baseline(findings: list[dict[str, str]]) -> None:
    BASELINE_PATH.write_text(
        json.dumps(
            {
                "_doc": "Baseline for tests/signal_contract_audit.py --ci. Each entry is kind:signal. "
                "Shrink it deliberately (a draft becoming stated) with --regenerate-baseline "
                "in the PR that lands the contract; never regenerate to hide a new finding.",
                "findings": sorted(_key(f) for f in findings),
            },
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )


def render() -> str:
    comments = schema_comments()
    lines = [
        "# Signal contracts",
        "",
        "> Rendered from `gitgalaxy/standards/signal_contracts.py` by `tests/signal_contract_audit.py --render`.",
        "> Do not edit by hand -- edit the module and re-render. Roadmap and rationale:",
        "> `docs/contract_roadmap.md`; the method for taking a row from *draft* to *stated*:",
        "> `.claude/skills/rule-contract-audit/SKILL.md`.",
        "",
        "## The stream contract",
        "",
        sc.STREAM_CONTRACT.strip(),
        "",
        "## The count contract (what every row below promises)",
        "",
        sc.COUNT_CONTRACT.strip(),
        "",
        "## Kinds and units",
        "",
        "| kind | one hit is | unit |",
        "|---|---|---|",
    ]
    for kind, (meaning, unit) in sc.KINDS.items():
        lines.append(f"| `{kind}` | {meaning} | `{unit}` |")
    stated = sum(1 for c in sc.CONTRACTS.values() if c.status == "stated")
    lines += [
        "",
        "## Signals",
        "",
        f"{stated} stated, {len(sc.CONTRACTS) - stated} draft. A **draft** row is the schema comment "
        "transcribed as-is; a **stated** row has been audited across the corpus languages and has a "
        "contract doc. `planted` = the keyword-rosetta corpus plants a known count of it (so the "
        "cross-language gate can hold it equal); unplanted signals that feed a risk formula are the "
        "ones the roadmap's Phase 3 must plant or declare absent.",
        "",
        "| signal | phase | kind | status | planted | contract | doc |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, c in sorted(sc.CONTRACTS.items(), key=lambda kv: (sc.PHASE_ORDER.index(kv[1].phase), kv[0])):
        doc = f"[{Path(c.doc).name}]({Path('..') / c.doc})" if c.doc else ""
        if c.issue:
            doc = (doc + " " if doc else "") + f"#{c.issue}"
        planted = "yes" if c.planted else ""
        lines.append(f"| `{name}` | {c.phase} | `{c.kind}` | {c.status} | {planted} | {c.contract} | {doc} |")
    lines += ["", "## Helper keys (not signals)", "", "| key | purpose |", "|---|---|"]
    for k, v in sorted(sc.HELPER_KEYS.items()):
        lines.append(f"| `{k}` | {v} |")
    missing = sorted(k for k in comments if k not in sc.CONTRACTS and not k.startswith("_"))
    if missing:
        lines += ["", f"Schema comments with no contract entry: {', '.join(missing)}"]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ci", action="store_true", help="baseline-gated regression check")
    ap.add_argument("--render", action="store_true", help="rewrite docs/signal_contracts.md")
    ap.add_argument("--regenerate-baseline", action="store_true")
    args = ap.parse_args(argv)

    if args.render:
        RENDER_PATH.write_text(render(), encoding="utf-8")
        print(f"rendered {RENDER_PATH.relative_to(REPO_ROOT)}")

    findings = run_audit()
    if args.regenerate_baseline:
        write_baseline(findings)
        print(f"baseline written: {len(findings)} findings -> {BASELINE_PATH.name}")
        return 0

    by_kind: dict[str, list[dict[str, str]]] = {}
    for f in findings:
        by_kind.setdefault(f["kind"], []).append(f)
    stated = sum(1 for c in sc.CONTRACTS.values() if c.status == "stated")
    print(
        f"signal contracts: {len(sc.CONTRACTS)} entries, {stated} stated, "
        f"{len(by_kind.get('draft', []))} draft, {len(registry_keys())} registry keys"
    )

    if args.ci:
        baseline = load_baseline()
        current = {_key(f) for f in findings}
        new = sorted(current - baseline)
        resolved = sorted(baseline - current)
        for k in resolved:
            print(f"  FYI resolved (shrink the baseline): {k}")
        for f in findings:
            if _key(f) in new:
                print(f"  NEW {f['kind']:18s} {f['signal']:28s} {f['detail']}")
        if new:
            print(f"signal_contract_audit: {len(new)} new finding(s) not in baseline")
            return 1
        print("signal_contract_audit: no new findings")
        return 0

    for kind, items in sorted(by_kind.items()):
        print(f"\n[{kind}] {len(items)}")
        for f in items:
            print(f"  {f['signal']:28s} {f['detail']}")
    return 1 if any(k != "draft" for k in by_kind) else 0


if __name__ == "__main__":
    raise SystemExit(main())
