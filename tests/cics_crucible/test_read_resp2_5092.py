"""#5092 box 4 (register X52): the full-key READ's INVREQ / NOTFND RESP2 values, on the stub (ggcics.c) and on CicsTask over one scenario list.

IBM (CICS TS 6.x, EXEC CICS READ): NOTFND RESP2 80, "an attempt to retrieve a record based on the search argument provided is
unsuccessful" (every form: plain, UPDATE, TOKEN, GTEQ, GENERIC); INVREQ RESP2 26, a KEYLENGTH without GENERIC that is not the key's
length; 25, a GENERIC KEYLENGTH "greater than or equal to the length of a full key"; 42, one "less than zero". A GENERIC KEYLENGTH of
zero is undocumented and refused by name. A NOTFND or INVREQ holds nothing; a second tokenless READ UPDATE (28) is checked first, a
planned fault next. INVREQ 20 (resource definition) is ASSUMED never to arise; the option-gated values are refused with their options."""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cics_runtimes import _cics_task, _stub, _stub_base_env, needs_cc, needs_javac  # noqa: E402

# flags (_ for a space; - none) | KEYLENGTH value (what the program gave, else the key's own length 3) | RIDFLD | want.
# Flags are the stub's GG-FLAGS words; KEYLENGTH is among them when the program coded it (GENERIC implies it).
_SCENARIO = (
    ("-|3|150", "resp=13 resp2=80"),  # plain, miss
    ("-|3|100", "resp=0 resp2=0"),
    ("TOKEN_UPDATE|3|150", "resp=13 resp2=80"),  # TOKEN, miss: no token issued
    ("TOKEN_UPDATE|3|100", "resp=0 resp2=0"),
    ("GTEQ|3|300", "resp=13 resp2=80"),  # GTEQ, nothing greater
    ("GTEQ|3|150", "resp=0 resp2=0"),
    ("GENERIC|2|30", "resp=13 resp2=80"),  # GENERIC, no key starts 30
    ("GENERIC|2|10", "resp=0 resp2=0"),
    ("GENERIC|1|2", "resp=0 resp2=0"),
    ("KEYLENGTH|3|100", "resp=0 resp2=0"),  # KEYLENGTH = the key's length: as without it
    ("KEYLENGTH|3|150", "resp=13 resp2=80"),
    ("KEYLENGTH|2|100", "resp=16 resp2=26"),  # not GENERIC, not the key's length
    ("KEYLENGTH|4|100", "resp=16 resp2=26"),
    ("KEYLENGTH|0|100", "resp=16 resp2=26"),
    ("KEYLENGTH|-1|100", "resp=16 resp2=26"),
    ("KEYLENGTH|100|100", "resp=16 resp2=26"),
    ("GTEQ_KEYLENGTH|2|100", "resp=16 resp2=26"),
    ("TOKEN_UPDATE_KEYLENGTH|2|100", "resp=16 resp2=26"),
    ("GENERIC|3|100", "resp=16 resp2=25"),  # GENERIC KEYLENGTH = the key
    ("GENERIC|4|100", "resp=16 resp2=25"),
    ("GENERIC|100|100", "resp=16 resp2=25"),
    ("GENERIC_GTEQ|3|100", "resp=16 resp2=25"),
    ("GENERIC|-1|100", "resp=16 resp2=42"),  # GENERIC KEYLENGTH below zero
    ("GENERIC|-5|100", "resp=16 resp2=42"),
    ("GENERIC_GTEQ_UPDATE|-1|100", "resp=16 resp2=42"),
    ("UPDATE_KEYLENGTH|2|100", "resp=16 resp2=26"),  # an INVREQ holds nothing ...
    ("UPDATE|3|150", "resp=13 resp2=80"),  # ... and a NOTFND holds nothing ...
    ("UPDATE|3|100", "resp=0 resp2=0"),  # ... so this is the first hold
    ("UPDATE_KEYLENGTH|2|100", "resp=16 resp2=28"),  # a second READ UPDATE: 28 before the KEYLENGTH check
    ("UPDATE|3|200", "resp=16 resp2=28"),
    ("UPDATE|3|150", "resp=16 resp2=28"),
)
_OPS = [o for o, _ in _SCENARIO]
_WANT = [f"{o} {w}" for o, w in _SCENARIO]
_MAIN = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; } gg_cics;
int GGCREAD(gg_cics *c, char *rid, int kl, char *into, int il);
int main(int argc, char **argv) {
    gg_cics c;
    for (int i = 1; i < argc; i++) {
        char flags[64], rid[8], into[5] = "....";
        int kl;
        memset(&c, 0, sizeof c);
        memset(c.name1, ' ', 8);
        memcpy(c.name1, "F", 1);
        memset(c.flags, ' ', 40);
        sscanf(argv[i], "%63[^|]|%d|%7s", flags, &kl, rid);
        for (char *p = flags; *p; p++) if (*p == '_') *p = ' ';
        if (strcmp(flags, "-") != 0) memcpy(c.flags, flags, strlen(flags));
        c.len = 4;
        GGCREAD(&c, rid, kl, into, 4);
        printf("%s resp=%d resp2=%d\n", argv[i], c.resp, c.resp2);
    }
    return 0;
}
"""


def _files(work: Path) -> None:
    (work / "f.dat").write_bytes(b"100a200b")
    (work / "files.cfg").write_text(f"F {work / 'f.dat'} 4 0 3\n", encoding="ascii")


def _run(exe: Path, work: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**_stub_base_env(), "GGCICS_DIR": str(work), "GGCICS_OUT": str(work / "out")}
    (work / "out").mkdir(parents=True, exist_ok=True)
    return subprocess.run([str(exe), *args], env=env, capture_output=True, text=True, check=False)  # noqa: S603


@needs_cc
def test_the_stub_read_answers_notfound_80_and_invreq_25_26_42(tmp_path):
    _files(tmp_path)
    done = _run(_stub(tmp_path, _MAIN), tmp_path, *_OPS)
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout.splitlines() == _WANT


@needs_cc
def test_the_stub_refuses_a_zero_generic_keylength_by_name_and_plans_still_override(tmp_path):
    _files(tmp_path)
    exe = _stub(tmp_path, _MAIN)
    refused = _run(exe, tmp_path, "GENERIC|0|100")
    assert refused.returncode == 98 and "READ GENERIC KEYLENGTH" in refused.stdout
    (tmp_path / "faults.cfg").write_text(
        "READ F 1 12 50\n", encoding="ascii"
    )  # the first READ of F: a planned condition
    got = _run(exe, tmp_path, "KEYLENGTH|2|100", "KEYLENGTH|2|100", "-|3|150").stdout.splitlines()
    assert got == [
        "KEYLENGTH|2|100 resp=12 resp2=50",  # the plan overrides the INVREQ, and nothing is read
        "KEYLENGTH|2|100 resp=16 resp2=26",
        "-|3|150 resp=13 resp2=80",
    ]


_JAVA = """
        java.util.TreeMap<String, String> f = new java.util.TreeMap<>(java.util.Map.of("100", "100a", "200", "200b"));
        CicsTask t = new CicsTask("T", "ENTER", null, null);
        for (String op : new String[] {%s}) {
            String[] p = op.split("[|]");
            java.util.Set<String> w = new java.util.HashSet<>(java.util.Arrays.asList(p[0].split("_")));
            int kl = Integer.parseInt(p[1]);
            String rid = p[2];
            boolean generic = w.contains("GENERIC"), gteq = w.contains("GTEQ"), given = generic || w.contains("KEYLENGTH");
            boolean update = w.contains("UPDATE") && !w.contains("TOKEN");
            int bad = !given ? 0 : generic ? (kl < 0 ? 42 : kl >= 3 ? 25 : 0) : kl != 3 ? 26 : 0;
            int n = generic ? kl : 3;
            CicsTask.FileRead<String> r;
            if (bad != 0) {
                r = t.readInvalid("F", update, bad);
            } else if (generic || gteq) {
                r = t.readSearch("F", update, () -> f.values().stream().filter(v -> {
                    int c = v.substring(0, n).compareTo(rid.substring(0, n));
                    return c == 0 || gteq && c > 0;
                }).findFirst());
            } else if (update) {
                r = t.readForUpdate("F", () -> java.util.Optional.ofNullable(f.get(rid)));
            } else {
                r = t.read("F", () -> java.util.Optional.ofNullable(f.get(rid)));
            }
            System.out.println(op + " resp=" + r.resp() + " resp2=" + r.resp2());
        }"""


@needs_javac
def test_cics_task_read_answers_notfound_80_and_invreq_25_26_42_as_the_stub_does(tmp_path):
    ops = ", ".join(f'"{o}"' for o in _OPS)
    assert _cics_task(tmp_path, _JAVA % ops).splitlines() == _WANT


@needs_javac
def test_cics_task_a_planned_fault_overrides_the_keylength_invreq_after_the_hold_check(tmp_path):
    out = _cics_task(
        tmp_path,
        """
        CicsTask t = new CicsTask("T", "ENTER", null, null).withFaults(java.util.List.of("READ F 1 12 50"), null);
        CicsTask.FileRead<String> fa = t.readInvalid("F", false, 26);
        CicsTask.FileRead<String> fb = t.readInvalid("F", false, 26);
        CicsTask.FileRead<String> fc = t.read("F", () -> java.util.Optional.empty());
        System.out.println(fa.resp() + "/" + fa.resp2() + " " + fb.resp() + "/" + fb.resp2() + " " + fc.resp() + "/" + fc.resp2());""",
    )
    assert out.strip() == "12/50 16/26 13/80"


def test_the_read_spec_states_each_resp2_both_runtimes_answer():
    from gitgalaxy.standards.cics.commands.files import READ

    stated = {(o.condition, o.resp2) for o in READ.outcomes}
    assert {("NOTFND", 80), ("INVREQ", 25), ("INVREQ", 26), ("INVREQ", 28), ("INVREQ", 42), ("LENGERR", 11)} <= stated
    assert not [o for o in READ.outcomes if o.resp2 is None]  # no READ outcome left unstated
