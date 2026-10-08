#!/usr/bin/env python3
r"""
#4048: one evidence record per ported program -- the claim, the oracle, provenance, approval, staleness.

A record is `gitgalaxy-evidence/1` JSON, committed next to the port:

    tests/equivalence/<case>/evidence.json                        an equivalence case's port
    tests/cics_crucible/ports/<case>/<PROGRAM>/evidence.json      a CICS crucible port

and rendered (never edited) to docs/language_status/evidence/. docs/language_status/evidence_records.md explains
the record; the schema is the one approved in the #4048 proposal.

**Status is computed, never stored.** A record stores the fingerprints of the inputs its proof ran against (the
port, the case, the corpus pin, the declared differences, the harness, the oracle, the generator). `status()`
recomputes them from the tree and names every input that changed. Tools write the evidence; only a person writes an
approval (`approve`, below -- and tests/cobol_mainframe/test_evidence.py fails if any other code path writes one).

Staleness policy (owner decision, #4048 Q1): a change to the port, its case, its corpus pin or its declared
differences makes the record stale and fails CI (test_every_committed_record_is_current). A change to the harness,
the oracle or the generator makes it stale too -- it is shown as stale, never as proven -- but it is re-proven by
the scheduled job (.github/workflows/evidence-refresh.yml: `evidence.py refresh --stale`), not by the PR.

Unproven methods (#4255, owner decision Q7): proof_reach sorts the methods no proof runs into stubs, left as
generated, and ported_unproven (behaviour the port added that no proof runs). PORTED_UNPROVEN_POLICY = "block": a
record with any ported_unproven method is NOT proven. "report" (the other value) keeps them as counts only. Stubs and
left-as-generated methods are always counts only.

    python tests/tools/evidence.py status [KEY ...] [--json] [--ci]     # computed status of every record
    python tests/tools/evidence.py prove KEY [KEY ...] | --all           # run the proof and write the record
    python tests/tools/evidence.py refresh --stale                       # re-prove every record that is stale
    python tests/tools/evidence.py mutation                              # refresh `mutation` from mutation_scores.json
    python tests/tools/evidence.py render [--check]                      # docs/language_status/evidence/
    python tests/tools/evidence.py approve KEY --by NAME --for PURPOSE [--note TEXT]   # a person, at a terminal
    python tests/tools/evidence.py reject  KEY --by NAME --for PURPOSE --note TEXT

KEY is an equivalence case (`carddemo-dateutil`) or a crucible port (`crucible:ca-link-lengths/CALINK`).
`equivalence.py run CASE --record` writes the record of the run it just made.
"""

from __future__ import annotations

import argparse
import datetime
import fnmatch
import functools
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS = REPO_ROOT / "tests" / "tools"
CASES = REPO_ROOT / "tests" / "equivalence"
CRUCIBLE_PORTS = REPO_ROOT / "tests" / "cics_crucible" / "ports"
CRUCIBLE_COVERAGE = REPO_ROOT / "tests" / "cics_crucible" / "coverage.json"
CORPORA = REPO_ROOT / "tests" / "cobol_mainframe" / "corpora.json"
MUTATION_SCORES = REPO_ROOT / "docs" / "language_status" / "mutation_scores.json"
PAGES = REPO_ROOT / "docs" / "language_status" / "evidence"
RECORD_NAME = "evidence.json"
FORMAT = "gitgalaxy-evidence/1"

# ---- the policy switch (#4048 Q7, owner decision 2026-10-04) --------------------------------------------------------
# "block": a port with any ported_unproven method (proof_reach: behaviour the port added that no proof runs) is not
# proven. "report": the methods are counted and shown, and do not change the status. Stubs and left-as-generated
# methods never block under either value. Changing this changes no record: status is computed from the record.
PORTED_UNPROVEN_POLICY = "block"
POLICIES = ("block", "report")

# What a person signs (#4048 Q5). The sign-off is accountability, not COBOL expertise: a named person, not a model,
# took responsibility for accepting this evidence for a stated purpose.
ATTESTATION = ("I reviewed this evidence summary (scenarios run, coverage, unproven methods, declared differences) "
               "and accept it for {purpose}.")  # fmt: skip

# ---- the inputs a proof is fingerprinted against ---------------------------------------------------------------------
INPUTS = ("port", "case", "corpus", "differences", "options", "harness", "oracle", "generator")
# Q1: stale here fails CI (the PR re-proves). #4704: "options" is the program's resolved compile / runtime options
# (gitgalaxy.core.estate_options.effective_options: installation defaults, the estate's PARM, the case's compiler_options,
# LE / Db2 / CICS options), so changing what an estate compiles or runs under makes its proofs stale. The program's own
# CBL / PROCESS cards are source: the corpus pin fixes them.
BLOCKING = ("port", "case", "corpus", "differences", "options")
SCHEDULED = ("harness", "oracle", "generator")  # Q1: stale here is re-proven by the scheduled job
MUTATION_INPUTS = ("port", "case", "corpus", "harness", "oracle")  # Q3: the generator alone keeps a score
HARNESS = ("tests/tools/equivalence.py", "tests/tools/equivalence_common.py", "tests/tools/equivalence_java.py",
           "tests/tools/equivalence_inputs.py", "tests/tools/equivalence_cics.py", "tests/tools/equivalence_call.py",
           "tests/tools/equivalence_cache.py", "tests/tools/equivalence_db2.py", "tests/tools/equivalence_oracle.py",
           "tests/tools/cobol_coverage.py", "tests/tools/java_target_matrix.py")  # fmt: skip
CRUCIBLE_HARNESS = (*HARNESS, "tests/tools/cics_crucible.py", "tests/tools/cics_crucible_compare.py")
ORACLE = ("tests/equivalence/gnucobol.Dockerfile", "tests/equivalence/gnucobol-db2.Dockerfile",
          "tests/equivalence/cics/**", "tests/equivalence/le/**", "tests/equivalence/faults/**",
          "tests/equivalence/db2/**", "tests/tools/equivalence_sql.py")  # fmt: skip
GENERATOR = ("gitgalaxy/tools/cobol_to_java/**",)  # #4048 Q2 (default): the Java generator, not the whole engine
NOT_PORT = ("*/provenance.json", f"*/{RECORD_NAME}")
EMPTY_SHA = hashlib.sha256(b"").hexdigest()

_MODEL_NAMES = re.compile(r"(claude|gpt|gemini|copilot|codex|llama|mistral|\bbot\b|\[bot\]|agent|model|automation)",
                          re.I)  # fmt: skip


# ---- trees and digests ---------------------------------------------------------------------------------------------
def _git(*args: str, binary: bool = False) -> Any:
    proc = subprocess.run(["git", "-C", str(REPO_ROOT), *args], capture_output=True, check=False)  # noqa: S603, S607
    if proc.returncode != 0:
        return None
    return proc.stdout if binary else proc.stdout.decode("utf-8", "replace")


@functools.lru_cache(maxsize=1)
def _files_now() -> tuple[str, ...]:
    """Every file of the working tree git would commit (tracked + untracked, not ignored), repo-relative."""
    out = _git("ls-files", "-z", "--cached", "--others", "--exclude-standard")
    if out is None:
        raise RuntimeError("evidence: the repo's file list needs git (git ls-files)")
    return tuple(sorted({p for p in out.split("\0") if p and (REPO_ROOT / p).is_file()}))


@functools.lru_cache(maxsize=8)
def _files_at(commit: str) -> Optional[tuple[str, ...]]:
    out = _git("ls-tree", "-r", "-z", "--name-only", commit)
    return None if out is None else tuple(sorted(p for p in out.split("\0") if p))


def _match(files: tuple[str, ...], patterns: list[str], exclude: list[str]) -> list[str]:
    def hit(p: str, pats: list[str]) -> bool:
        return any(p == pat or fnmatch.fnmatchcase(p, pat) for pat in pats)

    return [p for p in files if hit(p, patterns) and not hit(p, exclude)]


def tree_sha256(paths: list[str], read: Any = None) -> str:
    """sha256 over sorted repo-relative paths, each fed as `path \\0 bytes \\0` (equivalence_cache.engine_hash's
    scheme, repo-relative so the digest is the same in every checkout)."""
    h = hashlib.sha256()
    for p in sorted(paths):
        data = read(p) if read else (REPO_ROOT / p).read_bytes()
        h.update(p.encode() + b"\0" + data + b"\0")
    return h.hexdigest()


def json_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


# ---- what a record is about ------------------------------------------------------------------------------------------
@dataclass
class Target:
    key: str  # "carddemo-dateutil" | "crucible:ca-link-lengths/CALINK"
    kind: str  # batch | call | cics | crucible
    case: str
    program: str
    record: Path
    port_dir: Path  # this program's own port tree
    specs: dict[str, dict[str, Any]] = field(default_factory=dict)
    corpus: dict[str, str] = field(default_factory=dict)
    db2: bool = False

    @property
    def slug(self) -> str:
        return self.case if self.kind != "crucible" else f"crucible-{self.case}-{self.program}"


def rel_path(p: Path) -> str:
    return p.resolve().relative_to(REPO_ROOT).as_posix()


@functools.lru_cache(maxsize=1)
def _corpus_refs() -> dict[str, str]:
    return {c["name"]: c["ref"] for c in json.loads(CORPORA.read_text(encoding="utf-8"))["corpora"]}


def _crucible_pin() -> str:
    sys.path.insert(0, str(REPO_ROOT / "tests"))
    from _cics_crucible_pin import PINNED_REF  # noqa: PLC0415 -- the pin, read when a crucible record needs it

    return str(PINNED_REF)


def _case_json(case: str) -> dict[str, Any]:
    return dict(json.loads((CASES / case / "case.json").read_text(encoding="utf-8")))


def equivalence_target(case: str) -> Target:
    data = _case_json(case)
    port_case = data.get("port_from", case)
    ports = [port_case, *data.get("uses_ports", [])]
    for extra in data.get("programs", []):  # #4188: a LINKed program's committed model port runs in the proof
        prog = extra["program"].upper()
        for other in sorted(p.parent.name for p in CASES.glob("*/case.json")):
            if other not in ports and (CASES / other / "port").is_dir() and \
                    _case_json(other).get("program", "").upper() == prog:  # fmt: skip
                ports.append(other)
    corpus = data["corpus"]
    specs = {
        "port": {"paths": [f"tests/equivalence/{c}/port/**" for c in ports], "exclude": list(NOT_PORT)},
        "case": {"paths": [f"tests/equivalence/{case}/**"],
                 "exclude": [f"tests/equivalence/{case}/port/**", f"tests/equivalence/{case}/LICENSE",
                             f"tests/equivalence/{case}/NOTICE", f"tests/equivalence/{case}/{RECORD_NAME}"]},
        "harness": {"paths": list(HARNESS), "exclude": []},
        "oracle": {"paths": list(ORACLE), "exclude": []},
        "generator": {"paths": list(GENERATOR), "exclude": ["*/__pycache__/*"]},
    }  # fmt: skip
    return Target(key=case, kind=data.get("kind", "batch"), case=case, program=data["program"].upper(),
                  record=CASES / case / RECORD_NAME, port_dir=CASES / port_case / "port", specs=specs,
                  corpus={"name": corpus, "ref": _corpus_refs().get(corpus, "")}, db2=bool(data.get("db2")))  # fmt: skip


def crucible_target(case: str, program: str) -> Target:
    base = f"tests/cics_crucible/ports/{case}"
    specs = {
        # the proof lays every sibling port of the case (a LINK / XCTL runs the sibling's Java)
        "port": {"paths": [f"{base}/*/overlay/**"], "exclude": []},
        "case": {"paths": [f"tests/cics_crucible/strengthened/{case}/**"], "exclude": []},  # #4049, when it exists
        "harness": {"paths": list(CRUCIBLE_HARNESS), "exclude": []},
        "oracle": {"paths": [], "exclude": []},  # the crucible's expected logs: they are the corpus, at the pin
        "generator": {"paths": list(GENERATOR), "exclude": ["*/__pycache__/*"]},
    }
    return Target(key=f"crucible:{case}/{program}", kind="crucible", case=case, program=program,
                  record=CRUCIBLE_PORTS / case / program / RECORD_NAME, port_dir=CRUCIBLE_PORTS / case / program / "overlay",
                  specs=specs, corpus={"name": "cics-crucible", "ref": _crucible_pin()})  # fmt: skip


def target(key: str) -> Target:
    if key.startswith("crucible:"):
        case, _, program = key[len("crucible:") :].partition("/")
        return crucible_target(case, program.upper())
    return equivalence_target(key)


def targets() -> list[Target]:
    """Every committed port: the equivalence cases with a port/, then the crucible ports."""
    out = [equivalence_target(p.parent.name) for p in sorted(CASES.glob("*/port")) if p.is_dir()]
    out += [
        crucible_target(p.parent.name, p.name) for p in sorted(CRUCIBLE_PORTS.glob("*/*")) if (p / "overlay").is_dir()
    ]
    return out


def port_files(t: Target) -> list[str]:
    """The program's own port files (repo-relative): the overlay tree the record's claim is about."""
    root = rel_path(t.port_dir)
    return _match(_files_now(), [f"{root}/**"], list(NOT_PORT))


def options_input(t: Target) -> dict[str, Any]:
    """#4704: the fingerprint of the program's resolved options -- read from the estate options file and the case in the
    tree now (not from `files`: a historical commit's mutation score does not use this input). `sha256` hashes every
    value (no provenance: a changed note is not a changed option); `semantic_sha256` only the options cobc and the det
    port act on; `legacy_semantic_sha256` the same without the estate's file, which is what a record written before
    this input existed was proven under (see changed)."""
    from gitgalaxy.core.estate_options import effective_options  # noqa: PLC0415 -- the resolver, read when a record needs it

    case = {} if t.kind == "crucible" else _case_json(t.case)
    eff = effective_options(case, program=t.program)
    fp = eff.fingerprint()
    legacy = effective_options(case, estate={}, program=t.program)
    return {"sha256": json_sha256(fp), "semantic_sha256": json_sha256(fp["semantic"]),
            "legacy_semantic_sha256": json_sha256(legacy.semantic()), "estate": fp["estate"], "effective": fp}  # fmt: skip


def compute_inputs(t: Target, differences: Optional[list[Any]] = None, files: Any = None,
                   read: Any = None) -> dict[str, Any]:  # fmt: skip
    """The fingerprints of the target's inputs in the tree now (or, with files / read, at a commit)."""
    files = files if files is not None else _files_now()
    out: dict[str, Any] = {}
    for name, spec in t.specs.items():
        matched = _match(files, spec["paths"], spec["exclude"])
        out[name] = {"paths": spec["paths"], "files": len(matched), "sha256": tree_sha256(matched, read)}
    out["corpus"] = {**t.corpus, "sha256": json_sha256(t.corpus)}
    out["differences"] = {"sha256": json_sha256(differences or [])}
    out["options"] = options_input(t)
    out["digest"] = json_sha256({k: out[k]["sha256"] for k in INPUTS})
    return out


def inputs_at(t: Target, commit: str) -> Optional[dict[str, Any]]:
    """compute_inputs at an earlier commit (git history), for a mutation score judged there; None without it."""
    files = _files_at(commit)
    if files is None:
        return None

    def read(p: str) -> bytes:
        return _git("show", f"{commit}:{p}", binary=True) or b""

    at = Target(**{**t.__dict__, "corpus": dict(t.corpus)})
    if t.kind == "crucible":
        # the manifest, or (a commit from before it) the legacy one-line constant
        pins = _git("show", f"{commit}:tests/crucible_pins.toml")
        m = re.search(r'^\[cics\]\n(?:(?!\[).*\n)*?ref = "(.*)"', pins or "", re.M)
        if not m:
            m = re.search(r'^PINNED_REF = "(.*)"', _git("show", f"{commit}:tests/_cics_crucible_pin.py") or "", re.M)
        at.corpus["ref"] = m.group(1) if m else ""
    else:
        manifest = _git("show", f"{commit}:tests/cobol_mainframe/corpora.json")
        refs = {c["name"]: c["ref"] for c in json.loads(manifest)["corpora"]} if manifest else {}
        at.corpus["ref"] = refs.get(t.corpus["name"], "")
    return compute_inputs(at, [], files, read)


def changed(stored: Optional[dict[str, Any]], now: dict[str, Any], names: tuple[str, ...] = INPUTS) -> list[str]:
    if not stored:
        return list(names)
    out = []
    for n in names:
        if n == "options" and not stored.get(n):
            # #4704: a record from before this input existed was proven under the harness's own reading of the options
            # (IBM's defaults, the case's compiler_options, the program's cards): still current while the estate's file
            # changes no option the harness acts on. The next proof stores the full input.
            if now[n]["semantic_sha256"] != now[n]["legacy_semantic_sha256"]:
                out.append(n)
        elif (stored.get(n) or {}).get("sha256") != now[n]["sha256"]:
            out.append(n)
    return out


# ---- the sections tools write ----------------------------------------------------------------------------------------
def _now_ts() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def harness_commit() -> str:
    head = (_git("rev-parse", "HEAD") or "").strip()
    # tracked files only: the records this run writes (untracked until committed) are not the harness
    dirty = (_git("status", "--porcelain", "--untracked-files=no", "--", "tests/tools", "tests/equivalence",
                  "tests/cics_crucible", "gitgalaxy/tools/cobol_to_java") or "").strip()  # fmt: skip
    return head + ("+uncommitted" if dirty else "")


def proof_section(t: Target, report: dict[str, Any], digest: str) -> dict[str, Any]:
    outputs: dict[str, Any] = {}
    for name, o in (report.get("outputs") or {}).items():
        outputs[name] = {"equal": o.get("equal"), "records": o.get("records", o.get("events"))}
        if o.get("judged_to"):  # #4173 / #4607 (X6): a task compared only up to a LINK not run or a refused WRITEQ
            outputs[name]["judged_to"] = o["judged_to"]
            if o.get("x6"):  # #4270: or X23, a reference past a stated EIBCALEN
                outputs[name]["assumes"] = o["x6"].get("assumes", "X6")
    envs = [e["name"] for e in report.get("environments") or []]
    rc = report.get("return_code") or {}
    sysout = report.get("sysout")
    if t.kind == "batch":
        runs, faults = report.get("runs", 1), len(report.get("faults") or [])
    elif t.kind == "call":
        runs, faults = 1, 0
    else:  # cics, crucible: one run per scenario; a scenario with an injected fault is a fault run
        runs = len(outputs)
        faults = sum(1 for o in (report.get("outputs") or {}).values() if o.get("fired") or o.get("sql_faults"))
    return {
        "at": _now_ts(),
        "verdict": "proven" if report.get("proven") else "not-proven",
        "runs": runs, "fault_runs": faults,
        # #4048 follow-up: the batch step run once more through each of these methods (equivalence.py entry runs)
        **({"entry_runs": [e["method"] for e in report["entries"]]} if report.get("entries") else {}),
        "environments": envs if len(envs) > 1 else None,
        "outputs": outputs,
        "return_code_equal": (rc.get("cobol") == rc.get("java")) if rc else None,
        "sysout_compared": sysout.get("compared") if isinstance(sysout, dict) else None,
        "attributes_compared": None,  # #4053: not reported by the harness yet
        "java_failed": bool(report.get("java_failed")),
        # #4449: a CICS port proven through its deployed entry points too (equivalence_cics java-facade side)
        **({"facade": facade_summary(report["facade"])} if report.get("facade") is not None else {}),
        "harness_commit": harness_commit(),
        "inputs_digest": digest,
    }  # fmt: skip


def facade_summary(fc: dict[str, Any]) -> dict[str, Any]:
    """#4449: the java-facade side of a CICS proof, as the record keeps it."""
    outs = fc.get("outputs") or {}
    failed = [{"scenario": n, "why": ("refused: " + o["refused"]) if o.get("refused") else
               f"differs ({o['equal']}/{o['records']} events equal{', files differ' if o.get('files') else ''})"}
              for n, o in sorted(outs.items()) if not o.get("pass")]  # fmt: skip
    return {"verdict": "proven" if fc.get("proven") else "not-proven", "runs": len(outs),
            "passed": sum(1 for o in outs.values() if o.get("pass")),
            "entry_points": [e["method"] for e in fc.get("entry_points") or []],
            "failed": failed, "error": (fc.get("error") or "")[-500:] or None}  # fmt: skip


_FACADE = re.compile(r"public\s+[\w<>.]+\s+(handleTransaction|handleLink)\s*\(")


def port_facades(t: Target) -> list[str]:
    """#4449: the deployed entry points (Spring facades) a CICS equivalence port's own files declare."""
    if t.kind != "cics" or not t.port_dir.is_dir():
        return []
    return sorted({m for f in sorted(t.port_dir.rglob("*.java"), key=lambda q: q.parts)
                   for m in _FACADE.findall(f.read_text(encoding="utf-8"))})  # fmt: skip


def coverage_section(t: Target, report: dict[str, Any], digest: str) -> Optional[dict[str, Any]]:
    if t.kind == "crucible":
        return crucible_coverage(t, sorted((report.get("outputs") or {}).keys()), digest)
    c = report.get("coverage")
    if not c or "paragraphs" not in c:
        return None
    br = c.get("branches") or {}
    return {"paragraphs": {"covered": c["paragraphs"].get("covered"), "live": c["paragraphs"].get("live")},
            "branches": {"covered": br.get("covered"), "total": br.get("total")},
            "uncovered_branches": [{k: u.get(k) for k in ("line", "kind", "outcome", "unit")}
                                   for u in br.get("uncovered") or []],
            "handler_labels": {k: (c.get("handler_labels") or {}).get(k) for k in ("covered", "total")},
            "source": "the proof's own traced COBOL runs (cobol_coverage.py)", "inputs_digest": digest}  # fmt: skip


def crucible_coverage(t: Target, scenarios: list[str], digest: str) -> Optional[dict[str, Any]]:
    """From tests/cics_crucible/coverage.json (#4023): what the program's proof scenarios execute on the COBOL side."""
    ledger = json.loads(CRUCIBLE_COVERAGE.read_text(encoding="utf-8")).get("programs", {})
    rec = ledger.get(f"{t.case}/{t.program}")
    if rec is None:
        return None
    units: set[str] = set()
    outcomes: set[str] = set()
    for sid in scenarios:
        hit = rec["scenarios"].get(sid) or {}
        units.update(hit.get("units", []))
        outcomes.update(hit.get("outcomes", []))
    return {"paragraphs": {"covered": len(units), "live": rec["live"]},
            "branches": {"covered": len(outcomes), "total": rec["outcomes"]},
            "uncovered_branches": None, "handler_labels": None,
            "source": f"tests/cics_crucible/coverage.json#programs/{t.case}/{t.program}",
            "ledger_sha256": json_sha256(rec), "inputs_digest": digest}  # fmt: skip


def _generated_originals(work: Optional[Path]) -> list[Path]:
    """The generated services the port replaced in the proof's project (equivalence_java / cics_crucible keep them
    under generated_before_overlay/ when they lay the overlay)."""
    if work is None or not work.is_dir():
        return []
    return [p for d in work.rglob("generated_before_overlay") if d.is_dir() for p in d.rglob("*.java")]


def reach_section(t: Target, work: Optional[Path] = None, entries: Iterable[str] = ()) -> dict[str, Any]:
    """#4255: which of the port's methods the proof runs (proof_reach), sorted into its three kinds. `entries`:
    the methods the proof also drove the program through (a batch case's entry runs), roots beside PROOF_ROOTS."""
    from gitgalaxy.tools.cobol_to_java import proof_reach  # noqa: PLC0415 -- the engine's, only when a record is made

    own = [REPO_ROOT / p for p in port_files(t) if p.endswith(".java")]
    originals = _generated_originals(work)
    names = {p.name for p in own}
    generated = [p for p in originals if p.name in names]
    report = proof_reach.analyse(own, roots=(*proof_reach.PROOF_ROOTS, *entries), generated=generated)
    unproven = []
    for cls, r in sorted(report.items()):
        for m in r["unproven"]:
            kind = "stub" if m["stub"] else "left_as_generated" if m["generated"] else "ported_unproven"
            unproven.append({"class": cls, "method": m["method"], "line": m["line"], "kind": kind})
    counts = {k: sum(1 for m in unproven if m["kind"] == k) for k in ("stub", "left_as_generated", "ported_unproven")}
    return {"entry_points": sorted({root for r in report.values() for root in r["roots"]}),
            "unproven": unproven, "counts": counts,
            "generated_compared": bool(generated),  # False: "left as generated" could not be told from "ported"
            "port_sha256": tree_sha256(port_files(t))}  # fmt: skip


def oracle_section(t: Target, fp: Optional[dict[str, Any]]) -> dict[str, Any]:
    if t.kind == "crucible":
        return {"kind": "crucible-expected-logs",
                "source": f"cics-crucible {t.corpus['ref']}: each scenario's hand-written expected event log, derived "
                          "from IBM's documentation (its SPEC.md); the java-ported side (runTask) and the java-facade side "
                          "(the deployed entry points, #4343) are compared with it exactly",
                "compiler": None, "image": None, "models": [], "assumptions": None}  # fmt: skip
    case = _case_json(t.case)
    models = _match(_files_now(), list(ORACLE), [])
    return {"kind": "gnucobol-models",
            "compiler": (fp or {}).get("cobc"), "package": (fp or {}).get("gnucobol3"),
            "flags": "-std=ibm -fsign=EBCDIC", "compiler_options": case.get("compiler_options"),
            "image": ({"name": fp["image"]["name"], "id": fp["image"]["id"], "base": fp.get("base"),
                       "matches_pin": fp.get("matches_pin"), "mismatches": fp.get("mismatches")} if fp else None),
            "models": [{"path": p, "sha256": hashlib.sha256((REPO_ROOT / p).read_bytes()).hexdigest()} for p in models],
            "assumptions": None}  # fmt: skip


def provenance_section(t: Target) -> dict[str, Any]:
    prov_path = (t.port_dir / "provenance.json") if t.kind != "crucible" else t.port_dir.parent / "provenance.json"
    if not prov_path.is_file():  # #4048 Q6 (default): a hand port -- a person, named by git where it can be
        first = (
            (_git("log", "--diff-filter=A", "--format=%an|%h|%as", "--", rel_path(t.port_dir)) or "")
            .strip()
            .splitlines()
        )
        author, commit, day = (first[-1].split("|") + ["", "", ""])[:3] if first else ("", "", "")
        return {"written_by": "person", "author": author or None, "first_commit": commit or None,
                "first_committed": day or None, "model": None, "provenance_file": None,
                "note": "a hand port: no porting-loop provenance; author and date from the git history"}  # fmt: skip
    p = json.loads(prov_path.read_text(encoding="utf-8"))
    attempts = p.get("attempts")
    out = {"written_by": "model" if p.get("model") else "person", "model": p.get("model"),
           "backend": p.get("backend") if p.get("backend") != "command" else p.get("command"),
           "attempt": p.get("attempt"), "attempts": len(attempts) if isinstance(attempts, list) else attempts,
           "ticket_sha256": p.get("ticket_sha256"), "porting_rules_sha256": p.get("porting_rules_sha256"),
           "proposed_at": p.get("proposed") or p.get("proposed_at"),
           "generator_version": p.get("generator_version"),  # not recorded by the loop today
           "edited_after": p.get("edited_after"),
           "provenance_file": {"path": rel_path(prov_path), "format": p.get("format"),
                               "sha256": hashlib.sha256(prov_path.read_bytes()).hexdigest()}}  # fmt: skip
    if t.kind == "crucible":
        proof = p.get("proof") or {}
        again = proof.get("reproven") or []
        out["crucible_ref_proven"] = (again[-1] if again else proof).get("crucible_ref")
    return out


def _score(n: int, d: int) -> str:
    return f"{n}/{d}"


def mutation_section(t: Target) -> Optional[dict[str, Any]]:
    """The port's entry of docs/language_status/mutation_scores.json (#4047), with the inputs it was judged against
    (recomputed at its commit from git history; None in a shallow clone)."""
    if not MUTATION_SCORES.is_file():
        return None
    case_key = t.case if t.kind != "crucible" else f"crucible:{t.case}"
    ports = json.loads(MUTATION_SCORES.read_text(encoding="utf-8"))["ports"]
    e = next((p for p in ports if p["case"] == case_key and p["program"].upper() == t.program), None)
    if e is None:
        return None
    tot = e["total"]
    judged = tot["killed"] + tot["survived"]
    commit = e.get("rejudged", {}).get("commit") or e["commit"]
    at = inputs_at(t, commit)
    return {"commit": e["commit"], "rejudged": e.get("rejudged"), "seed": e.get("seed"), "mode": e.get("mode"),
            "mutants": e["mutants"], "chosen": e["chosen"],
            "killed": tot["killed"], "survived": tot["survived"], "stillborn": tot["stillborn"],
            "survivors": {k: tot.get(k, 0) for k in ("case_gap", "harness_gap", "equivalent", "unreachable",
                                                     "untriaged")},
            "score_raw": _score(tot["killed"], judged),
            "score_adjusted": _score(tot["killed"], judged - tot.get("equivalent", 0) - tot.get("unreachable", 0)),
            "source": f"docs/language_status/mutation_scores.json#{case_key}/{t.program}",
            "inputs": ({k: {"sha256": at[k]["sha256"]} for k in MUTATION_INPUTS} if at else None)}  # fmt: skip


# ---- the record --------------------------------------------------------------------------------------------------------
def new_record(t: Target) -> dict[str, Any]:
    return {"format": FORMAT, "case": t.key if t.kind != "crucible" else f"crucible:{t.case}", "program": t.program,
            "kind": t.kind, "port": None, "inputs": None, "proof": None, "coverage": None, "reach": None,
            "mutation": None, "differences": [], "oracle": None, "provenance": None, "approvals": []}  # fmt: skip


def load(t: Target) -> Optional[dict[str, Any]]:
    return json.loads(t.record.read_text(encoding="utf-8")) if t.record.is_file() else None


def save(t: Target, rec: dict[str, Any]) -> None:
    """Write the tool-owned sections. The approvals on disk are kept exactly as they are: a tool never writes one."""
    old = load(t)
    rec = {**rec, "approvals": (old or {}).get("approvals", [])}
    t.record.write_text(json.dumps(rec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def record_proof(t: Target, report: dict[str, Any], work: Optional[Path] = None) -> dict[str, Any]:
    """Write the record of a proof that just ran on the committed port and case (report = its report.json)."""
    rec = load(t) or new_record(t)
    inputs = compute_inputs(t, rec.get("differences"))
    own = port_files(t)
    rec.update({
        "port": {"paths": own, "sha256": tree_sha256(own),
                 "entry_points": None},  # filled from reach below
        "inputs": inputs,
        "proof": proof_section(t, report, inputs["digest"]),
        "coverage": coverage_section(t, report, inputs["digest"]),
        "reach": reach_section(t, work, [e["method"] for e in report.get("entries") or []]
                               + [e["method"] for e in (report.get("facade") or {}).get("entry_points") or []]),
        "mutation": mutation_section(t),
        "oracle": oracle_section(t, report.get("oracle")),
        "provenance": provenance_section(t),
    })  # fmt: skip
    rec["port"]["entry_points"] = rec["reach"]["entry_points"]
    save(t, rec)
    return rec


def record_equivalence_run(case: str, work: Path) -> dict[str, Any]:
    """`equivalence.py run CASE --record`: the record of the run in `work`."""
    report = json.loads((work / "report.json").read_text(encoding="utf-8"))
    return record_proof(equivalence_target(case), report, work)


def refresh_mutation(keys: Optional[list[str]] = None) -> list[str]:
    """Re-read every record's `mutation` from mutation_scores.json (mutation_scores.py build calls this)."""
    done = []
    for t in targets():
        if keys and t.key not in keys:
            continue
        rec = load(t)
        if rec is None:
            continue
        rec["mutation"] = mutation_section(t)
        save(t, rec)
        done.append(t.key)
    return done


# ---- status: computed, never stored --------------------------------------------------------------------------------------
def status(rec: Optional[dict[str, Any]], t: Target, *, live: bool = True,
           policy: str = PORTED_UNPROVEN_POLICY) -> dict[str, Any]:  # fmt: skip
    """{"status", "reasons", "stale", "blocking", "approved"}. live=False judges the record alone (the rendered page):
    no comparison with the tree."""
    if policy not in POLICIES:
        raise ValueError(f"PORTED_UNPROVEN_POLICY must be one of {POLICIES}, not {policy!r}")
    if rec is None:
        return {"status": "no-record", "reasons": ["no evidence record"], "stale": [], "blocking": [],
                "approved": None, "sections": {}}  # fmt: skip
    reasons: list[str] = []
    stale: list[str] = []
    sections: dict[str, str] = {}
    now = compute_inputs(t, rec.get("differences")) if live else None
    proof = rec.get("proof")
    if now is not None and proof:
        stale = changed(rec.get("inputs"), now)
        if proof.get("inputs_digest") != (rec.get("inputs") or {}).get("digest"):
            stale = list(INPUTS)
    blocking = [s for s in stale if s in BLOCKING]
    reach = rec.get("reach") or {}
    ported = [m for m in reach.get("unproven", []) if m["kind"] == "ported_unproven"]
    if now is not None and reach and reach.get("port_sha256") != tree_sha256(port_files(t)):
        sections["reach"] = "stale: the port changed since"
    against = now if now is not None else rec.get("inputs")  # the tree now, or (live=False) the proof's own inputs
    mut = rec.get("mutation")
    if mut and mut.get("inputs") and against:
        moved = [k for k in MUTATION_INPUTS if mut["inputs"][k]["sha256"] != (against.get(k) or {}).get("sha256")]
        if moved:
            sections["mutation"] = f"stale: {', '.join(moved)} changed since it was judged ({mut['commit']})"
    elif mut:
        sections["mutation"] = "not checked: its commit's inputs are unknown (no git history)"
    if not proof:
        st = "not-proven"
        reasons.append("never proven")
    elif proof["verdict"] != "proven":
        st = "not-proven"
        fc = proof.get("facade") or {}
        reasons.append(
            "the proof failed"
            + (" (the Java side did not build or run)" if proof.get("java_failed") else "")
            + (
                f" through its deployed entry points (java-facade: {fc['passed']}/{fc['runs']} scenarios pass"
                + (", the run failed" if fc.get("error") else "")
                + ")"
                if fc.get("verdict") == "not-proven"
                else ""
            )
        )
    elif t.kind == "cics" and proof.get("facade") is None and port_facades(t):
        st = "not-proven"  # #4449: a CICS online port is proven through its deployed entry points too
        reasons.append(f"not proven through its deployed entry points ({' / '.join(port_facades(t))}): the proof "
                       "predates the java-facade side (#4449); re-prove it")  # fmt: skip
    elif ported and policy == "block":
        st = "not-proven"
        names = ", ".join(sorted({m["method"] for m in ported}))
        reasons.append(f"{len(ported)} ported_unproven method{'s' if len(ported) != 1 else ''} ({names})")
    elif stale:
        st = "stale"
    else:
        st = "proven"
    if stale:
        reasons.append(f"stale: {', '.join(stale)} changed since the proof")
    approved = None
    for a in reversed(rec.get("approvals") or []):
        cur = a.get("inputs_digest") == (rec.get("inputs") or {}).get("digest") and not stale
        approved = {"by": a["by"], "at": a["at"], "decision": a["decision"], "for": a.get("purpose"), "current": cur}
        break
    if st == "proven":
        st = "proven, approved" if approved and approved["current"] and approved["decision"] == "approved" \
            else "proven, unapproved"  # fmt: skip
        if approved and not approved["current"]:
            reasons.append(f"{approved['decision']} by {approved['by']} for an earlier version")
    return {"status": st, "reasons": reasons, "stale": stale, "blocking": blocking, "approved": approved,
            "sections": sections, "policy": policy}  # fmt: skip


# ---- the claim (derived, never typed) ---------------------------------------------------------------------------------
def claim(rec: dict[str, Any], st: dict[str, Any]) -> str:
    p = rec.get("proof") or {}
    prog = rec["program"]
    if not p:
        return f"**{prog}**: no proof has been recorded. Status: **{st['status']}**."
    outs = p.get("outputs") or {}
    equal = sum(o.get("equal") or 0 for o in outs.values())
    total = sum(o.get("records") or 0 for o in outs.values())
    diffs = rec.get("differences") or []
    how = "byte-identical" if not diffs else f"equal under {len(diffs)} declared difference(s)"
    unit = {"call": "calls", "cics": "scenarios", "crucible": "scenarios"}.get(rec["kind"], "runs")
    n = p["runs"] if rec["kind"] != "call" else total
    o = rec.get("oracle") or {}
    oracle = (f"{o.get('compiler') or 'GnuCOBOL'} + the harness's models" if o.get("kind") == "gnucobol-models"
              else "the crucible's hand-written expected logs (derived from IBM's documentation)")  # fmt: skip
    parts = [f"**{prog}**: {how if p['verdict'] == 'proven' else 'NOT equal'} on **{n} {unit}** "
             f"({p['fault_runs']} fault runs{', ' + str(len(p['entry_runs'])) + ' entry runs' if p.get('entry_runs') else ''}"
             f"{', ' + str(len(p['environments'])) + ' environments' if p.get('environments') else ''}; "
             f"{equal}/{total} compared records equal), against **{oracle}**."]  # fmt: skip
    c = rec.get("coverage")
    if c:
        parts.append(f"COBOL coverage **{c['paragraphs']['covered']}/{c['paragraphs']['live']} paragraphs, "
                     f"{c['branches']['covered']}/{c['branches']['total']} branches**.")  # fmt: skip
    m = rec.get("mutation")
    if m:
        s = m["survivors"]
        note = st["sections"].get("mutation", "")
        parts.append(f"Mutation score **{m['score_raw']} raw, {m['score_adjusted']} adjusted** ({m['survived']} "
                     f"survivors: {s['case_gap']} case gaps, {s['harness_gap']} harness gaps, {s['equivalent']} "
                     f"equivalent, {s['unreachable']} unreachable, {s['untriaged']} untriaged)"
                     + (f" -- **{note}**" if note.startswith("stale") else "") + ".")  # fmt: skip
    fc = p.get("facade")
    if fc:
        parts.append(f"Through its deployed entry points (java-facade, #4449): **{fc['passed']}/{fc['runs']} "
                     f"scenarios pass**" + (f", entered by {' / '.join(fc['entry_points'])}" if fc["entry_points"]
                                            else "") + ".")  # fmt: skip
    r = rec.get("reach")
    if r:
        k = r["counts"]
        ported = sorted({x["method"] for x in r["unproven"] if x["kind"] == "ported_unproven"})
        parts.append(f"Proven through **{' / '.join(r['entry_points']) or '(no entry point)'}** only; "
                     f"**{k['ported_unproven']} ported method(s) that no proof runs**"
                     + (f" ({', '.join(ported)})" if ported else "")
                     + f", {k['left_as_generated']} left as generated, {k['stub']} stubs.")  # fmt: skip
    tail = f"Status: **{st['status']}**"
    if st["reasons"]:
        tail += " (" + "; ".join(st["reasons"]) + ")"
    a = st.get("approved")
    if a and a["current"]:
        tail += f"; {a['decision']} by {a['by']} on {a['at'][:10]} for {a['for']}"
    parts.append(tail + ".")
    return " ".join(parts)


# ---- approval: a person, at a terminal ----------------------------------------------------------------------------------
class ApprovalRefused(RuntimeError):
    pass


def _check_approver(by: str, purpose: str, interactive: bool) -> None:
    if not by.strip() or _MODEL_NAMES.search(by):
        raise ApprovalRefused(
            f"--by {by!r}: an approval names the person who takes responsibility, not a tool or model"
        )
    if not purpose.strip():
        raise ApprovalRefused("--for: say what the evidence is accepted for (e.g. 'the Q4 pilot cut-over')")
    if not interactive:
        raise ApprovalRefused("approve / reject run only at a terminal (stdin and stdout a TTY): a person signs, "
                              "never a script, a CI job or a model")  # fmt: skip


def _append_approval(t: Target, rec: dict[str, Any], entry: dict[str, Any]) -> None:
    """THE one place an approval is written (test_no_tool_writes_an_approval holds every other path to it)."""
    rec.setdefault("approvals", []).append(entry)
    t.record.write_text(json.dumps(rec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def sign(t: Target, by: str, purpose: str, decision: str, note: Optional[str], *, interactive: bool,
         confirm: Any = input) -> dict[str, Any]:  # fmt: skip
    _check_approver(by, purpose, interactive)
    rec = load(t)
    st = status(rec, t)
    if rec is None or (decision == "approved" and not st["status"].startswith("proven")):
        raise ApprovalRefused(f"{t.key}: {st['status']} ({'; '.join(st['reasons'])}) -- only a current proof can be "
                              "approved; re-prove it first (evidence.py prove)")  # fmt: skip
    if decision == "rejected" and not (note or "").strip():
        raise ApprovalRefused("reject: --note says why")
    text = claim(rec, st)
    attests = ATTESTATION.format(purpose=purpose.strip())
    print(f'\n{text}\n\nYou ({by}) attest: "{attests}"\nDecision: {decision}.')
    typed = confirm(f"Type your name exactly as given to --by ({by}) to sign, anything else to stop: ")
    if typed.strip() != by.strip():
        raise ApprovalRefused("not signed: the name typed does not match --by")
    entry = {"by": by.strip(), "at": _now_ts(), "decision": decision, "purpose": purpose.strip(),
             "attests": attests, "inputs_digest": rec["inputs"]["digest"], "status": st["status"],
             "claim": text, "note": note}  # fmt: skip
    _append_approval(t, rec, entry)
    return entry


# ---- the rendered pages ---------------------------------------------------------------------------------------------------
def render_page(t: Target, rec: dict[str, Any]) -> str:
    st = status(rec, t, live=False)
    p, inp = rec.get("proof") or {}, rec.get("inputs") or {}
    lines = [f"# Evidence: {rec['program']} ({rec['case']})", "",
             "<!-- generated by tests/tools/evidence.py render from "
             f"{rel_path(t.record)}; do not edit -->", "",
             claim(rec, st), "",
             f"The status above judges the record alone (policy: ported_unproven = {st['policy']}). Whether the tree "
             f"has moved since the proof is computed live: `python tests/tools/evidence.py status {t.key}`.", "",
             "| | |", "|---|---|",
             f"| proof | {p.get('verdict', '-')} at {p.get('at', '-')}, harness `{p.get('harness_commit', '-')}` |",
             f"| inputs digest | `{inp.get('digest', '-')}` |"]  # fmt: skip
    for k in INPUTS:
        v = inp.get(k) or {}
        if k == "options" and not v:
            continue  # #4704: proven before the options input existed
        what = f"{v['name']} @ `{v['ref']}`" if k == "corpus" else (f"{v.get('files')} files" if "files" in v else "")
        lines.append(f"| {k} | {what} `{(v.get('sha256') or '-')[:16]}` |")
    o = rec.get("oracle") or {}
    img = o.get("image") or {}
    lines.append(f"| oracle run | {o.get('kind', '-')}: {o.get('compiler') or o.get('source', '-')}"
                 + (f", image `{(img.get('id') or '')[:19]}` (matches pin: {img.get('matches_pin')})" if img else "")
                 + " |")  # fmt: skip
    pv = rec.get("provenance") or {}
    who = (f"model `{pv.get('model')}`, attempt {pv.get('attempt')}" if pv.get("written_by") == "model"
           else f"person ({pv.get('author') or 'unknown'})")  # fmt: skip
    lines.append(f"| written by | {who} |")
    lines += ["", "## Proof outputs", "", "| output | equal | compared |", "|---|---|---|"]
    for k, v in sorted((p.get("outputs") or {}).items()):
        refusal = f" (judged up to the refusal: {v['assumes']})" if v.get("assumes") else ""
        lines.append(f"| {k} | {v['equal']} | {v['records']}{refusal} |")
    x6 = sorted(k for k, v in (p.get("outputs") or {}).items() if v.get("assumes") == "X6")
    if x6:  # owner decision on #4607: the proof states X6 as an assumption of these tasks
        lines += ["", f"Assumes oracle_assumptions.md X6 for {len(x6)} task(s) ({', '.join(x6)}): each is compared up "
                  "to a WRITEQ whose LENGTH runs past its FROM area, refused on both sides; what z/OS writes there and "
                  "what the task does after it are not claimed (not settled on z/OS, #4050)."]  # fmt: skip
    x22 = sorted(k for k, v in (p.get("outputs") or {}).items() if v.get("assumes") == "X23")
    if x22:  # #4270: a task given a COMMAREA of a stated length that referenced past it
        lines += ["", f"Assumes oracle_assumptions.md X23 for {len(x22)} task(s) ({', '.join(x22)}): each is given a "
                  "COMMAREA shorter than its record and compared up to a reference past EIBCALEN, refused on both "
                  "sides; what z/OS shows there (the storage that follows the area) is not claimed."]  # fmt: skip
    fc = p.get("facade")
    if fc:  # #4449
        lines += ["", "## Through the deployed entry points (java-facade, #4449)", "",
                  f"{fc['passed']}/{fc['runs']} scenarios pass, entered by "
                  f"{' / '.join(fc['entry_points']) or '(no passing scenario)'}."]  # fmt: skip
        if fc.get("failed"):
            lines += ["", "| scenario | why it fails |", "|---|---|"]
            lines += [f"| {f['scenario']} | {f['why']} |" for f in fc["failed"]]
    r = rec.get("reach") or {}
    if r.get("unproven"):
        lines += ["", "## Methods no proof runs (#4255)", "", "| class | method | line | kind |", "|---|---|---|---|"]
        lines += [f"| {m['class']} | `{m['method']}` | {m['line']} | {m['kind']} |" for m in r["unproven"]]
    c = rec.get("coverage") or {}
    if c.get("uncovered_branches"):
        lines += ["", "## Uncovered branches", "", "| line | kind | outcome | paragraph |", "|---|---|---|---|"]
        lines += [f"| {u['line']} | {u['kind']} | {u['outcome']} | {u['unit']} |" for u in c["uncovered_branches"]]
    lines += ["", "## Approvals", ""]
    if not rec.get("approvals"):
        lines.append(
            "None. A person approves with `evidence.py approve` (see docs/language_status/evidence_records.md)."
        )
    for a in rec.get("approvals") or []:
        lines.append(f"- {a['decision']} by **{a['by']}** at {a['at']} for {a.get('purpose')}: \"{a.get('attests')}\""
                     + (f" -- {a['note']}" if a.get("note") else ""))  # fmt: skip
    return "\n".join(lines) + "\n"


def render_index(recs: list[tuple[Target, Optional[dict[str, Any]]]]) -> str:
    lines = ["# Evidence records", "",
             "<!-- generated by tests/tools/evidence.py render; do not edit -->", "",
             "One record per ported program (#4048): docs/language_status/evidence_records.md explains them. The "
             f"status column judges each record alone (policy: ported_unproven = {PORTED_UNPROVEN_POLICY}); run "
             "`python tests/tools/evidence.py status` for staleness against the tree.", "",
             "| program | case | kind | status | why | runs | coverage (para / branch) | mutation (raw / adj) | " +
             "ported unproven | approved |", "|---|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for t, rec in recs:
        if rec is None:
            lines.append(f"| {t.program} | {t.key} | {t.kind} | no record | | | | | | |")
            continue
        st = status(rec, t, live=False)
        p, c, m, r = rec.get("proof") or {}, rec.get("coverage"), rec.get("mutation"), rec.get("reach") or {}
        cov = (
            f"{c['paragraphs']['covered']}/{c['paragraphs']['live']} / {c['branches']['covered']}/{c['branches']['total']}"
            if c
            else "-"
        )
        mut = f"{m['score_raw']} / {m['score_adjusted']}" if m else "-"
        a = st["approved"]
        lines.append(f"| [{t.program}]({t.slug}.md) | {t.key} | {t.kind} | {st['status']} | {'; '.join(st['reasons'])} "
                     f"| {p.get('runs', '-')} | {cov} | {mut} | {(r.get('counts') or {}).get('ported_unproven', '-')} "
                     f"| {a['by'] + ' (' + a['at'][:10] + ')' if a and a['current'] else '-'} |")  # fmt: skip
    return "\n".join(lines) + "\n"


def write_pages() -> int:
    pages = rendered()
    PAGES.mkdir(parents=True, exist_ok=True)
    for p in PAGES.glob("*.md"):
        if p not in pages:
            p.unlink()
    for p, text in pages.items():
        p.write_text(text, encoding="utf-8")
    return len(pages)


def rendered() -> dict[Path, str]:
    recs = [(t, load(t)) for t in targets()]
    out = {PAGES / "README.md": render_index(recs)}
    for t, rec in recs:
        if rec is not None:
            out[PAGES / f"{t.slug}.md"] = render_page(t, rec)
    return out


# ---- validation (no dependency: the shape every record must have) -------------------------------------------------------
_SHA = re.compile(r"^[0-9a-f]{64}$")


def validate(rec: dict[str, Any]) -> list[str]:
    errs = []
    need = ("format", "case", "program", "kind", "port", "inputs", "proof", "coverage", "reach", "mutation",
            "differences", "oracle", "provenance", "approvals")  # fmt: skip
    errs += [f"missing `{k}`" for k in need if k not in rec]
    if rec.get("format") != FORMAT:
        errs.append(f"format is {rec.get('format')!r}, not {FORMAT!r}")
    if rec.get("kind") not in ("batch", "call", "cics", "crucible"):
        errs.append(f"kind {rec.get('kind')!r}")
    inp = rec.get("inputs") or {}
    for k in INPUTS:
        if k == "options" and k not in inp:
            continue  # #4704: a record proven before the options input existed; its next proof stores it
        if not _SHA.match(str((inp.get(k) or {}).get("sha256", ""))):
            errs.append(f"inputs.{k}.sha256 is not a sha256")
    if not _SHA.match(str(inp.get("digest", ""))):
        errs.append("inputs.digest is not a sha256")
    p = rec.get("proof")
    if p is not None:
        if p.get("verdict") not in ("proven", "not-proven"):
            errs.append(f"proof.verdict {p.get('verdict')!r}")
        for k in ("at", "runs", "fault_runs", "outputs", "harness_commit", "inputs_digest"):
            if k not in p:
                errs.append(f"proof.{k} missing")
    r = rec.get("reach")
    if r is not None:
        for m in r.get("unproven", []):
            if m.get("kind") not in ("stub", "left_as_generated", "ported_unproven"):
                errs.append(f"reach.unproven kind {m.get('kind')!r}")
    if not isinstance(rec.get("differences"), list):
        errs.append("differences is not a list")
    for i, a in enumerate(rec.get("approvals") or []):
        for k in ("by", "at", "decision", "purpose", "attests", "inputs_digest", "claim"):
            if k not in a:
                errs.append(f"approvals[{i}].{k} missing")
        if a.get("decision") not in ("approved", "rejected"):
            errs.append(f"approvals[{i}].decision {a.get('decision')!r}")
    return errs


# ---- running proofs ----------------------------------------------------------------------------------------------------
def prove(t: Target, work_root: Path, crucible: Optional[Path] = None, offline: bool = False) -> dict[str, Any]:
    """Run the target's proof on the committed port and case, and write its record. An infrastructure failure (no
    report at all) leaves the record as it was and is returned as {"error": ...}."""
    work = work_root / t.slug
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(p for p in (str(REPO_ROOT), os.environ.get("PYTHONPATH")) if p)}
    if t.kind == "crucible":
        report_dir, keep = work / "report", work / "keep"
        argv = [sys.executable, str(TOOLS / "cics_crucible.py"), "--cases", t.case, "--program", t.program,
                "--sides", "java-ported", "java-facade",  # #4343: runTask, and the deployed entry points
                "--report-dir", str(report_dir), "--keep", str(keep)]  # fmt: skip
        if crucible:
            argv += ["--crucible", str(crucible)]
        if offline:
            argv.append("--offline")
        proc = subprocess.run(argv, capture_output=True, text=True, check=False, env=env)  # noqa: S603
        report_file = report_dir / "report.json"
        if not report_file.is_file():
            return {"key": t.key, "error": (proc.stderr or proc.stdout).strip()[-2000:]}
        rec = record_proof(t, json.loads(report_file.read_text(encoding="utf-8")), keep)
    else:
        argv = [sys.executable, str(TOOLS / "equivalence.py"), "run", t.case, "--keep", str(work), "--record"]
        proc = subprocess.run(argv, capture_output=True, text=True, check=False, env=env)  # noqa: S603
        if not (work / "report.json").is_file() or not t.record.is_file():
            return {"key": t.key, "error": (proc.stderr or proc.stdout).strip()[-2000:]}
        rec = load(t) or {}
    return {"key": t.key, "status": status(rec, t)}


# ---- CLI ----------------------------------------------------------------------------------------------------------------
def _pick(keys: list[str], all_: bool) -> list[Target]:
    if all_ or not keys:
        return targets()
    return [target(k) for k in keys]


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status")
    s.add_argument("keys", nargs="*")
    s.add_argument("--json", action="store_true")
    s.add_argument("--ci", action="store_true", help="exit 1 when a record is stale on a blocking input (Q1)")
    for name in ("prove", "refresh"):
        p = sub.add_parser(name)
        p.add_argument("keys", nargs="*")
        p.add_argument("--all", action="store_true")
        p.add_argument("--stale", action="store_true", help="refresh: only records stale on any input, or missing")
        p.add_argument("--work", type=Path, help="keep the proofs' work trees here")
        p.add_argument("--crucible", type=Path, help="the cics-crucible checkout (at the pin)")
        p.add_argument("--offline", action="store_true")
        p.add_argument("--skip-db2", action="store_true", help="leave the Db2 cases (they need a Db2 container)")
    sub.add_parser("mutation")
    r = sub.add_parser("render")
    r.add_argument("--check", action="store_true", help="exit 1 when a page is not current")
    for name in ("approve", "reject"):
        a = sub.add_parser(name)
        a.add_argument("key")
        a.add_argument("--by", required=True, help="your name: the person who takes responsibility")
        a.add_argument("--for", dest="purpose", required=True, help="what the evidence is accepted for")
        a.add_argument("--note")
    args = ap.parse_args(argv)

    if args.cmd == "status":
        rows = [(t, status(load(t), t)) for t in _pick(args.keys, False)]
        if args.json:
            print(json.dumps({t.key: st for t, st in rows}, indent=1))
        else:
            for t, st in rows:
                print(f"{t.key:45} {st['status']:20} {'; '.join(st['reasons'])}")
        bad = [t.key for t, st in rows if st["blocking"]]
        if args.ci and bad:
            print(f"\n{len(bad)} record(s) stale on the port, case, corpus or differences: re-prove them in this PR "
                  f"(python tests/tools/evidence.py prove {' '.join(bad)})", file=sys.stderr)  # fmt: skip
            return 1
        return 0
    if args.cmd in ("prove", "refresh"):
        work = (args.work or Path(tempfile.mkdtemp(prefix="evidence_"))).resolve()
        failed = 0
        for t in _pick(args.keys, args.all):
            if args.skip_db2 and t.db2:
                print(f"{t.key}: skipped (Db2)")
                continue
            if args.cmd == "refresh" and args.stale:
                st = status(load(t), t)
                if st["status"] != "no-record" and not st["stale"]:
                    continue
            got = prove(t, work, args.crucible, args.offline)
            if "error" in got:
                failed += 1
                print(f"{t.key}: NOT RUN -- {got['error'].splitlines()[-1] if got['error'] else 'no report'}")
                continue
            st = got["status"]
            failed += ((load(t) or {}).get("proof") or {}).get("verdict") != "proven"  # the proof itself failed
            print(f"{t.key}: {st['status']} {'; '.join(st['reasons'])}")
        write_pages()
        return 1 if failed else 0
    if args.cmd == "mutation":
        done = refresh_mutation()
        write_pages()
        print(f"mutation sections refreshed: {len(done)} records")
        return 0
    if args.cmd == "render":
        pages = rendered()
        if args.check:
            bad = [p for p, text in pages.items() if not p.is_file() or p.read_text(encoding="utf-8") != text]
            extra = [p for p in PAGES.glob("*.md") if p not in pages]
            for p in bad + extra:
                print(f"not current: {rel_path(p)}")
            return 1 if bad or extra else 0
        print(f"rendered {write_pages()} pages under {rel_path(PAGES)}")
        return 0
    # approve / reject
    t = target(args.key)
    try:
        sign(t, args.by, args.purpose, "approved" if args.cmd == "approve" else "rejected", args.note,
             interactive=sys.stdin.isatty() and sys.stdout.isatty())  # fmt: skip
    except ApprovalRefused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    write_pages()
    print(f"{t.key}: {args.cmd}d by {args.by}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
