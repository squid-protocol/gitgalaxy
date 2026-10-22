"""#5945 (register X47): ZUIDSTCK is one model on two sides -- the port's Zuidstck.java and the oracle's zuidstck.c.

What is proved: both sides write the same 16 bytes for every stated TOD and refuse an unstated or malformed one by the
same name (never a clock reading), the Java side's per-task `state()` wins over the environment (all scenarios share one
JVM), and the harness's `tod` key and `le_call` regex reach the model. What the 16 bytes mean is not proved (X47)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests/tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

pytest.importorskip("tree_sitter_language_pack")
import equivalence_cics as ec  # noqa: E402
from javac_server import javac as javac_run  # noqa: E402

from gitgalaxy.tools.cobol_to_java.det import gen as G  # noqa: E402

C = ROOT / "tests/equivalence/le/zuidstck.c"
RT = ROOT / "gitgalaxy/tools/cobol_to_java/det/cobolrt"
REFUSAL = "ZUIDSTCK: a TOD the run does not state ($GGC_ZUIDSTCK_TOD, 32 hexadecimal digits) is not modelled"
REFUSED = "REFUSED"
VALID = [
    "000102030405060708090A0B0C0D0E0F",
    "0123456789abcdefABCDEF0123456789",
    "0" * 32,
    "F" * 32,
    "D4A3C1B2E5F60718293A4B5C6D7E8F90",
]
# unstated is None
BAD = [None, "", "0" * 31, "0" * 33, "G" * 32, "0" * 30 + " 1", "0x" + "0" * 30, "0" * 32 + "\n"]

C_DRIVER = """
#include <stdio.h>
#include <string.h>
int ZUIDSTCK(unsigned char *);
int main(void) {
    unsigned char b[20];
    memset(b, 0xAA, sizeof b);
    ZUIDSTCK(b);
    for (int i = 0; i < 20; i++) printf("%02X", b[i]);
    printf("\\n");
    return 0;
}
"""

JAVA_PROBE = """
import p.cobolrt.*;
import p.cobolrt.le.*;

public class Probe {
    public static void main(String[] a) {
        boolean viaState = a.length > 0 && a[0].equals("state");
        if (viaState) Zuidstck.state(a[1].isEmpty() ? null : a[1]);
        Storage s = new Storage(20);
        java.util.Arrays.fill(s.bytes, (byte) 0xAA);
        try {
            Zuidstck.call(Field.alphanumeric(s, 0, 16, false));
        } catch (UnsupportedOperationException e) {
            System.out.println("REFUSED|" + e.getMessage());
            return;
        }
        StringBuilder sb = new StringBuilder();
        for (byte x : s.bytes) sb.append(String.format("%02X", x));
        System.out.println(sb);
    }
}
"""


def _jdk() -> Path | None:
    home = os.environ.get("JDK_17") or os.environ.get("JAVA_HOME")
    return Path(home) / "bin" if home and (Path(home) / "bin/javac").is_file() else None


def _env(tod: str | None) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k != "GGC_ZUIDSTCK_TOD"}
    if tod is not None:
        env["GGC_ZUIDSTCK_TOD"] = tod
    return env


@pytest.fixture(scope="module")
def c_exe(tmp_path_factory):
    cc = shutil.which("cc") or shutil.which("gcc")
    if not cc:
        pytest.skip("needs a C compiler")
    d = tmp_path_factory.mktemp("zuidstck_c")
    (d / "main.c").write_text(C_DRIVER)
    exe = d / "probe"
    subprocess.run([cc, "-o", str(exe), str(d / "main.c"), str(C)], check=True)  # noqa: S603
    return exe


def _c(exe: Path, tod: str | None) -> str:
    run = subprocess.run([str(exe)], env=_env(tod), capture_output=True, text=True)  # noqa: S603
    if run.returncode == 98:
        assert run.stderr.strip() == REFUSAL
        return REFUSED
    assert run.returncode == 0, run.stderr
    return run.stdout.strip()


@pytest.fixture(scope="module")
def java_probe(tmp_path_factory):
    jdk = _jdk()
    if jdk is None:
        pytest.skip("needs a JDK 17 (JAVA_HOME / JDK_17)")
    d = tmp_path_factory.mktemp("zuidstck_j")
    out = d / "src/p/cobolrt"
    (out / "le").mkdir(parents=True)
    for f in RT.glob("*.java"):
        (out / f.name).write_text(f.read_text(encoding="utf-8").replace("__PACKAGE__", "p"), encoding="utf-8")
    for f in (RT / "le").glob("*.java"):
        (out / "le" / f.name).write_text(f.read_text(encoding="utf-8").replace("__PACKAGE__", "p"), encoding="utf-8")
    (d / "src/Probe.java").write_text(JAVA_PROBE)
    files = [str(f) for f in (d / "src").rglob("*.java")]
    javac_run([str(jdk / "javac"), "-encoding", "UTF-8", "-nowarn", "-d", str(d / "classes"), *files], check=True)  # noqa: S603
    return jdk, d / "classes"


def _java(probe, tod: str | None, via_state: bool = False, env_tod: str | None = None) -> str:
    jdk, classes = probe
    args = ["state", "" if tod is None else tod] if via_state else []
    run = subprocess.run(  # noqa: S603
        [str(jdk / "java"), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-cp", str(classes), "Probe", *args],
        env=_env(env_tod if via_state else tod),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    out = run.stdout.strip()
    if out.startswith(REFUSED + "|"):
        assert out.split("|", 1)[1] == REFUSAL
        return REFUSED
    return out


@pytest.mark.parametrize("tod", VALID)
def test_the_oracle_writes_the_stated_sixteen_bytes_and_no_more(c_exe, tod):
    assert _c(c_exe, tod) == tod.upper() + "AA" * 4


@pytest.mark.parametrize("tod", BAD, ids=repr)
def test_the_oracle_refuses_an_unstated_or_malformed_tod(c_exe, tod):
    assert _c(c_exe, tod) == REFUSED


def test_the_port_is_the_oracle_byte_for_byte(c_exe, java_probe):
    for tod in [*VALID, *BAD]:
        assert _java(java_probe, tod) == _c(c_exe, tod), repr(tod)


def test_a_task_stated_tod_wins_over_the_environment_and_none_clears_it(java_probe):
    a, b = VALID[0], VALID[4]
    assert _java(java_probe, a, via_state=True, env_tod=b) == a + "AA" * 4
    assert _java(java_probe, b, via_state=True, env_tod=a) == b + "AA" * 4
    assert _java(java_probe, None, via_state=True, env_tod=None) == REFUSED
    # state(null) falls back to the environment: an unstated scenario is refused only if the run states nothing at all
    assert _java(java_probe, None, via_state=True, env_tod=a) == a + "AA" * 4


def test_the_harness_states_the_tod_per_scenario_then_per_case():
    case = {"tod": VALID[0], "scenarios": [{"name": "a"}, {"name": "b", "tod": VALID[1]}]}
    assert ec.scenario_tod(case, case["scenarios"][0]) == VALID[0]
    assert ec.scenario_tod(case, case["scenarios"][1]) == VALID[1]
    assert ec.scenario_tod({"scenarios": [{"name": "c"}]}, {"name": "c"}) is None
    assert ec.case_states_tod(case) and not ec.case_states_tod({"scenarios": [{"name": "c"}]})
    for bad in ("", "0" * 31, "z" * 32, 7):
        with pytest.raises(ec.Unsupported):
            ec.scenario_tod({"scenarios": []}, {"name": "x", "tod": bad})


def test_the_model_is_linked_for_a_program_that_calls_it():
    # the regex lives in build code: read it from source, not by running a build
    text = (ROOT / "tests/tools/equivalence_cics.py").read_text(encoding="utf-8")
    assert "ZUIDSTCK" in text.split("le_call = re.compile(", 1)[1].split(")  # #5858", 1)[0]
    assert "ZUIDSTCK" in G.LIBRARY and (RT / "le/Zuidstck.java").is_file()


def test_the_zecs001_case_states_two_tods_that_differ_in_the_kept_prefix():
    # ZECS001 keeps only THE-TOD(1:6) (ZK-ZF-IDN): two scenarios must differ there, or the case proves nothing about it
    import json

    case = json.loads((ROOT / "tests/equivalence/zecs-zecs001/case.json").read_text(encoding="utf-8"))
    assert case["program"] == "ZECS001" and ec.case_states_tod(case)
    tods = [ec.scenario_tod(case, sc) for sc in case["scenarios"]]
    assert len(tods) >= 2 and all(tods) and len(set(tods)) == len(tods)
    assert len({t[:12] for t in tods}) == len(tods)


def test_every_le_stand_in_of_the_port_has_an_oracle_twin():
    # system-copybook rule (mainframe-evidence-policy 6): a stand-in only with a modelled runtime on both sides.
    # Each port class under cobolrt/le (LeTime is the shared helper) must be a service the oracle's le/*.c defines.
    import re

    oracle = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "tests/equivalence/le").glob("*.c"))
    services = {p.stem.upper() for p in (RT / "le").glob("*.java") if p.stem != "LeTime"}
    assert "ZUIDSTCK" in services
    missing = sorted(s for s in services if not re.search(rf"^int {s}\(", oracle, re.M))
    assert not missing, f"port stand-ins with no oracle twin: {missing}"


def test_the_register_states_the_zuidstck_assumption_as_its_own_assumed_entry():
    """#5945: X69 is ASSUMED, says the bytes are opaque and the layout unmodelled, cites STCK / STCKE as context, and X47 points at it."""
    import register

    meta, body = register.parse_entry(register.REG / "X69.md")
    assert meta["status"] == "ASSUMED"
    assert (
        "ZUIDSTCK's 16 bytes are opaque; the program depends only on them being stated; their STCK/STCKE layout is not modelled"
        in body
    )
    assert "STORE CLOCK (STCK)" in body and "STORE CLOCK EXTENDED (STCKE)" in body
    assert "https://www.ibm.com/" in body
    assert "see X69" in (register.REG / "X47.md").read_text(encoding="utf-8")
    assert not register.check()
