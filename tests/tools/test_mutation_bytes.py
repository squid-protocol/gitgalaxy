"""#4965: mutation_bytes.py picks the byte overload's assign and accessor statements, and only those."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutation_bytes as mb  # noqa: E402

FACADE = """package p.service;
public class XService {
    private byte[] lastAnswerBytes;
    public String handleTransaction(String transid, String request, byte[] area) {
        CicsTask task = region.transaction(transid, request, area);
        region.run(task, "X", this::runTask);
        lastAnswerBytes = task.returnedBytes();
        return task.returned(String.class);
    }
    public byte[] lastAnswerBytes() {
        return lastAnswerBytes == null ? null : java.util.Arrays.copyOf(lastAnswerBytes, lastAnswerBytes.length);
    }
    public void runTask(CicsTask task) {
        int n = 1;
        if (n > 0) {
            n = n + 1;
        }
    }
}
"""


def test_the_byte_overloads_assign_and_accessor_are_the_mutants_it_proves(tmp_path):
    (tmp_path / "service").mkdir()
    (tmp_path / "service" / "XService.java").write_text(FACADE)
    got = mb.bytes_mutants(tmp_path)
    assert {m.op for m in got} == {"DEL", "ROR"}
    assert sorted(m.line for m in got) == [7, 11]  # the assignment and the accessor's test, nothing in runTask
