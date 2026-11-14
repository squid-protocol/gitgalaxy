#!/usr/bin/env python3
"""Drive Jay Moseley's MVS 3.8J sysgen through Hercules' console (JCL oracle tier 2, #8414).

Internal use only until counsel answers Q16. Stdlib only; runs on the host and starts Hercules in the box image
(`docker run -i`), feeding it commands on stdin and reading its log (which carries the integrated 1052-C console) on
stdout. Stages are small functions over `Hercules`; each one checks the messages and PSW the guide documents and raises
`SysgenError` rather than carry on. Implemented: `starter` (the two stand-alone programs per volume) and `smp1` / `smp2` (starter-system
IPL over the telnet 3215 console, jobs through the card reader at 00C, tape mounts, condcode per job). Not yet: stage 1,
stage 2, user mods: see docs/jcl_oracle_mvs38j.md "Remaining slices".

    sysgen.py starter [--work DIR] [--image IMG] [--name NAME]
    sysgen.py smp1|smp2 [--work DIR] [--image IMG] [--name NAME] [--port N] [--tape VOLSER=FILE ...]
    sysgen.py condcode PRINTER_FILE JOB|ALL [--expect STEP=CC ...]
"""

import argparse
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # run as `python3 -I`: the script dir is not on the path
import console as telnet_console  # noqa: E402

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

    def __init__(self, work, conf, image, name, user=None, console_port=None):
        self.work, self.conf, self.image, self.name = Path(work), conf, image, name
        self.console_port = console_port  # publish the telnet 3215 console (loopback only) when set
        self.user = user or f"{os.getuid()}:{os.getgid()}"
        self.lines = []
        self._cv = threading.Condition()
        self.proc = None

    def start(self):
        cmd = ["docker", "run", "--rm", "-i", "--name", self.name, "--user", self.user, "-v", f"{self.work}:/mvs"]
        if self.console_port:
            cmd[3:3] = ["-p", f"127.0.0.1:{self.console_port}:3270"]
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
MOUNT_RE = re.compile(r"(?:^|\s)(\d+)\s+IEC501A\s+M\s+([0-9A-F]{3}),(\S+?)[,\s]")
SMP_CONSOLE_ERRORS = re.compile(r"\bIEA\d{3}E\b|IEC\d{3}E\b|\bABEND\b|\$HASP\d+\s+.*ERROR|HHC00828E")
SMP_IPL_UNIT, SMP_READER = "150", "12"


def printer_file(work, conf):
    """The host path of the first 1403 printer in a Hercules config (the JES2 job log lands there)."""
    for line in (Path(work) / conf).read_text(errors="backslashreplace").splitlines():
        m = re.match(r"\s*[0-9A-Fa-f]{3,4}\s+1403\s+(\S+)", line)
        if m:
            return Path(work) / m.group(1)
    raise SysgenError(f"no 1403 printer in {conf}")


def smp_jobs(work, stage):
    """The stage's job decks in order (jcl/smpjobNN.jcl). Which jobs belong to smp1 and which to smp2 is unconfirmed: every deck runs for either stage."""
    jobs = sorted(Path(work, "jcl").glob("smpjob*.jcl"))
    if not jobs:
        raise SysgenError(f"{work}/jcl/smpjob*.jcl missing: run mvs38j.sh stage first")
    return jobs


def answer_mounts(herc_cmd, con, since, tapes, seen):
    """Answer each new IEC501A mount request on the console: `devinit` the tape for its volser, reply with the unit."""
    for line in con.lines[since:]:
        m = MOUNT_RE.search(line)
        if not m or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        reply_id, unit, volser = m.groups()
        if volser not in tapes:
            raise SysgenError(f"mount request for volume {volser} on {unit}: pass --tape {volser}=FILE")
        herc_cmd(f"devinit {unit} {tapes[volser]}")
        con.send(f"r {reply_id},{unit}")


def smp_stage(work, image, name, stage, tapes, port=3270, job_timeout=1800):
    """IPL the starter system with `conf/<stage>.cnf`, run each smpjob deck and check its steps ran (condcode)."""
    conf = f"conf/{stage}.cnf"
    if not (Path(work) / conf).is_file():
        raise SysgenError(f"{work}/{conf} missing: run mvs38j.sh stage first")
    jobs = smp_jobs(work, stage)
    herc = Hercules(work, conf, image, name, console_port=port).start()
    con = telnet_console.Console(port=port).connect()
    try:
        herc.send(f"ipl {SMP_IPL_UNIT}")
        con.wait(r"IEA101A|SPECIFY SYSTEM PARAMETERS", 300)
        con.send("r 0,clpa")
        con.wait(r"\$HASP426|SPECIFY OPTIONS", 300)
        con.send("r 0,format,noreq")
        con.wait(r"\$HASP099|ALL AVAILABLE FUNCTIONS COMPLETE", 300)
        for job in jobs:
            since, seen = con.mark(), set()
            herc.send(f"devinit {SMP_READER} {job.relative_to(work)}")
            end = time.monotonic() + job_timeout
            while True:
                try:
                    con.wait(JOB_ENDED_RE.pattern, 5, since)
                    break
                except telnet_console.ConsoleError:
                    if time.monotonic() > end:
                        raise SysgenError(f"{job.name}: no $HASP395 ENDED within {job_timeout}s") from None
                    answer_mounts(herc.send, con, since, tapes, seen)
            bad = [ln for ln in con.lines[since:] if SMP_CONSOLE_ERRORS.search(ln)]
            if bad:
                raise SysgenError(f"{job.name}: {bad[0].strip()}")
            print(f"{stage}: {job.name} ended")
        results = step_results(printer_file(work, conf).read_text(errors="backslashreplace"))
        failed = [r for r in results if not r["executed"] or (r["cond_code"] or 0) > 4]
        if failed:
            raise SysgenError(f"{stage}: {len(failed)} step(s) not executed or over CC 4, first {failed[0]}")
        print(f"{stage}: {len(results)} steps checked (condcode)")
    finally:
        con.close()
        herc.quit()


# IEF142I: step executed with its completion code; IEF272I: step not executed (COND bypass / flushed).
# Layout of the part after the message id: JOB STEP [PROCSTEP] - STEP WAS (NOT) EXECUTED ... [COND CODE nnnn]
STEP_RE = re.compile(
    r"(IEF142I|IEF272I)\s+(\S+)\s+(\S+)\s+(?:(\S+)\s+)?-\s+STEP WAS (NOT )?EXECUTED(?:.*?COND CODE (\d{4}))?"
)


def step_results(printer_text, job="ALL"):
    """Step results from a Hercules printer file: [{job, step, procstep, executed, cond_code}], in log order."""
    out = []
    for line in printer_text.splitlines():
        m = STEP_RE.search(line)
        if not m or (job.upper() != "ALL" and m.group(2) != job.upper()):
            continue
        executed = m.group(5) is None
        out.append(
            {
                "job": m.group(2),
                "step": m.group(3),
                "procstep": m.group(4),
                "executed": executed,
                "cond_code": int(m.group(6)) if executed and m.group(6) else None,
            }
        )
    return out


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
    for stage in ("smp1", "smp2"):
        sp = sub.add_parser(stage)
        sp.add_argument("--work", default=os.environ.get("MVS38J_WORK", DEFAULT_WORK))
        sp.add_argument("--image", default=os.environ.get("MVS38J_IMAGE", "gitgalaxy-mvs38j-hyperion"))
        sp.add_argument("--name", default=os.environ.get("MVS38J_NAME", "gg-mvs38j") + "-sysgen")
        sp.add_argument("--port", type=int, default=3270)
        sp.add_argument("--tape", action="append", default=[], metavar="VOLSER=FILE")
    cc = sub.add_parser("condcode")
    cc.add_argument("printer_file")
    cc.add_argument("job")
    cc.add_argument("--expect", nargs="*", default=[], metavar="STEP=CC")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "starter":
            starter(args.work, args.image, args.name)
            return 0
        if args.cmd in ("smp1", "smp2"):
            tapes = dict(t.split("=", 1) for t in args.tape)
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
