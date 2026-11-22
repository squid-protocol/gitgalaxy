"""The Java side of an IDCAMS job step (#8881, SC23-6846-60): run one deck through `cobolrt/job/Idcams.java` and compare it,
line by line, with the model (`det/idcams_model.py`) run on the same catalog and datasets.

GnuCOBOL has no IDCAMS, so the model is the oracle and the Java is a second implementation of the same rules. What is
compared is what the job harness feeds forward and what a reader of the step sees: the return codes, the log, the
catalog (every cluster, alternate index and path), the sequential datasets, the records read through each path in
alternate-key order, and the text of a refusal. The line format is the driver's (`Idcams.main`), the same one
`tests/cobol_mainframe/test_idcams_java_8881.py` pins over its scenarios.

`compare` returns None when there is no JDK: the caller reports the step as model only, never as proven.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from javac_server import javac as javac_run  # noqa: E402 -- a javac that stays up
from javac_server import jdk_bin  # noqa: E402

from gitgalaxy.tools.cobol_to_java.det import idcams_model as M  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det.dfsort import Refused  # noqa: E402

JOB_RT = Path(__file__).resolve().parents[2] / "gitgalaxy" / "tools" / "cobol_to_java" / "det" / "cobolrt" / "job"


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


def model_lines(sysin: str, catalog: dict[str, Any], dds: dict[str, Any]) -> list[str]:
    """The model's side, in the driver's line format."""
    try:
        r = M.run(sysin, catalog, dds)
    except Refused as e:
        return [f"REFUSED {e}"]
    out = [f"RC {r.rc} {r.lastcc} {r.maxcc}", *(f"LOG {line}" for line in r.log)]
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


def _spec(catalog: dict[str, Any], dds: dict[str, Any], deck: Path) -> str:
    lines = ["RESET"]
    for c in catalog.values():
        if not isinstance(c, M.Cluster):
            raise Refused(f"the catalog entry {c.name} is not a cluster: a step starts with clusters only")
        lines.append(f"CLUSTER {c.name} {int(c.indexed)} {c.key_len} {c.key_off} {c.avg} {c.max} {hexes(c.records)}")
    for name, d in dds.items():
        lines.append(f"VSAM {name} {d.name}" if isinstance(d, M.Vsam)
                     else f"SEQ {name} {d.lrecl} {d.disp} {hexes(d.records)}")  # fmt: skip
    lines.append(f"STEP {deck}")
    return "\n".join(lines) + "\n"


def java_lines(sysin: str, catalog: dict[str, Any], dds: dict[str, Any]) -> list[str] | None:
    """The Java runtime's side for the same step, or None with no JDK."""
    bin_dir = jdk_bin()
    if bin_dir is None:
        return None
    with tempfile.TemporaryDirectory(prefix="idcams_java_") as tmp:
        work = Path(tmp)
        src = work / "src" / "p" / "cobolrt" / "job"
        src.mkdir(parents=True)
        (src / "Idcams.java").write_text(
            (JOB_RT / "Idcams.java").read_text(encoding="utf-8").replace("__PACKAGE__", "p"), encoding="utf-8"
        )
        javac_run([str(bin_dir / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(work / "classes"),
                   str(src / "Idcams.java")], check=True)  # fmt: skip
        deck = work / "deck.txt"
        deck.write_text(sysin, encoding="utf-8")
        spec = work / "spec.txt"
        spec.write_text(_spec(catalog, dds, deck), encoding="utf-8")
        got = subprocess.run(  # noqa: S603
            [str(bin_dir / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(work / "classes"),
             "p.cobolrt.job.Idcams", str(spec)],
            capture_output=True, encoding="utf-8", check=True,
        ).stdout  # fmt: skip
    return got.split("--\n")[1].splitlines()


def compare(sysin: str, catalog: dict[str, Any], dds: dict[str, Any]) -> dict[str, Any] | None:
    """`{"equal": bool, "lines": n, "differs": [first differing pair]}`, or None when the Java side cannot run (no JDK)."""
    want = model_lines(sysin, catalog, dds)
    got = java_lines(sysin, catalog, dds)
    if got is None:
        return None
    diff = [(w, g) for w, g in zip(want, got, strict=False) if w != g]
    if len(want) != len(got):
        diff.append((f"{len(want)} lines", f"{len(got)} lines"))
    return {"equal": not diff, "lines": len(want), "differs": diff[:3]}
