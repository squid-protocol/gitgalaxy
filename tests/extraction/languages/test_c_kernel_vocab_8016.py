"""#8016: kernel / BSD / Windows C vocabulary in the C sync_locks, io, alloc, cleanup rules."""

import time

import pytest

from gitgalaxy.standards.language_standards import LANGUAGE_DEFINITIONS

R = LANGUAGE_DEFINITIONS["c"]["rules"]

_POS = [
    ("sync_locks", "spin_lock_irqsave(&l, flags);"),
    ("sync_locks", "spin_unlock_irqrestore(&l, flags);"),
    ("sync_locks", "raw_spin_lock(&l);"),
    ("sync_locks", "mutex_lock(&m);"),
    ("sync_locks", "mutex_unlock(&m);"),
    ("sync_locks", "mutex_lock_interruptible(&m);"),
    ("sync_locks", "rcu_read_lock();"),
    ("sync_locks", "down_read(&sem);"),
    ("sync_locks", "up_write(&sem);"),
    ("sync_locks", "sx_xlock(&sx);"),
    ("sync_locks", "rw_rlock(&rw);"),
    ("sync_locks", "EnterCriticalSection(&cs);"),
    ("sync_locks", "AcquireSRWLockExclusive(&l);"),
    ("sync_locks", "InterlockedIncrement(&n);"),
    ("concurrency", "InterlockedCompareExchange(&n, 1, 0);"),
    ("io", "data = readl_relaxed(base);"),
    ("io", "writel_relaxed(data, base);"),
    ("io", "v = readl(base + 4);"),
    ("io", "writeb(1, p);"),
    ("io", "ioread32(p);"),
    ("io", "iowrite16be(v, p);"),
    ("io", "x = inb(0x60);"),
    ("io", "outb(1, 0x60);"),
    ("io", "copy_to_user(u, k, n);"),
    ("io", "copy_from_user(k, u, n);"),
    ("io", "bus_space_read_4(t, h, 0);"),
    ("memory_alloc", "p = kmalloc(8, GFP_KERNEL);"),
    ("memory_alloc", "p = kzalloc(8, GFP_KERNEL);"),
    ("memory_alloc", "p = devm_kzalloc(dev, 8, GFP_KERNEL);"),
    ("memory_alloc", "vfree(p);"),
    ("memory_alloc", "kfree(p);"),
    ("cleanup", "kfree(p);"),
    ("cleanup", "vfree(p);"),
    ("cleanup", "kmem_cache_free(c, p);"),
    ("cleanup", "iounmap(base);"),
]

_NEG = [
    ("sync_locks", "spin_lockdep_ok = 1;"),
    ("sync_locks", "mutex_lock_t m;"),
    ("sync_locks", "int up = 1, down = 2;"),
    ("sync_locks", "x = cs.EnterCriticalSection;"),
    ("io", "int readl = 1;"),
    ("io", "x.writel = 2;"),
    ("io", "int in = 0, out = 1;"),
    ("io", "readlink(p, b, n);"),
    ("memory_alloc", "kmalloc_failures++;"),
    ("memory_alloc", "int kfree_count;"),
    ("cleanup", "int kfree_count;"),
]


@pytest.mark.parametrize("sig,code", _POS)
def test_kernel_vocab_matches(sig, code):
    assert R[sig].search(code), (sig, code)


@pytest.mark.parametrize("sig,code", _NEG)
def test_kernel_vocab_boundaries(sig, code):
    assert not R[sig].search(code), (sig, code)


def test_string_literal_names_are_not_calls():
    for sig in ("sync_locks", "io", "memory_alloc"):
        assert not R[sig].search('msg = "kmalloc failed, readl bad, mutex_lock stuck";')


def test_existing_vocabulary_still_matches():
    assert R["sync_locks"].search("pthread_mutex_lock(&m);")
    assert R["memory_alloc"].search("free(p);")
    assert R["io"].search('fopen("f", "r");')


def test_kernel_vocab_redos_immune():
    for sig in ("sync_locks", "io", "memory_alloc", "cleanup"):
        t = time.perf_counter()
        R[sig].search("spin_lock_" * 5000 + "readl" * 5000)
        assert time.perf_counter() - t < 1.0


def test_apmu_enable_shape_reads_lock_and_io():
    body = "spin_lock_irqsave(&l, flags);\nval = readl(base);\nwritel(val | 1, base);\nspin_unlock_irqrestore(&l, flags);\n"
    assert len(R["sync_locks"].findall(body)) == 2
    assert len(R["io"].findall(body)) == 2
