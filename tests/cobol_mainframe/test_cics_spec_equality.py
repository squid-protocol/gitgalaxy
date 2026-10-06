"""#4270 spec PR 1: TRANSITIONAL equality tests -- gitgalaxy/standards/cics equals every hand copy it will replace.

docs/language_status/cics_command_spec.md section 7. Each test names the copy it reads and the spec PR that makes
that copy import the spec; that PR DELETES the test (the copy is gone, so there is nothing left to compare):

    PR 2  det/cics.py (DFHRESP, OPTIONS, _REFUSED_WHY / _ASSIGN_REFUSED_WHY / _SEND_TEXT_REFUSED_WHY, check_options,
          the option-group messages)
    PR 3  tests/tools/equivalence_cics.py (DFHRESP, CICS_RESP, _CONTAINER_OPTIONS, the refused tuples / sets)
    PR 4  the Java switches (DetCics.condition / resp, CicsTask.respName / abcodeFor), ggcics.c's enums and
          condition_abcode
    PR 5  the stated facts (CicsTask.withX, $GGCICS_X, cics_crucible.REGION_*) and the runtime refusal texts
    PR 4/5 cics_crucible.CONDITION_ABCODE
    PR 8a the engine's verb tables (core/cics_resources.py, core/cics_tasks.py)

Where today's copies disagree with each other, the spec does not silently pick one: the difference is listed here
(the `*_DIFFERENCES` tables, each with its reason) and asserted to be exactly that, so it can neither grow nor be
fixed unnoticed. No behaviour changes in PR 1: nothing reads the spec yet."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "tools"))

import cics_crucible as runner  # noqa: E402
import equivalence_cics as harness  # noqa: E402

from gitgalaxy.core import cics_resources, cics_tasks  # noqa: E402
from gitgalaxy.standards.cics import resp as spec_resp  # noqa: E402
from gitgalaxy.standards.cics.commands import COMMANDS  # noqa: E402
from gitgalaxy.standards.cics.commands import send_text as spec_send_text  # noqa: E402
from gitgalaxy.standards.cics.commands.shared import RESP_OPTIONS  # noqa: E402
from gitgalaxy.tools.cobol_to_java import cobol_to_java_transaction_forge as forge  # noqa: E402
from gitgalaxy.tools.cobol_to_java.det import cics as det  # noqa: E402

DET_SRC = (ROOT / "gitgalaxy/tools/cobol_to_java/det/cics.py").read_text(encoding="utf-8")
HARNESS_SRC = (ROOT / "tests/tools/equivalence_cics.py").read_text(encoding="utf-8")
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
# where a copy disagrees with the spec's DFHRESP, and why the spec does not follow it
DFHRESP_DIFFERENCES = {
    # tests/tools/equivalence_cics.py DFHRESP has 101 names: these three of IBM's RESP values (det/cics.py has them)
    # are missing. No case names them, so no verdict depends on it; PR 3 imports the spec's table.
    "harness": {"VOLIDERR": 71, "RESIDERR": 75, "NOSPOOL": 80},
}


def test_det_dfhresp_equals_the_spec():
    """Deleted in PR 2 (det/cics.py imports DFHRESP from the spec)."""
    assert dict(det.DFHRESP) == dict(DFHRESP)


def test_harness_dfhresp_equals_the_spec_but_for_its_listed_gaps():
    """Deleted in PR 3. The harness's table lacks exactly DFHRESP_DIFFERENCES["harness"]."""
    missing = {k: v for k, v in DFHRESP.items() if k not in harness.DFHRESP}
    assert missing == DFHRESP_DIFFERENCES["harness"]
    assert {k: v for k, v in DFHRESP.items() if k in harness.DFHRESP} == harness.DFHRESP


def test_harness_fault_plan_conditions_are_spec_values():
    """Deleted in PR 3. CICS_RESP (#4023: the conditions a scenario may inject) is a subset with the same numbers."""
    assert {k: DFHRESP.get(k) for k in harness.CICS_RESP} == harness.CICS_RESP


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


# ---- options and refusals: the det translator ------------------------------------------------------------------
_BASE = {  # a minimal body of each command, to which one option is added
    "PUT CONTAINER": "PUT CONTAINER('C') FROM(WS-A)",
    "GET CONTAINER": "GET CONTAINER('C') INTO(WS-A)",
    "DELETE CONTAINER": "DELETE CONTAINER('C')",
    "START": "START TRANSID('T1')",
    "RETRIEVE": "RETRIEVE INTO(WS-A)",
    "CANCEL": "CANCEL REQID('R1')",
    "RUN": "RUN TRANSID('T1') CHILD(WS-C)",
    "ASSIGN": "ASSIGN USERID(WS-U)",
    "SEND TEXT": "SEND TEXT FROM(WS-A)",
}
KEYS = sorted(COMMANDS)


def _check(body: str) -> str | None:
    words, opts = det.parse_exec(body)
    try:
        det.check_options(words, opts)
    except det.CicsError as e:
        return str(e)
    return None


def test_every_spec_command_has_a_base_body():
    assert sorted(_BASE) == KEYS


@pytest.mark.parametrize("key", KEYS)
def test_det_options_equal_the_spec(key):
    """Deleted in PR 2 (OPTIONS is built from the spec)."""
    assert det.OPTIONS[key] == frozenset(COMMANDS[key].options)


@pytest.mark.parametrize("key", KEYS)
def test_det_accepts_every_option_the_spec_honours(key):
    """Deleted in PR 2."""
    for o in COMMANDS[key].options:
        assert _check(f"{_BASE[key]} {o}(WS-X)") is None, o


@pytest.mark.parametrize("key", KEYS)
def test_det_refusal_messages_equal_the_spec(key):
    """Deleted in PR 2. Each refused option alone, all of them together, and an option in neither table: the
    message check_options raises today, word for word, is the one the spec renders."""
    c = COMMANDS[key]
    for o in c.refused:
        assert _check(f"{_BASE[key]} {o}(WS-X)") == c.refusal_message([o]), o
    if c.refused:
        together = " ".join(f"{o}(WS-X)" for o in c.refused)
        assert _check(f"{_BASE[key]} {together}") == c.refusal_message(list(c.refused))
    assert _check(f"{_BASE[key]} GGNOSUCH(WS-X)") == c.refusal_message(["GGNOSUCH"])


def _leaks() -> dict[str, dict[str, str]]:
    """The cross-command reasons check_options shows today: _REFUSED_WHY is keyed by option alone, so on a command
    whose own refusals carry no default reason, an option of ANOTHER command's table gets that table's reason."""
    out: dict[str, dict[str, str]] = {}
    for key, c in COMMANDS.items():
        if key in ("ASSIGN", "SEND TEXT", "CANCEL"):  # (their own table / whole reason wins)
            continue
        leaked = {o: why for o, why in det._REFUSED_WHY.items() if o not in c.options and o not in c.refused}
        if leaked:
            out[key] = leaked
    return out


# Disagreements inside the translator: what the spec records per command, the translator keys by option alone
DET_DIFFERENCES = {
    # an option of another command's _REFUSED_WHY entry shows that entry's reason on these commands (GET CONTAINER
    # WAIT: "a RETRIEVE waiting for START data ..."): every _REFUSED_WHY option the command does not list itself.
    # The spec gives these no reason (default_refusal None). PR 2
    # must choose: keep the leak (a global fallback table) or rebaseline these messages -- none occurs in a corpus.
    "cross_command_reasons": {
        "PUT CONTAINER": 13, "GET CONTAINER": 10, "DELETE CONTAINER": 16, "START": 10, "RETRIEVE": 14, "RUN": 16,
    },
}  # fmt: skip


def test_det_cross_command_refusal_reasons_are_the_listed_difference():
    """Deleted in PR 2. The leak is exactly DET_DIFFERENCES["cross_command_reasons"] (option counts per command),
    and each leaked option's message is today's _REFUSED_WHY reason where the spec has none."""
    leaks = _leaks()
    assert {k: len(v) for k, v in leaks.items()} == DET_DIFFERENCES["cross_command_reasons"]
    for key, leaked in leaks.items():
        for o, why in leaked.items():
            assert _check(f"{_BASE[key]} {o}(WS-X)") == f"{key} {o}: option not modelled ({o}: {why})"
            assert COMMANDS[key].refusal_message([o]) == f"{key} {o}: option not modelled"


def test_det_refusal_tables_equal_the_spec():
    """Deleted in PR 2. Every reason in _REFUSED_WHY is a spec refusal of a slice command with the same text (and
    the other way round); _ASSIGN_REFUSED_WHY and _SEND_TEXT_REFUSED_WHY are their commands' tables exactly."""
    general: dict[str, set[str]] = {}
    for key, c in COMMANDS.items():
        if key in ("ASSIGN", "SEND TEXT"):
            continue
        for o, r in c.refused.items():
            if not r.whole:
                general.setdefault(o, set()).add(r.why)
    assert {o: {why} for o, why in det._REFUSED_WHY.items()} == general
    assert det._ASSIGN_REFUSED_WHY == {o: r.why for o, r in COMMANDS["ASSIGN"].refused.items()}
    assert det._SEND_TEXT_REFUSED_WHY == {o: r.why for o, r in COMMANDS["SEND TEXT"].refused.items()}
    assert det.TEXT_OPTIONS == spec_send_text.TEXT_OPTIONS


def _template(msg: str) -> re.Pattern[str]:
    """A group message as it appears in source: each `{}` an f-string placeholder."""
    return re.compile(r"\{[^{}]*\}".join(re.escape(p) for p in msg.split("{}")))


@pytest.mark.parametrize("key", KEYS)
def test_det_group_messages_are_the_spec(key):
    """Deleted in PR 2 (the group checks are built from the spec). Each group's message is in det/cics.py."""
    for g in COMMANDS[key].groups:
        assert _template(g.msg).search(DET_SRC), g.msg


def test_assign_terminal_options_are_the_copies():
    """Deleted in PR 2 / 3. `raised_by` of ASSIGN's INVREQ RESP2 5 is the tuple both translators hard-code."""
    (invreq,) = [o for o in COMMANDS["ASSIGN"].outcomes if o.condition == "INVREQ"]
    literal = repr(invreq.raised_by).replace("'", '"')
    assert literal in DET_SRC and literal in HARNESS_SRC


# ---- options and refusals: the equivalence harness (the stub's translator) ----------------------------------------
def _function(name: str) -> ast.FunctionDef:
    tree = ast.parse(HARNESS_SRC)
    return next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)


def _assigned(fn: ast.FunctionDef, target: str) -> ast.expr:
    for n in ast.walk(fn):
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == target for t in n.targets):
            return n.value
    raise AssertionError(f"{fn.name}: no {target} = ...")


def _plain(key: str) -> set[str]:
    return set(COMMANDS[key].options) - set(RESP_OPTIONS)


# Disagreements between the harness and the translator (and so the spec), each with its reason
HARNESS_DIFFERENCES = {
    # deny-lists: the stub refuses only the options it lists, so an option in neither list (a typo, an IBM option
    # nobody modelled) is IGNORED by the stub where the translator refuses it. PR 3 makes the stub check the spec.
    "ignores_unknown_options": ["CANCEL", "RETRIEVE", "SEND TEXT", "START"],
    # option-rule messages the stub words its own way (spec message -> the stub's); PR 3 shares the translator's
    "group_messages": {
        "EXEC CICS option needs an argument": "without a name",  # (CONTAINER missing; PUT's FROM: "without FROM")
        "PUT CONTAINER {}: one data type": "PUT CONTAINER with two data types",
        "START {}: one expiry option": None,  # START INTERVAL and TIME, as the feature, no reason
        "START {} {}: HOURS / MINUTES / SECONDS go with AFTER / AT": None,
        "CANCEL without REQID: only CANCEL REQID is modelled": "CANCEL without REQID",
    },
    # option rules the stub does not check at all: START LENGTH and FLENGTH together (it takes LENGTH), START /
    # RETRIEVE LENGTH and FLENGTH together, START LENGTH without FROM (it moves the length and passes no area)
    "unchecked_groups": ["{} and {} together", "START LENGTH without FROM"],
}


def test_harness_container_options_equal_the_spec():
    """Deleted in PR 3 (_CONTAINER_OPTIONS goes)."""
    for verb, allowed in harness._CONTAINER_OPTIONS.items():
        assert allowed == _plain(f"{verb} CONTAINER"), verb


def test_harness_run_and_assign_allow_lists_equal_the_spec():
    """Deleted in PR 3. RUN's allowed tuple (_run_transid) and ASSIGN's `known` tuple and widths (_handle)."""
    run_allowed = next(
        ast.literal_eval(n.comparators[0])
        for n in ast.walk(_function("_run_transid"))
        if isinstance(n, ast.Compare) and isinstance(n.ops[0], ast.NotIn) and isinstance(n.comparators[0], ast.Tuple)
    )
    assert set(run_allowed) - {"RUN"} == set(COMMANDS["RUN"].options)
    handle = _function("_handle")
    assert set(ast.literal_eval(_assigned(handle, "known"))) == _plain("ASSIGN")
    widths = ast.literal_eval(_assigned(handle, "width").value)  # {...}[n]
    assert widths == {o: COMMANDS["ASSIGN"].options[o].width for o in widths}


def test_harness_deny_lists_equal_the_spec_refusals():
    """Deleted in PR 3. The stub's refused tuples (_interval_command) and _SEND_TEXT_REFUSED are exactly the
    spec's refused options of those commands."""
    refused = ast.literal_eval(_assigned(_function("_interval_command"), "refused").value)  # {...}[verb]
    for verb, names in refused.items():
        assert set(names) == set(COMMANDS[verb].refused), verb
    assert set(harness._SEND_TEXT_REFUSED) == set(COMMANDS["SEND TEXT"].refused)


@pytest.mark.parametrize("key", KEYS)
def test_harness_refuses_each_spec_refusal_by_name(key):
    """Deleted in PR 3. Every option the spec refuses is Unsupported in the stub too, as the feature
    `<command> <option>` (the stub gives no reason yet: PR 3 adds the translator's)."""
    feature = {"RUN": "RUN", "ASSIGN": "ASSIGN"}.get(key, key)
    for o in COMMANDS[key].refused:
        with pytest.raises(harness.Unsupported) as e:
            harness.translate_command(f"{_BASE[key]} {o}(WS-X)")
        assert e.value.features == [f"{feature} {o}"], o


def test_harness_ignores_unknown_options_where_listed():
    """Deleted in PR 3. An option in neither table: the stub refuses it on the allow-list commands and ignores it
    on exactly HARNESS_DIFFERENCES["ignores_unknown_options"]."""
    ignored = []
    for key in KEYS:
        try:
            harness.translate_command(f"{_BASE[key]} GGNOSUCH(WS-X)")
        except harness.Unsupported:
            continue
        ignored.append(key)
    assert ignored == HARNESS_DIFFERENCES["ignores_unknown_options"]
    for key in KEYS:
        assert _check(f"{_BASE[key]} GGNOSUCH(WS-X)") is not None  # the translator refuses every one


# the same message in the stub, composed from parts: f"RUN {' '.join(bad) or 'without TRANSID / CHILD'}"
_COMPOSED = {"RUN without TRANSID / CHILD": "'without TRANSID / CHILD'"}


def test_harness_group_messages_are_the_spec_or_listed():
    """Deleted in PR 3. Each group message is in the stub word for word, or is a listed difference (its own
    wording, None: refused as a bare feature) or a rule the stub does not check."""
    worded: dict[str, str | None] = HARNESS_DIFFERENCES["group_messages"]  # type: ignore[assignment]
    seen = set()
    for c in COMMANDS.values():
        for g in c.groups:
            seen.add(g.msg)
            if g.msg in HARNESS_DIFFERENCES["unchecked_groups"]:
                assert not _template(g.msg).search(HARNESS_SRC), g.msg
            elif g.msg in worded:
                assert not _template(g.msg).search(HARNESS_SRC), f"{g.msg}: now the same, drop the difference"
                if worded[g.msg]:
                    assert worded[g.msg] in HARNESS_SRC, g.msg
            elif g.msg in _COMPOSED:  # the same message, built from parts
                assert _COMPOSED[g.msg] in HARNESS_SRC, g.msg
            else:
                assert _template(g.msg).search(HARNESS_SRC), g.msg
    assert set(worded) | set(HARNESS_DIFFERENCES["unchecked_groups"]) <= seen


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
        if e.resource == "CONTAINER":
            assert cics_resources._CONTAINER_VERBS[verb] == e.access, key
        if e.task_verb is not None:
            assert cics_tasks._TASK_VERBS[e.task_verb] == (e.target_option, e.handle_option), key
        assert cics_resources._CHANNEL_VERBS.get(verb) == e.channel_option, key
