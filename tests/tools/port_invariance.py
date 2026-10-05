#!/usr/bin/env python3
"""Which scanner readings survive a COBOL -> Java port: a regression check that GitGalaxy reads a program and its
deterministic port alike where it should.

    python tests/tools/port_invariance.py check   --work SWEEP_DIR    every det port a sweep emitted (49 pairs)
    python tests/tools/port_invariance.py fixture --work SWEEP_DIR    rewrite the committed 12-pair fixture

A det port (gitgalaxy/tools/cobol_to_java/det) is proven to behave as its COBOL does, statement for statement, so a
reading that ranks the COBOL programs one way and their ports another is the scanner's doing, not the code's. The
CONTRACT readings must keep the programs' rank order (tie-corrected Spearman rho at or above the floor), and two
pair-level facts must hold for every pair: the port has at least as many methods as the COBOL has paragraphs, and
it does file I/O exactly when the COBOL does. DIFFERS names the readings that legitimately change across a port;
they are reported, never asserted. The contract and its measurements: docs/port_invariance_contract.md; the study
it comes from: docs/wiki/05-18-cobol-java-scan-parity.md.

Readings come from GitGalaxy's single-file extraction (Prism.split_streams + StructuralExtractor.splice), whose
counts are the ones a full scan records in file_data (function_count, struct_branch, state_flux, arch_io, arch_ipc;
checked on all 49 pairs on 2026-10-02), so the check needs neither git nor a full pipeline run.

Floors: FULL for the 49-pair check, FIXTURE for the 12 committed pairs (tests/cobol_mainframe/port_invariance/,
chosen so each reading's rho there sits near its 49-pair value). Each floor is the 2026-10-02 measurement less a
margin (0.08 to 0.15); a 12-pair rho moves about 0.05 to 0.1 when one pair swaps rank.
"""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
import sys
from functools import cache
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO_ROOT = TOOLS.parent.parent
FIXTURE_DIR = REPO_ROOT / "tests" / "cobol_mainframe" / "port_invariance"
CASES = REPO_ROOT / "tests" / "equivalence"

# reading -> (file_data column, extraction key, 49-pair floor, fixture floor); measured 2026-10-02 (49 / 12 pairs):
#   function_count 0.937 / 0.912   struct_branch 0.855 / 0.784   state_flux 0.762 / 0.708
#   arch_io        0.871 / 0.958   arch_ipc      0.835 / 0.757
# struct_branch re-measured after Java stopped counting a `?`/`:` inside a literal and a ternary twice (#4170):
# it was 0.826 / 0.745 before.
CONTRACT: dict[str, tuple[str, float, float]] = {
    "function_count": ("functions", 0.85, 0.80),
    "struct_branch": ("branch", 0.75, 0.65),
    "state_flux": ("state_mutation", 0.65, 0.55),
    "arch_io": ("io", 0.75, 0.80),
    "arch_ipc": ("ipc_rpc_bridges", 0.70, 0.60),
}
# readings a port legitimately changes (size, its runtime's overhead, per-scan normalised risk), never asserted
DIFFERS = ("coding_loc", "token_mass", "max_func_complexity", "risk_*", "file_archetype")

# the committed pairs: program -> (equivalence case, corpus-relative COBOL path)
FIXTURE = {
    "ABNDPROC": ("cbsa-abndproc", "src/base/cobol_src/ABNDPROC.cbl"),
    "CBACT03C": ("carddemo-readxref", "app/cbl/CBACT03C.cbl"),
    "CBCUS01C": ("carddemo-readcust", "app/cbl/CBCUS01C.cbl"),
    "CBTRN01C": ("carddemo-dailyval", "app/cbl/CBTRN01C.cbl"),
    "COBTUPDT": ("carddemo-cobtupdt", "app/app-transaction-type-db2/cbl/COBTUPDT.cbl"),
    "COUSR01C": ("carddemo-useradd", "app/cbl/COUSR01C.cbl"),
    "COUSR03C": ("carddemo-userdel", "app/cbl/COUSR03C.cbl"),
    "CSUTLDTC": ("carddemo-dateutil", "app/cbl/CSUTLDTC.cbl"),
    "DBCRFUN": ("cbsa-dbcrfun", "src/base/cobol_src/DBCRFUN.cbl"),
    "INQACC": ("cbsa-inqacc", "src/base/cobol_src/INQACC.cbl"),
    "LGAPVS01": ("genapp-lgapvs01", "base/src/lgapvs01.cbl"),
    "UPDCUST": ("cbsa-updcust", "src/base/cobol_src/UPDCUST.cbl"),
}


@cache
def _engines() -> tuple[Any, Any]:
    sys.path.insert(0, str(REPO_ROOT))
    from gitgalaxy.core.prism import Prism
    from gitgalaxy.standards.gitgalaxy_config import LEXICAL_FAMILY_HEURISTICS
    from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

    return Prism(LEXICAL_FAMILY_HEURISTICS, LANGUAGE_DEFINITIONS), LANGUAGE_DEFINITIONS


def readings(text: str, lang: str) -> dict[str, int]:
    """The CONTRACT readings of one file's text ('cobol' or 'java'), as a full scan's file_data records them."""
    from gitgalaxy.core.detector import StructuralExtractor

    prism, defs = _engines()
    streams = prism.split_streams(text, lang)
    r = StructuralExtractor(lang, defs).splice(streams["code_stream"], streams.get("comment_stream", ""),
                                               raw_content=text)  # fmt: skip
    eq = r.get("equations", {})
    return {col: (len(r.get("functions", [])) if key == "functions" else int(eq.get(key, 0) or 0))
            for col, (key, _, _) in CONTRACT.items()}  # fmt: skip


def _ranks(xs: list[float]) -> list[float]:
    """Average ranks (ties share the mean of the ranks they span)."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    out = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2
        i = j + 1
    return out


def spearman(a: list[float], b: list[float]) -> float | None:
    """Tie-corrected Spearman rho (Pearson on average ranks); None when either side is constant."""
    ra, rb = _ranks(a), _ranks(b)
    ma, mb = statistics.mean(ra), statistics.mean(rb)
    assert len(ra) == len(rb), "spearman: the two series differ in length"  # (zip(strict=) is 3.10+)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return num / den if den else None


def _read(path: Path) -> str:
    from gitgalaxy.core.source_text import read_source

    return read_source(path).text


def measure(pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each pair ({program, estate, cobol: Path, java: Path}) with both sides' readings."""
    _engines()
    return [{**p, "cobol_r": readings(_read(p["cobol"]), "cobol"), "java_r": readings(_read(p["java"]), "java")}
            for p in pairs]  # fmt: skip


def evaluate(measured: list[dict[str, Any]], floor: str = "full") -> tuple[dict[str, Any], list[str]]:
    """Each reading's rho (all pairs and per estate) and what breaks the contract ('full' or 'fixture' floors)."""
    idx = {"full": 1, "fixture": 2}[floor]
    report: dict[str, Any] = {}
    problems: list[str] = []
    estates = sorted({m["estate"] for m in measured})
    for col, spec in CONTRACT.items():

        def rho(sel: list[dict[str, Any]], c: str = col) -> float | None:
            return spearman([m["cobol_r"][c] for m in sel], [m["java_r"][c] for m in sel])

        overall = rho(measured)
        report[col] = {"rho": overall, "floor": spec[idx],
                       "by_estate": {e: rho([m for m in measured if m["estate"] == e]) for e in estates}}  # fmt: skip
        if overall is None or overall < spec[idx]:
            problems.append(f"{col}: rho {overall if overall is None else round(overall, 3)} < floor {spec[idx]} "
                            f"over {len(measured)} pairs -- the scanner reads COBOL and its port differently")  # fmt: skip
    for m in measured:
        c, j = m["cobol_r"], m["java_r"]
        if j["function_count"] < c["function_count"]:
            problems.append(f"{m['program']}: {j['function_count']} methods < {c['function_count']} paragraphs")
        if (c["arch_io"] > 0) != (j["arch_io"] > 0):
            problems.append(f"{m['program']}: file I/O in one form only (COBOL {c['arch_io']}, Java {j['arch_io']})")
    return report, problems


def fixture_pairs(root: Path = FIXTURE_DIR) -> list[dict[str, Any]]:
    manifest = json.loads((root / "pairs.json").read_text(encoding="utf-8"))
    return [{"program": p["program"], "estate": p["estate"], "cobol": root / p["cobol"], "java": root / p["java"]}
            for p in manifest]  # fmt: skip


def _service(program: str) -> str:
    sys.path.insert(0, str(TOOLS))
    import equivalence_java

    return equivalence_java._service_class(program) + ".java"


def sweep_pairs(work: Path, corpora: Path) -> list[dict[str, Any]]:
    """One pair per (corpus, program) from a det sweep's work dir (det_port.py run --work): the case's COBOL in the
    pinned corpus clone and the service class the sweep emitted (port/service/)."""
    pairs, seen = [], set()
    for case_json in sorted(CASES.glob("*/case.json")):
        case = json.loads(case_json.read_text(encoding="utf-8"))
        if "corpus" not in case or "program_source" not in case:
            continue
        key = (case["corpus"], case["program"].upper())
        java = work / case_json.parent.name / "port" / "service" / _service(case["program"].upper())
        if key in seen or not java.is_file():
            continue
        seen.add(key)
        pairs.append({"program": key[1], "estate": case["corpus"], "case": case_json.parent.name,
                      "cobol": corpora / case["corpus"] / case["program_source"], "java": java})  # fmt: skip
    return pairs


def write_fixture(work: Path, corpora: Path, root: Path = FIXTURE_DIR) -> None:
    """The FIXTURE pairs copied from the pinned corpora and a det sweep's output, with each corpus's licence files."""
    manifest_path = REPO_ROOT / "tests" / "cobol_mainframe" / "corpora.json"
    manifest = {c["name"]: c for c in json.loads(manifest_path.read_text(encoding="utf-8"))["corpora"]}
    by_case = {p["case"]: p for p in sweep_pairs(work, corpora)}
    shutil.rmtree(root, ignore_errors=True)
    rows = []
    for program, (case, rel) in sorted(FIXTURE.items()):
        p = by_case[case]
        estate = p["estate"]
        (root / estate / "cobol").mkdir(parents=True, exist_ok=True)
        (root / estate / "java").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(corpora / estate / rel, root / estate / "cobol" / Path(rel).name)
        shutil.copyfile(p["java"], root / estate / "java" / p["java"].name)
        rows.append({"program": program, "estate": estate, "case": case,
                     "cobol": f"{estate}/cobol/{Path(rel).name}", "java": f"{estate}/java/{p['java'].name}"})  # fmt: skip
    for estate in sorted({r["estate"] for r in rows}):
        for f in (corpora / estate).iterdir():
            if f.is_file() and f.name.upper().startswith(("LICENSE", "NOTICE")):
                shutil.copyfile(f, root / estate / f.name)
        c = manifest[estate]
        names = ", ".join(r["program"] for r in rows if r["estate"] == estate)
        (root / estate / "SOURCE.md").write_text(
            f"# {estate} (port-invariance pairs)\n\n"
            f"cobol/: {names} from <{c['url']}> at `{c['ref']}`, unmodified, under that project's license "
            f"({c['license']}; licence files copied alongside).\n\n"
            "java/: each program's deterministic Java port (service class), emitted by GitGalaxy's det-port "
            "translator (`tests/tools/det_port.py run`) from that source and proven equivalent to it.\n\n"
            "Regenerate with `python tests/tools/port_invariance.py fixture --work <det sweep work dir>`.\n",
            encoding="utf-8",
        )
    (root / "pairs.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")


_SHORT = {
    "aws-mainframe-modernization-carddemo": "carddemo",
    "cics-banking-sample-application-cbsa": "cbsa",
    "cics-genapp": "genapp",
}


def _print(report: dict[str, Any], problems: list[str], n: int) -> None:
    for col, r in report.items():
        est = "  ".join(f"{_SHORT.get(e, e)} {'-' if v is None else f'{v:.2f}'}" for e, v in r["by_estate"].items())
        rho = "-" if r["rho"] is None else f"{r['rho']:.3f}"
        print(f"{col:16} rho {rho}  (floor {r['floor']})   {est}")
    print(f"{n} pairs: " + ("contract holds" if not problems else f"{len(problems)} problem(s)"))
    for p in problems:
        print("  " + p)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "fixture"):
        s = sub.add_parser(name)
        s.add_argument("--work", type=Path, help="a det sweep's work dir (det_port.py run --work)")
        s.add_argument("--corpora", type=Path, help="mainframe corpora cache (default: $GITGALAXY_MAINFRAME_CORPORA)")
    args = ap.parse_args()
    sys.path.insert(0, str(TOOLS))
    import mainframe_corpus

    corpora = args.corpora or mainframe_corpus.cache_root()
    if args.cmd == "fixture":
        write_fixture(args.work, corpora)
        print(f"wrote {FIXTURE_DIR}")
        return 0
    pairs = sweep_pairs(args.work, corpora) if args.work else fixture_pairs()
    measured = measure(pairs)
    report, problems = evaluate(measured, "full" if args.work else "fixture")
    _print(report, problems, len(measured))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
