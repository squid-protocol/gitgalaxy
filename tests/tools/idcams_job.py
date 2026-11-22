"""An IDCAMS step in a job case (#8880, part of #8878 / #4890): the steps of `tests/tools/equivalence_job.py` that are not a
program but an IDCAMS deck.

    {"idcams": "load-ksds", "sysin": "load-ksds-sysin.txt",
     "dds": {"IN":  {"lrecl": 10, "feed": {"step": "report-step", "dd": "OUT"}},
             "OUT": {"lrecl": 10},
             "KS":  {"vsam": "APP.TRAN.KSDS"}}}

GnuCOBOL has no IDCAMS, so the oracle for the step is the model (`det/idcams_model.py`, #8931) and the port is the Java
runtime (`cobolrt/job/Idcams.java`, #8966). A step is run through both against the same inputs; the claim is that the
two agree on everything the step leaves: its condition code (RC, LASTCC, MAXCC), its log, the catalog and every
sequential dataset. What the step reads from an earlier step is that step's COBOL-side (oracle) output, the very bytes
both sides are given; what a later program step reads from it is the model's sequential output, so the chain composes
as a program-to-program feed does. The catalog persists from one IDCAMS step to the next. IBM (SC23-6846-60) is the
reference: the model's assumptions are register F6, and the oracle is the model, not z/OS.

`dds` keys: `lrecl` (record length, required for a sequential DD), `disp` (OLD default, SHR, NEW, passed to the model,
which refuses MOD), `feed` ({step, dd}: a sequential dataset of an earlier step, same record length), `input` (a
file of text lines beside the job case, read as fixed records in latin-1), or `vsam` (the DD names a cluster the
catalog holds). Refused by name: a feed from or into an indexed dataset (a KSDS direct to a program step is not
modelled: REPRO it to a sequential DD), a feed from a dataset the source step does not compare, a step the model
refuses (the Java must refuse with the same text, and the job stops there), a DD of an earlier step that the deck
relies on without declaring it again (the model gives a step only its own DDs; the Java driver keeps DDs).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))  # noqa: E402 -- before any gitgalaxy import
sys.path.insert(0, str(Path(__file__).resolve().parent))

from equivalence_gdg import Unsupported  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import idcams_model as M  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det.dfsort import Refused  # noqa: E402

JOB_RT = ROOT / "gitgalaxy" / "tools" / "cobol_to_java" / "det" / "cobolrt" / "job"
STEP_KEYS = {"idcams", "sysin", "dds"}
DD_KEYS = {"lrecl", "disp", "feed", "input", "vsam"}


def pseudo_case(step: dict[str, Any]) -> dict[str, Any]:
    """The step as `check_job` sees a case: its sequential DDs are datasets the step compares."""
    return {"kind": "idcams", "datasets": {dd: {"organization": "sequential", "reclen": spec["lrecl"], "compare": True}
                                           for dd, spec in step.get("dds", {}).items() if "lrecl" in spec}}  # fmt: skip


def check_step(step: dict[str, Any], earlier: list[str], cases: dict[str, dict[str, Any]], base: Path) -> None:
    """Refuse an IDCAMS step the harness cannot run faithfully."""
    name = step["idcams"]
    if unknown := set(step) - STEP_KEYS:
        raise Unsupported(f"idcams step {name}: unknown key(s) {sorted(unknown)}")
    sysin = step.get("sysin")
    if not isinstance(sysin, str) or not (base / sysin).is_file():
        raise Unsupported(f"idcams step {name}: no sysin file {sysin!r} beside the job case")
    dds = step.get("dds", {})
    if not isinstance(dds, dict):
        raise Unsupported(f"idcams step {name}: dds must be a mapping of DD name to its spec")
    for dd, spec in dds.items():
        if not isinstance(spec, dict) or (bad := set(spec) - DD_KEYS):
            raise Unsupported(
                f"idcams step {name}: DD {dd}: unknown key(s) {sorted(bad) if isinstance(spec, dict) else spec}"
            )
        if "vsam" in spec:
            if set(spec) != {"vsam"} or not isinstance(spec["vsam"], str):
                raise Unsupported(f"idcams step {name}: DD {dd}: a vsam DD carries only the cluster name")
            continue
        if not isinstance(spec.get("lrecl"), int) or spec["lrecl"] <= 0:
            raise Unsupported(f"idcams step {name}: DD {dd}: a sequential DD needs a positive lrecl")
        if "feed" in spec and "input" in spec:
            raise Unsupported(f"idcams step {name}: DD {dd} is both fed and given an input")
        if "input" in spec and not (base / spec["input"]).is_file():
            raise Unsupported(f"idcams step {name}: DD {dd}: no file {spec['input']} beside the job case")
        if "feed" in spec:
            feed = spec["feed"]
            src = feed.get("step") if isinstance(feed, dict) else None
            if src not in earlier:
                raise Unsupported(f"idcams step {name}: feed {dd} comes from {src!r}, which is not an earlier step")
            out = cases[src]["datasets"].get(feed.get("dd"))
            if out is None or not out.get("compare"):
                raise Unsupported(f"idcams step {name}: feed {dd} reads {src}.{feed.get('dd')}, which that step does "
                                  "not compare")  # fmt: skip
            if out.get("organization", "sequential") != "sequential":
                raise Unsupported(f"idcams step {name}: feed {dd} reads an {out['organization']} dataset: REPRO the "
                                  "cluster to a sequential DD in an IDCAMS step first")  # fmt: skip
            if out["reclen"] != spec["lrecl"]:
                raise Unsupported(f"idcams step {name}: feed {dd} has record length {spec['lrecl']}, "
                                  f"{src}.{feed['dd']} writes {out['reclen']}")  # fmt: skip


def hexes(recs: list[bytes]) -> str:
    return ",".join(r.hex() for r in recs) or "-"


def _jbool(v: bool) -> str:
    return "true" if v else "false"


def _describe(e: Any) -> str:
    if isinstance(e, M.Cluster):
        return f"CLUSTER {e.name} {_jbool(e.indexed)} {e.key_len} {e.key_off} {e.avg} {e.max} {hexes(e.records)}"
    if isinstance(e, M.Aix):
        return (f"AIX {e.name} {e.relate} {e.key_len} {e.key_off} {e.avg} {e.max} {_jbool(e.unique)} "
                f"{_jbool(e.upgrade)} {_jbool(e.built)}")  # fmt: skip
    return f"PATH {e.name} {e.aix} {_jbool(e.update)}"


def render(r: M.Result) -> list[str]:
    """The model's result in the Java driver's output format (RC, LOG, CAT, DS, PATH lines)."""
    out = [f"RC {r.rc} {r.lastcc} {r.maxcc}"] + [f"LOG {line}" for line in r.log]
    out += ["CAT " + _describe(e) for e in r.catalog.values()]
    out += [f"DS {k} {hexes(v.records)}" for k, v in r.datasets.items()]
    for e in r.catalog.values():
        if isinstance(e, M.Path):
            try:
                v = hexes(M.path_records(r.catalog, e.name))
            except Refused as x:
                v = f"REFUSED {x}"
            out.append(f"PATH {e.name} {v}")
    return out


def spec_lines(catalog: dict[str, Any], dds: dict[str, Any], deck: Path) -> list[str]:
    lines: list[str] = []
    for c in catalog.values():
        if isinstance(c, M.Cluster):
            lines.append(
                f"CLUSTER {c.name} {int(c.indexed)} {c.key_len} {c.key_off} {c.avg} {c.max} {hexes(c.records)}"
            )
    for dd, d in dds.items():
        lines.append(
            f"VSAM {dd} {d.name}" if isinstance(d, M.Vsam) else f"SEQ {dd} {d.lrecl} {d.disp} {hexes(d.records)}"
        )
    return [*lines, f"STEP {deck}"]


class JavaSide:
    """The Java runtime, compiled once. Each IDCAMS step replays the job's earlier steps (their DDs, their decks) in one
    JVM, so the catalog it ends with is its own, never one rebuilt from the model's."""

    def __init__(self, work: Path):
        self.work = work
        self.classes: Path | None = None
        self.steps: list[list[str]] = []  # per committed step: its DD lines + STEP line
        self.n = 0

    def _compile(self) -> Path:
        from javac_server import javac, jdk_bin

        bin_dir = jdk_bin()
        if bin_dir is None:
            raise SystemExit("an IDCAMS step needs a JDK 17 (JDK_17 / JAVA_HOME)")
        self.bin_dir = bin_dir
        src = self.work / "idcams-java" / "src" / "p" / "cobolrt" / "job"
        src.mkdir(parents=True, exist_ok=True)
        (src / "Idcams.java").write_text((JOB_RT / "Idcams.java").read_text(encoding="utf-8").replace("__PACKAGE__", "p"),
                                         encoding="utf-8")  # fmt: skip
        classes = self.work / "idcams-java" / "classes"
        javac(
            [str(bin_dir / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(classes), str(src / "Idcams.java")],
            check=True,
        )  # noqa: S603
        return classes

    def run(self, dds: dict[str, Any], sysin: str, commit: bool) -> list[str]:
        """The Java driver's lines for this step, replayed after the committed ones (a job's catalog starts empty)."""
        if self.classes is None:
            self.classes = self._compile()
        self.n += 1
        deck = self.work / "idcams-java" / f"deck{self.n}.txt"
        deck.write_text(sysin, encoding="utf-8")
        mine = spec_lines({}, dds, deck)
        spec = self.work / "idcams-java" / f"spec{self.n}.txt"
        spec.write_text("\n".join(["RESET", *[ln for s in self.steps for ln in s], *mine]) + "\n", encoding="utf-8")
        got = subprocess.run(  # noqa: S603
            [str(self.bin_dir / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(self.classes),
             "p.cobolrt.job.Idcams", str(spec)],
            capture_output=True, encoding="utf-8", check=True,
        ).stdout.split("--\n")[-1].splitlines()  # fmt: skip
        starts = [i for i, ln in enumerate(got) if ln.startswith(("RC ", "REFUSED "))]
        lines = got[starts[-1] :]
        if commit:
            self.steps.append(mine)
        return lines


def _records(data: bytes, lrecl: int, what: str) -> list[bytes]:
    if len(data) % lrecl:
        raise Unsupported(f"{what}: {len(data)} bytes are not whole records of {lrecl}")
    return [data[i : i + lrecl] for i in range(0, len(data), lrecl)]


def run_step(step: dict[str, Any], base: Path, outputs: dict[str, dict[str, bytes]], state: dict[str, Any],
             java: JavaSide, fed: dict[str, str]) -> dict[str, Any]:  # fmt: skip
    """Run one IDCAMS step on both sides. `state` holds the model's catalog between steps (`state["catalog"]`) and
    `outputs` the sequential output of every earlier step (`outputs[name][dd]`, fixed records joined)."""
    import equivalence_common as common

    name = step["idcams"]
    dds: dict[str, Any] = {}
    for dd, spec in step.get("dds", {}).items():
        if "vsam" in spec:
            dds[dd] = M.Vsam(spec["vsam"])
            continue
        data = b""
        if "feed" in spec:
            src = outputs.get(spec["feed"]["step"], {}).get(spec["feed"]["dd"])
            if src is None:
                return {"case": name, "kind": "idcams", "ok": False,
                        "stopped": f"{spec['feed']['step']} left no {spec['feed']['dd']}"}  # fmt: skip
            data = src
            fed[dd] = f"{spec['feed']['step']}.{spec['feed']['dd']} ({len(src) // spec['lrecl']} records)"
        elif "input" in spec:
            data = common._fixed(base / spec["input"], spec["lrecl"], "latin-1")
        dds[dd] = M.Sequential(spec["lrecl"], _records(data, spec["lrecl"], f"idcams step {name}: DD {dd}"),
                               spec.get("disp", "OLD"))  # fmt: skip
    sysin = (base / step["sysin"]).read_text(encoding="utf-8")
    entry: dict[str, Any] = {"case": name, "kind": "idcams", "fed": fed}
    try:
        r = M.run(sysin, state["catalog"], dds)
    except Refused as e:
        lines = java.run(dds, sysin, commit=False)
        entry.update(ok=False, refused=str(e), java_refused=lines == [f"REFUSED {e}"],
                     stopped=f"the model refuses the step by name ({e}): not proven")  # fmt: skip
        return entry
    want = render(r)
    got = java.run(dds, sysin, commit=True)
    state["catalog"] = r.catalog
    outputs[name] = {dd: b"".join(d.records) for dd, d in r.datasets.items()}
    jdd = {ln.split(" ", 2)[1]: ln.split(" ", 2)[2] for ln in got if ln.startswith("DS ")}
    entry["outputs"] = {dd: {"records": len(d.records),
                             "equal": sum(a == b for a, b in zip(jdd.get(dd, "-").split(","), hexes(d.records).split(","))
                                          ) if d.records else 0, "diffs": []}
                        for dd, d in r.datasets.items()}  # fmt: skip
    jrc = got[0].split()[1:] if got and got[0].startswith("RC ") else None
    entry["return_code"] = {"model": r.rc, "java": int(jrc[0]) if jrc else None}
    entry["condition_codes"] = {"model": [r.rc, r.lastcc, r.maxcc], "java": [int(x) for x in jrc] if jrc else None}
    entry["ok"] = want == got
    if not entry["ok"]:
        entry["diffs"] = [f"model {a!r} / java {b!r}" for a, b in zip(want, got) if a != b][:5] or [
            f"model {len(want)} lines / java {len(got)} lines"]  # fmt: skip
    return entry
