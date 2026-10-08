# ==============================================================================
# GitGalaxy Tool: JCL job flow -> Spring Batch jobs (#3622)
#
# PURPOSE:
# Most JCL in an estate is not application work: it compiles (IGYCRCTL), links (HEWL /
# IEWL), assembles, translates, updates the CSD, drives a workload simulator. Each job
# is classified from its steps (job_steps, PROC calls expanded):
#
#   application   runs a program of the estate (EXEC PGM=, or through a PROC)
#                 -> a Spring Batch Job;
#   runner        runs IKJEFT01 / IKJEFT1B / DFSRRC00 and what it runs is not known -- a
#                 SYSTSIN member not in the repository, a REXX / CLIST exec -- listed, not
#                 generated. #3710: a runner step whose program the engine resolved
#                 (job_steps `runner_programs`: SYSTSIN RUN PROGRAM / CALL, DFSRRC00 PARM)
#                 counts as that program: an estate program makes the job an
#                 application job, an IBM utility (DSNTEP2, DSNTIAD) a utility job;
#   utility       only data utilities (IDCAMS, IEBGENER, SORT, IEFBR14, ...) --
#                 VSAM defines, loads, copies: listed, not generated;
#   build         compilers, linkers, CSD updates, tooling -- listed, not generated.
#
# The listing is resources/batch/jcl-jobs.json. An application job becomes one
# `<Job>JobConfig` (@Configuration, one @Bean Job, its steps in JCL order, a PROC's
# steps expanded as `STEP.PROCSTEP`) over a small runtime in the batch package:
#   Dd / DatasetResolver  each step's DDs (job_dds) and datasets as files under
#                         gitgalaxy.datasets.directory, GDG generations kept apart;
#   JclConditions         COND= (step and job) and IF / THEN / ELSE, evaluated against
#                         the return codes of the steps before -- a satisfied COND
#                         bypasses the step, as JCL does;
#   JclSteps              the tasklets: a program step calls its service's `runBatch(dds, parm)`
#                         and records RETURN-CODE; IEFBR14 creates / deletes datasets per
#                         their DISP; IEBGENER copies SYSUT1 to SYSUT2; any other utility
#                         (SORT, IDCAMS, ...) fails the job unless
#                         gitgalaxy.batch.skip-unimplemented -- never a silent success;
#   JclJobLauncher        runs a job by its JCL name (the REST endpoint, and the programs
#                         that submit jobs through the internal reader: job_submissions);
#   CobolFiles / CobolAbend  a ported program's FILE STATUS per I/O statement and its abends
#                         (#4023 follow-up), with the equivalence harness's fault plan.
# ==============================================================================
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from gitgalaxy.tools.cobol_to_java.cobol_to_java_common import TraceLog, java_path, status_text
from gitgalaxy.tools.cobol_to_java.cobol_to_java_names import java_class_base
from gitgalaxy.tools.cobol_to_java.java_target import JavaTarget, record_charset_java

SUBPACKAGE = "batch"
# IBM's PL/I compiler, spelled in two parts: its name holds the two-byte DOS executable
# signature, which the X-Ray Inspector flags in a file's first 8 KB.
_PLI_COMPILER = "IBM" + "ZPLI"
BUILD_PROGRAMS = frozenset({
    "IGYCRCTL", "IGYCRCTL2", "HEWL", "IEWL", "IEWBLINK", "HEWLH096", "HEWLKED", "ASMA90", "IEV90",
    "DFHECP1$", "DFHEAP1$", "DFHEPP1$", "DFHEDP1$", _PLI_COMPILER, "IEL0AA", "IEL1AA", "DSNHPC", "DSNHPSM",
    "DSNHLI", "DFHCSDUP", "DFHMAPS", "EYU9XDUT", "EYU9XECS", "IEBCOPY", "SDSF", "BPXBATCH", "ITPSTL",
    "ITPENTER", "ITPLL", "IEBUPDTE", "AMBLIST", "IKJEFT1A",
})  # fmt: skip
RUNNERS = frozenset({"IKJEFT01", "IKJEFT1B", "DFSRRC00", "DFSRRC0"})
COPY = frozenset({"IEBGENER", "ICEGENER"})
SORTS = frozenset({"SORT", "DFSORT", "ICEMAN", "SYNCSORT", "ICETOOL"})


@dataclass
class Step:
    jcl: str  # the step's JCL name (STEP or STEP.PROCSTEP)
    name: str  # unique Spring Batch step name
    program: str | None
    cond: str | None
    if_cond: str | None
    line: int | None
    ordinal: int
    proc_step: str | None
    dds: list[dict] = field(default_factory=list)
    key: str | None = None  # the estate program's skeleton key
    runner: str | None = None  # #3710: the runner (IKJEFT01, DFSRRC00) that runs `program`
    via: str | None = None  # how: RUN PROGRAM / TSO CALL / DFSRRC00
    unresolved: str | None = None  # what the runner runs, when not a known program
    commands_only: bool = False  # a TSO runner running commands (DSN FREE / BIND, RACF), no program
    parm: str | None = None  # #3624: the text EXEC PARM= passes the program


@dataclass
class Job:
    file: str
    job: str
    cond: str | None
    kind: str
    reason: str
    steps: list[Step]
    cls: str = ""
    spring: str = ""  # the Spring Batch job name


def _jstr(v: Any) -> str:
    if v is None:
        return "null"
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


class BatchForge:
    """Plans every JCL job: classified, and the application ones as Spring Batch jobs."""

    def __init__(self, skeletons: dict[str, dict], estate: dict, package: str, target: JavaTarget,
                 trace: TraceLog | None = None) -> None:  # fmt: skip
        self.package, self.target, self.trace = package, target, trace
        self.enabled = target.features.batch
        sections = estate.get("sections") or {}
        self.status = status_text(sections.get("job_steps"))
        self.programs: dict[str, str] = {}  # PROGRAM-ID / stem -> skeleton key
        # A main program no JCL step names (CardDemo's CBTRN01C): files of its own, a PROCEDURE DIVISION with no
        # USING and no COMMAREA -- it is still a batch step, run by JCL the estate does not hold.
        self.unscheduled: set[str] = set()
        self.lineage: dict[str, list[dict]] = {}
        self.submissions: dict[str, list[dict]] = {}
        for key, sk in skeletons.items():
            prog = sk.get("program") or {}
            for pid in [*prog.get("program_ids", []), key]:
                self.programs.setdefault(str(pid).upper(), key)
            secs = sk.get("sections") or {}
            entries = (secs.get("entry_points") or {}).get("facts", [])
            itf = (secs.get("interface") or {}).get("facts") or {}
            if ((secs.get("file_control") or {}).get("facts") and entries
                    and all(e.get("kind") == "PROCEDURE" and not e.get("params") for e in entries)
                    and not (itf.get("commarea") if isinstance(itf, dict) else None)
                    and not (secs.get("cics_tasks") or {}).get("facts")):  # fmt: skip
                self.unscheduled.add(key)
            self.lineage[key] = (secs.get("dataset_lineage") or {}).get("facts", [])
            self.submissions[key] = [s for s in (secs.get("job_submissions") or {}).get("facts", [])
                                     if s.get("submitter") == prog.get("file")]  # fmt: skip
        dds: dict[tuple[str, int, str | None], list[dict]] = {}
        for d in (sections.get("job_dds") or {}).get("facts", []):
            dds.setdefault((d["file"], d["ordinal"], d.get("proc_step")), []).append(d)
        self.flows = (sections.get("job_dataset_flow") or {}).get("facts", [])
        self.jobs = [self._plan(j, dds) for j in (sections.get("job_steps") or {}).get("facts", [])]
        taken: set[str] = set()
        for j in self.jobs:
            base = java_class_base(j.job or j.file.rsplit("/", 1)[-1].split(".")[0]) + "JobConfig"
            name, n = base, 1
            while name in taken:
                n += 1
                name = f"{base[: -len('JobConfig')]}{n}JobConfig"
            taken.add(name)
            j.cls = name
        # A JCL job name is not unique across files (nor is it a Spring bean name): the Spring Batch
        # job carries it, suffixed with its file's stem when another generated job has it too.
        names = [j.job for j in self.applications]
        for j in self.applications:
            j.spring = j.job if names.count(j.job) == 1 else f"{j.job}#{j.file.rsplit('/', 1)[-1].split('.')[0]}"
        self.by_file = {j.file: j for j in self.applications}

    @property
    def applications(self) -> list[Job]:
        return [j for j in self.jobs if j.kind == "application"] if self.enabled else []

    def _plan(self, j: dict, dds: dict) -> Job:
        steps: list[Step] = []
        for s in j["steps"]:
            inner = s.get("expands_to") if s.get("proc") else None
            for ps in inner if inner is not None else [s]:
                jcl = f"{s['step']}.{ps['step']}" if inner is not None else s["step"]
                prog = (ps.get("program") or "").upper() or None
                st = Step(jcl, jcl, prog, ps.get("cond"), ps.get("if_cond"), s.get("line"), s["ordinal"],
                          ps["step"] if inner is not None else None,
                          dds.get((j["file"], s["ordinal"], ps["step"] if inner is not None else None), []),
                          self.programs.get(prog or ""))  # fmt: skip
                st.parm = ps.get("parm")
                self._through_runner(st, ps.get("runner_programs") or [])
                steps.append(st)
        names = [st.jcl for st in steps]
        for st in steps:
            if names.count(st.jcl) > 1:
                st.name = f"{st.jcl}#{st.ordinal}"
        # A TSO runner running commands only (DSN FREE / BIND, RACF) is utility work, not an unknown program.
        progs: set[str] = {st.program for st in steps if st.program is not None and not st.commands_only}
        progs |= {f"{st.program} (TSO commands)" for st in steps if st.commands_only}
        if any(st.key for st in steps):
            run = sorted({st.program or "?" for st in steps if st.key})
            kind, reason = "application", f"runs {', '.join(run)}"
        elif progs & RUNNERS:
            open_ = sorted({f"{st.program} ({st.unresolved})" for st in steps if st.program in RUNNERS
                            and not st.commands_only})  # fmt: skip
            kind, reason = "runner", f"runs {', '.join(open_)}"
        elif progs and progs <= (BUILD_PROGRAMS | {p for p in progs if p.startswith("&")}):
            kind, reason = "build", f"builds / installs ({', '.join(sorted(progs))})"
        elif progs and not (progs & BUILD_PROGRAMS):
            kind, reason = "utility", f"data utilities only ({', '.join(sorted(progs))})"
        else:
            kind, reason = "build", f"tooling ({', '.join(sorted(progs)) or 'no program'})"
        return Job(j["file"], j.get("job") or "", j.get("cond"), kind, reason, steps)

    def _through_runner(self, st: Step, runs: list[dict]) -> None:
        """#3710: a runner step runs the program its SYSTSIN / PARM names -- the estate program
        when one resolves, else the first load module it runs (an IBM utility: DSNTEP2); a runner
        whose program is not known keeps its own name, with what is missing in `unresolved`."""
        tso = st.program in RUNNERS and st.program != "DFSRRC00" and st.program != "DFSRRC0"
        if st.program not in RUNNERS:
            return
        if not runs:
            st.unresolved = "no SYSTSIN in the step" if tso else "no PARM program"
            return
        if all(r.get("via") == "TSO commands" for r in runs):
            st.commands_only = True
            st.unresolved = "TSO commands only (no RUN PROGRAM, CALL or EXEC)"
            return
        modules = [r for r in runs if r.get("program") and r.get("via") != "TSO EXEC"]
        estate = next((r for r in modules if self.programs.get(str(r["program"]).upper())), None)
        pick = estate or (modules[0] if modules else None)
        if pick is not None:
            st.runner, st.via, st.program = st.program, pick.get("via"), str(pick["program"]).upper()
            st.key = self.programs.get(st.program)
            return
        member = next((r.get("member") for r in runs if r.get("member") and not r.get("program")), None)
        execs = [r["program"] for r in runs if r.get("via") == "TSO EXEC" and r.get("program")]
        st.unresolved = (f"SYSTSIN member {member} is not in the repository" if member
                         else f"the REXX / CLIST exec {', '.join(execs)}" if execs else "nothing resolved")  # fmt: skip

    # ---- sources ------------------------------------------------------------------------------
    def sources(self) -> dict[tuple[str, ...], dict[str, str]]:
        if not self.applications:
            return {}
        pkg = f"{self.package}.{SUBPACKAGE}"
        out = {
            name: text.replace("{pkg}", pkg)
            .replace("{zone}", self.target.culture.zone)
            .replace("{record_charset}", record_charset_java(self.target.data.record_charset))
            for name, text in _RUNTIME.items()
        }
        if self.target.features.rest_controllers:
            out["BatchJobController"] = _CONTROLLER.replace("{pkg}", pkg)
        for j in self.applications:
            out[j.cls] = self._job_source(j)
        return {("base_pkg", SUBPACKAGE): out}

    def resources(self) -> dict[str, str]:
        if not self.enabled or not self.jobs:
            return {}
        rows = [{"job": j.job, "file": j.file, "kind": j.kind, "reason": j.reason,
                 "generated": j.cls if j.kind == "application" else None, "spring_job": j.spring or None,
                 "steps": [{"step": s.jcl, "program": s.program} for s in j.steps]} for j in self.jobs]  # fmt: skip
        return {"batch/jcl-jobs.json": json.dumps(rows, indent=2) + "\n"}

    def _flows_of(self, j: Job) -> list[str]:
        out = []
        for e in self.flows:
            p, c = e["producer"], e["consumer"]
            if c["file"] == j.file and p["file"] != j.file:
                out.append(f"reads {e['dataset']} (step {c['step']}), produced by {p['file']} step {p['step']}")
            elif p["file"] == j.file and c["file"] != j.file:
                out.append(f"produces {e['dataset']} (step {p['step']}), read by {c['file']} step {c['step']}")
        return sorted(set(out))

    def _job_source(self, j: Job) -> str:
        pkg = f"{self.package}.{SUBPACKAGE}"
        services = sorted({st.key for st in j.steps if st.key})  # type: ignore[type-var]
        imports = {"org.springframework.batch.core.Job", "org.springframework.batch.core.job.builder.JobBuilder",
                   "org.springframework.batch.core.repository.JobRepository",
                   "org.springframework.batch.core.step.builder.StepBuilder",
                   "org.springframework.context.annotation.Bean", "org.springframework.context.annotation.Configuration",
                   "org.springframework.transaction.PlatformTransactionManager", "java.util.List"}  # fmt: skip
        imports |= {f"{self.package}.service.{java_class_base(k)}Service" for k in services}
        params = ["JobRepository jobRepository", "PlatformTransactionManager tx", "JclSteps steps"]
        params += [f"{java_class_base(k)}Service {self._var(k)}" for k in services]
        flows = self._flows_of(j)
        doc = [f"/** JCL job {j.job} ({j.file}) as a Spring Batch job (#3622): its steps in JCL order,",
               " *  each bypassed when its COND= (or the job's) is satisfied, as JCL does."]  # fmt: skip
        if j.cond:
            doc.append(f" *  JOB COND={j.cond}.")
        doc += [f" *  Dataset flow: {f}." for f in flows]
        doc.append(f" *  JCL job flow field testing: {self.status}. */")
        java = [f"package {pkg};\n"] + [f"import {i};" for i in sorted(imports)] + [""] + doc
        java += ["@Configuration", f"public class {j.cls} {{\n"]
        for st in j.steps:
            java.append(f"    static final List<Dd> DDS_{self._const(st.name)} = List.of({self._dds(st)});")
        java.append("")
        bean = j.cls[0].lower() + j.cls[1 : -len("Config")]  # unique, as the class is
        java += ["    @Bean", f"    public Job {bean}({', '.join(params)}) {{",
                 f"        return new JobBuilder({_jstr(j.spring)}, jobRepository)"]  # fmt: skip
        for i, st in enumerate(j.steps):
            verb = ".start" if i == 0 else ".next"
            java.append(f"                {verb}(new StepBuilder({_jstr(st.name)}, jobRepository)")
            java.append(f"                        .tasklet({self._tasklet(j, st)}, tx).build())")
        java += ["                .build();", "    }", "}"]
        if self.trace:
            path = java_path(self.package, SUBPACKAGE, j.cls)
            self.trace.record(path, "Class", "batch-job", [{"source": f"{j.file}", "section": "job_steps",
                                                            "item": f"JOB {j.job}"}])  # fmt: skip
            for st in j.steps:
                todo = self._step_todo(st)
                self.trace.record(path, f"{j.cls}#{st.name}", "batch-step",
                                  [{"source": f"{j.file}:{st.line}", "section": "job_steps",
                                    "item": f"{st.jcl} EXEC {st.program or '?'}"}], [todo] if todo else [])  # fmt: skip
        return "\n".join(java) + "\n"

    @staticmethod
    def _const(name: str) -> str:
        return re.sub(r"[^A-Z0-9]", "_", name.upper())

    @staticmethod
    def _var(key: str) -> str:
        base = java_class_base(key) + "Service"
        return base[0].lower() + base[1:]

    @staticmethod
    def _dds(st: Step) -> str:
        return ", ".join(f"new Dd({_jstr(d['dd'])}, {_jstr(d.get('dsn'))}, {_jstr(d.get('disp'))}, "
                         f"{_jstr(d.get('disp_normal'))}, {_jstr(d.get('generation'))})"
                         for d in st.dds if d.get("dd"))  # fmt: skip

    def _step_todo(self, st: Step) -> str | None:
        p = st.program or "?"
        if st.key or p in ("IEFBR14", *COPY):
            return None
        if p in RUNNERS and st.commands_only:
            return (
                f"TODO: {st.jcl} runs {p} with TSO commands only (DSN FREE / BIND, RACF, ...) -- a utility step to port"
            )
        if p in RUNNERS:
            return f"TODO: {st.jcl} runs {p}, running {st.unresolved} -- a utility step to port"
        if st.runner:
            return f"TODO: {st.jcl} runs the utility {p} through {st.runner} ({st.via}) -- a utility step to port"
        return f"TODO: {st.jcl} runs the utility {p} (its control statements are in SYSIN) -- a utility step to port"

    def _tasklet(self, j: Job, st: Step) -> str:
        consts = f"DDS_{self._const(st.name)}"
        head = f"{_jstr(st.name)}, {_jstr(st.jcl)}, {_jstr(j.cond)}, {_jstr(st.cond)}, {_jstr(st.if_cond)}"
        if st.key:
            return f"steps.program({head}, () -> {self._var(st.key)}.runBatch({consts}, {_jstr(st.parm)}))"
        if st.program == "IEFBR14":
            return f"steps.iefbr14({head}, {consts})"
        if st.program in COPY:
            return f"steps.copy({head}, {consts})"
        todo = self._step_todo(st) or ""
        return f"steps.utility({head}, {_jstr(st.program)}, {_jstr(todo.split(': ', 1)[-1])})"

    # ---- services -------------------------------------------------------------------------------
    def has_entry(self, key: str) -> bool:
        """#4342: whether the program gets a batch entry (runBatch): a JCL step runs it, or it is a main program of
        an estate with JCL jobs that no step names. Only where the batch runtime is generated: a JCL-free estate's
        file programs keep their upload controllers (#3992)."""
        runs = any(st.key == key for j in self.applications for st in j.steps)
        return runs or (bool(self.applications) and key in self.unscheduled)

    def service_extras(self, key: str) -> dict[str, Any] | None:
        runs = [(j, st) for j in self.applications for st in j.steps if st.key == key]
        subs = self.submissions.get(key, []) if self.enabled else []
        unscheduled = bool(self.applications) and not runs and key in self.unscheduled
        if not runs and not subs and not unscheduled:
            return None
        pkg = f"{self.package}.{SUBPACKAGE}"
        imports: list[str] = []
        methods: list[str] = []
        fields: list[tuple[str, str]] = []
        if runs or unscheduled:
            imports += [f"import {pkg}.Dd;", "import java.util.List;"]
            where = "; ".join(f"job {j.job} step {st.jcl} ({j.file}:{st.line})"
                              + (f" through {st.runner} ({st.via})" if st.runner else "") for j, st in runs)  # fmt: skip
            where = where or "no JCL step in this estate (a main program with files of its own: its JCL is elsewhere)"
            lin = self.lineage.get(key, [])
            dd_doc = sorted({f"{x['dd_name']} ({'/'.join(x.get('modes') or [])}) -> {x.get('dataset') or x.get('dsn') or '?'}"
                             for x in lin if x.get("dd_name")})  # fmt: skip
            todo = "TODO: port the PROCEDURE DIVISION main line; return its RETURN-CODE"
            methods += [f"    /** The batch entry (#3622): run by {where}.",
                        "     *  `dds` are the step's DD statements (DatasetResolver maps each to its file); `parm` the",
                        "     *  text its EXEC PARM= passes (null without one) -- a PROCEDURE DIVISION USING area's data."]  # fmt: skip
            methods += [f"     *  DD {d}." for d in dd_doc[:12]]
            methods += [f"     *  {todo}.", f"     *  JCL job flow field testing: {self.status}. */",
                        "    public int runBatch(List<Dd> dds, String parm) {", "        return 0;", "    }\n"]  # fmt: skip
            if self.trace:
                self.trace.record(java_path(self.package, "service", f"{java_class_base(key)}Service"),
                                  f"{java_class_base(key)}Service#runBatch", "batch-entry",
                                  [{"source": f"{j.file}:{st.line}", "section": "job_steps",
                                    "item": f"{j.job} {st.jcl}"} for j, st in runs], [todo])  # fmt: skip
        for s in subs:
            targets = [r for r in s.get("runs", []) if r.get("resolves_to") in self.by_file and r.get("kind") == "JOB"]
            name = "submit" + java_class_base("_".join(s.get("jobs") or ["job"])) + f"L{s.get('line')}"
            if targets:
                job = self.by_file[targets[0]["resolves_to"]]
                if not fields:
                    imports.append(f"import {pkg}.JclJobLauncher;")
                    fields.append(("JclJobLauncher", "jclJobLauncher"))
                methods += [f"    /** Submits job {job.job} (#3622): the JCL written to the internal reader at line "
                            f"{s.get('line')} ({', '.join(s.get('evidence') or [])}) runs {job.file}. */",
                            f"    protected void {name}() {{", f"        jclJobLauncher.launch({_jstr(job.spring)});",
                            "    }\n"]  # fmt: skip
            else:
                runs_ = ", ".join(f"{r.get('kind')} {r.get('name')} ({r.get('resolves_to') or 'unresolved'})"
                                  for r in s.get("runs", [])) or "nothing resolved"  # fmt: skip
                todo = (f"TODO: this program submits job {', '.join(s.get('jobs') or ['?'])} through the internal "
                        f"reader, which runs {runs_}: no generated job matches -- launch its steps")  # fmt: skip
                methods += [f"    /** Job submission at line {s.get('line')} (#3622). {todo}. */",
                            f"    protected void {name}() {{", "    }\n"]  # fmt: skip
        return {"imports": imports, "fields": fields, "methods": methods}

    def audit_line(self) -> str:
        kinds = [j.kind for j in self.jobs]
        steps = sum(len(j.steps) for j in self.applications)
        todo = sum(1 for j in self.applications for st in j.steps if self._step_todo(st))
        return (f"  • Batch jobs (#3622)       : {len(self.jobs)} JCL jobs -- {kinds.count('application')} application "
                f"(generated: {steps} steps, {todo} utility steps to port), {kinds.count('runner')} runner, "
                f"{kinds.count('utility')} utility, {kinds.count('build')} build (resources/batch/jcl-jobs.json)\n")  # fmt: skip


_RUNTIME = {
    "Sysout": """package {pkg};

import java.io.IOException;
import java.io.UncheckedIOException;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.charset.Charset;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;

/**
 * The job log (#4056): a COBOL `DISPLAY` is `Sysout.display(...)` -- one line, its operands' text concatenated
 * exactly as IBM Enterprise COBOL writes them -- not a log line. SYSOUT is what operators read and scripts parse,
 * and the equivalence harness compares it line by line (trailing blanks aside). Written to standard output, or
 * appended to the file named by the system property gitgalaxy.sysout. #4691: the bytes are written in the record
 * charset (system property gitgalaxy.data.charset, else the target's data.record_charset), never UTF-8: a byte
 * above X'7F' leaves as that one byte, as the COBOL runtime writes it.
 */
public final class Sysout {

    private static final Object LOCK = new Object();
    private static final String POSITIVE = "{ABCDEFGHI";
    private static final String NEGATIVE = "}JKLMNOPQR";

    private Sysout() {
    }

    /** `DISPLAY a b c`: one line. */
    public static void display(Object... operands) {
        write(join(operands) + "\\n");
    }

    /** `DISPLAY a b c WITH NO ADVANCING`: the next DISPLAY continues the line. */
    public static void displayNoAdvancing(Object... operands) {
        write(join(operands));
    }

    /**
     * The text DISPLAY writes for a numeric item that is not edited and has no SIGN SEPARATE: its PICTURE digits
     * (`digits`, of which `scale` decimals), zero-padded, with no decimal point; when `signed`, the sign
     * overpunched in the last digit ({ A-I positive, } J-R negative). The same for a COMP / COMP-3 item, which IBM
     * converts to that external decimal first. PIC S9(3) holding -12 is "01K"; PIC S9(4) COMP holding -7 is "000P".
     */
    public static String number(BigDecimal value, int digits, int scale, boolean signed) {
        BigDecimal v = value == null ? BigDecimal.ZERO : value;
        String d = v.setScale(scale, RoundingMode.DOWN).unscaledValue().abs().toString();
        d = d.length() >= digits ? d.substring(d.length() - digits) : "0".repeat(digits - d.length()) + d;
        if (!signed || digits == 0) {
            return d;
        }
        int last = d.charAt(digits - 1) - '0';
        return d.substring(0, digits - 1) + (v.signum() < 0 ? NEGATIVE : POSITIVE).charAt(last);
    }

    private static String join(Object... operands) {
        StringBuilder b = new StringBuilder();
        for (Object o : operands) {
            b.append(o);
        }
        return b.toString();
    }

    private static void write(String text) {
        String target = System.getProperty("gitgalaxy.sysout");
        byte[] bytes = text.getBytes(Charset.forName(System.getProperty("gitgalaxy.data.charset", "{record_charset}")));
        synchronized (LOCK) {
            if (target == null) {
                System.out.write(bytes, 0, bytes.length);
                System.out.flush();
                return;
            }
            try {
                Files.write(Path.of(target), bytes, StandardOpenOption.CREATE, StandardOpenOption.APPEND);
            } catch (IOException e) {
                throw new UncheckedIOException(e);
            }
        }
    }
}
""",
    "CobolAbend": """package {pkg};

import java.util.Locale;

/**
 * A program's abend (#4023 follow-up): `CALL 'CEE3ABD' USING ABCODE` is `throw CobolAbend.user(abcode, why)`.
 * The step ends ABEND Unnnn (the code modulo 4096, as a user completion code is) with no return code.
 */
public class CobolAbend extends RuntimeException {

    private final String code;

    public CobolAbend(String code, String message) {
        super(code + ": " + message);
        this.code = code;
    }

    /** A user abend: CEE3ABD's ABCODE. */
    public static CobolAbend user(int abcode, String why) {
        return new CobolAbend(String.format(Locale.ROOT, "U%04d", Math.floorMod(abcode, 4096)), why);
    }

    /** The completion code: U0999. */
    public String code() {
        return code;
    }
}
""",
    "CobolFiles": """package {pkg};

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.function.BooleanSupplier;
import java.util.function.Supplier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * The FILE STATUS of each COBOL file I/O statement (#4023 follow-up). A port makes ONE call here per I/O
 * statement of the program, in the order the program runs them, and takes the program's FILE STATUS logic
 * (IF WS-STATUS = '00', AT END, INVALID KEY) from the status it returns: "00" done, "23" no record with that
 * key, "10" end of file, "35" an input dataset that does not exist.
 *
 * gitgalaxy.faults.plan names a fault plan -- the equivalence harness's, the same file its GnuCOBOL side
 * reads (tests/equivalence/faults/ggfault.c): one fault per line, `DD OP NTH STATUS` (e.g. `XREFFILE READ 2 23`;
 * NTH `*` = every occurrence). The planned statement is not performed: it returns its status, and the port's
 * error handling runs as the program's does. Every statement is counted, faulted or not, by DD and operation
 * (READ counts keyed and sequential reads alike). Each fault that fires is appended to gitgalaxy.faults.log.
 * With no plan (production) nothing is injected.
 */
@Component
public class CobolFiles {

    public enum Op { OPEN, CLOSE, READ, WRITE, REWRITE, DELETE, START }

    /** A READ's outcome: its FILE STATUS, and the record when there is one. */
    public record Read<T>(String status, T record) {
        public boolean found() {
            return record != null;
        }
    }

    /** An I/O action that may fail on the file system. */
    @FunctionalInterface
    public interface Io {
        void run() throws IOException;
    }

    private record Fault(String dd, Op op, int nth, String status) {
    }

    private final List<Fault> plan = new ArrayList<>();
    private final Map<String, Integer> seen = new HashMap<>();
    private final Path log;

    public CobolFiles(@Value("${gitgalaxy.faults.plan:}") String plan, @Value("${gitgalaxy.faults.log:}") String log) {
        this.log = log.isBlank() ? null : Path.of(log);
        if (plan.isBlank()) {
            return;
        }
        try {
            for (String line : Files.readAllLines(Path.of(plan), StandardCharsets.US_ASCII)) {
                String[] w = line.trim().split("[ ]+");
                if (w.length == 4) {
                    this.plan.add(new Fault(w[0], Op.valueOf(w[1]), "*".equals(w[2]) ? 0 : Integer.parseInt(w[2]), w[3]));
                }
            }
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    /** The planned status of this statement, or null. Every statement counts, whether or not it faults. */
    public String planned(String dd, Op op) {
        if (plan.isEmpty()) {
            return null;
        }
        int n = seen.merge(dd + " " + op, 1, Integer::sum);
        for (Fault f : plan) {
            if (f.dd().equals(dd) && f.op() == op && (f.nth() == 0 || f.nth() == n)) {
                if (log != null) {
                    try {
                        Files.writeString(log, String.format(Locale.ROOT, "%s %s %d %s%n", dd, op, n, f.status()),
                                StandardCharsets.US_ASCII, StandardOpenOption.CREATE, StandardOpenOption.APPEND);
                    } catch (IOException e) {
                        throw new UncheckedIOException(e);
                    }
                }
                return f.status();
            }
        }
        return null;
    }

    /** OPEN of a file the port keeps in a repository (a VSAM store): "00". */
    public String open(String dd) {
        String p = planned(dd, Op.OPEN);
        return p != null ? p : "00";
    }

    /** OPEN of a dataset file: "35" when an input (or I-O) dataset does not exist, else "00". */
    public String open(String dd, Path file, boolean input) {
        String p = planned(dd, Op.OPEN);
        return p != null ? p : input && (file == null || !Files.exists(file)) ? "35" : "00";
    }

    /** CLOSE: `close` runs, "00" (a planned status: it does not run). */
    public String close(String dd, Io close) {
        return perform(dd, Op.CLOSE, close);
    }

    public String close(String dd) {
        return close(dd, () -> { });
    }

    /** A keyed READ: "00" and the record, or "23" when there is none. */
    public <T> Read<T> read(String dd, Supplier<Optional<T>> read) {
        String p = planned(dd, Op.READ);
        if (p != null) {
            return new Read<>(p, null);
        }
        T r = read.get().orElse(null);
        return new Read<>(r != null ? "00" : "23", r);
    }

    /** A sequential READ (READ NEXT): "00" and the next record, or "10" at the end. A planned status does not
     *  advance the cursor. */
    public <T> Read<T> readNext(String dd, Iterator<T> cursor) {
        String p = planned(dd, Op.READ);
        if (p != null) {
            return new Read<>(p, null);
        }
        return cursor.hasNext() ? new Read<>("00", cursor.next()) : new Read<>("10", null);
    }

    public String write(String dd, Io write) {
        return perform(dd, Op.WRITE, write);
    }

    /** WRITE of a new record to a keyed (VSAM KSDS) file: "22" when a record with that key is already on file --
     *  a WRITE never replaces one, as repository.save() would -- else `write` runs, "00". */
    public String writeKeyed(String dd, BooleanSupplier exists, Io write) {
        String p = planned(dd, Op.WRITE);
        if (p != null) {
            return p;
        }
        return exists.getAsBoolean() ? "22" : perform(write);
    }

    /** REWRITE of a keyed file's record: "23" when no record with that key is on file (save() would insert one),
     *  else `rewrite` runs, "00". */
    public String rewriteKeyed(String dd, BooleanSupplier exists, Io rewrite) {
        String p = planned(dd, Op.REWRITE);
        if (p != null) {
            return p;
        }
        return exists.getAsBoolean() ? perform(rewrite) : "23";
    }

    public String rewrite(String dd, Io rewrite) {
        return perform(dd, Op.REWRITE, rewrite);
    }

    public String delete(String dd, Io delete) {
        return perform(dd, Op.DELETE, delete);
    }

    /** START: "00" when a record satisfies the key condition, else "23". */
    public String start(String dd, BooleanSupplier found) {
        String p = planned(dd, Op.START);
        return p != null ? p : found.getAsBoolean() ? "00" : "23";
    }

    private String perform(String dd, Op op, Io io) {
        String p = planned(dd, op);
        return p != null ? p : perform(io);
    }

    private static String perform(Io io) {
        try {
            io.run();
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
        return "00";
    }
}
""",
    "MainframeClock": """package {pkg};

import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/** The time a ported program reads -- FUNCTION CURRENT-DATE, ACCEPT FROM DATE / TIME, EXEC CICS ASKTIME
 *  (#3753): `gitgalaxy.clock` (an ISO local date-time, e.g. 2022-07-18T10:30:15.00) when set -- the
 *  equivalence harness pins it, so a run can be compared with the original's -- else the system clock.
 *  #3824: the mainframe's zone, never the JVM's; currentDate() carries its UTC offset. #3934: `gitgalaxy.zone`
 *  when set (the equivalence harness pins it per case), else `gitgalaxy.culture.zone` -- the key the
 *  generated application.yml writes, so editing it there moves the clock -- else {zone}, the target's
 *  culture.zone. A pinned local time that does not exist in the zone (a DST gap, e.g.
 *  2022-03-27T02:30 in Europe/Berlin) resolves by ZonedDateTime.ofLocal's rule: it moves forward. */
@Component
public class MainframeClock {

    private static final DateTimeFormatter FORMATTER = DateTimeFormatter.ofPattern("yyyyMMddHHmmssSSZ");
    private final String pinned;
    private final ZoneId zone;

    public MainframeClock(@Value("${gitgalaxy.clock:}") String pinned,
                          @Value("${gitgalaxy.zone:${gitgalaxy.culture.zone:{zone}}}") String zoneId) {
        this.pinned = pinned == null ? "" : pinned.trim();
        this.zone = ZoneId.of(zoneId == null || zoneId.trim().isEmpty() ? "{zone}" : zoneId.trim());
    }

    public LocalDateTime now() {
        return zonedNow().toLocalDateTime();
    }

    public ZonedDateTime zonedNow() {
        return pinned.isEmpty() ? ZonedDateTime.now(zone) : ZonedDateTime.of(LocalDateTime.parse(pinned), zone);
    }

    public String currentDate() {
        return zonedNow().format(FORMATTER);
    }
}
""",
    "Dd": """package {pkg};

/** One DD statement of a job step (#3622): its DD name, dataset (DSN, null for SYSOUT / DUMMY / in-stream),
 *  DISP status (NEW / OLD / SHR / MOD), DISP's normal-end disposition (KEEP / CATLG / DELETE / PASS /
 *  UNCATLG, null when not written) and GDG generation ((+1) a new one, (0) the current, (-1) before it). */
public record Dd(String name, String dsn, String status, String normalEnd, String generation) {
}
""",
    "DatasetResolver": """package {pkg};

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Locale;
import java.util.stream.Stream;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * Datasets as files (#3622): DSN A.B.C is `<gitgalaxy.datasets.directory>/A.B.C`; a GDG base is a directory
 * of generations G0001V00, G0002V00, ... -- (+1) the next, (0) the current, (-n) n before it.
 */
@Component
public class DatasetResolver {

    private final Path root;

    public DatasetResolver(@Value("${gitgalaxy.datasets.directory:datasets}") String root) {
        this.root = Path.of(root);
    }

    public Path path(Dd dd) {
        if (dd.dsn() == null) {
            return null;
        }
        Path base = root.resolve(dd.dsn());
        if (dd.generation() == null) {
            return base;
        }
        int current = latest(base);
        int g = current + Integer.parseInt(dd.generation().replace("+", ""));
        return base.resolve(String.format(Locale.ROOT, "G%04dV00", Math.max(g, 1)));
    }

    private int latest(Path gdg) {
        if (!Files.isDirectory(gdg)) {
            return 0;
        }
        try (Stream<Path> gens = Files.list(gdg)) {
            return gens.map(p -> p.getFileName().toString()).filter(n -> n.matches("G\\\\d{4}V00"))
                    .mapToInt(n -> Integer.parseInt(n.substring(1, 5))).max().orElse(0);
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }
}
""",
    "JclConditions": """package {pkg};

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * JCL step conditions (#3622), against the return codes of the steps before.
 *   COND=(code,op[,step]),... bypasses the step when ANY test holds: `code op RC` for the named step,
 *   else for every step before (COND=(4,LT): bypass if 4 < some RC). EVEN / ONLY concern abends, which
 *   stop a Spring Batch job: they are not evaluated here.
 *   IF (expression) THEN: RC, step.RC, relational operators, AND / & / OR / | / NOT; RC alone is the
 *   highest return code so far.
 */
public final class JclConditions {

    private static final Pattern TEST = Pattern.compile("(\\\\d+)\\\\s*,\\\\s*(GT|GE|EQ|LT|LE|NE)\\\\s*(?:,\\\\s*([A-Z0-9#@$.]+))?");

    private JclConditions() {
    }

    public static boolean bypass(String cond, Map<String, Integer> rcs) {
        if (cond == null || rcs.isEmpty()) {
            return false;
        }
        Matcher m = TEST.matcher(cond.toUpperCase(Locale.ROOT));
        while (m.find()) {
            int code = Integer.parseInt(m.group(1));
            String op = m.group(2);
            if (m.group(3) != null) {
                Integer rc = rcs.get(m.group(3));
                if (rc != null && compare(code, op, rc)) {
                    return true;
                }
            } else {
                for (int rc : rcs.values()) {
                    if (compare(code, op, rc)) {
                        return true;
                    }
                }
            }
        }
        return false;
    }

    static boolean compare(int left, String op, int right) {
        return switch (op) {
            case "GT", ">" -> left > right;
            case "GE", ">=" -> left >= right;
            case "EQ", "=" -> left == right;
            case "LT", "<" -> left < right;
            case "LE", "<=" -> left <= right;
            case "NE", "\\u00ac=", "^=" -> left != right;
            default -> throw new IllegalArgumentException("unknown operator " + op);
        };
    }

    /** Whether an IF expression holds (true when there is none). */
    public static boolean holds(String expression, Map<String, Integer> rcs) {
        if (expression == null || expression.isBlank()) {
            return true;
        }
        return new Parser(tokens(expression), rcs).or();
    }

    private static List<String> tokens(String text) {
        Matcher m = Pattern.compile("[A-Z0-9#@$]+(?:\\\\.[A-Z0-9#@$]+)*|>=|<=|\\u00ac=|\\\\^=|[=<>()&|\\u00ac]")
                .matcher(text.toUpperCase(Locale.ROOT));
        List<String> out = new ArrayList<>();
        while (m.find()) {
            out.add(m.group());
        }
        return out;
    }

    private static final class Parser {
        private final List<String> t;
        private final Map<String, Integer> rcs;
        private int i;

        Parser(List<String> t, Map<String, Integer> rcs) {
            this.t = t;
            this.rcs = rcs;
        }

        private String peek() {
            return i < t.size() ? t.get(i) : "";
        }

        boolean or() {
            boolean v = and();
            while (peek().equals("OR") || peek().equals("|")) {
                i++;
                v = and() || v;
            }
            return v;
        }

        boolean and() {
            boolean v = not();
            while (peek().equals("AND") || peek().equals("&")) {
                i++;
                v = not() && v;
            }
            return v;
        }

        boolean not() {
            if (peek().equals("NOT") || peek().equals("\\u00ac")) {
                i++;
                return !not();
            }
            if (peek().equals("(")) {
                i++;
                boolean v = or();
                if (peek().equals(")")) {
                    i++;
                }
                return v;
            }
            return relation();
        }

        boolean relation() {
            String left = t.get(i++);
            if (!left.endsWith("RC")) {
                return !left.contains("ABEND");  // ABEND / step.ABEND: no abended step continues a Spring Batch job
            }
            String op = t.get(i++);
            int right = Integer.parseInt(t.get(i++));
            int rc = left.equals("RC") ? rcs.values().stream().mapToInt(Integer::intValue).max().orElse(0)
                    : rcs.getOrDefault(left.substring(0, left.length() - 3), 0);
            return compare(rc, op, right);
        }
    }
}
""",
    "JclSteps": """package {pkg};

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.IntSupplier;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.batch.core.ExitStatus;
import org.springframework.batch.core.step.tasklet.Tasklet;
import org.springframework.batch.item.ExecutionContext;
import org.springframework.batch.repeat.RepeatStatus;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * The tasklets of the generated JCL jobs (#3622). Each step first checks the job's and its own COND= and
 * its IF against the return codes so far (the job's ExecutionContext, `jcl.rc`); a bypassed step records
 * no return code, as JCL does. The exit status is `RC=n` or `BYPASSED`.
 */
@Component
public class JclSteps {

    private static final Logger LOG = LoggerFactory.getLogger(JclSteps.class);
    private final DatasetResolver datasets;
    private final boolean skipUnimplemented;

    public JclSteps(DatasetResolver datasets,
            @Value("${gitgalaxy.batch.skip-unimplemented:false}") boolean skipUnimplemented) {
        this.datasets = datasets;
        this.skipUnimplemented = skipUnimplemented;
    }

    /** A step running a program of the estate: its service's runBatch, whose result is RETURN-CODE. */
    public Tasklet program(String name, String jcl, String jobCond, String cond, String ifCond, IntSupplier run) {
        return guarded(jcl, jobCond, cond, ifCond, run);
    }

    /** IEFBR14: does nothing; its DDs' DISP creates (NEW, or MOD when missing) or deletes (normal-end DELETE)
     *  the datasets. */
    public Tasklet iefbr14(String name, String jcl, String jobCond, String cond, String ifCond, List<Dd> dds) {
        return guarded(jcl, jobCond, cond, ifCond, () -> {
            for (Dd dd : dds) {
                Path p = datasets.path(dd);
                if (p == null) {
                    continue;
                }
                try {
                    if ("DELETE".equals(dd.normalEnd())) {
                        Files.deleteIfExists(p);
                    } else if (("NEW".equals(dd.status()) || "MOD".equals(dd.status())) && !Files.exists(p)) {
                        Files.createDirectories(p.getParent() == null ? Path.of(".") : p.getParent());
                        Files.createFile(p);
                    }
                } catch (IOException e) {
                    throw new UncheckedIOException(e);
                }
            }
            return 0;
        });
    }

    /** IEBGENER / ICEGENER: copies SYSUT1 to SYSUT2. */
    public Tasklet copy(String name, String jcl, String jobCond, String cond, String ifCond, List<Dd> dds) {
        return guarded(jcl, jobCond, cond, ifCond, () -> {
            Path in = dds.stream().filter(d -> d.name().equals("SYSUT1")).map(datasets::path).findFirst().orElse(null);
            Path out = dds.stream().filter(d -> d.name().equals("SYSUT2")).map(datasets::path).findFirst().orElse(null);
            if (in == null || out == null) {
                LOG.warn("{}: SYSUT1 / SYSUT2 is not a dataset (in-stream, SYSOUT or DUMMY): nothing copied", jcl);
                return 0;
            }
            try {
                Files.createDirectories(out.getParent() == null ? Path.of(".") : out.getParent());
                Files.copy(in, out, StandardCopyOption.REPLACE_EXISTING);
            } catch (IOException e) {
                throw new UncheckedIOException(e);
            }
            return 0;
        });
    }

    /** A utility not implemented here (SORT, IDCAMS, a TSO / IMS runner, ...): fails the job, unless
     *  gitgalaxy.batch.skip-unimplemented is set -- then it logs and returns 0. Never a silent success. */
    public Tasklet utility(String name, String jcl, String jobCond, String cond, String ifCond, String program,
            String todo) {
        return guarded(jcl, jobCond, cond, ifCond, () -> {
            if (!skipUnimplemented) {
                throw new UnsupportedOperationException(todo);
            }
            LOG.warn("{} ({}) skipped: {}", jcl, program, todo);
            return 0;
        });
    }

    @SuppressWarnings("unchecked")
    private Tasklet guarded(String jcl, String jobCond, String cond, String ifCond, IntSupplier run) {
        return (contribution, chunk) -> {
            ExecutionContext ctx = chunk.getStepContext().getStepExecution().getJobExecution().getExecutionContext();
            Map<String, Integer> rcs = new LinkedHashMap<>((Map<String, Integer>) ctx.get("jcl.rc", Map.class, Map.of()));
            if (JclConditions.bypass(jobCond, rcs) || JclConditions.bypass(cond, rcs)
                    || !JclConditions.holds(ifCond, rcs)) {
                contribution.setExitStatus(new ExitStatus("BYPASSED"));
                return RepeatStatus.FINISHED;
            }
            int rc = run.getAsInt();
            rcs.put(jcl, rc);
            ctx.put("jcl.rc", rcs);
            contribution.setExitStatus(new ExitStatus("RC=" + rc));
            return RepeatStatus.FINISHED;
        };
    }
}
""",
    "JclJobLauncher": """package {pkg};

import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import org.springframework.batch.core.Job;
import org.springframework.batch.core.JobExecution;
import org.springframework.batch.core.JobParametersBuilder;
import org.springframework.batch.core.launch.JobLauncher;
import org.springframework.stereotype.Component;

/** Runs a generated JCL job by its JCL name (#3622): for the REST endpoint and for programs that submit
 *  jobs through the internal reader. */
@Component
public class JclJobLauncher {

    private final JobLauncher launcher;
    private final Map<String, Job> jobs = new TreeMap<>();

    public JclJobLauncher(JobLauncher launcher, List<Job> jobs) {
        this.launcher = launcher;
        jobs.forEach(j -> this.jobs.put(j.getName(), j));
    }

    public List<String> names() {
        return List.copyOf(jobs.keySet());
    }

    public JobExecution launch(String name) {
        Job job = jobs.get(name);
        if (job == null) {
            throw new IllegalArgumentException("no generated job " + name + " (see resources/batch/jcl-jobs.json)");
        }
        try {
            return launcher.run(job, new JobParametersBuilder().addLong("run.id", System.nanoTime()).toJobParameters());
        } catch (Exception e) {
            throw new IllegalStateException("job " + name + " could not start", e);
        }
    }
}
""",
}

_CONTROLLER = """package {pkg};

import java.util.List;
import java.util.Map;
import org.springframework.batch.core.JobExecution;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** The generated JCL jobs (#3622): list them, and run one by its JCL name. */
@RestController
@RequestMapping("/api/v1/batch/jobs")
public class BatchJobController {

    private final JclJobLauncher launcher;

    public BatchJobController(JclJobLauncher launcher) {
        this.launcher = launcher;
    }

    @GetMapping
    public List<String> jobs() {
        return launcher.names();
    }

    @PostMapping("/{name}")
    public Map<String, Object> run(@PathVariable String name) {
        JobExecution run = launcher.launch(name);
        return Map.of("job", name, "id", run.getId(), "status", run.getStatus().toString(),
                "exit", run.getExitStatus().getExitCode());
    }
}
"""
