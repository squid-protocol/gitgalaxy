#!/usr/bin/env python3
"""
#4052 (slice 1): a proven case's COBOL outputs as golden files, and a check of a Java run against them.

    python tests/tools/golden_export.py export CASE --out DIR [--faults all|none|NAME,NAME]
    python tests/tools/golden_export.py check DIR --java JAVA_DIR

`export` runs the batch case's COBOL side once (and each fault run) under the equivalence harness's own
`run_cobol`, and writes what the mainframe-side oracle produced:

    DIR/golden.json                the manifest: case, program, data encoding, per run: RETURN-CODE or ABEND,
                                   and per output DD: bytes, sha256, file
    DIR/<run>/<DD>                 the output bytes (run "main" is the case's own run; a fault run is "fault-NAME")

`check` compares a Java run laid out the same way (`JAVA_DIR/<run>/<DD>`, plus `RETURN-CODE` / `ABEND` files)
byte for byte against the golden files and prints every difference. Byte equality is STRICTER than the harness's
comparison (which reads numeric fields as decimals and applies declared differences), never looser: a run that
differs only in a way the harness would accept is reported here as a difference. Field-level comparison and the
generated JUnit class are the later slices of #4052.

    python tests/tools/golden_export.py junit DIR --out SRC_DIR [--package PKG]

`junit` writes the same byte check as Java source into a generated project, so the golden files keep protecting the
Java after the mainframe (and this tool) are gone: `DIR/golden.index` (the manifest flattened to tab-separated lines the
Java reads without a JSON library), `PKG/GoldenCheck.java` (no dependencies: `problems(goldenDir, javaDir)` returns the
same messages as `check`) and `PKG/GoldenRegressionTest.java` (a JUnit 5 test that fails on any problem; it reads the
directories from the system properties `golden.dir` and `java.out.dir`). Producing `java.out.dir` (running the port on
the case's inputs, laid out as `check` expects) is the project harness's step: wiring it in, and proving the class fails
on a mutant the proof kills, are later slices of #4052.

    python tests/tools/golden_export.py project CASE PROJECT_DIR [--port DIR] [--faults all|none|NAME,NAME] [--package PKG]

`project` is the harness step that wires both ends into a generated Maven project (#4052 slice 3): the golden files go
to `PROJECT_DIR/src/test/resources/golden/CASE`, the two classes to `src/test/java/PKG`, and the port is RUN on the
case's inputs (the same Java run the equivalence proof makes, faults included) with its outputs written to
`PROJECT_DIR/target/golden-java-out/<run>/<DD>` -- the default of the JUnit class's `java.out.dir`. Fault runs are named
`fault-NAME` on both sides.

    python tests/tools/golden_export.py prove-mutant CASE --port DIR --mutants ID,ID [--faults ...] --out DIR

`prove-mutant` is #4052's "done when": the golden files are exported once, then the det port `DIR` and each mutant of it
(an id from `tests/tools/mutation.py`) are RUN on the case's inputs and checked against them, by `check` and by the
generated `GoldenCheck.java` (the class `GoldenRegressionTest` calls), compiled and run here. It exits 0 only when the
unmutated port passes and every mutant fails. Only a mutant the committed det-mutation ledger
(`tests/equivalence/det_mutation/CASE.json`) records as KILLED by the equivalence proof is accepted: the claim is that
the regression suite keeps what the proof kills, not that it kills something the proof would let live.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

MANIFEST = "golden.json"
MAIN = "main"
STATUS = ("RETURN-CODE", "ABEND")  # the run's result, not a dataset
NOT_OUTPUT = ("FAULTS",)  # the fault log of a fault run: the harness compares it as fired faults, kept as text


def _safe(name: str) -> str:
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        raise ValueError(f"not a usable file name: {name!r}")
    return name


def run_entry(outputs: dict[str, bytes], run_dir: Path) -> dict[str, Any]:
    """Write one run's outputs under `run_dir` and return its manifest entry."""
    run_dir.mkdir(parents=True, exist_ok=True)
    entry: dict[str, Any] = {"outputs": {}}
    for dd in sorted(outputs):
        data = outputs[dd]
        if dd in STATUS:
            entry[dd.lower().replace("-", "_")] = data.decode("ascii").strip()
            continue
        (run_dir / _safe(dd)).write_bytes(data)
        entry["outputs"][dd] = {
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "file": f"{run_dir.name}/{dd}",
        }
    return entry


def export(
    case: dict[str, Any], runs: dict[str, dict[str, bytes]], dest: Path, data_encoding: str = "latin-1"
) -> dict[str, Any]:
    """Write the golden files and manifest of `runs` ({run name: {DD: bytes, RETURN-CODE | ABEND: bytes}})."""
    if MAIN not in runs:
        raise ValueError(f"a golden export needs the case's own run, named {MAIN!r}")
    dest.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "case": case["name"],
        "program": case["program"],
        "data_encoding": data_encoding,
        "runs": {name: run_entry(res, dest / _safe(name)) for name, res in sorted(runs.items())},
    }
    (dest / MANIFEST).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def load_java(java_dir: Path, run: str) -> dict[str, bytes]:
    d = java_dir / run
    return {p.name: p.read_bytes() for p in sorted(d.iterdir()) if p.is_file()} if d.is_dir() else {}


def check(golden_dir: Path, java_dir: Path) -> list[str]:
    """Every way the Java run differs from the golden files; empty when it is byte-identical in every run."""
    manifest = json.loads((golden_dir / MANIFEST).read_text(encoding="utf-8"))
    problems: list[str] = []
    for name, want in manifest["runs"].items():
        java = load_java(java_dir, name)
        if not java:
            problems.append(f"{name}: the Java run has no outputs")
            continue
        for key in ("abend", "return_code"):
            got = java.get(key.upper().replace("_", "-"), b"").decode("ascii").strip() or None
            if got != want.get(key):
                problems.append(f"{name}: {key.replace('_', ' ')} {got!r}, golden {want.get(key)!r}")
        abended = bool(want.get("abend"))
        for dd, meta in want["outputs"].items():
            if abended and dd != "SYSOUT":  # what an abended step leaves in its datasets is not defined: not compared;
                continue  # its job log is (the proof compares SYSOUT after an abend too: its messages say why, #4056)
            golden = (golden_dir / meta["file"]).read_bytes()
            if hashlib.sha256(golden).hexdigest() != meta["sha256"]:
                problems.append(f"{name}/{dd}: the golden file no longer matches its manifest hash")
            elif dd not in java:
                problems.append(f"{name}/{dd}: missing from the Java run")
            elif java[dd] != golden:
                at = next(
                    (i for i, (a, b) in enumerate(zip(java[dd], golden)) if a != b), min(len(java[dd]), len(golden))
                )
                problems.append(f"{name}/{dd}: differs at byte {at} (Java {len(java[dd])} bytes, golden {len(golden)})")
        if abended:
            continue
        extra = sorted(
            set(java)
            - set(want["outputs"])
            - {k.upper().replace("_", "-") for k in ("abend", "return_code")}
            - set(NOT_OUTPUT)
        )
        problems += [f"{name}/{dd}: a Java output the golden run does not have" for dd in extra]
    return problems


INDEX = "golden.index"
GOLDEN_CHECK_JAVA = r"""package __PKG__;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.TreeSet;
import java.util.stream.Stream;

/** Generated by tests/tools/golden_export.py junit (#4052): the byte check of a Java run against golden files. */
public final class GoldenCheck {
    private GoldenCheck() {}

    private static final String ABEND = "ABEND";
    private static final String RC = "RETURN-CODE";

    private static Map<String, byte[]> load(Path dir) throws IOException {
        Map<String, byte[]> files = new TreeMap<>();
        if (!Files.isDirectory(dir)) {
            return files;
        }
        try (Stream<Path> s = Files.list(dir)) {
            for (Path p : (Iterable<Path>) s.sorted()::iterator) {
                if (Files.isRegularFile(p)) {
                    files.put(p.getFileName().toString(), Files.readAllBytes(p));
                }
            }
        }
        return files;
    }

    private static String status(Map<String, byte[]> java, String key) {
        byte[] b = java.get(key);
        return b == null ? "" : new String(b, StandardCharsets.US_ASCII).strip();
    }

    private static String sha256(byte[] data) throws IOException {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(data));
        } catch (java.security.NoSuchAlgorithmException e) {
            throw new IOException(e);
        }
    }

    /** Every way the Java run differs from the golden files; empty when it is byte-identical in every run. */
    public static List<String> problems(Path golden, Path javaDir) throws IOException {
        List<String> problems = new ArrayList<>();
        List<String> runs = new ArrayList<>();
        Map<String, String[]> status = new TreeMap<>();
        Map<String, List<String[]>> outputs = new TreeMap<>();
        for (String line : Files.readAllLines(golden.resolve("__INDEX__"), StandardCharsets.UTF_8)) {
            String[] f = line.split("\t", -1);
            if (f[0].equals("R")) {
                runs.add(f[1]);
                status.put(f[1], new String[] {f[2], f[3]});
                outputs.put(f[1], new ArrayList<>());
            } else if (f[0].equals("O")) {
                outputs.get(f[1]).add(new String[] {f[2], f[3], f[4]});
            }
        }
        for (String run : runs) {
            Map<String, byte[]> java = load(javaDir.resolve(run));
            if (java.isEmpty()) {
                problems.add(run + ": the Java run has no outputs");
                continue;
            }
            String abend = status.get(run)[0];
            String rc = status.get(run)[1];
            if (!status(java, ABEND).equals(abend)) {
                problems.add(run + ": abend " + quote(status(java, ABEND)) + ", golden " + quote(abend));
            }
            if (!status(java, RC).equals(rc)) {
                problems.add(run + ": return code " + quote(status(java, RC)) + ", golden " + quote(rc));
            }
            boolean abended = !abend.isEmpty();
            TreeSet<String> known = new TreeSet<>(java.keySet());
            known.remove(ABEND);
            known.remove(RC);
            known.remove("FAULTS");
            for (String[] o : outputs.get(run)) {
                known.remove(o[0]);
                if (abended && !o[0].equals("SYSOUT")) {
                    continue;
                }
                byte[] want = Files.readAllBytes(golden.resolve(o[2]));
                byte[] got = java.get(o[0]);
                if (!sha256(want).equals(o[1])) {
                    problems.add(run + "/" + o[0] + ": the golden file no longer matches its manifest hash");
                } else if (got == null) {
                    problems.add(run + "/" + o[0] + ": missing from the Java run");
                } else if (!Arrays.equals(got, want)) {
                    int at = 0;
                    int n = Math.min(got.length, want.length);
                    while (at < n && got[at] == want[at]) {
                        at++;
                    }
                    problems.add(run + "/" + o[0] + ": differs at byte " + at + " (Java " + got.length + " bytes, golden " + want.length + ")");
                }
            }
            for (String dd : abended ? new TreeSet<String>() : known) {
                problems.add(run + "/" + dd + ": a Java output the golden run does not have");
            }
        }
        return problems;
    }

    private static String quote(String s) {
        return s.isEmpty() ? "None" : "'" + s + "'";
    }
}
"""
GOLDEN_TEST_JAVA = """package __PKG__;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.nio.file.Path;
import java.util.List;
import org.junit.jupiter.api.Test;

/** Generated by tests/tools/golden_export.py junit (#4052): case __CASE__ against its golden COBOL outputs. */
class GoldenRegressionTest {
    @Test
    void javaRunMatchesTheGoldenOutputs() throws Exception {
        Path golden = Path.of(System.getProperty("golden.dir", "src/test/resources/golden/__CASE__"));
        Path javaOut = Path.of(System.getProperty("java.out.dir", "target/golden-java-out"));
        assertEquals(List.of(), GoldenCheck.problems(golden, javaOut));
    }
}
"""


def write_index(golden_dir: Path) -> Path:
    """Flatten `golden.json` to tab-separated lines (`R run abend rc`, `O run dd sha256 file`) for the Java check."""
    manifest = json.loads((golden_dir / MANIFEST).read_text(encoding="utf-8"))
    lines: list[str] = []
    for run, entry in manifest["runs"].items():
        lines.append("\t".join(("R", run, entry.get("abend") or "", entry.get("return_code") or "")))
        for dd, meta in entry["outputs"].items():
            lines.append("\t".join(("O", run, dd, meta["sha256"], meta["file"])))
    (golden_dir / INDEX).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return golden_dir / INDEX


def write_junit(golden_dir: Path, src_dir: Path, package: str = "golden") -> list[Path]:
    """Write the golden index beside the golden files and the two Java classes under `src_dir/<package path>`."""
    manifest = json.loads((golden_dir / MANIFEST).read_text(encoding="utf-8"))
    if not all(part.isidentifier() for part in package.split(".")):
        raise ValueError(f"not a Java package name: {package!r}")
    out = src_dir.joinpath(*package.split("."))
    out.mkdir(parents=True, exist_ok=True)
    subst = {"__PKG__": package, "__INDEX__": INDEX, "__CASE__": _safe(manifest["case"])}
    written = [write_index(golden_dir)]
    for name, text in (("GoldenCheck.java", GOLDEN_CHECK_JAVA), ("GoldenRegressionTest.java", GOLDEN_TEST_JAVA)):
        for k, v in subst.items():
            text = text.replace(k, v)
        (out / name).write_text(text, encoding="utf-8")
        written.append(out / name)
    return written


GOLDEN_RESOURCES = Path("src") / "test" / "resources" / "golden"
JAVA_OUT = Path("target") / "golden-java-out"


def java_run_name(name: str) -> str | None:
    """The harness's Java run name as a golden run name: `default` is `main`, `fault:X` is `fault-X`; an
    environment other than the first, and an `entry:` run, have no golden counterpart (None)."""
    if name == "default":
        return MAIN
    if name.startswith("fault:"):
        return "fault-" + name[len("fault:") :]
    return None


def write_java_out(runs: dict[str, dict[str, bytes]], dest: Path) -> list[str]:
    """Lay the harness's Java runs ({run name: {DD: bytes}}) out as `dest/<run>/<DD>`, the `java.out.dir` layout."""
    written = []
    for name, outputs in sorted(runs.items()):
        run = java_run_name(name)
        if run is None:
            continue
        d = dest / _safe(run)
        d.mkdir(parents=True, exist_ok=True)
        for dd, data in outputs.items():
            (d / _safe(dd)).write_bytes(data)
        written.append(run)
    return written


def install_project(golden_dir: Path, project: Path, package: str = "golden") -> list[Path]:
    """Copy the golden files into `project`'s test resources and write the JUnit classes into its test sources."""
    manifest = json.loads((golden_dir / MANIFEST).read_text(encoding="utf-8"))
    resources = project / GOLDEN_RESOURCES / _safe(manifest["case"])
    if resources.exists():
        shutil.rmtree(resources)
    shutil.copytree(golden_dir, resources)
    return write_junit(resources, project / "src" / "test" / "java", package)


def _run_ports(case_name: str, faults: str, ports: dict[str, Path | None], work: Path, golden: Path) -> dict[str, Any]:
    """The COBOL side once (golden files written to `golden`), then the Java side of each port in `ports`
    ({label: port dir, None = the case's own port}): {label: {harness run name: {DD: bytes}}}."""
    import equivalence
    import equivalence_java as ej
    import mainframe_corpus as mc

    case = equivalence.load_case(case_name)
    if (case.get("kind") or "batch") != "batch" or case.get("db2") or case.get("ims"):
        raise SystemExit(f"{case_name}: only a plain batch case is wired in this slice")
    (entry,) = mc.select([case["corpus"]])
    corpus = mc.require_clone(entry)
    equivalence.build_image()
    chosen = equivalence.selected_faults(case, faults)
    cobol = {MAIN: equivalence.run_cobol(case, corpus, work / "cobol")}
    fired = []
    for f in chosen:  # a fault the COBOL side cannot run has no golden run, so none on the Java side either
        try:
            cobol[f"fault-{f['name']}"] = equivalence.run_cobol(case, corpus, work / "faults" / f["name"], f)
            fired.append(f)
        except RuntimeError as e:
            print(f"{case_name}: fault {f['name']} not run: {str(e).strip().splitlines()[0]}")
    faults_arg = tuple(
        (
            f["name"],
            equivalence.fault_plan(f),
            "\n".join(f.get("sql_plan", [])),
            equivalence.run_parm(case, f) if f.get("parm") is not None else "",
            f["sysin"] if f.get("sysin") is not None else "",
            equivalence.fault_dli_dir(work, f),
        )
        for f in fired
    )
    java = {
        label: ej.run_java_environments(
            case, corpus, work / "java" / label, work / "cobol", [ej.environment("default")], True, port, faults_arg
        )
        for label, port in ports.items()
    }
    export(case, cobol, golden, equivalence.equivalence_common.data_encoding(case))
    return java


def _project_case(case_name: str, project: Path, faults: str, port: Path | None, package: str) -> int:
    with tempfile.TemporaryDirectory(prefix=f"golden_{case_name}_") as tmp:
        work = Path(tmp)
        java = _run_ports(case_name, faults, {"port": port}, work, work / "golden")
        install_project(work / "golden", project, package)
    out = project / JAVA_OUT
    if out.exists():
        shutil.rmtree(out)
    names = write_java_out(java["port"], out)
    print(f"{case_name}: golden files and classes in {project}, Java run(s) {', '.join(names)} in {out}")
    return 0


def killed_ids(case_name: str) -> set[str]:
    """The mutant ids the committed det-mutation ledger records as killed by the equivalence proof."""
    ledger = Path(__file__).resolve().parents[1] / "equivalence" / "det_mutation" / f"{case_name}.json"
    if not ledger.is_file():
        return set()
    return set(json.loads(ledger.read_text(encoding="utf-8")).get("entry", {}).get("killed", []))


def find_mutants(port: Path, ids: list[str]) -> dict[str, Any]:
    """The mutants of the port's .java files (tests/tools/mutation.py's operators) with the given ids."""
    import mutation

    found = {}
    for f in sorted(port.rglob("*.java")):
        rel = f.relative_to(port).as_posix()
        for m in mutation.mutants_of(rel, f.read_text(encoding="utf-8"), set(mutation.OPERATORS)):
            if m.id in ids:
                found[m.id] = m
    if missing := sorted(set(ids) - set(found)):
        raise SystemExit(f"no mutant {', '.join(missing)} in {port} (a different translation than the ledger's?)")
    return found


RUN_JAVA = (
    "import java.nio.file.Path;\n"
    "public class GoldenRun { public static void main(String[] a) throws Exception {\n"
    "  for (String p : PKG.GoldenCheck.problems(Path.of(a[0]), Path.of(a[1]))) System.out.println(p);\n"
    "} }\n"
)


def java_problems(golden_dir: Path, java_dirs: list[Path], scratch: Path) -> list[list[str]]:
    """The problems the generated `GoldenCheck.java` reports for each Java run directory (compiled and run here)."""
    import subprocess

    write_junit(golden_dir, scratch / "src", "goldenrun")
    classes = scratch / "classes"
    classes.mkdir(exist_ok=True)
    (scratch / "GoldenRun.java").write_text(RUN_JAVA.replace("PKG", "goldenrun"), encoding="utf-8")
    for srcs in ([scratch / "src/goldenrun/GoldenCheck.java"], [scratch / "GoldenRun.java"]):
        done = subprocess.run(
            ["javac", "-encoding", "UTF-8", "-cp", str(classes), "-d", str(classes), *map(str, srcs)],
            capture_output=True,
            encoding="utf-8",
        )
        if done.returncode:
            raise SystemExit(f"javac failed: {done.stderr}")
    result = []
    for jd in java_dirs:
        run = subprocess.run(
            ["java", "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(classes), "GoldenRun"]
            + [str(golden_dir), str(jd)],
            capture_output=True,
        )
        if run.returncode:
            raise SystemExit(f"java failed: {run.stderr.decode('utf-8')}")
        result.append(run.stdout.decode("utf-8").splitlines())
    return result


def _prove_mutants(case_name: str, port: Path, ids: list[str], faults: str, out: Path) -> int:
    unproven = sorted(set(ids) - killed_ids(case_name))
    if unproven:
        raise SystemExit(f"{case_name}: {', '.join(unproven)} not recorded as killed in tests/equivalence/det_mutation")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import mutation

    mutants = find_mutants(port, ids)
    ports: dict[str, Path | None] = {"unmutated": port}
    with tempfile.TemporaryDirectory(prefix=f"golden_{case_name}_") as tmp:
        work = Path(tmp)
        for mid, m in mutants.items():
            ports[mid] = mutation.write_mutant(port, m, work / "mutants" / mid)
        golden = out / "golden"
        java = _run_ports(case_name, faults, ports, work, golden)
        write_junit(golden, out / "src", "golden")
        dirs = {label: out / "java-out" / label for label in ports}
        for label, runs in java.items():
            if dirs[label].exists():
                shutil.rmtree(dirs[label])
            write_java_out(runs, dirs[label])
        by_java = dict(zip(ports, java_problems(golden, list(dirs.values()), work)))
    ok = True
    for label in ports:
        py = check(golden, dirs[label])
        if py != by_java[label]:
            print(f"{label}: the Python and the generated Java check disagree: {py} / {by_java[label]}")
            ok = False
        want_fail = label != "unmutated"
        m = mutants.get(label)
        what = (
            f"{m.op} {m.file}:{m.line} `{m.before.strip()[:60]}` -> `{m.after.strip()[:60]}`"
            if m
            else "the port as translated"
        )
        print(f"{label}: {what}: {len(py)} problem(s)" + "".join(f"\n    {p}" for p in py[:3]))
        ok = ok and bool(py) == want_fail
    print("prove-mutant: " + ("the unmutated port passes and every mutant fails" if ok else "NOT AS EXPECTED"))
    return 0 if ok else 1


def _export_case(case_name: str, out: Path, faults: str) -> int:
    import equivalence
    import mainframe_corpus as mc

    case = equivalence.load_case(case_name)
    if (case.get("kind") or "batch") != "batch" or case.get("db2"):
        raise SystemExit(
            f"{case_name}: only a plain batch case is exported in this slice (kind {case.get('kind') or 'batch'!r}, db2 {bool(case.get('db2'))})"
        )
    (entry,) = mc.select([case["corpus"]])
    corpus = mc.require_clone(entry)
    equivalence.build_image()
    with tempfile.TemporaryDirectory(prefix=f"golden_{case_name}_") as tmp:  # the build tree is not part of the export
        work = Path(tmp)
        runs = {MAIN: equivalence.run_cobol(case, corpus, work / MAIN)}
        for f in equivalence.selected_faults(case, faults):
            runs[f"fault-{f['name']}"] = equivalence.run_cobol(case, corpus, work / "faults" / f["name"], f)
    manifest = export(case, runs, out, equivalence.equivalence_common.data_encoding(case))
    print(f"{case_name}: {len(runs)} run(s), golden files in {out}")
    return 0 if manifest else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("case")
    e.add_argument("--out", type=Path, required=True)
    e.add_argument("--faults", default="all")
    c = sub.add_parser("check")
    c.add_argument("golden", type=Path)
    c.add_argument("--java", type=Path, required=True)
    j = sub.add_parser("junit")
    j.add_argument("golden", type=Path)
    j.add_argument("--out", type=Path, required=True)
    j.add_argument("--package", default="golden")
    pj = sub.add_parser("project")
    pj.add_argument("case")
    pj.add_argument("project", type=Path)
    pj.add_argument("--port", type=Path)
    pj.add_argument("--faults", default="all")
    pj.add_argument("--package", default="golden")
    pm = sub.add_parser("prove-mutant")
    pm.add_argument("case")
    pm.add_argument("--port", type=Path, required=True)
    pm.add_argument("--mutants", required=True)
    pm.add_argument("--faults", default="all")
    pm.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    if args.cmd == "prove-mutant":
        return _prove_mutants(args.case, args.port, args.mutants.split(","), args.faults, args.out)
    if args.cmd == "project":
        return _project_case(args.case, args.project, args.faults, args.port, args.package)
    if args.cmd == "junit":
        for p in write_junit(args.golden, args.out, args.package):
            print(p)
        return 0
    if args.cmd == "export":
        return _export_case(args.case, args.out, args.faults)
    problems = check(args.golden, args.java)
    for p in problems:
        print(p)
    print("golden check: " + ("DIFFERS" if problems else "byte-identical"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
