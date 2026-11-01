"""#5274: the det CICS translator's command families. `Cics._command` is a loop over COMMAND_FAMILIES, so a slice adds a
command to its family's `dispatch` and leaves det/cics.py alone; these pin that shape and the order the old chain had."""

from __future__ import annotations

import inspect

import pytest

from gitgalaxy.tools.cobol_to_java.det import cics as C
from gitgalaxy.tools.cobol_to_java.det import cics_counters as CO
from gitgalaxy.tools.cobol_to_java.det import cics_queues as Q
from gitgalaxy.tools.cobol_to_java.det import cics_system as S


class _NoGen:
    g = None


def test_command_is_the_registry_loop_and_holds_no_command_body():
    src = inspect.getsource(C.Cics._command)
    assert "task." not in src
    assert len(src.splitlines()) < 40


def test_every_family_method_is_inherited_by_cics_under_its_own_name():
    names = [d.__name__ for d in C.COMMAND_FAMILIES]
    assert len(set(names)) == len(names)
    for dispatch in C.COMMAND_FAMILIES:
        assert getattr(C.Cics, dispatch.__name__) is dispatch


def test_each_family_answers_none_for_a_command_of_another_family():
    for dispatch in C.COMMAND_FAMILIES:
        assert dispatch(_NoGen(), ["NOSUCHVERB"], "NOSUCHVERB", "NOSUCHVERB", {}, "") is None, dispatch


def test_counters_come_before_every_family_their_refusal_covers():
    """The counter family refuses any other command naming a counter, so only what ran before it in the old chain may
    run before it now."""
    order = list(C.COMMAND_FAMILIES)
    at = order.index(CO.CounterCommands.dispatch_counters)
    assert order[:at] == [C.ContainerCommands.dispatch_containers, C.TaskControlCommands.dispatch_taskcontrol]


def test_queues_come_before_the_system_services():
    """INQUIRE TDQUEUE ran before INQUIRE PROGRAM's `verb and option` test in the old chain."""
    order = list(C.COMMAND_FAMILIES)
    assert order.index(Q.QueueCommands.dispatch_queues) < order.index(S.SystemCommands.dispatch_system)


@pytest.mark.parametrize(
    "name", ("send_map", "receive", "web", "document", "storage", "address", "readq_td", "ts_queue")
)
def test_a_moved_method_is_reached_through_cics_and_no_longer_lives_there(name):
    assert callable(getattr(C.Cics, name)) and name not in vars(C.Cics)


def test_the_literal_helper_is_still_reachable_through_cics():
    assert C._literal("'ABC'") == "ABC"
