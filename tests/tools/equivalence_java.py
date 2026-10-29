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

import hashlib
import json
import os
import queue
import re
import shlex
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any
from collections.abc import Callable

import equivalence_common as common
import java_target_matrix as jtm
from maven_exe import JVM_SHORT_RUN_FLAGS, JVM_UTF8_FLAGS, decode_output, maven_utf8_env, mvn_executable, run_decoded

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


def data_charset_arg(case: dict[str, Any]) -> str:
    """#4060: the port reads and writes record bytes in CobolRecords.charset(); the harness sets it to the case's
    data encoding -- the bytes the COBOL side wrote -- so a port that hard-codes another charset fails."""
    from gitgalaxy.core.ebcdic_codecs import java_charset_name

    return f"-Dgitgalaxy.data.charset={java_charset_name(common.data_encoding(case))}"


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


def run_parm(parm: str) -> str:
    """#5561: a run's own PARM, as it travels in a JVM argline: no whitespace or quote to split or end it."""
    if not re.fullmatch(r"[^\s'\"\\]+", parm):
        raise ValueError(f"a run's PARM {parm!r} has whitespace or a quote: it cannot travel in the JVM argline")
    return parm


def entry_names(case: dict[str, Any]) -> list[str]:
    """#4048 follow-up: the case's `entries` -- each a no-argument method of the service (a controller's entry,
    executeX) that runs the whole step. Each is an entry run: the step once more through that method instead of
    runBatch, compared with the same COBOL run, every output and the RETURN-CODE: the one the method returns (#4342:
    the generated executeX returns runBatch's), or 0 when it returns normally and is void. The method passes no PARM,
    so a case with one cannot have entries."""
    names = [e["method"] for e in case.get("entries", [])]
    if names and case.get("parm") is not None:
        raise SystemExit(
            f"{case['name']}: an entry method passes no PARM, so it is not the step the COBOL ran "
            f"(PARM={case['parm']!r}): drop `entries`"
        )
    bad = [n for n in names if not re.fullmatch(r"[a-z][A-Za-z0-9_]*", n)]
    if bad:
        raise SystemExit(f"{case['name']}: entries {bad} are not Java method names")
    return names


def _entry_returns(case: dict[str, Any], svc: str) -> dict[str, str]:
    """#4342: each entry method's declared return type (int: its RETURN-CODE), read from the case's port."""
    src = CASES / case.get("port_from", case["name"]) / "port" / "service" / f"{svc}.java"
    text = src.read_text(encoding="utf-8") if src.is_file() else ""
    return {m.group(2): m.group(1) for m in re.finditer(r"public\s+(int|void)\s+([a-z]\w*)\s*\(\s*\)", text)}


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
    parm = (
        f'System.getProperty("equivalence.parm", {parm})'
        if parm != "null"
        else 'System.getProperty("equivalence.parm")'
    )  # #5561: a run's own PARM
    imports = "".join(
        f"import {PKG}.entity.vsam.{s['entity']};\n" for s in case["datasets"].values() if s.get("entity")
    )
    entry_call = f"            rc = {var}.runBatch(List.of({dds}), {parm});\n"
    if case.get("entries"):  # an entry run (equivalence.entry): the step through the program's no-argument method
        returns = _entry_returns(case, svc)
        arms = "".join(f'                case "{e}" -> rc = {var}.{e}();\n' if returns.get(e) == "int"
                       # a void method returned normally: the step ends RETURN-CODE 0 (it returns none)
                       else f'                case "{e}" -> {{\n                    {var}.{e}();\n'
                            "                    rc = 0;\n                }\n"
                       for e in entry_names(case))  # fmt: skip
        entry_call = (
            '            String entry = System.getProperty("equivalence.entry", "");\n'
            "            if (entry.isEmpty()) {\n    " + entry_call + "            } else {\n"
            "                switch (entry) {\n"
            + arms
            + '                    default -> throw new IllegalStateException("no entry " + entry);\n'
            "                }\n"
            "            }\n"
        )
    db2_members = ""
    if case.get("db2"):  # #4269: the step is one Db2 unit of work (db2Step), the det runtime's COMMIT / ROLLBACK in it
        entry_call = ("            int[] step = new int[1];\n            db2Step(() -> {\n"
                      + re.sub(r"\brc = ", "step[0] = ", "".join("    " + ln for ln in entry_call.splitlines(True)))
                      + "            });\n            rc = step[0];\n")  # fmt: skip
        db2_members = DB2_STEP
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
import org.springframework.test.annotation.DirtiesContext;

/** #3624: the equivalence run of {case["program"]} ({case["name"]}) -- generated by tests/tools/equivalence_java.py. */
@SpringBootTest(properties = {{"spring.jpa.show-sql=false", "gitgalaxy.clock={_clock(case)}",
        "gitgalaxy.zone={case.get("zone", "UTC")}", "gitgalaxy.datasets.directory=${{equivalence.datasets}}"}})
@DirtiesContext  // a session JVM (--one-jvm) runs this class again: each run on a context of its own, as a fresh JVM has
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
        String sysin = System.getProperty("equivalence.sysin");
        if (sysin != null) {{  // #5106: the step's SYSIN stream (surefire's fork owns the real stdin)
            System.setIn(new java.io.FileInputStream(sysin));
        }}
{chr(10).join(loads)}
        int rc;
        try {{
{entry_call}        }} catch (CobolAbend abend) {{  // the step ends ABEND Unnnn, with no return code
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
{db2_members}}}
"""


# #4269: a Db2 case's step runs as ONE Db2 unit of work, as Db2 for z/OS runs a batch program's (DSN / CAF): committed
# when the step ends normally, backed out when it abends (the exception passes on, the test records the abend). A
# det port's EXEC SQL COMMIT / ROLLBACK end that unit in between: the det runtime's DetSql.unitOfWork is given the
# step's connection (by reflection: a model port has no det runtime, an older det runtime no unit of work), and runs
# its savepoint statements there.
DB2_STEP = f"""
    @Autowired org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate db2Jdbc;  // EquivalenceDb2Config

    void db2Step(Runnable step) {{
        javax.sql.DataSource ds = db2Jdbc.getJdbcTemplate().getDataSource();
        new org.springframework.transaction.support.TransactionTemplate(
                new org.springframework.jdbc.datasource.DataSourceTransactionManager(ds)).executeWithoutResult(t -> {{
            java.lang.reflect.Method set = detUnitOfWork();
            Object was = null;
            try {{
                if (set != null) {{
                    Class<?> type = set.getParameterTypes()[0];
                    was = set.invoke(null, java.lang.reflect.Proxy.newProxyInstance(type.getClassLoader(),
                            new Class<?>[] {{type}}, (p, m, a) -> {{
                                switch (m.getName()) {{
                                    case "commit" -> org.springframework.jdbc.datasource.DataSourceUtils
                                            .getConnection(ds).commit();
                                    case "rollback" -> org.springframework.jdbc.datasource.DataSourceUtils
                                            .getConnection(ds).rollback();
                                    case "execute" -> {{  // a savepoint statement, on the step's connection
                                        try (java.sql.Statement st = org.springframework.jdbc.datasource
                                                .DataSourceUtils.getConnection(ds).createStatement()) {{
                                            st.execute((String) a[0]);
                                        }}
                                    }}
                                    case "hashCode" -> {{
                                        return System.identityHashCode(p);
                                    }}
                                    case "equals" -> {{
                                        return p == a[0];
                                    }}
                                    case "toString" -> {{
                                        return "the step's Db2 unit of work";
                                    }}
                                    default -> {{
                                    }}
                                }}
                                return null;
                            }}));
                }}
            }} catch (ReflectiveOperationException e) {{
                throw new IllegalStateException(e);
            }}
            try {{
                step.run();
            }} finally {{
                if (set != null) {{
                    try {{
                        set.invoke(null, was);
                    }} catch (ReflectiveOperationException e) {{
                        throw new IllegalStateException(e);
                    }}
                }}
            }}
        }});
    }}

    static java.lang.reflect.Method detUnitOfWork() {{
        try {{
            Class<?> det = Class.forName("{PKG}.cobolrt.sql.DetSql");
            return det.getMethod("unitOfWork", Class.forName("{PKG}.cobolrt.sql.DetSql$UnitOfWork"));
        }} catch (ReflectiveOperationException e) {{
            return null;  // no det runtime (a model port), or one with no unit of work
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
    overlay = (
        sorted(f.relative_to(port_dir).as_posix() for f in port_dir.rglob("*.java"))
        if port and port_dir.is_dir()
        else []
    )
    # A program that CALLs another (COTRN02C -> CSUTLDTC) runs against that program's proven port, never its
    # generated stub: `uses_ports` names the cases whose ports are laid first; the case's own port is laid last.
    used = [(CASES / other / "port", rel) for other in case.get("uses_ports", [])
            for rel in sorted(f.relative_to(CASES / other / "port").as_posix()
                              for f in (CASES / other / "port").rglob("*.java"))]  # fmt: skip
    # (merged before --reuse compares it with the earlier run's: both carry the borrowed files)
    overlay = [rel for _, rel in used if rel not in overlay] + overlay
    earlier = common.reused(work)
    if earlier is not None:  # --reuse: the earlier run's project, built from the same estate by the same generator
        project = _reused_project(earlier, work, overlay)
    else:
        import equivalence_cache

        with common.phase("java_generate"):  # #5882
            clean = equivalence_cache.refactor(corpus, work, scan=True)  # (once per corpus and engine: every case's)
            # #3828: a case's `culture` (e.g. {"db2_date_format": "eur"}) is the Java side's target config too
            config = {**jtm.MATRIX["h2"], "culture": case["culture"]} if case.get("culture") else jtm.MATRIX["h2"]
            project = jtm.generate(clean, "h2", config, work)
    (project / OVERLAY_FILE).write_text(json.dumps(overlay) + "\n", encoding="utf-8")
    sources = {rel: (port_dir / rel if (port_dir / rel).is_file() else next(d / r for d, r in used if r == rel))
               for rel in overlay}  # fmt: skip
    # #4188: a port proven with the programs its task LINKs to runs them as Java too, never as their stubs
    if port and port_dir.is_dir() and case.get("programs"):
        linked, origins = linked_programs(case, corpus, project, sources, work)
        overlay = overlay + [rel for rel in linked if rel not in sources]
        sources.update(linked)
        (work / LINKED_FILE).write_text(json.dumps(origins, indent=2) + "\n", encoding="utf-8")
    if port and port_dir.is_dir():  # #5856: a det port ships its service only; the runtime it names is this checkout's
        runtime = det_runtime(overlay, sources, project, work)
        overlay = overlay + [rel for rel in runtime if rel not in sources]
        sources.update(runtime)
    for rel in overlay:
        dest = project / "src/main/java" / PKG_DIR / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        keep_generated(dest, project, rel)
        shutil.copy(sources[rel], dest)
    if earlier is not None and overlay:
        _compile_overlay(project, earlier, overlay, work)
    if case.get("db2"):  # IBM's JDBC driver, and the Db2 repositories on the harness's Db2
        import equivalence_db2

        equivalence_db2.patch_project(project, PKG)
    test = project / "src/test/java" / PKG_DIR / "EquivalenceRunTest.java"
    test.parent.mkdir(parents=True, exist_ok=True)
    test.write_text(test_source, encoding="utf-8")
    return project


# #4048: the generated file each overlay file replaced, kept beside the project, so the evidence record can tell a
# method the port left as generated from one it ported (proof_reach's `generated`)
GENERATED_KEEP = "generated_before_overlay"


def keep_generated(dest: Path, project: Path, rel: str) -> None:
    """Before an overlay file replaces `dest`, keep the generated one (once) under ../generated_before_overlay/rel."""
    kept = project.parent / GENERATED_KEEP / rel
    if dest.is_file() and not kept.exists():
        kept.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(dest, kept)


OVERLAY_FILE = "equivalence_overlay.json"  # the port files laid over the generated project, for --reuse
LINKED_FILE = "linked_programs.json"  # #4188: where each LINKed program's Java came from, for the report


def linked_programs(case: dict[str, Any], corpus: Path, project: Path, sources: dict[str, Path],
                    work: Path) -> tuple[dict[str, Path], dict[str, str]]:  # fmt: skip
    """The Java of each program the case's task LINKs to (`"programs"`), for a port's proof (#4188): the port's own
    service when it carries one, else the program's committed model port (the case that proves it), else its
    deterministic translation from this checkout -- {published path: source}, and {program: origin}."""
    from gitgalaxy.tools.cobol_to_java.det import program as P

    files: dict[str, Path] = {}
    origins: dict[str, str] = {}
    for extra in case["programs"]:
        prog = extra["program"].upper()
        rel = f"service/{_service_class(prog)}.java"
        if rel in sources:
            origins[prog] = "the port under proof"
            continue
        proving = sorted(c.parent for c in CASES.glob("*/case.json")
                         if (c.parent / "port" / rel).is_file()
                         and json.loads(c.read_text(encoding="utf-8")).get("program", "").upper() == prog)  # fmt: skip
        if proving:
            other = proving[0] / "port"
            for f in sorted(other.rglob("*.java")):
                files.setdefault(f.relative_to(other).as_posix(), f)
            origins[prog] = f"committed model port ({proving[0].name})"
            continue
        dirs = [corpus / d for d in case.get("copy_dirs", ["app/cpy"])]
        dirs += [corpus / d for d in (case.get("db2") or {}).get("include_dirs", [])]
        # #4047: on --reuse the project's file is the earlier run's translation, not the stub: translate the kept stub
        kept = project.parent / GENERATED_KEEP / rel
        stub = (kept if kept.is_file() else project / "src/main/java" / PKG_DIR / rel).read_text(encoding="utf-8")
        r = P.translate(corpus / extra["program_source"], dirs, stub, PKG, P.estate_files(project), project,
                        options=common.effective_options(case, program=extra["program"]).layers,
                        layouts=common.engine_layouts(project, corpus, extra["program_source"]))  # fmt: skip
        out = work / "linked" / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(r.java, encoding="utf-8")
        files[rel] = out
        for x in r.extra:  # #5106: the LINKed program's sibling programs (a CALL into the same source), each a service
            x_rel = f"service/{x.service}.java"
            (work / "linked" / x_rel).write_text(x.java, encoding="utf-8")
            files[x_rel] = work / "linked" / x_rel
        for rt, text in P.runtime_files(PKG, P.has_batch(project)).items():
            dest = work / "linked" / rt
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8")
            files.setdefault(rt, dest)
        origins[prog] = f"det port (translated from {extra['program_source']})"
    return files, origins


def det_runtime(overlay: list[str], sources: dict[str, Path], project: Path, work: Path) -> dict[str, Path]:
    """#5856: the det runtime (cobolrt/...) of this checkout, for a port whose Java names it and does not carry it
    (a committed det port is its services; the runtime is the translator's, fingerprinted by the evidence record)."""
    if any(rel.startswith("cobolrt/") for rel in overlay):
        return {}
    if not any(f"{PKG}.cobolrt" in sources[rel].read_text(encoding="utf-8") for rel in overlay):
        return {}
    from gitgalaxy.tools.cobol_to_java.det import program as P

    files: dict[str, Path] = {}
    for rt, text in P.runtime_files(PKG, P.has_batch(project)).items():
        dest = work / "det_runtime" / rt
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
        files[rt] = dest
    return files


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
    kept = poms[0].parent.parent / GENERATED_KEEP  # #4047: the generated files the earlier overlay replaced (the stubs)
    if kept.is_dir():  # a LINKed program is translated from its stub, never from the earlier run's translation
        shutil.copytree(kept, work / GENERATED_KEEP, dirs_exist_ok=True)
    (project / PRECOMPILED).unlink(missing_ok=True)
    return project


# javac exactly as the generated pom's maven-compiler-plugin runs it (Spring Boot's parent: -parameters, release 17;
# Lombok found on the classpath)
JAVAC_OPTIONS = ["-g", "-parameters", "--release", "17", "-encoding", "UTF-8", "-nowarn"]
# #5882: the javac launcher's own JVM, C1 only and one GC thread: a compile is too short for C2 to pay back. A whole
# generated project (~210 sources, Lombok) took 13.9 CPU-s with the default JIT, 4.4 CPU-s like this, at the same wall
# time alone and ~2.3x faster four at once on four cores (a det shard's --jobs 4). Same compiler: the class files are
# byte-identical. (A warm javac_server JVM did not help: Lombok's processor reloads every compile.)
JAVAC_JVM_OPTIONS = ["-J-XX:TieredStopAtLevel=1", "-J-XX:+UseSerialGC"]
# #4904: timeouts for javac/java execution in equivalence tests
JAVAC_RUNNER_TIMEOUT = (
    300  # seconds: hang guard, well above the slowest honest run (normal single-file javac compile (~1-2s))
)
JAVA_DIRECT_TIMEOUT = (
    1200  # seconds: hang guard, well above the slowest honest run (normal Java equivalence test execution (~10-30s))
)
JAVAC_OVERLAY_TIMEOUT = (
    600  # seconds: hang guard, well above the slowest honest run (normal overlay javac compile (~3-10s))
)
MAVEN_TEST_TIMEOUT = (
    1200  # seconds: hang guard, well above the slowest honest run (normal mvn test execution (~20-60s))
)
JAVAC_PROJECT_TIMEOUT = (
    600  # seconds: hang guard, well above the slowest honest run (normal whole-project javac compile (~3-10s))
)
PRECOMPILED = "target/equivalence-precompiled"  # present: the main classes are built, Maven skips compiling them
TEST_CLASSPATH = "target/equivalence-test-classpath"  # --reuse: the classpath the tests run on, this project's
TEST_SOURCE = "target/equivalence-test-source"  # the EquivalenceRunTest source target/test-classes was built from
TEST_FILE = f"src/test/java/{PKG_DIR}/EquivalenceRunTest.java"
RUN_DONE = "@@EQUIVALENCE-RUN-DONE@@"  # --one-jvm: the line the session JVM ends each run's output with, then 0 / 1
RUNNER = f"""import org.junit.platform.launcher.core.LauncherDiscoveryRequestBuilder;
import org.junit.platform.launcher.core.LauncherFactory;
import org.junit.platform.launcher.listeners.SummaryGeneratingListener;
import org.junit.platform.launcher.listeners.TestExecutionSummary;
import static org.junit.platform.engine.discovery.DiscoverySelectors.selectClass;

/** --reuse: EquivalenceRunTest without Maven -- the JUnit Platform launcher surefire itself drives, in a fresh JVM.
 *  --session (--one-jvm): the same, once per line on stdin (tab-separated -Dname=value items, replacing the last
 *  run's), each run ended by a {RUN_DONE} line; "quit" or end of input ends the JVM. */
public class EquivalenceMain {{
    public static void main(String[] args) throws Exception {{
        if (args.length > 0 && args[0].equals("--session")) {{
            session();
            return;
        }}
        System.exit(runOnce() ? 0 : 1);
    }}

    static boolean runOnce() {{
        SummaryGeneratingListener listener = new SummaryGeneratingListener();
        LauncherFactory.create().execute(LauncherDiscoveryRequestBuilder.request()
                .selectors(selectClass("{PKG}.EquivalenceRunTest")).build(), listener);
        TestExecutionSummary s = listener.getSummary();
        s.printFailuresTo(new java.io.PrintWriter(System.out, true), 40);
        System.out.println("Tests run: " + s.getTestsFoundCount() + ", Failures: " + s.getTotalFailureCount());
        return s.getTestsSucceededCount() == 1 && s.getTotalFailureCount() == 0;
    }}

    static void session() throws Exception {{
        java.io.BufferedReader in = new java.io.BufferedReader(
                new java.io.InputStreamReader(System.in, java.nio.charset.StandardCharsets.UTF_8));
        System.setIn(new java.io.ByteArrayInputStream(new byte[0]));  // the step's stdin is its SYSIN or nothing
        java.util.List<String> set = new java.util.ArrayList<>();
        String line;
        while ((line = in.readLine()) != null && !line.equals("quit")) {{
            for (String k : set) {{
                System.clearProperty(k);
            }}
            set.clear();
            for (String kv : line.split("\t")) {{
                if (!kv.isEmpty()) {{
                    int eq = kv.indexOf('=');
                    String k = eq < 0 ? kv : kv.substring(0, eq);
                    System.setProperty(k, eq < 0 ? "" : kv.substring(eq + 1));
                    set.add(k);
                }}
            }}
            boolean ok = runOnce();
            System.out.println();
            System.out.println("{RUN_DONE} " + (ok ? 0 : 1));
            System.out.flush();
        }}
        System.exit(0);
    }}
}}
"""


def _launcher(classpath: list[str]) -> Path | None:
    """The junit-platform-launcher jar of the platform version the tests run on (surefire resolved it into the
    local repository), or None."""
    import re

    for e in classpath:
        e = e.replace("\\", "/")  # Windows entries are backslash paths
        m = re.search(r"(.*)/junit-platform-engine/([^/]+)/junit-platform-engine-\2\.jar$", e)
        if m:
            jar = (
                Path(m.group(1)) / "junit-platform-launcher" / m.group(2) / f"junit-platform-launcher-{m.group(2)}.jar"
            )
            return jar if jar.is_file() else None
    return None


def _runner(launcher: Path, java_bin: Path, classpath: str, shell: dict[str, str]) -> Path:
    """EquivalenceMain, compiled once per launcher version and runner source (shared by every mutant's proof)."""
    import hashlib
    import tempfile

    key = hashlib.sha256((str(launcher) + RUNNER).encode()).hexdigest()[:12]
    runner = Path(tempfile.gettempdir()) / f"gitgalaxy-equivalence-runner-{key}"
    if (runner / "EquivalenceMain.class").is_file():
        return runner
    build = Path(tempfile.mkdtemp(prefix="equivalence-runner-"))
    (build / "EquivalenceMain.java").write_text(RUNNER, encoding="utf-8")
    try:
        subprocess.run([str(java_bin / "javac"), *JAVAC_JVM_OPTIONS, "-encoding", "UTF-8", "-nowarn", "-d", str(build), "-cp", classpath,  # noqa: S603
                        str(build / "EquivalenceMain.java")], env=shell, check=True, capture_output=True,
                       timeout=JAVAC_RUNNER_TIMEOUT)  # fmt: skip
    except subprocess.TimeoutExpired as exc:
        shutil.rmtree(build, ignore_errors=True)
        raise RuntimeError(f"javac timed out after {JAVAC_RUNNER_TIMEOUT}s compiling EquivalenceMain") from exc
    try:
        build.rename(runner)  # atomic: a proof running beside this one may have made it first
    except OSError:
        shutil.rmtree(build, ignore_errors=True)
    return runner


def split_argline(argline: str, windows: bool | None = None) -> list[str]:
    """The -D properties of `argline` as argv items (#4939). POSIX mode treats a backslash as an escape, so it strips
    them out of a Windows path (`C:\\work\\in` -> `C:workin`); Windows takes the line as written."""
    return shlex.split(argline, posix=not (os.name == "nt" if windows is None else windows))


def _direct_parts(project: Path, shell: dict[str, str]) -> tuple[Path, str] | None:
    """The JDK bin directory and the classpath (tests, launcher, EquivalenceMain) of a plain-JVM run of this project's
    test, when the build is current (see `_run_direct`); else None."""
    test, snapshot, cp_file = project / TEST_FILE, project / TEST_SOURCE, project / TEST_CLASSPATH
    if not ((project / PRECOMPILED).is_file() and cp_file.is_file() and snapshot.is_file()
            and snapshot.read_bytes() == test.read_bytes()):  # fmt: skip
        return None
    classpath = cp_file.read_text(encoding="utf-8").split(os.pathsep)
    launcher = _launcher(classpath)
    if launcher is None:
        return None
    java_bin = Path(shell["JAVA_HOME"]) / "bin"
    runner = _runner(launcher, java_bin, os.pathsep.join([*classpath, str(launcher)]), shell)
    return java_bin, os.pathsep.join([*classpath, str(launcher), str(runner)])


class JvmSession:
    """--one-jvm: one JVM for all the runs of one proof. EquivalenceMain --session reads a run's -D properties from
    stdin, runs EquivalenceRunTest (a fresh Spring context each: the test class dirties it), and ends the run's
    output with RUN_DONE; the caller compares each run's outputs before sending the next, so --first-difference
    still stops where a fresh-JVM-per-run proof does."""

    def __init__(self, cmd: list[str], cwd: Path, env: dict[str, str]) -> None:
        self.cmd = cmd
        self.proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,  # noqa: S603
                                     stderr=subprocess.STDOUT, text=True, encoding="utf-8", bufsize=1)  # fmt: skip
        self._lines: queue.Queue[str | None] = queue.Queue()
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            self._lines.put(line)
        self._lines.put(None)

    def run(self, argline: str, timeout: float) -> subprocess.CompletedProcess[str]:
        """One run with the properties of `argline`: the JVM's output for it, and 0 / 1 (124 on a timeout, the JVM
        killed; the JVM's own status if it ended without finishing the run)."""
        assert self.proc.stdin is not None
        props = "\t".join(a[2:] for a in split_argline(argline) if a.startswith("-D"))
        out: list[str] = []
        deadline = time.monotonic() + timeout
        try:
            self.proc.stdin.write(props + "\n")
            self.proc.stdin.flush()
        except OSError:
            return subprocess.CompletedProcess(self.cmd, 1, "", "the session JVM is gone")
        while True:
            try:
                line = self._lines.get(timeout=max(0.0, deadline - time.monotonic()))
            except queue.Empty:
                self.proc.kill()
                return subprocess.CompletedProcess(self.cmd, 124, "".join(out),
                                                   f"java EquivalenceMain --session timed out after {timeout}s")  # fmt: skip
            if line is None:
                return subprocess.CompletedProcess(self.cmd, self.proc.wait() or 1, "".join(out),
                                                   "the session JVM ended before the run finished")  # fmt: skip
            if line.startswith(RUN_DONE):
                return subprocess.CompletedProcess(self.cmd, int(line.split()[-1]), "".join(out), "")
            out.append(line)

    def close(self) -> None:
        try:
            assert self.proc.stdin is not None
            self.proc.stdin.write("quit\n")
            self.proc.stdin.flush()
            self.proc.stdin.close()
            self.proc.wait(timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            self.proc.kill()
            self.proc.wait()


def start_session(project: Path, env: dict[str, str]) -> JvmSession | None:
    """A session JVM in `env` (its locale and zone are fixed at JVM start) when `_run_direct` could run, else None."""
    shell = dict(os.environ, JAVA_HOME=jtm._jdk(17))
    shell["PATH"] = str(Path(shell["JAVA_HOME"]) / "bin") + os.pathsep + shell["PATH"]
    parts = _direct_parts(project, shell)
    if parts is None:
        return None
    java_bin, full = parts
    cmd = [str(java_bin / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", *JVM_SHORT_RUN_FLAGS.split(),
           *split_argline(jvm_args(env)), "-cp", full, "EquivalenceMain", "--session"]  # fmt: skip
    return JvmSession(cmd, project, shell)


def _run_direct(project: Path, argline: str, shell: dict[str, str]) -> subprocess.CompletedProcess[str] | None:
    """--reuse: the test in a fresh JVM without Maven, when that is the same run -- the main classes compiled from
    the port, the test classes from this very test source; else None (Maven runs it)."""
    parts = _direct_parts(project, shell)
    if parts is None:
        return None
    java_bin, full = parts
    try:
        return subprocess.run([str(java_bin / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", *split_argline(argline), "-cp", full, "EquivalenceMain"],  # noqa: S603
                              cwd=project, env=shell, capture_output=True, text=True, encoding="utf-8", check=False,
                              timeout=JAVA_DIRECT_TIMEOUT)  # fmt: skip
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(
            args=[str(java_bin / "java"), *split_argline(argline), "-cp", full, "EquivalenceMain"],
            returncode=124,
            stdout=exc.stdout or "",
            stderr=((exc.stderr or "") + f"\njava EquivalenceMain timed out after {JAVA_DIRECT_TIMEOUT}s").lstrip(),
        )


def _surefire_classpath(report: Path, project: Path) -> list[str]:
    """The classpath surefire ran the tests on, from its report (the very `surefire.test.class.path` property)."""
    import xml.etree.ElementTree as ET

    props = {p.get("name"): p.get("value") for p in ET.parse(report).iter("property")}  # noqa: S314
    old = str(report.parents[2])  # the project the report was written in (a --reuse copy moves it)
    return [e.replace(old, str(project)) for e in props["surefire.test.class.path"].split(os.pathsep)]


# #5882: a project's first run went through Maven (its lifecycle and a surefire fork, ~5-10 s a case on top of the
# compile and the run), only to compile the sources and run the test. The dependency classpath depends only on the
# pom, so the first Maven run of a pom records it here, keyed by the pom's bytes (and the JDK); a later project with
# that pom compiles ALL its own sources with javac -- the options and annotation processing the pom's compiler plugin
# uses (JAVAC_OPTIONS: class files byte-identical to Maven's) -- and takes `_run_direct` from its first run. Nothing is
# shared between projects but the classpath. Anything unsure (no record, a jar gone, a resource Maven would filter,
# javac failing) falls back to Maven, which then reports as before. GITGALAXY_EQUIV_MAVEN_ONLY=1: always Maven.
CLASSPATH_CACHE = Path.home() / ".cache" / "gitgalaxy-equivalence" / "classpath"
MAVEN_ONLY_ENV = "GITGALAXY_EQUIV_MAVEN_ONLY"


def _pom_key(project: Path) -> str:
    """The pom's dependency identity: its bytes less the project's own top-level artifactId / name / description (a
    corpus's name: the only difference between two corpora's generated poms), and the JDK. A pom that does not parse
    is keyed by its raw bytes."""
    import xml.etree.ElementTree as ET

    raw = (project / "pom.xml").read_bytes()
    try:
        root = ET.fromstring(raw)  # noqa: S314 -- the generator's own pom
        for child in list(root):
            if child.tag.rsplit("}", 1)[-1] in ("artifactId", "name", "description"):
                root.remove(child)
        raw = ET.tostring(root)
    except ET.ParseError:
        pass
    return hashlib.sha256(raw + jtm._jdk(17).encode()).hexdigest()[:32]


def _save_classpath(project: Path, entries: list[str]) -> None:
    """The dependency jars of `entries` (a surefire classpath of `project`), recorded under the pom's key."""
    jars = [e for e in entries if not e.startswith(str(project))]
    CLASSPATH_CACHE.mkdir(parents=True, exist_ok=True)
    tmp = CLASSPATH_CACHE / f".{_pom_key(project)}.{os.getpid()}"
    tmp.write_text("\n".join(jars) + "\n", encoding="utf-8")
    tmp.replace(CLASSPATH_CACHE / f"{_pom_key(project)}.txt")


def _filtered(resources: Path) -> bool:
    """A resource spring-boot-starter-parent's filtering could change (an @...@ token): only Maven copies it right."""
    return resources.is_dir() and any(f.is_file() and b"@" in f.read_bytes() for f in resources.rglob("*"))


def _javac(args: list[str], env: dict[str, str]) -> bool:
    javac = str(Path(env["JAVA_HOME"]) / "bin" / "javac")
    try:
        return subprocess.run([javac, *JAVAC_JVM_OPTIONS, "-encoding", "UTF-8", *JAVAC_OPTIONS, *args], env=env, capture_output=True, text=True,  # noqa: S603
                              encoding="utf-8", check=False, timeout=JAVAC_PROJECT_TIMEOUT).returncode == 0  # fmt: skip
    except subprocess.TimeoutExpired:
        return False


def _javac_build(project: Path, shell: dict[str, str]) -> bool:
    """#5882: build `project` (main and test classes, resources) with javac on its pom's recorded classpath and mark it
    for `_run_direct`; False (nothing left behind) when Maven must build it."""
    if os.environ.get(MAVEN_ONLY_ENV) or not (project / "pom.xml").is_file():
        return False
    try:
        record = CLASSPATH_CACHE / f"{_pom_key(project)}.txt"
    except OSError:
        return False
    if not record.is_file():
        return False
    jars = [e for e in record.read_text(encoding="utf-8").splitlines() if e]
    main_res, test_res = project / "src/main/resources", project / "src/test/resources"
    if not all(Path(j).exists() for j in jars) or _filtered(main_res) or _filtered(test_res):
        return False
    classes, test_classes = project / "target" / "classes", project / "target" / "test-classes"
    main = sorted(str(f) for f in (project / "src/main/java").rglob("*.java"))
    tests = sorted(str(f) for f in (project / "src/test/java").rglob("*.java"))
    for d in (classes, test_classes):
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
    ok = _javac(["-d", str(classes), "-cp", os.pathsep.join(jars), *main], shell) and _javac(
        ["-d", str(test_classes), "-cp", os.pathsep.join([str(classes), *jars]), *tests], shell
    )
    if not ok:  # Maven builds it from scratch and says why
        for d in (classes, test_classes):
            shutil.rmtree(d, ignore_errors=True)
        return False
    for res, dest in ((main_res, classes), (test_res, test_classes)):
        if res.is_dir():
            shutil.copytree(res, dest, dirs_exist_ok=True)
    (project / TEST_CLASSPATH).write_text(os.pathsep.join([str(test_classes), str(classes), *jars]), encoding="utf-8")
    (project / TEST_SOURCE).write_bytes((project / TEST_FILE).read_bytes())
    (project / PRECOMPILED).write_text("", encoding="utf-8")
    return True


def _record_direct(project: Path) -> None:
    """#4910: after the first Maven run of a project built here (main classes compiled, tests passed on surefire's
    classpath), keep that classpath so every later run of it takes `_run_direct` -- a fresh JVM, no Maven/Spring
    start-up. A project without a surefire report just keeps running through Maven."""
    reports = sorted(project.glob("target/surefire-reports/TEST-*.xml"))
    classes = project / "target" / "classes"
    if not reports or not classes.is_dir() or (project / TEST_CLASSPATH).is_file():
        return
    try:
        entries = _surefire_classpath(reports[0], project)
    except (OSError, KeyError, ValueError, SyntaxError):
        return
    (project / TEST_CLASSPATH).write_text(os.pathsep.join(entries), encoding="utf-8")
    (project / PRECOMPILED).write_text("", encoding="utf-8")
    try:
        _save_classpath(project, entries)  # #5882: the next project with this pom builds with javac
    except OSError:  # (no pom, an unwritable cache: the next project just runs Maven)
        pass


def _compile_overlay(project: Path, earlier: Path, overlay: list[str], work: Path) -> None:
    """--reuse: compile only the port's files into the copied build (the rest of it is the earlier run's, from the
    same sources), against the classpath the earlier run's tests ran on. A compile error is the Java side failing,
    as Maven's would be."""
    import xml.etree.ElementTree as ET

    reports = sorted(earlier.glob("*/target/surefire-reports/TEST-*.xml"))
    if reports:
        props = {p.get("name"): p.get("value") for p in ET.parse(reports[0]).iter("property")}  # noqa: S314
        old = str(reports[0].parents[2])
        entries = props["surefire.test.class.path"].split(os.pathsep)
    else:  # #5882: a project `_javac_build` built ran no Maven, so no surefire report; it kept the classpath itself
        recorded = sorted(earlier.glob(f"*/{TEST_CLASSPATH}"))
        if not recorded:
            raise RuntimeError(f"--reuse: {earlier} has no surefire report or recorded classpath to take it from")
        old = str(recorded[0].parents[1])
        entries = recorded[0].read_text(encoding="utf-8").split(os.pathsep)
    entries = [e.replace(old, str(project)) for e in entries]
    classpath = os.pathsep.join(e for e in entries if not e.endswith("test-classes"))
    (project / TEST_CLASSPATH).write_text(os.pathsep.join(entries), encoding="utf-8")
    classes = project / "target" / "classes"
    sources = [str(project / "src/main/java" / PKG_DIR / rel) for rel in overlay]
    env = dict(os.environ, JAVA_HOME=jtm._jdk(17))
    javac = str(Path(env["JAVA_HOME"]) / "bin" / "javac")
    try:
        proc = subprocess.run([javac, *JAVAC_JVM_OPTIONS, "-encoding", "UTF-8", *JAVAC_OPTIONS, "-d", str(classes), "-cp", classpath, *sources],  # noqa: S603
                              env=env, capture_output=True, text=True, encoding="utf-8", check=False,
                              timeout=JAVAC_OVERLAY_TIMEOUT)  # fmt: skip
    except subprocess.TimeoutExpired as exc:
        errors = [f"[ERROR] javac timed out after {JAVAC_OVERLAY_TIMEOUT}s compiling overlay"]
        (work / "maven.log").write_text("\n".join(errors) + "\n", encoding="utf-8")
        raise RuntimeError(f"Java side failed (see {work / 'maven.log'}):\n" + "\n".join(errors)) from exc
    if proc.returncode != 0:
        errors = [f"[ERROR] {x}" for x in proc.stderr.splitlines() if ": error: " in x]
        (work / "maven.log").write_text("\n".join(errors) + "\n" + proc.stderr, encoding="utf-8")
        raise RuntimeError(f"Java side failed (see {work / 'maven.log'}):\n" + "\n".join(errors[:20]))
    (project / PRECOMPILED).write_text("", encoding="utf-8")


def run_maven(project: Path, work: Path, inputs: Path, env: dict[str, str] | None = None, props: str = "",
              session: JvmSession | None = None) -> Path:  # fmt: skip
    """Run EquivalenceRunTest in `env` (#3821; default: `default`), with more system properties `props`; the
    directory it wrote its outputs to. With `session` (--one-jvm) the run is the next one of that JVM."""
    out, datasets = work / "out", work / "datasets"
    for d in (out, datasets):
        d.mkdir(parents=True, exist_ok=True)
    props = f"{jvm_args(env or environment('default'))} {props}".strip()
    shell = dict(os.environ, JAVA_HOME=jtm._jdk(17))
    shell["PATH"] = str(Path(shell["JAVA_HOME"]) / "bin") + os.pathsep + shell["PATH"]
    argline = f"{JVM_SHORT_RUN_FLAGS} -Dequivalence.in={inputs} -Dequivalence.out={out} -Dequivalence.datasets={datasets} {props}"  # fmt: skip
    maven_argline = (
        f"{JVM_UTF8_FLAGS} {argline}"  # #5161: surefire's fork names its charset; an env's own file.encoding follows
    )
    if session is None and not (project / PRECOMPILED).is_file():
        with common.phase("java_javac"):  # #5882: a pom Maven built once before: javac, then the run below is direct
            _javac_build(project, shell)
    with common.phase("java_direct"):  # #5882: a run without Maven (None: Maven runs it, timed below)
        proc = session.run(argline, JAVA_DIRECT_TIMEOUT) if session else _run_direct(project, argline, shell)
    if proc is None:
        skip = ["-Dmaven.main.skip=true"] if (project / PRECOMPILED).is_file() else []  # --reuse: compiled already
        cmd = [mvn_executable(shell), "-q", "-B", "test", *skip, "-Dtest=EquivalenceRunTest", "-Dsurefire.failIfNoSpecifiedTests=false",
               f"-DargLine={maven_argline}"]  # fmt: skip
        try:
            with common.phase("java_maven"):  # #5882
                proc = run_decoded(cmd, cwd=project, env=maven_utf8_env(shell), check=False, timeout=MAVEN_TEST_TIMEOUT)
        except subprocess.TimeoutExpired as exc:
            proc = subprocess.CompletedProcess(
                args=cmd,
                returncode=124,
                stdout=decode_output(exc.stdout),
                stderr=(decode_output(exc.stderr) + f"\nmvn test timed out after {MAVEN_TEST_TIMEOUT}s").lstrip(),
            )
        if proc.returncode == 0 and (project / TEST_FILE).is_file():  # target/test-classes is this source's build
            (project / TEST_SOURCE).write_bytes((project / TEST_FILE).read_bytes())
            _record_direct(project)  # #4910: the later runs of this project skip Maven
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
    port_dir: Path | None = None, faults: tuple[tuple[str, ...], ...] = (),
    stop: Callable[[str, dict[str, bytes]], bool] | None = None, entries: tuple[str, ...] = (),
    one_jvm: bool = False,
) -> dict[str, dict[str, bytes]]:  # fmt: skip
    """#3821: the project built once, run in each environment from a fresh work area; {env name: {dd: bytes}}.
    #4023 follow-up: each of `faults` ((name, plan text)) runs once more in the first environment with the
    plan as gitgalaxy.faults.plan, as `fault:<name>` -- its outputs, and ABEND / FAULTS (the faults that fired).
    `stop(name, outputs)` True after a run ends there: the runs not made are missing from the result.
    #4048 follow-up: each of `entries` (entry_names) runs once more in the first environment through that
    method, as `entry:<name>`.
    `one_jvm`: the first environment's runs (it, the faults, the entries) go through one JVM (JvmSession) instead
    of one each; a Db2 / IMS case, and a project that cannot run directly, keep a JVM per run."""
    project = prepare_project(case, corpus, work, equivalence_test(case), port, port_dir)
    sessions = _Sessions(project, envs[0]) if one_jvm and not (case.get("db2") or case.get("ims")) else None
    try:
        return _run_all(case, project, work, inputs, envs, faults, stop, entries, sessions)
    finally:
        if sessions:
            sessions.close()


class _Sessions:
    """The one session JVM of a proof (--one-jvm), in the first environment. It starts once the project can run
    directly -- after the first run, when that run had to build it through Maven."""

    def __init__(self, project: Path, env: dict[str, str]) -> None:
        self.project, self.env = project, env
        self.session: JvmSession | None = None

    def get(self) -> JvmSession | None:
        if self.session is None:
            self.session = start_session(self.project, self.env)
        return self.session

    def close(self) -> None:
        if self.session:
            self.session.close()


def _run_all(case: dict[str, Any], project: Path, work: Path, inputs: Path, envs: list[dict[str, str]],
             faults: tuple[tuple[str, ...], ...], stop: Callable[[str, dict[str, bytes]], bool] | None,
             entries: tuple[str, ...], sessions: _Sessions | None) -> dict[str, dict[str, bytes]]:  # fmt: skip
    runs: dict[str, dict[str, bytes]] = {}
    for env in envs:
        area = work if len(envs) == 1 else work / f"env-{env['name'].replace('/', '_')}"
        datasets = area / "datasets"
        datasets.mkdir(parents=True, exist_ok=True)
        for dd, spec in case["datasets"].items():  # a sequential input is a file the program opens itself
            if "input" in spec and not spec.get("entity"):
                shutil.copy(inputs / f"{dd}.in", datasets / dd)
        runs[env["name"]] = _run_area(
            case, project, area, inputs, env, session=sessions.get() if sessions and env is envs[0] else None
        )
        if stop and stop(env["name"], runs[env["name"]]):
            return runs
    for name, plan, *rest in faults:
        sql = rest[:1]
        area = work / "faults" / name
        (area / "out").mkdir(parents=True, exist_ok=True)
        (area / "fault.plan").write_text(plan, encoding="ascii")
        (area / "out" / "FAULTS").unlink(missing_ok=True)  # the log appends: a re-run of this area starts afresh
        props = f"-Dgitgalaxy.faults.plan={area / 'fault.plan'} -Dgitgalaxy.faults.log={area / 'out' / 'FAULTS'}"
        if len(rest) > 1 and rest[1]:  # #5561: this run's own PARM (rest[1]), not the case's
            props += f" -Dequivalence.parm={run_parm(rest[1])}"
        if len(rest) > 2 and rest[2]:  # #5857: this run's own SYSIN (rest[2]), staged as the COBOL side read it
            sysin = rest[2]
            staged = (sysin if sysin.endswith("\n") else sysin + "\n").encode(common.data_encoding(case))
            (area / "SYSIN.in").write_bytes(staged)
            props += f" -Dequivalence.sysin={area / 'SYSIN.in'}"
        if sql and sql[0]:  # #4173: the run's SQL faults, to the det runtime's DetSql (the same log)
            (area / "sqlfaults.plan").write_text(sql[0] + "\n", encoding="ascii")
            props += (
                f" -Dgitgalaxy.sqlfaults.plan={area / 'sqlfaults.plan'}"
                f" -Dgitgalaxy.sqlfaults.log={area / 'out' / 'FAULTS'}"
            )
        own = {"dli_dir": Path(rest[3])} if len(rest) > 3 and rest[3] else {}  # #6967: this run's own IMS seed
        read = _run_area(case, project, area, inputs, envs[0], props, sessions.get() if sessions else None, **own)
        read.setdefault("FAULTS", b"")
        runs[f"fault:{name}"] = read
        if stop and stop(f"fault:{name}", read):
            return runs
    for name in entries:
        area = work / "entries" / name
        (area / "out").mkdir(parents=True, exist_ok=True)
        runs[f"entry:{name}"] = _run_area(
            case, project, area, inputs, envs[0], f"-Dequivalence.entry={name}", sessions.get() if sessions else None
        )
        if stop and stop(f"entry:{name}", runs[f"entry:{name}"]):
            return runs
    return runs


def _run_area(case: dict[str, Any], project: Path, area: Path, inputs: Path, env: dict[str, str],
              props: str = "", session: JvmSession | None = None,
              dli_dir: Path | None = None) -> dict[str, bytes]:  # fmt: skip
    """One run of the step from a fresh datasets area: {dd: bytes}, RETURN-CODE or ABEND, and FAULTS."""
    datasets = area / "datasets"
    datasets.mkdir(parents=True, exist_ok=True)
    for dd, spec in case["datasets"].items():  # a sequential input is a file the program opens itself
        if "input" in spec and not spec.get("entity"):
            shutil.copy(inputs / f"{dd}.in", datasets / dd)
    sysout = area / "out" / "SYSOUT"  # #4056: what the port DISPLAYs (the generated Sysout appends to it)
    sysout.parent.mkdir(parents=True, exist_ok=True)
    sysout.unlink(missing_ok=True)
    if case.get("db2"):  # the tables as the seed has them, the Db2 repositories on the harness's Db2
        import equivalence_db2

        equivalence_db2.reset(case, Path("."))
        props = f"{props} {equivalence_db2.java_props(case)}"
        if case["db2"].get("compare_sql"):  # #4507: the run's statements as Db2 answered them (EquivalenceDb2Config)
            sqlout = area / "out" / "sqlout.txt"
            sqlout.unlink(missing_ok=True)
            props = f"{props} -Dgitgalaxy.db2.sqllog={sqlout}"
    if case.get("ims"):  # #4893: the databases the COBOL side was given (equivalence_ims.stage), written back here
        dliout = area / "out" / "dli"
        shutil.rmtree(dliout, ignore_errors=True)
        dliout.mkdir(parents=True)
        props = f"{props} -Dgitgalaxy.dli.dir={dli_dir or inputs / 'dli'} -Dgitgalaxy.dli.out={dliout}"
    if case.get("mvs_step") is not None:  # #5856 (A2): the job step whose control blocks DetMvs lays
        props = f"{props} -Dgitgalaxy.mvs.step={case['mvs_step']}"
    if case.get("sysin") is not None and "-Dequivalence.sysin=" not in props:  # #5106: what the COBOL side read
        props = f"{props} -Dequivalence.sysin={inputs / 'SYSIN.in'}"
    out = run_maven(
        project, area, inputs, env, f"{props} -Dgitgalaxy.sysout={sysout} {data_charset_arg(case)}".strip(), session
    )
    outs = {dd: out / f"{dd}.out" for dd, spec in case["datasets"].items() if spec.get("compare")}
    for extra in ("RETURN-CODE", "ABEND", "FAULTS"):
        outs[extra] = out / extra
    read = {dd: f.read_bytes() for dd, f in outs.items() if f.is_file()}  # a stub may write nothing
    read["SYSOUT"] = sysout.read_bytes() if sysout.is_file() else b""
    if case.get("db2"):
        read.update(equivalence_db2.outputs(case))
        if case["db2"].get("compare_sql"):
            sqlout = area / "out" / "sqlout.txt"
            read["SQL"] = sqlout.read_bytes() if sqlout.is_file() else b""
    for name in (case.get("ims") or {}).get("compare", []):  # #4893: DetDli.leave's databases
        f = area / "out" / "dli" / f"{name}.out"
        read[f"IMS {name}"] = f.read_bytes() if f.is_file() else b""
    for extra in ("RETURN-CODE", "ABEND"):  # a code, not a record: whitespace is not data
        if extra in read:
            read[extra] = read[extra].strip()
    return read
