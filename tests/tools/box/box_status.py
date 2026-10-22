#!/usr/bin/env python3
"""What the box can take right now (box-capacity skill): cores, load, CPU / memory pressure, swap, who holds the heavy and
golden locks, which worktree burns the CPU, and the containers up -- with one verdict an orchestrator acts on before it
launches an agent or a heavy run.

    python tests/tools/box/box_status.py            # the table
    python tests/tools/box/box_status.py --json     # the same, for a script or a night-shift tick
    python tests/tools/box/box_status.py --sample 3 # seconds of CPU sampling per process (default 1)

Verdict (decide(), pure):
  RED     launch nothing; ask the newest worker to pause at its next checkpoint if it stays RED
  YELLOW  light work only: a read-only scout, a narrow test; no proof, sweep, gate or Docker run
  GREEN   may launch; heavy work only into a FREE heavy-run.sh slot (`free_slots`)
Thresholds: load1 and CPU pressure (PSI "some" avg60) against the cores; disk I/O pressure; memory available; memory
pressure (paging now -- swap merely in use is not judged alone, it can be old pages from a spike long gone); free heavy
slots; free disk space and inodes on the disks the fleet writes to (/, the temp dir, the repo's disk). Linux counts tasks blocked on disk (D state) in the load average, so load with no CPU or I/O pressure behind it
(tasks stuck on a dead mount) is reported, not judged (#4930). Whatever holds the box is named: the busiest CPU and disk
users, the processes blocked on disk, and probable strays (a whole-filesystem scan running 15+ minutes).
Linux only (/proc); elsewhere it says so and exits 0 with verdict UNKNOWN.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

LOCK_DIR = Path(os.environ.get("GG_LOCK_DIR", "/tmp/gitgalaxy-scratch/locks"))  # noqa: S108 (heavy-run.sh's lock dir)
WORKTREE_MARK = "gitgalaxy-worktrees"  # $PRIMARY/../gitgalaxy-worktrees/<slug> (parallel-pr-agents)
# Free space: YELLOW below min(10% of the disk, 100 GB), RED below min(5%, 25 GB) -- a percentage alone would hold a 15 TB
# disk YELLOW with 1.4 TB free. Inodes: YELLOW below 10% free, RED below 5%. Extra paths: GG_DISK_PATHS (colon-separated).
DISK_YELLOW, DISK_RED = (0.10, 100.0), (0.05, 25.0)


def decide(s: dict[str, Any]) -> dict[str, Any]:
    """snapshot -> {verdict, reasons, free_slots}. s: cores, load1, cpu_psi / mem_psi (PSI "some" avg60, %; None when the
    kernel has no PSI), mem_avail_gb, mem_total_gb, swap_used_gb (shown, not judged alone), slots, slots_held."""
    cores = max(int(s["cores"]), 1)
    reasons: list[str] = []
    red = yellow = False
    load_ratio = s["load1"] / cores
    psi, io = s.get("cpu_psi"), s.get("io_psi")
    culprit = f": {s['culprit']}" if s.get("culprit") else ""
    # #4930: the load average counts tasks waiting on disk too. Leave it unjudged only when BOTH pressures are known and
    # quiet (tasks stuck in D on a dead mount); without either reading, judge it as before.
    backed = psi is None or io is None or psi >= 5 or io >= 20
    on_disk = psi is not None and psi < 5 and io is not None and io >= 20
    if load_ratio >= 0.7 and not backed:
        reasons.append(f"load1 {s['load1']:.1f} not judged: no CPU or I/O pressure behind it "
                       f"({s.get('blocked', 0)} tasks stuck in D state{culprit})")  # fmt: skip
    elif load_ratio >= 1.0:
        red = True
        reasons.append(f"load1 {s['load1']:.1f} >= {cores} cores" + (f", mostly tasks waiting on disk{culprit}" if on_disk else ""))
    elif load_ratio >= 0.7:
        yellow = True
        reasons.append(f"load1 {s['load1']:.1f} >= 70% of {cores} cores"
                       + (f", mostly tasks waiting on disk{culprit}" if on_disk else ""))  # fmt: skip
    if psi is not None:
        if psi >= 40:
            red = True
            reasons.append(f"CPU pressure {psi:.0f}% (tasks waiting for a core)")
        elif psi >= 15:
            yellow = True
            reasons.append(f"CPU pressure {psi:.0f}%")
    if io is not None and io >= 50:
        yellow = True
        reasons.append(f"disk I/O pressure {io:.0f}% (tasks stalled on disk{culprit})")
    avail, total = s["mem_avail_gb"], max(s["mem_total_gb"], 1e-9)
    if avail / total < 0.10:
        red = True
        reasons.append(f"memory available {avail:.1f} GB < 10%")
    elif avail / total < 0.20:
        yellow = True
        reasons.append(f"memory available {avail:.1f} GB < 20%")
    # paging NOW is memory pressure (PSI); swap merely in use can be old pages pushed out by a spike long gone
    mpsi = s.get("mem_psi")
    if mpsi is not None and mpsi >= 20:
        red = True
        reasons.append(f"memory pressure {mpsi:.0f}% (the box is paging; swap {s.get('swap_used_gb', 0):.1f} GB)")
    elif mpsi is not None and mpsi >= 5:
        yellow = True
        reasons.append(f"memory pressure {mpsi:.0f}% (swap {s.get('swap_used_gb', 0):.1f} GB)")
    for d in s.get("disks", []):
        free, size, inodes = d["free_gb"], max(d["size_gb"], 1e-9), d.get("inodes_free_pct")
        where = f"{d['mount']}: {free:.0f} GB free of {size:.0f} GB ({100 * free / size:.0f}%)"
        if free < min(DISK_RED[0] * size, DISK_RED[1]):
            red = True
            reasons.append(f"disk almost full, {where}")
        elif free < min(DISK_YELLOW[0] * size, DISK_YELLOW[1]):
            yellow = True
            reasons.append(f"disk filling, {where}")
        if inodes is not None and inodes < 5:
            red = True
            reasons.append(f"inodes almost gone on {d['mount']}: {inodes:.1f}% free")
        elif inodes is not None and inodes < 10:
            yellow = True
            reasons.append(f"inodes low on {d['mount']}: {inodes:.1f}% free")
    free_slots = max(s["slots"] - s["slots_held"], 0)
    if free_slots == 0:
        yellow = True
        reasons.append(f"all {s['slots']} heavy slots held")
    reasons += [f"probable stray (kill it if nobody owns it): pid {x['pid']}, {x['age_min']} min, {x['cmd'][:80]}"
                for x in s.get("strays", [])]  # fmt: skip
    verdict = "RED" if red else "YELLOW" if yellow else "GREEN"
    if not red and not yellow:
        reasons.insert(0, "headroom")
    return {"verdict": verdict, "reasons": reasons, "free_slots": 0 if red else free_slots}


# --- reading the box ------------------------------------------------------------------------------------------------


def _meminfo() -> dict[str, float]:
    out = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        k, v = line.split(":", 1)
        out[k] = int(v.split()[0]) / 1024 / 1024  # kB -> GB
    return out


def _psi(kind: str, which: str = "some") -> float | None:
    try:
        m = re.search(which + r" avg10=[\d.]+ avg60=([\d.]+)", Path(f"/proc/pressure/{kind}").read_text())
    except OSError:
        return None
    return float(m.group(1)) if m else None


def _lock_holders() -> dict[str, list[int]]:
    """lock file name -> PIDs holding a flock on it (/proc/locks maps inode -> pid)."""
    by_inode: dict[int, list[int]] = {}
    try:
        for line in Path("/proc/locks").read_text().splitlines():
            f = line.split()
            if len(f) >= 6 and f[1] in ("FLOCK", "POSIX") and f[2] != "->":
                ino = int(f[5].split(":")[2])
                by_inode.setdefault(ino, []).append(int(f[4]))
    except OSError:
        return {}
    out = {}
    files = sorted(LOCK_DIR.glob("*")) if LOCK_DIR.is_dir() else []
    for p in files:
        out[p.name] = [pid for pid in by_inode.get(p.stat().st_ino, []) if Path(f"/proc/{pid}").exists()]
    # the PID that took a flock can exit while its children hold the descriptor: find the holders by open file
    if any(by_inode.get(p.stat().st_ino) and not out[p.name] for p in files):
        targets = {str(p): p.name for p in files if by_inode.get(p.stat().st_ino) and not out[p.name]}
        for d in Path("/proc").iterdir():
            if not d.name.isdigit():
                continue
            try:
                links = {os.readlink(fd) for fd in (d / "fd").iterdir()}
            except OSError:
                continue  # another user's process, or gone: best effort
            for t, name in targets.items():
                if t in links and len(out[name]) < 3:
                    out[name].append(int(d.name))
    return out


def _io_bytes() -> dict[int, int]:
    """pid -> bytes read + written so far (/proc/<pid>/io; another user's processes are unreadable and skipped)."""
    out = {}
    for d in Path("/proc").iterdir():
        if d.name.isdigit():
            try:
                f = dict(line.split(": ", 1) for line in (d / "io").read_text().splitlines())
                out[int(d.name)] = int(f["read_bytes"]) + int(f["write_bytes"])
            except (OSError, KeyError, ValueError):
                continue  # best effort, as _cpu_ticks
    return out


def _blocked() -> dict[int, int]:
    """pid -> threads in uninterruptible (disk) wait, the tasks the load average counts without using a core."""
    out: dict[int, int] = {}
    for d in Path("/proc").iterdir():
        if not d.name.isdigit():
            continue
        try:
            tasks = list((d / "task").iterdir())
        except OSError:
            continue
        for t in tasks:
            try:
                if (t / "stat").read_text().rsplit(")", 1)[1].split()[0] == "D":
                    out[int(d.name)] = out.get(int(d.name), 0) + 1
            except (OSError, IndexError):
                continue
    return out


def _age_min(pid: int) -> int:
    try:
        start = int(Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19])
        uptime = float(Path("/proc/uptime").read_text().split()[0])
    except (OSError, IndexError, ValueError):
        return 0
    return int((uptime - start / os.sysconf("SC_CLK_TCK")) // 60)


def _argv(pid: int) -> list[str]:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return []
    return [a.decode(errors="backslashreplace") for a in raw.split(b"\0") if a]


SCANNERS = {"find", "bfs", "fd", "fdfind", "du", "rg", "grep", "locate", "updatedb"}
STRAY_MINUTES = 15


def _scan_roots() -> set[str]:
    home = str(Path.home())
    return {"/", "/home", "/srv", "/srv/storage_16tb", "/mnt", "/media", home, home + "/"}


def is_stray_scan(argv: list[str], age_min: int) -> bool:
    """A whole-filesystem scan (find / bfs / fd / du / rg / grep over / or a mount root) alive past STRAY_MINUTES: almost
    always a command an agent left behind when its tool call timed out (#4930: a `find /` held the box YELLOW 40 min)."""
    if age_min < STRAY_MINUTES or not argv or Path(argv[0]).name not in SCANNERS:
        return False
    roots = _scan_roots()
    return any(a.rstrip("/") + ("/" if a.rstrip("/") == "" else "") in roots or a in roots for a in argv[1:])


def _cpu_ticks() -> dict[int, int]:
    out = {}
    for d in Path("/proc").iterdir():
        if d.name.isdigit():
            try:
                f = (d / "stat").read_text().rsplit(")", 1)[1].split()
                out[int(d.name)] = int(f[11]) + int(f[12])  # utime + stime
            except (OSError, IndexError, ValueError):
                # best effort: a /proc entry can vanish or be unreadable while we iterate (the process exited)
                continue
    return out


def _group(pid: int) -> str:
    """The worktree slug a process works in, else its command name."""
    try:
        cwd = os.readlink(f"/proc/{pid}/cwd")
    except OSError:
        cwd = ""
    if WORKTREE_MARK in cwd:
        return "wt:" + cwd.split(WORKTREE_MARK + "/", 1)[1].split("/", 1)[0]
    try:
        return Path(f"/proc/{pid}/comm").read_text().strip()
    except OSError:
        return "?"


def _cmd(pid: int) -> str:
    try:
        return (
            Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="backslashreplace")
        )  # lossless (#3813): an odd byte shows as \xNN.strip()[:100]
    except OSError:
        return "?"


def _containers() -> list[str]:
    try:
        r = subprocess.run(["docker", "ps", "--format", "{{.Names}} {{.Image}} {{.Status}}"],  # noqa: S607
                           capture_output=True, text=True, timeout=10, check=False)  # fmt: skip
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [x for x in r.stdout.splitlines() if x.strip()]


def _mount(path: Path) -> Path:
    path = path.resolve()
    # os.path.ismount, not Path.is_mount: the latter raises NotImplementedError on Windows before Python 3.12 (#5367)
    while not os.path.ismount(path) and path != path.parent:
        path = path.parent
    return path


def _statvfs(path: str) -> tuple[Any, Any]:
    """(device key, usage) for a path; usage has f_blocks/f_frsize/f_bavail/f_favail/f_files. Windows has no os.statvfs
    (an AttributeError, not an OSError): fall back to shutil.disk_usage, keyed by drive, with no inode counts."""
    try:
        if hasattr(os, "statvfs"):
            return os.stat(path).st_dev, os.statvfs(path)
        du = shutil.disk_usage(path)
        st = SimpleNamespace(f_blocks=du.total, f_frsize=1, f_bavail=du.free, f_favail=0, f_files=0)
        return os.path.splitdrive(os.path.abspath(path))[0].lower(), st
    except OSError:
        return -1, None


def _disks() -> list[dict[str, Any]]:
    """Free space and inodes per filesystem the fleet writes to: /, the temp dir, this repo's disk (its worktrees sit
    beside it), and GG_DISK_PATHS. One row per device."""
    paths = ["/", tempfile.gettempdir(), str(Path(__file__).resolve().parent)]
    paths += [x for x in os.environ.get("GG_DISK_PATHS", "").split(os.pathsep) if x]
    seen, out = set(), []
    for p in paths:
        dev, st = _statvfs(p)
        if st is None or dev in seen:
            continue
        seen.add(dev)
        out.append({"mount": str(_mount(Path(p))), "size_gb": round(st.f_blocks * st.f_frsize / 1e9, 1),
                    "free_gb": round(st.f_bavail * st.f_frsize / 1e9, 1),
                    "inodes_free_pct": round(100 * st.f_favail / st.f_files, 1) if st.f_files else None})  # fmt: skip
    return out


def snapshot(sample: float = 1.0) -> dict[str, Any]:
    cores = os.cpu_count() or 1
    mem = _meminfo()
    t0, io0 = _cpu_ticks(), _io_bytes()
    time.sleep(sample)
    t1, io1 = _cpu_ticks(), _io_bytes()
    hz = os.sysconf("SC_CLK_TCK")
    groups: dict[str, float] = {}
    for pid, ticks in t1.items():
        d = ticks - t0.get(pid, 0)  # a process born during the sample counts all its ticks (a gauntlet scan lives ~1 s)
        if d > 0:
            g = _group(pid)
            groups[g] = groups.get(g, 0.0) + d / hz / sample  # cores busy
    locks = _lock_holders()
    heavy = {k: v for k, v in locks.items() if k.startswith("heavy.slot")}
    slots = int(os.environ.get("GG_HEAVY_SLOTS", max(cores // 4, 1)))
    disk = sorted(
        ({"pid": pid, "who": _group(pid), "mb_s": round((b - io0.get(pid, 0)) / 1e6 / sample, 1), "cmd": _cmd(pid)}
         for pid, b in io1.items() if b - io0.get(pid, 0) >= 1e6 * sample),
        key=lambda x: -x["mb_s"])[:6]  # fmt: skip
    blocked = _blocked()
    held = sorted(({"pid": p, "threads": n, "who": _group(p), "age_min": _age_min(p), "cmd": _cmd(p)}
                   for p, n in blocked.items() if _argv(p)), key=lambda x: -x["threads"])[:6]  # user processes; fmt: skip
    strays = [{"pid": p, "age_min": a, "cmd": _cmd(p)} for p in t1 if (a := _age_min(p)) >= STRAY_MINUTES
              and is_stray_scan(_argv(p), a)]  # fmt: skip
    culprit = (f"{strays[0]['cmd'][:60]} (pid {strays[0]['pid']}, {strays[0]['age_min']} min)" if strays
               else f"{disk[0]['who']} pid {disk[0]['pid']} {disk[0]['mb_s']} MB/s" if disk
               else f"{held[0]['who']} pid {held[0]['pid']}" if held else "")  # fmt: skip
    s = {
        "cores": cores,
        "load1": os.getloadavg()[0],
        "load5": os.getloadavg()[1],
        "load15": os.getloadavg()[2],
        "cpu_psi": _psi("cpu"),
        "mem_psi": _psi("memory"),
        "io_psi": _psi("io"),
        "io_full_psi": _psi("io", "full"),
        "blocked": sum(blocked.values()),
        "blocked_procs": held,
        "disk_top": disk,
        "strays": strays,
        "culprit": culprit,
        "mem_total_gb": mem["MemTotal"],
        "mem_avail_gb": mem["MemAvailable"],
        "swap_used_gb": mem["SwapTotal"] - mem["SwapFree"],
        "slots": slots,
        "slots_held": sum(1 for v in heavy.values() if v),
        "locks": {k: [{"pid": p, "where": _group(p), "cmd": _cmd(p)} for p in v] for k, v in locks.items()},
        "top": sorted(
            ({"who": k, "cores": round(v, 2)} for k, v in groups.items() if v >= 0.05), key=lambda x: -x["cores"]
        )[:12],
        "containers": _containers(),
        "disks": _disks(),
    }
    s.update(decide(s))
    return s


def render(s: dict[str, Any]) -> str:
    cpu = s["cpu_psi"] if s["cpu_psi"] is not None else "-"
    memp = s["mem_psi"] if s["mem_psi"] is not None else "-"
    out = [f"{s['verdict']}: " + "; ".join(s["reasons"]),
           f"cores {s['cores']}  load {s['load1']:.1f} / {s['load5']:.1f} / {s['load15']:.1f}  "
           + f"cpu-pressure {cpu}%  mem-pressure {memp}%",
           f"memory available {s['mem_avail_gb']:.1f} / {s['mem_total_gb']:.1f} GB  swap used {s['swap_used_gb']:.1f} GB",
           f"heavy slots {s['slots_held']}/{s['slots']} held  free for new heavy work: {s['free_slots']}"]  # fmt: skip
    out += [f"  {name}: pid {h['pid']} {h['where']}  {h['cmd']}" for name, hs in s["locks"].items() for h in hs]
    out.append("busiest (cores in use, by worktree or command):")
    out += [f"  {t['cores']:5.2f}  {t['who']}" for t in s["top"]] or ["  (idle)"]
    iop = s.get("io_psi")
    out.append(f"disk: io-pressure {iop if iop is not None else '-'}% (full {s.get('io_full_psi', '-')}%)  "
               f"tasks blocked on disk {s.get('blocked', 0)}")  # fmt: skip
    out += [f"  {d['mount']}: {d['free_gb']:.0f} GB free of {d['size_gb']:.0f} GB, inodes {d['inodes_free_pct']}% free"
            for d in s.get("disks", [])]  # fmt: skip
    out += [f"  {d['mb_s']:7.1f} MB/s  {d['who']} pid {d['pid']}  {d['cmd'][:80]}" for d in s.get("disk_top", [])]
    out += [f"  blocked: {b['threads']} thread(s)  {b['who']} pid {b['pid']} ({b['age_min']} min)  {b['cmd'][:80]}"
            for b in s.get("blocked_procs", [])]  # fmt: skip
    out += [f"  STRAY? pid {x['pid']} ({x['age_min']} min): {x['cmd'][:90]}  -> kill {x['pid']} if nobody owns it"
            for x in s.get("strays", [])]  # fmt: skip
    if s["containers"]:
        out.append("containers: " + " | ".join(s["containers"]))
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--sample", type=float, default=1.0)
    a = ap.parse_args()
    if not Path("/proc/meminfo").exists():
        print(json.dumps({"verdict": "UNKNOWN", "reasons": ["not Linux"]}) if a.json else "UNKNOWN: not Linux (/proc)")
        return 0
    s = snapshot(a.sample)
    print(json.dumps(s, indent=1) if a.json else render(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
