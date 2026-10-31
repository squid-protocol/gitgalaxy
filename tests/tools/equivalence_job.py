"""A multi-step job as an equivalence case (#4268): `"kind": "job"`, `"steps"` = batch cases run in order, a step's
`"feeds"` naming the datasets it reads from an earlier step's output.

    {"kind": "job", "job": "TRANREPT",
     "steps": [{"case": "sort-step"},
               {"case": "report-step", "feeds": {"TRANFILE": {"step": "sort-step", "dd": "SORTOUT"}}}]}

Each step is proven like a batch case on its own (COBOL under GnuCOBOL, then the port, every compared output and the
RETURN-CODE), and what a step reads from an earlier step is the COBOL side's output of that step, the very bytes the
Java side is given too. If every step's Java output equals its COBOL output, the Java job's chain equals the COBOL
job's chain; that composition is the claim, nothing about a step that a standalone proof does not already make.

A step that abends has no output to feed: the job stops there and is not proven (what an abended step leaves in its
datasets is not defined, equivalence.compare_run). Refused by name: a Db2 / IMS / CICS / call step, an indexed (VSAM)
fed dataset, a feed from a step that is not earlier or a dataset that step does not compare, record lengths that
differ across a feed, a fault run on a step (a fault plan names one step's datasets; not modelled in the job).
The oracle is GnuCOBOL plus our stub, not z/OS; the JCL that wires the steps is the case's `feeds`, not a read job.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any


class Unsupported(Exception):
    """The job asks for what this harness does not model: named, never guessed."""


def step_names(job: dict[str, Any]) -> list[str]:
    return [s["case"] for s in job.get("steps", [])]


def check_job(job: dict[str, Any], cases: dict[str, dict[str, Any]]) -> None:
    """Refuse a job the chain cannot be proven for. `cases` is each step case by name, as `load_case` returns it."""
    steps = job.get("steps") or []
    names = step_names(job)
    if len(steps) < 2:
        raise Unsupported("a job case needs at least two steps (a one-step job is the step's own case)")
    if len(set(names)) != len(names):
        raise Unsupported(f"a step case appears twice ({sorted({n for n in names if names.count(n) > 1})}): "
                          "a feed names its source step by case")  # fmt: skip
    for i, step in enumerate(steps):
        name = step["case"]
        case = cases.get(name)
        if case is None:
            raise Unsupported(f"step {i + 1}: no case {name!r}")
        what = case.get("kind") or ("db2" if "db2" in case else "ims" if "ims" in case else "batch")
        if what != "batch":
            raise Unsupported(f"step {name}: a {what} step is not modelled in a job case (batch steps only)")
        for dd, feed in step.get("feeds", {}).items():
            _check_feed(name, dd, feed, case, names[:i], cases)
    unknown = {k for s in steps for k in s} - {"case", "feeds"}
    if unknown:
        raise Unsupported(f"unknown step key(s) {sorted(unknown)}")


def _check_feed(name: str, dd: str, feed: dict[str, Any], case: dict[str, Any], earlier: list[str],
                cases: dict[str, dict[str, Any]]) -> None:  # fmt: skip
    src = feed.get("step")
    if src not in earlier:
        raise Unsupported(f"step {name}: feed {dd} comes from {src!r}, which is not an earlier step")
    spec = case["datasets"].get(dd)
    if spec is None:
        raise Unsupported(f"step {name}: feed {dd} is not one of its datasets")
    out = cases[src]["datasets"].get(feed.get("dd"))
    if out is None or not out.get("compare"):
        raise Unsupported(f"step {name}: feed {dd} reads {src}.{feed.get('dd')}, which that step does not compare")
    if "indexed" in (spec.get("organization"), out.get("organization")):
        raise Unsupported(f"step {name}: feed {dd} is an indexed (VSAM) dataset; only sequential feeds are modelled")
    if spec["reclen"] != out["reclen"]:
        raise Unsupported(f"step {name}: feed {dd} has record length {spec['reclen']}, {src}.{feed['dd']} "
                          f"writes {out['reclen']}")  # fmt: skip


def records_as_lines(data: bytes, reclen: int, enc: str) -> bytes:
    """A step's fixed-length output as the text lines a dataset `input` is read from (`equivalence_common._fixed`
    pads each line back to the record length, so a record that ends in spaces survives)."""
    nl = "\n".encode(enc)
    if len(data) % reclen:
        raise Unsupported(f"an output of {len(data)} bytes is not whole records of {reclen}")
    return b"".join(data[i : i + reclen] + nl for i in range(0, len(data), reclen))


def run_case(api: Any, job: dict[str, Any], work: Path, port: bool = True, cobol_only: bool = False) -> int:
    """Prove the job. `api` is the `equivalence` module (its run_cobol, compare_run, load_case, ... -- passed in so
    the script run as __main__ and this module share one set of globals)."""
    import equivalence_java as ej
    import mainframe_corpus as mc

    cases = {n: api.load_case(n) for n in step_names(job)}
    try:
        check_job(job, cases)
    except Unsupported as e:
        raise SystemExit(f"{job['name']}: not runnable faithfully: {e}") from e
    api.build_image()
    report: dict[str, Any] = {"case": job["name"], "kind": "job", "job": job.get("job"), "steps": [],
                              "java": "ported" if port else "generated"}  # fmt: skip
    outputs: dict[str, dict[str, bytes]] = {}  # step case -> {dd: COBOL output bytes}
    ok = True
    for i, step in enumerate(job["steps"]):
        name = step["case"]
        case = cases[name]
        enc = api.data_encoding(case)
        fed = {}
        for dd, feed in step.get("feeds", {}).items():
            src = outputs.get(feed["step"], {}).get(feed["dd"])
            if src is None:
                report["steps"].append({"case": name, "ok": False, "stopped": f"{feed['step']} left no {feed['dd']}"})
                ok = False
                break
            path = work / "feeds" / f"{i + 1}-{name}-{dd}.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(records_as_lines(src, case["datasets"][dd]["reclen"], enc))
            case["datasets"][dd] = {**case["datasets"][dd], "input": str(path.resolve())}
            fed[dd] = f"{feed['step']}.{feed['dd']} ({len(src) // case['datasets'][dd]['reclen']} records)"
        else:
            (entry,) = mc.select([case["corpus"]])
            corpus = mc.require_clone(entry)
            sw = work / f"step{i + 1}-{name}"
            cobol = api.run_cobol(case, corpus, sw / "cobol")
            outputs[name] = cobol
            if cobol_only:
                report["steps"].append({"case": name, "ok": True, "cobol_only": True, "fed": fed})
                continue
            runs = ej.run_java_environments(case, corpus, sw / "java", sw / "cobol", [ej.environment("default")],
                                            port=port)  # fmt: skip
            run = api.compare_run(case, corpus, cobol, runs["default"])
            report["steps"].append({"case": name, "program": case["program"], "fed": fed, "ok": run["ok"],
                                    "return_code": run["return_code"], "abend": run["abend"],
                                    "outputs": run["outputs"]})  # fmt: skip
            ok &= run["ok"]
            if "ABEND" in cobol and i + 1 < len(job["steps"]):
                report["steps"][-1]["stopped"] = "the step abended: its datasets are not defined, the job stops"
                ok = False
                break
            continue
        break  # a feed had no source
    report["proven"] = ok and not cobol_only and len(report["steps"]) == len(job["steps"])
    (work / "report.json").write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    for s in report["steps"]:
        outs = ", ".join(f"{dd} {d['equal']}/{d['records']}" for dd, d in s.get("outputs", {}).items())
        print(f"{job['name']} step {s['case']}: {'equal' if s['ok'] else 'DIFFERS'}"
              + (f" ({outs})" if outs else "") + (f" -- {s['stopped']}" if s.get("stopped") else ""))  # fmt: skip
    print(f"{job['name']}: {'proven' if report['proven'] else 'NOT proven'} over {len(job['steps'])} steps")
    print(f"report: {work / 'report.json'}")
    return 0 if report["proven"] or cobol_only else 1


def work_dir(keep: Path | None, name: str) -> Path:
    return keep or Path(tempfile.mkdtemp(prefix=f"equiv_{name}_"))
