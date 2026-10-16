"""#5042 (register X58): the SET(ptr) siblings of the pointer lane -- RECEIVE, RETRIEVE, READQ TS, GET CONTAINER, READ, READNEXT
and READPREV with SET(pointer-item) -- run alike by the stub (ggcics.c) and CicsTask, from one list of steps.

A step is a word-line; pointer slots 0 and 1. `rcv S MAX [N]` RECEIVE SET (N: NOTRUNCATE), `rtv S` RETRIEVE SET, `rq S ITEM` READQ TS
SET, `pc NAME TEXT` / `gc S NAME` / `dc NAME` / `mc NAME AS` / `dh` the container commands on channel CH, `rf S KEY [U]` READ SET
(U: UPDATE), `rw KEY` REWRITE, `dl KEY` DELETE, `ul` UNLOCK, `sb KEY` STARTBR, `rn S` / `rp S` READNEXT / READPREV SET, `eb` ENDBR,
`sy` SYNCPOINT, `fm S` FREEMAIN, `rd S N` the first N bytes (hex) of the storage a slot addresses. What each IBM page says ends a
pointer is cited at the case; what it leaves open is refused by name (a last answer that is no step line)."""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_cics_runtimes as R  # noqa: E402  (bare import: tests/ has no __init__.py, see CLAUDE.md)

needs_cc, needs_javac = R.needs_cc, R.needs_javac

_STEPS = (
    "rcv",
    "rtv",
    "rq",
    "pc",
    "gc",
    "dc",
    "mc",
    "dh",
    "rf",
    "rw",
    "dl",
    "ul",
    "sb",
    "rn",
    "rp",
    "eb",
    "sy",
    "fm",
    "rd",
)
_PUT_HELD = (
    "PUT CONTAINER onto a container a GET CONTAINER SET pointer addresses: IBM does not say what the pointer then sees"
)
_MOVE_HELD = (
    "MOVE CONTAINER onto a container a GET CONTAINER SET pointer addresses: IBM does not say what the pointer then sees"
)
_FREEMAIN = "FREEMAIN of storage already freed or received"
_REFUSALS = (_PUT_HELD, _MOVE_HELD, _FREEMAIN)
_Z4, _Z5, _Z8 = "00000000", "0000000000", "0000000000000000"

# (steps, what both runtimes answer). Fixtures: terminal input "hello world"; one START's data "RETRIEVED"; TS queue Q1 with items
# "ITEM-ONE" and "ITEM-TWO!"; file F with the 4-byte records A1aa B2bb C3cc (key: the first 2 bytes).
_CASES = [
    # -- RECEIVE (IBM, RECEIVE (3270 logical): SET "valid until the next receive command or the end of task"; LENGTH "the length of the data")
    (["rcv 0 80", "rd 0 11"], ["rcv 0/0 11", "rd 68656C6C6F20776F726C64"]),
    (["rcv 0 5", "rd 0 5"], ["rcv 22/0 11", "rd 68656C6C6F"]),  # (LENGERR: truncated, LENGTH the original length)
    (["rcv 0 0"], ["rcv 22/0 11"]),
    (
        ["rcv 0 5 N", "rcv 1 80", "rd 0 5", "rd 1 6"],
        ["rcv 0/0 5", "rcv 0/0 6", "rd " + _Z5, "rd 20776F726C64"],
    ),  # (the next RECEIVE ends the first)
    (["rcv 0 80", "fm 0"], ["rcv 0/0 11", _FREEMAIN]),
    # -- RETRIEVE (IBM: "If you use SET you must also include LENGTH"; no validity end is stated: to the task's end, ASSUMED)
    (["rtv 0", "rd 0 9"], ["rtv 0/0 9", "rd 524554524945564544"]),
    (
        ["rtv 0", "rtv 1", "rd 0 9"],
        ["rtv 0/0 9", "rtv 29/0", "rd 524554524945564544"],
    ),  # (ENDDATA: the pointer as it was)
    # -- READQ TS (IBM: "valid until the next READQ TS command or the end of task"; "If you specify the SET option, the LENGTH must be specified")
    (["rq 0 1", "rd 0 8"], ["rq 0/0 8", "rd 4954454D2D4F4E45"]),
    (["rq 0 1", "rq 1 2", "rd 0 8", "rd 1 8"], ["rq 0/0 8", "rq 0/0 9", "rd " + _Z8, "rd 4954454D2D54574F"]),
    (
        ["rq 0 1", "rq 0 3", "rd 0 8"],
        ["rq 0/0 8", "rq 26/0", "rd 4954454D2D4F4E45"],
    ),  # (ITEMERR: the pointer as it was)
    # -- GET CONTAINER (IBM: the data area is kept until a later GET CONTAINER SET of the same container, a DELETE CONTAINER,
    #    a MOVE CONTAINER, the channel leaving scope or a DELETE CHANNEL)
    (["pc A hello", "gc 0 A", "rd 0 5"], ["pc 0/0", "gc 0/0 5", "rd 68656C6C6F"]),
    (
        ["pc A hello", "gc 0 A", "gc 1 A", "rd 0 5", "rd 1 5"],
        ["pc 0/0", "gc 0/0 5", "gc 0/0 5", "rd " + _Z5, "rd 68656C6C6F"],
    ),
    (["pc A hello", "gc 0 A", "dc A", "rd 0 5"], ["pc 0/0", "gc 0/0 5", "dc 0/0", "rd " + _Z5]),
    (["pc A hello", "gc 0 A", "mc A B", "rd 0 5"], ["pc 0/0", "gc 0/0 5", "mc 0/0", "rd " + _Z5]),
    (["pc A hello", "gc 0 A", "dh", "rd 0 5"], ["pc 0/0", "gc 0/0 5", "dh 0/0", "rd " + _Z5]),
    (
        ["pc A hello", "pc B world", "gc 0 A", "gc 1 B", "dc B", "rd 0 5", "rd 1 5"],
        ["pc 0/0", "pc 0/0", "gc 0/0 5", "gc 0/0 5", "dc 0/0", "rd 68656C6C6F", "rd " + _Z5],
    ),  # fmt: skip
    (["pc A hello", "gc 0 NOPE"], ["pc 0/0", "gc 110/10"]),
    (["pc A hello", "gc 0 A", "pc A world"], ["pc 0/0", "gc 0/0 5", _PUT_HELD]),
    (["pc A x", "pc B y", "gc 0 B", "mc A B"], ["pc 0/0", "pc 0/0", "gc 0/0 1", _MOVE_HELD]),
    (["pc A hello", "gc 0 A", "fm 0"], ["pc 0/0", "gc 0/0 5", _FREEMAIN]),
    # -- READ (IBM: valid "until the next READ command for the same file or until completion of a corresponding REWRITE, DELETE,
    #    or UNLOCK command, or a SYNCPOINT in the case of READ UPDATE SET")
    (["rf 0 B2", "rd 0 4"], ["rf 0/0 4", "rd 42326262"]),
    (["rf 0 A1", "rf 1 B2", "rd 0 4", "rd 1 4"], ["rf 0/0 4", "rf 0/0 4", "rd " + _Z4, "rd 42326262"]),
    (["rf 0 ZZ"], ["rf 13/80"]),
    (["rf 0 A1 U", "rw A1", "rd 0 4"], ["rf 0/0 4", "rw 0/0", "rd " + _Z4]),
    (["rf 0 A1 U", "ul", "rd 0 4"], ["rf 0/0 4", "ul 0/0", "rd " + _Z4]),
    (["rf 0 A1 U", "dl A1", "rd 0 4"], ["rf 0/0 4", "dl 0/0", "rd " + _Z4]),
    (
        ["rf 0 A1", "sy", "rd 0 4"],
        ["rf 0/0 4", "sy 0/0", "rd 41316161"],
    ),  # (a plain READ's pointer outlives a SYNCPOINT)
    (["rf 0 A1 U", "sy", "rd 0 4"], ["rf 0/0 4", "sy 0/0", "rd " + _Z4]),
    (
        ["rf 0 A1", "rw A1", "rd 0 4"],
        ["rf 0/0 4", "rw 16/30", "rd 41316161"],
    ),  # (a REWRITE that fails completes nothing)
    (["rf 0 A1 U", "rf 1 B2 U", "rd 0 4"], ["rf 0/0 4", "rf 16/28", "rd 41316161"]),
    (["rf 0 A1", "fm 0"], ["rf 0/0 4", _FREEMAIN]),
    # -- READNEXT / READPREV (IBM: valid "until the next READNEXT or READPREV command specifies SET for the same browse ... no
    #    longer valid after an ENDBR or SYNCPOINT")
    (["sb A1", "rn 0", "rn 1", "rd 0 4", "rd 1 4"], ["sb 0/0", "rn 0/0", "rn 0/0", "rd " + _Z4, "rd 42326262"]),
    (["sb A1", "rn 0", "eb", "rd 0 4"], ["sb 0/0", "rn 0/0", "eb 0/0", "rd " + _Z4]),
    (["sb A1", "rn 0", "sy", "rd 0 4"], ["sb 0/0", "rn 0/0", "sy 0/0", "rd " + _Z4]),
    (["sb C3", "rp 0", "rd 0 4"], ["sb 0/0", "rp 0/0", "rd 43336363"]),
    (
        ["sb C3", "rn 0", "rn 1", "rd 0 4"],
        ["sb 0/0", "rn 0/0", "rn 20/90", "rd 43336363"],
    ),  # (ENDFILE: the pointer as it was)
    (
        ["rf 0 A1", "sb B2", "rn 1", "rd 0 4"],
        ["rf 0/0 4", "sb 0/0", "rn 0/0", "rd 41316161"],
    ),  # (a browse read ends no READ's pointer)
]

_MAIN = r"""
#include <stdio.h>
#include <string.h>
typedef struct { int resp; int resp2; char name1[8]; char name2[8]; char flags[40]; int len;
                 char qname[16]; int item; int num; int go_to; char chan[16]; int hours, mins, secs;
                 char rtran[4], rterm[4], rqueue[8]; char as[16], tochan[16]; } gg_cics;
int GGCRECP(gg_cics *c, void **slot);
int GGCRTRS(gg_cics *c, void **slot);
int GGCRDQS(gg_cics *c, void **slot);
int GGCGETS(gg_cics *c, void **slot);
int GGCPUTC(gg_cics *c, char *from);
int GGCDELC(gg_cics *c);
int GGCMOVC(gg_cics *c);
int GGCDELH(gg_cics *c);
int GGCRDST(gg_cics *c, char *ridfld, int keylen, void **slot);
int GGCRDNS(gg_cics *c, char *ridfld, int keylen, void **slot);
int GGCRDPS(gg_cics *c, char *ridfld, int keylen, void **slot);
int GGCREWR(gg_cics *c, char *from, int fromlen);
int GGCDELT(gg_cics *c, char *ridfld, int keylen);
int GGCUNLK(gg_cics *c);
int GGCSTBR(gg_cics *c, char *ridfld, int keylen);
int GGCENBR(gg_cics *c);
int GGCSYNC(gg_cics *c);
int GGCFREM(gg_cics *c, void **slot);
static gg_cics c;
static char rid[3] = "  ";  /* the program's RIDFLD: STARTBR's key, then the key each READNEXT / READPREV read */
static void set(char *dst, int n, const char *s) { memset(dst, ' ', n); memcpy(dst, s, strlen(s) < (size_t)n ? strlen(s) : (size_t)n); }
static void fresh(const char *flags, const char *file) {
    memset(&c, 0, sizeof c);
    set(c.flags, 40, flags);
    set(c.name1, 8, file);
    set(c.qname, 16, "");
    set(c.chan, 16, "CH");
    set(c.tochan, 16, "CH");
}
static void show(const char *op, int len) {
    printf("%s %d/%d", op, c.resp, c.resp2);
    if (len >= 0 && (c.resp == 0 || c.resp == 22)) printf(" %d", len);
    printf("\n");
}
int main(int argc, char **argv) {
    static void *p[2];
    for (int i = 1; i < argc; i++) {
        char *w[4] = {"", "", "", ""};
        int k = 0;
        for (char *t = strtok(argv[i], " "); t && k < 4; t = strtok(NULL, " ")) w[k++] = t;
        int s = atoi(w[1]);
        if (strcmp(w[0], "rcv") == 0) {
            fresh(k > 3 ? "NOTRUNCATE" : "", "");
            c.len = atoi(w[2]);
            GGCRECP(&c, &p[s]);
            show("rcv", c.len);
        } else if (strcmp(w[0], "rtv") == 0) {
            fresh("INTO", "");
            GGCRTRS(&c, &p[s]);
            show("rtv", c.len);
        } else if (strcmp(w[0], "rq") == 0) {
            fresh("", "");
            set(c.qname, 16, "Q1");
            c.item = atoi(w[2]);
            GGCRDQS(&c, &p[s]);
            show("rq", c.len);
        } else if (strcmp(w[0], "pc") == 0) {
            fresh("CHANNEL", "");
            set(c.qname, 16, w[1]);
            c.len = (int)strlen(w[2]);
            GGCPUTC(&c, w[2]);
            show("pc", -1);
        } else if (strcmp(w[0], "gc") == 0) {
            fresh("CHANNEL", "");
            set(c.qname, 16, w[2]);
            GGCGETS(&c, &p[s]);
            show("gc", c.len);
        } else if (strcmp(w[0], "dc") == 0) {
            fresh("CHANNEL", "");
            set(c.qname, 16, w[1]);
            GGCDELC(&c);
            show("dc", -1);
        } else if (strcmp(w[0], "mc") == 0) {
            fresh("CHANNEL TOCHAN", "");
            set(c.qname, 16, w[1]);
            set(c.as, 16, w[2]);
            GGCMOVC(&c);
            show("mc", -1);
        } else if (strcmp(w[0], "dh") == 0) {
            fresh("", "");
            GGCDELH(&c);
            show("dh", -1);
        } else if (strcmp(w[0], "rf") == 0) {
            fresh(k > 3 ? "UPDATE" : "", "F");
            GGCRDST(&c, w[2], 2, &p[s]);
            show("rf", c.len);
        } else if (strcmp(w[0], "rw") == 0) {
            char rec[5];
            snprintf(rec, sizeof rec, "%s!!", w[1]);
            fresh("", "F");
            GGCREWR(&c, rec, 4);
            show("rw", -1);
        } else if (strcmp(w[0], "dl") == 0) {
            fresh("", "F");
            GGCDELT(&c, w[1], 2);
            show("dl", -1);
        } else if (strcmp(w[0], "ul") == 0) {
            fresh("", "F");
            GGCUNLK(&c);
            show("ul", -1);
        } else if (strcmp(w[0], "sb") == 0) {
            fresh("", "F");
            memcpy(rid, w[1], 2);
            GGCSTBR(&c, rid, 2);
            show("sb", -1);
        } else if (strcmp(w[0], "rn") == 0 || strcmp(w[0], "rp") == 0) {
            fresh("", "F");
            (strcmp(w[0], "rn") == 0 ? GGCRDNS : GGCRDPS)(&c, rid, 2, &p[s]);
            show(w[0], -1);
        } else if (strcmp(w[0], "eb") == 0) {
            fresh("", "F");
            GGCENBR(&c);
            show("eb", -1);
        } else if (strcmp(w[0], "sy") == 0) {
            fresh("", "");
            GGCSYNC(&c);
            show("sy", -1);
        } else if (strcmp(w[0], "fm") == 0) {
            fresh("", "");
            GGCFREM(&c, &p[s]);
            show("fm", -1);
        } else {
            printf("rd ");
            for (int j = 0; j < atoi(w[2]); j++) printf("%02X", ((unsigned char *)p[s])[j]);
            printf("\n");
        }
    }
    return 0;
}
"""

_JAVA = r"""
    static long[] slot = new long[2];
    static java.util.TreeMap<String, byte[]> file = new java.util.TreeMap<>();
    static String rid = "  ";  // the program's RIDFLD: STARTBR's key, then the key each READNEXT / READPREV read
    static final java.nio.charset.Charset L1 = java.nio.charset.StandardCharsets.ISO_8859_1;
    static String show(String op, int resp, int resp2, int len) {
        return op + " " + resp + "/" + resp2 + ((resp == 0 || resp == 22) && len >= 0 ? " " + len : "");
    }
    static void step(CicsTask t, String line) {
        String[] w = line.split(" ");
        String op = w[0];
        int s = w.length > 1 && w[1].matches("\\d") ? Integer.parseInt(w[1]) : 0;
        switch (op) {
            case "rcv" -> {
                CicsTask.Received r = t.receive(Integer.parseInt(w[2]), w.length > 3);
                slot[s] = t.acquireSet("RECEIVE", r.data().getBytes(L1));
                System.out.println(show(op, CicsSpec.resp(r.resp()), 0, r.length()));
            }
            case "rtv" -> {
                CicsTask.RetrieveResult r = t.retrieve(Integer.MAX_VALUE, false, false, false);
                if (r.data() != null) slot[s] = t.acquireSet(null, r.data());
                System.out.println(show(op, CicsSpec.resp(r.resp()), 0, r.length()));
            }
            case "rq" -> {
                CicsTask.TsResult r = t.readqTs("Q1", Integer.parseInt(w[2]), Integer.MAX_VALUE);
                if (r.data() != null) slot[s] = t.acquireSet("READQ", r.data());
                System.out.println(show(op, CicsSpec.resp(r.resp()), 0, r.length()));
            }
            case "pc" -> {
                byte[] d = w[2].getBytes(L1);
                CicsTask.ContainerResult r = t.putContainer("CH", w[1], d, d.length, null, false);
                System.out.println(show(op, CicsSpec.resp(r.resp()), r.resp2(), -1));
            }
            case "gc" -> {
                CicsTask.SetBlock b = t.getContainerSet("CH", w[2]);
                if (b.handle() != 0) slot[s] = b.handle();
                System.out.println(show(op, CicsSpec.resp(b.result().resp()), b.result().resp2(), b.result().length()));
            }
            case "dc" -> {
                CicsTask.ContainerResult r = t.deleteContainer("CH", w[1]);
                System.out.println(show(op, CicsSpec.resp(r.resp()), r.resp2(), -1));
            }
            case "mc" -> {
                CicsTask.ContainerResult r = t.moveContainer("CH", w[1], w[2], "CH");
                System.out.println(show(op, CicsSpec.resp(r.resp()), r.resp2(), -1));
            }
            case "dh" -> {
                CicsTask.ContainerResult r = t.deleteChannel("CH");
                System.out.println(show(op, CicsSpec.resp(r.resp()), r.resp2(), -1));
            }
            case "rf" -> {
                boolean upd = w.length > 3;
                String key = w[2];
                CicsTask.FileRead<byte[]> r = upd ? t.readForUpdate("F", () -> java.util.Optional.ofNullable(file.get(key)))
                                                  : t.read("F", () -> java.util.Optional.ofNullable(file.get(key)));
                if (r.record() != null) slot[s] = t.acquireSet("READ F", r.record(), upd);
                System.out.println(show(op, r.resp(), r.resp2(), r.record() == null ? -1 : r.record().length));
            }
            case "rw" -> {
                int r = t.rewrite("F", () -> { });
                System.out.println(show(op, r, t.resp2(), -1));
            }
            case "dl" -> {
                int r = t.delete("F", file.containsKey(w[1]), () -> file.remove(w[1]));
                System.out.println(show(op, r, t.resp2(), -1));
            }
            case "ul" -> {
                int r = t.unlockHeld("F");
                System.out.println(show(op, r, t.resp2(), -1));
            }
            case "sb" -> {
                rid = w[1];
                int r = t.startbr("F", w[1], false, () -> new java.util.TreeSet<>(file.keySet()));
                System.out.println(show(op, r, t.resp2(), -1));
            }
            case "rn", "rp" -> {
                CicsTask.Browsed r = op.equals("rn") ? t.readnext("F", rid) : t.readprev("F", rid);
                if (r.normal()) {
                    rid = r.key();
                    slot[s] = t.acquireSet("BROWSE F", file.get(r.key()), true);
                }
                System.out.println(show(op, r.resp(), r.resp2(), -1));
            }
            case "eb" -> {
                int r = t.endbr("F");
                System.out.println(show(op, r, t.resp2(), -1));
            }
            case "sy" -> {
                t.syncpoint();
                System.out.println("sy 0/0");
            }
            case "fm" -> {
                int[] r = t.freemain(slot[s]);
                System.out.println(show(op, r[0], r[1], -1));
            }
            default -> {
                byte[] b = t.storageAt(slot[s], 0);
                StringBuilder o = new StringBuilder("rd ");
                for (int j = 0; j < Integer.parseInt(w[2]); j++) o.append(String.format("%02X", b[j] & 0xFF));
                System.out.println(o);
            }
        }
    }
    static CicsTask fixture() {
        file.clear();
        file.put("A1", "A1aa".getBytes(L1));
        file.put("B2", "B2bb".getBytes(L1));
        file.put("C3", "C3cc".getBytes(L1));
        CicsTask.TempStorage ts = new CicsTask.TempStorage().seed("Q1",
                java.util.List.of("ITEM-ONE".getBytes(L1), "ITEM-TWO!".getBytes(L1)));
        return new CicsTask("ZC01", "ENTER", null, null).withTerminalInput("hello world").withTempStorage(ts)
                .withRetrieveData(java.util.List.of("RETRIEVED".getBytes(L1)));
    }
"""


def _fixture_dir(work: Path) -> None:
    """The stub's side of the fixtures (the Java side's are in _JAVA.fixture)."""
    (work / "terminal.in").write_bytes(b"hello world")
    (work / "retrieve_001.bin").write_bytes(b"RETRIEVED")
    q = work / "ts" / "5131"
    q.mkdir(parents=True)
    (q / "000001.bin").write_bytes(b"ITEM-ONE")
    (q / "000002.bin").write_bytes(b"ITEM-TWO!")
    (work / "f.dat").write_bytes(b"A1aaB2bbC3cc")
    (work / "files.cfg").write_text(f"F {work / 'f.dat'} 4 0 2\n", encoding="ascii")


@needs_cc
def test_the_stub_hands_out_set_pointers_as_ibm_documents(tmp_path):
    """#5042 (X58): the stub's SET(ptr) entry points, step list by step list; what IBM leaves open is refused by name."""
    exe = R._stub(tmp_path, _MAIN)
    for n, (steps, answers) in enumerate(_CASES):
        work = tmp_path / f"w{n}"
        work.mkdir()
        _fixture_dir(work)
        out = work / "out"
        out.mkdir()
        env = {**R._stub_base_env(), "GGCICS_DIR": str(work), "GGCICS_OUT": str(out)}
        run = subprocess.run([str(exe), *steps], env=env, capture_output=True, text=True, check=False)  # noqa: S603
        if answers[-1] not in _REFUSALS:
            assert run.returncode == 0 and run.stdout.splitlines() == answers, (steps, run.stdout, run.stderr)
        else:
            assert run.returncode == 98 and answers[-1] + ": not modelled" in run.stdout, (steps, run.stdout)
            assert run.stdout.splitlines()[:-1] == answers[:-1], steps


@needs_javac
def test_cics_task_hands_out_set_pointers_as_the_stub_does(tmp_path):
    """#5042 (X58): CicsTask.acquireSet / invalidateSet and the commands that end a pointer answer the same steps as the stub."""
    parts = []
    for steps, _answers in _CASES:
        run = "\n".join(f'step(t, "{st}");' for st in steps)
        parts.append(
            f"{{ CicsTask t = fixture(); slot = new long[2];\n try {{\n{run}\n}} catch (UnsupportedOperationException e) {{"
            ' System.out.println("refused " + e.getMessage()); }\nSystem.out.println("--"); }'
        )
    out = R._cics_task(tmp_path, "\n".join(parts) + "\n    }\n" + _JAVA + "\n    static void unused() {")
    lines = out.splitlines()
    pos = 0
    for steps, answers in _CASES:
        end = lines.index("--", pos)
        refused = answers[-1] in _REFUSALS
        want = answers[:-1] + [f"refused {answers[-1]}: not modelled"] if refused else answers
        assert lines[pos:end] == want, (steps, lines[pos:end], want)
        pos = end + 1


def test_the_case_table_is_in_the_class():
    """Every member of the SET(ptr) class has a case; a step the list does not know is a typo, not a member."""
    used = {st.split()[0] for steps, _ in _CASES for st in steps}
    assert used <= set(_STEPS)
    for op in ("rcv", "rtv", "rq", "gc", "rf", "rn", "rp"):
        assert op in used, f"no case for {op}"
