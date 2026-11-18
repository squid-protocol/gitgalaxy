#!/usr/bin/env python3
"""
Mutation testing of a proven port: does "proven" mean anything? (#3753 porting loop, #4023 coverage.)

A proof says the port and the COBOL program agree on the case's runs. It proves only what those runs look at. This
tool breaks a proven port on purpose -- one small change at a time (a flipped comparison, `+` for `-`, a constant
off by one, a deleted statement, a changed literal) -- and proves each broken port ("mutant") with the same harness.
A mutant the proof still calls proven SURVIVED: either the change means nothing (an equivalent mutant) or the case
never looks there -- a gap in the case, which a port could get wrong and still be "proven".

    python tests/tools/mutation.py run <case> --work DIR [--jobs 4] [--sample N] [--seed 0] [--ops ROR,AOR,...]
    python tests/tools/mutation.py list <case> [--ops ...]     # the mutants, without running them
    python tests/tools/mutation.py report DIR                  # mutation.md again from mutation.json

`run`:
  1. proves the port as committed (`equivalence.py run <case> --keep DIR/baseline`): it must be proven, or there is
     nothing to measure;
  2. writes every mutant of the port's .java files (outside comments; string and char literals only by LIT);
  3. drops the STILLBORN ones -- a mutant `javac` refuses against the baseline's classpath is caught by the
     compiler, not the proof, so it counts for nothing (about 1 s each);
  4. proves each remaining mutant (`equivalence.py run <case> --port <mutant>`), --jobs at a time, each under a time
     limit (a mutant that loops forever is TIMEOUT: caught, but by the clock);
  5. writes DIR/mutation.json and DIR/mutation.md: the score (killed / (killed + survived)), which runs killed what
     (a mutant only a fault run kills is what the fault runs are for), and every survivor with its line.

A survivor is not automatically a gap: read it. An equivalent mutant (`x >= 0` for `x > 0` where x is never 0 there,
a deleted statement whose effect is overwritten) is noise; anything else is a case to extend (a record, a scenario,
a fault) or, when the COBOL can't reach it either, dead code in the port. Logging statements are never mutated.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import hashlib
import json
import os
import queue
import random
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO_ROOT))
from equivalence_java import (  # noqa: E402
    JAVAC_JVM_OPTIONS,
    JAVAC_OPTIONS,
    PRECOMPILED_MANIFEST,
    PRECOMPILED_OVERLAY_ENV,
    TEST_CLASSPATH,
)
from maven_exe import maven_utf8_env, mvn_executable, run_decoded  # noqa: E402

EQUIVALENCE = TOOLS / "equivalence.py"
CASES = REPO_ROOT / "tests" / "equivalence"
# #4904: timeouts for mvn, javac, and process termination in mutation tooling
MVN_CLASSPATH_TIMEOUT = 600  # seconds: hang guard, well above the slowest honest run (normal mvn compile -X (~30-60s))
JAVAC_MUTANT_TIMEOUT = (
    300  # seconds: hang guard, well above the slowest honest run (normal single mutant javac compile (~5-10s))
)
KILL_WAIT_TIMEOUT = 10  # seconds: wait for process group termination after SIGKILL

# ---- the mutation operators ---------------------------------------------------------------------------------------
# Each operator rewrites one site in code (never inside a comment; string / char literals only by LIT). The binary
# operators are matched with a space on each side: that is how every port writes them, and it keeps generics
# (`List<Dd>`), lambdas (`->`) and shifts out.
OPERATORS = {
    "ROR": "relational: < <= > >= == != swapped for a neighbour",
    "COR": "conditional: && for || and back",
    "NEG": "a whole if / while condition negated",
    "AOR": "arithmetic: + - * / % swapped; ++ for --, += for -=",
    "BDM": "BigDecimal: add / subtract / multiply / negate, and the rounding mode",
    "CON": "an integer constant: 0 -> 1, n -> n + 1",
    "LIT": "a string or char literal: its first character changed",
    "RET": "return true for return false and back",
    "DEL": "one statement deleted (an expression statement, a break or a continue)",
}
_BINARY = {
    "ROR": {"<": ["<=", ">="], "<=": ["<", ">"], ">": [">=", "<="], ">=": [">", "<"], "==": ["!="], "!=": ["=="]},
    "COR": {"&&": ["||"], "||": ["&&"]},
    "AOR": {"+": ["-"], "-": ["+"], "*": ["/"], "/": ["*"], "%": ["*"]},
}
_BINARY_RE = re.compile(r"(?<=\s)(<=|>=|==|!=|&&|\|\||<|>|\+|-|\*|/|%)(?=\s)")
_ASSIGN_OPS = {"++": "--", "--": "++", "+=": "-=", "-=": "+="}
_ASSIGN_RE = re.compile(r"\+\+|--|\+=|-=")
_BIGDECIMAL = {".add(": ".subtract(", ".subtract(": ".add(", ".multiply(": ".divide(", ".negate()": "",
               "RoundingMode.HALF_UP": "RoundingMode.DOWN", "RoundingMode.DOWN": "RoundingMode.HALF_UP",
               "RoundingMode.HALF_EVEN": "RoundingMode.HALF_UP"}  # fmt: skip
_BIGDECIMAL_RE = re.compile("|".join(re.escape(k) for k in sorted(_BIGDECIMAL, key=len, reverse=True)))
_INT_RE = re.compile(r"(?<![\w.])(0x[0-9A-Fa-f]+|\d+)(?![\w.])")
_COND_RE = re.compile(r"\b(if|while)\s*\(")
_RETURN_RE = re.compile(r"\breturn (true|false);")
# an expression statement: a call, an assignment or an increment -- not a declaration, return or throw
_STATEMENT_RE = re.compile(
    r"^(\s*)((?:this\.)?[\w.\[\]]+(?:\(.*\))?(?:\s*[-+*/]?=\s*.+|\+\+|--)?;|break;|continue;)\s*$"
)
_DECLARATION_RE = re.compile(r"^\s*(?:final\s+)?[\w.]+(?:<[^;=]*>)?(?:\[\])*\s+\w+\s*(?:=|;)")
_LOGGING_RE = re.compile(r"^\s*(?:log|LOG|logger|LOGGER)\.")


@dataclass
class Mutant:
    id: str
    file: str  # relative to the port directory
    line: int
    op: str
    before: str  # the line as it was
    after: str  # the line as mutated
    offset: int = 0
    length: int = 0
    replacement: str = ""


def code_mask(text: str) -> tuple[list[bool], list[tuple[int, int]]]:
    """Per character: is it code (not a comment, not inside a literal)? And the literal spans (quotes included)."""
    mask = [True] * len(text)
    literals: list[tuple[int, int]] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
        elif text.startswith('"""', i):  # a text block
            j = text.find('"""', i + 3)
            j = n if j < 0 else j + 3
        elif c in "\"'":
            j = i + 1
            while j < n and text[j] != c and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            j = min(j + 1, n)
            literals.append((i, j))
        else:
            i += 1
            continue
        for k in range(i, j):
            mask[k] = False
        i = j
    return mask, literals


def _line_of(text: str, offset: int) -> tuple[int, int, int]:
    """(1-based line number, line start, line end) of `offset`."""
    start = text.rfind("\n", 0, offset) + 1
    end = text.find("\n", offset)
    return text.count("\n", 0, offset) + 1, start, len(text) if end < 0 else end


def _matching_paren(text: str, mask: list[bool], open_at: int) -> int | None:
    depth = 0
    for k in range(open_at, len(text)):
        if not mask[k]:
            continue
        if text[k] == "(":
            depth += 1
        elif text[k] == ")":
            depth -= 1
            if depth == 0:
                return k
    return None


def mutants_of(rel: str, text: str, ops: set[str]) -> list[Mutant]:
    """Every mutant of one Java file, in source order."""
    mask, literals = code_mask(text)
    sites: list[tuple[str, int, int, str]] = []  # (op, offset, length, replacement)

    def code(m: re.Match[str]) -> bool:
        return all(mask[m.start() : m.end()])

    skip_lines = {_line_of(text, m.start())[0] for m in re.finditer(r"(?m)^\s*(?:import|package)\b|^\s*@", text)}
    for m in _BINARY_RE.finditer(text):
        if not code(m):
            continue
        sites += [(op, m.start(), len(m.group(1)), rep) for op, table in _BINARY.items()
                  for rep in table.get(m.group(1), [])]  # fmt: skip
    sites += [("AOR", m.start(), 2, _ASSIGN_OPS[m.group(0)]) for m in _ASSIGN_RE.finditer(text) if code(m)]
    sites += [("BDM", m.start(), len(m.group(0)), _BIGDECIMAL[m.group(0)]) for m in _BIGDECIMAL_RE.finditer(text)
              if code(m)]  # fmt: skip
    for m in _INT_RE.finditer(text):
        if not code(m):
            continue
        lit = m.group(1)
        if lit.startswith("0x"):  # stays hex, as wide as it was
            rep = f"0x{int(lit, 16) + 1:0{len(lit) - 2}X}"
        else:
            rep = str(int(lit) + 1) if int(lit) else "1"
        sites.append(("CON", m.start(), len(lit), rep))
    for m in _COND_RE.finditer(text):
        if not code(m):
            continue
        close = _matching_paren(text, mask, m.end() - 1)
        if close is not None:
            cond = text[m.end() : close]
            sites.append(("NEG", m.end(), len(cond), f"!({cond})"))
    for m in _RETURN_RE.finditer(text):
        if code(m):
            flip = "false" if m.group(1) == "true" else "true"
            sites.append(("RET", m.start(1), len(m.group(1)), flip))
    for start, end in literals:
        body = text[start + 1 : end - 1]
        if not body or _LOGGING_RE.match(text[_line_of(text, start)[1] : start]):
            continue
        first = body[0]
        if first == "\\":  # an escape: replace the whole escape by a plain character
            width = 6 if body.startswith("\\u") else 2
            sites.append(("LIT", start + 1, width, "X"))
        else:
            sites.append(("LIT", start + 1, 1, "Y" if first == "X" else "X"))
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.rstrip("\n")
        m = _STATEMENT_RE.match(stripped)
        if m and not _DECLARATION_RE.match(stripped) and not _LOGGING_RE.match(stripped):
            body_at = offset + len(m.group(1))
            if all(mask[body_at : offset + len(stripped.rstrip())]) or stripped.strip() in ("break;", "continue;"):
                sites.append(("DEL", body_at, len(m.group(2)), f"/* {m.group(2).replace('*/', '* /')} */"))
        offset += len(line)

    # #5862: a mutant's id names its line by content (the line, and how many identical lines come before it), not by
    # byte offset, so a line added above leaves it alone and a ledger's verdicts can be carried to the moved port
    nth: dict[int, int] = {}
    identical: dict[str, int] = {}
    offset = 0
    for line in text.splitlines(keepends=True):
        nth[offset] = identical.get(line.strip(), 0)
        identical[line.strip()] = nth[offset] + 1
        offset += len(line)

    out: list[Mutant] = []
    seen: set[tuple[int, int, str]] = set()
    for op, at, length, rep in sorted(sites, key=lambda s: (s[1], s[0], s[3])):
        if op not in ops or (at, length, rep) in seen:
            continue
        seen.add((at, length, rep))
        line_no, ls, le = _line_of(text, at)
        if line_no in skip_lines or _LOGGING_RE.match(text[ls:le]):
            continue
        after_line = text[ls:at] + rep + text[at + length : le]
        if op == "NEG" and "\n" in text[at : at + length]:  # a condition over several lines: show its first line
            after_line = text[ls:at] + "!(" + text[at:le]
        where = f"{text[ls:le].strip()}:{nth.get(ls, 0)}:{at - ls}"
        ident = hashlib.sha1(f"{rel}:{where}:{length}:{op}:{rep}".encode(), usedforsecurity=False).hexdigest()[:10]
        out.append(Mutant(ident, rel, line_no, op, text[ls:le].strip(), after_line.strip(), at, length, rep))
    return out


def port_dir(case: str) -> Path:
    """The case's port: its own, or the one it proves on other inputs (`port_from`: a generated-inputs case)."""
    spec = CASES / case / "case.json"
    source = json.loads(spec.read_text(encoding="utf-8")).get("port_from", case) if spec.is_file() else case
    return CASES / source / "port"


def all_mutants(port: Path, ops: set[str], files: str = "**/*.java") -> list[Mutant]:
    """Every mutant of the port's .java files (`files`: a glob under the port, e.g. `service/*.java` for a det
    port's translated program without its cobolrt runtime)."""
    out: list[Mutant] = []
    for f in sorted(port.glob(files)):
        out += mutants_of(f.relative_to(port).as_posix(), f.read_text(encoding="utf-8"), ops)
    return out


def sample(mutants: list[Mutant], n: int | None, seed: int) -> list[Mutant]:
    """At most `n`, spread over the operators (round-robin over each operator's shuffled mutants)."""
    if n is None or n >= len(mutants):
        return mutants
    rng = random.Random(seed)  # noqa: S311 -- a repeatable sample, not a secret
    by_op: dict[str, list[Mutant]] = {}
    for m in mutants:
        by_op.setdefault(m.op, []).append(m)
    for ms in by_op.values():
        rng.shuffle(ms)
    picked: list[Mutant] = []
    while len(picked) < n:
        for op in sorted(by_op):
            if by_op[op] and len(picked) < n:
                picked.append(by_op[op].pop())
    return sorted(picked, key=lambda m: (m.file, m.offset, m.op))


def _link_or_copy(src: str, dst: str) -> str:
    """Hardlink unmodified port files into a mutant work dir, falling back to copy2 across filesystems."""
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)
    return dst


def write_mutant(port: Path, m: Mutant, dest: Path) -> Path:
    """The port with `m` applied, laid out like the port (the harness's --port)."""
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(port, dest, ignore=shutil.ignore_patterns("*.json", "*.md"), copy_function=_link_or_copy)
    f = dest / m.file
    text = f.read_text(encoding="utf-8")
    f.unlink()  # break hardlink before writing mutated file
    f.write_text(text[: m.offset] + m.replacement + text[m.offset + m.length :], encoding="utf-8")
    return dest


# ---- the Java side: the baseline's classpath, for the javac check ----------------------------------------------
def _java_env() -> dict[str, str]:
    import java_target_matrix as jtm

    env = dict(os.environ, JAVA_HOME=jtm._jdk(17))
    env["PATH"] = str(Path(env["JAVA_HOME"]) / "bin") + os.pathsep + env["PATH"]
    return env


def _cached_baseline_classpath(project: Path) -> str | None:
    """Fast path: read the compile classpath from `baseline`'s surefire report or recorded `TEST_CLASSPATH`."""
    classes = project / "target" / "classes"
    if not classes.is_dir():
        return None
    reports = sorted(project.glob("target/surefire-reports/TEST-*.xml"))
    if reports:
        try:
            props = {p.get("name"): p.get("value") for p in ET.parse(reports[0]).iter("property")}  # noqa: S314
            raw = props.get("surefire.test.class.path") or ""
            old = str(reports[0].parents[2])
            entries = [e.replace(old, str(project)) for e in raw.split(os.pathsep) if e]
        except (OSError, ET.ParseError):
            entries = []
    elif (project / TEST_CLASSPATH).is_file():
        entries = [e for e in (project / TEST_CLASSPATH).read_text(encoding="utf-8").split(os.pathsep) if e]
    else:
        return None
    cp_entries = [
        e
        for e in entries
        if not e.replace("\\", "/").endswith("/test-classes") and not e.endswith("test-classes")
    ]
    if not cp_entries or str(classes) not in cp_entries:
        return None
    if not all(Path(e).exists() for e in cp_entries if e.endswith(".jar")):
        return None
    return os.pathsep.join(cp_entries)


def baseline_classpath(baseline: Path, work: Path) -> str:
    """The compile classpath of the baseline's generated project: cached surefire/TEST_CLASSPATH first, else Maven -X."""
    (pom,) = sorted(baseline.glob("java/*/pom.xml"))[:1] or [None]
    if pom is None:
        raise SystemExit(f"no generated project under {baseline / 'java'}")
    project = pom.parent
    cached = _cached_baseline_classpath(project)
    if cached is not None:
        return cached
    scratch = work / "classpath-project"
    if scratch.exists():
        shutil.rmtree(scratch)
    shutil.copytree(project, scratch, ignore=shutil.ignore_patterns("target"))
    try:
        proc = run_decoded([mvn_executable(), "-o", "-X", "-B", "compile"], cwd=scratch, env=maven_utf8_env(_java_env()),
                           check=False, timeout=MVN_CLASSPATH_TIMEOUT)  # fmt: skip
    except subprocess.TimeoutExpired as exc:
        raise SystemExit(
            f"could not read the baseline's classpath (mvn compile timed out after {MVN_CLASSPATH_TIMEOUT}s)"
        ) from exc
    m = re.search(r"-classpath (\S+)", proc.stdout)
    if proc.returncode != 0 or not m:
        raise SystemExit(f"could not read the baseline's classpath (mvn exit {proc.returncode})")
    return m.group(1).replace(str(scratch / "target" / "classes"), str(project / "target" / "classes"))


def _write_overlay_manifest(out: Path, mutant_port: Path, compiled: list[Path] | None = None) -> None:
    """The overlay's manifest: the sources compiled into `out` (default: all of the port), by sha256. Only these:
    `_adopt_precompiled_overlay` drops the baseline's classes of every source listed, so a source listed but not
    compiled would leave its classes missing."""
    sources = {
        p.relative_to(mutant_port).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(compiled if compiled is not None else mutant_port.rglob("*.java"))
    }
    (out / PRECOMPILED_MANIFEST).write_text(
        json.dumps({"javac_options": JAVAC_OPTIONS, "sources": sources}) + "\n", encoding="utf-8"
    )


RUNTIME_DIR = "cobolrt"  # the port's copy of the runtime: never depends on the program (#8599)


def mutant_sources(mutant_port: Path, mutated: str, classpath: str) -> list[Path]:
    """The sources a mutant's javac check compiles (#8599). A mutant outside the runtime (`RUNTIME_DIR`) compiles the
    program's files only, against the baseline's classes on `classpath` (they hold the runtime, built from the same
    bytes): the runtime never refers to the program, so no constant javac inlines across files can go stale. Every
    program file is compiled, not just the mutated one, since a mutated constant is inlined into its callers. A
    mutant inside the runtime, or a port without one, compiles everything, as before."""
    every = sorted(mutant_port.rglob("*.java"))
    if Path(mutated).parts[:1] == (RUNTIME_DIR,) or not classpath:
        return every
    program = [p for p in every if p.relative_to(mutant_port).parts[:1] != (RUNTIME_DIR,)]
    return program if program and len(program) < len(every) else every


def compiles(mutant_port: Path, classpath: str, out: Path, only_file: str | None = None) -> tuple[bool, str]:
    import javac_server  # noqa: PLC0415

    out.mkdir(parents=True, exist_ok=True)
    single = mutant_port / only_file if only_file else None
    if single is not None and single.is_file() and classpath:
        compiled = mutant_sources(mutant_port, only_file or "", classpath)
        sp = ("-sourcepath", str(mutant_port))
    else:
        compiled = sorted(mutant_port.rglob("*.java"))
        sp = ()
    sources = [str(p) for p in compiled]
    javac_exe = str(Path(_java_env()["JAVA_HOME"]) / "bin" / "javac")
    try:
        proc = javac_server.javac(
            [javac_exe, *JAVAC_OPTIONS, "-d", str(out), "-cp", classpath, *sp, *sources],
            capture_output=True, text=True, encoding="utf-8", check=False, timeout=JAVAC_MUTANT_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return False, f"javac timed out after {JAVAC_MUTANT_TIMEOUT}s"
    errors = [x for x in proc.stderr.splitlines() if ": error: " in x]
    if proc.returncode == 0:
        _write_overlay_manifest(out, mutant_port, compiled)
    return proc.returncode == 0, (errors[0].split(": error: ", 1)[1] if errors else proc.stderr.strip()[:200])


JAVAC_SESSION_DONE = "@@JAVAC-DONE@@"
JAVAC_SESSION_SRC = f"""import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import javax.tools.*;

public class MutantJavacSession {{
    public static void main(String[] args) throws Exception {{
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        if (compiler == null) {{
            System.exit(2);
        }}
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
        String outDir;
        while ((outDir = in.readLine()) != null && !outDir.equals("quit")) {{
            String cp = in.readLine();
            if (cp == null) break;
            List<String> sources = new ArrayList<>();
            String s;
            while ((s = in.readLine()) != null && !s.isEmpty()) {{
                sources.add(s);
            }}
            DiagnosticCollector<JavaFileObject> diags = new DiagnosticCollector<>();
            boolean ok;
            try (StandardJavaFileManager fm = compiler.getStandardFileManager(null, Locale.ROOT, StandardCharsets.UTF_8)) {{
                List<String> opts = List.of("-g", "-parameters", "--release", "17", "-encoding", "UTF-8", "-nowarn", "-d", outDir, "-cp", cp);
                Iterable<? extends JavaFileObject> units = fm.getJavaFileObjectsFromStrings(sources);
                ok = Boolean.TRUE.equals(compiler.getTask(null, fm, diags, opts, null, units).call());
            }}
            String firstError = "";
            if (!ok) {{
                for (Diagnostic<? extends JavaFileObject> d : diags.getDiagnostics()) {{
                    if (d.getKind() == Diagnostic.Kind.ERROR) {{
                        firstError = d.getMessage(Locale.ROOT).replace('\\r', ' ').replace('\\n', ' ');
                        break;
                    }}
                }}
            }}
            System.out.println("{JAVAC_SESSION_DONE} " + (ok ? "0" : "1") + " " + firstError);
            System.out.flush();
        }}
    }}
}}
"""


def _javac_session_bin(env: dict[str, str]) -> Path | None:
    java_home = env.get("JAVA_HOME", "")
    key = hashlib.sha256((java_home + JAVAC_SESSION_SRC).encode()).hexdigest()[:12]
    target = Path(tempfile.gettempdir()) / f"gitgalaxy-javac-session-{key}"
    if (target / "MutantJavacSession.class").is_file():
        return target
    build = Path(tempfile.mkdtemp(prefix="javac-session-"))
    (build / "MutantJavacSession.java").write_text(JAVAC_SESSION_SRC, encoding="utf-8")
    javac = str(Path(java_home) / "bin" / "javac") if java_home else "javac"
    proc = subprocess.run([javac, *JAVAC_JVM_OPTIONS, "-encoding", "UTF-8", "-d", str(build),  # noqa: S603
                           str(build / "MutantJavacSession.java")], env=env, capture_output=True, text=True, encoding="utf-8", check=False)  # fmt: skip
    if proc.returncode != 0:
        shutil.rmtree(build, ignore_errors=True)
        return None
    try:
        build.rename(target)
    except OSError:
        shutil.rmtree(build, ignore_errors=True)
    return target if (target / "MutantJavacSession.class").is_file() else None


class JavacSession:
    """Persistent warm `javax.tools.JavaCompiler` worker so compiling N mutants pays JVM startup once per worker."""

    def __init__(self, bin_dir: Path, env: dict[str, str]) -> None:
        java_home = env.get("JAVA_HOME", "")
        java = str(Path(java_home) / "bin" / "java") if java_home else "java"
        jvm_flags = [x[2:] for x in JAVAC_JVM_OPTIONS if x.startswith("-J")]
        self.proc = subprocess.Popen([java, *jvm_flags, "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(bin_dir), "MutantJavacSession"],  # noqa: S603
                                     env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, encoding="utf-8", bufsize=1)  # fmt: skip
        self._lines: queue.Queue[str | None] = queue.Queue()
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            self._lines.put(line)
        self._lines.put(None)

    def compile(self, mutant_port: Path, classpath: str, out: Path,
                compiled: list[Path] | None = None) -> tuple[bool, str] | None:  # fmt: skip
        out.mkdir(parents=True, exist_ok=True)
        compiled = compiled if compiled is not None else sorted(mutant_port.rglob("*.java"))
        sources = [str(p) for p in compiled]
        assert self.proc.stdin is not None
        try:
            self.proc.stdin.write(f"{out}\n{classpath}\n" + "\n".join(sources) + "\n\n")
            self.proc.stdin.flush()
        except OSError:
            return None
        deadline = time.monotonic() + JAVAC_MUTANT_TIMEOUT
        while True:
            try:
                line = self._lines.get(timeout=max(0.0, deadline - time.monotonic()))
            except queue.Empty:
                self.proc.kill()
                return False, f"javac timed out after {JAVAC_MUTANT_TIMEOUT}s"
            if line is None:
                return None
            if line.startswith(JAVAC_SESSION_DONE):
                rest = line[len(JAVAC_SESSION_DONE) + 1 :].rstrip("\r\n")
                code, _, msg = rest.partition(" ")
                ok = code == "0"
                if ok:
                    _write_overlay_manifest(out, mutant_port, compiled)
                return ok, msg

    def close(self) -> None:
        try:
            assert self.proc.stdin is not None
            self.proc.stdin.write("quit\n")
            self.proc.stdin.flush()
            self.proc.stdin.close()
            self.proc.wait(timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            self.proc.kill()
            self.proc.wait()


# ---- proving one mutant ---------------------------------------------------------------------------------------------
def prove(case: str, port: Path | None, work: Path, timeout: float, extra: tuple[str, ...] = (),
          env: dict[str, str] | None = None) -> dict[str, Any]:  # fmt: skip
    """`equivalence.py run <case> [--port]` in its own process group; the report, or TIMEOUT."""
    argv = [sys.executable, str(EQUIVALENCE), "run", case, "--keep", str(work)]
    if port is not None:
        argv += ["--port", str(port)]
    argv += list(extra)
    start = time.time()
    with (work.parent / f"{work.name}.log").open("w", encoding="utf-8") as log:
        proc = subprocess.Popen(argv, cwd=REPO_ROOT, stdout=log, stderr=subprocess.STDOUT,  # noqa: S603
                                env=env, start_new_session=True)  # fmt: skip
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if hasattr(os, "killpg"):
                os.killpg(proc.pid, signal.SIGKILL)
            else:  # Windows: no process groups
                proc.kill()
            with contextlib.suppress(subprocess.TimeoutExpired):
                proc.wait(timeout=KILL_WAIT_TIMEOUT)
            return {"verdict": "timeout", "seconds": round(time.time() - start)}
    report_file = work / "report.json"
    if not report_file.is_file():
        return {"verdict": "error", "seconds": round(time.time() - start), "why": f"no report (exit {proc.returncode})"}
    report = json.loads(report_file.read_text(encoding="utf-8"))
    return {"verdict": "proven" if report.get("proven") else "refuted", "seconds": round(time.time() - start),
            "killed_by": killers(report), "report": report}  # fmt: skip


def killers(report: dict[str, Any]) -> list[str]:
    """Which of the proof's runs saw the mutant: `main`, a fault run's name, a CICS scenario, a CALL, or `java`
    (the port crashed or failed to build)."""
    if report.get("java_failed"):
        return ["java"]
    if report.get("kind") == "call":
        return [f"call {d['record']}" for d in report["outputs"]["CALLS"].get("diffs", [])]
    if report.get("kind") == "cics":
        out = []
        for name, o in report.get("outputs", {}).items():
            fired = o.get("fired")
            sql = o.get("sql") or {}  # #4507: a Db2 table left different, or a statement Db2 answered differently
            if (o["equal"] != o["records"] or o.get("diffs") or (fired and fired["cobol"] != fired["java"])
                    or o.get("files") or sql.get("equal") != sql.get("statements")):  # fmt: skip
                out.append(name)
        return out
    out = ["main"] if not all(e.get("ok") for e in report.get("environments", [{"ok": True}])) else []
    return out + [f["name"] for f in report.get("faults", []) if not f.get("ok")]


_ORIGINAL_PROVE = prove


class _MutantWorker:
    """One persistent worker owning a warm `JvmSession` (`--mutant-session`) and a private copy of `target/classes`."""

    def __init__(self, worker_id: int, work: Path, ctx: _DirectContext) -> None:
        self.ctx = ctx
        self.classes_dir = work / f".worker-{worker_id}" / "classes"
        self.session: Any = None
        self.cp = ""

    def _ensure(self) -> Any:
        if self.session is not None:
            return self.session
        import equivalence_java as ej

        if self.classes_dir.exists():
            shutil.rmtree(self.classes_dir, ignore_errors=True)
        shutil.copytree(self.ctx.base_classes, self.classes_dir)
        started = ej.start_mutant_session(self.ctx.project, self.ctx.env_default, cwd=self.classes_dir.parent)
        if started is None:
            return None
        self.session, _, test_classes = started
        self.cp = os.pathsep.join([str(self.classes_dir), str(test_classes)])
        return self.session

    def reset(self) -> None:
        if self.session is not None:
            self.session.close()
            self.session = None

    def swap_and_restore(self, mutant_classes: Path) -> list[tuple[Path, bool]]:
        """Ensure the worker JVM & classes copy exist, then install `mutant_classes` into `self.classes_dir`."""
        if self._ensure() is None:
            raise RuntimeError("mutant session unavailable")
        rels = [p.relative_to(mutant_classes) for p in mutant_classes.rglob("*.class")]
        touched: set[Path] = set()
        stems = {(r.parent, r.name.split("$", 1)[0].removesuffix(".class")) for r in rels}
        for parent, stem in stems:
            wdir = self.classes_dir / parent
            if wdir.is_dir():
                for existing in list(wdir.glob(f"{stem}.class")) + list(wdir.glob(f"{stem}$*.class")):
                    touched.add(existing.relative_to(self.classes_dir))
                    existing.unlink()
        for r in rels:
            touched.add(r)
            dest = self.classes_dir / r
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(mutant_classes / r, dest)
        return [(r, (self.ctx.base_classes / r).is_file()) for r in touched]

    def rollback(self, entries: list[tuple[Path, bool]]) -> None:
        for r, existed in entries:
            dest = self.classes_dir / r
            if existed:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(self.ctx.base_classes / r, dest)
            else:
                dest.unlink(missing_ok=True)


class _DirectContext:
    """In-process Batch / CICS runner backed by persistent `--mutant-session` JVMs (fast+one-jvm non-Db2/non-IMS)."""

    def __init__(self, *, kind: str, case: dict[str, Any], corpus: Path, project: Path, base_classes: Path,
                 env_default: dict[str, str], base_jvm_flags: str, shell: dict[str, str],
                 inputs: Path, faults: list[dict[str, Any]] | None = None,
                 cobol_batch: dict[str, bytes] | None = None, cobol_faults: dict[str, dict[str, bytes]] | None = None,
                 fault_props: dict[str, str] | None = None, cics_in: Path | None = None, cics_cobol_work: Path | None = None,
                 cics_files: list[dict[str, Any]] | None = None, cics_cobol: dict[str, Any] | None = None,
                 cics_shape: Any = None, cics_ret_read: Any = None) -> None:  # fmt: skip
        self.kind = kind
        self.case = case
        self.corpus = corpus
        self.project = project
        self.base_classes = base_classes
        self.env_default = env_default
        self.base_jvm_flags = base_jvm_flags
        self.shell = shell
        self.inputs = inputs
        self.faults = faults or []
        self.cobol_batch = cobol_batch or {}
        self.cobol_faults = cobol_faults or {}
        self.fault_props = fault_props or {}
        self.cics_in = cics_in
        self.cics_cobol_work = cics_cobol_work
        self.cics_files = cics_files or []
        self.cics_cobol = cics_cobol or {}
        self.cics_shape = cics_shape
        self.cics_ret_read = cics_ret_read

    @classmethod
    def build(cls, case_name: str, case_file: Path | None, baseline_work: Path, base: dict[str, Any],
              one_jvm: bool, full: bool) -> _DirectContext | None:  # fmt: skip
        if full or not one_jvm or prove is not _ORIGINAL_PROVE:
            return None
        report = base.get("report") or {}
        if report.get("java") != "ported":
            return None
        import equivalence as eq
        import equivalence_java as ej
        import mainframe_corpus as mc

        case = eq.load_case(case_name, case_file)
        if (case.get("db2") or case.get("ims") or case.get("entries") or case.get("environments")
                or case.get("kind") in ("job", "call")):  # fmt: skip
            return None
        (pom,) = sorted((baseline_work / "java").glob("*/pom.xml"))[:1] or [None]
        if pom is None:
            return None
        project = pom.parent
        shell = _java_env()
        if ej._direct_parts(project, shell) is None:
            return None
        (corpus_entry,) = mc.select([case["corpus"]])
        corpus = mc.require_clone(corpus_entry)
        env0 = ej.environment("default")
        base_flags = f"{ej.JVM_SHORT_RUN_FLAGS} {ej.jvm_args(env0)} {ej.data_charset_arg(case)}".strip()
        base_classes = (project / "target" / "classes").resolve()
        if not base_classes.is_dir():
            return None

        if case.get("kind") == "cics":
            import equivalence_cache
            import equivalence_cics as ec
            import equivalence_inputs
            from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir

            cics_in = baseline_work / "java" / "in"
            cobol_work = baseline_work / "cobol"
            if not (cics_in / "scenarios.json").is_file() or not (cobol_work / "refused.json").is_file():
                return None
            ir = load_galaxy_ir(equivalence_cache.scan_db(corpus, baseline_work / "scan"))
            symbols = ec.install_symbols(case.get("install_symbols"))
            files = ec.stub_files(ir, case["program_source"], case.get("datasets"), symbols)
            for extra in case.get("programs", []):
                files += [f for f in ec.stub_files(ir, extra["program_source"], case.get("datasets"), symbols)
                          if f["file"] not in {x["file"] for x in files}]  # fmt: skip
            case = equivalence_inputs.prepare_cics_case(case, corpus, files)
            refused = set(json.loads((cobol_work / "refused.json").read_text(encoding="utf-8")))
            refused.update((report.get("refused") or {}).keys())
            kept = [sc for sc in case["scenarios"] if sc["name"] not in refused]
            for sc in kept:  # the baseline's run_cobol_cics set prefix_x6 on its own copy of the case: set it here too
                if sc.get("prefix_x6"):
                    continue
                rc_f = cobol_work / "scenarios" / sc["name"] / "rc"
                said_f = cobol_work / "scenarios" / sc["name"] / "stdout.txt"
                if not (rc_f.is_file() and said_f.is_file()):
                    continue
                said = said_f.read_text(encoding="latin-1")
                rc_text = rc_f.read_text().strip()
                if rc_text == "1" and ec.PERFORM_DEPTH in said:
                    sc["prefix_x6"] = ec.PERFORM_DEPTH
                elif rc_text == "98" and (x6 := ec.judged_refusal(said)):
                    sc["prefix_x6"] = x6
            case = {**case, "scenarios": kept}
            src = project / "src/main/java"
            svc = ej._service_class(case["program"])
            svc_file = next(src.rglob(f"{svc}.java"))
            ca_cls = ec.commarea_class(case, src, svc_file)
            shape = ec.dto_shape(src, ca_cls, svc_file) if ca_cls else {}
            ca_fields = ec.commarea_fields(corpus, case)
            ret_read = ec.commarea_fields(corpus, case, occurrences=True) or ec.return_fields(corpus, case, True)
            cobol = {sc["name"]: ec.outputs(cobol_work / "scenarios" / sc["name"] / "out", case, corpus,
                                            ca_fields or ec.return_fields(corpus, case, True))
                     for sc in kept}  # fmt: skip
            return cls(
                kind="cics", case=case, corpus=corpus, project=project, base_classes=base_classes,
                env_default=env0, base_jvm_flags=base_flags, shell=shell, inputs=cics_in,
                cics_in=cics_in, cics_cobol_work=cobol_work, cics_files=files, cics_cobol=cobol,
                cics_shape=shape, cics_ret_read=ret_read,
            )

        inputs = baseline_work / "cobol"
        if not inputs.is_dir():
            return None
        cobol = eq.run_cobol(case, corpus, inputs)
        faults = eq.selected_faults(case, "all")
        cobol_faults: dict[str, dict[str, bytes]] = {}
        fault_props: dict[str, str] = {}
        stage = baseline_work / "_fault_inputs"
        stage.mkdir(parents=True, exist_ok=True)
        enc = eq.equivalence_common.data_encoding(case)
        for f in faults:
            f_cobol = baseline_work / "faults" / f["name"] / "cobol"
            if not f_cobol.is_dir():
                return None
            cobol_faults[f["name"]] = eq.run_cobol(case, corpus, f_cobol, f)
            fdir = stage / f["name"]
            fdir.mkdir(parents=True, exist_ok=True)
            (fdir / "fault.plan").write_text(eq.fault_plan(f), encoding="ascii")
            fp = f"-Dgitgalaxy.faults.plan={fdir / 'fault.plan'}"
            if f.get("parm") is not None:
                fp += f" -Dequivalence.parm={ej.run_parm(eq.run_parm(case, f))}"
            if f.get("sysin") is not None:
                sysin = f["sysin"] if f["sysin"].endswith("\n") else f["sysin"] + "\n"
                (fdir / "SYSIN.in").write_bytes(sysin.encode(enc))
                fp += f" -Dequivalence.sysin={fdir / 'SYSIN.in'}"
            fault_props[f["name"]] = fp
        return cls(
            kind="batch", case=case, corpus=corpus, project=project, base_classes=base_classes,
            env_default=env0, base_jvm_flags=base_flags, shell=shell, inputs=inputs,
            faults=faults, cobol_batch=cobol, cobol_faults=cobol_faults, fault_props=fault_props,
        )

    def _run_batch_area(self, worker: _MutantWorker, m_id: str, area: Path, timeout: float,
                        extra_props: str = "") -> tuple[int, dict[str, bytes] | None]:  # fmt: skip
        datasets, out = area / "datasets", area / "out"
        datasets.mkdir(parents=True, exist_ok=True)
        out.mkdir(parents=True, exist_ok=True)
        for dd, spec in self.case["datasets"].items():
            if "input" in spec and not spec.get("entity"):
                shutil.copy(self.inputs / f"{dd}.in", datasets / dd)
        sysout = out / "SYSOUT"
        sysout.unlink(missing_ok=True)
        (out / "FAULTS").unlink(missing_ok=True)
        props = extra_props
        if self.case.get("mvs_step") is not None:
            props = f"{props} -Dgitgalaxy.mvs.step={self.case['mvs_step']}"
        if self.case.get("sysin") is not None and "-Dequivalence.sysin=" not in props:
            props = f"{props} -Dequivalence.sysin={self.inputs / 'SYSIN.in'}"
        argline = (
            f"{self.base_jvm_flags} -Dequivalence.in={self.inputs} -Dequivalence.out={out} "
            f"-Dequivalence.datasets={datasets} -Dgitgalaxy.sysout={sysout} {props}"
        ).strip()
        session = worker._ensure()
        if session is None:
            return -1, None
        proc = session.run(argline, timeout, epoch=m_id, cp=worker.cp)
        if proc.returncode == 124:
            worker.reset()
            return 124, None
        if "the session JVM" in proc.stderr:
            worker.reset()
            return -1, None
        if proc.returncode != 0:
            return 1, None
        outs = {dd: out / f"{dd}.out" for dd, spec in self.case["datasets"].items() if spec.get("compare")}
        for extra in ("RETURN-CODE", "ABEND", "FAULTS"):
            outs[extra] = out / extra
        read = {dd: f.read_bytes() for dd, f in outs.items() if f.is_file()}
        read["SYSOUT"] = sysout.read_bytes() if sysout.is_file() else b""
        for extra in ("RETURN-CODE", "ABEND"):
            if extra in read:
                read[extra] = read[extra].strip()
        return 0, read

    def run_mutant(self, worker: _MutantWorker, m: Mutant, mw: Path, limit: float, keep: bool,
                   fault_ranks: dict[str, int]) -> dict[str, Any] | None:  # fmt: skip
        classes = mw / "classes"
        if not classes.is_dir():
            return None
        started = time.time()
        deadline = time.monotonic() + limit
        try:
            rollback = worker.swap_and_restore(classes)
        except (OSError, RuntimeError):
            worker.reset()
            return None
        poisoned = False
        try:
            proof = mw / "proof"
            if self.kind == "cics":
                out, datasets = proof / "java" / "out", proof / "java" / "datasets"
                out.mkdir(parents=True, exist_ok=True)
                datasets.mkdir(parents=True, exist_ok=True)
                session = worker._ensure()
                if session is None:
                    return None
                argline = (
                    f"{self.base_jvm_flags} -Dequivalence.in={self.cics_in} "
                    f"-Dequivalence.out={out} -Dequivalence.datasets={datasets}"
                )
                proc = session.run(argline, limit, epoch=m.id, cp=worker.cp)
                secs = round(time.time() - started)
                if proc.returncode == 124:
                    poisoned = True
                    worker.reset()
                    return {"verdict": "timeout", "seconds": secs}
                if "the session JVM" in proc.stderr:
                    poisoned = True
                    worker.reset()
                    return None
                if proc.returncode != 0:
                    return {"verdict": "killed", "seconds": secs, "killed_by": ["java"]}
                import equivalence_cics as ec

                assert self.cics_cobol_work is not None
                java = ec._java_events(self.case, out, self.cics_shape, self.cics_ret_read)
                ok, outs = ec.evaluate_cics_outputs(
                    self.case, self.corpus, self.cics_cobol_work, out, self.cics_files,
                    self.cics_cobol, java, quiet=True,
                )
                kb = [] if ok else killers({"kind": "cics", "outputs": outs})
                return {"verdict": "survived" if ok else "killed", "seconds": secs, "killed_by": kb}

            import equivalence as eq

            rc, java = self._run_batch_area(worker, m.id, proof / "java", max(1.0, deadline - time.monotonic()))
            secs = round(time.time() - started)
            if rc == 124:
                poisoned = True
                return {"verdict": "timeout", "seconds": secs}
            if rc < 0:
                poisoned = True
                return None
            if rc != 0:
                return {"verdict": "killed", "seconds": secs, "killed_by": ["java"]}
            assert java is not None
            if not eq.compare_run(self.case, self.corpus, self.cobol_batch, java)["ok"]:
                return {"verdict": "killed", "seconds": secs, "killed_by": ["main"]}
            ordered = sorted(enumerate(self.faults), key=lambda it: (-fault_ranks.get(it[1]["name"], 0), it[0]))
            for _, f in ordered:
                rem = deadline - time.monotonic()
                if rem <= 0:
                    poisoned = True
                    worker.reset()
                    return {"verdict": "timeout", "seconds": round(time.time() - started)}
                f_area = proof / "java" / "faults" / f["name"]
                f_props = f"{self.fault_props[f['name']]} -Dgitgalaxy.faults.log={f_area / 'out' / 'FAULTS'}"
                rc, f_java = self._run_batch_area(worker, m.id, f_area, rem, f_props)
                secs = round(time.time() - started)
                if rc == 124:
                    poisoned = True
                    return {"verdict": "timeout", "seconds": secs}
                if rc < 0:
                    poisoned = True
                    return None
                if rc != 0:
                    return {"verdict": "killed", "seconds": secs, "killed_by": ["java"]}
                assert f_java is not None
                f_java.setdefault("FAULTS", b"")
                if not eq.compare_run(self.case, self.corpus, self.cobol_faults[f["name"]], f_java, fault=f)["ok"]:
                    return {"verdict": "killed", "seconds": secs, "killed_by": [f["name"]]}
            return {"verdict": "survived", "seconds": round(time.time() - started), "killed_by": []}
        finally:
            if poisoned:
                shutil.rmtree(worker.classes_dir.parent, ignore_errors=True)
            else:
                try:
                    worker.rollback(rollback)
                except OSError:
                    worker.reset()
                    shutil.rmtree(worker.classes_dir.parent, ignore_errors=True)


# ---- the in-process time limit (#8599) ---------------------------------------------------------------------------
DIRECT_LIMIT_FLOOR = 30.0  # seconds: never less, however fast the unmutated port runs in process
DIRECT_LIMIT_FACTOR = 5.0  # x the slowest worker's run of the unmutated port (PIT's default is 1.25x + 4 s)
CALIBRATE_ID = "calibrate-unmutated"


def direct_limit(limit: float, calib: list[float]) -> float:
    """The time limit of one in-process mutant proof: `DIRECT_LIMIT_FACTOR` x the slowest calibration run (the
    unmutated port, in process, on a warm worker), at least `DIRECT_LIMIT_FLOOR`, never more than `limit` (the
    separate-run limit, `max(300, 3 x baseline)`). A mutant that loops for ever used to hold its worker for the whole
    `limit`: 201 timeouts in the 2026-11-18 ledgers, 300 s or more each. Timeout and killed are both caught."""
    if not calib:
        return limit
    return min(limit, max(DIRECT_LIMIT_FLOOR, DIRECT_LIMIT_FACTOR * max(calib)))


def calibrate(direct: _DirectContext, worker: _MutantWorker, mw: Path, limit: float) -> float | None:
    """Run the unmutated port (an empty overlay) on the worker; its seconds, or None when it does not survive: the
    in-process runner would then disagree with the proven baseline, and none of its verdicts can be trusted. Also
    warms the worker's JVM, which the first mutant paid for before."""
    (mw / "classes").mkdir(parents=True, exist_ok=True)
    unmutated = Mutant(id=CALIBRATE_ID, file="", line=0, op="none", before="", after="")
    started = time.monotonic()
    try:
        res = direct.run_mutant(worker, unmutated, mw, limit, False, {})
    finally:
        seconds = time.monotonic() - started
        shutil.rmtree(mw, ignore_errors=True)
    return seconds if res is not None and res["verdict"] == "survived" else None


# ---- the run -----------------------------------------------------------------------------------------------------
def run(case: str, work: Path, jobs: int, n: int | None, seed: int, ops: set[str], timeout: float | None,
        keep: bool, full: bool = False, only: Path | None = None, case_file: Path | None = None,
        port: Path | None = None, files: str = "**/*.java",
        select: Callable[[list[Mutant]], list[Mutant]] | None = None, one_jvm: bool = False) -> dict[str, Any]:  # fmt: skip
    """`port`: a port outside the case (#4628: the det port, `det_port.py run --translate-only`) instead of the
    committed one -- the baseline proves it too; `files`: the port's files to mutate; `select`: drops the mutants
    out of scope (det_mutation.py: entry points the case's kind never calls) before sampling."""
    work.mkdir(parents=True, exist_ok=True)
    given = port is not None
    port = port if port is not None else port_dir(case)
    started = time.time()
    print(f"{case}: proving the port as {'given' if given else 'committed'} (baseline)", flush=True)
    case_arg = ("--case-file", str(case_file)) if case_file else ()  # #4049: a candidate case
    base = prove(case, port if given else None, work / "baseline", timeout=3600, extra=case_arg)
    if base["verdict"] != "proven":  # the committed port must be proven
        raise SystemExit(f"{case}: the committed port is not proven ({base['verdict']}); nothing to measure")
    limit = timeout or max(300.0, 3 * base["seconds"])
    classpath = baseline_classpath(work / "baseline", work)
    # fast (the default): each mutant reuses the baseline's COBOL side and generated project, compiles only the
    # port, and stops at the first run that differs -- the same verdict as --full, which re-proves from scratch
    # (--one-jvm: and all the runs of a proof in one JVM, each on a fresh Spring context; judged against --full by
    # `compare` before it is trusted, hence its own mode name)
    fast = case_arg + (() if full else ("--reuse", str(work / "baseline"), "--first-difference")
                       + (("--one-jvm",) if one_jvm else ()))  # fmt: skip
    mode = "full" if full else "fast+one-jvm" if one_jvm else "fast"
    every = all_mutants(port, ops, files)
    if select is not None:
        every = select(every)
    chosen = sample(every, n, seed)
    if only is not None:  # the mutants another run judged (e.g. a --full reference), to compare against it
        judged = {r["id"] for r in json.loads((only / "mutation.json").read_text(encoding="utf-8"))["results"]
                  if r["verdict"] != "pending"}  # fmt: skip
        chosen = [m for m in every if m.id in judged]
    print(f"{case}: {len(every)} mutants, {len(chosen)} chosen; baseline {base['seconds']} s, limit {limit:.0f} s",
          flush=True)  # fmt: skip
    results: dict[str, dict[str, Any]] = {}

    java_env = _java_env()
    javac_bin = _javac_session_bin(java_env)
    compile_lock = threading.Lock()
    javac_sessions: list[JavacSession] = []
    local_javac = threading.local()

    def javac(m: Mutant) -> tuple[bool, str]:
        mdir = write_mutant(port, m, work / "mutants" / m.id / "port")
        out_dir = work / "mutants" / m.id / "classes"
        if javac_bin is not None:
            sess = getattr(local_javac, "sess", None)
            if sess is None:
                sess = JavacSession(javac_bin, java_env)
                local_javac.sess = sess
                with compile_lock:
                    javac_sessions.append(sess)
            compiled = sess.compile(mdir, classpath, out_dir, mutant_sources(mdir, m.file, classpath))
            if compiled is not None:
                return compiled
            with compile_lock:
                if sess in javac_sessions:
                    javac_sessions.remove(sess)
            local_javac.sess = None
            sess.close()
        return compiles(mdir, classpath, out_dir, only_file=m.file)

    live: list[Mutant] = []
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:  # (javac, --jobs at a time)
            for m, (ok, why) in zip(chosen, pool.map(javac, chosen), strict=True):
                if ok:
                    live.append(m)
                else:
                    results[m.id] = {"verdict": "stillborn", "why": why}
    finally:
        for sess in javac_sessions:
            sess.close()
    print(f"{case}: {len(chosen) - len(live)} stillborn (javac), {len(live)} to prove, {jobs} at a time", flush=True)

    direct = _DirectContext.build(case, case_file, work / "baseline", base, one_jvm, full)
    calib: list[float] = []  # #8599: each in-process worker's run of the unmutated classes, seconds
    claim_text = _baseline_claim(work)
    kill_counts: Counter[str] = Counter()
    state_lock = threading.Lock()
    work_iter = iter(live)
    done = 0
    last_save = time.monotonic()

    def fallback_prove(m: Mutant) -> dict[str, Any]:
        mw = work / "mutants" / m.id
        with state_lock:
            order = ",".join(k for k, _ in kill_counts.most_common() if k not in ("main", "java"))
        env = dict(os.environ, **{PRECOMPILED_OVERLAY_ENV: str(mw / "classes")})
        if order:
            env["GITGALAXY_FAULTS_ORDER"] = order
        res = prove(case, mw / "port", mw / "proof", limit, fast, env=env)
        res.pop("report", None)
        res["verdict"] = {"proven": "survived", "refuted": "killed"}.get(res["verdict"], res["verdict"])
        return res

    def run_worker(worker_id: int) -> None:
        nonlocal done, last_save
        worker = _MutantWorker(worker_id, work, direct) if direct is not None else None
        if worker is not None and direct is not None and live:
            seconds = calibrate(direct, worker, work / "mutants" / f".calibrate-{worker_id}", limit)
            if seconds is None:  # the in-process runner does not reproduce the proven baseline: the slow path only
                print(f"{case}: worker {worker_id}: the unmutated port does not survive in process: "
                      "proving its mutants as separate runs", flush=True)  # fmt: skip
                worker.reset()
                shutil.rmtree(worker.classes_dir.parent, ignore_errors=True)
                worker = None
            else:
                with state_lock:
                    calib.append(seconds)
        try:
            while True:
                with state_lock:
                    m = next(work_iter, None)
                    ranks = dict(kill_counts)
                if m is None:
                    break
                res: dict[str, Any] | None = None
                mw = work / "mutants" / m.id
                if worker is not None and direct is not None:
                    with state_lock:
                        m_limit = direct_limit(limit, calib)
                    res = direct.run_mutant(worker, m, mw, m_limit, keep, ranks)
                    if res is not None and res["verdict"] == "timeout":
                        res["limit"] = round(m_limit)
                    if res is None:
                        shutil.rmtree(mw / "proof", ignore_errors=True)
                if res is None:
                    res = fallback_prove(m)
                if not keep and res["verdict"] in ("killed", "timeout"):
                    shutil.rmtree(mw / "proof", ignore_errors=True)
                with state_lock:
                    results[m.id] = res
                    done += 1
                    for kb in res.get("killed_by", []):
                        kill_counts[kb] += 1
                    print(f"  [{done}/{len(live)}] {m.op} {m.file}:{m.line} {res['verdict']} "
                          f"{','.join(res.get('killed_by', []))[:60]}", flush=True)  # fmt: skip
                    now = time.monotonic()
                    if now - last_save >= 2.0 or done % 10 == 0:
                        last_save = now
                        _save(work, case, base, every, chosen, results, started, seed, mode, claim=claim_text)
        finally:
            if worker is not None:
                worker.reset()
                shutil.rmtree(worker.classes_dir.parent, ignore_errors=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(jobs, max(len(live), 1)))) as pool:
        futs = [pool.submit(run_worker, i) for i in range(max(1, min(jobs, max(len(live), 1))))]
        for fut in concurrent.futures.as_completed(futs):
            fut.result()
    return _save(work, case, base, every, chosen, results, started, seed, mode, claim=claim_text)


def _baseline_claim(work: Path) -> str | None:
    log = work / "baseline.log"
    if not log.is_file():
        return None
    m = re.search(r"COBOL coverage: (.+)", log.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def _save(work: Path, case: str, base: dict[str, Any], every: list[Mutant], chosen: list[Mutant],
          results: dict[str, dict[str, Any]], started: float, seed: int, mode: str,
          claim: str | None = None) -> dict[str, Any]:  # fmt: skip
    if claim is None:
        claim = _baseline_claim(work)
    summary = {"case": case, "program": (base.get("report") or {}).get("program"), "mutants": len(every),
               "chosen": len(chosen), "seed": seed, "mode": mode, "seconds": round(time.time() - started),
               "coverage": claim,
               "results": [{**{k: v for k, v in asdict(m).items() if k not in ("offset", "length", "replacement")},
                            **results.get(m.id, {"verdict": "pending"})} for m in chosen]}  # fmt: skip
    (work / "mutation.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (work / "mutation.md").write_text(mutation_md(summary), encoding="utf-8")
    return summary


def score(results: list[dict[str, Any]]) -> dict[str, int]:
    counts = dict.fromkeys(("killed", "timeout", "survived", "stillborn", "error", "pending"), 0)
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    return counts


def mutation_md(s: dict[str, Any]) -> str:
    c = score(s["results"])
    caught = c["killed"] + c["timeout"]
    judged = caught + c["survived"]
    pct = f"{100 * caught / judged:.0f}%" if judged else "n/a"
    lines = [f"# Mutation testing: {s['case']} ({s.get('program') or '?'})", "",
             f"**Score: {caught}/{judged} caught ({pct})** -- killed {c['killed']}, timeout {c['timeout']}, "
             + f"survived {c['survived']}; stillborn (javac) {c['stillborn']}, error {c['error']}, "
             + f"pending {c['pending']}. {s['chosen']} of {s['mutants']} mutants run (seed {s['seed']}, "
             + f"{s.get('mode', 'full')} mode), {s['seconds']} s.", ""]  # fmt: skip
    if s.get("coverage"):
        lines += [f"The proof, as committed: {s['coverage']}.", ""]
    ops: dict[str, dict[str, int]] = {}
    for r in s["results"]:
        ops.setdefault(r["op"], {}).setdefault(r["verdict"], 0)
        ops[r["op"]][r["verdict"]] += 1
    lines += ["| operator | killed | timeout | survived | stillborn |", "|---|---|---|---|---|"]
    for op in sorted(ops):
        o = ops[op]
        lines.append(f"| {op} | {o.get('killed', 0)} | {o.get('timeout', 0)} | {o.get('survived', 0)} "
                     f"| {o.get('stillborn', 0)} |")  # fmt: skip
    only_faults = [r for r in s["results"] if r["verdict"] == "killed" and r.get("killed_by")
                   and "main" not in r["killed_by"] and "java" not in r["killed_by"]
                   and not any(k.startswith("call ") for k in r["killed_by"])]  # fmt: skip
    if only_faults and any(r.get("killed_by") and "main" in r["killed_by"] for r in s["results"]):
        lines += ["", f"**Killed only by fault runs: {len(only_faults)}** (the normal run alone would have "
                  + "proven them)."]  # fmt: skip
    survivors = [r for r in s["results"] if r["verdict"] == "survived"]
    if survivors:
        lines += ["", "## Survivors", "", "Each is an equivalent mutant (noise) or a place the case never looks. "
                  + "Read each one.", ""]  # fmt: skip
        for r in survivors:
            lines += [f"- `{r['id']}` {r['op']} {r['file']}:{r['line']}", f"  - was: `{r['before']}`",
                      f"  - now: `{r['after']}`"]  # fmt: skip
    return "\n".join(lines) + "\n"


def compare(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Two runs of the same case (fast and --full): the mutants both judged, and every one they judge differently.
    Caught (killed or timeout) against survived is the verdict; stillborn is javac's in both."""

    def caught(v: str) -> str:
        return {"killed": "caught", "timeout": "caught"}.get(v, v)

    ra = {r["id"]: r for r in a["results"]}
    rb = {r["id"]: r for r in b["results"]}
    both = [i for i in ra if i in rb and "pending" not in (ra[i]["verdict"], rb[i]["verdict"])]
    differ = [{"id": i, "op": ra[i]["op"], "line": ra[i]["line"], a.get("mode", "a"): ra[i]["verdict"],
               b.get("mode", "b"): rb[i]["verdict"]} for i in both
              if caught(ra[i]["verdict"]) != caught(rb[i]["verdict"])]  # fmt: skip
    secs = {m: sum(r.get("seconds", 0) for r in x["results"] if r["id"] in both) for m, x in (("a", a), ("b", b))}
    survivors = [i for i in both if "survived" in (caught(ra[i]["verdict"]), caught(rb[i]["verdict"]))]
    surv_secs = {m: sum(x[i].get("seconds", 0) for i in survivors) for m, x in (("a", ra), ("b", rb))}
    by_op: dict[str, dict[str, int]] = {}  # per operator: judged by both / judged differently
    for i in both:
        o = by_op.setdefault(ra[i]["op"], {"judged": 0, "differ": 0})
        o["judged"] += 1
        o["differ"] += caught(ra[i]["verdict"]) != caught(rb[i]["verdict"])
    ma, mb = a.get("mode", "a"), b.get("mode", "b")
    return {"judged_by_both": len(both), "agree": len(both) - len(differ), "differ": differ,
            "proof_seconds": {ma: secs["a"], mb: secs["b"]},
            "survivor_proof_seconds": {ma: surv_secs["a"], mb: surv_secs["b"]},
            "by_operator": by_op}  # fmt: skip


def agreement_gate(result: dict[str, Any], minimum: int | None) -> bool:
    """`compare --require-agree N`: no gate without N; otherwise N or more judged by both, and none differ."""
    return minimum is None or (result["judged_by_both"] >= minimum and not result["differ"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("case")
    r.add_argument("--work", type=Path, required=True)
    r.add_argument("--jobs", type=int, default=4)
    r.add_argument("--sample", type=int, help="at most N mutants, spread over the operators (default: all)")
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--ops", default=",".join(OPERATORS), help="operators: " + ", ".join(OPERATORS))
    r.add_argument("--timeout", type=float, help="seconds per mutant (default: 3x the baseline, at least 300)")
    r.add_argument("--keep", action="store_true", help="keep killed mutants' proof directories too")
    r.add_argument("--case-file", type=Path, help="#4049: judge the mutants against this case.json instead of the "
                   "case's own (a candidate the test-strengthening loop wrote)")  # fmt: skip
    r.add_argument("--only", type=Path, help="run exactly the mutants another run's DIR judged (its "
                   "mutation.json), e.g. to check the fast mode against a --full reference")  # fmt: skip
    r.add_argument("--port", type=Path, help="#4628: mutate this port (e.g. a det port, DIR/CASE/port of "
                   "`det_port.py run --translate-only`) instead of the case's committed one")  # fmt: skip
    r.add_argument("--files", default="**/*.java", help="the port's files to mutate, a glob under it (a det port: "
                   "service/*.java, the translated program without the cobolrt runtime)")  # fmt: skip
    r.add_argument("--full", action="store_true", help="prove each mutant from scratch (the COBOL side, the whole "
                   "estate regenerated, every run): slow, the reference the default fast mode must agree with")  # fmt: skip
    r.add_argument("--one-jvm", action=argparse.BooleanOptionalAction, default=None, help="all the runs of one proof in "
                   "one JVM (equivalence.py --one-jvm); the default in fast mode (agrees with --full: docs/language_status/"
                   "mutation_testing.md), --no-one-jvm for a JVM per run; Db2 / IMS cases always use one per run")  # fmt: skip
    r.add_argument("--record", action="store_true", help="#4048: the run becomes the port's committed score "
                   "(mutation_scores.json, its survivors' triage kept) and its evidence record's `mutation`")  # fmt: skip
    r.add_argument("--triage", type=Path, nargs="*", default=[], help="with --record: triage files for new survivors")
    ls = sub.add_parser("list")
    ls.add_argument("case")
    ls.add_argument("--ops", default=",".join(OPERATORS))
    rp = sub.add_parser("report")
    rp.add_argument("work", type=Path)
    cp = sub.add_parser("compare", help="two runs of one case (fast and --full): do their verdicts agree?")
    cp.add_argument("a", type=Path)
    cp.add_argument("b", type=Path)
    cp.add_argument("--require-agree", type=int, metavar="N", help="a gate: exit 1 unless both runs judged at least N "
                    "mutants and none of them differ")  # fmt: skip
    args = ap.parse_args(argv)
    if args.cmd == "compare":
        loaded = [json.loads((w / "mutation.json").read_text(encoding="utf-8")) for w in (args.a, args.b)]
        result = compare(*loaded)
        print(json.dumps(result, indent=2))
        return 0 if agreement_gate(result, args.require_agree) else 1
    if args.cmd == "report":
        s = json.loads((args.work / "mutation.json").read_text(encoding="utf-8"))
        (args.work / "mutation.md").write_text(mutation_md(s), encoding="utf-8")
        print(mutation_md(s))
        return 0
    ops = {o.strip() for o in args.ops.split(",") if o.strip()}
    if ops - set(OPERATORS):
        raise SystemExit(f"unknown operators: {sorted(ops - set(OPERATORS))}")
    if args.cmd == "list":
        ms = all_mutants(port_dir(args.case), ops)
        for m in ms:
            print(f"{m.id} {m.op} {m.file}:{m.line}  {m.after}")
        counts: dict[str, int] = {}
        for m in ms:
            counts[m.op] = counts.get(m.op, 0) + 1
        print(f"{len(ms)} mutants: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
        return 0
    if args.one_jvm and args.full:
        raise SystemExit("--one-jvm is a fast-mode option: drop --full")
    if args.one_jvm is None:  # #4047: the session JVM is the fast-mode default
        args.one_jvm = not args.full
    if args.record and (args.case_file or args.only or args.port or args.files != "**/*.java"):
        raise SystemExit("--record scores the committed port on the committed case: drop --case-file / --only / "
                         "--port / --files")  # fmt: skip
    s = run(
        args.case,
        args.work,
        args.jobs,
        args.sample,
        args.seed,
        ops,
        args.timeout,
        args.keep,
        args.full,
        args.only,
        args.case_file,
        args.port,
        args.files,
        one_jvm=args.one_jvm,
    )
    print(mutation_md(s))
    if args.record:
        import mutation_scores

        mutation_scores.record_run(args.work, args.triage)
    return 0


if __name__ == "__main__":
    sys.exit(main())
