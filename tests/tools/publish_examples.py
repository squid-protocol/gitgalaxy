#!/usr/bin/env python3
"""
Regenerate the cobol_to_java_examples repository (#3624) from the pinned, answer-keyed
mainframe corpora, deterministically, so every refresh is a reviewable PR there.

    python tests/tools/publish_examples.py <examples checkout> [--only SLUG ...]
                                           [--equivalence DIR] [--work DIR]

Per corpus (EXAMPLES), `examples/<slug>/`:
  java/               the refractor + cobol-to-java output (default target config), run
                      timestamps blanked, no build output: the Spring project with its
                      traceability.json, migration_worklist.{json,md}, audit and tickets
  PROVENANCE.md       the corpus (URL, pinned commit, licence), the GitGalaxy commit and
                      the exact commands -- enough to reproduce the tree byte for byte
  scan_comparison.md  GitGalaxy's scan of the source estate next to its scan of the
                      generated Java (the same engine, the same metrics)
Plus `equivalence/<case>/` for each equivalence case (tests/equivalence): the reports of
the ported and the as-generated runs (tests/tools/equivalence.py), the port, the case, and
how to reproduce -- the harness runs unless --equivalence gives a directory of finished
runs (`<case>/ported/report.md`, `<case>/generated/report.md`). And the top README, whose
numbers all come from the generated trees, and a compile workflow.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import java_target_matrix as jtm  # noqa: E402
import mainframe_corpus as mc  # noqa: E402

EXAMPLES = [  # (slug, corpus, what it shows)
    ("carddemo", "aws-mainframe-modernization-carddemo",
     "AWS CardDemo: CICS online (BMS screens, COMMAREA), VSAM, DB2, IMS, MQ and a JCL batch cycle"),
    ("cbsa", "cics-banking-sample-application-cbsa",
     "IBM CICS Bank Sample Application: CICS / DB2 online banking and its DB2 install JCL"),
    ("genapp", "cics-genapp", "IBM CICS GenApp: the general insurance application (CICS, DB2, VSAM)"),
    ("zecs", "zecs", "Walmart zECS: an assembler + COBOL CICS key/value service"),
    ("zopeneditor", "zopeneditor-sample", "IBM Z Open Editor sample: batch COBOL and PL/I with JCL"),
    ("dsf-pli", "dsf", "NAV DSF: the Norwegian pension system, 431 PL/I programs under CICS / IMS"),
]  # fmt: skip
CODE_LANGUAGES = ("cobol", "pli", "hlasm", "rexx")
GITHUB = "https://github.com/squid-protocol/gitgalaxy"
CHECKOUT = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1"
SETUP_JAVA = "actions/setup-java@de7274f081f381c8f8158605e0321c36c376e2e6  # v6.0.1"


def _git_head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True,  # noqa: S603,S607
                          check=True).stdout.strip()  # fmt: skip


# ---- the scan comparison -------------------------------------------------------------
def scan_metrics(db: Path, languages: tuple[str, ...]) -> dict[str, Any]:
    """Code metrics of the files in `languages` from a GitGalaxy master DB."""
    c = sqlite3.connect(db)
    marks = ",".join("?" * len(languages))

    def one(sql: str) -> Any:
        return c.execute(sql.replace("LANGS", marks), languages).fetchone()

    files, loc, code = one("SELECT count(*), sum(total_loc), sum(coding_loc) FROM file_data WHERE language IN (LANGS)")
    fn = one("SELECT count(*), avg(f.complexity), max(f.complexity), avg(f.loc), sum(f.complexity > 10) "
             "FROM function_data f JOIN file_data d ON d.id = f.file_id WHERE d.language IN (LANGS)")  # fmt: skip
    risks = {k: one(f"SELECT avg({k}) FROM file_data WHERE language IN (LANGS)")[0]  # noqa: S608 -- k is a constant
             for k in ("risk_cognitive_load", "risk_tech_debt", "risk_safety_score", "risk_verification",
                       "risk_documentation", "risk_api_exposure", "risk_state_flux")}  # fmt: skip
    langs = dict(c.execute("SELECT language, count(*) FROM file_data GROUP BY language ORDER BY 2 DESC").fetchall())
    return {"files": files or 0, "total_loc": loc or 0, "coding_loc": code or 0, "functions": fn[0] or 0,
            "avg_complexity": round(fn[1] or 0, 2), "max_complexity": fn[2] or 0, "avg_function_loc": round(fn[3] or 0, 1),
            "functions_complexity_over_10": fn[4] or 0, **{k: round(v or 0, 1) for k, v in risks.items()},
            "languages": langs}  # fmt: skip


_ROWS = [
    ("files", "Source files"), ("total_loc", "Total lines"), ("coding_loc", "Code lines"),
    ("functions", "Functions (paragraphs / methods)"), ("avg_complexity", "Mean function complexity"),
    ("max_complexity", "Max function complexity"), ("avg_function_loc", "Mean function length (lines)"),
    ("functions_complexity_over_10", "Functions with complexity > 10"),
    ("risk_cognitive_load", "Cognitive-load exposure (mean, 0-100)"), ("risk_tech_debt", "Tech-debt exposure"),
    ("risk_safety_score", "Safety exposure"), ("risk_verification", "Verification exposure"),
    ("risk_documentation", "Documentation exposure"), ("risk_api_exposure", "API-exposure"),
    ("risk_state_flux", "State-flux exposure"),
]  # fmt: skip


def comparison_markdown(title: str, src: dict[str, Any], java: dict[str, Any], src_langs: tuple[str, ...]) -> str:
    sides = (
        f"Both trees scanned by the same GitGalaxy engine. Source side: the program code "
        f"({', '.join(src_langs)}); Java side: every generated `.java` file."
    )
    lines = [f"# {title}: GitGalaxy scan, source vs generated Java", "", sides, "",
             "| metric | source | generated Java |", "|---|---|---|"]  # fmt: skip
    lines += [f"| {label} | {src[k]} | {java[k]} |" for k, label in _ROWS]
    how_to_read = (
        "How to read it: the generated Java is the estate's STRUCTURE -- entities, DTOs, services, "
        "endpoints, batch jobs, wiring -- with each program's PROCEDURE DIVISION left as a traced TODO "
        "(migration_worklist.md). So its functions are small and simple, and its tech-debt exposure "
        "counts those TODO markers; the business logic moves over per program (see ../../equivalence)."
    )
    languages = ", ".join(f"{k} {v}" for k, v in src["languages"].items())
    lines += ["", f"Source estate by language: {languages}.", "", how_to_read, ""]
    return "\n".join(lines)


# ---- one example ---------------------------------------------------------------------
def example_summary(java: Path) -> dict[str, Any]:
    """Counts the README shows, from the generated tree itself."""
    src = java / "src/main/java/com/gitgalaxy/modernized"
    count = lambda sub: len(list((src / sub).rglob("*.java"))) if (src / sub).is_dir() else 0  # noqa: E731
    jobs_file = java / "src/main/resources/batch/jcl-jobs.json"
    jobs = Counter(j["kind"] for j in json.loads(jobs_file.read_text())) if jobs_file.is_file() else Counter()
    wl = java / "migration_worklist.json"
    work = Counter(i["category"] for i in json.loads(wl.read_text()).get("items", [])) if wl.is_file() else Counter()
    trace = java / "traceability.json"
    artifacts = len(json.loads(trace.read_text()).get("artifacts", [])) if trace.is_file() else 0
    return {"java_files": len(list(src.rglob("*.java"))), "services": count("service"),
            "controllers": count("controller"), "entities": count("entity"), "dtos": count("dto"),
            "batch_jobs": dict(jobs), "worklist": dict(work), "traced_artifacts": artifacts}  # fmt: skip


def legal_files(repo: Path) -> list[Path]:
    """A source's licence and notice files (LICENSE*, NOTICE*, COPYING*): mainframe_corpus.excerpt's rule."""
    return sorted(
        p for p in repo.iterdir() if p.is_file() and p.name.upper().startswith(("LICENSE", "NOTICE", "COPYING"))
    )


def file_header(entry: dict[str, Any]) -> str:
    """The notice every generated Java file of an example starts with (Apache-2.0 4(b), EPL-2.0 3)."""
    return (
        f"Generated by GitGalaxy ({GITHUB}) from\n"
        f"{entry['url']} at commit {entry['ref']},\n"
        f"which is licensed {entry['license']}. This file is derived from that source and was modified in\n"
        "generation; the source's licence terms apply to it (see the LICENSE / NOTICE files and\n"
        "PROVENANCE.md at the root of this example).\n"
    )


def build_example(slug: str, corpus_name: str, what: str, out: Path, work: Path, head: str) -> dict[str, Any]:
    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import scan_to_db

    (entry,) = mc.select([corpus_name])
    corpus = mc.require_clone(entry)
    ex_work = work / slug
    clean = jtm.refactor(corpus, ex_work, scan=True)
    header = ex_work / "header.txt"
    header.write_text(file_header(entry), encoding="utf-8")
    project = jtm.generate(clean, "default", {}, ex_work, header=header)
    jtm.normalize(project)
    dest = out / "examples" / slug
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(project, dest / "java", ignore=shutil.ignore_patterns("target", ".git"))
    legal = legal_files(corpus)
    for f in legal:  # the source's own licence and notices travel with what is derived from it
        shutil.copy(f, dest / f.name)
    src_db = scan_to_db(corpus, ex_work / "scan_src")
    # the generated tree where it was written: inside the examples checkout its files are untracked,
    # and the scanner enumerates a git work tree's files through git
    java_db = scan_to_db(project, ex_work / "scan_java")
    langs = tuple(lang for lang in CODE_LANGUAGES if lang in entry.get("languages", []))
    src_m, java_m = scan_metrics(src_db, langs), scan_metrics(java_db, ("java",))
    (dest / "scan_comparison.md").write_text(comparison_markdown(slug, src_m, java_m, langs), encoding="utf-8")
    (dest / "PROVENANCE.md").write_text(f"""# {slug}: provenance

- **Source:** [{entry['url']}]({entry['url']}) at commit `{entry['ref']}` ({what}).
- **Source licence:** {entry['license']}. This directory is derived from that source (its names, literals and
  source references carry over), so the source's licence terms apply to it. The source's own licence and
  notice files are copied here unchanged ({', '.join(f.name for f in legal) or 'none shipped'}), and every
  generated Java file opens with a notice naming the source, its commit and licence, and that it was
  modified in generation.
- **Generator:** [GitGalaxy]({GITHUB}) at commit [`{head[:12]}`]({GITHUB}/commit/{head}).
- **Commands** (from a GitGalaxy checkout at that commit, the corpus at that ref):

  ```
  python tests/tools/mainframe_corpus.py fetch {corpus_name}
  python tests/tools/publish_examples.py <this repository> --only {slug}
  ```

  which runs `cobol-refractor <corpus> --scan`, then `cobol-to-java <clean room>` with the default
  target config (Spring Boot 3.2, Java 17, Lombok, Maven), and blanks the run's timestamps.
- **Compiles:** the repository's `compile` workflow builds `java/` on every push; GitGalaxy's own
  `java-compile` CI builds this corpus in 17 target configurations.
""", encoding="utf-8")  # fmt: skip
    return {"slug": slug, "corpus": entry, "what": what, "metrics": {"source": src_m, "java": java_m},
            "legal": [f.name for f in legal], **example_summary(dest / "java")}  # fmt: skip


# ---- equivalence ---------------------------------------------------------------------
def build_equivalence(out: Path, work: Path, finished: Optional[Path]) -> list[dict[str, Any]]:
    import equivalence as eq

    results = []
    for case_file in sorted(eq.CASES.glob("*/case.json")):
        name = case_file.parent.name
        case = eq.load_case(name)
        dest = out / "equivalence" / name
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)
        runs = {}
        for mode in ("ported", "generated"):
            run_dir = finished / name / mode if finished else work / "equivalence" / name / mode
            if not finished:
                cmd = [sys.executable, str(Path(eq.__file__)), "run", name, "--keep", str(run_dir)]
                subprocess.run(cmd + (["--generated-only"] if mode == "generated" else []), check=False)  # noqa: S603
            shutil.copy(run_dir / "report.md", dest / f"report_{mode}.md")
            runs[mode] = json.loads((run_dir / "report.json").read_text())
        shutil.copytree(case_file.parent / "port", dest / "port")
        shutil.copy(case_file, dest / "case.json")
        for extra in case_file.parent.iterdir():  # the case data and the source's LICENSE / NOTICE files
            if extra.is_file() and extra.name != "case.json":
                shutil.copy(extra, dest / extra.name)
        tally = {m: (sum(o["equal"] for o in r["outputs"].values()), sum(o["records"] for o in r["outputs"].values()))
                 for m, r in runs.items()}  # fmt: skip
        (dest / "README.md").write_text(f"""# {case['program']}: COBOL vs Java, record by record

`{case['program_source']}` from [{case['corpus']}]({mc.select([case['corpus']])[0]['url']}), run as
job {case.get('job')} step {case.get('step')} (`PARM='{case.get('parm')}'`), on the same inputs as COBOL under
GnuCOBOL and as the generated Java, every output record diffed field by field, decimals exact.

| Java side | records equal |
|---|---|
| as generated (the stub) | {tally['generated'][0]} / {tally['generated'][1]} |
| generated + the hand port in `port/` | **{tally['ported'][0]} / {tally['ported'][1]}** |

- `report_ported.md`, `report_generated.md`: the two runs, every differing field.
- `port/`: the ported service (it replaces the generated one); each block names the COBOL paragraph it ports.
- `case.json`: the program, its datasets (keys, copybooks), PARM and pinned clock. {case.get('notes', '')}

Reproduce, from a GitGalaxy checkout (Docker and a JDK 17 + Maven needed):

```
python tests/tools/mainframe_corpus.py fetch {case['corpus']}
python tests/tools/equivalence.py run {name}                    # the port
python tests/tools/equivalence.py run {name} --generated-only   # the stub
```
""", encoding="utf-8")  # fmt: skip
        results.append({"name": name, "program": case["program"], "corpus": case["corpus"], "tally": tally,
                        "legal": sorted(f.name for f in case_file.parent.iterdir() if f.name.upper().startswith(
                            ("LICENSE", "NOTICE")))})  # fmt: skip
    return results


# ---- the repository ------------------------------------------------------------------
def readme(examples: list[dict[str, Any]], equivalence: list[dict[str, Any]], head: str) -> str:
    rows = []
    for e in examples:
        jobs = e["batch_jobs"]
        rows.append(f"| [{e['slug']}](examples/{e['slug']}) | {e['what']} | {e['java_files']} | {e['services']} | "
                    f"{e['entities']} | {e['dtos']} | {jobs.get('application', 0)} / {sum(jobs.values())} | "
                    f"{sum(e['worklist'].values())} | [scan](examples/{e['slug']}/scan_comparison.md) |")  # fmt: skip
    eq_rows = [f"| [{r['program']}](equivalence/{r['name']}) | {r['corpus']} | {r['tally']['generated'][0]} / "
               f"{r['tally']['generated'][1]} | **{r['tally']['ported'][0]} / {r['tally']['ported'][1]}** |"
               for r in equivalence]  # fmt: skip
    return f"""# COBOL to Java: GitGalaxy examples

Six real mainframe estates, taken through [GitGalaxy]({GITHUB})'s COBOL-to-Java pipeline, unedited. Each
compiles (the `compile` workflow builds every one on each push), and each is regenerated by a script
from a pinned source commit, so a refresh arrives as a pull request whose diff is exactly what a
pipeline change did.

## What the pipeline produces, and what it does not

**Generated from verified facts.** GitGalaxy scans the estate and extracts its facts: programs, calls,
CICS resources, COMMAREA and record layouts, VSAM keys, DB2 tables, JCL job flow, and more. Each fact
channel is checked against hand-verified answer keys on these same corpora, including blind-reviewer
censuses, and its field-testing status is published
([fact-channel status]({GITHUB}/blob/main/docs/language_status/cics_field_testing.md)). From those
facts it builds the **structure** of a Spring Boot application:
- JPA entities for VSAM files, with record codecs;
- DTOs for COMMAREAs, containers and screens;
- REST endpoints for transactions and LINKs;
- services wired to each other;
- repositories for VSAM and DB2;
- Spring Batch jobs for the JCL;
- messaging for TS/TD queues and MQ.

Every generated class, method and field is traced back to the source line and fact it came from
(`traceability.json`).

**Not generated: business logic.** Each program's PROCEDURE DIVISION is a traced TODO. Those TODOs,
with everything else left to a person, are sorted in `migration_worklist.md`. Porting the logic is
per-program work, and the equivalence harness below is how it is proven.

## The examples

| example | estate | Java files | services | entities | DTOs | batch jobs generated / JCL jobs | worklist items | GitGalaxy |
|---|---|---|---|---|---|---|---|---|
{chr(10).join(rows)}

Each `examples/<name>/` has:
- `java/`: the Spring project, as generated;
- `PROVENANCE.md`: source commit, licence, generator commit, commands;
- `scan_comparison.md`: the source estate and the Java, scanned by the same engine.

## Behavioural equivalence

The structure is necessary but not sufficient, so the ported logic is proven. The original program
runs under GnuCOBOL, the Java runs on the same inputs, and every output record is diffed field by
field, decimals exact.

| program | estate | as generated | generated + port |
|---|---|---|---|
{chr(10).join(eq_rows)}

CardDemo's CBACT04C (the interest calculator) matches on every record. The harness also found a defect
in the original: the last account's interest is never added to its balance, because the loop's
end-of-file branch is unreachable. The port keeps that behaviour, documented at the spot; fixing it is
a business decision, not a translation one.

## Licences and provenance

Each example is derived from its source and is under that source's licence. The source's LICENSE and
NOTICE files are included beside it, every generated file opens with a notice, and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) lists them all. The repository's own files are
Apache-2.0 ([LICENSE](LICENSE)).

{TRADEMARKS}

Generated by GitGalaxy commit [`{head[:12]}`]({GITHUB}/commit/{head}) with
`tests/tools/publish_examples.py`.
"""


TRADEMARKS = (
    "IBM, CICS, DB2, IMS and z/OS are trademarks of International Business Machines Corporation; AWS and "
    "Amazon Web Services are trademarks of Amazon.com, Inc. or its affiliates; Walmart is a trademark of "
    "Walmart Apps, LLC; NAV is the Norwegian Labour and Welfare Administration. Their names are used only "
    "to identify the source code these examples are derived from. This repository is not affiliated with, "
    "sponsored or endorsed by any of them."
)


def third_party_notices(examples: list[dict[str, Any]], equivalence: list[dict[str, Any]]) -> str:
    """What each directory is licensed under, and why."""
    rows = [f"| `examples/{e['slug']}/` | [{e['corpus']['name']}]({e['corpus']['url']}) at `{e['corpus']['ref'][:12]}` | "
            f"{e['corpus']['license']} | {', '.join(e.get('legal', [])) or '-'} |" for e in examples]  # fmt: skip
    for r in equivalence:
        (entry,) = mc.select([r["corpus"]])
        rows.append(f"| `equivalence/{r['name']}/` | [{entry['name']}]({entry['url']}) at `{entry['ref'][:12]}` | "
                    f"{entry['license']} | {', '.join(r.get('legal', [])) or '-'} |")  # fmt: skip
    return f"""# Third-party notices

This repository holds output GENERATED FROM third-party source code. Each directory below is derived from
the source named (its identifiers, literals, record layouts and source references carry over, and the
generator modified and reorganised it), so **the source's licence applies to that directory**. The
source's own licence and notice files are copied into the directory unchanged, every generated Java file
opens with a notice naming its source, commit and licence, and each example's `PROVENANCE.md` records
exactly how it was produced.

| directory | derived from | licence | licence / notice files included |
|---|---|---|---|
{chr(10).join(rows)}

The equivalence case's `port/` is a hand translation of the source program and its data file is the
source's data with changed balances: both are derived from that source too.

Everything else in this repository -- `README.md`, this file, `.github/` and `.publish/` -- is licensed
under the Apache License 2.0 (`LICENSE`).

## Trademarks

{TRADEMARKS}
"""


def compile_workflow(slugs: list[str]) -> str:
    return f"""name: compile

# Every example's generated Spring project must compile (JDK 17, Maven).
on:
  push:
  pull_request:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  compile:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        example: [{", ".join(slugs)}]
    steps:
      - uses: {CHECKOUT}
      - uses: {SETUP_JAVA}
        with:
          distribution: temurin
          java-version: "17"
          cache: maven
      - name: mvn compile
        working-directory: examples/${{{{ matrix.example }}}}/java
        run: mvn -B -q compile
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path, help="a checkout of cobol_to_java_examples")
    ap.add_argument("--only", nargs="*", help="example slugs to regenerate (default: all)")
    ap.add_argument("--equivalence", type=Path, help="finished equivalence runs to publish instead of running")
    ap.add_argument("--work", type=Path, help="work directory (default: a temporary one)")
    args = ap.parse_args()
    head = _git_head()
    work = args.work or Path(tempfile.mkdtemp(prefix="publish_examples_"))
    chosen = [e for e in EXAMPLES if not args.only or e[0] in args.only]
    examples = [build_example(slug, corpus, what, args.out, work, head) for slug, corpus, what in chosen]
    (args.out / ".publish").mkdir(exist_ok=True)
    for e in examples:  # the README reads every example's summary, including ones not rebuilt this run
        (args.out / ".publish" / f"{e['slug']}.json").write_text(json.dumps(e, indent=2, default=str) + "\n")
    summaries = [json.loads((args.out / ".publish" / f"{s}.json").read_text())
                 for s, _, _ in EXAMPLES if (args.out / ".publish" / f"{s}.json").is_file()]  # fmt: skip
    equivalence = build_equivalence(args.out, work, args.equivalence)
    (args.out / "README.md").write_text(readme(summaries, equivalence, head), encoding="utf-8")
    (args.out / "THIRD_PARTY_NOTICES.md").write_text(third_party_notices(summaries, equivalence), encoding="utf-8")
    apache = REPO_ROOT / "tests" / "equivalence" / "APACHE-2.0.txt"  # the plain licence text, no holder named
    shutil.copy(apache, args.out / "LICENSE")
    wf = args.out / ".github" / "workflows" / "compile.yml"
    wf.parent.mkdir(parents=True, exist_ok=True)
    wf.write_text(compile_workflow([s["slug"] for s in summaries]), encoding="utf-8")
    (args.out / ".gitignore").write_text("target/\n*.class\n", encoding="utf-8")
    print(f"published {len(examples)} examples and {len(equivalence)} equivalence cases into {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
