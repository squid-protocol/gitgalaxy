"""cics-crucible#97: the java-ported harness must tell CicsTask which TDQUEUEs the CSD defines.

`CicsTask.withTdQueues(null)` means "every queue is defined" (cics_task_tdqueues.py: `tdKind` returns 0 only when
the set is non-null and lacks the queue). `java_plan` never put the CSD's queues in plan.json, so the Java task
answered NORMAL for a queue the case had deliberately left undefined, where the oracle says QIDERR -- which is
why hc-tdqueue-enable's `inquire` and `undefined` scenarios failed while `toggle` and `badcvda` passed.

The stub never had the bug: it writes tdqueues.cfg. These tests pin the two harnesses to ONE rule, so a case
cannot be defined for one side and undefined for the other.
"""

import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
sys.path.insert(0, str(TESTS))
import cics_crucible as runner  # noqa: E402


def case_with(csd, events=()):
    c = type("C", (), {})()
    c.csd = csd
    c.expected = {"s": {"tasks": [{"events": list(events)}]}}
    return c


def test_the_csd_s_queues_reach_the_plan_with_their_types():
    td = runner.java_tdqueues(case_with({"tdqueues": {"HCQ1": "INTRA", "AAAA": ""}}))
    assert td == {"AAAA": "", "HCQ1": "INTRA"}  # sorted, and a stated-none TYPE is kept as ""


def test_a_case_that_defines_no_queue_but_expects_QIDERR_gets_an_EMPTY_plan_entry():
    """Empty is a real answer -- no queue is defined, so every queue is undefined -- and is not None."""
    td = runner.java_tdqueues(case_with({}, [{"event": "WRITEQ-TD", "resp": "QIDERR"}]))
    assert td == {}


def test_a_case_with_no_queues_and_no_QIDERR_gets_NO_plan_entry():
    """Absent must stay absent: CicsTask then takes every queue as defined, which is what cases without any
    TDQUEUE facts have always relied on."""
    assert runner.java_tdqueues(case_with({}, [{"event": "WRITEQ-TD", "resp": "NORMAL"}])) is None
    assert runner.java_tdqueues(case_with({})) is None


def test_the_plan_rule_is_the_STUB_s_rule(tmp_path):
    """Both harnesses ask the same question, so neither can drift. The stub writes tdqueues.cfg on exactly the
    condition that gives the plan a non-None answer."""
    for csd, events in (({"tdqueues": {"Q": "INTRA"}}, ()),
                        ({}, [{"event": "READQ-TD", "resp": "QIDERR"}]),
                        ({}, [{"event": "READQ-TD", "resp": "NORMAL"}]),
                        ({}, ())):
        case = case_with(csd, events)
        stub_writes = bool(csd.get("tdqueues")) or runner._expects_undefined_td_queue(case)
        assert (runner.java_tdqueues(case) is not None) == stub_writes


def test_the_generated_java_tells_CicsTask_about_them():
    """The plan entry is useless unless the generated test passes it on."""
    src = Path(runner.__file__).read_text(encoding="utf-8")
    assert 'if (plan.hasNonNull("tdqueues"))' in src
    assert "t.withTdQueues(qs);" in src
    assert "t.withTdQueueTypes(tdTypes);" in src
