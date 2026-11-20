"""#8599: every generated equivalence test (batch, CICS, CALL) starts its Spring context with the shared properties:
JPA repositories built on first use and no web layer take a warm context start from ~1.05 s to ~0.40 s, and a mutant
proof starts one per run."""

from __future__ import annotations

import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import equivalence_java as ej  # noqa: E402

GENERATORS = ("equivalence_java.py", "equivalence_cics.py", "equivalence_call.py")


def test_the_shared_properties():
    props = re.findall(r'"([^"]+)"', ej.SPRING_TEST_PROPERTIES)
    assert props == ["spring.jpa.show-sql=false", "spring.data.jpa.repositories.bootstrap-mode=lazy",
                     "spring.main.web-application-type=none"]  # fmt: skip


def test_every_generated_spring_test_uses_them():
    seen = 0
    for name in GENERATORS:
        for line in (TOOLS / name).read_text(encoding="utf-8").splitlines():
            if "@SpringBootTest(" not in line:
                continue
            seen += 1
            assert re.search(r"@SpringBootTest\(properties = \{\{\{(ej\.)?SPRING_TEST_PROPERTIES\}", line), (name, line)
    assert seen == 4  # equivalence_java (batch), equivalence_cics, equivalence_call (two)
