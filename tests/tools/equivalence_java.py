"""
The Java side of the equivalence harness (#3624; see equivalence.py).

The case's corpus goes through the refractor and cobol-to-java (target config `h2`,
java_target_matrix's own helpers), the case's hand-ported sources (`port/`, laid out
under com/gitgalaxy/modernized) replace the generated ones, and a generated JUnit test
-- EquivalenceRunTest -- runs the step in a Spring context on H2:

  1. each input dataset with an `entity` is loaded record by record through that
     entity's generated codec (fromRecord) into its repository;
  2. the program's service runs `runBatch(dds, parm)`, the DDs mapped by the generated
     DatasetResolver to files under the work directory, the clock pinned by
     `gitgalaxy.clock`;
  3. each compared output is dumped: a VSAM store from its repository in key order
     through toRecord, a sequential dataset as the file the step wrote.

Maven runs offline when the local repository already holds the build's artifacts
(the compile matrix fills it), else online.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

import equivalence_common as common
import java_target_matrix as jtm

CASES = Path(__file__).resolve().parents[1] / "equivalence"  # == equivalence.CASES
PKG = "com.gitgalaxy.modernized"
PKG_DIR = PKG.replace(".", "/")


# #3821: the JVM environments an equivalence claim can be made under -- a BCP-47 default locale and a
# default time zone, applied by the generated test before Spring starts. The mainframe's own zone is the
# case's `zone` (gitgalaxy.zone, #3824), never these: a port that reads the JVM's locale or zone shows
# up as a difference between environments. `default` pins what the harness used to inherit from the host.
ENVIRONMENTS: dict[str, dict[str, str]] = {
    "default": {"locale": "en-US", "tz": "UTC"},
    "turkish": {"locale": "tr-TR", "tz": "Europe/Istanbul"},  # dotless i: toUpperCase("i") is "İ"
    "arabic": {"locale": "ar-EG", "tz": "Africa/Cairo"},  # Arabic-Indic digits in String.format
    "thai": {"locale": "th-TH-u-nu-thai", "tz": "Asia/Bangkok"},  # Thai digits, Buddhist-era calendar
    "german": {"locale": "de-DE", "tz": "Europe/Berlin"},  # decimal comma in NumberFormat, DST
    "hindi": {"locale": "hi-IN", "tz": "Asia/Kolkata"},  # a +05:30 offset
}


def environment(name: str) -> dict[str, str]:
    """#3821: a named environment, or `LOCALE[/TZ]` (e.g. `sv-SE/Europe/Stockholm`) as written."""
    if name in ENVIRONMENTS:
        return {"name": name, **ENVIRONMENTS[name]}
    locale, _, tz = name.partition("/")
    return {"name": name, "locale": locale, "tz": tz or "UTC"}


def jvm_args(env: dict[str, str]) -> str:
    """The system properties that put the generated test in `env` (see EquivalenceRunTest's static block)."""
    args = f"-Dequivalence.locale={env['locale']} -Dequivalence.tz={env['tz']}"
    return args + (f" -Dfile.encoding={env['encoding']}" if env.get("encoding") else "")


def _service_class(program: str) -> str:
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_names import java_class_base

    return java_class_base(program) + "Service"


def _clock(case: dict[str, Any]) -> str:
    """The case's COB_CURRENT_DATE (`YYYY/MM/DD hh:mm:ss.cc`) as an ISO local date-time."""
    date, _, time = case["clock"].partition(" ")
    return f"{date.replace('/', '-')}T{time}"


def equivalence_test(case: dict[str, Any]) -> str:
    """The generated JUnit test that loads, runs and dumps one case (see the module docstring)."""
    svc = _service_class(case["program"])
    var = svc[0].lower() + svc[1:]
    fields, loads, dumps = [], [], []
    for dd, spec in case["datasets"].items():
        ent = spec.get("entity")
        if ent:
            fields.append(f"    @Autowired {PKG}.repository.vsam.{ent}Repository {ent[0].lower()}{ent[1:]}Repository;")
        if ent and "input" in spec:
            loads.append(
                f'        load("{dd}", {spec["reclen"]}, {ent}::fromRecord, {ent[0].lower()}{ent[1:]}Repository);'
            )
        if spec.get("compare") and ent:
            dumps.append(f'        dump("{dd}", {ent[0].lower()}{ent[1:]}Repository.findAll().stream()'
                         f'.map(r -> r.toRecord(TEXT)).sorted(java.util.Arrays::compare).toList());')  # fmt: skip
        elif spec.get("compare"):
            dumps.append(f'        if (Files.exists(datasets.resolve("{dd}"))) {{  // a stub may write nothing\n'
                         f'            Files.copy(datasets.resolve("{dd}"), out.resolve("{dd}.out"), '
                         "java.nio.file.StandardCopyOption.REPLACE_EXISTING);\n        }")  # fmt: skip
    dds = ", ".join(f'new Dd("{dd}", "{dd}", null, null, null)' for dd in case["datasets"])
    parm = f'"{case["parm"]}"' if case.get("parm") is not None else "null"
    imports = "".join(
        f"import {PKG}.entity.vsam.{s['entity']};\n" for s in case["datasets"].values() if s.get("entity")
    )
    return f"""package {PKG};

import {PKG}.batch.CobolAbend;
import {PKG}.batch.Dd;
{imports}import java.io.IOException;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.function.BiFunction;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.data.jpa.repository.JpaRepository;

/** #3624: the equivalence run of {case["program"]} ({case["name"]}) -- generated by tests/tools/equivalence_java.py. */
@SpringBootTest(properties = {{"spring.jpa.show-sql=false", "gitgalaxy.clock={_clock(case)}",
        "gitgalaxy.zone={case.get("zone", "UTC")}", "gitgalaxy.datasets.directory=${{equivalence.datasets}}"}})
class EquivalenceRunTest {{

    static {{  // #3821: the environment the claim is made under, before Spring reads the default locale
        java.util.Locale.setDefault(java.util.Locale.forLanguageTag(System.getProperty("equivalence.locale", "en-US")));
        java.util.TimeZone.setDefault(java.util.TimeZone.getTimeZone(System.getProperty("equivalence.tz", "UTC")));
    }}

    static final Charset TEXT = {common.java_charset(common.data_encoding(case))};
    final Path in = Path.of(System.getProperty("equivalence.in"));
    final Path out = Path.of(System.getProperty("equivalence.out"));
    final Path datasets = Path.of(System.getProperty("equivalence.datasets"));

    @Autowired {PKG}.service.{svc} {var};
{chr(10).join(fields)}

    @Test
    void run() throws IOException {{
{chr(10).join(loads)}
        int rc;
        try {{
            rc = {var}.runBatch(List.of({dds}), {parm});
        }} catch (CobolAbend abend) {{  // the step ends ABEND Unnnn, with no return code
            Files.writeString(out.resolve("ABEND"), abend.code());
            return;
        }} catch (RuntimeException e) {{  // an abend the port did not code as one: never equal to the COBOL's
            Files.writeString(out.resolve("ABEND"), ("UNCODED " + e).lines().findFirst().orElse("UNCODED"));
            return;
        }}
        Files.writeString(out.resolve("RETURN-CODE"), Integer.toString(rc));
{chr(10).join(dumps)}
    }}

    <E> void load(String dd, int reclen, BiFunction<byte[], Charset, E> fromRecord, JpaRepository<E, ?> repo)
            throws IOException {{
        byte[] data = Files.readAllBytes(in.resolve(dd + ".in"));
        List<E> rows = new ArrayList<>();
        for (int i = 0; i + reclen <= data.length; i += reclen) {{
            rows.add(fromRecord.apply(java.util.Arrays.copyOfRange(data, i, i + reclen), TEXT));
        }}
        repo.saveAll(rows);
    }}

    void dump(String dd, List<byte[]> records) throws IOException {{
        try (var o = Files.newOutputStream(out.resolve(dd + ".out"))) {{
            for (byte[] r : records) {{
                o.write(r);
            }}
        }}
    }}
}}
"""


def prepare_project(case: dict[str, Any], corpus: Path, work: Path, test_source: str, port: bool = True,
                    port_dir: Path | None = None) -> Path:  # fmt: skip
    """The generated project (config `h2`) with the port overlaid and `test_source` as its
    EquivalenceRunTest. `port` False keeps the generated service as generated (the stub)."""
    work.mkdir(parents=True, exist_ok=True)
    # #3753: any candidate port, laid out the same way; #3804: a case may prove another case's port
    port_dir = port_dir or CASES / case.get("port_from", case["name"]) / "port"
    overlay = sorted(f.relative_to(port_dir).as_posix() for f in port_dir.rglob("*.java")) if port else []
    earlier = common.reused(work)
    if earlier is not None:  # --reuse: the earlier run's project, built from the same estate by the same generator
        project = _reused_project(earlier, work, overlay)
    else:
        clean = jtm.refactor(corpus, work, scan=True)
        # #3828: a case's `culture` (e.g. {"db2_date_format": "eur"}) is the Java side's target config too
        config = {**jtm.MATRIX["h2"], "culture": case["culture"]} if case.get("culture") else jtm.MATRIX["h2"]
        project = jtm.generate(clean, "h2", config, work)
    (project / OVERLAY_FILE).write_text(json.dumps(overlay) + "\n", encoding="utf-8")
    for rel in overlay:
        dest = project / "src/main/java" / PKG_DIR / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(port_dir / rel, dest)
    if earlier is not None and overlay:
        _compile_overlay(project, earlier, overlay, work)
    test = project / "src/test/java" / PKG_DIR / "EquivalenceRunTest.java"
    test.parent.mkdir(parents=True, exist_ok=True)
    test.write_text(test_source, encoding="utf-8")
    return project


OVERLAY_FILE = "equivalence_overlay.json"  # the port files laid over the generated project, for --reuse


def _reused_project(earlier: Path, work: Path, overlay: list[str]) -> Path:
    """The earlier run's generated project, copied (its build too): only valid when the port covers the same
    files, so that every one the earlier port replaced is replaced again."""
    poms = sorted(earlier.glob(f"*/{OVERLAY_FILE}"))
    if len(poms) != 1:
        raise RuntimeError(f"--reuse: no single generated project under {earlier}")
    before = json.loads(poms[0].read_text(encoding="utf-8"))
    if before != overlay:
        raise RuntimeError(f"--reuse: the port's files {overlay} are not the earlier run's {before}")
    project = work / poms[0].parent.name
    shutil.copytree(poms[0].parent, project, dirs_exist_ok=True, ignore=shutil.ignore_patterns("surefire-reports"))
    (project / PRECOMPILED).unlink(missing_ok=True)
    return project


# javac exactly as the generated pom's maven-compiler-plugin runs it (Spring Boot's parent: -parameters, release 17;
# Lombok found on the classpath)
JAVAC_OPTIONS = ["-g", "-parameters", "--release", "17", "-encoding", "UTF-8", "-nowarn"]
PRECOMPILED = "target/equivalence-precompiled"  # present: the main classes are built, Maven skips compiling them


def _compile_overlay(project: Path, earlier: Path, overlay: list[str], work: Path) -> None:
    """--reuse: compile only the port's files into the copied build (the rest of it is the earlier run's, from the
    same sources), against the classpath the earlier run's tests ran on. A compile error is the Java side failing,
    as Maven's would be."""
    import xml.etree.ElementTree as ET

    reports = sorted(earlier.glob("*/target/surefire-reports/TEST-*.xml"))
    if not reports:
        raise RuntimeError(f"--reuse: {earlier} has no surefire report to take the classpath from")
    props = {p.get("name"): p.get("value") for p in ET.parse(reports[0]).iter("property")}  # noqa: S314
    old = str(reports[0].parents[2])
    entries = [e.replace(old, str(project)) for e in props["surefire.test.class.path"].split(os.pathsep)]
    classpath = os.pathsep.join(e for e in entries if not e.endswith("test-classes"))
    classes = project / "target" / "classes"
    sources = [str(project / "src/main/java" / PKG_DIR / rel) for rel in overlay]
    env = dict(os.environ, JAVA_HOME=jtm._jdk(17))
    javac = str(Path(env["JAVA_HOME"]) / "bin" / "javac")
    proc = subprocess.run([javac, *JAVAC_OPTIONS, "-d", str(classes), "-cp", classpath, *sources],  # noqa: S603
                          env=env, capture_output=True, text=True, check=False)  # fmt: skip
    if proc.returncode != 0:
        errors = [f"[ERROR] {x}" for x in proc.stderr.splitlines() if ": error: " in x]
        (work / "maven.log").write_text("\n".join(errors) + "\n" + proc.stderr, encoding="utf-8")
        raise RuntimeError(f"Java side failed (see {work / 'maven.log'}):\n" + "\n".join(errors[:20]))
    (project / PRECOMPILED).write_text("", encoding="utf-8")


def run_maven(project: Path, work: Path, inputs: Path, env: dict[str, str] | None = None, props: str = "") -> Path:
    """Run EquivalenceRunTest in `env` (#3821; default: `default`), with more system properties `props`; the
    directory it wrote its outputs to."""
    out, datasets = work / "out", work / "datasets"
    for d in (out, datasets):
        d.mkdir(parents=True, exist_ok=True)
    props = f"{jvm_args(env or environment('default'))} {props}".strip()
    shell = dict(os.environ, JAVA_HOME=jtm._jdk(17))
    shell["PATH"] = str(Path(shell["JAVA_HOME"]) / "bin") + os.pathsep + shell["PATH"]
    skip = ["-Dmaven.main.skip=true"] if (project / PRECOMPILED).is_file() else []  # --reuse: compiled already
    cmd = ["mvn", "-q", "-B", "test", *skip, "-Dtest=EquivalenceRunTest", "-Dsurefire.failIfNoSpecifiedTests=false",
           f"-DargLine=-Dequivalence.in={inputs} -Dequivalence.out={out} -Dequivalence.datasets={datasets} {props}"]  # fmt: skip
    proc = subprocess.run(cmd, cwd=project, env=shell, capture_output=True, text=True, check=False)  # noqa: S603
    (work / "maven.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
    if proc.returncode != 0:
        tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-60:])
        raise RuntimeError(f"Java side failed (see {work / 'maven.log'}):\n{tail}")
    return out


def run_java(
    case: dict[str, Any], corpus: Path, work: Path, inputs: Path, port: bool = True, port_dir: Path | None = None
) -> dict[str, bytes]:
    """Generate, overlay, run; {dd: output bytes}. `inputs` holds the COBOL side's `<DD>.in`
    fixed-length files -- the very bytes the COBOL program read. `port` False runs the generated
    service as generated (the stub), the baseline the port is measured against."""
    return run_java_environments(case, corpus, work, inputs, [environment("default")], port, port_dir)["default"]


def run_java_environments(
    case: dict[str, Any], corpus: Path, work: Path, inputs: Path, envs: list[dict[str, str]], port: bool = True,
    port_dir: Path | None = None, faults: tuple[tuple[str, str], ...] = (),
    stop: Callable[[str, dict[str, bytes]], bool] | None = None,
) -> dict[str, dict[str, bytes]]:  # fmt: skip
    """#3821: the project built once, run in each environment from a fresh work area; {env name: {dd: bytes}}.
    #4023 follow-up: each of `faults` ((name, plan text)) runs once more in the first environment with the
    plan as gitgalaxy.faults.plan, as `fault:<name>` -- its outputs, and ABEND / FAULTS (the faults that fired).
    `stop(name, outputs)` True after a run ends there: the runs not made are missing from the result."""
    project = prepare_project(case, corpus, work, equivalence_test(case), port, port_dir)
    runs: dict[str, dict[str, bytes]] = {}
    for env in envs:
        area = work if len(envs) == 1 else work / f"env-{env['name'].replace('/', '_')}"
        datasets = area / "datasets"
        datasets.mkdir(parents=True, exist_ok=True)
        for dd, spec in case["datasets"].items():  # a sequential input is a file the program opens itself
            if "input" in spec and not spec.get("entity"):
                shutil.copy(inputs / f"{dd}.in", datasets / dd)
        runs[env["name"]] = _run_area(case, project, area, inputs, env)
        if stop and stop(env["name"], runs[env["name"]]):
            return runs
    for name, plan in faults:
        area = work / "faults" / name
        (area / "out").mkdir(parents=True, exist_ok=True)
        (area / "fault.plan").write_text(plan, encoding="ascii")
        props = f"-Dgitgalaxy.faults.plan={area / 'fault.plan'} -Dgitgalaxy.faults.log={area / 'out' / 'FAULTS'}"
        read = _run_area(case, project, area, inputs, envs[0], props)
        read.setdefault("FAULTS", b"")
        runs[f"fault:{name}"] = read
        if stop and stop(f"fault:{name}", read):
            return runs
    return runs


def _run_area(case: dict[str, Any], project: Path, area: Path, inputs: Path, env: dict[str, str],
              props: str = "") -> dict[str, bytes]:  # fmt: skip
    """One run of the step from a fresh datasets area: {dd: bytes}, RETURN-CODE or ABEND, and FAULTS."""
    datasets = area / "datasets"
    datasets.mkdir(parents=True, exist_ok=True)
    for dd, spec in case["datasets"].items():  # a sequential input is a file the program opens itself
        if "input" in spec and not spec.get("entity"):
            shutil.copy(inputs / f"{dd}.in", datasets / dd)
    out = run_maven(project, area, inputs, env, props)
    outs = {dd: out / f"{dd}.out" for dd, spec in case["datasets"].items() if spec.get("compare")}
    for extra in ("RETURN-CODE", "ABEND", "FAULTS"):
        outs[extra] = out / extra
    read = {dd: f.read_bytes() for dd, f in outs.items() if f.is_file()}  # a stub may write nothing
    for extra in ("RETURN-CODE", "ABEND"):  # a code, not a record: whitespace is not data
        if extra in read:
            read[extra] = read[extra].strip()
    return read
