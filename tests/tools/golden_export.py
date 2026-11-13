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
differs only in a way the harness would accept is reported here as a difference, except what the manifest declares:
a dataset's field layout (`records`, from the case's copybook; #4052 slice 15) makes a byte difference a record-level
comparison by the harness's `diff_records` -- accepted only when no field differs and only FILLER does (counted in the
notes). The generated JUnit class does not yet apply this (it stays byte-exact, plus C10 and SYSOUT lines).

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

    python tests/tools/golden_export.py prove-mutant CASE --port DIR --mutants ID,ID [--faults ...] [--one-jvm] --out DIR

`prove-mutant` is #4052's "done when": the golden files are exported once, then the det port `DIR` and each mutant of it
(an id from `tests/tools/mutation.py`) are RUN on the case's inputs and checked against them, by `check` and by the
generated `GoldenCheck.java` (the class `GoldenRegressionTest` calls), compiled and run here. It exits 0 only when the
unmutated port passes and every mutant fails. Only a mutant the committed det-mutation ledger
(`tests/equivalence/det_mutation/CASE.json`) records as KILLED by the equivalence proof is accepted: the claim is that
the regression suite keeps what the proof kills, not that it kills something the proof would let live.

`project` also writes `PROJECT_DIR/pom.xml` (the forge's Spring Boot pom; JUnit 5 comes with its test starter) when the
project has none, so `mvn test` in it runs `GoldenRegressionTest` (#4052 slice 19); `--group-id` sets its groupId
(default: `--package` less its last segment). An existing pom is left alone.

`--one-jvm` (`project` and `prove-mutant`; the equivalence proof's own flag) runs each port's main run and fault runs in
one session JVM, each on a fresh Spring context, rather than a JVM start per run: the fault runs of a port plus its
mutants then fit in one sitting. The comparison is unchanged; only the way the Java side is launched is.
`--mutant-timeout SEC` (`prove-mutant`) is the hang guard for the mutants' runs only (the unmutated port keeps the
harness's 1200 s): a mutant that loops forever is a failing run either way, but 1200 s each is not a verdict.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
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
    case: dict[str, Any],
    runs: dict[str, dict[str, bytes]],
    dest: Path,
    data_encoding: str = "latin-1",
    records: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Write the golden files and manifest of `runs` ({run name: {DD: bytes, RETURN-CODE | ABEND: bytes}}).

    `records` ({DD: {"reclen": N, "fields": [layout_fields rows]}}, #4052 slice 15) is the field layout of each
    fixed-record dataset the case compares; carried only when given (a case with none is byte-exact as before)."""
    if MAIN not in runs:
        raise ValueError(f"a golden export needs the case's own run, named {MAIN!r}")
    dest.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "case": case["name"],
        "program": case["program"],
        "data_encoding": data_encoding,
        "runs": {name: run_entry(res, dest / _safe(name)) for name, res in sorted(runs.items())},
    }
    if case.get("zoned_sign_equivalent"):  # C10: a declared difference, carried only when the case declares one
        manifest["zoned_sign_equivalent"] = sorted(case["zoned_sign_equivalent"])
    if records:
        manifest["records"] = {dd: records[dd] for dd in sorted(records)}
        manifest["code_page"] = case.get("code_page", "cp037")
    (dest / MANIFEST).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def load_java(java_dir: Path, run: str) -> dict[str, bytes]:
    d = java_dir / run
    return {p.name: p.read_bytes() for p in sorted(d.iterdir()) if p.is_file()} if d.is_dir() else {}


def accept_unsigned_positive(a: bytes, b: bytes) -> tuple[bytes, bytes, int]:
    """The harness's C10 comparison (equivalence.accept_unsigned_positive), for a dataset the case declares."""
    import equivalence

    return equivalence.accept_unsigned_positive(a, b)


def check(golden_dir: Path, java_dir: Path, notes: list[str] | None = None) -> list[str]:
    """Every way the Java run differs from the golden files; empty when it is byte-identical in every run.

    A dataset the case declares in `zoned_sign_equivalent` (oracle_assumptions.md C10) is compared as the harness
    does: a digit against the same digit with the positive overpunch is equal. Only those datasets, and only that
    difference; each accepted byte count is appended to `notes` (never hidden)."""
    manifest = json.loads((golden_dir / MANIFEST).read_text(encoding="utf-8"))
    signed = set(manifest.get("zoned_sign_equivalent", []))
    records = manifest.get("records", {})
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
            elif java[dd] != golden and dd in signed and _sign_equal(java[dd], golden, f"{name}/{dd}", notes):
                continue
            elif java[dd] != golden and dd in records and _records_equal(java[dd], golden, manifest, dd, name, notes):
                continue
            elif (
                java[dd] != golden
                and dd == "SYSOUT"
                and line_sysout(manifest)
                and _sysout_equal(java[dd], golden, f"{name}/{dd}", notes)
            ):
                continue
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


ASCII_ENCODINGS = ("ascii", "latin-1", "latin1", "iso-8859-1", "utf-8")  # a line's bytes compare as its text does
NOT_MODELLED = b"GGDISPLAY-NOT-MODELLED"  # equivalence_common.NOT_MODELLED


def line_sysout(manifest: dict[str, Any]) -> bool:
    """Whether SYSOUT is compared as the harness does (by lines): only when a line's bytes are its text."""
    return str(manifest.get("data_encoding", "")).lower() in ASCII_ENCODINGS


def _sysout_lines(data: bytes, golden: bool) -> list[bytes]:
    lines = [x.rstrip(b" \r") for x in data.split(b"\n") if not (golden and x.startswith(b"libcob: "))]
    while lines and not lines[-1]:
        lines.pop()
    return lines


def _sysout_equal(java: bytes, golden: bytes, where: str, notes: list[str] | None) -> bool:
    """equivalence_common.compare_sysout: libcob's own runtime messages (GnuCOBOL's, not the program's) and trailing
    blanks are not text; a golden log holding a DISPLAY operand IBM's text is not modelled for stays byte-exact."""
    want = _sysout_lines(golden, True)
    if NOT_MODELLED in want or _sysout_lines(java, False) != want:
        return False
    if notes is not None:
        dropped = sum(1 for x in golden.split(b"\n") if x.startswith(b"libcob: "))
        notes.append(
            f"{where}: accepted as the harness compares SYSOUT (lines; {dropped} libcob runtime line(s) left out)"
        )
    return True


def _records_equal(
    java: bytes, golden: bytes, manifest: dict[str, Any], dd: str, name: str, notes: list[str] | None
) -> bool:
    """The harness's record comparison (equivalence_common.diff_records) of a dataset whose layout the golden export
    carries: every field decoded and compared, and the bytes no field covers. Accepted only when no field differs
    and the record counts match; a FILLER (no program can name it: the runtime's leftover record area) may differ,
    and the count of records where it does is appended to `notes`, never hidden. A field that decodes equal but
    differs in its bytes (a C vs F sign nibble) is a difference, as in the harness."""
    import equivalence_common as common

    spec = manifest["records"][dd]
    d = common.diff_records(
        golden,
        java,
        spec["reclen"],
        spec["fields"],
        manifest.get("code_page", "cp037"),
        manifest.get("data_encoding", common.DEFAULT_DATA_ENCODING),
    )
    if d["diffs"]:
        return False
    if notes is not None:
        notes.append(
            f"{name}/{dd}: {d['equal']}/{d['records']} records equal field by field; FILLER differs in "
            f"{d['filler_differs']} record(s) (accepted as the harness compares records)"
        )
    return True


def filler_spans(spec: dict[str, Any]) -> list[tuple[int, int]]:
    """The byte ranges [lo, hi) of a record that only a FILLER covers (equivalence_common.diff_records counts a FILLER
    difference apart): FILLER bytes a named field also covers (a REDEFINES) stay compared, through that field."""
    reclen = spec["reclen"]
    filler, named = bytearray(reclen), bytearray(reclen)
    for f in spec["fields"]:
        mask = filler if f["name"] == "FILLER" else named
        for i in range(max(f["offset"], 0), min(f["offset"] + f["bytes"], reclen)):
            mask[i] = 1
    spans: list[tuple[int, int]] = []
    for i in range(reclen):
        if filler[i] and not named[i]:
            if spans and spans[-1][1] == i:
                spans[-1] = (spans[-1][0], i + 1)
            else:
                spans.append((i, i + 1))
    return spans


def _sign_equal(java: bytes, golden: bytes, where: str, notes: list[str] | None) -> bool:
    a, b, n = accept_unsigned_positive(java, golden)
    if a != b:
        return False
    if n and notes is not None:
        notes.append(f"{where}: {n} byte(s) accepted as C10 sign-equivalent (declared by the case)")
    return True


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

    private static final String POSITIVE = "{ABCDEFGHI";

    /** The harness's C10 rule: a digit against the same digit with the positive overpunch is equal; same length only. */
    private static boolean signEquivalent(byte[] a, byte[] b) {
        if (a.length != b.length) {
            return false;
        }
        for (int i = 0; i < a.length; i++) {
            if (a[i] == b[i]) {
                continue;
            }
            boolean ok = false;
            for (int k = 0; k < 2 && !ok; k++) {
                int digit = k == 0 ? a[i] : b[i];
                int over = k == 0 ? b[i] : a[i];
                ok = digit >= 0x30 && digit <= 0x39 && over == POSITIVE.charAt(digit - 0x30);
            }
            if (!ok) {
                return false;
            }
        }
        return true;
    }

    private static List<String> sysoutLines(byte[] data, boolean golden) {
        List<String> lines = new ArrayList<>();
        for (String x : new String(data, StandardCharsets.ISO_8859_1).split("\n", -1)) {
            if (!(golden && x.startsWith("libcob: "))) {
                lines.add(x.replaceAll("[ \r]+$", ""));
            }
        }
        while (!lines.isEmpty() && lines.get(lines.size() - 1).isEmpty()) {
            lines.remove(lines.size() - 1);
        }
        return lines;
    }

    /** The harness's SYSOUT comparison: by lines, libcob's own messages and trailing blanks left out. */
    private static boolean sysoutEqual(byte[] got, byte[] want) {
        List<String> w = sysoutLines(want, true);
        return !w.contains("GGDISPLAY-NOT-MODELLED") && sysoutLines(got, false).equals(w);
    }

    /**
     * The harness's record comparison (diff_records): records paired in order, every byte equal except the ranges only a
     * FILLER covers (the runtime's leftover record area, which no program can name). A missing record or byte differs.
     */
    private static boolean recordsEqual(byte[] got, byte[] want, int reclen, List<int[]> filler) {
        if (reclen <= 0) {
            return false;
        }
        boolean[] ignorable = new boolean[reclen];
        for (int[] k : filler) {
            for (int i = Math.max(k[0], 0); i < Math.min(k[1], reclen); i++) {
                ignorable[i] = true;
            }
        }
        int records = Math.max((got.length + reclen - 1) / reclen, (want.length + reclen - 1) / reclen);
        for (int n = 0; n < records; n++) {
            int base = n * reclen;
            int len = Math.max(Math.min(got.length - base, reclen), Math.min(want.length - base, reclen));
            if (Math.min(got.length - base, reclen) <= 0 || Math.min(want.length - base, reclen) <= 0) {
                return false;
            }
            for (int i = 0; i < len; i++) {
                if (ignorable[i]) {
                    continue;
                }
                boolean g = base + i < got.length;
                boolean w = base + i < want.length;
                if (g != w || (g && got[base + i] != want[base + i])) {
                    return false;
                }
            }
        }
        return true;
    }

    /** Every way the Java run differs from the golden files; empty when it is byte-identical in every run. */
    public static List<String> problems(Path golden, Path javaDir) throws IOException {
        List<String> problems = new ArrayList<>();
        List<String> runs = new ArrayList<>();
        Map<String, String[]> status = new TreeMap<>();
        Map<String, List<String[]>> outputs = new TreeMap<>();
        TreeSet<String> signed = new TreeSet<>();
        boolean lineSysout = false;
        Map<String, Integer> reclens = new TreeMap<>();
        Map<String, List<int[]>> fillers = new TreeMap<>();
        for (String line : Files.readAllLines(golden.resolve("__INDEX__"), StandardCharsets.UTF_8)) {
            String[] f = line.split("\t", -1);
            if (f[0].equals("R")) {
                runs.add(f[1]);
                status.put(f[1], new String[] {f[2], f[3]});
                outputs.put(f[1], new ArrayList<>());
            } else if (f[0].equals("L")) {
                lineSysout = true;
            } else if (f[0].equals("C")) {
                reclens.put(f[1], Integer.parseInt(f[2]));
                fillers.computeIfAbsent(f[1], k -> new ArrayList<>());
            } else if (f[0].equals("K")) {
                fillers.computeIfAbsent(f[1], k -> new ArrayList<>()).add(new int[] {Integer.parseInt(f[2]), Integer.parseInt(f[3])});
            } else if (f[0].equals("Z")) {
                signed.add(f[1]);
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
                } else if (!Arrays.equals(got, want) && !(signed.contains(o[0]) && signEquivalent(got, want))
                        && !(reclens.containsKey(o[0]) && recordsEqual(got, want, reclens.get(o[0]), fillers.get(o[0])))
                        && !(lineSysout && o[0].equals("SYSOUT") && sysoutEqual(got, want))) {
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
    """Flatten `golden.json` to tab-separated lines (`R run abend rc`, `O run dd sha256 file`, `Z dd` for a declared C10 dataset, `L SYSOUT` when it is compared by lines, `C dd reclen` and `K dd lo hi` for a record-compared dataset and its FILLER-only byte ranges) for the Java check."""
    manifest = json.loads((golden_dir / MANIFEST).read_text(encoding="utf-8"))
    lines: list[str] = [f"Z\t{dd}" for dd in manifest.get("zoned_sign_equivalent", [])]
    lines += ["L\tSYSOUT"] if line_sysout(manifest) else []
    for dd, spec in sorted(manifest.get("records", {}).items()):
        lines.append(f"C\t{dd}\t{spec['reclen']}")  # a record dataset: its record length
        lines += [f"K\t{dd}\t{lo}\t{hi}" for lo, hi in filler_spans(spec)]
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


def write_pom(project: Path, package: str = "golden", group_id: str | None = None) -> Path | None:
    """#4052 slice 19: write `project/pom.xml` (the forge's Spring Boot pom, whose test starter brings JUnit 5) so
    `mvn test` runs the generated GoldenRegressionTest. groupId defaults to the package less its last segment
    (`com.acme.golden` -> `com.acme`; a one-segment package is its own), artifactId to the project directory's name.
    A pom the project already has is its own build and is left alone (None)."""
    pom = project / "pom.xml"
    if pom.exists():
        return None
    from gitgalaxy.tools.cobol_to_java.cobol_to_java_build_forge import generate_pom_xml

    group = group_id or package.rpartition(".")[0] or package
    artifact = re.sub(r"[^A-Za-z0-9._-]+", "-", project.resolve().name).strip("-.") or "golden-project"
    pom.write_text(generate_pom_xml(group, artifact), encoding="utf-8")
    return pom


def _run_ports(
    case_name: str,
    faults: str,
    ports: dict[str, Path | None],
    work: Path,
    golden: Path,
    one_jvm: bool = False,
    mutant_timeout: float | None = None,
) -> dict[str, Any]:
    """The COBOL side once (golden files written to `golden`), then the Java side of each port in `ports`
    ({label: port dir, None = the case's own port}): {label: {harness run name: {DD: bytes}}}, or for a mutant
    (any port after the first) whose Java run hung or crashed, {label: the reason (a str)}.
    `one_jvm` (#4052 slice 11): a port's main run and every fault run go through ONE session JVM (the equivalence
    proof's `--one-jvm`, each run on a fresh Spring context) instead of a JVM start per run, which is what made an
    all-faults run of a port plus its mutants give no verdict in 1100 s.
    `mutant_timeout`: the hang guard in seconds for every port after the first (the mutants); a mutant that loops
    forever otherwise holds a run for the harness's 1200 s. The first port keeps the harness's own bound."""
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
    java = {}
    first = None
    default_bound = ej.JAVA_DIRECT_TIMEOUT
    try:
        for label, port in ports.items():
            ej.JAVA_DIRECT_TIMEOUT = default_bound if first is None or not mutant_timeout else mutant_timeout
            if first is not None:
                # #4052 slice 11: a mutant of the first port is the same estate with one file changed, so it takes the
                # first port's generated project and re-overlays its files (mutation.py's `--reuse`) instead of
                # regenerating the whole estate once per mutant
                (work / "java" / first / "report.json").write_text("{}\n", encoding="utf-8")  # the first run is done
                equivalence.equivalence_common.reuse(work / "java" / label, work / "java" / first)
            try:
                java[label] = ej.run_java_environments(
                    case, corpus, work / "java" / label, work / "cobol", [ej.environment("default")], True, port,
                    faults_arg, one_jvm=one_jvm,
                )  # fmt: skip
            except RuntimeError as e:
                if first is None:
                    raise  # the unmutated port must run: nothing to compare a mutant with otherwise
                # a mutant whose Java run hangs or crashes (the harness raises) FAILS the golden check: the run
                # gave no outputs to match; its reason is kept (a str) instead of aborting the whole proof
                java[label] = str(e).strip().splitlines()[-1][:200] or "the Java run failed"
            first = first or label
    finally:
        ej.JAVA_DIRECT_TIMEOUT = default_bound
        equivalence.equivalence_common._REUSE = None
    export(case, cobol, golden, equivalence.equivalence_common.data_encoding(case), record_layouts(case, corpus))
    return java


def _project_case(
    case_name: str,
    project: Path,
    faults: str,
    port: Path | None,
    package: str,
    one_jvm: bool = False,
    group_id: str | None = None,
) -> int:
    with tempfile.TemporaryDirectory(prefix=f"golden_{case_name}_") as tmp:
        work = Path(tmp)
        java = _run_ports(case_name, faults, {"port": port}, work, work / "golden", one_jvm)
        install_project(work / "golden", project, package)
    pom = write_pom(project, package, group_id)
    out = project / JAVA_OUT
    if out.exists():
        shutil.rmtree(out)
    names = write_java_out(java["port"], out)
    print(
        f"{case_name}: golden files and classes in {project}{', pom ' + pom.name if pom else ''}, Java run(s) {', '.join(names)} in {out}"
    )
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


def _prove_mutants(
    case_name: str,
    port: Path,
    ids: list[str],
    faults: str,
    out: Path,
    one_jvm: bool = False,
    mutant_timeout: float | None = None,
) -> int:
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
        java = _run_ports(case_name, faults, ports, work, golden, one_jvm, mutant_timeout)
        write_junit(golden, out / "src", "golden")
        dirs = {label: out / "java-out" / label for label in ports}
        crashed = {label: runs for label, runs in java.items() if isinstance(runs, str)}
        for label, runs in java.items():
            if label in crashed:
                continue
            if dirs[label].exists():
                shutil.rmtree(dirs[label])
            write_java_out(runs, dirs[label])
        done = [label for label in ports if label not in crashed]
        by_java = dict(zip(done, java_problems(golden, [dirs[label] for label in done], work)))
    ok = True
    for label in ports:
        if label in crashed:  # the Java run did not finish (hang bound / crash): a failing run, with its reason
            m = mutants[label]
            print(f"{label}: {m.op} {m.file}:{m.line}: the Java run did not finish: {crashed[label]}")
            continue
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


def record_layouts(case: dict[str, Any], corpus: Path) -> dict[str, dict[str, Any]]:
    """The field layout of each fixed-record dataset the case compares (a V-format dataset is not laid out here)."""
    import equivalence_common as common

    out: dict[str, dict[str, Any]] = {}
    for dd, spec in case.get("datasets", {}).items():
        if not spec.get("compare") or spec.get("record_format") == "V" or not spec.get("copybook"):
            continue
        fields = common.layout_fields(corpus, spec["copybook"], spec.get("record"), occurrences=True)
        out[dd] = {"reclen": spec["reclen"], "fields": fields}
    return out


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
    manifest = export(case, runs, out, equivalence.equivalence_common.data_encoding(case), record_layouts(case, corpus))
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
    pj.add_argument("--group-id", help="the written pom.xml's groupId (default: the package less its last segment)")
    pj.add_argument("--one-jvm", action="store_true", help="each port's runs (main and faults) in one session JVM")
    pm = sub.add_parser("prove-mutant")
    pm.add_argument("case")
    pm.add_argument("--port", type=Path, required=True)
    pm.add_argument("--mutants", required=True)
    pm.add_argument("--faults", default="all")
    pm.add_argument("--out", type=Path, required=True)
    pm.add_argument("--mutant-timeout", type=float, help="hang guard in seconds for each mutant's run (default 1200)")
    pm.add_argument("--one-jvm", action="store_true", help="each port's runs (main and faults) in one session JVM")
    args = ap.parse_args(argv)
    if args.cmd == "prove-mutant":
        return _prove_mutants(
            args.case, args.port, args.mutants.split(","), args.faults, args.out, args.one_jvm, args.mutant_timeout
        )
    if args.cmd == "project":
        return _project_case(args.case, args.project, args.faults, args.port, args.package, args.one_jvm, args.group_id)
    if args.cmd == "junit":
        for p in write_junit(args.golden, args.out, args.package):
            print(p)
        return 0
    if args.cmd == "export":
        return _export_case(args.case, args.out, args.faults)
    notes: list[str] = []
    problems = check(args.golden, args.java, notes)
    for n in notes:
        print(n)
    for p in problems:
        print(p)
    print("golden check: " + ("DIFFERS" if problems else "byte-identical"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
