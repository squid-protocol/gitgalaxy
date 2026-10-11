"""box_status.decide (box-capacity skill): the verdict an orchestrator acts on before launching an agent or heavy run."""

import sys
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
