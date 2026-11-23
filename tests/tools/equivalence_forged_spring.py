"""#8886 slice 2: EXECUTE the forged Spring Batch jobs of a job case and compare each step with the COBOL chain.

`equivalence_forged_job.py` (slice 1) forges a job from the real JCL and REPLAYS its guard. This module runs the Java
the forge GENERATES: the estate's real `<Job>JobConfig` classes and the forge's own runtime (`JclSteps`, `JclConditions`,
`DatasetResolver`, `Dd`), compiled with javac against the Spring Batch 5.1 jars in the local Maven repository and run on
a real `JobRepository` (in-memory H2) and `TaskExecutorJobLauncher`. Each step's Spring exit status (`RC=n`,
`BYPASSED`, or the failure) is then read back and set against what the chain's step did.

The forge here is the REAL one for the estate: skeletons only for the estate's own COBOL programs, `job_steps` /
`job_dds` / `job_sysin` from a scan of the JCL. IDCAMS, SORT and IEFBR14 are the utilities they are, not estate programs
(slice 1's stand-in gave every program name a skeleton, so a utility-only job was forged there; it is NOT generated
here: "listed, not generated", `BatchForge.jobs[].kind == "utility"`, and the report says so per step).

What is stood in, named in the result: a program step calls a stub service whose `runBatch` returns the chain's COBOL
return code for that step (the proven ports are not linked: a later slice). A utility step the forge cannot run
(`steps.utility`) FAILS the job as shipped (`strict`); with `gitgalaxy.batch.skip-unimplemented` it logs and returns 0
(`skip`): both are run and reported, neither is a pass for the chain's answer.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

PKG = "com.gitgalaxy.batch"
REPO = Path(__file__).resolve().parents[2]
M2 = Path.home() / ".m2" / "repository"
# (group path, artifact): the jars a generated job needs to compile and run on a real JobRepository.
_JARS = [
    ("org/springframework/batch", "spring-batch-core"), ("org/springframework/batch", "spring-batch-infrastructure"),
    ("org/springframework", "spring-beans"), ("org/springframework", "spring-context"),
    ("org/springframework", "spring-core"), ("org/springframework", "spring-jcl"), ("org/springframework", "spring-tx"),
    ("org/springframework", "spring-jdbc"), ("org/springframework", "spring-aop"),
    ("org/springframework", "spring-expression"), ("org/springframework/retry", "spring-retry"),
    ("io/micrometer", "micrometer-core"), ("io/micrometer", "micrometer-commons"),
    ("io/micrometer", "micrometer-observation"), ("org/slf4j", "slf4j-api"), ("com/h2database", "h2"),
    ("aopalliance", "aopalliance"), ("com/fasterxml/jackson/core", "jackson-databind"),
    ("com/fasterxml/jackson/core", "jackson-core"), ("com/fasterxml/jackson/core", "jackson-annotations"),
    ("com/fasterxml/jackson/datatype", "jackson-datatype-jsr310"),
]  # fmt: skip
_OPTIONAL = {"aopalliance", "jackson-datatype-jsr310", "spring-retry"}

DRIVE = """package {pkg};

import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import org.springframework.batch.core.Job;
import org.springframework.batch.core.JobExecution;
import org.springframework.batch.core.JobParametersBuilder;
import org.springframework.batch.core.StepExecution;
import org.springframework.batch.core.launch.support.TaskExecutorJobLauncher;
import org.springframework.batch.core.repository.JobRepository;
import org.springframework.batch.core.repository.support.JobRepositoryFactoryBean;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;
import org.springframework.transaction.PlatformTransactionManager;

/** args: datasets dir, skip-unimplemented, then one JobConfig class name per job. Prints JOB / STEP lines. */
public final class SpringDrive {
    /** A service the job config takes: the stub (no-arg) or a det-ported SORT (the resolver, file and clock runtime). */
    static Object make(Class<?> t, DatasetResolver resolver) throws Exception {
        Constructor<?> c = t.getDeclaredConstructors()[0];
        Object[] v = new Object[c.getParameterCount()];
        for (int i = 0; i < v.length; i++) {
            Class<?> p = c.getParameterTypes()[i];
            v[i] = p == DatasetResolver.class ? resolver : p == CobolFiles.class ? new CobolFiles("", "")
                    : p == MainframeClock.class ? new MainframeClock("", "") : p.getDeclaredConstructor().newInstance();
        }
        return c.newInstance(v);
    }

    public static void main(String[] a) throws Exception {
        DriverManagerDataSource ds = new DriverManagerDataSource("jdbc:h2:mem:gg;DB_CLOSE_DELAY=-1", "sa", "");
        new ResourceDatabasePopulator(new ClassPathResource("org/springframework/batch/core/schema-h2.sql")).execute(ds);
        PlatformTransactionManager tx = new DataSourceTransactionManager(ds);
        JobRepositoryFactoryBean f = new JobRepositoryFactoryBean();
        f.setDataSource(ds);
        f.setTransactionManager(tx);
        f.afterPropertiesSet();
        JobRepository repo = f.getObject();
        TaskExecutorJobLauncher launcher = new TaskExecutorJobLauncher();
        launcher.setJobRepository(repo);
        launcher.afterPropertiesSet();
        DatasetResolver resolver = new DatasetResolver(a[0]);
        JclSteps steps = new JclSteps(resolver, Boolean.parseBoolean(a[1]));
        for (int i = 2; i < a.length; i++) {
            Object cfg = Class.forName(a[i]).getDeclaredConstructor().newInstance();
            Method m = null;
            for (Method c : cfg.getClass().getDeclaredMethods()) {
                if (Job.class.isAssignableFrom(c.getReturnType())) {
                    m = c;
                }
            }
            List<Object> args = new ArrayList<>();
            for (Class<?> t : m.getParameterTypes()) {
                if (t == JobRepository.class) {
                    args.add(repo);
                } else if (t == PlatformTransactionManager.class) {
                    args.add(tx);
                } else if (t == JclSteps.class) {
                    args.add(steps);
                } else {
                    args.add(make(t, resolver));
                }
            }
            Job job = (Job) m.invoke(cfg, args.toArray());
            JobExecution ex = launcher.run(job, new JobParametersBuilder().addLong("run.id", 1L).toJobParameters());
            System.out.println("JOB\\t" + job.getName() + "\\t" + ex.getStatus() + "\\t" + ex.getExitStatus().getExitCode());
            List<StepExecution> done = new ArrayList<>(ex.getStepExecutions());
            done.sort(Comparator.comparing(StepExecution::getId));
            for (StepExecution s : done) {
                String why = s.getFailureExceptions().isEmpty() ? "-"
                        : s.getFailureExceptions().get(0).getClass().getSimpleName() + ": "
                                + String.valueOf(s.getFailureExceptions().get(0).getMessage()).replace('\\n', ' ');
                System.out.println("STEP\\t" + s.getStepName() + "\\t" + s.getExitStatus().getExitCode() + "\\t" + why);
            }
        }
        System.exit(0);
    }
}
"""

STUB = """package com.gitgalaxy.service;

import com.gitgalaxy.batch.Dd;
import java.util.List;

/** The chain's COBOL return code stands in for the ported program (system property gg.rc.<class>). */
public class {cls} {
    public int runBatch(List<Dd> dds, String parm) {
        return Integer.getInteger("gg.rc.{cls}", 0);
    }
}
"""


def _version_key(p: Path) -> tuple:
    return tuple(int(x) if x.isdigit() else 0 for x in re.split(r"[.\-]", p.parent.name))


def classpath() -> list[Path] | None:
    """The jars of `_JARS` (highest version of each) from the local Maven repository; None when one is missing."""
    jars = []
    for group, art in _JARS:
        found = sorted((M2 / group / art).glob(f"*/{art}-*.jar"), key=_version_key)
        found = [j for j in found if not j.name.endswith(("-sources.jar", "-javadoc.jar"))]
        if found:
            jars.append(found[-1])
        elif art not in _OPTIONAL:
            return None
    return jars


def dcb_facts(jcl_members: dict[str, str], datasets: dict[str, dict]) -> list[dict]:
    """A dataset's stated record format as a `job_dds` row of its job (#8886 slice 5), for a dataset a step reads whose
    own DD states none: CardDemo's TRANSACT KSDS is read by CREASTMT's SORT with no DCB, its RECORDSIZE(350 350) is in
    another job's deck (TRANFILE.jcl), and the forge reads a dataset's DCB only inside its own job. The row has an ordinal
    no step has, so it joins no step's DDs: it only answers `_sort_reclen`'s "same dataset elsewhere in the job"."""
    return [
        {"file": f"jcl/{jcl_members[d['job']]}", "ordinal": -1, "dd": "DCB-" + dsn[-8:], "dsn": dsn,
         "lrecl": d["lrecl"], "recfm": d["recfm"]}
        for dsn, d in datasets.items()
    ]  # fmt: skip


def seed_datasets(datasets: dict[str, dict], root: Path) -> None:
    """Write each seeded input dataset as the file the DatasetResolver finds under `root` (DSN = file name): the seed's
    lines as `lrecl`-byte fixed records with no line ending, the form a RECFM=F(B) dataset has."""
    for dsn, d in datasets.items():
        if d.get("seed"):
            lines = (REPO / d["seed"]).read_bytes().split(b"\n")
            recs = [ln for ln in lines if ln]
            if any(len(r) != d["lrecl"] for r in recs):
                raise ValueError(f"{d['seed']}: a record is not {d['lrecl']} bytes")
            (root / dsn).write_bytes(b"".join(recs))


def forge_estate(
    ir,
    corpus: Path,
    cbl_dir: str,
    jcl_members: dict[str, str],
    package: str = "com.gitgalaxy",
    datasets=None,
    utility_jobs=(),
):
    """The real forge over the estate: skeletons for the corpus's own COBOL programs, the scan's job rows.

    `utility_jobs` (#8886 slice 6) names utility-only jobs (IDCAMS / SORT steps, no program) to generate anyway. The
    forge lists those and generates none, by design (`BatchForge` docstring); here each is planned as an application
    job so its steps RUN under Spring and the forge's own named refusal for each step is read back, not assumed. The
    forge is untouched: only the classification of the named jobs is overridden, and the job keeps `forged_utility`."""
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_batch_forge import BatchForge as _Forge
    from gitgalaxy.tools.cobol_to_java.java_target import load_target

    files = {f"jcl/{m}" for m in jcl_members.values()}
    steps = [f for f in ir.job_steps() if f["file"] in files]
    dds = [d for d in ir.job_dds() if d["file"] in files]
    sysin = [d for d in ir.job_sysin() if d["file"] in files]
    dds += dcb_facts(jcl_members, datasets or {})
    progs = sorted(p.stem.upper() for p in (corpus / cbl_dir).iterdir() if p.suffix.lower() == ".cbl")
    skeletons = {p: {"program": {"program_ids": [p], "file": f"cbl/{p}.cbl"}} for p in progs}
    sections = {
        "job_steps": {"facts": steps},
        "job_dds": {"facts": dds},
        "job_sysin": {"facts": sysin},
    }
    names = set(utility_jobs)

    class BatchForge(_Forge):
        def _plan(self, j, dds):
            job = super()._plan(j, dds)
            job.forged_utility = job.kind == "utility" and job.job in names
            if job.forged_utility:
                job.kind, job.reason = "application", f"utility-only, forged on request ({job.reason})"
            return job

    return BatchForge(skeletons, {"sections": sections}, package, load_target(None))


def _kind(job) -> str:
    return "utility (forged)" if getattr(job, "forged_utility", False) else job.kind


def _service_class(key: str) -> str:
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_names import java_class_base

    return java_class_base(key) + "Service"


def run_forged(
    forge, rc_by_step: dict[tuple[str, str], int | None], datasets: Path, work: Path, seeds: dict | None = None
) -> dict | None:
    """Compile the forge's generated sources and run every generated job, strict and skip-unimplemented.

    `rc_by_step[(job, jcl step)]` is the chain's return code for a program step (the stub service returns it).
    Returns {mode: {job: {"status", "exit", "steps": {name: (exit code, failure)}}}, "datasets": {mode: {file: {size,
    sha256}}}} or None without Spring jars. `seeds` are the input datasets written before each run (`seed_datasets`)."""
    jars = classpath()
    if jars is None or not shutil.which("javac") or not shutil.which("java"):
        return None
    sources = forge.sources()
    src = sources[("base_pkg", "batch")]
    srcdir = work / "src"
    for (
        _,
        where,
    ), group in sources.items():  # the batch classes, and the IDCAMS twin (cobolrt/job) when a step runs it
        for name, text in group.items():
            if name == "BatchJobController":  # the REST endpoint: needs spring-web, not part of a job's run
                continue
            d = srcdir / "com/gitgalaxy" / where
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{name}.java").write_text(text, "utf-8")
    sd = srcdir / "com/gitgalaxy/service"
    sd.mkdir(parents=True, exist_ok=True)
    if any(n.startswith("Dfsort") for n in sources.get(("base_pkg", "service"), {})):
        # a det-ported SORT imports CobolRecords, which the whole-estate forge (SkeletonForges) emits beside the entities
        from gitgalaxy.tools.cobol_to_java.cobol_to_java_repository_forge import RepositoryForge

        rec = RepositoryForge({}, {}, forge.package, forge.target).records_source(needed=True)
        (srcdir / "com/gitgalaxy/entity/vsam").mkdir(parents=True, exist_ok=True)
        (srcdir / "com/gitgalaxy/entity/vsam/CobolRecords.java").write_text(rec or "", "utf-8")
    rcs: dict[str, int] = {}
    for job in forge.applications:
        for st in job.steps:
            if st.key is None:
                continue
            cls = _service_class(st.key)
            want = rc_by_step.get((job.job, st.jcl)) or 0
            if rcs.setdefault(cls, want) != want:
                raise RuntimeError(f"{cls}: two steps ask for different return codes ({rcs[cls]}, {want})")
            (sd / f"{cls}.java").write_text(STUB.replace("{cls}", cls), "utf-8")
    (srcdir / "com/gitgalaxy/batch/SpringDrive.java").write_text(DRIVE.replace("{pkg}", PKG), "utf-8")
    cp = ":".join(map(str, jars))
    classes = work / "classes"
    classes.mkdir()
    files = [str(p) for p in srcdir.rglob("*.java")]
    r = subprocess.run(["javac", "-encoding", "UTF-8", "-cp", cp, "-d", str(classes), *files],
                       capture_output=True, text=True, encoding="utf-8")  # fmt: skip
    if r.returncode:
        raise RuntimeError(r.stderr[-4000:])
    configs = [f"{PKG}.{n}" for n in src if n.endswith("JobConfig")]
    out: dict[str, dict] = {}
    for mode, skip in (("strict", "false"), ("skip", "true")):
        ds = datasets / mode
        ds.mkdir(parents=True)
        seed_datasets(seeds or {}, ds)
        cmd = ["java", "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", *(f"-Dgg.rc.{c}={v}" for c, v in rcs.items()),
               "-cp", f"{classes}:{cp}", f"{PKG}.SpringDrive", str(ds), skip, *configs]  # fmt: skip
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=300)
        if r.returncode:
            raise RuntimeError(r.stderr[-4000:])
        jobs: dict[str, dict] = {}
        cur = None
        for ln in r.stdout.splitlines():
            f = ln.split("\t")
            if f[0] == "JOB":
                cur = jobs[f[1]] = {"status": f[2], "exit": f[3], "steps": {}}
            elif f[0] == "STEP" and cur is not None:
                cur["steps"][f[1]] = (f[2], None if f[3] == "-" else f[3])
        out[mode] = jobs
        # what the jobs left in the datasets directory (size and digest: the run's own files, compared by the caller)
        files = {p.name: {"size": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                 for p in sorted(ds.iterdir()) if p.is_file()}  # fmt: skip
        out.setdefault("datasets", {})[mode] = files
    return out


def _not_run(forge, job, jcl_step: str) -> str | None:
    """Why the forge runs no code for this step (its own `steps.utility` TODO), None when it runs one."""
    for st in job.steps:
        if st.jcl == jcl_step:
            todo = forge._step_todo(st)
            return todo.split(": ", 1)[-1] if todo else None
    return None


def compare_run(forge, spec: dict, rcs: dict, ran: set[str], run: dict) -> list[dict]:
    """Per case step, what each Spring run did against what the chain did. `rcs` is `chain_rcs(report)`, `ran` the
    case steps IBM reached."""
    kinds = {j.job: j for j in forge.jobs}
    rows = []
    for m in spec["steps"]:
        cname = m["case"]
        job = kinds[m["job"]]
        want = f"RC={rcs[cname]}" if cname in ran and rcs.get(cname) is not None else None
        row = {"case": cname, "job": m["job"], "jcl_steps": m["jcl_steps"], "kind": _kind(job), "modes": {}}
        for mode in ("strict", "skip"):
            issues: list[str] = []
            if job.kind != "application":
                issues.append(f"no forged job: {m['job']} is a {job.kind} job ({job.reason}), listed not generated")
                row["modes"][mode] = {"status": "no forged job", "issues": issues, "got": {}}
                continue
            jr = run[mode][m["job"]]
            got = {}
            for j in m["jcl_steps"]:
                code, why = jr["steps"].get(j, (None, None))
                got[j] = code or "not started"
                if code is None:
                    issues.append(f"{j}: not started (job {jr['status']} before it)")
                elif code == "FAILED":
                    issues.append(f"{j}: failed: {why}")
                elif cname not in ran:
                    if code != "BYPASSED":
                        issues.append(f"{j}: forged job ran it ({code}), the chain never reached it")
                elif mode == "skip" and (why := _not_run(forge, job, j)):
                    # skip-unimplemented returns 0 for a step the forge cannot run: never an RC the chain's answer matches
                    issues.append(f"{j}: not run, skip-unimplemented returned {code}: {why}")
                elif want is not None and code != want:
                    issues.append(f"{j}: forged {code}, chain {want}")
            row["modes"][mode] = {
                "status": "differs" if issues else "equal", "issues": issues, "got": got, "job": jr["status"],
            }  # fmt: skip
        rows.append(row)
    return rows


def scan_and_run(spec: dict, case: dict, report: dict, corpus: Path, chain_rcs) -> dict | None:
    """The whole slice-2 run for one job case; None when Spring or a JDK is missing."""
    from gitgalaxy.tools.cobol_to_cobol.galaxy_ir import load_galaxy_ir, scan_to_db

    work = Path(tempfile.mkdtemp(prefix="forged-spring-"))
    try:
        estate = work / "estate"
        for sub, d in (("jcl", spec["jcl_dir"]), ("proc", spec["proc_dir"])):
            shutil.copytree(corpus / d, estate / sub)
        ir = load_galaxy_ir(scan_to_db(estate, work / "scan"))
        forge = forge_estate(
            ir,
            corpus,
            spec.get("cbl_dir", "app/cbl"),
            spec["jobs"],
            datasets=spec.get("datasets"),
            utility_jobs=spec.get("forge_utility_jobs", ()),
        )
        rcs = chain_rcs(report)
        ran = {s["case"] for s in case["steps"]} - set((report.get("ibm_stop") or {}).get("not_reached") or [])
        # a program step's stub returns the RC of the case step that covers it
        rc_by_step = {(m["job"], j): rcs.get(m["case"]) for m in spec["steps"] for j in m["jcl_steps"]}
        run = run_forged(forge, rc_by_step, work / "datasets", work / "build", spec.get("datasets"))
        if run is None:
            return None
        rows = compare_run(forge, spec, rcs, ran, run)
        return {
            "rows": rows,
            "jobs": {j.job: {"kind": _kind(j), "reason": j.reason} for j in forge.jobs},
            "raw": run,
            "idcams_lowered": sorted(  # the steps the forge runs through the IDCAMS model, not a copy or `utility`
                f"{j.job}.{st.jcl}" for j in forge.applications for st in j.steps if st.idcams_deck
            ),
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


def render(res: dict, case_name: str) -> list[str]:
    out = []
    for r in res["rows"]:
        for mode in ("strict", "skip"):
            md = r["modes"][mode]
            out.append(
                f"{case_name} executed step {r['case']} [{r['job']}.{'+'.join(r['jcl_steps'])}] {mode}: {md['status']}"
            )
            out += [f"    differs: {i}" for i in md["issues"]]
    for mode in ("strict", "skip"):
        n = sum(r["modes"][mode]["status"] == "equal" for r in res["rows"])
        out.append(
            f"{case_name}: executed Spring jobs equal to the chain over {n} of {len(res['rows'])} steps ({mode})"
        )
    return out
