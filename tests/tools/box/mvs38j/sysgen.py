#!/usr/bin/env python3
"""Drive Jay Moseley's MVS 3.8J sysgen through Hercules' console (JCL oracle tier 2, #8414).

Internal use only until counsel answers Q16. Stdlib only; runs on the host and starts Hercules in the box image
(`docker run -i`), feeding it commands on stdin and reading its log (which carries the integrated 1052-C console) on
stdout. Stages are small functions over `Hercules`; each one checks the messages and PSW the guide documents and raises
`SysgenError` rather than carry on. Implemented: `starter` (the two stand-alone programs per volume) and `smp1` / `smp2` (starter-system
IPL over the telnet 3215 console, jobs through the card reader at 00C, tape mounts, condcode per job). `stage1` (sysgen00/01 to `stage1.output`) and `stage2` (the converted deck, SYSGEN1..6 released one by one). `stage3` (sysgen02..06, the user mods, FDZ1D02, shutdown of the starter). `ipl` (the first IPL of the generated system over the 009 console, with an optional probe deck). Not yet: Moseley's "Customizing MVS" page: see docs/jcl_oracle_mvs38j.md "Remaining slices".

    sysgen.py starter [--work DIR] [--image IMG] [--name NAME]
    sysgen.py smp1|smp2|stage1|stage2|stage3 [--work DIR] [--image IMG] [--name NAME] [--port N] [--tape VOLSER=FILE ...]
    sysgen.py ipl [--work DIR] [--image IMG] [--name NAME] [--probe DECK]
    sysgen.py serve [--work DIR] [--image IMG] [--name NAME]   # resident box for mvs38j.sh start/stop
    sysgen.py condcode PRINTER_FILE JOB|ALL [--expect STEP=CC ...]
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # run as `python3 -I`: the script dir is not on the path
import console as telnet_console

DEFAULT_WORK = "/srv/storage_16tb/projects/gitgalaxy/mvs38j"
PSW_RE = re.compile(r"HHC02278I Processor CP\d+ PSW: ([0-9A-F]{8}) ([0-9A-F]{8})")
# stand-alone programs (DASDI, then DUMP/RESTORE) per starter volume: (tape address, job card reader). The tape stays
# positioned after each program, so the same address is IPLed twice. Source: iSTARTERv8.htm, V8 May 2024.
STARTER_VOLUMES = (("START1", "280", "00c", "00d"), ("SPOOL0", "281", "00e", "00f"))
PSW_WAITING, PSW_DASDI_DONE, PSW_RESTORE_DONE = "FFFF", "1111", "EEEE"
STANDALONE_ERROR_RE = re.compile(r"IBC\d{3}E|CONTROL STATEMENT ERROR|JOB TERMINATE|HHC00828E")


class SysgenError(RuntimeError):
    pass


class Hercules:
    """One Hercules process in the box image, with its log collected on a thread."""

    def __init__(self, work, conf, image, name, user=None, console_port=None, publish=()):
        self.work, self.conf, self.image, self.name = Path(work), conf, image, name
        self.publish = tuple(publish)  # more loopback-only ports to publish (the card reader socket, 3505)
        self.console_port = console_port  # publish the telnet 3215 console (loopback only) when set
        self.user = user or f"{os.getuid()}:{os.getgid()}"
        self.lines = []
        self._cv = threading.Condition()
        self.proc = None

    def start(self):
        cmd = ["docker", "run", "--rm", "-i", "--name", self.name, "--user", self.user, "-v", f"{self.work}:/mvs"]
        if self.console_port:
            cmd[3:3] = ["-p", f"127.0.0.1:{self.console_port}:3270"]
        for port in self.publish:
            cmd[3:3] = ["-p", f"127.0.0.1:{port}:{port}"]
        cmd += ["-w", "/mvs", "--entrypoint", "hercules", self.image, "-f", self.conf, "--daemon"]
        self.proc = subprocess.Popen(  # noqa: S603
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="backslashreplace",
        )
        threading.Thread(target=self._pump, daemon=True).start()
        self.wait(r"HHC01603I|HHC00100I Thread id \S+, prio -?\d+, name 'timer_thread'", 60)
        return self

    def _pump(self):
        for line in self.proc.stdout:
            with self._cv:
                self.lines.append(line.rstrip("\n"))
                self._cv.notify_all()

    def send(self, command):
        self.proc.stdin.write(command + "\n")
        self.proc.stdin.flush()

    def mark(self):
        with self._cv:
            return len(self.lines)

    def wait(self, pattern, timeout, since=0):
        """The first log line at or after `since` matching `pattern`; SysgenError on timeout or a stand-alone error."""
        rx, end, i = re.compile(pattern), time.monotonic() + timeout, since
        with self._cv:
            while True:
                while i < len(self.lines):
                    if rx.search(self.lines[i]):
                        return self.lines[i]
                    if STANDALONE_ERROR_RE.search(self.lines[i]):
                        raise SysgenError(f"waiting for /{pattern}/: {self.lines[i].strip()}")
                    i += 1
                left = end - time.monotonic()
                if left <= 0:
                    raise SysgenError(f"timed out after {timeout}s waiting for /{pattern}/")
                self._cv.wait(min(left, 1.0))

    def psw_suffix(self, timeout=10):
        """The last four hex digits of the current PSW (the stand-alone programs signal their state there)."""
        since = self.mark()
        self.send("psw")
        return PSW_RE.search(self.wait(PSW_RE.pattern, timeout, since)).group(2)[-4:]

    def wait_psw(self, suffix, timeout):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self.psw_suffix() == suffix:
                return
            time.sleep(1.0)
        raise SysgenError(f"PSW never ended in {suffix} within {timeout}s")

    def quit(self):
        try:
            if self.proc and self.proc.poll() is None:
                self.send("quit")
                self.proc.wait(timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            subprocess.run(["docker", "rm", "-f", self.name], capture_output=True, check=False)  # noqa: S603, S607


def standalone(herc, tape, reader, done_psw, timeout=120):
    """IPL one stand-alone program from `tape`, point it at the job-card `reader` and wait for its done PSW."""
    herc.send(f"ipl {tape}")
    herc.wait_psw(PSW_WAITING, timeout)
    since = herc.mark()
    herc.send("/")  # attention on the 1052-C at 009: the program prompts for its input device
    herc.wait(r"IBC105A\s+DEFINE INPUT DEVICE|IBC\d{3}A", 30, since)
    since = herc.mark()
    herc.send(f"/input=1442,{reader}")
    herc.wait_psw(done_psw, timeout)
    return herc.lines[since:]


def starter(work, image, name):
    """Initialise and restore START1 and SPOOL0 (the starter system's residence and spool volumes)."""
    for need in ("conf/ibcdmprs.cnf", "dasd/start1.3330", "dasd/spool0.3330", "tape/vs2start.het", "tape/vs2spool.het"):
        if not (Path(work) / need).is_file():
            raise SysgenError(f"{work}/{need} missing: run mvs38j.sh stage and dasd starter first")
    herc = Hercules(work, "conf/ibcdmprs.cnf", image, name).start()
    try:
        for volume, tape, dasdi_reader, restore_reader in STARTER_VOLUMES:
            standalone(herc, tape, dasdi_reader, PSW_DASDI_DONE)
            herc.send("stop")
            standalone(herc, tape, restore_reader, PSW_RESTORE_DONE)
            herc.send("stop")
            print(f"starter: {volume} initialised and restored")
    finally:
        herc.quit()


# ---- SMP stages: IPL the starter system, then feed jobs through the reader and answer the operator console ----
JOB_ENDED_RE = re.compile(r"\$HASP395\s+(\S+)\s+ENDED")
# `*IEC501A M 170,MVS38J,SL,6250 BPI,` (live 2026-11-14): a mount is satisfied by readying the drive, so it carries no reply id
MOUNT_RE = re.compile(r"(?:IEC501A|IEF233A)\s+M\s+([0-9A-F]{3}),(\S+?)[,\s]")
# `*02 IEF238D JOB - REPLY DEVICE NAME OR 'CANCEL'`: no online unit fits the job's tape DD (seen live, smp4p44, 2026-11-14)
DEVICE_ASK_RE = re.compile(r"(\d+)\s+IEF238D\s+\S+\s+-\s+REPLY DEVICE NAME")
# `*03 IEC507D REPLY 'U'-USE OR 'M'-UNLOAD`: a mounted volume (START1 holding SYS1.PROCLIB) is not yet in use; use it
# and `*02 ICK003D REPLY U TO ALTER VOLUME 149 CONTENTS, ELSE T` (sysgen00's ICKDSF INIT of each target volume, live 2026-11-14)
USE_ASK_RE = re.compile(r"(\d+)\s+(?:IEC507D\s+REPLY\s+'U'|ICK003D\s+REPLY U )")
# `*01 IEF166D REPLY Y/N TO EXECUTE/SUPPRESS COMMAND`: smp2's reader-preloaded smpmount.jcl issues `M 148,...` (live 2026-11-14)
COMMAND_ASK_RE = re.compile(r"(\d+)\s+IEF166D\s+REPLY Y/N")
# `*06 IEH841D 148    CONFIRM REQUEST TO INITIALIZE`: IEHDASDR ANALYZE of an offline volume asks once per device; `U` confirms
INIT_ASK_RE = re.compile(r"(\d+)\s+IEH841D\s+(\S+)\s+CONFIRM REQUEST TO INITIALIZE")
SMP_CONSOLE_ERRORS = re.compile(r"\bIEA\d{3}E\b|IEC(?!502E)\d{3}E\b|\bABEND\b|\$HASP\d+\s+.*ERROR|HHC00828E")
SMP_IPL_UNIT, SMP_READER = "150", "12"
SMP_TARGET_UNITS = ("148", "149", "14A")  # SMP000 / WORK00 / WORK01 (smp4p44.jcl S5)
# IEHDASDR / IEBUPDTE refuse in a message that is not an E-message: `IEH824I  ANALYZE TERMINATED. DEVICE NOT OFF-LINE`
# Steps of the smp2 decks that end above CC 0 on a fresh build, read from their SMP SYSPRINT (live 2026-11-14).
# Key (JOB, STEP) -> (expected CC, reason). Any other step must end CC 4 or less; a listed step must end at exactly its CC.
SMP2_EXPECTED = {
    ("SMPJOB00", "IEHPROGM"): (
        8,
        "SCRATCH of the 53 SYS1.A* dataset names a fresh SMP000 never held: IEH207I DATA SET OR MEMBER NOT FOUND, UNUSUAL END",
    ),
    ("SMPJOB00", "DLBUCL"): (
        8,
        "UCLIN PTS: DEL SYS removes a system entry a freshly scratched PTS never had (HMA2532)",
    ),
    ("SMPJOB03", "DLBUCL4"): (4, "ACCEPT: linkage editor warnings on the AOSC5 modules (HMA2391 RETURN CODE=04)"),
    ("SMPJOB05", "DLBUCL"): (4, "ACCEPT USERMODS: linkage editor warnings (HMA2391 RETURN CODE=04)"),
    ("SMPJOB06", "DLBUCL"): (4, "REJECT: sysmods never applied or accepted (HMA4081, REJECT RC 04)"),
}
PRINTER_REFUSED_RE = re.compile(r"\bIEH\d{3}I\s+.*TERMINATED")


def printer_file(work, conf):
    """The host path of the first 1403 printer in a Hercules config (the JES2 job log lands there)."""
    for line in (Path(work) / conf).read_text(errors="backslashreplace").splitlines():
        m = re.match(r"\s*[0-9A-Fa-f]{3,4}\s+1403\s+(\S+)", line)
        if m:
            return Path(work) / m.group(1)
    raise SysgenError(f"no 1403 printer in {conf}")


def smp_jobs(work, stage):
    """The stage's job decks in order, from Moseley's configs (verified live 2026-11-14): smp1 runs `smp4p44.jcl` alone (it
    builds SMP 4.44 and needs an IPL after), smp2 (reader preloaded with `smpmount.jcl`) runs `smpjob00..07`."""
    jcl = Path(work, "jcl")
    jobs = [jcl / "smp4p44.jcl"] if stage == "smp1" else sorted(jcl.glob("smpjob*.jcl"))
    jobs = [j for j in jobs if j.is_file()]
    if not jobs:
        raise SysgenError(f"{work}/jcl/smpjob*.jcl missing: run mvs38j.sh stage first")
    return jobs


def with_target_volumes(work, conf, donor="conf/smp2.cnf"):
    """smp1's job (`smp4p44.jcl` step S5, IEHDASDR ANALYZE of 148/149/14A) initialises the SMP000/WORK00/WORK01 volumes, but
    `smp1.cnf` does not define those drives (live 2026-11-14: `IEA001I UNIT 148 INOPERATIVE`, the step hangs). Write
    `<conf>-gg` with the donor config's missing drive lines appended and return its path."""
    have = (Path(work) / conf).read_text(errors="backslashreplace")
    add = [
        ln
        for ln in (Path(work) / donor).read_text(errors="backslashreplace").splitlines()
        if re.match(r"\s*0?(148|149|14A)\s+3350\b", ln, re.I)
        and not re.search(rf"^\s*{ln.split()[0]}\s", have, re.M | re.I)
    ]
    out = conf.replace(".cnf", "-gg.cnf")
    (Path(work) / out).write_text(have.rstrip("\n") + "\n" + "\n".join(add) + ("\n" if add else ""))
    return out


def tape_unit(work, conf):
    """The first 3420 tape drive of a Hercules config (the unit a job's tape DD is pointed at when MVS asks for a device)."""
    for line in (Path(work) / conf).read_text(errors="backslashreplace").splitlines():
        m = re.match(r"\s*([0-9A-Fa-f]{3,4})\s+3420\b", line)
        if m:
            return m.group(1)[-3:].upper()
    raise SysgenError(f"no 3420 tape drive in {conf}")


# volumes the SMP jobs ask for (verified live 2026-11-14 except where the job's DD names them), by tape file under tape/;
# `--tape VOLSER=FILE` overrides. A volser not here is looked up as tape/<volser>.het.
DEFAULT_TAPES = {
    "MVS38J": "tape/zdlib1.het",
    "T74172": "tape/smp4b.het",
    "PTFS20": "tape/ptfs.het",
    "J90012": "tape/j90012.het",
    "STAGE1": "tape/stage1.het",  # sysgen01's continuation job writes the stage 2 deck here (IEBGENER to tape 170)
}


def answer_mounts(herc_cmd, con, since, tapes, seen, unit=None, extra=()):
    """Answer each new IEC501A mount request on the console: `devinit` the tape for its volser (no reply).
    An `IEF238D REPLY DEVICE NAME` ask is answered with `unit` (the config's tape drive); the mount request follows.
    `extra` is ((regex with the reply id as group 1, reply text), ...): further WTORs a stage knows (the custom stage's)."""
    tapes = {**DEFAULT_TAPES, **tapes}
    for line in con.lines[since:]:
        hit = next(((rx.search(line), reply) for rx, reply in extra if rx.search(line)), None)
        if hit and hit[0].group(1) not in seen:
            seen.add(hit[0].group(1))
            con.send(f"r {hit[0].group(1)},{hit[1]}")
            continue
        d = DEVICE_ASK_RE.search(line)
        if d and unit and d.group(1) not in seen:
            seen.add(d.group(1))
            con.send(f"r {d.group(1)},{unit}")
            continue
        u = USE_ASK_RE.search(line)
        if u and u.group(1) not in seen:
            seen.add(u.group(1))
            con.send(f"r {u.group(1)},u")
            continue
        c = COMMAND_ASK_RE.search(line)
        if c and c.group(1) not in seen:
            seen.add(c.group(1))
            con.send(f"r {c.group(1)},y")
            continue
        i = INIT_ASK_RE.search(line)
        if i and i.group(1) not in seen:
            seen.add(i.group(1))
            con.send(f"r {i.group(1)},u")
            continue
        m = MOUNT_RE.search(line)
        if not m or m.groups() in seen:
            continue
        seen.add(m.groups())
        unit, volser = m.groups()
        if volser not in tapes:
            raise SysgenError(f"mount request for volume {volser} on {unit}: pass --tape {volser}=FILE")
        herc_cmd(f"devinit {unit} {tapes[volser]}")


def ipl_starter(herc, con):
    """IPL the starter system (`ipl 150`), answer `clpa` and `format,noreq`, and return the first line after the spool
    questions (`$HASP099`, or smp2's preloaded job's `IEF166D`)."""
    herc.send(f"ipl {SMP_IPL_UNIT}")
    con.wait(r"IEA101A|SPECIFY SYSTEM PARAMETERS", 300)
    con.send("r 0,clpa")
    con.wait(r"\$HASP426|SPECIFY OPTIONS", 300)
    con.send("r 0,format,noreq")
    # a fresh spool asks to confirm the checkpoint change; a warm one does not; smp2's preloaded job asks first
    line = con.wait(r"\$HASP436|\$HASP099|IEF166D", 300)
    if "HASP436" in line:
        rid = re.search(r"(\d+)\s+\$HASP436", line)
        con.send(f"r {rid.group(1) if rid else '01'},y")
        line = con.wait(r"\$HASP099|ALL AVAILABLE FUNCTIONS COMPLETE|IEF166D", 300)
    return line


def await_ended(herc, con, work, conf, label, since, tapes, timeout, ended=1, extra=()):
    """Answer the console until `ended` `$HASP395 ... ENDED` lines have appeared after console mark `since` (JCL error and
    timeout raise SysgenError naming `label`)."""
    seen, end = set(), time.monotonic() + timeout
    while True:
        if sum(1 for ln in con.lines[since:] if JOB_ENDED_RE.search(ln)) >= ended:
            return
        jcl_err = [ln for ln in con.lines[since:] if "IEF452I" in ln]
        if jcl_err or time.monotonic() > end:
            tail = " | ".join(ln.strip() for ln in con.lines[-8:])
            why = jcl_err[0].strip() if jcl_err else f"{ended} x $HASP395 ENDED not seen within {timeout}s"
            raise SysgenError(f"{label}: {why}; console tail: {tail}")
        answer_mounts(herc.send, con, since, tapes, seen, tape_unit(work, conf), extra)
        time.sleep(2)


def run_deck(herc, con, work, conf, job, tapes, timeout, ended=1):
    """Feed `job` through the reader and answer the console until `ended` `$HASP395 ... ENDED` lines (the job, plus any it
    submits to the internal reader) have appeared; return the console mark taken before the deck, so the caller can read
    what the deck printed."""
    since = con.mark()
    herc.send(f"devinit {SMP_READER} {Path(job).relative_to(work)}")
    await_ended(herc, con, work, conf, Path(job).name, since, tapes, timeout, ended)
    return since


# smpjob07 submits a second job of the same name through the internal reader (`$HASP100 SMPJOB07 ON INTRDR  LINK UTILITIES`)
# that relinks ICKDSF into SYS1.LINKLIB; quitting Hercules after the first `ENDED` left the starter without ICKDSF, and
# sysgen00's ICKDSF step then abended S806 (live 2026-11-14).
SMP_ENDED = {"smpjob07.jcl": 2}


def smp_stage(work, image, name, stage, tapes, port=3270, job_timeout=1800):
    """IPL the starter system with `conf/<stage>.cnf`, run each smpjob deck and check its steps ran (condcode)."""
    conf = f"conf/{stage}.cnf"
    if not (Path(work) / conf).is_file():
        raise SysgenError(f"{work}/{conf} missing: run mvs38j.sh stage first")
    jobs = smp_jobs(work, stage)
    if stage == "smp1":
        conf = with_target_volumes(work, conf)
    herc = Hercules(work, conf, image, name, console_port=port).start()
    herc.wait(r"HHC01024I", 60)  # the console listener; docker's proxy accepts earlier and then drops the connection
    con = telnet_console.Console(port=port).connect()
    try:
        line = ipl_starter(herc, con)
        if stage == "smp2":  # the reader was preloaded with smpmount.jcl by the config: confirm its MOUNT command
            ask = line if COMMAND_ASK_RE.search(line) else con.wait(COMMAND_ASK_RE.pattern, 300)
            con.send(f"r {COMMAND_ASK_RE.search(ask).group(1)},y")
            con.wait(r"\$HASP395\s+SMPMOUNT\s+ENDED", 300)
            print(f"{stage}: SMPMOUNT ended")
        if (
            stage == "smp1"
        ):  # IEHDASDR ANALYZE (S5) refuses a device that is online: IEH824I "DEVICE NOT OFF-LINE" (live 2026-11-14)
            for unit in SMP_TARGET_UNITS:
                con.send(f"v {unit},offline")
                time.sleep(3)  # the starter system echoes nothing for VARY (seen live)
        printed = printer_file(work, conf)
        printed_from = printed.stat().st_size if printed.exists() else 0
        for job in jobs:
            since = run_deck(herc, con, work, conf, job, tapes, job_timeout, SMP_ENDED.get(job.name, 1))
            bad = [ln for ln in con.lines[since:] if SMP_CONSOLE_ERRORS.search(ln)]
            if bad:
                raise SysgenError(f"{job.name}: {bad[0].strip()}")
            print(f"{stage}: {job.name} ended")
        text = printed.read_bytes()[printed_from:].decode("latin-1")
        refused = [ln.strip() for ln in text.splitlines() if PRINTER_REFUSED_RE.search(ln)]
        if refused:
            raise SysgenError(f"{stage}: {refused[0]}")
        results = step_results(text)
        failed = smp_failed_steps(results, SMP2_EXPECTED if stage == "smp2" else {})
        if failed:
            raise SysgenError(f"{stage}: {len(failed)} step(s) not executed or over CC 4, first {failed[0]}")
        print(f"{stage}: {len(results)} steps checked (condcode)")
    finally:
        con.close()
        herc.quit()


# ---- stage 1: initialise the target volumes (sysgen00) and assemble the stage 1 deck onto tape (sysgen01) ----
# Steps of sysgen00 / sysgen01 allowed above CC 0 on a fresh build: key (JOB, STEP) -> (CC, reason); filled from live runs.
STAGE1_EXPECTED = {
    ("SYSGEN00", "IEHPROGM"): (8, "SCRATCH of work datasets a fresh WORK01 never held (IEH207I)"),
    ("SYSGEN01", "CLEANUP"): (8, "deletes the previous run's stage 1 output, absent on a fresh build"),
}
# (deck, `$HASP395 ENDED` count: the deck plus the jobs it submits). FDZ1D02 (ICKDSF R13) is NOT run here: it names the target
# master catalog as JOBCAT, so it belongs after sysgen00 has defined it (its IEWL step is `IEF212I JOBCAT - DATA SET NOT
# FOUND`, not executed, when run first; Moseley runs it last, after the target system is generated).
STAGE1_DECKS = (("sysgen00.jcl", 3), ("sysgen01.jcl", 2))


def attach_targets(herc, work):
    """Send the `attach` lines of `conf/sysgen.script` (149 MVSRES, 14A MVS000, 14B SPOOL1, 14C PAGE00: the target volumes)."""
    for ln in (Path(work) / "conf/sysgen.script").read_text(errors="backslashreplace").splitlines():
        if ln.strip().lower().startswith("attach "):
            herc.send(ln.strip())


def stage1(work, image, name, tapes, port=3270, job_timeout=1800):
    """IPL the starter system with `conf/sysgen.cnf`, attach the target volumes (`conf/sysgen.script`), run sysgen00 then
    sysgen01, and extract `stage1.output` from `tape/stage1.het` with the image's `hetget` for stage 2."""
    conf = "conf/sysgen.cnf"
    for need in (conf, "conf/sysgen.script", "jcl/sysgen00.jcl", "jcl/sysgen01.jcl", "tape/stage1.het"):
        if not (Path(work) / need).is_file():
            raise SysgenError(f"{work}/{need} missing: run mvs38j.sh stage first")
    herc = Hercules(work, conf, image, name, console_port=port).start()
    herc.wait(r"HHC01024I", 60)
    con = telnet_console.Console(port=port).connect()
    try:
        ipl_starter(herc, con)
        attach_targets(herc, work)
        printed = printer_file(work, conf)
        printed_from = printed.stat().st_size if printed.exists() else 0
        for deck, ended in STAGE1_DECKS:
            since = run_deck(herc, con, work, conf, Path(work) / "jcl" / deck, tapes, job_timeout, ended)
            bad = [ln for ln in con.lines[since:] if SMP_CONSOLE_ERRORS.search(ln)]
            if bad:
                raise SysgenError(f"{deck}: {bad[0].strip()}")
            print(f"stage1: {deck} ended")
        text = printed.read_bytes()[printed_from:].decode("latin-1")
        results = step_results(text)
        failed = smp_failed_steps(results, STAGE1_EXPECTED)
        if failed:
            raise SysgenError(f"stage1: {len(failed)} step(s) not executed or over CC 4, first {failed[0]}")
        print(f"stage1: {len(results)} steps checked (condcode)")
    finally:
        con.close()
        herc.quit()
    hetget(work, image, name, "tape/stage1.het", "stage1.output", 1)


def convert_stage1(text):
    """Port of Moseley's `stage2.awk`: turn `stage1.output` (the deck sysgen01 punched) into the stage 2 deck. SYSGEN1..5 are
    held (`TYPRUN=HOLD,TIME=1439`) with the target master catalog as JOBCAT, SYSGEN6 arrives held already, EXPDT=99350
    becomes 00000, SYSGEN6's STEPY runs IEFBR14, and the blank and `||||||||||` separator cards are dropped."""
    out, jobcat = [], "//JOBCAT   DD  DSN=SYS1.VSAM.MASTER.CATALOG,DISP=SHR"
    for raw in text.splitlines():
        card = raw.rstrip(" \t\r\n")
        if " JOB " in raw:
            name = raw.split()[0]
            if name == "//SYSGEN6":
                out += ["//", raw]
                continue
            if name != "//SYSGEN1":
                out.append("//")
            out += [card + ",", "//             TYPRUN=HOLD,TIME=1439", "/*JOBPARM LINES=100", jobcat]
        elif " TYPRUN=HOLD" in raw:
            out += [raw, "/*JOBPARM LINES=100"]
        elif "EXPDT=99350" in raw:
            out.append(raw.replace("99350", "00000", 1))
        elif "STEPY" in raw:
            out.append("//STEPY EXEC PGM=IEFBR14")
        elif raw and not raw.startswith("||||||||||"):
            out.append(raw)
    return "\n".join([*out, "//"]) + "\n"


TARGET_UNITS = ("149", "14A", "14B", "14C")  # the `attach` lines of conf/sysgen.script
# Steps of SYSGEN1..6 allowed above CC 4 (live 2026-11-19, fresh volumes: 130 steps; nine `LK` link-edit steps in SYSGEN1/2 end CC 4, within bound).
STAGE2_EXPECTED = {
    ("SYSGEN6", "STEPZ1"): (
        8,
        "IEHPROGM SCRATCH of SYS1.NUCLEUS(SYSCATLG): IEH207I DATA SET OR MEMBER NOT FOUND on a fresh build",
    ),
}
STAGE2_JOBS = tuple(f"SYSGEN{n}" for n in range(1, 7))


def stage2(work, image, name, tapes, port=3270, job_timeout=3600):
    """Convert `stage1.output` to `jcl/stage2.jcl`, IPL the starter system, attach the target volumes, submit the deck
    (every job but SYSGEN6 arrives held) and release SYSGEN1..6 one at a time with `$A'SYSGENn'`, waiting for each to end."""
    conf = "conf/sysgen.cnf"
    src = Path(work) / "stage1.output"
    if not src.is_file() or "SYSGEN1" not in src.read_text(errors="backslashreplace"):
        raise SysgenError(f"{src} missing or empty: run `sysgen stage1` first")
    deck = Path(work) / "jcl/stage2.jcl"
    deck.write_text(convert_stage1(src.read_text(errors="backslashreplace")))
    herc = Hercules(work, conf, image, name, console_port=port).start()
    herc.wait(r"HHC01024I", 60)
    con = telnet_console.Console(port=port).connect()
    try:
        ipl_starter(herc, con)
        attach_targets(herc, work)
        for unit in TARGET_UNITS:  # SYSGEN1 allocates MVSRES on 3350: an attached volume is offline (`IEF247I ... 149 OFFLINE`, live 2026-11-19)
            con.send(f"v {unit},online")
            time.sleep(
                3
            )  # back-to-back lines overrun the 3215 input buffer (`HHC02913E COMM: Buffer overrun` drops the console); VARY echoes nothing
        printed = printer_file(work, conf)
        printed_from = printed.stat().st_size if printed.exists() else 0
        deck_since = con.mark()
        herc.send(f"devinit {SMP_READER} {deck.relative_to(work)}")
        for job in STAGE2_JOBS:
            since = con.mark()
            # `$A` before `$HASP101 <job> HELD` answers `$HASP000 NOT HELD` and the job then waits forever (live 2026-11-19)
            # the reader queues the next job while the last runs, so look from the deck's start, not this job's mark
            con.wait(rf"\$HASP101\s+{job}\s+HELD", 600, deck_since)
            con.send(f"$A'{job}'")
            await_ended(herc, con, work, conf, job, since, tapes, job_timeout)
            bad = [ln for ln in con.lines[since:] if SMP_CONSOLE_ERRORS.search(ln)]
            if bad:
                raise SysgenError(f"{job}: {bad[0].strip()}")
            print(f"stage2: {job} ended")
        results = step_results(printed.read_bytes()[printed_from:].decode("latin-1"))
        failed = smp_failed_steps(results, STAGE2_EXPECTED)
        if failed:
            raise SysgenError(f"stage2: {len(failed)} step(s) not executed or over CC 4, first {failed[0]}")
        print(f"stage2: {len(results)} steps checked (condcode)")
    except (SysgenError, telnet_console.ConsoleError):
        print("stage2: Hercules log tail:\n" + "\n".join(ln.rstrip() for ln in herc.lines[-15:]), file=sys.stderr)
        raise
    finally:
        con.close()
        herc.quit()


# Moseley's "after stage 2" order (iSYSGENv8.htm, fetched 2026-11-19), all on the still-running STARTER system: sysgen02..06, the
# seven USERMODS jobs, FDZ1D02. Value = `$HASP395 ENDED` lines the deck makes: sysgen04 and FDZ1D02 submit a second job of the
# same name, USERMODS is seven jobs in one file. Tapes the decks ask for, by volser (read from the decks' VOL=SER, not guessed):
# sysgen03 PVTMAC, usermods SMPPTF, fdz1d02 MVS38J (which DEFAULT_TAPES maps to zdlib1, so it is overridden here).
STAGE3_DECKS = (
    ("sysgen02.jcl", 1),
    ("sysgen03.jcl", 1),
    ("sysgen04.jcl", 2),
    ("sysgen05.jcl", 1),
    ("sysgen06.jcl", 1),
    ("usermods.jcl", 7),
    ("fdz1d02.jcl", 2),
)
STAGE3_TAPES = {"PVTMAC": "tape/apvtmacs.het", "SMPPTF": "tape/usermods.het", "MVS38J": "tape/dz1d02.het"}
# Steps above CC 4 allowed: none (Moseley's expected codes are 0, with CC 4 for sysgen06's HMASMP and four USERMODS link-edit warnings).
STAGE3_EXPECTED: dict = {}


# Seen live (2026-11-19, a second starter IPL over the finished volumes): `$p jes2` prints `$HASP395 INIT ENDED` and, when JES2
# is down, `IEF142I JES2 JES2 - STEP WAS EXECUTED - COND CODE 0000`; `z eod` prints `IEE334I HALT     EOD SUCCESSFUL`. A
# first guess at `$HASP085 ... TERMINATION COMPLETE` never appeared (the stage timed out after the decks had all passed).
JES2_STOPPED_RE = r"IEF142I JES2 JES2 - STEP WAS EXECUTED"
EOD_DONE_RE = r"IEE334I\s+HALT\s+EOD SUCCESSFUL"


def shutdown_starter(herc, con):
    """Moseley's "Shut Down the Starter System": `$p jes2`, `z eod`, `quiesce`, then Hercules `quit`."""
    con.send("$p jes2")
    con.wait(JES2_STOPPED_RE, 300)
    con.send("z eod")
    con.wait(EOD_DONE_RE, 300)
    con.send("quiesce")
    time.sleep(10)


def stage3(work, image, name, tapes, port=3270, job_timeout=3600):
    """IPL the starter system with `conf/sysgen.cnf` over the stage 2 volumes, attach the target volumes, run sysgen02..06,
    the user mods and FDZ1D02 through the reader (tapes answered by volser), check every step's completion code, then shut
    down JES2 and MVS the way Moseley does. The first IPL of the generated system is the next page of his guide, not here."""
    conf = "conf/sysgen.cnf"
    for need in (conf, "conf/sysgen.script", *(f"jcl/{d}" for d, _ in STAGE3_DECKS), *STAGE3_TAPES.values()):
        if not (Path(work) / need).is_file():
            raise SysgenError(f"{work}/{need} missing: run mvs38j.sh stage first")
    stage2_deck = Path(work) / "jcl/stage2.jcl"
    if not stage2_deck.is_file():
        raise SysgenError(f"{stage2_deck} missing: run `sysgen stage2` first")
    tapes = {**STAGE3_TAPES, **tapes}
    herc = Hercules(work, conf, image, name, console_port=port).start()
    herc.wait(r"HHC01024I", 60)
    con = telnet_console.Console(port=port).connect()
    try:
        ipl_starter(herc, con)
        attach_targets(herc, work)
        for unit in TARGET_UNITS:
            con.send(f"v {unit},online")
            time.sleep(3)  # paced: back-to-back lines overrun the 3215 input buffer (see stage2)
        printed = printer_file(work, conf)
        printed_from = printed.stat().st_size if printed.exists() else 0
        for deck, ended in STAGE3_DECKS:
            since = run_deck(herc, con, work, conf, Path(work) / "jcl" / deck, tapes, job_timeout, ended)
            bad = [ln for ln in con.lines[since:] if SMP_CONSOLE_ERRORS.search(ln)]
            if bad:
                raise SysgenError(f"{deck}: {bad[0].strip()}")
            print(f"stage3: {deck} ended")
        results = step_results(printed.read_bytes()[printed_from:].decode("latin-1"))
        failed = smp_failed_steps(results, STAGE3_EXPECTED)
        if failed:
            raise SysgenError(f"stage3: {len(failed)} step(s) not executed or over CC 4, first {failed[0]}")
        print(f"stage3: {len(results)} steps checked (condcode)")
        shutdown_starter(herc, con)
    except (SysgenError, telnet_console.ConsoleError):
        print("stage3: Hercules log tail:\n" + "\n".join(ln.rstrip() for ln in herc.lines[-15:]), file=sys.stderr)
        raise
    finally:
        con.close()
        herc.quit()


# Moseley's "IPL the MVS System" page (iCUSTv8, read 2026-11-19) and what this box printed live the same day: `ipl 150`;
# IEA101A -> `r 0,clpa`; IFB010D -> `r 0,u`; $HASP426 -> `r 1,format,noreq`; $HASP479 -> `r 2,y`; $HASP436 -> `r 3,y`; the IPL is
# done at `$HASP099 ALL AVAILABLE FUNCTIONS COMPLETE`. SYSC.LINKLIB / SYSC.PROCLIB live on SYSCPK: without it the IPL stops at
# IEA317A (a blank 3350 of that volser is refused as an unacceptable unit), so the real volume is needed (a 3350 image).
SYSCPK_ARCHIVE = "dl/SYSCPK/SYSCPK.tar.gz"
SYSCPK_IMAGE = "dl/SYSCPK/x/dasd/syscpk.3350"
IPL_REPLIES = (  # (message pattern, reply)
    (r"IEA101A", "r 0,clpa"),
    (r"\*(\d+)\s+IFB010D", "r {id},u"),
    (r"\*(\d+)\s+\$HASP426", "r {id},format,noreq"),
    (r"\*(\d+)\s+\$HASP479", "r {id},y"),
    (r"\*(\d+)\s+\$HASP436", "r {id},y"),
)
# Warm IPL (Moseley iNORMv8, read 2026-11-19): $HASP426 -> `r 1,noreq` keeps the JES2 queues as the last shutdown left them;
# `format` is for the first IPL (it also draws the two checkpoint-reset prompts). A marker file records the first IPL.
IPL_DONE_MARKER = "ipl.done"
CUSTOM_MARKER = "custom.done"
IPL_READY_RE = r"\$HASP099\s+ALL AVAILABLE FUNCTIONS COMPLETE"
IPL_FATAL_RE = re.compile(r"IEA317A|IEA3\d\dI.*UNACCEPTABLE|IEA\d{3}W|\bWAIT STATE\b|HHC00828E")


def ipl_conf(work):
    """Write `conf/mvs.conf` (the file `mvs38j.sh start` and the image's CMD read) from Moseley's `conf/mvs.cnf`: the 1052-C
    at 009 takes `/` commands from the Hercules console (no tn3270 client), so the 3270 master console at 010 is commented
    out. Idempotent; returns the conf path relative to `work`."""
    src, dst = Path(work) / "conf/mvs.cnf", Path(work) / "conf/mvs.conf"
    if not src.is_file():
        raise SysgenError(f"{src} missing: run mvs38j.sh stage first")
    out = []
    for line in src.read_text().splitlines():
        if re.match(r"0010\s+3270\s+console", line):
            line = "#" + line
        elif re.match(r"#0009\s+3215-C\s+/", line):
            line = line[1:]
        elif (Path(work) / CUSTOM_MARKER).exists() and re.match(r"#(0180|0190)\s", line):
            line = line[1:]  # PUB000 / PUB001 are initialized: attached at every later IPL (Moseley's "remove the hash")
        out.append(
            re.sub(r"^(000C\s+3505\s+)localhost:3505\b", r"\g<1>3505", line)
        )  # bind every interface: docker's publish needs it
    dst.write_text("\n".join(out) + "\n")
    return "conf/mvs.conf"


def ipl_replies(warm):
    """IPL_REPLIES, with the JES2 start reply `noreq` (warm) instead of `format,noreq` (first IPL)."""
    return tuple((p, r.replace(",format,noreq", ",noreq") if warm else r) for p, r in IPL_REPLIES)


def ipl_system(herc, timeout=600, warm=False):
    """Drive the first IPL of the generated system: `ipl 150`, the console replies in IPL_REPLIES as each message appears,
    until the JES2-ready line. Returns the log mark taken before the IPL. A fatal wait or IEA317A raises."""
    since = herc.mark()
    herc.send("ipl 150")
    replies = ipl_replies(warm)
    patterns = [re.compile(p) for p, _ in replies]
    done, end, i = set(), time.monotonic() + timeout, since
    ready = re.compile(IPL_READY_RE)
    while time.monotonic() < end:
        with herc._cv:
            lines = herc.lines[i:]
            i = len(herc.lines)
        for ln in lines:
            if ready.search(ln):
                return since
            if IPL_FATAL_RE.search(ln):
                raise SysgenError(f"ipl: {ln.strip()}")
            for k, (rx, (_, reply)) in enumerate(zip(patterns, replies, strict=True)):
                m = rx.search(ln)
                if m and k not in done:
                    done.add(k)
                    herc.send("/" + reply.format(id=m.group(1) if m.groups() else ""))
        time.sleep(0.5)
    raise SysgenError(f"ipl: no {IPL_READY_RE} within {timeout}s; replies given: {sorted(done)}")


def shutdown_system(herc):
    """`$p jes2`, `z eod`, `quiesce` on the 009 console, then Hercules `quit` (the generated system's JES2 stop message)."""
    since = herc.mark()
    herc.send("/$p jes2")
    herc.wait(JES2_STOPPED_RE + r"|\$HASP085|\$HASP099", 300, since)
    herc.send("/z eod")
    herc.wait(EOD_DONE_RE, 300, since)
    herc.send("/quiesce")
    time.sleep(10)


def ipl(work, image, name, probe=None, job_timeout=90):
    """The first IPL of the generated system (needs the stage 3 volumes and SYSCPK in `dasd/`), reaching the JES2-ready line.
    With `probe` (a JCL deck), submit it through the card reader socket (3505, published on the loopback) with the
    runner and print its parsed log, and check the runner's patterns against the live console log. Then shut down."""
    if not (Path(work) / "dasd/mvsres.3350").is_file():
        raise SysgenError(f"{work}/dasd/mvsres.3350 missing: run the sysgen stages first")
    syscpk = Path(work) / "dasd/syscpk.3350"
    if not syscpk.is_file():
        src = Path(work) / SYSCPK_IMAGE
        if not src.is_file():
            raise SysgenError(f"{syscpk} missing: run `mvs38j.sh tapes` (downloads SYSCPK) first")
        shutil.copyfile(src, syscpk)
    conf = ipl_conf(work)
    herc = Hercules(work, conf, image, name, publish=(3505,)).start()
    try:
        marker = Path(work) / IPL_DONE_MARKER
        since = ipl_system(herc, warm=marker.exists())
        marker.write_text("first IPL done; later IPLs are warm (JES2 reply noreq)\n")
        print(f"ipl: JES2 ready ({len(herc.lines) - since} log lines)")
        if probe:
            probe_deck(herc, work, conf, probe, job_timeout)
        shutdown_system(herc)
    except SysgenError:
        print("ipl: Hercules log tail:\n" + "\n".join(ln.rstrip() for ln in herc.lines[-15:]), file=sys.stderr)
        raise
    finally:
        herc.quit()


# Moseley's "Customizing" page (iCUSTv8, read 2026-11-20): attach PUB000 (3380 at 180) and PUB001 (3390 at 190) with
# conf/mvs.script, then submit MVS00 (ICKDSF init of both, then a CLASS S continuation job that varies them online and imports
# the SYSCPK catalog), MVS01 (user catalogs), MVS02 (two TSO ids, 15 steps each) and MVS03 (four TSO apps from tape/tsoaps.het at
# 100, plus Greg Price's GREGQ job it submits). Each prints its page's expected codes: every step 0000. The page does not
# name the ICKDSF confirmation or the master-catalog password message ids (screenshots), so those WTORs are matched by
# their text and the live run must confirm them. Job end counts: MVS00 and MVS03 each submit a second job.
CUSTOM_DECKS = (("mvs00.jcl", 2), ("mvs01.jcl", 1), ("mvs02.jcl", 1), ("mvs03.jcl", 2))
CUSTOM_VOLUMES = ("dasd/pub000.3380", "dasd/pub001.3390")
CUSTOM_TAPES = {"TSOAPS": "tape/tsoaps.het"}
CUSTOM_REPLIES = (  # (WTOR regex with the reply id first, reply): the password is Moseley's SYSPROG
    (re.compile(r"\*(\d+)\s+.*\bPASSWORD\b", re.IGNORECASE), "sysprog"),
    (re.compile(r"\*(\d+)\s+ICK\d{3}D\b.*\bREPLY\b"), "u"),
)


class SlashConsole:
    """The 009 console of the generated system seen the way `answer_mounts` reads a console: `lines` is the Hercules log,
    `send` types `/r N,..` at the Hercules prompt."""

    def __init__(self, herc):
        self.herc = herc

    @property
    def lines(self):
        return self.herc.lines

    def send(self, text):
        self.herc.send("/" + text)


def custom_failed_steps(results):
    """Steps of the customizing jobs not executed or not completing 0000 (the page's expected code for every step)."""
    return [r for r in results if not r["executed"] or r["cond_code"] != 0]


def custom(work, image, name, job_timeout=900):
    """IPL the generated system, attach the two new volumes, run MVS00..MVS03 through the card reader answering the console
    (ICKDSF confirm, master catalog password, the tsoaps tape), require every step 0000, then shut down. Writes
    `custom.done`, after which `ipl_conf` attaches PUB000 / PUB001 at every IPL."""
    work = Path(work)
    for need in (*CUSTOM_VOLUMES, "dasd/mvsres.3350", "dasd/syscpk.3350", "conf/mvs.script", *CUSTOM_TAPES.values()):
        if not (work / need).is_file():
            raise SysgenError(f"{work}/{need} missing: run `mvs38j.sh dasd user` / the earlier stages first")
    for deck, _ in CUSTOM_DECKS:
        if not (work / "jcl" / deck).is_file():
            raise SysgenError(f"{work}/jcl/{deck} missing: run mvs38j.sh stage first")
    import runner

    (work / CUSTOM_MARKER).unlink(missing_ok=True)  # the volumes are not initialized yet: IPL without them
    conf = ipl_conf(work)
    herc = Hercules(work, conf, image, name, publish=(3505,)).start()
    con = SlashConsole(herc)
    try:
        ipl_system(herc, warm=(work / IPL_DONE_MARKER).exists())
        (work / IPL_DONE_MARKER).write_text("first IPL done; later IPLs are warm (JES2 reply noreq)\n")
        for line in (work / "conf/mvs.script").read_text().splitlines():
            if line.startswith("attach "):
                herc.send(line)
        printed = printer_file(work, conf)
        printed_from = printed.stat().st_size if printed.exists() else 0
        for deck, ended in CUSTOM_DECKS:
            since = herc.mark()
            runner.submit(str(work / "jcl" / deck))
            await_ended(herc, con, work, conf, deck, since, CUSTOM_TAPES, job_timeout, ended, CUSTOM_REPLIES)
            print(f"custom: {deck} ended")
        time.sleep(5)  # the printer file lags the console
        results = step_results(printed.read_bytes()[printed_from:].decode("latin-1"))
        failed = custom_failed_steps(results)
        if failed:
            raise SysgenError(f"custom: {len(failed)} step(s) not executed or not 0000, first {failed[0]}")
        print(f"custom: {len(results)} steps checked (condcode)")
        (work / CUSTOM_MARKER).write_text("PUB000 / PUB001 initialized by MVS00; attach them at every IPL\n")
        shutdown_system(herc)
    except SysgenError:
        print("custom: Hercules log tail:\n" + "\n".join(ln.rstrip() for ln in herc.lines[-15:]), file=sys.stderr)
        raise
    finally:
        herc.quit()


SERVE_READY, SERVE_PID = "box.ready", "box.pid"


def serve(work, image, name, ready_timeout=900):
    """The resident box behind `mvs38j.sh start`: IPL the generated system (warm after the first IPL), write `box.ready`,
    keep Hercules running (the card reader socket on 127.0.0.1:3505) until SIGTERM/SIGINT, then shut the system down
    cleanly. The host process stays because Hercules' console is its stdin pipe."""
    import signal

    work = Path(work)
    for f in (SERVE_READY, SERVE_PID):
        (work / f).unlink(missing_ok=True)
    if not (work / "dasd/mvsres.3350").is_file() or not (work / "dasd/syscpk.3350").is_file():
        raise SysgenError(f"{work}/dasd lacks the generated system: run `mvs38j.sh sysgen ipl` first")
    conf = ipl_conf(work)
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    herc = Hercules(work, conf, image, name, publish=(3505,)).start()
    try:
        marker = work / IPL_DONE_MARKER
        ipl_system(herc, timeout=ready_timeout, warm=marker.exists())
        marker.write_text("first IPL done; later IPLs are warm (JES2 reply noreq)\n")
        (work / SERVE_PID).write_text(f"{os.getpid()}\n")
        (work / SERVE_READY).write_text("JES2 ready\n")
        print("serve: JES2 ready; card reader on 127.0.0.1:3505", flush=True)
        while not stop.is_set() and herc.proc.poll() is None:
            stop.wait(1.0)
        if herc.proc.poll() is None:
            shutdown_system(herc)
    except SysgenError:
        print("serve: Hercules log tail:\n" + "\n".join(ln.rstrip() for ln in herc.lines[-15:]), file=sys.stderr)
        raise
    finally:
        herc.quit()
        for f in (SERVE_READY, SERVE_PID):
            (work / f).unlink(missing_ok=True)


ACCT_RE = re.compile(r"IEFACTRT\s+(\S+)\s+/[^/]*/[^/]*/[^/]*/(\d{5})/(\S+)")


def live_steps(lines, job):
    """(step, condition code) of every `IEFACTRT` step-accounting line the console printed for `job`: the live log carries
    these, not the IEF142I the printer listing has."""
    out = set()
    for ln in lines:
        m = ACCT_RE.search(ln)
        if m and m.group(3) == job:
            out.add((m.group(1), int(m.group(2))))
    return out


def probe_deck(herc, work, conf, deck, timeout):
    """Submit `deck` through the socket reader and compare the runner's reading of the printer file with the live console."""
    import runner

    first = Path(deck).read_text().splitlines()[0]
    m = re.match(r"//(\S+)\s+JOB\b", first)
    if not m:
        raise SysgenError(f"{deck}: the first card must be '//NAME JOB ...'")
    job, printed = m.group(1), printer_file(work, conf)
    before = printed.stat().st_size if printed.exists() else 0
    since = herc.mark()
    runner.submit(deck)
    try:
        herc.wait(rf"\$HASP395\s+{re.escape(job)}\s+ENDED", timeout, since)
    except SysgenError:
        herc.send("devlist 00c")  # what the reader and JES2 say, for the failure tail
        herc.send("/$d rdr1")
        time.sleep(5)
        raise
    if not runner.wait_for_job(printed, job, 60, before):
        raise SysgenError(f"probe: {job} ended on the console but never in {printed}")
    text = printed.read_bytes()[before:].decode("utf-8", "backslashreplace")
    parsed = runner.parse_log(text, job)
    mine = {(s["step"], s["cond_code"]) for j in parsed["jobs"] for s in j["steps"]}
    seen = live_steps(herc.lines[since:], job)
    print(json.dumps({"printer": parsed, "live_steps": sorted(map(list, seen))}, indent=1, default=str))
    if mine != seen:
        raise SysgenError(
            f"probe: runner read steps {sorted(mine)} from the printer, the live log shows {sorted(seen)}"
        )


def hetget(work, image, name, het, out, fileno):
    """Extract file `fileno` of a tape image as ASCII text into `work/out` with the image's `hetget -a`."""
    cmd = ["docker", "run", "--rm", "--name", f"{name}-hetget", "--user", f"{os.getuid()}:{os.getgid()}"]
    cmd += ["-v", f"{work}:/mvs", "-w", "/mvs", "--entrypoint", "hetget", image, "-a", het, out, str(fileno)]
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603
    if r.returncode != 0 or not (Path(work) / out).stat().st_size:
        raise SysgenError(f"hetget {het} -> {out} failed (rc {r.returncode}): {r.stdout.strip()[-300:]}")
    print(f"stage1: {out} extracted from {het} ({(Path(work) / out).stat().st_size} bytes)")


def smp_failed_steps(results, expected):
    """Steps not executed, or over CC 4 unless `expected` ({(job, step): (cc, reason)}) lists them; a listed step must match."""
    out = []
    for r in results:
        # a PROC step logs as `JOB STEP PROCSTEP` (SMPJOB00 `SMP DLBUCL`): a listed key may name either (live 2026-11-14)
        want = expected.get((r["job"], r["step"])) or expected.get((r["job"], r.get("procstep")))
        if not r["executed"]:
            out.append(r)
        elif want is not None:
            if r["cond_code"] != want[0]:
                out.append(r)
        elif (r["cond_code"] or 0) > 4:
            out.append(r)
    return out


def step_results(printer_text, job="ALL"):
    """Step results from a Hercules printer file: [{job, step, procstep, executed, cond_code}], in log order.

    Read by `runner.parse_log` (the one parser of the printer listing); `step_log` keeps the order across jobs."""
    import runner

    return [
        {k: r[k] for k in ("job", "step", "procstep", "executed", "cond_code")}
        for r in runner.parse_log(printer_text)["step_log"]
        if job.upper() == "ALL" or r["job"] == job.upper()
    ]


def check_expected(results, expected):
    """Names of steps whose code differs from `expected` ({step: code}); a missing or unexecuted step counts."""
    got = {r["step"]: r["cond_code"] for r in results}
    return [s for s, cc in expected.items() if got.get(s) != cc]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    st = sub.add_parser("starter")
    st.add_argument("--work", default=os.environ.get("MVS38J_WORK", DEFAULT_WORK))
    st.add_argument("--image", default=os.environ.get("MVS38J_IMAGE", "gitgalaxy-mvs38j-hyperion"))
    st.add_argument("--name", default=os.environ.get("MVS38J_NAME", "gg-mvs38j") + "-sysgen")
    for stage in ("smp1", "smp2", "stage1", "stage2", "stage3"):
        sp = sub.add_parser(stage)
        sp.add_argument("--work", default=os.environ.get("MVS38J_WORK", DEFAULT_WORK))
        sp.add_argument("--image", default=os.environ.get("MVS38J_IMAGE", "gitgalaxy-mvs38j-hyperion"))
        sp.add_argument("--name", default=os.environ.get("MVS38J_NAME", "gg-mvs38j") + "-sysgen")
        sp.add_argument("--port", type=int, default=3270)
        sp.add_argument("--tape", action="append", default=[], metavar="VOLSER=FILE")
    ip = sub.add_parser("ipl")
    ip.add_argument("--work", default=os.environ.get("MVS38J_WORK", DEFAULT_WORK))
    ip.add_argument("--image", default=os.environ.get("MVS38J_IMAGE", "gitgalaxy-mvs38j-hyperion"))
    ip.add_argument("--name", default=os.environ.get("MVS38J_NAME", "gg-mvs38j") + "-sysgen")
    ip.add_argument("--probe", metavar="DECK")
    cu = sub.add_parser("custom")
    cu.add_argument("--work", default=os.environ.get("MVS38J_WORK", DEFAULT_WORK))
    cu.add_argument("--image", default=os.environ.get("MVS38J_IMAGE", "gitgalaxy-mvs38j-hyperion"))
    cu.add_argument("--name", default=os.environ.get("MVS38J_NAME", "gg-mvs38j") + "-sysgen")
    sv = sub.add_parser("serve")
    sv.add_argument("--work", default=os.environ.get("MVS38J_WORK", DEFAULT_WORK))
    sv.add_argument("--image", default=os.environ.get("MVS38J_IMAGE", "gitgalaxy-mvs38j-hyperion"))
    sv.add_argument("--name", default=os.environ.get("MVS38J_NAME", "gg-mvs38j"))
    cc = sub.add_parser("condcode")
    cc.add_argument("printer_file")
    cc.add_argument("job")
    cc.add_argument("--expect", nargs="*", default=[], metavar="STEP=CC")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "starter":
            starter(args.work, args.image, args.name)
            return 0
        if args.cmd == "serve":
            serve(args.work, args.image, args.name)
            return 0
        if args.cmd == "custom":
            custom(args.work, args.image, args.name)
            return 0
        if args.cmd == "ipl":
            ipl(args.work, args.image, args.name, args.probe)
            return 0
        if args.cmd in ("smp1", "smp2", "stage1", "stage2", "stage3"):
            tapes = dict(t.split("=", 1) for t in args.tape)
            if args.cmd in ("stage1", "stage2", "stage3"):
                {"stage1": stage1, "stage2": stage2, "stage3": stage3}[args.cmd](
                    args.work, args.image, args.name, tapes, args.port
                )
                return 0
            smp_stage(args.work, args.image, args.name, args.cmd, tapes, args.port)
            return 0
        results = step_results(Path(args.printer_file).read_text(errors="backslashreplace"), args.job)
        for r in results:
            print(
                r["job"],
                r["step"],
                r["procstep"] or "",
                "NOT EXECUTED" if not r["executed"] else f"{r['cond_code']:04d}",
            )
        bad = check_expected(results, {k: int(v) for k, v in (e.split("=") for e in args.expect)})
        if bad:
            print("unexpected:", " ".join(bad), file=sys.stderr)
            return 1
        return 0
    except SysgenError as e:
        print(f"sysgen: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
