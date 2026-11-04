"""#4317: the estate-crucible scorer (tests/tools/estate_crucible.py).

The unit tests pin the projection of each channel onto the master DB with hand-made engine
facts, so they need no checkout. The end-to-end test scans a checkout of the crucible at the
pin and skips cleanly when there is none (ESTATE_CRUCIBLE_PATH, else ../estate-crucible
beside the main checkout). It asserts the scorecard's shape, not a score: the scorer is not
a gate yet (#4317 phase 5), and the seed horrors are open engine bugs.
"""

import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS / "tools"))
sys.path.insert(0, str(TESTS))
import _estate_crucible_pin as pin  # noqa: E402
import estate_crucible as ec  # noqa: E402


class FakeEngine:
    def __init__(self, units=None, synthetic=None, files=None, raw_imports=None):
        self.units = units or {}
        self.synthetic = synthetic or {}
        self.files = files or {}
        self.raw_imports = raw_imports or {}
        self.excluded = {}


def _unit(name, start, end, calls=(), transfers=()):
    return {
        "name": name,
        "start": start,
        "end": end,
        "calls": list(calls),
        "transfers": list(transfers),
        "synthetic": False,
    }


def _statuses(sc):
    return sorted((c.channel, c.fact, c.status, c.horror) for c in sc.checks)


def test_a_unit_is_scored_on_its_extent_not_only_its_name():
    eng = FakeEngine(units={"p.cbl": [_unit("A", 10, 12), _unit("B", 20, 25)]})
    entry = {
        "units": [
            {"name": "A", "kind": "paragraph", "start_line": 10, "end_line": 18, "horror": "H-0002"},
            {"name": "B", "kind": "paragraph", "start_line": 20, "end_line": 25},
        ]
    }
    sc = ec.Score()
    ec.score_units(sc, "p.cbl", entry, eng)
    got = {c.fact: c for c in sc.checks}
    assert got["A"].status == "fail" and "end_line: key 18 engine 12" in got["A"].detail and got["A"].horror == "H-0002"
    assert got["B"].status == "pass"


def test_the_main_line_is_found_as_a_synthetic_unit_or_missing():
    entry = {
        "units": [{"name": None, "kind": "mainline", "start_line": 5, "end_line": 9, "horror": "H-0003"}],
        "edges": [{"kind": "perform", "from": None, "target": "INIT", "line": 6, "horror": "H-0003"}],
    }
    sc = ec.Score()
    ec.score_units(sc, "p.cbl", entry, FakeEngine())
    ec.score_edges(sc, "p.cbl", entry, FakeEngine())
    assert [c.status for c in sc.checks] == ["missing", "missing"]
    synth = {
        "p.cbl": [{"name": "main", "start": 5, "end": None, "calls": ["INIT"], "transfers": [], "synthetic": True}]
    }
    sc = ec.Score()
    ec.score_units(sc, "p.cbl", entry, FakeEngine(synthetic=synth))
    ec.score_edges(sc, "p.cbl", entry, FakeEngine(synthetic=synth))
    assert [c.status for c in sc.checks] == ["pass", "pass"]


def test_an_unkeyed_callee_is_a_phantom_attributed_through_the_keys_phantom_list():
    eng = FakeEngine(units={"p.cbl": [_unit("MAIN", 1, 9, calls=["WORK", "TEST", "STRAY"], transfers=["000900"])]})
    entry = {
        "units": [{"name": "MAIN", "kind": "paragraph", "start_line": 1, "end_line": 9}],
        "edges": [
            {"kind": "perform", "from": "MAIN", "target": "WORK", "line": 2},
            {"kind": "goto", "from": "MAIN", "target": "END-PARA", "line": 4, "horror": "H-0001"},
        ],
        "phantoms": [
            {"channel": "edges", "kind": "perform", "from": "MAIN", "target": "TEST", "why": "w", "horror": "H-0006"},
            {"channel": "edges", "kind": "goto", "from": "MAIN", "target": "000900", "why": "w", "horror": "H-0001"},
            {
                "channel": "edges",
                "kind": "perform",
                "from": "MAIN",
                "target": "FOREVER",
                "why": "w",
                "horror": "H-0006",
            },
        ],
    }
    sc = ec.Score()
    ec.score_edges(sc, "p.cbl", entry, eng)
    assert _statuses(sc) == sorted(
        [
            ("edges", "MAIN -perform-> WORK @2", "pass", None),
            ("edges", "MAIN -goto-> END-PARA @4", "missing", "H-0001"),
            ("edges", "MAIN.calls_out_to STRAY", "phantom", None),
            ("edges", "MAIN.calls_out_to TEST", "phantom", "H-0006"),
            ("edges", "MAIN.transfers_to 000900", "phantom", "H-0001"),
            ("edges", "not MAIN -> FOREVER", "pass", "H-0006"),
        ]
    )


def test_a_copy_needs_the_raw_import_and_the_edge_and_accepts_an_alternative():
    ef = SimpleNamespace(copy_deps=["bms/MAPS.bms", "copybook/REC.cpy"])
    eng = FakeEngine(files={"p.cbl": ef}, raw_imports={"p.cbl": ["REC", "MAPS", "000600"]})
    entry = {
        "copies": [
            {"member": "REC", "kind": "copy", "line": 5, "resolves_to": "copybook/REC.cpy"},
            {
                "member": "MAPS",
                "kind": "copy",
                "line": 6,
                "resolves_to": "copybook/MAPS.cpy",
                "alternatives": ["bms/MAPS.bms"],
            },
            {"member": "SQLCA", "kind": "sql-include", "line": 7, "resolves_to": None},
        ],
        "phantoms": [{"channel": "copies", "member": "000600", "why": "seq", "horror": "H-0001"}],
    }
    sc = ec.Score()
    ec.score_copies(sc, "p.cbl", entry, eng)
    assert _statuses(sc) == sorted(
        [
            ("copies", "REC @5", "pass", None),
            ("copies", "MAPS @6", "pass", None),
            ("copies", "SQLCA @7", "missing", None),
            ("copies", "raw import 000600", "phantom", "H-0001"),
        ]
    )


def test_a_call_site_is_matched_on_verb_and_operand_then_compared():
    call = SimpleNamespace(verb="CALL", form="literal", operand="SUB", target="SUB", resolves_to=None, line=9)
    eng = FakeEngine(files={"p.cbl": SimpleNamespace(calls=[call])})
    entry = {
        "call_sites": [
            {
                "verb": "CALL",
                "form": "literal",
                "operand": "SUB",
                "target": "SUB",
                "line": 9,
                "resolves_to": "cobol/SUB.cbl",
                "depends_on": ["H-0008"],
            }
        ]
    }
    sc = ec.Score()
    ec.score_call_sites(sc, "p.cbl", entry, eng)
    (c,) = sc.checks
    assert c.status == "fail" and "resolves_to" in c.detail and c.depends_on == ["H-0008"]


def _runner_call(operand, target="BDLDDB2", resolves_to="cobol/BDLDDB2.cbl", line=22):
    return SimpleNamespace(
        verb="EXEC PGM", form="runner", operand=operand, target=target, resolves_to=resolves_to, line=line
    )


_RUN_KEY = {
    "verb": "RUN PROGRAM",
    "form": "literal",
    "operand": "BDLDDB2",
    "target": "BDLDDB2",
    "line": 22,
    "resolves_to": "cobol/BDLDDB2.cbl",
}


def _score_runner(calls, keyed=(_RUN_KEY,)):
    eng = FakeEngine(files={"j.jcl": SimpleNamespace(calls=calls)})
    sc = ec.Score()
    ec.score_call_sites(sc, "j.jcl", {"call_sites": list(keyed)}, eng)
    return [(c.fact, c.status) for c in sc.checks]


@pytest.mark.parametrize("runner", ["IKJEFT01", "IKJEFT1A", "IKJEFT1B"])
def test_a_tso_runner_row_is_the_keyed_run_program_call(runner):
    assert _score_runner([_runner_call(f"{runner} RUN PROGRAM")]) == [("RUN PROGRAM BDLDDB2 @22", "pass")]


def test_a_runner_row_with_another_target_or_line_fails_not_passes():
    got = _score_runner([_runner_call("IKJEFT01 RUN PROGRAM", target="OTHER")])
    assert ("RUN PROGRAM BDLDDB2 @22", "missing") in got and ("RUN PROGRAM OTHER @22", "phantom") in got
    assert _score_runner([_runner_call("IKJEFT01 RUN PROGRAM", line=23)]) == [("RUN PROGRAM BDLDDB2 @22", "fail")]


@pytest.mark.parametrize("via", ["TSO CALL", "DFSRRC00"])
def test_a_runner_via_the_key_does_not_define_stays_a_phantom(via):
    got = _score_runner([_runner_call(f"IKJEFT01 {via}")])
    assert ("RUN PROGRAM BDLDDB2 @22", "missing") in got and any(s == "phantom" for _, s in got)


def test_a_plain_exec_pgm_row_is_untouched():
    plain = SimpleNamespace(verb="EXEC PGM", form="literal", operand="SORT", target="SORT", resolves_to=None, line=5)
    key = {"verb": "EXEC PGM", "form": "literal", "operand": "SORT", "target": "SORT", "line": 5, "resolves_to": None}
    assert _score_runner([plain], keyed=(key,)) == [("EXEC PGM SORT @5", "pass")]


def test_a_value_keeps_the_blanks_inside_its_literal():
    assert ec._val("'PAGE '") == "PAGE "
    assert ec._val("PAGE ") == "PAGE "
    assert ec._val("ZERO") == "ZERO"


def test_a_key_in_another_format_is_refused(tmp_path):
    (tmp_path / "key").mkdir()
    (tmp_path / "key" / "manifest.json").write_text(json.dumps({"format": "estate-crucible-key/2", "members": {}}))
    with pytest.raises(ValueError, match="estate-crucible-key/2"):
        ec.load_key(tmp_path)


def test_the_pin_is_the_manifest_ref():
    text = (TESTS / "crucible_pins.toml").read_text()
    found = re.findall(r'^\[estate\]\n(?:(?!\[).*\n)*?ref = "(.*)"$', text, flags=re.M)
    assert found == [pin.PINNED_REF] and re.fullmatch(r"[0-9a-f]{40}|v\d+\.\d+\.\d+", pin.PINNED_REF)


# ---- end to end: a checkout of the crucible at the pin -----------------------------------------


def _checkout():
    path = ec.crucible_path(None)
    if not (path / "key" / "manifest.json").is_file():
        pytest.skip(f"no estate-crucible checkout at {path} (set {pin.PATH_ENV})")
    msg = pin.pin_mismatch(path)
    if msg:
        pytest.skip(msg)
    return path


def test_every_key_fact_is_scored_against_a_scan(tmp_path):
    crucible = _checkout()
    sc = ec.score(crucible, ec.scan(crucible, tmp_path))
    _, key = ec.load_key(crucible)
    assert {c.status for c in sc.checks} <= set(ec.STATUSES)
    keyed = sum(len(e.get(ch, [])) for e in key.values() for ch in ec.CHANNELS)
    scored = sum(1 for c in sc.checks if c.status != "phantom" and not c.fact.startswith("not "))
    assert scored >= keyed  # every keyed fact has at least one check (a layout's overlays add one)
    verdicts = ec.horror_verdicts(sc, crucible)
    assert [h["id"] for h in verdicts] == sorted(
        json.loads((crucible / "key" / "manifest.json").read_text())["horrors"]
    )
    assert ec.markdown(sc, crucible).count("| H-") == len(verdicts)


def test_a_gdg_reference_may_be_recorded_as_its_base_or_with_its_generation_only():
    eng = FakeEngine(raw_imports={"j.jcl": ["PROD.A", "PROD.B(+1)", "PROD.C("]})
    entry = {
        "language": "jcl",
        "jcl_datasets": [
            {"dsn": "PROD.A", "generation": "0", "step": "S", "dd": "A", "line": 2},
            {"dsn": "PROD.B", "generation": "+1", "step": "S", "dd": "B", "line": 3},
            {"dsn": "PROD.C", "generation": "-1", "step": "S", "dd": "C", "line": 4, "horror": "H-0011"},
        ],
    }
    sc = ec.Score()
    ec.score_jcl_datasets(sc, "j.jcl", entry, eng)
    assert _statuses(sc) == sorted(
        [
            ("jcl_datasets", "S.A PROD.A(0)", "pass", None),
            ("jcl_datasets", "S.B PROD.B(+1)", "pass", None),
            ("jcl_datasets", "S.C PROD.C(-1)", "missing", "H-0011"),
            ("jcl_datasets", "raw import PROD.C(", "phantom", "H-0011"),
        ]
    )


def test_file_edges_are_scored_per_target_and_kind():
    eng = FakeEngine()
    eng.file_edges = {"p.cbl": {("q.cbl", "call"), ("r.cbl", "call")}}
    entry = {"file_edges": [{"kind": "call", "target": "q.cbl"}, {"kind": "exec", "target": "q.cbl"}]}
    sc = ec.Score()
    ec.score_file_edges(sc, "p.cbl", entry, eng)
    assert _statuses(sc) == sorted(
        [
            ("file_edges", "call -> q.cbl", "pass", None),
            ("file_edges", "exec -> q.cbl", "missing", None),
            ("file_edges", "call -> r.cbl", "phantom", None),
        ]
    )


def test_the_scan_is_told_every_non_utf8_members_code_page():
    assert ec.source_encoding_arg({}) == []
    manifest = {"code_pages": {"apps/N/cobol/KØB.cbl": "cp277", "apps/J/cobol/A.cbl": "cp930"}}
    assert ec.source_encoding_arg(manifest) == [
        "--source-encoding",
        "apps/J/cobol/A.cbl=cp930,apps/N/cobol/KØB.cbl=cp277",
    ]


def test_a_data_move_is_matched_on_verb_line_source_and_target():
    def row(verb, source, kind, target, line):
        return SimpleNamespace(
            verb=verb,
            source=source,
            source_kind=kind,
            target=target,
            corresponding=False,
            source_refmod=False,
            target_refmod=False,
            line=line,
            source_refmod_text=None,
        )

    eng = FakeEngine(
        files={
            "p.cbl": SimpleNamespace(
                data_moves=[row("MOVE", "SPACE", "figurative", "X", 9), row("MOVE", "'A'", "literal", "Y", 8)]
            )
        }
    )
    base = {"corresponding": False, "source_refmod": False, "target_refmod": False, "source_refmod_text": None}
    entry = {
        "data_moves": [
            {"verb": "MOVE", "source": "'A'", "source_kind": "literal", "target": "Y", "line": 8, **base},
            {
                "verb": "MOVE",
                "source": "SPACE",
                "source_kind": "figurative",
                "target": "X項目",
                "line": 9,
                "horror": "H-0040",
                **base,
            },
        ],
        "phantoms": [{"channel": "data_moves", "target": "X", "why": "w", "horror": "H-0040"}],
    }
    sc = ec.Score()
    ec.score_data_moves(sc, "p.cbl", entry, eng)
    assert _statuses(sc) == sorted(
        [
            ("data_moves", "MOVE 'A' -> Y @8", "pass", None),
            ("data_moves", "MOVE SPACE -> X項目 @9", "missing", "H-0040"),
            ("data_moves", "MOVE SPACE -> X @9", "phantom", "H-0040"),
        ]
    )


# ---- phase 3 (v0.4.0): copy libraries, collisions, gaps, dead code -----------------------------


def test_the_scan_is_told_the_keys_own_copy_libraries_when_it_has_them():
    declared = {
        "libraries": {"ORDROLD": ["apps/ORDR/oldcopy"]},
        "syslib": [{"programs": "apps/ORDR/*", "order": ["ORDROLD"]}],
    }
    assert ec.copy_library_declaration({"copy_libraries": declared, "members": {}}) == declared
    derived = ec.copy_library_declaration(
        {
            "members": {
                "apps/A/copybook/X.cpy": {"app": "A", "library": "copybook"},
                "shared/copylib/Y.cpy": {"app": None, "library": "copylib"},
            }
        }
    )
    assert derived["syslib"] == [{"programs": "apps/A/*", "order": ["ACPY", "SHRCPY"]}]


def test_a_collision_is_matched_on_member_and_compared_on_winner_and_shadowed_libraries():
    eng = FakeEngine()
    eng.collisions = [
        {
            "importer": "p.cbl",
            "member": "ORDREC",
            "resolved": "a/ORDREC.cpy",
            "library": "ACPY",
            "shadowed": [{"library": "SHRCPY", "paths": ["s/ORDREC.cpy"]}],
        },
        {"importer": "p.cbl", "member": "DATEWS", "resolved": "a/DATEWS.cpy", "library": "ACPY", "shadowed": []},
    ]
    entry = {
        "copy_collisions": [
            {
                "member": "ORDREC",
                "line": 9,
                "library": "ACPY",
                "resolves_to": "a/ORDREC.cpy",
                "shadowed": [
                    {"library": "SHRCPY", "path": "s/ORDREC.cpy"},
                    {"library": "AOLD", "path": "o/ORDREC.cpy"},
                ],
                "horror": "H-0052",
            },
            {"member": "ADDRREC", "line": 12, "library": "ACPY", "resolves_to": "a/ADDRREC.cpy", "shadowed": []},
        ]
    }
    sc = ec.Score()
    ec.score_copy_collisions(sc, "p.cbl", entry, eng)
    assert _statuses(sc) == sorted(
        [
            ("copy_collisions", "ORDREC @9", "fail", "H-0052"),
            ("copy_collisions", "ADDRREC @12", "missing", None),
            ("copy_collisions", "DATEWS (reported)", "phantom", None),
        ]
    )
    eng.collisions = None
    sc = ec.Score()
    ec.score_copy_collisions(sc, "p.cbl", entry, eng)
    assert {c.status for c in sc.checks} == {"unscored"}


def test_a_gap_fails_only_when_the_scan_resolves_it_to_a_member_of_that_name():
    eng = FakeEngine()
    eng.out_edges = {"p.cbl": {("apps/A/cobol/PRICE.cbl", "import"), ("apps/A/copybook/REC.cpy", "import")}}
    entry = {
        "gaps": [
            {"kind": "copy", "name": "PRICE", "line": 5, "why": "", "horror": "H-0053"},
            {"kind": "call", "name": "VENDOR", "line": 9, "why": ""},
        ]
    }
    sc = ec.Score()
    ec.score_gaps(sc, "p.cbl", entry, eng)
    assert _statuses(sc) == sorted(
        [("gaps", "copy PRICE @5", "fail", "H-0053"), ("gaps", "call VENDOR @9", "pass", None)]
    )


def test_dead_code_is_an_unused_unit_or_a_member_nothing_points_at():
    eng = FakeEngine(
        units={"p.cbl": [dict(_unit("9000-OLD", 40, 44), usage=1), dict(_unit("1000-LIVE", 30, 39), usage=0)]}
    )
    eng.in_edges = {"old.cbl": {("main.cbl", "call")}}
    sc = ec.Score()
    ec.score_dead(
        sc,
        "p.cbl",
        {
            "dead": [
                {"kind": "paragraph", "name": "9000-old", "line": 40, "why": ""},
                {"kind": "paragraph", "name": "1000-LIVE", "line": 30, "why": ""},
                {"kind": "paragraph", "name": "GONE", "line": 50, "why": ""},
            ]
        },
        eng,
    )
    ec.score_dead(
        sc, "old.cbl", {"dead": [{"kind": "program", "name": "OLD", "line": 2, "why": "", "horror": "H-0051"}]}, eng
    )
    ec.score_dead(sc, "orphan.cpy", {"dead": [{"kind": "copybook", "name": "ORPHAN", "line": 1, "why": ""}]}, eng)
    assert _statuses(sc) == sorted(
        [
            ("dead", "paragraph 9000-old @40", "pass", None),
            ("dead", "paragraph 1000-LIVE @30", "fail", None),
            ("dead", "paragraph GONE @50", "missing", None),
            ("dead", "program OLD @2", "fail", "H-0051"),
            ("dead", "copybook ORPHAN @1", "pass", None),
        ]
    )


def test_an_explicit_file_edge_phantom_is_attributed_to_its_horror():
    eng = FakeEngine()
    eng.file_edges = {"main.cbl": {("ORDV#OLD.cbl", "call")}}
    entry = {
        "phantoms": [
            {"channel": "file_edges", "kind": "call", "target": "ORDV#OLD.cbl", "why": "stale copy", "horror": "H-0050"}
        ]
    }
    sc = ec.Score()
    ec.score_file_edges(sc, "main.cbl", entry, eng)
    assert _statuses(sc) == [("file_edges", "call -> ORDV#OLD.cbl", "phantom", "H-0050")]


def test_a_copy_gap_ignores_the_members_own_call_of_a_program_with_that_name():
    eng = FakeEngine()
    eng.out_edges = {"p.cbl": {("apps/A/cobol/PRICE.cbl", "call")}}
    sc = ec.Score()
    ec.score_gaps(sc, "p.cbl", {"gaps": [{"kind": "copy", "name": "PRICE", "line": 5, "why": ""}]}, eng)
    assert _statuses(sc) == [("gaps", "copy PRICE @5", "pass", None)]


def test_cics_macro_table_resources_and_explicit_phantoms_are_scored():
    ef = SimpleNamespace(
        screen_fields=[],
        csd_resources=[
            SimpleNamespace(
                resource_type="FILE",
                name="SHPFILE",
                group=None,
                macro_table="DFHFCT01",
                line=5,
                program=None,
                dsname="PROD.SHIP.MASTER",
                ddname=None,
                record_format="F",
            ),
            SimpleNamespace(
                resource_type="SRT",
                name="S0C7",
                group=None,
                macro_table="DFHSRT01",
                line=9,
                program=None,
                dsname=None,
                ddname=None,
                record_format=None,
            ),
        ],
        transactions=[
            SimpleNamespace(transid="SHPM", program="SHPINQ", line=12, resolves_to="apps/SHIP/cobol/SHPINQ.cbl")
        ],
    )
    eng = FakeEngine(files={"apps/SHIP/asm/SHPTBL.asm": ef})
    entry = {
        "csd_resources": [
            {
                "type": "FILE",
                "name": "SHPFILE",
                "group": "DFHFCT01",
                "line": 5,
                "dsname": "PROD.SHIP.MASTER",
                "record_format": "F",
                "horror": "H-0063",
            }
        ],
        "transactions": [
            {
                "transid": "SHPM",
                "program": "SHPINQ",
                "group": "DFHPCT01",
                "line": 12,
                "resolves_to": "apps/SHIP/cobol/SHPINQ.cbl",
                "horror": "H-0063",
            }
        ],
        "phantoms": [
            {"channel": "csd_resources", "type": "SRT", "name": "S0C7", "why": "RECOVER=NO", "horror": "H-0063"},
            {"channel": "csd_resources", "type": "TERMINAL", "name": "LINE", "why": "TYPE=LINE", "horror": "H-0063"},
        ],
    }
    sc = ec.Score()
    ec.score_cics(sc, "apps/SHIP/asm/SHPTBL.asm", entry, eng)
    assert _statuses(sc) == sorted(
        [
            ("csd_resources", "FILE SHPFILE", "pass", "H-0063"),
            ("csd_resources", "SRT S0C7", "phantom", "H-0063"),
            ("csd_resources", "not TERMINAL LINE", "pass", "H-0063"),
            ("transactions", "SHPM", "pass", "H-0063"),
        ]
    )


# ---- Batch Badlands (#7065): the JCL execution and utility-card facts


def _row(kind, **kw):
    base = dict(
        kind=kind,
        name=None,
        step_ordinal=None,
        step_name=None,
        program=None,
        proc=None,
        cond=None,
        if_cond=None,
        in_proc=None,
        dd_name=None,
        dsn=None,
        disp=None,
        generation=None,
        line=0,
        disp_normal=None,
        parm=None,
        instream=None,
    )
    return SimpleNamespace(**dict(base, **kw))


def _jcl(flow, **entry):
    eng = FakeEngine(files={"j.jcl": SimpleNamespace(job_flow=flow)})
    sc = ec.Score()
    ec.score_jcl(sc, "j.jcl", dict(language="jcl", **entry), eng)
    ec.score_jcl_utility_cards(sc, "j.jcl", dict(language="jcl", **entry), eng)
    return sc


def _step_key(**kw):
    return dict(step="S1", ordinal=1, program="X", exec_proc=None, cond=None, line=5, **kw)


def _step_row(**kw):
    return _row("STEP", step_name="S1", step_ordinal=1, program="X", line=5, **kw)


def test_a_step_parm_and_if_branch_are_compared_when_the_key_states_them():
    key = [_step_key(parm="MONTHLY", if_cond="LOAD020.RC = 0", branch="then")]
    sc = _jcl([_step_row(parm="MONTHLY", if_cond="(LOAD020.RC = 0)")], jcl_steps=key)
    assert [c.status for c in sc.checks] == ["pass"]
    sc = _jcl([_step_row(parm="WEEKLY", if_cond="NOT (LOAD020.RC = 0)")], jcl_steps=key)
    assert sc.checks[0].status == "fail"
    assert "parm" in sc.checks[0].detail and "branch" in sc.checks[0].detail
    key = [_step_key(if_cond="LOAD020.RC = 0", branch="else")]
    assert _jcl([_step_row(if_cond="NOT (LOAD020.RC = 0)")], jcl_steps=key).checks[0].status == "pass"


def test_a_key_without_the_new_fields_scores_a_step_as_before():
    sc = _jcl([_step_row(parm="IGNORED", if_cond="(A.RC = 0)")], jcl_steps=[_step_key()])
    assert [c.status for c in sc.checks] == ["pass"]


def test_a_job_restart_is_unscored_because_the_engine_keeps_none():
    sc = _jcl([_step_row()], jcl_steps=[_step_key(restart="LOAD020")])
    assert [c.status for c in sc.checks] == ["pass", "unscored"]


_SLICE3_STEP_FIELDS = {
    "restart_checkid": "C0000012",
    "rd": "R",
    "parm_overrides": [{"step": "RPT020", "parm": "QUARTERLY"}],
    "cond_overrides": [{"step": "RPT020", "cond": "(4,LT,SRT010)"}],
}


@pytest.mark.parametrize("field", sorted(_SLICE3_STEP_FIELDS))
def test_each_slice3_step_field_is_reported_unscored_with_a_reason_never_dropped(field):
    sc = _jcl([_step_row()], jcl_steps=[_step_key(**{field: _SLICE3_STEP_FIELDS[field]})])
    assert [c.status for c in sc.checks] == ["pass", "unscored"]
    assert field in sc.checks[1].fact and "job_flow_data keeps no" in sc.checks[1].detail


def test_a_step_with_every_slice3_field_adds_one_unscored_check_per_field():
    sc = _jcl([_step_row()], jcl_steps=[_step_key(restart="CHK020", **_SLICE3_STEP_FIELDS)])
    assert sorted(c.status for c in sc.checks) == ["pass"] + ["unscored"] * 5
    assert "RPT020:QUARTERLY" in " ".join(c.fact for c in sc.checks)


def test_a_step_without_the_slice3_fields_adds_no_check():
    assert [c.status for c in _jcl([_step_row()], jcl_steps=[_step_key()]).checks] == ["pass"]


def test_a_job_level_dd_before_the_first_exec_has_a_null_step_and_scores_against_a_null_step_row():
    key = [dict(_dd_key(), step=None, dd="SYSCHK", dsn="P.CHK", disp="OLD")]
    row = _dd_row(step_name=None, dd_name="SYSCHK", dsn="P.CHK", disp="OLD")
    sc = _jcl([row], jcl_dds=key)
    assert [c.status for c in sc.checks] == ["pass"]
    assert [c.status for c in _jcl([], jcl_dds=key).checks] == ["missing"]
    # the same DD under a step is not the job-level one
    sc = _jcl([_dd_row(dsn="P.CHK", dd_name="SYSCHK")], jcl_dds=key)
    assert sorted(c.status for c in sc.checks) == ["missing", "phantom"]


def test_an_override_dd_naming_a_dsn_matches_the_row_named_after_the_proc_step():
    key = [dict(_dd_key(override_of="RPT020"), step="QTR", dd="RPTOUT", dsn="P.OUT", disp="NEW")]
    row = _dd_row(step_name="RPT020", dd_name="RPTOUT", dsn="P.OUT", disp="NEW")
    assert _jcl([row], jcl_dds=key).checks[0].status == "pass"
    assert _jcl([dict_row(row, dsn="P.OTHER")], jcl_dds=key).checks[0].status == "fail"
    # a row under the calling step's own name is not the override
    sc = _jcl([dict_row(row, step_name="QTR")], jcl_dds=key)
    assert sorted(c.status for c in sc.checks) == ["missing", "phantom"]


def test_a_sysout_key_stated_as_class_writer_form_matches_the_engine_class():
    key = [dict(_dd_key(), line=6, step="S1", dd="RPTOUT", dsn=None, disp=None, sysout="(A,,STD1)")]
    eng = FakeEngine(
        files={"j.jcl": SimpleNamespace(job_flow=[_row("SYSOUT", step_name="S1", dd_name="RPTOUT", line=6)])}
    )
    eng.sysout = {("j.jcl", 6): "A"}
    sc = ec.Score()
    ec.score_jcl(sc, "j.jcl", dict(language="jcl", jcl_dds=key), eng)
    assert [c.status for c in sc.checks] == ["pass"]


def test_an_override_dd_that_is_sysout_matches_the_sysout_row_named_after_the_proc_step():
    key = [dict(_dd_key(override_of="RPT020"), line=7, step="QTR", dd="RPTOUT", dsn=None, disp=None, sysout="B")]
    row = _row("SYSOUT", step_name="RPT020", dd_name="RPTOUT", line=7)
    eng = FakeEngine(files={"j.jcl": SimpleNamespace(job_flow=[row])})
    eng.sysout = {("j.jcl", 7): "B"}
    sc = ec.Score()
    ec.score_jcl(sc, "j.jcl", dict(language="jcl", jcl_dds=key), eng)
    assert [c.status for c in sc.checks] == ["pass"]
    eng.sysout = {("j.jcl", 7): "A"}
    sc = ec.Score()
    ec.score_jcl(sc, "j.jcl", dict(language="jcl", jcl_dds=key), eng)
    assert [c.status for c in sc.checks] == ["fail"] and "sysout" in sc.checks[0].detail
    assert [c.status for c in _jcl([], jcl_dds=key).checks] == ["missing"]


def test_a_dummy_dd_is_the_dummy_row_and_an_unkeyed_dummy_row_is_a_phantom():
    key = [dict(_dd_key(), line=9, step="S1", dd="TRACE", dsn=None, disp=None, sysout=None, dummy=True)]
    row = _row("DUMMY", step_name="S1", dd_name="TRACE", line=9)
    assert [c.status for c in _jcl([row], jcl_dds=key).checks] == ["pass"]
    assert [c.status for c in _jcl([dict_row(row, line=10)], jcl_dds=key).checks] == ["fail"]
    assert [c.status for c in _jcl([], jcl_dds=key).checks] == ["missing"]
    assert [c.status for c in _jcl([row], jcl_dds=[]).checks] == ["phantom"]
    # a DUMMY row is not a DSN DD: it never satisfies a keyed dataset DD
    dsn_key = [dict(_dd_key(), line=9, step="S1", dd="TRACE", dsn="A.B", disp="SHR")]
    assert "pass" not in [c.status for c in _jcl([row], jcl_dds=dsn_key).checks]


def test_a_sysout_dd_keeps_its_output_refs_unscored():
    key = [dict(_dd_key(), line=7, step="S1", dd="RPT", dsn=None, disp=None, sysout="*", output_refs=["OUT1"])]
    row = _row("SYSOUT", step_name="S1", dd_name="RPT", line=7)
    eng = FakeEngine(files={"j.jcl": SimpleNamespace(job_flow=[row])})
    eng.sysout = {("j.jcl", 7): "*"}
    sc = ec.Score()
    ec.score_jcl(sc, "j.jcl", dict(language="jcl", jcl_dds=key), eng)
    assert [c.status for c in sc.checks] == ["pass", "unscored"]


_SLICE4_STEP_FIELDS = {"set_symbols": [{"name": "HLQ", "value": "PROD"}], "includes": ["BDLDDDS"]}


@pytest.mark.parametrize("field", sorted(_SLICE4_STEP_FIELDS))
def test_each_slice4_step_field_is_reported_unscored_with_a_reason(field):
    sc = _jcl([_step_row()], jcl_steps=[_step_key(**{field: _SLICE4_STEP_FIELDS[field]})])
    assert [c.status for c in sc.checks] == ["pass", "unscored"]
    assert field in sc.checks[1].fact and "job_flow_data keeps no" in sc.checks[1].detail


def test_a_set_symbol_is_labelled_name_equals_value():
    sc = _jcl([_step_row()], jcl_steps=[_step_key(set_symbols=[{"name": "HLQ", "value": "PROD"}])])
    assert "HLQ=PROD" in sc.checks[1].fact


def test_a_dd_of_an_include_group_is_unscored_not_matched_against_a_null_step_row():
    key = [dict(_dd_key(), job=None, proc=None, step=None, include="BDLDDDS", sysout="*", dsn=None, disp=None)]
    sc = _jcl([], jcl_dds=key)
    assert [c.status for c in sc.checks] == ["unscored"]
    assert "INCLUDE BDLDDDS" in sc.checks[0].fact and "INCLUDE" in sc.checks[0].detail
    # a non-SYSOUT member is not matched against the job-level row either
    key = [dict(key[0], sysout=None, dsn="A.B", disp="SHR")]
    assert [c.status for c in _jcl([_dd_row(step_name=None)], jcl_dds=key).checks] != ["pass"]


def test_an_added_sysout_dd_on_a_proc_step_is_scored_like_a_dsn_dd():
    key = [dict(_dd_key(override_of="RPT020", added=True), step="ADDQ", dd="AUDIT", dsn=None, disp=None, sysout="B")]
    # no SYSOUT row for it, and no procedure in the scan: the DD is missing
    assert [c.status for c in _jcl([], jcl_dds=key).checks] == ["missing"]


def test_a_nullfile_dd_is_the_dummy_row():
    key = [dict(_dd_key(), dd="SORTWK01", dsn=None, disp=None, dummy=True)]
    assert [c.status for c in _jcl([], jcl_dds=key).checks] == ["missing"]
    row = _row("DUMMY", step_name="S1", dd_name="SORTWK01", line=6)
    assert [c.status for c in _jcl([row], jcl_dds=key).checks] == ["pass"]


def _dd_key(**kw):
    return dict(step="S1", dd="D", dsn="A.B", generation=None, disp="SHR", disp_normal=None, sysout=None, line=6, **kw)


def _dd_row(**kw):
    return _row("DD", **dict(dict(step_name="S1", dd_name="D", dsn="A.B", disp="SHR", line=6), **kw))


def test_a_temporary_dataset_is_a_dsn_starting_with_two_ampersands():
    key = [dict(_dd_key(temp=True), dsn="&&T")]
    assert _jcl([_dd_row(dsn="&&T")], jcl_dds=key).checks[0].status == "pass"
    assert _jcl([_dd_row(dsn="&&T")], jcl_dds=[dict(key[0], temp=False)]).checks[0].status == "fail"


def test_a_concatenated_dd_has_no_name_of_its_own_and_matches_the_next_row_of_its_parent():
    first = _dd_key()
    cont = dict(_dd_key(concat_of="D"), dd=None, dsn="C.D", line=7)
    rows = [_dd_row(), _row("DD", step_name="S1", dd_name="D", dsn="C.D", disp="SHR", line=7)]
    sc = _jcl(rows, jcl_dds=[first, cont])
    assert [c.status for c in sc.checks] == ["pass", "pass"]
    assert _jcl(rows[:1], jcl_dds=[first, cont]).checks[1].status == "missing"


def test_an_inline_stream_is_found_in_its_instream_row_and_counted_in_lines():
    key = [dict(_dd_key(inline_lines=2), dd="SYSIN", dsn=None, disp=None)]
    row = _row(
        "INSTREAM", step_name="S1", dd_name="SYSIN", line=6, instream=" SORT FIELDS=(1,2,CH,A)\n SUM FIELDS=NONE"
    )
    assert _jcl([row], jcl_dds=key).checks[0].status == "pass"
    assert _jcl([dict_row(row, instream=" SORT")], jcl_dds=key).checks[0].status == "fail"
    assert _jcl([], jcl_dds=key).checks[0].status == "missing"


def dict_row(row, **kw):
    return SimpleNamespace(**dict(vars(row), **kw))


_BODY = (
    " DELETE PROD.X CLUSTER PURGE\n"
    " DEFINE CLUSTER (NAME(PROD.X) -\n"
    "        INDEXED KEYS(10 0)) -\n"
    "        CYLINDERS(1 1)\n"
    "* a comment\n"
    " SORT FIELDS=(1,10,CH,A),\n"
    "   EQUALS\n"
    " SUM FIELDS=NONE"
)


def _card(verb, operands, line):
    return dict(job="J", proc=None, step="S1", utility="IDCAMS", dd="SYSIN", verb=verb, operands=operands, line=line)


def test_cards_are_split_with_continuations_joined_and_the_hyphen_dropped():
    assert ec._cards(_BODY) == [
        (0, "DELETE", "PROD.X CLUSTER PURGE"),
        (1, "DEFINE", "CLUSTER (NAME(PROD.X) INDEXED KEYS(10 0)) CYLINDERS(1 1)"),
        (5, "SORT", "FIELDS=(1,10,CH,A), EQUALS"),
        (7, "SUM", "FIELDS=NONE"),
    ]


def test_a_card_is_scored_on_its_line_verb_and_operands():
    row = _row("INSTREAM", step_name="S1", dd_name="SYSIN", line=10, instream=_BODY)
    cards = [
        _card("DELETE", "PROD.X CLUSTER PURGE", 11),
        _card("DEFINE", "CLUSTER (NAME(PROD.X) INDEXED KEYS(10 0)) CYLINDERS(1 1)", 12),
        _card("SORT", "FIELDS=(1,10,CH,A), EQUALS", 16),
        _card("SUM", "FIELDS=ZD", 18),  # operands differ
        _card("INREC", "FIELDS=(1,2)", 17),  # not there
    ]
    sc = _jcl([row], jcl_utility_cards=cards)
    assert [c.status for c in sc.checks] == ["pass", "pass", "pass", "fail", "missing"]
    assert {c.channel for c in sc.checks} == {"jcl_utility_cards"}


@pytest.mark.parametrize("dd", ["TOOLIN", "SYSUT1", "SYSTSIN", "systsin"])
def test_a_card_in_a_dd_the_engine_keeps_no_body_for_is_unscored_with_a_reason(dd):
    card = dict(_card("COPY", "FROM(A)", 30), dd=dd)
    row = _row("INSTREAM", step_name="S1", dd_name="SYSIN", line=10, instream=_BODY)
    c = _jcl([row], jcl_utility_cards=[card]).checks[0]
    assert (c.status, dd.upper() in c.detail) == ("unscored", True)


@pytest.mark.parametrize("dd", ["SYSTSIN", "SYSUT1", "SORTIN"])
def test_an_inline_dd_the_engine_keeps_no_body_for_is_unscored_not_missing(dd):
    key = [dict(_dd_key(inline_lines=2), dd=dd, dsn=None, disp=None)]
    c = _jcl([], jcl_dds=key).checks[0]
    assert c.status == "unscored" and "core/job_flow.py" in c.detail


@pytest.mark.parametrize("dd", ["SYSIN", "SYMNAMES", "SORTCNTL", "DFSPARM"])
def test_a_kept_control_dd_with_no_instream_row_is_still_missing(dd):
    key = [dict(_dd_key(inline_lines=2), dd=dd, dsn=None, disp=None)]
    assert _jcl([], jcl_dds=key).checks[0].status == "missing"
    card = dict(_card("SORT", "FIELDS=(1,2,CH,A)", 7), dd=dd)
    assert _jcl([], jcl_utility_cards=[card]).checks[0].status == "missing"


def test_an_explicit_temp_dataset_phantom_is_attributed_and_its_absence_passes():
    ph = dict(channel="jcl_datasets", dsn="&&T", step="S1", line=7, why="temporary", horror="H-0065")
    eng = FakeEngine(raw_imports={"j.jcl": ["&&T", "A.B"]})
    sc = ec.Score()
    ec.score_jcl_datasets(sc, "j.jcl", dict(language="jcl", jcl_datasets=[], phantoms=[ph]), eng)
    assert [(c.status, c.horror) for c in sc.checks if c.fact == "raw import &&T"] == [("phantom", "H-0065")]
    eng.raw_imports["j.jcl"] = ["A.B"]
    sc = ec.Score()
    ec.score_jcl_datasets(sc, "j.jcl", dict(language="jcl", jcl_datasets=[], phantoms=[ph]), eng)
    assert [(c.fact, c.status) for c in sc.checks if c.status == "pass"] == [("not &&T", "pass")]


def _fc_key(**kw):
    base = {
        "select": "ORD-FILE",
        "assign": "ORDKSD",
        "organization": "INDEXED",
        "access_mode": "DYNAMIC",
        "record_key": "ORD-ID",
        "file_status": "WS-ST",
        "fd_copies": [],
        "line": 11,
    }
    return dict(base, **kw)


def _fc_row(**kw):
    base = {
        "select_name": "ORD-FILE",
        "assign": "ORDKSD",
        "organization": "INDEXED",
        "access_mode": "DYNAMIC",
        "record_key": "ORD-ID",
        "alternate_keys": [],
        "relative_key": None,
        "file_status": "WS-ST",
        "fd_copies": [],
        "line": 11,
    }
    return SimpleNamespace(**dict(base, **kw))


def _fc(key, row):
    eng = FakeEngine(files={"p.cbl": SimpleNamespace(file_control=[row])})
    sc = ec.Score()
    ec.score_file_control(sc, "p.cbl", {"file_control": [key]}, eng)
    return sc


def test_alternate_keys_are_scored_on_name_and_duplicates_flag():
    key = _fc_key(alternate_keys=[{"name": "ORD-CUST", "duplicates": True}, {"name": "ORD-DT", "duplicates": False}])
    ok = _fc_row(alternate_keys=[("ORD-DT", False), ("ORD-CUST", True)])
    assert [c.status for c in _fc(key, ok).checks] == ["pass"]
    wrong_flag = _fc_row(alternate_keys=[("ORD-CUST", False), ("ORD-DT", False)])
    sc = _fc(key, wrong_flag)
    assert sc.checks[0].status == "fail" and "alternate_keys" in sc.checks[0].detail
    missing = _fc_row(alternate_keys=[("ORD-CUST", True)])
    assert _fc(key, missing).checks[0].status == "fail"


def test_relative_key_is_scored_when_the_key_states_it():
    key = _fc_key(organization="RELATIVE", record_key=None, relative_key="WS-SLOT-NO")
    row = _fc_row(organization="RELATIVE", record_key=None, relative_key="ws-slot-no")
    assert [c.status for c in _fc(key, row).checks] == ["pass"]
    sc = _fc(key, _fc_row(organization="RELATIVE", record_key=None, relative_key=None))
    assert sc.checks[0].status == "fail" and "relative_key" in sc.checks[0].detail


def test_a_file_without_key_fields_adds_no_check_even_if_the_engine_has_some():
    key = _fc_key(organization="SEQUENTIAL", record_key=None, access_mode="SEQUENTIAL")
    row = _fc_row(organization="SEQUENTIAL", record_key=None, access_mode="SEQUENTIAL")
    assert [c.status for c in _fc(key, row).checks] == ["pass"]
    assert [c.status for c in _fc(_fc_key(), _fc_row(alternate_keys=[("X", True)])).checks] == ["pass"]


def test_every_output_jcl_statement_is_unscored_with_a_reason_at_job_and_step_level():
    outs = [
        dict(job="BDLDOUT", step=None, name="OUT1", params=["DEST", "CLASS"], line=3),
        dict(job="BDLDOUT", step="OUT010", name="LOCAL", params=["COPIES"], line=9),
    ]
    eng = FakeEngine(files={"j.jcl": SimpleNamespace(job_flow=[])})
    sc = ec.Score()
    ec.score_jcl_outputs(sc, "j.jcl", {"jcl_outputs": outs}, eng)
    assert [c.status for c in sc.checks] == ["unscored", "unscored"]
    assert "OUT1 OUTPUT (job level)" in sc.checks[0].fact and "OUTPUT (OUT010)" in sc.checks[1].fact
    assert all("job_flow_data keeps no OUTPUT" in c.detail for c in sc.checks)
    assert "jcl_outputs" in ec.CHANNELS and ec.score_jcl_outputs in ec.SCORERS


def test_a_sysout_dd_with_output_references_is_unscored_and_names_them():
    key = [dict(_dd_key(output_refs=["*.OUT1", "*.LOCAL"]), dd="RPTOUT", dsn=None, disp=None, sysout="A")]
    sc = _jcl([_row("SYSOUT", step_name="S1", dd_name="RPTOUT", line=6)], jcl_dds=key)
    assert [c.status for c in sc.checks] == ["fail", "unscored"]  # no sysout class in the fake engine
    assert "OUTPUT=*.OUT1,*.LOCAL" in sc.checks[1].fact


def test_a_rerun_clause_adds_one_unscored_check_beside_the_scored_select():
    key = _fc_key(rerun={"assign": "SYSCKPT", "every": 1000})
    sc = _fc(key, _fc_row())
    assert [c.status for c in sc.checks] == ["pass", "unscored"]
    assert "RERUN SYSCKPT" in sc.checks[1].fact and "RERUN" in sc.checks[1].detail
    assert [c.status for c in _fc(_fc_key(), _fc_row()).checks] == ["pass"]


# ---- #7065: the JCL key fields #7449 listed as uncompared (job, utility, symbolic, added, rerun every)


def _st(flow, channel, **entry):
    """Statuses of the keyed facts of one channel (a phantom row of the other scorer is not under test)."""
    return [c.status for c in _jcl(flow, **entry).checks if c.channel == channel and c.status != "phantom"]


def _job_row(name="J1"):
    return _row("JOB", name=name, line=1)


@pytest.mark.parametrize("engine_job,status", [("J1", "pass"), ("OTHER", "fail")])
def test_a_step_and_a_dd_are_compared_on_the_job_they_belong_to(engine_job, status):
    flow = [_job_row(engine_job), _step_row(), _dd_row()]
    assert _st(flow, "jcl_steps", jcl_steps=[_step_key(job="J1")]) == [status]
    assert _st(flow, "jcl_dds", jcl_dds=[_dd_key(job="J1")]) == [status]


def test_a_row_in_a_proc_has_no_job_and_a_row_before_any_job_row_fails_a_keyed_job():
    flow = [_job_row(), _step_row(in_proc="P1"), _dd_row(in_proc="P1")]
    assert _st(flow, "jcl_steps", jcl_steps=[_step_key(job=None, proc="P1")]) == ["pass"]
    assert _st(flow, "jcl_dds", jcl_dds=[_dd_key(job=None, proc="P1")]) == ["pass"]
    assert _st([_step_row()], "jcl_steps", jcl_steps=[_step_key(job="J1")]) == ["fail"]


def test_the_second_job_of_a_file_owns_the_rows_after_its_job_row():
    flow = [_job_row("J1"), _step_row(), _job_row("J2"), _dd_row()]
    assert _st(flow, "jcl_dds", jcl_dds=[_dd_key(job="J2")]) == ["pass"]
    assert _st(flow, "jcl_dds", jcl_dds=[_dd_key(job="J1")]) == ["fail"]


@pytest.mark.parametrize(
    "dsn,symbolic,status",
    [
        ("&HLQ..X", True, "pass"),
        ("&&T", False, "pass"),
        ("A.B", False, "pass"),
        ("&&T", True, "fail"),
        ("&HLQ..X", False, "fail"),
    ],
)
def test_a_symbolic_dsn_is_one_single_ampersand_never_a_temporary_dataset(dsn, symbolic, status):
    key = [dict(_dd_key(symbolic=symbolic), dsn=dsn)]
    assert _jcl([_dd_row(dsn=dsn)], jcl_dds=key).checks[0].status == status


def test_a_key_without_symbolic_or_job_scores_a_dd_as_before():
    assert _jcl([_dd_row(dsn="&HLQ..X")], jcl_dds=[dict(_dd_key(), dsn="&HLQ..X")]).checks[0].status == "pass"


@pytest.mark.parametrize("extra", [dict(sysout="B"), dict(dummy=True)])
def test_an_added_sysout_or_dummy_dd_is_unscored_when_the_proc_is_not_in_the_scan(extra):
    key = [dict(_dd_key(added=True, override_of="STEP1"), **extra)]
    row = _row("SYSOUT" if "sysout" in extra else "DUMMY", step_name="STEP1", dd_name="D", line=6)
    cs = _jcl([row], jcl_dds=key).checks
    assert any(c.status == "unscored" and c.fact.endswith("added") and "is not in the scan" in c.detail for c in cs)


def _added_flow(proc_dds=("D",), proc_in_scan=True):
    """A job whose EXEC S1 runs proc P (step STEP1); the proc defines the DDs `proc_dds`; an override row `STEP1.D`."""
    rows = [_row("STEP", step_name="S1", step_ordinal=1, program=None, proc="P", line=5)]
    if proc_in_scan:
        rows.append(_row("STEP", step_name="STEP1", in_proc="P", program="X", line=2))
        rows += [_row("DD", step_name="STEP1", dd_name=n, dsn="P.D", in_proc="P", line=3) for n in proc_dds]
    rows.append(_row("DD", step_name="STEP1", dd_name="D", dsn="A.B", disp="SHR", line=6))
    return rows


def _added_key(added):
    return [dict(_dd_key(added=added, override_of="STEP1"), step="S1")]


@pytest.mark.parametrize(
    "proc_dds,added,status",
    [((), True, "pass"), (("D",), False, "pass"), (("D",), True, "fail"), ((), False, "fail")],
)
def test_added_is_scored_against_the_proc_definitions_dd_rows(proc_dds, added, status):
    cs = _jcl(_added_flow(proc_dds), jcl_dds=_added_key(added)).checks
    assert [c.status for c in cs if c.fact.endswith(" added")] == [status]


def test_added_stays_unscored_when_the_procedure_is_not_in_the_scan():
    cs = _jcl(_added_flow((), proc_in_scan=False), jcl_dds=_added_key(True)).checks
    added = [c for c in cs if c.fact.endswith(" added")]
    assert [c.status for c in added] == ["unscored"] and "not in the scan" in added[0].detail


@pytest.mark.parametrize("program,status", [("IDCAMS", "pass"), ("SORT", "fail")])
def test_a_card_is_compared_on_the_utility_its_step_runs(program, status):
    row = _row("INSTREAM", step_name="S1", dd_name="SYSIN", line=10, instream=_BODY)
    flow = [_row("STEP", step_name="S1", step_ordinal=1, program=program, line=9), row]
    assert _st(flow, "jcl_utility_cards", jcl_utility_cards=[_card("DELETE", "PROD.X CLUSTER PURGE", 11)]) == [status]


def test_a_card_in_a_proc_step_looks_up_the_step_of_that_proc():
    row = _row("INSTREAM", step_name="S1", dd_name="SYSIN", line=10, instream=_BODY, in_proc="P1")
    flow = [
        _row("STEP", step_name="S1", step_ordinal=1, program="SORT", line=3),
        _row("STEP", step_name="S1", step_ordinal=1, program="IDCAMS", line=9, in_proc="P1"),
        row,
    ]
    card = dict(_card("DELETE", "PROD.X CLUSTER PURGE", 11), proc="P1")
    assert _st(flow, "jcl_utility_cards", jcl_utility_cards=[card]) == ["pass"]


def test_a_rerun_every_count_is_named_in_the_unscored_file_control_check():
    from types import SimpleNamespace as NS

    row = NS(
        select_name="F", assign="A", organization=None, access_mode=None, record_key=None, file_status=None,
        fd_copies=[], line=3, relative_key=None, alternate_keys=[],
    )  # fmt: skip
    eng = FakeEngine(files={"p.cbl": NS(file_control=[row])})
    key = dict(
        select="F",
        assign="A",
        organization=None,
        file_status=None,
        fd_copies=[],
        line=3,
        rerun=dict(assign="CK", every=1000),
    )
    sc = ec.Score()
    ec.score_file_control(sc, "p.cbl", dict(language="cobol", file_control=[key]), eng)
    c = [c for c in sc.checks if c.status == "unscored"][0]
    assert "1000" in c.detail


def _dli(line, pcb="DB-PCB", io="WS-IO-AREA", ssas=None):
    return SimpleNamespace(line=line, pcb=pcb, io_area=io, ssas=ssas, interface="CALL", function=None)


def _dli_eng(rows, resolved):
    eng = FakeEngine(files={"w.cbl": SimpleNamespace(dli_calls=rows)})
    eng.ir = SimpleNamespace(ims_calls=lambda: resolved)
    return eng


def _dli_key(line, **kw):
    return dict(function="GN", pcb="DB-PCB", io_area="WS-IO-AREA", ssas=[], line=line, horror="H-0097", **kw)


def test_a_cbltdli_call_is_scored_on_the_resolved_function_pcb_and_io_area():
    eng = _dli_eng([_dli(28), _dli(34, pcb="OTHER-PCB")], [{"file": "w.cbl", "line": 28, "function": "GN"}])
    sc = ec.Score()
    ec.score_dli_calls(sc, "w.cbl", {"dli_calls": [_dli_key(28), _dli_key(34), _dli_key(40)]}, eng)
    assert [c.status for c in sc.checks] == ["pass", "fail", "missing"]
    assert {c.channel for c in sc.checks} == {"dli_calls"}


def test_an_unresolved_function_fails_the_dli_call_not_passes_it():
    sc = ec.Score()
    ec.score_dli_calls(sc, "w.cbl", {"dli_calls": [_dli_key(28)]}, _dli_eng([_dli(28)], []))
    assert sc.checks[0].status == "fail"


def test_ssas_are_compared_comma_joined_in_order():
    key = _dli_key(28)
    key["ssas"] = ["SSA1", "SSA2"]
    sc = ec.Score()
    eng = _dli_eng([_dli(28, ssas="SSA1,SSA2")], [{"file": "w.cbl", "line": 28, "function": "GN"}])
    ec.score_dli_calls(sc, "w.cbl", {"dli_calls": [key]}, eng)
    assert sc.checks[0].status == "pass"


def _gen(kind, name, line, parent=None, nbytes=None):
    return SimpleNamespace(kind=kind, name=name, line=line, parent=parent, bytes=nbytes)


def test_an_ims_gen_segm_is_scored_on_parent_and_bytes():
    rows = [_gen("DBD", "HKEPDB", 2), _gen("SEGM", "KEEP", 3, None, 40), _gen("SEGM", "WALL", 4, "GATE", 40)]
    keys = [
        dict(kind="DBD", name="HKEPDB", line=2),
        dict(kind="SEGM", name="KEEP", parent="", bytes=40, line=3),
        dict(kind="SEGM", name="WALL", parent="KEEP", bytes=40, line=4),
        dict(kind="SEGM", name="GATE", parent="WALL", bytes=40, line=5),
    ]
    sc = ec.Score()
    ec.score_ims_gen(sc, "d.asm", {"ims_gen": keys}, FakeEngine(files={"d.asm": SimpleNamespace(ims_gen=rows)}))
    assert [c.status for c in sc.checks] == ["pass", "pass", "fail", "missing"]


def test_a_member_with_no_ims_keys_adds_no_ims_checks():
    sc = ec.Score()
    ec.score_dli_calls(sc, "x.cbl", {}, FakeEngine())
    ec.score_ims_gen(sc, "x.cbl", {}, FakeEngine())
    assert sc.checks == []


def _run_program_edge(got_edges, files, extra_calls=()):
    eng = FakeEngine(files=files)
    eng.file_edges = {"j.jcl": set(got_edges)}
    entry = {
        "call_sites": [{"verb": "RUN PROGRAM", "operand": "BDLDDB2", "line": 22, "horror": "H-0068"}, *extra_calls]
    }
    sc = ec.Score()
    ec.score_file_edges(sc, "j.jcl", entry, eng)
    return _statuses(sc)


def test_a_run_program_call_site_implies_the_exec_file_edge():
    files = {"d.cbl": SimpleNamespace(program_ids=["BDLDDB2"])}
    assert _run_program_edge({("d.cbl", "exec")}, files) == [("file_edges", "exec -> d.cbl", "pass", "H-0068")]
    assert _run_program_edge(set(), files) == [("file_edges", "exec -> d.cbl", "missing", "H-0068")]
    # two steps running the same program draw one edge
    twice = [{"verb": "RUN PROGRAM", "operand": "bdlddb2", "line": 40}]
    assert _run_program_edge({("d.cbl", "exec")}, files, twice) == [("file_edges", "exec -> d.cbl", "pass", "H-0068")]
    # an unresolved program states no edge; the engine's own exec edge stays a phantom
    assert _run_program_edge({("d.cbl", "exec")}, {}) == [("file_edges", "exec -> d.cbl", "phantom", None)]
    # a call edge is never excused by it
    assert ("file_edges", "call -> d.cbl", "phantom", None) in _run_program_edge({("d.cbl", "call")}, files)


def _sql_access_status(key_access, engine_access):
    row = SimpleNamespace(verb="INSERT", line=5, table="T", access=engine_access)
    eng = FakeEngine(files={"p.cbl": SimpleNamespace(sql_statements=[row], sql_tables=[])})
    entry = {"sql_statements": [{"verb": "INSERT", "line": 5, "table": "T", "access": key_access}]}
    sc = ec.Score()
    ec.score_sql(sc, "p.cbl", entry, eng)
    return [c.status for c in sc.checks if c.channel == "sql_statements"]


@pytest.mark.parametrize("engine_access", ["insert", "delete", "merge", "update"])
def test_a_data_change_verb_scores_as_the_keys_update(engine_access):
    assert _sql_access_status("update", engine_access) == ["pass"]


@pytest.mark.parametrize("key_access,engine_access", [("read", "insert"), ("update", "lock"), ("update", "read")])
def test_other_access_words_still_differ(key_access, engine_access):
    assert _sql_access_status(key_access, engine_access) == ["fail"]


def test_a_jcllib_library_phantom_is_attributed_to_its_horror_with_the_keys_why():
    why = "JCLLIB ORDER names a library search path, not a dataset a step reads"
    ph = dict(channel="jcl_datasets", dsn="PROD.BDLD.PROCLIB", step=None, line=3, why=why, horror="H-0071")
    eng = FakeEngine(raw_imports={"j.jcl": ["PROD.BDLD.PROCLIB"]})
    sc = ec.Score()
    ec.score_jcl_datasets(sc, "j.jcl", dict(language="jcl", jcl_datasets=[], phantoms=[ph]), eng)
    assert [(c.fact, c.status, c.horror, c.detail) for c in sc.checks] == [
        ("raw import PROD.BDLD.PROCLIB", "phantom", "H-0071", why)
    ]
