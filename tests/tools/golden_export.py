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
`fault-NAME` on both sides. Proving the class fails on a mutant the proof kills is the next slice.
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
        if want.get("abend"):  # what an abended step leaves in its datasets is not defined: not compared
            continue
        for dd, meta in want["outputs"].items():
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
            if (!abend.isEmpty()) {
                continue;
            }
            TreeSet<String> known = new TreeSet<>(java.keySet());
            known.remove(ABEND);
            known.remove(RC);
            known.remove("FAULTS");
            for (String[] o : outputs.get(run)) {
                known.remove(o[0]);
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
            for (String dd : known) {
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


def _project_case(case_name: str, project: Path, faults: str, port: Path | None, package: str) -> int:
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
    with tempfile.TemporaryDirectory(prefix=f"golden_{case_name}_") as tmp:
        work = Path(tmp)
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
        runs = ej.run_java_environments(
            case, corpus, work / "java", work / "cobol", [ej.environment("default")], True, port, faults_arg
        )
        golden = work / "golden"
        export(case, cobol, golden, equivalence.equivalence_common.data_encoding(case))
        install_project(golden, project, package)
    out = project / JAVA_OUT
    if out.exists():
        shutil.rmtree(out)
    names = write_java_out(runs, out)
    print(f"{case_name}: golden files and classes in {project}, Java run(s) {', '.join(names)} in {out}")
    return 0


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
    args = ap.parse_args(argv)
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
