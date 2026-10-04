#!/usr/bin/env python3
"""Devin's CardDemo ports (Cognition's public workshop repositories), run through our equivalence harness.

    python tests/tools/devin_port.py --work DIR [--port NAME,...] [--case NAME,...] [--environments all|default,...]
                                     [--jdk21 PATH]

Phase 2 of the Devin benchmark (docs/research/devin-carddemo-survey.md lists every branch; the results are in
docs/research/devin-carddemo-harness.md). Each port is fetched at a pinned commit, built as it ships, and run on
the inputs one of our proven cases gives GnuCOBOL; its outputs go through the harness's own comparison
(equivalence.compare_run: RETURN-CODE or ABEND, every compared dataset field by field per its copybook, and
SYSOUT). Nothing of theirs is committed here or changed.

The adapter -- this file and tests/tools/devin/adapter -- and nothing more:
  - launching: each port's own command line, as its README or main method documents it (PORTS[...]["argv"]),
    with the case's data sets, JCL PARM and frozen clock in the form that command line takes them;
  - inputs: the case's input data sets either as the fixed-length records GnuCOBOL is given (an indexed one in
    primary-key order, as a KSDS unloads), or -- for a port that reads text lines -- the case's input file as the
    corpus ships it (the same records, one per line);
  - the JVM default locale and time zone of each harness environment (#3821), set by EnvLauncher before the
    port's unmodified main class runs -- what the harness's generated test does for our ports;
  - how a port reports a user abend, read from its code (a stderr message, or a fixed exit status), recorded as
    the harness's Unnnn (the code modulo 4096, as the COBOL side's abend stub records it);
  - output decoding, declared per port and per data set (DECODERS): a port's own framing of variable-length
    records (newline-separated, or a bare 2-byte length) re-framed as GnuCOBOL frames them; packed-decimal
    fields a port writes as hex text turned back into their bytes. A port that writes variable-length records
    with no framing at all is compared as written: the comparison reports the framing error.
Not applied: the case's fault runs. They inject FILE STATUS values at the program's I/O statements through an
I/O layer our ports call (CobolFiles); these ports have their own I/O code and no such point, and adding one would
mean changing their code. Each port is judged on the case's base run, under every environment.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

TOOLS = Path(__file__).resolve().parent
REPO_ROOT = TOOLS.parent.parent
sys.path[:0] = [str(TOOLS), str(REPO_ROOT)]
import equivalence as eq  # noqa: E402
import equivalence_java as ej  # noqa: E402
import mainframe_corpus as mc  # noqa: E402
from equivalence_common import _fixed, _input_path, data_encoding  # noqa: E402

from gitgalaxy.core.source_text import decode_bytes  # noqa: E402

ADAPTER = TOOLS / "devin" / "adapter"
COGNITION = "https://github.com/Cognition-Partner-Workshops/uc-legacy-modernization-cobol-to-java"
CODEV = "https://github.com/codev-workshops/uc-legacy-modernization-cobol-to-java"
CBACT01C_FILES = {"ACCTFILE": "{dd:ACCTFILE}", "OUTFILE": "{dd:OUTFILE}", "ARRYFILE": "{dd:ARRYFILE}",
                  "VBRCFILE": "{dd:VBRCFILE}"}  # fmt: skip
POSITIONAL = list(CBACT01C_FILES.values())


def _dd_launcher(program: str) -> list[str]:
    return [program, "{dd-options}", "{parm-option}", "--now", "{now}"]


# Each port: a pinned branch; how it builds ("jar": `mvn package`, the jar; "classes": `mvn compile` plus its
# dependency classpath; "javac": one source file); its main class and command line ({dd:NAME}: the data set's
# file, {dd-options}: `--dd NAME=file` for each, {outdir}: a directory the port writes its outputs into under
# their DD names, {parm-option}: `--parm PARM` when the step has one, {now}: the frozen clock in "now"'s form);
# the input form ("fixed" or "source"); the per-data-set output decoders (DECODERS); how it reports an abend.
PORTS: dict[str, dict[str, Any]] = {
    "eval-arm-a": {
        "repo": COGNITION, "branch": "eval/devin-arm-a-raw-cobol", "sha": "19dd9f267abd4eac914d50db9367fdc083110f7e",
        "pr": None, "about": "eval arm A: the COBOL sources, copybooks, JCL and a golden-output harness only",
        "build": ("jar", "java", "java/target/carddemo-batch.jar"), "jdk": 21, "main": "carddemo.batch.Main",
        "now": "%Y-%m-%d %H:%M:%S", "abend": {"stderr": r"CEE3ABD: USER ABEND U(\d+)"}, "input": "fixed",
        "programs": {"CBACT01C": ("carddemo-readacct", _dd_launcher("CBACT01C")),
                     "CBACT04C": ("carddemo-intcalc", _dd_launcher("CBACT04C")),
                     "CBTRN02C": ("carddemo-posttran", _dd_launcher("CBTRN02C"))},
    },
    "eval-arm-b": {
        "repo": COGNITION, "branch": "eval/devin-arm-b-cobol-plus-atx-analysis",
        "sha": "ef9aa4f08f6f2bd2e10e461ca302fd7d1ef350b3", "pr": None,
        "about": "eval arm B: the same, plus AWS Transform's analysis of the code",
        "build": ("jar", "java", "java/target/carddemo-batch.jar"), "jdk": 21, "main": "carddemo.Main",
        "now": "%Y-%m-%d-%H.%M.%S.000000", "abend": {"exit": 999 & 0xFF, "code": 999}, "input": "fixed",
        "programs": {"CBACT01C": ("carddemo-readacct", _dd_launcher("CBACT01C")),
                     "CBACT04C": ("carddemo-intcalc", _dd_launcher("CBACT04C")),
                     "CBTRN02C": ("carddemo-posttran", _dd_launcher("CBTRN02C"))},
    },
    "pr229": {
        "repo": COGNITION, "branch": "devin/1785333294-cbact01c-java", "sha": "05c300cce2fc6ea9955e7913c06f598ebec74079",
        "pr": 229, "about": "one source file; its own parity run against GnuCOBOL, byte for byte",
        "build": ("javac", "java-migration/src/CBACT01C.java", None), "jdk": 17, "main": "CBACT01C",
        "input": "fixed", "programs": {"CBACT01C": ("carddemo-readacct", ["{dd:ACCTFILE}", "{outdir}", "ascii"])},
    },
    "pr167": {
        "repo": COGNITION, "branch": "devin/1776439113-cbact01c-java-migration",
        "sha": "ac6c2443b42fa8725f4bb81a44fa235c67a0238e", "pr": 167, "about": "Maven project, positional arguments",
        "build": ("classes", "java-migration", None), "jdk": 17, "main": "com.carddemo.batch.CBACT01C",
        "input": "source", "decode": {"VBRCFILE": "vb-unframed"},
        "programs": {"CBACT01C": ("carddemo-readacct", POSITIONAL)},
    },
    "pr168": {
        "repo": COGNITION, "branch": "devin/1776677664-cbact01c-java-migration",
        "sha": "baf8cfd453e103429c86a80810f808d869ef4a52", "pr": 168, "about": "Maven project, positional arguments",
        "build": ("classes", "java-app", None), "jdk": 17, "main": "com.carddemo.batch.Cbact01c",
        "input": "source", "decode": {"VBRCFILE": "vb-lines"},
        "programs": {"CBACT01C": ("carddemo-readacct", POSITIONAL)},
    },
    "pr214": {
        "repo": COGNITION, "branch": "devin/1781538606-cobol-to-java-cbact01c",
        "sha": "1fa50de24c402efc98a25775bbd6fcfab894264f", "pr": 214, "about": "Maven project, positional arguments",
        "build": ("classes", "java-migration", None), "jdk": 21, "main": "com.carddemo.batch.AccountFileProcessor",
        "input": "source",
        "decode": {"OUTFILE": ("lines-hex-packed", 107, [(90, 7)]),
                   "ARRYFILE": ("lines-hex-packed", 110, [(23 + 19 * k, 7) for k in range(5)]),
                   "VBRCFILE": "vb-len2"},
        "programs": {"CBACT01C": ("carddemo-readacct", POSITIONAL)},
    },
    "pr220": {
        "repo": COGNITION, "branch": "devin/1782308896-cobol-to-java-cbact01c",
        "sha": "ceea1ef9e5c0235b1bd1c8562bba325ab01b19df", "pr": 220, "about": "Maven project, positional arguments",
        "build": ("classes", "java-modernized", None), "jdk": 17, "main": "com.carddemo.batch.AccountFileProcessor",
        "input": "source", "programs": {"CBACT01C": ("carddemo-readacct", POSITIONAL)},
    },
    "codev13": {
        "repo": CODEV, "branch": "devin/1788345561-cbact01c-batch-flow", "sha": "73e9452dda39d56d564f5456092705ed84864983",
        "pr": 13, "about": "codev series: the batch flow", "build": ("classes", "java", None), "jdk": 17,
        "main": "com.carddemo.batch.cbact01c.Cbact01c", "input": "fixed",
        "decode": {"VBRCFILE": "vb-rdw"},
        "programs": {"CBACT01C": ("carddemo-readacct", ["--acctfile", "{dd:ACCTFILE}", "--outfile", "{dd:OUTFILE}",
                                                        "--arryfile", "{dd:ARRYFILE}", "--vbrcfile", "{dd:VBRCFILE}",
                                                        "--charset", "ASCII", "--display"])},
    },
    "codev14": {
        "repo": CODEV, "branch": "devin/1788346206-cbact01c-golden-master",
        "sha": "2f5c0773b96ae98b4046783f8de2e4e96e79cf1c", "pr": 14,
        "about": "codev series: the golden master (a Python oracle for the expected bytes)",
        "build": ("classes", "java", None), "jdk": 17, "main": "com.carddemo.batch.cbact01c.Cbact01c", "input": "fixed",
        "decode": {"VBRCFILE": "vb-rdw"},
        "programs": {"CBACT01C": ("carddemo-readacct", ["--acctfile", "{dd:ACCTFILE}", "--outfile", "{dd:OUTFILE}",
                                                        "--arryfile", "{dd:ARRYFILE}", "--vbrcfile", "{dd:VBRCFILE}",
                                                        "--charset", "ASCII", "--display"])},
    },
}  # fmt: skip


# ---- output decoders: a port's own representation of a data set, as the harness's bytes ---------------------
def gnucobol_frame(records: list[bytes]) -> bytes:
    """Variable-length records framed as GnuCOBOL writes them (equivalence_common.split_varseq)."""
    return b"".join(len(r).to_bytes(2, "big") + b"\0\0" + r for r in records)


def vb_lines(data: bytes) -> bytes:
    """Records separated by newlines (text with no newline inside a record), re-framed."""
    recs = data.split(b"\n")
    return gnucobol_frame(recs[:-1] if recs and recs[-1] == b"" else recs)


def vb_len2(data: bytes) -> bytes:
    """Records each led by a bare big-endian 2-byte length, re-framed."""
    recs, i = [], 0
    while i + 2 <= len(data):
        n = int.from_bytes(data[i : i + 2], "big")
        recs.append(data[i + 2 : i + 2 + n])
        i += 2 + n
    if i != len(data):
        return data  # not that framing: compared as written (the comparison reports the framing error)
    return gnucobol_frame(recs)


def lines_hex_packed(data: bytes, reclen: int, packed: list[tuple[int, int]]) -> bytes:
    """Newline-terminated records whose packed-decimal fields (offset, bytes) are written as 2*bytes hex digits:
    each record's bytes as the copybook lays them out. Anything else is compared as written."""
    out = []
    for line in data.split(b"\n"):
        if not line:
            continue
        rec, pos = bytearray(), 0  # rec: the record so far; pos: where in the line the next byte is read
        for off, n in sorted(packed):
            text = off - len(rec)  # the bytes before this packed field, copied as they are
            rec += line[pos : pos + text]
            pos += text
            try:
                rec += bytes.fromhex(line[pos : pos + 2 * n].decode("ascii"))
            except (ValueError, UnicodeDecodeError):
                return data  # not hex where a packed field sits: compared as written
            pos += 2 * n
        rec += line[pos:]
        if len(rec) != reclen:
            return data
        out.append(bytes(rec))
    return b"".join(out)


def vb_rdw(data: bytes) -> bytes:
    """Records each led by a z/OS RDW -- a 2-byte length that counts the 4-byte header, then two zero bytes --
    re-framed as GnuCOBOL frames them (oracle_assumptions.md F3: GnuCOBOL's length does not count the header)."""
    recs, i = [], 0
    while i + 4 <= len(data):
        n = int.from_bytes(data[i : i + 2], "big")
        if n < 4 or data[i + 2 : i + 4] != b"\0\0":
            return data  # not an RDW: compared as written (the comparison reports the framing error)
        recs.append(data[i + 4 : i + n])
        i += n
    if i != len(data):
        return data
    return gnucobol_frame(recs)


def decode(spec: Any, data: bytes) -> bytes:
    if spec is None:
        return data
    if spec == "vb-lines":
        return vb_lines(data)
    if spec == "vb-len2":
        return vb_len2(data)
    if spec == "vb-rdw":
        return vb_rdw(data)
    if spec == "vb-unframed":
        return data  # nothing marks where a record ends: compared as written
    if isinstance(spec, tuple) and spec[0] == "lines-hex-packed":
        return lines_hex_packed(data, spec[1], spec[2])
    raise ValueError(f"unknown decoder {spec!r}")


# ---- fetch, build, run ------------------------------------------------------------------------------------------
def run(argv: list[str], cwd: Optional[Path] = None, env: Optional[dict[str, str]] = None,
        timeout: int = 1800) -> subprocess.CompletedProcess:  # fmt: skip
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, timeout=timeout, check=False)  # noqa: S603


def fetch(port: dict[str, Any], work: Path) -> Path:
    """The port's repository at its pinned commit (one clone per repository, a detached worktree per port)."""
    clone = work / "src" / port["repo"].rstrip("/").split("/")[-2]
    if not (clone / ".git").is_dir():
        clone.parent.mkdir(parents=True, exist_ok=True)
        p = run(["git", "clone", "-q", "--no-checkout", port["repo"], str(clone)])
        if p.returncode:
            raise RuntimeError(f"git clone {port['repo']}: {p.stderr.decode()}")
    tree = work / "ports" / port["sha"][:12]
    if not tree.is_dir():
        if run(["git", "-C", str(clone), "cat-file", "-e", port["sha"]]).returncode:
            run(["git", "-C", str(clone), "fetch", "-q", "origin", port["sha"]])
        p = run(["git", "-C", str(clone), "worktree", "add", "-q", "--detach", str(tree), port["sha"]])
        if p.returncode:
            raise RuntimeError(f"checkout {port['sha']}: {p.stderr.decode()}")
    return tree


def jdk_env(jdk: Optional[Path]) -> Optional[dict[str, str]]:
    if not jdk:
        return None
    return {**os.environ, "JAVA_HOME": str(jdk), "PATH": f"{jdk / 'bin'}:{os.environ.get('PATH', '')}"}


def tool(jdk: Optional[Path], name: str) -> str:
    return str(jdk / "bin" / name) if jdk else (shutil.which(name) or name)


def build(port: dict[str, Any], tree: Path, work: Path, jdk: Optional[Path]) -> str:
    """The port built as it ships; returns its classpath. Its own tests are skipped (they are not our judge)."""
    kind, where, jar = port["build"]
    mvn = ["mvn", "-q", "-B", "-DskipTests", f"-Dmaven.repo.local={work / 'm2'}"]
    if kind == "jar":
        if not (tree / jar).is_file():
            p = run([*mvn, "package"], cwd=tree / where, env=jdk_env(jdk))
            if p.returncode or not (tree / jar).is_file():
                raise RuntimeError(f"build failed:\n{p.stdout.decode()[-2000:]}\n{p.stderr.decode()[-2000:]}")
        return str(tree / jar)
    if kind == "classes":
        cpf = tree / where / "target" / "gg-classpath.txt"
        if not cpf.is_file():
            p = run([*mvn, "compile", "dependency:build-classpath", f"-Dmdep.outputFile={cpf}"], cwd=tree / where,
                    env=jdk_env(jdk))  # fmt: skip
            if p.returncode:
                raise RuntimeError(f"build failed:\n{p.stdout.decode()[-2000:]}\n{p.stderr.decode()[-2000:]}")
        deps = cpf.read_text(encoding="utf-8").strip()
        return f"{tree / where / 'target' / 'classes'}" + (f":{deps}" if deps else "")
    out = tree.parent / f"{tree.name}-classes"
    if not out.is_dir():
        out.mkdir()
        p = run([tool(jdk, "javac"), "-d", str(out), str(tree / where)])
        if p.returncode:
            raise RuntimeError(f"javac failed:\n{p.stderr.decode()[-2000:]}")
    return str(out)


def adapter_classes(work: Path, jdk: Optional[Path]) -> Path:
    out = work / "adapter"
    if not (out / "devinadapter" / "EnvLauncher.class").is_file():
        out.mkdir(parents=True, exist_ok=True)
        p = run([tool(jdk, "javac"), "--release", "17", "-d", str(out), *map(str, ADAPTER.rglob("*.java"))])
        if p.returncode:
            raise RuntimeError(p.stderr.decode())
    return out


def key_ordered(data: bytes, reclen: int, key: dict[str, int]) -> bytes:
    """An indexed dataset's records in primary-key order, as a KSDS unloads (byte order of the key)."""
    recs = [data[i : i + reclen] for i in range(0, len(data), reclen)]
    return b"".join(sorted(recs, key=lambda r: r[key["offset"] : key["offset"] + key["length"]]))


def stage_inputs(case: dict[str, Any], corpus: Path, into: Path, form: str) -> dict[str, Path]:
    """{DDNAME: file}: an input as the case gives GnuCOBOL (`fixed`) or as the corpus ships it (`source`); an
    output, an empty file the port writes."""
    into.mkdir(parents=True, exist_ok=True)
    enc = data_encoding(case)
    dds = {}
    for dd, spec in case["datasets"].items():
        f = into / f"{dd}.dat"
        if "input" in spec and form == "source":
            f.write_bytes(_input_path(case, corpus, spec["input"]).read_bytes())
        elif "input" in spec:
            data = _fixed(_input_path(case, corpus, spec["input"]), spec["reclen"], enc)
            if spec.get("organization") == "indexed":
                data = key_ordered(data, spec["reclen"], spec["keys"][0])
            f.write_bytes(data)
        else:
            f.write_bytes(b"")
        dds[dd] = f
    return dds


def clock_arg(case: dict[str, Any], fmt: str) -> str:
    """The case's frozen clock ('YYYY/MM/DD HH:MM:SS.hh') in the form the port's --now takes (`fmt`, strftime)."""
    c = case["clock"]
    if not re.fullmatch(r"\d{4}/\d\d/\d\d \d\d:\d\d:\d\d\.00", c):
        raise ValueError(f"clock {c!r}: hundredths other than .00 cannot be passed to --now")
    return datetime.strptime(c[:19], "%Y/%m/%d %H:%M:%S").strftime(fmt)


def command(port: dict[str, Any], template: list[str], case: dict[str, Any], dds: dict[str, Path],
            outdir: Path) -> list[str]:  # fmt: skip
    argv: list[str] = []
    for t in template:
        if t == "{dd-options}":
            for dd, f in dds.items():
                argv += ["--dd", f"{dd}={f}"]
        elif t == "{parm-option}":
            argv += ["--parm", case["parm"]] if case.get("parm") else []
        elif t == "{now}":
            argv.append(clock_arg(case, port["now"]))
        elif t == "{outdir}":
            argv.append(str(outdir))
        elif t.startswith("{dd:"):
            argv.append(str(dds[t[4:-1]]))
        else:
            argv.append(t)
    return argv


def abend_code(port: dict[str, Any], proc: subprocess.CompletedProcess) -> Optional[int]:
    """The user abend code the port reports its own way: a message on stderr, or a fixed exit status."""
    how = port.get("abend")
    if not how:
        return None
    if "stderr" in how:
        m = re.search(how["stderr"].encode(), proc.stderr)
        return int(m.group(1)) if m else None
    return how["code"] if proc.returncode == how["exit"] else None


def java_outputs(case: dict[str, Any], port: dict[str, Any], dds: dict[str, Path], outdir: Path,
                 proc: subprocess.CompletedProcess) -> dict[str, bytes]:  # fmt: skip
    """Their run as the harness compares a run: every compared dataset (decoded per DECODERS), SYSOUT, and
    RETURN-CODE or ABEND."""
    outs = {}
    for dd, spec in case["datasets"].items():
        if not spec.get("compare"):
            continue
        f = outdir / dd if (outdir / dd).is_file() else dds[dd]
        outs[dd] = decode((port.get("decode") or {}).get(dd), f.read_bytes() if f.is_file() else b"")
    outs["SYSOUT"] = proc.stdout
    code = abend_code(port, proc)
    if code is not None:
        outs["ABEND"] = f"U{code % 4096:04d}".encode()
    else:
        outs["RETURN-CODE"] = str(proc.returncode).encode()
    return outs


# ---- what a difference is ----------------------------------------------------------------------------------------
OVERPUNCH = {**{c: (i, 1) for i, c in enumerate("{ABCDEFGHI")}, **{c: (i, -1) for i, c in enumerate("}JKLMNOPQR")}}


def _ibm_display(t: str) -> Optional[int]:
    """A signed zoned number as IBM's DISPLAY shows it: its digits, the last with the sign overpunched."""
    m = re.fullmatch(r"(\d*)([{}A-R])", t)
    if not m:
        return None
    digit, sign = OVERPUNCH[m.group(2)]
    return sign * int(m.group(1) + str(digit))


def _gnucobol_display(t: str) -> Optional[int]:
    """The same as GnuCOBOL's own DISPLAY shows it: every digit, then a separate + or -."""
    m = re.fullmatch(r"(\d+)([+-])", t)
    return (1 if m.group(2) == "+" else -1) * int(m.group(1)) if m else None


def sysout_classes(case: dict[str, Any], cobol: bytes, java: bytes) -> dict[str, Any]:
    """Every differing SYSOUT line, classed: `sign-display` when the only difference is a signed number shown as
    GnuCOBOL's own DISPLAY shows it (digits, then + or -) where IBM's DISPLAY shows the zoned bytes (the last
    digit overpunched; oracle_assumptions.md C8) -- the same value; `other` for anything else."""
    enc = data_encoding(case)
    a, b = eq.sysout_lines(cobol, enc), eq.sysout_lines(java, enc)
    out: dict[str, Any] = {"sign-display": 0, "other": 0, "examples": []}
    for n in range(max(len(a), len(b))):
        x, y = (a[n] if n < len(a) else None), (b[n] if n < len(b) else None)
        if x == y:
            continue
        if x is not None and y is not None and ":" in x and x.rsplit(":", 1)[0] == y.rsplit(":", 1)[0]:
            vx, vy = _ibm_display(x.rsplit(":", 1)[1].strip()), _gnucobol_display(y.rsplit(":", 1)[1].strip())
            if vx is not None and vx == vy:
                out["sign-display"] += 1
                continue
        out["other"] += 1
        if len(out["examples"]) < 3:
            out["examples"].append({"line": n + 1, "cobol": x, "java": y})
    return out


def first_difference(result: dict[str, Any]) -> str:
    """The run's first difference, in words: which output, which record, which field, both values."""
    if result.get("ok"):
        return ""
    for dd, d in (result.get("outputs") or {}).items():
        if d.get("diffs"):
            return f"{dd} {json.dumps(d['diffs'][0], default=str)[:400]}"
    s = result.get("sysout") or {}
    if s.get("diffs"):
        return f"SYSOUT {json.dumps(s['diffs'][0], default=str)[:400]}"
    return result.get("summary", "")


def judge(name: str, program: str, work: Path, envs: list[str], jdk: Optional[Path]) -> dict[str, Any]:
    port = PORTS[name]
    case_name, template = port["programs"][program]
    case = eq.load_case(case_name)
    (entry,) = mc.select([case["corpus"]])
    corpus = mc.require_clone(entry)
    out = work / "runs" / name / case_name
    if out.exists():
        out = out.with_name(f"{case_name}-{datetime.now().strftime('%H%M%S%f')}")
    out.mkdir(parents=True)
    cobol = eq.run_cobol(case, corpus, work / "cobol" / case_name)
    coverage = eq.cobol_coverage(case, corpus, [work / "cobol" / case_name / eq.cov.TRACE_NAME], out / "coverage.json")
    result: dict[str, Any] = {"port": name, "branch": port["branch"], "sha": port["sha"], "pr": port.get("pr"),
                              "program": program, "case": case_name, "coverage": coverage, "runs": [],
                              "fault_runs": len(case.get("faults", [])), "fault_runs_applied": 0}  # fmt: skip
    try:
        tree = fetch(port, work)
        classpath = build(port, tree, work, jdk)
    except RuntimeError as e:
        result.update({"proven": False, "build_error": str(e)[:2000]})
        return result
    adapter = adapter_classes(work, jdk)
    for env_name in envs:
        env = ej.environment(env_name)
        dds = stage_inputs(case, corpus, out / env_name, port["input"])
        outdir = out / env_name / "out"
        outdir.mkdir()
        argv = [tool(jdk, "java"), "-cp", f"{adapter}:{classpath}", "devinadapter.EnvLauncher", env["locale"],
                env["tz"], port["main"], *command(port, template, case, dds, outdir)]  # fmt: skip
        proc = run(argv, cwd=out / env_name, timeout=600)
        (out / env_name / "stdout.txt").write_bytes(proc.stdout)
        (out / env_name / "stderr.txt").write_bytes(proc.stderr)
        java = java_outputs(case, port, dds, outdir, proc)
        r = eq.compare_run(case, corpus, cobol, java)
        result["runs"].append({"environment": env_name, "ok": r["ok"], "summary": r["summary"],
                               "first_difference": first_difference(r), "stderr": decode_bytes(proc.stderr)[:600],
                               "sysout_classes": sysout_classes(case, cobol.get("SYSOUT", b""), java["SYSOUT"]),
                               "result": r})  # fmt: skip
    result["proven"] = all(x["ok"] for x in result["runs"])
    return result


def coverage_line(cov_report: Optional[dict[str, Any]]) -> str:
    if not cov_report:
        return ""
    p, b = cov_report.get("paragraphs", {}), cov_report.get("branches", {})
    return f"{p.get('covered', '?')}/{p.get('live', '?')} paragraphs, {b.get('covered', '?')}/{b.get('total', '?')} branches"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--port", default=",".join(PORTS))
    ap.add_argument("--case", help="only these of our cases (default: every case a port's programs map to)")
    ap.add_argument("--environments", default="all")
    ap.add_argument("--jdk21", type=Path, help="a JDK 21 for the ports that target Java 21")
    args = ap.parse_args()
    envs = list(ej.ENVIRONMENTS) if args.environments == "all" else args.environments.split(",")
    wanted = set(args.case.split(",")) if args.case else None
    work = args.work.resolve()
    results = []
    for name in args.port.split(","):
        for program, (case_name, _) in PORTS[name]["programs"].items():
            if wanted and case_name not in wanted:
                continue
            jdk = args.jdk21 if PORTS[name]["jdk"] >= 21 else None
            r = judge(name, program, work, envs, jdk)
            results.append(r)
            if "build_error" in r:
                print(f"{name:11} {program} on {case_name}: BUILD FAILED\n    {r['build_error'][:300]}")
                continue
            ok = sum(x["ok"] for x in r["runs"])
            print(f"{name:11} {program} on {case_name}: {'PROVEN' if r['proven'] else 'DIFFERS'} "
                  f"({ok}/{len(r['runs'])} environments; base run covers {coverage_line(r['coverage'])})")  # fmt: skip
            for x in r["runs"]:
                if not x["ok"]:
                    c = x["sysout_classes"]
                    print(f"    {x['environment']}: {x['summary']}\n      first: {x['first_difference']}\n"
                          f"      SYSOUT lines: {c['sign-display']} sign-display, {c['other']} other")  # fmt: skip
    (work / "devin-results.json").write_text(json.dumps(results, indent=1, default=str) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
