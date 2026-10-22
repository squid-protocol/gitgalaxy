"""box_status.decide (box-capacity skill): the verdict an orchestrator acts on before launching an agent or heavy run."""

import os
import sys
from collections import namedtuple
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "box"))
import box_status as bs


def snap(**kw):
    s = {"cores": 12, "load1": 2.0, "cpu_psi": 0.0, "mem_psi": 0.0, "mem_avail_gb": 20.0, "mem_total_gb": 30.0,
         "swap_used_gb": 0.0, "slots": 3, "slots_held": 0}  # fmt: skip
    s.update(kw)
    return s


def test_an_idle_box_is_green_with_every_slot_free():
    d = bs.decide(snap())
    assert d["verdict"] == "GREEN" and d["free_slots"] == 3


def test_load_past_the_cores_is_red_and_frees_no_slot():
    d = bs.decide(snap(load1=13.5))
    assert d["verdict"] == "RED" and d["free_slots"] == 0 and "12 cores" in d["reasons"][0]


def test_load_at_seventy_percent_or_cpu_pressure_is_yellow():
    assert bs.decide(snap(load1=9.0))["verdict"] == "YELLOW"
    assert bs.decide(snap(cpu_psi=20.0))["verdict"] == "YELLOW"
    assert bs.decide(snap(cpu_psi=45.0))["verdict"] == "RED"


def test_swap_in_use_alone_is_not_judged_paging_is():
    # 2026-10-11: 4 GB of swap left over from an earlier spike, 22 GB available, no memory pressure -> headroom
    assert bs.decide(snap(swap_used_gb=4.0))["verdict"] == "GREEN"
    assert bs.decide(snap(swap_used_gb=4.0, mem_psi=8.0))["verdict"] == "YELLOW"
    assert bs.decide(snap(swap_used_gb=6.5, mem_psi=25.0))["verdict"] == "RED"


def test_low_memory_and_held_slots():
    assert bs.decide(snap(mem_avail_gb=2.0))["verdict"] == "RED"
    assert bs.decide(snap(mem_avail_gb=5.0))["verdict"] == "YELLOW"
    full = bs.decide(snap(slots_held=3))
    assert full["verdict"] == "YELLOW" and full["free_slots"] == 0


def test_no_psi_kernel_still_decides():
    assert bs.decide(snap(cpu_psi=None, mem_psi=None))["verdict"] == "GREEN"


# --- #4930: disk-blocked load, I/O pressure, strays -------------------------------------------------------------------

def test_load_from_disk_wait_is_yellow_and_names_the_culprit():
    # 2026-10-11: load 9.3 on 12 cores, CPU pressure 0, I/O pressure 53% -- a stray `find /` held the box YELLOW 40 min
    d = bs.decide(snap(load1=9.3, cpu_psi=0.0, io_psi=53.0, blocked=9, culprit="bfs / -name box_status.py (pid 830173)"))
    assert d["verdict"] == "YELLOW"
    assert "waiting on disk" in d["reasons"][0] and "pid 830173" in d["reasons"][0]
    assert any(r.startswith("disk I/O pressure 53%") for r in d["reasons"])


def test_disk_pressure_alone_is_yellow():
    d = bs.decide(snap(io_psi=60.0, culprit="wt:det-4468 pid 42 80.0 MB/s"))
    assert d["verdict"] == "YELLOW" and "pid 42" in d["reasons"][0]
    assert bs.decide(snap(io_psi=30.0))["verdict"] == "GREEN"


def test_load_without_cpu_or_io_pressure_is_reported_not_judged():
    # tasks stuck in D on a dead mount: load climbs, nothing is busy
    d = bs.decide(snap(load1=11.0, cpu_psi=0.5, io_psi=2.0, blocked=11))
    assert d["verdict"] == "GREEN" and d["free_slots"] == 3
    assert "not judged" in d["reasons"][1] and "11 tasks stuck in D state" in d["reasons"][1]


def test_load_is_still_judged_when_the_kernel_has_no_psi():
    assert bs.decide(snap(load1=9.0, cpu_psi=None, io_psi=None))["verdict"] == "YELLOW"
    assert bs.decide(snap(load1=9.0, cpu_psi=0.0))["verdict"] == "YELLOW"  # I/O pressure unknown: judged
    assert bs.decide(snap(load1=13.0, cpu_psi=None, io_psi=None))["verdict"] == "RED"


def test_strays_are_named_without_changing_the_verdict():
    d = bs.decide(snap(strays=[{"pid": 830173, "age_min": 39, "cmd": "bfs -S dfs / -name box_status.py"}]))
    assert d["verdict"] == "GREEN" and any("probable stray" in r and "830173" in r for r in d["reasons"])


def test_is_stray_scan_covers_the_whole_filesystem_scanners_only():
    assert bs.is_stray_scan(["bfs", "-S", "dfs", "-regextype", "findutils-default", "/", "-name", "x"], 39)
    assert bs.is_stray_scan(["/usr/bin/find", "/srv/storage_16tb", "-name", "*.py"], 20)
    assert bs.is_stray_scan(["du", "-sh", "/srv/"], 16)
    assert bs.is_stray_scan(["rg", "-l", "TODO", str(Path.home())], 30)
    assert not bs.is_stray_scan(["find", "/", "-name", "x"], 5)  # young: maybe on purpose
    assert not bs.is_stray_scan(["find", "/srv/storage_16tb/projects/gitgalaxy-worktrees/x", "-name", "*.py"], 60)
    assert not bs.is_stray_scan(["find", "/tmp", "/var/tmp", "-type", "f"], 400)  # chkrootkit's daily walk: not a root scan
    assert not bs.is_stray_scan(["python", "/", "x"], 60)


# --- free disk space and inodes ---------------------------------------------------------------------------------------

def disk(mount="/", size=1900.0, free=500.0, inodes=60.0):
    return {"mount": mount, "size_gb": size, "free_gb": free, "inodes_free_pct": inodes}


def test_a_filling_disk_is_yellow_then_red():
    # 2026-10-17: / at 89% (205 GB free of 1.9 TB) after one job left 155 GB of scratch; nothing judged it
    assert bs.decide(snap(disks=[disk(free=205.0)]))["verdict"] == "GREEN"
    d = bs.decide(snap(disks=[disk(free=80.0)]))
    assert d["verdict"] == "YELLOW" and any(r.startswith("disk filling, /: 80 GB free") for r in d["reasons"])
    d = bs.decide(snap(disks=[disk(free=20.0)]))
    assert d["verdict"] == "RED" and d["free_slots"] == 0 and any("disk almost full" in r for r in d["reasons"])


def test_a_big_disk_is_judged_by_gigabytes_and_a_small_one_by_percent():
    assert bs.decide(snap(disks=[disk("/srv", size=16000.0, free=1200.0)]))["verdict"] == "GREEN"  # 7.5% but 1.2 TB
    assert bs.decide(snap(disks=[disk("/small", size=200.0, free=15.0)]))["verdict"] == "YELLOW"  # 7.5% of 200 GB
    assert bs.decide(snap(disks=[disk("/small", size=200.0, free=8.0)]))["verdict"] == "RED"


def test_running_out_of_inodes_is_judged():
    assert bs.decide(snap(disks=[disk(inodes=8.0)]))["verdict"] == "YELLOW"
    assert bs.decide(snap(disks=[disk(inodes=3.0)]))["verdict"] == "RED"
    assert bs.decide(snap(disks=[disk(inodes=None)]))["verdict"] == "GREEN"


def test_disks_reads_one_row_per_device():
    rows = bs._disks()
    assert rows and len({r["mount"] for r in rows}) == len(rows)
    assert all(r["free_gb"] <= r["size_gb"] for r in rows)


_Usage = namedtuple("_Usage", "total used free")


def test_disks_without_statvfs_falls_back_to_disk_usage(monkeypatch):
    # Windows has no os.statvfs; the AttributeError used to escape and fail the Windows legs of the full-suite gate (#5352)
    monkeypatch.delattr(os, "statvfs", raising=False)
    # shutil.disk_usage calls os.statvfs on POSIX, so stand in for the Windows implementation too
    monkeypatch.setattr(bs.shutil, "disk_usage", lambda _p: _Usage(1000, 400, 600))
    rows = bs._disks()
    assert rows and all(r["inodes_free_pct"] is None and r["free_gb"] <= r["size_gb"] for r in rows)


def test_disk_paths_split_on_the_platform_separator(monkeypatch, tmp_path):
    monkeypatch.setenv("GG_DISK_PATHS", os.pathsep.join([str(tmp_path), "/nonexistent-gg-path"]))
    seen = []
    real = bs._statvfs
    monkeypatch.setattr(bs, "_statvfs", lambda p: (seen.append(p), real(p))[1])
    bs._disks()
    assert str(tmp_path) in seen and "/nonexistent-gg-path" in seen


def test_mount_does_not_use_path_is_mount(monkeypatch, tmp_path):
    # Path.is_mount raises NotImplementedError on Windows before Python 3.12 (#5367)
    def boom(_self):
        raise NotImplementedError

    monkeypatch.setattr(bs.Path, "is_mount", boom)
    assert bs._mount(tmp_path).exists()
