"""The report-surface cluster: #3111, #3112, #3113, #3114.

All four issues came out of one real-repo plausibility audit (IBM's
zopeneditor-sample: COBOL/PL-I/JCL/HLASM/REXX, 51 files) and all four change
what the risk surface CLAIMS rather than how anything is computed:

* #3111 -- spec_match is opt-in, default OFF (absent, not 0.0, when off)
* #3112 -- the Cumulative Risk composite is removed
* #3113 -- the brief leads with the dependency story; 11 and 12 are merged
* #3114 -- documentation is reclassified as coverage, not a risk driver

The shared defect they fix: the brief's drivers line took the top 4 vectors by
raw value, and spec_match/documentation are both "fraction NOT covered by a
convention" meters that sit at ceiling on most codebases. They occupied 2 of 4
slots on all ten top-10 entries, so a line meant to discriminate between files
reprinted two constants.
"""

import pytest

from gitgalaxy.metrics.signal_processor import SignalProcessor
from gitgalaxy.recorders.llm_recorder import LLMRecorder
from gitgalaxy.standards import analysis_lens


# ---------------------------------------------------------------- #3111


def test_spec_match_is_declared_optional_and_off_by_default():
    assert "spec_match" in analysis_lens.OPTIONAL_VECTORS
    assert analysis_lens.inactive_vectors() == {"spec_match"}
    assert analysis_lens.inactive_vectors({}) == {"spec_match"}
    assert analysis_lens.inactive_vectors({"SPEC_ALIGNMENT": False}) == {"spec_match"}


def test_enabling_spec_alignment_activates_the_vector():
    assert analysis_lens.inactive_vectors({"SPEC_ALIGNMENT": True}) == set()


def test_optional_vectors_name_real_schema_entries():
    """A typo here would silently disable nothing, or hide a real vector."""
    schema = analysis_lens.RECORDING_SCHEMAS["RISK_SCHEMA"]
    for vector in analysis_lens.OPTIONAL_VECTORS:
        assert vector in schema, f"{vector} is not a RISK_SCHEMA name"
    for vector in analysis_lens.CONTEXT_VECTORS:
        assert vector in schema, f"{vector} is not a RISK_SCHEMA name"


def test_optional_and_context_families_are_disjoint():
    """Off and reframed are different asks -- #3114 is explicit about that."""
    overlap = set(analysis_lens.OPTIONAL_VECTORS) & set(analysis_lens.CONTEXT_VECTORS)
    assert not overlap, f"a vector cannot be both disabled and reframed: {overlap}"


def test_processor_does_not_compute_spec_alignment_when_disabled():
    off = SignalProcessor(aperture_config={})
    on = SignalProcessor(aperture_config={"SPEC_ALIGNMENT": True})
    assert off.spec_alignment_enabled is False
    assert on.spec_alignment_enabled is True


def test_spec_formula_still_works_when_enabled():
    """Opt-in must not mean broken: the formula itself is untouched."""
    processor = SignalProcessor(aperture_config={"SPEC_ALIGNMENT": True})
    # 4 entities, no spec tags -> fully unaligned -> ceiling.
    assert processor._calc_spec_alignment({"func_start": 4, "class_start": 0, "spec_exposure": 0}, 1.0) == 100.0
    # every entity tagged -> fully aligned -> floor.
    assert processor._calc_spec_alignment({"func_start": 4, "class_start": 0, "spec_exposure": 4}, 1.0) == 0.0


def test_disabled_vector_is_absent_from_the_section_6_table_not_zeroed():
    """The point of #3111: a 0.0 row asserts full alignment. Omit it."""
    recorder = LLMRecorder()
    rendered = "\n".join(_section_six(recorder))
    assert "Spec Alignment" not in rendered.split("> `Spec Alignment")[0]
    assert "not measured" in rendered
    assert "--spec-alignment" in rendered


def test_enabled_vector_appears_in_the_table():
    recorder = LLMRecorder(scan_config={"SPEC_ALIGNMENT": True})
    rendered = "\n".join(_section_six(recorder))
    assert "Spec Alignment" in rendered
    assert "not measured" not in rendered


def _section_six(recorder):
    """Render just the rows a section-6 table would contain for one file."""
    schema = recorder.RISK_SCHEMA
    vector = [50.0] * len(schema)
    out = []
    labels = analysis_lens.RECORDING_SCHEMAS.get("EXPOSURE_LABELS", {})
    for i, slug in enumerate(schema):
        if slug in recorder.inactive_vectors:
            continue
        label = recorder._surface_label(slug, labels.get(slug, slug))
        if slug in recorder.CONTEXT_VECTORS:
            label = f"{label} _(coverage)_"
        out.append(f"| {label} | {vector[i]} |")
    optional = analysis_lens.OPTIONAL_VECTORS
    for slug in sorted(recorder.inactive_vectors):
        flag = "--" + optional.get(slug, slug).lower().replace("_", "-")
        out.append(f"> `{recorder._surface_label(slug, labels.get(slug, slug))}` was not measured. Use `{flag}`.")
    return out


# ---------------------------------------------------------------- #3114


def test_documentation_is_declared_a_context_vector():
    assert "documentation" in analysis_lens.CONTEXT_VECTORS
    # reframed, NOT disabled -- it is still computed and still reported.
    assert "documentation" not in analysis_lens.OPTIONAL_VECTORS
    assert "documentation" not in analysis_lens.inactive_vectors()


def test_ceiling_pinned_vectors_are_excluded_from_the_drivers_line():
    """The measured defect, reproduced.

    A vector with spec_match and documentation both at ceiling and four
    ordinary vectors below them. Before the filter the drivers line reported
    the two constants; it must now report only what differentiates.
    """
    recorder = LLMRecorder()
    schema = recorder.RISK_SCHEMA
    vector = [0.0] * len(schema)
    vector[schema.index("spec_match")] = 100.0
    vector[schema.index("documentation")] = 100.0
    vector[schema.index("cognitive_load")] = 90.0
    vector[schema.index("state_flux")] = 80.0
    vector[schema.index("safety_score")] = 10.0
    vector[schema.index("tech_debt")] = 5.0

    drivers = " ".join(recorder._driver_labels(vector))
    assert "Spec" not in drivers, "a vector that was not measured cannot be a driver"
    assert "Doc" not in drivers, "documentation coverage is not a fragility driver (#3114)"
    # and the four that DO differentiate all survive
    for expected in ("90.0%", "80.0%", "10.0%", "5.0%"):
        assert expected in drivers


def test_documentation_is_still_reported_as_coverage():
    """#3114 asked for reframing, so nothing may be silently dropped."""
    recorder = LLMRecorder()
    schema = recorder.RISK_SCHEMA
    vector = [0.0] * len(schema)
    vector[schema.index("documentation")] = 73.5
    labels = recorder._coverage_labels(vector)
    assert labels == ["73.5% of unit weight undocumented"]


def test_driver_line_skips_zero_and_respects_the_limit():
    recorder = LLMRecorder()
    schema = recorder.RISK_SCHEMA
    vector = [0.0] * len(schema)
    vector[schema.index("cognitive_load")] = 42.0
    assert len(recorder._driver_labels(vector)) == 1
    vector = [7.0] * len(schema)
    assert len(recorder._driver_labels(vector, limit=3)) == 3


# ---------------------------------------------------------------- #3112


def test_forensic_report_no_longer_carries_the_cumulative_composite():
    processor = SignalProcessor()
    report = processor.generate_forensic_report(
        [
            {
                "path": "a.py",
                "name": "a.py",
                "lang_id": "python",
                "risk_vector": [50.0] * len(processor.RISK_SCHEMA),
                "file_impact": 10.0,
                "telemetry": {},
            }
        ]
    )
    assert "cumulative_risk" not in report, "removed in #3112 -- a unitless sum of mixed-unit vectors"
    assert "file_impact" in report, "the unit-honest replacement ranking must exist"


def test_signal_processor_has_no_cumulative_risk_helper_left():
    assert not hasattr(SignalProcessor, "get_cumulative_risk")


# ---------------------------------------------------------------- #3113


def test_blast_radius_sentence_states_a_consequence():
    recorder = LLMRecorder()
    sentence = recorder._blast_radius_sentence(
        {
            "raw_imports": ["x", "y"],
            "telemetry": {
                "network_metrics": {
                    "in_degree": 3,
                    "normalized_blast_radius": 0.42,
                    "ecosystem_role": "Hub",
                }
            },
        }
    )
    assert "3" in sentence and "importer" in sentence
    assert "2" in sentence, "outbound count comes from raw_imports, not the resolved out_degree"
    assert "0.42" in sentence


def test_blast_radius_sentence_is_honest_about_an_isolated_file():
    recorder = LLMRecorder()
    assert "isolated" in recorder._blast_radius_sentence({})


def test_blast_radius_outbound_matches_raw_imports_not_out_degree():
    """Regression: out_degree can be 0 while raw_imports lists two names.

    Printing "depends on 0" directly above a line naming two imports reads as
    a bug, and did during this cluster's development.
    """
    recorder = LLMRecorder()
    sentence = recorder._blast_radius_sentence(
        {
            "raw_imports": ["CUSTCOPY", "TRANREC"],
            "telemetry": {"network_metrics": {"in_degree": 1, "out_degree": 0}},
        }
    )
    assert "depends on **2**" in sentence


def test_executive_summary_leads_with_the_dependency_story():
    recorder = LLMRecorder()
    parsed = [
        {
            "path": "INCLUDES/BALSTATS.inc",
            "file_impact": 5.0,
            "raw_imports": [],
            "telemetry": {"popularity": 3},
        },
        {
            "path": "JCL/RUN.jcl",
            "file_impact": 9.0,
            "raw_imports": ["a"] * 14,
            "telemetry": {"popularity": 0},
        },
    ]
    rendered = "\n".join(recorder._executive_summary_lines(parsed, {"verified_files": 2, "total_loc": 100}, {}))
    assert rendered.startswith("## 1. EXECUTIVE SUMMARY")
    # the two facts #3113 verified against source on the audit
    assert "BALSTATS.inc" in rendered and "3 in-repo" in rendered
    assert "RUN.jcl" in rendered and "14" in rendered


def test_executive_summary_refuses_to_rank_a_flat_graph():
    """#2556's discipline: with no resolvable imports, a "most depended upon"
    ranking is scan order wearing a superlative."""
    recorder = LLMRecorder()
    parsed = [
        {"path": "a.txt", "file_impact": 1.0, "raw_imports": [], "telemetry": {"popularity": 0}},
        {"path": "b.txt", "file_impact": 2.0, "raw_imports": [], "telemetry": {"popularity": 0}},
    ]
    rendered = "\n".join(recorder._executive_summary_lines(parsed, {}, {}))
    assert "none identifiable" in rendered
    assert "a.txt" not in rendered and "b.txt" not in rendered.split("Heaviest artifact")[0]


def test_lexicon_survives_as_an_appendix():
    """#3113 kept the lexicon deliberately -- the honesty is an asset."""
    recorder = LLMRecorder()
    lexicon = "\n".join(recorder._lexicon_lines())
    assert "APPENDIX A" in lexicon
    # the non-predictive disclaimer must still be present verbatim-ish
    assert "activity/content surface meters" in lexicon
    assert "#2982" in lexicon or "2982" in lexicon
    # and it must still carry the equations it always did
    assert "Sigmoid" in lexicon


@pytest.mark.parametrize("removed", ["## 11. CUMULATIVE RISK HITLIST", "## 12. SCANNED ARTIFACTS HITLIST"])
def test_the_two_duplicate_hitlists_are_gone(removed):
    """#3113 ask 3: 11 and 12 answered the same question twice."""
    import inspect

    import gitgalaxy.recorders.llm_recorder as module

    source = inspect.getsource(module)
    assert removed not in source
