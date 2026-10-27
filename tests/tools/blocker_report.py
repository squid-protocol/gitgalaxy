#!/usr/bin/env python3
"""#5054: one run, two blocker reports -- a FULL one that stays with the customer and an ANONYMIZED twin they can send us.

    python tests/tools/blocker_report.py PROOF_BLOCKERS.json --out DIR [--salt-file FILE] [--redact-more subclass counts]
    python tests/tools/blocker_report.py --manifest          # print the fields the anonymized report contains

PROOF_BLOCKERS.json is `proof_blockers.py DIR --json` (the data #4493 / #5051 build on; nothing is re-derived here).
Writes DIR/blocker_report.full.{md,json} and DIR/blocker_report.anon.{md,json}.

The anonymized report is built from an ALLOW-LIST, never by scrubbing the full one: every blocker is reduced to
(category, sub-class, construct signature, counts); a signature is assembled only from fixed vocabulary (CICS verbs and
option names from the command spec, refusal exception classes, fixed gap phrases). Any name in a gap -- program,
copybook, field, file, table -- is replaced by `KIND_xxxx`, a salted HMAC-SHA256 prefix. The salt is one random value
per customer, kept in --salt-file on their side and never written to either report: the same salt gives the same hashes
every run (blockers compare over time), another salt gives different ones (nothing matches across customers).
Unknown gap text falls to category `other` with no text at all. The schema is docs/language_status/blocker_report_schema.md.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import importlib.metadata
import json
import re
import secrets
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO))

import gap_prevalence as gp  # noqa: E402

SCHEMA_VERSION = "1.2"
HASH_HEX = 6
REDACTIONS = ("subclass", "counts", "repro")

# The fields of one anonymized blocker, and of the report around them: the manifest a security team approves.
ANON_BLOCKER_FIELDS = {
    "id": "salted hash of the construct signature (stable per customer salt)",
    "category": "blocker category from a fixed list",
    "subclass": "sub-class from fixed vocabulary (CICS verb, refusal class, fact kind); dropped by --redact-more subclass",
    "construct": "ranking key of the construct class (gap_prevalence vocabulary, #5865); dropped by --redact-more subclass",
    "signature": "construct signature built from fixed vocabulary; every customer name is a KIND_xxxx hash",
    "repro": "optional minimal synthetic COBOL snippet built from the signature, made-up names; dropped by --redact-more repro",
    "programs_blocked": "programs the gap blocks (count)",
    "programs_only_gap": "programs for which it is the only gap left (count)",
    "programs_one_away": "programs it leaves one gap from proven (count)",
}
ANON_REPORT_FIELDS = {
    "schema_version": "version of this schema",
    "kind": "the constant string anonymized",
    "engine_version": "GitGalaxy package version that produced the report",
    "rule_catalogue": "version of the blocker classifier's rule catalogue",
    "estate": "KIND hash of the estate name (salted)",
    "totals": "translated-whole and proven program counts",
    "blockers": "list of the blocker objects above",
    "manifest": "this list of fields",
    "redactions": "the --redact-more options applied",
}
RULE_CATALOGUE = "2"

CATEGORIES = (
    "unresolved-link", "refusal", "cics-command", "runtime-fact", "no-case", "known-unproven",
    "scenario-differs", "coverage", "environment", "other",
)  # fmt: skip


# ---- vocabulary: the only words a signature may carry -------------------------------------------------------------
def _vocabulary() -> frozenset[str]:
    from gitgalaxy.standards.cics.commands import COMMANDS  # lazy: the CICS spec is a big import
    from gitgalaxy.standards.cics.eib import EIB_FACTS

    words: set[str] = set(EIB_FACTS)
    for key, cmd in COMMANDS.items():
        words.update(key.split())
        words.update(str(o).upper() for o in cmd.options)
    words.update({"RESP", "RESP2", "NOHANDLE", "EXEC", "CICS"})
    return frozenset(w for w in words if re.fullmatch(r"[A-Z][A-Z0-9]*", w))


_VOCAB: frozenset[str] | None = None


def vocabulary() -> frozenset[str]:
    global _VOCAB
    if _VOCAB is None:
        _VOCAB = _vocabulary()
    return _VOCAB


# ---- salted hashes ------------------------------------------------------------------------------------------------
def load_salt(path: Path | None) -> bytes:
    """The customer's salt: read from `path`, created (32 random bytes, hex) when missing. No path -> a one-off salt."""
    if path is None:
        return secrets.token_bytes(32)
    if path.is_file():
        return bytes.fromhex(path.read_text(encoding="utf-8").strip())
    salt = secrets.token_bytes(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(salt.hex() + "\n", encoding="utf-8")
    path.chmod(0o600)
    return salt


def hashed(salt: bytes, kind: str, name: str) -> str:
    """`PGM_7f3a1c`: HMAC-SHA256(salt, kind:NAME) prefix. Case-folded, so a name hashes the same however it is written."""
    mac = hmac.new(salt, f"{kind}:{name.upper()}".encode(), hashlib.sha256).hexdigest()
    return f"{kind}_{mac[:HASH_HEX]}"


# ---- gap string -> (category, subclass, signature) ----------------------------------------------------------------
_FIXED = {
    "no case": ("no-case", "no equivalence case"),
    "no det port (crucible)": ("no-case", "no det port"),
    "not proven in CI: Db2": ("environment", "Db2 proof lane"),
    "coverage: live paragraphs no scenario runs": ("coverage", "paragraphs"),
    "coverage: branch outcomes no scenario runs": ("coverage", "branches"),
    "coverage: unknown (no sweep, no evidence record)": ("coverage", "unknown"),
    "coverage: not measured for a LINKed program": ("coverage", "linked not measured"),
}


def _words_ok(text: str, vocab: frozenset[str]) -> bool:
    return all(w in vocab for w in text.split())


def classify(gap: str, salt: bytes) -> tuple[str, str, str]:
    """(category, subclass, signature) of one gap string. Names become hashes; unknown text is dropped."""
    vocab = vocabulary()
    gap = gap.strip()
    if gap in _FIXED:
        cat, sub = _FIXED[gap]
        return cat, sub, gap
    m = re.fullmatch(r"missing copybook (\S+?)( \(ambiguous\))?", gap)
    if m:
        sub = "ambiguous copybook" if m.group(2) else "copybook"
        return "unresolved-link", sub, f"missing copybook{m.group(2) or ''} {hashed(salt, 'CPY', m.group(1))}"
    m = re.match(r"refused: (macro-level CICS|CICS Assembler)", gap)
    if m:
        return "environment", "dialect", f"refused: {m.group(1)}"
    m = re.match(r"refused: ([A-Z][A-Za-z]*(?:Error|Exception|Refusal)):", gap) or re.fullmatch(
        r"refused: ([A-Z][A-Za-z]*(?:Error|Exception|Refusal))", gap
    )
    if m:  # the message may hold names: only the refusal class survives
        return "refusal", m.group(1), f"refused: {m.group(1)}"
    m = re.fullmatch(r"EXEC CICS ((?:[A-Z][A-Z0-9]* ?)+)", gap + " ")
    if m:
        toks = m.group(1).split()
        kept = [t if t in vocab else hashed(salt, "OPT", t) for t in toks]
        verb = " ".join(t for t in toks[:2] if t in vocab) or "unknown"
        return "cics-command", verb, "EXEC CICS " + " ".join(kept)
    if gap.startswith("EXEC CICS"):
        return "cics-command", "unknown", "EXEC CICS (no reason given)" if "no reason given" in gap else "EXEC CICS"
    m = re.fullmatch(r"fact: (\S+)", gap)
    if m:
        name = m.group(1)
        return "runtime-fact", "EIB/ASSIGN", "fact: " + (name if name in vocab else hashed(salt, "FLD", name))
    m = re.fullmatch(r"known unproven: (#\d+)", gap)
    if m:
        return "known-unproven", "baseline", f"known unproven: {m.group(1)}"
    m = re.fullmatch(r"scenario differs: (.*)", gap)
    if m:
        what = m.group(1).strip()
        if what in ("java side failed", "not proven (no report kept)", "not proven (no diff recorded)"):
            return "scenario-differs", what, gap
        toks = what.split()
        event, rest = (toks[0], toks[1:]) if toks else ("output", [])
        sig_ev = event if event in vocab or event == "output" else hashed(salt, "EVT", event)
        sig = " ".join([sig_ev] + [hashed(salt, "FLD", t) for t in rest])
        return "scenario-differs", sig_ev, f"scenario differs: {sig}"
    m = re.fullmatch(r"coverage: LINKed program (\S+) has (live paragraphs|branch outcomes) no scenario runs", gap)
    if m:
        what = "paragraphs" if m.group(2).startswith("live") else "branches"
        return "coverage", f"linked {what}", f"coverage: LINKed program {hashed(salt, 'PGM', m.group(1))} {what}"
    return "other", "unclassified", "unclassified"


def construct_key(gap: str) -> str:
    """The gap's key in docs/language_status/gap_prevalence.md (`gap_prevalence.scrub_key`: a closed vocabulary, so no
    customer name survives), so a customer blocker joins a ranking row. A CICS command keeps only the words of the
    command spec; the first other word ends it."""
    key = gp.scrub_key(gap.strip())
    if key.startswith("EXEC CICS"):
        vocab = vocabulary()
        kept: list[str] = []
        for tok in key.split()[2:]:
            if tok not in vocab:
                break
            kept.append(tok)
        return " ".join(["EXEC CICS", *kept]) if kept else "EXEC CICS: other"
    return key


_HASH = re.compile(r"[A-Z]{3}_[0-9a-f]{%d}" % HASH_HEX)


def _cobol_name(token: str) -> str:
    """`PGM_7f3a1c` -> `PGM-7F3A1C`: a hash as a legal COBOL name."""
    return token.replace("_", "-").upper()


def repro(cat: str, sig: str) -> str | None:
    """A minimal synthetic COBOL snippet that holds only the construct, from a signature that is already allow-listed
    (vocabulary words and KIND_xxxxxx hashes). None where no construct can be rebuilt from the signature."""
    vocab = vocabulary()
    head = ["       IDENTIFICATION DIVISION.", "       PROGRAM-ID. REPRO1."]
    if cat == "unresolved-link":
        m = re.fullmatch(r"missing copybook(?: \(ambiguous\))? (CPY_[0-9a-f]+)", sig)
        if m and _HASH.fullmatch(m.group(1)):
            body = [
                "       DATA DIVISION.",
                "       WORKING-STORAGE SECTION.",
                f"           COPY {_cobol_name(m.group(1))}.",
            ]
            return "\n".join(head + body) + "\n"
    elif cat == "cics-command" and sig.startswith("EXEC CICS "):
        toks = sig.split()[2:]
        if toks and all(t in vocab or _HASH.fullmatch(t) for t in toks):
            stmt = (
                "           EXEC CICS "
                + " ".join(_cobol_name(t) if _HASH.fullmatch(t) else t for t in toks)
                + " END-EXEC."
            )
            return "\n".join(head + ["       PROCEDURE DIVISION.", stmt, "           GOBACK."]) + "\n"
    elif cat == "runtime-fact":
        m = re.fullmatch(r"fact: (\S+)", sig)
        if m and (m.group(1) in vocab or _HASH.fullmatch(m.group(1))):
            body = ["       DATA DIVISION.", "       WORKING-STORAGE SECTION.", "       01 WS-OUT PIC X(8).",
                    "       PROCEDURE DIVISION.", f"           MOVE {_cobol_name(m.group(1))} TO WS-OUT.", "           GOBACK."]  # fmt: skip
            return "\n".join(head + body) + "\n"
    return None


# ---- the two reports ----------------------------------------------------------------------------------------------
def engine_version() -> str:
    try:
        return importlib.metadata.version("gitgalaxy")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def full_report(res: dict[str, Any], estate: str) -> dict[str, Any]:
    """Everything: the ranking and each program with its gaps, case and details. Never leaves the customer."""
    return {
        "schema_version": SCHEMA_VERSION, "kind": "full", "engine_version": engine_version(), "estate": estate,
        "totals": {"whole": res.get("whole", 0), "proven": res.get("proven", 0)},
        "blockers": [{**g, "construct": construct_key(g["gap"])} for g in res.get("gaps", [])],
        "programs": [dict(p) for p in res.get("programs", [])],
    }  # fmt: skip


def anon_report(res: dict[str, Any], salt: bytes, estate: str, redact_more: tuple[str, ...] = ()) -> dict[str, Any]:
    """The allow-listed twin. Blockers sharing a signature merge, so counts are per construct, not per raw string.
    Counts of a merged blocker: programs_blocked is recomputed from the programs, not summed (a program with two
    gaps that merge is counted once)."""
    for r in redact_more:
        if r not in REDACTIONS:
            raise ValueError(f"--redact-more: unknown {r!r}; choose from {', '.join(REDACTIONS)}")
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}
    seen: dict[tuple[str, str, str], set[tuple[str, str]]] = defaultdict(set)
    index = {g["gap"]: classify(g["gap"], salt) for g in res.get("gaps", [])}
    construct: dict[tuple[str, str, str], str] = {}
    for g in res.get("gaps", []):
        key = index[g["gap"]]
        construct.setdefault(key, construct_key(g["gap"]))
        b = merged.setdefault(key, {"programs_only_gap": 0, "programs_one_away": 0})
        b["programs_only_gap"] += g.get("only", 0)
        b["programs_one_away"] += g.get("one_away", 0)
    for p in res.get("programs", []):
        for gap in p.get("gaps", []):
            seen[index.get(gap) or classify(gap, salt)].add((p["corpus"], p["program"]))
    blockers = []
    for (cat, sub, sig), b in merged.items():
        blocker: dict[str, Any] = {"id": hashed(salt, "BLK", sig), "category": cat}
        if "subclass" not in redact_more:
            blocker["subclass"] = sub
        if "subclass" not in redact_more:  # finer than the sub-class, so it goes with it
            blocker["construct"] = construct[(cat, sub, sig)]
        blocker["signature"] = sig
        if "repro" not in redact_more and (snippet := repro(cat, sig)):
            blocker["repro"] = snippet
        if "counts" not in redact_more:
            blocker["programs_blocked"] = len(seen[(cat, sub, sig)])
            blocker.update(b)
        blockers.append(blocker)
    blockers.sort(key=lambda b: (-b.get("programs_only_gap", 0), -b.get("programs_blocked", 0), b["id"]))
    return {
        "schema_version": SCHEMA_VERSION, "kind": "anonymized", "engine_version": engine_version(),
        "rule_catalogue": RULE_CATALOGUE, "estate": hashed(salt, "EST", estate),
        "totals": {"whole": res.get("whole", 0), "proven": res.get("proven", 0)},
        "blockers": blockers, "redactions": list(redact_more),
        "manifest": {"report": ANON_REPORT_FIELDS, "blocker": ANON_BLOCKER_FIELDS},
    }  # fmt: skip


def full_markdown(rep: dict[str, Any]) -> str:
    t = rep["totals"]
    out = [f"# Blocker report (full) -- {rep['estate']}", "",
           "Stays on your machine. The anonymized twin is `blocker_report.anon.*`.", "",
           f"Translated whole: {t['whole']}; proven: {t['proven']}.", "",
           "| only gap | one away | touched | blocker |", "|---:|---:|---:|---|"]  # fmt: skip
    out += [f"| {b['only']} | {b['one_away']} | {b['touched']} | {b['gap']} |" for b in rep["blockers"]]
    out += ["", "## Programs", ""]
    for p in rep["programs"]:
        out.append(f"- `{p['corpus']}` / `{p['program']}` (case: {p.get('case') or 'none'}): "
                   + ("proven" if not p["gaps"] else "; ".join(p["gaps"])))  # fmt: skip
    return "\n".join(out) + "\n"


def anon_markdown(rep: dict[str, Any]) -> str:
    t = rep["totals"]
    out = [f"# Blocker report (anonymized) -- {rep['estate']}", "",
           f"Schema {rep['schema_version']}, engine {rep['engine_version']}, rule catalogue {rep['rule_catalogue']}.",
           f"Translated whole: {t['whole']}; proven: {t['proven']}.", "",
           "| id | category | sub-class | signature | blocked | only gap | one away |", "|---|---|---|---|---:|---:|---:|"]  # fmt: skip
    for b in rep["blockers"]:
        out.append(f"| {b['id']} | {b['category']} | {b.get('subclass', '-')} | {b['signature']} | "
                   f"{b.get('programs_blocked', '-')} | {b.get('programs_only_gap', '-')} | "
                   f"{b.get('programs_one_away', '-')} |")  # fmt: skip
    out += ["", "## What this file contains", ""]
    out += [f"- `{k}`: {v}" for k, v in {**rep["manifest"]["report"], **rep["manifest"]["blocker"]}.items()]
    return "\n".join(out) + "\n"


def write_reports(res: dict[str, Any], out: Path, salt: bytes, estate: str = "estate",
                  redact_more: tuple[str, ...] = ()) -> dict[str, Path]:  # fmt: skip
    """One run, both reports: returns the four paths."""
    out.mkdir(parents=True, exist_ok=True)
    full, anon = full_report(res, estate), anon_report(res, salt, estate, redact_more)
    paths = {
        "full_json": out / "blocker_report.full.json", "full_md": out / "blocker_report.full.md",
        "anon_json": out / "blocker_report.anon.json", "anon_md": out / "blocker_report.anon.md",
    }  # fmt: skip
    paths["full_json"].write_text(json.dumps(full, indent=1) + "\n", encoding="utf-8")
    paths["full_md"].write_text(full_markdown(full), encoding="utf-8")
    paths["anon_json"].write_text(json.dumps(anon, indent=1) + "\n", encoding="utf-8")
    paths["anon_md"].write_text(anon_markdown(anon), encoding="utf-8")
    return paths


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="?", type=Path, help="proof_blockers.py --json output")
    ap.add_argument("--out", type=Path, help="directory for the four report files")
    ap.add_argument("--salt-file", type=Path, help="the customer's salt (created when missing; keep it private)")
    ap.add_argument("--estate", default="estate", help="estate name (hashed in the anonymized report)")
    ap.add_argument("--redact-more", nargs="*", default=[], choices=REDACTIONS)
    ap.add_argument("--manifest", action="store_true", help="print the fields the anonymized report contains")
    args = ap.parse_args(argv)
    if args.manifest:
        print(json.dumps({"report": ANON_REPORT_FIELDS, "blocker": ANON_BLOCKER_FIELDS}, indent=1))
        return 0
    if not args.input or not args.out:
        ap.error("input and --out are required (or --manifest)")
    res = json.loads(args.input.read_text(encoding="utf-8"))
    paths = write_reports(res, args.out, load_salt(args.salt_file), args.estate, tuple(args.redact_more))
    for p in paths.values():
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
