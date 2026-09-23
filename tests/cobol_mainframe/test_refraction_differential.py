"""#3211: the refraction differential classifies every forge<->engine-DB delta with
a cause code and gates on the `unexplained` count.

The CI test scans each committed excerpt and fails if a run ADDS unexplained deltas
over the committed baseline. If the change is intended, read the run and bless it:

    python tests/tools/refraction_differential.py --update-baseline

and say in the PR description what moved and why. The full pinned corpora are gated
the same way but only when fetched (local): `--update-baseline --corpus NAME ...`.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import mainframe_corpus as mc
import refraction_differential as rd

EXCERPT_DIRS = sorted(p for p in rd.EXCERPTS.iterdir() if p.is_dir())
EXCERPT_TARGETS = rd._targets(None)  # (name, source, key, db=None)


# ==============================================================================
# The gate over real corpora
# ==============================================================================
def _assert_within_baseline(name: str, scope: str, summary, classified) -> None:
    base = rd._load_baseline().get(scope, {}).get(name, {}).get("unexplained", 0)
    new = [d for d in classified if rd.effective_cause(d) == rd.UNEXPLAINED]
    shown = "\n".join(f"  {d['program']}  {d['field']}/{d['side']}  {d['value']}" for d in new[:20])
    assert summary["unexplained"] <= base, (
        f"{name} [{scope}]: {summary['unexplained']} unexplained > baseline {base}. "
        f"Read the run, then bless with `python tests/tools/refraction_differential.py "
        f"--update-baseline{'' if scope == 'excerpts' else f' --corpus {name}'}`.\n{shown}"
    )


@pytest.mark.parametrize("target", EXCERPT_TARGETS, ids=lambda t: t[0])
def test_excerpt_no_new_unexplained(target):
    name, source, key, db = target
    summary, classified = rd.run_target(source, key, db)
    _assert_within_baseline(name, "excerpts", summary, classified)


@pytest.mark.parametrize("corpus", mc.load_manifest(), ids=lambda c: c["name"])
def test_full_corpus_no_new_unexplained(corpus):
    """Local only: skipped unless the corpus is fetched at its pin."""
    clone = mc.clone_path(corpus)
    if not (clone / ".git").exists():
        pytest.skip(f"{corpus['name']} not fetched (mainframe_corpus.py fetch)")
    key = next((k for n, _s, k, _d in EXCERPT_TARGETS if n == corpus["name"]), None)
    summary, classified = rd.run_target(mc.require_clone(corpus), key, mc.scan(corpus))
    _assert_within_baseline(corpus["name"], "full", summary, classified)


# ==============================================================================
# Baseline discipline
# ==============================================================================
def test_every_excerpt_in_baseline():
    excerpts = rd._load_baseline().get("excerpts", {})
    assert EXCERPT_DIRS
    for d in EXCERPT_DIRS:
        assert d.name in excerpts, d.name


def test_baseline_entries_carry_a_note():
    baseline = rd._load_baseline()
    for scope in ("excerpts", "full"):
        for name, entry in baseline.get(scope, {}).items():
            if entry["unexplained"] > 0:
                assert entry.get("note"), f"{scope}/{name} has unexplained deltas but no note"


# ==============================================================================
# Classifier unit tests (synthetic, no corpora)
# ==============================================================================
PROGRAM = "\n".join(
    [
        "       IDENTIFICATION DIVISION.",
        "       PROGRAM-ID. P.",
        "       DATA DIVISION.",
        "       WORKING-STORAGE SECTION.",
        "           COPY DFHAID.",
        "           COPY MAPSET.",
        "           COPY AMB.",
        "000100     COPY SEQCOPY.",
        "           EXEC SQL INCLUDE MYREC END-EXEC.",
        "       PROCEDURE DIVISION.",
        "       MAIN-PARA.",
        "           PERFORM SUB-PARA.",
        "           GOBACK.",
        "       SUB-PARA.",
        "           DISPLAY 'HI'.",
        "       DEAD-PARA.",
        "           DISPLAY 'X'.",
        "       MY-SECTION SECTION.",
        "       SEC-PARA.",
        "           DISPLAY 'Y'.",
        "",
    ]
)


@pytest.fixture(scope="module")
def mini_repo(tmp_path_factory):
    repo = tmp_path_factory.mktemp("mini_repo")
    (repo / "P.cbl").write_text(PROGRAM, encoding="utf-8")
    (repo / "SEQCOPY.cpy").write_text("       01 SEQ-REC PIC X.\n", encoding="utf-8")
    (repo / "MYREC.cpy").write_text("       01 MY-REC PIC X.\n", encoding="utf-8")
    (repo / "MAPSET.bms").write_text("MAPSET DFHMSD TYPE=MAP\n", encoding="utf-8")
    for sub in ("a", "b"):  # two same-stem copybooks -> AMBIGUOUS
        (repo / sub).mkdir()
        (repo / sub / "AMB.cpy").write_text("       01 AMB-REC PIC X.\n", encoding="utf-8")
    return repo


def _row(**kw):
    """A single-program row in compare()'s shape, with only the fields a test sets."""
    return {
        "file": "P.cbl",
        "program_id": {"old": kw.get("pid_old", "P"), "db": kw.get("pid_db", ["P"])},
        "paragraphs": {
            "old_count": 0,
            "db_count": 0,
            "old_only": sorted(kw.get("para_old", [])),
            "db_only": sorted(kw.get("para_db", [])),
        },
        "dead": {"old": sorted(kw.get("dead_old", [])), "db_usage_status_1": sorted(kw.get("dead_db", []))},
        "copybooks": {
            "named": sorted(kw.get("cb_named", [])),
            "old_resolved": sorted(kw.get("cb_old", [])),
            "db_edges": sorted(kw.get("cb_db", [])),
        },
        "subsystems": {"old_cics": kw.get("cics", 0), "old_sql": kw.get("sql", 0), "db_signals": []},
        "records": {"old": sorted(kw.get("rec_old", [])), "db": sorted(kw.get("rec_db", []))},
        "transactions": {"old": sorted(kw.get("tx_old", [])), "db": sorted(kw.get("tx_db", []))},
        "forge_only": {
            "dd_files": sorted(kw.get("dd", [])),
            "inputs": sorted(kw.get("inputs", [])),
            "outputs": sorted(kw.get("outputs", [])),
            "unresolved_calls": sorted(kw.get("calls", [])),
            "orphaned_vars": kw.get("orphaned", 0),
        },
    }


def _cause(mini_repo, **kw):
    """The cause of the single delta the given row produces."""
    classified = rd.classify(mini_repo, [_row(**kw)], None)
    assert len(classified) == 1, classified
    return classified[0]["cause"]


def test_scope_terminator(mini_repo):
    assert _cause(mini_repo, dead_old=["GOBACK"]) == "scope_terminator"


def test_program_inlined_as_copybook(mini_repo):
    assert _cause(mini_repo, para_old=["FOREIGN-PARA"]) == "program_inlined_as_copybook"


def test_section_header(mini_repo):
    assert _cause(mini_repo, para_db=["MY-SECTION"]) == "section_header"


def test_area_b_header(mini_repo):
    assert _cause(mini_repo, para_db=["PHANTOM-LINE"]) == "area_b_header"


def test_entry_point(mini_repo):
    assert _cause(mini_repo, dead_db=["MAIN-PARA"]) == "entry_point"


def test_ambiguous_copy_target(mini_repo):
    assert _cause(mini_repo, cb_old=["AMB"]) == "ambiguous_copy_target"


def test_exec_sql_include(mini_repo):
    assert _cause(mini_repo, cb_db=["MYREC"]) == "exec_sql_include"


def test_sequence_number_field(mini_repo):
    assert _cause(mini_repo, cb_db=["SEQCOPY"]) == "sequence_number_field"


def test_system_copybook(mini_repo):
    assert _cause(mini_repo, cb_named=["DFHAID"]) == "system_copybook"


def test_bms_symbolic_map(mini_repo):
    assert _cause(mini_repo, cb_named=["MAPSET"]) == "bms_symbolic_map"


def test_forge_only_is_stated_absence(mini_repo):
    assert _cause(mini_repo, dd=["CUSTFILE"]) == "stated_absence"


def test_subsystem_is_stated_absence(mini_repo):
    assert _cause(mini_repo, cics=5) == "stated_absence"


def test_engine_only_record_field_is_forge_flat_schema(mini_repo):
    """#3246: a field the engine carries that the forge's flat reader dropped is
    explained by the forge's known limitation -- NOT stated_absence (the DB now
    carries record layouts), which is exactly what this issue set out to change."""
    assert _cause(mini_repo, rec_db=["ACCT_ID"]) == "forge_flat_schema"


def test_forge_only_record_field_is_unexplained(mini_repo):
    """A field the forge read that the engine's walker missed is a real engine gap,
    left unexplained until a validated key adjudicates it."""
    assert _cause(mini_repo, rec_old=["ACCT_ID"]) == rd.UNEXPLAINED


def test_transaction_delta_is_unexplained(mini_repo):
    """#3247: both the forge reader and the engine parse the same CSD decks, so a
    transaction delta is a real parser defect on one side with no mechanism cause --
    left unexplained until a validated key adjudicates it (transaction is
    INDEPENDENT)."""
    assert _cause(mini_repo, tx_db=["OCRA"]) == rd.UNEXPLAINED
    assert _cause(mini_repo, tx_old=["OCRA"]) == rd.UNEXPLAINED


def test_usage_status_not_reachability(mini_repo):
    # Forge calls a real own unit dead; the engine's usage_status does not flag it.
    # The two signals differ by design (#3198) -- explained, not a bug.
    assert _cause(mini_repo, dead_old=["SUB-PARA"]) == "usage_status_not_reachability"


def test_unexplained_when_no_cause(mini_repo):
    # A real own paragraph the forge reports and the engine does not: no mechanism,
    # and (here) no key to adjudicate -> unexplained.
    assert _cause(mini_repo, para_old=["SUB-PARA"]) == rd.UNEXPLAINED


def _key(**prog):
    entry = {
        "program_id": "P",
        "units": [{"name": "MAIN-PARA", "kind": "paragraph"}, {"name": "SUB-PARA", "kind": "paragraph"}],
        "dead": {"SUB-PARA": {"reason": "unreachable", "trivial": False}},
        "copybooks": [],
        "verification": {"status": "validated"},
    }
    entry.update(prog)
    return {"programs": {"P.cbl": entry}}


def test_key_verdict_shared_model_does_not_clear_unexplained(mini_repo):
    """#3219: for units/dead the key shares the forge's control-flow model, so its
    agreement is not independent evidence and never clears `unexplained`. A real
    own paragraph the forge reports (no mechanism cause) is the case to check."""
    classified = rd.classify(mini_repo, [_row(para_old=["SUB-PARA"])], _key())
    summary = rd.summarize_causes(classified)
    assert summary["unexplained"] == 1
    assert classified[0]["verdict"]["confidence"] == "shared_model"


def test_key_verdict_clears_independent_field(mini_repo):
    """A program_id delta has no mechanism cause, but the key is an independent
    oracle for it, so an adjudicated verdict removes it from `unexplained`."""
    classified = rd.classify(mini_repo, [_row(pid_old="WRONG", pid_db=["P"])], _key())
    summary = rd.summarize_causes(classified)
    assert summary["unexplained"] == 0
    assert summary["by_cause"].get("key:old-parser defect") == 1


def test_record_verdict_needs_explicit_validation(mini_repo):
    """#3246: record layouts are auto-drafted even on an otherwise-validated
    program, so a forge-only record delta stays `unexplained` until the program
    is signed off with `records_validated` -- then the key (independent) clears
    it. `ACCT_ID` is a real field of the key here, so the forge is right and the
    engine has the gap."""
    rec = [{"name": "ACCT-ID", "level": 5, "pic": "9(11)"}]
    unvalidated = rd.classify(mini_repo, [_row(rec_old=["ACCT_ID"])], _key(records=rec))
    assert rd.summarize_causes(unvalidated)["unexplained"] == 1

    validated = rd.classify(mini_repo, [_row(rec_old=["ACCT_ID"])], _key(records=rec, records_validated=True))
    summary = rd.summarize_causes(validated)
    assert summary["unexplained"] == 0
    assert summary["by_cause"].get("key:engine defect") == 1


def test_transaction_verdict_needs_explicit_validation(mini_repo):
    """#3247: transactions are auto-drafted from the key's own CSD reader, so a
    forge-only transaction delta stays `unexplained` until the program is signed
    off with `transactions_validated` -- then the key (independent) clears it.
    `OCRA` is a key transaction here, so the forge is right and the engine has the
    gap."""
    unvalidated = rd.classify(mini_repo, [_row(tx_old=["OCRA"])], _key(transactions=["OCRA"]))
    assert rd.summarize_causes(unvalidated)["unexplained"] == 1

    validated = rd.classify(
        mini_repo, [_row(tx_old=["OCRA"])], _key(transactions=["OCRA"], transactions_validated=True)
    )
    summary = rd.summarize_causes(validated)
    assert summary["unexplained"] == 0
    assert summary["by_cause"].get("key:engine defect") == 1


# ==============================================================================
# #3250: PL/I record layouts -- the key's independent reader vs the engine
# ==============================================================================
def _pli_row(old=(), db=()):
    return {"file": "PLI/P.pli", "language": "pli", "pli_records": {"old": sorted(old), "db": sorted(db)}}


def test_a_pli_record_delta_is_a_real_finding_not_a_stated_absence(mini_repo):
    """The DB carries PL/I records now, so a disagreement between the two readers
    is a parser defect on one side (unexplained until a validated key rules)."""
    classified = rd.classify(mini_repo, [_pli_row(old=["REC.A", "REC.B"], db=["REC.A", "REC.C"])], None)
    assert sorted((d["side"], d["value"], d["cause"]) for d in classified) == [
        ("db", "REC.C", rd.UNEXPLAINED),
        ("old", "REC.B", rd.UNEXPLAINED),
    ]


def test_pli_rows_stay_out_of_the_cobol_summary(mini_repo):
    rows = [_pli_row(old=["REC.A"], db=["REC.A"])]
    assert rd.flatten(rows) == []
    assert rd.to_markdown({"repo": "r", "commit": "0" * 8}, rows).count("PLI/P.pli") == 0


def test_pli_record_verdict_needs_explicit_validation(mini_repo):
    """Drafted like COBOL records (#3246): a PL/I delta adjudicates only once the
    file is signed off with `records_validated`. `REC.B` is a real leaf of the key
    here, so the key reader is right and the engine has the gap."""
    items = [
        {"ordinal": 0, "parent": None, "level": 1, "name": "REC"},
        {"ordinal": 1, "parent": 0, "level": 2, "name": "B"},
    ]
    key = {"programs": {}, "pli_programs": {"PLI/P.pli": {"records": items, "records_validated": False}}}
    assert rd.summarize_causes(rd.classify(mini_repo, [_pli_row(old=["REC.B"])], key))["unexplained"] == 1

    key["pli_programs"]["PLI/P.pli"]["records_validated"] = True
    summary = rd.summarize_causes(rd.classify(mini_repo, [_pli_row(old=["REC.B"])], key))
    assert summary["unexplained"] == 0
    assert summary["by_cause"] == {"key:engine defect": 1}
