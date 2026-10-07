"""#4270 spec PRs 1-2: TRANSITIONAL equality tests -- gitgalaxy/standards/cics equals every hand copy it will replace.

docs/language_status/cics_command_spec.md section 7. Each test names the copy it reads and the spec PR that makes
that copy import the spec; that PR DELETES the test (the copy is gone, so there is nothing left to compare):

    PR 2  det/cics.py (DFHRESP, OPTIONS, _REFUSED_WHY / _ASSIGN_REFUSED_WHY / _SEND_TEXT_REFUSED_WHY, check_options,
          the option-group messages): DONE, det/cics.py imports them and their tests are gone
    PR 3  tests/tools/equivalence_cics.py (DFHRESP, CICS_RESP, _CONTAINER_OPTIONS, the refused tuples / sets): DONE,
          the harness imports them; tests/cobol_mainframe/test_equivalence_cics.py checks its refusals are the spec's
    PR 4  the Java switches (DetCics.condition / resp, CicsTask.respName / abcodeFor), ggcics.c's enums and
          condition_abcode
    PR 5  the stated facts (CicsTask.withX, $GGCICS_X, cics_crucible.REGION_*) and the runtime refusal texts
    PR 4/5 cics_crucible.CONDITION_ABCODE
    PR 8a the engine's verb tables (core/cics_resources.py, core/cics_tasks.py)

Where today's copies disagree with each other, the spec does not silently pick one: the difference is listed here
(the `*_DIFFERENCES` tables, each with its reason) and asserted to be exactly that, so it can neither grow nor be
fixed unnoticed."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import cics_crucible as runner  # noqa: E402

from gitgalaxy.core import cics_resources, cics_tasks  # noqa: E402
from gitgalaxy.standards.cics import resp as spec_resp  # noqa: E402
from gitgalaxy.standards.cics.commands import COMMANDS  # noqa: E402
from gitgalaxy.tools.cobol_to_java import cobol_to_java_transaction_forge as forge  # noqa: E402

DETCICS_JAVA = (ROOT / "gitgalaxy/tools/cobol_to_java/det/cobolrt/cics/DetCics.java").read_text(encoding="utf-8")
GGCICS_C = (ROOT / "tests/equivalence/cics/ggcics.c").read_text(encoding="utf-8")
JAVA = forge.CICS_TASK_JAVA + DETCICS_JAVA
DFHRESP = spec_resp.DFHRESP


def _switch(src: str, method: str, key: str, value: str) -> dict[str, str]:
    """The `case K -> V;` arms of a Java switch method, as text."""
    m = re.search(rf"\b{method}\([^)]*\)\s*\{{\s*return switch[^{{]*\{{(.*?)\n\s*\}};", src, re.S)
    assert m, f"no switch in {method}"
    return dict(re.findall(rf"case ({key}) -> ({value});", m.group(1)))


# ---- DFHRESP and abend codes ------------------------------------------------------------------------------------
def test_detcics_condition_and_resp_switches_are_spec_values():
    """Deleted in PR 4 (DetCics.condition / resp delegate to the generated CicsSpec.java). Partial tables by
    design (the conditions the runtime raises); every arm must be the spec's."""
    names = _switch(DETCICS_JAVA, "condition", r"\d+", r'"\w+"')
    assert {int(k): v.strip('"') for k, v in names.items()} == {int(k): spec_resp.RESP_NAME[int(k)] for k in names}
    assert 'default -> "RESP" + resp;' in DETCICS_JAVA  # the generated CicsSpec.condition's default too
    numbers = _switch(DETCICS_JAVA, "resp", r'"\w+"', r"\d+")
    assert {k.strip('"'): int(v) for k, v in numbers.items()} == {k.strip('"'): DFHRESP[k.strip('"')] for k in numbers}
    assert len(names) == 24 and len(numbers) == 19  # (today's sizes: a new arm must be a spec value too)


def test_cicstask_resp_name_and_abcode_switches_are_spec_values():
    """Deleted in PR 4 (CicsTask.respName / abcodeFor delegate to CicsSpec.java)."""
    names = _switch(forge.CICS_TASK_JAVA, "respName", r"\d+", r'"\w+"')
    assert {int(k): v.strip('"') for k, v in names.items()} == {int(k): spec_resp.RESP_NAME[int(k)] for k in names}
    abends = _switch(forge.CICS_TASK_JAVA, "abcodeFor", r'"\w+"', r'"\w+"')
    assert {k.strip('"'): v.strip('"') for k, v in abends.items()} == dict(spec_resp.CONDITION_ABEND)


# enums in ggcics.c that are not DFHRESP conditions
_C_NOT_CONDITIONS = {"ERRCOND", "RUNNING", "DONE", "XCTLED"}


def test_ggcics_condition_enums_and_abend_codes_are_spec_values():
    """Deleted in PR 4 (ggcics.c includes the generated ggcics_spec.h). The stub's enums are spread over the file
    (one per command family that added a condition); every one of them must be the spec's number."""
    enums: dict[str, int] = {}
    for body in re.findall(r"enum\s*\{([^}]*)\}", GGCICS_C):
        for name, value in re.findall(r"(\w+)\s*=\s*(\d+)", body):
            assert name not in enums, f"{name}: two enums"
            enums[name] = int(value)
    conditions = {k: v for k, v in enums.items() if k not in _C_NOT_CONDITIONS}
    assert conditions == {k: DFHRESP[k] for k in conditions}
    assert len(conditions) == 19
    abcode = re.search(r"condition_abcode\(int resp\)\s*\{(.*?)\n\}", GGCICS_C, re.S)
    assert abcode
    assert dict(re.findall(r'case (\w+): return "(\w{4})";', abcode.group(1))) == dict(spec_resp.CONDITION_ABEND)


def test_crucible_runner_condition_abcode_equals_the_spec():
    """Deleted when cics_crucible.py imports the spec's table (PR 4 / 5). (crucible_events.ABEND_FOR is the
    oracle's own table, never compared here: section 6; PR 6's report-only cross-check lists AEZJ / AEZV.)"""
    assert runner.CONDITION_ABCODE == dict(spec_resp.CONDITION_ABEND)


# the slice 1-4 commands, whose runtime refusals and stated facts PR 5 shares
KEYS = sorted(["PUT CONTAINER", "GET CONTAINER", "DELETE CONTAINER", "START", "RETRIEVE", "CANCEL", "RUN", "ASSIGN",
               "SEND TEXT"])  # fmt: skip


# ---- runtimes: refusal texts and stated facts ---------------------------------------------------------------------
@pytest.mark.parametrize("key", KEYS)
def test_runtime_refusal_texts_are_in_their_runtime(key):
    """Deleted in PR 5 (both runtimes share the spec's texts). The texts each runtime raises today; they differ
    between the two (e.g. ASSIGN STARTCODE in a RUN child: "(IBM lists no code for one)" vs ": IBM lists no code
    for it"), which is why the spec keeps both for now."""
    for r in COMMANDS[key].runtime_refusals:
        if r.java is not None:
            assert r.java in JAVA, r.situation
        if r.c is not None:
            assert r.c in GGCICS_C, r.situation


def test_stated_facts_are_the_runtimes_and_the_runners():
    """Deleted in PR 5 (the runner wires the facts from the spec)."""
    facts = {f.name: f for c in COMMANDS.values() for f in c.facts}
    for f in facts.values():
        if f.java is not None:
            assert f"public CicsTask {f.java}(" in forge.CICS_TASK_JAVA, f.name
        assert f'"{f.env}"' in GGCICS_C, f.name
    assert facts["userid"].region_default == runner.REGION_USERID
    assert facts["screen"].region_default == " ".join(map(str, runner.REGION_SCREEN))


# ---- engine verb tables -------------------------------------------------------------------------------------------
def test_engine_verb_tables_equal_the_spec():
    """Deleted in PR 8a (the engine walkers build their verb tables from the spec)."""
    for key, c in COMMANDS.items():
        e = c.engine
        if e is None:
            continue
        verb = key.split()[0]
        if e.resource is not None:
            table = {"CONTAINER": cics_resources._CONTAINER_VERBS, "FILE": cics_resources._FILE_VERBS,
                     "MAP": cics_resources._MAP_VERBS, "QUEUE": cics_resources._QUEUE_VERBS}[e.resource]  # fmt: skip
            assert table[verb] == e.access, key
        if e.task_verb is not None:
            assert cics_tasks._TASK_VERBS[e.task_verb] == (e.target_option, e.handle_option), key
        assert cics_resources._CHANNEL_VERBS.get(verb) == e.channel_option, key
