"""A generation data group (GDG) base across a job case (#8883, part of #8878; #4890, #4891).

The nightly hands data between jobs through generations: a step writes `DSN=BASE(+1)` and a later job reads
`BASE(0)`, or the whole base (all generations, newest first). `equivalence_job` carries the model below; this module is
the catalog and its refusals, with no file or Docker access.

    "gdgs": {"CARD.TRAN.BKUP": {"limit": 5, "reclen": 350, "generations": ["bkup-g1.txt"]}}   # oldest first, beside the case
    steps: {"case": "...", "job": "TRANBKP", "gdg_out": {"TRANSACT": "CARD.TRAN.BKUP"}}      # DD writes base(+1)
           {"case": "...", "job": "NEXT", "gdg_in": {"TRANFILE": {"base": "CARD.TRAN.BKUP", "gen": "0"}}}

`gen` is `"0"`, `"-n"`, `"+1"` or `"all"`. The rules below are ASSUMED (IBM-documented behaviour recalled from the z/OS MVS JCL Reference, "Generation data
groups" / the DSNAME parameter, NOT checked against the manual text; register F4 records the assumption):
* a relative number `(0)` / `(-n)` is resolved once per job, against the catalog as the job started: a generation a step
  of the same job catalogued does not move `(0)`; a step of that job reads it back as `(+1)`;
* a step that writes `(+1)` creates a new generation, catalogued when the step ends (a step that abends catalogues
  nothing: the job stops there, `equivalence_job`); a second `(+1)` in the job is the same generation, not a new one;
* a base named without a generation is read as the concatenation of the generations in the catalog when the step
  starts, newest first.
A step belongs to the job named by its `job` key (default: the previous step's, the first step's is the case's `job`);
a new job name starts a new job, so relative numbers are resolved afresh.

Refused by name, never guessed: a base the case does not declare (a GDG the job defines itself, IDCAMS DEFINE GDG, is not
modelled), a LIMIT roll-off when a new generation would exceed the base's LIMIT (SCRATCH, NOSCRATCH and EMPTY are not
modelled), `scratch` / `empty` / `noscratch` options on a declaration, a relative number the catalog cannot satisfy (an
empty base at job start, `(-n)` past the oldest), `(+2)` and further new generations in one job, a second step writing
the base's `(+1)`, `(+1)` read before a step of the job wrote it, a generation number past G9999, a dataset that is not
sequential or whose record length differs from the base's, a base that is both read and written by one DD.
The oracle is GnuCOBOL plus our stub, not z/OS's catalog (register F4).
"""

from __future__ import annotations

import re
from typing import Any


class Unsupported(Exception):
    """The job asks for what this harness does not model: named, never guessed."""


MAX_GEN = 9999
MAX_LIMIT = 255  # IDCAMS DEFINE GDG LIMIT's ceiling
_REL = re.compile(r"^(?:0|-[1-9][0-9]*)$")
_DECL_KEYS = {"limit", "reclen", "generations"}
_NOT_MODELLED = {"scratch", "noscratch", "empty", "noempty", "purge", "nopurge"}


def label(base: str, number: int) -> str:
    return f"{base}.G{number:04d}V00"


def check_declarations(job: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The job's declared bases, validated."""
    gdgs = job.get("gdgs") or {}
    for base, spec in gdgs.items():
        bad = sorted(set(spec) & _NOT_MODELLED)
        if bad:
            raise Unsupported(f"GDG {base}: option(s) {bad} not modelled (a LIMIT roll-off with SCRATCH is refused)")
        unknown = sorted(set(spec) - _DECL_KEYS)
        if unknown:
            raise Unsupported(f"GDG {base}: unknown key(s) {unknown}")
        limit, reclen = spec.get("limit"), spec.get("reclen")
        if not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
            raise Unsupported(f"GDG {base}: LIMIT must be an integer 1..{MAX_LIMIT}")
        if not isinstance(reclen, int) or reclen < 1:
            raise Unsupported(f"GDG {base}: reclen must be a positive integer")
        if len(spec.get("generations", [])) > limit:
            raise Unsupported(f"GDG {base}: {len(spec['generations'])} generations declared, LIMIT {limit}")
    return gdgs


class Catalog:
    """The catalog of the declared bases through a chain of jobs. A payload is whatever the caller stores per
    generation (bytes at run time, None in the dry run)."""

    def __init__(self, gdgs: dict[str, dict[str, Any]], loaded: dict[str, list[Any]] | None = None) -> None:
        self.limit = {b: s["limit"] for b, s in gdgs.items()}
        loaded = loaded or {}
        self.gens: dict[str, list[tuple[int, Any]]] = {
            b: [(n + 1, p) for n, p in enumerate(loaded.get(b, [None] * len(s.get("generations", []))))]
            for b, s in gdgs.items()
        }
        self.start: dict[str, list[tuple[int, Any]]] = {}
        self.created: dict[str, tuple[int, Any]] = {}
        self._job: str | None = None

    def begin_step(self, job_name: str) -> None:
        """A step of `job_name` starts; a new job name resolves relative numbers afresh."""
        if job_name != self._job:
            self._job = job_name
            self.start = {b: list(g) for b, g in self.gens.items()}
            self.created = {}

    def _gens(self, base: str) -> list[tuple[int, Any]]:
        if base not in self.gens:
            raise Unsupported(f"GDG {base} is not declared in the case (a GDG the job defines itself, IDCAMS DEFINE "
                              "GDG, is not modelled)")  # fmt: skip
        return self.gens[base]

    def read(self, base: str, gen: str) -> tuple[str, list[Any]]:
        """(label, payloads oldest-first-concatenated order as read) for one `gdg_in` reference."""
        gens = self._gens(base)
        if gen == "all":
            if not gens:
                raise Unsupported(f"GDG {base} read as a whole base is empty")
            newest_first = list(reversed(gens))
            return f"{base} (all {len(gens)} generations, newest first)", [p for _, p in newest_first]
        if gen == "+1":
            if base not in self.created:
                raise Unsupported(f"GDG {base}(+1) is read before a step of this job wrote it")
            n, p = self.created[base]
            return label(base, n), [p]
        if not _REL.match(gen):
            raise Unsupported(f"GDG {base}: generation {gen!r} is not 0, -n, +1 or all (+2 and further new "
                              "generations are not modelled)")  # fmt: skip
        back = -int(gen)
        start = self.start.get(base, [])
        if back >= len(start):
            raise Unsupported(f"GDG {base}({gen}): the catalog held {len(start)} generation(s) when the job started")
        n, p = start[-1 - back]
        return label(base, n), [p]

    def create(self, base: str, payload: Any) -> str:
        """A step ends and catalogues base(+1)."""
        gens = self._gens(base)
        if base in self.created:
            raise Unsupported(f"GDG {base}(+1) is written by a second step of one job (the same generation, not a "
                              "new one)")  # fmt: skip
        if len(gens) + 1 > self.limit[base]:
            raise Unsupported(f"GDG {base}: a new generation would exceed LIMIT {self.limit[base]}: the roll-off "
                              "(SCRATCH / NOSCRATCH / EMPTY) is not modelled")  # fmt: skip
        n = (gens[-1][0] if gens else 0) + 1
        if n > MAX_GEN:
            raise Unsupported(f"GDG {base}: generation number past G{MAX_GEN}")
        gens.append((n, payload))
        self.created[base] = (n, payload)
        return label(base, n)


def job_names(job: dict[str, Any]) -> list[str]:
    """Each step's job name: its own `job` key, else the previous step's, the first defaulting to the case's `job`."""
    names: list[str] = []
    cur = str(job.get("job") or job.get("name") or "JOB")
    for s in job.get("steps", []):
        cur = s.get("job", cur)
        names.append(cur)
    return names


def uses_gdg(job: dict[str, Any]) -> bool:
    return bool(job.get("gdgs")) or any(k in s for s in job.get("steps", []) for k in ("gdg_in", "gdg_out"))


def check_gdg(job: dict[str, Any], cases: dict[str, dict[str, Any]]) -> None:
    """Refuse a job whose GDG use the model cannot honour: shape per step, then a dry run of the catalog."""
    gdgs = check_declarations(job)
    steps = job.get("steps") or []
    cat = Catalog(gdgs)
    for step, jname in zip(steps, job_names(job), strict=True):
        name = step["case"]
        datasets = cases[name]["datasets"]
        refs: dict[str, str] = {}
        for dd, ref in step.get("gdg_in", {}).items():
            if not isinstance(ref, dict) or set(ref) != {"base", "gen"}:
                raise Unsupported(f"step {name}: gdg_in {dd} must be {{'base': ..., 'gen': ...}}")
            refs[dd] = ref["base"]
        for dd, base in step.get("gdg_out", {}).items():
            if dd in refs:
                raise Unsupported(f"step {name}: {dd} both reads and writes a GDG")
            refs[dd] = base
        for dd, base in refs.items():
            spec = datasets.get(dd)
            if spec is None:
                raise Unsupported(f"step {name}: GDG dataset {dd} is not one of its datasets")
            if dd in step.get("feeds", {}) or dd in step.get("inputs", {}):
                raise Unsupported(f"step {name}: {dd} is a GDG and also fed / given an input")
            if base not in gdgs:
                raise Unsupported(f"step {name}: GDG {base} is not declared in the case (a GDG the job defines "
                                  "itself, IDCAMS DEFINE GDG, is not modelled)")  # fmt: skip
            if spec.get("organization", "sequential") != "sequential":
                raise Unsupported(f"step {name}: GDG dataset {dd} is {spec.get('organization')}, not sequential")
            if spec["reclen"] != gdgs[base]["reclen"]:
                raise Unsupported(f"step {name}: {dd} has record length {spec['reclen']}, GDG {base} "
                                  f"{gdgs[base]['reclen']}")  # fmt: skip
        for dd in step.get("gdg_out", {}):
            if not datasets[dd].get("compare"):
                raise Unsupported(f"step {name}: GDG output {dd} is not a dataset the case compares")
        cat.begin_step(jname)  # the dry run: order, LIMIT, (+1) rules
        for ref in step.get("gdg_in", {}).values():
            cat.read(ref["base"], ref["gen"])
        for base in step.get("gdg_out", {}).values():
            cat.create(base, None)
