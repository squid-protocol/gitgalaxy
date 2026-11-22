"""A multi-step job as an equivalence case (#4268): `"kind": "job"`, `"steps"` = batch cases run in order, a step's
`"feeds"` naming the datasets it reads from an earlier step's output, `"inputs"` {DD: file beside the job case} replacing a
dataset's input (the parameter card the job's JCL shares between steps).

    {"kind": "job", "job": "TRANREPT",
     "steps": [{"case": "sort-step"},
               {"case": "report-step", "feeds": {"TRANFILE": {"step": "sort-step", "dd": "SORTOUT"}}}]}

Each step is proven like a batch case on its own (COBOL under GnuCOBOL, then the port, every compared output and the
RETURN-CODE), and what a step reads from an earlier step is the COBOL side's output of that step, the very bytes the
Java side is given too. If every step's Java output equals its COBOL output, the Java job's chain equals the COBOL
job's chain; that composition is the claim, nothing about a step that a standalone proof does not already make.

A step that abends has no output to feed: the job stops there and is not proven (what an abended step leaves in its
datasets is not defined, equivalence.compare_run).

An INDEXED (VSAM-style) dataset may be fed (#8879), including one the earlier step opens I-O (a KSDS it reads and
REWRITEs): what is fed is the earlier step's COBOL-side unload (`ul<DD>`, primary-key order), staged as the same
fixed-length lines and loaded, keyed as the next step's SELECT declares (`keys`), into both sides. Same composition
claim as a sequential feed. A step may be a batch case with `subprograms` (#8884: a static CALL of a COBOL program in
its estate, as CBSTM03A CALLs CBSTM03B): the harness hands the whole case to both sides, so each compiles / translates
the subprograms exactly as the step's own proof does. Refused by name: a Db2 / IMS / CICS / `kind: call` step, a feed between an indexed and a sequential
dataset, indexed feeds whose keys or record lengths differ, a feed from a step that is not earlier or a dataset that
step does not compare, record lengths that differ across a feed, a fault run on a step (a fault plan names one step's
datasets; not modelled in the job). A step that abended feeds nothing (the job stops). An `inputs` value beginning
`@corpus/` names a file in the step's corpus (CardDemo's shipped data) instead of one beside the job case.
A step may be an IDCAMS step (#8884, `"idcams": {"deck": file beside the job case, "dds": {DD: dataset spec}}`): there is no
COBOL to run, so the oracle is the model of the step (`det/idcams_model.py`, no GnuCOBOL IDCAMS exists), run on the
datasets fed to it; a DD carrying `"cluster": NAME` is a cluster the step starts with (empty), a later step reads its
records (key order for a KSDS) as any other output. The Java runtime of the step is not compared yet (#8881), so a job
with an IDCAMS step reports `model_only` for it and is never `proven`. A model refusal, or a nonzero condition code (the
JCL's COND=(0,NE) bypasses the later steps), stops the job. Refused by name: GDG, `inputs`, a subprogram on such a step.
The oracle is GnuCOBOL plus our stub, not z/OS; the JCL that wires the steps is the case's `feeds`, not a read job.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import equivalence_gdg as gdg
from equivalence_gdg import Unsupported

from gitgalaxy.tools.cobol_to_java.det import idcams_model as idc

JOBS = Path(__file__).resolve().parents[1] / "equivalence" / "jobs"


CORPUS_PREFIX = "@corpus/"


def step_names(job: dict[str, Any]) -> list[str]:
    return [s["case"] for s in job.get("steps", [])]


def load_steps(job: dict[str, Any], load_case: Any) -> dict[str, dict[str, Any]]:
    """Each step's case by name: `load_case(name)` for a batch step, the pseudo case of an IDCAMS step (its DD specs
    as `datasets`, a cluster DD an indexed one compared as an output) so the feed rules read both alike."""
    out = {}
    for step in job.get("steps", []):
        name = step["case"]
        spec = step.get("idcams")
        if spec is None:
            out[name] = load_case(name)
            continue
        dds = spec.get("dds") if isinstance(spec, dict) else None
        if not isinstance(dds, dict) or not dds:
            raise Unsupported(f"step {name}: idcams needs {{'deck': file, 'dds': {{DD: spec}}}}")
        out[name] = {"kind": "idcams", "program": "IDCAMS", "datasets": {
            dd: {"organization": "indexed" if "cluster" in d else "sequential",
                 **{k: v for k, v in d.items() if k in ("reclen", "keys", "compare")},
                 **({"compare": True} if "cluster" in d else {})} for dd, d in dds.items()}}  # fmt: skip
    return out


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
        if "idcams" in step:
            _check_idcams(step, case)
            what = "batch"
        else:
            what = case.get("kind") or ("db2" if "db2" in case else "ims" if "ims" in case else "batch")
        if what != "batch":
            raise Unsupported(f"step {name}: a {what} step is not modelled in a job case (batch steps only)")
        _check_subprograms(name, case)
        for dd, feed in step.get("feeds", {}).items():
            _check_feed(name, dd, feed, case, names[:i], cases)
    for step in steps:  # a dataset the JCL gives the step its own input for (the job's shared parameter card)
        for dd, rel in step.get("inputs", {}).items():
            if dd not in cases[step["case"]]["datasets"] or dd in step.get("feeds", {}):
                raise Unsupported(f"step {step['case']}: input {dd} is not one of its datasets, or is also fed")
            if not rel.startswith(CORPUS_PREFIX) and not (JOBS / rel).is_file():
                raise Unsupported(f"step {step['case']}: input {dd}: no file {rel} beside the job case")
    unknown = {k for s in steps for k in s} - {"case", "feeds", "inputs", "job", "gdg_in", "gdg_out", "idcams"}
    if unknown:
        raise Unsupported(f"unknown step key(s) {sorted(unknown)}")
    gdg.check_gdg(job, cases)  # #8883: generations across the chain
    for base, spec in gdg.check_declarations(job).items():
        for rel in spec.get("generations", []):
            if not (JOBS / rel).is_file():
                raise Unsupported(f"GDG {base}: no generation file {rel} beside the job case")


def _check_idcams(step: dict[str, Any], case: dict[str, Any]) -> None:
    """An IDCAMS step (#8884): a deck file beside the job case, DD specs with a record length, a cluster DD keyed."""
    name, spec = step["case"], step["idcams"]
    if not isinstance(spec.get("deck"), str) or not (JOBS / spec["deck"]).is_file():
        raise Unsupported(f"step {name}: idcams deck {spec.get('deck')!r}: no such file beside the job case")
    for k in ("inputs", "gdg_in", "gdg_out"):
        if step.get(k):
            raise Unsupported(f"step {name}: {k} on an IDCAMS step is not modelled")
    for dd, d in spec["dds"].items():
        if not isinstance(d.get("reclen"), int) or d["reclen"] < 1:
            raise Unsupported(f"step {name}: idcams DD {dd} needs a record length")
        if "cluster" in d and not (d.get("keys") and len(d["keys"]) == 1):
            raise Unsupported(f"step {name}: idcams DD {dd}: a cluster needs one key (offset, length)")
    if not any(d.get("compare") or "cluster" in d for d in case["datasets"].values()):
        raise Unsupported(f"step {name}: an IDCAMS step with no output dataset proves nothing")


def _check_subprograms(name: str, case: dict[str, Any]) -> None:
    """A step's `subprograms` (#8884) are corpus-relative source paths of programs it CALLs, none twice, none the step's own."""
    subs = case.get("subprograms", [])
    if not isinstance(subs, list) or not all(isinstance(r, str) and r for r in subs):
        raise Unsupported(f"step {name}: subprograms must be a list of corpus-relative source paths")
    stems = [Path(r).stem.upper() for r in subs]
    if len(set(stems)) != len(stems):
        raise Unsupported(f"step {name}: a subprogram appears twice ({subs})")
    if str(case.get("program", "")).upper() in stems:
        raise Unsupported(f"step {name}: subprogram {case['program']} is the step's own program")


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
    orgs = (spec.get("organization"), out.get("organization"))
    if "indexed" in orgs:
        if orgs != ("indexed", "indexed"):
            raise Unsupported(f"step {name}: feed {dd} ({orgs[0]}) reads {src}.{feed['dd']} ({orgs[1]}): "
                              "an indexed feed needs an indexed dataset on both sides")  # fmt: skip
        if spec.get("keys") != out.get("keys"):
            raise Unsupported(f"step {name}: feed {dd} is keyed {spec.get('keys')}, {src}.{feed['dd']} "
                              f"is keyed {out.get('keys')}")  # fmt: skip
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

    try:
        cases = load_steps(job, api.load_case)
        check_job(job, cases)
    except Unsupported as e:
        raise SystemExit(f"{job['name']}: not runnable faithfully: {e}") from e
    api.build_image()
    report: dict[str, Any] = {"case": job["name"], "kind": "job", "job": job.get("job"), "steps": [],
                              "java": "ported" if port else "generated"}  # fmt: skip
    outputs: dict[str, dict[str, bytes]] = {}  # step case -> {dd: COBOL output bytes}
    catalog = _catalog(api, job, cases)
    jobs = gdg.job_names(job)
    ok = True
    for i, step in enumerate(job["steps"]):
        name = step["case"]
        case = cases[name]
        if "idcams" in step:
            ok &= _idcams_step(step, outputs, report)
            if not ok:
                break
            continue
        enc = api.data_encoding(case)
        fed = {}
        catalog.begin_step(jobs[i])
        for dd, ref in step.get("gdg_in", {}).items():  # both sides read the same generation bytes (the COBOL side's)
            what, parts = catalog.read(ref["base"], ref["gen"])
            data = b"".join(parts)
            path = work / "feeds" / f"{i + 1}-{name}-{dd}.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(records_as_lines(data, case["datasets"][dd]["reclen"], enc))
            case["datasets"][dd] = {**case["datasets"][dd], "input": str(path.resolve())}
            fed[dd] = f"{what} ({len(data) // case['datasets'][dd]['reclen']} records)"
        for dd, rel in step.get("inputs", {}).items():
            path = rel[len(CORPUS_PREFIX) :] if rel.startswith(CORPUS_PREFIX) else str((JOBS / rel).resolve())
            case["datasets"][dd] = {**case["datasets"][dd], "input": path}
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
            if "ABEND" not in cobol:  # a step that abends catalogues nothing
                for dd, base in step.get("gdg_out", {}).items():
                    fed[f"{dd} (out)"] = catalog.create(base, cobol[dd])
            if cobol_only:
                report["steps"].append({"case": name, "ok": True, "cobol_only": True, "fed": fed})
                continue
            runs = ej.run_java_environments(case, corpus, sw / "java", sw / "cobol", [ej.environment("default")],
                                            port=port)  # fmt: skip
            run = api.compare_run(case, corpus, cobol, runs["default"])
            report["steps"].append({"case": name, "program": case["program"], "fed": fed, "ok": run["ok"],
                                    "return_code": run["return_code"], "abend": run["abend"],
                                    "outputs": run["outputs"],
                                    **({"subprograms": case["subprograms"]} if case.get("subprograms") else {})})  # fmt: skip
            ok &= run["ok"]
            if "ABEND" in cobol and i + 1 < len(job["steps"]):
                report["steps"][-1]["stopped"] = "the step abended: its datasets are not defined, the job stops"
                ok = False
                break
            continue
        break  # a feed had no source
    report["proven"] = (ok and not cobol_only and len(report["steps"]) == len(job["steps"])
                        and not any(s.get("model_only") for s in report["steps"]))  # fmt: skip
    work.mkdir(parents=True, exist_ok=True)
    (work / "report.json").write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    for s in report["steps"]:
        if s.get("model_only"):
            print(f"{job['name']} step {s['case']}: IDCAMS model only, rc {s.get('rc')} (Java not compared)")
            continue
        outs = ", ".join(f"{dd} {d['equal']}/{d['records']}" for dd, d in s.get("outputs", {}).items())
        print(f"{job['name']} step {s['case']}: {'equal' if s['ok'] else 'DIFFERS'}"
              + (f" ({outs})" if outs else "") + (f" -- {s['stopped']}" if s.get("stopped") else ""))  # fmt: skip
    print(f"{job['name']}: {'proven' if report['proven'] else 'NOT proven'} over {len(job['steps'])} steps")
    print(f"report: {work / 'report.json'}")
    return 0 if report["proven"] or cobol_only else 1


def _idcams_step(step: dict[str, Any], outputs: dict[str, dict[str, bytes]],
                 report: dict[str, Any]) -> bool:  # fmt: skip
    """Run an IDCAMS step on the model with what the earlier steps left it. Returns False when the job stops here."""
    name, spec = step["case"], step["idcams"]
    entry: dict[str, Any] = {"case": name, "program": "IDCAMS", "ok": False, "model_only": True}
    report["steps"].append(entry)
    catalog: dict[str, Any] = {}
    dds: dict[str, Any] = {}
    fed = {}
    try:
        for dd, d in spec["dds"].items():
            if "cluster" in d:
                key = d["keys"][0]
                catalog[d["cluster"]] = idc.Cluster(
                    d["cluster"], True, key["length"], key["offset"], d["reclen"], d["reclen"]
                )
                dds[dd] = idc.Vsam(d["cluster"])
                continue
            feed = step.get("feeds", {}).get(dd)
            data = b"" if feed is None else outputs.get(feed["step"], {}).get(feed["dd"])
            if data is None:
                entry["stopped"] = f"{feed['step']} left no {feed['dd']}"
                return False
            n = d["reclen"]
            if len(data) % n:
                raise Unsupported(f"an output of {len(data)} bytes is not whole records of {n}")
            dds[dd] = idc.Sequential(n, [data[k : k + n] for k in range(0, len(data), n)], d.get("disp", "OLD"))
            if feed is not None:
                fed[dd] = f"{feed['step']}.{feed['dd']} ({len(data) // n} records)"
        res = idc.run((JOBS / spec["deck"]).read_text(encoding="utf-8"), catalog, dds)
    except (idc.Refused, Unsupported) as e:
        entry["stopped"] = f"the IDCAMS model refuses: {e}"
        return False
    entry.update(fed=fed, rc=res.rc, log=res.log)
    outputs[name] = {}
    for dd, d in spec["dds"].items():
        recs = res.catalog[d["cluster"]].records if "cluster" in d else res.datasets[dd].records
        outputs[name][dd] = b"".join(recs)
    if res.rc:  # COND=(0,NE) on the next step: it is bypassed, the job's chain stops
        entry["stopped"] = f"IDCAMS ended with condition code {res.rc}"
        return False
    entry["ok"] = True
    return True


def _catalog(api: Any, job: dict[str, Any], cases: dict[str, dict[str, Any]]) -> gdg.Catalog:
    """The job's GDG catalog, its declared generations read from files beside the job case as the consuming steps
    read a dataset (one data page for every step that touches a base)."""
    import equivalence_common as common

    gdgs = gdg.check_declarations(job)
    encs = {api.data_encoding(cases[s["case"]]) for s in job["steps"] if "gdg_in" in s or "gdg_out" in s}
    if len(encs) > 1:
        raise SystemExit(f"{job['name']}: not runnable faithfully: steps that share a GDG use different data pages")
    enc = next(iter(encs), "latin-1")
    loaded = {b: [common._fixed(JOBS / rel, spec["reclen"], enc) for rel in spec.get("generations", [])]
              for b, spec in gdgs.items()}  # fmt: skip
    return gdg.Catalog(gdgs, loaded)


def work_dir(keep: Path | None, name: str) -> Path:
    return keep or Path(tempfile.mkdtemp(prefix=f"equiv_{name}_"))
