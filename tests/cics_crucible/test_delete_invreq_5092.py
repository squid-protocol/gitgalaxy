"""#5092 (register X22): DELETE's INVREQ RESP2 values, on the stub (ggcics.c GGCDELT) and on CicsTask over one scenario list.

IBM (CICS TS 6.x, EXEC CICS DELETE): INVREQ RESP2 21, a file that refers to a VSAM ESDS; 22, a generic delete of a file that is not
a KSDS; 25, a GENERIC KEYLENGTH "greater than or equal to the length of a full key"; 42, one "less than zero"; 26, a KEYLENGTH without
GENERIC that is not the key's length; 31, no RIDFLD and no READ UPDATE hold. A GENERIC KEYLENGTH of zero is undocumented and refused by
name. Nothing is deleted or released by an INVREQ; a planned fault is answered first, then an ESDS (21 / 22), then 26 / 25 / 42."""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cics_runtimes import _cics_task, _stub, _stub_base_env, needs_cc, needs_javac  # noqa: E402

# file | flags (_ for a space; - none) | KEYLENGTH value (the key's own length, 3, when the program gave none) | RIDFLD. F is a KSDS
# (key 3: 100a 200b 210c 300d), E an ESDS. Flags are the stub's GG-FLAGS words: GENERIC, KEYLENGTH (given, not generic), HELD.
_SCENARIO = (
    ("F|GENERIC|3|100", "resp=16 resp2=25"),  # GENERIC KEYLENGTH = the key
    ("F|GENERIC|4|100", "resp=16 resp2=25"),
    ("F|GENERIC|100|100", "resp=16 resp2=25"),
    ("F|GENERIC|-1|100", "resp=16 resp2=42"),  # below zero
    ("F|GENERIC|-5|100", "resp=16 resp2=42"),
    ("F|KEYLENGTH|2|100", "resp=16 resp2=26"),  # a KEYLENGTH without GENERIC that is not the key's length
    ("F|KEYLENGTH|4|100", "resp=16 resp2=26"),
    ("F|KEYLENGTH|0|100", "resp=16 resp2=26"),
    ("F|KEYLENGTH|-1|100", "resp=16 resp2=26"),
    ("F|KEYLENGTH|100|100", "resp=16 resp2=26"),
    ("F|-|3|100", "resp=0 resp2=0"),  # none of those deleted anything: this is the first delete of 100
    ("F|KEYLENGTH|3|200", "resp=0 resp2=0"),  # KEYLENGTH = the key: as without it
    ("F|KEYLENGTH|3|200", "resp=13 resp2=80"),
    ("F|-|3|100", "resp=13 resp2=80"),
    ("F|GENERIC|2|21", "resp=0 resp2=0"),  # a valid generic delete still works
    ("F|GENERIC|2|21", "resp=13 resp2=80"),
    ("F|GENERIC|1|3", "resp=0 resp2=0"),
    ("F|HELD|0|-", "resp=16 resp2=31"),  # no hold: 31, as before
    ("E|GENERIC|1|1", "resp=16 resp2=22"),  # a generic delete of an ESDS
    ("E|GENERIC|-1|1", "resp=16 resp2=22"),  # 22 before 42 / 25 ...
    ("E|GENERIC|9|1", "resp=16 resp2=22"),
    ("E|-|3|100", "resp=16 resp2=21"),  # a DELETE of an ESDS
    ("E|KEYLENGTH|2|100", "resp=16 resp2=21"),  # ... and 21 before 26
    ("E|HELD|0|-", "resp=16 resp2=21"),
)
_OPS = [o for o, _ in _SCENARIO]
_WANT = [f"{o} {w}" for o, w in _SCENARIO]
_MAIN = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; } gg_cics;
int GGCDELT(gg_cics *c, char *rid, int kl);
int main(int argc, char **argv) {
    gg_cics c;
    for (int i = 1; i < argc; i++) {
        char file[8], flags[64], rid[8];
        int kl;
        memset(&c, 0, sizeof c);
        memset(c.name1, ' ', 8);
        memset(c.flags, ' ', 40);
        memset(rid, 0, sizeof rid);
        sscanf(argv[i], "%7[^|]|%63[^|]|%d|%7s", file, flags, &kl, rid);
        memcpy(c.name1, file, strlen(file));
        for (char *p = flags; *p; p++) if (*p == '_') *p = ' ';
        if (strcmp(flags, "-") != 0) memcpy(c.flags, flags, strlen(flags));
        GGCDELT(&c, rid, kl);
        printf("%s resp=%d resp2=%d\n", argv[i], c.resp, c.resp2);
    }
    return 0;
}
"""


def _files(work: Path) -> None:
    (work / "f.dat").write_bytes(b"100a200b210c300d")
    (work / "e.dat").write_bytes(b"aaaabbbb")
    (work / "files.cfg").write_text(f"F {work / 'f.dat'} 4 0 3\nE {work / 'e.dat'} 4 0 0 ESDS\n", encoding="ascii")


def _run(exe: Path, work: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**_stub_base_env(), "GGCICS_DIR": str(work), "GGCICS_OUT": str(work / "out")}
    (work / "out").mkdir(parents=True, exist_ok=True)
    return subprocess.run([str(exe), *args], env=env, capture_output=True, text=True, check=False)  # noqa: S603


@needs_cc
def test_the_stub_delete_answers_invreq_21_22_25_26_42_and_leaves_the_file_alone(tmp_path):
    _files(tmp_path)
    done = _run(_stub(tmp_path, _MAIN), tmp_path, *_OPS)
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout.splitlines() == _WANT
    assert (
        tmp_path / "f.dat"
    ).read_bytes() == b""  # the valid deletes in the list took every record; no INVREQ took any
    assert (tmp_path / "e.dat").read_bytes() == b"aaaabbbb"  # the ESDS is untouched


@needs_cc
def test_the_stub_refuses_a_zero_generic_keylength_by_name_and_plans_still_override(tmp_path):
    _files(tmp_path)
    exe = _stub(tmp_path, _MAIN)
    refused = _run(exe, tmp_path, "F|GENERIC|0|100")
    assert refused.returncode == 98 and "DELETE GENERIC KEYLENGTH" in refused.stdout
    (tmp_path / "faults.cfg").write_text("DELETE F 1 12 50\nDELETE E 1 12 51\n", encoding="ascii")
    got = _run(
        exe, tmp_path, "F|GENERIC|3|100", "F|GENERIC|3|100", "E|GENERIC|1|1", "E|GENERIC|1|1"
    ).stdout.splitlines()
    assert got == [
        "F|GENERIC|3|100 resp=12 resp2=50",  # the plan overrides the INVREQ
        "F|GENERIC|3|100 resp=16 resp2=25",
        "E|GENERIC|1|1 resp=12 resp2=51",  # ... and the ESDS one
        "E|GENERIC|1|1 resp=16 resp2=22",
    ]


_JAVA = """
        java.util.TreeMap<String, String> f = new java.util.TreeMap<>(java.util.Map.of(
                "100", "100a", "200", "200b", "210", "210c", "300", "300d"));
        CicsTask t = new CicsTask("T", "ENTER", null, null).withEsds("E", 4, java.util.List.of("aaaa".getBytes(), "bbbb".getBytes()));
        for (String op : new String[] {%s}) {
            String[] p = op.split("[|]");
            String file = p[0];
            java.util.Set<String> w = new java.util.HashSet<>(java.util.Arrays.asList(p[1].split("_")));
            int kl = Integer.parseInt(p[2]);
            String rid = p[3];
            boolean generic = w.contains("GENERIC"), held = w.contains("HELD"), given = w.contains("KEYLENGTH");
            int bad = generic ? (kl < 0 ? 42 : kl >= 3 ? 25 : 0) : given && kl != 3 ? 26 : 0;
            java.util.function.Supplier<java.util.Optional<String>> search = () -> f.keySet().stream()
                    .filter(x -> x.startsWith(rid.substring(0, generic && kl > 0 ? kl : 0))).findFirst();
            int resp;
            if (held) {
                resp = t.deleteHeld(file, () -> {});
            } else if (bad != 0) {
                resp = t.deleteInvalid(file, generic, bad);
            } else if (generic) {
                resp = t.deleteGeneric(file, search.get().isPresent(), () -> {
                    java.util.Optional<String> found;
                    while ((found = search.get()).isPresent()) f.remove(found.get());
                });
            } else {
                resp = t.delete(file, f.containsKey(rid), () -> f.remove(rid));
            }
            System.out.println(op + " resp=" + resp + " resp2=" + t.resp2());
        }
        System.out.println(String.join("", f.values()));"""


@needs_javac
def test_cics_task_delete_answers_invreq_21_22_25_26_42_as_the_stub_does(tmp_path):
    ops = ", ".join(f'"{o}"' for o in _OPS)
    assert _cics_task(tmp_path, _JAVA % ops).splitlines() == [*_WANT, ""]


@needs_javac
def test_cics_task_a_planned_fault_overrides_the_delete_invreq_and_the_esds(tmp_path):
    out = _cics_task(
        tmp_path,
        """
        CicsTask t = new CicsTask("T", "ENTER", null, null).withEsds("E", 4, java.util.List.of("aaaa".getBytes()))
                .withFaults(java.util.List.of("DELETE F 1 12 50", "DELETE E 1 12 51"), null);
        int[] r = {t.deleteInvalid("F", true, 25), t.resp2(), t.deleteInvalid("F", true, 25), t.resp2(),
                   t.deleteGeneric("E", false, () -> {}), t.resp2(), t.deleteGeneric("E", false, () -> {}), t.resp2()};
        System.out.println(java.util.Arrays.toString(r));""",
    )
    assert out.strip() == "[12, 50, 16, 25, 12, 51, 16, 22]"


def test_the_delete_spec_states_each_resp2_both_runtimes_answer():
    from gitgalaxy.standards.cics.commands.files import DELETE

    stated = {(o.condition, o.resp2) for o in DELETE.outcomes}
    assert {
        ("NOTFND", 80),
        ("INVREQ", 21),
        ("INVREQ", 22),
        ("INVREQ", 25),
        ("INVREQ", 26),
        ("INVREQ", 31),
        ("INVREQ", 42),
    } <= stated
    assert not [o for o in DELETE.outcomes if o.resp2 is None]
    assert [r.situation for r in DELETE.runtime_refusals] == ["a GENERIC KEYLENGTH of zero"]
